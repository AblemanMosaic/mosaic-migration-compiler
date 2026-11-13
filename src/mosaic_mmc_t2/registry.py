"""Fixed installed semantics; there is no data-supplied handler loader."""
import hashlib
from .common import data,digest,canonical,clone,require
from ._pins import CONTRACT_ROOT, PROFILE_ROOTS

def profile_reference(name:str)->dict:
    profiles=data('profiles.json')
    require(type(name) is str and name in profiles,'MMC_T2_PROFILE_UNSUPPORTED')
    p=profiles[name];body=p['body']
    require(digest('profile',body)==p['root']==PROFILE_ROOTS.get(name),'MMC_T2_PROFILE_INTEGRITY')
    require(hashlib.sha256(canonical(data(name+'.schema.json'))).hexdigest()==body['input_schema_sha256'],'MMC_T2_SCHEMA_INTEGRITY')
    import importlib.resources as resources
    raw=resources.files('mosaic_mmc_t2').joinpath('data','PROTOCOL.md').read_bytes()
    require(hashlib.sha256(raw).hexdigest()==body['protocol_sha256'],'MMC_T2_PROTOCOL_INTEGRITY')
    return {'id':body['id'],'version':body['version'],'sha256':p['root']}

def resolve(ref:object)->str:
    canonical(ref)
    for name in data('profiles.json'):
        if canonical(ref)==canonical(profile_reference(name)):return name
    raise __import__('mosaic_mmc.errors',fromlist=['MMCError']).MMCError('MMC_T2_PROFILE_PIN')

def capabilities()->dict:
    return {'schema':'mmc.capabilities.t2','profile_version':'T2-D1','contract_root':CONTRACT_ROOT,
            'profiles':[profile_reference(n) for n in sorted(data('profiles.json'))],
            'operations':['profiles','assess','replay','plan','retirement','routes','lifecycle','compile','verify-compilation'],
            'effects':'NONE','live_controller':'NOT_IMPLEMENTED','native_pippi':'NOT_BOUND'}
