const fs=require('node:fs'),assert=require('node:assert/strict');
const harness=fs.readFileSync('tests/study_native_study_tools.cjs','utf8');
const create=new Function('require',harness.slice(0,harness.indexOf('const stringify='))+';return create;')(require);
const KEY='kyapyatango-study:v1';
(async()=>{
for(const mode of ['words','examples']){
 const key=KEY+(mode==='examples'?':examples':'');
 const original={records:{'old-card':{rating:'hard',due:'2026-10-25'}},session:{queue:['removed-card'],index:0,repeat:[],ratings:{again:0,hard:0,remembered:0},initial:1}};
 const raw=JSON.stringify(original);let t=create({[KEY+':mode']:mode,[key]:raw});
 assert.equal(t.run('readIssue'),'stale');assert.equal(t.storage.get(key),raw);assert(t.nodes.get('recoverSession'));
 const handler=t.nodes.get('recoverSession').onclick;await handler();assert.equal(t.run('readIssue'),null);assert.deepEqual(t.get('state.records'),original.records);assert.equal(t.run('state.session'),null);
 let backups=[...t.storage].filter(([k])=>k.startsWith(key+':stale-session-backup:'));assert.equal(backups.length,1);assert.equal(backups[0][1],raw);
 const repaired=t.storage.get(key);await handler();assert.equal(t.storage.get(key),repaired);assert.equal([...t.storage].filter(([k])=>k.startsWith(key+':stale-session-backup:')).length,1);
 t=create({[KEY+':mode']:mode,[key]:raw});t.storage.set(key,JSON.stringify({records:{},session:null}));await t.nodes.get('recoverSession').onclick();assert.equal(t.nodes.get('conflict-dialog').open,true);assert.equal(t.storage.get(key),JSON.stringify({records:{},session:null}));assert(![...t.storage.keys()].some(k=>k.includes(':stale-session-backup:')));
 t=create({[KEY+':mode']:mode,[key]:raw});t.run("localStorage.setItem=()=>{throw new Error('blocked')}");await t.nodes.get('recoverSession').onclick();assert.equal(t.storage.get(key),raw);assert.equal(t.run('readIssue'),'stale');
 t=create({[KEY+':mode']:mode,[key]:raw});t.run("const oldSet=localStorage.setItem;localStorage.setItem=(k,v)=>{if(k===storageKey())throw new Error('blocked');oldSet(k,v)}");await t.nodes.get('recoverSession').onclick();assert.equal(t.storage.get(key),raw);assert.equal(t.run('readIssue'),'stale');assert([...t.storage.values()].includes(raw));
}
console.log('PASS: explicit stale-session recovery retains all ratings and raw backup; no implicit mutation; stale double handler no-op; newer-tab conflicts and backup/current storage failures preserve original, both modes. Non-browser tests.');
})().catch(e=>{console.error(e);process.exit(1)});
