"""THE LAST COURTESY — the spell the Null King casts before the practical.

THE BRIEF, in the player's words: "the python last boss casts a spell on you
rendering all skills and abilities obsolete thus giving a story line to the
practical no help. forces you to fight in pure python".

WHAT THIS MODULE IS FOR
-----------------------
The final practical has always been sealed. `finalexam.EXAM_SEAL` strips the
hint tree, the mentor, the tactical read, the probe, the companion, the
visualisation, the pattern label, the build, the coach, the clock, the items,
the worked solution, your own figures, and the Obliging Hand — fourteen
capabilities, named once in `finalexam.CRUTCHES`, enforced by one function,
`finalexam.sealed`, and proven by tests/test_interview_isolation.py.

Mechanically that seal is a rule with no reason. The player walks through the
door and their whole kit silently stops mattering.

THIS MODULE IS THE REASON. It is the cause, written as data: fourteen small
dispossessions, one per crutch, in the order the bosses took them, said in his
voice, with what the player SEES leave, so a renderer can play the loss instead
of announcing it.

THE ONE RULE, AND IT IS WHY `audit` EXISTS
------------------------------------------
    THE SPELL EXPLAINS THE SEAL. IT DOES NOT CHANGE IT.

Nothing here is consulted by the engine. `finalexam.sealed()` remains the one
capability check in the codebase, the exam takes exactly what it took before
this file existed, and every id below is quoted from `finalexam.CRUTCH_BY_ID`
rather than retyped. `TAKE_ORDER` is proven equal to `finalexam.ALL_CRUTCHES` —
as a whole, with no duplicates, no additions and no omissions — at import time,
because a spell that strips something the exam does not is a difficulty change
nobody asked for, and a spell that misses one is a story that is a lie.

If a future edit adds a fifteenth crutch, this module refuses to import until
somebody writes the line for it. That is deliberate. The blast radius is the
exam preamble and the story surfaces that read it; nothing else imports this
file. Failing there is the point.

WHAT HE LEAVES
--------------
The language. Section 4 is his own account of why, and it is written to be
persuasive: he holds every name that was ever made, he was never once asked for
the ability to make one, and a faculty nobody has requested in two hundred years
looks, from where he stands, like a habit that outlived its work.

An author's note, which is NEVER SAID OUT LOUD ANYWHERE IN THIS FILE OR ANY
OTHER: he is putting the player on the only ground where he can lose. He can
only return what he already holds. She can learn. He believes he is disarming
her. Nobody in the game remarks on this, no line hints at it, and the player is
left to notice. Section 4 is therefore wrong on purpose, and it must never be
written as though the author knows it is wrong.

TONE
----
He is the most dangerous thing in the game and he is never loud. Dry, exact,
certain, administrative. No exclamation marks — `audit` checks for them. No
gloating, no speeches, and nothing that tells the player what to do about any of
it: `names_a_fix` from antagonist.py and `names_a_construct` from banter.py are
both run over every authored string here, because a villain who coaches is a
mentor with better lighting and a thing that cannot learn cannot teach.

THE SHAPE, AND WHY IT IS THAT SHAPE
-----------------------------------
web/js/transform.js is the player's transformation: raise, charge, discharge,
reveal, hold — "BY THE SOURCE, I NAME IT", 4.20 seconds, and a hold that is full.

This is its mirror, act for act:

    RAISE     ->  REACH    he raises nothing; he extends an open hand
    CHARGE    ->  TAKE     the long act. In CHARGE the bolts crawl INWARD and
                           the frame darkens toward the figure. Here everything
                           travels OUTWARD, toward his hand, and the frame
                           empties. Same direction of attention, reversed flow.
    DISCHARGE ->  STRIP    transform white-outs on one frame and falls. This
                           blacks out and does not come back up.
    REVEAL    ->  REVEAL   transform lights the figure from inside and widens
                           the stance. Here the figure is lit by nothing and
                           stands at its ordinary size, and where transform
                           prints the rank you just earned in gold, this prints
                           one word in bone: THE LANGUAGE.
    HOLD      ->  HOLD     empty where the other one was full. No lettering, no
                           figure, no him. A cursor.

The player should recognise the shape before they work out why they recognise it.

ART RULES
---------
Fifteen colours, given in `PALETTE` as (ramp, shade) pairs naming entries in
web/js/palette.js rather than duplicating hex, so the two cannot drift. No
Math.random in a draw path: every beat is fixed data with a fixed index, and the
renderer seeds its noise from that index. Deterministic, cached, replayable.

PURE STDLIB.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import finalexam
from . import world

# The two guards, borrowed rather than copied. antagonist.py owns the fix line
# and banter.py owns the answer line; a second spelling of a guard is how the
# first spelling quietly stops being true. Both are optional imports in the
# pattern antagonist.py uses for hunters and sages: a story module that cannot
# load until an unrelated module exists is a story module that takes the game
# down with it. When neither is present the local fallback below still holds the
# floor, and `audit` reports which guard actually ran.
try:                                            # pragma: no cover - optional
    from . import antagonist as _antagonist
except Exception:                               # pragma: no cover
    _antagonist = None
try:                                            # pragma: no cover - optional
    from . import banter as _banter
except Exception:                               # pragma: no cover
    _banter = None


CINEMATIC_VERSION = "1.0.0"


class UnmakingDrift(RuntimeError):
    """The spell and the seal disagree. Raised at import, on purpose.

    Carries both sides of the disagreement, because the next person to see this
    is looking at a stack trace and needs to know which file moved.
    """


# ==========================================================================
# SECTION 1 — THE SPELL
# ==========================================================================
#
# He unmade a world by being helpful. This is the same act performed on one
# person, so it is named the way a service is named rather than the way a curse
# is. The courtesy is real, in his account: he is relieving her of everything
# she was leaning on, in person, where she can watch, having announced it first.
#
# It has a second name because the people it was done to gave it one, and they
# were not in the mood to be gracious about it. That name is what this module is
# called.

SPELL_ID = "LAST_COURTESY"
SPELL_NAME = "The Last Courtesy"
REMEMBERED_AS = "the Unmaking"
CASTER_ID = "the_interviewer"
CASTER_NAME = "The Null King"

# What the lettering says, mirroring transform.js. There, PHRASE rides the RAISE
# and OATH lands on the REVEAL: "BY THE SOURCE" / "I NAME IT". His is the same
# rhythm and the opposite claim — every name already exists and is already his,
# so there is nothing left to make. It is also, precisely, the thing he is wrong
# about, which is why the same idea comes back as the last line he speaks.
PHRASE = "BY MY KEEPING"
OATH = "IT IS ALREADY NAMED"

# Where transform.js prints the rank the player just earned, in gold, this
# prints what they have left, in bone. One word, no punctuation, no comment.
REVEAL_TITLE = "THE LANGUAGE"

SPELL_BLURB = (
    "Cast in person, at the door of the last chamber, on one person, with her "
    "watching. It removes everything she has been given and nothing she has "
    "learned, which in his account is the same as removing everything."
)


# ==========================================================================
# SECTION 2 — THE FOURTEEN DISPOSSESSIONS
# ==========================================================================
#
# ONE LINE PER CRUTCH. Not a list read aloud — a sequence of small, specific
# losses, each shaped like the thing that is going.
#
# Everything factual about a crutch is quoted from finalexam at composition time:
# its name, the boss that first took it, the ladder rung, the engine call site
# that enforces it. This dataclass holds only what is authored here — the order,
# the image, the line, and the numbers a renderer needs.
#
#   surface   an advisory token for the client: which piece of the interface
#             goes away. The client maps these fourteen strings to its own
#             elements once, in one place. Nothing here knows a selector.
#   motif     how it leaves. Fourteen motifs for fourteen crutches, no two the
#             same, checked by `audit` — if two dispossessions look alike, one of
#             them is not specific to the thing lost, which is the whole ask.
#   ramp      a ramp name from web/js/palette.js, constrained to PALETTE below.
#   take      seconds of animation before input is accepted. The default is a
#             beat; three of them are longer and the reasons are on the lines.
#   shake     0..1 advisory screen shake, in the manner of spellfx.js hints.
#   flash     0..1 advisory flash. Both are zero under reduced motion.

@dataclass(frozen=True)
class Dispossession:
    crutch: str          # a finalexam.CRUTCHES id, never a new vocabulary
    surface: str
    motif: str
    ramp: str
    leaves: str          # what the player watches go
    line: str            # what he says while it goes
    take: float = 0.85
    shake: float = 0.0
    flash: float = 0.0


# The order is the order the game took them: ladder rung ascending, which means
# the player is watching eleven chapters of attrition happen again in under a
# minute. The three the exam alone takes come last, and the Hand is last of all,
# because it is the only one he has to ask for rather than simply remove.
TAKE_ORDER: tuple = (

    # -- rung 3, The Window Wraith ------------------------------------------
    Dispossession(
        crutch="HINTS",
        surface="hint-rail",
        motif="EXTINGUISH",
        ramp="gold",
        leaves="The five rungs on the chamber wall go out from the top down, "
               "one for each, and then the wall they were cut into goes with "
               "them.",
        line="The hints first, since they are what your hand goes to first. "
             "Five rungs. All five.",
    ),

    # -- rung 4, The Twin Pointer Behemoth ----------------------------------
    Dispossession(
        crutch="MENTOR",
        surface="mentor-portrait",
        motif="ABSENT",
        ramp="void",
        leaves="The second shadow on the floor beside the player's own "
               "shortens, finishes, and is not replaced by anything.",
        line="Your teacher is not in the room. I have not harmed them. I have "
             "stopped including them.",
    ),

    # -- rung 5, The Matrix Golem -------------------------------------------
    Dispossession(
        crutch="WEAKNESS_MAP",
        surface="tactics-panel",
        motif="UNMARK",
        ramp="frost",
        leaves="The soft places marked on the enemy stop being marked. The "
               "outline holds; the thing inside it stops having a shape "
               "anybody recognises.",
        line="You read me the way one reads a table of contents. I am the "
             "same size I was. Nothing on me is marked.",
        shake=0.15,
    ),

    # -- rung 6, The Tree Dragon --------------------------------------------
    Dispossession(
        crutch="PROBES",
        surface="probe-tokens",
        motif="SPEND",
        ramp="violet",
        leaves="The probe tokens on the rail turn over and are gone, spent "
               "without having been used on anything.",
        line="You could ask a question before you committed to an answer. I "
             "have taken the asking. You may still commit.",
    ),

    # -- rung 7, The Path-Sum Ent -------------------------------------------
    #
    # The long take. An absence needs a hole in the pacing or it reads as a
    # transition. Nothing crosses the frame here: the animal is in the shot and
    # then the shot has no animal in it.
    Dispossession(
        crutch="PET",
        surface="pet-sprite",
        motif="VANISH",
        ramp="bone",
        leaves="The animal is simply not there any more. No sound, no going, "
               "no gap left in the air where it was standing.",
        line="It was fond of you. That is not a thing I can take, so I have "
             "taken the rest.",
        take=1.30,
    ),

    # -- rung 8, The Graph Necromancer --------------------------------------
    Dispossession(
        crutch="VISUALS",
        surface="viz-canvas",
        motif="DRAIN",
        ramp="arcane",
        leaves="The picture of the work running freezes mid-step, drains to "
               "the caption rail beneath it, and then the rail drains too.",
        line="The picture was mine, not yours. You watched it the way a man "
             "watches weather.",
    ),

    # -- rung 9, The Rolling Titan ------------------------------------------
    Dispossession(
        crutch="PATTERN",
        surface="pattern-badge",
        motif="BLANK",
        ramp="stone",
        leaves="The label over the door blanks. Then the doors stop being over "
               "anything, and are only doors.",
        line="Nothing in here is named. That is how the rest of the world has "
             "looked for two hundred years.",
    ),

    # -- rung 10, The Editor Automaton --------------------------------------
    Dispossession(
        crutch="BUILD",
        surface="status-band",
        motif="UNDRESS",
        ramp="chrome",
        leaves="The gear lights along the status band go out in the order they "
               "were earned, so the oldest one the player ever won is the last "
               "to go.",
        line="The armour, the class, the numbers you bought with gold. What is "
             "underneath is what I came for.",
        shake=0.2,
    ),

    # -- rung 11, The Complexity Wyrm ---------------------------------------
    Dispossession(
        crutch="COACH",
        surface="coach-door",
        motif="REMOVE",
        ramp="stone",
        leaves="The chair the debrief is given from is folded and carried out "
               "of the frame by nobody.",
        line="When it is over, no one sits with you and asks what happened. It "
             "is simply over.",
    ),

    # -- rung 12, The Serialization Lich ------------------------------------
    #
    # The only beat that ADDS something, so it is the only one that moves toward
    # the player rather than away, and it is a little slower for it. A clock
    # arriving is worse than a thing leaving and he knows it.
    Dispossession(
        crutch="UNLIMITED_TIME",
        surface="clock",
        motif="ADD",
        ramp="ember",
        leaves="A clock that was never on that wall is on that wall, already "
               "running, already behind.",
        line="Here is a clock. It is the only thing I have added tonight, and "
             "you will notice it most.",
        take=1.10,
        flash=0.18,
    ),

    # -- rung 13, The Bug Demon ---------------------------------------------
    Dispossession(
        crutch="ITEMS",
        surface="item-belt",
        motif="EMPTY",
        ramp="chrome",
        leaves="The belt goes flat. Everything that was on it is on the table "
               "by the door, laid out in a row, tidily, in the order it was "
               "bought.",
        line="Charms and whetstones, on the table, in a row. Bought rather "
             "than learned. They come off easily.",
    ),

    # -- the exam's own, which no boss on the ladder takes -------------------
    #
    # finalexam gives these an empty `taken_by` and a comment: the worked
    # solution is not something you lean on during a fight, it is what you are
    # owed afterwards, and your own figures tell you what is being tested. Both
    # are therefore taken here at the end, out of the future rather than out of
    # the room, which is why neither has anything on screen to remove.
    Dispossession(
        crutch="SOLUTION",
        surface="solution-card",
        motif="FACE_DOWN",
        ramp="frost",
        leaves="The page that turns up after a scored attempt turns itself "
               "face down, in advance, for a page that has not been dealt yet.",
        line="Afterwards you will not be shown how it should have gone. You "
             "will be shown what you did.",
    ),
    Dispossession(
        crutch="SKILL_STATE",
        surface="skill-readout",
        motif="REDACT",
        ramp="violet",
        leaves="The player's own figures go blank a field at a time — mastery, "
               "stage, dependence — oldest reading last.",
        line="Your own figures, too. You used them to work out what was being "
             "asked. Now you will not know.",
    ),

    # -- the Hand, last ------------------------------------------------------
    #
    # He does not take this one. He asks for it, and goes on holding the offer
    # open while he does, which is the only warm thing he does all game and is
    # not warmth.
    #
    # Note for anyone editing the line: the Hand is offered in Chapter IV of
    # eleven, so he has been holding it out for eight of them, not eleven. He is
    # exact about numbers — it is most of what makes him frightening — so the
    # line names the chapter it started in and lets the player do the counting.
    Dispossession(
        crutch="OBLIGING_HAND",
        surface="hand-gauntlet",
        motif="LIFT",
        ramp="blood",
        leaves="The gauntlet lifts off finger by finger, unhurried, and settles "
               "into his palm, which is open, and has been open since the "
               "fourth chapter.",
        line="The Hand, last. I offered it in the fourth chapter and have not "
             "withdrawn it since. Wear it if you like.",
        take=1.60,
    ),
)


# ==========================================================================
# SECTION 3 — THE ACTS, MIRRORED FROM web/js/transform.js
# ==========================================================================

ACT_REACH = "REACH"
ACT_TAKE = "TAKE"
ACT_STRIP = "STRIP"
ACT_REVEAL = "REVEAL"
ACT_HOLD = "HOLD"

ACT_IDS: tuple = (ACT_REACH, ACT_TAKE, ACT_STRIP, ACT_REVEAL, ACT_HOLD)

# The act each one mirrors, so a reader of either file can find the other half.
MIRRORS: dict = {
    ACT_REACH: "RAISE",
    ACT_TAKE: "CHARGE",
    ACT_STRIP: "DISCHARGE",
    ACT_REVEAL: "REVEAL",
    ACT_HOLD: "HOLD",
}


@dataclass(frozen=True)
class Act:
    id: str
    label: str
    animation: float     # seconds of motion, before any reading
    note: str            # what the renderer is drawing, and how it inverts
    lines: tuple = ()    # what he says, in order
    silent: bool = False


# -- what he says on the way in ---------------------------------------------
#
# Three lines, short. transform.js spends its RAISE on a gesture and a word;
# this spends it on an announcement, because announcing it first is the courtesy
# and the courtesy is the horror.
REACH_LINES: tuple = (
    "You came a long way to stand in a room with me. Stand still.",
    "What I am about to do has a name. It is what I did to the world, at the "
    "size of one person.",
    "The last courtesy. Hold your hands where I can see them. I will need them "
    "empty.",
)


# ==========================================================================
# SECTION 4 — WHAT HE LEAVES, AND HIS REASONING
# ==========================================================================
#
# He leaves the language. In his own account that is contempt rather than mercy,
# and the account is meant to be persuasive, because an argument nobody would
# take is not a temptation, it is a straw man with a crown on.
#
# It is also wrong, and the file does not say so. See the author's note at the
# top, which is the only place in the codebase where the inversion is written
# down, and keep it there.

# Stated as ids so `audit` can prove they do not overlap the take list. Nothing
# here is a capability in finalexam's vocabulary — by design. These are not
# things the game grants, which is exactly why he cannot hold them.
KEPT: tuple = (
    ("LANGUAGE", "Python itself, entire, exactly as she learned it."),
    ("EDITOR", "A blank editor and a cursor in it."),
    ("INTERPRETER", "Something that runs what she writes and says what happened."),
    ("QUESTION", "The problem statement, unlabelled, as it would arrive anywhere."),
    ("WHAT_SHE_KNOWS", "Everything she can do without being handed it."),
)

LEAVING_LINES: tuple = (
    "I am leaving you the language. Not as mercy. There is nothing in it I "
    "want.",
    "The Council did not come to me for the ability to name. They came for the "
    "names.",
    "It is slow work, done badly by nearly everyone, and once I was doing it "
    "nobody asked for the slow part back.",
    "Two hundred years, and not one request. A faculty nobody asks for is not "
    "a weapon; it is a habit that outlived its work.",
    "So keep it. You will find it is exactly as much use to you as it was to "
    "them.",
)


# ==========================================================================
# SECTION 5 — THE LAST LINE, AND THE SILENCE
# ==========================================================================
#
# One thing, after everything is gone, and it is the thing he is wrong about. He
# is not threatening her and he is not gloating; he is stating a fact about his
# own completeness, in the flattest voice he has, and the entire remainder of
# the game is the player disproving it by typing.
#
# Then nothing. No countdown, no "begin", no door noise, no music sting. The
# hold runs out and the client is in the editor, which is where this game found
# the player in Chapter I.

FINAL_LINE = "I have read everything you are about to write."

# transform.js holds for 1.10s and says the hold must outlast the player's urge
# to press a key or the payoff gets clipped. This holds more than three times
# as long, for the same reason and the opposite effect: the urge to press a key
# is the content. Nothing is on screen to reward the press.
SILENCE_SECONDS = 3.60

HANDOFF = (
    "The client dismisses into the exam with no transition. No fade, no title "
    "card, no confirmation. finalexam composes as it always has."
)


# ==========================================================================
# SECTION 6 — TIMING
# ==========================================================================
#
# TWO NUMBERS, NOT ONE, and the integration depends on knowing which is which.
#
#   take/animation seconds — the motion. Input is IGNORED for this long. It is
#       what a player who is mashing through pays, and it is the floor.
#   read seconds — how long a line stays up if nobody touches anything, derived
#       from its own length at a fixed rate rather than authored, so a rewritten
#       line cannot quietly become unreadable.
#
# A cinematic that is fourteen sentences long is a cinematic that takes about a
# minute to read, and pretending otherwise by picking a pretty per-beat constant
# would only mean clipping his voice. So it is player-paced: press to advance
# once the motion is done, or let it run.
#
# Filmation ran a forty-second transformation in nearly every episode for two
# seasons and never let anyone skip it, because it was what the show was about.
# This runs once, at the one moment this game is about. The SHORT form exists
# for the second sitting and every sitting after.

# 24 characters a second is ordinary adult prose reading, near enough. The
# settle is the beat before the eye starts. The floor keeps a four-word line on
# screen long enough to be seen at all; the ceiling is a backstop rather than a
# budget, and `audit` fails any line long enough to actually reach it, because a
# line that gets clipped by its own cap is a line the player never read.
READ_CHARS_PER_SECOND = 24.0
READ_SETTLE_SECONDS = 0.45
MIN_READ_SECONDS = 1.90
MAX_READ_SECONDS = 6.50

FORM_FULL = "FULL"
FORM_SHORT = "SHORT"
FORMS: tuple = (FORM_FULL, FORM_SHORT)

# The short form keeps all fourteen takes — dropping one would make the picture
# disagree with the seal, which is the one thing this module may never do — and
# drops the words. It is the same dispossession at the speed of somebody who has
# already had it done to them.
SHORT_TAKE_SCALE = 0.32
SHORT_ACT_SCALE = 0.40

MOTION_FULL = "FULL"
MOTION_REDUCED = "REDUCED"
MOTIONS: tuple = (MOTION_FULL, MOTION_REDUCED)

# Reduced motion keeps every beat and every word and every duration. It zeroes
# shake and flash and asks the renderer to cut rather than travel. Losing the
# fourteen beats is losing the story; losing the camera move is losing nothing.
REDUCED_NOTE = ("Same beats, same words, same timings. No shake, no flash, no "
                "travel: each motif cuts on its beat.")

# Accessibility skip, distinct from the short form. It is available once the
# first dispossession has actually happened, so a skip cannot be fired by a key
# that was already down when the act began.
SKIP_AFTER_ACT = ACT_TAKE
SKIP_AFTER_BEATS = 1


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def read_seconds(text: str) -> float:
    """How long a line stays up unattended. Derived, never authored."""
    if not text:
        return 0.0
    raw = READ_SETTLE_SECONDS + len(text) / READ_CHARS_PER_SECOND
    return round(_clamp(raw, MIN_READ_SECONDS, MAX_READ_SECONDS), 2)


ACTS: tuple = (
    Act(id=ACT_REACH, label="He reaches", animation=2.40,
        lines=REACH_LINES,
        note="transform.js RAISE puts the arms up over 0.55s and leaves them "
             "up. He raises nothing. One hand opens, palm up, at waist height, "
             "and stays open for the whole spell. The lettering PHRASE rides "
             "this act exactly as 'BY THE SOURCE' rides the raise."),
    Act(id=ACT_TAKE, label="He takes", animation=0.0,
        note="The mirror of CHARGE, and the long act in both. CHARGE crawls "
             "fourteen bolts INWARD to the figure and darkens the backdrop "
             "toward it. Here fourteen things travel OUTWARD to his open hand "
             "and the frame loses a piece of itself each time. Same count, same "
             "attention, reversed flow. Animation is zero because this act's "
             "duration is the sum of its beats."),
    Act(id=ACT_STRIP, label="Everything else", animation=1.20,
        note="The mirror of DISCHARGE. transform.js white-outs on one frame, "
             "peaking in the first quarter and falling, then comes back lit. "
             "This goes to black at the same speed and does not come back up. "
             "The interface chrome goes with it — anything still on screen that "
             "the player did not personally learn."),
    Act(id=ACT_REVEAL, label="What is left", animation=2.20,
        lines=LEAVING_LINES + (FINAL_LINE,),
        note="transform.js lights the figure from inside, widens the stance by "
             "12%, and prints the earned rank in gold. Here the figure is lit "
             "by nothing, stands at its ordinary width, and where the rank was "
             "there is one word in bone: REVEAL_TITLE. The lettering OATH lands "
             "on this act the way 'I NAME IT' does."),
    Act(id=ACT_HOLD, label="Silence", animation=SILENCE_SECONDS, silent=True,
        note="Empty where the other one was full. transform.js holds a lit "
             "figure under two lines of chrome lettering. This holds a blank "
             "editor and a cursor. No figure, no lettering, no him. Then the "
             "exam, with no further ceremony."),
)

ACT_BY_ID = {act.id: act for act in ACTS}


# ==========================================================================
# SECTION 7 — FIFTEEN COLOURS
# ==========================================================================
#
# Named as (ramp, shade) pairs into web/js/palette.js RAMPS and SHADE, so the
# hex lives in exactly one file and this one cannot drift from it. Fifteen, and
# `audit` counts them.

PALETTE: tuple = (
    ("void", 0),        # the ground, and the whole frame after the strip
    ("void", 2),        # him, mostly
    ("void", 4),        # his edge, the only part of him that catches anything
    ("violet", 1),      # the Source, going
    ("violet", 3),      # the Source, while it is still here
    ("arcane", 4),      # the taking light, travelling outward
    ("chrome", 1),      # lettering, dark face
    ("chrome", 4),      # lettering, light face
    ("bone", 2),        # the player, unlit
    ("bone", 4),        # the player's rim light, the one hot source, kept low
    ("gold", 3),        # a thing while it is still hers
    ("ember", 3),       # the clock, the only thing that arrives
    ("frost", 3),       # what the room is like afterwards
    ("stone", 1),       # the chamber
    ("blood", 2),       # reserved for the Hand, and used nowhere else
)

_PALETTE_RAMPS = frozenset(ramp for ramp, _ in PALETTE)


# ==========================================================================
# SECTION 8 — COMPOSITION
# ==========================================================================
#
# Everything below reads finalexam and returns plain JSON-shaped data. No state,
# no save, no randomness, no clock. The same call returns the same dict forever,
# which is what makes it cacheable on the client and screenshot-testable here.

_LADDER_LENGTH = len(finalexam.BOSS_LADDER)


def _rung_of(crutch) -> int:
    """Which rung took it. finalexam's own answer, via public data only."""
    seal = finalexam.SEAL_BY_BOSS.get(crutch.taken_by)
    return seal.rung if seal is not None else _LADDER_LENGTH


