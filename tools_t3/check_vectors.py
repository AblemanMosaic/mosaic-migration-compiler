"""Full-result frozen data-ABI vectors. Never regenerate expectations while checking."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json,canonical,require
from mosaic_mmc import MMCError
from mosaic_mmc_t3.abi import dispatch

def invoke(request):
    try:return {'result':dispatch(request)}
    except MMCError as e:return {'refusal':e.code}

def check():
    corpus=read_json(ROOT/'interop/t3-known-answers.json');rows=[]
    for c in corpus['cases']:
        actual=invoke(c['request']);require(canonical(actual)==canonical(c['expected']),'MMC_T3_VECTOR_MISMATCH',c['id']);rows.append({'id':c['id'],'status':'PASS'})
    return {'schema':'mmc.vector-results.t3','status':'PASS','cases':rows,'oracle':'AUTHORED_STATUSES_REFERENCE_ASSISTED_EXACT_RESULTS','independent_implementation':False,'authority_effect':'NONE'}
if __name__=='__main__':print(canonical(check()).decode())
