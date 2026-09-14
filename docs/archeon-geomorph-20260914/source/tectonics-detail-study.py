"""Selected 2 km -> 250 m -> 64 m fields with inherited transient forcing."""
import sys,pathlib,importlib,json,argparse,time
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('tectonics-continuation');T=C.T;np=T.np;R=importlib.import_module('tectonics-refine')

def plans(work,seed):
 configs=[]
 for region in T.C['regions']:
  folder=work/region/str(seed)
  if not (folder/'landforms.json').exists():continue
  g=json.loads((work/region/'grid.json').read_text(encoding='utf8'));allow=np.load(work/region/'allow.npy');catalog=json.loads((folder/'landforms.json').read_text(encoding='utf8'));used=set(json.loads((folder/'construction.json').read_text(encoding='utf8'))['resolvedIds'])
  viable=[]
  for f in catalog:
   x,y=f['xy'];rr=int(round((g['ymax']-y)/g['stepM']));cc=int(round((x-g['xmin'])/g['stepM']))
   if 2<rr<g['height']-3 and 2<cc<g['width']-3 and allow[rr,cc]>.8 and f['id'] not in used:viable.append(f)
  if not viable:continue
  f=max(viable,key=lambda f:f['reliefM']*f['lengthM']);configs.append({'id':region+'-regional','parent':region,'center':f['center'],'widthKm':160,'stepM':2000,'continuationCatalog':True,'targetLandform':f['id']})
 configs.append({'id':'atheria-frontier-quiet','parent':'aethelgard','center':[.3,27],'widthKm':640,'stepM':2000,'continuationCatalog':True,'purpose':'Verify broad gentle terrain outside the protected detailed scenes'})
 return configs

def run(work,seed=5210914,mask=None):
 C.open_work(work,mask);R.WORK=work;R.T.WORK=work;configs=plans(work,seed);T.savejson(work/'detail-plan.json',configs);reports=[]
 def execute(config,dt,end):
  folder=work/'refined'/config['id'];report=folder/'simulation.json';parent_record=folder/'parent-boundary.json'
  parent=work/config['parent']/str(seed) if config['parent'] in T.C['regions'] else work/'refined'/config['parent']
  if report.exists() and parent_record.exists():
   old=json.loads(report.read_text(encoding='utf8'));lineage=json.loads(parent_record.read_text(encoding='utf8'))
   saved_grid=json.loads((folder/'grid.json').read_text(encoding='utf8'));cx,cy=T.Proj(saved_grid['projection'])(*config['center']);matches=saved_grid['stepM']==config['stepM'] and abs(saved_grid['xmin']+config['widthKm']*500-cx)<config['stepM']*.01 and abs(saved_grid['ymax']-config['widthKm']*500-cy)<config['stepM']*.01
   if matches and old.get('passed') and old.get('effectiveYears')==end and old.get('seed',5210914)==seed and lineage['parentHeightSha256']==T.sha(parent/'height.npy'):
    T.log('REUSED DETAIL '+config['id']);return
  R.run(config,seed,dtmax=dt,end=end)
 for config in configs:
  execute(config,1000,100000);reports.append({'id':config['id'],'gridM':config['stepM'],'years':100000})
 def cliff_center(parent_id,child_width):
  folder=work/'refined'/parent_id;g=json.loads((folder/'grid.json').read_text(encoding='utf8'));z=np.load(folder/'height.npy');kind=np.load(folder/'kind.npy');protected=np.load(folder/'protected.npy')>0;gy,gx=np.gradient(z,g['stepM']);score=np.hypot(gx,gy);n,m=z.shape;frame=np.minimum.reduce(np.broadcast_arrays(np.arange(n)[:,None],n-1-np.arange(n)[:,None],np.arange(m)[None,:],m-1-np.arange(m)[None,:]));score[(frame*g['stepM']<child_width*500+g['stepM']*2)|protected|(kind<30)]=0
  r,c=np.unravel_index(np.argmax(score),score.shape);return list(T.Proj(g['projection'])(g['xmin']+c*g['stepM'],g['ymax']-r*g['stepM'],inverse=True))
 for parent_id in ['aethelgard-regional','vorhan-regional','polar-north-two-regional']:
  parent=next((v for v in configs if v['id']==parent_id),None)
  if parent is None:continue
  config={**parent,'id':parent_id+'-250m','parent':parent_id,'center':cliff_center(parent_id,48),'widthKm':48,'stepM':250,'selection':'Maximum resolved parent slope with full child boundary support'};execute(config,500,100000);configs.append(config);reports.append({'id':config['id'],'gridM':250,'years':100000})
 fine=next((v for v in configs if v['id']=='aethelgard-regional-250m'),None)
 if fine:
  config={**fine,'id':'aethelgard-cliff-64m','parent':fine['id'],'center':cliff_center(fine['id'],8.192),'widthKm':8.192,'stepM':64};execute(config,100,10000);configs.append(config);reports.append({'id':config['id'],'gridM':64,'years':10000})
 T.savejson(work/'detail-plan.json',configs);T.savejson(work/'detail-summary.json',reports);return reports
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=C.DEFAULT);ap.add_argument('--seed',type=int,default=5210914);ap.add_argument('--mask',type=pathlib.Path);a=ap.parse_args();run(a.work,a.seed,a.mask)
