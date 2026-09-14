"""One user-painted candidate, in its own job directory; never overwrite a run."""
import pathlib,sys,json,shutil,importlib,hashlib,os
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');E=importlib.import_module('tectonics-export');R=importlib.import_module('tectonics-refine')
jobid=sys.argv[1];folder=T.WORK/'jobs'/jobid;job=json.loads((folder/'job.json').read_text(encoding='utf8'));original=T.WORK;region=job['region'];seed=job['seed'];config=dict(T.C);config['gridStepM']=job.get('gridM',16000);config['seeds']=[seed];config['timesYears']=[0,100000] if job['years']==100000 else [0,100000,500000,2000000]
config['faultDensity']=job.get('faultDensity',config.get('faultDensity',1.5))
config['magmatism']['intensity']=job.get('magmaticIntensity',1)
def stage_key(stage):
    m=json.loads((folder/'mask.json').read_text(encoding='utf8'));layers=list(m['layers'].values()) if 'layers' in m else [m]
    relevant={'tectonic','fault-bend','magmatism','protection'} if stage=='initial' else {'tectonic','fault-bend','magmatism','protection','water','weathering','aeolian','planation','rock-strength','soil'}
    sliced=[{'grid':v.get('grid'),'width':v['width'],'height':v['height'],'fields':{k:a for k,a in v['fields'].items() if k in relevant and any(x!=(0 if k=='protection' else 1) for x in a)}} for v in layers]
    cfg=json.loads(json.dumps(config));cfg.pop('ecology',None);cfg.pop('climate',None)
    if stage=='initial':cfg.pop('timesYears',None);cfg.pop('stepYears',None)
    inputs={p:T.sha(T.ROOT/p) for p in json.loads((T.BASE_WORK/'source-snapshot.json').read_text(encoding='utf8'))['hashes'] if p!='foundation/manifest.json'}
    sliced=[v for v in sliced if v['fields']]
    climate={'resultSha256':T.sha(pathlib.Path(T.REAL_CLIMATE)/'result.json'),'couplingSha256':T.sha(T.ROOT/'src/tectonics-coupling.py')} if T.REAL_CLIMATE and stage=='erosion' else None
    return hashlib.sha256(json.dumps({'stage':stage,'region':region,'seed':seed,'config':cfg,'mask':sliced,'code':T.LOADED_CODE_HASHES,'base':inputs,'climate':climate},sort_keys=True).encode()).hexdigest()
def link_or_copy(source,destination):
    try:os.link(source,destination)
    except OSError:shutil.copy2(source,destination)
def transfer(source,destination):
    shutil.copytree(source,destination,dirs_exist_ok=True,copy_function=shutil.copy2)
if region in config['regions']:
    work=folder/'work';work.mkdir();T.WORK=work;T.MASK=folder/'mask.json';T.C=config;T.savejson(work/'run-config.json',config)
    records=[]
    for stage in ['initial','erosion']:
        digest=stage_key(stage);cache=original/'stage-cache'/stage/digest;reuse=(cache/'complete.json').exists()
        if reuse:transfer(cache/region,work/region)
        elif stage=='initial':T.prepare(region);T.initial(region,seed)
        else:T.evolve(region,seed)
        if not reuse:
            cache.mkdir(parents=True,exist_ok=True);shutil.copytree(work/region,cache/region,dirs_exist_ok=True,copy_function=link_or_copy);T.savejson(cache/'complete.json',{'stage':stage,'digest':digest,'job':jobid})
        records.append({'stage':stage,'cacheKey':digest,'reused':reuse});T.log(('REUSED ' if reuse else 'COMPUTED ')+stage)
    T.savejson(work/'stage-dependencies.json',records)
    E.WORK=work;E.OUT=folder/'bake';E.OUT.mkdir();E.T.WORK=work;E.T.C={**config,'regions':{region:config['regions'][region]}};E.diagnostics=lambda:None;E.export()
else:
    refinement=next(r for r in config['refinements'] if r['id']==region);T.MASK=folder/'mask.json';R.T.MASK=T.MASK;R.run(refinement,seed,dtmax=10000,end=job['years'],suffix='-'+jobid);source=original/'refined'/(region+'-'+jobid);E.OUT=folder/'bake';E.OUT.mkdir();E.export_nested_job(source,refinement,seed)
manifest=json.loads((folder/'bake/manifest.json').read_text(encoding='utf-8'));manifest['bakeBase']='/tectonics-jobs/'+jobid+'/';(folder/'bake/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');(folder/'bake/data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(manifest,ensure_ascii=False)+';',encoding='utf-8')
T.log('BAKED '+jobid)
