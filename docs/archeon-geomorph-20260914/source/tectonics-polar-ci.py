"""Finite-inventory CI heat/ice experiments on the civil, not geologic, clock.

Enthalpy includes sensible ice/rock heat and latent water heat. Liquid and its
enthalpy move conservatively down actual free-surface gradients. Heat sources
end with the local CI; no perpetual warm spot is retained at Year 521.
"""
import pathlib,sys,importlib,json,math,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('tectonics-continuation');T=C.T;np=T.np
CFG=C.CFG['polarCI'];SECONDS=365.25*86400;YEARS=C.CFG['civilYears']

def activity(year,stop):
 if year<CFG['startCivilYear']:return 0.
 if year<0:return min(1.,(year-CFG['startCivilYear'])/10)
 return max(0.,1-year/stop)

def pick_sites(work,seed,mask=None):
 sites=[];T.MASK=mask
 for i,r in enumerate(C.CFG['polarRegions']):
  folder=work/r['id'];g=json.loads((folder/'grid.json').read_text(encoding='utf8'));z=np.load(folder/str(seed)/'height.npy');kind=np.load(folder/'kind.npy');allow=np.load(folder/'allow.npy');controls=T.weights(r['id'],g)
  gy,gx=np.gradient(z,g['stepM']);coast=T.edt(kind>=30)*g['stepM'];eligible=(allow>.7)&(coast>35000)&(coast<260000)&(z<2400)
  score=controls['ci-placement']*controls['ci-resource']*np.exp(-((coast-95000)/100000)**2)/(.01+np.hypot(gx,gy));score[~eligible]=-1
  if not eligible.any():raise RuntimeError('No eligible polar CI site: '+r['id'])
  rr,cc=np.unravel_index(score.argmax(),z.shape);x=g['xmin']+cc*g['stepM'];y=g['ymax']-rr*g['stepM'];p=T.Proj(g['projection']);lo,la=p(x,y,inverse=True)
  sites.append({'id':'ci-'+r['id'],'region':r['id'],'coordinates':[lo,la],'parentGrid':g,'parentHeightSha256':T.sha(folder/str(seed)/'height.npy'),'communicationLostYear':CFG['communicationLostYears'][i],'heatShutdownYear':CFG['heatShutdownYears'][i],'gasShutdownYear':50,'heatWeight':float(controls['ci-heat'][rr,cc]),'resourceWeight':float(controls['ci-resource'][rr,cc]),'footprintWeight':float(controls['ci-footprint'][rr,cc]),'secondaryCoordinates':[list(p(x+dx,y+dy,inverse=True)) for dx,dy in [(-24000,-12000),(19000,-17000),(-13000,21000),(23000,15000)]],'sitingStatus':'Inferred engineering candidate, within the existing CI node totals. No named story settlement added.'})
 return sites

def move_water(mass,H,bed,dx,dt,latent,rho):
 """A monotone local shallow-storage flux; unopened basins retain water."""
 water=np.minimum(mass,np.maximum(H,0)/latent);surface=bed+(mass-water)/rho+water/1000
 exported_mass=exported_H=0.;through=np.zeros_like(mass)
 for axis in [0,1]:
  aa=[slice(None)]*2;bb=aa.copy();aa[axis]=slice(None,-1);bb[axis]=slice(1,None);a=tuple(aa);b=tuple(bb)
  d=surface[a]-surface[b];wa=water[a];wb=water[b]
  move=np.sign(d)*np.minimum(abs(d)*1000*.24,np.where(d>0,wa,wb)*.22)
  delta=np.zeros_like(mass);delta[a]-=move;delta[b]+=move;mass+=delta;H+=delta*latent;water+=delta;through[a]+=abs(move);through[b]+=abs(move)
 # Regional cells outside this 48 km window receive the exported liquid. It is
 # recorded for civil-time catchment coupling, never teleported to an ocean.
 edge=np.zeros_like(mass,dtype=bool);edge[[0,-1],:]=True;edge[:,[0,-1]]=True
 drain=np.where(edge,np.maximum(0,np.minimum(mass,H/latent))*.4,0);mass-=drain;H-=drain*latent
 return float(drain.sum()*dx*dx),float(drain.sum()*dx*dx*latent),through

