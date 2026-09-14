"""Verify the bounded connection scope without claiming geological completion."""
import pathlib,sys,importlib,json
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('landscape-connect');L=C.L;np=L.np

def verify():
 rows=[]
 for f in sorted((L.WORK/'connected').glob('*/*')):
  if not (f/'hydrology.json').exists():continue
  g=L.read(f/'grid.json');source=L.WORK/'connection-base'/str(g['seed']);request=L.read(f/'request.json');hyd=L.read(f/'hydrology.json');story=L.read(f/'story-geography.json');conn=L.read(source/'connection.json')
  assert request['base']==L.T.sha(source/'height.npy'),'Stale parent height'
  z=np.load(source/'height.npy');k=np.load(source/'kind.npy');d=np.load(f/'lake-depth.npy');q=np.load(f/'discharge.npy');r=np.load(f/'receiver.npy');catch=np.load(f/'ishkar-catchment.npy');assert all(np.isfinite(a).all() for a in [z,d,q]);assert d.min()>=0 and q.min()>=0;assert r.min()>=-1 and r.max()<r.size
  assert hyd['maxWaterRelativeError']<1e-8
  assert conn['negativeLandCellsAfter']==0
  targets={'Frontier','Atheria','Crestline','Thornfield','Coppergate','Cliffwatch','Windbreak','Riverbend'};connected={s['name'] for s in conn['sites'] if s['centerOnIshkarCatchment']};assert targets<=connected
  assert not next(s['centerOnIshkarCatchment'] for s in conn['sites'] if s['name']=='Millhaven')
  source_cells=np.flatnonzero(catch.ravel()&(q.ravel()>0));terminal=(r.ravel()<0)&catch.ravel();outflow=float(q.ravel()[terminal].sum()/31557600)
  rows.append({'seed':g['seed'],'scenario':request['scenario'],'gridM':g['stepM'],'numericPassed':True,'waterRelativeError':hyd['maxWaterRelativeError'],'IshkarOutflowM3s':outflow,'flowingIshkarCells':len(source_cells),'storyScreenPassed':story['passed'],'floodedCoreScreens':[s['name'] for s in story['sites'] if s['corePermanentlyFlooded']],'convergence':hyd['convergence'],'geologicalYearsAdvanced':0})
 expected={(5210914,s) for s in ['dry','baseline','wet']}|{(s,'baseline') for s in [5210915,5210916]};found={(r['seed'],r['scenario']) for r in rows}
 result={'scope':L.read(L.WORK/'SCOPE.json'),'matrixComplete':expected<=found,'runs':rows,'numericPassed':bool(rows) and all(r['numericPassed'] for r in rows),'allStoryScreensPassed':bool(rows) and all(r['storyScreenPassed'] for r in rows),'allSeasonalCyclesConverged':bool(rows) and all(r['convergence']['passed'] for r in rows),'limitations':['2 km topology is not a street-scale flood-depth prediction','Shared outlet membership does not require the main channel to pass through the Riverbend town centre','Unconverged remote lakes remain explicitly unselected','No real-climate, vegetation or flight-route update in this pass']}
 L.save(L.WORK/'connection-verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':verify()
