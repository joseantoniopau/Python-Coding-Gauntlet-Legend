"""The dialogue engine, pinned.

Three things are load-bearing here and each one has a section below.

  THE ANSWER LINE   No authored string and no composed line may name a Python
                    construct. Elements, patterns, places and skills are the
                    vocabulary; a container or a callable is a HINT, and hints
                    belong to pets.py where they cost rank and are refused in a
                    measured run. This is the check that matters most, so it is
                    run over authored text AND over lines driven out of a live
                    composer, because a clean frame can still leak through a
                    slot.

  STALENESS         A speaker must not start repeating itself early. The floor
                    is measured against a FROZEN situation, which is the worst
                    case a player can construct, and it is asserted rather than
                    reported so that content added later cannot quietly lower
                    it. It has already done so once: see
                    test_deepening_a_pool_does_not_collapse_rotation.

  REWARDS RESOLVE   Every id a quest pays must exist in the module that owns it.
                    A quest that pays a metal that does not exist is worse than
                    a quest that pays gold.
"""
from __future__ import annotations

import re
import unittest

from base import GameTest

from gauntlet import banter, economy, elements, forge, items, potions
from gauntlet import quests, skills as skills_mod, story, world


# ==========================================================================
# 1 — THE ANSWER LINE
# ==========================================================================

class AnswerLine(GameTest):

    def test_guard_catches_the_shapes_it_claims_to(self):
        """The guard is only worth what it actually rejects."""
        for leak in ("use a dict for that", "wrap it in a set",
                     "from collections import Counter", "def solve(n):",
                     "return sorted(xs)", "a defaultdict keyed on the word",
                     "the answer is to memoise", "try enumerate(xs)",
                     "push it onto a Deque", "just paste this",
                     "if a == b", "xs[0] is the one you want"):
            self.assertTrue(banter.names_a_construct(leak),
                            f"guard missed a real leak: {leak!r}")

    def test_guard_permits_the_vocabulary_the_module_exists_to_speak(self):
        """Elements, patterns, places and skills must survive the guard, or the
        brief's whole advice layer would be unsayable."""
        for fine in ("bring something cold, the things here burn",
                     "the Wastes want the search that spreads in rings",
                     "Hashmap Highlands gives up keybrass",
                     "it wants keyed lookup, one name and one vault",
                     "the counter to fire is cold",
                     "that chapter measures whether you can say what a thing "
                     "costs"):
            self.assertEqual(banter.names_a_construct(fine), [],
                             f"guard rejected allowed vocabulary: {fine!r}")

    def test_every_authored_string_is_clean(self):
        bad = [(label, line) for label, line in banter._authored_text()
               if banter.names_a_construct(line)]
        self.assertEqual(bad, [], f"authored text names a construct: {bad[:5]}")

    def test_every_frame_is_clean(self):
        bad = []
        for register, beats in banter.FRAMES.items():
            for beat, pool in beats.items():
                for frame in pool:
                    found = banter.names_a_construct(frame)
                    if found:
                        bad.append((register, beat, found, frame))
        self.assertEqual(bad, [], f"a frame names a construct: {bad[:5]}")

    def test_no_composed_line_names_a_construct(self):
        """The one that actually matters: drive the composer over every speaker
        in every region and audit what comes out, because a frame can only leak
        a construct through a slot it was handed."""
        seen = 0
        bad = []
        for row in world.REGIONS:
            ctx = banter.context(region_id=row["id"])
            for sid in banter.speakers_in(row["id"]):
                state = banter.new_state()
                for _ in range(40):
                    for line in banter.speak(sid, ctx, state=state)["lines"]:
                        seen += 1
                        found = banter.names_a_construct(line, strict=False)
                        if found:
                            bad.append((row["id"], sid, found, line))
        self.assertEqual(bad, [], f"a composed line leaked: {bad[:3]}")
        # Guards the guard: if a refactor ever made `speak` return nothing this
        # test would pass vacuously. 47 speakers x 40 turns clears four thousand.
        self.assertGreater(seen, 4000, "the drive did not actually exercise much")

    def test_the_modules_own_audit_agrees(self):
        report = banter.self_check()
        self.assertTrue(report["ok"], report["problems"])

    def test_preparation_is_allowed_but_never_a_solution(self):
        """DEMAND is the table that talks about problems, so it is the one most
        able to cross the line. Every entry names a FAMILY and a SHAPE."""
        for skill, pool in banter.DEMAND.items():
            self.assertIn(skill, skills_mod.SKILLS, f"{skill} is not a skill")
            for line in pool:
                self.assertEqual(banter.names_a_construct(line), [],
                                 f"DEMAND[{skill}] names a construct: {line!r}")

    def test_nothing_works_in_a_measured_run(self):
        """One capability check, and it is finalexam.sealed."""
        sealed = banter.Ctx(sealed=frozenset(banter.BEATS))
        said = banter.speak("vess", sealed)
        self.assertTrue(said.get("sealed"))
        self.assertEqual(said.get("lines"), [])


