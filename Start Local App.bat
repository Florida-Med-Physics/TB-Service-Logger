@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
  if errorlevel 1 (
    echo Python 3.10 or later is required. Ask IT to install a supported Python version.
    pause
    exit /b 1
  )
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Python 3.10 or later is required. Ask IT to install Python with pip and Tk support.
    pause
    exit /b 1
  )
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency setup failed. See START HERE.txt for offline installation.
    pause
    exit /b 1
  )
)
.venv\Scripts\python.exe web_app.py
pause
