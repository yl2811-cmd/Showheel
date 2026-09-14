"""Re-erode the corrected island outlets and their dependent local windows."""
import pathlib,sys,importlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;L=importlib.import_module('tectonics-landscape')
OUT=C.TASK/'terrain-completion-v18/keld-outlet-evolution';BASE=C.TASK/'terrain-completion-v18/keld-outlet-repair-v2'

def run():
    L.WORK=OUT;T.WORK=OUT;T.MASK=None;L.CFG={**L.CFG,'maximumSeasonalCycles':1000};bg=C.read(BASE/'grid.json');arrays={n:np.load(BASE/(n+'.npy'),mmap_mode='r') for n in ['height','kind','soil','protected']}
    cg={**bg,'stepM':16000,'width':round((bg['width']-1)/8)+1,'height':round((bg['height']-1)/8)+1,'seed':5210914}
    for scenario in ['baseline','dry','wet']:
        coarse=OUT/'coarse'/scenario;z,kind,soil,hard=[T.sample(arrays[n],bg,cg,0 if n in ['kind','protected'] else 1) for n in ['height','kind','soil','protected']];kind=kind.astype('uint8');hard=hard>0;allow=((kind>=30)&~hard).astype(float)
        L.solve(coarse,cg,z.astype(float),kind,hard,allow,soil.astype(float),[],'erosion-only',scenario,1,end=2000000,dt=10000,cap=420)
        for id,center in [('shellharbor',[54,-2]),('tidemark',[47,11])]:
            spec={'id':id,'region':'keld','center':center};g=L.grid_window(spec,2000,256);g['seed']=5210914;z,kind,soil,hard=[T.sample(arrays[n],bg,g,0 if n in ['kind','protected'] else 1) for n in ['height','kind','soil','protected']];kind=kind.astype('uint8');hard=hard>0
            rr,cc=np.indices(z.shape);edge=np.minimum.reduce([rr,cc,g['height']-1-rr,g['width']-1-cc])*2000;allow=T.ease(edge/24000);allow[hard|(kind<30)]=0;folder=OUT/'regional'/id/scenario
            report=L.solve(folder,g,z.astype(float),kind,hard,allow,soil.astype(float),[],'erosion-only',scenario,1,parent=(coarse,cg),end=2000000,dt=5000,cap=420)
            C.write(folder/'source.json',{'outletCorrectionHeightSha256':C.sha(BASE/'height.npy'),'scope':'corrected inner scene envelope is a hypothesis; exact building/farmland geometry not registered','climateValidated':False});print('KELD REEROSION',id,scenario,report['passed'],flush=True);gc.collect()

if __name__=='__main__':run()
