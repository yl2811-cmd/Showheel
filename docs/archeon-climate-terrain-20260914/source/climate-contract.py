"""Engine-independent climate provenance, SI units and readiness checks."""
import pathlib,sys,importlib,json
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;TIME=importlib.import_module('climate-time')
SURFACE_UNITS={'tas':'K','pr':'m s-1','prsn':'m s-1','evap':'m s-1','uas':'m s-1','vas':'m s-1','ps':'Pa','rss':'W m-2','rlds':'W m-2','rlus':'W m-2','mrso':'m','snd':'m','mrro':'m s-1','hur':'1'}
PROFILE_UNITS={'ta':'K','ua':'m s-1','va':'m s-1','hus':'kg kg-1','wap':'Pa s-1','pressure':'Pa'}
CLOUD_UNITS={'clt':'1','cll':'1','clm':'1','clh':'1','lwp':'kg m-2','iwp':'kg m-2','cloud_top_height':'m','cloud_sw_effect':'W m-2','cloud_lw_effect':'W m-2'}

def balance(history,config=None,calendar=None,target_c=None):
 cfg=config or C.CFG['climate'];width=cfg['balanceWindowYears']*TIME.EARTH_YEAR_SECONDS;n=cfg['consecutiveBalanceWindows'];issues=[];windows=[]
 if not history:return {'passed':False,'issues':['no climate history'],'windows':[]}
 try:bounds=TIME.history_bounds(history,calendar)
 except ValueError as e:return {'passed':False,'issues':[str(e)],'windows':[]}
 end=bounds[-1,1];start=end-n*width
 if bounds[0,0]>start+1e-5:return {'passed':False,'issues':['fewer than '+str(n*cfg['balanceWindowYears'])+' physical Earth years'],'windows':[]}
 mid=bounds.mean(axis=1)/TIME.EARTH_YEAR_SECONDS
 for part in range(n):
  lo=start+part*width;hi=lo+width;weight=np.maximum(0,np.minimum(bounds[:,1],hi)-np.maximum(bounds[:,0],lo));use=weight>0;w=weight[use];y=mid[use];rows=[r for r,take in zip(history,use) if take]
  get=lambda k:np.asarray([r.get(k,np.nan) for r in rows],float)
  temp=get('areaWeightedTemperatureK');ice=get('seaIceAreaFraction');rain=get('landPrecipitationMyr');toa=get('toaNetWm2');surf=get('surfaceNetWm2');water=get('waterBudgetFraction')
  if len(rows)<2 or not np.isfinite(np.r_[temp,ice,rain,toa,surf,water]).all():issues.append('missing/nonfinite balance diagnostic');continue
  average=lambda a:float(np.average(a,weights=w))
  trend=float(np.polyfit(y,temp,1,w=np.sqrt(w))[0]);ice_trend=float(np.polyfit(y,ice,1,w=np.sqrt(w))[0])
  edge=5*TIME.EARTH_YEAR_SECONDS;first=np.maximum(0,np.minimum(bounds[use,1],lo+edge)-np.maximum(bounds[use,0],lo));last=np.maximum(0,np.minimum(bounds[use,1],hi)-np.maximum(bounds[use,0],hi-edge))
  rain_drift=abs(float(np.average(rain,weights=last)-np.average(rain,weights=first)))/max(.01,average(rain))
  checks={'timeStartSeconds':lo,'timeEndSeconds':hi,'meanTemperatureC':average(temp)-273.15,'toaNetWm2':average(toa),'surfaceNetWm2':average(surf),'temperatureTrendKyr':trend,'seaIceTrendFractionYr':ice_trend,'maximumWaterBudgetFraction':float(abs(water).max()),'regionalPrecipitationDriftFraction':max(rain_drift,max(float(r.get('maximumRegionalPrecipitationDriftFraction',float('inf'))) for r in rows))}
  checks['passed']=abs(checks['toaNetWm2'])<cfg['maximumTOAImbalanceWm2'] and abs(checks['surfaceNetWm2'])<cfg['maximumSurfaceImbalanceWm2'] and abs(trend)<cfg['maximumTemperatureTrendKyr'] and abs(ice_trend)<cfg['maximumSeaIceTrendFractionYr'] and checks['maximumWaterBudgetFraction']<cfg['maximumWaterBudgetFraction'] and checks['regionalPrecipitationDriftFraction']<cfg['maximumRegionalPrecipitationDriftFraction']
  if target_c is not None:checks['targetTemperaturePassed']=bool(target_c[0]<=checks['meanTemperatureC']<=target_c[1]);checks['passed']&=checks['targetTemperaturePassed']
  windows.append(checks)
 return {'passed':not issues and len(windows)==n and all(w['passed'] for w in windows),'issues':issues,'windows':windows,'trendUnit':'per Earth year','weighting':'physical interval overlap, not count of orbital cycles'}

