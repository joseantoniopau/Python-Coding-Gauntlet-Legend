"""Townspeople who read the situation.

The brief was "make the dialogue engaging for every npc", and the thing that
makes dialogue engaging is not more of it. It is dialogue that could only have
been said to THIS player, standing HERE, carrying THAT, with a particular boss
one road away. An NPC with one warm sentence is scenery. This module is the
engine that stops them being scenery.

WHAT THIS IS
------------
A composer. Given a speaker, a place and a live player, it assembles what that
person says NOW out of two separate vocabularies:

    FRAMES   the voice. Authored per REGISTER — a smith does not phrase a thing
             the way a lamplighter phrases it — and carrying slots.
    FILLINGS the content. Authored per ELEMENT, per HAZARD, per SKILL, and
             DERIVED from forge.METALS, pets.PETS, world.BOSSES and
             quests.QUESTS, so that a metal moving region moves the line.

Frames times fillings is why a villager does not go stale. The same frame over a
different area, a different loadout and a different unfinished forge order is a
different sentence, and the rotation in Section 8 will not reuse a frame until
the pool it came from is spent.

THE FIVE THINGS AN NPC CAN KNOW
-------------------------------
    AREA    what this place is made of, and what that does to a person.
    GEAR    your loadout AGAINST this place: your strike element, your
            resistances, and whether your boots will survive the ground.
    AHEAD   the next boss and the family it demands; the next chapter and the
            skill it tests. Preparation. See THE ANSWER LINE.
    PROVED  what you fixed here, named, by the person you fixed it for, forever.
    WHERE   which metal drops here, which companion hides nearby, what the
            vendor can have in at this tier. A world that answers "where do I
            get that" is a world worth walking.

THE ANSWER LINE
---------------
This is the sharp edge, and it is enforced rather than promised.

    THIS MODULE MAY NAME: an ELEMENT ("bring something cold"), a PATTERN ("the
    Wastes want a graph traversal"), a PLACE ("Wastes-iron comes out of the
    Wastes") or a SKILL ("that chapter is measuring whether you can say what a
    thing costs").

    THIS MODULE MAY NEVER NAME: a Python construct that solves the problem in
    front of the player. Not the name of a container, not the name of a callable,
    not a line of code, not an idiom written out.

The distinction is not stylistic. Telling a player to bring cold metal into the
Mines is TACTICAL advice about gear, which the brief asked for and which costs
nobody anything. Telling a player which container makes the lookup constant is a
HINT: hints belong to pets.py, they cost bond and rank, and they are refused in
a measured run. Two systems, one line between them, and `names_a_construct`
below is that line written as code. `self_check` runs it over every authored
string in this file AND over every line the composer can emit from a saturated
context, so a frame cannot smuggle one in through a slot.

"the boss in the Wastes demands a graph traversal" tells a player what to STUDY.
That is the opposite of telling them an answer, and it is the whole point.

THE OTHER RULES
---------------
NOTHING WORKS IN A MEASURED RUN. Every beat declares a capability from
finalexam.CRUTCHES and `speak` drops the beats whose capability is sealed. When
all five are gone the module returns finalexam.refuse, which is the same refusal
shape as every other "no" in this game. There is one capability check and it is
`finalexam.sealed`.

MASTERY MOVES ONLY ON GRADED EVIDENCE. This module reads state. It writes
exactly one thing — which frames a speaker has already used — and that is
bookkeeping, not evidence.

LEARNING NEVER DEAD-ENDS. AREA is available to every register in every region,
including the five neutral ones, so there is no state in which a speaker has
nothing to say. `self_check` proves it over every speaker times every region.

PURE STDLIB.

TONE. Dry, direct, a little wry. No exclamation marks, no quest markers in hats.
These are tired people in a world that is ending slowly, and most of them are
funny about it.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field

from . import curriculum
from . import elements
from . import finalexam
from . import forge
from . import items
from . import pets
from . import potions
from . import quests
from . import skills as skills_mod
from . import world

# economy.py is written in a parallel pass. It is read if it is there and
# ignored if it is not, because a dialogue system that cannot load until the
# shop exists is a dialogue system that blocks the shop. Nothing below assumes a
# shape: every use is a getattr with a default.
#
# regalia.py is deliberately NOT imported. It carries a second, disjoint roster
# of tack; the pieces a player can actually be paid and actually buy are
# quests.REGALIA, which economy.py prices. Pointing a villager at the other
# roster would advertise objects no quest grants and no vendor stocks.
try:                                            # pragma: no cover - optional
    from . import economy as _economy
except Exception:                               # pragma: no cover
    _economy = None


# ==========================================================================
# SECTION 1 — THE ANSWER LINE, AS CODE
# ==========================================================================
#
# Everything above the line is allowed. Everything below it is a hint, and a
# hint costs rank and is refused in a measured run, so it cannot be given away
# for free by a villager leaning on a fence.
#
# The list is deliberately literal rather than clever. A regex that tried to
# understand Python would have opinions; a list of the exact spellings a leaked
# answer would have to use has none, and a reviewer can read it in one pass.
#
# Three shapes are banned:
#   1. code punctuation — a fence, a call, a comparison, a slice
#   2. the standard library by name — the containers and modules whose NAME is
#      the answer to a whole family of problems
#   3. the sentences a walkthrough uses to introduce a solution
#
# What is NOT banned, and must not be: element names, pattern and family names,
# region names, skill names, and complexity notation. Those are the vocabulary
# this module exists to speak.

_BANNED_LITERAL: tuple = (
    # -- 1. code punctuation ------------------------------------------------
    "```", "def ", "return ", "import ", "lambda", "yield ", "elif ",
    "print(", "[::", ":=", "==", "!=", "->",
    # -- call shapes. The paren is what makes it code rather than English ---
    "enumerate(", "zip(", "sorted(", "reversed(", "len(", "range(", "map(",
    "filter(", "sum(", "min(", "max(", "abs(", "any(", "all(", "dict(",
    "set(", "list(", "tuple(", "counter(", "append(", "pop(", "push(",
    ".get(", ".add(", ".sort(", ".keys(", ".items(", ".values(", ".join(",
    ".split(", ".strip(", ".format(",
    # -- 2. the standard library by name ------------------------------------
    "defaultdict", "ordereddict", "namedtuple", "collections", "itertools",
    "functools", "lru_cache", "heapq", "bisect", "deque", "frozenset",
    # NOT banned, deliberately: "hash map", "hashmap", "stack", "queue",
    # "heap", "graph", "tree". Every one of those is a PATTERN name in
    # skills.PATTERN_TO_SKILL or a PLACE on the map — Hashmap Highlands is a
    # region — and rule E allows both. The construct is the container, and the
    # container is spelled "dict", which is banned two lines down.
    # -- 3. walkthrough sentences -------------------------------------------
    "the answer is", "the solution is", "here is the code", "here's the code",
    "write it like this", "type this", "copy this", "just paste",
    "solves it for you", "reveals the solution", "shows the solution",
    "one-liner", "one liner",
)

# Words that only read as a Python construct when they stand alone. `\bset\b`
# catches the container and leaves "settles" and "sunset" alone; `\bkey\b` is
# NOT here, because a key in the Highlands is a key in a lock and this world is
# full of them.
# `dict` lives here rather than above because "verdict" and "contradiction"
# contain it and neither is a container.
_BANNED_WORD: tuple = (
    "set", "sets", "list", "lists", "tuple", "tuples", "dict", "dicts",
)

# Case-SENSITIVE, and there is exactly one of these for a reason. The counter to
# fire is cold, and saying so is the single most useful sentence this module
# owns; banning the English word "counter" to catch a class name would cost the
# brief's whole gear-advice layer. The class is always capitalised, so the
# capital is what gets checked.
_BANNED_CASED: tuple = ("Counter", "Deque", "Heap", "OrderedDict")

_WORD_RE = {word: re.compile(r"\b" + re.escape(word) + r"\b")
            for word in _BANNED_WORD}
_CASED_RE = {word: re.compile(r"\b" + re.escape(word) + r"\b")
             for word in _BANNED_CASED}

# Shapes a plain substring test gets wrong. `self.` as a substring matches the
# English word "Itself." at the end of a sentence, which is how a chapter title
# tripped the guard; attribute access has no space after the dot.
_BANNED_PATTERN: dict = {
    "self.<attr>": re.compile(r"\bself\.[A-Za-z_]"),
    "subscript": re.compile(r"\w\[[0-9'\"]"),
}

# Words that are code in this codebase and English everywhere else. They are
# checked in AUTHORED text, where every word is chosen, and NOT in text derived
# from other modules, where "the stakes are set in one line" is a mason talking
# about stakes. `strict=False` is that second audience and nothing else.
_ENGLISH_AMBIGUOUS = frozenset({"set", "sets", "list", "lists",
                                "tuple", "tuples"})


def names_a_construct(text: str, *, strict: bool = True) -> list:
    """Every banned spelling in one string. Empty means the line is clean.

    THIS IS THE GUARD. `self_check` runs it over every authored frame, every
    filling, and every line the composer can actually emit; tests/ should run it
    over anything that ever concatenates onto a banter line.
    """
    raw = text or ""
    lowered = raw.lower()
    found = [token for token in _BANNED_LITERAL if token in lowered]
    found += [word for word, pattern in _WORD_RE.items()
              if pattern.search(lowered)
              and (strict or word not in _ENGLISH_AMBIGUOUS)]
    found += [word for word, pattern in _CASED_RE.items()
              if pattern.search(raw)]
    found += [name for name, pattern in _BANNED_PATTERN.items()
              if pattern.search(raw)]
    return sorted(found)


def clean(text: str) -> bool:
    return not names_a_construct(text)


# What this module IS allowed to name, stated as data so `self_check` can prove
# the vocabulary it speaks is real rather than invented next to the real one.
SPEAKABLE = ("ELEMENT", "PATTERN", "PLACE", "SKILL")


# ==========================================================================
# SECTION 2 — THE BEATS
# ==========================================================================
#
# Five, and there will not be a sixth. A beat is a QUESTION about live state,
# not a topic: "what is this place made of", "is your kit wrong for it", "what
# is one road away", "what did you fix here", "where does that thing come from".
#
# Each one declares the finalexam capability it leans on, because each one IS
# one of the crutches in a small way and should go out with it:
#
#   AREA    WEAKNESS_MAP  — the element of the ground is a tactical read
#   GEAR    WEAKNESS_MAP  — your loadout against that read is the same crutch
#   AHEAD   PATTERN       — naming the family a fight demands is the label
#   PROVED  MENTOR        — a named person speaking to you about your own record
#   WHERE   BUILD         — where the metal is, is gear progression
#
# When every one of them is sealed, `speak` refuses. That happens in Timed Practical
# Mode and on hold-out content, which is exactly where it should happen.

AREA = "AREA"
GEAR = "GEAR"
AHEAD = "AHEAD"
PROVED = "PROVED"
WHERE = "WHERE"

BEATS: tuple = (AREA, GEAR, AHEAD, PROVED, WHERE)

BEAT_CAPABILITY: dict = {
    AREA: "WEAKNESS_MAP",
    GEAR: "WEAKNESS_MAP",
    AHEAD: "PATTERN",
    PROVED: "MENTOR",
    WHERE: "BUILD",
}

BEAT_BLURB: dict = {
    AREA: "what this ground is made of",
    GEAR: "what you are carrying, against this ground",
    AHEAD: "what is one road from here, and what it will want",
    PROVED: "what you already fixed, named",
    WHERE: "where a thing comes from",
}

# The slots each beat's frames may carry. Every frame is formatted with the full
# set, so a frame may use any subset and `self_check` proves no frame reaches for
# a slot its beat does not define.
BEAT_SLOTS: dict = {
    AREA: ("region", "weather", "hazard"),
    GEAR: ("gear", "counter", "boots"),
    AHEAD: ("ahead", "demand", "where_ahead"),
    PROVED: ("deed", "proved"),
    WHERE: ("thing", "place", "rate"),
}


# ==========================================================================
# SECTION 3 — THE FILLINGS: WEATHER, COUNTERS, HAZARDS, BOOTS
# ==========================================================================
#
# The content half. These are keyed on elements.py's own ids, not on region ids,
# which means seventeen regions are covered by seven entries and a region that
# changes biome changes what the town says about it without this file moving.
#
# Three phrasings each, so that the FRAME rotating and the FILLING rotating are
# independent wheels. Two wheels of three and four is twelve, not four.

# What the ground does to a person. Never advice — this is the observation the
# advice is built on, and several registers only ever get this far.
WEATHER: dict = {
    elements.FIRE: (
        "the floor keeps more heat than anything put into it",
        "everything down there is either burning or has been",
        "the warmth comes up off the ground, not down off the sky",
        "the heat in there is patient. It does not rush you and it does not "
        "stop",
        "nothing in those galleries has been properly cool in a generation",
    ),
    elements.COLD: (
        "the cold takes the speed out of a swing before the swing lands",
        "nothing up there is warm and nothing up there is in a hurry",
        "it is cold enough that your own arms start arguing with you",
        "the cold up there is not weather. It is a condition of the place",
        "everything on that slope takes longer than it should, including you",
    ),
    elements.POISON: (
        "the things in there carry poison and the ground carries it too",
        "you will breathe some of it. Everyone does. It is the hours after "
        "that are the trouble",
        "it is never the bite that puts people down. It is the afternoon "
        "following the bite",
        "the whole of that country is mildly against you at all times",
        "nothing in there kills quickly and a great deal of it kills slowly",
    ),
    elements.BRUTE: (
        "nothing in there is clever. All of it is heavy",
        "what lands on you there does not care what you had on",
        "it arrives in a straight line and plate stops being the answer",
        "the things in there solve every problem by weighing more than it",
        "there is no finesse anywhere in that place, which is exactly what "
        "makes it difficult",
    ),
    elements.LIGHTNING: (
        "you will be the tallest metal for a day's walk in any direction",
        "it does not do the damage itself. It arranges for the next thing to",
        "the air is charged and what you are wearing is a decision about that",
        "the ground up there is one enormous conductor and so are you",
        "it goes where it is invited, and metal is an invitation",
    ),
    elements.VOID: (
        "nothing in there is labelled and nothing in there is lit",
        "what you spend does not come back while you are down there",
        "it is not a force. It is an absence turning up where a force was due",
        "the deeper in you go the less of it there is, and that is the problem",
        "nothing in there gives anything back, including light",
    ),
    elements.NEUTRAL: (
        "nothing out there pushes back. Whatever happens, you did it",
        "there is no weather here to blame afterwards",
        "plain ground, which is the only honest measurement anybody gets",
        "the ground here has no argument to make, which leaves only yours",
        "there is nothing in this place that will explain a bad afternoon "
        "for you",
    ),
}

# What to bring. Derived opposition, authored phrasing: the element named is
# always `elements.OPPOSED[area]`, so the wheel and the advice cannot drift.
#
# This is the brief's "hints on what armor or weapons affinities to use", and it
# is concrete enough to act on: it names the element, and elements.matchup turns
# that into a fight two thirds as long.
COUNTER: dict = {
    elements.FIRE: (
        "bring something cold. The things here burn, and cold is the whole of "
        "the argument against burning",
        "cold metal, and the fights get a third shorter. Fire, and they get "
        "longer, and you will not know why",
        "carry cold down there. It is not subtle advice and it does not need to be",
    ),
    elements.COLD: (
        "bring fire up here. Everything on this slope has been frozen for so "
        "long it has forgotten the alternative",
        "something that burns. Cold against cold is two people being stubborn "
        "at each other",
        "fire, and warded for cold if you have it. Both, if you are sensible",
    ),
    elements.POISON: (
        "bring something blunt. Poison is patient and patience does badly "
        "against weight",
        "brute force. No cleverness at all, which is exactly why it works in "
        "here",
        "heavy and stupid beats slow and clever in a marsh. Ask anyone who "
        "has walked one",
    ),
    elements.BRUTE: (
        "bring poison. The heavy things in here have no answer to something "
        "that does not care how the fight is going",
        "poison, and be patient with it. It is a debt, not a blow",
        "something that keeps working after you have stopped. That is poison "
        "and it is the counter to everything in here",
    ),
    elements.LIGHTNING: (
        "bring void. It is the only thing that arrives where the charge "
        "expected a conductor and finds nothing",
        "void metal. Lightning needs somewhere to go and void is nowhere",
        "carry void up here, and earth your boots, and you will keep your hair",
    ),
    elements.VOID: (
        "bring lightning. One instant of contact is enough, and after that "
        "everything conducts",
        "lightning. The dark in there is an absence and an absence can still "
        "be lit for a second",
        "something that arrives all at once. The void has no answer to sudden",
    ),
    elements.NEUTRAL: (
        "nothing you carry counts for more here than what you type",
        "no weather, so no advantage. It is you and the line",
        "bring whatever you like. This ground has no opinion about it",
        "carry what you are used to. There is nothing here to counter and "
        "nothing here to be countered by",
        "no element will save you on this ground and none will sink you "
        "either, which some people find restful and some find worse",
    ),
}

# When the loadout is actively wrong. Keyed on the `kind` elements.matchup
# returns, so the sentence and the multiplier come out of the same function.
#
# EVERY ENTRY HERE MUST BE A CLAUSE, not a noun phrase, and must begin with its
# own subject. Thirteen frames across nine registers embed this slot after a
# subordinator — "I am obliged to tell you that {gear}", "because {gear}", "In
# your case, {gear}" — and a noun phrase dropped into one of those produces
# "I am obliged to tell you that slightly the wrong metal." That is not a style
# preference, it is the difference between a sentence and a fault, and
# `self_check` now proves it over every frame times every filling rather than
# leaving it to whoever authors the next entry.
MISMATCH: dict = {
    "SAME": (
        "you are carrying the same thing this place is made of. It gets "
        "shrugged off — a third of every blow goes nowhere",
        "your weapon and the ground agree with each other, which is the worst "
        "possible arrangement",
        "you brought the room's own element into the room. It will not fail "
        "you. It will simply cost you a third more of everything",
        "you are hitting this place with what this place is built out of, and "
        "it is politely absorbing all of it",
        "your element and the ground's are the same element, which is the one "
        "arrangement that gives you nothing at all",
    ),
    "WEAK_INTO": (
        "what you are swinging is blunted in here. Not badly. Enough to notice "
        "on a long fight",
        "your element is the wrong way round against this one. It is a small "
        "tax and it is a real one",
        "you are carrying slightly the wrong metal. You will get through. You "
        "will get through slower",
        "your edge is on the losing side of this pairing, which costs you the "
        "back half of every fight rather than the front",
        "you are a little under-matched in there, in the way that only shows "
        "up once you are tired",
    ),
    "OPPOSED": (
        "you read the ground right. Whatever you are carrying is the counter "
        "to it, and it shows",
        "the metal you are carrying is the correct one for in there, and half "
        "the people who walk past me are not carrying it",
        "you have the counter, which is more than most of the people who walk "
        "past me can say",
        "you are carrying the one element this ground has no answer to, and "
        "you will feel it in how short the fights are",
        "whoever loaded you out was paying attention. That is the counter and "
        "it is worth a third of every fight in here",
    ),
    "SECONDARY": (
        "you have an edge in there. Not a counter, an edge. It is better than "
        "nothing and it is not a plan",
        "it will do a little more than it should. Do not build an evening "
        "around it",
        "what you are carrying is a slight advantage, honestly earned and "
        "easily overrated",
        "you are fractionally ahead on the exchange, which is not the same as "
        "being ahead",
        "your element leans the right way here, and leaning is all it does",
    ),
    "NEUTRAL": (
        "your metal has no opinion about this place and this place has none "
        "about it",
        "nothing you carry is helping or hurting here. That is not a complaint",
        "it is plain against plain in there. What happens is yours",
        "you are neither helped nor punished by what you are holding, which is "
        "at least honest of the place",
        "your element and this ground have nothing to say to each other. The "
        "fight will be exactly as long as you are good",
    ),
}

# Unwarded, in an area with weather. The second half of "what armour to use":
# resistance is proportional, so an unresisted elemental area is a real number
# of extra fights, not a mood.
UNWARDED: tuple = (
    "and nothing you have on resists it, which means you are paying the full "
    "price of every hit in here",
    "and not one piece of what you are wearing is warded for it. That is a "
    "choice. Make it on purpose",
    "and you have no resistance to it at all. Flat plate will stop a little of "
    "it. It will not stop the part that matters",
    "and you are carrying no ward against the one thing this ground is made "
    "of, which is the expensive kind of oversight",
    "and there is nothing on you cut for this element, so every exchange in "
    "here is being paid at the full asking price",
)

WARDED: tuple = (
    "and you are warded for it, which is most of why you are still upright",
    "and what you have on is cut for exactly this. Somebody thought ahead",
    "and your ward covers it. That is the difference between a long walk and a "
    "short one",
    "and you are warded against exactly the thing that is coming, which is "
    "rarer than it ought to be",
    "and the ward you have on is the one this ground argues with. Keep it on",
)

# Flat armour, which is the other road. Named separately because the whole point
# of elements.ArmourProfile is that the player chooses between the two.
PLATED: tuple = (
    "you are carrying real weight, which will stop a little of everything and "
    "all of nothing",
    "you have plate on. Certain, unglamorous, and it answers what you did not "
    "see coming",
    "the flat armour is doing its quiet work, which is a different job from "
    "the one a ward does",
    "you have weight on, which takes the top off everything and the whole of "
    "nothing",
    "the plate is honest. It will not save you from this place in particular, "
    "and it will save you from a great many things in general",
)
UNPLATED: tuple = (
    "and no flat armour either, so every small unexpected thing costs full "
    "price",
    "and nothing heavy on you. Fast, and you will feel every hit you did not "
    "plan for",
    "and no weight to fall back on, which is a decision rather than an "
    "oversight in most cases",
    "and not a scrap of plate, so the things you did not plan for are the "
    "things that will settle it",
    "and nothing flat to absorb the ordinary damage, which is most of the "
    "damage",
)

# The hazard. elements.HAZARDS already carries a blurb; these are what a person
# says about it, which is a different job.
HAZARD_TELL: dict = {
    "ICE": (
        "the ground takes your step somewhere you did not aim it",
        "black ice under the whole pass. You will arrive. Not necessarily where "
        "you were pointed",
        "it is not the fall that gets people. It is arriving a foot to "
        "the left of where they aimed",
        "you will not notice it until you try to change direction, which is "
        "the worst possible moment to find out",
        "the pass is perfectly safe to stand on and perfectly unreliable to "
        "walk on. Budget accordingly",
    ),
    "EMBER": (
        "the floor is hotter than whatever you have on your feet",
        "ember ground the length of it. It does not burn you all at once, which "
        "is how it gets people",
        "you can cross it. You will simply be a slightly different person "
        "on the other side",
        "the heat comes up through the sole rather than at the face, which is "
        "why people dress for the wrong fire",
        "nobody down there runs. Running is how you meet more of the floor",
    ),
    "DARK": (
        "you will see one tile. The map fills in behind you and never in front",
        "unlit, the whole way. Bring a light at ankle height or accept the walk "
        "taking twice as long",
        "the dark is not hiding anything in particular. It is hiding "
        "everything, indiscriminately",
        "you will walk past the thing you came for twice before you see it "
        "once",
        "it is not the sort of dark that a torch fixes. It is the sort that a "
        "torch makes smaller",
    ),
    "SPORE": (
        "every step lifts a little more of it off the ground",
        "spore air. It is not the walk that poisons you, it is having walked",
        "it settles on you on the way in and it is still on you on the "
        "way out",
        "the air in there is doing something slow to you for the entire time "
        "you are in it",
        "you will feel completely fine for the first hour. That is the part "
        "that fools people",
    ),
    "STATIC": (
        "the air is charged and your own gear is the tallest thing on the plateau",
        "charged air up there. It finds the metal. You are the metal",
        "it does not strike the tallest thing. It strikes the best-connected "
        "thing, and that is usually a person in plate",
        "the charge picks whatever is most joined up to everything else. In a "
        "party, that is whoever is wearing the most",
        "there is a reason the people who live up there own no jewellery",
    ),
    "RUBBLE": (
        "nothing on that ground is dangerous. All of it is slow",
        "loose rubble end to end. It will not hurt you. It will take your evening",
        "every step is fine and the ninth hundredth is the one you resent",
        "the danger in there is entirely to your schedule and not at all to "
        "your person",
        "you will not be hurt. You will be delayed, repeatedly, by stones with "
        "no opinion about you",
    ),
}

# Boots, answered. The tag comparison is real: elements.hazard_step looks the
# equipped id up in BOOTS_BY_ID and checks exactly this.
# Authored WITHOUT a leading connective, because the frames in Section 6 decide
# whether this arrives as "and", as "though", or as its own sentence.
BOOTS_OK: tuple = (
    "what you have on your feet answers it, so walk on",
    "your boots are cut for that ground, and nobody will mention it again",
    "you are shod for it, which is most of why you are not limping",
    "your feet are correctly answered, and that is one fewer thing",
    "whatever you have on down there is rated for that ground. Good",
)
BOOTS_WRONG: tuple = (
    "what you have on your feet will not survive it",
    "your boots are the wrong boots for that ground. They will not kill you. "
    "They will slow you, and they will keep slowing you",
    "you are not shod for it. Fix that before you go, or budget the time",
    "your boots answer a different ground than this one, and the ground does "
    "not care what they answer",
    "what is on your feet is rated for somewhere else entirely",
)
BOOTS_NONE: tuple = (
    "you would be walking it in whatever you arrived in",
    "there is nothing on your feet built for that ground at all",
    "you have no boots for it, and there is a pair for it, and they are not "
    "expensive",
    "you have nothing on your feet that this ground will respect",
    "your feet are the unanswered part of you, and this is the ground that "
    "asks about feet",
)
BOOTS_IDLE: tuple = (
    "nothing underfoot here needs answering, so your boots are your own business",
    "no ground worth the wrong boots. Wear whatever you like",
    "the floor makes no demands, which is the only thing about this place that "
    "does not",
    "your boots are irrelevant here, which is a rare holiday for them",
    "nothing down there is going to test your footwear. Something else will",
)


# ==========================================================================
# SECTION 4 — WHAT A THING DEMANDS
# ==========================================================================
#
# The AHEAD beat's content, and the single most dangerous table in this file,
# because it is the one that talks about problems.
#
# The rule it lives under: EVERY ENTRY NAMES A FAMILY AND A SHAPE, AND NOT ONE
# OF THEM NAMES A CONSTRUCT. "The Wastes want the search that spreads in rings"
# tells a player which chapter to go and read. "Use a queue of frontier nodes"
# would be the hint tree talking, and the hint tree costs rank.
#
# Keyed on skills.SKILLS, all thirty of them, checked in `self_check`. Two
# phrasings each, so that a player walking the same road twice is told the same
# true thing in a different mouth.
#
# Read these as: what should the player go and STUDY tonight.

DEMAND: dict = {
    "PYTHON": (
        "it wants the language itself, typed without stopping to think about "
        "the typing",
        "it is measuring whether writing the line costs you anything. It should "
        "cost you nothing",
        "you are not being asked to be clever here. You are being asked "
        "to be fluent, which is harder and quieter",
    ),
    "HASH_MAP": (
        "it wants keyed lookup — one name, one vault, and never trying the "
        "wrong vault twice",
        "it is the family where you have seen a thing before and can prove it "
        "without looking through everything again",
        "one name, one place it is kept, and never a second search for "
        "something you already filed",
    ),
    "SET": (
        "it wants membership. Have you met this one already, answered once, "
        "cheaply, and never rechecked",
        "the family is about uniqueness: many things arrive, some are the same "
        "thing twice, and you must not be surprised by that",
        "it is the family of having met a thing before and being certain "
        "about it without going back through everything",
    ),
    "STRING": (
        "it wants text handled as a thing with an order, not as a word with a "
        "meaning",
        "the family is letters: what they spell, what they spell rearranged, "
        "and what two spellings have in common",
        "letters in an order, and every question is about what that order "
        "does when you move it",
    ),
    "ARRAY": (
        "it wants position. The first place is zero and the last is one short "
        "of the count, and almost everything that goes wrong goes wrong there",
        "the family is a row of things and an honest opinion about where in the "
        "row you are",
        "a row, and a number saying where in the row you are, and the two "
        "ends of it where everything goes wrong",
    ),
    "SLIDING_WINDOW": (
        "it wants the frame that widens on the right and shrinks on the left, "
        "and never once starts over",
        "the family is a stretch of a sequence held under a rule. When the rule "
        "breaks you give ground at the back, you do not go back to the start",
        "you never go back to the beginning. When the rule breaks you "
        "give ground at the back and keep going",
    ),
    "TWO_POINTER": (
        "it wants two hands, one from each end, neither of them ever turning "
        "round",
        "the family is convergence: both ends walk toward each other, and "
        "neither of them ever retraces a step",
        "two ends, walking in, and the discipline that neither of them is "
        "ever allowed to turn round",
    ),
    "PREFIX_SUM": (
        "it wants running totals kept as you go, so any stretch can be asked "
        "about afterwards without walking it again",
        "the family is paying once for a measurement and then answering every "
        "question about it for free",
        "measure once as you walk, and then answer questions about any "
        "stretch of the walk without walking it again",
    ),
    "STACK": (
        "it wants the order things close in. Everything down here closes in the "
        "order it opened",
        "the family is nesting: the last thing you opened is the first thing "
        "that has to be finished",
        "the last thing opened is the first thing that has to close, and "
        "everything in that place obeys it",
    ),
    "QUEUE": (
        "it wants the oldest thing first, every time, without exception",
        "the family is a line of waiting things where fairness is the whole "
        "mechanism",
        "oldest first, no exceptions, and the whole mechanism is that "
        "there are no exceptions",
    ),
    "HEAP": (
        "it wants the smallest thing out of a pile, repeatedly, without sorting "
        "the pile",
        "the family is priority: you never need the whole order, only whatever "
        "is worst or best right now",
        "you never need the pile in order. You need the worst of it, now, "
        "and then the next worst",
    ),
    "SORTING": (
        "it wants order bought deliberately, and an honest account of what the "
        "order cost",
        "the family is arranging first so that the second pass is trivial. Most "
        "of the work is deciding to do it",
        "arrange it first and the second pass becomes trivial. Most of "
        "the work is deciding to spend the first pass",
    ),
    "BINARY_SEARCH": (
        "it wants halving. Look in the middle, throw half away, and be certain "
        "which half",
        "the family is an ordered thing and the discipline to discard most of "
        "it on every look",
        "look in the middle, throw half away, and be able to say why it "
        "was the right half",
    ),
    "INTERVALS": (
        "it wants ranges that overlap, sorted first and then walked once",
        "the family is stretches with starts and ends, and the question of "
        "where two of them touch",
        "stretches with two ends, arranged by where they start, then "
        "walked once to find where they touch",
    ),
    "MATRIX": (
        "it wants rows and columns held in the right order, and the whole plan "
        "turned without a second plan",
        "the family is a grid, and the discipline of always doing rows before "
        "columns",
        "rows before columns, every time, and the whole plan turned "
        "rather than a second plan drawn",
    ),
    "RECURSION": (
        "it wants the stopping condition said out loud before you go down",
        "the family is a thing that contains a smaller copy of itself, and the "
        "nerve to trust the smaller copy",
        "the smaller copy is correct. Your job is only to say what you do "
        "with what it hands back",
    ),
    "TREE": (
        "it wants branches that split and never rejoin, walked in one fixed "
        "order",
        "the family is structure with a top: what is left, what is under, what "
        "is right, and never those three in a different order",
        "a top, two ways down from everywhere, and one fixed order of "
        "visiting that you never vary",
    ),
    "DFS": (
        "it wants one committed path followed all the way down before any "
        "other is considered",
        "the family is going deep first and coming back up carrying whatever "
        "the depth found",
        "commit to one path, follow it to the bottom, and carry the "
        "bottom's answer back up",
    ),
    "BFS": (
        "it wants the search that spreads in rings, because rings are what "
        "make the shortest road shortest",
        "the family is everything one step away, then everything two steps "
        "away, and marking a place the moment you decide to go there",
        "rings outward from where you started, and a place is spoken for "
        "the moment you decide to go there",
    ),
    "GRAPH": (
        "it wants a graph traversal. Every ruin connects to several others and "
        "only one of those is on the way anywhere",
        "the family is a lattice of places and the question of which walk "
        "through it answers the question asked",
        "places joined to places, and the question of which walk through "
        "them answers what was actually asked",
    ),
    "DP": (
        "it wants the tile you already solved to stay lit, so you never pay for "
        "it twice",
        "the family is turning the same work done many times into the same work "
        "done once and remembered",
        "pay for a thing once, keep what it cost you, and walk over it "
        "free for the rest of the problem",
    ),
    "BIG_O": (
        "it wants you to say what it costs, and to be right about that before "
        "anyone checks",
        "the family is counting the work per element and multiplying by the "
        "elements. Correct is not the same as fast",
        "work per element, multiplied by elements. Say the number before "
        "somebody asks you for it",
    ),
    "GREEDY": (
        "it wants the locally obvious choice, and an argument for why the "
        "locally obvious choice is safe here",
        "the family is taking the best step in front of you and being able to "
        "defend never looking further",
        "take the good step in front of you, and be ready to defend never "
        "having looked past it",
    ),
    "SIMULATION": (
        "it wants the rules followed exactly, step after step, with no "
        "cleverness introduced anywhere",
        "the family is doing what the description said, in the order it said "
        "it, and not being clever about the order",
        "do exactly what was described, in the order described, and "
        "resist every urge to improve on it",
    ),
    "DESIGN": (
        "it wants several things kept in agreement at once, each one cheap to "
        "ask about",
        "the family is building the thing rather than solving the puzzle: what "
        "does it hold, what can it be asked, how fast does it answer",
        "several things kept true about each other at once, each one "
        "cheap to ask about",
    ),
    "DEBUGGING": (
        "it wants the failing input read, and then traced by hand. That is the "
        "whole method and there is not a second one",
        "the family is a program that worked once, on somebody's machine, for "
        "one input, and the patience to find out which",
        "the failing input, read slowly, traced by hand. There is no "
        "second method and there never was",
    ),
    "TESTING": (
        "it wants a suite that a wrong answer would actually fail",
        "the family is thinking of the input that breaks it before the input "
        "that breaks it thinks of you",
        "think of the input that breaks it before that input thinks of "
        "you",
    ),
    "COMMUNICATION": (
        "it wants the approach said aloud before the first keystroke. If you "
        "cannot say it you do not have one",
        "the family is explanation. Half of what is being measured is whether "
        "the person opposite understood you",
        "say the approach out loud first. Half of what is measured is "
        "whether the person opposite followed you",
    ),
    "SPEED": (
        "it wants something you already know, known faster than you can doubt "
        "yourself",
        "the family is not new work. It is old work with a clock on it, which "
        "is a different skill and nobody admits that",
        "old work with a clock on it, which is a different skill from the "
        "work and nobody admits that",
    ),
    "RECALL": (
        "it wants recognition with nothing labelled. No signpost tells you what "
        "is being asked",
        "the family is everything you have already done, arriving in a coat you "
        "have not seen it wear",
        "nothing labelled, nothing signposted, and everything you have "
        "already done arriving in a coat you have not seen",
    ),
}


# ==========================================================================
# SECTION 5 — REGISTERS
# ==========================================================================
#
# The brief's point D: a town should not sound like one person wearing different
# sprites. A register is a VOICE — what this kind of person notices first, what
# they measure things in, and what they would never say.
#
# Ten of them, covering all thirty-four NPCs in quests.NPCS, the smith in
# forge.SMITH, and all twelve mentors in world.MENTORS. Forty-seven speakers,
# ten voices, and `self_check` proves every speaker has one.
#
# `bias` shifts the beat scores in Section 8. A smith reaches for WHERE because
# a smith's whole world is where the metal is; a warden reaches for AREA because
# a warden's whole job is the ground. Nobody is silent on any beat — the bias
# decides what they lead with, not what they are capable of.

SMITH = "SMITH"
VENDOR = "VENDOR"
WARDEN = "WARDEN"
LABOURER = "LABOURER"
SCHOLAR = "SCHOLAR"
RANGER = "RANGER"
CHILD = "CHILD"
SOLDIER = "SOLDIER"
MENTOR = "MENTOR"
STEWARD = "STEWARD"


@dataclass(frozen=True)
class Register:
    id: str
    label: str
    voice: str          # what this kind of person notices first
    measure: str        # the unit they count in, which is most of a voice
    bias: dict          # beat -> score adjustment


REGISTERS: dict = {
    SMITH: Register(
        SMITH, "the smith",
        "Numerate and unsentimental. She has never once said a weapon was "
        "worthy of anyone, and she is not going to start with yours.",
        "bars, fees and fights-per-bar",
        {WHERE: 26, GEAR: 12, AREA: -6, AHEAD: -4, PROVED: 0}),
    VENDOR: Register(
        VENDOR, "the shopkeeper",
        "Transactional, well-informed, and bored of being told what people are "
        "about to attempt. They know what is in stock and what is not.",
        "coin, and what came in on the last cart",
        {WHERE: 22, AREA: 4, GEAR: 6, AHEAD: 0, PROVED: 4}),
    WARDEN: Register(
        WARDEN, "the warden",
        "Their entire job is the ground and what is standing on it. They will "
        "tell you the danger plainly and then decline to stop you.",
        "what has come back and what has not",
        {AREA: 22, GEAR: 16, AHEAD: 4, WHERE: -4, PROVED: 2}),
    LABOURER: Register(
        LABOURER, "the working hand",
        "They do a specific job with their arms and have opinions about the "
        "people who design the conditions. Funny, tired, precise about the "
        "part they own.",
        "shifts, loads and the thing that broke last week",
        {AREA: 10, GEAR: 8, WHERE: 10, PROVED: 12, AHEAD: 0}),
    SCHOLAR: Register(
        SCHOLAR, "the record-keeper",
        "They keep the written version of a place and are quietly annoyed that "
        "the place keeps disagreeing with it. They state things exactly.",
        "entries, tallies and the count of times a thing has been done before",
        {AHEAD: 18, AREA: 8, WHERE: 8, PROVED: 6, GEAR: -2}),
    RANGER: Register(
        RANGER, "the one who walks it",
        "They move through the land for a living and think of everything as a "
        "route. The least dramatic people in the game and the most useful.",
        "hours of walking and where a thing lives",
        {WHERE: 16, AREA: 14, GEAR: 10, AHEAD: 4, PROVED: 2}),
    CHILD: Register(
        CHILD, "the child",
        "Reports what they saw, accurately, without any of the framing an "
        "adult would add. Gives no advice and is frequently the best source in "
        "the village.",
        "what happened, and who it happened to",
        {AREA: 12, PROVED: 16, WHERE: 10, AHEAD: 6, GEAR: 6}),
    SOLDIER: Register(
        SOLDIER, "the drilled one",
        "Order, sequence and the consequences of doing things in the wrong "
        "one. Brisk. Does not consider encouragement part of the job.",
        "correct order, and the number of times it has been got wrong",
        {AHEAD: 14, GEAR: 14, AREA: 6, PROVED: 6, WHERE: 0}),
    MENTOR: Register(
        MENTOR, "the teacher",
        "They teach one thing and see the whole world through it. Warmer than "
        "the rest of the town and no softer.",
        "the one pattern they are responsible for",
        {AHEAD: 24, PROVED: 12, AREA: 4, GEAR: 4, WHERE: -2}),
    STEWARD: Register(
        STEWARD, "the steward of an empty house",
        "Keeps a castle nobody lives in, for a king who removed the labels "
        "rather than the rooms. Formal, patient, and entirely without hope.",
        "rooms, and how long since anyone was in them",
        {AREA: 16, AHEAD: 14, PROVED: 10, GEAR: 4, WHERE: -6}),
}

REGISTER_IDS: tuple = tuple(REGISTERS)


# --------------------------------------------------------------------------
# Who speaks in which voice
# --------------------------------------------------------------------------
#
# Written out rather than derived from the `role` string, because the roles in
# quests.NPCS are free prose ("an eight-year-old with a stick") and deriving a
# voice from prose is how a cook ends up talking like a drill sergeant.
#
# All thirty-four, grouped by region so the assignment can be read against the
# map. The pairing rule is that no region has two speakers in the same register
# where it can be avoided — a place with two voices should have two voices.

NPC_REGISTER: dict = {
    # -- Python Village -----------------------------------------------------
    "odile": LABOURER,      # mason. Scaffolding holding up other scaffolding.
    "tamsin": RANGER,       # seed-keeper. Thinks in seasons and in ground.
    "pel": CHILD,           # eight years old, and doing a route.

    # -- Fields of Syntax ---------------------------------------------------
    "harrow": WARDEN,
    "nils": LABOURER,       # fence-mender. A fence with one gap is a shape.

    # -- Hashmap Highlands --------------------------------------------------
    "vela": VENDOR,         # tollkeeper. Takes coin, gives keys, keeps a ledger.
    "brant": WARDEN,

    # -- Stringwood Labyrinth -----------------------------------------------
    "quill": SCHOLAR,       # namer of things, which is the scholar's whole job
    "moss": RANGER,         # forager. Navigates by spelling.

    # -- Array Caverns ------------------------------------------------------
    "dorn": VENDOR,         # quartermaster. Issues things and counts them.
    "esk": LABOURER,        # lamp-runner, twice a shift, end to end.

    # -- Sliding Window Marsh -----------------------------------------------
    "fenn": WARDEN,         # levee-keeper. The ground is literally his job.
    "sable": RANGER,        # ferrier. Every crossing is a route decision.

    # -- Twin Pointer Pass --------------------------------------------------
    "ondra": SOLDIER,       # convoy master. Two carts, one from each end.
    "kell": WARDEN,

    # -- Stack & Queue Mines ------------------------------------------------
    "greave": LABOURER,     # lift engineer
    "pitch": LABOURER,      # cart-boss. Deliberately two labourers: the Mines
                            # are a place where everyone has a specific job and
                            # nobody has a view of the whole.

    # -- Matrix Citadel -----------------------------------------------------
    "lorne": SCHOLAR,       # archivist of the floor plans
    "ives": SOLDIER,        # drillmaster. Rows, then columns. Always that order.

    # -- Recursive Forest ---------------------------------------------------
    "halla": RANGER,        # forester
    "bram": SCHOLAR,        # keeper of the inner grove. Says the condition aloud.

    # -- Binary Tree Canopy -------------------------------------------------
    "wren": RANGER,         # rookery keeper
    "alder": LABOURER,      # climber. It is a job with rope in it.

    # -- Graph Wastes -------------------------------------------------------
    "corvin": RANGER,       # courier. The purest route-thinker in the game.
    "mira": VENDOR,         # waystation cook. Feeds whoever arrives.

    # -- Dynamic Programming Ruins ------------------------------------------
    "tolliver": SCHOLAR,    # tallykeeper
    "nima": SCHOLAR,        # surveyor. Two scholars, because the Ruins are a
                            # place made entirely of other people's records.

    # -- Debugging Dungeon --------------------------------------------------
    "garrick": LABOURER,    # forge apprentice, two days into one crack
    "ilsa": WARDEN,         # keeper of the cells

    # -- Complexity Tower ---------------------------------------------------
    "ember": LABOURER,      # lamplighter, with opinions about the architect
    "stave": LABOURER,      # porter, who measures loads in floors

    # -- The Coding Coliseum ------------------------------------------------
    "junia": VENDOR,        # ticket clerk
    "bosk": LABOURER,       # sand-raker

    # -- The Null King's Castle ---------------------------------------------
    "steward": STEWARD,
}

# The smith is not in quests.NPCS — forge.py owns her, including her sprite and
# her voice — so she is adopted here by id rather than copied.
SMITH_ID = forge.SMITH["id"]

# Every mentor teaches, so every mentor is a MENTOR. What differs is the subject,
# and the subject is what the AHEAD beat fills with.
MENTOR_SUBJECT: dict = {
    "byte": "PYTHON",
    "archivist": "HASH_MAP",
    "ranger": "TWO_POINTER",
    "window_mage": "SLIDING_WINDOW",
    "druid": "RECURSION",
    "cartographer": "GRAPH",
    "armorer": "DEBUGGING",
    "oracle": "BIG_O",
    "testsmith": "TESTING",
    "chronomancer": "SPEED",
    "scribe": "COMMUNICATION",
    "interviewer": "RECALL",
}


def register_of(speaker_id: str) -> str:
    """The voice this speaker uses. Unknown speakers get the working hand,
    which is the register with the fewest assumptions in it."""
    if speaker_id == SMITH_ID:
        return SMITH
    if speaker_id in NPC_REGISTER:
        return NPC_REGISTER[speaker_id]
    if speaker_id in world.MENTORS:
        return MENTOR
    return LABOURER


def speaker(speaker_id: str) -> dict:
    """Name, role, sprite and home region for anyone this module can voice.

    Three sources, one shape. quests.NPCS first because it is the largest,
    forge.SMITH second because she is one person, world.MENTORS last because a
    mentor has no home region of its own — it has whichever regions list it.
    """
    npc = quests.NPCS.get(speaker_id)
    if npc:
        return {"id": speaker_id, "name": npc["name"], "role": npc["role"],
                "sprite": npc["sprite"], "region": npc["region"],
                "register": register_of(speaker_id), "kind": "npc"}
    if speaker_id == SMITH_ID:
        return {"id": speaker_id, "name": forge.SMITH["name"],
                "role": forge.SMITH["role"], "sprite": forge.SMITH["sprite"],
                "region": forge.SMITH["region"], "register": SMITH,
                "kind": "smith"}
    mentor = world.MENTORS.get(speaker_id)
    if mentor:
        homes = [r["id"] for r in world.REGIONS if r.get("mentor") == speaker_id]
        return {"id": speaker_id, "name": mentor["name"], "role": mentor["role"],
                "sprite": mentor["sprite"], "region": homes[0] if homes else "",
                "register": MENTOR, "kind": "mentor",
                "subject": MENTOR_SUBJECT.get(speaker_id, "")}
    return {}


SPEAKERS: tuple = tuple(list(quests.NPCS) + [SMITH_ID] + list(world.MENTORS))


# ==========================================================================
# SECTION 6 — THE FRAMES
# ==========================================================================
#
# Ten registers times five beats times four frames. Two hundred authored
# sentences, and every one of them has a hole in it that live state fills.
#
# SLOT DISCIPLINE, which `audit` enforces:
#   * a frame may only reach for the slots its beat defines in BEAT_SLOTS
#   * every frame must reach for at least one, or it is not reading the
#     situation and does not belong in this file
#   * no composed line may open a sentence in lower case
#
# Two kinds of thing arrive in a slot. PROPER-NOUN slots carry something already
# capitalised — a region, a boss, a quest title, a metal. PROSE slots carry a
# lower-case clause, because most of them land mid-sentence. A frame may open
# with either: `_sentence_case` in Section 8 capitalises whatever lands at the
# start of a sentence, which is why the frames below read like speech rather
# than like a template.
#
# The frames carry the voice and nothing else. Every fact in a finished line
# came out of Sections 3, 4 or 7, which is why a metal moving region changes
# what two hundred sentences say without any of them being edited.

# --------------------------------------------------------------------------
# WHERE frames and the ground you are standing on
# --------------------------------------------------------------------------
#
# A WHERE line names the place a thing comes from, and that place is very often
# the region the player is already in — the local vendor's shelf ALWAYS is, and
# the region's own metal and its resident companion usually are. A frame written
# as travel advice then produces "Go to Graph Wastes for a Flask of Clean Blood"
# said by somebody standing in Graph Wastes, and a frame written as local
# knowledge produces "it comes up out of this ground" about a marsh two regions
# away. Both were happening.
#
# Most frames are true either way and carry no marker. The ones that commit are
# tagged with a leading marker, stripped in `_render`, which picks from the
# subset that is true of THIS place. `self_check` proves every register keeps a
# usable frame in both localities, and that no marker ever reaches a player.
HERE = "\x01"      # the place is the ground underfoot
AWAY = "\x02"      # the place is somewhere the player must travel to
_MARKERS = (HERE, AWAY)


def _frame_locality(frame: str) -> str:
    return frame[0] if frame[:1] in _MARKERS else ""


def _frames_for(register: str, beat: str, *, local: bool | None = None) -> tuple:
    """The frames usable right now. `local` is None for every beat but WHERE."""
    pool = FRAMES[register][beat]
    if local is None:
        return pool
    forbidden = AWAY if local else HERE
    return tuple(f for f in pool if _frame_locality(f) != forbidden) or pool


_PROPER_SLOTS = frozenset({"region", "place", "where_ahead", "ahead", "deed",
                           "proved", "thing"})
_PROSE_SLOTS = frozenset({"weather", "hazard", "gear", "counter", "boots",
                          "demand", "rate"})

FRAMES: dict = {

    # ---------------------------------------------------------------------
    # SMITH — Vess. She counts. She does not encourage.
    # ---------------------------------------------------------------------
    SMITH: {
        AREA: (
            "People bring me metal out of {region} and tell me about it at "
            "length. What they never mention is that {weather}.",
            "{region}. I have had the same complaint from four people this "
            "month: {weather}. It is not a complaint. It is the place.",
            "You are asking about {region}. Fine. {hazard}, and that is before "
            "anything in there has noticed you.",
            "Half the bent plate on that wall came out of {region}, where "
            "{weather}. The other half came out of carelessness.",
            "There is nothing wrong with {region} that is not also the entire "
            "point of {region}. {weather}.",
        ),
        GEAR: (
            "Put it on the bench. There — {gear}. I am not going to dress that "
            "up for you.",
            "I can see what you are carrying from here, and {gear}. If you want "
            "my advice, which you did not ask for: {counter}.",
            "Your feet are the part everyone forgets. Down there, {boots}.",
            "I do not sell luck. What I can tell you is that {counter}, and "
            "that {gear}.",
            "Two things and then I am back to work. {gear}. And for the "
            "record, {counter}.",
        ),
        AHEAD: (
            "{ahead} is next for you, out of {where_ahead}, and {demand}. Bring "
            "me the blade before you go, not after.",
            "You will meet {ahead} sooner than you would like. Word from the "
            "people who came back is that {demand}.",
            "Everything on that wall was brought to me by somebody who was "
            "about to fight {ahead}. In every case {demand}, and in most cases "
            "they had not thought about it.",
            "{where_ahead} is where you are going whether you have decided or "
            "not. What waits there is {ahead}, and {demand}.",
            "I have had blades back on this bench four times over {ahead}, "
            "and every time the gap was the same. {demand}. Know that before "
            "you go.",
        ),
        PROVED: (
            "{deed}. I heard. People came in and told me, which they do not "
            "generally do.",
            "You did {deed} and the thing stayed done, which is rarer than the "
            "doing. {proved}",
            "{proved} I am told that was you. I have no reason to doubt it and "
            "no intention of making a speech about it.",
            "They still talk about {deed} in here. Mostly they talk about it "
            "while waiting for me to finish something else.",
            "{proved} That shows up as trade eventually, and trade is the "
            "only way I can tell anything has happened.",
        ),
        WHERE: (
            "{thing} comes out of {place}, and {rate}. Those are the numbers. "
            "Do what you like with them.",
            "You are short. The shortfall is {thing}, it is in {place}, and "
            "{rate}. That is the entire conversation.",
            "If you want the next rung you want {thing}. {place}, and {rate}. "
            "Bosses there give three at once, which is the only generosity in "
            "this system.",
            "People stop trying at this point because they think the upgrade is "
            "a wall. It is not a wall, it is {thing}, {place}, and {rate}.",
            "{thing}, out of {place}, and {rate}. Stop looking at me as "
            "though I am about to produce some.",
        ),
    },

    # ---------------------------------------------------------------------
    # VENDOR — a counter, a ledger, and no patience for ambition.
    # ---------------------------------------------------------------------
    VENDOR: {
        AREA: (
            "You are going out into {region}, then. I will tell you what I tell "
            "everyone: {weather}.",
            "I stock for {region}, which means I stock for the fact that "
            "{weather}. The stock is not sentimental and neither am I.",
            "Everyone who comes back through here from {region} says the same "
            "thing about the ground. {hazard}.",
            "{region} takes more out of a person than the map suggests, chiefly "
            "because {weather}.",
            "{region}, then. I will enter that as a departure rather than a "
            "visit, because {weather}.",
        ),
        GEAR: (
            "I can see what you are wearing and I am obliged to mention that "
            "{gear}. Consider it mentioned.",
            "Free with every purchase, whether you want it or not: {counter}.",
            "Your feet. Look at your feet. On that ground, {boots}.",
            "I do not tell people how to fight. I do tell them that {gear}, "
            "because people who ignore that stop coming back and that is bad "
            "for trade.",
            "Nobody asks me this and everybody should. {boots}. That is the "
            "whole of my expertise and it costs nothing.",
        ),
        AHEAD: (
            "You are provisioning for {ahead}, I take it. Everyone who does "
            "that comes back and tells me {demand}.",
            "{ahead}, out of {where_ahead}. I have had four people in this "
            "week buying for that, and not one of them had worked out that "
            "{demand}.",
            "There is a run on supplies every time someone decides to try "
            "{ahead}. The ones who come back say {demand}.",
            "{where_ahead} is the next thing on your road and {ahead} is the "
            "thing standing in it. For what it is worth, {demand}.",
            "Provision for {where_ahead} if you must. The thing in it is "
            "{ahead}, and {demand}, and none of that is for sale in here.",
        ),
        PROVED: (
            "{deed}. That was you. I put it in the ledger, which is where I put "
            "things that actually happened.",
            "{proved} Trade has been better since. I am not going to pretend "
            "that is unrelated.",
            "You are the one who did {deed}. I remember faces attached to "
            "outcomes. It is most of the job.",
            "{deed} changed what people buy in here, which is the only measure "
            "of anything I trust.",
            "People still ask about {deed} in here. I tell them, and then I "
            "sell them something.",
        ),
        WHERE: (
            "What I can get in, at this tier, is {thing}. {place} supplies it "
            "and {rate}.",
            "{thing}. That is what I have, that is where it comes from — "
            "{place} — and {rate}. Anything grander has to be walked to.",
            "People ask me for things from four chapters further on. What I "
            "have is {thing}, out of {place}, and {rate}.",
            "{place} sends me {thing} when the road is open, and {rate}. When "
            "the road is not open I sell rope.",
            "If you want {thing} I can tell you where it is and decline to "
            "sell it to you. {place}, and {rate}.",
        ),
    },

    # ---------------------------------------------------------------------
    # WARDEN — the ground and what is standing on it. Plain, then out of
    # the way.
    # ---------------------------------------------------------------------
    WARDEN: {
        AREA: (
            "I will say this once and then stand aside. In {region}, {weather}.",
            "{region} is mine to watch and I watch it honestly: {hazard}.",
            "People ask me whether {region} is safe. It is not safe. {weather}, "
            "and that is the ordinary condition rather than the bad day.",
            "{hazard}. That is {region} in one sentence and I have never needed "
            "a second.",
            "I have stood at this post eleven years and the ground has not "
            "altered once. {hazard}.",
        ),
        GEAR: (
            "Stand still. Right — {gear}. Now you know, and what you do about "
            "it is yours.",
            "The ones who come back out again are the ones who were told this and "
            "then did it: {counter}.",
            "Ground like that eats footwear. As things stand, {boots}.",
            "I am not going to stop you. I am going to note that {gear}, and "
            "that I said so.",
            "You may pass. You may also listen for four seconds: {counter}.",
        ),
        AHEAD: (
            "{ahead} holds the far end of this and {demand}. That is all the "
            "warning anyone gets.",
            "Past my post is {where_ahead}, and {ahead} is in it. Everything "
            "that has come back out agrees that {demand}.",
            "You will want to know about {ahead} before you meet it. {demand}. "
            "Go and learn that part somewhere quiet.",
            "I have watched people walk at {ahead} unprepared for years. It is "
            "always the same gap: {demand}, and they had not thought about it "
            "once.",
            "{ahead}. I have nothing to add to that name except the one fact "
            "worth having: {demand}.",
        ),
        PROVED: (
            "{deed}. My post has been quieter since, and I notice quiet.",
            "{proved} I was here before that and I am here after it. The "
            "difference is measurable.",
            "You did {deed} and then left without waiting to be thanked, which "
            "I respected and am now ruining.",
            "I keep a record of what has gone wrong on this stretch. {deed} is "
            "the last entry, and it is a closed one.",
            "{deed}. I have reduced the watch on that stretch, and I do not "
            "do that lightly.",
        ),
        WHERE: (
            HERE + "{thing} comes off this ground, if you are asking. {place}, and "
            "{rate}.",
            "People come through looking for {thing}. It is in {place} and "
            "{rate}. I send them on and most of them go.",
            "{place} gives up {thing} to anyone willing to fight for it, and "
            "{rate}. That is not a secret. It is simply unpopular work.",
            "If you want {thing} then you want {place}, and you should know "
            "before you leave this gate that {rate}.",
            AWAY + "{place} has {thing} in it and I am not going in there for it. "
            "{rate}.",
        ),
    },

    # ---------------------------------------------------------------------
    # LABOURER — a specific job, done with the arms, and opinions about
    # whoever designed the conditions.
    # ---------------------------------------------------------------------
    LABOURER: {
        AREA: (
            "You want to know about {region}? I work it. {weather}, and nobody "
            "who drew the plans has ever stood in it.",
            "Third shift in {region} teaches you one thing and it is that "
            "{weather}.",
            "{hazard}. I have said that at every safety meeting for six years "
            "and the meetings continue.",
            "{region} is fine for about an hour. After the hour you notice that "
            "{weather}, and then it is all you notice.",
            "{weather}. That is not me complaining about {region}. That is me "
            "describing it.",
        ),
        GEAR: (
            "No offence meant, but {gear}. I have seen what happens to people "
            "who go in like that and it is mostly limping.",
            "The old hands here tell everyone the same thing, and they are old "
            "because of it: {counter}.",
            "Look down. Ground like that, {boots}. That is not advice, that is "
            "just what will happen.",
            "Every season somebody arrives and I have to say this: {gear}. Then "
            "they go in anyway, and then they come and find me.",
            "I have carried people out of there. Every one of them, {gear}. "
            "Draw whatever conclusion you like.",
        ),
        AHEAD: (
            "{ahead} is what is waiting past the end of my shift, and the word "
            "on it is that {demand}.",
            "Nobody down here talks about anything except {ahead}. What they "
            "have worked out is that {demand}.",
            "{where_ahead}. That is the next stop, and {ahead} is in it, and "
            "{demand}. I would go and read about that part before walking.",
            "We had a man through here on his way to {ahead}. Very confident. "
            "He had not grasped that {demand}, and we did not see him come back "
            "this way.",
            "The lads run a book on who gets past {ahead}. The odds move on "
            "one thing only, and it is whether {demand} has sunk in yet.",
        ),
        PROVED: (
            "{deed}. That was you. It comes up at breaks. It comes up a lot at "
            "breaks.",
            "{proved} That is the difference in my working day, and I am the "
            "one who has to notice it.",
            "You did {deed}. I have stopped having to do the thing that job "
            "replaced, which is about as fond as I get.",
            "{deed}, and it held. Most things people fix around here do not "
            "hold past the first bad week.",
            "I owe you for {deed} and I have no way of paying it, so you are "
            "getting a conversation instead.",
        ),
        WHERE: (
            HERE + "{thing} comes up out of this ground. {place}, and {rate}, if you "
            "have the patience for it.",
            "You are after {thing}. So is everyone. It is in {place} and "
            "{rate}, and there is no faster road, and I have looked.",
            "{place} is where {thing} comes from and {rate}. I carry the stuff. "
            "I do not get to keep any of it.",
            "Half my shift is hauling {thing} out of {place}, and I can tell "
            "you exactly what it is worth: {rate}.",
            "We used to haul {thing} up out of {place}. {rate}, and my back "
            "has a view about that.",
        ),
    },

    # ---------------------------------------------------------------------
    # SCHOLAR — the written version of a place, and a quiet grievance that
    # the place keeps disagreeing with it.
    # ---------------------------------------------------------------------
    SCHOLAR: {
        AREA: (
            "{region} is recorded in three places and all three agree on one "
            "detail only: {weather}.",
            "I will give you the accurate version rather than the popular one. "
            "In {region}, {weather}.",
            "The survey of {region} is four years out of date except for one "
            "line, which is still true: {hazard}.",
            "People describe {region} badly, which I find irritating, so: "
            "{weather}. That is the whole of it and nothing else is required.",
            "Entry for {region}, abridged, because the full one runs four "
            "pages and three of them are apologies: {weather}.",
        ),
        GEAR: (
            "I observe, without judgement, that {gear}. Observation is most of "
            "what I do.",
            "There is a documented and slightly boring instruction about this that "
            "nobody reads: {counter}.",
            "Footwear is under-recorded in every account of this place. In "
            "yours, {boots}.",
            "If I were writing you up as an entry, the entry would note that "
            "{gear}, and the entry would be correct.",
            "A small correction to how you are equipped, offered without any "
            "warmth at all: {gear}.",
        ),
        AHEAD: (
            "{ahead} is the next thing of consequence on your road, and the "
            "record on it is consistent: {demand}.",
            "I have every account of {ahead} that survived. They disagree about "
            "everything except this: {demand}.",
            "{where_ahead} holds {ahead}, and I would rather you heard the "
            "useful part from me than from a song about it: {demand}.",
            "You could go at {ahead} unread. People do. The entries on those "
            "people are short. {demand}.",
            "Cross-reference on {ahead}, in one line, since you will not read "
            "the entry: {demand}.",
        ),
        PROVED: (
            "{deed}. I have it written down, which in here means it happened.",
            "{proved} I updated the record the same afternoon. It is not often "
            "I get to correct a thing in the right direction.",
            "The entry for {deed} is one of the few in this room with an ending "
            "on it.",
            "{deed} closed a question that had been open in these files for "
            "longer than I have been in this room.",
            "{deed}. I have had to rewrite the standing entry, which is work, "
            "and I am not complaining.",
        ),
        WHERE: (
            "{thing} is recorded as coming out of {place}. The working note "
            "against it reads: {rate}. The record has never been wrong about "
            "that.",
            "{place}. That is where {thing} is, and {rate}. I am told this is "
            "the sort of thing people actually want from an archive.",
            "There is a whole shelf on {thing}. The only sentence on that shelf "
            "you need is: {place}, and {rate}.",
            AWAY + "If you are hunting {thing}, do not hunt. Go to {place}. {rate}. "
            "And then stop asking around.",
            "{thing} is catalogued under places rather than under things, "
            "which tells you something. {place}. {rate}.",
        ),
    },

    # ---------------------------------------------------------------------
    # RANGER — people who walk it for a living. The least dramatic voices in
    # the game and the most useful.
    # ---------------------------------------------------------------------
    RANGER: {
        AREA: (
            "I walk {region} most weeks. What you need to know is that "
            "{weather}.",
            "{region} is a day and a half if the weather holds, and it does "
            "not, because {weather}.",
            "The route through {region} is fine. The ground is the problem: "
            "{hazard}.",
            "People plan for the distance in {region} and not for the fact that "
            "{weather}. Then they are out there in the dark.",
            "I have taken people through {region} who did not believe me "
            "about this until it happened to them. {hazard}.",
        ),
        GEAR: (
            "Before you go: {gear}. I would rather say it here than find out "
            "about it later.",
            "Everyone who walks that road arrives at the same conclusion, and here "
            "it is: {counter}.",
            "Boots first, always. On that ground, {boots}.",
            "I am not going to tell you not to go. I am going to tell you that "
            "{gear}, and then I am going to let you go.",
            "One more thing and then the road is yours. {boots}.",
        ),
        AHEAD: (
            "{ahead} sits at the far end of that road, and everyone who has "
            "walked back says {demand}.",
            "Two days out of here is {where_ahead}, and {ahead} is in it, and "
            "{demand}.",
            "I have carried messages past {ahead} and I have never once stopped "
            "to fight it. If you intend to, know that {demand}.",
            "The road to {ahead} is not the hard part. {demand}, and that is "
            "the part you prepare for indoors.",
            "I will walk you as far as {where_ahead} and not a step past it. "
            "What is in there is {ahead}, and {demand}.",
        ),
        PROVED: (
            "{deed}. I use that road now. I used to go round.",
            "{proved} That saves me most of a morning every week, which is a "
            "thing I think about more than you would expect.",
            "You did {deed}. I have told roughly forty people about it, none of "
            "whom asked.",
            "{deed} changed the route. Things that change the route are the "
            "only things I remember.",
            "{proved} I noticed on the second pass. I notice on the second "
            "pass, always.",
        ),
        WHERE: (
            "{thing}? {place}. {rate}, in my experience, and my experience is "
            "mostly walking.",
            "You want {thing}. It is in {place} and {rate}. I would go now "
            "rather than in the wet.",
            AWAY + "{place} is two days that way and it is full of {thing}, and "
            "{rate}. That is the whole errand.",
            "I know where most things live. {thing} lives in {place}, and "
            "{rate}, and it will not come to you.",
            AWAY + "{thing} is a walk, not a purchase. {place}, and {rate}.",
        ),
    },

    # ---------------------------------------------------------------------
    # CHILD — reports what was seen, accurately, without the framing an adult
    # would add. Gives no advice and is frequently the best source in town.
    # ---------------------------------------------------------------------
    CHILD: {
        AREA: (
            "I am not allowed in {region}. It is because {weather}. That is "
            "what they said, anyway.",
            "My route goes near {region}. I do not go in. {hazard}, and I am "
            "eight, not stupid.",
            "A man came back from {region} and sat down in the road for a while "
            "before he said anything. {weather}. He told me that bit.",
            "{region} is on my map. I drew a face on it. The face is because "
            "{weather}.",
            "There is a rhyme about {region} and the true part is the middle "
            "bit. {weather}. The rest of it is about a horse.",
        ),
        GEAR: (
            "There was a man with the wrong things and everyone kept looking at "
            "him. {gear}. I am only saying what they said.",
            "The old ones all say the same sentence to everybody: {counter}. "
            "They say it in the same voice as well.",
            "I look at people's feet. It is a thing I do. {boots}.",
            "I am not telling you what to do. But {gear}, and I heard three "
            "people say so, separately.",
            "My mother says you can always tell. She looked at you for a bit "
            "and then she said {boots}.",
        ),
        AHEAD: (
            "{ahead} is the one in the song. The song is wrong about nearly all "
            "of it except {demand}.",
            "Nobody will tell me about {ahead} properly, so I listen at the "
            "door instead. {demand}. That is the part they whisper.",
            "{where_ahead} is where {ahead} lives. I know because the grown-ups "
            "stop talking when you say the name. {demand}.",
            "I have decided I am going to fight {ahead} when I am bigger. I "
            "have been told {demand}, so I am practising that part.",
            "{ahead} is in {where_ahead}. My uncle went. He came back but he "
            "was quiet for ages, and what he said was {demand}.",
        ),
        PROVED: (
            "{deed}. That was you. I watched most of it from the wall.",
            "{proved} It was not like that before. I know because I am here all "
            "the time.",
            "You are the one who did {deed}. I told my mother and she said do "
            "not bother people, and here I am bothering you.",
            "I have a drawing of {deed}. It is not very good. You are the small "
            "orange one.",
            "Everyone knows about {deed} now. I knew first. I would like that "
            "written down somewhere.",
        ),
        WHERE: (
            "{thing} comes from {place}. I know that because people argue about "
            "it outside our door. {rate}, they say.",
            AWAY + "If you want {thing} you have to go to {place}, and {rate}, and "
            "everyone is always cross about it.",
            "{place} has {thing} in it. A woman with a cart told me. She said "
            "{rate} and then she said do not tell anyone.",
            "I keep a note of where things come from. {thing}: {place}. And "
            "{rate}, which I did not understand but I wrote it down.",
            AWAY + "I want to go to {place}, because that is where {thing} is. They "
            "say {rate}. They also say I am too small.",
        ),
    },

    # ---------------------------------------------------------------------
    # SOLDIER — order, sequence, and the consequences of the wrong one.
    # ---------------------------------------------------------------------
    SOLDIER: {
        AREA: (
            "{region}. Conditions, briefly: {weather}. That is the brief.",
            "You are asking about {region} and I will answer in the order it "
            "matters. Ground: {hazard}. Everything else is secondary.",
            "I have marched companies through {region}. The ones that arrived "
            "intact were the ones told in advance that {weather}.",
            "{weather}. Note it, act on it, and do not ask me to repeat it in "
            "{region} when it is already happening to you.",
            "{region}. I have marched it in both directions and the report is "
            "identical either way: {hazard}.",
        ),
        GEAR: (
            "Kit inspection. {gear}. Correct it or do not, but do it now rather "
            "than out there.",
            "Standing order, and it has never once been wrong: {counter}.",
            "Feet. Always feet. On that ground {boots}, and a column moves at "
            "the speed of its worst pair.",
            "I am obliged to tell you that {gear}. I am not obliged to tell you "
            "twice.",
            "Two corrections and no discussion. {gear}. And {counter}.",
        ),
        AHEAD: (
            "{ahead}. Objective, in one line: {demand}. Learn that before you "
            "form up.",
            "The next engagement is {ahead} in {where_ahead}, and the thing "
            "that decides it is that {demand}.",
            "I have lost people to {ahead} for one reason in every case. "
            "{demand}, and they were improvising.",
            "{where_ahead}, then {ahead}. In that order, and {demand}, and you "
            "do not get to reorder either of those.",
            "{ahead}. Not a skirmish. An examination. {demand}, and it will "
            "be looking for precisely that.",
        ),
        PROVED: (
            "{deed}. Logged, and closed. I do not reopen closed entries.",
            "{proved} That was the objective, that is the outcome, and the two "
            "match, which is rarer than it should be.",
            "You carried out {deed} to the standard. I will not be warmer about "
            "it than that and you should not want me to be.",
            "{deed} is on the board in the guardroom. It stays on the board.",
            "{deed}. Standard met. Next.",
        ),
        WHERE: (
            "Supply question. {thing}: it is in {place}, and {rate}. Requisition "
            "accordingly.",
            AWAY + "{place} is the source of {thing} and {rate}. Plan the trip once "
            "rather than making it twice.",
            AWAY + "{thing} does not arrive. It is fetched, from {place}, and {rate}. "
            "That is the whole of the supply chain in this country now.",
            "{thing}. Source, {place}. And the note beside it, which I am "
            "quoting: {rate}. There is no third option and I have looked for "
            "one.",
            "{thing}. {place}. {rate}. Dismissed.",
        ),
    },

    # ---------------------------------------------------------------------
    # MENTOR — they teach one thing and see the world through it. Warmer than
    # the rest of the town and no softer.
    # ---------------------------------------------------------------------
    MENTOR: {
        AREA: (
            "{region} teaches by making things cost more. {weather}, and that "
            "is a lesson delivered in the only language a place has.",
            "Every region in this world is an argument about something. "
            "{region} argues that {weather}.",
            "Before the pattern, the ground. In {region}, {hazard}. Learn the "
            "room before you learn the fight in it.",
            "I send students into {region} on purpose. {weather}, and a student "
            "who has felt that stops needing to be told it.",
            "The ground is the first lesson and it is the one everybody "
            "skips. In {region}, {weather}.",
        ),
        GEAR: (
            "Look at what you are carrying, and then look again, because "
            "{gear}.",
            "Preparation is not cheating and it never was. {counter}.",
            "You will spend an hour on that ground. Given the ground, {boots}.",
            "The mistake is thinking the reading of a room is separate from the "
            "work. It is not. {gear}.",
            "Somebody who has read the room has already done a third of the "
            "work. In your case, {gear}.",
        ),
        AHEAD: (
            "{ahead} is what you are walking toward, and {demand}. Go and "
            "practise that, tonight, badly, and then again tomorrow.",
            "I will not tell you how to beat {ahead}. I will tell you what it "
            "asks: {demand}. The asking is the part you can prepare for.",
            "{where_ahead} is the next chapter of this for you. {ahead} is in "
            "it and {demand}.",
            "There is one honest thing to say about {ahead}, and it is "
            "{demand}. Everything else is somebody selling you confidence.",
            "Everyone arrives at {ahead} believing it is a question of nerve. "
            "{demand}, and nerve is only what is left over once that is "
            "handled.",
        ),
        PROVED: (
            "{deed}. I watched you do that. I have been teaching long enough to "
            "know which ones were luck, and it was not.",
            "{proved} You changed a thing in the world and the world kept it. "
            "That is not a small category.",
            "{deed} is the one I mention to the ones who are about to give up. "
            "I do not tell them it was easy for you. It was not.",
            "You did {deed}, and then you carried on as though it were normal. "
            "It becomes normal. That is what this is.",
            "{deed}. Say that back to yourself sometimes. Not often. "
            "Sometimes.",
        ),
        WHERE: (
            "{thing} is in {place}, and {rate}. Knowing where a thing is, is "
            "not the same as having it, and it is not nothing either.",
            AWAY + "Go to {place} for {thing}. {rate}. I would rather you spent the "
            "evening walking than the evening wondering.",
            "{place}. {thing}. {rate}. There — now the not-knowing is over and "
            "only the work is left, which was always the better problem.",
            "Students stall here, always, and always for the same reason: "
            "nobody told them {thing} was in {place}, and that {rate}.",
            "Not knowing where {thing} is has stopped more people than the "
            "work ever has. {place}. {rate}.",
        ),
    },

    # ---------------------------------------------------------------------
    # STEWARD — keeps a castle nobody lives in, for a king who removed the
    # labels rather than the rooms.
    # ---------------------------------------------------------------------
    STEWARD: {
        AREA: (
            "{region}. I would offer you a description, but the descriptions "
            "were among the things removed. {weather}.",
            "The house has conditions rather than weather. In {region}, "
            "{weather}, and it has been so for longer than the staff.",
            "There is a ground to cross before the doors. {hazard}. Nobody has "
            "swept it in some years.",
            "Guests ask what {region} is like. {weather}. I have not found a "
            "kinder way to put it and I have had time.",
            "The house keeps a description of {region} from before. It is out "
            "of date in every particular but one: {weather}.",
        ),
        GEAR: (
            "If I may. {gear}. It is not my place to advise and it is very much "
            "my place to notice.",
            "The last several arrivals were given the same advice: {counter}. I am "
            "told none of them acted on it.",
            "The floors here are unkind to the wrong footwear. {boots}.",
            "I keep the register of who came in and who went out again. On the "
            "evidence of that register, {gear}.",
            "It is not my place. I shall do it anyway, the alternative being "
            "another guest shown politely to the door: {counter}.",
        ),
        AHEAD: (
            "{ahead} is expecting you, in the sense that it expects everyone. "
            "{demand}.",
            "{where_ahead} is through the far doors. {ahead} is beyond them. "
            "{demand}, and nothing in these halls will tell you so.",
            "The King removed the labels and not the rooms. So: {ahead}, and "
            "{demand}, said aloud, because no sign here will say it.",
            "I am permitted to announce guests. I am not permitted to prepare "
            "them. I am going to anyway: {demand}, before you meet {ahead}.",
            "The room {ahead} keeps has no plaque on its door. I will say the "
            "plaque aloud instead: {demand}.",
        ),
        PROVED: (
            "{deed}. Word reaches even here, eventually, and stale.",
            "{proved} I have written it in the house book. The house book has "
            "very few recent entries.",
            "You are the one who did {deed}. I find I have been looking forward "
            "to you, which is an unfamiliar condition.",
            "{deed}. The staff spoke about it for a week. There are four of us "
            "and it was still a week.",
            "{proved} The house noticed. The house notices very little now, "
            "so take that as it is meant.",
        ),
        WHERE: (
            "{thing} is held in {place}, and {rate}. The house has not had any "
            "in a long while.",
            "{place} supplies {thing}, and {rate}. We used to have it sent. We "
            "used to have a great many things sent.",
            "If you require {thing}, you require {place}, and {rate}. I am "
            "sorry it is not a shorter reply.",
            "There is one of everything in this house and none of it is "
            "{thing}. For that, {place}, and {rate}.",
            "{thing} would have come from {place} in the ordinary way, and "
            "{rate}. Nothing comes in the ordinary way now.",
        ),
    },
}


# ==========================================================================
# SECTION 7 — READING THE SITUATION
# ==========================================================================
#
# The composer is only as good as what it is allowed to notice. This section is
# the reader: one dataclass, one builder, and no writes to anything.
#
# It is deliberately TOLERANT. Every field has a defensible default, because
# this module is going to be called from a town screen with a half-built save
# during someone else's refactor, and a dialogue system that raises is a
# dialogue system that gets wrapped in a try block and then silently stops
# working.
#
# It is also deliberately DERIVED. Nothing here is a second copy of a fact that
# lives somewhere else: the element comes from elements.affinity_for, the strike
# comes from items.strike_element, the metal comes from forge.metal_for_region,
# the companion comes from pets.PETS, the boss comes from world.BOSSES.


@dataclass
class Ctx:
    """Everything a speaker is allowed to notice, resolved once."""

    # -- where ------------------------------------------------------------
    region: str = "python_village"
    region_name: str = "Python Village"
    element: str = elements.NEUTRAL
    hazard: str = ""

    # -- what you are carrying --------------------------------------------
    strike: str = elements.NEUTRAL
    matchup: str = "NEUTRAL"            # elements.matchup kind, strike vs area
    resist: float = 0.0                 # your resistance to the area's element
    points: int = 0                     # flat armour points
    boots: str = ""                     # elements.BOOTS id, "" for none known
    boots_ok: bool | None = None        # None means the area has no hazard

    # -- what is coming ---------------------------------------------------
    boss: str = ""                      # world.BOSSES id
    boss_name: str = ""
    boss_region: str = ""
    boss_skill: str = ""
    chapter: str = ""                   # curriculum.CHAPTERS id, the NEXT one
    chapter_title: str = ""
    chapter_skill: str = ""

    # -- what you have proved ---------------------------------------------
    done: tuple = ()                    # quest ids, in turn-in order
    recent: tuple = ()                  # the last few, which read as news

    # -- where things are --------------------------------------------------
    metal: str = ""                     # the metal this region gives up
    shortfall: str = ""                 # the metal the smith is waiting on
    blade: str = ""                     # the blade line that shortfall is for
    companion: str = ""                 # an undiscovered pet whose home is here
    stock: str = ""                     # a potion this area's tier can supply
    price: int = 0                      # what that costs here, 0 if unpriced
    relic: str = ""                     # a regalia piece found in this region
    tier: str = "EASY"                  # forge.typical_difficulty(region)
    gold: int = 0

    # -- the one capability check ------------------------------------------
    sealed: frozenset = frozenset()     # beats whose capability is sealed

    def open_beats(self) -> tuple:
        return tuple(b for b in BEATS if b not in self.sealed)


def _quest_done(state: dict) -> tuple:
    raw = (state or {}).get(quests.STATE_KEY) or {}
    return tuple(raw.get("done", []))


def _next_boss(region_id: str, cleared: set) -> dict:
    """The nearest boss this player has not beaten.

    In-region first, because a boss you can see from where you are standing is
    the one worth preparing for. Otherwise the first uncleared boss in world
    order, which is the game's own difficulty order.
    """
    here = [b for b in world.BOSSES
            if b["region"] == region_id and b["id"] not in cleared]
    if here:
        return here[0]
    for boss in world.BOSSES:
        if boss["id"] not in cleared:
            return boss
    return {}


def _next_chapter(state: dict):
    """The chapter the player is about to enter, not the one they are in.

    `curriculum.frontier` wants a skills mapping with a `.mastery` attribute;
    the save holds plain records. Rather than reimplement the ladder here this
    walks the same CHAPTERS list and takes the one after the deepest chapter
    whose skills have any evidence at all, which is a coarser answer to a
    coarser question — "what should this person read next" — and cannot
    disagree with the ladder about anything that matters.
    """
    skills_state = (state or {}).get("skills") or {}

    def mastery(skill: str) -> float:
        row = skills_state.get(skill)
        if isinstance(row, dict):
            return float(row.get("mastery", 0.0) or 0.0)
        return float(getattr(row, "mastery", 0.0) or 0.0)

    index = 0
    for i, chapter in enumerate(curriculum.CHAPTERS):
        if all(mastery(s) >= chapter.graduate_mastery for s in chapter.skills):
            index = i + 1
    index = min(index, len(curriculum.CHAPTERS) - 1)
    return curriculum.CHAPTERS[index]


def _undiscovered_here(region_id: str, found: set) -> str:
    """A companion whose home is this region and who is not yet with you.

    pets.Discovery.region is the authority. This never says HOW to find it —
    pets.py owns the discovery condition and says it in its own voice — it says
    that there is something here, which is the WHERE beat's whole job.
    """
    for pet in pets.PETS:
        if pet.discovery.region == region_id and pet.id not in found:
            return pet.id
    return ""


def _shortfall_metal(state: dict, gold: int) -> tuple:
    """The metal the smith is currently waiting on, and the blade it is for.

    Goes through forge.quote so the town and the smith's counter cannot
    disagree about what is missing. Lowest rung first, because the cheapest
    errand is the one a stuck player should be pointed at.
    """
    forge_state = (state or {}).get("forge") or {}
    best = ("", "")
    best_rung = 99
    for blade_id in forge.BLADE_BY_ID:
        if forge.owned_tier(forge_state, blade_id) < forge.MIN_TIER:
            continue
        q = forge.quote(forge_state, blade_id, gold=gold)
        if q.get("error") or q.get("at_top"):
            continue
        for metal_id in q.get("short") or {}:
            rung = forge.METAL_BY_ID[metal_id].rung
            if rung < best_rung:
                best_rung, best = rung, (metal_id, blade_id)
    return best


def _call(module, name: str, *args):
    """Call an optional neighbour's function, or return None.

    Everything about economy.py and regalia.py reaches this module through here:
    the name may not exist, the signature may move, and a dialogue system is not
    a good place to find that out. A missing answer is a subject this speaker
    does not raise, which is indistinguishable from tact.
    """
    fn = getattr(module, name, None)
    if not callable(fn):
        return None
    try:
        return fn(*args)
    except Exception:                           # pragma: no cover - defensive
        return None


def _stock_for(tier: str) -> str:
    """The best potion an area of this difficulty can actually supply.

    potions.available_at is the authority on the band. Taking the LAST id is
    taking the strongest the tier allows, which is what a shopkeeper would
    mention, and an unbanded area still returns the weakest rather than nothing.
    """
    ids = potions.available_at(tier)
    return ids[-1] if ids else (potions.POTION_IDS[0] if potions.POTION_IDS else "")


def context(state: dict | None = None, *, region_id: str = "",
            encounter=None, effects: dict | None = None,
            equipped: dict | None = None, companion: str = "",
            gold: int | None = None, recent: int = 3) -> Ctx:
    """Read the live situation once, for every speaker in the room.

    `state` is engine.Game.state, or anything shaped like it, or None.
    `effects` should be `engine.Game.effects()` when the caller has a Game,
    because that folds in a forged blade and an equipped artifact and this
    module cannot. Without it, items.total_effects is used, which is right for
    everything except those two.
    `companion` is the active pet id; it decides the strike element when the
    weapon has no element of its own, exactly as engine._player_element does.
    """
    state = state or {}
    player = state.get("player") or {}
    region = region_id or player.get("region") or "python_village"
    row = world.REGION_BY_ID.get(region, {})
    element = elements.affinity_for(region)
    hazard = elements.hazard_for(region)

    equipped = equipped if equipped is not None else (state.get("equipped") or {})
    if effects is None:
        try:
            effects = items.total_effects(equipped, state.get("attributes") or {})
        except Exception:                       # pragma: no cover - defensive
            effects = {}
    armour = elements.armour_from_effects(effects)

    if not companion:
        active = ((state.get("pets") or {}).get("active") or [])
        companion = active[0] if active else ""
    pet = pets.BY_ID.get(companion)
    strike = items.strike_element(
        equipped,
        fallback=elements.pet_element(getattr(pet, "species", ""), companion))

    boots_id = items.boots_id(equipped)
    boots_spec = elements.BOOTS_BY_ID.get(boots_id)
    boots_ok: bool | None = None
    if hazard is not None:
        boots_ok = bool(boots_spec and hazard.boots_tag in boots_spec.immunities)

    cleared = set(state.get("cleared_bosses") or [])
    boss = _next_boss(region, cleared)
    chapter = _next_chapter(state)

    done = _quest_done(state)
    gold_held = int(player.get("gold", 0) or 0) if gold is None else int(gold)
    shortfall, blade = _shortfall_metal(state, gold_held)
    metal = forge.metal_for_region(region)
    found = set((state.get("pets") or {}).get("found") or [])
    tier = forge.typical_difficulty(region)

    # economy.py and regalia.py were written in a parallel pass and may not be
    # here. Both are consulted through getattr and both degrade to the answer
    # this module could give on its own: the potion band from potions.py, and
    # no relic at all. Neither is allowed to raise into a conversation.
    stock = _stock_for(tier)
    price = 0
    if _economy is not None:
        shelf = _call(_economy, "stock_list", region) or ()
        if shelf:
            stock = shelf[-1]
        price = int(_call(_economy, "potion_price", stock, region) or 0)
    # THE TACK ROSTER IS quests.REGALIA, not regalia.py.
    # Both exist and their ids are disjoint: quests.REGALIA holds the seven
    # pieces that quest turn-ins actually pay and that economy.py prices and
    # shelves, while regalia.py carries a separate twenty-four-piece roster on a
    # different state key. A villager must only ever point at something the
    # player can really obtain, so this reads the roster the rest of the game
    # settles in. See the note at the end of quests.py: one roster, not two.
    held = set((state.get(quests.STATE_KEY) or {}).get("regalia") or ())
    relic = next((rid for rid, piece in quests.REGALIA.items()
                  if piece.get("region") == region and rid not in held), "")

    return Ctx(
        region=region, region_name=row.get("name", region),
        element=element, hazard=hazard.id if hazard else "",
        strike=strike, matchup=elements.matchup(strike, element)[1],
        resist=armour.resist_to(element), points=armour.points,
        boots=boots_id, boots_ok=boots_ok,
        boss=boss.get("id", ""), boss_name=boss.get("name", ""),
        boss_region=boss.get("region", ""), boss_skill=boss.get("skill", ""),
        chapter=chapter.id, chapter_title=chapter.title,
        chapter_skill=chapter.skills[0] if chapter.skills else "PYTHON",
        done=done, recent=done[-recent:] if recent else (),
        metal=metal.id if metal else "", shortfall=shortfall, blade=blade,
        companion=_undiscovered_here(region, found),
        stock=stock, price=price, relic=relic, tier=tier, gold=gold_held,
        sealed=frozenset(b for b in BEATS
                         if finalexam.sealed(encounter, BEAT_CAPABILITY[b])),
    )


# ==========================================================================
# SECTION 8 — THE COMPOSER
# ==========================================================================
#
# Scoring, then rotation, then filling. In that order, and the order matters:
# WHAT to say is a question about the player's situation, and only once it is
# answered does WHICH WORDS become a question about what this person has
# already said.

# Neutral ground still has to answer "what is underfoot", because AREA is the
# beat that guarantees nobody is ever speechless.
NO_HAZARD: tuple = (
    "there is nothing underfoot there that will argue with you",
    "the ground is only ground, which in this country counts as a feature",
    "nothing on that floor is trying anything. Enjoy it",
    "the floor there has no plans for you, which is rarer than it sounds",
    "you can put your weight anywhere on that ground and it will simply "
    "hold, and I would not take that for granted much further out",
)

# The WHERE beat's rate clause, for the two things that are not metal and
# therefore have no fights-per-bar.
COMPANION_RATE: tuple = (
    "there is no price on it and no shop that has one",
    "it is not a question of coin, it is a question of being the sort of "
    "person it will come out for",
    "nobody has ever bought one. Several people have deserved one",
)
RELIC_RATE: tuple = (
    "it is not guarded and it is not hidden. It is simply somewhere nobody has "
    "had a reason to look",
    "the animal it belongs to will know it on sight, which is the only "
    "authentication anybody has ever needed",
    "nothing in this region will stop you taking it. That is not the same as "
    "it being easy to find",
)
STOCK_RATE: tuple = (
    "that is inside what this tier can supply, which is more than can be said "
    "for the strong ones",
    "that is the best this end of the country stocks, and it is enough for "
    "the fights this end of the country has",
    "anything better than that has to be carried in from further up, and "
    "nothing is being carried anywhere at the moment",
)


# --------------------------------------------------------------------------
# Rotation
# --------------------------------------------------------------------------
#
# "Authored variants per beat, a rotation that does not repeat until it has to,
# and a memory of what this NPC last said to this player."
#
# One wheel per (speaker, pool). A pool is exhausted before any member of it
# comes round again, and exhausting it clears only that pool's marks — so a
# villager who has run out of ways to describe the marsh has not thereby
# forgotten which of their four smith-frames they used.
#
# The default pick is the lowest unused index rather than a random one, so a
# test can assert an exact sequence. Pass an rng to shuffle within the unused
# set, which is what a shipping client should do.

STATE_KEY = "banter"

# Marks per speaker before the oldest are dropped. Large enough that no speaker
# can exhaust every pool it owns within one, small enough that a save holding
# forty-seven speakers stays a few kilobytes.
MEMORY_CAP = 96


def new_state() -> dict:
    """Add under STATE_KEY to engine.DEFAULT_STATE. Bookkeeping, not evidence:
    a save that loses this loses variety for one session and nothing else."""
    return {"said": {}, "met": [], "turns": {}}


def _marks(state: dict | None, speaker_id: str) -> list:
    if state is None:
        return []
    return state.setdefault("said", {}).setdefault(speaker_id, [])


def _offset(salt: str, pool_key: str) -> int:
    """A stable starting position on one wheel, per speaker.

    Without this, every wheel starts at index zero, so the first time a player
    walks into a town every person in it opens with the same filling — five
    different voices delivering the identical observation about the ground. The
    offset is derived rather than stored, and it is crc32 rather than hash()
    because hash() of a string is salted per process and a save written on
    Tuesday would come back different on Wednesday.
    """
    return zlib.crc32(f"{salt}|{pool_key}".encode("utf-8"))


def _pick(pool, *, pool_key: str, marks: list, rng=None, salt: str = ""):
    """One member of `pool`, not repeated until the pool is spent.

    THE CYCLE NUMBER IS PART OF THE OFFSET, and that is the whole reason this
    module does not go stale. With a fixed offset every cycle traverses its pool
    in the same order, so a pool of five and another pool of five step together
    for ever and the pair of them behaves like a single pool of five. Frames are
    authored five deep, so any filling pool that reached five locked to them and
    a speaker's distinct-line count COLLAPSED as content was added — measured,
    not theorised: deepening the weather and hazard tables took the quietest
    speaker from 20 distinct remarks down to 10.
    Re-deriving the offset per cycle makes each pass through a pool a different
    permutation, so wheels of equal length drift against each other instead of
    locking, and the no-repeat-within-a-cycle guarantee is untouched.
    """
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
        # Rotate the UNUSED entries rather than indexing the whole pool, so the
        # no-repeat guarantee survives the offset: every member is still handed
        # out exactly once per cycle, just not in catalogue order.
        index = fresh[_offset(f"{salt}|{cycle}", pool_key) % len(fresh)]
    marks.append(f"{stamp}{index}")
    if len(marks) > MEMORY_CAP:
        # Trim the oldest PICKS but never a cycle counter: dropping one would
        # restart a pool's permutation and reintroduce the lockstep above.
        # Positional, not value-based — identical mark strings are common and
        # interning makes identity an unreliable way to tell two of them apart.
        pick_positions = [i for i, m in enumerate(marks) if "#" in m]
        drop = set(pick_positions[:max(0, len(pick_positions) - MEMORY_CAP)])
        marks[:] = [m for i, m in enumerate(marks) if i not in drop]
    return pool[index]


# --------------------------------------------------------------------------
# Slot builders — one per beat
# --------------------------------------------------------------------------
#
# Each returns `(slots, topic)` or None. None means "this speaker has nothing
# true to say on this beat right now", and the scorer drops it rather than
# inventing something.

def _region_name(region_id: str) -> str:
    return world.REGION_BY_ID.get(region_id, {}).get("name", region_id)


def _chapter_name(title: str) -> str:
    """"V. Scanning a Sequence" -> "Scanning a Sequence". The numeral belongs on
    a chapter select screen, not in somebody's mouth."""
    head, _, tail = title.partition(". ")
    return tail if tail and head.strip("IVXL") == "" else title


