import hashlib,tempfile,unittest
from .helpers import *
from mosaic_mmc import canonical,decode
from tools_t2.qualify import verify_stage,environment,EXAMPLES,OUTPUTS
from tools_t2.check_vectors import check

class QualificationTests(unittest.TestCase):
    def make(self,p):
        result={'runs':[{'script':s,'exit_code':0} for s in EXAMPLES]}
        (p/'examples.json').write_bytes(canonical({'schema':'mmc.examples.t2','source_root':'a'*64,**result}))
        for i in range(len(EXAMPLES)):
            for ext in ('stdout.txt','stderr.txt'):(p/f'example-{i}.{ext}').write_bytes(b'')
        record={'schema':'mmc.local-stage.t2','phase':'examples','source_root':'a'*64,'environment':environment(),'outputs':[{'path':n,'bytes':(p/n).stat().st_size,'sha256':hashlib.sha256((p/n).read_bytes()).hexdigest()} for n in sorted(OUTPUTS['examples'])],'result':result,'terminal_exit':0,'authority_effect':'NONE','signature':'NOT_SIGNED'}
        (p/'STAGE.json').write_bytes(canonical(record));return record
    def test_valid_bound_stage(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.make(p);self.assertEqual(verify_stage(p,'examples','a'*64)['terminal_exit'],0)
    def test_corrupt_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.make(p);(p/'example-1.stdout.txt').write_bytes(b'forged');refusal(self,lambda:verify_stage(p,'examples','a'*64),'MMC_T2_STAGE_OUTPUT_HASH')
    def test_extra_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.make(p);(p/'unexpected.json').write_bytes(b'{}');refusal(self,lambda:verify_stage(p,'examples','a'*64),'MMC_T2_STAGE_OUTPUT_CLOSURE')
    def test_duplicate_json(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.make(p);raw=(p/'STAGE.json').read_bytes().replace(b'"terminal_exit":0',b'"terminal_exit":2,"terminal_exit":0');(p/'STAGE.json').write_bytes(raw)
            refusal(self,lambda:verify_stage(p,'examples','a'*64),'MMC_DUPLICATE_KEY')
    def test_duplicate_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r=self.make(p);r['outputs'][0]=clone(r['outputs'][1]);(p/'STAGE.json').write_bytes(canonical(r));refusal(self,lambda:verify_stage(p,'examples','a'*64))
    def test_frozen_t2_vectors(self):self.assertEqual(len(check()['cases']),38)
    def test_frozen_program(self):
        from tools.common import verify_freeze
        self.assertEqual(verify_freeze()['program_root'],'abf1559fdede121a573335243b91dfa38014c6c825218ff2a6273656e593c7b7')
    def test_t2_contract_pin(self):
        from mosaic_mmc_t2.common import digest
        from mosaic_mmc_t2._pins import CONTRACT_ROOT
        c=decode((ROOT/'model/domain-t2/CONTRACT.json').read_bytes());self.assertEqual(digest('contract',c),CONTRACT_ROOT)
        for row in c['references']:self.assertEqual(hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest(),row['sha256'])

for field,bad in [('schema','other'),('phase','tests'),('source_root','b'*64),('terminal_exit',False),('authority_effect','EXECUTE'),('signature','SIGNED'),('result',{'status':'PASS'})]:
    def test(self,field=field,bad=bad):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r=self.make(p);r[field]=bad;(p/'STAGE.json').write_bytes(canonical(r));refusal(self,lambda:verify_stage(p,'examples','a'*64))
    setattr(QualificationTests,'test_stage_mutation_'+field,test)
for field,bad in [('python',True),('native_pippi','ENFORCED'),('independent_review','PASS'),('runtime_dependencies',['hidden'])]:
    def test(self,field=field,bad=bad):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r=self.make(p);r['environment'][field]=bad;(p/'STAGE.json').write_bytes(canonical(r));refusal(self,lambda:verify_stage(p,'examples','a'*64))
    setattr(QualificationTests,'test_environment_mutation_'+field,test)

class GateTests(unittest.TestCase):
    def fixture(self):
        from tools_t2.gates import LEG_NAMES
        cases=decode((ROOT/'constitution/ACCEPTANCE.json').read_bytes())['cases']
        reg={'foundation_tests':['base.test'],'tests':['domain.test'],'acceptance':{c['id']:['domain.test'] for c in cases if c['gate']=='T2'}}
        r={'schema':'mmc.qualification-input.t2','source_root':'a'*64,'program_root':'abf1559fdede121a573335243b91dfa38014c6c825218ff2a6273656e593c7b7','tests':[{'id':i,'status':'PASS'} for i in ['base.test','domain.test']],'legs':{n:{'status':'NOT_DUE_T2_RETAINED' if n=='end_to_end_where_due' else 'PASS','terminal_exit':0,'evidence_sha256':'b'*64} for n in LEG_NAMES},'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED','independent_study':'NOT_PERFORMED','authority_effect':'NONE','product_complete':False}
        return r,reg
    def test_modelled_gate_retains_future(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();x=assess(r,expected_source='a'*64,registry=reg);self.assertEqual(list(x['case_dispositions'].values()).count('NOT_RUN'),52)
    def test_missing_case(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();reg['acceptance'].pop(next(iter(reg['acceptance'])));refusal(self,lambda:assess(r,expected_source='a'*64,registry=reg),'MMC_T2_GATE_CASES')
    def test_false_completion(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();r['product_complete']=True;refusal(self,lambda:assess(r,expected_source='a'*64,registry=reg),'MMC_T2_GATE_OVERCLAIM')
    def test_native_not_invented(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();r['native_pippi']='ENFORCED';refusal(self,lambda:assess(r,expected_source='a'*64,registry=reg),'MMC_T2_GATE_OVERCLAIM')
    def test_independent_research_not_invented(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();r['independent_study']='PASS';refusal(self,lambda:assess(r,expected_source='a'*64,registry=reg),'MMC_T2_GATE_OVERCLAIM')
    def test_missing_external_leg(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();r['legs'].pop('installed_wheel');refusal(self,lambda:assess(r,expected_source='a'*64,registry=reg),'MMC_T2_GATE_LEGS')
    def test_boolean_terminal(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();r['legs']['installed_wheel']['terminal_exit']=False;refusal(self,lambda:assess(r,expected_source='a'*64,registry=reg),'MMC_T2_GATE_LEG')
    def test_synthetic_end_to_end_not_promoted(self):
        from tools_t2.gates import assess
        r,reg=self.fixture();r['legs']['end_to_end_where_due']['status']='PASS';refusal(self,lambda:assess(r,expected_source='a'*64,registry=reg),'MMC_T2_GATE_LEG')
