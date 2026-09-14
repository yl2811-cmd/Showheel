"""Independent v13 landform-first study, with coupled seasonal lakes.

All stages have immutable input fingerprints. Old v10/v12 output is read-only.
The finite-volume solver resolves mean surface evolution, not rock overhangs.
"""
import pathlib,sys,json,importlib,hashlib,shutil,argparse,time,gc,inspect,marshal
sys.path.insert(0,str(pathlib.Path(__file__).parent))
X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;H=importlib.import_module('landscape-water');R=importlib.import_module('tectonics-refine');REPAIR=importlib.import_module('landscape-repair');STORY=importlib.import_module('landscape-story')
from scipy.ndimage import gaussian_filter,maximum_filter,minimum_filter,label,distance_transform_edt
CFG=json.loads((T.ROOT/'data/tectonics-landscape.json').read_text(encoding='utf8'))
WORK=T.BASE_WORK/'landscape-v14';BASE=X.BASE;OLD=T.BASE_WORK/'erosion-v12';SEEDS=CFG['seeds']
LOADED_MODULE_HASHES={pathlib.Path(m.__file__).name:T.sha(pathlib.Path(m.__file__)) for m in [H,X,T,R,REPAIR,STORY]}
LOADED_SOURCE_BYTES={pathlib.Path(m.__file__).name:pathlib.Path(m.__file__).read_bytes() for m in [H,X,T,R,REPAIR,STORY]};LOADED_SOURCE_BYTES[pathlib.Path(__file__).name]=pathlib.Path(__file__).read_bytes()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,v):T.savejson(p,v)
def setup():
    T.C=read(BASE/'run-config.json');T.C['timesYears']=CFG['timesYears'];T.WORK=WORK;T.MASK=T.BASE_WORK/'archives/erosion-v12-before-landscape-v13/masks';WORK.mkdir(exist_ok=True);save(WORK/'config.json',CFG)
    versions=WORK/'source-versions';versions.mkdir(exist_ok=True);registry={}
    for name,data in LOADED_SOURCE_BYTES.items():
        sha=hashlib.sha256(data).hexdigest();file=versions/(sha+'-'+name)
        if not file.exists():file.write_bytes(data)
        registry[name]=file.name
    save(versions/(fingerprint(registry)+'.json'),registry)
def grid_region(region,step):
    pg=read(BASE/region/'grid.json');return {**pg,'stepM':step,'width':round((pg['width']-1)*pg['stepM']/step)+1,'height':round((pg['height']-1)*pg['stepM']/step)+1,'region':region,'id':region}
def grid_window(spec,step,width=None):
    pg=read(BASE/spec['region']/'grid.json');p=T.Proj(pg['projection']);cx,cy=p(*spec['center']);width=width or spec.get('widthKm',CFG['islandWidthKm'] if spec['region']=='keld' else CFG['regionalWidthKm']);n=round(width*1000/step)+1
    return {**pg,'id':spec['id'],'region':spec['region'],'width':n,'height':n,'stepM':step,'xmin':cx-(n-1)*step/2,'ymax':cy+(n-1)*step/2}
def cores(g,kind):
    hard=(kind==80);bank=X.bank_site()['coordinates']
    for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
        if f['geometry']['type']!='Point' or f.get('id') in ['V01','V02','WH']:continue
        q=bank if f.get('id')=='RB' else f['geometry']['coordinates'];radius=600 if f.get('id')=='RB' else 20000;hard|=T.distance(g,q)<radius
    if g['region']=='aethelgard':
        hard|=T.distance(g,T.F.S['orunLocal']['center'])<50000
        coords=read(BASE/'aethelgard/orun-trace.json')['revised']
        for q in [coords[0],coords[-1]]:hard|=T.distance(g,q)<16000
    return hard
