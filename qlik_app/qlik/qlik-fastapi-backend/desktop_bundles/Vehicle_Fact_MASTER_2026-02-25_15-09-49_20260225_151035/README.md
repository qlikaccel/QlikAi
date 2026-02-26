# Desktop + Cloud Publish Bundle

Generated: 2026-02-25T15:10:35.267108
Dataset name: Vehicle_Fact_MASTER_2026-02-25_15-09-49
Target workspace: 7219790d-ee43-4137-b293-e3c477a754f0

## Files
- `tables_schema.json`: table/field metadata extracted from Qlik
- `relationships_normalized.json`: inferred normalized relationships
- `er_diagram.mmd`: Mermaid ER diagram

## Publish steps
1. Open Power BI Desktop (latest version).
2. Build/import your data model using this schema.
3. Apply relationships from `relationships_normalized.json`.
4. Save PBIX and click Publish.
5. Publish to workspace `7219790d-ee43-4137-b293-e3c477a754f0`.
6. In Power BI Service, open the semantic model and Model view.

## Why this mode
This mode is for semantic models that must be fully editable in service.
Push datasets created by REST API can limit "Open semantic model".
