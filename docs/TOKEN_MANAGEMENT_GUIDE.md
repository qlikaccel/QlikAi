# 🔐 Alteryx Token Management Guide

## **Understanding Token Expiry**

### **Token Types & Lifespans**

| Token Type | Lifespan | Configurable? | Notes |
|-----------|----------|---------------|-------|
| **Access Token** | ~5 minutes ⏱️ | ❌ No - Alteryx Server Set | Short-lived, used for API calls |
| **Refresh Token** | ~365 days 📅 | ❌ No - Alteryx Server Set | Long-lived, stored securely |

**⚠️ IMPORTANT:** You **CANNOT** configure token expiry times. These are set by Alteryx servers and are non-negotiable.

---

## **How Token Refresh Works**

```
┌─ Request to API ─┐
│                  ├─→ Is access token valid?
│                  │
│                  ├─→ NO (expired or missing)
│                  │   ├─→ Use refresh_token to get new access_token
│                  │   ├─→ Save new access_token to persistent storage
│                  │   └─→ Proceed with API call
│                  │
│                  └─→ YES (still valid)
│                      └─→ Use existing access_token
│                          
└──────────────────┘
```

### **Token Persistence Architecture**

```
┌─────────────────────────────────────────────┐
│  Request → Alteryx API                      │
└─────────┬───────────────────────────────────┘
          │
          ├─ Check: Is access_token valid?
          │
          ├─→ NO: Refresh using refresh_token
          │       ├─ Call Ping Identity service
          │       ├─ Get new access_token
          │       ├─ Save to token_storage.json ← PERSISTENT
          │       └─ Retry API call with fresh token
          │
          └─→ YES: Use existing token
                   └─ Proceed with API call
```

**Key Improvement:** Refreshed tokens are now **saved to disk** (`token_storage.json`), so they persist across app restarts!

---

## **Token Management Endpoints**

### **1️⃣ Health Check**
```bash
GET /api/alteryx/health
```
**Purpose:** Verify credentials are loaded
**Status Codes:**
- `200 OK` - Credentials present
- `401 Unauthorized` - No credentials found

---

### **2️⃣ Test Connection** ⭐ USE THIS TO DIAGNOSE ISSUES
```bash
POST /api/alteryx/test-connection
```
**Purpose:** Validate refresh token and test token refresh capability

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Alteryx connection verified",
  "tests": {
    "refresh_token_valid": true,
    "access_token_obtained": true,
    "session_created": true,
    "ready_to_fetch_workflows": true
  },
  "token_info": {
    "access_token_valid_for": "~5 minutes (Alteryx server limit)",
    "refresh_token_valid_for": "~365 days (Alteryx server limit)",
    "refresh_token_rotated": true
  }
}
```

**Failure Response (401):**
```json
{
  "error": "INVALID_REFRESH_TOKEN",
  "message": "Your refresh token is no longer valid",
  "possible_causes": [
    "Token has expired (after 365 days)",
    "Token was revoked in Alteryx Cloud",
    "Token permissions were changed"
  ],
  "action": "Generate a new token: Alteryx Cloud → Settings → API Keys"
}
```

---

### **3️⃣ Token Diagnostics** 🔍
```bash
GET /api/alteryx/diagnostics/tokens
```
**Purpose:** Get detailed token status and recommendations

**Response:**
```json
{
  "status": "diagnostics_complete",
  "tokens": {
    "access_token": {
      "in_env": true,
      "in_storage": true,
      "expired": false,
      "expiry_details": "Expires in ~5 minutes"
    },
    "refresh_token": {
      "in_env": true,
      "in_storage": true,
      "valid": true,
      "validity_period": "365 days"
    }
  },
  "persistent_storage": {
    "enabled": true,
    "location": ".../app/token_storage.json",
    "has_data": true,
    "last_update": 1776417070.123
  },
  "recommendations": [
    "✅ Refresh token is valid and functional",
    "✅ Access token is valid"
  ]
}
```

---

### **4️⃣ Reset Token Storage**
```bash
POST /api/alteryx/reset-tokens
```
**Purpose:** Clear persistent token storage and force reload from .env

**Use Cases:**
- After manually updating tokens in .env
- When token_storage.json becomes corrupted
- Fresh start after credential update

---

## **Common Issues & Solutions**

### **Issue 1: "Refresh token does not exist" (400 Bad Request)**

**Cause:** Your refresh token is invalid/revoked

**Solution:**
```bash
# 1. Get new token from Alteryx Cloud
# → https://us1.alteryxcloud.com
# → Settings → API Keys → Generate New Key
# → Copy the Refresh Token (starts with eyJ...)

# 2. Update .env
ALTERYX_REFRESH_TOKEN=<paste_new_refresh_token_here>