def _slots_area(ctx: Ctx, pick) -> tuple:
    weather = pick(WEATHER.get(ctx.element, WEATHER[elements.NEUTRAL]),
                   f"weather:{ctx.element}")
    hazard = (pick(HAZARD_TELL[ctx.hazard], f"hazard:{ctx.hazard}")
              if ctx.hazard in HAZARD_TELL else pick(NO_HAZARD, "hazard:none"))
    return ({"region": ctx.region_name, "weather": weather, "hazard": hazard},
            ctx.element if ctx.element != elements.NEUTRAL else "plain")


def _slots_gear(ctx: Ctx, pick) -> tuple:
    """The brief's 'what armour or weapon affinities to use', made concrete.

    Three facts, and every one of them is checkable by the player against the
    damage numbers: the matchup their weapon has with this ground, whether
    anything they are wearing resists it, and whether their boots answer the
    hazard. Nothing here touches the problem in front of them.
    """
    if ctx.element == elements.NEUTRAL:
        verdict = pick(MISMATCH["NEUTRAL"], "gear:plain")
    else:
        verdict = pick(MISMATCH.get(ctx.matchup, MISMATCH["NEUTRAL"]),
                       f"gear:{ctx.matchup}")
        if ctx.resist > 0:
            verdict += ", " + pick(WARDED, "ward:yes")
        elif ctx.points > 0:
            verdict += ", though " + pick(PLATED, "ward:plate")
        else:
            verdict += ", " + pick(UNWARDED, "ward:no")
    if ctx.boots_ok is None:
        boots = pick(BOOTS_IDLE, "boots:idle")
    elif ctx.boots_ok:
        boots = pick(BOOTS_OK, "boots:ok")
    elif ctx.boots:
        boots = pick(BOOTS_WRONG, "boots:wrong")
    else:
        boots = pick(BOOTS_NONE, "boots:none")
    counter = pick(COUNTER.get(ctx.element, COUNTER[elements.NEUTRAL]),
                   f"counter:{ctx.element}")
    return ({"gear": verdict, "counter": counter, "boots": boots},
            ctx.matchup)