def validate(folder,require_ready=True):
 folder=pathlib.Path(folder);result=C.read(folder/'result.json');request=C.read(folder/'request.json');errors=[]
 if result.get('status')!='complete' or result.get('synthetic') or result.get('benchmark'):errors.append('not a completed planetary circulation result')
 try:
  if result.get('requestFingerprint')!=C.request_fingerprint(request):errors.append('request fingerprint mismatch')
 except ValueError as e:errors.append(str(e))
 file=folder/'climate.npz'
 if not file.exists() or C.sha(file)!=result.get('climateSha256'):errors.append('climate file missing or changed')
 radiation=result.get('radiationValidation',{})
 if not radiation.get('passed') or not set(C.CFG['climate']['requiredRadiativeSpecies']).issubset(radiation.get('validatedSpecies',[])):errors.append('required atmospheric absorbers not validated')
 for key in ['sourceHashes','spectralHashes','columnComparison','gcmTransferCheck']:
  if not radiation.get(key):errors.append('radiation evidence missing: '+key)
 if result.get('terrainFingerprint')!=request.get('terrainFingerprint'):errors.append('terrain lineage mismatch')
 try:
  cal=TIME.calendar(result.get('calendar'));requested_cal=TIME.calendar(request.get('calendar'))
  if cal!=requested_cal:errors.append('result calendar differs from requested orbit')
 except ValueError as e:errors.append(str(e));cal=TIME.calendar()
 units=result.get('units',{})
 for field,unit in {**SURFACE_UNITS,**PROFILE_UNITS}.items():
  if units.get(field)!=unit:errors.append('missing or wrong SI unit: '+field)
 cloud_required=bool(request.get('cloudValidationRequired'))
 if cloud_required:
  for field,unit in CLOUD_UNITS.items():
   if units.get(field)!=unit:errors.append('missing or wrong cloud unit: '+field)
  cloud_check=result.get('cloudSeasonalConvergence',{})
  if not cloud_check.get('passed') or cloud_check.get('maximumAbsoluteFractionDrift',float('inf'))>.03:errors.append('cloud seasonal stability not demonstrated')
  if not result.get('orbitalSeasonalConvergence',{}).get('passed'):errors.append('orbital seasonal stability not demonstrated')
 diagnostics=balance(result.get('history',[]),calendar=cal,target_c=request.get('target',{}).get('globalNearSurfaceTemperatureC'))
 if not diagnostics['passed']:errors.append('climate seasonal/energy/water balance not established')
 if file.exists():
  with np.load(file,allow_pickle=False) as data:
   missing=set(SURFACE_UNITS)|set(PROFILE_UNITS)|{'latitude','longitude','time_bounds_seconds'}
   if cloud_required:missing|=set(CLOUD_UNITS)
   missing-=set(data.files)
   if missing:errors.append('missing arrays: '+','.join(sorted(missing)))
   for key in set(data.files)&(set(SURFACE_UNITS)|set(PROFILE_UNITS)):
    if not np.isfinite(data[key]).all():errors.append('nonfinite values: '+key)
   if 'hur' in data and (np.min(data['hur'])<0 or np.max(data['hur'])>1.000001):errors.append('relative humidity is not fractional; a misleading unit label cannot substitute for conversion')
   if 'ps' in data and np.min(data['ps'])<=0:errors.append('nonpositive surface pressure')
   if 'pr' in data and np.min(data['pr'])<0:errors.append('negative precipitation')
   if 'prsn' in data and 'pr' in data and np.max(data['prsn']-data['pr'])>1e-10:errors.append('snowfall exceeds total precipitation')
   if cloud_required:
    for name in set(CLOUD_UNITS)&set(data.files):
     a=data[name]
     if not np.isfinite(a).all():errors.append('nonfinite cloud values: '+name)
     if name in ['clt','cll','clm','clh'] and (np.min(a)<0 or np.max(a)>1):errors.append('cloud cover outside 0-1: '+name)
     if name in ['lwp','iwp','cloud_top_height'] and np.min(a)<0:errors.append('negative physical cloud property: '+name)
   if 'time_bounds_seconds' in data:
    try:TIME.interval_check(data['time_bounds_seconds'],cal)
    except ValueError as e:errors.append(str(e))
 if require_ready:
  if not result.get('terrainAccepted') or not result.get('hydrologyAccepted'):errors.append('terrain and hydrology acceptance incomplete')
 if errors:raise ValueError('; '.join(errors))
 return request,result

def pet(tas,humidity,wind,pressure,net_radiation,soil_heat=0.):
 """Penman-Monteith reference demand in metres per physical second.

 The reference resistance is explicit; this is not a vegetation prediction.
 No Earth 24-hour coefficient is used.
 """
 tc=np.asarray(tas)-273.15;rh=np.clip(humidity,0,1);u=np.maximum(wind,.05)
 es=610.8*np.exp(17.27*tc/(tc+237.3));delta=4098*es/(tc+237.3)**2
 latent=np.maximum(2e6,2.501e6-2361*tc);cp=1004.;gascon=287.;rho=np.asarray(pressure)/(gascon*np.asarray(tas));gamma=cp*np.asarray(pressure)/(.622*latent)
 ra=208./u;rs=70.;flux=(delta*(np.asarray(net_radiation)-soil_heat)+rho*cp*es*(1-rh)/ra)/(delta+gamma*(1+rs/ra))
 return np.maximum(0,flux)/(latent*1000)

def dry_fields(precip,pet_rate,durations,temperature,snow):
 dt=np.asarray(durations).reshape((-1,)+(1,)*(np.ndim(precip)-1));p=(np.maximum(precip,0)*dt).sum(axis=0);e=(np.maximum(pet_rate,0)*dt).sum(axis=0)
 ratio=np.divide(p,e,out=np.full_like(p,np.nan),where=e>1e-5);ice=((np.asarray(temperature)*dt).sum(axis=0)/dt.sum()<263.15)&((np.asarray(snow)*dt).sum(axis=0)/dt.sum()>.1)
 cls=np.full(p.shape,5,np.uint8);cls[ratio<.65]=4;cls[ratio<.5]=3;cls[ratio<.2]=2;cls[ratio<.05]=1;cls[ice|~np.isfinite(ratio)]=0
 return {'annualPrecipitationM':p,'annualReferencePETM':e,'aridityPOverPET':ratio,'aridityClass':cls,'waterDeficitSeconds':((precip<pet_rate)*dt).sum(axis=0),'iceOrNoPET':ice|~np.isfinite(ratio)}
