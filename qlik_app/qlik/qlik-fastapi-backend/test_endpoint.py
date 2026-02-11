#!/usr/bin/env python3
"""
Test the /powerbi/login/initiate endpoint
"""
import requests
import time

# Start backend first (in background)
import subprocess
import os

print("Starting backend server...")
os.chdir(r'e:\qlikRender\QlikSense\qlik_app\qlik\qlik-fastapi-backend')

# Start uvicorn in background
process = subprocess.Popen(
    ['python', '-m', 'uvicorn', 'main:app', '--port', '8000'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

print("Waiting for server to start...")
time.sleep(4)

try:
    print("\nTesting POST /powerbi/login/initiate...")
    response = requests.post('http://localhost:8000/powerbi/login/initiate', timeout=5)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS!")
        print(f"   Device Code: {data.get('device_code')[:20]}...")
        print(f"   User Code: {data.get('user_code')}")
        print(f"   Message: {data.get('message')[:60]}...")
    else:
        print(f"❌ HTTP {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    print("\nStopping server...")
    process.terminate()
    process.wait(timeout=5)
    print("✅ Done")