def repair(z,g,kind,hard):
    correction=np.zeros_like(z);weight=np.zeros_like(z);zones={}
    if g['region']=='aethelgard':
        pg=read(BASE/'aethelgard/grid.json');legacy=T.sample(np.load(BASE/'aethelgard/hard-protected.npy'),pg,g,0)>0;land=(kind>=30)&(kind!=80);dx=g['stepM'];xx,yy=T.mesh(g);p=T.Proj(g['projection']);coords=read(BASE/'aethelgard/orun-trace.json')['revised'];pts=np.array([p(*q) for q in coords]);od,_=T.tracefield(g,coords)
        edge=np.zeros_like(legacy);edge[1:]|=legacy[1:]!=legacy[:-1];edge[:-1]|=legacy[1:]!=legacy[:-1];edge[:,1:]|=legacy[:,1:]!=legacy[:,:-1];edge[:,:-1]|=legacy[:,1:]!=legacy[:,:-1]
        coast=distance_transform_edt(land)*dx;away=od>110000
        for ridge in T.D['ridges']:
            if ridge['id'] in ['marneth','marneth-sw']:
                d,_=T.tracefield(g,ridge['geometry']['coordinates']);away&=d>100000
        broad=gaussian_filter(z,max(.5,110000/dx));residual=np.clip(z-gaussian_filter(z,max(.5,18000/dx)),-80,80);target=broad+residual
        for name,domain in [('west',xx<pts[0,0]+80000),('east',xx>pts[-1,0]-40000)]:
            original_edge=edge&domain&land&(coast>50000)&away
            if not original_edge.any():continue
            distance=distance_transform_edt(~original_edge)*dx
            w=(1-T.ease((distance-40000)/120000))*land*T.ease((coast-16000)/64000)*T.ease((od-60000)/80000);w*=T.ease(distance_transform_edt(~hard)*dx/60000)
            # Reconstruct the inherited hard-mask seam itself, not a newly
            # guessed endpoint ray. Named ridges taper out of the correction.
            for ridge in T.D['ridges']:
                if ridge['id'] in ['marneth','marneth-sw']:
                    d,_=T.tracefield(g,ridge['geometry']['coordinates']);w*=T.ease((d-60000)/80000)
            change=(target-z)*w;correction+=change;weight=np.maximum(weight,w);zones[name]={'cells':int(np.count_nonzero(w>.01)),'maximumChangeM':float(abs(change).max()),'centroid':list(p(float(np.sum(xx*w)/max(w.sum(),1)),float(np.sum(yy*w)/max(w.sum(),1)),inverse=True)),'edgeSource':'frozen v10 hard-protected boundary outside named ridges and coast'}
    result=z+correction;result[hard]=z[hard]
    return result,correction,weight,zones
def initial_region(region,seed,g):
    pg=read(BASE/region/'grid.json');folder=BASE/region/str(seed);z=T.sample(np.load(folder/'height.npy'),pg,g).astype(float);kind=T.sample(np.load(folder/'kind.npy') if (folder/'kind.npy').exists() else np.load(BASE/region/'kind.npy'),pg,g,0);kind=np.where(kind==80,80,np.where(kind==200,200,np.where(kind>=30,70,0)));hard=cores(g,kind);original=z.copy();z,correction,weight,zones=repair(z,g,kind,hard)
    marked_records=[];marked_change=np.zeros_like(z)
    if region=='aethelgard' and REPAIR.ANNOTATIONS.exists():
        legacy=T.sample(np.load(BASE/region/'hard-protected.npy'),pg,g,0);z,marked_change,marked_weight,marked_records=REPAIR.reconstruct(z,g,kind,hard,legacy);weight=np.maximum(weight,marked_weight);kind[(kind==200)&(marked_weight>.01)&~hard]=70
    # The legacy lake raster contains water surfaces, not bathymetry. Infer a
    # shallow bowl from its shore for the candidate; ordinary lakes are free.
    lakes=(kind==200)&~hard
    if lakes.any():
        _,idx=distance_transform_edt(lakes,return_indices=True);shore=z[tuple(idx)];depth=np.minimum(100,distance_transform_edt(lakes)*g['stepM']*.004);z[lakes]=shore[lakes]-depth[lakes];kind[lakes]=70
    ocean=kind==0;z[ocean]=-distance_transform_edt(ocean)[ocean]*g['stepM']*.01;z[hard]=original[hard]
    z,story_change,story_record=STORY.reconstruct(z,g,kind,hard,X.selected_route() if region=='aethelgard' else None)
    allow=T.ease(distance_transform_edt(~hard)*g['stepM']/24000);allow[hard]=0;allow[ocean]=0
    soil=T.sample(np.load(folder/'soil.npy'),pg,g);soil=np.maximum(0,soil);soil[hard]=0
    return z,kind,hard,allow,soil,{'original':original,'base-repair':z-original,'artifact-repair':correction+marked_change,'story-repair':story_change,'storyRecord':story_record,'repair-weight':weight,'zones':zones,'markedRegions':marked_records,'oldLakeReconstructedCells':int(lakes.sum())}
def proxy(z,g,kind,rain_factor=1.):
    dx=g['stepM'];xx,yy=T.mesh(g);lon,lat=T.Proj(g['projection'])(xx,yy,inverse=True);coast=distance_transform_edt(kind>=30)*dx;broad=gaussian_filter(z,max(.5,12000/dx));gy,gx=np.gradient(broad,dx);vx=np.where(abs(lat)<32,-.85,.85);vy=np.where(lat>0,.35,-.35);up=np.maximum(gx*vx-gy*vy,0);lee=np.maximum(-gx*vx+gy*vy,0)
    rain=np.clip((.35+.35+1.05*np.exp(-coast/420000)+np.minimum(2,up*35))*np.exp(-np.maximum(z-1600,0)/4500)*np.exp(-np.minimum(2,lee*30)),.035,3.5)*rain_factor;temp=30-.34*abs(lat)-.0056*z;evap=np.minimum(rain,np.maximum(.03,(temp+6)*.025));runoff=(rain-evap)*.8
    return {'rain':rain,'temperature':temp,'evap':evap,'runoff':runoff,'recharge':(rain-evap)*.2,'humidity':np.clip(rain/(.5+np.maximum(temp,0)*.05),.02,1),'latitude':lat}
