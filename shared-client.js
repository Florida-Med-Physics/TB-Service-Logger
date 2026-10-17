async function readImageCanvas(file){
 // Snapshot network/cloud-backed files before passing them to the image decoder.
 const bytes=await file.arrayBuffer();
 const blob=new Blob([bytes],{type:/\.png$/i.test(file.name)?'image/png':/\.jpe?g$/i.test(file.name)?'image/jpeg':file.type||'application/octet-stream'});
 try{const bitmap=await createImageBitmap(blob);try{return imageCanvas(bitmap);}finally{bitmap.close();}}
 catch(primary){
  const url=URL.createObjectURL(blob);
  try{const image=new Image();image.src=url;await image.decode();return cropCanvas(image,0,0,image.naturalWidth,image.naturalHeight);}
  catch(fallback){throw new Error('This image could not be decoded. Ensure the file is fully downloaded locally and try Import files again. '+fallback.message);}
  finally{URL.revokeObjectURL(url);}
 }
}
/* Therapist entry, standard-file import fallback, and visible import diagnostics. */
function sourceResponse(file,name=''){
 const extension=String(name||file.name||'').split('.').pop().toLowerCase();
 const types={png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',bmp:'image/bmp',webp:'image/webp',pdf:'application/pdf',txt:'text/plain'};
 return new Response(file,{headers:{'Content-Type':types[extension]||file.type||'application/octet-stream'}});
}
async function extractWithDeadline(file,kind,milliseconds=120000){
 let timer;
 try{return await Promise.race([extractLocalFile(file,kind),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Reading this file timed out. This computer may block the embedded PDF/OCR worker. Try Import files, then open Import details.')),milliseconds);})]);}
 finally{clearTimeout(timer);}
}
async function importSelectedFiles(files){
 if(browserStore.busy)throw new Error('Wait for the current import to finish before selecting more files.');
 browserStore.busy=true;let added=0,failed=0;
 try{
  for(const file of files){
   if(!supported.test(file.name))continue;
   const kind=/\.(png|jpe?g|bmp|webp)$/i.test(file.name)?'screenshots':'reports';
   browserStore.message='Importing '+file.name;await poll();
   try{
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))].map(v=>v.toString(16).padStart(2,'0')).join('');
    const old=browserStore.records.find(r=>r.kind===kind&&r.digest===digest&&r.entryType!=='manual');
    if(old&&!old.error){await dbPut('records',{...old,sourceFile:file});await refreshLocalRecords();added++;continue;}
    let text='',error='';
    try{text=(await extractWithDeadline(file,kind)).trim();if(!text)throw new Error('No readable text was found. The original file is saved and can still be opened.');}catch(e){error=e.message||String(e);failed++;}
    const fields=parseLocalText(text);
    if(old){const previous=parseLocalText(old.text||'');for(const key of LOCAL_FIELDS)if(old[key]&&(old.review==='Reviewed'||old[key]!==previous[key]))fields[key]=old[key];}
    const record={...old,...fields,key:old?.key||kind+':selected:'+digest,path:old?.path||file.name,kind,digest,signature:file.size+':'+file.lastModified,version:1,sourceFile:file,text,error,review:old?.review||'Closure documented',imported:new Date().toISOString()};
    await dbPut('records',record);await refreshLocalRecords();added++;
   }catch(e){failed++;notice('Could not save '+file.name+': '+e.message+'. Check browser storage and try again.',true);}
  }
 }finally{browserStore.busy=false;browserStore.message=added+' files saved'+(failed?' · '+failed+' import problems. Open Import details.':'.');await poll();}
 notice(browserStore.message,failed>0);
}
async function saveTherapistFault(data,files=[]){
 if(!String(data.issue||'').trim())throw new Error('Enter a fault description.');
 if(!String(data.worker_initials||'').trim())throw new Error('Enter the therapist initials.');
 if(!String(data.service_date||'').trim())throw new Error('Enter the event date and time.');
 const attachments=[];
 for(const file of files){if(!/\.(png|jpe?g|bmp|webp)$/i.test(file.name))throw new Error('Attach PNG or JPEG screenshots.');attachments.push({name:file.name,file});}
 const fields=Object.fromEntries(LOCAL_FIELDS.map(key=>[key,'']));
 for(const key of ['service_date','fault_code','fault_name','issue','work_performed','worker_initials'])fields[key]=String(data[key]||'').trim();
 fields.worker_initials=fields.worker_initials.toUpperCase().slice(0,12);
 const id=await dbPut('records',{...fields,key:'therapist:'+crypto.randomUUID(),kind:'screenshots',entryType:'manual',document_type:'Therapist entry',digest:'',path:'',signature:'manual',version:1,text:'',error:'',review:'Closure documented',attachments,imported:new Date().toISOString()});
 await refreshLocalRecords();await poll();chooseTab('screenshots');notice('Therapist fault saved. It is included in the fault table and Export Report.');return id;
}
function intakeDialog(id,title){
 const dialog=el('dialog');dialog.id=id;const head=el('div',undefined,'dialog-head');head.append(el('h2',title));const close=el('button','Close');close.type='button';close.onclick=()=>dialog.close();head.append(close);
 const body=el('div',undefined,'dialog-body');dialog.append(head,body);document.body.append(dialog);return {dialog,body};
}
async function retryImportProblems(){
 const files=[];
 for(const record of browserStore.records.filter(r=>r.error)){
  if(record.sourceFile)files.push(record.sourceFile);
  else if(record.handle&&await permission(record.handle,true)){try{files.push(await record.handle.getFile());}catch(e){notice('Cannot read '+record.path+': '+e.message,true);}}
 }
 if(!files.length){notice('Use Import files to select the originals again, or reconnect their folder in Folder settings.',true);return;}
 await importSelectedFiles(files);
 if($('import-details')?.open)showImportDetails();
}
function showImportDetails(){
 let dialog=$('import-details');if(!dialog){const created=intakeDialog('import-details','Import details');dialog=created.dialog;}
 const body=dialog.querySelector('.dialog-body');body.replaceChildren(el('p','Files with unreadable text stay in the table, and their originals can still be opened. If folder access is blocked on this computer, use Import files to select PDFs and PNGs directly.'));
 const problems=browserStore.records.filter(r=>r.error),summary=el('p',browserStore.records.length+' source entries · '+problems.length+' extraction problems');body.append(summary);
 if(problems.length){const retry=el('button','Retry problem files');retry.onclick=()=>retryImportProblems().catch(e=>notice(e.message,true));body.append(retry);}
 for(const record of browserStore.records.filter(r=>r.entryType!=='manual')){
  const section=el('div',undefined,'source');section.append(el('strong',record.path),el('p',record.error||'Imported successfully.'));
  const button=el('button','Open original');button.type='button';button.onclick=()=>openSource(record.id);section.append(button);body.append(section);
 }
 if(!browserStore.records.length)body.append(el('p','No entries yet. Choose folders and start monitoring, or use Import files.'));
 if(!dialog.open)dialog.showModal();
}
async function initIntake(){
 const actions=document.querySelector('.exports');
 const importButton=el('button','Import files');importButton.id='import-files';
 const input=el('input');input.type='file';input.multiple=true;input.accept='.pdf,.png,.jpg,.jpeg,.bmp,.webp,.txt,.docx';input.hidden=true;input.id='import-file-input';
 importButton.onclick=()=>input.click();input.onchange=async()=>{try{await importSelectedFiles([...input.files]);}catch(e){notice(e.message,true);}finally{input.value='';}};
 const details=el('button','Import details');details.id='import-details-button';details.onclick=showImportDetails;
 const add=el('button','Add fault','primary');add.id='add-fault';
 actions.prepend(add,importButton,details,input);
 const {dialog,body}=intakeDialog('therapist-fault','Add therapist fault');
 const form=el('form');form.id='therapist-fault-form';const grid=el('div',undefined,'edit-grid');
 for(const [key,label,type] of [['service_date','Event date / time','datetime-local'],['worker_initials','Therapist initials','text'],['fault_code','Error code (if known)','text'],['fault_name','Fault name (if known)','text'],['issue','Error Details','textarea'],['work_performed','Resolution (if fixed)','textarea']]){
  const wrap=el('div',undefined,type==='textarea'?'wide':'');const labelNode=el('label',label);labelNode.htmlFor='therapist-'+key;
  const control=el(type==='textarea'?'textarea':'input');control.id='therapist-'+key;control.name=key;if(type!=='textarea')control.type=type;
  if(['service_date','worker_initials','issue'].includes(key))control.required=true;
  if(key==='worker_initials'){control.maxLength=12;control.oninput=()=>control.value=control.value.toUpperCase();}
  wrap.append(labelNode,control);grid.append(wrap);
 }
 const attach=el('div',undefined,'wide'),label=el('label','Screenshots (optional)');label.htmlFor='therapist-attachments';
 const attachments=el('input');attachments.id='therapist-attachments';attachments.type='file';attachments.accept='.png,.jpg,.jpeg,.bmp,.webp';attachments.multiple=true;attach.append(label,attachments);grid.append(attach);
 const submit=el('button','Save fault','primary');submit.type='submit';const feedback=el('p');feedback.id='therapist-feedback';feedback.setAttribute('role','status');form.append(grid,feedback,submit);body.append(form);
 add.onclick=()=>{form.reset();feedback.textContent='';const date=new Date(Date.now()-new Date().getTimezoneOffset()*60000);$('therapist-service_date').value=date.toISOString().slice(0,16);dialog.showModal();};
 form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{await saveTherapistFault(Object.fromEntries(new FormData(form)),[...attachments.files]);dialog.close();}catch(e){feedback.textContent='Could not save: '+e.message;}finally{submit.disabled=false;}};
}

