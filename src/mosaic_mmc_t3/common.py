"""T3 finite shared admission. No implicit effects or ambient time."""
from __future__ import annotations
import hashlib,re
from pathlib import Path
from mosaic_mmc import canonical,decode,MMCError
from mosaic_mmc.codec import clone
from mosaic_mmc.errors import require
from ._pins import CONTRACT_ROOT

DOMAINS={'contract','policy','plan','context','request','statement','assessment','event','adapter','realization','ledger','test'}

def digest(domain,value):
    require(domain in DOMAINS,'MMC_T3_DOMAIN')
    return hashlib.sha256(b'MMC/T3/'+domain.encode('ascii')+b'\0'+canonical(value)).hexdigest()

def closed(value,keys,path='$'):
    require(type(value) is dict and set(value)==set(keys),'MMC_T3_FIELDS',path)

def integer(value,low=0,high=2**63-1):
    require(type(value) is int and low<=value<=high,'MMC_T3_INTEGER');return value

def token(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}',value) is not None,'MMC_T3_TOKEN');return value

def hashhex(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None,'MMC_T3_DIGEST');return value

def strings(value,limit=256):
    require(type(value) is list and len(value)<=limit,'MMC_T3_ARRAY')
    for v in value:token(v)
    require(value==sorted(set(value)),'MMC_T3_SET_ORDER');return value

def clock(value):
    closed(value,{'now','uncertainty'});integer(value['now']);integer(value['uncertainty'],0,86400)
    require(value['now']>=value['uncertainty'],'MMC_T3_CLOCK_RANGE')
    integer(value['now']+value['uncertainty'])
    return value['now']-value['uncertainty'],value['now']+value['uncertainty']

def fresh(body,time,max_age):
    lo,hi=clock(time)
    return body['issued_at']<=lo and hi<body['expires_at'] and hi-body['issued_at']<=max_age

def realization():
    r=Path(__file__).resolve().parent
    rows=[{'path':p.relative_to(r).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(r.rglob('*'),key=lambda item:item.relative_to(r).as_posix()) if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.md')]
    return digest('realization',{'contract_root':CONTRACT_ROOT,'files':rows})

BOUNDARY={'profile':'T3-O1','production_authorization':'NOT_ESTABLISHED','authority_effect':'NONE','native_pippi':'NOT_BOUND','signature':'NOT_SIGNED'}

def receipt(body):return {'body':body,'root':digest('assessment',body)}

def safe_database(path,create=False):
    """Cooperative owned-local-filesystem checks, not a hostile-writer sandbox."""
    p=Path(path).absolute()
    for a in (p,*p.parents):
        require(not a.is_symlink() and not(hasattr(a,'is_junction') and a.is_junction()),'MMC_T3_DATABASE_LINK')
    require(p.parent.is_dir(),'MMC_T3_DATABASE_PARENT')
    require(not p.exists() if create else p.is_file(),'MMC_T3_DATABASE_EXISTS' if create else 'MMC_T3_DATABASE_MISSING')
    if p.exists():require(p.stat().st_size<=128*1024*1024,'MMC_T3_DATABASE_LIMIT')
    return p
