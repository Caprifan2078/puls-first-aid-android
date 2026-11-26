import {readFileSync} from "node:fs";
// Experimental single-layer neural text classifier, never a clinical decision engine.
// Run offline. No generation, diagnosis, dosage, network, or runtime integration.
const DIM=2048;
function features(value){
 const text=" "+String(value).toLowerCase().replace(/ё/g,"е").replace(/[^a-zа-я0-9]+/g," ").trim()+" ";
 const counts=new Map();
 for(let n of [2,3,4])for(let i=0;i+n<=text.length;i++){
  let hash=2166136261;for(let k=i;k<i+n;k++)hash=Math.imul(hash^text.charCodeAt(k),16777619);
  const at=(hash>>>0)%DIM;counts.set(at,(counts.get(at)||0)+1);
 }
 const length=Math.sqrt([...counts.values()].reduce((a,b)=>a+b*b,0))||1;
 return [...counts].map(([i,v])=>[i,v/length]);
}
function train(pages,epochs=22){
 const weights=new Float32Array(pages.length*DIM),samples=[];
 for(let i=0;i<pages.length;i++)for(const value of [pages[i].ru,pages[i].aliases])if(value)samples.push({i,x:features(value)});
 function logits(x){const scores=new Float64Array(pages.length);for(let k=0;k<pages.length;k++){let s=0;for(const [f,v] of x)s+=weights[k*DIM+f]*v;scores[k]=s}return scores}
 for(let e=0;e<epochs;e++)for(let t=0;t<samples.length;t++){
  const {i,x}=samples[(t+e*17)%samples.length];const scores=logits(x),max=Math.max(...scores);let sum=0;
  for(let k=0;k<scores.length;k++){scores[k]=Math.exp(scores[k]-max);sum+=scores[k]}
  for(let k=0;k<scores.length;k++){const delta=.28*((k===i?1:0)-scores[k]/sum);for(const [f,v] of x)weights[k*DIM+f]+=delta*v;}
 }
 return query=>{if(typeof query!=="string"||!query.trim()||query.length>256)return [];return Array.from(logits(features(query)),(score,i)=>({id:pages[i].id,score})).sort((a,b)=>b.score-a.score).slice(0,5)};
}
function evaluate(pages){
 const predict=train(pages);let top1=0,top3=0,top5=0;const misses=[];
 for(const p of pages){const result=predict(p.en),idx=result.findIndex(x=>x.id===p.id);if(idx===0)top1++;if(idx>=0&&idx<3)top3++;if(idx>=0)top5++;else misses.push(p.id)}
 return {topics:pages.length,training:"Russian titles and bilingual aliases",test:"English titles withheld as separate examples; aliases can overlap",top1,top3,top5,misses,emptyRejected:predict("").length===0,oversizeRejected:predict("x".repeat(257)).length===0,clinicalValidation:false,release:false};
}

const html=readFileSync(new URL("../app/src/main/assets/index.html",import.meta.url),"utf8");
const match=html.match(/const PAGES\s*=\s*(\[[\s\S]*?\]);\s*const NAV=/);
if(!match)throw Error("Guide inventory not found");
const pages=JSON.parse(match[1]);
console.log(JSON.stringify(evaluate(pages),null,2));
