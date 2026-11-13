"""Actual Tk interaction checks. Run under a real display or explicitly provisioned Xvfb."""
from pathlib import Path
import sys,time,tempfile,json
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
INSTALLED='--installed' in sys.argv
if not INSTALLED:sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from mosaic_mmc import canonical,MMCError,decode
from mosaic_mmc_workbench.app import Application,PAGES
from mosaic_mmc_t4.views import assess_view,reader_for_sample
from mosaic_mmc_t4.common import envelope

def run(output=None):
    checks=[];app=Application()
    def check(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    def wait():
        deadline=time.monotonic()+15
        while app.future is not None and time.monotonic()<deadline:app.update();time.sleep(.01)
        check('worker completes '+str(len(checks)),app.future is None)
        app.update()
    try:
        app.update();check('ten pages',len(app.tabs.tabs())==10)
        check('initial no trust',app.model.reader is None and app.model.current is None)
        app.load_demo();app.update()
        check('demo loads without authority',app.model.reader is None and app.demo_reader is not None)
        app.guard(app.start_assessment);check('no implicit reader',app.last_error is not None and app.model.current is None)
        app.demo_enabled.set(True);app.toggle_demo();app.start_assessment();wait()
        check('context label public',app.model.context_label=='PUBLIC_FIXTURE_CONTEXT')
        check('court computed',app.model.current['body']['status']=='INDETERMINATE')
        check('headless UI exact parity',canonical(app.model.current)==canonical(assess_view(app.model.selection,app.model.reader)))
        check('missing obligation shown',len(app.obligations.get_children())>0)
        for page in PAGES:
            app.tabs.select(app.pages[page]);app.update();check('page visible '+page,app.pages[page].winfo_ismapped())
        app.claim.set('coverage');app.request_work();check('bounded work generated',app.model.work_order['body']['claim']=='coverage')
        check('work contains no effect grant',app.model.work_order['body']['permissions']['commit'] is False)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'workspace.json'
            with patch('mosaic_mmc_workbench.app.filedialog.asksaveasfilename',return_value=str(path)),patch('mosaic_mmc_workbench.app.messagebox.askyesno',return_value=False):app.export_dialog()
            check('cancel export has no write',not path.exists())
            with patch('mosaic_mmc_workbench.app.filedialog.asksaveasfilename',return_value=str(path)),patch('mosaic_mmc_workbench.app.messagebox.askyesno',return_value=True):app.export_dialog()
            check('explicit export creates file',path.is_file())
            original=path.read_bytes()
            with patch('mosaic_mmc_workbench.app.filedialog.asksaveasfilename',return_value=str(path)):
                app.guard(app.export_dialog)
            check('overwrite refused',path.read_bytes()==original and 'EXISTS' in str(app.last_error))
            packet=decode(original);app.load_packet(packet);app.update()
            check('import clears reader',app.model.reader is None)
            check('history not replayed',app.model.history[0]['verification']=='IMPORTED_NOT_REPLAYED')
            r=reader_for_sample(app.model.selection);app.model.select_reader(r,demonstration=True);app.render()
            app.history_tree.selection_set(app.history_tree.get_children()[0]);app.replay_selected()
            check('selected replay verified',app.model.history[0]['verification']=='REPLAYED_CURRENT_CONTEXT')
        # Source-context invalidation must never leave the old result displayed as current.
        bad=reader_for_sample(app.model.selection);bad['expected_policy_root']='f'*64
        app.guard(lambda:app.model.select_reader(bad));check('failed context clears current',app.model.current is None and app.model.reader is None)
        app.load_demo();app.demo_enabled.set(True);app.toggle_demo()
        # One worker at a time and cancellation discards its result.
        actual=assess_view
        def delayed(s,r):time.sleep(.12);return actual(s,r)
        with patch('mosaic_mmc_workbench.app.assess_view',delayed):
            app.start_assessment();app.guard(app.start_assessment)
            check('second worker refused','WORKER_BUSY' in str(app.last_error));app.cancel();wait()
        check('cancelled result absent',app.model.current is None)
        app.start_assessment();wait();check('safe reassessment progresses',app.model.current is not None)
        app.tabs.select(app.pages['Obligations']);app.update()
        check('footer visible',app.winfo_height()>=640)
        if output:
            from PIL import ImageGrab
            p=Path(output);p.mkdir(parents=True,exist_ok=True)
            app.lift();app.focus_force();app.update();time.sleep(.08);app.update()
            box=(app.winfo_rootx(),app.winfo_rooty(),app.winfo_rootx()+app.winfo_width(),app.winfo_rooty()+app.winfo_height())
            ImageGrab.grab(bbox=box).save(p/'workbench.png')
        result={'schema':'mmc.gui-smoke.t4','status':'PASS','checks':checks,'count':len(checks),'platform':'ACTUAL_TK_CURRENT_DISPLAY','installed_environment':INSTALLED,'module_path':__import__('mosaic_mmc_workbench').__file__,'operator_confirmation':'SIMULATED_EXPLICIT_TEST_ACTIONS','target_effects':'NOT_EXECUTED','host_effects':'TEMPORARY_CREATE_ONLY_EXPORT','authority_effect':'NONE'}
        if output:(Path(output)/'GUI.json').write_bytes(canonical(result))
        return result
    finally:app.close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out');p.add_argument('--installed',action='store_true');a=p.parse_args();print(canonical(run(a.out)).decode())
