"""Exercise the actual packaged binary with no browser/server."""
import json, subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
binary=(root/'dist'/'TrueBeam Service Log'/'TrueBeam Service Log.exe') if sys.platform=='win32' else (root/'dist'/'TrueBeam Service Log.app'/'Contents'/'MacOS'/'TrueBeam Service Log')
with tempfile.TemporaryDirectory() as folder:
    report=Path(folder)/'self-test.json'
    subprocess.run([str(binary),'--self-test-report',str(report)],check=True,timeout=180)
    result=json.loads(report.read_text())
    assert result['pdf'] and result['ocr'] and result['xlsx'],result
    subprocess.run([str(binary),'--smoke-test','--data-dir',str(Path(folder)/'data')],check=True,timeout=60)
    print('Packaged application passed OCR, PDF, XLSX, and native-window launch tests:',result['platform'])
