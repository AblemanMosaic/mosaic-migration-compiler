"""Reference/test mapping for delivery requirements; measurement requirements remain open."""
from pathlib import Path
import ast
from tools.common import ROOT,read_json,sha,canonical,require,source_snapshot
from tools_t6.audit import freeze,check_mapping

def check(tests_path=None):
    freeze();m=check_mapping();b=read_json(ROOT/'model/release-t6/REALIZATION-BINDING.json')
    require(b['schema']=='mmc.release-realization.t6' and b['authority_effect']=='NONE','MMC_T6_MODEL_FIELDS')
    for row in b['files']:require(sha(ROOT/row['path'])==row['sha256'],'MMC_T6_MODEL_FILE',row['path'])
    registry=read_json(ROOT/'provenance/turn6/TEST-REGISTRY.json')['tests']
    if tests_path:
        r=read_json(tests_path);require(r['source_root']==source_snapshot()['root'],'MMC_T6_MODEL_TEST_SOURCE')
        require(canonical(r['tests'])==canonical([{'id':i,'status':'PASS'} for i in registry]),'MMC_T6_MODEL_TESTS')
    mapping=read_json(ROOT/'provenance/turn6/REQUIREMENT-MAP.json')['requirements']
    for ob in mapping:require(all(t in registry for t in ob['tests']),'MMC_T6_MODEL_TEST_REFERENCE')
    for row in b['symbols']:
        names={n.name for n in ast.walk(ast.parse((ROOT/row['path']).read_text('utf8'))) if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        require(row['name'] in names,'MMC_T6_MODEL_SYMBOL')
    return {'status':'PASS_REFERENCE_AND_TRACEABILITY','mapped_requirements':6,'study_not_performed':2,
            'tests':'CHECKED' if tests_path else 'NOT_CHECKED','semantic_equivalence_proof':'NOT_ESTABLISHED','authority_effect':'NONE'}
