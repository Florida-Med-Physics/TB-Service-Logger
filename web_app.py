"""Loopback-only HTML application. Reports and database stay on this computer."""
import argparse, json, mimetypes, os, queue, secrets, sqlite3, subprocess, sys, tempfile, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from core import Engine, FIELDS
from contextlib import closing

BASE=Path(__file__).resolve().parent

class Service:
    def __init__(self, home):
        self.engine=Engine(home)
        self.reader=Engine(home)
        self.read_lock=threading.Lock()
        self.queue=queue.Queue()
        self.stop=threading.Event()
        self.snapshot={'busy':False,'message':('Folders saved. Start monitoring to resume.' if self.engine.config.get('reports') else 'Choose the service-report and screenshot folders to begin.'),'config':dict(self.engine.config),'last_scan':None,'job':None}
        self.engine.progress=self.progress
        self.thread=threading.Thread(target=self.worker,daemon=True)
    def progress(self,path):
        self.snapshot=dict(self.snapshot,message='Checking '+path.name)
    def publish(self,**changes):
        self.snapshot=dict(self.snapshot,**changes)
    def state(self):
        with self.read_lock:
            rows=self.reader.events()
        return dict(self.snapshot,records=rows,fields=FIELDS,database=str(self.engine.home/'service-log.sqlite3'))
    def submit(self,action,payload):
        job=secrets.token_hex(6)
        self.queue.put((job,action,payload))
        return job
    def worker(self):
        next_scan=0
        while not self.stop.is_set():
            try:
                try:job,action,payload=self.queue.get(timeout=.25)
                except queue.Empty:job=None
                if job:
                    try:
                        if action=='configure':
                            self.engine.configure(dict(payload,output=str(self.engine.home/'TrueBeam Service Log.xlsx')))
                            next_scan=0
                        elif action=='pause':
                            self.engine.config['running']=False
                            self.engine.config_path.write_text(json.dumps(self.engine.config,indent=2))
                            self.publish(message='Monitoring paused. Existing entries remain saved.')
                        elif action=='update':
                            old=self.engine.db.execute('SELECT * FROM records WHERE id=?',(int(payload['id']),)).fetchone()
                            if not old:raise ValueError('This record no longer exists.')
                            self.engine.update(dict(dict(old),**payload))
                        elif action=='merge':
                            self.engine.merge(int(payload['source']),int(payload['target']))
                        elif action=='retry':
                            self.engine.db.execute("UPDATE records SET digest='' WHERE error<>''")
                            self.engine.db.commit();next_scan=0
                            if self.engine.config.get('reports'):self.scan_passes=2
                        elif action=='scan':
                            if not self.engine.config.get('reports'):raise ValueError('Choose the two folders first.')
                            next_scan=0
                            self.scan_passes=2
                        elif action=='export':
                            self.engine.export();self.engine.dirty=False
                        self.publish(job={'id':job,'ok':True,'message':'Change applied.'},config=dict(self.engine.config))
                    except Exception as exc:
                        self.publish(job={'id':job,'ok':False,'message':str(exc)})
                running=self.engine.config.get('running',False)
                once=getattr(self,'scan_passes',0)>0
                if (running or once) and time.monotonic()>=next_scan:
                    self.publish(busy=True,message='Checking folders…')
                    self.engine.config['running']=True
                    try:self.engine.scan()
                    finally:self.engine.config['running']=running;self.scan_passes=max(0,getattr(self,'scan_passes',0)-1)
                    self.publish(busy=False,message=self.engine.message,last_scan=time.strftime('%Y-%m-%d %H:%M:%S'),config=dict(self.engine.config))
                    next_scan=time.monotonic()+3
                elif self.engine.dirty and self.engine.config.get('reports'):
                    try:self.engine.export();self.engine.dirty=False
                    except Exception as exc:self.publish(message='Database saved. Excel export pending: '+str(exc))
            except Exception as exc:self.publish(busy=False,message='Monitoring needs attention: '+str(exc))
    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)

