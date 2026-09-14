"""Audit and export the shared network without resampling its flow topology."""
import pathlib,sys,importlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np;E=importlib.import_module('tectonics-export');V=importlib.import_module('landscape-export')
from scipy.ndimage import label,find_objects
from rasterio.features import shapes
from affine import Affine
ROOT=C.TASK/'terrain-completion-v18/continuous/vorhan-duskreach';OUT=C.ROOT/'foundation/terrain-completion-v18'

def lake_vectors(g,z,d,occ):
    lab,n=label(d>.05,np.ones((3,3),int));boxes=find_objects(lab);stats={};p=T.Proj(g['projection']);features=[]
    for index,box in enumerate(boxes,1):
        if box is None:continue
        mask=lab[box]==index;depth=d[box][mask];freq=occ[box][mask]
        stats[index]={'areaKm2':float(mask.sum()*g['stepM']**2/1e6),'volumeM3':float(depth.astype(float).sum()*g['stepM']**2),'surfaceM':float(np.median(z[box][mask]+depth)),'maximumDepthM':float(depth.max()),'seasonalWetFraction':float(freq.mean()),'state':'perennial-in-scenario' if freq.min()>.99 else 'seasonal-in-scenario','gridM':g['stepM'],'notRealClimateValidated':True}
    def convert(coords):
        if isinstance(coords[0],(float,int)):return list(p(*coords,inverse=True))
        return [convert(v) for v in coords]
    transform=Affine(g['stepM'],0,g['xmin']-g['stepM']/2,0,-g['stepM'],g['ymax']+g['stepM']/2)
    for geom,index in shapes(lab.astype('int32'),mask=lab>0,transform=transform):features.append({'type':'Feature','id':'lake-'+str(int(index)),'geometry':{'type':geom['type'],'coordinates':convert(geom['coordinates'])},'properties':stats[int(index)]})
    return features

def run():
    E.OUT=OUT;rows=[]
    for epoch in ['base','evolved-2000000']:
        folder=ROOT/epoch;water=folder/'water-accelerated/baseline';report=water/'hydrology.json'
        if not report.exists():continue
        h=C.read(report);g=C.read(folder/'grid.json');height_hash=C.sha(folder/'height.npy')
        if h['sourceHeightSha256']!=height_hash:raise ValueError('Water/height lineage mismatch')
        name='joint-'+epoch;manifest=OUT/(name+'.json');key=C.fingerprint({'height':height_hash,'water':C.sha(report),'code':C.sha(__file__)})
        if manifest.exists() and C.read(manifest).get('fingerprint')==key:rows.append(C.read(manifest));continue
        z=np.load(folder/'height.npy',mmap_mode='r');kind=np.load(folder/'kind.npy',mmap_mode='r');d=np.load(water/'lake-depth.npy',mmap_mode='r');occ=np.load(water/'lake-occurrence.npy',mmap_mode='r');maximum=np.load(water/'lake-max-depth.npy',mmap_mode='r');q=np.load(water/'discharge.npy',mmap_mode='r');rec=np.load(water/'receiver.npy',mmap_mode='r');p=T.Proj(g['projection']);sites=[]
        for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
            if f['geometry']['type']!='Point':continue
            x,y=p(*f['geometry']['coordinates']);r=round((g['ymax']-y)/g['stepM']);c=round((x-g['xmin'])/g['stepM'])
            if not (0<=r<g['height'] and 0<=c<g['width']) or kind[r,c]<30:continue
            sites.append({'id':f['id'],'name':f.get('properties',{}).get('name',f['id']),'heightM':float(z[r,c]),'maximumLakeDepthM':float(maximum[r,c]),'permanentWaterAtMarker':bool(d[r,c]>.05 and occ[r,c]>.99),'exactFootprintRegistered':False})
        rivers=V.lines(g,q,np.where(d>.05,-1,rec));lakes=lake_vectors(g,z,d,occ)
        for f in rivers:f['properties'].pop('screen',None)
        meta={'heightSha256':height_hash,'gridM':2000,'continuousVorhanDuskreachNetwork':True,'candidateOnly':True,'climateValidated':False,'converged':h['convergence']['passed']}
        for suffix,features in [('rivers',rivers),('lakes',lakes)]:C.write(OUT/(name+'-'+suffix+'.geojson'),{'type':'FeatureCollection','properties':meta,'features':features})
        small=E.down(z,1800);kd=E.down(kind,1800,0);E.write_image(name+'-height.png',E.elevation(small),kd)
        rgb=E.elevation(small).copy();watermask=E.down(d,1800)>.05;rgb[watermask]=[148,196,202];E.write_image(name+'-water.png',rgb,kd)
        result={'fingerprint':key,**meta,'epoch':epoch,'height':name+'-height.png','waterPreview':name+'-water.png','rivers':name+'-rivers.geojson','lakes':name+'-lakes.geojson','riverFeatures':len(rivers),'lakeFeatures':len(lakes),'maximumWaterRelativeError':h['maximumWaterRelativeError'],'convergence':h['convergence'],'sites':sites,'permanentlyFloodedMarkers':[v['id'] for v in sites if v['permanentWaterAtMarker']],'terrainAccepted':False,'soilAndSedimentGlobalLedgerAccepted':False,'seasonality':'coherent synthetic annual rainfall phase; not modern orbital-climate forcing'}
        C.write(manifest,result);rows.append(result);print('JOINT AUDIT/EXPORT',epoch,len(rivers),len(lakes),result['permanentlyFloodedMarkers'],flush=True);gc.collect()
    C.write(OUT/'joint-manifest.json',{'candidates':rows,'worldDefaultChanged':False,'climate':'WIP'});return rows

if __name__=='__main__':run()
