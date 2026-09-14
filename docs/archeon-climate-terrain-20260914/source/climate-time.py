"""Physical orbital time is independent of the inherited Earth civil year."""
import math
EARTH_YEAR_SECONDS = 31557600.0
SOLAR_DAY_SECONDS = 97200.0

def calendar(value=None):
    value = value or {}
    earth = float(value.get('earthYearSeconds', EARTH_YEAR_SECONDS))
    orbit = float(value.get('orbitalPeriodSeconds', value.get('yearSeconds', EARTH_YEAR_SECONDS)))
    solar = float(value.get('solarDaySeconds', SOLAR_DAY_SECONDS))
    if not all(math.isfinite(v) and v > 0 for v in (earth, orbit, solar)):
        raise ValueError('Calendar requires positive finite physical durations')
    if earth != EARTH_YEAR_SECONDS or solar != SOLAR_DAY_SECONDS:
        raise ValueError('Earth civil year and Archeon solar day remain fixed')
    sidereal = 1.0 / (1.0 / solar + 1.0 / orbit)
    if 'siderealDaySeconds' in value and not math.isclose(float(value['siderealDaySeconds']), sidereal, rel_tol=1e-10):
        raise ValueError('Solar and sidereal rotation are inconsistent with the orbit')
    if 'yearSeconds' in value and not math.isclose(float(value['yearSeconds']), orbit, rel_tol=1e-10):
        raise ValueError('Legacy yearSeconds conflicts with explicit orbital period')
    return {'earthYearSeconds': earth, 'orbitalPeriodSeconds': orbit,
            'solarDaySeconds': solar, 'siderealDaySeconds': sidereal,
            'civilYearConvention': 'Earth inherited time; seasonal number and duration are not prescribed'}

def orbit_segments(start_seconds,end_seconds,bounds,value=None):
    """Split a civil-time interval at native forcing boundaries, retaining phase."""
    import numpy as np
    c=calendar(value);interval_check(bounds,c);b=np.asarray(bounds,float);b=b-b[0,0]
    if not (math.isfinite(start_seconds) and math.isfinite(end_seconds) and end_seconds>start_seconds):
        raise ValueError('Invalid ecological physical-time interval')
    orbit=c['orbitalPeriodSeconds'];cursor=float(start_seconds)
    while cursor<end_seconds-1e-6:
        cycle=math.floor(cursor/orbit)
        index=int(np.searchsorted(cycle*orbit+b[:,1],np.nextafter(cursor,np.inf),side='right'))
        if index==len(b):cycle+=1;index=0
        right=min(end_seconds,cycle*orbit+b[index,1]);duration=right-cursor
        if duration<=0:raise ValueError('Seasonal time did not advance')
        yield index,duration,cursor
        cursor=right

def interval_check(bounds, value=None):
    import numpy as np
    c = calendar(value); b = np.asarray(bounds, dtype=float)
    if b.ndim != 2 or b.shape[1] != 2 or not len(b) or not np.isfinite(b).all():
        raise ValueError('Expected finite physical interval bounds')
    duration = b[:, 1] - b[:, 0]
    if (duration <= 0).any() or not np.allclose(b[1:, 0], b[:-1, 1], rtol=0, atol=1e-5):
        raise ValueError('Missing, overlapping or reversed forcing intervals')
    if not math.isclose(float(duration.sum()), c['orbitalPeriodSeconds'], rel_tol=1e-9):
        raise ValueError('Seasonal forcing does not span one declared orbit')
    return duration

def history_bounds(rows, value=None):
    """Old histories count Earth years; explicit orbit records use SI intervals."""
    import numpy as np
    c = calendar(value)
    explicit = ['timeStartSeconds' in r and 'timeEndSeconds' in r for r in rows]
    if any(explicit) and not all(explicit):
        raise ValueError('Mixed legacy and explicit climate history clocks')
    if all(explicit):
        bounds = np.array([[r['timeStartSeconds'], r['timeEndSeconds']] for r in rows], float)
    else:
        if not math.isclose(c['orbitalPeriodSeconds'], EARTH_YEAR_SECONDS, rel_tol=1e-10):
            raise ValueError('Changed orbit requires physical history intervals')
        bounds = np.array([[(r['year']-1)*EARTH_YEAR_SECONDS, r['year']*EARTH_YEAR_SECONDS] for r in rows], float)
    if not np.isfinite(bounds).all() or np.any(bounds[:, 1] <= bounds[:, 0]) or not np.allclose(bounds[1:, 0], bounds[:-1, 1], rtol=0, atol=1e-5):
        raise ValueError('Climate history has missing, duplicate or invalid intervals')
    return bounds