# ==========================================================================
# 2 — THE PROSE IS ACTUALLY A SENTENCE
# ==========================================================================

class Prose(GameTest):
    """Composition defects that a string-level guard cannot see."""

    # Thirteen frames embed {gear} after a subordinator ("...tell you that
    # {gear}"), so a noun-phrase filling produces "tell you that slightly the
    # wrong metal." Four of the fifteen MISMATCH entries used to do exactly
    # that, on every register, in every elemental region.
    CLAUSE_OPENERS = frozenset({
        "you", "your", "yours", "nothing", "what", "it", "that", "they",
        "there", "half", "i", "the", "whoever",
    })

    def test_every_gear_filling_is_clause_shaped(self):
        bad = []
        for kind, pool in banter.MISMATCH.items():
            for i, line in enumerate(pool):
                first = line.split()[0].lower().strip(",.")
                if first not in self.CLAUSE_OPENERS:
                    bad.append((kind, i, line))
        self.assertEqual(bad, [],
                         "MISMATCH entries must open with a subject so they can "
                         f"follow 'that': {bad}")

    def test_gear_fillings_read_correctly_inside_every_frame(self):
        """Driven rather than reasoned about: build the sentence and look."""
        broken = []
        for register, beats in banter.FRAMES.items():
            for frame in beats[banter.GEAR]:
                if "{gear}" not in frame:
                    continue
                for kind, pool in banter.MISMATCH.items():
                    for filling in pool:
                        text = banter._sentence_case(
                            frame.format(gear=filling, counter="bring fire",
                                         boots="walk on"))
                        for stutter in (" that that ", " that a ",
                                        " that same ", " that slightly ",
                                        " that plain ", " because a ",
                                        " because same "):
                            if stutter in text.lower():
                                broken.append((register, stutter, text[:90]))
        self.assertEqual(broken, [], f"ungrammatical junction: {broken[:4]}")

    def test_no_text_defects_in_any_authored_string(self):
        """`"the best- " "connected thing"` concatenates to "best- connected".
        Grepping the source cannot see it because the defect is created by the
        adjacent-literal join, so it has to be checked on the joined value."""
        defects = [
            (re.compile(r"\w- \w"), "hyphen-space from a split literal"),
            (re.compile(r"  +"), "double space"),
            (re.compile(r"\s[.,]"), "space before punctuation"),
            (re.compile(r"!"), "exclamation mark (see TONE)"),
        ]
        bad = []
        pools = list(banter._authored_text())
        for register, beats in banter.FRAMES.items():
            for beat, pool in beats.items():
                pools += [(f"{register}:{beat}", f) for f in pool]
        for label, line in pools:
            clean = line
            for marker in banter._MARKERS:
                clean = clean.replace(marker, "")
            for pattern, why in defects:
                if pattern.search(clean):
                    bad.append((why, label, clean[:80]))
        self.assertEqual(bad, [], f"text defect: {bad[:5]}")

    def test_a_villager_never_sends_you_to_the_ground_you_stand_on(self):
        """WHERE names a place, and that place is very often the region the
        player is already in — the local shelf ALWAYS is. Travel frames and
        underfoot frames are tagged so only the true ones fire."""
        travel = re.compile(
            r"(go to|two days that way|not a purchase|it is fetched, from|"
            r"plan the trip|not going in there for it|have to go to)", re.I)
        underfoot = re.compile(r"this ground", re.I)
        bad = []
        for row in world.REGIONS:
            ctx = banter.context(region_id=row["id"])
            for sid in banter.speakers_in(row["id"]):
                state = banter.new_state()
                for _ in range(60):
                    said = banter.speak(sid, ctx, state=state)
                    for beat, line in zip(said["beats"], said["lines"]):
                        if beat != banter.WHERE:
                            continue
                        if travel.search(line) and row["name"] in line:
                            bad.append(("sent to here", row["id"], line[:90]))
                        if underfoot.search(line) and any(
                                r["name"] in line and r["id"] != row["id"]
                                for r in world.REGIONS):
                            bad.append(("underfoot elsewhere", row["id"],
                                        line[:90]))
        self.assertEqual(bad, [], f"locality violation: {bad[:4]}")

    def test_no_frame_marker_ever_reaches_a_player(self):
        for row in world.REGIONS:
            ctx = banter.context(region_id=row["id"])
            for sid in banter.speakers_in(row["id"]):
                state = banter.new_state()
                for _ in range(20):
                    for line in banter.speak(sid, ctx, state=state)["lines"]:
                        for marker in banter._MARKERS:
                            self.assertNotIn(marker, line)

    def test_every_register_can_speak_where_in_both_localities(self):
        for register in banter.REGISTER_IDS:
            for local in (True, False):
                pool = banter._frames_for(register, banter.WHERE, local=local)
                self.assertTrue(pool, f"{register} has no WHERE frame "
                                      f"for local={local}")


