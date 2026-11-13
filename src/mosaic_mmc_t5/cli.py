"""Explicit local foundry CLI: fixtures only, never a production effect API."""
from pathlib import Path
import argparse,sys
from mosaic_mmc import canonical,decode,MMCError
from mosaic_mmc.errors import require
from .foundry import catalogue,run_scenario,replay_scenario,inspect_result

def main():
    p=argparse.ArgumentParser(description='MMC finite local migration qualification; public fixture keys only')
    p.add_argument('operation',choices=['list','run','inspect','replay']);p.add_argument('scenario',nargs='?')
    p.add_argument('--seed',type=int,default=0);p.add_argument('--candidate');p.add_argument('--expected-root')
    a=p.parse_args()
    try:
        if a.operation=='list':
            require(a.scenario is None and a.candidate is None,'MMC_T5_ARGUMENTS')
            result={'schema':'mmc.foundry-capabilities.t5','scenarios':catalogue(),'run_effects':'TEMPORARY_LOCAL_SQLITE_SIMULATION',
              'replay_effects':'NEW_TEMPORARY_SIMULATION_ONLY','production':False,'authority_effect':'NONE'}
        elif a.operation=='run':
            require(a.candidate is None and a.expected_root is None,'MMC_T5_ARGUMENTS');result=run_scenario(a.scenario,seed=a.seed)
        else:
            require(a.candidate is not None,'MMC_T5_CANDIDATE_REQUIRED');f=Path(a.candidate).absolute()
            require(all(not q.is_symlink() and not(getattr(q,'is_junction',lambda:False)()) for q in (f,*f.parents)), 'MMC_T5_INPUT_LINK')
            require(f.is_file() and f.stat().st_size<=8*1024*1024,'MMC_T5_INPUT_LIMIT')
            value=decode(f.read_bytes(),limit=8*1024*1024)
            if a.operation=='inspect':result=inspect_result(value,expected_root=a.expected_root)
            else:
                inspect_result(value,expected_root=a.expected_root)
                result=replay_scenario(a.scenario,value,seed=a.seed)
        sys.stdout.buffer.write(canonical(result,limit=8*1024*1024)+b'\n');return 0
    except MMCError as exc:
        sys.stdout.buffer.write(canonical({'schema':'mmc.foundry-refusal.t5','error':exc.record(),'authority_effect':'NONE'})+b'\n');return 2
    except OSError as exc:
        sys.stdout.buffer.write(canonical({'schema':'mmc.foundry-refusal.t5','error':{'code':'MMC_T5_IO','type':type(exc).__name__},'authority_effect':'NONE'})+b'\n');return 2
if __name__=='__main__':raise SystemExit(main())
