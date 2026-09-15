"""Class movesets, area attacks, and the curve that makes an old move fade.

This module is the layer between a character class and the line of Python that
actually kills something. It adds no combat vocabulary: every blow it delivers
is an `incantation.cast`, graded by the same three layers, run in the same
sandbox, refusing the same way. What it adds is SHAPE — how many monsters one
typed idea reaches, how much typing that costs, and how a move you learned in
chapter one stops mattering without ever being taken away from you.

THE SPINE, RESTATED
-------------------
`incantation.measure_complexity` decides what a cast is worth by reading the
Python the player wrote. Nothing in this file is allowed to become a second
spine. Every multiplier here — rank fade, groove, variety, dual-class penalty —
is applied MULTIPLICATIVELY to whatever the typing already earned, which means
none of them can invert the incentive. A faded rung-one move rewards a composed
comprehension exactly 2.9 times better than a bare name, the same ratio a fresh
capstone does. The player is never paid to write worse Python in order to use a
better move.

WHY A MOVE IS SEVERAL INCANTATIONS
----------------------------------
Hitting four monsters should cost four monsters' worth of thinking. That is the
whole price model and it is the only honest one available in a game whose
attack is typing:

    SINGLE  one line.    CLEAVE  two lines, two monsters.
    CHAIN   two lines, three monsters, each further one taking less.
    STORM   three lines, everything standing.

The spine is cast in order, in one turn. Each step is a real incantation with
real holes, and each step lands on its own merits: miss the third line of a
STORM and you keep the first two. The turn is only wasted if NOTHING lands,
because a player who wrote two correct lines out of three did not waste
anything, they learned where the third one goes.

WHY OLD MOVES FADE AND NEVER EXPIRE
-----------------------------------
A move that is REMOVED teaches nothing: the player never finds out it got weak,
they just find out it is gone. A move that is visibly weak teaches that you have
outgrown it, every single time you cast it, without a word of text. So FIRST
WARD still casts at level ninety, still counts for mastery, still builds groove,
and lands for thirty per cent of what it once did. The floor is thirty and not
zero on purpose: thirty per cent finishes a wounded shade and is worth casting
when the focus is short. Zero would be expiry wearing a curve.

WHY REPETITION AND NOVELTY ARE BOTH PAID
----------------------------------------
They pull apart, so they are paid in different currencies:

    REPETITION is paid LARGE and SATURATING. Groove climbs to +25% over about
    five correct casts of the same move and then stops. It also pays a second,
    bigger dividend that this module does not own: re-casting is what raises the
    incantation scaffold tier, and a higher tier means the player is typing more
    of the line themselves, which the complexity measure sees directly.
    REPETITION IS THE ONLY THING THAT CAN RAISE THE SPINE ITSELF.

    NOVELTY is paid SMALL and ENDLESS. +12% for not repeating the move you cast
    last turn, +15% the first time a move ever lands. Never saturates.

The honest result, computed in `self_check()` over a real incantation rather
than asserted here: a player who drills one move and a player who alternates two
stay within a few per cent of each other at every horizon, trading the lead back
and forth. That is deliberate. If either strategy dominated, the other would
stop being played and half the lesson would go with it. What actually separates
them after twenty turns is not damage, it is that one of them is fluent in two
idioms and the other in one — and the second player finds that out the next time
the game demands the idiom they never drilled.

WHAT THE EXAM SEES
------------------
Nothing from this file. Every multiplier here is a fact about the character —
how far up the tree they invested, how many times they have drilled this move —
and `finalexam` seals that under BUILD. So `scale_for(..., sealed=True)` returns
exactly one, and a timed practical context alone is enough to trigger it even if the
caller forgot the keyword. Damage in a measured run is `complexity.weight` and
nothing else, which is the only reading under which the exam measures Python
rather than measuring a save file.

Pure stdlib. Importing this module builds a catalogue and touches nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from . import elements, incantation

# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
# `primary_share` and `splash` are fractions of the move's PAYLOAD, which is the
# sum of what every landed spine step earned. The numbers below are chosen so
# that area attacks buy TURNS and never raw damage: compare a shape's total
# delivery against casting SINGLE once per monster over that many turns, and
# area is worth between 0.87 and 1.35 of it. It is a tempo weapon with a real
# failure mode, not an upgrade. `self_check()` prints that table.

SINGLE = "SINGLE"
CLEAVE = "CLEAVE"
CHAIN = "CHAIN"
STORM = "STORM"


@dataclass(frozen=True)
class Shape:
    id: str
    label: str
    spine: int                # how many incantations the move demands
    max_targets: int          # 0 means everything standing
    min_targets: int          # below this the move refuses, and costs nothing
    primary_share: float
    splash: float
    decay: float = 1.0        # per-jump falloff, CHAIN only
    blurb: str = ""

    def targets_wanted(self, living: int) -> int:
        cap = living if self.max_targets == 0 else min(self.max_targets, living)
        return max(0, cap)

    def share(self, index: int) -> float:
        """What the target at position `index` takes, as a fraction of payload."""
        if index == 0:
            return self.primary_share
        return self.splash * (self.decay ** (index - 1))

    def to_dict(self) -> dict:
        return asdict(self)


SHAPES = {
    SINGLE: Shape(SINGLE, "Single", 1, 1, 1, 1.00, 0.00,
                  blurb="One line, one monster. The whole game is still this."),
    CLEAVE: Shape(CLEAVE, "Cleave", 2, 2, 2, 0.70, 0.50,
                  blurb="Two lines that reach the thing beside it."),
    CHAIN: Shape(CHAIN, "Chain", 2, 3, 2, 0.60, 0.42, decay=0.70,
                 blurb="Two lines that jump, weaker at every jump."),
    STORM: Shape(STORM, "Storm", 3, 0, 2, 0.45, 0.45,
                 blurb="Three lines, and everything still standing takes them."),
}

SHAPE_IDS = (SINGLE, CLEAVE, CHAIN, STORM)


# ---------------------------------------------------------------------------
# The rank curve
# ---------------------------------------------------------------------------
# Seven rungs, matching the seven nodes in a skill-tree branch, because that is
# where movesets are learned. `reach` is the highest rung the player has been
# granted; the gap between reach and a move's rung is how out of date it is.
#
#   gap  0     1     2     3     4     5     6
#   mult 1.00  0.84  0.71  0.59  0.50  0.42  0.35
#
# A stated curve, not a cliff: every step is a sixth quieter than the one
# before, and the floor is reached exactly at the seventh rung, so the player
# watches a move dim across the whole game instead of arriving one morning to
# find it dead. FADE_FLOOR is 0.35 and not zero because thirty-five per cent
# still finishes a wounded shade and is still worth casting when focus is
# short. Zero would be expiry wearing a curve.

MAX_RUNG = 7
FADE_BASE = 0.84
FADE_FLOOR = 0.35


def fade(rung: int, reach: int) -> float:
    """How much of its old strength a rung-N move has when you have reached M."""
    gap = max(0, int(reach) - int(rung))
    return round(max(FADE_FLOOR, FADE_BASE ** gap), 4)


def fade_table(rung: int = 1) -> list:
    """The curve, for a UI that wants to show the player where a move is going."""
    return [{"reach": r, "multiplier": fade(rung, r)}
            for r in range(int(rung), MAX_RUNG + 1)]


# ---------------------------------------------------------------------------
# Repetition and novelty
# ---------------------------------------------------------------------------

# THE INVARIANT THAT SIZES ALL FOUR OF THESE NUMBERS: the span of what the
# TYPING can do must be strictly wider than the span of everything this module
# can do, or a player would eventually be better off reaching for a fresh move
# than for a better line. Measured:
#
#   typing   WEIGHT_MAX / WEIGHT_MIN                      = 3.00 / 0.55 = 5.45x
#   this     (1 / FADE_FLOOR) * groove * variety * fresh  = 2.86 * 1.61 = 4.60x
#
# Complexity wins by twenty per cent, and `self_check()` fails if it ever stops
# winning. Every number below was chosen to keep that inequality true.

GROOVE_GAIN = 0.25            # the ceiling repetition pays
GROOVE_DECAY = 0.55           # how fast it gets there: ~5 casts
VARIETY_BONUS = 0.12          # not the move you cast last turn
FRESH_BONUS = 0.15            # the first time a move ever lands
DUAL_SCALE = 0.75             # a move borrowed from another class's tree


def groove(casts: int) -> float:
    """Fluency dividend for re-casting a move you already know.

    Saturating, on purpose: repetition should be worth reaching for and never
    worth farming. And it is a MULTIPLIER on the complexity term, so grinding
    `i += 1` two hundred times multiplies a very small number by 1.3 and the
    player can see that it is not working. Repetition amplifies what you are
    repeating; it cannot manufacture value out of a trivial line.
    """
    n = max(0, int(casts))
    return round(1.0 + GROOVE_GAIN * (1.0 - GROOVE_DECAY ** n), 4)


# ---------------------------------------------------------------------------
# The seal
# ---------------------------------------------------------------------------
# `finalexam.BUILD` is the crutch the editor_automaton takes away: "Attribute
# and gear effects". Every multiplier in this module is one of those. Rank fade,
# groove, variety, freshness and the dual-class penalty are all facts about the
# CHARACTER — how far up the tree they invested, how many times they have drilled
# this move — and a measured run is not allowed to read any of them. What it
# reads is the line the player just typed, which is `complexity.weight`, and
# nothing else.
#
# So under the seal `scale_for` returns exactly 1.0. Not a floor, not a reduced
# bonus: one, so that damage in the exam IS the typing and a reader of the log
# can verify that by multiplying nothing.
#
# It cuts both ways and that is the point. A player whose only move is faded to
# 0.35 does not carry that penalty into the exam either. The exam measures the
# Python. It does not know the player has a skill tree.
SEALED_SCALE = 1.0
SEALED_ROW = {"label": "sealed", "multiplier": 1.0,
              "why": "measured run: damage is the line you typed and nothing else"}


def is_sealed(context=None, *, sealed: bool = False) -> bool:
    """Whether this module's multipliers are switched off for this cast.

    Takes the caller's `finalexam.sealed(encounter, "BUILD")` when it is given
    one, and falls back to reading the context's mode when it is not. The
    fallback is a guard rail in the same spirit as `pets.available_in`: it can
    only ever refuse MORE than finalexam refuses, never less, so a caller who
    forgot the keyword still cannot smuggle a class bonus into an exam.
    """
    if sealed:
        return True
    return getattr(context, "mode", "adventure") == "interview"


def scale_for(book: dict, move_id: str, *, reach: int | None = None,
              sealed: bool = False) -> dict:
    """Every multiplier this module contributes, itemised so a UI can show it.

    Itemised rather than pre-multiplied because a player who cannot see why a
    number moved concludes the number is random, and a player who concludes that
    stops optimising the only thing worth optimising, which is the Python.

    `sealed` is `finalexam.sealed(encounter, "BUILD")`. Under it every row below
    is withheld and the total is exactly 1.0 — see SEALED_SCALE.
    """
    move = BY_ID.get(move_id)
    if move is None:
        return {"total": 1.0, "rows": []}
    if sealed:
        return {"total": SEALED_SCALE, "rows": [dict(SEALED_ROW)],
                "sealed": True}
    book = book or {}
    at = reach_of(book) if reach is None else int(reach)
    rows = []
    fade_mult = fade(move.rung, at)
    rows.append(("rank", fade_mult,
                 "rung %d against reach %d" % (move.rung, at)))
    groove_mult = groove(int((book.get("casts") or {}).get(move_id, 0)))
    rows.append(("groove", groove_mult,
                 "%d landings" % int((book.get("casts") or {}).get(move_id, 0))))
    fresh = move_id not in (book.get("landed") or [])
    if fresh:
        rows.append(("first cast", 1.0 + FRESH_BONUS, "never landed before"))
    varied = bool(book.get("last")) and book.get("last") != move_id
    if varied:
        rows.append(("variety", 1.0 + VARIETY_BONUS, "not the move you just cast"))
    if move.class_id and book.get("class") and move.class_id != book.get("class"):
        rows.append(("borrowed", DUAL_SCALE, "another discipline's move"))
    total = 1.0
    for _, value, _ in rows:
        total *= value
    return {
        "total": round(total, 4),
        "rows": [{"label": label, "multiplier": round(value, 4), "why": why}
                 for label, value, why in rows],
    }


# ---------------------------------------------------------------------------
# Elements, and what the client draws
# ---------------------------------------------------------------------------
# One element per class, because a class is a way of thinking and an element is
# what that looks like when it hits something.

CLASS_ELEMENT = {
    "analyst": elements.LIGHTNING,   # arrives already finished
    "berserker": elements.BRUTE,     # no finish at all
    "archivist": elements.VOID,      # the things that were
    "warden": elements.COLD,         # the stop
    "artificer": elements.FIRE,      # the forge
    "seer": elements.POISON,         # what it sees, it spreads
}

# web/js/spellfx.js ships five motion laws. Two of ours have no law of their own
# yet, so each names the law to use until it does. A pass that adds `venom` and
# `void` to ELEMENTS changes these two lines and nothing else.
FX_LAW = {
    elements.FIRE: "fire", elements.COLD: "frost", elements.LIGHTNING: "lightning",
    elements.BRUTE: "force", elements.POISON: "venom", elements.VOID: "void",
    elements.NEUTRAL: "force",
}
FX_LAW_FALLBACK = {"venom": "arcane", "void": "arcane"}

# Four roles per ramp, the vocabulary spellfx.SPELL_COLOURS already speaks.
FX_COLOUR = {
    elements.FIRE: {"key": "#ff8a2a", "hot": "#ffe8a0", "deep": "#7a1c0c",
                    "ink": "#0b0a12"},
    elements.COLD: {"key": "#8fd8ff", "hot": "#eafaff", "deep": "#123a52",
                    "ink": "#0b0a12"},
    elements.LIGHTNING: {"key": "#ffe36a", "hot": "#fffbe8", "deep": "#4a3a00",
                         "ink": "#0b0a12"},
    elements.BRUTE: {"key": "#e0d6c4", "hot": "#fffaf0", "deep": "#3a2f22",
                     "ink": "#0b0a12"},
    elements.POISON: {"key": "#8fe86a", "hot": "#e4ffd0", "deep": "#123f1a",
                      "ink": "#0b0a12"},
    elements.VOID: {"key": "#b48aff", "hot": "#ece0ff", "deep": "#241040",
                    "ink": "#0b0a12"},
    elements.NEUTRAL: {"key": "#cdd6e0", "hot": "#ffffff", "deep": "#2a2f38",
                       "ink": "#0b0a12"},
}


# ---------------------------------------------------------------------------
# The moves
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Move:
    """One class move: a shape, and the incantations it is spelled out of."""
    id: str
    name: str
    class_id: str
    rung: int                 # 1..7, matching the tree node that grants it
    shape: str
    spine: tuple              # incantation ids, cast in this order
    note: str                 # one line: when you reach for this
    flavour: str

    # -- derived -----------------------------------------------------------
    @property
    def incantations(self) -> tuple:
        return tuple(incantation.BY_ID[i] for i in self.spine)

    @property
    def element(self) -> str:
        return CLASS_ELEMENT.get(self.class_id, elements.NEUTRAL)

    @property
    def chapter(self) -> int:
        """The move opens when its hardest line does. The ladder still rules."""
        return max(i.chapter for i in self.incantations)

    @property
    def cost(self) -> int:
        """Focus. Three lines cost three lines' worth; nothing is discounted for
        being area, because the discount would be the loophole."""
        return sum(i.cost for i in self.incantations)

    @property
    def requires(self) -> tuple:
        out = []
        for inc in self.incantations:
            for kind in inc.requires:
                if kind not in out:
                    out.append(kind)
        return tuple(out)

    @property
    def skills(self) -> tuple:
        return tuple(dict.fromkeys(i.skill for i in self.incantations))

    @property
    def families(self) -> tuple:
        return tuple(dict.fromkeys(i.family for i in self.incantations))

    def shape_spec(self) -> Shape:
        return SHAPES[self.shape]

    def to_dict(self, *, reach: int = 0) -> dict:
        spec = self.shape_spec()
        return {
            "id": self.id, "name": self.name, "class": self.class_id,
            "rung": self.rung, "shape": self.shape, "shape_label": spec.label,
            "spine": list(self.spine),
            "lines": [{"incantation": i.id, "name": i.name, "note": i.note,
                       "skill": i.skill, "family": i.family,
                       "template": incantation.client_template(i.template)}
                      for i in self.incantations],
            "note": self.note, "flavour": self.flavour,
            "element": self.element, "chapter": self.chapter, "cost": self.cost,
            "requires": list(self.requires), "skills": list(self.skills),
            "max_targets": spec.max_targets, "min_targets": spec.min_targets,
            "fade": fade(self.rung, reach),
            "fade_curve": fade_table(self.rung),
        }


def _move(ident, name, class_id, rung, shape, spine, note, flavour) -> Move:
    if shape not in SHAPES:
        raise ValueError("%s: unknown shape %r" % (ident, shape))
    wanted = SHAPES[shape].spine
    if len(spine) != wanted:
        raise ValueError("%s: %s wants %d lines, got %d"
                         % (ident, shape, wanted, len(spine)))
    for inc_id in spine:
        if inc_id not in incantation.BY_ID:
            raise ValueError("%s: no such incantation %r" % (ident, inc_id))
    return Move(id=ident, name=name, class_id=class_id, rung=int(rung),
                shape=shape, spine=tuple(spine), note=note, flavour=flavour)


# -- I. The Analyst: LIGHTNING. Says what it believes, then proves it. -------
_ANALYST = (
    _move("measured_strike", "MEASURED STRIKE", "analyst", 1, SINGLE,
          ("measure",),
          "Count it before you hit it. Length before loop, always.",
          "The Analyst's opening move is arithmetic performed out loud."),
    _move("stated_case", "STATED CASE", "analyst", 2, SINGLE,
          ("ask",),
          "Ask with a default and nothing you ask can raise.",
          "A claim with its failure case already written into it."),
    _move("split_verdict", "SPLIT VERDICT", "analyst", 3, CLEAVE,
          ("guard", "ask"),
          "Two claims in one breath: what is new, and what it was worth.",
          "One argument that happens to cut two ways."),
    _move("order_of_magnitude", "ORDER OF MAGNITUDE", "analyst", 4, SINGLE,
          ("weigh",),
          "Order by a measure you can name. If you cannot name it, do not sort.",
          "Nothing is sorted here. Things are put in the order they were always in."),
    _move("complement_proof", "COMPLEMENT PROOF", "analyst", 5, CLEAVE,
          ("complement", "indexbook"),
          "Ask what is missing, then say where you last saw it.",
          "Two-sum, delivered as a verdict."),
    _move("standing_hypothesis", "THE STANDING HYPOTHESIS", "analyst", 6, CHAIN,
          ("consult", "enshrine"),
          "Check the archive before you pay, and file what the payment bought.",
          "The Analyst stops guessing and starts keeping receipts."),
    _move("falsified_map", "THE FALSIFIED MAP", "analyst", 7, STORM,
          ("witness", "bounds", "choose"),
          "Assert it, bound it, decide it. Everything standing hears all three.",
          "Every wrong answer you ever gave, filed, and now aimed."),
)

# -- II. The Berserker: BRUTE. Types first, converges loudly. ----------------
_BERSERKER = (
    _move("first_draft", "FIRST DRAFT", "berserker", 1, SINGLE,
          ("advance",),
          "Move the index. A loop that does not advance is a hang, not a bug.",
          "It is not elegant. It is already running."),
    _move("gut_swing", "GUT SWING", "berserker", 2, SINGLE,
          ("toll",),
          "One element joins the total. Then the next one.",
          "The accumulator step, thrown rather than placed."),
    _move("double_tap", "DOUBLE TAP", "berserker", 3, CLEAVE,
          ("advance", "toll"),
          "Take, then step. The two halves of every scan there has ever been.",
          "Twice, because once was never the Berserker's problem."),
    _move("running_tally", "RUNNING TALLY", "berserker", 4, CLEAVE,
          ("tally", "gather"),
          "Count it and keep it, in the same turn, at the same speed.",
          "Bookkeeping at a dead sprint."),
    _move("wide_arc", "WIDE ARC", "berserker", 5, STORM,
          ("march", "greatest", "toll"),
          "Walk every index, keep the best, take the toll. Everything is in range.",
          "Three lines, no plan, and the room is empty afterwards."),
    _move("breath_and_blow", "BREATH AND BLOW", "berserker", 6, CHAIN,
          ("inhale", "exhale"),
          "What the window takes on, the window must give back.",
          "In, out, and something falls over each time."),
    _move("last_draft", "THE LAST DRAFT", "berserker", 7, STORM,
          ("numbering", "transition", "choose"),
          "Number it, build on yesterday, take the better branch. All of it, now.",
          "The first draft, forty drafts later. Still typed at the same speed."),
)

# -- III. The Archivist: VOID. Remembers, and makes you pay once. ------------
_ARCHIVIST = (
    _move("first_sighting", "FIRST SIGHTING", "archivist", 1, SINGLE,
          ("mark",),
          "Record that you were here. Everything that de-duplicates starts here.",
          "The Archivist's entire method, in one method call."),
    _move("open_ledger", "OPEN LEDGER", "archivist", 2, SINGLE,
          ("ledger",),
          "Open the book before you need it. Empty braces are a dict, not a set.",
          "A blank page, which in this discipline is a weapon."),
    _move("filed_twice", "FILED TWICE", "archivist", 3, CLEAVE,
          ("inscribe", "mark"),
          "Write the entry, then note that you wrote it.",
          "Two records of one fact, which is one record more than most people keep."),
    _move("the_index", "THE INDEX", "archivist", 4, CHAIN,
          ("indexbook", "ask"),
          "Remember WHERE you saw it, then ask the book where that was.",
          "It jumps from name to name, and it has met all of them before."),
    _move("roll_call", "ROLL CALL", "archivist", 5, STORM,
          ("rollcall", "purge", "countdown"),
          "Read the names, strike the spent ones, decrement the rest.",
          "Every name in the ledger, read aloud, in order, to the room."),
    _move("paid_once", "PAID ONCE", "archivist", 6, CHAIN,
          ("consult", "enshrine"),
          "Ask the archive first. Pay only for what it has never heard of.",
          "Memoisation, which is the Archivist's argument with the universe."),
    _move("closed_archive", "THE CLOSED ARCHIVE", "archivist", 7, STORM,
          ("enshrine", "consult", "choose"),
          "File it, check it, decide it. Nothing in the room is asked twice.",
          "The book closes. Everything it remembered goes out at once."),
)

# -- IV. The Warden: COLD. Draws the perimeter before anything crosses it. ---
_WARDEN = (
    _move("first_ward", "FIRST WARD", "warden", 1, SINGLE,
          ("guard",),
          "The first-sighting test. Ask before you act.",
          "A line drawn on the floor, which is all a ward has ever been."),
    _move("probing_ward", "PROBING WARD", "warden", 2, SINGLE,
          ("probe",),
          "Ask whether it is in there. In a set the question is free.",
          "The Warden does not guess what is behind the door."),
    _move("double_perimeter", "DOUBLE PERIMETER", "warden", 3, CLEAVE,
          ("guard", "release"),
          "Refuse what is known, let go of what is spent.",
          "Two walls, because one wall is a suggestion."),
    _move("closing_vice", "CLOSING VICE", "warden", 4, CLEAVE,
          ("converge", "swap"),
          "Two pointers walking in. They have to be able to meet.",
          "The room gets smaller. Nothing about that is metaphorical."),
    _move("bisection", "BISECTION", "warden", 5, CHAIN,
          ("halve", "narrow"),
          "Halve it, then move PAST the midpoint. To it, and this never ends.",
          "Each jump lands on half of what the last one left."),
    _move("empty_case", "THE EMPTY CASE", "warden", 6, STORM,
          ("sentinel", "floor", "guard"),
          "Empty, base, guarded. The three cases you will be handed.",
          "The Warden's capstone argument: most things break on nothing at all."),
    _move("walled_plane", "THE WALLED PLANE", "warden", 7, STORM,
          ("bounds", "cell", "sentinel"),
          "Check the edge, read the cell, handle the void. Everything, everywhere.",
          "The perimeter closes on the whole plane at once."),
)

# -- V. The Artificer: FIRE. Builds the tool, then uses it. ------------------
# The Artificer's moveset is deliberately the most comprehension-heavy in the
# game, which under this damage model means it has the highest ceiling and the
# most demanding floor. That is the class fantasy stated in arithmetic: the
# Artificer is the build that rewards writing better Python most directly.
_ARTIFICER = (
    _move("bind_it", "BIND", "artificer", 1, SINGLE,
          ("bind",),
          "Name the result. Naming a result is the whole of programming.",
          "Before the tool, the handle."),
    _move("stock", "STOCK", "artificer", 2, SINGLE,
          ("gather",),
          "Build the answer as you go. Do not assemble it at the end.",
          "Raw material, acquired at speed."),
    _move("the_mirror", "THE MIRROR", "artificer", 3, SINGLE,
          ("mirror",),
          "Transform every element. A comprehension, not a loop with an append.",
          "One line that does what four lines were doing."),
    _move("the_sieve", "THE SIEVE", "artificer", 4, CLEAVE,
          ("sift", "distill"),
          "Keep what passes, then keep it only once.",
          "Two filters, and what comes through is smaller and truer."),
    _move("the_loom", "THE LOOM", "artificer", 5, CLEAVE,
          ("weave", "unravel"),
          "Join, and split. Never build a string with += in a loop.",
          "The tool that makes and the tool that unmakes, swung together."),
    _move("running_works", "RUNNING WORKS", "artificer", 6, CHAIN,
          ("prefix", "sift"),
          "Fold each element into the running total, then filter the results.",
          "A machine with two moving parts, which is one more than most."),
    _move("whole_tool", "THE WHOLE TOOL", "artificer", 7, STORM,
          ("table", "transition", "mirror"),
          "Size the ledger, pay each entry from the last, and map the lot.",
          "Everything the Artificer has ever built, running at once."),
)

# -- VI. The Seer: POISON. Reads the structure, and it spreads. --------------
_SEER = (
    _move("glance", "GLANCE", "seer", 1, SINGLE,
          ("reach",),
          "Read one position. Mind the last valid index.",
          "It looks at the thing. That turns out to be enough."),
    _move("cross_section", "CROSS SECTION", "seer", 2, SINGLE,
          ("sever",),
          "Cut a piece out. The stop index is never included.",
          "A clean slice through something that did not know it was layered."),
    _move("two_readings", "TWO READINGS", "seer", 3, CLEAVE,
          ("reach", "draw"),
          "Look at it, then take it off the top.",
          "Read twice, because the first reading is always of what you expected."),
    _move("paired_sight", "PAIRED SIGHT", "seer", 4, CLEAVE,
          ("pairing", "numbering"),
          "Two sequences in step, and the index of each. zip stops at the shorter.",
          "It sees both lists, at the same time, which nobody enjoys."),
    _move("front_and_top", "FRONT AND TOP", "seer", 5, CHAIN,
          ("dequeue", "peek"),
          "Take from the front, look at the back. Breadth first, then a glance.",
          "It jumps the queue, and then the queue's queue."),
    _move("spreading_edge", "THE SPREADING EDGE", "seer", 6, STORM,
          ("expand", "enqueue", "mark"),
          "Neighbours, scheduled, and remembered. The whole frontier moves.",
          "One ring at a time, and never the same node twice."),
    _move("every_path", "EVERY PATH AT ONCE", "seer", 7, STORM,
          ("unfold", "descend", "expand"),
          "Both branches, the sum of them, and every neighbour underneath.",
          "The Seer stops walking the graph and simply reads it."),
)

CATALOGUE: tuple = _ANALYST + _BERSERKER + _ARCHIVIST + _WARDEN + _ARTIFICER + _SEER
BY_ID: dict = {m.id: m for m in CATALOGUE}
BY_CLASS: dict = {}
for _move_row in CATALOGUE:
    BY_CLASS.setdefault(_move_row.class_id, []).append(_move_row)
for _rows in BY_CLASS.values():
    _rows.sort(key=lambda m: m.rung)
CLASS_IDS: tuple = tuple(BY_CLASS)


def get(move_id: str) -> Move | None:
    return BY_ID.get(move_id)


def for_class(class_id: str) -> list:
    return list(BY_CLASS.get(class_id, ()))


def at_rung(class_id: str, rung: int) -> Move | None:
    for move in BY_CLASS.get(class_id, ()):
        if move.rung == int(rung):
            return move
    return None


# ---------------------------------------------------------------------------
# The movebook
# ---------------------------------------------------------------------------
# Flat, JSON-safe, small enough to sit in the save blob beside `moveset`.
#
# Learning a move TEACHES ITS LINES. The skill tree is how you acquire a move;
# the move is how you acquire the incantations it is spelled out of. One
# acquisition path, not two, and it means a class's tree quietly decides which
# idioms that playthrough is fluent in — which is the replay value the brief
# asked for, arrived at without a single extra system.


def new_book(class_id: str = "") -> dict:
    return {"class": class_id, "known": [], "equipped": [], "casts": {},
            "landed": [], "last": "", "volleys": 0}


# There is deliberately NO slot limit on the movebook. `incantation` already
# rations the underlying lines — four slots at level one, eight at the ceiling —
# and rationing the same thing twice would mean a player who learned a move in
# the skill tree could still be told they may not cast it. A move you paid a
# skill point for is a move you own. What limits you in a fight is focus, and
# whether the field in front of you has enough monsters standing to answer the
# shape.


def known(book: dict) -> list:
    return [BY_ID[m] for m in (book.get("known") or []) if m in BY_ID]


def equipped(book: dict) -> list:
    return [BY_ID[m] for m in (book.get("equipped") or []) if m in BY_ID]


def is_known(book: dict, move_id: str) -> bool:
    return move_id in (book.get("known") or [])


def reach_of(book: dict) -> int:
    """The highest rung this player has been granted. Drives the fade curve."""
    return max([m.rung for m in known(book)] or [0])


def learn(book: dict, move_id: str, moveset: dict | None = None) -> dict:
    """Add a move, and teach every incantation it is made of.

    Returns what is news, so the caller has something to show. Learning is
    idempotent: re-granting a move the player already has is silent and safe,
    which matters because a tree can be respecced into the same shape twice.
    """
    move = BY_ID.get(move_id)
    if move is None:
        return {"move": move_id, "learned": False, "incantations": []}
    if is_known(book, move_id):
        return {"move": move_id, "learned": False, "incantations": [],
                "already": True}
    book.setdefault("known", []).append(move_id)
    book.setdefault("equipped", []).append(move_id)
    taught = []
    if moveset is not None:
        for inc_id in move.spine:
            if incantation.learn(moveset, inc_id):
                taught.append(inc_id)
    return {
        "move": move.id, "name": move.name, "learned": True,
        "rung": move.rung, "shape": move.shape,
        "incantations": taught,
        "line": "%s. %s" % (move.name, move.note),
    }


def record(book: dict, result: "VolleyResult") -> dict:
    """Fold a resolved volley into the evidence groove and variety read from."""
    move_id = result.move
    if move_id not in BY_ID:
        return book
    book["volleys"] = int(book.get("volleys", 0)) + 1
    if result.landed:
        casts = book.setdefault("casts", {})
        casts[move_id] = int(casts.get(move_id, 0)) + 1
        landed = book.setdefault("landed", [])
        if move_id not in landed:
            landed.append(move_id)
    # `last` moves whether or not the volley landed. Variety is about what you
    # reached for, not about whether it worked: a player who tries something new
    # and misses has still interleaved, and interleaving is the thing being paid.
    book["last"] = move_id
    return book


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------
# Adjacency is ROSTER ORDER, because roster order is the order the stage draws
# them in. A player aiming at the thing beside the thing they clicked should hit
# the sprite that is literally beside it; any cleverer definition of "adjacent"
# is a definition the player cannot see.


def targets_for(move: Move | str, context, *, primary: str = "") -> list:
    """The enemies this move will reach, in the order it reaches them."""
    move = BY_ID[move] if isinstance(move, str) else move
    spec = move.shape_spec()
    living = context.living()
    if not living:
        return []
    names = [e.name for e in living]
    start = names.index(primary) if primary in names else 0
    wanted = spec.targets_wanted(len(names))
    return [names[(start + offset) % len(names)] for offset in range(wanted)]


def castable(move: Move | str, context, *, chapter: int = 99) -> tuple:
    """(ok, why). A move that cannot land is refused BEFORE the turn is spent.

    A refusal costs nothing — no focus, no turn, no combo. Demanding a STORM of
    a player facing one monster is not difficulty, it is a trick, and this game
    does not charge for trick questions.
    """
    move = BY_ID[move] if isinstance(move, str) else move
    living = context.living()
    if not living:
        return False, "Nothing is standing."
    if move.chapter > int(chapter):
        return False, "%s is past what you have been taught." % move.name
    spec = move.shape_spec()
    if len(living) < spec.min_targets:
        return False, ("%s needs %d monsters standing and there %s %d."
                       % (move.name, spec.min_targets,
                          "is" if len(living) == 1 else "are", len(living)))
    for inc in move.incantations:
        if not incantation.castable(inc, context):
            return False, ("%s needs %s, and nothing here answers to it."
                           % (move.name, inc.name))
    return True, ""


def plan_move(move: Move | str, context, *, primary: str = "", book: dict | None = None,
              moveset: dict | None = None, skills: dict | None = None,
              chapter: int = 99, sealed: bool = False) -> dict:
    """Everything the client needs to render one move before a key is pressed.

    Per spine step: which incantation, at which scaffold tier, rendered. Plus
    the targets, the focus price, and the multipliers — itemised, because the
    player is about to make a decision and hiding the arithmetic from them would
    make that decision a guess.
    """
    move = BY_ID[move] if isinstance(move, str) else move
    ok, why = castable(move, context, chapter=chapter)
    spec = move.shape_spec()
    targets = targets_for(move, context, primary=primary) if ok else []
    steps = []
    for index, inc in enumerate(move.incantations):
        tier = (incantation.tier_for_move(moveset, inc.id, skills)
                if moveset is not None else 1)
        rendered = incantation.render_template(inc, tier, context=context)
        steps.append({**rendered, "step": index, "incantation": inc.id,
                      "tier": tier, "skill": inc.skill})
    multipliers = scale_for(book or {}, move.id,
                            sealed=is_sealed(context, sealed=sealed))
    return {
        "move": move.to_dict(reach=reach_of(book or {})),
        "castable": ok, "refusal": why,
        "targets": targets,
        "shares": [round(spec.share(i), 3) for i in range(len(targets))],
        "steps": steps,
        "focus": move.cost,
        "multipliers": multipliers,
        "rule": ("Every line has to land. Miss one and you keep what the others "
                 "did; miss all of them and the turn is gone."),
    }


# ---------------------------------------------------------------------------
# Resolving a volley
# ---------------------------------------------------------------------------

@dataclass
class Strike:
    """One target taking one spine step's share. The atom the client animates."""
    step: int = 0
    incantation: str = ""
    target: str = ""
    base: int = 0             # what the typing earned for this target, pre-wheel
    dealt: int = 0            # what actually landed, after the caller's wheel
    share: float = 1.0
    primary: bool = False
    weakness: bool = False
    resisted: bool = False
    defeated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VolleyResult:
    """One move, resolved. The whole turn, in one object."""
    move: str = ""
    name: str = ""
    shape: str = SINGLE
    element: str = elements.NEUTRAL
    correct: bool = False         # every line landed
    partial: bool = False         # some did
    wasted: bool = False          # none did
    refused: bool = False         # it never started, and cost nothing
    refusal: str = ""
    landed: list = field(default_factory=list)    # incantation ids that landed
    missed: list = field(default_factory=list)
    steps: list = field(default_factory=list)     # CastResult dicts, in order
    strikes: list = field(default_factory=list)
    targets: list = field(default_factory=list)
    defeated: list = field(default_factory=list)
    payload: int = 0              # what the typing earned before distribution
    dealt: int = 0                # what the monsters actually lost
    focus: int = 0
    scale: float = 1.0
    sealed: bool = False          # measured run: no class bonus reached this
    multipliers: list = field(default_factory=list)
    score: int = 0                # mean complexity of the lines that landed
    demanded: int = 0             # summed complexity: what the move cost to cast
    skill_deltas: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)
    fx: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["strikes"] = [s if isinstance(s, dict) else s.to_dict()
                           for s in self.strikes]
        return data


