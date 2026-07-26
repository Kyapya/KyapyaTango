from __future__ import annotations

import json
import sys
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from normalize_content import (  # noqa: E402
    normalize_entry,
    normalize_file,
    normalize_sense_title,
)


class SenseTitleNormalizationTests(unittest.TestCase):
    def test_repairs_missing_closing_bracket(self) -> None:
        self.assertEqual(normalize_sense_title("【形容詞"), "【形容詞】")

    def test_repairs_missing_opening_bracket(self) -> None:
        self.assertEqual(normalize_sense_title("形容詞】"), "【形容詞】")

    def test_preserves_balanced_and_plain_titles(self) -> None:
        self.assertEqual(normalize_sense_title("【形容詞】"), "【形容詞】")
        self.assertEqual(normalize_sense_title("形容詞"), "形容詞")

    def test_normalizes_all_senses_in_an_entry(self) -> None:
        entry = {
            "senses": [
                {"number": 1, "title": "【形容詞"},
                {"number": 2, "title": "【形容詞・古風／歴史的用法"},
            ]
        }
        self.assertTrue(normalize_entry(entry))
        self.assertEqual(entry["senses"][0]["title"], "【形容詞】")
        self.assertEqual(
            entry["senses"][1]["title"],
            "【形容詞・古風／歴史的用法】",
        )

    def test_normalize_file_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "enormous.json"
            path.write_text(
                json.dumps(
                    {"word": "enormous", "senses": [{"title": "【形容詞"}]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertTrue(normalize_file(path))
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["senses"][0]["title"], "【形容詞】")


if __name__ == "__main__":
    unittest.main()
