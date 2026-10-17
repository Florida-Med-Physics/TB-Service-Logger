"""Native TrueBeam desktop application for Windows and macOS."""
import argparse, json, os, queue, subprocess, sys, tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from desktop_worker import DesktopWorker, data_home
from report_export import date_value

REPORT_COLUMNS=[
 ('service_date','Start / release',.11),('work_order','Work order / case',.11),
 ('category','Category',.09),('issue','Subject / error codes',.16),
 ('work_performed','Summary of work',.18),('parts_installed','Parts installed',.10),
 ('engineer','Engineer / hours',.11),('service_status','Status',.07),('sources','Service report',.07)]
FAULT_COLUMNS=[
 ('service_date','Event date',.10),('fault_code','Error code',.08),
 ('fault_name','Fault name / severity',.13),('issue','Error Details',.18),
 ('suggestions','SUGGESTED SOLUTION',.18),('work_performed','OUR SOLUTION',.15),
 ('worker_initials','Initials',.06),('sources','Screenshot',.12)]
LABELS=dict((k,label) for k,label,_ in REPORT_COLUMNS+FAULT_COLUMNS)
LABELS.update(machine_release='Machine release',case_number='Case number',additional_codes='Additional error codes',
              work_hours='Work hours',downtime_hours='Downtime hours',severity='Severity',notes='Notes')
def open_file(path):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError('File unavailable: '+str(path))
    if sys.platform=='win32':os.startfile(str(path))
    elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
    else:subprocess.Popen(['xdg-open',str(path)])

