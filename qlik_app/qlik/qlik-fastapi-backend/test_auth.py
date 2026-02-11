#!/usr/bin/env python3
"""
Test authentication script
"""

from powerbi_auth import get_auth_manager
import time

def test_auth():
    print("=== AUTHENTICATION DIAGNOSTIC ===")
    
    auth = get_auth_manager()
    
    print(f"Client ID: {auth.app.client_id[:20]}...")
    print(f"Has client secret: {bool(auth.client_secret)}")
    print(f"Token valid: {auth.is_token_valid()}")
    print(f"Access token: {auth.access_token[:50] + '...' if auth.access_token else 'None'}")
    print(f"Token expires at: {auth.token_expires_at}")
    print(f"Current time: {time.time()}")
    
    # Test authentication
    print("\n=== TESTING AUTHENTICATION ===")
    result = auth.acquire_token_by_device_code(max_wait_seconds=10)
    print(f"Authentication result: {result}")
    
    # Test connection
    print("\n=== TESTING CONNECTION ===")
    connection_result = auth.test_connection()
    print(f"Connection result: {connection_result}")

if __name__ == "__main__":
    test_auth()