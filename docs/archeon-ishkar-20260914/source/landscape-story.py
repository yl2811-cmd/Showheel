"""Candidate drainage reconstruction and independent story-geography checks.

Corrections are authored initial conditions, never labelled physical erosion.
Scene translations are constant over an entire local footprint. No water mask
is used by the hydrology solver. Water is free to inundate a failed candidate.
"""
import pathlib,json,importlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).parent))
T=importlib.import_module('tectonics-model');H=importlib.import_module('landscape-water');np=T.np
from scipy.ndimage import gaussian_filter,gaussian_filter1d,distance_transform_edt,label,minimum_filter,maximum_filter
from scipy.spatial import cKDTree
from numba import njit

VERSION='story-drainage-v2'
SITES=[
 {'id':'FC','name':'Frontier','center':[0,26],'farmKm2':620,'builtKm2':17},
 {'id':'AT','name':'Atheria','center':[.5,27.8],'farmKm2':290,'builtKm2':10},
 {'id':'CR','name':'Crestline','center':[.3,27],'farmKm2':140,'builtKm2':6},
 {'id':'TH','name':'Thornfield','center':[12,25],'farmKm2':160,'builtKm2':6},
 {'id':'MI','name':'Millhaven','center':[-15,24],'farmKm2':140,'builtKm2':6},
 {'id':'CP','name':'Coppergate','center':[-3,18],'farmKm2':160,'builtKm2':6},
 {'id':'CL','name':'Cliffwatch','center':[-7,14],'farmKm2':150,'builtKm2':4.5},
 {'id':'WI','name':'Windbreak','center':[-3,11],'farmKm2':150,'builtKm2':4.5},
 {'id':'RB','name':'Riverbend','center':[-9.68122551399219,8.826584469092735],'farmKm2':140,'builtKm2':5},
]
for site in SITES:
 found=next((f for f in T.D['settlements'] if f.get('id')==site['id']),None)
 if found and site['id']!='RB':site['center']=found['geometry']['coordinates']
CORRIDORS=[[[.5,27.8],[.3,27],[0,26],[12,25],[14,31]],[[0,26],[-15,23]],[[-15,23],[-3,18],[-7,14],[-3,11],[-9.68,8.83]],[[-3,18],[12,25]]]

def location(g,coord):
 x,y=T.Proj(g['projection'])(*coord);return (g['ymax']-y)/g['stepM'],(x-g['xmin'])/g['stepM']

def domain(g):
 out=np.zeros((g['height'],g['width']),np.float32)
 if g['region']!='aethelgard':return out
 for line in CORRIDORS:
  d,_=T.tracefield(g,line);out=np.maximum(out,1-T.ease((d-170000)/160000))
 return out

def scene_mask(g,site,core=True):
 # Ellipses are diagnostic footprints. They never block water or form dams.
 x,y=T.Proj(g['projection'])(*site['center']);xx,yy=T.mesh(g)
 radius=np.sqrt(site['builtKm2']*1e6/np.pi) if core else 24000.
 return ((xx-x)/(radius*1.3))**2+((yy-y)/(radius/1.3))**2<=1

