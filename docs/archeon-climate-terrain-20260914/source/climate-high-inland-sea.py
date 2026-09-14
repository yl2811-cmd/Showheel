"""Half-area plateau-lake candidate with a real basin and Rim Falls outlet.

The author's old mapped lake is the area reference, not a imposed water mask.
Bed reconstruction, outlet excavation, water storage and erosion are separate.
"""
import pathlib,sys,importlib,argparse,time,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent))
C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;L=importlib.import_module('tectonics-landscape');H=L.H
from scipy.ndimage import gaussian_filter,distance_transform_edt,label
WORK=C.TASK/'high-inland-sea-v17/natural-shore-v3';PARENT=C.TASK/'plume-tracks-v16/base/5210914/g0.9'

def fields(g,area_factor=1.,level=2660.):
 pg=C.read(PARENT/'grid.json');original=T.sample(np.load(PARENT/'height.npy'),pg,g).astype(float);kind=T.sample(np.load(PARENT/'kind.npy'),pg,g,0).astype('uint8');soil=T.sample(np.load(PARENT/'soil.npy'),pg,g).astype(float)
 xx,yy=T.mesh(g);p=T.Proj(g['projection']);ox,oy=p(82,34);cx=ox-70000;cy=oy+20000;rx=200000*np.sqrt(area_factor);ry=244000*np.sqrt(area_factor)
 a=(xx-cx)/rx;b=(yy-cy-.10*(xx-cx)-12000*np.sin((xx-cx)/80000))/ry;theta=np.arctan2(b,a)
 r=np.hypot(a,b)/(1+.07*np.sin(3*theta)+.025*np.sin(5*theta+.6))
 land=(kind>=30)&(kind!=80);hard=kind==80;free=land.astype(float)
 for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
  if f['geometry']['type']!='Point' or f['id']=='V06':continue
  d=T.distance(g,f['geometry']['coordinates']);hard|=d<20000;free*=T.ease((d-20000)/40000)
 free[hard]=0
 # A broad, asymmetric subsiding floor between inherited shoulders. Banks
 # rise over tens of km; there is no narrow annular levee or no-water strip.
 bowl=level+160*(r*r-1)
 # Regional inherited shoulders and tributary hollows reach the shoreline.
 # The screening model faded these at r=1 and made an overly regular oval.
 residual=np.clip(gaussian_filter(original,max(.5,16000/g['stepM']))-gaussian_filter(original,max(.5,65000/g['stepM'])),-65,65)
 residual*=T.ease((np.hypot(xx-ox,yy-oy)-24000)/30000)
 residual*=.25+.75*T.ease((1-r)/.4)
 target=np.where(r<1,bowl+residual,np.maximum(original,bowl+residual))
 blend=(1-T.ease((r-1)/.65))*free;z=original+(target-original)*blend;basin_change=z-original
 # Explicit geological outlet joins the existing named Rim Falls relation.
 shore=[cx,cy-ry*(1+.07+.025*np.sin(-5*np.pi/2+.6))];coords=[list(p(cx,cy,inverse=True)),list(p(*shore,inverse=True)),[81,30],[79,29],[76,27],[72.92,24.64]];levels=[level-160,level,2440,2000,1250,0]
 best=np.full(z.shape,np.inf);bed=np.zeros(z.shape)
 xy=np.asarray([p(*q) for q in coords])
 for j,(a0,b0) in enumerate(zip(xy,xy[1:])):
  v=b0-a0;t=np.clip(((xx-a0[0])*v[0]+(yy-a0[1])*v[1])/np.dot(v,v),0,1);d=np.hypot(xx-a0[0]-t*v[0],yy-a0[1]-t*v[1]);take=d<best;best=np.minimum(best,d);bed[take]=(levels[j]+t*(levels[j+1]-levels[j]))[take]
 weight=(1-T.ease(best/22000))*free;outlet_change=np.minimum(bed-z,0)*weight;z+=outlet_change;z[hard]=original[hard]
 allow=free.copy();return z,kind,soil,hard,allow,{'original':original,'basin-reconstruction':basin_change,'outlet-reconstruction':outlet_change,'target-footprint':r<1}, {'lakeId':'high-sea','areaReference':'old cartographic polygon, not the already fragmented simulated water','oldMappedAreaKm2':306093.40633036103,'targetAreaKm2':153046.70316518052,'areaFactor':area_factor,'hypothesizedSpillLevelM':level,'floorMaximumDepthBelowDesignSpillM':160,'outletCoordinates':coords,'outletBedLevelsM':levels,'namedOutlet':'Rim Falls','lakeVistaV06MayChangeBed':True,'otherProtectedSitesMaximumChangeM':float(abs(z-original)[hard].max(initial=0)),'baseReconstructionNotErosion':True,'narrowRingLeveeUsed':False}

