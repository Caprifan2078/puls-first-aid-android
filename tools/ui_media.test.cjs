const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const page=fs.readFileSync('app/src/main/assets/index.html','utf8');
const js=page.match(/<script>([\s\S]*?)<\/script>/)[1];
test('inline script compiles',()=>assert.doesNotThrow(()=>new vm.Script(js)));
test('medicine shelf is grouped, bilingual and has no empty image slots',()=>{
 const chunk=js.slice(js.indexOf('const MEDICINES='),js.indexOf('const KIT_GROUPS='));
 const ctx=vm.createContext({state:{lang:'ru'},esc:v=>String(v)});
 vm.runInContext(chunk,ctx);
 const ru=vm.runInContext('renderMedicineShelf()',ctx);
 assert.equal((ru.match(/medicine-group/g)||[]).length,5);
 assert.equal((ru.match(/medicine-row/g)||[]).length,9);
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
 assert.ok(js.includes('d.open=groups.includes(d.dataset.group)'));
});

test('all three kit group mappings cover each item exactly once and keep legacy keys',()=>{const kits=vm.runInNewContext(js.slice(js.indexOf('const KITS='),js.indexOf('const I='))+'KITS');const groups=vm.runInNewContext(js.slice(js.indexOf('const KIT_GROUPS='),js.indexOf('const KIT_SOURCE='))+'KIT_GROUPS');assert.deepEqual(Array.from(kits,k=>k.id),['home','travel','outdoor']);for(const k of kits){const ids=Array.from(groups[k.id].flatMap(g=>g[2])).sort((a,b)=>a-b);assert.deepEqual(ids,Array.from({length:k.items.length},(_,i)=>i));assert.ok(k.items.length>=13);}});
test('SOS priority topics are unique and exist',()=>{const pages=vm.runInNewContext(js.slice(js.indexOf('const PAGES='),js.indexOf('const KITS='))+'PAGES');const order=vm.runInNewContext(js.slice(js.indexOf('const SOS_ORDER='),js.indexOf('const SOS_LABELS='))+'SOS_ORDER');assert.equal(new Set(order).size,order.length);for(const id of order)assert.ok(pages.some(p=>p.id===id));});