def _slots_ahead(ctx: Ctx, pick) -> tuple | None:
    """Preparation, never answers. See THE ANSWER LINE at the top of the file.

    The subject rotates between the boss and the chapter, so a player standing
    in one place for a while is told about both rather than about one twice.
    """
    targets = []
    if ctx.boss and ctx.boss_skill in DEMAND:
        targets.append("boss")
    if ctx.chapter and ctx.chapter_skill in DEMAND:
        targets.append("chapter")
    if not targets:
        return None
    target = pick(targets, "ahead:target")
    if target == "boss":
        return ({"ahead": ctx.boss_name,
                 "demand": pick(DEMAND[ctx.boss_skill], f"demand:{ctx.boss_skill}"),
                 "where_ahead": _region_name(ctx.boss_region)},
                ctx.boss_skill)
    chapter = curriculum.CHAPTER_BY_ID.get(ctx.chapter)
    return ({"ahead": _chapter_name(ctx.chapter_title),
             "demand": pick(DEMAND[ctx.chapter_skill],
                            f"demand:{ctx.chapter_skill}"),
             "where_ahead": _region_name(getattr(chapter, "region", ""))},
            ctx.chapter_skill)


def _proved_pool(speaker_id: str, ctx: Ctx) -> tuple:
    """Quests this speaker is entitled to bring up.

    Theirs first, by name, forever — that is the brief's point 4. Failing that,
    anything finished in the region they stand in, because a village that
    noticed nothing you did for the village is not a village.
    """
    home = speaker(speaker_id).get("region", "")
    mine, local = [], []
    for qid in ctx.done:
        quest = quests.QUEST_BY_ID.get(qid)
        if quest is None:
            continue
        if quest.giver == speaker_id:
            mine.append(qid)
        elif quest.region == home:
            local.append(qid)
    # Theirs come first and the scorer pays a bonus when any of them are in the
    # pool, so a person's own trouble is what they lead with. The neighbours'
    # troubles ride along behind it because a village where only the quest giver
    # noticed you is not a village, and because a speaker with exactly one deed
    # to their name would otherwise have exactly one thing to say about it.
    return tuple(mine + local)


