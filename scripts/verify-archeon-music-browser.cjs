const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert/strict');
const base=process.argv[2] || 'http://127.0.0.1:5281',out=process.env.MUSIC_QA_OUTPUT || path.join(os.tmpdir(),'showheel-music-qa');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {}),args:['--autoplay-policy=no-user-gesture-required','--mute-audio']});
 const p=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(base+'/Archeon');await p.waitForFunction(()=>document.querySelector('[data-archeon-music]').dataset.state==='playing');
 const result={autoplay:true,tracks:[]};
 for(let i=1;i<=9;i++){
  await p.waitForFunction(i=>{const a=document.querySelector('audio');return a.currentSrc.endsWith('archeonvibe'+i+'.mp3')&&a.readyState>=2&&!a.paused&&a.currentTime>0;},i);
  result.tracks.push(await p.locator('audio').evaluate(a=>({file:a.currentSrc.split('/').pop(),duration:a.duration})));
  if(i<9)await p.getByRole('button',{name:'下一首',exact:true}).click();
 }
 await p.locator('audio').evaluate(a=>{a.currentTime=a.duration-.15;});
 await p.waitForFunction(()=>document.querySelector('[data-archeon-music]').dataset.state==='waiting');
 const started=Date.now(); await p.waitForFunction(()=>document.querySelector('audio').currentSrc.endsWith('archeonvibe1.mp3')&&!document.querySelector('audio').paused,{},{timeout:15000});
 result.actualGapMs=Date.now()-started;assert(result.actualGapMs>=9700&&result.actualGapMs<14000);
 await p.getByRole('button',{name:'暂停背景音乐',exact:true}).click();assert(await p.locator('audio').evaluate(a=>a.paused));
 await p.getByRole('button',{name:'上一首',exact:true}).click();await p.waitForFunction(()=>document.querySelector('audio').currentSrc.endsWith('archeonvibe9.mp3')&&!document.querySelector('audio').paused);
 await p.getByRole('button',{name:'暂停背景音乐',exact:true}).click();
 await p.screenshot({path:path.join(out,'hero-desktop.png')});
 await p.locator('[data-story-reader]').scrollIntoViewIfNeeded();await p.locator('.story-prose').waitFor();
 result.width=await p.locator('.story-prose').evaluate(a=>({outer:a.clientWidth,padding:parseFloat(getComputedStyle(a).paddingLeft),text:a.clientWidth-2*parseFloat(getComputedStyle(a).paddingLeft)}));assert(result.width.text>1000);
 await p.screenshot({path:path.join(out,'reader-desktop.png')});
 await p.setViewportSize({width:390,height:844});await p.screenshot({path:path.join(out,'reader-mobile.png')});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 result.errors=errors;assert.deepEqual(errors,[]);await browser.close();
 const blocked=await chromium.launch({headless:true,...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {}),args:['--autoplay-policy=user-gesture-required','--mute-audio']});
 const q=await blocked.newPage();await q.goto(base+'/Archeon');await q.waitForFunction(()=>document.querySelector('[data-archeon-music]').dataset.state==='blocked');
 await q.getByRole('button',{name:'播放背景音乐',exact:true}).click();await q.waitForFunction(()=>document.querySelector('[data-archeon-music]').dataset.state==='playing');result.blockedRecovery=true;
 await blocked.close();result.passed=true;fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exit(1)});