/* Shared backend adapter; the existing HTML, CSS and table renderer are unchanged. */
const browserStore={records:[],busy:false};
async function sharedSaveField(record,field,value){
 await api('inline-update',{id:record.id,field,value,expected:record[field]||''});
}
async function sharedFile(file){
 const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
 for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
 return {name:file.name,data:btoa(binary)};
}
async function initShared(){
 let faultRequestId=crypto.randomUUID();
 const originalPoll=poll;
 poll=async()=>{await originalPoll();if(state){browserStore.records=state.records;browserStore.busy=state.busy;}};
 command=async(action,body={})=>{try{const result=await(await api(action,body)).json();notice('Change saved on the shared host.');await poll();return result;}catch(e){notice(e.message,true);return null;}};
 importSelectedFiles=async files=>{
  if(browserStore.busy)throw new Error('The host is scanning. Please try the file import again in a moment.');
  let problems=0;
  for(const file of files){
   notice('Importing '+file.name+' on the host…');
   const result=await(await api('upload',await sharedFile(file))).json();if(result.error)problems++;
  }
  await poll();notice(files.length+' files imported'+(problems?' · Open Import details for '+problems+' extraction problems.':'.'));
 };
 saveTherapistFault=async(data,files)=>{
  const attachments=[];for(const file of files)attachments.push(await sharedFile(file));
  const result=await(await api('add-fault',{...data,attachments,requestId:faultRequestId})).json();
  await poll();chooseTab('screenshots');notice('Fault saved to the shared database.');return result.id;
 };
 retryImportProblems=async()=>{await command('retry');notice('Host retry requested.');};
 await poll();await initIntake();
 const openAdd=$('add-fault').onclick;$('add-fault').onclick=()=>{faultRequestId=crypto.randomUUID();openAdd();};
 const folderBody=$('folder-dialog').querySelector('.dialog-body');
 const row=el('div');row.style.marginTop='15px';
 const label=el('label','Export Report');label.htmlFor='shared-output';
 const input=el('input');input.id='shared-output';input.value=state.config.output;input.style.width='100%';
 row.append(label,input,el('p','All applications use these host paths. The report reads new data every minute without replacing the open workbook.','sub'));folderBody.append(row);
 $('reports').value=state.config.reports;$('screenshots').value=state.config.screenshots;
 $('start').onclick=()=>command('configure',{reports:$('reports').value.trim(),screenshots:$('screenshots').value.trim(),output:input.value.trim()});
 if(!state.admin){
  for(const node of [$('reports'),$('screenshots'),input])node.readOnly=true;
  for(const button of [...document.querySelectorAll('.browse'),$('start'),$('pause'),$('retry')]){button.disabled=true;button.title='Host administrator only';}
 }
 $('excel').onclick=()=>download('excel','TrueBeam_Service_Log.xlsx');
 setInterval(poll,2000);
}
