# ⚡ LoadScript to PowerBI M Query Conversion - QUICK START

## What's New?

Your project now has a complete **6-phase pipeline** that:
1. **Fetches** Qlik LoadScript from QlikCloud
2. **Parses** the script to extract components
3. **Converts** to PowerBI M Query language
4. **Downloads** as a .m file ready for Power Query Editor

Each phase includes **detailed logging** so you can see exactly what's happening!

---

## 🚀 Quick Test

### Option 1: Complete Pipeline (Easiest)

```bash
# Terminal command
curl -X POST "http://localhost:8000/api/migration/full-pipeline?app_id=YOUR_APP_ID_HERE" \
  -H "Accept: application/json"
```

This will:
- ✅ Fetch your loadscript from QlikCloud
- ✅ Parse all components (tables, fields, connections, transformations)
- ✅ Convert to PowerBI M Query
- ✅ Return everything

### Option 2: Step by Step (For Debugging)

```bash
# Step 1: Fetch LoadScript (check console for logging output)
curl -X POST "http://localhost:8000/api/migration/fetch-loadscript?app_id=YOUR_APP_ID_HERE"

# Step 2: Parse the script
curl -X POST "http://localhost:8000/api/migration/parse-loadscript?loadscript=YOUR_SCRIPT_HERE"

# Step 3: Convert to M Query
curl -X POST "http://localhost:8000/api/migration/convert-to-mquery?parsed_script_json={...}"

# Step 4: Download the result
curl -X POST "http://localhost:8000/api/migration/download-mquery?m_query=..." \
  -o powerbi_query.m
```

---

## 📊 What You'll See in Logs

Each phase outputs comprehensive logging:

### Phase 1-4: Fetch LoadScript
```
================================================================================
PHASE 0: Initializing LoadScript Fetcher
================================================================================
✅ Initialized with Tenant URL: https://c8vlzp3sx6akvnh.in.qlikcloud.com
✅ API Base URL: https://c8vlzp3sx6akvnh.in.qlikcloud.com/api/v1

================================================================================
PHASE 1: Testing Connection to Qlik Cloud
================================================================================
🔌 Testing connection to: https://c8vlzp3sx6akvnh.in.qlikcloud.com/api/v1/users/me
✅ Connection successful!
✅ User ID: 6979dd842f92a48dc7c29bc7
✅ User Name: user@company.com

================================================================================
PHASE 2: Fetching Applications List from Qlik Cloud
================================================================================
✅ Successfully fetched 5 application(s)
   ✓ App 1: Sales Dashboard (ID: a1b2c3d4...)
   ✓ App 2: Financial Reports (ID: e5f6g7h8...)
   ...

... and more detailed info for PHASE 3 and PHASE 4
```

### Phase 5: Parse LoadScript
```
================================================================================
PHASE 5: PARSING LOADSCRIPT
================================================================================
📍 Step 5.1: Extracting comments...
✅ Found 3 comment block(s)

📍 Step 5.2: Extracting LOAD statements...
✅ Found 8 LOAD statement(s)

📍 Step 5.3: Extracting table names...
✅ Found 5 table(s)
   ✓ Table: Customers
   ✓ Table: Orders
   ✓ Table: Products
   ... and 2 more table(s)

📍 Step 5.4: Extracting field definitions...
✅ Found 24 field(s)
   ✓ Field: OrderID (column)
   ✓ Field: CustomerName (column)
   ... and 22 more field(s)

📍 Step 5.5: Extracting data connections...
✅ Found 2 data connection(s)
   ✓ Connection: file - lib://DataFiles/orders.csv

... continues for Steps 5.6, 5.7, 5.8
```

### Phase 6: Convert to M Query
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

📍 Step 6.4: Converting transformations...
✅ Converted 6 transformation(s)

📍 Step 6.5: Converting JOIN operations...
✅ Converted 2 JOIN(s)

📍 Step 6.6: Assembling final M query...
✅ Final M query assembled (8500 characters)

================================================================================
✅ CONVERSION COMPLETED SUCCESSFULLY
================================================================================
```

---

## 📁 New Files Created

```
qlik-fastapi-backend/
├── loadscript_fetcher.py          # Phase 1-4: Fetch from QlikCloud
├── loadscript_parser.py           # Phase 5: Parse loadscript
├── loadscript_converter.py        # Phase 6: Convert to M Query
├── LOADSCRIPT_CONVERSION_GUIDE.py # Complete usage documentation (this file!)
└── migration_api.py               # Updated with new 5 endpoints
```

---

## 🔌 New API Endpoints

### 1. `/api/migration/fetch-loadscript` (POST)
**Phases 1-4**: Fetch loadscript from QlikCloud

```
Method: POST
Parameter: app_id (string)
Returns: Loadscript with metadata
```

### 2. `/api/migration/parse-loadscript` (POST)
**Phase 5**: Parse and extract components

```
Method: POST
Parameter: loadscript (string)
Returns: Tables, fields, connections, transformations, joins, variables, comments
```

### 3. `/api/migration/convert-to-mquery` (POST)
**Phase 6**: Convert to PowerBI M Query

```
Method: POST
Parameter: parsed_script_json (JSON string)
Returns: M Query code
```

### 4. `/api/migration/download-mquery` (POST)
**Download**: Download M Query as .m file

```
Method: POST
Parameters: m_query (string), filename (optional)
Returns: Binary .m file
```

### 5. `/api/migration/full-pipeline` (POST)
**All Phases 1-6**: Complete pipeline in one call

```
Method: POST
Parameters: app_id (string), auto_download (boolean, optional)
Returns: Complete conversion result with all intermediate steps
```

---

## 🎯 Typical Workflow

### Using Full Pipeline (Recommended)

```python
import requests
import json

