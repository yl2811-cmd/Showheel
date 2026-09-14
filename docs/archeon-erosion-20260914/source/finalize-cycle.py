from pathlib import Path
import sys,importlib,json,shutil,hashlib,copy
sys.path.insert(0,'D:/SKBS/maps/archeon-atlas/src');X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;V=importlib.import_module('tectonics-cycle-verify')
work=X.DEFAULT;out=T.ROOT/'foundation/erosion';out.mkdir(parents=True,exist_ok=True);summary=V.inspect(work);site=X.bank_site();route=X.selected_route();river=next(f for f in T.D['rivers'] if f['id']=='ishkar');p=T.Proj(X.read(X.BASE/'aethelgard/grid.json')['projection']);old=np.array(river['geometry']['coordinates']);oxy=np.array([p(*q) for q in old]);start=np.array(p(*route[0]));join=int(np.argmin(np.linalg.norm(oxy-start,axis=1)));coords=old[:join+1].tolist()+route;widths=river['properties'].get('widthProfileM',[650]*len(old));oldwidth=np.asarray(widths);tailwidth=np.interp(np.linspace(join,len(old)-1,len(route)),np.arange(len(oldwidth)),oldwidth);tailwidth=np.clip(tailwidth,650,2800);features=[]
rb=copy.deepcopy(next(f for f in T.D['settlements'] if f['id']=='RB'));rb['geometry']['coordinates']=site['coordinates'];rb['properties'].update(candidateStatus='relocated to selected river bank anchor; urban extent and flood safety not inferred',previousCoordinates=[-10,9]);features.append(rb)
join_report=X.read(work/'ishkar-junction.json') if (work/'ishkar-junction.json').exists() else None
if join_report and join_report['passesLocalCellOverlap']:
    j=join_report['upstreamAnchorIndex'];tail=join_report['coordinates']+route[join_report['matchedLowerCourseIndex']:];coords=old[:j+1].tolist()+tail;tailwidth=np.clip(np.interp(np.linspace(j,len(oldwidth)-1,len(tail)),np.arange(len(oldwidth)),oldwidth),650,2800);join=j
rr=copy.deepcopy(river);rr['geometry']['coordinates']=coords;rr['properties'].update(widthProfileM=oldwidth[:join+1].tolist()+tailwidth.tolist(),candidateStatus='retained upstream geometry joined to selected simulated lower course',joinDistanceM=float(np.linalg.norm(oxy[join]-start)),lowerCourseSource=X.CFG['river']['sourceCase'],wholeRouteSpatialConvergence=False);features.append(rr)
if join_report:rr['properties'].update(junctionSimulation={k:v for k,v in join_report.items() if k!='coordinates'},joinDistanceM=join_report['simulatedStartGapM'],formerUnresolvedGapM=join_report['originalGapM'])
for r in T.D.get('routes',[]):
    if 'RB' in r.get('properties',{}).get('stops',[]) or 'Riverbend' in r.get('properties',{}).get('name','') or r.get('id')=='RB-SA':
        v=copy.deepcopy(r);v['properties'].update(geometryStatus='deferred pending final terrain',settlementAnchorOverrides={'RB':site['coordinates']});features.append(v)
geography={'type':'FeatureCollection','properties':{'candidateOnly':True,'formalAtlasChanged':False,'flightRouteGeometryRedrawDeferred':True},'features':features};T.savejson(out/'geography-candidate.geojson',geography);T.savejson(work/'geography-candidate.geojson',geography);T.savejson(out/'riverbend.json',site)
if (work/'local-spatial-convergence.json').exists():summary['localSpatialConvergence']=X.read(work/'local-spatial-convergence.json')
if join_report:summary['ishkarJunction']={k:v for k,v in join_report.items() if k!='coordinates'}
T.savejson(out/'verification-summary.json',summary)
lines=['# 岩层、河谷与沙地：本地候选','', '当前保存底稿为 v10，七个叙事级板块与 0.98g 保留。新一轮分别运行纯侵蚀和间歇造地，正式地图与正文未覆盖。','', '## 本轮结果','',f'- 三个种子、四个地区、两种过程：{len(summary["coarse"])} 组 16 km / 200 万有效年对照。',f'- 已完成 {len(summary["details"])} 组局部试算；各视图注明实际网格与时长。Atheria / Frontier 的 2 km 缓地核对采用 10 万年，宏观对照仍为 200 万年。','- Orun 与 Marneth 使用独立的保护地貌侵蚀试验；聚落核心和 Orun 两端保留。较新 Orun 的完整硬盖层与 Marneth 较薄的残余盖层是本轮工作假设。','- 岩石转成土砂、流水侵蚀、沉积、坡面搬移和向海输出分别记账。岩性差异加强了谷壁与台缘的选择性侵蚀。','- 初始地形的 DEM 细部与后续物理过程分开保存。DEM 使用已有美国地质调查局高程材料的裁切与旋转，不是 Archeon 实测地形。','', '## Riverbend 与海岸','',f'- Riverbend 的候选锚点移至 {site["coordinates"][0]:.6f}°, {site["coordinates"][1]:.6f}°。它距已选河道参考点约 {site["offsetM"]:.0f} m；完整城镇范围与洪水安全尚未由本轮确定。','- Ishkar 采用已选形成试验的下游河段，接入初始数值河床。历史试验的整条河仍未通过完整空间收敛，不能据此声称只有一种地质历史。','- 未受保护的既有沿海洼地允许进水，不为维持旧海岸而填高。新岸线与初始进水范围分别统计；细化海湾与河口继承父级水沙及边界高程。','- 深海床只是本轮近岸计算的外部边界假设。浏览器的海面显示在 0 m，不把这套假设当成测得的海底地形。','- 航线几何留到地形选定之后重绘。','', '## 数值与视觉核对','', '| 地区 | 过程 | 种子 | 最大累计下切 m | 最大沉积 m | 陆地增减总面积 km² |','|---|---|---:|---:|---:|---:|']
for r in summary['coarse']:
    m=r['metrics'];c=r['coast'];lines.append(f"| {r['region']} | {r['mode']} | {r['seed']} | {m['maximumCumulativeIncisionM']:.1f} | {m['maximumDepositionM']:.1f} | {c['gainedAreaKm2']+c['lostAreaKm2']:.0f} |")
