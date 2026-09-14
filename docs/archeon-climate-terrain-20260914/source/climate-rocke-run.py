"""Evidence-gated Linux ROCKE-3D execution, with no proxy fallback."""
import pathlib,sys,importlib,argparse,subprocess,time,json,re
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');K=importlib.import_module('climate-contract');TIME=importlib.import_module('climate-time')
def preflight(folder):
 folder=pathlib.Path(folder);missing=[]
 for name in ['request.json','native-inputs.json','radiation-validation.json','driver.json']:
  if not (folder/name).exists():missing.append(name)
 if missing:return {'passed':False,'missing':missing,'status':'input preparation incomplete','planetaryGCMExecuted':False}
 request=C.read(folder/'request.json');native=C.read(folder/'native-inputs.json');radiation=C.read(folder/'radiation-validation.json');driver=C.read(folder/'driver.json');errors=[]
 for row in native.get('files',[]):
  p=folder/row['file']
  if not p.exists() or C.sha(p)!=row['sha256']:errors.append('native input missing/changed: '+row['file'])
 required={'TOPO','AIC','GIC','SOIL','VEG','RVR','OHT','OCNML'}
 if not required.issubset({r.get('role') for r in native.get('files',[])}):errors.append('planetary surface, atmosphere, river or mixed-layer inputs incomplete')
 if not native.get('planetaryBoundaryValidationPassed'):errors.append('native planetary boundary checks not passed')
 if not radiation.get('passed') or not set(C.CFG['climate']['requiredRadiativeSpecies']).issubset(radiation.get('validatedSpecies',[])):errors.append('measured radiation calibration incomplete')
 for key in ['columnComparison','gcmTransferCheck','zeroGasRegression']:
  row=radiation.get(key,{})
  if not row.get('file') or not (folder/row['file']).exists() or C.sha(folder/row['file'])!=row.get('sha256'):errors.append('radiation evidence missing: '+key)
 try:TIME.calendar(request.get('calendar'))
 except ValueError as e:errors.append(str(e))
 if driver.get('distribution')!='ArcheonSim' or not re.fullmatch(r'ARCHEON_[A-Z0-9_]+',driver.get('runId','')):errors.append('invalid isolated runtime identity')
 if request.get('model')!='ROCKE-3D' or request.get('modelVersion')!='2.0':errors.append('unregistered climate engine version')
 try:request_hash=C.request_fingerprint(request)
 except ValueError as e:errors.append(str(e));request_hash=None
 return {'passed':not errors,'errors':errors,'requestFingerprint':request_hash,'planetaryGCMExecuted':False}
def execute(folder):
 folder=pathlib.Path(folder);check=preflight(folder);C.write(folder/'preflight.json',check)
 if not check['passed']:raise RuntimeError('ROCKE-3D not launched: '+json.dumps(check,ensure_ascii=False))
 driver=C.read(folder/'driver.json');run_id=driver['runId'];cmd=['wsl.exe','--distribution','ArcheonSim','--user','archeon','--exec','/opt/archeon/modelE2_planet_2.0/exec/runE',run_id,'-np',str(min(8,max(1,int(driver.get('ncpus',8)))))]
 state={'status':'running','started':time.time(),'command':cmd,'requestFingerprint':check['requestFingerprint'],'balanced':False};C.write(folder/'status.json',state)
 with (folder/'runtime.log').open('a',encoding='utf8') as log:code=subprocess.call(cmd,stdout=log,stderr=subprocess.STDOUT)
 state.update(status='model process completed; output validation required' if code==0 else 'failed',exitCode=code,finished=time.time());C.write(folder/'status.json',state)
 # This wrapper never promotes successful process exit to climate acceptance.
 return state
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--folder',type=pathlib.Path,default=C.WORK/'climate-inputs/5210914/screen');a.add_argument('--execute',action='store_true');q=a.parse_args()
 if q.execute:print(json.dumps(execute(q.folder)))
 else:r=preflight(q.folder);C.write(q.folder/'preflight.json',r);print(json.dumps(r))
