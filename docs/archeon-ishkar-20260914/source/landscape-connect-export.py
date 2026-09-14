"""Review assets for the bounded Ishkar connection pass, without age claims."""
import pathlib,sys,importlib,json,time,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('landscape-connect');L=C.L;T=L.T;np=L.np
E=importlib.import_module('tectonics-export');V=importlib.import_module('landscape-export');CE=importlib.import_module('tectonics-cycle-export')
from scipy.ndimage import label,zoom
from rasterio.features import shapes
from affine import Affine
OUT=T.ROOT/'foundation/landscape-v14'

def down(a,size=1600,order=1):
 factor=min(1,size/max(a.shape[:2]));return zoom(a,(factor,factor)+( (1,) if a.ndim==3 else ()),order=order,prefilter=False) if factor<1 else a

def lake_vectors(g,z,depth,occ):
 lab,n=label(depth>.05,np.ones((3,3)));flat=lab.ravel();area=np.bincount(flat)*g['stepM']**2;volume=np.bincount(flat,weights=depth.ravel())*g['stepM']**2;surface=np.bincount(flat,weights=(z+depth).ravel())/np.maximum(1,np.bincount(flat));maximum=np.zeros(n+1);np.maximum.at(maximum,flat,depth.ravel());frequency=np.bincount(flat,weights=occ.ravel())/np.maximum(1,np.bincount(flat));p=T.Proj(g['projection']);transform=Affine(g['stepM'],0,g['xmin']-g['stepM']/2,0,-g['stepM'],g['ymax']+g['stepM']/2)
 def convert(a):return list(p(*a,inverse=True)) if isinstance(a[0],(int,float)) else [convert(v) for v in a]
 return [{'type':'Feature','id':f'lake-{int(i)}','geometry':{'type':geo['type'],'coordinates':convert(geo['coordinates'])},'properties':{'areaKm2':float(area[int(i)]/1e6),'volumeM3':float(volume[int(i)]),'surfaceM':float(surface[int(i)]),'maximumDepthM':float(maximum[int(i)]),'seasonalWetFraction':float(frequency[int(i)]),'scenarioOnly':True,'gridM':g['stepM']}} for geo,i in shapes(lab.astype('int32'),mask=lab>0,transform=transform)]

def write(name,value):L.save(OUT/name,value)

def candidate(folder,source,g,prefix):
 request=L.read(folder/'request.json');hyd=L.read(folder/'hydrology.json');story=L.read(folder/'story-geography.json');z=np.load(source/'height.npy');before=np.load(source/'before.npy');kind=np.load(source/'kind.npy');depth=np.load(folder/'lake-depth.npy');occ=np.load(folder/'lake-occurrence.npy');q=np.load(folder/'discharge.npy');rec=np.load(folder/'receiver.npy');catchment=np.load(folder/'ishkar-catchment.npy');soil=np.load(source/'soil.npy');small=down(z);k=down(kind,order=0);dk=k.copy();dk[down(depth)>.05]=200
 prefix=prefix.replace('.','p');base=prefix+'-before.png';E.write_image(base,E.elevation(down(before)),k);oldmesh=E.height_mesh(prefix+'-before.f32',np.where(kind==0,0,before),420)
 image_fields={'height':(E.elevation(small),dk),'ground':(E.ground(small,g['stepM']*len(z)/len(small)),dk),'bed':(E.elevation(small),k),'change':(E.signed(down(z-before),60),k),'lake-depth':(E.plt.get_cmap('Blues')(np.clip(np.log1p(down(depth))/np.log(501),0,1))[:,:,:3]*255,k),'discharge':(E.plt.get_cmap('viridis')(np.clip(np.log10(1+down(q))/12,0,1))[:,:,:3]*255,k),'wetness':(E.plt.get_cmap('YlGnBu')(down(np.load(folder/'wetness.npy')))[:,:,:3]*255,k),'ishkar-catchment':(np.where(down(catchment,order=0)[:,:,None],[71,146,121],[218,215,193])+np.zeros((*k.shape,3)),k),'story-constraints':(np.where((down(np.load(source/'story-constraints.npy'))>.35)[:,:,None],[191,151,89],[228,224,210])+np.zeros((*k.shape,3)),k)}
 stage={'year':0,'label':'当前地形 · 季节河湖检验','mesh':E.height_mesh(prefix+'-water.f32',np.where(kind==0,0,z+depth),420),'bedMesh':E.height_mesh(prefix+'-bed.f32',np.where(kind==0,0,z),420),'stats':E.stats(z,before,kind,g['stepM'])}
 for name,(rgb,mask) in image_fields.items():stage[name]=prefix+'-'+name+'.png';E.write_image(stage[name],rgb,mask)
 # Lake interiors are water polygons, not artificial straight river links to
 # a reservoir representative. Rivers end at the shore and resume at spill.
 rivers=V.lines(g,q,np.where(depth>.05,-1,rec),threshold=2e9);display=[]
 for f in rivers:
  node=int(f['id'].split('-')[-1]);f['properties']['system']='Ishkar' if catchment.ravel()[node] else 'independent';f['properties']['scenario']=request['scenario']
 for f in sorted(rivers,key=lambda f:f['properties']['maximumDischargeM3s'],reverse=True)[:1400]:display.append({'screen':f['properties']['screen'],'name':f['properties']['system']})
 stage['routes']=display
 for f in rivers:f['properties'].pop('screen',None)
 lake=lake_vectors(g,z,depth,occ);write(prefix+'-rivers.geojson',{'type':'FeatureCollection','properties':{'candidateOnly':True,'scenario':request['scenario'],'gridM':g['stepM']},'features':rivers});write(prefix+'-lakes.geojson',{'type':'FeatureCollection','properties':{'candidateOnly':True,'scenario':request['scenario']},'features':lake});write(prefix+'-checks.json',{'hydrology':{k:v for k,v in hyd.items() if k not in ['lakes','activeStoryBasins']},'story':story,'connection':L.read(source/'connection.json')})
 connection=L.read(source/'connection.json');joined=[s['name'] for s in connection['sites'] if s['centerOnIshkarCatchment']]
 return {'seed':g['seed'],'mode':'hydrology','scenario':request['scenario'],'gain':1,'label':'固定种子 '+str(g['seed']),'baseline':base,'baselineMesh':oldmesh,'baselineGround':base,'stages':[stage],'faults':[],'processYear':0,'riverVector':prefix+'-rivers.geojson','lakeVector':prefix+'-lakes.geojson','lakePolygons':len(lake),'checks':{'waterRelativeError':hyd['maxWaterRelativeError'],'waterConvergence':hyd['convergence'],'storyGeography':story,'joinedSites':joined,'IshkarCatchmentKm2':float(catchment.sum()*g['stepM']**2/1e6)},'checkFile':prefix+'-checks.json','scope':'seasonal water on retained terrain; no new geological years or uplift','sourceFolder':folder.relative_to(L.WORK).as_posix(),'requestFingerprint':L.fingerprint(request),'exporterSha256':T.sha(pathlib.Path(__file__)),'diagnosticFingerprint':L.fingerprint({'story':T.sha(folder/'story-geography.json'),'connection':T.sha(source/'connection.json')})}

