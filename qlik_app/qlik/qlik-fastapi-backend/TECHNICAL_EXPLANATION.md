# 🔬 TECHNICAL DEEP DIVE: Why AADSTS7000218 and How REST Fixed It

## The AADSTS7000218 Error

**Full Error Message:**
```
AADSTS7000218: The request body must contain the following parameter: 'client_assertion' or 'client_secret'
```

**When It Occurs:**
Azure AD receives a token request that looks like it's from a **Confidential Client** (like a web service) but doesn't include client credentials.

---

## Why MSAL Failed

### What MSAL's `acquire_token_by_device_flow()` Does

```python
# WHAT MSAL WAS DOING (BROKEN):
token = self.app.acquire_token_by_device_flow(flow)
```

**Behind the scenes, MSAL:**

1. Takes the device code
2. Prepares a token request
3. **Adds headers/params identifying it as an app client** (the bug)
4. Sends to Azure AD

**Problem:** Even though the app is registered as **Public Client**, MSAL's method was formatting the request as if it needed confidential client credentials.

---

## The REST Fix

### What We Now Do (FIXED):

```python
# WHAT WE DO NOW (FIXED):
response = requests.post(
    f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
    data={
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",  # Device code grant
        "client_id": CLIENT_ID,                                         # App ID only
        "device_code": device_code,                                     # Code from device flow
        "scope": " ".join(SCOPES)                                       # What we're asking for
    },
    timeout=10
)
```

**Key differences:**

1. **Direct to Azure AD** - No MSAL intermediary
2. **Explicit grant type** - Tells Azure: "This is device code flow, not confidential client"
3. **Only client_id** - No client_secret or assertions
4. **Simple payload** - Minimal, standard OAuth2

---

## Azure AD Token Endpoint Request Flow

```
┌────────────────────────────────────────────────────────┐
│ Browser Tab 1: microsoft.com/devicelogin               │
│  User enters code and authenticates                     │
└────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│ Backend: powerbi_auth.py (polling loop)                │
│                                                        │
│  Loop every 1-2s:                                      │
│  1. POST to https://.../oauth2/v2.0/token             │
│  2. Include: grant_type, client_id, device_code       │
│  3. Wait for response                                  │
│  4. Handle: authorization_pending → retry             │
│  5. Handle: access_token received → success           │
└────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│ Azure AD Token Endpoint                                │
│                                                        │
│ Receives request with device_code grant type:         │
│ ✅ "This is public client device code flow"           │
│ ✅ No confidential client assertions expected         │
│ ✅ Validates device code status                       │
│ ✅ Returns access_token if user authenticated         │
└────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│ Frontend: MigrationPage.tsx                            │
│                                                        │
│ Status check detects: logged_in: true                 │
│ 1. Open Power BI: window.open(powerBIUrl)            │
│ 2. Close modal                                         │
│ 3. Create dataset in background                       │
└────────────────────────────────────────────────────────┘
```

---

## Polling Response Codes Explained

