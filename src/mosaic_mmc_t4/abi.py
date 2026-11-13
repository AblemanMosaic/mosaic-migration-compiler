"""Closed read-only data interface. Host paths, signing and commits are absent."""
from .common import *
from . import views,work,collectors,extensions,integrations
from ._pins import VERSION,REVISION

OPERATIONS={
 'capabilities':set(), 'inspect':{'snapshot'}, 'assess':{'snapshot','reader'},
 'replay':{'snapshot','reader','candidate'}, 'compare':{'first','second'},
 'work-order':{'snapshot','reader','claim','allowed_reads','ttl'},
 'review-submission':{'snapshot','reader','work_order','submission','expected_work_root'},
 'journal':{'events','expected_policy_root','minimum'},
 'profiles':set(),'profile-assess':{'name','value'},
 'record-assess':{'kind','value','expected'},
 'integrations':set(),'handoff':{'target','references'},
 'native-read':{'name','arguments'}}


def capabilities():
    return {'schema':'mmc.capabilities.t4','distribution_version':VERSION,'revision':REVISION,
            'contract_root':CONTRACT_ROOT,'operations':[{'name':k,'arguments':sorted(v),'effects':'NONE'} for k,v in sorted(OPERATIONS.items())],
            'host_only':['AgentHost.admit','ReadSession.read','FileCollector.collect','SQLiteCollector.collect','HttpCollector.collect','LocalExport.commit','Registry.qualify'],
            'collectors':collectors.descriptors(),'integrations':integrations.manifest(),
            'effects':'NOT_EXECUTED',**BOUNDARY}


def dispatch(request):
    canonical(request,limit=MAX_INPUT);closed(request,{'schema','operation','arguments'})
    require(request['schema']=='mmc.request.t4','MMC_T4_ABI_SCHEMA')
    op=request['operation'];require(type(op) is str and op in OPERATIONS,'MMC_T4_ABI_OPERATION')
    a=request['arguments'];closed(a,OPERATIONS[op])
    try:
        if op=='capabilities':return capabilities()
        if op=='inspect':
            s=views.validate_snapshot(a['snapshot'])
            return {'schema':'mmc.inspection.t4','snapshot_root':digest('snapshot',s),'scope':s['plan']['root'],
                    'evidence_label':'IMPORTED_UNVERIFIED','observations':len(s['records']),'reader_context':'NOT_SELECTED','effects':'NOT_EXECUTED',**BOUNDARY}
        if op=='assess':return views.assess_view(a['snapshot'],a['reader'])
        if op=='replay':return views.replay_view(a['snapshot'],a['reader'],a['candidate'])
        if op=='compare':return views.compare_views(**a)
        if op=='work-order':return work.make_work_order(a['snapshot'],a['reader'],a['claim'],a['allowed_reads'],a['ttl'])
        if op=='review-submission':return work.review_submission(a['snapshot'],a['reader'],a['work_order'],a['submission'],expected_work_root=a['expected_work_root'])
        if op=='journal':return views.journal_view(**a)
        if op=='profiles':return {'schema':'mmc.profiles.t4','profiles':[extensions.descriptor(x) for x in ('residency','jobs')],**BOUNDARY}
        if op=='profile-assess':return extensions.assess_extension(**a)
        if op=='record-assess':return collectors.assess_record(**a)
        if op=='integrations':return {'schema':'mmc.integrations.t4','bindings':integrations.manifest(),**BOUNDARY}
        if op=='handoff':return integrations.handoff(a['target'],a['references'])
        if op=='native-read':return integrations.native_read(**a)
    except MMCError:raise
    except (KeyError,TypeError,ValueError,IndexError,AttributeError,RecursionError) as exc:
        raise MMCError('MMC_T4_INPUT_INVALID',detail=type(exc).__name__) from exc
    raise MMCError('MMC_T4_ABI_OPERATION')