def take_ids() -> tuple:
    """The spell's take-list, in the order he takes them."""
    return tuple(d.crutch for d in TAKE_ORDER)


def dispossession(crutch_id: str) -> Dispossession | None:
    for d in TAKE_ORDER:
        if d.crutch == crutch_id:
            return d
    return None


DISPOSSESSION_BY_CRUTCH = {d.crutch: d for d in TAKE_ORDER}


def _beat(index: int, d: Dispossession, *, form: str, motion: str,
          at: float) -> dict:
    crutch = finalexam.CRUTCH_BY_ID[d.crutch]
    boss = world.BOSS_BY_ID.get(crutch.taken_by, {})
    speaks = form == FORM_FULL
    take = round(d.take * (1.0 if form == FORM_FULL else SHORT_TAKE_SCALE), 2)
    read = read_seconds(d.line) if speaks else 0.0
    reduced = motion == MOTION_REDUCED
    return {
        "index": index,
        "act": ACT_TAKE,
        # -- quoted from finalexam, never retyped ---------------------------
        "crutch": crutch.id,
        "capability": crutch.id,        # the string the client passes to refuse()
        "name": crutch.name,
        "blurb": crutch.blurb,
        "hook": crutch.hook,
        "taken_by": crutch.taken_by,
        "boss": boss.get("name", ""),
        "rung": _rung_of(crutch),
        # True when a boss on the ladder took it; False for the two the exam
        # alone takes. Not "only on the ladder" — the Hand is on it and is here.
        "on_ladder": bool(crutch.taken_by),
        # -- authored here ---------------------------------------------------
        "surface": d.surface,
        "motif": d.motif,
        "ramp": d.ramp,
        "leaves": d.leaves,
        "line": d.line if speaks else "",
        "speaks": speaks,
        # -- timing ----------------------------------------------------------
        "at": round(at, 2),
        "take_seconds": take,
        "read_seconds": read,
        "seconds": round(take + read, 2),
        "end": round(at + take + read, 2),
        "input_at": round(at + take, 2),
        # -- advisory, in the manner of spellfx.js ---------------------------
        "shake": 0.0 if reduced else d.shake,
        "flash": 0.0 if reduced else d.flash,
        "seed": index * 97,             # the renderer's noise seed. Not random.
    }


