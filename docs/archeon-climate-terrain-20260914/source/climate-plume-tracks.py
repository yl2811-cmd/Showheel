"""Moving hotspot footprints with finite supply, cooling and elastic loading.

Surface response hypotheses, not mantle convection. Twenty-four Myr source
ages prescribe the construction/cooling history; post-emplacement erosion has
its own effective clock. No claim of having simulated that older erosion.
"""
import pathlib,sys,importlib,argparse,time,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent))
P=importlib.import_module('climate-vorhan-plumes');C=P.C;T=P.T;np=P.np;L=P.L;D=P.D
C.WORK=C.TASK/'plume-tracks-v16'
from scipy.fft import rfft2,irfft2,rfftfreq,fftfreq
from scipy.ndimage import distance_transform_edt,label
CONFIG=C.ROOT/'data/plume-track-candidates.json'

def sources():return C.read(CONFIG)['sources']

def construction(g,seed=5210914,gain=1.):
 xx,yy=T.mesh(g);shape=xx.shape;fields={k:np.zeros(shape) for k in ['underplating-thickness','isostatic-uplift','thermal-support','basalt-thickness','load-subsidence','fault-displacement']};catalog=[];records=[]
 rho_m=3300.;rho_c=2900.;rho_b=2950.;gravity=C.CFG['climate']['gravityMs2'];E=70e9;Te=35000.;nu=.25;rigidity=E*Te**3/(12*(1-nu**2))
 for number,s in enumerate(sources()):
  xy=np.asarray([T.Proj(g['projection'])(*q) for q in s['coordinates']]);segment=np.linalg.norm(np.diff(xy,axis=0),axis=1);arc=np.r_[0,np.cumsum(segment)];length=arc[-1];times=np.linspace(0,length,s['sourceCount']);cx=np.interp(times,arc,xy[:,0]);cy=np.interp(times,arc,xy[:,1]);ages=np.linspace(s['durationMyr'],0,s['sourceCount']);rng=np.random.default_rng(seed+7181+number*991)
  root=np.zeros(shape);heat=np.zeros(shape);basalt=np.zeros(shape);fault=np.zeros(shape);episode=[];activity=np.zeros(shape)
  for j,(x,y,age) in enumerate(zip(cx,cy,ages)):
   theta=np.arctan2(cy[min(j+1,len(cy)-1)]-cy[max(j-1,0)],cx[min(j+1,len(cx)-1)]-cx[max(j-1,0)]);u=(xx-x)*np.cos(theta)+(yy-y)*np.sin(theta);v=-(xx-x)*np.sin(theta)+(yy-y)*np.cos(theta);v-=18000*np.sin(u/97000+.4*j)
   a=u/(s['kernelLengthKm']*500);b=v/(s['kernelWidthKm']*500);r=a*a+b*b;footprint=1-T.ease((r-.12)/.88)
   budget=(.88+.24*rng.random())*gain
   # Finite magma supply per episode. Increasing occupied area is an explicit
   # additional volume, not an unbounded height recurrence at one cell.
   underplate=3600*budget*footprint;sheet=900*budget*(1-T.ease((r-.18)/.66))*(.86+.14*T.ease((b+.5)/1.2));root+=underplate;basalt+=sheet
   residence=s['durationMyr']/(s['sourceCount']-1)
   heat+=620*budget*(1-np.exp(-residence/5.0))*np.exp(-age/5.0)*footprint
   step=(.5+.5*np.tanh((b+.12)/.075))*(1-.24*T.ease((b+.1)/.8));local_fault=1150*budget*footprint*step*(.85+.15*np.cos(a*3+j)**2);fault=np.maximum(fault,local_fault);activity=np.maximum(activity,footprint)
   episode.append({'index':j,'center':list(T.Proj(g['projection'])(x,y,inverse=True)),'ageMyr':float(age),'underplatePeakThicknessM':3600*budget,'basaltPeakThicknessM':900*budget,'thermalDecayMyr':5.,'thermalResidenceMyr':residence,'underplateVolumeKm3':float(underplate.sum()*g['stepM']**2/1e9),'basaltVolumeKm3':float(sheet.sum()*g['stepM']**2/1e9)})
   catalog.append({'id':s['id']+'-episode-'+str(j),'province':s['id'],'family':'tilted','process':'post-emplacement-normal-fault','xy':[float(x),float(y)],'center':episode[-1]['center'],'lengthM':s['kernelLengthKm']*380,'widthM':s['kernelWidthKm']*140,'reliefM':220*gain,'angleRadians':float(theta),'phase':float(j*.4),'startYear':int(j*160000),'durationYears':400000,'initialFraction':0.})
  # Airy support of added lower crust. Local upper-mantle density is an
  # explicit assumption, distinct from the planet's compressed mean mantle.
  uplift=root*(rho_m-rho_c)/rho_m
  # D nabla^4 w + rho_m*g*w = rho_b*g*basalt. Zero-padded, not periodic
  # continental loading. g changes stiffness relative to buoyancy, not a cap.
  pad=(shape[0],shape[1]);load=np.pad(rho_b*gravity*basalt,((pad[0]//2,pad[0]-pad[0]//2),(pad[1]//2,pad[1]-pad[1]//2)))
  ky=2*np.pi*fftfreq(load.shape[0],g['stepM'])[:,None];kx=2*np.pi*rfftfreq(load.shape[1],g['stepM'])[None,:];k2=ky*ky+kx*kx
  spectrum=rfft2(load);denominator=rigidity*k2*k2+rho_m*gravity;deflection=irfft2(spectrum/denominator,s=load.shape)
  subsidence=deflection[pad[0]//2:pad[0]//2+shape[0],pad[1]//2:pad[1]//2+shape[1]]
  fields['underplating-thickness']+=root;fields['isostatic-uplift']+=uplift;fields['thermal-support']+=heat;fields['basalt-thickness']+=basalt;fields['load-subsidence']+=subsidence;fields['fault-displacement']+=fault
  height=uplift+heat+basalt-subsidence+fault
  records.append({**s,'episodes':episode,'actualPathLengthKm':float(length/1000),'actualRelativeSpeedCmYr':float(length/1000/s['durationMyr']/10),'maximumRootAdditionM':float(root.max()),'maximumBasaltM':float(basalt.max()),'maximumAddedHeightM':float(height.max()),'maximumLoadSubsidenceM':float(subsidence.max()),'sourceInsideTaskGridMagmaVolumeKm3':float((root+basalt).sum()*g['stepM']**2/1e9),'pastErosionSimulated':False})
 response={k:v for k,v in fields.items() if k!='underplating-thickness'}
 total=fields['isostatic-uplift']+fields['thermal-support']+fields['basalt-thickness']-fields['load-subsidence']+fields['fault-displacement']
 physics={'gravityMs2':gravity,'upperMantleDensityKgM3':rho_m,'addedCrustDensityKgM3':rho_c,'basaltDensityKgM3':rho_b,'elasticThicknessM':Te,'youngModulusPa':E,'poissonRatio':nu,'rigidityNm':rigidity,'loadingEquation':'D*laplacian(laplacian(w)) + rho_m*g*w = rho_b*g*basaltThickness','constructionClock':'source ages span 24 Myr; prescribed emplacement and analytical cooling, prior erosion not simulated','erosionClock':'time zero is this reconstructed starting field; subsequent effective years separately integrated','rootThicknessReviewLimitM':30000,'unsupportedReliefStressReviewPa':160e6,'limits':'Elastic/Airy response and surface transport; no viscoelastic mantle flow or full 3D gravitational collapse.'}
 return total,fields,catalog,records,physics

def prepare(seed=5210914,gain=1):
 P.setup();g=D.joint_grid(16000);g['seed']=seed;g['region']='vorhan-duskreach';folder=C.WORK/'base'/str(seed)/f'g{gain:g}'
 z,kind,soil,allow,hard,features,_,_,_=P.initial(g,seed,'control');original=z.copy();delta,fields,extra,records,physics=construction(g,seed,gain);land=kind>=30
 free=land.astype(float)
 for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
  if f['geometry']['type']=='Point':free*=T.ease((T.distance(g,f['geometry']['coordinates'])-20000)/80000)
 free[hard]=0;z+=delta*free;allow=np.maximum(allow,T.ease(np.maximum(delta,0)/150)*free)
 construction_area=land&(delta>100);shore_distance=distance_transform_edt(land)*g['stepM'];core=delta>delta.max()*.25
 root_limit=fields['underplating-thickness'].max()<physics['rootThicknessReviewLimitM'];stress=physics['addedCrustDensityKgM3']*physics['gravityMs2']*np.maximum(delta,0)
 audit={'sources':records,'physics':physics,'gain':gain,'affectedOver100mKm2':float(construction_area.sum()*g['stepM']**2/1e6),'maximumAddedHeightM':float(delta.max()),'maximumAddedRootM':float(fields['underplating-thickness'].max()),'maximumReliefStressProxyPa':float(stress.max()),'mainMinimumCoastKm':float(shore_distance[core].min()/1000),'offshorePositiveSourceFraction':float(np.maximum(delta[~land],0).sum()/max(np.maximum(delta,0).sum(),1)),'protectedMaximumChangeM':float(abs(z-original)[hard].max(initial=0)),'rootBudgetPassed':bool(root_limit),'stressScreenPassed':bool(stress.max()<physics['unsupportedReliefStressReviewPa']),'initialHeightSha256':C.fingerprint({'sources':C.sha(CONFIG),'code':C.sha(__file__),'seed':seed,'gain':gain}),'status':'constructed, post-emplacement erosion pending'}
 audit['sourcePassed']=audit['rootBudgetPassed'] and audit['stressScreenPassed'] and audit['offshorePositiveSourceFraction']<.01 and audit['mainMinimumCoastKm']>300 and audit['protectedMaximumChangeM']==0
 labs,n=label(land&(original>3000));areas=np.bincount(labs.ravel())*g['stepM']**2/1e6;major=(labs>0)&(areas[labs]>6000)
 audit['mainMinimumExistingHighlandKm']=float(distance_transform_edt(~major)[core].min()*g['stepM']/1000)
 named=np.full(z.shape,np.inf)
 for f in T.D['ridges']:
  if f['id'].startswith(('vorhan','dusk')) or f['id']=='rift':named=np.minimum(named,T.tracefield(g,f['geometry']['coordinates'])[0])
 audit['mainMinimumNamedRidgeKm']=float(named[core].min()/1000)
 audit['areaPriorityHeightReviewM']=4200
 audit['areaPriorityPassed']=bool(delta.max()<=audit['areaPriorityHeightReviewM'])
 audit['sourcePassed']&=audit['mainMinimumExistingHighlandKm']>300 and audit['mainMinimumNamedRidgeKm']>220 and audit['areaPriorityPassed']
 for name,value in {'height':z,'control':original,'kind':kind,'soil':soil,'allow':allow,'protected':hard,'construction':delta*free,**fields}.items():C.save_array(folder/(name+'.npy'),value.astype('uint8') if name in ['kind','protected'] else value.astype('float32'))
 C.write(folder/'grid.json',g);C.write(folder/'sources.json',features+extra);C.write(folder/'construction.json',audit)
 print('TRACK CONSTRUCTION',seed,gain,audit['sourcePassed'],audit['affectedOver100mKm2'],audit['maximumAddedHeightM'],flush=True);return folder

def run(seed=5210914,gain=1,end=100000,mode='erosion-only',scenario='baseline'):
 base=prepare(seed,gain);audit=C.read(base/'construction.json')
 if not audit['sourcePassed']:raise ValueError('Track construction limits failed; saved candidate, no height clamp')
 g=C.read(base/'grid.json');folder=C.WORK/'coarse'/str(seed)/mode/scenario/f'g{gain:g}'/str(end)
 arrays={k:np.load(base/(k+'.npy')) for k in ['height','kind','soil','allow','protected']}
 # Restore float64 state before enforcing the strict solid budget.
 report=L.solve(folder,g,arrays['height'].astype(float),arrays['kind'],arrays['protected']>0,arrays['allow'].astype(float),arrays['soil'].astype(float),C.read(base/'sources.json'),mode,scenario,gain,end=end,dt=10000,cap=420)
 C.write(folder/'construction-link.json',{'base':str(base),'heightSha256':C.sha(base/'height.npy'),'constructionSha256':C.sha(base/'construction.json')});return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--seed',type=int,default=5210914);p.add_argument('--gain',type=float,default=1);p.add_argument('--end',type=int,default=100000);p.add_argument('--mode',default='erosion-only');p.add_argument('--scenario',default='baseline');q=p.parse_args()
 prepare(q.seed,q.gain) if q.prepare else run(q.seed,q.gain,q.end,q.mode,q.scenario)
