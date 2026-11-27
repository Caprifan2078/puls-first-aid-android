const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const page=fs.readFileSync('app/src/main/assets/index.html','utf8');
const js=page.match(/<script>([\s\S]*?)<\/script>/)[1];
const inventory=vm.runInNewContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const MED_LICENSE_URLS="))+";({medicines:MEDICINES,groups:MED_GROUPS})");
const medicineCount=inventory.medicines.length,groupCount=inventory.groups.length;
const referenceCount=inventory.medicines.filter(m=>m.group==="reference").length;
test('medicine library preserves expansion milestones',()=>{assert.ok(medicineCount>=534);assert.ok(groupCount>=13);assert.ok(referenceCount>=294)});
test('inline script compiles',()=>assert.doesNotThrow(()=>new vm.Script(js)));
test('medicine shelf is grouped, bilingual and has no empty image slots',()=>{
 const chunk=js.slice(js.indexOf('const MEDICINES='),js.indexOf('const KIT_GROUPS='));
 const ctx=vm.createContext({state:{lang:'ru'},esc:v=>String(v),norm:v=>String(v||"").toLowerCase()});
 vm.runInContext(chunk,ctx);
 const ru=vm.runInContext('renderMedicineShelf()',ctx);
 assert.equal((ru.match(/medicine-group/g)||[]).length,groupCount);
 assert.equal((ru.match(/medicine-row/g)||[]).length,medicineCount);
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

test('unapproved first-aid media never renders; approved paths are local only',()=>{const ctx=vm.createContext({PAGES:[{id:"cpr"}],MED_LICENSE_URLS:new Set(["https://creativecommons.org/licenses/by-sa/4.0/"]),state:{lang:"ru"},esc:String});vm.runInContext(js.slice(js.indexOf("const AID_MEDIA_LICENSES"),js.indexOf("const AID_REFERENCE")),ctx);const record={topic:"cpr",file:"sample.mp4",sha256:"a".repeat(64),author:"Author",license:"CC BY-SA 4.0",license_url:"https://creativecommons.org/licenses/by-sa/4.0/",source:"https://commons.wikimedia.org/wiki/File:Sample.webm",ru:"Тест",en:"Test",clinical_approval:false,visual_review:"pending",rights_review:"approved",review_ref:"test-only"};ctx.record=record;assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),0);assert.equal(vm.runInContext('renderAidMedia({id:"cpr"})',ctx),"");record.clinical_approval=true;record.visual_review="approved";assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),1);assert.ok(vm.runInContext('approvedAidMedia=validateAidMedia([record]);renderAidMedia({id:"cpr"})',ctx).includes('controls playsinline preload="none"'));record.file="../sample.mp4";assert.equal(vm.runInContext("validateAidMedia([record]).length",ctx),0);});

test('medicine search finds generic and aliases, rejects unmatched queries',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('medRows("регидрон")[0].id',ctx),"ors");assert.equal(vm.runInContext('medRows("aspirin")[0].id',ctx),"aspirin");assert.equal(vm.runInContext('medRows("zz-no-match").length',ctx),0);assert.equal(vm.runInContext('medRows("").length',ctx),medicineCount);});

test('home search no longer forces navigation or uses invalid search selection API',()=>{const body=js.slice(js.indexOf("function liveSearch()"),js.indexOf('document.addEventListener("error"'));assert.ok(body.includes('$("#home-browse").hidden=active'));assert.ok(!body.includes('location.hash="#/catalog"'));assert.ok(!body.includes("setSelectionRange"));});

test('all medicine cards contain reference classification and source status, no dosing tables',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MEDICINES.filter(m=>MED_DETAILS[m.id]).length',ctx),medicineCount);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.source).length',ctx),medicineCount);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="calamine"))',ctx).includes("ссылка требует проверки"));});

test('adult CPR calls immediately and recovery position excludes trauma',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const c=pages.find(p=>p.id==="cpr"),u=pages.find(p=>p.id==="unconscious");assert.ok(c.stepsRu[1].includes("сразу вызови"));assert.ok(c.stepsEn[1].includes("immediately"));assert.ok(u.stepsRu[1].includes("отсутствии травмы"));assert.ok(u.stepsEn[1].includes("no trauma"));assert.ok(c.stepsRu.some(s=>s.includes("30 надавливаний")));});

