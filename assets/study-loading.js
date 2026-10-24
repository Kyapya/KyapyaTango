'use strict';
// Keep the page usable before the comparatively large, local-only decks arrive.
function loadStudyScript(src){return new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=src;script.onload=resolve;script.onerror=()=>reject(new Error(src));document.head.append(script)})}
Promise.all([loadStudyScript('data/study-words.js'),loadStudyScript('data/study-examples.js')]).then(()=>loadStudyScript('assets/study.js')).catch(()=>{document.querySelector('#app').removeAttribute('aria-busy');document.querySelector('#loadingTitle').textContent='教材を読み込めませんでした';document.querySelector('#loadingMessage').textContent='通信状態を確認して、再読み込みしてください。この操作では学習記録を消していません。'});
