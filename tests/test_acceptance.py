import hashlib,io,json,os,random,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from .helpers import ROOT,model,get,a,copied,refuses
from mosaic_mmc import canonical,decode,digest,validate_model,compile_model,verify_compilation,capabilities
from mosaic_mmc.compiler import constant_value
from mosaic_mmc.contracts import contract,realization_identity
from mosaic_mmc.abi import dispatch
from tools.common import verify_freeze
from tools.package import build_source,verify_source_archive,build_wheel,zip_bytes
from tools.gates import assess_turn1,LEG_NAMES

class ModelAcceptance(unittest.TestCase):
    def test_ac_model_01(self):
        m=validate_model(model());self.assertEqual({o['kind'] for o in m['objects']},set(contract('foundation')['kinds']))
        m['objects'][0]['kind']='Unknown';refuses(self,lambda:validate_model(m),'MMC_KIND_UNSUPPORTED')
    def test_ac_model_02(self):
        for key,val in [('revision',True),('revision',None),('objects',{}),('initial_states',{})]:
            m=model();m[key]=val;refuses(self,lambda:validate_model(m))
        m=model();a(m,'producer.old')['resumable']=1;refuses(self,lambda:validate_model(m),'MMC_EXACT_TYPE')
        m=model();m['extra']=True;refuses(self,lambda:validate_model(m),'MMC_FIELDS')
    def test_ac_model_03(self):
        m=model();m['objects'].append(copied(m['objects'][0]));refuses(self,lambda:validate_model(m),'MMC_DUPLICATE_ID')
        m=model();a(m,'producer.old')['roles']=['worker','worker'];refuses(self,lambda:validate_model(m),'MMC_DUPLICATE_MEMBER')
    def test_ac_model_04(self):
        m=model();a(m,'flow.legacy')['asset']='absent';refuses(self,lambda:validate_model(m),'MMC_REFERENCE_MISSING')
        m=model();a(m,'flow.legacy')['asset']='producer.old';refuses(self,lambda:validate_model(m),'MMC_REFERENCE_KIND')
    def test_ac_model_05(self):
        m=model();a(m,'cohort.blue')['members'].remove('producer.old');refuses(self,lambda:validate_model(m))
        m=model();a(m,'effect.copy')['target']='consumer.main';refuses(self,lambda:validate_model(m),'MMC_EFFECT_SCOPE')
    def test_ac_model_06(self):
        c=compile_model(model());obs=a(c['ir']['normalized_model'],'obs.drain')
        self.assertEqual(obs['coverage'],'PARTIAL');self.assertEqual(obs['status'],'UNKNOWN')
        self.assertEqual(c['receipt']['body']['runtime_guards'],18)
    def test_ac_model_07(self):
        m=model();del get(m,'producer.old')['provenance']['source_digest'];refuses(self,lambda:validate_model(m),'MMC_FIELDS')
        m=model();get(m,'producer.old')['provenance']['observed_at']=True;refuses(self,lambda:validate_model(m),'MMC_PROVENANCE')
    def test_ac_model_08(self):
        m=model();m['objects']*=30;refuses(self,lambda:validate_model(m),'MMC_OBJECT_LIMIT')
        refuses(self,lambda:decode(b' '* (2*1024*1024+1)),'MMC_BYTE_LIMIT')
        refuses(self,lambda:canonical('x'*65537),'MMC_STRING_LIMIT')
        v=None
        for _ in range(34):v=[v]
        refuses(self,lambda:canonical(v),'MMC_DEPTH_LIMIT')
        m=model();rule={'op':'literal','value':True}
        for _ in range(18):rule={'op':'not','item':rule}
        a(m,'policy.base')['rule']=rule;refuses(self,lambda:validate_model(m),'MMC_PREDICATE_LIMIT')
    def test_ac_model_09(self):
        m=model();n=copied(m);random.Random(171).shuffle(n['objects']);n['initial_states'].reverse()
        a(n,'cohort.blue')['members'].reverse();a(n,'producer.old')['roles'].reverse()
        self.assertEqual(canonical(validate_model(m)),canonical(validate_model(n)))
        n=model();a(n,'policy.base')['rule']={'op':'all','items':[{'op':'literal','value':True},{'op':'literal','value':False}]}
        p=copied(n);a(p,'policy.base')['rule']['items'].reverse()
        self.assertNotEqual(canonical(validate_model(n)),canonical(validate_model(p)))
    def test_ac_model_10(self):
        for raw in [b'{"a":1,"a":2}',b'1.0',b'NaN',b'"\\ud800"']:
            refuses(self,lambda raw=raw:decode(raw))
        m=model();m['revision']=-1;refuses(self,lambda:validate_model(m),'MMC_REVISION')
    def test_ac_model_11(self):
        for domain in ['identity','storage','policy','workload']:
            m=validate_model(model(domain));self.assertEqual(m['domain'],domain)
            self.assertEqual(m['profile_ref'],model()['profile_ref'])
        self.assertIn('REPRESENTATION_EXAMPLES',capabilities()['domain_profiles'])
    def test_ac_model_12(self):
        m=model();a(m,'obs.drain').update(status='ASSERTED',value=True,measured_at=20,valid_until=10)
        refuses(self,lambda:validate_model(m),'MMC_INTERVAL')
        m=model();a(m,'evidence.fixture')['subject']='consumer.main';refuses(self,lambda:validate_model(m),'MMC_EVIDENCE_SCOPE')
        m=model();a(m,'effect.copy')['operation']='execute';refuses(self,lambda:validate_model(m),'MMC_DECLARED_OPERATION_SCOPE')

