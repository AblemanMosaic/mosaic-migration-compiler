"""Closed read-only interface. Source data cannot supply module names or effects."""
from __future__ import annotations
from .codec import canonical, digest
from .contracts import capabilities, program_inspect
from .model import validate_model, closed
from .compiler import compile_model, verify_compilation
from .errors import MMCError, require


def dispatch(request: object) -> dict:
    canonical(request,limit=8*1024*1024)
    closed(request,{'schema','operation','arguments'},'$')
    require(request['schema']=='mmc.request.t1','MMC_SCHEMA_UNSUPPORTED')
    op=request['operation'];args=request['arguments']
    require(type(op) is str,'MMC_OPERATION_UNSUPPORTED')
    if op=='model-validate':
        closed(args,{'model'},'$.arguments');m=validate_model(args['model'])
        result={'schema':'mmc.model-validation.t1','status':'VALID_STRUCTURAL_MODEL',
                'model_root':digest('canonical-model',m),'normalized_model':m,
                'semantic_domain_validation':'NOT_PERFORMED','authority_effect':'NONE'}
    elif op=='compile':
        closed(args,{'model'},'$.arguments');result=compile_model(args['model'])
    elif op=='verify-ir':
        closed(args,{'model','compilation','expected_model_root'},'$.arguments')
        result=verify_compilation(args['model'],args['compilation'],expected_model_root=args['expected_model_root'])
    elif op=='capabilities':
        closed(args,set(),'$.arguments');result=capabilities()
    elif op=='program-inspect':
        closed(args,set(),'$.arguments');result=program_inspect()
    else:raise MMCError('MMC_OPERATION_UNSUPPORTED','$.operation',op[:128])
    response={'schema':'mmc.response.t1','operation':op,'ok':True,'result':result}
    canonical(response)
    return response
