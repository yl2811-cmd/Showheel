"""Constrained fault-block kinematics and a reproducible Orun reconstruction.

This is a prescribed crustal model, not mantle convection. All displacement
histories and author constraints are exported separately from erosion products.
"""
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt, maximum_filter
from scipy.interpolate import CubicSpline

def bent_trace(T,g,seed):
    original=next(f for f in T.D['ridges'] if f['id']=='orun')['geometry']['coordinates']
    p=T.Proj(g['projection']);xy=np.array([p(*q) for q in original]);ds=np.hypot(*np.diff(xy,axis=0).T);s=np.r_[0,np.cumsum(ds)]
    t=np.linspace(0,s[-1],max(160,round(s[-1]/16000)))
    x=CubicSpline(s,xy[:,0])(t);y=CubicSpline(s,xy[:,1])(t)
    tx=np.gradient(x);ty=np.gradient(y);length=np.hypot(tx,ty);nx=-ty/length;ny=tx/length
    rng=np.random.default_rng(seed);bend=np.zeros_like(t)
    for wavelength,amplitude in [(620000,23000),(280000,11500),(140000,3600)]:
        bend+=amplitude*np.sin(2*np.pi*t/wavelength+rng.uniform(-np.pi,np.pi))
    weight=T.ease(t/160000)*T.ease((t[-1]-t)/160000)
    for q,radius,fade in [([-10,9],28000,70000),([-3,11],50000,90000)]:
        qx,qy=p(*q);weight*=T.ease((np.hypot(x-qx,y-qy)-radius)/fade)
    controls=T.weights('aethelgard',g)
    control=T.map_coordinates(controls['fault-bend'],[(g['ymax']-y)/g['stepM'],(x-g['xmin'])/g['stepM']],order=1,mode='nearest',prefilter=False)
    bend=(bend+40000*(control-1))*weight;new=np.column_stack([x+nx*bend,y+ny*bend]);new[[0,-1]]=xy[[0,-1]]
    lo,la=p(new[:,0],new[:,1],inverse=True)
    segments=[]
    for i in range(0,len(t)-1,12):
        stop=min(i+13,len(t));segments.append({'id':f'orun-normal-{len(segments)+1:02d}','parent':'orun','mode':'normal','dipDegrees':float(rng.uniform(53,67)),'coordinates':np.column_stack([lo[i:stop],la[i:stop]]).tolist(),'formationHistory':'regional uplift, segmented normal displacement, later erosion','hangingWall':'north/northwest lowlands','footwall':'south/southeast plateau'})
    return original,np.column_stack([lo,la]).tolist(),segments,{'maximumBendM':float(abs(bend).max()),'endpointErrorM':float(abs(new[[0,-1]]-xy[[0,-1]]).max()),'seed':seed}

def river_mask(T,g):
    """Preserve the actual trunk footprint, not a whole frozen drainage basin."""
    lines=[f['geometry'] for f in T.D['rivers'] if f['id'] in ['ishkar','ishkar-east','ishkar-west']]
    centreline=T.raster(lines,g)
    return distance_transform_edt(~centreline)*g['stepM']<=max(4000,g['stepM']*2)

