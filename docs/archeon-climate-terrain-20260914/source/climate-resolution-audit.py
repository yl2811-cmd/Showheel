"""Separate spatial and temporal errors on identical registered initial fields."""
import pathlib,sys,importlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;L=importlib.import_module('tectonics-landscape');OUT=C.TASK/'terrain-completion-v18'

def run(names=None,output='resolution-audit.json'):
    L.WORK=OUT;T.WORK=OUT;T.MASK=None;L.CFG={**L.CFG,'maximumSeasonalCycles':1000};results=[]
    for name in names or ['vorhan-west-track','duskreach-west-track']:
        base=OUT/'comparison'/name/'100000/250';g=C.read(base/'grid.json');parent=OUT/'regional'/name.removesuffix('-source');pg=C.read(parent/'grid.json')
        initial=np.load(base/'initial.npy');kind=np.load(base/'kind-0.npy');hard=np.load(base/'protected.npy');allow=np.load(base/'allow.npy');soil=np.load(base/'soil-initial.npy');features=C.read(base/'source-catalog.json');timecase=OUT/'temporal'/name/'100000/250-dt1250'
        L.solve(timecase,g,initial.astype(float),kind,hard,allow.astype(float),soil.astype(float),features,'erosion-only','baseline',.9,parent=(parent,pg),end=100000,dt=1250,cap=420)
        def compare(coarse,fine):
            cg=C.read(coarse/'grid.json');fg=C.read(fine/'grid.json');a=np.load(coarse/'height.npy').astype(float)-np.load(coarse/'initial.npy');b=np.load(fine/'height.npy').astype(float)-np.load(fine/'initial.npy');sample=T.sample(b,fg,cg);kd=np.load(coarse/'kind-0.npy');rr,cc=np.indices(a.shape);interior=np.minimum.reduce([rr,cc,cg['height']-1-rr,cg['width']-1-cc])*cg['stepM']>=5000;valid=(kd>=30)&interior&~np.load(coarse/'protected.npy')
            error=a[valid]-sample[valid];scale=max(1e-8,float(np.sqrt(np.mean(sample[valid]**2))));initial_error=np.load(coarse/'initial.npy')-T.sample(np.load(fine/'initial.npy'),fg,cg)
            return {'coarseM':cg['stepM'],'fineM':fg['stepM'],'heightChangeRMSErrorM':float(np.sqrt(np.mean(error**2))),'relativeHeightChangeRMSError':float(np.sqrt(np.mean(error**2))/scale),'heightChangeP95ErrorM':float(np.percentile(abs(error),95)),'initialInterpolationRMSErrorM':float(np.sqrt(np.mean(initial_error[valid]**2))),'samples':int(valid.sum())}
        c125=OUT/'comparison'/name/'100000/125';c64=OUT/'comparison'/name/'100000/64';spatial=[compare(base,c125),compare(c125,c64)];temporal=compare(base,timecase)
        results.append({'id':name,'spatial':spatial,'temporal':temporal,'temporalStepsYears':[2500,1250],'samePhysicalBoundaryFadeM':4000,'sameInitialParent':str(parent),'spatialErrorDecreases':spatial[1]['heightChangeRMSErrorM']<spatial[0]['heightChangeRMSErrorM'],'scope':'numerical comparison on the original diagnostic windows; these are not evidence that the new source produced mesas or that modern climate is valid'})
        print('RESOLUTION AUDIT',name,results[-1]['spatialErrorDecreases'],flush=True);gc.collect()
    C.write(OUT/output,{'cases':results,'climateValidated':False,'acceptance':'Errors reported separately; numerical budget closure does not imply spatial or temporal convergence'});return results

if __name__=='__main__':run()
