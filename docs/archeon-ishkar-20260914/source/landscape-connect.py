"""Final small drainage connections on the retained v14 terrain.

No new tectonic sources or large erosion campaign. A physical longitudinal
grade removes residual flat river beds; seasonal water routing is then free.
"""
import pathlib,sys,importlib,json,time,hashlib,argparse,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));L=importlib.import_module('tectonics-landscape');T=L.T;H=L.H;S=L.STORY;np=L.np
from numba import njit
from scipy.ndimage import distance_transform_edt,gaussian_filter

@njit(cache=False)
def longitudinal_grade(z,order,receiver,active,dx,width,grade):
 result=z.copy();support=active.copy()
 for k in range(len(order)-1,-1,-1):
  i=order[k];j=receiver[i]
  if support[i] and j>=0:support[j]=True
 for i in order:
  if not support[i]:continue
  j=receiver[i]
  if j<0:result[i]=max(.01,result[i]);continue
  r=i//width;c=i%width;rr=j//width;cc=j%width;ds=dx*np.sqrt((r-rr)**2+(c-cc)**2)
  result[i]=max(result[i],result[j]+grade*ds)
 return result,support

@njit(cache=False)
def reaches_gate(order,receiver,gate):
 reached=gate.copy()
 for i in order:
  j=receiver[i]
  if j>=0 and reached[j]:reached[i]=True
 return reached

def ishkar_outlet(g,topo):
 r,c=S.location(g,[-9.675078934,8.838133707]);i=round(r)*g['width']+round(c)
 for _ in range(g['width']*g['height']):
  j=int(topo['bed-receiver'][i])
  if j<0 or j==i:return i
  i=j
 raise RuntimeError('Cyclic Ishkar outlet trace')

def ishkar_support(g,topo,receiver=None):
 outlet=ishkar_outlet(g,topo);gate=np.zeros(g['width']*g['height'],bool);gate[outlet]=True
 return reaches_gate(topo['order'],topo['bed-receiver'] if receiver is None else receiver.ravel(),gate).reshape((g['height'],g['width'])),outlet

def prepare(seed,step=2000):
 out=L.WORK/'connection-base'/str(seed);out.mkdir(parents=True,exist_ok=True)
 source=L.WORK/'base/aethelgard'/str(seed);pg=L.read(source/'grid.json');g=L.grid_region('aethelgard',step);g['seed']=seed;g['id']='aethelgard-ishkar'
 key={'source':T.sha(source/'height.npy'),'gridM':step,'code':T.sha(pathlib.Path(__file__)),'storyCode':T.sha(pathlib.Path(S.__file__))}
 if (out/'input.json').exists() and L.read(out/'input.json')==key and (out/'height.npy').exists():return out
 old=T.sample(np.load(source/'height.npy'),pg,g).astype(float);kind=T.sample(np.load(source/'kind.npy'),pg,g,0);land=(kind>=30)&(kind!=80);focus=S.domain(g);tp=H.topology(old,land,step)
 corrected,support=longitudinal_grade(old.ravel(),tp['order'],tp['bed-receiver'],((focus>.35)|((old<0)&land)).ravel(),step,g['width'],.000025);corrected=corrected.reshape(old.shape)
 # The adjustments occupy existing drainage depressions and their downstream
 # links; the surrounding mesas, cliffs and interfluves are untouched.
 corrected[~land]=old[~land];delta=corrected-old
 tp2=H.topology(corrected,land,step);connected,outlet=ishkar_support(g,tp2)
 rows=[]
 for site in S.SITES:
  rr,cc=S.location(g,site['center']);r,c=round(rr),round(cc);near=T.distance(g,site['center'])<24000
  rows.append({'name':site['name'],'centerOnIshkarCatchment':bool(connected[r,c]),'nearbyIshkarCatchmentFraction':float(connected[near].mean()),'maxLocalChangeM':float(abs(delta[near]).max(initial=0))})
 for n,a in {'height':corrected,'before':old,'kind':kind,'connection-change':delta,'story-constraints':focus,'ishkar-catchment':connected,'soil':T.sample(np.load(source/'soil.npy'),pg,g)}.items():np.save(out/(n+'.npy'),a.astype('float32') if n not in ['kind','ishkar-catchment'] else a)
 L.save(out/'grid.json',g);L.save(out/'input.json',key);L.save(out/'connection.json',{'scope':'minor longitudinal-grade completion of retained river valleys; no additional tectonic generation','minimumGradeMperKm':.025,'maximumRaiseM':float(delta.max()),'changedAreaKm2':float((delta>.01).sum()*step*step/1e6),'medianChangedRaiseM':float(np.median(delta[delta>.01])) if (delta>.01).any() else 0,'negativeLandCellsBefore':int(((old<0)&land).sum()),'negativeLandCellsAfter':int(((corrected<0)&land).sum()),'sites':rows,'IshkarReference':[-9.675078934,8.838133707],'IshkarOutletNode':int(outlet),'membership':'same computed marine outlet as the Riverbend Ishkar branch; routes need not pass through the settlement itself','newTectonicUpliftM3':0,'correctionVolumeM3':float(delta.sum()*step*step),'oldSource':str(source)})
 print('CONNECTION BASE',seed,step,json.dumps(rows,ensure_ascii=False),flush=True);return out

