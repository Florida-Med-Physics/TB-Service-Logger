/* Offline XLSX writer: standard Open XML in an uncompressed ZIP. */
const xmlText=v=>String(v??'').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g,'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function zipWorkbook(entries){
 const encoder=new TextEncoder(),chunks=[],directory=[];let offset=0;
 const crc=data=>{let c=0xffffffff;for(const b of data){c^=b;for(let i=0;i<8;i++)c=(c>>>1)^((c&1)?0xedb88320:0);}return (c^0xffffffff)>>>0;};
 for(const [path,text] of entries){const name=encoder.encode(path),data=encoder.encode(text),checksum=crc(data),header=new Uint8Array(30+name.length),v=new DataView(header.buffer);
 v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint32(14,checksum,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,name.length,true);header.set(name,30);
 const central=new Uint8Array(46+name.length),d=new DataView(central.buffer);d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint32(16,checksum,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);d.setUint16(28,name.length,true);d.setUint32(42,offset,true);central.set(name,46);chunks.push(header,data);directory.push(central);offset+=header.length+data.length;}
 const size=directory.reduce((n,d)=>n+d.length,0),end=new Uint8Array(22),v=new DataView(end.buffer);v.setUint32(0,0x06054b50,true);v.setUint16(8,entries.length,true);v.setUint16(10,entries.length,true);v.setUint32(12,size,true);v.setUint32(16,offset,true);
 return new Blob([...chunks,...directory,end],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}
