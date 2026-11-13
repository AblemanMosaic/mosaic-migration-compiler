"""Deterministic closed source packaging and standard wheel generation. No installation/publication."""
from __future__ import annotations
from pathlib import Path,PurePosixPath
import argparse,base64,csv,hashlib,io,re,stat,sys,zipfile
try:from .common import ROOT,regular_files,read_json,sha,canonical,decode,digest,require
except ImportError:from common import ROOT,regular_files,read_json,sha,canonical,decode,digest,require

MANIFEST='FILE-MANIFEST.json'
FIXED=(1980,1,1,0,0,0)

def safe_names(names):
    require(len(names)==len(set(names)),'MMC_ARCHIVE_DUPLICATE')
    folded=set(); paths=set()
    for n in names:
        require(type(n) is str and 0<len(n)<=240 and n.isascii(),'MMC_ARCHIVE_PATH')
        parts=n.split('/')
        require(all(re.fullmatch(r'[A-Za-z0-9_.-]+',s) and s not in ('.','..') and not s.endswith('.') for s in parts),'MMC_ARCHIVE_PATH',n)
        require(not any(p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for p in parts),'MMC_ARCHIVE_RESERVED',n)
        folded_n=n.lower();require(folded_n not in folded,'MMC_ARCHIVE_ALIAS',n);folded.add(folded_n);paths.add(n)
    for n in paths:
        parts=n.split('/')
        require(not any('/'.join(parts[:i]).lower() in folded for i in range(1,len(parts))),'MMC_ARCHIVE_PREFIX',n)

def zip_bytes(values:dict[str,bytes])->bytes:
    safe_names(list(values))
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
        for name in sorted(values):
            info=zipfile.ZipInfo(name,FIXED);info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_STORED
            z.writestr(info,values[name])
    return out.getvalue()

def build_source(root:Path=ROOT)->bytes:
    values={rel:p.read_bytes() for rel,p in regular_files(root) if rel!=MANIFEST}
    body={'schema':'mmc.source-package.t1','files':[{'path':n,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in sorted(values.items())],
          'authority_effect':'NONE','signature':'NOT_SIGNED'}
    values[MANIFEST]=canonical(body)
    return zip_bytes(values)

def verify_source_archive(raw:bytes):
    require(type(raw) is bytes and len(raw)<=64*1024*1024,'MMC_ARCHIVE_BUDGET')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist();require(1<=len(infos)<=5000,'MMC_ARCHIVE_BUDGET')
            safe_names([i.filename for i in infos])
            require(sum(i.file_size for i in infos)<=64*1024*1024,'MMC_ARCHIVE_BUDGET')
            values={}
            for i in infos:
                require(i.file_size<=16*1024*1024 and i.compress_type==zipfile.ZIP_STORED and stat.S_ISREG(i.external_attr>>16),'MMC_ARCHIVE_KIND',i.filename)
                require(not(i.flag_bits&1),'MMC_ARCHIVE_ENCRYPTION')
                values[i.filename]=z.read(i)
    except (zipfile.BadZipFile,RuntimeError,OSError) as exc:
        raise ValueError('MMC_ARCHIVE_INVALID') from exc
    require(MANIFEST in values,'MMC_ARCHIVE_MANIFEST')
    m=decode(values[MANIFEST],canonical_only=True,limit=8*1024*1024)
    require(type(m) is dict and set(m)=={'schema','files','authority_effect','signature'} and m['schema']=='mmc.source-package.t1' and m['authority_effect']=='NONE' and m['signature']=='NOT_SIGNED','MMC_ARCHIVE_MANIFEST')
    require(type(m['files']) is list,'MMC_ARCHIVE_MANIFEST')
    listed=[]
    for row in m['files']:
        require(type(row) is dict and set(row)=={'path','bytes','sha256'},'MMC_ARCHIVE_ROW')
        require(type(row['bytes']) is int and 0<=row['bytes']<=16*1024*1024,'MMC_ARCHIVE_SIZE')
        require(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']),'MMC_ARCHIVE_DIGEST')
        n=row['path'];require(type(n) is str and n in values and n!=MANIFEST,'MMC_ARCHIVE_MEMBER')
        require(len(values[n])==row['bytes'] and hashlib.sha256(values[n]).hexdigest()==row['sha256'],'MMC_ARCHIVE_HASH',n)
        listed.append(n)
    require(listed==sorted(listed) and len(listed)==len(set(listed)) and set(listed)==set(values)-{MANIFEST},'MMC_ARCHIVE_CLOSURE')
    require(raw==zip_bytes(values),'MMC_ARCHIVE_NOT_CANONICAL')
    return {'status':'PASS_EXACT_ARCHIVE','members':len(values),'sha256':hashlib.sha256(raw).hexdigest(),'authority_effect':'NONE'}

def build_wheel(root:Path=ROOT)->bytes:
    values={rel[len('src/'):]:p.read_bytes() for rel,p in regular_files(root/'src') for rel in ['src/'+rel]}
    base='mosaic_migration_compiler-0.1.0a1.dist-info/'
    values[base+'METADATA']=b'Metadata-Version: 2.1\nName: mosaic-migration-compiler\nVersion: 0.1.0a1\nSummary: Non-effectful deterministic migration model compiler\nRequires-Python: >=3.12\n\nTurn 1 foundation engineering candidate; no production authority.\n'
    values[base+'WHEEL']=b'Wheel-Version: 1.0\nGenerator: mmc-stdlib-builder-t1\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
    values[base+'entry_points.txt']=b'[console_scripts]\nmmc = mosaic_mmc.cli:main\n'
    s=io.StringIO(newline='');writer=csv.writer(s,lineterminator='\n')
    for n,v in sorted(values.items()):writer.writerow([n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(v).digest()).rstrip(b'=').decode(),str(len(v))])
    writer.writerow([base+'RECORD','','']);values[base+'RECORD']=s.getvalue().encode()
    return zip_bytes(values)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--wheel');p.add_argument('--verify');a=p.parse_args()
    if a.source:Path(a.source).write_bytes(build_source())
    if a.wheel:Path(a.wheel).write_bytes(build_wheel())
    if a.verify:print(canonical(verify_source_archive(Path(a.verify).read_bytes())).decode())
