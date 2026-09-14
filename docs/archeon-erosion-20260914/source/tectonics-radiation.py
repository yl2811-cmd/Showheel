"""Trace-gas spectral column interface with explicit measurement/coverage gates.

This is a thermal-IR LTE absorption/emission column, not a GCM or atmospheric
chemistry solver. Synthetic tests are labelled tests, never planetary results.
No CO2-equivalent or GWP conversion is used.
"""
import pathlib,sys,importlib,json,math,argparse,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('tectonics-continuation');T=C.T;np=T.np
from scipy.interpolate import LinearNDInterpolator
H=6.62607015e-34;LIGHT=299792458.;KB=1.380649e-23;NA=6.02214076e23;GRAVITY=9.610517;CP=1004.

def planck(wn,temperature):
 nu=np.asarray(wn)*100;exponent=np.clip(H*LIGHT*nu/(KB*np.asarray(temperature)[...,None]),1e-10,700)
 return 2*H*LIGHT**2*nu**3/np.expm1(exponent)*100

def flux_column(wn,temperature,tsurface,tau,dp):
 tau=np.asarray(tau,dtype=float);temperature=np.asarray(temperature);n=len(temperature)
 if tau.shape!=(n,len(wn)) or np.any(tau<0) or not np.isfinite(tau).all():raise ValueError('Invalid optical depths')
 if np.any(np.asarray(dp)<=0):raise ValueError('Layer pressure thickness must be positive')
 # Two-point Gaussian quadrature over a hemisphere. Arrays run surface to top.
 up=np.zeros((n+1,len(wn)));down=np.zeros_like(up);source=planck(wn,temperature);surface=planck(wn,tsurface)
 for mu,w in [(0.2113248654051871,.5),(.7886751345948129,.5)]:
  trans=np.exp(-tau/mu);a=surface.copy();u=[a.copy()]
  for i in range(n):a=a*trans[i]+source[i]*(1-trans[i]);u.append(a.copy())
  a=np.zeros_like(surface);d=[None]*(n+1);d[n]=a.copy()
  for i in range(n-1,-1,-1):a=a*trans[i]+source[i]*(1-trans[i]);d[i]=a.copy()
  up+=2*np.pi*w*mu*np.asarray(u);down+=2*np.pi*w*mu*np.asarray(d)
 Fup=np.trapezoid(up,wn,axis=1);Fdown=np.trapezoid(down,wn,axis=1);net=Fup-Fdown;heating=(net[:-1]-net[1:])*GRAVITY/(np.asarray(dp)*CP)
 return {'upWm2':Fup,'downWm2':Fdown,'heatingKsec':heating,'budgetResidualWm2':float((heating*np.asarray(dp)*CP/GRAVITY).sum()-(net[0]-net[-1]))}

def read_xsc(path):
 """Read one measured HITRAN block. cm²/molecule -> m²/molecule."""
 lines=path.read_text(encoding='ascii').splitlines();line=lines[0]
 species=line[:20].strip();lo=float(line[20:30]);hi=float(line[30:40]);count=int(line[40:47]);temperature=float(line[47:54]);pressure=float(line[54:60])*101325/760
 sigma=np.fromstring(' '.join(lines[1:]).replace('D','E'),sep=' ')
 if len(sigma)!=count or not np.isfinite(sigma).all() or np.min(sigma)<0:raise ValueError('Invalid measured XSC block '+str(path))
 return {'species':species,'temperatureK':temperature,'pressurePa':pressure,'wavenumberCm1':np.linspace(lo,hi,count),'sigmaM2':sigma*1e-4,'sha256':T.sha(path)}

def measured_table(index_path,wn,temperature,pressure):
 index=json.loads(index_path.read_text(encoding='utf8'));required=['SF6','N2O','H2O','CO2','O3'];result={};records={}
 if index.get('scope')!='validated thermal IR with continuum':raise ValueError('Spectral coverage and continuum have not been validated')
 for gas in required:
  entries=index.get('species',{}).get(gas,[])
  if not entries:raise ValueError('Missing measured absorber '+gas)
  points=[];values=[];hashes=[]
  for e in entries:
   p=(index_path.parent/e['file']).resolve()
   if not p.is_relative_to(index_path.parent.resolve()):raise ValueError('Spectrum outside input directory')
   if T.sha(p)!=e['sha256']:raise ValueError('Spectrum fingerprint mismatch')
   # Preprocessed arrays must retain links to the original measured XSC/line
   # records, broadening and continuum provenance in the index.
   a=np.load(p)
   if not e.get('measurementSource') or not e.get('units')=='m2/molecule':raise ValueError('Unattributed or unitless spectrum')
   if a['wavenumberCm1'][0]>wn[0] or a['wavenumberCm1'][-1]<wn[-1]:raise ValueError('Incomplete spectral window '+gas)
   for i,(temp,press) in enumerate(zip(a['temperatureK'],a['pressurePa'])):
    points.append([float(temp),math.log(float(press))]);values.append(np.interp(wn,a['wavenumberCm1'],a['sigmaM2'][i]))
   hashes.append(e['sha256'])
  sigma=LinearNDInterpolator(np.asarray(points),np.asarray(values))(np.column_stack([temperature,np.log(pressure)]))
  if not np.isfinite(sigma).all() or np.any(sigma<0):raise ValueError('Requested T/P lies outside measured interpolation support: '+gas)
  result[gas]=sigma;records[gas]=hashes
 return result,records

