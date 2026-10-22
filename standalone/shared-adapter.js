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
 command=async(action,body={})=>{try{const result=await(await api(action,body)).json();await poll();return result;}catch(e){notice(e.message,true);return null;}};
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
 const logsRow=el('div');logsRow.style.marginTop='15px';const logsLabel=el('label','Logs folder');const logsInput=el('input');logsInput.value=state.config.logs||'';logsInput.style.width='calc(100% - 115px)';const logsChoose=el('button','Choose…');logsChoose.onclick=async()=>{try{const result=await(await api('browse',{kind:'logs'})).json();if(result.path)logsInput.value=result.path;}catch(e){notice(e.message,true);}};logsRow.append(logsLabel,logsInput,logsChoose,el('p','New timestamped Excel logs are saved whenever fault or service report data changes.','sub'));folderBody.insertBefore(logsRow,$('email-settings'));
 $('reports').value=state.config.reports;$('screenshots').value=state.config.screenshots;
 $('start').onclick=()=>command('configure',{reports:$('reports').value.trim(),screenshots:$('screenshots').value.trim(),logs:logsInput.value.trim()});
 if(!state.admin){
  for(const node of [$('reports'),$('screenshots'),logsInput,$('email-recipients'),$('email-time'),$('alert-recipients')])node.readOnly=true;
  for(const button of [...document.querySelectorAll('.browse'),$('start'),$('pause'),$('retry'),logsChoose,$('evening-email'),$('save-email'),$('test-email'),$('save-alerts')]){button.disabled=true;button.title='Host administrator only';}
 }
 $('excel').onclick=()=>{notice('Exporting the log to Downloads…');download('excel','TrueBeam_Service_Log_'+exportStamp()+'.xlsx');};
 setInterval(poll,2000);
}