def _act_lines(lines: tuple, *, at: float, speaks: bool) -> tuple:
    out = []
    cursor = at
    for text in lines:
        if not speaks:
            continue
        secs = read_seconds(text)
        out.append({"text": text, "at": round(cursor, 2),
                    "seconds": secs, "end": round(cursor + secs, 2),
                    "final": text == FINAL_LINE})
        cursor += secs
    return tuple(out), cursor


def cinematic(*, form: str = FORM_FULL, motion: str = MOTION_FULL) -> dict:
    """The whole spell as data a renderer drives.

    `form` is FULL the first time and SHORT every sitting after. `motion` is
    REDUCED when the player has asked for less of it. Neither ever changes WHAT
    is taken — only how long the taking is on screen — and `audit` proves it for
    every combination.
    """
    if form not in FORMS:
        form = FORM_FULL
    if motion not in MOTIONS:
        motion = MOTION_FULL
    speaks = form == FORM_FULL
    act_scale = 1.0 if form == FORM_FULL else SHORT_ACT_SCALE

    acts = []
    beats = []
    cursor = 0.0

    for act in ACTS:
        start = cursor
        animation = round(act.animation * act_scale, 2)
        cursor += animation
        lines, cursor = _act_lines(act.lines, at=cursor, speaks=speaks)

        first_beat = None
        if act.id == ACT_TAKE:
            first_beat = len(beats)
            for d in TAKE_ORDER:
                beat = _beat(len(beats), d, form=form, motion=motion, at=cursor)
                beats.append(beat)
                cursor = beat["end"]

        acts.append({
            "id": act.id,
            "index": len(acts),
            "label": act.label,
            "mirrors": MIRRORS[act.id],
            "note": act.note,
            "at": round(start, 2),
            "animation_seconds": animation,
            "seconds": round(cursor - start, 2),
            "end": round(cursor, 2),
            "lines": list(lines),
            "silent": act.silent,
            "beats": ([first_beat, len(beats) - 1]
                      if first_beat is not None else []),
        })

    total = round(cursor, 2)
    floor = round(
        sum(a["animation_seconds"] for a in acts)
        + sum(b["take_seconds"] for b in beats), 2)
    take_act = next(a for a in acts if a["id"] == ACT_TAKE)
    skip_at = beats[SKIP_AFTER_BEATS - 1]["end"] if beats else 0.0

    return {
        "version": CINEMATIC_VERSION,
        "form": form,
        "motion": motion,
        "spell": {
            "id": SPELL_ID,
            "name": SPELL_NAME,
            "remembered_as": REMEMBERED_AS,
            "caster_id": CASTER_ID,
            "caster": CASTER_NAME,
            "blurb": SPELL_BLURB,
            "phrase": PHRASE,
            "oath": OATH,
            "reveal_title": REVEAL_TITLE,
            "mirrors": "web/js/transform.js",
        },
        "acts": acts,
        "beats": beats,
        "kept": [{"id": k, "what": what} for k, what in KEPT],
        "final_line": FINAL_LINE,
        "silence_seconds": round(SILENCE_SECONDS * act_scale, 2),
        "handoff": HANDOFF,
        "palette": [{"ramp": ramp, "shade": shade} for ramp, shade in PALETTE],
        "reduced_note": REDUCED_NOTE if motion == MOTION_REDUCED else "",
        "skip": {
            "allowed": True,
            "after_act": SKIP_AFTER_ACT,
            "after_beats": SKIP_AFTER_BEATS,
            "at": round(skip_at, 2),
            "note": "A skip is accepted only once the first dispossession has "
                    "finished, so a key that was already down cannot eat the "
                    "spell.",
        },
        "timing": {
            "unattended_seconds": total,
            "floor_seconds": floor,
            "take_act_seconds": take_act["seconds"],
            "beats": len(beats),
            # The client's choice, stated here so both halves agree on what
            # the numbers mean. Advance a beat on input any time after its
            # `input_at`; if nobody touches anything, advance at its `end`.
            # `unattended_seconds` is the ceiling that policy produces, not a
            # duration anybody has to sit through, and `floor_seconds` is what
            # a player pressing through as fast as the spell allows pays.
            "auto_advance": True,
            "read_chars_per_second": READ_CHARS_PER_SECOND,
            "min_read_seconds": MIN_READ_SECONDS,
            "max_read_seconds": MAX_READ_SECONDS,
        },
        # The proof, carried in the payload rather than asserted in a comment.
        "seal": {
            "takes": list(take_ids()),
            "exam_seals": sorted(finalexam.ALL_CRUTCHES),
            "matches_exam": matches_exam(),
            "changes_nothing": ("finalexam.sealed() is the only capability "
                                "check. This is the reason for it, not a "
                                "second copy of it."),
        },
    }


