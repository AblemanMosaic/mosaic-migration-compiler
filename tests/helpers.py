from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT))
from mosaic_mmc import decode,canonical,MMCError

def model(domain='identity'):
    return decode((ROOT/'examples'/f'{domain}.json').read_bytes())
def get(m,id):return next(x for x in m['objects'] if x['id']==id)
def a(m,id):return get(m,id)['attributes']
def copied(x):return decode(canonical(x),limit=8*1024*1024)
def refuses(test,fn,code=None):
    with test.assertRaises(MMCError) as ctx:fn()
    if code:test.assertEqual(ctx.exception.code,code)
    return ctx.exception
