import { chromium } from "playwright";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createReadStream } from "node:fs";
import { stat, readFile } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
const main=resolve("app/src/main/assets"),debug=resolve("app/src/debug/assets");
const rows=JSON.parse(await readFile(debug+"/media/review/manifest.json","utf8")).review_only;
assert.ok(rows.some(r=>r.file.endsWith(".jpg")));
assert.ok(rows.some(r=>r.file.endsWith(".mp4")));
const server=createServer(async(req,res)=>{
 try{
  const pathname=decodeURIComponent(new URL(req.url,"http://localhost").pathname),root=pathname.startsWith("/media/review/")?debug:main;
  const path=resolve(root,"."+pathname);
  if(!path.startsWith(root+sep))throw Error("bad path");
  const size=(await stat(path)).size,mime={".html":"text/html; charset=utf-8",".json":"application/json",".jpg":"image/jpeg",".mp4":"video/mp4"}[extname(path)]||"application/octet-stream";
  const match=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range||"");
  let start=0,end=size-1;
  if(match){start=Number(match[1]);if(match[2])end=Math.min(end,Number(match[2]));if(start>end){res.writeHead(416,{"Content-Range":"bytes */"+size});return res.end()}}
  const headers={"Content-Type":mime,"Content-Length":end-start+1,"Accept-Ranges":"bytes"};
  if(match)headers["Content-Range"]="bytes "+start+"-"+end+"/"+size;
  res.writeHead(match?206:200,headers);if(req.method==="HEAD")return res.end();createReadStream(path,{start,end}).pipe(res);
 }catch{res.writeHead(404);res.end()}
});
await new Promise(r=>server.listen(0,"127.0.0.1",r));
let browser;
try{
 browser=await chromium.launch({channel:"chrome",headless:true,args:["--no-sandbox"]});
 const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const url="http://127.0.0.1:"+server.address().port;
 const external=[],errors=[];
 await context.route("**/*",route=>{if(route.request().url().startsWith(url+"/"))return route.continue();external.push(route.request().url());return route.abort()});
 const page=await context.newPage();page.on("pageerror",e=>errors.push(e.message));
 await page.goto(url+"/index.html#/more");
 await page.locator('a[href="#/review"]').click();
 await page.locator("#review-results").waitFor();
 assert.equal(await page.locator(".review-card").count(),Math.min(12,rows.length));
 await page.locator("#review-kind").selectOption("photo");
 await page.waitForFunction(()=>document.querySelector(".review-card img")?.naturalWidth>0);
 await page.locator("#review-kind").selectOption("video");
 const video=page.locator(".review-card video").first();
 await video.scrollIntoViewIfNeeded();
 assert.equal(await video.evaluate(v=>v.paused),true);
 await video.evaluate(async v=>{v.muted=true;await v.play()});
 await page.waitForFunction(()=>document.querySelector(".review-card video").currentTime>0);
 await video.evaluate(v=>{v.pause();v.currentTime=v.duration/2});
 await page.waitForFunction(()=>{const v=document.querySelector(".review-card video");return !v.seeking&&v.currentTime>0});
 await page.screenshot({path:"puls-review-gallery.png"});
 await page.locator('#nav a[href="#/sos"]').click();
 assert.equal(await page.locator(".review-card video").count(),0);
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
 console.log("PASS: packaged review photos, video playback/seek, navigation and no external requests");
}finally{await browser?.close();await new Promise(r=>server.close(r))}
