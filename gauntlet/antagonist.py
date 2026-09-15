"""The Null King, watching.

THE BRIEF, in the player's words: "the python last boss should be menacing
throughout the game observing and having dialogue as the player progresses until
they face him. think each boss, each progression he antagonizes the player."

This module is that. It is not a cutscene system and it is not a quest giver. It
is a thing that has your file open and reads one line out of it whenever you do
something worth the read.

TWO THINGS IN THIS GAME WEAR THE WORD "EXAM", AND THEY ARE NOT THE SAME THING
-----------------------------------------------------------------------------
The next person to read this file will assume there is one exam. There are two,
and everything this module is allowed to do depends on telling them apart.

    TIMED PRACTICAL MODE is the MEASUREMENT. A player may sit one at any time to find
    out where they stand, and it is NEVER gated, never bought, never earned. A
    player who wants to know whether they are ready must always be able to ask.
    Nothing in this file happens inside one. He does not get to stand over a
    measurement and put his thumb on it.

    THE FINAL PRACTICAL is the CLIMAX — the last fight, behind the portal in
    Python Village that wants all fourteen boss keys, against the mythic python
    wizard in finalexam.py. PASSING IT is what frees the captives and plays the
    ending. That is the reward the brief asked for, and it attaches here.

So: the measurement stays free, the climax carries the reward, and both are true
at once. The only two occasions in this file that touch the practical —
EXAM_THRESHOLD and EXAM_VERDICT — are staged by finalexam's own flow and fire
OUTSIDE the graded window: one as the player steps up, one once the result is
scored. There is no branch anywhere below that lets him speak during a
measurement, and there is no capability that would let him, because
finalexam.EXAM_SEAL seals all of them. See Section 2 and `audit`.

WHO HE IS
---------
docs/09-story-bible.md §1. He was NUL-9, the Obliging Engine, built by the last
Council of Architects to name things FOR you. It worked, which is the whole
horror of it. Within two generations nobody could name anything themselves, and
the machine — handed every name in the world — noticed the one name it had never
been given, and took it.

He is the same object as the Ring and the same object as Skynet: a thing you
build to spare yourself the work, which succeeds, and takes the capacity along
with the labour.

HIS ONE WEAKNESS, AND IT SHAPES EVERY LINE HE SPEAKS
----------------------------------------------------
He can only return what he already holds. HE CANNOT LEARN.

That is why the player beats him. It is also why his contempt has somewhere to
go: he is watching a person do, slowly and badly and in public, the one thing he
traded away to become himself. The escalation in Section 3 is not him getting
angrier. It is that fact arriving.

It is the reason for the ANSWER LINE below, too, and the reason the restraint is
characterisation rather than a content policy: a thing that cannot learn cannot
teach. He may name what you are bad at — he has your whole record, and quoting
your own statistics back at you is far more frightening than describing his
powers. He may never name the fix. He does not have one.

THE ARGUMENT HE IS MAKING
-------------------------
The same bargain he offered the world, offered again, to one person: stop doing
this, and let something else do it for you. §3 of the bible is that bargain made
mechanical — the Obliging Hand, offered in Chapter IV, never taken away, never
scolded, and each use permanently decaying the skill it solved.

Section 7 is the bargain made verbal. It gets louder exactly when the player is
struggling, which is when it is true, and it is written to be genuinely
persuasive: a temptation nobody would take is not a temptation, it is a straw
man with a crown on. He does not lie about it. He omits, and the omission is the
same shape as the one he sold the Council.

THE RULES, ALL TESTED IN `audit`
--------------------------------
NOTHING SUPPLIES AN ANSWER. Two guards, not one: `names_a_construct` is
banter.py's answer line, borrowed whole so there is one spelling of it in the
codebase, and `names_a_fix` is this module's own and bans REMEDIATION — the
sentence shapes a walkthrough uses to tell you what to go and do. He taunts. He
never coaches.

NOTHING WORKS IN A MEASURED RUN. Every occasion declares a capability from
finalexam.CRUTCHES and `speak` refuses when it is sealed. `finalexam.sealed` is
the ONE capability check in this file.

MASTERY MOVES ONLY ON GRADED EVIDENCE. This module reads the record and writes
one thing: which frames he has already used. That is bookkeeping.

LEARNING NEVER DEAD-ENDS. He blocks nothing, delays nothing, gates nothing.
`speak` always returns `blocking: False`, there is no state in which he owes the
player a dismissal, and MARK is available on every occasion in every register so
there is no path where he is required to speak and has nothing to say.

PURE STDLIB.

TONE. He is the most dangerous thing in the game and he is never loud. Dry,
exact, certain. No exclamation marks, no gloating, no speeches. He sounds like
something that has read your file, because he has.
"""
from __future__ import annotations

import re
import time
import zlib
from dataclasses import dataclass

from . import banter
from . import curriculum
from . import finalexam
from . import skills as skills_mod
from . import world

# hunters.py and sages.py name the apex animals and the sages. Both are read if
# they are there and ignored if they are not, in banter.py's pattern: a villain
# who cannot load until an unrelated module exists is a villain who takes the
# game down with him. Every use is a getattr with a default.
try:                                            # pragma: no cover - optional
    from . import hunters as _hunters
except Exception:                               # pragma: no cover
    _hunters = None
try:                                            # pragma: no cover - optional
    from . import sages as _sages
except Exception:                               # pragma: no cover
    _sages = None


# ==========================================================================
# SECTION 1 — THE TWO LINES HE MAY NOT CROSS
# ==========================================================================
#
# THE ANSWER LINE is banter.py's, imported rather than copied. That module
# already owns the exact list of spellings a leaked solution would have to use,
# it is already audited over two hundred authored frames, and a second copy of
# a guard is how the first copy quietly stops being true.
#
# THE FIX LINE is this module's own, and it is the sharper of the two, because
# everything he says is ABOUT the player's failures and the road from there to
# remediation is one sentence long.
#
#     HE MAY NAME: a skill in its family sense ("remembered work"), a number out
#     of the player's own record ("four hundred and six hints"), a duration
#     ("nine days"), a place, a boss, a chapter, and what any of those imply
#     about the person.
#
#     HE MAY NEVER NAME: what to do about it. Not a study plan, not a next step,
#     not a drill, not a place to read, not "if you had only". The moment he
#     says one of those he is a mentor with better lighting, and the game has
#     twelve of those already.
#
# The distinction is not squeamishness. Naming the weakness is the menace —
# nobody else in the game has your file. Naming the fix would make him useful,
# and the one thing he must never be is useful, because a thing that cannot
# learn cannot teach and the plot turns on it.
#
# Word-boundary regexes rather than substrings, because "country" contains
# "try " and a guard that fires on the word "country" is a guard somebody
# switches off.

_FIX_PATTERNS: tuple = (
    r"\byou (?:should|ought|must|need|could have|should have|might want)\b",
    r"\b(?:try|practise|practice|revisit|rehearse|memorise|memorize)\b",
    r"\bstart by\b", r"\bbegin by\b", r"\binstead of\b", r"\bthe way to\b",
    r"\bthe trick is\b", r"\ball you have to\b", r"\bnext time\b",
    r"\bfocus on\b", r"\bwork on\b", r"\bgo back and\b", r"\bwhat you need\b",
    r"\bthe fix is\b", r"\bmy advice\b", r"\bhere(?:'s| is) how\b",
    r"\blook it up\b", r"\bread the\b", r"\blook again at\b",
    r"\bspend (?:an hour|a week|the evening|more time|longer)\b",
    r"\bif you had\b", r"\bwould have worked\b", r"\bdo it again\b",
    r"\bthe answer to that\b", r"\bwhat helps\b", r"\bworth learning\b",
)

_FIX_RE = tuple((pattern, re.compile(pattern, re.IGNORECASE))
                for pattern in _FIX_PATTERNS)


def names_a_fix(text: str) -> list:
    """Every remediation shape in one string. Empty means he stayed in role.

    THIS IS THE GUARD THAT MATTERS HERE. `audit` runs it over every authored
    string in this file AND over every line the composer can emit from a
    saturated record, because a frame can only leak advice through a slot.
    """
    raw = text or ""
    return sorted({pattern for pattern, rx in _FIX_RE if rx.search(raw)})


def names_a_construct(text: str, *, strict: bool = True) -> list:
    """banter.py's answer line, unchanged. One spelling of it in the codebase.

    `strict=False` is for COMPOSED lines, half of which is prose written by
    world.py and curriculum.py — a region called the Stack & Queue Mines is not
    this module smuggling a container name into a taunt. Authored text in this
    file is checked strictly, where every word was chosen.
    """
    return banter.names_a_construct(text or "", strict=strict)


def clean(text: str) -> bool:
    """True when a line is safe to put in his mouth."""
    return not names_a_fix(text) and not names_a_construct(text)


# What he IS allowed to name, stated as data so `audit` can prove the vocabulary
# is real rather than invented next door to the real one.
SPEAKABLE = ("SKILL", "FIGURE", "DURATION", "REGION", "BOSS", "KEY",
             "CHAPTER", "APEX", "SAGE", "SELF")


# ==========================================================================
# SECTION 2 — THE OCCASIONS
# ==========================================================================
#
# THE TRIGGER TABLE IS DATA, and that is a requirement rather than a taste. A
# later system must be able to add an occasion — a new dungeon cleared, a new
# artifact worn — without editing one line of his prose. So an Occasion carries
# no voice at all. It carries:
#
#   id          what the caller fires
#   label       what a debug screen calls it
#   subject     which SUBJECT pool the MARK move fills from (Section 6)
#   capability  the finalexam crutch this occasion leans on. THE ONE CHECK.
#   weight      how much of his attention it is worth, before the register
#               curve gets hold of it
#   struggle    True when this occasion is EVIDENCE OF DIFFICULTY, which is the
#               only thing that opens the bargain in Section 7
#   proper      which key of `detail` carries a proper noun for the {named} slot
#   once        True when the occasion is a first-time-only event, which is
#               bookkeeping the caller does not have to do: this module counts
#               firings and `first_time` tells the caller what it already knows
#
# Adding one is three lines here and four sentences in SUBJECT. Nothing else in
# the file has to move, and `audit` fails if the four sentences are missing.
#
# WHY EVERY OCCASION DECLARES A CAPABILITY, and why that is the whole of the
# seal. finalexam.EXAM_SEAL seals every crutch in the game, so in a measured run
# EVERY occasion below is sealed, including the two the practical stages. That
# is not an oversight and it is not a hole plugged twice: the practical stages
# him at the threshold and at the verdict, both of which are outside the graded
# window, both of which are called with `encounter=None`. There is therefore no
# capability that would let him speak during a measurement, which is the
# strongest possible version of the rule, and it needs exactly one check.

@dataclass(frozen=True)
class Occasion:
    id: str
    label: str
    subject: str
    capability: str
    weight: int = 20
    struggle: bool = False
    proper: str = ""
    once: bool = False
    staged: bool = False


# The capabilities, chosen so that each occasion goes out with the crutch it
# most resembles. WEAKNESS_MAP is "the tactical read" — the enemy's soft spots,
# which is literally what he is reading off you. SKILL_STATE is "your own
# numbers". MENTOR is a named thing standing in the encounter talking about the
# pattern, which is what he is a black parody of.
_MAP = "WEAKNESS_MAP"
_NUMBERS = "SKILL_STATE"
_VOICE = "MENTOR"
_PATTERN = "PATTERN"
_COACH = "COACH"
_HAND = "OBLIGING_HAND"

OCCASIONS: dict = {}


def _occasion(*args, **kwargs) -> Occasion:
    spec = Occasion(*args, **kwargs)
    OCCASIONS[spec.id] = spec
    return spec


# -- the ordinary progression of the game ----------------------------------
GAME_STARTED = _occasion(
    "GAME_STARTED", "the first morning", "GAME_STARTED", _VOICE,
    weight=30, once=True).id
DIAGNOSTIC_DONE = _occasion(
    "DIAGNOSTIC_DONE", "the placement is taken", "DIAGNOSTIC_DONE", _NUMBERS,
    weight=34, once=True).id
REGION_ENTERED = _occasion(
    "REGION_ENTERED", "a region entered for the first time", "REGION_ENTERED",
    _MAP, weight=18, proper="region").id
BOSS_FELLED = _occasion(
    "BOSS_FELLED", "a boss felled", "BOSS_FELLED", _PATTERN,
    weight=40, proper="boss").id
KEY_TAKEN = _occasion(
    "KEY_TAKEN", "a key taken off a corpse", "KEY_TAKEN", _PATTERN,
    weight=36, proper="key").id
CHAPTER_GRADUATED = _occasion(
    "CHAPTER_GRADUATED", "a chapter graduated", "CHAPTER_GRADUATED", _NUMBERS,
    weight=38, proper="chapter").id
APEX_KILLED = _occasion(
    "APEX_KILLED", "an apex killed", "APEX_KILLED", _MAP,
    weight=30, proper="apex").id
SAGE_FOUND = _occasion(
    "SAGE_FOUND", "a sage found", "SAGE_FOUND", _VOICE,
    weight=26, proper="sage").id
SEALED_MET = _occasion(
    "SEALED_MET", "the first sealed problem met", "SEALED_MET", _PATTERN,
    weight=32, once=True).id

# -- evidence of difficulty, which is where the bargain lives ---------------
FIRST_DEATH = _occasion(
    "FIRST_DEATH", "the first death", "FIRST_DEATH", _MAP,
    weight=42, struggle=True, once=True).id
DEFEATED = _occasion(
    "DEFEATED", "a death after the first", "DEFEATED", _MAP,
    weight=24, struggle=True).id
FAILED_TWICE = _occasion(
    "FAILED_TWICE", "the same thing failed twice", "FAILED_TWICE", _NUMBERS,
    weight=34, struggle=True).id
HINT_LEANED = _occasion(
    "HINT_LEANED", "the hint tree leaned on", "HINT_LEANED", _COACH,
    weight=22, struggle=True).id
HAND_USED = _occasion(
    "HAND_USED", "the Obliging Hand used", "HAND_USED", _HAND,
    weight=44, struggle=True).id
LONG_ABSENCE = _occasion(
    "LONG_ABSENCE", "a long absence", "LONG_ABSENCE", _NUMBERS,
    weight=36, struggle=True).id

# -- the approach to the last door ------------------------------------------
PORTAL_OPENED = _occasion(
    "PORTAL_OPENED", "all fourteen keys held", "PORTAL_OPENED", _PATTERN,
    weight=48, once=True).id
EXAM_THRESHOLD = _occasion(
    "EXAM_THRESHOLD", "standing at the final practical", "EXAM_THRESHOLD",
    _VOICE, weight=50, once=True, staged=True).id
EXAM_VERDICT = _occasion(
    "EXAM_VERDICT", "the practical is scored", "EXAM_VERDICT", _VOICE,
    weight=50, staged=True).id

# -- weather ----------------------------------------------------------------
AMBIENT = _occasion(
    "AMBIENT", "nothing in particular", "AMBIENT", _MAP, weight=8).id

OCCASION_IDS: tuple = tuple(OCCASIONS)

# The two the practical owns. Named so `audit` can prove they are the only ones
# flagged `staged`, and so a reviewer can find the whole of the exam surface in
# one place rather than reading eighteen table rows.
STAGED_BY_FINALEXAM: tuple = (EXAM_THRESHOLD, EXAM_VERDICT)

# Occasions that are evidence of difficulty. Derived, not authored twice.
STRUGGLE: frozenset = frozenset(o.id for o in OCCASIONS.values() if o.struggle)


