"""Nested Landlab landscapes with water and sediment inherited from a parent.

The parent boundary supplies external runoff at receiver crossings. SPACE clears
its sediment-influx field, so inherited sediment is advanced by a separate,
conservative deposition/throughflow operator after SPACE. It is never silently
discarded. Nested products remain independent views; they are not blindly pasted
over the continental routing grid.
"""
import pathlib,sys,json,importlib,argparse,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model')
np=T.np;WORK=T.WORK;ROOT=T.ROOT
from landlab import RasterModelGrid,NodeStatus
from landlab.components import FlowAccumulator,SpaceLargeScaleEroder,LithoLayers,ExponentialWeatherer,TaylorNonLinearDiffuser
from numba import njit

@njit(cache=False)
def accumulate_double(source,order,receivers):
    q=source.copy()
    for k in range(len(order)-1,-1,-1):
        i=order[k];j=receivers[i]
        if j>=0 and j!=i:q[j]+=q[i]
    return q

class ConservativeFlowAccumulator(FlowAccumulator):
    def run_one_step(self,*args,**kwargs):
        result=super().run_one_step(*args,**kwargs);grid=self._grid
        # Landlab 2.11 cfuncs._accumulate_bw uses a float32 temporary even for
        # double arrays. Preserve its routing, but accumulate flux in float64.
        source=np.asarray(grid.at_node['water__unit_flux_in']*grid.cell_area_at_node,dtype='float64');source[grid.closed_boundary_nodes]=0
        grid.at_node['surface_water__discharge'][:]=accumulate_double(source,grid.at_node['flow__upstream_node_order'],grid.at_node['flow__receiver_node'])
        return result

def weighted_diffusion(grid,z,weight,dt,dx):
    """Nonlinear link flux with local weights; preserve finite-volume exchanges."""
    links=grid.nodes_at_link;coef=.025*np.minimum(weight[links[:,0]],weight[links[:,1]]);coef[grid.status_at_link==4]=0;remaining=dt
    while remaining>1e-9:
        slope=grid.calc_grad_at_link(z);factor=1+(slope/.7)**2
        step=min(remaining,.15*dx*dx/max(1e-12,float(np.max(coef*(1+3*(slope/.7)**2)))))
        flux=-coef*slope*factor;change=-grid.calc_flux_div_at_node(flux);z[grid.core_nodes]+=change[grid.core_nodes]*step;remaining-=step

@njit(cache=False)
def external_sediment(z,h,rec,order,q,influx,area,dt,allow):
    incoming=influx.copy()*dt;dep=np.zeros(len(z));export=0.
    for k in range(len(order)-1,-1,-1):
        i=order[k];j=rec[i];s=incoming[i]
        if s<=0:continue
        if j==i or j<0:export+=s;continue
        put=min(s/area*(1-np.exp(-.03*area/max(q[i],1))),2.)*allow[i]
        dep[i]=put;z[i]+=put;h[i]+=put;incoming[j]+=s-put*area
    return dep,export

def boundary_flux(parent,g,pg,q,rec,sed):
    xx,yy=T.mesh(pg)
    if pg['projection']!=g['projection']:
        lo,la=T.Proj(pg['projection'])(xx,yy,inverse=True);xx,yy=T.Proj(g['projection'])(lo,la)
    inside=(xx>=g['xmin'])&(xx<=g['xmin']+(g['width']-1)*g['stepM'])&(yy<=g['ymax'])&(yy>=g['ymax']-(g['height']-1)*g['stepM'])
    ok=(rec.ravel()>=0);cross=np.where(ok&~inside.ravel()&inside.ravel()[np.maximum(rec.ravel(),0)])[0]
    water=np.zeros((g['height'],g['width']));solids=np.zeros_like(water);records=[]
    for i in cross:
        j=rec.ravel()[i];x0,y0=xx.ravel()[i],yy.ravel()[i];x1,y1=xx.ravel()[j],yy.ravel()[j]
        # Locate the segment entry, not a displaced parent centre far inside.
        low,high=0.,1.
        for _ in range(24):
            mid=(low+high)/2;x=x0+(x1-x0)*mid;y=y0+(y1-y0)*mid
            if g['xmin']<=x<=g['xmin']+(g['width']-1)*g['stepM'] and g['ymax']-(g['height']-1)*g['stepM']<=y<=g['ymax']:high=mid
            else:low=mid
        x=x0+(x1-x0)*high;y=y0+(y1-y0)*high;c=int(np.clip(round((x-g['xmin'])/g['stepM']),2,g['width']-3));r=int(np.clip(round((g['ymax']-y)/g['stepM']),2,g['height']-3))
        water[r,c]+=q.ravel()[i];solids[r,c]+=sed.ravel()[i]
        records.append({'parentNode':int(i),'childNode':[r,c],'waterM3yr':float(q.ravel()[i]),'sedimentM3yr':float(sed.ravel()[i])})
    return water,solids,records