def _slots_proved(speaker_id: str, ctx: Ctx, pick) -> tuple | None:
    pool = _proved_pool(speaker_id, ctx)
    if not pool:
        return None
    qid = pick(pool, "proved:quest")
    quest = quests.QUEST_BY_ID[qid]
    return ({"deed": quest.title,
             "proved": quest.consequence.get("world", "")},
            quest.id)


def _metal_rate(metal_id: str) -> tuple:
    """Where it is and what it costs, straight out of forge.counsel so the town
    and the smith's counter cannot disagree about a number."""
    row = forge.counsel(metal_id)
    if not row:
        return "", ""
    best = (row.get("regions") or [{}])[0]
    fights = best.get("encounters_per_unit")
    where = best.get("name", "")
    if fights:
        return where, (f"about {fights} fights a bar at "
                       f"{str(best.get('typical_difficulty', '')).lower()}")
    return where, "the rate is whatever the ground feels like that day"


def _slots_where(ctx: Ctx, pick) -> tuple | None:
    """Which metal drops here, which companion hides nearby, what is in stock.

    The subjects are ranked by how stuck the player is — an outstanding forge
    order is the only thing in this game that reads as a wall — and then
    rotated, so a shopkeeper eventually mentions the shop.
    """
    subjects = []
    if ctx.shortfall:
        subjects.append("shortfall")
    if ctx.companion:
        subjects.append("companion")
    if ctx.metal:
        subjects.append("metal")
    if ctx.relic:
        subjects.append("relic")
    if ctx.stock:
        subjects.append("stock")
    if not subjects:
        return None
    subject = pick(subjects, "where:subject")

    if subject in ("shortfall", "metal"):
        metal_id = ctx.shortfall if subject == "shortfall" else ctx.metal
        metal = forge.METAL_BY_ID.get(metal_id)
        if metal is None:
            return None
        where, rate = _metal_rate(metal_id)
        place = where or ctx.region_name
        return ({"thing": metal.name, "place": place, "rate": rate,
                 "_local": place == ctx.region_name}, metal_id)
    if subject == "companion":
        pet = pets.BY_ID.get(ctx.companion)
        if pet is None:
            return None
        place = _region_name(pet.discovery.region)
        return ({"thing": f"{pet.name} the {pet.species}", "place": place,
                 "rate": pick(COMPANION_RATE, "rate:companion"),
                 "_local": place == ctx.region_name}, pet.id)
    if subject == "relic":
        piece = quests.REGALIA.get(ctx.relic)
        if piece is None:
            return None
        place = _region_name(piece.get("region", ""))
        return ({"thing": piece.get("name", ""), "place": place,
                 "rate": pick(RELIC_RATE, "rate:relic"),
                 "_local": place == ctx.region_name}, ctx.relic)
    brew = potions.BY_ID.get(ctx.stock)
    if brew is None:
        return None
    rate = pick(STOCK_RATE, "rate:stock")
    # The price is the shopkeeper's whole authority. When economy.py is there it
    # is the real number off the real shelf, and when it is not the sentence is
    # still true without it.
    if ctx.price:
        rate = f"{ctx.price} gold here, and {rate}"
    return ({"thing": brew.name, "place": ctx.region_name, "rate": rate,
             "_local": True}, brew.id)


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
#
# Salience, not randomness. A player wearing the wrong metal into a marsh should
# be told about the metal; a player who just finished this person's quest should
# be congratulated for it and then, on the next visit, told something useful.
#
# PROVED is the one that would otherwise go stale, because it is true forever
# once it is true at all. It is loud while it is news and quiet afterwards, and
# it never drops to zero, because the brief said forever after and meant it.

