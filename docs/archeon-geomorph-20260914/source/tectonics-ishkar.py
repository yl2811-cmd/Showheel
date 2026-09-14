"""Forward formation tests with an uncut restored barrier and real lake storage.

The river's present protected DEM is a target only. None of the historical
channel nodes is locked, burnt down, or reset to the modern gorge afterward.
"""
import pathlib,sys,importlib,json,math,argparse,time,gc,heapq
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('tectonics-continuation');T=C.T;np=T.np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter,map_coordinates
from numba import njit
CFG=C.CFG['riverHistory'];SECONDS=365.25*86400

def resample(line,step):
 line=np.asarray(line);s=np.r_[0,np.cumsum(np.hypot(*np.diff(line,axis=0).T))];keep=np.r_[True,np.diff(s)>1e-5];s=s[keep];line=line[keep];ss=np.arange(0,s[-1]+step*.1,step)
 return np.column_stack([np.interp(ss,s,line[:,0]),np.interp(ss,s,line[:,1])]),ss

def geometry(work,dx=2000,halfwidth=100000):
 base=C.FROZEN/'aethelgard';pg=json.loads((base/'grid.json').read_text(encoding='utf8'));p=T.Proj(pg['projection']);river=next(f for f in T.D['rivers'] if f['id']=='ishkar');r,ss=resample([p(*q) for q in river['geometry']['coordinates']],1000)
 fault=json.loads((base/'orun-trace.json').read_text(encoding='utf8'))['revised'];f,_=resample([p(*q) for q in fault],1000);dist,_=cKDTree(f).query(r);cross=int(dist.argmin());origin=r[cross];along=r[min(len(r)-1,cross+30)]-r[max(0,cross-30)];along/=np.linalg.norm(along);across=np.array([-along[1],along[0]])
 downstream=max(200000,float((r[-1]-origin)@along)+20000);u=np.arange(-halfwidth,halfwidth+dx*.1,dx);v=np.arange(-180000,downstream+dx*.1,dx);uu,vv=np.meshgrid(u,v);xx=origin[0]+uu*across[0]+vv*along[0];yy=origin[1]+uu*across[1]+vv*along[1]
 def sample(a,x=xx,y=yy):return map_coordinates(a,[(pg['ymax']-y)/pg['stepM'],(x-pg['xmin'])/pg['stepM']],order=1,mode='nearest',prefilter=False)
 z=sample(np.load(base/'5210914/height.npy')).astype(float);qfield=np.load(base/'5210914/discharge.npy');sedfield=np.load(base/'5210914/sediment-flux.npy');inlet=origin-160000*along;d=((T.mesh(pg)[0]-inlet[0])**2+(T.mesh(pg)[1]-inlet[1])**2);mask=d<48000**2;indices=np.flatnonzero(mask);chosen=indices[np.argmax(qfield.ravel()[indices])];qin=max(1e8,float(qfield.ravel()[chosen]));sedin=max(0,float(sedfield.ravel()[chosen]))
 # Restore the entire wide protected corridor from outside its footprint. The
 # resulting barrier includes the back slope all the way to the coastal end.
 flank=np.median(np.stack([sample(np.load(base/'5210914/height.npy'),origin[0]+offset*across[0]+v*along[0],origin[1]+offset*across[1]+v*along[1]) for offset in [-120000,-90000,90000,120000]]),axis=0)
 restored=z+(flank[:,None]-z)*(1-T.ease((abs(uu)-32000)/56000))
 modern=sample(np.load(base/'5210914/height.npy'),origin[0]+v*along[0],origin[1]+v*along[1]);head=float(np.median(modern[:8]));tail=max(0,float(np.median(modern[-8:])))
 low=np.broadcast_to(np.linspace(max(head,tail+120),tail,len(v))[:,None],z.shape).copy();rng=np.random.default_rng(5210914);rough=np.zeros_like(z)
 for k in range(6):
  wavelength=rng.uniform(18000,70000);angle=rng.uniform(-math.pi,math.pi);rough+=2.5*np.sin((xx*np.cos(angle)+yy*np.sin(angle))*2*math.pi/wavelength+rng.uniform(-math.pi,math.pi))
 low+=rough;uplift=np.maximum(0,restored-low)
 g={'id':'ishkar-history','width':len(u),'height':len(v),'stepM':dx,'xmin':float(u[0]),'ymax':float(-v[0]),'projection':pg['projection'],'worldAffine':{'origin':origin.tolist(),'across':across.tolist(),'downstream':along.tolist()},'orientation':'rows follow downstream, columns across the gorge; this diagnostic uses a rotated local metre grid'}
 record={'crossingCoordinates':list(p(*origin,inverse=True)),'crossingRegistrationM':float(dist[cross]),'upstreamDischargeM3yr':qin,'upstreamDischargeM3s':qin/SECONDS,'upstreamSedimentM3yr':sedin,'dischargeStatus':'Frozen v7 routed discharge under preliminary climate, not observed or GCM discharge','restoration':'Flank median beyond the modern protected corridor; no pre-cut gorge retained','formationBaseline':'Shallow undulating plane, at most order-ten-metre roughness, before uplift','modernDEMUsedFor':'target, exterior context, total relief, and upstream forcing only','sourceHashes':{n:T.sha(base/'5210914'/n) for n in ['height.npy','discharge.npy','sediment-flux.npy']},'grid':g}
 return low,uplift,restored,modern,qin,sedin,g,record

