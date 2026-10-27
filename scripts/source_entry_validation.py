"""Pinned source-format validator, copied from english-dictionary at
 a95ccaa6c60320a4f889701da37d3ffc50d432d0. No source-repository code is executed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FINAL_HEADING = "＃意味・用法・関連表現"
LEGACY_FINAL_HEADINGS = ("＃意味や関連情報の出力（日本語訳）",)
FINAL_HEADING_ALIASES = (FINAL_HEADING, *LEGACY_FINAL_HEADINGS)
REQUIRED_HEADINGS = [
    "＃発音記号",
    "＃語源",
]
ORDERED_HEADINGS = [
    "＃発音記号",
    "＃語源",
    "＃語形成",
    "＃コアイメージ",
    *FINAL_HEADING_ALIASES,
]


def _normalized_major_heading(line: str) -> str | None:
    """Return a known section heading in its canonical form.

    Legacy entries use fullwidth hash markers. Markdown entries may use one or
    two ASCII hash markers followed by a space.
    """
    stripped = line.strip()
    if stripped in ORDERED_HEADINGS:
        return stripped
    match = re.fullmatch(r"#{1,2}\s+(.+?)(?:\s+#+)?", stripped)
    if match is None:
        return None
    canonical = f"＃{match.group(1).strip()}"
    return canonical if canonical in ORDERED_HEADINGS else None


def _is_major_heading_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("＃") or bool(re.match(r"^#{1,6}\s+", stripped))


REQUIRED_FRONT_MATTER_KEYS = (
    "headword",
    "type",
    "status",
    "prompt_version",
    "created_at",
    "updated_at",
    "checked",
)
VALID_STATUSES = {
    "pending",
    "draft",
    "format_error",
    "needs_review",
    "review_ready",
    "checked",
    "final",
    "skip",
}
SUPPORTED_PROMPT_VERSIONS = {
    "entry_spec_v1",
    "entry_spec_v2",
    "entry_spec_v3",
    "entry_spec_v4",
    "entry_spec_v5",
}
SENSE_PATTERN = re.compile(r"^\d+\.\s*【.+】")
RELATION_FREQUENCY_PATTERN = re.compile(r"^頻度: 〈(?:10|[1-9])/10〉$")
SENSE_FREQUENCY_PATTERN = re.compile(r"〈(?:頻度:\s*)?(?:10|[1-9])/10〉")
LEGACY_PLACEHOLDER_PATTERN = re.compile(
    r"\+\s+(?:O\b|[ぁ-んァ-ヶ一-龠々]+(?:[・/][ぁ-んァ-ヶ一-龠々]+)*)"
)
LEGACY_SQUARE_PLACEHOLDER_PATTERN = re.compile(r"\[[^\]\n]+\]")
REDUNDANT_PREPOSITIONAL_PLUS_PATTERN = re.compile(
    r"\b(?:about|above|across|after|against|along|among|around|as|at|before|"
    r"behind|below|beneath|beside|between|beyond|by|during|except|for|from|in|"
    r"inside|into|near|of|off|on|onto|outside|over|past|since|through|throughout|"
    r"to|toward|towards|under|until|up|upon|via|with|within|without)\s+\+\s+〈",
    re.IGNORECASE,
)
ADJACENT_PLACEHOLDER_PATTERN = re.compile(r"〉\s+〈")
BRACKETED_GENERIC_SLOT_PATTERN = re.compile(
    r"〈(?:someone|something|someone/something|team|organization|team/organization)〉",
    re.IGNORECASE,
)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "]"
)
INLINE_SENSE_LABELS = (
    "【日本語訳・定義】",
    "【頻度】",
    "【レジスター/領域】",
    "【文法パターン】",
    "【語法・注意】",
)
GROUPED_SENSE_LABELS = (
    "【コロケーション】",
    "【類義語】",
    "【反意語】",
)
INTRANSITIVE_PREPOSITIONS = {
    "about",
    "against",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "on",
    "to",
    "under",
    "with",
    "without",
}
GRAMMAR_FRAME_ENFORCEMENT_DATE = "2026-08-27"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_front_matter(text: str) -> tuple[list[str] | None, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], "\n".join(lines[index + 1 :])
    return None, text


def _front_matter_values(front_matter: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in front_matter:
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
    return values


def _next_nonempty(lines: list[str], start: int, count: int) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped:
            found.append((index, stripped))
        if len(found) == count:
            break
    return found


def _check_headings(lines: list[str]) -> list[str]:
    errors: list[str] = []
    positions: dict[str, int] = {}
    for heading in ORDERED_HEADINGS:
        matches = [
            index
            for index, line in enumerate(lines)
            if _normalized_major_heading(line) == heading
        ]
        if len(matches) > 1:
            errors.append(f"duplicate heading: {heading}")
        if matches:
            positions[heading] = matches[0]

    for heading in REQUIRED_HEADINGS:
        if heading not in positions:
            errors.append(f"missing required heading: {heading}")

    present_final_headings = [
        heading for heading in FINAL_HEADING_ALIASES if heading in positions
    ]
    if not present_final_headings:
        aliases = " / ".join(FINAL_HEADING_ALIASES)
        errors.append(f"missing required heading: one of {aliases}")
    elif len(present_final_headings) > 1:
        errors.append(
            "duplicate final heading: " + " / ".join(present_final_headings)
        )

    present_in_document = sorted(positions, key=positions.get)
    expected_present = [
        heading
        for heading in ORDERED_HEADINGS
        if heading in positions
        and not (
            heading in FINAL_HEADING_ALIASES
            and any(
                other in positions
                for other in FINAL_HEADING_ALIASES
                if other != heading
            )
        )
    ]
    if present_in_document != expected_present:
        expected = " -> ".join(expected_present)
        errors.append(f"heading order is wrong; expected {expected}")
    return errors


def _check_example_translation_balance(lines: list[str]) -> list[str]:
    example_count = sum(1 for line in lines if line.strip().startswith("例:"))
    translation_count = sum(1 for line in lines if line.strip().startswith("訳:"))
    if example_count != translation_count:
        return [
            "example/translation count looks unbalanced: "
            f"例:={example_count}, 訳:={translation_count}"
        ]
    return []


def _section_lines(lines: list[str], marker_index: int) -> list[tuple[int, str]]:
    content: list[tuple[int, str]] = []
    for index in range(marker_index + 1, len(lines)):
        stripped = lines[index].strip()
        if (
            _is_major_heading_line(stripped)
            or stripped.startswith("【")
            or SENSE_PATTERN.match(stripped)
        ):
            break
        if stripped:
            content.append((index, stripped))
    return content


def _raw_section_lines(lines: list[str], marker_index: int) -> list[tuple[int, str]]:
    content: list[tuple[int, str]] = []
    for index in range(marker_index + 1, len(lines)):
        raw = lines[index]
        stripped = raw.strip()
        if (
            _is_major_heading_line(stripped)
            or stripped.startswith("【")
            or SENSE_PATTERN.match(stripped)
        ):
            break
        if stripped:
            content.append((index, raw))
    return content


def _check_fixed_blocks(
    lines: list[str],
    marker: str,
    expected: list[tuple[str, str]],
) -> list[str]:
    errors: list[str] = []
    block_size = len(expected)
    for index, line in enumerate(lines):
        if not line.strip().startswith(marker):
            continue
        content = _section_lines(lines, index)
        if not content:
            errors.append(f"line {index + 1}: {marker} section has no entries")
            continue
        if len(content) % block_size != 0:
            errors.append(
                f"line {index + 1}: {marker} section has {len(content)} non-empty lines; "
                f"expected a multiple of {block_size}"
            )
        complete_length = len(content) - (len(content) % block_size)
        for offset in range(0, complete_length, block_size):
            block = content[offset : offset + block_size]
            for (line_index, text), (prefix, label) in zip(block, expected):
                if not text.startswith(prefix):
                    errors.append(
                        f"line {line_index + 1}: {marker} {label} line should start with {prefix}"
                    )
    return errors


def _check_collocation_blocks(lines: list[str]) -> list[str]:
    return _check_fixed_blocks(
        lines,
        "【コロケーション】",
        [
            ("・", "pattern"),
            ("用途:", "usage"),
            ("例:", "example"),
            ("訳:", "translation"),
        ],
    )


def _check_relation_blocks(lines: list[str], marker: str) -> list[str]:
    return _check_fixed_blocks(
        lines,
        marker,
        [
            ("・", "entry term"),
            ("定義:", "definition"),
            ("頻度:", "frequency"),
            ("違い:", "difference"),
            ("例:", "example"),
            ("訳:", "translation"),
        ],
    )


def _check_sense_blocks(
    lines: list[str], *, allow_missing_synonyms: bool = False
) -> list[str]:
    errors: list[str] = []
    starts = [index for index, line in enumerate(lines) if SENSE_PATTERN.match(line.strip())]
    if not starts:
        return ["no numbered sense blocks found"]

    required_markers = [
        "【日本語訳・定義】",
        "【頻度】",
        "【レジスター/領域】",
        "【文法パターン】",
        "【コロケーション】",
        "【語法・注意】",
        "【類義語】",
    ]
    ordered_markers = required_markers + ["【反意語】"]
    if allow_missing_synonyms:
        required_markers.remove("【類義語】")
    for number, start in enumerate(starts, start=1):
        end = starts[number] if number < len(starts) else len(lines)
        block = lines[start:end]
        positions: dict[str, int] = {}
        for marker in ordered_markers:
            matches = [
                index
                for index, line in enumerate(block)
                if line.strip().startswith(marker)
            ]
            if len(matches) > 1:
                errors.append(f"line {start + 1}: sense {number} has duplicate {marker}")
            if matches:
                positions[marker] = matches[0]
        for marker in required_markers:
            if marker not in positions:
                errors.append(f"line {start + 1}: sense {number} is missing {marker}")
        present_order = sorted(positions, key=positions.get)
        expected_order = [
            marker
            for marker in ordered_markers
            if marker in positions
        ]
        if present_order != expected_order:
            errors.append(f"line {start + 1}: sense {number} subsection order is wrong")
    return errors


def _check_v3_heading_layout(lines: list[str]) -> list[str]:
    errors: list[str] = []
    nonempty = [index for index, line in enumerate(lines) if line.strip()]
    if nonempty and _normalized_major_heading(lines[nonempty[0]]) != "＃発音記号":
        errors.append("current-spec body must start with the pronunciation heading and contain no preamble")

    for heading in ORDERED_HEADINGS:
        matches = [
            index
            for index, line in enumerate(lines)
            if _normalized_major_heading(line) == heading
        ]
        for index in matches:
            if index > nonempty[0] and (index == 0 or lines[index - 1].strip()):
                errors.append(f"line {index + 1}: {heading} must have a blank line before it")
            if index + 1 >= len(lines) or lines[index + 1].strip():
                errors.append(f"line {index + 1}: {heading} must have a blank line after it")
    return errors


def _check_v3_fixed_block_layout(
    lines: list[str],
    marker: str,
    block_size: int,
) -> list[str]:
    errors: list[str] = []
    for marker_index, line in enumerate(lines):
        if not line.strip().startswith(marker):
            continue
        content = _raw_section_lines(lines, marker_index)
        if not content or len(content) % block_size != 0:
            continue
        for offset, (line_index, raw) in enumerate(content):
            if not raw.endswith("  "):
                errors.append(
                    f"line {line_index + 1}: {marker} entry lines must end with two spaces"
                )
            if offset == 0:
                continue
            previous_index = content[offset - 1][0]
            expected_gap = 2 if offset % block_size == 0 else 1
            actual_gap = line_index - previous_index
            if actual_gap != expected_gap:
                if expected_gap == 1:
                    errors.append(
                        f"line {line_index + 1}: {marker} entry must not contain blank lines"
                    )
                else:
                    errors.append(
                        f"line {line_index + 1}: {marker} entries must be separated by one blank line"
                    )
    return errors


def _check_v3_frequencies(lines: list[str]) -> list[str]:
    errors: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("【頻度】") and not SENSE_FREQUENCY_PATTERN.search(stripped):
            errors.append(
                f"line {index + 1}: sense frequency must contain 〈n/10〉 with n from 1 to 10"
            )

    for marker in ("【類義語】", "【反意語】"):
        for marker_index, line in enumerate(lines):
            if not line.strip().startswith(marker):
                continue
            content = _section_lines(lines, marker_index)
            complete_length = len(content) - (len(content) % 6)
            for offset in range(0, complete_length, 6):
                line_index, frequency = content[offset + 2]
                if not RELATION_FREQUENCY_PATTERN.fullmatch(frequency):
                    errors.append(
                        f"line {line_index + 1}: {marker} frequency must be "
                        "頻度: 〈n/10〉 with n from 1 to 10"
                    )
    return errors


def _declared_family_forms(lines: list[str]) -> set[str]:
    """Read explicitly named forms, not English words in explanatory prose.

    This establishes article-local scope only; the independent content review
    still has to verify the linguistic relationship to the headword.
    """
    forms: set[str] = set()
    in_formation = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("＃"):
            in_formation = stripped == "＃語形成"
        elif in_formation:
            match = re.match(r"・([A-Za-z]+(?:-[A-Za-z]+)*)(?=[：:（(])", stripped)
            if match:
                forms.add(match.group(1).casefold())
    return forms


def _contains_form(text: str, form: str) -> bool:
    return re.search(rf"(?<![A-Za-z]){re.escape(form)}(?![A-Za-z])", text, re.I) is not None


def _regular_plural_forms(form: str) -> set[str]:
    forms = {form, form + "s"}
    if re.search(r"[^aeiou]y$", form):
        forms.add(form[:-1] + "ies")
    if form.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(form + "es")
    return forms


def _check_v3_collocation_headword(lines: list[str], headword: str) -> list[str]:
    errors: list[str] = []
    if not headword:
        return errors
    expected = headword.casefold()
    declared_forms = _declared_family_forms(lines)
    sense_forms: set[str] = set()
    for marker_index, line in enumerate(lines):
        if SENSE_PATTERN.match(line.strip()):
            # A form must be declared in this sense's grammatical label, not
            # merely mentioned in a definition, example, or another sense.
            label = re.search(r"【([^】]+)】", line)
            sense_forms = set()
            if label:
                for form in declared_forms:
                    if _contains_form(label.group(1), form):
                        sense_forms.update(_regular_plural_forms(form))
        elif line.strip().startswith("＃"):
            sense_forms = set()
        if not line.strip().startswith("【コロケーション】"):
            continue
        content = _section_lines(lines, marker_index)
        complete_length = len(content) - (len(content) % 4)
        for offset in range(0, complete_length, 4):
            line_index, pattern = content[offset]
            if expected not in pattern.casefold() and not any(
                _contains_form(pattern, form) for form in sense_forms
            ):
                errors.append(
                    f"line {line_index + 1}: collocation pattern must include headword: {headword}"
                )
    return errors


def _check_modern_content(lines: list[str], headword: str) -> list[str]:
    errors: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if "【続きあり】" in stripped:
            errors.append(f"line {index + 1}: completed current-spec entry must not contain 【続きあり】")
        if stripped.startswith("【例文】"):
            errors.append(f"line {index + 1}: current-spec entry must not use an independent 【例文】 section")
        if EMOJI_PATTERN.search(line):
            errors.append(f"line {index + 1}: current-spec entry must not contain emoji")

    errors.extend(_check_v3_heading_layout(lines))
    errors.extend(_check_v3_fixed_block_layout(lines, "【コロケーション】", 4))
    errors.extend(_check_v3_fixed_block_layout(lines, "【類義語】", 6))
    errors.extend(_check_v3_fixed_block_layout(lines, "【反意語】", 6))
    errors.extend(_check_v3_frequencies(lines))
    errors.extend(_check_v3_collocation_headword(lines, headword))
    return errors


def _is_v5_structural_line(stripped: str) -> bool:
    return (
        _is_major_heading_line(stripped)
        or stripped in GROUPED_SENSE_LABELS
        or bool(SENSE_PATTERN.match(stripped))
    )


def _check_v5_line_endings(lines: list[str]) -> list[str]:
    errors: list[str] = []
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        trailing_spaces = len(raw) - len(raw.rstrip(" "))
        if _is_v5_structural_line(stripped):
            if trailing_spaces:
                errors.append(
                    f"line {index + 1}: v5 structural headings must not have trailing spaces"
                )
        elif trailing_spaces != 2:
            errors.append(
                f"line {index + 1}: v5 content lines must end with exactly two spaces"
            )
    return errors


def _check_v5_blank_lines(lines: list[str]) -> list[str]:
    errors: list[str] = []
    for index in range(1, len(lines)):
        if not lines[index].strip() and not lines[index - 1].strip():
            errors.append(f"line {index + 1}: v5 body must not contain consecutive blank lines")

    for index, raw in enumerate(lines):
        stripped = raw.strip()
        is_independent = (
            bool(SENSE_PATTERN.match(stripped))
            or stripped in GROUPED_SENSE_LABELS
            or any(stripped.startswith(label) for label in INLINE_SENSE_LABELS)
        )
        if not is_independent:
            continue
        if index == 0 or lines[index - 1].strip():
            errors.append(
                f"line {index + 1}: v5 independent blocks require one blank line before"
            )
        terminal_usage_note = (
            index == len(lines) - 1
            and stripped.startswith("【語法・注意】")
            and bool(stripped.removeprefix("【語法・注意】").strip())
        )
        if not terminal_usage_note and (
            index + 1 >= len(lines) or lines[index + 1].strip()
        ):
            errors.append(
                f"line {index + 1}: v5 independent blocks require one blank line after"
            )
    return errors


def _check_v5_label_shapes(lines: list[str]) -> list[str]:
    errors: list[str] = []
    expected_sense_number = 1
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if SENSE_PATTERN.match(stripped):
            match = re.fullmatch(r"(\d+)\.\s+【[^】]+】\s*\S.*", stripped)
            if match is None:
                errors.append(
                    f"line {index + 1}: v5 sense heading must include a translation after 【品詞・自他等】"
                )
            else:
                actual_number = int(match.group(1))
                if actual_number != expected_sense_number:
                    errors.append(
                        f"line {index + 1}: v5 sense numbers must be consecutive; "
                        f"expected {expected_sense_number}, got {actual_number}"
                    )
                expected_sense_number += 1

        for label in INLINE_SENSE_LABELS:
            if stripped.startswith(label) and not stripped[len(label) :].strip():
                errors.append(
                    f"line {index + 1}: v5 {label} must keep its content on the same line"
                )
        for label in GROUPED_SENSE_LABELS:
            if stripped.startswith(label) and stripped != label:
                errors.append(
                    f"line {index + 1}: v5 {label} must be a standalone heading"
                )

        if stripped.startswith("【頻度】") and not re.fullmatch(
            r"【頻度】〈(?:10|[1-9])/10〉", stripped
        ):
            errors.append(
                f"line {index + 1}: v5 sense frequency must be exactly 【頻度】〈n/10〉"
            )
    return errors


def _check_v5_forbidden_fillers(lines: list[str]) -> list[str]:
    errors: list[str] = []
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if "該当なし" in stripped or "特になし" in stripped:
            errors.append(
                f"line {index + 1}: v5 omits inapplicable fields instead of using filler text"
            )
    return errors


def _check_v5_format(lines: list[str]) -> list[str]:
    errors: list[str] = []
    errors.extend(_check_v5_line_endings(lines))
    errors.extend(_check_v5_blank_lines(lines))
    errors.extend(_check_v5_label_shapes(lines))
    errors.extend(_check_v5_forbidden_fillers(lines))
    return errors


def _classify_grammar_frame(pattern: str, headword: str) -> str | None:
    expression = pattern.split("＝", 1)[0].strip()
    match = re.search(rf"(?<![A-Za-z]){re.escape(headword)}(?![A-Za-z])", expression, re.I)
    if match is None:
        return None
    prefix = expression[: match.start()].strip().strip("`")
    if re.fullmatch(r"(?:be|am|is|are|was|were|been|being)", prefix, re.I):
        return "transitive"
    if prefix and not prefix.endswith("〉"):
        return None
    tail = expression[match.end() :].strip().lstrip("+").strip()
    if not tail:
        return None
    first = re.match(r"([A-Za-z]+)", tail)
    token = first.group(1).casefold() if first else ""
    if token in INTRANSITIVE_PREPOSITIONS:
        remainder = tail[first.end() :].strip() if first else ""
        if token == "to" and re.match(r"(?:do|be|have)\b", remainder, re.I):
            return None
        return "intransitive" if "〈" in tail else None
    if token == "oneself":
        return "transitive"
    if token == "up":
        remainder = tail[first.end() :].strip() if first else ""
        return "transitive" if remainder else None
    if tail.startswith("〈") or tail[0].isdigit():
        return "transitive"
    if re.match(r"(?:a|an|the|this|that|one's|[A-Za-z]+)\b", tail, re.I):
        return "transitive"
    return None


def grammar_frame_diagnostics(
    lines: list[str], headword: str
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    starts = [index for index, line in enumerate(lines) if SENSE_PATTERN.match(line.strip())]
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(lines)
        heading = lines[start].strip()
        label_match = re.search(r"【([^】]+)】", heading)
        label = label_match.group(1) if label_match else ""
        has_intransitive = "自動詞" in label
        has_transitive = "他動詞" in label
        if has_intransitive == has_transitive:
            continue
        for index in range(start + 1, end):
            stripped = lines[index].strip()
            if not stripped.startswith("【文法パターン】"):
                continue
            content = stripped.removeprefix("【文法パターン】").strip()
            for pattern in (item.strip() for item in content.split("／") if item.strip()):
                frame = _classify_grammar_frame(pattern, headword)
                if frame is None:
                    warnings.append(
                        f"line {index + 1}: grammar frame could not be classified: {pattern}"
                    )
                elif has_intransitive and frame == "transitive":
                    errors.append(
                        f"line {index + 1}: format_error: intransitive-only sense has "
                        f"a transitive grammar frame: {pattern}"
                    )
                elif has_transitive and frame == "intransitive":
                    errors.append(
                        f"line {index + 1}: format_error: transitive-only sense has "
                        f"an intransitive grammar frame: {pattern}"
                    )
    return errors, warnings


def _check_v5_notation_warnings(lines: list[str]) -> list[str]:
    warnings: list[str] = []
    candidate_indexes = {
        index
        for index, line in enumerate(lines)
        if line.strip().startswith("【文法パターン】")
    }
    for marker_index, line in enumerate(lines):
        if not line.strip().startswith("【コロケーション】"):
            continue
        content = _section_lines(lines, marker_index)
        complete_length = len(content) - (len(content) % 4)
        candidate_indexes.update(
            content[offset][0] for offset in range(0, complete_length, 4)
        )

    for index in sorted(candidate_indexes):
        stripped = lines[index].strip()
        if LEGACY_PLACEHOLDER_PATTERN.search(stripped):
            warnings.append(
                f"line {index + 1}: legacy placeholder notation detected; "
                "use 〈...〉 for placeholders and reserve + for syntactic slot boundaries"
            )
        if LEGACY_SQUARE_PLACEHOLDER_PATTERN.search(stripped):
            warnings.append(
                f"line {index + 1}: legacy square-bracket placeholder notation detected; "
                "use 〈...〉 for placeholders"
            )
        if REDUNDANT_PREPOSITIONAL_PLUS_PATTERN.search(stripped):
            warnings.append(
                f"line {index + 1}: redundant + before an angle-bracket placeholder; "
                "write the preposition directly before 〈...〉"
            )
        if ADJACENT_PLACEHOLDER_PATTERN.search(stripped):
            warnings.append(
                f"line {index + 1}: adjacent placeholders detected; "
                "separate syntactic slots with +"
            )
        if BRACKETED_GENERIC_SLOT_PATTERN.search(stripped):
            warnings.append(
                f"line {index + 1}: bracketed English generic slot detected; "
                "leave someone, something, and team/organization unbracketed"
            )
    return warnings


def _normalize_collocation_heading(text: str) -> str:
    """Accept the canonical heading while retaining legacy validation rules.

    Only structural labels at line starts are aliases; prose is never rewritten.
    Line counts and trailing spaces are preserved for diagnostics.
    """
    return re.sub(
        r"^(\s*)【コロケーション・構文例】",
        r"\1【コロケーション】",
        text,
        flags=re.MULTILINE,
    )


def validate_text(text: str) -> list[str]:
    text = _normalize_collocation_heading(text)
    errors: list[str] = []
    front_matter, body = _split_front_matter(text)
    if front_matter is None:
        errors.append("missing YAML front matter delimited by ---")
        front_values: dict[str, str] = {}
    else:
        front_values = _front_matter_values(front_matter)
        for key in REQUIRED_FRONT_MATTER_KEYS:
            if not front_values.get(key):
                errors.append(f"front matter is missing {key}:")
        status = front_values.get("status", "")
        checked = front_values.get("checked", "").lower()
        prompt_version = front_values.get("prompt_version", "")
        if status and status not in VALID_STATUSES:
            errors.append(f"front matter has invalid status: {status}")
        if prompt_version and prompt_version not in SUPPORTED_PROMPT_VERSIONS:
            errors.append(f"front matter has unsupported prompt_version: {prompt_version}")
        if checked and checked not in {"true", "false"}:
            errors.append("front matter checked: must be true or false")
        if status in {"checked", "final"} and checked != "true":
            errors.append(f"front matter status {status} requires checked: true")
        if (
            status in {"draft", "format_error", "needs_review", "review_ready"}
            and checked == "true"
        ):
            errors.append(f"front matter status {status} is inconsistent with checked: true")

    lines = body.splitlines()
    errors.extend(_check_headings(lines))
    errors.extend(
        _check_sense_blocks(
            lines,
            allow_missing_synonyms=front_values.get("prompt_version") == "entry_spec_v5",
        )
    )
    errors.extend(_check_example_translation_balance(lines))
    errors.extend(_check_collocation_blocks(lines))
    errors.extend(_check_relation_blocks(lines, "【類義語】"))
    errors.extend(_check_relation_blocks(lines, "【反意語】"))
    if front_values.get("prompt_version") in {
        "entry_spec_v3",
        "entry_spec_v4",
        "entry_spec_v5",
    }:
        errors.extend(_check_modern_content(lines, front_values.get("headword", "")))
    if front_values.get("prompt_version") == "entry_spec_v5":
        errors.extend(_check_v5_format(lines))
        if front_values.get("created_at", "") >= GRAMMAR_FRAME_ENFORCEMENT_DATE:
            frame_errors, _ = grammar_frame_diagnostics(
                lines, front_values.get("headword", "")
            )
            errors.extend(frame_errors)
    return errors


def validate_file(path: Path) -> list[str]:
    return validate_text(_read_text(path))


def validation_warnings(text: str) -> list[str]:
    text = _normalize_collocation_heading(text)
    front_matter, body = _split_front_matter(text)
    if front_matter is None:
        return []
    front_values = _front_matter_values(front_matter)
    if front_values.get("prompt_version") != "entry_spec_v5":
        return []
    lines = body.splitlines()
    _, frame_warnings = grammar_frame_diagnostics(
        lines, front_values.get("headword", "")
    )
    return [*_check_v5_notation_warnings(lines), *frame_warnings]


def validation_file_warnings(path: Path) -> list[str]:
    return validation_warnings(_read_text(path))


def _resolve_target(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return REPO_ROOT / path


def _collect_markdown_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(path for path in target.rglob("*.md") if path.is_file())
    raise FileNotFoundError(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate dictionary entry Markdown format.")
    parser.add_argument(
        "target",
        nargs="?",
        default="entries",
        help="Markdown file or directory to validate. Defaults to entries/.",
    )
    args = parser.parse_args(argv)

    target = _resolve_target(args.target)
    try:
        files = _collect_markdown_files(target)
    except FileNotFoundError:
        print(f"ERROR: target not found: {target}", file=sys.stderr)
        return 1

    if not files:
        print(f"No Markdown files found under {target}")
        return 0

    failed = False
    for path in files:
        errors = validate_file(path)
        warnings = validation_file_warnings(path)
        label = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        if warnings:
            print(f"WARNING {label}")
            for warning in warnings:
                print(f"  - {warning}")
        if errors:
            failed = True
            print(f"ERROR {label}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
