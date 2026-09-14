"""Bake orbit means and native time bins from validated physical circulation."""
import pathlib,sys,importlib,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');K=importlib.import_module('climate-contract');np=C.np

def climatology(values,bounds,orbital_seconds,parts=None):
    bounds=np.asarray(bounds,float);values=np.asarray(values,float)
    if values.shape[0]!=len(bounds):raise ValueError('Cloud/time dimension mismatch')
    duration=K.TIME.interval_check(bounds,{'orbitalPeriodSeconds':orbital_seconds})
    annual=np.average(values,axis=0,weights=duration);seasons=[]
    if parts is None:return annual,values.copy()
    origin=bounds[0,0]
    for i in range(parts):
        lo=origin+i*orbital_seconds/parts;hi=origin+(i+1)*orbital_seconds/parts
        weight=np.maximum(0,np.minimum(bounds[:,1],hi)-np.maximum(bounds[:,0],lo))
        if weight.sum()<=0:raise ValueError('Missing season')
        seasons.append(np.average(values,axis=0,weights=weight))
    return annual,np.asarray(seasons)

def bake(folder):
    folder=pathlib.Path(folder);request,result=K.validate(folder,require_ready=False)
    if not request.get('cloudValidationRequired'):raise ValueError('Full cloud properties and seasonal stability are required for baking')
    cal=K.TIME.calendar(result['calendar']);out=C.ROOT/'foundation/warm-climate-v18'/request['fingerprint'][:16]
    with np.load(folder/'climate.npz',allow_pickle=False) as f:
        for key in K.CLOUD_UNITS:
            annual,seasons=climatology(f[key],f['time_bounds_seconds'],cal['orbitalPeriodSeconds'])
            C.save_array(out/(key+'-annual.npy'),annual.astype('float32'));C.save_array(out/(key+'-seasons.npy'),seasons.astype('float32'))
        for key in ['latitude','longitude']:C.save_array(out/(key+'.npy'),f[key])
        C.save_array(out/'time-bounds-seconds.npy',f['time_bounds_seconds'])
    C.write(out/'manifest.json',{'status':'validated climate candidate','calendar':cal,'fields':K.CLOUD_UNITS,'cloudStatistic':'mean area fraction; not a fixed cloud image or instantaneous weather','seasonConvention':'native model time bins, not a prescribed count of named seasons; annual file is an orbital mean','sourceClimateSha256':C.sha(folder/'climate.npz'),'requestFingerprint':C.request_fingerprint(request),'climateGrid':request.get('gridDegrees'),'terrainFingerprint':request['terrainFingerprint'],'hydrologyAccepted':result.get('hydrologyAccepted',False),'vegetationReady':False})
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);a=p.parse_args();print(bake(a.folder))
