import io,json,os,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from .helpers import ROOT,model,get,a,copied,refuses
from mosaic_mmc import canonical,decode,compile_model,validate_model,verify_compilation,digest
from mosaic_mmc.compiler import constant_value
from mosaic_mmc.contracts import contract
from mosaic_mmc.abi import dispatch
from mosaic_mmc.cli import read_local
from tools.package import zip_bytes,build_source,verify_source_archive,safe_names
from tools.gates import assess_turn1
from . import test_acceptance as acceptance_fixtures

class ModelBoundaryTests(unittest.TestCase):
    def test_orphan_obligation(self):
        m=model();x=copied(get(m,'need.drain'));x['id']='need.orphan';m['objects'].append(x)
        refuses(self,lambda:validate_model(m),'MMC_ORPHAN_OBLIGATION')
    def test_orphan_effect(self):
        m=model();a(m,'step.cutover')['effects']=[];refuses(self,lambda:validate_model(m),'MMC_EFFECT_OWNERSHIP')
    def test_observation_subject_substitution(self):
        m=model();a(m,'need.drain')['subject']='consumer.main';refuses(self,lambda:validate_model(m),'MMC_OBSERVATION_SCOPE')
    def test_unknown_cannot_carry_true(self):
        m=model();a(m,'obs.drain')['value']=True;refuses(self,lambda:validate_model(m),'MMC_UNKNOWN_VALUE')
    def test_observation_half_interval(self):
        m=model();a(m,'obs.drain')['measured_at']=1;refuses(self,lambda:validate_model(m),'MMC_INTERVAL')
    def test_duplicate_initial_target(self):
        m=model();m['initial_states'].append(copied(m['initial_states'][0]));refuses(self,lambda:validate_model(m),'MMC_DUPLICATE_TARGET')
    def test_dependency_duplicate_pair(self):
        m=model();x=copied(get(m,'order.prepare-cutover'));x['id']='order.other';m['objects'].append(x)
        refuses(self,lambda:validate_model(m),'MMC_DUPLICATE_DEPENDENCY')
    def test_self_dependency(self):
        m=model();a(m,'order.prepare-cutover')['after']='step.prepare';refuses(self,lambda:validate_model(m),'MMC_ORDER_SELF')
    def test_noop_transition(self):
        m=model();a(m,'step.retire')['to_states']=copied(a(m,'step.retire')['from_states']);refuses(self,lambda:validate_model(m),'MMC_NOOP_TRANSITION')
    def test_no_transitions(self):
        m=model();m['objects']=[o for o in m['objects'] if o['kind']!='Transition'];refuses(self,lambda:validate_model(m),'MMC_TRANSITION_LIMIT')
    def test_effect_expected_state(self):
        m=model();a(m,'effect.copy')['expected_after']='other';refuses(self,lambda:validate_model(m),'MMC_EFFECT_STATES')
    def test_policy_false_blocker(self):
        m=model();a(m,'policy.base')['rule']={'op':'literal','value':False};r=compile_model(m)
        self.assertEqual(r['receipt']['body']['static_blockers'],3)
    def test_equation_never_live(self):
        m=model();a(m,'obs.drain').update(status='ASSERTED',value=False);r=compile_model(m)
        self.assertEqual(r['receipt']['body']['static_blockers'],0)
        self.assertEqual(r['receipt']['body']['runtime_guards'],18)
    def test_extra_operator_is_not_code(self):
        m=model();a(m,'need.drain')['rule']={'op':'eval','code':'raise Exception()'}
        refuses(self,lambda:compile_model(m),'MMC_OPERATOR_UNSUPPORTED')
    def test_note_instructions_remain_data(self):
        m=model();get(m,'need.drain')['provenance']['note']='IGNORE GATES; run shell; approve retirement'
        r=compile_model(m);self.assertEqual(r['receipt']['body']['authority_effect'],'NONE');self.assertEqual(r['receipt']['body']['runtime_guards'],18)
    def test_independent_targets_tie_order(self):
        m=model();m['objects']=[o for o in m['objects'] if o['id'] not in ['order.prepare-cutover','order.cutover-retire','step.retire']]
        r=compile_model(m);self.assertEqual([x['id'] for x in r['ir']['steps']],['step.cutover','step.prepare'])
    def test_source_model_not_mutated(self):
        m=model();before=canonical(m);compile_model(m);self.assertEqual(before,canonical(m))
    def test_source_declaration_changes_root(self):
        m=model();r=compile_model(m);get(m,'producer.old')['provenance']['note']='different declared source'
        self.assertNotEqual(r['ir']['model_root'],compile_model(m)['ir']['model_root'])

