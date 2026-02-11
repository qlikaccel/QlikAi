#!/usr/bin/env python3
"""
Test the complete Power BI integration with sample CSV data
"""

import requests
import json
import time
from io import BytesIO

# Backend URL
BACKEND_URL = "http://localhost:8000/powerbi/process"

# Sample CSV data (Sales data)
sample_csv = """Date,Product,Quantity,Amount,Region
2024-01-01,Laptop,5,5000,North
2024-01-01,Mouse,15,450,South
2024-01-02,Keyboard,8,800,East
2024-01-02,Monitor,3,1500,West
2024-01-03,Laptop,2,2000,North
2024-01-03,Mouse,20,600,South
2024-01-04,Keyboard,12,1200,East
2024-01-04,Monitor,4,2000,West
2024-01-05,Laptop,7,7000,North
2024-01-05,Mouse,25,750,South
2024-01-06,Keyboard,10,1000,East
2024-01-06,Monitor,5,2500,West
2024-01-07,Laptop,3,3000,North
2024-01-07,Mouse,18,540,South
2024-01-08,Keyboard,9,900,East
2024-01-08,Monitor,2,1000,West
2024-01-09,Laptop,6,6000,North
2024-01-09,Mouse,22,660,South
2024-01-10,Keyboard,11,1100,East
2024-01-10,Monitor,3,1500,West"""

# Sample DAX (optional, can be empty)
sample_dax = """// Sales Analysis DAX
CALCULATE(
    SUM('Sales'[Amount]),
    'Sales'[Region] = "North"
)

// Monthly Revenue
EVALUATE
VAR MonthStart = DATE(2024,1,1)
RETURN
ADDCOLUMNS(
    ALL('Calendar'[Month]),
    "Total Revenue", CALCULATE(SUM('Sales'[Amount]))
)"""

print("=" * 70)
print("🧪 Testing Power BI Integration with Sample Data")
print("=" * 70)

try:
    # Prepare multipart form data
    files = {
        "csv_file": ("sample_sales.csv", sample_csv, "text/plain"),
        "dax_file": ("sample.dax", sample_dax, "text/plain"),
        "meta_app_name": (None, "Qlik Sample App"),
        "meta_table": (None, "Sales"),
    }
    
    print("\n📤 Sending request to backend...")
    print(f"   URL: {BACKEND_URL}")
    print(f"   CSV rows: {len(sample_csv.splitlines()) - 1}")
    print(f"   DAX lines: {len(sample_dax.splitlines())}")
    
    response = requests.post(BACKEND_URL, files=files, timeout=30)
    
    print(f"\n📡 Response Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ SUCCESS!")
        print("\n📊 Dataset Created:")
        
        if "dataset" in data:
            dataset = data["dataset"]
            print(f"   Name: {dataset.get('name', 'N/A')}")
            print(f"   ID: {dataset.get('id', 'N/A')}")
            print(f"   Workspace ID: {dataset.get('workspace_id', 'N/A')}")
            
            if "urls" in dataset:
                urls = dataset["urls"]
                print(f"\n🔗 Links:")
                if "dataset" in urls:
                    print(f"   Dataset: {urls['dataset']}")
                if "report" in urls:
                    print(f"   Report: {urls['report']}")
        
        print("\n🚀 Next Steps:")
        print("   1. Open the Power BI workspace in your browser")
        print("   2. You should see the new dataset there")
        print("   3. Create a report from this dataset")
        print(f"\n📱 Power BI Workspace URL:")
        print(f"   https://app.powerbi.com/groups/7219790d-ee43-4137-b293-e3c477a754f0/datasets")
        
    else:
        print(f"\n❌ Error: {response.status_code}")
        print("Response:")
        print(response.text[:500])
        
except requests.exceptions.ConnectionError:
    print("\n❌ Cannot connect to backend at", BACKEND_URL)
    print("Make sure the backend is running:")
    print("   python -m uvicorn main:app --port 8000 --reload")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
