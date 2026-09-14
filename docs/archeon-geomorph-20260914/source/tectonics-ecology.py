"""Resource-limited Year 521 experiment; real balanced GCM input is mandatory."""
import pathlib,sys,importlib,json,argparse,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');np=T.np
from scipy.ndimage import convolve,gaussian_filter
from scipy.interpolate import RegularGridInterpolator

def climate_on_grid(folder,g):
    result=json.loads((folder/'result.json').read_text(encoding='utf8'));request=json.loads((folder/'request.json').read_text(encoding='utf8'))
    if result.get('model')!='ExoPlaSim' or not result.get('allowEcology') or not result.get('balanced'):raise RuntimeError('Year 521 requires a balanced real ExoPlaSim result; proxy or screening-only climate rejected')
    if T.sha(folder/'climate.npz')!=result['climateSha256'] or result['requestFingerprint']!=request['fingerprint']:raise RuntimeError('Climate lineage mismatch')
    xx,yy=T.mesh(g);lon,lat=T.Proj(g['projection'])(xx,yy,inverse=True);fields={}
    with np.load(folder/'climate.npz',allow_pickle=False) as data:
        la=data['latitude'];lo=data['longitude'];aorder=np.argsort(la);border=np.argsort(lo%360);la=la[aorder];lo=(lo%360)[border]
        for name in ['tas','pr','rss','mrro','snd']:
            a=data[name][:,aorder,:][:,:,border];a=np.concatenate([a[:,:,-1:],a,a[:,:,:1]],axis=2);x=np.r_[lo[-1]-360,lo,lo[0]+360]
            fields[name]=np.stack([RegularGridInterpolator((la,x),season,bounds_error=False,fill_value=None)((np.clip(lat,la.min(),la.max()),lon%360)) for season in a])
    fields['tas']-=273.15
    return fields,request,result

def year_step(biomass,soil,nitrogen,water,climate,seeds,year,dx,mask,config,source):
    """One year, five seasons. Shared resource caps prevent triple spending."""
    pfts=source['plantFunctionalTypes'];resources=source['resourceAssumptions'];land=mask>0;seconds=365.25*86400/5;growth_total=0.;water_residual=0.;nitrogen_residual=0.;fire_total=0.
    water_start=water.copy();nstart=nitrogen.copy();rain_total=np.zeros_like(water);out_total=np.zeros_like(water);use_total=np.zeros_like(water);nin_total=np.zeros_like(water);nuse_total=np.zeros_like(water);nreturn_total=np.zeros_like(water)
    cover=np.clip((biomass/np.array([p['capacityKgCm2'] for p in pfts])[:,None,None]).sum(axis=0),0,1)
    for season in range(5):
        rain=np.maximum(0,climate['pr'][season])*seconds*land;rain_total+=rain;water+=rain
        runoff=np.minimum(water,np.maximum(0,climate['mrro'][season])*seconds)*land
        capacity=np.maximum(.005,soil*.25);overflow=np.maximum(water-runoff-capacity,0);water-=runoff+overflow;out_total+=runoff+overflow
        evap=np.minimum(water,np.maximum(0,climate['tas'][season]+3)*.001*(1-.5*cover))*land;water-=evap;out_total+=evap
        ninput=resources['depositionNitrogenKgM2yr']/5*land;nitrogen+=ninput;nin_total+=ninput
        raw=[]
        for i,p in enumerate(pfts):
            # Propagule diffusion has an unaccelerated rate, independent of the
            # x3 potential-growth experiment. Wrap only east/west on the globe.
            b=biomass[i];spread=(np.roll(b,1,axis=1)+np.roll(b,-1,axis=1)+np.vstack([b[:1],b[:-1]])+np.vstack([b[1:],b[-1:]]))/4
            seed_supply=spread*min(.2,4*p['seedDiffusivityM2yr']/dx**2)+seeds[i]
            temp=np.clip(1-((climate['tas'][season]-p['temperatureOptimumC'])/p['temperatureWidthC'])**2,0,1)
            soil_limit=np.clip(soil/p['minimumSoilM'],0,1);remaining=np.clip(1-biomass[i]/p['capacityKgCm2'],0,1)
            recovery=.25+.75*(1-np.exp(-year/source['skyFire']['growthRecoveryYears']))
            raw.append((biomass[i]+.004*seed_supply)*p['earthPotentialRatePerYear']*config['potentialGrowthMultiplier']/5*temp*soil_limit*remaining*recovery*land)
        raw=np.stack(raw);demand=raw.sum(axis=0);water_cap=water*resources['waterUseEfficiencyKgCPerM3'];light_cap=np.maximum(0,climate['rss'][season])*seconds*resources['lightUseEfficiencyKgCPerJ']
        n_cap=nitrogen*resources['biomassCarbonNitrogenRatio'];factor=np.minimum(1,np.minimum.reduce([water_cap,light_cap,n_cap])/np.maximum(demand,1e-15));growth=raw*factor
        use=growth.sum(axis=0)/resources['waterUseEfficiencyKgCPerM3'];nuse=growth.sum(axis=0)/resources['biomassCarbonNitrogenRatio'];water-=use;nitrogen-=nuse;use_total+=use;nuse_total+=nuse;biomass+=growth;growth_total+=float(growth.sum())
        mortality=biomass*(.015+.012*np.exp(-year/source['skyFire']['decayYears']))/5
        dry=np.clip(1-water/np.maximum(capacity,1e-9),0,1);fire=biomass*(dry**4)*.006/5;death=mortality+fire;biomass-=death;fire_total+=float(fire.sum())
        returned=death.sum(axis=0)/resources['biomassCarbonNitrogenRatio']*.55;nitrogen+=returned;nreturn_total+=returned;soil+=death.sum(axis=0)*.0008
    soil+=resources['soilFormationMyr']*land
    water_residual=float(np.max(abs(water-water_start-rain_total+out_total+use_total)))
    nitrogen_residual=float(np.max(abs(nitrogen-nstart-nin_total+nuse_total-nreturn_total)))
    return biomass,soil,nitrogen,water,{'year':year,'growthKgCPerCellArea':growth_total,'fireLossKgCPerCellArea':fire_total,'waterResidualM':water_residual,'nitrogenResidualKgM2':nitrogen_residual,'minBiomass':float(biomass.min()),'minWaterM':float(water.min()),'minNitrogenKgM2':float(nitrogen.min())}