class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,service):
        self.service=service;self.token=secrets.token_urlsafe(32)
        super().__init__(address,Handler)
        self.expected_host='127.0.0.1:'+str(self.server_port)
        self.origin='http://'+self.expected_host

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,data,kind='application/json',filename=None):
        if kind=='application/json':data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' blob: data:; frame-src blob: 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.end_headers()
        try:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass
    def valid_host(self):
        return self.headers.get('Host')==self.server.expected_host
    def authorized(self):
        return self.valid_host() and secrets.compare_digest(self.headers.get('X-Local-Token',''),self.server.token)
    def do_GET(self):
        path=urlsplit(self.path)
        if not self.valid_host():return self.respond(403,{'error':'Local access only.'})
        if path.path=='/':
            return self.respond(200,(BASE/'index.html').read_bytes(),'text/html; charset=utf-8')
        if path.path=='/favicon.ico':return self.respond(204,b'','image/x-icon')
        if not self.authorized():return self.respond(403,{'error':'Launch the app using its local launcher.'})
        try:
            if path.path=='/api/state':return self.respond(200,self.server.service.state())
            if path.path=='/api/source':
                record_id=int(parse_qs(path.query).get('id',['0'])[0])
                service=self.server.service
                with service.read_lock:
                    row=service.reader.db.execute('SELECT path FROM records WHERE id=?',(record_id,)).fetchone()
                if not row:raise ValueError('Unknown source.')
                file=Path(row['path'])
                if not file.is_file():return self.respond(404,{'error':'Source is unavailable at its recorded location.'})
                return self.respond(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
            if path.path=='/api/excel':
                file=self.server.service.engine.home/'TrueBeam Service Log.xlsx'
                if not file.exists():return self.respond(404,{'error':'The Excel export is not ready yet.'})
                return self.respond(200,file.read_bytes(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','TrueBeam Service Log.xlsx')
            if path.path=='/api/backup':
                fd,name=tempfile.mkstemp(suffix='.sqlite3');os.close(fd)
                try:
                    with closing(sqlite3.connect(name)) as dest:
                        with self.server.service.read_lock:self.server.service.reader.db.backup(dest)
                    return self.respond(200,Path(name).read_bytes(),'application/octet-stream','TrueBeam Service Log.sqlite3')
                finally:os.unlink(name)
            return self.respond(404,{'error':'Not found.'})
        except (ValueError,OSError) as exc:self.respond(400,{'error':str(exc)})
    def do_POST(self):
        if not self.authorized() or self.headers.get('Origin',self.server.origin)!=self.server.origin:
            return self.respond(403,{'error':'Local session required.'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>1000000 or size<0:return self.respond(413,{'error':'Request too large.'})
            payload=json.loads(self.rfile.read(size) or b'{}')
            if not isinstance(payload,dict):raise ValueError('Invalid request.')
            action=urlsplit(self.path).path.removeprefix('/api/')
            if action=='browse':
                result=subprocess.run([sys.executable,str(BASE/'folder_picker.py')],capture_output=True,text=True,timeout=120)
                if result.returncode:raise ValueError('Folder picker unavailable. Paste the folder path instead.')
                return self.respond(200,{'path':result.stdout.strip()})
            if action not in ('configure','pause','update','merge','retry','scan','export'):
                return self.respond(404,{'error':'Unknown action.'})
            job=self.server.service.submit(action,payload)
            return self.respond(202,{'queued':True,'id':job})
        except (ValueError,TypeError,subprocess.TimeoutExpired) as exc:self.respond(400,{'error':str(exc)})

def main():
    parser=argparse.ArgumentParser(description='TrueBeam local browser application')
    default_home=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'.truebeam-service-log'
    parser.add_argument('--data-dir',default=os.environ.get('TRUEBEAM_LOG_HOME',str(default_home)))
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    service=Service(args.data_dir)
    try:server=LocalServer(('127.0.0.1',args.port),service)
    except OSError:
        print('Port 8765 is already in use. Close the other local app window and its launcher, or use --port with a different number.')
        return 1
    service.thread.start()
    url=server.origin+'/#'+server.token
    print('TrueBeam Service Log is running locally. Keep this window open.')
    print('Database:',service.engine.home/'service-log.sqlite3')
    print('Open this address if the browser does not appear:',url)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:pass
    finally:server.server_close();service.close()
    return 0

if __name__=='__main__':sys.exit(main())
