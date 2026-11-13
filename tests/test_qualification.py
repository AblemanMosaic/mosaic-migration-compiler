import json,tempfile,unittest,hashlib
from pathlib import Path
from .helpers import ROOT,copied,refuses
from mosaic_mmc import canonical,decode
from tools.qualify import verify_stage,_environment
from tools.check_vectors import check as check_vectors

class StageTests(unittest.TestCase):
    def make(self,path):
        runs=[{'script':'compile_and_inspect.py','exit_code':0},{'script':'blocked_retirement.py','exit_code':0}]
        (path/'examples.json').write_bytes(canonical({'schema':'mmc.example-results.t1','source_root':'a'*64,'runs':runs}))
        for n in ['compile_and_inspect','blocked_retirement']:
            for ext in ['stdout.txt','stderr.txt']:(path/(n+'.'+ext)).write_bytes(b'')
        outputs=[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(path.iterdir())]
        data={'schema':'mmc.local-stage.t1','phase':'examples','source_root':'a'*64,'environment':_environment(),'outputs':outputs,'result':{'runs':runs},'terminal_exit':0,'authority_effect':'NONE','signature':'NOT_SIGNED'}
        (path/'EXAMPLES-STAGE.json').write_bytes(canonical(data));return data
    def test_valid_bound_stage(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.make(p);self.assertEqual(verify_stage(p,'examples','a'*64)['terminal_exit'],0)
    def test_changed_bound_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.make(p);(p/'examples.json').write_bytes(b'{}');refuses(self,lambda:verify_stage(p,'examples','a'*64),'MMC_STAGE_OUTPUT_HASH')
    def test_duplicate_report_fields(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);self.make(p);raw=(p/'EXAMPLES-STAGE.json').read_bytes();(p/'EXAMPLES-STAGE.json').write_bytes(raw.replace(b'"terminal_exit":0',b'"terminal_exit":2,"terminal_exit":0'))
            refuses(self,lambda:verify_stage(p,'examples','a'*64),'MMC_DUPLICATE_KEY')
    def test_extra_unlisted_stage_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=self.make(p);data['outputs'].append(data['outputs'][0]);(p/'EXAMPLES-STAGE.json').write_bytes(canonical(data));refuses(self,lambda:verify_stage(p,'examples','a'*64),'MMC_STAGE_OUTPUTS')
    def test_frozen_vectors(self):self.assertEqual(len(check_vectors()['cases']),20)
    def test_fixture_lock(self):
        lock=decode((ROOT/'provenance/FIXTURE-LOCK.json').read_bytes())
        for row in lock['files']:self.assertEqual(hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest(),row['sha256'])

for field,bad in [('schema','fake'),('phase','tests'),('source_root','b'*64),('authority_effect','EXECUTE'),('terminal_exit',False),('signature','SIGNED'),('result',{'status':'PASS'})]:
    def test(self,field=field,bad=bad):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=self.make(p);data[field]=bad;(p/'EXAMPLES-STAGE.json').write_bytes(canonical(data));refuses(self,lambda:verify_stage(p,'examples','a'*64))
    setattr(StageTests,'test_stage_mutation_'+field,test)
for field,bad in [('native_pippi','ENFORCED'),('independent_review','PASS'),('third_party_runtime_dependencies',['hidden']),('python',True)]:
    def test(self,field=field,bad=bad):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=self.make(p);data['environment'][field]=bad;(p/'EXAMPLES-STAGE.json').write_bytes(canonical(data));refuses(self,lambda:verify_stage(p,'examples','a'*64),'MMC_STAGE_ENVIRONMENT')
    setattr(StageTests,'test_environment_mutation_'+field,test)
