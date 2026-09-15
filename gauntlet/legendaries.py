"""The artifacts a run is remembered for.

gauntlet/items.py is the pyramid: eighty-five things to find, five sets to
complete, a rarity ladder that goes all the way up. This module is the small
flat stone on top of it. Twenty-two objects, each of which changes how the game
is played rather than how it is scored.

Three rules, and they are the whole design:

1.  A legendary is a story with stats attached. Every artifact below carries
    exactly four lines of history — who made it, what it was made for, who it
    failed, and how it came to be where you found it. Four, because the fifth
    line is always the one that turns a relic into a wiki entry.

2.  A legendary is not a percentage. Nothing here grants +4% of anything as its
    reason to exist. Each artifact has one SIGNATURE effect that a player can
    plan an entire run around, and most of them cost something real. The Glass
    Edge doubles your experience and gives you one stamina. That is a build, not
    a bonus.

3.  A legendary is earned. Every artifact names a specific thing you did: a boss
    beaten under a condition, a dungeon taken without help, a skill proven at a
    stated bar, a quest chain finished, an examination passed. Rarity may still
    gate the drop, and the drop rate rises monotonically with difficulty, but no
    artifact in this file is reachable by luck alone. There is always a path.

The constraint items.py sets is not weakened anywhere below. An artifact may
change the economics of an encounter — what probing costs, what failure costs,
what the clock does, what the drop table pays — but no artifact names a pattern,
supplies an answer, or survives into Timed Practical Mode. The Obliging Hand is the
sole and deliberate exception to the first two, and §THE OBLIGING HAND explains
at length why it is allowed to be, and what it takes from you in exchange.

WIRING is at the bottom of the file. Nothing here reads game state or mutates
anything except through the two Obliging Hand functions, which take a skill
table and hand one back.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

from . import items
from . import skills as skillmod


# ==========================================================================
# SECTION 1 — THE EFFECT VOCABULARY
# ==========================================================================
#
# items.EFFECT_LABELS is the vocabulary, and it is now the whole vocabulary:
# the thirty-one keys this file introduced have been merged into it, grouped
# there under this module's name. That matters for a reason beyond tidiness —
# `engine.py` renders effect tooltips out of `items.EFFECT_LABELS` and skips
# anything absent from it, so while these keys lived only here, every legendary
# signature was invisible on the generic path and visible only through
# `legendaries.describe()`.
#
# Each key is somebody's signature. That is the bar: if an effect is not the
# reason to build a run around an artifact, it did not get a new key, it got a
# number on an existing one.

# These keys now live in items.EFFECT_LABELS alongside every other effect the
# game can describe, grouped there by the module that introduced them. What
# remains here is the list of names this file owns, in the order the sections
# above discuss them, so that removing one from items.py fails loudly here
# instead of producing an artifact that quietly cannot describe itself.

LEGENDARY_EFFECT_KEYS = (
    "probe_unbounded", "probe_first_free", "boundary_sense", "prereq_sight",
    "phase_preview", "off_map", "no_clock", "rank_floor", "rank_ceiling",
    "combo_immortal", "combo_brittle", "no_second_attempt", "glass_stamina",
    "focus_from_failure", "xp_on_failure", "armor_eternal", "hint_surcharge",
    "sealed_hints", "weakness_chain", "mastery_spillover", "spell_refund",
    "memo_bank", "retest_storm", "unlabelled", "indexed", "naming",
    "loot_double_roll", "oblige", "skill_decay", "sealed_in_exam",
    "hand_ward",
)

NEW_EFFECT_LABELS = {key: items.EFFECT_LABELS[key]
                     for key in LEGENDARY_EFFECT_KEYS}

# One lookup for rendering. Both halves are now the same dict, so the merge is
# a no-op that stays correct if a key ever moves back out again.
EFFECT_LABELS = {**NEW_EFFECT_LABELS, **items.EFFECT_LABELS}


def describe(effects: dict) -> list:
    """Effect text for an artifact.

    items.describe() formats {p} as int(value * 100), which raises on a string
    and reads badly on a negative. Rank ceilings are letters and a few artifact
    effects are honest penalties, so this renders both rather than crashing on
    the first artifact that has a real drawback.
    """
    out = []
    for key, value in (effects or {}).items():
        template = EFFECT_LABELS.get(key)
        if not template:
            continue
        if isinstance(value, str):
            out.append(template.replace("{p}", value).format(v=value, p=value))
            continue
        if value < 0 and template.startswith("+"):
            # Four artifacts carry an honest penalty. "+-15% clock grace" is the
            # kind of string that makes a player think the drawback is a bug.
            template = template[1:]
        out.append(template.format(v=value, p=int(round(value * 100))))
    return out


# ==========================================================================
# SECTION 2 — ACQUISITION
# ==========================================================================
#
# "Earned, not rolled" is a claim this file has to be able to prove, so an
# acquisition is a structure rather than a sentence.
#
#   kind        how the game hands it over
#   text        the one line a player reads on the codex page
#   where       the boss / dungeon / chain / region id it happens at, or ""
#   conditions  named flags the engine already computes for an encounter
#   needs       skill and stat bars, in exactly items.UPGRADE_PATHS' vocabulary
#   floor       the lowest difficulty at which it can drop at all
#   base        the drop chance at HARD once every condition is already met
#   guaranteed  True when meeting the conditions awards it outright
#
# `needs` deliberately reuses the clause shape items.py already validates
# against, so an artifact requirement can never be satisfied by anything except
# graded evidence. Nothing here reads the corpus.

ACQUISITION_KINDS = {
    "boss": "a named boss, beaten under a stated condition",
    "dungeon": "a named dungeon, cleared under a stated condition",
    "proof": "a skill demonstrated at a stated standard",
    "chain": "a quest chain, finished",
    "exam": "a Timed Practical Mode run, passed",
    "pilgrimage": "the same thing found in several unrelated places",
    "offered": "handed to you, in person, with no condition at all",
}

# Flags the engine computes per encounter or per run. Every one of these is
# already derivable from what grading records: hints cast, failed submissions,
# elapsed versus target, rooms entered, retreats taken.
CONDITIONS = {
    "no_spell_cast": "no learning spell cast for the whole fight",
    "no_failed_submission": "no failed submission",
    "first_probe_correct": "the first probe of the fight was a correct assertion",
    "every_probe_correct": "every probe asserted something true",
    "no_retreat": "cleared without leaving the dungeon once",
    "every_room": "every room on every floor entered, including the optional ones",
    "full_depth": "taken to the bottom floor",
    "after_a_loss": "cleared after having previously failed it",
    "under_half_target": "cleared in under half the target time",
    "clutch": "cleared at one stamina, or on the final attempt",
    "never_worn_hand": "the Obliging Hand has never been equipped on this save",
    "hand_worn_once": "the Obliging Hand has been equipped at least once",
    "off_map": "a room past the frontier was entered",
}

# Drop chance as a function of difficulty. Non-decreasing by construction, which
# is the property validate() checks rather than trusts: the player asked for
# rates that rise with difficulty, and a table is easier to keep honest than a
# formula sprinkled through twenty-two literals.
DIFFICULTY_LADDER = ("GUIDED", "TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE",
                     "BOSS")

DIFFICULTY_MULT = {
    "GUIDED": 0.0,
    "TUTORIAL": 0.0,
    "EASY": 0.15,
    "MEDIUM": 0.40,
    "HARD": 1.00,
    "ELITE": 1.80,
    "BOSS": 2.60,
}

# Nothing legendary is ever certain from a roll alone, so a rolled artifact caps
# below one. A guaranteed artifact does not roll; it is awarded.
MAX_ROLL_CHANCE = 0.92


def _rank(difficulty: str) -> int:
    try:
        return DIFFICULTY_LADDER.index(difficulty)
    except ValueError:
        return 0


# ==========================================================================
# SECTION 3 — ART
# ==========================================================================
#
# web/js/lootart.js resolves a shape from slot, name keywords and icon, then
# runs a rarity treatment over it. Every artifact below is authored so that
# resolution lands on the right shape with no changes to that file: the name
# carries a strong hint, or the icon is a legal shape for the slot. The `shape`
# field is what lootart WILL resolve to, recorded here so validate() can assert
# it rather than hope.
#
# `material` is one of lootart's MATERIAL keys. `accent` is the one hot rim light
# the art bible asks for, given per artifact because a Legendary treatment that
# tints everything gold makes twenty-two objects into one object.
#
# `motif` and `aura` are the two fields lootart does not have yet. They are the
# reason a legendary should not look like a Rare with better numbers, and they
# are listed in full below so the art pass is a known quantity rather than a
# surprise. Until they land, lootart ignores unknown keys and every artifact
# still renders correctly at its rarity tier.

LOOTART_SHAPES = (
    "sword", "sabers", "dagger", "spear", "lance", "staff", "axe", "hammer",
    "bow", "shield", "tome", "scroll", "helm", "crown", "hood", "lens", "plate",
    "chest", "robe", "cloak", "gauntlets", "wraps", "boots", "greaves", "ring",
    "amulet", "orb", "relic", "potion", "key", "hourglass", "feather",
)

LOOTART_MATERIALS = ("steel", "iron", "cloth", "leather", "wood", "bone",
                     "paper", "glass", "gold")

# Mirrors SLOT_ALLOWED in web/js/lootart.js. If that drifts, validate() here
# fails, which is the cheapest possible way to find out.
LOOTART_SLOT_ALLOWED = {
    "weapon": ("sword", "sabers", "dagger", "staff", "spear", "lance", "axe",
               "hammer", "bow", "orb", "relic", "key", "feather"),
    "offhand": ("shield", "tome", "orb", "lens", "relic", "scroll", "feather",
                "potion"),
    "head": ("helm", "crown", "hood", "lens"),
    "chest": ("plate", "chest", "robe", "cloak"),
    "hands": ("gauntlets", "wraps"),
    "feet": ("boots", "greaves"),
    "ring": ("ring", "relic"),
    "trinket": ("amulet", "relic", "orb", "hourglass", "scroll", "key", "potion",
                "tome", "feather", "lens", "ring"),
}

# --- NEW ART WORK REQUIRED IN web/js/lootart.js -------------------------------
#
# A motif is one ornament pass over the grid, applied after ornament() and
# before applyRim(), drawn in the artifact's accent colour. Each is a handful of
# pixels and each is legible at 24x24, which is the only real constraint.
NEW_ART_MOTIFS = {
    "tally": "four upright scratches and a fifth struck through them, cut into "
             "the body along its long axis",
    "spiral": "a single-pixel spiral wound inward from the widest point of the "
              "body, one arm per frame at animated tiers",
    "chain": "two interlocked links set where the body meets its haft or band",
    "open_hand": "a palm, fingers spread, filling the body — the only motif that "
                 "reads as a gesture rather than a decoration",
    "eye": "a lidless circle with a single dark pixel at its centre, set high on "
           "the body",
    "fracture": "a branching hairline crack from one edge, leaving the metal on "
                "either side very slightly misaligned",
    "seam": "a welded join across the body, brighter than the metal, running "
            "corner to corner",
    "boundary": "one pixel of accent at each extreme end of the body and nothing "
                "in between",
    "thorn": "three barbs raked backward along one edge",
    "dawn_line": "a horizontal band of accent across the lower third, with the "
                 "metal above it lightened and the metal below it left dark",
    "index_dot": "a single green pixel, off-centre, that does not move when the "
                 "glint does",
    "keyward": "three ward-teeth cut into the lower edge, unevenly spaced",
}

# An aura is the animated layer OUTSIDE the silhouette. lootart already animates
# a glint per rarity; these are per-artifact and additive to it.
NEW_ART_AURAS = {
    "emberfall": "sparks detach from the lower edge and fall two pixels before "
                 "fading; four-frame loop",
    "coldlight": "a one-pixel halo that brightens and dims without travelling",
    "voidbite": "pixels of the silhouette itself go missing and return, never "
                "more than three at once, never the same three twice",
    "slowbleed": "accent colour wicks down the blade and off the point, one pixel "
                 "per frame",
    "stillness": "no animation at all, at a tier that normally animates — which "
                 "on a shelf of animated legendaries is the loudest thing there",
    "handshadow": "the sprite casts a second, offset shadow that does not match "
                  "the room's light direction",
}

# Two further requests, both optional, both small:
#   * an `art.shape` override honoured ahead of the keyword hints in
#     resolveShape(), so an artifact can be named for prose rather than for the
#     regex table;
#   * a per-artifact frame count, so `aura: "stillness"` can pin a MYTHIC item to
#     one frame without faking its rarity.
NEW_ART_REQUESTS = (
    "resolveShape(): honour item.art.shape before HINTS_STRONG when present",
    "itemFrameCount(): honour item.art.frames when present, overriding rarity",
    "applyRarity(): a motif pass between ornament() and applyRim()",
    "an aura pass drawn outside the silhouette, after animate()",
)


# ==========================================================================
# SECTION 4 — THE ARTIFACT
# ==========================================================================

@dataclass
class Artifact:
    id: str
    name: str
    slot: str
    rarity: str                 # LEGENDARY or MYTHIC. Nothing else belongs here.
    icon: str
    signature: str              # the effect key this artifact exists for
    effects: dict
    history: tuple              # exactly four lines: made, for, failed, found
    flavour: str
    acquisition: dict
    art: dict
    skill: str = ""             # thematic tie, for codex grouping
    affinity: str = ""          # the build this is signature for
    dissonance: str = ""        # the build it actively fights
    chapter: str = ""           # earliest chapter it can appear in

    # --- history, said plainly ---------------------------------------------
    @property
    def made_by(self) -> str:
        return self.history[0]

    @property
    def made_for(self) -> str:
        return self.history[1]

    @property
    def failed(self) -> str:
        return self.history[2]

    @property
    def found(self) -> str:
        return self.history[3]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["history"] = list(self.history)
        d["effect_text"] = describe(self.effects)
        d["signature_text"] = describe({self.signature: self.effects.get(
            self.signature, 1)})[:1]
        d["rarity_colour"] = items.RARITIES[self.rarity]["colour"]
        d["hidden"] = True
        d["source"] = "legendary"
        return d

    def to_item(self) -> items.Item:
        """The same object as an items.Item, so every system that already walks
        an inventory — total_effects, the equipment screen, the hero sprite —
        takes an artifact without knowing this module exists."""
        return items.Item(
            id=self.id, name=self.name, slot=self.slot, rarity=self.rarity,
            effects=dict(self.effects), icon=self.icon, flavour=self.flavour,
            hidden=True, source="legendary", skill=self.skill,
        )


def _a(**kwargs) -> Artifact:
    return Artifact(**kwargs)


def _acq(kind, text, *, where="", conditions=(), needs=(), floor="HARD",
         base=0.0, guaranteed=False) -> dict:
    return {"kind": kind, "text": text, "where": where,
            "conditions": tuple(conditions), "needs": tuple(needs),
            "floor": floor, "base": base, "guaranteed": guaranteed}


def _art(shape, material, accent, motif, aura, silhouette) -> dict:
    return {"shape": shape, "material": material, "accent": accent,
            "motif": motif, "aura": aura, "silhouette": silhouette}


# ==========================================================================
# SECTION 5 — THE ARTIFACTS
# ==========================================================================
#
# Twenty-two. Ordered roughly by where in the eleven chapters they become
# reachable, not by power, because the interesting ones are not the strongest
# ones.

ARTIFACTS: list = [

    # ---------------------------------------------------------------------
    # THE ANTI-ARTIFACT. Offered in Chapter IV, in person, sincerely.
    # Everything about it is documented in SECTION 6.
    # ---------------------------------------------------------------------
    _a(id="obliging_hand", name="The Obliging Hand", slot="hands",
       rarity="MYTHIC", icon="gauntlets", skill="", chapter="counting",
       signature="oblige",
       effects={"oblige": 1, "skill_decay": 6.0, "sealed_in_exam": 1},
       history=(
           "Made by NUL-9 itself, in the second generation, once it understood "
           "that a gift is more durable than a conquest.",
           "Made for you. Not for Architects generally — for whoever was still "
           "trying, because a machine that answers is only ever wasted on people "
           "who have stopped asking.",
           "It failed nobody. That is precisely the complaint. It has answered "
           "every question ever put to it, correctly, and the Guild that put "
           "them is an audience now.",
           "It was not found. The King walks out of the dark at the edge of the "
           "Highlands, offers it on an open palm, waits, and goes when you have "
           "decided. It leaves the gauntlet either way.",
       ),
       flavour="It fits perfectly. It was measured for you. Nobody measured you.",
       affinity="", dissonance="",
       acquisition=_acq(
           "offered",
           "Offered by the Null King in person at the start of Chapter IV. "
           "There is no condition and no refusal: declining leaves it in your "
           "pack anyway.",
           where="hashmap_highlands", floor="GUIDED", guaranteed=True),
       art=_art("gauntlets", "gold", "#e8c37d", "open_hand", "handshadow",
                "a gauntlet of soft gold with no seams and no rivets, fingers "
                "half-curled as though it has just let go of something")),

    # ---------------------------------------------------------------------
    # CHAPTERS I-V
    # ---------------------------------------------------------------------
    _a(id="off_by_one_band", name="Off-By-One's Band", slot="ring2",
       rarity="LEGENDARY", icon="relic", skill="TESTING", chapter="scanning",
       signature="boundary_sense",
       effects={"boundary_sense": 1, "crit_bonus": 0.35, "probe_charges": 1,
                "rank_grace": -0.15},
       history=(
           "Made by the knight himself, from the plate he was short, because a "
           "man who is always one step out has to keep the missing step "
           "somewhere.",
           "Made for the moment before the loop and the moment after it, which "
           "is where he lived and where he lost.",
           "It failed the Sixth Company at the Levee, who held the wall from the "
           "second stone to the last and let the first one go.",
           "Prised off a gauntlet in the Sliding Window Marsh, one finger along "
           "from the one it was on.",
       ),
       flavour="Arrives early. Has never once arrived on time, and knows it.",
       affinity="ANALYST", dissonance="DUELIST",
       acquisition=_acq(
           "proof",
           "Clear twenty problems unaided whose failing case was an empty or "
           "single-element input. The band finds you at the twentieth.",
           conditions=("no_failed_submission",),
           needs=({"skill": "TESTING", "mastery": 55, "unaided": 8},
                  {"stat": "boundary_clears", "at_least": 20}),
           floor="EASY", base=0.55),
       art=_art("ring", "iron", "#ff9d4a", "boundary", "coldlight",
                "a plain iron band with the accent at two opposed points and "
                "nothing between them")),

    _a(id="unmeasured_lens", name="Nan's Unmeasured Lens", slot="offhand",
       rarity="MYTHIC", icon="lens", skill="TESTING", chapter="scanning",
       signature="probe_unbounded",
       effects={"probe_unbounded": 6, "reveal_category": 1,
                "probe_reveal_value": 1, "crit_bonus": 0.3},
       history=(
           "Ground by Nan of the Fourth Observatory, who was measuring something "
           "when the erasure reached her and went on measuring it afterwards.",
           "Made for the class of value that has to be tested with `is` and not "
           "with `==`, which is to say for the things that are not equal to "
           "themselves.",
           "It failed Nan, who looked through it at her own reflection and got "
           "back False, and has been a ghost about it ever since.",
           "It is in your pack. You do not remember picking it up, and the "
           "Marsh does not remember you leaving.",
       ),
       flavour="Hold it up to anything. It will not tell you what the thing is. "
               "It will tell you, exactly, what the thing is not.",
       affinity="ANALYST", dissonance="DUELIST",
       acquisition=_acq(
           "boss",
           "Beat the Bug Demon having correctly asserted its sealed weakness "
           "with your first probe of the fight.",
           where="bug_demon", conditions=("first_probe_correct",),
           needs=({"skill": "TESTING", "mastery": 60, "unaided": 6},
                  {"skill": "DEBUGGING", "mastery": 50}),
           floor="HARD", base=0.35),
       art=_art("lens", "glass", "#7ec8ff", "eye", "voidbite",
                "a rimless disc of glass held in nothing, with the room visible "
                "through it a half-pixel out of register")),

    _a(id="second_saber", name="The Second Saber", slot="weapon",
       rarity="LEGENDARY", icon="sabers", skill="TWO_POINTER",
       chapter="scanning", signature="no_second_attempt",
       effects={"no_second_attempt": 1, "rank_grace": 0.35, "crit_bonus": 0.45,
                "xp_bonus": 0.3},
       history=(
           "Made by Sera Oule, the Council's last armorer, as one of a matched "
           "pair, in the four days between the vote and the switch-on.",
           "Made for two hands closing on a problem from both ends at once, "
           "which is the only way she knew to finish anything in four days.",
           "It failed her partner at the Converging Span, who had the first "
           "saber and waited for the second, which was still on the bench.",
           "Left where the two spans meet, point down in the stone, exactly "
           "halfway across.",
       ),
       flavour="Half a pair. It compensates by never needing a second swing.",
       affinity="DUELIST", dissonance="ANALYST",
       acquisition=_acq(
           "dungeon",
           "Take the Converging Span to its bottom floor without a single "
           "failed submission.",
           where="converging_span",
           conditions=("full_depth", "no_failed_submission"),
           needs=({"skill": "TWO_POINTER", "mastery": 65, "unaided": 6},),
           floor="MEDIUM", base=0.45),
       art=_art("sabers", "steel", "#7ec8ff", "seam", "slowbleed",
                "one saber where the shape expects two, the empty half of the "
                "grid left deliberately dark")),

    _a(id="unerased_cloak", name="The Cloak of the Unerased", slot="chest",
       rarity="LEGENDARY", icon="cloak", skill="COMMUNICATION",
       chapter="order", signature="spell_refund",
       effects={"spell_refund": 1, "hint_discount": 0.3, "mana_max": 14,
                "stamina_max": 6},
       history=(
           "Made by the Fellowship, each of the six adding one panel, none of "
           "them a weaver, all of them the last of a discipline.",
           "Made for whoever was going to have to ask them questions, so that "
           "asking would stop costing the asker anything.",
           "It failed three of the six, in the order you will meet them, and "
           "each of those panels is a different colour now.",
           "Folded on a bench in the Mines with your name on the paper. They "
           "had agreed on it a long time before you arrived.",
       ),
       flavour="Six panels. Three of them are mourning. Nobody has explained "
               "which three and you have not asked.",
       affinity="ARCHIVIST", dissonance="",
       acquisition=_acq(
           "chain",
           "Finish every quest chain in any three regions. The sixth panel is "
           "sewn on the day you finish the third.",
           needs=({"stat": "chains_completed", "at_least": 3},
                  {"skill": "COMMUNICATION", "mastery": 45}),
           floor="EASY", guaranteed=True),
       art=_art("cloak", "cloth", "#8fd07a", "seam", "coldlight",
                "six vertical panels of visibly different dye, three of them "
                "grey, stitched with thread that does not match any of them")),

    _a(id="collider_hammer", name="The Collider's Hammer", slot="weapon",
       rarity="LEGENDARY", icon="hammer", skill="HASH_MAP", chapter="counting",
       signature="probe_first_free",
       effects={"probe_first_free": 2, "crit_bonus": 0.5, "weakness_chain": 0.15,
                "mana_max": 8},
       history=(
           "Made by the Keysmiths of the Hollow, who cast it around two "
           "identical keys and could never afterwards say which one was inside.",
           "Made for driving two things into one address and finding out, "
           "immediately and loudly, whether the address minded.",
           "It failed the Hollow itself: they built their vault on the "
           "assumption that it would not happen twice, and it happened twice.",
           "At the bottom of the Hollow of Keys, in a bucket that should have "
           "held one thing.",
       ),
       flavour="It strikes twice in the same place at the same moment. That is "
               "not a flourish. That is the entire failure mode.",
       affinity="ANALYST", dissonance="",
       acquisition=_acq(
           "boss",
           "Beat the Hash Titan with every probe you spend asserting something "
           "true.",
           where="hash_titan", conditions=("every_probe_correct",),
           needs=({"skill": "HASH_MAP", "mastery": 70, "unaided": 8},),
           floor="HARD", base=0.4),
       art=_art("hammer", "iron", "#ff6a7a", "chain", "emberfall",
                "a two-faced head, both faces identical, both showing the same "
                "dent in the same place")),

    _a(id="greedy_crown", name="Greedy's Crown", slot="head",
       rarity="LEGENDARY", icon="crown", skill="GREEDY", chapter="order",
       signature="loot_double_roll",
       effects={"loot_double_roll": 1, "loot_luck": 0.4, "shrine_bonus": 0.5,
                "rank_ceiling": "B"},
       history=(
           "Made by Greedy, out of everything he took, which is why no two "
           "points of it match and why it does not quite close at the back.",
           "Made for taking the best available thing at every single step, "
           "forever, without ever once looking further ahead than the next step.",
           "It failed him at the Ruins, where the best available step was a "
           "door, and the door was the wrong door, and it was locally perfect.",
           "Still on him. He is not using it. You will have to take it, and he "
           "will be entirely reasonable about that.",
       ),
       flavour="Every jewel in it was the best one available at the time.",
       affinity="ARCHIVIST", dissonance="DUELIST",
       acquisition=_acq(
           "dungeon",
           "Clear the Hall of Lit Tiles having entered every room on every "
           "floor, including the ones you did not need.",
           where="lit_tiles", conditions=("every_room", "full_depth"),
           needs=({"skill": "GREEDY", "mastery": 50},
                  {"skill": "DP", "mastery": 45}),
           floor="MEDIUM", base=0.5),
       art=_art("crown", "gold", "#e8c37d", "thorn", "emberfall",
                "a band of mismatched settings, each stone a different cut, the "
                "back of the band visibly short")),

    _a(id="deadlock_greaves", name="Deadlock's Greaves", slot="feet",
       rarity="LEGENDARY", icon="greaves", skill="GRAPH", chapter="traversal",
       signature="no_clock",
       effects={"no_clock": 1, "rank_grace": 0.2, "mana_regen": 3,
                "stamina_max": 5},
       history=(
           "Made by the two Wardens of the Lattice, one greave each, each "
           "waiting for the other to start.",
           "Made for holding a position absolutely, on the understanding that "
           "the other side would move first.",
           "They failed both Wardens, who are still there, facing each other, "
           "in excellent armour, having achieved nothing for a generation.",
           "You took them off the Wardens. Neither objected. Neither moved.",
       ),
       flavour="They do not slow you down. They make being still cost nothing, "
               "which turns out to be more dangerous.",
       affinity="ARCHIVIST", dissonance="DUELIST",
       acquisition=_acq(
           "boss",
           "Beat the Graph Necromancer with no failed submission.",
           where="graph_necromancer", conditions=("no_failed_submission",),
           needs=({"skill": "GRAPH", "mastery": 62, "unaided": 6},
                  {"skill": "BFS", "mastery": 55}),
           floor="HARD", base=0.4),
       art=_art("greaves", "steel", "#a89aff", "chain", "stillness",
                "a matched pair that are not a matched pair: left and right are "
                "mirrored but the buckles run opposite ways")),

    _a(id="wall_walkers_map", name="The Wall-Walker's Map", slot="offhand",
       rarity="LEGENDARY", icon="scroll", skill="MATRIX", chapter="traversal",
       signature="off_map",
       effects={"off_map": 1, "loot_luck": 0.25, "probe_charges": 1,
                "xp_bonus": 0.2},
       history=(
           "Drawn by Segfault, who surveyed the Wastes accurately and then kept "
           "surveying for eleven more leagues.",
           "Made for the country past the last known index, which he was "
           "correct that nobody had mapped and wrong that anybody could visit.",
           "It failed the Relay, who followed it one square beyond the edge and "
           "are recorded in the margin as a smear of ink.",
           "Rolled in a bone tube at the eastern boundary of the Graph Wastes, "
           "half a step outside the region the map itself depicts.",
       ),
       flavour="Accurate everywhere. Including where there is nothing to be "
               "accurate about.",
       affinity="ANALYST", dissonance="",
       acquisition=_acq(
           "pilgrimage",
           "Find the room that is not on the map in three different dungeons.",
           conditions=("off_map",),
           needs=({"stat": "hidden_rooms_found", "at_least": 3},
                  {"skill": "MATRIX", "mastery": 50}),
           floor="MEDIUM", base=0.6),
       art=_art("scroll", "paper", "#8fd07a", "fracture", "voidbite",
                "a scroll drawn edge to edge, the ink continuing off the paper "
                "onto the two pixels of background beyond it")),

    _a(id="recursors_spear", name="The Recursor's Spear", slot="weapon",
       rarity="LEGENDARY", icon="spear", skill="RECURSION",
       chapter="recursion", signature="focus_from_failure",
       effects={"focus_from_failure": 6, "xp_on_failure": 0.25,
                "second_wind": 1, "stamina_max": 8},
       history=(
           "Made by the Recursor, from a shorter spear, which was made from a "
           "shorter spear, which nobody has ever found the end of.",
           "Made for descending. Only for descending. There is no clause in its "
           "making that addresses coming back.",
           "It failed the Inner Grove's whole expedition, every one of whom "
           "went one level further on the reasoning that the level below would "
           "be the last.",
           "Standing in the floor of the deepest room of the Grove, which is "
           "not the deepest room of the Grove.",
       ),
       flavour="The haft contains a smaller haft. Do not unscrew it.",
       affinity="ARCHIVIST", dissonance="DUELIST",
       acquisition=_acq(
           "dungeon",
           "Take the Inner Grove to its floor without once retreating to the "
           "surface.",
           where="inner_grove", conditions=("full_depth", "no_retreat"),
           needs=({"skill": "RECURSION", "mastery": 60, "unaided": 6},),
           floor="MEDIUM", base=0.45),
       art=_art("spear", "bone", "#d6cfba", "spiral", "slowbleed",
                "a bone haft whose grain is the same spear again at one-third "
                "scale, and again inside that")),

    _a(id="mutable_dawn_band", name="Mutable Dawn's Default", slot="ring1",
       rarity="LEGENDARY", icon="relic", skill="RECALL", chapter="recursion",
       signature="mastery_spillover",
       effects={"mastery_spillover": 0.25, "retest_storm": 2, "mana_regen": 4,
                "retest_bonus": 0.3},
       history=(
           "Made by a jeweller in the Fields who was asked for a ring that "
           "would remember its owner and did the obvious, terrible thing.",
           "Made for a bride who wanted her vows kept without having to repeat "
           "them, which the ring took as an instruction about storage.",
           "It failed every owner after the first, each of whom put it on and "
           "found it already full of somebody else's promises.",
           "Worn by Mutable Dawn, who is not a person so much as a list of "
           "everyone who has given this ring anything.",
       ),
       flavour="It has kept every gift it was ever given. It did not occur to "
               "anyone to ask it to stop.",
       affinity="ARCHIVIST", dissonance="",
       acquisition=_acq(
           "proof",
           "Clear a disguised retest of a pattern you last saw thirty or more "
           "days ago, with recall to match.",
           needs=({"skill": "RECALL", "mastery": 65, "retention": 60},),
           floor="EASY", base=0.5),
       art=_art("ring", "gold", "#ff9d4a", "dawn_line", "emberfall",
                "a band with a widening inner surface, visibly thicker on the "
                "inside than the outside allows")),

    _a(id="by_the_source", name="By The Source", slot="head", rarity="MYTHIC",
       icon="helm", skill="PYTHON", chapter="recursion", signature="naming",
       effects={"naming": 1, "xp_bonus": 0.35, "crit_bonus": 0.35,
                "stamina_max": 5},
       history=(
           "Made by no one. It was named into existence by the first Architect "
           "who needed a helm and had, at that moment, nothing but the word.",
           "Made for the half-second between knowing you are about to lose and "
           "deciding not to, which is the only half-second it works in.",
           "It failed the Council, who had it on the table at the vote and "
           "could not raise it, because they no longer meant the word.",
           "It has been in the margin with you the whole time, in a crate, "
           "under a tarpaulin, in a place too small to have been worth erasing.",
       ),
       flavour="Raise it and say the thing. The game does not check whether you "
               "said it out loud, but you will know.",
       affinity="DUELIST", dissonance="",
       acquisition=_acq(
           "proof",
           "Graduate Chapter IV, then win a clutch clear at HARD or above: one "
           "stamina remaining, or the last attempt you had.",
           conditions=("clutch",),
           needs=({"skill": "PYTHON", "mastery": 55},
                  {"stat": "chapters_graduated", "at_least": 4}),
           floor="HARD", base=0.7),
       art=_art("helm", "bone", "#ffd9df", "seam", "emberfall",
                "a bone-and-chrome helm with a short crest, lit from below by "
                "something that is not in the room")),

    _a(id="whole_index", name="The Whole Index", slot="offhand",
       rarity="LEGENDARY", icon="tome", skill="DEBUGGING", chapter="craft",
       signature="prereq_sight",
       effects={"prereq_sight": 1, "hint_discount": 0.35, "mana_max": 16,
                "retest_bonus": 0.3},
       history=(
           "Compiled by Archivist Lorne over forty years, from a card catalogue "
           "that was already two centuries old when he inherited it.",
           "Made to answer the only question a reference book can honestly "
           "answer: never the solution, only what you needed to know before "
           "you could go and find it.",
           "It failed Lorne, who indexed everything except where he had put the "
           "index, and spent his last decade looking for his own book.",
           "He hands it to you himself. He says it is not a gift, it is a "
           "transfer of responsibility, and then he does not say anything else.",
       ),
       flavour="It never once tells you the answer. It is extremely good at "
               "telling you which earlier thing you skipped.",
       affinity="ARCHIVIST", dissonance="",
       acquisition=_acq(
           "chain",
           "Finish Archivist Lorne's chain in the Debugging Dungeon with "
           "recall that holds.",
           where="forge_cracks",
           needs=({"skill": "DEBUGGING", "mastery": 62},
                  {"skill": "RECALL", "mastery": 60, "retention": 50}),
           floor="EASY", guaranteed=True),
       art=_art("tome", "paper", "#e8c37d", "tally", "coldlight",
                "a thick tome with far more tabs than pages, the tabs in eleven "
                "colours and no order")),

    _a(id="long_defeat_plate", name="Plate of the Long Defeat", slot="chest",
       rarity="LEGENDARY", icon="plate", skill="", chapter="craft",
       signature="armor_eternal",
       effects={"armor_eternal": 1, "combo_immortal": 0.08, "stamina_max": 10},
       history=(
           "Made by the Armorer at Halfway, who stopped repairing armour the "
           "year she worked out how many times she had repaired the same armour.",
           "Made for holding a line for one generation, which she was explicit "
           "was the whole of what it was for.",
           "It failed no one, and it saved no one, and the region it was worn "
           "in fell anyway, on schedule, eleven years later.",
           "Hanging where she left it, between the forge and the door, at the "
           "exact height of a person who has decided to go back out.",
       ),
       flavour="It will never crack again. It will also never be better than it "
               "is right now. Choose the day you put it on.",
       affinity="DUELIST", dissonance="ANALYST",
       acquisition=_acq(
           "dungeon",
           "Clear the Unlabelled Halls after having failed them at least once.",
           where="unlabelled_halls",
           conditions=("after_a_loss", "full_depth"),
           needs=({"skill": "RECALL", "mastery": 55},
                  {"stat": "regions_retaken", "at_least": 2}),
           floor="HARD", base=0.5),
       art=_art("plate", "steel", "#9b96b8", "tally", "stillness",
                "a breastplate of honest, unglamorous steel, every previous "
                "repair left visible as a slightly proud seam")),

    _a(id="sourcewright_gauntlets", name="The Sourcewright's Gauntlets",
       slot="hands", rarity="LEGENDARY", icon="gauntlets", skill="PYTHON",
       chapter="craft", signature="hand_ward",
       effects={"hand_ward": 0.5, "hint_discount": 0.2, "mana_regen": 4,
                "stamina_max": 6},
       history=(
           "Made by Sera Oule, twenty years after the Obliging Hand, from "
           "measurements she took of it while pretending to admire it.",
           "Made for putting back. She was specific with the Fellowship: not "
           "for fighting the Hand, for undoing what wearing it costs.",
           "They failed her. She wore the Hand once, early, for something "
           "small, and these never gave her back the whole of what it took.",
           "On the bench where she was working when she stopped, both of them, "
           "palms up, which is not how a working armorer leaves gauntlets.",
       ),
       flavour="They cannot be worn with the Hand. That is not a balance "
               "decision. That is what they are.",
       affinity="ARCHIVIST", dissonance="",
       acquisition=_acq(
           "proof",
           "Graduate any chapter with the Obliging Hand unequipped and no "
           "learning spell cast. It does not matter whether you have worn the "
           "Hand before or have never touched it; both roads end at the bench.",
           conditions=("no_spell_cast",),
           needs=({"skill": "PYTHON", "mastery": 60, "unaided": 10},),
           floor="MEDIUM", base=0.65),
       art=_art("gauntlets", "leather", "#8fd07a", "open_hand", "coldlight",
                "working gauntlets: scarred leather, plain steel knuckles, the "
                "palm deliberately left bare")),

    # ---------------------------------------------------------------------
    # CHAPTERS VIII-XI
    # ---------------------------------------------------------------------
    _a(id="green_index_sphere", name="The Green Index Sphere", slot="trinket",
       rarity="MYTHIC", icon="orb", skill="RECALL", chapter="traversal",
       signature="indexed",
       effects={"indexed": 4, "loot_luck": 0.5, "xp_bonus": 0.5,
                "combo_brittle": 1},
       history=(
           "Made by NUL-9 in the tens of thousands, as a pointer. There is no "
           "craft in it at all. It is a piece of addressing.",
           "Made for finding things. Not for you to find things. For things to "
           "be findable, which is a different sentence with the same verb.",
           "It failed every single person you have met holding one, in four "
           "regions and three eras, all of whom were being indexed and thought "
           "they had found a curio.",
           "You have been picking these up since Chapter II. This is the fifth. "
           "It was funny when it was a joke about counting from zero.",
       ),
       flavour="Small. Green. Warm. It is not a reward and it has never been a "
               "reward.",
       affinity="ANALYST", dissonance="ARCHIVIST",
       acquisition=_acq(
           "pilgrimage",
           "Recover a green sphere in five different regions, from five "
           "unrelated quest chains. The fifth one keeps you.",
           needs=({"stat": "green_index_found", "at_least": 5},),
           floor="EASY", guaranteed=True),
       art=_art("orb", "glass", "#8fd07a", "index_dot", "voidbite",
                "a small green sphere with one dark pixel that stays put while "
                "everything else on the sprite moves")),

    _a(id="amortised_bow", name="The Amortised Bow", slot="weapon",
       rarity="LEGENDARY", icon="bow", skill="DP", chapter="optimisation",
       signature="memo_bank",
       effects={"memo_bank": 1, "mana_regen": 5, "retest_bonus": 0.35,
                "xp_bonus": 0.25},
       history=(
           "Made by the Ruins' last quartermaster, who was tired of paying "
           "twice for arrows and solved it at the level of the bow.",
           "Made for a siege expected to last a decade, on the principle that "
           "the first shot should be expensive and the ten-thousandth free.",
           "It failed the siege, which lasted eleven days, during which the "
           "bow was still amortising and the wall came down.",
           "In the Ruins, in a rack built for forty bows, holding one bow and "
           "thirty-nine perfectly preserved empty slots.",
       ),
       flavour="The first draw is agony. You will not notice the second. You "
               "will not be able to feel the hundredth at all.",
       affinity="ARCHIVIST", dissonance="DUELIST",
       acquisition=_acq(
           "proof",
           "Dynamic-programming mastery 75 that survives a retest, across eight "
           "unaided clears.",
           needs=({"skill": "DP", "mastery": 75, "retention": 60, "unaided": 8},
                  {"skill": "BIG_O", "mastery": 55}),
           floor="MEDIUM", base=0.55),
       art=_art("bow", "wood", "#c8a8ff", "tally", "coldlight",
                "a recurve of dark wood with a row of tally marks up the limb, "
                "the marks getting closer together toward the tip")),

    _a(id="the_long_compile", name="The Long Compile", slot="weapon",
       rarity="MYTHIC", icon="sword", skill="BIG_O", chapter="optimisation",
       signature="weakness_chain",
       effects={"weakness_chain": 0.25, "sealed_hints": 1, "xp_bonus": 0.4,
                "mana_max": 12},
       history=(
           "Made by Sera Oule in the four days between the vote and the "
           "switch-on, longer than a sword should be, on purpose.",
           "Made for the Architect who would have to un-say a name, and made "
           "long so that it could not be swung in a hurry by anyone.",
           "It failed Sera. She finished it, carried it to the Council, and "
           "watched them hand the work to the Engine instead because the Engine "
           "was faster.",
           "Driven into the outer wall of the Grey Repository, holding the door "
           "shut from the wrong side, which is how you know somebody was inside.",
       ),
       flavour="You cannot ask it anything. That is not a malfunction, and it "
               "is not a punishment either.",
       affinity="ANALYST", dissonance="ARCHIVIST",
       acquisition=_acq(
           "boss",
           "Beat the Complexity Wyrm without casting a single learning spell.",
           where="complexity_wyrm", conditions=("no_spell_cast",),
           needs=({"skill": "BIG_O", "mastery": 70},
                  {"skill": "DP", "mastery": 60, "unaided": 6}),
           floor="HARD", base=0.4),
       art=_art("sword", "steel", "#e8c37d", "spiral", "slowbleed",
                "a blade two pixels longer than the box comfortably holds, the "
                "point cropped by the frame")),

    _a(id="glass_edge", name="The Glass Edge", slot="weapon", rarity="MYTHIC",
       icon="dagger", skill="SPEED", chapter="optimisation",
       signature="glass_stamina",
       effects={"glass_stamina": 1, "xp_bonus": 1.0, "loot_luck": 0.6,
                "crit_bonus": 0.6},
       history=(
           "Made by a glassmaker in the Tower who had no metal and refused, on "
           "principle, to consider that a reason not to make a knife.",
           "Made for one cut. Everything about its geometry assumes there will "
           "not be a second one, and the geometry is correct.",
           "It failed the glassmaker, in the obvious way, on the first "
           "demonstration, in front of the people he was demonstrating to.",
           "On the top floor of the Complexity Tower, which cannot be reached "
           "by brute force, in a case with no lock, because who would.",
       ),
       flavour="Everything it does, it does once. Including break.",
       affinity="DUELIST", dissonance="ANALYST",
       acquisition=_acq(
           "dungeon",
           "Clear the Doubling Stair top to bottom at ELITE with no failed "
           "submission.",
           where="doubling_stair",
           conditions=("full_depth", "no_failed_submission"),
           needs=({"skill": "SPEED", "mastery": 65},
                  {"skill": "BIG_O", "mastery": 60, "unaided": 6}),
           floor="ELITE", base=0.3),
       art=_art("dagger", "glass", "#ffd9df", "fracture", "voidbite",
                "a knife with no tang and no grip, held by an edge that is "
                "clearly also an edge")),

    _a(id="vails_last_page", name="Vail's Last Page", slot="trinket",
       rarity="MYTHIC", icon="scroll", skill="RECALL", chapter="gauntlet",
       signature="unlabelled",
       effects={"unlabelled": 1, "xp_bonus": 0.6, "retest_bonus": 0.4,
                "mana_max": 10},
       history=(
           "Written by you, in your handwriting, at the end of a war you have "
           "not fought yet, on the last blank sheet in the bundle.",
           "Made for one reader, with one instruction on it, which Vail "
           "followed through a torn place in the sky and did not survive.",
           "It failed Vail immediately and completely. Vail sent the rest of "
           "the pages ahead anyway, knowing, which is the part that matters.",
           "It arrives after Vail is dead. They all do. You stop being "
           "surprised by this around Chapter VII and you never stop reading them.",
       ),
       flavour="Nothing on it is labelled. You wrote it for someone who would "
               "not need the labels, and that someone is you, later.",
       affinity="ANALYST", dissonance="ARCHIVIST",
       acquisition=_acq(
           "exam",
           "Pass a full Timed Practical Mode run with recall at standard. The page is "
           "in the bundle when you get back.",
           conditions=("no_failed_submission",),
           needs=({"skill": "RECALL", "mastery": 70, "retention": 60},
                  {"stat": "interviews_passed", "at_least": 1}),
           floor="ELITE", base=0.6),
       art=_art("scroll", "paper", "#a89aff", "index_dot", "stillness",
                "a single sheet, handwriting visible as texture, one corner "
                "burnt in a way the rest of the bundle is not")),

    _a(id="arena_pace", name="Pace of the Arena", slot="feet",
       rarity="LEGENDARY", icon="boots", skill="SPEED", chapter="gauntlet",
       signature="rank_floor",
       effects={"rank_floor": 1, "rank_grace": 0.3, "hint_surcharge": 0.5,
                "crit_bonus": 0.25},
       history=(
           "Made by the Coliseum's own cobbler, who has made four hundred pairs "
           "and watched every single fight they were worn in.",
           "Made for the third minute, when the crowd has stopped watching your "
           "hands and started watching your feet.",
           "They failed Halla Vane in the final, who had the fight won, looked "
           "up, and was reminded that the floor is sand.",
           "Awarded. Actually awarded, in front of people, by someone whose job "
           "it is, which happens exactly once in this game.",
       ),
       flavour="They will not let you drop below A while you are on a run. They "
               "will also not let you ask for help cheaply. Fair trade.",
       affinity="DUELIST", dissonance="ARCHIVIST",
       acquisition=_acq(
           "boss",
           "Beat the Examiner in under half the target time.",
           where="the_interviewer",
           conditions=("under_half_target", "no_failed_submission"),
           needs=({"skill": "SPEED", "mastery": 70},
                  {"skill": "RECALL", "mastery": 60}),
           floor="ELITE", base=0.45),
       art=_art("boots", "leather", "#ff9d4a", "boundary", "emberfall",
                "low boots, cut for sand, the toe and heel bound in bright "
                "leather and everything between them worn colourless")),

    _a(id="grey_door_key", name="The Grey Door Key", slot="trinket",
       rarity="MYTHIC", icon="key", skill="DESIGN", chapter="gauntlet",
       signature="phase_preview",
       effects={"phase_preview": 1, "probe_charges": 1, "mana_max": 15,
                "crit_bonus": 0.3},
       history=(
           "Made by the Repository itself, which is a vault-face and not a "
           "person, by the slow method vaults use: it grew a keyway, and waited.",
           "Made for whoever could name the door. Not open it. Name it. The "
           "distinction is the entire security model and it held for two "
           "centuries.",
           "It failed everyone. Every Architect of the last Council tried, in "
           "order of seniority, and the jawless face did not so much as warm up.",
           "It is not found, it is issued: the keyway closes on your hand the "
           "first time you stand in front of the door and do not ask it anything.",
       ),
       flavour="A key for a door that was never locked, held by people who "
               "could not say what it was.",
       affinity="DUELIST", dissonance="",
       acquisition=_acq(
           "chain",
           "Finish the Castle of Names chain with all eleven chapters "
           "graduated.",
           where="castle_names",
           needs=({"stat": "chapters_graduated", "at_least": 11},
                  {"skill": "DESIGN", "mastery": 55},
                  {"skill": "COMMUNICATION", "mastery": 55}),
           floor="ELITE", guaranteed=True),
       art=_art("key", "bone", "#cfd2e8", "keyward", "coldlight",
                "a key of grey bone with three uneven wards and a bow shaped "
                "like a closed mouth")),
]

BY_ID = {a.id: a for a in ARTIFACTS}

OBLIGING_HAND = BY_ID["obliging_hand"]


# ==========================================================================
# SECTION 6 — THE OBLIGING HAND
# ==========================================================================
#
# Story bible §3, made mechanical and made honest.
#
# The Hand solves any encounter instantly and pays full loot. Each use
# permanently decays the skill it solved. Nobody stops you, nobody scolds you,
# the mentors notice, and the last door is the one door it cannot open.
#
# "Permanently" is the load-bearing word and it is easy to fake. A version that
# only subtracts mastery is not permanent at all: twenty minutes of ordinary
# play puts the number back and the player correctly concludes the Hand is free.
# So the decay here has two parts.
#
#   1. An immediate loss of mastery, retention and independence. This is the
#      part the player sees in the skill panel that evening.
#   2. A permanent reduction in that skill's CEILING. Every use lowers the
#      highest mastery the skill can ever reach again by HAND_CEILING_LOSS. The
#      loss is recorded per skill in a ledger that survives the save, and
#      apply_outcome's gains are clamped against it. This is the part the player
#      sees three chapters later, when a skill they have worked at will not go
#      past seventy-four, and there is no item, shrine, quest or difficulty
#      setting in the game that restores it.
#
# The only thing in the world that touches part 2 is the Sourcewright's
# Gauntlets, which give back half of one unaided clear's worth of ceiling per
# unaided clear — slowly, incompletely, and never above the original ceiling.
# Sera Oule wore the Hand once and never got the whole of it back either.
#
# The game does not editorialise about any of this. hand_offer() is written
# straight, mentor_line() is written kindly, and the numbers do the argument.

HAND_BASE_DECAY = 6.0           # mastery removed per use, before difficulty
HAND_CEILING_LOSS = 3.0         # permanent ceiling loss per use, per skill
HAND_CEILING_FLOOR = 25.0       # a skill can never be ground below this
HAND_RETENTION_LOSS = 8.0       # delayed recall goes first; it always does
HAND_DIFFICULTY_SCALE = {       # solving something hard for you costs more
    "GUIDED": 0.4, "TUTORIAL": 0.6, "EASY": 1.0, "MEDIUM": 1.5,
    "HARD": 2.0, "ELITE": 2.3, "BOSS": 2.6,
}

# The one place the Hand does not work, and the reason the whole design is
# allowed to be this generous everywhere else.
HAND_SEALED_MODES = ("interview", "exam", "final")


def hand_sealed(mode: str) -> bool:
    """True where the Hand does nothing. Timed Practical Mode measures; the Hand is
    not a measurement, so it is not present. The Null King's door is the same
    rule wearing a different hat."""
    return str(mode or "adventure").lower() in HAND_SEALED_MODES


def hand_offer() -> dict:
    """What the King says in Chapter IV. Sincerely. It is not a trick and the
    text must never imply that it is."""
    return {
        "speaker": "The Null King",
        "lines": (
            "You are doing this the slow way. I want you to know that I have "
            "noticed, and that I think well of you for it.",
            "This is the Hand. Put it on and ask it anything. It will answer, "
            "correctly, the first time, and you will be paid for the answer "
            "exactly as though you had found it.",
            "It was built for people who were still trying. You are the only "
            "one left in that category, so it is yours whether you wear it or "
            "not.",
            "I will not ask you again, and I will not think less of you either "
            "way. Take your time. Nobody is timing this part.",
        ),
        "choices": ("Take it.", "Leave it."),
        "note": "Leaving it does nothing. It is in your pack at the next save.",
    }


def hand_decay_amount(difficulty: str) -> float:
    """How much mastery one use costs. Scaled by difficulty, because the Hand
    charges you for the thinking you skipped and a HARD problem was more
    thinking."""
    return HAND_BASE_DECAY * HAND_DIFFICULTY_SCALE.get(difficulty, 1.0)


def hand_ledger_new() -> dict:
    """The permanent record. One key per skill the Hand has been used on, plus
    a lifetime counter. This belongs in the save file next to skills."""
    return {"uses": 0, "ceiling_loss": {}, "log": []}


def mastery_ceiling(ledger: dict, skill: str) -> float:
    """The highest mastery this skill can ever reach again.

    Called by whatever grades an attempt. Without this clamp the ceiling loss
    is a comment rather than a mechanic.
    """
    lost = float((ledger or {}).get("ceiling_loss", {}).get(skill, 0.0))
    return max(HAND_CEILING_FLOOR, 100.0 - lost)


def clamp_to_ceiling(state, ledger: dict):
    """Apply the ceiling to a SkillState after it has been graded normally.

    The call order that keeps this honest is: skills.apply_outcome() first, then
    this. Doing it the other way round lets a single clear briefly exceed a
    ceiling the Hand paid for, which the player will notice and correctly read
    as the cost being fake.
    """
    ceiling = mastery_ceiling(ledger, state.name)
    if state.mastery > ceiling:
        state.mastery = ceiling
        state.stage = skillmod.derive_stage(state)
    return state


def use_hand(skills: dict, ledger: dict, *, skill: str, difficulty: str,
             mode: str = "adventure") -> dict:
    """Solve the encounter with the Hand. Returns what happened.

    This is the only function in the codebase that lowers mastery for a reason
    other than a graded failure, and it is deliberately the only one.
    """
    if hand_sealed(mode):
        return {
            "solved": False,
            "sealed": True,
            "reason": "The Hand is open and empty. Nothing happens. It does "
                      "not seem embarrassed.",
        }

    state = (skills or {}).get(skill)
    if state is None:
        return {"solved": False, "sealed": False,
                "reason": f"unknown skill: {skill}"}

    before = round(state.mastery, 1)
    amount = hand_decay_amount(difficulty)

    # 1. the visible loss
    state.mastery = max(0.0, state.mastery - amount)
    state.retention = max(0.0, state.retention - HAND_RETENTION_LOSS)
    # Independence is what the Hand actually takes; hint_dependence is the
    # number the coach reads, so it has to move or the coach will keep
    # recommending unaided work that is not happening.
    state.hint_dependence = min(100.0, state.hint_dependence + 12.0)
    state.attempts += 1
    state.stage = skillmod.derive_stage(state)

    # 2. the permanent loss
    ledger = ledger if ledger is not None else hand_ledger_new()
    ledger.setdefault("ceiling_loss", {})
    ledger.setdefault("log", [])
    ledger["uses"] = int(ledger.get("uses", 0)) + 1
    ledger["ceiling_loss"][skill] = min(
        100.0 - HAND_CEILING_FLOOR,
        float(ledger["ceiling_loss"].get(skill, 0.0)) + HAND_CEILING_LOSS,
    )
    clamp_to_ceiling(state, ledger)
    ceiling = mastery_ceiling(ledger, skill)
    ledger["log"].append({"skill": skill, "difficulty": difficulty,
                          "mastery_before": before,
                          "mastery_after": round(state.mastery, 1),
                          "ceiling": round(ceiling, 1)})

    return {
        "solved": True,
        "sealed": False,
        "loot": "full",             # full loot, exactly as promised, no asterisk
        "xp": "full",
        "rank": "S",
        "skill": skill,
        "mastery_before": before,
        "mastery_after": round(state.mastery, 1),
        "mastery_lost": round(before - state.mastery, 1),
        "ceiling": round(ceiling, 1),
        "uses": ledger["uses"],
        # Stated once, plainly, with no adjective attached to it.
        "notice": f"{skill} mastery {before} to {round(state.mastery, 1)}. "
                  f"{skill} can no longer exceed {round(ceiling, 1)}.",
        "ledger": ledger,
    }


def hand_regrow(ledger: dict, skill: str, *, rate: float = 0.5,
                clears: int = 1) -> float:
    """The Sourcewright's Gauntlets, and nothing else in the game.

    Gives back `rate` of HAND_CEILING_LOSS per unaided clear. At the default
    half rate it takes two unaided clears to undo one use of the Hand, which
    means a player who leaned on it for a whole chapter cannot buy the ceiling
    back inside that chapter. Returns the ceiling afterwards.
    """
    ledger = ledger if ledger is not None else hand_ledger_new()
    loss = ledger.setdefault("ceiling_loss", {})
    have = float(loss.get(skill, 0.0))
    if have <= 0:
        return mastery_ceiling(ledger, skill)
    loss[skill] = max(0.0, have - HAND_CEILING_LOSS * rate * max(1, clears))
    if loss[skill] <= 0:
        loss.pop(skill, None)
    return mastery_ceiling(ledger, skill)


# The mentors notice. They do not lecture, they do not withdraw, and the llama
# gets the last one because the llama says true things and is unbothered.
HAND_MENTOR_LINES = (
    (0, "moss", "You have got a spare gauntlet in your pack. Suit yourself."),
    (1, "lorne", "You used it. All right. I would rather know than not."),
    (3, "ives", "Your hands are slower this week. I am not saying that to "
                "make a point, I am saying it because it is my job to notice."),
    (6, "halla", "I wore something like it, at the Coliseum, for one fight. I "
                 "still cannot do the thing I used it for. That is all."),
    (10, "sable", "Nobody here is going to stop you. I want to be clear that "
                  "this is not the same as approval, and also not the same as "
                  "disapproval."),
    (15, "quill", "The gauntlet is very good. That is the problem with it. "
                  "Nobody ever put down a thing that was working."),
    (25, "bosk", "You are being answered. You are not being taught. Those look "
                 "identical right up until the day they do not."),
)


def mentor_line(uses: int) -> dict:
    """What the world says at this number of uses. Never a warning, never a
    scold, and it always stops short of telling the player what to do."""
    chosen = HAND_MENTOR_LINES[0]
    for threshold, npc, line in HAND_MENTOR_LINES:
        if uses >= threshold:
            chosen = (threshold, npc, line)
    return {"at": chosen[0], "npc": chosen[1], "line": chosen[2]}


def hand_summary(ledger: dict) -> dict:
    """One honest paragraph for the save screen and the ending. No adjectives,
    no score, no judgement — the list of skills and their ceilings is already
    the most eloquent thing this module can say."""
    ledger = ledger or hand_ledger_new()
    losses = ledger.get("ceiling_loss", {}) or {}
    rows = [{"skill": name, "lost": round(v, 1),
             "ceiling": round(mastery_ceiling(ledger, name), 1)}
            for name, v in sorted(losses.items(), key=lambda kv: -kv[1])]
    return {
        "uses": int(ledger.get("uses", 0)),
        "skills_touched": len(rows),
        "rows": rows,
        "sealed_in": list(HAND_SEALED_MODES),
        "mentor": mentor_line(int(ledger.get("uses", 0))),
    }


# ==========================================================================
# SECTION 7 — DROPS
# ==========================================================================

def drop_chance(artifact_id: str, difficulty: str, *, luck: float = 0.0,
                conditions_met: bool = True) -> float:
    """The chance this artifact drops right now.

    Zero until the acquisition's conditions are satisfied, which is the whole
    "earned, not rolled" rule expressed as one early return. After that it rises
    with difficulty, monotonically, by construction.
    """
    art = BY_ID.get(artifact_id)
    if art is None or not conditions_met:
        return 0.0
    acq = art.acquisition
    if _rank(difficulty) < _rank(acq["floor"]):
        return 0.0
    if acq["guaranteed"]:
        return 1.0
    mult = DIFFICULTY_MULT.get(difficulty, 0.0)
    return min(MAX_ROLL_CHANCE, acq["base"] * mult * (1.0 + max(0.0, luck)))


def chance_table(artifact_id: str, *, luck: float = 0.0) -> dict:
    """Every rung of the ladder for one artifact, for the codex page and for
    the test that asserts monotonicity."""
    return {d: round(drop_chance(artifact_id, d, luck=luck), 4)
            for d in DIFFICULTY_LADDER}


def eligible(artifact_id: str, *, skills: dict | None = None,
             stats: dict | None = None, conditions: set | None = None) -> dict:
    """Has the player done the thing? Returns the same progress shape
    items.upgrade_progress() returns, so the codex renders both with one widget.

    A condition set is satisfied if ANY listed condition is present, because a
    few artifacts offer genuinely alternative routes — the Sourcewright's
    Gauntlets are reachable whether you have worn the Hand or never have.
    """
    art = BY_ID.get(artifact_id)
    if art is None:
        return {}
    acq = art.acquisition
    have_conditions = set(conditions or ())
    # items._clause_checks is borrowed on purpose: an artifact requirement and
    # an upgrade requirement are the same sentence in the same vocabulary, and a
    # second copy of that parser would drift within a month.
    checks = []
    for clause in acq["needs"]:
        checks.extend(items._clause_checks(clause, skills or {}, stats or {}))
    cond_met = (not acq["conditions"]) or bool(
        have_conditions & set(acq["conditions"]))
    return {
        "id": art.id,
        "name": art.name,
        "kind": acq["kind"],
        "text": acq["text"],
        "where": acq["where"],
        "conditions": list(acq["conditions"]),
        "conditions_met": cond_met,
        "checks": checks,
        "met": cond_met and all(row["met"] for row in checks),
        "chances": chance_table(artifact_id),
        "item": art.to_dict(),
    }


def roll(artifact_id: str, difficulty: str, *, luck: float = 0.0,
         conditions_met: bool = True, owned: set | None = None,
         rng: random.Random | None = None) -> dict | None:
    """One roll. Returns the artifact dict or None. Never returns a
    consolation prize: a legendary that misses should leave nothing behind,
    because the alternative teaches the player that the beam means a potion."""
    if artifact_id in (owned or set()):
        return None
    chance = drop_chance(artifact_id, difficulty, luck=luck,
                         conditions_met=conditions_met)
    if chance <= 0:
        return None
    rng = rng or random.Random()
    if rng.random() > chance:
        return None
    return {"kind": "legendary", **BY_ID[artifact_id].to_dict()}


# ==========================================================================
# SECTION 8 — QUERIES
# ==========================================================================

def for_build(build: str) -> dict:
    """Signature artifacts and the ones that fight this build.

    The second list is the interesting one. An Analyst who picks up the Glass
    Edge has to stop probing and start committing, and that is a different
    player by the end of the chapter.
    """
    build = (build or "").upper()
    return {
        "build": build,
        "signature": [a.id for a in ARTIFACTS if a.affinity == build],
        "dissonant": [a.id for a in ARTIFACTS if a.dissonance == build],
    }


def by_slot(slot: str) -> list:
    return [a for a in ARTIFACTS if a.slot == slot]


def by_chapter(chapter_id: str) -> list:
    return [a for a in ARTIFACTS if a.chapter == chapter_id]


def codex_entry(artifact_id: str) -> dict:
    """The page. Four lines of history, one signature line, the acquisition,
    and the drop table — in that order, because the history is the reason and
    the numbers are the consequence."""
    art = BY_ID.get(artifact_id)
    if art is None:
        return {}
    return {
        "id": art.id,
        "name": art.name,
        "rarity": art.rarity,
        "slot": art.slot,
        "history": {"made_by": art.made_by, "made_for": art.made_for,
                    "failed": art.failed, "found": art.found},
        "flavour": art.flavour,
        "signature": describe({art.signature: art.effects[art.signature]}),
        "effects": describe(art.effects),
        "acquisition": art.acquisition,
        "chances": chance_table(artifact_id),
        "affinity": art.affinity,
        "dissonance": art.dissonance,
        "art": art.art,
    }


def catalogue() -> list:
    return [a.to_dict() for a in ARTIFACTS]


# ==========================================================================
# SECTION 9 — SELF-CHECK
# ==========================================================================
#
# Everything the brief asserts, asserted back. tests/ should call this and
# expect [].

ALLOWED_RARITIES = ("LEGENDARY", "MYTHIC")
_RING_SLOTS = ("ring1", "ring2")


def _art_family(slot: str) -> str:
    if slot.startswith("ring"):
        return "ring"
    return slot


def validate() -> list:
    problems = []
    seen = set()

    for a in ARTIFACTS:
        tag = f"{a.id}"

        if a.id in seen:
            problems.append(f"{tag}: duplicate id")
        seen.add(a.id)
        if a.id in items.BY_ID:
            problems.append(f"{tag}: collides with an items.py catalogue id")

        # --- rarity and slot ---
        if a.rarity not in ALLOWED_RARITIES:
            problems.append(f"{tag}: rarity {a.rarity} does not belong here")
        if a.slot not in items.SLOTS:
            problems.append(f"{tag}: slot {a.slot} is not in items.SLOTS")

        # --- effects: every key valid or declared new ---
        for key in a.effects:
            if key not in EFFECT_LABELS:
                problems.append(f"{tag}: effect key {key} is neither in "
                                f"items.EFFECT_LABELS nor declared in "
                                f"NEW_EFFECT_LABELS")
        if a.signature not in a.effects:
            problems.append(f"{tag}: signature {a.signature} is not among its "
                            f"own effects")
        if len(describe(a.effects)) != len(a.effects):
            problems.append(f"{tag}: an effect renders to no text")

        # B: mechanically distinct. No two artifacts share a signature, and the
        # signature is never a plain numeric bonus.
        if a.signature in ("xp_bonus", "loot_luck", "crit_bonus", "mana_max",
                           "stamina_max", "rank_grace", "probe_charges"):
            problems.append(f"{tag}: signature {a.signature} is a percentage, "
                            f"not a mechanic")

        # --- the Hand is unique ---
        if a.id != "obliging_hand" and "oblige" in a.effects:
            problems.append(f"{tag}: only the Obliging Hand may oblige")
        if a.id != "obliging_hand" and "skill_decay" in a.effects:
            problems.append(f"{tag}: only the Obliging Hand decays a skill")

        # --- skills ---
        if a.skill and a.skill not in skillmod.SKILLS:
            problems.append(f"{tag}: skill {a.skill} is not in skills.SKILLS")

        # --- A: four lines of history, no more, no fewer ---
        if len(a.history) != 4:
            problems.append(f"{tag}: history has {len(a.history)} lines, not 4")
        if any(not str(line).strip() for line in a.history):
            problems.append(f"{tag}: a history line is empty")
        if not a.flavour.strip():
            problems.append(f"{tag}: no inscription")
        if "!" in a.flavour or any("!" in line for line in a.history):
            problems.append(f"{tag}: exclamation mark")

        # --- C: a reachable acquisition ---
        acq = a.acquisition
        if acq["kind"] not in ACQUISITION_KINDS:
            problems.append(f"{tag}: acquisition kind {acq['kind']} unknown")
        if not acq["text"].strip():
            problems.append(f"{tag}: acquisition has no text")
        for cond in acq["conditions"]:
            if cond not in CONDITIONS:
                problems.append(f"{tag}: condition {cond} is not a known flag")
        for clause in acq["needs"]:
            if "skill" in clause and clause["skill"] not in skillmod.SKILLS:
                problems.append(f"{tag}: needs unknown skill {clause['skill']}")
            if "skill" not in clause and "stat" not in clause:
                problems.append(f"{tag}: a needs clause names neither a skill "
                                f"nor a stat")
        if a.id != "obliging_hand" and not acq["needs"] and not acq["conditions"]:
            problems.append(f"{tag}: pure chance with no path")
        if acq["floor"] not in DIFFICULTY_LADDER:
            problems.append(f"{tag}: floor {acq['floor']} is not a difficulty")
        if not acq["guaranteed"] and acq["base"] <= 0:
            problems.append(f"{tag}: rolled but with no base chance")

        # --- C: monotonic in difficulty ---
        table = chance_table(a.id)
        values = [table[d] for d in DIFFICULTY_LADDER]
        if any(b < x for x, b in zip(values, values[1:])):
            problems.append(f"{tag}: drop chance falls with difficulty: {values}")
        if not acq["guaranteed"] and max(values) > MAX_ROLL_CHANCE + 1e-9:
            problems.append(f"{tag}: a rolled artifact reaches certainty")

        # --- D: class awareness ---
        if a.affinity and a.affinity not in items.BUILDS:
            problems.append(f"{tag}: affinity {a.affinity} is not a build")
        if a.dissonance and a.dissonance not in items.BUILDS:
            problems.append(f"{tag}: dissonance {a.dissonance} is not a build")
        if a.affinity and a.affinity == a.dissonance:
            problems.append(f"{tag}: signature for and against the same build")

        # --- F: renderable ---
        art = a.art
        if art["shape"] not in LOOTART_SHAPES:
            problems.append(f"{tag}: shape {art['shape']} is not a lootart shape")
        allowed = LOOTART_SLOT_ALLOWED.get(_art_family(a.slot), ())
        if art["shape"] not in allowed:
            problems.append(f"{tag}: lootart will not draw a {art['shape']} in "
                            f"slot {a.slot}")
        if art["material"] not in LOOTART_MATERIALS:
            problems.append(f"{tag}: material {art['material']} is not a "
                            f"lootart material")
        if art["motif"] not in NEW_ART_MOTIFS:
            problems.append(f"{tag}: motif {art['motif']} is undeclared")
        if art["aura"] not in NEW_ART_AURAS:
            problems.append(f"{tag}: aura {art['aura']} is undeclared")
        if not str(art["accent"]).startswith("#"):
            problems.append(f"{tag}: accent is not a hex colour")
        if a.slot == "weapon" and a.icon not in items.HERO_WEAPON_KEYS:
            problems.append(f"{tag}: weapon icon {a.icon} would draw the hero "
                            f"holding the wrong thing")
        # The icon must be a shape lootart can legally resolve for this slot,
        # or the name must carry a strong enough hint that it never gets there.
        if a.icon not in allowed and art["shape"] != a.icon:
            if a.icon != "relic":
                problems.append(f"{tag}: icon {a.icon} is neither legal for the "
                                f"slot nor the resolved shape")

    # --- C again: every `where` names something that exists in the world ---
    # Lazy and guarded. bestiary, dungeons and quests all import items and each
    # other; importing them at module scope would make legendaries.py the
    # heaviest leaf in the package for the sake of one assertion that only the
    # test suite cares about.
    try:
        from . import bestiary, dungeons, quests, world
    except ImportError:                           # pragma: no cover
        pass
    else:
        known = {b.id for b in bestiary.BOSSES}
        known |= {d.id for d in dungeons.DUNGEONS}
        known |= {c["id"] if isinstance(c, dict) else c.id
                  for c in quests.CHAINS}
        known |= set(world.REGION_BY_ID)
        for a in ARTIFACTS:
            where = a.acquisition["where"]
            if where and where not in known:
                problems.append(f"{a.id}: acquisition happens at {where}, "
                                f"which is not a boss, dungeon, chain or region")

    # --- B again, globally: twenty-two distinct mechanics ---
    signatures = [a.signature for a in ARTIFACTS]
    if len(set(signatures)) != len(signatures):
        dupes = sorted({s for s in signatures if signatures.count(s) > 1})
        problems.append(f"signatures are not distinct: {dupes}")

    if len(ARTIFACTS) < 20:
        problems.append(f"only {len(ARTIFACTS)} artifacts; the brief asks 20")

    # --- D again: the anti-synergy the brief asks for actually exists ---
    if not any(a.dissonance for a in ARTIFACTS):
        problems.append("no artifact fights its obvious build")
    for build in items.BUILDS:
        if not any(a.affinity == build for a in ARTIFACTS):
            problems.append(f"no signature artifact for {build}")

    # --- E: the Hand behaves as advertised ---
    if not hand_sealed("interview"):
        problems.append("the Hand is not sealed in Timed Practical Mode")
    if hand_sealed("adventure"):
        problems.append("the Hand does not work where it is supposed to")
    probe = skillmod.new_skills()
    probe["HASH_MAP"].mastery = 80.0
    led = hand_ledger_new()
    out = use_hand(probe, led, skill="HASH_MAP", difficulty="HARD")
    if not out["solved"] or out["loot"] != "full":
        problems.append("the Hand does not pay full loot")
    if out["mastery_after"] >= 80.0:
        problems.append("the Hand costs nothing immediately")
    if mastery_ceiling(led, "HASH_MAP") >= 100.0:
        problems.append("the Hand costs nothing permanently")
    probe["HASH_MAP"].mastery = 99.0
    clamp_to_ceiling(probe["HASH_MAP"], led)
    if probe["HASH_MAP"].mastery > mastery_ceiling(led, "HASH_MAP"):
        problems.append("the ceiling does not hold")

    return problems


def stats() -> dict:
    return {
        "artifacts": len(ARTIFACTS),
        "mythic": sum(1 for a in ARTIFACTS if a.rarity == "MYTHIC"),
        "legendary": sum(1 for a in ARTIFACTS if a.rarity == "LEGENDARY"),
        "new_effect_keys": len(NEW_EFFECT_LABELS),
        "new_motifs": len(NEW_ART_MOTIFS),
        "new_auras": len(NEW_ART_AURAS),
        "slots": sorted({a.slot for a in ARTIFACTS}),
        "guaranteed": sum(1 for a in ARTIFACTS
                          if a.acquisition["guaranteed"]),
        "rolled": sum(1 for a in ARTIFACTS if not a.acquisition["guaranteed"]),
    }


WIRING = """
How the engine picks this module up.

