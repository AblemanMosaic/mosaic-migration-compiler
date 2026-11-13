"""PUBLIC FIXTURE: ambiguous return never licenses blind retry."""
from mosaic_mmc_t5 import run_scenario
from mosaic_mmc import canonical
r=run_scenario('lost-ack')['body']
print(canonical({'status':r['status'],'milestones':r['milestones'],'target_effects':r['target_effects'],
                 'checks':r['checks'],'authority_effect':'NONE','production_evidence':False}).decode())