def run(work,seed,climate_folder):
    c=json.loads((work/'run-config.json').read_text(encoding='utf8'));sourcepath=T.ROOT/'data/tectonics-ecology-sources.json';source=json.loads(sourcepath.read_text(encoding='utf8'));out=work/'ecology'/str(seed);out.mkdir(parents=True,exist_ok=True);parent=work/'global'/str(seed);g=json.loads((parent/'grid.json').read_text(encoding='utf8'));kind=np.load(parent/'kind.npy');land=((kind>=30)&(kind!=80)&(kind!=200)).astype(float)
    climate,request,result=climate_on_grid(climate_folder,g)
    if request['lineage']['globalHeightSha256']!=T.sha(parent/'height.npy'):raise RuntimeError('Terrain changed after climate; recompute circulation first')
    corridor=np.zeros(land.shape);soil=np.full(land.shape,.03)*land
    for line in source['corridors']:
        d,_=T.tracefield(g,line['coordinates']);corridor=np.maximum(corridor,np.exp(-(d/(line['widthKm']*1000))**2)*line['strength'])
    corridor*=land;rng=np.random.default_rng(seed);patches=gaussian_filter(rng.random(land.shape),1);patches=(patches>np.quantile(patches,.90))*.03*land
    soil+=corridor*.55;nitrogen=(.002+.02*corridor)*land;water=soil*.15
    biomass=np.stack([(.18*corridor+patches)*.35,.10*corridor*.55,.60*corridor*.7]);seeds=np.stack([corridor,corridor*.7,corridor*.4]);history=[]
    # Plant masks are collected per continent, not inferred from today's biome.
    seedweight=np.ones(land.shape);soilweight=np.ones(land.shape)
    for region in c['regions']:
        pg=json.loads((work/region/'grid.json').read_text(encoding='utf8'));ctrl=T.weights(region,pg);foot=T.raster([f['geometry'] for f in T.D['land'] if f['id'] in c['regions'][region].get('landIds',[]) or ('landPrefix' in c['regions'][region] and f['id'].startswith(c['regions'][region]['landPrefix']))],g)
        seedweight[foot]=T.sample(ctrl['seeding'],pg,g)[foot];soilweight[foot]=T.sample(ctrl['soil'],pg,g)[foot]
    seeds*=seedweight;soil*=soilweight
    for year in range(522):
        if year:
            restoration=np.exp(-year/source['restoration']['halfLifeYears']) if year<=source['restoration']['ciEndYear'] else 0
            cultivation=.12*(1-np.exp(-(year-110)/150)) if year>110 else 0
            supply=seeds*(1+restoration+cultivation)
            biomass,soil,nitrogen,water,entry=year_step(biomass,soil,nitrogen,water,climate,supply,year,g['stepM'],land,c['ecology'],source);history.append(entry)
            if min(entry['minWaterM'],entry['minNitrogenKgM2'],entry['minBiomass']) < -1e-10:raise RuntimeError('Ecological resource overspend')
        if year in c['ecology']['years']:
            cover=np.clip((biomass/np.array([v['capacityKgCm2'] for v in source['plantFunctionalTypes']])[:,None,None]).sum(axis=0),0,1)
            np.savez(out/f'year-{year}.npz',biomass=biomass.astype('float32'),cover=cover.astype('float32'),soil=soil.astype('float32'),nitrogen=nitrogen.astype('float32'),water=water.astype('float32'),albedo=(.28-.12*cover).astype('float32'),erosionResistance=(1+2*cover).astype('float32'));print('ECOLOGY '+str(year),flush=True)
    T.savejson(out/'result.json',{'status':'experimental result','climateModel':'ExoPlaSim','climateSha256':result['climateSha256'],'sourceSha256':T.sha(sourcepath),'potentialGrowthMultiplier':3,'initialEpoch':2573,'initialMap':'inferred CI corridors and survivors; no present-day biome raster read','history':history,'feedbackStatus':'albedo and erosion resistance exported for reruns; no claim of converged vegetation/climate feedback'})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=T.WORK);ap.add_argument('--seed',type=int,default=5210914);ap.add_argument('--climate',type=pathlib.Path,required=True);ap.add_argument('--mask',type=pathlib.Path);a=ap.parse_args();T.WORK=a.work;T.MASK=a.mask;run(a.work,a.seed,a.climate)
