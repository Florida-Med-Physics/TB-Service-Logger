/* Common validation and filename timestamps used by every delivery format. */
function uiFilenameTime(path){
 const name=String(path||'').split(/[\\/]/).pop(),explicit=/(?<!\d)(20\d{2})[_-](\d{2})[_-](\d{2})[ _T]+(\d{2})[_.:-](\d{2})[_.:-](\d{2})(?:[_.](\d{3,6}))?(?!\d)/g;
 let matches=[...name.matchAll(explicit)];
 if(!matches.length)matches=[...name.matchAll(/(?<!\d)(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{3,6})?(?!\d)/g)];
 for(const m of matches.reverse()){
  const parts=m.slice(1,7).map(Number),d=new Date(Date.UTC(parts[0],parts[1]-1,...parts.slice(2)));
  if(d.getUTCFullYear()!==parts[0]||d.getUTCMonth()+1!==parts[1]||d.getUTCDate()!==parts[2]||parts[3]>23||parts[4]>59||parts[5]>59)continue;
  return m[1]+'-'+m[2]+'-'+m[3]+'T'+m[4]+':'+m[5]+':'+m[6]+(m[7]?'.'+m[7].slice(0,3).padEnd(3,'0'):'');
 }
 return '';
}
function uiExclusionReason(r){
 if(r.entryType==='manual'||r.document_type==='Therapist entry')return r.issue||r.fault_code||r.fault_name?'':'Empty therapist entry.';
 const text=String(r.text||''),issue=String(r.issue||''),codes=String(r.fault_code||'')+' '+String(r.additional_codes||'');
 if(r.kind==='screenshots')return '';
 const header=/\b(?:work\s+order\s+information|field\s+service\s+report|service\s+report)\b/i.test(text),labelled=/\b(?:closure\s+summary|problem\s+description|work\s+performed\s+comments)\b/i.test(text),wo=/\bWO[-\s]*\d{5,}\b/i.test(String(r.work_order||'')+' '+text);
 if([r.issue,r.work_performed,r.service_date,r.engineer,r.work_order].some(Boolean)&&(header||(wo&&labelled)))return '';
 if(/\b(?:checklist|parameters?)\b/i.test(text)&&(/\b(?:PMP|PMI|prevent(?:ive|ative)\s+maintenance)\b/i.test(text)||/\bH\d{6}\b/.test(text))&&text.trim().length>=20)return '';
 return 'This file is not a recognizable service or maintenance report.';
}
function uiEventTime(value){
 const text=String(value||'').split(/Additional fault codes:/i)[0].trim();
 const date=new Date(text);
 return Number.isNaN(date.getTime())?(text.split('\n')[0]||'-'):date.toLocaleDateString()+'\n'+date.toLocaleTimeString();
}

function uiGroupScreenshotWindows(events){
 const result=[],windows=[],linked=new Set(events.filter(e=>e.linkTarget).map(e=>e.linkTarget));
 const stamp=e=>{const value=Date.parse(e.service_date||'');return Number.isFinite(value)?value:null;};
 for(const event of events.slice().sort((a,b)=>(stamp(a)??Infinity)-(stamp(b)??Infinity)||a.id-b.id)){
  const when=stamp(event);
  if(event.kind!=='screenshots'||event.entryType==='manual'||event.document_type==='Therapist entry'||event.linkTarget||linked.has(event.id)||when===null){result.push(event);continue;}
  const found=windows.slice().reverse().find(([start])=>when-start>=0&&when-start<=300000);
  if(!found){result.push(event);windows.push([when,event]);continue;}
  const target=found[1];target.sources.push(...event.sources);target.recordIds.push(...event.recordIds);
  for(const field of ['fault_code','additional_codes','fault_name','severity','issue','cause','suggestions','work_performed','worker_initials','error'])target[field]=[...new Set([target[field],event[field]].flatMap(v=>String(v||'').split('\n')).filter(Boolean))].join('\n');
 }
 return result;
}
