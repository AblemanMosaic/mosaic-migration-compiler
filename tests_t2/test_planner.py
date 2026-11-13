import itertools,unittest,random
from .helpers import *
from mosaic_mmc_t2 import plan
from mosaic_mmc_t2.planner import components
from mosaic_mmc import canonical

def pair(kind='coexistence'):
    return {'id':'a-needs-b','left':{'target':'actor.0','state':'new'},'right':{'target':'actor.1','state':'new'},'when':None}

def phased():
    p=simple_planning();a=pair();b=clone(a);b.update(id='b-needs-a',left=a['right'],right=a['left']);p['coexistence']=[a,b];return p

class PlannerAcceptance(unittest.TestCase):
    def test_ac_profile_09(self):
        m=graph_model();p=simple_planning();p['facts']=[{'id':'condition','value':None,'source_ref':'fixture:fact'}]
        p['orders']=[{'id':'conditional','before':'step.1','after':'step.0','when':'condition'}]
        self.assertEqual(plan(m,p)['body']['status'],'INDETERMINATE_CONDITIONS')
        p['facts'][0]['value']=True;self.assertEqual([s['action'] for s in plan(m,p)['body']['witness']],['step.1','step.0'])
        p['facts'][0]['value']=False;self.assertEqual([s['action'] for s in plan(m,p)['body']['witness']],['step.0','step.1'])
    def test_ac_profile_10(self):
        m=graph_model();p=simple_planning();p['coexistence']=[pair()];r=plan(m,p)
        self.assertEqual(r['body']['status'],'ADMISSIBLE_MODEL_PLAN');self.assertEqual(r['body']['witness'][0]['action'],'step.1')
        p=simple_planning();p['exclusions']=[pair()];self.assertEqual(plan(m,p)['body']['status'],'UNSATISFIABLE_FOR_SUPPLIED_MODEL')
    def test_ac_profile_11(self):
        m=graph_model();p=phased();self.assertEqual(plan(m,p)['body']['status'],'UNSATISFIABLE_FOR_SUPPLIED_MODEL')
        p['phases']=[{'id':'phase.both','members':['step.0','step.1'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'}]
        x=plan(m,p)['body'];self.assertEqual(x['status'],'ADMISSIBLE_MODEL_PLAN');self.assertEqual(len(x['witness']),1);self.assertEqual(x['witness'][0]['atomicity'],'REQUIRES_QUALIFIED_ADAPTER')
        p['orders']=[{'id':'strict.a','before':'step.0','after':'step.1','when':None},{'id':'strict.b','before':'step.1','after':'step.0','when':None}]
        x=plan(m,p)['body'];self.assertEqual(x['status'],'UNSATISFIABLE_FOR_SUPPLIED_MODEL');self.assertEqual(x['order_components'],[['step.0','step.1']])

class PlannerTests(unittest.TestCase):
    def test_foundation_order_retained(self):
        b=bundle();x=plan(b['model'],b['planning'])['body'];self.assertEqual([s['action'] for s in x['witness']],['step.prepare','step.cutover','step.retire'])
    def test_phase_not_implicit(self):
        x=plan(graph_model(),phased())['body'];self.assertEqual(x['witness'],[]);self.assertEqual(x['coexistence_components'],[['actor.0','actor.1']])
    def test_budget_is_not_impossibility(self):
        p=simple_planning();p['search_limit']=1
        x=plan(graph_model(),p)['body'];self.assertEqual(x['status'],'INDETERMINATE_SEARCH_LIMIT')
    def test_initial_violation(self):
        m=graph_model();m['initial_states'][0]['state']='new';p=simple_planning();p['coexistence']=[pair()]
        self.assertEqual(plan(m,p)['body']['diagnostics'][0]['code'],'INITIAL_CONSTRAINT_VIOLATION')
    def test_stable_permutation(self):
        m=graph_model(4);expected=canonical(plan(m,simple_planning()))
        for seed in range(10):
            c=clone(m);random.Random(seed).shuffle(c['objects']);self.assertEqual(canonical(plan(c,simple_planning())),expected)
    def test_no_model_mutation(self):
        m=graph_model();p=phased();before=canonical([m,p]);plan(m,p);self.assertEqual(canonical([m,p]),before)
    def test_order_scc_excludes_blocked_descendant(self):
        self.assertEqual(components(['a','b','c'],[('a','b'),('b','a'),('b','c')]),[['a','b'],['c']])
    def test_unknown_fact_missing(self):
        p=simple_planning();p['orders']=[{'id':'o','before':'step.0','after':'step.1','when':'missing'}]
        refusal(self,lambda:plan(graph_model(),p),'MMC_T2_FACT_REFERENCE')
    def test_wrong_reference(self):
        p=simple_planning();p['orders']=[{'id':'o','before':'missing','after':'step.1','when':None}]
        refusal(self,lambda:plan(graph_model(),p),'MMC_T2_ORDER_REFERENCE')
    def test_phase_identifier_alias(self):
        p=simple_planning();p['phases']=[{'id':'step.2','members':['step.0','step.1'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'}]
        refusal(self,lambda:plan(graph_model(3),p),'MMC_T2_PHASE_ID_ALIAS')
    def test_phase_disjoint(self):
        p=simple_planning();p['phases']=[{'id':'p','members':['step.0','step.1'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'},{'id':'q','members':['step.0','step.2'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'}]
        refusal(self,lambda:plan(graph_model(3),p),'MMC_T2_PHASE_OVERLAP')
    def test_phase_target_overlap(self):
        m=graph_model();ts=[o for o in m['objects'] if o['kind']=='Transition'];ts[1]['attributes']['from_states'][0]['target']='actor.0';ts[1]['attributes']['to_states'][0]['target']='actor.0'
        p=simple_planning();p['phases']=[{'id':'p','members':['step.0','step.1'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'}]
        refusal(self,lambda:plan(m,p),'MMC_T2_PHASE_TARGET_OVERLAP')
    def test_strict_edge_inside_phase(self):
        p=simple_planning();p['orders']=[{'id':'o','before':'step.0','after':'step.1','when':None}];p['phases']=[{'id':'p','members':['step.0','step.1'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'}]
        self.assertEqual(plan(graph_model(),p)['body']['status'],'UNSATISFIABLE_FOR_SUPPLIED_MODEL')
    def test_transition_limit(self):refusal(self,lambda:plan(graph_model(17),simple_planning()),'MMC_T2_PLANNER_TRANSITION_LIMIT')
    def test_explicit_state_chain(self):
        m=graph_model();ts=[o for o in m['objects'] if o['kind']=='Transition'];ts[1]['attributes']['from_states'][0]['state']='impossible'
        self.assertEqual(plan(m,simple_planning())['body']['status'],'UNSATISFIABLE_FOR_SUPPLIED_MODEL')
    def test_independent_exhaustive_small_order_oracle(self):
        # 64 distinct directed graphs; permutations are the independent order oracle.
        edges=[(a,b) for a in range(3) for b in range(3) if a!=b];m=graph_model(3)
        for mask in range(64):
            selected=[e for i,e in enumerate(edges) if mask&(1<<i)]
            valid=any(all(order.index(a)<order.index(b) for a,b in selected) for order in itertools.permutations(range(3)))
            p=simple_planning();p['orders']=[{'id':f'o{i}','before':f'step.{a}','after':f'step.{b}','when':None} for i,(a,b) in enumerate(selected)]
            self.assertEqual(plan(m,p)['body']['status']=='ADMISSIBLE_MODEL_PLAN',valid,selected)
    def test_independent_state_constraint_oracle(self):
        # Enumerate all two-actor constraints and compare a direct permutation/state evaluator.
        m=graph_model()
        constraints=[('coexistence','new','new'),('coexistence','new','old'),('exclusions','new','new'),('exclusions','old','old')]
        for mask in range(16):
            p=simple_planning();chosen=[c for i,c in enumerate(constraints) if mask&(1<<i)]
            for i,(kind,l,r) in enumerate(chosen):p[kind].append({'id':f'c{i}','left':{'target':'actor.0','state':l},'right':{'target':'actor.1','state':r},'when':None})
            def ok(s):return all((not(s[0]==l) or s[1]==r) if kind=='coexistence' else not(s[0]==l and s[1]==r) for kind,l,r in chosen)
            def path(order):
                s=['old','old']
                if not ok(s):return False
                for step in order:
                    s[step]='new'
                    if not ok(s):return False
                return True
            valid=any(path(order) for order in itertools.permutations(range(2)))
            self.assertEqual(plan(m,p)['body']['status']=='ADMISSIBLE_MODEL_PLAN',valid,chosen)
