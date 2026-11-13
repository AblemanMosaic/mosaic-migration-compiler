"""Finite local migration qualification against the actual T1–T4 realization.

No external services, imported handlers, user keys or production paths are accepted.
Running a case creates temporary controller/target databases and uses PUBLIC fixture
keys. Scenario replay runs in NEW temporary stores; journal replay is separately pure.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib, random, sqlite3, tempfile
from contextlib import closing
from mosaic_mmc import canonical, decode, MMCError
from mosaic_mmc.errors import require
from mosaic_mmc_t3 import Controller, SimulatedStore, make_plan, digest, seal, public_hex
from mosaic_mmc_t3.common import realization as t3_realization
from mosaic_mmc_t3.courts import compile_domain, scope, evaluate_evidence
from mosaic_mmc_t4.host import AgentHost,ReadSession
from mosaic_mmc_t4.collectors import JsonFileCollector
from mosaic_mmc_t4.common import digest as t4_digest
from mosaic_mmc_t4.extensions import job_observer
from mosaic_mmc_t4.work import make_work_order, review_submission
from mosaic_mmc_t4.views import reader_for_sample, journal_view
from ._pins import CONTRACT_ROOT
from .fixtures import make_bundle, reader_policy, rename_cohort, signed, approve_records, keys, STEPS


def hash_value(role,value):
    require(role in ('trace','spec','source','step','replay'), 'MMC_T5_HASH_DOMAIN')
    return hashlib.sha256(b'MMC/T5/'+role.encode()+b'\0'+canonical(value,limit=8*1024*1024)).hexdigest()


def catalogue():
    raw=Path(__file__).with_name('data').joinpath('CONTRACT.json').read_bytes()
    require(hashlib.sha256(b'MMC/T5/CONTRACT\0'+raw).hexdigest()==CONTRACT_ROOT,'MMC_T5_CONTRACT_PIN')
    return decode(raw)['cases']


def realization():
    package=Path(__file__).resolve().parent
    rows=[{'path':p.relative_to(package).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
          for p in sorted(package.rglob('*'),key=lambda item:item.relative_to(package).as_posix()) if p.is_file() and '__pycache__' not in p.parts]
    return hash_value('source',rows)


class Lab:
    """Trusted test caller, not a public controller or a source of production evidence."""
    def __init__(self,directory,domain,seed=0,two_cohorts=False):
        self.path=Path(directory);self.seed=seed;self.random=random.Random(seed)
        self.bundle=make_bundle(domain);self.domain=domain;self.mid='migration.blue'
        self.green=rename_cohort(self.bundle) if two_cohorts else None
        self.policy=reader_policy([self.bundle]+([self.green] if self.green else []))
        self.plan=make_plan(self.bundle,self.policy)
        self.now=100;self.sequence=4;self.trace=[];self.checks=[];self.milestones=[];self.request_serial=0
        self.controller=Controller.create(self.path/'controller.sqlite',self.policy)
        states={x['target']:x['state'] for x in self.bundle['model']['initial_states']}
        if self.green:states.update({x['target']:x['state'] for x in self.green['model']['initial_states']})
        self.targets=sorted(states)
        self.store=SimulatedStore.create(self.path/'target.sqlite','sim.foundry',states,floor=4,revoked=['revoked.key'])
        self.controller.submit(self.mid,self.bundle,expected_plan_root=self.plan['root'])
        if self.green:
            gp=make_plan(self.green,self.policy)
            self.controller.submit('migration.green',self.green,expected_plan_root=gp['root'])
        discovery={'schema':'mmc.fixture-roster.t5','objects':deepcopy(self.bundle['model']['objects']),
                   'coverage':'FINITE_DECLARED_FIXTURE_ROSTER'}
        (self.path/'inventory.json').write_bytes(canonical(discovery))
        self.collector=JsonFileCollector(self.path,'inventory.json','source.inventory')
        self.captured=self.collector.collect(observed_at=self.now)
        self.check('discovery.exact-supplied-source',canonical(self.captured['body']['value'])==canonical(discovery))
        self.note('source-capture',self.captured)
        self.note('discovery',{'coverage':'FINITE_DECLARED_FIXTURE_ROSTER','objects':len(self.bundle['model']['objects']),
                              'initial_target_state':self.store.snapshot(self.targets),'production':False})
        self.mark('DISCOVERED')

    @property
    def time(self):return {'now':self.now,'uncertainty':0}

    def note(self,kind,value):
        require(len(self.trace)<256,'MMC_T5_TRACE_LIMIT')
        previous=self.trace[-1]['root'] if self.trace else '0'*64
        body={'index':len(self.trace),'previous':previous,'kind':kind,'value':deepcopy(value)}
        self.trace.append({**body,'root':hash_value('step',body)})

    def mark(self,name):
        self.milestones.append(name);self.note('milestone',name)

    def check(self,name,condition,details=None):
        require(type(condition) is bool,'MMC_T5_CHECK_TYPE')
        self.checks.append({'id':name,'passed':condition})
        if not condition:raise MMCError('MMC_T5_ASSERTION',name,str(details)[:120])

    def mutation_count(self):
        with closing(sqlite3.connect(self.store.path)) as con:
            return con.execute('SELECT COUNT(*) FROM effects').fetchone()[0]

    def no_effect_refusal(self,label,fn,expected):
        before=self.store.path.read_bytes();n=self.mutation_count()
        try:fn()
        except MMCError as e:
            self.check(label+'.code',e.code in expected,e.code);self.note('refusal',{'id':label,**e.record()})
        else:raise MMCError('MMC_T5_EXPECTED_REFUSAL',label)
        self.check(label+'.no-target-write',self.store.path.read_bytes()==before)
        self.check(label+'.no-effect-record',self.mutation_count()==n)

    def record_set(self,step,*,overrides=None,omit=(),sequence=None,mid=None,plan=None):
        mid=mid or self.mid;plan=plan or self.plan;b=plan['body']['bundle']
        objects={o['id']:o for o in b['model']['objects']};t=objects[step]['attributes'];cohort=t['cohort']
        roster=sorted(objects[cohort]['attributes']['members']);rows=[]
        retired=next((x['record'] for x in b['retirements'] if x['transition']==step),None)
        seq=self.sequence if sequence is None else sequence
        def add(claim,subject,value,members=(),category='OBSERVATION'):
            if claim in omit:return
            value=deepcopy(value)
            if overrides and claim in overrides:value=deepcopy(overrides[claim])
            rows.append(signed(plan,mid,step,'observation',{'claim':claim,'subject':subject,'value':value,
                'coverage':'COMPLETE','members':sorted(members),'method':'fixture-world','evidence_class':category},
                now=self.now,sequence=seq))
        add('coverage',cohort,{'members':roster,'complete':True},roster,'COVERAGE')
        for a in b['assessments']:
            if a['transition']==step:
                rec=deepcopy(a['record'])
                if 'now' in rec:rec['now']=self.now
                add('domain:'+a['id'],a['subject'],rec)
        if retired is not None:
            r=deepcopy(retired);r['now']=self.now;r['coverage'].update(observed_at=self.now,valid_until=self.now+30)
            r['approval'].update(not_before=self.now,not_after=self.now+30)
            pstate=self.controller.replay()['projection'];r['recovery'].update(current_floor=pstate['floor'],proposed_floor=pstate['floor'],current_revoked=pstate['revoked'],proposed_revoked=pstate['revoked'])
            for p in r['producers']:
                state=self.store.snapshot([p['id']])[p['id']]['state'];p['fenced']=state in ('fenced','retired')
            for w in r['workers']:
                state=self.store.snapshot([w['id']])[w['id']]['state'];w['fenced']=state in ('fenced','retired')
            for a in r['assets']:
                state=self.store.snapshot([a['id']])[a['id']]['state'];a['disposition']='MIGRATED' if state=='new' else 'UNRESOLVED'
            for c in r['consumers']:
                state=self.store.snapshot([c['id']])[c['id']]['state'];c['new_ready']=state=='new'
            add('retirement:'+step,cohort,r,roster)
            for i,o in objects.items():
                if o['kind']=='Observation':
                    subject=o['attributes']['subject'];state=self.store.snapshot([subject])[subject]['state']
                    add('fact:'+i,subject,state in ('fenced','retired','new'),'','ENFORCEMENT' if 'drain' in i else 'OBSERVATION')
        self.random.shuffle(rows)
        return rows

    def deliver(self,step,**kwargs):
        rows=self.record_set(step,**kwargs)
        for r in rows:self.controller.observe(kwargs.get('mid') or self.mid,r)
        self.note('delivery',{'transition':step,'roots':sorted(r['root'] for r in rows),'sequence':self.sequence})
        return rows

    def assess(self,step):
        r=self.controller.assess(self.mid,step,self.time)
        self.note('assessment',{'transition':step,'status':r['body']['status'],'root':r['root'],
                              'blockers':[c for c in r['body']['checks'] if c['outcome']!='PASS']})
        return r

    def agent_coverage(self,step):
        rows=self.record_set(step);coverage=next(r for r in rows if r['body']['payload']['claim']=='coverage')
        for r in rows:
            if r is not coverage:self.controller.observe(self.mid,r)
        host=AgentHost(self.controller);s=host.capture(self.mid,step);reader=reader_for_sample(s,self.now)
        resources=[{'id':'source.inventory','root':hashlib.sha256(canonical(self.captured['body']['value'])).hexdigest()}]
        work=make_work_order(s,reader,'coverage',resources)
        session=ReadSession(work,expected_work_root=work['root'],sources={'source.inventory':self.collector},
                            current_snapshot_root=lambda:t4_digest('snapshot',host.capture(self.mid,step)))
        read=session.read('source.inventory',time=self.time)
        self.check('agent.exact-source-read',read['body']['raw_hashes']==self.captured['body']['raw_hashes'])
        submission={'schema':'mmc.agent-submission.t4','work_order_root':work['root'],'record':coverage,
                    'notes':'PUBLIC FIXTURE: one simulated roster. Not autonomous discovery.'}
        before=self.store.path.read_bytes();review=review_submission(s,reader,work,submission,expected_work_root=work['root'])
        self.check('agent.eligible-evidence',review['body']['status']=='ELIGIBLE_FOR_HOST_EVIDENCE_ADMISSION')
        admitted=host.admit(self.mid,step,reader,work,submission,expected_head=s['head'],expected_work_root=work['root'])
        self.check('agent.no-target-effect',before==self.store.path.read_bytes())
        self.note('agent-cycle',{'work_root':work['root'],'review_root':review['root'],'admission':admitted,
            'work_bytes':len(canonical(work)),'snapshot_bytes':len(canonical(s)),
            'independent_agent':'NOT_RUN','human_effort':'NOT_MEASURED'})
        self.mark('AGENT_COVERAGE_ADMITTED')

    def request(self,step,*,direction='FORWARD',mid=None):
        self.request_serial+=1
        r=self.controller.prepare(mid or self.mid,step,self.store,self.time,operation_id='op.'+str(self.request_serial),direction=direction)
        self.note('prepared',{'request_root':digest('request',r),'operation_id':r['operation_id'],'transition':step,'direction':direction})
        return r

    def approve(self,request,plan=None):
        rows=approve_records(plan or self.plan,request,self.now)
        r=self.controller.approve(request['operation_id'],rows,self.time)
        self.check('approval.'+request['operation_id'],r['body']['status']=='SCOPED_APPROVALS_SATISFIED')
        return rows

    def perform(self,step,*,deliver=True,fault=None):
        if deliver:self.deliver(step)
        assessment=self.assess(step)
        self.check('evidence.'+step,assessment['body']['status']=='EVIDENCE_SATISFIES_SELECTED_POLICY',assessment['body']['status'])
        r=self.request(step);self.approve(r)
        result=self.controller.commit(r['operation_id'],self.store,self.time,fault=fault)
        self.note('effect',result)
        if result['status']=='APPLIED':self.note('completed',{'transition':step,'operation_id':r['operation_id']})
        return r,result

    def progress(self,steps=None):
        for step in STEPS if steps is None else steps:
            _,r=self.perform(step);self.check('progress.'+step,r['status']=='APPLIED')
            names={'prepare':'PREPARED','canary':'CANARY','coexist':'COEXISTING','fence':'FENCED','reconcile':'RECONCILED','retire':'RETIRED'}
            if step.split('.')[1] in names:self.mark(names[step.split('.')[1]])

    def legacy_write(self):
        state=self.store.snapshot(['producer.old'])['producer.old']['state']
        observed=job_observer({'schema':'mmc.job-input.t4','jobs':[{'id':'producer.old','version':'legacy',
                              'resumable':True,'fenced':state in ('fenced','retired'),'pending_writes':0}]})
        result='SIMULATED_WRITE_REJECTED_FENCE' if observed['status']=='NONE_IN_SUPPLIED_SNAPSHOT' else 'SIMULATED_LEGACY_WRITE_POSSIBLE'
        self.note('legacy-write-probe',{'producer':'producer.old','state':state,'result':result,'observer':observed})
        return result

    def finish(self,case):
        state=self.controller.replay()['projection'];events=self.controller.journal.export()
        before=self.store.path.read_bytes();r=journal_view(events,digest('policy',self.policy),state['head'])
        self.check('journal.replay-exact',canonical(r['projection'])==canonical(state))
        self.check('journal.no-effect-on-replay',self.store.path.read_bytes()==before)
        self.check('required-milestones',set(case['required_milestones'])<=set(self.milestones),case['required_milestones'])
        self.check('final.legacy-fenced',self.legacy_write()=='SIMULATED_WRITE_REJECTED_FENCE')
        self.check('final.all-primary-transitions',set(STEPS)=={x['transition'] for x in state['migrations'][self.mid]['completed']})
        self.check('bounded.effect-count',self.mutation_count()<=64)
        result={'schema':'mmc.scenario-result.t5','case':case['id'],'scenario':case['scenario'],'domain':case['domain'],
          'seed':self.seed,'contract_root':CONTRACT_ROOT,'foundry_realization':realization(),'native_evaluator':t3_realization(),
          'milestones':self.milestones,'checks':self.checks,'trace':self.trace,'journal':events,'journal_head':state['head'],
          'final_targets':self.store.snapshot(self.targets),'target_effects':self.mutation_count(),
          'primary_transitions_completed':len(state['migrations'][self.mid]['completed']),
          'status':'PASS_SCOPED_SIMULATION','effects':'TEMPORARY_SQLITE_SIMULATION','authority_effect':'NONE',
          'native_pippi':'NOT_BOUND','production_evidence':False,'independent_review':'NOT_PERFORMED',
          'productivity_claim':'NOT_ESTABLISHED','signature':'NOT_SIGNED'}
        return {'body':result,'root':hash_value('trace',result)}


def _retirement_block(l,mutate,label,milestone):
    good=l.record_set('step.retire')
    r=next(x for x in good if x['body']['payload']['claim']=='retirement:step.retire')
    bad=deepcopy(r);mutate(bad['body']['payload']['value'])
    bad=seal(bad['body'],keys()[0])
    for x in good:l.controller.observe(l.mid,bad if x is r else x)
    result=l.assess('step.retire');l.check(label+'.blocked',result['body']['status'] in ('BLOCKED','INDETERMINATE'))
    l.no_effect_refusal(label,lambda:l.request('step.retire'),{'MMC_T3_EVIDENCE_NOT_SATISFIED'})
    l.mark(milestone);l.sequence+=1


def _run(l,name):
    if name=='safe-token':
        l.check('discovery.legacy-flow',l.legacy_write()=='SIMULATED_LEGACY_WRITE_POSSIBLE')
        l.agent_coverage('step.prepare');l.perform('step.prepare',deliver=False);l.mark('PREPARED')
        l.progress(STEPS[1:]);return
    if name=='dormant-worker':
        l.progress(STEPS[:3]);l.check('dormant.writes',l.legacy_write()=='SIMULATED_LEGACY_WRITE_POSSIBLE');l.mark('DORMANT_WRITE_OBSERVED')
        # The real retirement evaluator is evaluated even before planner ordering permits a commit.
        l.deliver('step.retire');l.check('dormant.retirement',l.assess('step.retire')['body']['status']=='BLOCKED')
        l.no_effect_refusal('retire-before-fence',lambda:l.request('step.retire'),{'MMC_T3_TRANSITION_ORDER'})
        l.mark('UNSAFE_RETIREMENT_BLOCKED');l.sequence+=1;l.progress(STEPS[3:4])
        l.check('dormant.fence-now-effective',l.legacy_write()=='SIMULATED_WRITE_REJECTED_FENCE');l.mark('FENCE_PROBE_REFUSED')
        l.progress(STEPS[4:]);return
    if name=='persisted-reader':
        l.progress(STEPS[:-1])
        def wrong(r):r['assets'][0].update(disposition='RETAINED_COMPATIBLE',legacy_reader_available=False)
        _retirement_block(l,wrong,'reader-removal','PERSISTED_READER_BLOCKED')
        l.mark('PERSISTED_DISPOSITION_REPAIRED');l.progress(STEPS[-1:]);return
    if name=='wrong-cohort':
        l.progress(STEPS[:1]);l.deliver('step.canary');r=l.request('step.canary');rows=approve_records(l.plan,r,l.now)
        bad=[]
        for row,key in zip(rows,keys()[1:3]):
            body=deepcopy(row['body']);body['cohort']='cohort.other';bad.append(seal(body,key))
        l.no_effect_refusal('wrong-cohort',lambda:l.controller.approve(r['operation_id'],bad,l.time),{'MMC_T3_APPROVAL_NOT_SATISFIED'})
        l.mark('WRONG_COHORT_REFUSED');l.approve(r);l.controller.commit(r['operation_id'],l.store,l.time);l.mark('CORRECT_APPROVAL_ACCEPTED');l.progress(STEPS[2:]);return
    if name=='late-revocation':
        l.deliver('step.prepare');r=l.request('step.prepare');l.approve(r)
        goodroot=l.plan['root'];old=l.controller.assess(l.mid,'step.prepare',l.time)
        withheld=l.record_set('step.prepare',sequence=5)
        target=next(x for x in withheld if x['body']['payload']['claim'].startswith('domain:'))
        body=deepcopy(target['body']);body['payload']['value']['keys'][0]['revoked_at']=99
        negative=seal(body,keys()[0])
        l.check('withheld.view-unchanged',l.controller.assess(l.mid,'step.prepare',l.time)==old);l.mark('WITHHELD_NOT_KNOWN')
        l.now=131;l.check('stale.blocks',l.assess('step.prepare')['body']['status']=='INDETERMINATE')
        l.no_effect_refusal('stale-commit',lambda:l.controller.commit(r['operation_id'],l.store,l.time),{'MMC_T3_REQUEST_EXPIRED'})
        l.mark('STALE_BLOCKED');l.controller.observe(l.mid,negative)
        # A fresh negative remains a blocker, not merely an expired record.
        l.sequence=6;body['issued_at']=l.now;body['expires_at']=l.now+30;body['sequence']=6
        l.controller.observe(l.mid,seal(body,keys()[0]));l.deliver('step.prepare',omit=['domain:assessment.step.prepare'])
        l.check('delivered.revocation-blocks',l.assess('step.prepare')['body']['status']=='BLOCKED');l.mark('DELIVERED_REVOCATION_BLOCKED')
        l.check('revocation.object-unchanged',l.plan['root']==goodroot)
        revised=deepcopy(l.bundle);revised['model']['revision']=2;revised['retirements'][0]['record']['migration_epoch']=2
        revised['retirements'][0]['record']['approval']['migration_epoch']=2
        for a in revised['assessments']:
            rec=a['record'];oldkey=rec['keys'][0];oldkey['revoked_at']=99;oldkey['successor']='key.replacement'
            new=deepcopy(oldkey);new.update(id='key.replacement',revoked_at=None,successor=None);rec['keys'].append(new)
            rec['accepted_keys']=['key.replacement']
            for tok in rec['tokens']:tok['key']='key.replacement'
        l.bundle=revised;l.plan=make_plan(revised,l.policy)
        l.controller.revise(l.mid,revised,expected_plan_root=l.plan['root'],expected_head=l.controller.replay()['projection']['head'])
        l.mark('REPLACEMENT_PLAN_ACCEPTED');l.progress();return
    if name=='lost-ack':
        l.progress(STEPS[:5]);req,res=l.perform('step.cutover',fault='lost_ack')
        l.check('lost-ack.unknown',res['status']=='UNKNOWN');l.mark('UNKNOWN_OUTCOME');n=l.mutation_count()
        l.controller=Controller(l.path/'controller.sqlite',expected_policy_root=digest('policy',l.policy))
        l.mark('RESTARTED');l.no_effect_refusal('lost-ack.no-blind-retry',lambda:l.controller.commit(req['operation_id'],l.store,l.time),{'MMC_T3_RECONCILE_REQUIRED'})
        repaired=l.controller.reconcile(req['operation_id'],l.store)
        l.check('lost-ack.applied',repaired['status']=='APPLIED');l.check('lost-ack.once',n==l.mutation_count())
        l.controller.commit(req['operation_id'],l.store,l.time);l.check('lost-ack.idempotent',n==l.mutation_count());l.mark('RECONCILED_ONCE')
        l.progress(STEPS[-1:]);return
    if name=='targeted-rollback':
        gp=make_plan(l.green,l.policy);gmid='migration.green'
        l.deliver('step.prepare',mid=gmid,plan=gp);gr=l.request('step.prepare',mid=gmid);l.approve(gr,gp)
        l.controller.commit(gr['operation_id'],l.store,l.time)
        green_ids=[x['target'] for x in l.green['model']['initial_states']];before=l.store.snapshot(sorted(green_ids))
        l.progress(STEPS[:2]);l.controller.raise_floor(5,['revoked.key']);l.store.raise_security(['consumer.main'],5,['revoked.key'])
        l.sequence=5;l.deliver('step.canary');r=l.request('step.canary',direction='COMPENSATE');l.approve(r)
        l.controller.commit(r['operation_id'],l.store,l.time);l.mark('SELECTED_COMPENSATION_APPLIED')
        l.check('compensate.other-cohort',before==l.store.snapshot(sorted(green_ids)));l.mark('OTHER_COHORT_UNCHANGED')
        v=l.store.snapshot(['consumer.main'])['consumer.main'];l.check('compensate.floor',v['floor']==5 and 'revoked.key' in v['revoked']);l.mark('SECURITY_FLOOR_RETAINED')
        l.progress(STEPS[1:]);return
    if name=='storage-migration':
        rec=deepcopy(l.bundle['assessments'][0]['record']);rec['destination']['items'][0]['digest']='0'*64
        l.deliver('step.prepare',overrides={'domain:assessment.step.prepare':rec})
        l.check('inventory.bad',l.assess('step.prepare')['body']['status']=='BLOCKED')
        l.no_effect_refusal('storage.bad-inventory',lambda:l.request('step.prepare'),{'MMC_T3_EVIDENCE_NOT_SATISFIED'})
        l.mark('BAD_INVENTORY_BLOCKED');l.sequence+=1;l.mark('STORAGE_REPAIRED');l.progress();return
    if name=='workload-migration':
        rec=deepcopy(l.bundle['assessments'][0]['record']);rec['workers'][0].update(checkpoint_version='checkpoint.unknown',pending_writes=2,fenced=False)
        l.deliver('step.prepare',overrides={'domain:assessment.step.prepare':rec})
        l.check('workload.bad',l.assess('step.prepare')['body']['status']=='BLOCKED')
        l.no_effect_refusal('workload.bad-checkpoint',lambda:l.request('step.prepare'),{'MMC_T3_EVIDENCE_NOT_SATISFIED'})
        l.mark('BAD_WORKLOAD_BLOCKED');l.sequence+=1;l.mark('WORKLOAD_REPAIRED');l.progress();return
    if name=='policy-migration':
        rec=deepcopy(l.bundle['assessments'][0]['record']);rec['consented_purposes']=[]
        l.deliver('step.prepare',overrides={'domain:assessment.step.prepare':rec})
        l.check('policy.no-consent',l.assess('step.prepare')['body']['status']=='BLOCKED')
        l.no_effect_refusal('policy.no-consent',lambda:l.request('step.prepare'),{'MMC_T3_EVIDENCE_NOT_SATISFIED'})
        l.mark('POLICY_INCOMPATIBILITY_BLOCKED')
        revised=deepcopy(l.bundle);revised['model']['revision']=2;revised['retirements'][0]['record']['migration_epoch']=2;revised['retirements'][0]['record']['approval']['migration_epoch']=2
        from mosaic_mmc_t2.profiles import policy as assess_policy
        for a in revised['assessments']:
            rec=a['record'];rec['after'][0]['minimum_retention']=50
        refused=compile_domain(revised);l.check('policy.unaccepted-widening',refused['body']['status']=='COMPILED_WITH_MODEL_BLOCKERS')
        for a in revised['assessments']:
            r=assess_policy(a['record']);a['record']['accepted_change_roots']=[x['root'] for x in r['widenings']]
        l.bundle=revised;l.plan=make_plan(revised,l.policy)
        l.controller.revise(l.mid,revised,expected_plan_root=l.plan['root'],expected_head=l.controller.replay()['projection']['head'])
        l.mark('POLICY_CHANGE_ACCEPTED');l.sequence+=1;l.progress();return
    raise MMCError('MMC_T5_UNKNOWN_SCENARIO')


def run_scenario(name, *, seed=0):
    require(type(name) is str,'MMC_T5_SCENARIO_TYPE')
    require(type(seed) is int and 0<=seed<=31,'MMC_T5_SEED_LIMIT')
    cases={x['scenario']:x for x in catalogue()};require(name in cases,'MMC_T5_UNKNOWN_SCENARIO')
    case=cases[name]
    with tempfile.TemporaryDirectory(prefix='mmc-t5-') as tmp:
        lab=Lab(tmp,case['domain'],seed,two_cohorts=name=='targeted-rollback')
        _run(lab,name)
        return lab.finish(case)


def replay_scenario(name, candidate, *, seed=0):
    """Recompute in fresh simulation stores. Does not reuse/mutate producer databases."""
    canonical(candidate,limit=8*1024*1024)
    actual=run_scenario(name,seed=seed)
    require(canonical(actual,limit=8*1024*1024)==canonical(candidate,limit=8*1024*1024),'MMC_T5_REPLAY_MISMATCH')
    return {'schema':'mmc.scenario-replay.t5','status':'MATCH_EXACT_FRESH_SIMULATION','root':actual['root'],
            'effects':'NEW_TEMPORARY_SIMULATION_ONLY','production_effects':'NONE','authority_effect':'NONE'}


def _inspect_result(candidate, *, expected_root):
    """Integrity + recorded-journal check only. Full simulation replay is separate.

    A pin obtained from the untrusted candidate does not authenticate its producer.
    This operation does not establish that the recorded execution actually occurred.
    """
    canonical(candidate,limit=8*1024*1024)
    require(type(candidate) is dict and set(candidate)=={'body','root'},'MMC_T5_RESULT_FIELDS')
    require(type(expected_root) is str and len(expected_root)==64 and candidate['root']==expected_root,
            'MMC_T5_RESULT_PIN')
    b=candidate['body'];expected={'schema','case','scenario','domain','seed','contract_root','foundry_realization','native_evaluator',
        'milestones','checks','trace','journal','journal_head','final_targets','target_effects','primary_transitions_completed',
        'status','effects','authority_effect','native_pippi','production_evidence','independent_review','productivity_claim','signature'}
    require(type(b) is dict and set(b)==expected,'MMC_T5_RESULT_FIELDS')
    require(hash_value('trace',b)==candidate['root'],'MMC_T5_RESULT_ROOT')
    require(b['schema']=='mmc.scenario-result.t5' and b['contract_root']==CONTRACT_ROOT and
            b['foundry_realization']==realization() and b['native_evaluator']==t3_realization(),'MMC_T5_RESULT_PROFILE')
    cases={c['scenario']:c for c in catalogue()};require(type(b['scenario']) is str and b['scenario'] in cases,'MMC_T5_UNKNOWN_SCENARIO')
    case=cases[b['scenario']];require(b['case']==case['id'] and b['domain']==case['domain'],'MMC_T5_CASE_SCOPE')
    require(type(b['seed']) is int and 0<=b['seed']<=31,'MMC_T5_SEED_LIMIT')
    require(type(b['target_effects']) is int and 7<=b['target_effects']<=64 and
            type(b['primary_transitions_completed']) is int and b['primary_transitions_completed']==7,'MMC_T5_COUNT_TYPE')
    require(b['status']=='PASS_SCOPED_SIMULATION' and b['effects']=='TEMPORARY_SQLITE_SIMULATION'
            and b['authority_effect']=='NONE' and b['production_evidence'] is False
            and b['native_pippi']=='NOT_BOUND' and b['independent_review']=='NOT_PERFORMED'
            and b['productivity_claim']=='NOT_ESTABLISHED' and b['signature']=='NOT_SIGNED','MMC_T5_CLAIM_CEILING')
    require(type(b['checks']) is list and 1<=len(b['checks'])<=256,'MMC_T5_CHECK_LIMIT')
    for c in b['checks']:
        require(type(c) is dict and set(c)=={'id','passed'} and type(c['id']) is str and c['passed'] is True,'MMC_T5_CHECK_RECORD')
    require(type(b['trace']) is list and 1<=len(b['trace'])<=256,'MMC_T5_TRACE_LIMIT')
    require(type(b['milestones']) is list and all(type(x) is str for x in b['milestones']),'MMC_T5_MILESTONE_TYPE')
    previous='0'*64;milestones=[]
    for i,t in enumerate(b['trace']):
        require(type(t) is dict and set(t)=={'index','previous','kind','value','root'},'MMC_T5_TRACE_SHAPE')
        require(type(t['kind']) is str,'MMC_T5_TRACE_KIND')
        require(type(t['index']) is int and t['index']==i and t['previous']==previous,'MMC_T5_TRACE_CHAIN')
        require(t['root']==hash_value('step',{k:t[k] for k in ('index','previous','kind','value')}),'MMC_T5_TRACE_ROOT')
        if t['kind']=='milestone':milestones.append(t['value'])
        previous=t['root']
    require(canonical(milestones)==canonical(b['milestones']) and set(case['required_milestones'])<=set(milestones),'MMC_T5_MILESTONES')
    require(type(b['journal']) is list and len(b['journal'])>0,'MMC_T5_JOURNAL')
    p=b['journal'][0]['payload']['policy']
    j=journal_view(b['journal'],digest('policy',p),b['journal_head'])
    completed=j['projection']['migrations']['migration.blue']['completed']
    require(len(completed)==7 and {r['transition'] for r in completed}==set(STEPS),'MMC_T5_COMPLETE_PATH')
    require(type(b['final_targets']) is dict and b['final_targets']['producer.old']['state']=='retired'
            and b['final_targets']['consumer.main']['state']=='new'
            and b['final_targets']['asset.legacy']['state']=='new','MMC_T5_FINAL_STATE')
    return {'schema':'mmc.scenario-inspection.t5','status':'PIN_AND_RECORDED_JOURNAL_MATCH','root':expected_root,
            'scenario_execution_replayed':False,'actual_execution_authenticated':False,'effects':'NOT_EXECUTED','authority_effect':'NONE'}


def inspect_result(candidate, *, expected_root):
    """Bounded untrusted-record admission; integrity inspection is not execution proof."""
    try:
        return _inspect_result(candidate, expected_root=expected_root)
    except MMCError:
        raise
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise MMCError('MMC_T5_RESULT_STRUCTURE', '$', type(exc).__name__) from exc
