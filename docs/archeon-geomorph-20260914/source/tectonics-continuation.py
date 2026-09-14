"""Regional continuation of the frozen v7 surface. Geological clocks only.

Mesoscale displacement and morphology priors are recorded separately. The
polar bed is an explicit hypothesis, not an inversion of measured ice depth.
"""
import pathlib,sys,json,math,importlib,argparse,shutil,time,hashlib,gc,os
sys.path.insert(0,str(pathlib.Path(__file__).parent))
T=importlib.import_module('tectonics-model');np=T.np
from scipy.ndimage import gaussian_filter,maximum_filter
ROOT=T.ROOT;BASE=T.BASE_WORK;ARCHIVE=BASE/'archives/strong-painted-v7-20260914';FROZEN=ARCHIVE/'study'
if os.environ.get('TECTONICS_FROZEN_BASE'):
 FROZEN=pathlib.Path(os.environ['TECTONICS_FROZEN_BASE']).resolve();ARCHIVE=FROZEN.parent
 if not (ARCHIVE/'freeze.json').is_file():raise ValueError('Continuation base must be a verified frozen study')
CFG=json.loads((ROOT/'data/tectonics-continuation.json').read_text(encoding='utf8'))
DEFAULT=BASE/'evolution-geomorph-v10';ORIGINAL_ATMOSPHERE=T.atmosphere

def config(work):
 c=json.loads((FROZEN/'run-config.json').read_text(encoding='utf8')) if (FROZEN/'run-config.json').exists() else json.loads((ARCHIVE/'config/tectonics-config.json').read_text(encoding='utf8'))
 c['version']=CFG['version'];c['timesYears']=CFG['geologyYears'];c['stepYears']=10000;c['gridStepM']=16000;c['refinements']=[]
 for r in CFG['polarRegions']:c['regions'][r['id']]={'title':r['title'],'landIds':[r['landId']],'center':r['center'],'faults':[],'polar':True}
 c['continuation']=CFG;c['frozenBase']=str(FROZEN);T.savejson(work/'run-config.json',c);return c

def open_work(work,mask=None):
 work.mkdir(parents=True,exist_ok=True);T.WORK=work;T.MASK=mask;T.C=config(work);T.atmosphere=atmosphere
 return T.C

def atmosphere(z,g,kind):
 a=ORIGINAL_ATMOSPHERE(z,g,kind)
 if g.get('region','').startswith('polar-'):
  # Annual temperature-cycle screening, not a glacier mass-balance solver.
  seasons=a['temperature'][None]+np.sin(np.arange(12)*2*np.pi/12)[:,None,None]*9
  thaw=(seasons>0).mean(axis=0);cross=((seasons.max(axis=0)>0)&(seasons.min(axis=0)<0)).astype(float)
  a['frost-weathering']=.08+1.6*cross;a['runoff']*=thaw
  a['recharge']*=thaw;a['snow-storage-rate']=np.maximum(a['rain']-a['evap']-a['runoff']-a['recharge'],0)
 return a

def quiet(g):
 d=np.minimum(T.distance(g,[.4897728955495773,27.798124784891048]),T.distance(g,[0,26]))
 return T.ease((d-CFG['mesorelief']['quietInnerKm']*1000)/100000)