def _default_deliver(context):
    def deliver(enemy_name: str, base: int, step: int) -> int:
        enemy = context.enemy(enemy_name)
        if enemy is None or not enemy.alive:
            return 0
        before = enemy.hp
        enemy.hp = max(0, enemy.hp - int(base))
        return before - enemy.hp
    return deliver


def resolve_move(move_id: str, answers: list, context, *,
                 book: dict | None = None, moveset: dict | None = None,
                 skills: dict | None = None, primary: str = "",
                 seconds: float = 0.0, streak: int = 0, timed: bool = False,
                 chapter: int = 99, deliver=None, sealed: bool = False) -> VolleyResult:
    """Cast one move: every line in its spine, in order, in one turn.

    ``answers`` is one entry per spine step — a hole dict, or the whole line as
    a string when the player is typing from memory. Short lists are legal and
    are treated as the player declining to write the rest, which lands what they
    did write and nothing else.

    ``deliver(enemy_name, base_damage, step) -> dealt`` is how damage actually
    reaches a monster. The default subtracts it directly, which is what a test
    or a headless run wants. gauntlet/engine.py passes its own, which runs the
    base through `elements.resolve_damage` — because between what the typing
    earned and what the monster loses sits the elemental wheel, and this module
    does not get an opinion about that.

    WHAT HAPPENS WHEN ONE DIES MID-CAST: the target list is RE-READ before every
    step. A line aimed at a corpse is re-pointed at whatever is still standing,
    and if nothing is, the remaining steps are cancelled and the volley closes
    as an overkill — landed, paid in full for what it landed, nothing withheld.
    Punishing a player for killing the room too fast would be absurd, and
    charging them a wasted turn for it would be worse.
    """
    move = BY_ID.get(move_id)
    if move is None:
        return VolleyResult(move=move_id, refused=True,
                            refusal="No such move is known.")
    ok, why = castable(move, context, chapter=chapter)
    if not ok:
        return VolleyResult(move=move.id, name=move.name, shape=move.shape,
                            element=move.element, refused=True, refusal=why)

    book = book if book is not None else new_book(move.class_id)
    deliver = deliver or _default_deliver(context)
    spec = move.shape_spec()
    shut = is_sealed(context, sealed=sealed)
    multipliers = scale_for(book, move.id, sealed=shut)
    scale = multipliers["total"]

    result = VolleyResult(move=move.id, name=move.name, shape=move.shape,
                          element=move.element, focus=move.cost,
                          scale=scale, multipliers=multipliers["rows"])
    answers = list(answers or [])
    scores, deltas = [], {}

    for index, inc in enumerate(move.incantations):
        if not context.living():
            result.lines.append("Nothing left standing. The rest of %s goes "
                                "unspoken." % move.name)
            break
        targets = targets_for(move, context, primary=primary)
        if not targets:
            break
        step_answers = answers[index] if index < len(answers) else {}
        tier = (incantation.tier_for_move(moveset, inc.id, skills)
                if moveset is not None else 1)
        cast = incantation.cast(
            inc.id, step_answers, context, tier=tier, seconds=seconds,
            streak=streak, timed=timed, apply=False, scale=scale,
            target=targets[0])
        result.steps.append(cast.to_dict())
        if not cast.correct:
            result.missed.append(inc.id)
            result.lines.append("%s: %s" % (inc.name, cast.teaching))
            for name, delta in (cast.skill_deltas or {}).items():
                deltas[name] = round(deltas.get(name, 0.0) + delta, 3)
            continue

        result.landed.append(inc.id)
        scores.append(int(cast.complexity_score))
        for name, delta in (cast.skill_deltas or {}).items():
            deltas[name] = round(deltas.get(name, 0.0) + delta, 3)
        result.payload += int(cast.damage)

        # Distribute this step's earnings across the field as it stands NOW.
        for position, enemy_name in enumerate(targets):
            enemy = context.enemy(enemy_name)
            if enemy is None or not enemy.alive:
                continue
            share = spec.share(position)
            base = max(1, int(round(cast.damage * share)))
            dealt = int(deliver(enemy_name, base, index))
            strike = Strike(
                step=index, incantation=inc.id, target=enemy_name, base=base,
                dealt=dealt, share=round(share, 3), primary=(position == 0),
                weakness=bool(cast.weakness and position == 0),
                resisted=bool(cast.resisted and position == 0),
                defeated=not enemy.alive)
            result.strikes.append(strike.to_dict())
            result.dealt += dealt
            if not enemy.alive and enemy_name not in result.defeated:
                result.defeated.append(enemy_name)
            if enemy_name not in result.targets:
                result.targets.append(enemy_name)

    result.correct = bool(result.landed) and not result.missed
    result.partial = bool(result.landed) and bool(result.missed)
    result.wasted = not result.landed
    result.score = int(round(sum(scores) / len(scores))) if scores else 0
    result.demanded = min(100, sum(scores))
    result.skill_deltas = deltas
    # The fade the EFFECT is drawn at follows the same seal. A rung-one move in
    # an exam must not look like a rung-one move at reach seven, because the
    # exam is not reading the tree and the picture may not imply that it is.
    result.fx = fx_for(move, result, reach=(move.rung if shut else reach_of(book)))
    result.sealed = shut
    if result.correct:
        result.lines.insert(0, "%s lands in full." % move.name)
    elif result.partial:
        result.lines.insert(0, "%s lands in part: %d of %d lines."
                            % (move.name, len(result.landed),
                               len(result.landed) + len(result.missed)))
    else:
        result.lines.insert(0, "%s does not land. The turn is gone." % move.name)
    return result


