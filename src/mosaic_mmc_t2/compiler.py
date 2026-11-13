"""Additive compiler overlay: T1 kernel guards are retained, never discharged by assertions."""
from mosaic_mmc.model import validate_model,closed,observation_refs
from mosaic_mmc.compiler import _guard
from mosaic_mmc.contracts import profile_reference as foundation_reference,realization_identity as foundation_identity
from mosaic_mmc.codec import digest as base_digest
from .common import canonical,clone,require,digest,realization_identity,BOUNDARY
from ._pins import CONTRACT_ROOT
from .evaluation import assess_profile
from .registry import resolve
from .planner import plan
from .lifecycle import assess_routes,assess_retirement,requirements


def _base_guards(objects,ident):
    t=objects[ident]['attributes'];cohort=objects[t['cohort']]['attributes'];needs=set(t['requires']);effects=[]
    for eid in t['effects']:
        ef=objects[eid]['attributes'];needs.update(ef['requires']);effects.append(eid)
    policies=set(t['policies'])|set(cohort['policy_refs'])
    for target in (r['target'] for r in t['from_states']):
        if objects[target]['kind']=='Asset':policies.update(objects[target]['attributes']['policy_refs'])
    for o in objects.values():
        if o['kind']=='Flow' and o['attributes']['cohort']==t['cohort']:policies.update(o['attributes']['policy_refs'])
    guards=[]
    for oid in sorted(needs):
        a=objects[oid]['attributes'];req={k:a[k] for k in ('subject','authority','evidence_classes','freshness_seconds','coverage_required')}
        req['observations']=sorted(set(observation_refs(a['rule'])))
        guards.append(_guard(ident+'/obligation/'+oid,a['category'],[ident,oid],a['rule'],req))
    for pid in sorted(policies):
        p=objects[pid]['attributes'];guards.append(_guard(ident+'/policy/'+pid,'applicable-policy',[ident,pid],p['rule'],{'jurisdiction':p['jurisdiction'],'observations':sorted(set(observation_refs(p['rule'])))}))
    for cat in ('current-authorization','fresh-evidence'):
        guards.append(_guard(ident+'/runtime/'+cat,cat,[ident,t['cohort']]))
    for eid in effects:
        for cat in ('adapter-binding','live-preconditions'):
            ef=objects[eid]['attributes'];guards.append(_guard(ident+'/effect/'+eid+'/'+cat,cat,[ident,eid],needs={'target':ef['target'],'authority':ef['authority']}))
    if t['goal']=='RETIRE':
        from mosaic_mmc.contracts import contract
        for cat in contract('foundation')['retirement_guard_categories']:
            guards.append(_guard(ident+'/retirement/'+cat,cat,[ident,t['cohort']],needs={'scope':t['cohort'],'coverage':'REQUIRES_AUTHENTICATED_T3_EVALUATION'}))
    return sorted(guards,key=lambda x:x['id'])


