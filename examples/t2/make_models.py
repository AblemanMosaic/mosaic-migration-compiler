"""Public synthetic declarations, not observations, keys, or approvals for production."""
from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from mosaic_mmc import canonical
from mosaic_mmc_t2.registry import profile_reference

def simple_planning():return {'schema':'mmc.planning-input.t2','facts':[],'orders':[],'coexistence':[],'exclusions':[],'phases':[],'search_limit':8192}

def worker():return {'id':'producer.old','code_version':'legacy','status':'SUSPENDED','can_resume':True,'can_write':True,'fenced':True,'pending_writes':0,'checkpoint_version':None,'resume_version':'legacy','disposition':'FENCE'}

def records():
    key={'id':'key.old','issuer':'authority.owner','not_before':0,'not_after':2000,'retired_at':None,'revoked_at':None,'successor':None}
    token={'id':'asset.legacy','issuer':'authority.owner','key':'key.old','audience':'reader','subject':'producer.old','scopes':['read'],'issued_at':10,'expires_at':1000,'parent':None}
    identity={'schema':'mmc.identity-input.t2','issuer':'authority.owner','audience':'reader','required_scopes':['read'],'accepted_keys':['key.old'],'now':100,'max_delegation_depth':2,'keys':[key],'tokens':[token],'selected_token':'asset.legacy','requested_subject':'producer.old'}
    item={'id':'asset.legacy','digest':hashlib.sha256(b'public fixture').hexdigest(),'schema':'data.v1','readers':['consumer.main'],'writers':['producer.old'],'retain_until':500,'hold':False,'purposes':['analysis']}
    rep={'id':'replica.1','location':'region.allowed','custodian':'owner'}
    storage={'schema':'mmc.storage-input.t2','now':100,'source':{'sequence':7,'consistent':True,'items':[item],'replicas':[rep]},'destination':{'sequence':7,'consistent':True,'items':[{**item,'id':'asset.new'}],'replicas':[rep]},'dispositions':[{'item':'asset.legacy','mode':'COPY','destination':'asset.new','legacy_reader_available':None,'writer_fenced':None}],'allowed_locations':['region.allowed'],'allowed_custodians':['owner'],'minimum_replicas':1,'required_purposes':['analysis'],'allow_extra_destination':False}
    rule={'subject':'producer.old','action':'read','resource':'asset.legacy','purpose':'analysis','effect':'ALLOW','consent_required':True,'minimum_retention':100,'authority':'authority.owner'}
    policy={'schema':'mmc.policy-input.t2','before':[rule],'after':[dict(rule)],'consented_purposes':['analysis'],'required_purposes':['analysis'],'accepted_change_roots':[]}
    workload={'schema':'mmc.workload-input.t2','legacy_versions':['legacy'],'target_version':'new','compatible_checkpoints':[],'workers':[worker()]}
    return dict(identity=identity,storage=storage,policy=policy,workload=workload)

def retirement():
    return {'schema':'mmc.retirement-input.t2','cohort':'cohort.blue','migration_epoch':1,'legacy_version':'legacy','now':100,'max_age':30,
      'producers':[{'id':'producer.old','legacy_capable':True,'active':False,'can_resume':True,'fenced':True}],
      'workers':[worker()],
      'assets':[{'id':'asset.legacy','disposition':'MIGRATED','legacy_reader_available':False,'writer_fenced':True,'retention_satisfied':True,'hold':False}],
      'consumers':[{'id':'consumer.main','required':True,'new_ready':True}],
      'coverage':{'status':'DECLARED_COMPLETE','subjects':['asset.legacy','consumer.main','producer.old'],'observed_at':90,'valid_until':120,'source_ref':'fixture:coverage'},
      'approval':{'cohort':'cohort.blue','migration_epoch':1,'operation':'RETIRE','status':'DECLARED_APPROVED','not_before':90,'not_after':120,'authority':'authority.owner'},
      'recovery':{'current_floor':4,'proposed_floor':4,'current_revoked':['revoked.key'],'proposed_revoked':['revoked.key'],'plan_ref':'fixture:recovery'}}

def routes():return {'schema':'mmc.routes-input.t2','routes':[{'cohort':'cohort.blue','use_case':'blue.usecase','legacy_version':'legacy','new_version':'new','active_route':'DUAL','producers':['producer.old'],'workers':['producer.old'],'consumers':['consumer.main'],'assets':['asset.legacy']}]}

def bundle(domain):
    m=json.loads((ROOT/f'examples/{domain}.json').read_bytes())
    for o in m['objects']:
        if o['id']=='authority.owner':o['attributes']['operations'].append('retire')
    rec=records()[domain]
    subjects={'identity':'producer.old','workload':'cohort.blue','storage':'cohort.blue','policy':'cohort.blue'}
    return {'schema':'mmc.domain-compilation-input.t2','model':m,'planning':simple_planning(),
            'assessments':[{'id':'assessment.'+t['id'],'profile_ref':profile_reference(domain),'transition':t['id'],'subject':subjects[domain],'record':rec} for t in m['objects'] if t['kind']=='Transition'],
            'routes':routes(),'retirements':[{'transition':'step.retire','record':retirement()}]}

if __name__=='__main__':
    for domain in records(): (ROOT/f'examples/t2/{domain}.json').write_bytes(canonical(bundle(domain)))
