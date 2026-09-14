"""Selected real 2 km and 250 m continuation, with transient upstream forcing."""
import pathlib,sys,importlib,json,argparse,copy,gc,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).parent));X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;R=importlib.import_module('tectonics-refine')

def centre(work,region,metric='erosion',width=256):
    folder=work/region/'5210914';g=X.read(work/region/'grid.json');z=np.load(folder/'initial.npy');score=np.load(folder/(metric+'.npy')).copy();allow=np.load(work/region/'allow.npy');kind=np.load(folder/'kind.npy');n,m=z.shape;frame=np.minimum.reduce(np.broadcast_arrays(np.arange(n)[:,None],n-1-np.arange(n)[:,None],np.arange(m)[None,:],m-1-np.arange(m)[None,:]));interior=(T.edt(kind>=30)*g['stepM']>width*500)&(frame*g['stepM']>width*500)&(allow>.8)
    if region=='aethelgard':interior&=X.C.quiet(g)>.99
    score[~interior]=0
    if score.max()<=0:score=np.hypot(*np.gradient(z));score[~interior]=0
    r,c=np.unravel_index(score.argmax(),score.shape);return list(T.Proj(g['projection'])(g['xmin']+c*g['stepM'],g['ymax']-r*g['stepM'],inverse=True))

def plans(work):
    ref=work/'erosion-only';result=[]
    for region,title in [('aethelgard','Aethelgard · 支沟与残余台山'),('vorhan','Vorhan · 倾斜山脉与谷底堆积'),('duskreach','Duskreach · 台缘切割'),('keld','Keld · 岛山风化')]:
        result.append({'id':region+'-erosion-2km','parent':region,'center':centre(ref,region),'widthKm':256,'stepM':2000,'title':title+' · 2 km','continuationCatalog':True,'erosionCycle':True})
    result.extend([
      {'id':'orun-desert-2km','parent':'aethelgard','center':[-3,6.5],'widthKm':256,'stepM':2000,'title':'Orun 南部 · 沙地与冲沟 · 2 km','continuationCatalog':True,'erosionCycle':True},
      {'id':'ishkar-riverbend-2km','parent':'aethelgard','center':X.bank_site()['coordinates'],'widthKm':256,'stepM':2000,'title':'Ishkar 与 Riverbend 新址 · 2 km','continuationCatalog':True,'erosionCycle':True,'inheritIshkarBed':True,'activeIshkarCorridor':True},
      {'id':'atheria-frontier-2km','parent':'aethelgard','center':[.3,27],'widthKm':640,'stepM':2000,'title':'Atheria / Frontier · 缓地 · 2 km','continuationCatalog':True,'erosionCycle':True}
    ])
    for r in result:
        if r['id'] not in ['atheria-frontier-2km','ishkar-riverbend-2km']:r.update(landformTarget='resistant caps, retreating soft beds, tributary dissection and talus',capThicknessM=220,softLayerErodibilityScale=3,weatheringScale=2)
    return result

def select_detail(work,spec,width=32):
    folder=work/'refined'/spec['id'];g=X.read(folder/'grid.json');z=np.load(folder/'height.npy');score=np.load(folder/'erosion.npy');allow=~(np.load(folder/'protected.npy')>0);kind=np.load(folder/'kind.npy');n,m=z.shape;frame=np.minimum.reduce(np.broadcast_arrays(np.arange(n)[:,None],n-1-np.arange(n)[:,None],np.arange(m)[None,:],m-1-np.arange(m)[None,:]));score[(frame*g['stepM']<width*500+8000)|~allow|(T.edt(kind>=30)*g['stepM']<width*500+4000)]=0
    relief=X.maximum_filter(z,size=max(3,round(width*1000/g['stepM'])))-X.minimum_filter(z,size=max(3,round(width*1000/g['stepM'])));score*=np.clip(relief/350,0,1);r,c=np.unravel_index(np.argmax(score),score.shape);p=T.Proj(g['projection']);return list(p(g['xmin']+c*g['stepM'],g['ymax']-r*g['stepM'],inverse=True))

