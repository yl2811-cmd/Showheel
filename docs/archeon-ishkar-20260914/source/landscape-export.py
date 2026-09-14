"""Baked review assets, complete river/lake vectors and small browser meshes."""
import pathlib,sys,importlib,json,argparse,hashlib,time
sys.path.insert(0,str(pathlib.Path(__file__).parent));L=importlib.import_module('tectonics-landscape');T=L.T;np=T.np;E=importlib.import_module('tectonics-export');C=importlib.import_module('tectonics-cycle-export')
from scipy.ndimage import label
from rasterio.features import shapes
from affine import Affine
OUT=T.ROOT/'foundation/landscape'
def write(name,value):L.save(OUT/name,value)
def lines(g,q,rec,threshold=1e9):
    f=q.ravel();r=rec.ravel();valid=(f>=threshold)&(r>=0)&(r!=np.arange(len(r)));up=np.bincount(r[valid],minlength=len(r));starts=np.flatnonzero(valid&(up!=1));used=np.zeros(len(r),bool);result=[];p=T.Proj(g['projection'])
    for start in starts:
        if used[start]:continue
        chain=[int(start)];i=int(start)
        while valid[i] and not used[i]:
            used[i]=True;j=int(r[i]);chain.append(j)
            if not valid[j] or up[j]!=1:break
            i=j
        if len(chain)<2:continue
        rows=np.array(chain)//g['width'];cols=np.array(chain)%g['width'];lo,la=p(g['xmin']+cols*g['stepM'],g['ymax']-rows*g['stepM'],inverse=True)
        result.append({'type':'Feature','id':'river-'+str(start),'geometry':{'type':'LineString','coordinates':np.column_stack([lo,la]).round(7).tolist()},'properties':{'maximumDischargeM3s':float(f[chain].max()/31557600),'headDischargeM3s':float(f[start]/31557600),'gridM':g['stepM'],'source':'computed receiver links','screen':np.column_stack([cols/(g['width']-1),rows/(g['height']-1)]).tolist()}})
    return result
def lakes(g,z,depth,occurrence):
    lab,n=label(depth>.05,np.ones((3,3),int));areas=np.bincount(lab.ravel())*g['stepM']**2;transform=Affine(g['stepM'],0,g['xmin']-g['stepM']/2,0,-g['stepM'],g['ymax']+g['stepM']/2);p=T.Proj(g['projection']);features=[]
    def convert(coords):
        if isinstance(coords[0],(int,float)):return list(p(*coords,inverse=True))
        return [convert(v) for v in coords]
    for geometry,value in shapes(lab.astype('int32'),mask=lab>0,transform=transform):
        i=int(value);m=lab==i
        features.append({'type':'Feature','id':'lake-'+str(i),'geometry':{'type':geometry['type'],'coordinates':convert(geometry['coordinates'])},'properties':{'areaKm2':float(areas[i]/1e6),'volumeM3':float(depth[m].sum()*g['stepM']**2),'surfaceM':float(np.median((z+depth)[m])),'maximumDepthM':float(depth[m].max()),'seasonalWetFraction':float(occurrence[m].mean()),'state':'perennial-in-scenario' if occurrence[m].min()>.99 else 'seasonal-in-scenario','gridM':g['stepM'],'notRealClimateValidated':True}})
    return features
def complete(folder):
    if not all((folder/name).exists() for name in ['simulation.json','run-key.json','request.json']):return False
    key=L.read(folder/'run-key.json');request=L.read(folder/'request.json');r=L.read(folder/'simulation.json')
    return key['key']==L.fingerprint(request) and r.get('effectiveYears')==request['end'] and r.get('passed')
