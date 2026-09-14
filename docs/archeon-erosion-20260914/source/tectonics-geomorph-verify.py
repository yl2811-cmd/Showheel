"""Audit the active geomorphology candidate, including honest failed trials."""
import pathlib,sys,importlib,json,argparse,shutil
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('tectonics-continuation');T=C.T;np=T.np;V=importlib.import_module('tectonics-verify');E=importlib.import_module('tectonics-export')
from scipy.spatial import cKDTree

def coast_checks(work):
 root=work/'ishkar-coast';cases={p.name:(p,json.loads((p/'result.json').read_text(encoding='utf8'))) for p in root.iterdir() if p.is_dir() and (p/'result.json').exists()};pairs=[]
 def key(dx,dt,width):return f'antecedent-12000000-0.3-dx{dx}-dt{dt}-w{width}'
 checks=[('time',key(8000,25000,480000),key(8000,12500,480000)),('space',key(8000,12500,480000),key(4000,12500,480000)),('domain',key(4000,12500,480000),key(4000,12500,720000)),('space',key(4000,12500,480000),key(2000,6250,480000)),('time',key(2000,6250,480000),key(2000,3125,480000))]
 def points(folder):
  g=json.loads((folder/'grid.json').read_text(encoding='utf8'));p=T.Proj(g['projection']);line=json.loads((folder/'route.geojson').read_text(encoding='utf8'))['features'][0]['geometry']['coordinates'];return np.array([p(*v) for v in line])
 for test,a,b in checks:
  if a not in cases or b not in cases:pairs.append({'type':test,'caseA':a,'caseB':b,'passed':False,'reason':'required comparison missing'});continue
  pa,x=cases[a];pb,y=cases[b];xx,yy=points(pa),points(pb);ha=float(max(cKDTree(xx).query(yy)[0].max(),cKDTree(yy).query(xx)[0].max()));inc=abs(x['maximumPathErosionM']-y['maximumPathErosionM'])/max(1,y['maximumPathErosionM']);volume=abs(x['erodedRockM3']-y['erodedRockM3'])/max(1,y['erodedRockM3']);same=x['reachesActualCoast']==y['reachesActualCoast'] and x['crossesOrunTrace']==y['crossesOrunTrace']
  # D8 route location cannot be compared more tightly than its cell size.
  passed=same and x['conservationPassed'] and y['conservationPassed'] and inc<.1 and ha<=max(x['gridStepM'],y['gridStepM'])*3
  pairs.append({'type':test,'caseA':a,'caseB':b,'routeHausdorffM':ha,'maximumIncisionFraction':inc,'erodedVolumeFraction':volume,'coastalRoutingStable':same,'passed':bool(passed)})
 result={'comparisons':pairs,'routeAndIncisionStable':all(v['passed'] for v in pairs),'volumeConvergencePassed':all(v.get('erodedVolumeFraction',1)<.1 for v in pairs if v['type']!='domain'),'scope':'Coarse formation feasibility and route candidate under prescribed runoff; a grid-cell channel is not a resolved bank-width sediment prediction. No modern riverbed locking.','cases':[{k:v for k,v in d.items() if k not in ['historyLedger','pathRows','pathColumns']} for p,d in cases.values()]};T.savejson(root/'convergence.json',result);return result