class CompilerAcceptance(unittest.TestCase):
    def test_ac_compiler_01(self):
        m=model();self.assertEqual(canonical(compile_model(m)),canonical(compile_model(m)))
    def test_ac_compiler_02(self):
        m=model();expected=canonical(compile_model(m))
        for seed in range(8):
            n=copied(m);random.Random(seed).shuffle(n['objects']);self.assertEqual(canonical(compile_model(n)),expected)
    def test_ac_compiler_03(self):
        for key,val in [('id','other'),('version','2'),('sha256','0'*64)]:
            m=model();m['profile_ref'][key]=val;refuses(self,lambda:compile_model(m),'MMC_PROFILE_PIN_MISMATCH')
    def test_ac_compiler_04(self):
        c=compile_model(model());steps=c['ir']['steps']
        self.assertEqual([s['id'] for s in steps],['step.prepare','step.cutover','step.retire'])
        self.assertEqual(steps[2]['predecessors'],['step.cutover'])
        m=model();m['objects']=[o for o in m['objects'] if o['id']!='order.prepare-cutover']
        # Without an ordering chain the shared producer transitions are ambiguous.
        refuses(self,lambda:compile_model(m),'MMC_UNORDERED_TARGET_CHANGES')
    def test_ac_compiler_05(self):
        m=model();dep=copied(get(m,'order.prepare-cutover'));dep['id']='order.cycle';dep['attributes'].update(before='step.retire',after='step.prepare');m['objects'].append(dep)
        e=refuses(self,lambda:compile_model(m),'MMC_ORDER_CYCLE');self.assertIn('step.prepare',e.detail)
    def test_ac_compiler_06(self):
        m=model();m['initial_states']=m['initial_states'][:1];refuses(self,lambda:compile_model(m),'MMC_INITIAL_STATE_MISSING')
        m=model();a(m,'step.retire')['from_states'][0]['state']='legacy';refuses(self,lambda:compile_model(m),'MMC_STATE_CHAIN')
    def test_ac_compiler_07(self):
        c=compile_model(model());steps=c['ir']['steps'];g=[g for s in steps for g in s['guards']]
        self.assertEqual(len(g),21);self.assertEqual(sum(x['category']=='applicable-policy' for x in g),3)
        self.assertTrue(all(x['source_refs'] for x in g));self.assertEqual(steps[1]['effects'][0]['binding_status'],'UNBOUND')
        expected=set(contract('foundation')['retirement_guard_categories'])
        self.assertEqual({x['category'] for x in steps[-1]['guards'] if '/retirement/' in x['id']},expected)
    def test_ac_compiler_08(self):
        m=model();a(m,'obs.drain').update(status='ASSERTED',value=True,coverage='DECLARED_COMPLETE',measured_at=0,valid_until=9999)
        c=compile_model(m);self.assertEqual(c['receipt']['body']['runtime_guards'],18)
        self.assertEqual(c['receipt']['body']['eligibility'],'NOT_EVALUATED');self.assertEqual(c['receipt']['body']['effects'],'NOT_EXECUTED')
    def test_ac_compiler_09(self):
        m=model();a(m,'need.drain')['rule']={'op':'literal','value':False};c=compile_model(m)
        self.assertEqual(c['receipt']['body']['status'],'COMPILED_WITH_STATIC_BLOCKERS');self.assertEqual(c['receipt']['body']['static_blockers'],2)
    def test_ac_compiler_10(self):
        m=model();c=compile_model(m);pin=c['ir']['model_root'];forged=copied(c)
        forged['ir']['steps'].pop();forged['ir_root']=digest('workflow-ir',forged['ir'])
        forged['receipt']['body']['ir_root']=forged['ir_root'];forged['receipt']['root']=digest('compilation-receipt',forged['receipt']['body'])
        refuses(self,lambda:verify_compilation(m,forged,expected_model_root=pin),'MMC_COMPILATION_MISMATCH')
        refuses(self,lambda:verify_compilation(m,c,expected_model_root='0'*64),'MMC_EXPECTED_MODEL_MISMATCH')
    def test_ac_compiler_11(self):
        m=model();before=compile_model(m);m['revision']+=1;after=compile_model(m)
        self.assertNotEqual(before['ir_root'],after['ir_root']);self.assertEqual(before['ir']['normalized_model']['revision'],1)
        with patch('mosaic_mmc.compiler.realization_identity',return_value='f'*64):other=compile_model(model())
        self.assertNotEqual(before['ir_root'],other['ir_root']);self.assertEqual(before['ir']['model_root'],other['ir']['model_root'])
    def test_ac_compiler_12(self):
        # Patches monitor attempts to perform external/ambient work while compiling.
        import socket,time
        m=model();compile_model(m)
        with patch('socket.socket',side_effect=AssertionError('network')),patch('subprocess.run',side_effect=AssertionError('process')),patch('time.time',side_effect=AssertionError('clock')),patch.object(Path,'write_bytes',side_effect=AssertionError('write')):
            c=compile_model(m)
        r=dispatch({'schema':'mmc.request.t1','operation':'compile','arguments':{'model':m}})
        self.assertEqual(canonical(c),canonical(r['result']))
        refuses(self,lambda:dispatch({'schema':'mmc.request.t1','operation':'commit','arguments':{}}),'MMC_OPERATION_UNSUPPORTED')
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1')
        proc=subprocess.run([sys.executable,'-m','mosaic_mmc','compile',str(ROOT/'examples/identity.json')],env=env,capture_output=True,timeout=20)
        self.assertEqual(proc.returncode,0,proc.stderr);self.assertEqual(decode(proc.stdout)['result'],c)