def export():
 OUT.mkdir(exist_ok=True);E.OUT=OUT;regions={};previous=L.read(OUT/'manifest.json') if (OUT/'manifest.json').exists() else {'regions':[]};cache={c['sourceFolder']:c for r in previous['regions'] for c in r['candidates']};exporter=T.sha(pathlib.Path(__file__))
 for folder in sorted((L.WORK/'connected').glob('*/*')):
  if not (folder/'hydrology.json').exists():continue
  g=L.read(folder/'grid.json');source=L.WORK/'connection-base'/str(g['seed']);rid='connected-aethelgard';prefix=f'{rid}-{g["seed"]}-{folder.name}';old=cache.get(folder.relative_to(L.WORK).as_posix());key=L.fingerprint(L.read(folder/'request.json'));c=old if old and old.get('exporterSha256')==exporter and old['requestFingerprint']==key and old.get('diagnosticFingerprint')==L.fingerprint({'story':T.sha(folder/'story-geography.json'),'connection':T.sha(source/'connection.json')}) else candidate(folder,source,g,prefix)
  if rid not in regions:
   regions[rid]={'id':rid,'title':'Aethelgard · Ishkar 汇流 · 2 km','grid':g,'width':g['width'],'height':g['height'],'baselineLabel':'连接小修前的地形','baseline':c['baseline'],'baselineMesh':c['baselineMesh'],'revised':c['stages'][0]['height'],'candidates':[],'markers':CE.markers(g,L.X.bank_site()),'oldRoutes':[],'group':None}
   p=T.Proj(g['projection'])
   for river in T.D['rivers']:
    if river.get('id')!='ishkar':continue
    xy=np.array([p(*q) for q in river['geometry']['coordinates']]);regions[rid]['oldRoutes'].append({'name':'旧 Ishkar 参考线','screen':np.column_stack([(xy[:,0]-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-xy[:,1])/((g['height']-1)*g['stepM'])]).tolist()})
  regions[rid]['candidates'].append(c)
 manifest={'version':'archeon-ishkar-connection-v14','studyKey':'erosion','bakeBase':'foundation/landscape-v14/','candidateOnly':True,'createdUnix':time.time(),'regions':list(regions.values()),'scenarios':{'dry':'偏干 · 0.5×','baseline':'基准 · 1×','wet':'偏湿 · 1.5×'},'enhancements':[1],'scope':'User narrowed the remaining work to small drainage connections to Ishkar. Larger geological runs are deferred.','finalized':False,'completion':{'completedRuns':sum(len(r['candidates']) for r in regions.values()),'candidateViews':len(regions)}}
 write('manifest.json',manifest);(OUT/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(manifest,ensure_ascii=False,default=T.json_scalar)+';',encoding='utf8');print(manifest['completion'])
if __name__=='__main__':export()
