"""Pure recomputation of selected evidence and authority obligations."""
from mosaic_mmc_t2 import compile_domain as _compile_domain, assess_profile, assess_retirement
from mosaic_mmc_t2.common import realization_identity as t2_identity
from mosaic_mmc.contracts import realization_identity as t1_identity
from functools import lru_cache
from mosaic_mmc_t2.lifecycle import requirements
from mosaic_mmc_t2.common import admit
from mosaic_mmc.model import observation_refs
from .common import *
from .statements import validate_policy,verify


@lru_cache(maxsize=32)
def _compiled_bytes(raw,engine):
    # Immutable compile-only reuse, not an eligibility/authority cache.
    return canonical(_compile_domain(decode(raw)))

def compile_domain(bundle):
    return decode(_compiled_bytes(canonical(bundle),(t1_identity(),t2_identity())),limit=8*1024*1024)


def make_plan(bundle,policy):
    p=validate_policy(policy);c=compile_domain(bundle)
    body={'schema':'mmc.operational-plan.t3','contract_root':CONTRACT_ROOT,'evaluator_root':realization(),'bundle':clone(bundle),'compilation_root':c['root'],'model_root':c['body']['model_root'],'policy_root':digest('policy',p)}
    return {'body':body,'root':digest('plan',body)}


def validate_plan(plan,policy):
    closed(plan,{'body','root'})
    closed(plan['body'],{'schema','contract_root','evaluator_root','bundle','compilation_root','model_root','policy_root'})
    require(canonical(make_plan(plan['body']['bundle'],policy))==canonical(plan),'MMC_T3_PLAN_MISMATCH')
    return plan


def scope(plan,migration,transition):
    token(migration);token(transition)
    objects={o['id']:o for o in plan['body']['bundle']['model']['objects']}
    require(transition in objects and objects[transition]['kind']=='Transition','MMC_T3_TRANSITION')
    t=objects[transition]['attributes']
    return {'migration':migration,'plan_root':plan['root'],'policy_root':plan['body']['policy_root'],'transition':transition,'cohort':t['cohort'],'targets':sorted(x['target'] for x in t['from_states'])}


def evidence_context(plan,migration,transition,records,floor,revoked):
    integer(floor);strings(revoked,128)
    require(type(records) is list and len(records)<=256,'MMC_T3_EVIDENCE_LIMIT')
    for r in records:verify(r)
    return digest('context',{'scope':scope(plan,migration,transition),'evaluator_root':realization(),'records':sorted(set(r['root'] for r in records)),'floor':floor,'revoked':revoked})


def fixed_record(name,reference,record):
    require(type(record) is dict and set(record)==set(reference),'MMC_T3_OBSERVATION_SHAPE')
    mutable={'identity':{'keys','now'},'storage':{'destination','dispositions','now'},'policy':{'consented_purposes'},'workload':{'workers'}}[name]
    for k in set(reference)-mutable:
        require(canonical(record[k])==canonical(reference[k]),'MMC_T3_OBSERVATION_REWRITES_REQUIREMENT',k)
    if name=='identity':
        require(type(record['keys']) is list and {k['id'] for k in record['keys']}=={k['id'] for k in reference['keys']},'MMC_T3_KEY_SET')
        old={k['id']:k for k in reference['keys']}
        for k in record['keys']:
            for field in set(old[k['id']])-{'retired_at','revoked_at'}:
                require(k.get(field)==old[k['id']][field],'MMC_T3_KEY_SCOPE')
            for field in ('retired_at','revoked_at'):
                if old[k['id']][field] is not None:require(k.get(field)==old[k['id']][field],'MMC_T3_KEY_ROLLBACK')
    if name=='workload':
        require(type(record['workers']) is list and {w['id'] for w in record['workers']}=={w['id'] for w in reference['workers']},'MMC_T3_WORKER_COVERAGE')
    if name=='storage':
        require(type(record['dispositions']) is list and len(record['dispositions'])==len(reference['dispositions']),'MMC_T3_DISPOSITION_SCOPE')
        old={x['item']:x for x in reference['dispositions']}
        for x in record['dispositions']:
            require(x.get('item') in old,'MMC_T3_DISPOSITION_SCOPE')
            for k in ('mode','destination'):require(x.get(k)==old[x['item']][k],'MMC_T3_DISPOSITION_SCOPE')


