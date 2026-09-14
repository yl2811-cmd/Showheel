"""Bake completed plume comparisons; every lake retains its convergence flag."""
import pathlib,sys,importlib,time,shutil
sys.path.insert(0,str(pathlib.Path(__file__).parent));P=importlib.import_module('climate-vorhan-plumes');C=P.C;T=P.T;np=P.np
V=importlib.import_module('landscape-export');E=importlib.import_module('tectonics-export')
OUT=C.ROOT/'foundation/vorhan-plumes-v15'

def run():
 OUT.mkdir(parents=True,exist_ok=True);E.OUT=OUT;items=[]
 for path in sorted(C.WORK.glob('**/simulation.json')):
  folder=path.parent
  if not V.complete(folder):continue
  g=C.read(folder/'grid.json');r=C.read(path);request=C.read(folder/'request.json');prefix=folder.relative_to(C.WORK).as_posix().replace('/','-')
  key=C.fingerprint({'height':C.sha(folder/'height.npy'),'simulation':C.sha(path),'exporter':C.sha(__file__)})
  cache=OUT/(prefix+'.json')
  if cache.exists() and C.read(cache).get('fingerprint')==key:items.append(C.read(cache));continue
  z=np.load(folder/'height.npy');initial=np.load(folder/'initial.npy');kind=np.load(folder/'kind-0.npy');depth=np.load(folder/'lake-depth.npy');q=np.load(folder/'discharge.npy');rec=np.load(folder/'receiver.npy')
  for label,value in [('initial',initial),('height',z)]:E.write_image(prefix+'-'+label+'.png',E.elevation(value),kind)
  E.write_image(prefix+'-erosion.png',E.signed(-np.load(folder/'erosion.npy'),100),kind)
  E.write_image(prefix+'-lake-depth.png',E.plt.get_cmap('Blues')(np.clip(np.log1p(depth)/np.log(1001),0,1))[:,:,:3]*255,kind)
  vectors=V.lines(g,q,np.where(depth>.05,-1,rec),threshold=1e9)
  for f in vectors:f['properties'].pop('screen',None)
  shared={'candidateOnly':True,'climateValidated':False,'seasonalWaterConverged':r['waterConvergence']['passed'],'effectiveYears':r['effectiveYears'],'sourceHeightSha256':C.sha(folder/'height.npy')}
  C.write(OUT/(prefix+'-rivers.geojson'),{'type':'FeatureCollection','properties':shared,'features':vectors})
  lakes=V.lakes(g,z,depth,np.load(folder/'lake-occurrence.npy'))
  for f in lakes:f['properties']['state']='unconverged-candidate' if not r['waterConvergence']['passed'] else f['properties']['state']
  C.write(OUT/(prefix+'-lakes.geojson'),{'type':'FeatureCollection','properties':shared,'features':lakes})
  item={'id':prefix,'fingerprint':key,'grid':g,'height':prefix+'-height.png','initial':prefix+'-initial.png','erosion':prefix+'-erosion.png','lakeDepth':prefix+'-lake-depth.png','rivers':prefix+'-rivers.geojson','lakes':prefix+'-lakes.geojson','effectiveYears':r['effectiveYears'],'gridM':g['stepM'],'numericalConservationPassed':r['passed'],'waterConverged':r['waterConvergence']['passed'],'terrainAccepted':False,'climateValidated':False,'protectedMaximumChangeM':r['protectedMaxDeltaM'],'maximumErosionM':float(np.load(folder/'erosion.npy').max()),'source':str(folder)}
  C.write(cache,item);items.append(item)
 for source in [C.WORK/'siting-audit.json',C.WORK/'impact.json',C.WORK/'long-impact.json']:
  if source.exists():shutil.copyfile(source,OUT/source.name)
 for source in [C.WORK/'siting-preview.png',C.TASK/'coastal-diagnosis/repair-preview.png',C.TASK/'climate-diagnostics/circulation-control-year4.png',C.TASK/'climate-diagnostics/circulation-control-year4.json']:
  if source.exists():shutil.copyfile(source,OUT/source.name)
 C.write(OUT/'manifest.json',{'version':'vorhan-inland-plumes-v15','createdUnix':time.time(),'status':'WIP','candidates':items,'climate':'ExoPlaSim transient control exists; validated global climate remains WIP','vegetation':'WIP','routes':'WIP','notes':['Source geometry and erosion outputs are separate.','Unconverged lake extents are comparison data, not adopted story geography.','The four coarse controls include the shared Vorhan-Duskreach bridge.']})
 print('PLUME BAKES',len(items),flush=True)

if __name__=='__main__':run()