function excelWorkbook(records){
 const ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main',column=i=>{let s='';for(i++;i;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;return s;};
 const sheet=(name,headers,widths,rows)=>{
  const cell=(v,r,c,style)=>{const ref=column(c)+r;if(v instanceof Date&&!isNaN(v))return '<c r="'+ref+'" s="4"><v>'+(v.getTime()/86400000+25569)+'</v></c>';if(typeof v==='number'&&Number.isFinite(v))return '<c r="'+ref+'" s="'+style+'"><v>'+v+'</v></c>';return '<c r="'+ref+'" s="'+style+'" t="inlineStr"><is><t xml:space="preserve">'+xmlText(v).slice(0,32767)+'</t></is></c>';};
  const all=[['TrueBeam — '+name],['Updated '+new Date().toLocaleString()+'. Automatically saved from the local database.'],[],headers,...rows];
  const statusCol=name==='Fault Reports'?headers.indexOf('Status'):-1;
  return '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="'+ns+'"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>'+widths.map((w,i)=>'<col min="'+(i+1)+'" max="'+(i+1)+'" width="'+w+'" customWidth="1"/>').join('')+'</cols><sheetData>'+all.map((row,i)=>'<row r="'+(i+1)+'"'+(i===3?' ht="42" customHeight="1"':'')+'>'+row.map((v,c)=>cell(v,i+1,c,i===0?1:i===1?2:i===3?3:i>3&&c===statusCol?(v==='Resolved'?6:5):0)).join('')+'</row>').join('')+'</sheetData><autoFilter ref="A4:'+column(headers.length-1)+Math.max(4,all.length)+'"/><printOptions horizontalCentered="1"/><pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.3" footer="0.3"/><pageSetup paperSize="1" orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>';
 };
 const date=v=>{const n=parsedDate(v);return n===null?(v||''):new Date(n);},number=v=>v!==''&&v!==undefined&&v!==null&&Number.isFinite(Number(v))?Number(v):(v||'');
 const sorted=records.slice().sort((a,b)=>(parsedDate(b.service_date)||0)-(parsedDate(a.service_date)||0));
 const service=sorted.filter(r=>r.kind==='reports').map(r=>[date(r.service_date),date(r.machine_release),r.work_order,r.case_number,r.category,r.issue,[r.fault_code,r.additional_codes].filter(Boolean).flatMap(value=>String(value).split(/[,;\n]+/)).map(code=>code.trim()).filter(Boolean).join('\n'),r.work_performed,r.parts_installed,r.engineer,number(r.work_hours),number(r.downtime_hours),r.service_status||r.review,r.notes,r.sources.map(s=>s.path).join('\n')]);
 const faults=sorted.filter(r=>r.kind==='screenshots').map(r=>[date(r.service_date),r.fault_code,r.additional_codes,r.fault_name,r.severity,r.issue,r.suggestions,r.current_status,r.work_performed,r.worker_initials,r.service_status==='Resolved'?'Resolved':'Open',r.sources.map(s=>s.path).join('\n')]);
 const styles='<?xml version="1.0"?><styleSheet xmlns="'+ns+'"><numFmts count="1"><numFmt numFmtId="164" formatCode="mm/dd/yyyy hh:mm"/></numFmts><fonts count="6"><font><sz val="14"/><name val="Arial"/></font><font><b/><sz val="20"/><name val="Arial"/></font><font><sz val="12"/><color rgb="FF595959"/><name val="Arial"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="14"/><name val="Arial"/></font><font><b/><color rgb="FF7A3300"/><sz val="14"/><name val="Arial"/></font><font><b/><color rgb="FF0F5128"/><sz val="14"/><name val="Arial"/></font></fonts><fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFDE2C4"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFCDEED6"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="2"><border/><border><left style="thin"><color rgb="FFD9E2F3"/></left><right style="thin"><color rgb="FFD9E2F3"/></right><top style="thin"><color rgb="FFD9E2F3"/></top><bottom style="thin"><color rgb="FFD9E2F3"/></bottom></border></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="7"><xf fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf fontId="1" fillId="0" borderId="0" xfId="0"/><xf fontId="2" fillId="0" borderId="0" xfId="0"/><xf fontId="3" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf fontId="4" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="top"/></xf><xf fontId="5" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
 return zipWorkbook([
 ['[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'],
 ['_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'],
 ['xl/workbook.xml','<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Service Reports" sheetId="1" r:id="rId1"/><sheet name="Fault Reports" sheetId="2" r:id="rId2"/></sheets><definedNames><definedName name="_xlnm.Print_Titles" localSheetId="0">\'Service Reports\'!$4:$4</definedName><definedName name="_xlnm.Print_Titles" localSheetId="1">\'Fault Reports\'!$4:$4</definedName></definedNames></workbook>'],
 ['xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'],
 ['xl/styles.xml',styles],
 ['xl/worksheets/sheet1.xml',sheet('Service Reports',['Malfunction Start','Machine Release','Work Order #','Case #','Category','Subject','Error Codes','Summary of Work','Parts Installed','Field Engineer','Total Work Hrs','Agreed Downtime Hrs','Status','Follow-up / Notes','Source Report'],[12,12,15,11,18,26,20,70,32,13,10,11,14,34,22],service)],
 ['xl/worksheets/sheet2.xml',sheet('Fault Reports',['Event Date','Error Code','Additional Codes','Fault Name','Severity','Error Details','Varian Suggested Solution','Current Status','Final Resolution','Initials','Status','Source Screenshots'],[20,15,18,32,14,70,60,45,50,10,12,32],faults)]
 ]);
}
async function initExcelSync(){
 await initLogSync();
 $('excel').onclick=()=>{try{const url=URL.createObjectURL(excelWorkbook(groupedEvents())),a=el('a');a.href=url;a.download='TrueBeam_Service_Log_'+exportStamp()+'.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);notice('Exported the log to Downloads.');}catch(e){notice('Export Report failed: '+e.message,true);}};
}

const logSync={handle:null,busy:false,signature:null,last:null};
function logSignature(records){return JSON.stringify(records.slice().sort((a,b)=>String(a.id).localeCompare(String(b.id))));}
async function syncTimestampedLog(force=false,allowDuringScan=false){
 if(!logSync.handle)return;
 if(logSync.busy){if(force)notice('A log is already saving. Please export again when it finishes.');return;}
 if(browserStore.busy&&!force&&!allowDuringScan)return;
 const records=groupedEvents(),signature=logSignature(records);
 if(!force&&(signature===logSync.signature||(!records.length&&logSync.signature===null)))return;
 logSync.busy=true;
 try{
  if(await logSync.handle.queryPermission({mode:'readwrite'})!=='granted')throw new Error('Choose the logs folder again to grant access.');
  const stamp=new Date().toISOString().replace(/[:.]/g,'-');
  const name='TrueBeam_Log_'+stamp+'_'+crypto.randomUUID()+'.xlsx';
  try{await logSync.handle.getFileHandle(name);throw new Error('Log filename already exists; retrying with a new filename.');}catch(e){if(e.name!=='NotFoundError')throw e;}
  const file=await logSync.handle.getFileHandle(name,{create:true});
  const writer=await file.createWritable();
  try{await writer.write(excelWorkbook(records));await writer.close();}catch(e){try{await writer.abort();}catch{}throw e;}
  logSync.signature=signature;logSync.last={path:logSync.handle.name+'/'+file.name,saved_at:new Date().toISOString()};await dbPut('settings',logSync.last,'last-log');await dbPut('settings',signature,'log-signature');
  notice('Timestamped Excel log saved · '+logSync.last.path);if(typeof poll==='function')await poll();
 }catch(e){notice('Log save pending: '+e.message,true);}finally{logSync.busy=false;}
}
async function initLogSync(){
 logSync.last=await dbGet('settings','last-log')||null;
 logSync.handle=await dbGet('settings','logs-folder');logSync.signature=await dbGet('settings','log-signature')||null;
 const row=el('div');row.style.marginTop='15px';const label=el('label','Logs folder');const input=el('input');input.readOnly=true;input.value=logSync.handle?.name||'';input.style.width='calc(100% - 115px)';
 const choose=el('button','Choose…');choose.onclick=async()=>{try{const startIn=logSync.handle||browserStore.handles.reports;const handle=await showDirectoryPicker({id:'truebeam-logs',mode:'readwrite',...(startIn?{startIn}:{})});const same=logSync.handle&&await logSync.handle.isSameEntry(handle);logSync.handle=handle;if(!same){logSync.signature=null;await dbPut('settings',null,'log-signature');}input.value=handle.name;await dbPut('settings',handle,'logs-folder');await syncTimestampedLog();}catch(e){if(e.name!=='AbortError')notice(e.message,true);}};
 row.append(label,input,choose,el('p','A new timestamped Excel log is saved whenever fault or service report data changes. Earlier logs are preserved.','sub'));$('folder-dialog').querySelector('.dialog-body').insertBefore(row,$('email-settings'));
 await syncTimestampedLog();setInterval(syncTimestampedLog,2000);
}
