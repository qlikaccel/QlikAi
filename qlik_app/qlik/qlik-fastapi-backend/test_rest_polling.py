#!/usr/bin/env python3
"""
Test REST-based device code flow polling
This bypasses MSAL and uses direct Azure AD REST calls
"""
import requests
import time
import json

CLIENT_ID = "6413a69e-b951-4d7f-9c8e-af5f040ca3ea"
TENANT_ID = "e912ee28-32ed-4aed-9332-e5d3c6cea258"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

SCOPES = [
    "https://analysis.windows.net/powerbi/api/Dataset.ReadWrite.All",
    "https://analysis.windows.net/powerbi/api/Workspace.ReadWrite.All",
    "https://analysis.windows.net/powerbi/api/Report.ReadWrite.All"
]

from msal import PublicClientApplication

def test_rest_polling():
    """Test REST-based device code flow"""
    
    print("\n" + "="*70)
    print("REST-BASED DEVICE CODE FLOW TEST")
    print("="*70 + "\n")
    
    # Step 1: Initiate device code flow
    print("1️⃣  Initiating device code...")
    
    app = PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY
    )
    
    flow = app.initiate_device_flow(scopes=SCOPES)
    
    if "error" in flow:
        print(f"❌ Failed: {flow['error']}")
        return False
    
    device_code = flow.get("device_code")
    user_code = flow.get("user_code")
    interval = flow.get("interval", 1)
    
    print(f"✅ Device code received")
    print(f"   User code: {user_code}")
    print(f"   Device code length: {len(device_code)}")
    print(f"   Polling interval: {interval}s\n")
    
    # Step 2: REST polling
    print("2️⃣  Using REST to poll for token...")
    print(f"   ⚠️  Please authenticate at: {flow.get('verification_uri')}")
    print(f"   ⚠️  You have 3 minutes...\n")
    
    token_url = f"{AUTHORITY}/oauth2/v2.0/token"
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < 180:  # 3 minute timeout
        attempt += 1
        elapsed = int(time.time() - start_time)
        
        try:
            # Direct REST call
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "scope": " ".join(SCOPES)
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            result = response.json()
            
            if response.status_code == 200:
                if "access_token" in result:
                    print(f"✅ TOKEN ACQUIRED!")
                    print(f"   Elapsed: {elapsed}s")
                    print(f"   Attempt: {attempt}")
                    print(f"   Token expires in: {result.get('expires_in')} seconds")
                    print("\n" + "="*70)
                    print("✅ REST-BASED POLLING WORKS!")
                    print("="*70 + "\n")
                    return True
            
            elif response.status_code == 400:
                error = result.get("error", "")
                error_desc = result.get("error_description", "")
                
                if error == "authorization_pending":
                    if attempt % 3 == 0:
                        print(f"  ⏳ Attempt {attempt}: Waiting... ({elapsed}s)")
                    time.sleep(interval)
                    continue
                
                elif error == "expired_token":
                    print(f"❌ Device code expired")
                    return False
                
                elif error == "access_denied":
                    print(f"❌ User declined authentication")
                    return False
                
                else:
                    print(f"⚠️  Error: {error} - {error_desc}")
                    time.sleep(interval)
                    continue
            
            else:
                print(f"❌ Unexpected status {response.status_code}: {result}")
                time.sleep(interval)
                continue
        
        except Exception as e:
            print(f"❌ Request error: {e}")
            time.sleep(interval)
            continue
    
    print(f"❌ Timeout after {180/60:.0f} minutes")
    return False

if __name__ == "__main__":
    success = test_rest_polling()
    
    print("\n" + "="*70)
    if success:
        print("✅ REST polling is working correctly")
        print("The AADSTS7000218 error should be fixed!")
    else:
        print("⚠️  REST polling test failed")
        print("This indicates an issue with device code grant setup in Azure AD")
    print("="*70 + "\n")
