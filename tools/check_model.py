"""Read-only reference/symbol/test traceability. Does not prove semantic equivalence."""
from __future__ import annotations
import argparse,ast
from pathlib import Path
try:from .common import ROOT,read_json,sha,verify_freeze,canonical,require,source_snapshot
except ImportError:from common import ROOT,read_json,sha,verify_freeze,canonical,require,source_snapshot
from mosaic_mmc import digest
from mosaic_mmc._pins import PROFILE_ROOT,PROGRAM_ROOT


def check(root:Path=ROOT,*,tests_path:Path|None=None)->dict:
    verify_freeze(root)
    contract=read_json(root/'model/foundation/CONTRACT.json')
    commitment=read_json(root/'model/foundation/COMMITMENT.json')
    require(commitment=={'domain':'foundation-profile','sha256':PROFILE_ROOT} and digest('foundation-profile',contract)==PROFILE_ROOT,'MMC_MODEL_PIN')
    for row in contract['references']:
        require(sha(root/row['path'])==row['sha256'],'MMC_MODEL_REFERENCE',row['path'])
    binding=read_json(root/'model/foundation/REALIZATION-BINDING.json')
    require(binding['program_root']==PROGRAM_ROOT and binding['profile_root']==PROFILE_ROOT,'MMC_REALIZATION_MODEL')
    for row in binding['files']:require(sha(root/row['path'])==row['sha256'],'MMC_REALIZATION_HASH',row['path'])
    wanted={r['id'] for r in read_json(root/'constitution/REQUIREMENTS.json')['requirements'] if r['capability_layer']=='T1'}
    require({r['requirement'] for r in binding['obligations']}==wanted and len(binding['obligations'])==len(wanted),'MMC_MODEL_OBLIGATION_COVERAGE')
    registry=read_json(root/'provenance/TEST-REGISTRY.json')
    test_results=None
    if tests_path is not None:
        record=read_json(tests_path)
        require(record['source_root']==source_snapshot(root)['root'],'MMC_MODEL_TEST_SOURCE')
        require([x['id'] for x in record['tests']]==registry['tests'],'MMC_MODEL_TEST_IDENTITIES')
        test_results={x['id']:x['status'] for x in record['tests']}
    for row in binding['obligations']:
        require(row['tests'] and all(t in registry['tests'] for t in row['tests']),'MMC_MODEL_TEST_REFERENCE')
        for symbol in row['symbols']:
            p=root/symbol['path'];tree=ast.parse(p.read_text('utf-8'))
            names={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
            require(symbol['name'] in names,'MMC_MODEL_SYMBOL',symbol['path'],symbol['name'])
        if test_results is not None:require(all(test_results[t]=='PASS' for t in row['tests']),'MMC_MODEL_TEST_NOT_PASS')
    return {'schema':'mmc.model-check.t1','status':'PASS_REFERENCE_AND_TRACEABILITY','obligations':len(wanted),
            'full_program_requirements':84,'program_root':PROGRAM_ROOT,'profile_root':PROFILE_ROOT,
            'tests':'CHECKED' if test_results is not None else 'NOT_CHECKED','authority_effect':'NONE',
            'semantic_equivalence_proof':'NOT_ESTABLISHED'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tests');a=p.parse_args();print(canonical(check(tests_path=Path(a.tests) if a.tests else None)).decode())
