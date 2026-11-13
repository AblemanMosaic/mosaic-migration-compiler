"""Model transition and retirement analysis; deliberately not a live controller."""
from mosaic_mmc.model import validate_model
from .common import admit,unique,Report,require,digest,BOUNDARY,conjunction,clone
from .profiles import check_workers

MAIN=['DRAFT','MODELED','COMPILED','READY','CANARY','COEXISTING','DRAINING','FENCED','RECONCILED','RETIRED']
SIDE={'BLOCKED','PAUSED','INCONCLUSIVE'}

def requirements(model,cohort):
    m=validate_model(model);objects={o['id']:o for o in m['objects']}
    require(type(cohort) is str and cohort in objects and objects[cohort]['kind']=='Cohort','MMC_T2_COHORT_REFERENCE')
    members=objects[cohort]['attributes']['members'];groups={'producers':set(),'workers':set(),'consumers':set(),'assets':set()}
    for i in members:
        o=objects[i]
        if o['kind']=='Asset':groups['assets'].add(i)
        else:
            for role,group in [('producer','producers'),('worker','workers'),('consumer','consumers')]:
                if role in o['attributes']['roles']:groups[group].add(i)
    for o in objects.values():
        if o['kind']=='Flow' and o['attributes']['cohort']==cohort and o['attributes']['legacy']:
            a=o['attributes'];groups['assets'].add(a['asset'])
            if objects[a['source']]['kind']=='Actor':groups['producers'].add(a['source'])
            if objects[a['target']]['kind']=='Actor':groups['consumers'].add(a['target'])
    body={'schema':'mmc.retirement-requirements.t2','cohort':cohort,'use_case':objects[cohort]['attributes']['use_case'],'model_root':__import__('mosaic_mmc').digest('canonical-model',m),'groups':{k:sorted(v) for k,v in groups.items()}}
    return {'body':body,'root':digest('retirement-requirements',body)}

def assess_routes(model,record):
    m=validate_model(model);r=admit('routes',record);rows=unique(r['routes'],'cohort');cohorts={o['id'] for o in m['objects'] if o['kind']=='Cohort'}
    require(set(rows)==cohorts,'MMC_T2_ROUTE_COVERAGE');out=Report('cohort-routes')
    for c,x in sorted(rows.items()):
        req=requirements(m,c)['body'];require(x['use_case']==req['use_case'],'MMC_T2_ROUTE_USE_CASE',c)
        require(x['legacy_version']!=x['new_version'],'MMC_T2_VERSION_ALIAS',c)
        for k,ids in req['groups'].items():require(set(x[k])==set(ids),'MMC_T2_ROUTE_MEMBER_SCOPE',c,k)
        out.check('EXACT_COHORT_ROUTE',True,[c],x['active_route'])
    return out.result(routes=clone(r['routes']))

