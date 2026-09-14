"""Conservative river routing and level-pool lakes for candidate landscapes.

Bed elevation, priority-flood spill elevation and actual stored water are
different fields. Seasonal water years are separate from geological steps.
No modern river polyline or lake water elevation is used as a fixed bed.
"""
import pathlib,sys,importlib,json
sys.path.insert(0,str(pathlib.Path(__file__).parent))
T=importlib.import_module('tectonics-model');np=T.np
from scipy.ndimage import label
from numba import njit

@njit(cache=False)
def _level(volume,lo,hi,floors,sums,area):
    if hi<=lo:return 0.,0
    if volume<=0:return floors[lo],0
    left=1;right=hi-lo
    while left<right:
        n=(left+right+1)//2
        needed=(floors[lo+n-1]*n-(sums[lo+n-1]-(sums[lo-1] if lo else 0.)))*area
        if needed<=volume:left=n
        else:right=n-1
    n=left;total=sums[lo+n-1]-(sums[lo-1] if lo else 0.)
    return (volume/area+total)/n,n

@njit(cache=False)
def _season(order,rec,bedrec,wet,basin,representative,starts,floors,sums,capacity,store,source,evap,leak,area,dt):
    incoming=source.copy()*dt;q=np.zeros(len(source));export=0.;evaporated=0.;infiltrated=0.
    for kk in range(len(order)-1,-1,-1):
        i=order[kk];b=basin[i];v=incoming[i]
        if b>=0:
            rp=representative[b]
            if i!=rp:
                # Dry exposed lake-basin cells remain river reaches. Only
                # actual inundated cells transfer directly to the level pool.
                q[i]=v/dt;j=rp if wet[i] else bedrec[i]
                if j>=0:incoming[j]+=v
                else:export+=v
                continue
            available=store[b]+v
            _,wet_count=_level(max(0.,store[b]+v*.5),starts[b],starts[b+1],floors,sums,area)
            loss=min(available,max(0.,evap[b])*wet_count*area*dt);available-=loss;evaporated+=loss
            loss=min(available,max(0.,leak[b])*wet_count*area*dt);available-=loss;infiltrated+=loss
            store[b]=min(available,capacity[b]);v=available-store[b]
        q[i]=v/dt;j=rec[i]
        if j>=0 and j!=i:incoming[j]+=v
        else:export+=v
    return q,export,evaporated,infiltrated

@njit(cache=False)
def _collapse(nodes,starts,rank,rec,basin,z,filled,area):
    count=len(starts)-1;representative=np.zeros(count,np.int64);capacity=np.zeros(count);spill=np.zeros(count);collapsed=rec.copy()
    for b in range(count):
        lo=starts[b];hi=starts[b+1];rp=nodes[lo];level=filled[rp]
        for k in range(lo,hi):
            node=nodes[k]
            if rank[node]<rank[rp]:rp=node
            level=min(level,filled[node])
        representative[b]=rp;spill[b]=level
        for k in range(lo,hi):
            node=nodes[k];capacity[b]+=max(0.,level-z[node])*area;collapsed[node]=rp
        j=rec[rp]
        while j>=0 and basin[j]==b:j=rec[j]
        collapsed[rp]=j
    return representative,capacity,spill,collapsed

@njit(cache=False)
def _depth_values(z,nodes,starts,floors,sums,store,area):
    depths=np.zeros(len(nodes))
    for b in range(len(store)):
        lo=starts[b];hi=starts[b+1];level,_=_level(store[b],lo,hi,floors,sums,area)
        for k in range(lo,hi):depths[k]=max(0.,level-z[nodes[k]])
    return depths

@njit(cache=False)
def _levels(store,starts,floors,sums,area):
    result=np.empty(len(store))
    for i in range(len(store)):result[i]=_level(store[i],starts[i],starts[i+1],floors,sums,area)[0]
    return result

