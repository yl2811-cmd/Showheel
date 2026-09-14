"""Finite global gas histories and Kepler-consistent orbit requests; no fitted climate."""
import pathlib,sys,importlib,math
sys.path.insert(0,str(pathlib.Path(__file__).parent))
C=importlib.import_module('climate-terrain-common');TIME=importlib.import_module('climate-time');np=C.np
OUT=C.TASK/'warm-climate-v18';CONFIG=C.ROOT/'data/climate-warm-candidates.json'

def gas_history(peak_kg_s,lifetime_earth_years,start,stop,ramp,epochs):
    tau=lifetime_earth_years*TIME.EARTH_YEAR_SECONDS;rows=[]
    for epoch in epochs:
        mass=injected=0.0
        knots=sorted(set([start,min(start+ramp,stop),stop,epoch]))
        knots=[v for v in knots if start<=v<=epoch]
        if epoch<start:knots=[]
        for a,b in zip(knots,knots[1:]):
            dt=(b-a)*TIME.EARTH_YEAR_SECONDS
            if a>=stop:r0=r1=0.0
            else:r0=peak_kg_s*min(1,max(0,(a-start)/ramp));r1=peak_kg_s*min(1,max(0,(b-start)/ramp))
            slope=(r1-r0)/dt;e=math.exp(-dt/tau);one=-math.expm1(-dt/tau)
            mass=mass*e+r0*tau*one+slope*(tau*dt-tau*tau*one)
            injected+=(r0+r1)*dt/2
        rows.append({'civilYear':epoch,'massKg':mass,'cumulativeInjectedKg':injected})
    return rows