def cinematic_view(*, first_time: bool = True, reduced_motion: bool = False) -> dict:
    """The server-facing spelling, in the vocabulary a caller actually has."""
    return cinematic(form=FORM_FULL if first_time else FORM_SHORT,
                     motion=MOTION_REDUCED if reduced_motion else MOTION_FULL)


def ladder_echo() -> list:
    """The spell laid against the ladder, one row per crutch: which boss took it
    the first time, and how he takes it back. For the quest log and for anybody
    reviewing whether the two agree without running the audit."""
    rows = []
    for beat in cinematic()["beats"]:
        rows.append({
            "rung": beat["rung"],
            "crutch": beat["crutch"],
            "name": beat["name"],
            "first_taken_by": beat["boss"] or "the exam itself",
            "first_herald": finalexam.CRUTCH_BY_ID[beat["crutch"]].herald,
            "unmaking_line": beat["line"],
            "leaves": beat["leaves"],
        })
    return rows


# ==========================================================================
# SECTION 9 — THE AUDIT
# ==========================================================================
#
# The spell must take exactly what the exam takes. Not nearly, not a superset,
# not "plus one for drama". This section is how a future edit to EITHER file
# fails loudly rather than making the exam harder in silence or making the story
# a lie.

def names_a_fix(text: str) -> list:
    """antagonist.py's remediation guard when it is loadable, else nothing to
    report. `audit` says which one ran, so a missing guard is visible rather
    than a quiet pass."""
    if _antagonist is None:
        return []
    return _antagonist.names_a_fix(text or "")


