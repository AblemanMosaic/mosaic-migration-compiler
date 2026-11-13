import copy,tempfile,unittest,sqlite3,shutil,threading
from unittest.mock import patch
from pathlib import Path
from mosaic_mmc import MMCError,canonical,decode
from mosaic_mmc_t3 import *
from tests_t3.helpers import *

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.e=Env(self.temp.name)
    def state(self):return self.e.controller.replay()['projection']
    def restart(self,minimum=None):self.e.controller=Controller(self.e.root/'controller.sqlite',expected_policy_root=digest('policy',validate_policy(self.e.policy)),minimum=minimum)
    def test_prepare_does_not_mutate_target(self):
        before=self.e.store.snapshot(['producer.old']);self.e.prepare();self.assertEqual(before,self.e.store.snapshot(['producer.old']))
    def test_commit_without_approval_refuses(self):
        self.e.prepare()
        with self.assertRaises(MMCError):self.e.controller.commit('op.1',self.e.store,TIME)
    def test_three_steps_progress(self):
        for i,s in enumerate(['step.prepare','step.cutover','step.retire']):self.assertEqual(self.e.run(s,'op.'+str(i))['status'],'APPLIED')
        self.assertEqual(len(self.state()['migrations'][self.e.mid]['completed']),3)
    def test_duplicate_commit_is_one_effect(self):
        a=self.e.run();b=self.e.controller.commit('op.1',self.e.store,TIME);self.assertEqual(a,b);self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1)
    def test_out_of_order_refused(self):
        self.e.observe('step.retire')
        with self.assertRaisesRegex(MMCError,'ORDER'):self.e.controller.prepare(self.e.mid,'step.retire',self.e.store,TIME,operation_id='later')
    def test_request_mutation_is_detached(self):
        r=self.e.prepare();good=copy.deepcopy(r);r['post_state']['producer.old']['state']='injected';self.e.approve(good);self.e.controller.commit('op.1',self.e.store,TIME);self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['state'],'dual')
    def test_target_change_before_commit(self):
        r=self.e.prepare();self.e.approve(r);self.e.store.raise_security(['producer.old'],5,['revoked.key'])
        with self.assertRaisesRegex(MMCError,'PRECONDITION_CHANGED'):self.e.controller.commit('op.1',self.e.store,TIME)
    def test_expired_request(self):
        r=self.e.prepare();self.e.approve(r)
        with self.assertRaises(MMCError):self.e.controller.commit('op.1',self.e.store,{'now':130,'uncertainty':0})
    def test_new_evidence_invalidates_approval(self):
        r=self.e.prepare();self.e.approve(r);n=observations(self.e.plan)[1];n['body']['sequence']=5;self.e.controller.observe(self.e.mid,resign(n))
        self.assertEqual(self.state()['operations']['op.1']['status'],'CANCELLED')
        with self.assertRaises(MMCError):self.e.controller.commit('op.1',self.e.store,TIME)
    def test_duplicate_observation_no_change(self):
        r=observations(self.e.plan)[0];self.e.controller.observe(self.e.mid,r);before=self.state()['head'];self.e.controller.observe(self.e.mid,r);self.assertEqual(before,self.state()['head'])
    def test_revision_invalidates_approval(self):
        r=self.e.prepare();self.e.approve(r);b=copy.deepcopy(self.e.bundle);b['model']['revision']+=1
        for x in b['retirements']:x['record']['migration_epoch']+=1;x['record']['approval']['migration_epoch']+=1
        p=make_plan(b,self.e.policy);self.e.controller.revise(self.e.mid,b,expected_plan_root=p['root'],expected_head=self.state()['head'])
        self.assertEqual(self.state()['operations']['op.1']['status'],'CANCELLED')
        with self.assertRaises(MMCError):self.e.controller.commit('op.1',self.e.store,TIME)
    def test_concurrent_head(self):
        old=self.state()['head'];self.e.observe()
        with self.assertRaisesRegex(MMCError,'CONCURRENT_HEAD'):self.e.controller.prepare(self.e.mid,'step.prepare',self.e.store,TIME,operation_id='op.x',expected_head=old)
    def test_raise_floor_is_monotone(self):
        self.e.controller.raise_floor(5,['revoked.key'])
        with self.assertRaisesRegex(MMCError,'SECURITY_FLOOR'):self.e.controller.raise_floor(4,['revoked.key'])
    def test_revoked_set_monotone(self):
        self.e.controller.raise_floor(4,['revoked.key'])
        with self.assertRaises(MMCError):self.e.controller.raise_floor(4,[])
    def test_security_change_cancels_pending(self):
        r=self.e.prepare();self.e.approve(r);self.e.controller.raise_floor(4,[public_hex(keys()[1])]);self.assertEqual(self.state()['operations']['op.1']['status'],'CANCELLED')
    def test_pause_resume_requires_fresh_prepare(self):
        r=self.e.prepare();self.e.approve(r);self.e.controller.pause(self.e.mid);self.assertEqual(self.state()['operations']['op.1']['status'],'CANCELLED')
        with self.assertRaises(MMCError):self.e.controller.prepare(self.e.mid,'step.prepare',self.e.store,TIME,operation_id='new')
        self.e.controller.resume(self.e.mid);r=self.e.controller.prepare(self.e.mid,'step.prepare',self.e.store,TIME,operation_id='new');self.e.approve(r);self.assertEqual(self.e.controller.commit('new',self.e.store,TIME)['status'],'APPLIED')
    def test_cancelled_approval_not_reusable(self):
        r=self.e.prepare();self.e.approve(r);self.e.controller.cancel('op.1')
        with self.assertRaises(MMCError):self.e.controller.commit('op.1',self.e.store,TIME)
    def test_wrong_adapter(self):
        r=self.e.prepare();self.e.approve(r);other=SimulatedStore.create(self.e.root/'other.sqlite','sim.other',{'producer.old':'legacy'})
        with self.assertRaisesRegex(MMCError,'ADAPTER_SUBSTITUTION'):self.e.controller.commit('op.1',other,TIME)
    def test_unbound_adapter_refused(self):
        self.e.observe()
        with self.assertRaisesRegex(MMCError,'ADAPTER_UNSUPPORTED'):self.e.controller.prepare(self.e.mid,'step.prepare',object(),TIME,operation_id='x')
    def test_restart_before_approval(self):
        r=self.e.prepare();before=self.state();self.restart();self.assertEqual(before,self.state());self.e.approve(r);self.e.controller.commit('op.1',self.e.store,TIME)
    def test_restart_after_approval(self):
        r=self.e.prepare();self.e.approve(r);before=self.state();self.restart();self.assertEqual(before,self.state());self.e.controller.commit('op.1',self.e.store,TIME)
    def test_restart_after_commit(self):
        self.e.run();before=self.state();self.restart();self.assertEqual(before,self.state());self.e.controller.commit('op.1',self.e.store,TIME);self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1)
    def test_journal_replay_never_calls_adapter(self):
        self.e.run()
        with patch.object(SimulatedStore,'apply',side_effect=AssertionError),patch.object(SimulatedStore,'snapshot',side_effect=AssertionError):self.e.controller.replay()
    def test_journal_missing_event_refused(self):
        self.e.observe();c=sqlite3.connect(self.e.root/'controller.sqlite');c.execute('DELETE FROM events WHERE sequence=2');c.commit();c.close()
        with self.assertRaises(MMCError):self.e.controller.replay()
    def test_wrong_policy_pin(self):
        with self.assertRaises(MMCError):Controller(self.e.root/'controller.sqlite',expected_policy_root='f'*64)
    def test_external_checkpoint_detects_database_restore(self):
        old=self.e.root/'old.sqlite';shutil.copyfile(self.e.root/'controller.sqlite',old);self.e.run();floor=self.state()['head'];shutil.copyfile(old,self.e.root/'controller.sqlite')
        with self.assertRaisesRegex(MMCError,'ROLLBACK'):self.restart(minimum=floor)
        self.restart();self.assertEqual(self.state()['migrations'][self.e.mid]['completed'],[])
    def test_target_reservation_across_migrations(self):
        self.e.prepare();mid='migration.other';self.e.controller.submit(mid,self.e.bundle,expected_plan_root=self.e.plan['root'])
        for r in observations(self.e.plan,mid):self.e.controller.observe(mid,r)
        with self.assertRaisesRegex(MMCError,'RESERVED'):self.e.controller.prepare(mid,'step.prepare',self.e.store,TIME,operation_id='op.other')
    def test_compensation_preserves_other_target_and_floors(self):
        self.e.run();self.e.run('step.cutover','op.2');before=self.e.store.snapshot(['producer.old'])
        r=self.e.controller.prepare(self.e.mid,'step.cutover',self.e.store,TIME,operation_id='undo',direction='COMPENSATE');self.e.approve(r);self.e.controller.commit('undo',self.e.store,TIME)
        self.assertEqual(self.e.store.snapshot(['producer.old']),before);v=self.e.store.snapshot(['asset.legacy'])['asset.legacy'];self.assertEqual(v['state'],'legacy');self.assertEqual(v['floor'],4);self.assertIn('revoked.key',v['revoked']);self.assertEqual(len(self.state()['migrations'][self.e.mid]['completed']),1)
    def test_compensation_blocked_by_completed_successor(self):
        self.e.run();self.e.run('step.cutover','op.2');self.e.run('step.retire','op.3')
        with self.assertRaisesRegex(MMCError,'COMPENSATION_DEPENDENCY'):self.e.controller.prepare(self.e.mid,'step.cutover',self.e.store,TIME,operation_id='undo',direction='COMPENSATE')
    def test_two_cooperating_controllers_do_not_double_dispatch(self):
        r=self.e.prepare();self.e.approve(r);results=[];errors=[]
        def work():
            c=Controller(self.e.root/'controller.sqlite',expected_policy_root=digest('policy',validate_policy(self.e.policy)))
            try:results.append(c.commit('op.1',self.e.store,TIME))
            except MMCError as exc:errors.append(exc.code)
        a=threading.Thread(target=work);b=threading.Thread(target=work);a.start();b.start();a.join();b.join()
        self.assertTrue(results);self.assertTrue(all(x['status']=='APPLIED' for x in results));self.assertEqual(self.e.store.snapshot(['producer.old'])['producer.old']['version'],1);self.assertTrue(all(x in ('MMC_T3_RECONCILE_REQUIRED','MMC_T3_CONCURRENT_DISPATCH') for x in errors))