def prepare():
    cfg=C.read(CONFIG);astro=C.read(C.ROOT/'data/astronomy.json');node=next(v for v in astro['nodes'] if v['id']=='archeon');star=node['hostStar'];bodies=astro['systemBodies'];planet=node['terraformPlanet']
    G=6.67430e-11;au=149597870700.;ms=star['massSolar']*1.98847e30;mp=planet['massKg'];lum=4*math.pi*(star['radiusSolar']*695700000.)**2*5.670374419e-8*star['temperatureK']**4
    old_a=(G*(ms+mp)*(TIME.EARTH_YEAR_SECONDS/(2*math.pi))**2)**(1/3);old_flux=lum/(4*math.pi*old_a**2)
    fractions=[old_flux/1361]+cfg['earthFluxFractions'];orbits=[]
    outer=next(v for v in bodies if v['id']=='outer-planet');moons=[v for v in bodies if v.get('parent')=='archeon']
    for index,fraction in enumerate(fractions):
        flux=fraction*1361;a=math.sqrt(lum/(4*math.pi*flux));period=2*math.pi*math.sqrt(a**3/(G*(ms+mp)));hill=a*(mp/(3*ms))**(1/3)
        mutual=((a+outer['semiMajorKm']*1000)/2)*((mp+outer['massKg'])/(3*ms))**(1/3)
        gap=(outer['semiMajorKm']*1000-a)/mutual
        moon_rows=[{'id':m['id'],'orbitKm':m['semiMajorKm'],'fractionOfHillRadius':m['semiMajorKm']*1000/hill,'conservativeScreenPassed':m['semiMajorKm']*1000<.4*hill} for m in moons]
        row={'id':'original' if index==0 else f's{fraction:.2f}','stellarFluxWm2':flux,'earthFluxFraction':fraction,'semiMajorAU':a/au,'periodEarthDays':period/86400,'calendar':TIME.calendar({'orbitalPeriodSeconds':period}),
             'hillRadiusKm':hill/1000,'moons':moon_rows,'outerPlanetMutualHillSeparation':gap,'orbitScreenPassed':gap>2*math.sqrt(3) and all(m['conservativeScreenPassed'] for m in moon_rows),
             'stabilityStatus':'circular-orbit separation and conservative lunar extent screening only; no long-term multi-body stability claim'}
        orbits.append(row)
    polar=C.read(C.ROOT/'data/tectonics-continuation.json')['polarCI'];hyp=cfg['globalGasHypotheses'];gas_rows=[]
    molar_mean=(1-cfg['oxygenMoleFraction']-cfg['co2MoleFraction'])*.0280134+cfg['oxygenMoleFraction']*.031998+cfg['co2MoleFraction']*.0440095
    atmosphere=4*math.pi*4750000.**2*cfg['pressurePa']/9.610517;total_moles=atmosphere/molar_mean
    for gw in hyp['plateauGroundElectricGW']:
        for share in hyp['gasShareOfElectricity']:
            assert 1-share>=hyp['minimumElectricalReserveFraction']-1e-12
            row={'id':f'p{gw}-g{share:g}','peakTotalElectricGW':gw,'gasElectricShare':share,'peakGasElectricGW':gw*share,'doubleCountsPolarPlants':False,'productionHistoryRole':hyp['scope'],'species':{}}
            for gas,molar,fraction in [('SF6',.146055,hyp['sf6ShareOfGasEnergy']),('N2O',.044013,1-hyp['sf6ShareOfGasEnergy'])]:
                energy=polar['gasSpecificEnergyJkg'][gas];rate=gw*1e9*share*fraction/energy
                histories=[]
                for mult in polar['lifetimeSensitivity']:
                    tau=polar['gasLifetimeEarthYears'][gas]*mult
                    history=gas_history(rate,tau,hyp['civilStart'],hyp['civilStop'],hyp['rampEarthYears'],[-81,0,50,521,621])
                    for h in history:h['moleFraction']=h['massKg']/molar/total_moles;h['ppbv']=h['moleFraction']*1e9
                    histories.append({'lifetimeEarthYears':tau,'lifetimeMultiplier':mult,'epochs':history})
                injected=histories[1]['epochs'][-1]['cumulativeInjectedKg']
                row['species'][gas]={'peakProductionKgS':rate,'specificEnergyJkg':energy,'history':histories,'totalSynthesisEnergyJ':injected*energy,'minimumElementFeedstockKg':{'fluorine':injected*(6*.0189984/molar),'sulfur':injected*(.032065/molar)} if gas=='SF6' else {'nitrogen':injected*(.0280134/molar),'oxygen':injected*(.015999/molar)}}
            row['engineeringStatus']='finite power allocation passed; site mineral reserves, process yield and plant allocation not validated'
            gas_rows.append(row)
    C.write(OUT/'orbit-candidates.json',{'star':star,'orbits':orbits,'formalAstronomyChanged':False})
    C.write(OUT/'gas-candidates.json',{'hypotheses':hyp,'atmosphericMassKg':atmosphere,'meanMolarMassKgMol':molar_mean,'cases':gas_rows,'completeMeasuredInventory':False})
    requests=[]
    for orbit in orbits:
        for gas in gas_rows:
            residual={name:next(h for h in d['history'] if h['lifetimeMultiplier']==1)['epochs'][3]['moleFraction'] for name,d in gas['species'].items()}
            for seed in cfg['seeds']:
                for state in cfg['initialStates']:
                    key=f"{orbit['id']}/{gas['id']}/{seed}/{state}"
                    req={'version':cfg['version'],'model':'ROCKE-3D','modelVersion':'2.0','radiation':'SOCRATES','calendar':orbit['calendar'],'target':cfg['target'],'seed':seed,'initialState':state,
                         'orbit':orbit,'pressurePa':cfg['pressurePa'],'gasMoleFractions':{'CO2':cfg['co2MoleFraction'],'O2':cfg['oxygenMoleFraction'],**residual},'gasHistoryId':gas['id'],
                         'cloudOutput':cfg['cloudOutput'],'cloudValidationRequired':True,'balanceWindowEarthYears':20,'consecutiveWindows':2,'maximumIntegrationEarthYears':300,
                         'terrainFingerprint':None,'terrainStatus':'must bind latest accepted worldwide terrain, including FAR-5 and polar coarse data, before launch',
                         'spectralValidationPassed':False,'scope':'prepared candidate, not a simulated temperature or cloud pattern','configSha256':C.sha(CONFIG)}
                    req['gasMoleFractions']['N2']=1-sum(req['gasMoleFractions'].values());req['fingerprint']=C.fingerprint(req)
                    C.write(OUT/'requests'/key/'request.json',req);requests.append({'id':key,'fingerprint':req['fingerprint'],'status':'awaiting validated radiation and native terrain inputs'})
    C.write(OUT/'manifest.json',{'version':cfg['version'],'target':cfg['target'],'calendar':cfg['calendar'],'requests':requests,'orbitCount':len(orbits),'gasCount':len(gas_rows),'formalClimateRuns':0,'climateAccepted':False,'vegetationReady':False})
    print({'orbits':len(orbits),'gasHypotheses':len(gas_rows),'requests':len(requests),'climateAccepted':False})
    return orbits,gas_rows

if __name__=='__main__':prepare()
