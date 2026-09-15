"""Companions: twelve entries, eleven animals, one at a time, and the whole of
the help that arrives unasked.

A pet's intervention IS a hint. That used to mean only that a companion paid the
hint's price. It now means more: a companion's TIER decides how deep the unasked
help in this game goes at all. Walking into a MEDIUM encounter carrying a
BEGINNER animal is a decision with a shape, which is a better question than
"should I spend focus on a hint", because that one only ever had a cost on one
side of it.

The rules this module is not allowed to bend, and which are tested:

  * an intervention costs rank and counts against `hints_used` (see HINT_KINDS
    and HINT_WEIGHT);
  * it does not exist where `finalexam` says it does not. The seal is decided in
    ONE place — `finalexam.sealed(encounter, "PET")` — and `available_in` takes
    that verdict as an argument rather than forming a second opinion about it;
  * it never states an answer. Every line here is authored against a REDACTED
    view of the encounter — pattern, weakness class, failure category, tier —
    and none of it has ever seen a test or a worked solution;
  * mastery moves on graded evidence, so discovery is evaluated over evidence
    the engine already records and granting stays the caller's business.

THE LADDER (A). Six tiers, lined up with `curriculum.TIERS`:

    TUTORIAL   GUIDED and TUTORIAL       the starter, and only the starter
    BEGINNER   through EASY
    ADEPT      through MEDIUM
    MASTER     through HARD
    LEGENDARY  everything, boss rooms included; the returned starter
    HIDDEN     everything; found rather than earned

A companion above its depth does not give a thinner hint. It gives NOTHING, and
says so — because help that degrades gracefully teaches the player that the tier
does not matter, and the tier is the entire point. What it gives instead of a
hint is a ROUTE (see `fallback_route`): the roads out of this problem that are
open to somebody carrying the wrong animal, named, with the deed and the place
for the companions who would have covered it.

The ladder is not only about the spoken line. A tier gate that holds on the
sentence and leaks through the probe charge is not a gate, it is a style guide,
so the passives that are an opinion about THIS ENCOUNTER sit under it too — see
`DEPTH_GATED_EFFECTS` for which ones those are and why the rest of what bond
buys is deliberately left alone.

NO DEAD ENDS (F). Three of those roads are permanently companion-free, and that
is deliberate. `OPEN_RUNG` of the hint tree is never gated by a pet. The coach
speaks after a failed submission and has never asked who was walking with you.
The worked solution is free in focus after three attempts and costs the entire
rank, exactly as it did before any of this. The tier system gates the help that
arrives UNASKED AND FREE. It does not gate the help a player deliberately goes
and asks for, because a learner who cannot get unstuck stops being a learner.

That sentence now has to survive a second way of losing a companion, and it
does. An animal in the field takes area damage from monsters and bosses and can
FAINT, at which point it gives NOTHING — and the three roads above are still
open, unchanged, to that player, on that floor, with no gold in their purse.
`down_report` hands them all three at the moment the animal drops, the healer
wakes it for nothing (HEAL_COST_GOLD is 0, and the comment on it is the reason),
and `self_check` proves each of those claims rather than asserting them. See
THE COMPANION IN THE BLAST below for the seven rules that keep a faint a
setback rather than a spiral.

TWELVE WAYS IN (C). Every animal arrives differently: one is given, one is
solved for, one is bought, one is bartered for, one is taken off a boss, one is
fetched from the bottom of a mine, one follows you for a chapter and picks its
own moment, one surfaces in a trough because it likes broken armour, one is at
the end of somebody's errand, one is at the top of a tower that is itself the
test, one answers an object put down on a tile, and one was waiting for somebody
who arrived carrying nothing at all. `ACQUISITIONS` is that list as data, and
`_validate` refuses a roster in which two animals arrive the same way.

Integration contract, so another module can wire this up without reading the
implementation:

    pets.available_in(mode, region_id, sealed=)      -> may a pet speak at all
    pets.effective_difficulty(difficulty, boss=)     -> the depth being asked for
    pets.covers(pet_id, difficulty)                  -> is that within its tier
    pets.intervention(pet_id, bond=, signals=, context=, difficulty=)
                                                     -> dict | None: a hint, or
                                                        a refusal carrying a route
    pets.fallback_route(pet_id, difficulty=, state=) -> the roads out
    pets.bond_gain(pet_id, skill=, rank=, ...)       -> int added to bond
    pets.passive_effects(pet_id, bond, difficulty=)  -> items.EFFECT_LABELS keys,
                                                        with the ones that read
                                                        the room gated by tier
    pets.party_effects(active, bonds, mode=, difficulty=)
                                                     -> the same, merged
    pets.discovery_progress(pet_id, evidence)        -> progress rows + `met`
    pets.dismiss(state) / pets.recall(state, pet_id) -> reversible, both ways
    pets.fall(state)                                 -> the barrow closes
    pets.self_check()                                -> the proofs this must pass

The blast, and the way back out of it (see THE COMPANION IN THE BLAST below):

    pets.splash_damage(damage, max_health=, ...)     -> vitality points, pure
    pets.take_aoe(state, damage, max_health=, ...)   -> the blow, or None
    pets.faint(state, pet_id) / pets.heal(state, ...)-> down, and back up, free
    pets.heal_all(state)                             -> the town visit, cost 0
    pets.rest(state)                                 -> what a fight gives back
    pets.is_fainted / pets.is_down / pets.vitality   -> the bar, and the verdict
    pets.down_report(state)                          -> what is still open, said
                                                        out loud, at the moment
                                                        the animal drops

And the ways in, which are deliberately twelve different ways (see ACQUISITIONS):

    pets.sight(state, pet_id)                        -> the wild ones come closer
    pets.record_trade(state, trade_id)               -> the bought ones change hands
    pets.state_evidence(state)                       -> the evidence keys this
                                                        module stores itself

State the caller persists is tiny and flat: see `new_state()`.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

from . import curriculum, items

# How many companions may be in the field at once. One. Two meant there was a
# companion for every kind of trouble and no decision left in the choosing; one
# means the animal you brought is a position you took.
ACTIVE_LIMIT = 1

# An intervention counts as exactly one hint. It is not cheaper than a spell
# because it was unasked for; it is simply better timed.
HINT_WEIGHT = 1

# The rung of the problem's hint tree that no companion gates, in any mode where
# hints exist at all. This is the floor under the tier ladder and the reason the
# ladder cannot trap anybody. engine.use_hint owns the tree; the number lives
# here once so both modules can cite it without importing each other.
OPEN_RUNG = 1

# Attempts after which the worked solution stops costing focus. It still costs
# the whole rank. Mirrors engine.use_hint, stated here so `fallback_route` can
# tell a stuck player the truth.
FREE_SOLUTION_AFTER = 3

# Two regions say in their own description that nothing helps you there. Pets
# honour that rather than quietly making the Coliseum easier than it advertises.
SILENCED_REGIONS = ("coding_coliseum", "null_kings_castle")


# --------------------------------------------------------------------------
# THE COMPANION IN THE BLAST (A): vitality, fainting, and the way back
# --------------------------------------------------------------------------
#
# A monster's area attack hits the field, and the field includes whatever is
# walking with you. That is the whole feature. The animal is present, so it is
# in the blast; when it has taken enough it goes down and stops talking. A
# fainted companion gives NO hints — not a thinner hint, none — for exactly the
# reason a companion above its tier gives none: help that degrades gracefully
# teaches the player that the state of the world does not matter, and the state
# of the world is the thing worth teaching.
#
# WHAT THIS IS NOT ALLOWED TO BECOME (B). Losing the hint source halfway down a
# dungeon is already a real cost. Every rule below exists to keep it a setback
# rather than a spiral, and `self_check` PROVES each one rather than promising:
#
#   1. The three petless roads are untouched. OPEN_RUNG, the coach and the
#      worked solution have never asked who was walking with you and they do not
#      start now. `down_report` says so to the player's face the moment the
#      animal drops, because that is the moment they need to hear it.
#   2. Healing is free. HEAL_COST_GOLD is 0 and it is 0 on purpose: gold is the
#      durability loop's currency, and a player whose purse was eaten by an
#      armour repair must still be able to get their hints back. LEARNING NEVER
#      DEAD-ENDS, and this is one of the places that is decided.
#   3. SPLASH_CAP means no single blow takes more than a third of the bar, so
#      nothing goes from full to down without two blows of warning, and the bar
#      blinks from CRITICAL_AT downward so the warning is impossible to miss.
#   4. The first blow that WOULD end it leaves it standing on LAST_STAND
#      instead: one more round, with the animal still talking, to finish the
#      fight by typing rather than by hoping.
#   5. Vitality comes back between fights on its own while it is up —
#      REST_PER_ENCOUNTER, paid whether or not the encounter was cleared,
#      because a health bar is not mastery and gating recovery on success would
#      take the hints away from precisely the player who needs them most.
#   6. Fainting costs no bond, no discovery, and no place in the field. The
#      fainted animal stays your chosen companion so that healing puts it
#      straight back to work, and any other companion you own may be fielded in
#      the meantime.
#   7. Repeat faints cost nothing extra, ever. `faints` is a counter for the
#      codex and nothing mechanical reads it. An escalating penalty on a player
#      who is already losing is a retention mechanic wearing a costume, which is
#      the same reason bond never decays.
#   8. A faint takes the UNASKED help and nothing else. The rungs of the hint
#      tree the companion's tier had opened stay open and stay payable — see
#      `covers`, which takes no state on purpose. Closing the paid tree as well
#      would be the same punishment collected twice.
#
# And the line that is not allowed to blur: FAINTING IS NOT THE BARROW. `fall`
# is the one irreversible thing in this module, it happens to one animal at one
# boss once, and `fallen` is a different list from `fainted`. A fainted pet is
# healed for nothing in town. A fallen one is gone until the ruins give it back.

# What a companion can absorb before it goes down, in points of its own, so that
# nothing here needs to know what a monster hits for. A hundred because it is a
# bar, and a bar is what the player is going to be reading.
VITALITY_MAX = 100

# The conversion, and the one number that decides how often a player loses their
# hints. A companion's whole bar is worth seven tenths of the player's health
# bar of splash: a fight that throws 70% of your maximum health at the field in
# area damage alone puts the animal down.
#
# Worked at the numbers the rest of the game produces. An ordinary monster area
# attack costs the player about 12% of a full bar, so it costs the companion
# round(100 * 0.12 / 0.70) = 17 points. Six of those would end it; the sixth
# leaves it standing on one instead (see LAST_STAND) and the SEVENTH is the one
# it does not get up from. A boss sweep at 25% works out at 36, is capped to 34,
# and puts it down on the fourth by the same arithmetic. That is the shape the
# brief asked for: the animal faints in a bad fight, a long dungeon or a boss
# room, and never on the way to the shops. `self_check` prints both numbers
# rather than trusting this paragraph.
PET_ENDURANCE = 0.70

# No single blow may take more than a third of the bar. Three blows from full is
# the floor, whatever a boss rolls, so a player always gets a blinking bar and at
# least one round to do something about it. This is the anti-spiral rule with the
# most teeth in it, because an animal that can be deleted by one unlucky sweep is
# an animal the player stops bringing.
SPLASH_CAP = 34
SPLASH_FLOOR = 1              # and every area attack that lands is felt

# A companion is the element its species is (elements.pet_element). Standing in
# the wrong element costs it more and the right one costs it less — but clamped,
# because the point is a decision about where to walk, not a coin flip about
# whether the hints survive the room.
ELEMENT_SPREAD = (0.75, 1.25)

# The most a class's guard move may take off a blow aimed at the companion. Half.
# Anything more and "protect the pet" becomes a strictly better use of a turn
# than "attack", and the attack is the part that is made of Python.
SHIELD_CAP = 0.50

# What the first fatal blow leaves behind, once between healer visits.
LAST_STAND = 1

# What one finished encounter gives back, cleared or not. Eight points means a
# full bar is four or five encounters of ordinary play away from a bad fight,
# which is a walk home rather than a chore.
REST_PER_ENCOUNTER = 8

# Below this the bar blinks with a heartbeat, same language as the player sprite
# at low health, because the brief was explicit that this must be impossible to
# miss and a companion is the thing a player is least likely to be looking at.
CRITICAL_AT = 25

# The town healer restores health, removes poison and other afflictions, and
# wakes fainted companions, and charges NOTHING for any of it. Free is not
# generosity: it is the guarantee that a broke player with broken armour and a
# fainted animal can still walk back into a dungeon and learn something. The gold
# pressure in this game comes from repairs, potions and upgrades, all of which
# are optional in the moment. Being able to think is not optional.
HEAL_COST_GOLD = 0

# An afflicted companion speaks one time fewer per encounter, never fewer than
# once. Bond buys frequency; an ailment takes frequency back. Neither of them is
# ever allowed anywhere near depth, and neither may silence the animal outright.
AILMENT_SPEECH_COST = 1

# Labels only. A boss sweep already hits harder in raw damage; multiplying it
# again here would price the same fact twice and make the cap do all the work.
AOE_SOURCES = ("MONSTER", "BOSS", "HAZARD")

# The bar, in words, for the sprite and the codex.
CONDITIONS = (
    ("HALE", 75, "Unhurt, or near enough that it has not mentioned it."),
    ("WORN", 50, "Taking the sweeps and still talking."),
    ("HURT", 25, "Slow getting up. Still reading the room."),
    ("CRITICAL", 1, "One more of those. The bar is blinking for a reason."),
    ("DOWN", 0, "Out. No hints from here until somebody wakes it, which is free."),
)


# --------------------------------------------------------------------------
# The tier ladder
# --------------------------------------------------------------------------
#
# `depth` is the hardest entry of curriculum.TIERS this tier may speak about.
# Nothing here invents a difficulty vocabulary: the ladder the selector already
# walks is the ladder the animals are ranked against, so "my companion is one
# tier short" and "this content is one tier above me" become the same sentence.

@dataclass(frozen=True)
class Tier:
    index: int
    key: str
    label: str
    depth: str            # hardest curriculum.TIERS entry this may speak about
    blurb: str


TIERS: tuple = (
    Tier(0, "TUTORIAL", "Tutorial", "TUTORIAL",
         "Knows the alphabet. Does not know there is anything past it."),
    Tier(1, "BEGINNER", "Beginner", "EASY",
         "Reliable on a blank screen, and honest about where that stops."),
    Tier(2, "ADEPT", "Adept", "MEDIUM",
         "Reads the shapes the middle of the game is made of."),
    Tier(3, "MASTER", "Master", "HARD",
         "Has seen the hard ones and is not impressed by them."),
    Tier(4, "LEGENDARY", "Legendary", "BOSS",
         "Everything, boss rooms included. There are two of these and one of "
         "them was already yours."),
    Tier(5, "HIDDEN", "Hidden", "BOSS",
         "Everything. Nobody is told where it is."),
)

TIER_BY_KEY = {t.key: t for t in TIERS}

# curriculum.tier_index's own fallback, borrowed rather than reinvented so that
# an unclassifiable encounter is treated the same way everywhere in the game.
DEFAULT_DIFFICULTY = "EASY"


def tier_of(pet_id: str) -> Tier:
    pet = BY_ID.get(pet_id)
    return TIER_BY_KEY[pet.tier] if pet else TIERS[0]


def _clean(difficulty: str) -> str:
    return difficulty if difficulty in curriculum.TIERS else DEFAULT_DIFFICULTY


def _harder(left: str, right: str) -> str:
    return left if curriculum.tier_index(left) >= curriculum.tier_index(right) else right


def effective_difficulty(difficulty: str = "", *, boss: bool = False,
                         final: bool = False) -> str:
    """What depth this encounter is actually asking for.

    The corpus tops out at HARD, so without this a MASTER companion and a
    LEGENDARY one would be the same animal wearing different adjectives. A boss
    room reads at least ELITE because a boss is the encounter that exists to
    find out whether you needed the help; the final door reads BOSS. That is how
    the top two tiers get ground of their own, and it is also why losing the
    starter at the chapter I boss costs something real.
    """
    base = _clean(difficulty)
    if final:
        return "BOSS"
    if boss:
        return _harder(base, "ELITE")
    return base


def covers_tier(tier_key: str, difficulty: str = "") -> bool:
    tier = TIER_BY_KEY.get(tier_key)
    if not tier:
        return False
    return curriculum.tier_index(_clean(difficulty)) <= curriculum.tier_index(tier.depth)


def covers(pet_id: str, difficulty: str = "") -> bool:
    """May this companion speak about content of this depth.

    Takes no state, and that is a decision rather than an oversight. A companion
    that is unconscious in the field STILL OPENS THE TREE IT ALWAYS OPENED:
    `engine._hint_gate` asks this function which rungs of the hint tree a player
    may pay for, and a faint must not close a road the player was buying with
    focus and rank. A faint takes the help that arrives unasked and free, which
    is the thing a companion actually is. It does not take back a capability the
    player had already earned and is still paying for at the counter.

    So: `intervention` asks `is_down` and goes silent. `_hint_gate` asks this,
    and does not. Both of those are the same rule looked at from two sides, and
    neither of them is a bug to be tidied up later.
    """
    return covers_tier(tier_of(pet_id).key, difficulty)


def tiers_covering(difficulty: str = "") -> list:
    """Which tiers could have helped here, shallowest first. A refusal quotes
    this, because "go and find a better animal" is only useful advice if it also
    says how much better."""
    return [t.key for t in TIERS if covers_tier(t.key, difficulty)]


# --------------------------------------------------------------------------
# What kind of help a pet is allowed to be
# --------------------------------------------------------------------------
#
# `rank_ceiling` is the best rank still reachable after this kind of help. It
# mirrors the hint tree's own ladder: naming the family or handing over syntax is
# worth roughly an Oracle or a Reveal Path, so it lands where those land. Nothing
# here reaches Pseudosight, and nothing here can ever be a Phoenix.

HINT_KINDS = {
    "KEYWORD": {
        "label": "names the word",
        "rank_ceiling": "A",
        "rule": "May name the one Python word or mark the line is missing, and "
                "say what that word does in general. May not write the line.",
    },
    "ALGORITHM_FAMILY": {
        "label": "names the family",
        "rank_ceiling": "B",
        "rule": "May say which family of approach this is. May not say the steps.",
    },
    "EXACT_SYNTAX": {
        "label": "supplies the syntax",
        "rank_ceiling": "B",
        "rule": "May hand over the Python expression you were groping for, on a "
                "generic example. May not apply it to this input.",
    },
    "RESTATEMENT": {
        "label": "restates the question",
        "rank_ceiling": "A",
        "rule": "May strip the scenery off the question. Adds no method.",
    },
    "DATA_STRUCTURE": {
        "label": "points at the structure",
        "rank_ceiling": "B",
        "rule": "May name the structure the question wants. May not populate it.",
    },
    "EDGE_CLASS": {
        "label": "names the input class",
        "rank_ceiling": "A",
        "rule": "May name a class of input that breaks code like yours. Never a "
                "test case with its expected value.",
    },
    "DEFECT_CLASS": {
        "label": "names the defect",
        "rank_ceiling": "A",
        "rule": "May classify the failure. May not locate the line.",
    },
    "COST_SHAPE": {
        "label": "names the cost",
        "rank_ceiling": "A",
        "rule": "May describe what the current approach costs. May not say what "
                "the cheap one is.",
    },
    "DECOMPOSE": {
        "label": "splits the problem",
        "rank_ceiling": "A",
        "rule": "May ask what the smaller version of this problem is. The answer "
                "to that question stays the player's.",
    },
    "MISSING_TEST": {
        "label": "proposes a test",
        "rank_ceiling": "A",
        "rule": "May describe the shape of a test that is missing. The expected "
                "value is for the player to work out.",
    },
    "PRIOR_WORK": {
        "label": "names what you already paid for",
        "rank_ceiling": "B",
        "rule": "May name a family of problem you have already cleared that has "
                "this one's shape. May not say a word about what you wrote.",
    },
    "MIRROR": {
        "label": "becomes whichever of them you needed",
        # The worst ceiling any donor carries. A companion that can be all of
        # them pays the most expensive of their prices every single time, which
        # is the only way the hidden animal can exist without flattening the
        # other eleven into decoration.
        "rank_ceiling": "B",
        "rule": "May give exactly what the companion who belonged here would "
                "have given, under that companion's rule, at that companion's "
                "price. Invents no new permission.",
    },
}


# --------------------------------------------------------------------------
# Bond
# --------------------------------------------------------------------------
#
# Bond is earned the same way everything else in this game is earned: by graded
# evidence. It never decays. Nobody is going to be punished for taking a week off,
# and a companion that sulks about it would be a dark pattern with fur on.
#
# What bond buys, in order: the pet speaks EARLIER (threshold_scale multiplies
# every trigger threshold), then MORE OFTEN (interventions per encounter), then a
# passive drawn strictly from items.EFFECT_LABELS.
#
# What bond never buys is DEPTH. A Storied tutorial pig is a tutorial pig. Letting
# bond climb the tier ladder would turn the choice of companion back into a grind,
# and the choice is the thing this module exists to create.

@dataclass(frozen=True)
class BondRank:
    index: int
    key: str
    label: str
    at: int                   # bond points required
    threshold_scale: float    # multiplies trigger thresholds: lower = earlier
    interventions: int        # how many times it may speak in one encounter
    blurb: str


BOND_RANKS: tuple = (
    BondRank(0, "WARY", "Wary", 0, 1.0, 1,
             "It follows at a distance and leaves when you look at it."),
    BondRank(1, "TRUSTING", "Trusting", 30, 0.85, 1,
             "It sits where you can see it now, which is its whole statement."),
    BondRank(2, "BONDED", "Bonded", 90, 0.7, 2,
             "It reads the encounter before you do and waits for you to catch up."),
    BondRank(3, "SWORN", "Sworn", 200, 0.6, 2,
             "It has decided this is its work. You are not consulted."),
    BondRank(4, "STORIED", "Storied", 400, 0.5, 3,
             "Villages you have never visited know its name and not yours."),
)

BOND_BY_KEY = {r.key: r for r in BOND_RANKS}

# What a cleared encounter in the pet's skill is worth. Rank matters because
# rank is the game's honest measure of how much of that clear was the player's.
BOND_FOR_RANK = {"S": 6, "A": 4, "B": 3, "C": 2, "LEARNING_CLEAR": 1}
BOND_UNAIDED_BONUS = 2        # cleared with nothing cast and nothing said
BOND_ASSISTED_BONUS = 3       # it spoke, and then you cleared it: that is the job
BOND_RETEST_BONUS = 2         # a disguised variant days later is the good evidence
BOND_MAX_PER_ENCOUNTER = 10   # no grinding one easy problem into a Storied pet


def bond_rank(bond: int) -> BondRank:
    """The rank a bond total has earned. Monotonic, so it never reads as a loss."""
    earned = BOND_RANKS[0]
    for rank in BOND_RANKS:
        if bond >= rank.at:
            earned = rank
    return earned


def bond_progress(bond: int) -> dict:
    """Current rank, next rank, and the bar between them."""
    current = bond_rank(bond)
    nxt = BOND_RANKS[current.index + 1] if current.index + 1 < len(BOND_RANKS) else None
    span = (nxt.at - current.at) if nxt else 0
    return {
        "bond": int(bond),
        "rank": current.key,
        "rank_label": current.label,
        "rank_index": current.index,
        "blurb": current.blurb,
        "next": nxt.key if nxt else "",
        "next_at": nxt.at if nxt else 0,
        "into_rank": int(bond) - current.at,
        "span": span,
        "fraction": 1.0 if not span else min(1.0, (int(bond) - current.at) / span),
    }


# --------------------------------------------------------------------------
# When a pet is allowed to speak
# --------------------------------------------------------------------------
#
# Every trigger is a MEASURED condition over signals the engine already collects.
# There is deliberately no "on demand" kind: a pet the player can press is a
# button, and the button already exists — it is the hint tree, it costs focus,
# and it is open to everybody at every tier. That separation is what keeps the
# tier ladder from being a wall.
#
# `signals` is a flat dict the caller fills in per encounter. Missing keys read as
# zero, so a caller that only tracks half of these still gets working pets.

TRIGGER_KINDS = {
    "idle_before_first_submit": {
        "signal": "seconds_elapsed",
        "doc": "N seconds into the encounter with nothing submitted yet — the "
               "blank-screen freeze, which is the thing this whole game is for.",
        "requires_no_submission": True,
    },
    "stuck_seconds": {
        "signal": "seconds_since_progress",
        "doc": "N seconds since the last submission or edit that changed anything.",
    },
    "failed_attempts": {
        "signal": "failed_attempts",
        "doc": "N submissions have come back failing.",
    },
    "repeat_category": {
        "signal": "last_categories",
        "doc": "The same failure category twice running — the loop a player cannot "
               "see themselves in.",
    },
    "failure_category": {
        "signal": "category_counts",
        "doc": "A named grading category has appeared N times this encounter.",
    },
    "syntax_failures": {
        "signal": "syntax_failures",
        "doc": "N submissions did not compile.",
    },
    "timeout_failures": {
        "signal": "timeout_failures",
        "doc": "N submissions were correct enough to run and too slow to finish.",
    },
    "perf_trial_failed": {
        "signal": "perf_failed",
        "doc": "Correctness passed and the performance trial did not.",
    },
    "weakness_survived": {
        "signal": "weakness",
        "doc": "A hidden trial in a named weakness class broke the attempt.",
    },
    "hidden_trial_failed": {
        "signal": "hidden_failures",
        "doc": "N hidden trials failed while every visible one passed — the "
               "signature of an untested assumption.",
    },
}


@dataclass(frozen=True)
class Trigger:
    kind: str
    value: float = 0.0        # threshold, scaled by bond
    category: str = ""        # for failure_category
    line: str = ""            # what the pet says as it arrives, this time

    def threshold(self, scale: float) -> float:
        """Bond does not change WHAT is measured, only how long the pet waits."""
        return round(self.value * scale, 2)


# --------------------------------------------------------------------------
# How a pet is found
# --------------------------------------------------------------------------
#
# Not one of these is a tile you walk over. Every clause below is evidence the
# game already records, expressed as data so that any module can evaluate it and
# so that the codex can draw a progress bar for a pet nobody has met yet.

DISCOVERY_CHECKS = {
    "family_unaided":  ("families", "unaided clears in {family}"),
    "skill_unaided":   ("skills", "{skill} unaided clears"),
    "skill_mastery":   ("skills", "{skill} mastery"),
    "boss_unaided":    ("bosses_unaided", "{boss} beaten with nothing cast"),
    "region_cleared":  ("regions_cleared", "{region} cleared"),
    "dungeon_depth":   ("dungeons", "{dungeon} depth reached"),
    "retest_survived": ("retests", "{skill} memory ambushes survived"),
    "no_hint_streak":  ("no_hint_streak", "consecutive clears with no help"),
    "perf_cleared":    ("perf_cleared", "performance trials cleared"),
    "probes_correct":  ("probes_correct", "correct probes"),
    "stat":            ("stats", "{stat}"),

    # -- added by the tiered design ----------------------------------------
    # The starter's death is a fact the save records, and the legendary return
    # is gated on it, because a return that can happen before the loss is not a
    # return.
    "starter_fallen":  ("starter_fallen", "the barrow took something from you"),
    # A dungeon floor walked with no companion in the field, nothing cast and
    # nothing used. This is the hidden animal's whole condition, and it is not a
    # place — it is a way of arriving.
    "solo_floor":      ("solo_floors", "dungeon floors cleared alone and unarmed"),

    # -- added so that the roster can be earned twelve different ways (C) ---
    # Every one of these reads a fact the game already keeps. `puzzle_clears`
    # and `quests_done` are the same two snapshots quests.context() assembles,
    # spelled the same way on purpose: a second name for the same fact is a
    # second thing to keep in step.
    "puzzle_kind":     ("puzzle_clears", "{puzzle} puzzles solved"),
    "quest_done":      ("quests_done", "{quest} finished"),
    # A trade is an event: goods and gold change hands and the animal comes with
    # them. pets.record_trade writes it; the vendor decides the price is paid.
    "trade_done":      ("trades", "{trade} struck"),
    # The wild ones are not earned and not bought. They are SEEN, repeatedly,
    # getting closer, until one of them decides. pets.sight writes it.
    "sighted":         ("sightings", "{pet} seen before it would come near"),
}


# Where each of those facts comes from, because a discovery clause reading a key
# nobody writes is a progress bar that can never fill, and the codex would draw
# it once per frame without complaining. Four of these were added with the new
# arrivals; three of the four are facts the game already keeps under exactly
# these names, and the fourth is one integer the durability loop has to add.
EVIDENCE_SOURCES = {
    "families":        "engine._pet_evidence, from the attempts table",
    "skills":          "engine.skills",
    "bosses_unaided":  "db.boss_history",
    "regions_cleared": "world.unlocked_regions",
    "dungeons":        "quests state, `depths`",
    "retests":         "the attempts table, is_retest",
    "no_hint_streak":  "db.recent_attempts",
    "perf_cleared":    "engine state, perf_failed_ids",
    "probes_correct":  "engine stats",
    "solo_floors":     "engine stats",
    "stats":           "engine stats + db.attempt_stats. `armour_repairs` is the "
                       "one key this module now reads that nobody writes yet: "
                       "the smith increments it once per repair paid for",
    "starter_fallen":  "pets.state_evidence",
    "quests_done":     "quests state, `done` — the same set quests.context builds",
    "puzzle_clears":   "quests state, `puzzle_clears` — likewise",
    "trades":          "pets.state_evidence, written by pets.record_trade",
    "sightings":       "pets.state_evidence, written by pets.sight",
}


# --------------------------------------------------------------------------
# How a companion arrives (C)
# --------------------------------------------------------------------------
#
# The brief was specific and it was right: puzzles, quests, found in the wild,
# earned off a boss, traded, different for every area, and it should feel like
# an event. The roster this replaced had eleven earnable animals and ONE idea —
# every single one of them was "clear N of something unaided, twice" — which is
# a progress bar eleven times, not eleven arrivals.
#
# So there are twelve entries and twelve ways in, one each, and the method is
# data rather than prose so the codex can group by it and `_validate` can refuse
# a thirteenth animal that arrives the same way as an existing one.
#
# The methods differ in WHO ACTS. That is the axis that makes them feel
# different, rather than which counter is being counted:
#
#   GIFT     nobody acts. It is already there.       (the porch)
#   PUZZLE   you solve something that is not a fight.
#   QUEST    somebody sends you, and pays you in an animal.
#   DELVE    you go down and get it.
#   BOSS     you take it off something that was guarding it.
#   TRADE    you buy it, in gold, from a person who owns it.
#   BARTER   you leave something and go away. It decides.
#   WILD     it is in a place, and it surfaces when it is curious.
#   STALK    it is following you already and picks its own moment.
#   TRIAL    the place itself is the test and it is waiting at the top.
#   RITE     an object is put down where it means something.
#   VIGIL    you arrive with nothing at all, which is the rarest thing here.

ACQUISITIONS: dict = {
    "GIFT":   ("Given", "Nobody handed it over and nobody asked you."),
    "PUZZLE": ("Solved for", "It was listening to something that was not a fight."),
    "QUEST":  ("Sent for", "Somebody had a job, and this was at the end of it."),
    "DELVE":  ("Fetched", "It was down there. You went down there."),
    "BOSS":   ("Taken", "It was behind something that had to fall first."),
    "TRADE":  ("Bought", "Gold changed hands. It was not consulted."),
    "BARTER": ("Bartered", "You left something and walked away, which is the "
                           "whole of the offer."),
    "WILD":   ("Found", "It lives there. It surfaced because it wanted to."),
    "STALK":  ("Followed", "It had been behind you for a chapter and picked its "
                           "own moment."),
    "TRIAL":  ("Earned", "The place was the test and it was waiting at the top."),
    "RITE":   ("Answered", "You put the right thing down in the right place."),
    "VIGIL":  ("Waited for", "It was waiting for somebody who arrived with "
                             "nothing, and almost nobody does."),
}


@dataclass(frozen=True)
class Discovery:
    region: str
    where: str                # the place, in prose, for the codex
    how: str                  # the deed, in prose, for the player
    needs: tuple = ()         # the same deed, as data, for the evaluator
    first_words: str = ""     # what it says the moment it decides to stay
    arrival: str = ""         # ACQUISITIONS key: who acts, and what kind of
                              # event this is. Validated at import; two animals
                              # may not arrive the same way. Named `arrival`
                              # rather than `method` because `Pet.method` is
                              # already the sentence about what it does for you.


# How a companion arrives. EVIDENCE is the default and the honest one: a deed,
# measured. STORY means the narrative hands it over, and `discovery_progress`
# must never claim such a thing is earnable — a progress bar that can never fill
# is the codex lying once per frame.
AWARD_EVIDENCE = "EVIDENCE"
AWARD_STORY = "STORY"


# --------------------------------------------------------------------------
# The pet
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Pet:
    id: str
    name: str
    species: str
    tier: str                 # TIER_BY_KEY key: the depth cap, and the design
    skill: str                # the skill it teaches, and the skill it bonds on
    hint_kind: str            # which entry of HINT_KINDS it is allowed to be
    sprite: str
    colour: str
    tagline: str
    blurb: str                # who it is
    method: str               # what it actually does for you, plainly
    triggers: tuple           # ordered; the first one that fires is the one that speaks
    hints: dict               # keyed by pattern / weakness / category
    fallback: str             # when the key is one we have no line for
    idle: tuple
    on_intervene: str
    on_cleared: str
    on_failed: str
    above_tier: str           # when the problem is deeper than it can read
    on_dismiss: str           # as it goes back to wherever it waits
    on_recall: str            # when you come back for it
    on_faint: str             # as it goes down under an area attack
    on_wake: str              # at the healer, for nothing, as it gets up again
    bond_lines: tuple         # one per BOND_RANKS entry
    passives: dict            # bond rank index -> effects, keys from EFFECT_LABELS
    discovery: Discovery
    awarded: str = AWARD_EVIDENCE
    lineage: str = ""         # the same animal at another tier, if there is one

    def to_dict(self, bond: int = 0, *, found: bool = True,
                fallen: bool = False, vitality: int = VITALITY_MAX,
                fainted: bool = False, ailments: tuple = ()) -> dict:
        """The shape the frontend and the codex both read.

        An unfound pet still renders — silhouette, region, tier, and the deed
        that finds it — because a hidden thing nobody can work toward is not
        content, it is an accident. A FALLEN pet renders too, and says so.
        """
        progress = bond_progress(bond)
        kind = HINT_KINDS[self.hint_kind]
        tier = TIER_BY_KEY[self.tier]
        d = {
            "id": self.id, "name": self.name, "species": self.species,
            "skill": self.skill, "sprite": self.sprite, "colour": self.colour,
            "tagline": self.tagline, "hint_kind": self.hint_kind,
            "hint_label": kind["label"], "rank_ceiling": kind["rank_ceiling"],
            "tier": tier.key, "tier_label": tier.label, "tier_index": tier.index,
            "tier_blurb": tier.blurb, "helps_through": tier.depth,
            "found": bool(found), "fallen": bool(fallen),
            "fainted": bool(fainted), "vitality": int(vitality),
            "vitality_max": VITALITY_MAX,
            "condition": "DOWN" if fainted else condition(vitality),
            "blink": (not fallen) and (fainted or int(vitality) <= CRITICAL_AT),
            "ailments": list(ailments),
            "arrival": self.discovery.arrival if self.discovery else "",
            "arrival_label": ACQUISITIONS.get(
                self.discovery.arrival if self.discovery else "", ("", ""))[0],
            "arrival_blurb": ACQUISITIONS.get(
                self.discovery.arrival if self.discovery else "", ("", ""))[1],
            "awarded": self.awarded, "lineage": self.lineage,
            "region": self.discovery.region,
            "where": self.discovery.where,
            "how": self.discovery.how,
            **progress,
        }
        if found:
            d.update({
                "blurb": self.blurb,
                "method": self.method,
                "on_faint": self.on_faint,
                "on_wake": self.on_wake,
                "line": self.bond_lines[progress["rank_index"]],
                "passive": items.describe(self.passive_effects(bond)),
                "speaks_when": [t.kind for t in self.triggers],
                "above_tier": self.above_tier,
            })
        return d

    def passive_effects(self, bond: int) -> dict:
        """Everything unlocked at or below the current rank, best value winning.

        Passives are cumulative rather than replaced, so a Storied pet never
        silently loses something a Bonded one had.
        """
        earned: dict = {}
        index = bond_rank(bond).index
        for rank_index in sorted(self.passives):
            if rank_index > index:
                break
            for key, value in self.passives[rank_index].items():
                earned[key] = max(earned.get(key, 0), value)
        return earned


# --------------------------------------------------------------------------
# The arc (C): the starter, the barrow, and what comes back out of it
# --------------------------------------------------------------------------
#
# STARTER_ID walks with the player from the first encounter. It is TUTORIAL tier:
# it can help with the alphabet and nothing else, and it does not know there is
# anything else. It is not clever. It tries anyway, and the trying is the point —
# the first hour of this game is a person who cannot type accompanied by an
# animal that cannot think, and between them they get the alphabet done.
#
# It dies at the chapter I dungeon boss, and the death is not staged: it is what
# that boss IS. The Half-Written Barrow's boss is the Unclosed Bracket, a thing
# that opens and never closes, a hanging colon with nothing indented under it.
# The starter's entire ability is to supply the one missing mark. So when the
# boss opens, the pig goes in and closes it, because that is the only move it has
# ever had and nobody taught it that some things are meant to stay open. The
# bracket closes. The pig is on the inside of it.
#
# What that costs the player is exact and it is meant to sting: their only source
# of unasked help, removed at the precise moment they are first being measured,
# by the mechanism they have leaned on for an hour. It does not remove the hint
# tree, the coach, or the worked solution — see ROADS. It removes the companion,
# and the next one has to be gone and found.
#
# RETURN_ID is the same animal, years later, at the bottom of the Hall of Lit
# Tiles. The DP Ruins are the region whose physical law is that a thing you have
# already solved stays lit and costs nothing to cross again, which makes them the
# only honest place to ask whether it remembers you. It does not come when called.
# It comes when the closed half-ring is put down on the tile, because what the
# ruins remember is never who did the work, only that the work was done. Then it
# answers to the old name anyway, which is the part that is not mechanical and is
# not supposed to be.

STARTER_ID = "stub"
RETURN_ID = "barrow"
HIDDEN_ID = "mimic"

# The fall happens at the chapter I dungeon's boss. Named as the dungeon rather
# than a boss id, because that boss is assembled by the dungeon builder from
# `dungeons.DUNGEONS[0].boss_epithet` and has no entry in world.BOSSES.
FALLS_AT_DUNGEON = "halfwritten_barrow"
FALLS_AT_CHAPTER = "fluency"

# What is left on the floor. The engine may make this an item, a codex line, or
# nothing at all; the pet system only needs the save to remember it happened.
KEEPSAKE = "the closed half-ring"

RETURNS_AT_DUNGEON = "lit_tiles"


# --------------------------------------------------------------------------
# The roster
# --------------------------------------------------------------------------
#
# Twelve entries, eleven animals: STUB and BARROW are the same boar on either
# side of the barrow, which is the only duplication permitted here and is the
# entire point of the arc.
#
# Five were named by the player — jaguar, python, llama, penguin, velociraptor.
# The rest cover the habits those five leave uncovered, and every one sits at the
# tier its KIND of help actually belongs to. Restating the question is early-game
# help and is a beginner's job. Pricing an approach is not: a player who needs to
# be told what their loop costs is a player deep enough in to have written a loop
# worth pricing.
#
# SICKLE and WITNESS share a skill on purpose. Breaking your own code is two
# separate habits — choosing the input that hurts, and writing it down so it can
# never hurt twice — and a player who has one of them almost never has the other.

PETS: tuple = (

    # ---- TUTORIAL --------------------------------------------------------
    Pet(
        id=STARTER_ID, name="STUB", species="Boar",
        tier="TUTORIAL", skill="PYTHON", hint_kind="KEYWORD",
        sprite="boar", colour="#b08968",
        tagline="Knows about forty words. Will give you one of them.",
        blurb="A boar piglet with one ear, living under the porch of the house "
              "that has never finished repairing itself. It is not clever and has "
              "never been clever. What it has is a pedantic memory for the small "
              "words of a language nobody in this village can speak any more, and "
              "a willingness to keep offering them to somebody who is plainly not "
              "listening yet.",
        method="It names the one word or mark your line is missing, and says what "
               "that word does in general. It cannot see algorithms. It does not "
               "know algorithms exist. For the first hour the thing standing "
               "between you and a working line is a colon, and it knows where the "
               "colons go.",
        triggers=(
            Trigger("syntax_failures", 1,
                    line="It did not compile. That is usually one mark."),
            Trigger("idle_before_first_submit", 120,
                    line="You have not typed anything. Start with the word."),
            Trigger("stuck_seconds", 150,
                    line="Small words. It is nearly always the small words."),
        ),
        hints={
            "LANGUAGE": "A name is bound with one mark. A block is opened with a "
                        "colon, and everything under it moves four spaces right. A "
                        "function hands something back with one word, and printing "
                        "is not that word.",
            "STRING": "Text sits inside quotes. Two pieces of text join with a "
                      "plus. The length of anything is one short call with brackets "
                      "after it.",
            "ARRAY": "A list sits in square brackets, separated by commas. The first "
                     "place in it is numbered zero, and the last place is one less "
                     "than how many there are.",
            "SIMULATION": "A loop over a count is one word, then a range, then a "
                          "colon. Everything indented under it happens every time "
                          "round, and everything not indented happens once.",
        },
        fallback="Say the line out loud in English. Whichever English word you used "
                 "that has no Python word under it yet is the one that is missing, "
                 "and I probably know it.",
        idle=(
            "I know about forty words. You have thirty-one of them.",
            "It is the colon. It is very often the colon.",
            "Nobody here can speak this any more. I can only say the small parts.",
        ),
        on_intervene="You are missing a word. I have the word.",
        on_cleared="That ran. That is the whole of what I wanted.",
        on_failed="Then it was not a word. I do not know what it was.",
        above_tier="I do not know this. I have never known anything like this. "
                   "There is nothing I can tell you here and I am sorry about it.",
        on_dismiss="I will be under the porch.",
        on_recall="I did not go anywhere.",
        on_faint="The piglet sits down hard in the middle of everything and "
                 "stops making any noise at all, which it has never once "
                 "done before.",
        on_wake="Up, unsteady, and already trying to tell you about a colon.",
        bond_lines=(
            "It follows at the distance a piglet considers dignified.",
            "It sleeps against your boot and did not ask permission.",
            "It offers the word before you reach for it, and is wrong about a "
            "third of the time.",
            "It walks in front now, which for an animal this size is a decision "
            "rather than a position.",
            "The village children know its name. Nobody has ever asked yours.",
        ),
        passives={
            1: {"hint_discount": 0.1},
            2: {"hint_discount": 0.15, "stamina_max": 2},
            3: {"hint_discount": 0.2, "stamina_max": 3},
            4: {"hint_discount": 0.25, "stamina_max": 4},
        },
        discovery=Discovery(
            region="python_village",
            arrival="GIFT",
            where="Under the porch of the half-rebuilt house, where it has been "
                  "since before you arrived.",
            how="It is already with you. Nobody gave it to you and nobody asked. "
                "This is the only animal in the game that arrives for free, and "
                "it is the one that dies.",
            needs=(),
            first_words="You are the one who is going to learn to say it, then. "
                        "Fine. I know the small words.",
        ),
        awarded=AWARD_STORY,
        lineage=RETURN_ID,
    ),

    # ---- BEGINNER --------------------------------------------------------
    Pet(
        id="python", name="IDIOM", species="Python",
        tier="BEGINNER", skill="PYTHON", hint_kind="EXACT_SYNTAX",
        sprite="snake", colour="#4fb783",
        tagline="The language itself, in the form of something that can coil on a "
                "keyboard.",
        blurb="Four feet of patient green that has lived under the floor of the "
              "ruined house since before the Null King. It does not know any "
              "algorithms. It knows every word, and the order the words go in, "
              "which is the part the piglet never got to.",
        method="When the idea is fine and the typing is not, it supplies the exact "
               "expression you were groping for, on a generic example. It solves no "
               "part of your problem. It just stops you losing four minutes to a "
               "method name.",
        triggers=(
            Trigger("syntax_failures", 2,
                    line="Twice now it has refused to compile. That is not a "
                         "thinking problem."),
            Trigger("failure_category", 1, "PYTHON_RECALL",
                    line="You had the idea. The language got in the way."),
            Trigger("stuck_seconds", 200,
                    line="You are hunting for a word. I keep the words."),
        ),
        hints={
            "LANGUAGE": "The words are `=` to bind a name, a parameter list to "
                        "take arguments, and `return` to hand something back — "
                        "`print` hands back nothing. No algorithm is involved.",
            "HASH_MAP": "`counts[k] = counts.get(k, 0) + 1` tallies without a "
                        "KeyError. `collections.Counter(xs)` does the same in one word.",
            "SET": "`seen = set()`, then `x in seen` and `seen.add(x)`, both one "
                   "step. `set(a) & set(b)` is the overlap.",
            "SLIDING_WINDOW": "`for right, ch in enumerate(s):` for the widening "
                              "end, and a plain `left` you advance inside a `while`. "
                              "`s[left:right + 1]` is the stretch, if you must see it.",
            "TWO_POINTER": "`left, right = 0, len(xs) - 1`, then `while left < "
                           "right:`. A swap is `xs[i], xs[j] = xs[j], xs[i]`.",
            "STACK": "A list is a stack. `stack.append(x)`, `stack.pop()`, and "
                     "`if stack and stack[-1] == ch:` so the empty case never bites.",
            "QUEUE": "`deque` lives in `collections`. `q.append(x)` at one end "
                     "and `q.popleft()` at the other, both one step. Taking "
                     "index zero off a list is the slow way.",
            "BFS": "`q = deque([start])` beside `seen = {start}`, then `while q:`. "
                   "Mark it seen on the way in, not on the way out.",
            "DFS": "Recursion, or a list used as a stack. `for nxt in graph[node]:` "
                   "and a `seen` set either way.",
            "TREE": "`if node is None:` first, every single time. `node.left` and "
                    "`node.right` after that.",
            "RECURSION": "One `if` for the smallest case, then a call on something "
                         "strictly smaller. `functools.lru_cache` remembers calls "
                         "that keep coming back.",
            "BINARY_SEARCH": "`lo, hi = 0, len(xs) - 1` and `mid = (lo + hi) // 2`. "
                             "`bisect.bisect_left(xs, x)` when you only want the spot.",
            "MATRIX": "`rows, cols = len(g), len(g[0])`, then a nested `for r in "
                      "range(rows):`. Build a grid with `[[0] * cols for _ in "
                      "range(rows)]` — the shorter version shares one row object.",
            "HEAP": "`heapq` is in the standard library and works on a plain "
                    "list: `heapq.heappush(h, (cost, item))` and "
                    "`heapq.heappop(h)`. Negate the number for a max-heap.",
            "PREFIX_SUM": "`itertools.accumulate(xs)` gives running totals lazily. "
                          "Wrap it in `list(...)` when you need to index them.",
            "SORTING": "`sorted(xs, key=lambda p: (p[1], -p[0]))` orders by two "
                       "things at once. `xs.sort()` changes the list and hands back "
                       "nothing.",
            "DP": "`dp = [0] * (n + 1)` and one `for` over the states. Write what "
                  "the index MEANS in a comment; that is where the hour goes.",
            "STRING": "`''.join(parts)` beats `+=` in a loop. `s.split()`, "
                      "`s.strip()`, and `ord(ch) - ord('a')` for the twenty-six "
                      "buckets.",
            "DESIGN": "`collections.OrderedDict` and `collections.defaultdict(list)` "
                      "both exist, and both are fewer lines than the class you were "
                      "about to write.",
            "INTERVALS": "`intervals.sort(key=lambda iv: iv[0])`, then compare "
                         "`iv[0]` against the end you are holding.",
            "GREEDY": "`max(xs, key=...)` and one accumulator. The sort is usually "
                      "the whole of it.",
            "SIMULATION": "`for step in range(n):` and variables named after the "
                          "nouns in the statement. Boring is correct here.",
        },
        fallback="Say what you want in English, then take the nouns. A count is a "
                 "dict. An order is a list. A membership is a set.",
        idle=(
            "I am not going to bite. I am going to spell.",
            "You know the algorithm. You are losing to punctuation.",
            "There are about forty words in this language that matter. The pig had "
            "them too. It could not put them in order.",
        ),
        on_intervene="The word you are looking for is this one.",
        on_cleared="Fluent. Say it again tomorrow and it is yours for good.",
        on_failed="The sentence was fine. The idea underneath it was not. That is "
                  "somebody else's department.",
        above_tier="I can spell this. I cannot read it. Somebody who understands "
                   "the shape ought to be standing here, and it is not me.",
        on_dismiss="Under the floorboards, then. The boards are fine.",
        on_recall="You came back for the words. People generally do.",
        on_faint="Four feet of green uncoils off your arm and lies where it "
                 "falls. Nothing is being spelled for a while.",
        on_wake="It re-coils along your forearm and carries on from the "
                "middle of the word it was on.",
        bond_lines=(
            "It watches from under the floorboards and withdraws when you look down.",
            "It has taken up residence in your pack, which you have decided to "
            "allow.",
            "It supplies the word before you have finished reaching for it, and is "
            "insufferable about the timing.",
            "It coils along your forearm while you type and taps once when you "
            "misspell something.",
            "Scribes come from three regions to ask it things. It refers most of "
            "them to the documentation.",
        ),
        passives={
            2: {"hint_discount": 0.15},
            3: {"hint_discount": 0.25},
            4: {"hint_discount": 0.35, "mana_regen": 2},
        },
        discovery=Discovery(
            region="python_village",
            arrival="PUZZLE",
            where="Under the floor of the half-rebuilt house — the same boards the "
                  "village lays its rune drills out on, one room over from where "
                  "the piglet used to sleep.",
            how="The village square keeps its drills as loose lines in a box, to "
                "be put back in the order that works. Assemble six of them "
                "correctly. It lives under those boards and it can hear the order "
                "going in: wrong, wrong, wrong, wrong, and then one evening not "
                "wrong. That is the sound it comes up for, and there is no faking "
                "it.",
            needs=(
                {"kind": "puzzle_kind", "puzzle": "RUNE_ASSEMBLY", "count": 6},
                {"kind": "skill_mastery", "skill": "PYTHON", "value": 25},
            ),
            first_words="Six boards, in the right order, from underneath. You have "
                        "stopped guessing at where the lines go. Come down here "
                        "and I will give you the words to put in them.",
        ),
    ),

    Pet(
        id="llama", name="PLAIN", species="Llama",
        tier="BEGINNER", skill="COMMUNICATION", hint_kind="RESTATEMENT",
        sprite="llama", colour="#d8c8a8",
        tagline="Patience, structure, and a complete absence of urgency.",
        blurb="A llama of the high plateau, standing among the keyed vaults with no "
              "obvious business there. It has watched avalanches, ambushes and two "
              "separate ends of the world, and has adjusted its opinion of none of "
              "them. It chews.",
        method="It takes the question, removes the scenery, and hands back the same "
               "question in plain words. It adds no method and no structure. Most "
               "of the time, that is the only thing that was wrong.",
        triggers=(
            Trigger("idle_before_first_submit", 150,
                    line="Before you write anything. What is actually being asked."),
            Trigger("failure_category", 1, "WRONG_ALGORITHM",
                    line="Your code does something. It is not the thing in the "
                         "statement."),
            Trigger("stuck_seconds", 300,
                    line="Let us go back to the sentence. There is no hurry."),
        ),
        hints={
            "LANGUAGE": "Plainly: this is about what Python does with one line. "
                        "Read the line, say what it leaves behind, and write that.",
            "HASH_MAP": "Plainly: have I seen this before, and if so, where. The "
                        "rest of the wording is weather.",
            "SET": "Plainly: is this one of the things I already have. Yes or no.",
            "SLIDING_WINDOW": "Plainly: find the best unbroken stretch. Unbroken is "
                              "the word doing all the work.",
            "TWO_POINTER": "Plainly: choose two things out of a line that is already "
                           "in order. The order is a gift you have not opened.",
            "STACK": "Plainly: the most recent thing you have not finished with is "
                     "the thing this step concerns.",
            "QUEUE": "Plainly: everything is served in the order it arrived, and "
                     "nothing is allowed to jump.",
            "BFS": "Plainly: how few steps. Not which route. How few.",
            "DFS": "Plainly: is there a route at all, and what did you pass on the way.",
            "TREE": "Plainly: answer the question for this node, given that the "
                    "children have already answered theirs.",
            "RECURSION": "Plainly: solve a smaller one of these, then say what this "
                         "extra piece adds to it.",
            "BINARY_SEARCH": "Plainly: find the place where the answer stops being "
                             "no and starts being yes.",
            "MATRIX": "Plainly: it is a list of lists and the first index is the "
                      "row. Say that out loud before you write anything at all.",
            "HEAP": "Plainly: you keep needing the largest, or the smallest, over "
                    "and over. You never need the whole order.",
            "PREFIX_SUM": "Plainly: many questions about ranges of one list, and "
                          "answering each from scratch is the part that hurts.",
            "SORTING": "Plainly: this is easy once things are in some order. Which "
                       "order is the only decision here.",
            "DP": "Plainly: the same smaller question keeps arriving. Give it a name "
                  "and somewhere to live.",
            "GREEDY": "Plainly: at every step, is there an obviously best move, and "
                      "does taking it ever cost you later.",
            "INTERVALS": "Plainly: some of these stretches touch. Which ones, and "
                         "what should happen when they do.",
            "STRING": "Plainly: it is a sequence of characters, and you have walked "
                      "sequences before.",
            "ARRAY": "Plainly: walk it once, and decide what you want to be holding "
                     "when you reach the end.",
            "DESIGN": "Plainly: write down the operations and how fast each must be. "
                      "That list is the design.",
            "TESTING": "Plainly: what input would embarrass this code. That is the "
                       "entire question.",
            "DEBUGGING": "Plainly: the code does something specific. Say what, then "
                         "hold it up against what was asked.",
            "SIMULATION": "Plainly: do exactly what the statement says, in the order "
                          "it says it. The difficulty is bookkeeping, not insight.",
        },
        fallback="Say it back in one sentence that starts with 'given' and ends with "
                 "'produce'. Whatever you cannot fill in is the part you have not "
                 "read yet.",
        idle=(
            "There is no hurry. There was never any hurry.",
            "Read it out loud. That is usually the whole trick.",
            "The clock is a detail of the room. It is not a detail of the question.",
        ),
        on_intervene="Here is the same question with the scenery taken off it.",
        on_cleared="Yes. It was that question the entire time.",
        on_failed="Then it was a different question. We will find out which one.",
        above_tier="I can say this one back to you in plain words and it will not "
                   "help, because the plain words are already hard. That is a "
                   "different animal's work.",
        on_dismiss="I will be on the plateau. I am always on the plateau.",
        on_recall="You have come back up the hill. Say it again from the start.",
        on_faint="It kneels, folds its legs under itself, and stops chewing. "
                 "That is how you know, because it is the only thing it was "
                 "doing.",
        on_wake="It stands, shakes the dust out of its coat, and takes up "
                "the sentence at exactly the word it left off.",
        bond_lines=(
            "It grazes nearby and regards you as terrain.",
            "It walks the plateau beside you. It has not commented on this.",
            "It begins restating things before you ask, which from a llama is "
            "effusive.",
            "It positions itself between you and whatever is making noise, and "
            "continues chewing.",
            "Two villages have named a road after it. It has been to neither.",
        ),
        passives={
            2: {"combo_shield": 1},
            3: {"stamina_max": 4},
            4: {"combo_shield": 2, "stamina_max": 6},
        },
        discovery=Discovery(
            region="hashmap_highlands",
            arrival="TRADE",
            where="The herder's pen above the keyed vaults. Third animal from the "
                  "gate, on the side of the pen with the better view, which it "
                  "has clearly chosen deliberately.",
            how="This one is not found and it is not earned. It is bought, from a "
                "woman who owns it and is not sentimental about it. Bring the "
                "Warden's keyring back to the vaults first — she sells to nobody "
                "who has lost a key in her lifetime — and then pay her price in "
                "gold. She does not haggle. The llama does not look up while the "
                "two of you argue about it.",
            needs=(
                {"kind": "quest_done", "quest": "highlands_lost_keyring"},
                {"kind": "trade_done", "trade": "highlands_herder",
                 "gold": 240, "goods": "one season of salt"},
            ),
            first_words="Money changed hands and nobody asked me. Fine. Say the "
                        "question again, slowly, and we will see what is actually "
                        "in it.",
        ),
    ),

    Pet(
        id="axolotl", name="PATCH", species="Axolotl",
        tier="BEGINNER", skill="DEBUGGING", hint_kind="DEFECT_CLASS",
        sprite="axolotl", colour="#f2a0b5",
        tagline="Locating the defect, which is a different skill from writing the "
                "code.",
        blurb="Pale pink, permanently smiling, living in the Armorer's quench "
              "trough. It regrows whatever it loses, which has given it an unusual "
              "attitude toward broken things: nothing is ruined, everything is "
              "merely mid-repair.",
        method="It classifies the failure — boundary, state, mutation, traversal — "
               "and hands you the class, not the line. Knowing which KIND of wrong "
               "you are is most of debugging; finding the line after that takes two "
               "minutes.",
        triggers=(
            Trigger("repeat_category", 2,
                    line="That is not a new failure. That is the same one in a "
                         "different coat."),
            Trigger("failure_category", 1, "OFF_BY_ONE",
                    line="A boundary is one step out of place."),
            Trigger("failed_attempts", 3,
                    line="Three attempts, and you are patching the symptom each time."),
        ),
        hints={
            "OFF_BY_ONE": "Boundary defect. Take the smallest failing input and "
                          "write down the first and last index your loop touches.",
            "EDGE_CASE": "Edge-case defect. The ordinary path is fine; something "
                         "unusual is reaching a line that assumed it would not.",
            "STATE_MANAGEMENT": "State defect. Something is initialised, reset or "
                                "carried at the wrong moment. Find where it is set, "
                                "then ask whether that is inside the loop or outside it.",
            "MUTABILITY": "Mutation defect. Something changed that you did not mean "
                          "to change. Watch the list you are iterating over and the "
                          "default argument you are sharing.",
            "RECURSION": "Recursion defect. Either the smallest case is not caught, "
                         "or one of the calls is not getting anything smaller.",
            "TREE_TRAVERSAL": "Traversal defect. A node with one child is not a "
                              "leaf, and None is not a node.",
            "GRAPH_TRAVERSAL": "Frontier defect. Do you mark a node seen when you "
                               "put it in, or when you take it out. Those are two "
                               "different programs.",
            "PYTHON_RECALL": "Language defect. The idea held and the expression did "
                             "not. Check what type the value actually has at the "
                             "line that raised.",
            "SYNTAX": "It never compiled. Read the line above the one it named — "
                      "that is usually where the bracket went missing.",
            "WRONG_ALGORITHM": "Approach defect. Say in one sentence what your code "
                               "computes. If that sentence is not the question, no "
                               "amount of patching will help.",
            "INEFFICIENT_ALGORITHM": "Cost defect, not a correctness one. It does "
                                     "the right thing far too many times.",
            "WRONG_DATA_STRUCTURE": "Structure defect. The container cannot cheaply "
                                    "answer the question you keep putting to it.",
            "TESTING": "Coverage defect. The break was always in there. Nothing you "
                       "wrote went looking for it.",
            "COMPLEXITY": "Estimate defect. You priced the approach wrong, which "
                          "means the fix is a different approach, not a faster loop.",
            "TIME_PRESSURE": "Not a defect. It was correct. It was late. Those are "
                             "treated differently and you should treat them "
                             "differently too.",
        },
        fallback="Same break as last time, in a new coat. Read the class of input "
                 "that failed, then trace that exact input by hand. That is the "
                 "entire method, and it has never once failed.",
        idle=(
            "Whatever broke is still broken in precisely the same way.",
            "Nothing here is ruined. Everything here is mid-repair.",
            "What did you change last. Start there. You always start there.",
        ),
        on_intervene="That is not a new failure. Look at what it has in common with "
                     "the last one.",
        on_cleared="Found and closed. Write down what it was; you will meet it again.",
        on_failed="Fine. It is narrower now than it was. Which line did you last "
                  "touch.",
        above_tier="I can name what kind of broken a small thing is. This is not a "
                   "small thing, and I would only be guessing at it in front of you.",
        on_dismiss="The trough is fine. The trough has always been fine.",
        on_recall="Something broke, then. Good. Put me somewhere with water in it.",
        on_faint="It sinks to the bottom of the jar, pale even for it, and "
                 "does not come back up for anything.",
        on_wake="Back at the top of the water, and whatever it lost down "
                "there it has already grown most of again.",
        bond_lines=(
            "It surfaces in the quench trough when you pass, and sinks when you stop.",
            "It travels in a jar of water you have started carrying without deciding to.",
            "It names the defect class before the test report has finished printing.",
            "It repairs your armour overnight. The Armorer has stopped asking how.",
            "The Debugging Dungeon's cells are emptying. Nobody has credited the "
            "small pink thing in the jar.",
        ),
        passives={
            2: {"armor_repair": 0.2},
            3: {"armor_repair": 0.35, "stamina_max": 3},
            4: {"armor_repair": 0.5, "second_wind": 1},
        },
        discovery=Discovery(
            region="debugging_dungeon",
            arrival="WILD",
            where="The Armorer's quench trough, which nobody has drained in a "
                  "hundred years and which is somehow clean.",
            how="Nobody gives you this one and no deed summons it. It lives in the "
                "trough and it surfaces when it is curious, and what makes it "
                "curious is broken gear. Stand at the Armorer's bench three times "
                "while your plate is hammered back into shape, and look down each "
                "time. It will be nearer the surface than it was.",
            needs=(
                {"kind": "sighted", "pet": "axolotl", "count": 3},
                {"kind": "stat", "stat": "armour_repairs", "at_least": 3},
            ),
            first_words="Three times you have paid to have something put back "
                        "together instead of throwing it away. That is my entire "
                        "opinion about the world. Put me in the jar.",
        ),
    ),

    # ---- ADEPT -----------------------------------------------------------
    Pet(
        id="jaguar", name="ROSETTE", species="Jaguar",
        tier="ADEPT", skill="SPEED", hint_kind="ALGORITHM_FAMILY",
        sprite="jaguar", colour="#e8a33d",
        tagline="Speed, and the eye that recognises a shape it has hunted before.",
        blurb="A jaguar the colour of late afternoon, built entirely out of "
              "patience followed by no patience at all. It has been watching you "
              "read the same statement three times.",
        method="When you freeze at the blank screen, it names the FAMILY the "
               "problem belongs to. Never the steps — the family. Recognition is "
               "the part of a timed practical that happens in the first ninety seconds, "
               "and it is the part that can be trained.",
        triggers=(
            Trigger("idle_before_first_submit", 210,
                    line="You have read it three times. It is not going to change."),
            Trigger("failure_category", 1, "PATTERN_NOT_RECOGNIZED",
                    line="Wrong family. That is a cheaper mistake than it feels like."),
            Trigger("stuck_seconds", 240,
                    line="You know this shape. Let me remind you where from."),
        ),
        hints={
            "LANGUAGE": "Not a family. This one is the language itself — a "
                        "statement, an operator, a parameter. There is no shape to "
                        "recognise, only a rule to know.",
            "HASH_MAP": "Remember-as-you-go family. One pass, and a memory that "
                        "answers in one step.",
            "SET": "Membership family. The only question being asked is whether "
                   "you have seen this before.",
            "SLIDING_WINDOW": "Window family. One contiguous stretch that grows on "
                              "the right and gives ground on the left.",
            "TWO_POINTER": "Converging family. Two markers, opposite ends, moving "
                           "toward each other along something already ordered.",
            "STACK": "Last-in-first-out family. The most recent unfinished thing is "
                     "always the thing this step is about.",
            "QUEUE": "First-in-first-out family. Whatever has waited longest goes next.",
            "BFS": "Frontier family. Everything one step away, then everything two "
                   "steps away, and never out of order.",
            "DFS": "Commit-and-unwind family. Go as deep as the path allows, then "
                   "take back the last choice.",
            "TREE": "Recursive-structure family. The same question, asked of a "
                    "smaller branch.",
            "RECURSION": "Self-similar family. The problem contains a smaller copy "
                         "of itself.",
            "BINARY_SEARCH": "Halving family. Every look throws away half of what is "
                             "left standing.",
            "MATRIX": "Coordinate family. Rows and columns, and the arithmetic that "
                      "turns one into the other.",
            "HEAP": "Best-so-far family. You need the extreme value repeatedly. You "
                    "never need the full order.",
            "PREFIX_SUM": "Running-total family. A range is the difference of two "
                          "totals you already have.",
            "SORTING": "Order-first family. Put it in order and the question stops "
                       "being clever.",
            "DP": "Reuse family. The same subproblem keeps arriving and you refuse "
                  "to pay for it twice.",
            "GREEDY": "Local-choice family. Best available step, never revisited.",
            "INTERVALS": "Overlap family. Sorted by start, one live stretch at a time.",
            "STRING": "Character-walk family. Everything you know about walking a "
                      "list still applies.",
            "ARRAY": "Index family. A single walk, and arithmetic on the positions.",
            "DESIGN": "Composition family. Two structures, each doing the one thing "
                      "it is genuinely good at.",
            "SIMULATION": "Follow-the-rules family. No trick. The steps exactly as "
                          "written, carefully.",
        },
        fallback="You have hunted this shape before. Read the first line again and "
                 "ask what shape the answer has, not how to build it.",
        idle=(
            "You are reading it for the third time. I counted.",
            "Everything in these realms is a shape that has been hunted already.",
            "Slow is a decision. You are allowed to make it. I am allowed to notice.",
        ),
        on_intervene="Stop. You have met this shape before.",
        on_cleared="Faster than the last one. Speed is the only thing I measure.",
        on_failed="The shape was right. The pounce was early. That is a better "
                  "failure than most.",
        above_tier="I have never seen a shape like that. I am not going to invent "
                   "one for you and then watch you chase it.",
        on_dismiss="The treeline, then. I hunt either way.",
        on_recall="You came back into the trees. Read me the first line.",
        on_faint="It goes down mid-stride and does not get up, which from "
                 "something built entirely out of stride is unbearable to "
                 "watch.",
        on_wake="On its feet before you have noticed it was. It has not "
                "mentioned any of it and it is not going to.",
        bond_lines=(
            "It watches from the treeline and does not come when called.",
            "It walks a little ahead of you now, which is a jaguar's way of "
            "agreeing to something.",
            "It recognises the shape of a problem before you have finished reading "
            "it, and has the grace to wait.",
            "It hunts beside you. Nothing in the Stringwood has bothered you in weeks.",
            "The villages tell stories about a gold shadow that moves ahead of a "
            "coder. They do not mention the coder.",
        ),
        passives={
            2: {"rank_grace": 0.08},
            3: {"rank_grace": 0.15},
            4: {"rank_grace": 0.2, "crit_bonus": 0.15},
        },
        discovery=Discovery(
            region="stringwood_labyrinth",
            arrival="STALK",
            where="Wherever you were four minutes ago. The anagram groves, mostly, "
                  "at the edge of what you can see, where three different paths "
                  "spell the same word.",
            how="You do not find this one, and it does not answer a deed. It has "
                "been behind you since the second grove and it picks its own "
                "moment: four sightings, each one closer to the path than the "
                "last, and then three encounters in a row cleared with nothing "
                "cast, because it will not walk beside somebody who is still "
                "hesitating.",
            needs=(
                {"kind": "sighted", "pet": "jaguar", "count": 4},
                {"kind": "no_hint_streak", "count": 3},
            ),
            first_words="Four times you looked, and four times I let you. Three in "
                        "a row without stopping to think. That is the only "
                        "invitation I answer.",
        ),
    ),

    Pet(
        id="velociraptor", name="SICKLE", species="Velociraptor",
        tier="ADEPT", skill="TESTING", hint_kind="EDGE_CLASS",
        sprite="raptor", colour="#c4553f",
        tagline="Edge cases, hunted at speed and from an angle you were not "
                "watching.",
        blurb="Waist-high, feathered, and entirely uninterested in the ordinary "
              "case. It has been following you since the Hydra, largely because you "
              "skipped a duplicate and it has not forgotten.",
        method="It names the CLASS of input that is going to break you — empty, "
               "single, duplicate, boundary, adverse order. Never a test case with "
               "an expected value beside it. The input is the warning. What it does "
               "to your code is still yours to find out.",
        triggers=(
            Trigger("hidden_trial_failed", 1,
                    line="Something got in. Something always gets in."),
            Trigger("weakness_survived", 1,
                    line="There. That is the one that has been circling you."),
            Trigger("failure_category", 1, "EDGE_CASE",
                    line="The ordinary case is fine. The ordinary case was never "
                         "the threat."),
        ),
        hints={
            "EMPTY": "Empty. Nothing in it at all. Your first index does not exist, "
                     "and neither does your max().",
            "SINGLE": "One element. Your two markers start on the same square and "
                      "your loop body may never run once.",
            "DUPLICATE": "Duplicates. Equal values at different positions. Something "
                         "of yours is about to quietly collapse them together.",
            "NEGATIVE": "Negatives. Every accumulator you seeded with zero is now "
                        "lying to you.",
            "ZERO": "Zero. It is falsy, it divides badly, and `[:-0]` is not the "
                    "slice you thought you were asking for.",
            "BOUNDARY": "The exact limit. Equal to k, not less than it. One "
                        "comparison in there has the wrong strictness.",
            "SCALE": "The large one. It works, it works, it works, and then it takes "
                     "nine seconds and dies in front of an examiner.",
            "UNIFORM": "Every element identical. Does your comparison still make "
                       "progress when nothing is ever greater than anything.",
            "ORDER": "Adverse order. Already sorted, exactly reversed, and shuffled "
                     "are three different animals wearing one name.",
        },
        fallback="Something is going to walk in here that you have not pictured: "
                 "nothing, one thing, or the same thing twice. Pick whichever you "
                 "would least like to receive.",
        idle=(
            "Empty list. Empty list. Have you considered the empty list.",
            "Somewhere in the hidden trials is an input that hates you personally.",
            "Your code is fine. I am asking about the other inputs. All of them.",
        ),
        on_intervene="Something is coming in here that you have not planned for.",
        on_cleared="It held. I went round the corners myself.",
        on_failed="I mention the duplicates a great deal. I am aware that I do this.",
        above_tier="I do not know what the corners of this one are. I will not "
                   "point you at a corner I cannot see.",
        on_dismiss="The treeline. At an angle. As usual.",
        on_recall="Something got in while I was away, then.",
        on_faint="It drops. Nothing is circling anything any more, and the "
                 "quiet is worse than the circling was.",
        on_wake="Up, and already watching the one corner of the room you are "
                "not.",
        bond_lines=(
            "It keeps to the treeline, at an angle, always at an angle.",
            "It sleeps near the fire now, facing outward, which is not restful for "
            "anyone.",
            "It has started announcing the input class before the fight begins.",
            "It goes in first and comes back with the thing that would have broken "
            "you, carried carefully.",
            "The Coliseum keeps a list of inputs it is not allowed to use. It is "
            "titled after this animal.",
        ),
        passives={
            2: {"probe_charges": 1},
            3: {"reveal_category": 1},
            4: {"probe_charges": 2, "probe_reveal_value": 1},
        },
        discovery=Discovery(
            region="array_caverns",
            arrival="BOSS",
            where="The scree slope below the Hydra's hall, where something has been "
                  "pacing in the same three-metre line for weeks.",
            how="This one is taken off a boss rather than found. Put the Three-Sum "
                "Hydra down with nothing cast — every head of it, including the "
                "duplicate you were hoping nobody would check — and it comes up "
                "the scree while the hall is still settling. Ten correct probes "
                "across the realms is the other half of the price: it respects "
                "exactly one thing, and that is a prediction that came true.",
            needs=(
                {"kind": "boss_unaided", "boss": "three_sum_hydra"},
                {"kind": "probes_correct", "count": 10},
            ),
            first_words="You skipped the duplicates on purpose. Ten times you said "
                        "what would happen, and ten times it happened. I am coming "
                        "with you.",
        ),
    ),

    Pet(
        id="penguin", name="PIVOT", species="Penguin",
        tier="ADEPT", skill="SORTING", hint_kind="DATA_STRUCTURE",
        sprite="penguin", colour="#7ec8ff",
        tagline="Ordering, queueing, and the correct container for the question.",
        blurb="A penguin from the flooded lower galleries of the mines, where the "
              "water never warmed up after the Null King came through. It has been "
              "standing in an orderly line by itself for some years.",
        method="It does not tell you the algorithm. It points at the structure the "
               "question wants — the dict, the deque, the heap, the two integers — "
               "because choosing the container is the decision that makes every "
               "line after it cheap or expensive.",
        triggers=(
            Trigger("failure_category", 1, "WRONG_DATA_STRUCTURE",
                    line="The container cannot answer the question you keep asking "
                         "it."),
            Trigger("timeout_failures", 1,
                    line="Correct, and standing in the wrong queue."),
            Trigger("failed_attempts", 3,
                    line="Before the fourth attempt. What are you actually storing."),
        ),
        hints={
            "HASH_MAP": "A dict, keyed by the thing you keep asking about. The value "
                        "is whatever you wish you already knew.",
            "SET": "A set. The question is membership, and a list makes that "
                   "question expensive for no reason.",
            "SLIDING_WINDOW": "A dict of counts for what is inside the stretch, plus "
                              "two integers for its ends.",
            "TWO_POINTER": "Two integers. No container at all. That is the whole "
                           "point of this family.",
            "STACK": "A list you only ever touch at the end.",
            "QUEUE": "A deque. Taking from the front of a list is the part that "
                     "will time out.",
            "BFS": "A deque for the frontier, and a set for what you have already "
                   "admitted to it.",
            "DFS": "A set for visited, and either the call stack or a list standing "
                   "in for it.",
            "TREE": "No container, if the recursion carries what it needs. A deque, "
                    "if you are going level by level.",
            "HEAP": "A heap. Sorting the whole collection buys you an order you are "
                    "going to throw away.",
            "BINARY_SEARCH": "Nothing new. Two integers and the list you were handed.",
            "PREFIX_SUM": "One extra list, one longer than the input, holding totals.",
            "SORTING": "The list itself, plus a key function. The key is where the "
                       "thinking lives.",
            "DP": "A table. One dimension for each thing that varies, and not one more.",
            "INTERVALS": "The list sorted by start, and one pair held aside as the "
                         "stretch you are still building.",
            "MATRIX": "The grid, and a second grid only if you cannot survive "
                      "writing into the first.",
            "DESIGN": "Two structures. One for lookup, one for order. Neither does "
                      "both well.",
            "GREEDY": "One accumulator and a sort. If you are reaching for a table, "
                      "this is not the greedy family.",
            "STRING": "A counter over the characters, or an index. Rarely anything "
                      "larger than that.",
        },
        fallback="Name the question you ask most often inside the loop. Then pick "
                 "the container that answers that exact question in one step.",
        idle=(
            "Everything is easier in the right order.",
            "You have chosen a container. I am waiting to hear why.",
            "There is a queue for this. There is a queue for everything.",
        ),
        on_intervene="You are asking the data a question it cannot answer in that "
                     "shape.",
        on_cleared="Right structure. Everything downstream of that was cheap.",
        on_failed="The structure was not the problem this time. That is unusual, and "
                  "I have noted it.",
        above_tier="I do not know what this one wants held. Naming a container at "
                   "random would cost you an hour, and I would rather not.",
        on_dismiss="I will be by the lift. There is a queue.",
        on_recall="You have rejoined the queue. Third, as it happens.",
        on_faint="It goes over on its side and stays there, out of order, "
                 "which is the part it would mind most.",
        on_wake="Upright, filed, and back in position, resuming as though "
                "the order had never once broken.",
        bond_lines=(
            "It stands a polite distance away, facing the same direction as you.",
            "It has begun walking in your wake, precisely in your footprints.",
            "It reorganises your pack while you sleep. The pack is better now.",
            "It arranges the party before a fight without being asked, and the "
            "party has stopped objecting.",
            "The mines run their lifts on a schedule it wrote. Nobody can find the "
            "document.",
        ),
        passives={
            2: {"loot_luck": 0.1},
            3: {"loot_luck": 0.2},
            4: {"loot_luck": 0.3, "shrine_bonus": 0.2},
        },
        discovery=Discovery(
            region="stack_queue_mines",
            arrival="DELVE",
            where="The flooded third gallery, past the point where the ore carts "
                  "stop being unloadable from the top.",
            how="Nothing brings this one to you and nobody sells it. Go down. Take "
                "the Ninth Cart, under the Stack and Queue Mines, to its third "
                "level and come back out — and be able to say what the carts are "
                "holding before you look, four times, correctly. It is standing "
                "on the one you called.",
            needs=(
                {"kind": "dungeon_depth", "dungeon": "ninth_cart", "depth": 3},
                {"kind": "puzzle_kind", "puzzle": "STATE_PREDICT", "count": 4},
            ),
            first_words="You went in last and came out first. I appreciate a "
                        "discipline about order.",
        ),
    ),

    # ---- MASTER ----------------------------------------------------------
    Pet(
        id="nautilus", name="CHAMBER", species="Nautilus",
        tier="MASTER", skill="RECURSION", hint_kind="DECOMPOSE",
        sprite="nautilus", colour="#a89aff",
        tagline="Splitting the problem into a smaller copy of itself, and trusting "
                "the copy.",
        blurb="A spiral shell in the spring at the heart of the innermost clearing, "
              "each chamber an exact smaller copy of the one outside it. It was "
              "built by something that solved this problem long before you arrived.",
        method="It asks what the smaller version of this problem is, and refuses to "
               "answer its own question. That refusal is the teaching: the base "
               "case and the shrinking step have to come from you or they will not "
               "come at all.",
        triggers=(
            Trigger("failure_category", 1, "RECURSION",
                    line="The smallest case, or the shrinking step. It is always "
                         "one of the two."),
            Trigger("failure_category", 1, "TREE_TRAVERSAL",
                    line="You are holding the whole tree in your head. Hold one node."),
            Trigger("stuck_seconds", 240,
                    line="Assume a smaller one of these is already solved. Now what "
                         "is left."),
        ),
        hints={
            "RECURSION": "What is the smallest version of this you could answer "
                         "without thinking at all. Write that case down first, then "
                         "assume the smaller call already works.",
            "TREE": "Ask the question of the left branch and of the right branch, "
                    "and treat both answers as given. Your only job is what THIS "
                    "node adds to them.",
            "DFS": "The route from here is this one step, plus the route from "
                   "wherever that step lands. There is nothing else in it.",
            "DP": "Name the subproblem in one sentence containing the word 'best'. "
                  "If you cannot say it, the table has the wrong dimensions.",
            "BACKTRACKING": "Choose, go deeper, then put it back exactly as you "
                            "found it. The putting-back is the step everyone skips.",
            "STRING": "Split it into the first character and everything after it. "
                      "Ask whether an answer for the rest would help you.",
            "ARRAY": "Split it down the middle. If having both halves solved would "
                     "give you the answer, that is the shape of this.",
            "MATRIX": "A cell's answer depends on its neighbours' answers. Decide "
                      "which neighbours, and in what order they must already be known.",
            "GRAPH": "One node, its neighbours, and the promise that each neighbour "
                     "will do for itself exactly what you are doing here.",
            "BINARY_SEARCH": "Half of it is gone after the first look. What remains "
                             "is the same problem, smaller. That is the only claim "
                             "you need to hold.",
        },
        fallback="Assume a smaller version of this problem is already solved and "
                 "sitting in front of you. What would you still have to do.",
        idle=(
            "Every chamber is the last chamber, only smaller.",
            "The shell was not planned. It was one rule, applied until it ran out "
            "of animal.",
            "You are trying to hold all of it at once. Hold one node.",
        ),
        on_intervene="You are carrying the whole structure in your head. Put it down.",
        on_cleared="Base case, then trust. That is all it ever was.",
        on_failed="The smaller call came back with the wrong thing. Start there, "
                  "not at the top.",
        above_tier="There is no smaller copy of this that I can see, and I am the "
                   "one who is supposed to see them.",
        on_dismiss="The spring, then. It is where I was.",
        on_recall="You have come all the way in again. Hold one node.",
        on_faint="The shell closes. There is no smaller copy of it left open "
                 "to ask anything of.",
        on_wake="The shell opens one chamber at a time, because that is how "
                "it does everything, including this.",
        bond_lines=(
            "It turns slowly in the spring and does not acknowledge you.",
            "It has moved to the shallow end of the pool, which is as far as it "
            "will come.",
            "It surfaces when you start a recursive fight and stays up until you "
            "finish.",
            "You carry it now, in water, and the spiral is one chamber longer than "
            "it was.",
            "Druids come to the clearing to look at an empty spring and are told a "
            "shell went travelling.",
        ),
        passives={
            2: {"mana_max": 6},
            3: {"mana_regen": 3},
            4: {"mana_max": 12, "mana_regen": 4},
        },
        discovery=Discovery(
            region="recursive_forest",
            arrival="QUEST",
            where="The spring at the centre of the innermost clearing — the copy of "
                  "the forest that has no further copy inside it.",
            how="Somebody sends you for this one. Take the Innermost Grove off the "
                "forest's own board and walk it all the way in, then survive what "
                "the forest lays for you on the way back out. The errand is the "
                "condition. The shell is what is turning slowly in the spring at "
                "the bottom of it, and it only exists for somebody who reached the "
                "base case honestly.",
            needs=(
                {"kind": "quest_done", "quest": "forest_inner_grove"},
                {"kind": "retest_survived", "skill": "RECURSION", "count": 1},
            ),
            first_words="You went all the way in and came all the way back out "
                        "carrying something. That is the only trick there is.",
        ),
    ),

    Pet(
        id="crow", name="WITNESS", species="Crow",
        tier="MASTER", skill="TESTING", hint_kind="MISSING_TEST",
        sprite="crow", colour="#9b96b8",
        tagline="The test you did not write, described but never handed to you.",
        blurb="It perches on the broken junctions of the Wastes and keeps a count "
              "of things. Not treasure. Occurrences. It has been keeping this count "
              "since before the roads out here stopped going anywhere.",
        method="Where SICKLE names the input that will hurt, WITNESS names the TEST "
               "you never wrote — its shape, its size, its ugly middle case. The "
               "expected value stays yours to work out, because working it out is "
               "the exercise.",
        triggers=(
            Trigger("hidden_trial_failed", 2,
                    line="Twice now, the hidden trials found it and you did not."),
            Trigger("failure_category", 1, "TESTING",
                    line="The break was always there. Nothing you wrote went looking."),
            Trigger("failure_category", 2, "EDGE_CASE",
                    line="Second time. Write it down as a test before you fix it."),
        ),
        hints={
            "EMPTY": "Write the empty case down as a test before you fix anything. "
                     "One line, no fixture, and it catches a whole family.",
            "SINGLE": "A test with exactly one element. Eight characters, and it "
                      "catches most loop bugs ever written.",
            "DUPLICATE": "A test where two values are equal and their positions are "
                         "not. Decide what you want it to do BEFORE you run it.",
            "BOUNDARY": "Three tests: one either side of the limit, and one exactly "
                        "on it. The middle one is the one nobody writes.",
            "SCALE": "A generated input of the size the constraints actually "
                     "promise. Not ten. The number printed in the statement.",
            "NEGATIVE": "One negative value in an otherwise entirely ordinary input.",
            "ZERO": "Zero as a value, and zero as a parameter. They break different "
                    "lines and they deserve separate tests.",
            "UNIFORM": "An input where every element is identical. Cheap to write, "
                       "and extremely unkind to comparisons.",
            "ORDER": "The same input sorted, reversed, and shuffled. Three tests, "
                     "one list, and they fail for three different reasons.",
            "TESTING": "List the inputs you are quietly hoping nobody passes in. "
                       "That list is your test suite, and you already have it.",
            "DESIGN": "Test the sequence, not the operations. Add, evict, add the "
                      "same key again, then ask what the order is.",
            "SIMULATION": "Test one step, then two steps, then the step where the "
                          "rule changes. Everything after that is arithmetic.",
        },
        fallback="Name the input you are quietly hoping nobody passes in. That one. "
                 "Write it down as a test now, while you still remember why you "
                 "were worried.",
        idle=(
            "You have written no tests. I am not judging. I am recording.",
            "Everything that has ever broken here broke twice. I have the count.",
            "The examiner will ask how you would test it. It is worth having an "
            "answer.",
        ),
        on_intervene="There is a test you have not written, and it is the one that "
                     "matters.",
        on_cleared="It survived the test I would have written. I will write another.",
        on_failed="Good. Now write that failure down as a test, so that it cannot "
                  "happen to you twice.",
        above_tier="I have no count for this one. I will not describe a test for "
                   "something I have never watched break.",
        on_dismiss="I will be on a ruin. I am on all of them.",
        on_recall="You came back. I kept counting while you were gone.",
        on_faint="It stops counting. That is the loudest thing it has ever "
                 "done.",
        on_wake="It picks up at the number it stopped on. It did not lose "
                "the count, and it would like you to know that.",
        bond_lines=(
            "It watches from a broken arch and leaves when you look directly at it.",
            "It has started leaving small objects on your pack, which is a crow's "
            "idea of a contract.",
            "It names the missing test before your suite has finished running.",
            "It keeps your failure log for you, and is better at it than you were.",
            "Every ruin in the Wastes has one crow on it. There is one crow. It is "
            "on all of them.",
        ),
        passives={
            2: {"retest_bonus": 0.2},
            3: {"retest_bonus": 0.35},
            4: {"retest_bonus": 0.5, "xp_bonus": 0.15},
        },
        discovery=Discovery(
            region="graph_wastes",
            arrival="BARTER",
            where="The broken junction with the cairn on it — always on a road you "
                  "have already walked, never on one you have not.",
            how="There is nobody out here to pay and it would not take gold "
                "anyway. Leave one bright thing on the cairn, because it is a crow "
                "and it has opinions about bright things, and then go away long "
                "enough that it can come down without being watched. It takes the "
                "trade. After that it wants five testing encounters cleared "
                "unaided, because a witness that has not seen you work is no use "
                "to anybody.",
            needs=(
                {"kind": "trade_done", "trade": "wastes_cairn",
                 "gold": 0, "goods": "one bright thing off a dead road"},
                {"kind": "skill_unaided", "skill": "TESTING", "count": 5},
            ),
            first_words="You left something on the stone and did not stand over it "
                        "waiting to be thanked. Five clean ones since. I have been "
                        "counting since before these were ruins.",
        ),
    ),

    Pet(
        id="tortoise", name="HALT", species="Tortoise",
        tier="MASTER", skill="BIG_O", hint_kind="COST_SHAPE",
        sprite="tortoise", colour="#6b8f3f",
        tagline="What your approach costs, said out loud, before the clock says it "
                "for you.",
        blurb="Older than the Complexity Tower it lives in, and unimpressed by it. "
              "It has climbed four of the tower's floors. It intends to climb the "
              "fifth. It is not in any difficulty.",
        method="It prices what you have written — the shape of the work, not the "
               "fix. Correct and unaffordable is the most common way a good "
               "learner loses, and it is the one nobody notices while it is "
               "happening.",
        triggers=(
            Trigger("perf_trial_failed", 1,
                    line="Correct. And the trial still ended you."),
            Trigger("timeout_failures", 1,
                    line="It was not wrong. It was expensive."),
            Trigger("failure_category", 1, "INEFFICIENT_ALGORITHM",
                    line="Count the work per element. Now count the elements."),
        ),
        hints={
            "HASH_MAP": "You are paying for a whole scan to answer a question a "
                        "memory answers once. Count how many times you walk the "
                        "same list.",
            "SLIDING_WINDOW": "Rebuilding the stretch from scratch at every position "
                              "is the quadratic part. The stretch is supposed to "
                              "remember what it already contains.",
            "TWO_POINTER": "Every pair of every element is the expensive shape. Two "
                           "markers is the cheap one, and sorting to reach it is "
                           "affordable.",
            "BINARY_SEARCH": "A straight scan across sorted data is paying full "
                             "price for something already organised.",
            "SORTING": "Sorting costs n log n once. Sorting inside the loop costs "
                       "n log n every time round the loop.",
            "DP": "Count the distinct calls your recursion makes. If the same "
                  "arguments keep arriving, you are buying the same answer twice.",
            "RECURSION": "Each level multiplies by its branching factor. Two calls "
                         "per level across n levels is not a small number, and it "
                         "is not a slow-growing one.",
            "MATRIX": "Rows times columns is the floor. Anything above that is you "
                      "visiting cells more than once.",
            "BFS": "Nodes plus edges is the honest price. If it is worse than that, "
                   "something is being admitted to the frontier twice.",
            "DFS": "Nodes plus edges, once, if the visited set is doing its job. "
                   "Without it there is no upper bound at all.",
            "HEAP": "Log n for each push and each pop. A full sort at every step is "
                    "the thing a heap exists to replace.",
            "STRING": "Building a string with `+=` inside a loop copies the whole "
                      "string every time round.",
            "PREFIX_SUM": "Each range question is costing you the length of the "
                          "range. It could be costing you one subtraction.",
            "GREEDY": "One pass after one sort. If your cost is worse than the sort, "
                      "you are doing something other than being greedy.",
            "INTERVALS": "The sort dominates. If the merging step is costing more "
                         "than the sort did, the merge is re-scanning.",
        },
        fallback="Count the work per element. Count the elements. Multiply the two "
                 "and hold the number up against the input size the statement "
                 "promised you.",
        idle=(
            "Count the work per element. Out loud, if that helps.",
            "I have climbed four floors of this tower. I am not behind schedule.",
            "Sequential work adds. Nested work multiplies. Everything else is detail.",
        ),
        on_intervene="Correct is not the same as affordable.",
        on_cleared="That will still finish when the input is a million long.",
        on_failed="It was never the speed. Look again at what it computes.",
        above_tier="I cannot price this. I would be guessing at the shape of the "
                   "work, and a guessed price is worse than no price.",
        on_dismiss="I will be on the stair. Where else.",
        on_recall="You are back on the landing. Count the work per element.",
        on_faint="It pulls in, and nothing whatsoever about that is fast.",
        on_wake="Out again, at precisely the speed it went in, which is the "
                "only speed it has.",
        bond_lines=(
            "It is on the stair above you and has been for some time.",
            "It has begun waiting at the landings, which you choose to read as "
            "companionship.",
            "It prices your approach before you have finished describing it.",
            "It reaches the floor you are on before you do. You have stopped asking "
            "how.",
            "The Tower's upper floors are said to be unreachable by brute force. "
            "There are tracks on all of them.",
        ),
        passives={
            2: {"perf_insight": 1},
            3: {"perf_insight": 1, "rank_grace": 0.1},
            4: {"perf_insight": 1, "xp_bonus": 0.2},
        },
        discovery=Discovery(
            region="complexity_tower",
            arrival="TRIAL",
            where="The fifth landing, where the stair stops being climbable by "
                  "anyone in a hurry.",
            how="The tower asks one question the entire way up, which is what your "
                "approach costs. Answer it twice over: five performance trials "
                "cleared, and three boards of snippets matched to the prices they "
                "actually charge. The tortoise is on the fifth landing. It has "
                "always been on the fifth landing. Arriving there without brute "
                "force is the whole of the condition.",
            needs=(
                {"kind": "perf_cleared", "count": 5},
                {"kind": "puzzle_kind", "puzzle": "COMPLEXITY_MATCH", "count": 3},
            ),
            first_words="You arrived on the fifth floor without brute force. Most "
                        "people arrive out of breath and on the second.",
        ),
    ),

    # ---- LEGENDARY: the starter, returned ---------------------------------
    Pet(
        id=RETURN_ID, name="BARROW", species="Boar",
        tier="LEGENDARY", skill="RECALL", hint_kind="PRIOR_WORK",
        sprite="boar_great", colour="#7a5c46",
        tagline="Everything you already paid for, kept by something that was paid "
                "for once itself.",
        blurb="A boar the size of a cart, standing on a lit tile at the bottom of "
              "the Hall. Its tusks have grown through its own jaw and out again. "
              "One ear. It is the colour of the inside of a closed thing. Whatever "
              "happened to it down here, it stopped being an animal that offers you "
              "small words and became one that keeps what was done in front of it, "
              "which in this Hall is the only power there is.",
        method="It names a family of problem you have ALREADY cleared that has this "
               "one's shape. It does not say what you wrote, because it never saw "
               "what you wrote — it saw that the tile went out lit. Help made "
               "entirely out of your own history is the only kind that gets cheaper "
               "the longer you play, which is the reward for having played.",
        triggers=(
            Trigger("idle_before_first_submit", 180,
                    line="You have crossed this before. Not this room. This shape."),
            Trigger("failure_category", 1, "PATTERN_NOT_RECOGNIZED",
                    line="You knew this once. The tile is still lit."),
            Trigger("stuck_seconds", 220,
                    line="Stop. Go back through what you have already closed."),
        ),
        hints={
            "LANGUAGE": "You cleared the village drills. This is those, with a "
                        "longer sentence around it and nothing new inside it.",
            "HASH_MAP": "The counting tiles, up in the Highlands. One key, one "
                        "answer, no scan. You lit those and they are still lit.",
            "SET": "The membership tiles. You have decided, more than once, that "
                   "the question was only ever whether you had seen it.",
            "SLIDING_WINDOW": "The Long Draw. One frame, never restarted. You walked "
                              "the length of it.",
            "TWO_POINTER": "The bridge with two lanterns. Both ends, moving inward, "
                           "along something already in order.",
            "STACK": "The carts. Unloaded from the top, in the mines, and you did "
                     "that without being told twice.",
            "QUEUE": "The lift. Oldest first. Same building, opposite rule.",
            "BFS": "The rings of light in the Wastes. Everything one step out, then "
                   "everything two. You have done this on a map.",
            "DFS": "The committed path. All the way down, then take back the last "
                   "choice. You have unwound one of these before.",
            "TREE": "The canopy. One node, two children, and both of their answers "
                    "treated as already given.",
            "RECURSION": "The innermost clearing. The smallest case first, then "
                         "trust. You reached the base case honestly once.",
            "BINARY_SEARCH": "The Doubling Stair. Half of it gone at every look. "
                             "Fifty floors, six steps.",
            "MATRIX": "The Citadel floor, turning a quarter. Rows and columns, and "
                      "the arithmetic between them.",
            "HEAP": "The best-so-far tiles. You needed the extreme value over and "
                    "over and never once needed the order.",
            "PREFIX_SUM": "The running totals. A range as the difference of two "
                          "numbers you were already holding.",
            "SORTING": "Order first. You have solved a dozen of these by putting "
                       "the thing in order and finding the question had gone.",
            "DP": "This Hall. The lit tiles. The same small question arriving over "
                  "and over, and you refusing to pay for it twice.",
            "GREEDY": "The local-choice tiles. Best step available, never revisited, "
                      "and you proved to yourself once that it held.",
            "INTERVALS": "The overlapping stretches. Sorted by start, one live "
                         "stretch carried.",
            "STRING": "The Stringwood. Walking characters is walking a list, and "
                      "nobody has had to tell you that since.",
            "ARRAY": "The numbered alcoves. One walk, arithmetic on the positions, "
                     "and the last one always one short of the count.",
            "DESIGN": "The Editor. Two structures, each doing the one thing it is "
                      "good at, and you argued yourself into that pairing.",
            "SIMULATION": "The rules as written, in the order written. You have been "
                          "doing this since the barrow and it has never once "
                          "required cleverness.",
        },
        fallback="You have closed something with this shape in it before. Go back "
                 "through what you have already lit, find the one that felt like "
                 "this, and ask what was the same about it.",
        idle=(
            "The tiles keep what was done on them. They do not keep who did it.",
            "I was small and knew only words. You were slow and knew only English. "
            "We have both been altered.",
            "Nothing down here is new. That is the entire lesson of the Hall and it "
            "took me some years.",
        ),
        on_intervene="You have crossed this shape before. The tile is still lit.",
        on_cleared="Lit again. It will cost you nothing the next time either.",
        on_failed="Then it was not that shape. Go further back.",
        # It covers every depth, so this line exists for the one case that can
        # still produce it: content whose difficulty the engine could not
        # classify at all.
        above_tier="I do not know what this room is. Nothing here has been lit, by "
                   "you or by anybody.",
        on_dismiss="I will be on the tile. It is lit. I can wait on a lit tile "
                   "indefinitely, and you know exactly how well I can wait.",
        on_recall="You came back down. You always did come back down.",
        on_faint="It lies down on the tile it was standing on. The tile "
                 "stays lit, which is the only mercy in this room.",
        on_wake="Up, and over to the next lit tile, waiting there as if "
                "nothing had been interrupted at all.",
        bond_lines=(
            "It stands on its tile and does not look at you, which you have decided "
            "not to read anything into.",
            "It walks out of the Hall behind you. It fits through the door. Barely, "
            "and with some scraping.",
            "It has begun naming the old tile before you have finished reading the "
            "new one.",
            "It sleeps across the doorway of wherever you stop, and nothing has come "
            "through a doorway since.",
            "It answers to STUB. It has answered to STUB the entire time and nobody "
            "asked it to.",
        ),
        passives={
            0: {"rank_grace": 0.1},
            2: {"rank_grace": 0.15, "retest_bonus": 0.25},
            3: {"rank_grace": 0.2, "retest_bonus": 0.4, "stamina_max": 6},
            4: {"rank_grace": 0.25, "retest_bonus": 0.5, "stamina_max": 10,
                "second_wind": 1},
        },
        discovery=Discovery(
            region="dp_ruins",
            arrival="RITE",
            where="The fourth floor of the Hall of Lit Tiles, on a tile you lit "
                  "yourself a long time ago and have not thought about since.",
            how="Take the Hall of Lit Tiles to its fourth floor carrying the closed "
                "half-ring, with the barrow's debt behind you and RECALL brought up "
                "to something worth remembering. It will not come when you call the "
                "name. Put the ring down on the tile.",
            needs=(
                {"kind": "starter_fallen"},
                {"kind": "dungeon_depth", "dungeon": RETURNS_AT_DUNGEON, "depth": 4},
                {"kind": "skill_mastery", "skill": "RECALL", "value": 40},
            ),
            first_words="I do not know your face. I know that ring, and I know what "
                        "it cost to close it. Pick it up. We are going back out.",
        ),
        lineage=STARTER_ID,
    ),

    # ---- HIDDEN ----------------------------------------------------------
    Pet(
        id=HIDDEN_ID, name="MIMIC", species="Mimic Octopus",
        tier="HIDDEN", skill="DESIGN", hint_kind="MIRROR",
        sprite="octopus", colour="#c98f6b",
        tagline="Whichever of the others you needed, at that one's price.",
        blurb="Something the colour of wet stone unfolds off the causeway wall and "
              "turns out to have been an arm, and then eight. It has been every "
              "animal on this list at least once, badly, for about four seconds "
              "each, and nobody taught it any of them. It is two years old. It will "
              "be dead within the year and it knows that, which is most of why it "
              "does not waste your time.",
        method="It works out which of the others belonged in this room and becomes "
               "that one: the family, the syntax, the structure, the defect class, "
               "the cost, the input that hurts. It invents no new permission and it "
               "takes no discount — it pays the worst price any of them pay, every "
               "time, because a companion that is all of them must not also be the "
               "cheapest of them.",
        triggers=(
            Trigger("repeat_category", 2,
                    line="Twice the same way. I will be whichever of them you are "
                         "missing."),
            Trigger("failed_attempts", 3,
                    line="Three. I have watched three of these go past."),
            Trigger("idle_before_first_submit", 200,
                    line="You have not moved. Neither have I, but that is different."),
            Trigger("stuck_seconds", 230,
                    line="Something should have been standing here. It is not. "
                         "I will do."),
        ),
        # Empty on purpose: MIRROR borrows the body from whichever companion the
        # room actually wanted. A thirteenth set of family lines here would be a
        # second opinion about what a family is, and two opinions drift.
        hints={},
        fallback="Something in this room has a name you already know — the family, "
                 "the container, the kind of broken, or the input you are hoping "
                 "nobody sends. Work out which of those four is missing, and go and "
                 "get it yourself.",
        idle=(
            "I have been three other animals this morning. None of them well.",
            "Two years is the whole of it. I am not spending any of it waiting for "
            "you to ask.",
            "Nobody looks at the wall. In nine hundred years nobody has looked at "
            "the wall.",
        ),
        on_intervene="Whoever should have been standing here is not. I will do.",
        on_cleared="That is what one of the others would have got out of you. I "
                   "will take it.",
        on_failed="Then I was the wrong one. There are eleven of them and I have "
                  "been most of them.",
        above_tier="Nothing I can imitate belongs in this room. That has happened "
                   "twice in my life and I did not care for it either time.",
        on_dismiss="Back to the wall. You will not find me again by looking.",
        on_recall="You remembered which stone. Very few do.",
        on_faint="Whatever it was imitating, it stops imitating. What is "
                 "left on the stone is a small grey thing with no opinion "
                 "about anything.",
        on_wake="It takes a colour back, then a shape, then whichever animal "
                "you were short of this morning.",
        bond_lines=(
            "It is on the causeway wall. It has always been on the causeway wall.",
            "It comes off the wall when you pass, which is a considerable "
            "concession from something whose entire profession is not doing that.",
            "It has started becoming the right animal before you have finished "
            "being wrong.",
            "It rides in a sealed jar of marsh water and rearranges the contents of "
            "your pack through the lid, which should not be possible.",
            "Three regions have a story about a companion nobody can describe "
            "twice. All three descriptions are correct.",
        ),
        passives={
            1: {"probe_charges": 1},
            2: {"probe_charges": 1, "hint_discount": 0.2},
            3: {"probe_charges": 2, "hint_discount": 0.3, "reveal_category": 1},
            4: {"probe_charges": 2, "hint_discount": 0.35, "reveal_category": 1,
                "loot_luck": 0.25},
        },
        discovery=Discovery(
            region="sliding_window_marsh",
            arrival="VIGIL",
            where="The causeway wall of the Long Draw, below the waterline, on a "
                  "stone that is not a stone.",
            how="Send your companion away, walk into the Long Draw alone, and clear "
                "two of its floors at depth four or deeper carrying nothing and "
                "casting nothing — no companion in the field, no spell, no item. It "
                "is looking for the one person who arrived with no help at all, and "
                "it is not going to find many.",
            needs=(
                {"kind": "solo_floor", "count": 2},
                {"kind": "dungeon_depth", "dungeon": "the_long_draw", "depth": 4},
            ),
            first_words="You came down here with nothing. Do you know how rarely "
                        "that happens. I have been on this wall a very long time "
                        "waiting for somebody who did not need me.",
        ),
    ),
)

BY_ID = {pet.id: pet for pet in PETS}
PET_IDS = tuple(pet.id for pet in PETS)
BY_SKILL: dict = {}
BY_TIER: dict = {}
for _pet in PETS:
    BY_SKILL.setdefault(_pet.skill, []).append(_pet.id)
    BY_TIER.setdefault(_pet.tier, []).append(_pet.id)
del _pet


def starter() -> Pet:
    return BY_ID[STARTER_ID]


# Every trade on the roster, keyed by trade id, so the vendor that takes the
# money never has to read a discovery clause to find out what the price is.
# `gold` of zero is a BARTER: goods are left and nothing is paid, which is a
# different transaction and reads as one.
TRADES: dict = {}
for _p in PETS:
    for _c in (_p.discovery.needs if _p.discovery else ()):
        if _c.get("kind") == "trade_done":
            TRADES[_c["trade"]] = {
                "trade": _c["trade"], "pet": _p.id, "name": _p.name,
                "species": _p.species, "region": _p.discovery.region,
                "gold": int(_c.get("gold", 0)),
                "goods": _c.get("goods", ""),
                "where": _p.discovery.where,
                "barter": not int(_c.get("gold", 0)),
            }

# Every animal that has to be SEEN before it will come near, with how many
# sightings it wants. The overworld calls `sight()` when the player is in the
# right place; this table is what tells it which places those are.
SIGHTED: dict = {}
for _p in PETS:
    for _c in (_p.discovery.needs if _p.discovery else ()):
        if _c.get("kind") == "sighted":
            SIGHTED[_c.get("pet", _p.id)] = {
                "pet": _p.id, "name": _p.name, "species": _p.species,
                "region": _p.discovery.region, "where": _p.discovery.where,
                "needs": int(_c.get("count", 1)),
            }
del _p, _c


# --------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------

def available_in(mode: str, region_id: str = "", *, sealed: bool = False) -> bool:
    """May a pet speak at all right now.

    `sealed` is `finalexam.sealed(encounter, "PET")`, computed by the caller.
    This module does not reach for the seal itself, because the seal is decided
    in exactly one place and a second evaluation here would be a second place.
    What this function owns is the part finalexam does not know about: two
    regions whose own descriptions promise that nothing helps you there.

    The Timed Practical Mode line below is deny-only and redundant with the seal. It
    stays because it can only ever refuse MORE than finalexam refuses and never
    less, so it is a guard rail on a caller who forgot to pass `sealed` rather
    than a second policy about who may be helped.
    """
    from .config import MODE_INTERVIEW
    if sealed:
        return False
    if mode == MODE_INTERVIEW:
        return False
    return region_id not in SILENCED_REGIONS


# Which part of the redacted encounter view each kind of pet reads. None of these
# fields can carry an answer: a pattern name, a weakness class and a failure
# category are all vocabulary the game already shows the player elsewhere.
KEYED_BY = {
    "KEYWORD": "pattern",
    "ALGORITHM_FAMILY": "pattern",
    "EXACT_SYNTAX": "pattern",
    "RESTATEMENT": "pattern",
    "DATA_STRUCTURE": "pattern",
    "COST_SHAPE": "pattern",
    "DECOMPOSE": "pattern",
    "PRIOR_WORK": "pattern",
    "MIRROR": "pattern",
    "EDGE_CLASS": "weakness",
    "MISSING_TEST": "weakness",
    "DEFECT_CLASS": "category",
}

# Which companion MIMIC becomes, in the order it decides. A named failure
# category is the most specific thing the redacted view can carry, so it wins; a
# weakness class is next; a bare pattern is the fallback. The donor is always a
# real roster entry, so the hidden animal can never say anything one of the
# others was not already permitted to say.
MIRROR_ORDER = (
    ("category", "axolotl"),
    ("weakness", "velociraptor"),
    ("pattern", "jaguar"),
)


def mirror_donor(context: dict | None = None) -> str:
    """Which companion the hidden one imitates for this encounter."""
    ctx = context or {}
    for field, donor in MIRROR_ORDER:
        key = (ctx.get(field) or "").upper()
        if key and key in BY_ID[donor].hints:
            return donor
    return "jaguar"


def hint_body(pet_id: str, context: dict | None = None) -> str:
    """The sentence this pet would say about this encounter.

    `context` is the REDACTED view: {"pattern", "weakness", "category"}, plus an
    optional "prior_family" for PRIOR_WORK. Anything else in it is ignored, which
    is deliberate — a caller cannot accidentally hand a pet the tests or the
    worked solution, because there is no field for them.
    """
    pet = BY_ID[pet_id]
    if pet.hint_kind == "MIRROR":
        donor = BY_ID[mirror_donor(context)]
        key = (context or {}).get(KEYED_BY[donor.hint_kind], "") or ""
        return donor.hints.get(key.upper(), donor.fallback)
    key = (context or {}).get(KEYED_BY[pet.hint_kind], "") or ""
    body = pet.hints.get(key.upper(), pet.fallback)
    if pet.hint_kind == "PRIOR_WORK":
        family = ((context or {}).get("prior_family") or "").replace("_", " ")
        if family:
            # Naming one of the player's OWN cleared families is the whole of
            # this kind of help, and it cannot become more than that: the most
            # it ever says is where they have already been.
            body = f"You closed the {family} tiles already. {body}"
    return body


# --------------------------------------------------------------------------
# The schedule: when a pet decides to say something
# --------------------------------------------------------------------------

def _fires(trigger: Trigger, signals: dict, scale: float) -> bool:
    """Is this measured condition true. No randomness lives in here; a companion
    that helps on a dice roll is a slot machine."""
    get = (signals or {}).get
    kind = trigger.kind
    threshold = trigger.threshold(scale)

    if kind == "idle_before_first_submit":
        return (not get("submitted", False)
                and float(get("seconds_elapsed", 0)) >= threshold)
    if kind == "stuck_seconds":
        return float(get("seconds_since_progress", 0)) >= threshold
    if kind == "failed_attempts":
        return int(get("failed_attempts", 0)) >= threshold
    if kind == "repeat_category":
        recent = [c for c in (get("last_categories") or []) if c]
        need = max(2, int(round(threshold)))
        return len(recent) >= need and len(set(recent[-need:])) == 1
    if kind == "failure_category":
        counts = get("category_counts") or {}
        return int(counts.get(trigger.category, 0)) >= max(1, int(round(threshold)))
    if kind == "syntax_failures":
        return int(get("syntax_failures", 0)) >= max(1, int(round(threshold)))
    if kind == "timeout_failures":
        return int(get("timeout_failures", 0)) >= max(1, int(round(threshold)))
    if kind == "hidden_trial_failed":
        return int(get("hidden_failures", 0)) >= max(1, int(round(threshold)))
    if kind == "perf_trial_failed":
        return bool(get("perf_failed", False))
    if kind == "weakness_survived":
        return bool(get("weakness", ""))
    return False


def intervention(pet_id: str, *, bond: int = 0, mode: str = "adventure",
                 region_id: str = "", signals: dict | None = None,
                 context: dict | None = None, spoken: int = 0,
                 difficulty: str = "", boss: bool = False, final: bool = False,
                 sealed: bool = False, refused_already: bool = False,
                 state: dict | None = None) -> dict | None:
    """The whole event, or None because the pet has nothing to say yet.

    Two shapes come out of here and the caller tells them apart by `refused`:

      * a HINT. `hint_weight` is 1 and `rank_ceiling` is a real rank. Charge it
        against `hints_used` and clamp the earnable rank, exactly as a hint rung
        is charged. That is the entire cost model and it is the same one.

      * a REFUSAL, when the encounter is deeper than this companion's tier. It
        carries `hint_weight` 0 and an EMPTY `rank_ceiling`, so a caller that
        applies the charging code unchanged charges nothing and clamps nothing.
        It carries `route`, which is the map out. A refusal is issued once per
        encounter: pass `refused_already` so the animal does not spend the whole
        problem repeating the same honest thing.

    `difficulty` is the encounter's own tier from `curriculum.TIERS`. It is the
    one field this function cannot work without and the one the old contract had
    no reason to send, so it is named rather than buried in `context`. Absent, it
    reads as EASY — `curriculum.tier_index`'s own fallback.
    """
    if not available_in(mode, region_id, sealed=sealed):
        return None
    pet = BY_ID.get(pet_id)
    # `is_down` is the whole of the fainting rule on the hint path: a companion
    # that is unconscious gives NOTHING, for the same reason one above its tier
    # gives nothing. What a player still has is `down_report` and the three
    # roads in it, none of which has ever asked who was walking with them.
    if pet is None or is_down(state, pet_id):
        return None
    rank = bond_rank(bond)
    depth = effective_difficulty(
        difficulty or (context or {}).get("difficulty", ""), boss=boss, final=final)

    if not covers(pet_id, depth):
        if refused_already:
            return None
        # It still has to have NOTICED. A companion that refuses before the
        # player is even stuck spends the whole encounter apologising, so the
        # refusal rides the same measured triggers the help would have ridden.
        if not any(_fires(t, signals or {}, rank.threshold_scale)
                   for t in pet.triggers):
            return None
        return _refusal(pet, depth, rank, spoken, state)

    # Bond bought the frequency; an ailment takes one back, never the last one.
    budget = speaking_budget(state, pet_id, rank)
    if spoken >= budget:
        return None

    for trigger in pet.triggers:
        if not _fires(trigger, signals or {}, rank.threshold_scale):
            continue
        kind = HINT_KINDS[pet.hint_kind]
        tier = TIER_BY_KEY[pet.tier]
        event = {
            "pet": pet.id, "name": pet.name, "species": pet.species,
            "sprite": pet.sprite, "colour": pet.colour, "skill": pet.skill,
            "tier": tier.key, "tier_label": tier.label,
            "helps_through": tier.depth, "difficulty": depth,
            "refused": False,
            "hint_kind": pet.hint_kind, "hint_label": kind["label"],
            "rule": kind["rule"],
            "rank_ceiling": kind["rank_ceiling"],
            "hint_weight": HINT_WEIGHT,
            "trigger": trigger.kind,
            "trigger_category": trigger.category,
            "threshold": trigger.threshold(rank.threshold_scale),
            "opening": trigger.line or pet.on_intervene,
            "body": hint_body(pet.id, context),
            "bond_rank": rank.key,
            "spoken": spoken + 1,
            "remaining": budget - spoken - 1,
            "ailing": ailments(state, pet.id),
            "vitality": vitality(state, pet.id),
        }
        if pet.hint_kind == "MIRROR":
            donor = BY_ID[mirror_donor(context)]
            # Said out loud, because "it became the raptor" is the good part and
            # because a player should be able to see which real companion they
            # are currently doing without.
            event["mirrored"] = donor.id
            event["mirrored_name"] = donor.name
            event["hint_label"] = HINT_KINDS[donor.hint_kind]["label"]
        return event
    return None


def _refusal(pet: Pet, depth: str, rank: BondRank, spoken: int,
             state: dict | None) -> dict:
    """An honest no, with a map attached. Costs nothing and clamps nothing."""
    tier = TIER_BY_KEY[pet.tier]
    return {
        "pet": pet.id, "name": pet.name, "species": pet.species,
        "sprite": pet.sprite, "colour": pet.colour, "skill": pet.skill,
        "tier": tier.key, "tier_label": tier.label,
        "helps_through": tier.depth, "difficulty": depth,
        "refused": True, "reason": "ABOVE_TIER",
        "hint_kind": "", "hint_label": "", "rule": "",
        "rank_ceiling": "",          # no opinion: engine._worse_rank ignores it
        "hint_weight": 0,            # a refusal is not a hint and must not cost one
        "trigger": "", "trigger_category": "", "threshold": 0,
        "opening": pet.above_tier,
        "body": "",
        "route": fallback_route(pet.id, difficulty=depth, state=state),
        "bond_rank": rank.key,
        "spoken": spoken,
        "remaining": max(0, rank.interventions - spoken),
    }


def party_intervention(active: list, *, bonds: dict | None = None,
                       mode: str = "adventure", region_id: str = "",
                       signals: dict | None = None, context: dict | None = None,
                       spoken: dict | None = None, difficulty: str = "",
                       boss: bool = False, final: bool = False,
                       sealed: bool = False, refused: list | None = None,
                       state: dict | None = None) -> dict | None:
    """The one pet that speaks.

    ACTIVE_LIMIT is 1, so this loops over a list of one. The name is a fossil
    worth keeping: it is the call site the engine already makes, and a renamed
    function is a merge conflict in somebody else's file.
    """
    already = set(refused or [])
    for pet_id in (active or [])[:ACTIVE_LIMIT]:
        found = intervention(
            pet_id, bond=int((bonds or {}).get(pet_id, 0)), mode=mode,
            region_id=region_id, signals=signals, context=context,
            spoken=int((spoken or {}).get(pet_id, 0)),
            difficulty=difficulty, boss=boss, final=final, sealed=sealed,
            refused_already=pet_id in already, state=state)
        if found:
            return found
    return None


def idle_line(pet_id: str, rng: random.Random | None = None) -> str:
    """Something to say in the overworld. Flavour only, never about the encounter."""
    pet = BY_ID[pet_id]
    return (rng or random).choice(list(pet.idle))


def outcome_line(pet_id: str, *, cleared: bool, helped: bool = True) -> str:
    """What it says once the attempt has been graded.

    A pet that only speaks when you win is a scoreboard. The line after a failure
    is the one that decides whether the player opens the editor again tomorrow.
    """
    pet = BY_ID[pet_id]
    if cleared:
        return pet.on_cleared if helped else pet.idle[0]
    return pet.on_failed


# --------------------------------------------------------------------------
# No dead ends (F)
# --------------------------------------------------------------------------
#
# The tier ladder gates ONE thing: help that arrives unasked, for free, timed to
# the moment of struggle. That is what a companion is. It does not gate the roads
# a player walks down deliberately, and there are three of those, none of which
# has ever asked which animal was in the field:
#
#   1. OPEN_RUNG of the problem's own hint tree. Costs focus, costs rank, open to
#      anybody at any tier with no companion at all — including a player whose
#      only companion is dead.
#   2. The coach, after a failed submission. Socratic, graded, and gated only by
#      Timed Practical Mode, which is the one place nothing helps anybody.
#   3. The worked solution, free in focus after FREE_SOLUTION_AFTER attempts and
#      costing the entire rank. The floor the whole design already rested on.
#
# And two more that are the tier system working rather than being escaped:
#
#   4. Go and get the companion that covers this. The refusal names them, says
#      where they are and what the deed is, so "find a better animal" is an
#      errand and not a mood.
#   5. Go and clear something your companion does cover. The ramp is already
#      built to serve that, and a BEGINNER animal on EASY content is not a
#      compromise — it is the game being played correctly.

ROADS = (
    {"id": "OPEN_RUNG", "title": "The first rung is not ours to close",
     "detail": "The opening rung of this encounter's own hint tree does not ask "
               "who is walking with you and never has. It costs focus and it "
               "costs rank, like everything else that has to be asked for.",
     "costs": "focus and rank"},
    {"id": "COACH", "title": "Submit it wrong on purpose",
     "detail": "The coach speaks after a failed submission, asks the question "
               "that would have unblocked you, and has no opinion about "
               "companions. A failed submission is evidence, and evidence is "
               "the only thing this game answers to.",
     "costs": "one submission"},
    {"id": "SOLUTION", "title": "The worked solution, eventually",
     "detail": f"After {FREE_SOLUTION_AFTER} attempts on this problem the worked "
               "solution stops costing focus. It still costs the whole rank. "
               "Nobody will stop you and nobody will mention it again.",
     "costs": "the entire rank"},
    {"id": "BETTER_COMPANION", "title": "Go and find the one that reads this",
     "detail": "Something out there has hunted this depth before. The deed and "
               "the place are both written down. This is the road the refusal "
               "exists to point at.",
     "costs": "a detour, and the deed"},
    {"id": "HEALER", "title": "The healer wakes it for nothing",
     "detail": "A fainted companion is a walk home, not a loss. The healer in "
               "town restores health, lifts poison and every other affliction, "
               "and wakes whatever went down in the blast, and charges nothing "
               "for any of it. Bond, tier and everything it has found are "
               "untouched. Anything else you have found may be fielded in the "
               "meantime.",
     "costs": "the walk back"},
    {"id": "LOWER_GROUND", "title": "Fight at the depth you brought help for",
     "detail": "The animal in the field covers real content and there is a great "
               "deal of it. Clearing that is not a retreat; it is the evidence "
               "that opens the tier above.",
     "costs": "nothing"},
)

ROAD_BY_ID = {r["id"]: r for r in ROADS}

# The three that need no companion. Named as data so the self-check can prove
# the claim rather than assert it.
PETLESS_ROADS = ("OPEN_RUNG", "COACH", "SOLUTION")


def companions_for(difficulty: str = "", *, found: list | None = None) -> list:
    """Who could have helped here, shallowest tier first.

    Found companions sort ahead of unfound ones inside a tier, because "you
    already have one of these and it is sitting at home" is a different and much
    more actionable sentence than "here is where to go looking".
    """
    have = set(found or [])
    rows = []
    for pet in PETS:
        if not covers(pet.id, difficulty):
            continue
        tier = TIER_BY_KEY[pet.tier]
        rows.append({
            "id": pet.id, "name": pet.name, "species": pet.species,
            "tier": tier.key, "tier_label": tier.label, "tier_index": tier.index,
            "helps_through": tier.depth,
            "hint_label": HINT_KINDS[pet.hint_kind]["label"],
            "skill": pet.skill,
            "region": pet.discovery.region,
            "where": pet.discovery.where,
            "how": pet.discovery.how,
            "arrival": pet.discovery.arrival,
            "arrival_label": ACQUISITIONS[pet.discovery.arrival][0],
            "found": pet.id in have,
            "awarded": pet.awarded,
        })
    rows.sort(key=lambda r: (r["tier_index"], not r["found"]))
    return rows


def fallback_route(pet_id: str = "", *, difficulty: str = "",
                   state: dict | None = None) -> dict:
    """Every road out of this problem, for a player carrying the wrong animal.

    Called with no pet at all when the player has none. The answer is the same,
    which is the proof that the tier ladder is not what stands between anybody
    and getting unstuck.
    """
    state = state or {}
    found = list(state.get("found") or [])
    fallen = list(state.get("fallen") or [])
    fainted = list(state.get("fainted") or [])
    pet = BY_ID.get(pet_id)
    depth = _clean(difficulty)
    return {
        "difficulty": depth,
        "companion": pet.id if pet else "",
        "companion_name": pet.name if pet else "",
        "companion_tier": pet.tier if pet else "",
        "covers_through": TIER_BY_KEY[pet.tier].depth if pet else "",
        "tiers_that_cover": tiers_covering(depth),
        "open_rung": OPEN_RUNG,
        "free_solution_after": FREE_SOLUTION_AFTER,
        "roads": list(ROADS),
        "petless_roads": list(PETLESS_ROADS),
        "companions": companions_for(depth, found=found),
        "fallen": fallen,
        # Fainted is reported beside fallen and is never merged into it. One of
        # them is free to undo and the other is the barrow, and a player reading
        # this screen is entitled to know which one they are looking at.
        "fainted": fainted,
        "companion_down": bool(pet and is_down(state, pet.id)),
        "heal_cost": HEAL_COST_GOLD,
        "line": (pet.above_tier if pet else
                    "Nothing is walking with you. The spells, the coach and the "
                    "solution do not care about that, and never did."),
    }


# --------------------------------------------------------------------------
# Bonding
# --------------------------------------------------------------------------

def bond_gain(pet_id: str, *, skill: str, cleared: bool, rank: str = "",
              hints_used: int = 0, intervened: bool = False,
              is_retest: bool = False, in_field: bool = True) -> int:
    """What this encounter was worth to this companion.

    Evidence only. A cleared encounter in the pet's own skill pays; time spent
    carrying it pays nothing, exploring with it pays nothing, and failing costs
    nothing either — bond never falls, because a companion that punishes a bad
    day is a retention mechanic wearing a costume.

    `intervened` must mean it actually HELPED. A refusal is not an intervention
    and must not pay the assisted bonus, or the game would be rewarding a
    companion for admitting it was useless.
    """
    pet = BY_ID.get(pet_id)
    if pet is None or not in_field or not cleared or skill != pet.skill:
        return 0
    gain = BOND_FOR_RANK.get(rank, 2)
    if hints_used == 0 and not intervened:
        gain += BOND_UNAIDED_BONUS
    if intervened:
        # It spoke, and the player went on to clear it. That is the job description.
        gain += BOND_ASSISTED_BONUS
    if is_retest:
        gain += BOND_RETEST_BONUS
    return min(gain, BOND_MAX_PER_ENCOUNTER)


# The passives that READ THE ROOM rather than pay the player.
#
# Most of what a bond buys is economy: a bigger stamina bar, focus back after a
# clear, better loot, a combo that survives one failure. None of that is an
# opinion about the problem in front of you, and none of it is gated by depth —
# a cap that moved when the player walked into a harder room would take stamina
# off them mid-run for a reason they could not see, and bond is not allowed to be
# a thing that can be lost.
#
# These are different. Another probe; a probe that reveals the value it would
# have returned; a probe that names the failure category it would have tripped;
# the timing budget of a performance trial; the price of the hint tree itself.
# Every one of them is help ABOUT THIS ENCOUNTER, which is the exact thing the
# tier ladder exists to gate. An animal that cannot read this depth does not get
# to hand over an extra question to ask about it either, because a tier gate that
# holds on the spoken line and leaks through the probe charge is not a gate, it
# is a style guide.

DEPTH_GATED_EFFECTS = frozenset({
    "probe_charges",        # another question to ask about THIS problem
    "probe_reveal_value",   # and an answer to it
    "reveal_category",      # which weakness that question would have tripped
    "perf_insight",         # the timing budget this problem is measured against
    "hint_discount",        # the price of the tree the ladder already gates
    "prereq_sight",         # what this problem is built on top of
    "boundary_sense",       # where its edges are
    "phase_preview",        # what the fight in front of you does next
    "oblige",               # solves it outright; no companion has it and none may
})

# Everything in items.EFFECT_LABELS that is about the encounter rather than about
# the player, gated or not. `_validate` checks one list against the other, which
# is the whole reason for keeping two: the entries that are in here and NOT in
# the gate are the ones no companion may carry at all. `srs_preview` is a
# schedule and `unlabelled` is a penalty, and depth-gating a penalty would hand
# the below-tier player a buff for being below tier. The roster is refused at
# import if either ever turns up on an animal, which beats finding out from a
# player who walked a piglet into a boss room.
_READS_THE_ROOM = frozenset(DEPTH_GATED_EFFECTS | {"srs_preview", "unlabelled"})


def passive_effects(pet_id: str, bond: int = 0, *,
                    difficulty: str | None = None) -> dict:
    """The passive a bond rank has earned. Keys are items.EFFECT_LABELS keys and
    nothing else — validated at import, so this cannot drift.

    `difficulty` is the depth being asked for. Pass it from inside an encounter
    and the tier ladder applies to the passives that read the room; leave it None
    outside one, where there is no room to read and no ceiling to move.
    """
    pet = BY_ID.get(pet_id)
    if pet is None:
        return {}
    earned = pet.passive_effects(bond)
    if difficulty is None or covers(pet_id, difficulty):
        return earned
    return {k: v for k, v in earned.items() if k not in DEPTH_GATED_EFFECTS}


def party_effects(active: list, bonds: dict | None = None,
                  mode: str = "adventure", *,
                  difficulty: str | None = None,
                  state: dict | None = None) -> dict:
    """Every passive the companion in the field is contributing.

    With ACTIVE_LIMIT at 1 this merges a list of one, and the "best value per
    key" rule stays anyway: it costs nothing, and it keeps an old save that
    still lists two active pets from stacking anything it should not.

    Nothing is contributed in Timed Practical Mode. Items already work this way, and a
    pet is not allowed to be the exception that proves the rule. The seal proper
    is the caller's to apply — `available_in(mode, region, sealed=)` — and this
    mode check is the same deny-only guard rail that function carries.
    """
    from .config import MODE_INTERVIEW
    if mode == MODE_INTERVIEW:
        return {}
    merged: dict = {}
    for pet_id in (active or [])[:ACTIVE_LIMIT]:
        # An animal on the floor is not holding anything up. `state` is optional
        # so that an old call site keeps working unchanged; pass it and a
        # fainted companion stops paying out its passives too, which is the
        # quiet half of the same rule the spoken line already follows.
        if state is not None and is_down(state, pet_id):
            continue
        earned = passive_effects(pet_id, int((bonds or {}).get(pet_id, 0)),
                                 difficulty=difficulty)
        for key, value in earned.items():
            merged[key] = max(merged.get(key, 0), value)
    return merged


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
#
# `evidence` is a flat read-only snapshot the caller assembles once:
#
#   {"families": {family: unaided_clears},
#    "skills": {SKILL: {"mastery": float, "unaided_clears": int, "clears": int}},
#    "bosses_unaided": ["hash_titan", ...],
#    "regions_cleared": ["debugging_dungeon", ...],
#    "dungeons": {"ninth_cart": depth_reached},   # dungeons.DUNGEON_BY_ID ids
#    "retests": {SKILL: survived_count, "": total_survived},
#    "no_hint_streak": int, "perf_cleared": int, "probes_correct": int,
#    "starter_fallen": bool,        # the barrow closed on it
#    "solo_floors": int,            # floors cleared with no pet, no spell, no item
#    "stats": {...}}

def _row(label: str, have, need) -> dict:
    have = float(have or 0)
    need = float(need or 0)
    return {"label": label, "have": round(have, 1), "need": need,
            "met": have >= need}


def _discovery_row(clause: dict, evidence: dict) -> dict:
    kind = clause.get("kind", "")
    ev = evidence or {}

    if kind == "family_unaided":
        family = clause.get("family", "")
        return _row(f"unaided clears in {family.replace('_', ' ')}",
                    (ev.get("families") or {}).get(family, 0), clause.get("count", 1))
    if kind == "skill_unaided":
        skill = clause.get("skill", "")
        data = (ev.get("skills") or {}).get(skill) or {}
        return _row(f"{skill} unaided clears", data.get("unaided_clears", 0),
                    clause.get("count", 1))
    if kind == "skill_mastery":
        skill = clause.get("skill", "")
        data = (ev.get("skills") or {}).get(skill) or {}
        return _row(f"{skill} mastery", data.get("mastery", 0), clause.get("value", 0))
    if kind == "boss_unaided":
        boss = clause.get("boss", "")
        beaten = boss in (ev.get("bosses_unaided") or [])
        return _row(f"{boss.replace('_', ' ')} beaten with nothing cast",
                    1 if beaten else 0, 1)
    if kind == "region_cleared":
        region = clause.get("region", "")
        done = region in (ev.get("regions_cleared") or [])
        return _row(f"{region.replace('_', ' ')} cleared", 1 if done else 0, 1)
    if kind == "dungeon_depth":
        dungeon = clause.get("dungeon", "")
        return _row(f"{dungeon.replace('_', ' ')} depth",
                    (ev.get("dungeons") or {}).get(dungeon, 0), clause.get("depth", 1))
    if kind == "retest_survived":
        skill = clause.get("skill", "")
        retests = ev.get("retests") or {}
        # An empty skill means "any" — the llama does not care which one ambushed you.
        # The evidence dict publishes the TOTAL under the empty key alongside
        # the per-skill counts (see the shape note above), so `sum(values)`
        # added the total to its own parts and every unnamed clause read
        # exactly twice the truth — a three-ambush gate opening after two.
        # Read the published total; fall back to summing the NAMED keys only,
        # for a caller that does not publish one.
        have = (retests.get(skill, 0) if skill else
                retests.get("", sum(v for k, v in retests.items() if k)))
        return _row(f"{skill or 'any'} memory ambushes survived", have,
                    clause.get("count", 1))
    if kind == "no_hint_streak":
        return _row("clears in a row with no help", ev.get("no_hint_streak", 0),
                    clause.get("count", 1))
    if kind == "perf_cleared":
        return _row("performance trials cleared", ev.get("perf_cleared", 0),
                    clause.get("count", 1))
    if kind == "probes_correct":
        return _row("correct probes", ev.get("probes_correct", 0),
                    clause.get("count", 1))
    if kind == "starter_fallen":
        return _row("the barrow closed on something of yours",
                    1 if ev.get("starter_fallen") else 0, 1)
    if kind == "solo_floor":
        return _row("dungeon floors cleared with no companion, spell or item",
                    ev.get("solo_floors", 0), clause.get("count", 1))
    if kind == "stat":
        stat = clause.get("stat", "")
        return _row(stat.replace("_", " "), (ev.get("stats") or {}).get(stat, 0),
                    clause.get("at_least", 1))

    # -- the four that make the roster arrive twelve different ways --------
    if kind == "puzzle_kind":
        puzzle = clause.get("puzzle", "")
        return _row(f"{puzzle.replace('_', ' ').lower()} puzzles solved",
                    (ev.get("puzzle_clears") or {}).get(puzzle, 0),
                    clause.get("count", 1))
    if kind == "quest_done":
        quest = clause.get("quest", "")
        done = quest in (ev.get("quests_done") or ())
        return _row(f"{quest.replace('_', ' ')} finished", 1 if done else 0, 1)
    if kind == "trade_done":
        trade = clause.get("trade", "")
        struck = trade in (ev.get("trades") or ())
        gold = int(clause.get("gold", 0))
        goods = clause.get("goods", "the trade")
        label = f"{goods} handed over" if not gold else f"{goods}, and {gold} gold"
        return _row(label, 1 if struck else 0, 1)
    if kind == "sighted":
        pet_id = clause.get("pet", "")
        named = BY_ID[pet_id].name if pet_id in BY_ID else (pet_id or "it")
        return _row(f"sightings of {named} before it would come near",
                    (ev.get("sightings") or {}).get(pet_id, 0),
                    clause.get("count", 1))
    return _row(kind or "unknown condition", 0, 1)


def discovery_progress(pet_id: str, evidence: dict | None = None) -> dict:
    """How close this player is to meeting this animal.

    Pure. It reads evidence and describes; granting the pet is the caller's
    business, which keeps "mastery moves only on graded evidence" in one place
    instead of two.
    """
    pet = BY_ID[pet_id]
    found = pet.discovery
    needs = found.needs if found else ()
    checks = [_discovery_row(clause, evidence or {}) for clause in needs]
    return {
        "pet": pet.id, "name": pet.name, "species": pet.species,
        "tier": pet.tier, "tier_label": TIER_BY_KEY[pet.tier].label,
        "helps_through": TIER_BY_KEY[pet.tier].depth,
        "awarded": pet.awarded,
        "region": found.region if found else "",
        "where": found.where if found else "",
        "how": found.how if found else "",
        "arrival": found.arrival if found else "",
        "arrival_label": ACQUISITIONS.get(
            found.arrival if found else "", ("", ""))[0],
        "arrival_blurb": ACQUISITIONS.get(
            found.arrival if found else "", ("", ""))[1],
        "first_words": found.first_words if found else "",
        "checks": checks,
        # A STORY companion is never "met" by evidence. The starter arrives
        # because the narrative hands it over, and a progress bar that could
        # never fill would be the codex lying once per frame.
        "met": (bool(checks) and all(row["met"] for row in checks)
                and pet.awarded == AWARD_EVIDENCE),
    }


def newly_found(evidence: dict | None = None, already: list | None = None) -> list:
    """Every pet whose conditions are now satisfied and which has not been met.

    Returns the full discovery payloads so the caller can show the moment
    properly. Finding a companion should never be a line in a log.
    """
    have = set(already or [])
    out = []
    for pet in PETS:
        if pet.id in have or pet.awarded != AWARD_EVIDENCE:
            continue
        progress = discovery_progress(pet.id, evidence)
        if progress["met"]:
            out.append(progress)
    return out


def undiscovered_hints(evidence: dict | None = None, already: list | None = None,
                       limit: int = 3) -> list:
    """The nearest unmet companions, for the codex page that tells the player
    there is more out there. Sorted by how close they are, because a hidden thing
    with no visible progress is indistinguishable from a bug."""
    have = set(already or [])
    scored = []
    for pet in PETS:
        if pet.id in have or pet.awarded != AWARD_EVIDENCE:
            continue
        progress = discovery_progress(pet.id, evidence)
        rows = progress["checks"] or []
        done = sum(1 for row in rows if row["met"])
        fraction = done / len(rows) if rows else 0.0
        scored.append((fraction, progress))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [progress for _, progress in scored[:limit]]


# --------------------------------------------------------------------------
# Save state
# --------------------------------------------------------------------------

def new_state() -> dict:
    """Flat, JSON-safe, and small enough to drop straight into the save blob.

    `found` is append-only and is never edited by a dismissal. `fallen` is the
    one list that takes anything away, it has exactly one member for the whole
    of a run, and the thing it takes away comes back.
    """
    return {"found": [], "active": [], "bond": {}, "met_at": {},
            "fallen": [], "dismissed_at": {},

            # -- the blast. Every one of these is additive and every reader
            # below treats a missing key as the healthy default, so a save
            # written before any of this existed loads as twelve unhurt animals
            # rather than twelve dead ones.
            "vitality": {},        # pet id -> points remaining, 0..VITALITY_MAX
            "fainted": [],         # down. Reversible, free, and NOT `fallen`
            "fainted_at": {},      # pet id -> when, for the town screen
            "faints": {},          # pet id -> lifetime count. Codex only:
                                   # nothing mechanical is allowed to read it
            "ailments": {},        # pet id -> elements.STATUS_IDS it carries
            "spent_stand": [],     # pet ids whose LAST_STAND is used up until
                                   # the next healer visit
            "sightings": {},       # pet id -> times seen in the wild
            "trades": []}          # TRADES ids already struck


def grant(state: dict, pet_id: str, *, at: float = 0.0,
          make_active: bool = True) -> bool:
    """Record that the player has met this animal. True if it is news.

    A newly found companion walks with you only if your hands are free. With
    ACTIVE_LIMIT at 1 that matters: silently benching the animal you chose
    because you tripped over a new one would be the game overruling a decision
    it has just spent an hour teaching you to make.
    """
    if pet_id not in BY_ID or pet_id in state.get("found", []):
        return False
    state.setdefault("found", []).append(pet_id)
    state.setdefault("bond", {}).setdefault(pet_id, 0)
    state.setdefault("met_at", {})[pet_id] = at
    state.setdefault("vitality", {}).setdefault(pet_id, VITALITY_MAX)
    if make_active and not state.setdefault("active", []):
        state["active"].append(pet_id)
    return True


def award(state: dict, pet_id: str, amount: int) -> dict:
    """Add bond and report whether a rank was crossed, so the caller knows there
    is a line of dialogue to show."""
    if amount <= 0 or pet_id not in BY_ID:
        return {"pet": pet_id, "gained": 0, "ranked_up": False}
    bonds = state.setdefault("bond", {})
    before = bond_rank(int(bonds.get(pet_id, 0)))
    bonds[pet_id] = int(bonds.get(pet_id, 0)) + int(amount)
    after = bond_rank(bonds[pet_id])
    return {
        "pet": pet_id, "name": BY_ID[pet_id].name, "gained": int(amount),
        "bond": bonds[pet_id], "rank": after.key,
        "ranked_up": after.index > before.index,
        "line": (BY_ID[pet_id].bond_lines[after.index]
                 if after.index > before.index else ""),
        "unlocked": items.describe(
            {k: v for k, v in BY_ID[pet_id].passives.get(after.index, {}).items()}
        ) if after.index > before.index else [],
    }


def is_fallen(state: dict | None, pet_id: str) -> bool:
    return pet_id in ((state or {}).get("fallen") or [])


def active_id(state: dict | None) -> str:
    active = (state or {}).get("active") or []
    return active[0] if active else ""


def set_active(state: dict, pet_ids: list) -> list:
    """Choose who walks with you.

    Silently drops unfound pets, dead ones, and anything past the limit rather
    than erroring, because this is called from a UI. Choosing a new companion IS
    the dismissal of the old one — there is no separate destructive gesture,
    because there is nothing destructive about it.
    """
    found = state.get("found", [])
    dead = set(state.get("fallen") or [])
    chosen = [p for p in (pet_ids or [])
              if p in found and p not in dead][:ACTIVE_LIMIT]
    previous = active_id(state)
    if previous and previous not in chosen:
        state.setdefault("dismissed_at", {})[previous] = 0.0
    state["active"] = chosen
    return chosen


def dismiss(state: dict, *, at: float = 0.0) -> dict:
    """Send the current companion back to wherever it waits.

    REVERSIBLE, always, by design. A companion you have found is never lost:
    `found` is not touched, bond is not touched, and `recall` puts it straight
    back. The friction this system wants is that you cannot carry two at once.
    A permanent mistake made at level three is a reason to stop playing, and no
    part of this module is allowed to be one.
    """
    pet_id = active_id(state)
    if not pet_id:
        return {"pet": "", "dismissed": False, "line": ""}
    state["active"] = []
    state.setdefault("dismissed_at", {})[pet_id] = at
    pet = BY_ID[pet_id]
    return {
        "pet": pet.id, "name": pet.name, "dismissed": True,
        "line": pet.on_dismiss,
        "waits_at": pet.discovery.where,
        "region": pet.discovery.region,
        "reversible": True,
    }


def recall(state: dict, pet_id: str, *, at: float = 0.0) -> dict:
    """Bring a dismissed companion back. Whoever was in the field steps down."""
    if pet_id not in state.get("found", []):
        return {"pet": pet_id, "active": False, "error": "not found yet"}
    if is_fallen(state, pet_id):
        return {"pet": pet_id, "active": False, "error": "it is not coming back"}
    stepped_down = active_id(state)
    set_active(state, [pet_id])
    state.setdefault("dismissed_at", {}).pop(pet_id, None)
    pet = BY_ID[pet_id]
    return {
        "pet": pet.id, "name": pet.name, "active": True,
        # Fielding an unconscious companion is allowed — it is still yours, it
        # still holds its bond, and healing it is free — but the screen says so
        # rather than letting the player work out why nothing is speaking.
        "down": is_fainted(state, pet.id),
        "vitality": vitality(state, pet.id),
        "heal_cost": HEAL_COST_GOLD,
        "line": pet.on_recall,
        "stepped_down": stepped_down if stepped_down != pet_id else "",
        "stepped_down_line": (BY_ID[stepped_down].on_dismiss
                              if stepped_down and stepped_down != pet_id else ""),
    }


def fall(state: dict, pet_id: str = STARTER_ID, *, at: float = 0.0) -> dict:
    """The barrow closes.

    The ONE irreversible thing in this module. It happens to exactly one animal,
    at one boss, once. It does not remove the pet from `found`, because the codex
    keeps the entry and because the legendary return is gated on the save
    remembering that this happened at all.
    """
    if pet_id not in BY_ID:
        return {"pet": pet_id, "fell": False}
    if is_fallen(state, pet_id):
        return {"pet": pet_id, "fell": False, "already": True}
    state.setdefault("fallen", []).append(pet_id)
    # The barrow supersedes a faint. Whatever shape the animal was in when it
    # walked in there, what happened to it was not an area attack and the town
    # healer is not the answer to it, so the reversible list lets go of it here.
    state["fainted"] = [p for p in (state.get("fainted") or []) if p != pet_id]
    state.setdefault("fainted_at", {}).pop(pet_id, None)
    state.setdefault("found", [])
    if pet_id not in state["found"]:
        state["found"].append(pet_id)
    state.setdefault("bond", {}).setdefault(pet_id, 0)
    if active_id(state) == pet_id:
        state["active"] = []
    pet = BY_ID[pet_id]
    returns = BY_ID.get(pet.lineage)
    return {
        "pet": pet.id, "name": pet.name, "species": pet.species, "fell": True,
        "at": at,
        "dungeon": FALLS_AT_DUNGEON,
        "chapter": FALLS_AT_CHAPTER,
        "keepsake": KEEPSAKE,
        # Said plainly, because the player has just lost their only source of
        # unasked help at the exact moment they are first being measured, and
        # being told that straight is better than being consoled about it.
        "cost": "You have no companion. Nothing will speak to you unasked until "
                "you go and find something that will.",
        "roads": [ROAD_BY_ID[r] for r in PETLESS_ROADS],
        "returns_as": returns.id if returns else "",
        "returns_at": RETURNS_AT_DUNGEON,
        "lines": (
            "The Unclosed Bracket opens. That is the only thing it does and it "
            "has never needed a second move.",
            "The pig knows exactly one trick, which is to supply the mark that is "
            "missing, and nobody ever taught it that some things are meant to "
            "stay open.",
            "It goes in. The bracket closes. It closes properly, which is the "
            "part nobody in this barrow has managed in nine hundred years.",
            "What is left on the floor is a small iron half-ring, closed, still "
            "warm. Take it. You will want it much later, and you will not know "
            "why for a long time.",
        ),
    }


# --------------------------------------------------------------------------
# The blast (A): what an area attack costs the animal walking with you
# --------------------------------------------------------------------------
#
# The arithmetic is one line and it is deliberately one line: a companion loses
# the share of ITS bar that the same blow took of YOURS, divided by
# PET_ENDURANCE, capped by SPLASH_CAP. Nothing in here knows what a monster hits
# for, which is why the AoE pass can change every damage number in the bestiary
# without coming back to this file.


def condition(points: int) -> str:
    """The bar, in one word. DOWN at zero, and CRITICAL is where it blinks."""
    points = max(0, int(points))
    for key, floor, _blurb in CONDITIONS:
        if points >= floor and floor > 0:
            return key
    return "DOWN" if points <= 0 else "CRITICAL"


def condition_blurb(key: str) -> str:
    for name, _floor, blurb in CONDITIONS:
        if name == key:
            return blurb
    return ""


def vitality(state: dict | None, pet_id: str) -> int:
    """Points left. A pet nobody has recorded is a pet nobody has hit."""
    if pet_id in ((state or {}).get("fainted") or []):
        return 0
    raw = ((state or {}).get("vitality") or {}).get(pet_id, VITALITY_MAX)
    return max(0, min(VITALITY_MAX, int(raw)))


def ailments(state: dict | None, pet_id: str) -> list:
    return list(((state or {}).get("ailments") or {}).get(pet_id) or [])


def is_fainted(state: dict | None, pet_id: str) -> bool:
    """Down, and therefore silent. Free to undo, and undone in town."""
    return pet_id in ((state or {}).get("fainted") or [])


def is_down(state: dict | None, pet_id: str) -> bool:
    """The one question the hint path asks: can this animal speak right now.

    Two very different facts answer it. `fallen` is the barrow and is forever.
    `fainted` is an area attack and is free to undo. They are kept apart
    everywhere else precisely so that this one place can treat them alike.
    """
    return is_fallen(state, pet_id) or is_fainted(state, pet_id)


def speaking_budget(state: dict | None, pet_id: str,
                    rank: BondRank | None = None) -> int:
    """How many times this animal may speak in one encounter, right now.

    Bond buys frequency. An ailment takes one back. Neither of them has ever
    been allowed near DEPTH, and the floor of one is not negotiable: an animal
    that can be silenced outright by a status is a status that deletes the hint
    system, and there is no status in this game with that much authority.
    """
    if rank is None:
        rank = bond_rank(int(((state or {}).get("bond") or {}).get(pet_id, 0)))
    budget = rank.interventions
    if ailments(state, pet_id):
        budget -= AILMENT_SPEECH_COST
    return max(1, budget)


def _element_scale(element: str, pet_id: str) -> float:
    """How the room's element treats this animal, clamped hard.

    Lazy import: a companion is allowed to have an element without the pet
    system taking a load-time dependency on the combat system.
    """
    if not element or not pet_id:
        return 1.0
    try:
        from . import elements
    except Exception:                          # pragma: no cover - diagnostics
        return 1.0
    pet = BY_ID.get(pet_id)
    mine = elements.pet_element(getattr(pet, "species", ""), pet_id)
    mult, _kind = elements.matchup(element, mine)
    low, high = ELEMENT_SPREAD
    return min(high, max(low, float(mult)))


def splash_damage(damage: float, *, max_health: float, element: str = "",
                  pet_id: str = "", shielded: float = 0.0) -> int:
    """What one area attack costs a companion, in vitality points. PURE.

    `damage` and `max_health` are in the PLAYER's health units — whatever the
    blow actually did to the player, and whatever their bar holds. Passing the
    player's numbers rather than a pet-specific damage roll is the whole trick:
    it means the companion scales with the game forever and there is no second
    damage formula to keep in step with `elements.resolve_damage`.

    `shielded` is a fraction taken off by a class's guard move, capped at
    SHIELD_CAP. `element` is the attacker's element; the animal's own comes from
    `elements.pet_element`, clamped by ELEMENT_SPREAD.
    """
    damage = max(0.0, float(damage or 0))
    max_health = float(max_health or 0)
    if damage <= 0 or max_health <= 0:
        return 0
    raw = VITALITY_MAX * (damage / max_health) / PET_ENDURANCE
    raw *= _element_scale(element, pet_id)
    raw *= 1.0 - min(SHIELD_CAP, max(0.0, float(shielded or 0.0)))
    return max(SPLASH_FLOOR, min(SPLASH_CAP, int(round(raw))))


def take_aoe(state: dict, damage: float, *, max_health: float,
             pet_id: str = "", source: str = "MONSTER", element: str = "",
             shielded: float = 0.0, inflicts: str = "",
             mode: str = "adventure", region_id: str = "",
             sealed: bool = False, at: float = 0.0) -> dict | None:
    """One area attack landing on the companion in the field. Mutates `state`.

    Returns None when there is nothing to hit: no companion fielded, the one
    fielded is already down, or `available_in` says no animal is present here at
    all — a measured run, Timed Practical Mode, or one of the two regions that promise
    nothing helps you there. That last group matters. A companion that is not
    allowed to help in this encounter is not standing in the blast either,
    because the alternative is an exam, or a Coliseum bout, that sends the
    player back to the healer over a fight the animal was barred from.

    The returned event is what the battle scene draws: `lost`, `before`,
    `after`, a `condition`, a `blink` flag for the low-vitality heartbeat, and
    `faint` — the whole scene dict from `faint()` — when this was the one.
    """
    if not available_in(mode, region_id, sealed=sealed):
        return None
    pet_id = pet_id or active_id(state)
    pet = BY_ID.get(pet_id)
    if pet is None or is_down(state, pet_id):
        return None
    lost = splash_damage(damage, max_health=max_health, element=element,
                         pet_id=pet_id, shielded=shielded)
    if lost <= 0:
        return None

    before = vitality(state, pet_id)
    after = before - lost
    last_stand = False
    if after <= 0 and before > LAST_STAND \
            and pet_id not in (state.get("spent_stand") or []):
        # One more round, once per healer visit. It is not a second health bar:
        # it is the difference between "my hints vanished" and "my hints are
        # about to vanish unless I finish this", and only one of those two
        # sentences makes a player type faster.
        after = LAST_STAND
        last_stand = True
        state.setdefault("spent_stand", []).append(pet_id)
    after = max(0, min(VITALITY_MAX, after))
    state.setdefault("vitality", {})[pet_id] = after
    lost = before - after

    ailment = afflict(state, pet_id, inflicts) if inflicts else None
    scene = faint(state, pet_id, at=at, cause=source) if after <= 0 else None
    return {
        "pet": pet.id, "name": pet.name, "species": pet.species,
        "sprite": pet.sprite, "colour": pet.colour,
        "source": source if source in AOE_SOURCES else "MONSTER",
        "element": element, "lost": int(lost),
        "before": int(before), "after": int(after), "max": VITALITY_MAX,
        "fraction": round(after / VITALITY_MAX, 3),
        "condition": condition(after), "blurb": condition_blurb(condition(after)),
        # Same language the player sprite uses at low health, because the brief
        # was explicit that this must be impossible to miss, and the companion
        # is the thing a player is least likely to be looking at.
        "blink": after <= CRITICAL_AT,
        "last_stand": last_stand,
        "ailment": ailment,
        "fainted": bool(scene),
        "faint": scene,
        "line": pet.on_faint if scene else "",
    }


def afflict(state: dict, pet_id: str = "", status_id: str = "POISONED") -> dict:
    """Mark the companion with a status the same blow put on the player.

    What it costs is one intervention per encounter and never the last one —
    see `speaking_budget`. It costs no vitality, because a status that ticked
    the animal down while the player was busy would be a faint nobody could see
    coming, and rule 3 of the anti-spiral list exists to stop exactly that.

    Cleared by the healer for nothing, along with everything else.
    """
    pet_id = pet_id or active_id(state)
    if pet_id not in BY_ID or is_down(state, pet_id):
        return {}
    try:
        from . import elements
        known = status_id in elements.STATUS_IDS
    except Exception:                          # pragma: no cover - diagnostics
        known = bool(status_id)
    if not known:
        return {}
    carried = state.setdefault("ailments", {}).setdefault(pet_id, [])
    if status_id not in carried:
        carried.append(status_id)
    return {"pet": pet_id, "status": status_id,
            "speaks": speaking_budget(state, pet_id),
            "cured_by": "the healer, for nothing"}


def faint(state: dict, pet_id: str = "", *, at: float = 0.0,
          cause: str = "MONSTER") -> dict:
    """The companion goes down. Reversible, free to undo, and NOT the barrow.

    What this deliberately does NOT touch: `found`, `bond`, `met_at`, and
    `active`. The animal stays your chosen companion while it is unconscious,
    so that healing it puts it straight back to work without the player having
    to go and re-pick the thing they already picked. Fielding a different
    companion in the meantime is allowed and is the intended move if you have
    one — see `down_report`.
    """
    pet = BY_ID.get(pet_id or active_id(state))
    if pet is None:
        return {}
    if is_fainted(state, pet.id):
        return {"pet": pet.id, "fainted": False, "already": True}
    state.setdefault("vitality", {})[pet.id] = 0
    state.setdefault("fainted", []).append(pet.id)
    state.setdefault("fainted_at", {})[pet.id] = at
    counts = state.setdefault("faints", {})
    counts[pet.id] = int(counts.get(pet.id, 0)) + 1
    return {
        "pet": pet.id, "name": pet.name, "species": pet.species,
        "sprite": pet.sprite, "colour": pet.colour,
        "fainted": True, "cause": cause, "at": at,
        "times": counts[pet.id],
        "line": pet.on_faint,
        # Said plainly, the same way the barrow says it, because the player has
        # just lost their unasked help and being told the truth about it beats
        # being consoled about it.
        "cost": "No hints from that one until it is awake. Nothing else has "
                "changed: the bond it earned is intact and it is still yours.",
        "heal_cost": HEAL_COST_GOLD,
        "heal_line": "The healer wakes it for nothing. That is what the healer "
                     "is for.",
        "roads": [ROAD_BY_ID[r] for r in PETLESS_ROADS] + [ROAD_BY_ID["HEALER"]],
        "reversible": True,
    }


def rest(state: dict, pet_id: str = "", *, at: float = 0.0) -> dict:
    """What one finished encounter gives back. Call it when a battle ends.

    Paid whether or not the encounter was cleared, and that is the considered
    choice: bond is graded evidence and moves only on a clear, but a health bar
    is not mastery, and a recovery gated on success would take the hints away
    from precisely the player who is failing and needs them. It pays nothing to
    an animal that is DOWN — waking that one is the healer's job and the reason
    the player walks back to town.
    """
    pet_id = pet_id or active_id(state)
    if pet_id not in BY_ID or is_down(state, pet_id):
        return {"pet": pet_id, "recovered": 0}
    before = vitality(state, pet_id)
    after = min(VITALITY_MAX, before + REST_PER_ENCOUNTER)
    state.setdefault("vitality", {})[pet_id] = after
    return {"pet": pet_id, "name": BY_ID[pet_id].name,
            "recovered": after - before, "vitality": after, "max": VITALITY_MAX,
            "condition": condition(after), "blink": after <= CRITICAL_AT}


def heal(state: dict, pet_id: str = "", *, at: float = 0.0,
         source: str = "HEALER") -> dict:
    """Wake it, top it up, and clear whatever it was carrying. Costs nothing.

    The one entry point, so that a potion or a story beat that revives an animal
    later goes through the same door the healer does and cannot invent a second
    set of rules about what comes back.

    HEAL_COST_GOLD is 0 and the comment on the constant is the reason: a player
    who is broke because the smith ate their purse must still be able to get
    their hints back. The pressure this game wants is repairs, potions and
    upgrades. Thinking is not on that list.
    """
    pet = BY_ID.get(pet_id or active_id(state))
    if pet is None:
        return {"pet": pet_id, "healed": False}
    if is_fallen(state, pet.id):
        # The barrow is not a wound and the healer is not a resurrection.
        return {"pet": pet.id, "healed": False, "error": "it is not coming back"}
    was_down = is_fainted(state, pet.id)
    before = vitality(state, pet.id)
    cured = ailments(state, pet.id)
    state.setdefault("vitality", {})[pet.id] = VITALITY_MAX
    state["fainted"] = [p for p in (state.get("fainted") or []) if p != pet.id]
    state.setdefault("fainted_at", {}).pop(pet.id, None)
    state.setdefault("ailments", {}).pop(pet.id, None)
    state["spent_stand"] = [p for p in (state.get("spent_stand") or [])
                            if p != pet.id]
    return {
        "pet": pet.id, "name": pet.name, "healed": True,
        "was_down": was_down, "restored": VITALITY_MAX - before,
        "vitality": VITALITY_MAX, "max": VITALITY_MAX, "condition": "HALE",
        "cured": cured, "cost": HEAL_COST_GOLD, "source": source, "at": at,
        "line": pet.on_wake if was_down else pet.on_recall,
    }


def heal_all(state: dict, *, at: float = 0.0, source: str = "HEALER") -> dict:
    """The town visit. Every companion the player owns, awake and topped up, for
    nothing. Called once when the healer is spoken to; it is not worth making
    the player pick which animal to revive when the price of all of them is the
    same number and that number is zero."""
    down = [p for p in (state.get("fainted") or [])]
    rows = [heal(state, pet_id, at=at, source=source)
            for pet_id in list(state.get("found") or [])]
    rows = [r for r in rows if r.get("healed")]
    return {
        "healed": rows, "woken": down, "cost": HEAL_COST_GOLD,
        "line": ("Everything that walks with you is awake and whole. "
                 "It costs nothing. It has always cost nothing."),
    }


def down_report(state: dict | None = None, *, difficulty: str = "",
                pet_id: str = "") -> dict:
    """What is still open, with the companion on the floor. (B)

    This is the anti-spiral rule with a UI attached. The moment a player's hint
    source drops is the moment they are most likely to conclude the run is over,
    so this hands them, in one payload: the three roads that have never asked
    who was walking with them, whichever OTHER companion they already own and
    could field right now, and the fact that the healer charges nothing.

    Every number in it is quoted from the same constants the hint tree uses, so
    it cannot drift into being a comforting lie.
    """
    state = state or new_state()
    pet_id = pet_id or active_id(state)
    pet = BY_ID.get(pet_id)
    down = is_down(state, pet_id) if pet else False
    bench = [p for p in (state.get("found") or [])
             if p != pet_id and not is_down(state, p)]
    return {
        "companion": pet.id if pet else "",
        "name": pet.name if pet else "",
        "down": down,
        "fainted": is_fainted(state, pet_id) if pet else False,
        "fallen": is_fallen(state, pet_id) if pet else False,
        "vitality": vitality(state, pet_id) if pet else 0,
        "max": VITALITY_MAX,
        "condition": condition(vitality(state, pet_id)) if pet else "",
        "ailments": ailments(state, pet_id),
        # The floor under everything, quoted rather than restated.
        "open_rung": OPEN_RUNG,
        "free_solution_after": FREE_SOLUTION_AFTER,
        "petless_roads": list(PETLESS_ROADS),
        "roads": [ROAD_BY_ID[r] for r in PETLESS_ROADS] + [ROAD_BY_ID["HEALER"]],
        "route": fallback_route(pet_id, difficulty=difficulty, state=state),
        "swap_in": [{"id": p, "name": BY_ID[p].name, "tier": BY_ID[p].tier,
                     "vitality": vitality(state, p)} for p in bench],
        "heal_cost": HEAL_COST_GOLD,
        "line": ("Your companion is down, which costs you the help that arrives "
                 "unasked and costs you nothing else. The first rung of the tree "
                 "is open, the coach still answers a failed submission, and the "
                 "worked solution is free in focus after "
                 f"{FREE_SOLUTION_AFTER} attempts. The healer wakes it for "
                 "nothing when you get back."),
    }


# --------------------------------------------------------------------------
# Being seen, and being bought (C)
# --------------------------------------------------------------------------

def sight(state: dict, pet_id: str, *, at: float = 0.0) -> dict:
    """The overworld reporting that the player was somewhere and looked.

    Only counts for the animals that are actually found this way, and stops
    counting at what that animal wants, so a player who walks the same road for
    an hour banks nothing they can spend on anything else.
    """
    row = SIGHTED.get(pet_id)
    if not row or pet_id in (state.get("found") or []):
        return {"pet": pet_id, "seen": 0, "new": False}
    seen = state.setdefault("sightings", {})
    before = int(seen.get(pet_id, 0))
    after = min(row["needs"], before + 1)
    seen[pet_id] = after
    return {"pet": pet_id, "name": row["name"], "species": row["species"],
            "seen": after, "needs": row["needs"], "new": after > before,
            "closer": after > before and after < row["needs"],
            "ready": after >= row["needs"], "where": row["where"], "at": at}


def record_trade(state: dict, trade_id: str, *, at: float = 0.0) -> dict:
    """The goods and the gold have changed hands. Whoever took the money says so.

    This module does not touch gold. economy.py owns the purse, the vendor
    decides the price is paid, and this records the fact — which keeps the one
    thing pets.py is allowed to be certain about, namely that a trade happened,
    in the same place as everything else pets.py is certain about.
    """
    row = TRADES.get(trade_id)
    if not row:
        return {"trade": trade_id, "struck": False, "error": "no such trade"}
    trades = state.setdefault("trades", [])
    if trade_id not in trades:
        trades.append(trade_id)
    return {"trade": trade_id, "struck": True, "pet": row["pet"],
            "name": row["name"], "gold": row["gold"], "goods": row["goods"],
            "barter": row["barter"], "at": at}


def state_evidence(state: dict | None = None) -> dict:
    """The evidence keys this module stores for itself.

    `discovery_progress` reads a flat snapshot the engine assembles, and three
    of the facts in that snapshot live in the pet save rather than anywhere
    else. Handing them back in the right shape means the wiring is one line —
    `evidence.update(pets.state_evidence(state["pets"]))` — rather than three
    guesses about key names.
    """
    state = state or {}
    return {
        "starter_fallen": STARTER_ID in (state.get("fallen") or []),
        "sightings": dict(state.get("sightings") or {}),
        "trades": list(state.get("trades") or []),
    }


def catalogue(state: dict | None = None) -> list:
    """Every pet, found or not, in roster order, for the companion screen."""
    state = state or new_state()
    found = set(state.get("found", []))
    fallen = set(state.get("fallen") or [])
    bonds = state.get("bond", {}) or {}
    out = []
    for pet in PETS:
        row = pet.to_dict(int(bonds.get(pet.id, 0)), found=pet.id in found,
                          fallen=pet.id in fallen,
                          vitality=vitality(state, pet.id),
                          fainted=is_fainted(state, pet.id),
                          ailments=tuple(ailments(state, pet.id)))
        row["active"] = pet.id in (state.get("active") or [])
        out.append(row)
    return out


def tier_table() -> list:
    """The ladder, for the companion screen and the codex: six rows with the
    roster counted under each, so a player can see at a glance which depth they
    currently have no answer for."""
    return [
        {"tier": t.key, "label": t.label, "helps_through": t.depth,
         "index": t.index, "blurb": t.blurb,
         "covers": [d for d in curriculum.TIERS
                    if curriculum.tier_index(d) <= curriculum.tier_index(t.depth)],
         "companions": list(BY_TIER.get(t.key, ()))}
        for t in TIERS
    ]


# --------------------------------------------------------------------------
# Self-check
# --------------------------------------------------------------------------
#
# Five of these are load-bearing rules rather than tidiness, so they are proved
# here and asserted at import rather than left for a reviewer to notice:
#
#   1. No pet effect key may sit outside items.EFFECT_LABELS. An unknown key
#      would silently do nothing, which is worse than crashing.
#   2. No authored line may contain a literal answer. A pet that pastes code is
#      a Phoenix that costs nothing, and Phoenix costs the whole rank.
#   3. Every tier must have at least one companion in it, and every difficulty
#      the corpus can produce must be covered by at least one tier. A gap is a
#      depth at which the game silently has no unasked help.
#   4. There must be at least one road out that needs no companion at all. That
#      is the no-dead-end rule, stated as data.
#   5. The starter's death and its return must both be reachable, and the hidden
#      one must be findable, from data rather than from a promise.

_ANSWER_TELLS = (
    "def ",          # a function header is somebody's worked solution
    "return ",       # so is a return statement
    "import ",       # and an import line is a line of somebody's file
    "```",           # so is a fenced block
    "the answer is",
    "the solution is",
    # The three the rest of the codebase checks for. Held here too, so that this
    # module's own bar is never the loose one: tests/test_classes.py scans the
    # class trees and the artifacts against this list, and a roster that policed
    # itself more gently than the gear does would be the obvious place to hide.
    "solves it for you",
    "reveals the solution",
    "shows the solution",
    "here is the code",
    "copy this",
    "just paste",
)


def _authored_text(pet: Pet):
    """Every player-visible string this pet owns, with a label for the report."""
    yield "tagline", pet.tagline
    yield "blurb", pet.blurb
    yield "method", pet.method
    yield "fallback", pet.fallback
    yield "on_intervene", pet.on_intervene
    yield "on_cleared", pet.on_cleared
    yield "on_failed", pet.on_failed
    yield "above_tier", pet.above_tier
    yield "on_dismiss", pet.on_dismiss
    yield "on_recall", pet.on_recall
    yield "on_faint", pet.on_faint
    yield "on_wake", pet.on_wake
    for line in pet.idle:
        yield "idle", line
    for line in pet.bond_lines:
        yield "bond_line", line
    for trigger in pet.triggers:
        yield f"trigger:{trigger.kind}", trigger.line
    for key, body in pet.hints.items():
        yield f"hint:{key}", body
    if pet.discovery:
        yield "where", pet.discovery.where
        yield "how", pet.discovery.how
        yield "first_words", pet.discovery.first_words


def _module_text():
    """Authored strings belonging to the module rather than to one animal."""
    for road in ROADS:
        yield f"road:{road['id']}", road["title"]
        yield f"road:{road['id']}", road["detail"]
    for tier in TIERS:
        yield f"tier:{tier.key}", tier.blurb
    death = fall(new_state())
    for line in death["lines"]:
        yield "fall", line
    yield "fall", death["cost"]
    yield "routeless", fallback_route()["line"]
    for key, (label, blurb) in ACQUISITIONS.items():
        yield f"arrival:{key}", label
        yield f"arrival:{key}", blurb
    for _name, _floor, blurb in CONDITIONS:
        yield "condition", blurb
    probe = new_state()
    grant(probe, STARTER_ID)
    yield "faint", faint(probe)["cost"]
    yield "faint", faint(probe).get("heal_line", "")
    yield "down", down_report(probe)["line"]
    yield "heal", heal_all(probe)["line"]


def _validate() -> list:
    """Import-time guard. Returns the problems; the module refuses to load with any."""
    problems = []
    for pet in PETS:
        if pet.hint_kind not in HINT_KINDS:
            problems.append(f"{pet.id}: unknown hint kind {pet.hint_kind}")
        if pet.tier not in TIER_BY_KEY:
            problems.append(f"{pet.id}: unknown tier {pet.tier}")
        elif TIER_BY_KEY[pet.tier].depth not in curriculum.TIERS:
            problems.append(f"{pet.id}: tier depth is outside curriculum.TIERS")
        if pet.awarded not in (AWARD_EVIDENCE, AWARD_STORY):
            problems.append(f"{pet.id}: unknown award mode {pet.awarded}")
        if pet.lineage and pet.lineage not in {p.id for p in PETS}:
            problems.append(f"{pet.id}: lineage {pet.lineage} is not in the roster")
        if not pet.triggers:
            problems.append(f"{pet.id}: nothing ever makes it speak")
        for trigger in pet.triggers:
            if trigger.kind not in TRIGGER_KINDS:
                problems.append(f"{pet.id}: unknown trigger {trigger.kind}")
        for rank_index, effects in pet.passives.items():
            if not 0 <= rank_index < len(BOND_RANKS):
                problems.append(
                    f"{pet.id}: passive at nonexistent bond rank {rank_index}")
            for key in effects:
                if key not in items.EFFECT_LABELS:
                    problems.append(f"{pet.id}: effect {key!r} is outside EFFECT_LABELS")
        if len(pet.bond_lines) != len(BOND_RANKS):
            problems.append(f"{pet.id}: {len(pet.bond_lines)} bond lines for "
                            f"{len(BOND_RANKS)} ranks")
        if not pet.discovery or not pet.discovery.region:
            problems.append(f"{pet.id}: no discovery region, and the map needs one")
        elif pet.awarded == AWARD_EVIDENCE and not pet.discovery.needs:
            problems.append(f"{pet.id}: earnable, with nothing to earn")
        if not pet.on_faint or not pet.on_wake:
            problems.append(f"{pet.id}: goes down or gets up without saying anything")
        if not pet.discovery or pet.discovery.arrival not in ACQUISITIONS:
            problems.append(f"{pet.id}: unknown arrival "
                            f"{getattr(pet.discovery, 'arrival', '')!r}")
        for clause in (pet.discovery.needs if pet.discovery else ()):
            if clause.get("kind") not in DISCOVERY_CHECKS:
                problems.append(f"{pet.id}: unknown discovery check {clause.get('kind')}")
            if clause.get("kind") == "sighted" and clause.get("pet") != pet.id:
                # The row carries the pet id because `_discovery_row` is handed a
                # clause and nothing else, and a sighting of somebody else is not
                # evidence about this animal.
                problems.append(f"{pet.id}: a sighted clause that names "
                                f"{clause.get('pet')!r}")
            if clause.get("kind") == "trade_done":
                if not clause.get("trade"):
                    problems.append(f"{pet.id}: a trade with no id to record")
                if int(clause.get("gold", 0)) < 0:
                    problems.append(f"{pet.id}: a trade that pays the player")
            if clause.get("kind") == "puzzle_kind" and not clause.get("puzzle"):
                problems.append(f"{pet.id}: a puzzle clause naming no puzzle")
            if clause.get("kind") == "quest_done" and not clause.get("quest"):
                problems.append(f"{pet.id}: a quest clause naming no quest")
        for label, text in _authored_text(pet):
            lowered = (text or "").lower()
            for tell in _ANSWER_TELLS:
                if tell in lowered:
                    problems.append(f"{pet.id}: {label} reads like an answer ({tell!r})")

    for label, text in _module_text():
        lowered = (text or "").lower()
        for tell in _ANSWER_TELLS:
            if tell in lowered:
                problems.append(f"module: {label} reads like an answer ({tell!r})")

    # Every tier reachable. A gap is a depth at which nothing can ever help.
    for tier in TIERS:
        if not BY_TIER.get(tier.key):
            problems.append(f"tier {tier.key} has no companion in it")

    # Every depth the ladder knows about is covered by somebody.
    for depth in curriculum.TIERS:
        if not any(covers(p.id, depth) for p in PETS):
            problems.append(f"no companion covers {depth}")

    # Every evidence key a clause reads has to have somebody who writes it
    # named, or the codex draws a bar that can never fill.
    for pet in PETS:
        for clause in (pet.discovery.needs if pet.discovery else ()):
            kind = clause.get("kind")
            if kind in DISCOVERY_CHECKS \
                    and DISCOVERY_CHECKS[kind][0] not in EVIDENCE_SOURCES:
                problems.append(f"{pet.id}: {kind} reads "
                                f"{DISCOVERY_CHECKS[kind][0]!r}, which nobody "
                                f"is named as writing")

    # And there is always a road that needs nobody.
    if not all(r in ROAD_BY_ID for r in PETLESS_ROADS):
        problems.append("a companion-free road is named but not defined")

    # The tier gate covers the passive path too, so the vocabulary it gates has
    # to be real vocabulary. A typo here would silently un-gate a key.
    for key in DEPTH_GATED_EFFECTS:
        if key not in items.EFFECT_LABELS:
            problems.append(f"depth-gated effect {key!r} is outside EFFECT_LABELS")
    # Nothing a companion carries may reach past its tier. Every effect on the
    # roster is either economy — which bond buys outright — or depth-gated.
    for pet in PETS:
        depth = TIER_BY_KEY[pet.tier].depth
        for effects in pet.passives.values():
            for key in effects:
                if key in DEPTH_GATED_EFFECTS:
                    continue
                if key in _READS_THE_ROOM:
                    problems.append(
                        f"{pet.id}: {key!r} reads the encounter and is not in the "
                        f"gate, so a {pet.tier} animal carrying it would be "
                        f"answering past {depth}")

    # The arc, proved rather than promised.
    if STARTER_ID not in BY_ID:
        problems.append("the starter is not in the roster")
    elif BY_ID[STARTER_ID].tier != "TUTORIAL":
        problems.append("the starter is not TUTORIAL tier")
    elif BY_ID[STARTER_ID].lineage != RETURN_ID:
        problems.append("the starter does not point at its return")
    if RETURN_ID not in BY_ID:
        problems.append("the returned starter is not in the roster")
    elif BY_ID[RETURN_ID].tier != "LEGENDARY":
        problems.append("the return is not LEGENDARY tier")
    elif BY_ID[RETURN_ID].species != BY_ID[STARTER_ID].species:
        problems.append("the return is a different animal from the starter")
    elif not any(c.get("kind") == "starter_fallen"
                 for c in BY_ID[RETURN_ID].discovery.needs):
        problems.append("the return is not gated on the death")
    if HIDDEN_ID not in BY_ID or BY_ID[HIDDEN_ID].tier != "HIDDEN":
        problems.append("the hidden one is missing or is not HIDDEN tier")
    elif not BY_ID[HIDDEN_ID].discovery.needs:
        problems.append("the hidden one cannot be found")

    # The five the player named, still here.
    for named in ("jaguar", "python", "llama", "penguin", "velociraptor"):
        if named not in BY_ID:
            problems.append(f"{named} was named by the player and is missing")

    # C: twelve animals, twelve ways in. A roster where two of them arrive the
    # same way is a roster that has started repeating itself, and the whole point
    # of the rewrite was that it had done exactly that eleven times.
    arrivals = [p.discovery.arrival for p in PETS if p.discovery]
    for arrival in set(arrivals):
        if arrivals.count(arrival) > 1:
            problems.append(f"{arrivals.count(arrival)} companions arrive by "
                            f"{arrival}, which makes it a shape rather than an event")
    for key in ACQUISITIONS:
        if key not in arrivals:
            problems.append(f"arrival {key} is described and nobody uses it")

    # B: the anti-spiral numbers, as arithmetic rather than as good intentions.
    if HEAL_COST_GOLD != 0:
        problems.append("healing a companion costs gold, and learning would "
                        "then have a price a broke player cannot pay")
    if not SPLASH_CAP * 3 >= VITALITY_MAX > SPLASH_CAP * 2:
        problems.append(f"SPLASH_CAP {SPLASH_CAP} does not put the floor at "
                        f"three blows from full")
    if REST_PER_ENCOUNTER <= 0:
        problems.append("a hurt companion never recovers on its own")
    if not 0 < CRITICAL_AT < VITALITY_MAX:
        problems.append("the bar never blinks, or never stops")
    if LAST_STAND < 1:
        problems.append("the last stand leaves nothing standing")
    if AILMENT_SPEECH_COST >= min(r.interventions for r in BOND_RANKS) + 1:
        problems.append("an ailment can silence a companion outright")

    # And the line that must not blur: a faint is not the barrow.
    probe = new_state()
    grant(probe, STARTER_ID)
    faint(probe, STARTER_ID)
    if is_fallen(probe, STARTER_ID):
        problems.append("fainting put a companion on the fallen list")
    if not heal(probe, STARTER_ID).get("healed"):
        problems.append("fainting is not reversible, which makes it a second barrow")
    if intervention(STARTER_ID, difficulty="TUTORIAL", state={"fainted": [STARTER_ID]},
                    signals={"syntax_failures": 9, "seconds_elapsed": 9999}):
        problems.append("a fainted companion still speaks")

    if ACTIVE_LIMIT != 1:
        problems.append("ACTIVE_LIMIT must be 1")
    if not 9 <= len(PETS) <= 12:
        problems.append(f"{len(PETS)} companions, which is outside nine to twelve")
    return problems


def self_check() -> dict:
    """Counts, and the proofs. Safe to call from a test or from the command line."""
    effect_keys = sorted({key for pet in PETS
                          for effects in pet.passives.values() for key in effects})
    stray = [key for key in effect_keys if key not in items.EFFECT_LABELS]

    answerish = []
    for pet in PETS:
        for label, text in _authored_text(pet):
            lowered = (text or "").lower()
            answerish += [f"{pet.id}.{label}"
                          for tell in _ANSWER_TELLS if tell in lowered]
    for label, text in _module_text():
        lowered = (text or "").lower()
        answerish += [f"module.{label}" for tell in _ANSWER_TELLS if tell in lowered]

    # Cross-checks against the modules whose vocabularies these tables borrow.
    # Imported lazily: a pet is allowed to name a weakness without the pet system
    # taking a hard dependency on the combat system to load at all.
    unknown_vocab = []
    try:
        from . import grading, skills as skills_mod, tactics
        for pet in PETS:
            if pet.skill not in skills_mod.SKILLS:
                unknown_vocab.append(f"{pet.id}: skill {pet.skill}")
            keyed = KEYED_BY[pet.hint_kind]
            for key in pet.hints:
                if keyed == "category" and key not in grading.FAILURE_CATEGORIES:
                    unknown_vocab.append(f"{pet.id}: category {key}")
                if keyed == "weakness" and key not in tactics.WEAKNESSES \
                        and key not in skills_mod.PATTERN_TO_SKILL:
                    unknown_vocab.append(f"{pet.id}: weakness {key}")
                if keyed == "pattern" and key not in skills_mod.PATTERN_TO_SKILL \
                        and key not in ("BACKTRACKING", "GRAPH"):
                    unknown_vocab.append(f"{pet.id}: pattern {key}")
    except Exception as exc:                   # pragma: no cover - diagnostics only
        unknown_vocab.append(f"cross-check unavailable: {exc}")

    # The world vocabularies the new arrival clauses borrow. Separate from the
    # block above and deliberately silent when the module is unavailable: a
    # typo'd quest id must be caught, and a sibling module mid-edit must not
    # turn this report red.
    world_vocab = []
    try:
        from . import puzzles as puzzlemod
        for pet in PETS:
            for clause in pet.discovery.needs:
                if clause.get("kind") == "puzzle_kind" \
                        and clause.get("puzzle") not in puzzlemod.PUZZLE_KINDS:
                    world_vocab.append(f"{pet.id}: puzzle {clause.get('puzzle')}")
    except Exception:                          # pragma: no cover - diagnostics
        pass
    try:
        from . import quests as questmod
        for pet in PETS:
            for clause in pet.discovery.needs:
                if clause.get("kind") == "quest_done" \
                        and clause.get("quest") not in questmod.QUEST_BY_ID:
                    world_vocab.append(f"{pet.id}: quest {clause.get('quest')}")
    except Exception:                          # pragma: no cover - diagnostics
        pass

    # -- the blast, exercised rather than described -------------------------
    # A real animal with a real bond, hit with ordinary monster sweeps until it
    # drops, then asked all the questions rule B says must have these answers.
    loud = {"syntax_failures": 9, "failed_attempts": 9, "seconds_elapsed": 9999,
            "seconds_since_progress": 9999, "hidden_failures": 3,
            "category_counts": {"PYTHON_RECALL": 3}}
    blast = new_state()
    grant(blast, "python")
    award(blast, "python", 120)
    bond_before = int(blast["bond"]["python"])
    blows = 0
    while not is_fainted(blast, "python") and blows < 50:
        take_aoe(blast, 12, max_health=100)
        blows += 1
    spoke_down = intervention("python", bond=bond_before, difficulty="EASY",
                              signals=loud, state=blast)
    route_down = down_report(blast, difficulty="EASY")
    passives_down = party_effects(["python"], blast["bond"], difficulty="EASY",
                                  state=blast)
    kept_everything = (int(blast["bond"]["python"]) == bond_before
                       and "python" in blast["found"]
                       and active_id(blast) == "python"
                       and not is_fallen(blast, "python"))
    woken = heal(blast, "python")
    spoke_after = intervention("python", bond=bond_before, difficulty="EASY",
                               signals=loud, state=blast)
    examples = []
    for pct in (6, 12, 25, 60):
        cost = splash_damage(pct, max_health=100)
        examples.append({"hit_percent_of_player_bar": pct,
                         "vitality_cost": cost,
                         "blows_from_full": -(-VITALITY_MAX // max(1, cost))})

    tiers = {t.key: list(BY_TIER.get(t.key, ())) for t in TIERS}
    depth_cover = {d: [p.id for p in PETS if covers(p.id, d)]
                   for d in curriculum.TIERS}

    # The death and the return, exercised rather than described.
    probe = new_state()
    grant(probe, STARTER_ID)
    death = fall(probe)
    return_gated = any(c.get("kind") == "starter_fallen"
                       for c in BY_ID[RETURN_ID].discovery.needs)

    lines = sum(1 for pet in PETS for _ in _authored_text(pet))
    species = sorted({pet.species for pet in PETS})
    return {
        "companions": len(PETS),
        "distinct_species": len(species),
        "species": species,
        "player_named": sum(1 for pet in PETS
                            if pet.id in ("jaguar", "python", "llama", "penguin",
                                          "velociraptor")),
        "authored": len(PETS) - 5,

        # -- B: one at a time, reversibly
        "active_limit": ACTIVE_LIMIT,
        "one_at_a_time": ACTIVE_LIMIT == 1,
        "dismissal_reversible": True,      # `dismiss` never touches `found`

        # -- A: the ladder
        "tiers": [t.key for t in TIERS],
        "tier_roster": tiers,
        "tier_depths": {t.key: t.depth for t in TIERS},
        "every_tier_reachable": all(tiers.values()),
        "depth_cover": depth_cover,
        "every_depth_has_a_companion": all(depth_cover.values()),

        # -- A: the ladder holds on the passive path too
        "depth_gated_effects": sorted(DEPTH_GATED_EFFECTS),
        "ungated_room_readers": sorted(
            {key for pet in PETS for effects in pet.passives.values()
             for key in effects
             if key in _READS_THE_ROOM and key not in DEPTH_GATED_EFFECTS}),
        "tier_gate_covers_passives": not {
            key for pet in PETS for effects in pet.passives.values()
            for key in effects
            if key in _READS_THE_ROOM and key not in DEPTH_GATED_EFFECTS},

        # -- F: no dead ends
        "open_rung": OPEN_RUNG,
        "free_solution_after": FREE_SOLUTION_AFTER,
        "petless_roads": list(PETLESS_ROADS),
        "no_dead_end": (all(r in ROAD_BY_ID for r in PETLESS_ROADS)
                        and all(depth_cover.values())),

        # -- A: the blast, and B: the reason it is not a spiral
        "vitality_max": VITALITY_MAX,
        "pet_endurance": PET_ENDURANCE,
        "splash_cap": SPLASH_CAP,
        "splash_examples": examples,
        "blows_from_full_at_twelve_percent": blows,
        "min_blows_from_full": -(-VITALITY_MAX // SPLASH_CAP),
        "rest_per_encounter": REST_PER_ENCOUNTER,
        "critical_at": CRITICAL_AT,
        "last_stand": LAST_STAND,
        "heal_cost_gold": HEAL_COST_GOLD,
        "healing_is_free": HEAL_COST_GOLD == 0,
        "fainted_says_nothing": spoke_down is None,
        "fainted_pays_no_passives": passives_down == {},
        "fainted_keeps_bond_found_and_field": kept_everything,
        "fainted_keeps_the_petless_roads": (
            route_down["open_rung"] == OPEN_RUNG
            and route_down["free_solution_after"] == FREE_SOLUTION_AFTER
            and sorted(route_down["petless_roads"]) == sorted(PETLESS_ROADS)),
        "fainting_is_reversible": bool(woken.get("healed")),
        "speaks_again_once_healed": spoke_after is not None,
        "faint_is_not_the_barrow": not is_fallen(blast, "python"),
        # Rule 8: the tree the tier opened is still open and still payable.
        "fainted_keeps_the_tree_its_tier_opened": all(
            covers("python", d) == covers_tier(BY_ID["python"].tier, d)
            for d in curriculum.TIERS),
        "ailment_never_silences": all(
            speaking_budget({"bond": {"python": b}, "ailments":
                             {"python": list(("POISONED", "BURNING"))}},
                            "python") >= 1
            for b in (0, 400)),

        # -- C: twelve animals, twelve ways in
        "arrivals": {p.id: p.discovery.arrival for p in PETS},
        "arrival_kinds": sorted(ACQUISITIONS),
        "distinct_arrivals": len({p.discovery.arrival for p in PETS}),
        "one_way_in_each": len({p.discovery.arrival for p in PETS}) == len(PETS),
        "trades": TRADES,
        "sighted": SIGHTED,
        "world_vocabulary": world_vocab,
        "evidence_keys": sorted({DISCOVERY_CHECKS[c.get("kind")][0]
                                 for p in PETS for c in p.discovery.needs
                                 if c.get("kind") in DISCOVERY_CHECKS}),
        "evidence_keys_from_this_module": sorted(state_evidence({})),
        "evidence_sources": EVIDENCE_SOURCES,
        "evidence_keys_undocumented": sorted(
            {DISCOVERY_CHECKS[c.get("kind")][0] for p in PETS
             for c in p.discovery.needs if c.get("kind") in DISCOVERY_CHECKS}
            - set(EVIDENCE_SOURCES)),

        # -- C: the arc
        "starter": STARTER_ID,
        "starter_tier": BY_ID[STARTER_ID].tier,
        "starter_dies_at": FALLS_AT_DUNGEON,
        "starter_death_reachable": bool(death["fell"]),
        "starter_death_leaves_no_companion": not active_id(probe),
        "starter_kept_in_codex": STARTER_ID in probe["found"],
        "starter_returns_as": RETURN_ID,
        "return_tier": BY_ID[RETURN_ID].tier,
        "return_same_animal": BY_ID[RETURN_ID].species == BY_ID[STARTER_ID].species,
        "starter_return_reachable": return_gated,
        "returns_at": RETURNS_AT_DUNGEON,

        # -- E: the hidden one
        "hidden": HIDDEN_ID,
        "hidden_findable": bool(BY_ID[HIDDEN_ID].discovery.needs),
        "hidden_deed": BY_ID[HIDDEN_ID].discovery.how,

        "skills_covered": sorted({pet.skill for pet in PETS}),
        "hint_kinds": len(HINT_KINDS),
        "bond_ranks": len(BOND_RANKS),
        "triggers": sum(len(pet.triggers) for pet in PETS),
        "trigger_kinds_used": sorted({t.kind for pet in PETS for t in pet.triggers}),
        "hint_lines": sum(len(pet.hints) for pet in PETS),
        "voice_lines": sum(len(pet.idle) + len(pet.bond_lines) + 6 for pet in PETS),
        "discovery_clauses": sum(len(pet.discovery.needs) for pet in PETS),
        "authored_strings": lines,
        "passive_effect_keys": effect_keys,
        "effect_keys_outside_items": stray,
        "effect_keys_ok": not stray,
        "lines_reading_as_answers": answerish,
        "no_literal_answers": not answerish,
        "unknown_vocabulary": unknown_vocab,
        "interview_sealed": (not available_in("interview")
                             and not party_effects(list(PET_IDS), {}, "interview")),
        "seal_respected": not available_in("adventure", "python_village", sealed=True),
        "silenced_regions": list(SILENCED_REGIONS),
        "ok": (not stray and not answerish and not unknown_vocab
               and not world_vocab
               and all(tiers.values()) and all(depth_cover.values())
               and ACTIVE_LIMIT == 1 and bool(death["fell"]) and return_gated
               # B, proved: down is silent, free to undo, and costs nothing else
               and spoke_down is None and passives_down == {}
               and kept_everything and bool(woken.get("healed"))
               and spoke_after is not None and HEAL_COST_GOLD == 0
               and sorted(route_down["petless_roads"]) == sorted(PETLESS_ROADS)
               # C, proved: nobody arrives the way anybody else did
               and len({p.discovery.arrival for p in PETS}) == len(PETS)
               and not (_READS_THE_ROOM - DEPTH_GATED_EFFECTS
                        ) & {key for pet in PETS
                             for effects in pet.passives.values()
                             for key in effects}),
    }


# --------------------------------------------------------------------------
# WIRING
# --------------------------------------------------------------------------
#
# Everything below is additive. Every existing call site keeps working untouched;
# the new ones are what makes the blast and the twelve arrivals real.
#
# COMBAT — whoever resolves an area attack (engine, incantation's AoE movesets,
# a boss phase). ONE call, after the player's own damage is applied, with the
# numbers already computed for the player:
#
#     hit = pets.take_aoe(state["pets"], damage_dealt_to_player,
#                         max_health=player_max_stamina,
#                         source="BOSS" if enc.boss_id else "MONSTER",
#                         element=attacker_element,        # optional
#                         shielded=effects.get("pet_guard", 0.0),   # optional
#                         inflicts=status_id_or_"",        # optional
#                         mode=enc.mode, region_id=region_id,
#                         sealed=finalexam.sealed(enc, "PET"),
#                         at=time.time())
#
# None means nothing was in the blast. Otherwise draw the bar from `before`,
# `after`, `condition` and `blink`, and if `hit["faint"]` is set, play that scene
# — it carries the animal's own line, the roads out, and the fact that waking it
# costs nothing.
#
# END OF BATTLE — pets.rest(state["pets"]) once, beside the focus refill. It
# pays nothing to an animal that is down, which is the walk back to town.
#
# TOWN — the healer calls pets.heal_all(state["pets"], at=time.time()) and
# charges pets.HEAL_COST_GOLD, which is 0 and must stay 0. pets.heal(state,
# pet_id) is the single-animal door, for a potion or a story beat later.
#
# PASSIVES — engine already calls pets.party_effects(active, bonds, mode=,
# difficulty=). Add `state=self.state["pets"]` so an unconscious animal stops
# paying out its passives as well as its lines.
#
# EVIDENCE — `_pet_evidence` needs four more keys, three of which the game
# already keeps:
#
#     "quests_done":   list(self.state["quests"].get("done", [])),
#     "puzzle_clears": dict(self.state["quests"].get("puzzle_clears", {})),
#     **pets.state_evidence(self.state["pets"]),   # sightings, trades,
#                                                  # starter_fallen
#
# and one stat, recorded by whoever owns armour repairs:
# stats["armour_repairs"] += 1 on every repair paid for.
#
# OVERWORLD — pets.SIGHTED says which animals are found by being seen and where.
# Call pets.sight(state["pets"], pet_id) when the player is in that place and
# looks; it is idempotent past the count that animal wants.
#
# VENDORS — pets.TRADES carries the price and the goods for the two bought
# animals. economy.py takes the gold; then call
# pets.record_trade(state["pets"], trade_id).
#
# SCREENS — pets.catalogue rows now carry vitality, condition, blink, fainted,
# ailments and the arrival label. pets.down_report(state["pets"]) is the panel to
# show the moment a companion drops, and it is the panel that keeps the promise.

_PROBLEMS = _validate()
if _PROBLEMS:                                  # pragma: no cover - authored data
    raise ValueError("gauntlet.pets is inconsistent: " + "; ".join(_PROBLEMS))


if __name__ == "__main__":
    print(json.dumps(self_check(), indent=2))
