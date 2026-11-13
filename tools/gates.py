"""Local evidence eligibility only. Does not provide native P/PPI admission or authentication."""
from __future__ import annotations
import re
try:from .common import ROOT,read_json,require,canonical
except ImportError:from common import ROOT,read_json,require,canonical
from mosaic_mmc.contracts import contract
from mosaic_mmc._pins import PROGRAM_ROOT

LEG_NAMES={'freeze','unit_and_acceptance','model_traceability','compiler_vectors','examples','clean_extraction','installed_wheel','archive_closure'}

def assess_turn1(record:object,registry:dict,*,expected_source:str)->dict:
    require(type(record) is dict and set(record)=={'schema','source_root','program_root','tests','legs','native_pippi','authority_effect','independent_study'},'MMC_GATE_FIELDS')
    require(record['schema']=='mmc.qualification-input.t1' and record['program_root']==PROGRAM_ROOT,'MMC_GATE_SCHEMA')
    require(type(expected_source) is str and re.fullmatch('[0-9a-f]{64}',expected_source) is not None and record['source_root']==expected_source,'MMC_GATE_SOURCE')
    require(record['native_pippi']=='NOT_BOUND' and record['authority_effect']=='NONE' and record['independent_study']=='NOT_PERFORMED','MMC_GATE_OVERCLAIM')
    tests=record['tests'];require(type(tests) is list,'MMC_GATE_TESTS')
    seen={}
    for row in tests:
        require(type(row) is dict and set(row)=={'id','status'} and type(row['id']) is str and row['id'] not in seen,'MMC_GATE_TEST_IDENTITIES')
        require(row['status'] in ('PASS','FAIL','ERROR','SKIP'),'MMC_GATE_TEST_STATUS')
        seen[row['id']]=row['status']
    require(set(seen)==set(registry['tests']),'MMC_GATE_TEST_COVERAGE')
    require(all(s=='PASS' for s in seen.values()),'MMC_GATE_TEST_FAILURE')
    legs=record['legs'];require(type(legs) is dict and set(legs)==LEG_NAMES,'MMC_GATE_LEGS')
    for name,leg in legs.items():
        require(type(leg) is dict and set(leg)=={'status','exit_code','evidence_sha256'} and leg['status']=='PASS' and type(leg['exit_code']) is int and leg['exit_code']==0 and type(leg['evidence_sha256']) is str and re.fullmatch('[0-9a-f]{64}',leg['evidence_sha256']) is not None,'MMC_GATE_LEG_INVALID',name)
    cases=contract('cases')['cases'];due={c['id'] for c in cases if c['gate']=='T1'}
    require(set(registry['acceptance'])==due,'MMC_GATE_CASE_COVERAGE')
    for case,ids in registry['acceptance'].items():
        require(type(ids) is list and ids and all(i in seen and seen[i]=='PASS' for i in ids),'MMC_GATE_CASE_TEST',case)
    return {'schema':'mmc.turn-gate.t1','status':'PASS_SCOPED_T1_LOCAL_ENGINEERING',
            'source_root':expected_source,'program_root':PROGRAM_ROOT,'due_cases':len(due),'passed_due_cases':len(due),
            'all_program_cases':len(cases),'remaining_not_run':len(cases)-len(due),
            'case_dispositions':{c['id']:('PASS_SCOPED' if c['id'] in due else 'NOT_RUN') for c in cases},
            'native_pippi':'NOT_BOUND','authority_effect':'NONE','product_release':'NOT_CLEARED',
            'independent_study':'NOT_PERFORMED','signature':'NOT_SIGNED',
            'claim_ceiling':'UNSIGNED_LOCAL_EVIDENCE_METADATA_REQUIRES_TRUSTED_RUNNER_AND_BOUND_FILES'}
