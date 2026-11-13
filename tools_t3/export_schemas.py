"""Export structural contracts only; runtime recomputes cryptographic and semantic checks."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
TOKEN={'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$'}
HEX={'type':'string','pattern':'^[0-9a-f]{64}$'}
KEY={'type':'string','pattern':'^0[23][0-9a-f]{64}$'}
N={'type':'integer','minimum':0,'maximum':9223372036854775807}
def arr(item,n=256,minimum=0):return {'type':'array','items':item,'maxItems':n,'minItems':minimum}
def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def enum(*v):return {'enum':list(v)}
def const(v):return {'const':v}
CLOCK=obj({'now':N,'uncertainty':N})
SCOPE=obj({'migration':TOKEN,'plan_root':HEX,'policy_root':HEX,'transition':TOKEN,'cohort':TOKEN,'targets':arr(TOKEN,64,1)})
BOUNDARY={'profile':const('T3-O1'),'production_authorization':const('NOT_ESTABLISHED'),'authority_effect':const('NONE'),'native_pippi':const('NOT_BOUND'),'signature':const('NOT_SIGNED')}
def schemas():
 observer=obj({'key':KEY,**{k:arr(TOKEN,512,1) for k in ('claims','subjects','cohorts','methods','classes','authorities')}})
 policy=obj({'schema':const('mmc.reader-policy.t3'),'observers':arr(observer,64,1),'jurisdictions':arr(obj({'id':TOKEN,'keys':arr(KEY,32,1),'threshold':{'type':'integer','minimum':1,'maximum':32}}),32,1),'max_age':{'type':'integer','minimum':1,'maximum':86400},'max_clock_uncertainty':{'type':'integer','minimum':0,'maximum':86400},'minimum_sequence':N,'revoked_keys':arr(KEY,128),'max_attempts':{'type':'integer','minimum':1,'maximum':3}})
 observation=obj({'claim':TOKEN,'subject':TOKEN,'value':{},'coverage':enum('COMPLETE','PARTIAL','UNKNOWN'),'members':arr(TOKEN,512),'method':TOKEN,'evidence_class':enum('OBSERVATION','ENFORCEMENT','COVERAGE','TEST_RESULT')})
 approval=obj({'request_root':HEX,'context_root':HEX,'jurisdiction':TOKEN,'decision':enum('ALLOW','DENY')})
 body=obj({'schema':const('mmc.statement.t3'),'kind':enum('observation','approval'),'signer':KEY,**SCOPE['properties'],'issued_at':N,'expires_at':N,'sequence':N,'payload':{'oneOf':[observation,approval]}})
 body['allOf']=[{'if':{'properties':{'kind':const('observation')}},'then':{'properties':{'payload':observation}},'else':{'properties':{'payload':approval}}}]
 statement=obj({'body':body,'algorithm':const('ECDSA-P256-SHA256-DER-LOW-S'),'signature':{'type':'string','pattern':'^[0-9a-f]{16,144}$'},'root':HEX})
 adapter=obj({'schema':const('mmc.adapter.t3'),'id':TOKEN,'mode':enum('SIMULATED_LOCAL_SQLITE','DISPOSABLE_LOCAL_SQLITE','SQLITE_TABLE_MIGRATION'),'atomic_preconditions':const(True),'idempotency':const('ATOMIC_LOCAL_LEDGER'),'production':const(False),'max_targets':const(64),'effect':enum('UPDATE_SIMULATED_ROWS','MIGRATE_DISPOSABLE_WORKLOAD','MIGRATE_ENROLLED_SQLITE_TABLES'),'power_loss_qualification':const('NOT_PERFORMED')})
 adapter['oneOf']=[{'properties':{'mode':const(mode),'effect':const(effect)}} for mode,effect in (('SIMULATED_LOCAL_SQLITE','UPDATE_SIMULATED_ROWS'),('DISPOSABLE_LOCAL_SQLITE','MIGRATE_DISPOSABLE_WORKLOAD'),('SQLITE_TABLE_MIGRATION','MIGRATE_ENROLLED_SQLITE_TABLES'))]
 state=obj({'state':TOKEN,'floor':N,'revoked':arr(TOKEN,128)})
 before=obj({**state['properties'],'version':N})
 def mapping(value):return {'type':'object','minProperties':1,'maxProperties':64,'propertyNames':TOKEN,'additionalProperties':value}
 request=obj({'schema':const('mmc.effect-request.t3'),'operation_id':TOKEN,'scope':SCOPE,'context_root':HEX,'direction':enum('FORWARD','COMPENSATE'),'compensates':{'anyOf':[TOKEN,{'type':'null'}]},'adapter':adapter,'pre_state':mapping(before),'post_state':mapping(state),'prepared_at':N,'expires_at':N,'max_attempts':{'type':'integer','minimum':1,'maximum':3}})
 plan=obj({'body':obj({'schema':const('mmc.operational-plan.t3'),'contract_root':HEX,'evaluator_root':HEX,'bundle':{'type':'object'},'compilation_root':HEX,'model_root':HEX,'policy_root':HEX}), 'root':HEX})
 common_args={'plan':plan,'policy':policy,'migration':TOKEN,'transition':TOKEN,'records':arr(statement),'time':CLOCK,'floor':N,'revoked':arr(TOKEN,128)}
 operations={'capabilities':{},'plan':{'bundle':{'type':'object'},'policy':policy},'verify-statement':{'record':statement},'evidence':common_args,'replay':{**common_args,'candidate':{'type':'object'}},'authority':{'request':request,'policy':policy,'records':arr(statement),'time':CLOCK,'revoked':arr(TOKEN,128)}}
 abi={'oneOf':[obj({'schema':const('mmc.request.t3'),'operation':const(op),'arguments':obj(args)}) for op,args in operations.items()]}
 evidence=obj({'body':obj({'schema':const('mmc.evidence-court.t3'),'evaluator_root':HEX,'scope':SCOPE,'context_root':HEX,'time':CLOCK,'floor':N,'revoked':arr(TOKEN,128),'checks':arr({'type':'object'},4096),'quarantine':arr({'type':'object'},4096),'accepted_statement_roots':arr(HEX),'domain_results':arr({'type':'object'},128),'retirement':{'type':['object','null']},'status':enum('BLOCKED','INDETERMINATE','EVIDENCE_SATISFIES_SELECTED_POLICY'),'coverage_basis':const('RECOGNIZED_TESTIMONY_OVER_DECLARED_ROSTER'),'discovery_completeness':const('NOT_ESTABLISHED'),'effects':const('NOT_EXECUTED'),**BOUNDARY}), 'root':HEX})
 authority=obj({'body':obj({'schema':const('mmc.authority-court.t3'),'evaluator_root':HEX,'request_root':HEX,'time':CLOCK,'status':enum('BLOCKED','SCOPED_APPROVALS_SATISFIED'),'jurisdictions':arr(obj({'jurisdiction':TOKEN,'count':N,'threshold':N,'denied':{'type':'boolean'},'satisfied':{'type':'boolean'}}),32),'ineligible':arr({'type':'object'}),'effects':const('NOT_EXECUTED'),**BOUNDARY}),'root':HEX})
 event=obj({'sequence':N,'previous':HEX,'type':enum('GENESIS','SUBMITTED','REVISED','OBSERVED','PAUSED','RESUMED','FLOOR_RAISED','PREPARED','APPROVED','DISPATCHED','OUTCOME','CANCELLED'),'payload':{'type':'object'},'root':HEX})
 output={'policy':policy,'statement':statement,'effect-request':request,'plan':plan,'request':abi,'evidence-court':evidence,'authority-court':authority,'journal-event':event,'clock':CLOCK,'adapter':adapter}
 return {name:{'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:mmc:t3:'+name,'title':'MMC T3 '+name,**value} for name,value in output.items()}
if __name__=='__main__':
 out=ROOT/'schemas/t3';out.mkdir(exist_ok=True)
 for n,v in schemas().items():(out/(n+'.schema.json')).write_text(json.dumps(v,sort_keys=True,separators=(',',':')),encoding='utf8')
