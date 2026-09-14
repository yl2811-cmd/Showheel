"""Island valley and watershed windows from the repaired, re-eroded parents."""
import pathlib,sys,importlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;L=importlib.import_module('tectonics-landscape')
from scipy.ndimage import maximum_filter,minimum_filter,distance_transform_edt
ROOT=C.TASK/'terrain-completion-v18';PARENT=ROOT/'keld-outlet-evolution'

def run():
    L.WORK=ROOT;T.WORK=ROOT;T.MASK=None;L.CFG={**L.CFG,'maximumSeasonalCycles':1000}
    for name in ['shellharbor','tidemark']:
        parent=PARENT/'regional'/name/'baseline';pg=C.read(parent/'grid.json');z=np.load(parent/'height.npy');kind=np.load(parent/'kind-0.npy');hard=np.load(parent/'protected.npy');rr,cc=np.indices(z.shape)
        relief=maximum_filter(z,9)-minimum_filter(z,9);valid=(kind>=30)&~hard&(distance_transform_edt(kind>=30)*2000>=16000)
        valid&=np.minimum.reduce([rr,cc,len(z)-1-rr,z.shape[1]-1-cc])*2000>=36000
        score=np.where(valid,relief,-np.inf)
        if not valid.any():raise ValueError('No supported island watershed window: '+name)
        r,c=np.unravel_index(np.argmax(score),score.shape);center=list(T.Proj(pg['projection'])(pg['xmin']+c*2000,pg['ymax']-r*2000,inverse=True));g=L.grid_window({'id':'keld-'+name+'-valley','region':'keld','center':center},250,64);g['seed']=5210914
        folder=ROOT/'detail'/g['id']/'2000000/250';z0=T.sample(np.load(parent/'initial.npy'),pg,g).astype(float);kd=T.sample(kind,pg,g,0).astype('uint8');protected=T.sample(hard,pg,g,0)>0;soil=T.sample(np.load(parent/'soil-initial.npy'),pg,g)
        rr,cc=np.indices(z0.shape);edge=np.minimum.reduce([rr,cc,g['height']-1-rr,g['width']-1-cc])*250;allow=T.ease(edge/4000);allow[protected|(kd<30)]=0
        C.write(folder/'selection.json',{'center':center,'parent':str(parent),'method':'island valley relief within supported interior, 16 km coast clearance; exact scene envelope inherited','climateValidated':False})
        result=L.solve(folder,g,z0,kd,protected,allow,soil,[],'erosion-only','baseline',1,parent=(parent,pg),end=2000000,dt=2500,cap=420)
        print('KELD DETAIL',name,result['passed'],flush=True);gc.collect()

if __name__=='__main__':run()