def channel(z,g,coords,heights,halfwidth=5000.):
 """Continuous valley along a sampled, gently smoothed geographic trace."""
 p=T.Proj(g['projection']);xy=np.array([p(*q) for q in coords]);ds=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
 valid=np.r_[True,np.diff(ds)>1];xy=xy[valid];ds=ds[valid];heights=np.asarray(heights)[valid]
 if len(ds)<2:return z.copy(),np.zeros_like(z),[]
 sample_step=min(1000.,g['stepM']*.5);samples=np.arange(0,ds[-1]+g['stepM']*.5,sample_step);samples=np.minimum(samples,ds[-1]);path=np.column_stack([np.interp(samples,ds,xy[:,i]) for i in range(2)]);levels=np.interp(samples,ds,heights)
 smooth=gaussian_filter1d(path,max(1,6000/sample_step),axis=0,mode='nearest');end_fade=T.ease(np.minimum(samples,ds[-1]-samples)/16000)[:,None];path=path*(1-end_fade)+smooth*end_fade
 # Query only the valley's physical bounding box, including broad shoulders.
 pad=180000.;c0=max(0,int((path[:,0].min()-pad-g['xmin'])/g['stepM']));c1=min(g['width'],int((path[:,0].max()+pad-g['xmin'])/g['stepM'])+2);r0=max(0,int((g['ymax']-path[:,1].max()-pad)/g['stepM']));r1=min(g['height'],int((g['ymax']-path[:,1].min()+pad)/g['stepM'])+2)
 if r1<=r0 or c1<=c0:return z.copy(),np.zeros_like(z),[]
 xx,yy=np.meshgrid(g['xmin']+np.arange(c0,c1)*g['stepM'],g['ymax']-np.arange(r0,r1)*g['stepM']);flat=np.column_stack([xx.ravel(),yy.ravel()]);distance,idx=cKDTree(path).query(flat,workers=1);sub=z[r0:r1,c0:c1];distance=distance.reshape(sub.shape);idx=idx.reshape(sub.shape)
 # Valley shoulders scale with incision depth; a fixed one-cell trench is
 # never substituted for a physically wide retreating valley side.
 floor=levels[idx];drop=np.maximum(0,sub-floor);width=np.maximum(halfwidth,halfwidth+drop/.035)
 weight=1-T.ease((distance-halfwidth*.22)/np.maximum(1,width-halfwidth*.22));new=z.copy();new[r0:r1,c0:c1]-=drop*weight
 return new,(new-z),path[::max(1,round(4000/min(1000.,g['stepM']*.5)))].tolist()

@njit(cache=False)
def graded_path(start,rec,z,width,dx,minimum_grade=0.00008):
 nodes=[];levels=[];i=start;h=z[i]-6.
 for _ in range(len(z)):
  nodes.append(i);levels.append(h);j=rec[i]
  if j<0 or j==i:break
  r=i//width;c=i%width;rr=j//width;cc=j%width;ds=dx*np.sqrt((r-rr)**2+(c-cc)**2)
  h=min(h-minimum_grade*ds,z[j]-6.);h=max(.01,h);i=j
 return nodes,levels

def reconstruct(z,g,kind,hard,river=None):
 if g['region']!='aethelgard':return z,np.zeros_like(z),{'version':VERSION,'sceneTranslations':[],'valleys':[]}
 before=z.copy();land=(kind>=30)&(kind!=80);focus=domain(g);p=T.Proj(g['projection']);valleys=[]
 # Reopen the established Orun water gap before drainage is recomputed.
 # The ordinary upstream route is a guide, not a locked receiver network.
 if river is not None:
  route=river;xy=np.array([p(*q) for q in route]);length=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
  first=location(g,route[0]);start=float(T.map_coordinates(z,np.array(first)[:,None],order=1,mode='nearest')[0]);height=np.maximum(0,start*(1-length/max(1,length[-1])))
  z,delta,path=channel(z,g,route,height,halfwidth=max(2500.,g['stepM']*.6));z[~land]=before[~land];valleys.append({'id':'orun-water-gap','maximumLoweringM':float(-delta.min()),'coordinates':route})
 # A basin is repaired as a catchment, including its outlet. Iterations are
 # explicit, bounded and retained in the correction ledger.
 for iteration in range(6):
  tp=H.topology(z,land,g['stepM']);depth=tp['filled']-z;labels=tp['basin'].reshape(z.shape);selected=np.unique(labels[(focus>.35)&(depth>2)&land]);selected=selected[selected>=0]
  scores=[]
  for b in selected:
   nodes=tp['nodes'][tp['starts'][b]:tp['starts'][b+1]];inside=nodes[focus.ravel()[nodes]>.35]
   if len(inside)*g['stepM']**2<2500e6 and depth.ravel()[inside].max()<25:continue
   scores.append((float(depth.ravel()[inside].max()),int(b),int(nodes[np.argmin(z.ravel()[nodes])])) )
  if not scores:break
  # Deepest basins first; recompute their downstream route on the next pass.
  for peak,b,start in sorted(scores,reverse=True):
   nodes,levels=graded_path(start,tp['bed-receiver'],z.ravel(),g['width'],g['stepM']);nodes=np.array(nodes);rr=nodes//g['width'];cc=nodes%g['width'];lo,la=p(g['xmin']+cc*g['stepM'],g['ymax']-rr*g['stepM'],inverse=True);coords=np.column_stack([lo,la]).tolist()
   if len(coords)<2:continue
   old=z;z,change,path=channel(z,g,coords,levels,halfwidth=max(3500.,g['stepM']*.6));z[~land]=before[~land]
   valleys.append({'id':f'basin-{iteration}-{b}','potentialDepthBeforeM':peak,'maximumLoweringM':float(-change.min()),'coordinates':coords,'bedM':levels})
 # Whole scene translations follow the repaired surrounding ground. No
 # point-sized elevated safe islands are installed in a flooded basin.
 translations=[]
 for site in SITES:
  rr,cc=location(g,site['center']);r,c=round(rr),round(cc)
  if not (0<=r<g['height'] and 0<=c<g['width']):continue
  distance=T.distance(g,site['center']);radius=max(5000.,np.sqrt(site['builtKm2']*1e6/np.pi)*2);core=distance<radius
  shift=float(np.median((z-before)[core])) if core.any() else float(z[r,c]-before[r,c]);w=1-T.ease((distance-radius)/24000)
  z=z*(1-w)+(before+shift)*w;translations.append({'id':site['id'],'name':site['name'],'center':site['center'],'shiftM':shift,'rigidRadiusM':radius,'blendM':24000,'inferredHeightOnly':True})
 z[~land]=before[~land]
 return z,z-before,{'version':VERSION,'method':'catchment-scale valley breach with physical shoulder widths; coherent scene translation','sceneTranslations':translations,'valleys':valleys,'maximumRaiseM':float((z-before).max()),'maximumLoweringM':float((before-z).max()),'notSimulatedErosion':True}

