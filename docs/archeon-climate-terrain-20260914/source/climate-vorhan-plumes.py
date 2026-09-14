"""Four independent inland plume-response hypotheses and their river impacts.

Parameterized crustal response, flood-basalt emplacement and normal-fault
activity; not a resolved mantle-convection calculation. Erosion is solved.
The screenshot marks sectors, never height, rainfall or protection masks.
"""
import pathlib,sys,importlib,argparse,shutil,time,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent))
C=importlib.import_module('climate-terrain-common');TASK=C.TASK
C.WORK=TASK/'vorhan-plume-study'
D=importlib.import_module('climate-terrain');T=C.T;np=C.np;L=D.L
from scipy.ndimage import distance_transform_edt,label,maximum_filter,minimum_filter
CASES={'control':[],'west':['west'],'east':['east'],'both':['west','east']}

def setup():
 C.WORK.mkdir(parents=True,exist_ok=True)
 library=C.WORK/'tile-library';library.mkdir(exist_ok=True)
 for f in (TASK/'tile-library').glob('*'):
  if f.is_file() and (not (library/f.name).exists() or C.sha(library/f.name)!=C.sha(f)):shutil.copyfile(f,library/f.name)
 D.configure()

def siting():return C.read(C.ROOT/'data/vorhan-plume-candidates.json')['sources']

def displacement(g,seed,case,gain=1):
 xx,yy=T.mesh(g);shape=xx.shape;fields={k:np.zeros(shape) for k in ['crustal-uplift','basalt-emplacement','fault-displacement']};features=[];sources=[]
 for index,s in enumerate(siting()):
  side=s['id'].split('-')[-1]
  if side not in CASES[case]:continue
  rng=np.random.default_rng(seed+3179+index*97);cx,cy=T.Proj(g['projection'])(*s['center']);angle=np.deg2rad((48 if side=='west' else 63)+rng.uniform(-6,6));length=460000 if side=='west' else 420000;width=260000 if side=='west' else 240000
  u=(xx-cx)*np.cos(angle)+(yy-cy)*np.sin(angle);v=-(xx-cx)*np.sin(angle)+(yy-cy)*np.cos(angle);bend=24000*np.sin(u/115000+.7)+10000*np.sin(u/46000);v-=bend
  r=(u/length)**2+(v/width)**2;support=1-T.ease((r-.10)/.90)
  swell=(820 if side=='west' else 700)*gain*support*(.9+.1*u/length)
  # Overlapping fissure-fed sheets have common bedding and offset margins.
  sheet=np.zeros(shape)
  for offset,relative in [(-.26,.72),(.23,1.)]:
   radius=(u/(length*.84))**2+((v-offset*width)/(width*.80))**2
   footprint=(1-T.ease((radius-.22)/.78))
   sheet=np.maximum(sheet,(850 if side=='west' else 1050)*gain*relative*footprint)
  block=np.zeros(shape)
  for k,offset in enumerate([-.43,.05,.48]):
   fault=offset*width+17000*np.sin(u/140000+k);cross=v-fault
   terrace=(.5+.5*np.tanh(cross/14000))*np.exp(-np.maximum(cross,0)/(width*.44))
   slip=(1050 if side=='west' else 1250)*gain*(.8+.2*np.sin(u/170000+k)**2)*support*terrace
   block=np.maximum(block,slip)
  # One geological history, with a mostly emplaced cap at erosion time zero.
  fields['crustal-uplift']+=swell;fields['basalt-emplacement']+=sheet;fields['fault-displacement']+=block
  for k,offset in enumerate([-.43,.05,.48]):
   fx=cx-np.sin(angle)*offset*width;fy=cy+np.cos(angle)*offset*width
   features.append({'id':s['id']+'-fault-'+str(k),'province':s['id'],'family':'tilted','process':'late-normal-fault-tilting','xy':[fx,fy],'center':list(T.Proj(g['projection'])(fx,fy,inverse=True)),'lengthM':length*.78,'widthM':width*.21,'reliefM':360*gain,'angleRadians':angle,'phase':float(k),'startYear':150000+k*210000,'durationYears':450000,'initialFraction':0.,'scale':'large'})
  sources.append({**s,'angleDegrees':float(np.rad2deg(angle)),'lengthKm':2*length/1000,'widthKm':2*width/1000,'effectiveFormationDurationYears':6000000,'dynamicSupportM':820 if side=='west' else 700,'basaltThicknessM':850 if side=='west' else 1050,'faultReliefM':1050 if side=='west' else 1250,'gain':gain,'model':'prescribed crustal response to two mantle upwelling hypotheses; basalt and later normal-fault motion separated; no mantle fluid solver'})
 return fields,features,sources

