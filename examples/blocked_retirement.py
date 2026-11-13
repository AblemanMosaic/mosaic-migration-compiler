"""A source may assert success; T1 still requires live evidence and external authority."""
from pathlib import Path
from mosaic_mmc import canonical,decode,compile_model,verify_compilation,digest,MMCError
m=decode((Path(__file__).parent/'identity.json').read_bytes())
for o in m['objects']:
    if o['kind']=='Observation':o['attributes'].update(status='ASSERTED',value=True,coverage='DECLARED_COMPLETE',measured_at=1,valid_until=999999)
r=compile_model(m)
assert r['receipt']['body']['runtime_guards']==18
forged=decode(canonical(r));forged['receipt']['body']['eligibility']='AUTHORIZED'
forged['receipt']['root']=digest('compilation-receipt',forged['receipt']['body'])
try:verify_compilation(m,forged,expected_model_root=r['ir']['model_root'])
except MMCError as exc:assert exc.code=='MMC_COMPILATION_MISMATCH'
else:raise AssertionError('forged approval accepted')
for o in m['objects']:
    if o['id']=='need.drain':o['attributes']['rule']={'op':'literal','value':False}
blocked=compile_model(m)
assert blocked['receipt']['body']['status']=='COMPILED_WITH_STATIC_BLOCKERS'
assert blocked['receipt']['body']['static_blockers']==2
print(canonical({'status':'PASS_SCOPED_DEMONSTRATION','runtime_guards_before':18,'static_blockers_after':2,'forged_approval':'REFUSED','migration_execution':'NOT_IMPLEMENTED','authority_effect':'NONE'}).decode())
