"""Bake browser textures and small metre meshes from numerical output only."""
import pathlib,sys,json,math,gc,importlib,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model')
np=T.np;Image=T.Image;ROOT=T.ROOT;WORK=T.WORK;OUT=ROOT/'foundation/tectonics';OUT.mkdir(parents=True,exist_ok=True)
from scipy.ndimage import gaussian_filter,zoom,label,maximum_filter
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
STOPS=np.array([[53,173,104],[54,120,207],[241,220,85],[244,154,56],[216,71,72],[134,66,180]])
cmap=LinearSegmentedColormap.from_list('altitude',STOPS/255)
def elevation(z):
    t=np.clip(z/1600,0,5);i=np.minimum(4,t.astype(int));f=t-i;rgb=(STOPS[i]*(1-f[:,:,None])+STOPS[i+1]*f[:,:,None])
    below=z<0;depth=np.clip(-z/2000,0,1)[:,:,None];negative=np.array([53,173,104])*(1-depth)+np.array([97,67,107])*depth;rgb[below]=negative[below]
    return rgb.astype('uint8')
def down(a,maxsize=1600,order=1):
    scale=min(1,maxsize/max(a.shape));return zoom(a,scale,order=order,prefilter=False) if scale<1 else a
def write_image(name,rgb,kind=None):
    if kind is not None:
        rgb=rgb.copy();rgb[kind==0]=[35,56,65];rgb[kind==80]=[132,137,134];rgb[kind==200]=[139,186,196]
    Image.fromarray(rgb.astype('uint8')).save(OUT/name,compress_level=2)
def ground(z,step,humidity=None):
    gy,gx=np.gradient(z,step);shade=np.clip((1-gx*.6+gy*.35)/np.sqrt(1+gx*gx+gy*gy),.3,1.2)
    col=np.zeros((*z.shape,3))+[169,139,108];bands=(np.sin(z/90)*.5+.5)*T.ease((np.hypot(gx,gy)-.025)/.15);col+=bands[:,:,None]*np.array([13,9,7]);col+=np.clip(z/10000,0,1)[:,:,None]*[-30,-20,-8]
    if humidity is not None:green=np.clip(humidity-.4,0,.45)[:,:,None];col=col*(1-green)+np.array([62,100,73])*green
    # Snow is a GCM output. Height alone must not paint a snow cap.
    return np.clip(col*shade[:,:,None],0,255).astype('uint8')
def signed(a,limit=1500):
    strength=np.clip(abs(a)/limit,0,1)[:,:,None];color=np.where((a>0)[:,:,None],[211,86,47],[47,125,201]);return np.array([236,230,213])*(1-strength)+color*strength
def height_mesh(name,z,maxsize=320):
    a=down(z,maxsize);a.astype('<f4').tofile(OUT/name);return {'file':name,'width':a.shape[1],'height':a.shape[0]}
def stats(z,old,kind,step,area=None):
    land=(kind>=30)&(kind!=80)&(kind!=200);high=(z>2500)&land;labs,n=label(high);count=np.bincount(labs.ravel());regions=[]
    if area is None:area=np.full(z.shape,step*step,dtype=float)
    sizes=np.bincount(labs.ravel(),weights=area.ravel())
    for i in np.where(sizes>1e10)[0]:
        if i==0:continue
        m=labs==i;regions.append({'areaKm2':float(sizes[i]/1e6),'peakM':float(z[m].max()),'p10M':float(np.percentile(z[m],10)),'localReliefM':float(z[m].max()-np.percentile(z[m],10))})
    return {'meanChangeM':float(np.average(z[land]-old[land],weights=area[land])),'meanAbsChangeM':float(np.average(abs(z[land]-old[land]),weights=area[land])),'rangeM':[float(z[land].min()),float(z[land].max())],'highlandAreaKm2':float(area[high].sum()/1e6),'highlandsOver10000Km2':regions,'newHighlandAreaKm2':float(area[high&(old<=2500)].sum()/1e6)}
