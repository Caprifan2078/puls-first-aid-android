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
 assert.equal((ru.match(/medicine-group/g)||[]).length,12);
 assert.equal((ru.match(/medicine-row/g)||[]).length,200);
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

test('medicine search finds generic and aliases, rejects unmatched queries',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('medRows("регидрон")[0].id',ctx),"ors");assert.equal(vm.runInContext('medRows("aspirin")[0].id',ctx),"aspirin");assert.equal(vm.runInContext('medRows("zz-no-match").length',ctx),0);assert.equal(vm.runInContext('medRows("").length',ctx),200);});

test('home search no longer forces navigation or uses invalid search selection API',()=>{const body=js.slice(js.indexOf("function liveSearch()"),js.indexOf('document.addEventListener("error"'));assert.ok(body.includes('$("#home-browse").hidden=active'));assert.ok(!body.includes('location.hash="#/catalog"'));assert.ok(!body.includes("setSelectionRange"));});

test('all medicine cards contain reference classification and source status, no dosing tables',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MEDICINES.filter(m=>MED_DETAILS[m.id]).length',ctx),200);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.source).length',ctx),200);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="calamine"))',ctx).includes("ссылка требует проверки"));});

test('adult CPR calls immediately and recovery position excludes trauma',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const c=pages.find(p=>p.id==="cpr"),u=pages.find(p=>p.id==="unconscious");assert.ok(c.stepsRu[1].includes("сразу вызови"));assert.ok(c.stepsEn[1].includes("immediately"));assert.ok(u.stepsRu[1].includes("отсутствии травмы"));assert.ok(u.stepsEn[1].includes("no trauma"));assert.ok(c.stepsRu.some(s=>s.includes("30 надавливаний")));});

test('original equipment artwork covers all checklist positions and missing filter works',()=>{const kits=vm.runInNewContext(js.slice(js.indexOf('const KITS='),js.indexOf('const I='))+'KITS');const ctx=vm.createContext({state:{check:{"home:0":true}}});vm.runInContext(js.slice(js.indexOf("const EQUIPMENT_DRAWINGS="),js.indexOf("const KIT_GROUPS=")),ctx);for(const k of kits){ctx.k=k;assert.equal(vm.runInContext("KIT_DRAWINGS[k.id].length",ctx),k.items.length);assert.ok(vm.runInContext("KIT_DRAWINGS[k.id].every(id=>EQUIPMENT_DRAWINGS[id])",ctx));}ctx.k=kits[0];assert.deepEqual(Array.from(vm.runInContext('missingOnly=true;kitVisibleIndices(k,[0,1])',ctx)),[1]);assert.ok(vm.runInContext('equipmentIcon("gauze")',ctx).includes("<svg"));});

test('all expanded guides have unique ids, paired steps and source for new topics',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(pages.length,150);assert.equal(new Set(pages.map(p=>p.id)).size,150);for(const p of pages){assert.equal(p.stepsRu.length,p.stepsEn.length,p.id);assert.ok(p.stepsRu.length&&p.avoidRu&&p.avoidEn,p.id);}for(const id of ["infant-choking","child-cpr","co-poison","battery-ingestion","sepsis","meningitis","pulmonary-embolism","dka","ectopic","testicular-pain"]){assert.ok(pages.some(p=>p.id===id&&p.level==="critical"));assert.match(refs[id],/^https:\/\/(www\.nhs\.uk|www\.resus\.org\.uk)\//);}assert.ok(pages.find(p=>p.id==="anaphylaxis").stepsRu.some(s=>s.includes("5 минут")));});

test('new medicine index links and cautions are distinguished from individual sources',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.sourceKind==="index").length',ctx),19);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.caution).length',ctx),31);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="paracetamol"))',ctx).includes("med-caution"));assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="mometasone"))',ctx).includes("общий указатель"));});

test('all medicine groups are populated and urgent categories are not lost',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MED_GROUPS.length',ctx),12);assert.ok(vm.runInContext('MED_GROUPS.every(g=>MEDICINES.some(m=>m.group===g[0]))',ctx));assert.equal(vm.runInContext('new Set(MEDICINES.map(m=>m.id)).size',ctx),200);const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");assert.ok(pages.filter(p=>p.level==="critical").every(p=>["children","injuries","environment","emergency"].includes(p.category)));});

test('interactions have bilingual warnings and source links',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.interaction&&m.interaction.length===2&&m.interactionSource).length',ctx),16);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="warfarin"))',ctx).includes("Важные сочетания"));});

