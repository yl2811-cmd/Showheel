"""Calendar and ecological resource checks; no vegetation map is produced."""
import pathlib,sys,importlib,math
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;TIME=importlib.import_module('climate-time');E=importlib.import_module('tectonics-ecology');B=importlib.import_module('climate-cloud-bake')

def run():
    checks=[];year=TIME.EARTH_YEAR_SECONDS;orbit=.63*year;cal=TIME.calendar({'orbitalPeriodSeconds':orbit});bounds=np.array([[0,.1],[.1,.25],[.25,.4],[.4,.58],[.58,.81],[.81,1.]])*orbit
    pieces=list(TIME.orbit_segments(0,3*year,bounds,cal));assert math.isclose(sum(p[1] for p in pieces),3*year,rel_tol=1e-12)
    split=[p for i in range(3) for p in TIME.orbit_segments(i*year,(i+1)*year,bounds,cal)]
    for i in range(6):assert math.isclose(sum(p[1] for p in pieces if p[0]==i),sum(p[1] for p in split if p[0]==i),rel_tol=1e-12)
    assert list(TIME.orbit_segments(year,2*year,bounds,cal))[0][0]!=0;checks.append('native six unequal bins retain orbital phase across civil years')
    values=np.arange(6.).reshape(6,1,1);mean,native=B.climatology(values,bounds,orbit);assert np.array_equal(native,values);assert math.isclose(float(mean[0,0]),float(np.average(np.arange(6),weights=np.diff(bounds,axis=1).ravel())))
    checks.append('cloud bins are retained without imposing named season count')
    source=C.read(C.ROOT/'data/tectonics-ecology-sources.json');shape=(4,4);zero=np.zeros(shape);cl={'calendar':cal,'timeBoundsSeconds':bounds}
    for name,value in [('pr',1/year),('pet',0),('mrro',0),('rss',0),('tas',15)]:cl[name]=np.full((6,)+shape,value)
    biomass=np.zeros((3,)+shape);soil=np.ones(shape)*100;nitrogen=zero.copy();water=zero.copy();records=[]
    for i in range(1,4):
        biomass,soil,nitrogen,water,report=E.year_step(biomass,soil,nitrogen,water,cl,np.zeros_like(biomass),i,2000,np.ones(shape),{'potentialGrowthMultiplier':3},source);records.append(report)
    assert np.allclose(water,3,rtol=0,atol=1e-12)
    assert np.allclose(nitrogen,3*source['resourceAssumptions']['depositionNitrogenKgM2yr'],rtol=0,atol=1e-12)
    assert np.allclose(soil,100+3*source['resourceAssumptions']['soilFormationMyr'],rtol=0,atol=1e-12)
    assert max(r['waterResidualM'] for r in records)<1e-12
    checks.append('water, nitrogen and soil integrate over physical Earth years on shortened orbit')
    import tempfile
    gate=importlib.import_module('climate-vegetation-start')
    with tempfile.TemporaryDirectory(prefix='archeon-vegetation-gate-') as tmp:
        path=pathlib.Path(tmp)/'start.json';C.write(path,{'vegetationReady':False,'missing':['radiation not validated']})
        try:gate.validate_package(path,path,'missing')
        except ValueError as error:assert 'unresolved' in str(error)
        else:raise AssertionError('WIP inputs were allowed into vegetation')
    checks.append('WIP vegetation package fails closed before arrays or simulation are loaded')
    report={'passed':True,'syntheticTestsOnly':True,'checks':checks,'civilYearSeconds':year,'testOrbitalSeconds':orbit,'seasonCountNotLocked':True,'vegetationSimulationExecuted':False};C.write(C.TASK/'warm-climate-v18/season-operator-tests.json',report);print(report)

if __name__=='__main__':run()