def diagnostics():
    if not (WORK/'aethelgard/revised.npy').exists():return
    g=json.loads((WORK/'aethelgard/grid.json').read_text());b=np.load(WORK/'aethelgard/baseline.npy');z=np.load(WORK/'aethelgard/revised.npy');mask=np.load(WORK/'aethelgard/override.npy');kind=np.load(WORK/'aethelgard/kind.npy')
    # Same crop, altitude ramp and physical limits for an honest comparison.
    jj,ii=np.where(mask);ys=slice(max(0,jj.min()-60),min(len(z),jj.max()+60));xs=slice(max(0,ii.min()-80),min(z.shape[1],ii.max()+80))
    fig,ax=plt.subplots(1,2,figsize=(16,7),layout='constrained',facecolor='#ebe5d5')
    for a,f,title in zip(ax,[b,z],['BEFORE / inherited terrain','REVISED / fault blocks and coastal ramp']):
        rgb=elevation(f[ys,xs]);rgb[kind[ys,xs]==0]=[35,56,65];a.imshow(rgb);a.set_title(title);a.axis('off')
    fig.savefig(OUT/'orun-plateau-before-after.png',dpi=150);plt.close(fig)
    log={'before':stats(b,b,kind,g['stepM']),'after':stats(z,b,kind,g['stepM'])};T.savejson(OUT/'plateau.json',{**json.loads((WORK/'aethelgard/plateau-report.json').read_text()),'registration':json.loads((WORK/'markup.geojson').read_text())['properties']})
def nested_item(folder,config,seed=5210914):
    g=json.loads((folder/'grid.json').read_text());old=np.load(folder/'initial.npy');kind=np.load(folder/'kind.npy');dk=down(kind,1600,0);id=config['id'];prefix='nested-'+id;small=down(old)
    write_image(prefix+'-before.png',elevation(small),dk);write_image(prefix+'-protected.png',np.where((down(np.load(folder/'protected.npy'),1600,0)>0)[:,:,None],[56,147,133],[226,214,185])+np.zeros((*dk.shape,3)),dk)
    titles={'orun-back':'Orun · 高原支谷','whisperflat':'Whisperflat · 升高的浅盆','north-west':'北部高地 · 西组','north-center':'北部高地 · 中组','north-east':'北部高地 · 东组','vorhan-rift':'Vorhan · 裂谷细部','dusk-plateau':'Duskreach · 台地细部','keld-arc':'Keld · 岛弧细部','orun-cliff64':'Orun · 64 m 岩阶'}
    item={'id':id,'title':titles.get(id,id),'grid':g,'width':dk.shape[1],'height':dk.shape[0],'baseline':prefix+'-before.png','revised':prefix+'-before.png','protected':prefix+'-protected.png','baselineMesh':height_mesh(prefix+'-before.f32',old),'candidates':[],'markers':[]};cand={'seed':seed,'stages':[],'faults':[]}
    for year in T.C['timesYears']:
        f=folder/f'height-{year}.npy'
        if not f.exists():continue
        z=np.load(f);s=down(z);name=prefix+'-'+str(year);write_image(name+'-height.png',elevation(s),dk);write_image(name+'-ground.png',ground(s,g['stepM']*len(z)/len(s)),dk);write_image(name+'-change.png',signed(down(z-old),500),dk);cand['stages'].append({'year':year,'height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','mesh':height_mesh(name+'.f32',z),'stats':stats(z,old,kind,g['stepM'])})
    for field in ['erosion','deposition','tectonic-uplift','rain','humidity','cloud','temperature','pressure','wind-east','wind-north','discharge']:
        f=folder/(field+'.npy')
        if not f.exists():continue
        a=down(np.load(f));name=prefix+'-'+field+'.png'
        if field in ['erosion','deposition','tectonic-uplift']:rgb=signed(a,600)
        else:
            lo,hi={'rain':(0,3.5),'humidity':(0,1),'cloud':(0,1),'temperature':(-30,35),'pressure':(15000,130000),'wind-east':(-10,10),'wind-north':(-10,10),'discharge':(0,12)}[field]
            if field=='discharge':a=np.log10(1+a)
            rgb=plt.get_cmap('coolwarm' if field=='temperature' else 'viridis')(np.clip((a-lo)/(hi-lo),0,1))[:,:,:3]*255
        write_image(name,rgb,dk);cand[field]=name
    cand['checks']={k:v for k,v in json.loads((folder/'simulation.json').read_text()).items() if k!='history'};item['candidates']=[cand];return item
def export_nested_job(folder,config,seed):
    item=nested_item(folder,config,seed);manifest={'version':T.C['version'],'status':'painted candidate','timesYears':T.C['timesYears'],'seeds':[seed],'regions':[item]};T.savejson(OUT/'manifest.json',manifest)