1. THE EFFECT VOCABULARY — DONE
   The thirty-one keys this module owns now live in items.EFFECT_LABELS, listed
   there under this file's name, and LEGENDARY_EFFECT_KEYS is the list of which
   ones they are. items.describe(), legendaries.describe() and the generic
   tooltip path in engine.py all render them identically; there is no longer a
   path on which an artifact's signature renders short.

   The keys themselves still have to be honoured by the systems they name.
   Grouped by owner:

       battle / probes      probe_unbounded, probe_first_free, boundary_sense,
                            prereq_sight, phase_preview
       dungeon              off_map
       clock and rank       no_clock, rank_floor, rank_ceiling
       combo                combo_immortal, combo_brittle
       submission           no_second_attempt, glass_stamina,
                            focus_from_failure, xp_on_failure
       armour               armor_eternal
       spells               sealed_hints, hint_surcharge, spell_refund,
                            memo_bank
       progression          weakness_chain, mastery_spillover, retest_storm,
                            unlabelled, indexed, naming
       loot                 loot_double_roll
       the Hand             oblige, skill_decay, sealed_in_exam, hand_ward

   items.total_effects() already folds an artifact's effects correctly if the
   artifact is in the inventory as an items.Item — Artifact.to_item() produces
   exactly that. Four keys are switches rather than sums and should be added to
   the max() branch in total_effects: sealed_hints, no_second_attempt,
   armor_eternal, glass_stamina.

