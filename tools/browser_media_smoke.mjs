import { chromium } from "playwright";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, extname, sep, join } from "node:path";

// Test-only media is served from RAM/temp, never written into Android assets.
const temp=await mkdtemp(join(tmpdir(),"puls-player-test-"));
const root=resolve("app/src/main/assets");
let server,browser;
try {
 const filename=join(temp,"fixture.mp4");
 execFileSync("ffmpeg",["-nostdin","-v","error","-f","lavfi","-i","testsrc2=size=320x180:rate=15","-t","5","-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",filename]);
 const bytes=await readFile(filename);
 const photoFile=join(temp,"fixture.jpg");
 execFileSync("ffmpeg",["-nostdin","-v","error","-i",filename,"-frames:v","1",photoFile]);
 const photoBytes=await readFile(photoFile);
 const record={topic:"cpr",file:"fixture.mp4",sha256:createHash("sha256").update(bytes).digest("hex"),author:"Synthetic QA fixture",license:"CC0 1.0",license_url:"https://creativecommons.org/publicdomain/zero/1.0/",source:"https://commons.wikimedia.org/wiki/File:Test-only-fixture.mp4",ru:"Тестовый ролик",en:"Test clip",clinical_approval:true,visual_review:"approved",rights_review:"approved",review_ref:"SYNTHETIC TEST ONLY"};
 const stepRu="Убедись, что подходить безопасно. Проверь, реагирует ли человек.",stepEn="Make sure it is safe to approach. Check responsiveness.";
 const manifest=[record,{...record,file:"inline.mp4",step_index:0,step_ru:stepRu,step_en:stepEn},{...record,file:"inline.jpg",sha256:createHash("sha256").update(photoBytes).digest("hex"),step_index:0,step_ru:stepRu,step_en:stepEn},{...record,file:"wrong-step.mp4",step_index:0,step_ru:"changed",step_en:stepEn},{...record,file:"second.mp4"},{...record,file:"missing.mp4"},{...record,file:"rejected.mp4",clinical_approval:false}];
 const requests=[];
 server=createServer(async(req,res)=>{
  try {
   const path=new URL(req.url,"http://localhost").pathname;
   if(path==="/media/firstaid/manifest.json"){res.writeHead(200,{"Content-Type":"application/json"});return res.end(JSON.stringify(manifest))}
   if(path==="/media/firstaid/inline.jpg"){res.writeHead(200,{"Content-Type":"image/jpeg"});return res.end(photoBytes)}
   if(path==="/media/firstaid/fixture.mp4"||path==="/media/firstaid/second.mp4"||path==="/media/firstaid/inline.mp4"){
    requests.push(req.headers.range||"full");
    const header=req.headers.range;
    const range=/^bytes=(\d*)-(\d*)$/.exec(header||"");
    let start=0,end=bytes.length-1;
    if(header){
     if(!range||(!range[1]&&!range[2])){res.writeHead(416,{"Content-Range":"bytes */"+bytes.length});return res.end()}
     if(!range[1]){start=Math.max(0,bytes.length-Number(range[2]))}
     else{start=Number(range[1]);if(range[2])end=Math.min(end,Number(range[2]))}
     if(start>end||start>=bytes.length){res.writeHead(416,{"Content-Range":"bytes */"+bytes.length});return res.end()}
    }
    const headers={"Content-Type":"video/mp4","Accept-Ranges":"bytes","Content-Length":end-start+1};
    if(header)headers["Content-Range"]="bytes "+start+"-"+end+"/"+bytes.length;
    res.writeHead(header?206:200,headers);return res.end(bytes.subarray(start,end+1));
   }
   const file=resolve(root,"."+decodeURIComponent(path));
   if(!file.startsWith(root+sep))throw Error("invalid path");
   const data=await readFile(file);
   res.writeHead(200,{"Content-Type":({".html":"text/html; charset=utf-8",".json":"application/json",".jpg":"image/jpeg"})[extname(file)]||"application/octet-stream"});
   res.end(data);
  }catch{res.writeHead(404);res.end()}
 });
 await new Promise(r=>server.listen(0,"127.0.0.1",r));
 browser=await chromium.launch({channel:"chrome",headless:true,args:["--no-sandbox"]});
 const ctx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const page=await ctx.newPage(),errors=[];
 const clickMediaSummary=async()=>{const summary=page.locator(".aid-media>summary");await summary.evaluate(el=>el.scrollIntoView({block:"center",behavior:"instant"}));await summary.click();};
 page.on("pageerror",e=>errors.push(e.message));
 await page.goto("http://127.0.0.1:"+server.address().port+"/index.html#/topic/cpr");
 await page.locator(".aid-media>summary").waitFor({state:"visible"});
 assert.equal(await page.locator(".aid-media video").count(),3,"unapproved record must not render");
 assert.equal(await page.locator('video[src$="rejected.mp4"]').count(),0);
 assert.ok(await page.locator(".step-list").isVisible(),"medical steps remain visible");
 const inline=page.locator('.step-media video[src$="inline.mp4"]');
 assert.equal(await page.locator('.step-media[data-step-index="0"] video').count(),1);
 await page.waitForFunction(()=>document.querySelector('.step-media img')?.naturalWidth>0);
 assert.equal(await inline.evaluate(v=>v.paused),true,"media must not autoplay");
 assert.equal(await page.locator('video[src$="wrong-step.mp4"]').count(),0);
 assert.ok(await page.locator("#media-jump").isVisible());
 await page.locator("#media-jump").click();
 assert.ok(!(await inline.isVisible()),"additional video is collapsed");
 const extra=page.locator(".step-extra-media>summary");
 await extra.click();
 assert.ok(await inline.isVisible());
 await inline.evaluate(async v=>{v.muted=true;await v.play()});
 await page.waitForFunction(()=>document.querySelector('.step-media video').currentTime>0);
 await extra.click();
 await page.waitForFunction(()=>document.querySelector('.step-media video').paused);
 await extra.click();
 await inline.evaluate(async v=>{await v.play()});
 await clickMediaSummary();
 const video=page.locator('video[src$="fixture.mp4"]');
 await video.evaluate(async v=>{v.muted=true;await v.play()});
 await page.waitForFunction(()=>document.querySelector('.step-media video').paused);
 await page.waitForFunction(()=>document.querySelector('video[src$="fixture.mp4"]').currentTime>0.15);
 const second=page.locator('video[src$="second.mp4"]');
 await second.evaluate(async v=>{v.muted=true;await v.play()});
 await page.waitForFunction(()=>document.querySelector('video[src$="fixture.mp4"]').paused);
 await second.evaluate(v=>v.pause());
 await video.evaluate(v=>{v.pause();v.currentTime=2.5});
 await page.waitForFunction(()=>{const v=document.querySelector('video[src$="fixture.mp4"]');return !v.seeking&&Math.abs(v.currentTime-2.5)<0.25});
 await video.evaluate(async v=>{await v.play()});
 await clickMediaSummary();
 await page.waitForFunction(()=>document.querySelector('video[src$="fixture.mp4"]').paused);
 await clickMediaSummary();
 await video.evaluate(async v=>{v.currentTime=0;await v.play();window.qaOldVideo=v});
 await page.evaluate(()=>{location.hash="#/topic/stroke"});
 await page.locator(".guide-visual").waitFor({state:"visible"});
 assert.equal(await page.evaluate(()=>window.qaOldVideo.paused),true,"navigation pauses detached video");
 await page.evaluate(()=>{location.hash="#/topic/cpr"});
 await page.locator(".aid-media>summary").waitFor({state:"visible"});
 await clickMediaSummary();
 const missing=page.locator('video[src$="missing.mp4"]');
 await missing.evaluate(v=>v.load());
 await missing.waitFor({state:"detached"});
 assert.equal(await page.locator(".aid-media video").count(),2);
 // If the primary step image fails, remaining collapsed video must be reachable.
 await page.locator('.step-media img').evaluate(img=>img.dispatchEvent(new Event("error")));
 await page.locator('.step-media img').waitFor({state:"detached"});
 await page.locator("#media-jump").click();
 assert.ok(await page.locator('.step-media .step-extra-media').evaluate(d=>d.open));
 assert.ok(await page.locator('.step-media video[src$="inline.mp4"]').isVisible());
 assert.equal(await page.locator('.step-media video[src$="inline.mp4"]').evaluate(v=>v.paused),true);
 assert.ok(requests.length>0,"fixture actually requested");
 assert.deepEqual(errors,[]);
 console.log("PASS browser media: playback, seek, collapse pause, route pause, corrupt/missing removal, unapproved hidden");
 // A late photo manifest must not replace a focused medicine search input.
 let releaseManifest,manifestSeen;
 const gate=new Promise(r=>{releaseManifest=r}),seen=new Promise(r=>{manifestSeen=r});
 await page.route("**/media/medicines/manifest.json",async route=>{
  manifestSeen();await gate;
  await route.fulfill({json:[null,{id:"paracetamol",author:"Synthetic QA",license:"CC0 1.0",license_url:"https://creativecommons.org/publicdomain/zero/1.0/",source:"https://commons.wikimedia.org/wiki/File:Test-only-fixture.jpg"}]});
 });
 await page.route("**/media/medicines/paracetamol.jpg",route=>route.fulfill({contentType:"image/jpeg",body:photoBytes}));
 await page.goto("http://127.0.0.1:"+server.address().port+"/index.html#/kits/medicines",{waitUntil:"domcontentloaded"});
 await seen;
 await page.locator("#medicine-search").fill("парацетамол");
 await page.locator("#medicine-search").evaluate(el=>{window.qaMedicineInput=el;el.focus()});
 releaseManifest();
 await page.waitForFunction(()=>document.querySelector(".medicine-row img")?.naturalWidth>0);
 assert.equal(await page.evaluate(()=>document.activeElement===window.qaMedicineInput),true,"late media cannot replace the active input");
 assert.equal(await page.locator("#medicine-search").inputValue(),"парацетамол");
 assert.deepEqual(errors,[]);
 console.log("PASS late medicine media, malformed manifest entry and focus preservation");
 await ctx.close();
} finally {
 await browser?.close();
 if(server) await new Promise(r=>server.close(r));
 await rm(temp,{recursive:true,force:true});
}
