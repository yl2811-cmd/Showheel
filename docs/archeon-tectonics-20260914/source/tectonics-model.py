"""Reproducible, offline tectonic candidates. Formal atlas is read-only.

Coarse fields use conservative finite-volume landscape evolution. Nested grids
use Landlab SPACE and explicit inherited boundary fluxes. All time is effective
model time, not a claim about Archeon history.
"""
import os,sys,pathlib,json,hashlib,math,argparse,importlib.util,time,gc
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE_WORK=ROOT.parents[1]/'review/tectonics-20260914'
WORK=pathlib.Path(os.environ.get('TECTONICS_WORK',str(BASE_WORK/'v2')))
OLD=ROOT.parents[1]/'review/foundation-20260914'
sys.path.insert(0,str(OLD/'deps'));os.environ.setdefault('MPLCONFIGDIR',str(WORK/'mpl'))
import numpy as np
from scipy.ndimage import gaussian_filter as blur, map_coordinates, distance_transform_edt as edt, zoom, label
from PIL import Image
from pyproj import Proj
from affine import Affine
from rasterio.features import rasterize
from numba import njit
Image.MAX_IMAGE_PIXELS=None
sys.path.insert(0,str(ROOT/'src'));F=importlib.import_module('foundation-model')
# The legacy module has caches created under earlier dynamic import names.
# Compile these three small kernels in this process to avoid stale module keys.
F.flood_route=njit(cache=False)(F.flood_route.py_func)
F.discharge=njit(cache=False)(F.discharge.py_func)
F.ridge_distance=njit(cache=False)(F.ridge_distance.py_func)
INPUT=json.loads((BASE_WORK/'input.json').read_text());D=INPUT['atlas']
C=json.loads((ROOT/'data/tectonics-config.json').read_text(encoding='utf-8'))
if os.environ.get('TECTONICS_GRID_M'):C['gridStepM']=int(os.environ['TECTONICS_GRID_M'])
STRUCT=importlib.import_module('tectonics-structure')
LOADED_CODE_HASHES={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/tectonics-model.py',ROOT/'src/tectonics-structure.py']}
MASK=None
REAL_CLIMATE=os.environ.get('TECTONICS_REAL_CLIMATE')
def weights(id,g):
    defaults={k:np.ones((g['height'],g['width']),np.float32) for k in ['tectonic','fault-bend','magmatism','water','weathering','aeolian','planation','rock-strength','soil','seeding']};defaults['protection']=np.zeros((g['height'],g['width']),np.float32)
    if MASK is None:return defaults
    path=pathlib.Path(MASK)
    if path.is_dir():
        path=path/(id+'.json')
        if not path.exists():return defaults
    obj=json.loads(path.read_text(encoding='utf-8'))
    if obj['region']!=id:raise ValueError('Mask region does not match simulation region')
    layers=list(obj['layers'].values()) if 'layers' in obj else [obj]
    for layer in layers:
      for k,v in layer['fields'].items():
        if k not in defaults:raise ValueError('Unknown process mask '+k)
        a=np.array(v,dtype=np.float32).reshape(layer['height'],layer['width']);limit=1 if k=='protection' else 2
        if not np.isfinite(a).all() or a.min()<0 or a.max()>limit:raise ValueError('Invalid process weight range')
        source=layer.get('grid')
        if source:
            xx,yy=mesh(g)
            if source['projection']!=g['projection']:
                lon,lat=Proj(g['projection'])(xx,yy,inverse=True);xx,yy=Proj(source['projection'])(lon,lat)
            rows=(source['ymax']-yy)/((source['height']-1)*source['stepM'])*(len(a)-1);cols=(xx-source['xmin'])/((source['width']-1)*source['stepM'])*(a.shape[1]-1)
            field=map_coordinates(a,[rows,cols],order=1,mode='constant',cval=0 if k=='protection' else 1,prefilter=False)
        else:field=zoom(a,(g['height']/len(a),g['width']/a.shape[1]),order=1,prefilter=False)[:g['height'],:g['width']]
        defaults[k]=np.maximum(defaults[k],field) if k=='protection' else np.clip(defaults[k]+field-1,0,2)
    return defaults
def log(s):print(s,flush=True)
def savejson(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.file_digest(open(p,'rb'),'sha256').hexdigest()
def ease(x):x=np.clip(x,0,1);return x*x*(3-2*x)
def norm(a):q=np.percentile(a,[5,50,95]);return np.clip((a-q[1])/max(1e-9,(q[2]-q[0])/3.29),-3,3)
def pairs(v):
    if isinstance(v[0],(int,float)):yield v
    else:
        for a in v:yield from pairs(a)
def geom(g,p):
    def walk(v):
        if isinstance(v[0],(int,float)):return list(p(*v))
        return [walk(a) for a in v]
    return {'type':g['type'],'coordinates':walk(g['coordinates'])}
def mesh(g):return np.meshgrid(g['xmin']+np.arange(g['width'])*g['stepM'],g['ymax']-np.arange(g['height'])*g['stepM'])
def sample(a,old,g,order=1):
    xx,yy=mesh(g)
    if old['projection']!=g['projection']:
        lon,lat=Proj(g['projection'])(xx,yy,inverse=True);xx,yy=Proj(old['projection'])(lon,lat)
    return map_coordinates(a,[(old['ymax']-yy)/old['stepM'],(xx-old['xmin'])/old['stepM']],order=order,mode='nearest',prefilter=False)
def raster(features,g):
    if not features:return np.zeros((g['height'],g['width']),bool)
    return rasterize([(geom(f,Proj(g['projection'])),1) for f in features],out_shape=(g['height'],g['width']),transform=Affine(g['stepM'],0,g['xmin']-g['stepM']/2,0,-g['stepM'],g['ymax']+g['stepM']/2),dtype='uint8')>0
def distance(g,q):
    x,y=Proj(g['projection'])(*q);xx,yy=mesh(g);return np.hypot(xx-x,yy-y)
def tracefield(g,coords):
    pts=np.array([Proj(g['projection'])(*q) for q in coords]);return F.ridge_distance(g['height'],g['width'],g['stepM'],g['xmin'],g['ymax'],pts)

def register_markup():
    p=Proj(F.G['projection'])
    anchors=[('RB',[270,602]),('WI',[588,492]),('WH',[903,433]),('V01',[176,556]),('CO',[562,170]),('CW',[399,364])]
    markers={f['id']:f for f in F.S['markers']}
    # Resolve names, as source IDs are stable but not mnemonic for every town.
    names={'CO':'Coppergate','CW':'Cliffwatch'}
    for key,name in names.items():markers[key]=next(f for f in F.S['markers'] if f['properties']['name']==name)
    xy=np.array([[*p(*markers[k]['geometry']['coordinates']),1] for k,s in anchors]);screen=np.array([s for k,s in anchors]);matrix=np.linalg.lstsq(xy,screen,rcond=None)[0]
    error=np.linalg.norm(xy@matrix-screen,axis=1)
    if max(error)>14:raise RuntimeError('Screenshot landmark registration exceeds 14 pixels: '+str(error))
    ring=[[294,647],[328,691],[350,747],[378,778],[420,793],[495,800],[570,805],[653,810],[692,805],[739,768],[801,719],[859,688],[906,679],[958,650],[1003,620],[1051,589],[1092,558],[1130,537],[1140,481],[1132,472],[1145,439],[1144,398],[1121,366],[1104,324],[1078,291],[1043,247],[1015,202],[1000,258],[951,339],[891,400],[826,447],[742,493],[660,522],[570,542],[478,555],[377,562],[292,569],[294,647]]
    inv=np.linalg.inv(matrix[:2,:]);world=(np.array(ring)-matrix[2,:])@inv
    ll=np.column_stack(p(world[:,0],world[:,1],inverse=True)).tolist()
    obj={'type':'Feature','id':'author-orun-back-uplift','geometry':{'type':'Polygon','coordinates':[ll]},'properties':{'source':'codex-clipboard-1c8e4ddc-2abc-4e54-9839-3345ffd05856.png','screenSize':[1155,896],'screenRing':ring,'registrationRmsPixels':float(np.sqrt(np.mean(error**2))),'registrationMaxPixels':float(max(error)),'anchors':[{'id':k,'pixel':s,'errorPixels':float(e)} for (k,s),e in zip(anchors,error)],'policy':'Uplift plateau and enclosed shallow basins; retain existing high peaks and explicitly protected wall/outlet'}}
    savejson(WORK/'markup.geojson',obj);savejson(ROOT/'data/tectonics-orun-uplift.geojson',obj);return obj

def region_grid(id):
    if id=='aethelgard':
        g=dict(F.G);ratio=g['stepM']/C['gridStepM'];g['width']=round((g['width']-1)*ratio)+1;g['height']=round((g['height']-1)*ratio)+1;g['stepM']=C['gridStepM'];return g
    r=C['regions'][id];p=Proj(proj='laea',lat_0=r['center'][1],lon_0=r['center'][0],R=C['radiusM'])
    land=[f for f in D['land'] if f['id'] in r.get('landIds',[]) or ('landPrefix'in r and f['id'].startswith(r['landPrefix']))]
    points=np.array([a for f in land for a in pairs(geom(f['geometry'],p)['coordinates'])]);dx=C['gridStepM']
    pad=max(4,math.ceil(C.get('shoreline',{}).get('maxDisplacementM',0)/dx)+4)
    xmin=math.floor(points[:,0].min()/dx-pad)*dx;ymax=math.ceil(points[:,1].max()/dx+pad)*dx
    return {'width':math.ceil((points[:,0].max()-xmin)/dx)+pad+1,'height':math.ceil((ymax-points[:,1].min())/dx)+pad+1,'xmin':xmin,'ymax':ymax,'stepM':dx,'projection':p.srs,'id':id}

def native(g):
    meta=INPUT['world'];p=Proj(proj='eqearth',R=C['radiusM']);cal=INPUT['worldCalibration'];a=np.array([[*p(*v['q']),1] for v in cal]);b=np.array([v['pixel'] for v in cal]);m=np.linalg.solve(a,b)
    xx,yy=mesh(g);lon,lat=Proj(g['projection'])(xx,yy,inverse=True);wx,wy=p(lon,lat);px=wx*m[0,0]+wy*m[1,0]+m[2,0]-.5;py=wx*m[0,1]+wy*m[1,1]+m[2,1]-.5
    z=np.memmap(ROOT/'terrain/world-height.f32',dtype='<f4',mode='r',shape=(meta['height'],meta['width']));k=np.asarray(Image.open(ROOT/'terrain/world-mask.png'))
    if k.ndim==3:k=k[:,:,0]
    return map_coordinates(z,[py,px],order=1,mode='nearest',prefilter=False).astype('float32'),map_coordinates(k,[py,px],order=0,mode='nearest',prefilter=False)

def prepare(id):
    out=WORK/id;out.mkdir(parents=True,exist_ok=True);g=region_grid(id);g['id']=id;g['region']=id
    r=C['regions'][id];land=[f['geometry'] for f in D['land'] if f['id'] in r.get('landIds',[]) or ('landPrefix'in r and f['id'].startswith(r['landPrefix']))]
    if id=='aethelgard':
        base=sample(np.load(OLD/'height.npy'),F.G,g);kind=sample(np.load(OLD/'kind.npy'),F.G,g,0);protected=sample(np.load(OLD/'protected.npy'),F.G,g,0)>0
    else:
        base,kind=native(g);kind[~raster(land,g)]=0;protected=(kind<30)|(kind==80)|(kind==200)
        for f in D['settlements']+D['vistas']+D.get('extra',[]):
            if f['geometry']['type']!='Point':continue
            x,y=Proj(g['projection'])(*f['geometry']['coordinates'])
            if g['xmin']-30000<x<g['xmin']+g['width']*g['stepM']+30000 and g['ymax']-g['height']*g['stepM']-30000<y<g['ymax']+30000:protected|=distance(g,f['geometry']['coordinates'])<24000
        protected|=edt(kind>=30)*g['stepM']<6000
    np.save(out/'baseline-kind.npy',kind)
    revised=base.copy();delta=np.zeros_like(base);override=np.zeros_like(protected);basin=np.zeros_like(base)
    if id=='vorhan' and C.get('structureVersion')==2:
        revised,kind,protected,override,rift_report=STRUCT.reconstruct_rift(sys.modules[__name__],g,base,kind,protected);delta=revised-base;savejson(out/'rift-report.json',rift_report)
    if id=='aethelgard' and C.get('structureVersion')==2:
        revised,protected,allow,override,report=STRUCT.reconstruct_orun(sys.modules[__name__],g,base,kind,protected)
        delta=revised-base
        for key,a in {'baseline':base,'revised':revised,'kind':kind,'protected':protected.astype('uint8'),'hard-protected':protected.astype('uint8'),'override':override.astype('uint8'),'plateau-uplift':delta,'allow':allow,'evolution-allow':allow}.items():np.save(out/(key+'.npy'),a)
        savejson(out/'plateau-report.json',report);savejson(out/'grid.json',g);savejson(WORK/'thermal-audit.json',STRUCT.thermal_audit(C));log(f'PREPARED {id}: {g["width"]} x {g["height"]}, segmented normal faults');return
    if id=='aethelgard':
        mark=register_markup();override=raster([mark['geometry']],g)&(kind>=30)&(kind!=80)
        orun=next(f for f in D['ridges'] if f['id']=='orun');wall,_=tracefield(g,orun['geometry']['coordinates'])
        exact=(wall<C['plateau']['wallBufferM'])|(distance(g,[-10,9])<28000)|(distance(g,F.S['orunLocal']['center'])<50000)
        override&=~exact
        wt=ease(edt(override)*g['stepM']/C['plateau']['boundaryFadeM'])
        xx,yy=mesh(g);target=3200+90*np.sin(xx/140000)+65*np.cos(yy/170000)
        # Retain terrain texture on the uplifted slab rather than a level fill.
        mesa=norm(np.load(OLD/'references/mesa.npy'))
        target+=np.clip(F.tiled(mesa,g,120,91477)*95,-190,190)
        target+=np.clip(base-blur(base,16),-100,140)*.45
        # A relative shallow lake floor survives without its old low datum.
        wd=distance(g,[4,11.5]);basin=500*np.exp(-(wd/50000)**2);target-=basin
        anchors=base[override&(base>2850)&(base<3750)];datum=float(np.median(anchors)) if len(anchors) else 3200
        datum=float(np.clip(datum,3100,3450));target+=datum-3200
        # Smooth positive increment preserves all higher peaks; no hard maximum.
        delta=np.maximum(target-base,0)*wt;revised+=delta
        # Spatial shapes and water class survive, water datum follows the raised floor.
        protected|=override
        savejson(out/'plateau-report.json',{'targetDatumM':datum,'areaKm2':float(override.sum()*g['stepM']**2/1e6),'maxUpliftM':float(delta.max()),'meanUpliftM':float(delta[override].mean()),'coreBelow2400Before':int(np.count_nonzero(override&(wt>.99)&(base<2400))),'coreBelow2400After':int(np.count_nonzero(override&(wt>.99)&(revised<2400))),'whisperflatRevisedM':float(sample(revised,g,{**g,'width':1,'height':1,'xmin':Proj(g['projection'])(4,11.5)[0],'ymax':Proj(g['projection'])(4,11.5)[1]})[0,0])})
    allow=ease(edt(~protected)*g['stepM']/36000).astype('float32')
    evolution_allow=allow.copy();hard_protected=protected.copy()
    if id=='aethelgard':
        # Revised plateau interior permits shallow geomorphic change. Scenic
        # footprints and the unchanged main wall remain exact numerical locks.
        shallow=override&~exact&(distance(g,[4,11.5])>12000)
        hard_protected[shallow]=False
        evolution_allow[shallow]=C['plateau']['evolutionWeight']*ease(edt(shallow)[shallow]*g['stepM']/24000)
        damping=WORK/'plateau-local-damping.npy'
        if damping.exists():evolution_allow*=np.load(damping)
    for key,a in {'baseline':base,'revised':revised,'kind':kind,'protected':protected.astype('uint8'),'hard-protected':hard_protected.astype('uint8'),'override':override.astype('uint8'),'plateau-uplift':delta,'allow':allow,'evolution-allow':evolution_allow}.items():np.save(out/(key+'.npy'),a)
    savejson(out/'grid.json',g);log(f'PREPARED {id}: {g["width"]} x {g["height"]}')

def tile_field(src,g,extent,salt):
    # Existing overlap-add quilting is metre based and uses a fixed crop stream.
    return F.tiled(src,g,extent,salt)

def initial(id,seed):
    out=WORK/id/str(seed);out.mkdir(parents=True,exist_ok=True);g=json.loads((WORK/id/'grid.json').read_text());base=np.load(WORK/id/'revised.npy');allow=np.load(WORK/id/'allow.npy');kind=np.load(WORK/id/'kind.npy')
    controls=weights(id,g);allow*=1-controls['protection'];rng=np.random.default_rng(seed);relief=np.zeros_like(base);uplift=np.zeros_like(base);rate=np.zeros_like(base);traces=[];provenance=[];new_traces=[]
    r=C['regions'][id];faults=r['faults'].copy()
    if id=='keld':faults=[['keld-arc','compression',0.00015]]
    for num,(name,mode,v) in enumerate(faults):
        if name=='orun' and C.get('structureVersion')==2:
            traces.extend(json.loads((WORK/id/'orun-faults.json').read_text()));continue
        if name=='rift' and C.get('structureVersion')==2:
            traces.extend(json.loads((WORK/id/'rift-faults.json').read_text()));continue
        coords=r['islandArc'] if name=='keld-arc' else next(f for f in D['ridges'] if f['id']==name)['geometry']['coordinates']
        p=Proj(g['projection']);pts=np.array([p(*q) for q in coords]);dr=np.diff(pts,axis=0);tangent=dr/max(1,np.linalg.norm(dr,axis=1).mean());normal=np.array([-np.mean(tangent[:,1]),np.mean(tangent[:,0])]);normal/=max(np.linalg.norm(normal),1e-9)
        for branch in range(3):
            shift=(branch-1)*rng.uniform(55000,145000);offset=pts+normal*shift
            if branch:offset+=rng.normal(0,20000,offset.shape)
            co=np.column_stack(p(offset[:,0],offset[:,1],inverse=True)).tolist();d,side=tracefield(g,co);signed=d*np.sign(side)
            width=rng.uniform(45000,95000);env=np.exp(-(d/(width*2))**2);xx,yy=mesh(g)
            along=xx*normal[1]-yy*normal[0];segment=.55+.45*np.sin(along/rng.uniform(110000,210000)+rng.uniform(-3,3))**2
            if mode=='extension':form=(.8*np.tanh(signed/20000)+.45*np.sin(signed/55000))*env*segment
            elif mode=='plateau':form=(.7+.3*np.tanh(signed/30000))*env*segment
            elif mode=='reactivation':form=(.6*np.tanh(signed/18000)+.4)*env*segment
            else:form=env*segment
            multiplier=.65 if branch else 1.;u=form*v*multiplier;rate+=u
            uplift+=form*rng.uniform(550,1600)*multiplier
            traces.append({'id':f'{name}-{branch}','parent':name,'mode':mode,'rateMyr':v*multiplier,'coordinates':co})
    # Northern anchors persist from foundation v5; textures are not another set of painted mountains.
    for i,t in enumerate(C['tiles']):
        path=ROOT.parent/'tile'/t['file'];a=norm(np.asarray(Image.open(path).convert('L'),np.float32));crop=a[round(a.shape[0]*.07):round(a.shape[0]*.94),round(a.shape[1]*.07):round(a.shape[1]*.94)]
        strength=t['amplitudeM']*(.4 if id=='keld' else 1)
        field=tile_field(crop,g,t['extentKm'],seed+i*997)
        relief+=field*strength
        provenance.append({**t,'sha256':sha(path),'cropFraction':[.07,.07,.94,.94],'rotation':'seeded multiples of 90 degrees, independent per overlapping patch','seed':seed+i*997,'role':'bounded zero-mean morphology prior; image lighting is not measured altitude'})
    for key,weight,extent in [('rift',200,300),('mesa',140,150),('snow',200,300)]:
        a=np.load(OLD/'references'/(key+'.npy'));relief+=tile_field(norm(a),g,extent,seed+len(key)*7919)*weight
    factor=.25+.75*ease((blur(base,max(1,24000/g['stepM']))-500)/2200)
    if C.get('structureVersion')==2:
        broad,extra,formation=STRUCT.provinces(sys.modules[__name__],g,id,seed)
        uplift+=broad;rate+=extra
        secondary,secondary_rate,new_traces=STRUCT.secondary_faults(sys.modules[__name__],g,id,seed,base,allow);uplift+=secondary;rate+=secondary_rate;traces.extend(new_traces)
        savejson(out/'formation.json',formation)
        # Image priors supply bounded detail; they cannot imprint a second set
        # of tile-shaped high plateaus into the regional geological envelope.
        relief=blur(relief,max(.5,6000/g['stepM']))*.35
    tectonic_field=uplift*controls['tectonic']*allow;prior_field=relief*factor*allow
    candidate=base+tectonic_field+prior_field
    dynamic,lava,plumes=STRUCT.magmatic_provinces(sys.modules[__name__],g,id,seed);magmatic=(dynamic+lava)*controls['magmatism']*allow;candidate+=magmatic
    lava_applied=lava*controls['magmatism']*allow;dynamic_applied=dynamic*controls['magmatism']*allow
    if id=='aethelgard' and C.get('structureVersion')==2:
        ramp=np.load(WORK/id/'orun-ramp-weight.npy');front=np.load(WORK/id/'orun-front-weight.npy');lock=np.maximum(ramp,front)
        keep=1-ease(lock/.25);candidate=base+(candidate-base)*keep;rate*=keep;tectonic_field*=keep;prior_field*=keep;magmatic*=keep;lava_applied*=keep;dynamic_applied*=keep
    if id=='vorhan' and C.get('structureVersion')==2:
        keep=1-.95*np.load(WORK/id/'rift-floor-weight.npy');candidate=base+(candidate-base)*keep;rate*=keep;tectonic_field*=keep;prior_field*=keep;magmatic*=keep;lava_applied*=keep;dynamic_applied*=keep
    savejson(out/'magmatism.json',{'provinces':plumes,'addedBasaltVolumeKm3':float(lava_applied.sum()*g['stepM']**2/1e9),'addedDynamicSupportVolumeKm3':float(dynamic_applied.sum()*g['stepM']**2/1e9),'volumeDomain':'after scene and reconstructed-base masks; shoreline changes recorded separately in boundary-reconstruction','intensity':C.get('magmatism',{}).get('intensity',1)})
    # Positive lowland transition, smoothly saturated peaks; locked cells are exact.
    free=allow>0
    candidate[~free]=base[~free];rate*=allow*controls['tectonic']
    coastal_displacement=np.where(kind==0,uplift*controls['tectonic']+(dynamic+lava)*controls['magmatism'],candidate-base)
    shore,final_kind,shore_allow,shore_report=STRUCT.shoreline_candidate(sys.modules[__name__],g,base,kind,coastal_displacement,controls)
    candidate[shore_allow>0]=shore[shore_allow>0];savejson(out/'shoreline.json',shore_report)
    rate[(final_kind<30)|(final_kind==80)|(final_kind==200)]=0
    for key,a in {'kind':final_kind,'shore-allow':shore_allow,'cap-thickness':C['lithology']['capThicknessM']+lava_applied,'magmatic-uplift':magmatic,'basalt-thickness':lava_applied}.items():np.save(out/(key+'.npy'),np.asarray(a,dtype='float32'))
    savejson(out/'tectonic-summary.json',{'faultDensity':C.get('faultDensity',1.5),'segments':len(traces),'secondarySegments':len(new_traces),'plumeProvinces':len(plumes),'shoreline':shore_report})
    for key,a in {'initial':candidate.astype('float32'),'uplift-rate':rate.astype('float32'),'construction':(candidate-base).astype('float32'),'tectonic-construction':tectonic_field.astype('float32'),'material-prior':prior_field.astype('float32'),'boundary-reconstruction':(candidate-base-tectonic_field-prior_field-magmatic).astype('float32')}.items():np.save(out/(key+'.npy'),a)
    savejson(out/'sources.json',provenance);savejson(out/'faults.json',traces)
    log(f'INITIAL {id} seed {seed}')

@njit(cache=False)
def fluvial(z,soil,order,rec,q,slope,filled,allow,hard,dx,dt,external,water_weight,rock_strength=None,gravity=9.610517,hard_k=2e-6,soft_k=1.2e-5):
    n=z.size;area=dx*dx;zz=z.ravel().copy();hh=soil.ravel().copy();incoming=external.copy()*dt
    er=np.zeros(n,np.float64);dep=np.zeros(n,np.float64);export=0.;mask=allow.ravel();cap=hard.ravel();ff=filled.ravel()
    active=np.zeros(n,np.uint8)
    for i in order:active[i]=1
    for k in range(len(order)-1,-1,-1):
        i=order[k];j=rec[i];water=max(0,q[i]);s=max(0,slope[i]);mobile=hh[i];can=mask[i]
        if j>=0 and can>0 and ff[i]-zz[i]<.1:
            drop=max(0,zz[i]-zz[j]);K=hard_k if cap[i] else soft_k
            strength=1. if rock_strength is None else max(.2,rock_strength.ravel()[i])
            fac=K*water_weight.ravel()[i]*(gravity/9.80665)*math.sqrt(water)*dt/max(dx,1)/strength
            cut=min(drop*fac/(1+fac),max(0,drop)*.4)*can
            zz[i]-=cut;hh[i]=max(0,hh[i]-cut);er[i]=cut;incoming[i]+=cut*area
        sediment=incoming[i]
        if sediment>0:
            if j<0:export+=sediment;continue
            settling=1-math.exp(-.03*area/max(water,1))
            put=sediment/area*settling*can
            put=min(put,30.,max(0,ff[i]-zz[i])+3.)
            zz[i]+=put;hh[i]+=put;dep[i]=put;sediment-=put*area
            if active[j]:incoming[j]+=sediment
            else:export+=sediment
    return zz.reshape(z.shape),hh.reshape(z.shape),er.reshape(z.shape),dep.reshape(z.shape),export,incoming/dt

def paired_flux(z,soil,allow,dx,dt,hard,dry,wind,planation=None,aeolian_weight=None,rock_strength=None,gravity=9.610517):
    # Finite-volume pair exchanges. Zero flux across fixed terrain cells.
    shape=z.shape;dz=np.zeros(shape);dh=np.zeros(shape);wear=np.zeros(shape)
    if planation is None:planation=np.ones(shape)
    if aeolian_weight is None:aeolian_weight=np.ones(shape)
    if rock_strength is None:rock_strength=np.ones(shape)
    for axis in [0,1]:
        a=[slice(None),slice(None)];b=a.copy();a[axis]=slice(None,-1);b[axis]=slice(1,None);a=tuple(a);b=tuple(b)
        diff=z[a]-z[b];mask=np.minimum(allow[a],allow[b]);slope=diff/dx
        flux=diff*np.minimum(.04,.025*dt/dx**2*(1+(slope/.7)**2))*mask
        # Bedding-sensitive retreat has a conservative downslope debris receiver.
        # Effective cohesive relief and friction oppose gravitational driving.
        # At coarse resolution this diagnoses only resolved slopes, not hidden
        # vertical faces. Nested grids perform the actual cliff-scale check.
        strength=np.maximum(.2,np.minimum(rock_strength[a],rock_strength[b]))
        critical=.65+((2e5+hard[a]*8e5)*strength)/(2950*gravity*np.maximum(abs(diff),50))
        retreat=np.sign(diff)*np.minimum(np.maximum(0,np.abs(slope)-critical)*dt*2e-4,5.)*mask
        move=(flux+retreat)*np.minimum(planation[a],planation[b])
        # Dry wind advects mobile sediment only, never solid bedrock.
        direction=wind[axis];availability=np.maximum(soil[a] if direction>0 else soil[b],0)
        aeolian=np.sign(direction)*np.minimum(availability*.035,dt*1e-5)*np.minimum(dry[a],dry[b])*mask*np.minimum(aeolian_weight[a],aeolian_weight[b])
        move+=aeolian;dz[a]-=move;dz[b]+=move
        dh[a]-=aeolian;dh[b]+=aeolian
    return z+dz,np.maximum(0,soil+dh),dz

def atmosphere(z,g,kind):
    if REAL_CLIMATE:
        return importlib.import_module('tectonics-coupling').forcing(REAL_CLIMATE,g,z)
    dx=g['stepM'];xx,yy=mesh(g);lon,lat=Proj(g['projection'])(xx,yy,inverse=True);coast=edt(kind>=30)*dx;h=blur(z,max(1,12000/dx));gy,gx=np.gradient(h,dx)
    vx=np.where(np.abs(lat)<32,-.85,.85);vy=np.where(lat>0,.35,-.35);supply=.35+1.05*np.exp(-coast/420000)
    up=np.maximum(gx*vx-gy*vy,0);rain=np.clip((.35+supply+np.minimum(2.,up*35))*np.exp(-np.maximum(z-1600,0)/4500),.035,3.5)
    if g.get('region')=='aethelgard':
        back=sample(np.load(WORK/'aethelgard/override.npy'),json.loads((WORK/'aethelgard/grid.json').read_text()),g)>0
        rain[back]*=.35
    temp=30-.34*np.abs(lat)-.0056*z;evap=np.minimum(rain,np.maximum(.03,(temp+6)*.025));recharge=(rain-evap)*.2;runoff=(rain-evap)*.8
    humidity=np.clip(rain/(.5+np.maximum(temp,0)*.05),.02,1);cloud=np.clip(humidity*.6+up*8,0,1)
    pressure=C.get('planet',{}).get('seaLevelPressurePa',110000)*np.exp(-C.get('planet',{}).get('gravityMs2',9.610517)*z/(287.05*np.maximum(220,temp+273.15)))
    return {'rain':rain,'temperature':temp,'evap':evap,'recharge':recharge,'runoff':runoff,'humidity':humidity,'cloud':cloud,'wind-east':vx*8,'wind-north':vy*8,'pressure':pressure}

def evolve(id,seed,step=None):
    out=WORK/id/str(seed);g=json.loads((WORK/id/'grid.json').read_text());g['region']=id;dx=g['stepM'];kind=np.load(WORK/id/'kind.npy');allowpath=WORK/id/'evolution-allow.npy';allow=np.load(allowpath if allowpath.exists() else WORK/id/'allow.npy').astype('float64');z=np.load(out/'initial.npy').astype('float64');initial=z.copy();rate=np.load(out/'uplift-rate.npy');soil=np.full(z.shape,.6);soil[allow==0]=0
    if (out/'kind.npy').exists():kind=np.load(out/'kind.npy')
    if (out/'shore-allow.npy').exists():allow=np.maximum(allow,np.load(out/'shore-allow.npy')*.5)
    allow[(kind<30)|(kind==80)|(kind==200)]=0
    controls=weights(id,g);soil*=controls['soil'];allow*=1-controls['protection'];land=(kind>=30)&(kind!=80);land[[0,-1],:]=False;land[:,[0,-1]]=False
    rate[allow==0]=0
    total_er=np.zeros_like(z);total_dep=np.zeros_like(z);total_up=np.zeros_like(z);total_slope=np.zeros_like(z);ledger=[];now=0;dt0=step or C['stepYears'];clim=atmosphere(z,g,kind)
    np.save(out/'height-0.npy',z.astype('float32'))
    def save_forcing(year,sediment=None):
        cl=atmosphere(z,g,kind);fill,order0,rec0,sl0=F.flood_route(z,land,dx);q0=F.discharge(order0,rec0,cl['runoff']*land,dx*dx)
        for key,a in {'discharge':q0.reshape(z.shape),'receiver':rec0.reshape(z.shape),'sediment-flux':np.zeros_like(z) if sediment is None else sediment.reshape(z.shape)}.items():np.save(out/f'{key}-{year}.npy',a.astype('int32') if key=='receiver' else a.astype('float32'))
    save_forcing(0)
    for target in C['timesYears'][1:]:
        while now<target:
            dt=min(dt0,target-now);before=z.sum(dtype=np.float64)*dx*dx
            u=rate*dt*np.exp(-now/2500000);z+=u;total_up+=u
            cap=np.load(out/'cap-thickness.npy') if now==0 and (out/'cap-thickness.npy').exists() else (cap if now else np.full(z.shape,180.))
            exposed=initial+total_up-z;hard=((exposed<cap)|((np.mod(np.maximum(0,exposed-cap),440)>260))).astype('float64')
            # Weathering is bedrock-to-regolith conversion, not new mass.
            weather=.00004*dt*np.exp(-soil/.7)*(1-hard*.7)*allow*controls['weathering'];soil+=weather
            if now%100000==0:clim=atmosphere(z,g,kind)
            filled,order,rec,slope=F.flood_route(z,land,dx);q=F.discharge(order,rec,clim['runoff']*land,dx*dx)
            z,soil,er,de,export,sed=fluvial(z,soil,order,rec,q,slope,filled,allow,hard,dx,dt,np.zeros(z.size),controls['water'],controls['rock-strength'],C['planet']['gravityMs2'],C['lithology']['hardK'],C['lithology']['softK'])
            z,soil,sl=paired_flux(z,soil,allow,dx,dt,hard,1-clim['humidity'],(.25,-.8),controls['planation'],controls['aeolian'],controls['rock-strength'],C['planet']['gravityMs2']);total_er+=er;total_dep+=de;total_slope+=sl
            after=z.sum(dtype=np.float64)*dx*dx;uplift=float(u.sum()*dx*dx);error=after-before-uplift+export
            receivers=rec[order];outlets=(receivers<0)|~land.ravel()[np.maximum(receivers,0)];qout=float(q[order[outlets]].sum());waterin=float((clim['runoff']*land).sum()*dx*dx)
            ledger.append({'year':now+dt,'dtYears':dt,'upliftM3':uplift,'erodedM3':float(er.sum()*dx*dx),'depositedM3':float(de.sum()*dx*dx),'exportedM3':export,'volumeResidualM3':float(error),'relativeVolumeError':float(abs(error)/max(1,export+abs(uplift))),'waterRelativeError':abs(qout-waterin)/max(1,waterin)})
            now+=dt
        np.save(out/f'height-{target}.npy',z.astype('float32'));log(f'EVOLVED {id} seed {seed}: {target} years');savejson(out/'progress.json',{'year':now,'steps':len(ledger),'lastStep':ledger[-1]})
        save_forcing(target,sed)
    clim=atmosphere(z,g,kind);filled,order,rec,slope=F.flood_route(z,land,dx);q=F.discharge(order,rec,clim['runoff']*land,dx*dx)
    for key,a in {'height':z.astype('float32'),'soil':soil.astype('float32'),'erosion':total_er.astype('float32'),'deposition':total_dep.astype('float32'),'tectonic-uplift':total_up.astype('float32'),'slope-transport':total_slope.astype('float32'),'discharge':q.reshape(z.shape).astype('float32'),'receiver':rec.reshape(z.shape),'sediment-flux':sed.reshape(z.shape).astype('float32'),'pond-depth':np.maximum(filled-z,0).astype('float32'),**{k:v.astype('float32') for k,v in clim.items()}}.items():np.save(out/(key+'.npy'),a)
    fixed=allow==0;report={'solver':'conservative coarse finite volume; nested refinement uses Landlab SPACE','effectiveYears':now,'stepYears':dt0,'protectedMaxDeltaM':float(np.max(np.abs(z[fixed]-initial[fixed]))),'maxWaterRelativeError':max(a['waterRelativeError'] for a in ledger),'maxVolumeRelativeError':max(a['relativeVolumeError'] for a in ledger),'history':ledger}
    if id=='aethelgard':
        plateau=np.load(WORK/id/'override.npy')>0;report['plateauMaxPhysicsDeltaM']=float(np.max(np.abs(z[plateau]-initial[plateau])));report['plateauPhysicsLimitM']=C['plateau']['maxPhysicsChangeM']
    report['climateSource']=importlib.import_module('tectonics-coupling').provenance(REAL_CLIMATE) if REAL_CLIMATE else 'preliminary terrain forcing, not ExoPlaSim';report['gravityMs2']=C['planet']['gravityMs2'];report['gridStepM']=dx
    report['reviewFlags']=[]
    if report.get('plateauMaxPhysicsDeltaM',0)>C['plateau']['maxPhysicsChangeM']:report['reviewFlags'].append('Large plateau change; inspect and tune locally')
    report['passed']=report['protectedMaxDeltaM']<=1e-6 and report['maxWaterRelativeError']<1e-8 and report['maxVolumeRelativeError']<1e-7
    mask_file=(pathlib.Path(MASK)/(id+'.json') if MASK and pathlib.Path(MASK).is_dir() else MASK)
    report['lineage']={'baseSha256':sha(WORK/id/'revised.npy'),'configSha256':hashlib.sha256(json.dumps(C,sort_keys=True).encode()).hexdigest(),'maskSha256':sha(mask_file) if mask_file and pathlib.Path(mask_file).exists() else None,'sourceSnapshotSha256':sha(BASE_WORK/'source-snapshot.json'),'loadedCode':LOADED_CODE_HASHES}
    savejson(out/'simulation.json',report)
    if not report['passed']:raise RuntimeError('Landscape protection limit exceeded: '+id)
    if report['protectedMaxDeltaM']>1e-6 or report['maxWaterRelativeError']>1e-8 or report['maxVolumeRelativeError']>1e-7:raise RuntimeError('Conservation/protection failure '+id)

def main():
    global WORK,C,MASK
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=pathlib.Path,default=ROOT/'data/tectonics-config.json');ap.add_argument('--out',type=pathlib.Path,default=WORK);ap.add_argument('--region',default='all');ap.add_argument('--seed',type=int);ap.add_argument('--mask',type=pathlib.Path);ap.add_argument('--fault-density',type=float);ap.add_argument('--magmatic-intensity',type=float);ap.add_argument('--grid-m',type=int,default=int(os.environ.get('TECTONICS_GRID_M',C['gridStepM'])));ap.add_argument('--years',type=int,default=2000000);ap.add_argument('--stage',choices=['prepare','initial','evolve','all'],default='all');args=ap.parse_args();WORK=args.out;MASK=args.mask;C=json.loads(args.config.read_text(encoding='utf-8'));C['gridStepM']=args.grid_m;C['timesYears']=[t for t in C['timesYears'] if t<=args.years]
    if args.fault_density is not None:C['faultDensity']=args.fault_density
    if args.magmatic_intensity is not None:C['magmatism']['intensity']=args.magmatic_intensity
    WORK.mkdir(parents=True,exist_ok=True);savejson(WORK/'run-config.json',C)
    snap=json.loads((BASE_WORK/'source-snapshot.json').read_text());
    for f,h in snap['hashes'].items():
        if f!='foundation/manifest.json' and sha(ROOT/f)!=h:raise RuntimeError('Formal input changed: '+f)
    for id in C['regions'] if args.region=='all' else [args.region]:
        if args.stage in ['prepare','all']:prepare(id)
        for seed in [args.seed] if args.seed else C['seeds']:
            if args.stage in ['initial','all']:initial(id,seed)
            if args.stage in ['evolve','all']:evolve(id,seed)
            gc.collect()
if __name__=='__main__':main()