def delta_column(wn,temperature,tsurface,pressure_edges,abundance,cross_sections):
 dp=-np.diff(pressure_edges);pressure=np.sqrt(np.asarray(pressure_edges[:-1])*np.asarray(pressure_edges[1:]));mean_molecule=(.815*.0280134+.185*.031998)/NA;number=dp/(GRAVITY*mean_molecule)
 tau={gas:sigma*np.broadcast_to(np.asarray(abundance.get(gas,0)),len(dp))[:,None]*number[:,None] for gas,sigma in cross_sections.items()}
 base=sum(v for k,v in tau.items() if k not in ['SF6','N2O']);trace=tau['SF6']+tau['N2O'];before=flux_column(wn,temperature,tsurface,base,dp);after=flux_column(wn,temperature,tsurface,base+trace,dp)
 return {k:after[k]-before[k] for k in ['upWm2','downWm2','heatingKsec']},max(abs(after['budgetResidualWm2']),abs(before['budgetResidualWm2']))

def tests():
 wn=np.linspace(.1,6000,30000);temps=np.array([280.,260.,230.,210.]);dp=np.array([35000.,30000.,25000.,19000.]);zero=np.zeros((4,len(wn)));transparent=flux_column(wn,temps,288.,zero,dp);blackbody=5.670374419e-8*288**4
 gray=np.full_like(zero,.3);isothermal=flux_column(wn,np.full(4,288.),288.,gray,dp);opaque=flux_column(wn,temps,288.,gray,dp)
 a=flux_column(wn,temps,288.,gray+gray,dp);b=flux_column(wn,temps,288.,gray,dp);c=flux_column(wn,temps,288.,zero,dp)
 r={'transparentRelativeBlackbodyError':abs(transparent['upWm2'][-1]-blackbody)/blackbody,'transparentDownWm2':float(abs(transparent['downWm2']).max()),'isothermalUpFluxSpreadWm2':float(np.ptp(isothermal['upWm2'])),'energyResidualWm2':abs(opaque['budgetResidualWm2']),'overlapDiffersFromAddingIndependentForcingsWm2':float(abs((a['upWm2'][-1]-c['upWm2'][-1])-2*(b['upWm2'][-1]-c['upWm2'][-1]))),'scope':'Analytic/synthetic solver checks only; no measured gas data or planetary climate asserted'}
 r['passed']=r['transparentRelativeBlackbodyError']<1e-6 and r['transparentDownWm2']==0 and r['isothermalUpFluxSpreadWm2']<1e-10 and r['energyResidualWm2']<1e-10 and r['overlapDiffersFromAddingIndependentForcingsWm2']>1
 return r

def run(work):
 out=work/'radiation';out.mkdir(parents=True,exist_ok=True);test=tests();T.savejson(out/'solver-checks.json',test);index=out/'spectra/index.json';missing=not index.exists()
 report={'status':'needs measured spectral inputs' if missing else 'measurement index present; validation required','solverTestsPassed':test['passed'],'measuredCalibrationPassed':False,'gcmBridgeValidated':False,'allowPlanetaryClimateClaim':False,'requires':['Measured SF6/N2O and background H2O/CO2/O3 absorption including spectral overlap/continuum','T/P support covering requested atmosphere; no silent extrapolation','Compiled ExoPlaSim flux/heating interface and zero-gas regression','Actual Linux GCM run and energy balance'],'observedDataAccess':{'provider':'HITRANonline','url':'https://hitran.org/xsc/','selectedRecords':[2151,2141,2140],'result':'Browser redirected to account login on Get data. No credentials supplied and no access bypass attempted.'},'runtime':'WSL2 --status confirms virtualization not active; prior VirtualMachinePlatform enabling awaits system restart','GWPUsed':False,'CO2EquivalentUsed':False}
 if not missing:
  wn=np.linspace(100,2500,4801);edges=np.geomspace(110000,1000,21);pressure=np.sqrt(edges[:-1]*edges[1:]);temperature=np.linspace(280,200,20);cross,provenance=measured_table(index,wn,temperature,pressure)
  delta,residual=delta_column(wn,temperature,285.,edges,{'SF6':1e-9,'N2O':3e-7,'CO2':.001,'O3':1e-7,'H2O':np.geomspace(.01,1e-5,20)},cross);np.savez(out/'column-increment.npz',pressureEdgesPa=edges,temperatureK=temperature,**delta);report.update(status='measured column evaluated; GCM bridge pending',measuredCalibrationPassed=residual<1e-8,sourceFingerprints=provenance)
 T.savejson(out/'status.json',report);T.log('RADIATION '+report['status']);return report
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=C.DEFAULT);a=ap.parse_args();run(a.work)
