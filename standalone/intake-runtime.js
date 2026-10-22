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
 const body=dialog.querySelector('.dialog-body');body.replaceChildren(el('p','Skipped or unreadable files remain available here, outside the report tables. If folder access is blocked on this computer, use Import Varian work orders to select work order PDFs directly. Screenshots are read from the monitored screenshot folder.'));
 const problems=browserStore.records.filter(r=>r.error),summary=el('p',browserStore.records.length+' source entries · '+problems.length+' extraction problems');body.append(summary);
 if(problems.length){const retry=el('button','Retry problem files');retry.onclick=()=>retryImportProblems().catch(e=>notice(e.message,true));body.append(retry);}
 for(const record of browserStore.records.filter(r=>r.entryType!=='manual')){
  const section=el('div',undefined,'source');section.append(el('strong',record.path),el('p',record.error||'Imported successfully.'));
  const button=el('button','Open original');button.type='button';button.onclick=()=>openSource(record.id);section.append(button);body.append(section);
 }
 for(const skipped of (state?.excluded||[])){const section=el('div',undefined,'source');section.append(el('strong',skipped.sources.map(s=>s.path.split(/[\\/]/).pop()).join(', ')),el('p',skipped.reason));for(const source of skipped.sources){const open=el('button','Open original');open.onclick=()=>openSource(source.id);section.append(open);}body.append(section);}
 if(!browserStore.records.length)body.append(el('p','No entries yet. Choose folders and start monitoring, or use Import files.'));
 if(!dialog.open)dialog.showModal();
}
/* Send Downtime Alert: a scripted email prefilled from the newest open fault. Patient identifiers are never prefilled. */
const DOWNTIME_FIELDS=[['recipients','To (email addresses)','text'],['site','Site/Machine','text'],['status','Machine status','select'],['started','Down since','datetime-local'],['issue','Issue','text'],['details','What happened','textarea'],['vendor','Vendor Actions to Date','textarea'],['patient_impact','Patient Impact','textarea'],['plan','Plan Going Forward','textarea'],['physics_impact','Physics Impact','textarea'],['reported_by','Reported by (initials)','text']];
const DOWNTIME_HINTS={recipients:'name@ufl.edu, name2@ufl.edu',patient_impact:'How many patients are affected and where they were moved. No names, MRNs or birth dates.',plan:'e.g. Field engineer contacted; expected onsite time',physics_impact:'e.g. No PSQA can be run until the machine is back up',vendor:'e.g. Varian helpline called, case # ____; remote session',details:'What was running, the error shown, and what was tried'};
function downtimeAlertButton(){
 const button=el('button');button.id='downtime-alert';button.type='button';button.className='downtime-alert';
 button.innerHTML='<svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" style="vertical-align:-3px;margin-right:6px"><path fill="#d92d20" d="M12 2 1 21h22L12 2z"/><path fill="#fff" d="M11 9h2v6h-2zm0 8h2v2h-2z"/></svg>Send Downtime Alert';
 const {dialog,body}=intakeDialog('downtime-dialog','Send Downtime Alert');
 const form=el('form');const grid=el('div',undefined,'edit-grid');const controls={};
 for(const [key,label,type] of DOWNTIME_FIELDS){
  const wrap=el('div',undefined,type==='textarea'||key==='recipients'?'wide':''),labelNode=el('label',label),control=el(type==='textarea'||type==='select'?type:'input');
  labelNode.htmlFor='downtime-'+key;control.id='downtime-'+key;control.name=key;if(type==='text'||type==='datetime-local')control.type=type;if(type==='textarea')control.rows=3;
  if(type==='select')for(const value of ['Machine down','Limited use','Back in service'])control.append(el('option',value));
  if(DOWNTIME_HINTS[key])control.placeholder=DOWNTIME_HINTS[key];
  if(key==='reported_by'){control.maxLength=12;control.oninput=()=>control.value=control.value.toUpperCase();}
  controls[key]=control;wrap.append(labelNode,control);grid.append(wrap);
 }
 const warning=el('p','Do not include patient names, MRNs or birth dates. Describe patient impact in numbers only.','warning');
 const to=el('p',undefined,'sub'),feedback=el('p');feedback.setAttribute('role','status');
 const send=el('button','Send alert','primary');send.type='submit';
 const mail=el('button','Open in email app');mail.type='button';
 const buttons=el('div',undefined,'controls');buttons.append(send,mail);form.append(warning,grid,to,feedback,buttons);body.append(form);
 const values=()=>Object.fromEntries(new FormData(form));
 const recipients=()=>String(controls.recipients.value||'').split(/[\s,;]+/).filter(Boolean);
 // Same header as the host email: DOWNTIME ALERT: Truebeam 9/12 @10am
 const subject=data=>{const d=data.started?new Date(data.started):new Date(),h=d.getHours()%12||12;return 'DOWNTIME ALERT: '+(data.site||'Truebeam')+' '+(d.getMonth()+1)+'/'+d.getDate()+' @'+h+(d.getMinutes()?':'+String(d.getMinutes()).padStart(2,'0'):'')+(d.getHours()<12?'am':'pm');};
 const text=data=>[subject(data),''].concat(...DOWNTIME_FIELDS.filter(([key])=>key!=='recipients').map(([key,label])=>[label+':',key==='started'&&data[key]?new Date(data[key]).toLocaleString():(data[key]||'-'),''])).join('\n');
 button.onclick=()=>{
  form.reset();feedback.textContent='';
  // Prefill only from a console screenshot fault captured today (therapist entries and older faults are skipped).
  const today=new Date().toDateString();
  const fault=(state?.records||[]).filter(r=>r.kind==='screenshots'&&r.entryType!=='manual'&&r.document_type!=='Therapist entry'&&parsedDate(r.service_date)!==null&&new Date(parsedDate(r.service_date)).toDateString()===today).sort((a,b)=>parsedDate(b.service_date)-parsedDate(a.service_date))[0];
  const local=d=>new Date(d-new Date(d).getTimezoneOffset()*60000).toISOString().slice(0,16);
  controls.recipients.value=(state?.config?.alert_recipients||[]).join(', ');
  controls.site.value='Truebeam';
  controls.started.value=local(fault&&parsedDate(fault.service_date)||Date.now());
  if(fault){
   const codes=[fault.fault_code,fault.additional_codes].filter(Boolean).join(', ');
   controls.issue.value=[fault.fault_name||String(fault.issue||'').split('\n')[0],codes&&'(error '+codes+')'].filter(Boolean).join(' ');
   controls.details.value=[fault.issue,fault.current_status&&'Current status: '+fault.current_status,fault.work_performed&&'Troubleshooting so far: '+fault.work_performed].filter(Boolean).join('\n\n');
   if(fault.worker_initials)controls.reported_by.value=String(fault.worker_initials).split('\n')[0];
  }
  const mailStatus=state?.email_status;
  to.textContent=!mailStatus?'This copy cannot send email. Use Open in email app.':mailStatus.configured?'Sent from the host through '+mailStatus.via+'. Separate addresses with commas. The saved list is in Folder settings > Downtime alert recipients.':'Host email is not set up: use Open in email app.';
  send.disabled=!mailStatus||!mailStatus.configured;
  dialog.showModal();
 };
 mail.onclick=()=>{
  const data=values();
  location.href='mailto:'+encodeURIComponent(recipients().join(';'))+'?subject='+encodeURIComponent(subject(data))+'&body='+encodeURIComponent(text(data));
 };
 form.onsubmit=async event=>{
  event.preventDefault();send.disabled=true;feedback.textContent='Sending…';
  try{const result=await(await api('downtime-alert',values())).json();if(result.error)throw new Error(result.error);dialog.close();notice('Downtime alert sent to '+result.recipients+' recipient'+(result.recipients===1?'':'s')+'.');}
  catch(e){feedback.textContent='Not sent: '+e.message;}finally{send.disabled=false;}
 };
 return button;
}
async function initIntake(){
 const actions=document.querySelector('.exports');
 // Manual work-order import lives in Folder settings; the toolbar slot is the downtime alert.
 const importButton=el('button','Import Varian work orders…');importButton.id='import-files';importButton.type='button';
 const input=el('input');input.type='file';input.multiple=true;input.accept='.pdf';input.hidden=true;input.id='import-file-input';
 importButton.onclick=()=>input.click();input.onchange=async()=>{try{const files=[...input.files];if(files.some(file=>!file.name.toLowerCase().endsWith('.pdf')))throw new Error('Select Varian work order PDF files only.');await importSelectedFiles(files);}catch(e){notice(e.message,true);}finally{input.value='';}};
 const importRow=el('div');importRow.style.marginTop='15px';importRow.append(el('label','Varian work orders'),importButton,input,el('p','Import work order PDFs by hand if a file was missed by folder monitoring.','sub'));
 $('folder-dialog').querySelector('.dialog-body').append(importRow);
 const add=el('button','Add fault','primary');add.id='add-fault';
 actions.prepend(add,downtimeAlertButton());
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
