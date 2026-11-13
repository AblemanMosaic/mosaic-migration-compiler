"""Read-only JSON CLI; effects cannot be selected by input data."""
import argparse,sys
from mosaic_mmc.cli import read_local
from mosaic_mmc import decode,canonical,MMCError
from .abi import dispatch

def main(argv=None):
    p=argparse.ArgumentParser(prog='mmc-t2',description='MMC Capability Layer T2 finite domain/model assessments, NOT live authorization')
    sub=p.add_subparsers(dest='operation',required=True)
    sub.add_parser('profiles')
    for name in ('request','compile'):sub.add_parser(name).add_argument('input')
    a=p.parse_args(argv)
    try:
        if a.operation=='profiles':request={'schema':'mmc.request.t2','operation':'profiles','arguments':{}}
        else:
            value=decode(read_local(a.input))
            request=value if a.operation=='request' else {'schema':'mmc.request.t2','operation':'compile','arguments':{'bundle':value}}
        sys.stdout.buffer.write(canonical(dispatch(request))+b'\n');return 0
    except MMCError as exc:
        sys.stdout.buffer.write(canonical({'schema':'mmc.refusal.t2','ok':False,'error':exc.record(),'authority_effect':'NONE'})+b'\n');return 2
if __name__=='__main__':raise SystemExit(main())
