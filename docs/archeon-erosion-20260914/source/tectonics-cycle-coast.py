"""2 km coastal screening with inherited discharge, sediment and boundary bed."""
import pathlib,sys,importlib,json,argparse,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;R=importlib.import_module('tectonics-refine')

def run(work,region,mode='episodic',seed=5210914,step=2000,end=2000000):
    target=work/mode;X.setup(target);pdir=target/region/str(seed);pg=X.read(target/region/'grid.json');initial=np.load(pdir/'initial.npy');z=np.load(pdir/'height.npy');kind0=np.load(pdir/'kind-0.npy');changed=(X.land_mask(initial,kind0)!=X.land_mask(z,kind0));delta=abs(z-initial)*changed
    if not changed.any():delta=np.load(pdir/'deposition.npy')*(T.edt(kind0>=30)*pg['stepM']<30000)
    r,c=np.unravel_index(np.argmax(delta),delta.shape);cx=pg['xmin']+c*pg['stepM'];cy=pg['ymax']-r*pg['stepM'];width=320000;g={**pg,'id':region+'-coast-2km','width':round(width/step)+1,'height':round(width/step)+1,'stepM':step,'xmin':cx-width/2,'ymax':cy+width/2};out=target/'refined'/g['id'];out.mkdir(parents=True,exist_ok=True);T.savejson(out/'grid.json',g)
    base=T.sample(initial,pg,g).astype(float);kind=T.sample(kind0,pg,g,0);hard=T.sample(np.load(pdir/'hard-protected.npy'),pg,g,0)>0;allow=T.sample(np.load(pdir/'allow.npy'),pg,g).astype(float);n=g['height'];frame=np.minimum.reduce(np.broadcast_arrays(np.arange(n)[:,None],n-1-np.arange(n)[:,None],np.arange(n)[None,:],n-1-np.arange(n)[None,:]));allow*=T.ease(frame/8);allow[hard]=0
    for k,a in {'initial':base,'height-0':base,'kind':kind,'kind-0':kind,'soil-initial':T.sample(np.load(pdir/'soil-initial.npy'),pg,g),'cap-thickness':T.sample(np.load(pdir/'cap-thickness.npy'),pg,g),'protected':hard}.items():np.save(out/(k+'.npy'),a)
    forcing=R.ParentForcing(region,pdir,g,pg);events=X.read(pdir/'events.json');strength=X.read(pdir/'simulation.json')['coastEventStrength'];X.solve(out,g,base,kind,allow,events,end,5000,coast_strength=strength,forcing=forcing)
    report=X.read(out/'simulation.json');report.update(parentBoundaryMaxDeltaM=float(abs(np.load(out/'height.npy')[[0,-1],:]-T.sample(np.load(pdir/f'height-{end}.npy'),pg,g)[[0,-1],:]).max()),exportDestination='Downstream parent boundary plus marine export, recorded as one reservoir in this screening window',coastSource='Bilinearly inherited v10/cycle bed; 2 km processes do not imply new independent bathymetric measurements');T.savejson(out/'simulation.json',report)
    T.savejson(out/'parent-boundary.json',{'parent':region,'parentHeightSha256':T.sha(pdir/'height.npy'),'sourceHashes':forcing.hashes,'sourceSnapshotsYears':forcing.years});cr=X.coast_report(g,kind,np.load(out/'height.npy'),region,base,hard);T.savejson(out/'coast.json',cr)
    spec={'id':g['id'],'parent':region,'mode':mode,'center':list(T.Proj(pg['projection'])(cx,cy,inverse=True)),'widthKm':320,'stepM':step,'title':T.C['regions'][region]['title'].split(' · ')[0]+' · 海湾与河口 · 2 km','coastalTrial':True,'seed':seed};T.savejson(out/'refinement-config.json',spec);planfile=work/'detail-plan.json';plan=X.read(planfile) if planfile.exists() else [];T.savejson(planfile,[s for s in plan if (s['id'],s['mode'])!=(spec['id'],mode)]+[spec]);gc.collect();return cr

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=X.DEFAULT);ap.add_argument('--region',default='all');ap.add_argument('--mode',choices=['episodic','erosion-only'],default='episodic');a=ap.parse_args()
    for region in X.REGIONS if a.region=='all' else [a.region]:run(a.work,region,a.mode)
