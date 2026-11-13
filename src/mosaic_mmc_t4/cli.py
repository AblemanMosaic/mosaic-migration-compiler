"""Read-only JSON/CLI parity; stdout redirection is a separate caller action."""
import argparse,sys
from .common import *
from .abi import dispatch
from ._pins import VERSION,REVISION
from mosaic_mmc.cli import read_local

def main(argv=None):
    p=argparse.ArgumentParser(prog='mmc-agent',description='MMC T4 bounded agent interfaces; no effects')
    p.add_argument('--version',action='store_true')
    sub=p.add_subparsers(dest='command')
    for c in ('capabilities','profiles','integrations'):sub.add_parser(c)
    q=sub.add_parser('request');q.add_argument('input')
    a=p.parse_args(argv)
    try:
        if a.version:r={'schema':'mmc.version.t4','version':VERSION,'revision':REVISION,**BOUNDARY}
        elif a.command=='request':r=dispatch(decode(read_local(a.input,limit=MAX_INPUT),limit=MAX_INPUT,canonical_only=True))
        elif a.command in ('capabilities','profiles','integrations'):r=dispatch({'schema':'mmc.request.t4','operation':a.command,'arguments':{}})
        else:raise MMCError('MMC_T4_COMMAND_REQUIRED')
        sys.stdout.buffer.write(canonical(r)+b'\n');return 0
    except MMCError as exc:
        sys.stdout.buffer.write(canonical({'schema':'mmc.refusal.t4','ok':False,'error':exc.record(),**BOUNDARY})+b'\n');return 2

if __name__=='__main__':raise SystemExit(main())
