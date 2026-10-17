import csv,json,os,sqlite3,tempfile,threading,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from application_host import SharedService,Server,Conflict,DEFAULTS
from live_report import publish_report
class SharedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for name in ('reports','screens','network'):(self.root/name).mkdir()
  self.defaults={'reports':str(self.root/'reports'),'screenshots':str(self.root/'screens'),'output':str(self.root/'network'/'Report.xlsx'),'running':False}
  self.service=SharedService(self.root/'home',defaults=self.defaults,shared_dir=self.root/'network')
  self.server=Server(('127.0.0.1',0),self.service);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.url='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.service.close();self.tmp.cleanup()
 def call(self,route,body=None,token=True):
  return urlopen(Request(self.url+'/api/'+route,data=None if body is None else json.dumps(body).encode(),headers={'X-Local-Token':self.service.token if token else '',**({'Content-Type':'application/json'} if body is not None else {})}),timeout=15)
 def fault(self):
  return json.load(self.call('add-fault',{'service_date':'2026-10-16T12:00','worker_initials':'BK','issue':'MLC fault'}))['id']
 def test_two_clients_merge_different_fields_and_reject_same_field_conflict(self):
  rid=self.fault()
  with ThreadPoolExecutor() as pool:
   results=list(pool.map(lambda p:json.load(self.call('inline-update',p)),[
    {'id':rid,'field':'work_performed','value':'Reset connection','expected':''},
    {'id':rid,'field':'fault_code','value':'420219','expected':''}]))
  self.assertTrue(all(r['ok'] for r in results))
  with self.assertRaises(HTTPError) as error:self.call('inline-update',{'id':rid,'field':'work_performed','value':'Old edit','expected':''})
  self.assertEqual(error.exception.code,409)
  r=json.load(self.call('state'))['records'][0];self.assertEqual(r['work_performed'],'Reset connection');self.assertEqual(r['fault_code'],'420219')
 def test_shared_backup_and_paths_survive_handoff(self):
  rid=self.fault();backup=self.root/'network'/'shared-data.sqlite3';self.assertTrue(backup.exists())
  with sqlite3.connect(backup) as db:self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],1)
  # Close the inspection handle on Windows.
  db.close()
  self.assertEqual(json.loads((self.root/'network'/'settings.json').read_text())['reports'],self.defaults['reports'])
 def test_report_publication_never_writes_open_workbook(self):
  self.fault();self.service.tick();output=Path(self.defaults['output']);before=output.read_bytes();stamp=output.stat().st_mtime_ns
  rid=self.service.state()['records'][0]['id'];self.service.update({'id':rid,'field':'work_performed','value':'New fix','expected':''})
  with open(output,'rb') as held:
   publish_report(self.service.state()['records'],output)
   self.assertEqual(held.read(),before)
  self.assertEqual(output.stat().st_mtime_ns,stamp)
  feed=output.parent/(output.stem+'_data')/'FaultReports.csv'
  self.assertIn('New fix',feed.read_text(encoding='utf-8-sig'))
 def test_authentication_and_cross_origin(self):
  with self.assertRaises(HTTPError) as error:self.call('state',token=False)
  self.assertEqual(error.exception.code,403)
  request=Request(self.url+'/api/add-fault',data=b'{}',headers={'X-Local-Token':self.service.token,'Origin':'https://example.com','Content-Type':'application/json'})
  with self.assertRaises(HTTPError) as error:urlopen(request)
  self.assertEqual(error.exception.code,403)
 def test_tenure_defaults(self):
  self.assertEqual(DEFAULTS['reports'],r'U:\QA\SystemQA\LINAC QA\TrueBeam\Service reports')
  self.assertEqual(DEFAULTS['screenshots'],r'W:\Varian\Transfer\TDS\H192905\PrintScreen')
if __name__=='__main__':unittest.main()
