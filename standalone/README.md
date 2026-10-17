# TrueBeam local HTML

Open TrueBeam-Local.html in desktop Chrome or Microsoft Edge. The existing HTML layout is retained; no executable, Python, or server is required. PDF parsing and screenshot OCR assets are embedded for offline use.

## Import files
Folder settings opens the two source-folder rows and the Excel output connection.
Choose the service-report and screenshot folders and Start monitoring. Folder handles are remembered by this browser; reconnect permissions when prompted. The initial scan checks existing files twice so they can appear immediately after settling.

If the computer restricts folder access, use Import files to choose PDFs and PNGs with the standard file chooser. These originals are copied into browser storage and can be reopened after a reload without folder permission. Selected files are snapshots; use folders for automatic new-file detection, or import selected files again when they change.

PNG decoding snapshots file bytes and falls back to the browser image decoder. Source links use explicit PDF/image MIME types. Import details lists exact extraction errors, opens originals, and retries problem files. Unreadable documents remain available for manual entry. A timeout prevents one blocked extraction from waiting forever. If institutional browser policy blocks OCR/worker execution, Import details reports the problem; the app cannot change that policy.

## Therapist fault entry
Add fault opens a form with event date/time, therapist initials, error code and name if known, Error Details, OUR SOLUTION if fixed, notes, and optional screenshots. Description, initials, and event time are required. The entry is saved immediately to the local database, appears in Fault Reports, remains editable, and is included in CSV and Excel reports. Screenshot attachments are retained in browser storage.

Fault Reports has SUGGESTED SOLUTION, OUR SOLUTION, Worker Initials, and Screenshot links. It has no Status or Machine column. Click plain-text values to edit; click longer descriptions for the full-text pop-up. Empty cells show a hyphen. Tables fit the page width and extend down the page.

## Excel
In Folder settings, choose Export Report and select a dedicated .xlsx output file. Its contents are replaced by both complete tables from the database. It saves after changes and re-saves every 10 minutes while the page is open. Background throttling, computer sleep, lost write permissions, or an Excel file lock may delay saving; failures are shown and retried. Keep the workbook closed in Excel. Export Report saves immediately. Editing the Excel output does not update the database.

## Storage and validation
Use the same HTML location and browser profile to retain browser data and remembered paths. Browser storage can be cleared by browser settings or organizational policy. Source folders and user documents are never uploaded or modified.

Tested from a local file URL with networking disabled: eight screenshot examples and their error codes, actual PDF import, direct-file import and source reopening, corrupt-PDF diagnostics, fallback image decoding, therapist entries with/without screenshots, persistence, edits, duplicate grouping, exports, and layout.
