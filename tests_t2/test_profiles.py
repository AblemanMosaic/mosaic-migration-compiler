import unittest
from .helpers import *
from mosaic_mmc_t2.profiles import identity,storage,policy,workload
from mosaic_mmc_t2 import assess_profile,profile_reference,replay_assessment
from mosaic_mmc_t2.common import digest

OK='MATCH_FOR_SUPPLIED_MODEL';BLOCK='BLOCKED_FOR_SUPPLIED_MODEL'
class ProfileAcceptance(unittest.TestCase):
    def test_ac_profile_01(self):
        r=records()['identity'];self.assertEqual(identity(r)['status'],OK)
        r['keys'][0]['issuer']='wrong';self.assertEqual(identity(r)['status'],BLOCK)
    def test_ac_profile_02(self):
        r=records()['identity'];r['keys'][0]['revoked_at']=80;x=identity(r)
        self.assertEqual(x['historical'][0]['status'],'CONSISTENT_AT_ISSUANCE');self.assertEqual(x['status'],BLOCK)
        r=records()['identity'];r['keys'][0]['retired_at']=80;r['keys'][0]['successor']='key.new'
        r['keys'].append({**r['keys'][0],'id':'key.new','retired_at':None,'not_before':80,'successor':None});r['accepted_keys']=['key.new']
        r['tokens'][0].update(key='key.new',issued_at=90);self.assertEqual(identity(r)['status'],OK)
    def test_ac_profile_03(self):
        r=records()['storage'];self.assertEqual(storage(r)['status'],OK);r['destination']['items']=[];self.assertEqual(storage(r)['status'],BLOCK)
    def test_ac_profile_04(self):
        r=records()['storage'];r['destination']['replicas'][0]['location']='forbidden';self.assertEqual(storage(r)['status'],BLOCK)
        r=records()['storage'];r['dispositions'][0].update(mode='DELETE',destination=None);r['destination']['items']=[];self.assertEqual(storage(r)['status'],BLOCK)
        r['now']=600;self.assertEqual(storage(r)['status'],OK);r['source']['items'][0]['hold']=True;self.assertEqual(storage(r)['status'],BLOCK)
    def test_ac_profile_05(self):
        r=records()['policy'];r['after'][0]['consent_required']=False;x=policy(r);self.assertEqual(x['status'],BLOCK);self.assertEqual(len(x['widenings']),1)
        r['accepted_change_roots']=[x['widenings'][0]['root']];x=policy(r);self.assertEqual(x['status'],OK);self.assertEqual(x['authorization'],'CURRENT_SCOPED_APPROVAL_REQUIRED')
    def test_ac_profile_06(self):
        r=records()['policy'];r['consented_purposes']=[];self.assertEqual(policy(r)['status'],BLOCK)
        r['consented_purposes']=None;self.assertEqual(policy(r)['status'],'INDETERMINATE')
        r=records()['policy'];r['required_purposes'].append('other');self.assertEqual(policy(r)['status'],BLOCK)
    def test_ac_profile_07(self):
        r=records()['workload'];r['workers'][0]['fenced']=False;self.assertEqual(workload(r)['status'],BLOCK)
        r['workers'][0]['fenced']=True;self.assertEqual(workload(r)['status'],OK)
    def test_ac_profile_08(self):
        r=records()['workload'];w=r['workers'][0];w.update(checkpoint_version='checkpoint.old',resume_version='new')
        self.assertEqual(workload(r)['status'],BLOCK)
        r['compatible_checkpoints']=[{'checkpoint':'checkpoint.old','runtime':'new'}];self.assertEqual(workload(r)['status'],OK)
        w['pending_writes']=1;self.assertEqual(workload(r)['status'],BLOCK)
    def test_ac_profile_12(self):
        from mosaic_mmc import compile_model,canonical
        from mosaic_mmc.contracts import realization_identity
        before=canonical(compile_model(model()));root=realization_identity()
        for name,r in records().items():self.assertEqual(assess_profile(profile_reference(name),r)['body']['result']['status'],OK)
        self.assertEqual(root,realization_identity());self.assertEqual(before,canonical(compile_model(model())))

