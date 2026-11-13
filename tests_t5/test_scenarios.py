"""Ten distinct frozen end-to-end scenarios; same-author local simulation only."""
import copy,functools,unittest
from mosaic_mmc import canonical,MMCError
from mosaic_mmc_t5 import run_scenario,catalogue,replay_scenario
from mosaic_mmc_t5.foundry import inspect_result,hash_value

@functools.lru_cache(maxsize=16)
def result(name):return run_scenario(name)

class EndToEndTests(unittest.TestCase):pass
for c in catalogue():
    def test(self,c=c):
        r=result(c['scenario']);b=r['body']
        self.assertEqual(b['status'],'PASS_SCOPED_SIMULATION')
        self.assertEqual(b['case'],c['id']);self.assertEqual(b['primary_transitions_completed'],7)
        self.assertTrue(set(c['required_milestones'])<=set(b['milestones']))
        self.assertTrue(all(x['passed'] is True for x in b['checks']))
        self.assertEqual(inspect_result(r,expected_root=r['root'])['status'],'PIN_AND_RECORDED_JOURNAL_MATCH')
    setattr(EndToEndTests,'test_'+c['id'].lower().replace('-','_')+'_'+c['scenario'].replace('-','_'),test)

class ReproducibilityTests(unittest.TestCase):
    def test_exact_fresh_replay(self):
        r=result('safe-token')
        self.assertEqual(replay_scenario('safe-token',r)['status'],'MATCH_EXACT_FRESH_SIMULATION')
    def test_rehashed_fabricated_result_not_replay(self):
        r=copy.deepcopy(result('safe-token'));next(x for x in r['body']['trace'] if x['kind']=='discovery')['value']['objects']+=1
        previous='0'*64
        for x in r['body']['trace']:
            x['previous']=previous;x['root']=hash_value('step',{k:x[k] for k in ('index','previous','kind','value')});previous=x['root']
        r['root']=hash_value('trace',r['body'])
        with self.assertRaisesRegex(MMCError,'REPLAY_MISMATCH'):replay_scenario('safe-token',r)
    def test_different_delivery_order_same_final_semantics(self):
        a=result('safe-token');b=run_scenario('safe-token',seed=7)
        self.assertEqual(a['body']['final_targets'],b['body']['final_targets'])
        self.assertEqual(a['body']['target_effects'],b['body']['target_effects'])
        self.assertNotEqual(a['root'],b['root'])
    def test_production_and_productivity_not_inferred(self):
        for c in catalogue():
            b=result(c['scenario'])['body'];self.assertIs(b['production_evidence'],False)
            self.assertEqual(b['native_pippi'],'NOT_BOUND');self.assertEqual(b['productivity_claim'],'NOT_ESTABLISHED')
    def test_no_effect_from_integrity_inspection(self):
        from unittest.mock import patch
        r=result('safe-token')
        with patch('mosaic_mmc_t3.storage.SimulatedStore.apply',side_effect=AssertionError('effect')),patch('mosaic_mmc_t3.storage.create_db',side_effect=AssertionError('database')):
            self.assertEqual(inspect_result(r,expected_root=r['root'])['effects'],'NOT_EXECUTED')
    def test_reader_pin_not_inferred(self):
        r=result('safe-token')
        with self.assertRaises(MMCError):inspect_result(r,expected_root='0'*64)

class AdmissionTests(unittest.TestCase):pass
for idx,value in enumerate([None,{},[],False,1,'unknown','../safe-token','safe-token;echo yes']):
    def test(self,v=value):
        with self.assertRaises(MMCError):run_scenario(v)
    setattr(AdmissionTests,'test_invalid_scenario_'+str(idx),test)
for idx,value in enumerate([True,False,None,-1,32,1.0,'1',{},[]]):
    def test(self,v=value):
        with self.assertRaises(MMCError):run_scenario('safe-token',seed=v)
    setattr(AdmissionTests,'test_invalid_seed_'+str(idx),test)

class ResultMutationTests(unittest.TestCase):pass
for idx,(field,value) in enumerate([
    ('authority_effect','EXECUTE'),('production_evidence',True),('production_evidence',0),
    ('native_pippi','NATIVE_ENFORCED'),('independent_review','PASS'),('productivity_claim','SAVES_HOURS'),
    ('signature','SIGNED'),('effects','NONE'),('status','APPROVED'),('target_effects',True),
    ('primary_transitions_completed',True),('seed',True),('case','AC-E2E-09'),('domain','storage'),
    ('contract_root','f'*64),('foundry_realization','0'*64),('native_evaluator','0'*64)]):
    def test(self,f=field,v=value):
        r=copy.deepcopy(result('safe-token'));r['body'][f]=v;r['root']=hash_value('trace',r['body'])
        with self.assertRaises(MMCError):inspect_result(r,expected_root=r['root'])
    setattr(ResultMutationTests,'test_rehashed_'+field+'_'+str(idx),test)


class MalformedRecordTests(unittest.TestCase):pass
for idx,(field,value) in enumerate([('scenario',[]),('scenario',{}),('milestones',[{}]),('journal',[None]),
                                   ('journal',[{}]),('final_targets',{}),('final_targets',{'producer.old':None})]):
    def test(self,f=field,v=value):
        r=copy.deepcopy(result('safe-token'));r['body'][f]=v;r['root']=hash_value('trace',r['body'])
        with self.assertRaises(MMCError):inspect_result(r,expected_root=r['root'])
    setattr(MalformedRecordTests,'test_typed_malformed_'+str(idx),test)