class App(tk.Tk):
    def __init__(self,home=None):
        super().__init__()
        self.title('TrueBeam Service Log')
        self.geometry('1450x900');self.minsize(950,600)
        self.worker=DesktopWorker(home);self.records=[];self.config={}
        self.closing=False;self.sorts={'reports':('service_date',True),'screenshots':('service_date',True)}
        self.message=tk.StringVar(value='Opening local database…')
        self.save_message=tk.StringVar(value='Export Report overwrites the same Excel log every 10 minutes.')
        self.search=tk.StringVar();self.search.trace_add('write',lambda *_:self.render())
        self.preferences=self.worker.home/'appearance.json'
        try:self.dark=json.loads(self.preferences.read_text()).get('dark',False)
        except (OSError,ValueError):self.dark=False
        self.build();self.apply_theme()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.worker.thread.start();self.after(150,self.receive)

    def build(self):
        self.header=tk.Frame(self,bg='#122d59',padx=22,pady=16);self.header.pack(fill='x')
        tk.Label(self.header,text='UFHPTI PHYSICS',fg='#ff9b61',bg='#122d59',font=('Arial',10,'bold')).pack(anchor='w')
        tk.Label(self.header,text='TrueBeam Service Log',fg='white',bg='#122d59',font=('Arial',24,'bold')).pack(side='left')
        tk.Button(self.header,text='Dark mode',command=self.toggle_theme,bg='#122d59',fg='white').pack(side='right')
        tk.Frame(self,bg='#fa7021',height=4).pack(fill='x')
        tools=ttk.Frame(self,padding=(16,12));tools.pack(fill='x')
        ttk.Button(tools,text='Folder settings',command=self.settings).pack(side='left')
        ttk.Button(tools,text='Scan now',command=lambda:self.worker.submit('scan')).pack(side='left',padx=6)
        ttk.Button(tools,text='Pause',command=lambda:self.worker.submit('pause')).pack(side='left')
        ttk.Button(tools,text='Import details',command=self.import_details).pack(side='left',padx=6)
        ttk.Button(tools,text='Export Report',command=lambda:self.worker.submit('export')).pack(side='right')
        ttk.Label(self,textvariable=self.save_message,padding=(16,0)).pack(anchor='w')
        bar=ttk.Frame(self,padding=(16,10));bar.pack(fill='x')
        ttk.Label(bar,text='Search').pack(side='left')
        ttk.Entry(bar,textvariable=self.search).pack(side='left',fill='x',expand=True,padx=10)
        ttk.Label(bar,text='Double-click a value to edit; double-click a filename to open.').pack(side='right')
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill='both',expand=True,padx=16,pady=(0,8))
        self.trees={}
        for kind,title,columns in [('reports','Service Reports',REPORT_COLUMNS),('screenshots','Fault Reports',FAULT_COLUMNS)]:
            frame=ttk.Frame(self.tabs);self.tabs.add(frame,text=title)
            tree=ttk.Treeview(frame,columns=[c[0] for c in columns],show='headings',selectmode='browse')
            scroll=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right',fill='y');tree.pack(fill='both',expand=True)
            for key,label,fraction in columns:
                tree.heading(key,text=label+' ↕',command=lambda k=kind,f=key:self.sort(k,f))
                tree.column(key,width=int(1400*fraction),minwidth=30,stretch=True,anchor='w')
            tree.bind('<Configure>',lambda event,k=kind:self.resize(k,event.width))
            tree.bind('<Double-1>',lambda event,k=kind:self.edit_cell(k,event))
            tree.bind('<Return>',lambda event,k=kind:self.edit_selected(k))
            self.trees[kind]=tree
        ttk.Label(self,textvariable=self.message,padding=(16,5),wraplength=1300).pack(fill='x')
        ttk.Label(self,text='Local disk database · originals are never modified · '+str(self.worker.home),padding=(16,4)).pack(anchor='w')

    def apply_theme(self):
        bg='#101c2d' if self.dark else '#f3f5f8';card='#1d3049' if self.dark else '#ffffff'
        fg='#e1eaf2' if self.dark else '#122d59'
        self.configure(bg=bg)
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',background=bg,foreground=fg,font=('Arial',10))
        style.configure('Treeview',background=card,fieldbackground=card,foreground=fg,rowheight=46,borderwidth=0)
        style.configure('Treeview.Heading',background='#223c61' if self.dark else '#eaf0f8',foreground=fg,font=('Arial',9,'bold'),padding=(5,10))
        style.map('Treeview',background=[('selected','#315c92')],foreground=[('selected','white')])
        style.configure('TNotebook.Tab',padding=(16,10))
        style.configure('TEntry',fieldbackground=card,foreground=fg)
        style.configure('TButton',padding=7)

    def toggle_theme(self):
        self.dark=not self.dark;self.preferences.write_text(json.dumps({'dark':self.dark}));self.apply_theme()

    def resize(self,kind,width):
        columns=REPORT_COLUMNS if kind=='reports' else FAULT_COLUMNS
        for key,_,fraction in columns:self.trees[kind].column(key,width=max(30,int((width-8)*fraction)))

    def receive(self):
        try:
            while True:
                event=self.worker.events.get_nowait()
                if event['type']=='closed':
                    if self.closing:self.destroy();return
                elif event['type']=='error':
                    self.message.set(event['message'])
                    if not self.closing:messagebox.showerror('TrueBeam',event['message'],parent=self)
                elif event['type']=='progress':self.message.set(event['message'])
                elif event['type']=='state':
                    self.records=event['records'];self.config=event['config']
                    if event.get('message'):self.message.set(event['message'])
                    if event.get('last_save'):self.save_message.set('Export Report saved '+event['last_save']+' · next save in 10 minutes · '+self.config.get('output',''))
                    self.render()
        except queue.Empty:pass
        if self.winfo_exists():self.after(150,self.receive)

    def sort(self,kind,key):
        old,reverse=self.sorts[kind];self.sorts[kind]=(key,not reverse if old==key else False);self.render()

    def display(self,r,key):
        value=str(r.get(key,'') or '')
        if key=='sources':value=' · '.join(Path(s['path']).name for s in r['sources'])
        elif key=='engineer':value=' · '.join(v for v in (value,str(r.get('work_hours',''))+' hrs' if r.get('work_hours') else '') if v)
        elif key=='fault_code':value=', '.join(v for v in (value,r.get('additional_codes','')) if v)
        elif key=='service_status':value=value or r.get('review','')
        return ' '.join(value.split()) or '-'

    def render(self):
        query=self.search.get().strip().casefold()
        for kind,tree in self.trees.items():
            selected=tree.selection();position=tree.yview()
            rows=[r for r in self.records if r['kind']==kind and (not query or query in json.dumps(r).casefold())]
            key,reverse=self.sorts[kind]
            def value(r):
                text=self.display(r,key)
                if key=='service_date':return str(date_value(r.get(key,'')))
                return text.casefold()
            rows.sort(key=value,reverse=reverse)
            tree.delete(*tree.get_children())
            for r in rows:tree.insert('', 'end',iid=str(r['id']),values=[self.display(r,k) for k in tree['columns']])
            if selected and tree.exists(selected[0]):tree.selection_set(selected)
            if position:tree.yview_moveto(position[0])
            index=0 if kind=='reports' else 1
            self.tabs.tab(index,text=('Service Reports' if kind=='reports' else 'Fault Reports')+'  '+str(len(rows)))

    def settings(self):
        popup=tk.Toplevel(self);popup.title('Folder settings');popup.geometry('800x300');popup.transient(self);popup.grab_set()
        values={}
        def choose(key):
            if key=='output':
                path=filedialog.asksaveasfilename(parent=popup,title='Choose Export Report',defaultextension='.xlsx',filetypes=[('Excel workbook','*.xlsx')],initialfile=Path(values[key].get()).name or 'TrueBeam Service Log.xlsx')
            else:path=filedialog.askdirectory(parent=popup,title='Choose '+('service-report' if key=='reports' else 'screenshot')+' folder',initialdir=values[key].get() or str(Path.home()))
            if path:values[key].set(path)
        for i,(key,label) in enumerate([('reports','Service-report folder'),('screenshots','Screenshot folder'),('output','Export Report')]):
            values[key]=tk.StringVar(value=self.config.get(key,str(self.worker.home/'TrueBeam Service Log.xlsx') if key=='output' else ''))
            ttk.Label(popup,text=label).grid(row=i,column=0,padx=12,pady=12,sticky='w')
            ttk.Entry(popup,textvariable=values[key]).grid(row=i,column=1,sticky='ew',padx=5)
            ttk.Button(popup,text='Browse…',command=lambda k=key:choose(k)).grid(row=i,column=2,padx=12)
        popup.columnconfigure(1,weight=1)
        ttk.Label(popup,text='Paths are remembered after Save & Monitor. The same Excel file is overwritten every 10 minutes.',wraplength=750).grid(row=3,column=0,columnspan=3,padx=12,pady=8)
        def save():
            data={key:v.get().strip() for key,v in values.items()}
            for key in ('reports','screenshots'):
                if not Path(data[key]).is_dir():messagebox.showerror('Folder unavailable','Choose an accessible '+key+' folder.',parent=popup);return
            self.worker.submit('configure',**data);popup.destroy()
        ttk.Button(popup,text='Save & Monitor',command=save).grid(row=4,column=2,padx=12,pady=8)

    def import_details(self):
        popup=tk.Toplevel(self);popup.title('Import details');popup.geometry('1000x600')
        text=tk.Text(popup,wrap='word',padx=15,pady=15);text.pack(fill='both',expand=True)
        for record in self.records:
            for source in record['sources']:
                text.insert('end',source['path']+'\n'+(source['error'] or 'Imported successfully.')+'\n\n')
        text.configure(state='disabled')
        ttk.Button(popup,text='Retry failed imports',command=lambda:self.worker.submit('retry')).pack(pady=8)
        ttk.Button(popup,text='Open application log',command=lambda:self.open_source(self.worker.home/'application.log')).pack(pady=4)

    def open_source(self,path):
        try:open_file(path)
        except Exception as exc:messagebox.showerror('Source unavailable',str(exc),parent=self)

    def edit_selected(self,kind):
        tree=self.trees[kind]
        if tree.selection():self.edit(kind,int(tree.selection()[0]),'issue')

    def edit_cell(self,kind,event):
        tree=self.trees[kind];row=tree.identify_row(event.y);col=tree.identify_column(event.x)
        if row and col:self.edit(kind,int(row),tree['columns'][int(col[1:])-1])

    def edit(self,kind,record_id,key):
        record=next((r for r in self.records if r['id']==record_id),None)
        if not record:return
        popup=tk.Toplevel(self);popup.title(LABELS.get(key,key));popup.geometry('800x500');popup.transient(self);popup.grab_set()
        if key=='sources':
            ttk.Label(popup,text='Original source files',font=('Arial',14,'bold')).pack(anchor='w',padx=18,pady=14)
            for source in record['sources']:
                ttk.Button(popup,text=Path(source['path']).name,command=lambda p=source['path']:self.open_source(p)).pack(anchor='w',padx=18,pady=7)
                if source['error']:ttk.Label(popup,text=source['error'],wraplength=740).pack(anchor='w',padx=18)
            return
        fields={'service_date':['service_date','machine_release'] if kind=='reports' else ['service_date'],
                'work_order':['work_order','case_number'],'fault_code':['fault_code','additional_codes'],
                'engineer':['engineer','work_hours','downtime_hours'],'fault_name':['fault_name','severity']}.get(key,[key])
        body=ttk.Frame(popup,padding=18);body.pack(fill='both',expand=True);inputs={}
        for field in fields:
            ttk.Label(body,text=('OUR SOLUTION' if kind=='screenshots' and field=='work_performed' else LABELS.get(field,field))).pack(anchor='w',pady=(0,4))
            text=tk.Text(body,height=12 if len(fields)==1 else 3,wrap='word',font=('Arial',12),undo=True)
            text.insert('1.0',record.get(field,'') or '');text.pack(fill='both',expand=True,pady=(0,12));inputs[field]=text
        def save():
            for field,text in inputs.items():
                value=text.get('1.0','end-1c').strip()
                if field=='worker_initials':value=value.upper()[:12]
                self.worker.submit('update',id=record_id,field=field,value=value)
            popup.destroy()
        ttk.Button(popup,text='Save',command=save).pack(side='right',padx=18,pady=10)
        ttk.Button(popup,text='Cancel',command=popup.destroy).pack(side='right',pady=10)

    def close(self):
        if self.closing:return
        self.closing=True;self.message.set('Saving pending changes and closing…');self.worker.submit('stop')
        # Worker finishes the current import and atomic save before closing.

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--self-test-report')
    args=parser.parse_args()
    if args.self_test_report:
        import tempfile
        from PIL import Image, ImageDraw, ImageFont
        from screenshot import recognize
        from core import extract
        from report_export import write_report
        import pymupdf
        with tempfile.TemporaryDirectory() as folder:
            image=Image.new('RGB',(1400,220),'white');draw=ImageDraw.Draw(image)
            draw.text((20,20),'ID: 420219',font=ImageFont.load_default(size=48),fill='black')
            text=recognize(image)
            if '420219' not in text:raise RuntimeError('Bundled screenshot OCR failed: '+text)
            pdf=Path(folder)/'sample.pdf'
            doc=pymupdf.open();page=doc.new_page();page.insert_text((50,50),'PDF import test 420219');doc.save(pdf);doc.close()
            if '420219' not in extract(pdf):raise RuntimeError('Bundled PDF import failed.')
            write_report([],Path(folder)/'test.xlsx')
        Path(args.self_test_report).write_text(json.dumps({'pdf':True,'ocr':True,'xlsx':True,'platform':sys.platform}))
        return
    app=App(args.data_dir)
    if args.smoke_test:app.after(1800,app.close)
    app.mainloop()
if __name__=='__main__':main()
