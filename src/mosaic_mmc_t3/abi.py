"""Read-only T3 data interface. No filesystem paths, key loading or effect methods."""
from .common import *
from .courts import evaluate_evidence,replay_evidence,assess_authority,make_plan
from .statements import verify,validate_policy

OPERATIONS={'capabilities':set(),'plan':{'bundle','policy'},'verify-statement':{'record'},'evidence':{'plan','policy','migration','transition','records','time','floor','revoked'},'replay':{'plan','policy','migration','transition','records','time','candidate','floor','revoked'},'authority':{'request','policy','records','time','revoked'}}

def dispatch(request):
    canonical(request,limit=2*1024*1024);closed(request,{'schema','operation','arguments'})
    require(request['schema']=='mmc.request.t3','MMC_T3_ABI_SCHEMA')
    op=request['operation'];require(type(op) is str and op in OPERATIONS,'MMC_T3_ABI_OPERATION');a=request['arguments'];closed(a,OPERATIONS[op])
    if op=='capabilities':return {'schema':'mmc.capabilities.t3','operations':sorted(OPERATIONS),'effect_adapter':'HOST_SELECTED_PYTHON_V1','adapter_profiles':['SIMULATED_LOCAL_SQLITE','DISPOSABLE_LOCAL_SQLITE','SQLITE_TABLE_MIGRATION'],'production_adapter':'NOT_SHIPPED','signatures':'ECDSA-P256-SHA256-DER-LOW-S','contract_root':CONTRACT_ROOT,**BOUNDARY}
    if op=='plan':return make_plan(**a)
    if op=='verify-statement':return {'schema':'mmc.verified-statement.t3','body':verify(a['record']),'recognition':'NOT_CHECKED',**BOUNDARY}
    if op=='evidence':return evaluate_evidence(**a)
    if op=='replay':return replay_evidence(**a)
    return assess_authority(**a)