def initial(g,seed,case,gain=1):
 a=D.input_fields('vorhan',seed,g,1);b=D.input_fields('duskreach',seed,g,1)
 ma=T.raster([f['geometry'] for f in T.D['land'] if f['id']=='Vorhan'],g);mb=T.raster([f['geometry'] for f in T.D['land'] if f['id'] in ['Duskreach','vorhan-duskreach-bridge']],g);land=ma|mb
 da=distance_transform_edt(~ma)*g['stepM'];db=distance_transform_edt(~mb)*g['stepM'];wa=np.exp(-da/32000);wb=np.exp(-db/32000);w=wa/(wa+wb+1e-30)
 z=a[0]*w+b[0]*(1-w);kind=np.where(land,70,0).astype('uint8');z[~land]=-distance_transform_edt(~land)[~land]*g['stepM']*.01
 soil=a[2]*w+b[2]*(1-w);allow,hard,quiet=D.regional_allow(z,kind,g)
 fields,late,sources=displacement(g,seed,case,gain);extra=sum(fields.values());free=land.astype(float)
 for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
  if f['geometry']['type']=='Point':free*=T.ease((T.distance(g,f['geometry']['coordinates'])-20000)/80000)
 free[hard]=0
 offshore=float(extra[~land].sum()/max(extra.sum(),1));fields={k:v*free for k,v in fields.items()};extra=sum(fields.values());z+=extra
 # Source domains intentionally transform selected lowlands; quiet plains
 # elsewhere retain the earlier constraint. No coast-distance shaping.
 allow=np.maximum(allow,T.ease(extra/120)*free)
 return z,kind,soil,allow,hard,a[6]+b[6]+late,fields,sources,offshore

def run(case,seed=5210914,scenario='baseline',mode='erosion-only',end=100000,gain=1):
 setup();g=D.joint_grid(16000);g['seed']=seed;g['region']='vorhan-duskreach';folder=C.WORK/('long-coarse' if end>100000 else 'coarse')/case/str(seed)/mode/scenario/f'g{gain:g}'
 z,kind,soil,allow,hard,features,fields,sources,offshore=initial(g,seed,case,gain)
 if offshore>.01:raise ValueError('Plume support reaches marine boundary; choose a different source, do not mask it')
 for k,v in fields.items():C.save_array(folder/(k+'.npy'),v.astype('float32'))
 C.write(folder/'plumes.json',{'sources':sources,'case':case,'offshoreSourceFraction':offshore,'sourceCodeSha256':C.sha(__file__),'coastalRepairCodeSha256':C.sha(D.COAST.__file__),'phase':'new emplacement at time zero; later activity only in episodic control','volumeM3':{k:float(v.sum()*g['stepM']**2) for k,v in fields.items()},'climateValidated':False})
 start=time.time();report=L.solve(folder,g,z,kind,hard,allow,soil,features,mode,scenario,gain,end=end,dt=10000,cap=420)
 C.write(folder/'runtime.json',{'seconds':time.time()-start});print('PLUME COMPLETE',case,seed,end,report['passed'],flush=True);return folder

def route_outlets(rec):
 # Receivers are acyclic. Resolve terminal labels with pointer doubling.
 nxt=rec.ravel().astype('int64').copy();ids=np.arange(nxt.size);nxt=np.where(nxt<0,ids,nxt)
 for _ in range(40):
  new=nxt[nxt]
  if np.array_equal(new,nxt):break
  nxt=new
 else:raise ValueError('Receiver graph did not reach terminal outlets')
 return nxt.reshape(rec.shape)

