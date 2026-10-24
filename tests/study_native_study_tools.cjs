// Non-browser contract tests. This harness does NOT validate layout or browser interaction.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const KEY='kyapyatango-study:v1';
const source=fs.readFileSync('assets/study.js','utf8');
function create(initial={},failKey=null){
 const storage=new Map(Object.entries(initial)),nodes=new Map(),classes=new Map(),windowEvents={},documentEvents={},intervals=[];let fail=failKey,activeElement=null;
 const staticIds=['app','reset','undo','storage','themeToggle','studyNav','reviewNav','conflict-dialog','conflict-message','loadLatest','reset-dialog','cancel','confirm'];
 class Node{
  constructor(id=''){this.id=id;this.value='';this.hidden=false;this.disabled=false;this.open=false;this.dataset={};this.style={};this.clientHeight=667;this.classList={add(){},remove(){},toggle(){},contains(){return false}};this._html='';this.events={};}
  set innerHTML(v){this._html=v;if(this.id==='app'){for(const k of [...nodes.keys()])if(!staticIds.includes(k))nodes.delete(k);classes.clear()}
   for(const match of v.matchAll(/<([a-z0-9-]+)\b([^>]*)>/gi)){const attrs=match[2],id=attrs.match(/\bid="([^"]+)"/)?.[1];let n=id?(nodes.get(id)||new Node(id)):new Node();if(id)nodes.set(id,n);n.hidden=/\bhidden(?:\s|$)/.test(attrs);n.disabled=/\bdisabled(?:\s|$)/.test(attrs);const rating=attrs.match(/data-rating="([^"]+)"/)?.[1];if(rating){n.dataset.rating=rating;nodes.set('rating-'+rating,n)}for(const cls of (attrs.match(/\bclass="([^"]+)"/)?.[1]||'').split(' '))if(cls)classes.set('.'+cls,n);}
   for(const m of v.matchAll(/<select[^>]*id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)){const options=[...m[2].matchAll(/<option value="([^"]+)"([^>]*)>/g)];nodes.get(m[1]).value=(options.find(o=>o[2].includes('selected'))||options[0])?.[1]||'';}
  }
  get innerHTML(){return this._html}
  querySelector(s){return query(s)}querySelectorAll(s){return s==='[data-rating]'?['again','hard','remembered'].map(r=>nodes.get('rating-'+r)):[]}
  addEventListener(name,f){this.events[name]=f}dispatchEvent(e){return (this['on'+e.type]||this.events[e.type])?.(e)}
  contains(){return false}append(){}prepend(){}before(){}replaceWith(){}remove(){}focus(){this.focused=true;activeElement=this}scrollIntoView(){}setAttribute(k,v){this[k]=v}removeAttribute(k){delete this[k]}getBoundingClientRect(){return {height:60}}showModal(){this.open=true}close(){this.open=false}
 }
 const query=s=>s.startsWith('#')?nodes.get(s.slice(1))||null:classes.get(s)||new Node();
 staticIds.forEach(id=>nodes.set(id,new Node(id)));
 const ctx=vm.createContext({console,Intl,Date,Math,JSON,Number,Object,String,Array,Promise,Set,setInterval:(fn,ms)=>{intervals.push({fn,ms});return intervals.length},Event:class{constructor(type){this.type=type}},document:{hidden:false,get activeElement(){return activeElement},getElementById:id=>nodes.get(id)||null,addEventListener:(name,fn)=>{documentEvents[name]=fn},querySelector:query,createElement:()=>new Node(),body:new Node(),documentElement:{dataset:{}}},window:{addEventListener:(name,fn)=>{windowEvents[name]=fn},removeEventListener:(name)=>{delete windowEvents[name]}},navigator:{},ResizeObserver:class{observe(){}disconnect(){}},localStorage:{getItem:k=>{if(fail===k)throw Error('blocked');return storage.get(k)??null},setItem:(k,v)=>{if(fail===k)throw Error('blocked');storage.set(k,v)},removeItem:k=>storage.delete(k)}});
 vm.runInContext(fs.readFileSync('data/study-words.js','utf8'),ctx);vm.runInContext(fs.readFileSync('data/study-examples.js','utf8'),ctx);vm.runInContext(source,ctx);
 return {ctx,storage,nodes,windowEvents,documentEvents,intervals,run:s=>vm.runInContext(s,ctx),get:s=>JSON.parse(vm.runInContext(`JSON.stringify(${s})`,ctx)),setFail:k=>fail=k};
}
const stringify=JSON.stringify;
const base={records:{abandon:{rating:'again',due:'2020-01-01'},abate:{rating:'hard',due:'2099-01-01'},abide:{rating:'remembered',due:'2020-01-01'}},session:null};
let t=create({[KEY]:stringify(base)});
const published=fs.readdirSync('content').filter(f=>f.endsWith('.json')).map(f=>JSON.parse(fs.readFileSync('content/'+f,'utf8')));
const wordCount=published.length,exampleCount=published.reduce((n,w)=>n+w.senses.reduce((n,s)=>n+s.collocations.length,0),0);
assert.equal(t.run('WORD_CARDS.length'),wordCount);assert.equal(t.run('EXAMPLE_CARDS.length'),exampleCount);
const unchanged=t.storage.get(KEY);
for(const [status,rating,count] of [['due','all',2],['scheduled','all',1],['unseen','all',wordCount-3],['all','again',1],['due','hard',0],['scheduled','hard',1]]){
 assert.equal(t.run(`reviewMatches(deck(),state.records,day(),{status:'${status}',rating:'${rating}'}).length`),count);
}
assert.equal(t.run("reviewMatches(deck(),state.records,day(),{query:' ABANDON '}).length"),1);
assert.equal(t.storage.get(KEY),unchanged,'filtering must not write progress');
assert.equal(t.run("validSize('3')"),3);assert.equal(t.run("validSize('999')"),5);assert.equal(t.run("validSize(null)"),5);
// Execute the actual UI handlers in the non-rendering harness.
t.nodes.get('reviewSearch').value='abandon';t.nodes.get('reviewSearch').oninput();assert.equal(t.nodes.get('studyFiltered').disabled,false);assert.match(t.nodes.get('studyFiltered').textContent,/1枚/);
t.nodes.get('size').value='3';t.nodes.get('size').onchange();assert.equal(t.storage.get(KEY+':session-size'),'3');
(async()=>{
 await t.nodes.get('studyFiltered').onclick();assert.deepEqual(t.get('state.session.queue'),['abandon']);assert.equal(t.storage.get(KEY),stringify({...base,session:t.get('state.session')}));assert.equal(t.run('shown'),false);
 t.nodes.get('reveal').onclick();assert.equal(t.run('shown'),true);
 await t.nodes.get('rating-hard').onclick();assert.equal(t.get('state.records').abandon.rating,'hard');assert.equal(t.run('state.session'),null);
 const saved=t.storage.get(KEY);t.run('home()');assert.equal(t.nodes.get('size').value,'3');assert.equal(t.storage.get(KEY),saved);
 // Clearing the list restores every filter, and typing preserves records.
 t.nodes.get('reviewSearch').value='zzz';t.nodes.get('ratingFilter').value='again';t.nodes.get('reviewSearch').oninput();assert.equal(t.nodes.get('studyFiltered').disabled,true);
 t.nodes.get('clearReview').onclick();assert.equal(t.nodes.get('ratingFilter').value,'all');assert.equal(t.nodes.get('reviewSearch').value,'');assert.equal(t.nodes.get('clearReview').disabled,true);assert.equal(t.storage.get(KEY),saved);
 // Both modes, all sizes: future exclusion, due-first, no duplicates, state unchanged until start.
 for(const mode of ['words','examples'])for(const size of [3,5,10]){
  t=create({[KEY+':mode']:mode});t.run(`state.records={};deck().slice(0,15).forEach((w,i)=>state.records[idOf(w)]={rating:'again',due:i<12?'2020-01-01':'2099-01-01'})`);t.run('save()');const before=t.get('state.records');t.run(`start(${size},false,deck().slice(0,25))`);let q=t.get('state.session.queue');assert.equal(q.length,size);assert.equal(new Set(q).size,size);assert(q.every(id=>before[id]?.due==='2020-01-01'));assert.deepEqual(t.get('state.records'),before);
  const snapshot=t.storage.get(mode==='words'?KEY:KEY+':examples');t.run('home()');assert.equal(t.nodes.get('studyFiltered').disabled,true);t.run(`start(10,false,deck().slice(100,110))`);assert.deepEqual(t.get('state.session.queue'),q);assert.equal(t.storage.get(mode==='words'?KEY:KEY+':examples'),snapshot);
 }
 // Scope can be larger than the first 20 rendered results, and future-only is ineligible.
 t=create();t.run("state.records={};deck().slice(0,30).forEach(w=>state.records[idOf(w)]={rating:'hard',due:'2020-01-01'});save();start(10,true,deck().slice(20,30))");assert(t.get('state.session.queue').every(id=>t.get('WORD_CARDS.slice(20,30).map(idOf)').includes(id)));
 t=create({[KEY]:stringify(base)});const before=t.storage.get(KEY);t.run("start(3,false,deck().filter(w=>w.word==='abate'))");assert.equal(t.run('state.session'),null);assert.equal(t.storage.get(KEY),before);
 // Resume from the other mode preserves both records and exact queue/index.
 const exampleId=t.run('EXAMPLE_CARDS[0].id');const other={records:{[exampleId]:{rating:'hard',due:'2099-01-01'}},session:{queue:[exampleId,exampleId],index:1,repeat:[],ratings:{again:0,hard:1,remembered:0},initial:2}};
 t=create({[KEY]:stringify(base),[KEY+':examples']:stringify(other)});assert.equal(t.run('otherSession().remaining'),1);await t.nodes.get('resumeOther').onclick();assert.equal(t.run('mode'),'examples');assert.deepEqual(t.get('state'),other);assert.equal(t.storage.get(KEY),stringify(base));assert.equal(t.storage.get(KEY+':examples'),stringify(other));
 // A preference-only storage failure remains non-fatal; a newer tab blocks focused start.
 t=create({},KEY+':session-size');t.run('start(3)');assert.equal(t.run('state.session.queue.length'),3);assert.equal(t.run('saveOK'),true);
 t=create();t.storage.set(KEY,stringify(base));t.run('start(3)');assert.equal(t.run('state.session'),null);assert.equal(t.storage.get(KEY),stringify(base));assert.equal(t.nodes.get('conflict-dialog').open,true);
 // Other-mode absent, completed or corrupt state never creates a misleading resume banner.
 for(const other of ['bad JSON',stringify({session:{queue:[],index:0}}),stringify({session:{queue:['x'],index:1}})]){t=create({[KEY+':examples']:other});assert.equal(t.run('otherSession()'),null);assert(!t.nodes.get('resumeOther'));}
 // Existing rating/undo/repeat/finish and reset remain exact in both modes.
 for(const mode of ['words','examples']){
  t=create({[KEY+':mode']:mode});t.run('start(3)');const original=t.get('state.session');const first=original.queue[0];
  t.nodes.get('reveal').onclick();await t.nodes.get('rating-again').onclick();assert.equal(t.run('state.session.queue.length'),4);assert.equal(t.get('state.records')[first].due,t.run('day()'));
  t.run('undoRating()');assert.deepEqual(t.get('state.session'),original);assert.equal(t.run('shown'),true);assert(!t.get('state.records')[first]);
  await t.nodes.get('rating-hard').onclick();assert.equal(t.get('state.records')[first].due,t.run('day(1)'));
  t.run('home()');const paused=t.get('state');const stored=t.storage.get(mode==='words'?KEY:KEY+':examples');t=create(Object.fromEntries(t.storage));assert.deepEqual(t.get('state'),paused);assert.equal(t.run('shown'),false);
  await t.nodes.get('resume').dispatchEvent({type:'click'});t.nodes.get('reveal').onclick();await t.nodes.get('rating-remembered').onclick();
  const last=t.run('state.session.queue[state.session.index]');t.nodes.get('reveal').onclick();await t.nodes.get('rating-again').onclick();t.nodes.get('reveal').onclick();await t.nodes.get('rating-again').onclick();assert.equal(t.run('state.session'),null,'again capped to one repeat');assert.equal(t.get('state.records')[last].rating,'again');
  const completed=t.get('state');t.run('home()');await t.nodes.get('confirm').onclick();assert.deepEqual(t.get('state.records'),{});await t.nodes.get('undo').onclick();assert.deepEqual(t.get('state'),completed);
 }
 console.log('PASS: current published words / examples; 6 filter intersections; focused start; size preference; clear/empty states; 6 mode-size queue cases; due-first/future exclusion; active queue preservation; exact other-mode resume; storage failure/conflict guards. Non-browser tests only.');
})().catch(e=>{console.error(e);process.exit(1)});
