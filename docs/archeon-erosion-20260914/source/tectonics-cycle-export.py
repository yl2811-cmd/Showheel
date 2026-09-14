"""Small baked products for the erosion-cycle browser; no numerical cache export."""
import pathlib,sys,importlib,json,argparse,copy,shutil
sys.path.insert(0,str(pathlib.Path(__file__).parent));X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;E=importlib.import_module('tectonics-export');W=importlib.import_module('tectonics-world')

def ground(z,soil,sand,dx):
    rgb=E.ground(z,dx).astype(float);fraction=np.clip(sand/3,0,.8)[:,:,None];rgb=rgb*(1-fraction)+np.array([196,167,112])*fraction
    loam=np.clip((soil-sand)/4,0,.6)[:,:,None];return rgb*(1-loam)+np.array([111,97,77])*loam

def markers(g,site):
    result=[];p=T.Proj(g['projection'])
    for f in E.D_markers():
        coords=site['coordinates'] if f.get('id')=='RB' or f['properties']['name']=='Riverbend' else f['geometry']['coordinates'];x,y=p(*coords);u=(x-g['xmin'])/((g['width']-1)*g['stepM']);v=(g['ymax']-y)/((g['height']-1)*g['stepM'])
        if 0<u<1 and 0<v<1:result.append({'name':f['properties']['name']+(' · 新址' if f['properties']['name']=='Riverbend' else ''),'position':[u,v]})
    return result