lines+=['','保护核心、水沙收支和共同初始基底的核对记录在 verification-summary.json。步长检查保留整体差异与局部最大差异；个别河段的敏感性没有被平均数隐藏。','', '平缓而突出的残余体由坡度、局部落差与面积筛查，数量由结果产生；它们是进一步核对的候选，不把每个平顶片都宣称为地质上的桌山。','', '界面提供同色标俯视、1×斜视、局部剖面和过程图层。旧的平滑坡面、偏向坡脚的窗口及失败海岸方案保留在本地记录中。','', '## 边界','', '当前降雨和风是地貌筛选条件，尚未经过真实环流校核；砂质覆盖不等于已验证的沙漠边界。没有把冰盖、气候反馈、Year 521 植被或航线当作已完成内容。','', '全数值场、缓存和中间快照保留在本地。网站只读取烘焙图与预览网格。本轮不做压缩构建、提交或推送。','', '模型说明：[Landlab SPACE](https://landlab.readthedocs.io/en/latest/tutorials/landscape_evolution/space/SPACE_user_guide_and_examples.html)。']
(out/'FINDINGS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
with (out/'FINDINGS.md').open('a',encoding='utf8') as f:
    f.write('\n局部空间检查：Orun 同一岩坡从250m细化至125m和64m，10万有效年的内部高程RMS差约0.33–0.35m，相对本次微小演化量约22%，尚未达到预设10%门槛。该组作为分辨率敏感性记录，不能据此声称细微侵蚀量已经收敛。\n')
    if join_report:f.write(f"\nIshkar上游衔接已另做2km/10万年试算：从保留上游锚点最近的网格节点出发，距原锚点{join_report['simulatedStartGapM']:.0f}m，接近已选下游河道{join_report['minimumDistanceToSelectedLowerCourseM']:.0f}m；这属于当前网格内的局部连接，不替代整条河历史的空间收敛。\n")
repro='''# 本地复算

使用已保存的 Python 运行环境及 review/foundation-20260914/deps 中的 Landlab 2.11.0。基准位于 archives/geomorph-v10-before-erosion；不得用旧 v7 起点重复叠加抬升。

统一入口 tectonics-pipeline.py 支持 cycle、cycle-detail、cycle-bake、cycle-verify，另有受保护地貌与近岸试算入口。运行参数登记 --region、--seed、--mode、--mask、--base-study、--years、--out。

本轮原始结果在 review/tectonics-20260914/erosion-v12。固定种子 5210914、5210915、5210916；时间 0、100000、500000、2000000 有效模型年。Orun/Marneth 另保存10000年；缓地细化仅运行100000年。

冻结画笔在 erosion-applied-masks-20260914。parent-boundary.json 保存父级高度、流量和泥沙的逐期指纹；refinement-config.json 与 detail-plan.json 保存选中窗口。父级任一相关字段改变后应重算依赖窗口。界面画笔另存的候选有独立 job 目录，不回写旧结果。

原始几何、基底重建、素材贡献、后续抬升、侵蚀、沉积、土层和砂质覆盖分开保存。地质有效年不改写为小说年代。
''';(out/'REPRODUCE.md').write_text(repro,encoding='utf8')
for name in ['FINDINGS.md','REPRODUCE.md','verification-summary.json']:shutil.copy2(out/name,work/name)
print(json.dumps({'coarse':len(summary['coarse']),'details':len(summary['details']),'riverJoinDistanceM':rr['properties']['joinDistanceM']}))
