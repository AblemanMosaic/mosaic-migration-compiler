"""Verify a closed delivery against its separately accepted ZIP SHA-256; no extraction/execution."""
import argparse,hashlib,json,zipfile
from pathlib import Path

def pairs(items):
    out={}
    for k,v in items:
        if k in out:raise ValueError('duplicate key')
        out[k]=v
    return out

def verify(path,expected):
    p=Path(path);raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('transport pin mismatch')
    with zipfile.ZipFile(p) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or any('/' in n or '\\' in n or n in ('.','..') for n in names):raise ValueError('invalid flat delivery')
        env=json.loads(z.read('DELIVERY-MANIFEST.json'),object_pairs_hook=pairs)
        if set(env)!={'schema','artifacts','authority_effect','signature'} or env['schema']!='mmc.delivery.t1' or env['authority_effect']!='NONE' or env['signature']!='NOT_SIGNED':raise ValueError('manifest shape')
        rows=env['artifacts'];expected_names=[r['name'] for r in rows]
        if len(expected_names)!=len(set(expected_names)) or set(names)!=set(expected_names)|{'DELIVERY-MANIFEST.json'}:raise ValueError('closure mismatch')
        for r in rows:
            if set(r)!={'name','bytes','sha256'} or type(r['bytes']) is not int:raise ValueError('row type')
            content=z.read(r['name'])
            if len(content)!=r['bytes'] or hashlib.sha256(content).hexdigest()!=r['sha256']:raise ValueError('member mismatch')
    return {'status':'PASS_EXACT_DELIVERY','members':len(names),'sha256':expected,'signature':'NOT_SIGNED'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--expected-sha256',required=True);a=p.parse_args();print(json.dumps(verify(a.archive,a.expected_sha256),sort_keys=True))