@njit(cache=False)
def route(z,profile,outlet_mask=None):
 h,w=z.shape;n=z.size;flat=z.ravel();filled=flat.copy();seen=np.zeros(n,np.uint8);outlet=np.zeros(n,np.uint8);parent=np.full(n,-1,np.int32);heap=[(-1e30,-1)];heapq.heappop(heap)
 if outlet_mask is not None:
  for i in range(n):
   if outlet_mask.ravel()[i]:outlet[i]=1;seen[i]=1;heapq.heappush(heap,(filled[i],i))
 else:
  for c in range(w):
   i=(h-1)*w+c;outlet[i]=1;seen[i]=1;heapq.heappush(heap,(filled[i],i))
 if not profile and outlet_mask is None:
  for r in range(1,h-1):
   for c in [0,w-1]:
    i=r*w+c;outlet[i]=1;seen[i]=1;heapq.heappush(heap,(filled[i],i))
 order=np.empty(n,np.int32);count=0
 while heap:
  level,i=heapq.heappop(heap);order[count]=i;count+=1;r=i//w;c=i%w
  for dr in range(-1,2):
   for dc in range(-1,2):
    if dr==0 and dc==0:continue
    rr=r+dr;cc=c+dc
    if rr<0 or cc<0 or rr>=h or cc>=w:continue
    j=rr*w+cc
    if seen[j]:continue
    seen[j]=1;filled[j]=max(flat[j],level+.00001);parent[j]=i;heapq.heappush(heap,(filled[j],j))
 rec=np.full(n,-1,np.int32)
 for i in order:
  if outlet[i]:continue
  rec[i]=parent[i];best=0.;r=i//w;c=i%w
  for dr in range(-1,2):
   for dc in range(-1,2):
    if dr==0 and dc==0:continue
    rr=r+dr;cc=c+dc
    if rr<0 or cc<0 or rr>=h or cc>=w:continue
    j=rr*w+cc;s=(filled[i]-filled[j])/math.sqrt(dr*dr+dc*dc)
    if s>best:best=s;rec[i]=j
 return filled.reshape(z.shape),order,rec

@njit(cache=False)
def water_step(z,filled,order,rec,store,source,area,dt):
 amount=source.ravel().copy()*dt;st=store.ravel().copy();capacity=np.maximum(filled.ravel()-z.ravel(),0)*area;active=np.zeros(z.size,np.uint8)
 for i in order:active[i]=1
 q=np.zeros(z.size);export=0.
 for kk in range(len(order)-1,-1,-1):
  i=order[kk];available=amount[i]+st[i];st[i]=min(available,capacity[i]);flow=available-st[i];q[i]=flow/dt;j=rec[i]
  if j>=0 and active[j]:amount[j]+=flow
  else:export+=flow
 return q,st.reshape(z.shape),export

