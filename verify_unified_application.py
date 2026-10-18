import json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
exe=root/'dist-unified'/('TrueBeam Service Log.app/Contents/MacOS/TrueBeam Service Log' if sys.platform=='darwin' else 'TrueBeam Service Log.exe')
with tempfile.TemporaryDirectory() as directory:
    report=Path(directory)/'interface-check.json'
    subprocess.run([str(exe),'--self-test-report',str(report)],check=True,timeout=240,env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QTWEBENGINE_CHROMIUM_FLAGS='--disable-gpu'))
    result=json.loads(report.read_text());manifest=json.loads((root/'standalone'/'ui-manifest.json').read_text())
    assert result['ready'] and result['desktop_window'] and result['ui']==manifest['ui_sha256'] and result['html_sha256']==manifest['html_sha256']
    print('PASS: desktop app rendered the identical downloadable HTML interface:',result['ui'])
