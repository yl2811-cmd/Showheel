"""Global area-conservative boundary packages, including unknown land."""
import sys,pathlib,importlib,argparse,json,math
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');T=C.T;np=C.np
W=importlib.import_module('tectonics-world')

def assemble(seed):
 g=W.global_grid(16000);base,kind=T.native(g);height=base.copy();coverage=np.zeros(height.shape,np.uint8);lineage=[]
 for region in ['aethelgard','vorhan','duskreach','keld']:
  if region=='aethelgard':source=T.BASE_WORK/'landscape-v14/connection-base'/str(seed);status='retained v14 story drainage'
  else:
   source=C.WORK/'accepted'/region/str(seed);status='accepted terrain candidate'
   if not (source/'height.npy').exists():source=C.WORK/'continental'/region/str(seed)/'g1';status='constructed candidate, erosion acceptance pending'
  if not (source/'height.npy').exists():continue
  pg=C.read(source/'grid.json');z=T.sample(np.load(source/'height.npy',mmap_mode='r'),pg,g)
  definition=T.C['regions'][region];mask=T.raster([f['geometry'] for f in T.D['land'] if f['id'] in definition.get('landIds',[]) or ('landPrefix' in definition and f['id'].startswith(definition['landPrefix']))],g)
  height[mask]=z[mask];coverage[mask]=1 if 'pending' in status else 2
  # Use the inherited land union; a coarse cell disappearing must not erase an island.
  lineage.append({'region':region,'source':str(source),'heightSha256':C.sha(source/'height.npy'),'status':status})
 xx,yy=T.mesh(g);lon,lat=T.Proj(g['projection'])(xx,yy,inverse=True)
 area=T.C['radiusM']**2*np.deg2rad(360/g['width'])*(np.sin(np.deg2rad(lat+90/g['height']))-np.sin(np.deg2rad(lat-90/g['height'])))
 out=C.WORK/'global'/str(seed)
 for name,a in {'height':height,'kind':kind,'coverage':coverage,'latitude':lat,'longitude':lon,'cell-area':area}.items():C.save_array(out/(name+'.npy'),a.astype('float32'))
 C.write(out/'grid.json',g);C.write(out/'lineage.json',{'parents':lineage,'unknownLand':'FAR-5 and polar inherited topography retained, uncertainty explicitly tagged','fingerprint':C.fingerprint(lineage),'terrainAccepted':len(lineage)==4 and all('pending' not in x['status'] for x in lineage)})
 return out

def aggregate(seed,resolution='screen'):
 source=assemble(seed);spacing=C.CFG['climate']['screenGridDegrees' if resolution=='screen' else 'reviewGridDegrees'];dy,dx=spacing
 # ROCKE-3D uses half-height polar rows, including centres at +/-90 degrees.
 latitude=np.arange(-90,90+dy/2,dy);longitude=np.arange(-180,180,dx);edges=np.r_[-90,(latitude[:-1]+latitude[1:])/2,90]
 lat=np.load(source/'latitude.npy');lon=np.load(source/'longitude.npy');weights=np.load(source/'cell-area.npy').astype(float);z=np.load(source/'height.npy');kind=np.load(source/'kind.npy');land=kind>=30;lake=kind==200;ice=kind==80
 row=np.clip(np.searchsorted(edges,lat,side='right')-1,0,len(latitude)-1);col=np.floor(((lon+180+dx/2)%360)/dx).astype(int);index=(row*len(longitude)+col).ravel();size=len(latitude)*len(longitude)
 def total(a):return np.bincount(index,weights=(a*weights).ravel(),minlength=size).reshape(len(latitude),len(longitude))
 areas=total(np.ones_like(z));la=total(land);land_fraction=la/areas;lake_fraction=total(lake)/areas;ice_fraction=total(ice)/areas
 mean=np.divide(total(z*land),la,out=np.zeros_like(la),where=la>0);variance=np.maximum(0,np.divide(total(z*z*land),la,out=np.zeros_like(la),where=la>0)-mean**2)
 native_area=float((weights*land).sum());represented=float((areas*land_fraction).sum());error=abs(represented-native_area)/native_area
 out=C.WORK/'climate-inputs'/str(seed)/resolution;out.mkdir(parents=True,exist_ok=True)
 arrays={'latitude':latitude,'longitude':longitude,'cell_area_m2':areas,'land_fraction':land_fraction,'lake_fraction':lake_fraction,'land_ice_fraction':ice_fraction,'orography_m':mean,'orography_variance_m2':variance,'surface_geopotential_m2s2':mean*C.CFG['climate']['gravityMs2'],'unknown_land_fraction':total(land*(np.load(source/'coverage.npy')==0))/areas}
 np.savez(out/'boundaries.npz',**arrays)
 record={'version':C.CFG['version'],'engine':'ROCKE-3D','seed':seed,'resolutionDegrees':spacing,'shape':list(mean.shape),'terrainFingerprint':C.read(source/'lineage.json')['fingerprint'],'parents':C.read(source/'lineage.json'),'boundarySha256':C.sha(out/'boundaries.npz'),'nativeLandAreaM2':native_area,'representedLandAreaM2':represented,'relativeLandAreaError':error,'globalAreaRelativeError':abs(areas.sum()-4*np.pi*4750000**2)/(4*np.pi*4750000**2),'status':'physical boundary arrays prepared; model-native file conversion and GCM execution still required','islandHandling':'fractional land coverage retained; no majority-vote deletion','coordinates':'south-to-north latitude, west-to-east longitude; explicit arrays are authoritative'}
 if error>1e-8:raise ValueError('Global land area mismatch')
 C.write(out/'boundary.json',record);print('GLOBAL BOUNDARY',seed,resolution,'land error',error,flush=True);return record

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--seed',type=int,default=5210914);a.add_argument('--resolution',choices=['screen','review'],default='screen');q=a.parse_args();aggregate(q.seed,q.resolution)