def export():
    manifest={'version':T.C['version'],'status':'candidate','timesYears':T.C['timesYears'],'seeds':T.C['seeds'],'regions':[],'atmosphereModel':'Terrain-conditioned seasonal proxy: precipitation, humidity, surface pressure and near-surface wind. No GCM or cloud microphysics.','units':{'height':'metres above mean sea level','time':'effective model years','rain':'m/year','temperature':'degrees C','pressure':'Pa','wind':'m/s'},'plateau':'orun-plateau-before-after.png'}
    diagnostics()
    for id,r in T.C['regions'].items():
        if not (WORK/id/'grid.json').exists():continue
        g=json.loads((WORK/id/'grid.json').read_text());old=np.load(WORK/id/'baseline.npy');revised=np.load(WORK/id/'revised.npy');kind=np.load(WORK/id/'kind.npy');dk=down(kind,1600,0);dz=down(revised);step=g['stepM']*len(revised)/len(dz)
        oldkind=np.load(WORK/id/'baseline-kind.npy') if (WORK/id/'baseline-kind.npy').exists() else kind
        write_image(f'{id}-before.png',elevation(down(old)),down(oldkind,1600,0));write_image(f'{id}-revised.png',elevation(dz),dk);write_image(f'{id}-protected.png',np.where((down(np.load(WORK/id/'protected.npy'),1600,0)>0)[:,:,None],[56,147,133],[226,214,185])+np.zeros((*dk.shape,3)),dk)
        item={'id':id,'title':r['title'],'grid':g,'width':dk.shape[1],'height':dk.shape[0],'baseline':f'{id}-before.png','revised':f'{id}-revised.png','protected':f'{id}-protected.png','baselineMesh':height_mesh(f'{id}-before.f32',old),'candidates':[],'markers':[]}
        item['revisedMesh']=height_mesh(f'{id}-revised.f32',revised)
        p=T.Proj(g['projection'])
        review_file=WORK/'review-points.json'
        if review_file.exists():
            for q in json.loads(review_file.read_text()):
                if q['region']==id:
                    x,y=p(*q['coordinates']);item['markers'].append({'name':q['name'],'position':[(x-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-y)/((g['height']-1)*g['stepM'])]})
        for f in D_markers():
            x,y=p(*f['geometry']['coordinates']);i=(x-g['xmin'])/(g['width']-1)/g['stepM'];j=(g['ymax']-y)/(g['height']-1)/g['stepM']
            if 0<i<1 and 0<j<1:item['markers'].append({'name':f['properties']['name'],'position':[i,j]})
        for seed in T.C['seeds']:
            folder=WORK/id/str(seed)
            if not (folder/'initial.npy').exists():continue
            kind=np.load(folder/'kind.npy') if (folder/'kind.npy').exists() else np.load(WORK/id/'kind.npy');dk=down(kind,1600,0)
            ini=np.load(folder/'initial.npy');candidate={'seed':seed,'stages':[],'faults':json.loads((folder/'faults.json').read_text())}
            for fault in candidate['faults']:
                fault['screen']=[[(p(*q)[0]-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-p(*q)[1])/((g['height']-1)*g['stepM'])] for q in fault['coordinates']]
            for year in T.C['timesYears']:
                f=folder/f'height-{year}.npy'
                if year==0:z=ini
                elif f.exists():z=np.load(f)
                else:continue
                small=down(z);base=f'{id}-{seed}-{year}';write_image(base+'-height.png',elevation(small),dk);write_image(base+'-ground.png',ground(small,step),dk);write_image(base+'-change.png',signed(down(z-revised)),dk)
                stage={'year':year,'height':base+'-height.png','ground':base+'-ground.png','change':base+'-change.png','mesh':height_mesh(base+'.f32',z),'stats':stats(z,revised,kind,g['stepM'])};candidate['stages'].append(stage)
            # Three seeds have an identical oblique camera and vertical multiplier.
            candidate['oblique']=None
            for field in ['erosion','deposition','tectonic-uplift','magmatic-uplift','basalt-thickness','pond-depth','rain','temperature','humidity','cloud','pressure','wind-east','wind-north','discharge']:
                path=folder/(field+'.npy')
                if not path.exists():continue
                a=down(np.load(path));fname=f'{id}-{seed}-{field}.png'
                if field in ['erosion','deposition','tectonic-uplift','magmatic-uplift','basalt-thickness','pond-depth']:rgb=signed(a,600)
                else:
                    ranges={'rain':(0,3.5),'temperature':(-30,35),'humidity':(0,1),'cloud':(0,1),'pressure':(15000,130000),'wind-east':(-10,10),'wind-north':(-10,10),'discharge':(0,12)};lo,hi=ranges[field]
                    if field=='discharge':a=np.log10(1+a)
                    cm=plt.get_cmap('viridis' if field!='temperature' else 'coolwarm');rgb=cm(np.clip((a-lo)/(hi-lo),0,1))[:,:,:3]*255
                write_image(fname,rgb,dk);candidate[field]=fname
            if (folder/'simulation.json').exists():candidate['checks']={k:v for k,v in json.loads((folder/'simulation.json').read_text()).items() if k!='history'}
            if (folder/'tectonic-summary.json').exists():candidate['tectonics']=json.loads((folder/'tectonic-summary.json').read_text())
            item['candidates'].append(candidate)
        manifest['regions'].append(item);gc.collect()
    for r in T.C['refinements']:
        folder=WORK/'refined'/r['id']
        if (folder/'simulation.json').exists() and json.loads((folder/'simulation.json').read_text()).get('passed'):manifest['regions'].append(nested_item(folder,r))
    if (WORK/'aethelgard/revised.npy').exists():manifest['regions'].append(focus_view('aethelgard','orun-ramp','Orun · 分段断层与长背坡',[0,10],2500000,2000000,'orun'))
    if (WORK/'vorhan/revised.npy').exists():manifest['regions'].append(focus_view('vorhan','rift-graben','Rift · 被拉开的大峡谷',[105.5,18],1200000,2000000,'rift'))
    if (WORK/'global'/str(T.C['seeds'][0])/'height.npy').exists():manifest['regions'].insert(0,world_view())
    manifest['sourceWork']=str(WORK);manifest['studyStage']='coarse preview' if T.C['gridStepM']>=8000 else 'regional candidate';manifest['climateStatus']='pending ExoPlaSim; preliminary forcing layers remain explicitly marked'
    T.savejson(OUT/'manifest.json',manifest);(OUT/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(manifest,ensure_ascii=False)+';\n',encoding='utf-8');log(f'EXPORTED {len(manifest["regions"])} regions')