def assess_retirement(model,record):
    m=validate_model(model);r=admit('retirement',record);req=requirements(m,r['cohort']);groups=req['body']['groups'];out=Report('retirement')
    objects={o['id']:o for o in m['objects']};rows={}
    for kind,expected in groups.items():
        rows[kind]=unique(r[kind]);require(set(rows[kind])==set(expected),'MMC_T2_RETIREMENT_COVERAGE',kind)
    for i,p in sorted(rows['producers'].items()):
        # Requirement derived from model cannot be erased by saying legacy_capable=False.
        legacy_flows=[o for o in objects.values() if o['kind']=='Flow' and o['attributes']['cohort']==r['cohort'] and o['attributes']['source']==i and o['attributes']['legacy']]
        declared_legacy=r['legacy_version'] in objects[i]['attributes']['versions'] or bool(legacy_flows)
        out.check('PRODUCER_CAPABILITY_CONSISTENCY',p['legacy_capable'] or not declared_legacy,[i])
        if declared_legacy or p['legacy_capable']:out.check('LEGACY_PRODUCER_FENCED',p['fenced'],[i],'Observed silence is insufficient')
    # Check worker obligations, using supplied version compatibility and explicit snapshot fields.
    for i,w in sorted(rows['workers'].items()):
        declared_resumable=objects[i]['attributes']['resumable']
        latent=w['code_version']==r['legacy_version'] or w['resume_version']==r['legacy_version']
        out.check('NO_PENDING_WRITES',w['pending_writes']==0,[i])
        if latent and (w['can_resume'] or w['can_write'] or declared_resumable):
            disposed=(w['status']=='TERMINATED' and w['disposition']=='TERMINATE' and not w['can_resume'] and not w['can_write'])
            out.check('DORMANT_LEGACY_WORKER',True if disposed else w['fenced'],[i])
        if w['disposition']=='UNRESOLVED':out.check('WORK_DISPOSITION',None,[i])
        if w['disposition']=='DRAIN':out.check('DRAINAGE_DISPOSITION',w['status']=='DRAINED' and not w['can_resume'] and not w['can_write'],[i])
        if w['disposition']=='TERMINATE':out.check('TERMINATION_DISPOSITION',w['status']=='TERMINATED' and not w['can_resume'] and not w['can_write'],[i])
        if w['disposition']=='FENCE':out.check('FENCED_DISPOSITION',w['fenced'],[i])
        if w['disposition']=='UPGRADE':
            # A fence can make a legacy worker safe, but cannot establish that
            # its separately declared upgrade disposition has happened. This
            # input has no target-version field; require elimination of the
            # legacy runtime and resume path, not a fabricated target identity.
            out.check('UPGRADED_DISPOSITION',w['code_version']!=r['legacy_version'] and w['resume_version']!=r['legacy_version'],[i])
        if i in rows['producers']:
            p=rows['producers'][i];out.check('DUPLICATE_ROLE_CONSISTENCY',p['fenced']==w['fenced'] and p['can_resume']==w['can_resume'],[i])
    for i,a in sorted(rows['assets'].items()):
        mode=a['disposition'];out.check('PERSISTED_DISPOSITION',mode!='UNRESOLVED',[i])
        if mode=='RETAINED_COMPATIBLE':out.check('PERSISTED_LEGACY_READER',a['legacy_reader_available'],[i])
        if mode=='ISOLATED':out.check('PERSISTED_ISOLATION',a['writer_fenced'],[i])
        if mode=='DELETED':out.check('PERSISTED_DELETE_HOLD',conjunction([a['retention_satisfied'],not a['hold']]),[i])
        if mode in ('MIGRATED','RETAINED_COMPATIBLE','ISOLATED'):out.check('PERSISTED_RETENTION',a['retention_satisfied'],[i])
    for i,c in sorted(rows['consumers'].items()):
        out.check('REQUIRED_CONSUMER',c['required'],[i],'A required model consumer cannot remove itself from scope')
        out.check('CONSUMER_READY',c['new_ready'],[i])
    cv=r['coverage'];all_ids=set().union(*(set(x) for x in groups.values()))
    require(cv['observed_at']<=cv['valid_until'],'MMC_T2_INTERVAL','coverage')
    out.check('DECLARED_COVERAGE',True if cv['status']=='DECLARED_COMPLETE' and set(cv['subjects'])==all_ids else None,[r['cohort']])
    out.check('COVERAGE_INTERVAL',cv['observed_at']<=r['now']<cv['valid_until'] and r['now']-cv['observed_at']<=r['max_age'],[r['cohort']])
    ap=r['approval'];require(ap['not_before']<ap['not_after'],'MMC_T2_INTERVAL','approval')
    require(ap['authority'] in objects and objects[ap['authority']]['kind']=='Authority','MMC_T2_AUTHORITY_REFERENCE')
    out.check('DECLARED_RETIREMENT_AUTHORITY', 'retire' in objects[ap['authority']]['attributes']['operations'],[ap['authority']])
    out.check('SCOPED_DECLARED_APPROVAL',conjunction([ap['cohort']==r['cohort'],ap['migration_epoch']==r['migration_epoch'],None if ap['status']=='UNKNOWN' else ap['status']=='DECLARED_APPROVED',ap['not_before']<=r['now']<ap['not_after']]),[ap['authority'],r['cohort']])
    rec=r['recovery'];out.check('RECOVERY_FLOOR',rec['proposed_floor']>=rec['current_floor'])
    out.check('REVOCATION_NONREGRESSION',set(rec['current_revoked'])<=set(rec['proposed_revoked']))
    result=out.result(requirements_root=req['root'],cohort=r['cohort'],migration_epoch=r['migration_epoch'],coverage_authentication='NOT_PERFORMED',approval_recognition='NOT_PERFORMED')
    if result['status']=='MATCH_FOR_SUPPLIED_MODEL':result['status']='MODEL_RETIREMENT_CONDITIONS_MET'
    return result

def assess_lifecycle(record):
    r=admit('lifecycle',record);out=Report('lifecycle');cur=r['current'];target=r['requested'];action=r['action'];resume=r['resume_from']
    require((cur in SIDE)==(resume is not None),'MMC_T2_RESUME_CONTEXT')
    require(resume not in ('RETIRED',) if resume else True,'MMC_T2_RESUME_CONTEXT')
    allowed=False;new_resume=None
    if cur!='RETIRED':
        if action=='ADVANCE' and cur in MAIN[:-1]:allowed=target==MAIN[MAIN.index(cur)+1]
        elif action in ('BLOCK','PAUSE','UNCERTAIN') and cur in MAIN[:-1]:
            allowed=target=={'BLOCK':'BLOCKED','PAUSE':'PAUSED','UNCERTAIN':'INCONCLUSIVE'}[action];new_resume=cur
        elif action=='RESUME' and cur in SIDE:allowed=target==resume
        elif action=='COMPENSATE' and cur in set(MAIN[4:-1])|SIDE:allowed=target=='COMPENSATING'
        elif action=='RECOVERY' and cur=='COMPENSATING':allowed=target=='RECOVERY_REQUIRED'
    out.check('ALLOWED_LIFECYCLE_EDGE',allowed,[cur,target])
    out.check('SECURITY_FLOOR',r['proposed_floor']>=r['current_floor'])
    out.check('REVOCATION_NONREGRESSION',set(r['current_revoked'])<=set(r['proposed_revoked']))
    result=out.result(proposed_state={'cohort':r['cohort'],'state':target,'resume_from':new_resume},runtime_guards=['CURRENT_EVIDENCE','CURRENT_AUTHORIZATION','QUALIFIED_ADAPTER']+(['RETIREMENT_ASSESSMENT'] if target=='RETIRED' else []))
    if result['status']!='MATCH_FOR_SUPPLIED_MODEL':result['proposed_state']=None
    return result
