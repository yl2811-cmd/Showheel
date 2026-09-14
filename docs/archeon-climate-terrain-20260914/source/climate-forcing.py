"""Diagnostic terrain downscaling of validated circulation, never painted rain."""
import pathlib,sys,importlib
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');K=importlib.import_module('climate-contract');np=C.np
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import gaussian_filter

def redistribute(rain,weights,parent_index):
 ids=parent_index.ravel();n=int(ids.max())+1;p=np.maximum(0,rain);w=np.maximum(.01,weights)
 before=np.bincount(ids,weights=p.ravel(),minlength=n);after=np.bincount(ids,weights=(p*w).ravel(),minlength=n)
 factor=np.divide(before,after,out=np.ones_like(before),where=after>0);result=p*w*factor[ids].reshape(p.shape)
 residual=np.max(abs(np.bincount(ids,weights=result.ravel(),minlength=n)-before))/max(1,float(before.sum()))
 if residual>1e-8:raise ValueError('Downscaled precipitation budget mismatch')
 return result,float(residual)

class Forcing:
 def __init__(self,folder,g,height):
  self.request,self.result=K.validate(folder,require_ready=False);self.folder=pathlib.Path(folder);self.g=g;self.z=height
  self.calendar=K.TIME.calendar(self.result.get('calendar'));self.data=np.load(self.folder/'climate.npz',allow_pickle=False);self.bounds=self.data['time_bounds_seconds'];self.durations=K.TIME.interval_check(self.bounds,self.calendar)
  lat=self.data['latitude'];lon=self.data['longitude'];self.rows=np.argsort(lat);self.columns=np.argsort(lon%360);self.lat=lat[self.rows];lo=(lon%360)[self.columns];self.lon=np.r_[lo[-1]-360,lo,lo[0]+360]
  xx,yy=C.T.mesh(g);self.qlon,self.qlat=C.T.Proj(g['projection'])(xx,yy,inverse=True)
  self.locations=(np.clip(self.qlat,self.lat.min(),self.lat.max()),self.qlon%360)
  ilat=np.abs(self.qlat[...,None]-self.lat).argmin(axis=-1) if height.size<100000 else np.clip(np.searchsorted((self.lat[:-1]+self.lat[1:])/2,self.qlat),0,len(self.lat)-1)
  edges=(lo[:-1]+lo[1:])/2;ilon=np.searchsorted(edges,self.qlon%360)%len(lo);self.parent_index=ilat*len(lo)+ilon
  filtered=gaussian_filter(height,max(.5,8000/g['stepM']));self.north_gradient,self.east_gradient=np.gradient(filtered,g['stepM']);self.north_gradient*=-1
  self.budget=[];self.limitations=['Diagnostic subgrid rain redistribution, not a 2km atmospheric GCM.','Strong blocking and convective extremes require regional dynamical validation.']
 def sample(self,key,season):
  a=self.data[key][season][self.rows,:][:,self.columns];a=np.concatenate([a[:,-1:],a,a[:,:1]],axis=1)
  return RegularGridInterpolator((self.lat,self.lon),a,bounds_error=False,fill_value=None)(self.locations)
 def season(self,i):
  fields={k:self.sample(k,i) for k in K.SURFACE_UNITS};wind=np.hypot(fields['uas'],fields['vas'])
  ascent=self.east_gradient*fields['uas']+self.north_gradient*fields['vas']
  factor=np.exp(np.clip(ascent*900/1800,-1.5,1.5));p,error=redistribute(fields['pr'],factor,self.parent_index)
  snowfraction=np.divide(fields['prsn'],np.maximum(fields['pr'],1e-20));fields['pr']=p;fields['prsn']=p*np.clip(snowfraction,0,1)
  # Near-surface model winds use the declared measurement height for reference PET.
  height=self.result.get('windHeightM')
  if height is None or height<=.12:raise ValueError('A physical near-surface wind measurement height is required')
  wind2=wind*np.log(2/.01476)/np.log(height/.01476)
  net=fields['rss']+fields['rlds']-fields['rlus'];fields['pet']=K.pet(fields['tas'],fields['hur'],wind2,fields['ps'],net)
  self.budget.append({'season':i,'rainRedistributionRelativeError':error,'windSource':'resolved GCM near-surface wind; no prescribed trade-wind bands','condensationTimeS':900,'moistureDepthM':1800})
  return fields
