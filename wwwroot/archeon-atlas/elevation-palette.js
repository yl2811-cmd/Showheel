/* Fixed absolute metres. These colours never change the source terrain. */
(function(root){
 'use strict';
 const stops=[[0,'#35ad68'],[1600,'#3678cf'],[3200,'#f1dc55'],[4800,'#f49a38'],[6400,'#d84748'],[8000,'#8642b4']];
 const rgb=stops.map(([h,c])=>[h,...c.slice(1).match(/../g).map(v=>parseInt(v,16))]);
 function color(h){const t=Math.max(0,Math.min(5,h/1600)),i=Math.min(4,Math.floor(t)),u=t-i;return rgb[i].slice(1).map((v,c)=>Math.round(v+(rgb[i+1][c+1]-v)*u));}
 const api={stops,color,water:'#718994',unknown:'#d8d6ca',paper:'#f5f2e9'};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.ATLAS_ELEVATION_PALETTE=api;
})(typeof window==='undefined'?globalThis:window);