def prepare(region,step=16000):
 out=T.WORK/region;out.mkdir(parents=True,exist_ok=True)
 if (FROZEN/region/'grid.json').exists():
  pg=json.loads((FROZEN/region/'grid.json').read_text(encoding='utf8'));g={**pg,'stepM':step,'width':round((pg['width']-1)*pg['stepM']/step)+1,'height':round((pg['height']-1)*pg['stepM']/step)+1}
  kind=T.sample(np.load(FROZEN/region/'kind.npy'),pg,g,0)
  protected=T.sample(np.load(FROZEN/region/'hard-protected.npy'),pg,g,0)>0
  for name in ['override','orun-ramp-weight','orun-front-weight','ishkar-protected']:
   p=FROZEN/region/(name+'.npy')
   if p.exists():np.save(out/(name+'.npy'),T.sample(np.load(p),pg,g,0))
  for p in (FROZEN/region).glob('*.json'):
   if p.name!='grid.json':shutil.copy2(p,out/p.name)
 else:
  old=T.C['gridStepM'];T.C['gridStepM']=step;g=T.region_grid(region);T.C['gridStepM']=old
  _,kind=T.native(g);footprint=T.raster([next(f for f in T.D['land'] if f['id']==T.C['regions'][region]['landIds'][0])['geometry']],g)
  # Explicit footprint wins at low-resolution coastline; FAR remains excluded.
  kind[~footprint]=0;kind[footprint]=70
  protected=(kind<30)|(T.edt(kind>=30)*step<16000)
 for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
  if f['geometry']['type']=='Point':protected|=T.distance(g,f['geometry']['coordinates'])<20000
 g.update(id=region,region=region);allow=T.ease(T.edt(~protected)*step/24000).astype('float32');allow[protected]=0
 for name,a in {'kind':kind,'baseline-kind':kind,'protected':protected,'hard-protected':protected,'allow':allow,'evolution-allow':allow}.items():np.save(out/(name+'.npy'),a)
 T.savejson(out/'grid.json',g)
 return g,kind,allow

def base_surface(region,seed,g):
 if (FROZEN/region).exists():
  pg=json.loads((FROZEN/region/'grid.json').read_text(encoding='utf8'));p=FROZEN/region/str(seed)/'height.npy';z=T.sample(np.load(p),pg,g)
 else:p=ROOT/'terrain/world-height.f32';z,_=T.native(g)
 return z.astype('float32'),{'file':str(p),'sha256':T.sha(p),'interpretation':'frozen v7 final surface' if (FROZEN/region).exists() else 'inherited polar elevation used as provisional rock datum; actual ice thickness unknown'}

def terrain_catalog(region,seed,g,base,allow):
 rng=np.random.default_rng(seed+sum(map(ord,region)));dx=g['stepM'];free=(allow>.6)&(base<6500);cells=np.flatnonzero(free);p=T.Proj(g['projection']);catalog=[];centres=[]
 if not len(cells):return catalog
 area=free.sum()*dx*dx/1e6;number=max(8,round(area*.27/(math.pi*65*32)))
 controls=T.weights(region,g);q=quiet(g) if region=='aethelgard' else np.ones_like(base)
 for cell in rng.permutation(cells):
  r,c=np.unravel_index(cell,base.shape);x=float(g['xmin']+c*dx);y=float(g['ymax']-r*dx)
  if any((x-xx)**2+(y-yy)**2<(85000*.8)**2 for xx,yy in centres):continue
  if rng.random()>min(1,float(controls['relief-density'][r,c])/1.5):continue
  centres.append((x,y));family=rng.choice(['bench','tilted','ridge','basin','low-hills'],p=[.25,.2,.2,.15,.2])
  length=rng.uniform(45000,150000);width=length*rng.uniform(.24,.6);amp=rng.uniform(200,1500)*(.14+.86*q[r,c]);theta=rng.uniform(-.3,.3)+({'aethelgard':.4,'vorhan':1.1,'duskreach':-.4,'keld':1.15}.get(region,.6))
  catalog.append({'id':f'{region}-meso-{len(catalog)+1:04}','center':list(p(x,y,inverse=True)),'xy':[x,y],'lengthM':length,'widthM':width,'reliefM':amp,'angleRadians':theta,'family':family,'phase':float(rng.uniform(-3,3)),'scale':'medium'})
  if len(catalog)>=number:break
 # Small features are catalogued at stable geographic positions and are only
 # evaluated on a grid able to resolve them. They are not fake coarse texture.
 for parent in catalog.copy()[::2]:
  for k in range(3):
   x,y=parent['xy'];x+=rng.uniform(-1,1)*parent['lengthM']*.5;y+=rng.uniform(-1,1)*parent['widthM']
   length=rng.uniform(4000,20000)
   rr=int(np.clip(round((g['ymax']-y)/dx),0,g['height']-1));cc=int(np.clip(round((x-g['xmin'])/dx),0,g['width']-1));quiet_scale=.14+.86*q[rr,cc]
   catalog.append({'id':parent['id']+f'-small-{k}','center':list(p(x,y,inverse=True)),'xy':[x,y],'lengthM':length,'widthM':length*rng.uniform(.4,.8),'reliefM':rng.uniform(20,500)*quiet_scale,'angleRadians':parent['angleRadians']+rng.uniform(-.6,.6),'family':rng.choice(['bench','basin','ridge']),'phase':float(rng.uniform(-3,3)),'scale':'small'})
 return catalog

