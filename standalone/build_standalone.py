from pathlib import Path
import argparse,base64,json,html
parser=argparse.ArgumentParser();parser.add_argument('--node-modules',required=True);parser.add_argument('--english',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
modules=Path(args.node_modules)
assets={
 'ocrWorker':modules/'tesseract.js/dist/worker.min.js',
 'ocrCore':modules/'tesseract.js-core/tesseract-core-lstm.wasm.js',
 'eng':Path(args.english),
 'pdf':modules/'pdfjs-dist/legacy/build/pdf.min.mjs',
 'pdfWorker':modules/'pdfjs-dist/legacy/build/pdf.worker.min.mjs',
}
embedded={name:base64.b64encode(path.read_bytes()).decode('ascii') for name,path in assets.items()}
api=(modules/'tesseract.js/dist/tesseract.min.js').read_text()
runtime=(root/'standalone/browser-runtime.js').read_text()+'\n'+(root/'standalone/excel-runtime.js').read_text()+'\n'+(root/'standalone/intake-runtime.js').read_text()
page=(root/'index.html').read_text()
page=page.replace('Local database · files stay on this computer','Local HTML · offline')
page=page.replace('Select folders on this computer or a mapped network drive. Existing files are included.','Use Edge or Chrome to choose two folders. This HTML runs offline; no launcher or server is needed.')
page=page.replace('Monitoring runs while the launcher is open. Original files are never changed. All extracted entries require review.','Monitoring runs while this page is open. The browser may slow checks in background tabs. Reconnect folder permissions when prompted. The connected Export Report is saved after changes and re-saved every minute while this page is open.')
start=page.index('async function api(path,body){')
end=page.index('\nasync function command(',start)
page=page[:start]+'async function api(path,body){return localApi(path,body);}'+page[end:]
page=page.replace("api('browse',{})","api('browse',{kind:button.dataset.for})")
page=page.replace("await download('excel','TrueBeam Service Log.xlsx');","await download('excel',kind==='reports'?'TrueBeam Service Reports.csv':'TrueBeam Fault Reports.csv');")
page=page.replace("notice('Downloading the latest completed Excel export. Entries from a scan in progress will appear in the next export.');","notice('Downloading a CSV of the selected tab.');")
page=page.replace("download('backup','TrueBeam Service Log.sqlite3')","download('backup','TrueBeam Database Backup.json')")
page=page.replace("if(location.protocol==='file:'||!token){$('launcher').hidden=false;$('workspace').hidden=true;}else{poll();setInterval(poll,2000);}","""$('launcher').hidden=true;$('workspace').hidden=false;
initStandalone();""")
marker="<script>\n'use strict';"
def script_text(value):return value.replace('</script','<\\/script')
injection='<script type="application/json" id="embedded-assets">'+json.dumps(embedded,separators=(',',':'))+'</script>\n<script>const EMBEDDED=JSON.parse(document.getElementById("embedded-assets").textContent);</script>\n<script>'+script_text(api)+'</script>\n<script>'+script_text(runtime)+'</script>\n'
assert marker in page
page=page.replace(marker,injection+marker,1)
licenses=[]
for name,path in [('Tesseract.js',modules/'tesseract.js/LICENSE.md'),('Tesseract.js core',modules/'tesseract.js-core/LICENSE'),('PDF.js',modules/'pdfjs-dist/LICENSE')]:
 if path.exists():licenses.append(name+'\n'+path.read_text())
licenses.append('English OCR data: tesseract-ocr/tessdata_fast, eng.traineddata; Apache License 2.0. https://github.com/tesseract-ocr/tessdata_fast')
page=page.replace('</main>','<details style="font-size:11px;color:var(--muted);margin-top:20px"><summary>Included open-source software</summary><pre style="white-space:pre-wrap">'+html.escape('\n\n'.join(licenses))+'</pre></details></main>',1)
output=root/'standalone/TrueBeam-Local.html'
output.write_text(page,encoding='utf-8')
print('Built:',output.name,round(output.stat().st_size/1024/1024,1),'MB; all OCR, language and PDF assets embedded.')
