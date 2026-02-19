import { useState, useEffect } from "react";
import "./SchemaModal.css";
import { API_ENDPOINTS } from "../../api/config";

interface SchemaModalProps {
  isOpen: boolean;
  onClose: () => void;
  appId?: string;
  masterTable?: string;
  tables?: any[];
}

export default function SchemaModal({
  isOpen,
  onClose,
  appId = "demo",
  masterTable,
  tables = [],
}: SchemaModalProps) {
  const [schemaImage, setSchemaImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const fetchSchema = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          API_ENDPOINTS.schemaBase64(appId),
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              tables: tables,
              master_table: masterTable,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        setSchemaImage(data.image);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load schema diagram"
        );
      } finally {
        setLoading(false);
      }
    };

    fetchSchema();
  }, [isOpen, appId, masterTable, tables]);

  if (!isOpen) return null;

  return (
    <div className="schema-modal-overlay" onClick={onClose}>
      <div className="schema-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="schema-modal-header">
          <h2>Entity Relationship Diagram (ER)</h2>
          <button className="schema-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="schema-modal-body">
          {loading && (
            <div className="schema-loading">
              <div className="schema-spinner"></div>
              <p>Generating ER diagram...</p>
            </div>
          )}

          {error && (
            <div className="schema-error">
              <p>⚠️ {error}</p>
              <button onClick={() => window.location.reload()}>
                Retry
              </button>
            </div>
          )}

          {schemaImage && !loading && (
            <img
              src={`data:image/png;base64,${schemaImage}`}
              alt="ER Diagram"
              className="schema-image"
            />
          )}
        </div>
      </div>
    </div>
  );
}
