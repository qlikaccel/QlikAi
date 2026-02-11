#!/usr/bin/env python3
from powerbi_auth import get_auth_manager

auth = get_auth_manager()
result = auth.get_device_code()
success = result.get('success')
print(f'Success: {success}')

if success:
    user_code = result.get('user_code')
    device_code = result.get('device_code')
    message = result.get('message')
    print(f'✅ Device code generated successfully')
    print(f'   User code: {user_code}')
    print(f'   Device code length: {len(device_code)}')
    print(f'   Ready for frontend!')
else:
    error = result.get('error')
    print(f'❌ Error: {error}')
