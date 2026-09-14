"""Unified local stages; quick morphology is the default."""
import argparse,pathlib,os,sys,json,subprocess,time,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];SRC=ROOT/'src';BASE=ROOT.parents[1]/'review/tectonics-20260914'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['tectonic','erosion','global','refine','climate','ecology','bake','verify','all','mesorelief','river-history','polar-ci','radiation-check','evolution-bake','river-coast','geomorph-detail','geomorph-verify'],default='tectonic');ap.add_argument('--region',default='all');ap.add_argument('--base',type=pathlib.Path);ap.add_argument('--seed',type=int);ap.add_argument('--mask',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path);ap.add_argument('--fidelity',choices=['preview','regional'],default='preview');ap.add_argument('--years',type=int);ap.add_argument('--fault-density',type=float,default=1.5);ap.add_argument('--magmatic-intensity',type=float,default=1);ap.add_argument('--climate-folder',type=pathlib.Path);ap.add_argument('--execute-climate',action='store_true');ap.add_argument('--resolution',choices=['T21','T42'],default='T21');ap.add_argument('--co2',type=float,default=.001);a=ap.parse_args()
    a.out=(a.out or BASE/'runs'/str(time.time_ns())).resolve();a.out.mkdir(parents=True,exist_ok=True);record_dir=a.out/'run-records'/str(time.time_ns());record_dir.mkdir(parents=True);grid=16000 if a.fidelity=='preview' else 2000;years=a.years or (100000 if a.fidelity=='preview' else 2000000)
    # Freeze masks: later browser strokes must not alter an active simulation.
    if a.mask:
        source=a.mask.resolve();snap=record_dir/'masks'
        if source.is_dir():shutil.copytree(source,snap)
        else:snap=record_dir/source.name;shutil.copy2(source,snap)
        a.mask=snap
    source_dir=record_dir/'source';source_dir.mkdir()
    for file in SRC.glob('tectonics-*.py'):shutil.copy2(file,source_dir/file.name)
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
        if stage=='mesorelief':
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
            if not a.climate_folder:state['status']='needs-real-climate';save();raise SystemExit('Ecology requires --climate-folder with balanced ExoPlaSim output.')
            cmd=common+[str(SRC/'tectonics-ecology.py'),'--work',str(a.out),'--climate',str(a.climate_folder),'--seed',str(a.seed or 5210914)]+(['--mask',str(a.mask)] if a.mask else [])
        rec={'stage':stage,'command':cmd,'started':time.time()};state['stages'].append(rec);save();result=subprocess.run(cmd,env=env);rec.update(exitCode=result.returncode,finished=time.time());save()
        if result.returncode:state['status']='needs-attention';save();raise SystemExit(result.returncode)
        if stage=='bake':
            result=subprocess.run(common+[str(SRC/'tectonics-bake.py')],env=env)
            if result.returncode:state['status']='bake-incomplete';save();raise SystemExit(result.returncode)
    state['status']='requested-stages-finished';save()
if __name__=='__main__':main()

