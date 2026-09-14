"""Prepare verifiable references for vegetation; incomplete climate cannot pass."""
import pathlib,sys,importlib,argparse,time
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;K=importlib.import_module('climate-contract')
ROOT=C.TASK/'terrain-completion-v18';OUT=C.TASK/'vegetation-input-v19'

def reference(path,unit):
    return {'path':str(path),'sha256':C.sha(path),'units':unit}

def prepare(climate=None):
    cases=[];missing=[]
    files=list((ROOT/'regional').glob('*/simulation.json'))+list((ROOT/'detail').glob('**/simulation.json'))+list((ROOT/'keld-outlet-evolution/regional').glob('**/simulation.json'))
    for file in files:
        folder=file.parent;r=C.read(file);fields={}
        for name,unit in [('height','m'),('soil','m'),('bedrock','m'),('erosion','m'),('deposition','m'),('wetness','1'),('lake-depth','m'),('lake-min-depth','m'),('lake-max-depth','m'),('lake-occurrence','1'),('discharge','m3 per effective-year proxy forcing')]:
            path=folder/(name+'.npy')
            if path.exists():fields[name]=reference(path,unit)
        cases.append({'id':folder.relative_to(ROOT).as_posix(),'grid':C.read(folder/'grid.json'),'requestSha256':C.sha(folder/'request.json'),'fields':fields,'numericalConservationPassed':r['passed'],'morphologyProxyPassed':r['retentionPassed'],'seasonalLakeConverged':r['waterConvergence']['passed'],'storyFootprintsFullyAccepted':False,'modernClimateDriven':False,'soilStatus':'erosion/weathering/deposition model candidate; mineral and fertility assumptions still required'})
    spatial_path=ROOT/'resolution-audit-v19.json'
    spatial=C.read(spatial_path) if spatial_path.exists() else {}
    if not spatial.get('cases') or not all(c['spatialErrorDecreases'] for c in spatial['cases']):missing.append('spatial convergence is not demonstrated for all registered comparison windows')
    joint=[]
    for epoch in ['base','evolved-2000000']:
        folder=ROOT/'continuous/vorhan-duskreach'/epoch;file=folder/'water-accelerated/baseline/hydrology.json'
        if not file.exists():missing.append('continuous '+epoch+' seasonal water result incomplete');continue
        water=C.read(file);joint.append({'epoch':epoch,'terrain':reference(folder/'height.npy','m'),'hydrologyReport':reference(file,'JSON'),'converged':water['convergence']['passed']})
        if not water['convergence']['passed']:missing.append('continuous '+epoch+' lake levels not converged')
    outlet_path=C.TASK/'story-outlets-v19/bounded-spill-valleys/water/baseline/hydrology.json';outlet=C.read(outlet_path) if outlet_path.exists() else None
    missing+=['three-seed / erosion-and-tectonic / dry-baseline-wet matrix incomplete for latest parents','global soil and sediment ledger, exact story footprints and worldwide accepted terrain assembly incomplete','new Driftmoor/Hearthstone/Verdance outlet correction still requires reconstruction of the initial parent and re-erosion']
    climate_result=None
    if climate:
        try:
            req,res=K.validate(climate,require_ready=True);climate_result={'path':str(climate),'sha256':res['climateSha256'],'requestFingerprint':C.request_fingerprint(req),'terrainFingerprint':res['terrainFingerprint']}
        except (ValueError,FileNotFoundError,KeyError) as e:missing.append('climate rejected: '+str(e))
    else:missing.append('no radiation-valid 12-14C, seasonally balanced Year 521 climate result')
    missing+=['climate-driven regional soil-water and snow fields not available','Orun aridity and agricultural story geography not validated under accepted climate','historical vegetation requires epoch-specific climate and initial soil/biomass state; Year 521 climate cannot stand in for the whole terraforming history']
    report={'version':'vegetation-input-v19','preparedUnix':time.time(),'status':'prepared candidate references; not ready for vegetation execution','vegetationReady':False,'cases':cases,'continuousNetwork':joint,'outletDiagnostic':outlet,'climate':climate_result,'missing':missing,'seasonCount':'not prescribed; native climate intervals retain orbital phase across Earth civil years','historicalClock':'Earth civil years, separate from effective geological erosion time','noVegetationMapGenerated':True}
    C.write(OUT/'manifest.json',report);C.write(C.ROOT/'foundation/warm-climate-v18/vegetation-readiness.json',{k:v for k,v in report.items() if k!='cases'})
    print({'candidateInputs':len(cases),'vegetationReady':False,'missing':missing});return report

def validate_package(path,global_height,climate_sha):
    """Execution requires a later fully accepted package, never this WIP manifest."""
    data=C.read(path)
    if not data.get('vegetationReady') or data.get('missing'):raise ValueError('Vegetation inputs have unresolved acceptance conditions')
    if data.get('globalHeightSha256')!=C.sha(global_height) or data.get('climate',{}).get('sha256')!=climate_sha:raise ValueError('Vegetation terrain/climate package lineage mismatch')
    if not data.get('historicalClimateCoverageValidated'):raise ValueError('Historical vegetation lacks verified climate coverage')
    required={'soil','soil-water','biomass','nitrogen'}
    if not required.issubset(data.get('initialState',{})):raise ValueError('Verified vegetation initial state is incomplete')
    for field,row in data['initialState'].items():
        if C.sha(row['path'])!=row['sha256']:raise ValueError('Vegetation initial field changed: '+field)
    history=data.get('climateHistory',[]);cursor=0.
    for row in history:
        if row.get('startCivilYear')!=cursor or row.get('endCivilYear',0)<=cursor:raise ValueError('Historical climate has missing or overlapping epochs')
        req,res=K.validate(row['folder'],require_ready=True)
        if res['climateSha256']!=row['sha256'] or req.get('lineage',{}).get('globalHeightSha256')!=data['globalHeightSha256']:raise ValueError('Historical climate lineage changed')
        cursor=row['endCivilYear']
    if cursor<521:raise ValueError('Climate history does not cover the simulated 0-521 civil-year interval')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--climate',type=pathlib.Path);a=p.parse_args();prepare(a.climate)
