"""Independent geological candidates and continuous continental water grids."""
import pathlib,sys,importlib,argparse,time,gc,copy
sys.path.insert(0,str(pathlib.Path(__file__).parent))
C=importlib.import_module('climate-terrain-common');M=importlib.import_module('climate-tile-structure')
L=importlib.import_module('tectonics-landscape');T=C.T;np=C.np
COAST=importlib.import_module('climate-coastal-highlands')
from scipy.ndimage import distance_transform_edt,maximum_filter,minimum_filter,gaussian_filter
BASE=T.BASE_WORK/'landscape-v13/base'

def configure():
 L.WORK=C.WORK;L.CFG=copy.deepcopy(L.CFG);L.CFG.update(version=C.CFG['version'],maximumSeasonalCycles=120)
 T.WORK=C.WORK;T.MASK=None
 # A feature-sized cache is useful in windows, but never cache 96 continents.
 L.feature_shape.cache_clear()

def grid(region,step):
 pg=C.read(BASE/region/'5210914/grid.json')
 return {**pg,'stepM':step,'width':round((pg['width']-1)*pg['stepM']/step)+1,'height':round((pg['height']-1)*pg['stepM']/step)+1,'region':region,'id':region}

def regional_allow(z,kind,g):
 land=(kind>=30)&(kind!=80);dx=g['stepM'];hard=L.cores(g,kind)
 gentle=(z<1400)&(np.hypot(*np.gradient(gaussian_filter(z,max(.5,8000/dx)),dx))<.025)&(maximum_filter(z,max(3,round(16000/dx)))-minimum_filter(z,max(3,round(16000/dx)))<120)
 protected=1-T.ease(distance_transform_edt(~hard)*dx/24000)
 quiet=1-T.ease(distance_transform_edt(~gentle)*dx/16000)
 allow=land*(1-protected)*(1-.97*quiet)*T.ease(distance_transform_edt(land)*dx/24000)*T.ease((z-200)/600)
 return allow.astype('float32'),hard,gentle

def input_fields(region,seed,g,gain):
 source=BASE/region/str(seed);pg=C.read(source/'grid.json')
 z=T.sample(np.load(source/'height.npy',mmap_mode='r'),pg,g).astype(float)
 kind=T.sample(np.load(source/'kind.npy',mmap_mode='r'),pg,g,0).astype('uint8')
 soil=T.sample(np.load(source/'soil.npy',mmap_mode='r'),pg,g).astype(float)
 inherited=z.copy();z,removed,replaced,coast_record=COAST.correct(z,kind,g,region,seed,L.cores(g,kind))
 allow,hard,quiet=regional_allow(z,kind,g)
 prior,tiles=M.field(g,region,seed,gain,allow)
 features=L.catalog(region,seed,gain)
 for feature in features:feature['xy']=list(T.Proj(g['projection'])(*feature['center']))
 # Additional events follow the existing provinces. Flood-basalt construction
 # and caldera subsidence remain different entries in the geological ledger.
 for province in C.CFG['provinces']:
  if province['region']!=region:continue
  x,y=T.Proj(g['projection'])(*province['center']);scale=.5 if region=='keld' else 1
  features.append({'id':province['id']+'-basalt','province':province['id'],'family':'bench','process':'basalt-emplacement','xy':[x,y],'center':province['center'],'lengthM':125000*scale,'widthM':58000*scale,'reliefM':280*gain,'angleRadians':np.deg2rad(province['angleDegrees']),'phase':.7,'startYear':80000,'durationYears':600000,'initialFraction':.35})
  if province['family'] in ['basin','volcanic']:
   features.append({'id':province['id']+'-collapse','province':province['id'],'family':'basin','process':'caldera-collapse','xy':[x+18000*scale,y-8000*scale],'center':province['center'],'lengthM':48000*scale,'widthM':33000*scale,'reliefM':220*gain,'angleRadians':np.deg2rad(province['angleDegrees'])+.2,'phase':1.5,'startYear':350000,'durationYears':100000,'initialFraction':.1})
 construction,resolved=L.form(g,features,allow)
 return z+prior+construction,kind,soil,allow,hard,quiet,features,{'inherited':inherited,'base-repair':z-inherited,'removed-source':removed,'replacement-source':replaced,'coastalRepair':coast_record,'tile':prior,'construction':construction,'tiles':tiles,'resolved':resolved,'source':str(source),'sourceHeightSha256':C.sha(source/'height.npy')}

