# app/routers/alteryx_router.py

import logging
import os
import requests
from fastapi import APIRouter, HTTPException, Header, Response
from typing import Optional
from pydantic import BaseModel
import json

from app.utils.alteryx_workspace_utils import (
    AlteryxSession,
    create_alteryx_session,
    list_alteryx_workflows,
    ALTERYX_BASE_URL,
    ensure_fresh_token,
    get_workspace_id_by_name,
)
from app.utils.token_manager import TokenManager

router = APIRouter(prefix="/api/alteryx", tags=["Alteryx"])
logger = logging.getLogger(__name__)

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AlteryxAuthRequest(BaseModel):
    access_token: Optional[str] = ""
    refresh_token: Optional[str] = None
    workspace_name: str


class AlteryxAuthResponse(BaseModel):
    status: str
    workspace_name: str
    workspace_id: str
    access_token: str
    refresh_token: Optional[str] = None


class AlteryxWorkflow(BaseModel):
    id: str
    name: str
    lastModifiedDate: Optional[str] = None
    runCount: Optional[int] = None
    credentialType: Optional[str] = None
    workerTag: Optional[str] = None
    description: Optional[str] = None
    ownerId: Optional[str] = None
    isPublic: Optional[bool] = None


# ── Health Check / Connection Verification ──────────────────────────────────

@router.get("/health")
def alteryx_health_check():
    """
    ✅ VERIFICATION ENDPOINT
    Simple health check to verify Alteryx backend connectivity.
    Returns credentials status without making actual API calls.
    """
    logger.info("🔵 Health check requested")
    
    access_token = os.getenv("ALTERYX_ACCESS_TOKEN", "")
    refresh_token = os.getenv("ALTERYX_REFRESH_TOKEN", "")
    workspace_name = os.getenv("ALTERYX_WORKSPACE_NAME", "")
    workspace_id = os.getenv("ALTERYX_WORKSPACE_ID", "")
    
    has_access = bool(access_token)
    has_refresh = bool(refresh_token)
    
    logger.info(f"  Access Token: {'✅ Present' if has_access else '❌ Missing'}")
    logger.info(f"  Refresh Token: {'✅ Present' if has_refresh else '❌ Missing'}")
    logger.info(f"  Workspace Name: {workspace_name if workspace_name else '❌ Missing'}")
    logger.info(f"  Workspace ID: {workspace_id if workspace_id else '❌ Missing'}")
    
    if not (has_access or has_refresh):
        logger.error("❌ Health check FAILED: No credentials found")
        raise HTTPException(
            status_code=401,
            detail="No Alteryx credentials configured. Set ALTERYX_REFRESH_TOKEN in .env"
        )
    
    logger.info("✅ Health check PASSED: Credentials present")
    
    return {
        "status": "healthy",
        "message": "Alteryx backend is ready",
        "credentials": {
            "has_access_token": has_access,
            "has_refresh_token": has_refresh,
            "workspace_name": workspace_name or "not-configured",
            "workspace_id": workspace_id or "not-configured",
        },
        "endpoints": {
            "validate_auth": "POST /api/alteryx/validate-auth",
            "get_workflows": "GET /api/alteryx/workflows",
            "debug": "GET /api/alteryx/debug/raw-workflows",
        }
    }


