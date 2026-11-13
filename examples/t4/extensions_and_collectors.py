"""Explicit local reads + host-installed finite extension qualification."""
from pathlib import Path
import sys,tempfile,sqlite3
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from mosaic_mmc import canonical
from mosaic_mmc_t4.sdk import Registry,handler_identity
from mosaic_mmc_t4.common import digest
from mosaic_mmc_t4.extensions import descriptor,residency_profile
from mosaic_mmc_t4.collectors import FileCollector,SQLiteCollector

def run():
    d=descriptor('residency');v={'schema':'mmc.residency-input.t4','allowed_regions':['zone-a'],'items':[{'id':'object.one','region':'zone-a'}]}
    cases=[{'id':'match','input':v,'expected':{'ok':True,'result':residency_profile(v)}},
           {'id':'bad-input','input':{'schema':'wrong'},'expected':{'ok':False,'error':'MMC_T4_EXTENSION_INPUT'}}]
    reg=Registry();receipt=reg.qualify(d,residency_profile,cases,expected_descriptor_root=digest('descriptor',d),expected_handler_hash=handler_identity(residency_profile))
    assert reg.call(receipt['body']['reference'],v)['status']=='MATCH_FOR_SUPPLIED_RECORDS'
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'state.json').write_bytes(canonical(v))
        capture=FileCollector(root,'selected.fixture',['state.json']).collect(observed_at=10)
        db=root/'db.sqlite';c=sqlite3.connect(db);c.execute('CREATE TABLE mmc_observations(id TEXT PRIMARY KEY,value TEXT)');c.execute('INSERT INTO mmc_observations VALUES (?,?)',('o1',canonical(v).decode()));c.commit();c.close()
        before=db.read_bytes();rows=SQLiteCollector(db,'selected.db').collect(observed_at=10)
        assert db.read_bytes()==before
    return {'status':'PASS','profile_reference':receipt['body']['reference'],'capture_root':capture['root'],'rows':len(rows['body']['value']['rows']),'claims':'SUPPLIED_RECORDS_NOT_PHYSICAL_RESIDENCY','effects':'TEMPORARY_TEST_FIXTURE_CREATION_AND_EXPLICIT_READS','authority_effect':'NONE'}
if __name__=='__main__':print(canonical(run()).decode())
