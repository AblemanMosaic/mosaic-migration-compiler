"""Invoke using the isolated installed interpreter and copied JSON fixtures, outside source."""
import argparse,hashlib,importlib.metadata,importlib.util,json,sys,zipfile
from pathlib import Path
from mosaic_mmc import canonical,decode
from mosaic_mmc.contracts import realization_identity as base_identity
from mosaic_mmc_t2 import compile_domain,verify_compilation,assess_retirement

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',required=True);p.add_argument('--wheel',required=True);a=p.parse_args()
    import mosaic_mmc,mosaic_mmc_t2
    for m in (mosaic_mmc,mosaic_mmc_t2):assert Path(m.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert importlib.metadata.version('mosaic-migration-compiler')=='0.1.0a2'
    assert base_identity()=='b8387cf06a06e26b290b8c3827c644068defd4ce8484167de98186d87452ee64'
    absent={n:importlib.util.find_spec(n) is None for n in ('cryptography','jsonschema','pytest','blake3')};assert all(absent.values())
    results=[]
    for domain in ('identity','storage','policy','workload'):
        b=decode((Path(a.fixtures)/(domain+'.json')).read_bytes());c=compile_domain(b)
        assert c['body']['status']=='COMPILED_WITH_RUNTIME_OBLIGATIONS'
        verify_compilation(b,c,expected_model_root=c['body']['model_root'])
        assert assess_retirement(b['model'],b['retirements'][0]['record'])['operational_eligibility']=='NOT_EVALUATED'
        results.append({'domain':domain,'status':'PASS'})
    checked=[]
    with zipfile.ZipFile(a.wheel) as z:
        dist=importlib.metadata.distribution('mosaic-migration-compiler')
        for n in z.namelist():
            if n.startswith(('mosaic_mmc/','mosaic_mmc_t2/')):
                actual=Path(dist.locate_file(n)).read_bytes();assert actual==z.read(n);checked.append(n)
    print(canonical({'schema':'mmc.installed-smoke.t2','status':'PASS','python':sys.version.split()[0],'prefix':sys.prefix,'package_files':len(checked),'files':checked,'runtime_third_party_absent':absent,'workflows':results,'authority_effect':'NONE','native_pippi':'NOT_BOUND'}).decode())
if __name__=='__main__':main()
