"""v10 -> independent erosion / episodic construction candidates.

The geological clock starts at the saved v10 final field. Coast bed, mobile
sediment and ocean export are separate reservoirs. No civil heat or GCM claim.
"""
import pathlib,sys,json,shutil,importlib,time,argparse,hashlib,math,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent))
C=importlib.import_module('tectonics-continuation');T=C.T;np=T.np
from scipy.ndimage import gaussian_filter,maximum_filter,minimum_filter
from scipy.spatial import cKDTree
CFG=json.loads((T.ROOT/'data/tectonics-erosion.json').read_text(encoding='utf8'))
SOURCE=T.BASE_WORK/CFG['baseStudy'];ARCHIVE=T.BASE_WORK/'archives/geomorph-v10-before-erosion';BASE=ARCHIVE/'study'
DEFAULT=T.BASE_WORK/'erosion-v12';REGIONS=['aethelgard','vorhan','duskreach','keld']

def read(p):return json.loads(p.read_text(encoding='utf8'))
def freeze():
    manifest=ARCHIVE/'freeze.json'
    if manifest.exists():
        record=read(manifest)
        for f,h in record['hashes'].items():
            if T.sha(ARCHIVE/f)!=h:raise RuntimeError('Frozen v10 changed: '+f)
        return record
    files={};ARCHIVE.mkdir(parents=True,exist_ok=True)
    for root,dest in [(SOURCE,BASE),(T.ROOT/'foundation/evolution',ARCHIVE/'web')]:
        for p in root.rglob('*'):
            if p.is_file() and not any(v in p.parts for v in ['__pycache__','mpl']):
                q=dest/p.relative_to(root);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);files[q.relative_to(ARCHIVE).as_posix()]=T.sha(q)
    for p in [T.ROOT/'evolution.html',T.ROOT/'tectonics-view.js',T.ROOT/'tectonics-brush.js']:
        q=ARCHIVE/'frontend'/p.name;q.parent.mkdir(exist_ok=True);shutil.copy2(p,q);files[q.relative_to(ARCHIVE).as_posix()]=T.sha(q)
    record={'study':'geomorph-v10','createdUnix':time.time(),'hashes':files,'bytes':sum((ARCHIVE/f).stat().st_size for f in files)};T.savejson(manifest,record);T.log('FROZEN v10 '+str(len(files))+' files');return record

def setup(work,mask=None):
    work.mkdir(parents=True,exist_ok=True);T.WORK=work;T.MASK=mask;T.C=read(BASE/'run-config.json');T.C.update(version=CFG['version'],timesYears=CFG['timesYears'],stepYears=CFG['screening']['maximumStepYears']);T.C['erosionCycle']=CFG;T.atmosphere=C.atmosphere
    T.savejson(work/'run-config.json',T.C)
    return T.C

def load_saved(region,seed,g,name='height',order=1):
    pg=read(BASE/region/'grid.json');p=BASE/region/str(seed)/(name+'.npy')
    if not p.exists():p=BASE/region/(name+'.npy')
    return T.sample(np.load(p),pg,g,order)

def history_sample(a,g):
    hg=read(BASE/CFG['river']['sourceCase']/'grid.json');xx,yy=T.mesh(g)
    if hg['projection']!=g['projection']:
        lo,la=T.Proj(g['projection'])(xx,yy,inverse=True);xx,yy=T.Proj(hg['projection'])(lo,la)
    affine=hg['worldAffine'];xx-=affine['origin'][0];yy-=affine['origin'][1]
    u=xx*affine['across'][0]+yy*affine['across'][1];v=xx*affine['downstream'][0]+yy*affine['downstream'][1]
    rows=(v+hg['ymax'])/hg['stepM'];cols=(u-hg['xmin'])/hg['stepM'];valid=(rows>=1)&(rows<hg['height']-2)&(cols>=1)&(cols<hg['width']-2)
    return T.map_coordinates(a,[rows,cols],order=1,mode='nearest',prefilter=False),valid

def selected_route():
    return next(f['geometry']['coordinates'] for f in read(BASE/CFG['river']['sourceCase']/'route.geojson')['features'] if f['geometry']['type']=='LineString' and f['properties']['name'].startswith('Ishkar'))

