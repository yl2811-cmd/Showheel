"""Read-only GCM downscaling and feedback inputs with explicit provenance."""
import pathlib,json,hashlib
from functools import lru_cache
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from pyproj import Proj

@lru_cache(maxsize=2)
def read_climate(path):
    folder=pathlib.Path(path);r=json.loads((folder/'result.json').read_text(encoding='utf8'));request=json.loads((folder/'request.json').read_text(encoding='utf8'))
    if r.get('model')!='ExoPlaSim' or not r.get('balanced'):raise RuntimeError('Feedback requires balanced actual ExoPlaSim output')
    digest=hashlib.sha256((folder/'climate.npz').read_bytes()).hexdigest()
    if digest!=r['climateSha256'] or request['fingerprint']!=r['requestFingerprint']:raise RuntimeError('GCM dependency or checksum mismatch')
    with np.load(folder/'climate.npz',allow_pickle=False) as data:arrays={k:data[k].copy() for k in data.files}
    arrays['referenceHeight']=np.load(folder/'height.npy');return arrays,r,request

@lru_cache(maxsize=6)
def remap(path,grid_json):
    grid=json.loads(grid_json);arrays,result,request=read_climate(path);xx,yy=np.meshgrid(grid['xmin']+np.arange(grid['width'])*grid['stepM'],grid['ymax']-np.arange(grid['height'])*grid['stepM']);lon,lat=Proj(grid['projection'])(xx,yy,inverse=True)
    lo=arrays['longitude']%360;la=arrays['latitude'];ii=np.argsort(lo);jj=np.argsort(la);lo=lo[ii];la=la[jj];extended=np.r_[lo[-1]-360,lo,lo[0]+360];fields={}
    for key,value in arrays.items():
        if key in ['latitude','longitude']:continue
        a=value
        if a.ndim==2:a=np.broadcast_to(a,(5,*a.shape))
        a=a[:,jj,:][:,:,ii];a=np.concatenate([a[:,:,-1:],a,a[:,:,:1]],axis=2)
        fields[key]=np.stack([RegularGridInterpolator((la,extended),v,bounds_error=False,fill_value=None)((np.clip(lat,la.min(),la.max()),lon%360)) for v in a])
    return fields,result,request

def forcing(folder,grid,z,season=None):
    fields,result,request=remap(str(pathlib.Path(folder).resolve()),json.dumps(grid,sort_keys=True));year=request['yearSeconds'];get=lambda key:fields[key].mean(axis=0) if season is None else fields[key][season]
    dz=z-get('referenceHeight');temp=get('tas')-273.15-.0065*dz
    rain=np.maximum(get('pr'),0)*year;runoff=np.maximum(get('mrro'),0)*year
    # PlaSim landmod adds devap to precipitation. Reverse its sign here;
    # condensation remains negative evaporation, not an invented water loss.
    evap=-get('evap')*year
    return {'rain':rain,'temperature':temp,'runoff':runoff,'evap':evap,'recharge':np.maximum(rain-runoff-evap,0),'humidity':np.clip(get('hur'),0,1),'cloud':np.clip(get('clt'),0,1),'pressure':get('ps')*100*np.exp(-request['params']['gravity']*dz/(287.05*np.maximum(180,temp+273.15))),'wind-east':get('uas'),'wind-north':get('vas'),'snow':np.maximum(get('snd'),0)}

def provenance(folder):
    arrays,result,request=read_climate(str(pathlib.Path(folder).resolve()))
    return {'model':'ExoPlaSim','climateSha256':result['climateSha256'],'requestFingerprint':request['fingerprint'],'downscaling':'Bilinear Gaussian-grid fields; temperature lapse and hydrostatic pressure corrections only. No painted precipitation. Runoff includes the parent model snow/hydrology response.','sourceResolution':request['params']['resolution']}
