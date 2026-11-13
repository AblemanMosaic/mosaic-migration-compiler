"""Durable operational spine. Host-selected policies; only local simulated effects."""
from __future__ import annotations
from .common import *
from .statements import validate_policy,verify
from .courts import compile_domain,make_plan,validate_plan,scope,evaluate_evidence,assess_authority,validate_request,validate_adapter_descriptor,adapter_model_kind
from .storage import Journal,admit_adapter,LostAcknowledgment,CrashInjected

LIVE={'PREPARED','APPROVED','DISPATCHED','UNKNOWN','NOT_APPLIED','RECOVERY_REQUIRED'}
CAPACITY_CODES={'MMC_NODE_LIMIT','MMC_BYTE_LIMIT','MMC_T3_JOURNAL_LIMIT'}

def _expected_post_state(request):
    return {target:{**value,'version':request['pre_state'][target]['version']+1}
            for target,value in request['post_state'].items()}

def _effect_result(request,status):
    """Construct the largest closed result shape needed by capacity reservations."""
    require(status in ('APPLIED','PARTIAL'),'MMC_T3_OUTCOME')
    return {'schema':'x'*160,'operation_id':request['operation_id'],
            'request_root':digest('request',request),'status':status,
            'changed':request['scope']['targets'],'post_state':_expected_post_state(request),
            'effects':'x'*160,'authority_effect':'NONE'}

def validate_outcome(request,result):
    """Check adapter testimony before admitting it to the durable journal.

    A buggy host adapter must leave an uncertain, reconcilable operation rather
    than poison the entire journal with an unreplayable success assertion.
    """
    require(type(result) is dict,'MMC_T3_OUTCOME')
    require(result.get('request_root')==digest('request',request),'MMC_T3_OUTCOME_REQUEST')
    status=result.get('status')
    require(status in ('APPLIED','PARTIAL','UNKNOWN','NOT_APPLIED'),'MMC_T3_OUTCOME')
    common={'status','request_root'}
    if status in ('APPLIED','PARTIAL'):
        required=common|{'schema','operation_id','changed','post_state','effects','authority_effect'}
        require(set(result)==required,'MMC_T3_OUTCOME_FIELDS')
        token(result['schema']);token(result['effects'])
        require(result['authority_effect']=='NONE','MMC_T3_OUTCOME_AUTHORITY')
        strings(result['changed'],64)
        require(set(result['changed'])<=set(request['scope']['targets']),'MMC_T3_POSTCONDITION')
        expected=_expected_post_state(request)
        require(type(result['post_state']) is dict and set(result['post_state'])==set(expected),
                'MMC_T3_POSTCONDITION')
        for target,value in result['post_state'].items():
            require(canonical(value)==canonical(expected[target] if target in result['changed']
                                                else request['pre_state'][target]),
                    'MMC_T3_POSTCONDITION')
    elif status=='UNKNOWN':
        required=common|{'reason','effects'};optional={'refusal_code'}
        require(required<=set(result)<=required|optional,'MMC_T3_OUTCOME_FIELDS')
        token(result['reason']);token(result['effects'])
        if 'refusal_code' in result:token(result['refusal_code'])
    else:
        require(set(result)==common|{'effects'},'MMC_T3_OUTCOME_FIELDS')
        token(result['effects'])
    if 'operation_id' in result:
        require(result['operation_id']==request['operation_id'],'MMC_T3_OUTCOME_REQUEST')
    if status=='APPLIED':
        expected=_expected_post_state(request)
        require(canonical(result.get('post_state'))==canonical(expected) and
                result.get('changed')==request['scope']['targets'],'MMC_T3_POSTCONDITION')
    canonical(result)
    return clone(result)