def reconstruct_orun(T,g,base,kind,old_protected):
    dx=g['stepM'];cfg=T.C['plateau'];orig,bent,segments,trace_report=bent_trace(T,g,T.C['seeds'][0]);od,os=T.tracefield(g,orig);nd,ns=T.tracefield(g,bent)
    land=(kind>=30)&(kind!=80);coast=distance_transform_edt(land)*dx;back=(ns<0)&land
    river=river_mask(T,g)
    exact=river|(T.distance(g,[-10,9])<28000)|(T.distance(g,[-3,11])<50000)
    for q in [orig[0],orig[-1]]:exact|=T.distance(g,q)<24000
    # Other named scenes remain fixed, except the expressly movable shallow basin.
    for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
        if f['geometry']['type']!='Point':continue
        if f['id'] in ['WH','WI','RB','V01']:continue
        exact|=T.distance(g,f['geometry']['coordinates'])<16000
    exact|=~land|(coast<6000)
    # Warp the existing front in physical space. A signed-distance displacement
    # moves its entire relief, rather than drawing a different line over it.
    xx,yy=T.mesh(g);signed=od*np.sign(os);gy,gx=np.gradient(signed,dx);gl=np.maximum(np.hypot(gx,gy),.25)
    shift=(nd*np.sign(ns)-signed)*np.exp(-(od/130000)**2)
    warped=T.map_coordinates(base,[(g['ymax']-(yy-gy/gl*shift))/dx,((xx+gx/gl*shift)-g['xmin'])/dx],order=1,mode='nearest',prefilter=False)
    # Define one regional slope from the front shoulder to the actual coast.
    # There is no painted polygon perimeter or fixed 300/650 km stopping edge.
    shoulder=cfg['shoulderM'];coastwide=gaussian_filter(coast,max(1,24000/dx))
    run=np.maximum(nd-shoulder,0)+coastwide
    datum=cfg['targetM'];ramp=datum*coastwide/np.maximum(run,1)
    rough=gaussian_filter(base,max(1,14000/dx))-gaussian_filter(base,max(2,80000/dx))
    rough=np.clip(rough,-90,90)
    ramp+=rough*T.ease(coast/60000)
    wh=T.distance(g,[4,11.5]);ramp-=cfg['basinDepthM']*np.exp(-(wh/45000)**2)
    # Preserve genuine mountain massifs, not every yellow patch in the old fill.
    massif=T.ease((gaussian_filter(base,max(1,18000/dx))-3500)/900)
    ramp=ramp*(1-massif)+np.maximum(ramp,base)*massif
    high=base>4300
    peak_weight=1-T.ease(distance_transform_edt(~high)*dx/160000)
    ramp+=np.maximum(base-ramp,0)*peak_weight
    # The length is determined by the coast. Lateral support fades away along
    # the endpoints so a contour cannot expose the original drawing boundary.
    mark=T.register_markup();author=T.raster([mark['geometry']],g)&land
    outside=distance_transform_edt(~author)*dx
    lateral=1-T.ease(outside/cfg['lateralFadeM'])
    ramp_w=lateral*T.ease((nd-18000)/65000)*T.ease((coast-6000)/24000)*back
    # Smooth author boundaries around fixed scenes; these remain exactly fixed.
    freefade=T.ease(distance_transform_edt(~exact)*dx/55000)
    ramp_w*=freefade
    front_w=np.exp(-(od/150000)**4)*freefade*land
    controls=T.weights('aethelgard',g);tectonic=controls['tectonic']
    revised=base+(warped-base)*front_w
    revised+=(ramp-revised)*ramp_w*tectonic
    revised[exact]=base[exact]
    authorized=(ramp_w>0)|(front_w>.001)
    hard=old_protected.copy();hard[authorized]=False;hard|=exact
    allow=T.ease(distance_transform_edt(~hard)*dx/36000).astype('float32')
    # Orun has already acquired its major displacement in the reconstruction.
    # The subsequent evolution integrates only the remaining activity.
    allow[ramp_w>.1]*=cfg['evolutionWeight']
    report={'mechanism':'Regional basalt plateau uplift with segmented normal fault displacement and erosional retreat','datumM':datum,'backSlopeExtent':'coast constrained, no fixed maximum distance','shoulderM':shoulder,'lateralFadeM':cfg['lateralFadeM'],'authorizedAreaKm2':float(authorized.sum()*dx*dx/1e6),'protectedMaxDeltaM':float(abs(revised[exact]-base[exact]).max()),'ishkarMaxDeltaM':float(abs(revised[river]-base[river]).max()),'targetDatumM':datum,'maxUpliftM':float((revised-base).max()),'maxLoweringM':float((base-revised).max()),'whisperflatRevisedM':float(revised.flat[np.argmin(wh)]),**trace_report}
    T.savejson(T.WORK/'aethelgard/orun-faults.json',segments);T.savejson(T.WORK/'aethelgard/orun-trace.json',{'original':orig,'revised':bent,'report':report})
    for key,a in {'ishkar-protected':river,'orun-exact':exact,'orun-ramp-weight':ramp_w,'orun-front-weight':front_w}.items():np.save(T.WORK/'aethelgard'/(key+'.npy'),np.asarray(a,dtype='float32'))
    return revised.astype('float32'),hard,allow,authorized,report

