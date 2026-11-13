import copy,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from mosaic_mmc_t4.exports import LocalExport
from mosaic_mmc_t4.common import *
from tests_t4.helpers import scenario,workspace

class ExportTests(unittest.TestCase):
    def value(self):return workspace(scenario()[0])
    def test_prepare_cancel_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            e=LocalExport(d);p=e.prepare(self.value(),'data.json');self.assertEqual(list(Path(d).iterdir()),[]);e.cancel()
            with self.assertRaises(MMCError):e.approve(p['root'])
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_one_use_host_token(self):
        with tempfile.TemporaryDirectory() as d:
            e=LocalExport(d);v=self.value();p=e.prepare(v,'data.json');a=e.approve(p['root']);r=e.commit(a)
            self.assertEqual((Path(d)/'data.json').read_bytes(),canonical(v));self.assertEqual(r['host_effect'],'CREATE_LOCAL_FILE')
            with self.assertRaises(MMCError):e.commit(a)
    def test_fake_json_approval(self):
        with tempfile.TemporaryDirectory() as d:
            e=LocalExport(d);p=e.prepare(self.value(),'data.json')
            with self.assertRaises(MMCError):e.commit({'plan_root':p['root'],'approved':True})
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'data.json';f.write_bytes(b'existing');e=LocalExport(d)
            with self.assertRaises(MMCError):e.prepare(self.value(),'data.json')
            self.assertEqual(f.read_bytes(),b'existing')
    def test_target_appears_after_approval(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'data.json';e=LocalExport(d);p=e.prepare(self.value(),'data.json');a=e.approve(p['root']);f.write_bytes(b'other')
            with self.assertRaises(MMCError):e.commit(a)
            self.assertEqual(f.read_bytes(),b'other')
    def test_context_change_invalidates(self):
        with tempfile.TemporaryDirectory() as d:
            state=[0];e=LocalExport(d,state_token=lambda:state[0]);p=e.prepare(self.value(),'data.json');a=e.approve(p['root']);state[0]=1
            with self.assertRaises(MMCError):e.commit(a)
    def test_expiry_rechecked_after_stage(self):
        with tempfile.TemporaryDirectory() as d:
            now=[100.0];e=LocalExport(d,clock=lambda:now[0]);p=e.prepare(self.value(),'data.json',ttl=10);a=e.approve(p['root'])
            actual=os.fsync
            def late(fd):actual(fd);now[0]=111
            with patch('mosaic_mmc_t4.exports.os.fsync',late):
                with self.assertRaises(MMCError):e.commit(a)
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_display_plan_mutation_cannot_change_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            e=LocalExport(d);v=self.value();p=e.prepare(v,'data.json');root=p['root'];p['body']['name']='other.json';v['history']=['changed']
            e.commit(e.approve(root));self.assertTrue((Path(d)/'data.json').exists());self.assertFalse((Path(d)/'other.json').exists())
    def test_postcommit_readback_uncertainty(self):
        with tempfile.TemporaryDirectory() as d:
            e=LocalExport(d);p=e.prepare(self.value(),'data.json');a=e.approve(p['root'])
            with patch('mosaic_mmc.cli.read_local',side_effect=OSError('fault')):r=e.commit(a)
            self.assertTrue((Path(d)/'data.json').is_file());self.assertEqual(r['status'],'LOCAL_FILE_CREATED_WITH_UNCERTAINTY')
    def test_unsupported_install_no_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            e=LocalExport(d);p=e.prepare(self.value(),'data.json');a=e.approve(p['root'])
            with patch('mosaic_mmc_t4.exports.os.link',side_effect=OSError('unsupported')):
                with self.assertRaises(MMCError):e.commit(a)
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_new_prepare_cancels_previous(self):
        with tempfile.TemporaryDirectory() as d:
            e=LocalExport(d);p=e.prepare(self.value(),'data.json');a=e.approve(p['root']);e.prepare(self.value(),'new.json')
            with self.assertRaises(MMCError):e.commit(a)
    def test_directory_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'real').mkdir();(p/'link').symlink_to(p/'real',target_is_directory=True)
            with self.assertRaises(MMCError):LocalExport(p/'link')

for n in ('../x.json','/x.json','CON.json','NUL.json','a..b.json','x.exe','hidden/.x.json','a:b.json'):
    def test(self,n=n):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(MMCError):LocalExport(d).prepare(self.value(),n)
    setattr(ExportTests,'test_bad_name_'+str(len(ExportTests.__dict__)),test)
