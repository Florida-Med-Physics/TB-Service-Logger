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
