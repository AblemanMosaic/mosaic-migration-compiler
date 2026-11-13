import copy,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from tools.common import ROOT,read_json,save_json,canonical,MMCError,sha
from tools_t6 import audit,study,qualify as q

def legs():
    return dict(tests=True,examples=True,scenarios=True,audit=True,installed=True,clean=True,closed_delivery=True,platforms=['Linux'],native_pippi='NOT_BOUND',independent_review='NOT_PERFORMED',independent_study='NOT_PERFORMED',public_release='NOT_CLEARED')

def ev(sequence,event,time,**kw):
    return dict(participant='p1',arm='mmc',task='S0-discovery',sequence=sequence,activity='modeling',event=event,time_seconds=time,**kw)

class ReleaseTests(unittest.TestCase):
    def test_frozen_original_and_release_plan(self):self.assertEqual(audit.freeze()['status'],'PASS_EXACT_FREEZE')
    def test_runtime_preserved(self):self.assertEqual(audit.preservation()['runtime_files'],88)
    def test_current_document_links(self):self.assertGreater(len(audit.document_links()['links']),15)
    def test_full_six_requirement_map(self):self.assertEqual(audit.check_mapping()['requirements'],6)
    def test_platform_stays_partial(self):
        d=audit.assess_final(legs(),read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'])
        self.assertEqual(d['cases']['AC-REPRO-05'],'PARTIAL_PLATFORM_COVERAGE');self.assertFalse(d['full_program_qualified'])
    def test_native_stays_blocked(self):
        d=audit.assess_final(legs(),read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'])
        self.assertEqual(d['cases']['AC-REPRO-06'],'BLOCKED_NATIVE_DEPENDENCY')
    def test_reconciliation_not_public_release(self):
        d=audit.assess_final(legs(),read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'])
        self.assertEqual(d['counts']['PASS_SCOPED'],98);self.assertEqual(d['public_release'],'NOT_CLEARED')
    def test_missing_case_refuses(self):
        with self.assertRaises(MMCError):audit.assess_final(legs(),read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'][:-1])
    def test_duplicate_case_refuses(self):
        a=read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'];a[-1]=copy.deepcopy(a[0])
        with self.assertRaises(MMCError):audit.assess_final(legs(),a)
    def test_substituted_case_identity_refuses(self):
        a=read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'];a[-1]['id']='AC-UNREVIEWED-01'
        with self.assertRaises(MMCError):audit.assess_final(legs(),a)
    def test_changed_oracle_refuses(self):
        a=read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'];a[-1]['oracle']='always pass'
        with self.assertRaises(MMCError):audit.assess_final(legs(),a)
    def test_no_test_import_before_admission(self):
        with tempfile.TemporaryDirectory() as d,patch.object(q,'verify_source',side_effect=MMCError('REFUSED')),patch.object(q.unittest.TestLoader,'discover') as load:
            with self.assertRaises(MMCError):q.run_tests(Path(d),'a'*64)
            load.assert_not_called()

for key,value in [(k,False) for k in ('tests','examples','scenarios','audit','installed','clean','closed_delivery')]+[('tests',1),('platforms',['Linux','Windows']),('native_pippi','PASS'),('independent_review','PASS'),('independent_study','PASS'),('public_release','CLEARED')]:
    def test(self,k=key,v=value):
        x=legs();x[k]=v
        with self.assertRaises(MMCError):audit.assess_final(x,read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'])
    setattr(ReleaseTests,'test_refuse_'+key+'_'+str(value).replace(' ','_').replace('[','').replace(']','').replace("'",''),test)

class StudyTests(unittest.TestCase):
    def setUp(self):self.design=read_json(ROOT/'study/DESIGN.json')
    def test_empty_not_zero_hours(self):
        r=study.summarize(self.design,[]);self.assertEqual(r['status'],'PREPARED_NOT_PERFORMED');self.assertEqual(r['rows'],[])
    def test_paired_accounting_is_not_independent_study(self):
        r=study.summarize(self.design,[ev(0,'start',10),ev(1,'stop',35)])
        self.assertEqual(r['rows'][0]['reported_seconds'],25);self.assertEqual(r['primary_study'],'NOT_PERFORMED')
    def test_open_span_not_zero(self):
        r=study.summarize(self.design,[ev(0,'start',10)]);self.assertTrue(r['incomplete_accounting']);self.assertEqual(r['open_spans'],['p1'])
    def test_no_overlap(self):
        with self.assertRaises(MMCError):study.summarize(self.design,[ev(0,'start',10),ev(1,'start',12)])
    def test_unpaired_stop(self):
        with self.assertRaises(MMCError):study.summarize(self.design,[ev(0,'stop',10)])
    def test_backwards_clock(self):
        with self.assertRaises(MMCError):study.summarize(self.design,[ev(0,'start',10),ev(1,'stop',9)])
    def test_missing_sequence(self):
        with self.assertRaises(MMCError):study.summarize(self.design,[ev(1,'start',10)])
    def test_activity_substitution(self):
        e=ev(1,'stop',20);e['activity']='review'
        with self.assertRaises(MMCError):study.summarize(self.design,[ev(0,'start',10),e])
    def test_arm_substitution(self):
        e=ev(1,'stop',20);e['arm']='conventional'
        with self.assertRaises(MMCError):study.summarize(self.design,[ev(0,'start',10),e])
    def test_unknown_field(self):
        e=ev(0,'start',10);e['saved_hours']=999
        with self.assertRaises(MMCError):study.summarize(self.design,[e])
    def test_no_primary_claim(self):
        r=study.reject_primary_claim({'primary_study':'NOT_PERFORMED','productivity_savings':'NOT_ESTABLISHED','economic_break_even':'NOT_ESTABLISHED','independent_participants':'NOT_OBSERVED','authority_effect':'NONE'})
        self.assertEqual(r['status'],'PRIMARY_STUDY_BLOCKED')
for key,val in [('time_seconds',True),('time_seconds',-1),('time_seconds',1.5),('sequence',True),('task','not-admitted'),('participant',''),('activity','invented'),('event','approved')]:
    def test(self,k=key,v=val):
        e=ev(0,'start',10);e[k]=v
        with self.assertRaises(MMCError):study.summarize(self.design,[e])
    setattr(StudyTests,'test_event_'+key+'_'+str(val).replace('.','_'),test)
for k,v in [('primary_study','PASS'),('productivity_savings','50%'),('economic_break_even',3),('independent_participants','OBSERVED'),('authority_effect','EXECUTE')]:
    def test(self,k=k,v=v):
        e={'primary_study':'NOT_PERFORMED','productivity_savings':'NOT_ESTABLISHED','economic_break_even':'NOT_ESTABLISHED','independent_participants':'NOT_OBSERVED','authority_effect':'NONE'};e[k]=v
        with self.assertRaises(MMCError):study.reject_primary_claim(e)
    setattr(StudyTests,'test_reject_claim_'+k,test)

class StageTests(unittest.TestCase):
    def fixture(self,d):
        out=Path(d);ids=['test.bound.case'];source='a'*64
        save_json(out/'collected.json',{'schema':'mmc.collected-tests.t6','source_root':source,'ids':ids})
        save_json(out/'tests.json',{'schema':'mmc.test-results.t6','source_root':source,'elapsed_ns':1,'tests':[{'id':i,'status':'PASS'} for i in ids],'counts':q.base.counts(1)})
        (out/'tests.txt').write_text('Synthetic verifier challenge, not actual product evidence.')
        s=q.write_stage(out,'test-t6',source,{'collected.json','tests.json','tests.txt'},q.base.counts(1),0)
        return out,source,s,ids
    def test_synthetic_stage(self):
        with tempfile.TemporaryDirectory() as d:
            out,source,s,ids=self.fixture(d)
            with patch.object(q,'test_ids',return_value=ids):self.assertEqual(q.verify_stage(out,'test-t6',source),s)
    def test_rehashed_wrong_test_identity(self):
        with tempfile.TemporaryDirectory() as d:
            out,source,s,ids=self.fixture(d);v=read_json(out/'tests.json');v['tests'][0]['id']='wrong';save_json(out/'tests.json',v)
            s['outputs']=q.artifacts(out,{'collected.json','tests.json','tests.txt'});save_json(out/'STAGE.json',s)
            with patch.object(q,'test_ids',return_value=ids),self.assertRaises(MMCError):q.verify_stage(out,'test-t6',source)
    def test_extra_stage_file(self):
        with tempfile.TemporaryDirectory() as d:
            out,source,s,ids=self.fixture(d);(out/'extra.txt').write_text('extra')
            with patch.object(q,'test_ids',return_value=ids),self.assertRaises(MMCError):q.verify_stage(out,'test-t6',source)
    def test_changed_log(self):
        with tempfile.TemporaryDirectory() as d:
            out,source,s,ids=self.fixture(d);(out/'tests.txt').write_text('changed')
            with patch.object(q,'test_ids',return_value=ids),self.assertRaises(MMCError):q.verify_stage(out,'test-t6',source)
for k,v in [('schema','wrong'),('terminal_exit',True),('terminal_exit',2),('source_root','b'*64),('authority_effect','EXECUTE'),('signature','SIGNED'),('phase','audit')]:
    def test(self,k=k,v=v):
        with tempfile.TemporaryDirectory() as d:
            out,source,s,ids=self.fixture(d);s[k]=v;save_json(out/'STAGE.json',s)
            with patch.object(q,'test_ids',return_value=ids),self.assertRaises(MMCError):q.verify_stage(out,'test-t6',source)
    setattr(StageTests,'test_header_'+k+'_'+str(v),test)
