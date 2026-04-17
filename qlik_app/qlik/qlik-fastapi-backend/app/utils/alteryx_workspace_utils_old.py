# qlikAI-backend/utils/alteryx_workspace_utils.py

import os
import requests
import jwt
import time
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

ALTERYX_BASE_URL = "https://us1.alteryxcloud.com"
ALTERYX_TOKEN_URL = "https://pingauth.alteryxcloud.com/as/token"

# Client ID shown on the OAuth2.0 API Tokens page — used for refresh grant
ALTERYX_CLIENT_ID = os.getenv("ALTERYX_CLIENT_ID", "")
#print(ALTERYX_CLIENT_ID)    
# Client secret — required by Ping Identity for the refresh_token grant
ALTERYX_CLIENT_SECRET = os.getenv("ALTERYX_CLIENT_SECRET", "")


# ---------------------------------------------------------------------------
# Token container
# ---------------------------------------------------------------------------

@dataclass
class AlteryxSession:
    access_token: str
    refresh_token: Optional[str] = None
    workspace_name: Optional[str] = None
    workspace_id: Optional[str] = None   # Keep as str — consistent across all files
    custom_url: Optional[str] = None  # e.g., "workspace-name.us1.alteryxcloud.com"


# ---------------------------------------------------------------------------
# Build session from .env (used when no token is supplied by the UI)
# ---------------------------------------------------------------------------

def get_session_from_env() -> AlteryxSession:
    """Build a session from environment variables."""
    access_token = os.getenv("ALTERYX_ACCESS_TOKEN", "")
    refresh_token = os.getenv("ALTERYX_REFRESH_TOKEN", "")

    if not access_token and not refresh_token:
        raise ValueError(
            "No Alteryx credentials found. Set ALTERYX_ACCESS_TOKEN "
            "(and optionally ALTERYX_REFRESH_TOKEN) in your .env file."
        )

    return AlteryxSession(
        access_token=access_token,
        refresh_token=refresh_token,
        workspace_name=os.getenv("ALTERYX_WORKSPACE_NAME"),
        workspace_id=os.getenv("ALTERYX_WORKSPACE_ID"),
    )


# ---------------------------------------------------------------------------
# Token refresh — Ping Identity OAuth2
# ---------------------------------------------------------------------------

