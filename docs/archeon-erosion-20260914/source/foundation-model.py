"""A reproducible candidate, never a mutation of the accepted atlas.

AI supplies bounded morphology priors. Measured DEMs supply independent
topography, then a conservative water/sediment solver evolves the mixed field.
Effective erosion time is a modelling control, not a proposed Archeon history.
"""
import pathlib, sys, json, hashlib, math, time
ROOT=pathlib.Path(__file__).resolve().parents[1]; WORK=ROOT.parents[1]/'review/foundation-20260914'
sys.path.insert(0,str(WORK/'deps'))
import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter, map_coordinates, distance_transform_edt, zoom, label
from PIL import Image
import rasterio
from rasterio.features import rasterize
from affine import Affine
from pyproj import Proj
from numba import njit
import heapq
Image.MAX_IMAGE_PIXELS=None
OUT=ROOT/'foundation'; OUT.mkdir(exist_ok=True)
G=json.loads((WORK/'grid.json').read_text(encoding='utf-8')); S=json.loads((WORK/'geography.json').read_text(encoding='utf-8'))
P=Proj(G['projection']); SEED=5210914

def log(s): print(s,flush=True)
def smooth(a,s):
    if s<8:return gaussian_filter(a,s,mode='nearest').astype('float32')
    # Three box passes approximate a Gaussian without a thousand-tap kernel.
    n=max(3,round(math.sqrt(4*s*s+1)));n+=1-n%2
    a=a.astype('float32',copy=False)
    for _ in range(3):a=uniform_filter(a,n,mode='nearest')
    return a
def ease(a):
    a=np.clip(a,0,1); return a*a*(3-2*a)
def norm(a):
    q=np.percentile(a,[5,50,95]); return np.clip((a-q[1])/max(1e-6,(q[2]-q[0])/3.29),-3,3).astype('float32')
def sample(a,old,new):
    x=(new['xmin']+np.arange(new['width'])*new['stepM']-old['xmin'])/old['stepM']
    y=(old['ymax']-new['ymax']+np.arange(new['height'])*new['stepM'])/old['stepM']
    yy,xx=np.meshgrid(y,x,indexing='ij'); return map_coordinates(a,[yy,xx],order=1,mode='nearest').astype('float32')
def native(g):
    m=S['source']; z=np.memmap(ROOT/'terrain/aethelgard-height.f32',dtype='<f4',mode='r',shape=(m['height'],m['width']))
    xs=g['xmin']+np.arange(g['width'])*g['stepM']; ys=g['ymax']-np.arange(g['height'])*g['stepM']
    ii=np.clip(np.rint(xs*G['nativeScale']+G['nativeTranslate'][0]-.5).astype(int),0,m['width']-1)
    jj=np.clip(np.rint(-ys*G['nativeScale']+G['nativeTranslate'][1]-.5).astype(int),0,m['height']-1)
    mask=np.asarray(Image.open(ROOT/'terrain/aethelgard-mask.png').convert('L'))
    return np.asarray(z[np.ix_(jj,ii)]).copy(),mask[np.ix_(jj,ii)].copy()

def tiled(src,g,extent_km,salt,band=True):
    """Seeded non-periodic overlapping crops, rotations, and partition of unity.
    Every tile has 50% overlap. Crops vary independently; no edge stitching.
    Detail wavelength is removed above one fifth of each named scale.
    """
    n=max(4,round(extent_km*1000/g['stepM'])); stride=n//2
    h,w=g['height'],g['width']; out=np.zeros((h,w),np.float32); weight=np.zeros_like(out)
    if n<48:
        f=norm(src-smooth(src,src.shape[0]/5)) if band else src
        return smooth(quilt_small(f,h,w,n,SEED+salt),.7)
    t=(np.arange(n)+.5)/n; win=(np.sin(t*np.pi)**2).astype('float32'); window=win[:,None]*win[None,:]
    rng=np.random.default_rng(SEED+salt)
    for y in range(-stride,h,stride):
        for x in range(-stride,w,stride):
            side=src.shape[0]; sz=int(rng.uniform(.57,.96)*side); a=int(rng.integers(0,side-sz+1)); b=int(rng.integers(0,side-sz+1))
            tile=src[a:a+sz,b:b+sz]; tile=np.rot90(tile,int(rng.integers(4)))
            if rng.random()<.5: tile=tile[:,::-1]
            tile=zoom(tile,n/sz,order=1,prefilter=False)[:n,:n]
            if band: tile=tile-smooth(tile,n/5)
            tile=norm(tile)
            y0=max(0,y);x0=max(0,x);y1=min(h,y+n);x1=min(w,x+n)
            sl=np.s_[y0-y:y1-y,x0-x:x1-x]; wt=window[sl]
            out[y0:y1,x0:x1]+=tile[sl]*wt;weight[y0:y1,x0:x1]+=wt
    assert weight.min()>0
    out/=weight
    return out

