import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from mosaic_mmc_t4.common import *
from mosaic_mmc_t4.abi import dispatch,OPERATIONS,capabilities
from mosaic_mmc_t4.views import *
from mosaic_mmc_t4.integrations import manifest,require_native_pippi,handoff
from mosaic_mmc_workbench.model import Workbench
from tests_t4.helpers import scenario,workspace,Env,TIME,ROOT

class InterfaceTests(unittest.TestCase):
    def test_discovery_exact_dispatch_surface(self):
        c=capabilities();self.assertEqual({x['name'] for x in c['operations']},set(OPERATIONS))
        for x in c['operations']:self.assertEqual(x['arguments'],sorted(OPERATIONS[x['name']]))
    def test_inspection_does_not_adopt_policy(self):
        s,r,w,sub=scenario();x=dispatch({'schema':'mmc.request.t4','operation':'inspect','arguments':{'snapshot':s}})
        self.assertEqual(x['evidence_label'],'IMPORTED_UNVERIFIED');self.assertEqual(x['reader_context'],'NOT_SELECTED')
    def test_headless_equals_abi(self):
        s,r,w,sub=scenario();expected=assess_view(s,r)
        self.assertEqual(canonical(expected),canonical(dispatch({'schema':'mmc.request.t4','operation':'assess','arguments':{'snapshot':s,'reader':r}})))
    def test_exact_replay(self):
        s,r,w,sub=scenario();x=assess_view(s,r);self.assertEqual(replay_view(s,r,x)['status'],'MATCH_EXACT_REPLAY')
    def test_rehashed_forged_pass_refuses(self):
        s,r,w,sub=scenario();x=assess_view(s,r);x['body']['status']='AUTHORIZED';x=envelope('view',x['body'])
        with self.assertRaises(MMCError):replay_view(s,r,x)
    def test_comparison_not_verification(self):
        s,r,w,sub=scenario();x=assess_view(s,r);y=clone(x);y['body']['status']='FORGED';y=envelope('view',y['body'])
        result=compare_views(x,y);self.assertIn('status',result['changed_fields']);self.assertEqual(result['evidence_label'],'IMPORTED_NOT_REPLAYED')
    def test_comparison_distinguishes_missing_from_null(self):
        s,r,w,sub=scenario();x=assess_view(s,r);y=clone(x);del y['body']['head'];y=envelope('view',y['body'])
        self.assertIn('head',compare_views(x,y)['changed_fields'])
    def test_cli_exact_library_parity(self):
        s,r,w,sub=scenario();request={'schema':'mmc.request.t4','operation':'assess','arguments':{'snapshot':s,'reader':r}}
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t4.cli','request','-'],input=canonical(request),capture_output=True,timeout=20,env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout,canonical(dispatch(request))+b'\n')
    def test_cli_duplicate_field_refused(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t4.cli','request','-'],input=b'{"schema":"mmc.request.t4","operation":"capabilities","arguments":{},"operation":"commit"}',capture_output=True,timeout=10,env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
        self.assertEqual(p.returncode,2)
    def test_no_filesystem_during_assessment(self):
        s,r,w,sub=scenario()
        with patch('os.system',side_effect=AssertionError('shell')),patch('subprocess.run',side_effect=AssertionError('process')),patch('urllib.request.urlopen',side_effect=AssertionError('network')):
            self.assertEqual(assess_view(s,r)['body']['effects'],'NOT_EXECUTED')
    def test_handoff_not_integration(self):
        h=handoff('pippi',[{'role':'plan','sha256':'a'*64}]);self.assertEqual(h['body']['operational_integration'],'NOT_ESTABLISHED')
    def test_mandatory_native_gate_refuses(self):
        with self.assertRaises(MMCError):require_native_pippi()
        self.assertEqual(next(x for x in manifest() if x['id']=='pippi')['gate'],'BLOCKED_NATIVE_DEPENDENCY')
    def test_journal_replay_exact(self):
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);e.observe();events=e.controller.journal.export();r=journal_view(events,e.controller.journal.policy_root,None)
            self.assertEqual(canonical(r['projection']),canonical(e.controller.replay()['projection']));self.assertEqual(r['effects'],'NOT_EXECUTED')
    def test_journal_chain_rehash_does_not_invent_event(self):
        from mosaic_mmc_t3.common import digest as dh
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);events=e.controller.journal.export();events[-1]['type']='GRANT_EVERYTHING';events[-1]['root']=dh('event',{k:events[-1][k] for k in ('sequence','previous','type','payload')})
            with self.assertRaises(MMCError):journal_view(events,e.controller.journal.policy_root,None)

for op in ['commit','approve','fetch','sign','install','register','import-plugin','amend-policy','publish','submit','observe']:
    def test(self,op=op):
        with self.assertRaises(MMCError):dispatch({'schema':'mmc.request.t4','operation':op,'arguments':{}})
    setattr(InterfaceTests,'test_forbidden_'+op.replace('-','_'),test)
for value in [None,False,1,[],"__import__('os')",{'schema':'mmc.request.t4','operation':True,'arguments':{}},{'schema':'bad','operation':'capabilities','arguments':{}}]:
    def test(self,value=value):
        with self.assertRaises(MMCError):dispatch(value)
    setattr(InterfaceTests,'test_bad_request_'+str(len(InterfaceTests.__dict__)),test)
for field in ('expected_plan_root','expected_policy_root','expected_snapshot_root'):
    def test(self,field=field):
        s,r,w,sub=scenario();r[field]='f'*64
        with self.assertRaises(MMCError):assess_view(s,r)
    setattr(InterfaceTests,'test_reader_pin_'+field,test)