def prepare(step=2000,area_factor=1.,level=2660.,continental=False):
 WORK.mkdir(parents=True,exist_ok=True);L.WORK=WORK;T.WORK=WORK;T.MASK=None
 g=importlib.import_module('climate-terrain').joint_grid(step) if continental else L.grid_window({'id':'high-inland-sea','region':'vorhan','center':[82,34]},step,1600);g['seed']=5210914
 if continental:g['region']='vorhan-duskreach'
 folder=WORK/('continental-base' if continental else 'base')/str(step)/f'a{area_factor:g}-h{level:g}';z,kind,soil,hard,allow,changes,record=fields(g,area_factor,level)
 for name,a in {'height':z,'kind':kind,'soil':soil,'protected':hard,'allow':allow,**changes}.items():C.save_array(folder/(name+'.npy'),a.astype('uint8') if name in ['kind','protected','target-footprint'] else a.astype('float32'))
 C.write(folder/'grid.json',g);record.update(parentHeightSha256=C.sha(PARENT/'height.npy'),gridM=step,basinReconstructionM3=float(changes['basin-reconstruction'].sum()*step**2),outletExcavationM3=float(-changes['outlet-reconstruction'].sum()*step**2));C.write(folder/'construction.json',record)
 return folder

def water(step=2000,area_factor=1.,level=2660.,scenario='baseline'):
 folder=prepare(step,area_factor,level);g=C.read(folder/'grid.json');z=np.load(folder/'height.npy').astype(float);kind=np.load(folder/'kind.npy');land=(kind>=30)&(kind!=80);proxy=L.proxy(z,g,kind)
 hyd=H.run(z,land,step,proxy,{'dry':.5,'baseline':1,'wet':1.5}[scenario],cycles=20,converge=True,max_cycles=2000)
 p=T.Proj(g['projection']);x,y=p(82,34);row=round((g['ymax']-y)/step);col=round((x-g['xmin'])/step);labels,n=label(hyd['lake-depth']>.05,np.ones((3,3)));body=labels==labels[row,col] if labels[row,col] else np.zeros(z.shape,bool)
 tp=hyd['topology'];b=tp['basin'].reshape(z.shape)[row,col];nodes=[];node=int(tp['representative'][b]) if b>=0 else row*g['width']+col
 for _ in range(z.size):
  nodes.append(node);j=int(tp['receiver'][node])
  if j<0 or j==node:break
  node=j
 rr=np.asarray(nodes)//g['width'];cc=np.asarray(nodes)%g['width'];lo,la=p(g['xmin']+cc*step,g['ymax']-rr*step,inverse=True)
 out=folder/'water'/scenario
 for name in ['lake-depth','lake-level','lake-occurrence','lake-min-depth','lake-max-depth','receiver','discharge','wetness']:C.save_array(out/(name+'.npy'),hyd[name].astype('int32') if name=='receiver' else hyd[name].astype('float32'))
 record={'scenario':scenario,'mainLakeAreaKm2':float(body.sum()*step**2/1e6),'fractionOfOldMappedArea':float(body.sum()*step**2/1e6/306093.40633036103),'mainMaximumDepthM':float(hyd['lake-depth'][body].max(initial=0)),'mainWaterLevelM':float(np.median(hyd['lake-level'][body])) if body.any() else None,'mainBasinSpillM':float(tp['spill'][b]) if b>=0 else None,'waterConvergence':hyd['convergence'],'maximumWaterRelativeError':hyd['maxWaterRelativeError'],'mainOutletRoute':np.column_stack([lo,la]).tolist(),'climateValidated':False,'otherProtectedSitesMaximumChangeM':C.read(folder/'construction.json')['otherProtectedSitesMaximumChangeM']}
 record['halfAreaPassed']=.45<=record['fractionOfOldMappedArea']<=.55
 route=np.column_stack([lo,la]);head=np.asarray(p(81,30));rx0,ry0=p(route[:,0],route[:,1]);record['minimumRouteDistanceToRimFallsHeadKm']=float(np.hypot(rx0-head[0],ry0-head[1]).min()/1000);record['rimFallsConnected']=record['minimumRouteDistanceToRimFallsHeadKm']<32
 C.write(out/'hydrology.json',record);C.write(out/'grid.json',g);print('HIGH SEA', {k:v for k,v in record.items() if k not in ['mainOutletRoute']},flush=True);return record

