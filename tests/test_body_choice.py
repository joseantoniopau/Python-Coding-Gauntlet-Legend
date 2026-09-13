"""You pick the body at the same door as the class, and it reaches the sprite.

THE GAP THIS CLOSES: web/js/sprites.js has carried BODY_RIG with two authored
bodies since the class work landed, and bodyKey() reads `body` — but nothing in
the save, the API or the UI ever set it, so it always answered 'a' and six of
the twelve authored sprites were unreachable from inside the game.

The axis is stored as 'a'/'b' rather than as a gender word because the rig is a
BUILD — a silhouette and a hem. The player picks it as male/female; what the
save keeps is which body was drawn.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import GameTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gauntlet import classes  # noqa: E402


class TestTheBodyIsChosenAndKept(unittest.TestCase):
    def test_both_bodies_exist_and_have_labels(self):
        self.assertEqual(("a", "b"), classes.BODIES)
        for key in classes.BODIES:
            self.assertIn(key, classes.BODY_LABEL)

    def test_an_old_save_defaults_rather_than_raising(self):
        """Every save written before this field existed lacks it."""
        self.assertEqual("a", classes.body_of({"class": {"class": "seer"}}))
        self.assertEqual("a", classes.body_of({}))
        self.assertEqual("a", classes.body_of({"class": None}))

    def test_an_unknown_body_takes_the_default(self):
        self.assertEqual("a", classes.body_of(
            {"class": {"class": "seer", "body": "zzz"}}))
        self.assertEqual("a", classes.new_state("seer", "zzz")["body"])


class TestTheBodyReachesTheSprite(GameTest):
    def test_the_choice_is_stored_and_shipped(self):
        g = self.game()
        g.choose_class("seer", "b")
        self.assertEqual("b", g.state["class"]["body"])
        # _hero_look is the ONLY sprite-options payload the client renders the
        # hero from, so if it is not here the choice is not in the game.
        self.assertEqual("b", g._hero_look()["body"])

    def test_it_survives_a_reload(self):
        g = self.game()
        g.choose_class("warden", "b")
        g.save()
        again = self.game()
        self.assertEqual("b", again._hero_look()["body"])

    def test_an_unchosen_class_still_has_a_body(self):
        """The generic hero is drawn too, and must not render bodyless."""
        g = self.game()
        self.assertEqual("a", g._hero_look()["body"])

    def test_a_client_that_sends_nothing_still_gets_a_character(self):
        g = self.game()
        out = g.choose_class("berserker")
        self.assertFalse(out.get("error"), out.get("error"))
        self.assertEqual("a", g._hero_look()["body"])


if __name__ == "__main__":
    unittest.main()
