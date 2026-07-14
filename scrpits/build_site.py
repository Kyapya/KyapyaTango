#!/usr/bin/env python3
from __future__ import annotations

from html import escape
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
WORDS = ROOT / "words"
DATA = ROOT / "data"
ASSETS = ROOT / "assets"


def load_words() -> list[dict]:
    words = []
    for path in sorted(CONTENT.glob("*.json")):
        words.append(json.loads(path.read_text(encoding="utf-8")))
    return sorted(words, key=lambda x: x["word"].lower())


def slug_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def list_html(items: list[str], cls: str = "") -> str:
    if not items:
        return ""
    return f'<ul class="{cls}">' + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{escape(i)}</span>' for i in items)


def relation_cards(items: list[dict]) -> str:
    return "".join(
        f'''<article class="relation-card searchable">
          <h4>{escape(item['word'])}</h4>
          <p class="ja"><b>違い</b>{escape(item['difference'])}</p>
          <p><b>例</b>{escape(item['example'])}</p>
          <p class="ja"><b>訳</b>{escape(item['translation'])}</p>
        </article>'''
        for item in items
    )


def details_block(title: str, body: str, count: int, open_by_default: bool = False) -> str:
    if not body:
        return ""
    op = " open" if open_by_default else ""
    return f'''<details class="subdetails"{op}>
      <summary>{escape(title)}<span class="count">{count}</span></summary>
      {body}
    </details>'''


def sense_html(sense: dict) -> str:
    collocations = "".join(
        f'''<article class="collocation searchable">
          <h4>{escape(item['pattern'])}</h4>
          <p class="ja"><b>用途</b>{escape(item['use'])}</p>
          <p><b>例</b>{escape(item['example'])}</p>
          <p class="ja"><b>訳</b>{escape(item['translation'])}</p>
        </article>'''
        for item in sense.get("collocations", [])
    )
    pattern_body = list_html(sense.get("patterns", []), "pattern-list")
    notes_body = list_html(sense.get("notes", []), "notes ja")
    syns = relation_cards(sense.get("synonyms", []))
    ants = relation_cards(sense.get("antonyms", []))
    freq = int(sense.get("frequency", 0))
    return f'''<section class="sense-card searchable" id="sense-{sense['number']}" data-freq="{freq}">
      <div class="sense-top">
        <div>
          <span class="sense-number">語義 {sense['number']}</span>
          <h2>{escape(sense['title'])}</h2>
        </div>
        <button class="learn-btn" data-sense="{sense['number']}" aria-pressed="false">未習得</button>
      </div>
      <div class="meta-row">
        <div class="frequency"><b>頻度 {freq}/10</b><span><i style="width:{freq*10}%"></i></span></div>
        <div class="chips">{chips(sense.get('register', []))}</div>
      </div>
      <p class="definition ja">{escape(sense['definition'])}</p>
      {details_block('文法パターン', pattern_body, len(sense.get('patterns', [])), True)}
      {details_block('コロケーションと例文', f'<div class="card-grid">{collocations}</div>', len(sense.get('collocations', [])), True)}
      {details_block('語法・注意', notes_body, len(sense.get('notes', [])), False)}
      {details_block('類義語', f'<div class="card-grid">{syns}</div>', len(sense.get('synonyms', [])), False) if syns else ''}
      {details_block('反意語', f'<div class="card-grid">{ants}</div>', len(sense.get('antonyms', [])), False) if ants else ''}
    </section>'''


def overview_panel(title: str, inner: str, ident: str) -> str:
    return f'<section class="overview-card searchable" id="{ident}"><h2>{escape(title)}</h2>{inner}</section>'