def displacement(g,catalog,allow,controls,minimum_cells=3):
 dx=g['stepM'];u=np.zeros(allow.shape);prior=np.zeros_like(u);traces=[];resolved=[]
 for f in catalog:
  if min(f['lengthM'],f['widthM'])*2<minimum_cells*dx:continue
  cx,cy=f['xy'];theta=f['angleRadians'];L=f['lengthM'];W=f['widthM'];radius=max(L,W)*1.3
  c0=max(0,math.floor((cx-radius-g['xmin'])/dx));c1=min(g['width'],math.ceil((cx+radius-g['xmin'])/dx)+1);r0=max(0,math.floor((g['ymax']-cy-radius)/dx));r1=min(g['height'],math.ceil((g['ymax']-cy+radius)/dx)+1)
  if c1<=c0 or r1<=r0:continue
  xx,yy=np.meshgrid(g['xmin']+np.arange(c0,c1)*dx-cx,g['ymax']-np.arange(r0,r1)*dx-cy)
  a=(xx*np.cos(theta)+yy*np.sin(theta))/L;b=(-xx*np.sin(theta)+yy*np.cos(theta))/W
  b-=.16*np.sin(a*2+f['phase']);rad=a*a+b*b;envelope=np.maximum(0,1-rad)**2
  family=f['family'];shape=envelope
  if family=='bench':shape=T.ease((1-rad)/.5)*(.85+.15*a)
  elif family=='tilted':shape=envelope*(.6+.5*np.tanh(b*4))
  elif family=='ridge':shape=np.maximum(0,1-a*a)**2*np.exp(-b*b*8)*T.ease((1-rad)*3)
  elif family=='basin':shape=-.28*envelope
  elif family=='low-hills':shape*=.2
  s=(slice(r0,r1),slice(c0,c1));u[s]+=shape*f['reliefM'];prior[s]+=.035*f['reliefM']*envelope*np.sin(a*4+f['phase'])*np.cos(b*3-f['phase'])
  resolved.append(f['id'])
  if family in ['bench','tilted','ridge']:
   p=T.Proj(g['projection']);tx=np.linspace(-.8,.8,15)*L;ty=(.16*np.sin(tx/L*2+f['phase']))*W
   coords=np.column_stack(p(cx+tx*np.cos(theta)-ty*np.sin(theta),cy+tx*np.sin(theta)+ty*np.cos(theta),inverse=True)).tolist()
   traces.append({'id':f['id'],'mode':'normal' if family!='ridge' else 'compression','coordinates':coords,'scale':f['scale']})
 return u*allow*controls['tectonic']*controls['relief-amplitude'],prior*allow*controls['relief-amplitude'],traces,resolved

