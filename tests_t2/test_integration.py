import hashlib,json,os,subprocess,sys,tempfile,unittest,zipfile
from unittest.mock import patch
from .helpers import *
from mosaic_mmc import canonical,decode,compile_model
from mosaic_mmc_t2 import *
from mosaic_mmc_t2.abi import dispatch
from mosaic_mmc_t2.common import digest,admit,shape
from mosaic_mmc_t2._pins import CONTRACT_ROOT

class IntegrationTests(unittest.TestCase):
    def test_four_compilations_retain_unknown_guards(self):
        for name in records():
            b=bundle(name);x=compile_domain(b);self.assertEqual(x['body']['status'],'COMPILED_WITH_RUNTIME_OBLIGATIONS')
            self.assertEqual(sum(g.get('compile_state')=='RUNTIME_REQUIRED' for s in x['body']['instructions'] for g in s['guards']),18)
            self.assertEqual(verify_compilation(b,x,expected_model_root=x['body']['model_root'])['status'],'MATCH_EXACT_DOMAIN_COMPILATION')
    def test_atomic_phase_compiles_without_kernel_change(self):
        from tests_t2.test_planner import phased
        m=graph_model();p=phased();p['phases']=[{'id':'phase.activate','members':['step.0','step.1'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'}]
        r=records()['workload'];r['workers']=[]
        b={'schema':'mmc.domain-compilation-input.t2','model':m,'planning':p,
           'assessments':[{'id':'assessment.'+str(i),'profile_ref':profile_reference('workload'),'transition':'step.'+str(i),'subject':'cohort.graph','record':r} for i in range(2)],
           'routes':{'schema':'mmc.routes-input.t2','routes':[{'cohort':'cohort.graph','use_case':'graph','legacy_version':'old','new_version':'new','active_route':'DUAL','producers':['actor.0','actor.1'],'workers':[],'assets':[],'consumers':[]}]},'retirements':[]}
        x=compile_domain(b);self.assertEqual(x['body']['status'],'COMPILED_WITH_RUNTIME_OBLIGATIONS');self.assertEqual(x['body']['plan']['body']['witness'][0]['transitions'],['step.0','step.1']);self.assertEqual(x['body']['effects'],'NOT_EXECUTED')
    def test_unknown_observations_never_discharge(self):
        b=bundle()
        for o in b['model']['objects']:
            if o['kind']=='Observation':o['attributes'].update(status='ASSERTED',value=True,measured_at=90,valid_until=110,coverage='DECLARED_COMPLETE')
        c=compile_domain(b);self.assertEqual(sum(g.get('compile_state')=='RUNTIME_REQUIRED' for s in c['body']['instructions'] for g in s['guards']),18)
    def test_forged_compilation_rehash(self):
        b=bundle();x=compile_domain(b);x['body']['operational_eligibility']='AUTHORIZED';x['root']=digest('compilation',x['body'])
        refusal(self,lambda:verify_compilation(b,x,expected_model_root=x['body']['model_root']),'MMC_T2_COMPILATION_MISMATCH')
    def test_false_expected_root(self):
        b=bundle();x=compile_domain(b);refusal(self,lambda:verify_compilation(b,x,expected_model_root='0'*64),'MMC_T2_EXPECTED_MODEL')
    def test_forged_profile_result_rehash(self):
        r=records()['identity'];ref=profile_reference('identity');x=assess_profile(ref,r);x['body']['result']['effects']='EXECUTED';x['root']=digest('report',x['body'])
        refusal(self,lambda:replay_assessment(ref,r,x),'MMC_T2_REPLAY_MISMATCH')
    def test_pin_substitution(self):
        r=profile_reference('identity');r['sha256']='0'*64;refusal(self,lambda:assess_profile(r,records()['identity']),'MMC_T2_PROFILE_PIN')
    def test_cross_profile(self):refusal(self,lambda:assess_profile(profile_reference('storage'),records()['identity']))
    def test_missing_assessment(self):
        b=bundle();b['assessments'].pop();refusal(self,lambda:compile_domain(b),'MMC_T2_DOMAIN_COVERAGE')
    def test_missing_retirement(self):
        b=bundle();b['retirements']=[];refusal(self,lambda:compile_domain(b),'MMC_T2_RETIREMENT_COVERAGE')
    def test_wrong_assessment_subject(self):
        b=bundle();b['assessments'][0]['subject']='consumer.main';refusal(self,lambda:compile_domain(b),'MMC_T2_ASSESSMENT_SCOPE')
    def test_wrong_retirement_epoch(self):
        b=bundle();b['retirements'][0]['record']['migration_epoch']=2;refusal(self,lambda:compile_domain(b),'MMC_T2_RETIREMENT_SCOPE')
    def test_missing_workers_cannot_compile(self):
        b=bundle('workload')
        for a in b['assessments']:a['record']['workers']=[]
        refusal(self,lambda:compile_domain(b),'MMC_T2_ASSESSMENT_SCOPE')
    def test_missing_assets_cannot_compile(self):
        b=bundle('storage')
        for a in b['assessments']:a['record']['source']['items']=[];a['record']['dispositions']=[];a['record']['allow_extra_destination']=True
        refusal(self,lambda:compile_domain(b),'MMC_T2_ASSESSMENT_SCOPE')
    def test_declared_authority_operation(self):
        m=model();next(o for o in m['objects'] if o['id']=='authority.owner')['attributes']['operations']=['migrate']
        self.assertEqual(assess_retirement(m,retirement())['status'],'BLOCKED_FOR_SUPPLIED_MODEL')
    def test_claimed_evidence_cannot_authorize(self):
        r=records()['identity'];r['approved']=True;refusal(self,lambda:assess_profile(profile_reference('identity'),r))
    def test_caller_inputs_detached(self):
        b=bundle();before=canonical(b);x=compile_domain(b);self.assertEqual(canonical(b),before);saved=canonical(x);b['model']['revision']=3;self.assertEqual(canonical(x),saved)
    def test_domain_block_reaches_compilation(self):
        b=bundle();b['assessments'][0]['record']['audience']='wrong';x=compile_domain(b);self.assertEqual(x['body']['status'],'COMPILED_WITH_MODEL_BLOCKERS')
    def test_static_false_survives_overlay(self):
        b=bundle();next(o for o in b['model']['objects'] if o['id']=='policy.base')['attributes']['rule']={'op':'literal','value':False}
        x=compile_domain(b);self.assertTrue(any(q['kind']=='static-foundation' for q in x['body']['blockers']))
    def test_new_retirement_blocker_propagates(self):
        b=bundle();b['retirements'][0]['record']['assets'][0]['disposition']='UNRESOLVED';self.assertEqual(compile_domain(b)['body']['status'],'COMPILED_WITH_MODEL_BLOCKERS')
    def test_no_effect_calls(self):
        b=bundle()
        with patch('socket.socket',side_effect=AssertionError('network')),patch('subprocess.run',side_effect=AssertionError('process')),patch('time.time',side_effect=AssertionError('clock')):
            self.assertEqual(compile_domain(b)['body']['effects'],'NOT_EXECUTED')
    def test_t1_runtime_exact_preservation(self):
        from tools.public_predecessor import load_public_predecessor
        record=load_public_predecessor(1)
        self.assertGreater(len(record['rows']),0)
    def test_t1_compilation_exact_against_predecessor(self):
        from mosaic_mmc.contracts import realization_identity
        self.assertEqual(realization_identity(),'b8387cf06a06e26b290b8c3827c644068defd4ce8484167de98186d87452ee64')
    def test_schema_runtime_parity_valid(self):
        from mosaic_mmc_t2.common import data
        for name,r in records().items():
            exported=decode((ROOT/f'schemas/t2/{name}.json').read_bytes())
            self.assertEqual(canonical(data(name+'.schema.json')),canonical(exported))
            shape(r,exported)
    def test_all_discovered_operations_exist(self):
        self.assertEqual(set(capabilities()['operations']),set(__import__('mosaic_mmc_t2.abi',fromlist=['OPS']).OPS))
    def test_lifecycle_refuses_root_input(self):refusal(self,lambda:assess_lifecycle(True))

class InterfaceTests(unittest.TestCase):
    def test_library_abi_parity(self):
        ref=profile_reference('identity');r=records()['identity'];request={'schema':'mmc.request.t2','operation':'assess','arguments':{'profile_ref':ref,'record':r}}
        self.assertEqual(canonical(dispatch(request)['result']),canonical(assess_profile(ref,r)))
    def test_cli_round_trip(self):
        req={'schema':'mmc.request.t2','operation':'plan','arguments':{'model':graph_model(),'planning':simple_planning()}}
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t2','request','-'],input=canonical(req),capture_output=True,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},timeout=20)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout,canonical(dispatch(req))+b'\n')
    def test_cli_compile(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t2','compile',str(ROOT/'examples/t2/identity.json')],capture_output=True,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},timeout=20)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(decode(p.stdout)['result']['body']['status'],'COMPILED_WITH_RUNTIME_OBLIGATIONS')
    def test_cli_refuses_effect(self):
        req={'schema':'mmc.request.t2','operation':'commit','arguments':{}}
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t2','request','-'],input=canonical(req),capture_output=True,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},timeout=20)
        self.assertEqual(p.returncode,2);self.assertEqual(decode(p.stdout)['error']['code'],'MMC_T2_OPERATION_UNSUPPORTED')
    def test_unknown_fields(self):refusal(self,lambda:dispatch({'schema':'mmc.request.t2','operation':'profiles','arguments':{},'approved':True}))

for field in ('transition','subject'):
    for bad in ([],{},None,True,123):
        def test(self,field=field,bad=bad):
            b=bundle();b['assessments'][0][field]=bad;refusal(self,lambda:compile_domain(b))
        setattr(InterfaceTests,'test_typed_'+field+'_'+type(bad).__name__,test)
for name in records():
    def test(self,name=name):
        r=records()[name];ref=profile_reference(name);x=assess_profile(ref,r);self.assertEqual(replay_assessment(ref,r,x)['status'],'MATCH_EXACT_RECOMPUTATION')
    setattr(InterfaceTests,'test_profile_replay_'+name,test)
