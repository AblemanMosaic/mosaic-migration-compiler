"""Pinned profile dispatch and exact evaluation replay, with no effect authority."""
from .common import canonical,clone,digest,realization_identity,require,BOUNDARY
from .registry import resolve,profile_reference
from . import profiles

def assess_profile(ref,record):
    name=resolve(ref)
    handler={'identity':profiles.identity,'storage':profiles.storage,'policy':profiles.policy,'workload':profiles.workload}[name]
    result=handler(record)
    body={'schema':'mmc.assessment.t2','profile_ref':clone(ref),'request_root':digest('request',record),'evaluator':realization_identity(),'result':result,**BOUNDARY}
    return {'body':body,'root':digest('report',body)}

def replay_assessment(ref,record,receipt):
    actual=assess_profile(ref,record)
    require(canonical(actual)==canonical(receipt),'MMC_T2_REPLAY_MISMATCH')
    return {'schema':'mmc.assessment-replay.t2','status':'MATCH_EXACT_RECOMPUTATION','root':actual['root'],**BOUNDARY}
