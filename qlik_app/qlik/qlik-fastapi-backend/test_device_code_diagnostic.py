#!/usr/bin/env python3
"""
Diagnostic test for device code flow issues
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from msal import PublicClientApplication
import time

CLIENT_ID = "6413a69e-b951-4d7f-9c8e-af5f040ca3ea"
TENANT_ID = "e912ee28-32ed-4aed-9332-e5d3c6cea258"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

SCOPES = [
    "https://analysis.windows.net/powerbi/api/Dataset.ReadWrite.All",
    "https://analysis.windows.net/powerbi/api/Workspace.ReadWrite.All",
    "https://analysis.windows.net/powerbi/api/Report.ReadWrite.All"
]

def test_basic_device_flow():
    """Test basic device code initiation"""
    print("🧪 TEST 1: Device Code Initiation")
    print("-" * 60)
    
    try:
        app = PublicClientApplication(
            client_id=CLIENT_ID,
            authority=AUTHORITY
        )
        
        flow = app.initiate_device_flow(scopes=SCOPES)
        
        if "error" in flow:
            print(f"❌ Error: {flow.get('error_description', flow['error'])}")
            return False
        
        print(f"✅ Device code received successfully")
        print(f"   User code: {flow.get('user_code')}")
        print(f"   Device code length: {len(flow.get('device_code', ''))}")
        print(f"   Message: {flow.get('message')}")
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cached_token():
    """Test if cached token exists"""
    print("\n🧪 TEST 2: Cached Token Check")
    print("-" * 60)
    
    token_file = os.path.join(os.path.dirname(__file__), ".powerbi_token_cache.json")
    
    if os.path.exists(token_file):
        import json
        try:
            with open(token_file) as f:
                data = json.load(f)
            
            import time as time_module
            expires_at = data.get("expires_at", 0)
            if expires_at > time_module.time():
                print(f"✅ Valid cached token found")
                print(f"   Expires in: {int(expires_at - time_module.time())} seconds")
                return True
            else:
                print(f"⚠️  Cached token exists but is expired")
                return False
        except Exception as e:
            print(f"❌ Error reading token cache: {e}")
            return False
    else:
        print(f"⚠️  No cached token found (expected on first run)")
        return False

def test_msal_polling():
    """Test MSAL polling without waiting for user"""
    print("\n🧪 TEST 3: MSAL Polling (without user auth)")
    print("-" * 60)
    
    try:
        app = PublicClientApplication(
            client_id=CLIENT_ID,
            authority=AUTHORITY
        )
        
        flow = app.initiate_device_flow(scopes=SCOPES)
        
        if "error" in flow:
            print(f"❌ Cannot initiate flow: {flow['error']}")
            return False
        
        print(f"📱 Started polling (will timeout in 5 seconds)...")
        
        # Try once immediately (should fail with authorization_pending)
        token = app.acquire_token_by_device_flow(flow)
        
        if "error" in token:
            error = token.get("error", "unknown")
            if error == "authorization_pending":
                print(f"✅ Got expected 'authorization_pending' error")
                print(f"   (This is normal - user hasn't authenticated yet)")
                return True
            else:
                print(f"❌ Got error: {error}")
                print(f"   Description: {token.get('error_description', 'N/A')}")
                return False
        
        print(f"❓ Got token (unexpected): {token.get('access_token', '')[:20]}...")
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("DEVICE CODE FLOW DIAGNOSTICS")
    print("="*60 + "\n")
    
    results = {
        "basic_device_flow": test_basic_device_flow(),
        "cached_token": test_cached_token(),
        "msal_polling": test_msal_polling(),
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {test}")
    
    print("\n" + "="*60)
    if all(results.values()):
        print("✅ ALL TESTS PASSED - Device code flow is working")
        print("The AADSTS7000218 error suggests a timing or polling issue.")
        print("Make sure you authenticate QUICKLY after seeing the code.")
    else:
        print("❌ SOME TESTS FAILED")
        print("This suggests an issue with Azure AD client registration.")
        print("Verify the client_id is registered for device code flow.")
    print("="*60 + "\n")
