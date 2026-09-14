"""Finish the latest moving-source terrain using shared, versioned parents."""
import pathlib,sys,importlib,argparse,gc,time
sys.path.insert(0,str(pathlib.Path(__file__).parent));P=importlib.import_module('climate-vorhan-plumes');C=P.C;T=P.T;np=P.np;D=P.D;L=P.L
SEA=importlib.import_module('climate-high-inland-sea');OUT=C.TASK/'terrain-completion-v18';TRACK=C.TASK/'plume-tracks-v16/base/5210914/g0.9'
PARENT=SEA.WORK/'coarse/erosion-only/baseline/16000/2000000'
WINDOWS=[{'id':'vorhan-west-track','region':'vorhan','center':[88.2,24.8]},
         {'id':'vorhan-east-track','region':'vorhan','center':[126.0,10.4]},
         {'id':'duskreach-west-track','region':'duskreach','center':[45.9,-25.8]},
         {'id':'duskreach-inland-cap','region':'duskreach','center':[69.8,-31.5]}]
from scipy.ndimage import maximum_filter,minimum_filter,distance_transform_edt

def setup():
    C.WORK=OUT;P.setup();L.WORK=OUT;T.WORK=OUT;L.CFG={**L.CFG,'maximumSeasonalCycles':1000}

def refined_initial(g):
    """Regional textures are recomputed; long-wave loading is inherited once."""
    z,kind,soil,allow,hard,features,_,_,_=P.initial(g,5210914,'control')
    tg=C.read(TRACK/'grid.json');track=T.sample(np.load(TRACK/'construction.npy',mmap_mode='r'),tg,g)
    _,_,_,_,_,changes,record=SEA.fields(g,1.47,2660.)
    lake=changes['basin-reconstruction']+changes['outlet-reconstruction']
    track[hard]=0;lake[hard]=0
    # V06 is the editable lake vista; SEA already preserves other scene cores.
    editable=T.distance(g,[82,34])<20000
    lake[editable]=changes['basin-reconstruction'][editable]+changes['outlet-reconstruction'][editable]
    hard=hard&~editable;z+=track+lake
    allow=np.maximum(allow,T.ease(np.maximum(track,0)/150));allow[hard|(kind<30)]=0
    extras=[f for f in C.read(TRACK/'sources.json') if '-episode-' in f['id']]
    for f in extras:f['xy']=list(T.Proj(g['projection'])(*f['center']))
    return z,kind,soil,allow,hard,features+extras,{'plume-displacement':track,'lake-reconstruction':lake}

def build_joint():
    setup();g=D.joint_grid(2000);g['seed']=5210914;folder=OUT/'continuous/vorhan-duskreach/base';folder.mkdir(parents=True,exist_ok=True)
    key=C.fingerprint({'code':C.sha(__file__),'sources':C.sources(),'track':C.sha(TRACK/'construction.npy'),'lakeSource':C.sha(SEA.__file__),'grid':g})
    if (folder/'complete.json').exists() and C.read(folder/'complete.json')['fingerprint']==key:return folder
    shape=(g['height'],g['width']);fields={n:np.lib.format.open_memmap(folder/(n+'.npy'),mode='w+',dtype=('uint8' if n=='kind' else 'float32'),shape=shape) for n in ['height','kind','soil','plume-displacement','lake-reconstruction']}
    # Halo exceeds the longest local smoothing/protection distance. It does
    # not define tectonic footprints and never becomes a drainage boundary.
    for row in range(0,g['height'],96):
        lo=max(0,row-100);hi=min(g['height'],row+96+100);bg={**g,'ymax':g['ymax']-lo*g['stepM'],'height':hi-lo}
        z,kind,soil,allow,hard,features,changes=refined_initial(bg);count=min(96,g['height']-row);sl=slice(row-lo,row-lo+count)
        for name,a in {'height':z,'kind':kind,'soil':soil,**changes}.items():fields[name][row:row+count]=a[sl]
        for f in fields.values():f.flush()
        C.write(folder/'progress.json',{'rowsCompleted':row+count,'totalRows':g['height'],'gridM':2000,'stage':'construction, water not yet solved'})
        print('CONTINUOUS BUILD',row+count,g['height'],flush=True);L.feature_shape.cache_clear();gc.collect()
    fields.clear();C.write(folder/'grid.json',g);C.write(folder/'complete.json',{'fingerprint':key,'heightSha256':C.sha(folder/'height.npy'),'fineStructure':'regional tile/lithology fields re-evaluated at 2 km','plumeResolutionM':16000,'plumeScope':'long-wave elastic and emplacement displacement inherited once; no claim of 2km mantle resolution','lakeReconstructionGridM':2000,'continuousRoutingPending':True});return folder

