"""Join resolved provinces into a 2km surface without repeating uplift.

The background geological solve remains 16km. Provincial evolution is 2km;
the assembled 2km grid is subsequently used for a continuous water network.
"""
import pathlib,sys,importlib,argparse,json,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));D=importlib.import_module('climate-terrain');C=D.C;T=C.T;np=C.np

def block_grid(g,row,rows):return {**g,'height':rows,'ymax':g['ymax']-row*g['stepM']}
def assemble(region,seed=5210914,mode='erosion-only',scenario='baseline'):
 status=C.read(C.WORK/'study-status.json');selection=status.get('selected',{});specs=[p for p in C.CFG['provinces'] if p['region']==region];chosen=[]
 for spec in specs:
  key=f'{spec["id"]}/{seed}/{mode}/{scenario}'
  if key not in selection:raise ValueError('No accepted enhancement for '+key)
  gain=selection[key];folder=C.WORK/'regional'/spec['id']/str(seed)/mode/scenario/f'g{gain:g}'/'2000'
  report=C.read(folder/'simulation.json')
  if report['effectiveYears']!=2000000 or not report['passed']:raise ValueError('Incomplete regional parent '+key)
  chosen.append((folder,C.read(folder/'grid.json'),np.load(folder/'height.npy',mmap_mode='r')))
 base=D.prepare(region,seed);g=C.read(base/'grid.json');original=np.load(base/'height.npy',mmap_mode='r');hard=np.load(base/'protected.npy',mmap_mode='r');kind=np.load(base/'kind.npy',mmap_mode='r')
 parent_name='vorhan-duskreach' if region!='keld' else region;parent=C.WORK/'coarse'/parent_name/str(seed)/mode/scenario/'g1';pg=C.read(parent/'grid.json');coarse_delta=np.load(parent/'height.npy')-np.load(parent/'initial.npy')
 out=C.WORK/'assembled'/region/str(seed)/mode/scenario;out.mkdir(parents=True,exist_ok=True)
 result=np.lib.format.open_memmap(out/'height.npy',mode='w+',dtype='float32',shape=original.shape);adjust=np.lib.format.open_memmap(out/'stitching-adjustment.npy',mode='w+',dtype='float32',shape=original.shape);volume=0
 for row in range(0,g['height'],128):
  rows=min(128,g['height']-row);bg=block_grid(g,row,rows);inherited=np.asarray(original[row:row+rows],float);background=inherited+T.sample(coarse_delta,pg,bg)
  numerator=np.zeros_like(background);denominator=np.zeros_like(background);xx,yy=T.mesh(bg)
  for folder,cg,cz in chosen:
   margin=np.minimum.reduce([xx-cg['xmin'],cg['xmin']+(cg['width']-1)*cg['stepM']-xx,cg['ymax']-yy,yy-(cg['ymax']-(cg['height']-1)*cg['stepM'])]);weight=T.ease(margin/24000)
   if weight.any():numerator+=weight*(T.sample(cz,cg,bg)-background);denominator+=weight
  correction=numerator/np.maximum(1,denominator);final=background+correction;fixed=np.asarray(hard[row:row+rows],bool)|(kind[row:row+rows]==0);final[fixed]=inherited[fixed]
  result[row:row+rows]=final;adjust[row:row+rows]=final-background;volume+=float((final-background).sum()*g['stepM']**2)
 result.flush();adjust.flush();del result,adjust
 for name in ['kind','soil','protected','quiet']:
  C.save_array(out/(name+'.npy'),np.load(base/(name+'.npy'),mmap_mode='r'))
 C.write(out/'grid.json',g);C.write(out/'assembly.json',{'version':C.CFG['version'],'sourceHeightSha256':C.sha(base/'height.npy'),'backgroundGridM':16000,'resolvedProvinceGridM':2000,'outputWaterGridM':2000,'stitchingWidthM':24000,'stitchingAdjustmentVolumeM3':volume,'parents':[{'path':str(p),'heightSha256':C.sha(p/'height.npy')} for p,cg,z in chosen],'oldUpliftRepeated':False,'status':'assembled; continuous hydrology and seam checks pending','climateReady':False})
 print('ASSEMBLED',region,seed,mode,scenario,flush=True);return out

def joint(seed=5210914,mode='erosion-only',scenario='baseline'):
 # The two continents and their land bridge share one grid and one receiver graph.
 g=D.joint_grid(2000);g['seed']=seed;sources=[]
 for region in ['vorhan','duskreach']:
  p=C.WORK/'assembled'/region/str(seed)/mode/scenario;sources.append((C.read(p/'grid.json'),np.load(p/'height.npy',mmap_mode='r'),np.load(p/'kind.npy',mmap_mode='r')))
 out=C.WORK/'assembled/vorhan-duskreach'/str(seed)/mode/scenario;out.mkdir(parents=True,exist_ok=True)
 height=np.lib.format.open_memmap(out/'height.npy',mode='w+',dtype='float32',shape=(g['height'],g['width']));kind=np.lib.format.open_memmap(out/'kind.npy',mode='w+',dtype='uint8',shape=height.shape)
 footprints={r:[f['geometry'] for f in T.D['land'] if f['id'] in (['Vorhan'] if r=='vorhan' else ['Duskreach','vorhan-duskreach-bridge'])] for r in ['vorhan','duskreach']}
 for row in range(0,g['height'],128):
  n=min(128,g['height']-row);bg=block_grid(g,row,n);z=np.zeros((n,g['width']));mask=np.zeros(z.shape,bool)
  for region,(pg,pz,pk) in zip(['vorhan','duskreach'],sources):
   m=T.raster(footprints[region],bg);sample=T.sample(pz,pg,bg);z[m]=sample[m];mask|=m
  z[~mask]=-20.;height[row:row+n]=z;kind[row:row+n]=np.where(mask,70,0)
 height.flush();kind.flush();del height,kind
 C.write(out/'grid.json',g);C.write(out/'assembly.json',{'continuousGrid':True,'gridM':2000,'regions':['vorhan','duskreach','vorhan-duskreach-bridge'],'heightSha256':C.sha(out/'height.npy'),'status':'joined surface; seam and seasonal-water validation pending','marineBed':'-20m numerical outlet boundary only, not bathymetry'})
 return out

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--region',default='all');a.add_argument('--seed',type=int,default=5210914);a.add_argument('--mode',default='erosion-only');a.add_argument('--scenario',default='baseline');q=a.parse_args()
 for region in C.CFG['regions'] if q.region=='all' else [q.region]:assemble(region,q.seed,q.mode,q.scenario);gc.collect()
 if q.region=='all':joint(q.seed,q.mode,q.scenario)
