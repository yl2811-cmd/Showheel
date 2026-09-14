"""Short CO2/H2O orbit controls; never an accepted Archeon climate."""
from pathlib import Path
import json,hashlib,shutil,time,argparse
import numpy as np
import exoplasim
parser=argparse.ArgumentParser();parser.add_argument('--earth-fraction',type=float,default=.8);parser.add_argument('--initial',choices=['both','native-default','frozen-restart'],default='both');args=parser.parse_args()
task=Path('/mnt/d/SKBS/review/climate-terrain-20260914');old=task/'climate/5210914/T21-co2-0.001';base=json.loads((old/'request.json').read_text());orbits=json.loads((task/'warm-climate-v18/orbit-candidates.json').read_text())['orbits'];orbit=next(v for v in orbits if v['id']==f's{args.earth_fraction:.2f}')
status=json.loads((old/'control-status.json').read_text());root=task/'warm-climate-v18'/('orbit-controls-v19' if args.earth_fraction==.8 else f'orbit-controls-s{args.earth_fraction:.2f}-v19');root.mkdir(exist_ok=True)
for state in ['native-default','frozen-restart'] if args.initial=='both' else [args.initial]:
    out=root/state;out.mkdir(exist_ok=True)
    if (out/'complete.json').exists():continue
    local=Path('/home/archeon/exoplasim-orbit-v19-'+orbit['id']+'-'+state);params=dict(base['params']);params.pop('resolution');params.update(flux=orbit['stellarFluxWm2'],year=orbit['periodEarthDays'],rotationperiod=orbit['calendar']['siderealDaySeconds']/86400,runsteps=round(orbit['calendar']['orbitalPeriodSeconds']/1800),landmap=str(old/'land.sra'),topomap=str(old/'topography.sra'))
    prior=[];completed=sorted(out.glob('orbit-*-report.json'))
    if completed:
        prior=[json.loads(p.read_text()) for p in completed];params['restartfile']=str(out/'latest-restart')
    elif state=='frozen-restart':params['restartfile']=str(old/status['restartFile'])
    model=exoplasim.Model(resolution='T21',layers=10,ncpus=4,precision=8,inityear=len(prior),workdir=str(local),modelname='ARCHEON_ORBIT_CONTROL',outputtype='.npz',recompile=False,crashtolerant=False,outputfaulttolerant=False)
    model.configure(**params);fields=['tas','ts','pr','prsn','clt','ps','ntr','hfns','rss','lsm','alb','rst','rlut','rsut','sic','prw'];model.cfgpostprocessor(variables=fields,times=20,timeaverage=True,extension='.npz')
    request={'state':state,'params':params,'orbit':orbit,'oldTerrainLineage':base['lineage'],'omittedAbsorbers':['SF6','N2O'],'climateAccepted':False,'scope':'short CO2/H2O control on frozen legacy topography; no inference of stable 12-14C or regional aridity','actualRunSecondsPerRecord':params['runsteps']*1800,'runDurationRoundingSeconds':params['runsteps']*1800-orbit['calendar']['orbitalPeriodSeconds']};(out/'request.json').write_text(json.dumps(request,indent=2))
    for i in range(len(prior)+1,4):
        started=time.time();model.run(years=1,postprocess=True,crashifbroken=True,clean=False);file=sorted(p for p in local.glob('*.npz') if not p.stem.endswith('_metadata'))[-1]
        with np.load(file,allow_pickle=False) as f:
            # Save arrays uncompressed, including when the library defaults differ.
            np.savez(out/f'orbit-{i}.npz',**{k:f[k] for k in f.files});w=np.load(old/'weights.npy');w=w/w.sum();mean=lambda a:float(np.mean(np.sum(a*w[None,:,None],axis=-2)));up=-mean(f['rsut']);incoming=mean(f['rst'])+up;ocean=1-f['lsm']
            record={'record':i,'elapsedSeconds':time.time()-started,'meanTemperatureC':mean(f['tas'])-273.15,'toaNetWm2':mean(f['ntr']),'meanCloudFraction':mean(f['clt']),'oceanSeaIceFraction':mean(f['sic']*ocean)/mean(ocean),'planetaryAlbedo':up/incoming,'incomingShortwaveWm2':incoming,'waterVapourColumnKgM2':mean(f['prw']),'physicalElapsedEarthYears':i*params['runsteps']*1800/31557600,'climateAccepted':False,'outputSha256':hashlib.sha256((out/f'orbit-{i}.npz').read_bytes()).hexdigest()}
            assert np.isfinite(list(record[k] for k in ['meanTemperatureC','toaNetWm2','planetaryAlbedo'])).all();assert abs(incoming-params['flux']/4)<.03*params['flux']/4
        shutil.copyfile(local/'plasim_restart',out/'latest-restart');(out/f'orbit-{i}-report.json').write_text(json.dumps(record,indent=2));prior.append(record);print(state,record,flush=True)
    (out/'complete.json').write_text(json.dumps({'status':'short control completed','history':prior,'climateAccepted':False,'convergenceNotTested':True},indent=2))