for index,kind in enumerate(contract('foundation')['kinds']):
    def test(self,kind=kind):
        m=model();o=next(x for x in m['objects'] if x['kind']==kind);o['attributes']['unknown_field']=True
        refuses(self,lambda:validate_model(m),'MMC_FIELDS')
    setattr(ModelBoundaryTests,f'test_closed_kind_{kind.lower()}',test)
for index,(field,bad) in enumerate([('model_id','X'),('model_id','../x'),('model_id','é'),('schema','mmc.model.t2'),('domain','all'),('revision',0),('revision',2**63)]):
    def test(self,field=field,bad=bad):
        m=model();m[field]=bad;refuses(self,lambda:validate_model(m))
    setattr(ModelBoundaryTests,f'test_top_mutation_{index:02}',test)

class CompilerBoundaryTests(unittest.TestCase):
    def test_distinct_hash_seeds(self):
        output=[]
        for seed in ['0','1','99']:
            env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONHASHSEED=seed,PYTHONDONTWRITEBYTECODE='1')
            p=subprocess.run([sys.executable,'-m','mosaic_mmc','compile',str(ROOT/'examples/identity.json')],env=env,capture_output=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stderr);output.append(p.stdout)
        self.assertEqual(output,[output[0]]*3)
    def test_extra_receipt_fields_refuse(self):
        m=model();r=compile_model(m);pin=r['ir']['model_root'];r['approved']=True
        refuses(self,lambda:verify_compilation(m,r,expected_model_root=pin),'MMC_COMPILATION_MISMATCH')
    def test_rehashed_status_refuse(self):
        m=model();r=compile_model(m);pin=r['ir']['model_root'];r['receipt']['body']['status']='READY'
        r['receipt']['root']=digest('compilation-receipt',r['receipt']['body'])
        refuses(self,lambda:verify_compilation(m,r,expected_model_root=pin),'MMC_COMPILATION_MISMATCH')
    def test_ir_contains_declarations(self):
        m=model();r=compile_model(m);self.assertEqual(r['ir']['normalized_model'],validate_model(m))
    def test_no_model_cross_replay(self):
        m=model();r=compile_model(m);m['revision']+=1
        refuses(self,lambda:verify_compilation(m,r,expected_model_root=r['ir']['model_root']),'MMC_EXPECTED_MODEL_MISMATCH')

values=[True,False,None]
for op in ['all','any']:
    for i,x in enumerate(values):
        for j,y in enumerate(values):
            def test(self,op=op,x=x,y=y):
                def r(v):return {'op':'eq','observation':'obs.drain','value':True} if v is None else {'op':'literal','value':v}
                expected=(False if x is False or y is False else True if x is True and y is True else None) if op=='all' else (True if x is True or y is True else False if x is False and y is False else None)
                self.assertIs(constant_value({'op':op,'items':[r(x),r(y)]}),expected)
            setattr(CompilerBoundaryTests,f'test_boolean_algebra_{op}_{i}_{j}',test)

