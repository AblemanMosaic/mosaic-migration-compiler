"""Source-admitted, independently runnable qualification stages. Not native P/PPI."""
from __future__ import annotations
from pathlib import Path
import argparse,io,os,platform,subprocess,sys,time,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import canonical,read_json,save_json,sha,verify_source,verify_freeze,require,source_snapshot
from tools.qualify import RecordedResult,flattened
from mosaic_mmc import MMCError

EXAMPLES=['examples/compile_and_inspect.py','examples/blocked_retirement.py','examples/t2/domain_profiles.py','examples/t2/retirement_progress.py','examples/t2/coexistence_planning.py']
OUTPUTS={
 'tests':{'collected.json','tests.json','t1-tests.json','t2-tests.json','t1-tests.txt','t2-tests.txt'},
 'examples':{'examples.json'}|{f'example-{i}.{ext}' for i in range(len(EXAMPLES)) for ext in ('stdout.txt','stderr.txt')},
 'audit':{'audit.json','vectors-t1.json','vectors-t2.json','model-t1.json','model-t2.json','preservation.json'}}

def environment():
    return {'python':platform.python_version(),'implementation':platform.python_implementation(),'system':platform.system(),'machine':platform.machine(),'executable':sys.executable,'runtime_dependencies':[],'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED'}

def registry():
    return read_json(ROOT/'provenance/turn2/TEST-REGISTRY.json')

def _record(out,phase,source,result,code):
    require({p.name for p in out.iterdir()}==OUTPUTS[phase],'MMC_T2_STAGE_OUTPUT_CLOSURE')
    stage={'schema':'mmc.local-stage.t2','phase':phase,'source_root':source,'environment':environment(),
           'outputs':[{'path':n,'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in sorted(OUTPUTS[phase])],
           'result':result,'terminal_exit':code,'authority_effect':'NONE','signature':'NOT_SIGNED'}
    save_json(out/'STAGE.json',stage);return stage

def run_tests(out,source):
    verify_source(ROOT,source);reg=registry();all_rows=[];all_ids=[];elapsed=0
    for group,directory in [('t1','tests'),('t2','tests_t2')]:
        suite=unittest.TestLoader().discover(str(ROOT/directory),top_level_dir=str(ROOT))
        ids=[t.id() for t in flattened(suite)];expected=reg['foundation_tests'] if group=='t1' else reg['tests']
        require(len(ids)==len(set(ids)) and sorted(ids)==expected,'MMC_T2_COLLECTION_COVERAGE',group)
        all_ids+=ids;stream=io.StringIO();start=time.perf_counter_ns()
        res=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult).run(suite)
        ns=time.perf_counter_ns()-start;elapsed+=ns;rows=sorted(res.records,key=lambda r:r['id'])
        require([r['id'] for r in rows]==expected,'MMC_T2_EXECUTION_COVERAGE',group)
        data={'schema':'mmc.test-results.t1' if group=='t1' else 'mmc.test-results.t2','source_root':source,'elapsed_ns':ns,'tests':rows,'counts':{s:sum(r['status']==s for r in rows) for s in ['PASS','FAIL','ERROR','SKIP']}}
        save_json(out/(group+'-tests.json'),data);(out/(group+'-tests.txt')).write_text(stream.getvalue(),encoding='utf-8');all_rows+=rows
    verify_source(ROOT,source)
    require(len(all_ids)==len(set(all_ids)),'MMC_T2_DUPLICATE_TEST_DISCOVERY')
    save_json(out/'collected.json',{'schema':'mmc.collected-tests.t2','source_root':source,'ids':sorted(all_ids)})
    counts={s:sum(r['status']==s for r in all_rows) for s in ['PASS','FAIL','ERROR','SKIP']}
    save_json(out/'tests.json',{'schema':'mmc.test-results.t2','source_root':source,'elapsed_ns':elapsed,'tests':sorted(all_rows,key=lambda r:r['id']),'counts':counts})
    return _record(out,'tests',source,counts,0 if counts['PASS']==len(all_rows) else 2)

def run_examples(out,source):
    verify_source(ROOT,source);rows=[]
    for i,script in enumerate(EXAMPLES):
        env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
        p=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,env=env,capture_output=True,timeout=45)
        for ext,raw in [('stdout.txt',p.stdout),('stderr.txt',p.stderr)]: (out/f'example-{i}.{ext}').write_bytes(raw)
        rows.append({'script':script,'exit_code':p.returncode})
    verify_source(ROOT,source);save_json(out/'examples.json',{'schema':'mmc.examples.t2','source_root':source,'runs':rows})
    return _record(out,'examples',source,{'runs':rows},0 if all(x['exit_code']==0 for x in rows) else 2)

