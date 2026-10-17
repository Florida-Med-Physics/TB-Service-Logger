@echo off
cd /d "%~dp0"
if exist "dist\TrueBeam Service Log\TrueBeam Service Log.exe" (
 start "" "dist\TrueBeam Service Log\TrueBeam Service Log.exe"
) else (
 py -3 desktop_app.py
)