### Success Response (HTTP 200)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "https://analysis.windows.net/powerbi/api/..."
}
```
**Action:** ✅ Cache token and return success

### Pending Response (HTTP 400)
```json
{
  "error": "authorization_pending",
  "error_description": "Waiting for user to authenticate..."
}
```
**Action:** ⏳ Wait and retry (this is normal!)

### Token Expired (HTTP 400)
```json
{
  "error": "expired_token",
  "error_description": "Device code has expired"
}
```
**Action:** ❌ Stop polling, tell user to start over

### User Declined (HTTP 400)
```json
{
  "error": "access_denied",
  "error_description": "The user declined consent"
}
```
**Action:** ❌ Stop polling, show error

---

## Why This Works

| Aspect | MSAL Method | REST Method |
|--------|-------------|------------|
| **Sends client_assertion** | ❌ Yes (bug) | ✅ No |
| **Explicit device code grant** | ❌ Implicit | ✅ Explicit |
| **Handles pending properly** | ❌ Built-in issues | ✅ Simple parsing |
| **Public client compatible** | ❌ No | ✅ Yes |
| **Error handling clarity** | ❌ Mixes errors | ✅ Clear responses |

---

## Side Benefits of REST Approach

1. **No MSAL Dependency** - Direct OAuth2, no framework baggage
2. **Clearer Logging** - Can see exactly what's being sent/received
3. **Simple Polling** - Just a loop with POST requests
4. **Standard OAuth2** - Not MSAL-specific, works with any Azure AD app
5. **Better Error Messages** - Raw Azure AD responses, not MSAL-wrapped

---

## Code Walkthrough: Complete Polling Loop

```python
def acquire_token_by_device_code(self, max_wait_seconds: int = 900):
    """
    Poll Azure AD directly for token
    Bypasses MSAL's broken method
    """
    # 1. Get the device code we saved earlier
    if not self.current_flow:
        return {"success": False, "error": "No active flow"}
    
    flow = self.current_flow
    start_time = time.time()
    attempt = 0
    
    # 2. Extract polling parameters
    device_code = flow["device_code"]
    interval = flow.get("interval", 1)  # How often to check
    
    # 3. Poll loop (max 15 minutes)
    while time.time() - start_time < max_wait_seconds:
        attempt += 1
        elapsed = int(time.time() - start_time)
        
        # 4. Construct token request
        token_url = f"{AUTHORITY}/oauth2/v2.0/token"
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": CLIENT_ID,
            "device_code": device_code,
            "scope": " ".join(SCOPES)  # What we're asking for
        }
        
        # 5. Send request
        response = requests.post(token_url, data=data, timeout=10)
        result = response.json()
        
        # 6. Parse response
        if response.status_code == 200 and "access_token" in result:
            # SUCCESS! We got a token
            access_token = result["access_token"]
            expires_in = result.get("expires_in", 3600)
            self._save_token(access_token, expires_in)
            self.current_flow = None
            print(f"✅ Token acquired in {elapsed}s")
            return {"success": True}
        
        if response.status_code == 400:
            error = result.get("error", "")
            
            # STILL WAITING - User hasn't signed in yet
            if error == "authorization_pending":
                if attempt % 5 == 0:
                    print(f"⏳ Attempt {attempt}: Waiting...")
                time.sleep(interval)
                continue
            
            # EXPIRED - Device code timed out
            if error == "expired_token":
                return {"success": False, "error": "Device code expired"}
            
            # DENIED - User said no
            if error == "access_denied":
                return {"success": False, "error": "User declined"}
        
        # Unknown error - retry
        time.sleep(interval)
    
    # Timeout reached
    return {"success": False, "error": "Timeout"}
```

---

## Critical Scopes Configuration

The `scope` parameter must be **space-separated** (not comma-separated)

```python
# CORRECT (our fix):
"scope": " ".join([
    "https://analysis.windows.net/powerbi/api/Dataset.ReadWrite.All",
    "https://analysis.windows.net/powerbi/api/Workspace.ReadWrite.All",
    "https://analysis.windows.net/powerbi/api/Report.ReadWrite.All"
])
# Results in: "scope": "https://analysis.windows.net/powerbi/api/Dataset.ReadWrite.All https://analysis.windows.net/powerbi/api/Workspace.ReadWrite.All ..."

# WRONG (don't do this):
"scope": ", ".join([...])  # Comma-separated NOT accepted by Azure AD
```

---

## Testing This Locally

**Option 1: Direct REST call with curl**
```bash
curl -X POST "https://login.microsoftonline.com/e912ee28-32ed-4aed-9332-e5d3c6cea258/oauth2/v2.0/token" \
  -d "grant_type=urn:ietf:params:oauth:grant-type:device_code" \
  -d "client_id=6413a69e-b951-4d7f-9c8e-af5f040ca3ea" \
  -d "device_code=YOUR_DEVICE_CODE" \
  -d "scope=https://analysis.windows.net/powerbi/api/Dataset.ReadWrite.All"
```

**Option 2: Test script**
```bash
python test_rest_polling.py
```

---

## Summary

| Issue | Cause | Fix | Result |
|-------|-------|-----|--------|
| AADSTS7000218 | MSAL using confidential client format for public client | Use direct REST with proper device code grant | ✅ No more error |
| Cryptic error messages | MSAL wrapping errors | Direct Azure AD responses | ✅ Clear error handling |
| Unclear what's happening | Black box MSAL method | Direct HTTP POST we control | ✅ Visible polling |
| Power BI not opening | Frontend didn't detect auth completion | Add `window.open()` when status is true | ✅ Auto-opens |

---

**The fix is elegant because it's simple: Just talk directly to Azure AD token endpoint instead of using MSAL's broken abstraction.**

