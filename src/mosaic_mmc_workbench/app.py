"""Optional dark native UI. All assessments call the shared headless implementation."""
from __future__ import annotations
import json
from pathlib import Path
import concurrent.futures
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from mosaic_mmc_t4.common import *
from mosaic_mmc_t4.views import assess_view,reader_for_sample
from mosaic_mmc_t4.work import claim_contracts
from mosaic_mmc_t4.abi import capabilities
from mosaic_mmc_t4.exports import LocalExport
from mosaic_mmc.cli import read_local
from .model import Workbench

BG='#111722';PANEL='#1b2533';FG='#e7edf5';MUTED='#a8b7cb';ACCENT='#7fcee8';WARN='#e6bf77'
PAGES=('Obligations','Migration graph','Inventory','Reader policy','Evidence','Timeline','Courts','Effect history','Replay & compare','Agent & SDK')


def pretty(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)


class Application(tk.Tk):
    def __init__(self):
        super().__init__();self.title('Mosaic Migration Compiler · T4-I1 / 0.1.0a4')
        self.geometry('1260x850');self.minsize(900,640);self.configure(bg=BG)
        self.model=Workbench();self.executor=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.future=None;self.job_generation=None;self.job_serial=0;self.demo_reader=None;self.last_error=None
        self.protocol('WM_DELETE_WINDOW',self.close)
        st=ttk.Style(self);st.theme_use('clam')
        st.configure('.',background=PANEL,foreground=FG,font=('TkDefaultFont',10))
        st.configure('TFrame',background=BG);st.configure('TLabel',background=BG,foreground=FG)
        st.configure('TButton',background=PANEL,foreground=FG,padding=(10,6));st.map('TButton',background=[('active','#2c4158')])
        st.configure('Treeview',background=PANEL,fieldbackground=PANEL,foreground=FG,rowheight=28)
        st.configure('Treeview.Heading',background='#28394d',foreground=FG)
        st.map('Treeview',background=[('selected','#29455e')]);st.configure('TNotebook',background=BG)
        st.configure('TNotebook.Tab',background=PANEL,foreground=FG,padding=(9,8));st.map('TNotebook.Tab',background=[('selected','#29455e')])
        banner=ttk.Frame(self);banner.pack(fill='x',padx=18,pady=(14,6))
        ttk.Label(banner,text='MOSAIC  /  MIGRATION COMPILER',font=('TkDefaultFont',19,'bold')).pack(side='left')
        ttk.Label(banner,text='T4-I1 · local review workbench',foreground=ACCENT).pack(side='right')
        ttk.Label(self,text='Investigate unresolved obligations. Preserve evidence. Keep execution authority separate.',foreground=MUTED).pack(anchor='w',padx=19,pady=(0,10))
        bar=ttk.Frame(self);bar.pack(fill='x',padx=15)
        for label,fn in [('Open workspace',self.open_dialog),('Load reader context',self.reader_dialog),('Assess',self.start_assessment),('Cancel',self.cancel),('Public demo',self.load_demo),('Export workspace',self.export_dialog)]:
            ttk.Button(bar,text=label,command=lambda fn=fn:self.guard(fn)).pack(side='left',padx=3)
        self.demo_enabled=tk.BooleanVar(value=False)
        ttk.Checkbutton(self,text='Explicitly select the public fixture reader (demonstration only)',variable=self.demo_enabled,command=lambda:self.guard(self.toggle_demo)).pack(anchor='w',padx=20,pady=10)
        self.summary=tk.StringVar(value='No selection · no reader policy · no effect authority')
        ttk.Label(self,textvariable=self.summary,foreground=WARN,font=('TkDefaultFont',11,'bold')).pack(anchor='w',padx=20,pady=(0,10))
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill='both',expand=True,padx=16,pady=4)
        self.pages={};self.texts={}
        for name in PAGES:
            page=ttk.Frame(self.tabs);self.tabs.add(page,text=name);self.pages[name]=page
        self.obligations=self.make_tree(self.pages['Obligations'],('outcome','code','references'))
        self.graph=tk.Canvas(self.pages['Migration graph'],bg=PANEL,highlightthickness=0);self.graph.pack(fill='both',expand=True)
        self.inventory=self.make_tree(self.pages['Inventory'],('kind','id','state / role'))
        for name in ('Reader policy','Evidence','Timeline','Courts','Effect history'):
            if name=='Timeline':
                ttk.Button(self.pages[name],text='Replay supplied journal under selected reader policy',command=lambda:self.guard(self.replay_journal)).pack(anchor='w',padx=5,pady=5)
            self.texts[name]=self.make_text(self.pages[name])
        rp=self.pages['Replay & compare'];rbar=ttk.Frame(rp);rbar.pack(fill='x')
        ttk.Button(rbar,text='Replay selected receipt',command=lambda:self.guard(self.replay_selected)).pack(side='left',padx=5,pady=5)
        ttk.Button(rbar,text='Compare last two',command=lambda:self.guard(self.compare_last)).pack(side='left',padx=5)
        self.history_tree=self.make_tree(rp,('index','verification','result','root'),height=8)
        self.texts['Replay & compare']=self.make_text(rp,height=7)
        ap=self.pages['Agent & SDK'];abar=ttk.Frame(ap);abar.pack(fill='x',padx=5,pady=5)
        self.claim=tk.StringVar();self.claim_choice=ttk.Combobox(abar,textvariable=self.claim,state='readonly',width=38);self.claim_choice.pack(side='left')
        for label,fn in [('Prepare work order',self.request_work),('Review submission',self.submission_dialog),('Export work order',lambda:self.export_dialog('work'))]:
            ttk.Button(abar,text=label,command=lambda fn=fn:self.guard(fn)).pack(side='left',padx=4)
        self.texts['Agent & SDK']=self.make_text(ap)
        self.status=tk.StringVar(value='Ready. Imported evidence is not a trusted result. Production effects are unavailable.')
        ttk.Label(self,textvariable=self.status,foreground=MUTED,wraplength=1200).pack(fill='x',padx=18,pady=(8,14))
        self.bind('<Control-o>',lambda e:self.guard(self.open_dialog))
        self.bind('<Control-r>',lambda e:self.guard(self.start_assessment))
        self.bind('<Escape>',lambda e:self.cancel())
        self.render()
    def make_tree(self,parent,columns,height=None):
        f=ttk.Frame(parent);f.pack(fill='both',expand=True)
        t=ttk.Treeview(f,columns=columns,show='headings',height=height or 15)
        for c in columns:t.heading(c,text=c.upper());t.column(c,width=180,stretch=True)
        scroll=ttk.Scrollbar(f,orient='vertical',command=t.yview);t.configure(yscrollcommand=scroll.set)
        t.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y');return t
    def make_text(self,parent,height=16):
        f=ttk.Frame(parent);f.pack(fill='both',expand=True)
        w=tk.Text(f,bg=PANEL,fg=FG,insertbackground=FG,font=('TkFixedFont',10),wrap='word',height=height,padx=12,pady=12,relief='flat')
        s=ttk.Scrollbar(f,command=w.yview);w.configure(yscrollcommand=s.set);w.pack(side='left',fill='both',expand=True);s.pack(side='right',fill='y');return w
    def put(self,name,value):
        w=self.texts[name];w.configure(state='normal');w.delete('1.0','end');w.insert('1.0',value if type(value) is str else pretty(value));w.configure(state='disabled')
    def guard(self,fn):
        try:self.last_error=None;return fn()
        except (MMCError,OSError,ValueError) as e:
            self.last_error=str(e);self.status.set('REFUSED: '+str(e));self.render();return None
    def load_packet(self,packet):
        self.cancel();self.demo_enabled.set(False);self.demo_reader=None
        self.model.load(packet);self.status.set('Workspace imported. Reader context not adopted.');self.render()
    def open_dialog(self):
        f=filedialog.askopenfilename(filetypes=[('Canonical JSON','*.json')])
        if f:self.load_packet(decode(read_local(f,limit=MAX_INPUT),limit=MAX_INPUT,canonical_only=True))
    def reader_dialog(self):
        f=filedialog.askopenfilename(filetypes=[('Reader context JSON','*.json')])
        if f:
            r=decode(read_local(f,limit=262144),limit=262144,canonical_only=True)
            self.model.select_reader(r);self.demo_enabled.set(False);self.status.set('Host-selected reader context; recognition path remains the operator responsibility.');self.render()
    def load_demo(self):
        p=Path(__file__).resolve().parent.parent/'mosaic_mmc_t4/data/demo.json';d=decode(p.read_bytes(),limit=MAX_INPUT)
        self.load_packet(d['workspace']);self.demo_reader=d['reader']
        self.status.set('PUBLIC FIXTURE ONLY. Select the demonstration reader explicitly before assessment.');self.render()
    def toggle_demo(self):
        if self.demo_enabled.get():
            require(self.demo_reader is not None,'MMC_T4_NO_DEMO_CONTEXT')
            self.model.select_reader(self.demo_reader,demonstration=True)
        else:self.model.invalidate();self.model.reader=None;self.model.context_label='NONE'
        self.render()
    def start_assessment(self):
        require(self.future is None,'MMC_T4_WORKER_BUSY')
        require(self.model.selection is not None and self.model.reader is not None,'MMC_T4_READER_REQUIRED')
        self.model.current=None;self.job_generation=self.model.generation
        s=clone(self.model.selection);r=clone(self.model.reader)
        self.future=self.executor.submit(assess_view,s,r)
        self.status.set('Computing fixed local evaluators. No network, signing or target effects.');self.render();self.after(25,self.poll)
    def poll(self):
        if self.future is None:return
        if not self.future.done():self.after(25,self.poll);return
        f=self.future;g=self.job_generation;self.future=None
        try:
            r=f.result()
            if g!=self.model.generation:self.status.set('Discarded cancelled or superseded result.');return
            self.model.accept_result(r,g);self.status.set('Recomputed supplied evidence. This is not effect authorization.')
        except Exception as e:self.last_error=str(e);self.model.current=None;self.status.set('REFUSED: '+str(e))
        finally:self.render()
    def cancel(self):
        self.model.invalidate();self.status.set('Current result cleared. Cancellation discards results; it does not kill running host code.');self.render()
    def request_work(self):
        r=self.model.request_work(self.claim.get(),[])
        self.put('Agent & SDK',r);self.status.set('Work order prepared in memory. No read capability, signature or effect grant was issued.')
    def submission_dialog(self):
        f=filedialog.askopenfilename(filetypes=[('Signed submission JSON','*.json')])
        if f:
            s=decode(read_local(f,limit=MAX_INPUT),limit=MAX_INPUT,canonical_only=True)
            r=self.model.review_submission(s);self.put('Agent & SDK',r)
            self.status.set('Submission reviewed, NOT stored. Controller evidence admission requires a separate host action.')
    def replay_journal(self):
        require(self.model.reader is not None,'MMC_T4_READER_REQUIRED')
        self.model.replay_journal(self.model.reader['expected_policy_root'])
        self.render();self.status.set('Journal replayed from supplied bytes, no external floor selected; no effects reissued.')
    def replay_selected(self):
        selected=self.history_tree.selection();require(selected,'MMC_T4_HISTORY_SELECTION')
        i=int(self.history_tree.item(selected[0],'values')[0]);r=self.model.replay_history(i);self.render();self.put('Replay & compare',r)
    def compare_last(self):
        n=len(self.model.history);require(n>=2,'MMC_T4_HISTORY_PAIR')
        self.put('Replay & compare',self.model.compare_history(n-2,n-1))
    def export_dialog(self,kind='workspace'):
        value=self.model.packet() if kind=='workspace' else self.model.work_order
        require(value is not None,'MMC_T4_NO_WORK_ORDER')
        path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('Canonical JSON','*.json')])
        if not path:return
        p=Path(path);e=LocalExport(p.parent,state_token=lambda:self.model.status())
        plan=e.prepare(value,p.name)
        question=f"CREATE ONLY — no overwrite\n\n{p}\n{plan['body']['bytes']} bytes\nSHA-256: {plan['body']['sha256']}\n\nPlaintext may contain private evidence. Create this exact local file?"
        if not messagebox.askyesno('Confirm local file creation',question):e.cancel();self.status.set('Export cancelled; no file created.');return
        r=e.commit(e.approve(plan['root']));self.status.set(r['status']+' — '+p.name)
    def render(self):
        if not hasattr(self,'texts'):return
        m=self.model;s=m.selection;r=None if m.current is None else m.current['body']
        self.obligations.delete(*self.obligations.get_children());self.inventory.delete(*self.inventory.get_children())
        self.history_tree.delete(*self.history_tree.get_children());self.graph.delete('all')
        label=m.context_label
        if s:
            objs=s['plan']['body']['bundle']['model']['objects']
            for o in sorted(objs,key=lambda x:x['id']):
                self.inventory.insert('', 'end',values=(o['kind'],o['id'],str(o['attributes'].get('role',o['attributes'].get('state','—')))))
            choices=sorted(claim_contracts(s));self.claim_choice['values']=choices
            if self.claim.get() not in choices:self.claim.set(choices[0] if choices else '')
            self.draw_graph(s,r)
            self.put('Evidence',{'label':'SIGNED_INPUTS_NOT_YET_RECOGNIZED' if r is None else r['evidence_label'],'records':s['records']})
            self.put('Reader policy',{'context_origin':label,'selected_reader':m.reader,'declared_policy':s['policy'],'note':'An imported policy is not automatically a recognized policy.'})
            self.put('Timeline',m.journal_result if m.journal_result else {'label':'IMPORTED_NOT_REPLAYED','journal':m.journal,'selected_head':s['head']})
        else:
            self.claim_choice['values']=[];self.claim.set('')
            for name in ('Evidence','Reader policy','Timeline'):self.put(name,'No selection.')
        if r:
            for c in r['court']['body']['checks']:self.obligations.insert('','end',values=(c['outcome'],c['code'],', '.join(c['refs'])))
            missing=sum(c['outcome']=='MISSING' for c in r['court']['body']['checks']);blocked=sum(c['outcome']=='BLOCK' for c in r['court']['body']['checks'])
            self.summary.set(f"{r['status']}  ·  {missing} missing  ·  {blocked} blocked  ·  {label}  ·  NO EFFECT AUTHORITY")
            self.put('Courts',m.current)
        else:
            self.summary.set(f"NOT EVALUATED  ·  {label}  ·  Imported results are not current authority")
            self.put('Courts','Select a reader context and run an assessment. Imported PASS text is not a recomputed result.')
        self.put('Effect history',{'replayed_operations':None if m.journal_result is None else m.journal_result['projection']['operations'],'status':'NO_TARGET_EXECUTION_INTERFACE','description':'This workbench does not approve, sign or commit migration targets. Supplied journal outcomes remain records until explicit replay.','journal_loaded':m.journal is not None})
        for i,h in enumerate(m.history):
            self.history_tree.insert('','end',values=(i,h['verification'],h['receipt']['body'].get('status'),h['receipt']['root'][:20]+'…'))
        if m.review:self.put('Agent & SDK',m.review)
        elif m.work_order:self.put('Agent & SDK',m.work_order)
        else:self.put('Agent & SDK',capabilities())
    def draw_graph(self,s,view):
        model=s['plan']['body']['bundle']['model'];ts=[x for x in model['objects'] if x['kind']=='Transition']
        self.graph.create_text(24,24,anchor='nw',fill=MUTED,text='Declared transition model · not observed execution',font=('TkDefaultFont',12))
        positions={}
        for i,t in enumerate(sorted(ts,key=lambda x:x['id'])):
            x=35+(i%4)*270;y=90+(i//4)*130;positions[t['id']]=(x+110,y+36)
            self.graph.create_rectangle(x,y,x+220,y+72,fill='#263b51',outline=ACCENT if t['id']==s['transition'] else '#4c6077',width=2)
            self.graph.create_text(x+12,y+18,anchor='w',text=t['id'],fill=FG,font=('TkDefaultFont',11,'bold'))
            self.graph.create_text(x+12,y+45,anchor='w',text=t['attributes']['goal']+' · '+t['attributes']['cohort'],fill=MUTED)
        if view:
            for e in view['graph']['order_edges']:
                if e['before'] in positions and e['after'] in positions:
                    x1,y1=positions[e['before']];x2,y2=positions[e['after']]
                    self.graph.create_line(x1+110,y1,x2-110,y2,fill=ACCENT,arrow='last')
    def close(self):
        self.executor.shutdown(wait=False,cancel_futures=True);self.destroy()


def main():
    app=Application();app.mainloop();return 0

if __name__=='__main__':raise SystemExit(main())
