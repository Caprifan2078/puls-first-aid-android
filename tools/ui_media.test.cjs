const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const page=fs.readFileSync('app/src/main/assets/index.html','utf8');
const js=page.match(/<script>([\s\S]*?)<\/script>/)[1];
test('inline script compiles',()=>assert.doesNotThrow(()=>new vm.Script(js)));
test('medicine shelf is grouped, bilingual and has no empty image slots',()=>{
 const chunk=js.slice(js.indexOf('const MEDICINES='),js.indexOf('const KIT_GROUPS='));
 const ctx=vm.createContext({state:{lang:'ru'},esc:v=>String(v),norm:v=>String(v||"").toLowerCase()});
 vm.runInContext(chunk,ctx);
 const ru=vm.runInContext('renderMedicineShelf()',ctx);
 assert.equal((ru.match(/medicine-group/g)||[]).length,7);
 assert.equal((ru.match(/medicine-row/g)||[]).length,27);
 assert.ok(!ru.includes('<img'));
 assert.ok(ru.includes('Не определяйте препарат по фото'));
 const en=vm.runInContext('state.lang="en";renderMedicineShelf()',ctx);
 assert.ok(en.includes('Never identify medicines by photo'));
});
test('emergency call and saved guide access remain',()=>{
 assert.ok(js.includes('href="tel:'));
 assert.ok(js.includes('href="#/favorites"'));
 assert.ok(page.includes('id="langbtn"'));
 assert.ok(js.includes('id="backup"'));
 assert.ok(js.includes('aria-expanded='));
});

test('malformed topic IDs and stale catalog categories are safe',()=>{
 const ctx=vm.createContext({CATS:[["all"],["injuries"]]});
 vm.runInContext(js.slice(js.indexOf("function safeTopicId"),js.indexOf("function renderMedicineShelf")),ctx);
 assert.equal(vm.runInContext('safeTopicId("%")',ctx),"");
 assert.equal(vm.runInContext('catalogCategory(undefined)',ctx),"all");
 assert.equal(vm.runInContext('catalogCategory("injuries")',ctx),"injuries");
 assert.ok(js.includes('history.replaceState(null,"","#/catalog/"+state.cat)'));
});
test('broken photo disappears and open category is restored after manifest load',()=>{
 assert.ok(js.includes('ev.target.remove()'));
 const groups=[{dataset:{group:'pain'},open:false},{dataset:{group:'skin'},open:true}];const ctx=vm.createContext({document:{querySelectorAll:()=>groups}});vm.runInContext(js.slice(js.indexOf('function restoreMedicineGroups'),js.indexOf('function renderMedicineGroups')),ctx);vm.runInContext('restoreMedicineGroups(["pain"],"")',ctx);assert.deepEqual(groups.map(g=>g.open),[true,false]);vm.runInContext('restoreMedicineGroups([],"test")',ctx);assert.deepEqual(groups.map(g=>g.open),[true,true]);
});

test('all three kit group mappings cover each item exactly once and keep legacy keys',()=>{const kits=vm.runInNewContext(js.slice(js.indexOf('const KITS='),js.indexOf('const I='))+'KITS');const groups=vm.runInNewContext(js.slice(js.indexOf('const KIT_GROUPS='),js.indexOf('const KIT_SOURCE='))+'KIT_GROUPS');assert.deepEqual(Array.from(kits,k=>k.id),['home','travel','outdoor']);for(const k of kits){const ids=Array.from(groups[k.id].flatMap(g=>g[2])).sort((a,b)=>a-b);assert.deepEqual(ids,Array.from({length:k.items.length},(_,i)=>i));assert.ok(k.items.length>=13);}});
test('SOS priority topics are unique and exist',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf('const PAGES='),js.indexOf('const KITS='))+'PAGES');const order=vm.runInNewContext(js.slice(js.indexOf('const SOS_ORDER='),js.indexOf('const SOS_LABELS='))+'SOS_ORDER');assert.equal(new Set(order).size,order.length);for(const id of order)assert.ok(pages.some(p=>p.id===id));});

test('unapproved first-aid media never renders; approved paths are local only',()=>{const ctx=vm.createContext({PAGES:[{id:"cpr"}],MED_LICENSE_URLS:new Set(["https://creativecommons.org/licenses/by-sa/4.0/"]),state:{lang:"ru"},esc:String});vm.runInContext(js.slice(js.indexOf("const AID_MEDIA_LICENSES"),js.indexOf("function renderTopic(p)")),ctx);const record={topic:"cpr",file:"sample.mp4",sha256:"a".repeat(64),author:"Author",license:"CC BY-SA 4.0",license_url:"https://creativecommons.org/licenses/by-sa/4.0/",source:"https://commons.wikimedia.org/wiki/File:Sample.webm",ru:"Тест",en:"Test",clinical_approval:false,visual_review:"pending",review_ref:"test-only"};ctx.record=record;assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),0);assert.equal(vm.runInContext('renderAidMedia({id:"cpr"})',ctx),"");record.clinical_approval=true;record.visual_review="approved";assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),1);assert.ok(vm.runInContext('approvedAidMedia=validateAidMedia([record]);renderAidMedia({id:"cpr"})',ctx).includes('controls playsinline preload="none"'));record.file="../sample.mp4";assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),0);});

test('medicine search finds generic and aliases, rejects unmatched queries',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('medRows("регидрон")[0].id',ctx),"ors");assert.equal(vm.runInContext('medRows("aspirin")[0].id',ctx),"aspirin");assert.equal(vm.runInContext('medRows("zz-no-match").length',ctx),0);assert.equal(vm.runInContext('medRows("").length',ctx),27);});

test('home search no longer forces navigation or uses invalid search selection API',()=>{const body=js.slice(js.indexOf("function liveSearch()"),js.indexOf('document.addEventListener("error"'));assert.ok(body.includes('$("#home-browse").hidden=active'));assert.ok(!body.includes('location.hash="#/catalog"'));assert.ok(!body.includes("setSelectionRange"));});

test('all medicine cards contain reference classification and source status, no dosing tables',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MEDICINES.filter(m=>MED_DETAILS[m.id]).length',ctx),27);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.source).length',ctx),25);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="calamine"))',ctx).includes("источник требует проверки"));});