def bank_site():
    folder=BASE/CFG['river']['sourceCase'];hg=read(folder/'grid.json');z=np.load(folder/'height.npy');route=selected_route();p=T.Proj(hg['projection']);xy=np.array([p(*q) for q in route]);anchor=np.array(p(*CFG['riverbend']['riverReference']));tree=cKDTree(xy)
    offsets=np.arange(-4500,4501,250);xx,yy=np.meshgrid(offsets+anchor[0],offsets+anchor[1]);a=hg['worldAffine'];dx=xx-a['origin'][0];dy=yy-a['origin'][1];u=dx*a['across'][0]+dy*a['across'][1];v=dx*a['downstream'][0]+dy*a['downstream'][1];rr=(v+hg['ymax'])/hg['stepM'];cc=(u-hg['xmin'])/hg['stepM'];zz=T.map_coordinates(z,[rr,cc],order=1,mode='nearest');dist,idx=tree.query(np.column_stack([xx.ravel(),yy.ravel()]));dist=dist.reshape(xx.shape);idx=idx.reshape(xx.shape)
    result=read(folder/'result.json');bed=z[np.array(result['pathRows']),np.array(result['pathColumns'])][idx];gy,gx=np.gradient(zz,250);slope=np.hypot(gx,gy);valid=(np.hypot(xx-anchor[0],yy-anchor[1])<=5000)&(dist>800)&(dist<3500)&(zz>bed+8)&(zz<bed+180)
    score=slope*5000+abs(zz-bed-35)+np.hypot(xx-anchor[0],yy-anchor[1])*.01;score[~valid]=np.inf
    if not np.isfinite(score).any():raise RuntimeError('No bank candidate within authorised 5 km')
    r,c=np.unravel_index(np.argmin(score),score.shape);location=list(p(xx[r,c],yy[r,c],inverse=True))
    return {'id':'RB','name':'Riverbend','coordinates':location,'riverReference':CFG['riverbend']['riverReference'],'offsetM':float(np.hypot(xx[r,c]-anchor[0],yy[r,c]-anchor[1])),'bankHeightAboveChannelM':float(zz[r,c]-bed[r,c]),'resolvedSlope':float(slope[r,c]),'status':'candidate bank on interpolated 2 km history; no claim of a resolved terrace or flood safety','sourceGridM':2000,'formerCoordinates':[-10,9],'routeRedraw':'deferred until terrain selection'}

def constraints(region,g,kind):
    old=load_saved(region,5210914,g,'hard-protected',0)>0;land=(kind>=30)&(kind!=80);coastdist=T.edt(land)*g['stepM']
    # Shore locks were created by the old fixed-coast policy. Remove only that
    # band, then reconstruct all named scene buffers; FAR stays exact.
    old[coastdist<=32000]=False
    scenes=np.zeros_like(old)
    for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
        if f['geometry']['type']=='Point' and f.get('id')!='RB':scenes|=T.distance(g,f['geometry']['coordinates'])<20000
    if region=='aethelgard':
        old[T.distance(g,[-10,9])<22000]=False
        ip=BASE/region/'ishkar-protected.npy'
        if ip.exists():old[load_saved(region,5210914,g,'ishkar-protected',0)>0]=False
        # River reconstruction itself is authorised; other scenic cores are not.
        old|=T.distance(g,bank_site()['coordinates'])<CFG['riverbend']['protectionRadiusM']
    hard=old|scenes|(kind==80)|(kind==200)
    hard[[0,-1],:]=True;hard[:,[0,-1]]=True
    allow=T.ease(T.edt(~hard)*g['stepM']/24000);allow[hard]=0
    return hard,allow,scenes

