"""Local water-routing sensitivity on the SAME retained continental surface.

250/125/64m denote water solver sampling, not newly surveyed terrain detail.
All windows use the same physical extent, parent rainfall and boundary supply.
"""
import sys,pathlib,importlib,json,argparse,time,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('landscape-connect');L=C.L;T=L.T;np=L.np
WINDOWS=[{'id':'frontier','center':[0,26]},{'id':'thornfield','center':[12,25]},{'id':'orun-ishkar-junction','center':[-9.895,8.87]},{'id':'crestline','center':[.3,27]}]

def run(scenario,step=250,only=None):
 parent=L.WORK/'connected/5210914'/scenario;source=L.WORK/'connection-base/5210914';pg=L.read(source/'grid.json');z0=np.load(source/'height.npy');kind0=np.load(source/'kind.npy');depth0=np.load(parent/'lake-depth.npy');q=np.load(parent/'discharge.npy');rec=np.load(parent/'receiver.npy');cl=L.proxy(z0,pg,kind0)
 rows=[]
 for spec in WINDOWS:
  if only and only!=spec['id']:continue
  g=L.grid_window({**spec,'region':'aethelgard'},step,64);g['seed']=5210914;folder=L.WORK/'connection-detail'/spec['id']/scenario/str(step);folder.mkdir(parents=True,exist_ok=True);key={'parent':L.read(parent/'request.json'),'height':T.sha(source/'height.npy'),'grid':g,'code':T.sha(pathlib.Path(__file__))}
  if (folder/'request.json').exists() and L.read(folder/'request.json')==key and (folder/'result.json').exists():rows.append(L.read(folder/'result.json'));continue
  z=T.sample(z0,pg,g).astype(float);kind=T.sample(kind0,pg,g,0);dep=T.sample(depth0,pg,g);qw,qs,crossings=L.R.boundary_flux('aethelgard',g,pg,q,rec,np.zeros_like(q))
  # Locate inherited inflow at the same physical 1km inset at every grid.
  qw.fill(0);inset=round(1000/step)
  for row in crossings:
   r,c=row['childNode'];r=int(np.clip(r,inset,g['height']-1-inset));c=int(np.clip(c,inset,g['width']-1-inset));qw[r,c]+=row['waterM3yr'];row['childNode']=[r,c];row['physicalInsetM']=1000
  climate={k:T.sample(cl[k],pg,g) for k in ['rain','temperature']};start=time.time();hyd=L.H.run(z,kind>=30,step,climate,L.CFG['rainScenarios'][scenario],cycles=5,converge=True,max_cycles=40,external=qw,initial_depth=dep,latitude=spec['center'][1]);story=L.STORY.check(g,z,hyd['lake-depth'],hyd['lake-occurrence'],hyd['lake-max-depth'])
  for k,a in {'height':z,'kind':kind,'discharge':hyd['discharge'],'lake-depth':hyd['lake-depth'],'receiver':hyd['receiver'],'external-water':qw}.items():np.save(folder/(k+'.npy'),a.astype('int32') if k=='receiver' else a.astype('float32'))
  # A fixed 3km physical margin, identical across resolution comparisons.
  margin=round(3000/step);inside=np.s_[margin:-margin,margin:-margin];last=hyd['history'][-1]
  result={'id':spec['id'],'scenario':scenario,'gridM':step,'widthKm':64,'physicalBufferM':3000,'parentTerrainResolutionM':2000,'geologicalYearsAdvanced':0,'climate':'same sampled parent rain and temperature; annual-mean crossing inflow held fixed across seasonal tests','externalWaterM3yr':float(qw.sum()),'outflowM3yr':last['outletM3'],'storageM3':last['storageM3'],'maximumInteriorLakeDepthM':float(hyd['lake-depth'][inside].max()),'waterRelativeError':hyd['maxWaterRelativeError'],'convergence':hyd['convergence'],'storyScreen':story,'seconds':time.time()-start}
  L.save(folder/'grid.json',g);L.save(folder/'request.json',key);L.save(folder/'parent-crossings.json',crossings);L.save(folder/'result.json',result);rows.append(result);print('DETAIL WATER',spec['id'],scenario,step,'seconds',round(result['seconds'],1),'error',result['waterRelativeError'],flush=True);gc.collect()
 return rows
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--scenario',default='baseline');ap.add_argument('--grid-m',type=int,default=250);ap.add_argument('--only');a=ap.parse_args();run(a.scenario,a.grid_m,a.only)
