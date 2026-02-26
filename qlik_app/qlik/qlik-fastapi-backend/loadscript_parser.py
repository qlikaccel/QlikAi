"""
Qlik LoadScript Parser Module

Parses the loadscript and extracts meaningful components with detailed logging.
"""

import logging
import re
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class LoadScriptParser:
    """Parse Qlik loadscript and extract components"""
    
    def __init__(self, loadscript: str):
        """Initialize parser with loadscript"""
        logger.info("=" * 80)
        logger.info("PHASE 5: PARSING LOADSCRIPT")
        logger.info("=" * 80)
        
        self.loadscript = loadscript
        self.script_length = len(loadscript)
        
        logger.info(f"📊 Input Script Length: {self.script_length} characters")
        logger.info(f"⏰ Parse Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Initialize component storage
        self.tables = []
        self.fields = []
        self.data_connections = []
        self.transformations = []
        self.joins = []
        self.variables = []
        self.functions = []
        self.comments = []
        self.load_statements = []
        
        logger.info("✅ Parser initialized and ready to parse")

    def parse(self) -> Dict[str, Any]:
        """Main parsing function"""
        logger.info("📍 Starting comprehensive script analysis...")
        
        try:
            # Extract comments first
            logger.info("📍 Step 5.1: Extracting comments...")
            self._extract_comments()
            logger.info(f"✅ Found {len(self.comments)} comment block(s)")
            
            # Extract load statements
            logger.info("📍 Step 5.2: Extracting LOAD statements...")
            self._extract_load_statements()
            logger.info(f"✅ Found {len(self.load_statements)} LOAD statement(s)")
            
            # Extract table names
            logger.info("📍 Step 5.3: Extracting table names...")
            self._extract_tables()
            logger.info(f"✅ Found {len(self.tables)} table(s)")
            for table in self.tables:
                logger.info(f"   ✓ Table: {table.get('name', 'Unknown')}")
            
            # Extract field definitions
            logger.info("📍 Step 5.4: Extracting field definitions...")
            self._extract_fields()
            logger.info(f"✅ Found {len(self.fields)} field(s)")
            for field in self.fields[:5]:  # Show first 5
                logger.info(f"   ✓ Field: {field.get('name', 'Unknown')} ({field.get('type', 'Unknown')})")
            if len(self.fields) > 5:
                logger.info(f"   ... and {len(self.fields) - 5} more field(s)")
            
            # Extract data connections
            logger.info("📍 Step 5.5: Extracting data connections...")
            self._extract_data_connections()
            logger.info(f"✅ Found {len(self.data_connections)} data connection(s)")
            for conn in self.data_connections:
                logger.info(f"   ✓ Connection: {conn.get('type', 'Unknown')} - {conn.get('source', 'Unknown')}")
            
            # Extract transformations
            logger.info("📍 Step 5.6: Extracting transformations...")
            self._extract_transformations()
            logger.info(f"✅ Found {len(self.transformations)} transformation(s)")
            for trans in self.transformations[:3]:
                logger.info(f"   ✓ {trans.get('type', 'Unknown')}: {trans.get('description', 'Unknown')}")
            if len(self.transformations) > 3:
                logger.info(f"   ... and {len(self.transformations) - 3} more transformation(s)")
            
            # Extract joins
            logger.info("📍 Step 5.7: Detecting JOIN operations...")
            self._extract_joins()
            logger.info(f"✅ Found {len(self.joins)} JOIN operation(s)")
            for join in self.joins:
                logger.info(f"   ✓ {join.get('type', 'Unknown')}: {join.get('description', 'Unknown')}")
            
            # Extract variables
            logger.info("📍 Step 5.8: Extracting variable definitions...")
            self._extract_variables()
            logger.info(f"✅ Found {len(self.variables)} variable(s)")
            for var in self.variables[:3]:
                logger.info(f"   ✓ Variable: {var.get('name', 'Unknown')}")
            if len(self.variables) > 3:
                logger.info(f"   ... and {len(self.variables) - 3} more variable(s)")
            
            logger.info("=" * 80)
            logger.info("✅ PARSING COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            
            return {
                "status": "success",
                "parse_timestamp": datetime.now().isoformat(),
                "script_length": self.script_length,
                "summary": {
                    "tables_count": len(self.tables),
                    "fields_count": len(self.fields),
                    "connections_count": len(self.data_connections),
                    "transformations_count": len(self.transformations),
                    "joins_count": len(self.joins),
                    "variables_count": len(self.variables),
                    "comments_count": len(self.comments)
                },
                "details": {
                    "tables": self.tables,
                    "fields": self.fields,
                    "data_connections": self.data_connections,
                    "transformations": self.transformations,
                    "joins": self.joins,
                    "variables": self.variables,
                    "comments": self.comments
                }
            }
        except Exception as e:
            logger.error(f"❌ Error during parsing: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "parse_timestamp": datetime.now().isoformat()
            }

    def _extract_comments(self):
        """Extract comments from script"""
        logger.debug("Extracting inline and block comments...")
        
        # Match // comments
        inline_comments = re.findall(r'//.*?(?=\n|$)', self.loadscript, re.DOTALL)
        self.comments.extend([{"type": "inline", "text": c.strip()} for c in inline_comments])
        
        # Match /* */ comments
        block_comments = re.findall(r'/\*.*?\*/', self.loadscript, re.DOTALL)
        self.comments.extend([{"type": "block", "text": c.strip()} for c in block_comments])

    def _extract_load_statements(self):
        """Extract LOAD statements"""
        logger.debug("Searching for LOAD statements...")
        
        # Match LOAD ... FROM patterns
        load_patterns = [
            r'LOAD\s+[\s\S]*?(?=;)',
            r'LOAD\s+[\s\S]*?(?=FROM)',
            r'LOAD\s+[\s\S]*?(?=RESIDENT)',
        ]
        
        for pattern in load_patterns:
            matches = re.finditer(pattern, self.loadscript, re.IGNORECASE)
            for match in matches:
                statement = match.group(0).strip()
                self.load_statements.append({
                    "statement": statement[:200],
                    "full_length": len(statement)
                })

    def _extract_tables(self):
        """Extract table names"""
        logger.debug("Extracting table names...")
        
        # Pattern 1: [TableName]: LOAD
        pattern1 = r'\[([^\]]+)\]\s*:\s*(?:LOAD|load)'
        matches = re.finditer(pattern1, self.loadscript)
        for match in matches:
            table_name = match.group(1)
            self.tables.append({
                "name": table_name,
                "type": "load_statement",
                "pattern": "bracketed"
            })
        
        # Pattern 2: TableName: LOAD (without brackets)
        pattern2 = r'(\w+)\s*:\s*(?:LOAD|load)'
        matches = re.finditer(pattern2, self.loadscript)
        for match in matches:
            table_name = match.group(1)
            if table_name.upper() not in ['LOAD', 'FROM', 'WHERE', 'RESIDENT', 'KEY']:
                if not any(t['name'] == table_name for t in self.tables):
                    self.tables.append({
                        "name": table_name,
                        "type": "load_statement",
                        "pattern": "unbracketed"
                    })
        
        # Remove duplicates
        seen = set()
        unique_tables = []
        for table in self.tables:
            if table['name'] not in seen:
                seen.add(table['name'])
                unique_tables.append(table)
        self.tables = unique_tables

    def _extract_fields(self):
        """Extract field definitions"""
        logger.debug("Extracting field definitions...")
        
        # Match field definitions in LOAD statements
        field_pattern = r'(?:LOAD\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+(?:as\s+)?([A-Za-z_][A-Za-z0-9_]*)?'
        
        # More specific: fields after LOAD keyword
        load_blocks = re.finditer(r'LOAD\s+([\s\S]*?)(?=FROM|RESIDENT|;|$)', self.loadscript, re.IGNORECASE)
        
        for block in load_blocks:
            load_section = block.group(1)
            # Extract field names (simplified)
            fields = re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*(?:as|AS)?', load_section)
            for field in fields:
                if field.upper() not in ['FROM', 'WHERE', 'RESIDENT', 'LOAD', 'SELECT']:
                    if not any(f['name'] == field for f in self.fields):
                        self.fields.append({
                            "name": field,
                            "type": "column",
                            "extracted_from": "load_statement"
                        })

    def _extract_data_connections(self):
        """Extract data connections (file paths, database connections)"""
        logger.debug("Extracting data connections...")
        
        # Match lib:// connections
        lib_connections = re.findall(r'lib://([^\s;\'\"]+)', self.loadscript)
        for conn in lib_connections:
            self.data_connections.append({
                "type": "library",
                "source": f"lib://{conn}",
                "path": conn
            })
        
        # Match file:// connections
        file_connections = re.findall(r'file://([^\s;\'\"]+)', self.loadscript)
        for conn in file_connections:
            self.data_connections.append({
                "type": "file",
                "source": f"file://{conn}",
                "path": conn
            })
        
        # Match direct file references in FROM clauses
        from_patterns = re.findall(r'FROM\s*[\'"]?([^\s;\'\"]+\.\w{3,4})[\'"]?', self.loadscript, re.IGNORECASE)
        for path in from_patterns:
            if not any(c['path'] == path for c in self.data_connections):
                self.data_connections.append({
                    "type": "file_reference",
                    "source": path,
                    "path": path
                })
        
        # Match database connections (SQL, Oracle, etc.)
        db_patterns = re.findall(r'(ODBC|SQL|ORACLE|MYSQL|POSTGRESQL)\s+([^;]+)', self.loadscript, re.IGNORECASE)
        for db_type, db_detail in db_patterns:
            self.data_connections.append({
                "type": "database",
                "source": db_type,
                "detail": db_detail.strip()[:100]
            })

    def _extract_transformations(self):
        """Extract data transformations"""
        logger.debug("Extracting transformations...")
        
        # WHERE clauses
        where_clauses = re.finditer(r'WHERE\s+([^;]*)', self.loadscript, re.IGNORECASE)
        for match in where_clauses:
            clause = match.group(1).strip()
            self.transformations.append({
                "type": "filter",
                "description": f"WHERE {clause[:80]}"
            })
        
        # GROUP BY statements
        group_bys = re.finditer(r'GROUP\s+BY\s+([^;]*)', self.loadscript, re.IGNORECASE)
        for match in group_bys:
            clause = match.group(1).strip()
            self.transformations.append({
                "type": "aggregation",
                "description": f"GROUP BY {clause[:80]}"
            })
        
        # DISTINCT keyword
        if re.search(r'\bDISTINCT\b', self.loadscript, re.IGNORECASE):
            self.transformations.append({
                "type": "deduplication",
                "description": "DISTINCT"
            })
        
        # ORDER BY statements
        order_bys = re.finditer(r'ORDER\s+BY\s+([^;]*)', self.loadscript, re.IGNORECASE)
        for match in order_bys:
            clause = match.group(1).strip()
            self.transformations.append({
                "type": "sorting",
                "description": f"ORDER BY {clause[:80]}"
            })

    def _extract_joins(self):
        """Extract JOIN operations"""
        logger.debug("Extracting JOIN operations...")
        
        # Different types of joins
        join_types = ['INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'FULL JOIN', 'CROSS JOIN']
        
        for join_type in join_types:
            pattern = f'{join_type}\\s+([^\\s]+)\\s+(?:ON|WHERE)\\s+([^;]*)'
            matches = re.finditer(pattern, self.loadscript, re.IGNORECASE)
            for match in matches:
                table = match.group(1).strip()
                condition = match.group(2).strip()[:80]
                self.joins.append({
                    "type": join_type,
                    "table": table,
                    "description": f"{join_type} {table} ON {condition}"
                })

    def _extract_variables(self):
        """Extract variable definitions"""
        logger.debug("Extracting variable definitions...")
        
        # Pattern: LET or SET statements
        let_patterns = re.finditer(r'(?:LET|SET)\s+(\w+)\s*=\s*([^;]*)', self.loadscript, re.IGNORECASE)
        for match in let_patterns:
            var_name = match.group(1)
            var_value = match.group(2).strip()[:80]
            self.variables.append({
                "name": var_name,
                "value": var_value,
                "type": "let_set"
            })


# Standalone testing
if __name__ == "__main__":
    sample_script = """
    // Sample Load Script
    [Customers]:
    LOAD
        CustomerID as [Cust ID],
        CustomerName,
        Country
    FROM lib://DataFiles/customers.csv;
    
    [Orders]:
    LOAD
        OrderID,
        CustomerID,
        OrderDate,
        Amount
    FROM lib://DataFiles/orders.xlsx
    WHERE OrderDate > '2024-01-01';
    
    [OrderDetails]:
    LOAD
        OrderID,
        ProductID,
        Quantity,
        UnitPrice,
        Quantity * UnitPrice as LineTotal
    FROM lib://DataFiles/orderdetails.csv
    GROUP BY OrderID;
    """
    
    parser = LoadScriptParser(sample_script)
    result = parser.parse()
    logger.info(f"\nParsing Result:\n{result}")
