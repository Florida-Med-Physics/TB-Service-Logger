/* Browser-only local database, folder access, extraction and export. */
const LOCAL_FIELDS=['service_date','machine','fault_code','additional_codes','fault_name','severity','impact','issue','cause','suggestions','work_performed','service_status','notes','work_order','case_number','machine_release','category','parts_installed','engineer','work_hours','downtime_hours','document_type','worker_initials'];
const browserStore={db:null,handles:{reports:null,screenshots:null},config:{reports:'',screenshots:'',running:false},busy:false,message:'Choose the two folders to begin.',last_scan:null,job:null,seen:new Map(),timer:null,worker:null,pdf:null,records:[]};
const supported=/\.(pdf|docx|txt|png|jpe?g|bmp|webp)$/i;
function binaryAsset(name){return Uint8Array.from(atob(EMBEDDED[name]),c=>c.charCodeAt(0));}
function scriptBlob(name){return URL.createObjectURL(new Blob([binaryAsset(name)],{type:'text/javascript'}));}
async function openLocalDatabase(){
 browserStore.db=await new Promise((resolve,reject)=>{const req=indexedDB.open('truebeam-standalone-v1',1);req.onupgradeneeded=()=>{const db=req.result;const records=db.createObjectStore('records',{keyPath:'id',autoIncrement:true});records.createIndex('key','key',{unique:true});db.createObjectStore('settings');};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
 for(const kind of ['reports','screenshots']){const handle=await dbGet('settings',kind);if(handle){browserStore.handles[kind]=handle;browserStore.config[kind]=handle.name;}}
 if(browserStore.handles.reports&&browserStore.handles.screenshots)browserStore.message='Folders remembered. Start monitoring to resume; grant access if prompted.';
 await refreshLocalRecords();
}
function dbGet(store,key){return new Promise((resolve,reject)=>{const req=browserStore.db.transaction(store).objectStore(store).get(key);req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});}
function dbAll(){return new Promise((resolve,reject)=>{const req=browserStore.db.transaction('records').objectStore('records').getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});}
function dbPut(store,value,key){return new Promise((resolve,reject)=>{const tx=browserStore.db.transaction(store,'readwrite');const req=key===undefined?tx.objectStore(store).put(value):tx.objectStore(store).put(value,key);let id;req.onsuccess=()=>id=req.result;tx.oncomplete=()=>resolve(id);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||new Error('Database transaction aborted.'));});}
async function refreshLocalRecords(){browserStore.records=await dbAll();for(const record of browserStore.records){if(record.review==='Needs review'){record.review='Closure documented';await dbPut('records',record);}}}
function groupedEvents(){
 const groups=new Map();
 for(const record of browserStore.records.slice().sort((a,b)=>a.id-b.id)){
  const norm=v=>String(v||'').replace(/\s/g,'').toLowerCase();
  const key=record.linkTarget?JSON.stringify(['manual',record.kind,record.linkTarget]):record.kind==='screenshots'&&record.fault_code&&record.service_date?JSON.stringify(['fault',...['machine','fault_code','fault_name','service_date','issue'].map(k=>norm(record[k]))]):JSON.stringify(['file',record.kind,record.digest||record.key]);
  if(!groups.has(key))groups.set(key,{...record,sources:[],possible_duplicate:false});
  let group=groups.get(key);
  if(record.linkTarget===record.id){const sources=group.sources;group={...record,sources,possible_duplicate:false};groups.set(key,group);}
  group.sources.push({id:record.id,path:record.path,error:record.error||''});
 }
 const events=[...groups.values()];
 for(const event of events){delete event.handle;event.possible_duplicate=events.some(other=>other.id!==event.id&&other.kind===event.kind&&event.fault_code&&other.fault_code===event.fault_code&&other.fault_name===event.fault_name&&other.machine===event.machine);}
 return events.reverse();
}
async function permission(handle,ask=false){
 if(!handle)return false;
 if(!handle.queryPermission)return true;
 if(await handle.queryPermission({mode:'read'})==='granted')return true;
 return ask&&await handle.requestPermission({mode:'read'})==='granted';
}
async function* walkFiles(directory,prefix=''){
 for await(const [name,handle] of directory.entries()){
  if(name.startsWith('.')||name.startsWith('~$'))continue;
  const path=prefix+name;
  if(handle.kind==='directory')yield*walkFiles(handle,path+'/');
  else if(supported.test(name))yield {handle,path};
 }
}
function normalizedCode(value){const result=value.replace(/[ \t-]/g,'').replace(/[Oo]/g,'0').replace(/[Il|i]/g,'1').replace(/[Ss]/g,'5').replace(/[Zz]/g,'2').replace(/B/g,'8');return /^(?:\d{4}|\d{6})$/.test(result)?result:'';}
function codeCandidates(text){
 const found=[];
 for(const line of text.split(/\r?\n/)){
  if(/^Additional fault codes:/i.test(line)){for(const token of line.split(':').slice(1).join(':').split(',')){const code=normalizedCode(token.trim());if(code&&!found.includes(code))found.push(code);}continue;}
  const match=line.match(/(?:Error\s*(?:code|ID)|Fault\s*(?:code|ID)|Interlock\s*(?:code|ID)|Code|[I1l]d)\s*[:=#]?\s*([0-9OoIlisSzZB|][0-9OoIlisSzZB| \t-]{2,15}[0-9OoIlisSzZB|])(?:\s|$)/i);
  if(match){const code=normalizedCode(match[1])||normalizedCode(match[1].trim().split(/\s+/)[0]);if(code&&!found.includes(code))found.push(code);}
 }
 return found;
}
function parseLocalText(text){
 const result=Object.fromEntries(LOCAL_FIELDS.map(key=>[key,'']));
 const labels={service_date:'Date\\s*Time|Service date|Date',machine:'Machine|System|Serial number',fault_name:'Name',severity:'Severity',impact:'Impact',issue:'Description|Issue|Problem',cause:'Causes?',suggestions:'Suggestions?',work_performed:'Work performed|Corrective action|Resolution',service_status:'Status'};
 const stops='Id|Name|Severity|Impact|Description|Causes?|Suggestions?|Date\\s*Time|Additional fault codes|Machine|System|Service date|Date|Issue|Problem|Work performed|Corrective action|Resolution|Status';
 for(const [field,label] of Object.entries(labels)){const match=text.match(new RegExp('^\\s*(?:'+label+')\\s*[:=]\\s*(.*?)(?=^\\s*(?:'+stops+')\\s*[:=]|(?![\\s\\S]))','gims'));if(match){const value=match[0].replace(new RegExp('^\\s*(?:'+label+')\\s*[:=]\\s*','i'),'').trim();result[field]=value.slice(0,16000);}}
 const all=codeCandidates(text);
 const detail=text.split(/^Additional fault codes:/im)[0],primary=codeCandidates(detail);
 result.fault_code=primary[0]||(all.length===1?all[0]:'');result.additional_codes=all.filter(c=>c!==result.fault_code).join(', ');
 if(!result.issue)result.issue=result.cause;
 if(/Work\s+Order\s+Information/i.test(text)){
  result.document_type='Work order';
  const patterns={work_order:/\bWO-\d+/,case_number:/\bCase(?:\s+Number)?\s+(\d{6,10})/i,machine:/(?:Asset|Installed Product)\s+(H\d{6})/i,engineer:/(?:Service Resource|Field Engineer)\s+(.+?)(?=\s{3,}|\n|Purchase Order)/i,service_date:/Malfunction Start\s*:?\s*(\d{1,2}\/\d{1,2}\/\d{4}(?:\s+\d{1,2}:\d{2}\s*[AP]M)?)/i,machine_release:/Machine Release(?: Time)?\s*:?\s*(\d{1,2}\/\d{1,2}\/\d{4}(?:\s+\d{1,2}:\d{2}\s*[AP]M)?)/i,work_hours:/Total Work Hours\s+(\d+(?:\.\d+)?)/i,downtime_hours:/Agreed Downtime\s+(\d+(?:\.\d+)?)/i};
  for(const [field,regex] of Object.entries(patterns)){const match=text.match(regex);if(match)result[field]=(match[1]||match[0]).trim();}
  const section=(start,end)=>{const match=text.match(new RegExp(start+'\\s+(.*?)(?='+end+')','is'));return match?match[1].replace(/\s*Product\s*>[\s\S]*/,'').trim():'';};
  result.issue=section('\\bSubject','Closure Summary')||section('Problem Description','Work Performed Comments')||result.issue;
  result.work_performed=section('Closure Summary','Follow Up|Work Order Times')||section('Work Performed Comments','Follow Up Comments');
  const parts=section('Parts Installed','Quality Statements|Customer is responsible');
  result.parts_installed=parts.split('\n').filter(line=>/^\s*[A-Z0-9-]{6,}\s+/.test(line)&&!line.includes('Part Number')).map(s=>s.trim()).join('\n');
  if(!result.service_date){const match=text.match(/Machine Release Time\s*\n([^\n]+)/);if(match){const dates=match[1].match(/\d{1,2}\/\d{1,2}\/\d{4}\s+\d{1,2}:\d{2}/g);if(dates?.length===4){result.service_date=dates[2];result.machine_release=dates[3];}}
  const hours=text.match(/Agreed Downtime\s*\n\s*(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)(?:[ \t]+(\d+\.\d+))?/);if(hours){result.work_hours=hours[2];result.downtime_hours=hours[4]||'';}}
  const codes=[...result.issue.matchAll(/\b\d{6}\b/g)].map(m=>m[0]);
  for(const match of (result.issue+' '+result.work_performed).matchAll(/(?:faults?|error|ID#?|BGM|COL|XI|EGN|STN)\s*[:#-]?\s*((?:\d{6})(?:[ ,;&]+\d{6})*)/gi)){for(const code of match[1].match(/\d{6}/g)||[])if(!codes.includes(code))codes.push(code);}
  if(codes.length){result.fault_code=codes[0];result.additional_codes=[...new Set(codes.slice(1))].join(', ');}
  result.category='Service';for(const [regex,label] of [[/\bPMP\b/i,'PMP'],[/LaserGuard/i,'LaserGuard'],[/SF6|waveguide/i,'SF6 / Waveguide'],[/MLC|collimator/i,'MLC / Collimator'],[/\bXI\b|CBCT|imaging|KVS/i,'Imaging'],[/thyratron|modulator|DeQ/i,'Modulator'],[/couch|encoder/i,'Couch'],[/\bBGM\b|gun|target/i,'Beam generation']]){if(regex.test(result.issue+' '+result.work_performed)){result.category=label;break;}}
  result.service_status=result.work_performed?'Closure documented':'Closure documented';
 }else if(/CHECKLIST|PARAMETER/i.test(text.slice(0,1500))){
  const checklist=/CHECKLIST/i.test(text.slice(0,1500));result.document_type=checklist?'PMP checklist':'PMP parameters';result.category='PMP attachment';result.issue=result.document_type;result.service_status='Attachment';
  const date=text.match(checklist?/PRINT\s*(?:PRINT)?\s*DATE\s*:\s*(?:DATE\s*:)?\s*(\w{3}\/\d{1,2}\/\d{4})/i:/\bDATE\s*:\s*(?:DATE\s*:)?\s*(\w{3}\/\d{1,2}\/\d{4})/i);if(date)result.service_date=date[1];result.machine=(text.match(/\bH\d{6}/)||[])[0]||'';
 }
 return result;
}
async function ocrWorker(){
 if(!browserStore.worker){
  const bootstrap="\n;self.TesseractCore=TesseractCore;\nconst embeddedEnglish=Uint8Array.from(atob("+JSON.stringify(EMBEDDED.eng)+"),c=>c.charCodeAt(0));const originalFetch=self.fetch;self.fetch=(url,options)=>String(url).startsWith('https://embedded.invalid/eng.traineddata')?Promise.resolve(new Response(embeddedEnglish)):originalFetch(url,options);\n";
  const workerURL=URL.createObjectURL(new Blob([binaryAsset('ocrCore'),bootstrap,binaryAsset('ocrWorker')],{type:'text/javascript'}));
  browserStore.worker=await Tesseract.createWorker('eng',1,{workerPath:workerURL,workerBlobURL:false,langPath:'https://embedded.invalid',cacheMethod:'none',gzip:false});
  await browserStore.worker.setParameters({tessedit_pageseg_mode:Tesseract.PSM.SINGLE_BLOCK});
 }
 return browserStore.worker;
}
function imageCanvas(image){const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;canvas.getContext('2d').drawImage(image,0,0);return canvas;}
function cropCanvas(image,x,y,w,h,scale=1){const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));canvas.getContext('2d').drawImage(image,x,y,w,h,0,0,canvas.width,canvas.height);return canvas;}
async function recognizeCanvas(canvas){const worker=await ocrWorker();return (await worker.recognize(canvas)).data.text.trim();}
async function screenshotText(file){
 const image=await createImageBitmap(file),canvas=imageCanvas(image),w=canvas.width,h=canvas.height;
 const top=Math.floor(h*.45),cw=Math.floor(w*.51),ch=Math.floor(h*.45),pixels=canvas.getContext('2d',{willReadFrequently:true}).getImageData(0,top,cw,ch).data;
 const colors=new Map();for(let i=0;i<pixels.length;i+=4){const r=pixels[i],g=pixels[i+1],b=pixels[i+2];if(r>235&&g>235&&b>170&&b<235){const key=(r<<16)|(g<<8)|b;colors.set(key,(colors.get(key)||0)+1);}}
 let chosen=0,count=0;for(const [key,value] of colors)if(value>count){chosen=key;count=value;}
 let panel=null;
 if(count>w*h*.003){
  const matches=index=>((pixels[index*4]<<16)|(pixels[index*4+1]<<8)|pixels[index*4+2])===chosen;
  let best=0,seed=0;
  for(let y=0;y<ch;y++){let start=-1;for(let x=0;x<=cw;x++){if(x<cw&&matches(y*cw+x)){if(start<0)start=x;}else if(start>=0){if(x-start>best){best=x-start;seed=y*cw+start;}start=-1;}}}
  if(best>w*.08){const queue=new Uint32Array(cw*ch),seen=new Uint8Array(cw*ch);let head=0,tail=1;queue[0]=seed;seen[seed]=1;let minX=cw,minY=ch,maxX=0,maxY=0;while(head<tail){const i=queue[head++],x=i%cw,y=Math.floor(i/cw);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);for(const n of [x>0?i-1:-1,x<cw-1?i+1:-1,y>0?i-cw:-1,y<ch-1?i+cw:-1])if(n>=0&&!seen[n]&&matches(n)){seen[n]=1;queue[tail++]=n;}}panel=cropCanvas(canvas,minX,top+minY,maxX-minX+1,maxY-minY+1,3);}
 }
 let detail=panel?await recognizeCanvas(panel):await recognizeCanvas(cropCanvas(canvas,w*.115,h*.46,w*.20,h*.23,3));
 if(!panel&&!/CTRL_|CAUSE\s*:|ID\s*:/i.test(detail))detail='';
 const list=await recognizeCanvas(cropCanvas(canvas,0,h*.615,w*.123,h*.07,3)),codes=[];
 for(const line of list.split('\n')){const match=line.match(/^[\s|©®○•()]*[oO]?\s*([0-9OoIlisSzZB|][0-9OoIlisSzZB| \t-]{2,15}[0-9OoIlisSzZB|])(?:\s+[A-Z]{2,5}|\s*$)/);if(match){const code=normalizedCode(match[1]);if(code&&!codes.includes(code))codes.push(code);}}
 image.close();
 if(!detail&&!codes.length)throw new Error('No fault tooltip, application error, or readable fault list detected. Review this source manually.');
 return detail+(codes.length?'\nAdditional fault codes: '+codes.join(', '):'');
}
async function pdfLibrary(){
 if(!browserStore.pdf){browserStore.pdf=await import(scriptBlob('pdf'));browserStore.pdf.GlobalWorkerOptions.workerSrc=scriptBlob('pdfWorker');}
 return browserStore.pdf;
}
async function extractPdf(file){
 const pdf=await pdfLibrary(),pdfDocument=await pdf.getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false,useSystemFonts:true,disableFontFace:true}).promise,pages=[];
 try{for(let n=1;n<=pdfDocument.numPages;n++){
  const page=await pdfDocument.getPage(n),content=await page.getTextContent(),lines=new Map();
  for(const item of content.items){if(!item.str)continue;const y=Math.round(item.transform[5]/2)*2;if(!lines.has(y))lines.set(y,[]);lines.get(y).push({x:item.transform[4],text:item.str});}
  let text=[...lines].sort((a,b)=>b[0]-a[0]).map(([,items])=>items.sort((a,b)=>a.x-b.x).map(i=>i.text).join('   ')).join('\n');
  if(!text.trim()){const viewport=page.getViewport({scale:2}),canvas=document.createElement('canvas');canvas.width=viewport.width;canvas.height=viewport.height;await page.render({canvasContext:canvas.getContext('2d'),viewport}).promise;text=await recognizeCanvas(canvas);}
  pages.push(text);
 }}finally{await pdfDocument.destroy();}
 return pages.join('\n');
}
async function extractDocx(file){
 const data=new Uint8Array(await file.arrayBuffer()),view=new DataView(data.buffer),decoder=new TextDecoder();
 for(let i=0;i<data.length-46;i++){
  if(view.getUint32(i,true)!==0x02014b50)continue;
  const length=view.getUint16(i+28,true),extra=view.getUint16(i+30,true),comment=view.getUint16(i+32,true),name=decoder.decode(data.slice(i+46,i+46+length));
  if(name==='word/document.xml'){
   const offset=view.getUint32(i+42,true),size=view.getUint32(i+20,true),method=view.getUint16(i+10,true),start=offset+30+view.getUint16(offset+26,true)+view.getUint16(offset+28,true);
   const compressed=new Blob([data.slice(start,start+size)]),xml=method===0?await compressed.text():await new Response(compressed.stream().pipeThrough(new DecompressionStream('deflate-raw'))).text();
   const document=new DOMParser().parseFromString(xml,'application/xml');
   if(document.querySelector('parsererror'))throw new Error('Invalid Word document XML.');
   return [...document.getElementsByTagNameNS('*','p')].map(p=>p.textContent).join('\n');
  }
  i+=45+length+extra+comment;
 }
 throw new Error('No readable document text found in this Word file.');
}
async function extractLocalFile(file,kind){
 if(/\.pdf$/i.test(file.name))return extractPdf(file);
 if(/\.docx$/i.test(file.name))return extractDocx(file);
 if(/\.txt$/i.test(file.name))return file.text();
 if(kind==='screenshots')return screenshotText(file);
 const bitmap=await createImageBitmap(file),canvas=imageCanvas(bitmap);bitmap.close();return recognizeCanvas(canvas);
}
async function scanFolders(){
 if(browserStore.busy)return;
 browserStore.busy=true;const warnings=[];
 try{for(const kind of ['reports','screenshots']){
  const directory=browserStore.handles[kind];
  if(!await permission(directory)){warnings.push('Folder access needs renewal: '+(directory?.name||kind)+'. Use Browse to reconnect.');continue;}
  try{for await(const source of walkFiles(directory)){
   if(browserStore.stopRequested)break;
   const key=kind+':'+directory.name+'/'+source.path;
   try{
    const file=await source.handle.getFile(),signature=file.size+':'+file.lastModified;
    browserStore.message='Checking '+file.name;
    if(browserStore.seen.get(key)!==signature||Date.now()-file.lastModified<2000){browserStore.seen.set(key,signature);continue;}
    const old=browserStore.records.find(r=>r.key===key);
    if(old&&old.signature===signature&&old.version===1){if(!old.handle){await dbPut('records',{...old,handle:source.handle});await refreshLocalRecords();}continue;}
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))].map(v=>v.toString(16).padStart(2,'0')).join('');
    if(old&&old.digest===digest&&old.version===1){await dbPut('records',{...old,signature,handle:source.handle});await refreshLocalRecords();continue;}
    let text='',error='';try{text=(await extractLocalFile(file,kind)).trim();if(!text)throw new Error('No readable text found.');}catch(e){error=e.message||String(e);}
    let fields=parseLocalText(text);
    if(old){const previous=parseLocalText(old.text||'');for(const field of LOCAL_FIELDS)if(old[field]&&(old.review==='Reviewed'||old[field]!==previous[field]))fields[field]=old[field];}
    const record={...fields,key,path:directory.name+'/'+source.path,kind,digest,signature,version:1,handle:source.handle,text,error,review:'Closure documented',imported:new Date().toISOString()};
    if(old){record.id=old.id;if(old.linkTarget)record.linkTarget=old.linkTarget;}
    const after=await source.handle.getFile();if(after.size!==file.size||after.lastModified!==file.lastModified)continue;
    await dbPut('records',record);await refreshLocalRecords();
   }catch(e){warnings.push(source.path+': '+(e.message||e));}
  }}catch(e){warnings.push(directory.name+': '+(e.message||e));}
 }}
 finally{browserStore.busy=false;browserStore.last_scan=new Date().toLocaleString();browserStore.message=warnings.join(' ')||(browserStore.stopRequested?'Monitoring paused.':'Folders checked. Entries are saved in this browser.');}
}
function scheduleAction(action,payload,operation){
 const id=crypto.randomUUID();
 setTimeout(async()=>{try{await operation();browserStore.job={id,ok:true,message:'Change applied.'};}catch(e){browserStore.job={id,ok:false,message:e.message||String(e)};}},0);
 return {queued:true,id};
}
function csvExport(){
 const fields=LOCAL_FIELDS.filter(k=>k!=='machine'&&(kind!=='screenshots'||k!=='impact'));
 const headers=['ID',...fields.map(k=>fieldLabel(k)),'Status','Source files','Import problems'],rows=[headers];
 for(const record of displayedRecords())rows.push([record.id,...fields.map(k=>record[k]||''),record.review,record.sources.map(s=>s.path).join('\n'),record.sources.map(s=>s.error).filter(Boolean).join('\n')]);
 const quote=value=>{let text=String(value??'');if(/^[=+\-@\t\r]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';};
 return '\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n');
}

async function localApi(route,body){
 if(route==='state')return new Response(JSON.stringify({records:groupedEvents(),fields:LOCAL_FIELDS,config:browserStore.config,busy:browserStore.busy,message:browserStore.message,last_scan:browserStore.last_scan,job:browserStore.job,database:'This browser profile · IndexedDB · Export Report saves both tables to Excel.'}));
 if(route==='browse'){
  if(!window.showDirectoryPicker)throw new Error('Open this HTML file in a current desktop version of Microsoft Edge or Google Chrome.');
  const kind=body.kind;if(!['reports','screenshots'].includes(kind))throw new Error('Choose the folder type.');
  const handle=await showDirectoryPicker({id:'truebeam-'+kind,mode:'read'});
  const other=browserStore.handles[kind==='reports'?'screenshots':'reports'];
  if(other){if(await handle.isSameEntry(other)||await handle.resolve(other)!==null||await other.resolve(handle)!==null)throw new Error('Choose separate folders that do not contain one another.');}
  browserStore.handles[kind]=handle;browserStore.config[kind]=handle.name;await dbPut('settings',handle,kind);
  return new Response(JSON.stringify({path:handle.name}));
 }
 if(route.startsWith('source?id=')){
  const id=Number(route.split('=')[1]),record=await dbGet('records',id);
  if(!record?.handle)throw new Error('Reconnect the source folder and scan it to reopen this source.');
  if(!await permission(record.handle,true))throw new Error('Read access was not granted.');
  const file=await record.handle.getFile();return new Response(file,{headers:{'Content-Type':file.type||(/\.pdf$/i.test(file.name)?'application/pdf':'application/octet-stream')}});
 }
 if(route==='backup'){
  const records=browserStore.records.map(({handle,...record})=>record);
  return new Response(JSON.stringify({format:'truebeam-browser-backup',version:1,created:new Date().toISOString(),records},null,2),{headers:{'Content-Type':'application/json'}});
 }
 if(route==='excel')return new Response(csvExport(),{headers:{'Content-Type':'text/csv;charset=utf-8'}});
 if(route==='configure'){
  for(const key of ['reports','screenshots'])if(!await permission(browserStore.handles[key],true))throw new Error('Use Browse to grant read access to the '+key+' folder.');
  browserStore.config.running=true;browserStore.stopRequested=false;browserStore.seen.clear();browserStore.message='Monitoring selected folders every five seconds while this page remains open.';
  if(!browserStore.timer)browserStore.timer=setInterval(()=>{if(browserStore.config.running)scanFolders().catch(e=>browserStore.message=e.message);},5000);
  return new Response(JSON.stringify(scheduleAction(route,body,async()=>{await scanFolders();})));
 }
 if(route==='pause'){browserStore.config.running=false;browserStore.stopRequested=true;browserStore.message='Monitoring paused. Existing entries remain saved.';return new Response(JSON.stringify(scheduleAction(route,body,async()=>{})));}
 if(route==='scan'||route==='retry'){
  if(browserStore.busy)throw new Error('A folder scan is already running. Please wait for it to finish.');
  if(!browserStore.handles.reports||!browserStore.handles.screenshots)throw new Error('Choose both folders first.');
  for(const key of ['reports','screenshots'])if(!await permission(browserStore.handles[key],true))throw new Error('Use Browse to reconnect the '+key+' folder.');
  browserStore.stopRequested=false;
  return new Response(JSON.stringify(scheduleAction(route,body,async()=>{
   if(route==='retry'){for(const record of browserStore.records.filter(r=>r.error)){record.signature='';record.version=0;await dbPut('records',record);}await refreshLocalRecords();}
   await scanFolders();await new Promise(resolve=>setTimeout(resolve,2200));await scanFolders();
  })));
 }
 if(route==='update')return new Response(JSON.stringify(scheduleAction(route,body,async()=>{const old=await dbGet('records',Number(body.id));if(!old)throw new Error('Unknown record.');const record={...old};for(const key of [...LOCAL_FIELDS,'review'])if(Object.hasOwn(body,key))record[key]=String(body[key]);if(!['Reviewed','Closure documented'].includes(record.review))throw new Error('Invalid review status.');await dbPut('records',record);await refreshLocalRecords();})));
 if(route==='merge')return new Response(JSON.stringify(scheduleAction(route,body,async()=>{const events=groupedEvents(),source=events.find(r=>r.id===Number(body.source)),target=events.find(r=>r.id===Number(body.target));if(!source||!target||source.id===target.id||source.kind!==target.kind)throw new Error('Choose two entries on the same tab.');for(const item of [...source.sources,...target.sources]){const record=await dbGet('records',item.id);record.linkTarget=target.id;await dbPut('records',record);}await refreshLocalRecords();})));
 throw new Error('Unknown local action.');
}
async function initStandalone(){
 try{
  await openLocalDatabase();
  $('reports').readOnly=true;$('screenshots').readOnly=true;
  $('reports').placeholder='Choose the service-report folder…';$('screenshots').placeholder='Choose the screenshot folder…';
  $('excel').textContent='Export Report';
  $('database-path').textContent='Database stored in this browser. The connected Export Report re-saves hourly.';
  if(!window.showDirectoryPicker)notice('Folder monitoring requires a current desktop Microsoft Edge or Google Chrome browser.',true);
  await poll();await initExcelSync();setInterval(poll,2000);
 }catch(e){notice('Browser database unavailable: '+(e.message||e)+'. Open the file in a regular Edge or Chrome window with browser storage enabled.',true);}
}
async function restoreStandalone(file){
 if(browserStore.busy||browserStore.config.running)throw new Error('Pause monitoring and wait for the current scan to finish before restoring a backup.');
 const backup=JSON.parse(await file.text());
 if(backup.format!=='truebeam-browser-backup'||backup.version!==1||!Array.isArray(backup.records))throw new Error('Choose a TrueBeam JSON database backup.');
 const ids=new Set(),keys=new Set();
 for(const record of backup.records){if(!Number.isSafeInteger(record.id)||record.id<1||!['reports','screenshots'].includes(record.kind)||typeof record.key!=='string'||ids.has(record.id)||keys.has(record.key))throw new Error('The backup contains invalid or duplicate source records.');ids.add(record.id);keys.add(record.key);}
 if(!confirm('Replace this browser database with '+backup.records.length+' source records from the backup? Save a backup of the current database first if you need it.'))return;
 await new Promise((resolve,reject)=>{const tx=browserStore.db.transaction('records','readwrite'),store=tx.objectStore('records');store.clear();for(const record of backup.records){const {handle,...safe}=record;store.put(safe);}tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});
 await refreshLocalRecords();await poll();notice('Database restored. Reconnect the original folders and scan to restore source-file access.');
}
