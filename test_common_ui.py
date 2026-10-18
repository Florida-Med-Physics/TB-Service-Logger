import hashlib,json,tempfile,threading,unittest
from pathlib import Path
from urllib.request import urlopen
from application_host import SharedService,Server
ROOT=Path(__file__).resolve().parent
class CommonInterfaceTests(unittest.TestCase):
 def test_download_and_desktop_manifest_match(self):
  manifest=json.loads((ROOT/'standalone/ui-manifest.json').read_text())
  self.assertEqual(manifest['ui_sha256'],hashlib.sha256((ROOT/'index.html').read_text(encoding='utf-8').encode()).hexdigest())
  page=(ROOT/'standalone/TrueBeam-Local.html').read_bytes()
  self.assertEqual(manifest['html_sha256'],hashlib.sha256(page).hexdigest())
  text=page.decode()
  self.assertIn('Boolean(window.TRUEBEAM_DESKTOP)',text)
  self.assertIn('if(USE_SHARED)initShared();else initStandalone();',text)
  self.assertIn((ROOT/'ui-policy.js').read_text().strip(),(ROOT/'index.html').read_text())
 def test_host_serves_the_identical_downloadable_html(self):
  with tempfile.TemporaryDirectory() as directory:
   service=SharedService(directory,defaults={'reports':'','screenshots':'','output':'','running':False})
   service.unified_html=True;server=Server(('127.0.0.1',0),service)
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    with urlopen('http://127.0.0.1:'+str(server.server_port)+'/') as response:body=response.read()
    self.assertEqual(body,(ROOT/'standalone/TrueBeam-Local.html').read_bytes())
   finally:server.shutdown();server.server_close();service.close()
if __name__=='__main__':unittest.main()
