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
 const input=el('input');input.id='shared-output';input.value=state.config.output;input.style.width='calc(100% - 115px)';
 const choose=el('button','Choose…');choose.id='choose-report';choose.onclick=async()=>{try{const result=await(await api('browse',{kind:'output'})).json();if(result.path)input.value=result.path;}catch(e){notice(e.message,true);}};
 row.append(label,input,choose,el('p','All applications use these host paths. The report reads new data every minute without replacing the open workbook.','sub'));folderBody.append(row);
 const logsRow=el('div');logsRow.style.marginTop='15px';const logsLabel=el('label','Logs folder');const logsInput=el('input');logsInput.value=state.config.logs||'';logsInput.style.width='calc(100% - 115px)';const logsChoose=el('button','Choose…');logsChoose.onclick=async()=>{try{const result=await(await api('browse',{kind:'logs'})).json();if(result.path)logsInput.value=result.path;}catch(e){notice(e.message,true);}};logsRow.append(logsLabel,logsInput,logsChoose,el('p','New timestamped Excel logs are saved when additional entries are added.','sub'));folderBody.append(logsRow);
 $('reports').value=state.config.reports;$('screenshots').value=state.config.screenshots;
 $('start').onclick=()=>command('configure',{reports:$('reports').value.trim(),screenshots:$('screenshots').value.trim(),output:input.value.trim(),logs:logsInput.value.trim()});
 if(!state.admin){
  for(const node of [$('reports'),$('screenshots'),input,logsInput])node.readOnly=true;
  for(const button of [...document.querySelectorAll('.browse'),$('start'),$('pause'),$('retry'),logsChoose]){button.disabled=true;button.title='Host administrator only';}
 }
 $('excel').onclick=async()=>{await api('export',{});notice('Report data refresh requested. The existing workbook is preserved, including while open in Excel.');};
 setInterval(poll,2000);
}
