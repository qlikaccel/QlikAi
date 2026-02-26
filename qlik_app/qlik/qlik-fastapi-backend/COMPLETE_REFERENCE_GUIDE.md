# 📚 COMPLETE REFERENCE GUIDE - Qlik to PowerBI M Query Conversion

## ✨ Feature Overview

Your project now has a production-ready feature to:

1. **Fetch LoadScript** from Qlik Cloud with logging
2. **Parse LoadScript** to identify tables, fields, connections, transformations  
3. **Convert to PowerBI M Query** in Power Query language
4. **Download as .m file** for immediate use in Power BI

All with **comprehensive phase-by-phase logging** so you can verify each step!

---

## 🎯 Quick Navigation

- [📋 What Was Added](#what-was-added)
- [🚀 How to Use](#how-to-use)
- [📊 Logging Output](#logging-output)
- [🔌 API Endpoints](#api-endpoints)
- [💻 Code Examples](#code-examples)
- [🧪 Testing](#testing)
- [📝 File Reference](#file-reference)
- [🔍 Troubleshooting](#troubleshooting)

---

## 📋 What Was Added

### New Python Modules (3 files)

| File | Purpose | Phases |
|------|---------|--------|
| `loadscript_fetcher.py` | Fetch from QlikCloud | 1-4 |
| `loadscript_parser.py` | Parse & extract components | 5 |
| `loadscript_converter.py` | Convert to M Query | 6 |

### Updated Files (1 file)

| File | Changes |
|------|---------|
| `migration_api.py` | Added 5 new endpoints |

### Documentation Files (4 files)

| File | Content |
|------|---------|
| `README_LOADSCRIPT_CONVERSION.md` | Quick start guide |
| `LOADSCRIPT_CONVERSION_GUIDE.py` | Complete API docs |
| `IMPLEMENTATION_SUMMARY.md` | Implementation details |
| `test_loadscript_feature.py` | Test script |

---

## 🚀 How to Use

### Option A: One-Click Pipeline (Recommended)

```bash
# Execute all 6 phases in one call
curl -X POST "http://localhost:8000/api/migration/full-pipeline?app_id=YOUR_QLIK_APP_ID"
```

**Response includes:**
- All fetched, parsed, and converted data
- M Query ready to use
- Complete statistics

### Option B: Step-by-Step

```bash
# Step 1: Fetch
curl -X POST "http://localhost:8000/api/migration/fetch-loadscript?app_id=YOUR_APP_ID"

# Step 2: Parse (use loadscript from Step 1)
curl -X POST "http://localhost:8000/api/migration/parse-loadscript?loadscript=SCRIPT_HERE"

# Step 3: Convert (use parsed result from Step 2)
curl -X POST "http://localhost:8000/api/migration/convert-to-mquery?parsed_script_json={...}"

# Step 4: Download
curl -X POST "http://localhost:8000/api/migration/download-mquery?m_query=..." -o query.m
```

### Option C: Python Code

```python
import requests
import json

# Full pipeline
resp = requests.post(
    "http://localhost:8000/api/migration/full-pipeline",
    params={"app_id": "YOUR_APP_ID"}
)

data = resp.json()
m_query = data['m_query']

# Save to file
with open("powerbi_query.m", "w") as f:
    f.write(m_query)

print("✅ Done!")
```

---

## 📊 Logging Output

### Phase 1-4: Fetch

```
================================================================================
PHASE 0: Initializing LoadScript Fetcher
================================================================================
✅ Initialized with Tenant URL: https://c8vlzp3sx6akvnh.in.qlikcloud.com
✅ API Base URL: https://c8vlzp3sx6akvnh.in.qlikcloud.com/api/v1

================================================================================
PHASE 1: Testing Connection to Qlik Cloud
================================================================================
🔌 Testing connection to: https://.../users/me
📊 Response Status Code: 200
✅ Connection successful!
✅ User ID: 6979dd842f92a48dc7c29bc7
```

### Phase 5: Parse

```
================================================================================
PHASE 5: PARSING LOADSCRIPT
================================================================================
📊 Input Script Length: 5432 characters
📍 Step 5.1: Extracting comments...
✅ Found 3 comment block(s)

📍 Step 5.2: Extracting LOAD statements...
✅ Found 8 LOAD statement(s)

📍 Step 5.3: Extracting table names...
✅ Found 5 table(s)
   ✓ Table: Customers
   ✓ Table: Orders
   ✓ Table: Products
```

### Phase 6: Convert

```
================================================================================
PHASE 6: CONVERTING TO POWERBI M QUERY
================================================================================
📍 Step 6.1: Converting data connections...
✅ Converted 2 connection(s)

📍 Step 6.2: Converting table definitions...
✅ Converted 5 table(s)

📍 Step 6.3: Converting field definitions...
✅ Generated 24 field transformation(s)
```

---

## 🔌 API Endpoints

### 1. Fetch LoadScript (Phases 1-4)

```
POST /api/migration/fetch-loadscript

Parameters:
  - app_id (required): Your Qlik Cloud app ID

Response:
{
  "status": "success",
  "app_id": "...",
  "app_name": "Sales Dashboard",
  "loadscript": "// Script content...",
  "script_length": 5432,
  "timestamp": "2026-02-25T10:30:45"
}
```

### 2. Parse LoadScript (Phase 5)

```
POST /api/migration/parse-loadscript

Parameters:
  - loadscript (required): Script content to parse

Response:
{
  "status": "success",
  "summary": {
    "tables_count": 5,
    "fields_count": 24,
    "connections_count": 2,
    "transformations_count": 6,
    "joins_count": 2
  },
  "details": {
    "tables": [...],
    "fields": [...],
    ...
  }
}
```

### 3. Convert to M Query (Phase 6)

```
POST /api/migration/convert-to-mquery

Parameters:
  - parsed_script_json (required): Parsed script as JSON string

Response:
{
  "status": "success",
  "m_query": "let\n  Source = ...",
  "query_length": 8500,
  "warnings_count": 2,
  "errors_count": 0,
  "statistics": {...}
}
```

### 4. Download M Query

```
POST /api/migration/download-mquery

Parameters:
  - m_query (required): The M query code
  - filename (optional): Output filename (default: powerbi_query.m)

Response:
Binary .m file download
```

### 5. Full Pipeline (Phases 1-6)

```
POST /api/migration/full-pipeline

Parameters:
  - app_id (required): Your Qlik Cloud app ID
  - auto_download (optional): Auto-download result

Response:
{
  "status": "success",
  "phases": {
    "phase_1_4_fetch": {...},
    "phase_5_parse": {...},
    "phase_6_convert": {...}
  },
  "m_query": "..."
}
```

---

## 💻 Code Examples

### Example 1: Complete Python Workflow

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/migration"

# Execute full pipeline
print("🔄 Executing full pipeline...")
response = requests.post(
    f"{BASE_URL}/full-pipeline",
    params={"app_id": "YOUR_QLIK_APP_ID"}
)

if response.status_code != 200:
    print(f"❌ Failed: {response.text}")
    exit(1)

data = response.json()

# Extract results
loadscript = data['detailed_results']['fetch_result']['loadscript']
parsed = data['detailed_results']['parse_result']
m_query = data['m_query']

# Show statistics
print(f"✅ Pipeline complete!")
print(f"   Tables: {parsed['summary']['tables_count']}")
print(f"   Fields: {parsed['summary']['fields_count']}")
print(f"   M Query: {len(m_query)} characters")

# Save M Query
with open("query.m", "w") as f:
    f.write(m_query)

print("💾 Saved to query.m")
```

### Example 2: Step-by-Step Processing

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/migration"

# Step 1: Fetch
print("📥 Fetching loadscript...")
resp1 = requests.post(
    f"{BASE_URL}/fetch-loadscript",
    params={"app_id": "YOUR_APP_ID"}
)
loadscript = resp1.json()['loadscript']
print(f"✅ Got {len(loadscript)} chars")

# Step 2: Parse
print("🔍 Parsing...")
resp2 = requests.post(
    f"{BASE_URL}/parse-loadscript",
    params={"loadscript": loadscript}
)
parsed = resp2.json()
print(f"✅ Found {parsed['summary']['tables_count']} tables")

# Step 3: Convert
print("🔄 Converting...")
resp3 = requests.post(
    f"{BASE_URL}/convert-to-mquery",
    params={"parsed_script_json": json.dumps(parsed)}
)
m_query = resp3.json()['m_query']
print(f"✅ Generated {len(m_query)} char M Query")

# Step 4: Download
print("💾 Downloading...")
resp4 = requests.post(
    f"{BASE_URL}/download-mquery",
    params={"m_query": m_query, "filename": "my_query.m"}
)
with open("my_query.m", "wb") as f:
    f.write(resp4.content)
print("✅ Done!")
```

### Example 3: Error Handling

```python
import requests

BASE_URL = "http://localhost:8000/api/migration"

try:
    # Make request
    response = requests.post(
        f"{BASE_URL}/full-pipeline",
        params={"app_id": "INVALID_ID"},
        timeout=30
    )
    
    # Check status
    if response.status_code == 400:
        error = response.json()
        print(f"❌ Validation Error: {error['detail']}")
    elif response.status_code == 500:
        error = response.json()
        print(f"❌ Server Error: {error['detail']}")
    elif response.status_code == 200:
        print("✅ Success!")
    
except requests.exceptions.Timeout:
    print("❌ Request timeout - backend might be overloaded")
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect - check if backend is running")

```

---

## 🧪 Testing

### Test 1: Verify Modules Load

```bash
cd qlik-fastapi-backend

python -c "from loadscript_fetcher import LoadScriptFetcher; print('✅ OK')"
python -c "from loadscript_parser import LoadScriptParser; print('✅ OK')"
python -c "from loadscript_converter import LoadScriptToMQueryConverter; print('✅ OK')"
```

### Test 2: Run Test Suite

```bash
# Run comprehensive tests
python test_loadscript_feature.py

# Tests:
# - Module imports
# - Parser with sample data
# - Converter with sample data
# - API endpoints (requires backend)
# - Full integration
```

### Test 3: Manual Testing

```bash
# Start backend
python main.py

# In another terminal, test endpoint
curl -X POST "http://localhost:8000/api/migration/pipeline-help" | jq '.loadscript_conversion'

# Should show new endpoints listed
```

---

## 📝 File Reference

### loadscript_fetcher.py
**Size**: ~550 lines  
**Purpose**: Phases 1-4 - Fetch from QlikCloud  
**Key Classes**: `LoadScriptFetcher`  
**Key Methods**:
- `test_connection()` - Phase 1
- `get_applications()` - Phase 2
- `get_application_details()` - Phase 3
- `fetch_loadscript()` - Phase 4

### loadscript_parser.py
**Size**: ~550 lines  
**Purpose**: Phase 5 - Parse loadscript  
**Key Classes**: `LoadScriptParser`  
**Key Methods**:
- `parse()` - Main parsing function
- `_extract_comments()` - Extract comments
- `_extract_tables()` - Find table names
- `_extract_fields()` - Extract field definitions
- `_extract_data_connections()` - Find connections
- `_extract_transformations()` - Find WHERE, GROUP BY, etc
- `_extract_joins()` - Find JOIN operations

### loadscript_converter.py
**Size**: ~650 lines  
**Purpose**: Phase 6 - Convert to M Query  
**Key Classes**: `LoadScriptToMQueryConverter`  
**Key Methods**:
- `convert()` - Main conversion function
- `_convert_connections()` - Convert data sources
- `_convert_tables()` - Convert tables
- `_convert_fields()` - Convert types
- `_convert_transformations()` - Convert operations
- `_convert_joins()` - Convert joins

### migration_api.py
**Changes**: +250 lines  
**New Endpoints**:
- `POST /fetch-loadscript`
- `POST /parse-loadscript`
- `POST /convert-to-mquery`
- `POST /download-mquery`
- `POST /full-pipeline`

---

## 🔍 Troubleshooting

### Issue: "Cannot connect to Qlik Cloud"

**Solution**:
1. Check `.env` file for valid credentials
2. Ensure credentials are not expired
3. Check Qlik API endpoint is accessible
4. Review PHASE 1 logging output

### Issue: "Empty tables/fields after parsing"

**Solution**:
1. Check loadscript format - ensure all statements end with `;`
2. Ensure table names are in brackets or valid format
3. Review PHASE 5 logging for what was found
4. Test with sample script first

### Issue: "M Query conversion has warnings"

**Solution**:
1. Check `conversion_warnings` in response
2. Manually adjust the M Query for specific issues
3. Database connections may need manual setup
4. Review "note" fields in statistics

### Issue: "Backend not responding"

**Solution**:
1. Check backend is running: `python main.py`
2. Check it's at `http://localhost:8000`
3. Check for import errors in console
4. Ensure all new modules are in correct directory

### Issue: "HTTP 500 error"

**Solution**:
1. Check backend console for error output
2. Look for traceback with specific error message
3. Ensure all required libraries installed
4. Review debug output in PHASE logs

---

## 💡 Best Practices

✅ **Use full-pipeline endpoint** - Simpler than step-by-step  
✅ **Monitor console logs** - See real-time progress  
✅ **Check warnings** - They indicate things to review manually  
✅ **Test with small scripts first** - Before large applications  
✅ **Save M Query output** - Create backups before modifying  
✅ **Review data types** - Power Query conversion may need adjustment  
✅ **Document changes** - Note any manual adjustments made  

❌ **Don't**: Modify working logic without testing  
❌ **Don't**: Reuse M Query without reviewing output  
❌ **Don't**: Ignore database connection warnings  
❌ **Don't**: Skip error checking in production  

---

## 📊 Success Metrics

After implementation, you should be able to:

- [x] Fetch loadscript with single endpoint call
- [x] See detailed logging for each phase
- [x] Parse all script components accurately
- [x] Convert complex scripts to M Query
- [x] Download M Query as `.m` file
- [x] Use results in Power Query Editor
- [x] Handle errors gracefully
- [x] Monitor progress in real-time

---

## 🎯 Next Steps

1. **Start Backend**
   ```bash
   cd qlik_app/qlik/qlik-fastapi-backend
   python main.py
   ```

2. **Test Full Pipeline**
   ```bash
   curl -X POST "http://localhost:8000/api/migration/full-pipeline?app_id=YOUR_APP_ID"
   ```

3. **Monitor Console Output**
   - Watch for PHASE markers
   - Verify success indicators (✅)
   - Check warning/error counts

4. **Review Results**
   - Check parsed components
   - Review M Query output
   - Note any adjustments needed

5. **Use in Power BI**
   - Download M Query file
   - Open Power Query Editor
   - Paste content in Advanced Editor
   - Configure data types and relationships
   - Load into model

---

## 📚 Documentation Files

- **README_LOADSCRIPT_CONVERSION.md** - Quick start (this document's replacement)
- **LOADSCRIPT_CONVERSION_GUIDE.py** - Full API documentation with curl examples
- **IMPLEMENTATION_SUMMARY.md** - What was implemented and why
- **test_loadscript_feature.py** - Verification test suite
- **.env** - Qlik Cloud credentials (already configured)

---

## ✅ Implementation Checklist

- [x] LoadScript fetcher created (Phase 1-4)
- [x] LoadScript parser created (Phase 5)
- [x] M Query converter created (Phase 6)
- [x] API endpoints added (5 new routes)
- [x] Comprehensive logging implemented
- [x] Error handling implemented
- [x] Documentation created
- [x] Test suite created
- [x] No breaking changes
- [x] Ready for production

**🎉 Feature is complete and ready to use!**

---

## 🤝 Support

For issues or questions:
1. Check console logs for detailed error messages
2. Review error response in API output
3. Test modules individually
4. Verify backend is running
5. Check .env credentials
6. Review documentation files

All logging includes timestamps and function names for easy troubleshooting!

---

*Last Updated: 2026-02-25*  
*Feature Status: ✅ PRODUCTION READY*
