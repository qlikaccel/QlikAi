from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from relationship_normalizer import RelationshipSchema

PBI_API_ROOT = "powerbi://api.powerbi.com/v1.0/myorg/powerbi"


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name, default)
    return val.strip() if isinstance(val, str) else val


def _is_guid(value: Optional[str]) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value or ""))


def _canonical_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _safe_m_identifier(column_name: str) -> str:
    name = (column_name or "").strip()
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return name
    escaped = name.replace('"', '""')
    return f'#"{escaped}"'


def _map_qlik_type_to_tabular(raw_type: str) -> str:
    value = (raw_type or "").strip().lower()
    mapping = {
        "string": "string",
        "text": "string",
        "varchar": "string",
        "char": "string",
        "int": "int64",
        "integer": "int64",
        "long": "int64",
        "bigint": "int64",
        "decimal": "double",
        "number": "double",
        "numeric": "double",
        "double": "double",
        "float": "double",
        "real": "double",
        "date": "dateTime",
        "datetime": "dateTime",
        "timestamp": "dateTime",
        "time": "dateTime",
        "bool": "boolean",
        "boolean": "boolean",
    }
    return mapping.get(value, "string")


def _map_tabular_to_m_type(tabular_type: str) -> str:
    value = (tabular_type or "").strip().lower()
    mapping = {
        "int64": "Int64.Type",
        "double": "type number",
        "boolean": "type logical",
        "datetime": "type datetime",
        "dateTime": "type datetime",
        "string": "type text",
    }
    return mapping.get(value, "type text")


def _resolve_workspace_name(access_token: str, workspace_id: str) -> Optional[str]:
    try:
        url = f"{PBI_API_ROOT}/groups/{workspace_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None
        body = response.json() if response.text else {}
        name = str(body.get("name", "")).strip()
        return name or None
    except Exception:
        return None


def resolve_xmla_server(workspace_id: Optional[str], access_token: Optional[str] = None) -> str:
    explicit = _env("POWERBI_XMLA_ENDPOINT")
    if explicit:
        return explicit

    if not workspace_id:
        raise RuntimeError("Missing POWERBI_XMLA_ENDPOINT and no workspace_id provided")

    ws = workspace_id.strip()
    if not ws:
        raise RuntimeError("workspace_id is empty")

    # XMLA endpoint expects workspace name, not GUID.
    if _is_guid(ws):
        if access_token:
            ws_name = _resolve_workspace_name(access_token=access_token, workspace_id=ws)
            print(f"Workspace name resolved: {ws_name}")
            if ws_name:
                return f"powerbi://api.powerbi.com/v1.0/myorg/{ws_name}"
        raise RuntimeError(
            "XMLA endpoint requires workspace name. Set POWERBI_XMLA_ENDPOINT in .env "
            "or provide a resolvable workspace with valid access token."
        )
        
    return f"powerbi://api.powerbi.com/v1.0/myorg/{ws}"