test('expanded eye category and new guides have matching source records',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('MEDICINES.filter(m=>m.group==="eye").length',ctx),7);assert.equal(vm.runInContext('medRows("тимолол").length',ctx),1);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="timolol"))',ctx).includes("Важные сочетания"));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");for(const id of ["hip-fracture","shoulder-dislocation","compartment","rib-injury","broken-nose","hemoptysis","bronchiolitis","severe-dehydration","heat-exhaustion","sunburn","kidney-infection","acute-pancreatitis"]){assert.ok(pages.some(p=>p.id===id));assert.match(refs[id],/^https:\/\/www\.nhs\.uk\//);}});

test('100-guide milestone has source references for every new scenario',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(Object.keys(refs).length,150);for(const id of ["acute-confusion","drug-rash","sickle-crisis","appendicitis","battery-ear-nose","postpartum-bleeding","pregnancy-bleeding","newborn-jaundice","urinary-retention"]){const p=pages.find(x=>x.id===id);assert.ok(p&&p.stepsRu.length>=3&&p.stepsRu.length===p.stepsEn.length);assert.ok(refs[id]?.startsWith("https://"));}});

test('candidate medicine sources are explicitly labeled and guide references cover every topic',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.equal(vm.runInContext('Object.values(MED_DETAILS).filter(m=>m.sourceKind==="candidate").length',ctx),127);assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="metoprolol"))',ctx).includes("ссылка требует проверки"));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.ok(pages.every(p=>refs[p.id]));});

test('retired NHS page is replaced and six new scenarios have references',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.ok(vm.runInContext('MED_DETAILS.clotrimazole.source.endsWith("/clotrimazole/")',ctx));assert.ok(vm.runInContext('MED_DETAILS.isotretinoin.source.endsWith("/isotretinoin-roaccutane/")',ctx));assert.ok(vm.runInContext('MED_DETAILS.thiamine.sourceKind==="index"',ctx));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");for(const id of ["altitude-sickness","marine-sting","friction-blister","nose-ear-object","smoke-inhalation","motion-sickness"]){assert.ok(pages.some(p=>p.id===id));assert.ok(refs[id]);}});

test('all 200 medicine records have a source link with context honestly labeled',()=>{const ctx=vm.createContext({state:{lang:"ru"},esc:String,norm:v=>String(v||"").toLowerCase()});vm.runInContext(js.slice(js.indexOf("const MEDICINES="),js.indexOf("const KIT_GROUPS=")),ctx);assert.ok(vm.runInContext('MEDICINES.every(m=>MED_DETAILS[m.id].source)',ctx));assert.ok(vm.runInContext('renderMedDetails(MEDICINES.find(m=>m.id==="povidone-iodine"))',ctx).includes("частный клинический контекст"));const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");for(const id of ["needlestick","dirty-puncture","human-bite","broken-tooth","eardrum-injury","contact-lens-eye","child-green-vomit","diabetic-foot-wound"]){assert.ok(pages.some(p=>p.id===id)&&refs[id]);}});

test('150-guide library retains paired instructions and prioritizes steps before cross-links',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(pages.length,150);assert.ok(pages.every(p=>refs[p.id]&&p.stepsRu.length===p.stepsEn.length));for(const id of ["tourniquet","imminent-birth","cord-prolapse","reduced-fetal-movement","kneecap-dislocation","finger-fracture","toe-fracture","achilles-rupture","paracetamol-overdose","bowel-obstruction"])assert.ok(pages.some(p=>p.id===id));const code=js.slice(js.indexOf("function renderTopic(p){"),js.indexOf("function drawNav"));assert.ok(code.indexOf("step-list")<code.indexOf("relatedEmergencyLinks(p)"));assert.ok(code.includes('p.level==="critical"')&&code.includes('p.level==="urgent"')&&code.includes("urgent-advice"));});

test('150-guide milestone includes scene safety and distinct pediatric and injury guides',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf("const PAGES="),js.indexOf("const NAV="))+"PAGES");const refs=vm.runInNewContext(js.slice(js.indexOf("const AID_REFERENCE="),js.indexOf("function aidReference"))+"AID_REFERENCE");assert.equal(pages.length,150);for(const id of ["scene-safety","traffic-collision","aortic-aneurysm","hyperglycemia","whooping-cough","child-asthma","acute-glaucoma","chemo-fever","jaw-injury","mushroom-poisoning"]){assert.ok(pages.some(p=>p.id===id)&&refs[id]);}assert.ok(js.slice(js.indexOf("function renderSos(){"),js.indexOf("function rankedTopics()")).includes("scene-safety-link"));});

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
 assert.equal(Object.keys(mappings).length,34);
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
