"""Spherical-area global context, assembled from checked regional candidates."""
import sys,pathlib,importlib,json,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');np=T.np

def global_grid(step=16000):
    nx=round(2*np.pi*T.C['radiusM']/step);ny=nx//2;dx=2*np.pi*T.C['radiusM']/nx
    return {'id':'world','region':'world','width':nx,'height':ny,'stepM':dx,'xmin':-np.pi*T.C['radiusM']+dx/2,'ymax':np.pi*T.C['radiusM']/2-dx/2,'projection':T.Proj(proj='eqc',R=T.C['radiusM']).srs,'pixelRegistration':'cell centres','nominalStepM':step}

def run(work,seed):
    T.WORK=work;g=global_grid();out=work/'global'/str(seed);out.mkdir(parents=True,exist_ok=True);base,kind=T.native(g);basekind=kind.copy();z=base.copy();p=T.Proj(g['projection']);xx,yy=T.mesh(g);lon,lat=p(xx,yy,inverse=True);lineage=[]
    for id in T.C['regions']:
        folder=work/id/str(seed)
        if not (folder/'height.npy').exists():continue
        pg=json.loads((work/id/'grid.json').read_text(encoding='utf8'));sample=T.sample(np.load(folder/'height.npy'),pg,g);pk=T.sample(np.load(folder/'kind.npy') if (folder/'kind.npy').exists() else np.load(work/id/'kind.npy'),pg,g,0)
        r=T.C['regions'][id];land=[f['geometry'] for f in T.D['land'] if f['id'] in r.get('landIds',[]) or ('landPrefix'in r and f['id'].startswith(r['landPrefix']))];footprint=T.raster(land,g);near=T.edt(~footprint)*g['stepM']<=30000;mask=(footprint|near)&(kind!=80)
        z[mask]=sample[mask];kind[mask]=pk[mask];lineage.append({'region':id,'heightSha256':T.sha(folder/'height.npy'),'cells':int(mask.sum())})
    # Seven narrative domains. These are explicitly schematic kinematic regions,
    # not a claim that seven Voronoi cells were produced by mantle convection.
    centres=[[-15,30],[-85,0],[96,25],[125,20],[49,2],[77,-29],[-160,-5]]
    a=np.deg2rad(lon);b=np.deg2rad(lat);xyz=np.stack([np.cos(b)*np.cos(a),np.cos(b)*np.sin(a),np.sin(b)],axis=-1)
    vectors=np.array([[np.cos(np.deg2rad(q[1]))*np.cos(np.deg2rad(q[0])),np.cos(np.deg2rad(q[1]))*np.sin(np.deg2rad(q[0])),np.sin(np.deg2rad(q[1]))] for q in centres]);plates=np.argmax(xyz@vectors.T,axis=-1).astype('uint8')
    boundary=(plates!=np.roll(plates,1,axis=1))|(plates!=np.roll(plates,1,axis=0));boundary[[0,-1]]=False
    area=T.C['radiusM']**2*np.deg2rad(360/g['width'])*(np.sin(np.deg2rad(lat+90/g['height']))-np.sin(np.deg2rad(lat-90/g['height'])))
    for key,v in {'height':z,'baseline':base,'kind':kind,'baseline-kind':basekind,'latitude':lat,'longitude':lon,'cell-area':area,'plate-domain':plates,'plate-boundary':boundary}.items():np.save(out/(key+'.npy'),np.asarray(v,dtype='float32'))
    T.savejson(out/'grid.json',g);T.savejson(out/'lineage.json',{'seed':seed,'regions':lineage,'unknownTreatment':'FAR-5 retains inherited coarse topography; no ecological or named terrain claims','plateDomains':'Schematic seven-parent domains; mapped fault belts and regional kinematics take precedence','parents':[{'id':i,'name':name,'centre':centres[i]} for i,name in enumerate(T.C['parents'])],'surfaceAreaM2':float(area.sum()),'expectedSurfaceAreaM2':4*np.pi*T.C['radiusM']**2,'formalHeightSha256':T.sha(T.ROOT/'terrain/world-height.f32')});T.log('GLOBAL '+str(seed))
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=T.WORK);ap.add_argument('--seed',type=int);a=ap.parse_args()
    for seed in [a.seed] if a.seed else T.C['seeds']:run(a.work,seed)
