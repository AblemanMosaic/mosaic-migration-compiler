"""Read-only T2 reference and executed-test traceability. No program equivalence claim."""
import ast,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json,sha,verify_freeze,canonical,require,source_snapshot
from mosaic_mmc_t2.common import digest
from mosaic_mmc_t2._pins import CONTRACT_ROOT

def check(tests_path=None):
    verify_freeze()
    c=read_json(ROOT/'model/domain-t2/CONTRACT.json');pin=read_json(ROOT/'model/domain-t2/COMMITMENT.json')
    require(pin=={'domain':'contract','sha256':CONTRACT_ROOT} and digest('contract',c)==CONTRACT_ROOT,'MMC_T2_MODEL_PIN')
    for row in c['references']:require(sha(ROOT/row['path'])==row['sha256'],'MMC_T2_MODEL_REFERENCE',row['path'])
    b=read_json(ROOT/'model/domain-t2/REALIZATION-BINDING.json')
    require(b['contract_root']==CONTRACT_ROOT,'MMC_T2_REALIZATION_MODEL')
    for row in b['files']:require(sha(ROOT/row['path'])==row['sha256'],'MMC_T2_REALIZATION_HASH',row['path'])
    expected={r['id'] for r in read_json(ROOT/'constitution/REQUIREMENTS.json')['requirements'] if r['capability_layer']=='T2'}
    require({o['requirement'] for o in b['obligations']}==expected and len(b['obligations'])==len(expected),'MMC_T2_OBLIGATION_COVERAGE')
    reg=read_json(ROOT/'provenance/turn2/TEST-REGISTRY.json');executed=None
    if tests_path:
        rec=read_json(Path(tests_path));require(rec['source_root']==source_snapshot()['root'],'MMC_T2_MODEL_TEST_SOURCE')
        require([r['id'] for r in rec['tests']]==reg['tests'],'MMC_T2_MODEL_TEST_COVERAGE');executed={r['id']:r['status'] for r in rec['tests']}
    for ob in b['obligations']:
        require(ob['tests'] and all(t in reg['tests'] for t in ob['tests']),'MMC_T2_TEST_REFERENCE')
        for s in ob['symbols']:
            names={n.name for n in ast.walk(ast.parse((ROOT/s['path']).read_text())) if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))}
            require(s['name'] in names,'MMC_T2_SYMBOL_REFERENCE',s['path'])
        if executed:require(all(executed[t]=='PASS' for t in ob['tests']),'MMC_T2_TEST_NOT_PASS')
    return {'schema':'mmc.model-check.t2','status':'PASS_REFERENCE_AND_TRACEABILITY','obligations':len(expected),'contract_root':CONTRACT_ROOT,'tests':'CHECKED' if tests_path else 'NOT_CHECKED','semantic_equivalence_proof':'NOT_ESTABLISHED','authority_effect':'NONE'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tests');a=p.parse_args();print(canonical(check(a.tests)).decode())