# ==========================================================================
# 3 — IT DOES NOT GO STALE
# ==========================================================================

class Staleness(GameTest):

    # Measured against a FROZEN situation, which no real session is: the region,
    # the loadout, the boss ahead and the quest log all move underneath these
    # frames in play. So this is a floor on the floor.
    FLOOR = 18

    def _frozen_capacity(self, sid):
        region = banter.speaker(sid).get("region", "")
        ctx = (banter.context(region_id=region) if region
               else banter.context())
        return banter.capacity(sid, ctx, limit=900)["distinct"]

    def test_no_speaker_repeats_before_the_floor(self):
        thin = []
        for sid in banter.SPEAKERS:
            distinct = self._frozen_capacity(sid)
            if distinct < self.FLOOR:
                thin.append((sid, distinct))
        self.assertEqual(thin, [],
                         f"speakers go stale below {self.FLOOR}: {thin}")

    def test_a_pool_hands_out_every_member_before_repeating_any(self):
        """The no-repeat-within-a-cycle guarantee, which the per-cycle
        reshuffle must not have broken."""
        for size in (2, 3, 4, 5, 6):
            pool = tuple(range(size))
            marks: list = []
            for cycle in range(4):
                got = [banter._pick(pool, pool_key="k", marks=marks,
                                    salt="who") for _ in range(size)]
                self.assertEqual(sorted(got), list(pool),
                                 f"size {size} cycle {cycle} repeated: {got}")

    def test_deepening_a_pool_does_not_collapse_rotation(self):
        """THE REGRESSION THAT MOTIVATES THE RESHUFFLE.

        Frames are authored five deep. With a fixed per-pool offset, every cycle
        traversed a pool in the same order, so any filling pool that also
        reached five locked step-for-step to the frames and the pair behaved
        like a single pool of five. Deepening the weather and hazard tables from
        three to five MEASURABLY cut the quietest speaker from 20 distinct
        remarks to 10. Two equal-length wheels must drift, not lock."""
        marks: list = []
        five_a = [banter._pick(tuple("abcde"), pool_key="a", marks=marks,
                               salt="s") for _ in range(25)]
        marks_b: list = []
        five_b = [banter._pick(tuple("abcde"), pool_key="b", marks=marks_b,
                               salt="s") for _ in range(25)]
        self.assertNotEqual(five_a, five_b,
                            "two equal-length wheels are in lockstep")
        # and a single wheel must not simply repeat one permutation for ever
        self.assertNotEqual(five_a[:5], five_a[5:10],
                            "a wheel repeats the same permutation every cycle")

    def test_rotation_is_stable_across_processes(self):
        """crc32, never hash(): a save written on Tuesday must read back the
        same on Wednesday."""
        def run():
            ctx = banter.context(region_id="graph_wastes")
            state = banter.new_state()
            return [" ".join(banter.speak("corvin", ctx, state=state)["lines"])
                    for _ in range(10)]
        self.assertEqual(run(), run())

    def test_banter_state_is_json_safe(self):
        import json
        ctx = banter.context(region_id="graph_wastes")
        state = banter.new_state()
        for _ in range(30):
            banter.speak("corvin", ctx, state=state)
        self.assertEqual(json.loads(json.dumps(state)), state)

    def test_scoring_a_beat_does_not_spend_it(self):
        """Five beats are scored and at most two are spoken. A filling burned on
        a beat nobody heard advanced every wheel by one every turn, which is
        what held the wheels in phase in the first place."""
        ctx = banter.context(region_id="graph_wastes")
        state = banter.new_state()
        said = banter.speak("corvin", ctx, state=state)
        marks = state["said"]["corvin"]
        picks = [m for m in marks if "#" in m]
        frame_picks = [m for m in picks if m.startswith("frame:")]
        self.assertEqual(len(frame_picks), len(said["lines"]),
                         "a frame was spent on a beat that was not spoken")


