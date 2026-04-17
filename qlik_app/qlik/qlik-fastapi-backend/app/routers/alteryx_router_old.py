# qlikAI-backend/app/routers/alteryx_router.py

import logging
import os
import requests
from fastapi import APIRouter, HTTPException, Header, Response
from typing import Optional
from pydantic import BaseModel

from app.utils.alteryx_workspace_utils import (
    AlteryxSession,
    create_alteryx_session,
    _get_with_refresh,
    ALTERYX_BASE_URL,
)

router = APIRouter(prefix="/api/alteryx", tags=["Alteryx"])
logger = logging.getLogger(__name__)


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


# ── Validate auth ─────────────────────────────────────────────────────────────

@router.post("/validate-auth", response_model=AlteryxAuthResponse)
def validate_alteryx_auth(config: AlteryxAuthRequest):
    """
    Validates Alteryx credentials and resolves workspace name → ID.

    Token priority:
      1. access_token from request body
      2. ALTERYX_ACCESS_TOKEN from .env
    Works with ACCESS_TOKEN + REFRESH_TOKEN (no CLIENT_SECRET needed)
    """
    workspace_name = config.workspace_name.strip() or os.getenv("ALTERYX_WORKSPACE_NAME", "")
    if not workspace_name:
        raise HTTPException(
            status_code=400, 
            detail="Workspace name is required."
        )

    try:
        print(f"\n🔵 Validating Alteryx auth for workspace: {workspace_name}")
        session = create_alteryx_session(
            access_token=config.access_token or "",
            refresh_token=config.refresh_token,
            workspace_name=workspace_name,
        )
        print(f"✅ Auth validation successful!")
    except ValueError as e:
        error_msg = str(e)
        print(f"❌ Validation error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except requests.HTTPError as e:
        error_msg = str(e)
        status_code = e.response.status_code if e.response is not None else 401
        print(f"❌ HTTP {status_code}: {error_msg}")
        raise HTTPException(status_code=status_code, detail=error_msg)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

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
    workspace_name: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    x_alteryx_refresh_token: Optional[str] = Header(None, alias="X-Alteryx-Refresh-Token"),
    response: Response = None,
):
    """
    Fetch all workflows for a workspace.

    Token priority:
      1. Authorization: Bearer <token> header
      2. ALTERYX_ACCESS_TOKEN from .env
    Works with ACCESS_TOKEN + REFRESH_TOKEN (no CLIENT_SECRET needed)
    
    Endpoint discovery:
      - Tries custom workspace domain first (/api/v1/workflows on custom URL)
      - Falls back to main domain endpoints
      - Iterates through Designer Cloud API patterns
    """
    # Resolve workspace_id (from param or .env)
    workspace_id = workspace_id or os.getenv("ALTERYX_WORKSPACE_ID", "")
    workspace_name = workspace_name or os.getenv("ALTERYX_WORKSPACE_NAME", "")
    
    if not workspace_id and not workspace_name:
        raise HTTPException(status_code=400, detail="Missing workspace_id or workspace_name parameter.")

    # Resolve access token
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ", 1)[1]
    else:
        access_token = os.getenv("ALTERYX_ACCESS_TOKEN", "")

    # Resolve refresh token
    refresh_token = x_alteryx_refresh_token or os.getenv("ALTERYX_REFRESH_TOKEN")

    if not access_token and not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="No access token available. Set ALTERYX_ACCESS_TOKEN in .env or pass Authorization header.",
        )

    # Create session
    session = AlteryxSession(
        access_token=access_token,
        refresh_token=refresh_token,
    )

    # If workspace_name provided, resolve it to get custom_url
    custom_url = None
    if workspace_name:
        try:
            from app.utils.alteryx_workspace_utils import get_workspace_id_by_name
            get_workspace_id_by_name(session, workspace_name)
            custom_url = session.custom_url
            workspace_id = session.workspace_id
            print(f"✅ Resolved workspace '{workspace_name}' → ID {workspace_id}, custom_url: {custom_url}")
        except Exception as e:
            print(f"⚠️  Could not resolve workspace name: {e}")

    # Build endpoint candidates - prioritize custom workspace domain
    endpoint_candidates = []
    
    # First priority: Custom workspace domain (Designer Cloud)
    if custom_url:
        endpoint_candidates.extend([
            (f"https://{custom_url}/api/v1/workflows", {}),
            (f"https://{custom_url}/api/workflows", {}),
            (f"https://{custom_url}/workflows", {}),
        ])
    
    # Second priority: Main domain Designer Cloud API
    endpoint_candidates.extend([
        (f"{ALTERYX_BASE_URL}/api/v1/workflows", {}),
        (f"{ALTERYX_BASE_URL}/designer/api/v1/workflows", {}),
        (f"{ALTERYX_BASE_URL}/designer/v1/workflows", {}),
        (f"{ALTERYX_BASE_URL}/api/designer/workflows", {}),
    ])
    
    # Third priority: Workspace-specific endpoints on main domain
    if workspace_id:
        endpoint_candidates.extend([
            (f"{ALTERYX_BASE_URL}/v4/workspaces/{workspace_id}/workflows", {}),
            (f"{ALTERYX_BASE_URL}/api/v1/workspaces/{workspace_id}/workflows", {}),
            (f"{ALTERYX_BASE_URL}/api/workspaces/{workspace_id}/workflows", {}),
        ])
    
    # Fourth priority: Generic workflow endpoints
    endpoint_candidates.extend([
        (f"{ALTERYX_BASE_URL}/api/v2/workflows", {}),
        (f"{ALTERYX_BASE_URL}/v1/workflows", {}),
        (f"{ALTERYX_BASE_URL}/workflows", {}),
    ])

    data = None
    last_error = None

    print(f"\n🔵 Fetching workflows | workspace_id: {workspace_id} | custom_url: {custom_url}")
    for endpoint, params in endpoint_candidates:
        print(f"  Trying: {endpoint}")
        try:
            data = _get_with_refresh(endpoint, session, params=params)
            print(f"  ✅ Success! Workflows endpoint found: {endpoint}")
            break
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 500
            last_error = (code, str(e))
            if code in {401, 403, 404}:
                print(f"  ⚠️  {code} - endpoint not available, trying next...")
                continue
            else:
                print(f"  ⚠️  {code} - {e}")
                continue
        except ValueError as e:
            last_error = (500, str(e))
            print(f"  ⚠️  Invalid response format, trying next...")
            continue

    if data is None:
        code, detail = last_error or (500, "Unable to fetch workflows.")
        error_msg = (
            f"❌ Failed to fetch workflows. No compatible endpoint found. "
            f"Tried {len(endpoint_candidates)} endpoints."
        )
        print(f"\n{error_msg}")
        raise HTTPException(
            status_code=code or 500,
            detail=error_msg,
        )

    # Normalise response shape (list OR {"data": [...]} OR {"workflows": [...]})
    if isinstance(data, list):
        raw_workflows = data
    else:
        # Try multiple common response structures
        raw_workflows = (
            data.get("workflows") or 
            data.get("data") or 
            data.get("items") or 
            data.get("results") or
            []
        )

    print(f"  📊 Found {len(raw_workflows)} workflow(s)")

    workflows = []
    for wf in raw_workflows:
        if not wf.get("id"):
            continue
        
        # Handle multiple field name variations
        workflow = AlteryxWorkflow(
            id=str(wf.get("id", "")),
            name=wf.get("name") or wf.get("packageName") or "Unnamed Workflow",
            lastModifiedDate=(
                wf.get("dateModified") or 
                wf.get("lastModifiedDate") or 
                wf.get("updated") or
                wf.get("dateCreated")
            ),
            runCount=wf.get("runCount") or wf.get("runs"),
            credentialType=wf.get("credentialType"),
            workerTag=wf.get("workerTag") or wf.get("tag"),
        )
        workflows.append(workflow)

    # Send rotated refresh token back to frontend if it changed
    if response is not None and session.refresh_token and session.refresh_token != refresh_token:
        response.headers["X-Alteryx-Refresh-Token"] = session.refresh_token

    return {
        "workspace_id": workspace_id,
        "total": len(workflows),
        "workflows": [wf.dict() for wf in workflows],
    }