def catalog(region,seed,gain=1.):
    result=[];pg=read(BASE/region/'grid.json');p=T.Proj(pg['projection']);rng=np.random.default_rng(seed+917)
    for province in CFG['provinces']:
        if province['region']!=region:continue
        x,y=p(*province['center']);scale=.45 if region=='keld' else 1.;candidates=[]
        for n in range(16):
            angle={'aethelgard':.4,'vorhan':1.1,'duskreach':-.4,'keld':1.15}[region]+rng.uniform(-.25,.25);cx=x+rng.uniform(-240000,240000)*scale;cy=y+rng.uniform(-240000,240000)*scale
            candidates.append({'id':province['id']+'-'+str(n),'province':province['id'],'family':province['family'] if n%3==0 else str(rng.choice(['bench','tilted','basin'],p=[.6,.25,.15])),'xy':[cx,cy],'center':list(p(cx,cy,inverse=True)),'lengthM':rng.uniform(40000,105000)*scale,'widthM':rng.uniform(15000,45000)*scale,'reliefM':float(rng.uniform(160,420)*gain),'angleRadians':angle,'phase':float(rng.uniform(-3,3)),'startYear':int(rng.uniform(0,1000000)),'durationYears':int(rng.uniform(180000,600000)),'initialFraction':.45,'scale':'medium'})
        result+=candidates[:round(8*gain)]
    if region=='aethelgard':result+=REPAIR.sources(pg,seed,gain)
    return result
from functools import lru_cache
@lru_cache(maxsize=96)
def feature_shape(grid_json,feature_json):
    g=json.loads(grid_json);f=json.loads(feature_json);xx,yy=T.mesh(g);dx=g['stepM'];cx,cy=f['xy'];angle=f['angleRadians'];u=((xx-cx)*np.cos(angle)+(yy-cy)*np.sin(angle))/f['lengthM'];v=(-(xx-cx)*np.sin(angle)+(yy-cy)*np.cos(angle))/f['widthM'];v-=.10*np.sin(u*3+f['phase'])+.045*np.sin(u*7-f['phase']);envelope=T.ease((1-abs(u))/.25)*T.ease((1-abs(v))/.32)
    if f['family']=='bench':shape=envelope*(.85+.12*u+.03*v)
    elif f['family']=='tilted':shape=envelope*(.58+.42*np.tanh((v+.35)*5))
    else:shape=envelope*(-.45+.35*np.exp(-((abs(v)-.65)/.17)**2))
    if f.get('authorisedRepairRegion'):
        feature=next(v for v in REPAIR.read()['features'] if v['id']==f['authorisedRepairRegion']);mask=T.raster([feature['geometry']],g);support=1-T.ease(distance_transform_edt(~mask)*dx/32000);pg=read(BASE/g['region']/'grid.json');old=T.sample(np.load(BASE/g['region']/'5210914/height.npy'),pg,g);shape*=support*T.ease((3800-old)/1000)
    return shape.astype('float32')
def form(g,features,allow,year0=None,year1=None,exclude=()):
    out=np.zeros_like(allow);resolved=[];dx=g['stepM'];grid_json=json.dumps(g,sort_keys=True)
    for f in features:
        if f['id'] in exclude or min(f['lengthM'],f['widthM'])*2<4*dx:continue
        if year0 is None:amount=f['initialFraction']
        else:amount=(1-f['initialFraction'])*float(T.ease((year1-f['startYear'])/f['durationYears'])-T.ease((year0-f['startYear'])/f['durationYears']))
        if year0 is not None and amount==0:continue
        shape=feature_shape(grid_json,json.dumps(f,sort_keys=True))
        if not np.any(shape):continue
        out+=shape*f['reliefM']*amount;resolved.append(f['id'])
    if g['region']=='aethelgard':out*=X.C.quiet(g)
    return out*allow,resolved
