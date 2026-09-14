"""The first lesson: twenty-four things a schoolteacher tells you once each,
six more she hands off to a screen that already says them, and the counters
behind the one violet arrow in a battle.

This is the DATA LAYER for docs/13-the-first-lesson.md. It holds the
curriculum, the latch that remembers what has been taught, the derived speaker
for after the teacher is taken, and the cue policy the client is not allowed to
re-decide. It renders nothing, it opens no panel and it owns no DOM.

NAMING, and it is the first thing the wiring pass needs to know.
--------------------------------------------------------------------------
docs/13 §7.1 calls this file `gauntlet/firstlesson.py`. The pass that wrote it
owned `gauntlet/tutorial.py` instead, so this is that file under this name and
every symbol in §7.1 is present with the name §7.1 gave it. The import is

    from . import tutorial            # NOT firstlesson

and there is no `firstlesson.py` anywhere in the tree. Nothing else diverges
from the document.

Six things this module insists on.

1. IT NEVER ASKS THE SEAL, AND ITS GATES FAIL CLOSED. It does not import
   `finalexam` at module scope, it never calls `finalexam.sealed()`, and it
   has no opinion about any capability. A measured run is refused ONE way, in
   `available_in()`, which defers to `captives.available_in()` — the same gate
   `captives` and `zonecompanions` already stand behind. Three modules
   answering the same question three ways is what docs/10 §0 was written
   about. `validate()` reads `finalexam.CRUTCHES` as a REFUSAL VOCABULARY, at
   check time, through a lazy import, and that is the only appearance of that
   module's name here.

   The refusal is only as good as its default, so every gated entry point —
   `may_teach`, `teach`, `cueable`, `cue_note`, `forget` — defaults
   `run_open` to TRUE, and every one of those arguments is keyword-only. A
   caller who forgets it is answered with {} and the save is not touched.
   `mode` keeps its Adventure default on purpose: the gate is a disjunction,
   so `run_open` alone already refuses, and the engine has no mode string to
   pass — flipping `mode` too would have closed the gate on the only caller
   there is. `snapshot()` is exempt from both and says why in its own
   docstring: it writes nothing and grants nothing.

2. THE TEACHER IS NOT A NEW PERSON AND HER PROSE IS NOT REWRITTEN. Thessaly
   Brun is `captives.CAPTIVES` row `thessaly_brun` and `zonecompanions.ESCORTS`
   row one. Her `walking`, `capture`, `narrator`, `loss_line`, `thanks`,
   `handover` and `retaken_line` are already authored in `zonecompanions.py`
   and not one word of them is touched here. Doc beats 2 and 26 are HANDOFFS to
   prose that already exists, and they are recorded in `HANDOFFS` rather than
   re-implemented, so that a pass reading the numbering does not conclude two
   beats went missing.

   FOUR MORE HANDOFFS ANSWER THE OTHER HALF OF THAT QUESTION. "One feature, one
   lesson" is only a real check if the features are counted against the
   SCREENS, not against this tuple — and four of the surfaces carrying most of
   a new player's first hour explain themselves already, in place, better than
   a beat could: the MCQ pane (#answer-here), the six puzzle trays
   (.puzzle-help), MISSING_RUNE's blanks (explainBlank) and the incantation
   list's own modal. They are rows 5, 6, 7 and 28, they carry no lines and no
   latch, and they exist so that a reader counting features against screens
   finds an answer where there was a hole.

3. SHE IS NEVER IN A FIGHT. `finalexam.CRUTCHES` holds PET — "a companion
   volunteering the one line you had forgotten", taken at LADDER RUNG SEVEN by
   `path_sum_ent`; it is the fifth ROW of that tuple, and this docstring used
   to call that rung five, which is where `the_companion`'s board line got its
   wrong number. A person talking inside an encounter is PET's shape, so every
   battle lesson is triggered BEFORE the first fight or AFTER it and there is
   no beat whose trigger is inside one. `validate()` checks the trigger prose
   for that.

   THE OPENING FRAME IS NOT THE FIGHT, and `the_code_fight` is the one beat
   that needs the distinction. It fires in `enterBattle`, on the branch that
   has just chosen the editor, on the frame the screen is built — before the
   timer's first tick has anything in it and before the player can have typed
   a character. She is describing the screen as it appears and is gone before
   the work starts. What rung seven forbids is help arriving DURING the work,
   volunteered, in response to how it is going; the four facts the cue may
   read (CUE_MAY_READ) draw the same line for the arrow.

4. A LESSON TAUGHT IS TAUGHT, AND THE LATCH IS IN THE SAVE. Not in
   `localStorage`: it has to survive an import, a new browser and a different
   machine, and the square panel has to be able to count what is left. `teach()`
   is the only writer in this file.

5. THE STATE IS DERIVED WHERE IT CAN BE. `speaker()` is a pure function of the
   save and reads `zonecompanions.sweep_fired()`, so a save written before this
   file existed answers correctly on its first load. Every reader goes through
   `_bucket()`, which returns {} for anything that is not a dict, so an old
   save, an empty save and a save somebody edited by hand all answer and none
   of them raises.

6. THE CURRICULUM SURVIVES ITS TEACHER. At the Interviewer's sweep every beat
   that never fired keeps its trigger and its latch and changes only its
   speaker and its channel: THE BOARD, on the wall of the empty square, one
   chalk line at a time. That is `Beat.board`, it costs one field, and it is
   already her own prop — it is in her authored capture lines twice.

Wiring is at the bottom, in WIRING, and what this needs from files it does not
own is in CONTRACT.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import captives
from . import config
from . import zonecompanions

# ---------------------------------------------------------------------------
# Who is speaking
# ---------------------------------------------------------------------------
# Two speakers, one derived from the save. There is no third, and `speaker()`
# is the only thing that decides which.

TEACHER_ID = "thessaly_brun"          # captives.CAPTIVE_BY_ID id. Never a new person.
TEACHER_NAME = "THESSALY BRUN"
TEACHER_PORTRAIT = "scholar"          # captives.SPRITES_ALLOWED member

SPEAKER_THESSALY = "thessaly"
SPEAKER_BOARD = "board"
SPEAKERS = (SPEAKER_THESSALY, SPEAKER_BOARD)

BOARD_NAME = "THE BOARD"
BOARD_PORTRAIT = ""                   # a wall has no face

CHANNEL_SAY = "say"                   # main.js say(who, lines, portraitKind)
CHANNEL_TOAST = "toast"               # main.js toast(title, body, kind)
CHANNELS = (CHANNEL_SAY, CHANNEL_TOAST)

SAY_LINES_MAX = 3                     # a dialogue box holds three and no more
TOAST_LINES = 1                       # a toast holds one, always

# The one interpolation in the whole curriculum, spelled out here so that
# nobody hard-codes a number into authored prose. See `_fill()` and beat 21.
COUNT_TOKEN = "{n}"


# ---------------------------------------------------------------------------
# The shape of a beat
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Beat:
    id: str               # the latch key, and the id the client posts
    order: int            # docs/13 §5.3's own beat number, gaps and all
    teaches: str          # one phrase, for the panel and for the self-check
    trigger: str          # prose, for the wiring pass
    site: str             # the docs/13 §7 work-list row that owns the trigger
    channel: str          # CHANNEL_SAY or CHANNEL_TOAST
    title: str            # the toast's title; "" for a say
    lines: tuple          # 1-3 for say, exactly 1 for toast
    board: str            # the one chalk line if she never got here. "" means
                          # the board cannot deliver this beat at all — see
                          # `speaker_for()`. Exactly one beat is allowed that.
    alt_lines: tuple = ()  # the variant used when nothing is left pending;
                           # beat 21 only, and `validate()` enforces that


@dataclass(frozen=True)
class Handoff:
    """A numbered entry in docs/13 §5.3 that is somebody else's prose already.

    These carry no lines and no latch. They exist so that a reader of `BEATS`
    who counts twenty-four rows against a document numbered to thirty finds
    the six missing numbers here instead of assuming they were dropped.
    """
    order: int
    name: str
    owner: str            # the module and symbol that already says it
    why: str


HANDOFFS = (
    Handoff(2, "the_doors and the_roads",
            "zonecompanions.ESCORTS[0].verb  ->  web/js/overworld.js",
            "Delivered by Overworld.setEscort/_offerEscortCaption and "
            "main.showEscortCaption from the server's walking flags, region "
            "description, mentor identity and oriented route requirements. "
            "Captions appear once per doorstep/exit per visit in the field "
            "sidebar, never during a measured run. The current houses all "
            "open mentorTalk; authored mender/smith signs and enterable "
            "interiors remain separate work. No second curriculum caption."),
    Handoff(5, "the_question",
            "web/index.html #answer-here  (setEditorMode('mcq'))",
            "The MCQ surface teaches itself, permanently, in the pane the "
            "editor would have been in: NOTHING TO TYPE ON THIS ONE, then "
            "where the answers are and that clicking one casts it. Ten of the "
            "first fourteen selections on a fresh save are entry.kind=mcq, "
            "measured, so this is most of a new player's first hour and a "
            "beat would be the loudest possible duplicate. Already wired and "
            "already correct; recorded here so that `one feature, one lesson` "
            "is checkable against the screens rather than only against the "
            "beats."),
    Handoff(6, "the_pile",
            "web/js/puzzleui.js .puzzle-help  (six trays)",
            "Every puzzle tray opens with its own sentence — drag or click "
            "the runes, depth is meaning, some do not belong — and there are "
            "six of them, one per puzzle kind. A beat would be a seventh "
            "explanation of six things that already explain themselves at the "
            "moment they are used, which is the rule cue refusal row 12 "
            "applies to the editor."),
    Handoff(7, "the_blanks",
            "web/js/main.js explainBlank()",
            "MISSING_RUNE's blanks are explained in words, in place, by "
            "explainBlank — which is also why CUE_REFUSED refuses to point an "
            "arrow at one. Four of the first fourteen selections on a fresh "
            "save are MISSING_RUNE, measured, so this surface is owed a "
            "lesson; it already has one, and this row is where a reader "
            "counting features against screens finds it."),
    Handoff(26, "the_slate",
            "zonecompanions.hand_over_early(state)",
            "The server hands the Slate over on rt_waking_road and carries "
            "her prose. main.consumeEscortResponse now retains the original "
            "move/travel escort_events and drainEscortNotices presents the "
            "gift on the free world screen, behind existing dialogue. Both "
            "side-panel travel and WorldUI travel feed it. No second grant, "
            "lesson acknowledgement or speech is authored by the curriculum."),
    Handoff(28, "the_incantation",
            "web/js/main.js showIncantList()'s modal",
            "SPEAK AN INCANTATION, in the world screen's ACTIONS list on the "
            "first frame of play. The incantation list carries its own "
            "explanation at the top of the modal that opens it — every enemy "
            "is a bound name, you "
            "attack by writing one line of Python that really does something "
            "to it, and a wrong line costs the turn and says which of the "
            "three layers it broke at. That is the lesson, it is already "
            "written, and it is on the screen you have to open to play one. "
            "This row is the decision, recorded: a second mode of combat is "
            "not missing from the curriculum, it is handed off."),
)


# ---------------------------------------------------------------------------
# The twenty-four
# ---------------------------------------------------------------------------
# Authored order, not emergent. `order` is docs/13 §5.3's own numbering so a
# reader can cross-reference a beat to the paragraph that decided it; the
# numbers missing from this tuple are in HANDOFFS above, and between the two
# the numbering runs 1..30 with no gap and no repeat.
#
# THE VOICE, because it is the thing most easily lost by an edit: plain,
# unhurried, dry. Nineteen years in one square and unimpressed by monsters. She
# does not exclaim, does not say "great job", does not say "let's", and never
# uses two sentences where one will do. `validate()` enforces the parts of that
# a machine can see — no exclamation mark, no second person cheerleading, no
# code, no problem name.
#
# AND EVERY NUMBER IN HER MOUTH IS READ OFF THE CODE THAT OWNS IT, because a
# schoolteacher who is confidently wrong about her own square is worse than one
# who says nothing. Nine rungs is forge.MAX_TIER. Eleven metals over sixteen
# regions is forge.METALS and forge.REGION_METAL, counted. Six counters is
# townui.TABS plus the portal tab in the one square that has one. Fourteen is
# world.BOSSES, world.KEYS and finalexam.BOSS_LADDER, which are the same
# fourteen. Rung seven is finalexam._rung_of(PET) — which is NOT PET's index in
# CRUTCHES, and this file had it as rung five from that index.

BEATS = (

    # -- PART ONE: THE FIELD ----------------------------------------------

    Beat(
        id="the_square", order=1,
        teaches="moving and interacting",
        trigger="The first frame of overworld control on a NEW save, in "
                "python_village. Not on a load, and not on either deep-link "
                "copy of the boot path.",
        site="main.js · M17",
        channel=CHANNEL_SAY, title="",
        lines=(
            "You will want to know where things are before you want to know "
            "anything else. I am Thessaly Brun and I have taught in this "
            "square for nineteen years.",
            "Walk with the arrows or with W, A, S and D. Stand on a thing and "
            "press space, and the thing will answer you.",
            "That is the whole of it. Everything else in this village is a "
            "door.",
        ),
        board="Arrows or WASD to walk. Space to speak to whatever you are "
              "standing on.",
    ),

    # KIND-NEUTRAL, and that is the whole design of this beat. It fires at the
    # mouth of the first encounter, where onNodeEnter has a marker and NOT a
    # problem: startNext() only learns the kind inside enterBattle, so anything
    # said here about the editor, RUN or CAST is said blind. The first
    # encounter on a clean save is a CODE_READING question with entry.kind mcq,
    # chosen by the ramp and measured on a fresh db, and renderMcq sets
    # #editor-host, #btn-run and #btn-submit to display:none. The version of
    # this beat that named those three named three hidden objects, in the one
    # lesson a new player is guaranteed to get. What is left here is true of
    # all four kinds; the rest of it is the beat below.
    Beat(
        id="the_fight", order=3,
        teaches="what an encounter is",
        trigger="The mouth of the FIRST encounter, in onNodeEnter, BEFORE the "
                "encounter is started, so the fight opens when she stops. She "
                "is never inside one. Reached by walking onto a marker or by "
                "NEXT ENCOUNTER (N) in the world screen's ACTIONS list — both "
                "go through startNext(), so one beat covers both doors.",
        site="main.js · M12",
        channel=CHANNEL_SAY, title="",
        lines=(
            "That is a question wearing a monster. It will ask you for Python "
            "and it will not take anything else.",
            "Some of them want a spell written out. Some want one line taken "
            "from a list, or a pile of them put in order. The screen says "
            "which as it opens, and it says it where the writing would have "
            "gone.",
            "Nothing in this village dies of a wrong answer. Go on.",
        ),
        board="A monster is a question. The screen says which kind as it "
              "opens. A wrong answer is not fatal here.",
    ),

    # THE OTHER HALF, and it says only what #editor-caption does not.
    # #editor-caption is permanent, it is on every code fight, and it already
    # carries WRITE YOUR PYTHON HERE, THEN PRESS CAST and both keystrokes. Cue
    # refusal row 12 refuses to point an arrow at that box for exactly that
    # reason, and a beat re-explaining it would be the same duplicate in more
    # words. What the caption does not carry is what either button COSTS.
    Beat(
        id="the_code_fight", order=4,
        teaches="RUN costs nothing and only CAST is scored",
        trigger="The first encounter that opens with an editor in it: in "
                "enterBattle, on the else-branch that has just chosen the "
                "editor over a puzzle or a question, on the frame the screen "
                "is built and before the player can have typed anything. On a "
                "clean save that is the third encounter, not the first.",
        site="main.js · M12b",
        channel=CHANNEL_SAY, title="",
        lines=(
            "The caption over that box tells you where to type and which "
            "button casts. It does not tell you what either one costs you, "
            "and that is the part worth knowing.",
            "RUN is free. Press it as often as you like. Nothing is spent, "
            "nothing is recorded, and nobody is counting.",
            "CAST answers the question. That one is scored, and it is the "
            "only one that is.",
        ),
        board="RUN is free and unrecorded. CAST is the one that is scored.",
    ),

    Beat(
        id="the_trials", order=8,
        teaches="the trials list, and what a locked trial will not tell you",
        trigger="The next visible battle trials tab after the first encounter, "
                "whatever the result. Never on the overworld or MCQ answer pane.",
        site="main.js · M13",
        channel=CHANNEL_SAY, title="",
        lines=(
            "The list on the right is the trials. The open ones show you what "
            "goes in and what should come out.",
            "The locked ones do not. They will name the shape of what broke "
            "and never the value, which is the same courtesy an examiner "
            "extends.",
        ),
        board="The trials are on the right. A locked trial names the shape of "
              "a failure, never the value.",
    ),

    # THREE GO AND TWO STAY, read off main.js's TAB_SEAL, which is
    # { spells: HINTS, tactics: PROBES, vision: VISUALS }. TRIALS and APPROACH
    # have no entry, applySeal() hides a tab only where TAB_SEAL has one, and
    # main.js says "TRIALS is never sealed" in its own comment. The order is
    # finalexam._rung_of: HINTS at rung 3, PROBES at 6, VISUALS at 8. Three of
    # the fourteen rungs touch a tab and the other eleven do not.
    #
    # AND APPROACH IS NOT A RESTATEMENT OF THE QUESTION. paintApproach draws a
    # textarea with SCORE MY EXPLANATION under it and the sentence "Interviewers
    # score this as heavily as the code" over it, and it is the DEFAULT tab in a
    # measured run. The plain statement of the problem is #problem-statement,
    # which is not a tab at all. A player told otherwise never types in the one
    # panel that teaches interview communication.
    Beat(
        id="the_tabs", order=9,
        teaches="the five side panels, and why three of them get taken away",
        trigger="A visible battle after two encounters; never on the overworld.",
        site="main.js · M13",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Five panels on the right and you are owed all five today. "
            "TRIALS, TACTICS, SPELLS, APPROACH, VISION.",
            "TACTICS reads the creature. SPELLS is the ladder of hints. "
            "APPROACH is a box you write in BEFORE you write any Python — "
            "your plan, the structure, what it costs — and what you put in it "
            "is scored. VISION draws the working.",
            "The fourteen will take three of them off you, one at a time, in "
            "a fixed order. That is not a cruelty. It is the measurement "
            "arriving slowly enough for you to survive it.",
        ),
        board="SPELLS goes first, then TACTICS, then VISION. TRIALS and "
              "APPROACH are yours to the end.",
    ),

    Beat(
        id="saving", order=10,
        teaches="it saves itself",
        trigger="The first return to the overworld after an encounter.",
        site="main.js · M13",
        channel=CHANNEL_TOAST, title="SHE WRITES IT DOWN",
        lines=(
            "It writes itself down after everything you do, on this machine, "
            "without being asked. You will not lose an afternoon in here.",
        ),
        board="It saves itself after everything, on this machine.",
    ),

    Beat(
        id="stamina", order=11,
        teaches="what the health bar is for",
        trigger="The first return to the overworld below full stamina.",
        site="main.js · M13",
        channel=CHANNEL_TOAST, title="WHAT THE BAR IS",
        lines=(
            "Stamina is not your life. It is how many more questions you get "
            "to be wrong about today.",
        ),
        board="Stamina is how many more questions you get to be wrong about "
              "today.",
    ),

    Beat(
        id="the_fall", order=12,
        teaches="losing an encounter",
        trigger="The first encounter that ends unsolved, once the player is "
                "back on the overworld.",
        site="main.js · M13",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Now you know what that costs. Stamina, and the walk back.",
            "It does not cost you the question. That family will come round "
            "again wearing a different face, and you will have had a "
            "fortnight's more practice when it does.",
        ),
        board="A wrong answer costs stamina and a walk. It never costs the "
              "question.",
    ),

    Beat(
        id="the_dying", order=13,
        teaches="what dying takes and what it cannot take",
        trigger="The first death, inside partyui.showTheFall's onClose, after "
                "the death screen is dismissed.",
        site="main.js · M14",
        channel=CHANNEL_SAY, title="",
        lines=(
            "You lost gold, and ground, and whatever you were carrying. That "
            "is what dying is for. If it took nothing from you it would mean "
            "nothing.",
            "It did not touch what you can do. Your attempts, your skills, "
            "the schedule, the records — none of that was on you when you "
            "fell. It is in the book, and I keep the book.",
        ),
        board="Dying costs gold, ground and carry. It never costs a skill, an "
              "attempt or a record.",
    ),

    # -- PART TWO: THE TOWN, AND WHAT YOU KEEP -----------------------------

    # NO KEY OPENS THIS. The only global keydown handler binds n, f, Escape and
    # Space; overworld.js binds the arrows, WASD, Escape and Space/Enter. The
    # single way into the square is the THE TOWN SQUARE button in the world
    # screen's ACTIONS list, plus the ledger row beside it. "One key, from
    # anywhere in a town" named a key that does not exist, in the first
    # sentence she says about the town.
    #
    # AND THE COUNT IS SIX HERE. tabsHere() returns townui.TABS — mender,
    # smith, shelf, broker, voices — plus PORTAL_TAB wherever the server sends
    # a portal, which is python_village and nowhere else. A new save starts in
    # python_village, so the square this beat first fires in always has six.
    Beat(
        id="the_square_panel", order=14,
        teaches="the town panel, and how many counters are in it",
        trigger="The first time the town panel is opened, after the body has "
                "painted once.",
        site="townui.js · T2",
        channel=CHANNEL_SAY, title="",
        lines=(
            "THE TOWN SQUARE is a button, in the ACTIONS list on the world "
            "screen. Every region has a square and the button is always in "
            "the same place.",
            "Six counters in this one and five in every other. I will "
            "introduce you to each as you reach it.",
            "Nothing in there is trying to kill you. It is the only screen in "
            "the realms I can say that about.",
        ),
        board="THE TOWN SQUARE is a button in the ACTIONS list. Six counters "
              "here, five in every other square.",
    ),

    Beat(
        id="town_mender", order=15,
        teaches="THE MENDER, free, and why",
        trigger="The first paintBody() with TAB === 'mender'.",
        site="townui.js · T1",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Margit Orr. She charges nothing and she will tell you why before "
            "you ask her.",
            "Health decides how many attempts you get. Charging a learner for "
            "attempts is charging them for learning, and Margit will not do "
            "it.",
        ),
        board="Margit Orr mends for free. Health is attempts, and attempts "
              "are not for sale.",
    ),

    Beat(
        id="town_smith", order=16,
        teaches="FERRO, armour integrity, and the two ways it comes back",
        trigger="The first paintBody() with TAB === 'smith'.",
        site="townui.js · T1",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Ferro. Armour has integrity, integrity wears down every time you "
            "are wrong, and he sells it back by the point.",
            "If you cannot pay for all of it he mends the cheapest piece "
            "first. That is not generosity. It is the most points for your "
            "gold, and he assumes you can do the sum.",
            "There is a second price and it is not gold. ARMORER'S FORGE on "
            "the world screen hands you a broken program instead; mend that "
            "and the piece it was tagged for mends with it.",
        ),
        board="Ferro sells armour integrity by the point. ARMORER'S FORGE "
              "mends a piece for a fixed program instead of for gold.",
    ),

    Beat(
        id="town_shelf", order=17,
        teaches="the vendor, the region band and the restock clock",
        trigger="The first paintBody() with TAB === 'shelf'.",
        site="townui.js · T1",
        channel=CHANNEL_SAY, title="",
        lines=(
            "The vendor. Potions are brewed to what this place can reach, not "
            "to what you have grown into — so a shallow region sells shallow "
            "however grand you have become.",
            "The shelf refills every sixth encounter you actually clear. "
            "Losing buys nothing.",
        ),
        board="The shelf is banded by the region, not by your level. It "
              "refills every sixth cleared encounter.",
    ),

    Beat(
        id="town_broker", order=18,
        teaches="ORIN TALLOW, one trial at a time, quoted before the work",
        trigger="The first paintBody() with TAB === 'broker'.",
        site="townui.js · T1",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Orin Tallow, the assayer. One trial open at a time, and he "
            "quotes it before the work rather than after it.",
            "Read the quote. He is honest and he is not generous, and those "
            "are different things.",
        ),
        board="Orin Tallow: one trial at a time, quoted before the work.",
    ),

    # THE FIFTH COUNTER, which had no lesson while the beat above promised one
    # for every counter in the square. banter.SPEAKERS is forty-seven people
    # and the tab is ONE call for all of them, which is why what they say
    # agrees with itself about the weather.
    Beat(
        id="town_voices", order=19,
        teaches="THE VOICES, and what the people here have noticed",
        trigger="The first paintBody() with TAB === 'voices'. The same "
                "forty-seven people as TALK TO PEOPLE HERE on the world "
                "screen — townui.talkOnTheOverworld and this tab are one "
                "banter.view call each, so this beat covers both doors and "
                "the world-screen button needs no beat of its own.",
        site="townui.js · T1",
        channel=CHANNEL_SAY, title="",
        lines=(
            "The voices. Whoever is standing in this square, and what they "
            "have noticed about the place, about your armour, and about what "
            "is one road away.",
            "They are not a menu and they are not a service. They are people "
            "who live here, and they say something else when your kit "
            "changes.",
        ),
        board="The voices are whoever is standing in the square, reading the "
              "place and your kit.",
    ),

    # ELEVEN METALS, SIXTEEN REGIONS, AND NONE FROM HERE. forge.METALS is 11
    # and forge.REGION_METAL is 16 entries drawn from those 11, so five metals
    # are shared by two regions each — keybrass, marshsilver, faultsteel,
    # heartwood_iron, doubling_steel. forge.NO_METAL_REGIONS is
    # ('python_village',), which is the square she is standing in while she
    # says it. "Every region leaves a different metal" was wrong twice in one
    # clause and wrong about the ground under her feet.
    Beat(
        id="the_forge", order=20,
        teaches="the nine rungs and the region metals",
        trigger="The first time the forge panel is drawn on the GEAR screen.",
        site="main.js · M16",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Nine rungs. A blade climbs them on metal the creatures leave "
            "behind — eleven metals over sixteen regions, five of them shared "
            "by two, and not one of them from this village.",
            "You do not buy that ladder. You walk it, and the blade you "
            "finish with is the one you signed.",
        ),
        board="Nine rungs. Region metals climb the blade. You walk that "
              "ladder; you do not buy it.",
    ),

    Beat(
        id="the_belt", order=21,
        teaches="potions and the belt",
        trigger="The first time a potion enters the pouch, on the overworld. "
                "Never in a fight, which is why this is a beat and not an "
                "arrow — see docs/13 §1.3 row 17.",
        site="main.js · M13 area (pouch gain, on the world screen)",
        channel=CHANNEL_TOAST, title="SOMETHING FOR THE BELT",
        lines=(
            "A potion goes on your belt, and the belt is the one thing in a "
            "fight that does not end your turn.",
        ),
        board="The belt is the one thing in a fight that does not end your "
              "turn.",
    ),

    Beat(
        id="gear", order=22,
        teaches="slots, rarity, elements and resists",
        trigger="The first item equipped, in paintCharacter().",
        site="main.js · M16",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Slots, a rarity, and an element each. A resist is worth more "
            "than a number on the day the ground is on fire.",
            "Read an item's lines, not its colour. The colour only tells you "
            "how rare it was to find.",
        ),
        board="Read an item's lines, not its colour. Resists matter on the "
              "ground they are for.",
    ),

    # RUNG SEVEN. PET is the fifth ROW of finalexam.CRUTCHES and the seventh
    # RUNG of the ladder: `_rung_of` maps a crutch to the boss that takes it,
    # and PET's is path_sum_ent, which is world.BOSSES index 7. The board line
    # here said rung five, which is the tuple index wearing the ladder's name.
    Beat(
        id="the_companion", order=23,
        teaches="the companion that walks with you",
        trigger="The first pet found, inside partyui.showPetFound's onClose.",
        site="main.js · M15",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Something has decided to come with you. It will speak in a "
            "fight, until the ladder takes that away from you as well.",
            "Pay it some attention. It is the only thing in the realms that "
            "gets better without being graded.",
        ),
        board="A companion speaks in a fight until the ladder takes it. Rung "
              "seven.",
    ),

    # THE STONE, and it is NOT the spaced-repetition schedule. Game.shrine
    # draws a riddle from world.SHRINE_QUESTIONS; shrine_answer pays three
    # stamina, six focus and twelve experience for a right one and moves RECALL
    # plus the question's own skill. The schedule and the records the beat
    # above promises death cannot take are srs.py, and they move on graded
    # evidence — which a roadside riddle is not, and which is exactly why a
    # measured run may read the stone and may not be paid for reading it.
    Beat(
        id="the_shrine", order=24,
        teaches="the roadside shrine and what a riddle pays",
        trigger="The first press of MEMORY SHRINE on the world screen, before "
                "the stone is drawn.",
        site="main.js · M19",
        channel=CHANNEL_SAY, title="",
        lines=(
            "A shrine is a stone with a question on it. Twenty seconds, one "
            "line, and WALK ON is always there if you would rather not.",
            "Right pays you stamina, focus and experience, and it moves two "
            "of the records I keep. Wrong costs you nothing but the twenty "
            "seconds.",
        ),
        board="A shrine is a stone, twenty seconds and one line. Right pays; "
              "wrong costs nothing.",
    ),

    # OFFERED FROM LEVEL ONE AND PROMPTED BY NOTHING. classes.CLASSES is six,
    # each with three branches; Game.choose_class refuses a class already taken
    # and never a level; and the way in is a THE SIX DISCIPLINES button inside
    # partyui that one ledger line mentions in passing. A system with no gate
    # and no prompt is a system most players never open, which makes it the
    # cheapest lesson in the set to be missing.
    Beat(
        id="the_disciplines", order=25,
        teaches="the six disciplines and the tree under one",
        trigger="The first time the party screen is painted with no class "
                "chosen, in paintCharacter, whichever screen opened it.",
        site="partyui.js · P1",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Six disciplines, and you may take one now. Nothing is holding "
            "them back and nothing will prompt you — the way in is a button "
            "on the party screen that says THE SIX DISCIPLINES.",
            "Under each is a tree of three branches, bought with the points a "
            "level hands you. The first change of mind is free, so taking one "
            "early costs you nothing you cannot undo.",
        ),
        board="Six disciplines, offered from level one, behind the THE SIX "
              "DISCIPLINES button. The first change of mind is free.",
    ),

    # -- PART THREE: THE ROAD ---------------------------------------------

    # THE WIN CONDITION, which had no lesson at all — a player could walk the
    # whole curriculum without once being told what they were trying to do.
    # world.BOSSES is fourteen, world.KEYS is fourteen, finalexam.BOSS_LADDER
    # is those same fourteen in order, and progression.PORTAL_NEED is all of
    # them. Twelve of the fourteen rungs take a capability and the first two
    # take none. Every one of the fourteen keys opens a road. The portal stands
    # in python_village, and its own payload says practical_requires_keys is
    # False — which is the sentence the beat below exists for, said here first
    # so the two never disagree.
    Beat(
        id="the_keys", order=27,
        teaches="the fourteen bosses, their keys, and the door they open",
        trigger="Whichever comes first: the first boss marker entered on the "
                "overworld, or the first press of CHALLENGE BOSS.",
        site="main.js · M20",
        channel=CHANNEL_SAY, title="",
        lines=(
            "Fourteen of them are out there. Twelve take something off you "
            "when they go down, all fourteen leave a key, and every key opens "
            "a road you could not walk before.",
            "All fourteen keys together open the door standing in this "
            "village. That door is what you are walking towards, and it is "
            "the end of the story rather than the measure of you.",
        ),
        board="Fourteen bosses, fourteen keys, fourteen roads. All fourteen "
              "keys open the door in this village.",
    ),

    Beat(
        id="the_practical", order=29,
        teaches="the INTERVIEW door is always open",
        trigger="Whichever comes first: the first road walked, queued behind "
                "the Slate handover, or the first press of the INTERVIEW nav "
                "button.",
        site="main.js · M18",
        channel=CHANNEL_SAY, title="",
        lines=(
            "There is a door on the menu marked INTERVIEW. It is open now. It "
            "was open before you arrived and it will be open when all this is "
            "finished.",
            "Nothing you do out here opens it and nothing closes it. Not the "
            "keys, and not the door the keys open. It is a measurement, not a "
            "prize, and the only honest thing to do with a measurement is "
            "take it whenever you want to know.",
        ),
        board="The INTERVIEW door on the menu is always open. Nothing here "
              "opens or closes it, keys included.",
    ),

    # The only beat with no chalk line, on purpose, and the only one with two
    # variants. See `speaker_for()` for what the empty `board` means and
    # docs/13 §6.3 for the argument.
    Beat(
        id="the_last_lesson", order=30,
        teaches="what is left on the board when she goes",
        trigger="Once, at the sweep, immediately after "
                "zonecompanions.scene('thessaly_brun') has played out.",
        site="main.js · the capture scene's onClose",
        channel=CHANNEL_SAY, title="",
        lines=(
            "There is still a list on that board. {n} things, I think, that "
            "we never got round to.",
            "It stays on the wall. Read it where you stand, when you reach "
            "the thing it is about. Chalk is not a worse teacher than I am; "
            "it is only a slower one.",
        ),
        board="",
        alt_lines=(
            "There is nothing left on that board. You have been through every "
            "door on this square and asked every question in it, and the man "
            "at the gate does not know that yet.",
            "Go and finish it. I will not be here to mark it, which is how it "
            "should be — a thing you can only do while somebody is watching "
            "is not a thing you can do.",
        ),
    ),
)


BY_ID = {row.id: row for row in BEATS}
ORDER = tuple(row.id for row in sorted(BEATS, key=lambda r: r.order))
LAST_LESSON_ID = "the_last_lesson"


# ---------------------------------------------------------------------------
# The cue's policy
# ---------------------------------------------------------------------------
# The arrow itself is CSS and `web/js/tutor.js`. What lives HERE is everything
# about it that a client must not be free to re-decide: which controls may ever
# be pointed at, how long a control stays cueable, and how long the player has
# to have stopped. Retirement in particular is server-side so that the client
# cannot drift from it — docs/13 §7.1 F10.
#
# THE SENTENCE THAT GOVERNS THE WHOLE TABLE:
#
#   The cue may point at a control because of what the control IS, and never
#   because of what the last attempt DID.
#
# and its corollary:
#
#   The cue points at containers, never at members of a set the player is
#   being asked to choose from.

CUE_RETIRE_AT = 3          # three shows OR three uses, whichever comes first
CUE_PER_ENCOUNTER = 2      # at most two appearances in one encounter
CUE_DWELL_MS = 8000        # idle before the cue appears, code/puzzle/incant
CUE_DWELL_MCQ_MS = 2000    # the one off-tab MCQ case, which reads as broken

KIND_CODE = "code"
KIND_MCQ = "mcq"
KIND_PUZZLE = "puzzle"
KIND_INCANT = "incant"
KINDS = (KIND_CODE, KIND_MCQ, KIND_PUZZLE, KIND_INCANT)

PLACEMENT_EDGE = "edge"    # on the control's left edge, overhanging 3px
PLACEMENT_UNDER = "under"  # in the control's bottom padding, for a tab


@dataclass(frozen=True)
class Control:
    """One row of the only list of things that may ever be cued."""
    id: str
    label: str            # what the player reads on it
    selector: str         # mirrored from docs/13 §4 for tutor.js's REGISTRY
    placement: str
    priority: int         # lower goes first
    kinds: tuple
    why: str              # why this is INTERFACE and not PROBLEM


# A CUE IS NEVER PLACED INSIDE A DISABLED HOST, and this is the only place the
# rule is written on the data rather than on the CSS. A `.cue` is a CHILD of the
# control it points at, so the host's opacity composites the whole subtree:
# game.css:72 sets .btn:disabled{opacity:.38} and metal.css:292 tightens it to
# .3. Measured on #btn-submit during a RUNE_ASSEMBLY encounter, where main.js
# keeps CAST disabled until G.puzzle.ready() — the cue renders (76,65,91) where
# the same cue on the same ENABLED button renders (186,149,215), and its
# contrast against the ground beneath it falls from 6.13:1 to 1.75:1. Worse
# than dim: the keyline composites too, so the cue's colour becomes
# GROUND-DEPENDENT again, which is the one property it exists to guarantee. `cast`'s `kinds`
# includes "puzzle", so this table invites exactly that placement; tutor.js's
# eligibility check is what has to refuse it, and docs/13 §7.2 J2 is where that
# is written down for the client. The same paragraph is in game.css beside
# `.has-cue`.

CUE_CONTROLS = (
    Control("run", "RUN", "#btn-run", PLACEMENT_EDGE, 10, (KIND_CODE,),
            "There is a button that tries your code. True of every code fight "
            "ever served; swap the question and the cue is identical."),
    Control("cast", "CAST", "#btn-submit", PLACEMENT_EDGE, 20,
            (KIND_CODE, KIND_PUZZLE),
            "There is a button that answers the question. THAT the player ran "
            "is a fact about the control; WHAT came back from the run is "
            "never read. On a puzzle it becomes eligible the moment ready() "
            "clears `disabled`, which is a property of the control."),
    Control("inc_cast", "CAST", "#editor-pane .inc-cast", PLACEMENT_EDGE, 20,
            (KIND_INCANT,),
            "Same shape as `cast`. IncantationUI owns the pane and carries "
            "its own cast control."),
    Control("rune", "the pile", "#puzzle-host .rune-tray .rune",
            PLACEMENT_EDGE, 10, (KIND_PUZZLE,),
            "RUNE_ASSEMBLY only. The pile is mcq.shuffle, so position in it "
            "carries no ordering information: pointing at its head says "
            "`these are draggable` and nothing else. THE OVERLAP WAS "
            "CONSIDERED: puzzleui.js:35 already says `drag or click runes "
            "from the pile` in words at the top of the tray, and cue refusal "
            "row 12 refuses the editor for having a caption. This row "
            "survives that rule because the tray sentence is above the pile "
            "and the cue is ON it — the caption says the pile can be dragged, "
            "the arrow says WHICH PILE, and a player who has read neither has "
            "a stationary screen. If the tray text ever moves onto the runes "
            "themselves, this row goes. THIS IS ALSO THE ONE ROW WITH A "
            "TRIPWIRE — see CUE_TRIPWIRE."),
    Control("trials_tab", "TRIALS",
            "#battle-side-tabs button[data-tab=\"trials\"]",
            PLACEMENT_UNDER, 5, (KIND_MCQ,),
            "Fired only when the kind is mcq and #battle-side-body holds no "
            ".list-item — the player navigated off the tab and the answers "
            "went with it. It points at the container, never at a choice."),
)

CUE_BY_ID = {row.id: row for row in CUE_CONTROLS}
CUE_IDS = tuple(row.id for row in CUE_CONTROLS)


@dataclass(frozen=True)
class Refusal:
    """A cue somebody will propose, and the reason it is already refused.

    Every row here was decided in docs/13 §1.3 or §4 and is repeated as data so
    that "we considered that" is checkable rather than remembered.
    """
    target: str
    verdict: str          # "PROBLEM" or "INTERFACE"
    why: str


VERDICT_PROBLEM = "PROBLEM"
VERDICT_INTERFACE = "INTERFACE"

CUE_REFUSED = (
    Refusal("the visible trials all passed, point at CAST", VERDICT_PROBLEM,
            "Reads the run report. `your solution looks right, submit it` is "
            "COACH wearing an arrow."),
    Refusal("a visible trial failed, point at TRIALS or the failing line",
            VERDICT_PROBLEM,
            "WEAKNESS_MAP and COACH. The single most tempting cue in the game "
            "and the most clearly refused, in every mode."),
    Refusal("a hidden trial failed, point at anything", VERDICT_PROBLEM,
            "Worse than the visible one: the locked trials exist precisely to "
            "withhold this."),
    Refusal("the player is idle and losing, point at RETREAT, SPELLS or the "
            "Mender", VERDICT_PROBLEM,
            "`you are losing, go and get help` is MENTOR plus a judgement of "
            "the attempt."),
    Refusal("the clock is past target_seconds, point at anything",
            VERDICT_PROBLEM,
            "UNLIMITED_TIME is rung 10 of the ladder. An arrow that appears "
            "because time passed is a clock crutch."),
    Refusal("an MCQ choice, any .list-item", VERDICT_PROBLEM,
            "Seven of the nine authored MCQ answer keys in the shipped corpus "
            "are index 0, and the client posts the index it rendered. An "
            "arrow on the first choice would be an arrow on the correct "
            "answer most of the time. Refused on evidence AND on the "
            "container rule."),
    Refusal("a SPOT_THE_FLAW code line", VERDICT_PROBLEM,
            "The question is WHICH LINE. An arrow on a line is the answer "
            "with a triangle in front of it."),
    Refusal("a COMPLEXITY_MATCH option", VERDICT_PROBLEM,
            "The question is WHICH OPTION. Same shape."),
    Refusal("a BREAK_IT quick-case button", VERDICT_PROBLEM,
            "Those six buttons are named edge cases. Pointing at one is "
            "WEAKNESS_MAP delivered as a suggestion."),
    Refusal("an incantation move, enemy or hole", VERDICT_PROBLEM,
            "Choosing a move and choosing a target ARE the encounter, and the "
            "holes are inputs. The container rule, third application."),
    Refusal("a __BLANK__ slot in the starter code", VERDICT_INTERFACE,
            "Refused anyway: explainBlank() already says this once, in words, "
            "better. Two explanations of one thing is worse than one."),
    Refusal("the editor, when it is empty and unfocused", VERDICT_INTERFACE,
            "Refused anyway: #editor-caption owns that box, and the cue never "
            "covers text."),
    Refusal("RESET and RETREAT", VERDICT_INTERFACE,
            "Refused anyway: they are exits, and a tutorial that points at "
            "RETREAT teaches quitting."),
    Refusal("the five side tabs, in a code fight", VERDICT_INTERFACE,
            "Refused anyway: there is no horizontal room inside a tab, and "
            "the two that would matter are capabilities the ladder removes."),
    Refusal("a belt slot when health is low", VERDICT_INTERFACE,
            "Refused anyway, and moved to the curriculum instead: the belt's "
            "lesson is `the one thing that does not end your turn`, and that "
            "is a sentence, not an arrow. It is beat 16."),
    Refusal("a TRACE or STATE_PREDICT text input", VERDICT_INTERFACE,
            "Refused anyway: a text field has a caret, a placeholder and a "
            "label of its own."),
    Refusal("anything at all, during a measured run", VERDICT_PROBLEM,
            "Two independent reasons. COMPARABILITY: a cue present on fight 3 "
            "and retired by fight 40 is a difference between two runs that "
            "were meant to be the same measurement. And the cheapest correct "
            "answer to `is this sealed` is not to have it there."),
)

CUE_TRIPWIRE = (
    "The `rune` control is legal ONLY because the RUNE_ASSEMBLY pile is "
    "mcq.shuffle and position in a shuffle carries no information. If shuffle "
    "is ever sorted, seeded to put distractors last, ordered by difficulty or "
    "otherwise made meaningful, DELETE the `rune` control the same day: it "
    "becomes a leak. corpus/validate.py checks the shuffle's LENGTH and "
    "nothing else — an identity permutation passes it, and an identity "
    "permutation is the solution in order — so the assertion that catches "
    "this had to be written on purpose. It is "
    "tests/test_corpus.py::TestCorpus::"
    "test_the_rune_pile_is_never_the_solution_in_order, it is written, and "
    "puzzleui.js's fallback for a missing shuffle is now an EMPTY pile rather "
    "than the authored order, which was the same leak reachable a second way."
)

# The four facts the cue is allowed to read, and there is no fifth.
CUE_MAY_READ = (
    ("KIND", "which of code/mcq/puzzle/incant the screen is in, read from the "
             "DOM and never passed in"),
    ("ELIGIBILITY", "for each control in CUE_CONTROLS: in the document, not "
                    "disabled, actually rendered"),
    ("USE", "how many times the player has pressed each control. A count of "
            "presses, never an outcome"),
    ("IDLE", "milliseconds since the last keystroke, click or key. A "
             "millisecond count cannot encode a Python question"),
)

CUE_MAY_NOT_READ = (
    "the problem", "the statement", "the pattern", "the starter code",
    "the run report", "the trial results", "the grade", "the score",
    "the timer", "the enemy", "the player's skills", "the hint tree",
    "anything derived from any of them",
)

# THE SEAL CLASS IS NOT `interview-mode`, AND THAT IS A CORRECTION.
#
# This table used to name `body.interview-mode` as the class that switches the
# cue off, because it is the class the battle screen already had. It is the
# wrong signal and the reason is a measured one: main.js's `returnToWorld()`
# removes `body.interview-mode` and nulls `G.interview` WHILE THE MEASURED RUN
# IS STILL OPEN SERVER-SIDE — RETREAT reaches it mid-run, and docs/10 §4b.I
# establishes that the player is on the overworld between two questions. A
# client gated on that class is blind in exactly the gap docs/13 §7.4 M13 hangs
# five `tutor.beat()` calls in.
#
# So the class is its own, carried from the server's own answer
# (`Game._run_is_open()`, served on /api/state as `run_open`) and set and
# cleared independently of the encounter. `interview-mode` cannot simply be
# left on instead: it also drives the palette drain, so keeping it up on the
# overworld would change how the game looks, which is a bigger change than a
# second class.
#
# The lessons need none of this. `/api/lesson` returns {} when the run is open
# and `teach()` defaults `run_open` to True, so the server is the authority and
# a client that forgets to check is refused rather than obeyed. The class
# exists for the ARROW, which has no round-trip per frame.
SEALED_BODY_CLASS = "run-open"
RUN_OPEN_FIELD = "run_open"        # the boolean /api/state carries

CUE_POLICY = {
    "retire_at": CUE_RETIRE_AT,
    "per_encounter": CUE_PER_ENCOUNTER,
    "dwell_ms": {KIND_CODE: CUE_DWELL_MS, KIND_PUZZLE: CUE_DWELL_MS,
                 KIND_INCANT: CUE_DWELL_MS, KIND_MCQ: CUE_DWELL_MCQ_MS},
    "kinds": list(KINDS),
    "setting": "cues",
    "off_body_class": "no-cues",
    "sealed_body_class": SEALED_BODY_CLASS,
    "sealed_field": RUN_OPEN_FIELD,
    "one_at_a_time": True,
    "aria": "none — it is a decoration over a control that is already "
            "focusable and already labelled",
}


def cue_registry() -> list:
    """CUE_CONTROLS as plain JSON, for tutor.js's REGISTRY.

    Served rather than re-typed: two copies of this table is how the client
    ends up cueing something this file has already refused.
    """
    return [{"id": row.id, "label": row.label, "selector": row.selector,
             "placement": row.placement, "priority": row.priority,
             "kinds": list(row.kinds), "why": row.why}
            for row in sorted(CUE_CONTROLS, key=lambda r: (r.priority, r.id))]


# ---------------------------------------------------------------------------
# The save
# ---------------------------------------------------------------------------
# One key, two buckets. `beats` is a LIST of ids so that a hand-edited save
# heals on the next write the way zonecompanions._write_bucket's does, and the
# two cue counters are DICTS of id -> int because that is what they are.
#
# THE LATCH IS THE AUTHORITY HERE, unlike zonecompanions', because there is
# nothing to derive a taught lesson from. That is why `teach()` is the only
# writer in the file and why it latches before it returns anything.

LESSON_KEY = "lessons"
SETTING_KEY = "cues"
SETTING_DEFAULT = True


def new_lesson_state() -> dict:
    """Add to engine.DEFAULT_STATE under LESSON_KEY. Forward-fills on load.

    An old save gains this on its next load with nothing taught and no counter
    set, which is exactly right: a player who has been playing for a week has
    not had the lesson, and will get it the next time a trigger fires.
    """
    return {"beats": [], "cue": {"shown": {}, "used": {}}}


def _bucket(state) -> dict:
    """Read-only view of the latch. Never writes; `_write_bucket` does that."""
    raw = state.get(LESSON_KEY) if isinstance(state, dict) else None
    return raw if isinstance(raw, dict) else {}


def _beats_list(state) -> list:
    value = _bucket(state).get("beats")
    return [b for b in value if isinstance(b, str)] if isinstance(value, list) else []


def _cue_bucket(state) -> dict:
    raw = _bucket(state).get("cue")
    return raw if isinstance(raw, dict) else {}


def _counter(state, kind: str) -> dict:
    raw = _cue_bucket(state).get(kind)
    if not isinstance(raw, dict):
        return {}
    return {k: int(v) for k, v in raw.items()
            if isinstance(k, str) and isinstance(v, int)
            and not isinstance(v, bool) and v >= 0}


def _write_bucket(state: dict) -> dict:
    """The repair. Every writer goes through here, so a save with the wrong
    type in any of the three slots is healed rather than raising."""
    raw = state.get(LESSON_KEY)
    if not isinstance(raw, dict):
        raw = new_lesson_state()
        state[LESSON_KEY] = raw
    if not isinstance(raw.get("beats"), list):
        raw["beats"] = []
    else:
        raw["beats"] = [b for b in raw["beats"] if isinstance(b, str)]
    cue = raw.get("cue")
    if not isinstance(cue, dict):
        cue = {}
        raw["cue"] = cue
    for kind in ("shown", "used"):
        bucket = cue.get(kind)
        if not isinstance(bucket, dict):
            cue[kind] = {}
        else:
            cue[kind] = {k: int(v) for k, v in bucket.items()
                         if isinstance(k, str) and isinstance(v, int)
                         and not isinstance(v, bool) and v >= 0}
    return raw


# ---------------------------------------------------------------------------
# The gates, and there are exactly two
# ---------------------------------------------------------------------------

def available_in(mode: str) -> bool:
    """Adventure Mode only, on the same gate captives.py uses.

    This is the WHOLE of this module's opinion about the measured run. It does
    not import finalexam, it does not call sealed(), and it has no per-lesson
    exception: a schoolteacher does not exist in a measurement, so nothing she
    would have said has to be individually refused.
    """
    return captives.available_in(mode)


def may_teach(mode: str = config.MODE_ADVENTURE, run_open: bool = True) -> bool:
    """The second gate, and it is the caller's fact rather than ours.

    `run_open` is `engine.Game._run_is_open()` — is a measured run open AT ALL,
    question on screen or not. It is passed in rather than derived because the
    shape of an open run is the engine's to know, and because a data layer that
    went looking for it would be a second opinion about the seal.

    `run_open` DEFAULTS TO TRUE, AND THAT IS THE WHOLE OF THE ARGUMENT. Every
    gated entry point in this file defaults it that way, so a caller who
    forgets the argument gets SILENCE rather than a lesson. It defaulted to
    False once and was measured teaching `the_trials` into an open interview
    through the bare call `tutorial.teach(state, beat_id)` — which is what
    docs/13 §7.8 E2 told the engine to write. A gate whose safe answer depends
    on the caller remembering is not a gate.

    `mode` KEEPS ITS ADVENTURE DEFAULT, and the asymmetry is deliberate rather
    than an oversight. This is a disjunction — refuse if the mode is measured
    OR the run is open — so `run_open=True` already refuses on its own and the
    mode default cannot open anything a forgetful caller would have closed.
    Flipping it as well would have closed the gate on the ONLY caller there
    is: the engine has no mode string to pass (there is no `state["mode"]`,
    and `hasattr(Game(), "mode")` is False), so `teach(state, id,
    run_open=self._run_is_open())` would have returned {} for every beat
    forever. Tested: `TheGatesFailClosed` calls both ways.

    And nothing is lost by it. `_run_is_open()` is True for `state["interview"]`,
    for `state["exam"]` and for an encounter opened in Interview Mode, so a
    caller that can honestly say `run_open=False` is not in a measured run. The
    `mode` argument stays for the callers that do hold a mode string, and the
    tests pass it.
    """
    return available_in(mode) and not run_open


# ---------------------------------------------------------------------------
# Who says it
# ---------------------------------------------------------------------------

def speaker(state) -> str:
    """THESSALY while she is in the square, THE BOARD once she is taken.

    Pure and derived: `zonecompanions.sweep_fired()` already returns False once
    `captives.final_release` has run, so she comes home and her voice comes
    back with her, and this function needs no transition of its own.
    """
    save = state if isinstance(state, dict) else {}
    if zonecompanions.sweep_fired(save):
        return SPEAKER_BOARD
    if captives.is_retaken(save, TEACHER_ID):
        return SPEAKER_BOARD
    return SPEAKER_THESSALY


def speaker_for(state, beat_id: str) -> str:
    """`speaker()`, with the one exemption, and the exemption is the data.

    A beat with an empty `board` line is a beat THE BOARD CANNOT DELIVER —
    there is no chalk line to deliver — so it stays in her voice. Exactly one
    beat is like that and it is `the_last_lesson`, which is her goodbye and is
    triggered at the sweep itself, while she is still standing there saying it.

    THE DOCUMENT IS AMBIGUOUS HERE AND THIS IS THE READING. docs/13 §6.3 says
    beat 21 fires "at the sweep, immediately after the capture scene", and also
    that a beat with no chalk line "is simply not shown". Taken together with
    §7.1 F6 — speaker is `board` once `sweep_fired` — the literal reading makes
    beat 21 unreachable and both of its authored variants dead prose. The
    reading that keeps the most authored intent is that she speaks it herself,
    which is also the only one the fiction supports: the board cannot say
    goodbye.
    """
    row = BY_ID.get(beat_id)
    if row is not None and not row.board:
        return SPEAKER_THESSALY
    return speaker(state)


def _fill(line: str, n: int) -> str:
    """The one interpolation, and the smallest possible amount of grammar.

    A schoolteacher who cannot count is the one character in this game who may
    not have that bug, so `1 things` is handled here rather than hoped for.
    """
    if n == 1:
        line = line.replace(COUNT_TOKEN + " things", COUNT_TOKEN + " thing")
    return line.replace(COUNT_TOKEN, str(n))


# ---------------------------------------------------------------------------
# Reading the curriculum
# ---------------------------------------------------------------------------

def taught(state, beat_id: str) -> bool:
    """Pure, total, and False for an id that is not a beat."""
    if beat_id not in BY_ID:
        return False
    return beat_id in _beats_list(state)


def pending(state) -> list:
    """Beat ids not yet taught, in authored order."""
    done = set(_beats_list(state))
    return [bid for bid in ORDER if bid not in done]


def count_pending(state, excluding: str = "") -> int:
    return len([b for b in pending(state) if b != excluding])


def lines_for(state, beat_id: str) -> list:
    """What this beat would say right now, without teaching it.

    The panel and the tests both want this, and neither of them should have to
    latch a lesson to find out what is in it.
    """
    row = BY_ID.get(beat_id)
    if row is None:
        return []
    if speaker_for(state, beat_id) == SPEAKER_BOARD:
        return [row.board] if row.board else []
    n = count_pending(state, excluding=row.id)
    source = row.alt_lines if (row.alt_lines and n == 0) else row.lines
    return [_fill(line, n) for line in source]


def view(state, beat_id: str) -> dict:
    """One beat as the client sees it, taught or not. Reads; never writes."""
    row = BY_ID.get(beat_id)
    if row is None:
        return {}
    who = speaker_for(state, beat_id)
    board = who == SPEAKER_BOARD
    return {
        "id": row.id,
        "order": row.order,
        "teaches": row.teaches,
        "trigger": row.trigger,
        "site": row.site,
        "taught": taught(state, row.id),
        "speaker": who,
        "who": BOARD_NAME if board else TEACHER_NAME,
        "portrait": BOARD_PORTRAIT if board else TEACHER_PORTRAIT,
        "channel": CHANNEL_TOAST if board else row.channel,
        "title": BOARD_NAME if board else row.title,
        "lines": lines_for(state, row.id),
        "board": row.board,
    }


# ---------------------------------------------------------------------------
# The only writer
# ---------------------------------------------------------------------------

def teach(state: dict, beat_id: str, *,
          mode: str = config.MODE_ADVENTURE,
          run_open: bool = True) -> dict:
    """Latch a beat and hand back what to show. {} means show nothing.

    {} is an ANSWER, not a refusal, and there are five of them:
      - the id is not a beat
      - the mode is a measured run, or a measured run is open
      - the beat is already taught
      - the board is speaking and this beat has no chalk line
      - (never) anything about the problem, because nothing here reads one

    It is deliberately safe to call on every trigger with no counting at the
    call site: the second call returns {} and writes nothing, which is why the
    work list in docs/13 §7.4 is eight lines rather than eight conditionals.

    BOTH GATES ARE KEYWORD-ONLY AND `run_open` FAILS CLOSED — see
    `may_teach()` for why that one and not both. A caller that passes neither
    is answered with {} and the save is not touched, so the failure mode of a
    forgotten argument is a missing lesson rather than a lesson delivered into
    a measurement. The engine passes `run_open=self._run_is_open()` and
    nothing else, because it does not keep a mode string and `run_open` is the
    fact that closes the gap docs/10's write clause is about.
    """
    row = BY_ID.get(beat_id)
    if row is None:
        return {}
    if not may_teach(mode, run_open):
        return {}
    if not isinstance(state, dict):
        return {}
    if taught(state, beat_id):
        return {}

    who = speaker_for(state, beat_id)
    board = who == SPEAKER_BOARD
    if board and not row.board:
        return {}

    # The count is taken BEFORE the latch, and this beat is excluded from it,
    # so "{n} things we never got round to" does not count itself.
    n = count_pending(state, excluding=row.id)

    raw = _write_bucket(state)
    if row.id not in raw["beats"]:
        raw["beats"].append(row.id)

    if board:
        lines = [row.board]
    else:
        source = row.alt_lines if (row.alt_lines and n == 0) else row.lines
        lines = [_fill(line, n) for line in source]

    return {
        "id": row.id,
        "order": row.order,
        "teaches": row.teaches,
        "speaker": who,
        "who": BOARD_NAME if board else TEACHER_NAME,
        "portrait": BOARD_PORTRAIT if board else TEACHER_PORTRAIT,
        "channel": CHANNEL_TOAST if board else row.channel,
        "title": BOARD_NAME if board else row.title,
        "lines": lines,
        "first_time": True,
        "blocks_input": False,      # a lesson is offered, never a modal
        "remaining": len(pending(state)),
    }


def forget(state: dict, *, run_open: bool = True) -> dict:
    """TEACH ME AGAIN. Clears the whole block — the counters and the latch.

    One button, two effects, because they are one idea: the player is saying
    "I would like to be shown this again", and there is no sensible reading in
    which that means the arrow and not the teacher.

    Gated like the other two writers, and fails closed. Clearing the block
    mid-run would re-arm two dozen lessons and five arrows inside a
    measurement, which is the loudest version of the thing the seal exists to
    stop — and it is a write, which is enough on its own.
    """
    if run_open:
        return {}
    if not isinstance(state, dict):
        return {"cleared": {"beats": 0, "shown": 0, "used": 0}}
    before = {
        "beats": len(_beats_list(state)),
        "shown": len(_counter(state, "shown")),
        "used": len(_counter(state, "used")),
    }
    state[LESSON_KEY] = new_lesson_state()
    return {"cleared": before, "pending": len(pending(state)),
            "state": new_lesson_state()}


# ---------------------------------------------------------------------------
# The cue's two counters
# ---------------------------------------------------------------------------

def cue_retired(state, control_id: str) -> bool:
    """Three shows or three uses, whichever came first.

    A player who finds RUN on their own never sees an arrow on it: the third
    press retires it with `shown` still at zero. That is the competence signal
    and it costs no extra machinery.
    """
    if control_id not in CUE_BY_ID:
        return True
    shown = _counter(state, "shown").get(control_id, 0)
    used = _counter(state, "used").get(control_id, 0)
    return shown >= CUE_RETIRE_AT or used >= CUE_RETIRE_AT


def cue_state(state) -> dict:
    """Both counters, who is retired, and the policy, in one read."""
    shown = _counter(state, "shown")
    used = _counter(state, "used")
    return {
        "shown": dict(shown),
        "used": dict(used),
        "retired": [cid for cid in CUE_IDS if cue_retired(state, cid)],
        "live": [cid for cid in CUE_IDS if not cue_retired(state, cid)],
        "policy": dict(CUE_POLICY),
        "controls": cue_registry(),
    }


def cue_note(state: dict, kind: str, control_id: str, *,
             run_open: bool = True) -> dict:
    """Count one show or one press. The only cue writer. {} for anything else.

    An unknown control id is REFUSED rather than counted, and that is the point
    of keeping this here: a client that grows a sixth control has to come to
    this file to get it counted, which is the moment somebody asks whether it
    is INTERFACE or PROBLEM.

    `run_open` fails closed exactly as `teach()`'s does, and for the same
    reason: this is a WRITER. No help leaks either way — a counter is not a
    hint — but docs/10's write clause is about the save, not about help, and
    three writers in one file gated two different ways is how the third one
    ends up ungated. There is no `mode` argument because a measured run in
    Adventure Mode is still an open run, and `run_open` is the fact the engine
    actually has.
    """
    if run_open:
        return {}
    if kind not in ("shown", "used"):
        return {}
    if control_id not in CUE_BY_ID:
        return {}
    if not isinstance(state, dict):
        return {}
    raw = _write_bucket(state)
    bucket = raw["cue"][kind]
    bucket[control_id] = int(bucket.get(control_id, 0)) + 1
    return {
        "id": control_id,
        "shown": int(raw["cue"]["shown"].get(control_id, 0)),
        "used": int(raw["cue"]["used"].get(control_id, 0)),
        "retired": cue_retired(state, control_id),
        "retire_at": CUE_RETIRE_AT,
    }


def cueable(state, control_id: str, *,
            mode: str = config.MODE_ADVENTURE,
            run_open: bool = True,
            setting_on: bool = SETTING_DEFAULT) -> bool:
    """The whole policy answer in one call, for a caller that wants one.

    Eligibility — rendered, enabled, not over the editor — is the DOM's to
    answer and stays in tutor.js. Everything that is not the DOM is here.

    Fails closed on the same default as `teach()`: no `run_open` means no
    arrow. CUE_REFUSED's last row is "anything at all, during a measured run",
    and a default that had to be remembered to hold it would not be holding it.
    """
    if control_id not in CUE_BY_ID:
        return False
    if not setting_on:
        return False
    if not may_teach(mode, run_open):
        return False
    return not cue_retired(state, control_id)


# ---------------------------------------------------------------------------
# The panel
# ---------------------------------------------------------------------------

def snapshot(state, mode: str = config.MODE_ADVENTURE) -> dict:
    """Everything a GUIDANCE panel or a save summary wants, in one call.

    THE ONE DEFAULT IN THIS FILE THAT DOES NOT FAIL CLOSED, on purpose. Every
    gate that grants something — a lesson, an arrow, a write — defaults to a
    measured run and refuses. This grants nothing: it writes nothing, latches
    nothing, and `available` is a LABEL on the panel rather than a permission.
    Defaulting it closed would only make the bare call report "unavailable" to
    a player standing in the square, so the engine calls it with no mode at
    all (docs/13 §7.8 E3) and there is no mode string in the engine to pass.
    """
    done = _beats_list(state)
    left = pending(state)
    return {
        "available": available_in(mode),
        "speaker": speaker(state),
        "who": (BOARD_NAME if speaker(state) == SPEAKER_BOARD
                else TEACHER_NAME),
        "teacher": {"id": TEACHER_ID, "name": TEACHER_NAME,
                    "portrait": TEACHER_PORTRAIT},
        "taught": [bid for bid in ORDER if bid in set(done)],
        "pending": left,
        "counts": {"total": len(BEATS), "taught": len(BEATS) - len(left),
                   "pending": len(left), "handoffs": len(HANDOFFS)},
        "cue": cue_state(state),
        "setting": {"key": SETTING_KEY, "default": SETTING_DEFAULT},
    }


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
# Two of these are worth a named function rather than a line in validate():
# the one that keeps her out of a fight, and the one that keeps a problem out
# of her mouth. Both fail BY NAME so that a reader of the failure knows which
# promise was broken.

_EXCLAMATION = "!"

# Words that would put her inside an encounter. The rule is rule 3 in the
# docstring: every battle lesson is taught before the first fight or after it.
_IN_BATTLE_TRIGGERS = (
    "during the encounter", "while the encounter", "mid-encounter",
    "inside the encounter", "during the fight", "while the fight",
    "mid-fight", "inside the fight", "after the player submits",
    "on a failed trial", "when the trials", "after a run",
)

# An advice verb next to an answer word, in ONE sentence, is the shape of a
# crutch. She may NAME a panel — "SPELLS is the ladder of hints" is geography —
# and she may not tell you to go and use one.
_ADVICE_VERBS = ("use", "using", "try", "press", "click", "open", "consult",
                 "check", "pick", "choose")
_ANSWER_WORDS = ("hint", "hints", "the answer", "correct answer",
                 "right answer", "answer key", "solution", "weakness",
                 "weaknesses", "pattern", "complexity", "mentor", "coach",
                 "probe", "probes")

# The shape of a problem id, for the refusal in `_no_beat_names_a_problem`.
# `fs-see-a-value`, `ll-nth-from-end`, `gen-fixed_window-market-1`. The prefix
# is 2-4 letters — the shipped corpus uses 37 of them, from `so` to `oopl` —
# and everything after the first hyphen is lowercase words and digits. No
# authored line in this curriculum contains a hyphen at all, measured; a beat
# that wants one has to be written without it, which is the cheaper half of
# this trade.
_PROBLEM_ID_SHAPE = re.compile(r"\b[a-z]{2,4}-[a-z0-9]+(?:-[a-z0-9]+)*\b")

# Python, in any amount, in authored prose. She does not write code on a board.
_CODE_MARKERS = ("def ", "return ", "import ", "lambda", "()", "[]", "==",
                 "->", "`", "o(n", "o(1", "big-o", "big o")


def _beat_text(row: Beat) -> str:
    """Every authored string on one beat, one per line.

    Newline-joined rather than space-joined so that `_sentences()` cannot run
    the end of one field into the start of the next and then report the wrong
    sentence back to whoever broke the rule.
    """
    return "\n".join((row.teaches, row.title, *row.lines, *row.alt_lines,
                       row.board))


def _sentences(text: str) -> list:
    return [s for s in re.split(r"[.!?\n]+", text) if s.strip()]


def _no_beat_names_a_problem() -> list:
    """The one invariant in this file that is worth a named function.

    A schoolteacher buys orientation. She may not buy a look at the problem,
    the pattern or the answer, and the refusal is enforced against a named
    vocabulary rather than against a reviewer's memory.

    `finalexam` is imported HERE, lazily, and only to read `CRUTCHES` as a list
    of words. This module never calls `finalexam.sealed()` and has no
    capability check anywhere in it.
    """
    problems = []

    families: tuple = ()
    try:
        from .corpus import _FAMILIES as families  # noqa: F401
    except Exception:                              # pragma: no cover
        problems.append("could not read corpus._FAMILIES; the family-name "
                        "refusal did not run")
    crutches: tuple = ()
    try:
        from .finalexam import CRUTCHES
        crutches = tuple(c.id for c in CRUTCHES)
    except Exception:                              # pragma: no cover
        problems.append("could not read finalexam.CRUTCHES; the crutch "
                        "refusal did not run")

    family_words = set()
    for name in families:
        family_words.add(name.replace("_", " ").lower())
        family_words.add(name.lower())
    crutch_words = set()
    for cid in crutches:
        spaced = cid.replace("_", " ").lower()
        crutch_words.add(spaced)

    for row in BEATS:
        text = _beat_text(row)
        low = text.lower()
        bare = low.replace(COUNT_TOKEN, "")

        # 1. No problem id and no family name.
        #
        #    TWO SHAPES, BECAUSE THE IDS COME IN TWO SHAPES, and the first
        #    version of this check only had the first one. Measured against the
        #    built corpus, 2026-09-13: 1013 problem ids, 1013 of them contain a
        #    hyphen and 24 of them contain an underscore (the
        #    `gen-fixed_window-*` and `gen-k_distinct-*` sets). An underscore
        #    check on its own therefore refused 24 of 1013 and let the other
        #    989 through: a beat reading "Try ll-nth-from-end when you are
        #    ready" validated clean, which is the exact leak docs/13 §7.1 F12
        #    promises this function refuses by name.
        #
        #    FAMILY ids are the underscore half (`sliding_window`,
        #    `arrays_hashing`) and they are also checked by name below.
        #    PROBLEM ids are `<2-4 letters>-<word>(-<word>)*` — 989 of 1013
        #    match that shape exactly and the remaining 24 are the underscore
        #    set already caught above, so between them the two rules cover
        #    1013/1013. The shape is matched rather than the corpus read,
        #    because this check runs at import time in a unit test that
        #    deliberately never builds a corpus.
        if "_" in bare:
            problems.append(f"{row.id}: beat text contains an underscore, and "
                            f"every family id in this project has one — as do "
                            f"24 problem ids. Authored prose does not.")
        for hit in _PROBLEM_ID_SHAPE.findall(bare):
            problems.append(f"{row.id}: {hit!r} has the shape of a problem id "
                            f"(letters, a hyphen, then words). A beat is about "
                            f"a screen, never about a question. If this is "
                            f"English, write it without the hyphen.")
        for word in sorted(family_words):
            if re.search(r"\b" + re.escape(word) + r"\b", bare):
                problems.append(f"{row.id}: names the corpus family "
                                f"{word!r}. A beat is about a screen, never "
                                f"about a question.")

        # 2. No Python, no complexity claim. She does not write code.
        for marker in _CODE_MARKERS:
            if marker in bare:
                problems.append(f"{row.id}: beat text contains {marker!r}, "
                                f"which is code or a complexity claim. "
                                f"Neither belongs in her mouth.")

        # 3. No advice verb beside an answer word, in one sentence.
        for sentence in _sentences(bare):
            has_verb = any(re.search(r"\b" + v + r"\b", sentence)
                           for v in _ADVICE_VERBS)
            if not has_verb:
                continue
            for word in _ANSWER_WORDS + tuple(sorted(crutch_words)):
                if re.search(r"\b" + re.escape(word) + r"\b", sentence):
                    problems.append(
                        f"{row.id}: {word!r} is recommended rather than "
                        f"named, in {sentence.strip()!r}. She may say what a "
                        f"panel IS; she may not send you to one for an "
                        f"answer.")
                    break

    return problems


def _she_is_never_in_a_fight() -> list:
    """Rule 3, checked against the trigger prose rather than remembered."""
    problems = []
    for row in BEATS:
        low = row.trigger.lower()
        for phrase in _IN_BATTLE_TRIGGERS:
            if phrase in low:
                problems.append(f"{row.id}: trigger {phrase!r} puts her "
                                f"inside an encounter. finalexam.CRUTCHES "
                                f"rung 5 is a companion volunteering a line "
                                f"in a fight, and the cheapest way not to be "
                                f"mistaken for it is not to be there.")
    return problems


def validate() -> list:
    """Everything that can be checked about two dozen lessons and five arrows.
    Returns a list of problems; empty is the pass condition."""
    problems = []

    seen_ids: set = set()
    seen_orders: set = set()
    seen_teaches: set = set()
    boardless = []
    token_lines = 0

    for row in BEATS:
        where = row.id
        if not row.id:
            problems.append("a beat with no id is not a beat")
        if row.id in seen_ids:
            problems.append(f"duplicate beat id {row.id!r}")
        seen_ids.add(row.id)
        if row.order in seen_orders:
            problems.append(f"{where}: two beats numbered {row.order}")
        seen_orders.add(row.order)

        # Every feature named in the design has EXACTLY ONE lesson, and this is
        # the half of that a data file can prove on its own.
        if not row.teaches:
            problems.append(f"{where}: a beat that teaches nothing is a line")
        if row.teaches in seen_teaches:
            problems.append(f"{where}: {row.teaches!r} is already taught by "
                            f"another beat; one idea, one lesson")
        seen_teaches.add(row.teaches)

        if not row.trigger:
            problems.append(f"{where}: no trigger, so it can never fire")
        if not row.site:
            problems.append(f"{where}: no work-list site, which leaves the "
                            f"wiring pass a re-reading job")

        if row.channel not in CHANNELS:
            problems.append(f"{where}: channel {row.channel!r} is not one the "
                            f"client can play")
        elif row.channel == CHANNEL_SAY:
            if not 1 <= len(row.lines) <= SAY_LINES_MAX:
                problems.append(f"{where}: one to three lines in a dialogue "
                                f"box, not {len(row.lines)}")
            if row.title:
                problems.append(f"{where}: a say has no title; the portrait "
                                f"carries the name")
        else:
            if len(row.lines) != TOAST_LINES:
                problems.append(f"{where}: a toast holds exactly one line, "
                                f"not {len(row.lines)}")
            if not row.title:
                problems.append(f"{where}: a toast with no title is an "
                                f"anonymous interruption")

        for line in row.lines + row.alt_lines + (row.board,):
            if line and line.strip() != line:
                problems.append(f"{where}: a line with loose whitespace")
            if _EXCLAMATION in (line or ""):
                problems.append(f"{where}: she does not exclaim. Nineteen "
                                f"years in one square and unimpressed by "
                                f"monsters.")
            token_lines += 1 if COUNT_TOKEN in (line or "") else 0

        if not row.board:
            boardless.append(row.id)

        if row.alt_lines and row.id != LAST_LESSON_ID:
            problems.append(f"{where}: only {LAST_LESSON_ID} has two "
                            f"variants; a second one is a branch nobody "
                            f"asked for")
        if row.alt_lines and not 1 <= len(row.alt_lines) <= SAY_LINES_MAX:
            problems.append(f"{where}: the variant is also one to three lines")

        # No beat id may collide with a person, a scene or a companion, because
        # both are addressed by id from the same client.
        if row.id in zonecompanions.BY_ID:
            problems.append(f"{where}: collides with a zonecompanions escort "
                            f"id, and scene() is addressed by that id")
        if row.id in captives.CAPTIVE_BY_ID:
            problems.append(f"{where}: collides with a captive id")

    # -- the board handover
    if boardless != [LAST_LESSON_ID]:
        problems.append(f"exactly one beat may have no chalk line and it must "
                        f"be {LAST_LESSON_ID!r}; found {boardless!r}. A beat "
                        f"with no board line is a lesson that dies with her.")

    # -- the one interpolation
    if token_lines != 1:
        problems.append(f"{COUNT_TOKEN} must appear in exactly one line in "
                        f"the whole curriculum, not {token_lines}. A number "
                        f"hard-coded into authored prose is a number that "
                        f"goes wrong on the day it matters.")
    one = _fill(COUNT_TOKEN + " things", 1)
    many = _fill(COUNT_TOKEN + " things", 2)
    if one != "1 thing" or many != "2 things":
        problems.append(f"the count reads {one!r} and {many!r}; a "
                        f"schoolteacher who cannot count is the one character "
                        f"in this game who may not have that bug")

    # -- the handoffs are not beats, and the numbering is whole
    numbers = sorted([row.order for row in BEATS] +
                     [h.order for h in HANDOFFS])
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append(f"the beat numbers and the handoff numbers together "
                        f"must run 1..{len(numbers)} with no gap and no "
                        f"repeat; got {numbers}")
    for hand in HANDOFFS:
        if hand.order in seen_orders:
            problems.append(f"handoff {hand.name!r} has the number of a beat")
        if not hand.owner or not hand.why:
            problems.append(f"handoff {hand.name!r}: a handoff without an "
                            f"owner is a dropped lesson")

    # -- the cue
    seen_control: set = set()
    for row in CUE_CONTROLS:
        if row.id in seen_control:
            problems.append(f"duplicate cue control {row.id!r}")
        seen_control.add(row.id)
        if not row.selector:
            problems.append(f"cue {row.id!r}: no selector, so tutor.js cannot "
                            f"find it")
        if row.placement not in (PLACEMENT_EDGE, PLACEMENT_UNDER):
            problems.append(f"cue {row.id!r}: placement {row.placement!r} is "
                            f"not one the CSS draws")
        if not row.kinds:
            problems.append(f"cue {row.id!r}: cueable in no encounter kind")
        for kind in row.kinds:
            if kind not in KINDS:
                problems.append(f"cue {row.id!r}: unknown kind {kind!r}")
        if not row.why:
            problems.append(f"cue {row.id!r}: no reason it is INTERFACE, and "
                            f"an unargued cue is the one that gets copied")
    if CUE_RETIRE_AT < 1 or CUE_PER_ENCOUNTER < 1:
        problems.append("a cue that never retires is a nag")
    for kind in KINDS:
        if kind not in CUE_POLICY["dwell_ms"]:
            problems.append(f"no dwell for kind {kind!r}")
    for row in CUE_REFUSED:
        if row.verdict not in (VERDICT_PROBLEM, VERDICT_INTERFACE):
            problems.append(f"refusal {row.target!r}: unknown verdict")
        if not row.why:
            problems.append(f"refusal {row.target!r}: a refusal without a "
                            f"reason gets reversed by the next reader")

    problems.extend(_she_is_never_in_a_fight())
    problems.extend(_no_beat_names_a_problem())
    return problems


def counts() -> dict:
    """The numbers, for the self-check and for whoever writes the patch note."""
    say = [r for r in BEATS if r.channel == CHANNEL_SAY]
    toast = [r for r in BEATS if r.channel == CHANNEL_TOAST]
    words = sum(len(" ".join(r.lines + r.alt_lines + (r.board,)).split())
                for r in BEATS)
    return {
        "beats": len(BEATS),
        "handoffs": len(HANDOFFS),
        "numbered": len(BEATS) + len(HANDOFFS),
        "say": len(say),
        "toast": len(toast),
        "lines": sum(len(r.lines) for r in BEATS),
        "alt_lines": sum(len(r.alt_lines) for r in BEATS),
        "board_lines": sum(1 for r in BEATS if r.board),
        "words": words,
        "cue_controls": len(CUE_CONTROLS),
        "cue_refusals": len(CUE_REFUSED),
        "cue_retire_at": CUE_RETIRE_AT,
        "town_beats": sum(1 for r in BEATS if r.id.startswith("town_")),
    }


def self_check() -> dict:
    """Raises on the first thing that is wrong, and otherwise hands back the
    numbers. Tests call `assert tutorial.validate() == []`; this is the version
    a human runs from a shell."""
    problems = validate()
    if problems:
        raise AssertionError("tutorial.py: " + "; ".join(problems[:8]))
    return counts()


WIRING = """
How the rest of the game picks this up. Nothing below is edited by the pass
that wrote this file; every row names the file, the symbol and the argument so
that the wiring pass works from this table rather than re-reading the design.

