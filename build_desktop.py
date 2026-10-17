"""Build a self-contained native application on the target operating system."""
import os, platform, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
assets=ROOT/'build-resources';assets.mkdir(exist_ok=True)
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir',
      '--name','TrueBeam Service Log','--collect-all','pymupdf','--hidden-import','PIL._tkinter_finder']
if sys.platform=='darwin':
    subprocess.run(['swiftc','ocr_macos.swift','-o',str(assets/'ocr_macos')],check=True)
    args+=['--add-binary',str(assets/'ocr_macos')+os.pathsep+'.',
           '--exclude-module','rapidocr_onnxruntime','--exclude-module','onnxruntime',
           '--exclude-module','cv2','--exclude-module','numpy']
elif sys.platform=='win32':
    args+=['--collect-all','rapidocr_onnxruntime','--collect-all','onnxruntime','--collect-all','cv2',
           '--copy-metadata','rapidocr_onnxruntime']
else:raise SystemExit('Build on Windows or macOS.')
args+=['--exclude-module','matplotlib','--exclude-module','pandas','--exclude-module','scipy',
       '--exclude-module','IPython','--exclude-module','pytest','desktop_app.py']
subprocess.run(args,check=True)
print('Application built in',ROOT/'dist')
