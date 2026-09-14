"""Export only complete track-model snapshots, with explicit acceptance state."""
import pathlib,sys,importlib,time,shutil
sys.path.insert(0,str(pathlib.Path(__file__).parent));P=importlib.import_module('climate-plume-tracks');C=P.C;T=P.T;np=P.np
V=importlib.import_module('landscape-export');E=importlib.import_module('tectonics-export');OUT=C.ROOT/'foundation/plume-tracks-v16'
def run():
 OUT.mkdir(parents=True,exist_ok=True);E.OUT=OUT;items=[]
 for path in sorted((C.WORK/'coarse').glob('**/simulation.json')):
  folder=path.parent
  if not V.complete(folder):continue
  r=C.read(path);g=C.read(folder/'grid.json');name=folder.relative_to(C.WORK).as_posix().replace('/','-');fingerprint=C.fingerprint({'request':C.sha(folder/'request.json'),'height':C.sha(folder/'height.npy'),'exporter':C.sha(__file__)})
  cache=OUT/(name+'.json')
  if cache.exists() and C.read(cache).get('fingerprint')==fingerprint:items.append(C.read(cache));continue
  z=np.load(folder/'height.npy');initial=np.load(folder/'initial.npy');kind=np.load(folder/'kind-0.npy');depth=np.load(folder/'lake-depth.npy');q=np.load(folder/'discharge.npy');rec=np.load(folder/'receiver.npy');stages=[]
  for year in [0,10000,100000,500000,2000000]:
   f=folder/f'height-{year}.npy'
   if not f.exists() or year>r['effectiveYears']:continue
   height=np.load(f);image=name+'-'+str(year)+'.png';E.write_image(image,E.elevation(height),kind);stages.append({'effectiveYears':year,'height':image})
  features=V.lines(g,q,np.where(depth>.05,-1,rec))
  for f in features:f['properties'].pop('screen',None)
  metadata={'candidateOnly':True,'climateValidated':False,'seasonalWaterConverged':r['waterConvergence']['passed'],'sourceHeightSha256':C.sha(folder/'height.npy')}
  C.write(OUT/(name+'-rivers.geojson'),{'type':'FeatureCollection','properties':metadata,'features':features});lakes=V.lakes(g,z,depth,np.load(folder/'lake-occurrence.npy'))
  for f in lakes:
   if not r['waterConvergence']['passed']:f['properties']['state']='unconverged-candidate'
  C.write(OUT/(name+'-lakes.geojson'),{'type':'FeatureCollection','properties':metadata,'features':lakes})
  item={'id':name,'fingerprint':fingerprint,'grid':g,'stages':stages,'riverVector':name+'-rivers.geojson','lakeVector':name+'-lakes.geojson','numericalConservationPassed':r['passed'],'waterConverged':r['waterConvergence']['passed'],'maximumWaterRelativeError':r['maxWaterRelativeError'],'maximumSolidRelativeError':r['maxVolumeRelativeError'],'maximumErosionM':float(np.load(folder/'erosion.npy').max()),'effectiveYears':r['effectiveYears'],'globalClimateReady':False,'terrainAccepted':False};C.write(cache,item);items.append(item)
 C.write(OUT/'manifest.json',{'version':'plume-tracks-v16','updatedUnix':time.time(),'state':'WIP','candidates':items,'construction':'prescribed finite source history, Airy support and elastic basalt-load subsidence','priorErosionSimulated':False,'surfaceAndVegetation':'WIP','globalClimate':'WIP','routes':'WIP'})
 print('TRACK BAKES',len(items),flush=True)
if __name__=='__main__':run()
