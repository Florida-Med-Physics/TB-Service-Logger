"""Launch the approved HTML interface unchanged; no native replacement UI or network listener."""
import argparse, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
import webbrowser
APP_NAME='TrueBeam Service Log'
def app_home():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'Library'/'Application Support') if sys.platform=='darwin' else str(Path.home())))/APP_NAME
def html_resource():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    return root/'standalone'/'TrueBeam-Local.html'
def install_html():
    source=html_resource()
    home=app_home();home.mkdir(parents=True,exist_ok=True)
    target=home/'TrueBeam-Local.html'
    content=source.read_bytes()
    if not target.exists() or hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(content).digest():
        fd,temp=tempfile.mkstemp(suffix='.html',dir=home)
        try:
            with os.fdopen(fd,'wb') as f:f.write(content)
            os.replace(temp,target)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    return target
def launch(path):
    url=path.as_uri()
    if sys.platform=='darwin':
        for browser in ('Google Chrome','Microsoft Edge'):
            check=subprocess.run(['open','-Ra',browser],capture_output=True)
            if check.returncode==0:
                subprocess.run(['open','-a',browser,url],check=True);return
        raise RuntimeError('Install Google Chrome or Microsoft Edge to run the local HTML app.')
    if sys.platform=='win32':
        roots=[os.environ.get('PROGRAMFILES',''),os.environ.get('PROGRAMFILES(X86)',''),os.environ.get('LOCALAPPDATA','')]
        browsers=[]
        # Prefer the user's default supported browser so the existing browser database is retained.
        default=''
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice') as key:
                default=winreg.QueryValueEx(key,'ProgId')[0].lower()
        except OSError:pass
        relative=[r'Google\Chrome\Application\chrome.exe',r'Microsoft\Edge\Application\msedge.exe']
        if 'edge' in default:relative.reverse()
        for suffix in relative:
            for root in roots:
                candidate=Path(root)/suffix
                if candidate.is_file():browsers.append(candidate)
        if browsers:
            subprocess.Popen([str(browsers[0]),url]);return
        raise RuntimeError('Install Microsoft Edge or Google Chrome to run the local HTML app.')
    webbrowser.open(url)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test-report')
    args=parser.parse_args()
    if args.self_test_report:
        source=html_resource();text=source.read_text()
        assert 'id="embedded-assets"' in text and 'function saveTherapistFault' in text
        assert 'Resolution' in text and 'Source Screenshots' in text
        Path(args.self_test_report).write_text(json.dumps({'html':True,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'bytes':source.stat().st_size,'platform':sys.platform}))
        return
    try:launch(install_html())
    except Exception as error:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,str(error),APP_NAME,0x10)
        elif sys.platform=='darwin':
            message=json.dumps(str(error))
            subprocess.run(['osascript','-e','display alert "TrueBeam Service Log" message '+message],capture_output=True)
        else:raise
if __name__=='__main__':main()
