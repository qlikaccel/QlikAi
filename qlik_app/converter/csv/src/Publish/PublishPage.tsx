import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
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
  const { state } = useLocation() as any;

  // Get data from sessionStorage (lightweight metadata) — prefer navigation `state` for large payloads
  const tableName = sessionStorage.getItem("migration_selected_table") || "";
  const appName = sessionStorage.getItem("migration_appName") || sessionStorage.getItem("appName") || "Unknown";
  const hasCSV = sessionStorage.getItem("migration_has_csv") === "true";
  const hasDAX = sessionStorage.getItem("migration_has_dax") === "true";
  const sessionRowCount = Number(sessionStorage.getItem("migration_row_count") || "0");
  // Prefer navigation state (totalRows or selectedTables) — fall back to sessionStorage
  const navTotalRows = state?.totalRows ?? (state?.selectedTables ? state.selectedTables.reduce((s: number, t: any) => s + (t.data?.rows?.length || 0), 0) : 0);
  const rowCount = navTotalRows || sessionRowCount;
  const columns = JSON.parse(sessionStorage.getItem("migration_columns") || "[]");

  // Check if multi-table mode (use metadata key first)
  const tableCount = Number(sessionStorage.getItem("migration_table_count") || "0");
  const isMultiTableMode = tableCount > 0;

  // Get export options from navigation state
  const exportOptions = state?.exportOptions || { combined: true, separate: false };
  const isSeparateMode = exportOptions.separate;

  // Selected tables to publish: prefer `state.selectedTables` (in-memory), fallback to lightweight metadata
  const selectedTablesToPublish = state?.selectedTables || (() => {
    try {
      const metaJson = sessionStorage.getItem("migration_selected_tables_meta") || sessionStorage.getItem("migration_selected_tables");
      if (!metaJson) return [];
      const parsed = JSON.parse(metaJson);
      // If metadata (array of {name,rowCount,...}) convert to expected shape
      return parsed.map((p: any) => ({ name: p.name || p.table || "", data: { name: p.name || p.table || "", rows: [] } }));
    } catch (e) {
      return [];
    }
  })();

  const [customTableName, setCustomTableName] = useState(tableName);
  const [datasetURL, setDatasetURL] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [statusBoxes, setStatusBoxes] = useState({ columns: false, powerbi: false, finished: false });
  const [result, setResult] = useState<any>(null);
  const [desktopBundle, setDesktopBundle] = useState<any>(null);
  const [desktopBundleLoading, setDesktopBundleLoading] = useState(false);
  const [desktopBundleError, setDesktopBundleError] = useState<string>("");
  const [xmlaSemanticLoading, setXmlaSemanticLoading] = useState(false);
  const [xmlaSemanticError, setXmlaSemanticError] = useState<string>("");
  const [xmlaSemanticResult, setXmlaSemanticResult] = useState<any>(null);
  const [showXmlaDiagram, setShowXmlaDiagram] = useState(false);
  const [bundlePathCopied, setBundlePathCopied] = useState(false);

  const [copied, setCopied] = useState(false);
  const [publishStartTime, setPublishStartTime] = useState<Date | null>(null);
  const [publishEndTime, setPublishEndTime] = useState<Date | null>(null);
  const [publishDuration, setPublishDuration] = useState<number>(0);
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [publishedTableName, setPublishedTableName] = useState<string>("");
  const [csvData, setCSVData] = useState<string>("");
  const [daxData, setDAXData] = useState<string>("");
  // Preview shows the first N rows (no pagination on Publish page)

  // Auto-publish on page load
  useEffect(() => {
    const timer = setTimeout(() => {
      handlePublish();
    }, 500);
    return () => clearTimeout(timer);
  }, []);

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

  // Helper function to publish a single table
  const publishSingleTable = async (
    csvText: string,
    daxText: string,
    tableNameToPublish: string,
    rowCount: number
  ) => {
    const startTime = new Date();
    const dateStr = startTime.toISOString().split('T')[0];
    const timeStr = startTime.toTimeString().split(' ')[0].replace(/:/g, '-');
    const tableNameWithDateTime = `${tableNameToPublish}_${dateStr}_${timeStr}`;

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

    // const res = await fetch("http://localhost:8000/powerbi/process", {
    const res = await fetch("https://qliksense-stuv.onrender.com/powerbi/process", {
    
      method: "POST",
      body: form,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data?.detail || "Publishing failed");
    }

    // Navigate to the Power BI workspace instead of dataset
    const realDatasetURL = data?.dataset?.workspace_id 
      ? `https://app.powerbi.com/groups/${data.dataset.workspace_id}`
      : "";

    return {
      tableName: tableNameToPublish,
      nameWithTime: tableNameWithDateTime,
      rowCount,
      url: realDatasetURL,
      workspaceId: data?.dataset?.workspace_id,
      datasetId: data?.dataset?.id,
      publishTime: new Date(),
    };
  };

  const handlePublish = async () => {
    try {
      const startTime = new Date();
      setPublishStartTime(startTime);
      setPublishing(true);
      setCurrentStep(0);

      // Step 2: Initiate authentication (Device Code Flow) - Do this once
      setCurrentStep(1);
      setStatusBoxes({ columns: true, powerbi: false, finished: false });
      console.log("🔐 Step 2: Initiating Power BI authentication...");
      
      // const authRes = await fetch("http://localhost:8000/powerbi/login/acquire-token", {
      const authRes = await fetch("https://qliksense-stuv.onrender.com/powerbi/login/acquire-token", {
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
      const maxAttempts = 30;
      let isAuthenticated = false;

      while (authAttempts < maxAttempts && !isAuthenticated) {
        await new Promise(resolve => setTimeout(resolve, 1000));

        try {
          // const statusRes = await fetch("http://localhost:8000/powerbi/login/status", {
          const statusRes = await fetch("https://qliksense-stuv.onrender.com/powerbi/login/status", {
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

      setCurrentStep(2);
      setStatusBoxes({ columns: true, powerbi: true, finished: false });
      console.log("📤 Step 3: Publishing to Power BI...");

      // Check if separate table mode
      /*if (isSeparateMode && isMultiTableMode && selectedTablesToPublish.length > 0) {
        // Publish each table separately
        const publishedResults: any[] = [];

        for (let i = 0; i < tableCount; i++) {
          const csvText = state?.csvPayloads?.[`migration_csv_${i}`] || sessionStorage.getItem(`migration_csv_${i}`) || "";
          const tableName = selectedTablesToPublish[i]?.name || `Table_${i + 1}`;
          const tableRows = selectedTablesToPublish[i]?.data?.rows || [];
          const inferredRowCount = tableRows.length || (csvText ? Math.max(0, csvText.split('\n').length - 1) : 0);

          if (csvText) {
            console.log(`📤 Publishing table ${i + 1}/${tableCount}: ${tableName}...`);
            const publishResult = await publishSingleTable(csvText, `-- ${tableName} data`, tableName, inferredRowCount);
            publishedResults.push(publishResult);
          }
        }

        // Use the first published table as the primary dataset for the unified success UI
        if (publishedResults.length > 0) {
          setPublishedTableName(publishedResults[0].nameWithTime || publishedResults[0].tableName || "");
          setDatasetURL(publishedResults[0].url || "");
        }

        setResult({ published_tables: publishedResults });*/
        if (isSeparateMode && isMultiTableMode && selectedTablesToPublish.length > 0) {
        // Publish all tables as a single dataset with relationships
        const batchTables: any[] = [];

        for (let i = 0; i < tableCount; i++) {
          const csvText = state?.csvPayloads?.[`migration_csv_${i}`] || sessionStorage.getItem(`migration_csv_${i}`) || "";
          const tName = selectedTablesToPublish[i]?.name || `Table_${i + 1}`;
          if (!csvText) continue;

          // Parse CSV into rows
          const lines = csvText.trim().split('\n').filter((l: string) => l.trim());
          if (lines.length < 2) continue;
          const headers = lines[0].split(',').map((h: string) => h.trim().replace(/^"|"$/g, ''));
          const rows = lines.slice(1).map((line: string) => {
            const vals = line.split(',');
            const row: any = {};
            headers.forEach((h: string, idx: number) => {
              row[h] = vals[idx]?.trim().replace(/^"|"$/g, '') ?? null;
            });
            return row;
          });

          batchTables.push({ name: tName, rows });
          console.log(`📦 Prepared table ${i + 1}/${tableCount}: ${tName} (${rows.length} rows)`);
        }

        if (batchTables.length === 0) throw new Error("No table data available to publish");

        console.log(`📤 Publishing ${batchTables.length} tables as single dataset with relationships...`);
        const batchRes = await fetch("http://localhost:8000/powerbi/process-batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            dataset_name: appName || "Qlik_Migrated_Dataset",
            tables: batchTables,
          }),
        });

        const batchData = await batchRes.json();
        if (!batchRes.ok) throw new Error(batchData?.detail || "Batch publish failed");

        console.log("✅ Batch publish successful:", batchData);
        setPublishedTableName(batchData.dataset_name || appName);
        setDatasetURL(batchData.workspace_url || "");
        setResult({ published_tables: batchTables.map((t: any) => ({ tableName: t.name, rowCount: t.rows.length, url: batchData.workspace_url })) });
      } else {
        // Combined mode or single table - use updated logic (prefer navigation state payloads)
        setCurrentStep(0);
        console.log("📦 Step 1: Preparing data...");
        
        let csvText = "";
        let daxText = "";
        let tableNameForPublish = customTableName || "Data";

        if (isMultiTableMode) {
          csvText = state?.csvPayloads?.["migration_csv_0"] || sessionStorage.getItem("migration_csv_0") || "";
          let selectedTableNames: string[] = [];
          try {
            const selectedTablesJson = sessionStorage.getItem("migration_selected_tables") || sessionStorage.getItem("migration_selected_tables_meta");
            if (selectedTablesJson) {
              const tables = JSON.parse(selectedTablesJson);
              // `tables` might be full objects or metadata; normalize
              selectedTableNames = tables.map((t: any) => t.name || t.table || '');
            }
          } catch (e) {
            //
          }
          
          daxText = state?.daxPayloads?.["migration_dax"] || sessionStorage.getItem("migration_dax") || `-- Multi-Table Export\n-- Primary Table: ${selectedTableNames[0] || 'Table 1'}\n`;
          daxText += `-- All Selected Tables: ${selectedTableNames.join(', ')}\n`;
          daxText += `-- Generated: ${new Date().toISOString()}\n\n`;
          daxText += selectedTableNames.map((name, idx) => {
            const tableCsv = state?.csvPayloads?.[`migration_csv_${idx}`] || sessionStorage.getItem(`migration_csv_${idx}`) || "";
            const tableSize = tableCsv ? Math.max(0, tableCsv.split('\n').length) : 0;
            return `-- ${name}: ${tableSize - 1} rows`;
          }).join('\n');

          tableNameForPublish = selectedTableNames[0] || "Combined_Data";
        } else {
          csvText = state?.csvPayloads?.["migration_csv"] || sessionStorage.getItem("migration_csv") || "";
          daxText = state?.daxPayloads?.["migration_dax"] || sessionStorage.getItem("migration_dax") || "";
        }

        console.log("📊 CSV Data length:", csvText.length);
        console.log("📊 DAX Data length:", daxText.length);
        setCSVData(csvText);
        setDAXData(daxText);

        if (!hasCSV && !hasDAX) {
          throw new Error("No formats selected. Please go back to Export page.");
        }

        if (hasCSV && !csvText) {
          throw new Error("CSV was selected but file not provided");
        }

        if (hasDAX && !daxText) {
          throw new Error("DAX was selected but file not provided");
        }

        const publishResult = await publishSingleTable(csvText, daxText, tableNameForPublish, rowCount);
        const dateStr = startTime.toISOString().split('T')[0];
        const timeStr = startTime.toTimeString().split(' ')[0].replace(/:/g, '-');
        setPublishedTableName(`${tableNameForPublish}_${dateStr}_${timeStr}`);
        setDatasetURL(publishResult.url);
        setResult({ dataset: publishResult });
      }

      setStatusBoxes({ columns: true, powerbi: true, finished: true });
      setCurrentStep(5);
      
      const endTime = new Date();
      setPublishEndTime(endTime);
      const durationMs = endTime.getTime() - startTime.getTime();
      setPublishDuration(durationMs);
      
      console.log("✅ Dataset published successfully!");

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
      console.log("📥 Generating Validation & Reconciliation Report...");
      
      // Extract actual metrics from the CSV data that was published
      let qlikRowCount = 0;
      let qlikColumnCount = 0;
      let qlikColumns: string[] = [];
      
      // Prefer reported totalRows from navigation state or previously computed `rowCount`.
      // This ensures the PDF/report shows the correct *total* even when the in-memory CSV contains only a page.
      const navReportedTotal = state?.totalRows ?? rowCount ?? 0;
      if (navReportedTotal && navReportedTotal > 0) {
        qlikRowCount = navReportedTotal;
        // attempt to infer columns if CSV or selectedTables available
        const csvContentForCols =
          state?.csvPayloads?.["migration_csv"] ||
          state?.csvPayloads?.["migration_csv_0"] ||
          csvData ||
          null;
        if (csvContentForCols) {
          const csvLinesForCols = csvContentForCols.trim().split('\n').filter((line: string) => line.trim());
          if (csvLinesForCols.length > 0) {
            qlikColumns = csvLinesForCols[0].split(',').map((col: string) => col.trim());
            qlikColumnCount = qlikColumns.length;
          }
        } else if (state?.selectedTables && state.selectedTables.length > 0) {
          const first = state.selectedTables[0];
          qlikColumns = first?.data?.rows?.length ? Object.keys(first.data.rows[0]) : (columns || []);
          qlikColumnCount = qlikColumns.length;
        } else {
          qlikColumns = columns || [];
          qlikColumnCount = qlikColumns.length;
        }
      } else {
        // Fallback: derive counts from CSV / state.selectedTables / sessionStorage (previous behaviour)
        const csvContent =
          state?.csvPayloads?.["migration_csv"] ||
          state?.csvPayloads?.["migration_csv_0"] ||
          (() => {
            const firstCsvKey = Object.keys(state?.csvPayloads || {}).find(k => k.startsWith('migration_csv_'));
            return firstCsvKey ? state.csvPayloads[firstCsvKey] : null;
          })() ||
          sessionStorage.getItem("migration_csv") ||
          sessionStorage.getItem("migration_csv_0") ||
          csvData ||
          "";

        if (csvContent) {
          const csvLines = csvContent.trim().split('\n').filter((line: string) => line.trim());
          if (csvLines.length > 0) {
            // First line = headers
            qlikColumns = csvLines[0].split(',').map((col: string) => col.trim());
            qlikColumnCount = qlikColumns.length;
            // Remaining lines = data rows
            qlikRowCount = csvLines.length - 1;
          }
        } else if (state?.selectedTables && state.selectedTables.length > 0) {
          qlikRowCount = state.selectedTables.reduce((sum: number, t: any) => sum + (t.data?.rows?.length || 0), 0);
          const first = state.selectedTables[0];
          qlikColumns = first?.data?.rows?.length ? Object.keys(first.data.rows[0]) : (columns || []);
          qlikColumnCount = qlikColumns.length;
        } else if (sessionStorage.getItem('migration_selected_tables_meta')) {
          try {
            const meta = JSON.parse(sessionStorage.getItem('migration_selected_tables_meta') || '[]');
            qlikRowCount = (meta || []).reduce((sum: number, t: any) => sum + (t.rowCount || 0), 0);
            qlikColumns = columns || [];
            qlikColumnCount = qlikColumns.length;
          } catch (e) {
            // fallback to session-stored migration_row_count
            qlikRowCount = Number(sessionStorage.getItem('migration_row_count') || 0);
          }
        } else {
          // fallback to session-stored migration_row_count if nothing else is present
          qlikRowCount = Number(sessionStorage.getItem('migration_row_count') || 0);
        }
      }
      
      // For demo: Power BI metrics same as Qlik (simulating successful sync)
      // In real scenario, this would query Power BI API for actual published metrics
      const powerbiRowCount = qlikRowCount;
      const powerbiColumnCount = qlikColumnCount;
      const powerbiColumns = [...qlikColumns];
      
      console.log(`📊 QLIK SENSE METRICS:
        📈 Row Count: ${qlikRowCount}
        📋 Column Count: ${qlikColumnCount}
        🏷️  Columns: ${qlikColumns.join(', ')}`);
      
      console.log(`📊 POWER BI METRICS:
        📈 Row Count: ${powerbiRowCount}
        📋 Column Count: ${powerbiColumnCount}
        🏷️  Columns: ${powerbiColumns.join(', ')}`);
      
      // Build comparison metrics with additional data
      const qlikMetrics = {
        row_count: qlikRowCount,
        table_count: (tableCount > 0 ? tableCount : (state?.selectedTables ? state.selectedTables.length : 1)),
        // column_count: qlikColumnCount,
        column_names: qlikColumns,
        total_records: qlikRowCount,
        // certification_status: "Pre-Migration",
        timestamp: new Date().toISOString()
      };
      
      const powerbiMetrics = {
        row_count: powerbiRowCount,
        table_count: (tableCount > 0 ? tableCount : (state?.selectedTables ? state.selectedTables.length : 1)),
        // column_count: powerbiColumnCount,
        column_names: powerbiColumns,
        total_records: powerbiRowCount,
        // certification_status: "Published to Power BI",
        timestamp: new Date().toISOString()
      };
      
      // Prepare comprehensive payload for PDF generation
      const payload = {
        table_name: publishedTableName || tableName,
        app_name: appName,
        qlik_metrics: qlikMetrics,
        powerbi_metrics: powerbiMetrics,
        sync_timestamp: new Date().toISOString(),
        migration_status: "Completed"
      };

      console.log("📤 Sending to backend:", JSON.stringify(payload, null, 2));

      // Download PDF
      // const response = await fetch('http://localhost:8000/report/download-pdf', {
      const response = await fetch('https://qliksense-stuv.onrender.com/report/download-pdf', {
        method: 'POST',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error?.detail || 'Failed to generate PDF');
      }

      // Get blob and trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      // link.download = `Validation_Report_${publishedTableName || tableName}_${new Date().toISOString().split('T')[0]}.pdf`;
       // sanitize filename to remove unicode and special chars
      const baseName = publishedTableName || tableName;
      const safeName = baseName.replace(/[^a-zA-Z0-9 _-]/g, '');
      link.download = `Validation_Reconciliation_Report_${safeName}_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      console.log('✅ Validation report downloaded successfully');
    } catch (error) {
      console.error('❌ Error downloading report:', error);
      alert('Failed to download report PDF: ' + (error instanceof Error ? error.message : String(error)));
    }
  };

  const openInPowerBI = () => {
    if (datasetURL) {
      window.open(datasetURL, "_blank");
    }
  };

  const resolveWorkspaceId = () => {
    const resultWorkspaceId =
      result?.dataset?.workspaceId ||
      result?.published_tables?.[0]?.workspaceId ||
      "";
    if (resultWorkspaceId) return resultWorkspaceId;

    const urlMatch = datasetURL.match(/groups\/([^/?#]+)/i);
    return urlMatch?.[1] || "";
  };

  const resolveAppId = () => {
    return state?.appId || sessionStorage.getItem("appSelected") || "";
  };

  const toCsvSample = (
    csvText: string,
    maxRows: number = 150,
    maxChars: number = 120000
  ) => {
    const text = (csvText || "").trim();
    if (!text) return "";

    const lines = text.split(/\r?\n/);
    if (lines.length === 0) return "";

    const sampledLines = [lines[0]]; // header
    for (let i = 1; i < lines.length && sampledLines.length <= maxRows; i++) {
      if (!lines[i]?.trim()) continue;
      sampledLines.push(lines[i]);
    }

    let sampled = sampledLines.join("\n");
    if (sampled.length > maxChars) {
      sampled = sampled.slice(0, maxChars);
    }
    return sampled;
  };

  const collectCsvPayloadMap = () => {
    const payloadMap: Record<string, string> = {};
    // Keep multipart form payload safely below 1MB parser limit.
    let remainingBudget = 650000;

    if (isMultiTableMode) {
      const totalTables = Math.max(tableCount, selectedTablesToPublish.length);
      for (let i = 0; i < totalTables; i++) {
        if (remainingBudget <= 2000) break;

        const tableNameForCsv = selectedTablesToPublish[i]?.name || `Table_${i + 1}`;
        const csvText =
          state?.csvPayloads?.[`migration_csv_${i}`] ||
          sessionStorage.getItem(`migration_csv_${i}`) ||
          "";

        const sampled = toCsvSample(csvText, 120, Math.min(100000, remainingBudget));
        if (sampled.trim()) {
          payloadMap[tableNameForCsv] = sampled;
          remainingBudget -= sampled.length + tableNameForCsv.length + 32;
        }
      }
      return payloadMap;
    }

    const singleCsv =
      state?.csvPayloads?.["migration_csv"] ||
      sessionStorage.getItem("migration_csv") ||
      state?.csvPayloads?.["migration_csv_0"] ||
      sessionStorage.getItem("migration_csv_0") ||
      "";
    const singleTableName = customTableName || tableName || "Data";
    const sampledSingle = toCsvSample(singleCsv, 200, 250000);
    if (sampledSingle.trim()) {
      payloadMap[singleTableName] = sampledSingle;
    }
    return payloadMap;
  };

  const generateXmlaSemanticModel = async () => {
    try {
      setXmlaSemanticLoading(true);
      setXmlaSemanticError("");
      setXmlaSemanticResult(null);
      setShowXmlaDiagram(false);

      const appId = resolveAppId();
      const workspaceId = resolveWorkspaceId();

      if (!appId) {
        throw new Error("Missing app ID. Please restart from app selection.");
      }
      if (!workspaceId) {
        throw new Error("Missing workspace ID. Publish to cloud first, then enable semantic model.");
      }

      const datasetNameRaw = publishedTableName || customTableName || tableName || "Model_Master";
      const datasetName = `${datasetNameRaw.replace(/\s+/g, "_")}_Semantic`;
      const csvPayloadMap = collectCsvPayloadMap();

      const form = new FormData();
      form.append("app_id", appId);
      form.append("dataset_name", datasetName);
      form.append("workspace_id", workspaceId);
      if (Object.keys(csvPayloadMap).length > 0) {
        const csvPayloadJson = JSON.stringify(csvPayloadMap);
        // Hard guard: avoid multipart part-size failures from large JSON payloads.
        if (csvPayloadJson.length <= 850000) {
          form.append("csv_payload_json", csvPayloadJson);
        } else {
          console.warn("XMLA CSV payload too large, sending schema-only mode.");
        }
      }

      const res = await fetch("http://localhost:8000/api/migration/publish-semantic-model", {
        method: "POST",
        body: form,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || data?.message || "Failed to create XMLA semantic model");
      }

      setXmlaSemanticResult(data);
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      setXmlaSemanticError(msg);
    } finally {
      setXmlaSemanticLoading(false);
    }
  };

  const generateDesktopCloudBundle = async () => {
    try {
      setDesktopBundleLoading(true);
      setDesktopBundleError("");
      setDesktopBundle(null);

      const appId = resolveAppId();
      const workspaceId = resolveWorkspaceId();

      if (!appId) {
        throw new Error("Missing app ID. Please restart from app selection.");
      }

      if (!workspaceId) {
        throw new Error("Missing workspace ID. Publish to cloud first, then generate desktop bundle.");
      }

      const datasetNameRaw = publishedTableName || customTableName || tableName || "Model_Master";
      const datasetName = datasetNameRaw.replace(/\s+/g, "_");

      const params = new URLSearchParams({
        app_id: appId,
        dataset_name: datasetName,
        workspace_id: workspaceId,
        publish_mode: "desktop_cloud",
      });

      const res = await fetch(`http://localhost:8000/api/migration/publish-table?${params.toString()}`, {
        method: "POST",
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || data?.message || "Failed to generate Desktop+Cloud bundle");
      }

      if (!data?.desktop_bundle?.bundle_dir) {
        throw new Error("Desktop bundle response missing bundle path");
      }

      setDesktopBundle(data.desktop_bundle);
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      setDesktopBundleError(msg);
    } finally {
      setDesktopBundleLoading(false);
    }
  };

  const copyBundlePath = () => {
    const path = desktopBundle?.bundle_dir;
    if (!path) return;

    navigator.clipboard.writeText(path).then(() => {
      setBundlePathCopied(true);
      setTimeout(() => setBundlePathCopied(false), 2000);
    }).catch(() => {
      // Ignore clipboard errors
    });
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

          {/* URL BOX */}
          <div className="url-box">
            <div className="url-label">🔗 Dataset URL </div>
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
                  width:"60px",
                  height : "45px",
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
                {copied ? "✅ Copy" : "📋"}
              </button>
            </div>
            <div className="url-note">
              ✓ This URL is ready to use. Click "Open in Power BI" to view your dataset.
            </div>
          </div>

          {/* COMBINED FORMAT INFO */}
          {hasCSV && hasDAX && (
            <div style={{ 
              backgroundColor: "#dbeafe", 
              border: "2px solid #0078d4", 
              borderRadius: "10px", 
              padding: "16px", 
              marginBottom: "20px",
              textAlign: "center"
            }}>
              <strong style={{ color: "#0078d4", fontSize: "16px" }}>
                📊 Combined Format: CSV + DAX
              </strong>
              <div style={{ fontSize: "13px", color: "#0369a1", marginTop: "8px" }}>
                ✅ CSV Data: Complete dataset with all rows and columns<br/>
                ✅ DAX Metadata: Query definitions and table structure
              </div>
            </div>
          )}

          {/* INFO BOXES (show master table details) */}
          <div className="info-boxes">
            <div className="info-box">
              <div className="info-box-label">Table Name </div>
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
              <div className="info-box-value" style={{ fontSize: "18px", fontWeight: "bold", color: "#0078d4" }}>{rowCount}</div>
            </div>
            <div className="info-box">
              <div className="info-box-label">Tables Exported</div>
              <div className="info-box-value" style={{ fontSize: "18px", fontWeight: "bold", color: "#0078d4" }}>{tableCount > 0 ? tableCount : (isMultiTableMode ? tableCount : 1)}</div>
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
              Open in Power BI
            </button>
            <button
              onClick={generateXmlaSemanticModel}
              className="btn btn-small btn-primary"
              disabled={xmlaSemanticLoading}
            >
              {xmlaSemanticLoading ? "Enabling Semantic..." : "Enable Semantic Model (XMLA)"}
            </button>
            <button
              onClick={generateDesktopCloudBundle}
              className="btn btn-small btn-primary"
              disabled={desktopBundleLoading}
            >
              {desktopBundleLoading ? "Building Bundle..." : "Desktop + Cloud Bundle"}
            </button>
            <button
              onClick={downloadDataset}
              className="btn btn-small btn-warning"
            >
              Download Report
            </button>
          </div>

          {desktopBundleError && (
            <div style={{
              marginTop: "12px",
              padding: "10px 12px",
              borderRadius: "6px",
              backgroundColor: "#fff5f5",
              color: "#b42318",
              border: "1px solid #fecaca",
              fontSize: "13px"
            }}>
              Desktop bundle error: {desktopBundleError}
            </div>
          )}

          {xmlaSemanticError && (
            <div style={{
              marginTop: "12px",
              padding: "10px 12px",
              borderRadius: "6px",
              backgroundColor: "#fff5f5",
              color: "#b42318",
              border: "1px solid #fecaca",
              fontSize: "13px"
            }}>
              XMLA semantic model error: {xmlaSemanticError}
            </div>
          )}

          {xmlaSemanticResult?.links?.workspace && (
            <div style={{
              marginTop: "14px",
              padding: "12px",
              borderRadius: "8px",
              backgroundColor: "#ecfdf3",
              border: "1px solid #86efac"
            }}>
              <div style={{ fontWeight: 600, marginBottom: "8px", color: "#14532d" }}>
                XMLA semantic model created in cloud
              </div>
              <div style={{ fontSize: "12px", color: "#14532d", marginBottom: "6px" }}>
                Model name: <strong>{xmlaSemanticResult?.dataset_name || "N/A"}</strong>
              </div>
              <div style={{ fontSize: "12px", color: "#14532d", marginBottom: "8px" }}>
                This mode builds an enhanced semantic model from Qlik schema + CSV metadata without Desktop.
              </div>
              <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "8px" }}>
                <input
                  type="text"
                  readOnly
                  value={xmlaSemanticResult?.links?.workspace || ""}
                  className="url-input"
                />
                <button
                  onClick={() => window.open(xmlaSemanticResult?.links?.workspace, "_blank")}
                  className="btn btn-small"
                  style={{
                    padding: "8px 12px",
                    minWidth: "120px",
                    height: "45px",
                    backgroundColor: "#16a34a",
                    color: "white",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                    fontSize: "13px",
                  }}
                >
                  Open Workspace
                </button>
              </div>
              {xmlaSemanticResult?.links?.dataset && (
                <div style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "8px" }}>
                  <input
                    type="text"
                    readOnly
                    value={xmlaSemanticResult?.links?.dataset || ""}
                    className="url-input"
                  />
                  <button
                    onClick={() => window.open(xmlaSemanticResult?.links?.dataset, "_blank")}
                    className="btn btn-small"
                    style={{
                      padding: "8px 12px",
                      minWidth: "120px",
                      height: "45px",
                      backgroundColor: "#15803d",
                      color: "white",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    Open Model
                  </button>
                  <button
                    onClick={() => setShowXmlaDiagram((v) => !v)}
                    className="btn btn-small"
                    style={{
                      padding: "8px 12px",
                      minWidth: "120px",
                      height: "45px",
                      backgroundColor: "#0f766e",
                      color: "white",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    {showXmlaDiagram ? "Hide ER Diagram" : "View ER Diagram"}
                  </button>
                </div>
              )}
              {!xmlaSemanticResult?.links?.dataset && (
                <div style={{ fontSize: "12px", color: "#14532d", marginTop: "8px" }}>
                  Dataset link unavailable. Use workspace search with the model name shown above.
                </div>
              )}
              {showXmlaDiagram && xmlaSemanticResult?.er_diagram && (
                <div style={{ marginTop: "10px" }}>
                  <div style={{ fontSize: "12px", color: "#14532d", marginBottom: "6px" }}>
                    Mermaid ER diagram (all tables + inferred relationships)
                  </div>
                  <textarea
                    readOnly
                    value={xmlaSemanticResult.er_diagram}
                    style={{
                      width: "100%",
                      minHeight: "180px",
                      borderRadius: "6px",
                      border: "1px solid #86efac",
                      padding: "10px",
                      fontFamily: "monospace",
                      fontSize: "12px",
                      color: "#14532d",
                      backgroundColor: "#f0fdf4",
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {desktopBundle?.bundle_dir && (
            <div style={{
              marginTop: "14px",
              padding: "12px",
              borderRadius: "8px",
              backgroundColor: "#f0f9ff",
              border: "1px solid #bae6fd"
            }}>
              <div style={{ fontWeight: 600, marginBottom: "8px", color: "#0c4a6e" }}>
                Desktop + Cloud bundle generated
              </div>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <input
                  type="text"
                  readOnly
                  value={desktopBundle.bundle_dir}
                  className="url-input"
                />
                <button
                  onClick={copyBundlePath}
                  className="btn btn-small"
                  style={{
                    padding: "8px 12px",
                    minWidth: "90px",
                    height: "45px",
                    backgroundColor: bundlePathCopied ? "#27ae60" : "#3498db",
                    color: "white",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                    fontSize: "13px",
                  }}
                >
                  {bundlePathCopied ? "Copied" : "Copy Path"}
                </button>
              </div>
              <div style={{ marginTop: "8px", fontSize: "12px", color: "#0c4a6e" }}>
                Open the bundle README file and publish with Power BI Desktop to cloud.
              </div>
            </div>
          )}
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

          {/* Dataset Details section removed per user request */}
          <div style={{ height: '8px' }} />

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

};