@router.post("/test-connection")
def test_alteryx_connection():
    """
    ✅ VERIFICATION ENDPOINT
    Validates your Alteryx credentials and token refresh capability.
    Use this to diagnose token issues before fetching workflows.
    
    Returns detailed status about:
    - Refresh token validity
    - Token refresh capability
    - Workspace accessibility
    """
    logger.info("🔵 Testing Alteryx connection...")
    
    refresh_token = os.getenv("ALTERYX_REFRESH_TOKEN", "")
    if not refresh_token:
        logger.error("❌ No refresh token found in .env")
        raise HTTPException(
            status_code=401, 
            detail={
                "error": "MISSING_REFRESH_TOKEN",
                "message": "ALTERYX_REFRESH_TOKEN not configured in .env",
                "action": "Set ALTERYX_REFRESH_TOKEN from Alteryx Cloud → Settings → API Keys"
            }
        )
    
    try:
        logger.info("   1️⃣ Validating refresh token...")
        if not TokenManager.validate_refresh_token(refresh_token):
            raise ValueError("Refresh token validation returned False")
        
        logger.info("   2️⃣ Obtaining fresh access token...")
        access_token, new_refresh = TokenManager.get_fresh_access_token("", refresh_token)
        
        if not access_token:
            raise ValueError("No access token obtained")
        
        logger.info("   3️⃣ Creating authenticated session...")
        session = AlteryxSession(
            access_token=access_token,
            refresh_token=new_refresh or refresh_token
        )
        
        logger.info("✅ All connection tests PASSED!")
        
        return {
            "status": "success",
            "message": "Alteryx connection verified",
            "tests": {
                "refresh_token_valid": True,
                "access_token_obtained": True,
                "session_created": True,
                "ready_to_fetch_workflows": True
            },
            "token_info": {
                "access_token_valid_for": "~5 minutes (Alteryx server limit)",
                "refresh_token_valid_for": "~365 days (Alteryx server limit)",
                "refresh_token_rotated": new_refresh is not None
            }
        }
        
    except ValueError as e:
        error_msg = str(e)
        
        if "invalid" in error_msg.lower() or "does not exist" in error_msg.lower():
            logger.error(f"❌ Refresh token is INVALID: {error_msg}")
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "INVALID_REFRESH_TOKEN",
                    "message": "Your refresh token is no longer valid",
                    "possible_causes": [
                        "Token has expired (after 365 days)",
                        "Token was revoked in Alteryx Cloud",
                        "Token permissions were changed",
                        "Alteryx account credentials were changed"
                    ],
                    "action": "Generate a new token: Alteryx Cloud → Settings → API Keys → Generate New Key",
                    "details": error_msg
                }
            )
        else:
            logger.error(f"❌ Validation failed: {error_msg}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "VALIDATION_FAILED",
                    "message": str(e),
                    "action": "Check your .env configuration and network connectivity"
                }
            )
    
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 401
        error_detail = e.response.text if e.response is not None else str(e)
        logger.error(f"❌ HTTP Error {status_code}: {error_detail}")
        raise HTTPException(status_code=status_code, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "INTERNAL_ERROR",
                "message": str(e),
                "action": "Check backend logs for details"
            }
        )




