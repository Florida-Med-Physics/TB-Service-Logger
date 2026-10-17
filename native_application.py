"""Native Qt desktop interface. No HTML renderer, browser, or WebView."""
import argparse, base64, csv, hashlib, json, ntpath, os, queue, re, shutil, sys, tempfile, threading, time, uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QRunnable, QThreadPool, QSettings, QUrl
from PySide6.QtGui import QIcon, QPixmap, QColor, QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
 QPushButton,QLineEdit,QComboBox,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,
 QAbstractItemView,QDialog,QFormLayout,QDialogButtonBox,QPlainTextEdit,QFileDialog,QMessageBox,
 QCheckBox,QListWidget)
from application_host import SharedService, Server, DEFAULTS, default_home, BASE
from shared_application import Lease, connection_url, app_home, REPORT_FOLDER
from report_export import date_value
from core import clean_event_time

REPORT_COLUMNS=[('service_date','Start / release',11),('work_order','Work order / case',10),
 ('category','Category',8),('issue','Subject',10),('fault_code','Error codes',7),
 ('work_performed','Summary of work',15),('parts_installed','Parts installed',10),
 ('engineer','Engineer',9),('work_hours','Hours',4),('service_status','Status',7),('sources','Service report',9)]
FAULT_COLUMNS=[('service_date','Event time',11),('fault_code','Error codes',8),('fault_name','Fault name / severity',13),
 ('issue','Error Details',20),('suggestions','SUGGESTED SOLUTION',18),
 ('work_performed','Resolution',18),('worker_initials','Initials',5),('sources','Screenshot',12)]

def display_path(value):
    text=str(value or '').strip()
    if re.match(r'^[A-Za-z]:',text) or text.startswith(('\\\\','//')):
        return ntpath.normpath(text)
    return text


class Signals(QObject):
    done=Signal(object);error=Signal(str)
class Task(QRunnable):
    def __init__(self,fn):
        super().__init__();self.fn=fn;self.signals=Signals()
    def run(self):
        try:self.signals.done.emit(self.fn())
        except Exception as exc:self.signals.error.emit(str(exc))