# ---------------------------------------------------------------------------
# What the monsters do back
# ---------------------------------------------------------------------------
# Monsters and bosses swing wide too, and the brief is specific about where that
# lands: on the player, and on whatever is standing behind them.
#
# THIS MODULE DOES NOT COMPUTE WHAT A COMPANION LOSES. `gauntlet/pets.py` owns
# that, deliberately and exclusively: `pets.splash_damage` takes the blow in the
# PLAYER's health units and converts it, so there is exactly one damage formula
# in the game and the companion scales with it forever. A second formula here
# would be a second thing to keep in step with `elements.resolve_damage`, and it
# would drift inside a month. What this function does is name the SHAPE of the
# monster's swing, which is this module's job, and then hand over.

def enemy_area(base: int, *, shape: str = STORM, boss: bool = False) -> dict:
    """One monster area attack, described. Pure; applying it is the caller's job.

    The player takes the blow in full — an area attack is not diluted by how
    many things are standing near it, because there is only ever one of them
    that matters. The companion is reached by the same blow, and how much of it
    the animal actually feels is `pets.take_aoe`'s arithmetic and nobody else's.
    """
    spec = SHAPES.get(shape, SHAPES[STORM])
    base = max(0, int(base))
    return {
        "shape": spec.id,
        "player": base,
        "reaches_pet": base > 0,
        "boss": bool(boss),
        # The exact downstream call, named, so the engine has nothing to guess.
        "call": ("pets.take_aoe(state['pets'], damage=<what the player actually "
                 "lost>, max_health=player['stamina_max'], element=<attacker>, "
                 "source='BOSS' if boss else 'MONSTER')"),
        "line": ("It comes down across the whole floor." if spec.id == STORM
                 else "It swings wide."),
        "fx": {
            "law": fx_law(elements.NEUTRAL),
            "impactWhere": "field",
            "sweep": SHAPE_FX[spec.id]["sweep"],
            "rings": SHAPE_FX[spec.id]["rings"],
            "shake": 12.0 if boss else 7.0,
            "flash": 0.55 if boss else 0.35,
        },
    }


