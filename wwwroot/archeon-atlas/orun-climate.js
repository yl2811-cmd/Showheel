/* Terrain-forced climate. Annual depths are art-calibrated metres, never measurements. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./orun-core.js'):root.ORUN_CORE);if(typeof module==='object'&&module.exports)module.exports=api;else root.ORUN_CLIMATE=api;})(typeof self!=='undefined'?self:globalThis,function(C){
'use strict';
const VERSION='orographic-v2',STRIDE=8,YEAR=31557600,S=C.smooth,K=C.clamp;
const CHANNELS=['rainMYear','fogMYear','potentialEvapMYear','temperatureC','windward','cloudFrequency','rechargeMYear','runoffMYear'];
function heightHash(g){let h=2166136261;const a=new Uint32Array(g.h.buffer,g.h.byteOffset,g.h.length);for(let i=0;i<a.length;i++)h=Math.imul(h^a[i],16777619);return h>>>0;}
function key(g,p){return [VERSION,heightHash(g),g.seed||0,g.baseKey||g.key||'',g.n,g.step,p.rainfall,p.climateWind,p.climateSpeed,p.condensationBase,p.fogCapture].join(':');}
function sample(g,x,z){const a=[];for(let c=0;c<STRIDE;c++)a.push(C.L.sampleGrid(g,g.data,x,z,STRIDE,c));return a;}
function transport(input,n,length,step,wx,wz){const rows=Math.round(input.length/n),out=new Float32Array(input.length),ax=Math.abs(wx)*length/step,az=Math.abs(wz)*length/step,dx=wx>=0?1:-1,dz=wz>=0?1:-1;for(let jj=0;jj<rows;jj++)for(let ii=0;ii<n;ii++){const i=dx>0?ii:n-1-ii,j=dz>0?jj:rows-1-jj,k=j*n+i,px=i-dx,pz=j-dz;out[k]=(input[k]+(px>=0&&px<n?ax*out[k-dx]:0)+(pz>=0&&pz<rows?az*out[k-dz*n]:0))/(1+ax+az);}return out;}
function deriveClimate(state,p=state.parameters,progress=()=>{}){
 const base=state.baseLandforms||state.landforms||state,step=Math.max(base.step,256),n=Math.round((base.n-1)*base.step/step)+1,min=base.min,h=new Float32Array(n*n),data=new Float32Array(n*n*STRIDE),condense=new Float32Array(n*n),rise=new Float32Array(n*n),angle=(p.climateWind??35)*Math.PI/180,wx=Math.cos(angle),wz=Math.sin(angle),speed=p.climateSpeed??12,cloudBase=p.condensationBase??1000,amount=p.rainfall??1;
 progress('正在计算迎风抬升、云滴飘移与全年补给…');
 for(let j=0;j<n;j++)for(let i=0;i<n;i++)h[j*n+i]=C.L.sampleGrid(base,base.h,min+i*step,min+j*step);
 for(let j=1;j<n-1;j++)for(let i=1;i<n-1;i++){const k=j*n+i,hx=(h[k+1]-h[k-1])/(2*step),hz=(h[k+n]-h[k-n])/(2*step),dot=hx*wx+hz*wz;rise[k]=dot;condense[k]=Math.max(0,dot)*S(cloudBase-200,cloudBase+400,h[k])*Math.exp(-Math.max(0,h[k]-cloudBase)/2400);}
 const cloud=transport(condense,n,speed*220,step,wx,wz),rain=transport(cloud,n,speed*260,step,wx,wz),shadow=transport(Float32Array.from(rise,v=>Math.max(0,-v)),n,12000,step,wx,wz),spent=transport(condense,n,120000,step,wx,wz),byAltitude={};let precipitationM3=0,rechargeM3=0,runoffM3=0,actualEvapM3=0;
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){
  const k=j*n+i,height=h[k],x=min+i*step,z=min+j*step,exposure=S(-.025,.09,rise[k]),lee=Math.max(K(shadow[k]*7),(1-Math.exp(-spent[k]*120000/1100))*(1-S(.015,.12,Math.max(0,rise[k])))),frequency=K(cloud[k]*7+Math.max(0,rise[k])*1.2)*S(cloudBase-200,cloudBase+250,height),rainDepth=amount*(1.05+2.4*(1-Math.exp(-rain[k]*8)))*(1-lee*.78),fog=amount*(p.fogCapture??1)*.28*frequency*(.35+.65*exposure),pet=K(1.14-height*.00017,.45,1.2),temperature=18-height*.0055;
  const input=rainDepth+fog,evap=Math.min(input,pet*(.64-.18*frequency)),available=Math.max(0,input-evap),fracture=.45+.12*exposure,groundwater=available*fracture,runoff=available-groundwater;
  data.set([rainDepth,fog,pet,temperature,exposure,frequency,groundwater,runoff],k*STRIDE);
  if(Math.hypot(x,z)<=C.RADIUS){const b=Math.floor(height/250)*250,a=byAltitude[b]||(byAltitude[b]={samples:0,rain:0,fog:0,recharge:0});a.samples++;a.rain+=rainDepth;a.fog+=fog;a.recharge+=groundwater;precipitationM3+=input*step*step;rechargeM3+=groundwater*step*step;runoffM3+=runoff*step*step;actualEvapM3+=evap*step*step;}
 }
 for(const a of Object.values(byAltitude)){a.rain/=a.samples;a.fog/=a.samples;a.recharge/=a.samples;}
 return{key:key(base,p),algorithm:VERSION,n,min,step,stride:STRIDE,channels:CHANNELS,data,report:{gridStepM:step,byAltitude,annual:{precipitationM3,rechargeM3,runoffM3,actualEvapM3,residualM3:precipitationM3-rechargeM3-runoffM3-actualEvapM3},defaults:{cloudBaseM:cloudBase,windMps:speed,windLocalDegrees:p.climateWind??35,conversionSeconds:220,falloutSeconds:260},scope:'Procedural orographic climate preset, not observed rainfall. Climate is independent of animated cloud opacity and playback.'}};
}
// Exact reservoir update for constant forcing; release + storage change equals recharge.
function advanceAquifer(storageM3,rechargeM3s,dtYears,tauYears=2.5){const dt=dtYears*YEAR,tau=tauYears*YEAR,steady=rechargeM3s*tau,next=steady+(storageM3-steady)*Math.exp(-dt/tau),released=storageM3+rechargeM3s*dt-next;return{storageM3:next,releasedM3:released,dischargeM3s:dt?released/dt:storageM3/tau};}
function seasonalBaseflow(mean,season=.45){let storage=mean*2.5*YEAR;const months=Array.from({length:12},(_,m)=>1+.62*Math.cos(2*Math.PI*(m-2)/12));let records=[];for(let year=0;year<16;year++){records=[];for(let m=0;m<12;m++){const r=advanceAquifer(storage,mean*months[m],1/12);storage=r.storageM3;records.push(r);}}const dry=Math.min(...records.map(r=>r.dischargeM3s)),wet=Math.max(...records.map(r=>r.dischargeM3s));return{discharge:C.mix(dry,wet,season),storageM3:C.mix(Math.min(...records.map(r=>r.storageM3)),Math.max(...records.map(r=>r.storageM3)),season),dry,wet};}
return{VERSION,STRIDE,CHANNELS,YEAR,key,sample,transport,deriveClimate,advanceAquifer,seasonalBaseflow};
});