def word_page(word: dict, all_words: list[dict]) -> str:
    idx = [w["slug"] for w in all_words].index(word["slug"])
    prev_word = all_words[idx - 1] if idx > 0 else None
    next_word = all_words[idx + 1] if idx + 1 < len(all_words) else None
    senses = "".join(sense_html(s) for s in word["senses"])
    nav = "".join(
        f'<a href="#sense-{s["number"]}" data-target="sense-{s["number"]}"><span>{s["number"]}</span>{escape(re.sub(r"^.*?】", "", s["title"]))}</a>'
        for s in word["senses"]
    )
    formation = "".join(
        f'<div class="formation-row"><b>{escape(x["term"])}</b><span class="ja">{escape(x["description"])}</span></div>'
        for x in word.get("formation", [])
    )
    core = "".join(
        f'<div class="core-item"><b>{escape(x["label"])}</b><span class="ja">{escape(x["description"])}</span></div>'
        for x in word.get("core", [])
    )
    sources = " / ".join(
        f'<a href="{escape(x["url"], quote=True)}" target="_blank" rel="noopener">{escape(x["name"])}</a>'
        for x in word.get("sources", [])
    )
    prev_link = f'<a class="pager-link" href="{prev_word["slug"]}.html">← {escape(prev_word["word"])}</a>' if prev_word else '<span></span>'
    next_link = f'<a class="pager-link" href="{next_word["slug"]}.html">{escape(next_word["word"])} →</a>' if next_word else '<span></span>'
    page = f'''<!doctype html>
<html lang="ja" data-theme="light">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="英単語 {escape(word['word'])} の発音・語源・意味・構文・コロケーションを詳しく解説。">
<title>{escape(word['word'])}｜英和辞典Extra</title>
<link rel="stylesheet" href="../assets/site.css">
</head>
<body data-word="{escape(word['slug'])}" data-sense-count="{len(word['senses'])}">
<header class="site-header">
  <a class="brand" href="../index.html">英和辞典<span>Extra</span></a>
  <nav><a href="../index.html">単語一覧</a><button id="themeToggle" class="icon-btn" aria-label="配色を切り替える">◐</button></nav>
</header>
<div class="word-toolbar">
  <div class="search-box"><input id="pageSearch" type="search" placeholder="この単語内を検索"></div>
  <select id="freqFilter"><option value="0">すべての頻度</option><option value="8">8以上</option><option value="6">6以上</option><option value="4">4以上</option></select>
  <button id="jaToggle">日本語を隠す</button><button id="expandAll">すべて開く</button><button id="collapseAll">すべて閉じる</button>
</div>
<div class="word-layout">
<aside class="word-sidebar">
  <div class="side-word"><h1>{escape(word['word'])}</h1><p>{escape(word['ipa'])}</p><div class="progress"><i id="progressFill"></i></div><small id="progressText">習得 0 / {len(word['senses'])}</small></div>
  <p class="side-label">概要</p>
  <nav class="side-nav"><a href="#pronunciation">発音</a><a href="#etymology">語源</a><a href="#formation">語形成</a><a href="#core">コアイメージ</a></nav>
  <p class="side-label">語義</p><nav class="side-nav sense-nav">{nav}</nav>
</aside>
<main class="word-main">
  <section class="word-hero"><p class="kicker">ENGLISH–JAPANESE EXTRA</p><h1>{escape(word['word'])}</h1><p class="hero-ipa">{escape(word['ipa'])}</p><p class="ja">{escape(word['lead'])}</p><div class="hero-badges"><span>主要語義 {len(word['senses'])}</span><span>更新 {escape(word['updated'])}</span></div></section>
  <div class="overview-grid">
    {overview_panel('発音記号', f'<p class="big-ipa">{escape(word["ipa"])}</p>{list_html(word.get("pronunciation", []), "ja")}', 'pronunciation')}
    {overview_panel('コアイメージ', f'<div class="core-grid">{core}</div>', 'core')}
    {overview_panel('語源', list_html(word.get('etymology', []), 'ja'), 'etymology')}
    {overview_panel('語形成', f'<div class="formation-list">{formation}</div>', 'formation')}
  </div>
  <div class="section-title"><div><p>MEANINGS & USAGE</p><h2>意味・構文・用法</h2></div><small>検索・頻度フィルター・習得管理に対応</small></div>
  <div id="senseContainer">{senses}</div><div id="noResults" class="empty-state">該当する語義・用例がありません。</div>
  <div class="page-pager">{prev_link}{next_link}</div>
  <footer class="source-box"><p><b>参照:</b> {sources}</p><p><a href="{escape(word['notion_url'], quote=True)}" target="_blank" rel="noopener">Notionの原本を開く</a></p></footer>
</main>
</div>
<button class="backtop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" aria-label="上部へ戻る">↑</button>
<script src="../assets/site.js"></script>
</body></html>'''
    return page


