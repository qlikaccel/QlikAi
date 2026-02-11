import "./ExportPage.css";
import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useWizard } from "../context/WizardContext";

export default function ExportPage() {
  const { state } = useLocation() as any;
  const navigate = useNavigate();

  const { getLastElapsed } = useWizard();
  const [pageLoadTime, setPageLoadTime] = useState<string | null>(null);

  // Capture the elapsed time from navigation (Summary -> Export)
  useEffect(() => {
    const elapsed = getLastElapsed?.();
    if (elapsed) {
      setPageLoadTime(elapsed);
    }
  }, [getLastElapsed]);

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

  const [options, setOptions] = useState<{ csv: boolean; dax: boolean }>({ csv: false, dax: false });
  const [selectAll, setSelectAll] = useState(false);
  const [showError, setShowError] = useState(false);

  // Check if at least one option is selected
  const isAnyOptionSelected = options.csv || options.dax;

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

  // Helper: Save data to sessionStorage (for Continue button)
  const saveDataToSessionStorage = () => {
    if (!rows?.length) return;

    // Always save metadata
    sessionStorage.setItem("migration_selected_table", selectedTable);
    sessionStorage.setItem("migration_appName", appName);
    sessionStorage.setItem("migration_columns", JSON.stringify(Object.keys(rows[0])));
    sessionStorage.setItem("migration_row_count", String(rows.length));

    // Save CSV data if selected
    if (options.csv) {
      const headers = Object.keys(rows[0]);
      const csv = [
        headers.join(","),
        ...rows.map((r: any) =>
          headers.map((h) => `"${r[h] ?? ""}"`).join(",")
        ),
      ].join("\n");
      sessionStorage.setItem("migration_csv", csv);
      sessionStorage.setItem("migration_has_csv", "true");
    }

    // Save DAX data if selected
    if (options.dax) {
      const cols = Object.keys(rows[0]);
      const daxLines = [] as string[];
      daxLines.push(`-- DAX export skeleton for table: ${selectedTable}`);
      daxLines.push(`-- Columns:`);
      cols.forEach((c) => daxLines.push(`-- ${c}`));
      daxLines.push(`\n-- Sample measure`);
      daxLines.push(`[${selectedTable} Count] = COUNTROWS('${selectedTable}')`);
      const daxContent = daxLines.join("\n");
      sessionStorage.setItem("migration_dax", daxContent);
      sessionStorage.setItem("migration_has_dax", "true");
    }

    sessionStorage.setItem("exportComplete", "true");
  };

  // Download CSV file
  const downloadCSV = () => {
    if (!rows?.length) return;

    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(","),
      ...rows.map((r: any) =>
        headers.map((h) => `"${r[h] ?? ""}"`).join(",")
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedTable}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Download DAX file
  const downloadDAX = () => {
    if (!rows?.length) return;

    const cols = Object.keys(rows[0]);
    const daxLines = [] as string[];
    daxLines.push(`-- DAX export skeleton for table: ${selectedTable}`);
    daxLines.push(`-- Columns:`);
    cols.forEach((c) => daxLines.push(`-- ${c}`));
    daxLines.push(`\n-- Sample measure`);
    daxLines.push(`[${selectedTable} Count] = COUNTROWS('${selectedTable}')`);
    const daxContent = daxLines.join("\n");

    const blob = new Blob([daxContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedTable}.dax`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Export Selected: Download files only
  const handleExportSelected = () => {
    if (options.csv) downloadCSV();
    if (options.dax) downloadDAX();
  };

  return (
    <div className="export-wrap">
      {/* 🔹 HEADER WITH TIMER */}
      <div className="header-with-timer">
        <h2>📤 Export Data</h2>
        <span className="analysis-time">Analysis Time: {pageLoadTime || "00s"}</span>
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

      {/* 🔹 TWO-COLUMN EXPORT OPTIONS */}
      <div className="export-options-grid">
        {/* LEFT: PowerBI Export */}
        <div className="export-section">
          <div className="export-header powerbi">
            Export To PowerBI
          </div>

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
              onClick={handleExportSelected}
              disabled={!options.csv && !options.dax}
            >
              ✅ Export Selected
            </button>
          </div>
        </div>

        {/* RIGHT: SSRS Export (Disabled) */}
        <div className="export-section disabled-section">
          <div className="export-header ssrs">
            Export To SSRS
          </div>

          <div className="checkbox-row">
            <label>
              <input type="checkbox" disabled />
              <strong> Select All</strong>
            </label>
          </div>

          <div className="checkbox-row">
            <label>
              <input type="checkbox" disabled />
              📄 Export as CSV
            </label>
          </div>

          <div className="checkbox-row">
            <label>
              <input type="checkbox" disabled />
              📊 Export as DAX
            </label>
          </div>

          <div className="actions-row">
            <button className="export-btn" disabled>
              ✅ Export Selected
            </button>
          </div>
        </div>
      </div>

      {/* 🔹 CONTINUE BUTTON */}
      <div className="page-actions">
        {showError && (
          <div className="error-message">
            ⚠️ Please select CSV or DAX before continuing
          </div>
        )}
        <button
          className="continue-btn"
          disabled={!isAnyOptionSelected}
          onClick={() => {
            if (isAnyOptionSelected) {
              setShowError(false);
              // Save data to sessionStorage before navigating
              saveDataToSessionStorage();
              navigate("/migration", { state: { appId: state?.appId, appName } });
            } else {
              setShowError(true);
            }
          }}
          title={!isAnyOptionSelected ? "Select CSV or DAX to continue" : "Continue to Migration"}
        >
          {!isAnyOptionSelected ? "⚠️ Select Export Option" : "➡️ Continue to Migration"}
        </button>
      </div>
    </div>
  );
}
