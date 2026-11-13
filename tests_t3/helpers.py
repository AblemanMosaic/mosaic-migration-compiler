from pathlib import Path
import tempfile,json,copy
from mosaic_mmc import decode,canonical
from mosaic_mmc_t3 import *
from mosaic_mmc_t3.courts import scope
from mosaic_mmc_t3.statements import backend
ROOT=Path(__file__).resolve().parents[1]
TIME={'now':100,'uncertainty':0}

def keys():
    # PUBLIC FIXTURE scalars. Never production keys.
    ec,*_=backend();return [ec.derive_private_key(i,ec.SECP256R1()) for i in range(1,7)]

def bundle(domain='identity'):
    b=decode((ROOT/f'examples/t2/{domain}.json').read_bytes())
    for o in b['model']['objects']:
        if o['kind']=='Effect':o['attributes']['compensation']='restore-prior-state'
    return b

def policy(b=None):
    b=b or bundle();ks=keys();objs={o['id']:o for o in b['model']['objects']}
    claims=['coverage']+['domain:'+a['id'] for a in b['assessments']]+['retirement:'+a['transition'] for a in b['retirements']]+['fact:'+i for i,o in objs.items() if o['kind']=='Observation']
    return {'schema':'mmc.reader-policy.t3','observers':[{'key':public_hex(ks[0]),'claims':sorted(claims),'subjects':sorted(i for i,o in objs.items() if o['kind'] in ('Actor','Asset','Cohort')),'cohorts':sorted(i for i,o in objs.items() if o['kind']=='Cohort'),'methods':['fixture-observation'],'classes':['COVERAGE','ENFORCEMENT','OBSERVATION'],'authorities':['authority.owner']}],'jurisdictions':[{'id':'authority.owner','keys':[public_hex(ks[1])],'threshold':1},{'id':'security','keys':[public_hex(ks[2])],'threshold':1}],'max_age':30,'max_clock_uncertainty':2,'minimum_sequence':4,'revoked_keys':[],'max_attempts':2}

def statement(plan,mid,transition,kind,payload,key=None,issued=90,expires=120,sequence=4):
    key=key or keys()[0]
    b={'schema':'mmc.statement.t3','kind':kind,'signer':public_hex(key),**scope(plan,mid,transition),'issued_at':issued,'expires_at':expires,'sequence':sequence,'payload':payload}
    return seal(b,key)

def observations(plan,mid='migration.blue',transition='step.prepare'):
    b=plan['body']['bundle'];objs={o['id']:o for o in b['model']['objects']};cohort=objs[transition]['attributes']['cohort'];roster=sorted(objs[cohort]['attributes']['members']);out=[]
    def add(claim,subject,value,members=()):out.append(statement(plan,mid,transition,'observation',{'claim':claim,'subject':subject,'value':copy.deepcopy(value),'coverage':'COMPLETE','members':sorted(members),'method':'fixture-observation','evidence_class':'COVERAGE' if claim=='coverage' else 'OBSERVATION'}))
    add('coverage',cohort,{'members':roster,'complete':True},roster)
    for i,o in objs.items():
        if o['kind']=='Observation':add('fact:'+i,o['attributes']['subject'],True)
    for a in b['assessments']:
        if a['transition']==transition:add('domain:'+a['id'],a['subject'],a['record'])
    for a in b['retirements']:
        if a['transition']==transition:add('retirement:'+transition,cohort,a['record'],roster)
    return out

def approvals(plan,request,allow=True):
    out=[]
    for jurisdiction,key in [('authority.owner',keys()[1]),('security',keys()[2])]:
        out.append(statement(plan,request['scope']['migration'],request['scope']['transition'],'approval',{'request_root':digest('request',request),'context_root':request['context_root'],'jurisdiction':jurisdiction,'decision':'ALLOW' if allow else 'DENY'},key))
    return out

def resign(record,key=None):return seal(copy.deepcopy(record['body']),key or keys()[0])

class Env:
    def __init__(self,root,domain='identity'):
        self.root=Path(root);self.bundle=bundle(domain);self.policy=policy(self.bundle);self.plan=make_plan(self.bundle,self.policy);self.mid='migration.blue'
        self.controller=Controller.create(self.root/'controller.sqlite',self.policy)
        self.store=SimulatedStore.create(self.root/'target.sqlite','sim.main',{x['target']:x['state'] for x in self.bundle['model']['initial_states']},floor=4,revoked=['revoked.key'])
        self.controller.submit(self.mid,self.bundle,expected_plan_root=self.plan['root'])
    def observe(self,step='step.prepare',records=None):
        for r in observations(self.plan,self.mid,step) if records is None else records:self.controller.observe(self.mid,r)
    def prepare(self,step='step.prepare',op='op.1',direction='FORWARD'):
        self.observe(step);return self.controller.prepare(self.mid,step,self.store,TIME,operation_id=op,direction=direction)
    def approve(self,r):return self.controller.approve(r['operation_id'],approvals(self.plan,r),TIME)
    def run(self,step='step.prepare',op='op.1',fault=None):
        r=self.prepare(step,op);self.approve(r);return self.controller.commit(op,self.store,TIME,fault=fault)