def thermal_case(work,site,seed,heat_gw,label):
 parent=work/site['region'];pg=site['parentGrid'];p=T.Proj(pg['projection']);cx,cy=p(*site['coordinates']);dx=2000;n=25
 g={'id':site['id'],'region':site['region'],'width':n,'height':n,'stepM':dx,'xmin':cx-24000,'ymax':cy+24000,'projection':pg['projection']}
 bed=T.sample(np.load(parent/str(seed)/'height.npy'),pg,g).astype(float);xx,yy=T.mesh(g);radius=math.sqrt(CFG['nominalIceAreaKm2']*1e6/math.pi)*math.sqrt(max(.1,site['footprintWeight']))
 shape=np.exp(-((xx-cx)**2/(radius*radius)+(yy-cy-.12*(xx-cx))**2/(radius*radius*.65)));shape/=shape.sum()*dx*dx
 mass=np.full_like(bed,CFG['initialIceThicknessM']*CFG['iceDensityKgM3']);latent=CFG['latentFusionJkg'];rockcap=CFG['heatedRockDepthM']*CFG['rockHeatCapacityJm3K'];H=(mass*CFG['iceHeatCapacityJkgK']+rockcap)*CFG['initialIceTemperatureC'];original_mass=mass.sum()*dx*dx
 initial_H=H.sum()*dx*dx;ledger=[];snapshots={};exports=[];total_in=total_air=total_out=total_water=0.;ice0=mass.copy();thaw=np.zeros_like(bed);out=work/'polar-ci'/str(seed)/site['id']/label;out.mkdir(parents=True,exist_ok=True)
 dt=SECONDS/12;steps=round((521-CFG['startCivilYear'])*12)
 heat=heat_gw*1e9*site['heatWeight'];net=CFG['netElectricalGWPerGroup']*1e9;thermal=net/CFG['conversionEfficiency'];allocated=heat/(1-CFG['activeLossFraction'])
 gasPower=sum(CFG['annualGasKgPerGroup'][k]*CFG['gasSpecificEnergyJkg'][k]/SECONDS for k in CFG['annualGasKgPerGroup'])*site['resourceWeight']
 electric_heat=max(0,allocated-(thermal-net));budget_ok=electric_heat+gasPower<=net
 if not budget_ok:
  T.savejson(out/'result.json',{'status':'failed energy budget','requiredIceAllocationW':allocated,'reactorThermalW':thermal,'electricityForGasW':gasPower,'passed':False});return {'site':site['id'],'case':label,'passed':False,'reason':'energy budget'}
 def save(year):
  water=np.minimum(mass,np.maximum(H,0)/latent);ice=mass-water
  fields={'ice-thickness':ice/CFG['iceDensityKgM3'],'water-depth':water/1000,'enthalpy':H,'bedrock':bed,'frost-thaw':thaw,'surface-height':bed+ice/CFG['iceDensityKgM3']+water/1000}
  for name,a in fields.items():np.save(out/f'{name}-{year}.npy',a.astype('float32'))
  snapshots[year]={'iceVolumeKm3':float(ice.sum()*dx*dx/CFG['iceDensityKgM3']/1e9),'waterVolumeKm3':float(water.sum()*dx*dx/1e12),'activeIceHeatW':heat*activity(year,site['heatShutdownYear']),'activeGasFraction':activity(year,site['gasShutdownYear']) if heat_gw else 0.}
 previousT=np.full_like(bed,-20.)
 for step in range(steps):
  year=CFG['startCivilYear']+step/12;active=activity(year+.5/12,site['heatShutdownYear']) if heat_gw else 0
  Q=heat*active*shape;air=-20+9*math.sin(2*math.pi*(step%12)/12)-.003*(bed-bed.mean())
  cap=mass*CFG['iceHeatCapacityJkgK']+rockcap;k=CFG['thermalConductanceWm2K'];rhs=H+(Q+k*air)*dt;fusion=mass*latent
  newH=np.where(rhs<0,rhs/(1+k*dt/np.maximum(cap,1)),np.where(rhs>fusion,(rhs+k*dt*fusion/np.maximum(rockcap+mass*4180,1))/(1+k*dt/np.maximum(rockcap+mass*4180,1)),rhs))
  temp=np.where(newH<0,newH/np.maximum(cap,1),np.where(newH>fusion,(newH-fusion)/np.maximum(rockcap+mass*4180,1),0))
  airJ=(newH-H-Q*dt).sum()*dx*dx;inputJ=Q.sum()*dt*dx*dx;H=newH
  drained,drainedH,flow=move_water(mass,H,bed,dx,dt,latent,CFG['iceDensityKgM3']);thaw+=((temp>=0)&(previousT<0))|((temp<0)&(previousT>=0));previousT=temp
  total_in+=inputJ;total_air+=airJ;total_out+=drainedH;total_water+=drained
  finalYear=round(year+1/12,8)
  if (step+1)%12==0:
   residual=H.sum()*dx*dx-initial_H-total_in-total_air+total_out;mass_error=mass.sum()*dx*dx+total_water-original_mass
   ledger.append({'year':finalYear,'inputJ':total_in,'airExchangeJ':total_air,'exportedEnthalpyJ':total_out,'enthalpyResidualJ':float(residual),'relativeEnergyError':float(abs(residual)/max(1,abs(total_in)+abs(total_air)+abs(total_out))),'massRelativeError':float(abs(mass_error)/original_mass),'exportedWaterM3':total_water/1000})
   exports.append({'civilYear':finalYear,'waterM3':total_water/1000,'receivingParent':site['region'],'couplingStatus':'boundary export retained for civil-time parent routing; no unvalidated terrain splice'})
  if finalYear in YEARS:save(int(finalYear))
 result={'site':site['id'],'case':label,'effectiveIceHeatGW':heat/1e9,'reactorThermalGW':thermal/1e9,'netElectricalGW':net/1e9,'allocatedHeatGW':allocated/1e9,'electricIceHeatGW':electric_heat/1e9,'gasSynthesisGW':gasPower/1e9,'pipeLossFraction':CFG['activeLossFraction'],'budgetPassed':budget_ok,'snapshots':snapshots,'maxEnergyRelativeError':max(v['relativeEnergyError'] for v in ledger),'maxWaterRelativeError':max(v['massRelativeError'] for v in ledger),'climate':'Assumed -20 C mean plus 9 C annual cycle and local lapse; no real GCM','iceDynamics':'local enthalpy, phase change and conservative shallow storage; no glacier flow','sedimentStatus':'No bedrock incision claimed by this thermal screening solver','shutdownYear':site['heatShutdownYear'],'activeHeatAt521W':0,'activeProductionAt521KgYr':0,'naturalGasReleasedKg':0,'history':ledger}
 result['passed']=result['maxEnergyRelativeError']<1e-8 and result['maxWaterRelativeError']<1e-8 and snapshots[521]['activeIceHeatW']==0
 T.savejson(out/'grid.json',g);T.savejson(out/'result.json',result);T.savejson(out/'parent-water-export.json',exports)
 return {k:v for k,v in result.items() if k!='history'}

