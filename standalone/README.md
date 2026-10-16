# Open directly from a local HTML file

Double-click **TrueBeam-Local.html** and open it with Microsoft Edge or Google Chrome.
This is the standalone application. It needs no Python, Tesseract installation, launcher,
local server, internet connection, or other files.

1. Use **Browse** to select the service-report folder and the screenshot folder.
2. Grant the browser read access to each folder.
3. Click **Start monitoring**.
4. Use the **Service Reports** and **Fault Reports** tabs.
5. Save a JSON copy with **Back up database**. **Restore database** loads that copy.

The default status is **Closure documented**. A separate **Reviewed** status is available.
The dark-mode switch remembers its setting.

## Storage and monitoring

The database is stored in IndexedDB in the browser profile. Keep the HTML in the same place
and use the same normal browser profile to return to the same database. Reconnect folder
permissions when the browser requests them. Clearing browser storage or removing that
profile can remove the database; portable JSON backups can restore it.

Monitoring runs every five seconds while this page is open. Background tabs may be
throttled by the browser. It stops when the page closes. Reopen the HTML, reconnect folders
if prompted, and start monitoring again. Source files are read only and never uploaded.

Folder access requires the File System Access API in a current desktop Edge or Chrome.
Institutional browser policy can restrict folder access, browser storage, workers, or
WebAssembly. This build was verified in Chrome on Mac; confirm these permissions on the
UFHPT Windows computer.

## Files and extraction

Supported: PDF, DOCX, TXT, PNG, JPEG, BMP and WebP.
PDF text extraction, scanned-page OCR, screenshot OCR and English language data are embedded.
Generated Excel files are ignored to prevent importing the log into itself.
**Export CSV** exports the selected tab; the JSON backup preserves both tabs and source records.
CSV is not a complete database backup.

Fault screenshots use the tooltip/dialog and the fault-list region in the supplied
dual-monitor TrueBeam layout. Different layouts may need adjustments.
PMP checklists and parameter sheets appear as attachment documents.
Unknown fields remain blank; import failures remain visible in the details and filters.

Identical files and faults with identical explicit timestamps can share an entry.
Different times stay separate. Link confirmed duplicates manually, keeping their source files.
Manual links have no undo control in this version.

Backup files do not embed the original reports or screenshots, or operating-system folder
permissions. After restoring, reconnect the original folders and scan to restore source links.

## Development

The generated HTML is the deliverable. browser-runtime.js contains the standalone application
logic. build_standalone.py embeds that code, the shared interface, PDF.js, Tesseract.js,
Tesseract's self-contained WebAssembly engine, and the English OCR model.

To rebuild, provide installed tesseract.js 7.0.0 and pdfjs-dist packages and the public
tessdata_fast/eng.traineddata model:

python standalone/build_standalone.py --node-modules PATH_TO_NODE_MODULES --english PATH_TO_ENG_TRAINEDDATA

The generated file includes open-source license information.
The optional Python/server implementation remains available separately in the repository.


Folder settings open in a pop-up, with separate rows for service reports and screenshots. Use Done to return to the tables. Click a column heading or use Sort by to arrange entries, including start/release date, category, and work hours. Each tab remembers its sort preference. Download fault table and Download service table save Excel-compatible CSV files containing the current filtered rows in the displayed order. The appearance uses the UFHPTI Physics Scheduler logo, navy, and orange branding; dark mode remains available.

Fault Reports show Error Details, SUGGESTED SOLUTION (the suggestions extracted from the source), and Worker Initials (a short editable initials field, e.g. BK; work performed is saved separately). These columns are included in downloads. Existing saved work is retained.


## Automatic Excel workbook
Open Folder settings and choose Choose Export Report. Choose a dedicated .xlsx output file; its contents will be replaced by the app's database, rather than imported or merged. The supplied reference workbook is a styling reference and is not bundled with the app.
The output contains Service Reports and Fault Reports, including all entries regardless of search filters. Service Reports uses the reference column order, widths, Arial text, blue headers, wrapped text, and frozen header row. Fault Reports includes Error Details, Solution, and Worker Initials. Machine is omitted from fault reports.
Updates save automatically within about two seconds after imports, edits, duplicate linking, or database restoration. Keep the local HTML open in desktop Edge or Chrome. On reopening, use Reconnect Export Report if browser write permission needs renewal. Close the workbook in Excel to release file locks. Save failures appear beside Folder settings and retry every ten seconds; database entries remain saved. Changes made directly in the Excel output do not flow back to the database and will be replaced on the next save.

The top Export Report button saves the connected Excel workbook immediately. It also saves after changes and re-saves every hour while the page is open; background browser throttling or computer sleep may delay that save. Backup and restore controls have been removed. Fault Reports omit the Machine column.

Tables fit the available width without lateral scrolling. On narrow screens entries use a stacked layout. Edit short fields directly; click a description preview to read and edit the full text in a pop-up. Changes save when leaving a field. Fault Reports has individual Screenshot links for each original source; service reports have source report links. Reconnect source folders and scan if browser source access needs renewal. The separate Review button has been removed.
