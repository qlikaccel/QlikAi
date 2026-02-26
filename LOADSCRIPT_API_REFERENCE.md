# LoadScript Conversion - API Reference & Curl Examples

## Base URL
```
http://localhost:8000
```

---

## 1. START SESSION

### Endpoint
```
POST /api/migration/conversion/start-session
```

### Curl Example
```bash
curl -X POST http://localhost:8000/api/migration/conversion/start-session
```

### Response
```json
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Conversion session created",
  "endpoints": {
    "fetch": "/api/migration/full-pipeline-tracked?session_id=550e8400-e29b-41d4-a716-446655440000",
    "logs": "/api/migration/conversion/logs?session_id=550e8400-e29b-41d4-a716-446655440000",
    "status": "/api/migration/conversion/status?session_id=550e8400-e29b-41d4-a716-446655440000",
    "data": "/api/migration/conversion/data?session_id=550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

## 2. EXECUTE PIPELINE WITH TRACKING

### Endpoint
```
POST /api/migration/full-pipeline-tracked
```

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `app_id` | string | Yes | Qlik App ID to convert |
| `session_id` | string | Yes | Session ID from start-session |

### Curl Example
```bash
APP_ID="abcd1234-ef56-7890-ab12-cdef34567890"
SESSION_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST "http://localhost:8000/api/migration/full-pipeline-tracked?app_id=$APP_ID&session_id=$SESSION_ID"
```

### Response Example
```json
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "progress": 100,
  "app_id": "abcd1234-ef56-7890-ab12-cdef34567890",
  "results": {
    "loadscript_length": 5248,
    "tables_count": 8,
    "fields_count": 42,
    "m_query_length": 15620,
    "m_query": "let\n    Source = ...\n in\n    Result"
  },
  "files_available": ["pq", "txt", "m"],
  "endpoints": {
    "download_pq": "/api/migration/download-file?session_id=550e8400...&format=pq",
    "download_txt": "/api/migration/download-file?session_id=550e8400...&format=txt",
    "download_m": "/api/migration/download-file?session_id=550e8400...&format=m",
    "download_dual_zip": "/api/migration/download-dual-zip?session_id=550e8400...",
    "logs": "/api/migration/conversion/logs?session_id=550e8400..."
  }
}
```

---

## 3. GET LIVE LOGS

### Endpoint
```
GET /api/migration/conversion/logs
```

### Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | Yes | - | Session ID |
| `limit` | integer | No | 50 | Max logs to return |

### Curl Example
```bash
SESSION_ID="550e8400-e29b-41d4-a716-446655440000"

# Get last 50 logs
curl "http://localhost:8000/api/migration/conversion/logs?session_id=$SESSION_ID"

# Get last 100 logs
curl "http://localhost:8000/api/migration/conversion/logs?session_id=$SESSION_ID&limit=100"
```

### Response
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "log_count": 15,
  "logs": [
    {
      "timestamp": "2024-02-25T10:30:15.123456",
      "level": "INFO",
      "message": "Testing Qlik Cloud connection...",
      "phase": 1,
      "data": {}
    },
    {
      "timestamp": "2024-02-25T10:30:16.234567",
      "level": "SUCCESS",
      "message": "Connected to Qlik Cloud as: user@company.com",
      "phase": 1,
      "data": {}
    },
    {
      "timestamp": "2024-02-25T10:30:17.345678",
      "level": "INFO",
      "message": "Fetching loadscript for app: abcd1234-ef56-7890...",
      "phase": 4,
      "data": {}
    },
    {
      "timestamp": "2024-02-25T10:30:18.456789",
      "level": "SUCCESS",
      "message": "Loadscript fetched (5248 characters)",
      "phase": 4,
      "data": {"script_length": 5248}
    },
    {
      "timestamp": "2024-02-25T10:30:19.567890",
      "level": "INFO",
      "message": "Parsing script components...",
      "phase": 5,
      "data": {}
    },
    {
      "timestamp": "2024-02-25T10:30:20.678901",
      "level": "SUCCESS",
      "message": "Parsed: 8 tables, 42 fields",
      "phase": 5,
      "data": {"tables": 8, "fields": 42}
    }
  ],
  "timestamp_retrieved": "2024-02-25T10:30:25.000000"
}
```

