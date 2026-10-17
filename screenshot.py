"""Only OCR a detected TrueBeam tooltip/error panel, excluding patient areas."""
import os, subprocess, sys, tempfile
from pathlib import Path

def panel(image):
    from PIL import Image
    image = image.convert('RGB')
    w,h = image.size
    # These screens span two monitors. Restrict detection to the treatment monitor.
    scan = image.crop((0, int(h*.45), int(w*.51), int(h*.9)))
    from collections import Counter
    colors=Counter(scan.getdata())
    candidates=[(count,color) for color,count in colors.items() if color[0]>235 and color[1]>235 and 170<color[2]<235]
    if candidates:
        count,color=max(candidates)
        if count>w*h*.003:
            from PIL import ImageDraw
            # Separate the connected tooltip background from identical colors in MLC graphics.
            pixels=scan.load()
            best=(0,0,0)
            for y in range(scan.height):
                start=None
                for x in range(scan.width+1):
                    match=x<scan.width and pixels[x,y]==color
                    if match and start is None: start=x
                    if not match and start is not None:
                        if x-start>best[0]: best=(x-start,start,y)
                        start=None
            if best[0]>w*.08:
                mask=Image.new('L',scan.size)
                mask.putdata([255 if pixel==color else 0 for pixel in scan.getdata()])
                ImageDraw.floodfill(mask,(best[1],best[2]),128)
                bounds=mask.point(lambda value:255 if value==128 else 0).getbbox()
                if bounds: return scan.crop(bounds)
    # Application Messages dialog in the supplied full-screen layout.
    crop=image.crop((int(w*.115),int(h*.46),int(w*.315),int(h*.69)))
    text=recognize(crop)
    if 'CTRL_' in text or ('CAUSE' in text.upper() and 'ID' in text.upper()):
        return crop
    raise ValueError('No fault tooltip or error dialog detected. Source retained for manual review; patient regions were not extracted.')

def recognize(image):
    from PIL import ImageOps
    image=ImageOps.grayscale(image)
    image=image.resize((image.width*3,image.height*3))
    if sys.platform=='darwin':
        fd, name=tempfile.mkstemp(suffix='.png'); os.close(fd)
        try:
            image.save(name)
            helper=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'ocr_macos'
            command=[str(helper),name] if helper.is_file() else ['swift',str(Path(__file__).with_name('ocr_macos.swift')),name]
            result=subprocess.run(command,capture_output=True,text=True,timeout=120)
            if result.returncode: raise RuntimeError(result.stderr[-600:])
            return result.stdout
        finally: os.unlink(name)
    if sys.platform=='win32':
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        global _rapid_ocr
        if '_rapid_ocr' not in globals():_rapid_ocr=RapidOCR()
        result,_=_rapid_ocr(np.asarray(image))
        return '\n'.join(item[1] for item in (result or []))
    import pytesseract
    if sys.platform=='win32':
        candidates=[os.environ.get('TESSERACT_CMD',''),str(Path(__file__).parent/'ocr'/'tesseract.exe'),str(Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Tesseract-OCR'/'tesseract.exe')]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                pytesseract.pytesseract.tesseract_cmd=candidate
                break
    try: return pytesseract.image_to_string(image,config='--psm 6')
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError('Install Tesseract OCR and add it to PATH, then retry failed imports.')

def extract_screenshot(image):
    from fault_codes import normalize_code, find_codes
    w,h=image.size
    # Fault-list rows occupy this strip on the supplied dual-monitor treatment layout.
    # Excludes patient demographics, imaging, and tooltip suggestions.
    fault_list=image.crop((0,int(h*.615),int(w*.123),int(h*.685)))
    list_text=recognize(fault_list)
    codes=[]
    import re
    for line in list_text.splitlines():
        match=re.match(r'^\s*[oO○•]?\s*([0-9OoIlisSzZB|][0-9OoIlisSzZB| \t-]{2,15}[0-9OoIlisSzZB|])(?:\s+[A-Z]{2,5}|\s*$)',line)
        if match:
            code=normalize_code(match.group(1))
            if code and code not in codes: codes.append(code)
    try:
        detail=panel(image)
        text=recognize(detail)
        # Retry the compact ID header at a different scale when the main OCR misses it.
        if not find_codes(text)[0]:
            header=detail.crop((0,0,detail.width,min(detail.height,max(35,int(detail.height*.22)))))
            retry=recognize(header)
            if find_codes(retry)[0]: text=retry+'\n'+text
    except ValueError:
        if not codes: raise
        text='No detailed fault tooltip detected. Review the fault list and original source.'
    if codes: text+='\nAdditional fault codes: '+', '.join(codes)
    return text
