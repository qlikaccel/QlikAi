#!/usr/bin/env python3
"""
Test script for device code authentication flow
"""
import requests
import time
import threading
import json

BASE_URL = "http://localhost:8000"

def test_device_code_flow():
    """Test the complete device code authentication flow"""
    
    print("=" * 60)
    print("DEVICE CODE AUTHENTICATION FLOW TEST")
    print("=" * 60)
    
    # Step 1: Initiate login
    print("\n1️⃣  Initiating device code login...")
    try:
        res = requests.post(f"{BASE_URL}/powerbi/login/initiate")
        res.raise_for_status()
        init_data = res.json()
        print(f"✅ Status: {res.status_code}")
        print(f"📱 Device code received:")
        print(f"   User Code: {init_data.get('user_code')}")
        print(f"   Message: {init_data.get('message')}")
        print(f"   Verification URI: {init_data.get('verification_uri')}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Step 2: Start token acquisition (background)
    print("\n2️⃣  Starting token acquisition (background)...")
    try:
        res = requests.post(f"{BASE_URL}/powerbi/login/acquire-token", json={})
        res.raise_for_status()
        acq_data = res.json()
        print(f"✅ Status: {res.status_code}")
        print(f"📢 Message: {acq_data.get('message')}")
        print(f"   Logged in: {acq_data.get('logged_in')}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Step 3: Check login status (simulating frontend checks)
    print("\n3️⃣  Checking login status (every 3 seconds)...")
    print("⚠️  Wait for user to scan code and authenticate at:")
    print(f"   {init_data.get('verification_uri')}")
    print(f"   and enter code: {init_data.get('user_code')}")
    print("\nThis will timeout in 3 minutes if user doesn't authenticate...")
    
    max_checks = 60  # 3 minutes with 3-second intervals
    check_count = 0
    authenticated = False
    
    for i in range(max_checks):
        time.sleep(3)
        check_count += 1
        
        try:
            res = requests.post(f"{BASE_URL}/powerbi/login/status")
            res.raise_for_status()
            status_data = res.json()
            
            if status_data.get('logged_in'):
                print(f"\n✅ Check #{check_count}: USER AUTHENTICATED!")
                print(f"   Message: {status_data.get('message')}")
                authenticated = True
                break
            else:
                if check_count % 5 == 0:  # Print every 5 checks (15 seconds)
                    print(f"   Check #{check_count}: Waiting for authentication...")
        except Exception as e:
            print(f"   Check #{check_count}: Error - {e}")
    
    if not authenticated:
        print("\n❌ Authentication timeout - user did not sign in")
        return False
    
    # Step 4: Test Power BI connection
    print("\n4️⃣  Testing Power BI connection...")
    try:
        res = requests.post(f"{BASE_URL}/powerbi/login/test")
        res.raise_for_status()
        test_data = res.json()
        print(f"✅ Status: {res.status_code}")
        print(f"📊 Test result: {test_data.get('message')}")
    except Exception as e:
        print(f"⚠️  Warning: {e}")
    
    print("\n" + "=" * 60)
    print("✅ DEVICE CODE FLOW TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("Starting test in 3 seconds... Make sure backend is running on port 8000")
    time.sleep(3)
    test_device_code_flow()