class FidelityAcceptance(unittest.TestCase):
    def test_ac_repro_01(self):
        self.assertEqual(verify_freeze()['files'],10)
        import shutil
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td);shutil.copytree(ROOT/'constitution',tmp/'constitution');shutil.copytree(ROOT/'src/mosaic_mmc/data',tmp/'src/mosaic_mmc/data')
            (tmp/'constitution/PROGRAM.json').write_bytes(b'{}');refuses(self,lambda:verify_freeze(tmp),'MMC_FREEZE_FILE')
    @staticmethod
    def record():
        registry={'tests':['test.example'], 'acceptance':{c['id']:['test.example'] for c in contract('cases')['cases'] if c['gate']=='T1'}}
        record={'schema':'mmc.qualification-input.t1','source_root':'a'*64,'program_root':verify_freeze()['program_root'],
                'tests':[{'id':'test.example','status':'PASS'}], 'legs':{n:{'status':'PASS','exit_code':0,'evidence_sha256':'b'*64} for n in LEG_NAMES},
                'native_pippi':'NOT_BOUND','authority_effect':'NONE','independent_study':'NOT_PERFORMED'}
        return registry,record
    def test_ac_repro_02(self):
        registry,record=self.record();self.assertEqual(assess_turn1(record,registry,expected_source='a'*64)['remaining_not_run'],71)
        for mutation in ['tests','legs','schema','authority_effect']:
            bad=copied(record)
            if mutation=='tests':bad['tests']=[]
            elif mutation=='legs':del bad['legs']['examples']
            else:bad[mutation]='PASS'
            refuses(self,lambda:assess_turn1(bad,registry,expected_source='a'*64))
        broken=copied(registry);broken['acceptance'].pop(next(iter(broken['acceptance'])))
        refuses(self,lambda:assess_turn1(record,broken,expected_source='a'*64),'MMC_GATE_CASE_COVERAGE')
    def test_ac_repro_03(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'a.txt').write_bytes(b'x');one=build_source(root);two=build_source(root)
            self.assertEqual(one,two);self.assertEqual(verify_source_archive(one)['members'],2)
            with zipfile.ZipFile(io.BytesIO(one)) as z: vals={n:z.read(n) for n in z.namelist()}
            vals['a.txt']=b'y';refuses(self,lambda:verify_source_archive(zip_bytes(vals)),'MMC_ARCHIVE_HASH')
    def test_ac_repro_04(self):
        # An actual offline installation; no --system-site-packages and no source PYTHONPATH.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);wheel=root/'mosaic_migration_compiler-0.1.0a1-py3-none-any.whl';wheel.write_bytes(build_wheel())
            envroot=root/'venv'
            create=subprocess.run([sys.executable,'-m','venv',str(envroot)],capture_output=True,timeout=30)
            self.assertEqual(create.returncode,0,create.stderr)
            py=envroot/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            install=subprocess.run([str(py),'-I','-m','pip','install','--no-index','--no-deps',str(wheel)],capture_output=True,timeout=30)
            self.assertEqual(install.returncode,0,install.stderr)
            proc=subprocess.run([str(py),'-I','-m','mosaic_mmc','compile',str(ROOT/'examples/identity.json')],cwd=root,capture_output=True,timeout=30)
            self.assertEqual(proc.returncode,0,proc.stderr)
            actual=decode(proc.stdout)['result'];self.assertEqual(canonical(actual),canonical(compile_model(model())))
    def test_ac_repro_07(self):
        registry,record=self.record()
        for key,value in [('independent_study','PASS'),('native_pippi','ENFORCED'),('authority_effect','EXECUTE')]:
            bad=copied(record);bad[key]=value;refuses(self,lambda:assess_turn1(bad,registry,expected_source='a'*64),'MMC_GATE_OVERCLAIM')
