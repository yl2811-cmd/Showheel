"""Export completed terrain candidates without promoting them to the world map."""
import pathlib,sys,importlib,time
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;E=importlib.import_module('tectonics-export');V=importlib.import_module('landscape-export')
ROOT=C.TASK/'terrain-completion-v18';OUT=C.ROOT/'foundation/terrain-completion-v18'

def one(folder,identifier):
    r=C.read(folder/'simulation.json');g=C.read(folder/'grid.json');key=C.fingerprint({'request':C.sha(folder/'request.json'),'height':C.sha(folder/'height.npy'),'exporter':C.sha(__file__)});cache=OUT/(identifier+'.json')
    if cache.exists() and C.read(cache).get('fingerprint')==key:return C.read(cache)
    kind=np.load(folder/'kind-0.npy');stages=[];E.OUT=OUT
    for year in [0,10000,100000,500000,2000000]:
        if year>r['effectiveYears'] or not (folder/f'height-{year}.npy').exists():continue
        z=np.load(folder/f'height-{year}.npy');d=np.load(folder/f'lake-depth-{year}.npy');q=np.load(folder/f'discharge-{year}.npy');rec=np.load(folder/f'receiver-{year}.npy');name=f'{identifier}-{year}'
        E.write_image(name+'.png',E.elevation(z),kind);rivers=V.lines(g,q,np.where(d>.05,-1,rec));lakes=V.lakes(g,z,d,np.load(folder/'lake-occurrence.npy') if year==r['effectiveYears'] else np.zeros_like(d))
        for f in rivers:f['properties'].pop('screen',None)
        for f in lakes:
            if year!=r['effectiveYears']:f['properties']['state']='snapshot; seasonal persistence not stored for this time'
        meta={'candidateOnly':True,'modernClimateValidated':False,'effectiveYears':year,'sourceHeightSha256':C.sha(folder/f'height-{year}.npy')}
        C.write(OUT/(name+'-rivers.geojson'),{'type':'FeatureCollection','properties':meta,'features':rivers});C.write(OUT/(name+'-lakes.geojson'),{'type':'FeatureCollection','properties':meta,'features':lakes});stages.append({'effectiveYears':year,'height':name+'.png','rivers':name+'-rivers.geojson','lakes':name+'-lakes.geojson'})
    row={'id':identifier,'fingerprint':key,'grid':g,'stages':stages,'effectiveYears':r['effectiveYears'],'numericalConservationPassed':r['passed'],'waterConverged':r['waterConvergence']['passed'],'morphologyProxyPassed':r['retentionPassed'],'quietAreaRetention':r['quietAreaRetention'],'maximumWaterRelativeError':r['maxWaterRelativeError'],'maximumSolidRelativeError':r['maxVolumeRelativeError'],'protectedMaximumChangeM':r['protectedMaxDeltaM'],'terrainAccepted':False,'climateAccepted':False,'state':'WIP candidate; full matrix and story-geography acceptance pending'};C.write(cache,row);return row

def run():
    OUT.mkdir(parents=True,exist_ok=True);rows=[]
    folders=list((ROOT/'regional').glob('*/simulation.json'))+list((ROOT/'detail').glob('**/simulation.json'))+list((ROOT/'keld-outlet-evolution/regional').glob('**/simulation.json'))
    sea=C.TASK/'high-inland-sea-v17/natural-shore-v3/regional/erosion-only/baseline/2000/2000000'
    if (sea/'simulation.json').exists():rows.append(one(sea,'high-inland-sea'))
    for file in folders:
        folder=file.parent;identifier=folder.relative_to(ROOT).as_posix().replace('/','-');rows.append(one(folder,identifier));print('COMPLETED BAKE',identifier,flush=True)
    C.write(OUT/'manifest.json',{'version':'terrain-completion-v18','updatedUnix':time.time(),'candidates':rows,'climate':'WIP','vegetation':'WIP','routes':'WIP','worldDefaultChanged':False});return rows

if __name__=='__main__':run()