# 1. Fetch, parse, and convert in one call
response = requests.post(
    "http://localhost:8000/api/migration/full-pipeline",
    params={"app_id": "YOUR_QLIK_APP_ID"}
)

data = response.json()

# 2. Extract M Query
m_query = data['m_query']

# 3. Download
download_response = requests.post(
    "http://localhost:8000/api/migration/download-mquery",
    params={"m_query": m_query, "filename": "my_query.m"}
)

with open("my_query.m", "wb") as f:
    f.write(download_response.content)

print("✅ M Query downloaded successfully!")
```

### Step-by-Step Workflow (For Debugging)

```python
import requests
import json

# Step 1: Fetch
fetch_res = requests.post(
    "http://localhost:8000/api/migration/fetch-loadscript",
    params={"app_id": "YOUR_APP_ID"}
)
loadscript = fetch_res.json()['loadscript']

# Step 2: Parse  
parse_res = requests.post(
    "http://localhost:8000/api/migration/parse-loadscript",
    params={"loadscript": loadscript}
)
parsed = parse_res.json()

# Step 3: Convert
convert_res = requests.post(
    "http://localhost:8000/api/migration/convert-to-mquery",
    params={"parsed_script_json": json.dumps(parsed)}
)
m_query = convert_res.json()['m_query']

print(f"✅ Generated M Query ({len(m_query)} chars)")
```

---

## 📝 Logging Features

✅ **PHASE markers** - Easy to track progress  
✅ **Step indicators** - Know exactly where you are  
✅ **Success checkmarks** - ✅ for completed steps  
✅ **Error indicators** - ❌ for failures  
✅ **Warning indicators** - ⚠️ for issues  
✅ **Timestamps** - When each operation started/ended  
✅ **Statistics** - Count summaries  
✅ **Data previews** - Sample of extracted data  

All logging goes to **console/stdout** so you can:
- See real-time progress
- Debug issues
- Understand conversions

---

## ⚙️ Configuration

Your existing `.env` file already has everything needed:

```env
# Qlik Cloud Credentials
QLIK_CLIENT_ID=...
QLIK_CLIENT_SECRET=...
QLIK_API_KEY=...
QLIK_TENANT_URL=https://c8vlzp3sx6akvnh.in.qlikcloud.com
QLIK_API_BASE_URL=https://c8vlzp3sx6akvnh.in.qlikcloud.com/api/v1
```

✅ **No additional configuration needed!**

---

## 🧪 Testing

### Test 1: View Available Endpoints

```bash
curl http://localhost:8000/api/migration/pipeline-help
```

You'll see all 5 new endpoints listed!

### Test 2: Test Without Qlik (Sample Data)

```bash
# Test parser with sample script
python loadscript_parser.py

# Test converter with sample parsed data  
python loadscript_converter.py
```

Both modules have built-in test data at the bottom!

### Test 3: Full End-to-End

```bash
# Make sure backend is running
python main.py

# In another terminal, run test
curl -X POST "http://localhost:8000/api/migration/full-pipeline?app_id=YOUR_APP_ID"
```

---

## 📊 Example Response

### Fetch Response
```json
{
  "status": "success",
  "app_id": "YOUR_APP_ID",
  "app_name": "Sales Dashboard",
  "loadscript": "// Application: Sales Dashboard\n[Customers]:\nLOAD...",
  "script_length": 5432,
  "method": "direct_api",
  "timestamp": "2026-02-25T10:30:45.123456"
}
```

### Parse Response
```json
{
  "status": "success",
  "summary": {
    "tables_count": 5,
    "fields_count": 24,
    "connections_count": 2,
    "transformations_count": 6,
    "joins_count": 2,
    "variables_count": 0,
    "comments_count": 3
  },
  "details": {
    "tables": [...],
    "fields": [...],
    ...
  }
}
```

### Convert Response
```json
{
  "status": "success",
  "m_query": "let\n  Source = ...",
  "query_length": 8500,
  "warnings_count": 2,
  "errors_count": 0,
  "statistics": {...}
}
```

---

## ✅ No Breaking Changes

✨ **Your existing working logic is untouched!**

- All existing endpoints still work
- All existing functionality preserved
- New feature is completely additive
- Can enable/disable by using/not using new endpoints

---

## 🎓 Next Steps

1. **Test Phase 1-4**: Call `/fetch-loadscript` with your app ID
2. **Check Console Logs**: Watch for detailed logging output
3. **Review Parsed Data**: Analyze what was extracted
4. **View Conversion**: See the generated M Query  
5. **Download Result**: Use `/download-mquery` to save .m file
6. **Import to Power Query**: Paste in Power BI and adjust as needed

---

## 🔍 Verification Steps

After implementation, you can verify:

```bash
# 1. Check modules load
python -c "from loadscript_fetcher import LoadScriptFetcher; print('✅ OK')"
python -c "from loadscript_parser import LoadScriptParser; print('✅ OK')"
python -c "from loadscript_converter import LoadScriptToMQueryConverter; print('✅ OK')"

# 2. Check API updated
curl http://localhost:8000/api/migration/pipeline-help | grep "fetch-loadscript"

# 3. Check endpoints are available
curl http://localhost:8000/docs  # Swagger UI shows all endpoints
```

---

## 📞 Support

Check:
- [Backend Logs](#logging-features) for detailed debugging
- [LOADSCRIPT_CONVERSION_GUIDE.py](LOADSCRIPT_CONVERSION_GUIDE.py) for complete API documentation
- [Error Responses](#error-handling) for common issues

**All features include comprehensive logging for troubleshooting!**
