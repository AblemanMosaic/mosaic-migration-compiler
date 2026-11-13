"""Source-admitted local qualification with exact test identities. Not a native pipeline host.
Use an externally accepted --expected-source; this tool never rewrites its source/oracles.
"""
from __future__ import annotations
import argparse,hashlib,io,json,os,platform,subprocess,sys,time,unittest
from pathlib import Path
try:from .common import ROOT,read_json,save_json,sha,canonical,verify_source,verify_freeze,require
except ImportError:from common import ROOT,read_json,save_json,sha,canonical,verify_source,verify_freeze,require


def flattened(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flattened(item)
        else:yield item

class RecordedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.records=[];self.current={}
    def startTest(self,test):super().startTest(test);self.current[test.id()]='PASS'
    def addFailure(self,test,err):super().addFailure(test,err);self.current[test.id()]='FAIL'
    def addError(self,test,err):super().addError(test,err);self.current[test.id()]='ERROR'
    def addSkip(self,test,reason):super().addSkip(test,reason);self.current[test.id()]='SKIP'
    def addExpectedFailure(self,test,err):super().addExpectedFailure(test,err);self.current[test.id()]='FAIL'
    def addUnexpectedSuccess(self,test):super().addUnexpectedSuccess(test);self.current[test.id()]='FAIL'
    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err is not None:self.current[test.id()]='FAIL'
    def stopTest(self,test):
        self.records.append({'id':test.id(),'status':self.current[test.id()]});super().stopTest(test)


def _environment():return {'python':platform.python_version(),'implementation':platform.python_implementation(),
    'system':platform.system(),'machine':platform.machine(),'executable':sys.executable,
    'third_party_runtime_dependencies':[],'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED'}


def _write_stage(out,phase,source,outputs,result,exit_code):
    data={'schema':'mmc.local-stage.t1','phase':phase,'source_root':source,'environment':_environment(),
          'outputs':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(outputs)],
          'result':result,'terminal_exit':exit_code,'authority_effect':'NONE','signature':'NOT_SIGNED'}
    save_json(out/(phase.upper()+'-STAGE.json'),data)
    return data


def run_tests(out,source):
    # Source admission occurs BEFORE importing any selected test module.
    verify_source(ROOT,source)
    registry=read_json(ROOT/'provenance/TEST-REGISTRY.json')
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    suite=unittest.TestLoader().discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
    ids=[t.id() for t in flattened(suite)]
    require(len(ids)==len(set(ids)) and sorted(ids)==registry['tests'],'MMC_TEST_IDENTITY_COVERAGE')
    save_json(out/'collected.json',{'schema':'mmc.collected-tests.t1','ids':sorted(ids),'source_root':source})
    stream=io.StringIO();runner=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult)
    start=time.perf_counter_ns();res=runner.run(suite);elapsed=time.perf_counter_ns()-start
    (out/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    verify_source(ROOT,source)
    rows=sorted(res.records,key=lambda r:r['id'])
    require([r['id'] for r in rows]==registry['tests'],'MMC_TEST_EXECUTION_COVERAGE')
    record={'schema':'mmc.test-results.t1','source_root':source,'elapsed_ns':elapsed,'tests':rows,
            'counts':{s:sum(r['status']==s for r in rows) for s in ['PASS','FAIL','ERROR','SKIP']}}
    save_json(out/'tests.json',record)
    code=0 if all(r['status']=='PASS' for r in rows) and res.wasSuccessful() else 2
    return _write_stage(out,'tests',source,[out/'collected.json',out/'tests.txt',out/'tests.json'],record['counts'],code)


def run_examples(out,source):
    verify_source(ROOT,source);env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1')
    rows=[];outputs=[]
    for script in ['compile_and_inspect.py','blocked_retirement.py']:
        name=script.removesuffix('.py');cmd=[sys.executable,str(ROOT/'examples'/script)]
        p=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,timeout=30)
        for ext,data in [('stdout.txt',p.stdout),('stderr.txt',p.stderr)]:
            dest=out/(name+'.'+ext);dest.write_bytes(data);outputs.append(dest)
        rows.append({'script':script,'exit_code':p.returncode})
    verify_source(ROOT,source);save_json(out/'examples.json',{'schema':'mmc.example-results.t1','source_root':source,'runs':rows});outputs.append(out/'examples.json')
    return _write_stage(out,'examples',source,outputs,{'runs':rows},0 if all(r['exit_code']==0 for r in rows) else 2)


