"""Numerical/physical regression tests and completion checks, without mutations."""
import pathlib,sys,importlib,json,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');np=T.np
def unit_cases():
    n=80;dx=1000.;yy,xx=np.mgrid[:n,:n];z=(500+(n-1-yy)*15+abs(xx-n/2)*2).astype(float);land=np.ones(z.shape,bool);land[[0,-1],:]=False;land[:,[0,-1]]=False;allow=land.astype(float);soil=np.full(z.shape,.6);filled,order,rec,slope=T.F.flood_route(z,land,dx);q=T.F.discharge(order,rec,np.ones(z.shape)*land,dx*dx)
    cases={}
    for name,rock,water in [('soft',0,1),('hard',1,1),('water-off',0,0),('strong-water',0,2)]:
        result=T.fluvial(z,soil,order,rec,q,slope,filled,allow,np.full(z.shape,rock),dx,10000,np.zeros(z.size),np.full(z.shape,water));after,hs,er,de,export,flux=result;balance=float((after.sum()-z.sum())*dx*dx+export)
        assert abs(balance)<max(1,export)*1e-8,(name,balance)
        cases[name]={'erosionM3':float(er.sum()*dx*dx),'balanceM3':balance}
    assert cases['water-off']['erosionM3']==0;assert cases['hard']['erosionM3']<cases['soft']['erosionM3']<cases['strong-water']['erosionM3']
    after,hs,dz=T.paired_flux(z,soil,allow,dx,10000,np.ones(z.shape),np.ones(z.shape),(.3,-.8),np.zeros(z.shape),np.zeros(z.shape));assert np.array_equal(after,z),'Zero planation and aeolian masks must turn off those operators'
    after,hs,dz=T.paired_flux(z,soil,allow,dx,10000,np.ones(z.shape),np.ones(z.shape),(.3,-.8));assert abs(float(dz.sum()))<1e-7,'Pair transport mass conservation'
    from landlab import RasterModelGrid
    R=importlib.import_module('tectonics-refine');grid=RasterModelGrid((n,n),xy_spacing=dx);v=grid.add_field('topographic__elevation',z.ravel().copy(),at='node');R.weighted_diffusion(grid,v,np.zeros(n*n),10000,dx);assert np.array_equal(v,z.ravel()),'Fine-grid planation-off mask failed'
    return cases
def route_audit():
    result=[];g=json.loads((T.WORK/'aethelgard/grid.json').read_text(encoding='utf8'));p=T.Proj(g['projection']);z=np.load(T.WORK/'aethelgard/5210914/height.npy');old=np.load(T.WORK/'aethelgard/baseline.npy')
    lineage=T.WORK/'aethelgard/5210914/construction.json'
    if lineage.exists():
        source=json.loads(lineage.read_text(encoding='utf8')).get('source',{}).get('file')
        if source and pathlib.Path(source).exists():
            source=pathlib.Path(source);old=T.sample(np.load(source),json.loads((source.parent.parent/'grid.json').read_text(encoding='utf8')),g)
    for route in T.D['routes']:
        if route['id'] not in ['home','iris','east','amber','orun-route','north','skyleaf-route','scar','RB-SA','MI-CA']:continue
        coords=route['geometry']['coordinates'];samples=[]
        for a,b in zip(coords[:-1],coords[1:]):
            x,y=p(*a);xx,yy=p(*b);count=max(2,int(np.hypot(xx-x,yy-y)/10000));samples.extend(zip(np.linspace(x,xx,count),np.linspace(y,yy,count)))
        xy=np.array(samples);ii=(xy[:,0]-g['xmin'])/g['stepM'];jj=(g['ymax']-xy[:,1])/g['stepM'];a=T.map_coordinates(old,[jj,ii],order=1);b=T.map_coordinates(z,[jj,ii],order=1);newly=(b+200>3000)&(a+200<=3000)
        result.append({'id':route['id'],'name':route['properties']['name'],'originalMaxGroundM':float(a.max()),'candidateMaxGroundM':float(b.max()),'newSamplesOver3000With200mClearance':int(newly.sum()),'approxNewlyAffectedKm':int(newly.sum()*10),'status':'requires route-scale review; no route or manuscript changed' if newly.any() else 'no new sampled 3 km ceiling conflict'})
    return result
def verify(require_complete=True):
    report={'unitCases':unit_cases(),'formalInputs':[],'runs':[],'refinements':[],'issues':[]};snap=json.loads((T.BASE_WORK/'source-snapshot.json').read_text(encoding='utf8'))
    for f,h in snap['hashes'].items():
        if f=='foundation/manifest.json':continue
        assert T.sha(T.ROOT/f)==h,'Formal source changed '+f;report['formalInputs'].append(f)
    for region in T.C['regions']:
        for seed in T.C['seeds']:
            folder=T.WORK/region/str(seed);f=folder/'simulation.json'
            if not f.exists():report['issues'].append(f'missing run {region}/{seed}');continue
            s=json.loads(f.read_text(encoding='utf8'));assert s['protectedMaxDeltaM']<1e-6;assert s['maxWaterRelativeError']<1e-8;assert s['maxVolumeRelativeError']<1e-7
            report['runs'].append({'region':region,'seed':seed,**{k:v for k,v in s.items() if k!='history'}})
    for c in T.C['refinements']:
        folder=T.WORK/'refined'/c['id'];f=folder/'simulation.json'
        if not f.exists():report['issues'].append('missing refinement '+c['id']);continue
        s=json.loads(f.read_text(encoding='utf8'));parent=T.WORK/c['parent']/'5210914' if c['parent'] in T.C['regions'] else T.WORK/'refined'/c['parent'];lineage=json.loads((folder/'parent-boundary.json').read_text(encoding='utf8'));fresh=lineage['parentHeightSha256']==T.sha(parent/'height.npy');report['refinements'].append({'id':c['id'],'passed':s.get('passed',False),'parentCurrent':fresh,'protectedMaxDeltaM':s['protectedMaxDeltaM'],'boundaryMaxDeltaM':s['parentBoundaryMaxDeltaM'],'volumeError':s['maxVolumeRelativeError']})
        if not s.get('passed') or not fresh:report['issues'].append('unverified or stale refinement '+c['id'])
    report['routes']=route_audit();report['passed']=not report['issues'];T.savejson(T.WORK/'verification.json',report);print(json.dumps({'passed':report['passed'],'runs':len(report['runs']),'refinements':len(report['refinements']),'issues':report['issues'],'routeConflicts':sum(v['newSamplesOver3000With200mClearance']>0 for v in report['routes'])}))
    if require_complete:assert report['passed'],report['issues']
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');ap.add_argument('--work',type=pathlib.Path,default=T.WORK);a=ap.parse_args();T.WORK=a.work
    if (a.work/'run-config.json').exists():T.C=json.loads((a.work/'run-config.json').read_text(encoding='utf8'))
    verify(not a.partial)