def thermal_audit(C):
    p=C['planet'];R=C['radiusM'];mass=p['massKg'];g=p['gravityMs2'];mean=mass/(4*np.pi*R**3/3)
    # Two homogeneous compositional reservoirs: a consistency check, not EOS.
    rho_c=p['coreDensityKgM3'];fraction=p['coreMassFraction'];Rc=(3*mass*fraction/(4*np.pi*rho_c))**(1/3)
    rho_m=mass*(1-fraction)/(4*np.pi*(R**3-Rc**3)/3)
    cases=[]
    for heating in [.5,1,2]:
        H=mass*(1-fraction)*p['mantleHeatProductionWkg']*heating
        loss=4*np.pi*R*R*p['surfaceHeatFluxWm2']
        cases.append({'radiogenicMultiplier':heating,'mantleRadiogenicTW':H/1e12,'surfaceLossTW':loss/1e12,'remainingCoolingOrCorePowerTW':(loss-H)/1e12})
    return {'meanDensityKgM3':mean,'coreRadiusKm':Rc/1000,'coreDensityKgM3':rho_c,'mantleMeanDensityKgM3':rho_m,'crustDensityKgM3':p['crustDensityKgM3'],'gravityMs2':g,'cases':cases,'inference':'High bulk density is compositional, not a multiplier for fault density. Heat and lithospheric strength are separate hypotheses. Tidal power is not assumed without an orbital dissipation calculation.','model':'Two-reservoir budget screening, no self-consistent mantle flow or planetary equation of state'}

def provinces(T,g,id,seed):
    """Broad displacement provinces. Different mechanics, not copied Orun arcs."""
    specs={
        'aethelgard':[([-28,37],'cap-plateau',380,260,2200,25),([-15,39],'fold-belt',520,190,2600,-25),([-3,38],'tilted-blocks',380,200,2100,30)],
        'vorhan':[([99,25],'tilted-blocks',700,250,3100,80),([112,34],'cap-plateau',460,340,2600,-20),([120,19],'fold-belt',550,220,2700,65)],
        'duskreach':[([75,-26],'cap-plateau',530,350,3200,-20),([69,-39],'tilted-blocks',550,260,2800,55),([82,-20],'fold-belt',450,180,2900,65)],
        'keld':[([46,9],'fold-belt',220,100,1500,65),([52,0],'cap-plateau',160,110,1200,65)]}
    xx,yy=T.mesh(g);p=T.Proj(g['projection']);rng=np.random.default_rng(seed);total=np.zeros_like(xx,dtype=float);remaining=np.zeros_like(xx,dtype=float);records=[]
    for num,(center,family,length,width,amplitude,angle) in enumerate(specs[id]):
        x,y=p(*center);theta=np.deg2rad(angle+rng.uniform(-8,8));u=((xx-x)*np.cos(theta)+(yy-y)*np.sin(theta))/1000;v=(-(xx-x)*np.sin(theta)+(yy-y)*np.cos(theta))/1000
        big=T.C.get('largeLandforms',{});scale=big.get('islandScale',1) if id=='keld' else big.get('regionalDisplacementScale',1)
        amp=amplitude*rng.uniform(.88,1.12)*scale;envelope=T.ease(1-(u/length)**2)*T.ease(1-(v/width)**2)
        if family=='cap-plateau':
            # Abrupt fault-facing flank, broad flexural back; future rivers must
            # carve the canyon network. No finished canyons are pre-painted.
            shoulder=.5+.5*np.tanh((v+width*.32)/14)
            back=np.clip((width-v)/(width*1.1),0,1)
            form=amp*envelope*shoulder*(.6+.4*back)
        elif family=='tilted-blocks':
            # Independently curved faults and different block widths/slip
            # patches replace the visibly repeated modulo/sawtooth ridges.
            form=np.zeros_like(u)
            for offset in [-.65,-.08,.48]:
                phase=rng.uniform(-3,3);fault=width*(offset+.11*np.sin(u/(length*.26)+phase)+.055*np.sin(u/(length*.11)+phase*.4))
                cross=v-fault;backwidth=width*rng.uniform(.38,.65)
                block=(.5+.5*np.tanh(cross/max(5,g['stepM']/1200)))*np.exp(-np.maximum(cross,0)/backwidth)
                slip=(.45+.55*np.sin(u/(length*rng.uniform(.25,.40))+phase)**2)*rng.uniform(.75,1)
                form=np.maximum(form,amp*envelope*block*slip)
        else:
            form=amp*envelope*(.38+.62*np.cos((v+.06*u)/(width*.22))**2)
        years=big.get('formationYears',8000000);total+=form;rate=amp/years;remaining+=form/amp*rate*.25
        records.append({'id':f'{id}-{family}-{num+1}','family':family,'center':center,'lengthKm':length*2,'widthKm':width*2,'displacementScaleM':amp,'formationEffectiveYears':years,'meanUpliftMyr':rate,'remainingRateFraction':.25,'rockLayers':'hard basalt/sandstone cap over weaker beds','origin':'prescribed crustal displacement under the seven-parent framework; hypothesis, not inferred mantle flow'})
    return total,remaining,records

