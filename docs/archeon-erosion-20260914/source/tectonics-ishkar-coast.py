"""Coarse, expanded-domain river histories whose only outlets are real ocean.

The smaller history window's side outlet is a warning, not proof of bypass.
These independent trials extend the surface to the inherited coastal footprint.
"""
import pathlib,sys,importlib,json,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent))
I=importlib.import_module('tectonics-ishkar');C=I.C;T=C.T;np=T.np
from scipy.ndimage import map_coordinates,gaussian_filter
from scipy.spatial import cKDTree

def run(work,history='antecedent',formation=12000000,runoff=.3,dx=8000,dt=25000,halfwidth=480000):
 C.open_work(work);low,uplift,restored,modern,q,sed,g,record=I.geometry(work,dx,halfwidth)
 a=g['worldAffine'];u=g['xmin']+np.arange(g['width'])*dx;v=-g['ymax']+np.arange(g['height'])*dx;uu,vv=np.meshgrid(u,v)
 xx=a['origin'][0]+uu*a['across'][0]+vv*a['downstream'][0];yy=a['origin'][1]+uu*a['across'][1]+vv*a['downstream'][1]
 base=C.FROZEN/'aethelgard';pg=json.loads((base/'grid.json').read_text(encoding='utf8'));kind=map_coordinates(np.load(base/'5210914/kind.npy'),[(pg['ymax']-yy)/pg['stepM'],(xx-pg['xmin'])/pg['stepM']],order=0,mode='nearest');coast=kind==0
 if not coast.any():raise ValueError('Expanded trial has no ocean outlet')
 # Former scene/river masks leave square notches in the historical target.
 # Remove those sub-parent-grid discontinuities with an isotropic, documented
 # morphology regularizer, before any river runs. This does not carve a channel.
 support=(~coast).astype(float);smooth=gaussian_filter(restored*support,12000/dx)/np.maximum(1e-9,gaussian_filter(support,12000/dx));weight=1-T.ease((abs(uu)-160000)/80000);restored=restored+(smooth-restored)*weight;uplift=np.maximum(0,restored-low)
 record['legacyGridRegularization']={'gaussianSigmaM':12000,'coreHalfWidthM':160000,'transitionM':80000,'purpose':'Remove inherited rectangular mask notches from the unconstrained historical rock target; no modern channel or future river path used'}
 low[coast]=0;uplift[coast]=0
 result,fields=I.solve(low,uplift,modern,q,sed,g,history,formation,runoff,dt,False,coast)
 rr=np.array(result['pathRows']);cc=np.array(result['pathColumns']);p=T.Proj(g['projection']);lo,la=p(xx[rr,cc],yy[rr,cc],inverse=True)
 line=np.column_stack([lo,la]);fault=np.array(json.loads((base/'orun-trace.json').read_text(encoding='utf8'))['revised']);fxy=np.array([p(*v) for v in fault]);fdense,_=I.resample(fxy,1000);dist,idx=cKDTree(fdense).query(np.column_stack([xx[rr,cc],yy[rr,cc]]));nearest=int(np.argmin(dist));bend=next(f for f in T.D['settlements'] if f['properties']['name']=='Riverbend');bx,by=p(*bend['geometry']['coordinates']);bdist=np.hypot(xx[rr,cc]-bx,yy[rr,cc]-by);ib=int(bdist.argmin())
 result.update(minimumDistanceToOrunM=float(dist[nearest]),closestOrunRouteCoordinates=line[nearest].tolist(),riverbendDistanceToNewRiverM=float(bdist[ib]),nearestRiverbendRouteCoordinates=line[ib].tolist(),domainHalfWidthM=halfwidth,actualOceanOutlets=True)
 result['crossesOrunTrace']=bool(dist[nearest]<=dx*1.5 and v[rr[-1]]>30000)
 result['geologicalInterpretation']='fault-crossing route candidate' if result['crossesOrunTrace'] else 'side route candidate; trace intersection not resolved'
 frame=np.zeros(kind.shape,bool);frame[[0,-1],:]=True;frame[:,[0,-1]]=True
 fields['kind']=kind;fields['physical-mask']=~frame;fields['modern-profile']=modern
 name=f'{history}-{formation}-{runoff:g}-dx{dx}-dt{dt}-w{halfwidth}';out=work/'ishkar-coast'/name;record.update(oceanSourceSha256=T.sha(base/'5210914/kind.npy'),inlandBoundary='closed; rerun with a wider domain before accepting a side path')
 I.save_case(out,result,fields,g,record)
 features=[{'type':'Feature','properties':{'name':'Ishkar · simulated candidate','status':'candidate','history':history,'formationYears':formation,'runoffMultiplier':runoff},'geometry':{'type':'LineString','coordinates':line.tolist()}},{'type':'Feature','properties':{'name':'Riverbend · current'},'geometry':bend['geometry']},{'type':'Feature','properties':{'name':'Riverbend · river-adjacent candidate','status':'provisional; no settlement moved'},'geometry':{'type':'Point','coordinates':line[ib].tolist()}},{'type':'Feature','properties':{'name':'Orun · accepted trace'},'geometry':{'type':'LineString','coordinates':fault.tolist()}}]
 T.savejson(out/'route.geojson',{'type':'FeatureCollection','features':features});T.log('COAST '+name+' '+json.dumps({k:result[k] for k in ['reachesActualCoast','maximumPathPondM','maximumPathErosionM','crossesOrunTrace','riverbendDistanceToNewRiverM','conservationPassed']},default=T.json_scalar));return result

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=C.DEFAULT);ap.add_argument('--history',default='antecedent');ap.add_argument('--formation',type=int,default=12000000);ap.add_argument('--runoff',type=float,default=.3);ap.add_argument('--grid-m',type=int,default=8000);ap.add_argument('--dt',type=int,default=25000);ap.add_argument('--halfwidth',type=int,default=480000);a=ap.parse_args();run(a.work,a.history,a.formation,a.runoff,a.grid_m,a.dt,a.halfwidth)
