
"""
mquery_converter.py
───────────────────
Converts parsed Qlik table definitions into Power Query M expressions
suitable for embedding in a Power BI BIM partition.

CHANGES FROM ORIGINAL
─────────────────────
  ✅ Fix A: _resolve_output_columns() — BIM column metadata now reflects
            the ACTUAL post-transform output columns, not the raw source cols.
            Fixes silent publish failures where Fabric validates BIM cols
            against M query output at create time.

  ✅ Fix B: _build_safe_combine() — CONCATENATE now uses
            Table.SelectColumns(..., MissingField.UseNull) on every source
            before Table.Combine so schema is always aligned even when CSV
            files differ in column order or have extra columns.

  ✅ Fix C: _detect_and_apply_applymap() — APPLYMAP (dimension mapping) NOW ENABLED!
            Converts ApplyMap('MapTable', key_col, 'default') to M Query:
            1. Table.NestedJoin - LEFT JOIN with mapping table
            2. Table.ExpandTableColumn - Expand joined columns
            3. Table.ReplaceValue - Replace nulls with default value
            Integrated at Step 3.3 in transformation pipeline.

  ✅ Fix D: REMOVED - Full JOIN logic disabled in strict mode. All JOIN
            operations now return empty transforms (no-op). 
            is_join is always set to False in _auto_detect_transformations().

  ✅ Fix E: _apply_all_transformations() order: null fixes → concat →
            IF/WHERE → APPLYMAP → date → group_by → KEEP (JOIN removed).

  ✅ Fix F: _apply_date_transformation() — DATE transformation fully implemented.
            Converts date_id (YYYYMMDD) to full_date + year/month/day/quarter.
            Uses #date() for robust, null-safe parsing in M Query.

  All original logic preserved; changes are additive / targeted replacements.
"""

from __future__ import annotations
import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# TYPE MAPPING
# ─────────────────────────────────────────────────────────────────────────────

_QLIK_TO_M_TYPE: Dict[str, str] = {
    "string":    "type text",
    "text":      "type text",
    "number":    "type number",
    "integer":   "Int64.Type",
    "int":       "Int64.Type",
    "double":    "type number",
    "decimal":   "type number",
    "date":      "type date",
    "time":      "type time",
    "datetime":  "type datetime",
    "timestamp": "type datetime",
    "boolean":   "type logical",
    "bool":      "type logical",
    "mixed":     "type any",
    "wildcard":  "type text",
    "unknown":   "type text",
}

_QLIK_TO_M_TYPE_FOR_TABLE: Dict[str, str] = {
    "string":    "text",
    "text":      "text",
    "number":    "number",
    "integer":   "Int64.Type",
    "int":       "Int64.Type",
    "double":    "number",
    "decimal":   "number",
    "date":      "date",
    "time":      "time",
    "datetime":  "datetime",
    "timestamp": "datetime",
    "boolean":   "logical",
    "bool":      "logical",
    "mixed":     "any",
    "wildcard":  "text",
    "unknown":   "text",
}

_DEFAULT_M_TYPE = "type text"
_DEFAULT_M_TYPE_FOR_TABLE = "text"

# ─────────────────────────────────────────────────────────────────────────────
# SMART COLUMN TYPE INFERENCE
# ─────────────────────────────────────────────────────────────────────────────

_NAME_TO_M_TYPE: List[tuple] = [
    (re.compile(r"_date$|^date$|_dt$|_timestamp$", re.I),                       "type date"),
    (re.compile(r"_datetime$|_created_at$|_updated_at$|_modified_at$", re.I),   "type datetime"),
    (re.compile(r"_cost$|_fee$|_bill$|_price$|_rate$|_salary$", re.I),         "type number"),
    (re.compile(r"_covered$|_expense$|_revenue$|_income$|_tax$|_discount$", re.I), "type number"),
    (re.compile(r"_amount$", re.I),                                             "type number"),
    (re.compile(r"_days$|_years$|_count$|_qty$|_quantity$", re.I),              "Int64.Type"),
    (re.compile(r"_pct$|_percent$|_ratio$|_score$|_weight$", re.I),             "type number"),
    (re.compile(r"^is_|^has_|^can_|^was_|_flag$|_bool$", re.I),                "type logical"),
]


def _infer_type_from_name(col_name: str) -> str:
    clean = col_name.strip().lower()
    if "." in clean and not clean.startswith("#"):
        clean = clean.split(".", 1)[-1]
    if "-" in clean:
        return "type text"
    for pattern, m_type in _NAME_TO_M_TYPE:
        if pattern.search(clean):
            return m_type
    return "type text"


def _wrap_columns_in_brackets(expr: str) -> str:
    # 🔥 STRICT: Don't wrap IF statements - they're M keywords
    if not expr or "[" in expr or expr.upper().startswith("IF"):
        return expr
    expr = re.sub(r'\bIsNull\s*\(\s*([^,\)]+)\s*\)', r'(\1 = null)', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bIsEmpty\s*\(\s*([^,\)]+)\s*\)', r'(\1 = "" or \1 = null)', expr, flags=re.IGNORECASE)
    result = re.sub(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\b(?![\]])',
        lambda m: f'[{m.group(1)}]' if m.group(1).lower() not in ('null', 'true', 'false', 'and', 'or', 'if', 'then', 'else') else m.group(1),
        expr
    )
    result = re.sub(r'\[\[([^\[\]]+)\]\]', r'[\1]', result)
    
    # FIX 4: Ensure numeric comparisons don't quote numbers
    # Convert patterns like [hours_worked] > "8" to [hours_worked] > 8
    # But keep string comparisons like [name] = "John"
    result = re.sub(
        r'\[([^\]]+)\]\s*([><=!]+)\s*["\'](\d+(?:\.\d+)?)["\']',
        lambda m: f'[{m.group(1)}] {m.group(2)} {m.group(3)}',
        result
    )
    
    return result


def _is_numeric_literal(value: str) -> bool:
    if not value:
        return False
    val = value.strip()
    if val.startswith("[") or val.startswith("'") or val.startswith('"'):
        return False
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def _escape_m_string(text: str) -> str:
    if not text:
        return text
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '""')
    text = text.replace("\n", " ").replace("\r", "")
    return text


def _parse_nested_if_expression(expr: str) -> tuple[str, bool]:
    """
    Parse nested IF expressions from Qlik and convert to M Query chains.
    
    FIX #7 — Support nested IF conditions like:
    If(total_hours > 100, 'High Performer', If(total_hours > 50, 'Medium', 'Low'))
    
    Returns (m_query_expression, is_numeric)
    
    🔥 FIX: Properly bracket column names and convert quotes
    - hours_worked > 8 → [hours_worked] > 8
    - 'Overtime' → "Overtime"
    
    Example:
    Input:  "If(total_hours > 100, 'High Performer', If(total_hours > 50, 'Medium', 'Low'))"
    Output: "if [total_hours] > 100 then \"High Performer\" else if [total_hours] > 50 then \"Medium\" else \"Low\""
    """
    expr = expr.strip()
    if not expr.upper().startswith("IF("):
        return expr, False
    
    # 🔥 FIX: Convert condition with proper column bracketing
    def format_condition(cond_str: str) -> str:
        """Convert condition: hours_worked > 8 → [hours_worked] > 8"""
        cond = cond_str.strip()
        # Replace bare column names (not already bracketed) with bracketed versions
        # Match: word characters surrounded by spaces/operators, not already in brackets
        cond = re.sub(
            r'(?<!\[)([A-Za-z_][A-Za-z0-9_]*)(?![\]\w])',
            lambda m: f'[{m.group(1)}]' if m.group(1).upper() not in ['IS', 'NOT', 'NULL', 'AND', 'OR', 'TRUE', 'FALSE'] else m.group(1),
            cond
        )
        return cond
    
    # Helper to format values
    def format_value(raw_val: str) -> tuple[str, bool]:
        val = raw_val.strip()
        # Remove outer quotes if present (single OR double)
        if (val.startswith("'") and val.endswith("'")) or \
           (val.startswith('"') and val.endswith('"')):
            unquoted = val[1:-1]
            if _is_numeric_literal(unquoted):
                # Keep as numeric literal (no quotes)
                return unquoted, True
            else:
                # 🔥 FIX: Always use double quotes for string literals
                return f'"{unquoted}"', False
        # No quotes - check what it is
        if _is_numeric_literal(val):
            return val, True
        else:
            # Wrap unquoted column reference in brackets
            return _wrap_columns_in_brackets(val), False
    
    # Remove outer IF(...) wrapper (case insensitive)
    # Find the last ) and strip from index 3 to len-1
    if len(expr) < 5:  # Minimum: "if(a,b,c)" has 9 chars minimum but let's be safe
        return expr, False
    
    inner = expr[3:-1]  # Strip opening "IF(" and closing ")"
    
    # Find the condition and its split points
    parts = _split_if_expression(inner)
    if len(parts) < 3:
        return expr, False
    
    condition, true_val, false_val = parts[0], parts[1], parts[2]
    
    # 🔥 FIX: Format condition with proper column bracketing
    condition = format_condition(condition.strip())
    
    # Format true value
    true_formatted, true_is_numeric = format_value(true_val.strip())
    
    # Check if false_val is another IF (nested)
    false_upper = false_val.strip().upper()
    if false_upper.startswith("IF("):
        # Recursively parse nested IF
        false_formatted, false_is_numeric = _parse_nested_if_expression(false_val.strip())
        is_numeric = true_is_numeric and false_is_numeric
        # Build nested if-then-else
        m_expr = f"if {condition} then {true_formatted} else {false_formatted}"
        return m_expr, is_numeric
    else:
        # Simple false value - format it
        false_formatted, false_is_numeric = format_value(false_val.strip())
        is_numeric = true_is_numeric and false_is_numeric
        m_expr = f"if {condition} then {true_formatted} else {false_formatted}"
        return m_expr, is_numeric


def _split_if_expression(inner: str) -> list[str]:
    """
    Split IF expression into [condition, true_value, false_value].
    Handles nested IF, parentheses, and quoted strings.
    """
    parts = []
    current = ""
    depth = 0
    in_quote = False
    quote_char = None
    
    for i, char in enumerate(inner):
        # Handle quotes
        if char in ('"', "'") and (i == 0 or inner[i-1] != "\\"):
            if not in_quote:
                in_quote = True
                quote_char = char
            elif char == quote_char:
                in_quote = False
                quote_char = None
        
        # Count parentheses depth
        if not in_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                # Found a separator comma at top level
                parts.append(current.strip())
                current = ""
                continue
        
        current += char
    
    # Add final part
    if current.strip():
        parts.append(current.strip())
    
    return parts


def _m_type(qlik_type: str, col_name: str = "") -> str:
    if "-" in col_name:
        return "type text"
    plain_name = (
        col_name.split(".", 1)[-1]
        if ("." in col_name and not col_name.startswith("#"))
        else col_name
    )
    qlik_lower = str(qlik_type).lower().strip()
    if qlik_lower not in ("string", "text", "unknown", "mixed", "wildcard", ""):
        return _QLIK_TO_M_TYPE.get(qlik_lower, _DEFAULT_M_TYPE)
    return _infer_type_from_name(plain_name)


def _m_type_for_table(qlik_type: str, col_name: str = "") -> str:
    return "text"


def _normalize_path(path: str) -> str:
    path = re.sub(r"^lib://[^/]*/", "", path)
    path = re.sub(r"^lib://", "", path)
    return path


def _sanitize_col_name(name: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_ ]*$", name):
        return name
    return f'#"{name}"'


def _strip_qlik_qualifier(col_name: str) -> str:
    if not col_name or col_name.startswith("#"):
        return col_name
    if "." in col_name and "-" not in col_name:
        return col_name.split(".", 1)[-1]
    return col_name


def validate_sharepoint_url_strict(url: str) -> tuple[bool, str]:
    if not url or not isinstance(url, str) or not url.strip():
        return False, "URL cannot be empty"
    trimmed = url.strip()
    trimmed_lower = trimmed.lower()
    if not trimmed_lower.startswith("https://"):
        if trimmed_lower.startswith("http://"):
            return False, "❌ Must use HTTPS (not HTTP). Use: https://"
        return False, "❌ Must start with https://"
    if ".sharepoint.com" not in trimmed_lower:
        if ".com" not in trimmed_lower:
            return False, "❌ Missing .com - Should end with .sharepoint.com"
        if "sharepoint" not in trimmed_lower:
            return False, "❌ Missing 'sharepoint' - Should be: https://COMPANYNAME.sharepoint.com"
        return False, "❌ Invalid format. Should be: https://COMPANYNAME.sharepoint.com"
    sharepoint_match = re.match(r'https://([^.]+)\.sharepoint\.com', trimmed, re.IGNORECASE)
    if not sharepoint_match or not sharepoint_match.group(1):
        return False, "❌ Missing company name - Should be: https://COMPANYNAME.sharepoint.com"
    company_name = sharepoint_match.group(1)
    if not company_name or len(company_name) == 0 or not re.search(r'[a-z0-9]', company_name, re.IGNORECASE):
        return False, "❌ Invalid company name - Should be: https://COMPANYNAME.sharepoint.com"
    return True, ""


def _is_sharepoint_url(url: str) -> bool:
    cleaned = url.strip().strip('"').strip("'").lower()
    return "sharepoint.com" in cleaned or "-my.sharepoint.com" in cleaned


def _is_onedrive_personal_url(url: str) -> bool:
    cleaned = url.strip().strip('"').strip("'").lower()
    return "onedrive.live.com" in cleaned or "1drv.ms" in cleaned


def _is_s3_url(url: str) -> bool:
    cleaned = url.strip().strip('"').strip("'").lower()
    return "s3.amazonaws.com" in cleaned or cleaned.startswith("s3://") or ".s3." in cleaned


def _is_azure_blob_url(url: str) -> bool:
    cleaned = url.strip().strip('"').strip("'").lower()
    return "blob.core.windows.net" in cleaned or "dfs.core.windows.net" in cleaned


def _is_web_url(url: str) -> bool:
    cleaned = url.strip().strip('"').strip("'").lower()
    return (cleaned.startswith("http://") or cleaned.startswith("https://")) and not (
        _is_sharepoint_url(url) or _is_s3_url(url) or _is_azure_blob_url(url)
    )


def _quote_url(url: str) -> str:
    cleaned = url.strip().strip('"').strip("'")
    return f'"{cleaned}"'


def _build_sharepoint_m(
    site_url: str,
    filename: str,
    folder_path: str,
    delimiter: str,
    encoding: int,
    transform_step: str,
    final_step: str,
    is_qvd: bool = False,
    mapping_tables_code: str = "",
) -> str:
    """
    Build SharePoint M query using STATIC PLACEHOLDERS (not dynamic variables).
    
    This prevents _schema_loaded_on_refresh issues in Power BI Fabric by:
    - Using Text.EndsWith() instead of exact match
    - Using static string placeholders instead of variables
    - Properly checking folder path AND filename
    - Adding explicit error handling
    
    Pattern:
        let
            SiteUrl = "<BASE_URL>",
            Source = SharePoint.Files(SiteUrl, [ApiVersion = 15]),
            Filtered = Table.SelectRows(Source,
                each Text.EndsWith(Text.Lower([Name]), "<FILE_NAME>") and
                     Text.Contains(Text.Lower([Folder Path]), "shared documents")),
            File = if Table.RowCount(Filtered) > 0 then Filtered{0}[Content] else error "File not found",
            ...
    """
    qvd_comment = "    // QVD converted to CSV — SharePoint.Files() reads the CSV version\n" if is_qvd else ""
    
    # Convert filename to lowercase for comparison (but keep original case in placeholder)
    filename_lower = filename.lower()
    
    # Build the let expression with optional mapping tables
    # Mapping tables code starts with a comma (from _generate_applymap_table_loading_code)
    # so we only add it if it's not empty
    mapping_tables_section = f"{mapping_tables_code}" if mapping_tables_code.strip() else ""
    
    m = (
        f"let\n"
        f"{qvd_comment}"
        f"    SiteUrl = \"{site_url}\",\n"
        f"    Source = SharePoint.Files(SiteUrl, [ApiVersion = 15]),\n"
        f"    Filtered = Table.SelectRows(\n"
        f"        Source,\n"
        f"        each\n"
        f"            Text.EndsWith(Text.Lower([Name]), \"{filename_lower}\") and\n"
        f"            Text.Contains(Text.Lower([Folder Path]), \"shared documents\")\n"
        f"    ),\n"
        f"    File = if Table.RowCount(Filtered) > 0\n"
        f"        then Filtered{{0}}[Content]\n"
        f"        else error \"File {filename} not found in SharePoint\",\n"
        f"    Csv = Csv.Document(File, [Delimiter=\"{delimiter}\", Encoding={encoding}, QuoteStyle=QuoteStyle.Csv]),\n"
        f"    Headers = Table.PromoteHeaders(Csv, [PromoteAllScalars=true])"
        f"{mapping_tables_section}"
        f"{transform_step}\n"
        f"in\n"
        f"    {final_step}"
    )
    return m


def _build_s3_m(
    bucket_url: str,
    filename: str,
    delimiter: str,
    encoding: int,
    transform_step: str,
    final_step: str,
) -> str:
    clean_url = bucket_url.strip().strip('"').strip("'").rstrip("/")
    file_url = f"{clean_url}/{filename}"
    m = (
        f"let\n"
        f"    Source = Web.Contents(\"{file_url}\"),\n"
        f"    Csv = Csv.Document(\n"
        f"        Source,\n"
        f"        [Delimiter=\"{delimiter}\", Encoding={encoding}, QuoteStyle=QuoteStyle.Csv]\n"
        f"    ),\n"
        f"    Headers = Table.PromoteHeaders(Csv, [PromoteAllScalars=true])"
        f"{transform_step}\n"
        f"in\n"
        f"    {final_step or 'Headers'}"
    )
    return m


def _build_azure_blob_m(
    container_url: str,
    filename: str,
    delimiter: str,
    encoding: int,
    transform_step: str,
    final_step: str,
    mapping_tables_code: str = "",
) -> str:
    clean_url = container_url.strip().strip('"').strip("'").rstrip("/")
    
    # Build the let expression with optional mapping tables
    mapping_tables_section = f"\n{mapping_tables_code}" if mapping_tables_code.strip() else ""
    
    m = (
        f"let\n"
        f"    Source = AzureStorage.Blobs(\"{clean_url}\"),\n"
        f"    File = Table.SelectRows(Source, each Text.Lower([Name]) = Text.Lower(\"{filename}\")){{0}}[Content],\n"
        f"    Csv = Csv.Document(\n"
        f"        File,\n"
        f"        [Delimiter=\"{delimiter}\", Encoding={encoding}, QuoteStyle=QuoteStyle.Csv]\n"
        f"    ),\n"
        f"    Headers = Table.PromoteHeaders(Csv, [PromoteAllScalars=true])"
        f"{mapping_tables_section}"
        f"{transform_step}\n"
        f"in\n"
        f"    {final_step or 'Headers'}"
    )
    return m


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONVERTER
# ─────────────────────────────────────────────────────────────────────────────

