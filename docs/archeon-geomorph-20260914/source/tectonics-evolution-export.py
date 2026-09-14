"""Publish small baked views only; all raw numerical fields stay in review/."""
import pathlib,sys,importlib,json,math,argparse,shutil
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('tectonics-continuation');T=C.T;np=T.np;E=importlib.import_module('tectonics-export');W=importlib.import_module('tectonics-world')
from scipy.ndimage import zoom
import matplotlib.pyplot as plt
from matplotlib import font_manager
font=pathlib.Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False

def render_region(work,id,spec,out,crop=None):
 pg=json.loads((work/id/'grid.json').read_text(encoding='utf8'));g=pg.copy();prefix=id;title=spec['title'];kind=np.load(work/id/'kind.npy');protect=np.load(work/id/'protected.npy')
 if crop:
  prefix,title,center,width,height=crop;cx,cy=T.Proj(g['projection'])(*center);g.update(id=prefix,width=round(width/g['stepM'])+1,height=round(height/g['stepM'])+1,xmin=cx-width/2,ymax=cy+height/2)
 def sub(a,order=1):return T.sample(a,pg,g,order) if crop else a
 kind=sub(kind,0);dk=E.down(kind,1600,0);protected=sub(protect,0);E.write_image(prefix+'-protected.png',np.where((E.down(protected,1600,0)>0)[:,:,None],[56,147,133],[226,214,185])+np.zeros((*dk.shape,3)),dk)
 item={'id':prefix,'title':title,'maskRegion':id,'grid':g,'width':dk.shape[1],'height':dk.shape[0],'protected':prefix+'-protected.png','candidates':[],'markers':[]}
 p=T.Proj(g['projection'])
 for f in E.D_markers():
  x,y=p(*f['geometry']['coordinates']);u=(x-g['xmin'])/((g['width']-1)*g['stepM']);v=(g['ymax']-y)/((g['height']-1)*g['stepM'])
  if 0<u<1 and 0<v<1:item['markers'].append({'name':f['properties']['name'],'position':[u,v]})
 for seed in C.CFG['seeds']:
  folder=work/id/str(seed)
  if not (folder/'height.npy').exists():continue
  kind=sub(np.load(folder/'kind.npy'),0);dk=E.down(kind,1600,0)
  fullbase,_=C.base_surface(id,seed,pg);base=sub(fullbase);ini=sub(np.load(folder/'initial.npy'));cand={'seed':seed,'stages':[],'faults':[],'baseline':f'{prefix}-{seed}-saved.png','baselineMesh':E.height_mesh(f'{prefix}-{seed}-saved.f32',base)}
  E.write_image(cand['baseline'],E.elevation(E.down(base)),dk)
  for f in json.loads((folder/'faults.json').read_text(encoding='utf8')):
   points=[[(p(*q)[0]-g['xmin'])/((g['width']-1)*g['stepM']),(g['ymax']-p(*q)[1])/((g['height']-1)*g['stepM'])] for q in f['coordinates']]
   if any(0<=u<=1 and 0<=v<=1 for u,v in points):cand['faults'].append({**f,'screen':points})
  for year in C.CFG['geologyYears']:
   f=folder/f'height-{year}.npy'
   if not f.exists():continue
   z=sub(np.load(f));small=E.down(z);name=f'{prefix}-{seed}-{year}';E.write_image(name+'-height.png',E.elevation(small),dk);E.write_image(name+'-ground.png',E.ground(small,g['stepM']*z.shape[0]/small.shape[0]),dk);E.write_image(name+'-change.png',E.signed(E.down(z-base)),dk)
   cand['stages'].append({'year':year,'label':'新增地貌基底' if year==0 else f'续演 {year/10000:g} 万有效年','height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','mesh':E.height_mesh(name+'.f32',z),'stats':E.stats(z,base,kind,g['stepM'])})
  for field in ['erosion','deposition','pond-depth','discharge']:
   a=E.down(sub(np.load(folder/(field+'.npy'))));name=f'{prefix}-{seed}-{field}.png';rgb=plt.get_cmap('viridis')(np.clip(np.log10(1+a)/12,0,1))[:,:,:3]*255 if field=='discharge' else E.signed(a,600);E.write_image(name,rgb,dk);cand[field]=name
  cand['checks']={k:v for k,v in json.loads((folder/'simulation.json').read_text(encoding='utf8')).items() if k!='history'};cand['construction']=json.loads((folder/'construction.json').read_text(encoding='utf8'));item['candidates'].append(cand)
 if not item['candidates']:return None
 first=item['candidates'][0];item.update(baseline=first['baseline'],revised=first['baseline'],baselineMesh=first['baselineMesh'],revisedMesh=first['baselineMesh'])
 return item

