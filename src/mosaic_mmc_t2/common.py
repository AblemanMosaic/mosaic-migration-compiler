"""Strict finite T2 inputs and explicitly scoped report construction."""
from __future__ import annotations
import hashlib
import importlib.resources as resources
import re
from pathlib import Path
from mosaic_mmc.codec import canonical, decode, clone
from mosaic_mmc.errors import MMCError, require
from ._pins import VERSION, CONTRACT_ROOT

DOMAINS = {'profile','contract','request','report','policy-change','plan','compilation','realization','retirement-requirements','test-source','stage','vectors'}

def digest(domain: str, value: object) -> str:
    require(type(domain) is str and domain in DOMAINS, 'MMC_T2_HASH_DOMAIN')
    return hashlib.sha256(b'MMC/T2/'+domain.encode('ascii')+b'\0'+canonical(value)).hexdigest()

def data(name: str) -> object:
    return decode(resources.files('mosaic_mmc_t2').joinpath('data',name).read_bytes(),limit=8*1024*1024)

def shape(value: object, spec: dict, path='$') -> None:
    if 'anyOf' in spec:
        for alternative in spec['anyOf']:
            try: shape(value,alternative,path); return
            except MMCError: pass
        raise MMCError('MMC_T2_SHAPE',path,'No admitted alternative')
    if 'const' in spec:
        require(canonical(value)==canonical(spec['const']),'MMC_T2_CONST',path)
    if 'enum' in spec:
        require(any(canonical(value)==canonical(x) for x in spec['enum']),'MMC_T2_ENUM',path)
    t=spec.get('type')
    if t=='null':require(value is None,'MMC_T2_TYPE',path)
    elif t=='boolean':require(type(value) is bool,'MMC_T2_TYPE',path)
    elif t=='integer':require(type(value) is int and spec.get('minimum',-2**63)<=value<=spec.get('maximum',2**63-1),'MMC_T2_INTEGER',path)
    elif t=='string':
        require(type(value) is str,'MMC_T2_TYPE',path)
        require(spec.get('minLength',0)<=len(value)<=spec.get('maxLength',65536),'MMC_T2_STRING',path)
        if 'pattern' in spec:require(re.fullmatch(spec['pattern'],value) is not None,'MMC_T2_TOKEN',path)
    elif t=='array':
        require(type(value) is list and spec.get('minItems',0)<=len(value)<=spec.get('maxItems',128),'MMC_T2_ARRAY',path)
        if spec.get('uniqueItems'): require(len({canonical(v) for v in value})==len(value),'MMC_T2_DUPLICATE',path)
        for i,v in enumerate(value):shape(v,spec['items'],f'{path}[{i}]')
    elif t=='object':
        require(type(value) is dict,'MMC_T2_TYPE',path)
        require(set(value)==set(spec['required']),'MMC_T2_FIELDS',path)
        for k,s in spec['properties'].items():shape(value[k],s,path+'.'+k)

def admit(kind: str, value: object) -> dict:
    canonical(value,limit=2*1024*1024)
    shape(value,data(kind+'.schema.json'))
    return clone(value)

def unique(rows: list[dict], field='id') -> dict:
    result={}
    for row in rows:
        require(row[field] not in result,'MMC_T2_DUPLICATE_ID',field,row[field])
        result[row[field]]=row
    return result

def strings_equal(a,b):return set(a)==set(b)

def realization_identity() -> str:
    root=Path(__file__).resolve().parent
    rows=[]
    for p in sorted(root.rglob('*'), key=lambda item: item.relative_to(root).as_posix()):
        if not p.is_file() or '__pycache__' in p.parts:continue
        require(not p.is_symlink(),'MMC_T2_REALIZATION_LINK')
        if p.suffix in ('.py','.json','.md'):
            raw=p.read_bytes(); rows.append({'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(raw).hexdigest()})
    return digest('realization',{'version':VERSION,'files':rows})

BOUNDARY={'operational_eligibility':'NOT_EVALUATED','evidence_authentication':'NOT_PERFORMED','authority_effect':'NONE','effects':'NOT_EXECUTED','coverage':'SUPPLIED_DECLARATIONS_ONLY'}
class Report:
    def __init__(self,kind:str):self.kind=kind;self.checks=[]
    def check(self,code:str,value:bool|None,refs=(),detail=''):
        require(type(value) in (bool,type(None)),'MMC_T2_INTERNAL_CHECK')
        self.checks.append({'code':code,'outcome':'UNKNOWN' if value is None else 'PASS' if value else 'BLOCK','refs':sorted(set(refs)),'detail':detail})
    def result(self,**extra):
        outcomes=[x['outcome'] for x in self.checks]
        return {'schema':'mmc.profile-result.t2','profile':self.kind,'status':('BLOCKED_FOR_SUPPLIED_MODEL' if 'BLOCK' in outcomes else 'INDETERMINATE' if 'UNKNOWN' in outcomes else 'MATCH_FOR_SUPPLIED_MODEL'),'checks':self.checks,**BOUNDARY,**extra}

def truth(value):return value if type(value) is bool else None

def conjunction(values):
    values=list(values)
    return False if False in values else None if None in values else True
