"""Optional exact-wheel native reads, not authority transfer or automatic installation."""
from pathlib import Path
import importlib
import importlib.util
from .common import *


def manifest():
    return [
      {'id':'pippi','status':'NOT_BOUND','gate':'BLOCKED_NATIVE_DEPENDENCY','reason':'Native schema/interpreter/admission/host receipts not supplied'},
      {'id':'ucm','status':'NOT_BOUND','gate':'BLOCKED_NATIVE_DEPENDENCY','reason':'No owner-selected native validator bound'},
      {'id':'chc','status':'REFERENCES_ONLY','gate':'NOT_ESTABLISHED','reason':'No full compiler/toolchain realization selected'},
      {'id':'cmba','status':'OPTIONAL_PINNED_READ_ADAPTER','version':'0.1.0a4','operation':'inspect-binding'},
      {'id':'dkn','status':'OPTIONAL_PINNED_READ_ADAPTER','version':'0.2.0rc5','operation':'verify-archive'}]


def require_native_pippi():
    raise MMCError('MMC_T4_NATIVE_PIPPI_NOT_BOUND')


@typed
def handoff(target,refs):
    require(target in ('pippi','ucm','cmba','dkn','chc'), 'MMC_T4_INTEGRATION_TARGET')
    require(type(refs) is list and 0<len(refs)<=32,'MMC_T4_HANDOFF_LIMIT')
    ids=[]
    for r in refs:
        closed(r,{'role','sha256'});token(r['role']);hashhex(r['sha256']);ids.append(r['role'])
    require(len(set(ids))==len(ids),'MMC_T4_HANDOFF_DUPLICATE')
    return envelope('handoff',{'schema':'mmc.integration-handoff.t4','target':target,'references':sorted(clone(refs),key=lambda x:x['role']),
            'status':'REFERENCES_ONLY','operational_integration':'NOT_ESTABLISHED','decision':'EXTERNAL_DECISION_REQUIRED','effects':'NOT_EXECUTED',**BOUNDARY})


def _admit(name):
    require(name in ('cmba','dkn'),'MMC_T4_NATIVE_UNKNOWN')
    pins=decode(Path(__file__).with_name('data').joinpath('native-pins.json').read_bytes())
    cfg=pins[name];top=cfg['package'];spec=importlib.util.find_spec(top)
    require(spec is not None and spec.origin is not None,'MMC_T4_NATIVE_DEPENDENCY')
    root=Path(spec.origin).parent
    require(root.is_dir() and not root.is_symlink(),'MMC_T4_NATIVE_PATH')
    expected={r['path']:r for r in cfg['files']};found={}
    for p in root.rglob('*'):
        require(not p.is_symlink(),'MMC_T4_NATIVE_LINK')
        if p.is_file() and '__pycache__' not in p.parts:
            rel=p.relative_to(root).as_posix();require(rel in expected,'MMC_T4_NATIVE_EXTRA',rel)
            raw=p.read_bytes();found[rel]={'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    require(canonical([found[x] for x in sorted(found)])==canonical([expected[x] for x in sorted(expected)]),'MMC_T4_NATIVE_HASH')
    return cfg,importlib.import_module(top)


@typed
def native_read(name,arguments):
    cfg,module=_admit(name)
    if name=='cmba':
        closed(arguments,{'binding','values'})
        result=module.inspect(arguments['binding'],arguments['values'])
    else:
        closed(arguments,{'archive_hex','expected_root'})
        hashhex(arguments['expected_root']);h=arguments['archive_hex']
        require(type(h) is str and len(h)<=MAX_INPUT and len(h)%2==0 and re.fullmatch('[0-9a-f]*',h) is not None,'MMC_T4_ARCHIVE_HEX')
        result=module.verify_archive(bytes.fromhex(h))
        # Native output shape is preserved; the expected logical root is a reader input.
        require(result['logical_root']==arguments['expected_root'],'MMC_T4_NATIVE_ROOT')
    _admit(name)
    return {'schema':'mmc.native-read.t4','native':name,'native_wheel_sha256':cfg['wheel_sha256'],'status':'NATIVE_REPORT_COMPUTED',
            'native_result':result,'runtime_dependencies':'HOST_SUPPLIED_NOT_FULL_ENVIRONMENT_ATTESTATION','effects':'NOT_EXECUTED',**BOUNDARY}
