"""Synthetic migration inputs. All keys are public fixture scalars, NOT credentials.

Models start from retained T2 examples, then explicate seven actual controller
transitions with explicit Effects. No kernel or predicate is replaced here.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
from mosaic_mmc import canonical, decode
from mosaic_mmc_t3 import public_hex, seal, digest, validate_policy
from mosaic_mmc_t3.statements import backend
from mosaic_mmc_t3.courts import scope

PHASES = [
    ('prepare','PREPARE',[('producer.old','legacy','prepared')]),
    ('canary','OTHER',[('consumer.main','legacy','canary')]),
    ('coexist','OTHER',[('producer.old','prepared','dual'),('consumer.main','canary','dual')]),
    ('fence','OTHER',[('producer.old','dual','fenced')]),
    ('reconcile','OTHER',[('asset.legacy','legacy','new')]),
    ('cutover','CUTOVER',[('consumer.main','dual','new')]),
    ('retire','RETIRE',[('producer.old','fenced','retired')]),
]
STEPS = ['step.'+n for n,_,_ in PHASES]

def keys():
    ec,*_ = backend()
    return [ec.derive_private_key(i,ec.SECP256R1()) for i in range(101,107)]

def provenance(ident):
    return {'source_ref':'fixture:t5/'+ident,'source_digest':hashlib.sha256(ident.encode()).hexdigest(),
            'observed_at':0,'epistemic':'ASSERTED','note':'PUBLIC SYNTHETIC QUALIFICATION INPUT; no production discovery.'}

def obj(ident, kind, attributes):
    return {'id':ident,'kind':kind,'attributes':attributes,'provenance':provenance(ident)}

def make_bundle(domain='identity'):
    b=decode(Path(__file__).with_name('data').joinpath('base-'+domain+'.json').read_bytes())
    objects=[x for x in b['model']['objects'] if x['kind'] not in ('Transition','Dependency','Effect')]
    model=b['model'];model['model_id']='foundry.'+domain
    model['initial_states']=[{'target':i,'state':'legacy'} for i in ('producer.old','consumer.main','asset.legacy')]
    record=deepcopy(b['assessments'][0]['record']);pref=deepcopy(b['assessments'][0]['profile_ref']);subject=b['assessments'][0]['subject']
    if domain=='identity':
        for k in record['keys']:k['not_after']=20000
        for t in record['tokens']:t['expires_at']=20000
        # Exercise a real finite parent/child attenuation relationship, not only a root token.
        parent=deepcopy(record['tokens'][0]);parent['id']='token.parent';parent['subject']='authority.owner';parent['scopes']=['read','write']
        record['tokens'][0]['parent']='token.parent';record['tokens'].append(parent)
    if domain=='storage':
        for side in ('source','destination'):
            for i in record[side]['items']:i['retain_until']=20000
    if domain=='workload':
        record['workers'][0]['checkpoint_version']='checkpoint.v1'
        record['compatible_checkpoints']=[{'checkpoint':'checkpoint.v1','runtime':'legacy'}]
    assessments=[]
    for idx,(name,goal,changes) in enumerate(PHASES):
        tid='step.'+name;effects=[]
        needs=['need.drain','need.data'] if name=='retire' else []
        for target,before,after in changes:
            eid='effect.'+name+'.'+target;effects.append(eid)
            objects.append(obj(eid,'Effect',{'adapter':'simulation.fixture','authority':'authority.owner',
                'compensation':'restore-prior-state','expected_after':after,'expected_before':before,
                'idempotency_scope':'foundry.'+name+'.'+target,'operation':'retire' if goal=='RETIRE' else 'migrate',
                'requires':needs,'target':target}))
        objects.append(obj(tid,'Transition',{'cohort':'cohort.blue','effects':effects,
            'from_states':[{'target':x,'state':p} for x,p,_ in changes],
            'to_states':[{'target':x,'state':q} for x,_,q in changes],
            'goal':goal,'policies':[],'requires':needs}))
        if idx:objects.append(obj('order.'+name,'Dependency',{'before':STEPS[idx-1],'after':tid,'relation':'REQUIRES'}))
        assessments.append({'id':'assessment.'+tid,'profile_ref':deepcopy(pref),'transition':tid,'subject':subject,'record':deepcopy(record)})
    model['objects']=objects;b['assessments']=assessments
    r=b['retirements'][0]['record'];r['approval']['not_after']=20000;r['coverage']['valid_until']=20000
    b['retirements'][0]['transition']='step.retire'
    return b

def rename_cohort(bundle, suffix='green'):
    """Exact token replacement for a disjoint cohort/target migration, not substring rewriting."""
    mapping={'cohort.blue':'cohort.'+suffix,'producer.old':'producer.'+suffix,
             'consumer.main':'consumer.'+suffix,'asset.legacy':'asset.'+suffix,'blue.usecase':suffix+'.usecase'}
    def replace(v):
        if type(v) is str:return mapping.get(v,v)
        if type(v) is list:return [replace(x) for x in v]
        if type(v) is dict:return {k:replace(x) for k,x in v.items()}
        return v
    return replace(bundle)

def reader_policy(bundles):
    ks=keys();claims={'coverage'};subjects=set();cohorts=set()
    for b in bundles:
        objects={o['id']:o for o in b['model']['objects']}
        claims.update('domain:'+a['id'] for a in b['assessments'])
        claims.update('retirement:'+a['transition'] for a in b['retirements'])
        claims.update('fact:'+i for i,o in objects.items() if o['kind']=='Observation')
        subjects.update(i for i,o in objects.items() if o['kind'] in ('Actor','Asset','Cohort'))
        cohorts.update(i for i,o in objects.items() if o['kind']=='Cohort')
    return validate_policy({'schema':'mmc.reader-policy.t3','observers':[{
        'key':public_hex(ks[0]),'claims':sorted(claims),'subjects':sorted(subjects),'cohorts':sorted(cohorts),
        'methods':['fixture-world'],'classes':['COVERAGE','ENFORCEMENT','OBSERVATION'],
        'authorities':['authority.owner']}],
        'jurisdictions':[{'id':'authority.owner','keys':[public_hex(ks[1])],'threshold':1},
                         {'id':'security','keys':[public_hex(ks[2])],'threshold':1}],
        'max_age':30,'max_clock_uncertainty':2,'minimum_sequence':4,'revoked_keys':[],'max_attempts':2})

def signed(plan,mid,step,kind,payload,*,now=100,sequence=4,key=None,expires=None):
    key=key or keys()[0]
    return seal({'schema':'mmc.statement.t3','kind':kind,'signer':public_hex(key),
        **scope(plan,mid,step),'issued_at':now,'expires_at':now+30 if expires is None else expires,
        'sequence':sequence,'payload':deepcopy(payload)},key)

def approve_records(plan, request, now=100, deny=None):
    return [signed(plan,request['scope']['migration'],request['scope']['transition'],'approval',
        {'request_root':digest('request',request),'context_root':request['context_root'],
         'jurisdiction':j,'decision':'DENY' if deny==j else 'ALLOW'},now=now,key=keys()[i])
        for j,i in [('authority.owner',1),('security',2)]]