def event_catalog(region,seed,g,base,allow,density=1,salt=0):
    controls=T.weights(region,g);source=read(BASE/region/str(seed)/'landforms.json');rng=np.random.default_rng(seed+77321+salt+sum(map(ord,region)));selected=[]
    for f in source:
        x,y=f['xy'];rr=int(np.clip(round((g['ymax']-y)/g['stepM']),0,g['height']-1));cc=int(np.clip(round((x-g['xmin'])/g['stepM']),0,g['width']-1))
        if rng.random()>.45*density*controls['relief-density'][rr,cc]:continue
        e=dict(f);e['id']='episode-'+f['id'];e['localSeed']=int(rng.integers(1,2**31));e['reliefM']=float(min(f['reliefM']*.6,rng.uniform(*CFG['eventBudget']['reliefM'])));e['startYear']=int(rng.uniform(0,CFG['eventBudget']['lastStartYear']));e['durationYears']=int(rng.uniform(*CFG['eventBudget']['durationYears']));e['mechanism']='fault-slip';e['lithology']='basalt-cap' if f['family']=='bench' else 'alternating-strong-soft';selected.append(e)
    # Coast episodes use a signed dipping block, not scaled island outlines.
    # All runs record the same displaced-volume budget before density changes.
    lands=[f for f in T.D['land'] if f['id'] in T.C['regions'][region].get('landIds',[]) or ('landPrefix' in T.C['regions'][region] and f['id'].startswith(T.C['regions'][region]['landPrefix']))]
    coast=(((T.edt(kind_land:=base>0)*g['stepM'])<48000)&kind_land&(allow>.5));cells=np.flatnonzero(coast)
    for k,cell in enumerate(rng.choice(cells,min(10 if region=='keld' else 5,len(cells)),replace=False)):
        r,c=np.unravel_index(cell,base.shape);x=g['xmin']+c*g['stepM'];y=g['ymax']-r*g['stepM'];L=rng.uniform(65000,145000);amp=rng.uniform(100,330)*(1 if rng.random()>.35 else -1)
        selected.append({'id':f'{region}-coast-episode-{k}','localSeed':int(rng.integers(1,2**31)),'center':list(T.Proj(g['projection'])(x,y,inverse=True)),'xy':[x,y],'lengthM':L,'widthM':L*rng.uniform(.4,.7),'reliefM':amp,'angleRadians':rng.uniform(0,np.pi),'family':'tilted','phase':rng.uniform(-3,3),'scale':'medium','startYear':int(rng.uniform(0,1000000)),'durationYears':int(rng.uniform(300000,900000)),'mechanism':'coastal-block-rotation','lithology':'basalt-cap','coastal':True})
    return selected

def event_field(g,events,allow,controls,year0,year1,coast_strength=1):
    active=[]
    for e in events:
        f=dict(e);a=T.ease((year0-e['startYear'])/e['durationYears']);b=T.ease((year1-e['startYear'])/e['durationYears']);f['reliefM']*=float(b-a)*(coast_strength if e.get('coastal') else 1)
        if f['reliefM']:active.append(f)
    field=C.displacement(g,active,allow,controls,minimum_cells=4)[0]
    if '_coastDistance' in controls:field*=coast_strength+(1-coast_strength)*T.ease((controls['_coastDistance']-80000)/80000)
    return field

def prepare(work,region,seed,step=16000,grid=None):
    pg=read(BASE/region/'grid.json');g=grid or {**pg,'stepM':step,'width':round((pg['width']-1)*pg['stepM']/step)+1,'height':round((pg['height']-1)*pg['stepM']/step)+1};g['region']=region
    root=work/region;out=root/str(seed);out.mkdir(parents=True,exist_ok=True);T.savejson(root/'grid.json',g);z=load_saved(region,seed,g).astype(float);kind=load_saved(region,seed,g,'kind',0);kind=np.where(kind==80,80,np.where(kind==200,200,np.where(kind>=30,70,0)));hard,allow,scenes=constraints(region,g,kind);base=z.copy();dx=g['stepM']
    if region=='aethelgard':
        folder=BASE/CFG['river']['sourceCase'];hist,valid=history_sample(np.load(folder/'height.npy'),g);d,_=T.tracefield(g,selected_route());weight=(1-T.ease((d-CFG['river']['bedCoreM'])/CFG['river']['bankTransitionM']))*valid;weight[scenes|(kind<30)|(kind==200)]=0;z+=weight*(hist-z)
        T.savejson(out/'river-integration.json',{'source':str(folder),'heightSha256':T.sha(folder/'height.npy'),'maxReconstructionM':float(abs(z-base).max()),'unlockedHistoricBed':True,'subsequentRiverBedLock':False,'gridConvergenceStatus':'selected 2 km history; whole-route spatial convergence still unproved'})
        np.save(root/'override.npy',load_saved(region,seed,g,'override',0))
    coast=(kind==0);z[coast]=-T.edt(coast)[coast]*dx*CFG['coast']['shelfSlope'];allow[coast&(z<-CFG['coast']['shelfWidthM']*CFG['coast']['shelfSlope'])]=0
    # User authorised flooding unprotected inherited coastal lows. Keep their
    # rock heights: this is water occupying a basin, not manufactured uplift.
    bad=(kind>=30)&~land_mask(z,kind);T.savejson(out/'coastal-datum.json',{'initialInundation':True,'inheritedSubseaLandCells':int(bad.sum()),'inundationAreaKm2':float(bad.sum()*dx*dx/1e6),'protectedInundatedCells':int((bad&hard).sum()),'maximumCorrectionM':0,'volumeM3':0,'reason':'User-authorised coastal change in existing unprotected lows; retained numeric bed, ocean datum zero','notIncludedInErosionOrDeposition':True});np.save(out/'datum-reconstruction.npy',np.zeros_like(z))
    # Water elevations and negative coastal bed are distinct. Existing lakes
    # remain scene constraints until a dedicated lake-basin reconstruction.
    for name,a in {'baseline':base,'revised':z,'kind':kind,'baseline-kind':kind,'protected':hard,'hard-protected':hard,'allow':allow,'evolution-allow':allow}.items():np.save(root/(name+'.npy'),a)
    for name,a in {'base-v10':base,'initial':z,'height-0':z,'kind':kind,'hard-protected':hard,'allow':allow,'evolution-allow':allow,'cap-thickness':load_saved(region,seed,g,'cap-thickness'),'soil-initial':load_saved(region,seed,g,'soil'),'uplift-rate':np.zeros_like(z)}.items():np.save(out/(name+'.npy'),a)
    T.savejson(out/'landforms.json',read(BASE/region/str(seed)/'landforms.json'));T.savejson(out/'faults.json',read(BASE/region/str(seed)/'faults.json'))
    T.savejson(out/'construction.json',{'source':str(BASE/region/str(seed)/'height.npy'),'baseSha256':T.sha(BASE/region/str(seed)/'height.npy'),'repeatedV7Uplift':False,'resolvedIds':read(BASE/region/str(seed)/'construction.json')['resolvedIds'],'clock':'0 starts at saved v10 final, with authorised river/coastal datum integration'})
    return g,z,kind,allow

