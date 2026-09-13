/* Reversible channel/byte ordering. No floating point operations or quantization. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SHOWHEEL_FLOAT_CODEC=api;})(globalThis,function(){
 'use strict';
 function transcode(input,transform,reverse){
  const bytes=input instanceof Uint8Array?input:new Uint8Array(input),stride=transform.stride,delta=!!transform.delta;
  if(bytes.byteLength%4||!Number.isInteger(stride)||stride<1||stride>256||transform.kind!=='f32-channels-v1')throw Error('Invalid lossless float layout');
  const n=bytes.byteLength/4,out=new Uint8Array(bytes.byteLength);let offset=0;
  for(let channel=0;channel<stride;channel++)for(let byte=0;byte<4;byte++){let previous=0;for(let i=channel;i<n;i+=stride){if(reverse){const value=(bytes[offset++]+(delta?previous:0))&255;out[i*4+byte]=value;previous=value;}else{const value=bytes[i*4+byte];out[offset++]=(value-(delta?previous:0))&255;previous=value;}}}
  return out;
 }
 return{encode:(b,t)=>transcode(b,t,false),decode:(b,t)=>transcode(b,t,true)};
});
