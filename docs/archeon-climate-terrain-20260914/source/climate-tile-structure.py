"""Reconstruct dimensionless geological motifs from image contours.

Only binary contour geometry survives extraction. Original brightness is never
sampled into a terrain height field. The masks are hypotheses, not DEMs.
"""
import sys,pathlib,importlib,argparse,json
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np
from scipy.ndimage import gaussian_filter,label,binary_closing,binary_opening,distance_transform_edt,map_coordinates
from PIL import Image

def extract(item):
 p=C.ROOT.parent/'tile'/item['file'];im=Image.open(p);a=np.asarray(im.convert('L').resize((512,512)),float)
 # Remove the frame before geometry inference, not after it has made a wall.
 a=a[36:476,36:476];smooth=gaussian_filter(a,3);components=[];support=np.zeros(a.shape,bool)
 for percentile in [55,70,83]:
  mask=binary_closing(smooth>np.percentile(smooth,percentile),iterations=3)
  mask=binary_opening(mask,iterations=2);labs,n=label(mask);counts=np.bincount(labs.ravel())
  keep=(counts>=100)&(counts<=a.size*.45);keep[0]=False;mask=keep[labs];components.append(mask);support|=mask
 inside=distance_transform_edt(support);outside=distance_transform_edt(~support)
 thickness=max(2,float(np.percentile(inside[inside>0],80))) if support.any() else 8
 distance=np.clip(inside/thickness,0,1)
 # Physical plateau terraces are generated from distance, independent of tone.
 terrace=.20*(distance>.10)+.25*(distance>.30)+.25*(distance>.56)+.30*(distance>.80)
 terrace=gaussian_filter(terrace,1.2)
 yy,xx=np.indices(a.shape);family=item['family']
 if family=='tilted':shape=terrace*(.65+.35*xx/(a.shape[1]-1))
 elif family=='volcanic':shape=.65*terrace+.35*np.sqrt(distance)
 elif family=='basin':shape=terrace-.32*np.exp(-(outside/max(2,thickness))**2)*(~support)
 elif family=='valley':
  shape=.3*terrace-.7*np.clip(outside/(thickness*1.7),0,1)
 else:shape=terrace
 shape-=shape.mean();shape/=max(1e-6,np.max(abs(shape)));shape=shape.astype('float32')
 cov=np.cov(np.column_stack(np.nonzero(support)).T) if support.sum()>3 else np.eye(2)
 record={**item,'sha256':C.sha(p),'sourcePixels':list(im.size),'cropFraction':[.07,.07,.93,.93],
  'extraction':'binary multilevel contour components -> signed distance -> procedural terraces',
  'heightRole':'dimensionless shape, fixed physical amplitude from regional lithology; not measured altitude',
  'components':int(label(support)[1]),'supportFraction':float(support.mean()),'orientationEigenvalues':np.linalg.eigvalsh(cov).tolist(),
  'normalisedMean':float(shape.mean()),'contourAmbiguity':'illumination can affect inferred contours; review as a morphology prior'}
 return shape,record

def build():
 out=C.WORK/'tile-library';out.mkdir(parents=True,exist_ok=True);used={};profiles={}
 for region,items in C.CFG['tileProfiles'].items():
  profiles[region]=[]
  for i,item in enumerate(items):
   name=f'{region}-{i}';field,record=extract(item);C.save_array(out/(name+'.npy'),field)
   record['id']=name;record['patternSha256']=C.sha(out/(name+'.npy'));used[item['file']]=record;profiles[region].append(record)
 inventory=[{'file':p.name,'sha256':C.sha(p),'used':p.name in used} for p in sorted((C.ROOT.parent/'tile').glob('*.png'))]
 C.write(out/'manifest.json',{'version':C.CFG['version'],'profiles':profiles,'inventory':inventory,'extractorSha256':C.sha(__file__)})
 print('Structural tile library',len(inventory),'images inspected;',len(used),'regional motifs',flush=True)
 return profiles

def placements(region,seed,gain):
 manifest=C.read(C.WORK/'tile-library/manifest.json');profiles=manifest['profiles'][region];rng=np.random.default_rng(seed+190514);result=[]
 for province in C.CFG['provinces']:
  if province['region']!=region:continue
  scale=.45 if region=='keld' else 1
  for i in range(16):
   p=profiles[i%len(profiles)];angle=np.deg2rad(province['angleDegrees'])+rng.uniform(-.22,.22)
   # All random draws precede gain selection: a 1x object survives at 1.5/2x.
   result.append({'id':province['id']+'-tile-'+str(i),'province':province['id'],'region':region,'pattern':p['id'],
    'offsetM':[float(rng.uniform(-270000,270000)*scale),float(rng.uniform(-270000,270000)*scale)],
    'provinceCenter':province['center'],'extentM':float(p['extentKm']*1000*rng.uniform(.8,1.2)),
    'angleRadians':float(angle),'phase':[float(rng.uniform(-.25,.25)),float(rng.uniform(-.25,.25))],
    'reliefM':p['reliefM']*gain,'index':i,'selected':i<round(8*gain)})
 return [r for r in result if r['selected']]

def field(g,region,seed,gain,allow):
 out=np.zeros(allow.shape,np.float32);records=placements(region,seed,gain);projection=C.T.Proj(g['projection']);dx=g['stepM']
 for f in records:
  cx,cy=projection(*f['provinceCenter']);cx+=f['offsetM'][0];cy+=f['offsetM'][1];extent=f['extentM'];radius=extent*.8
  c0=max(0,int((cx-radius-g['xmin'])/dx));c1=min(g['width'],int((cx+radius-g['xmin'])/dx)+2)
  r0=max(0,int((g['ymax']-cy-radius)/dx));r1=min(g['height'],int((g['ymax']-cy+radius)/dx)+2)
  if r0>=r1 or c0>=c1:continue
  yy,xx=np.meshgrid(g['ymax']-np.arange(r0,r1,dtype=float)*dx,g['xmin']+np.arange(c0,c1,dtype=float)*dx,indexing='ij');xx-=cx;yy-=cy
  angle=f['angleRadians'];u=(xx*np.cos(angle)+yy*np.sin(angle))/extent;v=(-xx*np.sin(angle)+yy*np.cos(angle))/extent
  u+=.06*np.sin(v*6+f['phase'][0]);v+=.05*np.sin(u*7+f['phase'][1]);w=C.T.ease((.5-abs(u))/.16)*C.T.ease((.5-abs(v))/.16)
  a=np.load(C.WORK/'tile-library'/(f['pattern']+'.npy'));sample=map_coordinates(a,[(v+.5)*(len(a)-1),(u+.5)*(a.shape[1]-1)],order=1,mode='constant',cval=0)
  # Each patch's volume-neutral relief is tapered with the same physical edge.
  if w.sum():sample-=float((sample*w).sum()/w.sum())
  out[r0:r1,c0:c1]+=sample*w*f['reliefM']
 return out*allow,records

if __name__=='__main__':build()
