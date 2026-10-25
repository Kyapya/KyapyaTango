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
const FREQ=KEY+':minimum-frequency',stringify=JSON.stringify;
const published=fs.readdirSync('content').filter(f=>f.endsWith('.json')).map(f=>JSON.parse(fs.readFileSync('content/'+f,'utf8')));
const sourceFrequency=new Map(published.flatMap(w=>w.senses.map(s=>[`${w.slug}:${s.number}`,s.frequency])));
let t=create();
for(let n=1;n<=10;n++){assert.equal(t.run(`validFrequency(${n})`),n);assert.equal(t.run(`validFrequency('${n}')`),n)}
for(const expr of ['undefined','null','true','false','0','11','-1','1.5','NaN','Infinity',"''","'06'","'6.0'","' 6 '","'6x'",'[]','{}'])assert.equal(t.run(`validFrequency(${expr})`),0,expr);
// Derived cards use their displayed meaning, never another meaning's maximum.
for(const w of published){const c=t.get(`WORD_CARDS.find(w=>w.word===${stringify(w.word)})`);assert.equal(c.frequency,w.senses[0].frequency,w.word)}
for(const e of t.get('EXAMPLE_CARDS'))assert.equal(e.frequency,sourceFrequency.get(e.senseId),e.id);
const base={records:{abandon:{rating:'again',due:'2020-01-01'},abate:{rating:'hard',due:'2099-01-01'}},session:null};
(async()=>{
 for(const mode of ['words','examples'])for(const n of [1,6,10]){
  t=create({[KEY+':mode']:mode,[FREQ]:String(n)});
  const all=t.get('deck()'),expected=all.filter(w=>Number.isInteger(w.frequency)&&w.frequency>=n&&w.frequency<=10);
  assert.deepEqual(t.get('studyDeck().map(idOf)'),expected.map(w=>w.id||w.word));
  assert.equal(t.nodes.get('minimumFrequency').value,String(n));
  t.run('start(10)');assert(t.get('state.session.queue').every(id=>expected.some(w=>(w.id||w.word)===id)));assert.equal(t.run('state.session.minFrequency'),n);
  const queue=t.get('state.session.queue');t.run('home()');assert.equal(t.nodes.get('minimumFrequency').disabled,true);
  // Changing the preference in another tab cannot replace an in-progress queue.
  t.storage.set(FREQ,'1');t.windowEvents.storage({key:FREQ,newValue:'1'});assert.deepEqual(t.get('state.session.queue'),queue);assert.equal(t.run('state.session.minFrequency'),n);
  t=create(Object.fromEntries(t.storage));assert.deepEqual(t.get('state.session.queue'),queue);assert.equal(t.nodes.get('minimumFrequency').value,String(n));
  await t.nodes.get('resume').dispatchEvent({type:'click'});t.nodes.get('reveal').onclick();await t.nodes.get('rating-again').onclick();assert.equal(t.get('state.session.queue').at(-1),queue[0]);t.run('undoRating()');assert.deepEqual(t.get('state.session.queue'),queue);
 }
 // Missing/invalid card frequencies are included only when no minimum is selected.
 t=create();t.run("WORD_CARDS[0].frequency=null;WORD_CARDS[1].frequency=99;WORD_CARDS[2].frequency='garbage'");
 assert.equal(t.run('studyDeck().length'),t.run('deck().length'));
 t.storage.set(FREQ,'1');t.run('home()');assert(!t.get('studyDeck().map(idOf)').some(id=>t.get('WORD_CARDS.slice(0,3).map(idOf)').includes(id)));
 // Every threshold includes its exact boundary, with canonical string values normalized.
 for(let n=1;n<=10;n++){
  t=create({[FREQ]:String(n)});t.run(`WORD_CARDS[0].frequency=${n};WORD_CARDS[1].frequency='${n}';WORD_CARDS[2].frequency=${n-1}`);
  assert(t.run('studyDeck().includes(WORD_CARDS[0])'));assert(t.run('studyDeck().includes(WORD_CARDS[1])'));assert(!t.run('studyDeck().includes(WORD_CARDS[2])'));
 }
 // Selecting a threshold never writes/reset learning records or their stable IDs.
 t=create({[KEY]:stringify(base)});const before=t.storage.get(KEY);
 t.nodes.get('minimumFrequency').value='6';await t.nodes.get('minimumFrequency').onchange({target:t.nodes.get('minimumFrequency')});assert.equal(t.storage.get(FREQ),'6');assert.equal(t.storage.get(KEY),before);assert.deepEqual(t.get('state.records'),base.records);
 t=create(Object.fromEntries(t.storage));assert.equal(t.nodes.get('minimumFrequency').value,'6');assert.equal(t.storage.get(KEY),before);
 for(const bad of ['garbage','11','-1','06','null','1.5']){t=create({[FREQ]:bad,[KEY]:before});assert.equal(t.run('preferredFrequency()'),0);assert.equal(t.nodes.get('minimumFrequency').value,'0');assert.equal(t.storage.get(KEY),before)}
 // All eligible entry points apply the threshold, including explicitly supplied candidates.
 for(const mode of ['words','examples'])for(const route of ['normal','due','filtered']){
  t=create({[KEY+':mode']:mode,[FREQ]:'6'});
  t.run("state.records={};deck().forEach((w,i)=>{if(i%3===0)state.records[idOf(w)]={rating:'again',due:'2020-01-01'};else if(i%3===1)state.records[idOf(w)]={rating:'hard',due:'2099-01-01'}});save();home()");const records=t.get('state.records');
  const expected=t.get("studyDeck().filter(w=>state.records[idOf(w)]&&state.records[idOf(w)].due<=day()).map(idOf)");assert.deepEqual(t.get('due().map(idOf)'),expected);
  if(route==='normal')t.run('start(10,false,deck())');else if(route==='due')await t.nodes.get('review').onclick();else await t.nodes.get('studyFiltered').onclick();
  assert(t.get('state.session.queue').every(id=>expected.includes(id)),`${mode}/${route}: due-first and threshold`);assert.deepEqual(t.get('state.records'),records);
 }
 // Zero eligible results disables start; an attempted start leaves records untouched.
 t=create({[FREQ]:'10',[KEY]:before});t.run('WORD_CARDS.forEach(w=>w.frequency=1);home()');assert.equal(t.nodes.get('start').disabled,true);assert.equal(t.nodes.get('studyFiltered').disabled,true);assert.equal(t.nodes.get('review').disabled,true);t.run('start(5)');assert.equal(t.run('state.session'),null);assert.equal(t.storage.get(KEY),before);
 // Legacy interrupted sessions have no filter; new preferences cannot delete their cards.
 t=create();const id=t.run('WORD_CARDS[0].id');const legacy={...base,session:{queue:[id],index:0,repeat:[],ratings:{again:0,hard:0,remembered:0},initial:1}};
 t=create({[KEY]:stringify(legacy),[FREQ]:'10'});assert.equal(t.run('readIssue'),null);assert.deepEqual(t.get('state'),legacy);assert.equal(t.nodes.get('minimumFrequency').value,'0');assert.equal(t.nodes.get('minimumFrequency').disabled,true);await t.nodes.get('resume').dispatchEvent({type:'click'});assert.equal(t.run('state.session.queue[0]'),id);
 // Shared preference survives mode switches but each mode's record storage remains unchanged.
 t=create({[KEY]:before,[FREQ]:'6'});t.run("changeMode('examples')");assert.equal(t.nodes.get('minimumFrequency').value,'6');assert.equal(t.storage.get(KEY),before);t.run("changeMode('words')");assert.deepEqual(t.get('state.records'),base.records);
 // An idle tab observes a preference event without touching learning history.
 t=create({[KEY]:before});t.storage.set(FREQ,'10');t.windowEvents.storage({key:FREQ,newValue:'10'});assert.equal(t.nodes.get('minimumFrequency').value,'10');assert.equal(t.storage.get(KEY),before);
 // Preference write failure is reported and does not affect the progress document.
 t=create({[KEY]:before});t.setFail(FREQ);t.nodes.get('minimumFrequency').value='6';await t.nodes.get('minimumFrequency').onchange({target:t.nodes.get('minimumFrequency')});assert.equal(t.storage.get(KEY),before);assert.match(t.nodes.get('storage').textContent,/保存できません/);assert.equal(t.nodes.get('minimumFrequency').value,'0');
 // Preferences are non-critical: failure to access the preference cannot reset history.
 t=create({[KEY]:before},FREQ);assert.equal(t.run('preferredFrequency()'),0);assert.equal(t.storage.get(KEY),before);
 console.log('PASS frequency: original displayed-sense mapping; 1..10 inclusive; invalid values; all selection paths; records/IDs preserved; saved/legacy preferences; frozen/repeated/undo/resumed sessions; mode changes; zero results; multiple tabs. Non-browser contract tests only.');
})().catch(e=>{console.error(e);process.exit(1)});
