"""Authorised Orun / Marneth sensitivity copies, without unlocking formal maps."""
import pathlib,sys,importlib,json,argparse,shutil
sys.path.insert(0,str(pathlib.Path(__file__).parent));X=importlib.import_module('tectonics-cycle');T=X.T;D=importlib.import_module('tectonics-cycle-detail');R=D.R

def run(work,mask=None):
    mode='erosion-only';X.setup(work/mode,mask);R.WORK=work/mode;oldtimes=T.C['timesYears'];T.C['timesYears']=[0,10000,100000,500000,2000000];planfile=work/'detail-plan.json';plan=X.read(planfile) if planfile.exists() else []
    configs=[
      {'id':'orun-young-2km','parent':'aethelgard','center':[-5,10.2],'widthKm':384,'stepM':2000,'title':'Orun 新高原 · 保护地貌侵蚀 · 2 km','authorisedProtectedLandform':'orun','capThicknessM':420,'erosionBufferM':110000,'initialGeologicalState':'recent uplifted plateau with intact strong cap; formation age not assigned to canon'},
      {'id':'marneth-old-2km','parent':'aethelgard','center':[19.2,27.4],'widthKm':384,'stepM':2000,'title':'Marneth 旧山带 · 保护地貌侵蚀 · 2 km','authorisedProtectedLandform':'marneth','capThicknessM':60,'erosionBufferM':100000,'initialGeologicalState':'older reworked tilted strata; thinner remaining surface cap is a sensitivity hypothesis'}
    ]
    for cfg in configs:
        cfg.update(erosionCycle=True,continuationCatalog=True,mode=mode,protectedTrial=True);folder=work/mode/'refined'/cfg['id'];plan=[s for s in plan if s['id']!=cfg['id']]+[cfg];T.savejson(planfile,plan)
        R.run(cfg,5210914,dtmax=5000,end=2000000)
        child={**cfg,'id':cfg['id'].replace('2km','250m'),'parent':cfg['id'],'center':D.select_detail(work/mode,cfg,48),'widthKm':48,'stepM':250,'title':cfg['title'].replace('2 km','250 m')};plan=[s for s in plan if s['id']!=child['id']]+[child];T.savejson(planfile,plan);R.run(child,5210914,dtmax=2000,end=2000000)
        T.savejson(folder/'age-assumption.json',{'state':cfg['initialGeologicalState'],'shortTimesYears':[10000,100000],'stressTestYears':[500000,2000000],'newAgeDoesNotGuaranteeLowIncision':True,'sceneCoresPreserved':True})
    T.C['timesYears']=oldtimes;return plan

def cliffs(work,mask=None):
    mode='erosion-only';X.setup(work/mode,mask);R.WORK=work/mode;T.C['timesYears']=[0,10000,100000,500000,2000000]
    for ridge,parent,title in [('orun','orun-young-2km','Orun 主崖 · 崖顶与谷头'),('marneth','marneth-old-2km','Marneth · 平行山脊与谷壁')]:
        folder=work/mode/'refined'/parent;g=X.read(folder/'grid.json');z=T.np.load(folder/'height.npy');p=T.Proj(g['projection']);coords=X.read(X.BASE/'aethelgard/orun-trace.json')['revised'] if ridge=='orun' else next(f['geometry']['coordinates'] for f in T.D['ridges'] if f['id']==ridge);distance,_=T.tracefield(g,coords);gy,gx=T.np.gradient(z,g['stepM']);score=T.np.hypot(gx,gy);n,m=z.shape;frame=T.np.minimum.reduce(T.np.broadcast_arrays(T.np.arange(n)[:,None],n-1-T.np.arange(n)[:,None],T.np.arange(m)[None,:],m-1-T.np.arange(m)[None,:]));score[(frame*g['stepM']<40000)|(T.np.load(folder/'protected.npy')>0)|(z<1800)|(distance>25000)]=0
        r,c=T.np.unravel_index(T.np.argmax(score),score.shape)
        if score[r,c]==0:raise RuntimeError('No resolved scarp in authorised zone '+ridge)
        center=list(p(g['xmin']+c*g['stepM'],g['ymax']-r*g['stepM'],inverse=True));spec={'id':ridge+'-scarp-250m','parent':parent,'center':center,'widthKm':48,'stepM':250,'title':title+' · 250 m','mode':mode,'erosionCycle':True,'continuationCatalog':True,'authorisedProtectedLandform':ridge,'capThicknessM':420 if ridge=='orun' else 60,'erosionBufferM':110000 if ridge=='orun' else 100000,'protectedTrial':True,'selection':'maximum resolved slope within 25 km of the mapped main fault/belt, above1800m, with full child support'}
        planfile=work/'detail-plan.json';plan=X.read(planfile);T.savejson(planfile,[v for v in plan if (v['id'],v['mode'])!=(spec['id'],mode)]+[spec]);R.run(spec,5210914,dtmax=2000,end=2000000)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=X.DEFAULT);ap.add_argument('--mask',type=pathlib.Path);ap.add_argument('--cliffs',action='store_true');a=ap.parse_args();cliffs(a.work,a.mask) if a.cliffs else run(a.work,a.mask)
