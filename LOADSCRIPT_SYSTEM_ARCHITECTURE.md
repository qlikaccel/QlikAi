# LoadScript Conversion - System Architecture & Data Flow

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER INTERFACE LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   LoadScriptConverterPage.tsx (React Component)          │   │
│  │                                                           │   │
│  │  • App ID Input                                          │   │
│  │  • Real-time Log Display (auto-scroll)                  │   │
│  │  • Progress Bar (0-100%)                                 │   │
│  │  • Phase Indicator (1-7)                                 │   │
│  │  • Summary Stats (tables, fields, sizes)                 │   │
│  │  • Download Buttons (.pq, .txt, .m, .zip)              │   │
│  │  • M Query Code Preview                                  │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│                     Polling API Endpoints                        │
│                              │                                   │
├─────────────────────────────────────────────────────────────────┤
│                    API GATEWAY LAYER (FastAPI)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              migration_api.py (Router)                    │   │
│  │                                                           │   │
│  │  Session Endpoints:                                      │   │
│  │  • POST /conversion/start-session                       │   │
│  │  • GET /conversion/logs                                 │   │
│  │  • GET /conversion/status                               │   │
│  │  • GET /conversion/data                                 │   │
│  │                                                           │   │
│  │  Pipeline Endpoints:                                     │   │
│  │  • POST /full-pipeline-tracked                          │   │
│  │  • POST /download-file                                  │   │
│  │  • POST /download-dual-zip                              │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
├─────────────────────────────────────────────────────────────────┤
│               CONVERSION LOGIC & TRACKING LAYER                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────┐    ┌──────────────────────────┐ │
│  │  conversion_logger.py       │    │  mquery_file_generator   │ │
│  │                             │    │  .py                     │ │
│  │  • ConversionSession        │    │                          │ │
│  │  • SessionManager           │    │  • MQueryFileGenerator   │ │
│  │  • Progress Tracking        │    │  • File Format Conv.     │ │
│  │  • Log Management           │    │  • ZIP Creation          │ │
│  │  • Phase Management         │    │  • Split Tables          │ │
│  │  • Error Handling           │    │                          │ │
│  │                             │    │                          │ │
│  └────────────────────────────┘    └──────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
         ┌──────────────────┐  ┌─────────────────┐
         │  LoadScript      │  │  M Query        │
         │  Fetcher         │  │  Converter      │
         │                  │  │                 │
         │ (Phases 1-4)     │  │ (Phase 6)       │
         │                  │  │                 │
         │ loadscript_      │  │ loadscript_     │
         │ fetcher.py       │  │ converter.py    │
         └──────────────────┘  └─────────────────┘
                    │                    ▲
                    │                    │
                    ▼                    │
         ┌──────────────────┐            │
         │  LoadScript      │            │
         │  Parser          │            │
         │                  │            │
         │ (Phase 5)        │            │
         │                  │            │
         │ loadscript_      │            │
         │ parser.py        │────────────┘
         └──────────────────┘
                    │
                    ▼
          ┌──────────────────────┐
          │  External Services   │
          ├──────────────────────┤
          │  • Qlik Cloud API    │
          │  • Qlik WebSocket    │
          │  • REST/XMLA         │
          └──────────────────────┘
```

---

## 📊 Data Flow Diagram

### Complete Conversion Flow

```
APPLICATION START
        │
        ▼
1. USER INTERACTION
   - Enter App ID: "abc-123-def-456"
   - Click "Start Conversion"
        │
        ▼
2. CREATE SESSION
   POST /conversion/start-session
   Response: session_id = "uuid-1234..."
        │
        ├─────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