BASE_SCORE: dict = {AREA: 30, GEAR: 20, AHEAD: 25, PROVED: 0, WHERE: 22}

NEWS_BONUS = 34         # PROVED, while the deed is still one of the last few
MINE_BONUS = 30         # PROVED, when the speaker is the one who asked for it
STALE_FLOOR = 10        # PROVED, forever after
WRONG_METAL = 40        # GEAR, when the matchup is actively costing damage
UNRESISTED = 18         # GEAR, in an elemental area with no ward at all
WRONG_BOOTS = 20        # GEAR, when the hazard will land every few steps
LOCAL_BOSS = 20         # AHEAD, when the thing is in the room you are in
STUCK_ON_METAL = 26     # WHERE, when the smith is waiting on a bar
HIDDEN_HERE = 14        # WHERE, when there is an animal in this region
ELEMENTAL = 12          # AREA, when the ground has weather at all

# A tail only appears when it is worth appearing. Below this a speaker says one
# thing and stops, which is a real register in itself.
TAIL_FLOOR = 24

# Salience decides WHAT is worth saying; it should not decide it so precisely
# that two beats one point apart are ordered forever. Anything within this of
# the best candidate is treated as equally worth leading with, and the rotation
# chooses between them — so a villager standing in a fixed situation moves
# through several subjects rather than repeating the best one with new wording.
#
# The spread is small on purpose. A wrong-element warning scores forty above the
# baseline and will still win every time, which is the point of scoring at all.
LEAD_SPREAD = 8


