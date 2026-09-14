"""An immutable browser-painted continuation job, with stage-specific reuse."""
import pathlib,sys,importlib,json,shutil,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('tectonics-continuation');T=C.T;E=importlib.import_module('tectonics-evolution-export');CI=importlib.import_module('tectonics-polar-ci')
jobid=sys.argv[1];folder=T.BASE_WORK/'preview-v2/jobs'/jobid;job=json.loads((folder/'job.json').read_text(encoding='utf8'));work=folder/'work';mask=folder/'mask.json';C.open_work(work,mask);C.record_sources(work);region=job['region'];seed=job['seed'];records=[]
if job.get('process','').startswith('ci-'):
 for r in C.CFG['polarRegions']:shutil.copytree(C.DEFAULT/r['id'],work/r['id'])
 records.append({'stage':'geological terrain','reused':True,'reason':'Only civil CI controls changed; geological surfaces inherited byte-for-byte','parent':str(C.DEFAULT)})
 CI.run(work,seed,mask);records.append({'stage':'polar CI','reused':False})
else:
 C.run_region(region,seed,job.get('gridM',16000),job['years'],mask);records.append({'stage':'regional construction and downstream erosion','reused':False,'base':str(C.FROZEN)})
T.savejson(work/'stage-dependencies.json',records)
out=folder/'bake';m=E.export(work,out);m['bakeBase']='/tectonics-jobs/'+jobid+'/';T.savejson(out/'manifest.json',m);(out/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(m,ensure_ascii=False,default=T.json_scalar)+';',encoding='utf8');T.log('BAKED EVOLUTION '+jobid)