def world(work):
 # Assemble all checked regions first, then compare each seed to its own v7.
 for seed in C.CFG['seeds']:
  W.run(work,seed);folder=work/'global'/str(seed);frozen=C.FROZEN/'global'/str(seed)
  if frozen.exists():shutil.copy2(frozen/'height.npy',folder/'baseline.npy');shutil.copy2(frozen/'kind.npy',folder/'baseline-kind.npy')
 E.WORK=work;item=E.world_view()
 for cand in item['candidates']:
  seed=cand['seed'];folder=work/'global'/str(seed);b=np.load(folder/'baseline.npy');k=np.load(folder/'baseline-kind.npy');name=f'world-{seed}-saved';E.write_image(name+'.png',E.elevation(E.down(b)),E.down(k,1600,0));cand['baseline']=name+'.png';cand['baselineMesh']=E.height_mesh(name+'.f32',b,700)
  stage=cand['stages'][0];z=np.load(folder/'height.npy');kind=np.load(folder/'kind.npy');stage['stats']=E.stats(z,b,kind,item['grid']['stepM'],np.load(folder/'cell-area.npy'));stage['label']='新地貌与极地 · 200 万有效年续演';E.write_image(f'world-{seed}-change.png',E.signed(E.down(z-b)),E.down(kind,1600,0))
 item['title']='全球 · 新地貌与极地';return item

def ci_views(work):
 result=[];folder=work/'polar-ci/5210914'
 if not (folder/'sites.json').exists():return result
 for site in json.loads((folder/'sites.json').read_text(encoding='utf8')):
  path=folder/site['id']/'heat-1GW'
  if not (path/'grid.json').exists():continue
  g=json.loads((path/'grid.json').read_text(encoding='utf8'));g['id']=site['id'];base=np.load(folder/site['id']/'no-engineering/surface-height-521.npy');kind=np.full(base.shape,70);prefix=site['id'];E.write_image(prefix+'-saved.png',E.elevation(base),kind)
  item={'id':site['id'],'title':next(r['title'].split(' · ')[0] for r in C.CFG['polarRegions'] if r['id']==site['region'])+' · CI 遗址','maskRegion':site['region'],'grid':g,'width':g['width'],'height':g['height'],'baseline':prefix+'-saved.png','revised':prefix+'-saved.png','baselineMesh':E.height_mesh(prefix+'-saved.f32',base),'protected':None,'markers':[{'name':'旧聚变与释气设施','position':[.5,.5]}],'candidates':[],'civilClock':True}
  cand={'seed':5210914,'stages':[],'faults':[]}
  for year in C.CFG['civilYears']:
   z=np.load(path/f'surface-height-{year}.npy');ice=np.load(path/f'ice-thickness-{year}.npy');water=np.load(path/f'water-depth-{year}.npy');name=f'{prefix}-{year}';E.write_image(name+'-height.png',E.elevation(z),kind);col=E.ground(z,g['stepM']);snow=np.clip(ice/5,0,1)[:,:,None];col=col*(1-snow)+np.array([211,225,223])*snow;wet=np.clip(water/.5,0,1)[:,:,None];col=col*(1-wet)+np.array([66,124,147])*wet;E.write_image(name+'-ground.png',col,kind);E.write_image(name+'-change.png',E.signed(z-base,120),kind)
   cand['stages'].append({'year':year,'label':f'Year {year} · '+('设施已停机' if year>=110 else '工程衰退期'),'height':name+'-height.png','ground':name+'-ground.png','change':name+'-change.png','mesh':E.height_mesh(name+'.f32',z),'stats':E.stats(z,base,kind,g['stepM'])})
  item['candidates']=[cand];result.append(item)
 return result