# ==========================================================================
# 4 — EVERY REWARD ID RESOLVES
# ==========================================================================

class Rewards(GameTest):
    """A quest that pays a metal that does not exist is worse than a quest that
    pays gold. Each id is checked against the module that OWNS it."""

    def test_every_material_reward_resolves(self):
        dangling = []
        for qid, row in quests._MATERIAL.items():
            if qid not in quests.QUEST_BY_ID:
                dangling.append((qid, "_MATERIAL names no such quest"))
                continue
            quest = quests.QUEST_BY_ID[qid]
            for key, value in row.items():
                if key == "potion":
                    if value[0] not in potions.BY_ID:
                        dangling.append((qid, f"potion {value[0]!r}"))
                elif key == "gear":
                    if value not in items.BY_ID:
                        dangling.append((qid, f"gear {value!r}"))
                elif key == "regalia":
                    if value not in quests.REGALIA:
                        dangling.append((qid, f"regalia {value!r}"))
                elif key == "metal":
                    metal = quests.metal_for(quest.region)
                    if not metal or metal not in forge.METAL_BY_ID:
                        dangling.append((qid, f"metal for {quest.region}"))
                elif key != "credit":
                    dangling.append((qid, f"unknown material key {key!r}"))
        self.assertEqual(dangling, [], f"dangling reward ids: {dangling}")

    def test_every_authored_reward_id_resolves(self):
        owners = {
            "card": story.GRIMOIRE_CARDS,
            "codex": story.CODEX,
            "pet": quests.PET_DISCOVERIES,
            "shortcut": quests.SHORTCUTS,
            "town_upgrade": quests.TOWN_UPGRADES,
            "incantation": quests.INCANTATION_GRANTS,
            "regalia": quests.REGALIA,
            "gear": items.BY_ID,
        }
        dangling = []
        for quest in quests.QUESTS:
            reward = quest.reward if isinstance(quest.reward, dict) else {}
            for key, value in reward.items():
                if key in owners and isinstance(value, str) and value:
                    if value not in owners[key]:
                        dangling.append((quest.id, key, value))
        self.assertEqual(dangling, [], f"dangling reward ids: {dangling}")

    def test_a_metal_reward_names_the_ground_it_came_out_of(self):
        for qid, row in quests._MATERIAL.items():
            if "metal" not in row:
                continue
            quest = quests.QUEST_BY_ID[qid]
            metal = forge.metal_for_region(quest.region)
            self.assertTrue(metal, f"{qid} pays metal in a region with none")
            self.assertEqual(quests.metal_for(quest.region), metal.id)

    def test_there_is_exactly_one_tack_roster_in_play(self):
        """quests.REGALIA is what quests pay and economy.py prices. Anything
        that shows the player a piece must show one from THAT roster, or it is
        advertising objects no quest grants and no vendor stocks."""
        for rid in quests.REGALIA:
            self.assertTrue(economy.regalia_price(rid),
                            f"{rid} is unpriced")
            self.assertTrue(
                economy.regalia_sold_at(quests.REGALIA[rid]["region"]),
                f"{rid} is sold nowhere")
        # and the dialogue layer must be pointed at the same roster
        for row in world.REGIONS:
            relic = banter.context(region_id=row["id"]).relic
            if relic:
                self.assertIn(relic, quests.REGALIA,
                              "banter names tack from the wrong roster")