3. EXECUTE PIPELINE WITH TRACKING                     │
   POST /full-pipeline-tracked                        │
   (Runs in background)                               │
        │                                              │
        ├─ PHASE 1-4: FETCH LoadScript ─────────────┐ │
        │ • Test connection                          │ │
        │ • Get available apps                       │ │
        │ • Fetch app details                        │ │
        │ • Download LoadScript                      │ │
        │ Log: "Connected as user@company.com" ✅    │ │
        │ Log: "Fetched LoadScript (5248 chars)" ✅  │ │
        │                                             │ │
        ├─────────────────────────────────────────┤ │
        ▼                                          │ │
        ├─ PHASE 5: PARSE LoadScript ────────────┐ │
        │ • Extract comments                       │ │
        │ • Find LOAD statements                   │ │
        │ • Identify table names                   │ │
        │ • Extract field definitions              │ │
        │ • Detect data connections                │ │
        │ • Find transformations (WHERE, GROUP)    │ │
        │ • Identify JOINs                         │ │
        │ Log: "Found 8 tables" ✅                 │ │
        │ Log: "Found 42 fields" ✅                │ │
        │                                          │ │
        ├──────────────────────────────────────┤ │
        ▼                                       │ │
        ├─ PHASE 6: CONVERT TO M QUERY ───────┐ │
        │ • Convert connections to M syntax     │ │
        │ • Create table queries                │ │
        │ • Transform field definitions         │ │
        │ • Apply transformations               │ │
        │ • Handle JOINs                        │ │
        │ Log: "M Query generated" ✅           │ │
        │                                       │ │
        ├──────────────────────────────────┤ │
        ▼                                   │ │
        ├─ PHASE 7: GENERATE FILES ──────┐ │
        │ • Create .pq format              │ │
        │ • Generate .txt docs             │ │
        │ • Create .m standard             │ │
        │ • Prepare ZIP (pq+txt)           │ │
        │ Log: "Files ready for download" ✅
        │
        (<--- MEANWHILE, USER POLLING ───────)
        │                              │
        ▼ (every 500-1000ms)          │
        POLL FOR UPDATES            │
        GET /conversion/logs         │
        GET /conversion/status       │
        Response: progress=65%       │
        Response: logs=[...]         │
        Response: phase=5            │
        │                           │
        └─────────────────────────┘
                    │
        UI UPDATES:
        ✓ Progress bar fills
        ✓ Logs display in real-time
        ✓ Phase number updates
        ✓ Summary stats show
                    │
                    ▼
        PIPELINE COMPLETES
        Status: COMPLETED
        Progress: 100%
                    │
                    ▼
        4. DOWNLOAD FILES
           GET /download-file?format=pq
           GET /download-file?format=txt
           POST /download-dual-zip
                    │
                    ├─ powerbi_query.pq
                    ├─ powerbi_query_documentation.txt
                    └─ powerbi_query.m
                    │
                    ▼
        5. USE IN POWER BI
           • Open Power Query Editor
           • Paste M Query
           • Configure connections
           • Load data
```

---

## 🔄 Session State Machine

```
┌─────────────┐
│   START     │
└──────┬──────┘
       │
       ▼
┌──────────────┐      ┌──────────────┐
│  PENDING     │─────▶│  RUNNING     │
│              │      │              │
│ Waiting to   │      │ Executing    │
│ begin        │      │ conversion   │
└──────────────┘      └──┬───────────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
         ┌─────────┐  ┌────────┐  ┌────────────┐
         │COMPLETED│  │ FAILED │  │ CANCELLED  │
         │         │  │        │  │            │
         │Success  │  │ Error  │  │ Interrupted│
         │100%     │  │ Logged │  │ by user    │
         └─────────┘  └────────┘  └────────────┘
              │          │          │
              └──────────┼──────────┘
                         │
                         ▼
                   ┌────────────┐
                   │  CLEANUP   │
                   │            │
                   │ Delete     │
                   │ old logs   │
                   └────────────┘
```

---

## 📁 File Structure

```
qlik-fastapi-backend/
├── main.py                          (FastAPI app initialization)
├── migration_api.py                 (✨ UPDATED - 7 new endpoints)
│
├── 🆕 conversion_logger.py           (NEW - Session tracking)
│   ├── ConversionSession class
│   ├── LogLevel enum
│   └── ConversionSessionManager class
│
├── 🆕 mquery_file_generator.py       (NEW - File generation)
│   ├── MQueryFileGenerator class
│   └── generate_dual_download_zip()
│
├── loadscript_fetcher.py            (Fetch LoadScript)
├── loadscript_parser.py             (Parse script)
└── loadscript_converter.py          (Convert to M Query)

converter/csv/src/
├── 🆕 LoadScriptConverter/
│   ├── LoadScriptConverterPage.tsx   (NEW - React component)
│   └── LoadScriptConverterPage.css   (NEW - Component styles)
│
└── router/
    └── AppRouter.tsx                (✨ UPDATED - Added route)
```

---

## 📊 Session Storage Model

```
In-Memory Session Store
├── sessions: { session_id: {...} }
│   │
│   └── session_id: "550e8400-e29b-41d4-a716-446655440000"
│       │
│       └── ConversionSession
│           ├── session_id: "550e8400-e29b-41d4-a716-446655440000"
│           │
│           ├── status: "COMPLETED"
│           ├── progress: 100
│           ├── current_phase: 7
│           │
│           ├── start_time: 2024-02-25T10:30:15.123456
│           ├── end_time: 2024-02-25T10:30:23.593456
│           ├── duration_seconds: 8.47
│           │
│           ├── logs: [
│           │   {
│           │     timestamp: "2024-02-25T10:30:15.123456",
│           │     level: "INFO",
│           │     message: "Testing Qlik Cloud connection...",
│           │     phase: 1,
│           │     data: {}
│           │   },
│           │   ...
│           │ ]
│           │
│           ├── conversion data:
│           │   ├── loadscript: "SET ...\nLOAD ..."
│           │   ├── parsed_script: {...}
│           │   └── m_query: "let\n    Source = ..."
│           │
│           └── metadata:
│               ├── tables_count: 8
│               ├── fields_count: 42
│               ├── loadscript_length: 5248
│               └── m_query_length: 15620
│
└── max_sessions: 100
    (Auto-delete oldest when limit reached)
