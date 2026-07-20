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

  // Sense numbers are already shown in headings, so hide duplicated leading
  // "1." / "2．" markers from hero summaries, definitions and list summaries.
  document.querySelectorAll(
    '.word-hero > p.ja, .sense-card .definition, .word-card .summary'
  ).forEach((element) => {
    const original = element.textContent || '';
    const cleaned = original.replace(/^\s*\d+\s*[.．]\s*/, '');
    if (cleaned !== original) element.textContent = cleaned;
  });

  // Repair legacy generated pages whose summary contains only a sense number.
  const heroLead = document.querySelector('.word-hero > p.ja');
  if (heroLead && /^\s*\d+[.．]?\s*$/.test(heroLead.textContent || '')) {
    const definition = document.querySelector('.sense-card .definition');
    const firstLine = (definition?.textContent || '')
      .split(/\r?\n/)
      .find((line) => line.trim());
    const repaired = firstLine
      ?.replace(/^\s*\d+\s*[.．]\s*/, '')
      .trim();
    if (repaired) heroLead.textContent = repaired;
  }

  // Limit study-mode hiding to the requested learning targets.
  // Keep usage notes, overviews, pronunciation, etymology, core image and central definitions visible.
  document.querySelectorAll('.ja').forEach((element) => {
    const isStudyTarget = Boolean(
      element.closest('#formation, .collocation, .relation-card')
    );
    if (!isStudyTarget) element.classList.remove('ja');
  });

  function installExampleSpeech() {
    if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) return;

    if (!document.getElementById('example-speech-style')) {
      const style = document.createElement('style');
      style.id = 'example-speech-style';
      style.textContent = `
        .speech-button{
          display:inline-grid;place-items:center;vertical-align:middle;
          width:30px;height:30px;margin-left:7px;padding:0;
          border:1px solid var(--line);border-radius:999px;
          background:var(--panel);color:var(--primary);cursor:pointer;
          transition:background .15s ease,color .15s ease,border-color .15s ease,transform .15s ease
        }
        .speech-button:hover{border-color:var(--primary);transform:translateY(-1px)}
        .speech-button:focus-visible{outline:3px solid color-mix(in srgb,var(--primary) 25%,transparent);outline-offset:2px}
        .speech-button.is-speaking{background:var(--primary);border-color:var(--primary);color:white}
        .speech-button svg{width:16px;height:16px;fill:currentColor;pointer-events:none}
        .word-hero h1 .headword-speech-button{
          width:42px;height:42px;margin-left:13px;
          border-color:rgba(255,255,255,.48);background:rgba(255,255,255,.14);color:white
        }
        .word-hero h1 .headword-speech-button:hover{border-color:white;background:rgba(255,255,255,.22)}
        .word-hero h1 .headword-speech-button.is-speaking{border-color:white;background:white;color:var(--primary2)}
        .word-hero h1 .headword-speech-button svg{width:21px;height:21px}
        @media(max-width:720px){
          .speech-button{width:34px;height:34px;margin-left:8px}
          .word-hero h1 .headword-speech-button{width:40px;height:40px;margin-left:10px}
        }
        @media(prefers-reduced-motion:reduce){.speech-button{transition:none}}
      `;
      document.head.append(style);
    }

    const synth = window.speechSynthesis;
    let activeButton = null;
    let englishVoices = [];

    const refreshVoices = () => {
      englishVoices = synth.getVoices().filter((voice) => /^en(?:-|_)/i.test(voice.lang));
    };
    refreshVoices();
    synth.addEventListener?.('voiceschanged', refreshVoices);

    const pickVoice = () => {
      const preferredName = /(Google|Microsoft|Samantha|Natural|Enhanced)/i;
      return englishVoices.find(
        (voice) => /^en-US$/i.test(voice.lang) && preferredName.test(voice.name)
      ) || englishVoices.find((voice) => /^en-US$/i.test(voice.lang)) || englishVoices[0] || null;
    };

    const resetButton = (button) => {
      if (!button) return;
      const defaultLabel = button.dataset.speechLabel || '例文を読み上げる';
      button.classList.remove('is-speaking');
      button.setAttribute('aria-pressed', 'false');
      button.setAttribute('aria-label', defaultLabel);
      button.title = defaultLabel;
    };

    const stopSpeech = () => {
      synth.cancel();
      resetButton(activeButton);
      activeButton = null;
    };

    const createSpeechButton = (defaultLabel) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'speech-button';
      button.dataset.speechLabel = defaultLabel;
      button.setAttribute('aria-label', defaultLabel);
      button.setAttribute('aria-pressed', 'false');
      button.title = defaultLabel;
      button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4zm11.5 3a3.5 3.5 0 0 0-1.5-2.87v5.74A3.5 3.5 0 0 0 15.5 12zm0-7.18v2.06a6 6 0 0 1 0 10.24v2.06a8 8 0 0 0 0-14.36z"/></svg>';
      return button;
    };

    const playSpeech = (button, text) => {
      if (activeButton === button) {
        stopSpeech();
        return;
      }

      stopSpeech();
      const utterance = new SpeechSynthesisUtterance(text);
      const voice = pickVoice();
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      } else {
        utterance.lang = 'en-US';
      }
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 1;

      activeButton = button;
      button.classList.add('is-speaking');
      button.setAttribute('aria-pressed', 'true');
      button.setAttribute('aria-label', '読み上げを停止する');
      button.title = '読み上げを停止する';

      const finish = () => {
        if (activeButton !== button) return;
        resetButton(button);
        activeButton = null;
      };
      utterance.addEventListener('end', finish);
      utterance.addEventListener('error', finish);
      synth.speak(utterance);
    };

    const headwordHeading = document.querySelector('.word-hero h1');
    const headword = (word || headwordHeading?.textContent || '').trim();
    if (headwordHeading && headword && !headwordHeading.querySelector('.headword-speech-button')) {
      const label = `見出し語 ${headword} を読み上げる`;
      const button = createSpeechButton(label);
      button.classList.add('headword-speech-button');
      button.addEventListener('click', () => playSpeech(button, headword));
      headwordHeading.append(button);
    }

    document.querySelectorAll('.collocation p, .relation-card p').forEach((paragraph) => {
      const label = paragraph.firstElementChild;
      if (
        !label ||
        label.tagName !== 'B' ||
        label.textContent.trim() !== '例' ||
        paragraph.querySelector('.speech-button')
      ) return;

      const sentence = [...paragraph.childNodes]
        .filter((node) => node !== label)
        .map((node) => node.textContent || '')
        .join('')
        .trim();
      if (!sentence) return;

      const button = createSpeechButton('例文を読み上げる');
      button.addEventListener('click', () => playSpeech(button, sentence));
      paragraph.append(' ', button);
    });

    window.addEventListener('pagehide', stopSpeech);
  }
  installExampleSpeech();

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

    let touchY = null;
    document.addEventListener('touchstart', (event) => {
      if (!mobileQuery.matches || toolbar.contains(event.target)) {
        touchY = null;
        return;
      }
      touchY = event.touches[0]?.clientY ?? null;
    }, { passive: true });

    document.addEventListener('touchmove', (event) => {
      if (!mobileQuery.matches || touchY === null) return;
      const nextTouchY = event.touches[0]?.clientY;
      if (nextTouchY === undefined) return;

      const fingerDelta = nextTouchY - touchY;
      if (Math.abs(fingerDelta) < 12) return;

      if (fingerDelta < 0) {
        if (toolbar.classList.contains('mobile-tools-open')) setOpen(false);
        if (window.scrollY > 40) toolbar.classList.add('mobile-toolbar-hidden');
      } else {
        toolbar.classList.remove('mobile-toolbar-hidden');
      }
      touchY = nextTouchY;
    }, { passive: true });

    document.addEventListener('touchend', () => {
      touchY = null;
    }, { passive: true });

    let lastScrollY = window.scrollY;
    window.addEventListener('scroll', () => {
      const currentY = window.scrollY;
      if (!mobileQuery.matches) {
        lastScrollY = currentY;
        return;
      }

      // Opening the toolbar changes page layout and may fire a synthetic-looking
      // scroll event. Do not close the toolbar unless a real touch gesture does it.
      if (toolbar.classList.contains('mobile-tools-open')) {
        lastScrollY = currentY;
        return;
      }

      const delta = currentY - lastScrollY;
      if (Math.abs(delta) < 8) return;

      if (delta > 0) {
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