THE IMPORT IS `from . import tutorial`. docs/13 §7.1 calls this module
`firstlesson`; it is this file, under this name, with every symbol §7.1 asked
for. There is no firstlesson.py.

ENGINE — gauntlet/engine.py
  1. DEFAULT_STATE, beside the other module sub-states:
         tutorial.LESSON_KEY: tutorial.new_lesson_state(),   # "lessons"
     `_merge` deep-copies DEFAULT_STATE and folds the save over the top, so an
     existing save gains the key on load with nothing taught. No migration.
  2. DEFAULT_STATE["settings"], one more default:
         "cues": True
     `set_setting` already writes any key, so this is a default and a checkbox.
  2b. THE STATE PAYLOAD, one more field, and it is the one thing this design
     asks of a file it does not own beyond the six calls below:
         view[tutorial.RUN_OPEN_FIELD] = self._run_is_open()   # "run_open"
     on whatever /api/state already returns. main.js mirrors it onto the body
     as `tutorial.CUE_POLICY["sealed_body_class"]` — "run-open" — setting AND
     clearing it from that boolean alone, never from the encounter. See the
     comment above CUE_POLICY for why `body.interview-mode` cannot be used:
     returnToWorld() clears it while the run is still open, which is the gap
     the five M13 beats fire in.
  3. Game.lesson(beat_id):
         return tutorial.teach(self.state, beat_id,
                               run_open=self._run_is_open())
     then self.save() if the return is non-empty.

     THE GAME HAS NO `mode` ATTRIBUTE AND NEVER HAD ONE. An earlier version
     of this table told the engine to pass one read off itself, in this row
     and in row 6. `hasattr(Game(), "mode")` is False and
     engine.py says so itself, beside `_advance_escorts`: "it takes a MODE
     STRING, which this file does not keep — there is no state['mode']; a
     measured run is state['interview'] or state['exam'] or an encounter
     opened in that mode". Both instructed call sites raised AttributeError.
     `run_open` is the engine's own answer to the same question and is what
     every other door in that file asks, so it is the only argument passed —
     `may_teach()` refuses on `run_open` alone, and `mode` defaults to a
     measured run anyway.
  4. Game.lesson_note(kind, control_id):
         return tutorial.cue_note(self.state, kind, control_id,
                                  run_open=self._run_is_open())    + save
  5. Game.lessons_forget():
         return tutorial.forget(self.state,
                                run_open=self._run_is_open())      + save
     ALL THREE WRITERS ARE GATED THE SAME WAY. teach, cue_note and forget each
     take `run_open` and each default it to True, so a call site that forgets
     it writes nothing. Two of three gated and one ungated is how the ungated
     one survives a review.
  6. Game.lessons():   read-only panel view
         return tutorial.snapshot(self.state)
     No mode argument, for the reason in row 3, and none is wanted: `snapshot`
     writes nothing and its `mode` only labels the panel.

