"""Nested 2km / 250m plume erosion with inherited water and sediment fluxes."""
import pathlib,sys,importlib,argparse,gc,time
sys.path.insert(0,str(pathlib.Path(__file__).parent))
P=importlib.import_module('climate-vorhan-plumes');C=P.C;D=P.D;L=P.L;T=P.T;np=P.np

def run(site,case='both',seed=5210914,mode='erosion-only',scenario='baseline',end=100000,step=2000):
 P.setup();s=next(v for v in P.siting() if v['id'].endswith(site));spec={'id':s['id'],'region':'vorhan','center':s['center']}
 if step<2000:
  # A fault-facing cap edge, chosen in physical coordinates and fixed across
  # 250/125/64m comparisons. Parent centre and main cap remain unchanged.
  baseg=D.grid('vorhan',16000);_,_,sources=P.displacement(baseg,seed,site);angle=np.deg2rad(sources[0]['angleDegrees']);x,y=T.Proj(baseg['projection'])(*s['center']);offset=100000
  spec['center']=list(T.Proj(baseg['projection'])(x-np.sin(angle)*offset,y+np.cos(angle)*offset,inverse=True));spec['id']=s['id']+'-cap-edge'
 g=L.grid_window(spec,step,64 if step<2000 else 768);g['seed']=seed
 folder=C.WORK/('detail' if step<2000 else 'regional')/case/site/str(seed)/mode/scenario/str(step)
 parent=C.WORK/'regional'/case/site/str(seed)/mode/scenario/'2000' if step<2000 else C.WORK/('long-coarse' if end>100000 else 'coarse')/case/str(seed)/mode/scenario/'g1'
 if not (parent/'simulation.json').exists() or C.read(parent/'simulation.json')['effectiveYears']<end:raise ValueError('Completed matching parent required: '+str(parent))
 z,kind,soil,allow,hard,quiet,features,record=D.input_fields('vorhan',seed,g,1);fields,late,sources=P.displacement(g,seed,case);extra=sum(fields.values());land=(kind>=30)&(kind!=80);free=land.astype(float)
 for feature in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
  if feature['geometry']['type']=='Point':free*=T.ease((T.distance(g,feature['geometry']['coordinates'])-20000)/80000)
 free[hard]=0;z+=extra*free;allow=np.maximum(allow,T.ease(extra/120)*free)
 rows,cols=np.indices(z.shape);buffer=4000 if step<2000 else 24000
 edge_distance=np.minimum.reduce([rows,cols,g['height']-1-rows,g['width']-1-cols])*step;allow*=T.ease(edge_distance/buffer)
 for key,value in fields.items():C.save_array(folder/(key+'.npy'),value*free)
 C.save_array(folder/'base-repair.npy',record['base-repair']);C.write(folder/'plumes.json',{'case':case,'site':site,'sources':sources,'parentHeightSha256':C.sha(parent/'height.npy'),'parentInitialSha256':C.sha(parent/'initial.npy'),'gridM':step,'initialDatum':'same repaired base and source physics, independently evaluated at physical coordinates','boundaryBufferM':buffer,'climateValidated':False})
 result=L.solve(folder,g,z,kind,hard,allow,soil,features+late,mode,scenario,1,parent=(parent,C.read(parent/'grid.json')),end=end,dt=2500 if step<250 else 5000,cap=420)
 print('PLUME DETAIL',case,site,step,end,result['passed'],flush=True);return folder

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--site',choices=['west','east','all'],default='all');p.add_argument('--case',choices=P.CASES,default='both');p.add_argument('--seed',type=int,default=5210914);p.add_argument('--mode',default='erosion-only');p.add_argument('--scenario',default='baseline');p.add_argument('--end',type=int,default=100000);p.add_argument('--step',type=int,default=2000);q=p.parse_args()
 for site in ['west','east'] if q.site=='all' else [q.site]:run(site,q.case,q.seed,q.mode,q.scenario,q.end,q.step);gc.collect()