def metrics(z0,z,g,features,erosion,deposition,quiet_mask=None,land=None):
    dx=g['stepM'];window=max(3,round(8000/dx));relief=maximum_filter(z,window)-minimum_filter(z,window);slope=np.hypot(*np.gradient(z,dx));floor=minimum_filter(z,window);land=(z>0) if land is None else land;tops=(slope<.04)&(z-floor>100)&land;labs,n=label(tops);areas=np.bincount(labs.ravel())*dx*dx/1e6;tops_count=int(np.count_nonzero(areas[1:]>=max(1,4*dx*dx/1e6)));rows=[]
    for f in features:
        if min(f['lengthM'],f['widthM'])*2<4*dx:continue
        cx,cy=f['xy'];r=round((g['ymax']-cy)/dx);c=round((cx-g['xmin'])/dx);rad=max(2,round(min(f['lengthM'],f['widthM'])/dx));a=z0[max(0,r-rad):min(g['height'],r+rad+1),max(0,c-rad):min(g['width'],c+rad+1)];b=z[max(0,r-rad):min(g['height'],r+rad+1),max(0,c-rad):min(g['width'],c+rad+1)]
        if not (0<=r<g['height'] and 0<=c<g['width']):continue
        if a.size<9 or b.shape!=a.shape:continue
        before=float(np.ptp(np.percentile(a,[10,95])));after=float(np.ptp(np.percentile(b,[10,95])));ratio=after/max(1,before);gy,gx=np.gradient(b,dx);upper=b>np.percentile(b,65);flat=upper&(np.hypot(gx,gy)<.04);components,num=label(flat);counts=np.bincount(components.ravel());largest=int(counts[1:].max(initial=0));fragmented=bool(flat.sum()>4 and largest/flat.sum()<.25);upper0=a>np.percentile(a,65);flat0=upper0&(np.hypot(*np.gradient(a,dx))<.04);table_ratio=float(flat.sum()/max(1,flat0.sum()));weak=after<CFG['minimumProminenceM'];retained=ratio>=.3 and not weak and (f['family']!='bench' or (not fragmented and table_ratio>=.3));rows.append({'id':f['id'],'family':f['family'],'initialProminenceM':before,'finalProminenceM':after,'retained':retained,'ratio':ratio,'tabletopAreaRetention':table_ratio,'tabletopFragmented':fragmented,'weakRelief':weak,'transformed':bool(np.max(abs(b-a))>max(20,.15*before))})
    lost=sum(not r['retained'] for r in rows);quiet_fraction=1. if quiet_mask is None or not quiet_mask.any() else float(np.mean((slope[quiet_mask]<.04)&(relief[quiet_mask]<120)));quiet_components=label((slope<.04)&(relief<120))[1]
    return {'resolved':len(rows),'lost':lost,'lostFraction':lost/max(1,len(rows)),'renewalNeeded':lost/max(1,len(rows))>CFG['lostFractionTrigger'] or any(r['weakRelief'] or (r['family']=='bench' and r['tabletopFragmented']) for r in rows),'features':rows,'tabletopCandidates':tops_count,'tabletopAreaKm2':float(tops.sum()*dx*dx/1e6),'quietAreaRetention':quiet_fraction,'quietConnectedComponents':int(quiet_components),'maximumReliefM':float(relief.max()),'incisionP99M':float(np.percentile(erosion,99)),'maximumIncisionM':float(erosion.max()),'depositedM3':float(deposition.sum()*dx*dx),'localReliefWindowM':window*dx,'classification':'resolved morphological candidates, not definitive geological identifications'}