def reconstruct_rift(T,g,base,kind,protected):
    """A segmented, pulled-apart graben, replacing the inherited lake capsule.

    The author's Rift reconstruction reopens lake cells only inside this
    explicit corridor. Old water level is not bedrock; ponding is recomputed
    by the drainage solver and permanent lake extent awaits climatic balance.
    """
    dx=g['stepM'];cfg=T.C.get('rift',{});p=T.Proj(g['projection']);xx,yy=T.mesh(g)
    f=next(f for f in T.D['ridges'] if f['id']=='rift');xy=np.array([p(*q) for q in f['geometry']['coordinates']])
    axis=xy[-1]-xy[0];length=np.linalg.norm(axis);tx,ty=axis/length;nx,ny=-ty,tx
    along=(xx-xy[0,0])*tx+(yy-xy[0,1])*ty;cross=(xx-xy[0,0])*nx+(yy-xy[0,1])*ny
    a=np.clip(along/length,0,1);end=T.ease(along/150000)*T.ease((length-along)/150000)
    # Independent, slowly varying slip patches keep the fault ends and relay
    # ramps from forming identical semicircular caps or parallel straight walls.
    bend=(26000*np.sin(a*np.pi*3)+13000*np.sin(a*np.pi*7))*np.sin(np.pi*a)**2
    half=cfg.get('halfWidthM',65000)*(1+.30*np.sin(a*11+.7)+.12*np.sin(a*23))
    signed=cross-bend;transition=max(5000,dx*.85)
    floor=.5*(1-np.tanh((abs(signed)-half)/transition))*end
    inherited_end=T.ease((along+180000)/150000)*T.ease((length+180000-along)/150000)
    corridor=np.exp(-(abs(signed)/cfg.get('reconstructionWidthM',230000))**4)*inherited_end
    authorized=(corridor>.01)&(kind>=30)&(kind!=80)
    reopened=(kind==200)&authorized
    hard=protected.copy();hard[reopened]=False
    # The named Rift marker belongs to the explicitly authorized reconstruction,
    # not an unrelated settlement that should pin a remnant of the old wall.
    rift_markers=[m for m in T.D['vistas'] if 'rift' in m.get('properties',{}).get('name','').lower() and m['geometry']['type']=='Point']
    for marker in rift_markers:hard[(T.distance(g,marker['geometry']['coordinates'])<24000)&authorized]=False
    for marker in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
        if marker['geometry']['type']=='Point' and marker not in rift_markers:hard|=T.distance(g,marker['geometry']['coordinates'])<24000
    free=T.ease(distance_transform_edt(~hard)*dx/36000)
    corridor*=free;floor*=free
    broad=gaussian_filter(base,max(1,55000/dx))
    flank=[]
    for offset in [-300000,300000]:
        sx=xx+(offset-signed)*nx;sy=yy+(offset-signed)*ny
        flank.append(T.map_coordinates(broad,[(g['ymax']-sy)/dx,(sx-g['xmin'])/dx],order=1,mode='nearest',prefilter=False))
    mix=np.clip((signed+300000)/600000,0,1);basement=flank[0]*(1-mix)+flank[1]*mix
    # This resolved basal surface removes an illustrator's narrow ridge. The
    # two fault throws and footwall tilts below supply the new tectonic relief.
    basement=base+(basement-base)*corridor
    slip=cfg.get('subsidenceM',1250)*(0.62+.38*np.sin(a*8+1.2)**2)
    controls=T.weights('vorhan',g);activity=controls['tectonic']
    depression=-slip*floor*activity
    west=np.maximum(0,signed-half);east=np.maximum(0,-signed-half)
    shoulder_w=cfg.get('westShoulderM',1100)*np.exp(-(west/120000)**2)*(signed>half)
    shoulder_e=cfg.get('eastShoulderM',800)*np.exp(-(east/145000)**2)*(signed<-half)
    shoulders=gaussian_filter(shoulder_w+shoulder_e,max(.4,transition/dx))
    shoulders*=end*(.55+.45*np.sin(a*10-.5)**2)*free*activity
    # Along-axis tilt provides an open low corridor; small relief may produce
    # real closed basins, recorded separately rather than filling an old lake.
    revised=basement+depression+shoulders
    revised[hard]=base[hard]
    k=kind.copy();k[reopened]=40
    faults=[];samples=np.linspace(0,1,max(60,round(length/20000)))
    bend1=(26000*np.sin(samples*np.pi*3)+13000*np.sin(samples*np.pi*7))*np.sin(np.pi*samples)**2
    width1=cfg.get('halfWidthM',65000)*(1+.30*np.sin(samples*11+.7)+.12*np.sin(samples*23))
    for side in [-1,1]:
        offset=bend1+side*width1;px=xy[0,0]+samples*length*tx+offset*nx;py=xy[0,1]+samples*length*ty+offset*ny
        lo,la=p(px,py,inverse=True);co=np.column_stack([lo,la]).tolist()
        for start in range(0,len(co)-1,10):faults.append({'id':f'rift-normal-{side}-{start}','parent':'rift','mode':'extension','dipDegrees':60,'coordinates':co[start:start+11],'hangingWall':'central graben','mechanism':'normal fault subsidence with tilted footwalls and relay ramps'})
    report={'mechanism':'Paired segmented normal faults, central graben subsidence and unequal tilted shoulders; later fluvial incision','lengthKm':float(length/1000),'widthRangeKm':[float(2*half.min()/1000),float(2*half.max()/1000)],'subsidenceScaleM':cfg.get('subsidenceM',1250),'authorizedRebuiltLakeAreaKm2':float(reopened.sum()*dx**2/1e6),'unrelatedLakeMaxDeltaM':float(np.max(abs(revised[(kind==200)&~reopened]-base[(kind==200)&~reopened]),initial=0)),'protectedMaxDeltaM':float(np.max(abs(revised[hard]-base[hard]),initial=0)),'waterPolicy':'Old 805 m water datum removed only inside authorized Rift corridor. Drainage solver outputs potential pond depth; permanent water requires precipitation/evaporation balance.','maxBasementChangeM':float(abs(revised-base).max())}
    T.savejson(T.WORK/'vorhan/rift-faults.json',faults)
    for key,value in {'rift-authorized':authorized,'rift-reopened-water':reopened,'rift-floor-weight':floor,'rift-reconstruction-weight':corridor}.items():np.save(T.WORK/'vorhan'/(key+'.npy'),np.asarray(value,dtype='float32'))
    return revised.astype('float32'),k,hard,authorized,report

