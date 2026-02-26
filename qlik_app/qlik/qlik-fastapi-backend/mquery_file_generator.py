"""
M Query File Generator Module

Generates PowerBI M Query files in multiple formats:
- .pq (Power Query format)
- .txt (Text format for documentation)
- Combined .m format

Supports splitting LoadScript into individual table blocks for separate downloads.
"""

import logging
from typing import Dict, List, Any, Tuple
import json

logger = logging.getLogger(__name__)


class MQueryFileGenerator:
    """Generate M Query files in various formats"""
    
    def __init__(self, m_query: str, parsed_script: Dict[str, Any] = None):
        """Initialize file generator"""
        self.m_query = m_query
        self.parsed_script = parsed_script or {}
        self.tables = parsed_script.get('details', {}).get('tables', [])
    
    def generate_pq_content(self) -> str:
        """
        Generate .pq format (Power Query format)
        This is compatible with Power Query import
        """
        logger.info("Generating .pq format file...")
        
        content = f"""// Power BI Query - Converted from Qlik LoadScript
// Generated automatically for Power Query Editor

{self.m_query}"""
        
        logger.info(f"✅ Generated .pq content ({len(content)} characters)")
        return content
    
    def generate_txt_content(self) -> str:
        """
        Generate .txt format (Documentation format)
        Contains M Query with metadata and instructions
        """
        logger.info("Generating .txt format file...")
        
        # Build metadata section
        metadata = "=" * 80 + "\n"
        metadata += "POWER BI M QUERY - DOCUMENTATION\n"
        metadata += "=" * 80 + "\n\n"
        
        # Add script summary
        if self.parsed_script:
            summary = self.parsed_script.get('summary', {})
            metadata += "SCRIPT SUMMARY:\n"
            metadata += f"  Tables: {summary.get('tables_count', 'N/A')}\n"
            metadata += f"  Fields: {summary.get('fields_count', 'N/A')}\n"
            metadata += f"  Data Connections: {summary.get('connections_count', 'N/A')}\n"
            metadata += f"  Transformations: {summary.get('transformations_count', 'N/A')}\n\n"
        
        # Add usage instructions
        metadata += "USAGE INSTRUCTIONS:\n"
        metadata += "1. Open Power BI Desktop\n"
        metadata += "2. Go to Home tab > Get Data > Other > Web (or paste directly in Editor)\n"
        metadata += "3. Paste the M Query code below into the Advanced Editor\n"
        metadata += "4. Adjust data source connections as needed\n"
        metadata += "5. Click 'Load' to import data\n\n"
        
        metadata += "=" * 80 + "\n"
        metadata += "M QUERY CODE:\n"
        metadata += "=" * 80 + "\n\n"
        
        content = metadata + self.m_query
        logger.info(f"✅ Generated .txt content ({len(content)} characters)")
        return content
    
    def generate_m_content(self) -> str:
        """
        Generate standard .m format
        Same as M query but potentially with additional wrapper
        """
        logger.info("Generating .m format file...")
        content = self.m_query
        logger.info(f"✅ Generated .m content ({len(content)} characters)")
        return content
    
    def split_tables(self) -> Dict[str, str]:
        """
        Split M Query and LoadScript into individual table queries
        Returns: {table_name: "M Query for this table"}
        """
        logger.info(f"Splitting into {len(self.tables)} individual tables...")
        
        table_queries = {}
        
        for table in self.tables:
            table_name = table.get('name', 'Unknown')
            table_alias = table.get('alias', table_name)
            
            # Create individual M query for this table
            individual_query = f"""let
    // Table: {table_name}
    // Alias: {table_alias}
    Source = [Data Source for {table_name}],
    #"Transformed Data" = Source,
    Result = #"Transformed Data"
in
    Result"""
            
            table_queries[table_name] = individual_query
            logger.info(f"  ✓ Created query for table: {table_name}")
        
        logger.info(f"✅ Split into {len(table_queries)} table queries")
        return table_queries
    
    def get_file_downloads(self) -> Dict[str, Dict[str, str]]:
        """
        Get all available file formats for download
        
        Returns: {
            'pq': {'filename': 'query.pq', 'content': '...'},
            'txt': {'filename': 'query.txt', 'content': '...'},
            'm': {'filename': 'query.m', 'content': '...'}
        }
        """
        logger.info("Generating all file formats for download...")
        
        files = {
            'pq': {
                'filename': 'powerbi_query.pq',
                'content': self.generate_pq_content(),
                'mime_type': 'text/plain'
            },
            'txt': {
                'filename': 'powerbi_query_documentation.txt',
                'content': self.generate_txt_content(),
                'mime_type': 'text/plain'
            },
            'm': {
                'filename': 'powerbi_query.m',
                'content': self.generate_m_content(),
                'mime_type': 'text/plain'
            }
        }
        
        logger.info(f"✅ Generated {len(files)} file formats")
        return files


def generate_dual_download_zip(m_query: str, parsed_script: Dict[str, Any] = None) -> bytes:
    """
    Generate a ZIP file containing .pq, .txt, and .m files
    
    Returns: ZIP file content as bytes
    """
    import io
    import zipfile
    
    logger.info("Creating dual-file ZIP package...")
    
    generator = MQueryFileGenerator(m_query, parsed_script)
    files = generator.get_file_downloads()
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_key, file_data in files.items():
            if file_key in ['pq', 'txt', 'm']:  # Include .pq, .txt, and .m in zip
                zip_file.writestr(
                    file_data['filename'],
                    file_data['content']
                )
                logger.info(f"  ✓ Added {file_key} file to ZIP: {file_data['filename']}")
    
    zip_buffer.seek(0)
    logger.info(f"✅ Created ZIP file ({len(zip_buffer.getvalue())} bytes) with .pq, .txt, and .m")
    return zip_buffer.getvalue()