def _score(beat: str, speaker_id: str, ctx: Ctx, has_slots: bool) -> int:
    if not has_slots:
        return -1
    score = BASE_SCORE[beat]
    if beat == AREA:
        if ctx.element != elements.NEUTRAL:
            score += ELEMENTAL
        if ctx.hazard:
            score += 6
    elif beat == GEAR:
        if ctx.element == elements.NEUTRAL:
            score -= 8
        else:
            if ctx.matchup in ("SAME", "WEAK_INTO"):
                score += WRONG_METAL
            elif ctx.matchup == "OPPOSED":
                score += 8
            if ctx.resist <= 0:
                score += UNRESISTED
        if ctx.boots_ok is False:
            score += WRONG_BOOTS
    elif beat == AHEAD:
        if ctx.boss and ctx.boss_region == ctx.region:
            score += LOCAL_BOSS
    elif beat == PROVED:
        pool = _proved_pool(speaker_id, ctx)
        if not pool:
            return -1
        mine = any(quests.QUEST_BY_ID[q].giver == speaker_id for q in pool)
        score += MINE_BONUS if mine else 0
        score += NEWS_BONUS if any(q in ctx.recent for q in pool) else STALE_FLOOR
    elif beat == WHERE:
        if ctx.shortfall:
            score += STUCK_ON_METAL
        if ctx.companion:
            score += HIDDEN_HERE
    return score + REGISTERS[register_of(speaker_id)].bias.get(beat, 0)