def execute(work,spec,end=2000000,dt=5000,mask=None):
    X.setup(work,mask);R.WORK=work;R.T.WORK=work;folder=work/'refined'/spec['id'];parent=work/spec['parent']/'5210914' if spec['parent'] in X.REGIONS else work/'refined'/spec['parent']
    region=T.C['regions'].get(spec['parent']);source_region=spec['parent'] if region else X.read(parent/'grid.json')['region'];maskfile=pathlib.Path(mask)/f'{source_region}.json' if mask and pathlib.Path(mask).is_dir() else pathlib.Path(mask) if mask else None
    inputs={'spec':spec,'end':end,'dt':dt,'maskSha256':T.sha(maskfile) if maskfile and maskfile.exists() else None,'solverSha256':R.SOURCE_SHA256,'cycleSha256':T.sha(pathlib.Path(X.__file__)),'parent':{p.name:T.sha(p) for p in parent.glob('*.npy') if p.name.startswith(('height','discharge-','sediment-flux-','receiver-','soil-initial'))}};key=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    if (folder/'simulation.json').exists() and (folder/'parent-boundary.json').exists() and (folder/'run-key.json').exists() and X.read(folder/'run-key.json')['key']==key:
        record=X.read(folder/'simulation.json');dependency=X.read(folder/'parent-boundary.json');saved=X.read(folder/'grid.json');cx,cy=T.Proj(saved['projection'])(*spec['center']);same=abs(saved['xmin']+spec['widthKm']*500-cx)<1 and abs(saved['ymax']-spec['widthKm']*500-cy)<1
        if same and record.get('passed') and record['effectiveYears']==end and dependency['parentHeightSha256']==T.sha(parent/'height.npy'):
            T.log('REUSE '+spec['id']);return
    try:R.run(spec,5210914,dtmax=dt,end=end)
    except Exception as e:T.savejson(folder/'failure.json',{'error':str(e),'config':spec});raise
    T.savejson(folder/'run-key.json',{'key':key,'inputs':inputs})
    np.save(folder/'uplift-rate.npy',np.zeros_like(np.load(folder/'height.npy')));gc.collect()

def run(work,mode='both',only=None,end=2000000,mask=None):
    X.setup(work/'erosion-only');specs=plans(work);planfile=work/'detail-plan.json';all_specs=X.read(planfile) if planfile.exists() else []
    def register(spec):
        nonlocal all_specs
        current=X.read(planfile) if planfile.exists() else all_specs;all_specs=[s for s in current if (s['id'],s['mode'])!=(spec['id'],spec['mode'])]+[spec];T.savejson(planfile,all_specs)
    for m in X.CFG['modes'] if mode=='both' else [mode]:
        for spec in specs:
            if only and only not in [spec['id'],spec['parent']]:continue
            s={**spec,'mode':m};register(s);execute(work/m,s,min(end,100000) if spec['id']=='atheria-frontier-2km' else end,5000,mask)
            if spec['id']!='atheria-frontier-2km':
                # Both modes use the same selected spatial window.
                existing=next((v for v in all_specs if v['id']==spec['id'].replace('2km','250m')),None);center=existing['center'] if existing else select_detail(work/m,s)
                child={**s,'id':spec['id'].replace('2km','250m'),'parent':spec['id'],'center':center,'widthKm':32,'stepM':250,'title':spec['title'].replace('2 km','250 m'),'inheritIshkarBed':False};register(child);execute(work/m,child,end,2500,mask)
    return all_specs

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=X.DEFAULT);ap.add_argument('--mode',choices=['both','episodic','erosion-only'],default='both');ap.add_argument('--region');ap.add_argument('--end',type=int,default=2000000);ap.add_argument('--mask',type=pathlib.Path);a=ap.parse_args();run(a.work,a.mode,a.region,a.end,a.mask)