class IdentityTests(unittest.TestCase):
    def test_delegation(self):
        r=records()['identity'];r['keys'].append({**r['keys'][0],'id':'key.delegate','issuer':'producer.old'})
        r['tokens'].append({**clone(r['tokens'][0]),'id':'child','issuer':'producer.old','key':'key.delegate','subject':'child.subject','issued_at':20,'parent':'asset.legacy'})
        r['accepted_keys'].append('key.delegate');r.update(selected_token='child',requested_subject='child.subject')
        self.assertEqual(identity(r)['status'],OK)
        r['tokens'][1]['scopes'].append('write');self.assertEqual(identity(r)['status'],BLOCK)
    def test_expiry_exclusive(self):
        r=records()['identity'];r['now']=1000;self.assertEqual(identity(r)['status'],BLOCK)
    def test_not_yet_valid(self):
        r=records()['identity'];r['now']=9;self.assertEqual(identity(r)['status'],BLOCK)
    def test_revocation_at_issuance(self):
        r=records()['identity'];r['keys'][0]['revoked_at']=10;x=identity(r);self.assertEqual(x['historical'][0]['status'],'INCONSISTENT_AT_ISSUANCE')
    def test_successor_cycle(self):
        r=records()['identity'];r['keys'][0]['successor']='key.old';refusal(self,lambda:identity(r),'MMC_T2_KEY_CYCLE')
    def test_parent_cycle(self):
        r=records()['identity'];r['tokens'][0]['parent']='asset.legacy';refusal(self,lambda:identity(r),'MMC_T2_DELEGATION_CYCLE')
    def test_missing_parent(self):
        r=records()['identity'];r['tokens'][0]['parent']='missing';refusal(self,lambda:identity(r),'MMC_T2_TOKEN_REFERENCE')
    def test_no_signature_promotion(self):
        x=identity(records()['identity']);self.assertEqual(x['token_signatures'],'NOT_CHECKED');self.assertEqual(x['recognized_authority'],'NOT_ESTABLISHED')

class StorageTests(unittest.TestCase):
    def test_digest_and_schema(self):
        for k,v in [('digest','0'*64),('schema','other')]:
            r=records()['storage'];r['destination']['items'][0][k]=v;self.assertEqual(storage(r)['status'],BLOCK)
    def test_reader_and_writer_loss(self):
        for k in ('readers','writers','purposes'):
            r=records()['storage'];r['destination']['items'][0][k]=[];self.assertEqual(storage(r)['status'],BLOCK)
    def test_unknown_consistency(self):
        r=records()['storage'];r['source']['consistent']=None;self.assertEqual(storage(r)['status'],'INDETERMINATE')
    def test_older_snapshot(self):
        r=records()['storage'];r['destination']['sequence']=6;self.assertEqual(storage(r)['status'],BLOCK)
    def test_missing_disposition(self):
        r=records()['storage'];r['dispositions']=[];refusal(self,lambda:storage(r),'MMC_T2_DISPOSITION_COVERAGE')
    def test_duplicate_replica(self):
        r=records()['storage'];r['destination']['replicas']*=2;refusal(self,lambda:storage(r),'MMC_T2_DUPLICATE_ID')
    def test_no_independence_claim(self):
        r=records()['storage'];r['destination']['replicas'].append({**r['destination']['replicas'][0],'id':'replica.2'});r['minimum_replicas']=2
        x=storage(r);self.assertEqual(x['status'],OK);self.assertEqual(x['replica_independence'],'NOT_ESTABLISHED')
    def test_retained_reader(self):
        r=records()['storage'];r['destination']['items']=[];r['dispositions'][0].update(mode='RETAIN',destination=None,legacy_reader_available=False)
        self.assertEqual(storage(r)['status'],BLOCK);r['dispositions'][0]['legacy_reader_available']=True;self.assertEqual(storage(r)['status'],OK)
    def test_isolation(self):
        r=records()['storage'];r['destination']['items']=[];r['dispositions'][0].update(mode='ISOLATE',destination=None,writer_fenced=None)
        self.assertEqual(storage(r)['status'],'INDETERMINATE');r['dispositions'][0]['writer_fenced']=True;self.assertEqual(storage(r)['status'],OK)
    def test_extra_destination(self):
        r=records()['storage'];r['destination']['items'].append({**r['destination']['items'][0],'id':'extra'})
        self.assertEqual(storage(r)['status'],BLOCK);r['allow_extra_destination']=True;self.assertEqual(storage(r)['status'],OK)