def land_mask(z,kind):
    # A negative elevation in a closed inland basin is not an ocean inlet.
    low,n=T.label(z<=0);ocean_ids=np.unique(low[(kind==0)&(z<=0)]);ocean_ids=ocean_ids[ocean_ids>0];sea=np.isin(low,ocean_ids)
    return (~sea)&(kind!=80)

def coast_report(g,initial_kind,z,region,initial_height=None,hard=None):
    dx=g['stepM'];old=(initial_kind>=30)&(initial_kind!=80);new=land_mask(z,initial_kind);changed=old^new;den=max(1,int(old.sum()));gained=int((new&~old).sum());lost=int((old&~new).sum());dist=np.where(old,T.edt(old)*dx,T.edt(~old)*dx);maxshift=float(dist[changed].max(initial=0));report={'gainedAreaKm2':gained*dx*dx/1e6,'lostAreaKm2':lost*dx*dx/1e6,'grossAreaFraction':(gained+lost)/den,'netAreaFraction':abs(gained-lost)/den,'maximumShiftM':maxshift,'gridStepM':dx,'islands':[]}
    reference=old if initial_height is None else land_mask(initial_height,initial_kind);inherited=old&~reference;post=reference^new;post_distance=np.where(reference,T.edt(reference)*dx,T.edt(~reference)*dx);post_shift=float(post_distance[post].max(initial=0));protected_change=0 if hard is None else int((changed&hard&old).sum());report.update(inheritedLowlandInundationKm2=float(inherited.sum()*dx*dx/1e6),maximumPostInitialShiftM=post_shift,postShiftReference='physical shoreline after authorised inherited lowland inundation',protectedInundatedCells=protected_change,coarseBoundaryUncertaintyM=dx*np.sqrt(2))
    # A 16 km screening raster cannot certify a 20 km vector displacement. Keep
    # the unresolved upper interval explicit; 2 km coast windows check it next.
    passed=post_shift<=CFG['coast']['mainlandMaxShiftM']+dx*np.sqrt(2) and report['grossAreaFraction']<=CFG['coast']['mainlandGrossAreaFraction'] and protected_change==0
    if region=='keld':
        main=[f for f in T.D['land'] if f['id'].startswith('keld-') and f['id'][5:].isdigit()];labels=np.zeros(z.shape,int)
        for k,f in enumerate(main):labels[T.raster([f['geometry']],g)]=k+1
        _,nearest=T.edt(labels==0,return_indices=True);nearestlabel=labels[tuple(nearest)]
        passed=report['netAreaFraction']<=CFG['coast']['archipelagoNetAreaFraction'];oldcom,nold=T.label(old);newcom,nnew=T.label(new)
        for k,f in enumerate(main):
            footprint=nearestlabel==k+1;ao=int((old&footprint).sum());an=int((new&footprint).sum());fraction=(an-ao)/max(1,ao);report['islands'].append({'id':f['id'],'areaIncludesNearestIslets':True,'baseAreaKm2':ao*dx*dx/1e6,'finalAreaKm2':an*dx*dx/1e6,'areaFraction':fraction});passed&=abs(fraction)<=CFG['coast']['islandAreaFraction']
        relation=[]
        for i in range(len(main)):
            for j in range(i+1,len(main)):
                a=oldcom[labels==i+1];b=oldcom[labels==j+1];c=newcom[labels==i+1];d=newcom[labels==j+1];same_old=bool(set(a[a>0])&set(b[b>0]));same_new=bool(set(c[c>0])&set(d[d>0]));
                if same_old!=same_new:relation.append([main[i]['id'],main[j]['id']])
        report['changedMainIslandConnections']=relation;passed&=not relation
    report['passed']=bool(passed);return report

