(() => {
  const root = document.documentElement;
  const themeButton = document.getElementById('themeToggle');
  const storedTheme = localStorage.getItem('eijiten-theme');
  if (storedTheme) root.dataset.theme = storedTheme;
  themeButton?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('eijiten-theme', root.dataset.theme);
  });

  const body = document.body;
  const word = body.dataset.word;
  const cards = [...document.querySelectorAll('.sense-card')];
  const search = document.getElementById('pageSearch');
  const freq = document.getElementById('freqFilter');
  const empty = document.getElementById('noResults');
  function filterCards(){
    const q=(search?.value||'').trim().toLowerCase();
    const min=Number(freq?.value||0);let shown=0;
    cards.forEach(card=>{const ok=(!q||card.textContent.toLowerCase().includes(q))&&Number(card.dataset.freq)>=min;card.classList.toggle('hidden',!ok);if(ok)shown++;});
    if(empty) empty.style.display=shown?'none':'block';
  }
  search?.addEventListener('input',filterCards);freq?.addEventListener('change',filterCards);
  document.getElementById('jaToggle')?.addEventListener('click',e=>{const state=body.classList.toggle('hide-ja');e.currentTarget.textContent=state?'日本語を表示':'日本語を隠す';});
  body.addEventListener('click',e=>{if(body.classList.contains('hide-ja')&&e.target.closest('.ja')){const el=e.target.closest('.ja');el.style.filter=el.style.filter?'':'none';}});
  document.getElementById('expandAll')?.addEventListener('click',()=>document.querySelectorAll('details').forEach(d=>d.open=true));
  document.getElementById('collapseAll')?.addEventListener('click',()=>document.querySelectorAll('details').forEach(d=>d.open=false));

  const key=`eijiten-learned-${word}`;
  let learned=new Set(JSON.parse(localStorage.getItem(key)||'[]').map(String));
  function renderLearned(){
    cards.forEach(card=>{const btn=card.querySelector('.learn-btn');const n=btn.dataset.sense;const yes=learned.has(n);card.classList.toggle('learned',yes);btn.textContent=yes?'習得済み':'未習得';btn.setAttribute('aria-pressed',yes);document.querySelector(`.sense-nav a[data-target="sense-${n}"]`)?.classList.toggle('learned',yes);});
    const count=learned.size,total=cards.length;const txt=document.getElementById('progressText');const fill=document.getElementById('progressFill');if(txt)txt.textContent=`習得 ${count} / ${total}`;if(fill)fill.style.width=`${total?count/total*100:0}%`;
  }
  document.querySelectorAll('.learn-btn').forEach(btn=>btn.addEventListener('click',()=>{const n=btn.dataset.sense;learned.has(n)?learned.delete(n):learned.add(n);localStorage.setItem(key,JSON.stringify([...learned]));renderLearned();}));
  renderLearned();

  if('IntersectionObserver' in window){
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){document.querySelectorAll('.sense-nav a').forEach(a=>a.style.fontWeight='');const active=document.querySelector(`.sense-nav a[data-target="${entry.target.id}"]`);if(active)active.style.fontWeight='850';}}),{rootMargin:'-25% 0px -65% 0px'});cards.forEach(c=>observer.observe(c));
  }
})();
