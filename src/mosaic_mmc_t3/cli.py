"""Read-only CLI. All effectful operations require deliberate Python host calls."""
import argparse,sys
from pathlib import Path
from .common import *
from .abi import dispatch

def main():
    p=argparse.ArgumentParser(prog='mmc-t3');p.add_argument('command',choices=['capabilities','request']);p.add_argument('file',nargs='?',default='-');a=p.parse_args()
    try:
        if a.command=='capabilities':req={'schema':'mmc.request.t3','operation':'capabilities','arguments':{}}
        else:
            if a.file=='-':raw=sys.stdin.buffer.read(2*1024*1024+1)
            else:
                f=Path(a.file).absolute()
                for x in (f,*f.parents):require(not x.is_symlink() and not(hasattr(x,'is_junction') and x.is_junction()),'MMC_T3_FILE_LINK')
                require(f.is_file() and f.stat().st_size<=2*1024*1024,'MMC_T3_INPUT_FILE')
                with f.open('rb') as h:raw=h.read(2*1024*1024+1)
            req=decode(raw)
        result=dispatch(req);sys.stdout.buffer.write(canonical(result)+b'\n');return 0
    except (MMCError,OSError) as exc:
        code=exc.code if isinstance(exc,MMCError) else 'MMC_T3_IO'
        sys.stdout.buffer.write(canonical({'schema':'mmc.refusal.t3','code':code,'effects':'NOT_EXECUTED',**BOUNDARY})+b'\n');return 2
if __name__=='__main__':raise SystemExit(main())
