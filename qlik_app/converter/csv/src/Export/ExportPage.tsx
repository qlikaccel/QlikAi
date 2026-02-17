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
  const appId = state?.appId || sessionStorage.getItem("appSelected");

  const appName = appNameRaw;

  const [options, setOptions] = useState<{ combined: boolean; separate: boolean }>({ combined: false, separate: false });
  const [showError, setShowError] = useState(false);

  // Check if any export option is selected
  const isAnyOptionSelected = options.combined || options.separate;

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
    if (options.combined || options.separate) {
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

    // Save separation flag if separate tables selected
    if (options.separate) {
      sessionStorage.setItem("migration_separate_tables", "true");
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
      if (options.combined || options.separate) {
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

      // Save separation flag if separate tables selected
      if (options.separate) {
        sessionStorage.setItem("migration_separate_tables", "true");
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

        {!isMultiSelect ? (
          <>
            <div className="info-box">
              <span className="label">Table Name</span>
              <span className="value">{selectedTable}</span>
            </div>

            <div className="info-box">
              <span className="label">Total Rows</span>
              <span className="value">{rows?.length || 0}</span>
            </div>

            <div className="info-box">
              <span className="label">Total Columns</span>
              <span className="value">{rows && rows.length > 0 ? Object.keys(rows[0]).length : 0}</span>
            </div>
          </>
        ) : (
          <>
            <div className="info-box">
              <span className="label">Selected Tables</span>
              <span className="value">{selectedTables.length}</span>
            </div>

            <div className="info-box">
              <span className="label">Total Rows</span>
              <span className="value">{selectedTables.reduce((sum, t) => sum + (t.data?.rows?.length || 0), 0)}</span>
            </div>

            <div className="info-box">
              <span className="label">Total Columns</span>
              <span className="value">{selectedTables.length > 0 && selectedTables[0].data?.rows?.length ? Object.keys(selectedTables[0].data.rows[0]).length : 0}</span>
            </div>
          </>
        )}
      </div>

      {/* Display table list for multi-select */}
      {isMultiSelect && (
        <div className="tables-list-container">
          <h3>Selected Tables:</h3>
          <div className="tables-list">
            {selectedTables.map((table, idx) => (
              <div key={idx} className="table-item-chip">
                <span>{table.name}</span>
                <span className="row-count">({table.data?.rows?.length || 0} rows)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 🔹 TABLE STRUCTURE & PREVIEW */}
      <div className="table-structure-section">
        <h3>📊 Table Structure & Data Preview</h3>
        {isMultiSelect ? (
          // Multi-select: Show all tables with their columns
          selectedTables.map((table, tableIdx) => (
            <div key={tableIdx} className="table-structure-card">
              <div className="table-header">
                <h4>{table.name}</h4>
                <span className="row-info">📈 {table.data?.rows?.length || 0} rows</span>
              </div>
              
              {table.data?.rows && table.data.rows.length > 0 && (
                <>
                  <div className="columns-section">
                    <strong>📋 Columns ({Object.keys(table.data.rows[0] || {}).length}):</strong>
                    <div className="columns-list">
                      {Object.keys(table.data.rows[0] || {}).map((col, colIdx) => (
                        <span key={colIdx} className="column-chip">{col}</span>
                      ))}
                    </div>
                  </div>

                  {/* Show sample data */}
                  <div className="sample-data-section">
                    <strong>📝 Sample Data (first 2 rows):</strong>
                    <table className="preview-table">
                      <thead>
                        <tr>
                          {Object.keys(table.data.rows[0] || {}).slice(0, 5).map((col, idx) => (
                            <th key={idx}>{col}</th>
                          ))}
                          {Object.keys(table.data.rows[0] || {}).length > 5 && <th>...</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {table.data.rows.slice(0, 2).map((row, rowIdx) => (
                          <tr key={rowIdx}>
                            {Object.keys(table.data.rows[0] || {}).slice(0, 5).map((col, colIdx) => (
                              <td key={colIdx}>{String(row[col] || '-').substring(0, 30)}</td>
                            ))}
                            {Object.keys(table.data.rows[0] || {}).length > 5 && <td>...</td>}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          ))
        ) : (
          // Single select: Show selected table with columns
          rows && rows.length > 0 && (
            <div className="table-structure-card">
              <div className="table-header">
                <h4>{selectedTable}</h4>
                <span className="row-info">📈 {rows.length} rows</span>
              </div>

              <div className="columns-section">
                <strong>📋 Columns ({Object.keys(rows[0] || {}).length}):</strong>
                <div className="columns-list">
                  {Object.keys(rows[0] || {}).map((col, idx) => (
                    <span key={idx} className="column-chip">{col}</span>
                  ))}
                </div>
              </div>

              {/* Show sample data */}
              <div className="sample-data-section">
                <strong>📝 Sample Data (first 2 rows):</strong>
                <table className="preview-table">
                  <thead>
                    <tr>
                      {Object.keys(rows[0] || {}).slice(0, 5).map((col, idx) => (
                        <th key={idx}>{col}</th>
                      ))}
                      {Object.keys(rows[0] || {}).length > 5 && <th>...</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, 2).map((row, rowIdx) => (
                      <tr key={rowIdx}>
                        {Object.keys(rows[0] || {}).slice(0, 5).map((col, colIdx) => (
                          <td key={colIdx}>{String(row[col] || '-').substring(0, 30)}</td>
                        ))}
                        {Object.keys(rows[0] || {}).length > 5 && <td>...</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        )}
      </div>

      {/* 🔹 HOW COMBINING WORKS */}
      {isMultiSelect && options.combined && (
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
      )}

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
              <strong> 📄 Export as CSV / DAX (Combined) </strong>
            </label>
          </div>

          <div className="checkbox-row">
            <label>
              <input
                type="checkbox"
                checked={options.separate}
                onChange={() => {
                  setOptions({ ...options, separate: !options.separate });
                }}
              />
              <strong> 📊 Export as Separate Tables </strong>
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
              navigate("/publish", { 
                state: { 
                  appId: state?.appId, 
                  appName,
                  exportOptions: options,
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
