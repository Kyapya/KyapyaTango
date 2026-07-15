from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_JS = ROOT / "assets" / "site.js"
FINALIZER = ROOT / "scripts" / "finalize_site.py"


class MobileToolbarBehaviorTests(unittest.TestCase):
    def test_action_buttons_do_not_auto_close_toolbar(self) -> None:
        script = SITE_JS.read_text(encoding="utf-8")
        self.assertNotIn("closeAfterAction", script)
        self.assertNotIn("setTimeout(() => setOpen(false), 120)", script)

    def test_downward_scroll_closes_and_hides_toolbar(self) -> None:
        script = SITE_JS.read_text(encoding="utf-8")
        self.assertIn("if (delta > 0)", script)
        self.assertIn("setOpen(false);", script)
        self.assertIn("toolbar.classList.add('mobile-toolbar-hidden')", script)
        self.assertIn("toolbar.classList.remove('mobile-toolbar-hidden')", script)

    def test_outside_interaction_still_closes_toolbar(self) -> None:
        script = SITE_JS.read_text(encoding="utf-8")
        self.assertIn("!toolbar.contains(event.target)", script)
        self.assertIn("setOpen(false);", script)

    def test_japanese_fragments_toggle_with_a_class(self) -> None:
        script = SITE_JS.read_text(encoding="utf-8")
        self.assertIn("classList.toggle('ja-revealed')", script)
        self.assertIn("classList.remove('ja-revealed')", script)
        self.assertNotIn("el.style.filter", script)
        self.assertNotIn("element.style.filter", script)

    def test_touch_hover_cannot_keep_hidden_text_revealed(self) -> None:
        finalizer = FINALIZER.read_text(encoding="utf-8")
        self.assertIn(".hide-ja .ja.ja-revealed{filter:none}", finalizer)
        self.assertIn("hover:none", finalizer)
        self.assertIn(":hover:not(.ja-revealed){filter:blur(5px)}", finalizer)


if __name__ == "__main__":
    unittest.main()
