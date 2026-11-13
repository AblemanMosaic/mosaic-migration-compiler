import copy,tempfile,unittest
from unittest.mock import patch
from mosaic_mmc import MMCError,canonical
from mosaic_mmc_t3 import *
from mosaic_mmc_t3.statements import backend,ORDER
from tests_t3.helpers import *
from mosaic_mmc_t3.courts import scope

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.b=bundle();self.p=policy(self.b);self.plan=make_plan(self.b,self.p);self.records=observations(self.plan)
    def assess(self,records=None,time=None,**extra):
        return evaluate_evidence(self.plan,self.p,'migration.blue','step.prepare',self.records if records is None else records,time or TIME,**extra)['body']
    def test_signed_evidence_satisfies(self):self.assertEqual(self.assess()['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY')
    def test_missing_is_not_false(self):self.assertEqual(self.assess([])['status'],'INDETERMINATE')
    def test_partial_is_not_complete(self):
        r=copy.deepcopy(self.records);r[0]['body']['payload']['coverage']='PARTIAL';r[0]=resign(r[0]);self.assertNotEqual(self.assess(r)['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY')
    def test_incomplete_roster_blocks(self):
        r=copy.deepcopy(self.records);r[0]['body']['payload']['members']=[];r[0]=resign(r[0]);self.assertEqual(self.assess(r)['status'],'BLOCKED')
    def test_stale_is_not_zero_activity(self):self.assertEqual(self.assess(time={'now':120,'uncertainty':0})['status'],'INDETERMINATE')
    def test_not_yet_valid(self):self.assertEqual(self.assess(time={'now':89,'uncertainty':0})['status'],'INDETERMINATE')
    def test_uncertain_clock_inside(self):self.assertEqual(self.assess(time={'now':100,'uncertainty':2})['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY')
    def test_uncertain_clock_crosses_expiry(self):self.assertEqual(self.assess(time={'now':119,'uncertainty':1})['status'],'INDETERMINATE')
    def test_clock_uncertainty_policy(self):self.assertEqual(self.assess(time={'now':100,'uncertainty':3})['status'],'BLOCKED')
    def test_age_equality(self):
        rr=[]
        for r in self.records:
            r=copy.deepcopy(r);r['body']['issued_at']=70;r['body']['expires_at']=150;rr.append(resign(r))
        self.assertEqual(self.assess(rr)['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY');self.assertEqual(self.assess(rr,time={'now':101,'uncertainty':0})['status'],'INDETERMINATE')
    def test_explicit_floor_rejects_rollback(self):self.assertEqual(self.assess(floor=5)['status'],'INDETERMINATE')
    def test_revoked_observer(self):self.assertEqual(self.assess(revoked=[public_hex(keys()[0])])['status'],'INDETERMINATE')
    def test_unrecognized_signer(self):
        rr=[]
        for r in self.records:
            r=copy.deepcopy(r);r['body']['signer']=public_hex(keys()[5]);rr.append(resign(r,keys()[5]))
        self.assertEqual(self.assess(rr)['status'],'INDETERMINATE')
    def test_unrecognized_method(self):
        rr=[]
        for r in self.records:
            r=copy.deepcopy(r);r['body']['payload']['method']='unsupported-method';rr.append(resign(r))
        self.assertEqual(self.assess(rr)['status'],'INDETERMINATE')
    def test_coverage_class_required(self):
        rr=copy.deepcopy(self.records);rr[0]['body']['payload']['evidence_class']='OBSERVATION';rr[0]=resign(rr[0]);self.assertEqual(self.assess(rr)['status'],'INDETERMINATE')
    def test_fact_class_not_coerced(self):
        rr=copy.deepcopy(self.records)
        for n,r in enumerate(rr):
            if r['body']['payload']['claim']=='fact:obs.drain':r['body']['payload']['evidence_class']='COVERAGE';rr[n]=resign(r)
        self.assertEqual(self.assess(rr)['status'],'INDETERMINATE')
    def test_negative_observation_blocks(self):
        rr=copy.deepcopy(self.records)
        for n,r in enumerate(rr):
            if r['body']['payload']['claim']=='fact:obs.drain':r['body']['payload']['value']=False;rr[n]=resign(r)
        self.assertEqual(self.assess(rr)['status'],'BLOCKED')
    def test_conflicting_applicable_observations_block(self):
        r=copy.deepcopy(next(r for r in self.records if r['body']['payload']['claim']=='fact:obs.drain'));r['body']['payload']['value']=False
        self.assertEqual(self.assess(self.records+[resign(r)])['status'],'BLOCKED')
    def test_duplicate_statement_no_extra_support(self):self.assertEqual(self.assess()['accepted_statement_roots'],self.assess(self.records+self.records)['accepted_statement_roots'])
    def test_true_not_integer(self):
        rr=copy.deepcopy(self.records)
        for n,r in enumerate(rr):
            if r['body']['payload']['claim']=='fact:obs.drain':r['body']['payload']['value']=1;rr[n]=resign(r)
        self.assertEqual(self.assess(rr)['status'],'BLOCKED')
    def test_rehashed_pass_not_evidence(self):
        rr=copy.deepcopy(self.records);rr[-1]['body']['payload']['value']={'status':'PASS'};rr[-1]=resign(rr[-1])
        with self.assertRaises(MMCError):self.assess(rr)
    def test_record_cannot_rewrite_audience(self):
        rr=copy.deepcopy(self.records);rr[-1]['body']['payload']['value']['audience']='elsewhere';rr[-1]=resign(rr[-1])
        with self.assertRaisesRegex(MMCError,'REWRITES_REQUIREMENT'):self.assess(rr)
    def test_key_revocation_current_blocks(self):
        rr=copy.deepcopy(self.records);rr[-1]['body']['payload']['value']['keys'][0]['revoked_at']=95;rr[-1]=resign(rr[-1]);self.assertEqual(self.assess(rr)['status'],'BLOCKED')
    def test_domain_uses_reader_time_not_statement_now(self):
        rr=copy.deepcopy(self.records);rr[-1]['body']['payload']['value']['now']=0;rr[-1]['body']['payload']['value']['keys'][0]['revoked_at']=95;rr[-1]=resign(rr[-1]);self.assertEqual(self.assess(rr)['status'],'BLOCKED')
    def test_obligations_bind_method_authority(self):
        p=copy.deepcopy(self.p);p['observers'][0]['authorities']=['other'];plan=make_plan(self.b,p)
        self.assertEqual(evaluate_evidence(plan,p,'migration.blue','step.prepare',observations(plan),TIME)['body']['status'],'INDETERMINATE')
    def test_missing_model_jurisdiction(self):
        p=copy.deepcopy(self.p);p['jurisdictions']=p['jurisdictions'][1:];plan=make_plan(self.b,p)
        self.assertEqual(evaluate_evidence(plan,p,'migration.blue','step.prepare',observations(plan),TIME)['body']['status'],'BLOCKED')
    def test_dormant_retirement_blocks(self):
        rr=observations(self.plan,transition='step.retire');rr[-1]['body']['payload']['value']['workers'][0]['fenced']=False;rr[-1]=resign(rr[-1])
        self.assertEqual(evaluate_evidence(self.plan,self.p,'migration.blue','step.retire',rr,TIME,floor=4,revoked=['revoked.key'])['body']['status'],'BLOCKED')
    def test_retirement_satisfies_recognized_snapshot(self):
        result=evaluate_evidence(self.plan,self.p,'migration.blue','step.retire',observations(self.plan,transition='step.retire'),TIME,floor=4,revoked=['revoked.key'])
        self.assertEqual(result['body']['status'],'EVIDENCE_SATISFIES_SELECTED_POLICY');self.assertEqual(result['body']['discovery_completeness'],'NOT_ESTABLISHED')
    def test_retirement_security_floor(self):
        rr=observations(self.plan,transition='step.retire');rr[-1]['body']['payload']['value']['recovery']['proposed_floor']=3;rr[-1]=resign(rr[-1])
        self.assertEqual(evaluate_evidence(self.plan,self.p,'migration.blue','step.retire',rr,TIME,floor=4,revoked=['revoked.key'])['body']['status'],'BLOCKED')
    def test_retirement_revocation_floor(self):
        rr=observations(self.plan,transition='step.retire');rr[-1]['body']['payload']['value']['recovery']['proposed_revoked']=[];rr[-1]=resign(rr[-1])
        self.assertEqual(evaluate_evidence(self.plan,self.p,'migration.blue','step.retire',rr,TIME,floor=4,revoked=['revoked.key'])['body']['status'],'BLOCKED')
    def test_replay_recomputes(self):
        r=evaluate_evidence(self.plan,self.p,'migration.blue','step.prepare',self.records,TIME);replay_evidence(self.plan,self.p,'migration.blue','step.prepare',self.records,TIME,r)
        r['body']['status']='AUTHORIZED';r['root']=digest('assessment',r['body'])
        with self.assertRaisesRegex(MMCError,'REPLAY_MISMATCH'):replay_evidence(self.plan,self.p,'migration.blue','step.prepare',self.records,TIME,r)
    def test_court_no_effect_or_clock_calls(self):
        with patch('time.time',side_effect=AssertionError),patch('subprocess.run',side_effect=AssertionError),patch('socket.socket',side_effect=AssertionError):self.assess()
    def test_empty_unsigned_report_refused(self):
        with self.assertRaises(MMCError):self.assess([{'status':'PASS'}])
    def test_signature_mutation(self):
        r=copy.deepcopy(self.records[0]);r['body']['sequence']+=1
        with self.assertRaises(MMCError):verify(r)
    def test_signature_mutation_rehashed(self):
        r=copy.deepcopy(self.records[0]);r['body']['sequence']+=1;r['root']=digest('statement',{k:r[k] for k in ('body','algorithm','signature')})
        with self.assertRaisesRegex(MMCError,'SIGNATURE'):verify(r)
    def test_inadmissible_curve_point(self):
        r=copy.deepcopy(self.records[0]);r['body']['signer']='02'+'ff'*32
        with self.assertRaises(MMCError):verify(r)
    def test_signature_high_s_refused(self):
        ec,utils,*_=backend();r=copy.deepcopy(self.records[0]);a,b=utils.decode_dss_signature(bytes.fromhex(r['signature']));r['signature']=utils.encode_dss_signature(a,ORDER-b).hex();r['root']=digest('statement',{k:r[k] for k in ('body','algorithm','signature')})
        with self.assertRaisesRegex(MMCError,'SIGNATURE_ENCODING'):verify(r)
    def test_finite_evidence(self):
        with self.assertRaisesRegex(MMCError,'LIMIT'):self.assess([self.records[0]]*257)
    def test_signing_does_not_expose_private_scalar(self):self.assertEqual(set(self.records[0]),{'body','signature','algorithm','root'})

for field,value in [('migration','other'),('plan_root','f'*64),('policy_root','e'*64),('transition','step.cutover'),('cohort','cohort.other'),('targets',['consumer.main'])]:
    def test(self,field=field,value=value):
        rr=[]
        for r in self.records:
            r=copy.deepcopy(r);r['body'][field]=value;rr.append(resign(r))
        self.assertEqual(self.assess(rr)['status'],'INDETERMINATE')
    setattr(EvidenceTests,'test_wrong_scope_'+field,test)

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.e=Env(self.temp.name);self.r=self.e.prepare();self.records=approvals(self.e.plan,self.r)
    def assess(self,records=None,time=TIME,**kw):return assess_authority(self.r,self.e.policy,self.records if records is None else records,time,**kw)['body']
    def test_joint_approval(self):self.assertEqual(self.assess()['status'],'SCOPED_APPROVALS_SATISFIED')
    def test_one_missing_cannot_mask(self):self.assertEqual(self.assess(self.records[:1])['status'],'BLOCKED')
    def test_denial_blocks(self):
        r=copy.deepcopy(self.records[1]);r['body']['payload']['decision']='DENY';r=resign(r,keys()[2]);self.assertEqual(self.assess(self.records+[r])['status'],'BLOCKED')
    def test_duplicate_signer_not_threshold(self):
        p=copy.deepcopy(self.e.policy);p['jurisdictions'][0]['keys']=sorted([public_hex(keys()[1]),public_hex(keys()[4])]);p['jurisdictions'][0]['threshold']=2
        plan=make_plan(self.e.bundle,p);r=copy.deepcopy(self.r);r['scope']=scope(plan,self.e.mid,'step.prepare');a=approvals(plan,r)
        self.assertEqual(assess_authority(r,p,a+[a[0]],TIME)['body']['status'],'BLOCKED')
    def test_unrecognized_signature(self):
        r=copy.deepcopy(self.records[1]);r['body']['signer']=public_hex(keys()[5]);r=resign(r,keys()[5]);self.assertEqual(self.assess([self.records[0],r])['status'],'BLOCKED')
    def test_expiry_exact_boundary(self):self.assertEqual(self.assess(time={'now':120,'uncertainty':0})['status'],'BLOCKED')
    def test_not_before(self):self.assertEqual(self.assess(time={'now':89,'uncertainty':0})['status'],'BLOCKED')
    def test_revoked_approver(self):self.assertEqual(self.assess(revoked=[public_hex(keys()[1])])['status'],'BLOCKED')
    def test_report_cannot_approve(self):
        with self.assertRaises(MMCError):self.e.controller.approve('op.1',[{'status':'PASS'}],TIME)
    def test_success_does_not_execute(self):
        before=self.e.store.snapshot(self.r['scope']['targets']);self.e.approve(self.r);self.assertEqual(before,self.e.store.snapshot(self.r['scope']['targets']))

for field,value in [('request_root','e'*64),('context_root','f'*64),('jurisdiction','other')]:
    def test(self,field=field,value=value):
        rr=[]
        for i,r in enumerate(self.records):
            r=copy.deepcopy(r);r['body']['payload'][field]=value;rr.append(resign(r,keys()[i+1]))
        self.assertEqual(self.assess(rr)['status'],'BLOCKED')
    setattr(ApprovalTests,'test_wrong_'+field,test)
