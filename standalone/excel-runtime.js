/* Offline XLSX writer: standard Open XML in an uncompressed ZIP. */
const excelSync={handle:null,signature:null,busy:false,retryAt:0};
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
  return '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="'+ns+'"><sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>'+widths.map((w,i)=>'<col min="'+(i+1)+'" max="'+(i+1)+'" width="'+w+'" customWidth="1"/>').join('')+'</cols><sheetData>'+all.map((row,i)=>'<row r="'+(i+1)+'"'+(i===3?' ht="32" customHeight="1"':'')+'>'+row.map((v,c)=>cell(v,i+1,c,i===0?1:i===1?2:i===3?3:0)).join('')+'</row>').join('')+'</sheetData><autoFilter ref="A4:'+column(headers.length-1)+Math.max(4,all.length)+'"/></worksheet>';
 };
 const date=v=>{const n=parsedDate(v);return n===null?(v||''):new Date(n);},number=v=>v!==''&&v!==undefined&&v!==null&&Number.isFinite(Number(v))?Number(v):(v||'');
 const sorted=records.slice().sort((a,b)=>(parsedDate(b.service_date)||0)-(parsedDate(a.service_date)||0));
 const service=sorted.filter(r=>r.kind==='reports').map(r=>[date(r.service_date),date(r.machine_release),r.work_order,r.case_number,r.category,[r.issue,r.fault_code,r.additional_codes].filter(Boolean).join('\n'),r.work_performed,r.parts_installed,r.engineer,number(r.work_hours),number(r.downtime_hours),r.service_status||r.review,r.notes,r.sources.map(s=>s.path).join('\n')]);
 const faults=sorted.filter(r=>r.kind==='screenshots').map(r=>[date(r.service_date),r.machine,r.fault_code,r.additional_codes,r.fault_name,r.severity,r.issue,r.suggestions,r.worker_initials,r.work_performed,r.review,r.notes,r.sources.map(s=>s.path).join('\n')]);
 const styles='<?xml version="1.0"?><styleSheet xmlns="'+ns+'"><numFmts count="1"><numFmt numFmtId="164" formatCode="mm/dd/yyyy hh:mm"/></numFmts><fonts count="4"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="14"/><name val="Arial"/></font><font><sz val="9"/><color rgb="FF595959"/><name val="Arial"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Arial"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="2"><border/><border><left style="thin"><color rgb="FFD9E2F3"/></left><right style="thin"><color rgb="FFD9E2F3"/></right><top style="thin"><color rgb="FFD9E2F3"/></top><bottom style="thin"><color rgb="FFD9E2F3"/></bottom></border></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="5"><xf fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf fontId="1" fillId="0" borderId="0" xfId="0"/><xf fontId="2" fillId="0" borderId="0" xfId="0"/><xf fontId="3" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
 return zipWorkbook([
 ['[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'],
 ['_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'],
 ['xl/workbook.xml','<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Service Reports" sheetId="1" r:id="rId1"/><sheet name="Fault Reports" sheetId="2" r:id="rId2"/></sheets></workbook>'],
 ['xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'],
 ['xl/styles.xml',styles],
 ['xl/worksheets/sheet1.xml',sheet('Service Reports',['Malfunction Start','Machine Release','Work Order #','Case #','Category','Subject / Fault Codes','Summary of Work','Parts Installed','Field Engineer','Total Work Hrs','Agreed Downtime Hrs','Status','Follow-up / Notes','Source Report'],[12,12,15,11,18,26,70,32,13,10,11,14,34,22],service)],
 ['xl/worksheets/sheet2.xml',sheet('Fault Reports',['Event Date','Machine','Error Code','Additional Codes','Fault Name','Severity','Error Details','Solution','Worker Initials','Work Performed','Status','Notes','Source Screenshots'],[20,18,15,18,32,14,70,70,16,50,24,34,32],faults)]
 ]);
}
function excelStatus(message,error=false){const node=$('excel-status');if(node){node.textContent=message;node.style.color=error?'#b23b31':'';}}
async function syncExcel(force=false){
 if(!excelSync.handle||excelSync.busy||(!force&&Date.now()<excelSync.retryAt))return;
 const records=groupedEvents(),signature=JSON.stringify(records);if(!force&&signature===excelSync.signature)return;
 excelSync.busy=true;
 try{
  if(await excelSync.handle.queryPermission({mode:'readwrite'})!=='granted')throw new Error('Reconnect Excel file to grant write access.');
  const blob=excelWorkbook(records),writer=await excelSync.handle.createWritable();
  try{await writer.write(blob);await writer.close();}catch(e){try{await writer.abort();}catch{}throw e;}
  excelSync.signature=signature;excelSync.retryAt=0;excelStatus('Excel saved · '+excelSync.handle.name+' · '+new Date().toLocaleTimeString());
 }catch(e){excelSync.retryAt=Date.now()+10000;excelStatus('Excel not saved: '+e.message+' Close the workbook in Excel if it is locked; changes remain in the database.',true);}
 finally{excelSync.busy=false;}
}
async function connectExcel(){
 try{
  if(!window.showSaveFilePicker)throw new Error('Use desktop Edge or Chrome to connect an Excel file.');
  const handle=await showSaveFilePicker({suggestedName:'TrueBeam_Service_Log.xlsx',types:[{description:'Excel workbook',accept:{'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':['.xlsx']}}]});
  if(excelSync.busy)throw new Error('A save is in progress. Try again in a moment.');
  excelSync.handle=handle;excelSync.signature=null;await dbPut('settings',handle,'excel-output');await syncExcel(true);
 }catch(e){if(e.name!=='AbortError')excelStatus(e.message,true);}
}
async function initExcelSync(){
 const button=el('button','Connect Excel file');button.id='connect-excel';button.onclick=connectExcel;$('folder-dialog').querySelector('.dialog-body').append(button,el('p','Choose a dedicated output workbook. Its contents are replaced with both complete database tables after imports and edits. Keep this page open; close the workbook in Excel to allow saving.','sub'));
 const status=el('span','Excel not connected · choose an output file in Folder settings');status.id='excel-status';status.setAttribute('role','status');document.querySelector('.monitor-bar').append(status);
 excelSync.handle=await dbGet('settings','excel-output');
 if(excelSync.handle){button.textContent='Change Excel file';excelStatus('Excel file remembered · '+excelSync.handle.name);const reconnect=el('button','Reconnect Excel');reconnect.onclick=async()=>{try{await excelSync.handle.requestPermission({mode:'readwrite'});excelSync.retryAt=0;await syncExcel(true);}catch(e){excelStatus(e.message,true);}};button.after(reconnect);await syncExcel();}
 setInterval(()=>syncExcel(),2000);
}