def polar_blocks(region,seed,g,allow):
 spec=next(v for v in CFG['polarRegions'] if v['id']==region);rng=np.random.default_rng(seed+sum(map(ord,region)));xx,yy=T.mesh(g);free=np.argwhere(allow>.7);u=np.zeros_like(allow,dtype=float);prior=np.zeros_like(u);records=[]
 if not len(free):return u,prior,records
 import rasterio
 source=T.OLD/'references'/('stepped.tif' if spec['family']=='cap-plateau' else 'mountain.tif')
 with rasterio.open(source) as raster:dem=raster.read(1).astype(float)
 dem[~np.isfinite(dem)|(abs(dem)>15000)]=np.nanmedian(dem[(np.isfinite(dem))&(abs(dem)<15000)])
 center=free.mean(axis=0);distance=((free-center)**2).sum(axis=1);row,col=free[np.argmin(distance)];cx=xx[row,col];cy=yy[row,col];extent=np.ptp(free,axis=0)*g['stepM'];L=max(90000,extent[1]*.32);W=max(60000,extent[0]*.30)
 for k in range(3):
  x=cx+(k-1)*L*.82;y=cy+(k-1)*W*.32+rng.uniform(-.18,.18)*W;angle=.25+rng.uniform(-.45,.45);a=((xx-x)*np.cos(angle)+(yy-y)*np.sin(angle))/L;b=(-(xx-x)*np.sin(angle)+(yy-y)*np.cos(angle))/W;b-=.18*np.sin(a*2+k)
  footprint=np.maximum(0,1-(a*a+b*b))**2;shape=footprint
  if spec['family']=='tilted-blocks':shape*=.6+.6*T.ease((b+.2)*2)
  elif spec['family']=='cap-plateau':shape=T.ease((1-a*a-b*b)/.55)*(.9+.1*a)
  elif spec['family']=='fold-belt':shape=np.exp(-b*b*8)*np.maximum(0,1-a*a)**2
  elif spec['family']=='volcanic':shape=np.exp(-3*(a*a+b*b))*T.ease((1-a*a-b*b)*3)
  amount=shape*spec['reliefM']*rng.uniform(.75,1.05)
  # These lobes describe one regional uplift episode. A smooth envelope avoids
  # counting its full displacement two or three times at overlapping centres.
  u=(u**4+amount**4)**.25
  size=int(rng.integers(560,900));rr=int(rng.integers(0,len(dem)-size));cc=int(rng.integers(0,dem.shape[1]-size));rotation=int(rng.integers(0,4));crop=np.rot90(dem[rr:rr+size,cc:cc+size],rotation);crop=T.norm(crop-gaussian_filter(crop,size/7))
  texture=T.map_coordinates(crop,[(b+1)*.5*(size-1),(a+1)*.5*(size-1)],order=1,mode='nearest',prefilter=False);prior+=texture*620*footprint
  p=T.Proj(g['projection']);records.append({'id':region+f'-block-{k}','family':spec['family'],'center':list(p(x,y,inverse=True)),'regionalReliefScaleM':spec['reliefM'],'overlap':'fourth-power envelope of one regional episode','morphology':{'source':str(source),'sha256':T.sha(source),'cropPixels':[cc,rr,size,size],'rotationQuarterTurns':rotation,'extentMetres':[2*L,2*W],'amplitudeM':620,'role':'Measured terrestrial morphology prior, not simulated Archeon rock displacement or measured Archeon elevation'}})
 return u*allow,prior*allow,records