def refresh_access_token(refresh_token: str) -> tuple[str, Optional[str]]:
    """
    Exchange a refresh token for a new access token via Ping Identity.

    Returns (new_access_token, new_refresh_token).
    new_refresh_token may be None if the server doesn't rotate it.
    Works with or without CLIENT_SECRET.
    """
    print(f"\n🔄 [refresh_access_token] Called - Using refresh_token to request new access_token...")
    
    data: dict = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": ALTERYX_CLIENT_ID,
    }
    # Include client_secret when configured
    if ALTERYX_CLIENT_SECRET:
        data["client_secret"] = ALTERYX_CLIENT_SECRET
        print(f"   Using CLIENT_ID + CLIENT_SECRET")
    else:
        print(f"   Using CLIENT_ID only (no CLIENT_SECRET)")

    try:
        print(f"   📡 POST to {ALTERYX_TOKEN_URL}...")
        resp = requests.post(
            ALTERYX_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
            timeout=15,
        )
        
        if resp.status_code == 200:
            body = resp.json()
            new_access = body["access_token"]
            new_refresh = body.get("refresh_token")
            print(f"\n✅ [refresh_access_token] SUCCESS!")
            print(f"   New access_token received (valid next 5 minutes)")
            if new_refresh:
                print(f"   New refresh_token received (rotated, valid 365 days)")
            else:
                print(f"   Refresh token not rotated (will use existing one)")
            return new_access, new_refresh
        else:
            print(f"\n❌ [refresh_access_token] FAILED with status {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            print(f"   Falling back to current token (may expire soon)")
            return refresh_token, None
    except Exception as e:
        print(f"\n❌ [refresh_access_token] ERROR: {e}")
        print(f"   Falling back to current token (may expire soon)")
        return refresh_token, None


# ---------------------------------------------------------------------------
# Token expiration checking
# ---------------------------------------------------------------------------

def is_token_expired(token: str, buffer_seconds: int = 30) -> bool:
    """
    Check if JWT token is expired or expiring soon.
    
    Args:
        token: JWT access/refresh token
        buffer_seconds: Refresh if expiring within this many seconds (default 30s)
    
    Returns:
        True if token is expired or expiring within buffer_seconds
    """
    if not token:
        return True
    
    try:
        # Decode JWT without verification (we just want the exp claim)
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = decoded.get("exp", 0)
        current_timestamp = time.time()
        
        # Check if expired or expiring soon
        if current_timestamp >= exp_timestamp - buffer_seconds:
            remaining = exp_timestamp - current_timestamp
            print(f"⏰ Token expiring in {remaining:.1f}s, refreshing now...")
            return True
        
        remaining = exp_timestamp - current_timestamp
        print(f"✅ Token valid for {remaining:.1f}s")
        return False
    except Exception as e:
        print(f"⚠️  Could not decode token: {e}. Treating as expired.")
        return True


def ensure_fresh_token(session: AlteryxSession) -> str:
    """
    Check if access token is expired. If so, refresh it using refresh_token.
    Returns a fresh access token.
    
    If both access_token and refresh_token are expired/missing, raises ValueError.
    """
    # First check: is access token still valid?
    if not is_token_expired(session.access_token):
        print(f"✓ Access token still valid, no refresh needed")
        return session.access_token
    
    # Access token is expired, try to refresh using refresh_token
    print(f"\n🔄 [ensure_fresh_token] ACCESS TOKEN EXPIRED - Attempting refresh via REFRESH_TOKEN...")
    
    if not session.refresh_token:
        print(f"\n❌ [ensure_fresh_token] CRITICAL: No refresh_token available!")
        raise ValueError(
            "Access token expired and no refresh_token available. "
            "Set ALTERYX_REFRESH_TOKEN in .env file (lasts 365 days)."
        )
    
    print(f"   Calling refresh_access_token() with refresh_token...")
    new_access, new_refresh = refresh_access_token(session.refresh_token)
    session.access_token = new_access
    if new_refresh:
        session.refresh_token = new_refresh
    
    print(f"\n✅ [ensure_fresh_token] Token refresh completed! Using new access_token for next request.")
    return session.access_token


# ---------------------------------------------------------------------------
# GET wrapper with PROACTIVE token refresh before each call
# ---------------------------------------------------------------------------

def _get_with_refresh(
    url: str,
    session: AlteryxSession,
    params: Optional[dict] = None,
) -> dict:
    """
    Authenticated GET with PROACTIVE token refresh:
      1. BEFORE calling API: Check if access token is expired/expiring
      2. If expired: Refresh using refresh_token (which lasts 365 days!)
      3. Make API call with fresh token
      4. On 401: Attempt one final refresh as fallback
      
    This ensures tokens never expire during API calls.
    Use ALTERYX_REFRESH_TOKEN (365 days) instead of just ACCESS_TOKEN (5 min).
    """
    def _do_get(token: str) -> requests.Response:
        return requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params=params,
            timeout=15,
        )

    # ✅ STEP 1: PROACTIVELY ensure token is fresh before making the call
    try:
        fresh_token = ensure_fresh_token(session)
    except ValueError as e:
        print(f"\n❌ FATAL: {e}")
        raise requests.HTTPError(str(e))

    # ✅ STEP 2: Make API call with fresh token
    resp = _do_get(fresh_token)

    # ✅ STEP 3: Handle 401 Unauthorized (fallback only)
    if resp.status_code == 401:
        error_detail = resp.text[:300] if resp.text else "Unauthorized"
        print(f"\n⚠️  [_get_with_refresh] 401 UNAUTHORIZED - FALLBACK REFRESH TRIGGERED")
        print(f"   (Note: Access token was already proactively refreshed in STEP 1)")
        print(f"   URL: {url}")
        print(f"   Response: {error_detail}")
        
        if session.refresh_token:
            print(f"\n   💡 [_get_with_refresh] FALLBACK: Attempting SECOND refresh using refresh_token...")
            try:
                new_token, new_refresh = refresh_access_token(session.refresh_token)
                session.access_token = new_token
                if new_refresh:
                    session.refresh_token = new_refresh
                print(f"\n   ✅ [_get_with_refresh] FALLBACK refresh succeeded! Retrying request...")
                resp = _do_get(new_token)
                print(f"   📊 Retry status: {resp.status_code}")
            except Exception as refresh_err:
                print(f"\n   ❌ [_get_with_refresh] FALLBACK refresh FAILED: {refresh_err}")
                raise requests.HTTPError(
                    f"401 Unauthorized. Final refresh failed: {error_detail}",
                    response=resp,
                )
        else:
            print(f"\n   ❌ [_get_with_refresh] No refresh_token available for fallback!")
            raise requests.HTTPError(
                f"401 Unauthorized and no refresh token available. {error_detail}",
                response=resp,
            )

    # ✅ STEP 4: Handle other HTTP errors
    if resp.status_code >= 400:
        error_detail = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
        print(f"\n❌ API ERROR {resp.status_code}:")
        print(f"   URL: {url}")
        print(f"   Response: {error_detail}")
        raise requests.HTTPError(
            f"API error {resp.status_code}: {error_detail}",
            response=resp,
        )

    try:
        return resp.json()
    except ValueError as e:
        raise ValueError(
            f"Invalid JSON from Alteryx ({url}, status {resp.status_code}): "
            f"{resp.text[:300]}"
        ) from e


