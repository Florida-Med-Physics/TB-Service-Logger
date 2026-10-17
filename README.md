# TrueBeam Service Log

## Native desktop application — recommended

Windows executable and Mac application with direct PDF/screenshot import and included offline OCR.

Open Folder settings. Choose the service-report and screenshot folders, choose a new Excel filename, and select Save & Monitor. All paths and the monitoring preference persist across relaunches.

Imports and saved edits commit immediately to SQLite. The same Excel report is atomically replaced every 10 minutes. Export Report saves immediately. Keep the app running and close the workbook in Excel to permit replacement.

Service Reports and Fault Reports are separate. Fault Reports has SUGGESTED SOLUTION, OUR SOLUTION, and Initials, with no Status column. Double-click a value to read/edit it, or a filename to open originals. Import details exposes extraction errors and retries.

Read DESKTOP START HERE.txt for installation, persistent data locations, and migration details.

## Build
Install Python 3.12. Run python -m pip install -r requirements-desktop.txt, then python build_desktop.py on the target OS. Output is in dist/. Run python verify_desktop.py to test packaged OCR, PDF, Excel and native-window launch.

The Build Windows application GitHub Actions workflow produces a downloadable Windows ZIP artifact. Source launch: python desktop_app.py, or Launch TrueBeam.command / Launch TrueBeam.bat.

This Mac build targets Apple silicon; Windows targets x64. Packages require no Python, Tesseract, server, or internet. Apps are unsigned; deployment approval on managed computers remains an institutional decision.

## Validation
Run python -m unittest -q test_core.py test_web.py test_desktop.py.
Tests cover ingestion, persistence, edits, links, report schemas, ten-minute replacement, retries, and preservation of the previous file on save failure. Packaged tests exercise bundled PDF and OCR support. No private PDFs, screenshots, settings, or databases are distributed.

## Earlier versions
Standalone HTML and browser-helper versions remain for existing installations. Native apps reuse disk-based SQLite data but do not automatically read browser IndexedDB. Transfer browser-only manual edits before retiring the HTML.