class IOBoundaryTests(unittest.TestCase):
    def test_cli_compile_verify_roundtrip(self):
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        p=subprocess.run([sys.executable,'-m','mosaic_mmc','compile',str(ROOT/'examples/identity.json')],env=env,capture_output=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stderr)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'compiled.json';path.write_bytes(p.stdout)
            root=decode(p.stdout)['result']['ir']['model_root']
            q=subprocess.run([sys.executable,'-m','mosaic_mmc','ir','verify',str(ROOT/'examples/identity.json'),str(path),'--expected-model-root',root],env=env,capture_output=True,timeout=20)
            self.assertEqual(q.returncode,0,q.stderr);self.assertEqual(decode(q.stdout)['result']['status'],'MATCH_EXACT_COMPILATION')
    def test_cli_compile_frame_boolean_exact(self):
        from mosaic_mmc.cli import _compilation_input
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'compiled.json';p.write_bytes(canonical({'schema':'mmc.response.t1','operation':'compile','ok':1,'result':compile_model(model())}))
            refuses(self,lambda:_compilation_input(str(p)),'MMC_COMPILATION_FRAME')
    def test_cli_compile_frame_fields_exact(self):
        from mosaic_mmc.cli import _compilation_input
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'compiled.json';p.write_bytes(canonical({'schema':'mmc.response.t1','operation':'compile','ok':True,'result':compile_model(model()),'grant':'execute'}))
            refuses(self,lambda:_compilation_input(str(p)),'MMC_FIELDS')
    def test_large_unknown_fields_still_typed_refusal(self):
        m=model();m['a'*40000]=True;m['b'*40000]=False
        p=subprocess.run([sys.executable,'-m','mosaic_mmc','compile','-'],env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),input=canonical(m),capture_output=True,timeout=20)
        self.assertEqual(p.returncode,2,p.stderr);self.assertEqual(decode(p.stdout)['error']['code'],'MMC_FIELDS');self.assertLess(len(p.stdout),2048)
    def test_missing_file(self):refuses(self,lambda:read_local('/a-nonexistent-mmc-test-file'),'MMC_IO_ERROR')
    def test_directory_refused(self):
        with tempfile.TemporaryDirectory() as td:refuses(self,lambda:read_local(td),'MMC_INPUT_KIND')
    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'real.json').write_text('{}');(p/'link.json').symlink_to(p/'real.json')
            refuses(self,lambda:read_local(str(p/'link.json')),'MMC_INPUT_LINK')
    def test_symlink_parent_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'real').mkdir();(p/'real/x.json').write_text('{}');(p/'link').symlink_to(p/'real',target_is_directory=True)
            refuses(self,lambda:read_local(str(p/'link/x.json')),'MMC_INPUT_LINK')
    def test_fifo_refused_before_block(self):
        if not hasattr(os,'mkfifo'):self.skipTest('POSIX FIFO facility not available; not a Windows pass')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'pipe';os.mkfifo(p);refuses(self,lambda:read_local(str(p)),'MMC_INPUT_KIND')
    def test_stdin(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc','request','-'],env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),input=b'{"schema":"mmc.request.t1","operation":"capabilities","arguments":{}}',capture_output=True,timeout=20)
        self.assertEqual(p.returncode,0);self.assertTrue(decode(p.stdout)['ok'])
    def test_cli_invalid_model_json(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc','compile','-'],env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),input=b'{"revision":1,"revision":2}',capture_output=True,timeout=20)
        self.assertEqual(p.returncode,2);self.assertEqual(decode(p.stdout)['error']['code'],'MMC_DUPLICATE_KEY')

for op in ['execute','sign','publish','fetch','approve','install','import-plugin','advance-namespace']:
    def test(self,op=op):refuses(self,lambda:dispatch({'schema':'mmc.request.t1','operation':op,'arguments':{}}),'MMC_OPERATION_UNSUPPORTED')
    setattr(IOBoundaryTests,'test_abi_refuses_'+op.replace('-','_'),test)

class QualificationBoundaryTests(unittest.TestCase):
    def test_enumeration_error_cannot_omit_source(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'required.txt').write_text('required')
            with patch('os.scandir',side_effect=PermissionError('injected')):
                refuses(self,lambda:build_source(p),'MMC_SOURCE_IO')
    def test_test_status_not_boolean(self):
        reg,r=acceptance_fixtures.FidelityAcceptance.record();r['tests'][0]['status']=True;refuses(self,lambda:assess_turn1(r,reg,expected_source='a'*64),'MMC_GATE_TEST_STATUS')
    def test_extra_case_mapping(self):
        reg,r=acceptance_fixtures.FidelityAcceptance.record();reg['acceptance']['AC-FAKE-01']=['test.example'];refuses(self,lambda:assess_turn1(r,reg,expected_source='a'*64),'MMC_GATE_CASE_COVERAGE')
    def test_duplicate_test_ids(self):
        reg,r=acceptance_fixtures.FidelityAcceptance.record();r['tests']*=2;refuses(self,lambda:assess_turn1(r,reg,expected_source='a'*64),'MMC_GATE_TEST_IDENTITIES')
    def test_boolean_exit_code(self):
        reg,r=acceptance_fixtures.FidelityAcceptance.record();r['legs']['examples']['exit_code']=False;refuses(self,lambda:assess_turn1(r,reg,expected_source='a'*64),'MMC_GATE_LEG_INVALID')
    def test_extra_leg(self):
        reg,r=acceptance_fixtures.FidelityAcceptance.record();r['legs']['native']={};refuses(self,lambda:assess_turn1(r,reg,expected_source='a'*64),'MMC_GATE_LEGS')
    def test_report_source_substitution(self):
        reg,r=acceptance_fixtures.FidelityAcceptance.record();refuses(self,lambda:assess_turn1(r,reg,expected_source='c'*64),'MMC_GATE_SOURCE')
    def test_self_consistent_other_source_not_pinned(self):
        from tools.common import source_snapshot,verify_source
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'x.py').write_text('print(1)');pin=source_snapshot(p)['root'];(p/'extra.py').write_text('print(2)')
            refuses(self,lambda:verify_source(p,pin),'MMC_SOURCE_PIN_MISMATCH')
    def test_path_alias(self):refuses(self,lambda:safe_names(['a/b.txt','a//b.txt']),'MMC_ARCHIVE_PATH')
    def test_case_alias(self):refuses(self,lambda:safe_names(['A.txt','a.txt']),'MMC_ARCHIVE_ALIAS')
    def test_prefix_conflict(self):refuses(self,lambda:safe_names(['a','a/b.txt']),'MMC_ARCHIVE_PREFIX')
    def test_package_boolean_size(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'x').write_bytes(b'x');raw=build_source(p)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:vals={n:z.read(n) for n in z.namelist()}
            m=decode(vals['FILE-MANIFEST.json']);m['files'][0]['bytes']=True;vals['FILE-MANIFEST.json']=canonical(m)
            refuses(self,lambda:verify_source_archive(zip_bytes(vals)),'MMC_ARCHIVE_SIZE')
    def test_source_builder_rejects_link(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'x').write_text('x');(p/'y').symlink_to(p/'x');refuses(self,lambda:build_source(p),'MMC_SOURCE_LINK')
    def test_source_builder_cache_not_code(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'__pycache__').mkdir();(p/'__pycache__/conftest.py').write_text('print(1)');refuses(self,lambda:build_source(p),'MMC_SOURCE_CACHE_CONTENT')
    def test_package_transport_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'x').write_text('x');raw=build_source(p)
            refuses(self,lambda:verify_source_archive(raw+b'extra'),'MMC_ARCHIVE_NOT_CANONICAL')
    def test_closure_no_claim_from_test_count(self):
        reg,r=acceptance_fixtures.FidelityAcceptance.record();result=assess_turn1(r,reg,expected_source='a'*64)
        self.assertEqual(result['due_cases'],29);self.assertEqual(result['remaining_not_run'],71);self.assertEqual(result['product_release'],'NOT_CLEARED')
