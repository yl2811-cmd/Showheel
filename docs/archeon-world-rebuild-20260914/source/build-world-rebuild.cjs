'use strict';
const fs=require('fs'),path=require('path'),{ROOT,data:D,d3,projection}=require('./projection.cjs');
const out=path.join(ROOT,'world-rebuild');fs.mkdirSync(out,{recursive:true});
const view=D.views.find(v=>v.id==='world'),project=projection(view),metaFile=path.join(out,'projection.json');
const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
if(process.argv.includes('--prepare')){
 fs.writeFileSync(metaFile,JSON.stringify({view,scale:project.scale(),translate:project.translate(),radiusM:4750000,anchors:[[0,0],[-12,28],[100,25],[70,-30]].map(q=>({q,pixel:project(q)}))},null,2));
 console.log('World projection registered');process.exit(0);
}
const meta=JSON.parse(fs.readFileSync(path.join(out,'manifest.json'))),named=JSON.parse(fs.readFileSync(path.join(out,'named-features.json'))),water=JSON.parse(fs.readFileSync(path.join(out,'water.geojson')));
function line(coords){return coords.map((q,i)=>{const p=project(q);return(i?'L':'M')+p.map(v=>v.toFixed(3)).join(',')}).join('');}
function polygon(coords){return coords.map(r=>line(r)+'Z').join('');}
let lakes='',tiers=['','',''];
for(const f of water.features){const g=f.geometry,p=f.properties;if(g.type==='LineString'){
 const flow=p.maximumDischargeM3s||0,t=flow>=1500?0:flow>=250?1:2;
 tiers[t]+=`<path d="${line(g.coordinates)}"><title>${escape(p.system==='Ishkar'?'Ishkar 水系':'当前支流')} · ${Math.round(flow).toLocaleString()} m³/s</title></path>`;
}else if(g.type==='Polygon'||g.type==='MultiPolygon'){
 const d=g.type==='Polygon'?polygon(g.coordinates):g.coordinates.map(polygon).join('');lakes+=`<path d="${d}"><title>当前湖面 · ${Number(p.areaKm2||0).toFixed(1)} km² · 水位待气候校正</title></path>`;
}}
const overrides=new Map(named.map(f=>[f.id,f]));const markers=[...D.settlements,...D.vistas,...D.extra].filter(f=>f.geometry.type==='Point'&&!f.properties.modelCommunity&&!f.properties.unnamed).map(f=>overrides.get(f.id)||f);let points='',labels='';
for(const f of markers){const [x,y]=project(f.geometry.coordinates),p=f.properties,isTown=p.kind==='settlement',min=isTown?((p.population||0)>=30000?1:2):(f.id==='V01'||f.id==='V02'?1:2);
 points+=`<g data-feature="${escape(f.id)}" data-detail-minzoom="${min}"><circle cx="${x.toFixed(3)}" cy="${y.toFixed(3)}" r="4" fill="${isTown?'#f6e6b6':'#c4d6ce'}" stroke="#273e46" stroke-width="1"/></g>`;
 labels+=`<g data-label="${escape(f.id)}" data-minzoom="${min}"><text x="${(x+6).toFixed(3)}" y="${(y-6).toFixed(3)}" font-size="${isTown?14:12}" data-base-size="${isTown?14:12}">${escape(p.name)}</text></g>`;
}
const sphere=d3.geoPath(project)({type:'Sphere'}),grid=d3.geoPath(project)(d3.geoGraticule10());
const header=`<svg xmlns="http://www.w3.org/2000/svg" width="${view.width}" height="${view.height}" viewBox="0 0 ${view.width} ${view.height}" role="img" aria-label="Archeon 世界地图：当前高程与水流，其他图层重建中"><title>Archeon · 高程与水流</title><defs><clipPath id="world-current-clip"><path d="${sphere}"/></clipPath></defs><style>text{font-family:Georgia,'Noto Serif SC',serif;fill:#f3eedf;stroke:#263b43;stroke-width:1.5;paint-order:stroke;stroke-linejoin:round}.current-rivers path{fill:none;stroke:#80d0eb;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.current-lakes{fill:#7bbac9;stroke:#bce1e6;stroke-width:.3;vector-effect:non-scaling-stroke}</style>`;
const body=`<g id="world-geographic-content"><g data-layer="base"><rect width="2200" height="1400" fill="#ebe7d8"/><path d="${sphere}" fill="#233841"/><image href="world-rebuild/world-base.png" width="2200" height="${meta.imageDisplayHeight}" clip-path="url(#world-current-clip)"/></g><g data-layer="current-height"><image href="world-rebuild/world-height.png" width="2200" height="${meta.imageDisplayHeight}" clip-path="url(#world-current-clip)"/></g><g data-layer="grid" opacity=".13"><path d="${grid}" fill="none" stroke="#e9eddf" stroke-width=".5"/></g><g data-layer="current-water"><g class="current-lakes" fill-rule="evenodd">${lakes}</g>${tiers.map((s,i)=>`<g class="current-rivers" data-detail-minzoom="${[1,2,4][i]}" style="stroke-width:${[1.25,.85,.55][i]}px">${s}</g>`).join('')}</g><g data-layer="places">${points}</g><g data-layer="labels">${labels}</g></g>`;
const markup=header+body+'</svg>';fs.writeFileSync(path.join(out,'world-map.js'),'window.ATLAS_MAPS=window.ATLAS_MAPS||{};window.ATLAS_MAPS.world='+JSON.stringify(markup)+';');
let standalone=markup;for(const n of ['world-base.png','world-height.png'])standalone=standalone.replace('world-rebuild/'+n,'data:image/png;base64,'+fs.readFileSync(path.join(out,n)).toString('base64'));fs.writeFileSync(path.join(out,'world.svg'),standalone);
meta.riverCount=water.features.filter(f=>f.geometry.type==='LineString').length;meta.lakeCount=water.features.length-meta.riverCount;meta.markerCount=markers.length;meta.namedFeatures=named;meta.mapFile='world-rebuild/world-map.js';fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(meta,null,2));fs.writeFileSync(path.join(out,'data.js'),'window.ATLAS_WORLD_REBUILD='+JSON.stringify(meta)+';');console.log(JSON.stringify({rivers:meta.riverCount,lakes:meta.lakeCount,markers:markers.length}));
