import json,os,subprocess,sys,tempfile,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
exe=root/'dist-native'/('TrueBeam Service Log.app/Contents/MacOS/TrueBeam Service Log' if sys.platform=='darwin' else 'TrueBeam Service Log.exe')
with tempfile.TemporaryDirectory() as directory:
    report=Path(directory)/'native-check.json'
    subprocess.run([str(exe),'--self-test-report',str(report)],check=True,timeout=120,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'))
    result=json.loads(report.read_text())
    assert not {'tkinter','_tkinter'}.intersection(result.get('loaded_ui_modules',[]))
    assert 'PySide6.QtWidgets' in result.get('loaded_ui_modules',[])
    assert result['native'] and result['browser'] is False and result['icon'] and result['tabs']==2
    print('PASS: packaged native desktop interface, both report tabs, UF Proton icon, no browser.')