class PolicyTests(unittest.TestCase):
    def test_deny_precedence(self):
        r=records()['policy'];r['after'].append({**r['after'][0],'effect':'DENY'});r['required_purposes']=[]
        x=policy(r);self.assertEqual(x['status'],OK);self.assertEqual(len(x['removed_permissions']),1)
    def test_unknown_change_root(self):
        r=records()['policy'];r['accepted_change_roots']=['0'*64];refusal(self,lambda:policy(r),'MMC_T2_CHANGE_SCOPE')
    def test_new_permission(self):
        r=records()['policy'];r['after'].append({**r['after'][0],'action':'write'});self.assertEqual(len(policy(r)['widenings']),1)
    def test_duplicate_rule(self):
        r=records()['policy'];r['after']*=2;refusal(self,lambda:policy(r),'MMC_T2_DUPLICATE_RULE')
    def test_authority_change(self):
        r=records()['policy'];r['after'][0]['authority']='other';self.assertEqual(policy(r)['status'],BLOCK)
    def test_retention_reduction(self):
        r=records()['policy'];r['after'][0]['minimum_retention']=99;self.assertEqual(policy(r)['status'],BLOCK)
    def test_stricter_policy(self):
        r=records()['policy'];r['after'][0]['minimum_retention']=101;self.assertEqual(policy(r)['status'],OK)

class WorkloadTests(unittest.TestCase):
    def test_terminated(self):
        r=records()['workload'];r['workers'][0].update(status='TERMINATED',can_resume=False,can_write=False,disposition='TERMINATE',fenced=False);self.assertEqual(workload(r)['status'],OK)
    def test_false_termination(self):
        r=records()['workload'];r['workers'][0].update(status='TERMINATED',disposition='TERMINATE');self.assertEqual(workload(r)['status'],BLOCK)
    def test_drain_does_not_mean_suspend(self):
        r=records()['workload'];r['workers'][0]['disposition']='DRAIN';self.assertEqual(workload(r)['status'],BLOCK)
    def test_new_code_old_resume(self):
        r=records()['workload'];r['workers'][0].update(code_version='new',resume_version='legacy',fenced=False);self.assertEqual(workload(r)['status'],BLOCK)
    def test_unresolved(self):
        r=records()['workload'];r['workers'][0]['disposition']='UNRESOLVED';self.assertEqual(workload(r)['status'],'INDETERMINATE')

# Fixed malformed-input regressions for each independently selectable profile.
class ShapeTests(unittest.TestCase):pass
for name,handler in [('identity',identity),('storage',storage),('policy',policy),('workload',workload)]:
    for variant in ('extra','missing','list','schema','null'):
        def test(self,name=name,handler=handler,variant=variant):
            r=records()[name]
            if variant=='extra':r['approved']=True
            elif variant=='missing':del r['schema']
            elif variant=='list':r=[]
            elif variant=='schema':r['schema']='other'
            else:r=None
            refusal(self,lambda:handler(r))
        setattr(ShapeTests,'test_'+name+'_'+variant,test)
