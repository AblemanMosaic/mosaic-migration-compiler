import unittest
from .helpers import *
from mosaic_mmc_t2 import assess_retirement,assess_routes,assess_lifecycle
from mosaic_mmc_t2.lifecycle import MAIN,requirements
OK='MATCH_FOR_SUPPLIED_MODEL';BLOCK='BLOCKED_FOR_SUPPLIED_MODEL'
class LifecycleAcceptance(unittest.TestCase):
    def test_ac_lifecycle_01(self):
        for a,b in zip(MAIN,MAIN[1:]):self.assertEqual(assess_lifecycle(lifecycle_input(current=a,requested=b))['status'],OK)
        self.assertEqual(assess_lifecycle(lifecycle_input(current='DRAFT',requested='RETIRED'))['status'],BLOCK)
        paused=assess_lifecycle(lifecycle_input(current='CANARY',requested='PAUSED',action='PAUSE'))
        self.assertEqual(paused['proposed_state']['resume_from'],'CANARY')
        self.assertEqual(assess_lifecycle(lifecycle_input(current='PAUSED',resume_from='CANARY',requested='CANARY',action='RESUME'))['status'],OK)
        self.assertEqual(assess_lifecycle(lifecycle_input(current='PAUSED',resume_from='CANARY',requested='RETIRED',action='RESUME'))['status'],BLOCK)
    def test_ac_lifecycle_02(self):
        m=model();r=routes();self.assertEqual(assess_routes(m,r)['status'],OK)
        r['routes'][0]['use_case']='other';refusal(self,lambda:assess_routes(m,r),'MMC_T2_ROUTE_USE_CASE')
    def test_ac_lifecycle_03(self):
        m=model();r=retirement();r['producers'][0]['fenced']=False;r['workers'][0]['fenced']=False
        self.assertEqual(assess_retirement(m,r)['status'],BLOCK)
    def test_ac_lifecycle_04(self):
        r=retirement();r['workers'][0]['fenced']=False
        self.assertEqual(r['workers'][0]['status'],'SUSPENDED');self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_ac_lifecycle_05(self):
        r=retirement();r['assets'][0].update(disposition='RETAINED_COMPATIBLE',legacy_reader_available=False)
        self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
        r['assets'][0]['legacy_reader_available']=True;self.assertEqual(assess_retirement(model(),r)['status'],'MODEL_RETIREMENT_CONDITIONS_MET')
    def test_ac_lifecycle_06(self):
        r=retirement();r['consumers'][0]['new_ready']=None;self.assertEqual(assess_retirement(model(),r)['status'],'INDETERMINATE')
        r['consumers'][0]['new_ready']=False;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_ac_lifecycle_11(self):
        r=retirement();x=assess_retirement(model(),r);self.assertEqual(x['status'],'MODEL_RETIREMENT_CONDITIONS_MET')
        self.assertEqual(x['approval_recognition'],'NOT_PERFORMED');self.assertEqual(x['operational_eligibility'],'NOT_EVALUATED');self.assertEqual(x['effects'],'NOT_EXECUTED')

