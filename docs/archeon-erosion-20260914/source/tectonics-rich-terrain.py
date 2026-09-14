"""Rich layered base variants after visual discovery of planar coarse ramps."""
import pathlib,sys,importlib,argparse,json
sys.path.insert(0,str(pathlib.Path(__file__).parent));X=importlib.import_module('tectonics-cycle');T=X.T;D=importlib.import_module('tectonics-cycle-detail')
def run(work,region,mode='episodic',mask=None,end=2000000):
    original=next(s for s in D.plans(work) if s['parent']==region and 'erosion-2km' in s['id']);s={**original,'id':region+'-layered-2km','mode':mode,'morphologyPrior':'mountain' if region=='vorhan' else 'stepped','priorAmplitudeM':100,'priorExtentKm':80,'title':{'aethelgard':'Aethelgard · 分层台地与谷网','vorhan':'Vorhan · 倾斜断块与支谷','duskreach':'Duskreach · 桌山群与峡谷','keld':'Keld · 岛山与残余台顶'}[region]+' · 2 km'};planfile=work/'detail-plan.json'
    def register(q):
        plan=X.read(planfile) if planfile.exists() else [];T.savejson(planfile,[v for v in plan if (v['id'],v['mode'])!=(q['id'],q['mode'])]+[q])
    register(s);D.execute(work/mode,s,end,5000,mask)
    folder=work/mode/'refined'/s['id'];g=X.read(folder/'grid.json');np=T.np;z=np.load(folder/'initial.npy');gy,gx=np.gradient(z,g['stepM']);score=np.hypot(gx,gy);n,m=z.shape;frame=np.minimum.reduce(np.broadcast_arrays(np.arange(n)[:,None],n-1-np.arange(n)[:,None],np.arange(m)[None,:],m-1-np.arange(m)[None,:]));score[(frame*g['stepM']<32000)|(np.load(folder/'protected.npy')>0)|(z<1500)]=0;r,c=np.unravel_index(np.argmax(score),score.shape);center=list(T.Proj(g['projection'])(g['xmin']+c*g['stepM'],g['ymax']-r*g['stepM'],inverse=True))
    child={**s,'id':region+'-layered-scarp-250m','parent':s['id'],'center':center,'widthKm':32,'stepM':250,'priorAmplitudeM':45,'priorExtentKm':12,'selection':'Resolved highland slope, not maximum-incision lowland floor','title':s['title'].replace('2 km','崖段 250 m')};register(child);D.execute(work/mode,child,end,2500,mask)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=X.DEFAULT);ap.add_argument('--region',default='all');ap.add_argument('--mode',default='episodic');ap.add_argument('--mask',type=pathlib.Path);ap.add_argument('--end',type=int,default=2000000);a=ap.parse_args()
    for region in X.REGIONS if a.region=='all' else [a.region]:run(a.work,region,a.mode,a.mask,a.end)