def validate_planned_request(m,r):
    p=m['plan'];b=p['body']['bundle'];objects={x['id']:x for x in b['model']['objects']}
    sc=scope(p,r['scope']['migration'],r['scope']['transition'])
    require(canonical(r['scope'])==canonical(sc),'MMC_T3_REQUEST_SCOPE')
    t=objects[sc['transition']]['attributes'];before={x['target']:x['state'] for x in t['from_states']};after={x['target']:x['state'] for x in t['to_states']}
    c=compile_domain(b);w=c['body']['plan']['body']['witness']
    require(w and all(len(x['transitions'])==1 for x in w),'MMC_T3_ATOMIC_PHASE_NOT_BOUND')
    completed={x['transition'] for x in m['completed']}
    if r['direction']=='FORWARD':
        remaining=[x['transitions'][0] for x in w if x['transitions'][0] not in completed]
        require(remaining and remaining[0]==sc['transition'],'MMC_T3_TRANSITION_ORDER')
    else:
        done=[x for x in m['completed'] if objects[x['transition']]['attributes']['cohort']==sc['cohort']]
        require(done and done[-1]['transition']==sc['transition'] and done[-1]['operation_id']==r['compensates'],'MMC_T3_COMPENSATION_SCOPE')
        require(t['effects'] and all(objects[e]['attributes']['compensation']=='restore-prior-state' for e in t['effects']),'MMC_T3_COMPENSATION_NOT_DECLARED')
        before,after=after,before
    require({k:v['state'] for k,v in r['pre_state'].items()}==before and {k:v['state'] for k,v in r['post_state'].items()}==after,'MMC_T3_REQUEST_MODEL_STATES')
    for effect in t['effects']:
        require(objects[effect]['attributes']['adapter']==adapter_model_kind(r['adapter']),
                'MMC_T3_ADAPTER_UNSUPPORTED')
    for target,v in r['post_state'].items():
        require(v['floor']>=r['pre_state'][target]['floor'] and set(r['pre_state'][target]['revoked'])<=set(v['revoked']),'MMC_T3_SECURITY_FLOOR')


