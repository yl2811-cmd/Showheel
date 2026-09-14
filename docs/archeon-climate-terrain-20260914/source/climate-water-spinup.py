"""Exact elimination of fixed dry river reaches during level-pool spinup.

Every potential-lake cell remains a node, including dry cells with competing
spill paths. This preserves the original wet/dry routing semantics. Four final
cycles run on the original complete graph before any output is accepted.
"""
import pathlib,sys,importlib,hashlib,json,os
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np;H=importlib.import_module('landscape-water')
from numba import njit

@njit(cache=False)
def destinations(order,receiver,compact):
    dest=compact.copy()
    for i in order:
        if compact[i]<0 and receiver[i]>=0:dest[i]=dest[receiver[i]]
    return dest

def checkpoint_key(z,land,dx,climate,rain_factor,external,initial_depth,seasonality,latitude):
    h=hashlib.sha256()
    for a in [z,land,climate['rain'],climate['temperature'],external,initial_depth]:
        if a is None:h.update(b'none');continue
        a=np.ascontiguousarray(a);h.update(str((a.shape,a.dtype.str)).encode());h.update(memoryview(a).cast('B'))
    h.update(json.dumps([dx,rain_factor,seasonality,latitude,C.sha(__file__),C.sha(H.__file__)]).encode())
    return h.hexdigest()