def fingerprint(inputs):return hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
def solve(folder,g,initial,kind,hard,allow,soil,features,mode,scenario,gain,parent=None,end=2000000,dt=5000,cap=220.):
    folder.mkdir(parents=True,exist_ok=True);save(folder/'grid.json',g);factor=CFG['rainScenarios'][scenario];source_hash=dict(LOADED_MODULE_HASHES);source_hash['config']=fingerprint(CFG);source_hash['solverFunctions']=hashlib.sha256(b''.join(marshal.dumps(f.__code__) for f in [solve,form,feature_shape.__wrapped__,proxy,X.conservative_slope,R.ParentForcing.__init__,R.ParentForcing.at,R.ParentForcing.snapshot,R.boundary_flux,T.weights])).hexdigest();parent_hashes={p.name:T.sha(p) for p in parent[0].glob('*.npy') if p.name.startswith(('height-','discharge-','receiver-','sediment-flux-','soil-initial'))} if parent else {};inputs={'grid':g,'seed':g.get('seed'),'mode':mode,'scenario':scenario,'gain':gain,'end':end,'dt':dt,'capM':cap,'code':source_hash,'initial':hashlib.sha256(initial.tobytes()).hexdigest(),'features':fingerprint(features),'allow':hashlib.sha256(allow.tobytes()).hexdigest(),'soil':hashlib.sha256(soil.tobytes()).hexdigest(),'kind':hashlib.sha256(kind.tobytes()).hexdigest(),'hard':hashlib.sha256(hard.tobytes()).hexdigest(),'parent':parent_hashes};key=fingerprint(inputs)
    if (folder/'run-key.json').exists() and read(folder/'run-key.json')['key']==key and (folder/'simulation.json').exists() and read(folder/'simulation.json')['passed']:return read(folder/'simulation.json')
    if (folder/'simulation.json').exists():(folder/'simulation.json').rename(folder/f'previous-simulation-{time.time_ns()}.json')
    save(folder/'request.json',inputs);np.save(folder/'initial.npy',initial);np.save(folder/'soil-initial.npy',soil);np.save(folder/'kind-0.npy',kind);np.save(folder/'protected.npy',hard);np.save(folder/'allow.npy',allow);save(folder/'source-catalog.json',features)
    z=initial.copy();soil=soil.copy();a=dx=g['stepM'];area=dx*dx;shape=z.shape;controls=T.weights(g['region'],g);controls['weathering']*=2;allow=allow*(1-controls['protection']);frame=np.zeros(shape,bool);frame[[0,-1]]=True;frame[:,[0,-1]]=True;allow[frame]=0
    forcing=R.ParentForcing(g['region'],parent[0],g,parent[1]) if parent else None
    if forcing:save(folder/'parent-boundary.json',{'source':str(parent[0]),'sourceHashes':forcing.hashes,'years':forcing.years,'parentHeightSha256':T.sha(parent[0]/'height.npy')})
    totals={k:np.zeros(shape) for k in ['erosion','deposition','tectonic-uplift','slope-transport','weathering']};history=[];now=0;depth=np.zeros(shape);quiet=(np.hypot(*np.gradient(initial,dx))<.025)&((maximum_filter(initial,max(3,round(8000/dx)))-minimum_filter(initial,max(3,round(8000/dx))))<80)&(kind>=30);hydro=None;sed=np.zeros(shape);water_years=0
    weakness=np.ones(shape);xx,yy=T.mesh(g);formation_allow=allow*T.ease((initial-200)/600)*(1-STORY.domain(g));cap_field=np.full(shape,cap)
    if g['region']=='aethelgard':
        od,_=T.tracefield(g,read(BASE/'aethelgard/orun-trace.json')['revised']);cap_field[od<110000]=420
        md,_=T.tracefield(g,next(r['geometry']['coordinates'] for r in T.D['ridges'] if r['id']=='marneth'));cap_field[(md<100000)&(od>=110000)]=60
    np.save(folder/'cap-thickness.npy',cap_field)
    for f in features:
        cx,cy=f['xy'];angle=f['angleRadians'];cross=-(xx-cx)*np.sin(angle)+(yy-cy)*np.cos(angle);along=(xx-cx)*np.cos(angle)+(yy-cy)*np.sin(angle);weakness+=1.5*np.exp(-(cross/max(2*dx,5000))**2)*T.ease(1-(along/f['lengthM'])**2)
    def water(cycles=1,converge=False):
        nonlocal hydro,depth,water_years
        bound,qw,qs=forcing.at(now) if forcing else (None,np.zeros(shape),np.zeros(shape));cl=proxy(z,g,kind);land=X.land_mask(z,kind);hydro=H.run(z,land,dx,cl,factor,cycles=cycles,external=qw,initial_depth=depth,seasonality=CFG['seasonalityAmplitude'],latitude=float(np.median(cl['latitude'])),converge=converge,max_cycles=CFG.get('maximumSeasonalCycles',120));depth=hydro['lake-depth'];water_years+=len(hydro['history']);return cl,qs
    def snapshot():
        for k,v in {'height':z,'discharge':hydro['discharge'],'receiver':hydro['receiver'],'sediment-flux':sed,'lake-depth':depth,'soil':soil,**totals}.items():np.save(folder/f'{k}-{now}.npy',v.astype('int32') if k=='receiver' else v.astype('float32'))
        np.save(folder/f'kind-{now}.npy',np.where(X.land_mask(z,kind),70,np.where(kind==80,80,0)).astype('uint8'));save(folder/f'lakes-{now}.json',hydro['lakes'])
    water(20,True);snapshot()
    for target in [v for v in CFG['timesYears'][1:] if v<=end]:
        while now<target:
            if (WORK/'STOP').exists():
                save(folder/'paused.json',{'year':now,'reason':'Task stop signal; resume from the same immutable request by rerunning'});raise InterruptedError('Landscape task paused')
            step=min(dt,target-now);before=z.copy();bound,qw,qs=forcing.at(now+step) if forcing else (z,np.zeros(shape),np.zeros(shape));exchange=float((bound[frame]-z[frame]).sum()*area) if forcing else 0.
            if forcing:z[frame]=bound[frame]
            u=form(g,features,formation_allow,now,now+step)[0] if mode=='episodic' else np.zeros(shape);z+=u;totals['tectonic-uplift']+=u
            # The first seasonal year releases water displaced by the changed
            # bed. Use the second year's mean for long-term incision, so one
            # transient lake-release pulse is not repeated for millennia.
            cl,qs_now=water(2);tp=hydro['topology'];exposure=np.maximum(0,initial+totals['tectonic-uplift']-z);hardrock=(exposure<cap_field)|(np.mod(np.maximum(0,exposure-cap_field),440)>260)
            k=np.where(hardrock,T.C['lithology']['hardK'],T.C['lithology']['softK']*3)*weakness*controls['water']/np.maximum(.2,controls['rock-strength'])*(.98)
            weather=.00004*step*np.exp(-soil/.7)*(1-hardrock*.7)*allow*controls['weathering'];soil+=weather;totals['weathering']+=weather
            z,soil,er,de,export,sed,res,lakedep=H.transport(z,soil,tp['order'],tp['transport-receiver'],hydro['discharge'].ravel(),allow.ravel(),k.ravel(),dx,step,qs,tp['basin'],tp['representative'],tp['starts'],tp['nodes'],tp['spill'],depth.ravel())
            z,soil,sl=X.conservative_slope(z,soil,allow,dx,step,hardrock,1-cl['humidity'],controls);totals['erosion']+=er;totals['deposition']+=de;totals['slope-transport']+=sl
            supplied=float(qs.sum()*step);residual=float((z-before-u).sum()*area+export-exchange-supplied);scale=max(1,float(abs(z-before).sum()*area),abs(export),supplied,abs(exchange));solid_error=abs(residual)/scale
            row={'year':now+step,'dtYears':step,'waterYearsIntegrated':water_years,'waterRelativeError':hydro['maxWaterRelativeError'],'solidRelativeError':solid_error,'solidResidualM3':residual,'externalSedimentM3':supplied,'exportM3':export,'lakeDepositionM3':lakedep,'upliftM3':float(u.sum()*area),'boundaryExchangeM3':exchange,'minimumSoilM':float(soil.min())};history.append(row)
            if solid_error>CFG['maximumSolidRelativeError'] or soil.min()<-1e-10:save(folder/'failure.json',row);raise RuntimeError('Coupled water/sediment verification failed '+str(folder)+' '+str(row))
            now+=step
        water(5,True);snapshot();save(folder/'progress.json',{'year':now,'target':end,'lastStep':history[-1]});T.log('LANDSCAPE '+str(folder.relative_to(WORK))+' '+str(now))
    finalkind=np.where(X.land_mask(z,kind),70,np.where(kind==80,80,0));finalkind[depth>.05]=200
    for k,v in {'height':z,'soil':soil,'kind':finalkind,'bedrock':z-soil,'discharge':hydro['discharge'],'receiver':hydro['receiver'],'sediment-flux':sed,'lake-depth':depth,'lake-level':hydro['lake-level'],'lake-occurrence':hydro['lake-occurrence'],'wetness':hydro['wetness'],'sand':soil*(1-cl['humidity']),**totals}.items():np.save(folder/(k+'.npy'),v.astype('int32') if k=='receiver' else v.astype('float32'))
    fixed=hard&~frame;retention=metrics(initial,z,g,features,totals['erosion'],totals['deposition'],quiet,finalkind==70);save(folder/'retention.json',retention);save(folder/'hydrology.json',{k:v for k,v in hydro.items() if k in ['lakes','history','maxWaterRelativeError','climateStatus','seasonality','initialStorageM3','releasedByBedChangeM3','convergence']})
    story=STORY.check(g,z,depth,hydro['lake-occurrence'],hydro['lake-max-depth']);save(folder/'story-geography.json',story)
    np.save(folder/'lake-min-depth.npy',hydro['lake-min-depth'].astype('float32'));np.save(folder/'lake-max-depth.npy',hydro['lake-max-depth'].astype('float32'));np.save(folder/'story-constraints.npy',STORY.domain(g))
    report={'effectiveYears':now,'gridM':dx,'seed':inputs.get('seed'),'mode':mode,'scenario':scenario,'enhancement':gain,'history':history,'protectedMaxDeltaM':float(abs(z[fixed]-initial[fixed]).max(initial=0)),'maxWaterRelativeError':max(v['waterRelativeError'] for v in history),'maxVolumeRelativeError':max(v['solidRelativeError'] for v in history),'quietAreaRetention':retention['quietAreaRetention'],'retentionPassed':not retention['renewalNeeded'],'tabletopCandidates':retention['tabletopCandidates'],'lakeCount':sum(v['state']!='dry-basin' for v in hydro['lakes']),'solver':'conservative semi-implicit finite-volume stream power, explicit sediment flux, stratified erodibility, level-pool lakes and slope debris','unresolved':'No overhang or full 3D cliff failure model; subgrid channels are mean rock removal','realClimate':False}
    report['passed']=report['protectedMaxDeltaM']<=1e-6 and report['maxWaterRelativeError']<1e-8 and report['maxVolumeRelativeError']<1e-7;report['storyGeographyPassed']=story['passed'];report['waterConvergence']=hydro['convergence'];report['selected']=report['passed'] and story['passed'] and hydro['convergence']['passed'];save(folder/'simulation.json',report);save(folder/'run-key.json',{'key':key,'inputs':inputs});return report

