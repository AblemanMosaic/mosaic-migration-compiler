from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from mosaic_mmc_t4.schemas import schemas
from mosaic_mmc import canonical
if __name__=='__main__':
    for n,s in schemas().items():(ROOT/'schemas/t4'/f'{n}.schema.json').write_bytes(canonical(s))
