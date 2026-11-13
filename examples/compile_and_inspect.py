"""Read-only demonstration: runtime obligations remain unresolved after compilation."""
from pathlib import Path
from mosaic_mmc import decode, compile_model, verify_compilation, canonical

root=Path(__file__).resolve().parent
for name in ['identity','storage','policy','workload']:
    model=decode((root/(name+'.json')).read_bytes())
    result=compile_model(model)
    verified=verify_compilation(model,result,expected_model_root=result['ir']['model_root'])
    assert [s['id'] for s in result['ir']['steps']]==['step.prepare','step.cutover','step.retire']
    assert result['receipt']['body']['runtime_guards']==18
    assert verified['eligibility']=='NOT_EVALUATED'
    assert result['ir']['steps'][-1]['effects_status']=='NOT_EXECUTED'
    print(canonical({'example':name,'status':result['receipt']['body']['status'],
                     'runtime_guards':18,'replay':verified['status'],'authority_effect':'NONE'}).decode())
