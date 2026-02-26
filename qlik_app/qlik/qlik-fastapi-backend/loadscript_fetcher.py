"""
Qlik LoadScript Fetcher Module

Fetches loadscript from Qlik Cloud with detailed logging at each phase.
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from datetime import datetime
from qlik_websocket_client import QlikWebSocketClient

load_dotenv()

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class LoadScriptFetcher:
    """Fetch loadscript from Qlik Cloud applications"""
    
    def __init__(self, api_key: Optional[str] = None, tenant_url: Optional[str] = None):
        """Initialize fetcher with Qlik Cloud credentials"""
        logger.info("=" * 80)
        logger.info("PHASE 0: Initializing LoadScript Fetcher")
        logger.info("=" * 80)
        
        self.api_key = api_key or os.getenv('QLIK_API_KEY')
        self.tenant_url = tenant_url or os.getenv('QLIK_TENANT_URL')
        self.api_base_url = os.getenv('QLIK_API_BASE_URL')
        
        if not self.api_base_url and self.tenant_url:
            self.api_base_url = f"{self.tenant_url}/api/v1"
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if not self.api_key:
            logger.error("❌ QLIK_API_KEY is not set in environment variables")
            raise ValueError('QLIK_API_KEY is not set in environment variables')
        if not self.api_base_url:
            logger.error("❌ QLIK_API_BASE_URL or QLIK_TENANT_URL is not set")
            raise ValueError('QLIK_API_BASE_URL or QLIK_TENANT_URL is not set in environment variables')
        
        logger.info(f"✅ Initialized with Tenant URL: {self.tenant_url}")
        logger.info(f"✅ API Base URL: {self.api_base_url}")

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Qlik Cloud"""
        logger.info("=" * 80)
        logger.info("PHASE 1: Testing Connection to Qlik Cloud")
        logger.info("=" * 80)
        
        url = f'{self.api_base_url}/users/me'
        logger.info(f"🔌 Testing connection to: {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            logger.info(f"📊 Response Status Code: {response.status_code}")
            response.raise_for_status()
            
            user_data = response.json()
            logger.info(f"✅ Connection successful!")
            logger.info(f"✅ User ID: {user_data.get('id', 'N/A')}")
            logger.info(f"✅ User Name: {user_data.get('name', 'N/A')}")
            
            return {"status": "success", "data": user_data}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Connection test failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_applications(self) -> Dict[str, Any]:
        """Fetch list of all applications from Qlik Cloud"""
        logger.info("=" * 80)
        logger.info("PHASE 2: Fetching Applications List from Qlik Cloud")
        logger.info("=" * 80)
        
        url = f'{self.api_base_url}/apps'
        logger.info(f"🔍 Fetching apps from: {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            logger.info(f"📊 Response Status Code: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list):
                apps = data
            elif isinstance(data, dict) and 'data' in data:
                apps = data['data']
            elif isinstance(data, dict) and 'items' in data:
                apps = data['items']
            else:
                apps = [data] if data else []
            
            logger.info(f"✅ Successfully fetched {len(apps)} application(s)")
            for i, app in enumerate(apps, 1):
                app_name = app.get('name', 'N/A')
                app_id = app.get('id', 'N/A')
                logger.info(f"   ✓ App {i}: {app_name} (ID: {app_id[:8]}...)")
            
            return {
                "status": "success",
                "count": len(apps),
                "data": apps
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error fetching applications: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "data": []
            }

    def get_application_details(self, app_id: str) -> Dict[str, Any]:
        """Get details of a specific application"""
        logger.info("=" * 80)
        logger.info("PHASE 3: Fetching Application Details")
        logger.info("=" * 80)
        
        url = f'{self.api_base_url}/apps/{app_id}'
        logger.info(f"🔍 Fetching app details from: {url}")
        logger.info(f"📋 App ID: {app_id}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            logger.info(f"📊 Response Status Code: {response.status_code}")
            response.raise_for_status()
            
            app_data = response.json()
            logger.info(f"✅ App Name: {app_data.get('name', 'N/A')}")
            logger.info(f"✅ App Description: {app_data.get('description', 'N/A')}")
            logger.info(f"✅ App Owner: {app_data.get('owner', {}).get('name', 'N/A')}")
            logger.info(f"✅ Last Reload: {app_data.get('lastReloadTime', 'N/A')}")
            
            return {
                "status": "success",
                "data": app_data
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error fetching application details: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    def fetch_loadscript(self, app_id: str) -> Dict[str, Any]:
        """
        Fetch the loadscript from a Qlik application
        First tries WebSocket (real script), then falls back to REST API
        """
        logger.info("=" * 80)
        logger.info("PHASE 4: FETCHING LOADSCRIPT FROM QLIK CLOUD")
        logger.info("=" * 80)
        
        logger.info(f"📋 Target App ID: {app_id}")
        logger.info(f"⏰ Fetch Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Try Method 1: WebSocket (Most reliable for actual script)
        logger.info("📍 Step 4.1: Attempting to fetch via WebSocket (Engine API)...")
        try:
            logger.info("   Initializing WebSocket client...")
            ws_client = QlikWebSocketClient()
            logger.info("   Calling _get_app_script_websocket method...")
            script_result = ws_client._get_app_script_websocket(app_id)
            
            logger.info(f"   WebSocket result: success={script_result.get('success')}, has_script={bool(script_result.get('script'))}")
            
            if script_result and script_result.get("success") and script_result.get("script"):
                loadscript = script_result.get("script", "")
                logger.info(f"✅ Successfully fetched real loadscript via WebSocket!")
                logger.info(f"📏 Script length: {len(loadscript)} characters")
                logger.info(f"📊 Found {len(script_result.get('tables', []))} table(s) in script")
                
                return {
                    "status": "success",
                    "app_id": app_id,
                    "app_name": script_result.get("app_name", "Unknown"),
                    "loadscript": loadscript,
                    "method": "websocket_engine_api",
                    "timestamp": datetime.now().isoformat(),
                    "script_length": len(loadscript),
                    "tables": script_result.get("tables", []),
                    "message": "✅ Full loadscript fetched via WebSocket Engine API"
                }
            else:
                logger.warning(f"⚠️  WebSocket returned non-success: {script_result.get('error', 'No error message')}")
        except Exception as ws_error:
            logger.warning(f"⚠️  WebSocket method failed: {str(ws_error)}")
            import traceback
            logger.debug(f"   Traceback: {traceback.format_exc()}")
        
        # Try Method 2: REST API - Direct script endpoint
        logger.info("📍 Step 4.2: Attempting REST API direct script endpoint...")
        try:
            script_url = f'{self.api_base_url}/apps/{app_id}/script'
            logger.info(f"🔍 Trying: {script_url}")
            
            try:
                response = requests.get(script_url, headers=self.headers, timeout=15)
                logger.info(f"📊 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    script_data = response.json()
                    loadscript = script_data.get('script', '') or script_data.get('qScript', '')
                    
                    if loadscript:
                        logger.info(f"✅ Successfully fetched loadscript from REST API!")
                        logger.info(f"📏 Script length: {len(loadscript)} characters")
                        
                        return {
                            "status": "success",
                            "app_id": app_id,
                            "app_name": script_data.get('name', 'Unknown'),
                            "loadscript": loadscript,
                            "method": "rest_api_direct",
                            "timestamp": datetime.now().isoformat(),
                            "script_length": len(loadscript),
                            "message": "Loadscript fetched via REST API"
                        }
            except Exception as e:
                logger.warning(f"⚠️  REST API direct endpoint failed: {str(e)}")
        except Exception as e:
            logger.warning(f"⚠️  Error trying REST API: {str(e)}")
        
        # Try Method 3: Get app details and tables for reconstruction
        logger.info("📍 Step 4.3: Verifying app exists and gathering metadata...")
        try:
            app_url = f'{self.api_base_url}/apps/{app_id}'
            logger.info(f"🔍 Fetching from: {app_url}")
            
            app_response = requests.get(app_url, headers=self.headers, timeout=15)
            logger.info(f"📊 Response status: {app_response.status_code}")
            
            if app_response.status_code == 200:
                app_data = app_response.json()
                app_name = app_data.get('name', 'Unknown')
                logger.info(f"✅ App verified: {app_name}")
            else:
                app_data = {}
                app_name = 'Unknown'
        except Exception as e:
            logger.warning(f"⚠️  Could not verify app: {str(e)}")
            app_data = {}
            app_name = 'Unknown'
        
        # Step 4: Fetch connections
        logger.info("📍 Step 4.4: Fetching data connections...")
        connections = []
        try:
            conn_url = f'{self.api_base_url}/data-connections'
            conn_response = requests.get(conn_url, headers=self.headers, timeout=15)
            logger.info(f"📊 Connections response status: {conn_response.status_code}")
            
            if conn_response.status_code == 200:
                conn_data = conn_response.json()
                if isinstance(conn_data, list):
                    connections = conn_data
                elif isinstance(conn_data, dict) and 'value' in conn_data:
                    connections = conn_data.get('value', [])
                elif isinstance(conn_data, dict) and 'items' in conn_data:
                    connections = conn_data.get('items', [])
                
                logger.info(f"✅ Found {len(connections)} data connection(s)")
        except Exception as e:
            logger.warning(f"⚠️  Could not fetch connections: {str(e)}")
        
        # Step 5: Build reconstructed loadscript from all gathered info
        logger.info("📍 Step 4.5: Reconstructing loadscript from metadata...")
        
        script_snippet = f"// ==================================================\n"
        script_snippet += f"// Qlik Cloud Application LoadScript\n"
        script_snippet += f"// Application: {app_name}\n"
        script_snippet += f"// App ID: {app_id}\n"
        script_snippet += f"// Description: {app_data.get('description', 'N/A')}\n"
        script_snippet += f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        script_snippet += f"// Fetch Method: Metadata Reconstruction (no direct script access)\n"
        script_snippet += f"// ==================================================\n\n"
        
        if connections:
            script_snippet += f"// Data Connections ({len(connections)})\n"
            script_snippet += f"// ==================================================\n"
            for conn in connections:
                conn_name = conn.get('name', 'Unknown')
                conn_type = conn.get('connectionType', 'Unknown')
                script_snippet += f"// {conn_name} ({conn_type})\n"
            script_snippet += f"\n"
        
        script_snippet += f"// Sample Load Statements\n"
        script_snippet += f"// ==================================================\n"
        script_snippet += f"// LOAD [Field1], [Field2], [Field3]\n"
        script_snippet += f"// FROM [DataSource];\n"
        script_snippet += f"\n"
        script_snippet += f"// Note: Full loadscript not accessible\n"
        script_snippet += f"// This is metadata-reconstructed content\n"
        
        logger.info(f"✅ Loadscript reconstructed from metadata")
        logger.info(f"📏 Script length: {len(script_snippet)} characters")
        
        return {
            "status": "partial_success",
            "app_id": app_id,
            "app_name": app_name,
            "loadscript": script_snippet,
            "method": "metadata_reconstruction",
            "timestamp": datetime.now().isoformat(),
            "script_length": len(script_snippet),
            "connections_count": len(connections),
            "connections": connections[:5] if connections else [],
            "message": "⚠️ Loadscript partially available - WebSocket Engine API may require additional configuration"
        }


# Standalone testing
if __name__ == "__main__":
    try:
        fetcher = LoadScriptFetcher()
        
        # Test connection
        conn_result = fetcher.test_connection()
        if conn_result["status"] != "success":
            logger.error("Cannot proceed - connection failed")
            exit(1)
        
        # Get apps
        apps_result = fetcher.get_applications()
        if apps_result["status"] == "success" and apps_result["data"]:
            first_app_id = apps_result["data"][0]["id"]
            
            # Get app details
            details_result = fetcher.get_application_details(first_app_id)
            
            # Fetch loadscript
            script_result = fetcher.fetch_loadscript(first_app_id)
            logger.info(f"Final Result: {script_result}")
        else:
            logger.error("No applications found")
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
