"""Standalone bounded delivery integrity check. Caller must recognize the expected hash."""
import argparse,hashlib,io,json,re,stat,sys,zipfile

def exact_object(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate JSON key')
        d[k]=v
    return d

def verify(raw,expected=None):
    if type(raw) is not bytes or len(raw)>192*1024*1024:raise ValueError('delivery byte limit')
    actual=hashlib.sha256(raw).hexdigest()
    if expected is not None and (not re.fullmatch('[a-f0-9]{64}',expected) or actual!=expected):raise ValueError('external transport mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or len(names)>32:raise ValueError('member count/duplicate')
        for i in infos:
            if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,170}',i.filename) or '..' in i.filename:raise ValueError('member name')
            if i.is_dir() or stat.S_IFMT(i.external_attr>>16)!=stat.S_IFREG:raise ValueError('member kind')
            if i.flag_bits&1 or i.file_size>96*1024*1024:raise ValueError('member budget')
        if sum(i.file_size for i in infos)>192*1024*1024:raise ValueError('expanded limit')
        manifest=json.loads(z.read('DELIVERY-MANIFEST.json'),object_pairs_hook=exact_object)
        if set(manifest)!={'schema','artifacts','authority_effect','signature','native_pippi','public_release'} or manifest['schema']!='mmc.delivery.t6':raise ValueError('manifest shape')
        if manifest['authority_effect']!='NONE' or manifest['signature']!='NOT_SIGNED' or manifest['native_pippi']!='NOT_BOUND' or manifest['public_release']!='NOT_CLEARED':raise ValueError('claim ceiling')
        rows=manifest['artifacts']
        if type(rows) is not list or len(rows)>31:raise ValueError('manifest limit')
        seen=set()
        for row in rows:
            if type(row) is not dict or set(row)!={'name','bytes','sha256'} or type(row['name']) is not str or type(row['bytes']) is not int or row['bytes']<0 or type(row['sha256']) is not str or not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('row shape/type')
            name=row['name']
            if name in seen or name=='DELIVERY-MANIFEST.json':raise ValueError('duplicate/self row')
            seen.add(name);data=z.read(name)
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('member hash')
        if set(names)!=seen|{'DELIVERY-MANIFEST.json'}:raise ValueError('closure')
    return {'schema':'mmc.delivery-check.t6','status':'PASS_EXACT_DELIVERY','artifacts':len(rows),'archive_sha256':actual,'expected_hash_checked':expected is not None,'signature':'NOT_SIGNED','publisher_authentication':'NOT_ESTABLISHED','authority_effect':'NONE'}

def main():
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--expected-sha256');a=p.parse_args()
    try:
        f=Path(a.archive)
        if f.is_symlink() or not f.is_file() or f.stat().st_size>192*1024*1024:raise ValueError('archive admission')
        r=verify(f.read_bytes(),a.expected_sha256);print(json.dumps(r,sort_keys=True,separators=(',',':')));return 0
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as e:
        print(json.dumps({'status':'REFUSED','reason':str(e),'authority_effect':'NONE'}));return 2
if __name__=='__main__':raise SystemExit(main())