class WorkbenchTests(unittest.TestCase):
    def loaded(self):
        s,r,w,sub=scenario();m=Workbench();m.load(workspace(s));return m,s,r,w,sub
    def test_import_reader_not_selected(self):
        m,s,r,w,sub=self.loaded();self.assertIsNone(m.reader)
        with self.assertRaises(MMCError):m.evaluate()
    def test_ui_model_exact_headless(self):
        m,s,r,w,sub=self.loaded();m.select_reader(r);self.assertEqual(canonical(m.evaluate()),canonical(assess_view(s,r)))
    def test_failed_reader_clears_current(self):
        m,s,r,w,sub=self.loaded();m.select_reader(r);m.evaluate();r['expected_plan_root']='f'*64
        with self.assertRaises(MMCError):m.select_reader(r)
        self.assertIsNone(m.current);self.assertIsNone(m.reader)
    def test_failed_load_clears_current(self):
        m,s,r,w,sub=self.loaded();m.select_reader(r);m.evaluate()
        with self.assertRaises(MMCError):m.load({'schema':'wrong'})
        self.assertIsNone(m.current);self.assertIsNone(m.selection)
    def test_imported_history_not_trusted(self):
        m,s,r,w,sub=self.loaded();m.select_reader(r);m.evaluate();p=m.packet();m.load(p)
        self.assertEqual(m.history[0]['verification'],'IMPORTED_NOT_REPLAYED');self.assertIsNone(m.reader)
        m.select_reader(r);m.replay_history(0);self.assertEqual(m.history[0]['verification'],'REPLAYED_CURRENT_CONTEXT')
    def test_forged_import_history_replay_refused(self):
        m,s,r,w,sub=self.loaded();v=assess_view(s,r);v['body']['status']='FORGED_PASS';v=envelope('view',v['body']);p=workspace(s);p['history']=[v];m.load(p);m.select_reader(r)
        with self.assertRaises(MMCError):m.replay_history(0)
        self.assertEqual(m.history[0]['verification'],'IMPORTED_NOT_REPLAYED')
    def test_cancelled_worker_refused(self):
        m,s,r,w,sub=self.loaded();m.select_reader(r);g=m.generation;result=assess_view(s,r);m.invalidate()
        with self.assertRaises(MMCError):m.accept_result(result,g)
        self.assertIsNone(m.current)
    def test_submission_preview_not_applied(self):
        m,s,r,w,sub=self.loaded();m.select_reader(r);work=m.request_work('coverage',[]);sub['work_order_root']=work['root'];original=canonical(m.selection)
        review=m.review_submission(sub);self.assertEqual(review['body']['after']['body']['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY');self.assertEqual(original,canonical(m.selection))
    def test_history_limit(self):
        m,s,r,w,sub=self.loaded();p=workspace(s);p['history']=[assess_view(s,r)]*65
        with self.assertRaises(MMCError):m.load(p)
    def test_open_cannot_supply_reader(self):
        m,s,r,w,sub=self.loaded();p=workspace(s);p['reader']=r
        with self.assertRaises(MMCError):m.load(p)
    def test_headless_does_not_import_tk(self):
        script='from mosaic_mmc_workbench.model import Workbench; import sys; assert "tkinter" not in sys.modules'
        p=subprocess.run([sys.executable,'-c',script],capture_output=True,timeout=10,env={**os.environ,'PYTHONPATH':str(ROOT/'src')});self.assertEqual(p.returncode,0,p.stderr)

class AllCliTests(unittest.TestCase):
    """Every advertised operation is sent through the actual subprocess interface."""
    def request_for(self,op):
        s,r,w,sub=scenario();v=assess_view(s,r)
        args={'capabilities':{},'profiles':{},'integrations':{},'inspect':{'snapshot':s},
          'assess':{'snapshot':s,'reader':r},'replay':{'snapshot':s,'reader':r,'candidate':v},
          'compare':{'first':v,'second':v},'work-order':{'snapshot':s,'reader':r,'claim':'coverage','allowed_reads':[],'ttl':30},
          'review-submission':{'snapshot':s,'reader':r,'work_order':w,'submission':sub,'expected_work_root':w['root']},
          'journal':{'events':[],'expected_policy_root':'a'*64,'minimum':None},
          'profile-assess':{'name':'jobs','value':{'schema':'mmc.job-input.t4','jobs':[]}},
          'record-assess':{'kind':'repository','value':{'schema':'mmc.repository-record.t4','revision':'fixture','files':[]},'expected':{'revision':'fixture'}},
          'handoff':{'target':'pippi','references':[{'role':'plan','sha256':'a'*64}]},
          'native-read':{'name':'unbound','arguments':{}}}
        return {'schema':'mmc.request.t4','operation':op,'arguments':args[op]}
for op in OPERATIONS:
    def test(self,op=op):
        request=self.request_for(op)
        try:expected=dispatch(request);exit_code=0
        except MMCError as e:expected={'schema':'mmc.refusal.t4','ok':False,'error':e.record(),**BOUNDARY};exit_code=2
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t4.cli','request','-'],input=canonical(request),capture_output=True,timeout=15,env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
        self.assertEqual(p.returncode,exit_code,p.stderr);self.assertEqual(p.stdout,canonical(expected)+b'\n')
    setattr(AllCliTests,'test_'+op.replace('-','_'),test)
