from __future__ import annotations
from pathlib import Path
import hashlib
import re
import os
import stat
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/'src') not in sys.path: sys.path.insert(0,str(ROOT/'src'))
from mosaic_mmc import canonical, decode, digest, MMCError
from mosaic_mmc.errors import require
from mosaic_mmc._pins import PROGRAM_ROOT

def read_json(path):return decode(Path(path).read_bytes(),limit=8*1024*1024)
def save_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(canonical(value))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def regular_files(root: Path):
    require(root.is_dir() and not root.is_symlink(),'MMC_SOURCE_ROOT')
    found=[]
    def walk(directory):
        try:
            with os.scandir(directory) as scan: entries=sorted(scan,key=lambda e:e.name)
            for entry in entries:
                p=Path(entry.path);rel=p.relative_to(root).as_posix()
                if rel=='.git':continue
                require(not entry.is_symlink() and not(hasattr(p,'is_junction') and p.is_junction()),'MMC_SOURCE_LINK',rel)
                st=entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):walk(p);continue
                require(stat.S_ISREG(st.st_mode),'MMC_SOURCE_KIND',rel)
                if '__pycache__' in p.parts:
                    require(p.suffix=='.pyc','MMC_SOURCE_CACHE_CONTENT',rel)
                    continue
                require(p.suffix not in ('.pyc','.pyo'),'MMC_SOURCE_BYTECODE',rel)
                require(st.st_size<=16*1024*1024,'MMC_SOURCE_FILE_LIMIT',rel)
                found.append((rel,p))
        except OSError as exc:
            from mosaic_mmc import MMCError
            raise MMCError('MMC_SOURCE_IO',str(directory.relative_to(root)),type(exc).__name__) from exc
    walk(root)
    return sorted(found,key=lambda x:x[0])

def source_snapshot(root: Path=ROOT):
    rows=[]
    for rel,p in regular_files(root):
        if rel in ('FILE-MANIFEST.json','provenance/SOURCE-ADMISSION.json'):continue
        if rel.startswith('evidence/'):
            require(p.suffix in ('.json','.txt','.xml','.md','.zip','.log'), 'MMC_EVIDENCE_EXECUTABLE',rel)
            continue
        rows.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)})
    body={'schema':'mmc.source-inventory.t1','files':rows}
    return {'body':body,'root':digest('source-inventory',body)}

def verify_source(root:Path, expected:str):
    require(type(expected) is str and re.fullmatch('[0-9a-f]{64}',expected) is not None,'MMC_SOURCE_PIN_REQUIRED')
    actual=source_snapshot(root)
    require(actual['root']==expected,'MMC_SOURCE_PIN_MISMATCH')
    return actual

def verify_freeze(root:Path=ROOT,expected:str=PROGRAM_ROOT):
    data=read_json(root/'constitution/FREEZE.json')
    require(set(data)=={'body','root'} and data['root']==expected==digest('program-freeze',data['body']),'MMC_FREEZE_PIN')
    listed=set()
    for row in data['body']['files']:
        require(set(row)=={'path','bytes','sha256'} and type(row['bytes']) is int,'MMC_FREEZE_ROW')
        p=root/row['path'];listed.add(p.name)
        require(p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'MMC_FREEZE_FILE',row['path'])
        copy=root/'src/mosaic_mmc/data'/p.name
        require(copy.is_file() and copy.read_bytes()==p.read_bytes(),'MMC_FREEZE_RUNTIME_COPY',row['path'])
    names={p.name for p in (root/'constitution').iterdir()}
    require(names==listed|{'FREEZE.json'},'MMC_FREEZE_CLOSURE')
    return {'status':'PASS_EXACT_FREEZE','program_root':expected,'files':len(listed),'authority_effect':'NONE'}
