"""
Qlik LoadScript to PowerBI M Query Converter Module

Converts parsed Qlik loadscript to PowerBI M query language with detailed logging.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class LoadScriptToMQueryConverter:
    """Convert parsed Qlik loadscript to PowerBI M (Power Query) language"""
    
    def __init__(self, parsed_script: Dict[str, Any]):
        """Initialize converter with parsed script data"""
        logger.info("=" * 80)
        logger.info("PHASE 6: CONVERTING TO POWERBI M QUERY")
        logger.info("=" * 80)
        
        self.parsed_script = parsed_script
        self.m_queries = []
        self.conversion_warnings = []
        self.conversion_errors = []
        
        logger.info(f"📊 Input Script Summary:")
        logger.info(f"   Tables: {parsed_script.get('summary', {}).get('tables_count', 0)}")
        logger.info(f"   Fields: {parsed_script.get('summary', {}).get('fields_count', 0)}")
        logger.info(f"   Connections: {parsed_script.get('summary', {}).get('connections_count', 0)}")
        logger.info(f"   Transformations: {parsed_script.get('summary', {}).get('transformations_count', 0)}")
        logger.info(f"⏰ Conversion Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def convert(self) -> Dict[str, Any]:
        """Main conversion function"""
        logger.info("📍 Starting Qlik to Power Query M conversion...")
        
        try:
            details = self.parsed_script.get('details', {})
            
            # Convert data connections
            logger.info("📍 Step 6.1: Converting data connections...")
            connection_queries = self._convert_connections(details.get('data_connections', []))
            logger.info(f"✅ Converted {len(connection_queries)} connection(s)")
            
            # Convert tables
            logger.info("📍 Step 6.2: Converting table definitions...")
            table_queries = self._convert_tables(details.get('tables', []), details.get('data_connections', []))
            logger.info(f"✅ Converted {len(table_queries)} table(s)")
            
            # Convert fields
            logger.info("📍 Step 6.3: Converting field definitions...")
            field_transformations = self._convert_fields(details.get('fields', []))
            logger.info(f"✅ Generated {len(field_transformations)} field transformation(s)")
            
            # Convert transformations
            logger.info("📍 Step 6.4: Converting transformations...")
            transformations = self._convert_transformations(details.get('transformations', []))
            logger.info(f"✅ Converted {len(transformations)} transformation(s)")
            
            # Convert joins
            logger.info("📍 Step 6.5: Converting JOIN operations...")
            join_statements = self._convert_joins(details.get('joins', []))
            logger.info(f"✅ Converted {len(join_statements)} JOIN(s)")
            
            # Combine all queries
            logger.info("📍 Step 6.6: Assembling final M query...")
            final_query = self._assemble_final_query(
                connection_queries,
                table_queries,
                field_transformations,
                transformations,
                join_statements
            )
            logger.info(f"✅ Final M query assembled ({len(final_query)} characters)")
            
            # Log warnings if any
            if self.conversion_warnings:
                logger.warning(f"⚠️  Conversion generated {len(self.conversion_warnings)} warning(s):")
                for i, warning in enumerate(self.conversion_warnings, 1):
                    logger.warning(f"   {i}. {warning}")
            
            # Log errors if any
            if self.conversion_errors:
                logger.error(f"❌ Conversion encountered {len(self.conversion_errors)} error(s):")
                for i, error in enumerate(self.conversion_errors, 1):
                    logger.error(f"   {i}. {error}")
            
            logger.info("=" * 80)
            logger.info("✅ CONVERSION COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            
            return {
                "status": "success",
                "conversion_timestamp": datetime.now().isoformat(),
                "m_query": final_query,
                "m_queries_detail": {
                    "connections": connection_queries,
                    "tables": table_queries,
                    "fields": field_transformations,
                    "transformations": transformations,
                    "joins": join_statements
                },
                "query_length": len(final_query),
                "warnings_count": len(self.conversion_warnings),
                "errors_count": len(self.conversion_errors),
                "warnings": self.conversion_warnings,
                "errors": self.conversion_errors,
                "statistics": {
                    "total_connections_converted": len(connection_queries),
                    "total_tables_converted": len(table_queries),
                    "total_fields_converted": len(field_transformations),
                    "total_transformations": len(transformations),
                    "total_joins": len(join_statements)
                }
            }
        except Exception as e:
            logger.error(f"❌ Error during conversion: {str(e)}")
            self.conversion_errors.append(f"Fatal error: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "conversion_timestamp": datetime.now().isoformat(),
                "errors": self.conversion_errors
            }

    def _convert_connections(self, connections: List[Dict]) -> List[Dict]:
        """Convert data connections to M query format"""
        logger.debug(f"Converting {len(connections)} connection(s)")
        m_connections = []
        
        for conn in connections:
            conn_type = conn.get('type', 'unknown')
            source = conn.get('source', '')
            
            logger.debug(f"   Converting {conn_type}: {source}")
            
            if conn_type == 'library':
                # lib:// -> relative file path
                path = source.replace('lib://', '')
                m_query = f'Source = Excel.Workbook(File.Contents("{path}"), [DelimiterType=Delimiter.Comma])'
                m_connections.append({
                    "connection_type": conn_type,
                    "original": source,
                    "m_query": m_query
                })
                logger.debug(f"   ✓ Generated M query for {conn_type}")
                
            elif conn_type == 'file':
                path = source.replace('file://', '')
                # Detect file type
                if path.endswith('.csv'):
                    m_query = f'Source = Csv.Document(File.Contents("{path}"),[Delimiter=",", Encoding=1252])'
                elif path.endswith(('.xlsx', '.xls')):
                    m_query = f'Source = Excel.Workbook(File.Contents("{path}"))'
                else:
                    m_query = f'Source = File.Contents("{path}")'
                    self.conversion_warnings.append(f"Unknown file type for {path}, using generic File.Contents")
                
                m_connections.append({
                    "connection_type": conn_type,
                    "original": source,
                    "m_query": m_query
                })
                logger.debug(f"   ✓ Generated M query for {conn_type}")
                
            elif conn_type == 'file_reference':
                # Direct file reference
                if source.endswith('.csv'):
                    m_query = f'Source = Csv.Document(File.Contents("{source}"),[Delimiter=","])'
                elif source.endswith(('.xlsx', '.xls')):
                    m_query = f'Source = Excel.Workbook(File.Contents("{source}"))'
                else:
                    m_query = f'Source = File.Contents("{source}")'
                
                m_connections.append({
                    "connection_type": conn_type,
                    "original": source,
                    "m_query": m_query
                })
                logger.debug(f"   ✓ Generated M query for {conn_type}")
                
            elif conn_type == 'database':
                db_source = conn.get('source', 'UNKNOWN')
                m_query = f'Source = [ManualConnection Name = "{db_source}", Note = "See database connection details in original Qlik app"]'
                
                m_connections.append({
                    "connection_type": conn_type,
                    "original": db_source,
                    "m_query": m_query
                })
                self.conversion_warnings.append(f"Database connection {db_source} requires manual configuration in Power Query")
                logger.debug(f"   ⚠️  {db_source} requires manual setup")
        
        return m_connections

    def _convert_tables(self, tables: List[Dict], connections: List[Dict]) -> List[Dict]:
        """Convert table definitions to M query tables"""
        logger.debug(f"Converting {len(tables)} table(s)")
        m_tables = []
        
        for table in tables:
            table_name = table.get('name', 'UnknownTable')
            logger.debug(f"   Converting table: {table_name}")
            
            # Create a basic table reference
            m_query = f'''// Table: {table_name}
let
    Source = [Reference to source connection],
    #"{table_name}" = Source,
    Renamed = Table.RenameColumns(#"{table_name}", {{{{"{table_name}", "{table_name}"}}}})
in
    Renamed'''
            
            m_tables.append({
                "table_name": table_name,
                "m_query": m_query,
                "conversion_note": "Basic table structure - requires source connection details"
            })
            logger.debug(f"   ✓ Generated M query for {table_name}")
        
        return m_tables

    def _convert_fields(self, fields: List[Dict]) -> List[Dict]:
        """Convert field definitions to M query type specifications"""
        logger.debug(f"Converting {len(fields)} field(s)")
        field_transformations = []
        
        for field in fields:
            field_name = field.get('name', 'UnknownField')
            field_type = field.get('type', 'column')
            
            logger.debug(f"   Converting field: {field_name} ({field_type})")
            
            # Generate M query type specifications
            m_query = f'''Table.TransformColumnTypes(
    Table,
    {{{{"{field_name}", type text}}}}  // Adjust type based on actual data
)'''
            
            field_transformations.append({
                "field_name": field_name,
                "field_type": field_type,
                "m_query": m_query,
                "note": "Type specification - adjust actual types based on data analysis"
            })
            logger.debug(f"   ✓ Generated type spec for {field_name}")
        
        return field_transformations

    def _convert_transformations(self, transformations: List[Dict]) -> List[Dict]:
        """Convert data transformations to M query operations"""
        logger.debug(f"Converting {len(transformations)} transformation(s)")
        m_transformations = []
        
        for trans in transformations:
            trans_type = trans.get('type', 'unknown')
            description = trans.get('description', '')
            
            logger.debug(f"   Converting {trans_type}: {description}")
            
            if trans_type == 'filter':
                # WHERE clause -> Table.SelectRows
                condition = description.replace('WHERE ', '')
                m_query = f'Table.SelectRows(#"Transformed", each [Column] = "{condition}")'
                m_transformations.append({
                    "transformation_type": trans_type,
                    "original": description,
                    "m_query": m_query
                })
                
            elif trans_type == 'aggregation':
                # GROUP BY -> Table.Group
                m_query = f'Table.Group(#"Transformed", {{"GroupBy"}}, {{"Aggregates"}})'
                m_transformations.append({
                    "transformation_type": trans_type,
                    "original": description,
                    "m_query": m_query
                })
                
            elif trans_type == 'deduplication':
                # DISTINCT -> Table.Distinct
                m_query = f'Table.Distinct(#"Transformed")'
                m_transformations.append({
                    "transformation_type": trans_type,
                    "original": description,
                    "m_query": m_query
                })
                
            elif trans_type == 'sorting':
                # ORDER BY -> Table.Sort
                m_query = f'Table.Sort(#"Transformed", {{{{"{description}", Order.Ascending}}}}'
                m_transformations.append({
                    "transformation_type": trans_type,
                    "original": description,
                    "m_query": m_query
                })
            
            logger.debug(f"   ✓ Generated M query for {trans_type}")
        
        return m_transformations

    def _convert_joins(self, joins: List[Dict]) -> List[Dict]:
        """Convert JOIN operations to M query merge operations"""
        logger.debug(f"Converting {len(joins)} JOIN(s)")
        m_joins = []
        
        for join in joins:
            join_type = join.get('type', 'INNER JOIN')
            target_table = join.get('table', 'TargetTable')
            description = join.get('description', '')
            
            logger.debug(f"   Converting {join_type} with {target_table}")
            
            # Map SQL JOIN types to M query
            if 'INNER' in join_type:
                m_type = 'JoinKind.Inner'
            elif 'LEFT' in join_type:
                m_type = 'JoinKind.LeftOuter'
            elif 'RIGHT' in join_type:
                m_type = 'JoinKind.RightOuter'
            elif 'FULL' in join_type:
                m_type = 'JoinKind.FullOuter'
            elif 'CROSS' in join_type:
                m_type = 'JoinKind.LeftAnti'
            else:
                m_type = 'JoinKind.Inner'
            
            m_query = f'''Table.NestedJoin(
    #"Transformed",
    {{"JoinColumn"}},
    {target_table},
    {{"JoinColumn"}},
    "JoinedTable",
    [{m_type}]
)'''
            
            m_joins.append({
                "join_type": join_type,
                "target_table": target_table,
                "m_query": m_query,
                "note": "Adjust join columns and parameters based on actual data model"
            })
            logger.debug(f"   ✓ Generated M query for {join_type}")
        
        return m_joins

    def _assemble_final_query(self, connections, tables, fields, transformations, joins) -> str:
        """Assemble all components into final M query"""
        logger.debug("Assembling final M query...")
        
        query = """// Power Query - Converted from Qlik LoadScript