# --------------------------------------------------------------------------
# The composer itself
# --------------------------------------------------------------------------

def _build(beat: str, speaker_id: str, ctx: Ctx, pick):
    """One beat's slots, or None when this speaker has nothing true to say on it.

    Split out of `_candidates` so the same builder can be run twice: once on a
    scratch memory to answer "could you say this", and once on the real memory
    for the beat actually spoken. See `_candidates`.
    """
    if beat == AREA:
        return _slots_area(ctx, pick)
    if beat == GEAR:
        return _slots_gear(ctx, pick)
    if beat == AHEAD:
        return _slots_ahead(ctx, pick)
    if beat == PROVED:
        return _slots_proved(speaker_id, ctx, pick)
    return _slots_where(ctx, pick)


def _candidates(speaker_id: str, ctx: Ctx, pick) -> list:
    """Every beat this speaker could truthfully open with, scored.

    Slots are built BEFORE scoring rather than after, because "can this person
    say anything true on this beat" is part of the score and the only honest way
    to answer it is to try.

    THE PICK PASSED IN HERE MUST BE A SCRATCH ONE. Scoring tries all five beats
    and speaks at most two, so a pick committed here would spend a filling on a
    beat nobody heard. That is not merely wasteful: it advanced EVERY wheel by
    exactly one every turn, which held pools of the same size permanently in
    phase with each other. With the weather, the matchup, the ward and the
    counter wheels all three long and all three stepping together, a speaker's
    whole vocabulary cycled as a single unit of three and the same sentence came
    back on a nine-turn beat. `speak` probes on a copy and re-runs `_build` on
    the real memory for the one or two beats it actually says.
    """
    out = []
    for beat in ctx.open_beats():
        built = _build(beat, speaker_id, ctx, pick)
        score = _score(beat, speaker_id, ctx, built is not None)
        if built is None or score < 0:
            continue
        slots, topic = built
        out.append({"beat": beat, "score": score, "slots": slots, "topic": topic})
    out.sort(key=lambda c: (-c["score"], BEATS.index(c["beat"])))
    return out


_SENTENCE_START = re.compile(r"(^|[.?] )([a-z])")


def _sentence_case(text: str) -> str:
    """Capitalise whatever landed at the start of a sentence.

    The prose fillings are authored lower-case, because most of them arrive
    mid-sentence and a frame cannot know which. Doing it here rather than
    forbidding frames from opening with a slot is the difference between two
    hundred frames written under a constraint and two hundred frames written
    the way a person would say them. Nothing else in a composed line is ever
    lower-case at a sentence start, so this is safe to apply to the whole line.
    """
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def _render(speaker_id: str, beat: str, slots: dict, pick) -> str:
    register = register_of(speaker_id)
    # `_local` is set by `_slots_where` only, and decides whether the travel
    # frames or the underfoot frames are true of this place. See HERE/AWAY.
    local = slots.get("_local") if beat == WHERE else None
    pool = _frames_for(register, beat, local=local)
    # The two localities are separate wheels, because they are separate pools
    # and a shared cursor into pools of different length would skip entries.
    # Every other beat keeps its original key.
    key = f"frame:{register}:{beat}"
    if local is not None:
        key += ":here" if local else ":away"
    frame = pick(pool, key)
    filled = dict.fromkeys(BEAT_SLOTS[beat], "")
    filled.update({k: v for k, v in slots.items() if k in BEAT_SLOTS[beat]})
    for marker in _MARKERS:
        frame = frame.replace(marker, "")
    return _sentence_case(frame.format(**filled).strip())


def _choose(options: list, floor: int, role: str, pick):
    """One of the candidates at or above `floor`, rotated.

    The wheel is keyed on WHICH beats were eligible, not just on the role, so a
    speaker whose eligible set changes — a quest finishes, a shortfall clears —
    starts a fresh rotation rather than inheriting a position from a set that no
    longer exists. Without that, an index into a three-beat field survives into
    a two-beat one and the wheel quietly favours whatever is left.
    """
    field = [o for o in options if o["score"] >= floor]
    if not field:
        return None
    if len(field) == 1:
        return field[0]
    beats = [o["beat"] for o in field]
    chosen = pick(beats, f"{role}:" + "+".join(sorted(beats)))
    return next(o for o in field if o["beat"] == chosen)


def refusal() -> dict:
    """The standard refusal, so this module's 'no' reads exactly like every
    other 'no' in the game. Reached when every beat's capability is sealed,
    which is Timed Practical Mode and hold-out content and nothing else."""
    return finalexam.refuse(BEAT_CAPABILITY[AREA])


def speak(speaker_id: str, ctx: Ctx | None = None, *, state: dict | None = None,
          rng=None, tail: bool = True) -> dict:
    """What this person says NOW.

    The one entry point. `ctx` comes from `context()`; pass the same Ctx to every
    speaker in a room so the town agrees with itself about the weather.

    `state` is the BANTER sub-state — `engine.state[banter.STATE_KEY]` — and is
    the only thing this function writes to. Pass None for a stateless preview
    and the rotation falls back to first-unused, which is deterministic.
    """
    who = speaker(speaker_id)
    if not who:
        return {"error": "no such speaker", "speaker": speaker_id}
    ctx = ctx if ctx is not None else context()
    if not ctx.open_beats():
        return {**who, "lines": [], "beats": [], "sealed": True, **refusal()}

    marks = _marks(state, speaker_id)

    def pick_into(target):
        def pick(pool, pool_key):
            return _pick(pool, pool_key=pool_key, marks=target, rng=rng,
                         salt=speaker_id)
        return pick

    # Probe on a COPY. Scoring has to try all five beats to find out which ones
    # this person can speak to truthfully, and a filling spent on a beat that is
    # then not spoken is a filling nobody heard — see `_candidates`.
    probe = pick_into(list(marks))
    pick = pick_into(marks)

    options = _candidates(speaker_id, ctx, probe)
    if not options:                            # pragma: no cover - AREA is total
        return {**who, "lines": [], "beats": [], "sealed": False}

    lead = _choose(options, options[0]["score"] - LEAD_SPREAD, "lead", pick)
    chosen = [lead]
    if tail:
        rest = [o for o in options if o["beat"] != lead["beat"]]
        second = _choose(rest, TAIL_FLOOR, "tail", pick)
        if second is not None:
            chosen.append(second)

    # Now spend the real memory, and only on what is about to be said.
    lines, beats, topics = [], [], []
    for option in chosen:
        built = _build(option["beat"], speaker_id, ctx, pick)
        slots, topic = built if built is not None else (option["slots"],
                                                        option["topic"])
        lines.append(_render(speaker_id, option["beat"], slots, pick))
        beats.append(option["beat"])
        topics.append(topic)

    if state is not None:
        turns = state.setdefault("turns", {})
        turns[speaker_id] = int(turns.get(speaker_id, 0)) + 1
        met = state.setdefault("met", [])
        if speaker_id not in met:
            met.append(speaker_id)

    return {**who, "lines": lines, "beats": beats, "topics": topics,
            "region": ctx.region, "sealed": False,
            "scores": {o["beat"]: o["score"] for o in options}}


def room(speaker_ids, ctx: Ctx | None = None, *, state: dict | None = None,
         rng=None) -> list:
    """Everyone in one place, asked once, against one reading of the situation."""
    ctx = ctx if ctx is not None else context()
    return [speak(sid, ctx, state=state, rng=rng) for sid in speaker_ids]


def speakers_in(region_id: str) -> list:
    """Who is standing here. NPCs by their own region, the smith by hers, and
    the mentor the region declares."""
    out = [sid for sid, npc in quests.NPCS.items() if npc["region"] == region_id]
    if forge.SMITH.get("region") == region_id:
        out.append(SMITH_ID)
    mentor = world.REGION_BY_ID.get(region_id, {}).get("mentor", "")
    if mentor in world.MENTORS:
        out.append(mentor)
    return out


# ==========================================================================
# SECTION 9 — THE IDENTITY LINE
# ==========================================================================
#
# quests.npc_line already owns the ONE sentence that says who a person is, and
# quests.complete permanently overwrites it when their trouble is fixed. That
# is a good mechanic and this module does not replace it: the identity line is
# what they say when you walk up, and `speak` is what they say when you keep
# talking. A caller that renders both gets a person; a caller that renders only
# the second gets an oracle with a hat on.

def identity_line(speaker_id: str, state: dict | None = None) -> str:
    """Their fixed line — the quest-overwritten one where there is one."""
    if speaker_id in quests.NPCS or speaker_id in world.MENTORS:
        return quests.npc_line(speaker_id, state or {})
    if speaker_id == SMITH_ID:
        return forge.SMITH["greeting"]
    return ""


# ==========================================================================
# SECTION 10 — COUNTS, CAPACITY AND PROOF
# ==========================================================================


def _slots_in(frame: str) -> set:
    return set(re.findall(r"\{(\w+)\}", frame))


def capacity(speaker_id: str, ctx: Ctx | None = None, *,
             limit: int = 800) -> dict:
    """How many distinct things this person can say before repeating.

    Measured rather than estimated. The composer is run against a fixed reading
    of the situation with a throwaway memory until a remark comes round again,
    which is the literal question the brief asked.

    The number is a FLOOR on what a player experiences, not a ceiling: it holds
    the situation still, and in a real game the region, the loadout, the boss
    ahead and the quest log all move underneath the same frames.
    """
    ctx = ctx if ctx is not None else context(region_id=speaker(speaker_id)
                                              .get("region", ""))
    memory = new_state()
    seen: dict = {}
    first_repeat = 0
    beats: dict = {}
    for turn in range(1, limit + 1):
        said = speak(speaker_id, ctx, state=memory)
        key = " ".join(said.get("lines", ()))
        for beat in said.get("beats", ()):
            beats[beat] = beats.get(beat, 0) + 1
        if key in seen and not first_repeat:
            # `distinct` stops here — that is the brief's question, asked
            # literally — but the walk carries on, because how much a player
            # sees over a long acquaintance is the more interesting number and
            # the two are not the same when several wheels interleave.
            first_repeat = turn
        seen.setdefault(key, turn)
    return {"speaker": speaker_id, "register": register_of(speaker_id),
            "distinct": (first_repeat - 1) if first_repeat else len(seen),
            "first_repeat_at": first_repeat,
            "distinct_in_full_walk": len(seen), "walk": limit,
            "beats_used": beats, "limit_hit": first_repeat == 0}


def counts() -> dict:
    """Content census. Cheap enough to print in a test failure message."""
    frames = sum(len(pool) for beats in FRAMES.values()
                 for pool in beats.values())
    fillings = (sum(len(v) for v in WEATHER.values())
                + sum(len(v) for v in COUNTER.values())
                + sum(len(v) for v in MISMATCH.values())
                + sum(len(v) for v in HAZARD_TELL.values())
                + sum(len(v) for v in DEMAND.values())
                + len(UNWARDED) + len(WARDED) + len(PLATED) + len(UNPLATED)
                + len(BOOTS_OK) + len(BOOTS_WRONG) + len(BOOTS_NONE)
                + len(BOOTS_IDLE) + len(NO_HAZARD)
                + len(COMPANION_RATE) + len(STOCK_RATE))
    by_register = {rid: sum(len(p) for p in beats.values())
                   for rid, beats in FRAMES.items()}
    return {
        "speakers": len(SPEAKERS),
        "npcs": len(quests.NPCS),
        "mentors": len(world.MENTORS),
        "registers": len(REGISTERS),
        "beats": len(BEATS),
        "frames": frames,
        "frames_per_register": by_register,
        "fillings": fillings,
        "demand_skills": len(DEMAND),
        "elements_covered": len(WEATHER),
        "hazards_covered": len(HAZARD_TELL),
        "regions": len(world.REGIONS),
    }


def _authored_text():
    """Every player-visible string this module owns, labelled for the report."""
    for name, table in (("weather", WEATHER), ("counter", COUNTER),
                        ("mismatch", MISMATCH), ("hazard", HAZARD_TELL),
                        ("demand", DEMAND)):
        for key, pool in table.items():
            for line in pool:
                yield f"{name}:{key}", line
    for name, pool in (("unwarded", UNWARDED), ("warded", WARDED),
                       ("plated", PLATED), ("unplated", UNPLATED),
                       ("boots_ok", BOOTS_OK), ("boots_wrong", BOOTS_WRONG),
                       ("boots_none", BOOTS_NONE), ("boots_idle", BOOTS_IDLE),
                       ("no_hazard", NO_HAZARD),
                       ("companion_rate", COMPANION_RATE),
                       ("stock_rate", STOCK_RATE)):
        for line in pool:
            yield name, line
    for rid, beats in FRAMES.items():
        for beat, pool in beats.items():
            for line in pool:
                yield f"frame:{rid}:{beat}", line
    for rid, reg in REGISTERS.items():
        yield f"register:{rid}", reg.label
        yield f"register:{rid}", reg.voice
        yield f"register:{rid}", reg.measure


