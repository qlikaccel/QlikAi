#!/usr/bin/env python3
"""
Simple test - Create a fresh Power BI dataset with minimal data
"""

import requests

# Simple CSV with basic columns
csv_data = """Name,Value,Status
Product A,100,Active
Product B,200,Inactive
Product C,150,Active"""

print("=" * 60)
print("🧪 Starting Fresh Power BI Test")
print("=" * 60)

try:
    # Create multipart request
    files = {
        "csv_file": ("products.csv", csv_data, "text/plain"),
        "meta_app_name": (None, "Test App"),
        "meta_table": (None, "Products"),
    }
    
    print("\n📤 Sending dataset to Power BI...")
    
    response = requests.post(
        "http://localhost:8000/powerbi/process",
        files=files,
        timeout=30
    )
    
    print(f"✅ Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        dataset_id = data.get("dataset", {}).get("id")
        print(f"\n✅ SUCCESS! Dataset created:")
        print(f"   ID: {dataset_id}")
        print(f"\n🔗 Access at:")
        print(f"   https://app.powerbi.com/groups/7219790d-ee43-4137-b293-e3c477a754f0/datasets/{dataset_id}")
    else:
        print(f"\n❌ Error: {response.text[:300]}")
        
except Exception as e:
    print(f"❌ {e}")

print("=" * 60)
