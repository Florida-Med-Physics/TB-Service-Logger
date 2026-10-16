# TrueBeam Service Log

## Standalone local HTML — recommended

Download **[standalone/TrueBeam-Local.html](standalone/TrueBeam-Local.html)** as a file and
double-click it in Microsoft Edge or Google Chrome.

It runs directly from a file URL with no Python, no installed OCR engine, no local server,
and no internet connection. PDF parsing, screenshot OCR and English language data are embedded.

Select the service-report and screenshot folders with Browse, grant read access, and start
monitoring. The app keeps its database in the browser and provides two tabs:

- **Service Reports:** work orders and PMP attachments, service dates, work performed,
  parts, engineer and hours.
- **Fault Reports:** error codes, fault descriptions, timestamps, severity, impact and
  linked original screenshots.

The default status is **Closure documented**. Dark mode can be turned on or off and is saved.
Search, edit entries, link confirmed duplicates, export a tab as CSV, and back up or restore
the complete database as JSON.

Keep the HTML at the same location and use the same browser profile. Monitoring runs while
the page is open. Save regular JSON backups; browser storage is not the source folder.
Original files are never modified or uploaded.

See **[standalone/README.md](standalone/README.md)** for details and limitations.

## Optional Python/server version

The older helper-based version is still available for deployments that prefer a local SQLite
database and an Excel export. It is separate from the standalone HTML and is not needed to
use it.

Extract the repository and run **Start Local App.bat** on Windows or **Start Local App.command**
on Mac. Python 3.10+ is required. Windows screenshot OCR additionally requires Tesseract.
Read **START HERE.txt** for setup and offline installation instructions.

## Validation

The Python version has 20 tests:
`python -m unittest -v test_core.py test_web.py`

The standalone HTML was tested from a file URL with networking disabled, including:
native browser file-system handles, new-file monitoring, persistent database records, edits,
duplicates, backups, restore, source reconnection, and dark mode.
The 38 supplied work orders parsed with their key fields, and all eight screenshot examples
produced the expected primary error codes. Additional 100000 codes were retained where shown.

Windows/browser-policy validation is still required on the target UFHPT computer.
