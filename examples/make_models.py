"""Explicit fixture authoring, never run automatically by a verifier.
All identities are synthetic; evidence hashes point to fixture labels, not live observations.
"""
from pathlib import Path
import hashlib
import json
from mosaic_mmc import canonical, profile_reference


def demo(domain='identity'):
    def obj(id,kind,attributes):
        return {'id':id,'kind':kind,'provenance':{'source_ref':'fixture:'+id,
            'source_digest':hashlib.sha256(('fixture:'+id).encode()).hexdigest(),
            'observed_at':0,'epistemic':'ASSERTED','note':'Synthetic declaration; not live evidence'},
            'attributes':attributes}
    assets={'identity':('credential','delegation-token.v1'), 'storage':('data','record.v1'),
            'policy':('configuration','policy.v1'),'workload':('configuration','job-checkpoint.v1')}
    cls,sch=assets[domain]
    objects=[
      obj('authority.owner','Authority',{'jurisdiction':'demo','principals':['owner'],'operations':['migrate']}),
      obj('asset.legacy','Asset',{'class':cls,'schema_ref':sch,'policy_refs':['policy.base'],'disposition':'UNRESOLVED'}),
      obj('producer.old','Actor',{'roles':['producer','worker'],'versions':['legacy','new'],'resumable':True}),
      obj('consumer.main','Actor',{'roles':['consumer'],'versions':['legacy','new'],'resumable':False}),
      obj('cohort.blue','Cohort',{'members':['producer.old','consumer.main','asset.legacy'],'policy_refs':['policy.base'],'use_case':'blue.usecase'}),
      obj('flow.legacy','Flow',{'source':'producer.old','target':'consumer.main','asset':'asset.legacy','policy_refs':['policy.base'],'cohort':'cohort.blue','legacy':True}),
      obj('policy.base','Policy',{'jurisdiction':'authority.owner','rule':{'op':'literal','value':True}}),
      obj('evidence.fixture','Evidence',{'subject':'producer.old','digest':hashlib.sha256(b'no actual evidence').hexdigest(),'format':'fixture.v1','issuer':'authority.owner','class':'DECLARATION'}),
      obj('obs.drain','Observation',{'subject':'producer.old','predicate':'drained','value':None,'status':'UNKNOWN','measured_at':None,'valid_until':None,'coverage':'PARTIAL','evidence_refs':['evidence.fixture']}),
      obj('obs.data','Observation',{'subject':'asset.legacy','predicate':'migrated','value':None,'status':'UNKNOWN','measured_at':None,'valid_until':None,'coverage':'UNKNOWN','evidence_refs':[]}),
      obj('need.drain','Obligation',{'subject':'producer.old','category':'outstanding-work-disposed','rule':{'op':'eq','observation':'obs.drain','value':True},'evidence_classes':['ENFORCEMENT','OBSERVATION'],'authority':'authority.owner','freshness_seconds':60,'coverage_required':'EXACT_SCOPE','reason':'A dormant worker is not proven drained by silence.'}),
      obj('need.data','Obligation',{'subject':'asset.legacy','category':'persisted-state-disposed','rule':{'op':'eq','observation':'obs.data','value':True},'evidence_classes':['OBSERVATION'],'authority':'authority.owner','freshness_seconds':60,'coverage_required':'EXACT_SCOPE','reason':'Stored legacy state must have an accepted disposition.'}),
      obj('effect.copy','Effect',{'adapter':'simulation.fixture','operation':'migrate','target':'asset.legacy','expected_before':'legacy','expected_after':'new','idempotency_scope':'demo.copy','compensation':None,'authority':'authority.owner','requires':['need.data']}),
      obj('step.prepare','Transition',{'cohort':'cohort.blue','from_states':[{'target':'producer.old','state':'legacy'}],'to_states':[{'target':'producer.old','state':'dual'}],'requires':['need.drain'],'effects':[],'policies':[],'goal':'PREPARE'}),
      obj('step.cutover','Transition',{'cohort':'cohort.blue','from_states':[{'target':'asset.legacy','state':'legacy'}],'to_states':[{'target':'asset.legacy','state':'new'}],'requires':['need.data'],'effects':['effect.copy'],'policies':[],'goal':'CUTOVER'}),
      obj('step.retire','Transition',{'cohort':'cohort.blue','from_states':[{'target':'producer.old','state':'dual'}],'to_states':[{'target':'producer.old','state':'new'}],'requires':['need.drain'],'effects':[],'policies':[],'goal':'RETIRE'}),
      obj('order.prepare-cutover','Dependency',{'before':'step.prepare','after':'step.cutover','relation':'REQUIRES'}),
      obj('order.cutover-retire','Dependency',{'before':'step.cutover','after':'step.retire','relation':'REQUIRES'})]
    return {'schema':'mmc.model.t1','model_id':'demo.'+domain,'revision':1,'domain':domain,
            'profile_ref':profile_reference(),'objects':objects,
            'initial_states':[{'target':'producer.old','state':'legacy'},{'target':'asset.legacy','state':'legacy'}]}

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    for domain in ['identity','storage','policy','workload']:
        (root/(domain+'.json')).write_bytes(canonical(demo(domain)))
