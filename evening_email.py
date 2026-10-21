"""Evening summary email of new log entries. Screenshots and OCR text are never included."""
import html, os, smtplib, socket, ssl
from datetime import datetime, timedelta
from email.message import EmailMessage

# Mail server settings live in the host's environment so no password is stored in settings.json.
ENVIRONMENT=('TRUEBEAM_SMTP_HOST','TRUEBEAM_SMTP_PORT','TRUEBEAM_SMTP_SECURITY','TRUEBEAM_SMTP_USER','TRUEBEAM_SMTP_PASSWORD','TRUEBEAM_EMAIL_FROM')
# Only structured or user-entered fields: OCR text from console screenshots (fault name, error details) may show patient information.
FAULT_COLUMNS=[('service_date','Event time'),('fault_code','Error code'),('additional_codes','Additional codes'),('severity','Severity'),('work_performed','Resolution'),('worker_initials','Worker initials')]
SERVICE_COLUMNS=[('service_date','Malfunction start'),('work_order','Work order #'),('case_number','Case #'),('category','Category'),('work_performed','Summary of work'),('engineer','Field engineer'),('service_status','Status')]
DEFAULT_TIME='18:00'

def smtp_settings(environ=os.environ):
    host=environ.get('TRUEBEAM_SMTP_HOST','').strip()
    if not host:return None
    security=environ.get('TRUEBEAM_SMTP_SECURITY','starttls').strip().lower()
    if security not in ('starttls','ssl','none'):raise ValueError('TRUEBEAM_SMTP_SECURITY must be starttls, ssl, or none.')
    port=int(environ.get('TRUEBEAM_SMTP_PORT') or (465 if security=='ssl' else 587 if environ.get('TRUEBEAM_SMTP_USER') else 25))
    user=environ.get('TRUEBEAM_SMTP_USER','').strip()
    sender=environ.get('TRUEBEAM_EMAIL_FROM','').strip() or user
    if not sender:raise ValueError('Set TRUEBEAM_EMAIL_FROM to the sending address.')
    return {'host':host,'port':port,'security':security,'user':user,'password':environ.get('TRUEBEAM_SMTP_PASSWORD',''),'sender':sender}

def parse_time(value):
    value=str(value or DEFAULT_TIME).strip()
    try:return datetime.strptime(value,'%H:%M').strftime('%H:%M')
    except ValueError:raise ValueError('Enter the evening email time as HH:MM.') from None

def due(config,status,now):
    """True once per day after the configured time, retrying every 15 minutes after a failure."""
    if not config.get('evening_email') or not config.get('email_recipients'):return False
    hour,minute=map(int,parse_time(config.get('email_time')).split(':'))
    if now<now.replace(hour=hour,minute=minute,second=0,microsecond=0):return False
    if status.get('last_sent_date')==now.date().isoformat():return False
    attempt=status.get('last_attempt_at')
    return not attempt or now-datetime.fromisoformat(attempt)>=timedelta(minutes=15)

def new_entries(records,since):
    return [r for r in records if str(r.get('imported') or '')>=since.strftime('%Y-%m-%dT%H:%M:%S')]

def _rows(records,columns):
    return [[str(r.get(key) or '').replace('\n',' ').strip() or '-' for key,_ in columns] for r in records]

def build_message(records,recipients,sender,since,now,test=False):
    faults=[r for r in records if r['kind']=='screenshots'];reports=[r for r in records if r['kind']=='reports']
    subject=('TEST · ' if test else '')+'TrueBeam service log · '+now.strftime('%d %b %Y')+' · '+str(len(faults))+' fault'+('' if len(faults)==1 else 's')+', '+str(len(reports))+' service report'+('' if len(reports)==1 else 's')
    period='New entries since '+since.strftime('%d %b %Y %H:%M')+'.'
    footer='Screenshots and screenshot text are not included. Open the TrueBeam Service Log for full details. Sent by the TrueBeam Service Log host on '+socket.gethostname()+'.'
    text=[('This is a test of the evening email.\n' if test else '')+period,'']
    body=['<p>'+('<b>This is a test of the evening email.</b><br>' if test else '')+html.escape(period)+'</p>']
    for title,items,columns in (('Fault reports',faults,FAULT_COLUMNS),('Service reports',reports,SERVICE_COLUMNS)):
        text.append(title+' ('+str(len(items))+')')
        body.append('<h3 style="font-family:Arial;margin:18px 0 6px">'+title+' ('+str(len(items))+')</h3>')
        if not items:
            text+=['  None',''];body.append('<p style="font-family:Arial;color:#555">None</p>');continue
        rows=_rows(items,columns)
        text+=['  '+' | '.join(label+': '+value for (_,label),value in zip(columns,row)) for row in rows]+['']
        cell='style="border:1px solid #cad7e0;padding:5px 8px;text-align:left;vertical-align:top"'
        body.append('<table style="border-collapse:collapse;font-family:Arial;font-size:13px"><tr>'+''.join('<th '+cell+'>'+html.escape(label)+'</th>' for _,label in columns)+'</tr>'+''.join('<tr>'+''.join('<td '+cell+'>'+html.escape(value)+'</td>' for value in row)+'</tr>' for row in rows)+'</table>')
    text.append(footer);body.append('<p style="font-family:Arial;color:#555;font-size:12px">'+html.escape(footer)+'</p>')
    message=EmailMessage();message['Subject']=subject;message['From']=sender;message['To']=', '.join(recipients)
    message.set_content('\n'.join(text));message.add_alternative('<html><body>'+''.join(body)+'</body></html>',subtype='html')
    return message

def send(message,settings,timeout=30):
    context=ssl.create_default_context()
    connect=smtplib.SMTP_SSL if settings['security']=='ssl' else smtplib.SMTP
    with connect(settings['host'],settings['port'],timeout=timeout,**({'context':context} if settings['security']=='ssl' else {})) as smtp:
        if settings['security']=='starttls':
            smtp.ehlo()
            # Internal relays on port 25 often lack TLS; use it whenever the server offers it.
            if smtp.has_extn('starttls'):smtp.starttls(context=context);smtp.ehlo()
            elif settings['user']:raise ValueError('The mail server does not offer STARTTLS; refusing to send the password unencrypted.')
        if settings['user']:smtp.login(settings['user'],settings['password'])
        smtp.send_message(message)
