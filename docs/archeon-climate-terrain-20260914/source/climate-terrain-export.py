"""Bake completed studies with their actual acceptance and climate state."""
import sys,pathlib,importlib,json,time,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np
E=importlib.import_module('tectonics-export');V=importlib.import_module('landscape-export');CE=importlib.import_module('tectonics-cycle-export');L=importlib.import_module('tectonics-landscape')
OUT=C.ROOT/'foundation/climate-terrain-v15'
def run():
 OUT.mkdir(parents=True,exist_ok=True);E.OUT=OUT;regions={}
 for p in sorted((C.WORK/'regional').glob('*/5210914/*/*/*/2000/simulation.json')):
  folder=p.parent;report=C.read(p)
  if report['effectiveYears']!=2000000:continue
  g=C.read(folder/'grid.json');sid=g['id'];mode=report['mode'];scenario=report['scenario'];gain=report['enhancement'];prefix=f'{sid}-{mode}-{scenario}-g{gain:g}';key=C.fingerprint({'simulation':C.sha(p),'height':C.sha(folder/'height.npy'),'exporter':C.sha(__file__)})
  cached=OUT/(prefix+'.json')
  if cached.exists() and C.read(cached).get('fingerprint')==key:case=C.read(cached)
  else:
   initial=np.load(folder/'initial.npy');kind=np.load(folder/'kind-0.npy');stages=[]
   E.write_image(prefix+'-initial.png',E.elevation(initial),kind)
   baseline_mesh=E.height_mesh(prefix+'-initial.f32',initial,420)
   for year in C.CFG['timesYears']:
    zfile=folder/f'height-{year}.npy'
    if not zfile.exists():continue
    z=np.load(zfile);k=np.load(folder/f'kind-{year}.npy');depth=np.load(folder/f'lake-depth-{year}.npy');waterkind=k.copy();waterkind[depth>.05]=200
    name=f'{prefix}-{year}';E.write_image(name+'-height.png',E.elevation(z),k);E.write_image(name+'-water.png',E.elevation(z),waterkind)
    erosion=np.load(folder/f'erosion-{year}.npy');deposition=np.load(folder/f'deposition-{year}.npy');E.write_image(name+'-change.png',E.signed(z-initial,250),k)
    stage={'year':year,'label':f'{year:,} 有效年','height':name+'-height.png','ground':name+'-height.png','water':name+'-water.png','change':name+'-change.png','mesh':E.height_mesh(name+'.f32',z,420),'stats':E.stats(z,initial,k,g['stepM'])}
    stages.append(stage)
   q=np.load(folder/'discharge.npy');rec=np.load(folder/'receiver.npy');depth=np.load(folder/'lake-depth.npy');features=V.lines(g,q,np.where(depth>.05,-1,rec),threshold=2e9)
   for f in features:f['properties'].pop('screen',None)
   C.write(OUT/(prefix+'-rivers.geojson'),{'type':'FeatureCollection','properties':{'scenarioOnly':True,'climateValidated':False,'sourceHeightSha256':C.sha(folder/'height.npy')},'features':features})
   case={'seed':5210914,'mode':mode,'scenario':scenario,'gain':gain,'baseline':prefix+'-initial.png','baselineMesh':baseline_mesh,'stages':stages,'checks':report,'riverVector':prefix+'-rivers.geojson','fingerprint':key,'accepted':report['passed'] and report['retentionPassed'] and report['waterConvergence']['passed'],'climateValidated':False}
   C.write(cached,case)
  if sid not in regions:regions[sid]={'id':sid,'title':next(x['region'] for x in C.CFG['provinces'] if x['id']==sid)+' · '+sid,'grid':g,'width':g['width'],'height':g['height'],'baseline':case['baseline'],'baselineMesh':case['baselineMesh'],'candidates':[],'markers':CE.markers(g,L.X.bank_site()),'group':g['region']}
  regions[sid]['candidates'].append(case);gc.collect()
 status=C.read(C.WORK/'study-status.json') if (C.WORK/'study-status.json').exists() else {}
 manifest={'version':C.CFG['version'],'createdUnix':time.time(),'bakeBase':'foundation/climate-terrain-v15/','regions':list(regions.values()),'scenarios':{'baseline':'基准历史情景','dry':'偏干历史情景','wet':'偏湿历史情景'},'enhancements':[1,1.5,2],'scope':'Completed regional geological candidates. Current global circulation and humidity remain WIP.','globalClimateReady':False,'vegetationReady':False,'completedRegionalRuns':len(status.get('completed',[]))}
 C.write(OUT/'manifest.json',manifest);(OUT/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(manifest,ensure_ascii=False,default=C.T.json_scalar)+';',encoding='utf8')
 progress={'version':C.CFG['version'],'terrain':'区域侵蚀与增强对照运行中' if status.get('status')=='running' else status.get('status','准备中'),'completedRegionalRuns':len(status.get('completed',[])),'circulation':'WIP · 辐射与输入资料待验证','humidity':'WIP','vegetation':'WIP','routes':'WIP','updatedUnix':time.time()}
 C.write(C.ROOT/'world-rebuild/simulation-progress.json',progress)
 print('V15 BAKE',len(regions),'regions',sum(len(r['candidates']) for r in regions.values()),'candidates; global climate remains WIP',flush=True)
if __name__=='__main__':run()
