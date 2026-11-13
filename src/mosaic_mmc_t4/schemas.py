"""Structural schemas only. Runtime pin, scope, signature and replay checks remain necessary."""
from .abi import OPERATIONS
from .views import SNAPSHOT_FIELDS,READER_FIELDS

D={'type':'string','pattern':'^[0-9a-f]{64}$'}
S={'type':'string'}
O={'type':'object'}
A={'type':'array'}
I={'type':'integer','minimum':0,'maximum':2**63-1}

def obj(props):return {'type':'object','required':sorted(props),'properties':props,'additionalProperties':False}
def env(body):return obj({'body':body,'root':D})
def const(v):return {'const':v}
def base(props):return {'$schema':'https://json-schema.org/draft/2020-12/schema',**obj(props)}

def schemas():
    snapshot={k:O for k in SNAPSHOT_FIELDS};snapshot.update(schema=const('mmc.snapshot.t4'),migration=S,transition=S,records={'type':'array','maxItems':256},floor=I,revoked=A,head={'type':['object','null']})
    reader={k:D for k in READER_FIELDS};reader.update(schema=const('mmc.reader.t4'),time=obj({'now':I,'uncertainty':I}))
    result={'snapshot':base(snapshot),'reader':base(reader),
      'submission':base({'schema':const('mmc.agent-submission.t4'),'work_order_root':D,'record':O,'notes':{'type':'string','maxLength':4096}}),
      'workspace':base({'schema':const('mmc.workspace.t4'),'snapshot':obj(snapshot),'history':{'type':'array','maxItems':64,'items':O},'journal':{'type':['object','null']}}),
      'descriptor':base({'schema':const('mmc.extension-descriptor.t4'),'id':S,'version':S,'kind':{'enum':['profile','observer']},'input_schema':S,'output_schema':S,'max_bytes':{'type':'integer','minimum':1,'maximum':1048576},'claim_ceiling':S,'effects':const('NONE_DECLARED_TRUSTED_HOST_CODE')}),
      'capture':env(obj({'schema':const('mmc.capture.t4'),'kind':S,'source_id':S,'observed_at':I,'value':{},'raw_hashes':A,'evidence_label':const('CAPTURED_UNAUTHENTICATED'),'coverage':const('EXPLICIT_SELECTED_RESOURCES_ONLY'),'effects':const('HOST_SELECTED_READ'),'signature':const('NOT_SIGNED'),'authority_effect':const('NONE')}))}
    # Exact request envelopes; nested T1-T3/profile objects are validated by their own runtime.
    variants=[]
    for op,args in sorted(OPERATIONS.items()):
        properties={k:{} for k in sorted(args)}
        variants.append(obj({'schema':const('mmc.request.t4'),'operation':const(op),'arguments':obj(properties)}))
    result['request']={'$schema':'https://json-schema.org/draft/2020-12/schema','oneOf':variants}
    boundaries={'profile':const('T4-I1'),'authority_effect':const('NONE'),'native_pippi':const('NOT_BOUND'),'production_authorization':const('NOT_ESTABLISHED'),'signature':const('NOT_SIGNED')}
    work={'schema':const('mmc.work-order.t4'),'scope':O,'snapshot_root':D,'reader_root':D,'evaluator_root':D,'head':{'type':['object','null']},'issued_at':I,'expires_at':I,'ttl':{'type':'integer','minimum':1,'maximum':3600},'claim':S,'subject':S,'source_refs':A,'reference':{},'blockers':A,'allowed_reads':{'type':'array','maxItems':16},'recognized_observers':A,'return_schema':const('mmc.agent-submission.t4'),'instructions':S,'permissions':obj({'proposal_only':const(True),'sign':const(False),'fetch':const(False),'commit':const(False),'amend':const(False)}),'context_scope':const('ONE_UNRESOLVED_CLAIM_NOT_FULL_HISTORY'),'effects':const('NOT_EXECUTED'),**boundaries}
    result['work-order']=env(obj(work))
    view={'schema':const('mmc.view.t4'),'snapshot_root':D,'reader_root':D,'evaluator_root':D,'status':{'enum':['BLOCKED','INDETERMINATE','EVIDENCE_SATISFIES_SELECTED_POLICY']},'court':O,'obligations':A,'blockers':A,'graph':O,'head':{'type':['object','null']},'evidence_label':const('RECOMPUTED_WITH_RECOGNIZED_TESTIMONY'),'eligibility':const('EVIDENCE_ONLY_NOT_OPERATIONAL_PERMISSION'),'effects':const('NOT_EXECUTED'),**boundaries}
    result['view']=env(obj(view))
    review={'schema':const('mmc.submission-review.t4'),'work_order_root':D,'submission_root':D,'snapshot_root':D,'status':{'enum':['ELIGIBLE_FOR_HOST_EVIDENCE_ADMISSION','SUBMISSION_INELIGIBLE']},'record_root':D,'reasons':A,'before':env(obj(view)),'after':env(obj(view)),'evidence_label':const('RECOMPUTED_NOT_STORED'),'effects':const('NOT_EXECUTED'),**boundaries}
    result['review']=env(obj(review))
    for name,s in result.items():s.setdefault('$schema','https://json-schema.org/draft/2020-12/schema')
    return result