def retention(out,g,catalog):
    z0=np.load(out/'initial.npy');z=np.load(out/'height.npy');er=np.load(out/'erosion.npy');dep=np.load(out/'deposition.npy');rows=[];dx=g['stepM']
    for f in catalog:
        if min(f['lengthM'],f['widthM'])*2<4*dx:continue
        cx,cy=f['xy'];r=int(round((g['ymax']-cy)/dx));c=int(round((cx-g['xmin'])/dx));rad=max(2,round(min(f['lengthM'],f['widthM'])/dx));s=(slice(max(0,r-rad),min(g['height'],r+rad+1)),slice(max(0,c-rad),min(g['width'],c+rad+1)))
        a=z0[s];b=z[s]
        if a.size<9:continue
        before=float(np.percentile(a,95)-np.percentile(a,10));after=float(np.percentile(b,95)-np.percentile(b,10));ratio=after/max(before,1);transformed=float(np.percentile(er[s]+dep[s],95))>max(20,before*.15);state='transformed' if transformed else 'retained' if ratio>=.3 else 'planed-away';rows.append({'id':f['id'],'initialProminenceM':before,'finalProminenceM':after,'ratio':ratio,'state':state})
    lost=sum(r['state']=='planed-away' for r in rows);report={'resolved':len(rows),'unresolvedNotCounted':len(catalog)-len(rows),'lost':lost,'lostFraction':lost/max(1,len(rows)),'renewalNeeded':lost/max(1,len(rows))>CFG['retention']['lostFractionTrigger'],'features':rows};T.savejson(out/'retention.json',report);return report

def run_region(work,region,seed,mode='episodic',step=16000,end=2000000,mask=None,dt=None,event_density=1,coast_strength=1):
    setup(work,mask);g,z,kind,allow=prepare(work,region,seed,step);out=work/region/str(seed);events=event_catalog(region,seed,g,z,allow,event_density) if mode=='episodic' else [];T.savejson(out/'events.json',events)
    solve(out,g,z,kind,allow,events,end,dt or min(10000,step*.625),coast_strength=coast_strength)
    report=coast_report(g,kind,np.load(out/'height.npy'),region,z,np.load(out/'hard-protected.npy'));T.savejson(out/'coast.json',report)
    if not report['passed']:
        fail=out/f'failed-coast-{coast_strength:g}';fail.mkdir(exist_ok=True)
        for n in ['height.npy','simulation.json','coast.json']:shutil.copy2(out/n,fail/n)
        if mode=='erosion-only' or coast_strength<=1/32:raise RuntimeError('Coast budget failed; adjust the affected source/process, not the acceptance limit')
        # Rerun the physical episode with a lower source amplitude. Never clip
        # the final coastline or silently restore gained/lost land afterwards.
        return run_region(work,region,seed,mode,step,end,mask,dt,event_density,coast_strength*.5)
    r=retention(out,g,read(out/'landforms.json'));triggered=r['renewalNeeded'];batches=0;budget=float(sum(abs(e['reliefM'])*e['lengthM']*e['widthM'] for e in events));original_count=len(events)
    while mode=='episodic' and r['renewalNeeded'] and batches<2:
        batches+=1;extra=event_catalog(region,seed,g,z,allow,event_density,salt=batches*7919);extra=[{**e,'id':e['id']+f'-renewal-{batches}'} for e in extra[:max(1,round(original_count*.25))]];events+=extra;new_budget=sum(abs(e['reliefM'])*e['lengthM']*e['widthM'] for e in events)
        for e in events:e['reliefM']*=budget/max(new_budget,1)
        T.savejson(out/f'retention-before-renewal-{batches}.json',r);T.savejson(out/'events.json',events);solve(out,g,z.copy(),kind,allow,events,end,dt or min(10000,step*.625),coast_strength=coast_strength);r=retention(out,g,read(out/'landforms.json'));report=coast_report(g,kind,np.load(out/'height.npy'),region,z,np.load(work/region/'hard-protected.npy'));T.savejson(out/'coast.json',report)
        if not report['passed']:raise RuntimeError('Renewal violates coast budget; failed candidate retained')
    T.savejson(out/'renewal-decision.json',{'triggered':triggered,'batches':batches,'batchFraction':.25,'maximumBatches':2,'activityBudgetRedistributed':True,'nominalDisplacementBudgetM3':budget,'status':'not needed' if not triggered else 'retained after bounded reseeding' if not r['renewalNeeded'] else 'failed retention after two batches; report retained'})
    T.log(f'CYCLE {mode} {region} {seed}: erosion {float(np.load(out/"erosion.npy").max()):.1f} m');return out