def verify_stage(directory:Path,phase:str,source:str):
    data=read_json(directory/(phase.upper()+'-STAGE.json'))
    require(type(data) is dict and set(data)=={'schema','phase','source_root','environment','outputs','result','terminal_exit','authority_effect','signature'},'MMC_STAGE_FIELDS')
    require(data['schema']=='mmc.local-stage.t1' and data['phase']==phase and data['source_root']==source,'MMC_STAGE_IDENTITY')
    require(type(data['terminal_exit']) is int and data['terminal_exit']==0 and data['authority_effect']=='NONE' and data['signature']=='NOT_SIGNED','MMC_STAGE_TERMINAL')
    env=data['environment']
    require(type(env) is dict and set(env)=={'python','implementation','system','machine','executable','third_party_runtime_dependencies','native_pippi','independent_review'},'MMC_STAGE_ENVIRONMENT')
    require(all(type(env[k]) is str and env[k] for k in ['python','implementation','system','machine','executable']) and env['third_party_runtime_dependencies']==[] and env['native_pippi']=='NOT_BOUND' and env['independent_review']=='NOT_PERFORMED','MMC_STAGE_ENVIRONMENT')
    expected={'tests':{'collected.json','tests.txt','tests.json'},'examples':{'examples.json','compile_and_inspect.stdout.txt','compile_and_inspect.stderr.txt','blocked_retirement.stdout.txt','blocked_retirement.stderr.txt'}}[phase]
    require(type(data['outputs']) is list and len(data['outputs'])==len(expected),'MMC_STAGE_OUTPUTS')
    seen=set()
    for row in data['outputs']:
        require(type(row) is dict and set(row)=={'path','bytes','sha256'} and row['path'] in expected and row['path'] not in seen,'MMC_STAGE_OUTPUTS')
        seen.add(row['path']);p=directory/row['path']
        require(type(row['bytes']) is int and p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'MMC_STAGE_OUTPUT_HASH')
    require(seen==expected,'MMC_STAGE_OUTPUTS')
    if phase=='tests':
        registry=read_json(ROOT/'provenance/TEST-REGISTRY.json');r=read_json(directory/'tests.json');c=read_json(directory/'collected.json')
        require(set(r)=={'schema','source_root','elapsed_ns','tests','counts'} and r['schema']=='mmc.test-results.t1' and r['source_root']==source and type(r['elapsed_ns']) is int and r['elapsed_ns']>=0,'MMC_STAGE_RESULTS')
        require(set(c)=={'schema','ids','source_root'} and c['schema']=='mmc.collected-tests.t1' and c['source_root']==source and c['ids']==registry['tests'],'MMC_TEST_IDENTITY_COVERAGE')
        require(type(r['tests']) is list and [x['id'] for x in r['tests']]==registry['tests'],'MMC_TEST_IDENTITY_COVERAGE')
        require(all(set(x)=={'id','status'} and x['status']=='PASS' for x in r['tests']),'MMC_TEST_EXECUTION_FAILURE')
        require(canonical(r['counts'])==canonical({'PASS':len(registry['tests']),'FAIL':0,'ERROR':0,'SKIP':0}) and canonical(data['result'])==canonical(r['counts']),'MMC_STAGE_RESULTS')
    else:
        r=read_json(directory/'examples.json')
        require(type(r) is dict and set(r)=={'schema','source_root','runs'} and r['source_root']==source and r['schema']=='mmc.example-results.t1' and canonical(r['runs'])==canonical([{'script':'compile_and_inspect.py','exit_code':0},{'script':'blocked_retirement.py','exit_code':0}]) and canonical(data['result'])==canonical({'runs':r['runs']}),'MMC_STAGE_RESULTS')
    return data


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-source',required=True);p.add_argument('--out',required=True);p.add_argument('--phase',choices=['tests','examples','assemble'],required=True);p.add_argument('--require-native-pippi',action='store_true');a=p.parse_args()
    require(not a.require_native_pippi,'MMC_NATIVE_PIPPI_NOT_BOUND')
    verify_freeze();verify_source(ROOT,a.expected_source)
    out=Path(a.out).absolute();require(not out.is_relative_to(ROOT),'MMC_EVIDENCE_OUTSIDE_SOURCE')
    if a.phase=='assemble':
        tests=verify_stage(out,'tests',a.expected_source);examples=verify_stage(out,'examples',a.expected_source)
        require(canonical(tests['environment'])==canonical(examples['environment']),'MMC_STAGE_CONTEXT_MISMATCH')
        result={'schema':'mmc.local-replay.t1','source_root':a.expected_source,'status':'PASS_TESTS_AND_EXAMPLES_ONLY',
                'tests':tests['result'],'examples':2,'stages':{p:sha(out/(p.upper()+'-STAGE.json')) for p in ['tests','examples']},
                'authority_effect':'NONE','native_pippi':'NOT_BOUND','signature':'NOT_SIGNED'}
        save_json(out/'LOCAL-REPLAY.json',result);print(canonical(result).decode());return 0
    out.mkdir(parents=True,exist_ok=True);require(not(out/(a.phase.upper()+'-STAGE.json')).exists(),'MMC_STAGE_ALREADY_EXISTS')
    result=(run_tests if a.phase=='tests' else run_examples)(out,a.expected_source)
    print(canonical(result).decode());return result['terminal_exit']

if __name__=='__main__':
    from mosaic_mmc import MMCError
    try:raise SystemExit(main())
    except MMCError as exc:
        print(canonical({'schema':'mmc.qualification-refusal.t1','error':exc.record(),'authority_effect':'NONE'}).decode());raise SystemExit(2)