def _project(events):
    """Rebuild state from admitted journal records; never consult an adapter."""
    require(type(events) is list and 0<len(events)<=4096,'MMC_T3_JOURNAL_LIMIT')
    p=validate_policy(events[0]['payload']['policy'])
    s={'policy':p,'floor':p['minimum_sequence'],'revoked':list(p['revoked_keys']),'migrations':{},'operations':{},'head':None,'clock_floor':0}
    for e in events:
        k=e['type'];a=e['payload'];s['head']={'sequence':e['sequence'],'root':e['root']}
        if k=='GENESIS':require(e['sequence']==1,'MMC_T3_JOURNAL_ORDER');continue
        if k=='SUBMITTED':
            closed(a,{'migration','plan'});mid=token(a['migration']);require(mid not in s['migrations'] and len(s['migrations'])<64,'MMC_T3_MIGRATION_EXISTS');validate_plan(a['plan'],p)
            s['migrations'][mid]={'plan':a['plan'],'observations':[],'completed':[],'pending':None,'status':'ACTIVE'}
        elif k=='FLOOR_RAISED':
            closed(a,{'floor','revoked'});integer(a['floor']);strings(a['revoked'],128)
            require(a['floor']>=s['floor'] and set(s['revoked'])<=set(a['revoked']),'MMC_T3_SECURITY_FLOOR')
            s['floor']=a['floor'];s['revoked']=a['revoked']
        elif k in ('REVISED','OBSERVED','PAUSED','RESUMED'):
            require(a.get('migration') in s['migrations'],'MMC_T3_MIGRATION_MISSING');m=s['migrations'][a['migration']]
            if k=='REVISED':
                closed(a,{'migration','plan'});require(m['pending'] is None,'MMC_T3_ACTIVE_EFFECT');validate_plan(a['plan'],p)
                require(a['plan']['root']!=m['plan']['root'],'MMC_T3_UNCHANGED_PLAN');m.update(plan=a['plan'],observations=[],completed=[],status='ACTIVE')
            elif k=='OBSERVED':
                closed(a,{'migration','record'});b=verify(a['record']);require(b['migration']==a['migration'] and b['kind']=='observation','MMC_T3_OBSERVATION_SCOPE')
                if a['record']['root'] not in {x['root'] for x in m['observations']}:m['observations'].append(a['record'])
                require(len(m['observations'])<=256,'MMC_T3_EVIDENCE_LIMIT')
            else:
                closed(a,{'migration'});require(m['pending'] is None,'MMC_T3_ACTIVE_EFFECT')
                require(m['status']==('ACTIVE' if k=='PAUSED' else 'PAUSED'),'MMC_T3_LIFECYCLE')
                m['status']='PAUSED' if k=='PAUSED' else 'ACTIVE'
        elif k=='PREPARED':
            closed(a,{'migration','request'});r=validate_request(a['request']);mid=a['migration'];m=s['migrations'][mid]
            require(r['prepared_at']>=s['clock_floor'],'MMC_T3_CLOCK_ROLLBACK');s['clock_floor']=r['prepared_at']
            require(m['pending'] is None and m['status']=='ACTIVE','MMC_T3_ACTIVE_EFFECT');validate_planned_request(m,r);op=r['operation_id']
            require(op not in s['operations'] and r['scope']['migration']==mid and r['scope']['plan_root']==m['plan']['root'],'MMC_T3_REQUEST_SCOPE')
            s['operations'][op]={'request':r,'status':'PREPARED','approvals':[],'attempts':0,'result':None};m['pending']=op
        elif k in ('APPROVED','DISPATCHED','OUTCOME','CANCELLED'):
            require(a.get('operation_id') in s['operations'],'MMC_T3_OPERATION_MISSING');o=s['operations'][a['operation_id']];r=o['request'];m=s['migrations'][r['scope']['migration']]
            if k=='APPROVED':
                closed(a,{'operation_id','records','time'});require(o['status']=='PREPARED','MMC_T3_APPROVAL_STATE')
                require(a['time']['now']>=s['clock_floor'],'MMC_T3_CLOCK_ROLLBACK');s['clock_floor']=a['time']['now']
                report=assess_authority(r,p,a['records'],a['time'],revoked=s['revoked'])
                require(report['body']['status']=='SCOPED_APPROVALS_SATISFIED','MMC_T3_APPROVAL_NOT_SATISFIED');o.update(status='APPROVED',approvals=a['records'])
            elif k=='DISPATCHED':
                closed(a,{'operation_id','time'});clock(a['time']);require(a['time']['now']>=s['clock_floor'],'MMC_T3_CLOCK_ROLLBACK');s['clock_floor']=a['time']['now']
                require(o['status'] in ('APPROVED','NOT_APPLIED') and o['attempts']<r['max_attempts'],'MMC_T3_RETRY_LIMIT')
                assessment=evaluate_evidence(m['plan'],p,r['scope']['migration'],r['scope']['transition'],m['observations'],a['time'],floor=s['floor'],revoked=s['revoked'])
                require(assessment['body']['status']=='EVIDENCE_SATISFIES_SELECTED_POLICY' and assessment['body']['context_root']==r['context_root'],'MMC_T3_JOURNAL_EVIDENCE')
                require(assess_authority(r,p,o['approvals'],a['time'],revoked=s['revoked'])['body']['status']=='SCOPED_APPROVALS_SATISFIED','MMC_T3_JOURNAL_AUTHORITY')
                require(a['time']['now']+a['time']['uncertainty']<r['expires_at'],'MMC_T3_REQUEST_EXPIRED')
                o.update(status='DISPATCHED',attempts=o['attempts']+1)
            elif k=='CANCELLED':
                closed(a,{'operation_id','reason'});token(a['reason'])
                require(o['status'] in ('PREPARED','APPROVED','NOT_APPLIED'),'MMC_T3_CANCELLATION_STATE');o['status']='CANCELLED';m['pending']=None
            else:
                closed(a,{'operation_id','result'});res=a['result'];require(o['status'] in ('DISPATCHED','UNKNOWN','RECOVERY_REQUIRED','NOT_APPLIED'),'MMC_T3_OUTCOME_STATE')
                validate_outcome(r,res)
                status=res['status']
                o['result']=res
                if status=='APPLIED':
                    expected={t:{**v,'version':r['pre_state'][t]['version']+1} for t,v in r['post_state'].items()}
                    require(canonical(res['post_state'])==canonical(expected) and res['changed']==r['scope']['targets'],'MMC_T3_POSTCONDITION')
                    o['status']='APPLIED';m['pending']=None
                    if r['direction']=='FORWARD':m['completed'].append({'transition':r['scope']['transition'],'operation_id':r['operation_id']})
                    else:m['completed']=[x for x in m['completed'] if x['operation_id']!=r['compensates']]
                    m['status']='ACTIVE'
                elif status=='PARTIAL':o['status']='RECOVERY_REQUIRED';m['status']='RECOVERY_REQUIRED'
                else:o['status']=status
        else:raise MMCError('MMC_T3_EVENT_UNSUPPORTED',detail=k)
    canonical(s)
    return s

