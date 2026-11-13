from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from mosaic_mmc import decode,canonical
from mosaic_mmc_t2 import compile_domain,verify_compilation
R=Path(__file__).parent
results=[]
for domain in ('identity','storage','policy','workload'):
    b=decode((R/(domain+'.json')).read_bytes());result=compile_domain(b)
    assert result['body']['status']=='COMPILED_WITH_RUNTIME_OBLIGATIONS'
    verify_compilation(b,result,expected_model_root=result['body']['model_root'])
    runtime=sum(g.get('compile_state')=='RUNTIME_REQUIRED' for s in result['body']['instructions'] for g in s['guards'])
    assert runtime==18
    results.append({'domain':domain,'root':result['root'],'runtime_guards_retained':runtime,'effects':'NOT_EXECUTED'})
print(canonical({'schema':'mmc.t2-example','results':results,'authority_effect':'NONE'}).decode())
