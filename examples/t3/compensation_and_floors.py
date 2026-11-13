"""Temporary simulated compensation and rollback-floor demonstration."""
import sys,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests_t3.helpers import Env,TIME,Controller,digest,approvals
from mosaic_mmc import canonical,MMCError

def main():
 with tempfile.TemporaryDirectory() as d:
  e=Env(d);shutil.copy2(Path(d)/'controller.sqlite',Path(d)/'old.sqlite')
  e.run();e.run('step.cutover','copy');producer=e.store.snapshot(['producer.old'])
  r=e.controller.prepare(e.mid,'step.cutover',e.store,TIME,operation_id='undo.copy',direction='COMPENSATE')
  e.controller.approve('undo.copy',approvals(e.plan,r),TIME);e.controller.commit('undo.copy',e.store,TIME)
  state=e.store.snapshot(['asset.legacy'])['asset.legacy'];assert state['state']=='legacy' and state['floor']>=4 and 'revoked.key' in state['revoked']
  assert producer==e.store.snapshot(['producer.old']);floor=e.controller.replay()['projection']['head']
  try:Controller(Path(d)/'old.sqlite',expected_policy_root=digest('policy',e.policy),minimum=floor)
  except MMCError:pass
  else:raise AssertionError('old database incorrectly met protected external floor')
  return {'schema':'mmc.compensation-example.t3','status':'PASS','targeted_compensation':'APPLIED_NEW_APPROVAL','security_floor':'PRESERVED','external_floor':'REFUSED_OLD_DATABASE','local_effects':'TEMPORARY_SQLITE_ROWS','production':False,'authority_effect':'NONE'}
if __name__=='__main__':print(canonical(main()).decode())
