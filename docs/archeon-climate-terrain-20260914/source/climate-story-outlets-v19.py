"""Minimal monotone valley tests for newly discovered flooded settlement markers."""
import pathlib,sys,importlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;S=importlib.import_module('climate-water-spinup');L=importlib.import_module('tectonics-landscape')
from scipy.ndimage import distance_transform_edt
ROOT=C.TASK/'terrain-completion-v18';BASE=ROOT/'continuous/vorhan-duskreach/evolved-2000000';OUT=C.TASK/'story-outlets-v19';IDS=['DR','HE','VE']

def run():
    g=C.read(BASE/'grid.json');source=C.sha(BASE/'height.npy');dx=g['stepM'];folder=OUT/'bounded-spill-valleys';z=np.load(BASE/'height.npy').astype(float);old=z.copy();kind=np.load(BASE/'kind.npy');land=(kind>=30)&(kind!=80);p=T.Proj(g['projection']);sites=[f for f in T.D['settlements'] if f['id'] in IDS];records=[]
    # Stored hydrological receivers collapse wet lakes to a representative.
    # Excavation must instead follow every adjacent bed cell through the basin.
    filled,order,receiver,slope=T.F.flood_route(z,land,dx);del filled,order,slope;gc.collect()
    for site in sites:
        x,y=p(*site['geometry']['coordinates']);r=round((g['ymax']-y)/dx);c=round((x-g['xmin'])/dx);node=r*g['width']+c;chain=[];seen=set()
        while node>=0 and node not in seen:
            seen.add(node);chain.append(node);node=int(receiver[node])
        rows=np.asarray(chain)//g['width'];cols=np.asarray(chain)%g['width'];path_distance=np.r_[0,np.cumsum(np.hypot(np.diff(rows),np.diff(cols))*dx)]
        assert np.all(np.maximum(abs(np.diff(rows)),abs(np.diff(cols)))==1),'Nonadjacent terrain route'
        # Bound the hydraulic spill below the town. Native deep pockets stay
        # available as lakes: their floors must not force every later saddle
        # down to the deepest encountered point.
        native=z.ravel()[chain];ceiling=native[0]-10-.00001*path_distance
        target=np.minimum(native,ceiling)
        pad=8;r0=max(0,int(rows.min())-pad);r1=min(g['height'],int(rows.max())+pad+1);c0=max(0,int(cols.min())-pad);c1=min(g['width'],int(cols.max())+pad+1);box=(slice(r0,r1),slice(c0,c1));path=np.zeros(z[box].shape,bool);bed=np.zeros_like(z[box]);path[rows-r0,cols-c0]=True;bed[rows-r0,cols-c0]=target
        d,idx=distance_transform_edt(~path,sampling=dx,return_indices=True);weight=1-T.ease(d/12000);bg={**g,'xmin':g['xmin']+c0*dx,'ymax':g['ymax']-r0*dx,'width':c1-c0,'height':r1-r0};protected=np.zeros(weight.shape,bool)
        for f in T.D['settlements']:
            if f['geometry']['type']=='Point':protected|=T.distance(bg,f['geometry']['coordinates'])<=5000
        weight[protected|~land[box]]=0;delta=np.minimum(bed[tuple(idx)]-z[box],0)*weight
        maximum=float(-delta.min());volume=float(-delta.sum()*dx*dx/1e9)
        if maximum>800:
            C.write(folder/'failure.json',{'site':site['id'],'maximumLoweringM':maximum,'proposedRemovedKm3':volume,'reason':'exceeds bounded local reconstruction; not selected'})
            C.save_array(folder/'failed-proposed-change.npy',delta)
            raise ValueError('Candidate would cut more than 800m: '+site['id']+' '+str(maximum))
        z[box]+=delta;records.append({'id':site['id'],'name':site['properties']['name'],'routeKm':float(path_distance[-1]/1000),'maximumLoweringM':maximum,'removedKm3':volume,'inner5kmSceneProxyPreserved':True,'pathCoordinates':np.column_stack(p(g['xmin']+cols*dx,g['ymax']-rows*dx,inverse=True)).tolist()});print('MINIMAL OUTLET', {k:v for k,v in records[-1].items() if k!='pathCoordinates'},flush=True);gc.collect()
    for name,a in [('height',z),('kind',kind),('soil',np.load(BASE/'soil.npy')),('base-reconstruction',z-old)]:C.save_array(folder/(name+'.npy'),a.astype('uint8') if name=='kind' else a.astype('float32'))
    C.write(folder/'grid.json',g);C.write(folder/'construction.json',{'sourceHeightSha256':source,'codeSha256':C.sha(__file__),'routeUsesAdjacentBedCells':True,'comparisonParents':[str(OUT/'minimal-valleys'),str(OUT/'minimal-valleys-connected')],'method':'upper spill grade below settlement, preserving lower native lake floors; compare excavation cost with strict monotone-bed candidate','sites':records,'coastlineChanged':False,'sceneProxyRadiusKm':5,'exactSceneFootprintsUnknown':True,'waterHidden':False,'scope':'drainage reconstruction on final candidate to diagnose spill obstruction; applying the correction to the initial parent and re-eroding remain required','millionYearReerosionCompleted':False})
    del old,receiver;gc.collect();initial=np.load(BASE/'water-accelerated/baseline/lake-depth.npy').astype(float);water=folder/'water/baseline'
    def progress(row):C.write(water/'progress.json',row);print('OUTLET WATER',row,flush=True)
    h=S.run(z,land,dx,L.proxy(z,g,kind),initial_depth=initial,max_cycles=5000,checkpoint=water/'spinup-checkpoint.npz',progress=progress)
    for name in ['discharge','receiver','lake-depth','lake-level','lake-occurrence','lake-min-depth','lake-max-depth','wetness']:C.save_array(water/(name+'.npy'),h[name].astype('int32') if name=='receiver' else h[name].astype('float32'))
    checks=[]
    for site in sites:
        x,y=p(*site['geometry']['coordinates']);r=round((g['ymax']-y)/dx);c=round((x-g['xmin'])/dx);checks.append({'id':site['id'],'name':site['properties']['name'],'lakeDepthM':float(h['lake-depth'][r,c]),'maximumLakeDepthM':float(h['lake-max-depth'][r,c]),'permanentLake':bool(h['lake-depth'][r,c]>.05 and h['lake-occurrence'][r,c]>.99)})
    report={'sourceHeightSha256':C.sha(folder/'height.npy'),'convergence':h['convergence'],'maximumWaterRelativeError':h['maxWaterRelativeError'],'sites':checks,'allMarkersDry':all(v['maximumLakeDepthM']<.05 for v in checks),'climateValidated':False,'reerosionPending':True};C.write(water/'hydrology.json',report);print('OUTLET CANDIDATE DONE',report,flush=True)

if __name__=='__main__':run()
