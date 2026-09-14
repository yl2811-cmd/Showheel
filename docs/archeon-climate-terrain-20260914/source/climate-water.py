"""Conservative current-climate soil, snow, groundwater and seasonal lakes."""
import pathlib,sys,importlib
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;H=importlib.import_module('landscape-water');F=importlib.import_module('climate-forcing');TIME=importlib.import_module('climate-time')

def run(z,land,dx,soil_depth,forcing,max_cycles=120,external=None,initial_depth=None,external_units='m3 per Earth year'):
 cal=TIME.calendar(getattr(forcing,'calendar',None));year_seconds=cal['orbitalPeriodSeconds']
 durations=np.asarray(forcing.durations,float)
 if not np.isfinite(durations).all() or np.any(durations<=0) or not np.isclose(durations.sum(),year_seconds,rtol=1e-9):raise ValueError('Hydrology forcing duration differs from declared orbital cycle')
 tp=H.topology(z,land,dx);active=tp['land'];area=dx*dx;b=tp['basin'];nodes=tp['nodes'];starts=tp['starts'];count=tp['count'];capacity=np.maximum(.005,np.maximum(soil_depth,0)*.25)
 sw=np.zeros_like(z);snow=np.zeros_like(z);groundwater=np.zeros_like(z);store=np.zeros(count)
 if initial_depth is not None:store=np.bincount(b[nodes],weights=initial_depth.ravel()[nodes]*area,minlength=count)
 ext=np.zeros_like(z) if external is None else np.asarray(external,float)
 if external_units=='m3 per Earth year':ext=ext*(year_seconds/TIME.EARTH_YEAR_SECONDS)
 elif external_units=='m3 s-1':ext=ext*year_seconds
 else:raise ValueError('External inflow needs explicit Earth-year volume or SI flow rate')
 if np.any(ext<0) or not np.isfinite(ext).all():raise ValueError('Invalid external inflow')
 if np.any(ext[~active]!=0):raise ValueError('External inflow must enter active interior cells')
 history=[];previous=None;stable=0;annual_pr=np.zeros_like(z);annual_pet=np.zeros_like(z);qmean=np.zeros_like(z);previous_storage=None
 for cycle in range(max_cycles):
  qmean.fill(0);annual_pr.fill(0);annual_pet.fill(0);occ=np.zeros_like(z);mind=np.full_like(z,np.inf);maxd=np.zeros_like(z);levels=[];errors=[];input_total=output_total=evap_total=0.
  storage_start=float((sw+snow+groundwater).sum()*area+store.sum())
  for i,seconds in enumerate(forcing.durations):
   f=forcing.season(i);fraction=seconds/year_seconds;before=float((sw+snow+groundwater).sum()*area+store.sum())
   p=np.maximum(f['pr'],0)*seconds*active;ps=np.minimum(p,np.maximum(f['prsn'],0)*seconds*active);pet=np.maximum(f['pet'],0)*seconds*active;annual_pr+=p;annual_pet+=pet
   snow+=ps;net=np.maximum(0,f['rss']+f['rlds']-f['rlus']);melt=np.minimum(snow,np.where(f['tas']>273.15,net*seconds/(334000*1000),0));snow-=melt;liquid=p-ps+melt
   depth=H.depth_field(z,dx,tp,store);wet=(depth>.05)&active;liquid[wet]+=sw[wet];sw[wet]=0
   recharge=np.minimum(liquid*.2,np.maximum(0,capacity-sw));recharge[wet]=0;groundwater+=recharge;liquid-=recharge
   baseflow=groundwater*(1-np.exp(-seconds/(180*86400)));groundwater-=baseflow
   sw[~wet]+=liquid[~wet];evap=np.minimum(sw,pet);sw-=evap;evap_total+=float(evap.sum()*area)
   runoff=np.maximum(sw-capacity,0);sw-=runoff;runoff[wet]=liquid[wet];runoff+=baseflow
   source=(runoff*area/fraction)+ext;basin_pet=np.bincount(b[nodes],weights=(f['pet']*year_seconds).ravel()[nodes],minlength=count)/np.maximum(1,np.diff(starts))
   q,out,levap,leak=H._season(tp['order'],tp['receiver'],tp['bed-receiver'],wet.ravel(),b,tp['representative'],starts,tp['floors'],tp['sums'],tp['capacity'],store,source.ravel(),basin_pet,np.zeros(count),area,fraction)
   # Groundwater exchange is handled explicitly above; no second hidden lake loss.
   qmean+=q.reshape(z.shape)*fraction;input_volume=float(p.sum()*area+ext.sum()*fraction);output_volume=float(out);evap_volume=float(evap.sum()*area+levap)
   after=float((sw+snow+groundwater).sum()*area+store.sum());residual=after-before-input_volume+output_volume+evap_volume;error=abs(residual)/max(1,before,input_volume,after)
   if error>1e-8:raise ValueError('Soil/snow/lake water balance '+str(error))
   errors.append(error);input_total+=input_volume;output_total+=out;evap_total+=levap
   depth=H.depth_field(z,dx,tp,store);mind=np.minimum(mind,depth);maxd=np.maximum(maxd,depth);occ+=(depth>.05)*fraction;levels.append(H._levels(store,starts,tp['floors'],tp['sums'],area))
  level=np.asarray(levels);end_storage=float((sw+snow+groundwater).sum()*area+store.sum())
  level_change=float(np.max(abs(level-previous),initial=0)) if previous is not None else float('inf');drift=abs(end_storage-storage_start)/max(1,input_total,end_storage)
  stable=stable+1 if level_change<.02 and drift<1e-4 else 0;previous=level
  history.append({'waterYear':cycle+1,'precipitationAndExternalM3':input_total,'evaporationM3':evap_total,'outletM3':output_total,'storageStartM3':storage_start,'storageEndM3':end_storage,'maxWaterRelativeError':max(errors),'maximumPeriodicLakeChangeM':level_change,'relativeStorageDrift':drift})
  if stable>=3:break
 depth=H.depth_field(z,dx,tp,store);receiver=tp['bed-receiver'].copy();receiver[depth.ravel()>.05]=tp['receiver'][depth.ravel()>.05];receiver[tp['representative']]=tp['receiver'][tp['representative']]
 return {'discharge':qmean*TIME.EARTH_YEAR_SECONDS/year_seconds,'discharge-m3-s':qmean/year_seconds,'receiver':receiver.reshape(z.shape),'lake-depth':depth,'lake-min-depth':mind,'lake-max-depth':maxd,'lake-occurrence':occ,'soil-water':sw,'groundwater':groundwater,'snow-water':snow,'precipitation':annual_pr,'reference-pet':annual_pet,'history':history,'topology':tp,'convergence':{'passed':stable>=3,'waterYears':cycle+1,'waterCycles':cycle+1,'elapsedEarthYears':(cycle+1)*year_seconds/TIME.EARTH_YEAR_SECONDS,'maximumPeriodicLevelChangeM':level_change,'relativeStorageDrift':drift},'maximumWaterRelativeError':max(r['maxWaterRelativeError'] for r in history),'runoffSource':'local precipitation/snow/soil/groundwater; GCM runoff is not added again','calendar':cal,'units':{'discharge':'m3 per Earth year','discharge-m3-s':'m3 s-1','precipitation':'m per orbital cycle','reference-pet':'m per orbital cycle'},'clock':'physical seconds; orbital seasons independent of Earth civil years'}
