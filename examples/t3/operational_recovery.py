"""PUBLIC FIXTURE keys. Temp-only simulated workflow; not the T5 production study."""
import sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests_t3.helpers import Env,TIME,Controller,digest
from mosaic_mmc import canonical

def main():
 with tempfile.TemporaryDirectory() as d:
  e=Env(d);c=e.controller
  assert c.assess(e.mid,'step.prepare',TIME)['body']['status']=='INDETERMINATE'
  r=e.prepare();e.approve(r);before=e.store.snapshot(['producer.old'])
  outcome=c.commit('op.1',e.store,TIME,fault='lost_ack');assert outcome['status']=='UNKNOWN'
  checkpoint=c.replay()['projection']['head']
  restarted=Controller(Path(d)/'controller.sqlite',expected_policy_root=digest('policy',e.policy),minimum=checkpoint)
  assert restarted.replay()['effects']=='NOT_EXECUTED'
  reconciled=restarted.reconcile('op.1',e.store);assert reconciled['status']=='APPLIED'
  assert e.store.snapshot(['producer.old'])['producer.old']['version']==before['producer.old']['version']+1
  e.controller=restarted
  for step,op in [('step.cutover','op.2'),('step.retire','op.3')]:assert e.run(step,op)['status']=='APPLIED'
  projection=restarted.replay()['projection'];assert len(projection['migrations'][e.mid]['completed'])==3
  return {'schema':'mmc.operational-example.t3','status':'PASS','missing_evidence':'INDETERMINATE','lost_ack':'UNKNOWN','reconciliation':'APPLIED_ONCE','confirmed_steps':3,'journal':restarted.journal.export(),'target':e.store.snapshot(sorted(x['target'] for x in e.bundle['model']['initial_states'])),'production':False,'authority_effect':'NONE','local_effects':'TEMPORARY_SQLITE_ROWS','scope':'SIGNED_FIXTURE_LOCAL_SIMULATION_NOT_T5_ACCEPTANCE'}
if __name__=='__main__':print(canonical(main()).decode())