def preservation():
    from tools.public_predecessor import load_public_predecessor
    record=load_public_predecessor(1)
    names=[row['path'] for row in record['rows']]
    runtime=sum(n.startswith('src/mosaic_mmc/') for n in names)
    return {'schema':'mmc.preservation.t2','status':'PASS','paths':names,'runtime_files':runtime,'authority_effect':'NONE'}

def run_audit(out,source,tests_dir):
    verify_source(ROOT,source)
    verify_stage(tests_dir,'tests',source)
    from tools.check_vectors import check as t1_vectors
    from tools_t2.check_vectors import check as t2_vectors
    from tools.check_model import check as t1_model
    from tools_t2.check_model import check as t2_model
    reports={'vectors-t1':t1_vectors(),'vectors-t2':t2_vectors(),'model-t1':t1_model(tests_path=tests_dir/'t1-tests.json'),'model-t2':t2_model(tests_dir/'t2-tests.json'),'preservation':preservation()}
    for name,record in reports.items():save_json(out/(name+'.json'),record)
    result={'status':'PASS','t1_vectors':len(reports['vectors-t1']['cases']),'t2_vectors':len(reports['vectors-t2']['cases']),'t1_obligations':reports['model-t1']['obligations'],'t2_obligations':reports['model-t2']['obligations'],'t1_runtime_files':reports['preservation']['runtime_files']}
    save_json(out/'audit.json',{'schema':'mmc.audit.t2','source_root':source,'result':result})
    verify_source(ROOT,source);return _record(out,'audit',source,result,0)

def verify_stage(out,phase,source):
    require(phase in OUTPUTS,'MMC_T2_STAGE_PHASE')
    d=read_json(out/'STAGE.json')
    require(type(d) is dict and set(d)=={'schema','phase','source_root','environment','outputs','result','terminal_exit','authority_effect','signature'},'MMC_T2_STAGE_FIELDS')
    require(d['schema']=='mmc.local-stage.t2' and d['phase']==phase and d['source_root']==source,'MMC_T2_STAGE_IDENTITY')
    require(type(d['terminal_exit']) is int and d['terminal_exit']==0 and d['authority_effect']=='NONE' and d['signature']=='NOT_SIGNED','MMC_T2_STAGE_TERMINAL')
    env=d['environment'];current=environment()
    require(type(env) is dict and set(env)==set(current),'MMC_T2_STAGE_ENVIRONMENT')
    require(all(type(env[k]) is str and env[k] for k in ['python','implementation','system','machine','executable']) and env['runtime_dependencies']==[] and env['native_pippi']=='NOT_BOUND' and env['independent_review']=='NOT_PERFORMED','MMC_T2_STAGE_ENVIRONMENT')
    require(type(d['outputs']) is list and len(d['outputs'])==len(OUTPUTS[phase]),'MMC_T2_STAGE_OUTPUTS')
    seen=set()
    for r in d['outputs']:
        require(type(r) is dict and set(r)=={'path','bytes','sha256'} and type(r['path']) is str and r['path'] in OUTPUTS[phase] and r['path'] not in seen,'MMC_T2_STAGE_OUTPUTS')
        seen.add(r['path']);p=out/r['path']
        require(type(r['bytes']) is int and p.is_file() and not p.is_symlink() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'MMC_T2_STAGE_OUTPUT_HASH')
    require(seen==OUTPUTS[phase] and {p.name for p in out.iterdir()}==OUTPUTS[phase]|{'STAGE.json'},'MMC_T2_STAGE_OUTPUT_CLOSURE')
    if phase=='tests':
        reg=registry();expected=sorted(reg['foundation_tests']+reg['tests']);combined=[]
        for group,ids in [('t1',reg['foundation_tests']),('t2',reg['tests']),('',expected)]:
            r=read_json(out/(group+'-tests.json' if group else 'tests.json'))
            require(type(r) is dict and set(r)=={'schema','source_root','elapsed_ns','tests','counts'} and r['schema']==('mmc.test-results.t1' if group=='t1' else 'mmc.test-results.t2') and r['source_root']==source,'MMC_T2_TEST_REPORT')
            require(type(r['elapsed_ns']) is int and r['elapsed_ns']>=0 and type(r['tests']) is list,'MMC_T2_TEST_REPORT')
            require(r['tests']==[{'id':i,'status':'PASS'} for i in ids],'MMC_T2_TEST_IDENTITIES')
            require(canonical(r['counts'])==canonical({'PASS':len(ids),'FAIL':0,'ERROR':0,'SKIP':0}),'MMC_T2_TEST_COUNTS')
        c=read_json(out/'collected.json');require(c=={'schema':'mmc.collected-tests.t2','source_root':source,'ids':expected},'MMC_T2_COLLECTION_COVERAGE')
        require(canonical(d['result'])==canonical({'PASS':len(expected),'FAIL':0,'ERROR':0,'SKIP':0}),'MMC_T2_STAGE_RESULT')
    elif phase=='examples':
        expected={'runs':[{'script':s,'exit_code':0} for s in EXAMPLES]};r=read_json(out/'examples.json')
        require(canonical(r)==canonical({'schema':'mmc.examples.t2','source_root':source,**expected}) and canonical(d['result'])==canonical(expected),'MMC_T2_STAGE_RESULT')
    else:
        r=read_json(out/'audit.json');require(canonical(r)==canonical({'schema':'mmc.audit.t2','source_root':source,'result':d['result']}),'MMC_T2_STAGE_RESULT')
        expected={'status':'PASS','t1_vectors':20,'t2_vectors':38,'t1_obligations':20,'t2_obligations':16,'t1_runtime_files':25}
        require(canonical(d['result'])==canonical(expected),'MMC_T2_STAGE_RESULT')
        for name,count in [('vectors-t1',20),('vectors-t2',38)]:
            v=read_json(out/(name+'.json'));require(v['status']=='PASS' and len(v['cases'])==count and all(row['status']=='PASS' for row in v['cases']),'MMC_T2_AUDIT_VECTOR')
        for name,count in [('model-t1',20),('model-t2',16)]:
            v=read_json(out/(name+'.json'));require(v['status']=='PASS_REFERENCE_AND_TRACEABILITY' and type(v['obligations']) is int and v['obligations']==count and v['tests']=='CHECKED' and v['semantic_equivalence_proof']=='NOT_ESTABLISHED','MMC_T2_AUDIT_MODEL')
        require(read_json(out/'preservation.json')==preservation(),'MMC_T2_AUDIT_PRESERVATION')
    return d

