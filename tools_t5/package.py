"""T5 source format retains T1 closure rules; wheel metadata explicitly selects a4."""
from pathlib import Path
import argparse,base64,csv,io,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.package import build_source,verify_source_archive,zip_bytes,regular_files
from mosaic_mmc import canonical

def build_wheel(root=ROOT):
    import hashlib
    values={rel:p.read_bytes() for rel,p in regular_files(root/'src')}
    base='mosaic_migration_compiler-0.1.0a5.dist-info/'
    values[base+'METADATA']=b'Metadata-Version: 2.1\nName: mosaic-migration-compiler\nVersion: 0.1.0a5\nSummary: Migration compiler with bounded agent interfaces and native workbench and finite migration qualification\nRequires-Python: >=3.12\nProvides-Extra: operational\nProvides-Extra: qualification\nRequires-Dist: cryptography>=46,<47; extra == "operational" or extra == "qualification"\nRequires-Dist: jsonschema>=4,<5; extra == "qualification"\n\nExperimental T5 candidate. Base stdlib only; optional operational crypto.\n'
    values[base+'WHEEL']=b'Wheel-Version: 1.0\nGenerator: mmc-stdlib-builder-t5\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
    values[base+'entry_points.txt']=b'[console_scripts]\nmmc = mosaic_mmc.cli:main\nmmc-t2 = mosaic_mmc_t2.cli:main\nmmc-t3 = mosaic_mmc_t3.cli:main\nmmc-agent = mosaic_mmc_t4.cli:main\nmmc-workbench = mosaic_mmc_workbench.app:main\nmmc-foundry = mosaic_mmc_t5.cli:main\n'
    out=io.StringIO(newline='');w=csv.writer(out,lineterminator='\n')
    for n,v in sorted(values.items()):w.writerow([n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(v).digest()).rstrip(b'=').decode(),str(len(v))])
    w.writerow([base+'RECORD','','']);values[base+'RECORD']=out.getvalue().encode();return zip_bytes(values)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--wheel');p.add_argument('--verify');a=p.parse_args()
    if a.source:Path(a.source).write_bytes(build_source())
    if a.wheel:Path(a.wheel).write_bytes(build_wheel())
    if a.verify:print(canonical(verify_source_archive(Path(a.verify).read_bytes())).decode())