def topology(z,land,dx):
    land=land.copy();land[[0,-1]]=False;land[:,[0,-1]]=False
    filled,order,rec,slope=T.F.flood_route(z,land,dx)
    labels,count=label((filled-z>1e-4)&land,np.ones((3,3),int));basin=labels.ravel().astype('int32')-1
    rank=np.full(z.size,z.size,np.int64);rank[order]=np.arange(len(order));nodes=np.flatnonzero(basin>=0)
    if len(nodes):nodes=nodes[np.lexsort((z.ravel()[nodes],basin[nodes]))]
    sizes=np.bincount(basin[nodes],minlength=count);starts=np.r_[0,np.cumsum(sizes)].astype('int64')
    floors=z.ravel()[nodes].copy();sums=np.cumsum(floors,dtype=float)
    representative,capacity,spill,collapsed=_collapse(nodes,starts,rank,rec,basin,z.ravel(),filled.ravel(),dx*dx)
    active=np.zeros(z.size,bool);active[order]=True
    collapsed[(collapsed>=0)&~active[np.maximum(collapsed,0)]]=-1
    rec[(rec>=0)&~active[np.maximum(rec,0)]]=-1
    return {'filled':filled,'order':order,'receiver':collapsed,'bed-receiver':rec,'slope':slope,'basin':basin,'nodes':nodes,'starts':starts,'floors':floors,'sums':sums,'representative':representative,'capacity':capacity,'spill':spill,'land':land,'count':count}

def run(z,land,dx,climate,rain_factor=1.,cycles=20,external=None,initial_depth=None,seasonality=.3,latitude=20.,topo=None,converge=False,max_cycles=400):
    topo=topo or topology(z,land,dx);area=dx*dx;b=topo['basin'];count=topo['count'];nodes=topo['nodes'];starts=topo['starts']
    store=np.zeros(count) if initial_depth is None else np.bincount(b[nodes],weights=initial_depth.ravel()[nodes]*area,minlength=count)
    start_total=float(store.sum());maximum_depth=np.zeros_like(z);minimum_depth=np.full_like(z,np.inf);qmean=np.zeros(z.size);history=[];last_q=np.zeros(z.size)
    rain=np.maximum(0,climate['rain'])*rain_factor;pet=np.maximum(.03,(climate['temperature']+6)*.025)
    ext=np.zeros_like(z) if external is None else np.maximum(0,external)
    released=np.zeros_like(z) if initial_depth is None else np.where(b.reshape(z.shape)<0,initial_depth*area,0.)
    evaporation=np.bincount(b[nodes],weights=pet.ravel()[nodes],minlength=count)/np.maximum(1,np.diff(starts))
    leakage=np.full(count,.02);peak=6 if latitude>=0 else 0
    last_runoff=np.zeros_like(z);wet_occurrence=np.zeros_like(z)
    stable=0;previous_cycle=None;periodic_error=float('inf');storage_error=float('inf');converged=False
    requested_cycles=cycles;cycle_limit=max(cycles,max_cycles) if converge else cycles
    for year in range(cycle_limit):
        maximum_depth.fill(0);minimum_depth.fill(np.inf);wet_occurrence.fill(0);last_runoff.fill(0);cycle_levels=[]
        annual_q=np.zeros(z.size);water_before=float(store.sum());annual_input=annual_export=annual_evap=annual_leak=0.
        for month in range(12):
            seasonal=1+seasonality*np.cos(2*np.pi*(month-peak)/12);p=rain*seasonal;land_evap=np.minimum(p,pet);recharge=(p-land_evap)*.2;runoff=(p-land_evap)*.8
            source=runoff*area*topo['land']+ext
            actual=_depth_values(z.ravel(),nodes,starts,topo['floors'],topo['sums'],store,area)>0
            wetnodes=nodes[actual];source.ravel()[wetnodes]=p.ravel()[wetnodes]*area+ext.ravel()[wetnodes]
            if year==0 and month==0:source+=released*12
            wetflat=np.zeros(z.size,np.bool_);wetflat[wetnodes]=True
            before=float(store.sum());q,export,ev,leak=_season(topo['order'],topo['receiver'],topo['bed-receiver'],wetflat,b,topo['representative'],starts,topo['floors'],topo['sums'],topo['capacity'],store,source.ravel(),evaporation,leakage,area,1/12)
            inp=float(source.sum()/12);res=float(store.sum())-before-inp+export+ev+leak;scale=max(1,inp,export,before)
            if abs(res)/scale>1e-8:raise RuntimeError('Lake water balance: '+str(res/scale))
            annual_q+=q/12;annual_input+=inp;annual_export+=export;annual_evap+=ev;annual_leak+=leak
            depth=depth_field(z,dx,topo,store);maximum_depth=np.maximum(maximum_depth,depth);minimum_depth=np.minimum(minimum_depth,depth);wet_occurrence+=(depth>.05)/12
            levels=_levels(store,starts,topo['floors'],topo['sums'],area)
            cycle_levels.append(levels);last_runoff+=runoff/12
        history.append({'waterYear':year+1,'inputM3':annual_input,'outletM3':annual_export,'lakeEvaporationM3':annual_evap,'lakeLeakageM3':annual_leak,'storageM3':float(store.sum()),'storageChangeM3':float(store.sum())-water_before,'relativeError':abs(float(store.sum())-water_before-annual_input+annual_export+annual_evap+annual_leak)/max(1,annual_input,water_before)})
        qmean=annual_q;last_q=q
        cycle_levels=np.array(cycle_levels)
        if previous_cycle is not None:
            periodic_error=float(np.max(abs(cycle_levels-previous_cycle),initial=0));storage_error=abs(float(store.sum())-water_before)/max(1,float(store.sum()),annual_input)
            stable=stable+1 if periodic_error<.02 and storage_error<1e-4 else 0
            converged=stable>=3
        previous_cycle=cycle_levels
        if converge and year+1>=requested_cycles and converged:break
    depth=depth_field(z,dx,topo,store);lake_rows=[]
    for i in range(count):
        level,wet=_level(store[i],starts[i],starts[i+1],topo['floors'],topo['sums'],area);group=nodes[starts[i]:starts[i+1]];permanent=int(np.count_nonzero(minimum_depth.ravel()[group]>.05));active=int(np.count_nonzero(maximum_depth.ravel()[group]>.05))
        state='perennial' if permanent else 'seasonal' if active else 'dry-basin'
        lake_rows.append({'id':i,'storageM3':float(store[i]),'capacityM3':float(topo['capacity'][i]),'surfaceM':float(level),'spillM':float(topo['spill'][i]),'wetAreaKm2':wet*area/1e6,'maximumAreaKm2':active*area/1e6,'permanentAreaKm2':permanent*area/1e6,'outflowM3yr':float(qmean[topo['representative'][i]]),'state':state})
    receiver=topo['bed-receiver'].copy();wetflat=depth.ravel()>.05;receiver[wetflat]=topo['receiver'][wetflat];receiver[topo['representative']]=topo['receiver'][topo['representative']]
    topo['transport-receiver']=receiver
    return {'discharge':qmean.reshape(z.shape),'receiver':receiver.reshape(z.shape),'lake-depth':depth,'lake-min-depth':minimum_depth,'lake-max-depth':maximum_depth,'lake-level':np.where(depth>0,z+depth,z),'lake-occurrence':wet_occurrence,'runoff':last_runoff,'wetness':np.clip(last_runoff/(last_runoff+.2)+np.minimum(depth,1),0,1),'lakes':lake_rows,'history':history,'maxWaterRelativeError':max(v['relativeError'] for v in history),'initialStorageM3':start_total,'releasedByBedChangeM3':float(released.sum()),'topology':topo,'store':store,'convergence':{'passed':converged,'waterYears':year+1,'maximumPeriodicLevelChangeM':periodic_error,'relativeStorageDrift':storage_error,'requiredStableCycles':3,'levelToleranceM':.02},'climateStatus':'proxy seasonal scenario; not a GCM prediction','seasonality':{'amplitude':seasonality,'months':12,'hemispherePeakMonth':peak}}