SERVER — gauntlet/server.py, the POST block
  POST /api/lesson         {id}         -> Game.lesson(id)
  POST /api/lesson/note    {kind, id}   -> Game.lesson_note(kind, id)
  POST /api/lesson/forget  {}           -> Game.lessons_forget()
  GET  /api/lessons                     -> Game.lessons()
  POST rather than GET for the first three because docs/10's write clause says
  a GET that changes the save is not a view. All three return {} rather than a
  409 when they decline: there is nothing to teach, which is an answer.

CLIENT — web/js/api.js
  lesson: (id) => softPost('/api/lesson', { id })
  lessonNote: (kind, id) => softPost('/api/lesson/note', { kind, id })
  lessonsForget: () => softPost('/api/lesson/forget', {})
  softPost, so a dropped teaching request never breaks a fight.

CLIENT — web/js/partyui.js (one beat, and the file is owned by nobody)
  P1. `paintClassSelection()` already exists and already renders the six. The
      beat fires where the player LANDS on the party screen with no class
      chosen — `paintSkillTree()` at the `tree.error === "no class chosen"`
      branch, which is the line that redirects to the selection screen — plus
      the `[data-pt-classes]` handler behind THE SIX DISCIPLINES. Both are one
      unconditional `tutor.beat('the_disciplines')`; the second returns {}.
      partyui.js already has a `configure()` injection point, so it imports
      nothing new.