def case_path(stage,id,seed,mode,scenario,gain=1.):return WORK/stage/id/str(seed)/mode/scenario/f'g{gain:g}'
def cases(args):
    for seed in [args.seed] if args.seed else SEEDS:
        for mode in [args.mode] if args.mode!='both' else CFG['modes']:
            for scenario in [args.scenario] if args.scenario!='all' else (CFG['rainScenarios'] if seed==SEEDS[0] else ['baseline']):yield seed,mode,scenario
def prepare(args=None):
    setup();freeze=T.BASE_WORK/'archives/erosion-v12-before-landscape-v13/freeze.json';assert freeze.exists(),'Freeze v12 first'
    for region in X.REGIONS if args is None or args.region=='all' else [args.region]:
        g=grid_region(region,16000)
        for seed in SEEDS:
            out=WORK/'base'/region/str(seed);out.mkdir(parents=True,exist_ok=True);z,kind,hard,allow,soil,record=initial_region(region,seed,g)
            for name,value in {'height':z,'kind':kind,'protected':hard,'allow':allow,'soil':soil,**{k:v for k,v in record.items() if isinstance(v,np.ndarray)}}.items():np.save(out/(name+'.npy'),value)
            save(out/'grid.json',g);save(out/'story-repair.json',record['storyRecord']);save(out/'repair.json',{'zones':record['zones'],'markedRegions':record['markedRegions'],'oldLakeReconstructedCells':record['oldLakeReconstructedCells'],'coreDeltaM':float(abs(z[hard]-record['original'][hard]).max(initial=0)),'sourceHeightSha256':T.sha(BASE/region/str(seed)/'height.npy'),'lakeBedHypothesis':'author-marked lakes use flank-conditioned bed; remaining ordinary lakes use shore-derived shallow bowls; not measured bathymetry','formalMapChanged':False})
    save(WORK/'freeze-lineage.json',{'v12FreezeSha256':T.sha(freeze),'v10FreezeSha256':T.sha(X.ARCHIVE/'freeze.json'),'source':str(BASE),'clock':'zero at saved v10 final plus separately recorded baseline repair','repeatedOldUplift':False})
    save(WORK/'operator-verification.json',H.tests());T.log('V13 BASE PREPARED')