def secondary_faults(T,g,id,seed,base,allow):
    """Seeded segments in free crust, with spacing and a shared slip budget."""
    rng=np.random.default_rng(seed+7091);density=T.C.get('faultDensity',1.5);target=round({'aethelgard':8,'vorhan':10,'duskreach':10,'keld':3}[id]*density)
    xx,yy=T.mesh(g);free=(allow>.45)&(base>120)&(base<5200);cells=np.flatnonzero(free);u=np.zeros_like(base,dtype=float);rate=np.zeros_like(u);traces=[];centres=[]
    if not len(cells):return u,rate,traces
    p=T.Proj(g['projection']);r=T.C['regions'][id];parents=[]
    for name,mode,v in r['faults']:
        co=next(f for f in T.D['ridges'] if f['id']==name)['geometry']['coordinates'];xy=np.array([p(*q) for q in co]);parents.append((name,mode,xy.mean(axis=0),np.arctan2(xy[-1,1]-xy[0,1],xy[-1,0]-xy[0,0])))
    if not parents:parents=[('keld-arc','compression',np.array([0,0]),np.deg2rad(-65))]
    for attempt in range(target*80):
        if len(traces)>=target:break
        i=int(rng.choice(cells));x,y=float(xx.flat[i]),float(yy.flat[i]);spacing=180000 if id!='keld' else 80000
        if any(np.hypot(x-a,y-b)<spacing for a,b in centres):continue
        parent,mode,centre,angle=min(parents,key=lambda v:np.hypot(x-v[2][0],y-v[2][1]));angle+=rng.uniform(-.45,.45)
        length=rng.uniform(180000,600000)*(0.4 if id=='keld' else 1);width=rng.uniform(45000,100000)*(0.55 if id=='keld' else 1)
        t=np.linspace(-.5,.5,7);offset=rng.normal(0,length*.025,7);px=x+np.cos(angle)*t*length-np.sin(angle)*offset;py=y+np.sin(angle)*t*length+np.cos(angle)*offset;lo,la=p(px,py,inverse=True);coords=np.column_stack([lo,la]).tolist();d,side=T.tracefield(g,coords)
        along=((xx-x)*np.cos(angle)+(yy-y)*np.sin(angle));end=T.ease(1-(along/(length*.65))**2);cross=d*np.sign(side)
        amp=rng.uniform(1000,2400)/np.sqrt(density)*(0.5 if id=='keld' else 1)*T.C.get('largeLandforms',{}).get('secondarySlipScale',1)
        if mode=='compression':form=amp*np.exp(-(d/width)**2)*end;family='folded-ridges'
        elif mode=='extension':form=amp*(.85*np.tanh(cross/(width*.15))+.25)*np.exp(-(d/(width*1.6))**2)*end;family='tilted-fault-block'
        else:form=amp*(.5+.5*np.tanh(cross/(width*.16)))*np.exp(-(d/(width*1.8))**2)*end;family='stepped-plateau'
        u+=form;rate+=form/8000000*.15;centres.append((x,y));traces.append({'id':f'{id}-secondary-{len(traces)+1:02d}','parent':parent,'mode':mode,'family':family,'coordinates':coords,'displacementM':amp,'lengthKm':length/1000,'widthKm':width/1000,'densityScenario':density,'formationEffectiveYears':8000000,'slipBudgetScaling':'per-segment amplitude / sqrt(density); independent from bulk planetary density'})
    return u,rate,traces