def solve(out,g,z,kind,allow,events,end,dtmax,coast_strength=1,forcing=None,extra_discharge=None):
    """Conservative coarse screening, including sediment landing on shelf bed."""
    dx=g['stepM'];area=dx*dx;initial=z.copy();soil=np.maximum(0,np.load(out/'soil-initial.npy').astype(float));soil[allow==0]=0;soil0=soil.copy();controls=T.weights(g['region'],g);allow=allow.copy()*(1-controls['protection']);cap=np.load(out/'cap-thickness.npy');bed0=z-soil;now=0;ledger=[];tot={k:np.zeros(z.shape) for k in ['erosion','deposition','tectonic-uplift','slope-transport','weathering','sand']};sed=np.zeros(z.size);times=sorted(set([v for v in CFG['timesYears'] if v<=end]+[end]));np.save(out/'initial.npy',initial)
    soil*=controls['soil'];controls['_coastDistance']=T.edt(land_mask(initial,kind))*dx
    frame=np.zeros(z.shape,bool);frame[[0,-1]]=True;frame[:,[0,-1]]=True;external_q=np.zeros_like(z);external_s=np.zeros_like(z)
    def route():
        land=land_mask(z,kind);land[[0,-1]]=False;land[:,[0,-1]]=False;cl=T.atmosphere(z,g,np.where(land,70,0));fill,order,rec,slope=T.F.flood_route(z,land,dx);local=cl['runoff']*land;q=T.F.discharge(order,rec,local,area)
        if forcing is not None:q+=T.F.discharge(order,rec,external_q/area,area)
        if extra_discharge is not None:q+=extra_discharge(order,rec,now)
        return land,cl,fill,order,rec,slope,q
    def save(year):
        land,cl,fill,order,rec,sl,q=route();arrays={'height':z,'discharge':q.reshape(z.shape),'receiver':rec.reshape(z.shape),'sediment-flux':sed.reshape(z.shape),'kind':np.where(land,70,np.where(kind==80,80,0))}
        arrays['kind'][kind==200]=200;arrays.update(soil=soil,sand=soil*(1-cl['humidity']))
        for key,a in arrays.items():np.save(out/f'{key}-{year}.npy',a.astype('int32') if key=='receiver' else a.astype('float32'))
    save(0)
    for target in times[1:]:
        while now<target:
            dt=min(dtmax,target-now);before=z.copy();soil_before=soil.copy();boundary_change=0.
            if forcing is not None:
                bound,external_q,external_s=forcing.at(now+dt);boundary_change=float((bound[frame]-z[frame]).sum()*area);z[frame]=bound[frame]
            u=event_field(g,events,allow,controls,now,now+dt,coast_strength);z+=u;tot['tectonic-uplift']+=u;land,cl,filled,order,rec,slope,q=route();exposure=np.maximum(0,initial+tot['tectonic-uplift']-z);hard=((exposure<cap)|(np.mod(np.maximum(0,exposure-cap),440)>260)).astype(float)
            weather=.00004*dt*np.exp(-soil/.7)*(1-hard*.7)*allow*controls['weathering'];weather[~land]=0;soil+=weather;tot['weathering']+=weather
            physical_width=np.clip(650*(np.maximum(q.reshape(z.shape)/31557600,1)/2500)**.42,10,2800);width_fraction=np.minimum(1,physical_width/dx)
            z,soil,er,de,export,sed=T.fluvial(z,soil,order,rec,q,slope,filled,allow*land,hard,dx,dt,external_s.ravel()*land.ravel(),controls['water']*width_fraction,controls['rock-strength'],T.C['planet']['gravityMs2'],T.C['lithology']['hardK'],T.C['lithology']['softK'],True)
            marine_in=external_s*(~land)*dt;marine_store=marine_in*allow;z+=marine_store/area;soil+=marine_store/area;de+=marine_store/area;export+=float((marine_in-marine_store).sum())
            # Sediment exits the land receiver network at actual shelf cells.
            # Deposition is an un-clipped bed increment. Ocean fraction not
            # retained on the shelf goes to the explicitly logged deep sink.
            outlets=order[(rec[order]>=0)&~land.ravel()[np.maximum(rec[order],0)]];mouth_volume=sed[outlets]*dt;mouths=rec[outlets];ocean_deposit=np.zeros(z.size)
            if len(mouths):
                depth=np.maximum(0,-z.ravel()[mouths]);retained=mouth_volume*np.exp(-depth/300)*np.clip(allow.ravel()[mouths],0,1);np.add.at(ocean_deposit,mouths,retained/area)
                # Conservative lateral spreading mimics unresolved mouth fans.
                ocean_deposit=ocean_deposit.reshape(z.shape);wet=(~land)&(allow>0);spread=gaussian_filter(ocean_deposit,1)*wet;mass=float(ocean_deposit.sum());spread*=mass/max(float(spread.sum()),1e-30);z+=spread;soil+=spread;de+=spread;export-=mass*area
            # Paired transport moves soil first and exposes rock only where the
            # material supply is exhausted. No negative soil clipping creates it.
            pre=z.copy();z,soil,sl=conservative_slope(z,soil,allow,dx,dt,hard,1-cl['humidity'],controls);tot['slope-transport']+=sl;tot['erosion']+=er;tot['deposition']+=de
            supplied_s=float(external_s.sum()*dt);residual=float(np.sum(z-before-u)*area+export-boundary_change-supplied_s);scale=max(1,float(np.sum(abs(z-before))*area),abs(export),float(np.sum(abs(u))*area),supplied_s,abs(boundary_change));receiver=rec[order];outlets0=(receiver<0)|~land.ravel()[np.maximum(receiver,0)];waterout=float(q[order[outlets0]].sum()+external_q[~land].sum());waterin=float((cl['runoff']*land).sum()*area+external_q.sum());bed=z-soil;rock_weather_transfer=float(weather.sum()*area)
            ledger.append({'year':now+dt,'dtYears':dt,'upliftM3':float(u.sum()*area),'fluvialErosionM3':float(er.sum()*area),'depositedM3':float(de.sum()*area),'deepOceanExportM3':float(export),'externalSedimentM3':supplied_s,'boundaryExchangeM3':boundary_change,'weatheredRockToSoilM3':rock_weather_transfer,'volumeResidualM3':residual,'relativeVolumeError':abs(residual)/scale,'waterRelativeError':abs(waterout-waterin)/max(1,waterin),'minimumSoilM':float(soil.min()),'bedSoilIdentityErrorM':float(abs((bed+soil)-z).max())});now+=dt
        save(target);T.savejson(out/'progress.json',{'year':now,'steps':len(ledger),'lastStep':ledger[-1]});T.log(f'{g["region"]} {out.name} {now} yr')
    land,cl,filled,order,rec,slope,q=route();finalkind=np.where(land,70,np.where(kind==80,80,0));finalkind[kind==200]=200
    tot['sand']=soil*(1-cl['humidity']);arrays={'height':z,'soil':soil,'bedrock':z-soil,'kind':finalkind,'discharge':q.reshape(z.shape),'receiver':rec.reshape(z.shape),'sediment-flux':sed.reshape(z.shape),'pond-depth':np.maximum(filled-z,0),'cap-thickness':cap,**tot,**cl}
    for k,a in arrays.items():np.save(out/(k+'.npy'),a.astype('int32') if k=='receiver' else a.astype('float32'))
    fixed=(allow==0)&(~frame if forcing is not None else True);report={'solver':'conservative coarse finite volume; explicit subgrid river width and marine sink','effectiveYears':end,'stepYears':dtmax,'gridStepM':dx,'protectedMaxDeltaM':float(abs(z[fixed]-initial[fixed]).max(initial=0)),'maxVolumeRelativeError':max(v['relativeVolumeError'] for v in ledger),'maxWaterRelativeError':max(v['waterRelativeError'] for v in ledger),'minimumSoilM':float(soil.min()),'gravityMs2':T.C['planet']['gravityMs2'],'coastEventStrength':coast_strength,'history':ledger,'climateSource':CFG['screening']['climate'],'physicalRiverWidth':'10–2800 m discharge-dependent screening; Ishkar ordinary 650 m minimum in regional river coupling; width is independent of grid step','subgridInterpretation':'coarse cut is cell-average removal, not a claim of a grid-wide canyon','routesDeferred':True}
    report['passed']=report['protectedMaxDeltaM']<=1e-6 and report['maxVolumeRelativeError']<1e-7 and report['maxWaterRelativeError']<1e-8 and report['minimumSoilM']>=0;T.savejson(out/'simulation.json',report)
    if not report['passed']:raise RuntimeError('Cycle conservation / core constraint failed '+str(out))