def evolve(step=16000,area_factor=1.07,level=2660.,scenario='baseline',mode='erosion-only',end=100000):
 base=prepare(step,area_factor,level,continental=step>=16000);g=C.read(base/'grid.json');L.WORK=WORK;T.WORK=WORK;T.MASK=None;L.CFG={**L.CFG,'maximumSeasonalCycles':1000}
 folder=WORK/('coarse' if step>=16000 else 'regional')/mode/scenario/str(step)/str(end);parent=None
 if step<16000:
  p=WORK/'coarse'/mode/scenario/'16000'/str(end)
  if not (p/'simulation.json').exists():raise ValueError('Completed repaired parent is required')
  parent=(p,C.read(p/'grid.json'))
 values={name:np.load(base/(name+'.npy')) for name in ['height','kind','protected','allow','soil']};features=C.read(PARENT/'sources.json')
 source_projection=T.Proj(C.read(PARENT/'grid.json')['projection']);target_projection=T.Proj(g['projection'])
 for feature in features:feature['xy']=list(target_projection(*source_projection(*feature['xy'],inverse=True)))
 if step<16000:
  rows,cols=np.indices(values['height'].shape);distance=np.minimum.reduce([rows,cols,g['height']-1-rows,g['width']-1-cols])*step;values['allow']*=T.ease(distance/24000)
 result=L.solve(folder,g,values['height'].astype(float),values['kind'],values['protected']>0,values['allow'].astype(float),values['soil'].astype(float),features,mode,scenario,1,parent=parent,end=end,dt=10000 if step>=16000 else 5000,cap=420)
 C.write(folder/'construction-link.json',{'source':str(base),'heightSha256':C.sha(base/'height.npy'),'constructionSha256':C.sha(base/'construction.json')});print('HIGH SEA EROSION',step,end,result['passed'],flush=True);return folder

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--step',type=int,default=2000);p.add_argument('--area-factor',type=float,default=1);p.add_argument('--level',type=float,default=2660);p.add_argument('--scenario',default='baseline');p.add_argument('--evolve',action='store_true');p.add_argument('--mode',default='erosion-only');p.add_argument('--end',type=int,default=100000);q=p.parse_args()
 for scenario in ['baseline','dry','wet'] if q.scenario=='all' else [q.scenario]:
  evolve(q.step,q.area_factor,q.level,scenario,q.mode,q.end) if q.evolve else water(q.step,q.area_factor,q.level,scenario)
  gc.collect()
