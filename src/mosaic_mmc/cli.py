"""Only caller-selected local reads and stdout. Redirection is a caller action."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import stat
import sys
from .codec import canonical, decode, MAX_INPUT, MAX_OUTPUT
from .abi import dispatch
from .model import closed
from .errors import MMCError, require


def read_local(name: str, *, limit: int = MAX_INPUT) -> bytes:
    if name=='-':
        data=sys.stdin.buffer.read(limit+1)
        require(len(data)<=limit,'MMC_BYTE_LIMIT')
        return data
    path=Path(os.path.abspath(name))
    try:
        for part in [path,*path.parents]:
            require(not part.is_symlink() and not (hasattr(part,'is_junction') and part.is_junction()),'MMC_INPUT_LINK',str(path))
        before=path.stat()
        require(stat.S_ISREG(before.st_mode),'MMC_INPUT_KIND',str(path))
        require(before.st_size<=limit,'MMC_BYTE_LIMIT')
        flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
        fd=os.open(path,flags)
        with os.fdopen(fd,'rb') as handle:
            first=os.fstat(handle.fileno())
            require(stat.S_ISREG(first.st_mode),'MMC_INPUT_KIND')
            require((before.st_dev,before.st_ino)==(first.st_dev,first.st_ino),'MMC_INPUT_CHANGED')
            data=handle.read(limit+1)
            last=os.fstat(handle.fileno())
        require(len(data)<=limit,'MMC_BYTE_LIMIT')
        require((first.st_size,first.st_mtime_ns,first.st_ctime_ns)==(last.st_size,last.st_mtime_ns,last.st_ctime_ns),'MMC_INPUT_CHANGED')
        return data
    except MMCError:raise
    except OSError as exc:raise MMCError('MMC_IO_ERROR','$',type(exc).__name__) from exc


def _load(name: str,limit: int=MAX_INPUT) -> object:
    return decode(read_local(name,limit=limit),limit=limit)


def _compilation_input(name: str) -> object:
    value=_load(name,MAX_OUTPUT)
    if type(value) is dict and value.get('schema')=='mmc.response.t1':
        closed(value,{'schema','operation','ok','result'},'$.cli_envelope')
        require(value['operation']=='compile' and value['ok'] is True,'MMC_COMPILATION_FRAME')
        return value['result']
    return value


def main(argv: list[str]|None=None) -> int:
    p=argparse.ArgumentParser(prog='mmc',description='Mosaic Migration Compiler — non-effectful T1 foundation')
    p.add_argument('--version',action='store_true')
    sub=p.add_subparsers(dest='command')
    for name in ['capabilities','program-inspect']:sub.add_parser(name)
    val=sub.add_parser('model');vs=val.add_subparsers(dest='model_command',required=True);vs.add_parser('validate').add_argument('input')
    comp=sub.add_parser('compile');comp.add_argument('input')
    ir=sub.add_parser('ir');irs=ir.add_subparsers(dest='ir_command',required=True);verify=irs.add_parser('verify')
    verify.add_argument('model');verify.add_argument('compilation');verify.add_argument('--expected-model-root',required=True)
    req=sub.add_parser('request');req.add_argument('input')
    args=p.parse_args(argv)
    try:
        if args.version:
            from ._pins import VERSION,ENGINEERING_REVISION
            result={'distribution':'mosaic-migration-compiler','version':VERSION,'revision':ENGINEERING_REVISION}
        else:
            op=args.command
            if op=='request':result=dispatch(_load(args.input,MAX_OUTPUT))
            else:
                if op=='model':op='model-validate';arguments={'model':_load(args.input)}
                elif op=='compile':arguments={'model':_load(args.input)}
                elif op=='ir':
                    op='verify-ir'
                    require(not(args.model=='-' and args.compilation=='-'),'MMC_STDIN_AMBIGUOUS')
                    arguments={'model':_load(args.model),'compilation':_compilation_input(args.compilation),'expected_model_root':args.expected_model_root}
                elif op in ('capabilities','program-inspect'):arguments={}
                else:raise MMCError('MMC_COMMAND_REQUIRED')
                result=dispatch({'schema':'mmc.request.t1','operation':op,'arguments':arguments})
        sys.stdout.buffer.write(canonical(result)+b'\n');return 0
    except MMCError as exc:
        sys.stdout.buffer.write(canonical({'schema':'mmc.refusal.t1','ok':False,'error':exc.record(),'authority_effect':'NONE'})+b'\n')
        return 2

if __name__=='__main__':raise SystemExit(main())