def river_lines(g,q,rec,threshold=1e9):
    # Actual receiver links; display does not smooth a different physical path.
    rows=[];flat=q.ravel();rr=rec.ravel();valid=np.flatnonzero((flat>threshold)&(rr>=0)&(rr!=np.arange(len(rr))));valid=valid[::max(1,len(valid)//1200)]
    for i in valid:
        j=int(rr[i]);a,b=divmod(int(i),g['width']);c,d=divmod(j,g['width']);rows.append({'name':'模拟汇流','screen':[[b/(g['width']-1),a/(g['height']-1)],[d/(g['width']-1),c/(g['height']-1)]]})
    return rows

def bake_candidate(folder,g,prefix,seed,mode):
    original=np.load(folder/'initial.npy');kind=np.load(folder/'kind-0.npy') if (folder/'kind-0.npy').exists() else np.load(folder/'kind.npy');before=np.load(folder/'base-v10.npy') if (folder/'base-v10.npy').exists() else original
    c={'seed':seed,'mode':mode,'baseline':prefix+'-saved.png','baselineMesh':E.height_mesh(prefix+'-saved.f32',np.where(kind==0,0,before),700),'stages':[],'faults':[]}
    E.write_image(c['baseline'],E.elevation(E.down(before)),E.down(kind,1600,0))
    soil=np.load(folder/'soil.npy');sand=np.load(folder/'sand.npy') if (folder/'sand.npy').exists() else soil*0;end=X.read(folder/'simulation.json')['effectiveYears']
    for year in sorted(int(p.stem.split('-')[-1]) for p in folder.glob('height-*.npy') if int(p.stem.split('-')[-1])<=end):
        path=folder/f'height-{year}.npy'
        if not path.exists():continue
        z=np.load(path);small=E.down(z);k=np.load(folder/f'kind-{year}.npy') if (folder/f'kind-{year}.npy').exists() else kind;dk=E.down(k,1600,0);name=f'{prefix}-{year}';dx=g['stepM']*z.shape[0]/small.shape[0]
        st={'year':year,'label':'共同初始基底' if year==0 else f'{year/10000:g} 万有效年','height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','mesh':E.height_mesh(name+'.f32',np.where(k==0,0,z),700),'stats':E.stats(z,original,k,g['stepM']),'meshDatum':'land elevation and ocean water surface; numeric bed retained locally'}
        if g['stepM']<=2000:
            core=(slice(4,-4),slice(4,-4));delta=(z-original)[core];st['localStats']={'loweringM':float(np.maximum(0,-delta).max(initial=0)),'raisingM':float(np.maximum(0,delta).max(initial=0)),'reliefM':float(np.ptp(z[core]))}
        ys=np.load(folder/f'soil-{year}.npy') if (folder/f'soil-{year}.npy').exists() else soil if year==end else np.load(folder/'soil-initial.npy');ya=np.load(folder/f'sand-{year}.npy') if (folder/f'sand-{year}.npy').exists() else sand if year==end else soil*0
        E.write_image(st['height'],E.elevation(small),dk);E.write_image(st['ground'],ground(small,E.down(ys),E.down(ya),dx),dk);E.write_image(st['change'],E.signed(E.down(z-original),500),dk)
        qpath=folder/f'discharge-{year}.npy';rpath=folder/f'receiver-{year}.npy'
        if qpath.exists() and rpath.exists():st['routes']=river_lines(g,np.load(qpath),np.load(rpath),threshold=1e10 if g['stepM']>=16000 else 3e9)
        c['stages'].append(st)
    dk=E.down(np.load(folder/'kind.npy'),1600,0)
    for field in ['erosion','deposition','tectonic-uplift','pond-depth','weathering','soil','sand','discharge']:
        path=folder/(field+'.npy')
        if not path.exists():continue
        a=E.down(np.load(path));name=prefix+'-'+field+'.png'
        if field=='discharge':rgb=E.plt.get_cmap('viridis')(np.clip(np.log10(1+np.maximum(a,0))/12,0,1))[:,:,:3]*255
        elif field in ['soil','sand','weathering']:rgb=E.plt.get_cmap('YlOrBr')(np.clip(np.log1p(np.maximum(a,0))/np.log(101),0,1))[:,:,:3]*255
        else:rgb=E.signed(a,600)
        E.write_image(name,rgb,dk);c[field]=name
    z=np.load(folder/'height.npy');gy,gx=np.gradient(z,g['stepM']);n=np.stack([-gx,gy,np.ones_like(gx)],axis=-1);n/=np.linalg.norm(n,axis=-1,keepdims=True);normal=prefix+'-normal.png';E.write_image(normal,((n+1)*127.5).astype('uint8'));c['normal']=normal
    c['checks']={k:v for k,v in X.read(folder/'simulation.json').items() if k!='history'}
    for key in ['coast','retention','renewal-decision']:
        if (folder/(key+'.json')).exists():c[key]=X.read(folder/(key+'.json')) if key!='retention' else {k:v for k,v in X.read(folder/(key+'.json')).items() if k!='features'}
    events=folder/'events.json'
    if events.exists():
        for e in X.read(events):
            cx,cy=e['xy'];a=e['angleRadians'];L=e['lengthM']*.7;coords=[[cx-L*np.cos(a),cy-L*np.sin(a)],[cx+L*np.cos(a),cy+L*np.sin(a)]];c['faults'].append({'mode':'normal','screen':[[(x-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-y)/((g['height']-1)*g['stepM'])] for x,y in coords]})
    return c

def region_item(work,id):
    paths=[work/m/id for m in X.CFG['modes'] if (work/m/id/'grid.json').exists()]
    if not paths:return
    g=X.read(paths[0]/'grid.json');site=X.bank_site();title=T.C['regions'][id]['title'];kind=np.load(paths[0]/'kind.npy');protected=np.load(paths[0]/'hard-protected.npy');E.write_image(id+'-protected.png',np.where(E.down(protected,1600,0)[:,:,None]>0,[56,147,133],[226,214,185])+np.zeros((*E.down(kind).shape,3)),E.down(kind,1600,0))
    item={'id':id,'title':title,'grid':g,'width':g['width'],'height':g['height'],'maskRegion':id,'markers':markers(g,site),'protected':id+'-protected.png','candidates':[],'baselineLabel':'已保存的 v10 地形'}
    for mode in X.CFG['modes']:
        for seed in X.CFG['seeds']:
            folder=work/mode/id/str(seed)
            if (folder/'height.npy').exists() and (folder/'simulation.json').exists():item['candidates'].append(bake_candidate(folder,g,f'{id}-{mode}-{seed}',seed,mode))
    if not item['candidates']:return
    first=item['candidates'][0];item.update(baseline=first['baseline'],revised=first['baseline'],baselineMesh=first['baselineMesh']);return item

def world_item(work):
    if not (work/'episodic/aethelgard/5210914/height.npy').exists():return None
    g=X.read(X.BASE/'global/5210914/grid.json');item={'id':'world','title':'全球 · 台地、裂谷与海湾','grid':g,'width':g['width'],'height':g['height'],'readOnly':True,'markers':[],'candidates':[],'baselineLabel':'已保存的 v10 全球地形'}
    for mode in X.CFG['modes']:
        for seed in X.CFG['seeds']:
            if not all((work/mode/r/str(seed)/'height.npy').exists() for r in X.REGIONS):continue
            saved=X.BASE/'global'/str(seed);base=np.load(saved/'height.npy');basekind=np.load(saved/'kind.npy');areas=np.load(saved/'cell-area.npy');prefix=f'world-{mode}-{seed}';E.write_image(prefix+'-before.png',E.elevation(E.down(base)),E.down(basekind,1600,0));cand={'seed':seed,'mode':mode,'baseline':prefix+'-before.png','baselineMesh':E.height_mesh(prefix+'-before.f32',np.where(basekind==0,0,base),700),'stages':[],'faults':[]};out=work/mode/'global'/str(seed);out.mkdir(parents=True,exist_ok=True);T.savejson(out/'grid.json',g)
            for year in X.CFG['timesYears']:
                z=base.copy();kind=basekind.copy();inputs=[]
                for region in X.REGIONS:
                    folder=work/mode/region/str(seed);pg=X.read(work/mode/region/'grid.json');spec=T.C['regions'][region];lands=[f['geometry'] for f in T.D['land'] if f['id'] in spec.get('landIds',[]) or ('landPrefix' in spec and f['id'].startswith(spec['landPrefix']))];footprint=T.raster(lands,g);support=(T.edt(~footprint)*g['stepM']<32000)&(basekind!=80);field=T.sample(np.load(folder/f'height-{year}.npy'),pg,g);k=T.sample(np.load(folder/f'kind-{year}.npy'),pg,g,0);z[support]=field[support];kind[support]=k[support];inputs.append({'region':region,'heightSha256':T.sha(folder/f'height-{year}.npy')})
                name=f'{prefix}-{year}';np.save(out/f'height-{year}.npy',z);np.save(out/f'kind-{year}.npy',kind);T.savejson(out/f'lineage-{year}.json',{'regionalInputs':inputs,'far5MaxDeltaM':float(abs(z[basekind==80]-base[basekind==80]).max(initial=0)),'polarTerrain':'saved v10, unchanged in this cycle'})
                small=E.down(z);dk=E.down(kind,1600,0);E.write_image(name+'-height.png',E.elevation(small),dk);E.write_image(name+'-ground.png',E.ground(small,g['stepM']*len(z)/len(small)),dk);E.write_image(name+'-change.png',E.signed(E.down(z-base),500),dk);cand['stages'].append({'year':year,'label':'本轮初始基底' if year==0 else f'{year/10000:g} 万有效年','height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','mesh':E.height_mesh(name+'.f32',np.where(kind==0,0,z),700),'stats':E.stats(z,base,kind,g['stepM'],areas)})
            item['candidates'].append(cand)
    if not item['candidates']:return None
    first=item['candidates'][0];item.update(baseline=first['baseline'],revised=first['baseline'],baselineMesh=first['baselineMesh']);return item

def build_page():
    s=(T.ROOT/'tectonics.html').read_text(encoding='utf8').replace('foundation/tectonics/data.js','foundation/erosion/data.js').replace('LANDSCAPE STUDY 02','LANDSCAPE STUDY 04').replace('Archeon · 岩层与长风','Archeon · 岩层、河谷与沙地').replace('岩层抬起，流水留下谷地','台缘退去，河谷与沙地展开')
    a=s.index('<div class="intro">');b=s.index('<nav id="regions"',a);s=s[:a]+'<div class="intro"><p class="eyebrow">ROCK, WATER & DEEP TIME</p><h1>台缘退去，河谷与沙地展开</h1><p>从保存的地形继续演化。比较纯侵蚀与间歇抬升，放大查看沟谷、台阶、坡脚堆积和沙地。Riverbend 已落在选中的新河段旁。</p><p class="status">本地候选 · 航线待最终地形确定后重绘</p></div>'+s[b:]
    s=s.replace('<label>候选 <select id="seed">','<label>过程 <select id="evolution-mode"><option value="episodic">间歇造地＋侵蚀</option><option value="erosion-only">纯侵蚀</option></select></label><label>候选 <select id="seed">')
    s=s.replace('<option value="height">高程</option>','<option value="height">高程</option><option value="soil">土层</option><option value="sand">松散砂质覆盖</option><option value="weathering">累计风化</option><option value="normal">地形法线</option>')
    s=s.replace('<option value="water">流水侵蚀</option>','<option value="relief-density">造地事件分布</option><option value="relief-amplitude">新地貌起伏</option><option value="water">流水侵蚀</option>')
    s=s.replace('<option value="initial">构造与素材加入后</option>','<option value="initial" selected>本轮共同初始基底</option>').replace('<option value="revised">构造基底重建后</option>','<option value="revised">已保存的 v10 地形</option>')
    s=s.replace('<label><input id="faults" type="checkbox">断层</label>','<label><input id="faults" type="checkbox">断层</label><label><input id="rivers" type="checkbox">河网</label>')
    s=s.replace('<span>同一份数值高程</span>','<span>同一份数值高程</span><label>表面 <select id="three-surface"><option value="after">当前候选</option><option value="before">左图基底</option></select></label>')
    s=s.replace('2 km 大陆计算','2 km 局部续演').replace('<option value="1.5" selected>1.5×</option>','<option value="1.5">1.5×</option>').replace('<option value="1">1×</option><option value="1.5">','<option value="1" selected>1×</option><option value="1.5">')
    s=s.replace('2 km 局部续演','当前局部精度续演').replace('<a href="erosion.html">侵蚀与分层台地候选 ↗</a>','')
    a=s.index('<details><summary>Orun 高原修订对照');b=s.index('</main>',a);s=s[:a]+'''<section class="study-results"><h2>放大看地表怎样改变</h2><p>从地区菜单进入 2 km 与 250 m 细部，左右图同步缩放；切换经过的时间和过程，比较同一位置。立体图默认使用真实的 1× 垂直比例。</p><p>地质演化使用有效模型年。降雨和风仍为粗试算条件，松散砂质覆盖不等于经过气候验证的沙漠边界。细部继承上游来水与泥沙。</p><p><a href="foundation/erosion/FINDINGS.md">结果与核对范围 ↗</a> · <a href="foundation/erosion/manifest.json">烘焙清单 ↗</a> · <a href="evolution.html">上一版已保存地形 ↗</a></p></section>'''+s[b:]
    (T.ROOT/'erosion.html').write_text(s,encoding='utf8')

def export(work,out=None,fast=False):
    out=out or T.ROOT/'foundation/erosion';out.mkdir(parents=True,exist_ok=True);X.setup(work/'episodic');E.OUT=out;items=[]
    for region in X.REGIONS:
        item=region_item(work,region)
        if item:items.append(item)
    previous=X.read(out/'manifest.json') if fast and (out/'manifest.json').exists() else {};context=next((r for r in previous.get('regions',[]) if r['id']=='world'),None) if previous.get('sourceWork')==str(work) else None
    if context is None:context=world_item(work)
    if context:items.insert(0,context)
    plan=work/'detail-plan.json';known=X.read(plan) if plan.exists() else []
    # Discover completed folders as well as the live plan: independent workers
    # may finish at different times. No numeric trial is discarded by a UI list.
    for mode in X.CFG['modes']:
        for report in (work/mode/'refined').glob('*/simulation.json'):
            folder=report.parent;r=X.read(report)
            if not r.get('passed'):continue
            existing=next((v for v in known if (v['id'],v['mode'])==(folder.name,mode)),None)
            if (folder/'refinement-config.json').exists():spec=X.read(folder/'refinement-config.json')
            elif existing and ' · ' in existing.get('title','') and not existing['title'].startswith(folder.name):spec=existing
            else:
                g=X.read(folder/'grid.json');name=folder.name;label='Orun 坡脚 · 保护地貌侵蚀' if name.startswith('orun-young') and '250m' in name else 'Orun 新高原 · 保护地貌侵蚀' if name.startswith('orun-young') else 'Marneth 旧山带 · 保护地貌侵蚀' if name.startswith('marneth-old') else 'Orun 南部 · 沙地与冲沟' if name.startswith('orun-desert') else 'Ishkar 与 Riverbend 新址' if name.startswith('ishkar-') else 'Atheria / Frontier · 缓地' if name.startswith('atheria-') else {'aethelgard':'Aethelgard · 台地与支谷','vorhan':'Vorhan · 倾斜山地与峡谷','duskreach':'Duskreach · 台缘切割','keld':'Keld · 岛山与残余台顶'}.get(g['region'],name);spec={'id':name,'parent':r['parent'],'center':list(T.Proj(g['projection'])(g['xmin']+(g['width']-1)*g['stepM']/2,g['ymax']-(g['height']-1)*g['stepM']/2,inverse=True)),'stepM':g['stepM'],'widthKm':(g['width']-1)*g['stepM']/1000,'title':label+f" · {g['stepM']:g} m"}
            spec.update(mode=mode);known=[v for v in known if (v['id'],v['mode'])!=(spec['id'],mode)]+[spec]
            if spec['id']=='orun-young-250m':spec['title']='Orun 坡脚 · 短期与长时对照 · 250 m'
    T.savejson(plan,known)
    if plan.exists():
        for spec in X.read(plan):
            folder=work/spec['mode']/'refined'/spec['id']
            if not (folder/'simulation.json').exists():continue
            g=X.read(folder/'grid.json');item=next((v for v in items if v['id']==spec['id']),None)
            if not item:
                item={'id':spec['id'],'title':spec['title'],'group':'放大细部','grid':g,'width':g['width'],'height':g['height'],'maskRegion':g['region'],'markers':markers(g,X.bank_site()),'candidates':[],'baselineLabel':'本轮共同初始基底'};items.append(item)
            cand=bake_candidate(folder,g,spec['mode']+'-'+spec['id'],spec.get('seed',5210914),spec['mode']);item['candidates'].append(cand);item.update(baseline=cand['baseline'],revised=cand['baseline'],baselineMesh=cand['baselineMesh'])
    manifest={'version':X.CFG['version'],'studyKey':'erosion','status':'candidate','bakeBase':'foundation/erosion/','seeds':X.CFG['seeds'],'regions':items,'baseStudy':str(X.BASE),'sourceWork':str(work),'riverbend':X.bank_site(),'routesDeferred':True,'climate':X.CFG['screening']['climate']};T.savejson(out/'manifest.json',manifest);(out/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(manifest,ensure_ascii=False,default=T.json_scalar)+';',encoding='utf8');build_page();T.log('EROSION BAKED '+str(len(items))+' views');return manifest

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=X.DEFAULT);ap.add_argument('--out',type=pathlib.Path);ap.add_argument('--fast',action='store_true');a=ap.parse_args();export(a.work,a.out,a.fast)