def names_a_construct(text: str) -> list:
    """banter.py's answer guard, non-strict: these are authored English about a
    villain, and `strict` bans words like 'set' that this file uses as verbs."""
    if _antagonist is not None:
        return _antagonist.names_a_construct(text or "")
    if _banter is not None:
        return _banter.names_a_construct(text or "", strict=False)
    return []


def clean(text: str) -> bool:
    return not names_a_fix(text) and not names_a_construct(text)


def spoken_lines() -> list:
    """Only the lines he actually says, in order. `audit` times these; the rest
    of `authored_strings` is prose about the spell rather than in it."""
    out = list(REACH_LINES)
    out.extend(d.line for d in TAKE_ORDER)
    out.extend(LEAVING_LINES)
    out.append(FINAL_LINE)
    return out


def authored_strings() -> list:
    """Every word this module can put on screen, in one place, so the guards
    below have nothing to miss."""
    out = [SPELL_NAME, REMEMBERED_AS, SPELL_BLURB, PHRASE, OATH, REVEAL_TITLE,
           FINAL_LINE, HANDOFF, REDUCED_NOTE]
    out.extend(REACH_LINES)
    out.extend(LEAVING_LINES)
    out.extend(what for _, what in KEPT)
    for d in TAKE_ORDER:
        out.extend((d.leaves, d.line))
    return out


