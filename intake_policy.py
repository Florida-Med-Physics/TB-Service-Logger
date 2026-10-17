"""Decide which imported files belong in the service/fault tables."""
import re
def exclusion_reason(record):
    if record.get('document_type')=='Therapist entry':
        return '' if any(record.get(k) for k in ('issue','fault_code','fault_name')) else 'Empty therapist entry.'
    text=str(record.get('text','') or '')
    issue=str(record.get('issue','') or '').strip()
    codes=' '.join(str(record.get(k,'') or '') for k in ('fault_code','additional_codes'))
    if record.get('kind')=='screenshots':
        if re.search(r'\b(?:\d{4}|\d{6})\b',codes):return ''
        if record.get('fault_name'):return ''
        negative=re.search(r'\b(?:no|zero)\s+(?:active\s+)?(?:faults?|errors?|interlocks?)\b',issue,re.I)
        if issue and not negative and (record.get('severity') or record.get('cause') or record.get('impact')
                                      or re.search(r'\b(?:fault|error|interlock|failed|failure|mismatch)\b',issue,re.I)):
            return ''
        return 'No identifiable fault was found in this screenshot.'
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
