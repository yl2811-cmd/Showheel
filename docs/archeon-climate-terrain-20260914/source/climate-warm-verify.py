"""Physical-time regression cases for changed orbits and unchanged civil dates."""
import pathlib,sys,importlib,copy,math
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;K=importlib.import_module('climate-contract');TIME=K.TIME;W=importlib.import_module('climate-water');G=importlib.import_module('climate-warm-candidates')

def tests():
    request={'calendar':{'orbitalPeriodSeconds':20000000.},'seed':5210914};request['fingerprint']=C.fingerprint(request);assert C.request_fingerprint(request)==request['fingerprint'];tampered=copy.deepcopy(request);tampered['seed']+=1
    try:C.request_fingerprint(tampered)
    except ValueError:pass
    else:raise AssertionError('Changed request accepted under old fingerprint')
    old=TIME.calendar({'yearSeconds':31557600,'solarDaySeconds':97200});short=TIME.calendar({'orbitalPeriodSeconds':TIME.EARTH_YEAR_SECONDS/2})
    assert math.isclose(1/short['siderealDaySeconds']-1/short['orbitalPeriodSeconds'],1/97200,rel_tol=1e-12)
    base={'areaWeightedTemperatureK':286.15,'seaIceAreaFraction':.15,'landPrecipitationMyr':1.,'toaNetWm2':.1,'surfaceNetWm2':.1,'waterBudgetFraction':1e-6,'maximumRegionalPrecipitationDriftFraction':.01}
    rows=[{**base,'year':i+1,'timeStartSeconds':i*short['orbitalPeriodSeconds'],'timeEndSeconds':(i+1)*short['orbitalPeriodSeconds']} for i in range(80)]
    assert K.balance(rows,calendar=short,target_c=[12,14])['passed']
    assert not K.balance(rows[:40],calendar=short,target_c=[12,14])['passed']
    bad=copy.deepcopy(rows)
    for r in bad:r['areaWeightedTemperatureK']+=.03*(r['timeStartSeconds']+r['timeEndSeconds'])/(2*TIME.EARTH_YEAR_SECONDS)
    assert not K.balance(bad,calendar=short)['passed']
    assert not K.balance(rows[:30]+rows[31:],calendar=short)['passed']
    cold=[{**r,'areaWeightedTemperatureK':194.} for r in rows]
    assert not K.balance(cold,calendar=short,target_c=[12,14])['passed']
    # Same physical source rate produces the same SI outlet flow with either
    # calendar. With zero soil storage/PET, no orbital discretization lag exists.
    n=9;yy,xx=np.indices((n,n));z=(n-yy)*3.+xx*.01;land=np.ones_like(z,bool)
    class Forcing:
        def __init__(self,cal):self.calendar=cal;self.durations=np.full(5,cal['orbitalPeriodSeconds']/5)
        def season(self,i):
            zero=np.zeros_like(z)
            return {'pr':np.ones_like(z)/TIME.EARTH_YEAR_SECONDS,'prsn':zero,'pet':zero,'tas':zero+290,'rss':zero,'rlds':zero,'rlus':zero}
    a=W.run(z,land,100,np.zeros_like(z),Forcing(old),max_cycles=30)
    b=W.run(z,land,100,np.zeros_like(z),Forcing(short),max_cycles=60)
    assert a['maximumWaterRelativeError']<1e-8 and b['maximumWaterRelativeError']<1e-8
    assert np.allclose(a['discharge-m3-s'],b['discharge-m3-s'],rtol=1e-5,atol=1e-10)
    assert np.allclose(a['precipitation'],2*b['precipitation'])
    # Analytic inventory against constant production and post-shutdown decay.
    rates=G.gas_history(1.,3200.,-81,50,35,[50,521])
    assert rates[1]['massKg']<rates[0]['massKg']
    assert math.isclose(rates[1]['massKg']/rates[0]['massKg'],math.exp(-471/3200),rel_tol=1e-12)
    assert math.isclose(rates[0]['cumulativeInjectedKg'],(131-35/2)*TIME.EARTH_YEAR_SECONDS,rel_tol=1e-12)
    return {'passed':True,'syntheticTestsOnly':True,'checks':['old Earth-year calendar accepted','new sidereal/solar relation','80 half-orbits cover 40 Earth years','40 half-orbits rejected as too short','physical temperature trend rejected','missing interval rejected','cold balanced climate rejected by 12-14C target','same SI river flow under two orbital periods','rain totals scale with actual duration','finite ramped gas inventory and unchanged 471 Earth-year decay'], 'maximumWaterRelativeError':max(a['maximumWaterRelativeError'],b['maximumWaterRelativeError'])}

if __name__=='__main__':
    result=tests();C.write(C.TASK/'warm-climate-v18/operator-tests.json',result);print(result)