def evaluate_evidence(plan,policy,migration,transition,records,time,*,floor=0,revoked=()):
    p=validate_policy(policy);validate_plan(plan,p);revoked=sorted(set(revoked)|set(p['revoked_keys']))
    integer(floor);lo,hi=clock(time);s=scope(plan,migration,transition);bundle=plan['body']['bundle']
    compiled=compile_domain(bundle);objects={o['id']:o for o in bundle['model']['objects']};t=objects[transition]['attributes']
    instruction=next(x for x in compiled['body']['instructions'] if x['id']==transition)
    checks=[];quarantine=[];accepted=[];facts={}
    def check(code,state,refs=()):
        require(type(state) in (bool,type(None)),'MMC_T3_INTERNAL_TRUTH')
        checks.append({'code':code,'outcome':'MISSING' if state is None else 'PASS' if state else 'BLOCK','refs':sorted(set(refs))})
    check('CLOCK_POLICY',time['uncertainty']<=p['max_clock_uncertainty'])
    check('ADMISSIBLE_COMPILED_MODEL',compiled['body']['status']=='COMPILED_WITH_RUNTIME_OBLIGATIONS')
    needed_authorities={g['evidence_requirements']['authority'] for g in instruction['guards'] if 'authority' in g.get('evidence_requirements',{})}
    needed_authorities|={objects[pid]['attributes']['jurisdiction'] for pid in objects[t['cohort']]['attributes']['policy_refs']+t['policies']}
    if t['goal']=='RETIRE':needed_authorities|={x['record']['approval']['authority'] for x in bundle['retirements'] if x['transition']==transition}
    check('MODEL_JURISDICTIONS_BOUND',needed_authorities<={j['id'] for j in p['jurisdictions']})
    require(type(records) is list and len(records)<=256,'MMC_T3_EVIDENCE_LIMIT')
    observers={o['key']:o for o in p['observers']};groups={};seen=set();streams={};admitted=[]
    for raw in records:
        b=verify(raw)
        if raw['root'] in seen:continue
        seen.add(raw['root'])
        reason=None
        if b['kind']!='observation':reason='NOT_OBSERVATION'
        elif any(canonical(b[k])!=canonical(v) for k,v in s.items()):reason='WRONG_SCOPE'
        elif b['signer'] in revoked:reason='REVOKED'
        elif b['signer'] not in observers:reason='UNRECOGNIZED_OBSERVER'
        else:
            o=observers[b['signer']];v=b['payload']
            if not(v['claim'] in o['claims'] and v['subject'] in o['subjects'] and b['cohort'] in o['cohorts'] and v['method'] in o['methods'] and v['evidence_class'] in o['classes']):reason='UNRECOGNIZED_METHOD_OR_SCOPE'
            elif b['sequence']<max(floor,p['minimum_sequence']):reason='BELOW_FLOOR'

        if reason:quarantine.append({'root':raw['root'],'reason':reason});continue
        stream=(b['signer'],b['payload']['claim'],b['payload']['subject'])
        streams[stream]=max(streams.get(stream,0),b['sequence']);admitted.append((b,raw['root'],stream))
    for b,root,stream in admitted:
        if b['sequence']<streams[stream]:quarantine.append({'root':root,'reason':'SUPERSEDED_BY_KNOWN_SEQUENCE'});continue
        if not fresh(b,time,p['max_age']):quarantine.append({'root':root,'reason':'STALE_OR_OUTSIDE_INTERVAL'});continue
        accepted.append(root);groups.setdefault(b['payload']['claim'],[]).append((b,root))
    def obtain(claim,subject,members=None,classes=None,authority=None):
        rows=groups.get(claim,[])
        candidates=[(b,h) for b,h in rows if b['payload']['subject']==subject and (classes is None or b['payload']['evidence_class'] in classes) and (authority is None or authority in observers[b['signer']]['authorities'])]
        for b,h in rows:
            if b['payload']['subject']!=subject:quarantine.append({'root':h,'reason':'WRONG_CLAIM_SUBJECT'})
        if not candidates:check('EVIDENCE:'+claim,None,[subject]);return None
        values={canonical(b['payload']['value']) for b,h in candidates}
        complete=all(b['payload']['coverage']=='COMPLETE' and (members is None or b['payload']['members']==members) for b,h in candidates)
        check('COVERAGE:'+claim,complete,[subject])
        if len(values)!=1:check('CONTRADICTORY:'+claim,False,[subject]);return None
        return clone(candidates[0][0]['payload']['value']) if complete else None
    roster=sorted(set(objects[t['cohort']]['attributes']['members']))
    coverage=obtain('coverage',t['cohort'],roster,classes=['COVERAGE'])
    check('SOURCE_COVERAGE',type(coverage) is dict and canonical(coverage)==canonical({'members':roster,'complete':True}) if coverage is not None else None,[t['cohort']])
    for ob in sorted(set(x for g in instruction['guards'] if g.get('condition') is not None for x in observation_refs(g['condition']))):
        a=objects[ob]['attributes'];obligations=[g['evidence_requirements'] for g in instruction['guards'] if ob in g.get('evidence_requirements',{}).get('observations',[]) and 'evidence_classes' in g['evidence_requirements']]
        v=obtain('fact:'+ob,a['subject'])
        for obligation in obligations:
            qualified=obtain('fact:'+ob,a['subject'],classes=obligation['evidence_classes'],authority=obligation['authority'])
            if qualified is None:v=None
        if v is not None:facts[ob]=v
    def expression(r):
        op=r['op']
        if op=='literal':return r['value']
        if op=='eq':return canonical(facts[r['observation']])==canonical(r['value']) if r['observation'] in facts else None
        if op=='not':
            v=expression(r['item']);return None if v is None else not v
        vals=[expression(x) for x in r['items']]
        if op=='all':return False if False in vals else None if None in vals else True
        return True if True in vals else None if None in vals else False
    for guard in instruction['guards']:
        if guard.get('condition') is not None:
            check('GUARD:'+guard['id'],expression(guard['condition']),guard['source_refs'])
            max_age=guard.get('evidence_requirements',{}).get('freshness_seconds')
            if max_age is not None:
                for ob in observation_refs(guard['condition']):
                    for b,h in groups.get('fact:'+ob,[]):check('OBLIGATION_AGE:'+guard['id'],hi-b['issued_at']<=max_age,[h])
    results=[]
    for a in sorted((x for x in bundle['assessments'] if x['transition']==transition),key=lambda x:x['id']):
        rec=obtain('domain:'+a['id'],a['subject'])
        if rec is not None:
            name=a['profile_ref']['id'].split('.')[-1];rec=admit(name,rec);fixed_record(name,a['record'],rec)
            if 'now' in rec:rec['now']=hi
            result=assess_profile(a['profile_ref'],rec)
            check('DOMAIN:'+a['id'],result['body']['result']['status']=='MATCH_FOR_SUPPLIED_MODEL',[a['id']]);results.append(result)
    retirement=None
    if t['goal']=='RETIRE':
        r=obtain('retirement:'+transition,t['cohort'],roster)
        if r is not None:
            r=admit('retirement',r)
            ref=next(x['record'] for x in bundle['retirements'] if x['transition']==transition)
            for k in ('schema','cohort','migration_epoch','legacy_version','max_age'):
                require(canonical(r.get(k))==canonical(ref[k]),'MMC_T3_RETIREMENT_REQUIREMENT',k)
            r['now']=hi
            check('RETIREMENT_FLOOR',r['recovery']['proposed_floor']>=floor and set(revoked)<=set(r['recovery']['proposed_revoked']))
            retirement=assess_retirement(bundle['model'],r)
            check('RETIREMENT_MODEL',retirement['status']=='MODEL_RETIREMENT_CONDITIONS_MET',[transition])
    status='BLOCKED' if any(x['outcome']=='BLOCK' for x in checks) else 'INDETERMINATE' if any(x['outcome']=='MISSING' for x in checks) else 'EVIDENCE_SATISFIES_SELECTED_POLICY'
    context=evidence_context(plan,migration,transition,records,floor,revoked)
    return receipt({'schema':'mmc.evidence-court.t3','evaluator_root':realization(),'scope':s,'context_root':context,'time':clone(time),'floor':floor,'revoked':revoked,'checks':checks,'quarantine':sorted(quarantine,key=lambda x:(x['root'],x['reason'])),'accepted_statement_roots':sorted(set(accepted)),'domain_results':results,'retirement':retirement,'status':status,'coverage_basis':'RECOGNIZED_TESTIMONY_OVER_DECLARED_ROSTER','discovery_completeness':'NOT_ESTABLISHED','effects':'NOT_EXECUTED',**BOUNDARY})


