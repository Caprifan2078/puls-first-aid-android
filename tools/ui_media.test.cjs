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
 assert.equal((ru.match(/medicine-group/g)||[]).length,10);
 assert.equal((ru.match(/medicine-row/g)||[]).length,100);
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

test('unapproved first-aid media never renders; approved paths are local only',()=>{const ctx=vm.createContext({PAGES:[{id:"cpr"}],MED_LICENSE_URLS:new Set(["https://creativecommons.org/licenses/by-sa/4.0/"]),state:{lang:"ru"},esc:String});vm.runInContext(js.slice(js.indexOf("const AID_MEDIA_LICENSES"),js.indexOf("const AID_REFERENCE")),ctx);const record={topic:"cpr",file:"sample.mp4",sha256:"a".repeat(64),author:"Author",license:"CC BY-SA 4.0",license_url:"https://creativecommons.org/licenses/by-sa/4.0/",source:"https://commons.wikimedia.org/wiki/File:Sample.webm",ru:"Тест",en:"Test",clinical_approval:false,visual_review:"pending",review_ref:"test-only"};ctx.record=record;assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),0);assert.equal(vm.runInContext('renderAidMedia({id:"cpr"})',ctx),"");record.clinical_approval=true;record.visual_review="approved";assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),1);assert.ok(vm.runInContext('approvedAidMedia=validateAidMedia([record]);renderAidMedia({id:"cpr"})',ctx).includes('controls playsinline preload="none"'));record.file="../sample.mp4";assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),0);});

test('medicine search finds generic and aliases, rejects unmatched queries',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('medRows("регидрон")[0].id',ctx),"ors");assert.equal(vm.runInContext('medRows("aspirin")[0].id',ctx),"aspirin");assert.equal(vm.runInContext('medRows("zz-no-match").length',ctx),0);assert.equal(vm.runInContext('medRows("").length',ctx),100);});

test('home search no longer forces navigation or uses invalid search selection API',()=>{const body=js.slice(js.indexOf("function liveSearch()"),js.indexOf('document.addEventListener("error"'));assert.ok(body.includes('$("#home-browse").hidden=active'));assert.ok(!body.includes('location.hash="#/catalog"'));assert.ok(!body.includes("setSelectionRange"));});

test('all medicine cards contain reference classification and source status, no dosing tables',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MEDICINES.filter(m=>MED_DETAILS[m.id]).length',ctx),100);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.source).length',ctx),98);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="calamine"))',ctx).includes("источник требует проверки"));});

test('adult CPR calls immediately and recovery position excludes trauma',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const c=pages.find(p=>p.id==="cpr"),u=pages.find(p=>p.id==="unconscious");assert.ok(c.stepsRu[1].includes("сразу вызови"));assert.ok(c.stepsEn[1].includes("immediately"));assert.ok(u.stepsRu[1].includes("отсутствии травмы"));assert.ok(u.stepsEn[1].includes("no trauma"));assert.ok(c.stepsRu.some(s=>s.includes("30 надавливаний")));});

test('original equipment artwork covers all checklist positions and missing filter works',()=>{const kits=vm.runInNewContext(js.slice(js.indexOf('const KITS='),js.indexOf('const I='))+'KITS');const ctx=vm.createContext({state:{check:{"home:0":true}}});vm.runInContext(js.slice(js.indexOf("const EQUIPMENT_DRAWINGS="),js.indexOf("const KIT_GROUPS=")),ctx);for(const k of kits){ctx.k=k;assert.equal(vm.runInContext("KIT_DRAWINGS[k.id].length",ctx),k.items.length);assert.ok(vm.runInContext("KIT_DRAWINGS[k.id].every(id=>EQUIPMENT_DRAWINGS[id])",ctx));}ctx.k=kits[0];assert.deepEqual(Array.from(vm.runInContext('missingOnly=true;kitVisibleIndices(k,[0,1])',ctx)),[1]);assert.ok(vm.runInContext('equipmentIcon("gauze")',ctx).includes("<svg"));});

test('all expanded guides have unique ids, paired steps and source for new topics',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(pages.length,71);assert.equal(new Set(pages.map(p=>p.id)).size,71);for(const p of pages){assert.equal(p.stepsRu.length,p.stepsEn.length,p.id);assert.ok(p.stepsRu.length&&p.avoidRu&&p.avoidEn,p.id);}for(const id of ["infant-choking","child-cpr","co-poison","battery-ingestion","sepsis","meningitis","pulmonary-embolism","dka","ectopic","testicular-pain"]){assert.ok(pages.some(p=>p.id===id&&p.level==="critical"));assert.match(refs[id],/^https:\/\/(www\.nhs\.uk|www\.resus\.org\.uk)\//);}assert.ok(pages.find(p=>p.id==="anaphylaxis").stepsRu.some(s=>s.includes("5 минут")));});

test('new medicine index links and cautions are distinguished from individual sources',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.sourceKind==="index").length',ctx),53);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.caution).length',ctx),19);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="paracetamol"))',ctx).includes("med-caution"));assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="esomeprazole"))',ctx).includes("общий указатель"));});

test('all medicine groups are populated and urgent categories are not lost',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MED_GROUPS.length',ctx),10);assert.ok(vm.runInContext('MED_GROUPS.every(g=>MEDICINES.some(m=>m.group===g[0]))',ctx));assert.equal(vm.runInContext('new Set(MEDICINES.map(m=>m.id)).size',ctx),100);const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");assert.ok(pages.filter(p=>p.level==="critical").every(p=>["children","injuries","environment","emergency"].includes(p.category)));});
