"""Qualification/source-boundary regressions, separate from runtime security claims."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.common import save_json,read_json,sha,canonical
from tools_t3 import qualify as q
from tools_t3.export_schemas import schemas
from tools_t3.check_vectors import invoke,check
from mosaic_mmc import MMCError
from tests_t3.helpers import Env,TIME,approvals,bundle,policy,make_plan,observations
ROOT=Path(__file__).resolve().parents[1]

class QualificationTests(unittest.TestCase):
    def stage(self,d):
        out=Path(d);source='a'*64
        for n in q.OUTPUTS['examples']:
            if n!='examples.json':(out/n).write_text('')
        result={'runs':[{'script':s,'exit_code':0} for s in q.EXAMPLES]}
        save_json(out/'examples.json',{'schema':'mmc.examples.t3','source_root':source,**result})
        q.record(out,'examples',source,result,0);return out,source
    def test_valid_stage(self):
        with tempfile.TemporaryDirectory() as d:
            out,s=self.stage(d);self.assertEqual(q.verify_stage(out,'examples',s)['terminal_exit'],0)
    def test_output_bytes_changed(self):
        with tempfile.TemporaryDirectory() as d:
            out,s=self.stage(d);(out/'example-0.stdout.txt').write_text('tampered')
            with self.assertRaises(MMCError):q.verify_stage(out,'examples',s)
    def test_extra_file_refused(self):
        with tempfile.TemporaryDirectory() as d:
            out,s=self.stage(d);(out/'extra.txt').write_text('')
            with self.assertRaises(MMCError):q.verify_stage(out,'examples',s)
    def test_missing_stage_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            out,s=self.stage(d);(out/'example-0.stdout.txt').unlink()
            with self.assertRaises(MMCError):q.verify_stage(out,'examples',s)
    def test_duplicate_status_field_refused(self):
        with tempfile.TemporaryDirectory() as d:
            out,s=self.stage(d);p=out/'STAGE.json';p.write_bytes(p.read_bytes()[:-1]+b',"terminal_exit":0}')
            with self.assertRaises(MMCError):q.verify_stage(out,'examples',s)
    def test_rehashed_bool_exit_not_integer_zero(self):
        with tempfile.TemporaryDirectory() as d:
            out,s=self.stage(d);p=out/'examples.json';r=read_json(p);r['runs'][0]['exit_code']=False;save_json(p,r);stage=read_json(out/'STAGE.json');stage['result']['runs'][0]['exit_code']=False
            for row in stage['outputs']:
                if row['path']=='examples.json':row.update(bytes=p.stat().st_size,sha256=sha(p))
            save_json(out/'STAGE.json',stage)
            with self.assertRaises(MMCError):q.verify_stage(out,'examples',s)
    def test_schema_exports_exact(self):
        for n,s in schemas().items():self.assertEqual(read_json(ROOT/f'schemas/t3/{n}.schema.json'),s)
    def test_schema_valid_examples(self):
        import jsonschema
        ss=schemas()
        for s in ss.values():jsonschema.Draft202012Validator.check_schema(s)
        with tempfile.TemporaryDirectory() as d:
            e=Env(d);r=e.prepare();a=e.approve(r)
            samples={'policy':e.policy,'statement':observations(e.plan)[0],'effect-request':r,'plan':e.plan,'evidence-court':e.controller.assess(e.mid,'step.prepare',TIME),'authority-court':a,'journal-event':e.controller.journal.export()[0],'clock':TIME,'adapter':e.store.descriptor(),'request':{'schema':'mmc.request.t3','operation':'capabilities','arguments':{}}}
            for n,v in samples.items():jsonschema.validate(v,ss[n])
    def test_schema_is_not_signature_verification(self):
        import jsonschema
        from mosaic_mmc_t3 import verify
        r=observations(make_plan(bundle(),policy()))[0];r['signature']='00'*32
        jsonschema.validate(r,schemas()['statement'])
        with self.assertRaises(MMCError):verify(r)
    def test_source_closure_extra_hook_refuses(self):
        from tools.common import source_snapshot,verify_source
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'a.py').write_text('pass\n');pin=source_snapshot(root)['root'];(root/'conftest.py').write_text('pass\n')
            with self.assertRaises(MMCError):verify_source(root,pin)
    def test_package_and_wheel_are_deterministic(self):
        from tools_t3.package import build_wheel
        self.assertEqual(build_wheel(),build_wheel())
    def test_predecessor_runtime_preserved(self):self.assertEqual(q.preservation()['runtime_files'],47)
    def test_vector_oracle_rejects_changed_result(self):
        c=copy.deepcopy(read_json(ROOT/'interop/t3-known-answers.json')['cases'][0]);c['expected']['result']['authority_effect']='EXECUTE'
        self.assertNotEqual(canonical(invoke(c['request'])),canonical(c['expected']))
    def test_frozen_vectors_pass(self):self.assertEqual(len(check()['cases']),24)

for field,value in [('schema','unrelated'),('phase','tests'),('source_root','b'*64),('authority_effect','EXECUTE'),('terminal_exit',False),('signature','SIGNED')]:
    def test(self,field=field,value=value):
        with tempfile.TemporaryDirectory() as d:
            out,s=self.stage(d);r=read_json(out/'STAGE.json');r[field]=value;save_json(out/'STAGE.json',r)
            with self.assertRaises(MMCError):q.verify_stage(out,'examples',s)
    setattr(QualificationTests,'test_stage_substitution_'+field,test)
