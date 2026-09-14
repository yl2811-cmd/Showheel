"""Replace two inherited coastal cap sources, not the coast or the whole DEM.

The removed displacement is reconstructed from the frozen v7 source geometry.
Later erosion is retained. Partition of later uplift is an explicit assumption.
New source support is a physical, bent structural footprint: coastline distance
is used for diagnostics only, never to draw the highland perimeter.
"""
import pathlib,sys,importlib,json,argparse,gc,copy
from functools import lru_cache
sys.path.insert(0,str(pathlib.Path(__file__).parent))
C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np
from scipy.ndimage import distance_transform_edt,gaussian_filter
ARCHIVE=T.BASE_WORK/'archives/strong-painted-v7-20260914'
FROZEN=ARCHIVE/'study'
BASE=T.BASE_WORK/'landscape-v13/base'
SPECS={
 'duskreach':{'oldCenter':[75,-26],'oldLengthKm':530,'oldWidthKm':350,'oldAngle':-20,'oldIndex':0,
  'center':[69.8,-31.5],'angle':-52,'lengthKm':400,'widthKm':210,'reliefM':3650},
 'vorhan':{'oldCenter':[112,34],'oldLengthKm':460,'oldWidthKm':340,'oldAngle':-20,'oldIndex':1,
  'center':[113,28.2],'angle':63,'lengthKm':340,'widthKm':190,'reliefM':3350}}

def axes(g,center,angle):
 xx,yy=T.mesh(g);x,y=T.Proj(g['projection'])(*center);theta=np.deg2rad(angle)
 return ((xx-x)*np.cos(theta)+(yy-y)*np.sin(theta))/1000,(-(xx-x)*np.sin(theta)+(yy-y)*np.cos(theta))/1000

@lru_cache(maxsize=6)
def removed_source(region,seed):
 spec=SPECS[region];root=FROZEN/region;folder=root/str(seed);g=C.read(root/'grid.json');rng=np.random.default_rng(seed)
 # Replay the original source RNG, including the preceding tilted-block draws.
 if spec['oldIndex']:
  rng.uniform(-8,8);rng.uniform(.88,1.12)
  for _ in range(3):rng.uniform(-3,3);rng.uniform(.38,.65);rng.uniform(.25,.40);rng.uniform(.75,1)
 theta=spec['oldAngle']+rng.uniform(-8,8);amplitude_rng=rng.uniform(.88,1.12)
 record=next(r for r in C.read(folder/'formation.json') if r['family']=='cap-plateau')
 config=C.read(ARCHIVE/'config/tectonics-config.json');expected=(3200 if region=='duskreach' else 2600)*amplitude_rng*config['largeLandforms']['regionalDisplacementScale']
 if abs(expected-record['displacementScaleM'])>1e-7:raise ValueError('Frozen source RNG no longer matches '+region)
 u,v=axes(g,spec['oldCenter'],theta);length=spec['oldLengthKm'];width=spec['oldWidthKm']
 cap=record['displacementScaleM']*T.ease(1-(u/length)**2)*T.ease(1-(v/width)**2)*(.5+.5*np.tanh((v+width*.32)/14))*(.6+.4*np.clip((width-v)/(width*1.1),0,1))
 cap*=np.load(root/'allow.npy')
 if region=='vorhan':cap*=1-.95*np.load(root/'rift-floor-weight.npy')
 # Source contribution in nearshore cells uses the original recorded limiter.
 kind=np.load(root/'kind.npy');shore=np.load(folder/'shore-allow.npy')>0
 strength=C.read(folder/'shoreline.json')['coastalSlipFraction'];dl=distance_transform_edt(kind>=30)*g['stepM']
 limit=np.where(kind>=30,strength+(1-strength)*T.ease(dl/config['shoreline']['maxDisplacementM']),strength)
 cap[shore]*=limit[shore]
 total=np.load(folder/'tectonic-construction.npy');later=np.load(folder/'tectonic-uplift.npy')
 share=np.clip(cap/np.maximum(total,1),0,1);later_share=np.maximum(later,0)*share
 removal=cap+later_share
 return g,removal,{'source':record,'sourceRotationDegrees':theta,'initialSourceM3':float(cap.sum()*g['stepM']**2),
  'laterUpliftPartitionM3':float(later_share.sum()*g['stepM']**2),'laterPartitionAssumption':'proportional share of positive frozen tectonic uplift; not a reverse erosion solve',
  'sourceHashes':{str(p.relative_to(ARCHIVE)):C.sha(p) for p in [folder/'formation.json',folder/'tectonic-construction.npy',folder/'tectonic-uplift.npy',root/'allow.npy']}}

