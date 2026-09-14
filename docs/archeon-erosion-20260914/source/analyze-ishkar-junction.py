import sys,importlib
sys.path.insert(0,'D:/SKBS/maps/archeon-atlas/src');X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;out=X.DEFAULT/'erosion-only/refined/ishkar-junction-2km';g=X.read(out/'grid.json');p=T.Proj(g['projection']);record=X.read(X.DEFAULT/'ishkar-junction.json');old=next(f['geometry']['coordinates'] for f in T.D['rivers'] if f['id']=='ishkar');anchor=np.array(p(*old[record['upstreamAnchorIndex']]));xx,yy=T.mesh(g);points=np.column_stack([xx.ravel(),yy.ravel()]);rec=np.load(out/'receiver.npy').ravel();i=int(np.linalg.norm(points-anchor,axis=1).argmin());path=[]
while i not in path:
    path.append(i);j=int(rec[i])
    if j<0 or j==i:break
    i=j
pts=points[path];target=np.array([p(*q) for q in X.selected_route()]);distance,index=X.cKDTree(target).query(pts);k=int(np.argmin(distance));gap=float(np.linalg.norm(pts[0]-anchor));record.update(simulatedStartGapM=gap,minimumDistanceToSelectedLowerCourseM=float(distance[k]),matchedLowerCourseIndex=int(index[k]),passesLocalCellOverlap=bool(gap<=g['stepM']*1.414214 and distance[k]<=3000),coordinates=np.column_stack(p(pts[:k+1,0],pts[:k+1,1],inverse=True)).tolist(),startSelection='nearest physical node to the preserved upstream river anchor; no search for a more favourable high-discharge node');T.savejson(X.DEFAULT/'ishkar-junction.json',record);print({k:v for k,v in record.items() if k!='coordinates'})
