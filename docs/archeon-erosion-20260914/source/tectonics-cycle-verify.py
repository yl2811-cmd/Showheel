"""Physical accounting, fixed-base comparisons and scoped convergence tests."""
import pathlib,sys,importlib,json,argparse,shutil,hashlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;R=importlib.import_module('tectonics-refine');D=importlib.import_module('tectonics-cycle-detail')

def terrain_metrics(folder,g):
    z=np.load(folder/'height.npy');a=np.load(folder/'initial.npy');kind=np.load(folder/'kind.npy');land=(kind>=30)&(kind!=80)&(kind!=200);dx=g['stepM'];er=np.load(folder/'erosion.npy');dep=np.load(folder/'deposition.npy');gy,gx=np.gradient(z,dx);slope=np.hypot(gx,gy);window=max(3,round(8000/dx));relief=X.maximum_filter(z,size=window)-X.minimum_filter(z,size=window);mesa=(slope<.04)&(relief>100)&land&(z>X.minimum_filter(z,size=window)+100);labels,n=T.label(mesa);areas=np.bincount(labels.ravel())*dx*dx/1e6;mesa_count=int(np.count_nonzero(areas[1:]>=max(1,4*dx*dx/1e6)))
    return {'maximumCumulativeIncisionM':float(er[land].max(initial=0)),'maximumDepositionM':float(dep[land].max(initial=0)),'meanAbsoluteChangeM':float(abs(z[land]-a[land]).mean()) if land.any() else 0,'maximumResolvedLocalReliefM':float(relief[land].max(initial=0)),'localReliefWindowM':window*dx,'maximumResolvedSlope':float(slope[land].max(initial=0)),'flatElevatedRemnantCandidates':mesa_count,'remnantCriterion':'slope<0.04, relief>100m in target8km window (minimum3cells; actual window recorded), at least100m above local floor; connected area>=4cells and>=1km2; not a geological classification','subgridFeaturesNotCounted':True}

def operator_checks():
    dx=100.;n=12;z=np.indices((n,n))[0].astype(float)[::-1]*2+10;soil=np.ones_like(z)*.5;land=np.ones(z.shape,bool);land[[0,-1]]=False;land[:,[0,-1]]=False;filled,order,rec,slope=T.F.flood_route(z,land,dx);q=T.F.discharge(order,rec,np.full_like(z,.4)*land,dx*dx);external=np.zeros(z.size);external[n+5]=1000
    zz,hh,er,de,export,sed=T.fluvial(z,soil,order,rec,q,slope,filled,land.astype(float),np.ones_like(z),dx,10,external,np.ones_like(z),None,9.610517,0,0,True);outlets=order[(rec[order]<0)|~land.ravel()[np.maximum(rec[order],0)]];balance=float((zz-z).sum()*dx*dx+export-external.sum()*10);flux=float(sed[outlets].sum()*10-export);assert abs(balance)<1e-6 and abs(flux)<1e-6,'Outgoing sediment must exclude material already deposited'
    controls={k:np.ones_like(z) for k in ['rock-strength','planation','aeolian']};zz,hh,change=X.conservative_slope(z,soil,land.astype(float),dx,500,np.ones_like(z),np.ones_like(z),controls);assert abs(change.sum())<1e-8 and hh.min()>=0;assert np.array_equal(zz[~land],z[~land]);return {'sedimentVolumeResidualM3':balance,'outgoingFluxResidualM3':flux,'slopeMassResidualM3':float(change.sum()*dx*dx),'minimumSoilM':float(hh.min()),'fixedCellsExact':True,'passed':True}

def convergence(work,mask=None):
    records=[]
    for region in ['aethelgard','vorhan']:
        root=work/'episodic';X.setup(root,mask);source=root/region/'5210914';out=work/'verification-runs'/('half-step-'+region);out.mkdir(parents=True,exist_ok=True)
        for name in ['soil-initial.npy','cap-thickness.npy','initial.npy']:shutil.copy2(source/name,out/name)
        g=X.read(root/region/'grid.json');initial=np.load(source/'initial.npy');kind=np.load(source/'kind-0.npy');allow=np.load(source/'allow.npy');events=X.read(source/'events.json');report=X.read(source/'simulation.json');X.solve(out,g,initial.copy(),kind,allow,events,2000000,5000,coast_strength=report['coastEventStrength']);ref=np.load(source/'height.npy');z=np.load(out/'height.npy');free=allow>.01;delta=z[free]-ref[free];evolution=ref[free]-initial[free];rms=float(np.sqrt(np.mean(delta**2)));den=max(1,float(np.sqrt(np.mean(evolution**2))));row={'region':region,'coarseStepYears':10000,'fineStepYears':5000,'years':2000000,'rmsDifferenceM':rms,'relativeEvolutionRms':rms/den,'p99DifferenceM':float(np.percentile(abs(delta),99)),'maximumDifferenceM':float(abs(delta).max()),'passed':rms/den<.1};records.append(row);T.log('HALF STEP '+json.dumps(row));gc.collect()
    T.savejson(work/'timestep-convergence.json',records);return records