def plots(work,out):
 summaries={}
 source=work/'polar-ci/5210914/summary.json'
 if source.exists():
  ci=json.loads(source.read_text(encoding='utf8'));summaries['ci']={k:v for k,v in ci.items() if k not in ['cases','gases']};fig,ax=plt.subplots(1,2,figsize=(13,4),layout='constrained',facecolor='#eee8d8')
  for v in ci['cases']:
   if v['case']!='heat-1GW':continue
   years=[int(y) for y in v['snapshots']];vol=[v['snapshots'][str(y)]['iceVolumeKm3'] for y in years];ax[0].plot(years,vol,label=v['site'].replace('ci-polar-',''))
  ax[0].set(xlabel='CI 年历',ylabel='窗口内陆冰体积 / km³',title='停机后：融水外流与再冻结');ax[0].legend(fontsize=7)
  gas=json.loads((work/'polar-ci/5210914/gas-history.json').read_text(encoding='utf8'));ref=next(v for v in gas if v['engineeringEnabled'] and v['lifetimeScale']==1)
  for k in ['SF6','N2O']:
   vals=[v['massKg'][k] for v in ref['history']];ax[1].plot([v['year'] for v in ref['history']],np.asarray(vals)/max(vals),label=k)
  ax[1].axvline(50,color='#857660',ls='--');ax[1].set(xlabel='CI 年历',ylabel='各气体相对峰值库存',title='地球寿命参照 · 尚非 Archeon 光化学');ax[1].legend();fig.savefig(out/'polar-ci-history.png',dpi=135);plt.close(fig)
 source=work/'ishkar-history/screen-summary.json'
 if source.exists():
  rows=json.loads(source.read_text(encoding='utf8'));fig,ax=plt.subplots(1,3,figsize=(14,4),layout='constrained',facecolor='#eee8d8')
  for j,h in enumerate(C.CFG['riverHistory']['histories']):
   data=np.array([[next(v['maximumIncisionM'] for v in rows if v['history']==h and v['formationYears']==t and v['runoffMultiplier']==r) for r in [.3,1,3]] for t in [3000000,12000000,30000000]])
   im=ax[j].imshow(data,vmin=0,vmax=max(v['maximumIncisionM'] for v in rows),cmap='YlOrBr');ax[j].set(title={'antecedent':'先有河后抬升','fracture-assisted':'断裂辅助','late-breach':'高原先形成'}[h],xticks=[0,1,2],xticklabels=['0.3×','1×','3×'],yticks=[0,1,2],yticklabels=['3 Myr','12 Myr','30 Myr'],xlabel='径流试算')
   for rr in range(3):
    for cc in range(3):ax[j].text(cc,rr,f'{data[rr,cc]:.0f} m',ha='center',va='center',fontsize=8)
  fig.colorbar(im,ax=ax,label='最大累计下切量');fig.savefig(out/'ishkar-screen.png',dpi=135);plt.close(fig)
  summaries['ishkarScreen']={'cases':len(rows),'open':sum(v['hydrologicallyOpen'] for v in rows),'targetCompatible':sum(v['targetCompatible'] for v in rows),'status':'一维筛查，二维验证另列'}
 results=sorted((work/'ishkar-history').glob('two-d-summary-*.json'))
 if results:summaries['ishkar2D']={p.stem:json.loads(p.read_text(encoding='utf8')) for p in results}
 coast=sorted((work/'ishkar-coast').glob('antecedent-*-w480000'))
 if coast:
  folder=min(coast,key=lambda p:json.loads((p/'result.json').read_text(encoding='utf8'))['gridStepM']);r=json.loads((folder/'result.json').read_text(encoding='utf8'));g=json.loads((folder/'grid.json').read_text(encoding='utf8'));z=np.load(folder/'height.npy');b=np.load(folder/'restored-barrier.npy');kind=np.load(folder/'kind.npy');rr=np.array(r['pathRows']);cc=np.array(r['pathColumns']);dx=g['stepM'];extent=[g['xmin']/1000,(g['xmin']+(g['width']-1)*dx)/1000,(-g['ymax']+(g['height']-1)*dx)/1000,-g['ymax']/1000]
  fig,ax=plt.subplots(2,2,figsize=(13,9),layout='constrained',facecolor='#eee8d8')
  for axis,field,title in zip(ax[0],[b,z],['未预挖峡谷的抬升目标','自由排水与侵蚀的终态']):
   rgb=E.elevation(field);rgb[kind==0]=[35,56,65];rgb[[0,-1],:]=[35,56,65];rgb[:,[0,-1]]=[35,56,65];axis.imshow(rgb,extent=extent);axis.set(title=title,xlabel='沿崖方向 / km',ylabel='向海岸方向 / km')
  ax[0,1].plot((g['xmin']+cc*dx)/1000,(-g['ymax']+rr*dx)/1000,color='#1fe8ff',lw=1.3,label='模拟河道');ax[0,1].legend(fontsize=8)
  s=np.r_[0,np.cumsum(np.hypot(np.diff(rr),np.diff(cc))*dx)]/1000
  ax[1,0].plot(s,b[rr,cc],color='#a49885',label='同一路径上的完整抬升目标');ax[1,0].plot(s,z[rr,cc],color='#376351',label='侵蚀后河床');ax[1,0].set(xlabel='顺流距离 / km',ylabel='海拔 / m',title='沿真实模拟河道的纵剖面（纵轴放大）');ax[1,0].legend(fontsize=8)
  ax[1,1].plot(s,z[rr,cc]/1000,color='#376351');ax[1,1].set(xlabel='顺流距离 / km',ylabel='海拔 / km',title='同一剖面 · 水平与垂直 1×');ax[1,1].set_aspect('equal',adjustable='box')
  fig.suptitle(f"Ishkar · {r['formationYears']/1e6:g} Myr 抬升 · 径流 {r['runoffMultiplier']:g}× · {dx/1000:g} km 网格\n未使用现今河床锁定；该降雨条件仍是地貌试算输入",fontsize=13);fig.savefig(out/'ishkar-coast-comparison.png',dpi=145);plt.close(fig)
  summaries['ishkarCoast']={k:v for k,v in r.items() if k not in ['historyLedger','pathRows','pathColumns']}
 T.savejson(out/'study-results.json',summaries)

