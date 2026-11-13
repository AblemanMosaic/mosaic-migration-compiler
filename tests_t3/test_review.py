"""Targeted review regressions, platform model and admission boundaries."""
import copy,tempfile,unittest,subprocess,os,sys,sqlite3
from pathlib import Path
from unittest.mock import patch
from mosaic_mmc import MMCError,canonical,decode
from mosaic_mmc_t3 import *
from mosaic_mmc_t3.courts import scope,validate_request
from mosaic_mmc_t3.abi import dispatch
from tests_t3.helpers import *

class ReviewTests(unittest.TestCase):
    def test_stale_newer_does_not_revive_old_positive(self):
        b=bundle();p=policy(b);plan=make_plan(b,p);rr=observations(plan)
        i=next(i for i,r in enumerate(rr) if r['body']['payload']['claim']=='fact:obs.drain');old=copy.deepcopy(rr[i]);old['body'].update(issued_at=70,expires_at=200);rr[i]=resign(old)
        negative=copy.deepcopy(old);negative['body'].update(sequence=5,issued_at=80,expires_at=90);negative['body']['payload']['value']=False;rr.append(resign(negative))
        result=evaluate_evidence(plan,p,'migration.blue','step.prepare',rr,TIME)
        self.assertEqual(result['body']['status'],'INDETERMINATE');self.assertIn('SUPERSEDED_BY_KNOWN_SEQUENCE',{x['reason'] for x in result['body']['quarantine']})
    def test_same_sequence_equivocation_retained(self):
        b=bundle();p=policy(b);plan=make_plan(b,p);rr=observations(plan);r=copy.deepcopy(rr[1]);r['body']['payload']['value']=False;rr.append(resign(r));self.assertEqual(evaluate_evidence(plan,p,'migration.blue','step.prepare',rr,TIME)['body']['status'],'BLOCKED')
    def test_evaluator_bound_to_plan_and_receipt(self):
        from mosaic_mmc_t3.common import realization
        b=bundle();p=policy(b);plan=make_plan(b,p);self.assertEqual(plan['body']['evaluator_root'],realization());result=evaluate_evidence(plan,p,'migration.blue','step.prepare',observations(plan),TIME);self.assertEqual(result['body']['evaluator_root'],realization())
    def test_readonly_abi_refuses_effects(self):
        for op in ('commit','approve','sign','install','fetch','submit','raise-floor'):
            with self.assertRaisesRegex(MMCError,'ABI_OPERATION'):dispatch({'schema':'mmc.request.t3','operation':op,'arguments':{}})
    def test_abi_capabilities_parity(self):
        from mosaic_mmc_t3.abi import OPERATIONS
        self.assertEqual(dispatch({'schema':'mmc.request.t3','operation':'capabilities','arguments':{}})['operations'],sorted(OPERATIONS))
    def test_cli_capabilities(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t3.cli','capabilities'],capture_output=True,timeout=15);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(decode(p.stdout)['profile'],'T3-O1')
    def test_cli_effect_refusal(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t3.cli','request','-'],input=canonical({'schema':'mmc.request.t3','operation':'commit','arguments':{}}),capture_output=True,timeout=15);self.assertEqual(p.returncode,2);self.assertEqual(decode(p.stdout)['effects'],'NOT_EXECUTED')
    def test_cli_duplicate_json(self):
        p=subprocess.run([sys.executable,'-m','mosaic_mmc_t3.cli','request','-'],input=b'{"schema":"mmc.request.t3","schema":"other"}',capture_output=True,timeout=15);self.assertEqual(p.returncode,2)
    def test_cli_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';a.write_text('{}');b=Path(d)/'b';b.symlink_to(a)
            p=subprocess.run([sys.executable,'-m','mosaic_mmc_t3.cli','request',str(b)],capture_output=True,timeout=15);self.assertEqual(p.returncode,2);self.assertEqual(decode(p.stdout)['code'],'MMC_T3_FILE_LINK')
    def test_request_shape_type_refusal(self):
        for x in (None,[],True,{'status':'PASS'}):
            with self.assertRaises(MMCError):validate_request(x)
    def test_policy_substitution_refused(self):
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);r=e.prepare();p=copy.deepcopy(e.policy);p['jurisdictions']=p['jurisdictions'][:1]
            with self.assertRaisesRegex(MMCError,'REQUEST_POLICY'):assess_authority(r,p,approvals(e.plan,r),TIME)
    def test_clock_cannot_regress_after_approval(self):
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);r=e.prepare();e.controller.approve('op.1',approvals(e.plan,r),{'now':105,'uncertainty':0})
            with self.assertRaisesRegex(MMCError,'CLOCK_ROLLBACK'):e.controller.commit('op.1',e.store,TIME)
    def test_unmodeled_effect_descriptor_refused(self):
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);r=e.prepare();r['adapter']['production']=True
            with self.assertRaisesRegex(MMCError,'ADAPTER_PROFILE'):e.store.apply(r)
    def test_actual_multi_target_partial(self):
        with tempfile.TemporaryDirectory() as d:
            b=bundle();b['model']['initial_states'].append({'target':'consumer.main','state':'legacy'})
            for o in b['model']['objects']:
                if o['id']=='step.prepare':o['attributes']['from_states'].append({'target':'consumer.main','state':'legacy'});o['attributes']['to_states'].append({'target':'consumer.main','state':'dual'})
            p=policy(b);plan=make_plan(b,p);c=Controller.create(Path(d)/'c.sqlite',p);target=SimulatedStore.create(Path(d)/'s.sqlite','sim.main',{x['target']:x['state'] for x in b['model']['initial_states']},floor=4,revoked=['revoked.key']);c.submit('migration.blue',b,expected_plan_root=plan['root'])
            for obs in observations(plan):c.observe('migration.blue',obs)
            r=c.prepare('migration.blue','step.prepare',target,TIME,operation_id='partial');c.approve('partial',approvals(plan,r),TIME);result=c.commit('partial',target,TIME,fault='partial')
            self.assertEqual(result['status'],'PARTIAL');self.assertEqual(len(result['changed']),1);self.assertEqual(target.snapshot(['consumer.main','producer.old'])['producer.old']['state'],'legacy');self.assertEqual(c.replay()['projection']['migrations']['migration.blue']['status'],'RECOVERY_REQUIRED')
    def test_other_cohort_unchanged_by_compensation(self):
        with tempfile.TemporaryDirectory() as d:
            blue=bundle();green=decode(canonical(blue).replace(b'cohort.blue',b'cohort.green').replace(b'producer.old',b'producer.green').replace(b'consumer.main',b'consumer.green').replace(b'asset.legacy',b'asset.green'))
            p=policy(blue);pg=policy(green)
            for key in ('subjects','cohorts'):p['observers'][0][key]=sorted(set(p['observers'][0][key])|set(pg['observers'][0][key]))
            plans={x:make_plan(b,p) for x,b in [('blue',blue),('green',green)]};c=Controller.create(Path(d)/'c.sqlite',p);target=SimulatedStore.create(Path(d)/'s.sqlite','sim.main',{x['target']:x['state'] for b in (blue,green) for x in b['model']['initial_states']},floor=4,revoked=['revoked.key'])
            for x,b in [('blue',blue),('green',green)]:
                mid='migration.'+x;plan=plans[x];c.submit(mid,b,expected_plan_root=plan['root'])
                for step in ('step.prepare','step.cutover'):
                    for obs in observations(plan,mid,step):c.observe(mid,obs)
                    r=c.prepare(mid,step,target,TIME,operation_id=x+'.'+step);c.approve(r['operation_id'],approvals(plan,r),TIME);c.commit(r['operation_id'],target,TIME)
            before=target.snapshot(['asset.green','producer.green']);g_before=c.replay()['projection']['migrations']['migration.green']
            r=c.prepare('migration.blue','step.cutover',target,TIME,operation_id='undo.blue',direction='COMPENSATE');c.approve('undo.blue',approvals(plans['blue'],r),TIME);c.commit('undo.blue',target,TIME)
            self.assertEqual(before,target.snapshot(['asset.green','producer.green']));self.assertEqual(g_before,c.replay()['projection']['migrations']['migration.green'])
    def test_authentic_but_false_statement_not_truth(self):
        b=bundle();p=policy(b);plan=make_plan(b,p);result=evaluate_evidence(plan,p,'migration.blue','step.prepare',observations(plan),TIME)
        self.assertEqual(result['body']['coverage_basis'],'RECOGNIZED_TESTIMONY_OVER_DECLARED_ROSTER');self.assertEqual(result['body']['production_authorization'],'NOT_ESTABLISHED')
    def test_producer_evidence_pure_assessment_not_execution(self):
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);e.observe();before=e.store.snapshot(['producer.old']);r=e.controller.assess(e.mid,'step.prepare',TIME);self.assertEqual(r['body']['effects'],'NOT_EXECUTED');self.assertEqual(before,e.store.snapshot(['producer.old']))