@njit(cache=True)
def quilt_small(src,h,w,n,seed):
    out=np.empty((h,w),np.float32);stride=n/2.;size=src.shape[0]
    for y in range(h):
        for x in range(w):
            by=int(y/stride);bx=int(x/stride);value=0.;weight=0.
            for a in range(2):
                for b in range(2):
                    gy=by-a;gx=bx-b;u=(x-gx*stride)/n;v=(y-gy*stride)/n
                    if u<0 or v<0 or u>=1 or v>=1:continue
                    key=((gx+20000)*73856093 ^ (gy+20000)*19349663 ^ seed)&0x7fffffff
                    crop=.58+(key%1000)/1000*.36;ox=((key//17)%1000)/1000*(1-crop);oy=((key//53)%1000)/1000*(1-crop)
                    if key%2:u=1-u
                    if (key//2)%2:v=1-v
                    if (key//4)%2:u,v=v,u
                    sx=(ox+u*crop)*(size-1);sy=(oy+v*crop)*(size-1);ix=min(size-2,int(sx));iy=min(size-2,int(sy));fx=sx-ix;fy=sy-iy
                    z=(src[iy,ix]*(1-fx)+src[iy,ix+1]*fx)*(1-fy)+(src[iy+1,ix]*(1-fx)+src[iy+1,ix+1]*fx)*fy
                    wt=math.sin((x-gx*stride)/n*math.pi)**2*math.sin((y-gy*stride)/n*math.pi)**2
                    value+=z*wt;weight+=wt
            out[y,x]=value/max(weight,1e-9)
    return out

def dist(g,q):
    x,y=P(*q); xx=g['xmin']+np.arange(g['width'])*g['stepM']-x; yy=g['ymax']-np.arange(g['height'])*g['stepM']-y
    return np.hypot(yy[:,None],xx[None,:]).astype('float32')
def project_geom(g):
    def walk(c): return list(P(*c)) if isinstance(c[0],(int,float)) else [walk(v) for v in c]
    return {'type':g['type'],'coordinates':walk(g['coordinates'])}

@njit(cache=True)
def ridge_distance(h,w,step,xmin,ymax,points):
    distance=np.empty((h,w),np.float32);side=np.empty((h,w),np.float32)
    for y in range(h):
        py=ymax-y*step
        for x in range(w):
            px=xmin+x*step;best=1e30;bestside=0.
            for j in range(len(points)-1):
                ax,ay=points[j];bx,by=points[j+1];dx=bx-ax;dy=by-ay;l2=dx*dx+dy*dy
                t=max(0.,min(1.,((px-ax)*dx+(py-ay)*dy)/max(l2,1.)))
                ex=px-(ax+t*dx);ey=py-(ay+t*dy);d2=ex*ex+ey*ey
                if d2<best:best=d2;bestside=dx*(py-ay)-dy*(px-ax)
            distance[y,x]=math.sqrt(best);side[y,x]=bestside
    return distance,side

GEO_CACHE=None
def geological_protection(g):
    """Continuous landscape belts, expanded from the author's yellow/red markup.
    Orun's north-facing escarpment and SE backing plateau are a single protected
    structure; the SW Marneth flank runs beside it before the desert hinterland.
    """
    global GEO_CACHE
    if GEO_CACHE is None:
        ridges={f['id']:f for f in S['ridges']}
        def field(id):
            p=np.array([P(*q) for q in ridges[id]['geometry']['coordinates']])
            return ridge_distance(G['height'],G['width'],G['stepM'],G['xmin'],G['ymax'],p)
        od,os=field('orun');sd,ss=field('marneth-sw');md,ms=field('marneth')
        plateau=((os<0)&(od<1100000))|((ss<0)&(sd<900000))
        hard=(od<110000)|plateau
        # Keep the relationship, permitting only a quarter of the proposed
        # reconstruction inside the remaining main Marneth mountain envelope.
        soft=1-.75*ease((230000-np.minimum(md,sd))/100000)
        GEO_CACHE=(hard.astype('float32'),soft.astype('float32'),plateau.astype('float32'))
    if g is G:return GEO_CACHE
    return tuple(sample(a,G,g) for a in GEO_CACHE)

def locks(g,base,kind):
    # Fixed terrain cores are also impermeable to geomorphic material exchange;
    # routing still crosses them. Only documented scene footprints are locked.
    lake_labels,nlake=label(kind==200);counts=np.bincount(lake_labels.ravel());large_lakes=(kind==200)&(counts[lake_labels]*g['stepM']**2>=200e6)
    core=large_lakes|(kind==0)|(kind==80); dsk=dist(g,[24,32]); core[(dsk<28000)&(kind>=30)]=False
    reasons=[]
    sizes={'FC':25000,'AT':20000,'CR':12000,'RB':28000,'WI':15000,'V01':24000,'AX':18000,'WH':25000}
    for f in S['markers']:
        if f['id'] in ['SK','KG','V02']: continue
        r=sizes.get(f['id'],8000)
        if f['id']=='AT': q=S['atheria']['center']
        else: q=f['geometry']['coordinates']
        d=dist(g,q);core|=d<r
        reasons.append({'id':f['id'],'name':f['properties']['name'],'coord':q,'radiusM':r,'mode':'exact scene core'})
    # Preserve the full validated Windbreak/Orun simulation as a separate fine source.
    core|=dist(g,S['orunLocal']['center'])<50000
    aff=Affine(g['stepM'],0,g['xmin']-g['stepM']/2,0,-g['stepM'],g['ymax']+g['stepM']/2)
    for f in S['landmarkSurfaces']:
        raster=rasterize([(project_geom(f['geometry']),1)],out_shape=base.shape,transform=aff,dtype='uint8')>0
        if raster.any(): core|=distance_transform_edt(~raster)*g['stepM']<6000
    geo,soft,_=geological_protection(g);core|=(geo>.999)&(kind>=30)
    # Old inferred pond dots must not drill round low-altitude holes into new
    # mountains. Keep major lakes and scene-related water; re-evaluate other
    # small lakes in the next hydrological stage. The accepted mask is untouched.
    released=(kind==200)&~core&(dsk>13000);kind[released]=40
    # Six km coastal buffer keeps existing coastline and coastal cliffs exact.
    coast=distance_transform_edt(kind>=30)*g['stepM'];core|=coast<6000
    fade=ease(distance_transform_edt(~core)*g['stepM']/36000).astype('float32')
    fade*=soft
    return core,fade,reasons

def climate(z,g,kind):
    """Two representative seasons. Terrain-conditioned estimate, not a GCM."""
    h,w=z.shape; dx=g['stepM']; coast=distance_transform_edt(kind>=30)*dx
    yg=g['ymax']-np.arange(h)*dx; xg=g['xmin']+np.arange(w)*dx
    # Latitude on a coarser grid avoids storing two full coordinate meshes.
    yy,xx=np.meshgrid(yg[::8],xg[::8],indexing='ij'); lat=P(xx,yy,inverse=True)[1]
    lat=zoom(lat,(h/lat.shape[0],w/lat.shape[1]),order=1)[:h,:w]
    zs=smooth(z,max(1,12000/dx)); gy,gx=np.gradient(zs,dx)
    seaSupply=.32+.9*np.exp(-coast/380000)
    wet=[]
    for vx,vy,season in [(.82,.57,1.0),(-.65,.76,.62)]:
        up=smooth(np.maximum(gx*vx+gy*vy,0),max(1,8000/dx))
        # Upwind relief governs a rain shadow. No old route geometry enters.
        shadow=np.zeros_like(z)
        for km,wt in [(40,.3),(100,.4),(200,.3)]:
            from scipy.ndimage import shift
            upstream=shift(zs,(vy*km*1000/dx,vx*km*1000/dx),order=1,mode='nearest',prefilter=False)
            shadow+=wt*np.maximum(0,upstream-zs)
        rain=(.5+seaSupply+np.minimum(1.9,up*30))*np.exp(-shadow/1700)*season
        wet.append(rain.astype('float32'))
    rain=.65*wet[0]+.35*wet[1]; temp=30-.29*np.abs(lat)-.0056*z
    pet=np.maximum(.08,(temp+5)*.039).astype('float32')
    evap=np.minimum(rain,pet*(.55+.25*np.exp(-coast/1000000)))
    surplus=np.maximum(0,rain-evap);recharge=surplus*.22;runoff=surplus-recharge
    return {'rain':rain,'adverseRain':wet[1],'temperature':temp.astype('float32'),'evap':evap.astype('float32'),'recharge':recharge,'runoff':runoff}

@njit(cache=True)
def flood_route(z,land,dx):
    """Priority flood supplies virtual lake spill levels, without raising bedrock."""
    h,w=z.shape;n=h*w;flat=z.ravel();ok=land.ravel();seen=np.zeros(n,np.uint8);filled=flat.astype(np.float64).copy()
    heap=[(-1e30,-1)];heapq.heappop(heap)
    order=np.empty(n,np.int32);cnt=0
    for i in range(n):
        r=i//w;c=i%w
        if not ok[i]: seen[i]=1;continue
        edge=r==0 or c==0 or r==h-1 or c==w-1
        if not edge: edge=not(ok[i-1] and ok[i+1] and ok[i-w] and ok[i+w])
        if edge: seen[i]=1;heapq.heappush(heap,(filled[i],i))
    while heap:
        v,i=heapq.heappop(heap);order[cnt]=i;cnt+=1;r=i//w;c=i%w
        for dr in range(-1,2):
            for dc in range(-1,2):
                if dr==0 and dc==0:continue
                rr=r+dr;cc=c+dc
                if rr<0 or cc<0 or rr>=h or cc>=w:continue
                j=rr*w+cc
                if seen[j]:continue
                seen[j]=1;filled[j]=max(flat[j],v+.00001);heapq.heappush(heap,(filled[j],j))
    rec=np.full(n,-1,np.int32);slope=np.zeros(n,np.float32)
    for a in range(cnt):
        i=order[a];r=i//w;c=i%w;best=0.
        for dr in range(-1,2):
            for dc in range(-1,2):
                if dr==0 and dc==0:continue
                rr=r+dr;cc=c+dc
                if rr<0 or cc<0 or rr>=h or cc>=w:continue
                j=rr*w+cc;sl=(filled[i]-filled[j])/(dx*math.sqrt(dr*dr+dc*dc))
                if sl>best:best=sl;rec[i]=j
        slope[i]=best
    return filled.reshape(h,w),order[:cnt],rec,slope

@njit(cache=True)
def discharge(order,rec,runoff,area):
    q=runoff.ravel().astype(np.float64)*area
    for a in range(len(order)-1,-1,-1):
        i=order[a];j=rec[i]
        if j>=0:q[j]+=q[i]
    return q

@njit(cache=True)
def erosion_step(z,filled,order,rec,q,slope,hard,allow,dx,dt,rain_scale=1.):
    """Finite-volume sediment ledger with flux through frozen scene cores.
    Stream power removes material; transport capacity and settling deposit it.
    Every removed cubic metre is deposited, retained in a closed sink, or exported.
    """
    zz=z.ravel().astype(np.float64); n=len(zz); area=dx*dx; incoming=np.zeros(n,np.float64)
    er=np.zeros(n,np.float32);dep=np.zeros(n,np.float32);export=0.;retained=0.
    mask=allow.ravel();rock=hard.ravel(); fl=filled.ravel()
    for a in range(len(order)-1,-1,-1):
        i=order[a];j=rec[i];water=max(0.,q[i]*rain_scale);s=max(0.,slope[i]);lake=fl[i]-zz[i]>.1
        if j>=0 and mask[i]>0 and not lake:
            drop=max(0.,zz[i]-zz[j]);k=2.8e-5/(.45+rock[i]*2.8)
            e=min(35.,drop*.18,k*math.sqrt(water)*s*dt)*mask[i]
            zz[i]-=e;er[i]=e;incoming[i]+=e*area
        sediment=incoming[i]
        if sediment<=0:continue
        if j<0:
            retained+=sediment;continue
        # Capacity declines sharply on flatter ground, producing alluvial fans.
        capacity=water*dt*.002*min(1.,s/.04)
        settle=1.-math.exp(-.018*area/max(water,1.))
        d=max(sediment*settle,sediment-capacity)/area
        if lake:d=max(d,min(sediment/area,max(0.,fl[i]-zz[i])*.25))
        d=min(d,sediment/area,10.)*mask[i]
        # Do not invert a reach. Excess sediment is carried to the next cell.
        if not lake:d=min(d,max(0.,fl[i]-zz[i])+2.)
        zz[i]+=d;dep[i]=d;sediment-=d*area
        if j>=0:incoming[j]+=sediment
    # Receivers outside the land domain are outlets; count their accumulated solids.
    in_order=np.zeros(n,np.uint8)
    for i in order:in_order[i]=1
    for i in range(n):
        if in_order[i]==0:export+=incoming[i]
    return zz.reshape(z.shape).astype(np.float32),er.reshape(z.shape),dep.reshape(z.shape),export,retained

def hillslope(z,allow,dx,dt):
    """Conservative pairwise creep plus threshold slumping; no global blur."""
    dz=np.zeros_like(z)
    for axis in [0,1]:
        s1=[slice(None),slice(None)];s2=s1.copy();s1[axis]=slice(0,-1);s2[axis]=slice(1,None);a=tuple(s1);b=tuple(s2)
        diff=z[a]-z[b];can=np.minimum(allow[a],allow[b]);creep=diff*(.08*dt/dx**2)
        slump=np.sign(diff)*np.maximum(0,np.abs(diff)-dx*.62)*.18
        move=(creep+slump)*can;dz[a]-=move;dz[b]+=move
    return z+dz

def evolve(z,g,kind,allow,hard,steps=18):
    dx=g['stepM'];land=(kind>=30)&(kind!=80);land[[0,-1],:]=False;land[:,[0,-1]]=False
    all_er=np.zeros_like(z);all_dep=np.zeros_like(z);history=[]
    for it in range(steps):
        c=climate(z,g,kind) if it%6==0 else c
        filled,order,rec,sl=flood_route(z,land,dx);q=discharge(order,rec,c['runoff']*land,dx*dx)
        before=z.copy();z,er,de,export,ret=erosion_step(z,filled,order,rec,q,sl,hard,allow,dx,2500.)
        z=hillslope(z,allow,dx,2500.)
        all_er+=er;all_dep+=de
        removed=float(er.sum(dtype=np.float64)*dx*dx);deposited=float(de.sum(dtype=np.float64)*dx*dx)
        balance=removed-deposited-export-ret
        record={'iteration':it+1,'effectiveYears':(it+1)*2500,'erosionM3':removed,'depositionM3':deposited,'exportM3':export,'retainedSuspendedM3':ret,'sedimentBalanceRelativeError':abs(balance)/max(1,removed),'meanHeightChangeM':float(np.mean(np.abs(z-before)[land]))}
        assert record['sedimentBalanceRelativeError']<2e-5,record
        history.append(record)
        if it%3==0 or it==steps-1:log(f"{g.get('id','continent')} iteration {it+1}/{steps}: mean change {record['meanHeightChangeM']:.3f} m; sediment error {record['sedimentBalanceRelativeError']:.2g}")
    c=climate(z,g,kind);filled,order,rec,sl=flood_route(z,land,dx);q=discharge(order,rec,c['runoff']*land,dx*dx)
    return z,all_er,all_dep,c,q.reshape(z.shape),np.maximum(0,filled-z).astype('float32'),history

def ecology(z,g,kind,c,dep,hard):
    """Young introduced ecology, conditional on water, temperature and substrate."""
    fertility=ease((c['rain']-.25)/1.35)*ease((c['temperature']+1)/13)*ease((34-c['temperature'])/14)
    fertility*=np.clip(.45+dep*.08+(1-hard)*.4,.1,1)
    seed=np.zeros_like(z)
    for f in S['markers']:
        if f['id'] in ['SK','FC','AT','CA','MI','IH','RB','TH','CP']:
            d=dist(g,f['geometry']['coordinates']);seed=np.maximum(seed,np.exp(-(d/145000)**2))
    # The back-plateau is outside the main terraform footprint. Existing local
    # watercut refuges may remain, without turning the whole desert green.
    _,_,dry=geological_protection(g);refuge=np.zeros_like(z)
    for id in ['RB','WI','WH','AX','RT']:
        f=next(f for f in S['markers'] if f['id']==id)
        refuge=np.maximum(refuge,np.exp(-(dist(g,f['geometry']['coordinates'])/28000)**2))
    seed*=1-dry*(1-refuge)*.98
    # 521 years of patch-limited spread; this is separate from geological time.
    cover=np.clip(seed*.6,0,.9)
    for _ in range(52):
        neighbour=smooth(cover,max(1,7000/g['stepM']))
        cover+=.13*fertility*cover*(1-cover)+.032*fertility*neighbour*(1-cover)-.055*(1-fertility)*cover
        cover=np.clip(cover,0,1)
    cover[(kind==0)|(kind==80)|(kind==200)]=0
    cover*=1-dry*(1-refuge)*.98
    return cover.astype('float32'),fertility.astype('float32')

def build():
    assert hashlib.file_digest(open(ROOT/'terrain/aethelgard-height.f32','rb'),'sha256').hexdigest()==G['sourceHeightSha256'],'Accepted source changed; regenerate and review the input snapshot first.'
    refs={}
    for key in ['stepped','basalt','mountain']:
        with rasterio.open(WORK/'references'/f'{key}.tif') as ds: refs[key]=norm(ds.read(1))
    for key in ['rift','snow','mesa']:refs[key]=norm(np.load(WORK/'references'/f'{key}.npy'))
    ai={k:norm(np.asarray(Image.open(OUT/'seeds'/f'{k}.png').convert('L'),dtype=np.float32)) for k in ['continent','1000km','500km','200km','50km','10km']}
    base=np.load(WORK/'base.npy');kind=np.load(WORK/'input-kind.npy');original_kind=kind.copy();core,fade,reasons=locks(G,base,kind)
    log('Building independent multiscale bedrock priors')
    macro=smooth(base,24);mount=ease((smooth(base,36)-1300)/3000)
    yy,xx=np.meshgrid(G['ymax']-np.arange(G['height'])*G['stepM'],G['xmin']+np.arange(G['width'])*G['stepM'],indexing='ij')
    lon,lat=P(xx,yy,inverse=True);plateau=ease((18-lat)/5)*ease((20-lon)/7)*(1-mount*.55)
    del xx,yy,lon,lat
    continental=zoom(ai['continent'],(base.shape[0]/ai['continent'].shape[0],base.shape[1]/ai['continent'].shape[1]),order=1)[:base.shape[0],:base.shape[1]]
    continental=smooth(continental,36)
    a1000=tiled(ai['1000km'],G,1000,1);a500=tiled(ai['500km'],G,500,2);a200=tiled(ai['200km'],G,200,3)
    realMountain=tiled(refs['snow'],G,220,10)*.62+tiled(refs['mountain'],G,300,11)*.38
    realPlateau=tiled(refs['rift'],G,180,12)*.55+tiled(refs['stepped'],G,260,13)*.45
    realSmall=tiled(refs['mesa'],G,100,14)*.45+tiled(refs['basalt'],G,140,15)*.55
    # Author approved a fresh creation across the unprotected periphery.
    # Broad fault-block provinces now contribute their own elevation, not merely
    # a roughness overlay on the old painted surface.
    free=np.ones_like(base)
    for f in S['markers']:
        if f['id']!='V02':free=np.minimum(free,ease(dist(G,f['geometry']['coordinates'])/320000))
    free*=1-mount*.78
    province=tiled(refs['rift'],G,1000,71,False)*.48+tiled(refs['mesa'],G,500,72,False)*.27+a1000*.25
    fresh=.38*macro+850+province*920
    fresh=100+260*np.logaddexp(0,(fresh-100)/260)
    coast=ease((distance_transform_edt(kind>=30)*G['stepM']-6000)/130000)
    macro=macro+(fresh-macro)*free*coast
    newMountain=ease((smooth(macro,18)-1100)/2700)
    mount=np.maximum(mount,newMountain)
    plateau=np.maximum(plateau,np.clip((province+.8)/2.3,0,1)*free*.85)
    small50=tiled(ai['50km'],G,50,73);small10=tiled(ai['10km'],G,10,74)
    # Macro position comes from the current atlas; seeds replace short drawn ridges.
    relief=(continental*170+a1000*300+a500*290+a200*130)*(0.12+mount*.85+plateau*.3)
    relief+=realMountain*(70+mount*800)+realPlateau*(70+plateau*470)+realSmall*(35+mount*120+plateau*210)
    relief+=small50*(12+mount*35+plateau*25)+small10*(2+mount*5+plateau*3)
    candidate=macro+relief
    # Three author-requested northern highland candidates. Locations are input
    # hypotheses; their ridges/valleys come from transformed measured DEMs.
    # No Gaussian mountain is painted into the accepted height raster.
    northern=[([-24,33],360000,240000,-.5,0),([-14,35],300000,340000,.35,1),([-3,38],400000,230000,-.3,2)]
    for q0,rx,ry,angle,variant in northern:
        cx,cy=P(*q0);xx=G['xmin']+np.arange(G['width'])*G['stepM']-cx;yy=G['ymax']-np.arange(G['height'])*G['stepM']-cy
        u=(xx[None,:]*math.cos(angle)+yy[:,None]*math.sin(angle))/rx
        v=(-xx[None,:]*math.sin(angle)+yy[:,None]*math.cos(angle))/ry
        src=np.rot90(refs['snow' if variant!=1 else 'mountain'],variant)
        measured=map_coordinates(src,[(v/3+.5)*(src.shape[0]-1),(u/3+.5)*(src.shape[1]-1)],order=1,mode='reflect')
        footprint=ease((1.6-np.sqrt(u*u+v*v))/.9)
        # An irregular ridge footprint follows measured relief, while low valleys
        # remain between blocks. 1000/500 km seed fields perturb shoulders.
        mass=(800+3900*np.clip((measured+.9)/3.7,0,1)**1.25)*footprint
        candidate+=mass
    del xx,yy,u,v,measured,mass,footprint
    # Smooth upper saturation avoids flattened peaks at a hard max-height clamp.
    hi=candidate>6800;candidate[hi]=6800+1100*np.tanh((candidate[hi]-6800)/1100)
    candidate=np.maximum(2,candidate)
    initial=base+(candidate-base)*fade
    dsk=dist(G,[24,32]); basin=ease((24000-dsk)/12000)
    # Existing crater, Gate and settlement coordinates survive. This 1000 m datum
    # is the sole explicit height exception approved by the author.
    target=1000+np.minimum(80,(dsk/13000)**2*55)
    initial=initial*(1-basin)+target*basin
    initial[kind==0]=base[kind==0]
    hard=np.clip(.42+plateau*.35+mount*.18+smooth(realSmall,4)*.08,.12,.95).astype('float32')
    allow=fade.copy();allow[kind==200]=0;allow[core]=0;allow[dsk<13000]=0
    initial=initial.astype('float32');np.save(WORK/'initial.npy',initial)
    z,er,de,c,q,pond,hist=evolve(initial,G,kind,allow,hard)
    cover,fert=ecology(z,G,kind,c,de,hard)
    fields={'baseline':base,'initial':initial,'height':z,'kind':kind,'baseline-kind':original_kind,'protected':core.astype('uint8'),'blend':fade,'hardness':hard,'erosion':er,'deposition':de,'rain':c['rain'],'adverse-rain':c['adverseRain'],'temperature':c['temperature'],'runoff':c['runoff'],'discharge':q.astype('float32'),'pond-depth':pond,'vegetation':cover,'fertility':fert}
    for key,a in fields.items():np.save(WORK/(key+'.npy'),a)
    np.save(WORK/'reconstruction-delta.npy',initial-base)
    np.save(WORK/'simulation-delta.npy',z-initial)
    # Meaningful causal checks isolate a solver step on identical input/flow.
    land=(kind>=30)&(kind!=80);land[[0,-1],:]=False;land[:,[0,-1]]=False
    filled,order,rec,sl=flood_route(initial,land,G['stepM']);cq=discharge(order,rec,c['runoff']*land,G['stepM']**2)
    e0=erosion_step(initial,filled,order,rec,cq,sl,hard,allow,G['stepM'],2500.)[1]
    ewet=erosion_step(initial,filled,order,rec,cq,sl,hard,allow,G['stepM'],2500.,1.5)[1]
    erock=erosion_step(initial,filled,order,rec,cq,sl,hard*2,allow,G['stepM'],2500.)[1]
    assert ewet.sum()>e0.sum() and erock.sum()<e0.sum()
    watererror=float(np.max(np.abs(c['rain']-c['evap']-c['recharge']-c['runoff'])))
    assert watererror<1e-5
    assert np.array_equal(z[core],base[core])
    records={'version':'archeon-foundation-creation-v2-20260914','seed':SEED,'status':'candidate; current production terrain is unchanged','grid':G,'sources':json.loads((WORK/'references/manifest.json').read_text())+json.loads((WORK/'references/satellite-manifest.json').read_text()),'protected':reasons,'history':hist,'tests':{'protectedSampleMaxDeltaM':float(np.max(np.abs(z[core]-base[core]))),'annualWaterBalanceMaxErrorM':watererror,'wetRunErosionRatio':float(ewet.sum()/e0.sum()),'hardRockErosionRatio':float(erock.sum()/e0.sum())},'model':{'effectiveErosionYears':45000,'terraformEcologyYears':521,'geologicalTimeStatus':'effective solver time, not historical canon','rainStatus':'two-season terrain-conditioned estimate, not a general circulation model','lakeRouting':'virtual spill levels for runoff; bedrock is never globally filled','iceStatus':'temperature-dependent snow display only; ice flow/erosion is not yet simulated','seedAmplitudeStatus':'uncalibrated AI brightness converted to bounded zero-mean priors; physical metres follow declared blending weights','resolution':'continent 2 km; periphery 1 km; protected-area comparison 250 m; existing Orun 64 m preserved','plateCount':'not inferred from bulk density; fault-block diversity is a morphological prior'},'stats':{'meanAbsoluteReconstructionChangeM':float(np.mean(np.abs(initial-base)[land])),'meanAbsolutePhysicsChangeM':float(np.mean(np.abs(z-initial)[land])),'heightPercentilesM':np.percentile(z[land],[0,5,50,95,99,100]).tolist(),'greenCoverageFraction':float(np.mean(cover[land]>.25))}}
    (WORK/'model-report.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    log(json.dumps(records['tests']))
    # All fine outputs sample the same continental parent, then add only shorter
    # residual bands. Parent blends occupy the outside fifth of each patch.
    for id,q0,widthkm in [('marneth',[22,32],512),('riverbend',[-10,9],160),('frontier',[0,26],160),('skyleaf',[24,32],128),('northwest',[-41,34],640),('north',[-12,44],640),('west',[-36,11],640),('southeast',[23,6],640),('north-highland-west',[-24,33],800),('north-highland-center',[-14,35],800),('north-highland-east',[-3,38],800)]:
        step=1000 if widthkm>=600 else 250
        n=round(widthkm*1000/step)+1;x,y=P(*q0)
        g={**G,'id':id,'width':n,'height':n,'stepM':step,'xmin':x-widthkm*500,'ymax':y+widthkm*500,'center':q0}
        b,k=native(g); original_k=k.copy(); parent=sample(z,G,g);finecore,finefade,_=locks(g,b,k)
        edge=np.minimum.outer(np.minimum(np.arange(n),np.arange(n)[::-1]),np.minimum(np.arange(n),np.arange(n)[::-1]));edge=ease(edge/(n*.17))
        detail=tiled(ai['50km'],g,50,30)*.23+tiled(ai['10km'],g,10,31)*.08
        detail+=tiled(refs['snow' if id in ['marneth','skyleaf'] else 'rift'],g,55,32)*.52+tiled(refs['stepped'],g,15,33)*.17
        amplitude=50+ease((parent-1200)/2500)*180
        f=parent+detail*amplitude*edge*finefade
        f=b+(f-b)*finefade
        if id in ['marneth','skyleaf']:
            d=dist(g,[24,32]);bn=ease((24000-d)/12000);targ=1000+np.minimum(80,(d/13000)**2*55)
            f=f*(1-bn)+targ*bn
        f[(k==0)|(k==80)]=b[(k==0)|(k==80)]
        al=finefade*edge;al[(k==200)|finecore]=0
        if id in ['marneth','skyleaf']:al[dist(g,[24,32])<13000]=0
        fh=sample(hard,G,g)
        f0=f.astype('float32'); f,fe,fd,fc,fq,fp,fhist=evolve(f0,g,k,al,fh,steps=6)
        fol=WORK/id;fol.mkdir(exist_ok=True)
        for key,a in {'baseline':b,'initial':f0,'height':f,'kind':k,'protected':finecore.astype('uint8'),'rain':fc['rain'],'adverse-rain':fc['adverseRain'],'temperature':fc['temperature'],'discharge':fq.astype('float32'),'erosion':fe,'deposition':fd,'vegetation':sample(cover,G,g),'hardness':fh}.items():np.save(fol/(key+'.npy'),a)
        np.save(fol/'baseline-kind.npy',original_k)
        (fol/'grid.json').write_text(json.dumps(g,indent=2));(fol/'history.json').write_text(json.dumps(fhist,indent=2))
        log(f'Fine patch ready: {id} {n} x {n}')

if __name__=='__main__':build()
