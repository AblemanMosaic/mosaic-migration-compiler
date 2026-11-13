"""PUBLIC FIXTURE: actual controller transition sequence in temporary SQLite stores."""
from mosaic_mmc_t5 import run_scenario
from mosaic_mmc import canonical
r=run_scenario('safe-token')['body']
print(canonical({'status':r['status'],'milestones':r['milestones'],'target_effects':r['target_effects'],
                 'final_targets':r['final_targets'],'authority_effect':'NONE','production_evidence':False}).decode())