test('original equipment artwork covers all checklist positions and missing filter works',()=>{const kits=vm.runInNewContext(js.slice(js.indexOf('const KITS='),js.indexOf('const I='))+'KITS');const ctx=vm.createContext({state:{check:{"home:0":true}}});vm.runInContext(js.slice(js.indexOf("const EQUIPMENT_DRAWINGS="),js.indexOf("const KIT_GROUPS=")),ctx);for(const k of kits){ctx.k=k;assert.equal(vm.runInContext("KIT_DRAWINGS[k.id].length",ctx),k.items.length);assert.ok(vm.runInContext("KIT_DRAWINGS[k.id].every(id=>EQUIPMENT_DRAWINGS[id])",ctx));}ctx.k=kits[0];assert.deepEqual(Array.from(vm.runInContext('missingOnly=true;kitVisibleIndices(k,[0,1])',ctx)),[1]);assert.ok(vm.runInContext('equipmentIcon("gauze")',ctx).includes("<svg"));});

test('all expanded guides have unique ids, paired steps and source for new topics',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(pages.length,162);assert.equal(new Set(pages.map(p=>p.id)).size,162);for(const p of pages){assert.equal(p.stepsRu.length,p.stepsEn.length,p.id);assert.ok(p.stepsRu.length&&p.avoidRu&&p.avoidEn,p.id);}for(const id of ["infant-choking","child-cpr","co-poison","battery-ingestion","sepsis","meningitis","pulmonary-embolism","dka","ectopic","testicular-pain"]){assert.ok(pages.some(p=>p.id===id&&p.level==="critical"));assert.match(refs[id],/^https:\/\/(www\.nhs\.uk|www\.resus\.org\.uk)\//);}assert.ok(pages.find(p=>p.id==="anaphylaxis").stepsRu.some(s=>s.includes("5 минут")));});

test('new medicine index links and cautions are distinguished from individual sources',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.sourceKind==="index").length',ctx),59);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.caution).length',ctx),71+referenceCount);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="paracetamol"))',ctx).includes("med-caution"));assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="mometasone"))',ctx).includes("общий указатель"));});

test('all medicine groups are populated and urgent categories are not lost',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MED_GROUPS.length',ctx),groupCount);assert.ok(vm.runInContext('MED_GROUPS.every(g=>MEDICINES.some(m=>m.group===g[0]))',ctx));assert.equal(vm.runInContext('new Set(MEDICINES.map(m=>m.id)).size',ctx),medicineCount);const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");assert.ok(pages.filter(p=>p.level==="critical").every(p=>["children","injuries","environment","emergency"].includes(p.category)));});

test('interactions have bilingual warnings and source links',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.interaction&&m.interaction.length===2&&m.interactionSource).length',ctx),16);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="warfarin"))',ctx).includes("Важные сочетания"));});

test('expanded eye category and new guides have matching source records',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MEDICINES.filter(m=>m.group==="eye").length',ctx),10);assert.equal(vm.runInContext('medRows("тимолол").length',ctx),1);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="timolol"))',ctx).includes("Важные сочетания"));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");for(const id of ["hip-fracture","shoulder-dislocation","compartment","rib-injury","broken-nose","hemoptysis","bronchiolitis","severe-dehydration","heat-exhaustion","sunburn","kidney-infection","acute-pancreatitis"]){assert.ok(pages.some(p=>p.id===id));assert.match(refs[id],/^https:\/\/www\.nhs\.uk\//);}});

test('100-guide milestone has source references for every new scenario',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(Object.keys(refs).length,162);for(const id of ["acute-confusion","drug-rash","sickle-crisis","appendicitis","battery-ear-nose","postpartum-bleeding","pregnancy-bleeding","newborn-jaundice","urinary-retention"]){const p=pages.find(x=>x.id===id);assert.ok(p&&p.stepsRu.length>=3&&p.stepsRu.length===p.stepsEn.length);assert.ok(refs[id]?.startsWith("https://"));}});

test('candidate medicine sources are explicitly labeled and guide references cover every topic',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.sourceKind==="candidate").length',ctx),127);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="metoprolol"))',ctx).includes("ссылка требует проверки"));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.ok(pages.every(p=>refs[p.id]));});

test('retired NHS page is replaced and six new scenarios have references',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.ok(vm.runInContext('MED_DETAILS.clotrimazole.source.endsWith("/clotrimazole/")',ctx));assert.ok(vm.runInContext('MED_DETAILS.isotretinoin.source.endsWith("/isotretinoin-roaccutane/")',ctx));assert.ok(vm.runInContext('MED_DETAILS.thiamine.sourceKind==="index"',ctx));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");for(const id of ["altitude-sickness","marine-sting","friction-blister","nose-ear-object","smoke-inhalation","motion-sickness"]){assert.ok(pages.some(p=>p.id===id));assert.ok(refs[id]);}});

test('all 534 medicine records have a source link with context honestly labeled',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.ok(vm.runInContext('MEDICINES.every(m=>MED_DETAILS[m.id].source)',ctx));assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="povidone-iodine"))',ctx).includes("частный клинический контекст"));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");for(const id of ["needlestick","dirty-puncture","human-bite","broken-tooth","eardrum-injury","contact-lens-eye","child-green-vomit","diabetic-foot-wound"]){assert.ok(pages.some(p=>p.id===id)&&refs[id]);}});