def inspect(work):
    X.setup(work/'episodic');rows=[];paired=[]
    for mode in X.CFG['modes']:
        for region in X.REGIONS:
            for seed in X.CFG['seeds']:
                folder=work/mode/region/str(seed);path=folder/'simulation.json'
                if not path.exists():continue
                r=X.read(path);c=X.read(folder/'coast.json');g=X.read(work/mode/region/'grid.json');metrics=terrain_metrics(folder,g);minimum_export=min(v['deepOceanExportM3'] for v in r['history']);finite=all(np.isfinite(np.load(folder/(f+'.npy'))).all() for f in ['height','erosion','deposition','soil']);rows.append({'region':region,'mode':mode,'seed':seed,'gridM':g['stepM'],'years':r['effectiveYears'],'protectionPassed':r['protectedMaxDeltaM']==0,'waterError':r['maxWaterRelativeError'],'solidError':r['maxVolumeRelativeError'],'coastPassed':c['passed'],'coast':c,'minimumOceanExportM3':minimum_export,'finite':bool(finite),'metrics':metrics,'passed':bool(r['passed'] and c['passed'] and minimum_export>=-1e-6 and finite)})
                T.savejson(folder/'terrain-metrics.json',metrics)
    for region in X.REGIONS:
        for seed in X.CFG['seeds']:
            paths=[work/mode/region/str(seed)/'initial.npy' for mode in X.CFG['modes']]
            if all(p.exists() for p in paths):paired.append({'region':region,'seed':seed,'sameInitialBase':T.sha(paths[0])==T.sha(paths[1])})
    fine=[]
    for mode in X.CFG['modes']:
        for p in (work/mode/'refined').glob('*/simulation.json'):
            folder=p.parent;r=X.read(p);g=X.read(folder/'grid.json');metrics=terrain_metrics(folder,g);T.savejson(folder/'terrain-metrics.json',metrics);fine.append({'id':folder.name,'mode':mode,'gridM':g['stepM'],'years':r['effectiveYears'],'passed':r['passed'],'protectedMaxDeltaM':r['protectedMaxDeltaM'],'waterError':r['maxWaterRelativeError'],'solidError':r['maxVolumeRelativeError'],'metrics':metrics,'upstream':X.read(folder/'parent-boundary.json') if (folder/'parent-boundary.json').exists() else None})
    summary={'coarse':rows,'details':fine,'pairedBases':paired,'operatorChecks':operator_checks(),'coarseComplete':len(rows)==24,'coarseAccountingPassed':all(r['passed'] for r in rows),'sameInitialBases':all(r['sameInitialBase'] for r in paired),'detailAccountingPassed':all(r['passed'] for r in fine),'routesDeferred':True,'fullIshkarHistorySpatialConvergence':False,'realClimateValidated':False,'wholeCoastVectorDisplacementCertified':False,'notes':['Coarse coastline displacement includes raster uncertainty; initial unprotected lowland inundation is separately authorised.','Subgrid DEM morphology is an initial prior, distinct from subsequently eroded terrain.','Historical whole-Ishkar formation still lacks full spatial convergence.','No real GCM, glaciers, vegetation or flight-route calculations are represented as completed.']}
    if (work/'timestep-convergence.json').exists():summary['timestepConvergence']=X.read(work/'timestep-convergence.json')
    summary['allScientificChecksPassed']=False;T.savejson(work/'verification.json',summary);T.log('CHECKED '+json.dumps({k:v for k,v in summary.items() if k in ['coarseComplete','coarseAccountingPassed','sameInitialBases','detailAccountingPassed']}));return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=X.DEFAULT);ap.add_argument('--convergence',action='store_true');ap.add_argument('--mask',type=pathlib.Path);a=ap.parse_args()
    if a.convergence:convergence(a.work,a.mask)
    inspect(a.work)
