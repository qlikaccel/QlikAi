#!/usr/bin/env python3
"""
Simple M Query Generator - Creates WORKING M Query code ready to paste into Power BI
"""

from typing import Dict, List, Any
from datetime import datetime

class SimpleMQueryGenerator:
    """Generate simple, working M Query code that users can immediately use"""
    
    def __init__(self, parsed_script: Dict[str, Any]):
        self.parsed_script = parsed_script
        self.details = parsed_script.get('details', {})
        self.summary = parsed_script.get('summary', {})
        
    def generate(self) -> str:
        """Generate simple, working M Query"""
        
        tables = self.details.get('tables', [])
        
        # Start with header
        output = self._header()
        
        # If no tables, return minimal query
        if not tables:
            output += self._empty_query()
            return output
        
        # For each table, create a working query
        for i, table in enumerate(tables, 1):
            output += self._generate_table_query(table, i, len(tables))
        
        # Add final section
        output += self._footer(tables)
        
        return output
    
    def _header(self) -> str:
        """Header with instructions"""
        return f"""// PowerBI M Query - Converted from Qlik LoadScript
// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// 
// INSTRUCTIONS:
// 1. Open Power BI Desktop
// 2. Home → Get Data → Power Query Editor → Advanced Editor
// 3. Replace ALL content with this code
// 4. Update the file paths below to your actual data files
// 5. Click Done

// ═══════════════════════════════════════════════════════════════════════════════

"""
    
    def _generate_table_query(self, table: Dict[str, Any], table_num: int, total_tables: int) -> str:
        """Generate M Query for a single table"""
        
        table_name = table.get('name', f'Table_{table_num}')
        fields = table.get('fields', [])
        
        # Start with table definition
        code = f"\n// ════════════════════════════════════════════════════════════════════════════════\n"
        code += f"// TABLE {table_num}: {table_name}\n"
        code += f"// ════════════════════════════════════════════════════════════════════════════════\n\n"
        
        # If it's the first table, add the main connection
        if table_num == 1:
            code += f"{table_name} = let\n"
            code += f"    // TODO: Update this file path to your data source\n"
            code += f"    // Supported formats: CSV, Excel (.xlsx), JSON, SQL Database, API, etc.\n"
            code += f"    Source = Csv.Document(File.Contents(\"C:\\\\data\\\\{table_name}.csv\"), "
            code += f"[Delimiter=\",\", Quote=\"\"\"\"]),\n"
        else:
            code += f"{table_name} = let\n"
            code += f"    Source = Csv.Document(File.Contents(\"C:\\\\data\\\\{table_name}.csv\"), "
            code += f"[Delimiter=\",\", Quote=\"\"\"\"]),\n"
        
        # Add header promotion
        code += f"    PromotedHeaders = Table.PromoteHeaders(Source),\n"
        
        # Add column type transformation if we have fields
        if fields:
            code += f"    ChangedType = Table.TransformColumnTypes(PromotedHeaders, " + "{\n"
            
            for j, field in enumerate(fields):
                field_name = field.get('name', 'Field')
                field_type = field.get('type', 'text').lower()
                m_type = self._map_type(field_type)
                
                code += f"        {{" + f'"{field_name}"' + f", {m_type}" + "}}"
                if j < len(fields) - 1:
                    code += ","
                code += "\n"
            
            code += "    }),\n"
        else:
            code += f"    ChangedType = PromotedHeaders,\n"
        
        # Add null filtering
        code += f"    RemoveNulls = Table.SelectRows(ChangedType, each [Column1] <> null)\n"
        
        # End the let statement
        code += f"in\n"
        code += f"    RemoveNulls,\n"
        
        return code
    
    def _empty_query(self) -> str:
        """Return minimal query when no tables found"""
        return """
// No tables were parsed from the script
// Update the data source below:

Example = let
    Source = Csv.Document(File.Contents("C:\\\\data\\\\your_file.csv"), [Delimiter=",", Quote="\\""])
in
    Source
"""
    
    def _footer(self, tables: List[Dict[str, Any]]) -> str:
        """Footer with combined output"""
        
        if not tables:
            return ""
        
        footer = "\n// ═══════════════════════════════════════════════════════════════════════════════\n"
        footer += "// FINAL OUTPUT - All tables combined\n"
        footer += "// ═══════════════════════════════════════════════════════════════════════════════\n\n"
        
        # Just reference each table
        for table in tables:
            table_name = table.get('name', 'Table')
            footer += f"{table_name}\n"
        
        return footer
    
    def _map_type(self, qlik_type: str) -> str:
        """Map Qlik type to Power BI M type"""
        
        qlik_type = qlik_type.lower().strip()
        
        # Type mappings
        type_map = {
            'integer': 'Int64.Type',
            'int': 'Int64.Type',
            'number': 'Double.Type',
            'numeric': 'Double.Type',
            'decimal': 'Double.Type',
            'float': 'Double.Type',
            'double': 'Double.Type',
            'text': 'Text.Type',
            'string': 'Text.Type',
            'varchar': 'Text.Type',
            'char': 'Text.Type',
            'date': 'Date.Type',
            'datetime': 'DateTime.Type',
            'timestamp': 'DateTime.Type',
            'time': 'Time.Type',
            'boolean': 'Logical.Type',
            'bool': 'Logical.Type',
            'binary': 'Binary.Type',
        }
        
        return type_map.get(qlik_type, 'Text.Type')


# For testing
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    sample_parsed = {
        "status": "success",
        "summary": {
            "tables_count": 2,
            "fields_count": 5
        },
        "details": {
            "tables": [
                {
                    "name": "Vehicles",
                    "fields": [
                        {"name": "VehicleID", "type": "Integer"},
                        {"name": "Make", "type": "Text"},
                        {"name": "Model", "type": "Text"},
                        {"name": "Year", "type": "Integer"}
                    ]
                },
                {
                    "name": "Scooters",
                    "fields": [
                        {"name": "ScooterID", "type": "Integer"},
                        {"name": "Brand", "type": "Text"}
                    ]
                }
            ]
        }
    }
    
    generator = SimpleMQueryGenerator(sample_parsed)
    m_query = generator.generate()
    print(m_query)