@njit(cache=False)
def incise(z,soil,order,rec,q,filled,area,dx,dt,erodibility,sedin,inlet):
 zz=z.ravel().copy();hh=soil.ravel().copy();n=zz.size;er=np.zeros(n);dep=np.zeros(n);supply=np.zeros(n);active=np.zeros(n,np.uint8);export=0.
 for i in order:active[i]=1
 # Downstream-first implicit stream-power update has no time-step-dependent
 # arbitrary drop cap. Deposited sediment shields the bed exponentially.
 for i in order:
  j=rec[i]
  if j<0 or filled.ravel()[i]-z.ravel()[i]>.2:continue
  drop=max(0,zz[i]-zz[j]);fac=erodibility.ravel()[i]*math.sqrt(max(0,q[i]))*dt/dx
  fac*=.08+.92*math.exp(-hh[i]/.5);cut=drop*fac/(1+fac);zz[i]-=cut;er[i]=cut;hh[i]=max(0,hh[i]-cut)
 supply[inlet]=sedin*dt
 for kk in range(len(order)-1,-1,-1):
  i=order[kk];s=supply[i]+er[i]*area;j=rec[i]
  if j<0:export+=s;continue
  settling=1-math.exp(-.03*area/max(1,q[i]));put=min(s/area*settling,max(0,filled.ravel()[i]-zz[i])+1.);zz[i]+=put;hh[i]+=put;dep[i]=put;s-=put*area
  if j>=0 and active[j]:supply[j]+=s
  else:export+=s
 return zz.reshape(z.shape),hh.reshape(z.shape),er.reshape(z.shape),dep.reshape(z.shape),export

