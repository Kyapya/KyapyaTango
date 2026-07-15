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
  const toolbar = document.querySelector('.word-toolbar');
  const jaToggle = document.getElementById('jaToggle');

  // Limit study-mode hiding to the requested learning targets.
  // Keep usage notes, overviews, pronunciation, etymology, core image and central definitions visible.
  document.querySelectorAll('.ja').forEach((element) => {
    const isStudyTarget = Boolean(
      element.closest('#formation, .collocation, .relation-card')
    );
    if (!isStudyTarget) element.classList.remove('ja');
  });

  function installMobileToolbar() {
    if (!toolbar || toolbar.querySelector('#mobileToolsToggle')) return;

    const mobileQuery = window.matchMedia('(max-width: 720px)');
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.id = 'mobileToolsToggle';
    toggle.className = 'mobile-toolbar-toggle';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-controls', 'pageSearch freqFilter jaToggle expandAll collapseAll');
    toggle.innerHTML = '<span>学習ツール</span><span class="mobile-toolbar-chevron" aria-hidden="true">⌄</span>';
    toolbar.prepend(toggle);
    toolbar.classList.add('mobile-tools-ready');

    const setOpen = (open, focusSearch = false) => {
      toolbar.classList.toggle('mobile-tools-open', open);
      toolbar.classList.remove('mobile-toolbar-hidden');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.querySelector('.mobile-toolbar-chevron').textContent = open ? '⌃' : '⌄';
      if (open && focusSearch) window.setTimeout(() => search?.focus(), 80);
    };

    toggle.addEventListener('click', () => {
      setOpen(!toolbar.classList.contains('mobile-tools-open'));
    });

    document.addEventListener('click', (event) => {
      if (
        mobileQuery.matches &&
        toolbar.classList.contains('mobile-tools-open') &&
        !toolbar.contains(event.target)
      ) {
        setOpen(false);
      }
    });

    let lastScrollY = window.scrollY;
    window.addEventListener('scroll', () => {
      const currentY = window.scrollY;
      if (!mobileQuery.matches) {
        lastScrollY = currentY;
        return;
      }

      const delta = currentY - lastScrollY;
      if (Math.abs(delta) < 8) return;

      if (delta > 0) {
        if (toolbar.classList.contains('mobile-tools-open')) setOpen(false);
        if (currentY > 80) toolbar.classList.add('mobile-toolbar-hidden');
      } else {
        toolbar.classList.remove('mobile-toolbar-hidden');
      }
      lastScrollY = currentY;
    }, { passive: true });

    mobileQuery.addEventListener?.('change', (event) => {
      setOpen(false);
      if (!event.matches) toolbar.classList.remove('mobile-toolbar-hidden');
    });
  }
  installMobileToolbar();

  function filterCards(){
    const q=(search?.value||'').trim().toLowerCase();
    const min=Number(freq?.value||0);let shown=0;
    cards.forEach(card=>{const ok=(!q||card.textContent.toLowerCase().includes(q))&&Number(card.dataset.freq)>=min;card.classList.toggle('hidden',!ok);if(ok)shown++;});
    if(empty) empty.style.display=shown?'none':'block';
  }
  search?.addEventListener('input',filterCards);freq?.addEventListener('change',filterCards);

  jaToggle?.addEventListener('click', (event) => {
    const state = body.classList.toggle('hide-ja');
    document.querySelectorAll('.ja-revealed').forEach((element) => {
      element.classList.remove('ja-revealed');
    });
    event.currentTarget.textContent = state ? '日本語を表示' : '日本語を隠す';
  });

  body.addEventListener('click', (event) => {
    if (!body.classList.contains('hide-ja')) return;
    const element = event.target.closest('.ja');
    if (!element) return;
    element.classList.toggle('ja-revealed');
  });

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