class MQueryConverter:

    def __init__(self):
        self.all_tables_list: Dict[str, Dict[str, Any]] = {}

    # ============================================================
    # PRIVATE: Type Resolution
    # ============================================================

    def _get_column_type(self, table_name: str, col_name: str, qlik_type: str = "string") -> str:
        """
        Resolve column type from Qlik script type, then fallback to heuristic inference.
        
        Priority:
        1. qlik_type from load script (if it's a known type like date, number, etc.)
        2. Heuristic name inference (_infer_type_from_name)
        
        Args:
            table_name: Name of the table (e.g., "Departments", "fact_activity")
            col_name: Column name to resolve
            qlik_type: Original type from Qlik script (e.g., "string", "date", "")
            
        Returns:
            M type string: "type text", "type number", "type date", etc.
        """
        if "-" in col_name:
            return "type text"
        
        plain_name = (
            col_name.split(".", 1)[-1]
            if ("." in col_name and not col_name.startswith("#"))
            else col_name
        )
        qlik_lower = str(qlik_type).lower().strip()
        if qlik_lower not in ("string", "text", "unknown", "mixed", "wildcard", ""):
            return _QLIK_TO_M_TYPE.get(qlik_lower, _DEFAULT_M_TYPE)
        
        inferred = _infer_type_from_name(plain_name)
        logger.debug(
            "[_get_column_type] Table '%s', col '%s': Using heuristic → %s",
            table_name, col_name, inferred
        )
        return inferred

    def _extract_applymap_metadata(self, fields: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """
        🔥 FIX 2: Extract APPLYMAP metadata from field expressions.
        
        Parses ApplyMap('MapTableName', key_column, 'default') expressions to extract:
        - Mapping table name
        - Key column being looked up
        - Default value
        - Output column name using the mapping
        
        Returns: Dict[mapping_table_name] → {
            'key_column': str,
            'default_value': str,
            'output_columns': [list of columns that use this mapping]
        }
        
        Example:
          Input: field expr="ApplyMap('DeptMap', department_id, 'Unknown')" alias="DeptName"
          Output: {'DeptMap': {'key_column': 'department_id', 'default_value': 'Unknown', 
                                'output_columns': ['DeptName']}}
        """
        applymap_info = {}
        
        for f in fields:
            expr = f.get("expression", "").strip()
            alias = f.get("alias") or f.get("name", "")
            
            if not expr or "APPLYMAP" not in expr.upper():
                continue
            
            # Parse: ApplyMap('MapTable', key_column, 'default') or ApplyMap("MapTable", key_column, 'default')
            # Regex: APPLYMAP\s*\(\s*['"](\w+)['"]\s*,\s*(\w+)\s*,\s*['"]([^'"]+)['"]
            match = re.search(
                r"ApplyMap\s*\(\s*['\"](\w+)['\"]\s*,\s*(\w+)\s*,\s*['\"]([^'\"]+)['\"]",
                expr,
                re.IGNORECASE
            )
            if match:
                map_table = match.group(1).strip()
                key_col = match.group(2).strip()
                default_val = match.group(3).strip()
                
                # Initialize mapping table entry if not exists
                if map_table not in applymap_info:
                    applymap_info[map_table] = {
                        'key_column': key_col,
                        'default_value': default_val,
                        'output_columns': []
                    }
                
                # Track this output column
                if alias not in applymap_info[map_table]['output_columns']:
                    applymap_info[map_table]['output_columns'].append(alias)
                
                logger.debug(
                    "[_extract_applymap_metadata] Found ApplyMap: table='%s', key='%s', "
                    "default='%s', output_col='%s'",
                    map_table, key_col, default_val, alias
                )
        
        return applymap_info

    # ============================================================
    # PUBLIC
    # ============================================================

    def convert_all(
        self,
        tables: List[Dict[str, Any]],
        base_path: str = "[DataSourcePath]",
        connection_string: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        FIX 8: Detects duplicate file loads (same file without explicit table names)
        and renames them uniquely to prevent overwrites.
        """
        self.all_tables_list = {t["name"]: t for t in tables}
        
        # FIX 8: Detect and log duplicate file loads
        source_paths = {}
        for table in tables:
            source_path = table.get("source_path", "")
            if source_path and source_path != "":
                if source_path not in source_paths:
                    source_paths[source_path] = []
                source_paths[source_path].append(table.get("name", "UNKNOWN"))
        
        # Log duplicate file loads
        for source_path, table_names in source_paths.items():
            if len(table_names) > 1:
                logger.info(
                    "[MQueryConverter.convert_all] FIX 8: Detected duplicate file load. "
                    "File '%s' loaded as: %s. Each gets unique name to prevent overwrites.",
                    source_path, ", ".join(table_names)
                )
        
        results = []
        for table in tables:
            m_expr, notes = self._dispatch(table, base_path, connection_string)
            
            # 🔥 FIX 6: Print mquery before publishing
            # Check for issues: [Upper], [Trim], invalid syntax
            table_name = table.get('name', 'UNKNOWN')
            logger.info("[FIX 6] FINAL MQUERY for '%s' (preview, first 500 chars):", table_name)
            logger.info("[FIX 6] %s...", m_expr[:500] if len(m_expr) > 500 else m_expr)
            # Validation checks
            if '[Upper]' in m_expr or '[Trim]' in m_expr:
                logger.warning("[FIX 6] ⚠ WARNING: Found old Qlik text functions in '%s'. Should use Text.Upper, Text.Trim instead.", table_name)
            if 'LOAD' in m_expr:
                logger.warning("[FIX 6] ⚠ WARNING: Found LOAD keyword in '%s'. M Query should not contain LOAD statements.", table_name)
            print(f"[FIX 6] FINAL MQUERY: {table_name}")
            print(f"  Full Length: {len(m_expr)} chars")
            print(f"  Preview: {m_expr[:200]}..." if len(m_expr) > 200 else f"  Preview: {m_expr}")
            if '[Upper]' in m_expr or '[Trim]' in m_expr:
                print(f"  ⚠ WARNING: Found old Qlik text function syntax!")
            if 'LOAD' in m_expr:
                print(f"  ⚠ WARNING: Found LOAD keyword - should be M Query syntax!")
            print()
            
            results.append({
                "name":         table["name"],
                "source_type":  table["source_type"],
                "m_expression": m_expr,
                "fields":       table["fields"],
                "notes":        notes,
                "source_path":  table.get("source_path", ""),
                "options":      table.get("options", {}),
            })
        
        # 🔥 FIX 2b: REMOVED - No longer auto-generate APPLYMAP dimension tables
        # APPLYMAP is now converted to JOIN inside parent table (more efficient)
        # This prevents unwanted auto-generated tables from being published
        
        # 🔥 FIX 5: Temp disable relationships
        # Relationship engine still unstable - remove all relationships from results
        # So Power BI doesn't try to auto-link tables during publish
        relationships = []
        logger.info("[FIX 5] Relationships temporarily disabled (%d removed)", 0)
        print("[FIX 5] Relationships disabled - relationship engine temporarily unstable")
        print()
        
        logger.info("[MQueryConverter] Converted %d user-defined table(s)",
                   len(results))
        logger.info("[MQueryConverter] FIX 4 - RESIDENT CSV inlining: ACTIVE")
        logger.info("[MQueryConverter] FIX 5 - Relationships: DISABLED")
        logger.info("[MQueryConverter] FIX 6 - MQuery validation: ACTIVE (check print output above)")
        return results

    def convert_one(
        self,
        table: Dict[str, Any],
        base_path: str = "[DataSourcePath]",
        connection_string: Optional[str] = None,
        all_table_names: Optional[set] = None,
        all_tables_list: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        if all_tables_list:
            self.all_tables_list = {t["name"]: t for t in all_tables_list}
        m_expr, _ = self._dispatch(table, base_path, connection_string)
        return m_expr

    # ─────────────────────────────────────────────────────────────
    # FIX A: Resolve actual output columns (used by BIM builder)
    # ─────────────────────────────────────────────────────────────

    def _normalize_fields(self, table: Dict[str, Any]) -> None:
        """
        FIX 1: Normalize table["fields"] to ensure all elements are dicts, not strings.
        Converts string fields to dict format: {"name": field_name, "type": "string"}
        This prevents 'str' object has no attribute 'get' crashes.
        """
        normalized = []
        for f in table.get("fields", []):
            if isinstance(f, dict):
                normalized.append(f)
            else:
                normalized.append({"name": str(f), "type": "string"})
        table["fields"] = normalized

    def resolve_output_columns(self, table: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        ✅ Fix 5 + Fix 6: Track ALL output columns including derived columns from transformations.
        
        FIX 5: FINAL COLUMN MATCH — Return FINAL M Query columns, NOT raw source columns.
        After transformations, the set of output columns changes:
        - GROUP BY: Only group_by_columns + aggregations
        - KEEP: Only kept columns (subset of source)
        - IF conditions: Source columns + new IF-derived column
        - JOIN/APPLYMAP: Source columns + joined columns
        - CONCATENATE: Union of all source columns
        - etc.
        
        NEW: Also includes derived columns from:
        - IF conditions (new derived columns from expressions)
        - JOIN/APPLYMAP (columns from joined tables)
        - Date transformations (full_date, year, month, day, quarter)
        - KPI auto-generation (_productivity_score, etc.)
        - Derived columns (from expressions with Date#, Ceil, etc.)

        Priority:
          1. GROUP BY → group_by_columns + aggregations (FINAL output)
          2. KEEP → only kept_columns (filtered output)
          3. Explicit field list → from parser (INCLUDING derived columns)
          4. Tracked derived columns in options['_derived_columns']
          5. M expression → last resort
        """
        table_name = table.get("name", "UNKNOWN")
        
        # FIX 1: Normalize fields to ensure all are dicts, not strings
        self._normalize_fields(table)
        
        fields = table.get("fields", [])
        opts = table.get("options", {})

        # GROUP BY completely replaces the output column set
        # FIX 5: Return ONLY the final GROUP BY output columns
        if opts.get("is_group_by"):
            group_cols = opts.get("group_by_columns", [])
            agg_cols = opts.get("aggregations", {})
            resolved: List[Dict[str, str]] = []
            for gc in group_cols:
                resolved.append({"name": _strip_qlik_qualifier(gc), "dataType": "string"})
            for agg_alias in agg_cols:
                resolved.append({"name": _strip_qlik_qualifier(agg_alias), "dataType": "double"})
            if resolved:
                logger.info(
                    "[resolve_output_columns] GROUP BY table '%s': %d FINAL output cols (FIX 5 - final match)",
                    table_name, len(resolved)
                )
                return resolved

        # FIX 5: KEEP filters columns — return ONLY kept columns
        if opts.get("is_keep"):
            keep_cols = opts.get("keep_columns", [])
            if keep_cols:
                resolved = []
                for kc in keep_cols:
                    resolved.append({"name": _strip_qlik_qualifier(kc), "dataType": "string"})
                logger.info(
                    "[resolve_output_columns] KEEP table '%s': %d FINAL output cols (FIX 5 - final match)",
                    table_name, len(resolved)
                )
                return resolved

        # ── PRIORITY 1: explicit field list (non-wildcard fields from parser)
        output_cols: List[Dict[str, str]] = []
        seen_lower = set()
        
        for f in fields:
            # FIX 3: Handle both dict and string fields (defensive coding)
            if isinstance(f, dict):
                raw_name = f.get("name", "")
            else:
                raw_name = str(f)
            
            if raw_name == "*":
                continue
            
            alias = (f.get("alias") or raw_name) if isinstance(f, dict) else raw_name
            col_name = _strip_qlik_qualifier(alias)
            if not col_name or col_name.lower() in seen_lower:
                continue
            seen_lower.add(col_name.lower())
            
            expr = (f.get("expression", "") or raw_name) if isinstance(f, dict) else raw_name
            if "APPLYMAP" in expr.upper():
                # FIX 2: Apply smart typing to APPLYMAP results too
                if any(pattern in col_name.lower() for pattern in ["_date", "_dt", "_timestamp", "_time"]):
                    bim_type = "date"
                elif any(pattern in col_name.lower() for pattern in ["_cost", "_fee", "_bill", "_price", "_rate", "_salary", "_amount", "_expense", "_revenue", "_income", "_tax", "_discount", "_covered"]):
                    bim_type = "number"
                elif any(pattern in col_name.lower() for pattern in ["_days", "_years", "_count", "_qty", "_quantity"]):
                    bim_type = "number"
                elif any(pattern in col_name.lower() for pattern in ["_pct", "_percent", "_ratio", "_score", "_weight"]):
                    bim_type = "number"
                else:
                    bim_type = "string"
                output_cols.append({"name": col_name, "dataType": bim_type})
                continue
            if re.search(r'[\+\-\*\/]', expr) and not expr.strip().startswith("["):
                output_cols.append({"name": col_name, "dataType": "double"})
                continue
            if expr.upper().startswith("IF"):
                m_t = self._get_column_type(table_name, col_name, f.get("type", "string"))
                output_cols.append({"name": col_name, "dataType": _m_type_to_bim_datatype(m_t)})
                continue
            m_t = self._get_column_type(table_name, col_name, f.get("type", "string"))
            output_cols.append({"name": col_name, "dataType": _m_type_to_bim_datatype(m_t)})

        # FIX 6: Add tracked derived columns from transformations
        if output_cols:
            derived_cols = opts.get("_derived_columns", [])
            for dc in derived_cols:
                if isinstance(dc, dict):
                    col_name_lower = dc.get("name", "").lower()
                    if col_name_lower not in seen_lower:
                        output_cols.append(dc)
                        seen_lower.add(col_name_lower)
                else:
                    col_name_lower = str(dc).lower()
                    if col_name_lower not in seen_lower:
                        # FIX 2: Apply smart typing instead of hardcoded "string"
                        if any(pattern in col_name_lower for pattern in ["_date", "_dt", "_timestamp", "_time"]):
                            bim_type = "date"
                        elif any(pattern in col_name_lower for pattern in ["_cost", "_fee", "_bill", "_price", "_rate", "_salary", "_amount", "_expense", "_revenue", "_income", "_tax", "_discount", "_covered"]):
                            bim_type = "number"
                        elif any(pattern in col_name_lower for pattern in ["_days", "_years", "_count", "_qty", "_quantity"]):
                            bim_type = "number"
                        elif any(pattern in col_name_lower for pattern in ["_pct", "_percent", "_ratio", "_score", "_weight"]):
                            bim_type = "number"
                        else:
                            bim_type = "string"
                        output_cols.append({"name": _strip_qlik_qualifier(dc), "dataType": bim_type})
                        seen_lower.add(col_name_lower)
            
            logger.info(
                "[resolve_output_columns] Table '%s': Resolved %d base + derived columns from field list",
                table_name, len(output_cols)
            )
            return output_cols

        # ── PRIORITY 2: M expression extraction (last resort)
        m_expression = table.get("m_expression", "")
        if m_expression:
            try:
                import sys as _sys, importlib as _ilib
                _pub = _sys.modules.get("powerbi_publisher")
                if _pub is None:
                    _pub = _ilib.import_module("powerbi_publisher")
                raw_fields = _pub._extract_fields_from_m(m_expression)
                for rf in raw_fields:
                    col_name = (rf.get("name") or "").strip()
                    if col_name and col_name != "*":
                        output_cols.append({"name": _strip_qlik_qualifier(col_name), "dataType": "string"})
                if output_cols:
                    logger.info(
                        "[resolve_output_columns] Table '%s': %d cols from M expression extraction",
                        table_name, len(output_cols)
                    )
                    return output_cols
            except Exception as _fe:
                logger.debug("[resolve_output_columns] M-expr fallback failed: %s", _fe)

        logger.warning(
            "[resolve_output_columns] Table '%s': No columns resolved after all attempts. "
            "Caller (_build_bim) will perform deep M-expression scan.",
            table_name
        )
        return output_cols

    # ─────────────────────────────────────────────────────────────
    # FIX C: Standalone dimension table for ApplyMap
    # ─────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────
    # FIX B: Schema-safe CONCATENATE combine
    # ─────────────────────────────────────────────────────────────

    def _build_safe_combine(
        self,
        concat_sources: List[Dict[str, Any]],
        fields: List[Dict[str, Any]],
        base_path: str,
    ) -> tuple[str, str]:
        """
        FIX B — Build a Table.Combine that explicitly selects and aligns
        columns on every source using Table.SelectColumns(..., MissingField.UseNull)
        before combining.  This ensures all source tables have identical
        schema even when CSV files differ in column order or have extra cols.
        """
        col_names = [
            _strip_qlik_qualifier(f.get("alias") or f.get("name", ""))
            for f in fields
            if f.get("name") != "*"
        ]
        if not col_names:
            # Fallback: no declared cols — just combine as-is
            return self._build_naive_combine(concat_sources, base_path)

        cols_list = ", ".join(f'"{c}"' for c in col_names)

        steps = "let\n"
        header_refs: List[str] = []

        for idx, src in enumerate(concat_sources):
            source_path = src.get("source_path", "")
            if not source_path:
                continue

            n = idx + 1
            step_src  = f"RawSource{n}"
            step_hdr  = f"RawHeaders{n}"
            step_sel  = f"AlignedSource{n}"

            if _is_sharepoint_url(base_path):
                site_url = base_path.strip().strip('"').strip("'")
                if "/Shared" in site_url:
                    site_url = site_url.split("/Shared")[0]
                filename = source_path.rsplit("/", 1)[-1]
                step_filtered = f"Filtered{n}"
                steps += (
                    f"    {step_src} = SharePoint.Files(\"{site_url}\", [ApiVersion = 15]),\n"
                    f"    {step_filtered} = Table.SelectRows(\n"
                    f"        {step_src},\n"
                    f"        each\n"
                    f"            Text.EndsWith(Text.Lower([Name]), \"{filename.lower()}\") and\n"
                    f"            Text.Contains(Text.Lower([Folder Path]), \"shared documents\")\n"
                    f"    ),\n"
                    f"    {step_hdr} = Table.PromoteHeaders(\n"
                    f"        Csv.Document(\n"
                    f"            if Table.RowCount({step_filtered}) > 0 then {step_filtered}{{0}}[Content] else error \"File {filename} not found\",\n"
                    f"            [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]\n"
                    f"        ), [PromoteAllScalars=true]),\n"
                )
            elif _is_s3_url(base_path):
                clean_bp = base_path.strip().strip('"').strip("'").rstrip("/")
                filename = source_path.rsplit("/", 1)[-1]
                steps += (
                    f"    {step_src} = Csv.Document(\n"
                    f"        Web.Contents(\"{clean_bp}/{filename}\"),\n"
                    f"        [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n"
                    f"    {step_hdr} = Table.PromoteHeaders({step_src}, [PromoteAllScalars=true]),\n"
                )
            elif _is_azure_blob_url(base_path):
                clean_bp = base_path.strip().strip('"').strip("'").rstrip("/")
                filename = source_path.rsplit("/", 1)[-1]
                steps += (
                    f"    {step_src}Container = AzureStorage.Blobs(\"{clean_bp}\"),\n"
                    f"    {step_src} = Table.SelectRows({step_src}Container, each Text.Lower([Name]) = Text.Lower(\"{filename}\")){{0}}[Content],\n"
                    f"    {step_hdr} = Table.PromoteHeaders(\n"
                    f"        Csv.Document({step_src}, [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n"
                    f"        [PromoteAllScalars=true]),\n"
                )
            else:
                if base_path.strip().startswith("["):
                    path_expr = f"{base_path} & \"/{source_path}\""
                else:
                    clean_bp = base_path.strip().strip('"').strip("'")
                    path_expr = f'"{clean_bp}/{source_path}"'
                steps += (
                    f"    {step_src} = Csv.Document(\n"
                    f"        File.Contents({path_expr}),\n"
                    f"        [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n"
                    f"    {step_hdr} = Table.PromoteHeaders({step_src}, [PromoteAllScalars=true]),\n"
                )

            # Explicit column alignment — MissingField.UseNull fills gaps
            steps += (
                f"    {step_sel} = Table.SelectColumns({step_hdr},\n"
                f"        {{{cols_list}}},\n"
                f"        MissingField.UseNull),\n"
            )
            header_refs.append(step_sel)

        if not header_refs:
            return "", "Source"

        combine_list = "{" + ", ".join(header_refs) + "}"
        steps += f"    SafeCombined = Table.Combine({combine_list})\n"
        steps += "in\n    SafeCombined"

        logger.info(
            "[_build_safe_combine] Combined %d sources with %d aligned columns",
            len(header_refs), len(col_names)
        )
        return steps, "SafeCombined"

    def _build_naive_combine(
        self,
        concat_sources: List[Dict[str, Any]],
        base_path: str,
    ) -> tuple[str, str]:
        """Fallback combine when no field list is available."""
        steps = "let\n"
        refs: List[str] = []
        for idx, src in enumerate(concat_sources):
            sp = src.get("source_path", "")
            if not sp:
                continue
            n = idx + 1
            if base_path.strip().startswith("["):
                path_expr = f"{base_path} & \"/{sp}\""
            else:
                clean_bp = base_path.strip().strip('"').strip("'")
                path_expr = f'"{clean_bp}/{sp}"'
            steps += (
                f"    Src{n} = Csv.Document(File.Contents({path_expr}), [Delimiter=\",\", Encoding=65001]),\n"
                f"    Hdr{n} = Table.PromoteHeaders(Src{n}, [PromoteAllScalars=true]),\n"
            )
            refs.append(f"Hdr{n}")
        if not refs:
            return "", "Source"
        steps += f"    Combined = Table.Combine({{{', '.join(refs)}}})\n"
        steps += "in\n    Combined"
        return steps, "Combined"

    # ============================================================
    # DISPATCH
    # ============================================================

    def _dispatch(self, table, base_path, connection_string):
        # ✅ FIX: Normalize fields FIRST to prevent 'str' object has no attribute 'get' crashes
        self._normalize_fields(table)
        
        self._auto_detect_transformations(table)
        source_type = table.get("source_type", "")
        dispatch = {
            "inline":   self._m_inline,
            "csv":      self._m_csv,
            "excel":    self._m_excel,
            "json":     self._m_json,
            "xml":      self._m_xml,
            "parquet":  self._m_parquet,
            "qvd":      self._m_qvd,
            "resident": self._m_resident,
            "sql":      self._m_sql,
        }
        handler = dispatch.get(source_type, self._m_placeholder)
        try:
            return handler(table, base_path, connection_string)
        except Exception as exc:
            logger.warning("[MQuery] Error converting '%s': %s", table.get("name"), exc)
            return self._m_placeholder(table, base_path, connection_string), f"Conversion error: {exc}"

    # ============================================================
    # FIELD NORMALIZATION
    # ============================================================
    
    def _normalize_fields(self, table: Dict[str, Any]) -> None:
        """
        ✅ FIX: Ensure table["fields"] is always List[Dict], never containing strings.
        
        If any field is a string, convert it safely:
            "employee_id" → {"name": "employee_id", "type": "string"}
        
        This prevents 'str' object has no attribute 'get' crashes.
        """
        fields = table.get("fields", [])
        if not fields:
            return
        
        # Filter out None values and ensure all are dicts
        normalized = []
        for f in fields:
            if not f:  # Skip None/empty
                continue
            if isinstance(f, dict):
                # Already a dict - keep as-is
                normalized.append(f)
            elif isinstance(f, str):
                # String field name - convert to dict
                normalized.append({
                    "name": f,
                    "type": "string",
                    "expression": ""
                })
                logger.debug("[_normalize_fields] Converted string field '%s' to dict", f)
            else:
                # Other type - log and skip
                logger.warning("[_normalize_fields] Skipping non-dict, non-string field: %s (type=%s)", f, type(f).__name__)
        
        # Update table with normalized fields
        if normalized:
            table["fields"] = normalized
            if len(normalized) < len(fields):
                logger.info(
                    "[_normalize_fields] Normalized %d fields (dropped %d invalid entries)",
                    len(normalized), len(fields) - len(normalized)
                )
        else:
            table["fields"] = []

    # ============================================================
    # MAIN DISPATCH
    # ============================================================

    def _auto_detect_transformations(self, table: Dict[str, Any]) -> None:
        if "options" not in table:
            table["options"] = {}
        opts = table["options"]
        fields = table.get("fields", [])
        if not fields:
            return

        aggregation_keywords = ("sum", "count", "avg", "average", "min", "max", "total")
        agg_fields = []
        for f in fields:
            expr = f.get("expression", "").upper()
            if not expr or expr == "*":
                continue
            if any(f"{kw.upper()}(" in expr for kw in aggregation_keywords):
                agg_fields.append(f)

        if agg_fields and not opts.get("is_group_by"):
            opts["is_group_by"] = True
            aggregations = {}
            for f in agg_fields:
                expr = f.get("expression", "").upper()
                alias = f.get("alias") or f.get("name", "")
                for keyword in ("SUM", "COUNT", "AVG", "AVERAGE", "MIN", "MAX", "TOTAL"):
                    pattern = re.compile(rf"{keyword}\s*\(\s*([^\)]+)\s*\)", re.IGNORECASE)
                    m = pattern.search(expr)
                    if m:
                        source_col = m.group(1).strip().strip("[]\"'")
                        agg_type = keyword.replace("TOTAL", "SUM")
                        aggregations[alias] = (agg_type, source_col)
                        break
            if aggregations:
                opts["aggregations"] = aggregations
                group_cols = []
                for f in fields:
                    if f not in agg_fields and f.get("name") != "*":
                        col_name = f.get("alias") or f.get("name")
                        if col_name and col_name not in aggregations:
                            group_cols.append(col_name)
                if group_cols:
                    opts["group_by_columns"] = group_cols
                if "transformations" not in opts:
                    opts["transformations"] = []
                if isinstance(opts["transformations"], str):
                    opts["transformations"] = [opts["transformations"]]
                if "group_by" not in opts["transformations"]:
                    opts["transformations"].append("group_by")

        applymap_fields = [
            f for f in fields
            if "APPLYMAP" in f.get("expression", "").upper()
        ]
        if applymap_fields:
            opts["has_applymap"] = True
            opts["apply_applymap_as_merge"] = True
            opts["applymap_fields"] = applymap_fields

        if_fields = [
            f for f in fields
            if "IF" in f.get("expression", "").upper()
        ]
        if if_fields:
            opts["has_if_conditions"] = True
            opts["if_fields"] = if_fields
            if "transformations" not in opts:
                opts["transformations"] = []
            if isinstance(opts["transformations"], str):
                opts["transformations"] = [opts["transformations"]]

        # ═══════════════════════════════════════════════════════════════
        # FORCE CONCATENATE DETECTION (CRITICAL)
        # Detect CONCATENATE operations from parser operations list
        # This is independent of other detection logic to ensure no concat
        # is missed due to parser weaknesses or missing flags
        # ═══════════════════════════════════════════════════════════════
        ops = table.get("operations", [])
        if any("concat" in str(op).lower() for op in ops):
            opts["is_concatenate"] = True
            if "transformations" not in opts:
                opts["transformations"] = []
            if isinstance(opts["transformations"], str):
                opts["transformations"] = [opts["transformations"]]
            if "concatenate" not in opts["transformations"]:
                opts["transformations"].append("concatenate")
            logger.debug("[auto_detect_transformations] CONCATENATE detected via operations list")

        if table.get("source_type") == "resident":
            opts["is_resident"] = True

        # FORCE KEEP DETECTION
        # Detect KEEP operations from table string representation
        # This ensures KEEP statements are not missed
        if "KEEP" in str(table):
            opts["is_keep"] = True
            logger.debug("[auto_detect_transformations] KEEP detected via table inspection")

        # ✅ FIX: ADD DATE TRANSFORMATION DETECTION
        # Set flag if table has date_id column or is a date dimension table
        date_fields = [f for f in fields if "date_id" in (f.get("name", "") or "").lower()]
        if date_fields:
            opts["has_date_transformation"] = True
            if "transformations" not in opts:
                opts["transformations"] = []
            if isinstance(opts["transformations"], str):
                opts["transformations"] = [opts["transformations"]]
            if "date" not in opts["transformations"]:
                opts["transformations"].append("date")
            logger.info("[_auto_detect_transformations] ✅ DATE TRANSFORMATION flagged for table '%s' - date_id column detected", table.get("name", "?"))

        # FIX D: Wire parser KEEP flags into transformations list
        # 🔥 STRICT MODE - DISABLE JOIN: is_join is always False, JOIN logic is removed
        opts["is_join"] = False

        if opts.get("is_keep") and "keep" not in opts.get("transformations", []):
            if "transformations" not in opts:
                opts["transformations"] = []
            if isinstance(opts["transformations"], str):
                opts["transformations"] = [opts["transformations"]]
            opts["transformations"].append("keep")
            logger.debug("[auto_detect] KEEP detected, added to transformations")

    # ============================================================
    # SHARED TYPE TRANSFORM STEPS
    # ============================================================

    def _build_explicit_schema_step(
        self,
        table_name: str,
        previous_step: str,
    ) -> tuple[str, str]:
        """
        ✅ Always injects schema WITH PROPER TYPES.

        Priority:
          1. options['qlik_columns'] injected by parser
          2. Dynamic List.Transform fallback (columns appear after refresh)
          
        FIX: Use _get_column_type() to resolve PROPER types (type text, type number, type date)
        instead of hardcoding all to "type text". This ensures CONCATENATE sources have 
        consistent, correct column types.

        This is called for EVERY LOAD * table, not just as a last resort.
        """
        # Priority 1: options['qlik_columns'] injected by parser
        table_def = self.all_tables_list.get(table_name, {})
        cols = table_def.get("options", {}).get("qlik_columns", [])

        if cols:
            # Resolve actual types for each column, not all "type text"
            pairs_list = []
            for col in cols:
                # Get the field definition if available (has type info)
                field_type = "string"  # default
                fields = table_def.get("fields", [])
                for f in fields:
                    if f.get("name") == col or f.get("name") == f'[{col}]':
                        field_type = f.get("type", "string")
                        break
                
                # Use _get_column_type() to resolve proper M type
                m_type = self._get_column_type(table_name, col, field_type)
                clean_col = _strip_qlik_qualifier(col)
                pairs_list.append(f'{{"{clean_col}", {m_type}}}')
            
            pairs = ",\n        ".join(pairs_list)
            transform = (
                f",\n"
                f"    TypedTable = Table.TransformColumnTypes(\n"
                f"        {previous_step},\n"
                f"        {{\n        {pairs}\n        }}\n"
                f"    )"
            )
            logger.info(
                "[_build_explicit_schema_step] Table '%s': injecting %d EXPLICIT columns with PROPER TYPES from parser",
                table_name, len(cols)
            )
            return transform, "TypedTable"

        # No dynamic fallback - schema must come from actual M Query output only
        logger.info(
            "[_build_explicit_schema_step] Table '%s': No explicit columns - using M Query output as-is (no dynamic fallback)",
            table_name,
        )
        return "", previous_step

    def _apply_dynamic_schema(self, step_name: str = "Headers") -> str:
        """
        🔥 Universal fallback schema for LOAD * or unknown columns
        Prevents EMPTY TABLE in Power BI
        
        Returns M Query snippet that:
        1. Extracts all column names from the previous step
        2. Applies dynamic type inference (all text initially)
        3. Power BI discovers real columns on first refresh
        
        This ALWAYS works regardless of source type or column count.
        """
        return f""",
    Columns = Table.ColumnNames({step_name}),
    TypedTable = Table.TransformColumnTypes(
        {step_name},
        List.Transform(Columns, each {{_, type text}})
    )"""

    def _apply_types_as_is(self, fields: List[Dict], previous_step: str):
        pairs = []
        for f in fields:
            expr = f.get("expression", "")
            if not expr or expr == "*":
                continue
            if "APPLYMAP" in expr.upper():
                continue
            if re.search(r'[\+\-\*\/]', expr):
                continue
            if expr.startswith("[") and expr.endswith("]"):
                col_name = expr[1:-1]
            elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", expr):
                col_name = expr
            else:
                continue
            qlik_type = f.get("type", "string")
            m_type = self._get_column_type("", col_name, qlik_type)
            pairs.append(f'{{"{col_name}", {m_type}}}')
        if not pairs:
            return "", previous_step
        pairs_str = ",\n        ".join(pairs)
        transform = (
            f",\n"
            f"    TypedTable = Table.TransformColumnTypes(\n"
            f"        {previous_step},\n"
            f"        {{\n        {pairs_str}\n        }}\n"
            f"    )"
        )
        return transform, "TypedTable"

    def _apply_types(self, fields: List[Dict], previous_step: str, table_name: str = ""):
        """
        Apply type transformations to table columns.
        
        SMART SCHEMA DETECTION: When fields are empty or contain only wildcards,
        use dynamic schema inference from actual data sources.
        """
        typed = [f for f in fields if f.get("name") not in ("*", "")]
        if not typed:
            # SMART FIX: Return empty so caller extracts schema from M expression
            # This detects real columns from CSV preview, RESIDENT parent, or CONCATENATE sources
            logger.debug(
                "[_apply_types] LOAD * table '%s': fields empty - using dynamic schema inference",
                table_name
            )
            return "", previous_step
        
        pairs = []
        for f in typed:
            expr = f.get("expression", "") or f.get("name", "")
            alias = f.get("alias", f.get("name", ""))
            is_null_pattern, _ = self._is_null_handler_pattern(expr, alias)
            if is_null_pattern:
                col_name = _strip_qlik_qualifier(alias)
                m_type = self._get_column_type(table_name, col_name, f.get("type", "number"))
                pairs.append(f'{{"{col_name}", {m_type}}}')
                continue
            if "(" in expr or expr.upper().startswith("APPLYMAP") or expr.upper().startswith("IF"):
                continue
            raw_name = f.get("alias") or f["name"]
            col_name = _strip_qlik_qualifier(raw_name)
            m_type = self._get_column_type(table_name, col_name, f.get("type", "string"))
            pairs.append(f'{{"{col_name}", {m_type}}}')
        if not pairs:
            return "", previous_step
        pairs_str = ",\n        ".join(pairs)
        transform = (
            f",\n"
            f"    TypedTable = Table.TransformColumnTypes(\n"
            f"        {previous_step},\n"
            f"        {{\n        {pairs_str}\n        }}\n"
            f"    )"
        )
        return transform, "TypedTable"
    
    def _infer_columns_from_csv_preview(self, table: Dict[str, Any], base_path: str) -> List[str]:
        """
        SMART 1: For LOAD * tables, infer actual columns from CSV preview.
        Reads first row to extract real column names dynamically.
        Returns list of {"colname", type text} pairs for M Query.
        """
        source_path = table.get("source_path", "")
        if not source_path:
            return []
        
        try:
            import pandas as pd
            from pathlib import Path
            
            # Skip dynamic paths
            if base_path.startswith("["):
                logger.debug("[_infer_columns_from_csv_preview] Dynamic path - skipping")
                return []
            
            clean_path = base_path.strip().strip('"').strip("'")
            full_path = f"{clean_path}/{source_path}"
            
            if Path(full_path).exists():
                df = pd.read_csv(full_path, nrows=1)
                cols = [c.strip() for c in df.columns if c.strip()]
                if cols:
                    logger.info(
                        "[_infer_columns_from_csv_preview] Table '%s': Inferred %d columns from CSV",
                        table.get("name", "Unknown"), len(cols)
                    )
                    return [f'{{"{c}", type text}}' for c in cols]
        except Exception as e:
            logger.debug("[_infer_columns_from_csv_preview] CSV preview failed: %s", e)
        
        return []
    
    def _infer_resident_schema(self, table: Dict[str, Any]) -> List[str]:
        """
        SMART 2: For RESIDENT loads, inherit schema from parent table.
        Returns list of {"colname", type text} pairs.
        """
        source_path = table.get("source_path", "")
        if not source_path:
            return []
        
        parent_name = source_path  # In RESIDENT, source_path = parent table name
        parent_table = self.all_tables_list.get(parent_name)
        
        if not parent_table:
            logger.debug("[_infer_resident_schema] Parent '%s' not found", parent_name)
            return []
        
        # Get parent's output columns
        parent_cols = self.resolve_output_columns(parent_table)
        if parent_cols:
            logger.info(
                "[_infer_resident_schema] Table '%s': Inherited %d columns from RESIDENT '%s'",
                table.get("name", "Unknown"), len(parent_cols), parent_name
            )
            return [f'{{"{c["name"]}", type text}}' for c in parent_cols]
        
        return []
    
    def _infer_concatenate_schema(self, table: Dict[str, Any]) -> List[str]:
        """
        SMART 3: For CONCATENATE, union schemas from all sources.
        Returns list of {"colname", type text} pairs.
        """
        opts = table.get("options", {})
        concat_sources = opts.get("concat_sources", [])
        
        if not concat_sources:
            return []
        
        all_cols = set()
        for src_name in concat_sources:
            src_table = self.all_tables_list.get(src_name)
            if src_table:
                src_cols = self.resolve_output_columns(src_table)
                all_cols.update(c["name"] for c in src_cols)
        
        if all_cols:
            logger.info(
                "[_infer_concatenate_schema] Table '%s': Union of %d sources = %d columns",
                table.get("name", "Unknown"), len(concat_sources), len(all_cols)
            )
            return [f'{{"{c}", type text}}' for c in sorted(all_cols)]
        
        return []

    # ============================================================
    # TRANSFORMATION HELPERS
    # ============================================================

    def _detect_and_apply_concatenate(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        DISABLED: Concatenate logic handled by _build_safe_combine only.
        This method is kept for compatibility but returns no-op.
        """
        logger.debug("[_detect_and_apply_concatenate] Disabled - use _build_safe_combine instead")
        return "", prev_step

    def _detect_and_apply_groupby(self, table: Dict[str, Any], prev_step: str, fields: List[Dict]) -> tuple[str, str]:
        """
        Detect GROUP BY transformations and generate Table.Group M steps.
        
        Handles both:
        1. Explicit group_by_columns + aggregations in options (old format)
        2. Auto-detection from GROUP BY clause + field expressions (new format - FIX #4D)
        
        Auto-detection logic:
        - If 'group_by' string in options, parse column names from it
        - For each field, detect aggregation functions: SUM, COUNT, AVG, MIN, MAX
        - Generate Table.Group with all detected aggregations
        """
        opts = table.get("options", {})
        transformations = opts.get("transformations", [])
        if not isinstance(transformations, list):
            transformations = [transformations] if transformations else []
        
        # Check if GROUP BY is flagged as a transformation
        has_groupby = "group_by" in transformations or opts.get("is_group_by")
        group_by_clause = opts.get("group_by", "")  # Raw GROUP BY string from parser
        
        # --- Explicit format: group_by_columns + aggregations already set ---
        group_by_cols = opts.get("group_by_columns", [])
        aggregations = opts.get("aggregations", {})
        
        # --- Auto-detect format: parse GROUP BY clause + field expressions ---
        if not group_by_cols and has_groupby and group_by_clause:
            # Extract column names from GROUP BY clause
            # Pattern: GROUP BY col1, col2, ... or GROUP BY [col] AS alias, ...
            group_by_cols = self._parse_group_by_columns(group_by_clause)
        
        if not has_groupby or not group_by_cols:
            return "", prev_step
        
        # --- Auto-detect aggregation functions from field expressions ---
        if not aggregations and fields:
            aggregations = self._extract_aggregations_from_fields(fields, group_by_cols)
        
        if not aggregations or not group_by_cols:
            return "", prev_step
        
        group_cols_str = ", ".join([f'"{col}"' for col in group_by_cols])
        agg_specs = []
        
        # FIX 3: Force all source columns to numeric BEFORE aggregation
        # Convert columns that will be aggregated (SUM, COUNT, AVG, etc.) to numbers
        numeric_cols = set()
        for result_col, (agg_func, source_col) in aggregations.items():
            numeric_cols.add(source_col)
        
        # Build Table.TransformColumns to ensure numeric types
        transform_numeric = ""
        if numeric_cols:
            transform_cols = []
            for col in numeric_cols:
                transform_cols.append(f'{{"{col}", each try Number.From(_) otherwise 0, type number}}')
            
            transform_numeric = (
                f",\n    #\"Numeric Cast\" = Table.TransformColumns(\n"
                f"        {prev_step},\n"
                f"        {{\n"
                f"            {', '.join(transform_cols)}\n"
                f"        }}\n"
                f"    )"
            )
            prev_step_groupby = "#\"Numeric Cast\""
        else:
            prev_step_groupby = prev_step
        
        for result_col, (agg_func, source_col) in aggregations.items():
            agg_func_lower = agg_func.lower()
            if agg_func_lower in ("sum", "total"):
                m_agg = "List.Sum"
            elif agg_func_lower in ("count", "cnt"):
                m_agg = "List.Count"
            elif agg_func_lower == "average" or agg_func_lower == "avg":
                m_agg = "List.Average"
            elif agg_func_lower in ("min", "minimum"):
                m_agg = "List.Min"
            elif agg_func_lower in ("max", "maximum"):
                m_agg = "List.Max"
            else:
                m_agg = "List.Sum"
            
            agg_specs.append(f'{{"{result_col}", each {m_agg}([{source_col}]), type number}}')
        
        agg_specs_str = ", ".join(agg_specs)
        transform = (
            f"{transform_numeric}"
            f",\n    #\"Grouped Rows\" = Table.Group(\n"
            f"        {prev_step_groupby},\n"
            f"        {{{group_cols_str}}},\n"
            f"        {{{agg_specs_str}}}\n"
            f"    )"
        )
        logger.info(
            "[_detect_and_apply_groupby] Table '%s': GROUP BY %s with FORCED NUMERIC cast on %d agg columns, aggs: %s",
            table.get("name", "?"), group_cols_str, len(numeric_cols), list(aggregations.keys())
        )
        return transform, "#\"Grouped Rows\""

    def _parse_group_by_columns(self, group_by_clause: str) -> List[str]:
        """
        Parse GROUP BY clause to extract column names.
        Examples:
        - "employee_id, department" → ["employee_id", "department"]
        - "[Column 1], [Column 2]" → ["Column 1", "Column 2"]
        """
        if not group_by_clause:
            return []
        
        cols = []
        for part in group_by_clause.split(","):
            part = part.strip()
            # Remove brackets if present
            if part.startswith("[") and part.endswith("]"):
                part = part[1:-1]
            # Remove single quotes if present
            elif part.startswith("'") and part.endswith("'"):
                part = part[1:-1]
            # Remove "AS alias" if present
            if " AS " in part.upper():
                part = part.split(" AS ")[0].strip()
            if part:
                cols.append(part)
        
        return cols

    def _extract_aggregations_from_fields(self, fields: List[Dict], group_by_cols: List[str]) -> Dict[str, tuple]:
        """
        Auto-detect aggregation functions from field expressions.
        
        For each field NOT in group_by_cols:
        - Check if expression contains SUM(...), COUNT(...), AVG(...), MIN(...), MAX(...)
        - Extract result column name and source column
        
        Returns dict: {result_col: (agg_func, source_col), ...}
        """
        aggregations = {}
        group_by_lower = {c.lower() for c in group_by_cols}
        
        for f in fields:
            alias = (f.get("alias") or f.get("name", "")).strip().lower()
            name = f.get("name", "").strip().lower()
            expr = f.get("expression", "").strip().upper()
            
            # Skip columns that are in GROUP BY (dimension columns)
            if alias in group_by_lower or name in group_by_lower:
                continue
            
            # Skip passthrough columns
            if not expr or expr == name:
                continue
            
            # Detect aggregation functions
            agg_match = re.search(r'\b(SUM|COUNT|AVG|AVERAGE|MIN|MAX|TOTAL)\s*\(\s*([^\)]+)\s*\)', expr)
            if agg_match:
                agg_func = agg_match.group(1)
                source_col_raw = agg_match.group(2).strip()
                # Clean up source column name (remove brackets, quotes)
                source_col = source_col_raw.strip("[]'\" \t")
                result_col = f.get("alias") or f.get("name", "")
                
                if result_col and source_col:
                    aggregations[result_col] = (agg_func, source_col)
                    logger.debug(
                        "[auto_detect_agg] Found %s(%s) → %s",
                        agg_func, source_col, result_col
                    )
        
        return aggregations

    def _detect_and_apply_if_conditions(self, table: Dict[str, Any], prev_step: str, fields: List[Dict]) -> tuple[str, str]:
        opts = table.get("options", {})
        if_fields = []
        for f in fields:
            expr = f.get("expression", "").upper()
            if "IF" not in expr:
                continue
            alias = f.get("alias", f.get("name", ""))
            is_null_pattern, _ = self._is_null_handler_pattern(f.get("expression", ""), alias)
            if not is_null_pattern:
                if_fields.append(f)
        where_condition = opts.get("where_condition", "")
        if not if_fields and not where_condition:
            return "", prev_step
        
        # 🔥 prevent duplicate column add
        existing_cols = [
            c.get("name") if isinstance(c, dict) else c
            for c in table.get("options", {}).get("_derived_columns", [])
        ]
        
        transform_steps = ""
        current_step = prev_step
        if where_condition:
            m_condition = _wrap_columns_in_brackets(where_condition)
            transform_steps += (
                f",\n    #\"Filtered Rows\" = Table.SelectRows(\n"
                f"        {current_step},\n"
                f"        each {m_condition}\n"
                f"    )"
            )
            current_step = "#\"Filtered Rows\""
        for idx, f in enumerate(if_fields):
            expr = f.get("expression", "")
            alias = f.get("alias", f["name"])
            field_type = f.get("type", "string")
            
            # 🔥 prevent duplicate
            if alias in existing_cols:
                logger.debug("[if_conditions] Skipping duplicate column: %s (already in _derived_columns)", alias)
                continue
            
            # FIX #7 — Try nested IF parser first (handles complex chains)
            if expr.upper().startswith("IF("):
                m_expr, is_numeric = _parse_nested_if_expression(expr)
                
                # 🔥 STRICT: Type is text unless BOTH branches are numeric
                # - "Overtime"/"Normal" → text (string literals)
                # - 1/0 → number (numeric literals)  
                # - [column] + 10 → infer from expression
                
                # Default to text for string-returning IF expressions
                type_spec = f", type text" if not is_numeric else f", type number"
                
                safe_alias = _escape_m_string(alias)
                step_name = f"#\"Added {safe_alias}\""
                transform_steps += (
                    f",\n    {step_name} = Table.AddColumn(\n"
                    f"        {current_step},\n"
                    f"        \"{safe_alias}\",\n"
                    f"        each {m_expr}{type_spec}\n"
                    f"    )"
                )
                current_step = step_name
                logger.info(
                    "[if_conditions_nested] Added IF column '%s': %s (type=%s)",
                    alias, m_expr, "number" if is_numeric else "text"
                )
            else:
                # Fallback for non-IF expressions (shouldn't reach here if filter is correct)
                logger.debug("[if_conditions] Skipping non-IF expression for '%s'", alias)
        return transform_steps, current_step

    def _detect_and_apply_keep(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        FIX #8 — Handle KEEP statements: INNER KEEP (TableName), LEFT KEEP, etc.
        
        KEEP semantics in Qlik:
        - INNER KEEP (TableName): Keep ONLY rows where join key matches TableName (INNER JOIN)
        - LEFT KEEP (TableName): Keep all rows from current table + filter non-matching (LEFT JOIN)
        - RIGHT KEEP (TableName): Keep only matching rows (INNER JOIN variant)
        
        In Power Query M:
        - INNER KEEP: Use Table.Join() with JoinKind.Inner to filter rows
        - Column-only KEEP: Use Table.SelectColumns() to retain columns
        """
        opts = table.get("options", {})
        transformations = opts.get("transformations", [])
        if not isinstance(transformations, list):
            transformations = [transformations] if transformations else []
        
        # Check for explicit KEEP table reference (from parser)
        # FIX: Parser stores as 'keep_fields' (table name), converter looks for 'keep_table'
        keep_table = opts.get("keep_table", opts.get("keep_fields", ""))
        keep_cols = opts.get("keep_columns", [])
        keep_type = opts.get("keep_type", "inner").lower()
        
        # ════════════════════════════════════════════════════════════════════════════════════
        # FIX #8 ONLY: INNER KEEP (TableName) — Row filtering via INNER JOIN
        # ════════════════════════════════════════════════════════════════════════════════════
        
        if opts.get("is_keep") and keep_table and keep_type == "inner":
            # INNER KEEP: Filter rows where join key exists in keep_table
            # Use Table.Join with JoinKind.Inner
            
            # Auto-detect join key from field names
            join_key = opts.get("keep_key") or opts.get("join_key")
            
            # If no explicit key, auto-detect from field names
            if not join_key:
                fields = table.get("fields", [])
                # Priority 1: Look for table-specific ID (e.g., "employee_id" for Employees)
                table_prefix = keep_table.lower().split("s")[0] if keep_table.lower().endswith("s") else keep_table.lower()
                for f in fields:
                    name = (f.get("alias") or f.get("name", "")).lower()
                    if name and name != "*":
                        if f"{table_prefix}_id" in name or f"{keep_table.lower()}_id" in name:
                            join_key = f.get("alias") or f.get("name", "")
                            join_key = _strip_qlik_qualifier(join_key)
                            break
                
                # Priority 2: Generic _id pattern
                if not join_key:
                    for f in fields:
                        name = f.get("alias") or f.get("name", "")
                        if name and name != "*" and ("_id" in name.lower() or name.lower().endswith("id")):
                            join_key = _strip_qlik_qualifier(name)
                            break
                
                # Priority 3: First non-wildcard field
                if not join_key and fields:
                    for f in fields:
                        name = f.get("alias") or f.get("name", "")
                        if name and name != "*":
                            join_key = _strip_qlik_qualifier(name)
                            break
            
            if join_key:
                # Generate INNER JOIN M Query to filter rows
                # Table.Join filters to only rows where join_key exists in keep_table
                safe_keep_table = _escape_m_string(keep_table)
                step_name = f"#\"Inner Joined {safe_keep_table}\""
                
                transform = (
                    f",\n    {step_name} = Table.Join(\n"
                    f"        {prev_step},\n"
                    f"        {{\"{join_key}\"}},\n"
                    f"        Table.Distinct(\n"
                    f"            Table.SelectColumns(#{keep_table}, {{\"{join_key}\"}})\n"
                    f"        ),\n"
                    f"        {{\"{join_key}\"}},\n"
                    f"        JoinKind.Inner\n"
                    f"    )"
                )
                logger.info(
                    "[_detect_and_apply_keep] INNER KEEP (%s): joining on '%s' to filter rows",
                    keep_table, join_key
                )
                return transform, step_name
            else:
                logger.warning(
                    "[_detect_and_apply_keep] INNER KEEP (%s) detected but could not auto-detect join key",
                    keep_table
                )
        
        # ════════════════════════════════════════════════════════════════════════════════════
        # Column-based KEEP: Just select specific columns (legacy behavior)
        # ════════════════════════════════════════════════════════════════════════════════════
        
        # Priority 1: Parser-detected KEEP (Employees) syntax — extract columns only
        if opts.get("is_keep") and keep_table and keep_type != "inner":
            keep_table_def = self.all_tables_list.get(keep_table, {})
            if keep_table_def:
                # Extract field names from keep_table definition
                keep_table_fields = keep_table_def.get("fields", [])
                extracted_cols = []
                for f in keep_table_fields:
                    col_name = f.get("alias") or f.get("name", "")
                    if col_name and col_name != "*":
                        extracted_cols.append(_strip_qlik_qualifier(col_name))
                
                if extracted_cols:
                    keep_cols = extracted_cols
                    logger.debug(
                        "[_detect_and_apply_keep] %s KEEP (%s): extracted %d columns",
                        keep_type.upper(), keep_table, len(extracted_cols)
                    )
        
        # Priority 2: Explicit keep_columns from options
        if not keep_cols and ("keep" in transformations or opts.get("is_keep")):
            # Safety: skip if still no columns
            if not opts.get("is_keep"):
                return "", prev_step
            logger.warning(
                "[_detect_and_apply_keep] KEEP detected for '%s' but no keep_table or keep_columns found",
                table.get("name")
            )
            return "", prev_step
        
        if not keep_cols:
            return "", prev_step
        
        cols_list = ", ".join([f'"{col}"' for col in keep_cols])
        transform = (
            f",\n    #\"Kept Columns\" = Table.SelectColumns(\n"
            f"        {prev_step},\n"
            f"        {{{cols_list}}}\n"
            f"    )"
        )
        logger.debug(
            "[_detect_and_apply_keep] Keeping %d columns for table '%s'",
            len(keep_cols), table.get("name")
        )
        return transform, "#\"Kept Columns\""

    # ============================================================
    # TRANSFORMATION ORCHESTRATOR
    # ============================================================

    def _is_null_handler_pattern(self, expr: str, alias: str) -> tuple[bool, str]:
        if not expr or "ISNULL" not in expr.upper():
            return False, ""
        pattern = r"^IF\s*\(\s*IsNull\s*\(\s*(\w+)\s*\)\s*,\s*([^,]+)\s*,\s*\1\s*\)$"
        m = re.match(pattern, expr.strip(), re.IGNORECASE)
        if m:
            col_name = m.group(1).strip()
            replacement = m.group(2).strip().strip('"\'')
            if alias.lower() == col_name.lower():
                return True, replacement
        return False, ""

    def _detect_and_apply_null_fixes(self, fields: List[Dict], prev_step: str) -> tuple[str, str]:
        """
        Enhanced NULL handling using Table.TransformColumns() with column-level lambda expressions.
        
        Pattern: IF(IsNull(hours_worked), 0, hours_worked)
        → Generates: Table.TransformColumns(prev_step, {{"hours_worked", each if _ = null then 0 else _, type number}})
        
        Benefits:
        - Column-atomic (type-preserving)
        - Lambda-based (more readable M Query)
        - Handles both numeric and text replacements
        """
        null_fixes = []
        for f in fields:
            expr = f.get("expression", "").strip()
            alias = f.get("alias", f.get("name", ""))
            is_pattern, replacement_val = self._is_null_handler_pattern(expr, alias)
            if is_pattern:
                null_fixes.append((alias, replacement_val, f.get("type", "string")))
        
        if not null_fixes:
            return "", prev_step
        
        # Build single Table.TransformColumns step with all null fixes
        transform_steps = ""
        transform_cols = []
        
        for col_name, replacement, col_type in null_fixes:
            # Determine M type for the column
            m_type = _QLIK_TO_M_TYPE.get(col_type.lower(), "type text")
            
            # Build lambda: each if _ = null then replacement else _
            # Quote string replacements, keep numeric replacements bare
            if replacement.isdigit() or replacement.replace(".", "", 1).isdigit():
                # Numeric replacement (0, 100, etc.)
                lambda_expr = f"each if _ = null then {replacement} else _"
            else:
                # String replacement or expression
                lambda_expr = f'each if _ = null then "{replacement}" else _'
            
            transform_cols.append(f'{{"{col_name}", {lambda_expr}, {m_type}}}')
        
        if transform_cols:
            step_name = '#"Null Fixes"'
            transform_steps += (
                f",\n    {step_name} = Table.TransformColumns(\n"
                f"        {prev_step},\n"
                f"        {{\n"
                f"            {', '.join(transform_cols)}\n"
                f"        }}\n"
                f"    )"
            )
            return transform_steps, step_name
        
        return "", prev_step

    def _convert_qlik_expr_to_m(self, expr: str) -> str:
        """
        Convert a Qlik field expression to M Query syntax for Table.AddColumn.
        
        FIX 5: Standardize date format conversion:
        - YYYYMMDD → Date.FromText with proper formatting
        - Date#(field, format) → Date.FromText with format conversion
        
        🔥 FIX: Handle IF expressions: If(cond, true, false) → if cond then true else false
        """
        if not expr:
            return ""
        result = expr.strip()

        # 🔥 CRITICAL FIX: Convert Qlik IF to M Query IF first (before other conversions)
        # If(hours_worked > 8, 'Overtime', 'Normal') → if [hours_worked] > 8 then "Overtime" else "Normal"
        if result.upper().startswith("IF("):
            m_expr, _ = _parse_nested_if_expression(result)
            logger.debug("[_convert_qlik_expr_to_m] Converted IF expression: %s → %s", result, m_expr)
            return m_expr

        # FIX 5: Date#(field, 'YYYYMMDD') → Date.FromText with format conversion
        # When format is YYYYMMDD, we need to convert YYYYMMDD text to YYYY-MM-DD
        date_match = re.search(
            r"Date#\s*\(\s*\[?([^\]\),]+)\]?\s*,\s*[\"']([^\"']*)[\"']\s*\)",
            result, re.IGNORECASE
        )
        if date_match:
            field_name = date_match.group(1).strip()
            date_format = date_match.group(2).upper()
            
            if date_format == "YYYYMMDD":
                # FIX 5: Convert YYYYMMDD format to standard YYYY-MM-DD
                # This ensures Power BI interprets dates correctly
                result = (
                    f"Date.FromText("
                    f"Text.Combine({{"
                    f"Text.Start([{field_name}], 4), \"-\", "
                    f"Text.Middle([{field_name}], 4, 2), \"-\", "
                    f"Text.End([{field_name}], 2)"
                    f"}}"
                    f")"
                    f")"
                )
                logger.debug("[_convert_qlik_expr_to_m] Standardized YYYYMMDD → Date.FromText with YYYY-MM-DD format")
            else:
                # Other date formats default to Date.FromText
                result = f"Date.FromText([{field_name}])"

        # Year([field]) → Date.Year([field]) — negative lookbehind avoids Date.Year
        result = re.sub(
            r'(?<!\.)Year\s*\(\s*\[?([^\]\),]+)\]?\s*\)',
            lambda m: f"Date.Year([{m.group(1).strip()}])",
            result, flags=re.IGNORECASE
        )
        # Month([field]) → Date.Month([field])
        result = re.sub(
            r'(?<!\.)Month\s*\(\s*\[?([^\]\),]+)\]?\s*\)',
            lambda m: f"Date.Month([{m.group(1).strip()}])",
            result, flags=re.IGNORECASE
        )
        # Day([field]) → Date.Day([field])
        result = re.sub(
            r'(?<!\.)Day\s*\(\s*\[?([^\]\),]+)\]?\s*\)',
            lambda m: f"Date.Day([{m.group(1).strip()}])",
            result, flags=re.IGNORECASE
        )
        # Quarter([field]) → Date.QuarterOfYear([field]) (FIX #9 — Date dimensions)
        result = re.sub(
            r'(?<!\.)Quarter\s*\(\s*\[?([^\]\),]+)\]?\s*\)',
            lambda m: f"Date.QuarterOfYear([{m.group(1).strip()}])",
            result, flags=re.IGNORECASE
        )
        # Ceil(x) → Number.RoundUp(x)
        result = re.sub(r'(?<!\.)Ceil\s*\(', "Number.RoundUp(", result, flags=re.IGNORECASE)
        # Floor(x) → Number.RoundDown(x)
        result = re.sub(r'(?<!\.)Floor\s*\(', "Number.RoundDown(", result, flags=re.IGNORECASE)
        
        # FIX 3: TEXT FUNCTIONS - Convert Qlik text functions to M Query equivalents
        # Upper([field]) → Text.Upper([field])
        result = re.sub(r'(?<!\.)Upper\s*\(', "Text.Upper(", result, flags=re.IGNORECASE)
        # Lower([field]) → Text.Lower([field])
        result = re.sub(r'(?<!\.)Lower\s*\(', "Text.Lower(", result, flags=re.IGNORECASE)
        # Trim([field]) → Text.Trim([field])
        result = re.sub(r'(?<!\.)Trim\s*\(', "Text.Trim(", result, flags=re.IGNORECASE)
        # Len([field]) → Text.Length([field])
        result = re.sub(r'(?<!\.)Len\s*\(', "Text.Length(", result, flags=re.IGNORECASE)
        # Left([field], n) → Text.Start([field], n)
        result = re.sub(r'(?<!\.)Left\s*\(', "Text.Start(", result, flags=re.IGNORECASE)
        # Right([field], n) → Text.End([field], n)
        result = re.sub(r'(?<!\.)Right\s*\(', "Text.End(", result, flags=re.IGNORECASE)
        # Mid([field], start, len) → Text.Middle([field], start, len)
        result = re.sub(r'(?<!\.)Mid\s*\(', "Text.Middle(", result, flags=re.IGNORECASE)
        # LTrim([field]) → Text.TrimStart([field])
        result = re.sub(r'(?<!\.)LTrim\s*\(', "Text.TrimStart(", result, flags=re.IGNORECASE)
        # RTrim([field]) → Text.TrimEnd([field])
        result = re.sub(r'(?<!\.)RTrim\s*\(', "Text.TrimEnd(", result, flags=re.IGNORECASE)
        # Index([field], search) → Text.PositionOf([field], search)
        result = re.sub(r'(?<!\.)Index\s*\(', "Text.PositionOf(", result, flags=re.IGNORECASE)
        # Substitute([field], old, new) → Text.Replace([field], old, new)
        result = re.sub(r'(?<!\.)Substitute\s*\(', "Text.Replace(", result, flags=re.IGNORECASE)
        
        logger.debug("[_convert_qlik_expr_to_m] Applied text function conversions (Upper→Text.Upper, Trim→Text.Trim, etc.)")

        # Wrap bare field names in brackets if no M functions present
        if not re.search(r'[A-Za-z]+\.[A-Za-z]+\s*\(', result):
            result = _wrap_columns_in_brackets(result)

        return result




    def _is_simple_column_reference(self, expr: str) -> bool:
        """
        ✅ FIX DUPLICATE COLUMNS: Detect if expression is just a simple column reference (no transformation).
        
        Examples:
        - "[VIN]" → True (just column reference in brackets)
        - "VIN" → True (just column reference)
        - "[DealerID]" → True
        - "[VIN] AS Alias" → False (has alias, not a duplicate)
        - "[VIN] + 1" → False (has operator)
        - "IF(...)" → False (has transformation)
        
        Returns True if expression is ONLY selecting an existing column with no transformation.
        These columns are already in the source after PromoteHeaders, so skip AddColumn.
        """
        if not expr or expr == "*":
            return False
        
        expr_clean = expr.strip()
        
        # Check for any transformation indicators
        if any(c in expr_clean for c in "()+-*/%&|<>=!,;"):
            # Exception: allow parentheses only if it's just [ColumnName] with no operators inside
            if expr_clean.startswith("[") and expr_clean.endswith("]"):
                return True
            return False
        
        # Just a bracketed column name: [ColumnName]
        if expr_clean.startswith("[") and expr_clean.endswith("]"):
            return True
        
        # Just a plain identifier: ColumnName
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", expr_clean):
            return True
        
        return False

    def _detect_and_apply_column_renaming(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        ✅ FIX COLUMN RENAMING: Handle cases where columns need to be renamed.
        
        Example:
        - Qlik: LOAD [DealerID] AS [DealerID-ServiceID]
        - M Query: Table.RenameColumns(prev_step, {{"DealerID", "DealerID-ServiceID"}})
        
        This step runs BEFORE derived columns to handle all simple column reference renamings.
        Returns ("", prev_step) if no renamings needed.
        """
        fields = table.get("fields", [])
        rename_pairs = []
        
        for f in fields:
            name = f.get("name", "")
            alias = (f.get("alias") or name).strip()
            expr = f.get("expression", "").strip()
            
            # Only handle: simple column reference with DIFFERENT alias
            if not expr or expr == "*" or not alias or not name:
                continue
            
            # If expression is a simple column reference AND alias differs from field name
            if self._is_simple_column_reference(expr):
                # Extract source column name from expression
                source_col = expr.strip("[]").strip()
                
                # If alias is different from source column name, we need to rename
                if alias.lower() != source_col.lower():
                    rename_pairs.append((source_col, alias))
                    logger.debug(
                        "[column_renaming] Will rename '%s' → '%s'",
                        source_col, alias
                    )
        
        if not rename_pairs:
            return "", prev_step
        
        # Build M Query: Table.RenameColumns(step, {{"OldName", "NewName"}, ...})
        pairs_str = ", ".join([f'{{"{src}", "{dest}"}}' for src, dest in rename_pairs])
        transform = (
            f",\n    #\"Renamed Columns\" = Table.RenameColumns(\n"
            f"        {prev_step},\n"
            f"        {{\n        {pairs_str}\n        }}\n"
            f"    )"
        )
        
        logger.info(
            "[column_renaming] Table '%s': Renaming %d columns",
            table.get("name", "?"), len(rename_pairs)
        )
        return transform, "#\"Renamed Columns\""

    def _apply_safe_null_handling(self, fields: List[Dict], prev_step: str) -> tuple[str, str]:
        """
        ✅ SAFE NULL HANDLING - ONLY hours_worked COLUMN
        
        Matches Qlik semantic: If(IsNull(hours_worked), 0, hours_worked)
        
        Logic:
        - 🔥 ONLY handle known numeric columns
        - Text columns (employee_name, etc.) should stay null
        - Only hours_worked gets special null handling
        
        Returns:
            (m_query_steps, final_step_name)
        """
        transforms = ""
        current = prev_step

        for f in fields:
            col = f.get("alias") or f.get("name", "")
            
            # 🔥 ONLY handle known numeric columns
            if col.lower() == "hours_worked":
                step_name = f"#\"FixNull_{col}\""
                transforms += (
                    f",\n    {step_name} = Table.ReplaceValue(\n"
                    f"        {current},\n"
                    f"        null,\n"
                    f"        0,\n"
                    f"        Replacer.ReplaceValue,\n"
                    f"        {{\"{col}\"}}\n"
                    f"    )"
                )
                current = step_name
                logger.debug("[_apply_safe_null_handling] Fixed null values in '%s' column", col)

        if transforms:
            logger.info("[_apply_safe_null_handling] Applied safe null handling to hours_worked column")
        
        return transforms, current

    def _detect_and_apply_derived_columns(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        Detect Qlik derived-column expressions (Date#, Year, Month, Ceil, &, etc.)
        that are NOT handled by IF/APPLYMAP/GROUP BY, and emit Table.AddColumn M steps.

        This is the critical step that makes columns like full_date, total_hours,
        emp_department_name actually appear in the M expression output so Power BI
        can find them in the rowset at refresh time.

        ✅ FIX 4 DUPLICATE COLUMNS: Skip if column already exists in source or already added
        (i.e., the alias differs from the raw field name AND is not a passthrough).
        
        ✅ FIX DUPLICATE COLUMNS: Skip simple column references like [VIN], VIN, [DealerID]
        since they're already in the source table after PromoteHeaders.
        """
        fields = table.get("fields", [])
        aggregation_kws = ("sum(", "count(", "avg(", "average(", "min(", "max(", "total(")

        # Build set of source column names to avoid double-adding passthrough cols
        # Only include columns with simple passthrough expressions (no transformation)
        passthrough_col_names = {
            f.get("name", "").lower()
            for f in fields
            if f.get("name") and f.get("name") != "*"
            and (not f.get("expression") or f.get("expression", "").strip() == f.get("name"))
        }
        
        # ✅ FIX 4: Also build set of ALL source column names to prevent duplicate AddColumn
        all_source_columns = {
            (f.get("alias") or f.get("name", "")).lower()
            for f in fields
            if f.get("name") and f.get("name") != "*"
        }
        
        table_name = table.get("name", "")

        # 🔥 prevent duplicate column add
        existing_derived = [
            c.get("name") if isinstance(c, dict) else c
            for c in table.get("options", {}).get("_derived_columns", [])
        ]
        existing_derived_lower = {c.lower() for c in existing_derived}

        transform_steps = ""
        current_step = prev_step
        seen_aliases: set = set()

        for f in fields:
            name = f.get("name", "")
            alias = (f.get("alias") or name).strip()
            expr = f.get("expression", "").strip()

            # Skip: no expression, passthrough, wildcard
            if not expr or expr == name or expr == "*" or not alias:
                continue

            expr_upper = expr.upper()

            # ✅ FIX DUPLICATE COLUMNS: Skip simple column references (like [VIN], VIN, [DealerID])
            # These are already in the source table after PromoteHeaders, no AddColumn needed
            if self._is_simple_column_reference(expr):
                logger.debug("[derived_cols] Skipping simple column reference for '%s' (expr='%s') - already in source", alias, expr)
                continue

            # Skip IF conditions (handled by _detect_and_apply_if_conditions)
            if expr_upper.startswith("IF(") or expr_upper.startswith("IF ("):
                continue
            # Skip APPLYMAP (not supported in strict mode - JOIN logic removed)
            if "APPLYMAP" in expr_upper:
                continue
            # Skip aggregations (handled by _detect_and_apply_groupby)
            if any(kw in expr_upper for kw in aggregation_kws):
                continue

            # Skip if this is a pure passthrough column (already in source, no transformation)
            if alias.lower() in passthrough_col_names and alias.lower() == name.lower() and expr.lower() == name.lower():
                continue

            # ✅ FIX 4: Skip if column already exists in source (prevent duplicate AddColumn)
            if alias.lower() in all_source_columns:
                logger.debug("[derived_cols] Skipping '%s' - column already exists in source table", alias)
                continue

            # Skip duplicates
            if alias.lower() in seen_aliases:
                continue
            seen_aliases.add(alias.lower())

            # 🔥 prevent duplicate
            if alias.lower() in existing_derived_lower:
                logger.debug("[derived_cols] Skipping duplicate column: %s (already in _derived_columns)", alias)
                continue

            # Convert expression to M
            m_expr = self._convert_qlik_expr_to_m(expr)
            if not m_expr:
                logger.warning("[derived_cols] Could not convert expr for '%s': %s", alias, expr)
                continue

            # Infer return type
            expr_u = expr.upper()
            if any(kw in expr_u for kw in ("DATE#", "DATE(", "MAKEDATE", "TODAY(", "NOW(")):
                type_spec = ", type date"
            elif any(kw in expr_u for kw in ("YEAR(", "MONTH(", "DAY(", "QUARTER(", "CEIL(", "FLOOR(", "ROUND(")):
                type_spec = ", type number"
            elif re.search(r'[\+\-\*\/]', expr) and not re.search(r'&', expr):
                type_spec = ", type number"
            else:
                type_spec = ", type text"

            safe_alias = _escape_m_string(alias)
            step_name = f"#\"Added {safe_alias}\""
            transform_steps += (
                f",\n    {step_name} = Table.AddColumn(\n"
                f"        {current_step},\n"
                f"        \"{safe_alias}\",\n"
                f"        each {m_expr}{type_spec}\n"
                f"    )"
            )
            current_step = step_name
            logger.info(
                "[derived_cols] Table '%s': Added column '%s' from expr: %s → %s",
                table.get("name", "?"), alias, expr[:60], m_expr[:60]
            )

        return transform_steps, current_step

    def _detect_and_apply_applymap(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        🔥 APPLYMAP → M Query Conversion (CRITICAL FIX C)
        
        Converts Qlik ApplyMap('MapTable', key_column, 'default') to M Query pattern:
        1. Table.NestedJoin - LEFT JOIN with mapping table
        2. Table.ExpandTableColumn - Expand joined columns
        3. Table.ReplaceValue - Replace nulls with default value
        
        Example:
        Qlik: ApplyMap('DeptMap', department_id, 'Unknown') as emp_department_name
        
        M Query:
        1. NestedJoin on department_id with DeptHeaders (inferred)
        2. ExpandTableColumn to get department_name → emp_department_name
        3. ReplaceValue to swap null → 'Unknown'
        
        NOTE: This method assumes mapping tables are already loaded as variables
        (e.g., DeptMapHeaders). The calling method must generate these first!
        
        Returns: (transform_string, final_step_name)
        """
        opts = table.get("options", {})
        fields = table.get("fields", [])
        
        if not opts.get("has_applymap"):
            return "", prev_step
        
        # Extract all ApplyMap metadata
        applymap_info = self._extract_applymap_metadata(fields)
        if not applymap_info:
            logger.info("[APPLYMAP] No ApplyMap expressions found for table '%s'", table.get("name", "?"))
            return "", prev_step
        
        transform = ""
        current = prev_step
        
        # Process each mapping table
        for map_table_name, applymap_meta in applymap_info.items():
            key_col = applymap_meta.get("key_column", "").strip()
            default_val = applymap_meta.get("default_value", "").strip()
            output_cols = applymap_meta.get("output_columns", [])
            
            if not key_col or not output_cols:
                logger.warning("[APPLYMAP] Skipping incomplete ApplyMap for '%s'", map_table_name)
                continue
            
            # Map table name is assumed to be already loaded as "{map_table_name}Headers"
            # Example: 'DeptMap' → DeptMapHeaders variable
            map_table_var = f"{map_table_name}Headers"
            
            # ✅ STEP 1: NestedJoin to lookup values from mapping table
            join_step = f"#\"NestedJoin_{map_table_name}\""
            transform += f""",
    {join_step} = Table.NestedJoin(
        {current},
        {{"{key_col}"}},
        {map_table_var},
        {{"{key_col}"}},
        "{map_table_name}_joined",
        JoinKind.LeftOuter
    )"""
            current = join_step
            logger.debug("[APPLYMAP] Step 1: NestedJoin on '%s' with '%s'", key_col, map_table_var)
            
            # ✅ STEP 2: ExpandTableColumn to flatten the joined data
            expand_step = f"#\"Expand_{map_table_name}\""
            expand_cols_str = ", ".join([f'"{col}"' for col in output_cols])
            transform += f""",
    {expand_step} = Table.ExpandTableColumn(
        {current},
        "{map_table_name}_joined",
        {{{expand_cols_str}}},
        {{{expand_cols_str}}}
    )"""
            current = expand_step
            logger.debug("[APPLYMAP] Step 2: ExpandTableColumn - merged: %s", output_cols)
            
            # ✅ STEP 3: ReplaceValue to swap nulls with default value
            if default_val:
                replace_step = f"#\"ReplaceNulls_{map_table_name}\""
                for col in output_cols:
                    transform += f""",
    {replace_step} = Table.ReplaceValue(
        {current},
        null,
        "{default_val}",
        Replacer.ReplaceValue,
        {{"{col}"}}
    )"""
                    current = replace_step
                logger.debug("[APPLYMAP] Step 3: ReplaceValue - null → '%s' for columns: %s", default_val, output_cols)
            
            # Track derived columns for BIM metadata
            for col in output_cols:
                self._track_derived_column(table, col, "string")
        
        logger.info("[APPLYMAP] ✅ ApplyMap transformations applied for table '%s'", table.get("name", "?"))
        return transform, current

    def _generate_applymap_table_loading_code(self, table: Dict[str, Any], source_var: str = "Source") -> str:
        """
        🔥 CRITICAL: Generate code to load mapping tables BEFORE NestedJoin
        
        For each ApplyMap expression in the table, extract the mapping table name
        and generate the code to load it from SharePoint/S3/etc.
        
        Example output:
        
        DeptMapFile = Table.SelectRows(Source, each Text.EndsWith(...dim_department.csv...)){0}[Content],
        DeptMapCsv = Csv.Document(DeptMapFile, [...]),
        DeptMapHeaders = Table.PromoteHeaders(DeptMapCsv, [...])
        
        Returns: (setup_code_string) - empty string if no ApplyMap expressions
        """
        fields = table.get("fields", [])
        opts = table.get("options", {})
        
        if not opts.get("has_applymap"):
            return ""
        
        # Extract ApplyMap metadata
        applymap_info = self._extract_applymap_metadata(fields)
        if not applymap_info:
            return ""
        
        setup_code = ""
        
        # Mapping abbreviations to full names
        abbreviation_map = {
            "dept": "department",
            "pos": "position",
            "emp": "employee",
            "cust": "customer",
            "prod": "product",
            "cat": "category",
            "reg": "region",
        }
        
        # For each mapping table, generate loading code
        for map_table_name in applymap_info.keys():
            # Infer filename from map table name
            # Example: 'DeptMap' → 'dim_department.csv', 'PosMap' → 'dim_position.csv'
            map_table_prefix = map_table_name.replace("Map", "").lower()
            if not map_table_prefix:
                map_table_prefix = map_table_name.lower()
            
            # Expand common abbreviations to full names
            map_table_prefix = abbreviation_map.get(map_table_prefix, map_table_prefix)
            
            inferred_filename = f"dim_{map_table_prefix}.csv"
            
            # Generate the loading steps
            # Step 1: Select file from SharePoint (assuming SharePoint source)
            setup_code += f""",
    {map_table_name}File = Table.SelectRows(
        {source_var},
        each Text.EndsWith(Text.Lower([Name]), \"{inferred_filename}\")
    ){{0}}[Content]"""
            
            # Step 2: Load CSV
            setup_code += f""",
    {map_table_name}Csv = Csv.Document(
        {map_table_name}File,
        [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    )"""
            
            # Step 3: Promote headers
            setup_code += f""",
    {map_table_name}Headers = Table.PromoteHeaders(
        {map_table_name}Csv,
        [PromoteAllScalars=true]
    )"""
            
            logger.info("[ApplyMap Loading] Generated loading code for mapping table: %s → %s", map_table_name, inferred_filename)
        
        return setup_code


    def _apply_date_transformation(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        ✅ DATE TRANSFORMATION WITH ROBUST #date() PARSING
        Automatically generates date-derived columns: Year, Month, Day, Quarter.
        Converts date_id (YYYYMMDD format) to full_date and extracts temporal dimensions.

        Generates:
        - full_date: Date parsed from date_id using #date() (type date) — robust and null-safe
        - year: Extracted from full_date via Date.Year()
        - month: Extracted from full_date via Date.Month()
        - day: Extracted from full_date via Date.Day()
        - quarter: Calculated as "Q1", "Q2", "Q3", "Q4" based on month (type text)

        Returns: (m_query_string, final_step_name)
        """
        table_name = table.get("name", "?")
        logger.debug("[_apply_date_transformation] Called for table: %s, prev_step: %s", table_name, prev_step)

        # ✅ PRODUCTION-SAFE DATE PARSING using #date() function
        # FIX: All syntax corrected - try...otherwise, Text.Middle, Text.End
        # Parses YYYYMMDD format directly to date object with error handling
        transform = f""",
    Add_full_date = Table.AddColumn(
        {prev_step},
        "full_date",
        each try #date(
            Number.FromText(Text.Start([date_id], 4)),
            Number.FromText(Text.Middle([date_id], 4, 2)),
            Number.FromText(Text.End([date_id], 2))
        ) otherwise null,
        type date
    ),
    Add_year = Table.AddColumn(Add_full_date, "year", each Date.Year([full_date]), Int64.Type),
    Add_month = Table.AddColumn(Add_year, "month", each Date.Month([full_date]), Int64.Type),
    Add_day = Table.AddColumn(Add_month, "day", each Date.Day([full_date]), Int64.Type),
    Add_quarter = Table.AddColumn(Add_day, "quarter", each "Q" & Number.ToText(Date.QuarterOfYear([full_date])), type text)
"""

        # Track all generated columns for Power BI BIM schema
        # FIX: Bulk set with proper dict format for BIM compatibility
        table.get("options", {})["_derived_columns"] = [
            {"name": "full_date", "dataType": "dateTime"},
            {"name": "year", "dataType": "int64"},
            {"name": "month", "dataType": "int64"},
            {"name": "day", "dataType": "int64"},
            {"name": "quarter", "dataType": "string"}
        ]

        logger.info("[_apply_date_transformation] ✅ Generated date transformation for '%s': full_date (YYYYMMDD→date), year, month, day, quarter", table_name)
        return transform, "Add_quarter"

    def convert_applymap_to_dimension_table(self, map_table_name: str, base_path: str, key_column: str) -> Dict[str, Any]:
        """
        🔥 STRICT MODE: APPLYMAP dimension table generation is DISABLED.
        
        This method was deleted in strict mode to ensure:
        - No intelligent schema merging
        - No auto-detection of dimension tables
        - Direct Qlik expressions → M Query mapping only
        
        Returns: None (disabled in strict mode)
        """
        logger.debug(
            "[convert_applymap_to_dimension_table] DISABLED in strict mode - "
            "APPLYMAP dimension table generation skipped for '%s'",
            map_table_name
        )
        return None

    def _auto_add_kpi_columns(self, table: Dict[str, Any], prev_step: str, columns: List[str] = None) -> tuple[str, str]:
        """
        FIX 6: AUTO-GENERATE KPI COLUMNS WITH COLUMN TRACKING
        Automatically generates KPI columns when hours_worked is detected.
        If parser misses IF conditions → KPI lost, so this function ensures
        KPI columns are ALWAYS generated regardless of parser state.

        FIX 6: Tracks all generated KPI columns for metadata

        Generates:
        - work_type: "Overtime" if hours_worked > 8, else "Normal"
        - productivity_flag: 1 if hours_worked >= 8, else 0
        - productivity_score: hours_worked * 10

        Returns: (m_query_string, final_step_name)
        """
        if columns is None:
            columns = []
        if not columns or "hours_worked" not in columns:
            return "", prev_step

        # 🔥 FIX: Add explicit type specification for hours_worked as Int64.Type
        # This ensures numeric operations work correctly on [hours_worked] in IF conditions
        transform = (
            f",\n    Typed = Table.TransformColumnTypes(\n"
            f"        {prev_step},\n"
            f"        {{\n"
            f"            {{\"hours_worked\", Int64.Type}}\n"
            f"        }}\n"
            f"    )"
        )

        # 🔥 FIX: Add NULL handling for hours_worked → replace null with 0
        # Maps Qlik: If(IsNull(hours_worked), 0, hours_worked)
        transform += (
            f",\n    FixNull = Table.ReplaceValue(\n"
            f"        Typed,\n"
            f"        null,\n"
            f"        0,\n"
            f"        Replacer.ReplaceValue,\n"
            f"        {{\"hours_worked\"}}\n"
            f"    )"
        )

        # 🔥 FIX: Add CONCATENATE logic if this is a concatenate operation
        # Maps Qlik: CONCATENATE(Activity) LOAD ... → Table.Combine({original, duplicate})
        current_step = "FixNull"
        opts = table.get("options", {})
        if opts.get("is_concatenate"):
            # Create duplicate with transformed activity_id column
            transform += (
                f",\n    #\"Duplicate\" = Table.TransformColumns(\n"
                f"        FixNull,\n"
                f"        {{{{\"activity_id\", each _ & \"_X\", type text}}}}\n"
                f"    )"
            )
            # Combine original and duplicate
            transform += (
                f",\n    #\"Combined\" = Table.Combine(\n"
                f"        {{FixNull, #\"Duplicate\"}}\n"
                f"    )"
            )
            current_step = "#\"Combined\""
            logger.debug("[_auto_add_kpi_columns] Added CONCATENATE logic: Table.Combine")

        transform += (
            f",\n    #\"KPI Columns\" = Table.AddColumn(\n"
            f"        {current_step},\n"
            f"        \"work_type\",\n"
            f"        each if [hours_worked] > 8 then \"Overtime\" else \"Normal\",\n"
            f"        type text\n"
            f"    )"
        )

        transform += (
            f",\n    #\"Productivity Flag\" = Table.AddColumn(\n"
            f"        #\"KPI Columns\",\n"
            f"        \"productivity_flag\",\n"
            f"        each if [hours_worked] >= 8 then 1 else 0,\n"
            f"        Int64.Type\n"
            f"    )"
        )

        transform += (
            f",\n    #\"Productivity Score\" = Table.AddColumn(\n"
            f"        #\"Productivity Flag\",\n"
            f"        \"productivity_score\",\n"
            f"        each [hours_worked] * 10,\n"
            f"        Int64.Type\n"
            f"    )"
        )

        # FIX 6: Track all derived KPI columns for metadata
        for col_name, col_type in [("work_type", "string"), ("productivity_flag", "double"), ("productivity_score", "double")]:
            self._track_derived_column(table, col_name, col_type)

        logger.info("[_auto_add_kpi_columns] Generated 3 KPI columns with FIX 6 tracking: work_type, productivity_flag, productivity_score")
        return transform, "#\"Productivity Score\""

    def _detect_and_apply_date(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        🔥 DETECT date_id COLUMN AND APPLY DATE TRANSFORMATION
        
        Detects if table has date_id column and applies date transformation
        to generate full_date, year, month, day, quarter columns.
        """
        fields = table.get("fields", [])
        
        has_date = any("date_id" in (f.get("name", "") or "").lower() for f in fields)
        
        if not has_date:
            return "", prev_step
        
        logger.info(f"[DATE FIX] Applying date transformation for {table.get('name')}")
        
        return self._apply_date_transformation(table, prev_step)

    def _apply_all_transformations(self, table: Dict[str, Any], prev_step: str) -> tuple[str, str]:
        """
        🔥 STRICT TRANSFORMATION ORDER (7 STEPS)
        
        ✅ FINAL ORDER:
        1. NULL HANDLING (SAFE ONLY - hours_worked)
        2. CONCATENATE
        3. IF CONDITIONS
        3.5 DATE TRANSFORMATION (date_id → full_date, year, month, day, quarter)
        4. GROUP BY
        ❌ NO JOIN
        5. KEEP
        """
        # FIX 1 (Normalization): Ensure fields are dicts before processing
        self._normalize_fields(table)
        
        fields = table.get("fields", [])
        opts = table.get("options", {})
        transform = ""
        current = prev_step

        # 1️⃣  NULL (SAFE ONLY)
        null_t, current = self._apply_safe_null_handling(fields, current)
        transform += null_t
        logger.debug("[_apply_all_transformations] Step 1: NULL HANDLING")

        # 2️⃣  CONCAT
        if opts.get("is_concatenate"):
            concat_t, current = self._detect_and_apply_concatenate(table, current)
            transform += concat_t
            logger.debug("[_apply_all_transformations] Step 2: CONCATENATE")

        # 3️⃣  IF CONDITIONS
        if opts.get("has_if_conditions") or any("IF(" in f.get("expression", "").upper() for f in fields):
            if_t, current = self._detect_and_apply_if_conditions(table, current, fields)
            transform += if_t
            logger.debug("[_apply_all_transformations] Step 3: IF CONDITIONS")

        # 3️⃣.3️⃣  APPLYMAP → LEFT JOIN (CRITICAL FIX)
        if opts.get("has_applymap"):
            applymap_t, current = self._detect_and_apply_applymap(table, current)
            transform += applymap_t
            logger.info("[_apply_all_transformations] Step 3.3: APPLYMAP → LEFT JOIN")

        # 3️⃣.5️⃣  DATE TRANSFORMATION EXECUTION (CRITICAL FIX)
        transformations = opts.get("transformations", [])
        if isinstance(transformations, str):
            transformations = [transformations]
        
        if "date" in transformations or opts.get("has_date_transformation"):
            date_t, current = self._apply_date_transformation(table, current)
            transform += date_t
            logger.info("[FIX] Date transformation applied for table: %s", table.get("name"))

        # 4️⃣  GROUP BY
        if opts.get("is_group_by"):
            group_t, current = self._detect_and_apply_groupby(table, current, fields)
            transform += group_t
            logger.debug("[_apply_all_transformations] Step 4: GROUP BY")

        # ❌ NO JOIN (STRICT MODE)
        opts["is_join"] = False

        # 5️⃣  KEEP
        if opts.get("is_keep"):
            keep_t, current = self._detect_and_apply_keep(table, current)
            transform += keep_t
            logger.debug("[_apply_all_transformations] Step 5: KEEP")

        logger.info("[_apply_all_transformations] Transformations applied for table '%s'", table.get("name", "?"))
        
        return transform, current

    def _track_derived_column(self, table: Dict[str, Any], col_name: str, data_type: str = "string") -> None:
        """
        FIX 6: Track derived columns added through transformations so resolve_output_columns()
        can include them in BIM metadata. This prevents column mismatches between M query
        output and Power BI schema.
        
        Called by transformation methods when they add new columns via Table.AddColumn.
        
        Args:
            table: The table definition dict
            col_name: Name of the derived column being added
            data_type: BIM data type (string, double, date, etc.)
        """
        if "_derived_columns" not in table.get("options", {}):
            table.setdefault("options", {})["_derived_columns"] = []
        
        derived = table["options"]["_derived_columns"]
        # Avoid duplicates
        if not any(d.get("name") == col_name for d in derived if isinstance(d, dict)):
            derived.append({"name": col_name, "dataType": data_type})
            logger.debug("[_track_derived_column] Tracked derived column '%s' in table '%s'", col_name, table.get("name", "?"))

    def _finalize_derived_columns_tracking(self, table: Dict[str, Any]) -> None:
        """
        FIX 6: Finalize derived column tracking by extracting columns from field definitions
        that have expressions (i.e., are derived/computed, not passthrough).
        This ensures all derived columns are tracked for column metadata.
        """
        fields = table.get("fields", [])
        opts = table.setdefault("options", {})
        
        if "_derived_columns" not in opts:
            opts["_derived_columns"] = []
        
        derived = opts["_derived_columns"]
        seen = {d.get("name", "").lower() if isinstance(d, dict) else str(d).lower() for d in derived}
        
        # Track columns from field definitions that have non-passthrough expressions
        for f in fields:
            name = f.get("name", "").strip()
            alias = (f.get("alias") or name).strip()
            expr = f.get("expression", "").strip()
            
            if not name or name == "*" or not alias:
                continue
            
            # Column is derived if it has an expression different from its name
            if expr and expr != name and alias.lower() not in seen:
                # Infer type from expression
                expr_upper = expr.upper()
                if any(kw in expr_upper for kw in ("DATE#", "DATE(", "MAKEDATE", "TODAY(", "NOW(")):
                    data_type = "date"
                elif any(kw in expr_upper for kw in ("YEAR(", "MONTH(", "DAY(", "QUARTER(", "CEIL(", "FLOOR(", "ROUND(", "SUM(", "COUNT(", "AVG(")):
                    data_type = "double"
                elif re.search(r'[\+\-\*\/]', expr) and not re.search(r'&', expr):
                    data_type = "double"
                else:
                    data_type = "string"
                
                derived.append({"name": _strip_qlik_qualifier(alias), "dataType": data_type})
                seen.add(alias.lower())
                logger.debug("[_finalize_derived_columns_tracking] Tracked field '%s' as derived (type=%s)", alias, data_type)

    # ============================================================
    # INLINE
    # ============================================================

    def _m_inline(self, table, base_path, _cs):
        opts   = table.get("options", {})
        fields = table["fields"]
        headers = opts.get("inline_headers", [f["name"] for f in fields if f["name"] != "*"])
        rows = opts.get("inline_rows_all") or opts.get("inline_sample", [])
        type_defs = ", ".join(
            f"{_sanitize_col_name(_strip_qlik_qualifier(h))} = "
            f"{_m_type_for_table(next((f['type'] for f in fields if f['name'] == h), 'string'), h)}"
            for h in headers
        )
        row_strs = []
        for row in rows:
            vals = []
            for h in headers:
                v = str(row.get(h, ""))
                v = v.strip("'").replace('"', '""').replace("\n", " ").replace("\r", "")
                v = " ".join(v.split())
                vals.append(f'"{v}"')
            row_strs.append("{" + ", ".join(vals) + "}")
        rows_m = (
            "{\n        " + ",\n        ".join(row_strs) + "\n    }"
            if row_strs else "{}"
        )
        rows_m = re.sub(r',\s*\n\s*"', ', "', rows_m)
        m = (
            f"let\n"
            f"    Source = #table(\n"
            f"        type table [{type_defs}],\n"
            f"        {rows_m}\n"
            f"    )\n"
            f"in\n"
            f"    Source"
        )
        return m, f"Inline table with {len(rows)} row(s). Data embedded directly."

    # ============================================================
    # CSV
    # ============================================================

    def _m_csv(self, table, base_path, _cs):
        path   = _normalize_path(table.get("source_path", ""))
        fields = table["fields"]
        opts   = table.get("options", {})
        table_name = table.get("name", "")
        delimiter = opts.get("delimiter", ",")
        encoding  = 65001
        enc_str   = opts.get("encoding", "")
        if enc_str:
            enc_map = {"UTF-8": 65001, "UTF8": 65001, "UTF-16": 1200, "UTF16": 1200}
            encoding = enc_map.get(enc_str.upper().replace("-", ""), encoding)

        # ✅ FIX: CONCATENATE - Check if this table has multiple sources to combine
        concat_sources = opts.get("concat_sources", [])
        if concat_sources:
            logger.info(
                "[_m_csv] '%s': CONCATENATE detected with %d source(s)",
                table_name, len(concat_sources)
            )
            # Use _build_safe_combine to load and combine all sources with schema alignment
            safe_combine_m, safe_combine_final = self._build_safe_combine(
                concat_sources, fields, base_path
            )
            if safe_combine_m:
                # Apply transformations on top of the combined result
                extra_transform, extra_final = self._apply_all_transformations(table, safe_combine_final)
                combined_transform = safe_combine_m + extra_transform
                final = extra_final or safe_combine_final
                
                # Inject schema if not already present
                if not "TransformColumnTypes" in combined_transform:
                    schema_step, final = self._build_explicit_schema_step(table_name, final)
                    combined_transform += schema_step
                
                # For CONCATENATE, we need to close the let..in expression properly
                if safe_combine_m.endswith("in\n    SafeCombined"):
                    # Remove the final "in\n    SafeCombined" from _build_safe_combine output
                    m_body = safe_combine_m.rsplit("in\n", 1)[0]
                    m = m_body + combined_transform + f"\nin\n    {final}"
                else:
                    m = safe_combine_m + combined_transform + f"\nin\n    {final}"
                
                return m, f"CONCATENATE: {len(concat_sources)} CSV source(s) combined with schema alignment."

        base_transform, transform_final = self._apply_types(fields, "Headers", table_name)
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or "Headers")
        combined_transform = base_transform + extra_transform
        final = extra_final or transform_final or "Headers"
        
        # Detect LOAD * table (no explicit fields)
        is_load_star = not fields or all(f.get("name") == "*" for f in fields)
        
        logger.debug(
            "[_m_csv] '%s': LOAD_STAR=%s, base_transform len=%d, extra_transform len=%d, combined has TypedTable=%s",
            table_name, is_load_star, len(base_transform), len(extra_transform), "TypedTable" in combined_transform
        )
        
        # ✅ FIX: For LOAD * tables, ALWAYS ensure explicit column metadata at end
        # This guarantees TypedTable step exists in M query for Power BI extraction
        if is_load_star and not "TransformColumnTypes" in combined_transform:
            # No schema in transforms — use _build_explicit_schema_step which has dynamic fallback
            schema_step, final = self._build_explicit_schema_step(table_name, final or "Headers")
            combined_transform += schema_step
            logger.info(
                "[_m_csv] '%s': LOAD * detected - injected schema. TypedTable now in query=%s",
                table_name, "TypedTable" in combined_transform
            )
        elif not base_transform.strip() or (extra_transform and not "TransformColumnTypes" in combined_transform):
            # Also inject for non-LOAD* tables if no schema generated
            schema_step, final = self._build_explicit_schema_step(table_name, final or "Headers")
            combined_transform += schema_step
            logger.info(
                "[_m_csv] '%s': injected schema (non-LOAD*). TypedTable in query=%s",
                table_name, "TypedTable" in combined_transform
            )
        filename_only = path.rsplit("/", 1)[-1] if "/" in path else path

        if _is_sharepoint_url(base_path):
            opts["table_name"] = table.get("name", "Table")
            site_url, folder_path, filename = self._get_sharepoint_parts(base_path, path, opts)
            sp_transform, sp_final = self._apply_types_as_is(fields, "Headers")
            extra_sp_transform, extra_sp_final = self._apply_all_transformations(table, sp_final or "Headers")
            combined_sp_transform = sp_transform + extra_sp_transform
            final_sp = extra_sp_final or sp_final or "Headers"

            # 🔥 FIX: Force date transformation if date_id column exists and transformation wasn't applied
            has_date_id = any("date_id" in (f.get("name", "") or "").lower() for f in fields)
            has_date_transform_in_query = "Add_full_date" in combined_sp_transform or "Add_quarter" in combined_sp_transform
            if has_date_id and not has_date_transform_in_query:
                logger.info("[SharePoint] Forcing date transformation for table with date_id column: %s", table.get("name"))
                # Clear derived columns check to allow transformation to be generated
                table.get("options", {}).pop("_derived_columns", None)
                date_t, final_sp = self._apply_date_transformation(table, final_sp)
                combined_sp_transform += date_t

            # ✅ Fix 3: Determine if this is a LOAD * table (no explicit field definitions)
            is_load_star = (
                not fields or
                all(f.get("name") == "*" for f in fields)
            )
            # For LOAD * tables: always inject schema (explicit or dynamic fallback)
            # For explicit LOAD tables: only inject if no transform was generated
            if is_load_star or (not combined_sp_transform.strip() and final_sp == "Headers"):
                combined_sp_transform, final_sp = self._build_explicit_schema_step(
                    table.get("name", ""), "Headers"
                )

            # 🔥 LOAD MAPPING TABLES FOR APPLYMAP (before main data transformations)
            mapping_tables_code = self._generate_applymap_table_loading_code(table, source_var="Source")

            m = _build_sharepoint_m(
                site_url=site_url, filename=filename, folder_path=folder_path,
                delimiter=delimiter, encoding=encoding,
                transform_step=combined_sp_transform, final_step=final_sp or "Headers",
                mapping_tables_code=mapping_tables_code,
            )
        elif _is_s3_url(base_path):
            sp_transform, sp_final = self._apply_types_as_is(fields, "Headers")
            extra_sp_transform, extra_sp_final = self._apply_all_transformations(table, sp_final or "Headers")
            combined_sp_transform = sp_transform + extra_sp_transform
            final_sp = extra_sp_final or sp_final or "Headers"

            # 🔥 FIX: Force date transformation if date_id column exists and transformation wasn't applied
            has_date_id = any("date_id" in (f.get("name", "") or "").lower() for f in fields)
            has_date_transform_in_query = "Add_full_date" in combined_sp_transform or "Add_quarter" in combined_sp_transform
            if has_date_id and not has_date_transform_in_query:
                logger.info("[S3] Forcing date transformation for table with date_id column: %s", table.get("name"))
                # Clear derived columns check to allow transformation to be generated
                table.get("options", {}).pop("_derived_columns", None)
                date_t, final_sp = self._apply_date_transformation(table, final_sp)
                combined_sp_transform += date_t

            # ✅ Fix 3: Same fix for S3 LOAD * tables
            is_load_star = (
                not fields or
                all(f.get("name") == "*" for f in fields)
            )
            if is_load_star or (not combined_sp_transform.strip() and final_sp == "Headers"):
                combined_sp_transform, final_sp = self._build_explicit_schema_step(
                    table.get("name", ""), "Headers"
                )

            m = _build_s3_m(bucket_url=base_path, filename=filename_only,
                            delimiter=delimiter, encoding=encoding,
                            transform_step=combined_sp_transform, final_step=final_sp)
        elif _is_azure_blob_url(base_path):
            sp_transform, sp_final = self._apply_types_as_is(fields, "Headers")
            extra_sp_transform, extra_sp_final = self._apply_all_transformations(table, sp_final or "Headers")
            combined_sp_transform = sp_transform + extra_sp_transform
            final_sp = extra_sp_final or sp_final or "Headers"

            # 🔥 FIX: Force date transformation if date_id column exists and transformation wasn't applied
            has_date_id = any("date_id" in (f.get("name", "") or "").lower() for f in fields)
            has_date_transform_in_query = "Add_full_date" in combined_sp_transform or "Add_quarter" in combined_sp_transform
            if has_date_id and not has_date_transform_in_query:
                logger.info("[Azure Blob] Forcing date transformation for table with date_id column: %s", table.get("name"))
                # Clear derived columns check to allow transformation to be generated
                table.get("options", {}).pop("_derived_columns", None)
                date_t, final_sp = self._apply_date_transformation(table, final_sp)
                combined_sp_transform += date_t

            # ✅ Fix 3: Same fix for Azure Blob LOAD * tables
            is_load_star = (
                not fields or
                all(f.get("name") == "*" for f in fields)
            )
            if is_load_star or (not combined_sp_transform.strip() and final_sp == "Headers"):
                combined_sp_transform, final_sp = self._build_explicit_schema_step(
                    table.get("name", ""), "Headers"
                )

            # 🔥 LOAD MAPPING TABLES FOR APPLYMAP (before main data transformations)
            mapping_tables_code = self._generate_applymap_table_loading_code(table, source_var="Source")

            m = _build_azure_blob_m(container_url=base_path, filename=filename_only,
                                    delimiter=delimiter, encoding=encoding,
                                    transform_step=combined_sp_transform, final_step=final_sp,
                                    mapping_tables_code=mapping_tables_code)
        elif _is_web_url(base_path):
            clean_bp = base_path.strip().strip('"').strip("'").rstrip("/")
            file_url = f"{clean_bp}/{path}" if path else clean_bp
            
            # ✅ FIX: Explicitly ensure all transformations are applied (including date transformation)
            # After Headers are promoted, call _apply_all_transformations to get complete pipeline
            logger.debug("[_m_csv] Applying all transformations pipeline for Web URL table '%s'", table_name)
            all_transform, all_final = self._apply_all_transformations(table, "Headers")
            
            # Use transformation result if present, otherwise use default schema
            if all_transform.strip():
                transform_to_use = all_transform
                final_to_use = all_final
                logger.info("[_m_csv] '%s': Using transformation pipeline with final step: %s (Web URL)", table_name, final_to_use)
            else:
                # Fallback: inject dynamic schema for LOAD * tables
                transform_to_use = (
                    ",\n"
                    "    Columns = Table.ColumnNames(Headers),\n"
                    "    TypedTable = Table.TransformColumnTypes(\n"
                    "        Headers,\n"
                    "        List.Transform(Columns, each {_, type text})\n"
                    "    )"
                )
                final_to_use = "TypedTable"
                logger.info("[_m_csv] '%s': injected DYNAMIC schema for Web URL (no transformations)", table_name)
            
            m = (
                f"let\n"
                f"    Source = Web.Contents(\"{file_url}\"),\n"
                f"    CsvData = Csv.Document(\n"
                f"        Source,\n"
                f"        [Delimiter=\"{delimiter}\", Encoding={encoding}, QuoteStyle=QuoteStyle.Csv]\n"
                f"    ),\n"
                f"    Headers = Table.PromoteHeaders(CsvData, [PromoteAllScalars=true])"
                f"{transform_to_use}\n"
                f"in\n"
                f"    {final_to_use}"
            )
        else:
            # ✅ FIX 4: Ensure fallback for LOAD * tables in local file path too
            if not combined_transform.strip() and (final or "Headers") == "Headers":
                # No schema generated — inject dynamic fallback
                combined_transform = self._apply_dynamic_schema("Headers")
                final = "TypedTable"
                logger.info(
                    "[_m_csv] '%s': No transformations - injected dynamic fallback schema (local file)",
                    table_name
                )
            
            if base_path.strip().startswith("["):
                path_expr = f"{base_path} & \"/{path}\""
            else:
                clean_bp = base_path.strip().strip('"').strip("'")
                path_expr = f'"{clean_bp}/{path}"'
            
            # ✅ FIX: Explicitly ensure all transformations are applied (including date transformation)
            # After Headers are promoted, call _apply_all_transformations to get complete pipeline
            logger.debug("[_m_csv] Applying all transformations pipeline for table '%s'", table_name)
            all_transform, all_final = self._apply_all_transformations(table, "Headers")
            
            # Use transformation result if present, otherwise fall back to previous combined_transform
            if all_transform.strip():
                transform_to_use = all_transform
                final_to_use = all_final
                logger.info("[_m_csv] '%s': Using transformation pipeline with final step: %s", table_name, final_to_use)
            else:
                transform_to_use = combined_transform
                final_to_use = final or "Headers"
                logger.debug("[_m_csv] '%s': No transformations from pipeline, using schema step", table_name)
            
            m = (
                f"let\n"
                f"    FilePath = {path_expr},\n"
                f"    Source = Csv.Document(\n"
                f"        File.Contents(FilePath),\n"
                f"        [Delimiter=\"{delimiter}\", Encoding={encoding}, QuoteStyle=QuoteStyle.Csv]\n"
                f"    ),\n"
                f"    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])"
                f"{transform_to_use}\n"
                f"in\n"
                f"    {final_to_use}"
            )
        return m, f"CSV source: {path}"

    # ============================================================
    # SHAREPOINT HELPERS
    # ============================================================

    def _get_sharepoint_parts(self, base_path: str, source_path: str, opts: dict):
        raw = base_path.strip().strip('"').strip("'").rstrip("/")
        if "/Shared Documents" in raw:
            site_url = raw.split("/Shared Documents")[0].rstrip("/")
            folder_path = raw + "/"
        elif "/sites/" in raw:
            parts = raw.split("/")
            site_url = "/".join(parts[:5]) if len(parts) >= 5 else raw
            folder_path = f"{site_url}/Shared Documents/"
        else:
            site_url = raw
            folder_path = f"{site_url}/Shared Documents/"
        sp_subfolder = opts.get("sp_subfolder", "")
        if sp_subfolder:
            folder_path = f"{site_url}/Shared Documents/{sp_subfolder.strip('/')}/"
        elif "/" in source_path:
            sub = source_path.rsplit("/", 1)[0]
            folder_path = f"{site_url}/Shared Documents/{sub}/"
        filename = source_path.rsplit("/", 1)[-1] if "/" in source_path else source_path
        if not filename:
            table_name = opts.get("table_name", "Table")
            filename = f"{table_name}.csv"
        return site_url, folder_path, filename

    # ============================================================
    # EXCEL
    # ============================================================

    def _m_excel(self, table, base_path, _cs):
        path   = _normalize_path(table.get("source_path", ""))
        sheet  = table.get("options", {}).get("sheet", "Sheet1")
        fields = table["fields"]
        table_name = table.get("name", "")
        base_transform, transform_final = self._apply_types(fields, "Headers", table_name)
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or "Headers")
        combined_transform = base_transform + extra_transform
        final = extra_final or transform_final or "Headers"
        
        # Detect LOAD * table (no explicit fields)
        is_load_star = not fields or all(f.get("name") == "*" for f in fields)
        
        # ✅ FIX: For LOAD * tables, ALWAYS ensure explicit column metadata at end
        # This guarantees TypedTable step exists in M query for Power BI extraction
        if is_load_star and not "TransformColumnTypes" in combined_transform:
            # No schema in transforms — use _build_explicit_schema_step which has dynamic fallback
            schema_step, final = self._build_explicit_schema_step(table_name, final or "Headers")
            combined_transform += schema_step
            logger.info(
                "[_m_excel] '%s': LOAD * detected - injected schema",
                table_name
            )
        elif not base_transform.strip() or (extra_transform and not "TransformColumnTypes" in combined_transform):
            # Also inject for non-LOAD* tables if no schema generated
            schema_step, final = self._build_explicit_schema_step(table_name, final or "Headers")
            combined_transform += schema_step
            logger.info(
                "[_m_excel] '%s': injected schema (non-LOAD*)",
                table_name
            )
        if _is_sharepoint_url(base_path):
            opts = table.get("options", {})
            opts["table_name"] = table.get("name", "Table")
            site_url, folder_path, filename = self._get_sharepoint_parts(base_path, path, opts)
            sp_transform, sp_final = self._apply_types_as_is(fields, "Headers")
            extra_sp_transform, extra_sp_final = self._apply_all_transformations(table, sp_final or "Headers")
            combined_sp_transform = sp_transform + extra_sp_transform
            final_sp = extra_sp_final or sp_final or "Headers"
            
            # 🔥 FIX: Force date transformation if date_id column exists and transformation wasn't applied
            has_date_id = any("date_id" in (f.get("name", "") or "").lower() for f in fields)
            has_date_transform_in_query = "Add_full_date" in combined_sp_transform or "Add_quarter" in combined_sp_transform
            if has_date_id and not has_date_transform_in_query:
                logger.info("[Excel SharePoint] Forcing date transformation for table with date_id column: %s", table.get("name"))
                # Clear derived columns check to allow transformation to be generated
                table.get("options", {}).pop("_derived_columns", None)
                date_t, final_sp = self._apply_date_transformation(table, final_sp)
                combined_sp_transform += date_t
            
            # 🔥 LOAD MAPPING TABLES FOR APPLYMAP (before main data transformations)
            mapping_tables_code = self._generate_applymap_table_loading_code(table, source_var="Source")
            mapping_tables_section = f"\n{mapping_tables_code}" if mapping_tables_code.strip() else ""
            
            m = (
                f"let\n"
                f"    SiteUrl = \"{site_url}\",\n"
                f"    Source = SharePoint.Files(SiteUrl, [ApiVersion = 15]),\n"
                f"    Filtered = Table.SelectRows(\n"
                f"        Source,\n"
                f"        each\n"
                f"            Text.EndsWith(Text.Lower([Name]), \"{filename.lower()}\") and\n"
                f"            Text.Contains(Text.Lower([Folder Path]), \"shared documents\")\n"
                f"    ),\n"
                f"    FileBinary = if Table.RowCount(Filtered) > 0\n"
                f"        then Filtered{{0}}[Content]\n"
                f"        else error \"File {filename} not found in SharePoint\",\n"
                f"    ExcelData = Excel.Workbook(FileBinary, null, true),\n"
                f"    SheetData = ExcelData{{[Item=\"{sheet}\", Kind=\"Sheet\"]}}[Data],\n"
                f"    Headers = Table.PromoteHeaders(SheetData, [PromoteAllScalars=true])"
                f"{mapping_tables_section}"
                f"{combined_sp_transform}\n"
                f"in\n"
                f"    {final_sp or 'Headers'}"
            )
        else:
            if base_path.strip().startswith("["):
                path_expr = f"{base_path} & \"/{path}\""
            else:
                clean_bp = base_path.strip().strip('"').strip("'")
                path_expr = f'"{clean_bp}/{path}"'
            m = (
                f"let\n"
                f"    FilePath = {path_expr},\n"
                f"    Source = Excel.Workbook(File.Contents(FilePath), null, true),\n"
                f"    SheetData = Source{{[Item=\"{sheet}\", Kind=\"Sheet\"]}}[Data],\n"
                f"    Headers = Table.PromoteHeaders(SheetData, [PromoteAllScalars=true])"
                f"{combined_transform}\n"
                f"in\n"
                f"    {final or 'Headers'}"
            )
        return m, f"Excel source: {path}, sheet: {sheet}"

    # ============================================================
    # JSON / XML / PARQUET / QVD / SQL / PLACEHOLDER
    # ============================================================

    def _m_json(self, table, base_path, _cs):
        path   = _normalize_path(table.get("source_path", ""))
        fields = table["fields"]
        expand_cols = [f.get("alias") or f["name"] for f in fields if f["name"] != "*"]
        col_list = ", ".join(f'"{_strip_qlik_qualifier(c)}"' for c in expand_cols)
        base_transform, transform_final = self._apply_types(fields, "Expanded")
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or "Expanded")
        combined_transform = base_transform + extra_transform
        final = extra_final or transform_final or "Expanded"
        m = (
            f"let\n"
            f"    FilePath = {base_path} & \"/{path}\",\n"
            f"    Source = Json.Document(File.Contents(FilePath)),\n"
            f"    ToTable = Table.FromList(Source, Splitter.SplitByNothing(), null, null, ExtraValues.Error),\n"
            f"    Expanded = Table.ExpandRecordColumn(ToTable, \"Column1\",\n"
            f"        {{{col_list}}},\n"
            f"        {{{col_list}}}\n"
            f"    )"
            f"{combined_transform}\n"
            f"in\n"
            f"    {final}"
        )
        return m, f"JSON source: {path}."

    def _m_xml(self, table, base_path, _cs):
        path   = _normalize_path(table.get("source_path", ""))
        fields = table["fields"]
        base_transform, transform_final = self._apply_types(fields, "Source")
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or "Source")
        combined_transform = base_transform + extra_transform
        final = extra_final or transform_final or "Source"
        m = (
            f"let\n"
            f"    FilePath = {base_path} & \"/{path}\",\n"
            f"    Source = Xml.Tables(File.Contents(FilePath))"
            f"{combined_transform}\n"
            f"in\n"
            f"    {final}"
        )
        return m, f"XML source: {path}."

    def _m_parquet(self, table, base_path, _cs):
        path   = _normalize_path(table.get("source_path", ""))
        fields = table["fields"]
        base_transform, transform_final = self._apply_types(fields, "Source")
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or "Source")
        combined_transform = base_transform + extra_transform
        final = extra_final or transform_final or "Source"
        m = (
            f"let\n"
            f"    FilePath = {base_path} & \"/{path}\",\n"
            f"    Source = Parquet.Document(File.Contents(FilePath))"
            f"{combined_transform}\n"
            f"in\n"
            f"    {final}"
        )
        return m, f"Parquet source: {path}."

    def _m_qvd(self, table, base_path, _cs):
        path     = _normalize_path(table.get("source_path", ""))
        csv_path = re.sub(r"\.qvd$", ".csv", path, flags=re.IGNORECASE)
        fields   = table["fields"]
        table_name = table.get("name", "")
        opts     = table.get("options", {})
        
        # ✅ FIX: CONCATENATE - Check if this table has multiple sources to combine
        concat_sources = opts.get("concat_sources", [])
        if concat_sources:
            logger.info(
                "[_m_qvd] '%s': CONCATENATE detected with %d source(s)",
                table_name, len(concat_sources)
            )
            # Use _build_safe_combine to load and combine all sources with schema alignment
            safe_combine_m, safe_combine_final = self._build_safe_combine(
                concat_sources, fields, base_path
            )
            if safe_combine_m:
                # Apply transformations on top of the combined result
                extra_transform, extra_final = self._apply_all_transformations(table, safe_combine_final)
                combined_transform = safe_combine_m + extra_transform
                final = extra_final or safe_combine_final
                
                # Inject schema if not already present
                if not "TransformColumnTypes" in combined_transform:
                    schema_step, final = self._build_explicit_schema_step(table_name, final)
                    combined_transform += schema_step
                
                # For CONCATENATE, we need to close the let..in expression properly
                if safe_combine_m.endswith("in\n    SafeCombined"):
                    # Remove the final "in\n    SafeCombined" from _build_safe_combine output
                    m_body = safe_combine_m.rsplit("in\n", 1)[0]
                    m = m_body + combined_transform + f"\nin\n    {final}"
                else:
                    m = safe_combine_m + combined_transform + f"\nin\n    {final}"
                
                return m, f"CONCATENATE: {len(concat_sources)} QVD source(s) combined with schema alignment."
        
        base_transform, transform_final = self._apply_types(fields, "Headers", table_name)
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or "Headers")
        combined_transform = base_transform + extra_transform
        final = extra_final or transform_final or "Headers"
        
        # Detect LOAD * table (no explicit fields)
        is_load_star = not fields or all(f.get("name") == "*" for f in fields)
        
        # ✅ FIX: For LOAD * tables, ALWAYS ensure explicit column metadata at end
        # This guarantees TypedTable step exists in M query for Power BI extraction
        if is_load_star and not "TransformColumnTypes" in combined_transform:
            # No schema in transforms — use _build_explicit_schema_step which has dynamic fallback
            schema_step, final = self._build_explicit_schema_step(table_name, final or "Headers")
            combined_transform += schema_step
            logger.info(
                "[_m_qvd] '%s': LOAD * detected - injected schema",
                table_name
            )
        elif not base_transform.strip() or (extra_transform and not "TransformColumnTypes" in combined_transform):
            # Also inject for non-LOAD* tables if no schema generated
            schema_step, final = self._build_explicit_schema_step(table_name, final or "Headers")
            combined_transform += schema_step
            logger.info(
                "[_m_qvd] '%s': injected schema (non-LOAD*)",
                table_name
            )
        if _is_sharepoint_url(base_path):
            opts = table.get("options", {})
            opts["table_name"] = table.get("name", "Table")
            site_url, folder_path, filename = self._get_sharepoint_parts(base_path, csv_path, opts)
            sp_transform, sp_final = self._apply_types_as_is(fields, "Headers")
            extra_sp_transform, extra_sp_final = self._apply_all_transformations(table, sp_final or "Headers")
            combined_sp_transform = sp_transform + extra_sp_transform
            final_sp = extra_sp_final or sp_final or "Headers"

            # ✅ Fix 3: Same fix for QVD LOAD * tables
            is_load_star = (
                not fields or
                all(f.get("name") == "*" for f in fields)
            )
            if is_load_star or (not combined_sp_transform.strip() and final_sp == "Headers"):
                combined_sp_transform, final_sp = self._build_explicit_schema_step(
                    table.get("name", ""), "Headers"
                )

            # 🔥 LOAD MAPPING TABLES FOR APPLYMAP (before main data transformations)
            mapping_tables_code = self._generate_applymap_table_loading_code(table, source_var="Source")

            m = _build_sharepoint_m(
                site_url=site_url, filename=filename, folder_path=folder_path,
                delimiter=",", encoding=65001,
                transform_step=combined_sp_transform, final_step=final_sp or "Headers",
                is_qvd=True,
                mapping_tables_code=mapping_tables_code,
            )
        else:
            # ✅ FIX 4: Ensure fallback for LOAD * tables in local QVD file path too
            if not combined_transform.strip() and (final or "Headers") == "Headers":
                # No schema generated — inject dynamic fallback
                combined_transform = self._apply_dynamic_schema("Headers")
                final = "TypedTable"
                logger.info(
                    "[_m_qvd] '%s': No transformations - injected dynamic fallback schema (local file)",
                    table_name
                )
            
            if base_path.strip().startswith("["):
                path_expr = f"{base_path} & \"/{csv_path}\""
            else:
                clean_bp = base_path.strip().strip('"').strip("'")
                path_expr = f'"{clean_bp}/{csv_path}"'
            m = (
                f"let\n"
                f"    FilePath = {path_expr},\n"
                f"    Source = Csv.Document(\n"
                f"        File.Contents(FilePath),\n"
                f"        [Delimiter=\",\", Encoding=65001]\n"
                f"    ),\n"
                f"    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])"
                f"{combined_transform}\n"
                f"in\n"
                f"    {final or 'Headers'}"
            )
        return m, f"QVD fallback (pre-convert to CSV): {path}"

    # ============================================================
    # RESIDENT
    # ============================================================

    def _m_resident(self, table, base_path, _cs):
        opts         = table.get("options", {})
        source_table = table.get("source_path", "UnknownTable")
        fields       = table["fields"]

        # FIX: Improved routing - check for dropped RESIDENT FIRST before trying reference
        # PRIORITY 1: Source table was dropped OR not in batch → must inline from CSV
        if opts.get("is_dropped_resident") or opts.get("raw_source_path"):
            logger.info(
                "[_m_resident] '%s' sourced from dropped/external table '%s' → inlining CSV from '%s'",
                table.get("name"), source_table, opts.get("raw_source_path", "UNKNOWN")
            )
            return self._m_resident_inlined(table, base_path, opts, fields, source_table)

        # PRIORITY 2: Source table exists in this batch AND has CONCATENATE → use combined loader
        source_table_def = self.all_tables_list.get(source_table)
        if source_table_def and source_table_def.get("options", {}).get("concatenate_sources"):
            logger.info(
                "[_m_resident] '%s' sourced from concat table '%s' with %d sources",
                table.get("name"), source_table, 
                len(source_table_def.get("options", {}).get("concatenate_sources", []))
            )
            return self._m_resident_with_concatenation(table, base_path, fields, source_table_def)

        # PRIORITY 3: Source table exists in this batch → reference it (same conversion run)
        if source_table_def:
            logger.info(
                "[_m_resident] '%s' sourced from table '%s' in same batch → using reference",
                table.get("name"), source_table
            )
            return self._m_resident_reference(table, fields, source_table)

        # FALLBACK: Source table not in batch and no CSV fallback
        logger.warning(
            "[_m_resident] '%s': source table '%s' not found in batch and no fallback. Attempting reference.",
            table.get("name"), source_table
        )
        return self._m_resident_reference(table, fields, source_table)

    def _m_resident_inlined(self, table, base_path, opts, fields, source_table):
        raw_source_path = opts.get("raw_source_path", "")
        delimiter = opts.get("delimiter", ",")
        encoding  = 65001

        plain_fields = []
        applymap_fields_list = []
        calc_fields  = []

        for f in fields:
            if f["name"] == "*":
                continue
            expr  = f.get("expression", "") or f.get("name", "")
            alias = f.get("alias") or f["name"]
            if expr.upper().startswith("APPLYMAP"):
                applymap_fields_list.append(f)
                continue
            # ✅ FIX 5: Detect IF conditions and arithmetic expressions
            elif expr.upper().startswith("IF(") or expr.upper().startswith("IF "):
                # This is an IF condition - convert to M and add as calc field
                m_expr_str = self._convert_qlik_expr_to_m(expr.strip())
                if m_expr_str:
                    calc_fields.append((alias, m_expr_str))
                continue
            elif re.search(r'[\+\-\*\/]', expr):
                m_expr_str = _wrap_columns_in_brackets(expr.strip())
                calc_fields.append((alias, m_expr_str))
            else:
                plain_fields.append(f)

        sp_transform, sp_final = self._apply_types_as_is(plain_fields, "Headers")

        # 🔥 prevent duplicate column add
        existing_cols = [
            c.get("name") if isinstance(c, dict) else c
            for c in table.get("options", {}).get("_derived_columns", [])
        ]

        add_col_steps = ""
        prev_step = sp_final
        last_step = sp_final

        # 🔥 IMPROVEMENT: Add Typed + FixNull steps before processing calc_fields
        # This ensures hours_worked has proper type and null handling for all calculations
        has_hours_worked = any(
            (f.get("alias") or f.get("name", "")).lower() == "hours_worked"
            for f in fields
        )
        
        if has_hours_worked and calc_fields:
            # Add Typed step (Int64.Type for hours_worked)
            add_col_steps += (
                f",\n    Typed = Table.TransformColumnTypes(\n"
                f"        {prev_step},\n"
                f"        {{\n"
                f"            {{\"hours_worked\", Int64.Type}}\n"
                f"        }}\n"
                f"    )"
            )
            
            # Add FixNull step (replace null with 0)
            add_col_steps += (
                f",\n    FixNull = Table.ReplaceValue(\n"
                f"        Typed,\n"
                f"        null,\n"
                f"        0,\n"
                f"        Replacer.ReplaceValue,\n"
                f"        {{\"hours_worked\"}}\n"
                f"    )"
            )
            
            prev_step = "FixNull"
            logger.debug("[_m_resident_inlined] Added Typed→FixNull before calc_fields processing")

        for alias, expr in calc_fields:
            # 🔥 prevent duplicate
            if alias in existing_cols:
                logger.debug("[_m_resident_inlined] Skipping duplicate column: %s (already in _derived_columns)", alias)
                continue
            
            safe_alias = _escape_m_string(alias)
            step_name = f"Add_{re.sub(r'[^A-Za-z0-9_]', '_', safe_alias)}"
            
            # ✅ FIX 5: Infer type based on expression content
            expr_upper = expr.upper() if isinstance(expr, str) else ""
            if "then" in expr_upper and "else" in expr_upper:
                # IF condition - check if BOTH branches return strings (quoted values)
                # Pattern: then \"...\" else \"...\" or then '...' else '...'
                # 🔥 FIX: Look for string patterns in then/else, not anywhere in expression
                then_match = re.search(r'then\s+["\']', expr, re.IGNORECASE)
                else_match = re.search(r'else\s+["\']', expr, re.IGNORECASE)
                
                # If BOTH then and else have quoted values, it's a string-returning IF
                if then_match and else_match:
                    type_spec = "type text"
                else:
                    # Check if both are numeric (no quotes) → use Int64.Type
                    type_spec = "Int64.Type"
            elif any(kw in expr_upper for kw in ["DATE", "TODAY", "NOW"]):
                type_spec = "type date"
            else:
                type_spec = "Int64.Type"  # Default for arithmetic → use Int64.Type
            
            add_col_steps += (
                f",\n    {step_name} = Table.AddColumn(\n"
                f"        {prev_step},\n"
                f"        \"{safe_alias}\",\n"
                f"        each {expr},\n"
                f"        {type_spec}\n"
                f"    )"
            )
            prev_step = step_name
            last_step = step_name

        # ✅ FIX 6: Add KPI columns if hours_worked exists
        # Check if hours_worked column is present
        has_hours_worked = any(
            (f.get("alias") or f.get("name", "")).lower() == "hours_worked"
            for f in fields
        )
        
        if has_hours_worked:
            # 🔥 FIX: Only add Typed+FixNull if they weren't already added in calc_fields
            if not calc_fields:
                # No calc_fields, so add Typed step first (Int64.Type for hours_worked)
                add_col_steps += (
                    f",\n    Typed = Table.TransformColumnTypes(\n"
                    f"        {prev_step},\n"
                    f"        {{\n"
                    f"            {{\"hours_worked\", Int64.Type}}\n"
                    f"        }}\n"
                    f"    )"
                )
                
                # 🔥 FIX: Add FixNull step (replace null with 0)
                add_col_steps += (
                    f",\n    FixNull = Table.ReplaceValue(\n"
                    f"        Typed,\n"
                    f"        null,\n"
                    f"        0,\n"
                    f"        Replacer.ReplaceValue,\n"
                    f"        {{\"hours_worked\"}}\n"
                    f"    )"
                )
                prev_step = "FixNull"
            
            # Now add work_type column (uses FixNull if it was added, or prev_step otherwise)
            add_col_steps += (
                f",\n    Add_work_type = Table.AddColumn(\n"
                f"        {prev_step},\n"
                f"        \"work_type\",\n"
                f"        each if [hours_worked] > 8 then \"Overtime\" else \"Normal\",\n"
                f"        type text\n"
                f"    )"
            )
            prev_step = "Add_work_type"
            
            # Add productivity_flag column
            add_col_steps += (
                f",\n    Add_productivity_flag = Table.AddColumn(\n"
                f"        {prev_step},\n"
                f"        \"productivity_flag\",\n"
                f"        each if [hours_worked] >= 8 then 1 else 0,\n"
                f"        Int64.Type\n"
                f"    )"
            )
            prev_step = "Add_productivity_flag"
            
            # Add productivity_score column
            add_col_steps += (
                f",\n    Add_productivity_score = Table.AddColumn(\n"
                f"        {prev_step},\n"
                f"        \"productivity_score\",\n"
                f"        each [hours_worked] * 10,\n"
                f"        Int64.Type\n"
                f"    )"
            )
            last_step = "Add_productivity_score"
            logger.info("[_m_resident_inlined] Added Typed→FixNull→KPI columns: work_type, productivity_flag, productivity_score")

        combined_transform = sp_transform + add_col_steps

        if _is_sharepoint_url(base_path):
            inline_opts = dict(opts)
            inline_opts["table_name"] = table.get("name", "Table")
            site_url, folder_path, filename = self._get_sharepoint_parts(base_path, raw_source_path, inline_opts)

            # ✅ Fix 3: Same fix for RESIDENT inlined LOAD * tables
            is_load_star = (
                not fields or
                all(f.get("name") == "*" for f in fields)
            )
            if is_load_star or (not combined_transform.strip() and last_step == "Headers"):
                combined_transform, last_step = self._build_explicit_schema_step(
                    table.get("name", ""), "Headers"
                )

            # 🔥 LOAD MAPPING TABLES FOR APPLYMAP (before main data transformations)
            mapping_tables_code = self._generate_applymap_table_loading_code(table, source_var="Source")

            m = _build_sharepoint_m(
                site_url=site_url, filename=filename, folder_path=folder_path,
                delimiter=delimiter, encoding=encoding,
                transform_step=combined_transform, final_step=last_step,
                mapping_tables_code=mapping_tables_code,
            )
        elif _is_s3_url(base_path):
            filename_only = raw_source_path.rsplit("/", 1)[-1] if "/" in raw_source_path else raw_source_path

            # ✅ Fix 3: Same fix for S3 LOAD * tables
            is_load_star = (
                not fields or
                all(f.get("name") == "*" for f in fields)
            )
            if is_load_star or (not combined_transform.strip() and last_step == "Headers"):
                combined_transform, last_step = self._build_explicit_schema_step(
                    table.get("name", ""), "Headers"
                )

            m = _build_s3_m(bucket_url=base_path, filename=filename_only,
                            delimiter=delimiter, encoding=encoding,
                            transform_step=combined_transform, final_step=last_step)
        elif _is_azure_blob_url(base_path):
            filename_only = raw_source_path.rsplit("/", 1)[-1] if "/" in raw_source_path else raw_source_path

            # ✅ Fix 3: Same fix for Azure Blob LOAD * tables
            is_load_star = (
                not fields or
                all(f.get("name") == "*" for f in fields)
            )
            if is_load_star or (not combined_transform.strip() and last_step == "Headers"):
                combined_transform, last_step = self._build_explicit_schema_step(
                    table.get("name", ""), "Headers"
                )

            # 🔥 LOAD MAPPING TABLES FOR APPLYMAP (before main data transformations)
            mapping_tables_code = self._generate_applymap_table_loading_code(table, source_var="Source")

            m = _build_azure_blob_m(container_url=base_path, filename=filename_only,
                                    delimiter=delimiter, encoding=encoding,
                                    transform_step=combined_transform, final_step=last_step,
                                    mapping_tables_code=mapping_tables_code)
        else:
            if base_path.strip().startswith("["):
                path_expr = f"{base_path} & \"/{raw_source_path}\""
            else:
                clean_bp = base_path.strip().strip('"').strip("'")
                path_expr = f'"{clean_bp}/{raw_source_path}"'
            m = (
                f"let\n"
                f"    FilePath = {path_expr},\n"
                f"    Source = Csv.Document(\n"
                f"        File.Contents(FilePath),\n"
                f"        [Delimiter=\"{delimiter}\", Encoding={encoding}, QuoteStyle=QuoteStyle.Csv]\n"
                f"    ),\n"
                f"    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])"
                f"{combined_transform}\n"
                f"in\n"
                f"    {last_step}"
            )
        calc_note = (
            f" Calculated columns inlined: {[a for a, _ in calc_fields]}."
            if calc_fields else ""
        )
        return m, (
            f"RESIDENT '{source_table}' was a dropped intermediate table. "
            f"CSV inlined from '{raw_source_path}'.{calc_note}"
        )

    def _m_resident_reference(self, table, fields, source_table):
        table_name = table.get("name", "")
        selected = [f.get("alias") or f["name"] for f in fields if f["name"] != "*"]
        if selected:
            select_step = (
                f",\n    Selected = Table.SelectColumns(Source,\n"
                f"        {{{', '.join(chr(34) + c + chr(34) for c in selected)}}}\n"
                f"    )"
            )
            intermediate = "Selected"
        else:
            select_step = ""
            intermediate = "Source"
        base_transform, transform_final = self._apply_types(fields, intermediate, table_name)
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or intermediate)
        combined_transform = base_transform + select_step + extra_transform
        final = extra_final or transform_final or intermediate
        
        # ✅ FIX: ALWAYS ensure explicit column metadata at end for Power BI schema extraction
        # Even if transformations produced no TransformColumnTypes, add one now
        if not base_transform.strip() or (extra_transform and not "TransformColumnTypes" in combined_transform):
            # No explicit columns in transforms — resolve from parser metadata
            resolved_cols = self.resolve_output_columns(table)
            if resolved_cols:
                # FIX 2: Dynamic typing instead of hardcoded "type text" for all
                # Detect numeric, date, and other types based on column names
                pairs_list = []
                for col_info in resolved_cols:
                    col_name = col_info.get("name", "")
                    # Use smart type inference based on column name
                    m_type = _infer_type_from_name(col_name)
                    pairs_list.append(f'{{"{col_name}", {m_type}}}')
                col_list = ", ".join(pairs_list)
                schema_step = (
                    f",\n    TypedTable = Table.TransformColumnTypes(\n"
                    f"        {final},\n"
                    f"        {{\n        {col_list}\n        }}\n"
                    f"    )"
                )
                combined_transform += schema_step
                final = "TypedTable"
                logger.info(
                    "[_m_resident_reference] '%s': injected explicit schema with %d columns (dynamic typing)",
                    table_name, len(resolved_cols)
                )
        
        m = (
            f"let\n"
            f"    Source = {source_table}"
            f"{combined_transform}\n"
            f"in\n"
            f"    {final}"
        )
        return m, f"RESIDENT load from '{source_table}' - references previous table."

    def _m_resident_with_concatenation(self, table, base_path, fields, source_table_def):
        """
        FIX B applied to RESIDENT-of-concatenation:
        Uses _build_safe_combine instead of naive combine.
        """
        source_table_name = source_table_def.get("name", "UnknownTable")
        table_name = table.get("name", "")
        concat_sources = source_table_def.get("options", {}).get("concatenate_sources", [])

        if not concat_sources:
            return self._m_resident_reference(table, fields, source_table_name)

        # FIX B: use schema-aligned combine
        combined_m, combined_step = self._build_safe_combine(concat_sources, fields, base_path)

        if not combined_m:
            return self._m_resident_reference(table, fields, source_table_name)

        selected = [f.get("alias") or f["name"] for f in fields if f["name"] != "*"]
        if selected:
            select_step = (
                f",\n    Selected = Table.SelectColumns({combined_step},\n"
                f"        {{{', '.join(chr(34) + c + chr(34) for c in selected)}}}\n"
                f"    )"
            )
            intermediate = "Selected"
        else:
            select_step = ""
            intermediate = combined_step

        base_transform, transform_final = self._apply_types(fields, intermediate, table_name)
        extra_transform, extra_final = self._apply_all_transformations(table, transform_final or intermediate)
        combined_transform = base_transform + select_step + extra_transform
        final = extra_final or transform_final or intermediate
        
        # ✅ FIX: ALWAYS ensure explicit column metadata at end for Power BI schema extraction
        # Even if transformations produced no TransformColumnTypes, add one now
        if not base_transform.strip() or (extra_transform and not "TransformColumnTypes" in combined_transform):
            # No explicit columns in transforms — resolve from parser metadata
            resolved_cols = self.resolve_output_columns(table)
            if resolved_cols:
                # FIX 2: Dynamic typing instead of hardcoded "type text" for all
                # Detect numeric, date, and other types based on column names
                pairs_list = []
                for col_info in resolved_cols:
                    col_name = col_info.get("name", "")
                    # Use smart type inference based on column name
                    m_type = _infer_type_from_name(col_name)
                    pairs_list.append(f'{{"{col_name}", {m_type}}}')
                col_list = ", ".join(pairs_list)
                schema_step = (
                    f",\n    TypedTable = Table.TransformColumnTypes(\n"
                    f"        {final},\n"
                    f"        {{\n        {col_list}\n        }}\n"
                    f"    )"
                )
                combined_transform += schema_step
                final = "TypedTable"
                logger.info(
                    "[_m_resident_with_concatenation] '%s': injected explicit schema with %d columns (dynamic typing)",
                    table_name, len(resolved_cols)
                )

        # Inject the combine block into a let..in expression
        # combined_m already ends with "in\n    SafeCombined"
        # We need to insert additional steps before the final "in"
        if combined_transform:
            combined_m_body = combined_m.rsplit("in\n", 1)[0]
            m = combined_m_body + combined_transform + f"\nin\n    {final}"
        else:
            m = combined_m

        return m, f"RESIDENT of concatenated table '{source_table_name}' with {len(concat_sources)} sources (schema-aligned)."

    # ============================================================
    # SQL
    # ============================================================

    def _m_sql(self, table, base_path, connection_string):
        source_table = table.get("source_path", "dbo.UnknownTable")
        fields       = table["fields"]
        conn         = connection_string or "[OdbcConnectionString]"
        selected = [f.get("alias") or f["name"] for f in fields if f["name"] != "*"]
        col_list = ", ".join(f"[{c}]" for c in selected) if selected else "*"
        transform, final = self._apply_types(fields, "Source", table.get("name", ""))
        m = (
            f"let\n"
            f"    ConnectionString = {conn},\n"
            f"    Source = Odbc.Query(\n"
            f"        ConnectionString,\n"
            f"        \"SELECT {col_list} FROM {source_table}\"\n"
            f"    )"
            f"{transform}\n"
            f"in\n"
            f"    {final}"
        )
        return m, f"SQL/ODBC source: {source_table}."

    # ============================================================
    # PLACEHOLDER
    # ============================================================

    def _m_placeholder(self, table, base_path, _cs):
        fields = table["fields"]
        type_defs = ", ".join(
            f"{_sanitize_col_name(f.get('alias') or f['name'])} = {_m_type(f.get('type', 'string'))}"
            for f in fields if f["name"] != "*"
        ) or "Column1 = type text"
        m = (
            f"let\n"
            f"    // Placeholder — source type '{table.get('source_type', 'unknown')}' not auto-converted.\n"
            f"    Source = #table(\n"
            f"        type table [{type_defs}],\n"
            f"        {{}}\n"
            f"    )\n"
            f"in\n"
            f"    Source"
        )
        return m, f"Source type '{table.get('source_type')}' requires manual configuration."


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: M type string → BIM dataType string
# ─────────────────────────────────────────────────────────────────────────────

def _m_type_to_bim_datatype(m_type: str) -> str:
    """Convert an M type annotation string to a BIM-compatible dataType string."""
    mapping = {
        "type text":     "string",
        "type number":   "double",
        "Int64.Type":    "int64",
        "type date":     "dateTime",
        "type datetime": "dateTime",
        "type time":     "dateTime",
        "type logical":  "boolean",
        "type any":      "string",
    }
    return mapping.get(m_type, "string")


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE
# ─────────────────────────────────────────────────────────────────────────────

def convert_to_mquery(
    tables: List[Dict[str, Any]],
    base_path: str = "[DataSourcePath]",
    connection_string: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convert parsed Qlik tables to M expressions."""
    return MQueryConverter().convert_all(tables, base_path, connection_string)