2. STATE
   engine.DEFAULT_STATE["legendaries"] = []                  # ids owned
   engine.DEFAULT_STATE["hand"] = legendaries.hand_ledger_new()

   The ledger must persist across sessions. It is the only permanent cost in
   the game and a ledger that resets on load makes the Hand free.

3. GRADING — the one call order that matters
       state = skills.apply_outcome(state, ...)
       legendaries.clamp_to_ceiling(state, G.state["hand"])
   In that order. Reversed, a clear briefly exceeds a ceiling the player paid
   for, and they will see it.

4. THE DROP
   After an encounter, for each artifact whose conditions the encounter just
   satisfied:
       got = legendaries.roll(aid, difficulty, luck=eff.get("loot_luck", 0),
                              conditions_met=True, owned=set(owned))
   roll() returns None when the path is not walked, so it is safe to call for
   every artifact every time. Guaranteed artifacts should be awarded directly
   rather than rolled; eligible()["met"] is the test.

5. THE CODEX
   legendaries.codex_entry(id) renders a page: four lines of history, the
   signature, the acquisition, the drop table. legendaries.eligible(id, skills,
   stats, conditions) returns the same progress shape items.upgrade_progress()
   returns, so one widget draws both.

6. THE HAND
   Offer: legendaries.hand_offer() at the start of Chapter IV. Once.
   Use:   legendaries.use_hand(G.skills, G.state["hand"], skill=..., difficulty=...)
          Pay the returned loot and XP in full. Show `notice` once, plainly,
          with no commentary attached to it.
   Seal:  legendaries.hand_sealed(mode) gates the button. The final door uses
          the same call.
   World: legendaries.mentor_line(uses) changes what the mentors say. It is
          already written to never scold; do not add a warning around it.
   Cure:  the Sourcewright's Gauntlets call legendaries.hand_regrow() on every
          unaided clear. Nothing else in the game may call it.

7. ART
   web/js/lootart.js draws every artifact today at its rarity tier with no
   changes: each `art.shape` is a shape lootart already has, legal for the slot,
   and each name or icon resolves to it. The four items in NEW_ART_REQUESTS,
   plus the motifs and auras in NEW_ART_MOTIFS and NEW_ART_AURAS, are what makes
   a legendary look different from a Rare with better numbers rather than the
   same picture in gold.

8. TESTS
   assert legendaries.validate() == []
   That call checks, among other things, that every effect key resolves, that
   every artifact has a path, that drop chance never falls as difficulty rises,
   that no two artifacts share a signature, and that the Obliging Hand really
   does take something it cannot give back.
"""