def detail_views(work):
 result=[];plan=work/'detail-plan.json'
 if not plan.exists():return result
 for spec in json.loads(plan.read_text(encoding='utf8')):
  folder=work/'refined'/spec['id'];report=folder/'simulation.json'
  if not report.exists() or not json.loads(report.read_text(encoding='utf8')).get('passed'):continue
  item=E.nested_item(folder,spec);parent=json.loads((folder/'grid.json').read_text(encoding='utf8'))['region'];title=T.C['regions'][parent]['title'].split(' · ')[0]
  item.update(title=('Atheria / Frontier 缓地' if spec['id']=='atheria-frontier-quiet' else title+' · 地貌细部')+f" · {spec['stepM']:g} m",group='细部',maskRegion=parent)
  for st in item['candidates'][0]['stages']:st['label']='细部初始' if st['year']==0 else f"细部续演 {st['year']/10000:g} 万有效年"
  result.append(item)
 return result

def river_views(work,out):
 result=[];available=[p for p in (work/'ishkar-coast').glob('*w480000') if (p/'result.json').exists()];folders=[]
 for history in C.CFG['riverHistory']['histories']:
  options=[p for p in available if p.name.startswith(history+'-')]
  if options:folders.append(min(options,key=lambda p:(json.loads((p/'result.json').read_text(encoding='utf8'))['gridStepM'],json.loads((p/'result.json').read_text(encoding='utf8'))['timeStepYears'])))
 for folder in folders:
  report=json.loads((folder/'result.json').read_text(encoding='utf8'));g=json.loads((folder/'grid.json').read_text(encoding='utf8'));kind=np.load(folder/'kind.npy')[1:-1,1:-1];base=np.load(folder/'restored-barrier.npy')[1:-1,1:-1];z=np.load(folder/'height.npy')[1:-1,1:-1];prefix='ishkar-'+report['history'];gg={**g,'id':prefix,'width':g['width']-2,'height':g['height']-2,'xmin':g['xmin']+g['stepM'],'ymax':g['ymax']-g['stepM']};E.write_image(prefix+'-before.png',E.elevation(base),kind)
  routes=json.loads((folder/'route.geojson').read_text(encoding='utf8'));a=g['worldAffine'];p=T.Proj(g['projection']);markers=[]
  for f in routes['features']:
   if f['geometry']['type']!='Point':continue
   xx,yy=p(*f['geometry']['coordinates']);d=np.array([xx,yy])-a['origin'];u=float(d@np.array(a['across']));v=float(d@np.array(a['downstream']));pos=[(u-gg['xmin'])/((gg['width']-1)*g['stepM']),(-v-gg['ymax'])/-((gg['height']-1)*g['stepM'])]
   current='current' in f['properties']['name'];markers.append({'name':'Riverbend 原位' if current else '河道最近点 · 选址参考','position':pos,'labelOffset':[-96,-12] if current else [8,16]})
  title={'antecedent':'Ishkar · 先成河再抬升','late-breach':'Ishkar · 高原先形成','fracture-assisted':'Ishkar · 断裂辅助'}[report['history']];item={'id':prefix,'title':title,'group':'河流试验','readOnly':True,'baselineLabel':'未预挖峡谷的抬升目标','grid':gg,'width':kind.shape[1],'height':kind.shape[0],'baseline':prefix+'-before.png','revised':prefix+'-before.png','baselineMesh':E.height_mesh(prefix+'-before.f32',base,700),'markers':markers,'candidates':[]}
  cand={'seed':5210914,'label':f"{report['formationYears']/1e6:g} Myr / 径流 {report['runoffMultiplier']:g}×",'faults':[],'stages':[],'checks':{k:v for k,v in report.items() if k not in ['historyLedger','pathRows','pathColumns']}}
  for name,field in [('height',z),('ground',z),('change',z-base),('erosion',np.load(folder/'erosion.npy')[1:-1,1:-1])]:
   rgb=E.ground(field,g['stepM']) if name=='ground' else E.signed(field,3200) if name in ['change','erosion'] else E.elevation(field);E.write_image(prefix+'-'+name+'.png',rgb,kind)
  route={'name':'Ishkar simulated','mode':'extension','screen':[[(c-1)/(gg['width']-1),(r-1)/(gg['height']-1)] for r,c in zip(report['pathRows'],report['pathColumns'])]};cand['routes']=[route]
  cand['stages']=[{'year':report['formationYears']+C.CFG['riverHistory']['postUpliftYears'],'label':'形成试验终态 · 非故事年历','height':prefix+'-height.png','ground':prefix+'-ground.png','change':prefix+'-change.png','mesh':E.height_mesh(prefix+'.f32',z,700),'stats':E.stats(z,base,kind,g['stepM'])}];cand['erosion']=prefix+'-erosion.png';item['candidates']=[cand];result.append(item)
  shutil.copy2(folder/'route.geojson',out/(prefix+'-route.geojson'))
  if report['history']=='antecedent':
   import copy
   dxy=np.array(p(*report['closestOrunRouteCoordinates']))-a['origin'];cu=float(dxy@np.array(a['across']));cv=float(dxy@np.array(a['downstream']))+40000;dx=g['stepM'];c0=max(0,round((cu-100000-gg['xmin'])/dx));c1=min(gg['width'],c0+round(200000/dx)+1);r0=max(0,round((cv-120000+gg['ymax'])/dx));r1=min(gg['height'],r0+round(240000/dx)+1);sl=(slice(r0,r1),slice(c0,c1));crop=copy.deepcopy(item);cp='ishkar-crossing';crop.update(id=cp,title='Ishkar · 穿崖段与 Riverbend',width=c1-c0,height=r1-r0);crop['grid']={**gg,'id':cp,'width':c1-c0,'height':r1-r0,'xmin':gg['xmin']+c0*dx,'ymax':gg['ymax']-r0*dx};crop['baseline']=cp+'-before.png';crop['revised']=crop['baseline'];crop['baselineMesh']=E.height_mesh(cp+'-before.f32',base[sl],700)
   E.write_image(crop['baseline'],E.elevation(base[sl]),kind[sl]);crop['markers']=[{**m,'position':[(m['position'][0]*(gg['width']-1)-c0)/(c1-c0-1),(m['position'][1]*(gg['height']-1)-r0)/(r1-r0-1)]} for m in markers]
   ccand=crop['candidates'][0];ccand['routes'][0]['screen']=[[(u*(gg['width']-1)-c0)/(c1-c0-1),(v*(gg['height']-1)-r0)/(r1-r0-1)] for u,v in route['screen']]
   st=ccand['stages'][0]
   for name,field in [('height',z[sl]),('ground',z[sl]),('change',(z-base)[sl]),('erosion',np.load(folder/'erosion.npy')[1:-1,1:-1][sl])]:
    rgb=E.ground(field,dx) if name=='ground' else E.signed(field,3200) if name in ['change','erosion'] else E.elevation(field);E.write_image(cp+'-'+name+'.png',rgb,kind[sl]);st[name]=cp+'-'+name+'.png'
   st['mesh']=E.height_mesh(cp+'.f32',z[sl],700);st['stats']=E.stats(z[sl],base[sl],kind[sl],dx);ccand['erosion']=cp+'-erosion.png';result.append(crop)
 return result