from functools import lru_cache
@lru_cache(maxsize=16)
def _project_bytes(raw,evaluator_root):
    return canonical(_project(decode(raw,limit=8*1024*1024)))

def project(events):
    # Exact immutable event bytes + evaluator identity; never cache live target state.
    return decode(_project_bytes(canonical(events),realization()),limit=8*1024*1024)


class Controller:
    def __init__(self,path,*,expected_policy_root,minimum=None):
        self.journal=Journal(path,expected_policy_root,minimum)
        self.replay()
    @classmethod
    def create(cls,path,policy):
        j=Journal.create(path,policy)
        return cls(path,expected_policy_root=j.policy_root)
    def _load(self,con,expected_head=None):
        events=self.journal.events(con)
        try:s=project(events)
        except MMCError:raise
        except (KeyError,TypeError,AttributeError,IndexError,ValueError) as exc:
            raise MMCError('MMC_T3_JOURNAL_PROJECTION') from exc
        if expected_head is not None:require(canonical(expected_head)==canonical(s['head']),'MMC_T3_CONCURRENT_HEAD')
        return events,s
    @staticmethod
    def _migration(s,mid):
        token(mid);require(mid in s['migrations'],'MMC_T3_MIGRATION_MISSING');return s['migrations'][mid]
    @staticmethod
    def _append(con,events,kind,payload):
        """Admit only a write whose aggregate history remains replayable and recoverable."""
        try:
            result=Journal.append(con,events,kind,payload)
            state=project(events)
            reserved=list(events)
            for operation_id in sorted(state['operations']):
                operation=state['operations'][operation_id]
                status=operation['status']
                if status=='DISPATCHED':
                    partial=_effect_result(operation['request'],'PARTIAL')
                    reserved.append(Journal.event(reserved,'OUTCOME',
                                    {'operation_id':operation_id,'result':partial}))
                    status='RECOVERY_REQUIRED'
                if status in ('UNKNOWN','RECOVERY_REQUIRED'):
                    applied=_effect_result(operation['request'],'APPLIED')
                    reserved.append(Journal.event(reserved,'OUTCOME',
                                    {'operation_id':operation_id,'result':applied}))
            if len(reserved)!=len(events):
                project(reserved)
            return result
        except MMCError as exc:
            if exc.code in CAPACITY_CODES:
                raise MMCError('MMC_T3_JOURNAL_CAPACITY',detail=exc.code) from exc
            raise
    def replay(self):
        with self.journal.transaction() as con:
            events,s=self._load(con)
            return {'schema':'mmc.controller-replay.t3','status':'REPLAYED_LOCAL_JOURNAL','projection':s,'projection_root':digest('ledger',s),'effects':'NOT_EXECUTED',**BOUNDARY}
    def submit(self,migration,bundle,*,expected_plan_root,expected_head=None):
        with self.journal.transaction(True) as con:
            ev,s=self._load(con,expected_head);token(migration);plan=make_plan(bundle,s['policy'])
            require(plan['root']==expected_plan_root,'MMC_T3_EXPECTED_PLAN');require(migration not in s['migrations'],'MMC_T3_MIGRATION_EXISTS')
            require(len(s['migrations'])<64,'MMC_T3_MIGRATION_LIMIT')
            self._append(con,ev,'SUBMITTED',{'migration':migration,'plan':plan})
        return self.replay()
    def observe(self,migration,record):
        b=verify(record)
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);m=self._migration(s,migration)
            require(b['kind']=='observation' and b['migration']==migration and b['plan_root']==m['plan']['root'],'MMC_T3_OBSERVATION_SCOPE')
            if record['root'] in {x['root'] for x in m['observations']}:return {'status':'DUPLICATE_NO_CHANGE','root':record['root'],**BOUNDARY}
            require(len(m['observations'])<256,'MMC_T3_EVIDENCE_LIMIT')
            if m['pending'] and s['operations'][m['pending']]['status'] in ('PREPARED','APPROVED','NOT_APPLIED'):
                self._append(con,ev,'CANCELLED',{'operation_id':m['pending'],'reason':'EVIDENCE_CHANGED'})
            self._append(con,ev,'OBSERVED',{'migration':migration,'record':record})
        return {'status':'SIGNED_STATEMENT_STORED_RECOGNITION_PENDING','root':record['root'],**BOUNDARY}
    def revise(self,migration,bundle,*,expected_plan_root,expected_head):
        with self.journal.transaction(True) as con:
            ev,s=self._load(con,expected_head);m=self._migration(s,migration);p=make_plan(bundle,s['policy']);require(p['root']==expected_plan_root,'MMC_T3_EXPECTED_PLAN')
            if m['pending']:
                o=s['operations'][m['pending']];require(o['status'] in ('PREPARED','APPROVED','NOT_APPLIED'),'MMC_T3_UNRESOLVED_EFFECT')
                self._append(con,ev,'CANCELLED',{'operation_id':m['pending'],'reason':'PLAN_REVISED'})
            require(p['root']!=m['plan']['root'],'MMC_T3_UNCHANGED_PLAN');self._append(con,ev,'REVISED',{'migration':migration,'plan':p})
        return self.replay()
    def raise_floor(self,floor,revoked):
        integer(floor);strings(revoked,128)
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);require(floor>=s['floor'] and set(s['revoked'])<=set(revoked),'MMC_T3_SECURITY_FLOOR')
            for mid,m in s['migrations'].items():
                if m['pending'] and s['operations'][m['pending']]['status'] in ('PREPARED','APPROVED','NOT_APPLIED'):
                    self._append(con,ev,'CANCELLED',{'operation_id':m['pending'],'reason':'SECURITY_CONTEXT_CHANGED'})
            self._append(con,ev,'FLOOR_RAISED',{'floor':floor,'revoked':revoked})
        return self.replay()
    def pause(self,migration):return self._pause(migration,True)
    def resume(self,migration):return self._pause(migration,False)
    def _pause(self,mid,pause):
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);m=self._migration(s,mid)
            if m['pending']:
                require(s['operations'][m['pending']]['status'] in ('PREPARED','APPROVED','NOT_APPLIED'),'MMC_T3_UNRESOLVED_EFFECT')
                self._append(con,ev,'CANCELLED',{'operation_id':m['pending'],'reason':'PAUSED'})
            require(m['status']==('ACTIVE' if pause else 'PAUSED'),'MMC_T3_LIFECYCLE')
            self._append(con,ev,'PAUSED' if pause else 'RESUMED',{'migration':mid})
        return self.replay()
    def assess(self,migration,transition,time):
        with self.journal.transaction() as con:
            ev,s=self._load(con);m=self._migration(s,migration)
            return evaluate_evidence(m['plan'],s['policy'],migration,transition,m['observations'],time,floor=s['floor'],revoked=s['revoked'])
    def _readiness(self,s,mid,transition,adapter,time,direction='FORWARD'):
        admit_adapter(adapter);validate_adapter_descriptor(adapter.descriptor())
        m=self._migration(s,mid);require(m['status']=='ACTIVE','MMC_T3_MIGRATION_NOT_ACTIVE')
        require(time['now']>=s['clock_floor'],'MMC_T3_CLOCK_ROLLBACK')
        p=m['plan'];c=compile_domain(p['body']['bundle'])
        witness=c['body']['plan']['body']['witness'];require(witness and all(len(x['transitions'])==1 for x in witness),'MMC_T3_ATOMIC_PHASE_NOT_BOUND')
        seq=[x['transitions'][0] for x in witness];completed={x['transition'] for x in m['completed']}
        if direction=='FORWARD':
            remaining=[x for x in seq if x not in completed];require(remaining and transition==remaining[0],'MMC_T3_TRANSITION_ORDER')
        else:
            require(transition in completed,'MMC_T3_COMPENSATION_SOURCE')
            # Inverse is supported only for the latest confirmed step of that cohort;
            # any completed graph successor (including another cohort) blocks reversal.
            objs={x['id']:x for x in p['body']['bundle']['model']['objects']};cohort=objs[transition]['attributes']['cohort']
            cohort_done=[x for x in m['completed'] if objs[x['transition']]['attributes']['cohort']==cohort]
            require(cohort_done[-1]['transition']==transition,'MMC_T3_COMPENSATION_DEPENDENCY')
            edges=c['body']['plan']['body']['order_edges'];desc={transition}
            for _ in range(len(seq)):
                desc|={x['after'] for x in edges if x['before'] in desc}
            require(not((desc-{transition})&completed),'MMC_T3_COMPENSATION_DEPENDENCY')
        assessment=evaluate_evidence(p,s['policy'],mid,transition,m['observations'],time,floor=s['floor'],revoked=s['revoked'])
        require(assessment['body']['status']=='EVIDENCE_SATISFIES_SELECTED_POLICY','MMC_T3_EVIDENCE_NOT_SATISFIED')
        return assessment
    def prepare(self,migration,transition,adapter,time,*,operation_id,ttl=30,direction='FORWARD',expected_head=None):
        token(operation_id);integer(ttl,1,3600);clock(time);require(direction in ('FORWARD','COMPENSATE'),'MMC_T3_DIRECTION')
        with self.journal.transaction(True) as con:
            ev,s=self._load(con,expected_head);m=self._migration(s,migration)
            require(m['pending'] is None and operation_id not in s['operations'],'MMC_T3_OPERATION_EXISTS')
            assessment=self._readiness(s,migration,transition,adapter,time,direction)
            p=m['plan'];sc=scope(p,migration,transition);objects={x['id']:x for x in p['body']['bundle']['model']['objects']};t=objects[transition]['attributes']
            for o in s['operations'].values():
                if o['status'] in LIVE and o['request']['adapter']['id']==adapter.identity['id']:
                    require(not(set(o['request']['scope']['targets'])&set(sc['targets'])),'MMC_T3_TARGET_RESERVED')
            pre=adapter.snapshot(sc['targets']);before={x['target']:x['state'] for x in t['from_states']};after={x['target']:x['state'] for x in t['to_states']}
            for eid in t['effects']:
                ef=objects[eid]['attributes'];require(ef['adapter']==adapter.model_adapter==adapter_model_kind(adapter.descriptor()),'MMC_T3_ADAPTER_UNSUPPORTED')
                require(ef['operation'] in objects[ef['authority']]['attributes']['operations'],'MMC_T3_MODEL_AUTHORITY_SCOPE')
                require(ef['expected_before']==before[ef['target']] and ef['expected_after']==after[ef['target']],'MMC_T3_EFFECT_MODEL_MISMATCH')
            compensates=None
            if direction=='COMPENSATE':
                require(t['effects'] and all(objects[x]['attributes']['compensation']=='restore-prior-state' for x in t['effects']),'MMC_T3_COMPENSATION_NOT_DECLARED')
                compensates=next(x['operation_id'] for x in reversed(m['completed']) if x['transition']==transition)
                before,after=after,before
            require({k:v['state'] for k,v in pre.items()}==before,'MMC_T3_LIVE_PRESTATE')
            post={k:{'state':after[k],'floor':max(v['floor'],s['floor']),'revoked':sorted(set(v['revoked'])|set(s['revoked']))} for k,v in pre.items()}
            request={'schema':'mmc.effect-request.t3','operation_id':operation_id,'scope':sc,'context_root':assessment['body']['context_root'],'direction':direction,'compensates':compensates,'adapter':adapter.descriptor(),'pre_state':pre,'post_state':post,'prepared_at':time['now'],'expires_at':time['now']+ttl,'max_attempts':s['policy']['max_attempts']}
            validate_request(request);self._append(con,ev,'PREPARED',{'migration':migration,'request':request})
        return clone(request)
    def approve(self,operation_id,records,time):
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);require(operation_id in s['operations'],'MMC_T3_OPERATION_MISSING');o=s['operations'][operation_id]
            require(o['status']=='PREPARED','MMC_T3_APPROVAL_STATE')
            clock(time);require(time['now']>=s['clock_floor'],'MMC_T3_CLOCK_ROLLBACK')
            report=assess_authority(o['request'],s['policy'],records,time,revoked=s['revoked'])
            require(report['body']['status']=='SCOPED_APPROVALS_SATISFIED','MMC_T3_APPROVAL_NOT_SATISFIED')
            self._append(con,ev,'APPROVED',{'operation_id':operation_id,'records':clone(records),'time':clone(time)})
        return report
    def cancel(self,operation_id):
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);require(operation_id in s['operations'] and s['operations'][operation_id]['status'] in ('PREPARED','APPROVED','NOT_APPLIED'),'MMC_T3_CANCELLATION_STATE')
            self._append(con,ev,'CANCELLED',{'operation_id':operation_id,'reason':'HOST_CANCELLED'})
        return self.replay()
    def _recheck(self,s,o,adapter,time):
        r=o['request'];admit_adapter(adapter);validate_adapter_descriptor(adapter.descriptor())
        require(adapter.descriptor()==r['adapter'] and
                adapter.model_adapter==adapter_model_kind(r['adapter']),
                'MMC_T3_ADAPTER_SUBSTITUTION')
        require(clock(time)[1]<r['expires_at'],'MMC_T3_REQUEST_EXPIRED')
        assessment=self._readiness(s,r['scope']['migration'],r['scope']['transition'],adapter,time,r['direction'])
        require(assessment['body']['context_root']==r['context_root'],'MMC_T3_CONTEXT_CHANGED')
        require(assess_authority(r,s['policy'],o['approvals'],time,revoked=s['revoked'])['body']['status']=='SCOPED_APPROVALS_SATISFIED','MMC_T3_APPROVAL_NOT_SATISFIED')
        require(canonical(adapter.snapshot(r['scope']['targets']))==canonical(r['pre_state']),'MMC_T3_PRECONDITION_CHANGED')
    def commit(self,operation_id,adapter,time,*,fault=None):
        require(fault in (None,'before','lost_ack','crash_after','partial','after_intent'),'MMC_T3_FAULT_MODE')
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);require(operation_id in s['operations'],'MMC_T3_OPERATION_MISSING');o=s['operations'][operation_id]
            if o['status']=='APPLIED':return clone(o['result'])
            require(o['status'] in ('APPROVED','NOT_APPLIED'),'MMC_T3_RECONCILE_REQUIRED')
            require(o['attempts']<o['request']['max_attempts'],'MMC_T3_RETRY_LIMIT');self._recheck(s,o,adapter,time)
            if o['status']=='NOT_APPLIED':require(adapter.lookup(operation_id,digest('request',o['request']))['status']=='ABSENT_FROM_LOCAL_LEDGER','MMC_T3_RECONCILE_REQUIRED')
            self._append(con,ev,'DISPATCHED',{'operation_id':operation_id,'time':clone(time)})
        if fault=='after_intent':raise CrashInjected('Durable intent; no dispatch yet')
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);o=s['operations'][operation_id]
            require(o['status']=='DISPATCHED','MMC_T3_CONCURRENT_DISPATCH')
            # Recheck under controller lock: cooperating observations cannot race this call.
            # External target CAS remains separate and is atomic only in the qualified adapter.
            try:
                self._recheck(s,o,adapter,time)
                result=adapter.apply(o['request'],fault=fault)
                validate_outcome(o['request'],result)
            except Exception as exc:
                result={'status':'UNKNOWN','request_root':digest('request',o['request']),'reason':type(exc).__name__,'effects':'OUTCOME_UNCERTAIN'}
                if isinstance(exc,MMCError):result['refusal_code']=exc.code
            self._append(con,ev,'OUTCOME',{'operation_id':operation_id,'result':result})
        return result
    def reconcile(self,operation_id,adapter):
        admit_adapter(adapter);validate_adapter_descriptor(adapter.descriptor())
        with self.journal.transaction(True) as con:
            ev,s=self._load(con);require(operation_id in s['operations'],'MMC_T3_OPERATION_MISSING');o=s['operations'][operation_id]
            if o['status']=='APPLIED':return clone(o['result'])
            require(o['status'] in ('DISPATCHED','UNKNOWN','RECOVERY_REQUIRED','NOT_APPLIED'),'MMC_T3_RECONCILE_STATE')
            require(adapter.descriptor()==o['request']['adapter'],'MMC_T3_ADAPTER_SUBSTITUTION')
            result=adapter.lookup(operation_id,digest('request',o['request']))
            if result['status']=='ABSENT_FROM_LOCAL_LEDGER':result={'status':'NOT_APPLIED','request_root':digest('request',o['request']),'effects':'NONE_RECORDED_BY_QUALIFIED_LOCAL_ADAPTER'}
            validate_outcome(o['request'],result)
            self._append(con,ev,'OUTCOME',{'operation_id':operation_id,'result':result})
        return result