def shoreline_candidate(T,g,base,kind,displacement,controls):
    c=T.C.get('shoreline',{});dx=g['stepM'];land=(kind>=30)&(kind!=80)&(kind!=200);sea=kind==0
    if not c.get('enabled'):return base.copy(),kind.copy(),np.zeros_like(base),{'enabled':False}
    dl=distance_transform_edt(kind>=30)*dx;ds=distance_transform_edt(sea)*dx;near=((land&(dl<=c['maxDisplacementM']))|(sea&(ds<=c['maxDisplacementM'])))
    safe=near.copy()
    for f in T.D['settlements']+T.D['vistas']+T.D.get('extra',[]):
        if f['geometry']['type']=='Point':safe&=T.distance(g,f['geometry']['coordinates'])>c['harbourBufferM']
    if g.get('id')=='aethelgard':safe&=~river_mask(T,g)
    bed=base.astype(float).copy();bed[sea]=-ds[sea]*c['nearshoreSlope'];shore=np.zeros_like(base,dtype=float);status={}
    for strength in [1,.5,.25,0]:
        limit=np.where(land,strength+(1-strength)*T.ease(dl/c['maxDisplacementM']),strength)
        shore=displacement*limit*(1-controls['protection'])*safe;z=bed+shore;k=kind.copy();k[sea&safe&(z>0)]=40;k[land&safe&(z<=0)]=0
        changed=(k!=kind);fraction=float(changed.sum()/max(1,land.sum()))
        if fraction<=c['maxChangedLandFraction']:
            status={'enabled':True,'maxAllowedDisplacementM':c['maxDisplacementM'],'changedAreaKm2':float(changed.sum()*dx**2/1e6),'changedLandFraction':fraction,'coastalSlipFraction':strength,'nearshorePriorSlope':c['nearshoreSlope'],'portAndOutletBuffersM':c['harbourBufferM']};break
    result=base.copy();result[safe]=np.where(k[safe]==0,0,np.maximum(0,z[safe]));return result,k,safe.astype(float),status

