"""Headless UI parity, import labels, replay and explicit local export."""
from pathlib import Path
import sys,tempfile
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from mosaic_mmc import canonical,decode
from mosaic_mmc_workbench.model import Workbench
from mosaic_mmc_t4.exports import LocalExport

def run():
    data=decode((ROOT/'examples/t4/public-demo.json').read_bytes())
    ui=Workbench();ui.load(data['workspace']);assert ui.reader is None
    ui.select_reader(data['reader'],demonstration=True);ui.evaluate()
    packet=ui.packet();ui.load(packet);assert ui.history[0]['verification']=='IMPORTED_NOT_REPLAYED'
    ui.select_reader(data['reader'],demonstration=True);ui.replay_history(0)
    with tempfile.TemporaryDirectory() as d:
        e=LocalExport(d,state_token=lambda:ui.status());p=e.prepare(ui.packet(),'review.json')
        assert not list(Path(d).iterdir())
        r=e.commit(e.approve(p['root']));assert (Path(d)/'review.json').is_file()
    return {'status':'PASS','result':ui.status()['assessment_status'],'export':r['status'],'target_effects':'NOT_EXECUTED','authority_effect':'NONE'}
if __name__=='__main__':print(canonical(run()).decode())