# 3. Reset storage and test
POST /api/alteryx/reset-tokens
POST /api/alteryx/test-connection
```

---

### **Issue 2: Token Expires After 365 Days**

**Cause:** Refresh token has natural expiry limit set by Alteryx

**Solution:** Generate new tokens annually or before they expire:
```bash
# 1. Go to Alteryx Cloud → Settings → API Keys
# 2. Generate a new API Key (creates new refresh token)
# 3. Update .env with new token
# 4. Test with POST /api/alteryx/test-connection
```

---

### **Issue 3: Multiple Requests Failing Simultaneously**

**Cause:** Token refresh race condition (fixed in new version!)

**Solution:** Already handled by TokenManager with:
- Thread-safe token refresh (using locks)
- Exponential backoff retry logic
- Persistent token storage

---

## **Token Storage Details**

### **Location**
```
qlik-fastapi-backend/app/token_storage.json
```

### **Contents**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "timestamp": 1776417070.123,
  "access_token_exp": 1776417370,
  "refresh_token_exp": 1808953070
}
```

### **Automatic Management**
- ✅ Created automatically on first token refresh
- ✅ Updated after every successful refresh
- ✅ Contains expiry metadata for diagnostics
- ✅ Can be manually cleared with `/reset-tokens` endpoint

---

## **Recommended Workflow**

### **Initial Setup**

```bash
# 1. Generate tokens from Alteryx Cloud
curl -X POST https://us1.alteryxcloud.com/api/tokens/generate

# 2. Update .env with REFRESH token
ALTERYX_REFRESH_TOKEN=eyJ...

# 3. Test connection
curl -X POST http://localhost:8000/api/alteryx/test-connection
# ✅ Should return 200 OK with "success"

# 4. Fetch workflows
curl -X GET "http://localhost:8000/api/alteryx/workflows?workspace_id=..."
# ✅ Should return list of workflows
```

### **Token Refresh (Automatic)**

The application now handles this automatically:
1. Before each API call, checks if access token is valid
2. If expired, uses refresh token to get new one
3. Saves new token to persistent storage
4. Proceeds with API call

**You don't need to do anything!** ✨

### **Annual Renewal**

```bash
# Before token expires (every ~360 days):

# 1. Generate new tokens from Alteryx Cloud
# 2. Update ALTERYX_REFRESH_TOKEN in .env
# 3. Reset storage
POST /api/alteryx/reset-tokens

# 4. Verify new token works
POST /api/alteryx/test-connection
```

---

## **API Endpoints Summary**

| Endpoint | Method | Purpose | Returns |
|----------|--------|---------|---------|
| `/health` | GET | Check credentials loaded | Status + credential info |
| `/test-connection` | POST | Validate refresh token | Success or detailed error |
| `/diagnostics/tokens` | GET | Token status report | Detailed diagnostics |
| `/reset-tokens` | POST | Clear token storage | Success message |
| `/workflows` | GET | Fetch workflows | List of workflows |
| `/debug/raw-workflows` | GET | Raw API response | Unmodified JSON from Alteryx |

---

## **Troubleshooting Decision Tree**

```
Start: "Is your Alteryx integration working?"
├─ NO
│  ├─ Step 1: GET /api/alteryx/health
│  │  ├─ 401? → Add ALTERYX_REFRESH_TOKEN to .env
│  │  ├─ 200? → Go to Step 2
│  │
│  ├─ Step 2: POST /api/alteryx/test-connection
│  │  ├─ 400 (invalid_grant)? → Refresh token expired/revoked
│  │  │  └─ Solution: Generate new token from Alteryx Cloud
│  │  │
│  │  ├─ 400 (other)? → Check network & .env formatting
│  │  │
│  │  ├─ 200? → Go to Step 3
│  │
│  ├─ Step 3: GET /api/alteryx/workflows?workspace_id=...
│  │  ├─ 404? → Wrong workspace ID or token lacks permissions
│  │  ├─ 200? → ✅ SUCCESS!
│  │
│
├─ YES
│  └─ ✅ System is working correctly!
```

---

## **Key Features of New Token Manager**

✅ **Persistent Storage**
- Tokens saved to disk survive app restart
- Metadata tracks token expiry

✅ **Thread-Safe Refresh**
- Prevents race conditions in concurrent requests
- Uses locks to serialize token refresh

✅ **Retry Logic**
- Exponential backoff for temporary failures
- 3 retry attempts by default

✅ **Intelligent Validation**
- Distinguishes between invalid token vs network error
- Provides actionable error messages

✅ **Auto Token Rotation**
- Detects when Alteryx rotates refresh tokens
- Automatically saves new rotation

✅ **Comprehensive Logging**
- Tracks all token operations
- Helps diagnose issues quickly

---

## **Questions?**

- **Token expired?** → Generate new one from Alteryx Cloud
- **Getting 400 error?** → Check test-connection endpoint
- **Need diagnostics?** → Call /diagnostics/tokens endpoint
- **Unsure about workflow?** → Review this guide's sections above

