from mosaic_mmc.model import closed
from .common import canonical,require,BOUNDARY
from mosaic_mmc.errors import MMCError
from .registry import capabilities
from .evaluation import assess_profile,replay_assessment
from .planner import plan
from .lifecycle import assess_retirement,assess_routes,assess_lifecycle
from .compiler import compile_domain,verify_compilation

OPS={
 'profiles':(set(),lambda a:capabilities()),
 'assess':({'profile_ref','record'},lambda a:assess_profile(a['profile_ref'],a['record'])),
 'replay':({'profile_ref','record','receipt'},lambda a:replay_assessment(a['profile_ref'],a['record'],a['receipt'])),
 'plan':({'model','planning'},lambda a:plan(a['model'],a['planning'])),
 'retirement':({'model','record'},lambda a:assess_retirement(a['model'],a['record'])),
 'routes':({'model','record'},lambda a:assess_routes(a['model'],a['record'])),
 'lifecycle':({'record'},lambda a:assess_lifecycle(a['record'])),
 'compile':({'bundle'},lambda a:compile_domain(a['bundle'])),
 'verify-compilation':({'bundle','candidate','expected_model_root'},lambda a:verify_compilation(a['bundle'],a['candidate'],expected_model_root=a['expected_model_root']))}

def dispatch(request):
    canonical(request,limit=8*1024*1024);closed(request,{'schema','operation','arguments'},'$')
    require(request['schema']=='mmc.request.t2','MMC_T2_SCHEMA')
    op=request['operation'];require(type(op) is str and op in OPS,'MMC_T2_OPERATION_UNSUPPORTED')
    keys,fn=OPS[op];closed(request['arguments'],keys,'$.arguments');result=fn(request['arguments'])
    response={'schema':'mmc.response.t2','operation':op,'ok':True,'result':result,**BOUNDARY};canonical(response);return response
