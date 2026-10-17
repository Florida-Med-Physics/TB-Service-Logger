"""Verify the package contains exactly the approved HTML, byte for byte."""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
binary=root/'dist-html'/('TrueBeam Service Log/TrueBeam Service Log.exe' if sys.platform=='win32' else 'TrueBeam Service Log.app/Contents/MacOS/TrueBeam Service Log')
with tempfile.TemporaryDirectory() as folder:
    report=Path(folder)/'package-test.json'
    subprocess.run([str(binary),'--self-test-report',str(report)],check=True,timeout=60)
    result=json.loads(report.read_text())
    expected=hashlib.sha256((root/'standalone/TrueBeam-Local.html').read_bytes()).hexdigest()
    assert result['html'] and result['sha256']==expected
    print('PASS: executable contains the exact current HTML design and all embedded assets.',result['platform'],result['bytes'])