class ParentForcing:
    """Interpolate boundary reservoirs after routing each parent snapshot.

    Receiver topology can change. Interpolating already-mapped crossings keeps
    the water/sediment routing paired with its own height snapshot.
    """
    def __init__(self,parent,folder,g,pg):
        self.parent=parent;self.folder=folder;self.g=g;self.pg=pg;self.cache={}
        self.years=sorted(int(p.stem.split('-')[-1]) for p in folder.glob('height-*.npy'))
        if not self.years or self.years[0]!=0:raise RuntimeError('Time-dependent parent snapshots are required')
        self.hashes={}
        for year in self.years:
            for field in ['height','discharge','receiver','sediment-flux']:
                file=folder/f'{field}-{year}.npy'
                if not file.exists():raise RuntimeError('Missing time-dependent parent forcing '+str(file))
                self.hashes[file.name]=T.sha(file)
    def snapshot(self,year):
        if year not in self.cache:
            arrays={k:np.load(self.folder/f'{k}-{year}.npy') for k in ['height','discharge','receiver','sediment-flux']}
            qw,qs,records=boundary_flux(self.parent,self.g,self.pg,arrays['discharge'],arrays['receiver'],arrays['sediment-flux'])
            self.cache[year]=(T.sample(arrays['height'],self.pg,self.g),qw,qs)
            if len(self.cache)>2:del self.cache[min(self.cache)]
        return self.cache[year]
    def at(self,year):
        if year>self.years[-1]:raise RuntimeError('Child cannot evolve past the parent')
        i=max(0,np.searchsorted(self.years,year,side='right')-1);a=self.years[i];b=self.years[min(i+1,len(self.years)-1)];w=0 if a==b else (year-a)/(b-a)
        av=self.snapshot(a);bv=self.snapshot(b)
        return tuple(x*(1-w)+y*w for x,y in zip(av,bv))

