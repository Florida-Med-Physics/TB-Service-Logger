"""Native desktop controller: disk settings/database and 10-minute atomic report writes."""
import json, logging, os, queue, threading, time
from pathlib import Path
from core import Engine, FIELDS
from report_export import write_report

SAVE_SECONDS = 600
SCAN_SECONDS = 5

def data_home():
    if os.environ.get('TRUEBEAM_LOG_HOME'):
        return Path(os.environ['TRUEBEAM_LOG_HOME']).expanduser()
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / '.truebeam-service-log'

class DesktopWorker:
    def __init__(self, home=None, clock=time.monotonic):
        self.home=Path(home or data_home())
        self.home.mkdir(parents=True,exist_ok=True)
        self.clock=clock
        self.commands=queue.Queue()
        self.events=queue.Queue()
        self.stopped=threading.Event()
        self.thread=threading.Thread(target=self.run,daemon=True)
        self.logger=logging.getLogger('truebeam.'+str(self.home))
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            from logging.handlers import RotatingFileHandler
            h=RotatingFileHandler(self.home/'application.log',maxBytes=2000000,backupCount=1,encoding='utf-8')
            h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));self.logger.addHandler(h)
        self.next_save=None
        self.next_scan=0
        self.next_retry=0
        self.last_save=None
        self.engine=None

    def submit(self,action,**payload):
        self.commands.put((action,payload))

    def snapshot(self,message=None):
        self.events.put(dict(type='state',records=self.engine.events(),config=dict(self.engine.config),
                             message=message,last_save=self.last_save,next_save=self.next_save))

    def save_report(self):
        try:
            output=Path(self.engine.config['output'])
            write_report(self.engine.events(),output)
            self.engine.dirty=False
            self.last_save=time.strftime('%Y-%m-%d %H:%M:%S')
            self.next_save=self.clock()+SAVE_SECONDS
            self.next_retry=0
            self.logger.info('Report replaced: %s',output)
            self.snapshot('Export Report saved: '+str(output))
            return True
        except Exception as exc:
            self.next_retry=self.clock()+30
            self.logger.exception('Report save failed')
            self.snapshot('Report not saved: '+str(exc)+'. Close Excel if the file is locked. Retrying in 30 seconds; database entries are safe.')
            return False

    def tick(self):
        now=self.clock()
        if self.engine.config.get('running') and now>=self.next_scan:
            self.engine.scan(auto_export=False)
            self.next_scan=self.clock()+SCAN_SECONDS
            errors=sum(bool(r['error']) for r in self.engine.rows())
            # Folder warnings from the scan replace the steady connected status.
            status='Connected · Actively monitoring' if self.engine.message.startswith('Monitoring established') else self.engine.message
            self.snapshot(status+' · '+str(len(self.engine.rows()))+' source files saved'+(' · '+str(errors)+' import warnings. Open Import details to inspect.' if errors else '.'))
        output_ready=bool(self.engine.config.get('reports') and self.engine.config.get('screenshots'))
        if output_ready and self.next_save is not None and self.clock()>=self.next_save and self.clock()>=self.next_retry:
            self.save_report()

    def handle(self,action,payload):
        if action=='configure':
            self.engine.configure(payload)
            self.next_scan=0
            if self.next_save is None:self.next_save=self.clock()
            self.snapshot('Folders and report path saved. Monitoring started.')
        elif action=='pause':
            self.engine.config['running']=False
            self.engine.config_path.write_text(json.dumps(self.engine.config,indent=2))
            self.snapshot('Monitoring paused. Report still re-saves every 10 minutes while the app is running.')
        elif action=='scan':
            if not all(self.engine.config.get(k) for k in ('reports','screenshots')):raise ValueError('Choose both folders first.')
            # Explicit scan works even when monitoring is paused.
            running=self.engine.config.get('running',False)
            self.engine.config['running']=True
            try:self.engine.scan(auto_export=False)
            finally:self.engine.config['running']=running
            self.snapshot('Scan complete. Newly copied files are imported after two stable scans.')
        elif action=='retry':
            self.engine.db.execute("UPDATE records SET extractor_version='' WHERE error<>''")
            self.engine.db.commit();self.next_scan=0
            self.snapshot('Failed imports will be retried on the next scan.')
        elif action=='update':
            record=next((r for r in self.engine.events() if r['id']==payload['id']),None)
            if not record:raise ValueError('Entry no longer exists.')
            field=payload['field']
            if field not in FIELDS:raise ValueError('Unknown field.')
            # Apply edits to all grouped originals so duplicate grouping remains stable.
            with self.engine.db:
                for source in record['sources']:
                    self.engine.db.execute('UPDATE records SET '+field+'=? WHERE id=?',(payload['value'],source['id']))
            self.engine.dirty=True
            self.snapshot('Change saved. Export Report is overwritten at the next 10-minute save.')
        elif action=='export':
            self.save_report()
        elif action=='stop':
            if self.engine.config.get('reports') and self.engine.dirty:self.save_report()
            self.stopped.set()

    def run(self):
        try:
            self.engine=Engine(self.home)
            self.engine.progress=lambda path:self.events.put(dict(type='progress',message='Reading '+path.name))
            configured=all(self.engine.config.get(k) for k in ('reports','screenshots'))
            # Saved running preference and all three paths survive restarts.
            self.next_save=self.clock()+SAVE_SECONDS if configured else None
            self.snapshot('Saved folders restored.' if configured else 'Choose your service-report folder, screenshot folder, and Excel output.')
            while not self.stopped.is_set():
                try:
                    action,payload=self.commands.get(timeout=.2)
                    self.handle(action,payload)
                except queue.Empty:
                    pass
                except Exception as exc:
                    self.logger.exception('Operation failed')
                    self.events.put(dict(type='error',message=str(exc)))
                if not self.stopped.is_set():
                    try:self.tick()
                    except Exception as exc:
                        self.next_scan=self.clock()+SCAN_SECONDS
                        self.logger.exception('Monitoring failed')
                        self.events.put(dict(type='error',message=str(exc)))
        except Exception as exc:
            self.logger.exception('Startup failed')
            self.events.put(dict(type='error',message='Startup failed: '+str(exc)))
        finally:
            if self.engine:self.engine.db.close()
            for handler in self.logger.handlers[:]:handler.close();self.logger.removeHandler(handler)
            self.events.put(dict(type='closed'))
