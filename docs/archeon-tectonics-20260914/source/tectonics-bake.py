"""Full-resolution terrain and atmospheric proxy maps, no web compression build."""
import pathlib,sys,importlib,json,hashlib,gc
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');E=importlib.import_module('tectonics-export');np=T.np;Image=T.Image
OUT=T.WORK/'baked';OUT.mkdir(exist_ok=True)
RANGES={'height':(-4096,16384,'m'),'rain':(0,4,'m/year'),'temperature':(-100,60,'degC'),'humidity':(0,1,'fraction'),'cloud':(0,1,'condensation potential'),'pressure':(15000,130000,'Pa'),'wind-east':(-15,15,'m/s'),'wind-north':(-15,15,'m/s'),'erosion':(0,16384,'m'),'deposition':(0,4096,'m'),'magmatic-uplift':(-4096,8192,'m'),'basalt-thickness':(0,8192,'m')}
manifest={'version':T.C['version'],'source':'numerical simulation','selectedSeed':5210914,'regions':{},'runtime':'read baked textures and metadata; simulation remains offline','atmosphere':'terrain/latitude/season proxy, not general circulation or cloud microphysics','noWebsiteCompressionOrPublication':True}
for id in T.C['regions']:
    folder=T.WORK/id/'5210914'
    if not(folder/'simulation.json').exists():continue
    g=json.loads((T.WORK/id/'grid.json').read_text());out=OUT/id;out.mkdir(exist_ok=True);fields={}
    for field,(lo,hi,units) in RANGES.items():
        path=folder/(field+'.npy');a=np.load(path);u=np.rint(np.clip((a-lo)/(hi-lo),0,1)*65535).astype('uint16');dest=out/(field+'-u16.png');Image.fromarray(u).save(dest,compress_level=2)
        fields[field]={'file':id+'/'+dest.name,'encoding':'uint16 PNG','decode':{'offset':lo,'scale':(hi-lo)/65535},'units':units,'shape':[g['height'],g['width']],'numericalSource':str(path),'sourceSha256':T.sha(path),'textureSha256':T.sha(dest),'clippedSamples':int(np.count_nonzero((a<lo)|(a>hi)))}
        del a,u
    z=np.load(folder/'height.npy');gy,gx=np.gradient(z,g['stepM']);normal=np.stack([-gx,gy,np.ones_like(z)],axis=-1);normal/=np.linalg.norm(normal,axis=-1)[:,:,None];Image.fromarray(np.rint((normal*.5+.5)*255).astype('uint8')).save(out/'normal.png',compress_level=2)
    col=np.zeros((*z.shape,3),np.float32)+[169,139,108];col+=((np.sin(z/90)*.5+.5)*T.ease((np.hypot(gx,gy)-.025)/.15))[:,:,None]*[13,9,7];col+=np.clip(z/10000,0,1)[:,:,None]*[-30,-20,-8];Image.fromarray(np.clip(col,0,255).astype('uint8')).save(out/'rock-albedo.png',compress_level=2)
    Image.fromarray(np.load(folder/'kind.npy').astype('uint8')).save(out/'surface-kind.png',compress_level=2)
    fields['normal']={'file':id+'/normal.png','encoding':'RGB8, normal=(-dz/dx,+dz/drow,1), normalized, mapped [-1,1] to [0,255]','sha256':T.sha(out/'normal.png')};fields['albedo']={'file':id+'/rock-albedo.png','encoding':'RGB8 unlit rock preview, no vegetation claim','sha256':T.sha(out/'rock-albedo.png')};fields['kind']={'file':id+'/surface-kind.png','encoding':'0 ocean, 80 unknown, 200 lake; other values from current atlas','sha256':T.sha(out/'surface-kind.png')}
    manifest['regions'][id]={'grid':g,'fields':fields};gc.collect();T.log('FULL BAKE '+id)
T.savejson(OUT/'manifest.json',manifest)