test('162-guide library retains paired instructions and prioritizes steps before cross-links',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(pages.length,162);assert.ok(pages.every(p=>refs[p.id]&&p.stepsRu.length===p.stepsEn.length));for(const id of ["tourniquet","imminent-birth","cord-prolapse","reduced-fetal-movement","kneecap-dislocation","finger-fracture","toe-fracture","achilles-rupture","paracetamol-overdose","bowel-obstruction"])assert.ok(pages.some(p=>p.id===id));const code=js.slice(js.indexOf("function renderTopic(p){"),js.indexOf("function drawNav"));assert.ok(code.indexOf("step-list")<code.indexOf("relatedEmergencyLinks(p)"));assert.ok(code.includes('p.level==="critical"')&&code.includes('p.level==="urgent"')&&code.includes("urgent-advice"));});

test('162-guide milestone includes scene safety and distinct pediatric and injury guides',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(pages.length,162);for(const id of ["scene-safety","traffic-collision","aortic-aneurysm","hyperglycemia","whooping-cough","child-asthma","acute-glaucoma","chemo-fever","jaw-injury","mushroom-poisoning"]){assert.ok(pages.some(p=>p.id===id)&&refs[id]);}assert.ok(js.slice(js.indexOf("function renderSos(){"),js.indexOf("function rankedTopics()")).includes("scene-safety-link"));});

