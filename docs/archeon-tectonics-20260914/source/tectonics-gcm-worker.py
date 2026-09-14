"""Linux-only ExoPlaSim worker. An incomplete/cold run remains a real result.

The Windows host only prepares boundaries and reads outputs. Compilation and
working files stay in an isolated Linux venv/work directory.
"""
import argparse,pathlib,json,sys,os,re,shutil,hashlib,importlib.metadata,time
import numpy as np

FIELDS=['tas','ts','pr','prsn','mrro','evap','uas','vas','hur','clt','snd','ntr','hfns','rss','ps','mrso']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')

def validate_output(file,lat_weights):
    with np.load(file,allow_pickle=False) as ds:
        missing=set(FIELDS)-set(ds.files)
        if missing:raise RuntimeError('Missing real GCM fields: '+str(sorted(missing)))
        values={k:np.asarray(ds[k],dtype=float) for k in FIELDS};values['lat']=np.asarray(ds['lat']);values['lon']=np.asarray(ds['lon'])
    meta_file=file.with_name(file.stem+'_metadata.npz')
    if not meta_file.exists():raise RuntimeError('GCM output metadata is required')
    with np.load(meta_file,allow_pickle=False) as meta:
        for field,unit in {'tas':'K','pr':'m s-1','ntr':'W m-2','ps':'hPa'}.items():
            if unit not in ' '.join(map(str,meta[field].ravel())):raise RuntimeError('Unexpected GCM units for '+field)
    for key,a in values.items():
        if not np.isfinite(a).all():raise RuntimeError('Non-finite '+key)
    toa=np.asarray(values['ntr']);surface=np.asarray(values['hfns']);weights=lat_weights/lat_weights.sum()
    return values,{'toaWm2':float(np.mean(np.sum(toa*weights[None,:,None],axis=-2))),'surfaceWm2':float(np.mean(np.sum(surface*weights[None,:,None],axis=-2))),'meanTemperatureK':float(values['tas'].mean())}

