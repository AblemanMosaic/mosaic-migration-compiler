"""Finite, non-effectful predicates for four migration domains.
All input is a supplied model, not an authenticated observation or permission.
"""
from .common import admit, unique, Report, require, digest, conjunction

def identity(record):
    r=admit('identity',record); out=Report('identity')
    keys=unique(r['keys']);tokens=unique(r['tokens'])
    require(r['selected_token'] in tokens,'MMC_T2_TOKEN_REFERENCE')
    require(set(r['accepted_keys'])<=set(keys),'MMC_T2_KEY_REFERENCE')
    for k in keys.values():
        require(k['not_before']<k['not_after'],'MMC_T2_INTERVAL',k['id'])
        if k['successor'] is not None:
            require(k['successor'] in keys and keys[k['successor']]['issuer']==k['issuer'],'MMC_T2_SUCCESSOR',k['id'])
        seen=set();cur=k
        while cur is not None:
            require(cur['id'] not in seen,'MMC_T2_KEY_CYCLE');seen.add(cur['id'])
            cur=keys[cur['successor']] if cur['successor'] else None
    for t in tokens.values():
        require(t['key'] in keys and (t['parent'] is None or t['parent'] in tokens),'MMC_T2_TOKEN_REFERENCE',t['id'])
        require(t['issued_at']<t['expires_at'],'MMC_T2_INTERVAL',t['id'])
        seen=set();cur=t
        while cur:
            require(cur['id'] not in seen,'MMC_T2_DELEGATION_CYCLE');seen.add(cur['id'])
            cur=tokens[cur['parent']] if cur['parent'] else None
    selected=tokens[r['selected_token']];chain=[];cur=selected
    while cur:
        chain.append(cur);cur=tokens[cur['parent']] if cur['parent'] else None
    chain.reverse();hist=[]
    out.check('DELEGATION_DEPTH',len(chain)-1<=r['max_delegation_depth'],[t['id'] for t in chain])
    out.check('ROOT_ISSUER',chain[0]['issuer']==r['issuer'],[chain[0]['id']])
    out.check('SUBJECT',selected['subject']==r['requested_subject'],[selected['id']])
    out.check('REQUESTED_SCOPE',set(r['required_scopes'])<=set(selected['scopes']),[selected['id']])
    for i,t in enumerate(chain):
        k=keys[t['key']];at=t['issued_at'];now=r['now']
        historical=(k['issuer']==t['issuer'] and k['not_before']<=at<k['not_after'] and
                    (k['retired_at'] is None or at<k['retired_at']) and
                    (k['revoked_at'] is None or at<k['revoked_at']))
        hist.append({'token':t['id'],'status':'CONSISTENT_AT_ISSUANCE' if historical else 'INCONSISTENT_AT_ISSUANCE'})
        out.check('ISSUANCE_KEY',historical,[t['id'],k['id']])
        out.check('AUDIENCE',t['audience']==r['audience'],[t['id']])
        out.check('CURRENT_TOKEN_INTERVAL',t['issued_at']<=now<t['expires_at'],[t['id']])
        out.check('CURRENT_KEY',k['id'] in r['accepted_keys'] and k['not_before']<=now<k['not_after'] and (k['revoked_at'] is None or now<k['revoked_at']) and (k['retired_at'] is None or now<k['retired_at']),[k['id']])
        if i:
            p=chain[i-1]
            out.check('DELEGATION_ATTENUATION',t['issuer']==p['subject'] and t['audience']==p['audience'] and set(t['scopes'])<=set(p['scopes']) and p['issued_at']<=t['issued_at'] and t['expires_at']<=p['expires_at'],[p['id'],t['id']])
    return out.result(historical=hist,token_signatures='NOT_CHECKED',recognized_authority='NOT_ESTABLISHED')

def storage(record):
    r=admit('storage',record);out=Report('storage')
    source=unique(r['source']['items']);dest=unique(r['destination']['items']);disp=unique(r['dispositions'],'item')
    require(set(source)==set(disp),'MMC_T2_DISPOSITION_COVERAGE')
    for inv in (r['source'],r['destination']):unique(inv['replicas'])
    out.check('SOURCE_CONSISTENCY',r['source']['consistent'])
    out.check('DESTINATION_CONSISTENCY',r['destination']['consistent'])
    out.check('SNAPSHOT_SEQUENCE',r['destination']['sequence']>=r['source']['sequence'])
    reps=r['destination']['replicas'];out.check('REPLICA_MINIMUM',len(reps)>=r['minimum_replicas'])
    for rep in reps:
        out.check('RESIDENCY',rep['location'] in r['allowed_locations'],[rep['id']])
        out.check('CUSTODY',rep['custodian'] in r['allowed_custodians'],[rep['id']])
    used=[]
    for ident,s in sorted(source.items()):
        d=disp[ident];mode=d['mode']
        if mode=='COPY':
            require(d['destination'] is not None,'MMC_T2_DESTINATION_REFERENCE',ident)
            used.append(d['destination']);target=dest.get(d['destination'])
            out.check('PERSISTED_ITEM_PRESENT',target is not None,[ident,d['destination']])
            if target:
                out.check('EXACT_CONTENT_SCHEMA',s['digest']==target['digest'] and s['schema']==target['schema'],[ident,target['id']])
                out.check('READERS_WRITERS_PRESERVED',set(s['readers'])<=set(target['readers']) and set(s['writers'])<=set(target['writers']),[ident])
                out.check('RETENTION_HOLD',target['retain_until']>=s['retain_until'] and (not s['hold'] or target['hold']),[ident])
                out.check('PURPOSES',set(s['purposes'])|set(r['required_purposes'])<=set(target['purposes']),[ident])
        else:
            require(d['destination'] is None,'MMC_T2_DESTINATION_REFERENCE',ident)
            if mode=='DELETE':out.check('DELETION_ALLOWED',r['now']>=s['retain_until'] and not s['hold'],[ident])
            elif mode=='RETAIN':out.check('LEGACY_READER',d['legacy_reader_available'],[ident])
            elif mode=='ISOLATE':out.check('ISOLATION_FENCE',d['writer_fenced'],[ident])
    require(len(used)==len(set(used)),'MMC_T2_DESTINATION_ALIAS')
    if not r['allow_extra_destination']:out.check('DESTINATION_CLOSURE',set(dest)==set(used))
    return out.result(payload_integrity='INVENTORY_DIGEST_COMPARISON_ONLY',replica_independence='NOT_ESTABLISHED')