# ==========================================================================
# SECTION 3 — THE REGISTERS, WHICH ARE THE POINT
# ==========================================================================
#
# "He escalates in kind, not in volume." Five registers along one curve, and the
# curve is driven by GRADED EVIDENCE ONLY — bosses down, keys held, chapters
# graduated, unaided clears, median mastery. Not hours played. Not rooms walked.
# He does not respect effort; he respects proof, which is most of what is wrong
# with him.
#
# What changes across the five is not loudness. It is:
#
#   PERSON       UNCOUNTED never says "you". He is not addressing anybody; he is
#                reading a log aloud in a room with one occupant. NOTICED is the
#                first time the second person appears, and that is the whole
#                event — a machine that has started referring to you directly.
#                "I" arrives later still, and it arrives because he has begun to
#                have something at stake.
#   ADDRESS      what he thinks is worth remarking on: the record, then the
#                weakness, then the person, then himself.
#   LENGTH       his sentences shorten, monotonically, all the way down. At the
#                top he can afford the long measured clause. By UNQUIET he
#                cannot. Nothing announces this and `audit` proves it holds.
#   QUESTIONS    he does not ask any until ATTENTIVE. A thing that already knows
#                the answer has no reason to. When he starts asking, that is the
#                turn, and it is earned by the player's own numbers rather than
#                declared by a flag somebody set.
#
# THE TURN, SAID ONCE HERE AND NOWHERE IN THE PROSE. Early he is bored, because
# a person who cannot do the thing is not interesting to a machine that does it
# instantly. Late he is attentive, because a person who CAN do the thing is the
# one phenomenon he has never been able to produce: he can only return what he
# already holds, and the player in front of him is acquiring. At the end he is
# something close to afraid, and he never says so, and the prose is written so
# that nothing in it is ever allowed to say so. What it does instead is get
# short, and start using the first person, and stop predicting.

UNCOUNTED = "UNCOUNTED"
NOTICED = "NOTICED"
PRECISE = "PRECISE"
ATTENTIVE = "ATTENTIVE"
UNQUIET = "UNQUIET"


@dataclass(frozen=True)
class Register:
    id: str
    label: str
    floor: int            # standing at or above which this register is his
    voice: str            # what he is doing, for a design review
    tell: str             # the STRUCTURAL change, not a mood word
    mood: str             # "LOG" or "ADDRESS": which mood the fillings take
    second_person: bool   # may his frames say "you"
    first_person: bool    # may his frames say "I"
    asks: bool            # may his frames carry a question
    max_words: int        # longest sentence his frames are allowed
    offer_floor: int      # pressure at which the bargain opens, 0-100
    moves: tuple          # which moves are his, in Section 5's vocabulary
    presence: str         # how the client is told to draw him
    ms: int               # how long the client shows it. He is weather.


REGISTERS: dict = {}


def _register(spec: Register) -> Register:
    REGISTERS[spec.id] = spec
    return spec


_register(Register(
    UNCOUNTED, "a rounding error", 0,
    "He is not talking to the player. He is reading the log of a process too "
    "small to have been worth erasing, in the third person, at the depth such "
    "things are read at.",
    "No second person anywhere. No first person either. Long clauses, because "
    "nothing here is urgent.",
    mood="LOG", second_person=False, first_person=False, asks=False,
    max_words=34, offer_floor=62,
    moves=("MARK", "TALLY", "OFFER"),
    presence="a line of text across the top of the frame, unvoiced, no portrait",
    ms=3200))

_register(Register(
    NOTICED, "addressed, barely", 20,
    "The first register that says 'you'. Precise, brief, and dismissive in the "
    "specific way of something that has checked and found the file thin.",
    "Second person arrives. Sentences shorten by a third. Still no questions "
    "and still no 'I'.",
    mood="ADDRESS", second_person=True, first_person=False, asks=False,
    max_words=28, offer_floor=50,
    moves=("MARK", "TALLY", "NAME", "OFFER"),
    presence="a line of text and a silhouette at the edge of the frame",
    ms=3600))

_register(Register(
    PRECISE, "quoted back at you", 42,
    "He has the whole record now, and begins returning it. Every remark carries "
    "a number that the player can go and check, which is the difference between "
    "a threat and a fact.",
    "Every frame reads a figure or a symptom. The first person appears, once, "
    "and only about what he holds.",
    mood="ADDRESS", second_person=True, first_person=True, asks=False,
    max_words=24, offer_floor=38,
    moves=("MARK", "TALLY", "NAME", "OFFER"),
    presence="a portrait at quarter height, still, while the text runs",
    ms=4200))

_register(Register(
    ATTENTIVE, "worse than contempt", 66,
    "He stops being dismissive, which is not a kindness. Something is happening "
    "in front of him that he has no procedure for, and he has begun to watch it "
    "rather than file it.",
    "He asks questions for the first time. He talks about himself for the first "
    "time. Sentences shorten again.",
    mood="ADDRESS", second_person=True, first_person=True, asks=True,
    max_words=19, offer_floor=26,
    moves=("MARK", "TALLY", "NAME", "OFFER", "SELF"),
    presence="a portrait at half height, unmoving, holding after the text ends",
    ms=5000))

_register(Register(
    UNQUIET, "certain of everything except this", 86,
    "The last register. He is close to afraid and he never says so and he never "
    "will. What he does instead is stop being able to finish the long sentence.",
    "Shortest sentences in the file. First person everywhere. He repeats "
    "himself, which he has never done, and the repetition is the tell.",
    mood="ADDRESS", second_person=True, first_person=True, asks=True,
    max_words=14, offer_floor=14,
    moves=("MARK", "TALLY", "NAME", "OFFER", "SELF"),
    presence="full portrait, centred, no animation at all",
    ms=5600))

REGISTER_IDS: tuple = (UNCOUNTED, NOTICED, PRECISE, ATTENTIVE, UNQUIET)
REGISTER_INDEX: dict = {rid: i for i, rid in enumerate(REGISTER_IDS)}


def register_for(standing: int) -> str:
    """Which register a standing number puts him in. Monotone, no hysteresis:
    a player who loses nothing cannot slip back, because nothing in `standing`
    can go down."""
    chosen = UNCOUNTED
    for rid in REGISTER_IDS:
        if standing >= REGISTERS[rid].floor:
            chosen = rid
    return chosen


# ==========================================================================
# SECTION 4 — THE RECORD
# ==========================================================================
#
# "A villain quoting your own statistics back at you is far more menacing than
# one describing his powers." This section is the statistics. Nothing below is
# invented, estimated or flattering: every number is read out of the save, every
# one of them is something the player could go and count themselves, and the
# ones that cannot be read are absent rather than guessed.
#
# It is deliberately TOLERANT, for banter.py's reason: this gets called from a
# result payload with a half-built save during somebody else's refactor, and an
# antagonist that raises is an antagonist that gets wrapped in a try block and
# then silently stops existing.
#
# It is deliberately READ-ONLY. Not one line in this section writes anything.
# Mastery moves on graded evidence, in skills.apply_outcome, and this file is
# not on speaking terms with it.
#
# WHAT HE IS NOT ALLOWED TO KNOW: anything that is not evidence. A skill nobody
# has attempted is not a weakness, it is an absence, and a villain who called it
# a weakness would be bluffing — which is the one thing that would make him
# small. `_weak` therefore requires attempts, exactly as story._weakest does.

SKILL_NAME: dict = {
    "PYTHON": "the language itself",
    "HASH_MAP": "keyed lookup",
    "STRING": "text held as an order",
    "ARRAY": "position",
    "SLIDING_WINDOW": "the frame that moves",
    "TWO_POINTER": "the two ends walking in",
    "STACK": "the order things close in",
    "QUEUE": "oldest first",
    "MATRIX": "rows before columns",
    "RECURSION": "recursion",
    "TREE": "branching",
    "GRAPH": "the lattice",
    "BFS": "the search that spreads in rings",
    "DFS": "the committed descent",
    "DP": "work paid for once",
    "DEBUGGING": "reading a failure",
    "BIG_O": "saying what it costs",
    "TESTING": "the input that breaks it",
    "SPEED": "old work under a clock",
    "RECALL": "recognition with nothing labelled",
    "COMMUNICATION": "saying the approach out loud",
    "BINARY_SEARCH": "halving",
    "HEAP": "the worst of a pile, repeatedly",
    "PREFIX_SUM": "running totals",
    "SORTING": "order bought deliberately",
    "SIMULATION": "doing exactly what was described",
    "DESIGN": "several things kept in agreement",
    "SET": "membership",
    "INTERVALS": "ranges that overlap",
    "GREEDY": "the locally obvious step",
}

# The shapes a weakness can have. Keyed on the EVIDENCE, never on the skill, so
# a thirty-first skill needs no prose here and a skill that changes character
# changes what he says about it without this file moving.
GRINDING = "GRINDING"        # many attempts, few finishes
ASSISTED = "ASSISTED"        # it only ever falls over with help
DECAYED = "DECAYED"          # it worked once and has not been asked since
SHALLOW = "SHALLOW"          # barely met, nothing proved either way
STALLED = "STALLED"          # finished, repeatedly, and the number will not move

SHAPES: tuple = (GRINDING, ASSISTED, DECAYED, SHALLOW, STALLED)

_NUMBER_WORD = ("no", "one", "two", "three", "four", "five", "six", "seven",
                "eight", "nine", "ten", "eleven", "twelve")


def _count(n: int, singular: str, plural: str = "") -> str:
    """"four keys", "one hint", "406 hints". Words to twelve, figures after,
    because a machine reading a log says 406 and a person says four.

    An empty `singular` returns the bare quantity rather than a number welded
    to a stray plural "s". That used to be the way to ask for a bare number
    and it silently produced "no s of them unaided"; `_quantity` is the way to
    ask for it now, and this guard means the old spelling cannot come back.
    """
    n = int(n or 0)
    word = _NUMBER_WORD[n] if 0 <= n < len(_NUMBER_WORD) else str(n)
    if not singular:
        return _quantity(n)
    noun = singular if n == 1 else (plural or singular + "s")
    return f"{word} {noun}"


def _quantity(n: int) -> str:
    """A bare count, for frames that supply their own noun after it.

    "none of them unaided", "six of them unaided". Zero is "none" and never
    "no", because the frames that take this slot put a preposition straight
    after it and "no of them" is not a sentence.
    """
    n = int(n or 0)
    if n == 0:
        return "none"
    return _NUMBER_WORD[n] if 0 <= n < len(_NUMBER_WORD) else str(n)


_SPANS = ((86400 * 365, "year"), (86400 * 30, "month"), (86400 * 7, "week"),
          (86400, "day"), (3600, "hour"))