# ---------------------------------------------------------------------------
# The graphics contract
# ---------------------------------------------------------------------------
# web/js/spellfx.js and web/js/battlescene.js are drawn by another pass, and it
# will not guess. Everything below is the complete specification of what a move
# looks like, keyed in the vocabulary spellfx already speaks (see its
# `defineEffect` spec object and its per-effect contract comment).
#
# Three things escalate, and they escalate for three DIFFERENT reasons, which is
# why they are three separate numbers rather than one "level":
#
#   RUNG      what the skill tree granted. Sets the silhouette: how big the
#             figure is, how many motes, how long the hold frame runs.
#   FADE      how out of date the move is. Dims and shrinks it. A rung-one move
#             at reach seven must LOOK like thirty per cent, or the curve is a
#             secret and a secret mechanic is a bug report.
#   COMPLEXITY what the player just wrote. Drives `power`, which spellfx already
#             defines as "1 is a plain blow, ~1.5 a crit". This is the number the
#             player is meant to learn to move, so it is the number with the
#             loudest tell: the screen shake and the white flash both ride it.

RUNG_FX = {
    1: {"scale": 0.75, "motes": 28, "shake": 2.0, "flash": 0.22, "hold": 0.030,
        "debris": 4, "wash": 0.05, "duration": 0.55, "impactAt": 0.38},
    2: {"scale": 0.90, "motes": 40, "shake": 3.0, "flash": 0.28, "hold": 0.040,
        "debris": 6, "wash": 0.08, "duration": 0.60, "impactAt": 0.38},
    3: {"scale": 1.05, "motes": 56, "shake": 4.5, "flash": 0.34, "hold": 0.055,
        "debris": 9, "wash": 0.12, "duration": 0.70, "impactAt": 0.40},
    4: {"scale": 1.20, "motes": 76, "shake": 6.0, "flash": 0.42, "hold": 0.070,
        "debris": 12, "wash": 0.16, "duration": 0.80, "impactAt": 0.42},
    5: {"scale": 1.40, "motes": 100, "shake": 8.0, "flash": 0.50, "hold": 0.090,
        "debris": 16, "wash": 0.20, "duration": 0.95, "impactAt": 0.44},
    6: {"scale": 1.62, "motes": 132, "shake": 10.5, "flash": 0.58, "hold": 0.110,
        "debris": 22, "wash": 0.26, "duration": 1.10, "impactAt": 0.45},
    7: {"scale": 1.90, "motes": 180, "shake": 14.0, "flash": 0.70, "hold": 0.140,
        "debris": 30, "wash": 0.34, "duration": 1.35, "impactAt": 0.46},
}