def build_page(out):
 s=(T.ROOT/'tectonics.html').read_text(encoding='utf8');s=s.replace('foundation/tectonics/data.js','foundation/evolution/data.js').replace('<title>Archeon · 岩层与长风</title>','<title>Archeon · 河流、极地与旧日热源</title>')
 s=s.replace('LANDSCAPE STUDY 02','LANDSCAPE STUDY 03').replace('<a href="foundation.html">上一轮地形对照</a>','<a href="tectonics.html">已封存的上轮候选 ↗</a>')
 s=s.replace('岩层抬起，流水留下谷地','河流穿过岩层，冰缘留下旧日热源').replace('从 Orun 的弯折与长背坡，看到其他大陆的倾斜断块、高原和山群。先用粗网格看形状，再沿时间看流水与岩层怎样改变地面。','当前版本已完整封存。新候选补入分散台地、岩脊与极地山群；Ishkar 的穿崖形成另做试验，南北极 CI 在衰亡后留下融水沟与重新冻结的冰缘。')
 s=s.replace('<option value="baseline">上一轮底稿</option>','<option value="baseline">已保存的同种子版本</option>')
 extra='<option value="relief-density">中小地貌分布密度</option><option value="relief-amplitude">中小地貌起伏</option><option value="ci-placement">CI 站点分布</option><option value="ci-heat">CI 入冰热量</option><option value="ci-resource">CI 原料可达性</option><option value="ci-footprint">CI 干预范围</option>'
 s=s.replace('<option value="water">流水侵蚀</option>',extra+'<option value="water">流水侵蚀</option>')
 s=s.replace('<option value="2000000">200 万年完整运行</option>','<option value="2000000">200 万有效年续演</option>')
 s=s.replace('<details><summary>Orun 高原修订对照</summary>','<section class="study-results"><h2>Ishkar 与极地 CI 的独立试验</h2><p>地质形成时间与 Year 0–521 分别计算。极地冰厚、气体产率和气候为试算假设；Year 521 无主动供热或主动释气。</p><img src="foundation/evolution/ishkar-screen.png" alt="Ishkar 三种形成历史的初步下切对照"><img src="foundation/evolution/polar-ci-history.png" alt="CI 停机后的冰量及遗留气体库存"><p><a href="foundation/evolution/FINDINGS.md">结果、失败案例与验证范围 ↗</a></p></section><details><summary>Orun 高原修订对照</summary>')
 # The active deliverable is terrain. Civil engineering and climate remain
 # independent local experiments, without premature meltwater/vegetation claims.
 s=s.replace('Archeon · 河流、极地与旧日热源','Archeon · 大陆、极地与穿崖河流').replace('河流穿过岩层，冰缘留下旧日热源','高原展开，河流寻找出路').replace('当前版本已完整封存。新候选补入分散台地、岩脊与极地山群；Ishkar 的穿崖形成另做试验，南北极 CI 在衰亡后留下融水沟与重新冻结的冰缘。','已封存的地形旁，加入中小台地、岩脊与两极山群。沿同一色标比较百万年级侵蚀；Ishkar 另用完整海岸边界检验能否穿过 Orun。')
 start=s.index('<section class="study-results">');end=s.index('<details><summary>Orun 高原修订对照',start)
 s=s[:start]+'<section class="study-results"><h2>Ishkar 的形成与路线</h2><p>对比先有河再抬升、断裂辅助和高原先形成。河流允许自行转弯，现今河床不锁定。海岸窗口的结果与旧窄窗口分开保存；Riverbend 的近河位置仍是候选。</p><img src="foundation/evolution/ishkar-coast-comparison.png" alt="Ishkar 的实际河道与纵剖面对照"><p><a href="foundation/evolution/FINDINGS.md">结果、失败案例与验证范围 ↗</a> · <a href="foundation/evolution/verification-summary.json">核对记录 ↗</a></p></section>'+s[end:]
 s=s.replace('<a href="foundation/tectonics/manifest.json">烘焙清单</a>','<a href="foundation/evolution/manifest.json">烘焙清单</a>').replace('<a href="foundation/tectonics/FINDINGS.md">结果与验证</a>','<a href="foundation/evolution/FINDINGS.md">结果与验证</a>')
 s=s.replace('<a href="evolution.html">新地貌、极地与 CI 试验 ↗</a>','')
 (T.ROOT/'evolution.html').write_text(s,encoding='utf8')
 old=(T.ROOT/'tectonics.html').read_text(encoding='utf8')
 if 'href="evolution.html"' not in old:old=old.replace('<span>LANDSCAPE STUDY 02</span>','<a href="evolution.html">新地貌、极地与 CI 试验 ↗</a><span>LANDSCAPE STUDY 02</span>');(T.ROOT/'tectonics.html').write_text(old,encoding='utf8')

