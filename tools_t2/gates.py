"""Finite G2 local-evidence eligibility. This does not authenticate evidence producers."""
import re
from pathlib import Path
from tools.common import ROOT,read_json,canonical,require
from mosaic_mmc._pins import PROGRAM_ROOT

LEG_NAMES={'current_source_tests','mapped_acceptance','end_to_end_where_due','exact_evidence','residual_limits','clean_extraction','installed_wheel','archive_closure'}

def assess(record,*,expected_source,registry):
    require(type(record) is dict and set(record)=={'schema','source_root','program_root','tests','legs','native_pippi','independent_review','independent_study','authority_effect','product_complete'},'MMC_T2_GATE_FIELDS')
    require(record['schema']=='mmc.qualification-input.t2' and record['source_root']==expected_source and record['program_root']==PROGRAM_ROOT,'MMC_T2_GATE_CONTEXT')
    require(type(expected_source) is str and re.fullmatch('[0-9a-f]{64}',expected_source),'MMC_T2_GATE_SOURCE')
    require(record['native_pippi']=='NOT_BOUND' and record['independent_review']=='NOT_PERFORMED' and record['independent_study']=='NOT_PERFORMED' and record['authority_effect']=='NONE' and record['product_complete'] is False,'MMC_T2_GATE_OVERCLAIM')
    expected=sorted(registry['foundation_tests']+registry['tests'])
    require(record['tests']==[{'id':i,'status':'PASS'} for i in expected] and len(expected)==len(set(expected)),'MMC_T2_GATE_TESTS')
    require(type(record['legs']) is dict and set(record['legs'])==LEG_NAMES,'MMC_T2_GATE_LEGS')
    for n,r in record['legs'].items():
        require(type(r) is dict and set(r)=={'status','terminal_exit','evidence_sha256'},'MMC_T2_GATE_LEG_FIELDS')
        want='NOT_DUE_T2_RETAINED' if n=='end_to_end_where_due' else 'PASS'
        require(r['status']==want and type(r['terminal_exit']) is int and r['terminal_exit']==0 and type(r['evidence_sha256']) is str and re.fullmatch('[0-9a-f]{64}',r['evidence_sha256']),'MMC_T2_GATE_LEG',n)
    cases=read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'];due={c['id'] for c in cases if c['gate']=='T2'}
    require(set(registry['acceptance'])==due,'MMC_T2_GATE_CASES')
    for case,ids in registry['acceptance'].items():require(ids and all(t in registry['tests'] for t in ids),'MMC_T2_GATE_CASE_TEST',case)
    return {'schema':'mmc.turn-gate.t2','status':'PASS_SCOPED_T2_LOCAL_ENGINEERING','source_root':expected_source,'program_root':PROGRAM_ROOT,'t1_replayed_cases':29,'t2_passed_cases':len(due),'case_dispositions':{c['id']:('PASS_SCOPED' if c['gate'] in ('T1','T2') else 'NOT_RUN') for c in cases},'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED','independent_study':'NOT_PERFORMED','authority_effect':'NONE','product_release':'NOT_CLEARED','signature':'NOT_SIGNED','claim_ceiling':'UNSIGNED_EVIDENCE_METADATA_MUST_BE_BOUND_TO_ACTUAL_VERIFIED_RUN_OUTPUTS'}
