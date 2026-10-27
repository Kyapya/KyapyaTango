"""Pure source-to-block adapter; no Notion requests or credentials.

Copied without semantic changes from Kyapya/english-dictionary
scripts/import_to_notion.py at a95ccaa6c60320a4f889701da37d3ffc50d432d0.
Keep this compatibility transform pinned and tested; never execute fetched code.
"""
from __future__ import annotations
import json
import re
from typing import Any

MAX_TEXT_CHARS = 1900

SUBHEADING_LABELS = (
    "【日本語訳・定義】",
    "【頻度】",
    "【レジスター/領域】",
    "【文法パターン】",
    "【コロケーション・構文例】",
    "【語法・注意】",
    "【類義語】",
    "【反意語】",
)

GROUPED_ENTRY_SECTIONS = {"【コロケーション・構文例】", "【類義語】", "【反意語】"}

GROUPED_ENTRY_SCHEMAS = {
    "【コロケーション・構文例】": ("・", "用途:", "例:", "訳:"),
    "【類義語】": ("・", "定義:", "頻度:", "違い:", "例:", "訳:"),
    "【反意語】": ("・", "定義:", "頻度:", "違い:", "例:", "訳:"),
}

INLINE_MARKUP_PATTERN = re.compile(r"(<br>|\n|`[^`\n]+`|\*[^*\n]+\*)")

def _split_front_matter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Entry is missing YAML front matter.")
    end = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if end is None:
        raise ValueError("Entry has unterminated YAML front matter.")
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        cleaned = value.strip()
        if cleaned.startswith('"') and cleaned.endswith('"'):
            try:
                cleaned = json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        values[key.strip()] = str(cleaned)
    return values, "\n".join(lines[end + 1 :]).strip()

def chunk_text(text: str, limit: int = MAX_TEXT_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    rest = text
    while len(rest) > limit:
        split_at = rest.rfind(" ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(rest[:split_at].rstrip())
        rest = rest[split_at:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks

def _rich_text_item(content: str, *, italic: bool = False, code: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "text", "text": {"content": content}}
    if italic or code:
        item["annotations"] = {
            "bold": False,
            "italic": italic,
            "strikethrough": False,
            "underline": False,
            "code": code,
            "color": "default",
        }
    return item

def rich_text(content: str) -> list[dict[str, Any]]:
    """Compile the repository's inline Markdown to Notion rich-text objects."""
    items: list[dict[str, Any]] = []
    cursor = 0
    for match in INLINE_MARKUP_PATTERN.finditer(content):
        if match.start() > cursor:
            items.append(_rich_text_item(content[cursor : match.start()]))
        token = match.group(0)
        if token in {"<br>", "\n"}:
            # <br> is the conversion contract; the API's native representation is a
            # newline inside the same rich_text block, not the literal HTML string.
            items.append(_rich_text_item("\n"))
        elif token.startswith("`"):
            items.append(_rich_text_item(token[1:-1], code=True))
        else:
            items.append(_rich_text_item(token[1:-1], italic=True))
        cursor = match.end()
    if cursor < len(content):
        items.append(_rich_text_item(content[cursor:]))
    return items or [_rich_text_item("")]

def text_block(block_type: str, content: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": rich_text(content)},
    }

def _heading_block(
    line: str,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    stripped = line.strip()
    fullwidth = re.match(r"^＃\s*(.+)$", stripped)
    if fullwidth:
        return text_block("heading_1", fullwidth.group(1)), None, None
    markdown = re.match(r"^(#{1,3})\s*(.+)$", stripped)
    if markdown:
        level = min(len(markdown.group(1)), 3)
        return text_block(f"heading_{level}", markdown.group(2)), None, None
    if re.match(r"^\d+\.\s*【.+】", stripped):
        return text_block("heading_2", stripped), None, None
    for label in SUBHEADING_LABELS:
        if stripped.startswith(label):
            remainder = stripped[len(label) :].strip()
            return text_block("heading_3", label[1:-1]), label, remainder or None
    return None, None, None

def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    # Both source labels produce the canonical Notion heading and identical cards.
    markdown = re.sub(
        r"^(\s*)【コロケーション】", r"\1【コロケーション・構文例】",
        markdown, flags=re.MULTILINE,
    )
    lines = markdown.splitlines()
    blocks: list[dict[str, Any]] = []
    grouped_section: str | None = None
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue

        heading, label, remainder = _heading_block(stripped)
        if heading is not None:
            blocks.append(heading)
            grouped_section = label if label in GROUPED_ENTRY_SECTIONS else None
            if grouped_section and remainder:
                raise ValueError(f"{grouped_section} must be a standalone source heading.")
            if remainder:
                for chunk in chunk_text(remainder):
                    blocks.append(text_block("paragraph", chunk))
            index += 1
            continue

        if grouped_section and stripped.startswith("・"):
            entry_lines = [stripped]
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate:
                    break
                candidate_heading, _, _ = _heading_block(candidate)
                if candidate_heading is not None or candidate.startswith("・"):
                    break
                entry_lines.append(candidate)
                index += 1
            expected_prefixes = GROUPED_ENTRY_SCHEMAS[grouped_section]
            if len(entry_lines) != len(expected_prefixes) or any(
                not line.startswith(prefix)
                for line, prefix in zip(entry_lines, expected_prefixes)
            ):
                raise ValueError(
                    f"Malformed {grouped_section} entry; expected "
                    f"{len(expected_prefixes)} fixed lines in one block."
                )
            entry_text = "<br>".join(entry_lines)
            if len(entry_text) > MAX_TEXT_CHARS:
                raise ValueError(
                    f"A {grouped_section} entry exceeds Notion's safe text size: "
                    f"{len(entry_text)} characters"
                )
            blocks.append(text_block("paragraph", entry_text))
            continue

        grouped_section = None
        if stripped.startswith("・") or stripped.startswith("- ") or stripped.startswith("* "):
            content = stripped[1:].strip() if stripped.startswith("・") else stripped[2:].strip()
            for chunk in chunk_text(content):
                blocks.append(text_block("bulleted_list_item", chunk))
        else:
            for chunk in chunk_text(stripped):
                blocks.append(text_block("paragraph", chunk))
        index += 1
    return blocks
