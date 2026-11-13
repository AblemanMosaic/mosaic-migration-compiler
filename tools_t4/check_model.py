"""Mechanical T4 requirement/source/execution correspondence. Not a refinement proof."""
import ast,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json,sha,verify_freeze,canonical,require,source_snapshot
from mosaic_mmc_t4.common import digest,CONTRACT_ROOT

def check(tests_path=None):
    verify_freeze()
    c=read_json(ROOT/'model/interfaces-t4/CONTRACT.json');pin=read_json(ROOT/'model/interfaces-t4/COMMITMENT.json')
    require(pin['sha256']==CONTRACT_ROOT and digest('contract',c)==CONTRACT_ROOT,'MMC_T4_MODEL_PIN')
    require((ROOT/'src/mosaic_mmc_t4/data/CONTRACT.json').read_bytes()==(ROOT/'model/interfaces-t4/CONTRACT.json').read_bytes(),'MMC_T4_CONTRACT_COPY')
    b=read_json(ROOT/'model/interfaces-t4/REALIZATION-BINDING.json');require(b['contract_root']==CONTRACT_ROOT,'MMC_T4_REALIZATION_MODEL')
    listed=[]
    for row in b['files']:
        require(sha(ROOT/row['path'])==row['sha256'],'MMC_T4_REALIZATION_HASH',row['path']);listed.append(row['path'])
    require(len(listed)==len(set(listed)),'MMC_T4_BINDING_DUPLICATE')
    expected={r['id'] for r in read_json(ROOT/'constitution/REQUIREMENTS.json')['requirements'] if r['capability_layer']=='T4'}
    require({o['requirement'] for o in b['obligations']}==expected and len(b['obligations'])==len(expected),'MMC_T4_MODEL_COVERAGE')
    registry=read_json(ROOT/'provenance/turn4/TEST-REGISTRY.json');executed=None
    if tests_path:
        record=read_json(Path(tests_path));require(record['source_root']==source_snapshot()['root'],'MMC_T4_MODEL_TEST_SOURCE')
        require([r['id'] for r in record['tests']]==registry['tests'],'MMC_T4_MODEL_TEST_COVERAGE');executed={r['id']:r['status'] for r in record['tests']}
    for ob in b['obligations']:
        require(ob['tests'] and all(t in registry['tests'] for t in ob['tests']),'MMC_T4_MODEL_TEST_REFERENCE')
        require(ob['symbols'],'MMC_T4_MODEL_SYMBOL_REFERENCE')
        for s in ob['symbols']:
            require(s['path'] in listed,'MMC_T4_MODEL_SOURCE_UNBOUND');names={n.name for n in ast.walk(ast.parse((ROOT/s['path']).read_text())) if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))}
            require(s['name'] in names,'MMC_T4_MODEL_SYMBOL_REFERENCE',s['path'])
        if executed:require(all(executed[t]=='PASS' for t in ob['tests']),'MMC_T4_MODEL_TEST_NOT_PASS')
    return {'schema':'mmc.model-check.t4','status':'PASS_REFERENCE_AND_TRACEABILITY','obligations':len(expected),'contract_root':CONTRACT_ROOT,'tests':'CHECKED' if tests_path else 'NOT_CHECKED','semantic_equivalence_proof':'NOT_ESTABLISHED','native_pippi':'NOT_BOUND','requirement_W11_R04':'PARTIAL_NATIVE_HOST_UNAVAILABLE','authority_effect':'NONE'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tests');a=p.parse_args();print(canonical(check(a.tests)).decode())