def run(request_path,phase):
    if os.name=='nt':raise RuntimeError('ExoPlaSim runs only in the isolated Linux environment')
    request=json.loads(request_path.read_text());dest=request_path.parent
    if importlib.metadata.version('exoplasim')!=request['requiredVersion']:raise RuntimeError('Pinned ExoPlaSim version mismatch')
    import exoplasim
    # This release derives solar day from an integer calendar length. Correct
    # that one relation so 27 h and 365.25 Earth days are both explicit inputs.
    # The patch is scoped to the task's isolated venv and recorded by hash.
    package=pathlib.Path(exoplasim.__file__).parent;source=package/'plasim/src/plasim.f90';before=source.read_text();old='solar_day = sidereal_day * n_days_per_year/(n_days_per_year-1)';new='solar_day = 1.0 / (1.0/sidereal_day - 1.0/sidereal_year)'
    if old in before:
        if before.count(old)!=1:raise RuntimeError('Unexpected solar-day source shape')
        source.write_text(before.replace(old,new));patched=True
    elif new in before:patched=False
    else:raise RuntimeError('Cannot verify the solar-day relation in pinned source')
    if (dest/'climate.npz').exists() and (dest/'result.json').exists():
        result=json.loads((dest/'result.json').read_text())
        if result.get('requestFingerprint')==request['fingerprint'] and (phase=='screen' or result.get('balanced')):return
    runroot=pathlib.Path.home()/'.local/share/archeon-gcm'/(request['fingerprint'][:20]+'-'+str(time.time_ns()))
    if not re.fullmatch(r'[A-Za-z0-9_./-]+',str(runroot)):raise RuntimeError('Linux run path must contain only safe path characters')
    runroot.mkdir(parents=True,exist_ok=True)
    for name in ['land.sra','topography.sra']:
        if sha(dest/name)!=request['inputHashes'][name]:raise RuntimeError('Climate boundary changed '+name)
        shutil.copy2(dest/name,runroot/name)
    status={'model':'ExoPlaSim','version':request['requiredVersion'],'phase':phase,'status':'running','requestFingerprint':request['fingerprint'],'sourceSolarDaySha256':sha(source),'solarDayPatch':'exact sidereal / orbital relation','history':[],'started':time.time()};save(dest/'status.json',status)
    params=dict(request['params']);resolution=params.pop('resolution');params.update(landmap=str(runroot/'land.sra'),topomap=str(runroot/'topography.sra'))
    # Completed matching outputs are reused. Failed attempts remain in separate
    # Linux directories; this worker does not claim restart-file validation yet.
    model=exoplasim.Model(resolution=resolution,layers=10,ncpus=8,precision=8,workdir=str(runroot/'model'),modelname='ARCHEON',outputtype='.npz',recompile=patched,crashtolerant=False,outputfaulttolerant=False)
    model.configure(**params);model.cfgpostprocessor(variables=FIELDS,times=20,timeaverage=True,extension='.npz')
    cfg=request['climate'];limit=cfg['screenYears'] if phase=='screen' else cfg['maxSpinupYears'];window=cfg['balanceWindowYears'];weights=np.load(dest/'weights.npy');balanced=False;files=[]
    for year in range(1,limit+1):
        model.run(years=1,postprocess=True,crashifbroken=True,clean=False)
        files=sorted(p for p in (runroot/'model').glob('*.npz') if not p.stem.endswith('_metadata'))
        if not files:raise RuntimeError('No postprocessed circulation output')
        values,diagnostic=validate_output(files[-1],weights);status['history'].append({'year':year,**diagnostic});save(dest/'status.json',status)
        if len(status['history'])>=window:
            tail=status['history'][-window:];toa=np.array([v['toaWm2'] for v in tail]);surface=np.array([v['surfaceWm2'] for v in tail]);drift=np.polyfit(np.arange(window),[v['meanTemperatureK'] for v in tail],1)[0]
            balanced=abs(toa.mean())<cfg['maxTOAImbalanceWm2'] and abs(surface.mean())<1 and abs(drift)<.02
        if phase=='equilibrate' and balanced:break
    samplefiles=files[-min(window,len(files)):];series={key:[] for key in FIELDS}
    for file in samplefiles:
        values,_=validate_output(file,weights)
        for key in FIELDS:
            a=values[key]
            if a.ndim==4:a=a[:,-1,:,:] # lowest atmospheric level, explicitly recorded
            if a.shape[0]!=20:raise RuntimeError('Expected twenty equal annual output intervals')
            series[key].append(a.reshape(5,4,*a.shape[-2:]).mean(axis=1))
    arrays={key:np.mean(series[key],axis=0).astype('float32') for key in FIELDS};arrays['latitude']=values['lat'];arrays['longitude']=values['lon'];np.savez(dest/'climate.npz',**arrays)
    result={**status,'status':'complete','balanced':balanced,'years':year,'requestFingerprint':request['fingerprint'],'sourceOutputHashes':{p.name:sha(p) for p in samplefiles},'climateSha256':sha(dest/'climate.npz'),'allowEcology':balanced,'seasons':'Five equal orbital-year intervals; not named Earth months','humidity':'lowest sigma level relative humidity','units':{'tas':'K','pr':'m/s','mrro':'m/s','evap':'m/s with model sign convention','ps':'hPa','rss':'W/m2'},'ocean':'50 m mixed layer; no full ocean dynamics'}
    save(dest/'result.json',result);save(dest/'status.json',result)
    print(json.dumps({'status':'complete','balanced':balanced,'years':year}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--request',type=pathlib.Path,required=True);ap.add_argument('--phase',choices=['screen','equilibrate'],default='screen');a=ap.parse_args()
    try:run(a.request.resolve(),a.phase)
    except Exception as e:
        save(a.request.resolve().parent/'failure.json',{'model':'ExoPlaSim','status':'failed','reason':str(e)});raise
