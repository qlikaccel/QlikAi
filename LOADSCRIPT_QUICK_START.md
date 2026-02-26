# LoadScript Conversion - Quick Reference Guide

## 🎯 Quick Start (5 minutes)

### For UI Users
1. Go to `/loadscript-converter` in the app
2. Paste your Qlik App ID
3. Click "► Start Conversion"
4. Watch real-time logs and progress
5. Download .pq or .txt when complete
6. Paste in Power BI Advanced Editor

### For API Users
```bash
# Copy-paste this into terminal:
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/migration/conversion/start-session | jq -r '.session_id')
curl -X POST "http://localhost:8000/api/migration/full-pipeline-tracked?app_id=YOUR_APP_ID&session_id=$SESSION_ID"
curl "http://localhost:8000/api/migration/download-file?session_id=$SESSION_ID&format=pq" -o query.pq
```

---

## 📊 API Endpoint Summary

### Create Session
```
POST /api/migration/conversion/start-session
Response: { session_id: "..." }
```

### Execute Pipeline (with tracking)
```
POST /api/migration/full-pipeline-tracked?app_id=X&session_id=Y
Response: { success: true, results: {...}, files_available: [...] }
```

### Get Live Logs
```
GET /api/migration/conversion/logs?session_id=X&limit=50
Response: { logs: [...] }
```

### Get Status
```
GET /api/migration/conversion/status?session_id=X
Response: { status: "RUNNING", progress: 65, current_phase: 5 }
```

### Get Complete Data
```
GET /api/migration/conversion/data?session_id=X
Response: { session: {...}, logs: [...], data: {loadscript, parsed, m_query} }
```

### Download Files
```
POST /api/migration/download-file?session_id=X&format=pq|txt|m
POST /api/migration/download-dual-zip?session_id=X
```

---

## 🔄 Flow Diagram

```
┌─────────────────────────┐
│  UI or API Request      │
│  (App ID provided)      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 1. START SESSION                │
│ POST /conversion/start-session  │
└────────────┬────────────────────┘
             │ Returns: session_id
             ▼
┌──────────────────────────────────────────┐
│ 2. EXECUTE PIPELINE (Real-time tracking) │
│ POST /full-pipeline-tracked              │
│   - Phase 1-4: Fetch LoadScript          │
│   - Phase 5: Parse Script                │
│   - Phase 6: Convert to M Query          │
│   - Phase 7: Generate Files              │
└────────────┬─────────────────────────────┘
             │ Executes in background
             │ Logs automatically tracked
             ▼
┌────────────────────────────────────┐
│ 3. POLL PROGRESS                   │
│ GET /conversion/logs               │
│ GET /conversion/status             │
│ (Call every 500-1000ms)            │
└────────────┬───────────────────────┘
             │ Shows: Logs, Progress %, Phase
             ▼
┌────────────────────────────────────┐
│ 4. DOWNLOAD RESULTS                │
│ - POST /download-file (format=pq)  │
│ - POST /download-file (format=txt) │
│ - POST /download-dual-zip          │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 5. USE IN POWER BI                 │
│ - Paste .pq/.m in Advanced Editor  │
│ - Reference .txt for docs          │
└────────────────────────────────────┘
```

---

## 📝 Log Levels Quick Reference

| Symbol | Level | Meaning |
|--------|-------|---------|
| 📍 | INFO | General progress information |
| ✅ | SUCCESS | Task completed successfully |
| ⚠️ | WARNING | Non-blocking issue, continued processing |
| ❌ | ERROR | Critical error, may need attention |

Example logs you'll see:
```
📍 10:30:15 Testing Qlik Cloud connection...
✅ 10:30:16 Connected to Qlik Cloud as: user@company.com
📍 10:30:17 Fetching loadscript for app: abc123...
✅ 10:30:18 Loadscript fetched (5248 characters)
📍 10:30:19 Parsing script components...
✅ 10:30:20 Parsed: 8 tables, 42 fields
📍 10:30:21 Converting to PowerBI M Query...
✅ 10:30:22 M Query generated (15620 characters)
✅ 10:30:23 Session completed in 8.47 seconds
```

---

## 🔑 Key Endpoints

| Endpoint | Method | Purpose | Returns |
|----------|--------|---------|---------|
| `/conversion/start-session` | POST | Create new session | session_id |
| `/full-pipeline-tracked` | POST | Run conversion | Results + logs |
| `/conversion/logs` | GET | Get live logs | Log entries |
| `/conversion/status` | GET | Get progress | Status + progress % |
| `/conversion/data` | GET | Get all data | Complete session data |
| `/download-file` | POST | Download format | File download |
| `/download-dual-zip` | POST | Download both | ZIP file |

---

## 💾 Download File Formats