def gas_history(work,sites,seed):
 surface=4*math.pi*C.CFG.get('radiusM',4750000)**2;atm=110000*surface/9.610517;mean_molar=.815*.0280134+.185*.031998
 molar={'SF6':.14606,'N2O':.044013};results=[]
 for multiplier in [0,1]:
  for lifetimeScale in CFG['lifetimeSensitivity']:
   stock={k:rate*140*sum(s['resourceWeight'] for s in sites)*multiplier for k,rate in CFG['annualGasKgPerGroup'].items()};initial=stock.copy();mass={k:0. for k in stock};lost=mass.copy();emitted=mass.copy();history=[];snapshots={}
   for y in range(CFG['startCivilYear'],522):
    source={k:sum(rate*activity(y,s['gasShutdownYear'])*s['resourceWeight'] for s in sites)*multiplier for k,rate in CFG['annualGasKgPerGroup'].items()}
    if y in YEARS:snapshots[y]={k:{'massKg':mass[k],'ppb':mass[k]/atm*mean_molar/molar[k]*1e9,'sourceKgYr':source[k]} for k in mass}
    for k in mass:
     add=min(stock[k],source[k]);stock[k]-=add;emitted[k]+=add;tau=CFG['gasLifetimeEarthYears'][k]*lifetimeScale;before=mass[k];mass[k]=mass[k]*math.exp(-1/tau)+add*tau*(1-math.exp(-1/tau));lost[k]+=before+add-mass[k]
    history.append({'year':y,'sourceKgYr':source,'massKg':mass.copy()})
   residual=max(abs(initial[k]-stock[k]-lost[k]-mass[k])/max(1,initial[k]) for k in mass)
   results.append({'engineeringEnabled':bool(multiplier),'lifetimeScale':lifetimeScale,'lifetimeStatus':'Earth reference only; Archeon photochemistry and Sky Fire uncertainty unresolved','initialStockKg':initial,'remainingStockKg':stock,'emittedKg':emitted,'destroyedKg':lost,'massRelativeError':residual,'snapshots':snapshots,'history':history,'passed':residual<1e-8 and all(v['sourceKgYr']==0 for v in snapshots[521].values()),'forcingWm2':None,'radiationStatus':'No GWP or CO2 equivalence used. Actual spectral transfer still required.'})
 T.savejson(work/'polar-ci'/str(seed)/'gas-history.json',results);return [{k:v for k,v in r.items() if k!='history'} for r in results]

def run(work,seed=5210914,mask=None):
 T.WORK=work;T.MASK=mask;sites=pick_sites(work,seed,mask);out=work/'polar-ci'/str(seed);T.savejson(out/'sites.json',sites);cases=[]
 for site in sites:
  for heat in [0]+CFG['usefulIceHeatGW']:
   label='no-engineering' if heat==0 else f'heat-{heat:g}GW';cases.append(thermal_case(work,site,seed,heat,label));T.log('CI '+site['id']+' '+label)
 gas=gas_history(work,sites,seed);report={'seed':seed,'cases':cases,'gases':gas,'primaryGroups':6,'secondarySites':24,'netElectricAllocationGW':18,'countedWithinExistingTotals':True,'passed':all(v['passed'] for v in cases+gas),'scope':'Civil-time local thermal and finite-gas inventory screening; not equilibrated climate or full glacier erosion'};T.savejson(out/'summary.json',report);return report
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=C.DEFAULT);ap.add_argument('--seed',type=int,default=5210914);ap.add_argument('--mask',type=pathlib.Path);a=ap.parse_args();C.open_work(a.work,a.mask);run(a.work,a.seed,a.mask)
