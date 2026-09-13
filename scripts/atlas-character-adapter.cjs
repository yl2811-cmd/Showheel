'use strict';
// Website-owned additions: source atlas exports remain unchanged.
const ownedFiles = ['character-panel.js', 'character-panel.css'];
function replace(text, before, after) {
    if (text.split(before).length !== 2) throw Error('Atlas Character integration anchor changed: ' + before.slice(0, 80));
    return text.replace(before, after);
}
function adapt(relative, original) {
    if (relative !== 'index.html' && relative !== 'space-controller.js') return original;
    let text = original.toString('utf8');
    if (relative === 'index.html') {
        text = replace(text, '<span>05</span>Federation</button></nav>', '<span>05</span>Federation</button><button data-tab="character" aria-pressed="false"><span>06</span>Character</button></nav>');
        text = replace(text, '</head>', '<link rel="stylesheet" href="../css/character.css"><link rel="stylesheet" href="character-panel.css"></head>');
        text = replace(text, '<main class="map-panel">', '<main class="map-panel"><section id="character-stage" aria-label="人物 · Character" aria-busy="false" hidden></section>');
        text = replace(text, '<script src="space-controller.js"></script>', '<script src="../js/character.js"></script><script src="character-panel.js"></script><script src="space-controller.js"></script>');
    }
    if (relative === 'space-controller.js') {
        text = replace(text, 'function syncInterface(){', "function syncInterface(){\n  const character=activeTab==='character';document.body.classList.toggle('character-mode',character);$('character-stage').hidden=!character;");
        text = replace(text, "$('map-stage').hidden=cosmic;", "$('map-stage').hidden=cosmic||character;");
        text = replace(text, "async function setTab(id){", `async function setTab(id){
  if(id==='character'){
   const token=++loadToken;restoreSpaceScenic();instance?.dispose();instance=null;engineType='base';playing=false;app.spaceState=null;
   window.ATLAS_ATHERIA_PAGE?.close();app.suspend();activeTab=id;syncInterface();app.currentView=id;app.ready=false;app.loadingView=id;$('detail').hidden=true;
   try{await window.ATLAS_CHARACTERS.open();if(token!==loadToken)return;app.ready=true;app.loadingView=null;window.dispatchEvent(new CustomEvent('atlas-view-ready',{detail:{id}}));}
   catch(error){if(token!==loadToken)return;app.ready=false;app.loadingView=null;}
   return;
  }`);
        text = replace(text, "['system','federation','world','aethelgard','local'].includes(initial)", "['system','federation','world','aethelgard','local','character'].includes(initial)");
    }
    return Buffer.from(text);
}
module.exports = { ownedFiles, adapt };
