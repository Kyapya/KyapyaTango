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

    def page_markdown(self, page_id: str) -> tuple[str, bool]:
        """Return page text and whether it uses Markdown punctuation escapes."""
        response = self.request("GET", f"/pages/{page_id}/markdown")
        if response.ok:
            data = response.json()
            markdown = data.get("markdown") or data.get("content") or ""
            if markdown:
                return markdown, True
        return blocks_to_markdown(self.block_tree(page_id)), False

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


def is_complete_page(
    page: dict[str, Any], status_property: str, complete_status: str
) -> bool:
    prop = page.get("properties", {}).get(status_property)
    if not prop:
        return False
    return property_text(prop).strip() == complete_status


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
    status_property: str,
    complete_status: str,
    requested: set[str],
    minimum_last_edited_time: str,
) -> tuple[list[dict[str, Any]], int, int]:
    tagged = [
        page
        for page in pages
        if is_dictionary_page(page, tag_property, tag_value)
    ]

    candidates = newest_per_word(tagged, title_property)
    if requested:
        candidates = [
            page
            for page in candidates
            if get_word(page, title_property).casefold() in requested
        ]

    incomplete = [
        page
        for page in candidates
        if not is_complete_page(page, status_property, complete_status)
    ]
    completed = [
        page
        for page in candidates
        if is_complete_page(page, status_property, complete_status)
    ]

    skipped_legacy = 0
    if requested:
        selected = completed
    else:
        recent = [
            page
            for page in completed
            if is_recent_page(page, minimum_last_edited_time)
        ]
        skipped_legacy = len(completed) - len(recent)
        selected = recent

    return selected, skipped_legacy, len(incomplete)


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
    # Kept as an explicit failure, not a second writer or a silent legacy path.
    print("Notion-to-site writes are disabled. Use scripts/sync_source.py.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