class AdditionalReviewTests(unittest.TestCase):
    def test_authority_revocation_string_refused(self):
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);r=e.prepare()
            with self.assertRaises(MMCError):assess_authority(r,e.policy,approvals(e.plan,r),TIME,revoked=public_hex(keys()[1]))
    def test_authority_revocation_boolean_refused(self):
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);r=e.prepare()
            with self.assertRaises(MMCError):assess_authority(r,e.policy,approvals(e.plan,r),TIME,revoked=True)
    def test_self_consistent_malformed_event_typed_refusal(self):
        from mosaic_mmc_t3.storage import Journal
        with tempfile.TemporaryDirectory() as d:
            e=Env(d)
            with e.controller.journal.transaction(True) as con:
                events=e.controller.journal.events(con);Journal.append(con,events,'OUTCOME',{'operation_id':[],'result':None})
            with self.assertRaisesRegex(MMCError,'JOURNAL_PROJECTION'):e.controller.replay()

for field,value in [('issued_at',True),('expires_at',False),('sequence',True),('schema','other'),('kind','execute'),('targets','producer.old')]:
    def test(self,field=field,value=value):
        b=bundle();p=policy(b);r=observations(make_plan(b,p))[0];r['body'][field]=value
        with self.assertRaises(MMCError):verify(r)
    setattr(ReviewTests,'test_statement_type_'+field,test)
