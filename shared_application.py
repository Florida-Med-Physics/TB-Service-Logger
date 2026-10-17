"""Discover one UFHPTI host from the shared folder; all launchers use the same HTML UI."""
import argparse, ipaddress, json, os, shutil, socket, sqlite3, sys, tempfile, time, urllib.request, webbrowser
from pathlib import Path
from application_host import SharedService,Server,DEFAULTS,default_home
REPORT_FOLDER=Path(r'U:\QA\SystemQA\LINAC QA\TrueBeam')
def app_home():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'Library'/'Application Support')))/'TrueBeam Service Log'
def open_url(url):
    if sys.platform=='darwin':
        import subprocess
        for app in ('Google Chrome','Microsoft Edge'):
            if subprocess.run(['open','-Ra',app],capture_output=True).returncode==0:
                subprocess.run(['open','-a',app,url],check=True);return
    webbrowser.open(url)
def connection_url(folder):
    metadata=json.loads((folder/'connection.json').read_text())
    host=str(metadata['host']);port=int(metadata['port']);token=str(metadata['token'])
    if not all(ipaddress.ip_address(addr[4][0]).is_private for addr in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)):raise ValueError('Use the UFHPTI internal host.')
    url='http://'+host+':'+str(port)
    request=urllib.request.Request(url+'/api/health',headers={'X-Local-Token':token})
    with urllib.request.urlopen(request,timeout=4) as response:
        if not json.load(response).get('ok'):raise ValueError('Host unavailable.')
    return url+'/#'+token
class Lease:
    def __init__(self,path):
        self.file=open(path,'a+b')
        self.file.seek(0)
        if self.file.read(1)==b'':self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if sys.platform=='win32':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:self.file.close();raise
    def close(self):
        if not self.file.closed:self.file.close()
def choose_shared_folder():
    home=app_home();home.mkdir(parents=True,exist_ok=True);settings=home/'shared-location.json'
    if settings.exists():return Path(json.loads(settings.read_text())['folder'])
    if sys.platform=='win32' and REPORT_FOLDER.is_dir():folder=REPORT_FOLDER/'TrueBeamApp'
    elif sys.platform=='darwin':
        import subprocess
        result=subprocess.run(['osascript','-e','POSIX path of (choose folder with prompt "Select the TrueBeamApp folder on the UFHPTI shared drive")'],capture_output=True,text=True)
        if result.returncode:raise ValueError('Select the shared TrueBeamApp folder to connect.')
        folder=Path(result.stdout.strip())
    else:raise ValueError('Connect the U: network drive or provide --shared-folder.')
    settings.write_text(json.dumps({'folder':str(folder)}));return folder
def run(folder,allow_host=True,no_browser=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    try:lease=Lease(folder/'host.lock')
    except OSError:
        error=None
        for _ in range(15):
            try:
                url=connection_url(folder)
                if not no_browser:open_url(url)
                return
            except Exception as e:error=e;time.sleep(.4)
        raise ValueError('The host is starting or is unavailable. '+str(error))
    if not allow_host or sys.platform!='win32':
        lease.close()
        try:open_url(connection_url(folder));return
        except Exception:raise ValueError('Start the application on a Windows computer with U: and W: connected. Mac clients then open the same shared app.')
    service=None;server=None
    try:
        home=default_home();home.mkdir(parents=True,exist_ok=True)
        durable=folder/'shared-data.sqlite3'
        if durable.exists():
            for suffix in ('-wal','-shm'):(home/('service-log.sqlite3'+suffix)).unlink(missing_ok=True)
            shutil.copy2(durable,home/'service-log.sqlite3')
        service=SharedService(home,shared_dir=folder)
        try:server=Server(('0.0.0.0',8766),service)
        except OSError:server=Server(('0.0.0.0',0),service)
        metadata={'host':socket.gethostname(),'port':server.server_port,'token':service.token}
        fd,tmp=tempfile.mkstemp(dir=folder,suffix='.json');os.close(fd)
        Path(tmp).write_text(json.dumps(metadata));os.replace(tmp,folder/'connection.json')
        service.thread.start()
        if not no_browser:open_url('http://127.0.0.1:'+str(server.server_port)+'/#'+service.token)
        server.serve_forever(poll_interval=.5)
    finally:
        if server:server.server_close()
        if service:service.close()
        lease.close()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--shared-folder');parser.add_argument('--no-browser',action='store_true');parser.add_argument('--pick-folder',action='store_true');parser.add_argument('--picker-result');parser.add_argument('--self-test-report');args=parser.parse_args()
    if args.pick_folder:
        import tkinter as tk
        from tkinter import filedialog
        root=tk.Tk();root.withdraw();root.attributes('-topmost',True)
        selected=filedialog.askdirectory();root.destroy()
        if args.picker_result:Path(args.picker_result).write_text(selected)
        else:print(selected)
        return
    if args.self_test_report:
        import hashlib
        from application_host import BASE
        text=(BASE/'index.html').read_bytes()
        Path(args.self_test_report).write_text(json.dumps({'html':True,'sha256':hashlib.sha256(text).hexdigest(),'platform':sys.platform,'shared':True,'defaults':DEFAULTS}));return
    try:run(Path(args.shared_folder) if args.shared_folder else choose_shared_folder(),no_browser=args.no_browser)
    except Exception as e:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,str(e),'TrueBeam Service Log',0x10)
        elif sys.platform=='darwin':
            import subprocess
            subprocess.run(['osascript','-e','display alert "TrueBeam Service Log" message '+json.dumps(str(e))],capture_output=True)
        else:raise
if __name__=='__main__':main()