def assemble(out,source):
    verify_source(ROOT,source);stages={p:verify_stage(out/p,p,source) for p in OUTPUTS}
    require(all(canonical(v['environment'])==canonical(stages['tests']['environment']) for v in stages.values()),'MMC_T2_STAGE_CONTEXT')
    reg=registry();cases=read_json(ROOT/'constitution/ACCEPTANCE.json')['cases'];due={c['id'] for c in cases if c['gate']=='T2'}
    require(set(reg['acceptance'])==due,'MMC_T2_ACCEPTANCE_COVERAGE')
    for case,ids in reg['acceptance'].items():require(ids and all(t in reg['tests'] for t in ids),'MMC_T2_ACCEPTANCE_TESTS',case)
    result={'schema':'mmc.local-replay.t2','status':'PASS_LOCAL_TESTS_EXAMPLES_AND_AUDIT_ONLY','source_root':source,'tests':stages['tests']['result'],'examples':len(EXAMPLES),'t2_cases':len(due),'case_dispositions':{c['id']:('PASS_SCOPED' if c['gate'] in ('T1','T2') else 'NOT_RUN') for c in cases},'stages':{p:sha(out/p/'STAGE.json') for p in OUTPUTS},'authority_effect':'NONE','native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED','public_release':'NOT_CLEARED','signature':'NOT_SIGNED','clean_extraction':'SEPARATE_LEG_REQUIRED','installed_wheel':'SEPARATE_LEG_REQUIRED'}
    save_json(out/'LOCAL-REPLAY.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-source',required=True);p.add_argument('--out',required=True);p.add_argument('--phase',choices=['tests','examples','audit','assemble'],required=True);p.add_argument('--require-native-pippi',action='store_true');a=p.parse_args()
    require(not a.require_native_pippi,'MMC_NATIVE_PIPPI_NOT_BOUND')
    verify_freeze();verify_source(ROOT,a.expected_source)
    out=Path(a.out).absolute();require(not out.is_relative_to(ROOT),'MMC_T2_EVIDENCE_OUTSIDE_SOURCE')
    if a.phase=='assemble':result=assemble(out,a.expected_source);print(canonical(result).decode());return 0
    target=out/a.phase;require(not target.exists(),'MMC_T2_STAGE_EXISTS');target.mkdir(parents=True)
    result={'tests':lambda:run_tests(target,a.expected_source),'examples':lambda:run_examples(target,a.expected_source),'audit':lambda:run_audit(target,a.expected_source,out/'tests')}[a.phase]()
    print(canonical(result).decode());return result['terminal_exit']
if __name__=='__main__':
    try:raise SystemExit(main())
    except MMCError as e:print(canonical({'schema':'mmc.qualification-refusal.t2','error':e.record(),'authority_effect':'NONE'}).decode());raise SystemExit(2)