### .pq (Power Query)
```m
let
    Source = [Data Connection],
    #"Step 1" = Source,
    #"Step 2" = Table.SelectColumns(#"Step 1", {...}),
    Result = #"Step 2"
in
    Result
```
**Use**: Paste in Power Query Editor

### .txt (Documentation)
```
================================================================================
POWER BI M QUERY - DOCUMENTATION
================================================================================

SCRIPT SUMMARY:
  Tables: 8
  Fields: 42
  Data Connections: 3
  Transformations: 15

USAGE INSTRUCTIONS:
1. Open Power BI Desktop
2. Go to Home > Get Data > Other > Web
3. Paste the M Query code below into Advanced Editor
...

================================================================================
M QUERY CODE:
================================================================================

[M Query code here]
```
**Use**: Reference + instructions

### .m (M Query)
Pure M Query code without metadata.
**Use**: Standard format compatibility

### .zip (Combined)
Contains: `powerbi_query.pq` + `powerbi_query_documentation.txt`

---

## 🔍 Session Status Values

| Status | Meaning |
|--------|---------|
| PENDING | Session created, waiting to start |
| RUNNING | Conversion in progress |
| COMPLETED | Conversion finished successfully |
| FAILED | Conversion failed with error |

---

## 📊 Conversion Phases Explained

### Phase 1-4: Fetch LoadScript
- Tests connection to Qlik Cloud
- Retrieves app details
- Downloads full LoadScript content
- **Output**: Raw loadscript file

### Phase 5: Parse Script
- Splits into components
- Identifies tables: `LOAD [Table1], [Table2]`
- Extracts fields with types
- Detects data sources (CSV, Excel, DB, etc.)
- Finds transformations (WHERE, GROUP BY, etc.)
- Identifies JOIN operations
- **Output**: Structured parsed data

### Phase 6: Convert to M Query
- Converts Qlik syntax to Power Query syntax
- Creates individual table queries
- Handles logical operators and functions
- Adapts data source connectors
- **Output**: M Query code

### Phase 7: Generate Files
- Creates .pq format
- Generates .txt documentation
- Prepares .m standard format
- **Output**: Downloadable files

---

## 🎯 Use Cases

### Use Case 1: Simple Table Migration
1. Enter App ID
2. Download .pq
3. Paste in Power Query
4. Done!

### Use Case 2: Complex Analysis
1. Enter App ID
2. Download .txt to understand structure
3. Review parsed tables and fields
4. Download .pq to use modified version
5. Reference .txt for transformations

### Use Case 3: Team Collaboration
1. Run conversion and get results
2. Share both .pq and .txt with team
3. Team understands logic via .txt
4. Team imports data via .pq

### Use Case 4: Documentation
1. Run conversion
2. Save .txt as reference document
3. Share with stakeholders
4. Explains what data is being migrated

---

## ⚙️ Configuration

### Environment Variables (if needed)
```bash
QLIK_API_KEY=your_api_key
QLIK_TENANT_URL=https://your-tenant.qlikcloud.com
```

### Session Memory Limit
Default: 100 sessions stored in memory
To change: Edit `conversion_logger.py` line ~150:
```python
self.max_sessions = 200  # Increase to 200
```

---

## 🆘 Troubleshooting

### "Session not found"
- Session ID is invalid or expired
- Check: Did you copy the full session ID?
- Try: Start a new session

### "No M Query available"
- Conversion hasn't completed yet
- Check status first: `/conversion/status`
- Wait for progress to reach 100%

### "Download fails"
- Session may have expired
- Start new session and conversion
- Check session status before downloading

### Conversion stuck?
- Check backend logs for errors
- Verify Qlik credentials valid
- Ensure app ID is correct format
- Try starting new session

---

## 📈 Performance Tips

1. **Poll every 500-1000ms** for status
   - Not too fast (wastes resources)
   - Not too slow (poor UX)

2. **Cache session data** client-side
   - Store logs and status
   - Only fetch new logs after last timestamp

3. **Use ZIP download** for batch operations
   - One download for both .pq and .txt
   - Faster than two separate downloads

4. **Batch multiple conversions**
   - Start sessions
   - Poll all at once
   - Download all at once

---

## 🔒 Security Notes

1. **Session IDs**: Random UUIDs - cryptographically secure
2. **No sensitive data**: Logs don't contain credentials
3. **File downloads**: Streamed from memory (no disk writes)
4. **CORS enabled**: Only whitelisted origins allowed
5. **Session cleanup**: Oldest sessions auto-deleted

---

## 📞 Support

- Check full docs: `LOADSCRIPT_CONVERSION_IMPLEMENTATION.md`
- API help endpoint: `GET /api/migration/pipeline-help`
- UI Page: `/loadscript-converter`
- Backend logs: Check console where uvicorn is running

---

**Your quick reference guide! Bookmark this page.** 🚀
