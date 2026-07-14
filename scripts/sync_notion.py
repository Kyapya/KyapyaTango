#!/usr/bin/env python3
"""Synchronize dictionary pages from Notion into content/*.json."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from notion_parser import blocks_to_markdown, parse_dictionary_markdown, validate_entry

API_BASE = "https://api.notion.com/v1"
API_VERSION = "2026-03-11"
DEFAULT_DATABASE_ID = "493016e2a89d4cd08295bf0d825cfd60"


class NotionError(RuntimeError):
    pass


@dataclass
class NotionClient:
    token: str
    version: str = API_VERSION
    timeout: int = 30

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.version,
            "Content-Type": "application/json",
            "User-Agent": "eijiten-extra-sync/2.1",
        }

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = None
        for attempt in range(5):
            response = requests.request(
                method,
                f"{API_BASE}{path}",
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 4:
                    time.sleep(
                        min(float(response.headers.get("Retry-After", 2**attempt)), 20)
                    )
                    continue
            return response
        assert response is not None
        return response

    def json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, path, **kwargs)
        if not response.ok:
            try:
                detail = response.json().get("message", response.text)
            except ValueError:
                detail = response.text
            raise NotionError(f"Notion API {response.status_code} for {path}: {detail}")
        return response.json()

    def resolve_data_source(self, database_id: str, configured: str = "") -> str:
        if configured:
            return configured
        sources = self.json("GET", f"/databases/{database_id}").get("data_sources") or []
        if len(sources) == 1:
            return sources[0]["id"]
        if not sources:
            raise NotionError("No data_sources found. Set NOTION_DATA_SOURCE_ID.")
        names = ", ".join(
            f"{source.get('name', '(unnamed)')}={source.get('id')}" for source in sources
        )
        raise NotionError(
            "Multiple data sources found. Set NOTION_DATA_SOURCE_ID to one of: "
            + names
        )

    def query_all_pages(self, data_source_id: str) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self.json(
                "POST", f"/data_sources/{data_source_id}/query", json=payload
            )
            pages.extend(data.get("results", []))
            if not data.get("has_more"):
                return pages
            cursor = data.get("next_cursor")

    def page_markdown(self, page_id: str) -> str:
        response = self.request("GET", f"/pages/{page_id}/markdown")
        if response.ok:
            data = response.json()
            markdown = data.get("markdown") or data.get("content") or ""
            if markdown:
                return markdown
        return blocks_to_markdown(self.block_tree(page_id))

    def block_tree(self, block_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = self.json("GET", f"/blocks/{block_id}/children", params=params)
            for block in data.get("results", []):
                if block.get("has_children"):
                    block["children"] = self.block_tree(block["id"])
                results.append(block)
            if not data.get("has_more"):
                return results
            cursor = data.get("next_cursor")


def property_text(prop: dict[str, Any]) -> str:
    kind = prop.get("type")
    if kind in {"title", "rich_text"}:
        return "".join(item.get("plain_text", "") for item in prop.get(kind, []))
    if kind == "select":
        return (prop.get("select") or {}).get("name", "")
    if kind == "status":
        return (prop.get("status") or {}).get("name", "")
    return ""


def get_word(page: dict[str, Any], property_name: str) -> str:
    properties = page.get("properties", {})
    if property_name in properties:
        return property_text(properties[property_name]).strip()
    for prop in properties.values():
        if prop.get("type") == "title":
            return property_text(prop).strip()
    return ""


def is_dictionary_page(
    page: dict[str, Any], tag_property: str, tag_value: str
) -> bool:
    prop = page.get("properties", {}).get(tag_property)
    if not prop:
        return False
    return tag_value in [item.get("name", "") for item in prop.get("multi_select", [])]


def normalize_cutoff(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return f"{value}T00:00:00Z"
    return value


def is_recent_page(page: dict[str, Any], cutoff: str) -> bool:
    cutoff = normalize_cutoff(cutoff)
    if not cutoff:
        return True
    return page.get("last_edited_time", "") >= cutoff


def newest_per_word(
    pages: list[dict[str, Any]], title_property: str
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for page in pages:
        key = get_word(page, title_property).casefold()
        if not key:
            continue
        if key not in selected or page.get("last_edited_time", "") > selected[key].get(
            "last_edited_time", ""
        ):
            selected[key] = page
    return list(selected.values())


def select_pages(
    pages: list[dict[str, Any]],
    *,
    title_property: str,
    tag_property: str,
    tag_value: str,
    requested: set[str],
    minimum_last_edited_time: str,
) -> tuple[list[dict[str, Any]], int]:
    tagged = [
        page
        for page in pages
        if is_dictionary_page(page, tag_property, tag_value)
    ]

    skipped_legacy = 0
    if requested:
        selected = newest_per_word(tagged, title_property)
        selected = [
            page
            for page in selected
            if get_word(page, title_property).casefold() in requested
        ]
    else:
        recent = [
            page
            for page in tagged
            if is_recent_page(page, minimum_last_edited_time)
        ]
        skipped_legacy = len(tagged) - len(recent)
        selected = newest_per_word(recent, title_property)

    return selected, skipped_legacy


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json_if_changed(path: Path, value: dict[str, Any], dry_run: bool) -> bool:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(rendered, encoding="utf-8")
        temp.replace(path)
    return True


def safe_slug(word: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", word.casefold()).strip("-") or "entry"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("content"))
    parser.add_argument("--word", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--config", type=Path, default=Path("config/notion.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        print("NOTION_TOKEN is required", file=sys.stderr)
        return 2

    config = (
        json.loads(args.config.read_text(encoding="utf-8"))
        if args.config.exists()
        else {}
    )
    database_id = os.environ.get(
        "NOTION_DATABASE_ID", config.get("database_id", DEFAULT_DATABASE_ID)
    )
    data_source_id = os.environ.get(
        "NOTION_DATA_SOURCE_ID", config.get("data_source_id", "")
    )
    title_property = config.get("title_property", "ALL")
    tag_property = config.get("tag_property", "タグ")
    tag_value = config.get("tag_value", "英単語")
    minimum_last_edited_time = config.get("minimum_last_edited_time", "")
    requested = {word.casefold() for word in args.word}

    client = NotionClient(token)
    data_source_id = client.resolve_data_source(database_id, data_source_id)
    all_pages = client.query_all_pages(data_source_id)
    pages, skipped_legacy = select_pages(
        all_pages,
        title_property=title_property,
        tag_property=tag_property,
        tag_value=tag_value,
        requested=requested,
        minimum_last_edited_time=minimum_last_edited_time,
    )

    if skipped_legacy:
        print(
            f"Skipped {skipped_legacy} tagged page(s) edited before "
            f"{normalize_cutoff(minimum_last_edited_time)}"
        )

    changed = 0
    errors: list[str] = []
    for page in sorted(pages, key=lambda item: get_word(item, title_property).casefold()):
        word = get_word(page, title_property)
        if not word:
            continue
        try:
            existing = load_json(args.output / f"{safe_slug(word)}.json")
            entry = parse_dictionary_markdown(
                client.page_markdown(page["id"]),
                word=word,
                page_url=page.get("url", ""),
                updated=page.get("last_edited_time", "")[:10],
                existing=existing,
            )
            validation = validate_entry(entry)
            if validation:
                raise ValueError("; ".join(validation))
            output = args.output / f"{entry['slug']}.json"
            if write_json_if_changed(output, entry, args.dry_run):
                changed += 1
                action = "Would update" if args.dry_run else "Updated"
                print(f"{action} {word} -> {output}")
            else:
                print(f"Unchanged {word}")
        except Exception as exc:
            message = f"{word}: {exc}"
            errors.append(message)
            print(f"ERROR {message}", file=sys.stderr)
            if os.environ.get("GITHUB_ACTIONS") == "true":
                print(f"::warning title=Skipped invalid Notion page::{message}")
            if not args.allow_partial:
                break

    print(
        f"Processed {len(pages)} page(s); changed {changed}; "
        f"errors {len(errors)}; skipped legacy {skipped_legacy}"
    )
    return 1 if errors and not args.allow_partial else 0


if __name__ == "__main__":
    raise SystemExit(main())