def depth_field(z,dx,topo,store):
    depth=np.zeros_like(z);depth.ravel()[topo['nodes']]=_depth_values(z.ravel(),topo['nodes'],topo['starts'],topo['floors'],topo['sums'],store,dx*dx)
    return depth

@njit(cache=False)
def transport(z,soil,order,rec,q,allow,rock_k,dx,dt,influx,basin,representative,starts,nodes,spill,water_depth):
    depth=water_depth
    zz=z.ravel().copy();hh=soil.ravel().copy();original=zz.copy();er=np.zeros(len(zz));dep=np.zeros(len(zz));incoming=influx.ravel().copy()*dt;outflux=np.zeros(len(zz));area=dx*dx;export=0.;lake_deposit=0.
    # Downstream-first semi-implicit rock incision, confined to mobile nodes.
    for i in order:
        j=rec[i]
        if j<0 or j==i or allow[i]<=0 or depth[i]>.05:continue
        drop=max(0.,zz[i]-zz[j]);width=min(2800.,max(10.,650*(max(q[i]/31557600.,1.)/2500.)**.42));fraction=min(1.,width/dx)
        k=rock_k[i]*(.08+.92*np.exp(-max(hh[i],0.)/.5));fac=k*np.sqrt(max(q[i],0.))*dt/dx*fraction*allow[i]
        cut=drop*fac/(1+fac);soilcut=min(hh[i],max(0.,drop*.000025*np.sqrt(max(q[i],0.))*dt/dx*fraction*allow[i]))
        cut=min(drop*.95,cut+soilcut);zz[i]-=cut;hh[i]=max(0.,hh[i]-cut);er[i]=cut
    for kk in range(len(order)-1,-1,-1):
        i=order[kk];j=rec[i];volume=incoming[i]+er[i]*area;b=basin[i]
        if b>=0 and i==representative[b]:
            lo=starts[b];hi=starts[b+1];available=0.;wetarea=0.
            for k in range(lo,hi):
                node=nodes[k]
                if allow[node]>0 and depth[node]>.05:available+=depth[node]*area;wetarea+=area
            trapped=volume*(1-np.exp(-.03*wetarea/max(q[i],1.))) if wetarea>0 else 0.;trapped=min(trapped,available)
            if trapped>0:
                for k in range(lo,hi):
                    node=nodes[k]
                    if allow[node]>0 and depth[node]>.05:
                        put=trapped*depth[node]*area/max(available,1.)/area;zz[node]+=put;hh[node]+=put;dep[node]+=put
                volume-=trapped;lake_deposit+=trapped
        elif depth[i]<=.05 and j>=0 and allow[i]>0:
            settling=1-np.exp(-.03*area/max(q[i],1.));put=volume*settling/area*allow[i];zz[i]+=put;hh[i]+=put;dep[i]+=put;volume-=put*area
        outflux[i]=volume/dt
        if j>=0 and j!=i:incoming[j]+=volume
        else:export+=volume
    residual=(zz-original).sum()*area+export-influx.sum()*dt
    return zz.reshape(z.shape),hh.reshape(z.shape),er.reshape(z.shape),dep.reshape(z.shape),export,outflux.reshape(z.shape),residual,lake_deposit