@router.post("/validate-auth", response_model=AlteryxAuthResponse)
def validate_alteryx_auth(config: AlteryxAuthRequest):
    """
    Step 1: Called from ConnectPage.
    Validates credentials and resolves workspace name → ID.
    Returns fresh access_token + workspace_id to store in sessionStorage.
    """
    workspace_name = config.workspace_name.strip() or os.getenv("ALTERYX_WORKSPACE_NAME", "")
    if not workspace_name:
        logger.error("❌ Workspace name is required but not provided")
        raise HTTPException(status_code=400, detail="Workspace name is required.")

    try:
        logger.info(f"\n🔵 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🔵 VALIDATING ALTERYX AUTH")
        logger.info(f"   Workspace: {workspace_name}")
        logger.info(f"🔵 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        session = create_alteryx_session(
            access_token=config.access_token or "",
            refresh_token=config.refresh_token,
            workspace_name=workspace_name,
        )
        
        logger.info(f"✅ Auth validation successful!")
        logger.info(f"   Workspace ID : {session.workspace_id}")
        logger.info(f"   Custom URL   : {session.custom_url}")
        logger.info(f"✅ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
    except ValueError as e:
        logger.error(f"❌ Auth validation FAILED (ValueError): {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 401
        error_detail = e.response.text if e.response is not None else str(e)
        logger.error(f"❌ Auth validation FAILED (HTTP {status_code}): {error_detail}")
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Auth validation FAILED (Unexpected): {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    return AlteryxAuthResponse(
        status="authenticated",
        workspace_name=session.workspace_name,
        workspace_id=str(session.workspace_id),
        access_token=session.access_token,
        refresh_token=session.refresh_token,
    )


# ── Fetch workflows ───────────────────────────────────────────────────────────

@router.get("/workflows")
def get_alteryx_workflows(
    workspace_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    x_alteryx_refresh_token: Optional[str] = Header(None, alias="X-Alteryx-Refresh-Token"),
    response: Response = None,
):
    """
    Step 2: Called from AppsPage after successful auth.

    Uses the confirmed-working Alteryx Designer Cloud endpoint:
      GET https://us1.alteryxcloud.com/svc-workflow/api/v1/workflows

    Source: Alteryx Community engineer confirmation
    (community.alteryx.com/t5/Alteryx-IO-Discussions/...td-p/1297049)

    Headers required:
      Authorization: Bearer <access_token>
      X-Alteryx-Refresh-Token: <refresh_token>  (optional, enables auto-refresh)
    """
    workspace_id = workspace_id or os.getenv("ALTERYX_WORKSPACE_ID", "")

    logger.info(f"\n🔵 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"🔵 FETCHING WORKFLOWS")
    logger.info(f"   Workspace ID: {workspace_id}")
    logger.info(f"🔵 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── Resolve access token ──────────────────────────────────────────────────
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ", 1)[1]
        logger.info("   Access token from Authorization header")
    else:
        access_token = os.getenv("ALTERYX_ACCESS_TOKEN", "")
        logger.info("   Access token from environment")

    # ── Resolve refresh token ─────────────────────────────────────────────────
    refresh_token = x_alteryx_refresh_token or os.getenv("ALTERYX_REFRESH_TOKEN")
    
    if refresh_token:
        logger.info("   Refresh token available")
    else:
        logger.warning("   ⚠️  No refresh token available (auto-refresh disabled)")

    if not access_token and not refresh_token:
        logger.error("❌ No credentials: neither access token nor refresh token found")
        raise HTTPException(
            status_code=401,
            detail="No access token. Pass Authorization: Bearer <token> header.",
        )

    # ── Build session ─────────────────────────────────────────────────────────
    session = AlteryxSession(
        access_token=access_token,
        refresh_token=refresh_token,
        workspace_id=workspace_id,
    )

    # ── Fetch workflows using correct endpoint ────────────────────────────────
    logger.info("   Fetching from svc-workflow endpoint...")
    try:
        raw_workflows = list_alteryx_workflows(session, workspace_id=workspace_id)
        logger.info(f"   ✅ Retrieved raw workflows count: {len(raw_workflows)}")
    except ValueError as e:
        logger.error(f"❌ Workflow fetch FAILED (ValueError): {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 500
        error_detail = e.response.text if e.response is not None else str(e)
        logger.error(f"❌ Workflow fetch FAILED (HTTP {code}): {error_detail}")
        raise HTTPException(status_code=code, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Workflow fetch FAILED (Unexpected): {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    # ── Normalise workflow fields ─────────────────────────────────────────────
    # svc-workflow returns varying field names — handle all known variants
    workflows = []
    for wf in raw_workflows:
        wf_id = (
            wf.get("id")
            or wf.get("workflowId")
            or wf.get("flowId")
        )
        if not wf_id:
            continue

        workflow = AlteryxWorkflow(
            id=str(wf_id),
            name=(
                wf.get("name")
                or wf.get("workflowName")
                or wf.get("packageName")
                or wf.get("fileName")
                or "Unnamed Workflow"
            ),
            lastModifiedDate=(
                wf.get("updatedAt")
                or wf.get("dateModified")
                or wf.get("lastModifiedDate")
                or wf.get("updated")
                or wf.get("createdAt")
                or wf.get("dateCreated")
            ),
            runCount=wf.get("runCount") or wf.get("runs"),
            credentialType=wf.get("credentialType"),
            workerTag=wf.get("workerTag") or wf.get("tag"),
            description=wf.get("description") or wf.get("comments"),
            ownerId=wf.get("ownerId") or wf.get("owner"),
            isPublic=wf.get("isPublic") or wf.get("public"),
        )
        workflows.append(workflow)

    logger.info(f"   📊 Normalized {len(workflows)} workflow(s)")
    logger.info(f"✅ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # ── Propagate rotated refresh token to frontend ───────────────────────────
    if (
        response is not None
        and session.refresh_token
        and session.refresh_token != refresh_token
    ):
        logger.info("   Updating refresh token in response header")
        response.headers["X-Alteryx-Refresh-Token"] = session.refresh_token

    return {
        "workspace_id": workspace_id,
        "total": len(workflows),
        "workflows": [wf.dict() for wf in workflows],
    }


# ── Debug: dump raw response from svc-workflow ───────────────────────────────

@router.get("/debug/raw-workflows")
def debug_raw_workflows(
    authorization: Optional[str] = Header(None),
):
    """
    Debug endpoint — returns the raw JSON from svc-workflow so you can
    inspect the exact field names returned for your account.
    Hit: GET /api/alteryx/debug/raw-workflows
    with Authorization: Bearer <your_token>
    """
    logger.info("\n🔵 DEBUG: Raw workflow endpoint called")
    
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ", 1)[1]
        logger.info("   Access token from Authorization header")
    else:
        access_token = os.getenv("ALTERYX_ACCESS_TOKEN", "")
        logger.info("   Access token from environment")

    if not access_token:
        logger.error("❌ No access token provided")
        return {"error": "No access token"}

    session = AlteryxSession(
        access_token=access_token,
        refresh_token=os.getenv("ALTERYX_REFRESH_TOKEN"),
    )

    try:
        logger.info("   Fetching raw workflows...")
        raw = list_alteryx_workflows(session)
        logger.info(f"   ✅ Retrieved {len(raw)} workflows")
        logger.info(f"   Field names: {list(raw[0].keys()) if raw else []}")
        
        return {
            "count": len(raw),
            "raw_sample": raw[:3],   # first 3 items so you can see field names
            "all_field_names": list(raw[0].keys()) if raw else [],
        }
    except Exception as e:
        logger.error(f"❌ DEBUG endpoint FAILED: {str(e)}")
        return {"error": str(e)}


@router.get("/diagnostics/tokens")
def token_diagnostics():
    """
    📊 TOKEN DIAGNOSTICS ENDPOINT
    Provides detailed information about token status and validity.
    
    Helps diagnose:
    - Token availability from different sources
    - Token expiry status
    - Token persistence state
    - Recommended actions
    """
    logger.info("🔍 Running token diagnostics...")
    
    try:
        access_env = os.getenv("ALTERYX_ACCESS_TOKEN", "")
        refresh_env = os.getenv("ALTERYX_REFRESH_TOKEN", "")
        
        # Get tokens from storage
        stored = TokenManager._load_tokens_from_storage()
        access_stored = stored.get("access_token", "")
        refresh_stored = stored.get("refresh_token", "")
        
        # Check expiry
        access_expired = TokenManager._is_token_expired(access_env)
        refresh_valid = TokenManager.validate_refresh_token(refresh_env) if refresh_env else False
        
        return {
            "status": "diagnostics_complete",
            "tokens": {
                "access_token": {
                    "in_env": bool(access_env),
                    "in_storage": bool(access_stored),
                    "expired": access_expired,
                    "expiry_details": "Expires in ~5 minutes (Alteryx server limit)"
                },
                "refresh_token": {
                    "in_env": bool(refresh_env),
                    "in_storage": bool(refresh_stored),
                    "valid": refresh_valid,
                    "validity_period": "365 days (Alteryx server limit)"
                }
            },
            "persistent_storage": {
                "enabled": True,
                "location": ".../app/token_storage.json",
                "has_data": bool(stored),
                "last_update": stored.get("timestamp") if stored else None
            },
            "recommendations": TokenManager._get_recommendations(
                access_env, refresh_env, access_expired, refresh_valid
            ),
            "next_steps": [
                "1. Use GET /api/alteryx/test-connection to verify refresh token",
                "2. If refresh fails, generate new tokens from Alteryx Cloud",
                "3. Update .env with new ALTERYX_REFRESH_TOKEN",
                "4. Run test-connection again to validate"
            ]
        }
        
    except Exception as e:
        logger.error(f"Diagnostics error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "action": "Check backend logs for details"
        }


@router.post("/reset-tokens")
def reset_token_storage():
    """
    🔄 RESET ENDPOINT
    Clears persistent token storage and forces reloading from .env.
    Use this after manually updating tokens in .env file.
    """
    logger.info("🔄 Resetting token storage...")
    try:
        TokenManager.clear_storage()
        return {
            "status": "success",
            "message": "Token storage cleared",
            "details": "Will reload tokens from .env on next request",
            "next_step": "Call test-connection to verify new tokens"
        }
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