def execute_tmsl_xmla(
    tmsl_payload: Dict[str, Any],
    workspace_id: Optional[str],
    database: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a TMSL payload against XMLA endpoint via Invoke-ASCmd.
    """
    xmla_server = resolve_xmla_server(workspace_id=workspace_id, access_token=access_token)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as fp:
        json.dump(tmsl_payload, fp)
        temp_path = fp.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as sf:
        sf.write(
            """param(
    [Parameter(Mandatory=$true)][string]$Server,
    [Parameter(Mandatory=$true)][string]$TmslPath,
    [string]$Database
)

if ([string]::IsNullOrWhiteSpace($TmslPath) -or -not (Test-Path -LiteralPath $TmslPath)) {
    throw "TMSL file path is invalid or empty: '$TmslPath'"
}

if (-not (Get-Command Invoke-ASCmd -ErrorAction SilentlyContinue)) {
    try { Import-Module SqlServer -ErrorAction Stop } catch {}
}
if (-not (Get-Command Invoke-ASCmd -ErrorAction SilentlyContinue)) {
    try { Import-Module SqlServerPreview -ErrorAction Stop } catch {}
}
if (-not (Get-Command Invoke-ASCmd -ErrorAction SilentlyContinue)) {
    try {
        Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction SilentlyContinue
        Install-Module SqlServer -Scope CurrentUser -Force -AllowClobber -ErrorAction Stop
        Import-Module SqlServer -ErrorAction Stop
    } catch {}
}
if (-not (Get-Command Invoke-ASCmd -ErrorAction SilentlyContinue)) {
    throw "Invoke-ASCmd cmdlet not found. Install module: Install-Module SqlServer -Scope CurrentUser"
}

$query = Get-Content -Path $TmslPath -Raw -Encoding UTF8
if ([string]::IsNullOrWhiteSpace($Database)) {
    Invoke-ASCmd -Server $Server -Query $query
} else {
    Invoke-ASCmd -Server $Server -Database $Database -Query $query
}
"""
        )
        script_path = sf.name

    try:
        powershell_exe = (
            _env("POWERSHELL_EXE")
            or shutil.which("pwsh")
            or shutil.which("powershell")
            or "powershell"
        )
        pwsh_cmd = [
            powershell_exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            "-Server",
            xmla_server,
            "-TmslPath",
            temp_path,
        ]
        if database:
            pwsh_cmd.extend(["-Database", database])

        proc = subprocess.run(pwsh_cmd, capture_output=True, text=True, check=False)
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        combined = "\n".join(p for p in [stderr, stdout] if p)
        combined_lower = combined.lower()

        if proc.returncode != 0:
            if "invoke-ascmd cmdlet not found" in combined_lower:
                raise RuntimeError(
                    "Invoke-ASCmd is not available. Install SqlServer PowerShell module "
                    "using: Install-Module SqlServer -Scope CurrentUser"
                )
            raise RuntimeError(combined or "Invoke-ASCmd failed")

        # Some PowerShell runs can return code 0 while writing command errors in output.
        error_signatures = [
            "parameterbindingvalidationexception",
            "commandnotfoundexception",
            "is not recognized as the name of a cmdlet",
            "cannot bind argument to parameter",
            "xmla endpoint requires workspace name",
            "invoke-ascmd cmdlet not found",
        ]
        if any(sig in combined_lower for sig in error_signatures):
            raise RuntimeError(combined or "XMLA execution reported errors")
        return {
            "success": True,
            "server": xmla_server,
            "database": database,
            "output": stdout,
        }
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        try:
            os.remove(script_path)
        except OSError:
            pass


def _infer_scalar_type(values: List[str]) -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip() != ""]
    if not cleaned:
        return "string"

    def _is_int(v: str) -> bool:
        return bool(re.fullmatch(r"[+-]?\d+", v))

    def _is_float(v: str) -> bool:
        return bool(re.fullmatch(r"[+-]?(\d+(\.\d+)?|\.\d+)", v))

    def _is_bool(v: str) -> bool:
        return v.lower() in {"true", "false", "yes", "no", "0", "1"}

    def _is_datetime(v: str) -> bool:
        candidates = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        ]
        for fmt in candidates:
            try:
                datetime.strptime(v, fmt)
                return True
            except ValueError:
                continue
        return False

    if all(_is_int(v) for v in cleaned):
        return "int64"
    if all(_is_float(v) for v in cleaned):
        return "double"
    if all(_is_bool(v) for v in cleaned):
        return "boolean"
    if all(_is_datetime(v) for v in cleaned):
        return "dateTime"
    return "string"


def _extract_csv_metadata(csv_table_payloads: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    csv_meta: Dict[str, Dict[str, Any]] = {}
    for table_name, csv_text in (csv_table_payloads or {}).items():
        raw_text = csv_text if isinstance(csv_text, str) else ""
        if not table_name or not raw_text.strip():
            continue

        reader = csv.DictReader(io.StringIO(raw_text))
        headers = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
        if not headers:
            continue

        samples: Dict[str, List[str]] = {h: [] for h in headers}
        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > 2000:
                continue
            for header in headers:
                samples[header].append((row.get(header) or "").strip())

        columns = [
            {"name": header, "dataType": _infer_scalar_type(samples.get(header, []))}
            for header in headers
        ]

        csv_meta[_canonical_name(table_name)] = {
            "name": table_name.strip(),
            "columns": columns,
            "row_count": row_count,
            "source": "csv",
        }

    return csv_meta


def _extract_qlik_columns(table: Dict[str, Any]) -> List[Dict[str, str]]:
    raw_fields = table.get("fields") or table.get("columns") or []
    columns: List[Dict[str, str]] = []
    seen = set()

    for field in raw_fields:
        if isinstance(field, str):
            name = field.strip()
            data_type = "string"
        else:
            name = str(field.get("name", "")).strip()
            data_type = _map_qlik_type_to_tabular(field.get("type") or field.get("data_type") or "string")

        if not name:
            continue
        col_key = _canonical_name(name)
        if col_key in seen:
            continue
        seen.add(col_key)
        columns.append({"name": name, "dataType": data_type})

    return columns


def _merge_table_metadata(
    qlik_tables: List[Dict[str, Any]],
    csv_metadata: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    used_csv_keys = set()

    for table in qlik_tables or []:
        table_name = str(table.get("name", "")).strip()
        if not table_name:
            continue

        canonical_table = _canonical_name(table_name)
        qlik_columns = _extract_qlik_columns(table)
        qlik_lookup = {_canonical_name(c["name"]): c for c in qlik_columns}

        csv_table = csv_metadata.get(canonical_table)
        if csv_table:
            used_csv_keys.add(canonical_table)
            for csv_col in csv_table.get("columns", []):
                csv_key = _canonical_name(csv_col.get("name", ""))
                if not csv_key:
                    continue
                if csv_key not in qlik_lookup:
                    qlik_lookup[csv_key] = dict(csv_col)
                    continue

                # Metadata enhance: if Qlik type is generic text, promote using CSV inference.
                existing_type = qlik_lookup[csv_key].get("dataType", "string").lower()
                inferred_type = str(csv_col.get("dataType", "string")).lower()
                if existing_type == "string" and inferred_type != "string":
                    qlik_lookup[csv_key]["dataType"] = inferred_type

        merged.append(
            {
                "name": table_name,
                "columns": list(qlik_lookup.values()),
                "source": "qlik_schema_enhanced",
                "row_count": (csv_table or {}).get("row_count", table.get("no_of_rows", 0)),
            }
        )

    for csv_key, csv_table in csv_metadata.items():
        if csv_key in used_csv_keys:
            continue
        merged.append(
            {
                "name": csv_table.get("name", "CSV_Table"),
                "columns": csv_table.get("columns", []),
                "source": "csv_only",
                "row_count": csv_table.get("row_count", 0),
            }
        )

    return merged


def _relationship_cardinality(raw_value: str) -> str:
    value = (raw_value or "").strip().lower()
    mapping = {
        "manytoone": "manyToOne",
        "many:1": "manyToOne",
        "*:1": "manyToOne",
        "onetomany": "oneToMany",
        "1:many": "oneToMany",
        "1:*": "oneToMany",
        "onetoone": "oneToOne",
        "1:1": "oneToOne",
        "manytomany": "manyToMany",
        "*:*": "manyToMany",
    }
    return mapping.get(value, "manyToOne")


def _relationship_cross_filter(raw_value: str) -> str:
    value = (raw_value or "").strip().lower()
    if value in {"both", "bothdirections", "bidirectional", "bothdirection"}:
        return "bothDirections"
    return "oneDirection"


def _build_relationship_objects(
    relationships: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    table_name_lookup = {_canonical_name(t["name"]): t["name"] for t in tables}
    column_lookup: Dict[str, Dict[str, str]] = {}
    for t in tables:
        table_key = _canonical_name(t["name"])
        column_lookup[table_key] = {
            _canonical_name(c["name"]): c["name"] for c in t.get("columns", [])
        }

    tmsl_relationships: List[Dict[str, Any]] = []
    seen = set()
    for rel in relationships or []:
        from_table = rel.get("fromTable") or rel.get("from_table")
        from_column = rel.get("fromColumn") or rel.get("from_column")
        to_table = rel.get("toTable") or rel.get("to_table")
        to_column = rel.get("toColumn") or rel.get("to_column")
        if not all([from_table, from_column, to_table, to_column]):
            continue

        from_table_key = _canonical_name(str(from_table))
        to_table_key = _canonical_name(str(to_table))
        actual_from_table = table_name_lookup.get(from_table_key)
        actual_to_table = table_name_lookup.get(to_table_key)
        if not actual_from_table or not actual_to_table:
            continue

        actual_from_column = column_lookup.get(from_table_key, {}).get(_canonical_name(str(from_column)))
        actual_to_column = column_lookup.get(to_table_key, {}).get(_canonical_name(str(to_column)))
        if not actual_from_column or not actual_to_column:
            continue

        key = (
            _canonical_name(actual_from_table),
            _canonical_name(actual_from_column),
            _canonical_name(actual_to_table),
            _canonical_name(actual_to_column),
        )
        if key in seen:
            continue
        seen.add(key)

        rel_name = rel.get("name") or f"{actual_from_table}_{actual_to_table}_{actual_from_column}"
        tmsl_relationships.append(
            {
                "name": str(rel_name),
                "fromTable": actual_from_table,
                "fromColumn": actual_from_column,
                "toTable": actual_to_table,
                "toColumn": actual_to_column,
                "cardinality": _relationship_cardinality(str(rel.get("cardinality", "ManyToOne"))),
                "crossFilteringBehavior": _relationship_cross_filter(
                    str(
                        rel.get("crossFilteringBehavior")
                        or rel.get("cross_filtering_behavior")
                        or "bothDirections"
                    )
                ),
                "isActive": bool(rel.get("isActive", rel.get("is_active", True))),
            }
        )

    return tmsl_relationships


def _build_semantic_model_tmsl(
    dataset_name: str,
    tables: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, Any]:
    model_tables: List[Dict[str, Any]] = []
    for table in tables:
        table_name = table["name"]
        raw_columns = table.get("columns", [])
        columns = [
            {
                "name": c["name"],
                "dataType": c["dataType"],
                "sourceColumn": c["name"],
            }
            for c in raw_columns
            if c.get("name")
        ]
        if not columns:
            columns = [{"name": "Placeholder", "dataType": "string", "sourceColumn": "Placeholder"}]

        m_fields = ", ".join(
            f"{_safe_m_identifier(c['name'])} = {_map_tabular_to_m_type(c['dataType'])}"
            for c in columns
        )
        empty_table_expr = "    Empty = #table(type table [{}], {{}})".format(m_fields)
        partition_name = re.sub(r"[^A-Za-z0-9_]", "_", table_name).strip("_") or "Partition"

        model_tables.append(
            {
                "name": table_name,
                "columns": columns,
                "partitions": [
                    {
                        "name": f"{partition_name}_Import",
                        "mode": "import",
                        "source": {
                            "type": "m",
                            "expression": [
                                "let",
                                empty_table_expr,
                                "in",
                                "    Empty",
                            ],
                        },
                    }
                ],
                "annotations": [
                    {"name": "source", "value": str(table.get("source", "qlik_schema"))},
                    {"name": "row_count_hint", "value": str(table.get("row_count", 0))},
                ],
            }
        )

    model_relationships = _build_relationship_objects(relationships, tables)

    return {
        "createOrReplace": {
            "object": {"database": dataset_name},
            "database": {
                "name": dataset_name,
                "compatibilityLevel": 1567,
                "model": {
                    "culture": "en-US",
                    "defaultPowerBIDataSourceVersion": "powerBI_V3",
                    "tables": model_tables,
                    "relationships": model_relationships,
                },
            },
        }
    }


def _find_dataset_id_by_name(
    access_token: Optional[str],
    workspace_id: str,
    dataset_name: str,
) -> Optional[str]:
    if not access_token:
        return None

    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{PBI_API_ROOT}/groups/{workspace_id}/datasets"
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        return None

    datasets = response.json().get("value", []) if response.text else []
    target = dataset_name.strip().lower()
    for ds in datasets:
        if str(ds.get("name", "")).strip().lower() == target:
            return ds.get("id")
    return None


def create_semantic_model_via_xmla(
    dataset_name: str,
    workspace_id: str,
    qlik_tables: List[Dict[str, Any]],
    normalized_relationships: Optional[List[Dict[str, Any]]] = None,
    csv_table_payloads: Optional[Dict[str, str]] = None,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create/replace an enhanced semantic model in Power BI via XMLA.

    This path does not require Power BI Desktop and is intended to make the
    service-side semantic model editable ("Open semantic model" enabled when tenant/workspace allows).
    """
    if not dataset_name:
        raise ValueError("dataset_name is required")
    if not workspace_id:
        raise ValueError("workspace_id is required")

    csv_metadata = _extract_csv_metadata(csv_table_payloads or {})
    merged_tables = _merge_table_metadata(qlik_tables, csv_metadata)
    if not merged_tables:
        return {
            "success": False,
            "message": "No tables available to build semantic model",
            "error": "tables_empty",
        }

    tmsl_payload = _build_semantic_model_tmsl(
        dataset_name=dataset_name,
        tables=merged_tables,
        relationships=normalized_relationships or [],
    )
    xmla_exec = execute_tmsl_xmla(
        tmsl_payload=tmsl_payload,
        workspace_id=workspace_id,
        database=None,
        access_token=access_token,
    )

    dataset_id = _find_dataset_id_by_name(
        access_token=access_token,
        workspace_id=workspace_id,
        dataset_name=dataset_name,
    )

    return {
        "success": True,
        "status": "success",
        "method": "XMLA",
        "message": "Enhanced semantic model created via XMLA",
        "dataset_name": dataset_name,
        "dataset_id": dataset_id,
        "tables_created": len(merged_tables),
        "relationships_applied": len(
            _build_relationship_objects(normalized_relationships or [], merged_tables)
        ),
        "csv_tables_used": len(csv_metadata),
        "workspace_id": workspace_id,
        "workspace_url": f"https://app.powerbi.com/groups/{workspace_id}",
        "dataset_url": (
            f"https://app.powerbi.com/groups/{workspace_id}/datasets/{dataset_id}"
            if dataset_id
            else None
        ),
        "xmla_server": xmla_exec.get("server"),
        "xmla_output": xmla_exec.get("output", ""),
    }


def _build_tmsl(schema: RelationshipSchema) -> Dict[str, Any]:
    rel_objects = []
    for rel in schema.relationships:
        rel_objects.append(
            {
                "name": rel.relationship_name,
                "fromTable": rel.from_table,
                "fromColumn": rel.from_column,
                "toTable": rel.to_table,
                "toColumn": rel.to_column,
                "crossFilteringBehavior": "BothDirections" if rel.direction == "Both" else "OneDirection",
                "isActive": bool(rel.is_active),
                "cardinality": rel.cardinality,
            }
        )

    return {
        "createOrReplace": {
            "object": {"database": schema.dataset_name},
            "database": {
                "name": schema.dataset_name,
                "model": {
                    "relationships": rel_objects
                },
            },
        }
    }


def _apply_via_xmla(schema: RelationshipSchema, dataset_id: str, workspace_id: Optional[str]) -> Dict[str, Any]:
    tmsl = _build_tmsl(schema)
    exec_result = execute_tmsl_xmla(
        tmsl_payload=tmsl,
        workspace_id=workspace_id,
        database=schema.dataset_name,
    )
    return {
        "method": "XMLA",
        "created": len(schema.relationships),
        "failed": 0,
        "details": [{"relationship": r.relationship_name, "status": "created"} for r in schema.relationships],
        "raw_output": exec_result.get("output", ""),
        "dataset_id": dataset_id,
    }


def _apply_via_rest(schema: RelationshipSchema, dataset_id: str, workspace_id: Optional[str]) -> Dict[str, Any]:
    # Placeholder for REST-based relationship creation if your tenant exposes this operation.
    # For many tenants, relationship write is effectively done through XMLA/TOM.
    details = []
    for rel in schema.relationships:
        details.append(
            {
                "relationship": rel.relationship_name,
                "status": "skipped",
                "reason": "REST relationship write not configured; use XMLA",
            }
        )

    return {
        "method": "REST",
        "created": 0,
        "failed": len(schema.relationships),
        "details": details,
        "dataset_id": dataset_id,
        "workspace_id": workspace_id,
    }


def apply_normalized_relationships_to_powerbi(
    dataset_name: str,
    dataset_id: str,
    schema: RelationshipSchema,
    workspace_id: Optional[str] = None,
    use_xmla: bool = False,
) -> Dict[str, Any]:
    if not dataset_name or not dataset_id:
        raise ValueError("dataset_name and dataset_id are required")

    if not schema.relationships:
        return {"method": "none", "created": 0, "failed": 0, "details": []}

    if use_xmla:
        return _apply_via_xmla(schema=schema, dataset_id=dataset_id, workspace_id=workspace_id)

    return _apply_via_rest(schema=schema, dataset_id=dataset_id, workspace_id=workspace_id)
