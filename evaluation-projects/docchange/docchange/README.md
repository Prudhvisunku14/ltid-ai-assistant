# Document Change Monitoring System

Compares two versions of a document, summarises the differences, flags changes that may affect software
requirements, shows the evidence (source file, section, line numbers, before/after text) and keeps a reviewable history.

**Verified vs interpreted** - every result carries two clearly separated layers:
* **VERIFIED FACT (green)** - computed by exact text comparison (`monitor/differ.py`): what changed, where, before/after text, line numbers.
* **AI INTERPRETATION (purple, unverified)** - advisory requirement-impact analysis (`monitor/analyzer.py`): severity,
  categories, reasons. Currently rule-based heuristics (modal verbs shall/should, numeric thresholds, deprecations,
  endpoint paths, requirement IDs). Replace `analyze_change` with an LLM call if desired; keep the label.

## Run
```
python3 run.py                      # http://127.0.0.1:8000, uses ./drive_snapshot (real LTID Drive documents)
DRIVE_SOURCE=mock python3 run.py    # synthetic Meridian Logistics test set in ./mock_drive
python3 -m monitor.cli list|compare <doc> <vOld> <vNew>|scan
python3 -m unittest discover -s tests -v     # 23 automated tests
```
No third-party packages needed. Use "Scan all documents" in the UI to populate history.

## Data used (from the shared LTID competition Drive folder)
Documents were read through the Google Drive connector with **read-only calls only** (search/list + read content) and
captured verbatim into `drive_snapshot/` (provenance, Drive file IDs and REAL/MOCK flags in `drive_snapshot/MANIFEST.json`).
Nothing in Drive was created, modified, moved or trashed.
* **REAL version pair:** `Policy_Expense_v1_Superseded.txt` -> `Policy_Expense_v2_Current.txt` (30 -> 10 day claim window, hotel cap JPY 12,000 -> 15,000, new receipt/approval rules).
* **REAL single-version documents** (Leave, Helpdesk spec, Deployment guide, Scenario 01/02/03 requirements, Project Context): listed on the dashboard but cannot be compared (only one version exists in Drive).
* **MOCK test revisions** (invented by us, NOT in Drive, flagged `MOCK` in the UI): `02_Weather_Requirements_v2_MOCK.md`, `03_RAG_Requirements_v2_MOCK.md`, plus the separate `mock_drive/` set.
* Native Drive revision history could not be listed with the connector tools available, so versions are discovered from file names. The live adapter (`GoogleDriveSource`) does read native revisions.
* The snapshot is a point-in-time copy (2026-11-10); re-capture or use `DRIVE_SOURCE=gdrive` for live data. .docx files were captured as the connector's text rendition (tables/images/comments not included; one footer line omitted).

## Google Drive
See `docs/GOOGLE_DRIVE_INTEGRATION.md` (methods compared, recommendation: service account + `drive.readonly`).
`DRIVE_SOURCE=gdrive` switches from the mock folder to the real folder. **The live-Drive path was NOT exercised
against the real competition folder** (no network/credentials in the build sandbox); it is unit-tested against a fake
Drive service (version grouping, read-only scope, absence of write calls).

## Safety
Source access is read-only (`drive.readonly`; tests assert no create/update/delete calls and that mock files are byte-identical after a full scan + API run). History is stored only in the app's own `history.db`.

## Layout
`monitor/` differ, analyzer, sources (local + Drive), store (SQLite), service, server (stdlib HTTP + JSON API), static/index.html (dashboard) ·
`mock_drive/` fictional "Meridian Logistics" documents with versions (SRS v1-v3, Security Policy, Data Retention Policy, Partner API Spec) ·
`tests/` · `docs/`

## Limitations
Text/Markdown/Google-Docs-text/.docx (paragraph text) only; tables, images and comments are ignored. Heuristic analysis can miss or over-flag - always check the evidence.
