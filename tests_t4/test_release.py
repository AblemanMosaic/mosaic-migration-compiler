"""Release, schema and oracle checks. No acceptance of unexecuted native integration."""
from pathlib import Path
import copy,hashlib,json,tempfile,unittest
from unittest.mock import patch
from mosaic_mmc import canonical,decode,MMCError
from tools.common import read_json,save_json,sha
from tools_t4 import qualify as q
ROOT=Path(__file__).resolve().parents[1]
CORPUS=read_json(ROOT/'interop/t4-known-answers.json')

class VectorTests(unittest.TestCase):pass
for case in CORPUS['cases']:
    def test(self,c=case):
        from tools_t4.check_vectors import invoke
        self.assertEqual(canonical(invoke(c['request'])),canonical(c['expected']))
    setattr(VectorTests,'test_'+case['id'].replace('-','_'),test)

class ReleaseTests(unittest.TestCase):
    def test_vector_lock(self):
        lock=read_json(ROOT/'provenance/turn4/VECTOR-LOCK.json')
        self.assertEqual(lock['sha256'],sha(ROOT/'interop/t4-known-answers.json'))
        self.assertEqual(lock['cases'],len(CORPUS['cases']))
    def test_original_runtime_exact(self):
        self.assertEqual(q.preservation()['runtime_files'],57)
    def test_admission_before_collection(self):
        with tempfile.TemporaryDirectory() as d,patch.object(q,'verify_source',side_effect=MMCError('EXPECTED_REFUSAL')),patch.object(q.unittest.TestLoader,'discover') as collect:
            with self.assertRaises(MMCError):q.run_test_group(Path(d),'f'*64,'t4')
            collect.assert_not_called()
    def test_exact_type_equality(self):
        with self.assertRaises(MMCError):q.exact({'n':True},{'n':1},'REFUSE_BOOL')
    def test_closed_groups(self):
        self.assertEqual(q.GROUPS,{'t1':'tests','t2':'tests_t2','t3':'tests_t3','t4':'tests_t4'})
    def test_no_duplicate_registered_test(self):
        ids=sum(q.expected_ids().values(),[]);self.assertEqual(len(ids),len(set(ids)))
    def test_native_case_not_locally_passed(self):
        self.assertNotIn('AC-REPRO-06',q.registry()['acceptance'])
        self.assertEqual(len(q.registry()['acceptance']),8)
    def test_structural_schema_exports(self):
        from mosaic_mmc_t4.schemas import schemas
        import jsonschema
        for name,body in schemas().items():
            jsonschema.Draft202012Validator.check_schema(body)
            self.assertEqual(canonical(body),(ROOT/'schemas/t4'/f'{name}.schema.json').read_bytes())
    def test_source_package_bool_size_refused(self):
        from tools.package import zip_bytes,verify_source_archive
        # Deliberately malformed independent tiny archive; verifier must not promote bool.
        m={'schema':'mmc.source-inventory.t1','files':[{'path':'a','bytes':True,'sha256':hashlib.sha256(b'x').hexdigest()}]}
        with self.assertRaises(MMCError):verify_source_archive(zip_bytes({'a':b'x','FILE-MANIFEST.json':canonical(m)}))

    def _part(self,d):
        ids=['test.example'];root='a'*64;out=Path(d)
        save_json(out/'t4-tests.json',{'schema':'mmc.test-results.t4','source_root':root,'elapsed_ns':1,'tests':[{'id':ids[0],'status':'PASS'}],'counts':q.counts(1)})
        (out/'t4-tests.txt').write_text('synthetic verifier test only')
        p={'schema':'mmc.test-part.t4','group':'t4','source_root':root,'environment':q.environment(),'collected':ids,'terminal_exit':0,'counts':q.counts(1),'outputs':[{'path':n,'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in ['t4-tests.json','t4-tests.txt']],'authority_effect':'NONE','signature':'NOT_SIGNED'}
        save_json(out/'t4-PART.json',p);return p,out,root,ids
    def test_part_positive_verifier_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d)
            with patch.object(q,'expected_ids',return_value={'t4':ids}):self.assertEqual(q.verify_part(out,root,'t4'),p)
    def test_part_output_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d);(out/'t4-tests.txt').write_text('changed')
            with patch.object(q,'expected_ids',return_value={'t4':ids}),self.assertRaises(MMCError):q.verify_part(out,root,'t4')
    def test_part_identity_wrong_even_with_new_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d);r=read_json(out/'t4-tests.json');r['tests'][0]['id']='test.unrelated';save_json(out/'t4-tests.json',r)
            p['outputs'][0]={'path':'t4-tests.json','bytes':(out/'t4-tests.json').stat().st_size,'sha256':sha(out/'t4-tests.json')};save_json(out/'t4-PART.json',p)
            with patch.object(q,'expected_ids',return_value={'t4':ids}),self.assertRaises(MMCError):q.verify_part(out,root,'t4')

for key,value in [('schema','unrelated'),('group','t1'),('source_root','b'*64),('terminal_exit',True),('terminal_exit',2),('counts',{'PASS':True,'FAIL':0,'ERROR':0,'SKIP':0}),('authority_effect','EXECUTE'),('signature','SIGNED'),('collected',['test.unrelated'])]:
    def test(self,key=key,value=value):
        with tempfile.TemporaryDirectory() as d:
            p,out,root,ids=self._part(d);p[key]=value;save_json(out/'t4-PART.json',p)
            with patch.object(q,'expected_ids',return_value={'t4':ids}),self.assertRaises(MMCError):q.verify_part(out,root,'t4')
    setattr(ReleaseTests,'test_part_mutation_'+str(len(ReleaseTests.__dict__)),test)