---

## 4. GET CONVERSION STATUS

### Endpoint
```
GET /api/migration/conversion/status
```

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session ID |

### Curl Example
```bash
SESSION_ID="550e8400-e29b-41d4-a716-446655440000"

curl "http://localhost:8000/api/migration/conversion/status?session_id=$SESSION_ID"
```

### Response
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "progress": 100,
  "current_phase": 7,
  "duration_seconds": 8.47,
  "error_message": null,
  "data_summary": {
    "tables_count": 8,
    "fields_count": 42,
    "loadscript_length": 5248,
    "m_query_length": 15620
  },
  "timestamp_start": "2024-02-25T10:30:15.123456",
  "timestamp_end": "2024-02-25T10:30:23.593456"
}
```

---

## 5. GET COMPLETE SESSION DATA

### Endpoint
```
GET /api/migration/conversion/data
```

### Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | Yes | - | Session ID |
| `include_logs` | boolean | No | false | Include full logs |

### Curl Example
```bash
SESSION_ID="550e8400-e29b-41d4-a716-446655440000"

# Get data without logs
curl "http://localhost:8000/api/migration/conversion/data?session_id=$SESSION_ID"

# Get data with full logs
curl "http://localhost:8000/api/migration/conversion/data?session_id=$SESSION_ID&include_logs=true"
```

### Response (Partial)
```json
{
  "session": {...},  // Full session status object
  "logs": [          // Only if include_logs=true
    {...}
  ],
  "data": {
    "loadscript": "SET ...\nLOAD [Field1], [Field2] FROM [...];",
    "parsed_script": {
      "summary": {
        "tables_count": 8,
        "fields_count": 42,
        "connections_count": 3,
        "transformations_count": 15,
        "joins_count": 2
      },
      "details": {
        "tables": [
          {
            "name": "TableName",
            "alias": "T1",
            "fields_count": 5
          }
        ],
        "fields": [...],
        "data_connections": [...]
      }
    },
    "m_query": "let\n    Source = ...\n in\n    Result"
  }
}
```

---

## 6. DOWNLOAD M QUERY FILE

### Endpoint
```
POST /api/migration/download-file
```

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session ID |
| `format` | string | Yes | File format: `pq` \| `txt` \| `m` |

### Curl Examples

#### Download .pq (Power Query)
```bash
SESSION_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST "http://localhost:8000/api/migration/download-file?session_id=$SESSION_ID&format=pq" \
  -o powerbi_query.pq
```

#### Download .txt (Documentation)
```bash
curl -X POST "http://localhost:8000/api/migration/download-file?session_id=$SESSION_ID&format=txt" \
  -o powerbi_query_documentation.txt
```

#### Download .m (M Query)
```bash
curl -X POST "http://localhost:8000/api/migration/download-file?session_id=$SESSION_ID&format=m" \
  -o powerbi_query.m
```

### Response
- File is streamed directly
- Saved to local disk with `-o` parameter
- MIME type: `text/plain`

---

## 7. DOWNLOAD DUAL ZIP (PQ + TXT)

### Endpoint
```
POST /api/migration/download-dual-zip
```

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session ID |

### Curl Example
```bash
SESSION_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST "http://localhost:8000/api/migration/download-dual-zip?session_id=$SESSION_ID" \
  -o powerbi_query_files.zip
```

### Response
- ZIP file containing:
  - `powerbi_query.pq` (Power Query format)
  - `powerbi_query_documentation.txt` (Documentation)
- MIME type: `application/zip`

---

## Complete Workflow Example

### Step-by-step with variables

```bash
#!/bin/bash

