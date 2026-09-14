"""Story geography is tested against results, never used to paint forcing."""
import pathlib,sys,importlib
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;S=importlib.import_module('landscape-story')
def named_cores(g,height,kind,hydrology,baseline_quiet=None):
 atlas=C.read(C.ROOT/'data/atlas.json');continents=['vorhan','duskreach'] if g['region']=='vorhan-duskreach' else [g['region']];rows=[]
 for site in atlas['settlements']:
  if site['properties'].get('continent','').lower() not in continents:continue
  xy=C.T.Proj(g['projection'])(*site['geometry']['coordinates']);r=round((g['ymax']-xy[1])/g['stepM']);c=round((xy[0]-g['xmin'])/g['stepM'])
  if not (0<=r<g['height'] and 0<=c<g['width']):continue
  perennial=bool(hydrology['lake-min-depth'][r,c]>.05);on_land=bool(kind[r,c]>=30 and kind[r,c]!=80)
  row={'id':site['id'],'name':site['properties']['name'],'coreOnLand':on_land,'permanentLakeAtMarker':perennial,'maximumLakeDepthM':float(hydrology['lake-max-depth'][r,c]),'resolutionM':g['stepM'],'extentStatus':site['properties'].get('extentStatus','unknown'),'passed':on_land and not perennial}
  if baseline_quiet is not None:
   footprint=(C.T.distance(g,site['geometry']['coordinates'])<20000)&baseline_quiet&(kind>=30)&(kind!=80)
   row['lowlandScreenAreaKm2']=float(footprint.sum()*g['stepM']**2/1e6)
   if footprint.any():
    row['perennialDryLowlandFraction']=float(np.mean(hydrology['lake-min-depth'][footprint]<=.05));row['passed']&=row['perennialDryLowlandFraction']>=.85
   row['footprintRole']='Existing 20km scene protection and baseline lowlands; not surveyed farmland boundaries'
  rows.append(row)
 return {'passed':all(r['passed'] for r in rows),'sites':rows,'scope':'named position and inherited-lowland screen; exact building/farm layouts need registered fine geometry','noArtificialExclusionOfWater':True}
def assess(g,height,fields,hydrology):
 atlas=C.read(C.ROOT/'data/atlas.json');core=next((p for p in atlas.get('surfaceProvinces',[]) if p.get('id')=='a-ochre'),None)
 if core is None or 'geometry' not in core:raise ValueError('The named Great Ochre acceptance polygon is required')
 mask=C.T.raster([core['geometry']],g);ratio=fields['aridityPOverPET'];valid=mask&np.isfinite(ratio)&~fields['iceOrNoPET'];area=valid.sum()*g['stepM']**2
 desert={'evaluated':bool(valid.any()),'areaKm2':float(area/1e6),'aridFraction':float(np.mean(ratio[valid]<.2)) if valid.any() else None,'semiAridOrDrierFraction':float(np.mean(ratio[valid]<.5)) if valid.any() else None,'role':'acceptance mask only; not applied to rainfall, wind or evaporation'}
 desert['passed']=bool(valid.any() and desert['aridFraction']>=C.CFG['desert']['minimumCoreAridFraction']) if g['region']=='aethelgard' else True
 story=S.check(g,height,hydrology['lake-depth'],hydrology['lake-occurrence'],hydrology['lake-max-depth']) if g['region']=='aethelgard' else {'passed':False,'scope':'run named_cores with the actual land mask and registered scene geometry before acceptance'}
 water_passed=hydrology['convergence']['passed'] and hydrology['maximumWaterRelativeError']<1e-8
 return {'desert':desert,'story':story,'waterPassed':water_passed,'passed':desert['passed'] and story['passed'] and water_passed,'noRainfallMaskApplied':True}