def coarse(args):
    setup()
    for region in X.REGIONS if args.region=='all' else [args.region]:
        for seed,mode,scenario in cases(args):
            source=WORK/'base'/region/str(seed);g=read(source/'grid.json');g['seed']=seed;z=np.load(source/'height.npy');kind=np.load(source/'kind.npy');hard=np.load(source/'protected.npy');allow=np.load(source/'allow.npy');soil=np.load(source/'soil.npy');features=catalog(region,seed,args.gain);added,resolved=form(g,features,allow*T.ease((z-200)/600)*(1-STORY.domain(g)));folder=case_path('coarse',region,seed,mode,scenario,args.gain);folder.mkdir(parents=True,exist_ok=True);np.save(folder/'formation-initial.npy',added);save(folder/'resolved-sources.json',resolved)
            result=solve(folder,g,z+added,kind,hard,allow,soil,features,mode,scenario,args.gain,end=args.end,dt=10000);save(folder/'coast.json',X.coast_report(g,kind,np.load(folder/'height.npy'),region,z+added,hard));gc.collect()
def specifications():
    specs=list(CFG['provinces']);record=read(WORK/'base/aethelgard/5210914/repair.json')
    if REPAIR.ANNOTATIONS.exists():
        p=T.Proj(read(BASE/'aethelgard/grid.json')['projection']);titles=['北部旧湖盆','西北旧湖盆','Orun 西侧坡地','Marneth 西侧坡地','东南沿岸坡地']
        for feature,title in zip(REPAIR.read()['features'],titles):
            xy=np.array([p(*q) for q in feature['geometry']['coordinates'][0]]);cx,cy=(xy.min(axis=0)+xy.max(axis=0))*.5;width=float(np.ceil((np.ptp(xy,axis=0).max()+128000)/32000)*32);specs.append({'id':feature['id'],'region':'aethelgard','center':list(p(cx,cy,inverse=True)),'family':'bench','title':title,'widthKm':max(768,width),'repairSide':feature['id'],'markedRepair':True})
    else:
        for side,data in record['zones'].items():specs.append({'id':'orun-'+side,'region':'aethelgard','center':data['centroid'],'family':'bench','title':'Orun · '+side,'widthKm':768,'repairSide':side})
    return specs
