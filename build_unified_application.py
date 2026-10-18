"""Build, smoke-test, and archive apps using the EMBRACE packaging pattern."""
import os, platform, shutil, subprocess, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
assets=ROOT/'build-resources';assets.mkdir(exist_ok=True)
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onefile' if sys.platform=='win32' else '--onedir',
      '--name','TrueBeam Service Log','--distpath','dist-unified','--workpath','build-unified','--specpath','build-unified',
      '--icon',str(ROOT/'assets'/('truebeam-icon.icns' if sys.platform=='darwin' else 'truebeam-icon.ico')),
      '--add-data',str(ROOT/'assets')+os.pathsep+'assets',
      '--add-data',str(ROOT/'standalone'/'TrueBeam-Local.html')+os.pathsep+'standalone',
      '--add-data',str(ROOT/'standalone'/'ui-manifest.json')+os.pathsep+'standalone','--collect-all','pymupdf']
if sys.platform=='darwin':
    args+=['--osx-bundle-identifier','org.floridamedphysics.truebeam-service-log']
    subprocess.run(['swiftc','-target',platform.machine()+'-apple-macos13.0','ocr_macos.swift','-o',str(assets/'ocr_macos')],check=True)
    args+=['--add-binary',str(assets/'ocr_macos')+os.pathsep+'.',
           '--exclude-module','rapidocr_onnxruntime','--exclude-module','onnxruntime',
           '--exclude-module','cv2','--exclude-module','numpy']
elif sys.platform=='win32':
    args+=['--collect-all','rapidocr_onnxruntime','--collect-all','onnxruntime','--collect-all','cv2',
           '--copy-metadata','rapidocr_onnxruntime']
else:raise SystemExit('Build on Windows or macOS.')
args+=['--exclude-module','matplotlib','--exclude-module','pandas','--exclude-module','scipy',
       '--exclude-module','IPython','--exclude-module','pytest','--exclude-module','tkinter','unified_application.py']
subprocess.run(args,check=True)
subprocess.run([sys.executable,str(ROOT/'verify_unified_application.py')],check=True)
if sys.platform=='win32':
    executable=ROOT/'dist-unified'/'TrueBeam Service Log.exe'
    archive=ROOT/'dist-unified'/'TrueBeam-Service-Log-Windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:bundle.write(executable,executable.name)
else:
    archive=ROOT/'dist-unified'/('TrueBeam-Service-Log-macOS-'+platform.machine()+'.zip')
    archive.unlink(missing_ok=True)
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(ROOT/'dist-unified'/'TrueBeam Service Log.app'),str(archive)],check=True)
print('Ready:',archive)
