"""Run from outside source using an explicitly selected installed interpreter."""
from pathlib import Path
import argparse,json,sys,importlib.metadata,importlib.util,hashlib,zipfile,subprocess,tempfile

def main():
    p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--fixture',required=True);p.add_argument('--prefix',required=True);p.add_argument('--out',required=True);p.add_argument('--operational',action='store_true');a=p.parse_args()
    import mosaic_mmc,mosaic_mmc_t2,mosaic_mmc_t3
    from mosaic_mmc import canonical,decode,MMCError
    from mosaic_mmc_t3 import Controller,SimulatedStore,make_plan,digest,seal,public_hex
    from mosaic_mmc_t3.common import realization
    from mosaic_mmc_t3.courts import scope
    prefix=Path(a.prefix).resolve()
    for mod in (mosaic_mmc,mosaic_mmc_t2,mosaic_mmc_t3):assert Path(mod.__file__).resolve().is_relative_to(prefix),mod.__file__
    assert importlib.metadata.version('mosaic-migration-compiler')=='0.1.0a3'
    site=Path(mosaic_mmc.__file__).resolve().parent.parent;compared=[]
    with zipfile.ZipFile(a.wheel) as z:
        for n in z.namelist():
            if '.dist-info/' not in n:
                assert (site/n).read_bytes()==z.read(n),n;compared.append(n)
    fixture=decode(Path(a.fixture).read_bytes());result={'schema':'mmc.installed-probe.t3','status':'PASS','package_files':len(compared),'package_paths':compared,'prefix':str(prefix),'python':sys.version.split()[0],'stdlib_core':True,'operational':a.operational,'source_tree_imports':False,'fresh_dependency_resolution':'NOT_ESTABLISHED','production':False,'authority_effect':'NONE'}
    if not a.operational:
        assert importlib.util.find_spec('cryptography') is None
        from mosaic_mmc_t3.statements import backend
        try:backend()
        except MMCError as e:assert e.code=='MMC_T3_SIGNING_DEPENDENCY'
        else:raise AssertionError('missing optional dependency falsely available')
        from mosaic_mmc_t2 import compile_domain
        assert compile_domain(fixture['bundle'])['body']['operational_eligibility']=='NOT_EVALUATED'
        result['missing_crypto']='EXPLICIT_REFUSAL'
    else:
        from cryptography.hazmat.primitives.asymmetric import ec
        import cryptography
        assert importlib.metadata.version('cryptography').split('.')[0]=='46', 'declared operational backend not installed'
        assert Path(cryptography.__file__).resolve().is_relative_to(prefix), 'crypto not isolated'
        bundle=fixture['bundle'];policy=fixture['policy'];plan=make_plan(bundle,policy)
        assert plan['root']==fixture['plan_root'] and realization()==fixture['evaluator_root']
        with tempfile.TemporaryDirectory() as d:
            c=Controller.create(Path(d)/'c.sqlite',policy);s=SimulatedStore.create(Path(d)/'s.sqlite','sim.installed',{v['target']:v['state'] for v in bundle['model']['initial_states']},floor=4,revoked=['revoked.key'])
            c.submit('migration.blue',bundle,expected_plan_root=fixture['plan_root'])
            for step,op in [('step.prepare','op.1'),('step.cutover','op.2'),('step.retire','op.3')]:
                for record in fixture['observations'][step]:c.observe('migration.blue',record)
                time={'now':100,'uncertainty':0};r=c.prepare('migration.blue',step,s,time,operation_id=op);approvals=[]
                for jurisdiction,scalar in [('authority.owner',2),('security',3)]:
                    key=ec.derive_private_key(scalar,ec.SECP256R1()) # PUBLIC fixture only
                    body={'schema':'mmc.statement.t3','kind':'approval','signer':public_hex(key),**scope(plan,'migration.blue',step),'issued_at':90,'expires_at':120,'sequence':4,'payload':{'request_root':digest('request',r),'context_root':r['context_root'],'jurisdiction':jurisdiction,'decision':'ALLOW'}}
                    approvals.append(seal(body,key))
                c.approve(op,approvals,time);outcome=c.commit(op,s,time,fault='lost_ack' if op=='op.1' else None)
                if op=='op.1':
                    assert outcome['status']=='UNKNOWN';c=Controller(Path(d)/'c.sqlite',expected_policy_root=digest('policy',policy));outcome=c.reconcile(op,s)
                assert outcome['status']=='APPLIED'
            assert len(c.replay()['projection']['migrations']['migration.blue']['completed'])==3
        result['operational_workflow']='PASS_SIGNED_SIMULATION_AND_LOST_ACK_RESTART'
        result['crypto_version']=importlib.metadata.version('cryptography')
        result['dependency_source']='EXACT_COPIES_OF_GENUINE_PREINSTALLED_DISTRIBUTIONS'
    cmd=Path(sys.executable).parent/'mmc-t3'
    p=subprocess.run([str(cmd),'capabilities'],capture_output=True,timeout=15)
    assert p.returncode==0 and decode(p.stdout)['profile']=='T3-O1'
    result['installed_cli']='PASS';Path(a.out).write_bytes(canonical(result));print(canonical(result).decode())
if __name__=='__main__':main()
