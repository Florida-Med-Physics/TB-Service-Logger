"""Package the identical standalone HTML as a Mac app or Windows executable."""
from pathlib import Path
import os, subprocess, sys
root=Path(__file__).resolve().parent
os.chdir(root)
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir',
      '--name','TrueBeam Service Log','--distpath','dist-html','--workpath','build-html',
      '--add-data',str(root/'standalone'/'TrueBeam-Local.html')+os.pathsep+'standalone']
for name in ['tkinter','numpy','pandas','scipy','PIL','matplotlib','IPython','pymupdf','onnxruntime','cv2','rapidocr_onnxruntime']:
    args+=['--exclude-module',name]
args+=['html_application.py']
subprocess.run(args,check=True)
print('HTML application built in dist-html.')
