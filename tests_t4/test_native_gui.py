import copy,importlib,json,os,subprocess,sys,tempfile,unittest,zipfile,shutil
from pathlib import Path
from mosaic_mmc_t4.common import *
from mosaic_mmc_t4.integrations import native_read,_admit
from tests_t4.helpers import ROOT

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        inputs=(os.environ.get('MMC_QUALIFICATION_CMBA_A4_WHEEL'),os.environ.get('MMC_QUALIFICATION_DKN_RC5_WHEEL'))
        if not all(inputs):
            cls.tmp.cleanup();raise unittest.SkipTest('EXTERNAL_NATIVE_QUALIFICATION_WHEELS_NOT_SUPPLIED')
        for supplied in inputs:
            z=zipfile.ZipFile(Path(supplied))
            for i in z.infolist():
                p=cls.path/i.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(i))
        sys.path.insert(0,str(cls.path));importlib.invalidate_caches()
    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(cls.path))
        for n in list(sys.modules):
            if n.split('.')[0] in ('cmba_core','cmba_workbench','dkn_v02','dkn_core'):del sys.modules[n]
        cls.tmp.cleanup()
    def test_actual_cmba_read(self):
        cfg,m=_admit('cmba');from cmba_core.registry import contract
        v={'description':'test'};d=m.dimension('meta','metadata','example.metadata',v,critical=False);b=m.bind(m.profile_reference(contract('cmba.generic')),[d])
        r=native_read('cmba',{'binding':b,'values':{'meta':v}})
        self.assertEqual(r['status'],'NATIVE_REPORT_COMPUTED');self.assertEqual(r['native_result']['semantic_truth'],'NOT_ESTABLISHED')
    def test_actual_dkn_read(self):
        cfg,m=_admit('dkn');a,manifest=m.pack({'x.txt':b'hello'})
        r=native_read('dkn',{'archive_hex':a.hex(),'expected_root':manifest['logical_root']})
        self.assertEqual(r['native_result']['status'],'PASS');self.assertEqual(r['native_result']['authority_effect'],'NONE')
    def test_native_root_substitution(self):
        cfg,m=_admit('dkn');a,manifest=m.pack({'x.txt':b'hello'})
        with self.assertRaises(MMCError):native_read('dkn',{'archive_hex':a.hex(),'expected_root':'f'*64})
    def test_extra_native_source_refused(self):
        p=self.path/'cmba_core/unaccepted.py';p.write_text('raise RuntimeError("must not import")')
        try:
            with self.assertRaises(MMCError):_admit('cmba')
        finally:p.unlink()
    def test_native_source_mutation_refused(self):
        p=self.path/'cmba_core/__init__.py';raw=p.read_bytes();p.write_bytes(raw+b'\n# modified')
        try:
            with self.assertRaises(MMCError):_admit('cmba')
        finally:p.write_bytes(raw)

class GUIQualificationTests(unittest.TestCase):
    def test_actual_tk_interaction(self):
        with tempfile.TemporaryDirectory() as d:
            # The GUI smoke requires a real atomic export. Test the OS fixture
            # directly; never suppress arbitrary GUI/product failures.
            probe=Path(d)/'link-source';probe.write_bytes(b'fixture')
            try:os.link(probe,Path(d)/'link-destination')
            except OSError as error:
                if os.name=='nt' and getattr(error,'winerror',None)==5:
                    self.skipTest('HOST_FIXTURE_HARDLINK_DENIED:5')
                raise
            command=[sys.executable,str(ROOT/'tools_t4/gui_smoke.py'),'--out',d]
            if shutil.which('xvfb-run'):command=['xvfb-run','-a','-s','-screen 0 1440x1000x24',*command]
            p=subprocess.run(command,capture_output=True,timeout=40,env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
            self.assertEqual(p.returncode,0,p.stderr.decode('utf-8','replace'));r=decode((Path(d)/'GUI.json').read_bytes())
            self.assertEqual(r['status'],'PASS');self.assertGreaterEqual(r['count'],30);self.assertTrue((Path(d)/'workbench.png').exists())
