#!/usr/bin/env python3
"""Parse an 英和辞典Extra Notion page into the site's JSON schema."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
SENSE_RE = re.compile(r"^(?:(\d+)\s*[.．]\s*)?(.+)$")
FREQ_RE = re.compile(r"(?:〈|<)?\s*(\d{1,2})\s*/\s*10\s*(?:〉|>)?")
LINK_RE = re.compile(r"\[([^\]]+)\]\((?:https?://|notion://)[^)]+\)")
PAREN_LINK_RE = re.compile(
    r"\s*[（(]\s*\[([^\]]+)\]\(((?:https?://|notion://)[^)]+)\)\s*[）)]"
)
DOMAIN_LABEL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}"
    r"(?::\d+)?(?:/[^\s]*)?$",
    re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
LABEL_RE = re.compile(r"^([^:：]+)\s*[:：]\s*(.*)$")

SECTION_ALIASES = {
    "発音記号": "pronunciation",
    "語源": "etymology",
    "語形成": "formation",
    "コアイメージ": "core",
    "意味や関連情報の出力（日本語訳）": "meanings",
    "意味や関連情報の出力": "meanings",
}
SUBSECTION_ALIASES = {
    "日本語訳・定義": "definition",
    "頻度": "frequency",
    "レジスター/領域": "register",
    "レジスター／領域": "register",
    "文法パターン": "patterns",
    "コロケーション": "collocations",
    "語法・注意": "notes",
    "類義語": "synonyms",
    "反意語": "antonyms",
}


@dataclass
class Section:
    level: int
    title: str
    lines: list[str] = field(default_factory=list)


def _remove_parenthesized_domain_link(match: re.Match[str]) -> str:
    """Remove source citations such as ([dictionary.cambridge.org](https://...))."""
    label = html.unescape(match.group(1)).strip()
    if DOMAIN_LABEL_RE.fullmatch(label):
        return ""
    return match.group(0)


def _clean_inline(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    text = PAREN_LINK_RE.sub(_remove_parenthesized_domain_link, text)
    text = LINK_RE.sub(r"\1", text).replace("**", "").replace("__", "")
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return HTML_TAG_RE.sub("", text).strip()


def _normalize_heading(text: str) -> str:
    return _clean_inline(text).strip().strip("【】[] ")


def _strip_bullet(text: str) -> str:
    return re.sub(r"^\s*(?:[-*+・●▪︎◦]|\d+[.．])\s*", "", text).strip()


def _paragraphs(lines: Iterable[str]) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    for raw in lines:
        for line in (_clean_inline(raw).splitlines() or [raw]):
            if not line.strip():
                if current:
                    out.append("\n".join(current).strip())
                    current = []
            else:
                current.append(line.rstrip())
    if current:
        out.append("\n".join(current).strip())
    return [item for item in out if item]


def split_sections(markdown: str) -> list[Section]:
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    markdown = re.sub(
        r"^([＃]+)",
        lambda match: "#" * len(match.group(1)),
        markdown,
        flags=re.MULTILINE,
    )
    sections = [Section(0, "")]
    current = sections[0]
    for raw in markdown.split("\n"):
        match = HEADING_RE.match(raw)
        if match:
            current = Section(len(match.group(1)), _normalize_heading(match.group(2)))
            sections.append(current)
        else:
            current.lines.append(raw)
    return sections


def _section_key(title: str, mapping: dict[str, str]) -> str | None:
    normalized = _normalize_heading(title)
    for label, key in mapping.items():
        if normalized == label or normalized.startswith(label):
            return key
    return None


def _simple_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for paragraph in _paragraphs(lines):
        for line in paragraph.splitlines():
            line = _strip_bullet(line)
            if line:
                items.append(line)
    return items


def _parse_formation(lines: list[str]) -> list[dict[str, str]]:
    result = []
    for item in _simple_items(lines):
        match = re.match(
            r"^([^\s:：]+(?:\s+office|\s+hall|\s+kit|\s+tin)?)\s+(.*)$",
            item,
        )
        if match:
            term, description = match.group(1), match.group(2)
        else:
            parts = re.split(r"[:：]", item, maxsplit=1)
            term, description = (parts + [""])[:2]
        result.append({"term": term.strip(), "description": description.strip()})
    return result


def _parse_core(lines: list[str]) -> list[dict[str, str]]:
    result = []
    for item in _simple_items(lines):
        match = LABEL_RE.match(item)
        if match:
            label, description = match.group(1), match.group(2)
        else:
            words = item.split(maxsplit=1)
            label = words[0]
            description = words[1] if len(words) > 1 else ""
        result.append({"label": label.strip(), "description": description.strip()})
    return result


def _entry_chunks(lines: list[str]) -> list[list[str]]:
    flattened = []
    for paragraph in _paragraphs(lines):
        flattened.extend(
            item.strip() for item in paragraph.splitlines() if item.strip()
        )
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in flattened:
        if re.match(r"^[・●*-]\s*", line) and current:
            chunks.append(current)
            current = []
        current.append(line)
    if current:
        chunks.append(current)
    return chunks


def _parse_entries(
    lines: list[str], relation: bool = False
) -> list[dict[str, Any]]:
    entries = []
    for chunk in _entry_chunks(lines):
        data: dict[str, Any] = {
            "word" if relation else "pattern": _strip_bullet(chunk[0])
        }
        for raw in chunk[1:]:
            match = LABEL_RE.match(_strip_bullet(raw))
            if not match:
                continue
            label, value = match.group(1).strip(), match.group(2).strip()
            key = {
                "用途": "use",
                "例": "example",
                "訳": "translation",
                "定義": "definition",
                "頻度": "frequency",
                "違い": "difference",
            }.get(label)
            if not key:
                continue
            if key == "frequency":
                frequency_match = FREQ_RE.search(value)
                data[key] = (
                    int(frequency_match.group(1)) if frequency_match else value
                )
            else:
                data[key] = value
        if relation:
            data.setdefault("definition", "")
            data.setdefault("difference", "")
        else:
            data.setdefault("use", "")
        data.setdefault("example", "")
        data.setdefault("translation", "")
        entries.append(data)
    return entries


def _split_patterns(lines: list[str]) -> list[str]:
    items = _simple_items(lines)
    if len(items) == 1 and "／" in items[0]:
        return [item.strip() for item in items[0].split("／") if item.strip()]
    return items


def _split_register(text: str) -> list[str]:
    return [value for value in re.split(r"\s*(?:／|/|\|)\s*", text) if value]


def parse_dictionary_markdown(
    markdown: str,
    *,
    word: str,
    page_url: str = "",
    updated: str = "",
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = existing or {}
    sections = split_sections(markdown)
    top: dict[str, list[str]] = {}
    senses_raw: list[tuple[Section, list[Section]]] = []
    current_sense: tuple[Section, list[Section]] | None = None

    for section in sections:
        if section.level == 1:
            key = _section_key(section.title, SECTION_ALIASES)
            if key:
                top[key] = section.lines
            current_sense = None
        elif section.level == 2:
            current_sense = (section, [])
            senses_raw.append(current_sense)
        elif section.level == 3 and current_sense is not None:
            current_sense[1].append(section)

    pronunciation_items = _simple_items(top.get("pronunciation", []))
    ipa = existing.get("ipa", "")
    if pronunciation_items and re.search(r"/[^/]+/", pronunciation_items[0]):
        ipa = pronunciation_items.pop(0)

    senses = []
    for index, (sense_section, subsections) in enumerate(senses_raw, 1):
        match = SENSE_RE.match(_clean_inline(sense_section.title))
        number = int(match.group(1)) if match and match.group(1) else index
        title = match.group(2).strip() if match else sense_section.title
        payload: dict[str, list[str]] = {}
        for subsection in subsections:
            key = _section_key(subsection.title, SUBSECTION_ALIASES)
            if key:
                payload[key] = subsection.lines

        definition = "\n".join(
            _paragraphs(payload.get("definition", []))
        ).strip()
        frequency_match = FREQ_RE.search(
            " ".join(_simple_items(payload.get("frequency", [])))
        )
        senses.append(
            {
                "number": number,
                "title": title,
                "frequency": int(frequency_match.group(1))
                if frequency_match
                else 0,
                "register": _split_register(
                    " ".join(_simple_items(payload.get("register", [])))
                ),
                "definition": definition,
                "patterns": _split_patterns(payload.get("patterns", [])),
                "collocations": _parse_entries(
                    payload.get("collocations", [])
                ),
                "notes": _simple_items(payload.get("notes", [])),
                "synonyms": _parse_entries(
                    payload.get("synonyms", []), True
                ),
                "antonyms": _parse_entries(
                    payload.get("antonyms", []), True
                ),
            }
        )

    lead = existing.get("lead", "") or (
        re.split(r"(?<=[。.!?])\s*", senses[0]["definition"])[0][:180]
        if senses
        else ""
    )
    return {
        "word": word.strip(),
        "slug": existing.get("slug") or slugify(word),
        "ipa": ipa,
        "lead": lead,
        "updated": updated,
        "notion_url": page_url,
        "pronunciation": pronunciation_items,
        "etymology": _simple_items(top.get("etymology", [])),
        "formation": _parse_formation(top.get("formation", [])),
        "core": _parse_core(top.get("core", [])),
        "sources": existing.get("sources", []),
        "senses": sorted(senses, key=lambda item: item["number"]),
    }


def slugify(word: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", word.strip().lower()).strip("-")
    if not slug:
        raise ValueError(f"Cannot generate URL slug from title: {word!r}")
    return slug


def validate_entry(entry: dict[str, Any]) -> list[str]:
    errors = []
    if not entry.get("word"):
        errors.append("word is empty")
    if not entry.get("slug"):
        errors.append("slug is empty")
    if not entry.get("ipa"):
        errors.append("pronunciation/IPA could not be parsed")
    senses = entry.get("senses") or []
    if not senses:
        errors.append("no sense headings were found")
    for sense in senses:
        prefix = f"sense {sense.get('number', '?')}"
        if not sense.get("definition"):
            errors.append(f"{prefix}: definition is empty")
        if (
            not isinstance(sense.get("frequency"), int)
            or not 1 <= sense["frequency"] <= 10
        ):
            errors.append(f"{prefix}: frequency must be 1-10")
        if not sense.get("patterns"):
            errors.append(f"{prefix}: grammar patterns are empty")
        if not sense.get("collocations"):
            errors.append(f"{prefix}: collocations are empty")
    return errors


def rich_text_plain(rich_text: list[dict[str, Any]]) -> str:
    return "".join(str(item.get("plain_text", "")) for item in rich_text)


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    lines = []
    for block in blocks:
        kind = block.get("type", "")
        payload = block.get(kind, {}) if kind else {}
        text = rich_text_plain(payload.get("rich_text", []))
        if kind.startswith("heading_"):
            lines.append(f"{'#' * int(kind.rsplit('_', 1)[-1])} {text}")
        elif kind in {"bulleted_list_item", "numbered_list_item"}:
            lines.append(f"・{text}")
        elif kind in {"paragraph", "quote", "callout", "code"}:
            lines.append(text)
        elif kind == "divider":
            lines.append("")
        if block.get("children"):
            lines.append(blocks_to_markdown(block["children"]))
        lines.append("")
    return "\n".join(lines)
