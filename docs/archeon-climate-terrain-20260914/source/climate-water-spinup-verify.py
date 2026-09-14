"""Compare accelerated lake iterations against the unchanged full solver."""
import pathlib,sys,importlib,tempfile
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;S=importlib.import_module('climate-water-spinup');H=S.H;L=importlib.import_module('tectonics-landscape')

def compare(a,b,tolerance):
    rows={}
    for name in ['lake-depth','lake-min-depth','lake-max-depth','lake-occurrence','discharge']:
        error=float(np.max(abs(a[name]-b[name]),initial=0));scale=max(1,float(np.max(abs(a[name]),initial=0)));rows[name]={'maximumAbsoluteError':error,'relativeToMaximum':error/scale}
        if error/scale>tolerance:raise ValueError('Accelerated/full mismatch '+name+' '+str(error/scale))
    return rows

def run():
    n=25;yy,xx=np.indices((n,n));land=np.ones((n,n),bool);land[[0,-1]]=False;land[:,[0,-1]]=False
    z=8+.03*yy-7*np.exp(-((xx-8)**2+(yy-9)**2)/22)-6*np.exp(-((xx-17)**2+(yy-17)**2)/18);climate={'rain':np.ones_like(z)*1.2,'temperature':np.ones_like(z)*12}
    results=[]
    for name,factor,initial,ext in [('baseline',1,None,None),('dry',.5,None,None),('wet',1.5,None,None),('external',1,None,np.where((xx==6)&(yy==5),30000.,0.)),('recession',0,np.maximum(0,7-z)*land,None)]:
        a=H.run(z,land,100,climate,factor,cycles=20,converge=True,max_cycles=200,initial_depth=initial,external=ext);b=S.run(z,land,100,climate,factor,cycles=20,max_cycles=200,initial_depth=initial,external=ext)
        result=compare(a,b,1e-8);results.append({'case':name,'difference':result,'fullCycles':a['convergence']['waterYears'],'acceleratedCycles':b['convergence']['waterYears']});print('SPINUP MATCH',name,flush=True)
    with tempfile.TemporaryDirectory(prefix='archeon-water-checkpoint-') as tmp:
        checkpoint=pathlib.Path(tmp)/'state.npz'
        uninterrupted=S.run(z,land,100,climate,max_cycles=200)
        S.run(z,land,100,climate,cycles=7,max_cycles=7,checkpoint=checkpoint)
        resumed=S.run(z,land,100,climate,max_cycles=200,checkpoint=checkpoint)
        check=compare(uninterrupted,resumed,1e-12)
        if uninterrupted['convergence']['waterYears']!=resumed['convergence']['waterYears']:raise ValueError('Checkpoint changed convergence clock')
        try:S.run(z+.01,land,100,climate,max_cycles=200,checkpoint=checkpoint)
        except ValueError as e:
            if 'Checkpoint inputs' not in str(e):raise
        else:raise ValueError('Checkpoint accepted changed terrain')
        results.append({'case':'interrupted/resumed equivalence and changed-input rejection','difference':check})
    base=C.TASK/'assembled/keld/5210914/erosion-only/baseline';g=C.read(base/'grid.json');z=np.load(base/'height.npy').astype(float);kind=np.load(base/'kind.npy');b=S.run(z,(kind>=30)&(kind!=80),g['stepM'],L.proxy(z,g,kind),progress=lambda r:print('KELD FAST',r,flush=True))
    original=base/'water/baseline';a={name:np.load(original/(name+'.npy')) for name in ['lake-depth','lake-min-depth','lake-max-depth','lake-occurrence','discharge']};result=compare(a,b,1e-6)
    results.append({'case':'full 3.4 million-cell Keld regression','difference':result,'acceleration':b['spinupAcceleration'],'waterConverged':b['convergence']['passed']})
    C.write(C.TASK/'terrain-completion-v18/spinup-verification.json',{'passed':True,'cases':results,'unchangedReferenceSolverSha256':C.sha(H.__file__)});print('SPINUP ALL VERIFIED',flush=True)

if __name__=='__main__':run()