def verify(work):
 C.open_work(work,work/'applied-masks');report={'version':'geomorph-v10','unitCases':V.unit_cases(),'runs':[],'refinements':[],'formalInputs':[],'issues':[],'deferred':['polar CI engineering','calibrated GCM','glacier flow','Year 521 vegetation']};snap=json.loads((T.BASE_WORK/'source-snapshot.json').read_text(encoding='utf8'))
 for name,h in snap['hashes'].items():
  if name=='foundation/manifest.json':continue
  ok=T.sha(T.ROOT/name)==h;report['formalInputs'].append({'path':name,'unchanged':ok})
  if not ok:report['issues'].append('formal input changed '+name)
 for region in T.C['regions']:
  g=json.loads((work/region/'grid.json').read_text(encoding='utf8'));protected=np.load(work/region/'protected.npy')>0
  for seed in C.CFG['seeds']:
   folder=work/region/str(seed);s=json.loads((folder/'simulation.json').read_text(encoding='utf8'));con=json.loads((folder/'construction.json').read_text(encoding='utf8'));z=np.load(folder/'height.npy');base,_=C.base_surface(region,seed,g);kind=np.load(folder/'kind.npy');delta=float(np.max(abs(z[protected]-base[protected]),initial=0));shore_change=0
   if (C.FROZEN/region/str(seed)/'kind.npy').exists():shore_change=int(np.count_nonzero(kind!=T.sample(np.load(C.FROZEN/region/str(seed)/'kind.npy'),json.loads((C.FROZEN/region/'grid.json').read_text(encoding='utf8')),g,0)))
   row={'region':region,'seed':seed,'protectedTotalDeltaM':delta,'shoreKindChangedCells':shore_change,'construction':con,'simulation':{k:v for k,v in s.items() if k!='history'},'stats':E.stats(z,base,kind,g['stepM'])};report['runs'].append(row)
   if not s['passed'] or delta>1e-6 or shore_change or not np.isfinite(z).all():report['issues'].append(f'failed terrain {region}/{seed}')
 plan=json.loads((work/'detail-plan.json').read_text(encoding='utf8'))
 for c in plan:
  folder=work/'refined'/c['id'];s=json.loads((folder/'simulation.json').read_text(encoding='utf8'));lineage=json.loads((folder/'parent-boundary.json').read_text(encoding='utf8'));parent=work/c['parent']/'5210914' if c['parent'] in T.C['regions'] else work/'refined'/c['parent'];fresh=lineage['parentHeightSha256']==T.sha(parent/'height.npy');report['refinements'].append({'id':c['id'],'stepM':c['stepM'],'effectiveYears':s['effectiveYears'],'passed':s['passed'],'parentCurrent':fresh,'protectedMaxDeltaM':s['protectedMaxDeltaM'],'boundaryMaxDeltaM':s['parentBoundaryMaxDeltaM'],'waterError':s['maxWaterRelativeError'],'solidError':s['maxVolumeRelativeError']})
  if not fresh or not s['passed']:report['issues'].append('stale or failed detail '+c['id'])
 report['routes']=V.route_audit();report['river']=coast_checks(work)
 temporal=work/'timestep-convergence.json';report['timestepConvergence']=json.loads(temporal.read_text(encoding='utf8')) if temporal.exists() else {'passed':False,'reason':'missing'}
 if not report['timestepConvergence']['passed']:report['issues'].append('coarse timestep convergence incomplete')
 report['far5']=[]
 for seed in C.CFG['seeds']:
  folder=work/'global'/str(seed);frozen=C.FROZEN/'global'/str(seed)
  if folder.exists() and frozen.exists():
   a=np.load(folder/'height.npy');b=np.load(frozen/'height.npy');mask=np.load(frozen/'kind.npy')==80;delta=float(np.max(abs(a[mask]-b[mask]),initial=0));report['far5'].append({'seed':seed,'unknownSurfaceDeltaM':delta})
   if delta>1e-6:report['issues'].append(f'FAR-5 changed {seed}')
 # Current completed river trial can be a feasible candidate without claiming
 # all rejected narrow-domain or sediment-width comparisons are successful.
 report['passed']=not report['issues'];report['routeConflicts']=sum(v['newSamplesOver3000With200mClearance']>0 for v in report['routes']);T.savejson(work/'verification.json',report);T.log(json.dumps({'terrainPassed':report['passed'],'runs':len(report['runs']),'details':len(report['refinements']),'riverRoutingStable':report['river']['routeAndIncisionStable'],'issues':report['issues']}));return report

def timesteps(work):
 C.open_work(work,work/'applied-masks');out=work/'validation-half-dt';out.mkdir(exist_ok=True);results=[]
 for region in ['aethelgard','vorhan','polar-north-two','polar-south-west']:
  source=work/region;dest=out/region
  if not dest.exists():shutil.copytree(source,dest)
  T.WORK=out;T.MASK=work/'applied-masks';s=json.loads((source/'5210914/simulation.json').read_text(encoding='utf8'));T.evolve(region,5210914,s['stepYears']/2);a=np.load(source/'5210914/height.npy');b=np.load(dest/'5210914/height.npy');ini=np.load(source/'5210914/initial.npy');allow=np.load(source/'allow.npy')>0;dz=np.abs(a-b)[allow];change=np.sqrt(np.mean((b[allow]-ini[allow])**2));error=float(np.sqrt(np.mean(dz**2))/max(1,change));result={'region':region,'rmsFractionOfEvolution':error,'p99HeightDifferenceM':float(np.percentile(dz,99)),'maximumHeightDifferenceM':float(dz.max()),'passed':error<.1};results.append(result)
 T.WORK=work;T.savejson(work/'timestep-convergence.json',{'comparisons':results,'passed':all(v['passed'] for v in results)});return results

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=C.DEFAULT);ap.add_argument('--timesteps',action='store_true');a=ap.parse_args();result=timesteps(a.work) if a.timesteps else verify(a.work)
 if not a.timesteps and not result['passed']:raise SystemExit(1)
