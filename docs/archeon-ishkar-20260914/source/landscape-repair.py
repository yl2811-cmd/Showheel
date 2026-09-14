"""Author-marked legacy-lake and frozen-plateau baseline reconstruction.

Only candidate bed geometry changes. Real mountains, coastline and scene
cores remain controls; later hydrology determines water surfaces.
"""
import pathlib,sys,importlib,json
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');np=T.np
from scipy.ndimage import gaussian_filter,distance_transform_edt
ANNOTATIONS=T.BASE_WORK/'landscape-v13/five-area-review/annotations.geojson'
def read():return json.loads(ANNOTATIONS.read_text(encoding='utf8')) if ANNOTATIONS.exists() else {'features':[]}
def reconstruct(z,g,kind,hard,legacy):
    result=z.copy();total=np.zeros_like(z);ownership=np.zeros_like(z);records=[];dx=g['stepM'];land=(kind>=30)&(kind!=80);coast=distance_transform_edt(land)*dx
    for feature in read()['features']:
        marked=T.raster([feature['geometry']],g);artifacts=marked&((legacy>0)|(kind==200))&(z<3200)&land&~hard
        if not artifacts.any():continue
        outside=distance_transform_edt(~artifacts)*dx;inside=distance_transform_edt(artifacts)*dx
        weight=T.ease((inside+24000)/64000)*(1-T.ease(outside/64000));weight*=T.ease((coast-16000)/32000)*T.ease(distance_transform_edt(~hard)*dx/48000)*T.ease((3800-z)/1000)
        # Reconstruct the regional bed from unmasked flanks. This removes the
        # inherited lake datum and polygon perimeter before adding geological
        # sources; fixed old water levels are never inserted as river sinks.
        available=land.astype(float)*(1-weight)*(kind!=200)*T.ease((3200-z)/1200);sigma=max(.5,100000/dx);den=gaussian_filter(available,sigma);target=gaussian_filter(z*available,sigma)/np.maximum(den,1e-6);target=np.where(den>.02,target,gaussian_filter(np.minimum(z,2200),sigma))
        # Screened harmonic relaxation retains the surrounding gradient rather
        # than installing a new constant-elevation fill surface.
        bed=z*(1-weight)+target*weight
        for _ in range(120):
            average=(np.roll(bed,1,0)+np.roll(bed,-1,0)+np.roll(bed,1,1)+np.roll(bed,-1,1))*.25
            bed=z*(1-weight)+weight*(.85*average+.15*target)
        change=(bed-result)*weight;change[hard|~land]=0;result+=change;total+=change;ownership=np.maximum(ownership,weight)
        records.append({'id':feature['id'],'markedCells':int(marked.sum()),'rebuiltCells':int(np.count_nonzero(abs(change)>.01)),'maximumChangeM':float(abs(change).max()),'coreDeltaM':float(abs(change[hard]).max(initial=0)),'method':'flank-conditioned screened harmonic bed, with high-massif and coastal taper','oldWaterSurfaceNotFixed':True})
    return result,total,ownership,records

def sources(g,seed,gain):
    rng=np.random.default_rng(seed+220919);p=T.Proj(g['projection']);result=[]
    for feature in read()['features']:
        xy=np.array([p(*q) for q in feature['geometry']['coordinates'][0]]);lo=xy.min(axis=0);hi=xy.max(axis=0);candidates=[]
        for i in range(16):
            x,y=lo+(hi-lo)*rng.uniform(.15,.85,2);angle=rng.uniform(-.2,.2)+(.4 if feature['id'].startswith(('north','west','orun')) else 1.1)
            candidates.append({'id':feature['id']+'-source-'+str(i),'province':feature['id'],'family':str(rng.choice(['bench','tilted','basin'],p=[.5,.3,.2])),'xy':[float(x),float(y)],'center':list(p(x,y,inverse=True)),'lengthM':float(rng.uniform(30000,85000)),'widthM':float(rng.uniform(16000,40000)),'reliefM':float(rng.uniform(140,360)*gain),'angleRadians':float(angle),'phase':float(rng.uniform(-3,3)),'startYear':int(rng.uniform(0,900000)),'durationYears':int(rng.uniform(180000,600000)),'initialFraction':.45,'scale':'medium','authorisedRepairRegion':feature['id']})
        result+=candidates[:round(8*gain)]
    return result