def compile_domain(bundle):
    canonical(bundle,limit=2*1024*1024)
    closed(bundle,{'schema','model','planning','assessments','routes','retirements'},'$')
    require(bundle['schema']=='mmc.domain-compilation-input.t2','MMC_T2_SCHEMA')
    m=validate_model(bundle['model']);objects={o['id']:o for o in m['objects']};steps={i:o for i,o in objects.items() if o['kind']=='Transition'}
    for key in ('assessments','retirements'):
        require(type(bundle[key]) is list and len(bundle[key])<=128,'MMC_T2_ARRAY',key)
    route_result=assess_routes(m,bundle['routes']);routes={r['cohort']:r for r in bundle['routes']['routes']}
    evaluations=[];seen=set();covered=set()
    for a in bundle['assessments']:
        closed(a,{'id','profile_ref','transition','subject','record'},'assessment')
        require(type(a['id']) is str and a['id'] and a['id'] not in seen,'MMC_T2_DUPLICATE_ASSESSMENT');seen.add(a['id'])
        require(type(a['transition']) is str and a['transition'] in steps,'MMC_T2_TRANSITION_REFERENCE')
        t=steps[a['transition']]['attributes'];cohort=t['cohort'];scope=set(objects[cohort]['attributes']['members'])|{cohort}
        require(type(a['subject']) is str and a['subject'] in scope,'MMC_T2_ASSESSMENT_SCOPE')
        name=resolve(a['profile_ref']);receipt=assess_profile(a['profile_ref'],a['record'])
        if name==m['domain']:covered.add(a['transition'])
        rec=a['record']
        if name=='identity':
            require(rec['requested_subject']==a['subject'] and objects[a['subject']]['kind']=='Actor','MMC_T2_ASSESSMENT_SCOPE')
            require(rec['issuer'] in objects and objects[rec['issuer']]['kind']=='Authority','MMC_T2_ISSUER_SCOPE')
        elif name=='workload':require({w['id'] for w in rec['workers']}==set(requirements(m,cohort)['body']['groups']['workers']),'MMC_T2_ASSESSMENT_SCOPE')
        elif name=='storage':
            require({x['id'] for x in rec['source']['items']}==set(requirements(m,cohort)['body']['groups']['assets']),'MMC_T2_ASSESSMENT_SCOPE')
            require(all(set(x['readers']+x['writers'])<=scope for x in rec['source']['items']),'MMC_T2_ASSESSMENT_SCOPE')
        elif name=='policy':
            require({r['resource'] for r in rec['before']+rec['after']}<=scope,'MMC_T2_ASSESSMENT_SCOPE')
            require(all(r['subject'] in scope and r['authority'] in objects and objects[r['authority']]['kind']=='Authority' for r in rec['before']+rec['after']),'MMC_T2_ASSESSMENT_SCOPE')
        evaluations.append({'id':a['id'],'transition':a['transition'],'subject':a['subject'],'receipt':receipt})
    require(covered==set(steps),'MMC_T2_DOMAIN_COVERAGE')
    retirement=[];done=set()
    for entry in bundle['retirements']:
        closed(entry,{'transition','record'},'retirement')
        ident=entry['transition'];require(type(ident) is str and ident in steps and steps[ident]['attributes']['goal']=='RETIRE' and ident not in done,'MMC_T2_RETIREMENT_TRANSITION');done.add(ident)
        cohort=steps[ident]['attributes']['cohort'];rec=entry['record']
        result=assess_retirement(m,rec)
        require(rec['cohort']==cohort and rec['migration_epoch']==m['revision'] and rec['legacy_version']==routes[cohort]['legacy_version'],'MMC_T2_RETIREMENT_SCOPE')
        retirement.append({'transition':ident,'result':result,'request_root':digest('request',rec)})
    require(done=={i for i,o in steps.items() if o['attributes']['goal']=='RETIRE'},'MMC_T2_RETIREMENT_COVERAGE')
    planned=plan(m,bundle['planning']);lowered=[]
    for ident,tobj in sorted(steps.items()):
        guards=_base_guards(objects,ident)
        for ev in sorted((e for e in evaluations if e['transition']==ident),key=lambda e:e['id']):
            guards.append({'id':ident+'/domain/'+ev['id'],'category':'domain-model-assessment','source_refs':[ident,ev['subject']],'assessment_root':ev['receipt']['root'],'model_status':ev['receipt']['body']['result']['status'],'runtime_state':'AUTHENTICATED_EVIDENCE_STILL_REQUIRED'})
        lowered.append({'id':ident,'cohort':tobj['attributes']['cohort'],'guards':guards,'effect_descriptors':[{'id':eid,'descriptor':objects[eid]['attributes'],'binding':'UNBOUND','execution':'NOT_EXECUTED'} for eid in tobj['attributes']['effects']]})
    blockers=([{'kind':'static-foundation','transition':s['id'],'guard':g['id']} for s in lowered for g in s['guards'] if g.get('compile_state')=='STATIC_FALSE']+
              [{'kind':'domain','assessment':e['id'],'status':e['receipt']['body']['result']['status']} for e in evaluations if e['receipt']['body']['result']['status']!='MATCH_FOR_SUPPLIED_MODEL']+
              [{'kind':'retirement','transition':e['transition'],'status':e['result']['status']} for e in retirement if e['result']['status']!='MODEL_RETIREMENT_CONDITIONS_MET'])
    if planned['body']['status']!='ADMISSIBLE_MODEL_PLAN':blockers.append({'kind':'planning','status':planned['body']['status']})
    body={'schema':'mmc.domain-compilation.t2','contract_root':CONTRACT_ROOT,'foundation_profile':foundation_reference(),'foundation_realization':foundation_identity(),'realization':realization_identity(),'request_root':digest('request',{**bundle,'model':m}),'model_root':base_digest('canonical-model',m),'plan':planned,'domain_assessments':sorted(evaluations,key=lambda e:e['id']),'routes':route_result,'retirements':sorted(retirement,key=lambda e:e['transition']),'instructions':lowered,'blockers':blockers,'status':'COMPILED_WITH_MODEL_BLOCKERS' if blockers else 'COMPILED_WITH_RUNTIME_OBLIGATIONS',**BOUNDARY}
    return {'body':body,'root':digest('compilation',body)}


def verify_compilation(bundle,candidate,*,expected_model_root):
    actual=compile_domain(bundle)
    require(type(expected_model_root) is str and actual['body']['model_root']==expected_model_root,'MMC_T2_EXPECTED_MODEL')
    require(canonical(actual)==canonical(candidate),'MMC_T2_COMPILATION_MISMATCH')
    return {'schema':'mmc.domain-recompile.t2','status':'MATCH_EXACT_DOMAIN_COMPILATION','root':actual['root'],**BOUNDARY}
