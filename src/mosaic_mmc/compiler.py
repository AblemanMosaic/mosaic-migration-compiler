"""Deterministic non-effectful lowering of the admitted foundation language."""
from __future__ import annotations
import heapq
from .codec import canonical, digest, clone
from .contracts import contract, profile_reference, realization_identity
from .model import validate_model, observation_refs
from .errors import MMCError, require
from ._pins import PROGRAM_ROOT


def constant_value(rule: dict) -> bool|None:
    op=rule['op']
    if op=='literal': return rule['value']
    if op=='eq': return None  # supplied observation values NEVER discharge a runtime fact
    if op=='not':
        val=constant_value(rule['item'])
        return None if val is None else not val
    vals=[constant_value(v) for v in rule['items']]
    if op=='all':
        return False if any(v is False for v in vals) else True if all(v is True for v in vals) else None
    return True if any(v is True for v in vals) else False if all(v is False for v in vals) else None


def _order(objects: dict) -> tuple[list[str],dict[str,set[str]],dict[str,set[str]]]:
    ids=sorted(i for i,o in objects.items() if o['kind']=='Transition')
    predecessors={i:set() for i in ids}; successors={i:set() for i in ids}
    for o in objects.values():
        if o['kind']=='Dependency':
            a=o['attributes']; predecessors[a['after']].add(a['before']);successors[a['before']].add(a['after'])
    remaining={i:len(predecessors[i]) for i in ids}
    ready=[i for i in ids if not remaining[i]];heapq.heapify(ready);ordered=[]
    while ready:
        current=heapq.heappop(ready);ordered.append(current)
        for nxt in sorted(successors[current]):
            remaining[nxt]-=1
            if remaining[nxt]==0:heapq.heappush(ready,nxt)
    require(len(ordered)==len(ids),'MMC_ORDER_CYCLE','$.objects',','.join(i for i in ids if remaining[i]>0))
    ancestors={i:set() for i in ids}
    for current in ordered:
        for pred in predecessors[current]:ancestors[current] |= {pred}|ancestors[pred]
    targets={i:{r['target'] for r in objects[i]['attributes']['from_states']} for i in ids}
    for pos,a in enumerate(ids):
        for b in ids[pos+1:]:
            if targets[a]&targets[b]:
                require(a in ancestors[b] or b in ancestors[a], 'MMC_UNORDERED_TARGET_CHANGES', '$.objects', a+','+b)
    return ordered,predecessors,ancestors


def _guard(ident: str, category: str, sources: list[str], rule: dict|None=None,
           needs: dict|None=None) -> dict:
    v=None if rule is None else constant_value(rule)
    return {'id':ident, 'category':category, 'source_refs':sorted(set(sources)),
            'condition':rule, 'compile_state':('RUNTIME_REQUIRED' if v is None else 'STATIC_TRUE' if v else 'STATIC_FALSE'),
            'evidence_requirements':needs or {}, 'evidence_authentication':'NOT_PERFORMED'}


