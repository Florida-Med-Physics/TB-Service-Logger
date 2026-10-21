"""Decide which imported files belong in the service/fault tables."""
import re
def exclusion_reason(record):
    if record.get('document_type')=='Therapist entry':
        return '' if any(record.get(k) for k in ('issue','fault_code','fault_name')) else 'Empty therapist entry.'
    text=str(record.get('text','') or '')
    issue=str(record.get('issue','') or '').strip()
    codes=' '.join(str(record.get(k,'') or '') for k in ('fault_code','additional_codes'))
    if record.get('kind')=='screenshots':return ''
    header=re.search(r'\b(?:work\s+order\s+information|field\s+service\s+report|service\s+report)\b',text,re.I)
    labelled=re.search(r'\b(?:closure\s+summary|problem\s+description|work\s+performed\s+comments)\b',text,re.I)
    work_order=re.search(r'\bWO[-\s]*\d{5,}\b',str(record.get('work_order',''))+' '+text,re.I)
    details=any(record.get(k) for k in ('issue','work_performed','service_date','engineer','work_order'))
    if details and (header or (work_order and labelled)):return ''
    maintenance=re.search(r'\b(?:PMP|PMI|prevent(?:ive|ative)\s+maintenance)\b',text,re.I)
    form=re.search(r'\b(?:checklist|parameters?)\b',text,re.I)
    asset=re.search(r'\bH\d{6}\b',text)
    if form and (maintenance or asset) and len(text.strip())>=20:return ''
    return 'This file is not a recognizable service or maintenance report.'

def group_screenshot_windows(events,linked=()):
    """Keep each automatic screenshot cluster within five minutes of its first capture."""
    from datetime import datetime
    linked=set(linked);result=[];windows=[]
    def stamp(event):
        try:return datetime.fromisoformat(event.get('service_date','')).timestamp()
        except (ValueError,TypeError):
            for pattern in ('%d-%b-%Y %I:%M:%S %p','%m/%d/%Y %I:%M:%S %p'):
                try:return datetime.strptime(event.get('service_date',''),pattern).timestamp()
                except (ValueError,TypeError):pass
            return None
    ordered=sorted(events,key=lambda e:(stamp(e) is None,stamp(e) or 0,e['id']))
    for event in ordered:
        when=stamp(event)
        if event['kind']!='screenshots' or event.get('document_type')=='Therapist entry' or when is None or any(s['id'] in linked for s in event['sources']):
            result.append(event);continue
        target=next((item for start,item in reversed(windows) if 0<=when-start<=300),None)
        if target is None:
            result.append(event);windows.append((when,event));continue
        target['sources'].extend(event['sources'])
        for field in ('fault_code','additional_codes','fault_name','severity','issue','cause','suggestions','work_performed','worker_initials','error'):
            values=list(dict.fromkeys(v for value in (target.get(field,''),event.get(field,'')) for v in str(value or '').split('\n') if v))
            target[field]='\n'.join(values)
    return result
