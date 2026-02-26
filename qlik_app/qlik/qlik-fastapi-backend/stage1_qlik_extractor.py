"""
STAGE 1: Qlik Cloud API - Extract Metadata

Extracts:
- Tables
- Fields with data types
- Key flags
- Associations
"""

import requests
import logging
from typing import Dict, List, Any, Optional
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from backend folder explicitly so stage-1 works regardless of import order
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_PATH)


class QlikMetadataExtractor:
    """Extract metadata from Qlik Cloud via REST API"""
    
    def __init__(self, api_key: Optional[str] = None, tenant: Optional[str] = None):
        # Accept either explicit key, QLIK_API_KEY, or legacy API_KEY
        self.api_key = (api_key or os.getenv("QLIK_API_KEY") or os.getenv("API_KEY") or "").strip()

        # Resolve tenant from multiple env styles:
        # - QLIK_TENANT_URL=https://xxx.qlikcloud.com
        # - QLIK_TENANT=xxx
        tenant_source = (
            tenant
            or os.getenv("QLIK_TENANT_URL")
            or os.getenv("QLIK_TENANT")
            or ""
        ).strip()

        if tenant_source.startswith("http://") or tenant_source.startswith("https://"):
            parsed = urlparse(tenant_source)
            tenant_host = parsed.netloc
        elif "." in tenant_source:
            tenant_host = tenant_source
        elif tenant_source:
            tenant_host = f"{tenant_source}.qlikcloud.com"
        else:
            tenant_host = ""

        self.tenant = tenant_host
        self.base_url = (
            (os.getenv("QLIK_API_BASE_URL") or "").strip()
            or (f"https://{tenant_host}/api/v1" if tenant_host else "")
        )

        if not self.api_key:
            logger.warning("QLIK_API_KEY/API_KEY not configured. Stage 1 extraction may fail.")
        if not self.base_url:
            logger.warning("QLIK tenant URL not configured. Set QLIK_TENANT_URL or QLIK_API_BASE_URL.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.last_extraction_method = "unknown"
    
    def extract_metadata(self, app_id: str) -> Dict[str, Any]:
        """
        Extract complete metadata from Qlik app
        
        Returns:
        {
            "app_id": "app_123",
            "app_name": "Sales App",
            "tables": [
                {
                    "name": "Sales",
                    "fields": [
                        {"name": "OrderID", "type": "integer", "is_key": true},
                        {"name": "CustomerID", "type": "integer", "is_key": false}
                    ]
                }
            ]
        }
        """
        try:
            app_id = (app_id or "").strip()
            if not app_id:
                return {"success": False, "error": "App ID is required"}
            if not self.base_url or not self.api_key:
                return {
                    "success": False,
                    "error": "Qlik configuration missing: check QLIK_API_KEY and QLIK_TENANT_URL/QLIK_API_BASE_URL",
                }

            logger.info(f"[STAGE 1] Extracting metadata from Qlik app: {app_id}")
            
            # Get app info
            app_info = self._get_app_info(app_id)
            if not app_info:
                return {"success": False, "error": "App not found or inaccessible"}
            if app_info.get("__error__"):
                return {"success": False, "error": app_info.get("__error__")}
            
            # Get tables/sheets
            tables = self._extract_tables(app_id)
            if not tables:
                return {
                    "success": False,
                    "error": (
                        "No tables found in app metadata. "
                        "Verify app has loaded tables and API key has access."
                    ),
                    "app_id": app_id,
                    "app_name": app_info.get("name"),
                    "tables": [],
                }
            
            return {
                "success": True,
                "app_id": app_id,
                "app_name": app_info.get("name"),
                "tables": tables,
                "extraction_method": self.last_extraction_method
            }
            
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _get_app_info(self, app_id: str) -> Dict[str, Any]:
        """Get basic app information"""
        try:
            url = f"{self.base_url}/apps/{app_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            status_code = None
            response_text = ""
            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
                response_text = e.response.text[:400]

            detail = f"Failed to get app info for app_id={app_id}"
            if status_code:
                detail += f" (HTTP {status_code})"
            if response_text:
                detail += f": {response_text}"
            else:
                detail += f": {str(e)}"

            logger.error(detail)
            return {"__error__": detail}
    
    def _extract_tables(self, app_id: str) -> List[Dict[str, Any]]:
        """Extract tables and fields from app (WebSocket first, REST fallback)."""
        # Primary path: WebSocket model extraction (most reliable for real table metadata)
        ws_tables = self._extract_tables_via_websocket(app_id)
        if ws_tables:
            self.last_extraction_method = "Qlik WebSocket Engine API"
            return ws_tables

        # Fallback path: REST items metadata
        rest_tables = self._extract_tables_via_items(app_id)
        if rest_tables:
            self.last_extraction_method = "Qlik Cloud REST Items API"
            return rest_tables

        self.last_extraction_method = "none"
        return []

    def _extract_tables_via_websocket(self, app_id: str) -> List[Dict[str, Any]]:
        """Use existing websocket client to fetch real data model tables."""
        try:
            from qlik_websocket_client import QlikWebSocketClient

            ws_client = QlikWebSocketClient()
            result = ws_client.get_app_tables_simple(app_id)
            if not result.get("success", False):
                logger.warning(f"WebSocket extraction failed: {result.get('error')}")
                return []

            raw_tables = result.get("tables", []) or []
            normalized_tables: List[Dict[str, Any]] = []

            for t in raw_tables:
                table_name = t.get("name") or "Unknown"
                raw_fields = t.get("fields", []) or []
                fields: List[Dict[str, Any]] = []

                for f in raw_fields:
                    field_name = (f.get("name") or "").strip()
                    if not field_name:
                        continue
                    if f.get("is_system", False):
                        continue

                    fields.append({
                        "name": field_name,
                        "type": self._infer_field_type_from_tags(f.get("tags", [])),
                        "is_key": bool(f.get("is_key", False)),
                    })

                if fields:
                    normalized_tables.append({
                        "name": table_name,
                        "fields": fields,
                        "field_count": len(fields),
                        "no_of_rows": t.get("no_of_rows", 0),
                    })

            logger.info(f"[STAGE 1] WebSocket extracted {len(normalized_tables)} tables")
            return normalized_tables

        except Exception as e:
            logger.warning(f"WebSocket table extraction unavailable: {str(e)}")
            return []

    def _extract_tables_via_items(self, app_id: str) -> List[Dict[str, Any]]:
        """Fallback: extract tables from item definitions (may be limited)."""
        try:
            # Get all items (sheets, visualizations)
            url = f"{self.base_url}/items"
            params = {
                "filter": f'resourceType eq "app" and resourceId eq "{app_id}"',
                "limit": 100
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            items = response.json().get("data", [])
            
            tables = []
            for item in items:
                table_data = self._extract_table_from_item(item)
                if table_data:
                    tables.append(table_data)
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to extract tables via items API: {str(e)}")
            return []
    
    def _extract_table_from_item(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Extract table structure from item"""
        try:
            name = item.get("name", "Unknown")
            
            # Extract fields from item definition
            definition = item.get("definition", {})
            dimensions = definition.get("dimensions", [])
            measures = definition.get("measures", [])
            
            fields = []
            
            # Add dimensions
            for dim in dimensions:
                field = {
                    "name": dim.get("label") or dim.get("name", "Dimension"),
                    "type": "string",
                    "is_key": self._is_key_field(dim.get("name", ""))
                }
                fields.append(field)
            
            # Add measures
            for meas in measures:
                field = {
                    "name": meas.get("label") or meas.get("name", "Measure"),
                    "type": "decimal",
                    "is_key": False
                }
                fields.append(field)
            
            if fields:
                return {
                    "name": name,
                    "fields": fields,
                    "field_count": len(fields)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract table: {str(e)}")
            return None
    
    def _is_key_field(self, field_name: str) -> bool:
        """Detect if field is likely a primary key"""
        key_patterns = ["id", "key", "code", "number"]
        field_lower = field_name.lower()
        return any(pat in field_lower for pat in key_patterns)

    def _infer_field_type_from_tags(self, tags: List[str]) -> str:
        """Infer a coarse field type from Qlik field tags."""
        tag_text = " ".join(tags or []).lower()
        if "$numeric" in tag_text:
            return "decimal"
        if "$date" in tag_text or "$timestamp" in tag_text or "$time" in tag_text:
            return "date"
        if "$boolean" in tag_text:
            return "boolean"
        return "string"