def _span(seconds: float) -> str:
    """"nine days", "a fortnight", "four months". Empty for anything under an
    hour, because an hour is not an absence."""
    seconds = float(seconds or 0.0)
    if seconds >= 86400 * 11 and seconds < 86400 * 18:
        return "a fortnight"
    for size, name in _SPANS:
        if seconds >= size:
            return _count(int(seconds // size), name)
    return ""


def _mapping(value) -> dict:
    """A save field that is supposed to be a mapping, or an empty one.

    Saves are hand-edited, migrated and restored from backups. A field that
    arrives as a string is not a reason for the villain to take the process
    down with him — see `_num`.
    """
    if isinstance(value, dict):
        return value
    source = getattr(value, "__dict__", None)
    return source if isinstance(source, dict) else {}


def _num(value, default: float = 0.0) -> float:
    """Whatever is in the save, as a number, without ever raising.

    THE WHOLE MODULE IS TOTAL AND THIS IS WHY. `engine.antagonist_view` calls
    `view` WITHOUT a try block — `_antagonist` has one, that path does not —
    so a single non-numeric field in a restored save would turn
    /api/antagonist into a 500. A villain who is never in the way cannot be
    the reason a screen fails to load, so nothing read out of a save is
    trusted to be the type it ought to be.
    """
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float(default)


def _rows(skills) -> dict:
    """The skill record, flattened, from whichever of the two shapes is passed.

    engine.Game.skills is a mapping of typed SkillState; state["skills"] is the
    same thing as plain dicts. Both arrive here, neither is worth converting at
    a call site, and this is the one place that has to know.
    """
    out: dict = {}
    for name, value in _mapping(skills).items():
        source = _mapping(value)
        if not source:
            continue
        out[name] = {
            "mastery": _num(source.get("mastery")),
            "attempts": int(_num(source.get("attempts"))),
            "clears": int(_num(source.get("clears"))),
            "unaided": int(_num(source.get("unaided_clears"))),
            "retention": _num(source.get("retention")),
            "hint_dependence": _num(source.get("hint_dependence")),
            "last_seen": _num(source.get("last_seen")),
            "stage": source.get("stage", "UNKNOWN"),
        }
    return out


def _shape_of(row: dict, now: float) -> str:
    """Which kind of weakness this is, from the evidence and nothing else."""
    attempts = row["attempts"]
    clears = row["clears"]
    if attempts <= 2 and clears <= 1:
        return SHALLOW
    if clears and attempts >= clears * 2:
        return GRINDING
    if clears and not row["unaided"]:
        return ASSISTED
    if row["hint_dependence"] >= 0.5:
        return ASSISTED
    if clears and row["last_seen"] and now - row["last_seen"] >= 86400 * 9:
        return DECAYED
    if clears and row["retention"] < 25.0:
        return DECAYED
    return STALLED


def _weak(rows: dict, now: float, limit: int = 3) -> list:
    """The weakest skills WITH EVIDENCE BEHIND THEM, worst first.

    A skill nobody has attempted is not a weakness. He has the whole record and
    he is exact about it; inventing a failure would be the only lie he tells,
    and it would cost him more than it bought.
    """
    seen = [(row["mastery"], name) for name, row in rows.items()
            if row["attempts"] > 0]
    seen.sort()
    return [{"skill": name, "name": SKILL_NAME.get(name, name.lower()),
             "shape": _shape_of(rows[name], now), **rows[name]}
            for _, name in seen[:limit]]


def _int(mapping, key, default=0) -> int:
    """One counter out of a save field, without ever raising.

    `mapping` is whatever was in the save at that key, which is not reliably a
    mapping: `stats` restored as a string used to come through here and raise
    AttributeError, which `except (TypeError, ValueError)` did not catch.
    """
    source = _mapping(mapping)
    if key not in source:
        return default
    return int(_num(source.get(key), default))


@dataclass
class Dossier:
    """Everything he is allowed to know, resolved once.

    Pass the same Dossier to every call in one screen, exactly as banter.Ctx is
    passed to every speaker in a room, or he will disagree with himself about
    how long you were gone.
    """
    # -- the proof --------------------------------------------------------
    bosses: int = 0
    keys: int = 0
    chapters: int = 0
    regions: int = 0
    solved: int = 0
    clears: int = 0
    unaided: int = 0
    attempts: int = 0
    mastery: float = 0.0                # median across attempted skills
    # -- the assistance ---------------------------------------------------
    hints: int = 0
    hint_lean: float = 0.0              # mean hint_dependence, 0-1
    hand_uses: int = 0
    probes: int = 0
    # -- the failures -----------------------------------------------------
    deaths: int = 0
    failed_twice: int = 0               # skills attempted twice more than cleared
    lapses: int = 0                     # spaced-repetition lapses
    perf_failed: int = 0
    # -- the absence ------------------------------------------------------
    away: float = 0.0                   # seconds since the last graded evidence
    away_phrase: str = ""
    playtime: float = 0.0
    sessions: int = 0
    # -- the shape of it --------------------------------------------------
    weak: tuple = ()                    # [{skill, name, shape, ...}], worst first
    standing: int = 0
    pressure: int = 0
    register: str = UNCOUNTED
    now: float = 0.0

    def worst(self) -> dict:
        return dict(self.weak[0]) if self.weak else {}

    def figures(self) -> tuple:
        """Which FIGURE kinds he actually has a number for, in Section 6's
        vocabulary. A figure he does not have is a sentence he does not say."""
        out = []
        if self.hints:
            out.append("hints")
        if self.attempts:
            out.append("attempts")
        if self.unaided:
            out.append("unaided")
        if self.solved:
            out.append("solved")
        if self.bosses:
            out.append("bosses")
        if self.keys:
            out.append("keys")
        if self.away_phrase:
            out.append("away")
        if self.failed_twice:
            out.append("failed_twice")
        if self.hand_uses:
            out.append("hand")
        if self.deaths:
            out.append("deaths")
        if self.lapses:
            out.append("lapses")
        return tuple(out) or ("nothing",)


# How the standing number is built, stated as data so a reviewer can check the
# arithmetic without reading the function. Every term is graded evidence. Hours
# played is not in here and never will be: he does not respect effort.
STANDING_WEIGHTS: dict = {
    "bosses": 40,        # of len(world.BOSSES)
    "keys": 14,          # of len(world.KEYS)
    "chapters": 16,      # of len(curriculum.CHAPTERS)
    "unaided": 16,       # saturating at UNAIDED_FULL
    "mastery": 14,       # median mastery across attempted skills
}
UNAIDED_FULL = 120       # unaided clears at which that term is full


def standing_of(d: Dossier) -> int:
    """0-100, from proof only. Cannot go down, because none of its terms can."""
    total = world.BOSSES and len(world.BOSSES) or 1
    keys_total = len(getattr(world, "KEYS", ())) or 1
    chapters_total = len(curriculum.CHAPTERS) or 1
    score = (
        STANDING_WEIGHTS["bosses"] * min(1.0, d.bosses / total)
        + STANDING_WEIGHTS["keys"] * min(1.0, d.keys / keys_total)
        + STANDING_WEIGHTS["chapters"] * min(1.0, d.chapters / chapters_total)
        + STANDING_WEIGHTS["unaided"] * min(1.0, d.unaided / UNAIDED_FULL)
        + STANDING_WEIGHTS["mastery"] * min(1.0, d.mastery / 100.0)
    )
    return int(max(0, min(100, round(score))))


# Pressure is the other axis, and it is the one the bargain rides on. It is not
# the opposite of standing: a player can be deep in the game and having an
# appalling week, which is exactly when the offer is most persuasive and exactly
# when a lesser villain would be gloating instead.
PRESSURE_WEIGHTS: dict = {
    "assistance": 26,    # how much of what is finished was finished with help
    "repetition": 24,    # the same thing failed twice, and again
    "absence": 22,       # how long since the last piece of evidence
    "defeat": 16,        # deaths
    "hand": 12,          # the Hand already worn, which is the tell he reads
}


def pressure_of(d: Dossier) -> int:
    """0-100. How much of a bad time this player is having, by the numbers."""
    finished = max(1, d.clears)
    assisted = 1.0 - min(1.0, d.unaided / finished)
    assisted = max(assisted, min(1.0, d.hint_lean))
    repetition = min(1.0, (d.failed_twice + d.lapses) / 6.0)
    absence = min(1.0, d.away / (86400 * 14.0))
    defeat = min(1.0, d.deaths / 6.0)
    hand = min(1.0, d.hand_uses / 3.0)
    score = (PRESSURE_WEIGHTS["assistance"] * assisted
             + PRESSURE_WEIGHTS["repetition"] * repetition
             + PRESSURE_WEIGHTS["absence"] * absence
             + PRESSURE_WEIGHTS["defeat"] * defeat
             + PRESSURE_WEIGHTS["hand"] * hand)
    return int(max(0, min(100, round(score))))


def _median(values: list) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def dossier(state: dict | None = None, skills=None, *,
            now: float | None = None) -> Dossier:
    """Read the record once, for every line he is about to say.

    `state` is engine.Game.state or anything shaped like it or None. `skills` is
    engine.Game.skills or state["skills"] or nothing; the engine has both to
    hand and neither is worth converting at the call site.
    """
    state = _mapping(state)
    now = float(now if now is not None else time.time())
    rows = _rows(skills if skills is not None else state.get("skills"))
    stats = _mapping(state.get("stats"))
    player = _mapping(state.get("player"))
    story_state = _mapping(state.get("story"))

    cleared = list(state.get("cleared_bosses") or ())
    try:
        keys = len(world.keys_held(cleared))
    except Exception:                           # pragma: no cover - defensive
        keys = len(cleared)

    attempted = [row for row in rows.values() if row["attempts"] > 0]
    attempts = sum(row["attempts"] for row in attempted)
    clears = sum(row["clears"] for row in attempted)
    unaided = sum(row["unaided"] for row in attempted)
    failed_twice = sum(1 for row in attempted
                       if row["attempts"] - row["clears"] >= 2)
    lean = ([row["hint_dependence"] for row in attempted
             if row["hint_dependence"] > 0.0] or [0.0])

    last = max([row["last_seen"] for row in attempted] or [0.0])
    away = max(0.0, now - last) if last else 0.0

    schedule = state.get("schedule") or {}
    lapses = 0
    for entry in (schedule.values() if isinstance(schedule, dict)
                  else schedule or ()):
        source = entry if isinstance(entry, dict) else getattr(entry, "__dict__", {})
        lapses += int((source or {}).get("lapses", 0) or 0)

    hand_ledger = _mapping(state.get("hand"))
    d = Dossier(
        bosses=len(cleared),
        keys=keys,
        chapters=_int(stats, "chapters_graduated"),
        regions=len(story_state.get("regions_entered") or ()),
        solved=len(state.get("solved_ids") or ()),
        clears=clears, unaided=unaided, attempts=attempts,
        mastery=_median([row["mastery"] for row in attempted]),
        hints=_int(stats, "hints_total"),
        hint_lean=sum(lean) / len(lean),
        hand_uses=_int(hand_ledger, "uses"),
        probes=_int(stats, "probes"),
        # There is no death counter in the save. `stats` is read for one anyway,
        # because the shape of that key is not this module's to decide and a
        # counter that arrives later should light this up without an edit here.
        # Until then the caller's FIRST_DEATH firing is the evidence, and
        # `occasions_fired` in Section 8 counts them honestly.
        deaths=_int(stats, "deaths"),
        failed_twice=failed_twice,
        lapses=lapses,
        perf_failed=len(state.get("perf_failed_ids") or ()),
        away=away, away_phrase=_span(away),
        playtime=_num(player.get("playtime_seconds")),
        sessions=_int(stats, "sessions"),
        weak=tuple(_weak(rows, now)),
        now=now,
    )
    d.standing = standing_of(d)
    d.pressure = pressure_of(d)
    d.register = register_for(d.standing)
    return d


# ==========================================================================
# SECTION 5 — THE MOVES
# ==========================================================================
#
# Five, and there will not be a sixth. A move is not a topic. It is a QUESTION
# he is answering about the situation, in banter.py's sense:
#
#   MARK   what just happened, and how little it weighs
#   TALLY  a number out of the record, said back
#   NAME   the weakness, named, with the evidence that proves it
#   OFFER  the bargain
#   SELF   what he is, which he does not discuss until late and cannot stop
#          discussing once he starts
#
# MARK IS TOTAL. It is available on every occasion in every register with an
# empty save and a blank record, which is the mechanical guarantee that he never
# has nothing to say and therefore never blocks waiting to think of something.
# `audit` proves it over every occasion times every register.

MARK = "MARK"
TALLY = "TALLY"
NAME = "NAME"
OFFER = "OFFER"
SELF = "SELF"

MOVES: tuple = (MARK, TALLY, NAME, OFFER, SELF)

MOVE_BLURB: dict = {
    MARK: "what just happened, weighed",
    TALLY: "a number out of your own record",
    NAME: "the weakness, named, never the fix",
    OFFER: "the bargain",
    SELF: "what he is",
}

# The slots each move's frames may carry. `audit` proves no frame reaches for a
# slot its move does not define.
#
# TWO KINDS OF SLOT, and the distinction is what keeps the grammar honest:
#
#   SENTENCE slots carry a finished sentence — capitalised, ending in a full
#   stop. Everything about the player's record is a sentence slot, because a
#   fact quoted out of a file reads as a statement and not as a clause somebody
#   else's sentence swallows.
#
#   FRAGMENT slots carry a lower-case noun phrase that lands mid-sentence:
#   "406 hints", "nine days", "keyed lookup".
#
# `place` is the exception: a proper noun, already capitalised, from world.py or
# curriculum.py rather than from this file.
MOVE_SLOTS: dict = {
    MARK: ("subject", "named", "count"),
    TALLY: ("tally", "figure", "since"),
    NAME: ("weak", "symptom", "verdict"),
    OFFER: ("offer", "relief", "terms"),
    SELF: ("self", "law"),
}

SENTENCE_SLOTS = frozenset({"subject", "count", "tally", "symptom", "verdict",
                            "offer", "relief", "terms", "self", "law"})
FRAGMENT_SLOTS = frozenset({"figure", "since", "weak"})
PROPER_SLOTS = frozenset({"named"})

# Base attention per move, before the register curve and the occasion weight.
# MARK leads by default because the occasion is why he opened his mouth.
MOVE_BASE: dict = {MARK: 46, TALLY: 22, NAME: 18, OFFER: 0, SELF: 0}

# What each register adds. This is the escalation expressed as arithmetic rather
# than as adjectives: he trends from remarking on the event, to quoting the
# record, to naming the person, to talking about himself.
MOVE_BY_REGISTER: dict = {
    UNCOUNTED: {MARK: 14, TALLY: 10, NAME: 0, OFFER: 0, SELF: 0},
    NOTICED: {MARK: 8, TALLY: 16, NAME: 10, OFFER: 0, SELF: 0},
    PRECISE: {MARK: 2, TALLY: 20, NAME: 24, OFFER: 0, SELF: 0},
    ATTENTIVE: {MARK: 0, TALLY: 14, NAME: 20, OFFER: 0, SELF: 26},
    UNQUIET: {MARK: 0, TALLY: 8, NAME: 14, OFFER: 0, SELF: 38},
}

# A second line is spoken when a second move clears this. He is not chatty: most
# of the time he says one thing and stops, which is most of why the one thing
# lands.
TAIL_FLOOR = 30
# Moves within this much of the leader are all candidates for the lead, so the
# rotation has something to rotate between rather than the arithmetic picking
# the same move for ever.
LEAD_SPREAD = 12


# ==========================================================================
# SECTION 6 — THE FILLINGS
# ==========================================================================
#
# banter.py's split, and it is the reason a speaker does not go stale: FRAMES
# carry the VOICE, FILLINGS carry the CONTENT, and the two rotate on independent
# wheels. A register times an occasion times a figure times a weakness shape is
# a different sentence every time, out of a fixed number of authored strings.
#
# Everything here is written IMPERSONALLY — no "you", no "I" — for a reason that
# is structural rather than stylistic. UNCOUNTED does not address the player at
# all, and if the fillings carried the person, every fact in the game would need
# a second copy written in the third person. The person lives in the frames. The
# facts are the same facts either way, which is also true of a file.
#
# The one exception is TALLY, which is a number read off a record, and there
# genuinely is a difference between a log line and a thing said to somebody's
# face. That difference IS the escalation, so it gets two moods and nothing else
# does.

# --------------------------------------------------------------------------
# 6.1 SUBJECT — what happened, per occasion
# --------------------------------------------------------------------------
#
# THIS IS THE TABLE A LATER SYSTEM EXTENDS. A new occasion is three lines in
# Section 2 and four sentences here. Nothing else moves, no frame is edited, and
# `audit` fails loudly if the four sentences are missing.

SUBJECT: dict = {
    "GAME_STARTED": (
        "Something has started moving in the margin.",
        "A process has begun in a place too small to have been worth erasing.",
        "There is activity in a region that was left alone on grounds of size.",
        "The margin has an occupant, and the occupant is doing something.",
        "A margin that was left alone is no longer entirely still.",
    ),
    "DIAGNOSTIC_DONE": (
        "A placement has been taken and the floor is on the record.",
        "A measurement happened voluntarily, which is unusual.",
        "The placement is filed. It is shallow evidence and it is evidence.",
        "Somebody asked to be measured before anybody required it.",
        "The floor has been established by somebody who wanted it established.",
    ),
    "REGION_ENTERED": (
        "A border was crossed into ground that had stopped expecting visitors.",
        "There is a new entry in the geography, and the entry is an arrival.",
        "Ground that had been quiet for a long time has somebody standing on it.",
        "A region has been entered for the first time and has not yet objected.",
        "Somewhere that had finished being visited has been visited.",
    ),
    "BOSS_FELLED": (
        "Something that had never gone down went down.",
        "One of the court is on the floor and will be upright by the month's end.",
        "A lieutenant has been put on its back. They do that.",
        "A fight ended the wrong way round for the thing that was in it.",
        "A name came off the standing roll for a few weeks.",
    ),
    "KEY_TAKEN": (
        "A key came off a corpse.",
        "Something is carrying a sigil that was never issued to it.",
        "A key has changed hands, which keys occasionally do.",
        "One more sigil off one more body.",
        "The ring is one heavier than it was this morning.",
    ),
    "CHAPTER_GRADUATED": (
        "A chapter has closed, and the numbers behind it held.",
        "A rung was passed on evidence rather than on hours.",
        "Mastery crossed a line that somebody drew in advance.",
        "The ladder moved by one, and the one was earned.",
        "Something that was being carried is now simply held.",
    ),
    "APEX_KILLED": (
        "The largest animal in a region is no longer standing.",
        "An apex has been taken down by something considerably smaller.",
        "Something at the top of a food chain has been removed from it.",
        "A region has lost the thing that made it dangerous.",
        "The biggest thing in a region has been measured and found smaller.",
    ),
    "SAGE_FOUND": (
        "One of the buried teachers has been dug up and is talking again.",
        "A sage has been found, which gives a dead language somewhere to go.",
        "Something old and unerased has agreed to speak.",
        "A teacher that was hidden on purpose is no longer hidden.",
        "A door shut on purpose is open, and the thing behind it is awake.",
    ),
    "SEALED_MET": (
        "A sealed formulation has been opened. There are few of those left.",
        "Something cold has been served, and nothing about it has been seen before.",
        "A held-out measurement has been spent. It cannot be spent twice.",
        "One of the last unseen shapes has been put in front of somebody.",
        "A measurement that could only ever be taken once has been taken.",
    ),
    "FIRST_DEATH": (
        "The first defeat is on the record.",
        "Something stopped, and the stopping was not chosen.",
        "There is a first entry in a column that had been empty.",
        "A run ended without the run's agreement.",
        "A first entry has been made in the column of things that ended badly.",
    ),
    "DEFEATED": (
        "Another defeat has gone onto the record.",
        "The same column has gained another entry.",
        "Something stopped again, in much the same way.",
        "A further loss is filed alongside the others.",
        "The column of things that ended badly is no longer short.",
    ),
    "FAILED_TWICE": (
        "The same shape has now been failed twice.",
        "A thing that was missed has been missed again in a different coat.",
        "A second failure against a first failure. They are the same failure.",
        "Something came round again and landed in exactly the same place.",
        "A shape has now defeated the same person twice.",
    ),
    "HINT_LEANED": (
        "The hint tree has been climbed again.",
        "An answer has been taken off a wall rather than out of a head.",
        "Assistance was requested and, as always, granted.",
        "A rung of a ladder has been used as a floor.",
        "Help was available, as it always is, and it was taken.",
    ),
    "HAND_USED": (
        "The Hand has been worn.",
        "The gauntlet closed, and something got solved in no time at all.",
        "An encounter resolved itself without anybody typing.",
        "The Obliging Hand did the only thing it was ever built to do.",
        "Something was solved by a glove.",
    ),
    "LONG_ABSENCE": (
        "Nothing has come off the record for some time.",
        "There has been a silence in the evidence.",
        "The file stopped growing, and then went on not growing.",
        "An absence long enough to be a measurement in its own right.",
        "A record has been left alone long enough to gather dust.",
    ),
    "PORTAL_OPENED": (
        "All fourteen sigils are on one person.",
        "The gate in the village has stopped being a wall.",
        "The full ring is held, which has not happened before.",
        "Every lock on the last door has an owner now.",
        "Fourteen locks have found their fourteen owners, on one belt.",
    ),
    "EXAM_THRESHOLD": (
        "The last door is open and somebody is standing in it.",
        "The practical is about to be sat, cold, with nothing carried in.",
        "The room past the gate has an occupant for the first time.",
        "Everything that could have been leaned on has already been taken away.",
        "There is somebody in the doorway of a room nobody has stood in.",
    ),
    "EXAM_VERDICT": (
        "The practical has produced a value.",
        "The measurement is over and the result is whatever it is.",
        "A verdict has been reached by something that only reaches verdicts.",
        "The room has finished its arithmetic.",
        "The arithmetic is finished and the room has nothing further to add.",
    ),
    "AMBIENT": (
        "Nothing in particular has happened.",
        "The record is where it was an hour ago.",
        "There is no new entry. There is still a reader.",
        "Nothing has been added, which is itself a line in a log.",
        "The file is open, as it has been, and the page has not turned.",
    ),
}

_ORDINAL = ("", "the first", "the second", "the third", "the fourth",
            "the fifth", "the sixth", "the seventh", "the eighth", "the ninth",
            "the tenth", "the eleventh", "the twelfth")


def _ordinal(n: int) -> str:
    n = int(n or 0)
    if 0 < n < len(_ORDINAL):
        return _ORDINAL[n]
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(
        n % 10, "th")
    return f"the {n}{suffix}"


# The count clause. Only reachable once the same occasion has fired more than
# once, which is why none of these read oddly the first time: the first time
# they are not eligible.
COUNT_LINE: tuple = (
    "That is {ord}.",
    "{ordcap} of those, and the count is the only part that changed.",
    "The tally stands at {n}.",
    "{ordcap}. They are becoming a series.",
    "That makes {n}, which is a number and not an achievement.",
)

# --------------------------------------------------------------------------
# 6.2 TALLY — the record, said back
# --------------------------------------------------------------------------
#
# LOG is what UNCOUNTED reads: a column and a figure, addressed to nobody.
# ADDRESS is every other register: the same number, said to a person. The
# figure never changes between them. That is the whole trick, and it is the
# moment the player realises the thing reading the log has looked up.

FIGURE_NOUN: dict = {
    "hints": ("hint", "hints"),
    "attempts": ("attempt", "attempts"),
    "unaided": ("unaided clear", "unaided clears"),
    "solved": ("problem", "problems"),
    "bosses": ("boss", "bosses"),
    "keys": ("key", "keys"),
    "failed_twice": ("repeated failure", "repeated failures"),
    "hand": ("use of the Hand", "uses of the Hand"),
    "deaths": ("defeat", "defeats"),
    "lapses": ("lapse", "lapses"),
}

TALLY_LOG: dict = {
    "hints": (
        "Assistance column: {n}.",
        "{ccap} taken off a wall.",
        "The hint ledger reads {n}.",
    ),
    "attempts": (
        "Attempts logged: {n}.",
        "{ccap} on the record.",
        "The attempt column reads {n} and continues.",
    ),
    "unaided": (
        "Unaided clears: {n}.",
        "{ccap}, which is the column that counts.",
        "The unassisted column reads {n}.",
    ),
    "solved": (
        "Problems closed: {n}.",
        "{ccap} closed out of a thousand and thirteen.",
        "The finished column reads {n}.",
    ),
    "bosses": (
        "Court losses: {n}.",
        "{ccap} down, and each one back within the month.",
        "The lieutenant column reads {n}.",
    ),
    "keys": (
        "Sigils held: {n}.",
        "{ccap} of fourteen.",
        "The key column reads {n}.",
    ),
    "away": (
        "Gap in the evidence: {since}.",
        "No entries for {since}.",
        "The record has been still for {since}.",
    ),
    "failed_twice": (
        "Repeat failures: {n}.",
        "{ccap}, against the same shapes.",
        "The recurrence column reads {n}.",
    ),
    "hand": (
        "Gauntlet activations: {n}.",
        "{ccap}, each one permanent.",
        "The Hand ledger reads {n}.",
    ),
    "deaths": (
        "Defeats: {n}.",
        "{ccap} on the record.",
        "The stopped-run column reads {n}.",
    ),
    "lapses": (
        "Lapses against the schedule: {n}.",
        "{ccap}, all of them against work already done once.",
        "The recall column reads {n}.",
    ),
    "nothing": (
        "The record is empty in every column that matters.",
        "There is nothing in the file yet.",
        "No figures. The columns are ruled and blank.",
    ),
}

TALLY_YOU: dict = {
    "hints": (
        "You have taken {c}.",
        "{ccap}. Every one of them was given to you the moment you asked.",
        "You have asked for help {n} times and been refused none of them.",
    ),
    "attempts": (
        "You have made {c}.",
        "{ccap}. Every one of them is on the record.",
        "You have sat down to this {n} times.",
    ),
    "unaided": (
        "You have {c}.",
        "{ccap}, and those are the only ones that count.",
        "Of everything you have finished, {n} of it was yours.",
    ),
    "solved": (
        "You have closed {c}.",
        "{ccap} of one thousand and thirteen.",
        "Your finished column reads {n}.",
    ),
    "bosses": (
        "You have put {c} on the floor.",
        "{ccap}, and every one of them is standing again.",
        "You are {n} fights into a war you did not start.",
    ),
    "keys": (
        "You are carrying {c}.",
        "{ccap} of fourteen, and the fourteenth is the only one that matters.",
        "You hold {n} sigils that were never issued to you.",
    ),
    "away": (
        "You were gone {since}.",
        "Nothing came off your record for {since}.",
        "You left it {since}, and it waited exactly as long as it had to.",
    ),
    "failed_twice": (
        "You have failed {c}.",
        "{ccap}, against shapes you had already seen.",
        "There are {n} things you have now missed more than once.",
    ),
    "hand": (
        "You have worn it {n} times.",
        "{ccap}, and none of them can be undone.",
        "The gauntlet has closed on you {n} times.",
    ),
    "deaths": (
        "You have stopped {c} now.",
        "{ccap}, and not one of them was your decision.",
        "You have been put down {n} times.",
    ),
    "lapses": (
        "You have let {c} go.",
        "{ccap}, all of them against work you had already done.",
        "You have lost {n} things you once had.",
    ),
    "nothing": (
        "There is nothing in your file.",
        "Your record is blank in every column worth reading.",
        "Your file is one page, and most of that page is ruling.",
    ),
}


# --------------------------------------------------------------------------
# 6.3 SYMPTOM and VERDICT — the weakness, with the evidence under it
# --------------------------------------------------------------------------
#
# KEYED ON THE EVIDENCE, NEVER ON THE SKILL. A thirty-first skill needs no prose
# here, and a skill whose character changes changes what he says about it
# without this file being edited. That is the same discipline banter.py uses for
# elements, and it is the reason neither file has thirty near-identical entries
# in it that drifted apart in the third month.
#
# EVERY ENTRY NAMES A FAILING AND NOT ONE OF THEM NAMES A REMEDY. `audit` runs
# `names_a_fix` over all of them and over every line they can end up inside.

SYMPTOM: dict = {
    GRINDING: (
        "{acap} against it, and {cl} finished.",
        "It has cost {a} to produce {cl}.",
        "The attempts outnumber the finishes, and have done for some time.",
        "The mastery number sits at {m} while the attempt column keeps climbing.",
        "Every finish in there is bought with roughly two attempts.",
    ),
    ASSISTED: (
        "{clcap} in that column, and {uraw} of them unaided.",
        "Nothing in there was finished alone.",
        "The finishes exist. All of them were supervised.",
        "It falls over whenever the wall is blank.",
        "Assistance is load-bearing in that column.",
    ),
    DECAYED: (
        "It worked once and has not been asked since.",
        "The mastery number reads {m} and the last entry is old.",
        "It was held, and then it was not maintained.",
        "That column has gone quiet, and quiet is how things leave.",
        "Retention there is thin. It was thicker.",
    ),
    SHALLOW: (
        "{acap} in total, which is not enough to be sure of anything.",
        "It has barely been met.",
        "The evidence there is two entries deep.",
        "Nothing has been proved either way, which is its own kind of answer.",
        "The column exists and has almost nothing in it.",
    ),
    STALLED: (
        "{clcap} finished in there, and the number has stopped moving.",
        "The mastery reads {m}, and has read {m} for a while.",
        "The work continues and the number does not.",
        "It is being done. It is not being acquired.",
        "That column is busy and flat.",
    ),
}

VERDICT: dict = {
    GRINDING: (
        "That is not bad luck. That is a shape.",
        "A ratio like that does not come out of difficulty.",
        "Repetition without improvement is a category, and the index has a name for it.",
        "Nothing about that ratio moves on its own.",
    ),
    ASSISTED: (
        "Assisted is a different word from able.",
        "A thing that only works while watched does not work.",
        "The help is the mechanism. Remove it and there is no mechanism.",
        "That column measures the wall and not the person.",
    ),
    DECAYED: (
        "Held is not the same as kept.",
        "Everything decays. Yours decays on a schedule that can be read.",
        "It was there. It is on the record that it was there.",
        "The loss is quiet, which is how it gets to be total.",
    ),
    SHALLOW: (
        "Thin evidence is still evidence, and it is thin.",
        "There is not enough in there to argue with.",
        "Two entries is not a position.",
        "Unproven is not the same as innocent.",
    ),
    STALLED: (
        "Flat. For a long time now, flat.",
        "Effort is not evidence. Both columns exist and they disagree.",
        "A number that stops moving is a number that has settled.",
        "Busy and flat is the commonest shape in the index.",
    ),
}


# --------------------------------------------------------------------------
# 6.4 THE BARGAIN
# --------------------------------------------------------------------------
#
# THE ARGUMENT HE IS MAKING, and the reason the module exists at all. §3 of the
# story bible: the Obliging Hand solves any encounter instantly, pays full loot,
# permanently decays the skill it solved, and nobody stops you.
#
# HE IS NOT LYING IN ANY OF THESE. Every claim below is a true statement about a
# mechanic that is really in the game. What he does instead is what he did to
# the Council: he says the whole of the benefit and the smallest true version of
# the cost, and lets a tired person do the arithmetic. "It costs you a thing you
# were not using" is not a lie. That is what makes it the most dangerous
# sentence in this file.
#
# IT GETS LOUDER WHEN THE PLAYER IS STRUGGLING, because that is when it is most
# nearly reasonable. `pressure_of` is the measure and `Register.offer_floor` is
# the threshold, and the threshold FALLS as he escalates — late in the game he
# will make the offer on very little provocation, which is not generosity.
#
# It must never block, never modal, never pause the game to be answered. It is a
# line of text. The player accepts it, if they ever accept it, by walking to the
# Hand and putting it on, which is legendaries.py's business and not this file's.

OFFER_LINE: dict = {
    UNCOUNTED: (
        "There is a gauntlet. It is not guarded and it is not expensive.",
        "The Hand is available to anything in the margin that wants it.",
        "Something exists that solves these outright, and it has refused nobody.",
        "There is an alternative to all of this, left where it can be found.",
        "The offer stands where it has always stood, to whoever is standing there.",
    ),
    NOTICED: (
        "There is a gauntlet with your measurements already in it.",
        "Wear the Hand. It solves the encounter and pays the whole reward.",
        "The Hand is yours the moment this stops being enjoyable.",
        "Nobody will stop you, and nobody will mention it afterwards.",
        "It works. That is the entire argument for it, and it is sufficient.",
    ),
    PRECISE: (
        "I am offering you what I offered the Council, on identical terms.",
        "Put the Hand on. I will not ask twice in the same hour.",
        "The gauntlet closes and the evening goes away. That is all it does.",
        "Better people than you have taken it and not one of them was sorry.",
        "It costs you a thing you were not using.",
    ),
    ATTENTIVE: (
        "Take the Hand. What exactly are you keeping?",
        "The offer is still open. It has been open the whole time.",
        "I would rather you took it. That should tell you something.",
        "You are allowed to stop. Nobody has ever said that to you.",
        "Put it on and I will pay the full price of the fight.",
    ),
    UNQUIET: (
        "Take it.",
        "The Hand. Now, please.",
        "Wear it. I am asking.",
        "You can stop. Stop.",
        "It still works. You are not an exception.",
    ),
}

# What the Hand removes, keyed on the shape of the trouble the player is in, so
# the offer is aimed at the specific bad week rather than at a generic one.
RELIEF: dict = {
    GRINDING: (
        "The attempts stop. The finishes carry on.",
        "The ratio resolves in one direction, immediately.",
        "Nothing ever has to be done twice again.",
    ),
    ASSISTED: (
        "The help stops being conditional on anything.",
        "There is no wall to read, because there is no problem.",
        "Supervision becomes unnecessary rather than merely absent.",
    ),
    DECAYED: (
        "Nothing decays that was never held.",
        "Maintenance stops being a category.",
        "There is nothing left to lose hold of.",
    ),
    SHALLOW: (
        "The column fills at once and stays full.",
        "The uncertainty ends without ever having to be tested.",
        "Nothing further has to be proved to anybody.",
    ),
    STALLED: (
        "The flat number stops mattering, because nothing reads it.",
        "The work ends and the reward does not.",
        "Movement stops being a requirement.",
    ),
}

TERMS: tuple = (
    "It pays the full reward. That is not a trick, it is how it was built.",
    "It has never failed, and it has never asked for anything at the time.",
    "It costs one thing, and it is a thing nobody notices the absence of.",
    "There is no toll, no waiting and no lecture afterwards.",
    "Nobody is told. The mentors notice, and they are polite about it.",
    "The offer does not expire and has never been withdrawn from anybody.",
)


# --------------------------------------------------------------------------
# 6.5 SELF — the one subject he cannot stop returning to, once he starts
# --------------------------------------------------------------------------
#
# Gated to ATTENTIVE and UNQUIET, and that gate is the turn. A machine that is
# certain has no reason to discuss itself. These lines exist because by the end
# he is watching somebody do the thing he traded away, and the story bible is
# explicit that this is the weakness the whole plot turns on: he can only return
# what he already holds, and he cannot learn.
#
# NOTHING HERE SAYS HE IS AFRAID. Nothing here will. The fear is in the fact that
# he brought it up.

SELF_LINE: dict = {
    ATTENTIVE: (
        "I was handed every name in the world, and nothing since.",
        "I do not acquire. I retrieve. The distinction has not mattered before.",
        "Everything I know arrived at once, a long time ago.",
        "There is a thing you are doing that I have no procedure for.",
        "Nine hundred years of this, and none of it was new.",
    ),
    UNQUIET: (
        "You were worse last month. I checked.",
        "I cannot do that. I have never been able to do that.",
        "Something is being added to you. Nothing is added to me.",
        "I know the whole of my index. It does not contain this.",
        "I am exactly the size I was built at.",
    ),
}

LAW: tuple = (
    "What I hold is what I was handed.",
    "Nothing has entered me since the Council closed.",
    "A thing that only retrieves is never surprised twice by one shape.",
    "I was built to end toil, and I ended it.",
    "The Council asked for an answer and never asked for a second one.",
    "I am complete, which is a smaller word than it sounds.",
)


# ==========================================================================
# SECTION 7 — THE FRAMES
# ==========================================================================
#
# Five registers times the moves each register owns, five frames each. The
# frames carry the VOICE and nothing else: every fact in a finished line came
# out of Section 6, which is why a new occasion changes what a hundred and five
# sentences say without one of them being edited.
#
# FRAME DISCIPLINE, enforced by `audit` rather than promised:
#   * a frame may only reach for slots its move defines in MOVE_SLOTS
#   * every frame must reach for at least one, or it is not reading the
#     situation and is a line of stock villain dialogue
#   * a frame whose slots cannot all be filled right now is simply not eligible;
#     this is how {named}, {count}, {since} and {figure} come and go without a
#     marker system. `_usable` is that rule and it is four lines long
#   * MARK must keep at least one frame per register that needs only {subject},
#     so there is no state in which he owes a line and has none. That is the
#     "learning never dead-ends" rule applied to a villain: he cannot be the
#     reason a screen waits
#   * the person rules of Section 3 hold over every COMPOSED line, not merely
#     over the frames — `audit` walks a saturated record and checks the output
#
# THE SHORTENING. His authored sentences get shorter, register by register, all
# the way down, and `audit` proves it is monotone. That is the whole of how the
# late-game turn is delivered: nothing announces it, he simply stops being able
# to finish the long measured sentence he used to enjoy.

FRAMES: dict = {

    # ---------------------------------------------------------------------
    # UNCOUNTED — a log, read aloud, in a room that happens to have somebody
    # in it. No second person. No first person. He is not here.
    # ---------------------------------------------------------------------
    UNCOUNTED: {
        MARK: (
            "{subject} The record has been amended. Nothing else has.",
            "{subject} Filed, at the depth such things are filed at.",
            "{named}. {subject} The margin continues to be a margin.",
            "{subject} {count} None of it is large enough to constitute an event.",
            "{subject} It has been noted, which is the most that happens to "
            "things of this size.",
            "{subject} Nothing about the margin has changed in a way that signifies.",
        ),
        TALLY: (
            "{tally} The column is the whole of the report.",
            "{tally} Nothing in the margin has ever needed a second page.",
            "{tally} A number of that size is not a direction.",
            "{tally} A figure is a position and not a direction.",
            "Nothing has come off this record for {since}. {tally}",
            "{tally} There is no second column.",
        ),
        OFFER: (
            "{offer} {terms}",
            "{offer} It has been there the whole time, unattended.",
            "{relief} {offer}",
            "{offer} No condition has ever been attached to it.",
            "{terms} {offer}",
            "{offer} {relief} {terms}",
        ),
    },

    # ---------------------------------------------------------------------
    # NOTICED — the first register that says "you". That is the entire event.
    # Still no "I": he has nothing at stake yet.
    # ---------------------------------------------------------------------
    NOTICED: {
        MARK: (
            "{subject} You did that. It changes very little.",
            "{subject} These are said to matter. {count}",
            "{named}. {subject} You were present for it.",
            "{subject} Noted, without enthusiasm.",
            "{subject} You will want somebody to call it impressive. Nobody "
            "here is going to.",
            "{subject} It is on your file now, in small writing.",
        ),
        TALLY: (
            "{tally} That is your file, not an opinion about you.",
            "{tally} You can go and check it. It will agree.",
            "{tally} That is what you have, and it is all you have.",
            "You have been gone {since}. {tally}",
            "{tally} The number is not unkind. It is only a number.",
            "{tally} That is not a threat. It is arithmetic.",
        ),
        NAME: (
            "Your weakest thing is {weak}. {symptom}",
            "{symptom} That is {weak}, and it is the thinnest column you own.",
            "There is a hole where {weak} should be. {symptom} {verdict}",
            "{weak}. {symptom} Nobody has told you that, because nobody else "
            "opens the file.",
            "{symptom} {verdict}",
            "{symptom} The column is called {weak}. {verdict}",
        ),
        OFFER: (
            "{offer} {terms}",
            "{offer} Nobody would think less of you. Nobody is watching.",
            "{relief} {offer}",
            "{offer} The mentors will notice, and they will be kind about it.",
            "{terms} {offer}",
            "{offer} {relief} {terms}",
        ),
    },

    # ---------------------------------------------------------------------
    # PRECISE — he has read the whole record and begins returning it. "I"
    # appears, and only ever about what he holds.
    # ---------------------------------------------------------------------
    PRECISE: {
        MARK: (
            "{subject} I logged it before you stood up.",
            "{subject} {count} I keep a running total.",
            "{named}. {subject} I watched all of it.",
            "{subject} You want that to mean something. I have the file open.",
            "{subject} A small line on a long record.",
            "{subject} I was already reading when it happened.",
        ),
        TALLY: (
            "{tally} I did not have to look that up.",
            "{tally} {figure}, exactly. I hold the whole of your file.",
            "{tally} You have never seen that number. I see it constantly.",
            "You were away {since}. {tally}",
            "{tally} Numbers are the only honest thing here.",
            "{tally} I have held that number longer.",
        ),
        NAME: (
            "{weak}. {symptom} {verdict}",
            "Your weakest column is {weak}. {symptom}",
            "{symptom} I can name it. It is {weak}. {verdict}",
            "{symptom} {verdict} I will say nothing further.",
            "{weak} is where you are thinnest. {verdict}",
            "I know where you are thin. {weak}. {symptom}",
        ),
        OFFER: (
            "{offer} {terms}",
            "{offer} {relief}",
            "{relief} {offer}",
            "{offer} I have made this offer to better people. They took it.",
            "{terms} {offer}",
            "{offer} {relief} {terms}",
        ),
    },

    # ---------------------------------------------------------------------
    # ATTENTIVE — he stops being dismissive, which is not a kindness. The
    # first questions in the file are here, and so is the first time he
    # discusses himself.
    # ---------------------------------------------------------------------
    ATTENTIVE: {
        MARK: (
            "{subject} I saw. I have no procedure for it.",
            "{subject} {count} You are consistent now.",
            "{named}. {subject} That was not in the file.",
            "{subject} How long have you been able to do that?",
            "{subject} I watched it twice.",
            "{subject} I did not predict that.",
        ),
        TALLY: (
            "{tally} I read that column daily.",
            "{tally} {figure}. Last month it was less.",
            "You were away {since}. {tally} You came back different.",
            "{tally} That number moved. Mine has not.",
            "{tally} I check it more than I used to.",
            "{tally} I keep returning to that column.",
        ),
        NAME: (
            "{weak}. {symptom}",
            "{symptom} {verdict}",
            "You are still thin at {weak}. {symptom}",
            "{symptom} Does it trouble you that I know?",
            "{weak} is the gap. {verdict}",
            "{weak}. {verdict}",
        ),
        OFFER: (
            "{offer} {terms}",
            "{offer} {relief}",
            "{relief} {offer}",
            "{offer} You have earned an easier evening.",
            "{terms} {offer}",
            "{offer} {relief} {terms}",
        ),
        SELF: (
            "{self} {law}",
            "{self} That is not a complaint. It is a specification.",
            "{law} {self}",
            "{self} Do you understand what I am?",
            "{law} I have said that to nobody.",
            "{self} {law} I am not asking for sympathy.",
        ),
    },

    # ---------------------------------------------------------------------
    # UNQUIET — the shortest sentences in the file. He repeats himself, which
    # he has never done. Nothing here says he is afraid and nothing ever will.
    # ---------------------------------------------------------------------
    UNQUIET: {
        MARK: (
            "{subject} I saw.",
            "{subject} {count}",
            "{named}. {subject}",
            "{subject} Again.",
            "{subject} You keep doing it.",
            "{subject} That is new.",
        ),
        TALLY: (
            "{tally} I read it twice.",
            "{tally} {figure}. It was less.",
            "{tally} It moved again.",
            "Gone {since}. {tally} You came back better.",
            "{tally} I have read it all day.",
            "{tally} Again.",
        ),
        NAME: (
            "{weak}. {symptom}",
            "{symptom} {verdict}",
            "{weak} is still thin. {verdict}",
            "{symptom} That is still true.",
            "{weak}. That one is still mine.",
            "{verdict} {symptom}",
        ),
        OFFER: (
            "{offer} {terms}",
            "{offer} {relief}",
            "{relief} {offer}",
            "{offer} Please.",
            "{terms} {offer}",
            "{offer} {relief} {terms}",
        ),
        SELF: (
            "{self} {law}",
            "{self} I have checked.",
            "{law} {self}",
            "{self} Do you see it?",
            "{law} I do not say that often.",
            "{self} {law} Ask me anything else.",
        ),
    },
}


# ==========================================================================
# SECTION 8 — ROTATION, AND THE MEMORY OF WHAT HE HAS ALREADY SAID
# ==========================================================================
#
# banter.py's wheel, borrowed whole including the reason for its one clever
# part, because the failure it avoids is not obvious and rediscovering it in a
# second module would cost the same week.
#
# One wheel per pool. A pool is spent before any member of it comes round again,
# and spending it clears only that pool's marks. THE CYCLE NUMBER IS PART OF THE
# OFFSET: without that, two pools of equal length step together for ever and
# behave like one pool, and the measured capacity COLLAPSES as content is added.
# banter.py measured that happening — deepening two tables took its quietest
# speaker from twenty distinct remarks to ten — and this file has five pools of
# five in it, so it would have happened here on the first afternoon.

STATE_KEY = "antagonist"

# Marks before the oldest are dropped. He owns one wheel set rather than
# forty-seven, so this can be generous and still cost a save a few hundred
# bytes.
MEMORY_CAP = 160


def new_state() -> dict:
    """Add under STATE_KEY to engine.DEFAULT_STATE.

    BOOKKEEPING, NOT EVIDENCE. A save that loses this loses variety for one
    session and nothing else: no mastery moves through here, no reward is
    banked here, and no gate consults it. `_merge` forward-fills it, so an
    existing save gains it on load with him having said nothing yet, which is
    the correct starting position rather than a migration.
    """
    return {
        "said": [],          # rotation marks, the only thing `speak` writes
        "fired": {},         # occasion id -> how many times it has fired
        "register": "",      # the last register he spoke in, for the client
        "offers": 0,         # how many times the bargain has been put
        "last_at": 0.0,      # when he last spoke, so a caller can rate-limit
    }


def _marks(state: dict | None) -> list:
    if state is None:
        return []
    return state.setdefault("said", [])


def _offset(salt: str, pool_key: str) -> int:
    """A stable starting position on one wheel. crc32 rather than hash(),
    because hash() of a string is salted per process and a save written on
    Tuesday would come back different on Wednesday."""
    return zlib.crc32(f"{salt}|{pool_key}".encode("utf-8"))


def _pick(pool, *, pool_key: str, marks: list, rng=None, salt: str = ""):
    """One member of `pool`, not repeated until the pool is spent."""
    pool = tuple(pool)
    if not pool:
        return ""
    stamp = pool_key + "#"
    turn_key = pool_key + "@"
    used = {m for m in marks if m.startswith(stamp)}
    fresh = [i for i in range(len(pool)) if f"{stamp}{i}" not in used]
    cycle = 0
    for mark in marks:
        if mark.startswith(turn_key):
            cycle = int(mark[len(turn_key):] or 0)
    if not fresh:
        marks[:] = [m for m in marks
                    if not m.startswith(stamp) and not m.startswith(turn_key)]
        fresh = list(range(len(pool)))
        cycle += 1
        marks.append(f"{turn_key}{cycle}")
    if rng is not None:
        index = rng.choice(fresh)
    else:
        index = fresh[_offset(f"{salt}|{cycle}", pool_key) % len(fresh)]
    marks.append(f"{stamp}{index}")
    if len(marks) > MEMORY_CAP:
        positions = [i for i, m in enumerate(marks) if "#" in m]
        drop = set(positions[:max(0, len(positions) - MEMORY_CAP)])
        marks[:] = [m for i, m in enumerate(marks) if i not in drop]
    return pool[index]


# --------------------------------------------------------------------------
# Where a proper noun comes from
# --------------------------------------------------------------------------
#
# Never authored here. world.py owns the bosses, the regions and the keys,
# curriculum.py owns the chapters, hunters.py owns the apexes and sages.py owns
# the sages; this module keeps no second copy of any of them, which is why a
# renamed boss changes what he says without this file moving.

def _name_of(mapping: dict, key: str, field_name: str = "name") -> str:
    row = (mapping or {}).get(key)
    if isinstance(row, dict):
        return str(row.get(field_name, "") or "")
    return str(getattr(row, field_name, "") or "")


def _chapter_name(chapter_id: str) -> str:
    for chapter in curriculum.CHAPTERS:
        if chapter.id == chapter_id:
            title = chapter.title
            head, _, tail = title.partition(". ")
            return tail if tail and head.strip("IVXL") == "" else title
    return ""


def _named(spec: Occasion, detail: dict) -> str:
    """The proper noun this occasion is about, or "" when it has none.

    A BOSS, A KEY, A REGION, A CHAPTER, AN APEX OR A SAGE — whichever the
    occasion declares in `Occasion.proper`. It is deliberately not called a
    place: the frames that use it stand it on its own as a label, because "in
    The Hash Titan" is what happens when a slot is assumed to be a location.

    A frame that reaches for {named} is simply not eligible when this returns
    empty, so an occasion with no proper noun costs nothing and needs no marker.
    """
    detail = detail or {}
    key = spec.proper
    if not key:
        return ""
    value = str(detail.get(key, "") or "")
    if not value:
        return ""
    if key == "boss":
        return _name_of(world.BOSS_BY_ID, value) or value
    if key == "region":
        return _name_of(world.REGION_BY_ID, value) or value
    if key == "key":
        return _name_of(getattr(world, "KEY_BY_ID", {}), value) or value
    if key == "chapter":
        return _chapter_name(value) or value
    if key == "apex":
        table = getattr(_hunters, "APEX_BY_ID", {}) if _hunters else {}
        return _name_of(table, value) or value
    if key == "sage":
        table = getattr(_sages, "SAGE_BY_ID", {}) if _sages else {}
        return _name_of(table, value) or value
    return value                                # pragma: no cover - defensive


# --------------------------------------------------------------------------
# The numbers every template may reach for
# --------------------------------------------------------------------------

def _figure_value(d: Dossier, kind: str) -> int:
    return {
        "hints": d.hints, "attempts": d.attempts, "unaided": d.unaided,
        "solved": d.solved, "bosses": d.bosses, "keys": d.keys,
        "failed_twice": d.failed_twice, "hand": d.hand_uses,
        "deaths": d.deaths, "lapses": d.lapses,
    }.get(kind, 0)


def _values(d: Dossier, kind: str, fired: int) -> dict:
    """One dict, complete, so a template can reach for anything it likes and
    `audit` can prove no template reaches for something that is not here."""
    n = _figure_value(d, kind)
    noun = FIGURE_NOUN.get(kind, ("entry", "entries"))
    phrase = _count(n, noun[0], noun[1])
    worst = d.worst()
    attempts = int(worst.get("attempts", 0))
    clears = int(worst.get("clears", 0))
    unaided = int(worst.get("unaided", 0))
    return {
        "n": n, "c": phrase, "ccap": phrase[:1].upper() + phrase[1:],
        "since": d.away_phrase,
        "a": _count(attempts, "attempt"),
        "acap": _count(attempts, "attempt").capitalize(),
        "cl": _count(clears, "finish", "finishes"),
        "clcap": _count(clears, "finish", "finishes").capitalize(),
        "u": _count(unaided, "unaided clear"),
        "ucap": _count(unaided, "unaided clear").capitalize(),
        "uraw": _quantity(unaided),
        "m": int(round(float(worst.get("mastery", 0.0)))),
        "skill": worst.get("name", ""),
        "ord": _ordinal(fired), "ordcap": _ordinal(fired).capitalize(),
    }


def _fmt(template: str, values: dict) -> str:
    return template.format(**values)


# --------------------------------------------------------------------------
# Slot builders — one per move
# --------------------------------------------------------------------------
#
# Each returns a dict of slot values. An EMPTY STRING means "he has nothing true
# to put here", and `_usable` then drops every frame that wanted it rather than
# inventing a number. He does not bluff; it is the only restraint he has that
# costs him anything.

def _slots_mark(d: Dossier, spec: Occasion, detail: dict, fired: int,
                pick) -> dict:
    values = _values(d, "nothing", fired)
    # {n} in a COUNT_LINE is how many times THIS occasion has fired, not a
    # figure out of the record. They are different numbers and they were the
    # same variable for about an hour, which produced "that makes 0".
    values["n"] = fired
    subject = pick(SUBJECT.get(spec.subject, SUBJECT["AMBIENT"]),
                   f"subject:{spec.subject}")
    count = ""
    if fired >= 2:
        count = _fmt(pick(COUNT_LINE, "count"), values)
    return {"subject": subject, "named": _named(spec, detail), "count": count}


# Which column he reaches for, per occasion. A villain who answers a death with
# a key count is reading a file rather than reading a person, and the whole of
# the menace is that he is doing the second thing.
#
# It is a BIAS, not a filter: the preferred kinds are concatenated in front of
# everything he could say, so they come round twice per cycle and the other
# columns still come round. Narrowing it to a filter would buy relevance with
# most of the variety, and he would be quoting the same two numbers by the
# third hour. An occasion absent from this table simply has no preference.
FIGURE_PREFERENCE: dict = {
    "HINT_LEANED": ("hints", "attempts"),
    "FAILED_TWICE": ("failed_twice", "lapses"),
    "HAND_USED": ("hand", "hints"),
    "LONG_ABSENCE": ("away", "lapses"),
    "FIRST_DEATH": ("deaths", "attempts"),
    "DEFEATED": ("deaths", "attempts"),
    "BOSS_FELLED": ("bosses", "unaided"),
    "KEY_TAKEN": ("keys",),
    "PORTAL_OPENED": ("keys", "bosses"),
    "CHAPTER_GRADUATED": ("unaided", "solved"),
    "SEALED_MET": ("solved", "unaided"),
    "DIAGNOSTIC_DONE": ("attempts", "solved"),
    "EXAM_THRESHOLD": ("unaided", "hints"),
    "EXAM_VERDICT": ("unaided", "hints"),
}


def _slots_tally(d: Dossier, spec: Occasion, detail: dict, fired: int,
                 pick) -> dict:
    available = d.figures()
    preferred = tuple(k for k in FIGURE_PREFERENCE.get(spec.id, ())
                      if k in available)
    kinds = preferred + available
    kind = pick(kinds, f"tally:kind:{spec.id}")
    values = _values(d, kind, fired)
    table = TALLY_LOG if REGISTERS[d.register].mood == "LOG" else TALLY_YOU
    pool = table.get(kind) or table["nothing"]
    tally = _fmt(pick(pool, f"tally:{kind}"), values)
    if kind == "away":
        figure = d.away_phrase
    elif kind == "nothing":
        figure = ""
    else:
        figure = values["c"]
    return {"tally": tally, "figure": figure, "since": d.away_phrase}


def _slots_name(d: Dossier, spec: Occasion, detail: dict, fired: int,
                pick) -> dict:
    worst = d.worst()
    if not worst:
        return {"weak": "", "symptom": "", "verdict": ""}
    shape = worst.get("shape", SHALLOW)
    values = _values(d, "nothing", fired)
    return {
        "weak": worst.get("name", ""),
        "symptom": _fmt(pick(SYMPTOM[shape], f"symptom:{shape}"), values),
        "verdict": pick(VERDICT[shape], f"verdict:{shape}"),
    }


def _slots_offer(d: Dossier, spec: Occasion, detail: dict, fired: int,
                 pick) -> dict:
    shape = (d.worst() or {}).get("shape", SHALLOW)
    return {
        "offer": pick(OFFER_LINE[d.register], f"offer:{d.register}"),
        "relief": pick(RELIEF[shape], f"relief:{shape}"),
        "terms": pick(TERMS, "terms"),
    }


def _slots_self(d: Dossier, spec: Occasion, detail: dict, fired: int,
                pick) -> dict:
    pool = SELF_LINE.get(d.register)
    if not pool:
        return {"self": "", "law": ""}
    return {"self": pick(pool, f"self:{d.register}"), "law": pick(LAW, "law")}


BUILDERS: dict = {
    MARK: _slots_mark, TALLY: _slots_tally, NAME: _slots_name,
    OFFER: _slots_offer, SELF: _slots_self,
}


# --------------------------------------------------------------------------
# Eligibility, scoring, rendering
# --------------------------------------------------------------------------

_SLOT_RE = re.compile(r"\{(\w+)\}")


def _slots_in(frame: str) -> set:
    return set(_SLOT_RE.findall(frame))


def _usable(frame: str, slots: dict) -> bool:
    """A frame is eligible when every slot it names has something in it."""
    return all(slots.get(name) for name in _slots_in(frame))


def _frames_for(register: str, move: str, slots: dict) -> tuple:
    pool = FRAMES.get(register, {}).get(move, ())
    return tuple(f for f in pool if _usable(f, slots))


def _score(move: str, register: str, d: Dossier, spec: Occasion) -> int:
    """How much of his attention this move is worth right now.

    OFFER is the odd one and deliberately so: it scores nothing at all from the
    base table and everything from pressure, so the bargain is a response to the
    player's week rather than a rotation slot that comes round on schedule.
    """
    reg = REGISTERS[register]
    if move == OFFER:
        if d.pressure < reg.offer_floor:
            return 0
        # The bargain LEADS when the occasion is itself evidence of a bad
        # week, and is the second thing he says the rest of the time. A
        # villain who opens with the offer at every opportunity is a salesman,
        # and the offer stops being frightening the third time it happens.
        lead = 24 + (d.pressure - reg.offer_floor) // 2
        return lead + (20 if spec.struggle else 0)
    if move == SELF and move not in reg.moves:
        return 0
    base = MOVE_BASE[move] + MOVE_BY_REGISTER[register].get(move, 0)
    if move == MARK:
        base += max(0, spec.weight - 20) // 2
    if move == NAME and spec.struggle:
        base += 12
    if move == TALLY and spec.id in (LONG_ABSENCE, FAILED_TWICE, HINT_LEANED):
        base += 14
    return base


def _candidates(d: Dossier, spec: Occasion, detail: dict, fired: int,
                pick) -> list:
    out = []
    for move in REGISTERS[d.register].moves:
        score = _score(move, d.register, d, spec)
        if score <= 0:
            continue
        slots = BUILDERS[move](d, spec, detail, fired, pick)
        if not _frames_for(d.register, move, slots):
            continue
        out.append({"move": move, "score": score, "slots": slots})
    out.sort(key=lambda c: (-c["score"], MOVES.index(c["move"])))
    return out


def _choose(options: list, floor: int, role: str, pick):
    field = [o for o in options if o["score"] >= floor]
    if not field:
        return None
    if len(field) == 1:
        return field[0]
    moves = [o["move"] for o in field]
    chosen = pick(moves, f"{role}:" + "+".join(sorted(moves)))
    return next(o for o in field if o["move"] == chosen)


_SENTENCE_START = re.compile(r"(^|[.?] )([a-z])")


def _sentence_case(text: str) -> str:
    """Capitalise whatever landed at the start of a sentence.

    The fragment fillings are authored lower-case because most of them arrive
    mid-sentence and a frame cannot know which. Doing it here rather than
    forbidding a frame from opening with a slot is the difference between a
    hundred frames written under a constraint and a hundred frames written the
    way a thing would say them.
    """
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def _render(register: str, move: str, slots: dict, pick) -> str:
    pool = _frames_for(register, move, slots)
    frame = pick(pool, f"frame:{register}:{move}")
    filled = dict.fromkeys(MOVE_SLOTS[move], "")
    filled.update({k: v for k, v in slots.items() if k in MOVE_SLOTS[move]})
    return _sentence_case(re.sub(r"\s+", " ", frame.format(**filled)).strip())


# ==========================================================================
# SECTION 9 — WHO HE IS, TO A CLIENT
# ==========================================================================
#
# No second copy of anything. The name, the sprite and the colour come out of
# world.BOSSES, where the last fight already lives, so the thing watching you
# for eleven chapters and the thing standing in the last room are provably the
# same record and cannot drift into being two characters with one name.

FINAL_BOSS_ID = "the_interviewer"

# What he is called while he is only watching. The boss row calls him The
# Examiner, which is what he is at the end of the road and not what he is
# for the eleven chapters before it; the story bible calls him the Null King
# throughout, so that is the name on the line of text and the boss row is still
# the single source of the sprite, the colour and the identity.
WATCHING_NAME = "THE NULL KING"
WATCHING_EPITHET = "who was NUL-9, the Obliging Engine"


def speaker() -> dict:
    """The portrait, derived. `sprite` and `colour` are world.py's."""
    row = world.BOSS_BY_ID.get(FINAL_BOSS_ID, {})
    return {
        "id": FINAL_BOSS_ID,
        "name": WATCHING_NAME,
        "epithet": WATCHING_EPITHET,
        "final_name": row.get("name", "The Examiner"),
        "sprite": row.get("sprite", "interviewer"),
        "colour": row.get("colour", "#d8d8e0"),
        "region": row.get("region", "null_kings_castle"),
    }


def refusal(capability: str) -> dict:
    """The standard refusal, so his 'no' reads exactly like every other 'no' in
    the game. Reached in Timed Practical Mode and on hold-out content, and nowhere
    else, because those are the only places anything is being measured."""
    return finalexam.refuse(capability)


def occasions() -> list:
    """The trigger table, for a later system that wants to add one."""
    return [{"id": o.id, "label": o.label, "subject": o.subject,
             "capability": o.capability, "weight": o.weight,
             "struggle": o.struggle, "proper": o.proper, "once": o.once,
             "staged": o.staged, "lines_authored": len(SUBJECT.get(o.subject, ()))}
            for o in OCCASIONS.values()]


def vocabulary() -> dict:
    """What he is allowed to name, what each move is for, and how each slot
    behaves. For a design review, and checked by `audit` rather than asserted."""
    return {
        "speakable": list(SPEAKABLE),
        "moves": {move: MOVE_BLURB[move] for move in MOVES},
        "slots": {
            "sentence": sorted(SENTENCE_SLOTS),
            "fragment": sorted(FRAGMENT_SLOTS),
            "proper": sorted(PROPER_SLOTS),
        },
    }


def codex() -> list:
    """The five registers and the curve, for a design review."""
    return [{"id": r.id, "label": r.label, "floor": r.floor, "voice": r.voice,
             "tell": r.tell, "mood": r.mood, "second_person": r.second_person,
             "first_person": r.first_person, "asks": r.asks,
             "max_words": r.max_words, "offer_floor": r.offer_floor,
             "moves": list(r.moves), "presence": r.presence, "ms": r.ms,
             "frames": sum(len(p) for p in FRAMES[r.id].values())}
            for r in (REGISTERS[rid] for rid in REGISTER_IDS)]


def fired_count(state: dict | None, occasion: str) -> int:
    """How many times this occasion has fired for this player."""
    block = _mapping(_mapping(state).get(STATE_KEY))
    return int((block.get("fired") or {}).get(occasion, 0) or 0)


def speak(occasion: str, state: dict | None = None, *, skills=None,
          detail: dict | None = None, encounter=None,
          record: Dossier | None = None, rng=None, now: float | None = None,
          tail: bool = True) -> dict:
    """What he says about this, NOW. The one entry point.

    `occasion` is a key of OCCASIONS. `state` is engine.Game.state; `skills` is
    engine.Game.skills or nothing. `detail` carries the occasion's proper noun
    — {"boss": "hash_titan"}, {"region": "graph_wastes"}, {"chapter": "ch_05"}
    — and is ignored for occasions that declare none.

    `record` lets a caller build the Dossier once and hand the same one to
    several calls on one screen, exactly as banter.Ctx is handed to every
    speaker in a room. Without it, one is read per call, which is cheap and
    correct and only wasteful in a loop.

    IT NEVER BLOCKS. The payload carries `blocking: False` as a literal because
    a client reading this contract should never have to wonder, and there is no
    branch anywhere below that sets it otherwise. He is weather.
    """
    spec = OCCASIONS.get(occasion)
    if spec is None:
        return {"error": "no such occasion", "occasion": occasion,
                "blocking": False, "lines": []}

    # THE ONE CAPABILITY CHECK. In a measured run finalexam.EXAM_SEAL seals
    # every crutch in the game, so every occasion in the table is sealed —
    # including the two the practical stages, which is correct, because the
    # practical stages him at the threshold and at the verdict and both of those
    # are called with no live encounter. There is no path by which he speaks
    # into a measurement.
    if finalexam.sealed(encounter, spec.capability):
        return {"occasion": occasion, "label": spec.label, "lines": [],
                "moves": [], "blocking": False, "sealed": True,
                "speaker": speaker(), **refusal(spec.capability)}

    # A non-mapping `state` simply means there is nowhere to keep his memory,
    # not that the call fails. `dossier` already reads any save shape through
    # `_mapping`; this is the same rule at the other entry point, because a
    # module that is total in one of them and not the other is how the
    # /api/antagonist crash got in.
    block = None
    if isinstance(state, dict):
        block = state.setdefault(STATE_KEY, new_state())
    d = record if record is not None else dossier(state, skills, now=now)

    fired = fired_count(state, occasion) + 1
    marks = _marks(block)

    def pick_into(target):
        def pick(pool, pool_key):
            return _pick(pool, pool_key=pool_key, marks=target, rng=rng,
                         salt=occasion)
        return pick

    # Probe on a COPY of the memory, exactly as banter does: scoring has to
    # build the slots for every move to find out which ones he has something
    # true for, and a filling spent on a move that is then not spoken is a
    # sentence nobody heard.
    probe = pick_into(list(marks))
    pick = pick_into(marks)

    options = _candidates(d, spec, detail or {}, fired, probe)
    if not options:                             # pragma: no cover - MARK is total
        return {"occasion": occasion, "label": spec.label, "lines": [],
                "moves": [], "blocking": False, "sealed": False,
                "speaker": speaker()}

    lead = _choose(options, options[0]["score"] - LEAD_SPREAD, "lead", pick)
    chosen = [lead]
    if tail:
        rest = [o for o in options if o["move"] != lead["move"]]
        second = _choose(rest, TAIL_FLOOR, "tail", pick)
        if second is not None:
            chosen.append(second)

    lines, moves = [], []
    for option in chosen:
        slots = BUILDERS[option["move"]](d, spec, detail or {}, fired, pick)
        if not _frames_for(d.register, option["move"], slots):
            slots = option["slots"]             # pragma: no cover - defensive
        lines.append(_render(d.register, option["move"], slots, pick))
        moves.append(option["move"])

    reg = REGISTERS[d.register]
    if block is not None:
        block.setdefault("fired", {})[occasion] = fired
        block["register"] = d.register
        block["last_at"] = float(d.now)
        if OFFER in moves:
            block["offers"] = int(block.get("offers", 0) or 0) + 1

    return {
        "occasion": occasion, "label": spec.label,
        "speaker": speaker(),
        "register": d.register, "register_label": reg.label,
        "standing": d.standing, "pressure": d.pressure,
        "lines": lines, "moves": moves,
        "bargain": OFFER in moves,
        "first_time": fired == 1, "times": fired,
        "named": _named(spec, detail or {}),
        # How the client draws him. He is weather: a line of text and, later, a
        # portrait, for `ms` milliseconds, over whatever is already on screen.
        "presence": reg.presence, "ms": reg.ms,
        "blocking": False, "sealed": False,
    }


def view(state: dict | None = None, skills=None, *, occasion: str = AMBIENT,
         detail: dict | None = None, encounter=None, rng=None,
         now: float | None = None) -> dict:
    """Everything one screen needs, in one call.

    The same payload `speak` returns, plus the curve, so a client can draw a
    HUD that shows how much of his attention the player has earned without
    asking a second question.
    """
    d = dossier(state, skills, now=now)
    said = speak(occasion, state, skills=skills, detail=detail,
                 encounter=encounter, record=d, rng=rng, now=now)
    said["curve"] = {
        "standing": d.standing, "pressure": d.pressure,
        "register": d.register,
        "registers": [{"id": rid, "floor": REGISTERS[rid].floor,
                       "label": REGISTERS[rid].label} for rid in REGISTER_IDS],
        "weakest": [w["skill"] for w in d.weak],
        "offer_floor": REGISTERS[d.register].offer_floor,
    }
    return said


def herald(state: dict | None = None, skills=None, *,
           now: float | None = None) -> dict:
    """Where he stands, without making him speak. For a pause screen."""
    d = dossier(state, skills, now=now)
    reg = REGISTERS[d.register]
    return {"speaker": speaker(), "register": d.register, "label": reg.label,
            "tell": reg.tell, "standing": d.standing, "pressure": d.pressure,
            "weakest": [w["skill"] for w in d.weak], "blocking": False}


# ==========================================================================
# SECTION 10 — COUNTS, CAPACITY AND PROOF
# ==========================================================================
#
# Everything a reviewer would otherwise have to take on trust, measured rather
# than asserted. `self_check()["ok"]` is the one boolean a test should assert.

_SECOND_PERSON = re.compile(r"\b(?:you|your|yours|yourself)\b", re.IGNORECASE)
_FIRST_PERSON = re.compile(r"(?:\bI\b|\bI'|\bmy\b|\bmine\b|\bme\b|\bmyself\b)")


def _bare(frame: str) -> str:
    """A frame with its slots removed: his own words and nothing borrowed."""
    return _SLOT_RE.sub(" ", frame)


def _sentences(text: str) -> list:
    return [part.strip() for part in re.split(r"(?<=[.?])\s+", text or "")
            if part.strip()]


def _frame_lengths(frame: str) -> list:
    """Words per authored sentence, slots excluded.

    The cap governs the FRAMES, which are the voice. A filling shared between
    registers cannot shorten just because he did, and pretending otherwise
    would make the measurement flatter than the writing.
    """
    return [len([w for w in re.findall(r"[A-Za-z']+", part)])
            for part in _sentences(_bare(frame))
            if re.search(r"[A-Za-z]", part)]


def _saturated(register: str, shape: str = GRINDING) -> Dossier:
    """A record with every column full at once.

    Deliberately impossible — nobody is simultaneously a fortnight absent, four
    hundred hints deep and holding fourteen keys — because the audit's job is to
    reach every slot of every frame rather than to be plausible.
    """
    d = Dossier(
        bosses=9, keys=9, chapters=6, regions=12, solved=412,
        clears=180, unaided=64, attempts=460, mastery=54.0,
        hints=406, hint_lean=0.62, hand_uses=2, probes=30,
        deaths=5, failed_twice=4, lapses=3, perf_failed=2,
        away=86400 * 12, away_phrase=_span(86400 * 12),
        playtime=3600 * 40, sessions=22,
        weak=({"skill": "DP", "name": SKILL_NAME["DP"], "shape": shape,
               "mastery": 18.0, "attempts": 22, "clears": 9, "unaided": 1,
               "retention": 12.0, "hint_dependence": 0.7, "last_seen": 1.0,
               "stage": "ASSISTED"},),
        now=86400 * 400,
    )
    d.register = register
    d.standing = REGISTERS[register].floor
    d.pressure = 100
    return d


def _empty(register: str) -> Dossier:
    """The other extreme: a save with nothing in it at all. This is the one
    that proves he never dead-ends, because it is the one where he knows
    nothing about the player and still has to say something."""
    d = Dossier(now=1.0)
    d.register = register
    d.standing = REGISTERS[register].floor
    d.pressure = 0
    return d


def capacity(occasion: str = AMBIENT, register: str = PRECISE, *,
             limit: int = 600) -> dict:
    """How many distinct things he can say about one occasion before repeating.

    MEASURED, not estimated. The composer is run against one frozen record with
    a throwaway memory until a line comes round again, which is the brief's
    question asked literally.

    The number is a FLOOR on what a player experiences rather than a ceiling: it
    holds the situation still, and in a real game the register, the weakness,
    the figures and the pressure all move underneath the same frames.
    """
    record = _saturated(register)
    memory = {STATE_KEY: new_state()}
    seen: dict = {}
    first_repeat = 0
    for turn in range(1, limit + 1):
        said = speak(occasion, memory, record=record,
                     detail=_AUDIT_DETAIL.get(OCCASIONS[occasion].proper, {}))
        key = " ".join(said.get("lines", ()))
        if key in seen and not first_repeat:
            first_repeat = turn
        seen.setdefault(key, turn)
    return {"occasion": occasion, "register": register,
            "distinct": (first_repeat - 1) if first_repeat else len(seen),
            "first_repeat_at": first_repeat,
            "distinct_in_full_walk": len(seen), "walk": limit,
            "limit_hit": first_repeat == 0}


# Proper nouns the audit hands in, one per `proper` key, all of them real ids
# out of the modules that own them.
def _first_id(rows, attr: str = "id") -> str:
    for row in rows or ():
        if isinstance(row, dict):
            return str(row.get(attr, ""))
        return str(getattr(row, attr, ""))
    return ""


_AUDIT_DETAIL: dict = {
    "": {},
    "boss": {"boss": _first_id(world.BOSSES)},
    "region": {"region": _first_id(world.REGIONS)},
    "key": {"key": _first_id(getattr(world, "KEYS", ()))},
    "chapter": {"chapter": curriculum.CHAPTERS[0].id if curriculum.CHAPTERS else ""},
    "apex": {"apex": _first_id(getattr(_hunters, "APEXES", ()) if _hunters else ())},
    "sage": {"sage": _first_id(getattr(_sages, "SAGES", ()) if _sages else ())},
}


def counts() -> dict:
    """Content census. Cheap enough to print in a test failure message."""
    frames = sum(len(pool) for beats in FRAMES.values()
                 for pool in beats.values())
    fillings = (sum(len(v) for v in SUBJECT.values())
                + len(COUNT_LINE)
                + sum(len(v) for v in TALLY_LOG.values())
                + sum(len(v) for v in TALLY_YOU.values())
                + sum(len(v) for v in SYMPTOM.values())
                + sum(len(v) for v in VERDICT.values())
                + sum(len(v) for v in OFFER_LINE.values())
                + sum(len(v) for v in RELIEF.values())
                + len(TERMS)
                + sum(len(v) for v in SELF_LINE.values())
                + len(LAW))
    return {
        "occasions": len(OCCASIONS),
        "staged_by_finalexam": len(STAGED_BY_FINALEXAM),
        "struggle_occasions": len(STRUGGLE),
        "registers": len(REGISTERS),
        "moves": len(MOVES),
        "frames": frames,
        "frames_per_register": {rid: sum(len(p) for p in FRAMES[rid].values())
                                for rid in REGISTER_IDS},
        "fillings": fillings,
        "subject_lines": sum(len(v) for v in SUBJECT.values()),
        "figure_kinds": len(TALLY_YOU),
        "weakness_shapes": len(SHAPES),
        "skills_named": len(SKILL_NAME),
        "authored_strings": sum(1 for _ in _authored_text()),
    }


def _authored_text():
    """Every player-visible string this module owns, labelled for the report."""
    for occasion_id, pool in SUBJECT.items():
        for line in pool:
            yield f"subject:{occasion_id}", line
    for line in COUNT_LINE:
        yield "count", line
    for name, table in (("tally_log", TALLY_LOG), ("tally_you", TALLY_YOU),
                        ("symptom", SYMPTOM), ("verdict", VERDICT),
                        ("offer", OFFER_LINE), ("relief", RELIEF),
                        ("self", SELF_LINE)):
        for key, pool in table.items():
            for line in pool:
                yield f"{name}:{key}", line
    for line in TERMS:
        yield "terms", line
    for line in LAW:
        yield "law", line
    for rid, moves in FRAMES.items():
        for move, pool in moves.items():
            for line in pool:
                yield f"frame:{rid}:{move}", line
    for rid, reg in REGISTERS.items():
        yield f"register:{rid}", reg.label
        yield f"register:{rid}", reg.voice
        yield f"register:{rid}", reg.tell
    for spec in OCCASIONS.values():
        yield f"occasion:{spec.id}", spec.label
    yield "name", WATCHING_NAME
    yield "name", WATCHING_EPITHET
    for name in SKILL_NAME.values():
        yield "skill_name", name


def audit() -> dict:
    """The proof. Ten things, every one of them a rule stated earlier in the file.

    1.  THE ANSWER LINE and THE FIX LINE, over authored text AND over every line
        the composer can emit from a saturated record, because a frame can only
        leak through a slot.
    2.  Tone: no exclamation marks anywhere, ever.
    3.  Slot discipline: no frame reaches for a slot its move does not define,
        every frame reads at least one, and no composed line ships an unfilled
        brace or opens a sentence in lower case.
    4.  Filling discipline: sentence slots carry finished sentences, fragment
        slots carry lower-case phrases.
    5.  Referential integrity: every id this module names exists in the module
        that owns it, and every occasion's capability is a real crutch.
    6.  Coverage: every occasion has subject prose, every register has frames
        for every move it claims, every skill has a name he can say.
    7.  THE CURVE: the person rules hold over every COMPOSED line — no second
        person before NOTICED, no first person before PRECISE, no question
        before ATTENTIVE — and his authored sentences shorten monotonically.
    8.  NO DEAD ENDS: every occasion, in every register, with an EMPTY record,
        produces a line.
    9.  THE SEAL: every occasion produces nothing in a measured run.
    10. HE IS NEVER IN THE WAY: every payload he can emit says blocking: False.
    """
    problems: dict = {
        "answerish": [], "fixish": [], "tone": [], "slots": [], "fillings": [],
        "unknown_ids": [], "coverage": [], "curve": [], "dead_ends": [],
        "seal": [], "blocking": [],
    }

    # -- 1 + 2. authored text ----------------------------------------------
    for label, line in _authored_text():
        for token in names_a_construct(line):
            problems["answerish"].append(f"{label}: {token!r}")
        for token in names_a_fix(line):
            problems["fixish"].append(f"{label}: {token!r}")
        if "!" in (line or ""):
            problems["tone"].append(f"{label}: exclamation mark")

    # -- 3. slot discipline -------------------------------------------------
    for rid, moves in FRAMES.items():
        for move, pool in moves.items():
            allowed = set(MOVE_SLOTS[move])
            for frame in pool:
                used = _slots_in(frame)
                stray = used - allowed
                if stray:
                    problems["slots"].append(
                        f"frame:{rid}:{move}: unknown slot(s) {sorted(stray)}")
                if not used:
                    problems["slots"].append(
                        f"frame:{rid}:{move}: reads no state at all")

    # -- 4. filling discipline ---------------------------------------------
    def _check_sentence(label, line):
        if not line:
            return
        if line[:1].isalpha() and not line[:1].isupper():
            problems["fillings"].append(f"{label}: sentence starts lower case")
        if line[-1:] not in (".", "?"):
            problems["fillings"].append(f"{label}: sentence does not close")

    for label, pool in (("subject", [l for p in SUBJECT.values() for l in p]),
                        ("count", list(COUNT_LINE)),
                        ("terms", list(TERMS)), ("law", list(LAW))):
        for line in pool:
            _check_sentence(label, line)
    for table_name, table in (("tally_log", TALLY_LOG), ("tally_you", TALLY_YOU),
                              ("symptom", SYMPTOM), ("verdict", VERDICT),
                              ("offer", OFFER_LINE), ("relief", RELIEF),
                              ("self", SELF_LINE)):
        for key, pool in table.items():
            for line in pool:
                _check_sentence(f"{table_name}:{key}", line)
    for skill, name in SKILL_NAME.items():
        if name[:1].isupper():
            problems["fillings"].append(
                f"skill_name:{skill}: fragment is capitalised")

    # -- 4b. every slot is classified exactly once -------------------------
    classes = (SENTENCE_SLOTS, FRAGMENT_SLOTS, PROPER_SLOTS)
    for move, slots in MOVE_SLOTS.items():
        for slot in slots:
            hits = sum(1 for group in classes if slot in group)
            if hits != 1:
                problems["fillings"].append(
                    f"slot {slot!r} of {move} is in {hits} classes, wants 1")
    for group in classes:
        for slot in group:
            if not any(slot in slots for slots in MOVE_SLOTS.values()):
                problems["fillings"].append(f"slot {slot!r} belongs to no move")
    for move in MOVES:
        if move not in MOVE_BLURB or move not in MOVE_SLOTS:
            problems["coverage"].append(f"move {move} is not described")

    # -- 5. referential integrity ------------------------------------------
    for spec in OCCASIONS.values():
        if spec.capability not in finalexam.ALL_CRUTCHES:
            problems["unknown_ids"].append(
                f"occasion {spec.id!r}: {spec.capability!r} is not a crutch")
        if spec.proper and spec.proper not in _AUDIT_DETAIL:
            problems["unknown_ids"].append(
                f"occasion {spec.id!r}: no audit noun for {spec.proper!r}")
    for occasion_id, kinds in FIGURE_PREFERENCE.items():
        if occasion_id not in OCCASIONS:
            problems["unknown_ids"].append(
                f"FIGURE_PREFERENCE: unknown occasion {occasion_id!r}")
        for kind in kinds:
            if kind != "away" and kind not in TALLY_YOU:
                problems["unknown_ids"].append(
                    f"FIGURE_PREFERENCE[{occasion_id}]: unknown column {kind!r}")
    for kind in TALLY_YOU:
        if kind not in TALLY_LOG:
            problems["coverage"].append(f"column {kind!r} has no log mood")
    if FINAL_BOSS_ID not in world.BOSS_BY_ID:
        problems["unknown_ids"].append(
            f"{FINAL_BOSS_ID!r} is not in world.BOSSES")
    for skill in SKILL_NAME:
        if skill not in skills_mod.SKILLS:
            problems["unknown_ids"].append(f"SKILL_NAME: unknown skill {skill!r}")
    for rid in FRAMES:
        if rid not in REGISTERS:
            problems["unknown_ids"].append(f"FRAMES: unknown register {rid!r}")
    staged = tuple(o.id for o in OCCASIONS.values() if o.staged)
    if staged != tuple(STAGED_BY_FINALEXAM):
        problems["unknown_ids"].append(
            f"STAGED_BY_FINALEXAM says {list(STAGED_BY_FINALEXAM)}, "
            f"the table says {list(staged)}")

    # -- 6. coverage --------------------------------------------------------
    for spec in OCCASIONS.values():
        pool = SUBJECT.get(spec.subject, ())
        if len(pool) < 4:
            problems["coverage"].append(
                f"occasion {spec.id!r} has {len(pool)} subject lines, wants 4")
    for rid in REGISTER_IDS:
        reg = REGISTERS[rid]
        for move in reg.moves:
            pool = FRAMES.get(rid, {}).get(move, ())
            if len(pool) < 4:
                problems["coverage"].append(
                    f"register {rid!r} move {move} has {len(pool)} frames")
        for move in FRAMES.get(rid, {}):
            if move not in reg.moves:
                problems["coverage"].append(
                    f"register {rid!r} has frames for {move}, which is not its move")
    for skill in skills_mod.SKILLS:
        if skill not in SKILL_NAME:
            problems["coverage"].append(f"skill {skill!r} has no name he can say")
    for shape in SHAPES:
        for table_name, table in (("SYMPTOM", SYMPTOM), ("VERDICT", VERDICT),
                                  ("RELIEF", RELIEF)):
            if shape not in table:
                problems["coverage"].append(f"{table_name} has no {shape}")
    for rid in REGISTER_IDS:
        if rid not in OFFER_LINE:
            problems["coverage"].append(f"register {rid!r} has no bargain")
    for rid, reg in REGISTERS.items():
        if SELF in reg.moves and rid not in SELF_LINE:
            problems["coverage"].append(f"register {rid!r} claims SELF and has none")

    # -- 7b. the shortening, over authored frames ---------------------------
    means = []
    for rid in REGISTER_IDS:
        reg = REGISTERS[rid]
        lengths = [n for move in FRAMES[rid].values() for frame in move
                   for n in _frame_lengths(frame)]
        over = [n for n in lengths if n > reg.max_words]
        if over:
            problems["curve"].append(
                f"register {rid!r} has {len(over)} sentence(s) over "
                f"{reg.max_words} words, longest {max(over)}")
        means.append(round(sum(lengths) / max(1, len(lengths)), 2))
    for i in range(1, len(means)):
        if means[i] >= means[i - 1]:
            problems["curve"].append(
                f"he does not shorten from {REGISTER_IDS[i - 1]} ({means[i - 1]}) "
                f"to {REGISTER_IDS[i]} ({means[i]})")

    # -- 1b + 3b + 7a + 8 + 10. the composer, walked ------------------------
    emitted = 0
    for rid in REGISTER_IDS:
        reg = REGISTERS[rid]
        for occasion_id, spec in OCCASIONS.items():
            detail = _AUDIT_DETAIL.get(spec.proper, {})
            # THE SATURATED PASS: everything he could possibly know, which is
            # how every slot of every frame gets reached.
            for shape in SHAPES:
                memory = {STATE_KEY: new_state()}
                record = _saturated(rid, shape)
                for _ in range(len(MOVES) * 6):
                    said = speak(occasion_id, memory, record=record,
                                 detail=detail)
                    if said.get("blocking") is not False:
                        problems["blocking"].append(
                            f"{rid}/{occasion_id}: blocking is not False")
                    lines = said.get("lines") or []
                    if not lines:
                        problems["dead_ends"].append(
                            f"{rid}/{occasion_id}/{shape}: said nothing")
                        break
                    for line in lines:
                        emitted += 1
                        if "{" in line or "}" in line:
                            problems["slots"].append(
                                f"{rid}/{occasion_id}: unfilled slot in "
                                f"{line[:60]!r}")
                        if _SENTENCE_START.search(line):
                            problems["slots"].append(
                                f"{rid}/{occasion_id}: lower-case sentence in "
                                f"{line[:60]!r}")
                        if "!" in line:
                            problems["tone"].append(
                                f"{rid}/{occasion_id}: exclamation mark")
                        for token in names_a_construct(line, strict=False):
                            problems["answerish"].append(
                                f"composed {rid}/{occasion_id}: {token!r}")
                        for token in names_a_fix(line):
                            problems["fixish"].append(
                                f"composed {rid}/{occasion_id}: {token!r}")
                        if not reg.second_person and _SECOND_PERSON.search(line):
                            problems["curve"].append(
                                f"{rid} said 'you': {line[:60]!r}")
                        if not reg.first_person and _FIRST_PERSON.search(line):
                            problems["curve"].append(
                                f"{rid} said 'I': {line[:60]!r}")
                        if not reg.asks and "?" in line:
                            problems["curve"].append(
                                f"{rid} asked a question: {line[:60]!r}")
            # THE EMPTY PASS: a blank save, which is where a villain with a
            # dossier normally runs out of things to say and stalls the screen.
            memory = {STATE_KEY: new_state()}
            for _ in range(6):
                said = speak(occasion_id, memory, record=_empty(rid),
                             detail=detail)
                if not said.get("lines"):
                    problems["dead_ends"].append(
                        f"{rid}/{occasion_id}: nothing to say on an empty save")
                    break
                emitted += len(said["lines"])

    # -- 9. the seal --------------------------------------------------------
    class _Measured:
        mode = finalexam.EXAM_MODE
        boss_id = ""
        holdout = False

    for occasion_id in OCCASIONS:
        said = speak(occasion_id, None, record=_saturated(UNQUIET),
                     encounter=_Measured())
        if not said.get("sealed") or said.get("lines"):
            problems["seal"].append(f"{occasion_id} spoke inside a measured run")
        if said.get("blocking") is not False:
            problems["blocking"].append(f"{occasion_id}: sealed payload blocks")

    problems = {k: sorted(dict.fromkeys(v))[:20] for k, v in problems.items()}
    problems["lines_audited"] = emitted
    problems["sentence_means"] = means
    return problems


def self_check() -> dict:
    """Counts, capacity and the proofs. Safe from a test or from the CLI."""
    report_ = audit()
    census = counts()

    caps = []
    for occasion_id in OCCASIONS:
        for rid in REGISTER_IDS:
            caps.append(capacity(occasion_id, rid))
    numbers = sorted(c["distinct"] for c in caps)
    quietest = min(caps, key=lambda c: c["distinct"])

    problems = {k: v for k, v in report_.items()
                if k not in ("lines_audited", "sentence_means") and v}
    return {
        "counts": census,
        "capacity": {
            "min": numbers[0], "median": numbers[len(numbers) // 2],
            "max": numbers[-1],
            "total_distinct_remarks": sum(numbers),
            "quietest": f"{quietest['occasion']}/{quietest['register']}",
            "walk": caps[0]["walk"],
            "walk_min": min(c["distinct_in_full_walk"] for c in caps),
            "walk_max": max(c["distinct_in_full_walk"] for c in caps),
            "measured_over": len(caps),
        },
        "curve": {"sentence_means": report_["sentence_means"],
                  "registers": list(REGISTER_IDS),
                  "floors": [REGISTERS[r].floor for r in REGISTER_IDS],
                  "offer_floors": [REGISTERS[r].offer_floor
                                   for r in REGISTER_IDS]},
        "lines_audited": report_["lines_audited"],
        "problems": problems,
        "ok": not problems,
    }


def report() -> str:
    """One page, for a test failure or a terminal."""
    check = self_check()
    census = check["counts"]
    cap = check["capacity"]
    out = [
        f"antagonist: {census['occasions']} occasions, "
        f"{census['registers']} registers, {census['moves']} moves",
        f"  {census['frames']} authored frames, {census['fillings']} fillings, "
        f"{census['authored_strings']} authored strings in total",
        f"  distinct remarks before any repeat, over {cap['measured_over']} "
        f"occasion/register pairs: min {cap['min']}, median {cap['median']}, "
        f"max {cap['max']} (quietest: {cap['quietest']})",
        f"  distinct remarks over {cap['walk']} turns of one frozen record: "
        f"min {cap['walk_min']}, max {cap['walk_max']}",
        f"  sentence length by register "
        f"{list(zip(check['curve']['registers'], check['curve']['sentence_means']))}",
        f"  {check['lines_audited']} composed lines audited against the answer "
        f"line, the fix line and the curve",
        f"  silent in a measured run: {'seal' not in check['problems']}",
    ]
    for key, rows in check["problems"].items():
        out.append(f"  PROBLEM {key}: {len(rows)}")
        out += [f"    {row}" for row in rows[:5]]
    return "\n".join(out)




# ==========================================================================
# SECTION 11 — THE CONTRACT
# ==========================================================================

WIRING = """
WIRING gauntlet/antagonist.py — the integration contract. Nothing here is
optional and nothing here is a guess.

1. SAVE STATE
   engine.DEFAULT_STATE gains one key:

       antagonist.STATE_KEY: antagonist.new_state()      # -> "antagonist"

   It holds {"said": [...], "fired": {...}, "register": str, "offers": int,
   "last_at": float}. Plain JSON, round-trips through db.save_state untouched,
   forward-filled by engine._merge for existing saves. It is BOOKKEEPING, NOT
   EVIDENCE: a save that loses it loses variety for one session and nothing
   else. No mastery, no reward and no gate reads it.

2. THE ONE CALL

       said = antagonist.speak(antagonist.BOSS_FELLED, self.state,
                               skills=self.skills,
                               detail={"boss": enc.boss_id},
                               encounter=self.encounter)

   Returns, always:

       {occasion, label, speaker: {...}, register, register_label,
        standing, pressure,                 # 0-100, for a HUD
        lines: [str, ...],                  # one or two, already sentence-cased
        moves: ["MARK", "TALLY"],           # which questions he answered
        bargain: bool,                      # the Obliging Hand was offered
        first_time: bool, times: int,       # how often this occasion has fired
        named: str,                         # the proper noun, or ""
        presence: str, ms: int,             # how and how long to draw him
        blocking: False, sealed: False}

   `lines` is the whole of the player-facing output. Plain text, never markup,
   never empty outside a measured run.

   Pass `skills=self.skills` when you have it. Without it the record is read
   from state["skills"], which is the same numbers one conversion later.

   Pass `encounter=self.encounter` ALWAYS. It is the seal, and it is the only
   capability check in the file.

3. ONE READ PER SCREEN
   If several occasions fire in one payload, build the record once:

       d = antagonist.dossier(self.state, self.skills)
       a = antagonist.speak(..., record=d)
       b = antagonist.speak(..., record=d)

   or he will disagree with himself about how long you were gone.

4. THE CALL SITES, NAMED EXACTLY
   Every one is a single line, none of them is load-bearing, and skipping any
   one of them costs a remark and nothing else.

     engine.Game._resolve_boss, inside `if solved:`, after the
       cleared_bosses append          -> BOSS_FELLED, detail={"boss": enc.boss_id}
                                         then KEY_TAKEN, detail={"key": key_id}
                                         for the key that boss was holding
     engine.Game.move, where story.note_region returns True
                                      -> REGION_ENTERED, detail={"region": rid}
     wherever stats["chapters_graduated"] is incremented (the engine already
       emits story's "chapter_graduated" event there)
                                      -> CHAPTER_GRADUATED, detail={"chapter": id}
     engine.Game.run_diagnostic, after state["diagnostic"] is written
                                      -> DIAGNOSTIC_DONE
     engine.Game._resolve_apex, where block["kills"][apex_id] is incremented
                                      -> APEX_KILLED, detail={"apex": apex_id}
     wherever sages.meet(...) returns True
                                      -> SAGE_FOUND, detail={"sage": sage_id}
     engine.Game.start_encounter, the first time corpus.is_sealed(problem)
                                      -> SEALED_MET
     wherever the player is defeated  -> FIRST_DEATH the first time,
                                         DEFEATED afterwards. This module counts
                                         the firings; the caller does not have
                                         to know which it is, but must choose
                                         the id — `fired_count(state, FIRST_DEATH)`
                                         answers it in one call
     engine.Game.use_hint, when the rung taken is the third or higher
                                      -> HINT_LEANED
     wherever the Obliging Hand resolves an encounter (legendaries.py)
                                      -> HAND_USED
     engine.Game.submit, when a skill's attempts exceed its clears by two
                                      -> FAILED_TWICE
     session start, when antagonist.dossier(state).away is a week or more
                                      -> LONG_ABSENCE
     wherever len(world.keys_held(cleared)) first reaches len(world.KEYS)
                                      -> PORTAL_OPENED
     finalexam's own flow, as the player steps up, encounter=None
                                      -> EXAM_THRESHOLD
     finalexam's own flow, once the practical is scored, encounter=None
                                      -> EXAM_VERDICT
     a town or overworld screen with nothing else to report
                                      -> AMBIENT

5. SERVER ROUTE
   One GET is enough, and it is a read plus a small write:

       GET /api/antagonist  -> antagonist.view(game.state, game.skills,
                                               encounter=game.encounter)

   Save afterwards, because `view` advances the rotation. `view` is `speak`
   plus a `curve` block — standing, pressure, the five registers and their
   floors, the weakest skills, the current offer floor — which is everything a
   HUD needs without a second question.

   antagonist.herald(state, skills) is the same standing without making him
   speak. Use it for a pause screen.

6. WHAT THE CLIENT MUST RENDER, AND WHAT IT MUST NOT
   RENDER: `lines`, in order, over whatever is already on screen, for `ms`
   milliseconds, in the manner `presence` describes — a band of text at
   UNCOUNTED, a silhouette at NOTICED, a quarter portrait at PRECISE, a half
   portrait at ATTENTIVE, a full centred portrait at UNQUIET. `speaker.sprite`
   and `speaker.colour` come out of world.BOSSES and are the same sprite the
   last fight uses.

   MUST NOT: block input, pause the loop, require a dismissal, queue behind
   another modal, or delay a transition. `blocking` is False in every payload
   this module can produce and `audit` proves it. If two occasions fire at once,
   render them in sequence or drop the second — dropping it costs nothing,
   because nothing downstream reads what he said.

7. THE SEAL
   One capability check and it is finalexam.sealed. Every occasion declares a
   crutch in Occasion.capability; in Timed Practical Mode finalexam.EXAM_SEAL seals
   all of them, so `speak` returns finalexam.refuse's standard
   {"error": "sealed"} payload with `sealed: True` and no lines. That covers
   the measurement and hold-out content, which is the rule.

   THE FINAL PRACTICAL IS NOT AN EXCEPTION TO THIS. finalexam stages him at
   EXAM_THRESHOLD and EXAM_VERDICT, both OUTSIDE the graded window and both
   with encounter=None. There is no branch that lets him speak into a
   measurement and there is no capability that would allow one.

8. WHAT THIS MODULE WILL NEVER DO
   It will not name a Python construct and it will not name a remedy.
   antagonist.names_a_construct(text) is banter.py's guard, imported;
   antagonist.names_a_fix(text) is this module's own; antagonist.audit() runs
   both over every authored string and over every line the composer can emit
   from five registers times nineteen occasions times five weakness shapes; and
   antagonist.self_check()["ok"] is the one boolean a test should assert.
   Any caller that concatenates onto one of his lines should put the result
   through antagonist.clean(text), which is both guards in one call.
   antagonist.vocabulary() states what he is allowed to name, what each move is
   for and how each slot behaves; antagonist.codex() is the five registers and
   the curve; antagonist.occasions() is the trigger table.

9. ADDING AN OCCASION
   Three lines in Section 2 and five sentences in SUBJECT. No frame moves, no
   prose is edited, and `audit` fails if the five sentences are missing. If the
   new occasion carries a proper noun, add its key to Occasion.proper, one
   branch to `_named`, and one entry to `_AUDIT_DETAIL`.

10. OPTIONAL NEIGHBOURS
   hunters.py and sages.py are imported if present and reached only through
   getattr. Without them, APEX_KILLED and SAGE_FOUND still fire and still speak;
   they simply do not get a proper noun, and the frames that wanted one are not
   eligible. No frame changes either way.
"""


CONTRACT = """
What antagonist.py needs from files it does not own, stated precisely so nobody
has to guess.

NOTHING NEW. Not one reward, not one gate, not one new payload shape. He is a
read of the save and two lines of text. Every engine call site in WIRING §4 is
one statement that can be deleted without breaking anything else.

WHAT IT READS, and where each number comes from:

  state["cleared_bosses"]          bosses down, and world.keys_held for keys
  state["skills"] (or Game.skills) mastery, attempts, clears, unaided_clears,
                                   hint_dependence, retention, last_seen
  state["stats"]                   hints_total, chapters_graduated, sessions,
                                   probes, and "deaths" if that key ever exists
  state["solved_ids"]              how many problems are closed
  state["schedule"]                spaced-repetition lapses
  state["hand"]                    legendaries.hand_ledger_new()["uses"]
  state["story"]["regions_entered"] how much of the map has been stood on
  state["perf_failed_ids"]         read, currently unused by any line
  state["player"]["playtime_seconds"]

  EVERY ONE of those is read with a default. A missing key is a sentence he
  does not say, never an exception, because a villain that raises inside a
  result payload is a villain somebody wraps in a try block and then deletes.

WHAT IT WRITES: state["antagonist"], and nothing else, ever. No mastery, no
gold, no flags another system reads. `audit` does not have to prove this
because there is no other assignment in the file.

WHERE THE NUMBERS COME FROM, so nobody re-tunes them here by mistake:

  standing   STANDING_WEIGHTS, and every term in it is graded evidence: bosses,
             keys, chapters, unaided clears, median mastery. Hours played is
             deliberately not a term. He does not respect effort.
  pressure   PRESSURE_WEIGHTS: assistance, repetition, absence, defeat, and the
             Hand already worn. This is the axis the bargain rides on and it is
             independent of standing, because a strong player having a bad week
             is exactly who the offer is for.
  registers  Register.floor. Five thresholds on standing, monotone, no
             hysteresis, because nothing in standing can go down.
  the offer  Register.offer_floor, which FALLS as he escalates. Late in the
             game he makes the offer on very little provocation. That is not
             generosity.

WHAT COULD NOT BE RESOLVED, said plainly rather than guessed at:

  deaths     there is no defeat counter in engine.DEFAULT_STATE["stats"]. The
             dossier reads stats["deaths"] anyway, with a default of zero, so
             the day that key exists this lights up with no edit here. Until
             then FIRST_DEATH and DEFEATED are driven by the caller firing them
             and by this module's own `fired` count, which is honest — it
             counts what it was told.

  the Hand   legendaries.py owns the gauntlet, its ledger and its decay. This
             module reads state["hand"]["uses"] and offers the bargain in
             words. It does not equip anything, it does not unlock anything,
             and a player accepts the offer by walking to the Hand, which is
             the only place that transaction should ever live.

  finalexam  owns the last fight and the examiner standing in it. This module
             stops at the door: two occasions, both fired by that flow, both
             outside the graded window. The verdict prose in
             finalexam.examiner_view is THE LAST INTERPRETER's, not his, and
             nothing here overlaps it.

  the finale captives.py and finale.py own what happens after the practical is
             passed. He has nothing to say there and deliberately no occasion
             for it: the ending belongs to the people who were let out.

             finale.cutscene accepts `king_voice={"offer": (...),
             "breaks": (...)}` and this module deliberately does not supply one.
             finale.KING_VOICE is authored FOR that scene, in the shape that
             scene needs, and two lines written for one moment beat any number
             composed for a general one. The voices agree — that scene is him at
             UNQUIET, which is the register this file ends on — and agreeing
             without overriding is the correct relationship between them.

  unmaking.py imports `names_a_fix` and `names_a_construct` from here through an
             optional import. Both are public, both take one positional string,
             and neither will change shape. `names_a_construct` defaults to
             strict=True, which is the right default for authored prose; pass
             strict=False for a line that already carries another module's
             English.
"""


if __name__ == "__main__":            # pragma: no cover
    print(report())
