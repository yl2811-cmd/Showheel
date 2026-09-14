"""Validated fast spinup plus full-graph checks for the shared 2 km network."""
import pathlib,sys,importlib,time,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;S=importlib.import_module('climate-water-spinup');L=importlib.import_module('tectonics-landscape')
ROOT=C.TASK/'terrain-completion-v18'

def solve(folder,initial_water=None):
    proof=C.read(ROOT/'spinup-verification.json')
    if not proof['passed'] or proof['unchangedReferenceSolverSha256']!=C.sha(S.H.__file__) or proof['cases'][-1]['acceleration']['implementationSha256']!=C.sha(S.__file__):raise ValueError('Spinup algorithm requires matching reference tests')
    folder=pathlib.Path(folder);g=C.read(folder/'grid.json');out=folder/'water-accelerated/baseline';height_hash=C.sha(folder/'height.npy')
    if (out/'hydrology.json').exists() and C.read(out/'hydrology.json')['sourceHeightSha256']==height_hash:return out
    z=np.load(folder/'height.npy').astype(float);kind=np.load(folder/'kind.npy');initial=None if initial_water is None else np.load(pathlib.Path(initial_water)/'lake-depth.npy').astype(float);started=time.time()
    def progress(row):C.write(out/'progress.json',row);print(folder.name,row,flush=True)
    h=S.run(z,(kind>=30)&(kind!=80),g['stepM'],L.proxy(z,g,kind),initial_depth=initial,max_cycles=5000,progress=progress,checkpoint=out/'spinup-checkpoint.npz')
    for name in ['discharge','receiver','lake-depth','lake-level','lake-occurrence','lake-min-depth','lake-max-depth','wetness']:C.save_array(out/(name+'.npy'),h[name].astype('int32') if name=='receiver' else h[name].astype('float32'))
    C.write(out/'grid.json',g);report={'sourceHeightSha256':height_hash,'gridM':g['stepM'],'continuousNetwork':True,'maximumWaterRelativeError':h['maxWaterRelativeError'],'convergence':h['convergence'],'acceleration':h['spinupAcceleration'],'history':h['history'],'lakes':h['lakes'],'climateValidated':False,'elapsedSeconds':time.time()-started,'initialWaterSource':str(initial_water) if initial_water else None};C.write(out/'hydrology.json',report);print('FULL CONTINUOUS WATER DONE',folder.name,report['convergence'],flush=True);return out

if __name__=='__main__':
    base=ROOT/'continuous/vorhan-duskreach/base';first=solve(base);gc.collect();evolved=ROOT/'continuous/vorhan-duskreach/evolved-2000000';solve(evolved,first)