def home_page(words: list[dict]) -> str:
    letters = sorted({w["word"][0].upper() for w in words})
    letter_buttons = '<button data-letter="all" class="active">ALL</button>' + ''.join(f'<button data-letter="{l}">{l}</button>' for l in letters)
    cards = []
    for word in words:
        top = word["senses"][0]
        tags = sorted({tag for s in word["senses"] for tag in s.get("register", [])})[:4]
        search_blob = " ".join([
            word["word"], word["lead"], word["ipa"],
            *[s["title"] + " " + s["definition"] + " " + " ".join(s.get("patterns", [])) for s in word["senses"]]
        ])
        cards.append(f'''<article class="word-card" data-letter="{word['word'][0].upper()}" data-search="{escape(search_blob.lower(), quote=True)}">
          <a href="words/{escape(word['slug'])}.html">
            <div class="word-card-top"><span>{escape(word['word'][0].upper())}</span><small>{len(word['senses'])} senses</small></div>
            <h2>{escape(word['word'])}</h2><p class="ipa">{escape(word['ipa'])}</p>
            <p class="ja summary">{escape(top['definition'])}</p>
            <div class="chips">{chips(tags)}</div>
          </a>
        </article>''')
    index_json = json.dumps([{"word":w["word"],"slug":w["slug"],"ipa":w["ipa"],"lead":w["lead"]} for w in words], ensure_ascii=False).replace('</', '<\\/')
    return f'''<!doctype html>
<html lang="ja" data-theme="light">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="発音・語源・構文・コロケーションまで学べる詳細英和辞典。"><title>英和辞典Extra</title><link rel="stylesheet" href="assets/site.css"></head>
<body>
<header class="site-header"><a class="brand" href="index.html">英和辞典<span>Extra</span></a><nav><a href="#words">単語一覧</a><button id="themeToggle" class="icon-btn" aria-label="配色を切り替える">◐</button></nav></header>
<main class="home-main">
<section class="home-hero"><p class="kicker">A DEEP ENGLISH–JAPANESE DICTIONARY</p><h1>意味だけでなく、<br>使い方まで身につく辞典。</h1><p>発音、語源、コアイメージ、主要構文、コロケーション、類義語の違いを一つのページで学べます。</p><div class="home-search"><input id="homeSearch" type="search" placeholder="英単語・日本語訳・構文を検索"><span>⌕</span></div><div id="suggestions" class="suggestions"></div></section>
<section class="stats"><div><b>{len(words)}</b><span>収録単語</span></div><div><b>{sum(len(w['senses']) for w in words)}</b><span>収録語義</span></div><div><b>A–Z</b><span>索引対応</span></div><div><b>100%</b><span>静的サイト</span></div></section>
<section class="dictionary-section" id="words"><div class="section-title"><div><p>DICTIONARY</p><h2>単語一覧</h2></div><small>アルファベット・検索で絞り込み</small></div><div class="alphabet" id="alphabet">{letter_buttons}</div><div class="word-grid" id="wordGrid">{''.join(cards)}</div><div id="homeEmpty" class="empty-state">該当する単語がありません。</div></section>
<section class="howto"><div><p class="kicker">FIRST STAGE COMPLETE</p><h2>新しい単語を追加できる構成</h2></div><ol><li><b>content/</b> に単語JSONを追加</li><li><b>scripts/build_site.py</b> を実行</li><li>トップページ、単語ページ、検索索引を一括更新</li></ol></section>
</main>
<footer class="site-footer"><p>英和辞典Extra</p><p>学習用の詳細英和辞典</p></footer>
<script id="dictionaryData" type="application/json">{index_json}</script><script src="assets/home.js"></script></body></html>'''


def write_search_index(words: list[dict]) -> None:
    DATA.mkdir(exist_ok=True)
    index = []
    for w in words:
        index.append({
            "word": w["word"], "slug": w["slug"], "ipa": w["ipa"], "lead": w["lead"],
            "senses": len(w["senses"]),
            "keywords": [s["title"] for s in w["senses"]]
        })
    (DATA / "search-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def build() -> None:
    words = load_words()
    WORDS.mkdir(exist_ok=True)
    for w in words:
        (WORDS / f"{w['slug']}.html").write_text(word_page(w, words), encoding="utf-8")
    (ROOT / "index.html").write_text(home_page(words), encoding="utf-8")
    (ROOT / "404.html").write_text(home_page(words).replace('<title>英和辞典Extra</title>', '<title>ページが見つかりません｜英和辞典Extra</title>'), encoding="utf-8")
    write_search_index(words)
    print(f"Built {len(words)} words and {sum(len(w['senses']) for w in words)} senses.")


if __name__ == "__main__":
    build()