ADAPTER_PROFILES={
    ('SIMULATED_LOCAL_SQLITE','UPDATE_SIMULATED_ROWS'):'simulation.fixture',
    ('DISPOSABLE_LOCAL_SQLITE','MIGRATE_DISPOSABLE_WORKLOAD'):'disposable.sqlite.v1',
    ('SQLITE_TABLE_MIGRATION','MIGRATE_ENROLLED_SQLITE_TABLES'):'sqlite.table-migration.v1',
}


def validate_adapter_descriptor(adapter):
    closed(adapter,{'schema','id','mode','atomic_preconditions','idempotency','production','max_targets','effect','power_loss_qualification'})
    require(adapter['schema']=='mmc.adapter.t3' and
            (adapter['mode'],adapter['effect']) in ADAPTER_PROFILES and
            adapter['atomic_preconditions'] is True and adapter['production'] is False and
            type(adapter['max_targets']) is int and adapter['max_targets']==64 and
            adapter['idempotency']=='ATOMIC_LOCAL_LEDGER' and
            adapter['power_loss_qualification']=='NOT_PERFORMED',
            'MMC_T3_ADAPTER_PROFILE')
    token(adapter['id'])
    return adapter


def adapter_model_kind(adapter):
    validate_adapter_descriptor(adapter)
    return ADAPTER_PROFILES[(adapter['mode'],adapter['effect'])]