def conservative_slope(z,soil,allow,dx,dt,hard,dry,controls):
    original=z.copy();z=z.copy();soil=soil.copy()
    # Sequential pair exchanges avoid several links spending the same sediment.
    for axis in [0,1]:
        for parity in [0,1]:
            a=[slice(None),slice(None)];b=a.copy();a[axis]=slice(parity,z.shape[axis]-1,2);b[axis]=slice(parity+1,z.shape[axis],2);a=tuple(a);b=tuple(b)
            diff=z[a]-z[b];mask=np.minimum(allow[a],allow[b]);s=diff/dx;strength=np.maximum(.2,np.minimum(controls['rock-strength'][a],controls['rock-strength'][b]));critical=.65+(2e5+hard[a]*8e5)*strength/(2950*T.C['planet']['gravityMs2']*np.maximum(abs(diff),50));move=(diff*np.minimum(.04,.025*dt/dx**2*(1+(s/.7)**2))+np.sign(diff)*np.minimum(np.maximum(0,abs(s)-critical)*dt*2e-4,5))*mask*np.minimum(controls['planation'][a],controls['planation'][b]);amount=np.minimum(abs(move),abs(diff)*.2);forward=move>=0;donor_soil=np.where(forward,soil[a],soil[b]);mobile=np.minimum(amount,np.maximum(0,donor_soil));signed=np.where(forward,amount,-amount);soil_move=np.where(forward,mobile,-mobile);z[a]-=signed;z[b]+=signed;soil[a]-=soil_move;soil[b]+=soil_move
            # Exposed rock transported downslope becomes debris at the receiver.
            debris=amount-mobile;soil[b]+=np.where(forward,debris,0);soil[a]+=np.where(forward,0,debris)
            wind=1 if axis==0 else -1;donor=soil[a] if wind>0 else soil[b];sand=np.minimum(donor*.03,dt*1e-5)*np.minimum(dry[a],dry[b])*mask*np.minimum(controls['aeolian'][a],controls['aeolian'][b]);sand*=wind;z[a]-=sand;z[b]+=sand;soil[a]-=sand;soil[b]+=sand
    return z,soil,z-original

