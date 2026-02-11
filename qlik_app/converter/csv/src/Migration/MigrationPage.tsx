import "./MigrationPage.css";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function MigrationPage() {
  const navigate = useNavigate();
  const appName = sessionStorage.getItem("migration_appName") || sessionStorage.getItem("appName") || "Unknown";
  const tableName = sessionStorage.getItem("migration_selected_table") || "";

  const hasCSV = sessionStorage.getItem("migration_has_csv") === "true";
  const hasDAX = sessionStorage.getItem("migration_has_dax") === "true";
  const hasJSON = sessionStorage.getItem("migration_has_json") === "true";

  const columns: string[] = JSON.parse(sessionStorage.getItem("migration_columns") || "[]");
  const rowCount = Number(sessionStorage.getItem("migration_row_count") || "0");

  const [publishing, setPublishing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>("");
  const [statusBoxes, setStatusBoxes] = useState({ columns: false, powerbi: false, finished: false });
  const [customTableName, setCustomTableName] = useState(tableName);
  const [pushedTables, setPushedTables] = useState<any[]>([]);

  useEffect(() => {
    // Log sessionStorage content when component mounts
    console.log("🔍 SessionStorage Debug on Mount:");
    console.log("- migration_csv size:", sessionStorage.getItem("migration_csv")?.length);
    console.log("- migration_dax size:", sessionStorage.getItem("migration_dax")?.length);
    console.log("- migration_has_csv:", sessionStorage.getItem("migration_has_csv"));
    console.log("- migration_has_dax:", sessionStorage.getItem("migration_has_dax"));
    console.log("- migration_selected_table:", sessionStorage.getItem("migration_selected_table"));
  }, []);

  const authenticateAndPublish = async () => {
    try {
      console.log("🚀 Starting backend authentication and publishing...");
      setError("");
      setResult(null);
      
      // Step 1: Initiate authentication in backend
      console.log("🔐 Initiating backend authentication...");
      const authRes = await fetch("http://localhost:8000/powerbi/login/acquire-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      
      if (!authRes.ok) {
        throw new Error(`Authentication failed: ${authRes.status}`);
      }
      
      const authData = await authRes.json();
      console.log("✅ Backend authentication started:", authData);
      
      // Step 2: Wait for authentication to complete
      console.log("⏳ Waiting for authentication to complete...");
      let authAttempts = 0;
      const maxAttempts = 30; // 30 seconds max wait
      
      // Wait 3 seconds for authentication to complete before checking status
      console.log("⏳ Waiting 3 seconds for authentication to complete...");
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      while (authAttempts < maxAttempts) {
        try {
          const statusRes = await fetch("http://localhost:8000/powerbi/login/status", {
            method: "POST",
          });
          const statusData = await statusRes.json();
          
          if (statusData.logged_in) {
            console.log("✅ Authentication completed successfully!");
            break;
          }
        } catch (e) {
          console.warn("⚠️ Error checking auth status:", e);
        }
        
        authAttempts++;
        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
        
        if (authAttempts % 5 === 0) {
          console.log(`⏳ Still waiting for authentication... (${authAttempts}s)`);
        }
      }
      
      if (authAttempts >= maxAttempts) {
        throw new Error("Authentication timeout: Please try again");
      }
      
      // Step 3: Proceed with publishing
      console.log("🚀 Proceeding with dataset publishing...");
      await proceedWithPublish();
      
    } catch (e: any) {
      const errorMsg = e?.message || "Authentication failed";
      console.error("❌ Authentication error:", errorMsg, e);
      setError(errorMsg);
    }
  };

  const proceedWithPublish = async () => {
    setPublishing(true);
    setError("");
    setResult(null);

    try {
      // Debug: Check what we have in sessionStorage
      const csvText = sessionStorage.getItem("migration_csv") || "";
      const daxText = sessionStorage.getItem("migration_dax") || "";
      
      console.log("📊 Migration Debug Info:");
      console.log("CSV content length:", csvText.length);
      console.log("DAX content length:", daxText.length);
      console.log("App Name:", appName);
      console.log("Table Name:", tableName || customTableName);
      console.log("Has CSV (selected in Export):", hasCSV);
      console.log("Has DAX (selected in Export):", hasDAX);

      // Validate: Check selection from Export page
      if (!hasCSV && !hasDAX) {
        throw new Error("No formats selected in Export page. Please go back and select CSV and/or DAX.");
      }
      
      // Validate: Check that selected formats have data
      if (hasCSV && !csvText) {
        throw new Error("CSV was selected but no data found. Please re-export from Export page.");
      }
      if (hasDAX && !daxText) {
        throw new Error("DAX was selected but no data found. Please re-export from Export page.");
      }

      const form = new FormData();
      
      // Only add CSV if it was selected in Export page
      if (hasCSV && csvText) {
        form.append("csv_file", new Blob([csvText], { type: "text/csv" }), `${tableName || "dataset"}.csv`);
        console.log("✅ Added CSV file (selected in Export page):", csvText.length, "bytes");
      }
      
      // Only add DAX if it was selected in Export page
      if (hasDAX && daxText) {
        form.append("dax_file", new Blob([daxText], { type: "text/plain" }), `${tableName || "dataset"}.dax`);
        console.log("✅ Added DAX file (selected in Export page):", daxText.length, "bytes");
      }

      // Metadata
      form.append("meta_app_name", appName);
      form.append("meta_table", customTableName || tableName);
      form.append("has_csv", hasCSV ? "true" : "false");
      form.append("has_dax", hasDAX ? "true" : "false");

      console.log("🚀 Sending request to http://localhost:8000/powerbi/process");
      
      const res = await fetch("http://localhost:8000/powerbi/process", {
        method: "POST",
        body: form,
      });

      console.log("📡 Response status:", res.status);
      const data = await res.json();
      console.log("📦 Response data:", data);

      if (!res.ok) {
        throw new Error(data?.detail || data?.message || `Server error: ${res.status}`);
      }

      // Update status boxes
      setStatusBoxes({ columns: true, powerbi: false, finished: false });
      
      setResult(data);
      console.log("✅ Success! Dataset published to Power BI Cloud...");
      
      // Extract dataset info
      const reportUrl = data?.dataset?.urls?.report;
      const datasetUrl = data?.dataset?.urls?.dataset;
      const datasetId = data?.dataset?.id;
      const workspaceId = data?.dataset?.workspace_id || "7219790d-ee43-4137-b293-e3c477a754f0";
      const pushedTableName = data?.dataset?.table;
      
      // Create table entry
      const newTable = {
        id: datasetId,
        name: pushedTableName,
        datasetName: data?.dataset?.name,
        workspaceId: workspaceId,
        reportUrl: reportUrl,
        datasetUrl: datasetUrl,
        powerbiUrl: reportUrl || datasetUrl || (datasetId ? `https://app.powerbi.com/groups/${workspaceId}/datasets/${datasetId}` : "https://app.powerbi.com/home")
      };
      
      // Add to pushed tables list
      setPushedTables([...pushedTables, newTable]);
      
      // Update status boxes immediately
      setStatusBoxes({ columns: true, powerbi: true, finished: true });
      
      console.log("✅ Dataset saved to Power BI Cloud!");
      console.log("📌 Dataset persists in Cloud - not auto-opening");
      console.log("Click 'Open in Power BI Cloud' button to view your data");
    } catch (e: any) {
      const errorMsg = e?.message || "Failed to publish";
      console.error("❌ Error:", errorMsg, e);
      setError(errorMsg);
      setStatusBoxes({ columns: false, powerbi: false, finished: false });
    } finally {
      setPublishing(false);
    }
  };

  const publishToPowerBI = async () => {
    // Authenticate and publish in backend
    await authenticateAndPublish();
  };

  if (!hasCSV && !hasDAX) {
    return (
      <div className="wrap">
        <h2>🔐 Migration - Power BI Integration</h2>
        <div style={{ marginTop: 20, padding: "20px", backgroundColor: "#fff3cd", borderRadius: "8px", border: "2px solid #ffc107" }}>
          <h3 style={{ marginTop: 0, color: "#856404" }}>⚠️ No Data to Migrate</h3>
          <p style={{ color: "#856404", marginBottom: "20px" }}>
            It looks like you haven't exported your CSV/DAX data yet. Please follow these steps:
          </p>
          
          <div style={{ backgroundColor: "white", padding: "15px", borderRadius: "6px", marginBottom: "15px" }}>
            <div style={{ marginBottom: "12px" }}>
              <strong style={{ color: "#333", fontSize: "16px" }}>📋 Required Steps:</strong>
            </div>
            <ol style={{ color: "#555", lineHeight: "1.8" }}>
              <li>Go back to <strong>Export page</strong></li>
              <li>Select your <strong>Qlik table</strong></li>
              <li>Click <strong>"Export CSV/DAX"</strong> button</li>
              <li>Select <strong>"Continue to Migration"</strong></li>
              <li>This will return you here with your data ready to publish</li>
            </ol>
          </div>

          <div style={{ backgroundColor: "#e3f2fd", padding: "15px", borderRadius: "6px", marginBottom: "15px", border: "1px solid #1f77d2" }}>
            <strong style={{ color: "#1f77d2" }}>📱 What happens next:</strong>
            <ul style={{ color: "#555", marginTop: "10px" }}>
              <li>Click <strong>"Continue"</strong> button</li>
              <li>Login with device code at <code>microsoft.com/devicelogin</code></li>
              <li>Dataset automatically created in Power BI</li>
              <li>Power BI opens automatically</li>
            </ul>
          </div>

          <button 
            onClick={() => navigate(-1)}
            style={{
              padding: "12px 24px",
              backgroundColor: "#1f77d2",
              color: "white",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "16px",
              fontWeight: "bold"
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = "#1a5fa0"}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = "#1f77d2"}
          >
            ← Go Back to Export
          </button>
        </div>

        <div style={{ marginTop: 30, padding: "15px", backgroundColor: "#f5f5f5", borderRadius: "6px", fontSize: "12px", color: "#666" }}>
          <strong>🔍 Debug Info:</strong>
          <div>CSV stored: {(sessionStorage.getItem("migration_csv")?.length || 0)} bytes</div>
          <div>DAX stored: {(sessionStorage.getItem("migration_dax")?.length || 0)} bytes</div>
          <div>CSV flag: {sessionStorage.getItem("migration_has_csv")}</div>
          <div>Table: {sessionStorage.getItem("migration_selected_table")}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="wrap">
      <h2>Migration</h2>

      <div style={{ marginTop: 8 }}>
        <p>Application: <strong>{appName}</strong></p>
        <p>Dataset (table): <strong>{tableName || "-"}</strong></p>
        <p>Rows: <strong>{rowCount}</strong> | Columns: <strong>{columns.length}</strong></p>
        
        <div style={{ marginTop: "15px", padding: "15px", backgroundColor: "#f5f5f5", borderRadius: "6px" }}>
          <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold", color: "#333" }}>
            📝 Custom Table Name (Optional):
          </label>
          <input
            type="text"
            value={customTableName}
            onChange={(e) => setCustomTableName(e.target.value)}
            placeholder="Enter table name or use default..."
            style={{
              width: "100%",
              padding: "10px",
              borderRadius: "4px",
              border: "1px solid #ddd",
              fontSize: "14px",
              boxSizing: "border-box"
            }}
          />
          <small style={{ display: "block", marginTop: "5px", color: "#666" }}>
            💡 This name will be used as the table name in Power BI
          </small>
        </div>
      </div>

      <div className="export-options" style={{ marginTop: 16 }}>
        <div className={`export-box ${hasCSV ? "" : "disabled"}`}>📄 CSV {hasCSV ? "Ready" : "Missing"}</div>
        <div className={`export-box ${hasDAX ? "" : "disabled"}`}>📊 DAX {hasDAX ? "Ready" : "Missing"}</div>
        <div className={`export-box ${hasJSON ? "" : "disabled"}`}>📋 JSON {hasJSON ? "Ready" : "Missing"}</div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="info-box">
          <span className="label">Columns</span>
          <span className="value">{columns.join(", ") || "-"}</span>
        </div>
      </div>

      <div className="page-actions" style={{ marginTop: 24 }}>
        {!hasCSV && !hasDAX && (
          <button className="go-back-btn" onClick={() => navigate(-1)} style={{ marginRight: "10px", backgroundColor: "#ff9800" }}>
            ⬅️ Go Back to Export
          </button>
        )}
        <button className="continue-btn" onClick={publishToPowerBI} disabled={publishing || (!hasCSV && !hasDAX)} style={{
          padding: "12px 24px",
          backgroundColor: publishing ? "#ccc" : "#28a745",
          color: "white",
          border: "none",
          borderRadius: "6px",
          cursor: publishing ? "not-allowed" : "pointer",
          fontSize: "16px",
          fontWeight: "bold",
          transition: "all 0.3s ease"
        }}>
          {publishing ? "🔄 Publishing…" : "✅ Publish to Power BI"}
        </button>
      </div>

      {publishing && (
        <div style={{ marginTop: "20px", padding: "20px", backgroundColor: "#e3f2fd", borderRadius: "8px", border: "2px solid #1f77d2" }}>
          <div style={{ fontSize: "14px", color: "#1f77d2", fontWeight: "bold", marginBottom: "15px" }}>Publishing to Power BI... 🚀</div>
          
          {/* Mini Status Boxes while Publishing */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
            <div style={{
              backgroundColor: statusBoxes.columns ? "#4caf50" : "#e0e0e0",
              height: "8px",
              borderRadius: "4px",
              transition: "all 0.3s ease"
            }} />
            <div style={{
              backgroundColor: statusBoxes.powerbi ? "#4caf50" : "#e0e0e0",
              height: "8px",
              borderRadius: "4px",
              transition: "all 0.3s ease"
            }} />
            <div style={{
              backgroundColor: statusBoxes.finished ? "#4caf50" : "#e0e0e0",
              height: "8px",
              borderRadius: "4px",
              transition: "all 0.3s ease"
            }} />
          </div>
        </div>
      )}

      {error && (
        <div style={{
          marginTop: 16,
          backgroundColor: "#ffebee",
          padding: "16px",
          borderRadius: "8px",
          border: "2px solid #f44336",
          color: "#c62828"
        }}>
          <div style={{ fontWeight: "bold", fontSize: "16px", marginBottom: "8px" }}>❌ Error</div>
          <div>{error}</div>
        </div>
      )}

      {/* Debug Info */}
      <div style={{ marginTop: 20, padding: "10px", backgroundColor: "#f0f0f0", borderRadius: "4px", fontSize: "12px" }}>
        <strong>🔍 Debug Info:</strong>
        <div>CSV size: {(sessionStorage.getItem("migration_csv")?.length || 0)} bytes</div>
        <div>DAX size: {(sessionStorage.getItem("migration_dax")?.length || 0)} bytes</div>
        <div>CSV flag: {sessionStorage.getItem("migration_has_csv")}</div>
        <div>DAX flag: {sessionStorage.getItem("migration_has_dax")}</div>
      </div>

      {result && (
        <div className="info-grid" style={{ marginTop: 20 }}>
          <div style={{ backgroundColor: "#d4edda", padding: "20px", borderRadius: "8px", marginBottom: "20px", border: "2px solid #28a745", textAlign: "center" }}>
            <h3 style={{ color: "#155724", margin: "0 0 10px 0", fontSize: "20px" }}>✅ Successfully Published to Power BI!</h3>
            <p style={{ color: "#155724", marginTop: "10px", marginBottom: "5px" }}>
              <strong>{result?.dataset?.name}</strong>
            </p>
            <p style={{ color: "#155724", margin: "5px 0" }}>
              📊 {result?.local_parse?.row_count} rows | 📋 {result?.local_parse?.columns?.length} columns
            </p>
            <div style={{ backgroundColor: "rgba(255,255,255,0.3)", padding: "10px", borderRadius: "6px", marginTop: "10px", fontSize: "12px", color: "#155724" }}>
              <strong>💾 Dataset saved to Power BI Cloud!</strong>
              <div style={{ marginTop: "5px" }}>You can access it anytime - even if you close this app</div>
            </div>
          </div>

          {/* 3 Status Boxes */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "15px", marginTop: "20px", marginBottom: "20px" }}>
            <div style={{
              backgroundColor: statusBoxes.columns ? "#c8e6c9" : "#f5f5f5",
              padding: "20px",
              borderRadius: "8px",
              textAlign: "center",
              border: `2px solid ${statusBoxes.columns ? "#4caf50" : "#ddd"}`,
              transition: "all 0.3s ease"
            }}>
              <div style={{ fontSize: "24px", marginBottom: "10px" }}>📊</div>
              <div style={{ fontWeight: "bold", fontSize: "16px", color: statusBoxes.columns ? "#2e7d32" : "#666" }}>
                Column
              </div>
              <div style={{ fontSize: "14px", marginTop: "8px", color: statusBoxes.columns ? "#2e7d32" : "#999" }}>
                {statusBoxes.columns ? "✅ Finished" : "Processing..."}
              </div>
            </div>

            <div style={{
              backgroundColor: statusBoxes.powerbi ? "#c8e6c9" : "#f5f5f5",
              padding: "20px",
              borderRadius: "8px",
              textAlign: "center",
              border: `2px solid ${statusBoxes.powerbi ? "#4caf50" : "#ddd"}`,
              transition: "all 0.3s ease"
            }}>
              <div style={{ fontSize: "24px", marginBottom: "10px" }}>☁️</div>
              <div style={{ fontWeight: "bold", fontSize: "16px", color: statusBoxes.powerbi ? "#2e7d32" : "#666" }}>
                PowerBI
              </div>
              <div style={{ fontSize: "14px", marginTop: "8px", color: statusBoxes.powerbi ? "#2e7d32" : "#999" }}>
                {statusBoxes.powerbi ? "✅ Opened" : "Waiting..."}
              </div>
            </div>

            <div style={{
              backgroundColor: statusBoxes.finished ? "#c8e6c9" : "#f5f5f5",
              padding: "20px",
              borderRadius: "8px",
              textAlign: "center",
              border: `2px solid ${statusBoxes.finished ? "#4caf50" : "#ddd"}`,
              transition: "all 0.3s ease"
            }}>
              <div style={{ fontSize: "24px", marginBottom: "10px" }}>✨</div>
              <div style={{ fontWeight: "bold", fontSize: "16px", color: statusBoxes.finished ? "#2e7d32" : "#666" }}>
                Complete
              </div>
              <div style={{ fontSize: "14px", marginTop: "8px", color: statusBoxes.finished ? "#2e7d32" : "#999" }}>
                {statusBoxes.finished ? "✅ Yes" : "Not yet..."}
              </div>
            </div>
          </div>

          {/* Pushed Tables List */}
          <div style={{ marginTop: "20px", padding: "20px", backgroundColor: "#e8f5e9", borderRadius: "8px", border: "2px solid #28a745" }}>
            <div style={{ color: "#155724", fontWeight: "bold", marginBottom: "15px", fontSize: "16px" }}>
              📋 Pushed Tables ({pushedTables.length})
            </div>
            
            {pushedTables.length > 0 ? (
              <div style={{ display: "grid", gap: "12px" }}>
                {pushedTables.map((table, idx) => (
                  <div key={idx} style={{ 
                    backgroundColor: "rgba(255,255,255,0.7)",
                    padding: "12px",
                    borderRadius: "6px",
                    border: "1px solid #4caf50",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center"
                  }}>
                    <div>
                      <div style={{ fontWeight: "bold", color: "#155724" }}>📊 {table.name}</div>
                      <div style={{ fontSize: "12px", color: "#666", marginTop: "4px" }}>
                        Dataset: <code style={{ backgroundColor: "#fff", padding: "2px 4px", fontSize: "11px" }}>{table.datasetName}</code>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        console.log("🚀 Opening Power BI for table:", table.name);
                        window.open(table.powerbiUrl, `PowerBI_${idx}`);
                      }}
                      style={{
                        padding: "8px 16px",
                        backgroundColor: "#4caf50",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                        fontSize: "13px",
                        fontWeight: "bold",
                        whiteSpace: "nowrap"
                      }}
                      onMouseOver={(e) => e.currentTarget.style.backgroundColor = "#388e3c"}
                      onMouseOut={(e) => e.currentTarget.style.backgroundColor = "#4caf50"}
                    >
                      ☁️ Open in Power BI
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "#666", fontSize: "13px", fontStyle: "italic" }}>
                No tables pushed yet. Click "Publish to Power BI" to push your first table.
              </div>
            )}
            
            <div style={{ marginTop: "15px", padding: "10px", backgroundColor: "rgba(255,255,255,0.5)", borderRadius: "4px", fontStyle: "italic", color: "#155724" }}>
              ✓ Your datasets are stored in Power BI Cloud and will be available even after you close this application
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
