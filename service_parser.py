"""Extract labelled Varian service-report fields; retain source wording for review."""
import re

def clean(value):
    return re.sub(r'[ \t]+',' ',value).strip()

def parse_service(text):
    result={}
    modern='Work Order Information' in text
    if not modern:
        upper=text[:1500].upper()
        kind='PMP checklist' if 'CHECKLIST' in upper else 'PMP parameters'
        result.update(document_type=kind,category='PMP attachment',issue=kind)
        # Some exported PMP forms duplicate each word in their text layer.
        asset=re.search(r'\bH\d{6}',text)
        if asset:result['machine']=asset.group()
        date_pattern=r'PRINT\s*(?:PRINT)?\s*DATE\s*:\s*(?:DATE\s*:)?\s*(\w{3}/\d{1,2}/\d{4})' if kind=='PMP checklist' else r'\bDATE\s*:\s*(?:DATE\s*:)?\s*(\w{3}/\d{1,2}/\d{4})'
        date=re.search(date_pattern,text,re.I)
        if date:result['service_date']=date.group(1)
        result['service_status']='Attachment'
        return result
    result['document_type']='Work order'
    patterns={
        'work_order':r'\bWO-\d+',
        'case_number':r'\bCase(?: Number)?\s+(\d{6,10})',
        'machine':r'(?:Asset|Installed Product)\s+(H\d{6})',
        'engineer':r'(?:Service Resource|Field Engineer)\s+(.+?)(?=\s{3,}|\n|Purchase Order)',
        'service_date':r'Malfunction Start\s*:?\s*(\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2}\s*[AP]M)?)',
        'machine_release':r'Machine Release(?: Time)?\s*:?\s*(\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2}\s*[AP]M)?)',
        'work_hours':r'Total Work Hours\s+(\d+(?:\.\d+)?)',
        'downtime_hours':r'Agreed Downtime\s+(\d+(?:\.\d+)?)',
    }
    for field,pattern in patterns.items():
        match=re.search(pattern,text,re.I)
        if match:result[field]=clean(match.group(1) if match.lastindex else match.group())
    for field,start,end in [
        ('issue','Subject',r'Closure Summary'),
        ('work_performed','Closure Summary',r'Follow Up(?:\s+Notables)?|Work Order Times'),
        ('parts_installed','Parts Installed',r'Quality Statements|Customer is responsible'),
    ]:
        match=re.search(r'\b'+start+r'\s+(.*?)(?=\b(?:'+end+r'))',text,re.S|re.I)
        if match:
            value=match.group(1)
            if field=='parts_installed':
                lines=[]
                for line in value.splitlines():
                    if re.match(r'^\s*[A-Z0-9-]{6,}\s+',line) and 'Part Number' not in line:
                        lines.append(clean(line))
                value='\n'.join(lines)
            else:
                value=re.sub(r'\s*Product\s*>\s*.*','',value,flags=re.S)
                value=clean(value)
            result[field]=value
    if not result.get('issue'):
        match=re.search(r'Problem Description\s+(.*?)(?=Work Performed Comments)',text,re.S|re.I)
        if match:result['issue']=clean(match.group(1))
        match=re.search(r'Work Performed Comments\s+(.*?)(?=Follow Up Comments)',text,re.S|re.I)
        if match:result['work_performed']=clean(match.group(1))
    # Legacy reports lay the dates and hours out as a horizontal table.
    if not result.get('service_date'):
        match=re.search(r'Machine Release Time\s*\n([^\n]+)',text)
        if match:
            dates=re.findall(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}',match.group(1))
            if len(dates)==4:result.update(service_date=dates[2],machine_release=dates[3])
    if not result.get('work_hours'):
        match=re.search(r'Agreed Downtime\s*\n\s*(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)(?:[ \t]+(\d+\.\d+))?',text)
        if match:
            result.pop('downtime_hours',None)
            result['work_hours']=match.group(2)
            if match.group(4):result['downtime_hours']=match.group(4)
    subject=result.get('issue','')
    details=subject+' '+result.get('work_performed','')
    category='Service'
    for pattern,label in [
        (r'\bPMP\b','PMP'),(r'LaserGuard','LaserGuard'),(r'SF6|waveguide','SF6 / Waveguide'),
        (r'MLC|collimator','MLC / Collimator'),(r'\bXI\b|CBCT|imaging|KVS','Imaging'),
        (r'thyratron|modulator|DeQ','Modulator'),(r'couch|encoder','Couch'),(r'\bBGM\b|gun|target','Beam generation')]:
        if re.search(pattern,details,re.I):category=label;break
    result['category']=category
    # Unlabelled six-digit numbers are accepted only in fault-related subject/narrative phrases.
    codes=[]
    for match in re.finditer(r'(?:faults?|error|ID#?|BGM|COL|XI|EGN|STN)\s*[:#-]?\s*((?:\d{6})(?:[ ,;&]+\d{6})*)',details,re.I):
        for code in re.findall(r'\b\d{6}\b',match.group(1)):
            if code not in codes:codes.append(code)
    for code in re.findall(r'\b\d{6}\b',subject):
        if code not in codes:codes.append(code)
    if codes:
        result['fault_code']=codes[0];result['additional_codes']=', '.join(codes[1:])
    result['service_status']='Closure documented' if result.get('work_performed') else 'Needs review'
    return result
