#!/usr/bin/env python3
"""
Complete test of device code flow + auto Power BI opening
This script simulates the full user journey
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from powerbi_auth import get_auth_manager
import json
import time

def simulate_full_flow():
    """Simulate complete authentication and dataset creation flow"""
    
    print("\n" + "="*70)
    print("FULL DEVICE CODE AUTHENTICATION + POWER BI FLOW TEST")
    print("="*70 + "\n")
    
    auth = get_auth_manager()
    
    # Step 1: Initiate device code
    print("1️⃣  INITIATING DEVICE CODE LOGIN")
    print("-" * 70)
    
    device_code_result = auth.get_device_code()
    
    if not device_code_result.get("success"):
        print(f"❌ Failed to get device code: {device_code_result.get('error')}")
        return False
    
    print(f"✅ Device code obtained successfully")
    print(f"   User code: {device_code_result.get('user_code')}")
    print(f"   Verification URL: {device_code_result.get('verification_uri')}")
    print(f"\n⚠️  MANUAL STEP REQUIRED:")
    print(f"   1. Open: {device_code_result.get('verification_uri')}")
    print(f"   2. Enter code: {device_code_result.get('user_code')}")
    print(f"   3. Sign in with your Microsoft account")
    print(f"   4. Return to this terminal (you have 15 minutes)")
    print(f"\n🕐 Waiting for your authentication...")
    
    # Step 2: Poll for token
    print("\n2️⃣  POLLING FOR TOKEN ACQUISITION")
    print("-" * 70)
    
    # Start polling
    timeout_at = time.time() + 900  # 15 minutes
    
    while time.time() < timeout_at:
        token_result = auth.acquire_token_by_device_code(max_wait_seconds=60)
        
        if token_result.get("success"):
            print(f"✅ TOKEN ACQUIRED SUCCESSFULLY!")
            print(f"   Message: {token_result.get('message')}")
            print(f"   Token expires in: {token_result.get('expires_in', 3600)} seconds")
            break
        elif "authorization_pending" not in token_result.get("error", ""):
            # Check if token was acquired on previous call
            if auth.is_token_valid():
                print(f"✅ TOKEN ALREADY VALID!")
                break
            else:
                print(f"❌ Authentication failed: {token_result.get('error')}")
                break
    
    if not auth.is_token_valid():
        print("\n❌ Token acquisition failed or timed out")
        return False
    
    # Step 3: Verify Power BI connection
    print("\n3️⃣  VERIFYING POWER BI CONNECTION")
    print("-" * 70)
    
    test_result = auth.test_connection()
    
    if test_result.get("success"):
        print(f"✅ Power BI connection verified!")
        print(f"   {test_result.get('message')}")
    else:
        print(f"❌ Power BI connection failed: {test_result.get('error')}")
        return False
    
    # Step 4: Show next steps
    print("\n4️⃣  NEXT STEPS (AUTO-EXECUTED IN REAL APP)")
    print("-" * 70)
    
    print("✅ Backend would now:")
    print("   1. Receive CSV/DAX files from frontend")
    print("   2. Create Power BI dataset")
    print("   3. Push data to the dataset")
    print("   4. Return dataset URL")
    print("\n✅ Frontend would now:")
    print("   1. Receive dataset URL from backend")
    print("   2. Open Power BI in new tab")
    print("   3. Display success message")
    
    print("\n" + "="*70)
    print("✅ DEVICE CODE FLOW SUCCESS!")
    print("="*70)
    print("\nToken is cached in: .powerbi_token_cache.json")
    print("Token will be reused for future requests without re-authentication")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    success = simulate_full_flow()
    sys.exit(0 if success else 1)