// Auto-generated M query
// Manual adjustments may be required for data types and source connections

"""
        
        # Add header comment
        query += f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        query += f"// Tables: {len(tables)}\n"
        query += f"// Connections: {len(connections)}\n"
        query += f"// Transformations: {len(transformations)}\n"
        query += f"// Joins: {len(joins)}\n\n"
        
        # Add connections
        if connections:
            query += "// ==== DATA CONNECTIONS ====\n"
            for conn in connections:
                query += f"// {conn.get('original', 'Connection')}\n"
                query += conn.get('m_query', '') + "\n\n"
        
        # Add tables
        if tables:
            query += "// ===== TABLE DEFINITIONS =====\n"
            for table in tables:
                query += f"// Table: {table.get('table_name', 'Unknown')}\n"
                query += table.get('m_query', '') + "\n\n"
        
        # Add transformations if any
        if transformations:
            query += "// ===== TRANSFORMATIONS =====\n"
            for trans in transformations:
                query += f"// {trans.get('original', 'Transformation')}\n"
                query += trans.get('m_query', '') + "\n\n"
        
        # Add joins if any
        if joins:
            query += "// ===== JOINS =====\n"
            for join in joins:
                query += f"// {join.get('join_type', 'Join')}: {join.get('target_table', 'Table')}\n"
                query += join.get('m_query', '') + "\n\n"
        
        query += "\n// ===== FINAL OUTPUT =====\nin\n"
        query += "    FinalTable\n"
        
        logger.debug(f"✅ Final query assembled ({len(query)} characters)")
        return query


# Standalone testing
if __name__ == "__main__":
    sample_parsed = {
        "status": "success",
        "summary": {
            "tables_count": 2,
            "fields_count": 5,
            "connections_count": 1,
            "transformations_count": 1,
            "joins_count": 0,
            "variables_count": 0,
            "comments_count": 1
        },
        "details": {
            "tables": [
                {"name": "Customers"},
                {"name": "Orders"}
            ],
            "fields": [
                {"name": "CustomerID", "type": "column"},
                {"name": "OrderID", "type": "column"},
                {"name": "Amount", "type": "column"}
            ],
            "data_connections": [
                {"type": "file", "source": "file://data.csv"}
            ],
            "transformations": [
                {"type": "filter", "description": "WHERE OrderDate > '2024-01-01'"}
            ],
            "joins": [],
            "variables": [],
            "comments": [{"type": "inline", "text": "// Sample script"}]
        }
    }
    
    converter = LoadScriptToMQueryConverter(sample_parsed)
    result = converter.convert()
    logger.info(f"\n\nFinal M Query:\n{result.get('m_query', '')}")
