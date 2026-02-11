#!/usr/bin/env python3
"""
Test script to push sample CSV data to Power BI dataset.
This demonstrates the complete flow: login → create dataset → push data → open Power BI
"""

import os
import time
import json
import requests
import csv
import io
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8000"
POWERBI_WORKSPACE_URL = "https://app.powerbi.com/groups/7219790d-ee43-4137-b293-e3c477a754f0/datasets"

# Sample CSV data
SAMPLE_CSV = """ProductID,ProductName,Category,UnitPrice,UnitsInStock
1,Chai,Beverages,18.00,39
2,Chang,Beverages,19.00,17
3,Aniseed Syrup,Condiments,10.00,13
4,Chef Anton's Cajun Seasoning,Condiments,22.00,53
5,Chef Anton's Gumbo Mix,Condiments,21.35,0
6,Grandma's Boysenberry Spread,Condiments,25.00,120
7,Uncle Bob's Organic Dried Pears,Produce,30.00,15
8,Northwoods Cranberry Sauce,Condiments,40.00,6
9,Mishi Kobe Nori,Seafood,97.00,42
10,Ikura,Seafood,31.00,31"""

def log(msg: str, status: str = "ℹ"):
    """Pretty print log messages"""
    print(f"[{status}] {msg}")

def step(msg: str):
    """Print step header"""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def test_login_flow():
    """Test complete login and data push flow"""
    
    log("Starting Power BI test flow", "🚀")
    
    # Step 1: Initiate device code login
    step("Step 1: Initiate Device Code Login")
    try:
        response = requests.post(f"{BACKEND_URL}/powerbi/login/initiate")
        response.raise_for_status()
        login_data = response.json()
        
        if login_data["success"]:
            print(f"\n✓ Device code initiated successfully!")
            print(f"  Device Code: {login_data['device_code']}")
            print(f"  User Code: {login_data['user_code']}")
            print(f"  URL: {login_data['verification_uri']}")
            print(f"\n  Message: {login_data['message']}")
            print(f"  Expires in: {login_data['expires_in']} seconds")
            
            device_code = login_data["device_code"]
            user_code = login_data["user_code"]
            expires_in = login_data["expires_in"]
        else:
            log(f"Failed to initiate device code: {login_data}", "❌")
            return False
            
    except Exception as e:
        log(f"Error initiating login: {e}", "❌")
        return False
    
    # Step 2: Wait for user to complete login
    step("Step 2: Waiting for User to Complete Device Code Login")
    
    print(f"\n⏳ Waiting for you to:")
    print(f"   1. Open: {login_data['verification_uri']}")
    print(f"   2. Enter code: {user_code}")
    print(f"   3. Sign in with your Power BI account")
    print(f"\n⏳ Checking status every 5 seconds (timeout: {expires_in}s)...\n")
    
    start_time = time.time()
    check_interval = 5
    
    while time.time() - start_time < expires_in:
        # Check if logged in
        try:
            response = requests.post(f"{BACKEND_URL}/powerbi/login/status")
            status_data = response.json()
            
            if status_data.get("logged_in"):
                log("✓ User successfully authenticated!", "✓")
                print(f"  Message: {status_data.get('message', 'Logged in')}")
                return True
            else:
                remaining = expires_in - (time.time() - start_time)
                print(f"⏳ Still waiting... ({int(remaining)}s remaining)")
                time.sleep(check_interval)
        except Exception as e:
            remaining = expires_in - (time.time() - start_time)
            print(f"⏳ Still waiting... ({int(remaining)}s remaining)")
            time.sleep(check_interval)
    
    log("Device code login timeout - user did not complete authentication", "⚠")
    return False

def test_dataset_creation():
    """Test creating and pushing data to Power BI dataset"""
    
    # Step 3: Test Power BI connection
    step("Step 3: Verify Power BI Workspace Access")
    
    try:
        response = requests.post(f"{BACKEND_URL}/powerbi/login/test")
        response.raise_for_status()
        test_data = response.json()
        
        log(f"✓ Connection test successful!", "✓")
        print(f"  Workspace: {test_data.get('workspace_id')}")
        print(f"  Datasets found: {test_data.get('dataset_count', 0)}")
        
    except requests.exceptions.HTTPError as e:
        log(f"❌ Connection test failed: {e.response.json()}", "❌")
        return False
    except Exception as e:
        log(f"❌ Error testing connection: {e}", "❌")
        return False
    
    # Step 4: Create sample CSV temp file
    step("Step 4: Prepare Sample Data")
    
    csv_file = io.StringIO(SAMPLE_CSV)
    csv_lines = SAMPLE_CSV.strip().split('\n')
    log(f"✓ Sample CSV prepared with {len(csv_lines)-1} data rows", "✓")
    print(f"  Columns: {csv_lines[0]}")
    print(f"  Sample row: {csv_lines[1]}")
    
    # Step 5: Test dataset creation with sample data
    step("Step 5: Create Power BI Dataset with Sample Data")
    
    files = {
        'csv_file': ('sample_data.csv', SAMPLE_CSV, 'text/csv'),
    }
    data = {
        'dataset_name': 'Sample Products Dataset',
        'table_name': 'Products',
        'dax_query': ''  # Optional DAX
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/powerbi/process",
            files=files,
            data=data
        )
        response.raise_for_status()
        result = response.json()
        
        log(f"✓ Dataset created successfully!", "✓")
        print(f"  Workspace ID: {result.get('workspace_id')}")
        print(f"  Dataset ID: {result.get('dataset_id')}")
        print(f"  Dataset Name: {result.get('dataset_name')}")
        print(f"  Table Name: {result.get('table_name')}")
        print(f"  Rows pushed: {result.get('rows_pushed')}")
        
        # Step 6: Open Power BI
        step("Step 6: Open Power BI Workspace")
        
        print(f"\n✓ Your dataset has been created in Power BI!")
        print(f"\n  To view it, open:")
        print(f"  {POWERBI_WORKSPACE_URL}")
        print(f"\n  Or use this shortened URL:")
        print(f"  https://app.powerbi.com/")
        
        return True
        
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json().get('detail', str(e))
        log(f"❌ Failed to create dataset: {error_detail}", "❌")
        return False
    except Exception as e:
        log(f"❌ Error creating dataset: {e}", "❌")
        return False

def main():
    """Run complete test flow"""
    
    print("\n" + "="*60)
    print("  Power BI Integration Test Script")
    print("="*60)
    
    # Test login flow
    if not test_login_flow():
        log("Test aborted - login flow failed", "⚠")
        return
    
    # Test dataset creation
    if not test_dataset_creation():
        log("Test aborted - dataset creation failed", "⚠")
        return
    
    # Success
    print("\n" + "="*60)
    log("✓ All tests passed! Power BI integration working correctly", "✓")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
