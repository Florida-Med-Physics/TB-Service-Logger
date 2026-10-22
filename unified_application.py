"""One HTML interface, displayed in a dedicated Windows or Mac app window."""
import argparse,base64,json,os,queue,re,sys,tempfile,time
from pathlib import Path
from PySide6.QtCore import QObject,Signal,Slot,QFile,QIODevice,QUrl,QTimer,QSettings,QStandardPaths
from PySide6.QtGui import QIcon,QDesktopServices
from PySide6.QtWidgets import QApplication,QMainWindow,QFileDialog,QMessageBox
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest,QWebEnginePage,QWebEngineProfile,QWebEngineScript,QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from native_application import Backend,Api,Task
from shared_application import app_home,REPORT_FOLDER
from application_host import BASE
from PySide6.QtCore import QThreadPool

class Bridge(QObject):
    reply=Signal(str,str)
    def __init__(self,window):
        super().__init__(window);self.window=window
    @Slot(str,str,str)
    def request(self,route,payload,request_id):
        allowed={'state','inline-update','add-fault','upload','configure','pause','scan','retry','export','excel','email-settings','email-test','downtime-alert','alert-settings'}
        if route not in allowed:
            self.reply.emit(request_id,json.dumps({'error':'Unsupported application request.'}));return
        def work():
            body=json.loads(payload) if payload else None
            data=self.window.api.request(route,body,raw=True)
            return {'data':base64.b64encode(data).decode(),'type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if route=='excel' else 'application/json'}
        self.window.task(work,lambda result:self.reply.emit(request_id,json.dumps(result)),lambda error:self.reply.emit(request_id,json.dumps({'error':error})))
    @Slot(str,result=str)
    def pick(self,kind):
        if not self.window.api or not self.window.api.local:return json.dumps({'error':'Choose shared folders on the host computer.'})
        from application_host import DEFAULTS
        config=self.window.api.request('state')['config']
        chosen=getattr(self.window,'selected_service_folder',None)
        defaults={'reports':DEFAULTS['reports'],'screenshots':DEFAULTS['screenshots'],'logs':str(REPORT_FOLDER),'output':str(REPORT_FOLDER)}
        remembered=config.get(kind,'')
        candidates=[remembered,defaults.get(kind,''),chosen,config.get('reports','')]
        start=next((str(Path(value).parent if kind=='output' and Path(value).suffix.lower()=='.xlsx' else Path(value)) for value in candidates if value and (Path(value).parent if kind=='output' and Path(value).suffix.lower()=='.xlsx' else Path(value)).is_dir()),str(Path.home()))
        if kind=='output':
            path,_=QFileDialog.getSaveFileName(self.window,'Choose Excel report',str(Path(start)/'TrueBeam_Service_Log.xlsx'),'Excel workbook (*.xlsx)',options=QFileDialog.DontConfirmOverwrite)
        else:path=QFileDialog.getExistingDirectory(self.window,'Choose '+('service report' if kind=='reports' else 'logs' if kind=='logs' else 'screenshot')+' folder',start)
        if path and kind=='reports':self.window.selected_service_folder=path
        return json.dumps({'path':os.path.normpath(path) if path else ''})
    @Slot(str,result=str)
    def source(self,source_id):
        window=self.window
        def work():
            state=window.api.request('state')
            sources=[s for r in state['records'] for s in r.get('sources',[])]+[s for r in state.get('excluded',[]) for s in r.get('sources',[])]
            item=next((s for s in sources if str(s['id'])==source_id),None)
            if not item:raise ValueError('Source file is unavailable.')
            name=Path(str(item['path']).replace(chr(92),'/')).name
            folder=app_home()/'opened-files';folder.mkdir(parents=True,exist_ok=True)
            path=folder/(source_id.replace(':','-')+'-'+name)
            path.write_bytes(window.api.request('source?id='+source_id,raw=True))
            return str(path)
        window.task(work,lambda path:QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
        return json.dumps({'queued':True})

class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self,level,message,line,source):
        if hasattr(self,'messages'):self.messages.append(str(message)[:300])

class Window(QMainWindow):
    def __init__(self,backend,preferences):
        super().__init__();self.backend=backend;self.preferences=preferences;self.api=None
        self.pool=QThreadPool(self);self.tasks=set();self.last_error=''
        self.setWindowTitle('TrueBeam Service Log');self.resize(1540,960);self.setMinimumSize(1000,650)
        self.setWindowIcon(QIcon(str(BASE/'assets'/'truebeam-icon.png')))
        self.view=QWebEngineView(self);self.setCentralWidget(self.view)
        self.profile=QWebEngineProfile(self) if backend.home else QWebEngineProfile('TrueBeamSharedUI',self)
        home=(Path(backend.home).parent/'interface-profile') if backend.home else app_home()/'interface-profile';home.mkdir(parents=True,exist_ok=True)
        if not backend.home:self.profile.setPersistentStoragePath(str(home));self.profile.setCachePath(str(home/'cache'))
        self.page=Page(self.profile,self.view);self.page.messages=[];self.view.setPage(self.page)
        self.page.settings().setAttribute(QWebEngineSettings.PdfViewerEnabled,True)
        self.channel=QWebChannel(self.page);self.bridge=Bridge(self);self.channel.registerObject('truebeam',self.bridge);self.page.setWebChannel(self.channel)
        library=QFile(':/qtwebchannel/qwebchannel.js')
        if not library.open(QIODevice.ReadOnly):raise RuntimeError('The desktop interface bridge is missing.')
        script=QWebEngineScript();script.setName('TrueBeam desktop bridge');script.setInjectionPoint(QWebEngineScript.DocumentCreation)
        script.setWorldId(QWebEngineScript.MainWorld);script.setSourceCode(bytes(library.readAll()).decode()+'''
window.TRUEBEAM_DESKTOP=true;
window.truebeamNativeReady=new Promise(resolve=>new QWebChannel(qt.webChannelTransport,c=>resolve(c.objects.truebeam)));
window.truebeamNativeRequest=async(route,body)=>{
 const bridge=await window.truebeamNativeReady,id=crypto.randomUUID();
 return new Promise((resolve,reject)=>{
  const receive=(key,text)=>{if(key!==id)return;bridge.reply.disconnect(receive);const result=JSON.parse(text);if(result.error)reject(new Error(result.error));else resolve(result);};
  bridge.reply.connect(receive);bridge.request(route,body===undefined?'':JSON.stringify(body),id);
 });
};
''')
        self.page.scripts().insert(script)
        self.profile.downloadRequested.connect(self.download)
        self.timer=QTimer(self);self.timer.timeout.connect(self.connect_backend);self.timer.start(100)
        menu=self.menuBar().addMenu('Connection')
        def connect_shared():
            folder=QFileDialog.getExistingDirectory(self,'Select the shared TrueBeamApp folder')
            if folder:self.preferences.setValue('shared_folder',folder);QMessageBox.information(self,'Connection saved','Close and reopen the application to use this shared folder.')
        menu.addAction('Choose shared database folder…',connect_shared)
        menu.addAction('Use a local workspace on next launch',lambda:self.preferences.remove('shared_folder'))
    def task(self,fn,done,error=None):
        task=Task(fn);self.tasks.add(task)
        def finish(value):self.tasks.discard(task);done(value)
        def fail(message):
            self.tasks.discard(task);self.last_error=message
            if error:error(message)
            else:QMessageBox.warning(self,'TrueBeam Service Log',message)
        task.signals.done.connect(finish);task.signals.error.connect(fail);self.pool.start(task)
    def connect_backend(self):
        try:url,error=self.backend.ready.get_nowait()
        except queue.Empty:return
        self.timer.stop()
        if error:self.last_error=error;QMessageBox.warning(self,'TrueBeam Service Log',error);return
        self.api=Api(url);self.view.load(QUrl.fromLocalFile(str(BASE/'standalone'/'TrueBeam-Local.html')))
    def download(self,request):
        # Exports go straight to the Downloads folder; an existing file is never replaced.
        folder=Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or Path.home()/'Downloads');folder.mkdir(parents=True,exist_ok=True)
        path=folder/Path(request.suggestedFileName() or 'TrueBeam export').name;stem,suffix,n=path.stem,path.suffix,1
        while path.exists():path=folder/(stem+' ('+str(n)+')'+suffix);n+=1
        request.setDownloadDirectory(str(folder));request.setDownloadFileName(path.name)
        def finished():
            done=request.state()==QWebEngineDownloadRequest.DownloadState.DownloadCompleted
            self.page.runJavaScript('notice('+json.dumps(('Saved to Downloads: ' if done else 'Download failed: ')+str(path))+','+('false' if done else 'true')+')')
        request.isFinishedChanged.connect(finished)
        request.accept()
    def closeEvent(self,event):
        if self.backend.host and not self.backend.local:
            if QMessageBox.question(self,'Close shared host?','This computer is hosting the shared log. Closing it disconnects other users until the app is launched again. Close?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:event.ignore();return
        self.timer.stop();self.backend.stop.set();self.pool.waitForDone(150000);self.backend.thread.join(timeout=135)
        # Delete the page before its owning WebEngine profile.
        self.page.triggerAction(QWebEnginePage.Stop);event.accept()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test-report');parser.add_argument('--local',action='store_true')
    parser.add_argument('--shared-folder');parser.add_argument('--pick-folder',action='store_true');parser.add_argument('--picker-result')
    args=parser.parse_args()
    app=QApplication(sys.argv[:1]);app.setApplicationName('TrueBeam Service Log');app.setWindowIcon(QIcon(str(BASE/'assets'/'truebeam-icon.png')))
    if args.pick_folder:
        path=QFileDialog.getExistingDirectory(None,'Choose folder')
        if args.picker_result:Path(args.picker_result).write_text(path)
        return
    preferences=QSettings('UFHPTI','TrueBeam Service Log')
    test_dir=tempfile.TemporaryDirectory() if args.self_test_report else None
    folder='' if args.self_test_report else (args.shared_folder or ('' if args.local else preferences.value('shared_folder','')))
    if not folder and not args.local and not args.self_test_report and sys.platform=='win32' and REPORT_FOLDER.is_dir():folder=str(REPORT_FOLDER/'TrueBeamApp')
    backend=Backend(folder=folder,local=not bool(folder),home=Path(test_dir.name)/'db' if test_dir else None,unified=True)
    window=Window(backend,preferences);window.show()
    if args.self_test_report:
        deadline=time.monotonic()+60;result={}
        def evaluate():
            window.page.runJavaScript("JSON.stringify({ready:typeof state!=='undefined'&&!!state&&!!document.getElementById('add-fault'),ui:document.querySelector('meta[name=\"truebeam-ui-sha256\"]')?.content,tabs:[...document.querySelectorAll('.tab')].map(x=>x.textContent.trim()),dark:!!document.getElementById('theme-toggle')})",lambda value:result.update(json.loads(value)) if value else None)
        while time.monotonic()<deadline and not result.get('ready'):
            app.processEvents();evaluate();time.sleep(.05)
        assert result.get('ready') and result.get('dark') and len(result.get('tabs',[]))==2,(result,window.page.messages)
        window.api.request('add-fault',{'service_date':'2026-10-18T09:00','worker_initials':'AB','issue':'Unified UI launch test'})
        window.page.runJavaScript("poll().then(()=>{chooseTab('screenshots');document.getElementById('theme-toggle').click();window.__verified={rows:state.records.length,headers:document.getElementById('head').textContent,dark:document.documentElement.dataset.theme};})")
        checked={};deadline=time.monotonic()+15
        while time.monotonic()<deadline and not checked.get('rows'):
            app.processEvents();window.page.runJavaScript('JSON.stringify(window.__verified||{})',lambda value:checked.update(json.loads(value)) if value else None);time.sleep(.05)
        assert checked.get('rows')==1 and all(h in checked.get('headers','') for h in ('Varian Suggested Solution','Current Status','Final Resolution','Initials','Status')),(checked,window.page.messages)
        result['data_roundtrip']=True
        manifest=json.loads((BASE/'standalone'/'ui-manifest.json').read_text())
        assert result['ui']==manifest['ui_sha256']
        Path(args.self_test_report).write_text(json.dumps(dict(result,html_sha256=manifest['html_sha256'],platform=sys.platform,desktop_window=True)))
        window.grab().save(str(Path(args.self_test_report).with_suffix('.png')))
        window.close();app.processEvents();test_dir.cleanup();return
    sys.exit(app.exec())
if __name__=='__main__':main()
