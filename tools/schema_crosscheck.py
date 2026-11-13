"""Optional development cross-check against installed JSON Schema implementation, not a runtime dependency."""
from pathlib import Path
import importlib.metadata
try:from .common import ROOT,read_json,canonical
except ImportError:from common import ROOT,read_json,canonical
from mosaic_mmc import compile_model,validate_model

def main():
    import jsonschema
    from referencing import Registry,Resource
    schemas=[read_json(p) for p in sorted((ROOT/'schemas').glob('*.schema.json'))]
    registry=Registry().with_resources([(s['$id'],Resource.from_contents(s)) for s in schemas])
    byid={s['$id']:s for s in schemas}
    count=0
    for domain in ['identity','storage','policy','workload']:
        m=read_json(ROOT/'examples'/f'{domain}.json');c=compile_model(m)
        for ident,value in [('urn:mmc:model:t1',m),('urn:mmc:ir:t1',c['ir']),('urn:mmc:compilation:t1',c),('urn:mmc:request:t1',{'schema':'mmc.request.t1','operation':'compile','arguments':{'model':m}})]:
            jsonschema.Draft202012Validator(byid[ident],registry=registry).validate(value);count+=1
    print(canonical({'schema':'mmc.optional-schema-crosscheck.t1','status':'PASS_SHAPE_ONLY','checks':count,'jsonschema':importlib.metadata.version('jsonschema'),'claim_ceiling':'SHAPE_NOT_HASH_OR_SCOPE_OR_LOWERING'}).decode())
if __name__=='__main__':main()
