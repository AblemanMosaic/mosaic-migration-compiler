import copy,tempfile,unittest,sqlite3,subprocess,sys,os
from unittest.mock import patch
from pathlib import Path
from mosaic_mmc import MMCError,canonical
from mosaic_mmc_t3 import *
from tests_t3.helpers import *

class FaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.e=Env(self.tmp.name)
    def test_lost_ack_reconciles_without_repeating(self):
        self.assertEqual(self.e.run(fault='lost_ack')['status'],'UNKNOWN')
        with self.assertRaisesRegex(MMCError,'RECONCILE_REQUIRED'):self.e.controller.commit('op.1',self.e.store,TIME)
        self.assertEqual(self.e.controller.reconcile('op.1',self.e.store)['status'],'APPLIED');self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1)
    def test_crash_after_effect_before_receipt(self):
        with self.assertRaises(CrashInjected):self.e.run(fault='crash_after')
        c=Controller(self.e.root/'controller.sqlite',expected_policy_root=digest('policy',validate_policy(self.e.policy)));self.assertEqual(c.replay()['projection']['operations']['op.1']['status'],'DISPATCHED');self.assertEqual(c.reconcile('op.1',self.e.store)['status'],'APPLIED');self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1)
    def test_crash_after_intent_before_effect(self):
        with self.assertRaises(CrashInjected):self.e.run(fault='after_intent')
        self.assertEqual(self.e.controller.reconcile('op.1',self.e.store)['status'],'NOT_APPLIED');self.assertEqual(self.e.controller.commit('op.1',self.e.store,TIME)['status'],'APPLIED');self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1)
    def test_retry_budget(self):
        self.assertEqual(self.e.run(fault='before')['status'],'NOT_APPLIED');self.e.controller.commit('op.1',self.e.store,TIME,fault='before')
        with self.assertRaisesRegex(MMCError,'RETRY_LIMIT'):self.e.controller.commit('op.1',self.e.store,TIME)
        self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],0)
    def test_partial_outcome_is_not_no_effect(self):
        result=self.e.run(fault='partial');self.assertEqual(result['status'],'PARTIAL');self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1)
        with self.assertRaises(MMCError):self.e.controller.cancel('op.1')
        with self.assertRaises(MMCError):self.e.controller.commit('op.1',self.e.store,TIME)
        self.assertEqual(self.e.controller.reconcile('op.1',self.e.store)['status'],'PARTIAL')
    def test_adapter_outcome_is_closed_before_journal_admission(self):
        r=self.e.prepare();self.e.approve(r)
        original=self.e.store.apply
        def invalid(request,**kwargs):
            result=original(request,**kwargs);result['unbounded_adapter_note']='not-admitted';return result
        with patch.object(self.e.store,'apply',side_effect=invalid):
            result=self.e.controller.commit('op.1',self.e.store,TIME)
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(result['refusal_code'],'MMC_T3_OUTCOME_FIELDS')
        self.assertNotIn('unbounded_adapter_note',self.e.controller.replay()['projection']['operations']['op.1']['result'])
        self.assertEqual(self.e.controller.reconcile('op.1',self.e.store)['status'],'APPLIED')
    def test_no_revision_while_unknown(self):
        self.e.run(fault='lost_ack')
        with self.assertRaisesRegex(MMCError,'UNRESOLVED_EFFECT'):self.e.controller.revise(self.e.mid,self.e.bundle,expected_plan_root=self.e.plan['root'],expected_head=self.e.controller.replay()['projection']['head'])
    def test_observation_after_unknown_cannot_hide_actual_effect(self):
        self.e.run(fault='lost_ack');r=observations(self.e.plan)[1];r['body']['payload']['value']=False;self.e.controller.observe(self.e.mid,resign(r));self.assertEqual(self.e.controller.assess(self.e.mid,'step.prepare',TIME)['body']['status'],'BLOCKED');self.assertEqual(self.e.controller.reconcile('op.1',self.e.store)['status'],'APPLIED')
    def test_atomic_target_rechecks_preconditions(self):
        r=self.e.prepare();self.e.store.raise_security(['producer.old'],5,['revoked.key'])
        with self.assertRaisesRegex(MMCError,'PRECONDITION_CHANGED'):self.e.store.apply(r)
        self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['state'],'legacy')
    def test_idempotency_collision(self):
        r=self.e.prepare();self.e.approve(r);self.e.controller.commit('op.1',self.e.store,TIME);r['post_state']['producer.old']['state']='other'
        with self.assertRaisesRegex(MMCError,'IDEMPOTENCY_CONFLICT'):self.e.store.apply(r)
    def test_adapter_rejects_security_rollback(self):
        r=self.e.prepare();r['post_state']['producer.old']['floor']=3
        with self.assertRaisesRegex(MMCError,'SECURITY_FLOOR'):self.e.store.apply(r)
    def test_adapter_rejects_revocation_erasure(self):
        r=self.e.prepare();r['post_state']['producer.old']['revoked']=[]
        with self.assertRaisesRegex(MMCError,'SECURITY_FLOOR'):self.e.store.apply(r)
    def test_real_subprocess_dies_before_sqlite_commit(self):
        code='import sqlite3,os,sys\nc=sqlite3.connect(sys.argv[1]);c.execute("BEGIN IMMEDIATE");c.execute("DELETE FROM targets");os._exit(71)\n'
        p=subprocess.run([sys.executable,'-c',code,str(self.e.store.path)],capture_output=True,timeout=15);self.assertEqual(p.returncode,71);self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['state'],'legacy')
    def test_real_subprocess_commits_effect_then_dies(self):
        r=self.e.prepare();self.e.approve(r);request=self.e.root/'request.json';request.write_bytes(canonical(r))
        code='import os,sys\nfrom mosaic_mmc import decode\nfrom mosaic_mmc_t3.storage import SimulatedStore\ns=SimulatedStore(sys.argv[1]);r=decode(open(sys.argv[2],"rb").read());s.apply(r);os._exit(72)\n'
        with self.assertRaises(CrashInjected):self.e.controller.commit('op.1',self.e.store,TIME,fault='after_intent')
        p=subprocess.run([sys.executable,'-c',code,str(self.e.store.path),str(request)],capture_output=True,timeout=15);self.assertEqual(p.returncode,72,p.stderr);self.assertEqual(self.e.controller.reconcile('op.1',self.e.store)['status'],'APPLIED');self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1)
    def test_file_symlink_refused(self):
        link=self.e.root/'alias.sqlite';link.symlink_to(self.e.root/'target.sqlite')
        with self.assertRaises(MMCError):SimulatedStore(link)
    def test_wrong_db_format_refused(self):
        with self.assertRaisesRegex(MMCError,'DATABASE_FORMAT'):SimulatedStore(self.e.root/'controller.sqlite')
    def test_existing_db_never_overwritten(self):
        before=(self.e.root/'target.sqlite').read_bytes()
        with self.assertRaises(MMCError):SimulatedStore.create(self.e.root/'target.sqlite','other',{'x':'y'})
        self.assertEqual(before,(self.e.root/'target.sqlite').read_bytes())