def export(work,out=None):
 out=out or T.ROOT/'foundation/evolution';out.mkdir(parents=True,exist_ok=True);C.open_work(work);E.OUT=out;E.WORK=work;E.T.C=T.C;E.T.WORK=work;items=[]
 for id,spec in T.C['regions'].items():
  if (work/id/'grid.json').exists():
   item=render_region(work,id,spec,out)
   if item:items.append(item)
 if (work/'aethelgard/5210914/height.npy').exists():
  for crop in [('atheria-frontier','Atheria 与 Frontier · 宽谷与缓地',[.3,27],750000,650000),('orun-ramp','Orun · 长背坡与水口',[0,10],2500000,2000000)]:items.append(render_region(work,'aethelgard',T.C['regions']['aethelgard'],out,crop))
 if len(items)>=10:items.insert(0,world(work))
 items.extend(detail_views(work));items.extend(river_views(work,out));plots(work,out)
 m={'version':C.CFG['version'],'studyKey':'evolution','status':'candidate','bakeBase':'foundation/evolution/','seeds':C.CFG['seeds'],'regions':items,'sourceWork':str(work),'frozenBase':str(C.FROZEN),'clocks':{'geology':'effective continuation years','civil':'CI engineering and ecological years'},'atmosphereModel':'preliminary forcing; ExoPlaSim trace-gas transfer not yet validated'}
 T.savejson(out/'manifest.json',m);(out/'data.js').write_text('window.ARCHEON_TECTONICS='+json.dumps(m,ensure_ascii=False,default=T.json_scalar)+';',encoding='utf8');build_page(out);T.log('EVOLUTION BAKED '+str(len(items))+' views');return m
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=C.DEFAULT);ap.add_argument('--out',type=pathlib.Path);a=ap.parse_args();export(a.work,a.out)
