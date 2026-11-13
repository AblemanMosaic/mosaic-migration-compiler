from pathlib import Path
import sys,copy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mosaic_mmc import decode,MMCError
from examples.t2.make_models import records,worker,retirement,routes,simple_planning

def bundle(domain='identity'):return decode((ROOT/f'examples/t2/{domain}.json').read_bytes())
def model(domain='identity'):return bundle(domain)['model']
def clone(v):return copy.deepcopy(v)
def refusal(test,fn,code=None):
    with test.assertRaises(MMCError) as ctx:fn()
    if code:test.assertEqual(ctx.exception.code,code)
    return ctx.exception

def graph_model(n=2):
    from mosaic_mmc.contracts import profile_reference
    prov={'source_ref':'fixture:graph','source_digest':'0'*64,'observed_at':0,'epistemic':'ASSERTED','note':'synthetic graph'}
    obs=[]
    def add(id,kind,attrs):obs.append({'id':id,'kind':kind,'attributes':attrs,'provenance':clone(prov)})
    for i in range(n):add('actor.'+str(i),'Actor',{'roles':['producer'],'resumable':True,'versions':['old','new']})
    add('cohort.graph','Cohort',{'members':['actor.'+str(i) for i in range(n)],'policy_refs':[],'use_case':'graph'})
    for i in range(n):add('step.'+str(i),'Transition',{'cohort':'cohort.graph','goal':'OTHER','effects':[],'requires':[],'policies':[],'from_states':[{'target':'actor.'+str(i),'state':'old'}],'to_states':[{'target':'actor.'+str(i),'state':'new'}]})
    return {'schema':'mmc.model.t1','model_id':'graph.demo','revision':1,'domain':'workload','profile_ref':profile_reference(),'objects':obs,'initial_states':[{'target':'actor.'+str(i),'state':'old'} for i in range(n)]}

def lifecycle_input(**changes):
    r={'schema':'mmc.lifecycle-input.t2','cohort':'cohort.blue','current':'DRAFT','resume_from':None,'requested':'MODELED','action':'ADVANCE','current_floor':5,'proposed_floor':5,'current_revoked':['revoked.key'],'proposed_revoked':['revoked.key']};r.update(changes);return r
