/* Offline language layer. Text changes never recreate a map, simulation or camera. */
(() => {
 'use strict';
 const catalogue=window.ATLAS_TRANSLATIONS||{},cjk=/[\u3400-\u9fff]/,originals=new WeakMap(),missing=new Set();
 const cache=new Map();
 const replacements=Object.entries(catalogue).sort((a,b)=>b[0].length-a[0].length);
 let locale='zh',scheduled=false;
 try{locale=new URLSearchParams(location.search).get('lang')||localStorage.getItem('archeon-atlas-language')||'zh';}catch{}
 locale=locale.toLowerCase().startsWith('en')?'en':'zh';
 function english(value){const s=String(value??'');if(!cjk.test(s))return s;if(cache.has(s))return cache.get(s);const trim=s.trim();if(catalogue[trim])return s.replace(trim,catalogue[trim]);let out=s;for(const[a,b]of replacements)if(out.includes(a))out=out.split(a).join(b);if(cjk.test(out))missing.add(s);if(cache.size>3000)cache.clear();cache.set(s,out);return out;}
 function text(value,lang=locale){return lang==='en'?english(value):String(value??'');}
 const skip=e=>!e||e.closest('script,style,pre,code,[data-no-translate]');
 function applyText(node){if(skip(node.parentElement))return;const current=node.nodeValue;let entry=originals.get(node);if(!entry||entry.last!==current)entry={source:current,last:current};const next=text(entry.source);entry.last=next;originals.set(node,entry);if(next!==current)node.nodeValue=next;}
 function applyAttributes(el){if(skip(el))return;let entries=originals.get(el);if(!entries)originals.set(el,entries={});for(const name of ['title','aria-label','placeholder','alt']){if(!el.hasAttribute(name))continue;const current=el.getAttribute(name);let entry=entries[name];if(!entry||entry.last!==current)entry={source:current,last:current};const next=text(entry.source);entry.last=next;entries[name]=entry;if(next!==current)el.setAttribute(name,next);}}
 function localize(root=document.body){if(!root)return;if(root.nodeType===3){applyText(root);return;}if(root.nodeType!==1)return;applyAttributes(root);const walker=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT);while(walker.nextNode()){const n=walker.currentNode;if(n.nodeType===3)applyText(n);else applyAttributes(n);}}
 const observer=new MutationObserver(records=>{const roots=new Set();for(const r of records){if(r.type==='childList')r.addedNodes.forEach(n=>roots.add(n));else roots.add(r.target);}for(const root of roots)localize(root);});
 function downloads(){for(const id of ['download-svg','download-png']){const a=document.getElementById(id);if(!a)continue;const href=a.getAttribute('href');if(!href)continue;a.setAttribute('href',href.replace(/(?:-en)?\.(svg|png)$/,(m,ext)=>(locale==='en'?'-en':'')+'.'+ext));}}
 function refresh(){document.documentElement.lang=locale==='en'?'en':'zh-CN';localize();downloads();document.querySelectorAll('[data-atlas-language]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.atlasLanguage===locale)));}
 function setLocale(value){const next=value==='en'?'en':'zh';try{localStorage.setItem('archeon-atlas-language',next);}catch{}if(next===locale){refresh();return;}locale=next;try{const u=new URL(location.href);u.searchParams.set('lang',locale);history.replaceState(history.state,'',u);}catch{}refresh();dispatchEvent(new CustomEvent('atlas-language-changed',{detail:{locale}}));}
 function bind(){const header=document.querySelector('.masthead');if(header){const group=document.createElement('div');group.className='language-switch';group.dataset.noTranslate='';group.setAttribute('role','group');group.setAttribute('aria-label','Language / 语言');for(const[id,label]of [['zh','中文'],['en','EN']]){const b=document.createElement('button');b.type='button';b.dataset.atlasLanguage=id;b.textContent=label;b.onclick=()=>setLocale(id);group.append(b);}header.append(group);}refresh();observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','aria-label','placeholder','alt']});}
 const localizedFeatures=new Map();
 function feature(f){if(!f)return f;const p=f.properties||f,key=f.id||p.id;if(!localizedFeatures.has(key))localizedFeatures.set(key,{zh:{name:p.name,description:p.description},en:{name:english(p.name),description:english(p.description)}});return localizedFeatures.get(key)[locale];}
 window.ATLAS_I18N={get locale(){return locale;},t:text,english,setLocale,localize,refresh,downloads,feature,searchText(f){const p=f.properties||f;return [f.id,p.name,p.description,english(p.name),english(p.description),f.id==='AT'?'鹰巢 The Eyrie Atheria':''].filter(Boolean).join(' ').toLowerCase();},missing:()=>[...missing]};
 addEventListener('atlas-view-ready',()=>{refresh();});addEventListener('eyrie-view-ready',()=>refresh());
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind,{once:true});else bind();
})();