# Per shape: how the effect is staged across the field. `sweep` is the delay
# between consecutive targets being struck, as a fraction of the effect's own
# duration, so a STORM reads as one wave crossing the room rather than four
# simultaneous copies of the same animation.
SHAPE_FX = {
    SINGLE: {"sweep": 0.00, "rings": 0, "arc": False, "groupShake": 1.00,
             "impactWhere": "target"},
    CLEAVE: {"sweep": 0.10, "rings": 1, "arc": True, "groupShake": 1.15,
             "impactWhere": "target"},
    CHAIN: {"sweep": 0.18, "rings": 0, "arc": True, "groupShake": 1.10,
            "impactWhere": "target"},
    STORM: {"sweep": 0.08, "rings": 2, "arc": False, "groupShake": 1.40,
            "impactWhere": "field"},
}

FADE_ALPHA_FLOOR = 0.55       # a faded move is dimmer, never invisible
FADE_SCALE_FLOOR = 0.55       # and smaller, never a dot
POWER_MIN = 0.70              # spellfx `power` at the bottom of the curve
POWER_MAX = 2.20              # and at the top


def power_from(score: int) -> float:
    """Complexity score -> spellfx `power`. 1.0 is the plain blow it defines."""
    k = max(0.0, min(100.0, float(score))) / 100.0
    return round(POWER_MIN + (POWER_MAX - POWER_MIN) * k, 3)