def prepare(region,seed,step=2000,gain=1):
 configure();g=grid(region,step);g['seed']=seed;folder=C.WORK/'continental'/region/str(seed)/f'g{gain:g}'
 key={'source':C.sha(BASE/region/str(seed)/'height.npy'),'grid':g,'gain':gain,'code':C.sources(),'tiles':C.sha(C.WORK/'tile-library/manifest.json')}
 if (folder/'request.json').exists() and C.read(folder/'request.json')==key and (folder/'height.npy').exists():return folder
 print('TERRAIN START',region,seed,step,'cells',g['width']*g['height'],flush=True);start=time.time()
 z,kind,soil,allow,hard,quiet,features,record=input_fields(region,seed,g,gain)
 for name,value in {'height':z,'kind':kind,'soil':soil,'allow':allow,'protected':hard,'quiet':quiet,'inherited':record['inherited'],'tile-construction':record['tile'],'event-construction':record['construction']}.items():C.save_array(folder/(name+'.npy'),value.astype('uint8') if name in ['kind','protected','quiet'] else value.astype('float32'))
 C.write(folder/'grid.json',g);C.write(folder/'sources.json',features);C.write(folder/'tile-placements.json',record['tiles'])
 for name in ['base-repair','removed-source','replacement-source']:C.save_array(folder/(name+'.npy'),record[name].astype('float32'))
 C.write(folder/'coastal-repair.json',record['coastalRepair'])
 report={'version':C.CFG['version'],'source':record['source'],'sourceHeightSha256':record['sourceHeightSha256'],'cells':z.size,'gridM':step,'newErosionYears':0,'status':'constructed candidate; erosion and climate pending','tileReliefVolumeM3':float(record['tile'].sum()*step**2),'eventConstructionVolumeM3':float(record['construction'].sum()*step**2),'protectedMaximumChangeM':float(abs(z-record['inherited'])[hard].max(initial=0)),'elapsedSeconds':time.time()-start,'oldTectonicsReapplied':False}
 C.write(folder/'construction.json',report);C.write(folder/'request.json',key);print('TERRAIN READY',region,seed,round(report['elapsedSeconds'],1),flush=True);return folder

def regional(spec,seed,mode,scenario,gain=1,detail=False,end=2000000,step_override=None):
 configure();region=spec['region'];step=step_override or (250 if detail else 2000);width=64 if detail else (256 if region=='keld' else 768)
 g=L.grid_window(spec,step,width);g['seed']=seed
 folder=C.WORK/('detail' if detail else 'regional')/spec['id']/str(seed)/mode/scenario/f'g{gain:g}'/str(step)
 z,kind,soil,allow,hard,quiet,features,record=input_fields(region,seed,g,gain)
 parent_name='vorhan-duskreach' if region in ['vorhan','duskreach'] else region
 coarse_parent=C.WORK/'coarse'/parent_name/str(seed)/mode/scenario/f'g{gain:g}'
 if not (coarse_parent/'simulation.json').exists():raise RuntimeError('Completed continuous parent required: '+str(coarse_parent))
 parent=(coarse_parent,C.read(coarse_parent/'grid.json'))
 if detail:
  p=C.WORK/'regional'/spec['id']/str(seed)/mode/scenario/f'g{gain:g}'/'2000';pg=C.read(p/'grid.json')
  parent=(p,pg)
 C.save_array(folder/'tile-construction.npy',record['tile']);C.save_array(folder/'event-construction.npy',record['construction']);C.save_array(folder/'inherited.npy',record['inherited']);C.write(folder/'tile-placements.json',record['tiles'])
 C.save_array(folder/'base-repair.npy',record['base-repair']);C.write(folder/'coastal-repair.json',record['coastalRepair'])
 start=time.time();result=L.solve(folder,g,z,kind,hard,allow,soil,features,mode,scenario,gain,parent=parent,end=end,dt=2500 if step<250 else 5000,cap=340 if region=='vorhan' else 260)
 result['climateStatus']='historical effective erosion scenario; not present-day GCM';result['wallSeconds']=time.time()-start;C.write(folder/'simulation.json',result);L.feature_shape.cache_clear();gc.collect();return folder

def water(region,seed,scenario,gain=1,cycles=120):
 configure();base=prepare(region,seed,2000,gain);g=C.read(base/'grid.json');out=base/'water'/scenario
 key={'terrain':C.sha(base/'height.npy'),'scenario':scenario,'waterCode':C.sha(L.H.__file__),'maximumCycles':cycles}
 if (out/'request.json').exists() and C.read(out/'request.json')==key and (out/'hydrology.json').exists():return out
 z=np.load(base/'height.npy').astype(float);kind=np.load(base/'kind.npy');start=time.time();hyd=L.H.run(z,(kind>=30)&(kind!=80),2000,L.proxy(z,g,kind),L.CFG['rainScenarios'][scenario],cycles=5,converge=True,max_cycles=cycles)
 for n in ['discharge','receiver','lake-depth','lake-level','lake-occurrence','lake-min-depth','lake-max-depth','wetness','runoff']:C.save_array(out/(n+'.npy'),hyd[n].astype('int32') if n=='receiver' else hyd[n].astype('float32'))
 C.write(out/'grid.json',g);C.write(out/'hydrology.json',{**{n:hyd[n] for n in ['lakes','history','convergence','maxWaterRelativeError','climateStatus','seasonality']},'wallSeconds':time.time()-start,'climateValidated':False,'terrainErosionPending':True,'independentContinentalSolve':region!='keld','jointBridgeValidationPending':region in ['vorhan','duskreach']});C.write(out/'request.json',key)
 print('CONTINENTAL WATER',region,seed,scenario,round(time.time()-start,1),hyd['convergence'],flush=True);return out

