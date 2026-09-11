"""Companions: nine animals that are found, never bought, and never obedient.

A pet's intervention IS a hint. That single sentence decides everything else in
this module, because the game already has rules about hints and a companion is
not allowed a private exemption from them:

  * it costs rank — an intervention counts as one hint against `hints_used`, and
    the stronger kinds clamp the ceiling further (see HINT_KINDS);
  * it does not exist in Interview Mode — `available_in()` is the gate, and it is
    the caller's job to ask before constructing anything a player can see;
  * it never states an answer. Every line in this file is authored against a
    REDACTED view of the encounter — pattern, weakness class, failure category —
    and none of it has ever seen the problem's tests or its canonical solution.

What a pet adds on top of the hint tree is TIMING. Spells are bought on demand at
the moment the player decides to give up. A pet watches measured signals and
speaks at the moment of struggle instead — which is both the better story and the
better pedagogy, since help that arrives before the struggle teaches nothing.

Integration contract, so another module can wire this up without reading the
implementation:

    pets.available_in(mode, region_id)          -> may a pet speak at all
    pets.intervention(pet_id, bond=, signals=, context=)
                                                -> dict | None, the whole event
    pets.bond_gain(pet_id, skill=, rank=, ...)  -> int, added to the pet's bond
    pets.passive_effects(pet_id, bond)          -> dict of items.EFFECT_LABELS keys
    pets.discovery_progress(pet_id, evidence)   -> progress rows + `met`
    pets.self_check()                           -> the proofs this file must pass

State the caller persists per pet is tiny and flat: see `new_state()`.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

from . import items

# How many companions may be in the field at once. Two, because at three you have
# a companion for every kind of trouble and choosing who to bring stops being a
# choice at all.
ACTIVE_LIMIT = 2

# An intervention counts as exactly one hint. It is not cheaper than a spell
# because it was unasked for; it is simply better timed.
HINT_WEIGHT = 1

# Two regions say in their own description that nothing helps you there. Pets
# honour that rather than quietly making the Coliseum easier than it advertises.
SILENCED_REGIONS = ("coding_coliseum", "null_kings_castle")


# --------------------------------------------------------------------------
# What kind of help a pet is allowed to be
# --------------------------------------------------------------------------
#
# `rank_ceiling` is the best rank still reachable after this kind of help. It
# mirrors the hint tree's own ladder: naming the family or handing over syntax is
# worth roughly an Oracle or a Reveal Path, so it lands where those land. Nothing
# here reaches Pseudosight, and nothing here can ever be a Phoenix.

HINT_KINDS = {
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
# button, and a button would be bought back into the spell list where it belongs.
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
}


@dataclass(frozen=True)
class Discovery:
    region: str
    where: str                # the place, in prose, for the codex
    how: str                  # the deed, in prose, for the player
    needs: tuple = ()         # the same deed, as data, for the evaluator
    first_words: str = ""     # what it says the moment it decides to stay


# --------------------------------------------------------------------------
# The pet
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Pet:
    id: str
    name: str
    species: str
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
    bond_lines: tuple         # one per BOND_RANKS entry
    passives: dict            # bond rank index -> effects, keys from EFFECT_LABELS
    discovery: Discovery | None = None

    def to_dict(self, bond: int = 0, *, found: bool = True) -> dict:
        """The shape the frontend and the codex both read.

        An unfound pet still renders — silhouette, region, and the deed that
        finds it — because a hidden thing nobody can work toward is not content,
        it is an accident.
        """
        progress = bond_progress(bond)
        kind = HINT_KINDS[self.hint_kind]
        d = {
            "id": self.id, "name": self.name, "species": self.species,
            "skill": self.skill, "sprite": self.sprite, "colour": self.colour,
            "tagline": self.tagline, "hint_kind": self.hint_kind,
            "hint_label": kind["label"], "rank_ceiling": kind["rank_ceiling"],
            "found": bool(found),
            "region": self.discovery.region if self.discovery else "",
            "where": self.discovery.where if self.discovery else "",
            "how": self.discovery.how if self.discovery else "",
            **progress,
        }
        if found:
            d.update({
                "blurb": self.blurb,
                "method": self.method,
                "line": self.bond_lines[progress["rank_index"]],
                "passive": items.describe(self.passive_effects(bond)),
                "speaks_when": [t.kind for t in self.triggers],
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
# The roster
# --------------------------------------------------------------------------
#
# Five of these were named by the player. The other four were authored to cover
# the habits the five leave uncovered: locating a defect, pricing an approach,
# splitting a problem, and writing the test that would have caught it.
#
# SICKLE and WITNESS share a skill on purpose. Breaking your own code is two
# separate habits — choosing the input that hurts, and writing it down so it can
# never hurt twice — and a player who has one of them almost never has the other.

PETS: tuple = (

    Pet(
        id="jaguar", name="ROSETTE", species="Jaguar",
        skill="SPEED", hint_kind="ALGORITHM_FAMILY",
        sprite="jaguar", colour="#e8a33d",
        tagline="Speed, and the eye that recognises a shape it has hunted before.",
        blurb="A jaguar the colour of late afternoon, built entirely out of "
              "patience followed by no patience at all. It has been watching you "
              "read the same statement three times.",
        method="When you freeze at the blank screen, it names the FAMILY the "
               "problem belongs to. Never the steps — the family. Recognition is "
               "the part of an interview that happens in the first ninety seconds, "
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
            where="The anagram groves, where three different paths spell the same "
                  "word and lead to the same clearing.",
            how="Clear three anagram-grove encounters with nothing cast and nothing "
                "hinted. It will not show itself to someone still hesitating.",
            needs=(
                {"kind": "family_unaided", "family": "anagrams", "count": 3},
                {"kind": "no_hint_streak", "count": 3},
            ),
            first_words="You solved three without stopping to think. That is the "
                        "only invitation I answer.",
        ),
    ),

    Pet(
        id="python", name="IDIOM", species="Python",
        skill="PYTHON", hint_kind="EXACT_SYNTAX",
        sprite="snake", colour="#4fb783",
        tagline="The language itself, in the form of something that can coil on a "
                "keyboard.",
        blurb="Four feet of patient green that has lived under the floor of the "
              "ruined house in Python Village since before the Null King. It does "
              "not know any algorithms. It knows every word.",
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
            "QUEUE": "`from collections import deque`, then `q.append(x)` and "
                     "`q.popleft()`. Taking index zero off a list is the slow way.",
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
            "HEAP": "`import heapq`, then `heapq.heappush(h, (cost, item))` and "
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
            "There are about forty words in this language that matter. You have "
            "thirty-one of them.",
        ),
        on_intervene="The word you are looking for is this one.",
        on_cleared="Fluent. Say it again tomorrow and it is yours for good.",
        on_failed="The sentence was fine. The idea underneath it was not. That is "
                  "somebody else's department.",
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
            where="Under the floor of the half-rebuilt house, which is the one room "
                  "in the village that has never finished repairing itself.",
            how="Clear five of the village's language drills unaided and bring "
                "Python to real fluency. It listens for the sound of someone who "
                "has stopped translating, and there is no faking that sound.",
            needs=(
                {"kind": "family_unaided", "family": "python_basics", "count": 5},
                {"kind": "skill_mastery", "skill": "PYTHON", "value": 30},
            ),
            first_words="You stopped typing like someone translating. I came up to "
                        "see who had learned to speak.",
        ),
    ),

    Pet(
        id="llama", name="PLAIN", species="Llama",
        skill="COMMUNICATION", hint_kind="RESTATEMENT",
        sprite="llama", colour="#d8c8a8",
        tagline="Patience, structure, and a complete absence of urgency.",
        blurb="A llama of the high pass. It has watched avalanches, ambushes and "
              "two separate ends of the world, and has adjusted its opinion of none "
              "of them. It chews.",
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
        bond_lines=(
            "It grazes nearby and regards you as terrain.",
            "It walks the pass beside you. It has not commented on this.",
            "It begins restating things before you ask, which from a llama is "
            "effusive.",
            "It positions itself between you and whatever is making noise, and "
            "continues chewing.",
            "Two villages have named a road after it. It has not been to either.",
        ),
        passives={
            2: {"combo_shield": 1},
            3: {"stamina_max": 4},
            4: {"combo_shield": 2, "stamina_max": 6},
        },
        discovery=Discovery(
            region="twin_pointer_pass",
            where="Halfway up the pass, on the side of the path with the better "
                  "view, which it has clearly chosen deliberately.",
            how="Survive two memory ambushes — disguised variants of problems you "
                "cleared days earlier. It turns up afterward and does not consider "
                "this remarkable.",
            needs=(
                {"kind": "retest_survived", "skill": "", "count": 2},
                {"kind": "skill_mastery", "skill": "COMMUNICATION", "value": 20},
            ),
            first_words="You were ambushed by something you had already beaten, and "
                        "you beat it again. Fine. I will come along.",
        ),
    ),

    Pet(
        id="penguin", name="PIVOT", species="Penguin",
        skill="SORTING", hint_kind="DATA_STRUCTURE",
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
            where="The flooded third gallery, past the point where the ore carts "
                  "stop being unloadable from the top.",
            how="Take the Ninth Cart, under the Stack and Queue Mines, to its "
                "third level and come back out. It will be waiting by the lift, "
                "third in a queue of one.",
            needs=(
                {"kind": "dungeon_depth", "dungeon": "ninth_cart", "depth": 3},
                {"kind": "skill_unaided", "skill": "QUEUE", "count": 2},
            ),
            first_words="You went in last and came out first. I appreciate a "
                        "discipline about order.",
        ),
    ),

    Pet(
        id="velociraptor", name="SICKLE", species="Velociraptor",
        skill="TESTING", hint_kind="EDGE_CLASS",
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
                     "nine seconds and dies in front of an interviewer.",
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
            where="The scree slope below the Hydra's hall, where something has been "
                  "pacing in the same three-metre line for weeks.",
            how="Beat the Three-Sum Hydra with nothing cast, and land ten correct "
                "probes across the realms. It respects exactly one thing, and that "
                "is a prediction that came true.",
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
        id="axolotl", name="PATCH", species="Axolotl",
        skill="DEBUGGING", hint_kind="DEFECT_CLASS",
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
            where="The Armorer's quench trough, which nobody has drained in a "
                  "hundred years and which is somehow clean.",
            how="Repair six broken programs unaided and clear the dungeon's cells. "
                "It only surfaces for somebody who has stopped guessing at fixes.",
            needs=(
                {"kind": "skill_unaided", "skill": "DEBUGGING", "count": 6},
                {"kind": "region_cleared", "region": "debugging_dungeon"},
            ),
            first_words="Six repairs, and not one of them a guess. You may keep me "
                        "in something with water in it.",
        ),
    ),

    Pet(
        id="tortoise", name="HALT", species="Tortoise",
        skill="BIG_O", hint_kind="COST_SHAPE",
        sprite="tortoise", colour="#6b8f3f",
        tagline="What your approach costs, said out loud, before the clock says it "
                "for you.",
        blurb="Older than the Complexity Tower it lives in, and unimpressed by it. "
              "It has climbed four of the tower's floors. It intends to climb the "
              "fifth. It is not in any difficulty.",
        method="It prices what you have written — the shape of the work, not the "
               "fix. Correct and unaffordable is the most common way a good "
               "candidate loses, and it is the one nobody notices while it is "
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
            where="The fifth landing, where the stair stops being climbable by "
                  "anyone in a hurry.",
            how="Clear five performance trials and bring Complexity to real "
                "competence. The tortoise is on the fifth floor. It has always been "
                "on the fifth floor. Getting there is the condition.",
            needs=(
                {"kind": "perf_cleared", "count": 5},
                {"kind": "skill_mastery", "skill": "BIG_O", "value": 45},
            ),
            first_words="You arrived on the fifth floor without brute force. Most "
                        "people arrive out of breath and on the second.",
        ),
    ),

    Pet(
        id="nautilus", name="CHAMBER", species="Nautilus",
        skill="RECURSION", hint_kind="DECOMPOSE",
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
            where="The spring at the centre of the innermost clearing — the copy of "
                  "the forest that has no further copy inside it.",
            how="Clear four of the forest's recursive encounters unaided and survive "
                "one recursion ambush. The innermost clearing only exists for "
                "somebody who reached the base case honestly.",
            needs=(
                {"kind": "family_unaided", "family": "recursion_basics", "count": 4},
                {"kind": "retest_survived", "skill": "RECURSION", "count": 1},
            ),
            first_words="You went all the way in and came all the way back out "
                        "carrying something. That is the only trick there is.",
        ),
    ),

    Pet(
        id="crow", name="WITNESS", species="Crow",
        skill="TESTING", hint_kind="MISSING_TEST",
        sprite="crow", colour="#9b96b8",
        tagline="The test you did not write, described but never handed to you.",
        blurb="It perches on the tiles you have already lit in the Ruins and keeps "
              "a count of things. Not treasure. Occurrences. It has been keeping "
              "this count since before the Ruins were ruins.",
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
            "The interviewer will ask how you would test it. It is worth having an "
            "answer.",
        ),
        on_intervene="There is a test you have not written, and it is the one that "
                     "matters.",
        on_cleared="It survived the test I would have written. I will write another.",
        on_failed="Good. Now write that failure down as a test, so that it cannot "
                  "happen to you twice.",
        bond_lines=(
            "It watches from a broken arch and leaves when you look directly at it.",
            "It has started leaving small objects on your pack, which is a crow's "
            "idea of a contract.",
            "It names the missing test before your suite has finished running.",
            "It keeps your failure log for you, and is better at it than you were.",
            "Every ruin in the region has one crow on it. There is one crow. It is "
            "on all of them.",
        ),
        passives={
            2: {"retest_bonus": 0.2},
            3: {"retest_bonus": 0.35},
            4: {"retest_bonus": 0.5, "xp_bonus": 0.15},
        },
        discovery=Discovery(
            region="dp_ruins",
            where="On the lit tiles — always on a tile you have already solved, "
                  "never on one you have not.",
            how="Clear five testing encounters unaided and hold a five-clear streak "
                "with nothing cast. It counts. That is the whole of what it does, "
                "and you have to give it something worth counting.",
            needs=(
                {"kind": "skill_unaided", "skill": "TESTING", "count": 5},
                {"kind": "no_hint_streak", "count": 5},
            ),
            first_words="Five in a row, unassisted. I have been counting since "
                        "before this was a ruin. That is the best run I have.",
        ),
    ),
)

BY_ID = {pet.id: pet for pet in PETS}
PET_IDS = tuple(pet.id for pet in PETS)
BY_SKILL: dict = {}
for _pet in PETS:
    BY_SKILL.setdefault(_pet.skill, []).append(_pet.id)
del _pet


# --------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------

def available_in(mode: str, region_id: str = "") -> bool:
    """May a pet speak at all right now.

    One function, because a rule that is checked in three places is a rule that
    is eventually checked in two. Interview Mode is absolute; the Coliseum and
    the Castle are silent because their own descriptions say they are.
    """
    from .config import MODE_INTERVIEW
    if mode == MODE_INTERVIEW:
        return False
    return region_id not in SILENCED_REGIONS


# Which part of the redacted encounter view each kind of pet reads. None of these
# fields can carry an answer: a pattern name, a weakness class and a failure
# category are all vocabulary the game already shows the player elsewhere.
KEYED_BY = {
    "ALGORITHM_FAMILY": "pattern",
    "EXACT_SYNTAX": "pattern",
    "RESTATEMENT": "pattern",
    "DATA_STRUCTURE": "pattern",
    "COST_SHAPE": "pattern",
    "DECOMPOSE": "pattern",
    "EDGE_CLASS": "weakness",
    "MISSING_TEST": "weakness",
    "DEFECT_CLASS": "category",
}


def hint_body(pet_id: str, context: dict | None = None) -> str:
    """The sentence this pet would say about this encounter.

    `context` is the REDACTED view: {"pattern", "weakness", "category"}. Anything
    else in it is ignored, which is deliberate — a caller cannot accidentally hand
    a pet the tests or the worked solution, because there is no field for them.
    """
    pet = BY_ID[pet_id]
    key = (context or {}).get(KEYED_BY[pet.hint_kind], "") or ""
    return pet.hints.get(key.upper(), pet.fallback)


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
                 context: dict | None = None, spoken: int = 0) -> dict | None:
    """The whole event, or None because the pet has nothing to say yet.

    `spoken` is how many times this pet has already spoken in this encounter;
    the cap comes from its bond rank. Callers apply `hint_weight` to the
    encounter's `hints_used` and clamp the earnable rank to `rank_ceiling`. That
    is the entire cost model, and it is the same one the hint tree pays.
    """
    if not available_in(mode, region_id):
        return None
    pet = BY_ID.get(pet_id)
    if pet is None:
        return None
    rank = bond_rank(bond)
    if spoken >= rank.interventions:
        return None

    for trigger in pet.triggers:
        if not _fires(trigger, signals or {}, rank.threshold_scale):
            continue
        kind = HINT_KINDS[pet.hint_kind]
        return {
            "pet": pet.id, "name": pet.name, "species": pet.species,
            "sprite": pet.sprite, "colour": pet.colour, "skill": pet.skill,
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
            "remaining": rank.interventions - spoken - 1,
        }
    return None


def party_intervention(active: list, *, bonds: dict | None = None,
                       mode: str = "adventure", region_id: str = "",
                       signals: dict | None = None, context: dict | None = None,
                       spoken: dict | None = None) -> dict | None:
    """The one pet that speaks, when two are in the field.

    Only one of them ever speaks at a time. Two companions talking over each
    other during a timed problem is noise, and noise is the opposite of a hint.
    Order of the active list decides ties, so the player's own arrangement is the
    tiebreak rather than something they cannot see.
    """
    for pet_id in active or []:
        found = intervention(
            pet_id, bond=int((bonds or {}).get(pet_id, 0)), mode=mode,
            region_id=region_id, signals=signals, context=context,
            spoken=int((spoken or {}).get(pet_id, 0)))
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


def passive_effects(pet_id: str, bond: int = 0) -> dict:
    """The passive a bond rank has earned. Keys are items.EFFECT_LABELS keys and
    nothing else — validated at import, so this cannot drift."""
    pet = BY_ID.get(pet_id)
    return pet.passive_effects(bond) if pet else {}


def party_effects(active: list, bonds: dict | None = None,
                  mode: str = "adventure") -> dict:
    """Every passive the companions in the field are contributing.

    Merged by taking the best value per key rather than by adding, so carrying
    two pets that both give loot luck is a worse plan than carrying two pets that
    do different jobs — which is the decision this system exists to create.

    Nothing is contributed in Interview Mode. Items already work this way, and a
    pet is not allowed to be the exception that proves the rule.
    """
    from .config import MODE_INTERVIEW
    if mode == MODE_INTERVIEW:
        return {}
    merged: dict = {}
    for pet_id in (active or [])[:ACTIVE_LIMIT]:
        earned = passive_effects(pet_id, int((bonds or {}).get(pet_id, 0)))
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
        have = retests.get(skill, 0) if skill else sum(retests.values())
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
    if kind == "stat":
        stat = clause.get("stat", "")
        return _row(stat.replace("_", " "), (ev.get("stats") or {}).get(stat, 0),
                    clause.get("at_least", 1))
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
        "region": found.region if found else "",
        "where": found.where if found else "",
        "how": found.how if found else "",
        "first_words": found.first_words if found else "",
        "checks": checks,
        "met": bool(checks) and all(row["met"] for row in checks),
    }


def newly_found(evidence: dict | None = None, already: list | None = None) -> list:
    """Every pet whose conditions are now satisfied and which has not been met.

    Returns the full discovery payloads so the caller can show the moment
    properly. Finding a companion should never be a line in a log.
    """
    have = set(already or [])
    out = []
    for pet in PETS:
        if pet.id in have:
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
        if pet.id in have or not pet.discovery:
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
    """Flat, JSON-safe, and small enough to drop straight into the save blob."""
    return {"found": [], "active": [], "bond": {}, "met_at": {}}


def grant(state: dict, pet_id: str, *, at: float = 0.0) -> bool:
    """Record that the player has met this animal. True if it is news."""
    if pet_id not in BY_ID or pet_id in state.get("found", []):
        return False
    state.setdefault("found", []).append(pet_id)
    state.setdefault("bond", {}).setdefault(pet_id, 0)
    state.setdefault("met_at", {})[pet_id] = at
    if len(state.setdefault("active", [])) < ACTIVE_LIMIT:
        state["active"].append(pet_id)     # a new companion walks with you by default
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


def set_active(state: dict, pet_ids: list) -> list:
    """Choose who walks with you. Silently drops unfound pets and anything past
    the limit rather than erroring, because this is called from a UI."""
    chosen = [p for p in (pet_ids or []) if p in state.get("found", [])][:ACTIVE_LIMIT]
    state["active"] = chosen
    return chosen


def catalogue(state: dict | None = None) -> list:
    """Every pet, found or not, in roster order, for the companion screen."""
    state = state or new_state()
    found = set(state.get("found", []))
    bonds = state.get("bond", {}) or {}
    out = []
    for pet in PETS:
        row = pet.to_dict(int(bonds.get(pet.id, 0)), found=pet.id in found)
        row["active"] = pet.id in (state.get("active") or [])
        out.append(row)
    return out


# --------------------------------------------------------------------------
# Self-check
# --------------------------------------------------------------------------
#
# Two of these are load-bearing rules rather than tidiness, so they are proved
# here and asserted at import rather than left for a reviewer to notice:
#
#   1. No pet effect key may sit outside items.EFFECT_LABELS. An unknown key
#      would silently do nothing, which is worse than crashing.
#   2. No authored line may contain a literal answer. A pet that pastes code is
#      a Phoenix that costs nothing, and Phoenix costs the whole rank.

_ANSWER_TELLS = (
    "def ",          # a function header is somebody's worked solution
    "return ",       # so is a return statement
    "```",           # so is a fenced block
    "the answer is",
    "the solution is",
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


def _validate() -> list:
    """Import-time guard. Returns the problems; the module refuses to load with any."""
    problems = []
    for pet in PETS:
        if pet.hint_kind not in HINT_KINDS:
            problems.append(f"{pet.id}: unknown hint kind {pet.hint_kind}")
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
        for clause in (pet.discovery.needs if pet.discovery else ()):
            if clause.get("kind") not in DISCOVERY_CHECKS:
                problems.append(f"{pet.id}: unknown discovery check {clause.get('kind')}")
        for label, text in _authored_text(pet):
            lowered = (text or "").lower()
            for tell in _ANSWER_TELLS:
                if tell in lowered:
                    problems.append(f"{pet.id}: {label} reads like an answer ({tell!r})")
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

    lines = sum(1 for pet in PETS for _ in _authored_text(pet))
    return {
        "pets": len(PETS),
        "player_named": sum(1 for pet in PETS
                            if pet.id in ("jaguar", "python", "llama", "penguin",
                                          "velociraptor")),
        "authored": len(PETS) - 5,
        "skills_covered": sorted({pet.skill for pet in PETS}),
        "hint_kinds": len(HINT_KINDS),
        "bond_ranks": len(BOND_RANKS),
        "triggers": sum(len(pet.triggers) for pet in PETS),
        "trigger_kinds_used": sorted({t.kind for pet in PETS for t in pet.triggers}),
        "hint_lines": sum(len(pet.hints) for pet in PETS),
        "voice_lines": sum(len(pet.idle) + len(pet.bond_lines) + 3 for pet in PETS),
        "discovery_clauses": sum(len(pet.discovery.needs)
                                for pet in PETS if pet.discovery),
        "authored_strings": lines,
        "passive_effect_keys": effect_keys,
        "effect_keys_outside_items": stray,
        "effect_keys_ok": not stray,
        "lines_reading_as_answers": answerish,
        "no_literal_answers": not answerish,
        "unknown_vocabulary": unknown_vocab,
        "interview_sealed": not available_in("interview")
                            and not party_effects(list(PET_IDS), {}, "interview"),
        "silenced_regions": list(SILENCED_REGIONS),
        "ok": not stray and not answerish and not unknown_vocab,
    }


_PROBLEMS = _validate()
if _PROBLEMS:                                  # pragma: no cover - authored data
    raise ValueError("gauntlet.pets is inconsistent: " + "; ".join(_PROBLEMS))


if __name__ == "__main__":
    print(json.dumps(self_check(), indent=2))
