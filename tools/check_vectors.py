"""Exact frozen vectors. Never regenerates expectations."""
from pathlib import Path
try:from .common import ROOT,read_json,canonical,require
except ImportError:from common import ROOT,read_json,canonical,require
from mosaic_mmc import decode,digest,validate_model,compile_model,MMCError

def check():
    vectors=read_json(ROOT/'interop/known-answers.json')
    rows=[]
    for v in vectors['cases']:
        op=v['op'];actual=None
        try:
            if op=='canonical':actual={'hex':canonical(v['value']).hex()}
            elif op=='digest':actual={'hex':digest(v['domain'],v['value'])}
            elif op=='decode':actual={'value':decode(bytes.fromhex(v['input_hex']),canonical_only=True)}
            elif op=='model':
                m=validate_model(read_json(ROOT/v['file']));c=compile_model(m)
                actual={'model_root':digest('canonical-model',m),'steps':[s['id'] for s in c['ir']['steps']],
                        'runtime_guards':c['receipt']['body']['runtime_guards'],'eligibility':c['receipt']['body']['eligibility']}
            else:raise ValueError('unknown fixture operation')
        except MMCError as exc:actual={'refusal':exc.code}
        require(canonical(actual)==canonical(v['expected']),'MMC_VECTOR_MISMATCH',v['id'])
        rows.append({'id':v['id'],'status':'PASS'})
    return {'schema':'mmc.vector-results.t1','status':'PASS','cases':rows,'authority_effect':'NONE',
            'oracle':'AUTHORED_CODEC_EXPECTATIONS_REFERENCE_ASSISTED_MODEL_ROOTS','independent_implementation':False}
if __name__=='__main__':print(canonical(check()).decode())
