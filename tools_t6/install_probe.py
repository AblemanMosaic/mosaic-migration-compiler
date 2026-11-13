"""Run outside checkout with selected installed interpreter; no source sys.path modification."""
from pathlib import Path
import argparse,hashlib,importlib.metadata,importlib.util,json,sys,tempfile,zipfile,subprocess

def main():
    p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--prefix',required=True);p.add_argument('--out',required=True);p.add_argument('--operational',action='store_true');p.add_argument('--native',action='store_true');a=p.parse_args()
    import mosaic_mmc,mosaic_mmc_t2,mosaic_mmc_t3,mosaic_mmc_t4,mosaic_mmc_workbench,mosaic_mmc_t5
    from mosaic_mmc import canonical,decode,MMCError
    from mosaic_mmc_t4.abi import dispatch,capabilities
    from mosaic_mmc_t4.views import assess_view,replay_view,reader_for_sample
    prefix=Path(a.prefix).resolve();mods=(mosaic_mmc,mosaic_mmc_t2,mosaic_mmc_t3,mosaic_mmc_t4,mosaic_mmc_workbench,mosaic_mmc_t5)
    for m in mods:assert Path(m.__file__).resolve().is_relative_to(prefix),m.__file__
    assert importlib.metadata.version('mosaic-migration-compiler')=='0.1.0a6'
    site=Path(mosaic_mmc.__file__).resolve().parent.parent;paths=[]
    with zipfile.ZipFile(a.wheel) as z:
        for n in z.namelist():
            if '.dist-info/' not in n:
                assert (site/n).read_bytes()==z.read(n),n;paths.append(n)
    c=capabilities();assert c['native_pippi']=='NOT_BOUND'
    profile=dispatch({'schema':'mmc.request.t4','operation':'profile-assess','arguments':{'name':'jobs','value':{'schema':'mmc.job-input.t4','jobs':[]}}});assert profile['status']=='NONE_IN_SUPPLIED_SNAPSHOT'
    result={'schema':'mmc.installed-probe.t6','status':'PASS','version':importlib.metadata.version('mosaic-migration-compiler'),'prefix':str(prefix),'source_tree_imports':False,'package_paths':paths,'package_files':len(paths),'operational':a.operational,'native':a.native,'authority_effect':'NONE','fresh_dependency_resolution':'NOT_ESTABLISHED'}
    if not a.operational:
        assert importlib.util.find_spec('cryptography') is None
        try:
            from mosaic_mmc_t3.statements import backend
            backend()
        except MMCError as e:assert e.code=='MMC_T3_SIGNING_DEPENDENCY'
        else:raise AssertionError('unexpected signing backend')
        result['optional_missing']='EXPLICIT_REFUSAL'
    else:
        from mosaic_mmc_workbench.model import Workbench
        import cryptography
        assert importlib.metadata.version('cryptography').split('.')[0]=='46'
        assert Path(cryptography.__file__).resolve().is_relative_to(prefix)
        demo=decode(Path(mosaic_mmc_t4.__file__).parent.joinpath('data/demo.json').read_bytes())
        model=Workbench();model.load(demo['workspace']);assert model.reader is None
        model.select_reader(demo['reader'],demonstration=True);v=model.evaluate();assert v['body']['status']=='INDETERMINATE'
        assert replay_view(model.selection,model.reader,v)['status']=='MATCH_EXACT_REPLAY'
        work=model.request_work('coverage',[]);assert len(canonical(work))<len(canonical(model.selection))
        from mosaic_mmc_t4.exports import LocalExport
        with tempfile.TemporaryDirectory() as d:
            h=LocalExport(d,state_token=lambda:'installed',clock=lambda:1)
            plan=h.prepare(model.packet(),'workspace.json');approval=h.approve(plan['root']);out=h.commit(approval)
            assert Path(d,'workspace.json').is_file()
        result['workbench_model']='PASS_READER_ASSESS_REPLAY_WORK_EXPORT'
        result['crypto_version']=importlib.metadata.version('cryptography')
        result['dependency_source']='EXACT_COPIES_OF_GENUINE_PREINSTALLED_DISTRIBUTIONS'
    if a.native:
        from mosaic_mmc_t4.integrations import native_read
        import cmba_core,dkn_v02
        from cmba_core.registry import contract
        value={'note':'installed fixture'}
        dim=cmba_core.dimension('description','metadata','example.description.v1',value,critical=False)
        b=cmba_core.bind(cmba_core.profile_reference(contract('cmba.generic')),[dim])
        x=native_read('cmba',{'binding':b,'values':{'description':value}});assert x['status']=='NATIVE_REPORT_COMPUTED'
        z,m=dkn_v02.pack({'hello.txt':b'hi'})
        x=native_read('dkn',{'archive_hex':z.hex(),'expected_root':m['logical_root']});assert x['native_result']['logical_root']==m['logical_root']
        result['native_readers']='CMBA_INSPECT_DKN_ARCHIVE_PASS'
    from mosaic_mmc_t5 import catalogue
    assert len(catalogue())==10
    if a.operational:
        from mosaic_mmc_t5 import run_scenario, replay_scenario
        from mosaic_mmc_t5.foundry import inspect_result
        simulation=run_scenario('lost-ack')
        assert inspect_result(simulation,expected_root=simulation['root'])['effects']=='NOT_EXECUTED'
        assert replay_scenario('lost-ack',simulation)['status']=='MATCH_EXACT_FRESH_SIMULATION'
        result['foundry']='PASS_FULL_LOST_ACK_AND_FRESH_REPLAY'
        result['simulation_root']=simulation['root']
    binary=Path(sys.executable).parent/'mmc-agent' 
    cp=subprocess.run([str(binary),'capabilities'],capture_output=True,timeout=15)
    assert cp.returncode==0 and decode(cp.stdout)['profile']=='T4-I1'
    cp=subprocess.run([str(Path(sys.executable).parent/'mmc-foundry'),'list'],capture_output=True,timeout=15)
    assert cp.returncode==0 and len(decode(cp.stdout)['scenarios'])==10
    result['cli']='PASS_MMC_AGENT_AND_FOUNDRY' 
    Path(a.out).write_bytes(canonical(result));print(canonical(result).decode())
if __name__=='__main__':main()
