"""Source-admitted release replay. Delegates unchanged runtime gates; adds T6 qualification tests."""
from pathlib import Path
import argparse,io,os,sys,subprocess,time,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json,save_json,sha,canonical,require,verify_source,verify_freeze,source_snapshot
from tools.qualify import RecordedResult,flattened
from tools_t5 import qualify as base
from tools_t6.audit import audit,freeze
from mosaic_mmc import MMCError

BASE_PHASES={'test-t1','test-t2','test-t3','test-t4','test-t5','tests','scenarios','examples','audit','assemble'}

def test_ids():return read_json(ROOT/'provenance/turn6/TEST-REGISTRY.json')['tests']
def artifacts(out,names):return [{'path':n,'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in sorted(names)]
def write_stage(out,phase,source,names,result,exit_code):
    require({p.name for p in out.iterdir()}==set(names),'MMC_T6_OUTPUT_CLOSURE')
    v={'schema':'mmc.qualification-stage.t6','phase':phase,'source_root':source,'environment':base.environment(),
       'outputs':artifacts(out,names),'result':result,'terminal_exit':exit_code,'authority_effect':'NONE','signature':'NOT_SIGNED'}
    save_json(out/'STAGE.json',v);return v

def verify_stage(out,phase,source):
    names={'test-t6':{'tests.json','tests.txt','collected.json'},'audit':{'audit.json','model.json'}}[phase]
    d=read_json(out/'STAGE.json')
    require(type(d) is dict and set(d)=={'schema','phase','source_root','environment','outputs','result','terminal_exit','authority_effect','signature'},'MMC_T6_STAGE_FIELDS')
    require(d['schema']=='mmc.qualification-stage.t6' and d['phase']==phase and d['source_root']==source and type(d['terminal_exit']) is int and d['terminal_exit']==0 and d['authority_effect']=='NONE' and d['signature']=='NOT_SIGNED','MMC_T6_STAGE_TERMINAL')
    base.exact(d['environment'],base.environment(),'MMC_T6_STAGE_CONTEXT')
    require({p.name for p in out.iterdir()}==names|{'STAGE.json'},'MMC_T6_OUTPUT_CLOSURE')
    for n in names:require((out/n).is_file() and not (out/n).is_symlink(),'MMC_T6_OUTPUT_KIND')
    base.exact(d['outputs'],artifacts(out,names),'MMC_T6_OUTPUT_HASH')
    if phase=='test-t6':
        r=read_json(out/'tests.json');ids=test_ids();expected=[{'id':i,'status':'PASS'} for i in ids]
        require(type(r) is dict and set(r)=={'schema','source_root','elapsed_ns','tests','counts'} and r['schema']=='mmc.test-results.t6' and r['source_root']==source and type(r['elapsed_ns']) is int and r['elapsed_ns']>=0,'MMC_T6_TEST_HEADER')
        base.exact(r['tests'],expected,'MMC_T6_TEST_IDENTITIES');base.exact(r['counts'],base.counts(len(ids)),'MMC_T6_TEST_COUNTS')
        base.exact(read_json(out/'collected.json'),{'schema':'mmc.collected-tests.t6','source_root':source,'ids':ids},'MMC_T6_COLLECTION')
        base.exact(d['result'],r['counts'],'MMC_T6_TEST_RESULT')
    else:
        base.exact(read_json(out/'audit.json'),audit(),'MMC_T6_AUDIT_RECOMPUTE')
        from tools_t6.check_model import check
        base.exact(read_json(out/'model.json'),check(out.parent/'test-t6/tests.json'),'MMC_T6_MODEL_RECOMPUTE')
        base.exact(d['result'],{'status':'PASS','mapped_requirements':6,'measured_study':False},'MMC_T6_AUDIT_RESULT')
    return d

def run_tests(out,source):
    verify_source(ROOT,source);freeze();suite=unittest.TestLoader().discover(str(ROOT/'tests_t6'),top_level_dir=str(ROOT))
    ids=sorted(t.id() for t in flattened(suite));require(len(ids)==len(set(ids)) and ids==test_ids(),'MMC_T6_COLLECTION')
    save_json(out/'collected.json',{'schema':'mmc.collected-tests.t6','source_root':source,'ids':ids})
    stream=io.StringIO();start=time.perf_counter_ns();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult).run(suite)
    rows=sorted(r.records,key=lambda x:x['id']);require([x['id'] for x in rows]==ids,'MMC_T6_EXECUTED_COVERAGE')
    counts={s:sum(x['status']==s for x in rows) for s in ('PASS','FAIL','ERROR','SKIP')}
    save_json(out/'tests.json',{'schema':'mmc.test-results.t6','source_root':source,'elapsed_ns':time.perf_counter_ns()-start,'tests':rows,'counts':counts})
    (out/'tests.txt').write_text(stream.getvalue(),encoding='utf8');verify_source(ROOT,source)
    return write_stage(out,'test-t6',source,{'tests.json','tests.txt','collected.json'},counts,0 if r.wasSuccessful() and counts==base.counts(len(ids)) else 2)

def run_audit(out,source):
    verify_source(ROOT,source);verify_stage(out.parent/'test-t6','test-t6',source)
    from tools_t6.check_model import check
    save_json(out/'audit.json',audit());save_json(out/'model.json',check(out.parent/'test-t6/tests.json'))
    verify_source(ROOT,source)
    return write_stage(out,'audit',source,{'audit.json','model.json'},{'status':'PASS','mapped_requirements':6,'measured_study':False},0)

def assemble(out,source):
    verify_source(ROOT,source);freeze()
    b=out/'base';stages={p:base.verify_stage(b/p,p,source) for p in base.OUTPUTS}
    br=read_json(b/'LOCAL-REPLAY.json')
    require(br['schema']=='mmc.local-replay.t5' and br['status']=='PASS_SCOPED_T5_SIMULATION_NATIVE_GATE_BLOCKED' and br['source_root']==source,'MMC_T6_BASE_TERMINAL')
    base.exact(br['stages'],{p:sha(b/p/'STAGE.json') for p in base.OUTPUTS},'MMC_T6_BASE_STAGE_REFS')
    base.exact(br['tests'],stages['tests']['result'],'MMC_T6_BASE_COUNTS')
    require(br['public_release']=='NOT_CLEARED' and br['native_pippi']=='NOT_BOUND' and br['authority_effect']=='NONE','MMC_T6_BASE_CLAIM')
    t=verify_stage(out/'test-t6','test-t6',source);a=verify_stage(out/'audit','audit',source)
    inherited=sum(base.expected_ids().values(),[]);new=test_ids();ids=sorted(inherited+new)
    require(len(ids)==len(set(ids)),'MMC_T6_DUPLICATE_TEST')
    r={'schema':'mmc.local-replay.t6','status':'PASS_LOCAL_REPLAY_NOT_RELEASE_APPROVAL','source_root':source,'environment':base.environment(),
      'tests':base.counts(len(ids)),'inherited_tests':len(inherited),'new_tests':len(new),'test_identity_root':__import__('hashlib').sha256(canonical(ids)).hexdigest(),
      'examples':12,'scenarios':10,'stage_hashes':{'base':sha(b/'LOCAL-REPLAY.json'),'t6_tests':sha(out/'test-t6/STAGE.json'),'t6_audit':sha(out/'audit/STAGE.json')},
      'model_bindings':{'inherited':78,'release_mapped':6,'research_requirements_not_performed':2},
      'clean_extraction':'SEPARATE_LEG_REQUIRED','installed_wheel':'SEPARATE_LEG_REQUIRED','platform_coverage':'CURRENT_HOST_ONLY',
      'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED','independent_study':'NOT_PERFORMED','public_release':'NOT_CLEARED','authority_effect':'NONE','signature':'NOT_SIGNED'}
    save_json(out/'LOCAL-REPLAY.json',r);return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-source',required=True);p.add_argument('--out',required=True)
    p.add_argument('--phase',choices=['test-t1','test-t2','test-t3','test-t4','test-t5','base-tests','scenarios','examples','base-audit','base-assemble','test-t6','audit','assemble'],required=True)
    p.add_argument('--require-native-pippi',action='store_true');p.add_argument('--require-platform',choices=['Linux','Windows','Darwin'])
    a=p.parse_args();require(not a.require_native_pippi,'MMC_NATIVE_PIPPI_NOT_BOUND')
    if a.require_platform:require(__import__('platform').system()==a.require_platform,'MMC_T6_REQUIRED_PLATFORM_UNAVAILABLE')
    verify_source(ROOT,a.expected_source);freeze();require(Path.cwd().resolve()==ROOT,'MMC_T6_EXECUTION_DIRECTORY')
    out=Path(a.out).resolve();require(not out.is_relative_to(ROOT),'MMC_T6_EVIDENCE_OUTSIDE_SOURCE');out.mkdir(parents=True,exist_ok=True)
    os.environ['PYTHONPATH']=os.pathsep.join([str(ROOT/'src'),str(ROOT)]);os.environ['PYTHONDONTWRITEBYTECODE']='1'
    for k in ('PYTEST_ADDOPTS','PYTEST_PLUGINS'):os.environ.pop(k,None)
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    phase=a.phase.removeprefix('base-')
    if a.phase not in ('test-t6','audit','assemble'):
        require(phase in BASE_PHASES,'MMC_T6_PHASE')
        return subprocess.run([sys.executable,str(ROOT/'tools_t5/qualify.py'),'--expected-source',a.expected_source,'--out',str(out/'base'),'--phase',phase],cwd=ROOT).returncode
    if a.phase=='assemble':r=assemble(out,a.expected_source)
    else:
        folder=out/a.phase;require(not folder.exists(),'MMC_T6_STAGE_EXISTS');folder.mkdir()
        r=(run_tests if a.phase=='test-t6' else run_audit)(folder,a.expected_source)
    print(canonical(r).decode());return r.get('terminal_exit',0)
if __name__=='__main__':
    try:raise SystemExit(main())
    except MMCError as e:print(canonical({'schema':'mmc.qualification-refusal.t6','error':e.record(),'authority_effect':'NONE'}).decode());raise SystemExit(2)
