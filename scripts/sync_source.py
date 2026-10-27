#!/usr/bin/env python3
"""Import checked articles from one immutable english-dictionary checkout.

No network requests, Notion credentials, deletions, or execution of source code.
All candidates are validated in memory before any output is changed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from notion_parser import blocks_to_markdown, parse_dictionary_markdown, validate_entry
from normalize_content import normalize_entry
from source_markdown import _split_front_matter, markdown_to_blocks
from source_entry_validation import validate_text
from verify_source_ci import verify_source_ci

SOURCE_REPOSITORY = "Kyapya/english-dictionary"
STATE_PATH = Path("data/source-sync.json")
SHA_RE = re.compile(r"[0-9a-f]{40}")


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def checked(values: dict[str, str]) -> bool:
    return values.get("status", "").strip() in {"checked", "final"} and values.get("checked", "").strip().lower() == "true"


def source_to_entry(body: str, word: str, existing: dict[str, Any]) -> dict[str, Any]:
    blocks = markdown_to_blocks(body)
    # Match Notion's response shape, without sending or receiving a Notion call.
    for block in blocks:
        for item in block[block["type"]].get("rich_text", []):
            item["plain_text"] = item["text"]["content"]
    parsed = parse_dictionary_markdown(
        blocks_to_markdown(blocks), word=word, existing=existing,
        page_url=existing.get("notion_url", ""), updated=existing.get("updated", ""),
        decode_literal_escapes=False,
    )
    normalize_entry(parsed)
    # Retain auxiliary metadata unknown to the parser, including legacy sources.
    entry = {**existing, **parsed}
    errors = validate_entry(entry)
    if errors:
        raise ValueError(f"{word}: {'; '.join(errors)}")
    return entry


def safe_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'entries' or path.suffix != '.md':
        raise ValueError(f"Unsafe article path: {relative!r}")
    target = root / path
    if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Article escapes source checkout: {relative!r}")
    return target


def plan_sync(source: Path, output: Path, previous: dict[str, Any], revision: str,
              *, word: str = '', date_for_path=None) -> tuple[dict[Path, dict[str, Any]], dict[str, Any]]:
    if not SHA_RE.fullmatch(revision):
        raise ValueError('Source revision must be an immutable full commit SHA')
    if previous and previous.get('repository') != SOURCE_REPOSITORY:
        raise ValueError('Unexpected source repository in existing sync state')
    queue = source / 'queue/words.csv'
    if queue.is_symlink() or not queue.resolve().is_relative_to(source.resolve()):
        raise ValueError('Unsafe source queue path')
    with queue.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('Empty source queue; preserving last-known-good site')
    existing_by_word = {}
    for path in sorted(output.glob('*.json')):
        entry = json.loads(path.read_text(encoding='utf-8'))
        key = entry['word'].casefold()
        if key in existing_by_word or path.stem != entry['slug']:
            raise ValueError(f'Duplicate word or noncanonical existing path: {path}')
        existing_by_word[key] = (path, entry)
    changes = {}; entries = dict(previous.get('entries', {})); seen = set(); slugs = {p.stem: k for k,(p,_) in existing_by_word.items()}
    skipped = []
    for row in rows:
        headword = row.get('headword', '').strip(); key = headword.casefold()
        if not key or key in seen:
            raise ValueError(f'Missing or duplicate source headword: {headword!r}')
        seen.add(key)
        if word and key != word.casefold():
            continue
        path = safe_path(source, row.get('file', ''))
        if not path.is_file():
            skipped.append({'word': headword, 'reason': 'missing source; retained'})
            continue
        raw = path.read_text(encoding='utf-8'); meta, body = _split_front_matter(raw)
        if meta.get('headword') != headword:
            raise ValueError(f'Queue/front matter headword mismatch: {path}')
        if not checked(row) or not checked(meta):
            skipped.append({'word': headword, 'reason': 'not checked; retained'})
            continue
        errors = validate_text(raw)
        if errors:
            raise ValueError(f'{headword}: source validation failed: {"; ".join(errors)}')
        old_path, existing = existing_by_word.get(key, (None, {}))
        entry = source_to_entry(body, headword, existing)
        slug = entry['slug']
        if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', slug) or (slug in slugs and slugs[slug] != key):
            raise ValueError(f'Unsafe or colliding slug: {slug}')
        slugs[slug] = key
        if entry != existing:
            updated = date_for_path(row['file']) if date_for_path else meta.get('updated_at', '')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', updated):
                raise ValueError(f'{headword}: missing source change date')
            entry['updated'] = updated
            changes[old_path or output / f'{slug}.json'] = entry
        entries[key] = {'path': row['file'], 'sha256': hashlib.sha256(raw.encode()).hexdigest()}
    if word and word.casefold() not in seen:
        raise ValueError(f'Requested word is absent from source queue: {word}')
    for key in sorted(set(existing_by_word) - seen):
        skipped.append({'word': existing_by_word[key][1]['word'], 'reason': 'absent from queue; retained'})
    state = {'version': 1, 'repository': SOURCE_REPOSITORY, 'revision': revision, 'entries': entries, 'retained': skipped}
    return changes, state


def write_json(path: Path, value: dict[str, Any]) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') == rendered:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(rendered, encoding='utf-8'); temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('content'))
    parser.add_argument('--state', type=Path, default=STATE_PATH)
    parser.add_argument('--word', default='')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--require-ci', action='store_true', help='Require exact source main ordinary CI success (public read)')
    args = parser.parse_args()
    revision = git(args.source, 'rev-parse', 'HEAD')
    if git(args.source, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Source checkout is dirty; immutable input required')
    previous = json.loads(args.state.read_text()) if args.state.exists() else {}
    prior = previous.get('revision')
    if prior:
        if not SHA_RE.fullmatch(prior):
            raise ValueError('Invalid previous source revision')
        if subprocess.run(['git','-C',str(args.source),'merge-base','--is-ancestor',prior,revision]).returncode:
            raise ValueError('Source rollback or unrelated history rejected')
    if args.require_ci:
        verify_source_ci(revision)
    changes, state = plan_sync(args.source, args.output, previous, revision, word=args.word,
        date_for_path=lambda path: git(args.source, 'log', '-1', '--format=%cI', revision, '--', path)[:10])
    print(json.dumps({'revision': revision, 'changed': len(changes), 'retained': state['retained'], 'dry_run': args.dry_run}, ensure_ascii=False))
    if not args.dry_run:
        for path, entry in changes.items(): write_json(path, entry)
        write_json(args.state, state)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
