const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const page=fs.readFileSync('app/src/main/assets/index.html','utf8');
const js=page.match(/<script>([\s\S]*?)<\/script>/)[1];
test('inline script compiles',()=>assert.doesNotThrow(()=>new vm.Script(js)));
test('medicine shelf is grouped, bilingual and has no empty image slots',()=>{
 const chunk=js.slice(js.indexOf('const MEDICINES='),js.indexOf('function renderKits(){'));
 const ctx=vm.createContext({state:{lang:'ru'},esc:v=>String(v)});
 vm.runInContext(chunk,ctx);
 const ru=vm.runInContext('renderMedicineShelf()',ctx);
 assert.equal((ru.match(/medicine-group/g)||[]).length,4);
 assert.equal((ru.match(/medicine-row/g)||[]).length,6);
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
