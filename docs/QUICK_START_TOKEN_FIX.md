# ⚡ QUICK ACTION GUIDE - Get Alteryx Connected Again

## **Your Situation**
✅ Token Manager implemented (DONE)
❌ Your refresh token is invalid/expired (NEEDS FIX)

---

## **Get It Working in 5 Minutes**

### **1️⃣ Get New Refresh Token (2 min)**

```
Open: https://us1.alteryxcloud.com
Login: accelerators@sorim.ai / @1tr3yx123
Click: Settings (gear icon) → API Keys
Click: Generate New Key
Copy: The "Refresh Token" value (starts with eyJ...)
```

### **2️⃣ Update .env File (1 min)**

Open: `d:\Alteryx_Update\QlikAi\qlik_app\qlik\qlik-fastapi-backend\.env`

Find this line:
```
ALTERYX_REFRESH_TOKEN=eyJhbGciOiJSUzI1NiIsImtpZCI6ImRlZmF1bHQifQ...
```

Replace with your NEW token:
```
ALTERYX_REFRESH_TOKEN=<paste_your_new_token_here>
```

Save file.

### **3️⃣ Reset Token Storage (1 min)**

```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/alteryx/reset-tokens" `
  -Method POST -UseBasicParsing
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

Expected response:
```json
{
  "status": "success",
  "message": "Token storage cleared",
  "next_step": "Call test-connection to verify new tokens"
}
```

### **4️⃣ Test Connection (1 min)**

```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/alteryx/test-connection" `
  -Method POST -UseBasicParsing
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

Expected response:
```json
{
  "status": "success",
  "message": "Alteryx connection verified",
  "tests": {
    "refresh_token_valid": true,
    "access_token_obtained": true,
    "session_created": true,
    "ready_to_fetch_workflows": true
  }
}
```

✅ **If you see this, you're done!** Connection is working!

---

## **Verify Everything Works**

### **Check Token Status**
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/alteryx/diagnostics/tokens" `
  -Method GET -UseBasicParsing
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

Should show:
```json
{
  "status": "diagnostics_complete",
  "tokens": {
    "refresh_token": {
      "valid": true  // ← This is the key one!
    }
  },
  "recommendations": [
    "✅ Refresh token is valid and functional"
  ]
}
```

### **Fetch Your Workflows**
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/alteryx/workflows?workspace_id=01KNS7RVQS14ZM22MY51EZRGKJ" `
  -Method GET -UseBasicParsing
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

Should show your workflows (5 in your case).

---

## **Troubleshooting**

### **If test-connection returns 401 "INVALID_REFRESH_TOKEN"**
```
❌ Problem: Refresh token is still invalid
✅ Solution: 
   1. Go back to Alteryx Cloud
   2. Make sure you copied the full token
   3. Check for extra spaces at start/end
   4. Try generating a fresh token again
```

### **If test-connection returns timeout**
```
❌ Problem: Network issue or slow Alteryx server
✅ Solution:
   1. Wait 30 seconds
   2. Try again
   3. Check your internet connection
```

### **If workflows endpoint returns 404**
```
❌ Problem: Workspace ID not found or wrong
✅ Solution:
   1. Check workspace_id is correct
   2. Verify your account has access to that workspace
   3. Use GET /diagnostics/tokens for more info
```

---

## **What Changed in Your System**

### **Before (Had Issues)**
```
.env → Load token at startup
     → Make API call
     → Token expires after 5 min
     → Try to refresh
     → Refresh fails (retry once)
     → Error ❌
     → Restart needed to reload from .env
```

### **After (Now Works)**
```
.env → Load token at startup
     → Make API call
     → Token expires after 5 min
     → Auto-refresh (try 3 times with backoff)
     → Get new token
     → Save to token_storage.json 💾
     → Continue working ✅
     → No restart needed!
```

---

## **Key Improvements**

| Feature | Before | After |
|---------|--------|-------|
| Token persistence | ❌ Lost on restart | ✅ Saved to disk |
| Retry logic | ❌ Single try | ✅ 3 tries with backoff |
| Thread safety | ❌ Race conditions | ✅ Protected with locks |
| Error messages | ❌ Generic errors | ✅ Actionable guidance |
| Diagnostics | ❌ None | ✅ Full token status |

---

## **You're All Set!**

Once you complete these 4 steps, your Alteryx integration will:
- ✅ Automatically refresh tokens every 5 minutes
- ✅ Persist tokens across restarts
- ✅ Handle concurrent requests safely
- ✅ Provide detailed error messages
- ✅ Work for 365 days without manual intervention*

*Then generate new tokens and update .env

---

## **Need Help?**

Reference files:
- `docs/TOKEN_MANAGEMENT_GUIDE.md` - Detailed guide
- `docs/TOKEN_FIX_IMPLEMENTATION_SUMMARY.md` - What was fixed
- `app/utils/token_manager.py` - Token logic
- Backend logs - Real-time operations