def _saturated_context(region_id: str) -> Ctx:
    """A reading of the situation with every beat live at once.

    Used only by the audit. It is deliberately impossible — no real player is
    simultaneously two metals short, standing on an undiscovered animal and
    holding a finished quest for whoever they are talking to — because the
    audit's job is to reach every slot of every frame, not to be plausible.
    """
    element = elements.affinity_for(region_id)
    hazard = elements.hazard_for(region_id)
    metal = forge.metal_for_region(region_id)
    here = [p for p in pets.PETS if p.discovery.region == region_id]
    boss = next((b for b in world.BOSSES if b["region"] == region_id),
                world.BOSSES[0])
    done = tuple(q.id for q in quests.QUESTS if q.region == region_id)
    return Ctx(
        region=region_id, region_name=_region_name(region_id),
        element=element, hazard=hazard.id if hazard else "",
        strike=elements.OPPOSED.get(element, elements.NEUTRAL),
        matchup="OPPOSED" if element != elements.NEUTRAL else "NEUTRAL",
        resist=0.0, points=0, boots="", boots_ok=False if hazard else None,
        boss=boss["id"], boss_name=boss["name"], boss_region=boss["region"],
        boss_skill=boss["skill"],
        chapter=curriculum.CHAPTERS[0].id,
        chapter_title=curriculum.CHAPTERS[0].title,
        chapter_skill=curriculum.CHAPTERS[0].skills[0],
        done=done, recent=done[-3:],
        metal=metal.id if metal else "",
        shortfall=metal.id if metal else "fieldiron",
        blade=forge.BLADES[0].id,
        companion=here[0].id if here else "",
        stock=potions.POTION_IDS[0], price=12,
        relic=next((rid for rid, piece in quests.REGALIA.items()
                    if piece.get("region") == region_id), ""),
        tier=forge.typical_difficulty(region_id),
    )


def audit() -> dict:
    """The proof. Everything a reviewer would otherwise have to take on trust.

    1. THE ANSWER LINE, over authored text AND over every line the composer can
       actually emit, because a frame can only leak a construct through a slot.
    2. Slot discipline: no frame reaches for a slot its beat does not define,
       and no prose slot opens a sentence.
    3. Referential integrity: every id this module names exists in the module
       that owns it.
    4. Coverage: every speaker has a register, every register has every beat,
       every element and hazard and skill has vocabulary.
    5. No dead ends: every speaker, in every region, says something.
    """
    problems: dict = {
        "answerish": [], "slots": [], "unknown_ids": [], "coverage": [],
        "dead_ends": [], "tone": [],
    }

    # -- 1a. authored text --------------------------------------------------
    for label, line in _authored_text():
        for token in names_a_construct(line):
            problems["answerish"].append(f"{label}: {token!r}")
        if "!" in (line or ""):
            problems["tone"].append(f"{label}: exclamation mark")

    # -- 2. slot discipline -------------------------------------------------
    for rid, beats in FRAMES.items():
        for beat, pool in beats.items():
            allowed = set(BEAT_SLOTS[beat])
            for frame in pool:
                used = _slots_in(frame)
                stray = used - allowed
                if stray:
                    problems["slots"].append(
                        f"frame:{rid}:{beat}: unknown slot(s) {sorted(stray)}")
                if not used:
                    problems["slots"].append(
                        f"frame:{rid}:{beat}: frame reads no state at all")

    # -- 3. referential integrity -------------------------------------------
    for skill in DEMAND:
        if skill not in skills_mod.SKILLS:
            problems["unknown_ids"].append(f"DEMAND: unknown skill {skill!r}")
    for element in WEATHER:
        if element not in elements.ALL_AFFINITIES:
            problems["unknown_ids"].append(f"WEATHER: unknown element {element!r}")
    for element in COUNTER:
        if element not in elements.ALL_AFFINITIES:
            problems["unknown_ids"].append(f"COUNTER: unknown element {element!r}")
    for hazard in HAZARD_TELL:
        if hazard not in elements.HAZARDS:
            problems["unknown_ids"].append(f"HAZARD_TELL: unknown {hazard!r}")
    for kind in MISMATCH:
        if kind not in elements.MATCHUP_MULT:
            problems["unknown_ids"].append(f"MISMATCH: unknown kind {kind!r}")
    for npc_id in NPC_REGISTER:
        if npc_id not in quests.NPCS:
            problems["unknown_ids"].append(f"NPC_REGISTER: unknown npc {npc_id!r}")
    for mentor_id, skill in MENTOR_SUBJECT.items():
        if mentor_id not in world.MENTORS:
            problems["unknown_ids"].append(f"MENTOR_SUBJECT: unknown {mentor_id!r}")
        if skill not in skills_mod.SKILLS:
            problems["unknown_ids"].append(
                f"MENTOR_SUBJECT[{mentor_id}]: unknown skill {skill!r}")
    for register_id in set(NPC_REGISTER.values()):
        if register_id not in REGISTERS:
            problems["unknown_ids"].append(f"unknown register {register_id!r}")

    # -- 4. coverage --------------------------------------------------------
    for npc_id in quests.NPCS:
        if npc_id not in NPC_REGISTER:
            problems["coverage"].append(f"npc {npc_id!r} has no register")
    for mentor_id in world.MENTORS:
        if mentor_id not in MENTOR_SUBJECT:
            problems["coverage"].append(f"mentor {mentor_id!r} has no subject")
    for rid in REGISTERS:
        if rid not in FRAMES:
            problems["coverage"].append(f"register {rid!r} has no frames")
            continue
        for beat in BEATS:
            pool = FRAMES[rid].get(beat, ())
            if len(pool) < 3:
                problems["coverage"].append(
                    f"register {rid!r} beat {beat} has only {len(pool)} frames")
    for skill in skills_mod.SKILLS:
        if skill not in DEMAND:
            problems["coverage"].append(f"skill {skill!r} has no DEMAND text")
    for element in elements.ALL_AFFINITIES:
        if element not in WEATHER or element not in COUNTER:
            problems["coverage"].append(f"element {element!r} has no vocabulary")
    for hazard_id in elements.HAZARDS:
        if hazard_id not in HAZARD_TELL:
            problems["coverage"].append(f"hazard {hazard_id!r} has no vocabulary")
    for boss in world.BOSSES:
        if boss["skill"] not in DEMAND:
            problems["coverage"].append(
                f"boss {boss['id']!r} demands {boss['skill']!r}, which has no text")
    for chapter in curriculum.CHAPTERS:
        for skill in chapter.skills:
            if skill not in DEMAND:
                problems["coverage"].append(
                    f"chapter {chapter.id!r} tests {skill!r}, which has no text")

    # -- 1b + 5. every speaker, every region, saturated ---------------------
    emitted = 0
    for region in world.REGIONS:
        ctx = _saturated_context(region["id"])
        for speaker_id in SPEAKERS:
            memory = new_state()
            # Enough turns to walk every frame of every beat at least once.
            for _ in range(len(BEATS) * 8):
                said = speak(speaker_id, ctx, state=memory)
                lines = said.get("lines", ())
                if not lines:
                    problems["dead_ends"].append(
                        f"{speaker_id} in {region['id']} said nothing")
                    break
                for line in lines:
                    emitted += 1
                    if "{" in line or "}" in line:
                        problems["slots"].append(
                            f"{speaker_id}/{region['id']}: unfilled slot in "
                            f"{line[:60]!r}")
                    if "!" in line:
                        problems["tone"].append(
                            f"{speaker_id}/{region['id']}: exclamation mark")
                    if _SENTENCE_START.search(line):
                        problems["slots"].append(
                            f"{speaker_id}/{region['id']}: sentence opens "
                            f"lower-case in {line[:60]!r}")
                    # strict=False: half of what is in a composed line was
                    # written by quests.py and world.py, and their English is
                    # not this module's to police. Everything that can ONLY be
                    # code is still checked, which is the part that matters.
                    for token in names_a_construct(line, strict=False):
                        problems["answerish"].append(
                            f"composed {speaker_id}/{region['id']}: {token!r}")
    problems = {k: sorted(dict.fromkeys(v))[:20] for k, v in problems.items()}
    problems["lines_audited"] = emitted
    return problems


def self_check() -> dict:
    """Counts, coverage, capacity and the proofs. Safe from a test or the CLI."""
    report = audit()
    census = counts()

    caps = []
    for speaker_id in SPEAKERS:
        home = speaker(speaker_id).get("region", "") or "python_village"
        caps.append(capacity(speaker_id, _saturated_context(home)))
    numbers = sorted(c["distinct"] for c in caps)
    quietest = min(caps, key=lambda c: c["distinct"])

    # A measured run must produce nothing. One check, and it is the only
    # capability question this module asks.
    class _Exam:
        mode = finalexam.EXAM_MODE
        boss_id = ""
        holdout = False

    sealed_ctx = context(encounter=_Exam())
    sealed_out = speak(SPEAKERS[0], sealed_ctx)

    return {
        "counts": census,
        "capacity": {
            "min": numbers[0], "median": numbers[len(numbers) // 2],
            "max": numbers[-1],
            "total_distinct_remarks": sum(numbers),
            "quietest_speaker": quietest["speaker"],
            "walk": caps[0]["walk"],
            "walk_min": min(c["distinct_in_full_walk"] for c in caps),
            "walk_median": sorted(c["distinct_in_full_walk"]
                                  for c in caps)[len(caps) // 2],
            "walk_max": max(c["distinct_in_full_walk"] for c in caps),
        },
        "sealed_in_exam": bool(sealed_out.get("sealed")),
        "sealed_beats": sorted(sealed_ctx.sealed),
        "problems": {k: v for k, v in report.items()
                     if k != "lines_audited" and v},
        "lines_audited": report["lines_audited"],
        "ok": not any(v for k, v in report.items() if k != "lines_audited")
        and bool(sealed_out.get("sealed")),
    }


def report() -> str:
    """One page, for a test failure or a terminal."""
    check = self_check()
    census = check["counts"]
    out = [
        f"banter: {census['speakers']} speakers, {census['registers']} registers, "
        f"{census['beats']} beats",
        f"  {census['frames']} authored frames, {census['fillings']} fillings",
        f"  distinct remarks before any repeat: min {check['capacity']['min']}, "
        f"median {check['capacity']['median']}, max {check['capacity']['max']}",
        f"  distinct remarks over {check['capacity']['walk']} turns of one "
        f"frozen situation: min {check['capacity']['walk_min']}, "
        f"median {check['capacity']['walk_median']}, "
        f"max {check['capacity']['walk_max']}",
        f"  {check['lines_audited']} composed lines audited against the answer line",
        f"  sealed in a measured run: {check['sealed_in_exam']}",
    ]
    for key, rows in check["problems"].items():
        out.append(f"  PROBLEM {key}: {len(rows)}")
        out += [f"    {row}" for row in rows[:5]]
    return "\n".join(out)




# ==========================================================================
# SECTION 11 — THE VIEW, AND THE CONTRACT
# ==========================================================================


def view(state: dict | None = None, *, region_id: str = "", encounter=None,
         effects: dict | None = None, rng=None) -> dict:
    """Everything a town screen draws, in one call.

    The identity line and the composed remark are BOTH returned, because they
    are different things: the first is who this person is, the second is what
    they have noticed about you. A client that renders only the second has
    built an advice kiosk.
    """
    ctx = context(state, region_id=region_id, encounter=encounter,
                  effects=effects)
    memory = (state or {}).setdefault(STATE_KEY, new_state()) \
        if state is not None else None
    rows = []
    for speaker_id in speakers_in(ctx.region):
        said = speak(speaker_id, ctx, state=memory, rng=rng)
        said["identity"] = identity_line(speaker_id, state or {})
        rows.append(said)
    return {
        "region": ctx.region, "region_name": ctx.region_name,
        "element": ctx.element, "hazard": ctx.hazard,
        "sealed": not ctx.open_beats(),
        "beats_open": list(ctx.open_beats()),
        "speakers": rows,
    }


def codex() -> list:
    """The ten voices, for a settings screen or a design review."""
    return [{"id": r.id, "label": r.label, "voice": r.voice,
             "measure": r.measure, "bias": dict(r.bias),
             "speakers": sorted(sid for sid in SPEAKERS
                                if register_of(sid) == r.id)}
            for r in REGISTERS.values()]


WIRING = """
WIRING gauntlet/banter.py — the integration contract. Nothing here is optional
and nothing here is a guess.

1. SAVE STATE
   engine.DEFAULT_STATE gains one key:

       banter.STATE_KEY: banter.new_state()      # -> "banter"

   It holds {"said": {speaker: [marks]}, "met": [...], "turns": {...}}. It is
   plain JSON, it round-trips through db.save_state untouched, and it is
   BOOKKEEPING, NOT EVIDENCE: a save that loses it loses variety for one
   session. engine._merge forward-fills it for existing saves; nothing else in
   this module needs migrating.

2. THE ONE CALL
       payload = banter.view(self.state, effects=self.effects(),
                             encounter=self.encounter)

   `view` reads the region off state["player"]["region"], asks every speaker
   standing there, writes the rotation marks back into state["banter"], and
   returns {region, region_name, element, hazard, sealed, beats_open,
   speakers: [...]}.

   Pass `effects=self.effects()`. Without it this module falls back to
   items.total_effects, which is correct for equipment and ATTRIBUTES but blind
   to a forged blade and an equipped artifact — both of which carry
   resist_<element> and armour_points, which is exactly what the GEAR beat
   reads. The advice would be quietly wrong for the two best loadouts in the
   game.

3. ONE SPEAKER AT A TIME
       ctx  = banter.context(self.state, effects=self.effects(),
                             encounter=self.encounter)
       said = banter.speak(npc_id, ctx, state=self.state[banter.STATE_KEY])

   Build the Ctx ONCE per screen and hand the same one to every speaker, or the
   town will disagree with itself about the weather. `speak` returns:

       {id, name, role, sprite, region, register, kind,
        lines: [str, ...],        # one or two, already sentence-cased
        beats: ["GEAR", "AREA"],  # which questions were answered
        topics: [...],            # the element / skill / quest id / metal id
        scores: {beat: int},      # diagnostics; safe to ignore
        sealed: False}

   `lines` is the whole of the player-facing output. It is plain text, it never
   contains markup, and it is never empty outside a measured run.

4. THE IDENTITY LINE STAYS WHERE IT IS
   quests.npc_line is still the authority on the ONE sentence that says who a
   person is, and quests.complete still overwrites it permanently when their
   trouble is fixed. Render it first, then the composed lines. banter.view
   already returns it as `identity`; banter.identity_line(npc_id, state) is the
   same thing for a caller that wants only that.

5. THE SEAL
   There is one capability check and it is finalexam.sealed. Each beat declares
   its crutch in banter.BEAT_CAPABILITY (AREA and GEAR -> WEAKNESS_MAP,
   AHEAD -> PATTERN, PROVED -> MENTOR, WHERE -> BUILD). Pass the live encounter
   into `context`; beats whose crutch is sealed are dropped, and when all five
   are gone `speak` returns finalexam.refuse's standard {"error": "sealed"}
   payload with `sealed: True` and no lines. Timed Practical Mode and hold-out
   content therefore produce nothing, which is the rule.

6. WHO CAN SPEAK
   banter.SPEAKERS is all forty-seven: the thirty-four in quests.NPCS, the smith
   in forge.SMITH, and the twelve in world.MENTORS. banter.speakers_in(region)
   is who is standing in one place. Any id outside that set returns
   {"error": "no such speaker"} rather than raising.

7. SERVER ROUTE
   One GET is enough, and it is a read plus a small write:

       GET /api/town        -> banter.view(game.state, effects=game.effects(),
                                           encounter=game.encounter)

   Save afterwards, because `view` advances the rotation. If the client wants a
   second remark from the same person on the same screen, call `speak` again
   with the same Ctx — that is what the rotation is for.

8. WHAT THIS MODULE WILL NEVER DO
   It will not name a Python construct. banter.names_a_construct(text) is the
   guard, banter.audit() runs it over every authored string and over every line
   the composer can emit from every region, and banter.self_check()["ok"] is the
   one boolean a test should assert. Any caller that concatenates onto a banter
   line should run it through the same guard.

9. OPTIONAL NEIGHBOURS
   economy.py and regalia.py are imported if present and reached only through
   banter._call, which returns None for a missing name or a raised exception.
   When they are there:
     * economy.stock_list(region) sets what the shopkeeper actually has, and
       economy.potion_price(id, region) puts the real gold figure in the line.
     * regalia.REGALIA supplies a fifth WHERE subject — the piece lying in this
       region that nobody has picked up — skipping anything already in
       state["regalia"]["found"].
   When they are not, the band from potions.available_at is used and the relic
   subject simply never comes up. No frame changes either way.
"""


if __name__ == "__main__":            # pragma: no cover
    print(report())