def build_evolved():
    setup();base=OUT/'continuous/vorhan-duskreach/base';g=C.read(base/'grid.json');pg=C.read(PARENT/'grid.json');folder=OUT/'continuous/vorhan-duskreach/evolved-2000000';folder.mkdir(parents=True,exist_ok=True)
    initial=np.load(base/'height.npy',mmap_mode='r');coarse_delta=np.load(PARENT/'height.npy')-np.load(PARENT/'initial.npy');chosen=[]
    for p in [OUT/'regional'/s['id'] for s in WINDOWS]+[SEA.WORK/'regional/erosion-only/baseline/2000/2000000']:
        if not (p/'simulation.json').exists():raise ValueError('Missing completed regional evolution: '+str(p))
        chosen.append((p,C.read(p/'grid.json'),np.load(p/'height.npy',mmap_mode='r')))
    result=np.lib.format.open_memmap(folder/'height.npy',mode='w+',dtype='float32',shape=initial.shape);adjust=np.lib.format.open_memmap(folder/'stitching-adjustment.npy',mode='w+',dtype='float32',shape=initial.shape);volume=0.
    hard_refs=T.D['settlements']+T.D['vistas']+T.D.get('extra',[])
    for row in range(0,g['height'],128):
        count=min(128,g['height']-row);bg={**g,'height':count,'ymax':g['ymax']-row*g['stepM']};background=np.asarray(initial[row:row+count],float)+T.sample(coarse_delta,pg,bg);xx,yy=T.mesh(bg);num=np.zeros_like(background);den=np.zeros_like(background)
        for path,cg,cz in chosen:
            margin=np.minimum.reduce([xx-cg['xmin'],cg['xmin']+(cg['width']-1)*cg['stepM']-xx,cg['ymax']-yy,yy-cg['ymax']+(cg['height']-1)*cg['stepM']]);weight=T.ease(margin/24000)
            if weight.any():num+=weight*(T.sample(cz,cg,bg)-background);den+=weight
        delta=num/np.maximum(1,den);final=background+delta
        hard=np.zeros(final.shape,bool)
        for f in hard_refs:
            if f['geometry']['type']=='Point' and f['id']!='V06':hard|=T.distance(bg,f['geometry']['coordinates'])<20000
        final[hard]=initial[row:row+count][hard];delta=final-background;result[row:row+count]=final;adjust[row:row+count]=delta;volume+=float(delta.sum()*g['stepM']**2)
    result.flush();adjust.flush();del result,adjust
    for name in ['kind','soil']:C.save_array(folder/(name+'.npy'),np.load(base/(name+'.npy'),mmap_mode='r'))
    C.write(folder/'grid.json',g);C.write(folder/'assembly.json',{'effectiveYears':2000000,'backgroundEvolutionGridM':16000,'regionalEvolutionGridM':2000,'continuousWaterGridM':2000,'initialHeightSha256':C.sha(base/'height.npy'),'coarseHeightSha256':C.sha(PARENT/'height.npy'),'regionalParents':[{'path':str(p),'heightSha256':C.sha(p/'height.npy')} for p,_,_ in chosen],'stitchingAdjustmentM3':volume,'stitchingIsNotErosion':True,'soilStatus':'inherited candidate soil; complete sediment/soil assembly pending','climateValidated':False,'globalSolidBudgetAccepted':False})
    print('EVOLVED CONTINUOUS ASSEMBLY READY',flush=True);return folder

def hydrate(folder,scenario='baseline',initial_water=None):
    setup();folder=pathlib.Path(folder);g=C.read(folder/'grid.json');out=folder/'water'/scenario
    height=np.load(folder/'height.npy').astype(float);kind=np.load(folder/'kind.npy');land=(kind>=30)&(kind!=80)
    key={'sourceHeight':C.sha(folder/'height.npy'),'kind':C.sha(folder/'kind.npy'),'solver':C.sha(L.H.__file__),'scenario':scenario}
    if (out/'request.json').exists() and C.read(out/'request.json')==key and (out/'hydrology.json').exists():return out
    print('CONTINUOUS WATER',g['id'],height.size,flush=True)
    initial_depth=None if initial_water is None else np.load(pathlib.Path(initial_water)/'lake-depth.npy').astype(float)
    if initial_depth is not None and initial_depth.shape!=height.shape:raise ValueError('Initial water grid does not match evolved terrain')
    hyd=L.H.run(height,land,g['stepM'],L.proxy(height,g,kind),{'dry':.5,'baseline':1.,'wet':1.5}[scenario],cycles=20,converge=True,max_cycles=1000,initial_depth=initial_depth)
    for name in ['discharge','receiver','lake-depth','lake-level','lake-occurrence','lake-min-depth','lake-max-depth','wetness']:
        C.save_array(out/(name+'.npy'),hyd[name].astype('int32') if name=='receiver' else hyd[name].astype('float32'))
    C.write(out/'grid.json',g);C.write(out/'request.json',key);C.write(out/'hydrology.json',{'convergence':hyd['convergence'],'maximumWaterRelativeError':hyd['maxWaterRelativeError'],'climateValidated':False,'gridM':g['stepM'],'continuousNetwork':True,'history':hyd['history'],'lakes':hyd['lakes'],'landCells':int(land.sum())});print('CONTINUOUS WATER DONE',g['id'],hyd['convergence'],flush=True);return out

