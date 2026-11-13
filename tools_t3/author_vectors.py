"""Explicit authoring tool, NEVER called by verification. Preserve frozen predecessor on amendment."""
from pathlib import Path
import sys,copy,tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests_t3.helpers import *
from tools.common import save_json,require
from tools_t3.check_vectors import invoke

def author():
    b=bundle();p=policy(b);plan=make_plan(b,p);records=observations(plan)
    cases=[]
    def add(name,op,args,expected_status=None,refusal=None):
        request={'schema':'mmc.request.t3','operation':op,'arguments':args};expected=invoke(request)
        if refusal:require(expected=={'refusal':refusal},'MMC_T3_VECTOR_AUTHOR_ORACLE',name)
        if expected_status:require(expected['result']['body']['status']==expected_status,'MMC_T3_VECTOR_AUTHOR_ORACLE',name)
        cases.append({'id':name,'request':request,'expected':expected})
    base={'plan':plan,'policy':p,'migration':'migration.blue','transition':'step.prepare','records':records,'time':TIME,'floor':4,'revoked':[]}
    add('capabilities','capabilities',{})
    add('operational-plan','plan',{'bundle':b,'policy':p})
    add('signed-observation','verify-statement',{'record':records[0]})
    add('evidence-match','evidence',base,'EVIDENCE_SATISFIES_SELECTED_POLICY')
    add('missing-evidence','evidence',{**base,'records':[]},'INDETERMINATE')
    add('expired-evidence','evidence',{**base,'time':{'now':120,'uncertainty':0}},'INDETERMINATE')
    add('future-evidence','evidence',{**base,'time':{'now':89,'uncertainty':0}},'INDETERMINATE')
    add('clock-over-policy','evidence',{**base,'time':{'now':100,'uncertainty':3}},'BLOCKED')
    add('clock-crosses-expiry','evidence',{**base,'time':{'now':119,'uncertainty':1}},'INDETERMINATE')
    add('higher-sequence-floor','evidence',{**base,'floor':5},'INDETERMINATE')
    add('revoked-observer','evidence',{**base,'revoked':[public_hex(keys()[0])]},'INDETERMINATE')
    rr=copy.deepcopy(records);rr[0]['body']['payload']['coverage']='PARTIAL';rr[0]=resign(rr[0]);add('partial-coverage','evidence',{**base,'records':rr},'BLOCKED')
    rr=copy.deepcopy(records);i=next(i for i,r in enumerate(rr) if r['body']['payload']['claim']=='fact:obs.drain');rr[i]['body']['payload']['value']=False;rr[i]=resign(rr[i]);add('negative-fact','evidence',{**base,'records':rr},'BLOCKED')
    rr=copy.deepcopy(records);r=copy.deepcopy(rr[i]);r['body']['payload']['value']=False;rr.append(resign(r));add('same-sequence-conflict','evidence',{**base,'records':rr},'BLOCKED')
    rr=copy.deepcopy(records);r=copy.deepcopy(rr[i]);r['body'].update(sequence=5,expires_at=99);r['body']['payload']['value']=False;rr.append(resign(r));add('stale-newer-no-fallback','evidence',{**base,'records':rr},'INDETERMINATE')
    add('duplicate-records','evidence',{**base,'records':records+records},'EVIDENCE_SATISFIES_SELECTED_POLICY')
    r=copy.deepcopy(records[0]);r['signature']='00'*32;r['root']=digest('statement',{k:r[k] for k in ('body','algorithm','signature')});add('invalid-signature','verify-statement',{'record':r},refusal='MMC_T3_SIGNATURE')
    add('effect-not-in-ABI','commit',{},refusal='MMC_T3_ABI_OPERATION')
    with tempfile.TemporaryDirectory() as d:
        e=Env(d);request=e.prepare();aa=approvals(e.plan,request)
        auth={'request':request,'policy':e.policy,'records':aa,'time':TIME,'revoked':[]}
        add('joint-approval','authority',auth,'SCOPED_APPROVALS_SATISFIED')
        add('missing-jurisdiction','authority',{**auth,'records':aa[:1]},'BLOCKED')
        deny=copy.deepcopy(aa[1]);deny['body']['payload']['decision']='DENY';deny=resign(deny,keys()[2]);add('recognized-denial','authority',{**auth,'records':[aa[0],deny]},'BLOCKED')
        add('approval-expiry','authority',{**auth,'time':{'now':120,'uncertainty':0}},'BLOCKED')
    result=evaluate_evidence(**base)
    add('exact-assessment-replay','replay',{**base,'candidate':result})
    fake=copy.deepcopy(result);fake['body']['production_authorization']='GRANTED';fake['root']=digest('assessment',fake['body']);add('rehashed-forged-authority','replay',{**base,'candidate':fake},refusal='MMC_T3_REPLAY_MISMATCH')
    require(len(cases)==24,'MMC_T3_VECTOR_COUNT')
    return {'schema':'mmc.known-answers.t3','claim':'Finite authored oracles, reference-assisted full records; not independent proof','cases':cases}
if __name__=='__main__':
    path=ROOT/'interop/t3-known-answers.json';require(not path.exists(),'MMC_T3_VECTOR_ALREADY_FROZEN');save_json(path,author());print('24 cases frozen')
