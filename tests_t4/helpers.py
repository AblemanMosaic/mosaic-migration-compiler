from pathlib import Path
import copy
from mosaic_mmc import canonical,decode,MMCError
from tests_t3.helpers import bundle,policy,observations,make_plan,keys,TIME,statement,resign,Env
from mosaic_mmc_t4.views import snapshot,reader_for_sample
from mosaic_mmc_t4.work import make_work_order,review_submission
from mosaic_mmc_t4.common import digest,envelope
ROOT=Path(__file__).resolve().parents[1]

def scenario(missing='coverage'):
    b=bundle();p=policy(b);plan=make_plan(b,p);records=observations(plan)
    s=snapshot(plan,p,'migration.blue','step.prepare',[r for r in records if r['body']['payload']['claim']!=missing])
    reader=reader_for_sample(s)
    w=make_work_order(s,reader,missing,[])
    record=next(r for r in records if r['body']['payload']['claim']==missing)
    sub={'schema':'mmc.agent-submission.t4','work_order_root':w['root'],'record':record,'notes':'PUBLIC FIXTURE'}
    return s,reader,w,sub

def review(s,r,w,sub):return review_submission(s,r,w,sub,expected_work_root=w['root'])

def workspace(s):return {'schema':'mmc.workspace.t4','snapshot':copy.deepcopy(s),'history':[],'journal':None}