test('14 medication red flags link to sources and valid first aid guides; pictograms are original and complete',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const flags=vm.runInContext('Object.entries(MED_DETAILS).filter(([id,m])=>m.redflag)',ctx);assert.equal(flags.length,14);for(const [id,m] of flags){assert.equal(m.redflag.length,2);assert.match(m.redflagSource,/^https:\/\/www\.nhs\.uk\//);if(m.redflagTopic)assert.ok(pages.some(p=>p.id===m.redflagTopic));}assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="methotrexate"))',ctx).includes("Когда нужна срочная помощь"));vm.runInContext(js.slice(js.indexOf("const GUIDE_PICTOGRAMS="),js.indexOf("function renderTopic(p){")),ctx);assert.equal(vm.runInContext("Object.keys(GUIDE_PICTOGRAMS).length",ctx),10);assert.equal(vm.runInContext("Object.keys(GUIDE_VISUALS).length",ctx),9);assert.ok(vm.runInContext("Object.values(GUIDE_VISUALS).flat().every(row=>GUIDE_PICTOGRAMS[row[0]]&&row[1]&&row[2])",ctx));assert.ok(vm.runInContext('renderGuideVisual({id:"stroke"})',ctx).includes("Краткая памятка"));assert.equal(vm.runInContext('renderGuideVisual({id:"nonexistent"})',ctx),"");});

test('SOS search returns only critical topics and rejects punctuation',()=>{
 const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");
 const ctx=vm.createContext({PAGES:pages,norm:s=>String(s).toLowerCase().trim(),match:(p,q)=>(p.ru+" "+p.en+" "+p.aliases).toLowerCase().includes(q)});
 vm.runInContext(js.slice(js.indexOf("const SEARCH_PHRASES="),js.indexOf("function sosSearchResults(")),ctx);
 assert.ok(vm.runInContext('sosMatches("инсульт").some(p=>p.id==="stroke")',ctx));
 assert.ok(vm.runInContext('sosMatches("инсульт").every(p=>p.level==="critical")',ctx));
 assert.equal(vm.runInContext('sosMatches("").length',ctx),0);
 assert.equal(vm.runInContext('sosMatches("x").length',ctx),0);
});
test('combined kit inventory uses all legacy positions and counts only checked booleans',()=>{
 const kits=vm.runInNewContext(js.slice(js.indexOf('const KITS='),js.indexOf('const I='))+'KITS');
 const ctx=vm.createContext({KITS:kits,state:{lang:"en",check:{"home:0":true,"travel:0":"true"}},esc:String});
 vm.runInContext(js.slice(js.indexOf("function kitOverview("),js.indexOf("function refreshKitOverview(")),ctx);
 const out=vm.runInContext("kitOverview()",ctx);
 assert.ok(out.includes("1 / 42"));assert.equal((out.match(/<li>/g)||[]).length,41);
});

test('step-bound media requires the exact bilingual reviewed step and rights approval',()=>{
 const ctx=vm.createContext({PAGES:[{id:"cpr",stepsRu:["RU"],stepsEn:["EN"]}],MED_LICENSE_URLS:new Set(["https://creativecommons.org/licenses/by-sa/4.0/"]),state:{lang:"ru"},esc:String});
 vm.runInContext(js.slice(js.indexOf("const AID_MEDIA_LICENSES"),js.indexOf("const AID_REFERENCE")),ctx);
 ctx.record={topic:"cpr",file:"fixture.mp4",sha256:"a".repeat(64),author:"Author",license:"CC BY-SA 4.0",license_url:"https://creativecommons.org/licenses/by-sa/4.0/",source:"https://commons.wikimedia.org/wiki/File:Fixture.webm",ru:"Фото",en:"Photo",clinical_approval:true,visual_review:"approved",rights_review:"approved",review_ref:"test-only",step_index:0,step_ru:"RU",step_en:"EN"};
 assert.equal(vm.runInContext("validateAidMedia([record,record]).length",ctx),1);
 assert.ok(vm.runInContext('approvedAidMedia=validateAidMedia([record]);renderStepAidMedia(PAGES[0],0)',ctx).includes("fixture.mp4"));
 assert.equal(vm.runInContext("renderAidMedia(PAGES[0])",ctx),"");
 ctx.record.step_en='changed';assert.equal(vm.runInContext('validateAidMedia([record]).length',ctx),0);ctx.record.step_en='EN';ctx.record.rights_review='pending';assert.equal(vm.runInContext('validateAidMedia([record]).length',ctx),0);
});

test('symbolic step cues map only to existing steps and are decorative',()=>{
 const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");
 const ctx=vm.createContext({state:{lang:"ru"},esc:String});
 vm.runInContext(js.slice(js.indexOf("const GUIDE_PICTOGRAMS="),js.indexOf("function renderTopic(p){")),ctx);
 const mappings=vm.runInContext("STEP_CUES",ctx);
 assert.ok(pages.filter(p=>p.level==='critical').every(p=>mappings[p.id]?.length===p.stepsRu.length&&mappings[p.id].some(Boolean)));
 assert.equal(Object.keys(mappings).length,87);
 for(const [id,icons] of Object.entries(mappings)){
  const p=pages.find(p=>p.id===id);assert.ok(p,id);assert.equal(icons.length,p.stepsRu.length,id);
  ctx.p=p;for(let i=0;i<icons.length;i++)if(icons[i])assert.ok(vm.runInContext("renderStepCue(p,"+i+")",ctx).includes('aria-hidden="true"'));
 }
});

test('real panic search phrases prioritize relevant guides without diagnosis or automatic navigation',()=>{
 const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");
 const ctx=vm.createContext({PAGES:pages});
 const norm=js.split("\n").find(x=>x.startsWith("const norm="));
 const fuzzy=js.split("\n").find(x=>x.startsWith("const match="));
 const edit=js.slice(js.indexOf("function oneEdit("),js.indexOf("\n}",js.indexOf("function oneEdit("))+2);
 vm.runInContext(norm+"\n"+fuzzy+"\n"+edit+"\n"+js.slice(js.indexOf("const SEARCH_PHRASES="),js.indexOf("function sosSearchResults(")),ctx);
 const cases=[["сильно течёт кровь","bleeding"],["потерял сознание","unconscious"],["человек не дышит","cpr"],["ребёнок не дышит","child-cpr"],["младенец подавился","infant-choking"],["не могу вдохнуть","asthma"],["перекосило лицо","stroke"],["болит грудь","heart"],["chest pain","heart"],["baby not breathing","child-cpr"],["без сознания но дышит","unconscious"],["не дышет","cpr"],["ударило током","electric"],["сильное кровотечение после родов","postpartum-bleeding"]];
 for(const [q,id] of cases){ctx.q=q;const got=vm.runInContext("sosMatches(q)",ctx);assert.ok(got.slice(0,2).some(p=>p.id===id),q+" => "+got.slice(0,2).map(p=>p.id));assert.ok(got.every(p=>p.level==="critical"))}
 ctx.q="сильно течет кровь";assert.equal(vm.runInContext("sosMatches(q)[0].id",ctx),"bleeding");
 ctx.q="ребенок не дышит";assert.equal(vm.runInContext("sosMatches(q)[0].id",ctx),"child-cpr");
 ctx.q="chest pain";assert.equal(vm.runInContext("sosMatches(q)[0].id",ctx),"heart");
 ctx.q="ожог";assert.equal(vm.runInContext("searchTopicRows(q)[0].id",ctx),"burn");
 ctx.q="не дышит";assert.ok(vm.runInContext("sosMatches(q).slice(0,2).some(p=>p.id==='child-cpr')",ctx));
 ctx.q="zzznoresults";assert.equal(vm.runInContext("sosMatches(q).length",ctx),0);
 assert.ok(vm.runInContext("SEARCH_PHRASES.every(([ids,phrases])=>phrases.length&&ids.every(id=>PAGES.some(p=>p.id===id)))",ctx));
});

test('screen awake only in visible emergency mode and respects preference',()=>{
 const ctx=vm.createContext({state:{keepAwake:true},document:{hidden:false,body:{classList:{contains:()=>true}}},window:{PulsDisplay:{postMessage:v=>sent.push(v)}}});
 const sent=[];
 vm.runInContext(js.slice(js.indexOf("function notifyEmergencyAwake("),js.indexOf("function renderMore(){")),ctx);
 vm.runInContext("notifyEmergencyAwake()",ctx);assert.equal(sent.at(-1),"on");
 ctx.document.hidden=true;vm.runInContext("notifyEmergencyAwake()",ctx);assert.equal(sent.at(-1),"off");
 ctx.document.hidden=false;ctx.state.keepAwake=false;vm.runInContext("notifyEmergencyAwake()",ctx);assert.equal(sent.at(-1),"off");
});

test('large step media groups show one primary photo and collapse extra media',()=>{
 const ctx=vm.createContext({PAGES:[{id:"cpr",stepsRu:["RU"],stepsEn:["EN"]}],MED_LICENSE_URLS:new Set(["https://creativecommons.org/licenses/by-sa/4.0/"]),state:{lang:"en"},esc:String});
 vm.runInContext(js.slice(js.indexOf("const AID_MEDIA_LICENSES"),js.indexOf("const AID_REFERENCE")),ctx);
 const row={topic:"cpr",file:"fixture.mp4",sha256:"a".repeat(64),author:"Author",license:"CC BY-SA 4.0",license_url:"https://creativecommons.org/licenses/by-sa/4.0/",source:"https://commons.wikimedia.org/wiki/File:Fixture.webm",ru:"Фото",en:"Photo",clinical_approval:true,visual_review:"approved",rights_review:"approved",review_ref:"test",step_index:0,step_ru:"RU",step_en:"EN"};
 ctx.rows=[row,{...row,file:"first.jpg"},{...row,file:"second.jpg"}];
 const out=vm.runInContext("approvedAidMedia=validateAidMedia(rows);renderStepAidMedia(PAGES[0],0)",ctx);
 assert.ok(out.indexOf("first.jpg")<out.indexOf("step-extra-media"));
 assert.ok(out.indexOf("step-extra-media")<out.indexOf("fixture.mp4"));
 assert.match(out,/<details class="step-extra-media">/);
});

test('expanded library includes 12 sourced guide drafts and 40 clearly labeled medicine records',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");for(const id of ["severe-hypoglycaemia","neck-compression","nonblanching-rash","infant-dehydration","shingles-eye","uveitis-warning","hand-foot-mouth","chickenpox-risk","cellulitis","breast-abscess","pneumonia-warning","ear-infection-warning"])assert.ok(pages.some(p=>p.id===id)&&refs[id]);const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);for(const id of ["acarbose","glucagon","pregabalin","venlafaxine","trazodone","vortioxetine","moclobemide","lacosamide","brivaracetam","zonisamide","pramipexole","rasagiline","entacapone","rivastigmine","galantamine","sildenafil","tadalafil","sodium-alginate","miconazole","itraconazole","valaciclovir","oseltamivir","rifampicin","isoniazid","co-trimoxazole","salmeterol","formoterol","ipratropium","umeclidinium","brimonidine","dorzolamide","travoprost","bisoprolol-hydrochlorothiazide","hydrochlorothiazide","dabigatran","enoxaparin","fondaparinux","ticagrelor","sacubitril-valsartan","febuxostat"]){ctx.id=id;assert.equal(vm.runInContext("MED_DETAILS[id].sourceKind",ctx),"index");assert.ok(vm.runInContext("MED_DETAILS[id].caution.length===2",ctx));}});

test('backup of the entire guide library round-trips, old schema remains compatible',()=>{
 const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");
 const area={value:""};let message="";
 const state={lang:"ru",light:false,large:true,hicontrast:false,num:"112",saved:pages.map(p=>p.id),recent:[],check:{"home:0":true},keepAwake:false,kitOpen:"home"};
 const ctx=vm.createContext({PAGES:pages,KITS:[{id:"home",items:[1]},{id:"travel",items:[1]}],state,document:{querySelector:()=>area},toastMessage:s=>message=s,t:s=>s,confirm:()=>true,store:{set:()=>true},route:()=>{}});
 vm.runInContext(js.slice(js.indexOf("function makeBackup()"),js.indexOf("function quickSuggestions()")),ctx);
 const exported=JSON.parse(vm.runInContext("JSON.stringify(makeBackup())",ctx));
 assert.equal(exported.saved.length,pages.length);assert.equal(exported.keepAwake,false);
 area.value=JSON.stringify(exported);state.saved=[];state.keepAwake=true;state.kitOpen="travel";
 vm.runInContext("importBackup()",ctx);
 assert.equal(message,"backupRestored");assert.equal(state.saved.length,pages.length);assert.equal(state.keepAwake,false);assert.equal(state.kitOpen,"home");
 delete exported.keepAwake;delete exported.kitOpen;area.value=JSON.stringify(exported);state.keepAwake=true;
 vm.runInContext("importBackup()",ctx);assert.equal(message,"backupRestored");assert.equal(state.keepAwake,true);
 exported.keepAwake="false";area.value=JSON.stringify(exported);vm.runInContext("importBackup()",ctx);assert.equal(message,"backupError");assert.equal(state.keepAwake,true);
});

test('reviewed media index matches the manifest, rejects invalid records and refreshes',()=>{
 const PAGES=[{id:"cpr",stepsRu:["r"],stepsEn:["e"]},{id:"stroke",stepsRu:["r"],stepsEn:["e"]}];
 const license="https://creativecommons.org/publicdomain/zero/1.0/";
 const ctx=vm.createContext({PAGES,state:{lang:"ru"},esc:String,MED_LICENSE_URLS:new Set([license])});
 vm.runInContext(js.slice(js.indexOf("const AID_MEDIA_LICENSES"),js.indexOf("const AID_REFERENCE")),ctx);
 const fixture=i=>({topic:i%2?"cpr":"stroke",file:"sample-"+i+".jpg",sha256:"a".repeat(64),author:"Synthetic QA",license:"CC0 1.0",license_url:license,source:"https://commons.wikimedia.org/wiki/File:Sample.jpg",ru:"Тест",en:"Test",clinical_approval:true,visual_review:"approved",rights_review:"approved",review_ref:"TEST ONLY"});
 ctx.records=[null,{...fixture(6000),clinical_approval:false},{...fixture(6001),step_index:0,step_ru:"changed",step_en:"e"},...Array.from({length:5200},(_,i)=>fixture(i)),fixture(0)];
 vm.runInContext("approvedAidMedia=validateAidMedia(records)",ctx);
 assert.equal(vm.runInContext("approvedAidMedia.length",ctx),5000);
 for(const id of ["cpr","stroke"]){ctx.id=id;assert.deepEqual(Array.from(vm.runInContext("topicAidRows({id}).map(a=>a.file)",ctx)),Array.from(vm.runInContext("approvedAidMedia.filter(a=>a.topic===id).map(a=>a.file)",ctx)));}
 ctx.records=[fixture(1)];vm.runInContext("approvedAidMedia=validateAidMedia(records)",ctx);
 assert.equal(vm.runInContext('topicAidRows({id:"cpr"}).length',ctx),1);
 assert.equal(vm.runInContext('topicAidRows({id:"stroke"}).length',ctx),0);
});

test('library status distinguishes photo-only, video-only and full guide coverage',()=>{
 const ctx=vm.createContext({});
 vm.runInContext(js.slice(js.indexOf("function guideMediaCoverage"),js.indexOf("function mediaCoverage")),ctx);
 ctx.pages=[{id:"a",level:"critical"},{id:"b",level:"urgent"},{id:"c",level:"critical"},{id:"d",level:"urgent"}];
 ctx.records=[{topic:"a",file:"one.jpg"},{topic:"a",file:"two.jpg"},{topic:"a",file:"three.mp4"},{topic:"b",file:"four.mp4"},{topic:"d",file:"five.jpg"},{topic:"unknown",file:"six.jpg"}];
 const result=JSON.parse(vm.runInContext("JSON.stringify(guideMediaCoverage(pages,records))",ctx));
 assert.deepEqual(result,{guides:3,critical:1,photoGuides:2,videoGuides:2,both:1,criticalBoth:1,photos:3,videos:2});
 assert.equal(vm.runInContext("guideMediaCoverage(pages,[]).both",ctx),0);
});

test('all 162 bilingual guides and seven primary screens render complete steps and valid topic links',()=>{
 const cut=js.indexOf('window.addEventListener("hashchange",()=>route());');
 assert.ok(cut>0);
 const ctx=vm.createContext({localStorage:{getItem:()=>null,setItem:()=>{}},location:{hash:"#/home"},history:{state:null,replaceState(){}},window:{addEventListener(){}},document:{addEventListener(){},querySelector(){return null},querySelectorAll(){return []},body:{classList:{contains:()=>false}}}});
 vm.runInContext(js.slice(0,cut),ctx);
 const result=JSON.parse(vm.runInContext(`JSON.stringify((()=>{
 const ids=new Set(PAGES.map(p=>p.id));let screens=0,steps=0,unknown=[];
 function scan(html){screens++;if(!html.includes("<h1>"))throw Error("no title");for(const m of html.matchAll(/href="#\\/topic\\/([^"]+)"/g))if(!ids.has(decodeURIComponent(m[1])))unknown.push(m[1]);}
 for(const lang of ["ru","en"]){state.lang=lang;for(const p of PAGES){const html=renderTopic(p);scan(html);const n=(html.match(/class="step"/g)||[]).length;if(n!==(lang==="ru"?p.stepsRu:p.stepsEn).length)throw Error("step mismatch "+p.id);steps+=n;if(p.level==="critical"&&!html.includes('href="tel:112"'))throw Error("missing SOS "+p.id)}
 for(const [hash,render] of [["#/home",renderHome],["#/sos",renderSos],["#/catalog",renderCatalog],["#/kits",renderKits],["#/kits/medicines",renderKits],["#/more",renderMore],["#/favorites",renderFavorites]]){location.hash=hash;scan(render())}}
 return {screens,steps,unknown};
 })())`,ctx));
 assert.deepEqual(result,{screens:338,steps:1002,unknown:[]});
});

test('294 source-only medicine cards use unique MedlinePlus links and omit dosing',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);const result=vm.runInContext('MEDICINES.filter(m=>m.group==="reference").map(m=>({id:m.id,source:MED_DETAILS[m.id].source,kind:MED_DETAILS[m.id].sourceKind,redflag:MED_DETAILS[m.id].redflag,interaction:MED_DETAILS[m.id].interaction}))',ctx);assert.equal(result.length,referenceCount);assert.equal(new Set(result.map(m=>m.source)).size,referenceCount);for(const m of result){assert.match(m.source,/^https:\/\/medlineplus\.gov\/druginfo\/meds\/a\d+\.html$/);assert.equal(m.kind,"external-reference");assert.equal(m.redflag,undefined);assert.equal(m.interaction,undefined)}assert.equal(vm.runInContext('medRows("дезлоратадин")[0].id',ctx),"desloratadine")});

test('review gallery never auto-plays, filters and separates candidates from emergency guide',()=>{
 const a=js.indexOf("let reviewMedia=null"),b=js.indexOf("function notifyEmergencyAwake(",a);
 const ctx=vm.createContext({state:{lang:"ru"},esc:v=>String(v||"").replace(/"/g,"&quot;"),title:v=>"<h1>"+v+"</h1>",document:{addEventListener(){}},fetch:()=>Promise.resolve({ok:false})});
 vm.runInContext(js.slice(a,b),ctx);
 ctx.records=[{file:"a".repeat(40)+".jpg",title:"Test image",author:"QA",license:"CC0",labels:[{group:"medicine",ru:"Аптека",en:"Pharmacy"}]},{file:"b".repeat(40)+".mp4",title:"Test video",author:"QA",license:"CC0",labels:[{group:"guide",ru:"Проверка",en:"Review"}]}];
 vm.runInContext("reviewMedia=records",ctx);
 assert.equal(vm.runInContext('reviewRows("аптека","photo","medicine").length',ctx),1);
 assert.equal(vm.runInContext('reviewRows("","video","medicine").length',ctx),0);
 assert.match(vm.runInContext("renderReview()",ctx),/Не проверено врачом/);
 assert.match(vm.runInContext("reviewCards(records)",ctx),/preload="none"/);
 assert.doesNotMatch(vm.runInContext("reviewCards(records)",ctx),/autoplay/);
 assert.doesNotMatch(js.slice(js.indexOf("function renderTopic("),js.indexOf("function drawNav(")),/reviewMedia|media\/review/);
});

test('expanded gallery keeps a bounded twelve-card window across pages and supports multiword searches',()=>{
 const a=js.indexOf("let reviewMedia=null"),b=js.indexOf("function notifyEmergencyAwake(",a);
 const ctx=vm.createContext({state:{lang:"ru"},esc:v=>String(v||""),document:{addEventListener(){}}});
 vm.runInContext(js.slice(a,b),ctx);
 ctx.records=Array.from({length:826},(_,i)=>({file:i.toString(16).padStart(40,"0")+".jpg",title:"Тест "+i,author:"QA",labels:[{group:"medicine",ru:"Лекарство",en:"Drug"}]}));
 vm.runInContext("reviewMedia=records;reviewOffset=12",ctx);
 const html=vm.runInContext("reviewCards(records)",ctx);
 assert.equal((html.match(/class="panel secondary review-card"/g)||[]).length,12);
 assert.match(html,/<strong>Тест 12<\/strong>/);assert.doesNotMatch(html,/<strong>Тест 0<\/strong>/);
 assert.equal(vm.runInContext('reviewRows("лекарство QA","photo","medicine").length',ctx),826);
});

test('gallery search normalizes punctuation and Cyrillic, caches immutable record text',()=>{
 const a=js.indexOf("let reviewMedia=null"),b=js.indexOf("function notifyEmergencyAwake(",a);
 const ctx=vm.createContext({state:{lang:"ru"},esc:String});
 vm.runInContext(js.slice(a,b),ctx);
 ctx.records=[{file:"a".repeat(40)+".jpg",title:"Ожёг — тест",author:"QA",labels:[{group:"guide",ru:"Первая помощь",en:"First aid"}]},{file:"b".repeat(40)+".mp4",title:"Other",author:"QA",labels:[]}];
 vm.runInContext("reviewMedia=records",ctx);
 assert.equal(vm.runInContext('reviewRows("ожег, помощь","photo","guide").length',ctx),1);
 assert.equal(vm.runInContext('reviewRows("first-aid","","guide").length',ctx),1);
 assert.equal(vm.runInContext('reviewRows("unknown","","").length',ctx),0);
 assert.equal(vm.runInContext('reviewSearchCache.has(records[0])',ctx),true);
});

test('step-only filter and long search-label list remain bounded in the QA gallery',()=>{
 const a=js.indexOf("let reviewMedia=null"),b=js.indexOf("function notifyEmergencyAwake(",a);
 const ctx=vm.createContext({state:{lang:"ru"},esc:v=>String(v||"")});
 vm.runInContext(js.slice(a,b),ctx);
 ctx.records=[{file:"a".repeat(40)+".jpg",title:"Original",author:"QA",labels:Array.from({length:30},(_,i)=>({group:"guide",step:true,ru:"Шаг "+i,en:"Step "+i}))},{file:"b".repeat(40)+".jpg",title:"Other",author:"QA",labels:[{group:"guide",step:false,ru:"Общая тема",en:"Guide"}]}];
 vm.runInContext("reviewMedia=records",ctx);
 assert.equal(vm.runInContext('reviewRows("","","step").length',ctx),1);
 assert.equal(vm.runInContext('reviewRows("","","guide").length',ctx),2);
 assert.match(vm.runInContext("reviewCards(records)",ctx),/Ещё поисковые темы: 27/);
});

test('review filters and page survive rerender and clear safely',()=>{
 const a=js.indexOf("let reviewMedia=null"),b=js.indexOf("function notifyEmergencyAwake(",a);
 const ctx=vm.createContext({state:{lang:"ru"},esc:v=>String(v??"").replace(/"/g,"&quot;"),title:v=>"<h1>"+v+"</h1>"});
 vm.runInContext(js.slice(a,b),ctx);
 ctx.records=Array.from({length:35},(_,i)=>({file:i.toString(16).padStart(40,"0")+".jpg",title:"QA "+i,author:"QA",labels:[{group:"medicine",ru:"Препарат",en:"Drug"}]}));
 vm.runInContext('reviewMedia=records;reviewFilters.q="Препарат";reviewFilters.kind="photo";reviewFilters.group="medicine";reviewOffset=24',ctx);
 let html=vm.runInContext("renderReview()",ctx);
 assert.match(html,/value="Препарат"/);assert.match(html,/value="photo" selected/);assert.match(html,/25–35/);
 html=vm.runInContext('state.lang="en";renderReview()',ctx);
 assert.match(html,/25–35/);assert.match(html,/Found: 35/);
 vm.runInContext('reviewFilters.q="none";reviewSelection()',ctx);
 assert.equal(vm.runInContext("reviewOffset",ctx),0);
 assert.match(vm.runInContext("renderReview()",ctx),/No matches/);
 vm.runInContext("clearReviewFilters()",ctx);
 assert.equal(vm.runInContext("reviewSelection().length",ctx),35);
});

test('quality filters and coverage panel never imply approval',()=>{
 const a=js.indexOf("let reviewMedia=null"),b=js.indexOf("function notifyEmergencyAwake(",a);
 const ctx=vm.createContext({state:{lang:"ru"},esc:v=>String(v??"")});
 vm.runInContext(js.slice(a,b),ctx);
 ctx.records=[{file:"a".repeat(40)+".jpg",title:"QA",review_quality:{priority:0,flags:["multiple-drug-identities","no-title-token-match"]},labels:[]},{file:"b".repeat(40)+".mp4",title:"Other",review_quality:{priority:2,flags:[]},labels:[]}];
 vm.runInContext('reviewMedia=records;reviewSummary={coverage:{guide_step:{targets:501,photo_targets:224,video_targets:136}}}',ctx);
 assert.equal(vm.runInContext('reviewRows("","","priority").length',ctx),1);
 assert.equal(vm.runInContext('reviewRows("","","unmatched").length',ctx),1);
 assert.match(vm.runInContext('reviewCards(records)',ctx),/Несколько препаратов/);
 assert.match(vm.runInContext('reviewCoveragePanel()',ctx),/224\/501/);
 assert.match(vm.runInContext('reviewCoveragePanel()',ctx),/не подтверждённые/);
});