# ==========================================================================
# 5 — REGALIA NEVER RAISES A TIER
# ==========================================================================

class NoSecondHintEconomy(GameTest):

    def test_regalia_buys_earlier_and_more_often_and_never_deeper(self):
        for rid, piece in quests.REGALIA.items():
            self.assertGreaterEqual(piece["threshold_scale"],
                                    quests.REGALIA_SCALE_FLOOR,
                                    f"{rid} lets a companion speak too early")
            self.assertLessEqual(piece["interventions"],
                                 quests.REGALIA_INTERVENTION_CAP,
                                 f"{rid} speaks too many times")
            for key in ("tier", "depth", "rank", "covers", "effects"):
                self.assertNotIn(key, piece,
                                 f"{rid} carries {key!r}, which is depth")

    def test_no_reward_key_grants_a_hint_effect(self):
        from gauntlet import pets
        for quest in quests.QUESTS:
            reward = quest.reward if isinstance(quest.reward, dict) else {}
            for key in reward:
                self.assertNotIn(key, pets.DEPTH_GATED_EFFECTS,
                                 f"{quest.id} grants a hint effect")

    def test_one_piece_at_a_time(self):
        from gauntlet import pets
        self.assertEqual(quests.REGALIA_ACTIVE_LIMIT, pets.ACTIVE_LIMIT)


# ==========================================================================
# 6 — LEARNING NEVER DEAD-ENDS
# ==========================================================================

class NeverSpeechless(GameTest):

    def test_every_speaker_has_something_true_to_say_everywhere(self):
        for row in world.REGIONS:
            ctx = banter.context(region_id=row["id"])
            for sid in banter.SPEAKERS:
                said = banter.speak(sid, ctx)
                self.assertTrue(said.get("lines"),
                                f"{sid} is speechless in {row['id']}")

    def test_neutral_ground_still_answers(self):
        neutral = [r["id"] for r in world.REGIONS
                   if elements.affinity_for(r["id"]) == elements.NEUTRAL]
        self.assertTrue(neutral)
        for region in neutral:
            ctx = banter.context(region_id=region)
            for sid in banter.speakers_in(region):
                self.assertTrue(banter.speak(sid, ctx)["lines"])


if __name__ == "__main__":
    unittest.main()
