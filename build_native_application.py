"""Build a self-contained native application on the target operating system."""
import os, platform, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
assets=ROOT/'build-resources';assets.mkdir(exist_ok=True)
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir',
      '--name','TrueBeam Service Log','--distpath','dist-native','--workpath','build-native',
      '--icon',str(ROOT/'assets'/('truebeam-icon.icns' if sys.platform=='darwin' else 'truebeam-icon.ico')),
      '--add-data',str(ROOT/'assets')+os.pathsep+'assets','--collect-all','pymupdf','--hidden-import','PIL._tkinter_finder']
if sys.platform=='darwin':
    subprocess.run(['swiftc','-target',platform.machine()+'-apple-macos13.0','ocr_macos.swift','-o',str(assets/'ocr_macos')],check=True)
    args+=['--add-binary',str(assets/'ocr_macos')+os.pathsep+'.',
           '--exclude-module','rapidocr_onnxruntime','--exclude-module','onnxruntime',
           '--exclude-module','cv2','--exclude-module','numpy']
elif sys.platform=='win32':
    args+=['--collect-all','rapidocr_onnxruntime','--collect-all','onnxruntime','--collect-all','cv2',
           '--copy-metadata','rapidocr_onnxruntime']
else:raise SystemExit('Build on Windows or macOS.')
args+=['--exclude-module','matplotlib','--exclude-module','pandas','--exclude-module','scipy',
       '--exclude-module','IPython','--exclude-module','pytest','--exclude-module','tkinter','--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtWebEngineWidgets','--exclude-module','PySide6.QtQml','--exclude-module','PySide6.QtQuick','native_application.py']
subprocess.run(args,check=True)
print('Application built in',ROOT/'dist-native')
