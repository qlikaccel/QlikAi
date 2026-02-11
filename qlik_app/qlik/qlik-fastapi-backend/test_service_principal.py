#!/usr/bin/env python3
"""
Test service principal (client credentials) token acquisition
"""
from powerbi_auth import get_auth_manager

auth = get_auth_manager()
print('✅ Auth manager initialized')

result = auth.acquire_token_by_device_code()
success = result.get('success')
print(f'Success: {success}')

if success:
    print('✅ TOKEN ACQUIRED!')
    print(f'   Message: {result.get("message")}')
    print(f'   Expires in: {result.get("expires_in")} seconds')
else:
    error = result.get('error', 'Unknown')
    print(f'❌ Error: {error}')
