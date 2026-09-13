"""Both Unmaking renderers must survive consolidation.

There are two renderers for the Null King's spell, on purpose, at two scales:
web/js/unmakingfx.js is the world map (15.6s, wordless, non-blocking) and
web/js/spellfx.js §THE UNMAKING is the last chamber (116.75s, five acts, a
title card). They share a function name, which makes them look like an obvious
duplication to anyone sweeping for it.

docs/11-the-two-unmakings.md is the argument. This file is the tripwire, so a
pass that deletes one of them fails a test instead of shipping.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORLD = ROOT / "web" / "js" / "unmakingfx.js"
CHAMBER = ROOT / "web" / "js" / "spellfx.js"
SPELL = ROOT / "gauntlet" / "unmaking.py"
RULE = ROOT / "docs" / "11-the-two-unmakings.md"


class TestBothRenderersSurvive(unittest.TestCase):
    def test_all_three_files_exist(self):
        for p in (WORLD, CHAMBER, SPELL, RULE):
            self.assertTrue(p.is_file(), f"{p.relative_to(ROOT)} is gone — "
                                         "read docs/11-the-two-unmakings.md "
                                         "before deleting either renderer")

    def test_world_renderer_is_the_short_wordless_one(self):
        src = WORLD.read_text()
        self.assertIn("export function createUnmaking", src)
        self.assertIn("export const BEATS", src)
        # The standalone table is the short form and must stay short: a world-map
        # spell that runs for two minutes is the bug this rule exists to prevent.
        spans = [float(m) for m in re.findall(r"span:\s*([0-9.]+)", src)]
        self.assertTrue(spans, "no beat spans found in unmakingfx.js")
        self.assertLess(sum(spans), 30.0,
                        f"world-map Unmaking grew to {sum(spans):.2f}s; it is "
                        "cast where the player is standing and must stay brief")

    def test_chamber_renderer_keeps_its_disambiguating_alias(self):
        src = CHAMBER.read_text()
        self.assertIn("THE UNMAKING", src)
        # Without this alias the two modules cannot be co-imported unqualified.
        self.assertIn("createUnmakingCinematic", src)


if __name__ == "__main__":
    unittest.main()