def solve(low,uplift,modern,qin,sedin,g,history,formation,runoff,dt=10000,profile=False,coast=None):
 dx=g['stepM'];area=dx*dx;z=low.copy()+(uplift if history=='late-breach' else 0);initial=z.copy();soil=np.full(z.shape,.3);land=np.ones(z.shape,bool);land[[0,-1],:]=False;land[:,[0,-1]]=False
 z[0,:]=np.max(low+uplift)+10000;uplift=uplift.copy();uplift[0,:]=0
 if profile:z[:,[0,-1]]=np.max(low+uplift)+10000;uplift[:,[0,-1]]=0
 if coast is not None:
  land&=~coast;frame=np.zeros(z.shape,bool);frame[[0,-1],:]=True;frame[:,[0,-1]]=True;walls=frame&~coast;z[walls]=np.max(low+uplift)+10000;uplift[walls|coast]=0;z[coast]=0
 initial=z.copy();source=np.full_like(z,.06*runoff*area);source[~land]=0;inlet=np.ravel_multi_index((2,z.shape[1]//2),z.shape);source.ravel()[inlet]+=qin*runoff;source_total=float(source.sum());store=np.zeros_like(z);all_er=np.zeros_like(z);all_dep=np.zeros_like(z);all_u=np.zeros_like(z);waterout=sedout=0.;ledger=[];end=formation+CFG['postUpliftYears'];now=-500000. if history!='late-breach' else 0.;snapshots={int(now):z.copy()};breakthrough=None;spill_time=None;max_water_error=max_solid_error=0.
 width=np.arange(z.shape[1])*dx-(z.shape[1]-1)*dx/2;weak=1+(CFG['fractureErodibilityMultiplier']-1)*np.exp(-((width-8000)/12000)**2) if history=='fracture-assisted' else np.ones_like(width)
 while now<end:
  step=min(dt,end-now);before=z.copy();water_before=store.sum();oldprogress=max(0,min(1,now/formation));newprogress=max(0,min(1,(now+step)/formation))
  du=uplift*(newprogress-oldprogress) if history!='late-breach' else np.zeros_like(z);z+=du;all_u+=du
  filled,order,rec=route(z,profile,coast);q,store,out=water_step(z,filled,order,rec,store,source,area,step);waterout+=out
  if spill_time is None and out>source_total*step*.5:spill_time=now+step
  exposed=np.maximum(0,initial+all_u-z);cap=420.;K=np.where((exposed<cap)|(np.mod(np.maximum(0,exposed-cap),440)>260),T.C['lithology']['hardK'],T.C['lithology']['softK']);K*=weak[None]*.98;K[~land]=0
  z,soil,er,dep,export=incise(z,soil,order,rec,q,filled,area,dx,step,K,sedin*runoff,inlet);all_er+=er;all_dep+=dep;sedout+=export
  solid_error=(z-before-du).sum()*area-sedin*runoff*step+export;water_error=store.sum()-water_before-source_total*step+out
  max_water_error=max(max_water_error,abs(water_error)/max(1,source_total*step));max_solid_error=max(max_solid_error,abs(solid_error)/max(1,abs(du.sum()*area)+export+sedin*runoff*step))
  # Follow the actual receiver chain. Reaching a side is a diverted trial.
  path=[];i=inlet;seen=set();barrier_depth=0
  while i>=0 and i not in seen and len(path)<z.size:
   seen.add(i);path.append(i);barrier_depth=max(barrier_depth,float(filled.ravel()[i]-z.ravel()[i]));j=int(rec[i])
   if j<0 or not land.ravel()[j]:break
   i=j
  row=path[-1]//z.shape[1];col=path[-1]%z.shape[1];south=row>=z.shape[0]-3;reaches_ocean=bool(coast is not None and j>=0 and coast.ravel()[j]);openchannel=(reaches_ocean if coast is not None else south) and barrier_depth<5 and out>source_total*step*.9
  if breakthrough is None and openchannel and now+step>=formation:breakthrough=now+step
  now+=step
  if len(ledger)<10 or int(now)%100000==0 or now==end:ledger.append({'year':now,'lakeStorageM3':float(store.sum()),'waterRelativeError':float(abs(water_error)/max(1,source_total*step)),'solidRelativeError':float(abs(solid_error)/max(1,abs(du.sum()*area)+export+sedin*runoff*step)),'largestPathPondM':barrier_depth,'southOutlet':south})
  for year in [0,formation*.1,formation*.5,formation,end]:
   if now-step<year<=now:snapshots[int(year)]=z.copy()
  if int(now)%5000000==0 and not profile:T.log(f'ISHKAR {history} {formation//1000000}M runoff{runoff} {int(now)//1000} kyr')
 # Run the final routing again, after the final erosion update.
 filled,order,rec=route(z,profile,coast);path=[];i=inlet;seen=set()
 while i>=0 and i not in seen:
  seen.add(i);path.append(i);j=int(rec[i])
  if j<0 or not land.ravel()[j]:break
  i=j
 indices=np.asarray(path);rr=indices//z.shape[1];cc=indices%z.shape[1];south=rr[-1]>=z.shape[0]-3;pond=float(np.max((filled-z).ravel()[indices]));offset=float(np.max(abs(width[cc])));river_rms=float(np.sqrt(np.mean((z[rr,cc]-modern[rr])**2)))
 result={'history':history,'formationYears':formation,'runoffMultiplier':runoff,'timeStepYears':dt,'gridStepM':dx,'dimension':'1D network screening' if profile else '2D free drainage with finite lake storage','breakthroughYear':breakthrough,'firstMajorSpillYear':spill_time,'southOutlet':bool(south),'maximumPathPondM':pond,'pathOffsetM':offset,'modernProfileRmsM':river_rms,'maximumIncisionM':float(all_er.max()),'erodedRockM3':float(all_er.sum()*area),'depositedM3':float(all_dep.sum()*area),'exportedSedimentM3':sedout,'exportedWaterM3':waterout,'lakeStorageM3':float(store.sum()),'maxWaterRelativeError':max(v['waterRelativeError'] for v in ledger),'maxSolidRelativeError':max(v['solidRelativeError'] for v in ledger),'hydrologicallyOpen':bool(south and pond<5),'targetCompatible':bool(south and pond<5 and offset<28000 and river_rms<150),'protectedModernSurfaceWritten':False,'historicalRiverLocked':False,'historyLedger':ledger,'pathRows':rr.tolist(),'pathColumns':cc.tolist()}
 result['preUpliftRiverEstablishmentYears']=500000 if history!='late-breach' else 0;result['maxWaterRelativeError']=max_water_error;result['maxSolidRelativeError']=max_solid_error;result['boundaryPolicy']='north inflow-only reservoir; south and 2D sides can export; 1D sides closed, excluded from physical terrain';result['conservationPassed']=max_water_error<1e-8 and max_solid_error<1e-7
 if coast is not None:
  end_receiver=int(rec[indices[-1]]);reaches=bool(end_receiver>=0 and coast.ravel()[end_receiver]);result.update(reachesActualCoast=reaches,hydrologicallyOpen=bool(reaches and pond<5),boundaryPolicy='Only inherited ocean cells export; inland outer edges are closed reservoirs, excluded from physical terrain',targetCompatible=bool(reaches and pond<5 and offset<28000 and river_rms<150))
  result['maximumPathErosionM']=float(all_er[rr,cc].max());result['coastExitNode']=end_receiver if reaches else None
 return result,{'initial':initial,'height':z,'erosion':all_er,'deposition':all_dep,'water-storage':store,'restored-barrier':low+uplift,'snapshots':snapshots}

def save_case(folder,result,fields,g,provenance):
 folder.mkdir(parents=True,exist_ok=True)
 for name,a in fields.items():
  if name=='snapshots':
   for y,v in a.items():np.save(folder/f'height-{y}.npy',v.astype('float32'))
  else:np.save(folder/(name+'.npy'),a.astype('float32'))
 T.savejson(folder/'result.json',result);T.savejson(folder/'grid.json',g);T.savejson(folder/'provenance.json',provenance)

def run(work,stage='screen',dx=2000,dt=10000):
 T.WORK=work;out=work/'ishkar-history';out.mkdir(parents=True,exist_ok=True);low,uplift,restored,modern,q,sed,g,record=geometry(work,dx);T.savejson(out/'source.json',record)
 results=[]
 if stage=='screen':
  # A three-column network prevents an artificial pre-cut channel; lateral
  # routing is deliberately unavailable here, which is why 2D is mandatory.
  center=g['width']//2;l=low[:,center:center+1];u=uplift[:,center:center+1];l=np.repeat(l,3,axis=1);u=np.repeat(u,3,axis=1);gg={**g,'width':3}
  for history in CFG['histories']:
   for formation in CFG['formationYears']:
    for runoff in CFG['runoffMultipliers']:
     result,fields=solve(l,u,modern,q,sed,gg,history,formation,runoff,dt,True);name=f'{history}-{formation}-{runoff:g}';save_case(out/'screen'/name,result,fields,gg,record);results.append(result);T.log('ISHKAR SCREEN '+name)
  T.savejson(out/'screen-summary.json',results)
 else:
  screen=json.loads((out/'screen-summary.json').read_text(encoding='utf8'));selected=[]
  for history in CFG['histories']:
   rows=[v for v in screen if v['history']==history];rank=sorted(rows,key=lambda v:(not v['hydrologicallyOpen'],v['modernProfileRmsM'],abs(math.log(v['runoffMultiplier'])),abs(v['formationYears']-12000000)))
   selected.append(rank[0]);failed=[v for v in rows if not v['hydrologicallyOpen']];selected.append(min(failed,key=lambda v:abs(v['formationYears']-rank[0]['formationYears'])+1e6*abs(v['runoffMultiplier']-rank[0]['runoffMultiplier'])) if failed else rank[-1])
  seen=set()
  for v in selected:
   key=(v['history'],v['formationYears'],v['runoffMultiplier'])
   if key in seen:continue
   seen.add(key);result,fields=solve(low,uplift,modern,q,sed,g,*key,dt,False);name=f'{key[0]}-{key[1]}-{key[2]:g}-dx{dx}-dt{dt}';save_case(out/'two-d'/name,result,fields,g,record);results.append(result)
  T.savejson(out/f'two-d-summary-dx{dx}-dt{dt}.json',results)
 return results
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=C.DEFAULT);ap.add_argument('--stage',choices=['screen','two-d','all'],default='screen');ap.add_argument('--grid-m',type=int,default=2000);ap.add_argument('--dt',type=int,default=10000);a=ap.parse_args();C.open_work(a.work)
 for stage in ['screen','two-d'] if a.stage=='all' else [a.stage]:run(a.work,stage,a.grid_m,a.dt)
