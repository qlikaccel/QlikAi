# app/utils/token_manager.py
"""
Token Manager for persistent token storage and lifecycle management.
Handles token refresh, persistence, and validation.
"""

import os
import json
import time
import logging
from typing import Optional, Tuple
from pathlib import Path
import threading

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

logger = logging.getLogger(__name__)

# Token storage file (persists refreshed tokens)
TOKEN_STORAGE_PATH = Path(__file__).parent.parent / "token_storage.json"
TOKEN_LOCK = threading.Lock()  # Prevent concurrent token refresh races

ALTERYX_TOKEN_URL = "https://pingauth.alteryxcloud.com/as/token"
ALTERYX_CLIENT_ID = os.getenv("ALTERYX_CLIENT_ID", "af1b5321-afe0-48c2-966a-c77d74e98085")
ALTERYX_CLIENT_SECRET = os.getenv("ALTERYX_CLIENT_SECRET", "")


class TokenManager:
    """Manages Alteryx token lifecycle with persistence and validation."""
    
    @staticmethod
    def _load_tokens_from_storage() -> dict:
        """Load tokens from persistent storage (JSON file)."""
        if TOKEN_STORAGE_PATH.exists():
            try:
                with open(TOKEN_STORAGE_PATH, 'r') as f:
                    data = json.load(f)
                    logger.debug("📁 Loaded tokens from storage file")
                    return data
            except Exception as e:
                logger.warning(f"⚠️  Could not load token storage: {e}")
                return {}
        return {}
    
    @staticmethod
    def _save_tokens_to_storage(access_token: str, refresh_token: Optional[str]) -> None:
        """Save tokens to persistent storage with metadata."""
        try:
            data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "timestamp": time.time(),
                "access_token_exp": TokenManager._get_token_expiry(access_token),
                "refresh_token_exp": TokenManager._get_token_expiry(refresh_token),
            }
            with open(TOKEN_STORAGE_PATH, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("💾 Tokens saved to persistent storage")
        except Exception as e:
            logger.error(f"❌ Could not save token storage: {e}")
    
    @staticmethod
    def _get_token_expiry(token: Optional[str]) -> Optional[float]:
        """Extract expiry timestamp from JWT token."""
        if not token or not HAS_JWT:
            return None
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded.get("exp")
        except Exception:
            return None
    
    @staticmethod
    def get_valid_tokens() -> Tuple[str, Optional[str]]:
        """
        Get valid tokens, trying multiple sources in order:
        1. Persistent storage (recently refreshed tokens)
        2. Environment variables (.env file)
        3. Raise error if none found
        """
        logger.info("🔍 Checking for valid tokens...")
        
        # 1. Try persistent storage first (most recent tokens)
        stored = TokenManager._load_tokens_from_storage()
        if stored.get("access_token") and stored.get("refresh_token"):
            access = stored["access_token"]
            refresh = stored["refresh_token"]
            
            if not TokenManager._is_token_expired(access, buffer=30):
                logger.info("✅ Using access token from storage")
                return access, refresh
            else:
                logger.info("⏰ Stored access token expired, will refresh")
                return access, refresh
        
        # 2. Fall back to environment variables
        access = os.getenv("ALTERYX_ACCESS_TOKEN", "")
        refresh = os.getenv("ALTERYX_REFRESH_TOKEN", "")
        
        if not access and not refresh:
            error = "❌ No tokens found. Set ALTERYX_REFRESH_TOKEN in .env"
            logger.error(error)
            raise ValueError(error)
        
        logger.info("✅ Using tokens from environment variables")
        return access, refresh
    
    @staticmethod
    def _is_token_expired(token: Optional[str], buffer: int = 30) -> bool:
        """Check if token is expired with buffer."""
        if not token or not HAS_JWT:
            return False
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp = decoded.get("exp", 0)
            remaining = exp - time.time()
            
            if remaining <= buffer:
                logger.info(f"⏰ Token expiring in {remaining:.1f}s")
                return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def refresh_token(refresh_token: str, max_retries: int = 3) -> Tuple[str, Optional[str]]:
        """
        Refresh access token with retry logic and thread safety.
        
        Returns: (new_access_token, new_refresh_token)
        """
        with TOKEN_LOCK:  # Prevent concurrent refresh race conditions
            logger.info(f"\n🔄 [TokenManager] Attempting token refresh (max {max_retries} retries)...")
            
            if not refresh_token:
                raise ValueError("No refresh token available for refresh attempt")
            
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"   Attempt {attempt}/{max_retries}...")
                    
                    import requests
                    
                    payload = {
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": ALTERYX_CLIENT_ID,
                    }
                    if ALTERYX_CLIENT_SECRET:
                        payload["client_secret"] = ALTERYX_CLIENT_SECRET
                    
                    resp = requests.post(
                        ALTERYX_TOKEN_URL,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        data=payload,
                        timeout=15,
                    )
                    
                    if resp.status_code == 200:
                        body = resp.json()
                        new_access = body.get("access_token", "")
                        new_refresh = body.get("refresh_token")
                        
                        if new_access:
                            logger.info(f"✅ Token refresh successful on attempt {attempt}")
                            
                            # Persist the new tokens
                            TokenManager._save_tokens_to_storage(new_access, new_refresh)
                            
                            return new_access, new_refresh
                        else:
                            raise ValueError("Empty access token in response")
                    
                    elif resp.status_code == 400:
                        error_body = resp.json()
                        error_desc = error_body.get("error_description", "")
                        
                        if "does not exist" in error_desc.lower():
                            logger.error(f"❌ Refresh token is INVALID (does not exist)")
                            logger.error(f"   Error: {error_desc}")
                            raise ValueError(
                                "Refresh token is invalid or has been revoked. "
                                "Generate a new token from Alteryx Cloud."
                            )
                        else:
                            # Temporary error, retry
                            logger.warning(f"   ⚠️  Temporary error (attempt {attempt}): {error_desc}")
                            if attempt < max_retries:
                                time.sleep(2 ** attempt)  # Exponential backoff
                                continue
                    
                    else:
                        logger.warning(f"   ⚠️  HTTP {resp.status_code}: {resp.text[:200]}")
                        if attempt < max_retries:
                            time.sleep(2 ** attempt)
                            continue
                
                except requests.exceptions.Timeout:
                    logger.warning(f"   ⚠️  Request timeout (attempt {attempt})")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                
                except requests.exceptions.ConnectionError:
                    logger.warning(f"   ⚠️  Connection error (attempt {attempt})")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                
                except Exception as e:
                    logger.error(f"   ❌ Unexpected error: {str(e)}")
                    raise
            
            raise ValueError(
                f"Token refresh failed after {max_retries} attempts. "
                "Check your refresh token or network connectivity."
            )
    
    @staticmethod
    def get_fresh_access_token(current_access: str, refresh_token: str) -> Tuple[str, Optional[str]]:
        """
        Get a fresh access token if needed.
        Returns: (access_token, refresh_token)
        """
        if not TokenManager._is_token_expired(current_access, buffer=30):
            logger.debug("✅ Current access token is still valid")
            return current_access, refresh_token
        
        logger.info("🔄 Access token expired, refreshing...")
        return TokenManager.refresh_token(refresh_token)
    
    @staticmethod
    def validate_refresh_token(refresh_token: str) -> bool:
        """
        Validate that a refresh token is functional.
        Returns True if valid, False if invalid.
        """
        try:
            TokenManager.refresh_token(refresh_token, max_retries=1)
            return True
        except ValueError as e:
            if "invalid" in str(e).lower() or "does not exist" in str(e).lower():
                logger.error(f"❌ Refresh token validation failed: {e}")
                return False
            raise
        except Exception as e:
            logger.warning(f"⚠️  Refresh token validation inconclusive: {e}")
            return False
    
    @staticmethod
    def clear_storage() -> None:
        """Clear persistent token storage (use when manually resetting tokens)."""
        try:
            if TOKEN_STORAGE_PATH.exists():
                TOKEN_STORAGE_PATH.unlink()
                logger.info("🗑️  Token storage cleared")
        except Exception as e:
            logger.error(f"Error clearing token storage: {e}")
    
    @staticmethod
    def _get_recommendations(access_env: str, refresh_env: str, access_expired: bool, refresh_valid: bool) -> list:
        """Generate recommendations based on token state."""
        recommendations = []
        
        if not refresh_env:
            recommendations.append("❌ MISSING: ALTERYX_REFRESH_TOKEN not in .env")
            recommendations.append("   → Set ALTERYX_REFRESH_TOKEN from Alteryx Cloud")
        elif not refresh_valid:
            recommendations.append("❌ INVALID: Refresh token is no longer valid")
            recommendations.append("   → Generate new token from Alteryx Cloud → Settings → API Keys")
        else:
            recommendations.append("✅ Refresh token is valid and functional")
        
        if not access_env:
            recommendations.append("ℹ️  No access token in .env (normal - will be auto-generated)")
        elif access_expired:
            recommendations.append("ℹ️  Access token has expired (normal - will auto-refresh)")
        else:
            recommendations.append("✅ Access token is valid")
        
        return recommendations