def water_case(seed,scenario,step=2000,cycles=80):
 source=prepare(seed,step);g=L.read(source/'grid.json');folder=L.WORK/'connected'/str(seed)/scenario;folder.mkdir(parents=True,exist_ok=True);key={'base':T.sha(source/'height.npy'),'scenario':scenario,'hydrology':T.sha(pathlib.Path(H.__file__)),'cycles':cycles,'gridM':step}
 if (folder/'request.json').exists() and L.read(folder/'request.json')==key and (folder/'hydrology.json').exists():return folder
 z=np.load(source/'height.npy').astype(float);kind=np.load(source/'kind.npy');land=(kind>=30)&(kind!=80);cl=L.proxy(z,g,kind);start=time.time();hyd=H.run(z,land,step,cl,L.CFG['rainScenarios'][scenario],cycles=5,converge=True,max_cycles=cycles)
 for name in ['discharge','receiver','lake-depth','lake-level','lake-occurrence','lake-min-depth','lake-max-depth','wetness','runoff']:np.save(folder/(name+'.npy'),hyd[name].astype('int32') if name=='receiver' else hyd[name].astype('float32'))
 tp=hyd['topology'];connected,outlet=ishkar_support(g,tp,hyd['receiver']);np.save(folder/'ishkar-catchment.npy',connected)
 story=S.check(g,z,hyd['lake-depth'],hyd['lake-occurrence'],hyd['lake-max-depth']);L.save(folder/'story-geography.json',story)
 # Restrict convergence diagnostics to the changed story area as well as
 # reporting the full continental result. Unchanged remote lakes may fill.
 local=(S.domain(g)>.35)&(hyd['lake-depth']>.05);b=tp['basin'].reshape(z.shape);ids=np.unique(b[local]);ids=ids[ids>=0]
 record={k:v for k,v in hyd.items() if k in ['lakes','history','convergence','maxWaterRelativeError','climateStatus','seasonality','initialStorageM3','releasedByBedChangeM3']};record.update({'elapsedSeconds':time.time()-start,'terrainFixedDuringSeasonalSolve':True,'geologicalYearsAdvanced':0,'sceneCheckPassed':story['passed'],'activeStoryBasins':ids.tolist()})
 L.save(folder/'hydrology.json',record);L.save(folder/'request.json',key);L.save(folder/'grid.json',g);print('CONNECTED WATER',seed,scenario,'seconds',round(time.time()-start,1),'story',story['passed'],'convergence',hyd['convergence'],flush=True);return folder

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,default=5210914);ap.add_argument('--scenario',choices=['all','dry','baseline','wet'],default='all');ap.add_argument('--grid-m',type=int,default=2000);ap.add_argument('--cycles',type=int,default=80);ap.add_argument('--prepare-only',action='store_true');a=ap.parse_args();L.setup()
 if a.prepare_only:prepare(a.seed,a.grid_m)
 else:
  for scenario in L.CFG['rainScenarios'] if a.scenario=='all' else [a.scenario]:water_case(a.seed,scenario,a.grid_m,a.cycles);gc.collect()
