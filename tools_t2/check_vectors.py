"""Full frozen model reports. Expectations are reference-assisted, not independent proof."""
import sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json,canonical,require
from mosaic_mmc import MMCError
from mosaic_mmc_t2 import profiles
from mosaic_mmc_t2.planner import plan
from mosaic_mmc_t2.lifecycle import assess_retirement,assess_routes,assess_lifecycle

def invoke(v):
    op=v['operation'];a=v['arguments']
    try:
        if op in ('identity','storage','policy','workload'):return {'result':getattr(profiles,op)(a['record'])}
        if op=='plan':return {'result':plan(a['model'],a['planning'])}
        if op=='retirement':return {'result':assess_retirement(a['model'],a['record'])}
        if op=='routes':return {'result':assess_routes(a['model'],a['record'])}
        if op=='lifecycle':return {'result':assess_lifecycle(a['record'])}
        raise ValueError('unknown frozen vector operation')
    except MMCError as exc:return {'refusal':exc.code}

def check():
    corpus=read_json(ROOT/'interop/t2-known-answers.json');rows=[]
    for v in corpus['cases']:
        actual=invoke(v);require(canonical(actual)==canonical(v['expected']),'MMC_T2_VECTOR_MISMATCH',v['id']);rows.append({'id':v['id'],'status':'PASS'})
    return {'schema':'mmc.vector-results.t2','status':'PASS','cases':rows,'oracle':'AUTHORED_STATUS_EXPECTATIONS_REFERENCE_ASSISTED_FULL_RECORDS','independent_implementation':False,'authority_effect':'NONE'}
if __name__=='__main__':print(canonical(check()).decode())
