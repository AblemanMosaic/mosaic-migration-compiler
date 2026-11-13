"""Additional operational challenge cases against the same full seven-step model."""
from pathlib import Path
from copy import deepcopy
import tempfile,unittest,sqlite3,shutil
from unittest.mock import patch
from mosaic_mmc import MMCError,canonical
from mosaic_mmc_t3 import Controller,digest,seal
from mosaic_mmc_t3.storage import CrashInjected
from mosaic_mmc_t5.foundry import Lab
from mosaic_mmc_t5.fixtures import approve_records,keys,STEPS

class FaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lab=Lab(self.tmp.name,'identity')
    def test_partial_coverage_is_not_no_activity(self):
        l=self.lab;rows=l.record_set('step.prepare')
        for r in rows:
            if r['body']['payload']['claim']=='coverage':r['body']['payload']['coverage']='PARTIAL';r=seal(r['body'],keys()[0])
            l.controller.observe(l.mid,r)
        self.assertNotEqual(l.assess('step.prepare')['body']['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY')
        l.no_effect_refusal('coverage-partial',lambda:l.request('step.prepare'),{'MMC_T3_EVIDENCE_NOT_SATISFIED'})
    def test_partition_expiry_then_delivery_allows_progress(self):
        l=self.lab;l.deliver('step.prepare');self.assertEqual(l.assess('step.prepare')['body']['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY')
        l.now=131;l.no_effect_refusal('partition',lambda:l.request('step.prepare'),{'MMC_T3_EVIDENCE_NOT_SATISFIED'})
        l.sequence+=1;l.deliver('step.prepare');r=l.request('step.prepare');l.approve(r)
        self.assertEqual(l.controller.commit(r['operation_id'],l.store,l.time)['status'],'APPLIED')
    def test_latest_expired_negative_never_revives_old_positive(self):
        l=self.lab
        rows=l.record_set('step.prepare');negative=deepcopy(next(r for r in rows if r['body']['payload']['claim']=='coverage'))
        negative['body']['sequence']=5;negative['body']['payload']['value']['complete']=False;negative['body']['expires_at']=101
        for r in rows:l.controller.observe(l.mid,r)
        l.controller.observe(l.mid,seal(negative['body'],keys()[0]));l.now=102
        self.assertEqual(l.assess('step.prepare')['body']['status'],'INDETERMINATE')
    def test_equal_sequence_conflicting_observations(self):
        l=self.lab;rows=l.deliver('step.prepare');r=deepcopy(next(r for r in rows if r['body']['payload']['claim']=='coverage'))
        r['body']['payload']['value']['complete']=False;l.controller.observe(l.mid,seal(r['body'],keys()[0]))
        self.assertEqual(l.assess('step.prepare')['body']['status'],'BLOCKED')
    def test_duplicate_positive_cannot_outvote_negative(self):
        l=self.lab;rows=l.deliver('step.prepare')
        for _ in range(5):
            for r in rows:l.controller.observe(l.mid,r)
        r=deepcopy(next(r for r in rows if r['body']['payload']['claim']=='coverage'));r['body']['payload']['value']['complete']=False
        l.controller.observe(l.mid,seal(r['body'],keys()[0]));self.assertEqual(l.assess('step.prepare')['body']['status'],'BLOCKED')
    def test_wrong_plan_observer_does_not_satisfy_missing_claim(self):
        l=self.lab;rows=l.record_set('step.prepare')
        for r in rows:
            r['body']['plan_root']='f'*64
            with self.assertRaisesRegex(MMCError,'OBSERVATION_SCOPE'):l.controller.observe(l.mid,seal(r['body'],keys()[0]))
        self.assertEqual(l.assess('step.prepare')['body']['status'],'INDETERMINATE')
    def test_revoked_observer_cannot_supply_newer_positive(self):
        l=self.lab
        from mosaic_mmc_t3 import public_hex
        l.controller.raise_floor(5,[public_hex(keys()[0])]);l.sequence=5;l.deliver('step.prepare')
        self.assertEqual(l.assess('step.prepare')['body']['status'],'INDETERMINATE')
    def test_wrong_target_signature_refused(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare');rows=approve_records(l.plan,r)
        for i,x in enumerate(rows):x['body']['targets']=['asset.legacy'];rows[i]=seal(x['body'],keys()[i+1])
        l.no_effect_refusal('wrong-target',lambda:l.controller.approve(r['operation_id'],rows,l.time),{'MMC_T3_APPROVAL_NOT_SATISFIED'})
    def test_joint_jurisdiction_missing(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare')
        l.no_effect_refusal('missing-security',lambda:l.controller.approve(r['operation_id'],approve_records(l.plan,r)[:1],l.time),{'MMC_T3_APPROVAL_NOT_SATISFIED'})
    def test_recognized_denial_not_masked(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare')
        records=approve_records(l.plan,r)+approve_records(l.plan,r,deny='security')
        l.no_effect_refusal('denial',lambda:l.controller.approve(r['operation_id'],records,l.time),{'MMC_T3_APPROVAL_NOT_SATISFIED'})
    def test_clock_uncertainty_cannot_cross_expiry(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare');l.approve(r)
        l.no_effect_refusal('expiry-uncertainty',lambda:l.controller.commit(r['operation_id'],l.store,{'now':129,'uncertainty':2}),{'MMC_T3_REQUEST_EXPIRED'})
    def test_floor_change_invalidates_approval(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare');l.approve(r);l.controller.raise_floor(5,[])
        l.no_effect_refusal('floor-changed',lambda:l.controller.commit(r['operation_id'],l.store,l.time),{'MMC_T3_RECONCILE_REQUIRED'})
    def test_pause_invalidates_approval(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare');l.approve(r);l.controller.pause(l.mid);l.controller.resume(l.mid)
        l.no_effect_refusal('paused',lambda:l.controller.commit(r['operation_id'],l.store,l.time),{'MMC_T3_RECONCILE_REQUIRED'})
    def test_replay_journal_never_calls_adapter(self):
        l=self.lab;l.perform('step.prepare')
        with patch.object(type(l.store),'apply',side_effect=AssertionError('effect')):
            state=l.controller.replay()['projection'];self.assertEqual(len(state['migrations'][l.mid]['completed']),1)
    def test_crash_after_intent_reconciles_before_retry(self):
        l=self.lab
        with self.assertRaises(CrashInjected):l.perform('step.prepare',fault='after_intent')
        op='op.1';l.controller=Controller(l.path/'controller.sqlite',expected_policy_root=digest('policy',l.policy))
        l.no_effect_refusal('retry-before-reconcile',lambda:l.controller.commit(op,l.store,l.time),{'MMC_T3_RECONCILE_REQUIRED'})
        self.assertEqual(l.controller.reconcile(op,l.store)['status'],'NOT_APPLIED')
        self.assertEqual(l.controller.commit(op,l.store,l.time)['status'],'APPLIED');self.assertEqual(l.mutation_count(),1)
    def test_crash_after_commit_reconciles(self):
        l=self.lab
        with self.assertRaises(CrashInjected):l.perform('step.prepare',fault='crash_after')
        l.controller=Controller(l.path/'controller.sqlite',expected_policy_root=digest('policy',l.policy))
        self.assertEqual(l.controller.reconcile('op.1',l.store)['status'],'APPLIED');self.assertEqual(l.mutation_count(),1)
    def test_lost_ack_cannot_be_cancelled_or_hidden_by_pause(self):
        l=self.lab;l.perform('step.prepare',fault='lost_ack')
        for fn in (lambda:l.controller.cancel('op.1'),lambda:l.controller.pause(l.mid)):
            with self.assertRaises(MMCError):fn()
        self.assertEqual(l.controller.reconcile('op.1',l.store)['status'],'APPLIED')
    def test_retry_budget_is_bounded(self):
        l=self.lab;l.perform('step.prepare',fault='before');l.controller.commit('op.1',l.store,l.time,fault='before')
        l.no_effect_refusal('retry-budget',lambda:l.controller.commit('op.1',l.store,l.time),{'MMC_T3_RETRY_LIMIT'})
    def test_partial_multitarget_never_reports_no_effect(self):
        l=self.lab;l.progress(STEPS[:2]);r,x=l.perform('step.coexist',fault='partial')
        self.assertEqual(x['status'],'PARTIAL');self.assertEqual(len(x['changed']),1)
        self.assertEqual(l.controller.replay()['projection']['operations'][r['operation_id']]['status'],'RECOVERY_REQUIRED')
        with self.assertRaises(MMCError):l.controller.cancel(r['operation_id'])
        with self.assertRaises(MMCError):l.controller.commit(r['operation_id'],l.store,l.time)
        self.assertEqual(l.controller.reconcile(r['operation_id'],l.store)['status'],'PARTIAL')
    def test_external_checkpoint_detects_whole_database_rollback(self):
        l=self.lab;backup=l.path/'old.sqlite';shutil.copyfile(l.path/'controller.sqlite',backup)
        l.perform('step.prepare');head=l.controller.replay()['projection']['head']
        shutil.copyfile(backup,l.path/'controller.sqlite')
        with self.assertRaisesRegex(MMCError,'JOURNAL_ROLLBACK'):
            Controller(l.path/'controller.sqlite',expected_policy_root=digest('policy',l.policy),minimum=head)
    def test_plan_revision_does_not_preserve_pending_approvals(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare');l.approve(r)
        b=deepcopy(l.bundle);b['model']['model_id']='foundry.revised'
        from mosaic_mmc_t3 import make_plan
        plan=make_plan(b,l.policy)
        l.controller.revise(l.mid,b,expected_plan_root=plan['root'],expected_head=l.controller.replay()['projection']['head'])
        l.no_effect_refusal('revised',lambda:l.controller.commit(r['operation_id'],l.store,l.time),{'MMC_T3_RECONCILE_REQUIRED'})
    def test_live_target_drift_blocks_commit(self):
        l=self.lab;l.deliver('step.prepare');r=l.request('step.prepare');l.approve(r)
        l.store.raise_security(['producer.old'],5,['revoked.key'])
        l.no_effect_refusal('target-drift',lambda:l.controller.commit(r['operation_id'],l.store,l.time),{'MMC_T3_PRECONDITION_CHANGED'})
