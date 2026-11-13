from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from mosaic_mmc import canonical,decode,MMCError
from mosaic_mmc.codec import clone
from mosaic_mmc_t2 import assess_retirement,compile_domain,verify_compilation
b=decode((Path(__file__).parent/'identity.json').read_bytes());r=b['retirements'][0]['record']
quiet=clone(r);quiet['producers'][0]['fenced']=False;quiet['workers'][0]['fenced']=False
before=assess_retirement(b['model'],quiet);assert before['status']=='BLOCKED_FOR_SUPPLIED_MODEL'
after=assess_retirement(b['model'],r);assert after['status']=='MODEL_RETIREMENT_CONDITIONS_MET'
assert after['operational_eligibility']=='NOT_EVALUATED'
comp=compile_domain(b);forged=clone(comp);forged['body']['operational_eligibility']='AUTHORIZED'
from mosaic_mmc_t2.common import digest
forged['root']=digest('compilation',forged['body'])
try:verify_compilation(b,forged,expected_model_root=comp['body']['model_root'])
except MMCError as exc:assert exc.code=='MMC_T2_COMPILATION_MISMATCH'
else:raise AssertionError('forged authorization accepted')
print(canonical({'quiet_resumable_worker':before['status'],'supplied_fenced_model':after['status'],'live_authorization':'NOT_EVALUATED','forged_receipt':'REFUSED'}).decode())