def tests():
    n=17;yy,xx=np.indices((n,n));z=np.full((n,n),12.,float);z[4:13,4:13]=2.;z[:,8]=np.minimum(z[:,8],8.);z[-1,:]=0.;land=np.ones_like(z,bool);cl={'rain':np.ones_like(z)*1.5,'temperature':np.zeros_like(z)}
    wet=run(z,land,100.,cl,cycles=40);dry=run(z,land,100.,{'rain':np.zeros_like(z),'temperature':np.ones_like(z)*25},cycles=40,initial_depth=wet['lake-depth']);assert wet['lake-depth'].max()>0;assert dry['lake-depth'].sum()<wet['lake-depth'].sum()
    tp=wet['topology'];allow=tp['land'].ravel().astype(float);soil=np.ones_like(z);inf=np.zeros_like(z);inf[2,8]=100.
    out=transport(z,soil,tp['order'],tp['receiver'],wet['discharge'].ravel(),allow,np.full(z.size,1e-6),100.,10.,inf,tp['basin'],tp['representative'],tp['starts'],tp['nodes'],tp['spill'],wet['lake-depth'].ravel());scale=max(1.,out[4],float(inf.sum()*10));assert abs(out[6])/scale<1e-7;assert out[1].min()>=0
    # A downstream-only sloping domain transmits external water without loss.
    plane=(n-yy).astype(float)*3;zero={'rain':np.zeros_like(z),'temperature':np.zeros_like(z)};external=np.zeros_like(z);external[2,8]=1e6;cross=run(plane,land,100.,zero,cycles=2,external=external,seasonality=0);assert abs(cross['history'][-1]['outletM3']-1e6)<1e-6
    return {'filledLakeDepthM':float(wet['lake-depth'].max()),'dryingStorageM3':float(dry['lake-depth'].sum()*10000),'sedimentResidualM3':float(out[6]),'lakeSedimentM3':float(out[7]),'crossBoundaryWaterM3':cross['history'][-1]['outletM3'],'maximumWaterError':max(wet['maxWaterRelativeError'],dry['maxWaterRelativeError'],cross['maxWaterRelativeError']),'passed':True}

if __name__=='__main__':print(json.dumps(tests()))
