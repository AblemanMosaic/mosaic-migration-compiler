"""Read-only T5 contract/realization/test traceability; never evidence of equivalence."""
from pathlib import Path
import sys,hashlib,ast,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json,canonical,sha,verify_freeze,source_snapshot,require
from mosaic_mmc_t5._pins import CONTRACT_ROOT

def check(tests_path=None):
    verify_freeze();p=ROOT/'model/qualification-t5/CONTRACT.json';c=read_json(p)
    require(hashlib.sha256(b'MMC/T5/CONTRACT\0'+p.read_bytes()).hexdigest()==CONTRACT_ROOT,'MMC_T5_CONTRACT_PIN')
    require((ROOT/'src/mosaic_mmc_t5/data/CONTRACT.json').read_bytes()==p.read_bytes(),'MMC_T5_CONTRACT_COPY')
    require(read_json(ROOT/'model/qualification-t5/COMMITMENT.json')['sha256']==CONTRACT_ROOT,'MMC_T5_COMMITMENT')
    b=read_json(ROOT/'model/qualification-t5/REALIZATION-BINDING.json')
    require(b['contract_root']==CONTRACT_ROOT,'MMC_T5_MODEL_ROOT')
    listed=set()
    for row in b['files']:
        require(row['path'] not in listed and sha(ROOT/row['path'])==row['sha256'],'MMC_T5_MODEL_FILE',row['path']);listed.add(row['path'])
    expected={r['id'] for r in read_json(ROOT/'constitution/REQUIREMENTS.json')['requirements'] if r['capability_layer']=='T5'}
    require(len(b['obligations'])==len(expected) and {r['requirement'] for r in b['obligations']}==expected,'MMC_T5_MODEL_COVERAGE')
    registry=read_json(ROOT/'provenance/turn5/TEST-REGISTRY.json');executed=None
    if tests_path:
        r=read_json(tests_path);require(r['source_root']==source_snapshot()['root'],'MMC_T5_MODEL_TEST_SOURCE')
        require([x['id'] for x in r['tests']]==registry['tests'],'MMC_T5_MODEL_TEST_IDENTITIES');executed={x['id']:x['status'] for x in r['tests']}
    for ob in b['obligations']:
        require(ob['symbols'] and ob['tests'] and all(t in registry['tests'] for t in ob['tests']),'MMC_T5_MODEL_BINDING')
        for s in ob['symbols']:
            require(s['path'] in listed,'MMC_T5_MODEL_SYMBOL_UNBOUND')
            names={n.name for n in ast.walk(ast.parse((ROOT/s['path']).read_text())) if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))}
            require(s['name'] in names,'MMC_T5_MODEL_SYMBOL')
        if executed:require(all(executed[x]=='PASS' for x in ob['tests']),'MMC_T5_MODEL_TEST_FAILURE')
    return {'schema':'mmc.model-check.t5','status':'PASS_REFERENCE_AND_TRACEABILITY','obligations':8,
            'contract_root':CONTRACT_ROOT,'tests':'CHECKED' if tests_path else 'NOT_CHECKED',
            'semantic_equivalence_proof':'NOT_ESTABLISHED','authority_effect':'NONE',
            'external_platform_and_study_gates':'NOT_ESTABLISHED'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tests');a=p.parse_args();print(canonical(check(a.tests)).decode())
