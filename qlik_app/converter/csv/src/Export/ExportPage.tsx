import "./ExportPage.css";
import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useWizard } from "../context/WizardContext";

export default function ExportPage() {
  const { state } = useLocation() as any;
  const navigate = useNavigate();

  const { getLastElapsed } = useWizard();
  const lastElapsedForPage = getLastElapsed?.("/summary");

  // Prefer friendly appName; fallback to appId or session storage
  const appNameRaw = state?.appName || state?.appId || sessionStorage.getItem("appName") || "Unknown";
  let selectedTable = state?.selectedTable || sessionStorage.getItem("selectedTable");
  let rows = state?.rows || [];

  // try to hydrate rows from storage if not passed
  if ((!rows || !rows.length) && sessionStorage.getItem("selectedRows")) {
    try {
      rows = JSON.parse(sessionStorage.getItem("selectedRows") || "[]");
    } catch (_) {
      rows = [];
    }
  }

  const appName = appNameRaw;

  const [showPowerBIOptions, setShowPowerBIOptions] = useState(false);
  const [options, setOptions] = useState<{ csv: boolean; dax: boolean }>({ csv: true, dax: false });
  const [selectAll, setSelectAll] = useState(false);

  if (!selectedTable) {
    // if the summary step completed previously, send user to Summary to pick a table
    if (sessionStorage.getItem("summaryComplete") === "true") {
      navigate("/summary");
      return null;
    }

    return (
      <div className="export-wrap">
        <p>No export data found.</p>
        <button onClick={() => navigate("/apps")}>Go Back</button>
      </div>
    );
  }

  // CSV EXPORT (REUSED LOGIC)
  const exportCSV = () => {
    if (!rows?.length) return;

    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(","),
      ...rows.map((r: any) =>
        headers.map((h) => `"${r[h] ?? ""}"`).join(",")
      ),
    ].join("\n");

    // Save to sessionStorage for Migration page
    sessionStorage.setItem("migration_csv", csv);
    sessionStorage.setItem("migration_has_csv", "true");
    sessionStorage.setItem("migration_selected_table", selectedTable);
    sessionStorage.setItem("migration_appName", appName);
    sessionStorage.setItem("migration_columns", JSON.stringify(Object.keys(rows[0])));
    sessionStorage.setItem("migration_row_count", String(rows.length));

    // Also download as file
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedTable}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    // Mark export done
    sessionStorage.setItem("exportCSV", "true");
    sessionStorage.setItem("exportComplete", "true");
  };

  // small DAX exporter - writes a lightweight skeleton .dax file containing columns and a sample measure
  const exportDAX = () => {
    if (!rows?.length) return;

    const cols = Object.keys(rows[0]);
    const daxLines = [] as string[];
    daxLines.push(`-- DAX export skeleton for table: ${selectedTable}`);
    daxLines.push(`-- Columns:`);
    cols.forEach((c) => daxLines.push(`-- ${c}`));
    daxLines.push(`\n-- Sample measure`);
    daxLines.push(`[${selectedTable} Count] = COUNTROWS('${selectedTable}')`);

    const daxContent = daxLines.join("\n");

    // Save to sessionStorage for Migration page
    sessionStorage.setItem("migration_dax", daxContent);
    sessionStorage.setItem("migration_has_dax", "true");

    // Also download as file
    const blob = new Blob([daxContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedTable}.dax`;
    a.click();
    URL.revokeObjectURL(url);

    sessionStorage.setItem("exportDAX", "true");
    sessionStorage.setItem("exportComplete", "true");
  };

  return (
    <div className="export-wrap">
      <div className="timerStyle">
      <h2>📤 Export Data</h2>
          <span className="label"></span>
          <span className="value">AnalysisTime  - {lastElapsedForPage || "-"}</span>
        </div>

      {/* 🔹 TOP INFO BOXES */}
      <div className="info-grid">
          <div className="info-box">
  <span className="label">Application</span>
  <span className="value">{appName}</span>
</div>

        <div className="info-box">
          <span className="label">Table Name</span>
          <span className="value">{selectedTable}</span>
        </div>

        <div className="info-box">
          <span className="label">Total Rows</span>
          <span className="value">{rows?.length || 0}</span>
        </div>

        
      </div>

      {/* 🔹 EXPORT OPTIONS */}
      <div className="export-options">
        <div
          className="export-box powerbi"
          onClick={() => setShowPowerBIOptions(!showPowerBIOptions)}
        >
          🔵 Export To PowerBI
        </div>

        <div className="export-box disabled">
          Export to SSRS (Coming Soon)
        </div>
      </div>
      

      {/* 🔹 EXPORT CHECKBOX OPTIONS (inside one box) */}
      {showPowerBIOptions && (
        <div className="powerbi-options">
          <div className="export-box sub">
            <div className="checkbox-row">
              <label>
                <input
                  type="checkbox"
                  checked={selectAll}
                  onChange={() => {
                    const newVal = !selectAll;
                    setSelectAll(newVal);
                    setOptions({ csv: newVal, dax: newVal });
                  }}
                />
                <strong> Select All</strong>
              </label>
            </div>

            <div className="checkbox-row">
              <label>
                <input
                  type="checkbox"
                  checked={options.csv}
                  onChange={() => {
                    const csv = !options.csv;
                    setOptions((s) => ({ ...s, csv }));
                    setSelectAll(csv && options.dax);
                  }}
                />
                📄 Export as CSV
              </label>
            </div>

            <div className="checkbox-row">
              <label>
                <input
                  type="checkbox"
                  checked={options.dax}
                  onChange={() => {
                    const dax = !options.dax;
                    setOptions((s) => ({ ...s, dax }));
                    setSelectAll(options.csv && dax);
                  }}
                />
                📊 Export as DAX (Coming Soon)
              </label>
            </div>

            <div className="actions-row">
              <button
                className="export-btn"
                onClick={() => {
                  // Export selected options
                  if (options.csv) exportCSV();
                  if (options.dax) exportDAX();
                }}
                disabled={!options.csv && !options.dax}
              >
                ✅ Export Selected
              </button>
            </div>
          </div>
        </div>
      )}



              <div className="page-actions">
  <button
    className="continue-btn"
    onClick={() => {
      // Auto-export CSV before moving to migration
      if (rows?.length) {
        exportCSV();
        console.log("✅ CSV exported to sessionStorage");
      }
      
      sessionStorage.setItem("exportComplete", "true");
      // Navigate to migration after a short delay to ensure export is saved
      setTimeout(() => {
        navigate("/migration", { state: { appId: state?.appId, appName } });
      }, 100);
    }}
  >
    ➡️ Continue to Migration
  </button>
</div>
    </div>
  );
}