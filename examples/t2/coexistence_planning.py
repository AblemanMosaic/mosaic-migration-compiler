from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from mosaic_mmc import decode,canonical
from mosaic_mmc_t2 import plan
r=Path(__file__).parent
model=decode((r/'coexistence-model.json').read_bytes());planning=decode((r/'coexistence-planning.json').read_bytes())
sequential=plan(model,planning)
assert sequential['body']['status']=='UNSATISFIABLE_FOR_SUPPLIED_MODEL'
planning['phases']=[{'id':'phase.activation','members':['step.0','step.1'],'atomicity':'MODELED_ONLY_REQUIRES_ADAPTER'}]
phase=plan(model,planning);assert phase['body']['status']=='ADMISSIBLE_MODEL_PLAN'
assert phase['body']['witness'][0]['atomicity']=='REQUIRES_QUALIFIED_ADAPTER'
planning['orders']=[{'id':'strict','before':'step.0','after':'step.1','when':None}]
strict=plan(model,planning);assert strict['body']['status']=='UNSATISFIABLE_FOR_SUPPLIED_MODEL'
print(canonical({'sequential':sequential['body']['status'],'explicit_phase':phase['body']['status'],'strict_order_not_erased':strict['body']['status'],'effects':'NOT_EXECUTED'}).decode())