# ── Debug: Test workflow endpoints ─────────────────────────────────────────────

@router.get("/debug/test-endpoints")
def debug_test_endpoints(
    workspace_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """
    Debug endpoint to test different workflow API endpoints.
    Helps identify which endpoint works for your Alteryx Cloud instance.
    """
    workspace_id = workspace_id or os.getenv("ALTERYX_WORKSPACE_ID", "")
    if not workspace_id:
        return {"error": "Missing workspace_id parameter"}

    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ", 1)[1]
    else:
        access_token = os.getenv("ALTERYX_ACCESS_TOKEN", "")

    if not access_token:
        return {"error": "No access token available"}

    session = AlteryxSession(
        access_token=access_token,
        refresh_token=os.getenv("ALTERYX_REFRESH_TOKEN"),
    )

    test_endpoints = [
        f"{ALTERYX_BASE_URL}/v4/workspaces/{workspace_id}/workflows",
        f"{ALTERYX_BASE_URL}/v3/workspaces/{workspace_id}/workflows",
        f"{ALTERYX_BASE_URL}/api/v4/workspaces/{workspace_id}/workflows",
        f"{ALTERYX_BASE_URL}/api/workspaces/{workspace_id}/workflows",
        f"{ALTERYX_BASE_URL}/v4/workflows",
        f"{ALTERYX_BASE_URL}/api/workflows",
        f"{ALTERYX_BASE_URL}/designer/api/workflows/list",
        f"{ALTERYX_BASE_URL}/designer/api/v1/workflows",
        f"{ALTERYX_BASE_URL}/api/v1/workflows",
        f"{ALTERYX_BASE_URL}/workflows",
    ]

    results = []
    for endpoint in test_endpoints:
        try:
            resp = requests.get(
                endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                params={"limit": 5} if "/workflows" in endpoint else {"workspaceId": workspace_id},
                timeout=10,
            )
            
            result = {
                "endpoint": endpoint,
                "status": resp.status_code,
                "success": resp.status_code == 200,
            }
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    result["response_type"] = type(data).__name__
                    result["keys"] = list(data.keys()) if isinstance(data, dict) else "array"
                    result["count"] = len(data) if isinstance(data, list) else len(data.get("data", data.get("workflows", [])))
                except:
                    result["response"] = "Non-JSON response"
            else:
                result["error"] = resp.text[:200]
            
            results.append(result)
        except Exception as e:
            results.append({
                "endpoint": endpoint,
                "status": "error",
                "error": str(e),
            })

    successful = [r for r in results if r.get("success")]
    return {
        "workspace_id": workspace_id,
        "total_tested": len(test_endpoints),
        "successful": len(successful),
        "endpoints": results,
    }