def new_sources(region,seed,g):
 spec=SPECS[region];rng=np.random.default_rng(seed+715);angle=spec['angle']+rng.uniform(-4,4)
 u,v=axes(g,spec['center'],angle);L=spec['lengthKm'];W=spec['widthKm'];phase=rng.uniform(-2,2)
 # Flexed structural axis and staggered cap lobes; no land/shore input here.
 v=v-22*np.sin(u/105+phase)-9*np.sin(u/43+.4*phase)
 total=np.zeros_like(u);records=[]
 for index,(along,cross,ll,ww,relative) in enumerate([(0,0,1,1,1),(-.71,-.27,.43,.61,.66),(.66,.37,.46,.57,.58)]):
  a=(u-along*L)/(L*ll);b=(v-cross*W)/(W*ww);rad=a*a+b*b
  support=1-T.ease((rad-.22)/.78)
  # A hard cap above a softer, broad footwall. The two narrow structural lows
  # seed drainage; their subsequent valley widths are computed by erosion.
  shoulder=.5+.5*np.tanh((b+.62)/.10);back=1-.22*T.ease((b+.2)/1.1)
  shape=support*shoulder*back*(1-.075*a)
  height=spec['reliefM']*relative*(.95+.10*rng.random())*shape
  total=np.maximum(total,height)
  records.append({'id':region+'-inland-cap-'+str(index+1),'centerReference':spec['center'],'alongOffsetKm':along*L,'crossOffsetKm':cross*W,'lengthKm':2*L*ll,'widthKm':2*W*ww,'angleDegrees':angle,'capReliefM':spec['reliefM']*relative,'lithology':'intact basalt cap, erodible sedimentary substrate'})
 return total,records

def correct(z,kind,g,region,seed,hard):
 if region not in SPECS:return z.copy(),np.zeros_like(z),np.zeros_like(z),{'applied':False}
 pg,source,provenance=removed_source(region,seed);removed=T.sample(source,pg,g)
 added,records=new_sources(region,seed,g);land=(kind>=30)&(kind!=80)
 free=land.astype(float)
 # Analytic scene distances remain identical in continent and cropped grids.
 # EDT of an all-free cropped window would invent a corner protection ramp.
 for feature in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
  if feature['geometry']['type']=='Point' and feature.get('id') not in ['V01','V02','WH']:
   free*=T.ease((T.distance(g,feature['geometry']['coordinates'])-20000)/80000)
 free[hard]=0
 # Keep old erosion and unrelated construction. The floor limiter is recorded,
 # rather than silently allowing the reconstructed bed to create new oceans.
 removal=np.minimum(removed,np.maximum(z-80,0))*free
 addition=added*free;out=z-removal+addition;out[hard]=z[hard]
 result={'applied':True,'region':region,'seed':seed,'oldSource':provenance,'newSources':records,
  'initialRepairOnly':True,'oldUpliftReapplied':False,'coastlineUsedToShapeSources':False,
  'removedM3':float(removal.sum()*g['stepM']**2),'addedM3':float(addition.sum()*g['stepM']**2),
  'sourceOutsideLandFraction':float(added[~land].sum()/max(added.sum(),1)),
  'floorLimitedM3':float(np.maximum(removed-np.maximum(z-80,0),0).sum()*g['stepM']**2),
  'protectedMaximumChangeM':float(abs(out-z)[hard].max(initial=0)),'newNonpositiveLandCells':int((land&(z>0)&(out<=0)).sum()),
  'assumption':'remove reconstructed old cap support, retain intervening erosion, add inland cap source once; reroute all affected rivers'}
 return out,removal,addition,result

def audit(z,kind,g):
 land=(kind>=30)&(kind!=80);dx=g['stepM'];coast=distance_transform_edt(land)*dx;high=land&(z>3000)
 near=high&(coast<100000);area=dx*dx/1e6
 return {'landAreaKm2':float(land.sum()*area),'highlandAreaKm2':float(high.sum()*area),'highlandWithin100kmCoastKm2':float(near.sum()*area),'maximumM':float(z[land].max()),'lowlandAreaKm2':float((land&(z<1400)).sum()*area)}

def run(seed=5210914,step=2000):
 L=importlib.import_module('tectonics-landscape')
 out=C.WORK/'coastal-repair';out.mkdir(parents=True,exist_ok=True);rows=[]
 for region in SPECS:
  source=BASE/region/str(seed);pg=C.read(source/'grid.json');g={**pg,'stepM':step,'width':round((pg['width']-1)*pg['stepM']/step)+1,'height':round((pg['height']-1)*pg['stepM']/step)+1,'seed':seed}
  old=T.sample(np.load(source/'height.npy'),pg,g);kind=T.sample(np.load(source/'kind.npy'),pg,g,0);hard=L.cores(g,kind)
  z,removed,added,report=correct(old,kind,g,region,seed,hard);folder=out/region/str(seed)
  for n,a in {'height':z,'initial':old,'kind':kind,'protected':hard,'removed-source':removed,'new-source':added,'base-repair':z-old}.items():C.save_array(folder/(n+'.npy'),a.astype('uint8') if n in ['kind','protected'] else a.astype('float32'))
  C.write(folder/'grid.json',g);report.update(before=audit(old,kind,g),after=audit(z,kind,g),parentHeightSha256=C.sha(source/'height.npy'),gridM=step)
  report['sourceGeometryPassed']=report['sourceOutsideLandFraction']<.01 and report['protectedMaximumChangeM']==0 and report['newNonpositiveLandCells']==0
  C.write(folder/'repair.json',report);rows.append(report);print('COASTAL SOURCE',region,seed,report['sourceGeometryPassed'],report['sourceOutsideLandFraction'],flush=True);gc.collect()
 C.write(out/f'audit-{seed}.json',rows)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=5210914);p.add_argument('--step',type=int,default=2000);q=p.parse_args();run(q.seed,q.step)