def impacts(seed=5210914,mode='erosion-only',scenario='baseline',end=100000):
 root=C.WORK/('long-coarse' if end>100000 else 'coarse');base=root/'control'/str(seed)/mode/scenario/'g1'
 if not (base/'simulation.json').exists():return
 g=C.read(base/'grid.json');z0=np.load(base/'height.npy');land=np.load(base/'kind-0.npy')>=30;d0=np.load(base/'lake-depth.npy');out0=route_outlets(np.load(base/'receiver.npy'));area=g['stepM']**2/1e6;rows=[]
 vorhan=T.raster([f['geometry'] for f in T.D['land'] if f['id']=='Vorhan'],g)
 for case in CASES:
  f=root/case/str(seed)/mode/scenario/'g1'
  if not (f/'simulation.json').exists():continue
  z=np.load(f/'height.npy');depth=np.load(f/'lake-depth.npy');report=C.read(f/'simulation.json');out=route_outlets(np.load(f/'receiver.npy'));lift=np.load(f/'crustal-uplift.npy')+np.load(f/'basalt-emplacement.npy')+np.load(f/'fault-displacement.npy');affected=(lift>100)&vorhan
  shifted=vorhan&(out!=out0);high=vorhan&(z>3000);slope=np.hypot(*np.gradient(z,g['stepM']));table=high&(slope<.04);labs,n=label(table);sizes=np.bincount(labs.ravel())*area
  rows.append({'case':case,'effectiveYears':report['effectiveYears'],'passed':report['passed'],'waterConverged':report['waterConvergence']['passed'],'affectedOver100mKm2':float(affected.sum()*area),'fractionOfVorhanAffected':float(affected.sum()/max(vorhan.sum(),1)),'maximumAddedInitialM':float(lift.max()),'meanAddedAffectedM':float(lift[affected].mean()) if affected.any() else 0.,'landAbove3000mKm2':float(high.sum()*area),'tabletopProxyKm2':float(table.sum()*area),'largestTabletopProxyKm2':float(sizes[1:].max(initial=0)),'outletChangedAreaKm2':float(shifted.sum()*area),'outletComparison':'exact coastal receiving grid cell; nearby-mouth changes also count, not all are basin capture','standingWaterAreaKm2':float((vorhan&(depth>.05)).sum()*area),'standingWaterVolumeKm3':float(depth[vorhan].sum()*area/1000),'standingWaterChangeKm3':float((depth-d0)[vorhan].sum()*area/1000),'erosionVolumeKm3':float(np.load(f/'erosion.npy')[vorhan].sum()*area/1000),'maximumErosionM':float(np.load(f/'erosion.npy')[vorhan].max()),'maximumSolidRelativeError':report['maxVolumeRelativeError'],'maximumWaterRelativeError':report['maxWaterRelativeError'],'protectedMaximumChangeM':report['protectedMaxDeltaM'],'climateEffect':'not computed; historical rain proxy only'})
 C.write(C.WORK/('long-impact.json' if end>100000 else 'impact.json'),{'seed':seed,'mode':mode,'scenario':scenario,'gridM':g['stepM'],'cases':rows,'notes':['Terrain and water sensitivity; no validated modern climate.','Tabletop proxy at 16km cannot resolve mesa islands or individual cliff steps.','Erosion volume includes background geology; use matched control differences.']});print('IMPACTS',len(rows),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',choices=[*CASES,'all'],default='all');p.add_argument('--seed',type=int,default=5210914);p.add_argument('--scenario',default='baseline');p.add_argument('--mode',default='erosion-only');p.add_argument('--end',type=int,default=100000);p.add_argument('--gain',type=float,default=1);q=p.parse_args()
 for case in CASES if q.case=='all' else [q.case]:run(case,q.seed,q.scenario,q.mode,q.end,q.gain);gc.collect()
 impacts(q.seed,q.mode,q.scenario,q.end)
