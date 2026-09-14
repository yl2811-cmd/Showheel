"""Bake current terrain and water into the atlas projection, no new simulation."""
import pathlib,sys,importlib,json,hashlib,time
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');np=T.np
from PIL import Image
from scipy.ndimage import map_coordinates
OUT=T.ROOT/'world-rebuild';WORK=T.BASE_WORK;meta=json.loads((OUT/'projection.json').read_text());view=meta['view'];W=6000;factor=W/view['width'];H=round(view['height']*factor);R=meta['radiusM'];scale=meta['scale'];tx,ty=meta['translate'];projection=T.Proj(proj='eqearth',R=R)
sources=[]
for region in ['aethelgard','vorhan','duskreach','keld']:
 folder=WORK/'landscape-v14/connection-base/5210914' if region=='aethelgard' else WORK/'landscape-v13/coarse'/region/'5210914/erosion-only/baseline/g1'
 if region!='aethelgard':assert json.loads((folder/'simulation.json').read_text())['passed']
 g=json.loads((folder/'grid.json').read_text());z=np.load(folder/'height.npy');k=np.load(folder/'kind.npy');land=(k>=30)&(k!=80);sources.append({'region':region,'folder':folder,'grid':g,'project':T.Proj(g['projection']),'height':z*land,'land':land.astype('float32')})
native=np.asarray(Image.open(T.ROOT/'terrain/world-mask.png').convert('L').resize((W,H),Image.Resampling.NEAREST));base=np.empty((H,W,3),np.uint8);base[:]=[35,56,65];base[native>=30]=[173,177,163];base[native==80]=[131,140,140];rgb=base.copy();coverage=np.zeros((H,W),np.uint8)
stops=np.array([[53,173,104],[54,120,207],[241,220,85],[244,154,56],[216,71,72],[134,66,180]],float)
def colors(z):
 t=np.clip(z/1600,0,5);i=np.minimum(4,t.astype(int));f=t-i;return (stops[i]*(1-f[...,None])+stops[i+1]*f[...,None]).astype('uint8')
for y in range(0,H,96):
 end=min(H,y+96);px,py=np.meshgrid((np.arange(W)+.5)/factor,(np.arange(y,end)+.5)/factor);mx=(px-tx)*R/scale;my=-(py-ty)*R/scale;lon,lat=projection(mx,my,inverse=True);valid=np.isfinite(lon)&np.isfinite(lat)&(abs(lon)<=180)&(abs(lat)<=90);lon=np.where(valid,lon,0);lat=np.where(valid,lat,0);native_land=(native[y:end]>=30)&(native[y:end]!=80)&valid
 for code,source in enumerate(sources,1):
  xq,yq=source['project'](lon,lat);g=source['grid'];rr=(g['ymax']-yq)/g['stepM'];cc=(xq-g['xmin'])/g['stepM'];inside=(rr>=0)&(rr<=g['height']-1)&(cc>=0)&(cc<=g['width']-1)&native_land
  if not inside.any():continue
  rr=np.where(inside,rr,0);cc=np.where(inside,cc,0);support=map_coordinates(source['land'],[rr,cc],order=1,mode='nearest',prefilter=False);h=map_coordinates(source['height'],[rr,cc],order=1,mode='nearest',prefilter=False)/np.maximum(support,1e-6);take=inside&(support>.01);rgb[y:end][take]=colors(h[take]);coverage[y:end][take]=code
 print('WORLD BAKE',end,H,flush=True) if end%960==0 else None
Image.fromarray(base).save(OUT/'world-base.png',compress_level=2);Image.fromarray(rgb).save(OUT/'world-height.png',compress_level=2)
lineage=[{'region':s['region'],'source':str(s['folder']),'heightSha256':T.sha(s['folder']/'height.npy'),'gridM':s['grid']['stepM'],'waterStatus':'current' if s['region']=='aethelgard' else 'wip','pixels':int((coverage==i).sum())} for i,s in enumerate(sources,1)]
waterdir=T.ROOT/'foundation/landscape-v14';features=[]
for suffix in ['rivers','lakes']:
 p=waterdir/f'connected-aethelgard-5210914-baseline-{suffix}.geojson';features+=json.loads(p.read_text(encoding='utf8'))['features']
(OUT/'water.geojson').write_text(json.dumps({'type':'FeatureCollection','properties':{'region':'aethelgard','scenario':'baseline','climateCorrection':'WIP','source':'current completed bake'},'features':features},ensure_ascii=False),encoding='utf8')
g=sources[0]['grid'];rec=np.load(WORK/'landscape-v14/connected/5210914/baseline/receiver.npy');q=np.load(WORK/'landscape-v14/connected/5210914/baseline/discharge.npy');p=sources[0]['project'];x,y=p(.3,27);node=round((g['ymax']-y)/g['stepM'])*g['width']+round((x-g['xmin'])/g['stepM']);path=[]
for _ in range(rec.size):
 row,col=divmod(int(node),g['width']);path.append(list(p(g['xmin']+col*g['stepM'],g['ymax']-row*g['stepM'],inverse=True)));next_node=int(rec.ravel()[node])
 if next_node<0 or next_node==node:break
 node=next_node
bank=next(s for s in json.loads((WORK/'landscape-v14/connection-base/5210914/connection.json').read_text(encoding='utf8'))['sites'] if s['name']=='Riverbend');rb=next(f for f in T.D['settlements'] if f['id']=='RB');rb=json.loads(json.dumps(rb));rb['geometry']['coordinates']=bank['center'];rb['properties'].update(mapRevisionOnly=True,source='当前 Ishkar 岸地烘焙')
named=[rb,{'type':'Feature','id':'ishkar','geometry':{'type':'LineString','coordinates':path},'properties':{'name':'Ishkar','kind':'river','description':'按当前高程重新汇流的主干。气候与湖水校正仍在进行。','source':'当前高程与水流烘焙','positionStatus':'inferred','extentStatus':'inferred'}}]
(OUT/'named-features.json').write_text(json.dumps(named,ensure_ascii=False),encoding='utf8')
errors=[]
for anchor in meta['anchors']:
 x,y=projection(*anchor['q']);errors.append(float(np.linalg.norm(np.array([x*scale/R+tx,-y*scale/R+ty])-anchor['pixel'])))
assert max(errors)<1e-5,errors
record={'version':'world-rebuild-20260914','status':'WIP','view':'world','imageWidth':W,'imageHeight':H,'imageDisplayHeight':H/factor,'heightStatus':'current','waterCoverage':['aethelgard'],'pending':['vegetation-surface','circulation','humidity-climate','routes','contours','other-thematic-layers'],'sources':lineage,'projectionMaxErrorPixels':max(errors),'heightColors':'altitude only, not vegetation or humidity','resampling':'bilinear height over land support; inherited coastline mask; no new erosion or climate simulation','createdUnix':time.time()}
(OUT/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print('WORLD HEIGHT READY',W,H)
