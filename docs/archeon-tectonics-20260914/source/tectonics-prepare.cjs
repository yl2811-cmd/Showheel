'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const {ROOT,projection,data}=require('./projection.cjs');
const work=path.resolve(ROOT,'../../review/tectonics-20260914');fs.mkdirSync(work,{recursive:true});
const hash=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const wm=JSON.parse(fs.readFileSync(path.join(ROOT,'terrain/world-meta.json'))),wp=projection(wm.view);
const snapshot=path.join(work,'source-snapshot.json');
if(!fs.existsSync(snapshot)){
 const files=['data/atlas.json','data/living-atlas.json','terrain/world-height.f32','terrain/world-mask.png','terrain/aethelgard-height.f32','terrain/atheria-height.f32','terrain/marneth-height.f32','terrain/skyleaf-height.f32','orun-assets/manifest.json','orun-assets/input.json','foundation/manifest.json'];
 const hashes=Object.fromEntries(files.map(f=>[f,hash(path.join(ROOT,f))]));
 hashes['../../timelapse-skies_beyond_the_star.txt']=hash(path.resolve(ROOT,'../../timelapse-skies_beyond_the_star.txt'));
 const baseline={};for(const f of ['foundation/manifest.json','foundation/data.js','foundation.html','foundation-view.js','foundation-view.css','index.html']){const dest=path.join(work,'backup',f);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(path.join(ROOT,f),dest);baseline[f]=hash(dest);}
 const repo='D:/repo/Showheel',args=['-c','safe.directory='+repo,'-C',repo];
 const status=cp.execFileSync('git',[...args,'status','--porcelain=v1','--untracked-files=all'],{encoding:'utf8'});
 const dirty={};for(const l of status.split(/\r?\n/)){if(!l)continue;const f=l.slice(3),full=path.join(repo,f);if(fs.existsSync(full)&&fs.statSync(full).isFile())dirty[f]=hash(full);}
 fs.writeFileSync(snapshot,JSON.stringify({created:new Date().toISOString(),hashes,baseline,showheel:{branch:cp.execFileSync('git',[...args,'branch','--show-current'],{encoding:'utf8'}).trim(),head:cp.execFileSync('git',[...args,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),status,dirty}},null,2));
}
const input={atlas:data,world:wm,worldCalibration:[[0,0],[60,0],[0,45]].map(q=>({q,pixel:wp(q).map(v=>v*wm.scale)}))};
fs.writeFileSync(path.join(work,'input.json'),JSON.stringify(input));
console.log(JSON.stringify({work,snapshot,calibration:input.worldCalibration}));
