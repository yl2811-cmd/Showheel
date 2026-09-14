"""Immutable browser mask job on the registered saved base, never on v7."""
import pathlib,sys,importlib,json,shutil
sys.path.insert(0,str(pathlib.Path(__file__).parent));X=importlib.import_module('tectonics-cycle');T=X.T;E=importlib.import_module('tectonics-cycle-export');D=importlib.import_module('tectonics-cycle-detail')
jobid=sys.argv[1];folder=T.BASE_WORK/'preview-v2/jobs'/jobid;job=X.read(folder/'job.json');mask=folder/'mask.json';work=folder/'work';mode=job.get('mode','episodic');region=job['region'];seed=job['seed'];target=work/mode;X.setup(target,mask);X.record(target)
if job.get('gridM',16000)==16000:
    X.run_region(target,region,seed,mode,16000,job['years'],mask)
else:
    source=X.DEFAULT/mode;shutil.copytree(source/region,target/region,dirs_exist_ok=True);plan=X.read(X.DEFAULT/'detail-plan.json');spec=next((s for s in plan if s['id']==job.get('viewId') and s['mode']==mode),None)
    if spec is None:
        data=X.read(mask);layers=list(data.get('layers',{}).values()) or [data];layer=next((v for v in layers if v.get('viewId')==job.get('viewId')),layers[-1]);g=layer['grid'];np=T.np;a=np.array(layer['fields'].get(job['process'],[1]*(layer['height']*layer['width']))).reshape(layer['height'],layer['width']);weight=np.abs(a-(0 if job['process']=='protection' else 1));rows,cols=np.indices(a.shape);sw=max(1e-9,float(weight.sum()));u=float((cols*weight).sum()/sw)/max(1,a.shape[1]-1);v=float((rows*weight).sum()/sw)/max(1,a.shape[0]-1);x=g['xmin']+u*(g['width']-1)*g['stepM'];y=g['ymax']-v*(g['height']-1)*g['stepM'];center=list(T.Proj(g['projection'])(x,y,inverse=True));spec={'id':region+'-painted-2km','parent':region,'center':center,'widthKm':256,'stepM':2000,'title':'画笔区域 · 2 km','mode':mode,'continuationCatalog':True,'erosionCycle':True}
    # Registered ancestry is copied with all transient forcing snapshots. Only
    # the painted child is run; its upstream source remains explicitly recorded.
    parent=spec['parent']
    while parent not in X.REGIONS:
        shutil.copytree(source/'refined'/parent,target/'refined'/parent,dirs_exist_ok=True);parent=next(s['parent'] for s in plan if s['id']==parent and s['mode']==mode)
    D.execute(target,spec,job['years'],min(5000,spec['stepM']*10),mask);T.savejson(work/'detail-plan.json',[spec])
T.savejson(target/'stage-dependencies.json',{'base':str(X.BASE),'maskSha256':T.sha(mask),'process':job['process'],'region':region,'mode':mode,'upstreamParentResultsReused':job.get('gridM')==2000,'downstreamProductsInvalidated':True,'routesDeferred':True})
out=folder/'bake';m=E.export(work,out);m['bakeBase']='/tectonics-jobs/'+jobid+'/';T.savejson(out/'manifest.json',m);(out/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(m,ensure_ascii=False,default=T.json_scalar)+';',encoding='utf8');T.log('CYCLE PAINTED '+jobid)
