# TrueBeam Service Log

[Download HTML, Mac, or Windows](https://github.com/Florida-Med-Physics/TB-Service-Logger/releases/latest).

All three versions use the **same HTML interface file**, including Service Reports, Fault Reports, dark mode, sorting, editable fields, screenshot links, therapist entries, filename timestamps, and import filtering.

- **Windows:** Run TrueBeam-Service-Log-Windows.exe. It is a single executable with the UF Proton icon and opens in its own application window.
- **Mac (Apple Silicon):** Extract the macOS-arm64 ZIP and open TrueBeam Service Log.app.
- **HTML:** Download TrueBeam-Local.html and open it in desktop Chrome or Edge. PDF and OCR assets are embedded for offline use.

The Mac and Windows applications display the HTML inside their dedicated application windows. A separate browser tab is not used. Both packages embed the exact downloadable HTML; UI and file hashes are recorded in ui-manifest.json and checked during build tests.

## Data and folders

Desktop applications retain the shared UFHPTI database and preset U:/W: folder locations. Keep the hosting Windows application running for other clients. Without a shared folder selected, an app opens a local workspace. Folder locations remain saved.

The standalone HTML uses its browser profile's local database and browser-granted folder handles. Browser storage is separate from the desktop/shared database. Monitoring requires keeping the interface open. In HTML mode, Excel snapshot saving can be delayed if Excel locks the output file; desktop mode publishes shared report data feeds without replacing the open workbook.

## Development

Install requirements-unified.txt. Run unified_application.py --local for a desktop window, or open standalone/TrueBeam-Local.html in Chrome or Edge.

standalone/build_standalone.py builds the common interface. It reuses the PDF/OCR assets already embedded in the HTML, so rebuilding does not require network downloads.

build_unified_application.py builds, launches a packaged UI smoke test, and archives the app using the EMBRACE packaging pattern: one Windows executable and one Mac application bundle.

Older launchers are retained in source for reference only. Use the latest release downloads.