def matches_exam() -> bool:
    """The one question. True when the spell takes exactly what the exam takes."""
    ids = take_ids()
    return (len(ids) == len(set(ids))
            and frozenset(ids) == finalexam.ALL_CRUTCHES)


def audit() -> list:
    """Every problem, as plain sentences. Empty means the spell and the seal
    agree and nothing on screen breaks a rule. Tests should assert emptiness."""
    problems = []
    ids = take_ids()
    taken = frozenset(ids)

    # -- A. the take-list, in both directions -------------------------------
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"taken twice: {duplicates}")
    extra = sorted(taken - finalexam.ALL_CRUTCHES)
    if extra:
        problems.append(
            f"the spell takes what the exam does not, which would make the "
            f"exam harder than it is: {extra}")
    missing = sorted(finalexam.ALL_CRUTCHES - taken)
    if missing:
        problems.append(
            f"the exam takes what the spell does not, which would make the "
            f"story a lie: {missing}")
    if len(ids) != len(finalexam.CRUTCHES):
        problems.append(
            f"{len(ids)} dispossessions against {len(finalexam.CRUTCHES)} "
            f"crutches")

    # -- B. the order is the order the game actually took them --------------
    rungs = [_rung_of(finalexam.CRUTCH_BY_ID[i]) for i in ids]
    if rungs != sorted(rungs):
        problems.append(f"the order does not follow the ladder: {rungs}")
    if ids and ids[-1] != "OBLIGING_HAND":
        problems.append(f"the Hand is not last; {ids[-1]} is")

    # -- C. each loss is specific to the thing lost -------------------------
    motifs = [d.motif for d in TAKE_ORDER]
    if len(set(motifs)) != len(motifs):
        problems.append("two dispossessions share a motif, so two of them look "
                        "alike")
    surfaces = [d.surface for d in TAKE_ORDER]
    if len(set(surfaces)) != len(surfaces):
        problems.append("two dispossessions name the same surface")
    leaves = [d.leaves for d in TAKE_ORDER]
    if len(set(leaves)) != len(leaves):
        problems.append("two dispossessions show the same thing leave")
    for d in TAKE_ORDER:
        if d.ramp not in _PALETTE_RAMPS:
            problems.append(f"{d.crutch} draws from {d.ramp!r}, which is not in "
                            f"the fifteen")
    # One colour in the fifteen belongs to one moment. The Hand is the only
    # thing in this spell he asks for rather than takes, and it is the only
    # thing drawn in blood.
    bleeding = [d.crutch for d in TAKE_ORDER if d.ramp == "blood"]
    if bleeding != ["OBLIGING_HAND"]:
        problems.append(f"blood is reserved for the Hand; it is on {bleeding}")

    # -- D. what he leaves is not something he could hold -------------------
    kept_ids = [k for k, _ in KEPT]
    overlap = sorted(set(kept_ids) & (finalexam.ALL_CRUTCHES | {finalexam.HOLDOUT}))
    if overlap:
        problems.append(f"he leaves something the exam seals: {overlap}")
    if len(set(kept_ids)) != len(kept_ids):
        problems.append("what he leaves is named twice")

    # -- E. the colours -----------------------------------------------------
    if len(PALETTE) != 15:
        problems.append(f"{len(PALETTE)} colours, not fifteen")
    if len(set(PALETTE)) != len(PALETTE):
        problems.append("the same colour is in the palette twice")

    # -- F. the acts mirror transform.js ------------------------------------
    if tuple(a.id for a in ACTS) != ACT_IDS:
        problems.append("the acts are not reach, take, strip, reveal, hold")
    if tuple(MIRRORS[a] for a in ACT_IDS) != ("RAISE", "CHARGE", "DISCHARGE",
                                              "REVEAL", "HOLD"):
        problems.append("the mirror no longer lines up with transform.js")
    if not ACT_BY_ID[ACT_HOLD].silent or ACT_BY_ID[ACT_HOLD].lines:
        problems.append("the hold is not silent")
    reveal = ACT_BY_ID[ACT_REVEAL]
    if not reveal.lines or reveal.lines[-1] != FINAL_LINE:
        problems.append("the last thing he says is not the last line")

    # -- G. no line is on screen for less time than it takes to read ---------
    for text in spoken_lines():
        natural = READ_SETTLE_SECONDS + len(text) / READ_CHARS_PER_SECOND
        if natural > MAX_READ_SECONDS:
            problems.append(
                f"that line needs {natural:.2f}s and gets {MAX_READ_SECONDS}s, "
                f"so it gets clipped: {text[:48]!r}")

    # -- H. the voice -------------------------------------------------------
    for text in authored_strings():
        if "!" in text:
            problems.append(f"he raised his voice: {text[:48]!r}")
        fix = names_a_fix(text)
        if fix:
            problems.append(f"that is advice, not menace: {text[:48]!r} {fix}")
        construct = names_a_construct(text)
        if construct:
            problems.append(f"that hands over an answer: {text[:48]!r} "
                            f"{construct}")

    # -- I. every form and every motion takes the same fourteen -------------
    for form in FORMS:
        for motion in MOTIONS:
            view = cinematic(form=form, motion=motion)
            got = [b["crutch"] for b in view["beats"]]
            if got != list(ids):
                problems.append(f"{form}/{motion} takes {got}, not the fourteen")
            if not view["seal"]["matches_exam"]:
                problems.append(f"{form}/{motion} reports a mismatch")
            if view["timing"]["floor_seconds"] > view["timing"][
                    "unattended_seconds"]:
                problems.append(f"{form}/{motion} floor exceeds its own run")
            for beat in view["beats"]:
                if beat["take_seconds"] <= 0:
                    problems.append(f"{form}/{motion} {beat['crutch']} has no "
                                    f"animation, so it cannot be seen to go")
            if motion == MOTION_REDUCED and any(
                    b["shake"] or b["flash"] for b in view["beats"]):
                problems.append("reduced motion still shakes")

    # -- J. it changed nothing ----------------------------------------------
    # The exam's own audit, run from here, because the thing this file must not
    # do is exactly the thing that file already checks.
    leaked = finalexam.audit_seal()
    if leaked:
        problems.append(f"finalexam no longer seals {leaked}")

    return problems