CLIENT — web/js/tutor.js (new; created by the cue half of this run)
  REGISTRY should be built from `cue_registry()` as served, NOT re-typed. Two
  copies of that table is how a client ends up cueing something this file has
  already refused. The retirement rule is `cue_retired()` and lives here on
  purpose, so `tutor.js` asks rather than counts.

FIELD HANDOFF DELIVERY — the client consumers for the two companion-owned rows:

  W3  DELIVERED: main.js consumeEscortResponse / drainEscortNotices consumes
      region.escort and the original move/travel.escort_events; WorldUI passes
      its travel response before navigation teardown. Overworld.setEscort and
      _offerEscortCaption feed the field sidebar from walking capability flags.
      The Slate uses the server's existing grant and authored lines once; no
      second grant or tutorial acknowledgement. Measured runs suppress both.
      Captions reset per visit. Current house doorsteps speak to the mentor;
      distinct service signs, human follower animation and enterable interiors
      in docs/12 are still separate work, not implied by this handoff.

TRIGGERS — the twenty-four call sites, by docs/13 §7 row. Every one of them is
a single unconditional `tutor.beat('<id>')`: the second call returns {} and
writes nothing, so no call site needs a counter, a flag or an `if`.
""" + "\n".join(
    f"  {row.site:<34} {row.id:<18} {row.trigger.splitlines()[0][:64]}"
    for row in sorted(BEATS, key=lambda r: r.order)) + """

