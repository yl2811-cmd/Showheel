'use strict';
// Loopback-only editor. No arbitrary command, filesystem path or URL is accepted.
const http=require('http'),fs=require('fs'),path=require('path'),crypto=require('crypto'),{spawn}=require('child_process');
const ROOT=path.resolve(__dirname,'..'),WORK=path.resolve(ROOT,'../../review/tectonics-20260914/preview-v2'),PORT=Number(process.env.TECTONICS_PORT)||8796;
const config=JSON.parse(fs.readFileSync(path.join(ROOT,'data/tectonics-config.json'))),regions=new Set([...Object.keys(config.regions),...config.refinements.map(r=>r.id)]),processes=new Set(['tectonic','fault-bend','magmatism','water','weathering','aeolian','planation','protection','rock-strength','soil','seeding']);
const python='C:/Users/yl281/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',masks=path.join(WORK,'masks'),jobsDir=path.join(WORK,'jobs');fs.mkdirSync(masks,{recursive:true});fs.mkdirSync(jobsDir,{recursive:true});let running=null;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex'),reply=(res,status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data))};
function validate(body){if(body.version!==1||!regions.has(body.region))throw Error('未知区域或权重版本');if(!Number.isInteger(body.width)||!Number.isInteger(body.height)||body.width<2||body.height<2||body.width>768||body.height>768)throw Error('权重尺寸超出范围');if(!body.fields||typeof body.fields!=='object'||Array.isArray(body.fields))throw Error('缺少过程权重');for(const[k,a]of Object.entries(body.fields)){if(!processes.has(k)||!Array.isArray(a)||a.length!==body.width*body.height)throw Error('无效的过程或尺寸');const max=k==='protection'?1:2;if(a.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0||v>max))throw Error('权重必须在允许范围内')}return body}
function readBody(req){return new Promise((resolve,reject)=>{let size=0,chunks=[];req.on('data',b=>{size+=b.length;if(size>16*1024*1024){reject(Error('权重文件过大'));req.destroy()}else chunks.push(b)});req.on('end',()=>{try{resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')))}catch(e){reject(Error('无效 JSON'))}});req.on('error',reject)})}
function atomic(file,bytes){const temp=file+'.tmp';fs.writeFileSync(temp,bytes);fs.renameSync(temp,file)}
function jobState(id){if(!/^[0-9]{13}-[a-f0-9]{8}$/.test(id))return null;const file=path.join(jobsDir,id,'job.json');return fs.existsSync(file)?JSON.parse(fs.readFileSync(file)):null}
const server=http.createServer(async(req,res)=>{try{const url=new URL(req.url,'http://127.0.0.1:'+PORT),pathname=decodeURIComponent(url.pathname);
 if(pathname.startsWith('/api/tectonics/')){
  if(req.method==='POST'){
   if(req.headers.origin!=='http://127.0.0.1:'+PORT||!String(req.headers['content-type']).startsWith('application/json'))return reply(res,403,{error:'仅接受此本地页面发起的 JSON 操作'});
   const body=await readBody(req);
   if(pathname==='/api/tectonics/mask'){const checked=validate(body),name=checked.region+'.json',file=path.join(masks,name);let saved=fs.existsSync(file)?JSON.parse(fs.readFileSync(file)):{version:1,region:checked.region,layers:{}};if(!saved.layers)saved={version:1,region:checked.region,layers:{[saved.viewId||saved.region]:saved}};saved.layers[checked.viewId||checked.region]=checked;const bytes=Buffer.from(JSON.stringify(saved));atomic(file,bytes);return reply(res,200,{name,sha256:hash(bytes),bytes:bytes.length})}
   if(pathname==='/api/tectonics/run'){
    if(running)return reply(res,409,{error:'已有一个画笔候选正在计算，请等待它完成。'});
    if(!regions.has(body.region)||!config.seeds.includes(body.seed)||![100000,2000000].includes(body.years))return reply(res,400,{error:'无效的区域、种子或时间'});
    const source=path.join(masks,body.region+'.json');if(!fs.existsSync(source)||hash(fs.readFileSync(source))!==body.maskSha256)return reply(res,409,{error:'权重已变化，请重新保存后运行。'});
    if(body.gridM!==undefined&&![16000,2000].includes(body.gridM))return reply(res,400,{error:'无效的网格精度'});
    if(body.faultDensity!==undefined&&![1,1.5,2].includes(body.faultDensity))return reply(res,400,{error:'无效的断层密度'});
    if(body.magmaticIntensity!==undefined&&![0.6,1,1.5].includes(body.magmaticIntensity))return reply(res,400,{error:'无效的岩浆活动强度'});
    const id=Date.now()+'-'+crypto.randomBytes(4).toString('hex'),dir=path.join(jobsDir,id);fs.mkdirSync(dir);fs.copyFileSync(source,path.join(dir,'mask.json'));const job={id,status:'running',region:body.region,seed:body.seed,years:body.years,gridM:body.gridM||16000,faultDensity:body.faultDensity||config.faultDensity,magmaticIntensity:body.magmaticIntensity||1,created:new Date().toISOString(),url:'/tectonics.html?job='+id};atomic(path.join(dir,'job.json'),Buffer.from(JSON.stringify(job)));
    const stdout=fs.openSync(path.join(dir,'run.log'),'a'),child=spawn(python,[path.join(ROOT,'src/tectonics-job.py'),id],{cwd:ROOT,windowsHide:true,env:{...process.env,TECTONICS_WORK:WORK,PYTHONUTF8:'1',MPLCONFIGDIR:path.join(WORK,'mpl')},stdio:['ignore',stdout,stdout]});running={id,child};child.on('error',e=>finish('failed',e.message));child.on('exit',code=>finish(code===0?'complete':'failed',code===0?null:'计算退出码 '+code));let finished=false;function finish(status,error){if(finished)return;finished=true;job.status=status;job.error=error;job.completed=new Date().toISOString();atomic(path.join(dir,'job.json'),Buffer.from(JSON.stringify(job)));fs.closeSync(stdout);running=null}return reply(res,202,job)
   }
  }
  const match=pathname.match(/^\/api\/tectonics\/jobs\/([0-9]{13}-[a-f0-9]{8})$/);if(req.method==='GET'&&match){const job=jobState(match[1]);if(!job)return reply(res,404,{error:'未知候选'});const log=path.join(jobsDir,job.id,'run.log');if(fs.existsSync(log))job.progress=fs.readFileSync(log,'utf8').trim().split(/\r?\n/).at(-1)?.slice(0,240);return reply(res,200,job)}
  const maskMatch=pathname.match(/^\/api\/tectonics\/mask\/([a-z-]+)$/);if(req.method==='GET'&&maskMatch&&regions.has(maskMatch[1])){const file=path.join(masks,maskMatch[1]+'.json');return fs.existsSync(file)?reply(res,200,JSON.parse(fs.readFileSync(file))):reply(res,404,{error:'此区域尚无保存权重'})}
  return reply(res,404,{error:'未知接口'});
 }
 if(!['GET','HEAD'].includes(req.method)){res.writeHead(405).end();return}
 let file,root=ROOT;const bakeMatch=pathname.match(/^\/tectonics-jobs\/([0-9]{13}-[a-f0-9]{8})\/([A-Za-z0-9_.-]+)$/);
 if(bakeMatch){root=path.join(jobsDir,bakeMatch[1],'bake');file=path.resolve(root,bakeMatch[2])}else file=path.resolve(root,'.'+(pathname==='/'?'/tectonics.html':pathname));if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}
 if(!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404).end('Not found');return}
 let bytes=fs.readFileSync(file);
 if(pathname==='/tectonics.html'&&url.searchParams.has('job')){const id=url.searchParams.get('job'),job=jobState(id);if(!job||job.status!=='complete')return reply(res,404,{error:'该候选尚未完成'});bytes=Buffer.from(bytes.toString('utf8').replace('src="foundation/tectonics/data.js"','src="/tectonics-jobs/'+id+'/data.js"'))}
 const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.svg':'image/svg+xml','.json':'application/json; charset=utf-8','.md':'text/plain; charset=utf-8'};res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});res.end(req.method==='HEAD'?undefined:bytes);
 }catch(e){reply(res,400,{error:e.message})}});
server.listen(PORT,'127.0.0.1',()=>console.log('Terrain weights: http://127.0.0.1:'+PORT+'/tectonics.html'));