def joint_grid(step=16000):
 proj=T.Proj(proj='laea',lat_0=0,lon_0=105,R=C.CFG['climate']['radiusM']);points=[]
 for f in T.D['land']:
  if f['id'] not in ['Vorhan','Duskreach','vorhan-duskreach-bridge']:continue
  def walk(v):
   if isinstance(v[0],(float,int)):points.append(proj(*v))
   else:
    for a in v:walk(a)
  walk(f['geometry']['coordinates'])
 p=np.asarray(points);lo=np.floor(p.min(axis=0)/step)*step-step*4;hi=np.ceil(p.max(axis=0)/step)*step+step*4
 return {'id':'vorhan-duskreach','region':'vorhan-duskreach','projection':proj.srs,'stepM':step,'xmin':float(lo[0]),'ymax':float(hi[1]),'width':int(round((hi[0]-lo[0])/step))+1,'height':int(round((hi[1]-lo[1])/step))+1}

def coarse(region,seed,mode,scenario,gain=1,end=2000000):
 configure();joint=region in ['vorhan','duskreach','vorhan-duskreach'];name='vorhan-duskreach' if joint else region
 g=joint_grid() if joint else grid(region,16000);g['seed']=seed;folder=C.WORK/'coarse'/name/str(seed)/mode/scenario/f'g{gain:g}'
 if joint:
  a=input_fields('vorhan',seed,g,gain);b=input_fields('duskreach',seed,g,gain)
  ma=T.raster([f['geometry'] for f in T.D['land'] if f['id']=='Vorhan'],g);mb=T.raster([f['geometry'] for f in T.D['land'] if f['id'] in ['Duskreach','vorhan-duskreach-bridge']],g)
  da=distance_transform_edt(~ma)*g['stepM'];db=distance_transform_edt(~mb)*g['stepM'];wa=np.exp(-da/32000);wb=np.exp(-db/32000);w=wa/(wa+wb+1e-30);land=ma|mb
  z=a[0]*w+b[0]*(1-w);kind=np.where(land,70,0).astype('uint8');z[~land]=-distance_transform_edt(~land)[~land]*16000*.01
  soil=a[2]*w+b[2]*(1-w);allow,hard,quiet=regional_allow(z,kind,g);features=a[6]+b[6]
  C.write(folder/'bridge.json',{'sharedGrid':True,'regions':['vorhan','duskreach','vorhan-duskreach-bridge'],'joiningWidthM':32000,'routing':'one continuous priority-flood network; no independently assigned bridge outlets'})
 else:z,kind,soil,allow,hard,quiet,features,_=input_fields(region,seed,g,gain)
 print('COARSE PARENT',name,seed,mode,scenario,'cells',z.size,flush=True)
 return L.solve(folder,g,z,kind,hard,allow,soil,features,mode,scenario,gain,end=end,dt=5000,cap=300)

def main():
 a=argparse.ArgumentParser();a.add_argument('--stage',choices=['prepare','coarse','regional','detail','water'],default='prepare');a.add_argument('--region',default='all');a.add_argument('--seed',type=int);a.add_argument('--mode',default='erosion-only');a.add_argument('--scenario',default='baseline');a.add_argument('--gain',type=float,default=1);a.add_argument('--end',type=int,default=2000000);a.add_argument('--step',type=int);q=a.parse_args()
 for seed in [q.seed] if q.seed else C.CFG['seeds']:
  for r in C.CFG['regions'] if q.region=='all' else [q.region]:
   if q.stage=='prepare':prepare(r,seed,q.step or 2000,q.gain)
   elif q.stage=='coarse':coarse(r,seed,q.mode,q.scenario,q.gain,q.end)
   elif q.stage=='water':water(r,seed,q.scenario,q.gain)
   else:
    for spec in C.CFG['provinces']:
     if spec['region']==r:regional(spec,seed,q.mode,q.scenario,q.gain,q.stage=='detail',q.end,q.step)
   gc.collect()
if __name__=='__main__':main()