def fx_law(element: str) -> str:
    """The spellfx motion law, already resolved past anything unimplemented."""
    law = FX_LAW.get(element, "force")
    return FX_LAW_FALLBACK.get(law, law)


def fx_for(move: Move | str, result: "VolleyResult | None" = None, *,
           reach: int = 0, score: int | None = None,
           targets: list | None = None, reduced_motion: bool = False) -> dict:
    """The complete per-cast drawing order. One dict; nothing else is needed.

    Callable without a result, so a client can preview a move in the movebook
    at the strength it would currently be cast at.
    """
    move = BY_ID[move] if isinstance(move, str) else move
    rung = RUNG_FX[max(1, min(MAX_RUNG, move.rung))]
    shape = SHAPE_FX[move.shape]
    faded = fade(move.rung, reach)
    if score is None:
        score = result.score if result is not None else 40
    if targets is None:
        targets = list(result.targets) if result is not None else []
    power = power_from(score)
    dim = FADE_ALPHA_FLOOR + (1.0 - FADE_ALPHA_FLOOR) * faded
    shrink = FADE_SCALE_FLOOR + (1.0 - FADE_SCALE_FLOOR) * faded
    element = move.element
    law = fx_law(element)
    strikes = list(result.strikes) if result is not None else []
    return {
        # -- identity -----------------------------------------------------
        "id": "move_%s" % move.id,
        "family": "moveset",
        "label": move.name,
        "move": move.id,
        "class": move.class_id,
        "rung": move.rung,
        "shape": move.shape,
        # -- spellfx.createEffect(kind, opts) ------------------------------
        "law": law,                       # e.element: the motion law to use
        "law_requested": FX_LAW.get(element, "force"),
        "element": element,               # the game's element, for the label
        "colour": dict(FX_COLOUR.get(element, FX_COLOUR[elements.NEUTRAL])),
        "power": power,                   # e.power — the complexity tell
        "scale": round(rung["scale"] * shrink, 3),
        "alpha": round(dim, 3),
        "motes": int(round(rung["motes"] * shrink * power)),
        "debris": int(round(rung["debris"] * faded)),
        "duration": round(rung["duration"] * (0.45 if reduced_motion else 1.0), 3),
        "impactAt": rung["impactAt"],
        "hold": round(rung["hold"] * power * faded, 4),
        # -- advisory, per spellfx's own shakeHint/flashHint contract -------
        "shake": round(rung["shake"] * power * faded * shape["groupShake"], 3),
        "flash": round(min(1.0, rung["flash"] * power * faded), 3),
        "wash": round(rung["wash"] * faded, 3),
        "impactWhere": shape["impactWhere"],
        # -- battlescene.js: how many things get painted, and when ----------
        "targets": list(targets),
        "target_count": len(targets),
        "sweep": shape["sweep"],
        "rings": shape["rings"],
        "arc": shape["arc"],
        "lanes": lanes_for(len(targets)),
        "strikes": [{"step": s["step"], "target": s["target"],
                     "share": s["share"], "primary": s["primary"],
                     "damage": s["dealt"],
                     "kind": ("crit" if s["weakness"] else
                              "resist" if s["resisted"] else "hit")}
                    for s in strikes],
        # -- the tells, said in words for whoever draws them ---------------
        "fade": faded,
        "fade_tell": ("full strength" if faded >= 0.99 else
                      "dimmed to %d%% — this move has been outgrown"
                      % int(round(faded * 100))),
        "power_tell": "complexity %d of 100" % int(score),
    }