def validate_request(r):
    closed(r,{'schema','operation_id','scope','context_root','direction','compensates','adapter','pre_state','post_state','prepared_at','expires_at','max_attempts'})
    require(r['schema']=='mmc.effect-request.t3','MMC_T3_REQUEST_SCHEMA');token(r['operation_id']);hashhex(r['context_root'])
    closed(r['scope'],{'migration','plan_root','policy_root','transition','cohort','targets'})
    for k in ('migration','transition','cohort'):token(r['scope'][k])
    for k in ('plan_root','policy_root'):hashhex(r['scope'][k])
    strings(r['scope']['targets'],64);require(bool(r['scope']['targets']),'MMC_T3_EMPTY_TARGETS')
    for k in ('prepared_at','expires_at'):integer(r[k])
    require(r['prepared_at']<r['expires_at'],'MMC_T3_REQUEST_INTERVAL');integer(r['max_attempts'],1,3)
    require(r['direction'] in ('FORWARD','COMPENSATE'),'MMC_T3_DIRECTION')
    if r['direction']=='COMPENSATE':token(r['compensates'])
    else:require(r['compensates'] is None,'MMC_T3_COMPENSATION_SCOPE')
    validate_adapter_descriptor(r['adapter'])
    for field in ('pre_state','post_state'):
        require(type(r[field]) is dict and set(r[field])==set(r['scope']['targets']),'MMC_T3_REQUEST_TARGETS')
        for value in r[field].values():
            closed(value,{'state','floor','revoked'}|({'version'} if field=='pre_state' else set()))
            token(value['state']);integer(value['floor']);strings(value['revoked'],128)
            if field=='pre_state':integer(value['version'])
    canonical(r)
    return r


def assess_authority(request,policy,records,time,*,revoked=()):
    p=validate_policy(policy);validate_request(request);lo,hi=clock(time)
    revoked=list(revoked) if type(revoked) is tuple else revoked;strings(revoked,128)
    revoked=set(revoked)|set(p['revoked_keys'])
    require(request['scope']['policy_root']==digest('policy',p),'MMC_T3_REQUEST_POLICY')
    require(type(records) is list and len(records)<=256,'MMC_T3_APPROVAL_LIMIT')
    scope_=request['scope'];allow={j['id']:set() for j in p['jurisdictions']};denied=set();invalid=[]
    roles={j['id']:j for j in p['jurisdictions']}
    for rec in records:
        b=verify(rec);v=b['payload'];reason=None
        if b['kind']!='approval':reason='NOT_APPROVAL'
        elif any(canonical(b[k])!=canonical(x) for k,x in scope_.items()):reason='WRONG_SCOPE'
        elif v['request_root']!=digest('request',request) or v['context_root']!=request['context_root']:reason='WRONG_REQUEST'
        elif b['signer'] in revoked:reason='REVOKED'
        elif v['jurisdiction'] not in roles or b['signer'] not in roles[v['jurisdiction']]['keys']:reason='UNRECOGNIZED_AUTHORITY'
        elif not fresh(b,time,p['max_age']):reason='EXPIRED_OR_STALE'
        if reason:invalid.append({'root':rec['root'],'reason':reason});continue
        if v['decision']=='DENY':denied.add(v['jurisdiction'])
        else:allow[v['jurisdiction']].add(b['signer'])
    checks=[{'jurisdiction':j['id'],'count':len(allow[j['id']]),'threshold':j['threshold'],'denied':j['id'] in denied,'satisfied':len(allow[j['id']])>=j['threshold'] and j['id'] not in denied} for j in p['jurisdictions']]
    ok=all(x['satisfied'] for x in checks) and hi<request['expires_at'] and time['uncertainty']<=p['max_clock_uncertainty']
    return receipt({'schema':'mmc.authority-court.t3','evaluator_root':realization(),'request_root':digest('request',request),'time':clone(time),'status':'SCOPED_APPROVALS_SATISFIED' if ok else 'BLOCKED','jurisdictions':checks,'ineligible':invalid,'effects':'NOT_EXECUTED',**BOUNDARY})


def replay_evidence(plan,policy,migration,transition,records,time,candidate,*,floor=0,revoked=()):
    actual=evaluate_evidence(plan,policy,migration,transition,records,time,floor=floor,revoked=revoked)
    require(canonical(actual)==canonical(candidate),'MMC_T3_REPLAY_MISMATCH')
    return {'status':'MATCH_EXACT_REPLAY','root':actual['root'],'effects':'NOT_EXECUTED',**BOUNDARY}
