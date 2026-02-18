import "./ExportPage.css";
import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useWizard } from "../context/WizardContext";

interface SelectedTableData {
  name: string;
  rows: any[];
  summary: any;
}

interface SelectedTable {
  name: string;
  data: SelectedTableData;
}

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

  // Check if this is multi-select or single-select mode
  const isMultiSelect = state?.selectedTables && state?.selectedTables.length > 0;
  
  // Prefer friendly appName; fallback to appId or session storage
  const appNameRaw = state?.appName || state?.appId || sessionStorage.getItem("appName") || "Unknown";
  
  // Single select variables
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

  // Multi-select variables
  const selectedTables: SelectedTable[] = state?.selectedTables || [];

  const appName = appNameRaw;

  const [options, setOptions] = useState<{ combined: boolean }>({ combined: false });
  const [showError, setShowError] = useState(false);

  // Check if any export option is selected (only combined remains)
  const isAnyOptionSelected = options.combined;

  // 🔹 SAVE METADATA IMMEDIATELY ON LOAD
  useEffect(() => {
    if (!isMultiSelect && rows && rows.length > 0) {
      // Single-select: Save metadata immediately
      sessionStorage.setItem("migration_selected_table", selectedTable || "");
      sessionStorage.setItem("migration_appName", appName);
      sessionStorage.setItem("migration_columns", JSON.stringify(Object.keys(rows[0])));
      sessionStorage.setItem("migration_row_count", String(rows.length));
    } else if (isMultiSelect && selectedTables.length > 0) {
      // Multi-select: Save metadata immediately
      sessionStorage.setItem("migration_selected_tables", JSON.stringify(selectedTables));
      sessionStorage.setItem("migration_appName", appName);
      sessionStorage.setItem("migration_table_count", String(selectedTables.length));
      
      // Save first table's columns and row count for display on Publish page
      if (selectedTables[0]?.data?.rows && selectedTables[0].data.rows.length > 0) {
        sessionStorage.setItem("migration_columns", JSON.stringify(Object.keys(selectedTables[0].data.rows[0])));
        sessionStorage.setItem("migration_row_count", String(selectedTables[0].data.rows.length));
      }
    }
  }, [selectedTable, rows, selectedTables, appName, isMultiSelect]);

  // Validation: check if we have data
  if (!isMultiSelect && !selectedTable) {
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

  if (isMultiSelect && selectedTables.length === 0) {
    return (
      <div className="export-wrap">
        <p>No tables selected for export.</p>
        <button onClick={() => navigate("/summary")}>Go Back</button>
      </div>
    );
  }

  // Helper: Save data to sessionStorage (for Continue button) - Single Select
  const saveDataToSessionStorageSingle = () => {
    if (!rows?.length) return;

    // Always save metadata
    sessionStorage.setItem("migration_selected_table", selectedTable);
    sessionStorage.setItem("migration_appName", appName);
    sessionStorage.setItem("migration_columns", JSON.stringify(Object.keys(rows[0])));
    sessionStorage.setItem("migration_row_count", String(rows.length));

    // Save CSV data if export is selected
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

  // Helper: Save data to sessionStorage (for Continue button) - Multi Select
  const saveDataToSessionStorageMulti = () => {
    try {
      // Save all selected tables data
      sessionStorage.setItem("migration_selected_tables", JSON.stringify(selectedTables));
      sessionStorage.setItem("migration_appName", appName);
      sessionStorage.setItem("migration_table_count", String(selectedTables.length));

      // Save CSV data if export is selected
      if (options.combined) {
        selectedTables.forEach((table, idx) => {
          const tableRows = table.data?.rows || [];
          if (tableRows.length > 0) {
            const headers = Object.keys(tableRows[0]);
            const csv = [
              headers.join(","),
              ...tableRows.map((r: any) =>
                headers.map((h) => `"${r[h] ?? ""}"`).join(",")
              ),
            ].join("\n");
            sessionStorage.setItem(`migration_csv_${idx}`, csv);
          }
        });

        sessionStorage.setItem("migration_has_csv", "true");
        sessionStorage.setItem("migration_has_dax", "true");
      }



      sessionStorage.setItem("exportComplete", "true");
    } catch (e) {
      console.error("Error saving to sessionStorage:", e);
    }
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

        {/* Always show master table details. When multiple tables are provided, the first table is treated as the master */}
        <>
          <div className="info-box">
            <span className="label">Table Name</span>
            <span className="value">{isMultiSelect ? (selectedTables[0]?.name || "") : selectedTable}</span>
          </div>

          <div className="info-box">
            <span className="label">Total Rows</span>
            <span className="value">{isMultiSelect ? (selectedTables[0]?.data?.rows?.length || 0) : (rows?.length || 0)}</span>
          </div>

          <div className="info-box">
            <span className="label">Total Columns</span>
            <span className="value">{isMultiSelect ? (selectedTables[0]?.data?.rows?.length ? Object.keys(selectedTables[0].data.rows[0]).length : 0) : (rows && rows.length > 0 ? Object.keys(rows[0]).length : 0)}</span>
          </div>
        </>
      </div>





      {/* 🔹 HOW COMBINING WORKS */}
      {/* {isMultiSelect && options.combined && (
        <div className="combining-info-section">
          <h3>🔄 How Tables Will Be Combined</h3>
          <div className="info-card">
            <p>✅ <strong>Step 1:</strong> The first table <strong>"{selectedTables[0]?.name}"</strong> will be used as the primary dataset ({selectedTables[0]?.data?.rows?.length || 0} rows)</p>
            <p>✅ <strong>Step 2:</strong> All {selectedTables.length} tables will be published as <strong>ONE</strong> dataset with a timestamp name</p>
            <p>✅ <strong>Step 3:</strong> The dataset will include:</p>
            <ul>
              <li>📄 CSV format with all data from the primary table</li>
              <li>🔧 DAX metadata describing all selected tables and their structure</li>
            </ul>
            <p style={{ marginTop: '12px', fontSize: '12px', color: '#666' }}>
              💡 All selected tables: {selectedTables.map(t => t.name).join(", ")}
            </p>
          </div>
        </div>
      )} */}

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
                  setOptions({ ...options, combined: !options.combined });
                }}
              />
              <strong> 📄 Export as CSV / DAX </strong>
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
            ⚠️ Please select an export option to continue
          </div>
        )}
        <button
          className="continue-btn"
          disabled={!isAnyOptionSelected}
          onClick={() => {
            if (isAnyOptionSelected) {
                setShowError(false);
                // Save data to sessionStorage before navigating
                if (isMultiSelect) {
                  saveDataToSessionStorageMulti();
                } else {
                  saveDataToSessionStorageSingle();
                }

                // When multiple tables are provided, we want the publish step to process all related tables.
                const exportOptions = { combined: options.combined, separate: isMultiSelect };

                navigate("/publish", { 
                  state: { 
                    appId: state?.appId, 
                    appName,
                    exportOptions,
                    selectedTables: isMultiSelect ? selectedTables : null
                  } 
                });
              } else {
                setShowError(true);
              }
          }}
          title={!isAnyOptionSelected ? "Select an export option to continue" : "Publish to PowerBI"}
        >
          {isAnyOptionSelected ? "✅ Publish to PowerBI" : "⚠️ Select Export Option"}
        </button>
      </div>
    </div>
  );
}