# battlescene.js publishes one enemyX. A fight with four monsters needs four,
# and it needs them to be the same four every frame or the sweep lands on the
# wrong sprite. Lanes are laid out from the existing SCENE_STAGE numbers:
# heroX 46, enemyX 136, stage width 192. The centre of the group stays at 136
# whatever the count, so a one-monster fight is pixel-identical to what ships
# today and nothing already drawn has to move.
LANE_CENTRE = 136
LANE_SPREAD = 21              # logical units between lanes
LANE_MIN = 108                # never overlap the hero's half of the stage
LANE_MAX = 182                # never leave the stage


def lanes_for(count: int) -> list:
    """Where `count` monsters stand, in battlescene logical units."""
    count = max(0, int(count))
    if count <= 0:
        return []
    if count == 1:
        return [{"index": 0, "x": LANE_CENTRE, "depth": 0.0, "scale": 1.0}]
    span = LANE_SPREAD * (count - 1)
    start = LANE_CENTRE - span / 2.0
    out = []
    for index in range(count):
        x = max(LANE_MIN, min(LANE_MAX, start + LANE_SPREAD * index))
        # Back rank sits a little further away, so four sprites in a row read as
        # a group with depth rather than as a wallpaper pattern.
        depth = 0.0 if index % 2 == 0 else 0.35
        out.append({"index": index, "x": round(x, 1), "depth": depth,
                    "scale": round(1.0 - 0.08 * depth, 3)})
    return out


def fx_table(*, reduced_motion: bool = False) -> list:
    """Every move, at its own rung, fully specified. The drawing pass's brief.

    Forty-two rows, each one a complete `createEffect` argument set at a
    representative complexity, plus the rung and shape numbers the effect
    interpolates between. A pass building spellfx.js can read this instead of
    reading this module.
    """
    return [fx_for(move, reach=move.rung, score=50,
                   targets=["a", "b", "c", "d"][:max(1, SHAPES[move.shape].min_targets)],
                   reduced_motion=reduced_motion)
            for move in CATALOGUE]


def fx_bands() -> dict:
    """The two lookup tables the client interpolates, published as data.

    Sent once at load rather than per cast, so a client that wants to preview a
    move it has never seen can build the effect without asking the server.
    """
    return {
        "rungs": {str(rung): dict(spec) for rung, spec in RUNG_FX.items()},
        "shapes": {shape: dict(spec) for shape, spec in SHAPE_FX.items()},
        "laws": {element: fx_law(element) for element in FX_LAW},
        "laws_requested": dict(FX_LAW),
        "law_fallbacks": dict(FX_LAW_FALLBACK),
        "colours": {element: dict(ramp) for element, ramp in FX_COLOUR.items()},
        "power": {"min": POWER_MIN, "max": POWER_MAX,
                  "means": "spellfx e.power; 1.0 is one plain blow"},
        "fade": {"floor_alpha": FADE_ALPHA_FLOOR, "floor_scale": FADE_SCALE_FLOOR,
                 "curve": [fade(1, r) for r in range(1, MAX_RUNG + 1)]},
        "lanes": {"centre": LANE_CENTRE, "spread": LANE_SPREAD,
                  "min": LANE_MIN, "max": LANE_MAX,
                  "examples": {str(n): lanes_for(n) for n in range(1, 6)}},
    }


# ---------------------------------------------------------------------------
# Self check
# ---------------------------------------------------------------------------

