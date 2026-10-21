"""UFHPTI internal shared host for the existing, unchanged HTML interface."""
import argparse, base64, hashlib, ipaddress, json, mimetypes, os, re, secrets, smtplib, socket, sqlite3, subprocess, sys, tempfile, threading, time, uuid, webbrowser
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timedelta
from core import Engine, FIELDS, SUPPORTED, extract, parse
import evening_email

BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
DEFAULTS={
 'reports':r'U:\QA\SystemQA\LINAC QA\TrueBeam\Service reports',
 'screenshots':r'W:\Varian\Transfer\TDS\H192905\PrintScreen',
 'output':r'U:\QA\SystemQA\LINAC QA\TrueBeam\TrueBeam_Service_Log.xlsx',
 'running':True}
EMAIL=re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$')
def default_home():
    return Path(os.environ.get('TRUEBEAM_SHARED_HOME',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'.truebeam-shared-log')))
class Conflict(ValueError):pass
class SharedService:
    def __init__(self,home,clock=time.monotonic,defaults=None,shared_dir=None):
        self.home=Path(home);self.home.mkdir(parents=True,exist_ok=True)
        self.shared_dir=Path(shared_dir) if shared_dir else None;self.mirror_lock=threading.Lock();self.log_lock=threading.Lock()
        self.storage_root=self.shared_dir/'files' if self.shared_dir else self.home
        self.clock=clock;self.stop=threading.Event();self.next_report=0;self.last_report=None;self.last_log=None
        self.snapshot={'busy':False,'message':'Shared UFHPTI database ready.','last_scan':None}
        self.scan_lock=threading.Lock();self.engine=Engine(self.home)
        if self.shared_dir and (self.shared_dir/'settings.json').exists():
            self.engine.config=json.loads((self.shared_dir/'settings.json').read_text())
            self.engine.config_path.write_text(json.dumps(self.engine.config,indent=2))
        if not self.engine.config_path.exists():
            self.engine.config=dict(defaults or DEFAULTS)
            self.engine.config_path.write_text(json.dumps(self.engine.config,indent=2))
        if self.shared_dir:(self.shared_dir/'settings.json').write_text(json.dumps(self.engine.config,indent=2))
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY,record_id INTEGER,name TEXT,path TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS overrides(record_id INTEGER,field TEXT,value TEXT,PRIMARY KEY(record_id,field))')
            db.commit()
        last_log_file=self.home/'last-log.json'
        if last_log_file.exists():self.last_log=json.loads(last_log_file.read_text())
        self.email_file=self.home/'evening-email.json'
        self.email_status=json.loads(self.email_file.read_text()) if self.email_file.exists() else {}
        self.email_lock=threading.Lock();self.environ=os.environ;self.now=datetime.now;self.outlook_check=evening_email.outlook_available
        key=self.home/'access-key'
        if not key.exists():
            fd=os.open(key,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
        self.token=key.read_text().strip()
        self.engine.progress=lambda p:self.snapshot.update(message='Reading '+p.name)
        self.engine.apply_overrides=self.apply_overrides
        self.thread=threading.Thread(target=self.worker,daemon=True);self.last_scan=-5
    def mirror(self):
        if not self.shared_dir:return
        import shutil
        with self.mirror_lock:
            fd,local=tempfile.mkstemp(dir=self.home,suffix='.sqlite3');os.close(fd)
            fd,remote=tempfile.mkstemp(dir=self.shared_dir,suffix='.sqlite3');os.close(fd)
            try:
                with self.connection() as source:
                    with closing(sqlite3.connect(local)) as target:source.backup(target)
                shutil.copyfile(local,remote)
                os.replace(remote,self.shared_dir/'shared-data.sqlite3')
            finally:
                for path in (local,remote):
                    if os.path.exists(path):os.unlink(path)
    def apply_overrides(self,path):
        row=self.engine.db.execute('SELECT id FROM records WHERE path=?',(str(path),)).fetchone()
        if row:
            for field,value in self.engine.db.execute('SELECT field,value FROM overrides WHERE record_id=?',(row[0],)).fetchall():
                if field in FIELDS:self.engine.db.execute('UPDATE records SET '+field+'=? WHERE id=?',(value,row[0]))
    def connection(self):
        return closing(sqlite3.connect(self.home/'service-log.sqlite3',timeout=30))
    def reader(self):return Engine(self.home)
    def state(self):
        e=self.reader()
        try:
            from intake_policy import exclusion_reason
            records=[];excluded=[]
            for record in e.events():
                reason=exclusion_reason(record)
                if reason:excluded.append({'id':record['id'],'sources':record['sources'],'reason':reason,'error':record.get('error','')})
                else:records.append(record)
            with self.connection() as db:attachments=db.execute('SELECT id,record_id,name FROM attachments ORDER BY id').fetchall()
            for r in records:
                ids=[s['id'] for s in r['sources']];r['recordIds']=ids
                if r['document_type']=='Therapist entry':
                    r['entryType']='manual'
                    r['sources']=[{'id':'a:'+str(a),'path':n,'error':''} for a,rid,n in attachments if rid in ids]
            return dict(self.snapshot,folders_connected=all(self.engine.config.get(k) and os.path.isdir(self.engine.config[k]) and os.access(self.engine.config[k],os.R_OK) for k in ('reports','screenshots')),records=records,excluded=excluded,fields=FIELDS,config=dict(self.engine.config),email_status=self.email_summary(),last_report=self.last_report,last_log=self.last_log,database='Shared UFHPTI host database · edits save immediately.',shared=True)
        finally:e.db.close()
    def update(self,payload):
        field=payload.get('field')
        if field not in FIELDS:raise ValueError('Unknown field.')
        e=self.reader()
        try:
            e.db.execute('BEGIN IMMEDIATE')
            event=next((r for r in e.events() if r['id']==int(payload['id'])),None)
            if not event:raise ValueError('Entry no longer exists.')
            current=event.get(field,'') or ''
            if field=='service_status':current=current or event['review']
            if str(payload.get('expected','') or '')!=current:
                raise Conflict('Someone else changed this value. Your edit was not applied. Reload, check their value, and reapply your change if appropriate.')
            value=str(payload.get('value','')).strip()
            for source in event['sources']:
                e.db.execute('UPDATE records SET '+field+'=? WHERE id=?',(value,source['id']))
                e.db.execute('INSERT OR REPLACE INTO overrides VALUES(?,?,?)',(source['id'],field,value))
            e.db.commit();self.mirror();self.log_change();return {'ok':True}
        except Exception:e.db.rollback();raise
        finally:e.db.close()
    def add_fault(self,payload):
        fields=dict.fromkeys(FIELDS,'')
        for k in ('service_date','worker_initials','fault_code','fault_name','issue','work_performed'):fields[k]=str(payload.get(k,'')).strip()
        if not all(fields[k] for k in ('service_date','worker_initials','issue')):raise ValueError('Event time, initials and Error Details are required.')
        fields['worker_initials']=fields['worker_initials'].upper()[:12];fields['document_type']='Therapist entry'
        items=payload.get('attachments',[]);prepared=[]
        for item in items:
            name=Path(str(item.get('name','screenshot.png')).replace('\\','/')).name
            if Path(name).suffix.lower() not in {'.png','.jpg','.jpeg','.bmp','.webp'}:raise ValueError('Attach image files only.')
            data=base64.b64decode(item['data'],validate=True)
            if len(data)>20000000:raise ValueError('Each attachment must be under 20 MB.')
            prepared.append((name,data))
        folder=self.storage_root/'attachments';folder.mkdir(parents=True,exist_ok=True);written=[];committed=False
        try:
            with self.connection() as db:
                columns=['path','kind','digest','imported','text','error','review','extractor_version']+FIELDS
                values=['therapist://'+str(uuid.UUID(payload.get('requestId',str(uuid.uuid4())))),'screenshots',uuid.uuid4().hex,time.strftime('%Y-%m-%dT%H:%M:%S'),'','','Closure documented','manual']+[fields[k] for k in FIELDS]
                old=db.execute('SELECT id FROM records WHERE path=?',(values[0],)).fetchone()
                if old:self.mirror();return {'ok':True,'id':old[0]}
                cur=db.execute('INSERT INTO records('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',values);rid=cur.lastrowid
                for name,data in prepared:
                    path=folder/(uuid.uuid4().hex+Path(name).suffix.lower());path.write_bytes(data);written.append(path)
                    db.execute('INSERT INTO attachments(record_id,name,path) VALUES(?,?,?)',(rid,name,str(path)))
                db.commit();committed=True
            self.mirror();self.log_change();return {'ok':True,'id':rid}
        except Exception:
            if not committed:
                for path in written:path.unlink(missing_ok=True)
            raise
    def upload(self,payload):
        name=Path(str(payload.get('name','')).replace('\\','/')).name
        if Path(name).suffix.lower() not in SUPPORTED:raise ValueError('Unsupported file type.')
        data=base64.b64decode(payload['data'],validate=True)
        if len(data)>25000000:raise ValueError('Select a file under 25 MB.')
        digest=hashlib.sha256(data).hexdigest();folder=self.storage_root/'uploads';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(digest[:16]+'-'+name);path.write_bytes(data)
        kind='screenshots' if Path(name).suffix.lower() in {'.png','.jpg','.jpeg','.bmp','.webp','.tif','.tiff'} else 'reports'
        text='';error=''
        try:text=extract(path).strip()
        except Exception as exc:error=str(exc)
        fields=parse(text)
        if kind=='screenshots':
            from core import screenshot_file_time
            fields['service_date']=screenshot_file_time(name)
        e=self.reader()
        try:
            e.db.execute('BEGIN IMMEDIATE')
            old=e.db.execute('SELECT * FROM records WHERE path=?',(str(path),)).fetchone()
            if old:return {'ok':True,'id':old['id'],'error':old['error']}
            columns=['path','kind','digest','imported','text','error','review','extractor_version']+FIELDS
            values=[str(path),kind,digest,time.strftime('%Y-%m-%dT%H:%M:%S'),text,error,'Closure documented','shared-upload']+[fields[k] for k in FIELDS]
            cur=e.db.execute('INSERT INTO records('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',values);e.db.commit()
            self.mirror();self.log_change();return {'ok':True,'id':cur.lastrowid,'error':error}
        finally:e.db.close()
    def configure(self,payload):
        with self.scan_lock:
            logs=str(payload.get('logs',self.engine.config.get('logs',''))).strip()
            if logs and not Path(logs).is_dir():raise ValueError('Choose an existing logs folder.')
            email={k:self.engine.config[k] for k in ('evening_email','email_recipients','email_time') if k in self.engine.config}
            self.engine.configure(dict(payload,output=payload.get('output') or self.engine.config.get('output') or str(self.home/'unused-report.xlsx')),reuse_existing=True)
            self.engine.config['logs']=logs
            self.engine.config.update(email)
            self.engine.config['running']=bool(payload.get('running',True))
            self.engine.config_path.write_text(json.dumps(self.engine.config,indent=2))
            self.last_scan=-5;self.next_report=0
        if self.shared_dir:(self.shared_dir/'settings.json').write_text(json.dumps(self.engine.config,indent=2))
        return {'ok':True}
    def email_settings(self,payload):
        recipients=payload.get('recipients',[])
        if not isinstance(recipients,list):raise ValueError('Send email recipients as a list.')
        recipients=list(dict.fromkeys(str(r).strip() for r in recipients if str(r).strip()))
        invalid=[r for r in recipients if not EMAIL.match(r)]
        if invalid:raise ValueError('Check these email addresses: '+', '.join(invalid))
        enabled=bool(payload.get('enabled'))
        if enabled and not recipients:raise ValueError('Add at least one email address to send the evening email.')
        send_time=evening_email.parse_time(payload.get('time',self.engine.config.get('email_time')))
        with self.scan_lock:
            self.engine.config.update(evening_email=enabled,email_recipients=recipients,email_time=send_time)
            self.engine.config_path.write_text(json.dumps(self.engine.config,indent=2))
        if self.shared_dir:(self.shared_dir/'settings.json').write_text(json.dumps(self.engine.config,indent=2))
        return {'ok':True}
    def email_summary(self):
        try:method,settings=evening_email.delivery(self.environ,self.outlook_check);problem=''
        except ValueError as exc:method,settings,problem=None,None,str(exc)
        via='Outlook on this host' if method=='outlook' else settings['host'] if settings else ''
        return {'configured':bool(method),'via':via,'problem':problem,'last_sent_at':self.email_status.get('last_sent_at'),'last_error':self.email_status.get('last_error','')}
    def send_evening_email(self,test=False):
        method,settings=evening_email.delivery(self.environ,self.outlook_check)
        recipients=self.engine.config.get('email_recipients') or []
        if not recipients:raise ValueError('Add at least one email address, then save email settings.')
        now=self.now();last=self.email_status.get('last_sent_at')
        since=datetime.fromisoformat(last) if last else now-timedelta(days=1)
        everything=self.state()['records'];records=evening_email.new_entries(everything,since)
        message=evening_email.build_message(records,everything,recipients,settings['sender'] if settings else '',since,now,test=test)
        if method=='outlook':evening_email.send_outlook(message)
        else:evening_email.send(message,settings)
        return now,len(records)
    def email_tick(self):
        with self.email_lock:
            now=self.now()
            if not evening_email.due(self.engine.config,self.email_status,now):return
            self.email_status['last_attempt_at']=now.isoformat(timespec='seconds')
            try:
                sent,_=self.send_evening_email()
                self.email_status.update(last_sent_at=sent.isoformat(timespec='seconds'),last_sent_date=sent.date().isoformat(),last_error='')
            except Exception as exc:self.email_status['last_error']=now.strftime('%Y-%m-%d %H:%M')+' · '+str(exc)
            self.email_file.write_text(json.dumps(self.email_status))
    def email_test(self):
        with self.email_lock:
            try:sent,count=self.send_evening_email(test=True)
            except (OSError,smtplib.SMTPException,subprocess.TimeoutExpired) as exc:raise ValueError('Test email failed: '+str(exc)) from None
        return {'ok':True,'entries':count,'recipients':len(self.engine.config.get('email_recipients') or [])}
    def log_change(self):
        try:self.save_addition_log()
        except Exception as exc:self.snapshot.update(message='Log save pending: '+str(exc)+'. Changes remain saved; retrying automatically.')
    def save_addition_log(self,force=False):
        with self.log_lock:return self._save_change_log(force)
    def _save_change_log(self,force=False):
        folder=self.engine.config.get('logs','')
        if not folder:
            if force:raise ValueError('Choose a Logs folder in Folder settings.')
            return
        records=self.state()['records']
        signature=hashlib.sha256(json.dumps(sorted(records,key=lambda r:str(r['id'])),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        ledger=self.home/'timestamped-log-entries.json'
        saved=json.loads(ledger.read_text()) if ledger.exists() else {}
        previous=saved.get(str(folder))
        if not force and (previous==signature or (not records and previous is None)):return
        from datetime import datetime
        from report_export import write_report
        output=Path(folder)/('TrueBeam_Log_'+datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')+'_'+uuid.uuid4().hex[:8]+'.xlsx')
        write_report(records,output,overwrite=False)
        saved[str(folder)]=signature
        self.last_report=time.strftime('%Y-%m-%d %H:%M:%S')
        self.last_log={'path':str(output),'saved_at':datetime.now().astimezone().isoformat()}
        (self.home/'last-log.json').write_text(json.dumps(self.last_log))
        temporary=ledger.with_suffix('.tmp');temporary.write_text(json.dumps(saved));temporary.replace(ledger)

    def tick(self):
        if self.engine.config.get('running') and self.clock()-self.last_scan>=5:
            with self.scan_lock:
                self.snapshot.update(busy=True,message='Monitoring established folders.')
                try:
                    self.engine.scan(auto_export=False)
                    # Reapply persisted edits, including intentionally empty values.
                    with self.connection() as db:
                        for rid,field,value in db.execute('SELECT record_id,field,value FROM overrides').fetchall():
                            if field in FIELDS:db.execute('UPDATE records SET '+field+'=? WHERE id=?',(value,rid))
                        db.commit()
                    if self.engine.dirty:self.mirror();self.engine.dirty=False
                    self.snapshot.update(message=self.engine.message or 'Host folders checked.')
                finally:self.snapshot.update(busy=False,last_scan=time.strftime('%Y-%m-%d %H:%M:%S'));self.last_scan=self.clock()
        self.save_addition_log()
        self.email_tick()
    def worker(self):
        while not self.stop.wait(.25):
            try:self.tick()
            except Exception as e:self.last_scan=self.clock();self.snapshot.update(busy=False,message='Monitoring needs attention: '+str(e))
    def close(self):
        self.stop.set()
        if self.thread.is_alive():self.thread.join(timeout=130)
        self.engine.db.close()

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,service):
        self.service=service;super().__init__(address,Handler)
        hostname=socket.gethostname().lower()
        # Discovery always publishes this hostname. Avoid reverse-DNS lookups that
        # can stall native startup on networks without reverse DNS configured.
        self.allowed_hosts={'localhost','127.0.0.1',hostname,hostname.split('.')[0]}
        if address[0] not in ('0.0.0.0',''):self.allowed_hosts.add(address[0])
    def valid_host(self,host):
        try:
            parsed=urlsplit('http://'+host)
            return parsed.hostname in self.allowed_hosts and parsed.port==self.server_port
        except ValueError:return False
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,data,kind='application/json'):
        if kind=='application/json':data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; frame-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try:self.wfile.write(data)
        except ConnectionError:pass
    def authorized(self):
        try:internal=ipaddress.ip_address(self.client_address[0]).is_private
        except ValueError:internal=False
        return internal and self.server.valid_host(self.headers.get('Host','')) and secrets.compare_digest(self.headers.get('X-Local-Token',''),self.server.service.token)
    def local_admin(self):return self.client_address[0] in ('127.0.0.1','::1')
    def do_GET(self):
        route=urlsplit(self.path)
        if not self.server.valid_host(self.headers.get('Host','')):return self.respond(403,{'error':'Use the UFHPTI host app address.'})
        if route.path=='/' and getattr(self.server.service,'unified_html',False):return self.respond(200,(BASE/'standalone'/'TrueBeam-Local.html').read_bytes(),'text/html; charset=utf-8')
        if route.path=='/':
            page=(BASE/'index.html').read_text()
            page=page.replace("if(typeof localApi==='function')await api('inline-update',{id:record.id,field,value});","if(typeof sharedSaveField==='function')await sharedSaveField(record,field,value);else if(typeof localApi==='function')await api('inline-update',{id:record.id,field,value});")
            page=page.replace("poll();setInterval(poll,2000);","window.addEventListener('DOMContentLoaded',initShared);",1)
            page=page.replace("<script>\n'use strict';","<script src=\"/shared-client.js\"></script><script>\n'use strict';")
            page=page.replace('Local database · files stay on this computer','Shared UFHPTI app')
            page=page.replace('Monitoring runs while the launcher is open. Original files are never changed. All extracted entries require review.','Edits save to the shared database. Excel refreshes report data without replacing the open workbook.')
            return self.respond(200,page.encode(),'text/html; charset=utf-8')
        if route.path=='/shared-client.js':return self.respond(200,(BASE/'shared-client.js').read_bytes(),'text/javascript; charset=utf-8')
        if route.path=='/favicon.ico':return self.respond(204,b'','image/x-icon')
        if not self.authorized():return self.respond(403,{'error':'Open the access link provided by the UFHPTI host.'})
        s=self.server.service
        try:
            if route.path=='/api/health':return self.respond(200,{'ok':True})
            if route.path=='/api/state':return self.respond(200,dict(s.state(),admin=self.local_admin()))
            if route.path=='/api/source':
                source=parse_qs(route.query).get('id',[''])[0]
                with s.connection() as db:
                    row=db.execute('SELECT path FROM '+('attachments' if source.startswith('a:') else 'records')+' WHERE id=?',(int(source[2:] if source.startswith('a:') else source),)).fetchone()
                if not row or not Path(row[0]).is_file():raise ValueError('Original file unavailable on the host.')
                path=Path(row[0]);return self.respond(200,path.read_bytes(),mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            if route.path=='/api/excel':
                path=Path(s.engine.config['output'])
                if not path.is_file():raise ValueError('Report not created. Check the shared report folder on the host.')
                return self.respond(200,path.read_bytes(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            return self.respond(404,{'error':'Not found.'})
        except (ValueError,OSError) as e:return self.respond(400,{'error':str(e)})
    def do_POST(self):
        if not self.authorized():return self.respond(403,{'error':'UFHPTI shared app access required.'})
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host'):return self.respond(403,{'error':'Open this action within the app.'})
        try:
            size=int(self.headers.get('Content-Length',0))
            if size<0 or size>40000000:return self.respond(413,{'error':'Select files under 25 MB.'})
            body=json.loads(self.rfile.read(size) or b'{}')
            if not isinstance(body,dict):raise ValueError('Invalid request.')
            route=urlsplit(self.path).path.removeprefix('/api/');s=self.server.service
            if route in ('configure','pause','export','retry','browse','email-settings','email-test') and not self.local_admin():return self.respond(403,{'error':'Manage folder settings from the host computer.'})
            if route=='browse':
                command=[sys.executable,'--pick-folder'] if getattr(sys,'frozen',False) else [sys.executable,str(BASE/'shared_application.py'),'--pick-folder']
                with tempfile.TemporaryDirectory() as picker_dir:
                    picker_path=Path(picker_dir)/'selected.txt'
                    picked=subprocess.run(command+['--picker-result',str(picker_path)],capture_output=True,text=True,timeout=120)
                    if picked.returncode:raise ValueError('Paste the host folder path into the field.')
                    result={'path':picker_path.read_text() if picker_path.exists() else ''}
            elif route=='inline-update':result=s.update(body)
            elif route=='add-fault':result=s.add_fault(body)
            elif route=='upload':result=s.upload(body)
            elif route=='configure':result=s.configure(body)
            elif route=='email-settings':result=s.email_settings(body)
            elif route=='email-test':result=s.email_test()
            elif route=='pause':
                with s.scan_lock:s.engine.config['running']=False;s.engine.config_path.write_text(json.dumps(s.engine.config,indent=2))
                result={'ok':True}
            elif route in ('scan','retry'):
                if route=='retry':
                    with s.connection() as db:db.execute("UPDATE records SET extractor_version='' WHERE error<>''");db.commit()
                s.last_scan=-5;result={'ok':True}
            elif route=='export':
                with s.scan_lock:s.save_addition_log(force=True)
                result={'ok':True}
            else:return self.respond(404,{'error':'Unknown action.'})
            return self.respond(200,result)
        except Conflict as e:return self.respond(409,{'error':str(e)})
        except (ValueError,OSError,KeyError,TypeError) as e:return self.respond(400,{'error':str(e)})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',default=str(default_home()))
    parser.add_argument('--port',type=int,default=8766);parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--share-ufhpti',action='store_true',help='Enable authorized UFHPTI internal-network sharing.')
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--self-test-report')
    args=parser.parse_args()
    if args.self_test_report:
        from desktop_app import main as desktop_test
        sys.argv=[sys.argv[0],'--self-test-report',args.self_test_report];desktop_test();return
    service=SharedService(args.data_dir)
    address='0.0.0.0' if args.share_ufhpti else args.host
    server=Server((address,args.port),service);service.thread.start()
    local='http://127.0.0.1:'+str(server.server_port)+'/#'+service.token
    shared='http://'+socket.gethostname()+':'+str(server.server_port)+'/#'+service.token
    (service.home/'Shared app link.txt').write_text(shared+'\nUFHPTI internal staff only. Keep the host running.')
    if not args.no_browser:webbrowser.open(local)
    try:server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:pass
    finally:server.server_close();service.close()
if __name__=='__main__':main()
