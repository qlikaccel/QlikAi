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

  const [options, setOptions] = useState<{ combined: boolean }>({ combined: false });
  const [showError, setShowError] = useState(false);

  // Check if combined export is selected
  const isAnyOptionSelected = options.combined;

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

    // Save CSV data if combined export is selected
    if (options.combined) {
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

    // Save DAX data if combined export is selected
    if (options.combined) {
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

  // Download functions (removed - combined export only)

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
                checked={options.combined}
                onChange={() => {
                  const combined = !options.combined;
                  setOptions({ combined });
                }}
              />
              <strong> 📄 Export as CSV & DAX (Combined)</strong>
            </label>
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
            ⚠️ Please select CSV & DAX export before continuing
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
              navigate("/publish", { state: { appId: state?.appId, appName } });
            } else {
              setShowError(true);
            }
          }}
          title={!isAnyOptionSelected ? "Select export to continue" : "Publish to PowerBI"}
        >
          {!isAnyOptionSelected ? "⚠️ Select Export Option" : "➡️ Publish to PowerBI"}
        </button>
      </div>
    </div>
  );
}