def translated_reference(reference,g,records):
 out=reference.copy()
 for row in records:
  d=T.distance(g,row['center']);out+=row['shiftM']*(1-T.ease((d-row['rigidRadiusM'])/row['blendM']))
 return out

def check(g,z,depth,occurrence=None,maximum_depth=None):
 if g['region']!='aethelgard':return {'passed':True,'applicable':False,'sites':[]}
 rows=[];dx=g['stepM'];slope=np.hypot(*np.gradient(z,dx));permanent=(depth>.05) if occurrence is None else occurrence>.99;maxdepth=depth if maximum_depth is None else maximum_depth
 for site in SITES:
  rr,cc=location(g,site['center']);r,c=round(rr),round(cc)
  if not(0<=r<g['height'] and 0<=c<g['width']):continue
  core=scene_mask(g,site);distance=T.distance(g,site['center']);resolved=dx<=250
  if not core.any():core[r,c]=True
  farmland=(distance<=24000)&(slope<.06)&~permanent&(z>0)&~core
  labels,n=label(farmland);areas=np.bincount(labels.ravel())*dx*dx/1e6;areas[0]=0
  farm_area=float(areas.max(initial=0));flooded=bool((permanent&core).any());max_core=float(maxdepth[core].max(initial=0))
  rows.append({'id':site['id'],'name':site['name'],'gridM':dx,'coreResolved':resolved,'corePermanentlyFlooded':flooded,'maximumCoreWaterDepthM':max_core,'continuousFarmAreaKm2':farm_area,'minimumFarmAreaKm2':site['farmKm2'],'farmAreaPassed':farm_area>=site['farmKm2'],'passed':not flooded and farm_area>=site['farmKm2'],'geometryStatus':'planning footprint, not a surveyed parcel map'})
 focus=domain(g);labs,n=label((depth>.05)&(focus>.35),np.ones((3,3)));areas=np.bincount(labs.ravel())*dx*dx/1e6;areas[0]=0;largest=float(areas.max(initial=0))
 return {'passed':all(r['passed'] for r in rows) and largest<=2500,'applicable':True,'sites':rows,'largestStoryLakeKm2':largest,'maximumStoryLakeKm2':2500,'lakeLimitStatus':'authored candidate acceptance ceiling; not a climate prediction','fineCoreValidationRequired':dx>250}
