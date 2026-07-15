from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_JS = ROOT / "assets" / "site.js"


class MobileToolbarBehaviorTests(unittest.TestCase):
    def test_action_buttons_do_not_auto_close_toolbar(self) -> None:
        script = SITE_JS.read_text(encoding="utf-8")
        self.assertNotIn("closeAfterAction", script)
        self.assertNotIn("setTimeout(() => setOpen(false), 120)", script)

    def test_outside_interaction_still_closes_toolbar(self) -> None:
        script = SITE_JS.read_text(encoding="utf-8")
        self.assertIn("!toolbar.contains(event.target)", script)
        self.assertIn("setOpen(false);", script)


if __name__ == "__main__":
    unittest.main()