def run(z,land,dx,climate,rain_factor=1.,cycles=20,external=None,initial_depth=None,seasonality=.3,latitude=20.,topo=None,max_cycles=1000,progress=None,checkpoint=None):
    key=checkpoint_key(z,land,dx,climate,rain_factor,external,initial_depth,seasonality,latitude) if checkpoint else None
    tp=topo or H.topology(z,land,dx);nodes=tp['nodes'];area=dx*dx;count=tp['count'];b=tp['basin'];starts=tp['starts'];size=z.size
    if not count:return H.run(z,land,dx,climate,rain_factor,cycles=4,external=external,initial_depth=initial_depth,seasonality=seasonality,latitude=latitude,topo=tp,converge=True,max_cycles=4)
    compact=np.full(size,-1,np.int64);compact[nodes]=np.arange(len(nodes));dest=destinations(tp['order'],tp['bed-receiver'],compact)
    order=compact[tp['order']];order=order[order>=0];bed=tp['bed-receiver'][nodes];bed=np.where(bed>=0,dest[np.maximum(bed,0)],-1);rec=tp['receiver'][nodes];rec=np.where(rec>=0,dest[np.maximum(rec,0)],-1);rp=compact[tp['representative']];cb=b[nodes]
    active=tp['order'];group=dest[active]+1;store=np.zeros(count) if initial_depth is None else np.bincount(b[nodes],weights=initial_depth.ravel()[nodes]*area,minlength=count)
    original_storage=float(store.sum());ext=np.zeros_like(z) if external is None else np.maximum(0,external);released=np.zeros_like(z) if initial_depth is None else np.where(b.reshape(z.shape)<0,initial_depth*area,0.);original_release=float(released.sum())
    release=np.bincount(group,weights=released.ravel()[active],minlength=len(nodes)+1)
    rain=np.maximum(0,climate['rain'])*rain_factor;pet=np.maximum(.03,(climate['temperature']+6)*.025);evap=np.bincount(b[nodes],weights=pet.ravel()[nodes],minlength=count)/np.maximum(1,np.diff(starts));leak=np.full(count,.02);peak=6 if latitude>=0 else 0
    base=[];extra=[]
    for month in range(12):
        p=rain*(1+seasonality*np.cos(2*np.pi*(month-peak)/12));runoff=(p-np.minimum(p,pet))*.8;source=runoff*area*tp['land']+ext
        base.append(np.bincount(group,weights=source.ravel()[active],minlength=len(nodes)+1));extra.append(((p-runoff)*area).ravel()[nodes])
    del compact,dest,active,group,released,ext,rain,pet,p,runoff,source
    history=[];ring=[];previous=None;stable=0;periodic=float('inf');drift=float('inf');converged=False
    start_year=0
    if checkpoint and pathlib.Path(checkpoint).exists():
        with np.load(checkpoint,allow_pickle=False) as saved:
            if str(saved['key'])!=key:raise ValueError('Checkpoint inputs or solver changed; preserve this checkpoint and use a new candidate path')
            store=saved['store'].copy();previous=saved['previous'].copy();ring=list(saved['ring'].copy());history=json.loads(str(saved['history']));stable=int(saved['stable']);start_year=len(history)
        if progress:progress({'resumedFromWaterYear':start_year})
    for year in range(start_year,max(cycles,max_cycles)):
        ring.append(store.copy())
        if len(ring)>4:ring.pop(0)
        before_year=float(store.sum());inp_year=out_year=ev_year=leak_year=0.;levels=[];max_error=0.
        for month in range(12):
            wet=H._depth_values(z.ravel(),nodes,starts,tp['floors'],tp['sums'],store,area)>0
            source=base[month][1:]+extra[month]*wet;direct=base[month][0]/12
            if year==0 and month==0:source=source+release[1:]*12;direct+=release[0]
            before=float(store.sum());q,out,ev,lk=H._season(order,rec,bed,wet,cb,rp,starts,tp['floors'],tp['sums'],tp['capacity'],store,source,evap,leak,area,1/12);out+=direct;inp=float(source.sum()/12+direct);residual=float(store.sum())-before-inp+out+ev+lk;error=abs(residual)/max(1,inp,out,before)
            if error>1e-8:raise ValueError('Compressed spinup water budget failed: '+str(error))
            max_error=max(max_error,error);inp_year+=inp;out_year+=out;ev_year+=ev;leak_year+=lk;levels.append(H._levels(store,starts,tp['floors'],tp['sums'],area))
        levels=np.asarray(levels);periodic=float(np.max(abs(levels-previous),initial=0)) if previous is not None else float('inf');drift=abs(float(store.sum())-before_year)/max(1,inp_year,float(store.sum()));previous=levels
        stable=stable+1 if periodic<.02 and drift<1e-4 else 0
        history.append({'waterYear':year+1,'inputM3':inp_year,'outletM3':out_year,'lakeEvaporationM3':ev_year,'lakeLeakageM3':leak_year,'storageM3':float(store.sum()),'storageChangeM3':float(store.sum())-before_year,'relativeError':max_error})
        if checkpoint and ((year+1)%25==0 or stable>=3 or year+1==max(cycles,max_cycles)):
            path=pathlib.Path(checkpoint);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
            with tmp.open('wb') as handle:np.savez(handle,key=key,store=store,previous=previous,ring=np.asarray(ring),history=json.dumps(history),stable=stable)
            os.replace(tmp,path)
        if progress and ((year+1)%25==0 or stable>=3):progress({'waterYear':year+1,'periodicLevelChangeM':periodic,'relativeStorageDrift':drift})
        if year+1>=cycles and stable>=3:converged=True;break
    # Reproduce the last four years on the complete river graph, including
    # all individual discharges and seasonal inundation fields.
    first=ring[0];initial=initial_depth if len(history)<=4 else H.depth_field(z,dx,tp,first);full=H.run(z,land,dx,climate,rain_factor,cycles=4,external=external,initial_depth=initial,seasonality=seasonality,latitude=latitude,topo=tp,converge=True,max_cycles=4)
    count_years=len(history);full_history=full['history'];offset=count_years-len(full_history)
    for row in full_history:row['waterYear']+=offset
    full['history']=history[:offset]+full_history;full['convergence']['waterYears']=count_years;full['convergence']['passed']=bool(converged and full['convergence']['passed']);full['maxWaterRelativeError']=max(full['maxWaterRelativeError'],max(r['relativeError'] for r in history))
    full['initialStorageM3']=original_storage;full['releasedByBedChangeM3']=original_release
    full['spinupAcceleration']={'method':'exact routing-node elimination; all potential-lake cells retained','fullGridCells':size,'spinupGraphCells':len(nodes),'spinupCycles':count_years,'fullGraphVerificationCycles':len(full_history),'originalWaterSolverSha256':C.sha(H.__file__),'implementationSha256':C.sha(__file__)}
    return full