# ---------------------------------------------------------------------------
# Workspace listing
# ---------------------------------------------------------------------------

def list_alteryx_workspaces(session: AlteryxSession) -> list[dict]:
    """Fetch all workspaces accessible to this token."""
    print(f"\n🔵 Fetching workspaces list...")
    
    # Try multiple endpoint variations
    endpoints = [
        f"{ALTERYX_BASE_URL}/v4/workspaces",
        f"{ALTERYX_BASE_URL}/iam/v1/workspaces",
        f"{ALTERYX_BASE_URL}/api/v1/workspaces",
    ]
    
    for endpoint in endpoints:
        try:
            print(f"  Trying: {endpoint}")
            data = _get_with_refresh(endpoint, session)
            
            # Normalize response
            if isinstance(data, list):
                workspaces = data
            else:
                workspaces = data.get("data", data.get("workspaces", []))
            
            if workspaces:
                print(f"  ✅ Found {len(workspaces)} workspace(s)")
                return workspaces
        except Exception as e:
            print(f"  ⚠️  Failed: {e}")
            continue
    
    print(f"  ❌ Could not fetch workspaces from any endpoint")
    raise ValueError(
        f"Unable to fetch workspaces. Your tokens may be expired. "
        f"Run: python app/utils/alteryx_auth_generator.py to refresh tokens."
    )


# ---------------------------------------------------------------------------
# Workspace name → ID resolution
# ---------------------------------------------------------------------------

def get_workspace_id_by_name(session: AlteryxSession, workspace_name: str) -> str:
    """
    Resolve workspace name → ID. Tries exact then partial match.
    Mutates session.workspace_id / session.workspace_name / session.custom_url on success.
    Raises ValueError if not found or ambiguous.
    """
    workspaces = list_alteryx_workspaces(session)

    # 1. Exact match (case-insensitive)
    for ws in workspaces:
        if ws.get("name", "").lower() == workspace_name.lower():
            session.workspace_id = str(ws["id"])
            session.workspace_name = ws["name"]
            session.custom_url = ws.get("custom_url")  # e.g., "workspace-name.us1.alteryxcloud.com"
            return session.workspace_id

    # 2. Partial match fallback
    matches = [ws for ws in workspaces if workspace_name.lower() in ws.get("name", "").lower()]

    if len(matches) == 1:
        session.workspace_id = str(matches[0]["id"])
        session.workspace_name = matches[0]["name"]
        session.custom_url = matches[0].get("custom_url")
        return session.workspace_id
    elif len(matches) > 1:
        names = [ws["name"] for ws in matches]
        raise ValueError(
            f"Ambiguous workspace name '{workspace_name}'. "
            f"Multiple matches: {names}. Use the full exact name."
        )
    else:
        available = [ws.get("name") for ws in workspaces]
        raise ValueError(
            f"No workspace found matching '{workspace_name}'. "
            f"Available: {available}"
        )


# ---------------------------------------------------------------------------
# Convenience entry point used by the FastAPI endpoint
# ---------------------------------------------------------------------------

def create_alteryx_session(
    access_token: str,
    workspace_name: str,
    refresh_token: Optional[str] = None,
) -> AlteryxSession:
    """
    Build and validate an AlteryxSession.

    Works with ACCESS_TOKEN + REFRESH_TOKEN (no CLIENT_SECRET needed).
    If access_token is empty, falls back to ALTERYX_ACCESS_TOKEN from env.

    Returns a fully populated AlteryxSession on success.
    Raises ValueError or requests.HTTPError on failure.
    """
    # Resolve tokens — UI values take priority, env values are fallback
    # resolved_access = access_token or os.getenv("ALTERYX_ACCESS_TOKEN", "")
    resolved_access = access_token  
    resolved_refresh = refresh_token or os.getenv("ALTERYX_REFRESH_TOKEN")

    # if not resolved_access:
    #     raise ValueError(
    #         "No access token available. Set ALTERYX_ACCESS_TOKEN in .env "
    #         "or provide it on the Connect page."
    #     )

    print(f"\n✅ Creating Alteryx session for workspace: {workspace_name}")
    
    session = AlteryxSession(
        access_token=resolved_access,
        refresh_token=resolved_refresh,
    )
    
    get_workspace_id_by_name(session, workspace_name)
    return session