class Api:
    def __init__(self,url):
        parts=urlsplit(url);self.base=parts.scheme+'://'+parts.netloc;self.token=parts.fragment
        self.local=parts.hostname in ('127.0.0.1','localhost')
    def request(self,route,payload=None,raw=False):
        request=Request(self.base+'/api/'+route,data=None if payload is None else json.dumps(payload).encode(),
                        headers={'X-Local-Token':self.token,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=150) as response:
                return response.read() if raw else json.load(response)
        except HTTPError as exc:
            try:message=json.loads(exc.read()).get('error',str(exc))
            except Exception:message=str(exc)
            raise ValueError(message) from None

class Backend:
    """Own the host lease and service on one dedicated thread."""
    def __init__(self,folder=None,local=False,home=None,defaults=None):
        self.ready=queue.Queue();self.stop=threading.Event();self.host=False
        self.folder=folder;self.local=local;self.home=home;self.defaults=defaults
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        service=None;server=None;lease=None
        try:
            if self.local:
                home=Path(self.home or (app_home()/'native-local'))
                service=SharedService(home,defaults=self.defaults or {'reports':'','screenshots':'','output':'','running':False})
                address='127.0.0.1'
            else:
                folder=Path(self.folder);folder.mkdir(parents=True,exist_ok=True)
                try:lease=Lease(folder/'host.lock')
                except OSError:
                    for _ in range(20):
                        if self.stop.wait(.5):return
                        try:self.ready.put((connection_url(folder),None));return
                        except Exception:pass
                    raise ValueError('The shared host is unavailable. Keep the host computer running and check the network connection.')
                if sys.platform!='win32':
                    lease.close();lease=None
                    self.ready.put((connection_url(folder),None));return
                home=default_home();home.mkdir(parents=True,exist_ok=True)
                durable=folder/'shared-data.sqlite3'
                if durable.exists():
                    for suffix in ('-wal','-shm'):(home/('service-log.sqlite3'+suffix)).unlink(missing_ok=True)
                    shutil.copy2(durable,home/'service-log.sqlite3')
                service=SharedService(home,shared_dir=folder);address='0.0.0.0'
            self.host=True
            try:server=Server((address,8766 if not self.local else 0),service)
            except OSError:server=Server((address,0),service)
            if not self.local:
                import socket
                metadata={'host':socket.gethostname(),'port':server.server_port,'token':service.token}
                fd,tmp=tempfile.mkstemp(dir=self.folder,suffix='.json');os.close(fd)
                Path(tmp).write_text(json.dumps(metadata));os.replace(tmp,Path(self.folder)/'connection.json')
            service.thread.start();server.timeout=.3
            self.ready.put(('http://127.0.0.1:'+str(server.server_port)+'/#'+service.token,None))
            while not self.stop.is_set():server.handle_request()
        except Exception as exc:self.ready.put((None,str(exc)))
        finally:
            if server:server.server_close()
            if service:service.close()
            if lease:lease.close()

def cell_value(record,key):
    if key=='sources':return '\n'.join(Path(s.get('path','')).name for s in record.get('sources',[])) or '-'
    if key=='fault_code':
        return '\n'.join(dict.fromkeys(re.findall(r'\b\d{4,7}\b',str(record.get('fault_code',''))+' '+str(record.get('additional_codes',''))))) or '-'
    if key=='service_date':
        if record.get('kind')=='screenshots':
            value=clean_event_time(record.get(key,''));parsed=date_value(value)
            return parsed.strftime('%m/%d/%Y\n%I:%M:%S %p') if hasattr(parsed,'strftime') else (value or '-')
        value=record.get(key,'') or '-'
        if record.get('machine_release'):value+='\nRelease: '+record['machine_release']
        return value
    if key=='work_order':
        return (record.get(key,'') or '-')+('\nCase '+record['case_number'] if record.get('case_number') else '')
    if key=='fault_name':
        return (record.get(key,'') or '-')+('\n'+record['severity'] if record.get('severity') else '')
    return str(record.get(key,'') or ('Closure documented' if key=='service_status' else '-'))

class Window(QMainWindow):
    def __init__(self,backend,settings=None):
        super().__init__();self.backend=backend;self.api=None;self.state={};self.records=[]
        self.preferences=settings or QSettings('UFHPTI','TrueBeam Service Log')
        self.pool=QThreadPool(self);self.pending=set();self.polling=False;self.editing=False;self.signature=None
        self.setWindowTitle('TrueBeam Service Log');self.setWindowIcon(QIcon(str(BASE/'assets'/'truebeam-icon.png')))
        self.resize(1540,960);self.setMinimumSize(1050,680)
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        header=QWidget();header.setObjectName('header');h=QHBoxLayout(header);h.setContentsMargins(24,16,24,16)
        logo=QLabel();logo.setPixmap(QPixmap(str(BASE/'assets'/'truebeam-icon.png')).scaled(72,72,Qt.KeepAspectRatio,Qt.SmoothTransformation));h.addWidget(logo)
        title=QVBoxLayout();eyebrow=QLabel('UFHPTI  /  PHYSICS');eyebrow.setObjectName('eyebrow')
        title.addWidget(eyebrow);heading=QLabel('TrueBeam Service Log');heading.setObjectName('title');title.addWidget(heading);h.addLayout(title);h.addStretch()
        self.dark=QCheckBox('Dark mode');self.dark.setChecked(self.preferences.value('dark',False,type=bool))
        self.dark.toggled.connect(self.theme);h.addWidget(self.dark);layout.addWidget(header)
        accent=QWidget();accent.setFixedHeight(4);accent.setObjectName('accent');layout.addWidget(accent)
        body=QWidget();b=QVBoxLayout(body);b.setContentsMargins(22,16,22,14);b.setSpacing(12);layout.addWidget(body,1)
        tools=QHBoxLayout()
        for label,callback in [('Folder settings',self.settings_dialog),('Scan now',self.scan),('Import files',self.import_files),('Import details',self.import_details)]:
            tools.addWidget(self.button(label,callback))
        tools.addStretch();tools.addWidget(self.button('Add fault',self.add_fault,True));tools.addWidget(self.button('Export Report',self.export_report));b.addLayout(tools)
        cards=QHBoxLayout();self.counts=[]
        for name in ('SERVICE REPORTS','FAULT REPORTS','REPORT DATA'):
            card=QWidget();card.setObjectName('card');cl=QVBoxLayout(card);cl.setContentsMargins(18,12,18,12)
            cap=QLabel(name);cap.setObjectName('caption');cl.addWidget(cap);value=QLabel('—');value.setObjectName('metric');cl.addWidget(value);self.counts.append(value);cards.addWidget(card)
        b.addLayout(cards)
        self.tabs=QTabWidget();self.tables={};self.tab_tools={};b.addWidget(self.tabs,1)
        for kind,title_text,columns in [('reports','Service Reports',REPORT_COLUMNS),('screenshots','Fault Reports',FAULT_COLUMNS)]:
            page=QWidget();pl=QVBoxLayout(page);pl.setContentsMargins(12,12,12,8)
            bar=QHBoxLayout();search=QLineEdit();search.setPlaceholderText('Search work order, error code, or description…')
            search.textChanged.connect(self.render);bar.addWidget(search,1)
            category=QComboBox();category.addItem('All categories');category.currentTextChanged.connect(self.render);bar.addWidget(category)
            bar.addWidget(self.button('Download '+('service' if kind=='reports' else 'fault')+' table',lambda checked=False,k=kind:self.download_table(k),True));pl.addLayout(bar)
            table=QTableWidget(0,len(columns));table.setHorizontalHeaderLabels([c[1] for c in columns]);table.setAlternatingRowColors(True)
            table.verticalHeader().hide();table.verticalHeader().setDefaultSectionSize(76)
            table.setShowGrid(False);table.setWordWrap(True);table.setTextElideMode(Qt.ElideRight)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection);table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed);table.horizontalHeader().setMinimumSectionSize(25)
            table.horizontalHeader().setSectionsClickable(True);table.horizontalHeader().setSortIndicatorShown(True)
            table.horizontalHeader().sectionClicked.connect(lambda col,k=kind:self.sort(k,col))
            table.cellDoubleClicked.connect(lambda row,col,k=kind:self.edit_cell(k,row,col));pl.addWidget(table,1)
            hint=QLabel('Double-click any field to view its full text and edit. Double-click a document to open it.');hint.setObjectName('caption');pl.addWidget(hint)
            self.tabs.addTab(page,title_text);self.tables[kind]=table
            self.tab_tools[kind]={'search':search,'category':category,'sort':(0,True),'rows':[],'columns':columns}
        self.message=QLabel('Opening application…');self.message.setWordWrap(True);self.message.setObjectName('caption');b.addWidget(self.message)
        self.tabs.currentChanged.connect(lambda _:QTimer.singleShot(0,self.fit_columns));self.theme();self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(150)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'tables'):QTimer.singleShot(0,self.fit_columns)
    def fit_columns(self):
        for kind,table in self.tables.items():
            columns=self.tab_tools[kind]['columns'];total=sum(c[2] for c in columns);available=max(1,table.viewport().width())
            widths=[int(available*c[2]/total) for c in columns];widths[-1]+=available-sum(widths)
            for i,width in enumerate(widths):table.setColumnWidth(i,width)
    def button(self,label,callback,primary=False):
        button=QPushButton(label);button.clicked.connect(callback)
        if primary:button.setObjectName('primary')
        return button
    def theme(self):
        dark=self.dark.isChecked();self.preferences.setValue('dark',dark)
        bg='#101d2d' if dark else '#f2f4f8';card='#203545' if dark else '#ffffff';fg='#deebf4' if dark else '#163963'
        muted='#aebfce' if dark else '#63778c';line='#385266' if dark else '#dce3ed';alt='#243b4d' if dark else '#f6f8fb'
        self.setStyleSheet(f"""
          QWidget {{font-family: 'Segoe UI', 'Arial'; font-size:13px; color:{fg};}}
          QMainWindow,QDialog {{background:{bg};}}
          QWidget#header {{background:#123c70;}} QWidget#header QLabel,QWidget#header QCheckBox {{color:white;}}
          QLabel#title {{font-size:26px;font-weight:700;}} QLabel#eyebrow {{color:#ff9757;font-size:11px;font-weight:700;}}
          QWidget#accent,QPushButton#primary {{background:#ff7020;}}
          QWidget#card {{background:{card};border:1px solid {line};border-radius:12px;}}
          QLabel#metric {{font-size:25px;font-weight:700;}} QLabel#caption {{color:{muted};font-size:11px;}}
          QPushButton {{background:{card};border:1px solid {line};border-radius:6px;padding:9px 13px;font-weight:600;}}
          QPushButton:hover {{border-color:#ff7020;}} QPushButton:disabled {{color:{muted};}}
          QPushButton#primary {{border:1px solid #ff7020;color:#12345b;}}
          QLineEdit,QComboBox,QPlainTextEdit,QListWidget {{background:{card};border:1px solid {line};border-radius:5px;padding:8px;}}
          QTabWidget::pane {{border:1px solid {line};background:{card};border-radius:8px;}}
          QTabBar::tab {{padding:13px 22px;background:{bg};font-weight:700;}}
          QTabBar::tab:selected {{background:{card};border-bottom:3px solid #ff7020;}}
          QTableWidget {{background:{card};alternate-background-color:{alt};border:none;selection-background-color:#c7e1f4;selection-color:#12345b;}}
          QTableWidget::item {{padding:7px;border-bottom:1px solid {line};}}
          QHeaderView::section {{background:{alt};color:{muted};border:none;border-bottom:1px solid {line};padding:10px 4px;font-size:10px;font-weight:700;}}
          QScrollBar:vertical {{width:10px;background:{bg};}} QScrollBar::handle:vertical {{background:{line};min-height:30px;border-radius:4px;}}
        """)
    def task(self,fn,done=None,error=None):
        task=Task(fn);self.pending.add(task)
        def finish(value):
            self.pending.discard(task)
            if done:done(value)
        def failed(message):
            self.pending.discard(task)
            if error:error(message)
            else:self.alert(message)
        task.signals.done.connect(finish);task.signals.error.connect(failed);self.pool.start(task)
    def alert(self,message):QMessageBox.warning(self,'TrueBeam Service Log',message)
    def tick(self):
        if self.api is None:
            try:url,error=self.backend.ready.get_nowait()
            except queue.Empty:return
            if error:
                self.timer.stop();self.message.setText(error);self.alert(error);return
            self.api=Api(url);self.timer.setInterval(2000)
        if self.polling or self.editing:return
        self.polling=True
        def done(state):
            self.polling=False
            if self.editing:return
            self.state=state;self.records=state['records'];self.message.setText(state.get('message',''))
            self.counts[0].setText(str(sum(r['kind']=='reports' for r in self.records)))
            self.counts[1].setText(str(sum(r['kind']=='screenshots' for r in self.records)))
            self.counts[2].setText(state.get('last_report') or 'Waiting for report folder')
            signature=json.dumps(self.records,sort_keys=True)
            if signature!=self.signature:
                self.signature=signature
                for kind,tools in self.tab_tools.items():
                    combo=tools['category'];old=combo.currentText();combo.blockSignals(True);combo.clear();combo.addItem('All categories')
                    combo.addItems(sorted(set(r.get('category','') for r in self.records if r['kind']==kind and r.get('category'))));combo.setCurrentIndex(max(0,combo.findText(old)));combo.blockSignals(False)
                self.render()
        def error(message):self.polling=False;self.message.setText('Connection: '+message)
        self.task(lambda:self.api.request('state'),done,error)
    def sort(self,kind,column):
        tools=self.tab_tools[kind];old,descending=tools['sort'];tools['sort']=(column,not descending if old==column else False);self.render()
    def render(self,*_):
        for kind,table in self.tables.items():
            tools=self.tab_tools[kind];query=tools['search'].text().casefold();category=tools['category'].currentText()
            rows=[r for r in self.records if r['kind']==kind and (not query or query in json.dumps(r,ensure_ascii=False).casefold())
                  and (category=='All categories' or not category or r.get('category')==category)]
            column,descending=tools['sort'];key=tools['columns'][column][0]
            def order(r):
                value=cell_value(r,key)
                if key=='service_date':
                    value=date_value(r.get(key,''))
                    return (0,value.isoformat()) if hasattr(value,'isoformat') else (1,str(value))
                if key=='work_hours':
                    try:return float(r.get(key) or 0)
                    except ValueError:return 0.
                return value.casefold()
            rows.sort(key=order,reverse=descending);tools['rows']=rows
            scroll=table.verticalScrollBar().value();table.setUpdatesEnabled(False);table.setRowCount(len(rows))
            for i,record in enumerate(rows):
                for j,(key,label,width) in enumerate(tools['columns']):
                    text=cell_value(record,key);item=QTableWidgetItem(text);item.setToolTip(text)
                    item.setTextAlignment(Qt.AlignLeft|Qt.AlignTop)
                    if key=='sources':item.setForeground(QColor('#4589bd'))
                    table.setItem(i,j,item)
                codes=cell_value(record,'fault_code').count('\n')+1
                table.setRowHeight(i,max(76,min(160,22+codes*18)))
            table.horizontalHeader().setSortIndicator(column,Qt.DescendingOrder if descending else Qt.AscendingOrder)
            table.setUpdatesEnabled(True);table.verticalScrollBar().setValue(scroll)
            self.tabs.setTabText(0 if kind=='reports' else 1,('Service Reports' if kind=='reports' else 'Fault Reports')+'  '+str(len(rows)))
    def edit_cell(self,kind,row,col):
        record=dict(self.tab_tools[kind]['rows'][row]);key,label,_=self.tab_tools[kind]['columns'][col]
        if key=='service_status':record[key]=record.get(key) or record.get('review','')
        if key=='sources':return self.sources(record)
        self.editing=True
        dialog=QDialog(self);dialog.setWindowTitle(label);dialog.resize(620,380);form=QFormLayout(dialog)
        keys=[key]
        if key=='service_date' and kind=='reports':keys.append('machine_release')
        if key=='work_order':keys.append('case_number')
        if key=='fault_name':keys.append('severity')
        if key=='fault_code':keys.append('additional_codes')
        editors={}
        for field in keys:
            editor=QPlainTextEdit(str(record.get(field,'') or ''));editor.setMinimumHeight(65);editors[field]=editor
            form.addRow({'machine_release':'Release','case_number':'Case number','severity':'Severity','additional_codes':'Additional error codes'}.get(field,label),editor)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);form.addRow(buttons);buttons.rejected.connect(dialog.reject)
        def save():
            changes=[{'id':record['id'],'field':field,'value':editor.toPlainText(),'expected':str(record.get(field,'') or '')} for field,editor in editors.items() if editor.toPlainText()!=str(record.get(field,'') or '')]
            if not changes:dialog.accept();return
            buttons.setEnabled(False)
            def work():
                for change in changes:self.api.request('inline-update',change)
            def failed(message):buttons.setEnabled(True);self.alert(message)
            self.task(work,lambda _:dialog.accept(),failed)
        buttons.accepted.connect(save);dialog.exec();self.editing=False;self.tick()
    def sources(self,record):
        sources=record.get('sources',[])
        if not sources:self.alert('No source file is attached to this entry.');return
        if len(sources)==1:return self.open_source(sources[0])
        dialog=QDialog(self);dialog.setWindowTitle('Attached files');dialog.resize(600,300);layout=QVBoxLayout(dialog);items=QListWidget();items.addItems([Path(s.get('path','')).name for s in sources]);layout.addWidget(items)
        items.itemDoubleClicked.connect(lambda item:self.open_source(sources[items.row(item)]));dialog.exec()
    def open_source(self,source):
        name=Path(str(source['path']).replace('\\','/')).name
        folder=app_home()/'opened-files';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(str(source['id']).replace(':','-')+'-'+name)
        def done(data):
            path.write_bytes(data)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):self.alert('No application is registered to open this file.')
        self.task(lambda:self.api.request('source?id='+str(source['id']),raw=True),done)
    def scan(self):
        if self.api:self.task(lambda:self.api.request('scan',{}),lambda _:self.tick())
    def import_details(self):
        dialog=QDialog(self);dialog.setWindowTitle('Import details');dialog.resize(760,400);layout=QVBoxLayout(dialog)
        text=QPlainTextEdit();text.setReadOnly(True)
        details=[str(r.get('issue') or r.get('path') or r.get('id'))+'\n'+str(r['error']) for r in self.records if r.get('error')]
        for skipped in self.state.get('excluded',[]):
            names=', '.join(Path(s.get('path','')).name for s in skipped.get('sources',[]))
            details.append(names+'\n'+skipped['reason']+('\n'+skipped['error'] if skipped.get('error') else ''))
        text.setPlainText('\n\n'.join(details) or 'No import errors or skipped files.')
        layout.addWidget(text);dialog.exec()
    def import_files(self):
        if not self.api:return
        files,_=QFileDialog.getOpenFileNames(self,'Import reports or screenshots','','Reports and screenshots (*.pdf *.docx *.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff *.txt)')
        if not files:return
        self.message.setText('Importing files…')
        def work():
            results=[]
            for filename in files:
                path=Path(filename)
                if path.stat().st_size>25000000:raise ValueError(path.name+' is over 25 MB.')
                results.append(self.api.request('upload',{'name':path.name,'data':base64.b64encode(path.read_bytes()).decode()}))
            return results
        def done(results):
            errors=[r.get('error') for r in results if r.get('error')]
            if errors:self.alert('\n'.join(errors))
            self.tick()
        self.task(work,done)
    def settings_dialog(self):
        if not self.api:return
        dialog=QDialog(self);dialog.setWindowTitle('Folder settings');dialog.resize(760,280);form=QFormLayout(dialog)
        fields={};config=self.state.get('config',{})
        for key,label in [('reports','Service report folder'),('screenshots','Screenshot folder'),('output','Excel report')]:
            row=QWidget();line=QHBoxLayout(row);line.setContentsMargins(0,0,0,0);edit=QLineEdit(display_path(config.get(key,'')));line.addWidget(edit,1)
            def browse(checked=False,k=key,e=edit):
                if k=='output':path,_=QFileDialog.getSaveFileName(dialog,'Excel report',e.text(),'Excel workbook (*.xlsx)')
                else:path=QFileDialog.getExistingDirectory(dialog,'Select folder',e.text())
                if path:e.setText(display_path(path))
            button=self.button('Choose…',browse);line.addWidget(button);form.addRow(label,row);fields[key]=edit
        info=QLabel('Folder locations are remembered. Report data updates every minute.');info.setWordWrap(True);form.addRow(info)
        running=QCheckBox('Monitor folders');running.setChecked(config.get('running',False));form.addRow(running)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);form.addRow(buttons);buttons.rejected.connect(dialog.reject)
        if not self.api.local:
            for edit in fields.values():edit.setReadOnly(True)
            buttons.button(QDialogButtonBox.Save).setEnabled(False);info.setText('Manage shared folder locations on the host computer.')
        def save():
            payload={k:display_path(e.text()) for k,e in fields.items()};payload['running']=running.isChecked();buttons.setEnabled(False)
            self.task(lambda:self.api.request('configure',payload),lambda _:dialog.accept(),lambda error:(buttons.setEnabled(True),self.alert(error)))
        buttons.accepted.connect(save);dialog.exec();self.tick()
    def add_fault(self):
        if not self.api:return
        self.editing=True;dialog=QDialog(self);dialog.setWindowTitle('Add fault');dialog.resize(660,580);form=QFormLayout(dialog);fields={}
        for key,label in [('service_date','Event date / time'),('worker_initials','Initials'),('fault_code','Error code'),('fault_name','Fault name'),('issue','Error Details'),('work_performed','Resolution')]:
            edit=QPlainTextEdit() if key in ('issue','work_performed') else QLineEdit()
            if key=='service_date':edit.setText(time.strftime('%Y-%m-%dT%H:%M'))
            form.addRow(label,edit);fields[key]=edit
        files=[];filelabel=QLabel('No screenshots attached')
        def attach():
            names,_=QFileDialog.getOpenFileNames(dialog,'Attach screenshots','','Images (*.png *.jpg *.jpeg *.bmp *.webp)')
            files[:]=names;filelabel.setText(', '.join(Path(n).name for n in names) or 'No screenshots attached')
        form.addRow(self.button('Attach screenshots',attach),filelabel)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);form.addRow(buttons);buttons.rejected.connect(dialog.reject);request_id=str(uuid.uuid4())
        def save():
            payload={k:(e.toPlainText() if isinstance(e,QPlainTextEdit) else e.text()).strip() for k,e in fields.items()}
            if not all(payload[k] for k in ('service_date','worker_initials','issue')):self.alert('Enter an event date, initials, and Error Details.');return
            buttons.setEnabled(False)
            def work():
                attachments=[]
                for filename in files:
                    path=Path(filename)
                    if path.stat().st_size>20000000:raise ValueError('Each screenshot must be under 20 MB.')
                    attachments.append({'name':path.name,'data':base64.b64encode(path.read_bytes()).decode()})
                return self.api.request('add-fault',dict(payload,attachments=attachments,requestId=request_id))
            self.task(work,lambda _:dialog.accept(),lambda error:(buttons.setEnabled(True),self.alert(error)))
        buttons.accepted.connect(save);dialog.exec();self.editing=False;self.tick()
    def download_table(self,kind):
        tools=self.tab_tools[kind];filename,_=QFileDialog.getSaveFileName(self,'Download table',('ServiceReports' if kind=='reports' else 'FaultReports')+'.csv','CSV (*.csv)')
        if not filename:return
        try:
            with open(filename,'w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.writer(stream);writer.writerow([c[1] for c in tools['columns']])
                for record in tools['rows']:
                    values=[cell_value(record,c[0]) for c in tools['columns']]
                    writer.writerow(["'"+v if v[:1] in ('=','+','-','@') and v!='-' else v for v in values])
            self.message.setText('Table saved: '+filename)
        except OSError as exc:self.alert(str(exc))
    def export_report(self):
        if not self.api:return
        filename,_=QFileDialog.getSaveFileName(self,'Export Report','TrueBeam_Service_Log.xlsx','Excel workbook (*.xlsx)')
        if not filename:return
        configured=self.state.get('config',{}).get('output','')
        if configured and os.path.normcase(str(Path(filename).resolve()))==os.path.normcase(str(Path(configured).resolve())):
            self.task(lambda:self.api.request('export',{}),lambda _:self.message.setText('Report data refresh requested. The existing workbook stays open and is not replaced.'))
            return
        def done(data):
            try:
                from live_report import atomic_write
                atomic_write(Path(filename),data);self.message.setText('Report exported: '+filename)
            except OSError as exc:self.alert(str(exc))
        def work():
            from live_report import create_live_workbook
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'Report.xlsx'
                create_live_workbook(self.api.request('state')['records'],path,[],live=False)
                return path.read_bytes()
        self.task(work,done)
    def closeEvent(self,event):
        if self.backend.host and not self.backend.local:
            result=QMessageBox.question(self,'Close shared host?','This computer is hosting the shared log. Closing it disconnects other users until the app is launched again. Close the application?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if result!=QMessageBox.Yes:event.ignore();return
        self.timer.stop();self.backend.stop.set();self.pool.waitForDone(150000);self.backend.thread.join(timeout=135);event.accept()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--local',action='store_true');parser.add_argument('--shared-folder')
    parser.add_argument('--self-test-report');args=parser.parse_args()
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('UFHPTI.TrueBeam.ServiceLog')
    app=QApplication(sys.argv[:1]);app.setStyle('Fusion');app.setWindowIcon(QIcon(str(BASE/'assets'/'truebeam-icon.png')))
    preferences=QSettings('UFHPTI','TrueBeam Service Log')
    if args.self_test_report:
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);backend=Backend(local=True,home=home/'db')
            url,error=backend.ready.get(timeout=20)
            if error:raise RuntimeError(error)
            backend.ready.put((url,None));window=Window(backend,QSettings(str(home/'prefs.ini'),QSettings.IniFormat));window.show()
            deadline=time.monotonic()+15
            while (not window.api or not window.state) and time.monotonic()<deadline:app.processEvents();time.sleep(.02)
            assert window.state and window.tabs.count()==2 and not window.windowIcon().isNull()
            assert not any(c[0]=='service_status' for c in FAULT_COLUMNS)
            backend.stop.set();window.timer.stop();window.pool.waitForDone();backend.thread.join(timeout=10)
            window.grab().save(str(Path(args.self_test_report).with_suffix('.png')))
            Path(args.self_test_report).write_text(json.dumps({'native':True,'browser':False,'tabs':window.tabs.count(),'icon':True,'platform':sys.platform,'loaded_ui_modules':[name for name in ('PySide6.QtWidgets','tkinter','_tkinter') if name in sys.modules]}))
        return
    folder=args.shared_folder
    if not args.local and not folder:
        folder=preferences.value('shared_folder','')
        if not folder and sys.platform=='win32' and REPORT_FOLDER.is_dir():folder=str(REPORT_FOLDER/'TrueBeamApp')
    backend=Backend(folder=folder,local=not bool(folder))
    window=Window(backend,preferences)
    if not folder:
        menu=window.menuBar().addMenu('Connection')
        def connect():
            path=QFileDialog.getExistingDirectory(window,'Select the shared TrueBeamApp folder')
            if path:preferences.setValue('shared_folder',path);QMessageBox.information(window,'Connection saved','Close and reopen the app to connect to this shared folder.')
        menu.addAction('Connect to shared UFHPTI log…',connect)
        window.message.setText('Local workspace. Use Folder settings to monitor folders, or Connection to join the shared log.')
    window.show();sys.exit(app.exec())
if __name__=='__main__':main()