def run(config,seed=5210914,dtmax=50000,end=2000000,suffix=''):
    id=config['id'];parent=config['parent'];isfine=parent not in T.C['regions'];pdir=WORK/'refined'/parent if isfine else WORK/parent/str(seed);pg=json.loads(((pdir if isfine else WORK/parent)/'grid.json').read_text());p=T.Proj(pg['projection']);cx,cy=p(*config['center']);step=config['stepM'];n=round(config['widthKm']*1000/step)+1
    g={'width':n,'height':n,'stepM':step,'xmin':cx-(n-1)*step/2,'ymax':cy+(n-1)*step/2,'projection':pg['projection'],'region':parent if not isfine else 'aethelgard','id':id}
    out=WORK/'refined'/(id+suffix);out.mkdir(parents=True,exist_ok=True);T.savejson(out/'grid.json',g)
    pb=np.load(pdir/('initial.npy'));pi=T.sample(pb,pg,g).astype('float64');finalparent=np.load(pdir/'height.npy');pf=T.sample(finalparent,pg,g)
    baseparent=WORK/'aethelgard' if isfine else WORK/parent;bg=json.loads((baseparent/'grid.json').read_text());kind=T.sample(np.load(pdir/'kind.npy') if (pdir/'kind.npy').exists() else np.load(baseparent/'kind.npy'),pg if (pdir/'kind.npy').exists() else bg,g,0);protected=T.sample(np.load(baseparent/('hard-protected.npy' if (baseparent/'hard-protected.npy').exists() else 'protected.npy')),bg,g,0)>0
    allowpath=baseparent/'evolution-allow.npy';allow=T.sample(np.load(allowpath if allowpath.exists() else baseparent/'allow.npy'),bg,g).astype('float64');allow[protected]=0
    mask_id=(parent if not isfine else 'aethelgard') if T.MASK and pathlib.Path(T.MASK).is_dir() else id
    controls=T.weights(mask_id,g);allow*=1-controls['protection']
    # Higher frequencies only; vertical mean is removed and amplitude is bounded.
    source=T.norm(np.load(T.OLD/'references/mesa.npy'));detail=T.F.tiled(source,g,15 if step==250 else 3,seed+n);detail=np.clip(detail*35,-90,90)*allow
    pi+=detail
    frame=np.minimum.reduce(np.broadcast_arrays(np.arange(n)[:,None],(n-1-np.arange(n))[:,None],np.arange(n)[None,:],(n-1-np.arange(n))[None,:]));fade=T.ease(frame/12);allow*=fade
    z0=pi.copy();grid=RasterModelGrid((n,n),xy_spacing=step);z=grid.add_field('topographic__elevation',pi.ravel().copy(),at='node');h=grid.add_field('soil__depth',np.asarray(.7*controls['soil'].ravel(),dtype='float64'),at='node');bed=grid.add_field('bedrock__elevation',z-h,at='node')
    hard=protected.ravel()|((kind.ravel()<30)|(kind.ravel()==80));allow.ravel()[hard]=0;grid.status_at_node[(kind.ravel()<30)|(kind.ravel()==80)]=NodeStatus.FIXED_VALUE;grid.set_closed_boundaries_at_grid_edges(False,False,False,False)
    grid.status_at_node[grid.boundary_nodes]=NodeStatus.FIXED_VALUE
    weather=ExponentialWeatherer(grid,soil_production_maximum_rate=np.maximum(1e-12,.00004*allow.ravel()*controls['weathering'].ravel()),soil_production_decay_depth=.7)
    cap=T.C['lithology']['capThicknessM'];lith=LithoLayers(grid,[cap,cap+260,cap+440,cap+700,20000],[1,2,1,2,1],{'K_sp':{1:T.C['lithology']['hardK'],2:T.C['lithology']['softK']},'D':{1:.015,2:.04}},function=lambda x,y: .001*x)
    water_in=grid.add_zeros('water__unit_flux_in',at='node');flow=ConservativeFlowAccumulator(grid,flow_director='D8',depression_finder='DepressionFinderAndRouter')
    eroder=SpaceLargeScaleEroder(grid,K_sed=.000025,K_br=grid.at_node['K_sp'],F_f=0,phi=0,H_star=.5,v_s=.03,m_sp=.5,n_sp=1)
    diffuser=TaylorNonLinearDiffuser(grid,linear_diffusivity=.025,slope_crit=.7,dynamic_dt=True,if_unstable='raise')
    forcing=ParentForcing(parent,pdir,g,pg);_,qw,qs=forcing.at(0)
    # Inputs falling inside a fixed scene still pass through routing; erosion is
    # disabled by status. Sediment entering an exact scene is exported separately.
    T.savejson(out/'parent-boundary.json',{'parent':parent,'parentHeightSha256':T.sha(pdir/'height.npy'),'sourceSnapshotsYears':forcing.years,'sourceHashes':forcing.hashes,'forcing':'Time-dependent upstream discharge, sediment and boundary heights; routed crossings interpolated between parent snapshots. Child remains a nested sensitivity result, not blindly pasted into parent.'})
    clim=T.atmosphere(pi,g,kind);water_in[:]=clim['runoff'].ravel()+qw.ravel()/step**2
    totals={k:np.zeros_like(pi) for k in ['erosion','deposition','tectonic-uplift','slope-transport']};history=[];now=0;initial_h=h.copy();core=grid.core_nodes;area=step*step
    np.save(out/'initial.npy',pi.astype('float32'));np.save(out/'height-0.npy',pi.astype('float32'))
    flow.run_one_step()
    for key,field in [('discharge','surface_water__discharge'),('receiver','flow__receiver_node'),('sediment-flux','sediment__outflux')]:np.save(out/f'{key}-0.npy',grid.at_node[field].reshape(pi.shape))
    rate=np.zeros_like(pi) if isfine else T.sample(np.load(pdir/'uplift-rate.npy'),pg,g)*allow*controls['tectonic']
    for target in sorted(set([v for v in T.C['timesYears'][1:] if v<=end]+[end])):
        while now<target:
            dt=min(dtmax,target-now);before=float(z.sum()*area);fixed_before=z.copy();bound,qw,qs=forcing.at(now+dt)
            clim=T.atmosphere(z.reshape(pi.shape),g,kind);water_in[:]=clim['runoff'].ravel()*(kind.ravel()>=30)+qw.ravel()/step**2
            boundary_indices=np.flatnonzero(frame.ravel()==0);boundary_change=float(np.sum(bound.ravel()[boundary_indices]-z[boundary_indices])*area);z[boundary_indices]=bound.ravel()[boundary_indices];bed[boundary_indices]=z[boundary_indices]-h[boundary_indices]
            du=rate*dt*np.exp(-now/2500000);du.ravel()[grid.status_at_node!=NodeStatus.CORE]=0;z+=du.ravel();bed+=du.ravel();totals['tectonic-uplift']+=du
            weather.calc_soil_prod_rate();production=grid.at_node['soil_production__rate']*dt;production[grid.status_at_node!=NodeStatus.CORE]=0;bed-=production;h+=production
            # Lithology follows actual bedrock exposure, including block motion.
            lith.dz_advection=du.ravel();lith.rock_id=1;lith.run_one_step();eroder.K_br=grid.at_node['K_sp']*allow.ravel()*controls['water'].ravel()/np.maximum(.2,controls['rock-strength'].ravel())*(T.C['planet']['gravityMs2']/9.80665)
            eroder.K_sed=T.C['lithology']['sedimentK']*allow.ravel()*controls['water'].ravel()
            flow.run_one_step();water_expected=float(np.sum(water_in*grid.cell_area_at_node));sinks=grid.at_node['flow__receiver_node']==np.arange(grid.number_of_nodes);water_out=float(grid.at_node['surface_water__discharge'][sinks].sum());water_error=abs(water_out-water_expected)/max(1,water_expected)
            pre=z.copy();export=eroder.run_one_step(dt);totals['erosion']+=np.maximum(pre-z,0).reshape(pi.shape);totals['deposition']+=np.maximum(z-pre,0).reshape(pi.shape)
            extdep,extout=external_sediment(z,h,grid.at_node['flow__receiver_node'],grid.at_node['flow__upstream_node_order'],grid.at_node['surface_water__discharge'],qs.ravel(),area,dt,allow.ravel());totals['deposition']+=extdep.reshape(pi.shape);bed[:]=z-h
            # Conservative pairwise bedding/wind term, plus Landlab's nonlinear
            # diffuser on free terrain. Keep exact core constraints afterward.
            pre=z.copy()
            weighted_diffusion(grid,z,controls['planation'].ravel()*allow.ravel(),dt,step)
            diff=z-pre
            # Diffuser edge exchange is explicitly part of the boundary ledger.
            z[hard]=fixed_before[hard];h[hard]=initial_h[hard];bed[:]=z-h;diffusion_exchange=float((z-pre).sum()*area)
            zz,hh,dz=T.paired_flux(z.reshape(pi.shape),h.reshape(pi.shape),allow,step,dt,(grid.at_node['K_sp'].reshape(pi.shape)<T.C['lithology']['softK']).astype(float),1-clim['humidity'],(.25,-.8),controls['planation'],controls['aeolian'],controls['rock-strength'],T.C['planet']['gravityMs2']);z[:]=zz.ravel();h[:]=hh.ravel();bed[:]=z-h;totals['slope-transport']+=(z-pre).reshape(pi.shape)
            # The frozen scene reset above includes border cells; restore moving
            # exterior boundary and count its reservoir exchange independently.
            prev=z[boundary_indices].copy();z[boundary_indices]=bound.ravel()[boundary_indices];bed[boundary_indices]=z[boundary_indices]-h[boundary_indices];boundary_change+=float(np.sum(z[boundary_indices]-prev)*area)
            after=float(z.sum()*area);inp=float(qs.sum()*dt);exported=float(sum(export)+extout);expected=float(du.sum()*area)+boundary_change+inp-exported+diffusion_exchange;residual=after-before-expected
            history.append({'year':now+dt,'boundaryExchangeM3':boundary_change+diffusion_exchange,'upliftM3':float(du.sum()*area),'externalWaterM3yr':float(qw.sum()),'waterRelativeError':water_error,'externalSedimentM3':inp,'exportedM3':exported,'volumeResidualM3':float(residual),'relativeVolumeError':abs(residual)/max(1,abs(expected)+exported+inp)})
            now+=dt
            T.savejson(out/'progress.json',{'year':now,'targetYears':end,'steps':len(history),'lastStep':history[-1]})
        np.save(out/f'height-{target}.npy',z.reshape(pi.shape).astype('float32'));flow.run_one_step()
        for key,field in [('discharge','surface_water__discharge'),('receiver','flow__receiver_node'),('sediment-flux','sediment__outflux')]:np.save(out/f'{key}-{target}.npy',grid.at_node[field].reshape(pi.shape))
        T.log(f'LANDLAB {id}: {target} years')
    flow.run_one_step();final=z.reshape(pi.shape);clim=T.atmosphere(final,g,kind)
    for key,a in {'height':final,'kind':kind,'protected':protected,'discharge':grid.at_node['surface_water__discharge'].reshape(pi.shape),'receiver':grid.at_node['flow__receiver_node'].reshape(pi.shape),'sediment-flux':grid.at_node['sediment__outflux'].reshape(pi.shape),'soil':h.reshape(pi.shape),**totals,**clim}.items():np.save(out/(key+'.npy'),a.astype('int32') if key=='receiver' else a.astype('float32'))
    fixed=hard.reshape(pi.shape)&(frame>0);report={'components':['Landlab 2.11.0','FlowAccumulator D8','DepressionFinderAndRouter','LithoLayers','ExponentialWeatherer','SpaceLargeScaleEroder','weighted nonlinear hillslope flux','conservative inherited sediment and bedding/wind transport'],'effectiveYears':now,'stepYears':dtmax,'protectedMaxDeltaM':float(np.max(abs(final[fixed]-z0[fixed]))) if fixed.any() else 0,'parent':parent,'parentBoundaryMaxDeltaM':float(np.max(abs(final[frame==0]-bound[frame==0]))),'maxVolumeRelativeError':max(a['relativeVolumeError'] for a in history),'history':history}
    report['maxWaterRelativeError']=max(v['waterRelativeError'] for v in history);report['parentSnapshotsYears']=forcing.years
    report['passed']=report['protectedMaxDeltaM']<=1e-6 and report['parentBoundaryMaxDeltaM']<=1e-6 and report['maxVolumeRelativeError']<1e-7 and report['maxWaterRelativeError']<1e-8
    T.savejson(out/'simulation.json',report);T.log(f'REFINED {id}: {report["maxVolumeRelativeError"]:.3g} volume error')
    if not report['passed']:raise RuntimeError('Nested protection, boundary or conservation mismatch')
def main():
    global WORK
    ap=argparse.ArgumentParser();ap.add_argument('--region',default='all');ap.add_argument('--work',type=pathlib.Path,default=WORK);ap.add_argument('--mask',type=pathlib.Path);ap.add_argument('--dt',type=float,default=10000);ap.add_argument('--end',type=int,default=2000000);ap.add_argument('--suffix',default='');a=ap.parse_args();WORK=a.work;T.WORK=WORK;T.MASK=a.mask
    if (WORK/'run-config.json').exists():T.C=json.loads((WORK/'run-config.json').read_text())
    for r in T.C['refinements']:
        if a.region in ['all',r['id']]:
            try:run(r,dtmax=a.dt,end=a.end,suffix=a.suffix)
            except Exception as e:T.savejson(WORK/'refined'/(r['id']+a.suffix)/'failure.json',{'status':'failed','reason':str(e)});raise
            gc.collect()
if __name__=='__main__':main()