def focus_view(parent,id,title,center,width_m,height_m,prefix):
    pg=json.loads((WORK/parent/'grid.json').read_text());p=T.Proj(pg['projection']);cx,cy=p(*center);dx=pg['stepM'];nx=round(width_m/dx)+1;ny=round(height_m/dx)+1
    g={**pg,'id':id,'width':nx,'height':ny,'xmin':cx-(nx-1)*dx/2,'ymax':cy+(ny-1)*dx/2};kind=T.sample(np.load(WORK/parent/'kind.npy'),pg,g,0);base=T.sample(np.load(WORK/parent/'baseline.npy'),pg,g);rev=T.sample(np.load(WORK/parent/'revised.npy'),pg,g)
    item={'id':id,'title':title,'maskRegion':parent,'grid':g,'width':nx,'height':ny,'baseline':prefix+'-before.png','revised':prefix+'-revised.png','protected':prefix+'-protected.png','baselineMesh':height_mesh(prefix+'-before.f32',base,700),'revisedMesh':height_mesh(prefix+'-revised.f32',rev,700),'markers':[],'candidates':[]}
    oldkind=T.sample(np.load(WORK/parent/'baseline-kind.npy'),pg,g,0) if (WORK/parent/'baseline-kind.npy').exists() else kind
    write_image(item['baseline'],elevation(base),oldkind);write_image(item['revised'],elevation(rev),kind);protected=T.sample(np.load(WORK/parent/'hard-protected.npy'),pg,g,0);write_image(item['protected'],np.where(protected[:,:,None]>0,[56,147,133],[226,214,185])+np.zeros((*kind.shape,3)),kind)
    for seed in T.C['seeds']:
        folder=WORK/parent/str(seed)
        if not (folder/'initial.npy').exists():continue
        if (folder/'kind.npy').exists():kind=T.sample(np.load(folder/'kind.npy'),pg,g,0)
        cand={'seed':seed,'stages':[],'faults':[]}
        for f in json.loads((WORK/parent/(prefix+'-faults.json')).read_text()):
            f['screen']=[[(p(*q)[0]-g['xmin'])/((nx-1)*dx),(g['ymax']-p(*q)[1])/((ny-1)*dx)] for q in f['coordinates']];cand['faults'].append(f)
        for year in T.C['timesYears']:
            file=folder/('initial.npy' if year==0 else f'height-{year}.npy')
            if not file.exists():continue
            z=T.sample(np.load(file),pg,g);name=f'{prefix}-{seed}-{year}';write_image(name+'-height.png',elevation(z),kind);write_image(name+'-ground.png',ground(z,dx),kind);write_image(name+'-change.png',signed(z-rev),kind)
            cand['stages'].append({'year':year,'height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','mesh':height_mesh(name+'.f32',z,700),'stats':stats(z,rev,kind,dx)})
        item['candidates'].append(cand)
        if (folder/'tectonic-summary.json').exists():cand['tectonics']=json.loads((folder/'tectonic-summary.json').read_text())
        for field in ['pond-depth','erosion','deposition','magmatic-uplift','basalt-thickness']:
            file=folder/(field+'.npy')
            if file.exists():
                name=f'{prefix}-{seed}-{field}.png';write_image(name,signed(T.sample(np.load(file),pg,g),600),kind);cand[field]=name
    for f in D_markers():
        x,y=p(*f['geometry']['coordinates']);u=(x-g['xmin'])/((nx-1)*dx);v=(g['ymax']-y)/((ny-1)*dx)
        if 0<u<1 and 0<v<1:item['markers'].append({'name':f['properties']['name'],'position':[u,v]})
    return item