class RetirementTests(unittest.TestCase):
    def test_no_omission(self):
        for k in ('producers','workers','assets','consumers'):
            r=retirement();r[k]=[];refusal(self,lambda:assess_retirement(model(),r),'MMC_T2_RETIREMENT_COVERAGE')
    def test_cannot_erase_legacy_capability(self):
        r=retirement();r['producers'][0]['legacy_capable']=False;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_cannot_exempt_consumer(self):
        r=retirement();r['consumers'][0]['required']=False;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_unknown_fence(self):
        r=retirement();r['producers'][0]['fenced']=None;r['workers'][0]['fenced']=None;self.assertEqual(assess_retirement(model(),r)['status'],'INDETERMINATE')
    def test_workload_pending(self):
        r=retirement();r['workers'][0]['pending_writes']=1;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_persisted_hold(self):
        r=retirement();r['assets'][0].update(disposition='DELETED',hold=True);self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_unresolved_asset(self):
        r=retirement();r['assets'][0]['disposition']='UNRESOLVED';self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_partial_is_not_zero(self):
        r=retirement();r['coverage']['status']='PARTIAL';self.assertEqual(assess_retirement(model(),r)['status'],'INDETERMINATE')
    def test_scope_coverage_gap(self):
        r=retirement();r['coverage']['subjects'].pop();self.assertEqual(assess_retirement(model(),r)['status'],'INDETERMINATE')
    def test_declared_future_observation(self):
        r=retirement();r['now']=89;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_expiry_half_open(self):
        r=retirement();r['now']=120;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_age(self):
        r=retirement();r['max_age']=9;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_wrong_cohort_approval(self):
        r=retirement();r['approval']['cohort']='other';self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_wrong_epoch_approval(self):
        r=retirement();r['approval']['migration_epoch']=2;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_negative_approval(self):
        r=retirement();r['approval']['status']='DENIED';self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_unknown_approval(self):
        r=retirement();r['approval']['status']='UNKNOWN';self.assertEqual(assess_retirement(model(),r)['status'],'INDETERMINATE')
    def test_floor_regression(self):
        r=retirement();r['recovery']['proposed_floor']=3;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_revocation_erasure(self):
        r=retirement();r['recovery']['proposed_revoked']=[];self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_inconsistent_roles(self):
        r=retirement();r['workers'][0]['can_resume']=False;self.assertEqual(assess_retirement(model(),r)['status'],BLOCK)
    def test_scope_new_actor_required(self):
        m=model();actor=clone(next(o for o in m['objects'] if o['id']=='producer.old'));actor['id']='producer.other';m['objects'].append(actor)
        next(o for o in m['objects'] if o['id']=='cohort.blue')['attributes']['members'].append(actor['id'])
        refusal(self,lambda:assess_retirement(m,retirement()),'MMC_T2_RETIREMENT_COVERAGE')
    def test_routing_wrong_member(self):
        r=routes();r['routes'][0]['producers']=[];refusal(self,lambda:assess_routes(model(),r),'MMC_T2_ROUTE_MEMBER_SCOPE')
    def test_routes_not_blanket(self):
        r=routes();r['routes'][0]['cohort']='missing';refusal(self,lambda:assess_routes(model(),r),'MMC_T2_ROUTE_COVERAGE')
    def test_lifecycle_no_floor_rollback(self):
        self.assertEqual(assess_lifecycle(lifecycle_input(proposed_floor=4))['status'],BLOCK)
    def test_retired_terminal(self):
        for action in ('ADVANCE','BLOCK','PAUSE','UNCERTAIN','RESUME','COMPENSATE','RECOVERY'):
            x=lifecycle_input(current='RETIRED',requested='DRAFT',action=action);self.assertEqual(assess_lifecycle(x)['status'],BLOCK)
    def test_recovery_not_automatic_reversal(self):
        x=assess_lifecycle(lifecycle_input(current='COMPENSATING',requested='RECOVERY_REQUIRED',action='RECOVERY'));self.assertEqual(x['status'],OK)
        x=assess_lifecycle(lifecycle_input(current='RECOVERY_REQUIRED',requested='DRAFT',action='ADVANCE'));self.assertEqual(x['status'],BLOCK)
    def test_retirement_edge_does_not_grant(self):
        x=assess_lifecycle(lifecycle_input(current='RECONCILED',requested='RETIRED'));self.assertIn('RETIREMENT_ASSESSMENT',x['runtime_guards']);self.assertEqual(x['effects'],'NOT_EXECUTED')
    def test_unknown_route_id(self):
        r=routes();r['routes'].append(clone(r['routes'][0]));refusal(self,lambda:assess_routes(model(),r),'MMC_T2_DUPLICATE_ID')
