#!/usr/bin/env python3
"""Build the static dictionary site from content/*.json."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


def e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def load_entries(content_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(content_dir.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            entry = json.load(handle)
        if entry.get("word") and entry.get("slug"):
            entries.append(entry)
    return sorted(entries, key=lambda x: x["word"].casefold())


def short_meaning(title: str) -> str:
    if "】" in title:
        return title.split("】", 1)[1]
    return re.sub(r"^\d+[.．]\s*", "", title)


def li(items: list[str], class_name: str = "") -> str:
    cls = f' class="{e(class_name)}"' if class_name else ""
    return f"<ul{cls}>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"


def chips(items: list[str]) -> str:
    return '<div class="chips">' + "".join(f'<span class="chip">{e(x)}</span>' for x in items) + "</div>"


def relation_cards(items: list[dict[str, Any]], title: str) -> str:
    if not items:
        return ""
    cards = []
    for item in items:
        definition = f'<p class="ja"><b>定義</b>{e(item.get("definition"))}</p>' if item.get("definition") else ""
        frequency = f'<p><b>頻度</b>{e(item.get("frequency"))}/10</p>' if isinstance(item.get("frequency"), int) else ""
        cards.append(
            '<article class="relation-card searchable">'
            f'<h4>{e(item.get("word"))}</h4>{definition}{frequency}'
            f'<p class="ja"><b>違い</b>{e(item.get("difference"))}</p>'
            f'<p><b>例</b>{e(item.get("example"))}</p>'
            f'<p class="ja"><b>訳</b>{e(item.get("translation"))}</p>'
            '</article>'
        )
    return (
        '<details class="subdetails">'
        f'<summary>{e(title)}<span class="count">{len(items)}</span></summary>'
        f'<div class="card-grid">{"".join(cards)}</div></details>'
    )


def collocation_cards(items: list[dict[str, Any]]) -> str:
    cards = []
    for item in items:
        cards.append(
            '<article class="collocation searchable">'
            f'<h4>{e(item.get("pattern"))}</h4>'
            f'<p class="ja"><b>用途</b>{e(item.get("use"))}</p>'
            f'<p><b>例</b>{e(item.get("example"))}</p>'
            f'<p class="ja"><b>訳</b>{e(item.get("translation"))}</p>'
            '</article>'
        )
    return "".join(cards)


def overview(entry: dict[str, Any]) -> tuple[str, str]:
    links: list[str] = []
    cards: list[str] = []
    pronunciation = entry.get("pronunciation") or []
    links.append('<a href="#pronunciation">発音</a>')
    cards.append(
        '<section class="overview-card searchable" id="pronunciation"><h2>発音記号</h2>'
        f'<p class="big-ipa">{e(entry.get("ipa"))}</p>{li(pronunciation, "ja")}</section>'
    )
    if entry.get("core"):
        links.append('<a href="#core">コアイメージ</a>')
        core = "".join(
            f'<div class="core-item"><b>{e(x.get("label"))}</b><span class="ja">{e(x.get("description"))}</span></div>'
            for x in entry["core"]
        )
        cards.append(f'<section class="overview-card searchable" id="core"><h2>コアイメージ</h2><div class="core-grid">{core}</div></section>')
    if entry.get("etymology"):
        links.append('<a href="#etymology">語源</a>')
        cards.append(f'<section class="overview-card searchable" id="etymology"><h2>語源</h2>{li(entry["etymology"], "ja")}</section>')
    if entry.get("formation"):
        links.append('<a href="#formation">語形成</a>')
        rows = "".join(
            f'<div class="formation-row"><b>{e(x.get("term"))}</b><span class="ja">{e(x.get("description"))}</span></div>'
            for x in entry["formation"]
        )
        cards.append(f'<section class="overview-card searchable" id="formation"><h2>語形成</h2><div class="formation-list">{rows}</div></section>')
    return "".join(links), "".join(cards)


def sense_html(sense: dict[str, Any]) -> str:
    n = int(sense.get("number", 0))
    freq = int(sense.get("frequency", 0))
    patterns = sense.get("patterns") or []
    collocations = sense.get("collocations") or []
    notes = sense.get("notes") or []
    return f'''<section class="sense-card searchable" id="sense-{n}" data-freq="{freq}">
<div class="sense-top"><div><span class="sense-number">語義 {n}</span><h2>{e(sense.get("title"))}</h2></div><button class="learn-btn" data-sense="{n}" aria-pressed="false">未習得</button></div>
<div class="meta-row"><div class="frequency"><b>頻度 {freq}/10</b><span><i style="width:{freq*10}%"></i></span></div>{chips(sense.get("register") or [])}</div>
<p class="definition ja">{e(sense.get("definition"))}</p>
<details class="subdetails" open><summary>文法パターン<span class="count">{len(patterns)}</span></summary>{li(patterns, "pattern-list")}</details>
<details class="subdetails" open><summary>コロケーションと例文<span class="count">{len(collocations)}</span></summary><div class="card-grid">{collocation_cards(collocations)}</div></details>
<details class="subdetails"><summary>語法・注意<span class="count">{len(notes)}</span></summary>{li(notes, "notes ja")}</details>
{relation_cards(sense.get("synonyms") or [], "類義語")}
{relation_cards(sense.get("antonyms") or [], "反意語")}
</section>'''


def word_page(entry: dict[str, Any]) -> str:
    word = entry["word"]
    senses = entry.get("senses") or []
    overview_links, overview_cards = overview(entry)
    sense_nav = "".join(
        f'<a href="#sense-{int(s.get("number", 0))}" data-target="sense-{int(s.get("number", 0))}"><span>{int(s.get("number", 0))}</span>{e(short_meaning(s.get("title", "")))}</a>'
        for s in senses
    )
    sources = ""
    if entry.get("sources"):
        sources = '<p class="source-links"><b>参照:</b> ' + " / ".join(
            f'<a href="{e(x.get("url"))}" target="_blank" rel="noopener">{e(x.get("name"))}</a>' for x in entry["sources"]
        ) + "</p>"
    notion = f'<p><a href="{e(entry.get("notion_url"))}" target="_blank" rel="noopener">Notion原本</a></p>' if entry.get("notion_url") else ""
    return f'''<!doctype html>
<html lang="ja" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="英単語 {e(word)} の発音・語源・意味・構文・コロケーションを詳しく解説。"><title>{e(word)}｜英和辞典Extra</title><link rel="stylesheet" href="../assets/site.css"></head>
<body data-word="{e(entry.get('slug'))}" data-sense-count="{len(senses)}">
<header class="site-header"><a class="brand" href="../index.html">英和辞典<span>Extra</span></a><nav><a href="../index.html">単語一覧</a><button id="themeToggle" class="icon-btn" aria-label="配色を切り替える">◐</button></nav></header>
<div class="word-toolbar"><div class="search-box"><input id="pageSearch" type="search" placeholder="この単語内を検索"></div><select id="freqFilter"><option value="0">すべての頻度</option><option value="8">8以上</option><option value="6">6以上</option><option value="4">4以上</option></select><button id="jaToggle">日本語を隠す</button><button id="expandAll">すべて開く</button><button id="collapseAll">すべて閉じる</button></div>
<div class="word-layout"><aside class="word-sidebar"><div class="side-word"><h1>{e(word)}</h1><p>{e(entry.get('ipa'))}</p><div class="progress"><i id="progressFill"></i></div><small id="progressText">習得 0 / {len(senses)}</small></div><p class="side-label">概要</p><nav class="side-nav">{overview_links}</nav><p class="side-label">語義</p><nav class="side-nav sense-nav">{sense_nav}</nav></aside>
<main class="word-main"><section class="word-hero"><p class="kicker">ENGLISH–JAPANESE EXTRA</p><h1>{e(word)}</h1><p class="hero-ipa">{e(entry.get('ipa'))}</p><p class="ja">{e(entry.get('lead'))}</p><div class="hero-badges"><span>主要語義 {len(senses)}</span><span>更新 {e(entry.get('updated'))}</span></div></section><div class="overview-grid">{overview_cards}</div><div class="section-title"><div><p>MEANINGS &amp; USAGE</p><h2>意味・構文・用法</h2></div><small>検索・頻度フィルター・習得管理に対応</small></div><div id="senseContainer">{"".join(sense_html(s) for s in senses)}</div><div class="empty-state" id="pageEmpty">該当する語義がありません。</div></main></div>
<footer class="site-footer">{sources}{notion}<p>英和辞典Extra</p></footer><button class="backtop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" aria-label="上へ戻る">↑</button><script src="../assets/site.js"></script></body></html>'''


def catalog(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for entry in entries:
        searchable: list[str] = [entry.get("word", ""), entry.get("ipa", ""), entry.get("lead", "")]
        for sense in entry.get("senses") or []:
            searchable.extend([sense.get("title", ""), sense.get("definition", "")])
            searchable.extend(sense.get("patterns") or [])
        result.append({
            "word": entry["word"], "slug": entry["slug"], "ipa": entry.get("ipa", ""),
            "lead": entry.get("lead", ""), "sense_count": len(entry.get("senses") or []),
            "updated": entry.get("updated", ""), "search": " ".join(searchable),
        })
    return result


def index_page(items: list[dict[str, Any]]) -> str:
    cards = "".join(
        f'''<article class="word-card" data-letter="{e(x['word'][0].upper())}" data-search="{e(x['search'].casefold())}"><a href="words/{e(x['slug'])}.html"><div class="word-card-top"><span>{e(x['word'][0].upper())}</span><small>{x['sense_count']}語義</small></div><h2>{e(x['word'])}</h2><p class="ipa">{e(x['ipa'])}</p><p class="summary">{e(x['lead'])}</p><div class="chips"><span class="chip">更新 {e(x['updated'])}</span></div></a></article>'''
        for x in items
    )
    letters = sorted({x["word"][0].upper() for x in items})
    alpha = '<button class="active" data-letter="all">ALL</button>' + "".join(f'<button data-letter="{e(x)}">{e(x)}</button>' for x in letters)
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    total_senses = sum(x["sense_count"] for x in items)
    return f'''<!doctype html><html lang="ja" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="発音・語源・構文・コロケーションまで学べる詳細英和辞典。"><title>英和辞典Extra</title><link rel="stylesheet" href="assets/site.css"></head><body><header class="site-header"><a class="brand" href="index.html">英和辞典<span>Extra</span></a><nav><a href="#words">単語一覧</a><button id="themeToggle" class="icon-btn" aria-label="配色を切り替える">◐</button></nav></header><main class="home-main"><section class="home-hero"><p class="kicker">ENGLISH–JAPANESE EXTRA</p><h1>意味だけでなく、<br>使える英語を身につける。</h1><p>発音、語源、主要構文、コロケーション、類義語の違いまでを一つのページで学べる英和辞典。</p><div class="home-search"><input id="homeSearch" type="search" placeholder="英単語・日本語・構文から検索"><span>⌕</span></div><div class="suggestions" id="suggestions"></div></section><section class="stats"><div><b>{len(items)}</b><span>収録単語</span></div><div><b>{total_senses}</b><span>収録語義</span></div><div><b>10</b><span>頻度スケール</span></div><div><b>2</b><span>米英発音</span></div></section><section class="dictionary-section" id="words"><div class="section-title"><div><p>DICTIONARY</p><h2>単語一覧</h2></div><small>検索またはアルファベットで絞り込み</small></div><div class="alphabet" id="alphabet">{alpha}</div><div class="word-grid">{cards}</div><div class="empty-state" id="homeEmpty">該当する単語がありません。</div></section><section class="howto"><div><p class="kicker">LEARNING FEATURES</p><h2>読んで終わらない辞書</h2></div><ol><li>日本語を隠して例文を確認</li><li>頻度で重要語義に絞り込み</li><li>習得済みをブラウザに保存</li></ol></section></main><footer class="site-footer"><p>英和辞典Extra</p><p>Notionから自動同期</p></footer><script type="application/json" id="dictionaryData">{data}</script><script src="assets/home.js"></script></body></html>'''


def validate_entry(entry: dict[str, Any], path: Path) -> None:
    required = ["word", "slug", "ipa", "senses"]
    missing = [key for key in required if not entry.get(key)]
    if missing:
        raise ValueError(f"{path}: missing {', '.join(missing)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content-dir", type=Path, default=Path("content"))
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = load_entries(args.content_dir)
    if not entries:
        raise SystemExit(f"No JSON files found in {args.content_dir}")
    for path in args.content_dir.glob("*.json"):
        with path.open(encoding="utf-8") as handle:
            validate_entry(json.load(handle), path)
    output = args.output_dir
    words = output / "words"
    data_dir = output / "data"
    words.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        (words / f"{entry['slug']}.html").write_text(word_page(entry), encoding="utf-8")
    items = catalog(entries)
    (output / "index.html").write_text(index_page(items), encoding="utf-8")
    (data_dir / "search-index.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (data_dir / "search-index.js").write_text("window.EIJITEN_INDEX=" + json.dumps(items, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"Built {len(entries)} words and {sum(len(x.get('senses') or []) for x in entries)} senses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