def _effective(rules):
    require(len({__import__('mosaic_mmc').canonical(r) for r in rules})==len(rules),'MMC_T2_DUPLICATE_RULE')
    result={};denied=set()
    for r in rules:
        k=tuple(r[n] for n in ('subject','action','resource','purpose'))
        if r['effect']=='DENY':denied.add(k);continue
        old=result.get(k,{'consent_required':False,'minimum_retention':0,'authorities':set()})
        old['consent_required'] |= r['consent_required'];old['minimum_retention']=max(old['minimum_retention'],r['minimum_retention']);old['authorities'].add(r['authority']);result[k]=old
    return {k:{**v,'authorities':sorted(v['authorities'])} for k,v in result.items() if k not in denied}

def policy(record):
    r=admit('policy',record);out=Report('policy');before=_effective(r['before']);after=_effective(r['after']);changes=[]
    for k,new in sorted(after.items()):
        old=before.get(k)
        widening=(old is None or (old['consent_required'] and not new['consent_required']) or new['minimum_retention']<old['minimum_retention'] or new['authorities']!=old['authorities'])
        if widening:
            body={'key':list(k),'before':old,'after':new};root=digest('policy-change',body)
            changes.append({'root':root,'body':body})
            out.check('WIDENING_REQUIRES_AUTHORIZATION',root in r['accepted_change_roots'],list(k),'Accepted root is only a supplied-model disposition; current authority remains unchecked')
        out.check('PURPOSE_CONSENT',None if r['consented_purposes'] is None else k[3] in r['consented_purposes'],list(k))
    require(set(r['accepted_change_roots'])<={c['root'] for c in changes},'MMC_T2_CHANGE_SCOPE')
    out.check('REQUIRED_PURPOSES',set(r['required_purposes'])<={k[3] for k in after})
    return out.result(widenings=changes,removed_permissions=[list(k) for k in sorted(set(before)-set(after))],authorization='CURRENT_SCOPED_APPROVAL_REQUIRED')

def check_workers(r, out):
    workers=unique(r['workers']);pairs={(p['checkpoint'],p['runtime']) for p in r['compatible_checkpoints']}
    for ident,w in sorted(workers.items()):
        legacy=w['code_version'] in r['legacy_versions'] or w['resume_version'] in r['legacy_versions']
        latent=legacy and (w['can_write'] or w['can_resume'])
        if latent:out.check('LEGACY_WRITE_POTENTIAL',w['fenced'],[ident],'Suspension or silence is not a fence')
        out.check('OUTSTANDING_WRITES',w['pending_writes']==0,[ident])
        if w['checkpoint_version'] is not None and w['resume_version'] is not None:
            out.check('CHECKPOINT_COMPATIBILITY',(w['checkpoint_version'],w['resume_version']) in pairs,[ident])
        if w['disposition']=='TERMINATE':out.check('TERMINATED_DISPOSITION',w['status']=='TERMINATED' and not w['can_resume'] and not w['can_write'],[ident])
        elif w['disposition']=='DRAIN':out.check('DRAINED_DISPOSITION',w['status']=='DRAINED' and not w['can_resume'] and not w['can_write'] and w['pending_writes']==0,[ident])
        elif w['disposition']=='FENCE':out.check('FENCED_DISPOSITION',w['fenced'],[ident])
        elif w['disposition']=='UPGRADE':out.check('UPGRADED_DISPOSITION',w['code_version']==r['target_version'] and w['resume_version'] in (None,r['target_version']),[ident])
        elif w['disposition']=='UNRESOLVED':out.check('WORK_DISPOSITION',None,[ident])
    return workers

def workload(record):
    r=admit('workload',record);out=Report('workload')
    require(r['target_version'] not in r['legacy_versions'],'MMC_T2_VERSION_ALIAS')
    check_workers(r,out)
    return out.result(exhaustive_worker_discovery='NOT_ESTABLISHED')