# Configuration
APP_ID="abcd1234-ef56-7890-ab12-cdef34567890"
API_BASE="http://localhost:8000"

echo "🚀 Starting Qlik to Power BI conversion..."

# Step 1: Create session
echo "📌 Step 1: Creating session..."
SESSION_RESPONSE=$(curl -s -X POST "$API_BASE/api/migration/conversion/start-session")
SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.session_id')
echo "✅ Session ID: $SESSION_ID"

# Step 2: Start conversion
echo "📌 Step 2: Starting conversion pipeline..."
curl -s -X POST "$API_BASE/api/migration/full-pipeline-tracked?app_id=$APP_ID&session_id=$SESSION_ID" > /dev/null

# Step 3: Poll for completion
echo "📌 Step 3: Monitoring progress..."
while true; do
  STATUS=$(curl -s "$API_BASE/api/migration/conversion/status?session_id=$SESSION_ID")
  PROGRESS=$(echo $STATUS | jq -r '.progress')
  PHASE=$(echo $STATUS | jq -r '.current_phase')
  CONV_STATUS=$(echo $STATUS | jq -r '.status')
  
  echo -ne "\r⏱️  Progress: $PROGRESS% | Phase: $PHASE/7 | Status: $CONV_STATUS"
  
  if [ "$CONV_STATUS" = "COMPLETED" ] || [ "$CONV_STATUS" = "FAILED" ]; then
    echo ""
    break
  fi
  
  sleep 1
done

if [ "$CONV_STATUS" = "COMPLETED" ]; then
  echo "✅ Conversion completed!"
  
  # Step 4: Download .pq file
  echo "📌 Step 4: Downloading .pq file..."
  curl -s -X POST "$API_BASE/api/migration/download-file?session_id=$SESSION_ID&format=pq" \
    -o "powerbi_query.pq"
  echo "✅ Downloaded: powerbi_query.pq"
  
  # Step 5: Download .txt file
  echo "📌 Step 5: Downloading .txt file..."
  curl -s -X POST "$API_BASE/api/migration/download-file?session_id=$SESSION_ID&format=txt" \
    -o "powerbi_query_documentation.txt"
  echo "✅ Downloaded: powerbi_query_documentation.txt"
  
  # Step 6: Get logs for review
  echo "📌 Step 6: Saving logs..."
  curl -s "$API_BASE/api/migration/conversion/logs?session_id=$SESSION_ID&limit=100" | jq '.' > "conversion_logs.json"
  echo "✅ Saved: conversion_logs.json"
  
  echo "🎉 All files ready!"
  echo "📁 Files:"
  echo "  - powerbi_query.pq (Use in Power Query)"
  echo "  - powerbi_query_documentation.txt (Reference)"
  echo "  - conversion_logs.json (Logs)"
  
else
  echo "❌ Conversion failed!"
  ERROR=$(echo $STATUS | jq -r '.error_message')
  echo "Error: $ERROR"
  exit 1
