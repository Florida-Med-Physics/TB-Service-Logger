import json, os, sqlite3, tempfile, threading, time, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from core import Engine, parse
from web_app import LocalServer, Service

class BrowserServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('reports','screens','data'):(self.root/name).mkdir()
        self.service=Service(self.root/'data')
        self.server=LocalServer(('127.0.0.1',0),self.service)
        self.service.thread.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.service.close()
        self.service.engine.db.close();self.service.reader.db.close();self.tmp.cleanup()
    def request(self,path,body=None,token=True,origin=None):
        headers={}
        if token:headers['X-Local-Token']=self.server.token
        if origin:headers['Origin']=origin
        if body is not None:headers['Content-Type']='application/json'
        return urlopen(Request(self.server.origin+path,data=None if body is None else json.dumps(body).encode(),headers=headers),timeout=5)
    def state(self):return json.load(self.request('/api/state'))
    def wait(self,predicate,timeout=12):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            value=self.state()
            if predicate(value):return value
            time.sleep(.1)
        self.fail('Expected state did not appear: '+str(self.state()))
    def test_api_authentication_and_local_origin(self):
        self.assertIn(b'Service Reports',self.request('/').read())
        with self.assertRaises(HTTPError) as error:self.request('/api/state',token=False)
        self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError) as error:self.request('/api/pause',{},origin='https://example.com')
        self.assertEqual(error.exception.code,403)
    def test_monitor_review_backup_and_restart(self):
        report=self.root/'reports'/'sample.txt'
        report.write_text('Error code: 420219\nIssue: synthetic fault\nWork performed: inspected')
        os.utime(report,(1,1))
        self.request('/api/configure',{'reports':str(self.root/'reports'),'screenshots':str(self.root/'screens')}).read()
        value=self.wait(lambda state:len(state['records'])==1)
        record=value['records'][0]
        job=json.load(self.request('/api/update',{'id':record['id'],'notes':'Reviewed locally','review':'Reviewed'}))
        value=self.wait(lambda state:state['records'][0]['review']=='Reviewed')
        self.assertEqual(value['records'][0]['issue'],'synthetic fault')
        self.assertEqual(value['records'][0]['notes'],'Reviewed locally')
        self.assertIn(b'synthetic fault',self.request('/api/source?id='+str(record['id'])).read())
        screenshot=self.root/'screens'/'fault.txt';screenshot.write_text('ID: 4016\nNAME: CTRL_OPEN_PATIENT_Q\nCAUSE: test');os.utime(screenshot,(1,1))
        value=self.wait(lambda state:len(state['records'])==2)
        self.assertEqual({r['kind'] for r in value['records']},{'reports','screenshots'})
        backup=self.request('/api/backup').read();self.assertTrue(backup.startswith(b'SQLite format 3'))
        path=self.root/'backup.sqlite3';path.write_bytes(backup)
        with sqlite3.connect(path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],2)
        self.assertTrue(self.request('/api/excel').read().startswith(b'PK'))
        reopened=Engine(self.root/'data');self.assertEqual(len(reopened.rows()),2);reopened.db.close()
    def test_scan_now_imports_a_new_file_while_paused(self):
        self.service.engine.configure({'reports':str(self.root/'reports'),'screenshots':str(self.root/'screens'),'output':str(self.root/'data'/'TrueBeam Service Log.xlsx')})
        self.service.engine.config['running']=False
        source=self.root/'reports'/'new.txt';source.write_text('Issue: newly copied while paused');os.utime(source,(1,1))
        self.request('/api/scan',{}).read()
        value=self.wait(lambda state:len(state['records'])==1)
        self.assertFalse(value['config']['running'])
    def test_missing_source_is_visible(self):
        with self.assertRaises(HTTPError) as error:self.request('/api/source?id=999')
        self.assertEqual(error.exception.code,400)

class ServiceParsingTests(unittest.TestCase):
    def test_report_fields(self):
        text='''Work Order Information
Work Order WO-004557496 Case 05777281
Service Resource Lawrence Paice   Purchase Order
Machine Information
Asset H192905
Work Order Comments
Subject BGM faults 222090, 210016
Closure Summary Inspected gun driver. Ordered replacement.
Follow Up Notables
Work Order Times
Malfunction Start : 9/7/2026 8:30 AM   Machine Release 9/8/2026 9:00 AM
Total Work Hours 0.75   Agreed Downtime 0.25
Work Order Line Items
Parts Installed
10004694807 MODULE, CONTROLLER 1 V - Varian Supplied
Quality Statements'''
        row=parse(text)
        for key,value in {'work_order':'WO-004557496','case_number':'05777281','machine':'H192905','engineer':'Lawrence Paice','work_hours':'0.75','downtime_hours':'0.25','fault_code':'222090','additional_codes':'210016'}.items():
            with self.subTest(key=key):self.assertEqual(row[key],value)
        self.assertIn('Inspected gun driver',row['work_performed'])
    def test_pmp_uses_print_date(self):
        row=parse('CHECKLISTCHECKLIST SHEETSHEET\nACCEPTANCEACCEPTANCE DATE:DATE: Dec/20/2016Dec/20/2016\nPRINTPRINT DATE:DATE: Jun/28/2022Jun/28/2022\nPCSN: H192905')
        self.assertEqual(row['service_date'],'Jun/28/2022')
        self.assertEqual(row['document_type'],'PMP checklist')
    def test_legacy_missing_downtime_stays_blank(self):
        text='''Work Order Information
Case Number 02581822 Work Order Number WO-02525001
Field Engineer Marcelo Luna
Problem Description
BGM fault 210016
Work Performed Comments
Rebooted BGM.
Follow Up Comments
Work Order Times
Time In   Time Out   Malfunction Start   Machine Release Time
12/27/2019 07:30   12/27/2019 14:15   12/27/2019 07:12   12/27/2019 14:00
Total Travel Hours   Total Work Hours   Total Site Hours   Agreed Downtime
0.00   1.75   1.75
Work Details'''
        row=parse(text);self.assertEqual(row['work_hours'],'1.75');self.assertEqual(row['downtime_hours'],'')
    def test_nested_folders_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'nested').mkdir();engine=Engine(root/'data')
            with self.assertRaises(ValueError):engine.configure({'reports':str(root),'screenshots':str(root/'nested'),'output':str(root/'log.xlsx')})
            engine.db.close()
if __name__=='__main__':unittest.main()
