'use strict';
importScripts('orun-landforms.js','orun-core.js','orun-clouds-v5.js','orun-clouds.js');
let state=null;
self.onmessage=e=>{const m=e.data;try{if(m.type==='init'){state=m.state;return;}if(!state)throw Error('Cloud terrain is not ready');const start=performance.now(),field=ORUN_CLOUDS.buildCloudField(state,m.parameters,m.time,m.focus,m.quality);field.stats.computeMs=performance.now()-start;postMessage({id:m.id,...field},field.chunks.flatMap(c=>[c.position.buffer,c.density.buffer,c.tone.buffer]));}catch(e){postMessage({id:m.id,error:e.message});}};
