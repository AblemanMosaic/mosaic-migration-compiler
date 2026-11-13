"""Headless workbench state. Imported results and reader-selected evaluations are separate."""
from mosaic_mmc_t4.common import *
from mosaic_mmc_t4.views import validate_snapshot,validate_reader,assess_view,replay_view,compare_views,journal_view
from mosaic_mmc_t4.work import make_work_order,review_submission

class Workbench:
    def __init__(self):
        self.generation=0;self.selection=None;self.reader=None;self.current=None;self.history=[]
        self.work_order=None;self.review=None;self.journal=None;self.journal_result=None;self.context_label='NONE'
    def invalidate(self):
        self.generation+=1;self.current=None;self.work_order=None;self.review=None;self.journal_result=None
    def load(self,packet):
        self.invalidate();self.selection=None;self.reader=None;self.history=[];self.journal=None;self.context_label='NONE'
        canonical(packet,limit=MAX_INPUT)
        closed(packet,{'schema','snapshot','history','journal'})
        require(packet['schema']=='mmc.workspace.t4','MMC_T4_WORKSPACE_SCHEMA')
        s=validate_snapshot(packet['snapshot'])
        require(type(packet['history']) is list and len(packet['history'])<=64,'MMC_T4_HISTORY_LIMIT')
        history=[]
        for receipt in packet['history']:
            b=unwrap('view',receipt);require(b.get('schema')=='mmc.view.t4','MMC_T4_VIEW_SCHEMA')
            history.append({'receipt':clone(receipt),'verification':'IMPORTED_NOT_REPLAYED'})
        if packet['journal'] is not None:
            closed(packet['journal'],{'events','expected_policy_root','minimum'})
            # Only imported data here; no trust in self-supplied checkpoint until explicit replay.
            canonical(packet['journal'],limit=MAX_INPUT)
        self.selection=s;self.history=history;self.journal=clone(packet['journal'])
        return self.status()
    def select_reader(self,reader,*,demonstration=False):
        self.invalidate();self.reader=None;self.context_label='NONE'
        require(self.selection is not None,'MMC_T4_NO_SELECTION');validate_reader(self.selection,reader)
        self.reader=clone(reader);self.context_label='PUBLIC_FIXTURE_CONTEXT' if demonstration else 'HOST_SELECTED_READER'
        return self.status()
    def evaluate(self):
        require(self.selection is not None and self.reader is not None,'MMC_T4_READER_REQUIRED')
        self.current=None
        r=assess_view(self.selection,self.reader)
        self.accept_result(r,self.generation)
        return clone(r)
    def accept_result(self,r,generation):
        require(generation==self.generation,'MMC_T4_STALE_WORKER')
        require(len(self.history)<64,'MMC_T4_HISTORY_LIMIT')
        self.current=clone(r);self.history.append({'receipt':clone(r),'verification':'RECOMPUTED_CURRENT_CONTEXT'})
    def request_work(self,claim,allowed_reads,ttl=30):
        require(self.selection is not None and self.reader is not None,'MMC_T4_READER_REQUIRED')
        self.work_order=make_work_order(self.selection,self.reader,claim,allowed_reads,ttl);return clone(self.work_order)
    def review_submission(self,submission):
        require(self.work_order is not None and self.reader is not None,'MMC_T4_NO_WORK_ORDER')
        self.review=None;self.review=review_submission(self.selection,self.reader,self.work_order,submission,expected_work_root=self.work_order["root"])
        return clone(self.review)
    def replay_history(self,index):
        integer(index,0,len(self.history)-1);require(self.reader is not None,'MMC_T4_READER_REQUIRED')
        entry=self.history[index];entry['verification']='IMPORTED_NOT_REPLAYED'
        result=replay_view(self.selection,self.reader,entry['receipt']);entry['verification']='REPLAYED_CURRENT_CONTEXT';return result
    def replay_journal(self,expected_policy_root,minimum=None):
        require(self.journal is not None,'MMC_T4_NO_JOURNAL')
        # Use fresh host arguments, NOT the imported packet's checkpoint/policy declarations.
        self.journal_result=journal_view(self.journal['events'],expected_policy_root,minimum)
        return clone(self.journal_result)
    def compare_history(self,first,second):
        integer(first,0,len(self.history)-1);integer(second,0,len(self.history)-1)
        return compare_views(self.history[first]['receipt'],self.history[second]['receipt'])
    def packet(self):
        require(self.selection is not None,'MMC_T4_NO_SELECTION')
        return {'schema':'mmc.workspace.t4','snapshot':clone(self.selection),
                'history':[clone(x['receipt']) for x in self.history],'journal':clone(self.journal)}
    def status(self):
        return {'schema':'mmc.workbench-status.t4','generation':self.generation,
                'selection':None if self.selection is None else digest('snapshot',self.selection),
                'context_label':self.context_label,'current_result':None if self.current is None else self.current['root'],
                'assessment_status':'NOT_EVALUATED' if self.current is None else self.current['body']['status'],
                'history_labels':[h['verification'] for h in self.history],
                'effect_authorization':'NOT_GRANTED','native_pippi':'NOT_BOUND','authority_effect':'NONE'}
