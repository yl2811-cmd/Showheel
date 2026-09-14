"""Drain inherited island basins along their minimax spill paths; preserve scene cores."""
import pathlib,sys,importlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;H=importlib.import_module('landscape-water');L=importlib.import_module('tectonics-landscape')
from scipy.ndimage import distance_transform_edt
BASE=C.TASK/'assembled/keld/5210914/erosion-only/baseline';OUT=C.TASK/'terrain-completion-v18/keld-outlet-repair-v2'

def run():
    g=C.read(BASE/'grid.json');z=np.load(BASE/'height.npy').astype(float);old=z.copy();kind=np.load(BASE/'kind.npy');land=(kind>=30)&(kind!=80);hard=np.load(BASE/'protected.npy')>0
    # The old 20 km marker disks were numerical envelopes, not registered
    # building polygons. This independent candidate allows a river corridor
    # in their outer parts and preserves a 5 km inner scene exactly.
    legacy_hard=hard.copy();scene=np.zeros(z.shape,bool);adjustable=np.zeros(z.shape,bool)
    for site in [s for s in T.D['settlements'] if s['id'] in ['SH','TI']]:
        dist=T.distance(g,site['geometry']['coordinates']);scene|=dist<=5000;adjustable|=(dist>5000)&(dist<24000)
    hard=(hard&~adjustable)|scene
    filled,order,rec,slope=T.F.flood_route(z,land,g['stepM']);records=[]
    for site in [s for s in T.D['settlements'] if s['id'] in ['SH','TI']]:
        x,y=T.Proj(g['projection'])(*site['geometry']['coordinates']);r=round((g['ymax']-y)/g['stepM']);c=round((x-g['xmin'])/g['stepM']);node=r*g['width']+c;nodes=[];seen=set()
        while node>=0 and node not in seen:
            seen.add(node);nodes.append(node);node=int(rec[node])
        rows=np.asarray(nodes)//g['width'];cols=np.asarray(nodes)%g['width'];distance=np.r_[0,np.cumsum(np.hypot(np.diff(rows),np.diff(cols))*g['stepM'])]
        target=(z[r,c]-30)*(1-distance/max(distance[-1],1));target=np.minimum.accumulate(np.minimum(target,z.ravel()[nodes]));path=np.zeros(z.shape,bool);path[rows,cols]=True;bed=np.zeros(z.shape);bed[rows,cols]=target
        d,ix=distance_transform_edt(~path,sampling=g['stepM'],return_indices=True);valleybed=bed[tuple(ix)];weight=1-T.ease(d/12000);weight[hard|~land]=0
        delta=np.minimum(valleybed-z,0)*weight;z+=delta
        protected_path=hard[rows,cols];records.append({'id':site['id'],'name':site['properties']['name'],'routeLengthKm':float(distance[-1]/1000),'oldGroundM':float(old[r,c]),'oldSpillM':float(filled[r,c]),'maximumProtectedPathBedM':float(old[rows[protected_path],cols[protected_path]].max(initial=-1e9)),'maximumExcavationM':float(-delta.min()),'excavationKm3':float(-delta.sum()*g['stepM']**2/1e9),'pathCoordinates':np.column_stack(T.Proj(g['projection'])(g['xmin']+cols*g['stepM'],g['ymax']-rows*g['stepM'],inverse=True)).tolist()})
    for name,a in {'height':z,'kind':kind,'soil':np.load(BASE/'soil.npy'),'outlet-incision':old-z,'protected':hard}.items():C.save_array(OUT/(name+'.npy'),a.astype('uint8') if name in ['kind','protected'] else a.astype('float32'))
    C.write(OUT/'grid.json',g);C.write(OUT/'construction.json',{'parentHeightSha256':C.sha(BASE/'height.npy'),'method':'lowest spill paths with monotonic downstream valley floors and 12 km smooth side slopes; geological outlet reconstruction, not additional dated erosion','protectedMaximumChangeM':float(abs(z-old)[hard].max(initial=0)),'innerSceneMaximumChangeM':float(abs(z-old)[scene].max(initial=0)),'oldEnvelopeMaximumChangeM':float(abs(z-old)[legacy_hard].max(initial=0)),'sceneEnvelopeAssumption':'5 km inner scene preserved; former 20 km marker buffer is not surveyed buildings or farmland. Exact scene footprint acceptance remains pending.','coastlineChanged':False,'waterHidden':False,'sites':records})
    print('KELD OUTLET RECONSTRUCTION', [{k:v for k,v in r.items() if k!='pathCoordinates'} for r in records],flush=True)
    del filled,order,rec,slope,old;gc.collect()
    hyd=H.run(z,land,g['stepM'],L.proxy(z,g,kind),cycles=20,converge=True,max_cycles=1000)
    for name in ['discharge','receiver','lake-depth','lake-level','lake-occurrence','lake-min-depth','lake-max-depth','wetness']:C.save_array(OUT/'water/baseline'/(name+'.npy'),hyd[name].astype('int32') if name=='receiver' else hyd[name].astype('float32'))
    check=importlib.import_module('climate-acceptance').named_cores(g,z,kind,hyd)
    C.write(OUT/'water/baseline/grid.json',g);C.write(OUT/'water/baseline/hydrology.json',{'convergence':hyd['convergence'],'maximumWaterRelativeError':hyd['maxWaterRelativeError'],'namedCoreCheck':check,'climateValidated':False,'lakes':hyd['lakes']});print('KELD REPAIR WATER',hyd['convergence'],check,flush=True)

if __name__=='__main__':run()
