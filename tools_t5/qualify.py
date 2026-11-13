"""Bounded local qualification, not a native P/PPI interpreter or approval authority."""
from pathlib import Path
import argparse, io, os, platform, sqlite3, subprocess, sys, time, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import canonical,read_json,save_json,sha,verify_source,verify_freeze,require,source_snapshot
from tools.qualify import RecordedResult,flattened
from mosaic_mmc import MMCError

GROUPS={'t1':'tests','t2':'tests_t2','t3':'tests_t3','t4':'tests_t4','t5':'tests_t5'}
EXAMPLES=['examples/compile_and_inspect.py','examples/blocked_retirement.py','examples/t2/domain_profiles.py','examples/t2/retirement_progress.py','examples/t2/coexistence_planning.py','examples/t3/operational_recovery.py','examples/t3/compensation_and_floors.py','examples/t4/agent_cycle.py','examples/t4/extensions_and_collectors.py','examples/t4/workbench_review.py','examples/t5/full_migration.py','examples/t5/fault_and_recovery.py']
OUTPUTS={
 'tests':{'collected.json','tests.json'}|{f'{g}-tests.{ext}' for g in GROUPS for ext in ('json','txt')}|{g+'-PART.json' for g in GROUPS},
 'examples':{'examples.json'}|{f'example-{i}.{ext}' for i in range(len(EXAMPLES)) for ext in ('stdout.txt','stderr.txt')},
 'scenarios':{'summary.json'}|{f'AC-E2E-{i:02d}.json' for i in range(1,11)},
 'audit':{'audit.json','preservation.json'}|{f'{kind}-{g}.json' for kind in ('model','vectors') for g in GROUPS}}

def environment():
    from importlib.metadata import version
    return {'python':platform.python_version(),'implementation':platform.python_implementation(),
      'system':platform.system(),'machine':platform.machine(),'executable':sys.executable,
      'sqlite':sqlite3.sqlite_version,'cryptography':version('cryptography'),'jsonschema':version('jsonschema'),
      'source_directory':str(ROOT),'invocation_cwd':str(Path.cwd()),'subprocess_import_path':os.environ.get('PYTHONPATH',''),'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED'}

def registry():return read_json(ROOT/'provenance/turn5/TEST-REGISTRY.json')
def expected_ids():
    r=registry();return {'t1':r['foundation_tests'],'t2':r['domain_tests'],'t3':r['operational_tests'],'t4':r['interface_tests'],'t5':r['tests']}
def exact(a,b,code):require(canonical(a)==canonical(b),code)
def counts(n):return {'PASS':n,'FAIL':0,'ERROR':0,'SKIP':0}

