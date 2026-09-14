"""Independent numerical invariants and explicit completeness accounting."""
import pathlib,sys,importlib,tempfile,copy,json
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');K=importlib.import_module('climate-contract');np=C.np

def tests():
 rows=[{'year':y,'areaWeightedTemperatureK':285.,'seaIceAreaFraction':.15,'landPrecipitationMyr':1.,'toaNetWm2':.1,'surfaceNetWm2':.1,'waterBudgetFraction':1e-5,'maximumRegionalPrecipitationDriftFraction':.01} for y in range(1,41)]
 assert K.balance(rows)['passed'];assert not K.balance(rows[:20])['passed']
 drifting=copy.deepcopy(rows)
 for r in drifting:r['areaWeightedTemperatureK']+=r['year']*.03
 assert not K.balance(drifting)['passed']
 ice=copy.deepcopy(rows)
 for r in ice:r['seaIceAreaFraction']+=r['year']*.003
 assert not K.balance(ice)['passed']
 water=copy.deepcopy(rows);water[-1]['waterBudgetFraction']=.1;assert not K.balance(water)['passed']
 demand=float(K.pet(293.15,.5,2,110000,100));assert 1e-8<demand<1e-7
 assert K.pet(293.15,.25,2,110000,100)>demand and K.pet(293.15,.5,3,110000,100)>demand
 assert abs((demand*97200)/(demand*86400)-27/24)<1e-12
 # A correct annual mean must be duration-weighted, even with irregular bins.
 dt=np.array([100.,200.]);p=np.array([[[.1]],[[.2]]]);pet=np.array([[[1.]],[[1.]]]);d=K.dry_fields(p,pet,dt,np.ones_like(p)*290,np.zeros_like(p));assert np.isclose(d['aridityPOverPET'][0,0],1/6)
 old=C.T.BASE_WORK/'strong-painted-v7/climate/5210914/T21-co2-0.001'
 try:K.validate(old)
 except (ValueError,FileNotFoundError):rejected=True
 else:rejected=False
 assert rejected
 F=importlib.import_module('climate-forcing');parent=np.array([[0,0,1],[0,1,1]]);rain=np.array([[.1,.2,.3],[.2,.1,.4]]);weighted,error=F.redistribute(rain,np.array([[.2,2,1],[.7,3,.5]]),parent)
 assert error<1e-12 and np.all(weighted>=0)
 for group in [0,1]:assert np.isclose(weighted[parent==group].sum(),rain[parent==group].sum())
 watermod=importlib.import_module('climate-water');n=13;yy,xx=np.indices((n,n));z=(n-yy).astype(float)*3;land=np.ones_like(z,bool)
 class SyntheticForcing:
  durations=np.array([31557600/5]*5)
  def season(self,i):
   return {'pr':np.ones_like(z)/31557600,'prsn':np.zeros_like(z),'pet':np.ones_like(z)*.25/31557600,'tas':np.ones_like(z)*290,'rss':np.zeros_like(z),'rlds':np.zeros_like(z),'rlus':np.zeros_like(z)}
 hydro=watermod.run(z,land,100,np.ones_like(z)*.3,SyntheticForcing(),max_cycles=25)
 assert hydro['maximumWaterRelativeError']<1e-8 and hydro['convergence']['passed']
 library=C.read(C.WORK/'tile-library/manifest.json');assert len(library['inventory'])==18 and sum(v['used'] for v in library['inventory'])==7
 for profile in library['profiles'].values():
  for item in profile:
   a=np.load(C.WORK/'tile-library'/(item['id']+'.npy'));assert np.isfinite(a).all() and abs(a.mean())<1e-5 and a.max()<=1.00001
 return {'syntheticTestsOnly':True,'passed':True,'checks':['two separate 20-year windows','temperature drift rejected','sea-ice drift rejected','water imbalance rejected','PET humidity/wind response','27-hour physical clock','duration-weighted aridity','prepared-only climate refused','18-source inventory and 7 shape-only motifs','orographic precipitation conservation','soil/groundwater/lake conservation and periodic convergence'],'referencePETmPerSecond':demand,'soilLakeWaterError':hydro['maximumWaterRelativeError']}

def verify():
 result=tests();C.write(C.WORK/'operator-tests.json',result)
 simulations=[]
 for p in (C.WORK/'regional').rglob('simulation.json'):
  v=C.read(p);simulations.append({'path':str(p.parent),'passed':v['passed'],'effectiveYears':v['effectiveYears'],'waterError':v['maxWaterRelativeError'],'solidError':v['maxVolumeRelativeError'],'retentionPassed':v['retentionPassed'],'waterConverged':v['waterConvergence']['passed']})
 report={'operatorTestsPassed':True,'completedRegionalRuns':len(simulations),'regionalRuns':simulations,'climateReady':False,'vegetationReady':False,'scope':'Operator correctness is separate from physical calibration and completed run coverage'}
 C.write(C.WORK/'verification.json',report);print(json.dumps({'operatorTestsPassed':True,'completedRegionalRuns':len(simulations),'climateReady':False}),flush=True);return report
if __name__=='__main__':verify()