def world_view():
    folder=WORK/'global'/str(T.C['seeds'][0]);g=json.loads((folder/'grid.json').read_text());kind=np.load(folder/'baseline-kind.npy');old=np.load(folder/'baseline.npy');dk=down(kind,1600,0);s=down(old);write_image('world-before.png',elevation(s),dk)
    item={'id':'world','title':'全球 · 构造与大陆','readOnly':True,'grid':g,'width':s.shape[1],'height':s.shape[0],'baseline':'world-before.png','revised':'world-before.png','protected':None,'baselineMesh':height_mesh('world-before.f32',old,700),'candidates':[],'markers':[]}
    for seed in T.C['seeds']:
        f=WORK/'global'/str(seed)
        if not (f/'height.npy').exists():continue
        z=np.load(f/'height.npy');kind=np.load(f/'kind.npy');dk=down(kind,1600,0);small=down(z);name=f'world-{seed}';write_image(name+'-height.png',elevation(small),dk);write_image(name+'-ground.png',ground(small,g['stepM']*len(z)/len(small)),dk);write_image(name+'-change.png',signed(down(z-old)),dk)
        stage={'year':T.C['timesYears'][-1],'height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','mesh':height_mesh(name+'.f32',z,700),'stats':stats(z,old,kind,g['stepM'],np.load(f/'cell-area.npy'))}
        # Metrics on an equirectangular globe need spherical cell areas.
        area=np.load(f/'cell-area.npy');land=(kind>=30)&(kind!=80)&(kind!=200);stage['stats']['newHighlandAreaKm2']=float(area[land&(z>2500)&(old<=2500)].sum()/1e6)
        stage['stats']['highlandAreaKm2']=float(area[land&(z>2500)].sum()/1e6)
        faults=[];p=T.Proj(g['projection'])
        for region in T.C['regions']:
            file=WORK/region/str(seed)/'faults.json'
            if file.exists():
                for fault in json.loads(file.read_text()):
                    fault['screen']=[[(p(*q)[0]-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-p(*q)[1])/((g['height']-1)*g['stepM'])] for q in fault['coordinates']];faults.append(fault)
        item['candidates'].append({'seed':seed,'stages':[stage],'faults':faults})
    return item

def D_markers():return [f for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]) if f['geometry']['type']=='Point']
def log(s):print(s,flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=WORK);ap.add_argument('--out',type=pathlib.Path,default=OUT);a=ap.parse_args();WORK=a.work;OUT=a.out;OUT.mkdir(parents=True,exist_ok=True);T.WORK=WORK
    if (WORK/'run-config.json').exists():T.C=json.loads((WORK/'run-config.json').read_text())
    export()