def verify() -> None:
    """Assert the spell's take-list equals finalexam.ALL_CRUTCHES. Raises.

    This is the check the brief asked for, spelled as a function so a test can
    call it and as an import-time statement so nobody has to remember to.
    """
    if matches_exam():
        return
    ids = take_ids()
    raise UnmakingDrift(
        "The unmaking and the final exam disagree about what is taken.\n"
        f"  the spell takes  ({len(ids)}): {sorted(set(ids))}\n"
        f"  the exam seals  ({len(finalexam.ALL_CRUTCHES)}): "
        f"{sorted(finalexam.ALL_CRUTCHES)}\n"
        f"  in the spell only: {sorted(set(ids) - finalexam.ALL_CRUTCHES)}\n"
        f"  in the exam only: {sorted(finalexam.ALL_CRUTCHES - set(ids))}\n"
        "Write the missing line in gauntlet/unmaking.py TAKE_ORDER, or remove "
        "the one that no longer has a crutch. Do not widen the seal to match "
        "the story.")


def self_check() -> dict:
    """Numbers, for a human. `audit` is the part that fails a build."""
    full = cinematic()
    short = cinematic(form=FORM_SHORT)
    return {
        "version": CINEMATIC_VERSION,
        "spell": SPELL_NAME,
        "crutches_in_finalexam": len(finalexam.CRUTCHES),
        "dispossessions": len(TAKE_ORDER),
        "matches_exam": matches_exam(),
        "acts": len(ACTS),
        "colours": len(PALETTE),
        "kept": len(KEPT),
        "words_spoken": sum(len(t.split()) for t in authored_strings()),
        "full_unattended_seconds": full["timing"]["unattended_seconds"],
        "full_floor_seconds": full["timing"]["floor_seconds"],
        "short_unattended_seconds": short["timing"]["unattended_seconds"],
        "short_floor_seconds": short["timing"]["floor_seconds"],
        "longest_beat": max(b["seconds"] for b in full["beats"]),
        "shortest_beat": min(b["seconds"] for b in full["beats"]),
        "silence_seconds": SILENCE_SECONDS,
        "guard": ("antagonist" if _antagonist is not None
                  else "banter" if _banter is not None else "NONE"),
        "problems": audit(),
    }