CONTRACT — what this module needs from files it does not own
  captives.available_in(mode)                already exists, already correct
  zonecompanions.sweep_fired(state)          already exists, already derived
  captives.is_retaken(state, id)             already exists
  engine.Game._run_is_open()                 already exists
  engine.set_setting(key, value)             already exists
  Nothing new is asked of any of them, and in particular no `Game.mode`
  attribute is asked for — there is not one, and row 3 above is why this
  sentence is here rather than a call that would have raised.
"""


CONTRACT = """
What this module promises, in the order somebody will try to break it.

1. IT NEVER ASKS THE SEAL. No import of finalexam at module scope, no call to
   sealed(), no capability check. `available_in()` is the whole opinion and it
   defers to captives.

2. IT NEVER BLOCKS. `teach()` returns `blocks_input: False` and there is no
   modal anywhere in the shape. A lesson is offered; the player keeps walking.

3. IT NEVER REPEATS. The latch is in the save, `teach()` is the only writer of
   it, and a second call returns {} without writing. `forget()` is the one way
   back, and it is a button the player presses.

7. IT REFUSES BY DEFAULT. All three writers — `teach`, `cue_note`, `forget` —
   take `run_open` as a keyword-only argument defaulting to True, so a caller
   that forgets it writes nothing and is told nothing. `cueable` and
   `may_teach` default the same way. Two of three gated and one ungated is how
   the ungated one survives a review, which is how `cue_note` and `forget`
   spent a version writing into an open measured run.

4. IT NEVER RAISES. Every reader goes through `_bucket()`. None, {}, a string,
   a list where a dict belongs, an int where a list belongs and a save written
   before this file existed all answer and none of them raises.

5. IT ROUND-TRIPS. Every value in the state and in every return is str, int,
   bool, list or dict. json.dumps eats all of it.

6. THE CURRICULUM SURVIVES ITS TEACHER. At the sweep the speaker becomes THE
   BOARD, the channel becomes a toast and the text becomes the one chalk line
   each beat already carries. After captives.final_release she comes home and
   her voice comes back with her, derived, with no transition to run.
"""
