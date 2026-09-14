"""Unified local stages; quick morphology is the default."""
import argparse,pathlib,os,sys,json,subprocess,time,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];SRC=ROOT/'src';BASE=ROOT.parents[1]/'review/tectonics-20260914'
def main():
    v15={'climate-v15-tiles':'climate-tile-structure.py','climate-v15-terrain':'climate-terrain.py','climate-v15-studies':'climate-terrain-queue.py','climate-v15-boundaries':'climate-boundaries.py','climate-v15-stellar':'climate-stellar.py','climate-v15-verify':'climate-terrain-verify.py','climate-v15-bake':'climate-terrain-export.py','climate-v15-assemble':'climate-terrain-assemble.py','climate-v15-runtime-status':'climate-rocke-status.py','climate-v15-run':'climate-rocke-run.py','climate-v15-control':'climate-exoplasim-control.py'}
    if '--stage' in sys.argv:
        v15.update({'climate-v15-coastal-repair':'climate-coastal-highlands.py','climate-v15-plumes':'climate-vorhan-plumes.py','climate-v15-plume-detail':'climate-vorhan-plume-detail.py','climate-v15-plume-bake':'climate-vorhan-plume-export.py','climate-v16-plume-tracks':'climate-plume-tracks.py'})
        v15.update({'climate-v16-track-bake':'climate-plume-tracks-export.py','climate-v17-lake':'climate-high-inland-sea.py','climate-v18-candidates':'climate-warm-candidates.py','climate-v18-spectra':'climate-sf6-measured.py','climate-v18-verify':'climate-warm-verify.py','climate-v18-terrain':'climate-terrain-completion.py'})
        v15.update({'climate-v19-water':'climate-continuous-water.py','climate-v19-water-verify':'climate-water-spinup-verify.py','climate-v19-island-detail':'climate-keld-detail.py','climate-v19-season-verify':'climate-season-verify.py','climate-v19-vegetation-start':'climate-vegetation-start.py','climate-v19-cloud-bake':'climate-cloud-bake.py','climate-v19-terrain-bake':'climate-delivery-bake.py'})
        v15.update({'climate-v19-story-outlets':'climate-story-outlets-v19.py','climate-v19-joint-bake':'climate-joint-delivery.py'})
        at=sys.argv.index('--stage');stage=sys.argv[at+1]
        if stage in v15:
            args=sys.argv[1:at]+sys.argv[at+2:]
            raise SystemExit(subprocess.call([sys.executable,'-X','utf8',str(SRC/v15[stage]),*args]))
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['tectonic','erosion','global','refine','climate','ecology','bake','verify','all','mesorelief','river-history','polar-ci','radiation-check','evolution-bake','river-coast','geomorph-detail','geomorph-verify','cycle','cycle-detail','cycle-bake','cycle-verify','story-connect','story-bake','story-verify'],default='tectonic');ap.add_argument('--region',default='all');ap.add_argument('--base',type=pathlib.Path);ap.add_argument('--base-study',type=pathlib.Path);ap.add_argument('--mode',choices=['erosion-only','episodic','both'],default='both');ap.add_argument('--event-density',type=float,default=1);ap.add_argument('--seed',type=int);ap.add_argument('--mask',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path);ap.add_argument('--fidelity',choices=['preview','regional'],default='preview');ap.add_argument('--years',type=int);ap.add_argument('--fault-density',type=float,default=1.5);ap.add_argument('--magmatic-intensity',type=float,default=1);ap.add_argument('--climate-folder',type=pathlib.Path);ap.add_argument('--execute-climate',action='store_true');ap.add_argument('--resolution',choices=['T21','T42'],default='T21');ap.add_argument('--co2',type=float,default=.001);a=ap.parse_args()
    a.out=(a.out or (BASE/'landscape-v14' if a.stage.startswith('story-') else BASE/'runs'/str(time.time_ns()))).resolve();a.out.mkdir(parents=True,exist_ok=True);record_dir=a.out/'run-records'/str(time.time_ns());record_dir.mkdir(parents=True);grid=16000 if a.fidelity=='preview' else 2000;years=a.years or (100000 if a.fidelity=='preview' else 2000000)
    # Freeze masks: later browser strokes must not alter an active simulation.
    if a.mask:
        source=a.mask.resolve();snap=record_dir/'masks'
        if source.is_dir():shutil.copytree(source,snap)
        else:snap=record_dir/source.name;shutil.copy2(source,snap)
        a.mask=snap
    source_dir=record_dir/'source';source_dir.mkdir()
    for file in list(SRC.glob('tectonics-*.py'))+list(SRC.glob('landscape-*.py')):shutil.copy2(file,source_dir/file.name)
    env={**os.environ,'PYTHONUTF8':'1','TECTONICS_WORK':str(a.out),'TECTONICS_GRID_M':str(grid)}
    if a.base:env['TECTONICS_FROZEN_BASE']=str(a.base.resolve())
    if a.climate_folder:env['TECTONICS_REAL_CLIMATE']=str(a.climate_folder.resolve())
    stages=['tectonic','global','bake','verify'] if a.stage=='all' else [a.stage]
    state={'requested':{k:str(v) if isinstance(v,pathlib.Path) else v for k,v in vars(a).items()},'stages':[],'status':'running','started':time.time(),'scope':'requested local stages; not a full-planet completion claim'}
    def save():
        text=json.dumps(state,ensure_ascii=False,indent=2);(record_dir/'pipeline.json').write_text(text,encoding='utf8');(a.out/'pipeline.json').write_text(text,encoding='utf8')
    save()
    for stage in stages:
        common=[sys.executable]
        if stage.startswith('story-'):
            script={'story-connect':'landscape-connect.py','story-bake':'landscape-connect-export.py','story-verify':'landscape-connect-verify.py'}[stage];cmd=common+[str(SRC/script)]
            if a.out!=BASE/'landscape-v14':raise SystemExit('Story connection stages currently use the registered landscape-v14 study directory.')
            if stage=='story-connect':cmd+=['--seed',str(a.seed or 5210914),'--scenario','all' if a.seed in [None,5210914] else 'baseline']
        elif stage=='cycle':
            cmd=common+[str(SRC/'tectonics-cycle.py'),'--work',str(a.out),'--region',a.region,'--grid-m',str(grid),'--end',str(years),'--mode',a.mode,'--event-density',str(a.event_density)]+(['--seed',str(a.seed)] if a.seed else [])+(['--mask',str(a.mask)] if a.mask else [])+(['--base-study',str(a.base_study)] if a.base_study else [])
        elif stage in ['cycle-detail','cycle-bake','cycle-verify','story-connect','story-bake','story-verify']:
            script={'cycle-detail':'tectonics-cycle-detail.py','cycle-bake':'tectonics-cycle-export.py','cycle-verify':'tectonics-cycle-verify.py'}[stage];cmd=common+[str(SRC/script),'--work',str(a.out)]
            if stage=='cycle-detail':
                if a.seed not in [None,5210914]:raise SystemExit('Registered fine windows use seed5210914; create a separate selected-window study for another seed.')
                cmd+=['--mode',a.mode,'--end',str(years)]+(['--region',a.region] if a.region!='all' else [])+(['--mask',str(a.mask)] if a.mask else [])
        elif stage=='mesorelief':
            cmd=common+[str(SRC/'tectonics-continuation.py'),'--work',str(a.out),'--region',a.region,'--grid-m',str(grid),'--end',str(years)]+(['--seed',str(a.seed)] if a.seed else [])+(['--mask',str(a.mask)] if a.mask else [])
        elif stage=='river-history':
            cmd=common+[str(SRC/'tectonics-ishkar.py'),'--work',str(a.out),'--stage','all']
        elif stage=='river-coast':
            cmd=common+[str(SRC/'tectonics-ishkar-coast.py'),'--work',str(a.out),'--grid-m',str(grid)]
        elif stage=='geomorph-detail':
            cmd=common+[str(SRC/'tectonics-detail-study.py'),'--work',str(a.out),'--seed',str(a.seed or 5210914)]+(['--mask',str(a.mask)] if a.mask else [])
        elif stage=='geomorph-verify':
            cmd=common+[str(SRC/'tectonics-geomorph-verify.py'),'--work',str(a.out)]
        elif stage=='polar-ci':
            cmd=common+[str(SRC/'tectonics-polar-ci.py'),'--work',str(a.out),'--seed',str(a.seed or 5210914)]+(['--mask',str(a.mask)] if a.mask else [])
        elif stage=='radiation-check':
            cmd=common+[str(SRC/'tectonics-radiation.py'),'--work',str(a.out)]
        elif stage=='evolution-bake':
            cmd=common+[str(SRC/'tectonics-evolution-export.py'),'--work',str(a.out)]
        elif stage in ['tectonic','erosion']:
            cmd=common+[str(SRC/'tectonics-model.py'),'--out',str(a.out),'--grid-m',str(grid),'--years',str(years),'--region',a.region,'--fault-density',str(a.fault_density),'--magmatic-intensity',str(a.magmatic_intensity),'--stage','all' if stage=='tectonic' else 'evolve']
            if a.seed:cmd+=['--seed',str(a.seed)]
            if a.mask:cmd+=['--mask',str(a.mask)]
        elif stage=='global':cmd=common+[str(SRC/'tectonics-world.py'),'--work',str(a.out)]+(['--seed',str(a.seed)] if a.seed else [])
        elif stage=='bake':cmd=common+[str(SRC/'tectonics-export.py'),'--work',str(a.out)]
        elif stage=='refine':cmd=common+[str(SRC/'tectonics-refine.py'),'--work',str(a.out),'--region',a.region,'--end',str(years)]+(['--mask',str(a.mask)] if a.mask else [])
        elif stage=='verify':cmd=common+[str(SRC/'tectonics-verify.py'),'--work',str(a.out),'--partial']
        elif stage=='climate':
            cmd=common+[str(SRC/'tectonics-climate.py'),'--work',str(a.out),'--stage','run' if a.execute_climate else 'prepare','--resolution',a.resolution,'--co2',str(a.co2),'--phase','equilibrate']+(['--seed',str(a.seed)] if a.seed else [])
        else:
            if not a.climate_folder:state['status']='needs-real-climate';save();raise SystemExit('Ecology requires --climate-folder with verified radiation, planetary circulation, matching terrain and seasonal hydrology.')
            cmd=common+[str(SRC/'tectonics-ecology.py'),'--work',str(a.out),'--climate',str(a.climate_folder),'--seed',str(a.seed or 5210914)]+(['--mask',str(a.mask)] if a.mask else [])
        rec={'stage':stage,'command':cmd,'started':time.time()};state['stages'].append(rec);save();result=subprocess.run(cmd,env=env);rec.update(exitCode=result.returncode,finished=time.time());save()
        if result.returncode:state['status']='needs-attention';save();raise SystemExit(result.returncode)
        if stage=='bake':
            result=subprocess.run(common+[str(SRC/'tectonics-bake.py')],env=env)
            if result.returncode:state['status']='bake-incomplete';save();raise SystemExit(result.returncode)
    state['status']='requested-stages-finished';save()
if __name__=='__main__':main()

