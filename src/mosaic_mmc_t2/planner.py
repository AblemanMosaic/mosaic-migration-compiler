"""Deterministic finite-state witness search. No live observations or effect invocation."""
from collections import deque
from mosaic_mmc.model import validate_model
from .common import admit,unique,Report,require,digest,BOUNDARY,clone


def components(nodes,edges):
    """Exact strongly connected components by finite reachability, at most 16 transitions."""
    nodes=sorted(nodes);reach={n:{n} for n in nodes}
    for a,b in edges:reach[a].add(b)
    for k in nodes:
        for i in nodes:
            if k in reach[i]:reach[i]|=reach[k]
    left=set(nodes);result=[]
    while left:
        n=min(left);c=sorted(i for i in left if i in reach[n] and n in reach[i]);left-=set(c);result.append(c)
    return result


def plan(model,planning):
    m=validate_model(model);r=admit('planning',planning)
    objects={o['id']:o for o in m['objects']};steps={i:o['attributes'] for i,o in objects.items() if o['kind']=='Transition'}
    require(len(steps)<=16,'MMC_T2_PLANNER_TRANSITION_LIMIT')
    facts=unique(r['facts']);labels=[]
    for collection in ('orders','coexistence','exclusions','phases'):labels += [x['id'] for x in r[collection]]
    require(len(labels)==len(set(labels)),'MMC_T2_DUPLICATE_CONSTRAINT')
    unresolved=set()
    def enabled(row):
        cond=row['when']
        if cond is None:return True
        require(cond in facts,'MMC_T2_FACT_REFERENCE',row['id'],cond)
        v=facts[cond]['value']
        if v is None:unresolved.add(cond)
        return v is True
    edges=set();origins={}
    for ident,o in objects.items():
        if o['kind']=='Dependency':
            a=o['attributes'];e=(a['before'],a['after']);edges.add(e);origins.setdefault(e,[]).append(ident)
    for row in r['orders']:
        require(row['before'] in steps and row['after'] in steps,'MMC_T2_ORDER_REFERENCE',row['id'])
        require(row['before']!=row['after'],'MMC_T2_SELF_ORDER',row['id'])
        if enabled(row):
            e=(row['before'],row['after']);edges.add(e);origins.setdefault(e,[]).append(row['id'])
    active=[];availability=set();targets={x['target'] for x in m['initial_states']}
    initial={x['target']:x['state'] for x in m['initial_states']}
    for kind in ('coexistence','exclusions'):
        for row in r[kind]:
            for side in ('left','right'):
                q=row[side];require(q['target'] in objects and objects[q['target']]['kind'] in ('Actor','Asset'),'MMC_T2_STATE_REFERENCE',row['id'])
                require(q['target'] in initial,'MMC_T2_INITIAL_STATE',row['id'],q['target'])
            if enabled(row):
                active.append((kind,row))
                if kind=='coexistence':availability.add((row['left']['target'],row['right']['target']))
    for ident,t in steps.items():
        require({x['target'] for x in t['from_states']}<=targets,'MMC_T2_INITIAL_STATE',ident)
    used=set();actions=[]
    for ph in sorted(r['phases'],key=lambda x:x['id']):
        require(ph['id'] not in steps,'MMC_T2_PHASE_ID_ALIAS',ph['id'])
        members=set(ph['members']);require(members<=set(steps),'MMC_T2_PHASE_REFERENCE',ph['id'])
        require(not members&used,'MMC_T2_PHASE_OVERLAP',ph['id']);used |= members
        require(len({steps[i]['cohort'] for i in members})==1,'MMC_T2_PHASE_COHORT',ph['id'])
        touched=[x['target'] for i in members for x in steps[i]['from_states']]
        require(len(touched)==len(set(touched)),'MMC_T2_PHASE_TARGET_OVERLAP',ph['id'])
        actions.append((ph['id'],tuple(sorted(members)),True))
    actions += [(i,(i,),False) for i in steps if i not in used];actions.sort(key=lambda x:x[0])
    ids=sorted(steps);bits={i:1<<n for n,i in enumerate(ids)};goal=(1<<len(ids))-1
    order_scc=[c for c in components(steps,edges) if len(c)>1]
    coexist_scc=[c for c in components(targets,availability) if len(c)>1]
    diagnostics=[]
    def diag(code,refs,detail):diagnostics.append({'code':code,'source_refs':sorted(refs),'detail':detail,'requirement':'MMC-W04-R03'})
    def constraints(state):
        bad=[]
        for kind,row in active:
            l=state.get(row['left']['target'])==row['left']['state'];rr=state.get(row['right']['target'])==row['right']['state']
            if (kind=='coexistence' and l and not rr) or (kind=='exclusions' and l and rr):bad.append(row['id'])
        return bad
    status=None;witness=[];seen_count=0;initial_bad=constraints(initial)
    internal=[(a,b) for a,b in edges if any(a in ms and b in ms for _,ms,_ in actions)]
    if unresolved:
        status='INDETERMINATE_CONDITIONS';diag('UNKNOWN_CONDITION',unresolved,'No truth value inferred for missing knowledge')
    elif order_scc or internal:
        status='UNSATISFIABLE_FOR_SUPPLIED_MODEL'
        for c in order_scc:diag('STRICT_ORDER_CYCLE',c,'Strict before cannot be satisfied by an atomic phase')
        for a,b in internal:diag('STRICT_ORDER_WITHIN_PHASE',[a,b],'Strict precedence is incompatible with simultaneous action')
    elif initial_bad:
        status='UNSATISFIABLE_FOR_SUPPLIED_MODEL';diag('INITIAL_CONSTRAINT_VIOLATION',initial_bad,'Initial model violates declared constraints')
    else:
        queue=deque([(0,initial,[])]);seen={0};limit_hit=False;rejects=set()
        # For a fixed done-set, each target has a unique reachable state only when its
        # transition path is coherent; retain state in the search key (not just done mask).
        seen={(0,tuple(sorted(initial.items())))}
        while queue:
            done,state,path=queue.popleft()
            if done==goal:witness=path;status='ADMISSIBLE_MODEL_PLAN';break
            for ident,members,atomic in actions:
                mask=sum(bits[i] for i in members)
                if done&mask:continue
                if any(b in members and not(done&bits[a]) for a,b in edges):continue
                if any(state[x['target']]!=x['state'] for i in members for x in steps[i]['from_states']):continue
                nxt=dict(state)
                for i in members:
                    for x in steps[i]['to_states']:nxt[x['target']]=x['state']
                bad=constraints(nxt)
                if bad:rejects.update(bad);continue
                key=(done|mask,tuple(sorted(nxt.items())))
                if key in seen:continue
                if len(seen)>=r['search_limit']:limit_hit=True;continue
                seen.add(key)
                node={'action':ident,'transitions':list(members),'atomicity':'REQUIRES_QUALIFIED_ADAPTER' if atomic else 'SEQUENTIAL_MODEL_STEP','cohort':steps[members[0]]['cohort'],'post_state':[{'target':k,'state':v} for k,v in sorted(nxt.items())]}
                queue.append((done|mask,nxt,path+[node]))
        seen_count=len(seen)
        if status is None:
            status='INDETERMINATE_SEARCH_LIMIT' if limit_hit else 'UNSATISFIABLE_FOR_SUPPLIED_MODEL'
            diag('SEARCH_BUDGET' if limit_hit else 'NO_VALID_SEQUENCE',rejects or set(steps),'Bounded search incomplete' if limit_hit else 'All admitted finite sequences explored')
    body={'schema':'mmc.plan.t2','status':status,'model_root':__import__('mosaic_mmc').digest('canonical-model',m),'planning_root':digest('request',r),'witness':witness,'diagnostics':diagnostics,'order_components':order_scc,'coexistence_components':coexist_scc,'order_edges':[{'before':a,'after':b,'source_refs':sorted(origins[(a,b)])} for a,b in sorted(edges)],'visited_states':seen_count,'search_limit':r['search_limit'],'all_orders_enumerated':False,'selection':'LEXICAL_BFS_WITNESS_NOT_OPTIMALITY','affected_cohorts':sorted({t['cohort'] for t in steps.values()}),**BOUNDARY}
    return {'body':body,'root':digest('plan',body)}
