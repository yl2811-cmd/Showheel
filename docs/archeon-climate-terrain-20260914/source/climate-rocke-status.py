"""Audit executable, spectral and input evidence without declaring climate."""
import pathlib,sys,importlib,json,re
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common')
def run():
 rt=C.WORK/'runtime';log=rt/'rocke-sf6-build.log';compiled=log.exists() and 'linking ok' in log.read_text(encoding='utf8',errors='replace')
 bridge=C.read(rt/'sf6-bridge.json');bridge['compiled']=compiled;C.write(rt/'sf6-bridge.json',bridge)
 spectral=[]
 for p in (rt/'nasa-spectra/spectral_files').rglob('*'):
  if not p.is_file() or p.suffix in ['.nc','.tgz','.gz']:continue
  try:
   with p.open('r',encoding='ascii',errors='ignore') as f:head=f.read(6000).split('*END',1)[0]
  except OSError:continue
  if 'Summary of spectral data' not in head:continue
  absorber_section=head.split('List of indexing numbers and absorbers.',1)[-1].split('Listing of continuum',1)[0]
  absorbers=[{'index':int(m[0]),'identifier':int(m[1]),'name':m[2].strip()} for m in re.findall(r'^\s*(\d+)\s+(\d+)\s+([^\r\n]+)',absorber_section,re.M)]
  spectral.append({'path':str(p.relative_to(rt)),'sf6':any(a['identifier']==104 for a in absorbers),'absorbers':absorbers,'sha256':C.sha(p)})
 files=C.read(rt/'benchmark-inputs.json')['files'];missing=[r['file'] for r in files if 'error' in r]
 status={'engine':'ROCKE-3D','version':'2.0','runtime':'ArcheonSim Ubuntu 24.04','compiledWithSOCRATES':compiled,'sf6BridgeCompiled':compiled,'earthBenchmarkExecuted':False,'planetaryGCMExecuted':False,'validatedSF6Spectra':False,'downloadedSpectralTables':len(spectral),'sf6TablesFound':[r for r in spectral if r['sf6']],'unavailableBenchmarkInputs':missing,'radiationValidation':False,'climateReady':False,'vegetationReady':False,'blockers':['NASA initialization data server unreachable from Windows and Linux','GEISA data component returned HTTP 403; HITRAN measured data requires authorized access','Measured SF6/background column comparison and zero-gas GCM regression not completed'],'scope':'Compilation and input preparation only; no planetary climate output or fitted temperature claimed'}
 ptb=rt/'ptb-sf6/manifest.json'
 if ptb.exists():
  measured=C.read(ptb);status['publicSF6Measurements']={'source':measured['sourceDOI'],'files':len(measured['spectra']),'measurementAuditPassed':measured['measuredSpectrumAuditPassed'],'temperatureCoverageK':measured['temperatureCoverageK'],'fullAtmosphericTableValidated':False}
  status['blockers'][1]='PTB measured SF6 at 296K acquired; cold upper-atmosphere coverage and SOCRATES absorption-table validation remain incomplete'
 C.write(rt/'runtime-status.json',status);C.write(rt/'spectral-inventory.json',spectral);print(json.dumps({k:status[k] for k in ['compiledWithSOCRATES','downloadedSpectralTables','validatedSF6Spectra','planetaryGCMExecuted','climateReady']}),flush=True);return status
if __name__=='__main__':run()
