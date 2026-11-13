import copy,http.server,json,os,socketserver,sqlite3,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from mosaic_mmc_t4.collectors import *
from mosaic_mmc_t4.sdk import Registry,handler_identity
from mosaic_mmc_t4.extensions import descriptor,residency_profile,job_observer

class CollectorTests(unittest.TestCase):
    def test_file_inventory_actual_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a';p.write_bytes(b'abc');before=sorted(Path(d).iterdir())
            r=FileCollector(d,'fixture',['a']).collect(observed_at=3)
            self.assertEqual(r['body']['value']['files'][0]['sha256'],hashlib.sha256(b'abc').hexdigest())
            self.assertEqual(r['body']['evidence_label'],'CAPTURED_UNAUTHENTICATED');self.assertEqual(sorted(Path(d).iterdir()),before)
    def test_json_capture(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'a.json').write_text('{"x": 3}')
            self.assertEqual(JsonFileCollector(d,'a.json','fixture').collect(observed_at=5)['body']['value'],{'x':3})
    def test_json_duplicate_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'a.json').write_text('{"x": 3,"x":4}')
            with self.assertRaises(MMCError):JsonFileCollector(d,'a.json','fixture').collect(observed_at=5)
    def test_missing_not_empty(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(MMCError):FileCollector(d,'fixture',['missing']).collect(observed_at=3)
    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'target').write_bytes(b'x');(p/'link').symlink_to(p/'target')
            with self.assertRaises(MMCError):FileCollector(d,'fixture',['link'])
    def test_fifo_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pipe';os.mkfifo(p)
            with self.assertRaises(MMCError):FileCollector(d,'fixture',['pipe']).collect(observed_at=3)
    def test_aggregate_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'a').write_bytes(b'x'*600000);(p/'b').write_bytes(b'x'*600000)
            with self.assertRaises(MMCError):FileCollector(d,'fixture',['a','b']).collect(observed_at=3)
    def database(self,d,rows):
        p=Path(d)/'observations.sqlite';c=sqlite3.connect(p);c.execute('CREATE TABLE mmc_observations(id TEXT PRIMARY KEY,value TEXT)')
        c.executemany('INSERT INTO mmc_observations VALUES (?,?)',rows);c.commit();c.close();return p
    def test_sqlite_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.database(d,[('o1','{"x":1}')]);before=p.read_bytes();names=sorted(x.name for x in p.parent.iterdir())
            r=SQLiteCollector(p,'db').collect(observed_at=1)
            self.assertEqual(r['body']['value']['rows'][0]['value'],{'x':1});self.assertEqual(p.read_bytes(),before);self.assertEqual(names,sorted(x.name for x in p.parent.iterdir()))
    def test_sqlite_no_create(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'absent'
            with self.assertRaises(MMCError):SQLiteCollector(p,'db')
            self.assertFalse(p.exists())
    def test_sqlite_view_not_table(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'db';c=sqlite3.connect(p);c.execute('CREATE VIEW mmc_observations AS SELECT 1 AS id,2 AS value');c.close()
            with self.assertRaises(MMCError):SQLiteCollector(p,'db').collect(observed_at=1)
    def test_sqlite_row_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.database(d,[(f'id{i}','{}') for i in range(513)])
            with self.assertRaises(MMCError):SQLiteCollector(p,'db').collect(observed_at=1)
    def test_sqlite_wal_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.database(d,[]);Path(str(p)+'-wal').write_bytes(b'x')
            with self.assertRaises(MMCError):SQLiteCollector(p,'db').collect(observed_at=1)
    def test_release_correspondence(self):
        x={'schema':'mmc.release-record.t4','artifact_root':'a'*64,'source_root':'b'*64,'toolchain_root':'c'*64};e={k:v for k,v in x.items() if k!='schema'}
        self.assertEqual(assess_record('release',x,e)['status'],'MATCH_FOR_SUPPLIED_RECORDS');e['toolchain_root']='f'*64
        self.assertEqual(assess_record('release',x,e)['status'],'CONTRADICTED')
    def test_repository_revision(self):
        v={'schema':'mmc.repository-record.t4','revision':'commit.a','files':[]}
        self.assertEqual(assess_record('repository',v,{'revision':'commit.a'})['status'],'MATCH_FOR_SUPPLIED_RECORDS')
        self.assertEqual(assess_record('repository',v,{'revision':'commit.b'})['status'],'CONTRADICTED')
    def test_deployment_roster(self):
        x={'schema':'mmc.deployment-record.t4','cohort':'blue','instances':[{'id':'p1','version':'new','ready':True}]};e={'cohort':'blue','version':'new','instance_ids':['p1']}
        self.assertEqual(assess_record('deployment',x,e)['status'],'MATCH_FOR_SUPPLIED_RECORDS');e['instance_ids'].append('p2')
        self.assertEqual(assess_record('deployment',x,e)['details']['missing'],['p2'])
    def test_jobs_dormant_risk(self):
        x={'schema':'mmc.job-input.t4','jobs':[{'id':'sleeper','version':'legacy','resumable':True,'fenced':False,'pending_writes':0}]}
        self.assertEqual(job_observer(x)['status'],'LEGACY_WRITERS_POSSIBLE');x['jobs'][0]['fenced']=True
        self.assertEqual(job_observer(x)['status'],'NONE_IN_SUPPLIED_SNAPSHOT')

for name in ['../escape','/absolute','a//b','a/./b','C:stream','a\\b']:
    def test(self,name=name):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(MMCError):FileCollector(d,'fixture',[name])
    setattr(CollectorTests,'test_path_'+str(len(CollectorTests.__dict__)),test)

class Handler(http.server.BaseHTTPRequestHandler):
    mode='good';calls=0
    def log_message(self,*a):pass
    def do_GET(self):
        type(self).calls+=1
        if self.mode=='redirect':self.send_response(302);self.send_header('Location','http://127.0.0.1:1/private');self.end_headers();return
        raw=b'{"captured":true}' if self.mode!='large' else b'a'*(MAX_BYTES+1)
        self.send_response(200);self.send_header('Content-Type','text/html' if self.mode=='html' else 'application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers()
        try:self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):pass

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}/observation'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def run_mode(self,mode):
        Handler.mode=mode
        return HttpCollector(self.url,'loopback',allow_loopback_http=True).collect(observed_at=8)
    def test_actual_loopback_get(self):self.assertEqual(self.run_mode('good')['body']['value'],{'captured':True})
    def test_redirect_refused(self):
        with self.assertRaises(MMCError):self.run_mode('redirect')
    def test_content_type_refused(self):
        with self.assertRaises(MMCError):self.run_mode('html')
    def test_body_limit(self):
        with self.assertRaises(MMCError):self.run_mode('large')
    def test_ambient_proxy_disabled(self):
        with patch.dict(os.environ,{'HTTP_PROXY':'http://127.0.0.1:1','HTTPS_PROXY':'http://127.0.0.1:1','NO_PROXY':''}):
            self.assertEqual(self.run_mode('good')['body']['kind'],'http-json')
    def test_http_requires_host_opt_in(self):
        with self.assertRaises(MMCError):HttpCollector(self.url,'loopback')
    def test_nonlocal_http_refuses(self):
        with self.assertRaises(MMCError):HttpCollector('http://example.com/a','remote',allow_loopback_http=True)
    def test_file_scheme_refuses(self):
        with self.assertRaises(MMCError):HttpCollector('file:///etc/passwd','x')
    def test_credentials_refuse(self):
        with self.assertRaises(MMCError):HttpCollector('https://user:pass@example.com/a','x')

class SDKTests(unittest.TestCase):
    def setup_registry(self):
        reg=Registry();d=descriptor('residency');good={'schema':'mmc.residency-input.t4','allowed_regions':['us'],'items':[{'id':'a','region':'us'}]}
        cases=[{'id':'positive','input':good,'expected':{'ok':True,'result':residency_profile(good)}},
               {'id':'negative','input':{'schema':'bad'},'expected':{'ok':False,'error':'MMC_T4_EXTENSION_INPUT'}}]
        return reg,d,good,cases
    def qualify(self,reg,d,cases,handler=residency_profile):return reg.qualify(d,handler,cases,expected_descriptor_root=digest('descriptor',d),expected_handler_hash=handler_identity(handler))
    def test_new_profile_qualified_without_kernel_change(self):
        reg,d,v,cases=self.setup_registry();receipt=self.qualify(reg,d,cases)
        self.assertEqual(reg.call(receipt['body']['reference'],v)['status'],'MATCH_FOR_SUPPLIED_RECORDS');self.assertEqual(receipt['body']['independent_review'],'NOT_PERFORMED')
    def test_new_observer_qualified(self):
        reg=Registry();d=descriptor('jobs');v={'schema':'mmc.job-input.t4','jobs':[]}
        cases=[{'id':'pos','input':v,'expected':{'ok':True,'result':job_observer(v)}},{'id':'neg','input':{'schema':'bad'},'expected':{'ok':False,'error':'MMC_T4_EXTENSION_INPUT'}}]
        r=self.qualify(reg,d,cases,job_observer);self.assertEqual(reg.call(r['body']['reference'],v)['coverage'],'SUPPLIED_SNAPSHOT_ONLY')
    def test_no_string_handler(self):
        reg,d,v,cases=self.setup_registry()
        with self.assertRaises(MMCError):reg.qualify(d,'os.system',cases,expected_descriptor_root=digest('descriptor',d),expected_handler_hash='a'*64)
    def test_handler_pin(self):
        reg,d,v,cases=self.setup_registry()
        with self.assertRaises(MMCError):reg.qualify(d,residency_profile,cases,expected_descriptor_root=digest('descriptor',d),expected_handler_hash='a'*64)
    def test_descriptor_pin(self):
        reg,d,v,cases=self.setup_registry()
        with self.assertRaises(MMCError):reg.qualify(d,residency_profile,cases,expected_descriptor_root='a'*64,expected_handler_hash=handler_identity(residency_profile))
    def test_wrong_expected_not_regenerated(self):
        reg,d,v,cases=self.setup_registry();cases[0]['expected']['result']['status']='PASS_EVERYTHING'
        with self.assertRaises(MMCError):self.qualify(reg,d,cases)
    def test_bool_int_oracle(self):
        reg,d,v,cases=self.setup_registry();cases[0]['expected']['ok']=1
        with self.assertRaises(MMCError):self.qualify(reg,d,cases)
    def test_missing_negative(self):
        reg,d,v,cases=self.setup_registry();cases[1]={'id':'copy','input':v,'expected':cases[0]['expected']}
        with self.assertRaises(MMCError):self.qualify(reg,d,cases)
    def test_input_descriptor_cannot_import(self):
        reg,d,v,cases=self.setup_registry();d['module']='os'
        with self.assertRaises(MMCError):self.qualify(reg,d,cases)
    def test_ref_substitution(self):
        reg,d,v,cases=self.setup_registry();r=self.qualify(reg,d,cases);r['body']['reference']['version']='2'
        with self.assertRaises(MMCError):reg.call(r['body']['reference'],v)