fi
```

### Save as script
```bash
# Save as: convert_script.sh
chmod +x convert_script.sh
./convert_script.sh
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid format: xyz. Available: pq, txt, m"
}
```

### 404 Not Found
```json
{
  "detail": "Session 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

### 500 Server Error
```json
{
  "detail": "Pipeline execution failed: [error details]"
}
```

---

## Response Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Session or resource not found |
| 500 | Server error |

---

## Rate Limiting Notes

Currently: **No rate limiting**

For production, consider adding:
- Per IP: 100 requests/minute
- Per session: 10 downloads/hour
- Max 50 concurrent sessions

---

## Best Practices

### 1. Error Handling
```bash
# Always check HTTP status
curl -s -w "\n%{http_code}" ... | tail -n1  # Get status code

# Check for JSON error
jq '.detail' response.json
```

### 2. Polling Strategy
```bash
# Poll every 500-1000ms
# Stops when status is COMPLETED or FAILED
# Timeout after 5 minutes
while [ $((elapsed++)) -lt 300 ]; do
  status=$(curl -s ... | jq -r '.status')
  [ "$status" != "RUNNING" ] && break
  sleep 1
done
```

### 3. Session Management
```bash
# Store session ID for later
echo $SESSION_ID > .session_id

# Retrieve later
SESSION_ID=$(cat .session_id)
curl ... "?session_id=$SESSION_ID"
```

### 4. Error Recovery
```bash
# Catch errors from pipeline
ERROR=$(echo $RESPONSE | jq -r '.error_message // empty')
if [ ! -z "$ERROR" ]; then
  # Start new session and retry
  # Or log error and notify
fi
```

---

## Environment Variables

For automation, set:
```bash
export QLIK_APP_ID="your-app-id"
export API_BASE="http://localhost:8000"
export SESSION_ID="your-session-id"
```

Then use in commands:
```bash
curl -X POST "$API_BASE/api/migration/full-pipeline-tracked?app_id=$QLIK_APP_ID&session_id=$SESSION_ID"
```

---

## Testing the API

### 1. Health Check
```bash
curl http://localhost:8000/api/migration/health
```

### 2. Get API Documentation
```bash
curl http://localhost:8000/api/migration/pipeline-help | jq '.'
```

### 3. Simple End-to-End Test
```bash
# Create session
SID=$(curl -s -X POST http://localhost:8000/api/migration/conversion/start-session | jq -r '.session_id')

# Check status
curl "http://localhost:8000/api/migration/conversion/status?session_id=$SID"
```

---

## Integration Examples

### Python
```python
import requests
import time

session_id = requests.post('http://localhost:8000/api/migration/conversion/start-session').json()['session_id']

requests.post(f'http://localhost:8000/api/migration/full-pipeline-tracked?app_id=X&session_id={session_id}')

while True:
    status = requests.get(f'http://localhost:8000/api/migration/conversion/status?session_id={session_id}').json()
    if status['status'] in ['COMPLETED', 'FAILED']:
        break
    time.sleep(1)

# Download
with open('query.pq', 'wb') as f:
    r = requests.post(f'http://localhost:8000/api/migration/download-file?session_id={session_id}&format=pq')
    f.write(r.content)
```

### JavaScript/Node.js
```javascript
const axios = require('axios');

const api = 'http://localhost:8000';

async function convert() {
  // Start session
  const { data: { session_id } } = await axios.post(`${api}/api/migration/conversion/start-session`);
  
  // Start pipeline
  await axios.post(`${api}/api/migration/full-pipeline-tracked?app_id=YOUR_APP_ID&session_id=${session_id}`);
  
  // Poll status
  let status = 'RUNNING';
  while (status === 'RUNNING') {
    const { data } = await axios.get(`${api}/api/migration/conversion/status?session_id=${session_id}`);
    status = data.status;
    console.log(`Progress: ${data.progress}%`);
    await new Promise(r => setTimeout(r, 1000));
  }
  
  // Download file
  const response = await axios.post(`${api}/api/migration/download-file?session_id=${session_id}&format=pq`, null, {
    responseType: 'blob'
  });
  
  // Save file
  const fs = require('fs');
  fs.writeFileSync('query.pq', response.data);
}

convert();
```

---

## Support & Debugging

### Enable Debug Logging (Backend)
```python
# In conversion_logger.py
logging.basicConfig(level=logging.DEBUG)  # Change from INFO to DEBUG
```

### Get Detailed Logs
```bash
# Get all logs with full data
curl "http://localhost:8000/api/migration/conversion/logs?session_id=$SID&limit=1000" | jq '.'
```

### Check Backend Console
- Look for phase transition logs
- Check for error messages
- Verify timestamps and durations

---

**All endpoints documented! You're ready to integrate.** 🎯