def self_check() -> dict:
    """Counts, proofs and the balance table, with real numbers.

    Safe to call from a test or the command line. Everything it asserts is
    something that would be a design defect rather than a crash.
    """
    problems: list = []

    # -- shape ------------------------------------------------------------
    for class_id, moves in BY_CLASS.items():
        rungs = [m.rung for m in moves]
        if rungs != list(range(1, MAX_RUNG + 1)):
            problems.append("%s: rungs %s" % (class_id, rungs))
        chapters = [m.chapter for m in moves]
        if chapters != sorted(chapters):
            problems.append("%s: chapters go backwards up the tree: %s"
                            % (class_id, chapters))
        if len({m.shape for m in moves}) < 3:
            problems.append("%s: fewer than three shapes in seven moves" % class_id)
        if not any(m.shape == STORM for m in moves):
            problems.append("%s: no area move at all" % class_id)

    for move in CATALOGUE:
        if len(move.spine) != SHAPES[move.shape].spine:
            problems.append("%s: spine length disagrees with its shape" % move.id)
        if move.class_id not in CLASS_ELEMENT:
            problems.append("%s: class %r has no element" % (move.id, move.class_id))

    # -- no new combat vocabulary ----------------------------------------
    stray = sorted({i for m in CATALOGUE for i in m.spine} - set(incantation.BY_ID))
    if stray:
        problems.append("incantations invented outside the catalogue: %s" % stray)

    # -- the price of area, measured -------------------------------------
    # For each shape, what one move delivers against N monsters, in units of
    # "one SINGLE cast", versus spending N turns casting SINGLE at each.
    price = []
    for shape_id in SHAPE_IDS:
        spec = SHAPES[shape_id]
        for living in (2, 3, 4):
            hit = spec.targets_wanted(living)
            if hit < spec.min_targets:
                continue
            delivered = spec.spine * sum(spec.share(i) for i in range(hit))
            singles = float(hit)
            price.append({
                "shape": shape_id, "monsters": living, "reached": hit,
                "lines_typed": spec.spine,
                "delivered": round(delivered, 3),
                "vs_singles": round(delivered / singles, 3),
                "turns_saved": hit - 1,
            })
            if delivered / singles > 1.60:
                problems.append("%s at %d monsters is strictly better than "
                                "playing properly (%.2f)"
                                % (shape_id, living, delivered / singles))

    # -- repetition against novelty, computed ----------------------------
    # Two players over twenty turns, same pool, same class. One drills a single
    # move; one alternates two. Both curves include the thing that actually
    # matters — the scaffold tier, which only repetition can raise, and which
    # feeds the complexity measure directly. Damage is in units of one weight.
    probe = incantation.BY_ID["tally"]
    by_tier = [incantation.measure_complexity(probe, dict(probe.example),
                                              tier=t).weight for t in range(4)]

    def _tier_after(casts: int) -> int:
        # incantation.tier_for, for a player with no misses: 2 correct casts
        # buy tier 1, five buy tier 2, nine buy tier 3.
        return 3 if casts >= 9 else 2 if casts >= 5 else 1 if casts >= 2 else 0

    turns = 20
    drill_total, alt_total, race = 0.0, 0.0, []
    counts = {"a": 0, "b": 0}
    for turn in range(1, turns + 1):
        drill_total += by_tier[_tier_after(turn - 1)] * groove(turn - 1)
        which = "a" if turn % 2 else "b"
        alt_total += (by_tier[_tier_after(counts[which])]
                      * groove(counts[which]) * (1.0 + VARIETY_BONUS))
        counts[which] += 1
        race.append({"turn": turn, "drill": round(drill_total, 3),
                     "alternate": round(alt_total, 3),
                     "gap": round(alt_total / drill_total - 1.0, 4)})
    divergence = max(abs(row["gap"]) for row in race)
    if divergence > 0.15:
        problems.append("one study strategy dominates the other by %.0f%%"
                        % (divergence * 100))

    # -- the fade curve ---------------------------------------------------
    curve = [{"gap": gap, "multiplier": fade(1, 1 + gap)}
             for gap in range(0, MAX_RUNG)]
    if curve[-1]["multiplier"] <= 0:
        problems.append("a move expired instead of fading")
    if curve[-1]["multiplier"] >= curve[0]["multiplier"]:
        problems.append("the fade curve does not fade")

    # -- complexity still outranks everything this module can do ----------
    # The worst move in the game, cast beautifully, against the best move cast
    # lazily. If the second one wins, this module has become the spine.
    typing_span = incantation.WEIGHT_MAX / incantation.WEIGHT_MIN
    module_span = ((1.0 / FADE_FLOOR) * (1.0 + GROOVE_GAIN)
                   * (1.0 + VARIETY_BONUS) * (1.0 + FRESH_BONUS))
    if module_span >= typing_span:
        problems.append("this module's multipliers (%.2fx) have overtaken the "
                        "typing (%.2fx): complexity is no longer the spine"
                        % (module_span, typing_span))
    worst = incantation.DAMAGE_UNIT * incantation.WEIGHT_MAX * FADE_FLOOR
    best_lazy = (incantation.DAMAGE_UNIT * incantation.WEIGHT_MIN
                 * (1.0 + GROOVE_GAIN) * (1.0 + VARIETY_BONUS)
                 * (1.0 + FRESH_BONUS))

    # -- the seal ---------------------------------------------------------
    # The most decorated book in the game, in an exam. Every row has to be gone
    # and the total has to be exactly one, in both directions: the drilled
    # capstone gets no bonus and the faded rung-one gets no penalty.
    loaded = new_book("analyst")
    for move in for_class("analyst"):
        learn(loaded, move.id)
    loaded["casts"] = {m.id: 40 for m in for_class("analyst")}
    loaded["last"] = "stated_case"
    decorated = scale_for(loaded, "falsified_map")["total"]
    faded = scale_for(loaded, "measured_strike")["total"]
    sealed_rows = scale_for(loaded, "falsified_map", sealed=True)
    seal = {
        "decorated_open": decorated,
        "faded_open": faded,
        "decorated_sealed": sealed_rows["total"],
        "faded_sealed": scale_for(loaded, "measured_strike", sealed=True)["total"],
        "interview_context_alone_is_enough": is_sealed(
            incantation.BattleContext(mode="interview")),
        "adventure_is_not_sealed": not is_sealed(
            incantation.BattleContext(mode="adventure")),
    }
    if sealed_rows["total"] != SEALED_SCALE:
        problems.append("a class bonus survived the seal: %.4f"
                        % sealed_rows["total"])
    if seal["faded_sealed"] != SEALED_SCALE:
        problems.append("a rank penalty survived the seal: %.4f"
                        % seal["faded_sealed"])
    if not seal["interview_context_alone_is_enough"]:
        problems.append("a timed practical context does not seal this module on its own")

    return {
        "moves": len(CATALOGUE),
        "classes": len(BY_CLASS),
        "per_class": {c: len(m) for c, m in BY_CLASS.items()},
        "shapes": {s: sum(1 for m in CATALOGUE if m.shape == s) for s in SHAPE_IDS},
        "incantations_used": len({i for m in CATALOGUE for i in m.spine}),
        "incantations_total": len(incantation.CATALOGUE),
        "area_price": price,
        "fade_curve": curve,
        "study_race": race,
        "study_divergence": round(divergence, 4),
        "typing_span": round(typing_span, 2),
        "module_span": round(module_span, 2),
        "oldest_move_written_well": round(worst, 2),
        "newest_move_written_badly": round(best_lazy, 2),
        "seal": seal,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# Integration contract
# ---------------------------------------------------------------------------
# Wiring this up is five calls and they all belong in gauntlet/engine.py:
#
#   1. state["movebook"] = movesets.new_book(state["class"]["class"]) beside the
#      existing state["moveset"]. Both persist; they are different books.
#   2. On spending a skill point: for move_id in classes.moves_for_node(node_id):
#      movesets.learn(state["movebook"], move_id, state["moveset"]). That is the
#      ONLY way a move is ever acquired.
#   3. On opening the move panel: movesets.plan_move(move_id, ctx,
#      book=state["movebook"], moveset=state["moveset"], skills=self.skills,
#      chapter=curriculum.frontier(self.skills), primary=<clicked enemy>,
#      sealed=finalexam.sealed(enc, "BUILD")).
#   4. On submit: movesets.resolve_move(move_id, [answers_per_line], ctx,
#      book=..., moveset=..., skills=..., primary=..., streak=combo,
#      deliver=self._incant_deliver, sealed=finalexam.sealed(enc, "BUILD")). `deliver` is `_incant_strike` with its
#      enemy-picking removed: it takes (enemy_name, base, step), runs the base
#      through elements.resolve_damage exactly as it does today, applies the
#      result, and returns hit.damage. Then movesets.record(book, result), and
#      incantation.record_cast(moveset, CastResult) per entry in result.steps.
#   5. On a monster's area turn: movesets.enemy_area(base, shape=..., boss=...)
#      names the swing, the player takes result["player"] through the wheel it
#      already goes through, and then pets.take_aoe(state["pets"], damage=<what
#      the player actually lost>, max_health=player["stamina_max"]) reaches the
#      companion. This module does not compute what the animal loses; pets.py
#      owns that formula and there is only one of it.
#   6. result.fx goes to the client untouched. web/js/spellfx.js reads `law`,
#      `colour`, `power`, `scale`, `alpha`, `motes`, `debris`, `duration`,
#      `impactAt`, `hold`, `shake`, `flash`, `wash`, `impactWhere`;
#      web/js/battlescene.js reads `lanes`, `targets`, `sweep`, `rings`, `arc`
#      and `strikes`. movesets.fx_bands() is sent once at load; movesets.fx_table()
#      is the whole forty-two-row brief for whoever writes the effects.
#
# Nothing here can win a fight without typing. `resolve_move` with an empty
# answers list lands nothing, deals nothing and returns wasted=True, which is
# the same thing a wrong cast has always done.