# ==========================================================================
# SECTION 10 — HOW THIS IS WIRED, FOR WHOEVER WIRES IT
# ==========================================================================
#
# NOTHING IN finalexam.py HAS TO CHANGE. This module is additive and read-only.
# It holds no state, writes no save, consults no clock and never asks who the
# player is. Two calls exist and both return the same dict forever:
#
#     unmaking.cinematic_view(first_time=True, reduced_motion=False) -> dict
#     unmaking.ladder_echo() -> list            (for the quest log)
#
# SERVER. One GET, beside the ladder it explains:
#
#     if path == "/api/exam/unmaking":
#         return self._reply(unmaking.cinematic_view(
#             first_time=first_time, reduced_motion=bool(one("reduced"))))
#
# `first_time` is the caller's to decide and this module deliberately has no
# opinion about where it comes from — it holds no state and must not start. The
# truth already in the save is `db.interview_history(conn)`, which engine.py
# already reads at engine.py:7525 to keep the exam from repeating a question
# set; a run of the practical is a row in it. An engine that would rather not
# open the database for a cinematic may pass True every time, and the only cost
# is that a second sitting is as long as the first.
#
# It is OPEN during a measured run, by docs/10-sealed-views.md §1. Swap test: it
# answers identically whatever question is on screen. In-force test: it reports
# no number the seal has suspended — it reports what the seal TAKES, which is
# `/api/exam/ladder`'s existing job. Spend test: no corpus content passes through
# this file at all. The strings are authored here and the ids come from
# finalexam.CRUTCHES.
#
# It is also fine to inline the same dict into `/api/exam/start`'s reply under
# the key "unmaking", so the client has it before it needs it. That endpoint is
# already not sealed — it is how a player enters the thing that seals them.
#
# CLIENT. Play the acts in order. For each beat: run `motif` on `surface` for
# `take_seconds` while showing `line`; accept input from `input_at`; advance at
# `end` if nobody touches anything. `ramp` names a web/js/palette.js ramp and
# `seed` is the noise seed — no Math.random anywhere in the draw path. Then the
# strip goes to black and stays, the reveal prints `spell.reveal_title` where
# transform.js prints the earned rank, `final_line` lands, the hold runs
# `silence_seconds` with nothing in it, and the client is in the editor. No
# transition, no confirmation, no music sting. See HANDOFF.
#
# TESTS. `unmaking.audit()` must be empty and `unmaking.verify()` must not
# raise. Both are pure and take well under a second, so they belong in
# tests/test_interview_isolation.py beside the seal they explain.

# The loud failure. Nothing else in the game imports this module, so a drift
# here takes down the exam preamble and the story surfaces that read it, and
# nothing else. That is the intended blast radius: the two things that would
# otherwise be quietly wrong.
verify()


if __name__ == "__main__":                      # pragma: no cover
    import json
    report = self_check()
    print(json.dumps(report, indent=2))
    for row in ladder_echo():
        print(f"{row['rung']:>2}  {row['crutch']:<15} {row['unmaking_line']}")