```

---

## 🔌 API Integration Points

### Input Sources
```
┌─────────────────────┐
│   Qlik Cloud API    │
│   (REST + WebSocket)│
└──────────┬──────────┘
           │
    loadscript_fetcher.py ◀────┐
           │                    │
           ▼                    │
    LoadScript Content          │
    (Qlik Script Language)       │
           │                    │
    loadscript_parser.py         │
           │                    │
           ▼                    │
    Parsed Structure             │
    (Tables, Fields, Conns)      │
           │                    │
    loadscript_converter.py      │
           │                    │
           ▼                    │
    M Query Language  ◀──────────┘
    (Power Query)
           │
           ▼
    mquery_file_generator.py
           │
     ┌─────┼─────┐
     │     │     │
     ▼     ▼     ▼
    .pq  .txt   .m
    │     │     │
    └─────┼─────┘
          │
          ▼
    Power BI Desktop
    Advanced Editor
```

---

## 🔐 Security & Performance

### Security Measures
```
API Request
    │
    ├─ CORS Validation ✅
    │  (Only whitelisted origins)
    │
    ├─ Session ID Validation ✅
    │  (UUID format check)
    │
    ├─ Parameter Validation ✅
    │  (App ID format, format enum)
    │
    ├─ Qlik API Authentication ✅
    │  (API key from env vars)
    │
    └─ No Sensitive Data Logging ✅
       (No credentials in logs)
```

### Performance Optimizations
```
Polling Efficiency
    │
    ├─ Partial Logs Returned ✅
    │  (Last N logs only, default 50)
    │
    ├─ Status Only Endpoint ✅
    │  (Small response size)
    │
    ├─ ZIP Compression ✅
    │  (Reduces download size)
    │
    ├─ In-Memory Storage ✅
    │  (No disk I/O overhead)
    │
    └─ Session Auto-Cleanup ✅
       (100 session limit)
```

---

## 🎯 Phase Execution Timeline

```
Timeline (typical):
├─ 0s    : Session created
├─ 1s    : Phase 1-4 start (Fetch)
├─ 2s    : Connected to Qlik
├─ 3s    : LoadScript fetched
├─ 4s    : Phase 5 start (Parse)
├─ 5s    : Parsing complete
├─ 6s    : Phase 6 start (Convert)
├─ 7s    : Conversion complete
├─ 8s    : Phase 7 (Generate files)
└─ 9s    : All complete ✅

Total: ~9 seconds for typical app
```

---

## 📈 Data Volume Example

```
Typical Small App
├─ LoadScript size: 5-10 KB
├─ Parsed data: ~20-50 KB JSON
├─ M Query output: 10-20 KB
└─ Total session: ~50-100 KB

Typical Large App
├─ LoadScript size: 50-100 KB
├─ Parsed data: ~200-500 KB JSON
├─ M Query output: 100-200 KB
└─ Total session: ~500-1000 KB

Max in-memory (100 sessions):
└─ ~50-100 MB (for large apps)
```

---

## 🧪 Testing Points

### Unit Testing
- Session creation/deletion
- Log entry formatting
- File generation for each format
- Phase transitions

### Integration Testing
- End-to-end pipeline
- Session polling
- Download endpoints
- Error scenarios

### Load Testing
- 100 concurrent sessions
- High-frequency polling (100 polls/sec)
- Large file downloads
- Memory usage

---

## 🔍 Monitoring & Debugging

### Key Metrics to Track
```
✓ Average conversion time (seconds)
✓ Success rate (%)
✓ Average logs per session
✓ Memory usage (MB)
✓ Active sessions count
✓ Download success rate
```

### Debug Endpoints
```
GET /api/migration/health
GET /api/migration/pipeline-help
GET /api/migration/conversion/status

Backend Logs:
- Check console where uvicorn runs
- Filter by session_id
- Look for phase transitions
- Check error messages
```

---

## 🚀 Deployment Checklist

- ✅ Backend: conversion_logger.py in place
- ✅ Backend: mquery_file_generator.py in place
- ✅ Backend: migration_api.py updated with 7 endpoints
- ✅ Frontend: LoadScriptConverterPage.tsx component
- ✅ Frontend: LoadScriptConverterPage.css styling
- ✅ Frontend: Router updated with /loadscript-converter route
- ✅ Environment: QLIK_API_KEY set
- ✅ Environment: QLIK_TENANT_URL set
- ✅ CORS: Whitelisted frontend origin
- ✅ Testing: End-to-end workflow verified

---

**Complete system architecture documented!** 🎯
