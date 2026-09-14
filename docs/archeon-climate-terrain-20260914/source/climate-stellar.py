"""Coupled stellar/Kepler and finite residual-gas screening, not a climate fit."""
import pathlib,sys,importlib,math
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np

def run():
 astronomy=C.read(C.ROOT/'data/astronomy.json');node=next(n for n in astronomy['nodes'] if n['id']=='archeon');star=node['hostStar'];year=C.CFG['climate']['yearSeconds'];G=6.67430e-11;Msun=1.98847e30;AU=149597870700.;sigma=5.670374419e-8;Rsun=695700000.;Lsun=3.828e26
 orbit=(G*(star['massSolar']*Msun+3.25e24)*year**2/(4*np.pi**2))**(1/3);lum=4*np.pi*(star['radiusSolar']*Rsun)**2*sigma*star['temperatureK']**4;flux=lum/(4*np.pi*orbit**2)
 inventory=C.read(C.ROOT/'data/tectonics-continuation.json')['polarCI'];atmos_mass=4*np.pi*4750000**2*110000/9.610517;species={}
 for gas,molar_mass in [('SF6',.146055),('N2O',.044013)]:
  rate=inventory['annualGasKgPerGroup'][gas]*inventory['primaryGroups'];lifetime=inventory['gasLifetimeEarthYears'][gas];start=inventory['startCivilYear'];stop=inventory['gasShutdownYear'];now=521
  rows=[]
  for factor in inventory['lifetimeSensitivity']:
   tau=lifetime*factor;shutdown=rate*tau*(1-math.exp(-(stop-start)/tau));mass=shutdown*math.exp(-(now-stop)/tau)
   vmr=mass/molar_mass/(atmos_mass/.02875);rows.append({'lifetimeEarthYears':tau,'massKg':mass,'moleFraction':vmr,'ppbv':vmr*1e9})
  species[gas]={'history':'existing six polar groups only; not a complete historical planetary gas inventory','scenarios':rows}
 out={'status':'physically linked current working values and finite-gas inventory; radiative fit pending','stellarMassSolar':star['massSolar'],'stellarRadiusSolar':star['radiusSolar'],'temperatureK':star['temperatureK'],'luminositySolar':lum/Lsun,'orbitAU':orbit/AU,'periodSeconds':year,'fluxWm2':flux,'earthFluxFraction':flux/1361,'solarDaySeconds':97200,'siderealDaySeconds':1/(1/97200+1/year),'residualGases':species,'missingForCalibration':['Complete Phase A global injected inventories, beyond the six polar-group screening assumptions','Measured SF6/N2O spectral coverage and GCM transfer validation','Stellar-evolution-consistent K2V alternatives; varying mass, radius and temperature independently is forbidden'],'co2EquivalentUsed':False,'activeCIHeatingAtYear521':False,'sourceHashes':{'astronomy':C.sha(C.ROOT/'data/astronomy.json'),'inventory':C.sha(C.ROOT/'data/tectonics-continuation.json')}}
 C.write(C.WORK/'climate-inputs/stellar-gas-audit.json',out);print('WORKING STAR',round(flux,3),'W/m2; trace-gas quantities are screening priors',flush=True)
 return out
if __name__=='__main__':run()
