"""PUBLIC FIXTURE: actual evidence-only agent/host round trip. No target operation."""
from pathlib import Path
import sys,tempfile
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests_t3.helpers import Env,observations,TIME
from mosaic_mmc_t4 import AgentHost,make_work_order,review_submission
from mosaic_mmc_t4.views import reader_for_sample
from mosaic_mmc import canonical

def run():
    with tempfile.TemporaryDirectory() as d:
        e=Env(d);host=AgentHost(e.controller);records=observations(e.plan)
        for r in records[1:]:e.controller.observe(e.mid,r)
        s=host.capture(e.mid,'step.prepare');reader=reader_for_sample(s)
        work=make_work_order(s,reader,'coverage',[],30)
        submission={'schema':'mmc.agent-submission.t4','work_order_root':work['root'],'record':records[0],'notes':'Public fixture observation; not an actual production discovery.'}
        before=e.store.path.read_bytes()
        result=review_submission(s,reader,work,submission,expected_work_root=work['root'])
        assert result['body']['before']['body']['status']=='INDETERMINATE'
        assert result['body']['after']['body']['status']=='EVIDENCE_SATISFIES_SELECTED_POLICY'
        host.admit(e.mid,'step.prepare',reader,work,submission,expected_head=s['head'],expected_work_root=work['root'])
        assert e.controller.assess(e.mid,'step.prepare',TIME)['body']['status']=='EVIDENCE_SATISFIES_SELECTED_POLICY'
        assert e.controller.replay()['projection']['operations']=={}
        assert e.store.path.read_bytes()==before
        return {'status':'PASS','scenario':'PUBLIC_FIXTURE','work_order_bytes':len(canonical(work)),'full_snapshot_bytes':len(canonical(s)),
                'context_measure':'BYTES_NOT_AGENT_TOKEN_OR_PRODUCTIVITY_MEASUREMENT','host_effect':'EVIDENCE_JOURNAL_APPEND','target_effect':'NONE','authority_effect':'NONE'}
if __name__=='__main__':print(canonical(run()).decode())
