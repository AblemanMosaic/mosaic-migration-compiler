from pathlib import Path
import copy,tempfile,unittest,subprocess,sys,os
from unittest.mock import patch
from mosaic_mmc import canonical,MMCError
from tools.common import read_json,save_json,sha
from tools_t5 import qualify as q
from tools_t5.fidelity import check_claims
from tests_t5.test_scenarios import result
ROOT=Path(__file__).resolve().parents[1]

class CorpusTests(unittest.TestCase):pass
for c in read_json(ROOT/'interop/t5-known-answers.json')['cases']:
    def test(self,c=c):
        from tools_t5.check_vectors import compare
        self.assertEqual(compare(c,result(c['scenario']))['status'],'PASS')
    setattr(CorpusTests,'test_'+c['id'].replace('-','_'),test)

class QualificationTests(unittest.TestCase):
    def test_original_program_and_oracles_preserved(self):
        from tools.common import verify_freeze
        self.assertEqual(verify_freeze()['status'],'PASS_EXACT_FREEZE')
    def test_all_predecessor_runtime_semantics_exact(self):self.assertEqual(q.preservation()['runtime_files'],78)
    def test_eight_requirements_bound(self):
        from tools_t5.check_model import check
        self.assertEqual(check()['obligations'],8)
    def test_all_ten_due_cases_bound(self):
        due={c['id'] for c in read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'] if c['gate']=='T5'}
        self.assertEqual(set(q.registry()['acceptance']),due);self.assertEqual(len(due),10)
    def test_test_registry_unique(self):
        ids=sum(q.expected_ids().values(),[]);self.assertEqual(len(ids),len(set(ids)))
    def test_pre_execution_source_admission(self):
        with tempfile.TemporaryDirectory() as d,patch.object(q,'verify_source',side_effect=MMCError('REFUSED')),patch.object(q.unittest.TestLoader,'discover') as launch:
            with self.assertRaises(MMCError):q.run_test_group(Path(d),'f'*64,'t5')
            launch.assert_not_called()
    def test_oracle_not_regenerated_by_checker(self):
        from tools_t5.check_vectors import compare
        c=read_json(ROOT/'interop/t5-known-answers.json')['cases'][0];r=result('safe-token')
        c['expected']['target_effects']+=1
        with self.assertRaises(MMCError):compare(c,r)
    def test_bool_is_not_case_count(self):
        with self.assertRaises(MMCError):q.exact({'count':True},{'count':1},'FALSE_COUNT')
    def test_mandatory_stage_includes_scenarios(self):self.assertIn('scenarios',q.OUTPUTS)
    def test_gui_remains_actual_not_mocked_gate(self):self.assertIn('tests_t4.test_native_gui.GUIQualificationTests.test_actual_tk_interaction',q.expected_ids()['t4'])
    def test_no_external_platform_promotion(self):
        v={'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED','production_evidence':False,
        'productivity_claim':'NOT_ESTABLISHED','public_release':'NOT_CLEARED','qualification_scope':'FINITE_LOCAL_SIMULATION','authority_effect':'NONE'}
        self.assertEqual(check_claims(v)['status'],'SCOPED_CLAIMS_ONLY')
    def test_cli_capabilities(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t5.cli','list'],capture_output=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stderr);r=__import__('mosaic_mmc').decode(p.stdout)
        self.assertEqual(len(r['scenarios']),10);self.assertIs(r['production'],False)
    def test_cli_no_production_commit(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t5.cli','commit'],capture_output=True,timeout=20)
        self.assertEqual(p.returncode,2)
    def test_cli_bad_seed_has_typed_refusal(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t5.cli','run','safe-token','--seed','-1'],capture_output=True,timeout=20)
        self.assertEqual(p.returncode,2);self.assertIn(b'MMC_T5_SEED_LIMIT',p.stdout)
    def test_spec_freeze_not_rewritten(self):
        from mosaic_mmc_t5._pins import CONTRACT_ROOT
        self.assertEqual(read_json(ROOT/'provenance/turn5/FREEZE.json')['contract_root'],CONTRACT_ROOT)

for field,value in [('native_pippi','NATIVE_ENFORCED'),('independent_review','PASS'),('production_evidence',True),
                    ('production_evidence',0),('productivity_claim','SAVES_50_PERCENT'),('public_release','APPROVED'),
                    ('authority_effect','EXECUTE'),('qualification_scope','FULL_PRODUCTION')]:
    def test(self,f=field,v=value):
        value={'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED','production_evidence':False,
          'productivity_claim':'NOT_ESTABLISHED','public_release':'NOT_CLEARED','qualification_scope':'FINITE_LOCAL_SIMULATION','authority_effect':'NONE'}
        value[f]=v
        with self.assertRaises(MMCError):check_claims(value)
    setattr(QualificationTests,'test_false_claim_'+field+'_'+str(value).lower(),test)

class StageTests(unittest.TestCase):
    def _part(self,d):
        ids=['test.example'];root='a'*64;out=Path(d)
        save_json(out/'t5-tests.json',{'schema':'mmc.test-results.t5','source_root':root,'elapsed_ns':1,'tests':[{'id':ids[0],'status':'PASS'}],'counts':q.counts(1)})
        (out/'t5-tests.txt').write_text('synthetic verifier fixture, not product execution')
        p={'schema':'mmc.test-part.t5','group':'t5','source_root':root,'environment':q.environment(),'collected':ids,'terminal_exit':0,'counts':q.counts(1),
           'outputs':[{'path':n,'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['t5-tests.json','t5-tests.txt']],
           'authority_effect':'NONE','signature':'NOT_SIGNED'}
        save_json(out/'t5-PART.json',p);return p,out,root,ids
    def test_part_positive(self):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d)
            with patch.object(q,'expected_ids',return_value={'t5':ids}):self.assertEqual(q.verify_part(out,root,'t5'),p)
    def test_changed_terminal_log_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d);(out/'t5-tests.txt').write_text('changed')
            with patch.object(q,'expected_ids',return_value={'t5':ids}),self.assertRaises(MMCError):q.verify_part(out,root,'t5')
    def test_rehashed_wrong_identity_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d);v=read_json(out/'t5-tests.json');v['tests'][0]['id']='wrong.identity';save_json(out/'t5-tests.json',v)
            p['outputs'][0]={'path':'t5-tests.json','bytes':(out/'t5-tests.json').stat().st_size,'sha256':sha(out/'t5-tests.json')};save_json(out/'t5-PART.json',p)
            with patch.object(q,'expected_ids',return_value={'t5':ids}),self.assertRaises(MMCError):q.verify_part(out,root,'t5')

for index,(key,value) in enumerate([('schema','wrong'),('group','t4'),('source_root','b'*64),('terminal_exit',True),('terminal_exit',2),
    ('counts',{'PASS':True,'FAIL':0,'ERROR':0,'SKIP':0}),('authority_effect','EXECUTE'),('signature','SIGNED'),('collected',['wrong.identity'])]):
    def test(self,k=key,v=value):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d);p[k]=v;save_json(out/'t5-PART.json',p)
            with patch.object(q,'expected_ids',return_value={'t5':ids}),self.assertRaises(MMCError):q.verify_part(out,root,'t5')
    setattr(StageTests,'test_mutation_'+str(index),test)
