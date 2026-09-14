"""Prepare area-weighted ExoPlaSim boundaries and dispatch an isolated Linux run.

No empirical terrain/rain proxy is accepted as circulation output. A preparation
is not a completed GCM run. The model worker validates units and energy balance.
"""
import pathlib,sys,json,importlib,argparse,hashlib,subprocess,os
from functools import lru_cache
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');np=T.np

def sra(path,code,a):
    with path.open('w',encoding='ascii',newline='\n') as f:
        f.write(' '.join(map(str,[code,0,20170927,0,a.shape[1],a.shape[0],0,0]))+'\n')
        np.savetxt(f,a.reshape(-1,8),fmt='%16.9e')

@lru_cache(maxsize=6)
def boundaries(work,seed,resolution):
    parent=work/'global'/str(seed);g=json.loads((parent/'grid.json').read_text());z=np.load(parent/'height.npy');kind=np.load(parent/'kind.npy');area=np.load(parent/'cell-area.npy')
    # Gaussian cells are bounded in sin(latitude) by their quadrature weights.
    nlats={'T21':32,'T42':64}[resolution];mu,weight=np.polynomial.legendre.leggauss(nlats);edges=np.r_[-1,-1+np.cumsum(weight)];edges[-1]=1
    lat=np.load(parent/'latitude.npy');lon=np.load(parent/'longitude.npy');row=nlats-1-np.clip(np.searchsorted(edges,np.sin(np.deg2rad(lat)),side='right')-1,0,nlats-1)
    nlon=nlats*2;col=np.floor((lon%360+180/nlon)/(360/nlon)).astype(int)%nlon;index=(row*nlon+col).ravel();size=nlats*nlon
    def total(v):return np.bincount(index,weights=(v*area).ravel(),minlength=size).reshape(nlats,nlon)
    a=total(np.ones_like(z));land=(kind>=30)&(kind!=200);land_area=total(land);fraction=land_area/np.maximum(a,1);binary=fraction>=.5
    topography=total(z*land)/np.maximum(land_area,1);topography[~binary]=0
    return {'height':topography,'land':binary.astype(float),'land-fraction':fraction,'latitude':np.degrees(np.arcsin(mu[::-1])),'longitude':np.arange(nlon)*360/nlon,'weights':weight[::-1]}, {'globalHeightSha256':T.sha(parent/'height.npy'),'globalKindSha256':T.sha(parent/'kind.npy'),'nativeLandAreaM2':float(land_area.sum()),'representedLandAreaM2':float(a[binary].sum()),'binaryMaskRelativeAreaError':float(abs(a[binary].sum()-land_area.sum())/land_area.sum()),'aggregation':'area weighted on Gaussian-cell bounds; islands below T21/T42 resolution may be absent','unknown':'FAR-5 uses inherited coarse boundary conditions only'}

def prepare(work,seed,resolution,co2):
    c=json.loads((work/'run-config.json').read_text());p=c['planet'];arrays,lineage=boundaries(work,seed,resolution);folder=work/'climate'/str(seed)/f'{resolution}-co2-{co2:g}';folder.mkdir(parents=True,exist_ok=True)
    solar=p['solarDayHours']*3600;year=p['yearEarthDays']*86400;sidereal=1/(1/solar+1/year);flux=1361*p['stellarLuminositySolar']/p['orbitAU']**2
    params={'resolution':resolution,'gravity':p['gravityMs2'],'radius':c['radiusM']/6371220,'rotationperiod':sidereal/86400,'year':p['yearEarthDays'],'obliquity':p['obliquityDegrees'],'eccentricity':0.0,'fixedorbit':True,'keplerian':True,'flux':flux,'startemp':p['stellarTemperatureK'],'pressure':p['seaLevelPressurePa']/1e5,'pCO2':co2*p['seaLevelPressurePa']/1e5,'pN2':(1-.185-co2)*p['seaLevelPressurePa']/1e5,'pO2':.185*p['seaLevelPressurePa']/1e5,'mldepth':c['climate']['mixedLayerDepthM'],'vegetation':False,'timestep':30 if resolution=='T21' else 20,'snapshots':None}
    params['runsteps']=round(year/(params['timestep']*60));params['otherargs']={'PLARAD@planet_namelist':str(c['radiusM'])}
    sra(folder/'land.sra',172,arrays['land']);sra(folder/'topography.sra',129,arrays['height']*p['gravityMs2'])
    for key,v in arrays.items():np.save(folder/(key+'.npy'),v)
    request={'model':'ExoPlaSim','requiredVersion':'3.4.2','status':'prepared, not run','seed':seed,'params':params,'climate':c['climate'],'targetSolarDaySeconds':solar,'siderealDaySeconds':sidereal,'yearSeconds':year,'sourceWork':str(work.resolve()),'lineage':lineage,'units':{'topography.sra':'m2 s-2, surface geopotential = gravity * height','land.sra':'binary land mask','radius':'Earth radii in API; PLARAD explicitly sets metres','pressure':'bar in API'},'radiativeLimits':['Mixed-layer ocean; no full ocean circulation.','CO2 brackets are hypotheses. Do not paint precipitation to force habitability.','Engineered trace-gas forcing is not represented by an arbitrary CO2 equivalence.'],'inputHashes':{f:T.sha(folder/f) for f in ['land.sra','topography.sra']}}
    request['fingerprint']=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest();T.savejson(folder/'request.json',request)
    return folder

def launch(folder,phase):
    worker=pathlib.Path(__file__).with_name('tectonics-gcm-worker.py').resolve()
    if os.name=='nt':
        def linux(p):
            p=pathlib.Path(p).resolve();return '/mnt/'+p.drive[0].lower()+str(p)[2:].replace('\\','/')
        cmd=['wsl.exe','--distribution','ArcheonSim','--user','archeon','--exec','/opt/archeon-venv/bin/python',linux(worker),'--request',linux(folder/'request.json'),'--phase',phase]
    else:cmd=[sys.executable,str(worker),'--request',str(folder/'request.json'),'--phase',phase]
    code=subprocess.call(cmd)
    if code:raise RuntimeError('GCM did not complete; retain the run log. Windows requires working WSL, ArcheonSim and /opt/archeon-venv. No proxy output was substituted.')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=T.WORK);ap.add_argument('--seed',type=int);ap.add_argument('--resolution',choices=['T21','T42','both'],default='both');ap.add_argument('--co2',type=float);ap.add_argument('--stage',choices=['prepare','run'],default='prepare');ap.add_argument('--phase',choices=['screen','equilibrate'],default='screen');a=ap.parse_args();c=json.loads((a.work/'run-config.json').read_text());folders=[]
    for seed in [a.seed] if a.seed else c['seeds']:
      for res in ['T21','T42'] if a.resolution=='both' else [a.resolution]:
       for co2 in [a.co2] if a.co2 is not None else c['climate']['co2VolumeFractions']:
        folder=prepare(a.work,seed,res,co2);folders.append(str(folder));print('GCM INPUT '+str(folder),flush=True)
        if a.stage=='run':launch(folder,a.phase)
    T.savejson(a.work/'climate-preparation.json',{'status':'inputs prepared; no executed circulation claim','requests':folders,'runtimePrerequisite':'Windows restart required after enabling VirtualMachinePlatform; then isolated ArcheonSim Linux setup'})

if __name__=='__main__':main()