def record(out,phase,source,result,code):
    require({p.name for p in out.iterdir()}==OUTPUTS[phase],'MMC_T5_STAGE_CLOSURE')
    stage={'schema':'mmc.qualification-stage.t5','phase':phase,'source_root':source,'environment':environment(),
      'outputs':[{'path':n,'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in sorted(OUTPUTS[phase])],
      'result':result,'terminal_exit':code,'authority_effect':'NONE','signature':'NOT_SIGNED'}
    save_json(out/'STAGE.json',stage);return stage

def run_test_group(out,source,group):
    verify_source(ROOT,source);require(group in GROUPS,'MMC_T5_TEST_GROUP')
    expected=expected_ids()[group];names=[group+'-tests.json',group+'-tests.txt',group+'-PART.json']
    require(not any((out/n).exists() for n in names),'MMC_T5_TEST_PART_EXISTS')
    suite=unittest.TestLoader().discover(str(ROOT/GROUPS[group]),top_level_dir=str(ROOT))
    ids=[t.id() for t in flattened(suite)]
    require(len(ids)==len(set(ids)) and sorted(ids)==expected,'MMC_T5_COLLECTION',group)
    stream=io.StringIO();start=time.perf_counter_ns()
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult).run(suite)
    ns=time.perf_counter_ns()-start;rows=sorted(result.records,key=lambda r:r['id'])
    require([r['id'] for r in rows]==expected,'MMC_T5_EXECUTED_COVERAGE',group)
    c={k:sum(r['status']==k for r in rows) for k in ('PASS','FAIL','ERROR','SKIP')}
    save_json(out/names[0],{'schema':f'mmc.test-results.{group}','source_root':source,'elapsed_ns':ns,'tests':rows,'counts':c})
    (out/names[1]).write_text(stream.getvalue(),encoding='utf8');verify_source(ROOT,source)
    part={'schema':'mmc.test-part.t5','group':group,'source_root':source,'environment':environment(),'collected':sorted(ids),'terminal_exit':0 if c==counts(len(expected)) else 2,'counts':c,'outputs':[{'path':n,'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in names[:2]],'authority_effect':'NONE','signature':'NOT_SIGNED'}
    save_json(out/names[2],part);return part

def verify_part(out,source,group):
    part=read_json(out/(group+'-PART.json'));expected=expected_ids()[group]
    require(type(part) is dict and set(part)=={'schema','group','source_root','environment','collected','terminal_exit','counts','outputs','authority_effect','signature'},'MMC_T5_PART_FIELDS')
    require(part['schema']=='mmc.test-part.t5' and part['group']==group and part['source_root']==source and type(part['terminal_exit']) is int and part['terminal_exit']==0 and part['authority_effect']=='NONE' and part['signature']=='NOT_SIGNED','MMC_T5_PART_TERMINAL')
    exact(part['environment'],environment(),'MMC_T5_PART_CONTEXT');exact(part['collected'],expected,'MMC_T5_PART_IDENTITIES');exact(part['counts'],counts(len(expected)),'MMC_T5_PART_COUNTS')
    rows=[{'path':n,'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in (group+'-tests.json',group+'-tests.txt')]
    exact(part['outputs'],rows,'MMC_T5_PART_OUTPUTS')
    r=read_json(out/(group+'-tests.json'))
    require(type(r) is dict and set(r)=={'schema','source_root','elapsed_ns','tests','counts'},'MMC_T5_TEST_FIELDS')
    require(r['schema']==f'mmc.test-results.{group}' and r['source_root']==source and type(r['elapsed_ns']) is int and r['elapsed_ns']>=0,'MMC_T5_TEST_HEADER')
    exact(r['tests'],[{'id':x,'status':'PASS'} for x in expected],'MMC_T5_TEST_IDENTITIES')
    exact(r['counts'],counts(len(expected)),'MMC_T5_TEST_COUNTS')
    return part

def run_tests(out,source):
    verify_source(ROOT,source);all_rows=[];elapsed=0
    for group in GROUPS:
        verify_part(out,source,group);r=read_json(out/(group+'-tests.json'));all_rows+=r['tests'];elapsed+=r['elapsed_ns']
    ids=[r['id'] for r in all_rows];require(len(ids)==len(set(ids)),'MMC_T5_DUPLICATE_TEST')
    c={s:sum(r['status']==s for r in all_rows) for s in ('PASS','FAIL','ERROR','SKIP')}
    save_json(out/'tests.json',{'schema':'mmc.test-results.t5','source_root':source,'elapsed_ns':elapsed,'tests':sorted(all_rows,key=lambda r:r['id']),'counts':c})
    save_json(out/'collected.json',{'schema':'mmc.collected-tests.t5','source_root':source,'ids':sorted(ids)})
    verify_source(ROOT,source);return record(out,'tests',source,c,0 if c==counts(len(all_rows)) else 2)

def run_examples(out,source):
    verify_source(ROOT,source);runs=[]
    for i,script in enumerate(EXAMPLES):
        env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
        p=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,env=env,capture_output=True,timeout=60)
        (out/f'example-{i}.stdout.txt').write_bytes(p.stdout);(out/f'example-{i}.stderr.txt').write_bytes(p.stderr)
        runs.append({'script':script,'exit_code':p.returncode})
    save_json(out/'examples.json',{'schema':'mmc.examples.t5','source_root':source,'runs':runs})
    verify_source(ROOT,source);return record(out,'examples',source,{'runs':runs},0 if all(r['exit_code']==0 for r in runs) else 2)

def preservation():
    from tools.public_predecessor import load_public_predecessor
    record=load_public_predecessor(5,error_stage=5)
    paths=[row['path'] for row in record['rows']]
    return {'schema':'mmc.preservation.t5','status':'PASS','paths':paths,'runtime_files':sum(n.startswith('src/') for n in paths),'authority_effect':'NONE'}


def run_scenarios(out,source):
    verify_source(ROOT,source)
    from mosaic_mmc_t5 import run_scenario,catalogue
    from mosaic_mmc_t5.foundry import inspect_result
    rows=[]
    for c in catalogue():
        result=run_scenario(c['scenario'])
        inspection=inspect_result(result,expected_root=result['root'])
        save_json(out/(c['id']+'.json'),result)
        rows.append({'case':c['id'],'scenario':c['scenario'],'root':result['root'],'checks':len(result['body']['checks']),
                     'effects':result['body']['target_effects'],'status':'PASS_SCOPED_SIMULATION'})
    summary={'schema':'mmc.scenarios.t5','source_root':source,'cases':rows,'authority_effect':'NONE',
             'production_evidence':False,'productivity_claim':'NOT_ESTABLISHED'}
    save_json(out/'summary.json',summary);verify_source(ROOT,source)
    return record(out,'scenarios',source,{'cases':len(rows),'status':'PASS_SCOPED_SIMULATION'},0)

def run_audit(out,source,tests_dir):
    verify_source(ROOT,source);verify_stage(tests_dir,'tests',source);verify_stage(tests_dir.parent/'scenarios','scenarios',source)
    from tools.check_vectors import check as v1
    from tools_t2.check_vectors import check as v2
    from tools_t3.check_vectors import check as v3
    from tools_t4.check_vectors import check as v4
    from tools_t5.check_vectors import check as v5
    from tools.check_model import check as m1
    from tools_t2.check_model import check as m2
    from tools_t3.check_model import check as m3
    from tools_t4.check_model import check as m4
    from tools_t5.check_model import check as m5
    reports={'vectors-t1':v1(),'vectors-t2':v2(),'vectors-t3':v3(),'vectors-t4':v4(),'vectors-t5':v5(tests_dir.parent/'scenarios'),
      'model-t1':m1(tests_path=tests_dir/'t1-tests.json'),'model-t2':m2(tests_dir/'t2-tests.json'),
      'model-t3':m3(tests_dir/'t3-tests.json'),'model-t4':m4(tests_dir/'t4-tests.json'),'model-t5':m5(tests_dir/'t5-tests.json'),'preservation':preservation()}
    for name,value in reports.items():save_json(out/(name+'.json'),value)
    result={'status':'PASS','vectors':{g:len(reports['vectors-'+g]['cases']) for g in GROUPS},'obligations':{g:reports['model-'+g]['obligations'] for g in GROUPS},'inherited_runtime_files':reports['preservation']['runtime_files']}
    save_json(out/'audit.json',{'schema':'mmc.audit.t5','source_root':source,'result':result})
    verify_source(ROOT,source);return record(out,'audit',source,result,0)

def verify_stage(out,phase,source):
    require(phase in OUTPUTS,'MMC_T5_STAGE_PHASE');d=read_json(out/'STAGE.json')
    require(type(d) is dict and set(d)=={'schema','phase','source_root','environment','outputs','result','terminal_exit','authority_effect','signature'},'MMC_T5_STAGE_FIELDS')
    require(d['schema']=='mmc.qualification-stage.t5' and d['phase']==phase and d['source_root']==source,'MMC_T5_STAGE_IDENTITY')
    require(type(d['terminal_exit']) is int and d['terminal_exit']==0 and d['authority_effect']=='NONE' and d['signature']=='NOT_SIGNED','MMC_T5_STAGE_TERMINAL')
    env=d['environment'];actual=environment()
    require(type(env) is dict and set(env)==set(actual) and all(type(v) is str and v for v in env.values()),'MMC_T5_STAGE_CONTEXT')
    exact(env,actual,'MMC_T5_STAGE_CONTEXT')
    require(type(d['outputs']) is list and len(d['outputs'])==len(OUTPUTS[phase]),'MMC_T5_STAGE_OUTPUTS');seen=set()
    for row in d['outputs']:
        require(type(row) is dict and set(row)=={'path','bytes','sha256'} and type(row['path']) is str and row['path'] in OUTPUTS[phase] and row['path'] not in seen,'MMC_T5_STAGE_OUTPUTS')
        p=out/row['path'];require(type(row['bytes']) is int and p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'MMC_T5_STAGE_HASH');seen.add(row['path'])
    require(seen==OUTPUTS[phase] and {p.name for p in out.iterdir()}==OUTPUTS[phase]|{'STAGE.json'},'MMC_T5_STAGE_CLOSURE')
    if phase=='tests':
        for g in GROUPS:verify_part(out,source,g)
        groups=expected_ids();all_ids=sorted(sum(groups.values(),[]));require(len(all_ids)==len(set(all_ids)),'MMC_T5_DUPLICATE_TEST')
        for g,ids in [*groups.items(),('',all_ids)]:
            r=read_json(out/(f'{g}-tests.json' if g else 'tests.json'))
            require(type(r) is dict and set(r)=={'schema','source_root','elapsed_ns','tests','counts'} and r['schema']==f'mmc.test-results.{g or "t5"}' and r['source_root']==source and type(r['elapsed_ns']) is int and r['elapsed_ns']>=0,'MMC_T5_TEST_FIELDS')
            exact(r['tests'],[{'id':i,'status':'PASS'} for i in ids],'MMC_T5_TEST_IDENTITIES');exact(r['counts'],counts(len(ids)),'MMC_T5_TEST_COUNTS')
        exact(read_json(out/'collected.json'),{'schema':'mmc.collected-tests.t5','source_root':source,'ids':all_ids},'MMC_T5_COLLECTION')
        exact(d['result'],counts(len(all_ids)),'MMC_T5_STAGE_RESULT')
    elif phase=='examples':
        r={'runs':[{'script':s,'exit_code':0} for s in EXAMPLES]}
        exact(read_json(out/'examples.json'),{'schema':'mmc.examples.t5','source_root':source,**r},'MMC_T5_EXAMPLES');exact(d['result'],r,'MMC_T5_STAGE_RESULT')
    elif phase=='scenarios':
        from mosaic_mmc_t5 import catalogue
        from mosaic_mmc_t5.foundry import inspect_result
        summary=read_json(out/'summary.json');rows=[]
        for c in catalogue():
            r=read_json(out/(c['id']+'.json'));inspect_result(r,expected_root=r['root'])
            rows.append({'case':c['id'],'scenario':c['scenario'],'root':r['root'],'checks':len(r['body']['checks']),'effects':r['body']['target_effects'],'status':'PASS_SCOPED_SIMULATION'})
        exact(summary,{'schema':'mmc.scenarios.t5','source_root':source,'cases':rows,'authority_effect':'NONE','production_evidence':False,'productivity_claim':'NOT_ESTABLISHED'},'MMC_T5_SCENARIO_SUMMARY')
        exact(d['result'],{'cases':10,'status':'PASS_SCOPED_SIMULATION'},'MMC_T5_SCENARIO_RESULT')
    else:
        exact(read_json(out/'audit.json'),{'schema':'mmc.audit.t5','source_root':source,'result':d['result']},'MMC_T5_AUDIT')
        expected={'status':'PASS','vectors':{'t1':20,'t2':38,'t3':24,'t4':len(read_json(ROOT/'interop/t4-known-answers.json')['cases']),'t5':len(read_json(ROOT/'interop/t5-known-answers.json')['cases'])},'obligations':{'t1':20,'t2':16,'t3':19,'t4':15,'t5':8},'inherited_runtime_files':78}
        exact(d['result'],expected,'MMC_T5_STAGE_RESULT')
        for g in GROUPS:
            r=read_json(out/f'vectors-{g}.json');require(r['status']=='PASS' and len(r['cases'])==expected['vectors'][g] and all(x['status']=='PASS' for x in r['cases']),'MMC_T5_VECTOR_EVIDENCE')
            r=read_json(out/f'model-{g}.json');require(r['status']=='PASS_REFERENCE_AND_TRACEABILITY' and type(r['obligations']) is int and r['obligations']==expected['obligations'][g] and r['tests']=='CHECKED' and r['semantic_equivalence_proof']=='NOT_ESTABLISHED','MMC_T5_MODEL_EVIDENCE')
        exact(read_json(out/'preservation.json'),preservation(),'MMC_T5_PRESERVATION')
    return d

def assemble(out,source):
    verify_source(ROOT,source);stages={p:verify_stage(out/p,p,source) for p in OUTPUTS}
    reg=registry();cases=read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'];due={c['id'] for c in cases if c['gate']=='T5' and c['id']!='AC-REPRO-06'}
    require(set(reg['acceptance'])==due,'MMC_T5_ACCEPTANCE_COVERAGE')
    for case,ids in reg['acceptance'].items():require(ids and all(t in reg['tests'] for t in ids),'MMC_T5_ACCEPTANCE_TESTS',case)
    r={'schema':'mmc.local-replay.t5','status':'PASS_SCOPED_T5_SIMULATION_NATIVE_GATE_BLOCKED','source_root':source,'tests':stages['tests']['result'],'examples':len(EXAMPLES),'t5_cases':len(due),'full_scenarios':10,'case_dispositions':{c['id']:('BLOCKED_NATIVE_DEPENDENCY' if c['id']=='AC-REPRO-06' else ('PASS_SCOPED' if c['gate'] in ('T1','T2','T3','T4','T5') else 'NOT_RUN')) for c in cases},'stages':{p:sha(out/p/'STAGE.json') for p in OUTPUTS},'authority_effect':'NONE','simulated_effects':'EXECUTED_IN_TEMPORARY_LOCAL_DATABASES','native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED','public_release':'NOT_CLEARED','signature':'NOT_SIGNED','clean_extraction':'SEPARATE_LEG_REQUIRED','installed_wheel':'SEPARATE_LEG_REQUIRED'}
    save_json(out/'LOCAL-REPLAY.json',r);return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-source',required=True);p.add_argument('--out',required=True);p.add_argument('--phase',required=True,choices=[*OUTPUTS,'assemble','test-t1','test-t2','test-t3','test-t4','test-t5']);p.add_argument('--require-native-pippi',action='store_true');a=p.parse_args()
    require(not a.require_native_pippi,'MMC_NATIVE_PIPPI_NOT_BOUND')
    verify_freeze();verify_source(ROOT,a.expected_source)
    for k in ('PYTEST_ADDOPTS','PYTEST_PLUGINS'):os.environ.pop(k,None)
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    os.environ['PYTHONPATH']=os.pathsep.join((str(ROOT/'src'),str(ROOT)))
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    require(Path.cwd().resolve()==ROOT,'MMC_T5_EXECUTION_DIRECTORY')
    out=Path(a.out).absolute();require(not out.is_relative_to(ROOT),'MMC_T5_EVIDENCE_OUTSIDE_SOURCE')
    if a.phase=='assemble':result=assemble(out,a.expected_source);print(canonical(result).decode());return 0
    if a.phase.startswith('test-'):
        target=out/'tests';target.mkdir(parents=True,exist_ok=True)
        require(not (target/'STAGE.json').exists(),'MMC_T5_STAGE_EXISTS')
        result=run_test_group(target,a.expected_source,a.phase[5:]);print(canonical(result).decode());return result['terminal_exit']
    target=out/a.phase
    if a.phase=='tests':require(target.is_dir() and not (target/'STAGE.json').exists(),'MMC_T5_TEST_PARTS_REQUIRED')
    else:require(not target.exists(),'MMC_T5_STAGE_EXISTS');target.mkdir(parents=True)
    result={'tests':lambda:run_tests(target,a.expected_source),'examples':lambda:run_examples(target,a.expected_source),'audit':lambda:run_audit(target,a.expected_source,out/'tests'),'scenarios':lambda:run_scenarios(target,a.expected_source)}[a.phase]()
    print(canonical(result).decode());return result['terminal_exit']
if __name__=='__main__':
    try:raise SystemExit(main())
    except MMCError as e:print(canonical({'schema':'mmc.qualification-refusal.t5','error':e.record(),'authority_effect':'NONE'}).decode());raise SystemExit(2)