def candidate(folder,g,prefix):
    request=L.read(folder/'request.json');report=L.read(folder/'simulation.json');initial=np.load(folder/'initial.npy');kind0=np.load(folder/'kind-0.npy');core=np.load(folder/'protected.npy');stages=[]
    source=L.WORK/'base'/g['region']/str(request['seed']);sg=L.read(source/'grid.json');old=T.sample(np.load(source/'original.npy'),sg,g);coarse=L.read(source/'repair.json')
    c={'seed':request['seed'],'mode':request['mode'],'scenario':request['scenario'],'gain':request['gain'],'baseline':prefix+'-old.png','baselineMesh':E.height_mesh(prefix+'-old.f32',np.where(kind0==0,0,old),420),'stages':stages,'faults':[],'checks':{k:v for k,v in report.items() if k!='history'},'processYear':report['effectiveYears']}
    E.write_image(c['baseline'],E.elevation(E.down(old)),E.down(kind0,1600,0));soil=np.load(folder/'soil.npy');sand=np.load(folder/'sand.npy');occ=np.load(folder/'lake-occurrence.npy');fields=['erosion','deposition','tectonic-uplift','weathering','soil','sand','lake-depth','wetness']
    for year in sorted(int(p.stem.split('-')[-1]) for p in folder.glob('height-*.npy') if int(p.stem.split('-')[-1])<=report['effectiveYears']):
        z=np.load(folder/f'height-{year}.npy');kind=np.load(folder/f'kind-{year}.npy');depth=np.load(folder/f'lake-depth-{year}.npy');displaykind=kind.copy();displaykind[depth>.05]=200;small=E.down(z);dk=E.down(displaykind,1600,0);name=f'{prefix}-{year}';ys=np.load(folder/f'soil-{year}.npy');ground=C.ground(small,E.down(ys),E.down(np.minimum(sand,ys)),g['stepM']*z.shape[0]/small.shape[0]);rgb=E.elevation(small);meshz=np.where(kind==0,0,z+depth)
        stage={'year':year,'label':'重建地面与成形源点' if year==0 else f'{year/10000:g} 万有效年','height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','lake-depth':name+'-lake-depth.png','discharge':name+'-discharge.png','mesh':E.height_mesh(name+'.f32',meshz,420),'stats':E.stats(z,initial,displaykind,g['stepM'])}
        E.write_image(stage['height'],rgb,dk);E.write_image(stage['ground'],ground,dk);E.write_image(stage['change'],E.signed(E.down(z-initial),500),dk);E.write_image(stage['lake-depth'],E.plt.get_cmap('Blues')(np.clip(np.log1p(E.down(depth))/np.log(501),0,1))[:,:,:3]*255,E.down(kind,1600,0))
        q=np.load(folder/f'discharge-{year}.npy');rec=np.load(folder/f'receiver-{year}.npy');E.write_image(stage['discharge'],E.plt.get_cmap('viridis')(np.clip(np.log10(1+E.down(q))/12,0,1))[:,:,:3]*255,E.down(kind,1600,0));river=lines(g,q,rec);display=sorted(river,key=lambda v:v['properties']['maximumDischargeM3s'],reverse=True)[:1600];stage['routes']=[{'screen':v['properties']['screen'],'name':'模拟河流'} for v in display]
        if year==report['effectiveYears']:
            for f in river:f['properties'].pop('screen',None)
            write(prefix+'-rivers.geojson',{'type':'FeatureCollection','properties':{'scenario':request['scenario'],'gain':request['gain'],'gridM':g['stepM'],'candidateOnly':True},'features':river});lake=lakes(g,z,depth,occ);write(prefix+'-lakes.geojson',{'type':'FeatureCollection','properties':{'scenario':request['scenario'],'candidateOnly':True},'features':lake});c['riverVector']=prefix+'-rivers.geojson';c['lakeVector']=prefix+'-lakes.geojson';c['riverSegments']=len(river);c['lakePolygons']=len(lake)
        if g['stepM']<=2000:
            delta=(z-initial)[4:-4,4:-4];stage['localStats']={'loweringM':float(np.maximum(0,-delta).max()),'raisingM':float(np.maximum(0,delta).max()),'reliefM':float(np.ptp(z[4:-4,4:-4]))}
        stages.append(stage)
    for field in fields:
        data=E.down(np.load(folder/(field+'.npy')));name=prefix+'-'+field+'.png'
        if field in ['soil','sand','weathering']:rgb=E.plt.get_cmap('YlOrBr')(np.clip(np.log1p(np.maximum(data,0))/np.log(101),0,1))[:,:,:3]*255
        elif field=='wetness':rgb=E.plt.get_cmap('YlGnBu')(np.clip(data,0,1))[:,:,:3]*255
        elif field=='lake-depth':rgb=E.plt.get_cmap('Blues')(np.clip(np.log1p(np.maximum(data,0))/np.log(501),0,1))[:,:,:3]*255
        else:rgb=E.signed(data,600)
        E.write_image(name,rgb,E.down(np.load(folder/'kind.npy'),1600,0) if field not in ['lake-depth'] else None);c[field]=name
    final=np.load(folder/'height.npy');gy,gx=np.gradient(final,g['stepM']);normal=np.stack([-gx,gy,np.ones_like(gx)],axis=-1);normal/=np.linalg.norm(normal,axis=-1,keepdims=True);c['normal']=prefix+'-normal.png';E.write_image(c['normal'],E.down((normal+1)*127.5))
    retention=L.read(folder/'retention.json');c['retention']={k:v for k,v in retention.items() if k!='features'};c['sourceFolder']=folder.relative_to(L.WORK).as_posix();c['requestFingerprint']=L.fingerprint(request)
    for f in L.read(folder/'source-catalog.json'):
        x,y=f['xy'];a=f['angleRadians'];length=f['lengthM'];c['faults'].append({'mode':'normal','screen':[[(x+sign*np.cos(a)*length-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-y-sign*np.sin(a)*length)/((g['height']-1)*g['stepM'])] for sign in [-1,1]]})
    return c
