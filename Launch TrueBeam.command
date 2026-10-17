#!/bin/zsh
cd -- "$(dirname "$0")"
if [[ -x "dist/TrueBeam Service Log.app/Contents/MacOS/TrueBeam Service Log" ]]; then
  open "dist/TrueBeam Service Log.app"
elif [[ -x .venv/bin/python ]]; then
  .venv/bin/python desktop_app.py
else
  python3 desktop_app.py
fi
