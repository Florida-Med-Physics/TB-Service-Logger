# TrueBeam Service Log — local HTML app

A browser interface with a persistent local SQLite database and two tabs:

- **Service Reports:** work-order and PMP documents, service dates, work performed, parts, engineer and hours.
- **Fault Reports:** screenshot fault codes, descriptions, timestamps, severity, impact and linked originals.

Select two source folders. The local helper checks them every three seconds while running.
Search records, review/edit extracted fields, link confirmed duplicates, export Excel, and download database backups.
No application data is uploaded. The browser interface has no CDN, external font, analytics, or cloud API.

## Run on Windows

Extract the whole package, read **START HERE.txt**, then double-click **Start Local App.bat**.
Python 3.10+ is required. First launch installs the Python dependencies.
Screenshot/scanned-PDF OCR requires Tesseract, available on PATH, in its usual Program Files installation,
in a local ocr subfolder, or through TESSERACT_CMD.
After setup, normal use can run without an internet connection.
Offline installation steps for IT are included in START HERE.txt.

The HTML requires the included local Python helper for monitoring and OCR.
It is not a single-file, double-click HTML deployment or a standalone Windows executable.

## Run on Mac

Double-click **Start Local App.command**. Screenshot OCR uses Apple Vision through Swift
and requires Apple Command Line Tools.

## Data

The default Windows data directory is %LOCALAPPDATA%/.truebeam-service-log;
Mac uses ~/.truebeam-service-log. Folder settings and the Excel export live beside the database.
The browser shows the database path. A consistent backup is available through Back up database.
Use a local disk for SQLite and institutionally backed-up storage for copies.
Close the previous desktop app before sharing its data directory.

Source folders are read recursively. Supported files: PDF, DOCX, TXT, PNG, JPEG, TIFF, BMP.
Generated Excel logs are deliberately ignored to avoid feeding them back into the database.
PMP documents are shown as attachment records, separately from work orders.
No sample reports, patient screenshots, or database records are included in the distribution.

Matching screenshot codes and explicit event timestamps can share an event with several sources.
Different event times remain separate. Confirm duplicates before manually linking; sources are retained.
Manual linking has no undo control in this version.

## Validation

Run `python -m unittest -v test_core.py test_web.py`.

The local database/web tests cover persistence, new-file detection, paused scans, review edits,
duplicate grouping, source access, backup consistency, workbook export and local session checks.
Browser smoke tests exercised both tabs, review editing, search and backup downloading in Chrome on Mac.
Service parsing was checked against the 38 supplied work-order PDFs and 15 PMP attachments.
Windows launch and OCR integration still require validation on the target computer.
