"""Build one HTML artifact for browser, Windows, and Mac interfaces."""
from pathlib import Path
import argparse,base64,json,re,hashlib,html
parser=argparse.ArgumentParser()
parser.add_argument('--node-modules');parser.add_argument('--english');parser.add_argument('--reuse-assets')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
output=root/'standalone'/'TrueBeam-Local.html'
previous=Path(args.reuse_assets).read_text() if args.reuse_assets else output.read_text()
scripts=list(re.finditer(r'<script([^>]*)>(.*?)</script>',previous,re.S))
embedded=json.loads(next(m.group(2) for m in scripts if 'id="embedded-assets"' in m.group(1)))
library=next(m.group(2) for m in scripts if m.group(2).startswith('/*! For license information please see tesseract.min.js'))
if args.node_modules:
 modules=Path(args.node_modules)
 assets={'ocrWorker':modules/'tesseract.js/dist/worker.min.js','ocrCore':modules/'tesseract.js-core/tesseract-core-lstm.wasm.js','eng':Path(args.english),'pdf':modules/'pdfjs-dist/legacy/build/pdf.min.mjs','pdfWorker':modules/'pdfjs-dist/legacy/build/pdf.worker.min.mjs'}
 embedded={name:base64.b64encode(path.read_bytes()).decode() for name,path in assets.items()}
 library=(modules/'tesseract.js/dist/tesseract.min.js').read_text()
runtime='\n'.join((root/'standalone'/name).read_text() for name in ('browser-runtime.js','excel-runtime.js','intake-runtime.js','shared-adapter.js'))
page=(root/'index.html').read_text();ui_hash=hashlib.sha256(page.encode()).hexdigest()
page=page.replace('</head>','<meta name="truebeam-ui-sha256" content="'+ui_hash+'"></head>')
start=page.index('async function api(path,body){');end=page.index('\nasync function command(',start)
network=page[start:end]
network=network.replace('async function api(path,body){','async function api(path,body){\n if(!USE_SHARED)return localApi(path,body);\n if(window.truebeamNativeRequest&&path!==\"browse\"){const result=await window.truebeamNativeRequest(path,body);return new Response(Uint8Array.from(atob(result.data),c=>c.charCodeAt(0)),{headers:{\"Content-Type\":result.type}});}\n if(path==="browse"&&window.truebeamNativeReady){const bridge=await window.truebeamNativeReady;const data=JSON.parse(await new Promise(resolve=>bridge.pick(body?.kind||"reports",resolve)));if(data.error)throw new Error(data.error);return new Response(JSON.stringify(data));}\n')
page=page[:start]+network+page[end:]
page=page.replace('let state=null,kind=',"const USE_SHARED=Boolean(window.TRUEBEAM_DESKTOP)||(/^https?:$/.test(location.protocol)&&Boolean(token));\nlet state=null,kind=")
page=page.replace("if(typeof localApi==='function')await api('inline-update',{id:record.id,field,value});","if(USE_SHARED)await sharedSaveField(record,field,value);else if(typeof localApi==='function')await api('inline-update',{id:record.id,field,value});")
old="if(location.protocol==='file:'||!token){$('launcher').hidden=false;$('workspace').hidden=true;}else{poll();setInterval(poll,2000);}"
assert old in page
page=page.replace(old,"$('launcher').hidden=true;$('workspace').hidden=false;\nif(USE_SHARED)initShared();else initStandalone();")
page=page.replace('Local database · files stay on this computer','Local files · UFHPTI Physics')
page=page.replace('Monitoring runs while the launcher is open. Original files are never changed. All extracted entries require review.','Monitoring runs while this interface is open. Original files are retained. Open Import details to inspect skipped files.')
marker="<script>\n'use strict';"
def safe(value):return value.replace('</script','<\\/script')
injection='<script type="application/json" id="embedded-assets">'+json.dumps(embedded,separators=(',',':'))+'</script>\n<script>const EMBEDDED=JSON.parse(document.getElementById("embedded-assets").textContent);</script>\n<script>'+safe(library)+'</script>\n<script>'+safe(runtime)+'</script>\n'
page=page.replace(marker,injection+marker,1)
license_match=re.search(r'<details[^>]*>.*?<summary>Included open-source software</summary>.*?</details>',previous,re.S)
if license_match:page=page.replace('</main>',license_match.group(0)+'</main>',1)
output.write_text(page,encoding='utf-8')
(root/'standalone'/'ui-manifest.json').write_text(json.dumps({'ui_sha256':ui_hash,'html_sha256':hashlib.sha256(page.encode()).hexdigest(),'source':'index.html'},indent=2))
print('Built one shared HTML interface:',output.stat().st_size,'bytes; UI SHA256',ui_hash)