def record(work):
    out=work/'source-used';out.mkdir(parents=True,exist_ok=True)
    for p in (T.ROOT/'src').glob('tectonics-*'):
        if p.suffix in ['.py','.cjs']:shutil.copy2(p,out/p.name)
    shutil.copy2(T.ROOT/'data/tectonics-erosion.json',work/'erosion-config.json');T.savejson(work/'lineage.json',{'baseStudy':str(BASE),'frozenManifestSha256':T.sha(ARCHIVE/'freeze.json'),'createdUnix':time.time(),'routesDeferred':True,'formalMapChanged':False,'climate':CFG['screening']['climate']});T.savejson(work/'riverbend.json',bank_site())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=DEFAULT);ap.add_argument('--base-study',type=pathlib.Path);ap.add_argument('--region',default='all');ap.add_argument('--seed',type=int);ap.add_argument('--mode',choices=['erosion-only','episodic','both'],default='both');ap.add_argument('--grid-m',type=int,default=16000);ap.add_argument('--end',type=int,default=2000000);ap.add_argument('--dt',type=int);ap.add_argument('--mask',type=pathlib.Path);ap.add_argument('--event-density',type=float,default=1);ap.add_argument('--freeze-only',action='store_true');a=ap.parse_args()
    if a.base_study and a.base_study.resolve() not in [SOURCE.resolve(),BASE.resolve()]:raise ValueError('Only the reviewed v10 base is registered; freeze a new base explicitly first')
    freeze()
    if a.freeze_only:return
    for mode in CFG['modes'] if a.mode=='both' else [a.mode]:
        work=a.work/mode;setup(work,a.mask);record(work)
        for region in REGIONS if a.region=='all' else [a.region]:
            for seed in [a.seed] if a.seed else CFG['seeds']:run_region(work,region,seed,mode,a.grid_m,a.end,a.mask,a.dt,a.event_density);gc.collect()
if __name__=='__main__':main()