def compile_model(value: object) -> dict:
    model=validate_model(value)
    objects={o['id']:o for o in model['objects']}
    ordered,preds,_=_order(objects)
    state={r['target']:r['state'] for r in model['initial_states']}
    steps=[];diagnostics=[]
    for ident in ordered:
        t=objects[ident]['attributes'];cohort=objects[t['cohort']]['attributes']
        before={r['target']:r['state'] for r in t['from_states']}
        after={r['target']:r['state'] for r in t['to_states']}
        for target,expected in sorted(before.items()):
            require(target in state,'MMC_INITIAL_STATE_MISSING',ident,target)
            require(state[target]==expected,'MMC_STATE_CHAIN',ident,target)
        state.update(after)
        needs=set(t['requires'])
        effects=[]
        for eid in t['effects']:
            ef=objects[eid]['attributes'];needs.update(ef['requires'])
            effects.append({'id':eid,'source_ref':eid,'descriptor':ef,'binding_status':'UNBOUND','execution':'NOT_IMPLEMENTED'})
        policies=set(t['policies'])|set(cohort['policy_refs'])
        for target in before:
            if objects[target]['kind']=='Asset':policies.update(objects[target]['attributes']['policy_refs'])
        for o in objects.values():
            if o['kind']=='Flow' and o['attributes']['cohort']==t['cohort']:policies.update(o['attributes']['policy_refs'])
        guards=[]
        for oid in sorted(needs):
            a=objects[oid]['attributes']
            req={k:a[k] for k in ('subject','authority','evidence_classes','freshness_seconds','coverage_required')}
            req['observations']=sorted(set(observation_refs(a['rule'])))
            guards.append(_guard(ident+'/obligation/'+oid,a['category'],[ident,oid],a['rule'],req))
        for pid in sorted(policies):
            p=objects[pid]['attributes']
            guards.append(_guard(ident+'/policy/'+pid,'applicable-policy',[ident,pid],p['rule'],
                                 {'jurisdiction':p['jurisdiction'],'observations':sorted(set(observation_refs(p['rule'])))}))
        for category in ['current-authorization','fresh-evidence']:
            guards.append(_guard(ident+'/runtime/'+category,category,[ident,t['cohort']]))
        for ef in effects:
            for category in ['adapter-binding','live-preconditions']:
                guards.append(_guard(ident+'/effect/'+ef['id']+'/'+category,category,[ident,ef['id']],None,
                                     {'target':ef['descriptor']['target'],'authority':ef['descriptor']['authority']}))
        if t['goal']=='RETIRE':
            for category in contract('foundation')['retirement_guard_categories']:
                guards.append(_guard(ident+'/retirement/'+category,category,[ident,t['cohort']],None,
                                     {'scope':t['cohort'],'coverage':'REQUIRES_ACTUAL_T2_T3_EVALUATION'}))
        guards.sort(key=lambda g:g['id'])
        for guard in guards:
            if guard['compile_state']=='STATIC_FALSE':
                diagnostics.append({'code':'STATIC_CONDITION_FALSE','severity':'BLOCKER','transition':ident,
                                    'guard':guard['id'],'source_refs':guard['source_refs']})
        steps.append({'id':ident,'cohort':t['cohort'],'goal':t['goal'],'predecessors':sorted(preds[ident]),
                      'pre_state':t['from_states'],'post_state':t['to_states'],'guards':guards,'effects':effects,
                      'source_refs':sorted({ident,t['cohort']}|needs|policies|set(t['effects'])),
                      'eligibility':'NOT_EVALUATED','effects_status':'NOT_EXECUTED'})
    model_root=digest('canonical-model',model)
    compiler_root=realization_identity()
    ir={'schema':'mmc.ir.t1','program_root':PROGRAM_ROOT,'profile_ref':profile_reference(),
        'compiler_realization':compiler_root,'model_root':model_root,'normalized_model':model,
        'steps':steps,'declared_final_states':[{'target':k,'state':v} for k,v in sorted(state.items())],
        'diagnostics':diagnostics,'authority_effect':'NONE','eligibility':'NOT_EVALUATED',
        'inventory_coverage':'SUPPLIED_DECLARATIONS_ONLY','external_evidence':'NOT_AUTHENTICATED'}
    ir_root=digest('workflow-ir',ir)
    body={'schema':'mmc.compilation-receipt.t1','model_root':model_root,'profile_ref':profile_reference(),
          'program_root':PROGRAM_ROOT,'compiler_realization':compiler_root,'ir_root':ir_root,
          'status':'COMPILED_WITH_STATIC_BLOCKERS' if diagnostics else 'COMPILED_WITH_RUNTIME_OBLIGATIONS',
          'step_count':len(steps),'static_blockers':len(diagnostics),
          'runtime_guards':sum(g['compile_state']=='RUNTIME_REQUIRED' for s in steps for g in s['guards']),
          'eligibility':'NOT_EVALUATED','authority_effect':'NONE','effects':'NOT_EXECUTED','signature':'NOT_SIGNED'}
    result={'schema':'mmc.compilation.t1','ir':ir,'ir_root':ir_root,
            'receipt':{'body':body,'root':digest('compilation-receipt',body)}}
    canonical(result)
    return result


def verify_compilation(model: object, candidate: object, *, expected_model_root: str) -> dict:
    expected=compile_model(model)
    require(type(expected_model_root) is str and expected['ir']['model_root']==expected_model_root,
            'MMC_EXPECTED_MODEL_MISMATCH')
    require(canonical(candidate)==canonical(expected),'MMC_COMPILATION_MISMATCH', '$',
            'Candidate must match actual recompilation, not merely a self-consistent hash')
    return {'schema':'mmc.recompile-verification.t1','status':'MATCH_EXACT_COMPILATION',
            'model_root':expected_model_root,'ir_root':expected['ir_root'],
            'compiler_realization':expected['ir']['compiler_realization'],
            'eligibility':'NOT_EVALUATED','authority_effect':'NONE','effects':'NOT_EXECUTED'}