def magmatic_provinces(T,g,id,seed):
    specs={'aethelgard':[([-34,24],520,850,560,'flood-basalt')],'vorhan':[([117,33],490,800,700,'flood-basalt')],'duskreach':[([72,-32],540,1000,650,'uplift-collapse')],'keld':[([49,3],160,400,450,'volcanic-chain')]}
    xx,yy=T.mesh(g);p=T.Proj(g['projection']);rng=np.random.default_rng(seed+80017);uplift=np.zeros(xx.shape);lava=np.zeros(xx.shape);records=[];scale=T.C.get('magmatism',{}).get('intensity',1)
    if not T.C.get('magmatism',{}).get('enabled'):return uplift,lava,records
    for q,radius,thermal,thickness,mode in specs[id]:
        x,y=p(*q);angle=rng.uniform(-1,1);u=((xx-x)*np.cos(angle)+(yy-y)*np.sin(angle))/1000;v=(-(xx-x)*np.sin(angle)+(yy-y)*np.cos(angle))/1000
        rr=np.hypot(u/(radius*1.25),v/(radius*.8));swell=thermal*np.exp(-rr**2*1.7)*scale
        # The plate drags the swell; inherited directions deform the volcanic
        # sheet. This intentionally avoids perfectly circular stamped volcanoes.
        lavafront=T.ease((1-rr+.09*np.sin(u/90)+.07*np.sin(v/60))/.5);sheet=thickness*lavafront*scale
        if mode=='uplift-collapse':swell-=420*np.exp(-((u-60)**2+(v+30)**2)/110**2)*scale
        uplift+=swell;lava+=sheet;records.append({'center':q,'type':mode,'radiusKm':radius,'dynamicSupportScaleM':thermal*scale,'basaltThicknessScaleM':thickness*scale,'formationEffectiveYears':T.C['magmatism']['formationYears'],'mechanism':'parameterized mantle upwelling and crustal magmatism; analogue scenario','sourceReferences':['https://www.nature.com/articles/nature13703','https://www.nasa.gov/missions/magellan/nasas-magellan-mission-reveals-possible-tectonic-activity-on-venus/']})
    if id=='aethelgard':records.append({'center':[2,7],'type':'inherited-orun-basalt-province','addedHeightM':0,'mechanism':'The Orun reconstructed base already includes regional support and basalt accumulation; do not add it a second time.'})
    return uplift,lava,records