def selected_detail(folder,spec,width=64):
    g=read(folder/'grid.json');z=np.load(folder/'height.npy');er=np.load(folder/'erosion.npy');kind=np.load(folder/'kind.npy');hard=np.load(folder/'protected.npy');score=maximum_filter(z,17)-minimum_filter(z,17);score*=1+np.sqrt(np.maximum(er,0));r,c=np.indices(z.shape);margin=width*500+24000;valid=(np.minimum.reduce([r,c,g['height']-1-r,g['width']-1-c])*g['stepM']>margin)&~hard&(kind>=30)&(kind!=200);score[~valid]=0
    row,col=np.unravel_index(np.argmax(score),score.shape);return list(T.Proj(g['projection'])(g['xmin']+col*g['stepM'],g['ymax']-row*g['stepM'],inverse=True))
def nested(args,detail=False):
    setup()
    for spec in specifications():
        if args.region not in ['all',spec['region'],spec['id']]:continue
        for seed,mode,scenario in cases(args):
            if detail and seed!=SEEDS[0] and args.seed is None:continue
            parent=case_path('regional' if detail else 'coarse',spec['id'] if detail else spec['region'],seed,mode,scenario,args.gain)
            if not (parent/'simulation.json').exists():raise RuntimeError('Missing completed parent '+str(parent))
            pg=read(parent/'grid.json');s=dict(spec);width=64 if detail else spec.get('widthKm',256 if spec['region']=='keld' else 768);step=250 if detail else 2000
            if detail:
                choice=WORK/'windows'/(spec['id']+'.json')
                if choice.exists():s['center']=read(choice)['center']
                else:s['center']=selected_detail(parent,s);save(choice,{'center':s['center'],'selection':'maximum combined relief and erosion within supported interior','parent':str(parent)})
            g=grid_window(s,step,width);g['seed']=seed;initial=T.sample(np.load(parent/'initial.npy'),pg,g);kind=T.sample(np.load(parent/'kind-0.npy'),pg,g,0);hard=cores(g,kind);allow=T.ease(distance_transform_edt(~hard)*step/24000);allow[hard|(kind<30)]=0;rows,cols=np.indices(initial.shape);distance=np.minimum.reduce([rows,cols,g['height']-1-rows,g['width']-1-cols])*step;fade=CFG['detailBoundaryFadeM'] if detail else CFG['regionalBoundaryFadeM'];allow*=T.ease(distance/fade);soil=T.sample(np.load(parent/'soil-initial.npy'),pg,g);features=catalog(spec['region'],seed,args.gain);used=read(parent/'resolved-sources.json');added,resolved=form(g,features,allow*T.ease((initial-200)/600),exclude=used);initial+=added;original_grid=read(BASE/spec['region']/'grid.json');original=T.sample(np.load(BASE/spec['region']/str(seed)/'height.npy'),original_grid,g);initial[hard]=original[hard];folder=case_path('detail' if detail else 'regional',spec['id'],seed,mode,scenario,args.gain);folder.mkdir(parents=True,exist_ok=True);np.save(folder/'formation-initial.npy',added);save(folder/'resolved-sources.json',sorted(set(used+resolved)));save(folder/'window.json',{**s,'widthKm':width,'stepM':step,'boundaryFadeM':fade,'newSources':resolved,'coreReference':'frozen v10 height, sampled directly rather than through modified coarse neighbors'})
            solve(folder,g,initial,kind,hard,allow,soil,features,mode,scenario,args.gain,parent=(parent,pg),end=args.end,dt=2000 if detail else 5000,cap=420 if spec.get('repairSide') else 220);gc.collect()
def main():
    global WORK
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['prepare','coarse','regional','detail','all'],default='prepare');ap.add_argument('--work',type=pathlib.Path,default=WORK);ap.add_argument('--region',default='all');ap.add_argument('--seed',type=int);ap.add_argument('--mode',choices=['both','erosion-only','episodic'],default='both');ap.add_argument('--scenario',choices=['all','dry','baseline','wet'],default='all');ap.add_argument('--gain',type=float,default=1);ap.add_argument('--end',type=int,default=2000000);args=ap.parse_args();WORK=args.work;setup()
    if args.stage in ['prepare','all']:prepare(args)
    if args.stage in ['coarse','all']:coarse(args)
    if args.stage in ['regional','all']:nested(args)
    if args.stage in ['detail','all']:nested(args,True)
if __name__=='__main__':main()