def regional(spec):
    setup();g=L.grid_window(spec,2000,768);g['seed']=5210914;z,kind,soil,allow,hard,features,changes=refined_initial(g)
    rr,cc=np.indices(z.shape);edge=np.minimum.reduce([rr,cc,g['height']-1-rr,g['width']-1-cc])*2000;allow*=T.ease(edge/24000)
    folder=OUT/'regional'/spec['id'];parent=(PARENT,C.read(PARENT/'grid.json'))
    for name,a in changes.items():C.save_array(folder/(name+'.npy'),a.astype('float32'))
    L.solve(folder,g,z,kind,hard,allow,soil,features,'erosion-only','baseline',.9,parent=parent,end=2000000,dt=5000,cap=420)
    report=C.read(folder/'simulation.json');C.write(folder/'scope.json',{'parentHeightSha256':C.sha(PARENT/'height.npy'),'geologicalClock':'post-emplacement effective Earth years','modernClimateValidated':False})
    print('REGIONAL DONE',spec['id'],report['passed'],flush=True);return folder

def details(parent,id,region,steps=(250,125,64),end=2000000):
    setup();parent=pathlib.Path(parent);pg=C.read(parent/'grid.json');z=np.load(parent/'height.npy');initial=np.load(parent/'initial.npy');kind=np.load(parent/'kind-0.npy');erosion=np.load(parent/'erosion.npy')
    radius=round(8000/pg['stepM']);relief=maximum_filter(z,2*radius+1)-minimum_filter(z,2*radius+1);score=relief+4*erosion;valid=kind>=30;rr,cc=np.indices(z.shape);valid&=(rr>24)&(cc>24)&(rr<z.shape[0]-25)&(cc<z.shape[1]-25)
    valid&=distance_transform_edt(kind>=30)*pg['stepM']>=48000
    source_file=parent/'plume-displacement.npy'
    if parent.name=='duskreach-inland-cap':
        source=D.COAST.new_sources('duskreach',5210914,pg)[0];valid&=source>=max(100,float(source.max())*.2)
    elif source_file.exists():
        source=np.load(source_file);valid&=source>=max(100,float(source.max())*.2)
    if not valid.any():raise ValueError('No supported inland source window; keep failed selection rather than sampling a coastal scarp')
    score[~valid]=-np.inf
    row,col=np.unravel_index(np.argmax(score),score.shape);center=list(T.Proj(pg['projection'])(pg['xmin']+col*pg['stepM'],pg['ymax']-row*pg['stepM'],inverse=True));spec={'id':id,'region':region,'center':center}
    C.write(OUT/'detail'/id/'selection.json',{'center':center,'method':'maximum 16km local relief plus erosion inside the new source, at least 48km from coast and supported by the parent interior','parent':str(parent),'sameInitialSurfaceAcrossResolutions':True,'boundaryFadeM':4000})
    for step in steps:
        g=L.grid_window(spec,step,64);g['seed']=5210914;z0=T.sample(initial,pg,g).astype(float);kd=T.sample(kind,pg,g,0).astype('uint8');soil=T.sample(np.load(parent/'soil-initial.npy'),pg,g).astype(float);hard=L.cores(g,kd)
        rr,cc=np.indices(z0.shape);edge=np.minimum.reduce([rr,cc,g['height']-1-rr,g['width']-1-cc])*step;allow=T.ease(edge/4000);allow[hard|(kd<30)]=0
        features=C.read(parent/'source-catalog.json')
        for f in features:f['xy']=list(T.Proj(g['projection'])(*T.Proj(pg['projection'])(*f['xy'],inverse=True)))
        folder=OUT/('detail' if end==2000000 else 'comparison')/id/str(end)/str(step)
        L.solve(folder,g,z0,kd,hard,allow,soil,features,'erosion-only','baseline',.9,parent=(parent,pg),end=end,dt=2500,cap=420)
        print('DETAIL DONE',id,step,flush=True);L.feature_shape.cache_clear();gc.collect()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['joint','keld-water','regional','detail']);a.add_argument('--id');a.add_argument('--steps',default='250,125,64');a.add_argument('--end',type=int,default=2000000);q=a.parse_args()
    if q.stage=='joint':hydrate(build_joint())
    elif q.stage=='keld-water':hydrate(C.TASK/'assembled/keld/5210914/erosion-only/baseline')
    elif q.stage=='regional':
        spec=next(s for s in WINDOWS+C.CFG['provinces'] if s['id']==q.id);regional(spec)
    elif q.stage=='detail':
        parent=OUT/'regional'/q.id;region=q.id.split('-')[0];details(parent,q.id,region,steps=tuple(int(s) for s in q.steps.split(',')),end=q.end)
