"""Find explicitly labelled error codes without mistaking dates or measurements for codes."""
import re

# Apply OCR substitutions only inside a labelled numeric code, never across prose.
DIGITS = str.maketrans({'O':'0','o':'0','I':'1','l':'1','i':'1','|':'1','S':'5','s':'5','Z':'2','z':'2','B':'8'})
TOKEN = r'[0-9OoIlisSzZB|][0-9OoIlisSzZB| \t-]{2,15}[0-9OoIlisSzZB|]'
LABEL = r'(?:error[ \t]*(?:code|id)|fault[ \t]*(?:code|id)|interlock[ \t]*(?:code|id)|code|[I1l][Dd])'

def normalize_code(token):
    value = re.sub(r'[ \t-]', '', token).translate(DIGITS)
    # The supplied faults are six-digit interlocks or four-digit application messages.
    return value if value.isdigit() and len(value) in (4,6) else ''

def find_codes(text):
    primary=[]
    additional=[]
    for line in text.splitlines():
        extra = re.match(r'^\s*Additional fault codes\s*:\s*(.*)$',line,re.I)
        if extra:
            for token in extra.group(1).split(','):
                code=normalize_code(token.strip())
                if code and code not in additional: additional.append(code)
            continue
        for match in re.finditer(r'\b'+LABEL+r'\s*[:=#]?\s*('+TOKEN+r')(?![A-Za-z0-9])',line,re.I):
            label = match.group(0).split(':')[0].lower()
            # Bare "ID" in a report could be a patient, work order, or serial number.
            if re.match(r'^\s*[I1l]d\b',match.group(0),re.I) and not re.search(r'^\s*(?:Name|Severity|Impact|CAUSE)\s*:',text,re.I|re.M):
                continue
            code=normalize_code(match.group(1))
            if code and code not in primary:primary.append(code)
    codes=primary+[c for c in additional if c not in primary]
    return (primary[0] if primary else (additional[0] if len(additional)==1 else '')), codes