def run_region(region,seed,step=16000,end=100000,mask=None):
 T.MASK=mask;g,kind,allow=prepare(region,step);base,lineage=base_surface(region,seed,g);out=T.WORK/region/str(seed);out.mkdir(parents=True,exist_ok=True);controls=T.weights(region,g);allow*=1-controls['protection']
 frozen_kind=FROZEN/region/str(seed)/'kind.npy'
 if frozen_kind.exists():kind=T.sample(np.load(frozen_kind),json.loads((FROZEN/region/'grid.json').read_text(encoding='utf8')),g,0)
 allow[(kind<30)|(kind==80)|(kind==200)]=0
 catalog=terrain_catalog(region,seed,g,base,allow);u,prior,traces,resolved=displacement(g,catalog,allow,controls);broad=np.zeros_like(u);blocks=[]
 if region.startswith('polar-'):
  broad,polar_prior,blocks=polar_blocks(region,seed,g,allow);broad*=controls['tectonic'];prior+=polar_prior*controls['relief-amplitude']
 ini=base+u+prior+broad
 # Preserve base highlands and cores; basin offsets are intentional, bounded
 # geological features rather than a global height normalization.
 ini[allow==0]=base[allow==0]
 for name,a in {'baseline':base,'revised':base}.items():np.save(T.WORK/region/(name+'.npy'),a)
 if region=='aethelgard' and not (T.WORK/region/'override.npy').exists():np.save(T.WORK/region/'override.npy',np.zeros_like(base))
 for name,a in {'initial':ini,'height-0':ini,'kind':kind,'uplift-rate':np.zeros_like(base),'meso-displacement':u,'material-prior':prior,'polar-construction':broad,'cap-thickness':np.full_like(base,420)}.items():np.save(out/(name+'.npy'),np.asarray(a,dtype='float32'))
 oldfaults=FROZEN/region/str(seed)/'faults.json';faults=json.loads(oldfaults.read_text(encoding='utf8')) if oldfaults.exists() else []
 T.savejson(out/'faults.json',faults+traces);T.savejson(out/'landforms.json',catalog);T.savejson(out/'polar-blocks.json',blocks)
 q=quiet(g) if region=='aethelgard' else np.ones_like(base)
 report={'source':lineage,'geologicalClock':'continuation after frozen v7, not civil years','resolvedLandforms':len(resolved),'cataloguedLandforms':len(catalog),'gridStepM':step,'resolvedIds':resolved,'protectedMaxDeltaM':float(np.max(abs(ini[allow==0]-base[allow==0]),initial=0)),'quietNewReliefP99M':float(np.percentile(abs((u+prior)[(q==0)&(allow>0)]),99)) if ((q==0)&(allow>0)).any() else None,'materials':'Small procedural morphology prior recorded separately; no new tile crop is claimed as DEM evidence.','polarDatumStatus':lineage['interpretation']}
 T.savejson(out/'construction.json',report)
 oldtimes=T.C['timesYears'];T.C['timesYears']=[v for v in CFG['geologyYears'] if v<=end];T.C['stepYears']=min(10000,max(500,step*.5));T.evolve(region,seed);T.C['timesYears']=oldtimes
 T.log(f'CONTINUATION {region} {seed}: {len(resolved)} resolved landforms')
 return out

def record_sources(work):
 out=work/'source-used';out.mkdir(parents=True,exist_ok=True)
 for p in (ROOT/'src').glob('tectonics-*.py'):shutil.copy2(p,out/p.name)
 shutil.copy2(ROOT/'data/tectonics-continuation.json',work/'continuation-config.json')
 T.savejson(work/'lineage.json',{'frozenArchive':str(ARCHIVE),'freezeManifestSha256':T.sha(ARCHIVE/'freeze.json'),'createdUnix':time.time(),'climate':'preliminary forcing; no real GCM result','formalMapChanged':False})

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=DEFAULT);ap.add_argument('--region',default='all');ap.add_argument('--seed',type=int);ap.add_argument('--grid-m',type=int,default=16000);ap.add_argument('--end',type=int,default=100000);ap.add_argument('--mask',type=pathlib.Path);a=ap.parse_args();open_work(a.work,a.mask);record_sources(a.work)
 for region in T.C['regions']:
  if a.region not in ['all',region]:continue
  for seed in [a.seed] if a.seed else CFG['seeds']:run_region(region,seed,a.grid_m,a.end,a.mask);gc.collect()
if __name__=='__main__':main()