def export():
    L.setup();OUT.mkdir(exist_ok=True);E.OUT=OUT;regions={};previous=L.read(OUT/'manifest.json') if (OUT/'manifest.json').exists() else {'regions':[]};cache={c.get('sourceFolder'):c for r in previous['regions'] for c in r['candidates']};specs={s['id']:s for s in L.specifications()}
    for stage in ['coarse','regional','detail','continental','river-detail']:
        for path in sorted((L.WORK/stage).glob('**/simulation.json')):
            folder=path.parent
            if not complete(folder):continue
            g=L.read(folder/'grid.json');request=L.read(folder/'request.json');rid=stage+'-'+g['id'];prefix=rid+'-'+str(request['seed'])+'-'+request['mode']+'-'+request['scenario']+'-'+str(request['gain']).replace('.','p');old=cache.get(folder.relative_to(L.WORK).as_posix());key=L.fingerprint(request)
            c=old if old and old.get('requestFingerprint')==key else candidate(folder,g,prefix)
            if rid not in regions:
                title=specs.get(g['id'],{}).get('title',{'aethelgard':'Aethelgard','vorhan':'Vorhan','duskreach':'Duskreach','keld':'Keld'}.get(g['id'],g['id']));title+=f' · {g["stepM"]/1000:g} km' if g['stepM']>=1000 else f' · {g["stepM"]:g} m';name=rid+'-protected.png';E.write_image(name,np.where((E.down(np.load(folder/'protected.npy'),1600,0)>0)[:,:,None],[56,147,133],[226,214,185])+np.zeros((*E.down(np.load(folder/'kind.npy'),1600,0).shape,3)))
                regions[rid]={'id':rid,'title':title,'grid':g,'width':g['width'],'height':g['height'],'baseline':c['baseline'],'revised':c['stages'][0]['height'],'baselineMesh':c['baselineMesh'],'protected':name,'candidates':[],'markers':C.markers(g,L.X.bank_site()),'oldRoutes':[],'group':None if stage=='coarse' else stage}
                p=T.Proj(g['projection'])
                for river in T.D['rivers']:
                    if river['geometry']['type']!='LineString':continue
                    xy=np.array([p(*q) for q in river['geometry']['coordinates']]);uv=np.column_stack([(xy[:,0]-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-xy[:,1])/((g['height']-1)*g['stepM'])]);inside=((uv>=0)&(uv<=1)).all(axis=1)
                    if inside.any():regions[rid]['oldRoutes'].append({'screen':uv.tolist(),'name':river.get('properties',{}).get('name','旧河道')})
            regions[rid]['candidates'].append(c)
    manifest={'version':L.CFG['version'],'studyKey':'erosion','bakeBase':'foundation/landscape/','candidateOnly':True,'createdUnix':time.time(),'regions':list(regions.values()),'scenarios':{'dry':'偏干 · 0.5×','baseline':'基准 · 1×','wet':'偏湿 · 1.5×'},'enhancements':[1,1.5,2],'scope':'形成与保留特色地貌；季节河湖为情景结果；真实气候、植被和航线仍在后续','completion':{'candidateViews':len(regions),'completedRuns':sum(len(v['candidates']) for v in regions.values())}}
    write('manifest.json',manifest);(OUT/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(manifest,ensure_ascii=False,default=T.json_scalar)+';',encoding='utf8');print(json.dumps(manifest['completion']))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=L.WORK);a=ap.parse_args();L.WORK=a.work;export()
