"""Build role-separated prospective study materials; no results or admission are generated."""
from pathlib import Path
import argparse,sys,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import regular_files,canonical,require
from tools.package import zip_bytes
from tools_t6.audit import freeze

def build(wheel:bytes):
    freeze()
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(wheel)) as z:
        m=z.read('mosaic_migration_compiler-0.1.0a6.dist-info/METADATA')
        require(b'Version: 0.1.0a6\n' in m,'MMC_T6_STUDY_WHEEL')
        # Exact expected installed payload, not merely a matching version string.
        actual={n:z.read(n) for n in z.namelist() if '.dist-info/' not in n}
        expected={n:p.read_bytes() for n,p in regular_files(ROOT/'src')}
        require(actual==expected,'MMC_T6_STUDY_WHEEL_PAYLOAD')
    shared={'TASK.md':(ROOT/'study/participant/TASK.md').read_bytes()}
    conventional={**shared,'ARM.md':(ROOT/'study/participant/CONVENTIONAL-ARM.md').read_bytes()}
    mmc={**shared,'ARM.md':(ROOT/'study/participant/MMC-ARM.md').read_bytes(),
         'mosaic_migration_compiler-0.1.0a6-py3-none-any.whl':wheel,
         'USER-AND-INTEGRATION.md':(ROOT/'docs/release/USER-AND-INTEGRATION.md').read_bytes()}
    operator={n.removeprefix('study/'):p.read_bytes() for n,p in regular_files(ROOT/'study') if not n.startswith('participant/')}
    operator['NOTICE.txt']=b'PREPARED_NOT_PERFORMED. Supply independent participants, hidden cases, allocation, budgets, analysis and observed effort. Public foundry cases are not blinded tests.\n'
    result={'MMC-STUDY-CONVENTIONAL-START.zip':zip_bytes(conventional),
            'MMC-STUDY-TREATMENT-START.zip':zip_bytes(mmc),'MMC-STUDY-OPERATOR.zip':zip_bytes(operator)}
    manifest={'schema':'mmc.study-packets.t6','state':'PREPARED_NOT_PERFORMED','files':[{'name':n,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in sorted(result.items())],
              'independent_holdouts':'NOT_SUPPLIED_OPERATOR_REQUIRED','assignment':'NOT_PERFORMED','human_effort':'NOT_MEASURED','authority_effect':'NONE'}
    result['STUDY-MANIFEST.json']=canonical(manifest);return zip_bytes(result)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--out',required=True);a=p.parse_args();Path(a.out).write_bytes(build(Path(a.wheel).read_bytes()))
