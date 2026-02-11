#!/usr/bin/env python
from powerbi_service import PowerBIService
import requests

try:
    pbi = PowerBIService()
    print('Fetching available workspaces...\n')
    
    # List all groups (workspaces)
    url = 'https://api.powerbi.com/v1.0/myorg/groups'
    r = requests.get(url, headers=pbi._headers(), timeout=10)
    
    if r.status_code == 200:
        groups = r.json().get('value', [])
        print(f'✓ Found {len(groups)} workspaces:\n')
        for g in groups:
            name = g.get('name')
            wid = g.get('id')
            print(f'  Name: {name}')
            print(f'  ID:   {wid}')
            print()
        
        if not groups:
            print("⚠️ No workspaces found. Service principal may not have access to any workspace.")
    else:
        print(f'✗ Error listing workspaces: {r.status_code}')
        print(f'  Response: {r.text}')
        
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
