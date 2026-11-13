"""Check manually authored terminal outcomes, not regenerated reference answers."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json,canonical,require,sha
from mosaic_mmc_t5 import run_scenario
from mosaic_mmc_t5.foundry import inspect_result

def compare(case,result):
    inspect_result(result,expected_root=result['root'])
    b=result['body'];e=case['expected']
    require(b['case']==case['id'] and b['scenario']==case['scenario'] and type(b['seed']) is int and b['seed']==case['seed'],'MMC_T5_VECTOR_SCOPE')
    selected={k:b[k] for k in ('primary_transitions_completed','target_effects','status','production_evidence','authority_effect')}
    require(canonical(selected)==canonical({k:e[k] for k in selected}),'MMC_T5_VECTOR_MISMATCH')
    require(set(e['required_milestones'])<=set(b['milestones']),'MMC_T5_VECTOR_MILESTONES')
    require(canonical({k:b['final_targets'][k]['state'] for k in e['terminal_states']})==canonical(e['terminal_states']),'MMC_T5_VECTOR_STATE')
    return {'id':case['id'],'status':'PASS'}

def check(scenario_dir=None):
    corpus=read_json(ROOT/'interop/t5-known-answers.json');lock=read_json(ROOT/'provenance/turn5/VECTOR-LOCK.json')
    require(lock['sha256']==sha(ROOT/'interop/t5-known-answers.json') and lock['cases']==len(corpus['cases']),'MMC_T5_VECTOR_LOCK')
    rows=[]
    for c in corpus['cases']:
        r=read_json(Path(scenario_dir)/(c['id']+'.json')) if scenario_dir else run_scenario(c['scenario'],seed=c['seed'])
        rows.append(compare(c,r))
    return {'schema':'mmc.vector-results.t5','status':'PASS','cases':rows,'oracle':corpus['oracle'],
            'independent_implementation':False,'authority_effect':'NONE'}
if __name__=='__main__':print(canonical(check()).decode())
