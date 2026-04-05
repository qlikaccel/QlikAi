# CONCATENATE Logic Fix - Complete Implementation

## Problem Identified

The CONCATENATE logic in mquery_converter.py was **incomplete and non-functional**. When Qlik scripts contained:

```qlik
CONCATENATE (Activity)
LOAD ...
```

The converter was NOT actually loading and combining the multiple datasets. Instead, it was just trying to reference file names by name without loading them, resulting in invalid M Query.

## Root Cause

The old `_detect_and_apply_concatenate()` method was applying transforms AFTER the base table was already loaded:

```python
# ❌ WRONG - Just tries to reference sources by name:
source_refs = ", ".join([f"{src}" for src in concat_sources])
transform = f"Table.Combine({{{prev_step}{', ' + source_refs}}})"
```

This doesn't work because:
1. The source files were never loaded
2. Headers were never promoted
3. Column schemas were never aligned
4. Power Query had no valid source to combine

## Solution Implemented

**NEW: EARLY CONCATENATE DETECTION** in `_m_csv()` and `_m_qvd()` methods:

1. **Check for `concat_sources`** at the very beginning of file loading
2. **If found:** Call `_build_safe_combine()` which:
   - Loads EACH source file separately
   - Promotes headers on each table
   - Aligns column schemas using `Table.SelectColumns(..., MissingField.UseNull)`
   - Combines with `Table.Combine()`
3. **Then apply** any additional transformations on top of the combined result
4. **Finally inject** schema metadata

## Example Output M Query

### Before (❌ Broken):
```m
let
    Headers = Table.PromoteHeaders(...)
    Combined Tables = Table.Combine({Headers, Activity, Fact2})
in
    Combined Tables
```
Problem: `Activity` and `Fact2` undefined! Nothing to combine!

### After (✅ Fixed):
```m
let
    RawSource1 = Csv.Document(File.Contents(".../Activity.csv"), ...),
    RawHeaders1 = Table.PromoteHeaders(RawSource1, ...),
    AlignedSource1 = Table.SelectColumns(RawHeaders1, 
        {"activity_id", "hours_worked", "department_id", ...}, 
        MissingField.UseNull),
    
    RawSource2 = Csv.Document(File.Contents(".../Activity_Fact2.csv"), ...),
    RawHeaders2 = Table.PromoteHeaders(RawSource2, ...),
    AlignedSource2 = Table.SelectColumns(RawHeaders2,
        {"activity_id", "hours_worked", "department_id", ...},
        MissingField.UseNull),
    
    SafeCombined = Table.Combine({AlignedSource1, AlignedSource2}),
    
    TypedTable = Table.TransformColumnTypes(SafeCombined, {
        {"activity_id", type text},
        {"hours_worked", type number},
        {"department_id", type text}
    })
in
    TypedTable
```

Key benefits:
✅ All sources properly loaded
✅ Column schemas aligned (handles missing columns)
✅ Complete M expression with no undefined references
✅ Power BI Desktop can execute and refresh

## Qlik → M Query Mapping

| Qlik Script | M Query Generated |
|---|---|
| `Activity: LOAD * FROM activity.csv;` | Single file load |
| `CONCATENATE (Activity) LOAD ... FROM fact1.csv;` | First source loaded |
| `CONCATENATE (Activity) LOAD ... FROM fact2.csv;` | Second source loaded + combined with first |
| `CONCATENATE (Activity) LOAD ... FROM fact3.csv;` | Third source added to combine |
| Result in Activity table | `Table.Combine({source1_headers, source2_headers, source3_headers})` |

## How CONCATENATE Detection Works

### In qlik_script_parser.py:
1. Scans for `CONCATENATE (TargetTable)` patterns
2. Extracts each source file path
3. Stores in table options:
   ```python
   {"concatenate_sources": [
       {"source_path": "activity.csv"},
       {"source_path": "fact1.csv"},
       {"source_path": "fact2.csv"}
   ]}
   ```

### In mquery_converter.py (_m_csv):
1. Checks if `opts["concat_sources"]` exists
2. If yes:
   - Calls `_build_safe_combine(concat_sources, fields, base_path)`
   - Gets back fully-formed M query with all file loads, header promotions, schema alignment, and `Table.Combine()`
   - Applies any additional transformations (GROUP BY, IF, JOIN, etc.)
   - Returns complete M expression

## Non-Breaking Changes

✅ **Existing single-file loads still work** - No change to those code paths
✅ **CONCATENATE transform layer still intact** - For any edge case we missed
✅ **All transformations preserved** - IF conditions, GROUP BY, JOIN, KEEP still applied
✅ **Existing code flow unchanged** - Just added early detection + routing

## Files Modified

1. **mquery_converter.py**
   - `_m_csv()` method: Added CONCATENATE detection at start (line ~1760)
   - `_m_qvd()` method: Added CONCATENATE detection at start (line ~2130)
   - Logic: Check concat_sources → use _build_safe_combine() → apply transforms → return

2. **No changes to:**
   - `_build_safe_combine()` - Already correct, now properly used
   - `_build_naive_combine()` - Fallback for edge cases
   - Parser logic - Already detecting CONCATENATE correctly
   - Other transformation methods - Still work as before

## Testing

To verify CONCATENATE works:

```qlik
Activity:
LOAD *
FROM [data/activity1.csv];

CONCATENATE (Activity)
LOAD *
FROM [data/activity2.csv];

CONCATENATE (Activity)
LOAD *
FROM [data/activity3.csv];

Final_Activity:
LOAD *
RESIDENT Activity;
```

Expected M Query flow:
1. Load activity1.csv → RawHeaders1 → AlignedSource1
2. Load activity2.csv → RawHeaders2 → AlignedSource2
3. Load activity3.csv → RawHeaders3 → AlignedSource3
4. Combine all three: `Table.Combine({AlignedSource1, AlignedSource2, AlignedSource3})`
5. Final_Activity references the combined result

Power BI will see all rows from all 3 CSV files as a single table.

## Debugging

If CONCATENATE still looks wrong, check these logs:

```python
INFO:[_m_csv] '%s': CONCATENATE detected with %d source(s)
INFO:[_build_safe_combine] Combined %d sources with %d aligned columns
```

These confirm:
1. ✅ CONCATENATE was detected
2. ✅ All sources were loaded
3. ✅ Columns were aligned

Without these logs, the table doesn't have concat_sources set (check parser output).
