import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./PublishPage.css";

// Stepper Component
interface StepperProps {
  currentStep: number;
  steps: string[];
}

function Stepper({ currentStep, steps }: StepperProps) {
  return (
    <div className="stepper-container">
      <div className="stepper">
        {steps.map((step, idx) => (
          <div key={idx} className="step">
            <div
              className={`step-circle ${
                idx < currentStep
                  ? "completed"
                  : idx === currentStep
                  ? "active"
                  : ""
              }`}
            >
              {idx < currentStep ? "✓" : idx + 1}
            </div>
            <div
              className={`step-label ${
                idx < currentStep
                  ? "completed"
                  : idx === currentStep
                  ? "active"
                  : ""
              }`}
            >
              {step}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const STEPPER_STEPS = [
  "Prepare Data",
  "Authenticate",
  "Publish Dataset",
  "Generate URL",
  "Publish",
];

export default function PublishPage() {
  const navigate = useNavigate();

  // Get data from sessionStorage
  const tableName = sessionStorage.getItem("migration_selected_table") || "";
  const appName = sessionStorage.getItem("migration_appName") || sessionStorage.getItem("appName") || "Unknown";
  const hasCSV = sessionStorage.getItem("migration_has_csv") === "true";
  const hasDAX = sessionStorage.getItem("migration_has_dax") === "true";
  const rowCount = Number(sessionStorage.getItem("migration_row_count") || "0");
  const columns = JSON.parse(sessionStorage.getItem("migration_columns") || "[]");

  const [customTableName, setCustomTableName] = useState(tableName);
  const [datasetURL, setDatasetURL] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [statusBoxes, setStatusBoxes] = useState({ columns: false, powerbi: false, finished: false });
  const [result, setResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);
  const [publishStartTime, setPublishStartTime] = useState<Date | null>(null);
  const [publishEndTime, setPublishEndTime] = useState<Date | null>(null);
  const [publishDuration, setPublishDuration] = useState<number>(0);
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [publishedTableName, setPublishedTableName] = useState<string>("");
  const [csvData, setCSVData] = useState<string>("");
  const [daxData, setDAXData] = useState<string>("");

  // Auto-publish on page load
  useEffect(() => {
    const timer = setTimeout(() => {
      handlePublish();
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  // Format duration as 00m:00s:000ms
  const formatDuration = (durationMs: number) => {
    const totalSeconds = Math.floor(durationMs / 1000);
    const milliseconds = durationMs % 1000;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}m:${String(seconds).padStart(2, '0')}s:${String(milliseconds).padStart(3, '0')}ms`;
  };

  // Timer for publishing duration
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (publishing && publishStartTime && !result) {
      interval = setInterval(() => {
        const now = new Date();
        const elapsed = now.getTime() - publishStartTime.getTime();
        setElapsedTime(elapsed);
      }, 100);
    }
    return () => clearInterval(interval);
  }, [publishing, publishStartTime, result]);

  // Monitor CSV/DAX data updates
  useEffect(() => {
    if (csvData) console.log("✅ CSV Data updated:", csvData.length, "characters");
    if (daxData) console.log("✅ DAX Data updated:", daxData.length, "characters");
  }, [csvData, daxData]);

  const handlePublish = async () => {
    try {
      const startTime = new Date();
      setPublishStartTime(startTime);
      setPublishing(true);
      setCurrentStep(0);

      // Create table name with date and time
      const dateStr = startTime.toISOString().split('T')[0]; // YYYY-MM-DD
      const timeStr = startTime.toTimeString().split(' ')[0].replace(/:/g, '-'); // HH-MM-SS
      const tableNameWithDateTime = `${customTableName}_${dateStr}_${timeStr}`;
      setPublishedTableName(tableNameWithDateTime);

      // Step 1: Prepare data
      setCurrentStep(0);
      console.log("📦 Step 1: Preparing data...");
      const csvText = sessionStorage.getItem("migration_csv") || "";
      const daxText = sessionStorage.getItem("migration_dax") || "";
      
      // Store CSV/DAX data for PDF report
      console.log("📊 CSV Data length:", csvText.length);
      console.log("📊 DAX Data length:", daxText.length);
      setCSVData(csvText);
      setDAXData(daxText);

      if (!hasCSV && !hasDAX) {
        throw new Error("No formats selected. Please go back to Export page.");
      }

      // Step 2: Initiate authentication (Device Code Flow)
      setCurrentStep(1);
      setStatusBoxes({ columns: true, powerbi: false, finished: false });
      console.log("🔐 Step 2: Initiating Power BI authentication...");
      
      // const authRes = await fetch("http://localhost:8000/powerbi/login/acquire-token", {
      const authRes = await fetch("https://qlik-sense-cloud.onrender.com/powerbi/login/acquire-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (!authRes.ok) {
        const errData = await authRes.json();
        throw new Error(errData?.detail || "Authentication initiation failed");
      }

      const authData = await authRes.json();
      console.log("✅ Device code generated. User needs to authenticate.");
      console.log("Instructions:", authData?.message || "Check backend logs");

      // Step 3: Wait for user to complete authentication (up to 30 seconds)
      let authAttempts = 0;
      const maxAttempts = 30; // 30 seconds total
      let isAuthenticated = false;

      while (authAttempts < maxAttempts && !isAuthenticated) {
        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second between checks

        try {
          // const statusRes = await fetch("http://localhost:8000/powerbi/login/status", {
          const statusRes = await fetch("https://qlik-sense-cloud.onrender.com/powerbi/login/status", {
            method: "POST",
          });
          const statusData = await statusRes.json();

          if (statusData.logged_in) {
            console.log("✅ Authentication successful!");
            isAuthenticated = true;
            break;
          }
        } catch (e) {
          console.warn("⚠️ Error checking auth status:", e);
        }

        authAttempts++;
        if (authAttempts % 5 === 0) {
          console.log(`⏳ Still waiting for authentication... (${authAttempts}s elapsed)`);
        }
      }

      if (!isAuthenticated) {
        throw new Error("Authentication timeout. Please login at microsoft.com/devicelogin and try again.");
      }

      // Step 4: Publish dataset
      setCurrentStep(2);
      setStatusBoxes({ columns: true, powerbi: true, finished: false });
      console.log("📤 Step 3: Publishing to Power BI...");

      const form = new FormData();
      if (hasCSV && csvText) {
        form.append("csv_file", new Blob([csvText], { type: "text/csv" }), `${tableNameWithDateTime}.csv`);
      }
      if (hasDAX && daxText) {
        form.append("dax_file", new Blob([daxText], { type: "text/plain" }), `${tableNameWithDateTime}.dax`);
      }
      form.append("meta_app_name", appName);
      form.append("meta_table", tableNameWithDateTime);
      form.append("has_csv", hasCSV ? "true" : "false");
      form.append("has_dax", hasDAX ? "true" : "false");

      // https://qlik-sense-cloud.onrender.com
      // const res = await fetch("http://localhost:8000/powerbi/process", {
      const res = await fetch("https://qlik-sense-cloud.onrender.com/powerbi/process", {
        method: "POST",
        body: form,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.detail || "Publishing failed");
      }

      // Step 5: Generate URL
      setCurrentStep(3);
      console.log("🔗 Step 4: Generating dataset URL...");
      
      const realDatasetURL = data?.dataset?.urls?.dataset || 
                            data?.dataset?.urls?.report ||
                            (data?.dataset?.id ? `https://app.powerbi.com/groups/${data.dataset.workspace_id}/datasets/${data.dataset.id}` : "");
      
      if (!realDatasetURL) {
        throw new Error("No dataset URL returned from Power BI. Please check backend response.");
      }

      setDatasetURL(realDatasetURL);

      setStatusBoxes({ columns: true, powerbi: true, finished: true });
      setCurrentStep(5); // Show all steps completed (green checkmarks)
      
      const endTime = new Date();
      setPublishEndTime(endTime);
      const durationMs = endTime.getTime() - startTime.getTime();
      setPublishDuration(durationMs);
      
      setResult(data);
      console.log("✅ Dataset published successfully!");
      console.log("📎 Dataset URL:", realDatasetURL);
      console.log("🏢 Workspace ID:", data?.dataset?.workspace_id);
      console.log("📊 Dataset ID:", data?.dataset?.id);

    } catch (err: any) {
      console.error("❌ Publishing error:", err);
      setStatusBoxes({ columns: false, powerbi: false, finished: false });
    } finally {
      setPublishing(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(datasetURL).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      // Silently fail if copy fails
    });
  };

  const downloadDataset = async () => {
    try {
      console.log('📥 Generating PDF with CSV and DAX data...');
      
      const element = document.getElementById('report-content');
      if (!element) {
        alert('Report content not found. Please try again.');
        return;
      }

      // Make element visible for html2pdf
      const originalStyle = element.getAttribute('style');
      element.style.position = 'relative';
      element.style.left = '0';
      element.style.top = '0';
      element.style.display = 'block';
      element.style.visibility = 'visible';
      
      // Load html2pdf from CDN
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js';
      document.head.appendChild(script);

      script.onload = () => {
        const win = window as any;
        if (win.html2pdf) {
          setTimeout(() => {
            const opt = {
              margin: 10,
              filename: `${publishedTableName}_Report.pdf`,
              image: { type: 'jpeg', quality: 0.98 },
              html2canvas: { scale: 2 },
              jsPDF: { orientation: 'portrait', unit: 'mm', format: 'a4' }
            };
            
            win.html2pdf()
              .set(opt)
              .from(element)
              .save()
              .then(() => {
                // Restore original style
                if (originalStyle) {
                  element.setAttribute('style', originalStyle);
                } else {
                  element.style.position = 'absolute';
                  element.style.left = '-9999px';
                  element.style.top = '-9999px';
                }
                console.log('✅ PDF generated and downloaded successfully!');
              });
          }, 500);
        }
      };
    } catch (err) {
      console.error('❌ PDF generation failed:', err);
      alert('Failed to generate PDF. Please try again.');
    }
  };

  const openInPowerBI = () => {
    if (datasetURL) {
      window.open(datasetURL, "_blank");
    }
  };

  return (
    <div className="publish-container">
      <h2 className="publish-header">📤 Publish to Power BI</h2>

      {/* STEPPER - Show while publishing and after completion */}
      {(publishing || result) && (
        <Stepper currentStep={currentStep} steps={STEPPER_STEPS} />
      )}

      {/* LOADING MESSAGE - Show only while publishing and no result yet */}
      {publishing && !result && (
        <div style={{ 
          textAlign: "center", 
          padding: "40px 20px",
          fontSize: "18px",
          color: "#555"
        }}>
          <div style={{ marginBottom: "20px", fontSize: "48px" }}>⏳</div>
          <div>Publishing your dataset to Power BI...</div>
          <div style={{ fontSize: "14px", marginTop: "10px", color: "#999" }}>
            This may take a few moments.
          </div>
          {publishStartTime && (
            <div style={{ 
              marginTop: "20px", 
              fontSize: "18px", 
              fontWeight: "bold",
              color: "#0078d4",
              padding: "12px 20px",
              backgroundColor: "#e7f3ff",
              borderRadius: "5px",
              display: "inline-block"
            }}>
              ⏱️ Publishing time: {formatDuration(elapsedTime)}
            </div>
          )}
        </div>
      )}

      {/* FORM SECTION - HIDDEN */}
      {false && (
        <div className="form-section">
          <div className="form-group">
            <label className="form-label">📋 Custom Table Name</label>
            <input
              type="text"
              value={customTableName}
              onChange={(e) => setCustomTableName(e.target.value)}
              placeholder="Enter table name"
              disabled={publishing}
              className="form-input"
            />
          </div>

          {/* STATUS BOXES */}
          <div className="status-boxes">
            {/* CSV Status */}
            <div className={`status-box ${statusBoxes.columns ? "active" : ""}`}>
              <div className="status-box-icon">📊</div>
              <div className="status-box-label">CSV Data</div>
              <div className="status-box-status">
                {statusBoxes.columns ? "✅ Prepared" : "⏳ Pending"}
              </div>
            </div>

            {/* Power BI Auth Status */}
            <div className={`status-box ${statusBoxes.powerbi ? "active" : ""}`}>
              <div className="status-box-icon">⚡</div>
              <div className="status-box-label">Power BI Auth</div>
              <div className="status-box-status">
                {statusBoxes.powerbi ? "✅ Authenticated" : "⏳ Pending"}
              </div>
            </div>

            {/* URL Status */}
            <div className={`status-box ${statusBoxes.finished ? "active" : ""}`}>
              <div className="status-box-icon">🔗</div>
              <div className="status-box-label">Dataset URL</div>
              <div className="status-box-status">
                {statusBoxes.finished ? "✅ Generated" : "⏳ Pending"}
              </div>
            </div>
          </div>

          {/* PUBLISH BUTTON */}
          <button
            onClick={handlePublish}
            disabled={publishing}
            className="btn btn-primary"
          >
            {publishing ? "⏳ Publishing..." : "🚀 Publish Now"}
          </button>

          {/* Authentication Instructions */}
          {publishing && (
            <div className="instruction-box">
              <div className="instruction-title">🔐 Authentication Required</div>
              <div className="instruction-line">1️⃣ A device code has been generated</div>
              <div className="instruction-line">2️⃣ Go to: <strong>https://microsoft.com/devicelogin</strong></div>
              <div className="instruction-line">3️⃣ Enter the code shown in the console</div>
              <div className="instruction-line">4️⃣ Wait for this page to complete...</div>
            </div>
          )}
        </div>
      )}

      {/* SUCCESS SECTION */}
      {result && (
        <div className="success-section">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <div className="success-title">✨ Success!</div>
            <div style={{ 
              fontSize: "14px", 
              color: "#0078d4",
              fontWeight: "bold",
              padding: "8px 15px",
              backgroundColor: "#e7f3ff",
              borderRadius: "5px"
            }}>
              ⏱️ Published in {formatDuration(publishDuration)}
            </div>
          </div>
          <div className="success-message">
            Dataset "<strong>{publishedTableName}</strong>" published to Power BI Cloud
          </div>

          {/* URL BOX - TURNS GREEN AFTER GENERATION */}
          <div className="url-box">
            <div className="url-label">🔗 Dataset URL (GREEN - Ready)</div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "8px" }}>
              <input
                type="text"
                value={datasetURL}
                readOnly
                className="url-input"
              />
              <button
                onClick={copyToClipboard}
                className="btn btn-small"
                style={{
                  padding: "8px 12px",
                  width:"50px",
                  height : "50px",
                  whiteSpace: "nowrap",
                  backgroundColor: copied ? "#27ae60" : "#3498db",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "14px",
                  transition: "background-color 0.3s"
                }}
              >
                {copied ? "✅ Copied!" : "📋"}
              </button>
            </div>
            <div className="url-note">
              ✓ This URL is ready to use. Click "Open in Power BI" to view your dataset.
            </div>
          </div>

          {/* INFO BOXES */}
          <div className="info-boxes">
            <div className="info-box">
              <div className="info-box-label">Table Name (With Date & Time)</div>
              <div className="info-box-value" style={{ fontSize: "12px", wordBreak: "break-word" }}>{publishedTableName}</div>
            </div>
            <div className="info-box">
              <div className="info-box-label">Published Date & Time</div>
              <div className="info-box-value">{publishEndTime ? publishEndTime.toLocaleString() : new Date().toLocaleString()}</div>
            </div>
            <div className="info-box">
              <div className="info-box-label">Publishing Duration</div>
              <div className="info-box-value">⏱️ {formatDuration(publishDuration)}</div>
            </div>
            <div className="info-box">
              <div className="info-box-label">Total Rows</div>
              <div className="info-box-value">{rowCount}</div>
            </div>
            <div className="info-box">
              <div className="info-box-label">Total Columns</div>
              <div className="info-box-value">{columns.length}</div>
            </div>
            <div className="info-box">
              <div className="info-box-label">Status</div>
              <div className="info-box-value">✅ Published</div>
            </div>
          </div>

          {/* ACTION BUTTONS */}
          <div className="btn-group">
            <button
              onClick={openInPowerBI}
              className="btn btn-small btn-success"
            >
              ☁️ Open in Power BI
            </button>
            <button
              onClick={downloadDataset}
              className="btn btn-small btn-warning"
            >
              📥 Download Dataset
            </button>
          </div>

          {/* COMPLETION MESSAGE */}
          <div className="completion-message">
            🎉 Your dataset is now live in Power BI! You can start creating reports and dashboards with your data.
          </div>
        </div>
      )}

      {/* HIDDEN REPORT CONTENT FOR PDF GENERATION */}
      <div id="report-content" style={{
        position: 'absolute',
        left: '-9999px',
        top: '-9999px',
        width: '1000px',
        backgroundColor: 'white'
      }}>
        <div style={{ padding: '40px', fontFamily: 'Arial, sans-serif', color: '#333' }}>
          <h1 style={{ color: '#0078d4', borderBottom: '3px solid #0078d4', paddingBottom: '15px', marginBottom: '20px', fontSize: '28px' }}>
            📊 Power BI Dataset Report
          </h1>
          
          <h2 style={{ color: '#0078d4', marginTop: '25px', marginBottom: '15px', fontSize: '18px', borderLeft: '4px solid #0078d4', paddingLeft: '10px' }}>
            📋 Table Information
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', margin: '15px 0' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Original Table Name:</td>
                <td style={{ padding: '10px 12px' }}>{customTableName}</td>
              </tr>
              <tr style={{ backgroundColor: '#f9f9f9', borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Published Table Name:</td>
                <td style={{ padding: '10px 12px', backgroundColor: '#fff3cd', fontWeight: 'bold' }}>{publishedTableName}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Application:</td>
                <td style={{ padding: '10px 12px' }}>{appName}</td>
              </tr>
              <tr style={{ backgroundColor: '#f9f9f9', borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Published Date & Time:</td>
                <td style={{ padding: '10px 12px' }}>{publishEndTime ? publishEndTime.toLocaleString() : new Date().toLocaleString()}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Publishing Duration:</td>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>{formatDuration(publishDuration)}</td>
              </tr>
            </tbody>
          </table>

          <h2 style={{ color: '#0078d4', marginTop: '25px', marginBottom: '15px', fontSize: '18px', borderLeft: '4px solid #0078d4', paddingLeft: '10px' }}>
            📊 Dataset Details
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', margin: '15px 0' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Total Rows:</td>
                <td style={{ padding: '10px 12px' }}>{rowCount}</td>
              </tr>
              <tr style={{ backgroundColor: '#f9f9f9', borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Total Columns:</td>
                <td style={{ padding: '10px 12px' }}>{columns.length}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Export Format:</td>
                <td style={{ padding: '10px 12px' }}>{hasCSV ? "✓ CSV" : "✗"} {hasDAX ? "✓ DAX" : "✗"}</td>
              </tr>
            </tbody>
          </table>

          <h2 style={{ color: '#0078d4', marginTop: '25px', marginBottom: '15px', fontSize: '18px', borderLeft: '4px solid #0078d4', paddingLeft: '10px' }}>
            📑 Columns ({columns.length} total)
          </h2>
          <pre style={{ backgroundColor: '#f5f5f5', padding: '15px', borderRadius: '5px', borderLeft: '3px solid #0078d4', fontSize: '12px', overflow: 'auto' }}>
            {columns.map((col: string, idx: number) => `${idx + 1}. ${col}`).join("\n")}
          </pre>

          <h2 style={{ color: '#0078d4', marginTop: '25px', marginBottom: '15px', fontSize: '18px', borderLeft: '4px solid #0078d4', paddingLeft: '10px' }}>
            ☁️ Power BI Information
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', margin: '15px 0' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Dataset URL:</td>
                <td style={{ padding: '10px 12px', wordBreak: 'break-all', fontSize: '12px' }}>{datasetURL}</td>
              </tr>
              <tr style={{ backgroundColor: '#f9f9f9', borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Status:</td>
                <td style={{ padding: '10px 12px', color: '#107c10', fontWeight: 'bold' }}>✅ Published to Power BI Cloud</td>
              </tr>
            </tbody>
          </table>

          <h2 style={{ color: '#0078d4', marginTop: '25px', marginBottom: '15px', fontSize: '18px', borderLeft: '4px solid #0078d4', paddingLeft: '10px' }}>
            ✅ Export Status
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', margin: '15px 0' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>CSV Processed:</td>
                <td style={{ padding: '10px 12px' }}>{hasCSV ? "✅ Yes" : "❌ No"}</td>
              </tr>
              <tr style={{ backgroundColor: '#f9f9f9', borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>DAX Processed:</td>
                <td style={{ padding: '10px 12px' }}>{hasDAX ? "✅ Yes" : "❌ No"}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #e0e0e0' }}>
                <td style={{ padding: '10px 12px', fontWeight: 'bold' }}>Dataset Published to Power BI:</td>
                <td style={{ padding: '10px 12px', color: '#107c10', fontWeight: 'bold' }}>✅ Successfully Published</td>
              </tr>
            </tbody>
          </table>

          {hasCSV && csvData && (
            <>
              <h2 style={{ color: '#0078d4', marginTop: '25px', marginBottom: '15px', fontSize: '18px', borderLeft: '4px solid #0078d4', paddingLeft: '10px' }}>
                📄 CSV Data
              </h2>
              <div style={{ backgroundColor: '#ffffff', padding: '15px', borderRadius: '5px', borderLeft: '3px solid #0078d4', fontSize: '11px', overflow: 'visible', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                {csvData}
              </div>
            </>
          )}

          {hasDAX && daxData && (
            <>
              <h2 style={{ color: '#0078d4', marginTop: '25px', marginBottom: '15px', fontSize: '18px', borderLeft: '4px solid #0078d4', paddingLeft: '10px' }}>
                🔧 DAX Query
              </h2>
              <div style={{ backgroundColor: '#ffffff', padding: '15px', borderRadius: '5px', borderLeft: '3px solid #0078d4', fontSize: '11px', overflow: 'visible', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                {daxData}
              </div>
            </>
          )}

          <div style={{ marginTop: '40px', fontSize: '11px', color: '#666', borderTop: '1px solid #ddd', paddingTop: '15px', textAlign: 'center' }}>
            <p><strong>Qlik to Power BI Migration Tool</strong></p>
            <p>This report was automatically generated on: {new Date().toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* BACK BUTTON */}
      <div className="publish-footer">
        <button
          onClick={() => navigate("/")}
          className="btn btn-secondary"
        >
          ← Back to Connect
        </button>
      </div>
    </div>
  
  );
}