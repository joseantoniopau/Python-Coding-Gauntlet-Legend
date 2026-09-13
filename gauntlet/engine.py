"""The game engine: state, encounters, combat, progression.

Everything the client can do goes through here, so the invariants live in one
place — chief among them that Interview Mode never leaks a hint, a pattern name,
or a coach.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field, asdict

from . import adaptive, config, coach as coachmod, db, grading, items, sandbox
from . import curriculum, diagnostic, puzzles, story as storymod, tactics
from . import death
from . import unmaking
from . import skills as skillmod
from . import srs as srsmod
from . import world
from . import weather as weathermod
from . import bestiary, classes, dungeons, elements, finalexam, forge
from . import incantation, legendaries, potions
from . import minirepo
from . import pets, progression, quests, saves, worldgen
from . import corpus as corpusmod
from . import transfer as transfermod
# The ten systems this file is the only door to. Each one was built in
# isolation, proved itself against real numbers and wrote down a contract; none
# of them imports this file and none of them writes progression. Everything
# below is that contract being honoured at the call sites the contracts name.
from . import antagonist, arts, banter, captives, economy, finale, hunters, movesets
# ending.py is the seam between the two exams and it is the ONLY thing in
# this file that decides whether a practical was the story's last room or a
# measurement sat from the menu. See ending.WIRING; the four touch points it
# names are the DEFAULT_STATE key below, `_start_exam(staged=...)`,
# `finish_interview`'s single `ending.resolve()` and `start_final_trial()`.
from . import ending
from . import regalia, sages, sanctuary, upkeep
from .corpus import ensure as ensure_corpus
from .corpus.schema import Problem

# THE NINETY-SIX SECRET ARTS ARE PUT INTO THE TWO CATALOGUES HERE, ONCE.
#
# `arts.py` deliberately registers nothing on import — it used to, and a package
# whose test suite imports every module at discovery time then had ninety-six
# extra lines in `incantation.BY_ID` as a side effect of an import statement.
# So registration is something a caller asks for, and this is the caller: one
# call, at the top of the one module that is the whole engine, where it can be
# seen happening.
#
# It writes to `incantation.BY_ID` and `movesets.BY_ID` and to nothing else. In
# particular it does NOT touch `incantation.CATALOGUE`, which is what keeps
# `learn_from_clear()` from ever handing a secret art out as a clear reward. A
# sage or nothing.
arts.register()

# Artifacts are ordinary items everywhere the engine looks one up — the equip
# path, the loadout panel, the secret awards — through _item() below.
#
# The manifest says to do that by writing them into items.BY_ID at boot.  Do not:
# legendaries.validate() asserts `a.id not in items.BY_ID`, which is how it
# proves an artifact never shadows a catalogue item, so the registration would
# turn that module's own invariant into a permanent failure. One resolver in
# this file gets the same result and leaves the catalogue alone.
#
# The 31 artifact keys and the 22 class-tree keys already carry labels in
# items.EFFECT_LABELS, so items.describe renders them; no merge is needed.


# ---------------------------------------------------------------------------
# The forge, resolved into the catalogue (forge.WIRING §3)
# ---------------------------------------------------------------------------
#
# Fifty-four rungs want to be ordinary items, because everything that already
# works on an item — the equip path, the tooltip, the loadout screen, the
# inventory — then works on a forged blade with no second code path.
# forge.item_kwargs() returns exactly what items._i() takes, so the ladder is
# one loop.
#
# They are NOT written into items.BY_ID. forge.validate() asserts that a rung id
# never appears there, which is how that module proves a blade can never shadow
# a catalogue item, and the registration would turn its own invariant into a
# permanent failure. This is the same arrangement legendaries.py has, and the
# same resolver below serves both: one lookup in this file, catalogue untouched.
#
# Staying out of the catalogue also settles the drop question by construction.
# A forged blade is never FOUND — items.roll_drop only ever picks out of
# items.CATALOGUE — and that is the honest statement of the design: the only
# road to one of these is the smith.
#
# What DOES have to be merged is the restriction. classes.CLASS_RESTRICTED
# knows only the six ids classes.GEAR_REQUESTS declared, which are rung SIX of
# each line; without forge.FORGE_RESTRICTED a Berserker can equip the Analyst's
# rung-seven Calipers, which is the kind of bug nobody reports and everybody
# exploits.
#
# Nothing is granted here. The objects exist; owning one is
# state["forge"]["tiers"], and that only ever moves through forge.upgrade().

FORGE_ITEMS: dict = {}
for _blade in forge.BLADES:
    for _tier in range(forge.MIN_TIER, forge.MAX_TIER + 1):
        _kwargs = forge.item_kwargs(_blade.id, _tier)
        # The blade takes the element of the ground its heaviest metal came out
        # of, which closes the loop the forge was built for: walk to the mines,
        # carry ember-metal back to Vess, and the thing she hands you strikes
        # with FIRE. Nobody authored that; items.py derives a weapon's element
        # from its region the same way, and forge.METALS already knows which
        # region each bar belongs to. Rung one cost no metal, so it takes the
        # line's first field metal — the same fallback _forge_art() uses.
        _rung = forge.rung(_blade.id, _tier)
        _ore = (max(_rung.cost, key=lambda mid: forge.METAL_BY_ID[mid].rung)
                if _rung.cost else _blade.metals.get("r1", ""))
        _regions = forge.METAL_BY_ID[_ore].regions if _ore in forge.METAL_BY_ID else ()
        _element = elements.affinity_for(_regions[0] if _regions else "")
        FORGE_ITEMS[_kwargs["id"]] = items._i(
            **_kwargs, hidden=True,
            element=_element if _element in elements.ELEMENTS else "")
        classes.CLASS_RESTRICTED.setdefault(_kwargs["id"], _blade.class_id)
del _blade, _tier, _kwargs, _rung, _ore, _regions, _element


def _forge_art(item_id: str) -> dict:
    """The nested `forge` block web/js/lootart.js reads off an item dict.

    lootart.forgeSpec() wants the line, the rung and the ore alongside
    forge.art_at()'s own keys; art_at names the material the object is FINISHED
    in ("steel") and the ore is what the player carried out of a region, and the
    two are deliberately different words. The ore is the heaviest metal the rung
    actually cost, because that is the one a player would name if you asked them
    what the thing is made of. Rung one cost nothing, so it borrows the line's
    first field metal.
    """
    pair = forge.RUNG_BY_ID.get(item_id)
    if pair is None:
        return {}
    blade, rung = pair
    ore = max(rung.cost, key=lambda mid: forge.METAL_BY_ID[mid].rung) \
        if rung.cost else blade.metals.get("r1", "")
    return {"blade": blade.id, "tier": rung.tier, "metal": ore,
            **forge.art_at(blade.id, rung.tier)}


def _forge_item_dict(item_id: str) -> dict | None:
    """A rung as the client sees it: an ordinary item dict plus its forge
    block, so one payload feeds both the tooltip and the art pipeline."""
    item = FORGE_ITEMS.get(item_id)
    if item is None:
        return None
    blade, rung = forge.RUNG_BY_ID[item_id]
    return {**item.to_dict(), "forge": _forge_art(item_id),
            "technique": {"name": blade.technique, "rank": rung.technique_rank,
                          "text": rung.technique_text},
            "look": rung.look, "line": blade.line}


def _item(item_id: str):
    """An item, an artifact or a forged rung, whichever owns this id.

    Neither of the latter two ever shadows the catalogue: both modules assert
    their ids are absent from items.BY_ID, and both are checked after it.
    """
    found = items.BY_ID.get(item_id)
    if found is not None:
        return found
    rung = FORGE_ITEMS.get(item_id)
    if rung is not None:
        return rung
    artifact = legendaries.BY_ID.get(item_id)
    return artifact.to_item() if artifact is not None else None


@dataclass
class Encounter:
    problem_id: str
    mode: str
    started_at: float
    hints_used: int = 0
    hint_levels: list = field(default_factory=list)
    used_phoenix: bool = False
    runs: int = 0
    submits: int = 0
    syntax_errors: int = 0
    first_code_at: float = 0.0
    is_retest: bool = False
    interval_days: float = 0.0
    declared_pattern: str = ""
    # What the player said was WRONG, before the diagnosis rendered. Kept beside
    # `declared_pattern` because it is the same kind of claim — a guess made
    # before the answer — and it is graded the same way, which is not at all.
    declared_cause: str = ""
    explanation: str = ""
    boss_id: str = ""
    boss_phase: int = 0
    interview_id: str = ""
    last_report: dict = field(default_factory=dict)
    probes_used: int = 0
    probe_log: list = field(default_factory=list)
    exposed: list = field(default_factory=list)      # weakness keys revealed by probes
    temp_effects: dict = field(default_factory=dict)  # consumables used this battle
    enemy: dict = field(default_factory=dict)
    free_recast_used: bool = False
    # -- the turn, the pouch and the wheel ----------------------------------
    # An encounter is turn-based: one graded submission is one turn, right or
    # wrong, and a potion may be drunk ALONGSIDE that submission rather than
    # instead of it. `potion_turn` is potions.TurnState and is what enforces
    # "one draught per turn"; without it the optimal play is drink-instead-of-
    # think, which would delete the only thing this game teaches.
    potion_turn: dict = field(default_factory=dict)
    poison: dict = field(default_factory=dict)        # potions.Poison, the player's
    # elements.StatusInstance lists, as plain dicts. Both sides, because every
    # status in elements.STATUSES applies to monsters exactly as it applies to
    # the player and the functions that tick them do not ask whose they are.
    statuses: list = field(default_factory=list)
    enemy_statuses: list = field(default_factory=list)
    # bestiary.vitals(): the enemy's focus pool, its element and the specials
    # that pool buys. Carried on the encounter so a fight survives a reload.
    enemy_vitals: dict = field(default_factory=dict)
    enemy_poison: dict = field(default_factory=dict)  # potions.Poison, the enemy's
    turn: int = 1
    combat_log: list = field(default_factory=list)
    # Companion interventions live here rather than in temp_effects, which is
    # folded straight into items.total_effects and can only hold numbers.
    pet_spoke: bool = False
    pet_spoken: dict = field(default_factory=dict)   # pet id -> times spoken
    # Companions that have already said "this is above me" in this encounter.
    # A refusal is honest exactly once; after that the animal would just be
    # apologising for the length of the problem.
    pet_refused: list = field(default_factory=list)
    rank_ceiling: str = ""          # the best rank still earnable here
    # HOW BADLY THIS FIGHT WENT, which is what the kit wears out on.
    #
    # `upkeep.wear_encounter` is driven by blows taken and blows landed and
    # nothing was counting either. They are counted on the encounter rather than
    # in `stats` because wear is billed ONCE, when the encounter settles, and a
    # lifetime counter cannot answer "how much of that was this fight".
    hits_taken: int = 0             # enemy turns that actually landed damage
    blows_landed: int = 0           # graded submissions and casts that landed
    # The region this fight is being fought in, frozen at start. `player.region`
    # can move underneath a long encounter, and every region-scoped number this
    # fight produces — what it pays, which vendor restocks, which sage's toll it
    # counts against — has to be about where the fight actually happened.
    region: str = ""
    dungeon_room: int = -1          # the room this fight belongs to, or -1
    # Hold-out content: `corpus.sealed`, not `finalexam.sealed`. Carried on the
    # encounter because it decides the seal, and the seal is what every hint,
    # probe, companion and worked solution in this file already consults.
    holdout: bool = False
    # -- Mini-Repo Battles --------------------------------------------------
    # A Mini-Repo encounter names a repo rather than a problem. `problem_id`
    # still carries an id, because everything downstream of _apply_outcome
    # stores one, but it is the synthetic id below and it is not in the corpus.
    # `repo_files` is the player's working tree, kept so a reload mid-fight
    # does not throw away twenty minutes of reading.
    repo_id: str = ""
    repo_files: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


_ENC_FIELDS = frozenset(Encounter.__dataclass_fields__)


# Which learning failure a puzzle miss actually represents.
_PUZZLE_CAUSE = {
    "RUNE_ASSEMBLY": "PYTHON_RECALL",
    "TRACE": "DEBUGGING",
    "SPOT_THE_FLAW": "DEBUGGING",
    "STATE_PREDICT": "PYTHON_RECALL",
    "BREAK_IT": "TESTING",
    "COMPLEXITY_MATCH": "COMPLEXITY",
}

# ---------------------------------------------------------------------------
# A Repo, wearing a Problem's coat
# ---------------------------------------------------------------------------
#
# `_apply_outcome` is the one place progression changes, and it reads a Problem.
# A Repo is not a Problem — no single entry point, no reference callable, no
# derived tests — so it is not pushed into the corpus, not validated as one, and
# not selected from. What it gets instead is this: exactly the fields
# `_apply_outcome` and the world layer behind it consult, and nothing else.
#
# The id carries a prefix the corpus cannot produce, so a Mini-Repo in
# `solved_ids`, `recent_ids` or the attempt log can never be mistaken for a
# corpus problem by anything that looks one up — and everything that does look
# one up already guards with `if i in self.by_id`.

REPO_ID_PREFIX = "minirepo:"

# One skill. Reading somebody else's code and repairing it without breaking a
# caller is debugging, and the suite is the contract, which is testing.
REPO_SKILL = "DEBUGGING"
REPO_SECONDARY = "TESTING"

_REPO_PROBLEMS: dict = {}


def repo_problem(repo) -> Problem:
    """The Problem-shaped view of a Repo. Cached: it is derived and frozen."""
    found = _REPO_PROBLEMS.get(repo.id)
    if found is not None:
        return found
    problem = Problem(
        id=REPO_ID_PREFIX + repo.id,
        title=repo.title,
        realm=repo.realm,
        pattern=REPO_SKILL,
        difficulty=repo.difficulty,
        problem_statement=repo.brief,
        # No entry point on purpose. Everything that runs code checks this and
        # a Mini-Repo is run by minirepo.run, through its own door.
        entry={"kind": "project"},
        canonical_solution="",          # the reference patch is the debrief's
        encounter_kind=minirepo.ENCOUNTER_KIND,
        secondary_patterns=[REPO_SECONDARY],
        source_type="GENERAL_INTERVIEW",
        provenance_note=("The reported practical: an existing codebase, its own "
                         "tests, and a ticket."),
        spaced_repetition_family="mini_repo_" + repo.id,
        estimated_seconds=repo.clock,
        target_seconds=repo.clock,
        tags=["mini_repo", "realm:" + repo.realm] + ["tag:" + t for t in repo.tags],
    )
    _REPO_PROBLEMS[repo.id] = problem
    return problem


def repo_report(verdict) -> sandbox.ExecutionReport:
    """The verdict's test rows as the ExecutionReport the rest of the engine
    reads. Not a second grader: every field here comes off the verdict, which
    minirepo produced from the sandbox."""
    tests = [
        sandbox.TestResult(
            index=i, name=row["id"], hidden=False, kind="project",
            status=row["status"], ms=float(row.get("ms") or 0.0),
            message=row.get("message", ""))
        for i, row in enumerate(verdict.tests)
    ]
    return sandbox.ExecutionReport(
        ok=verdict.outcome != "BROKEN", phase="tests", tests=tests,
        stdout=verdict.stdout, stderr=verdict.stderr, error=verdict.error,
        wall_ms=verdict.wall_ms, hardened=verdict.hardened)


# What the player's focus bar does between turns.
#
# Focus is what learning spells are bought with, so it has to come back or the
# hint tree eventually closes and learning dead-ends — which is the one thing
# this game is not allowed to do. Two a turn is slow enough that a hint is still
# a decision and fast enough that a long fight is never a locked door.
# elements.STATUSES["VOIDED"] suppresses this and nothing else: it stops focus
# COMING BACK, never focus being SPENT, for exactly that reason.
FOCUS_PER_TURN = 2

# What an enemy's ordinary swing is worth before the wheel touches it. Deliberately
# the same number the game already charged for a failed submission
# (config.STAMINA_LOSS_FAILED_SUBMIT), because the enemy getting a turn is not
# meant to make the game harder — it is meant to make the same cost READABLE, as
# something that swung at you out of a region with weather rather than as a
# silent subtraction. elements.resolve_damage then scales it between 0.25x and
# 1.5x depending on what the player read and what they are wearing.
ENEMY_BASE_DAMAGE = config.STAMINA_LOSS_FAILED_SUBMIT

# WHAT A LANDED LINE GIVES BACK, AND WHY THERE HAS TO BE SOMETHING.
#
# FOCUS_PER_TURN above says focus has to come back "or the hint tree eventually
# closes and learning dead-ends — which is the one thing this game is not
# allowed to do". Health is the same sentence and the incantation loop did not
# have it: `submit` refunds a point of stamina on a solved answer and ends the
# fight on the same breath, while an incantation battle runs fifteen to forty
# turns against a twenty-point bar and regenerated nothing at all.
#
# The measurement, taken over all thirty-seven authored fights at every element
# a player can hold: incoming damage against a caster who never misses averages
# 0.8 points a turn and peaks at 2.6, because a charged attack lands about seven
# and the status it leaves ticks another four. Twenty-four of the thirty-seven
# fights therefore routed a player who typed PERFECTLY and happened to have no
# armour and nothing to drink — which is the dead end this game is not allowed
# to have, and which `_incant_enemy_turn` already argues against in its own
# docstring: a fight you can only win by shopping is not a fight about Python.
#
# A FRACTION OF THE BAR, not a flat number, because that is the discipline
# potions.py already uses for restoration — a hefty flagon is still hefty after
# VIGOR doubles your health — and because armour's bonus_health would otherwise
# make the refund quietly weaker the better geared you were, which is backwards.
#
# TEN PERCENT, and the ceiling is what sets it: it has to stay BELOW the peak
# incoming rate of 12.9% of the bar, or a perfect run through the worst matchup
# in the game stops costing anything and the pouch becomes decoration. It sits
# above the median instead, so the ordinary fight is comfortable, the worst one
# is survivable and close, and missing a line still loses ground exactly as fast
# as it always did.
CAST_HEAL_SHARE = 0.10
CAST_HEAL_FLOOR = 1

# How much focus a problem-encounter enemy carries, by the depth of the problem.
# Deeper problems take more submissions, so their enemy gets more turns, so it
# has to be able to pay for more than one special across a fight — and the
# cheapest in bestiary.SPECIALS costs eight, which is what the bottom of this
# table is measured against. A TUTORIAL enemy can afford exactly one, late in a
# bad run, which is the right amount of weather for a first lesson.
ENEMY_FOCUS_BY_DIFFICULTY = {
    "GUIDED": 8, "TUTORIAL": 10, "EASY": 14, "MEDIUM": 20,
    "HARD": 28, "ELITE": 36, "BOSS": 48,
}

# The pouch's key is potions.py's to name, and DEFAULT_STATE spells it out as a
# literal so the shape of a save is readable in one place. A literal that agrees
# with reality by accident is worse than no literal at all, so it is checked
# here, at import, where a rename shows up as an ImportError rather than as a
# pouch that silently empties on every load.
assert potions.POUCH_STATE_KEY == "potions", (
    "potions.POUCH_STATE_KEY moved to %r; DEFAULT_STATE still says 'potions'"
    % potions.POUCH_STATE_KEY)

# See the note in DEFAULT_STATE: sages.py declares no state key of its own.
SAGES_STATE_KEY = "sages"

DEFAULT_STATE = {
    "player": {
        "name": "The Security Architect",
        "xp": 0, "gold": 0, "level": 1, "title": "Python Apprentice",
        "stamina": config.STAMINA_MAX, "stamina_max": config.STAMINA_MAX,
        "mana": config.MANA_MAX, "mana_max": config.MANA_MAX,
        "combo": 0, "best_combo": 0,
        "region": "python_village", "x": 24, "y": 18,
        "profile": config.DEFAULT_PROFILE,
        "created_at": 0.0, "playtime_seconds": 0.0,
        "diagnostic_done": False, "intro_seen": False,
    },
    "armor": {piece["id"]: (100 if piece["id"] != "legendary" else 0)
              for piece in world.ARMOR},
    "weapons": {},
    "companions": [],
    "achievements": [],
    "cleared_bosses": [],
    "boss_rematch": {},
    # THE OPEN BOSS FIGHT, and it is a fight rather than a flag now.
    #
    # bestiary.open_fight() returns plain JSON and bestiary.land() mutates it;
    # this is where it is kept between requests. A boss is four to six graded
    # solves, which is long enough that the fight WILL be interrupted by a
    # reload, and a fight that cannot be written to the save is a fight that
    # gets lost. None when nobody is standing in front of anything.
    "boss_fight": None,
    "solved_ids": [],
    "recent_ids": [],
    "attributes": {"LOGIC": 0, "FOCUS": 0, "VIGOR": 0, "INSIGHT": 0, "HASTE": 0},
    "unspent_points": 0,
    "build": "",
    "inventory": [],
    "equipped": {},
    "consumables": {},
    # The pouch. potions.POUCH_STATE_KEY is the authority on this name; it is
    # spelled out rather than interpolated so a reader of DEFAULT_STATE can see
    # what is in a save without opening another file, and `_load_or_create`
    # asserts the two agree.
    "potions": {},
    "secrets_found": [],
    "perf_failed_ids": [],
    "crit_streak": 0,
    "story": {},
    "diagnostic": {},
    "grimoire": [],
    "codex": [],
    "settings": {"music": True, "sfx": True, "reduced_motion": False,
                 "text_scale": 1.0, "high_contrast": False, "colorblind": False,
                 "crt": True,
                 # the mixer: master, music and sound effects move independently
                 "vol_master": 0.7, "vol_music": 0.55, "vol_sfx": 0.8},
    "skills": {},
    "schedule": {},
    "encounter": None,
    "interview": None,
    "daily": {"date": "", "quests": [], "completed": []},
    "stats": {"encounters": 0, "armor_repairs": 0, "shrines": 0,
              "hints_total": 0, "sessions": 0, "probes": 0, "probes_correct": 0,
              "crits": 0, "items_found": 0, "secrets": 0,
              # counters the artifact acquisition conditions read
              "boundary_clears": 0, "chains_completed": 0,
              "hidden_rooms_found": 0, "green_index_found": 0,
              "chapters_graduated": 0, "regions_retaken": 0,
              "interviews_passed": 0, "session_started_at": 0.0,
              "forge_streak": 0,
              # Dungeon floors cleared with no companion in the field, nothing
              # cast and nothing used. The hidden companion's whole gate.
              "solo_floors": 0},

    # --- the eleven modules' own sub-states -------------------------------
    # Each blob is whatever its owning module says it is, asked for rather than
    # copied, so a module that grows a key does not need this file edited. They
    # are all plain JSON and round-trip through db.save_state untouched.
    "pets": pets.new_state(),
    # The bag of metal, the rung each blade line stands at, and what is on the
    # rack. Loot, never evidence: a save that loses this loses gear, not
    # learning. It persists, because a bag that resets on load makes the ladder
    # infinite.
    "forge": forge.new_state(),
    "quests": quests.new_quest_state(),
    "world": progression.new_world_state(),
    dungeons.STATE_KEY: None,
    "dungeons_cleared": [],          # ours to write; progression.snapshot reads it
    "dungeon_map": {},               # dungeon id -> {room id: problem id}
    "class": {},                     # classes.new_state() at class choice
    "world_seed": 0,                 # the int, never the WorldSpec
    "legendaries": [],               # artifact ids owned
    "hand": legendaries.hand_ledger_new(),   # the Hand's ledger MUST persist
    "moveset": incantation.new_moveset(),
    "incantation": None,             # the live typed-Python battle, or None
    "exam": None,                    # the sealed practical, or None
    # The barrow's scene, held until the client has played it. It lives here
    # rather than inside the pets blob because pets.py owns the FACT and this
    # file owns the DELIVERY, and because a scene that is lost to a page refresh
    # is the one moment of this game that must not be.
    "pet_fall": None,
    # What this sitting has already covered. The selector reads it to bring a
    # family back inside the session; the SRS schedule still owns tomorrow.
    "session": {"started_at": 0.0, "log": []},

    # --- the ten systems' own sub-states ----------------------------------
    # Same arrangement as the block above: each module is ASKED for its shape
    # rather than having it copied here, so a module that grows a key does not
    # need this file edited. `_merge` deep-copies DEFAULT_STATE and folds the
    # save over the top, which means every one of these keys is back-filled on
    # load — a player mid-run gains them and loses nothing. All plain JSON.
    upkeep.UPKEEP_STATE_KEY: upkeep.new_state(),          # "upkeep"
    economy.ECONOMY_STATE_KEY: economy.new_state(),       # "economy"
    banter.STATE_KEY: banter.new_state(),                 # "banter"
    regalia.REGALIA_STATE_KEY: regalia.new_state(),       # "regalia"
    sanctuary.STATE_KEY: sanctuary.new_state(),           # "sanctuary"
    captives.STATE_KEY: captives.new_captive_state(),     # "captives"
    finale.STATE_KEY: finale.new_state(),                 # "finale"
    # THE SEAM BETWEEN THE TWO EXAMS — "ending". Which practical was the
    # story climax, whether it was passed, and whether the coda was watched.
    # BOOKKEEPING, NOT EVIDENCE: it gates nothing, and a save that loses it
    # replays a cutscene and is otherwise identical. `_merge` deep-copies
    # DEFAULT_STATE and folds the save over the top, so a save written before
    # this key existed gets ending.new_state() back-filled on load;
    # ending.ensure() fills any single key a newer build adds on every call.
    ending.STATE_KEY: ending.new_state(),                 # "ending"
    # THE NULL KING'S OWN LEDGER — "antagonist". What he has already said, so
    # he does not say it twice. He writes here and nowhere else, ever: no
    # mastery, no gold, no flag another system reads.
    antagonist.STATE_KEY: antagonist.new_state(),         # "antagonist"
    # sages.py ships new_state() and never named the key it belongs under —
    # the one module of the ten that did not. It is named here, once, so there
    # is still exactly one spelling of it in the codebase.
    SAGES_STATE_KEY: sages.new_state(),                   # "sages"
    arts.STATE_KEY: arts.new_state(),                     # "arts"
    # The movebook. `moveset` above is the book of LINES; this is the book of
    # MOVES those lines are spelled out of, and they are different books with
    # different limits — see movesets.new_book's note on why neither rations
    # the other.
    "movebook": movesets.new_book(),
    # THE HUNT, which is this file's own bookkeeping and not a module's.
    #
    # hunters.py ships a `Hunt` dataclass per region and deliberately no state
    # key: it declined to own the chase because `web/js/overworld.js` mirrors it
    # frame by frame and two sources of truth for a creature's position is how
    # the creature ends up in two places. So the engine holds the serialised
    # Hunt rows, one per region, and hunters.hunt_step remains the only thing
    # that advances one. `peak` is the readiness at the moment a fight STARTED,
    # frozen there, because the bounty is priced on how prepared you were when
    # you took the fight and not on what you put on afterwards.
    "hunters": {"regions": {}, "global_cooldown": 0.0, "kills": {},
                "trophies": [], "fight": None, "last_tick": 0.0},
}


class Game:
    def __init__(self, *, db_path=None, corpus_path=None, rebuild: bool = False):
        self.conn = db.connect(db_path)
        saves.ensure_schema(self.conn)          # named slots, autosave ring, undo
        self.corpus: list = ensure_corpus(corpus_path, rebuild=rebuild)
        self.by_id: dict = {p.id: p for p in self.corpus}
        # THE WALL. Everything that teaches selects from `self.teachable` and
        # never from `self.corpus`: Adventure selection, the SRS, dungeons,
        # daily quests, remediation, boss ladders. Filtering the hold-out out at
        # the end of a selection would work right up until the day somebody adds
        # a selector and forgets, so the hold-out is not in the list the
        # selectors are handed at all.
        self.teachable: list = corpusmod.teachable(self.corpus)
        self.holdout: list = corpusmod.sealed_pool(self.corpus)
        self.state = self._load_or_create()
        # Idempotent, and returns None when an anchor already exists. Without it
        # a death in the very first fight takes the fallback path and the player
        # wakes where they fell.
        death.ensure_wake_point(self.conn, self.state)
        self._rng = random.Random()
        # The world is rebuilt from its seed rather than serialised: the spec is
        # a frozen description and generate() is pure, so a save carries 4 bytes.
        # The manifest says generate(0) means "pick one"; it does not — seed 0 is
        # a real world, so every save would be the same one. The pick is made
        # here, once, and then persisted.
        self._reseed_world(self.state.get("world_seed") or 0)
        self._dungeons: dict = {}               # id -> built Dungeon, this process
        self._exam = None                       # the composed Exam, this process
        self._resolved_dungeon = None           # (Dungeon, run) for this encounter
        self._last_tick = time.time()
        self._open_session()
        self._sync_class_points()

    def _reseed_world(self, seed) -> None:
        seed = worldgen.parse_seed(seed) if seed else random.getrandbits(31) or 1
        self.world = worldgen.generate(seed)
        self.state["world_seed"] = self.world.seed
        self._dungeons = {}

    def new_world(self, seed=0) -> dict:
        """Reroll the world. The seed is shareable: the same code is the same
        geography, the same dungeons and the same boss affixes, for anyone.

        Sealed in a measured run: rerolling the geography under a running exam
        moves the ground the run was composed against."""
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        self._reseed_world(seed)
        self.save()
        return {"ok": True, "seed": worldgen.seed_text(self.world.seed),
                "card": worldgen.world_card(self.world)}

    def world_card(self) -> dict:
        return {"seed": worldgen.seed_text(self.world.seed),
                "card": worldgen.world_card(self.world),
                "first_hour": worldgen.first_hour(self.world)}

    # -- sessions and playtime ---------------------------------------------
    # story._STAT_LABELS exposes "Sessions" as a trigger dimension, and both of
    # these were declared and never written, so every beat keyed to them was
    # unreachable. A session is a launch, not a page refresh: reconnecting the
    # client inside the window continues the one already open.
    SESSION_GAP_SECONDS = 20 * 60
    # A gap longer than this is somebody making coffee, not somebody playing.
    PLAYTIME_MAX_GAP = 15 * 60

    def _open_session(self) -> None:
        # WHERE YOU ARE COUNTS AS SOMEWHERE YOU HAVE BEEN.
        #
        # `note_region` was wired into the two places the region CHANGES —
        # `Game.move` and `Game.travel` — and nowhere into the place it starts.
        # So a save's persisted arrival list never contained Python Village,
        # the village you have by definition stood in, and it never contained
        # wherever a loaded save was parked either. `story.build_context` hides
        # that by folding in the current region, so the story gates read
        # correctly; the two readers that take the stored list at its word do
        # not. antagonist.py counts it to decide how much of the map has been
        # walked and was permanently one short.
        #
        # Idempotent and free: note_region ignores a region it already has.
        storymod.note_region(self.state["story"],
                             self.state["player"]["region"])
        stats = self.state["stats"]
        now = time.time()
        if now - float(stats.get("session_started_at") or 0) > self.SESSION_GAP_SECONDS:
            stats["sessions"] = int(stats.get("sessions", 0)) + 1
            stats["armor_full_this_session"] = False
            # A new sitting starts with an empty board: yesterday's interleaving
            # is the spaced-repetition schedule's business, not the selector's.
            self.state["session"] = {"started_at": now, "log": []}
        stats["session_started_at"] = now
        self.save()

    def _tick_playtime(self) -> None:
        now = time.time()
        delta = now - self._last_tick
        self._last_tick = now
        if 0 < delta < self.PLAYTIME_MAX_GAP:
            self.state["player"]["playtime_seconds"] = round(
                float(self.state["player"].get("playtime_seconds") or 0.0) + delta, 2)

    def _sync_class_points(self) -> None:
        """classes.sync_points is the only granter and is idempotent, so calling
        it on every load and every level-up cannot double-grant."""
        cls = self.state.get("class") or {}
        if not cls.get("class"):
            return
        classes.sync_points(
            cls, level=int(self.state["player"]["level"]),
            chapters_graduated=classes.chapters_graduated(self.skills))

    # -- persistence -------------------------------------------------------
    def _load_or_create(self) -> dict:
        raw = db.load_state(self.conn)
        if raw is None:
            state = _deep_copy(DEFAULT_STATE)
            state["player"]["created_at"] = time.time()
            state["skills"] = {k: v.to_dict() for k, v in skillmod.new_skills().items()}
            state["story"] = storymod.new_story_state()
            self._migrate_pets(state, fresh=True)
            db.save_state(self.conn, state)
            return state
        # forward-compatible: fill in anything a newer build added
        merged = _deep_copy(DEFAULT_STATE)
        _merge(merged, raw)
        for name in skillmod.SKILLS:
            merged["skills"].setdefault(name, skillmod.SkillState(name=name).to_dict())
        if not merged.get("story"):
            merged["story"] = storymod.new_story_state()
        self._migrate_pets(merged, fresh=False,
                           legacy=("fallen" not in (raw.get("pets") or {})))
        return self._repair_blocks(merged)

    @staticmethod
    def _repair_blocks(state: dict) -> dict:
        """NOTHING IN THE ENDING IS ALLOWED TO REFUSE THE PRACTICAL, and this is
        that rule enforced at the doors every save comes through.

        `_merge` folds the save OVER the defaults and a non-dict incoming value
        wins outright, so a save carrying `"ending": null` — hand-edited,
        imported, or written by something that is not this game; `db` validates
        the envelope and not the type of each block — survives the merge as
        None. That used to be harmless bookkeeping. It is not any more:
        `_start_exam` calls `ending.clear_staging` on EVERY compose, so the next
        sitting of the practical would raise AttributeError inside
        `ending.ensure` and /api/exam/start would answer 500 — the measurement,
        refused, by the module whose whole contract is that it never refuses it.

        It repairs rather than refuses because the block is bookkeeping and
        nothing else: rebuilding it replays a cutscene and costs the player
        nothing. Both doors call this — `_load_or_create` for the save on disk
        and `_after_load` for a slot or an undo, which does its own `_merge` and
        would otherwise let the same null through.
        """
        if not isinstance(state.get(ending.STATE_KEY), dict):
            state[ending.STATE_KEY] = ending.new_state()
        return state

    def _migrate_pets(self, state: dict, *, fresh: bool,
                      legacy: bool = False) -> None:
        """The starter is not found, it is already there — and the barrow's debt
        has to be honest about saves that predate it.

        Two jobs, both of them once-only and both idempotent:

        1. GRANT THE STARTER. It walks with the player from the first encounter,
           so every save has it in `found`. Without this the map layer would
           advertise the animal already under the porch as something hiding in
           Python Village, and the tutorial would have no unasked help in it at
           all.

        2. SETTLE AN OLD DEBT. A save written before the fall existed can have
           the Half-Written Barrow already cleared. The scene must not replay —
           that player is not in that fight and has not been for weeks — but the
           legendary return is gated on `starter_fallen`, so leaving the debt
           unpaid would quietly make BARROW unreachable for everybody who played
           the chapter early. So the fall is recorded, and the scene is parked in
           `pet_fall` marked `retroactive` for the client to deliver once, as a
           thing that happened rather than a thing happening.
        """
        pet_state = state.setdefault("pets", pets.new_state())
        pet_state.setdefault("fallen", [])
        pet_state.setdefault("dismissed_at", {})
        pets.grant(pet_state, pets.STARTER_ID, at=time.time())
        # ACTIVE_LIMIT used to be two. A save that still lists two would show as
        # "in the field: one of one" while quietly contributing both animals'
        # passives, so the list is brought down to the limit here, keeping the
        # one the player chose first. Nothing is lost: `found` is untouched and
        # `recall` puts the other one straight back.
        active = [p for p in (pet_state.get("active") or [])
                  if p in pet_state.get("found", [])]
        if len(active) > pets.ACTIVE_LIMIT:
            for benched in active[pets.ACTIVE_LIMIT:]:
                pet_state.setdefault("dismissed_at", {})[benched] = 0.0
        pet_state["active"] = active[:pets.ACTIVE_LIMIT]
        if fresh or not legacy:
            return
        if pets.FALLS_AT_DUNGEON not in (state.get("dungeons_cleared") or []):
            return
        if pets.is_fallen(pet_state, pets.STARTER_ID):
            return
        scene = pets.fall(pet_state, at=time.time())
        if scene.get("fell"):
            scene["retroactive"] = True
            state["pet_fall"] = scene

    def save(self) -> None:
        self._tick_playtime()
        db.save_state(self.conn, self.state)

    # -- typed views over the raw state ------------------------------------
    @property
    def skills(self) -> dict:
        """The skill book, carrying where the diagnostic PLACED this player.

        The placement is a statement about the chapter ladder, not about
        mastery, so it rides alongside the mastery rather than being faked into
        it. Everything downstream — selection, the quest log, the world map —
        reads this one object, which is why the floor lives on it.
        """
        # THROUGH saves._skill_states, NOT SkillState(**data) DIRECTLY, and the
        # difference is whether the game starts.
        #
        # A raw splat trusts the save to have exactly today's fields. It does
        # not: a save written by a build with one extra column raises
        # `TypeError: SkillState.__init__() got an unexpected keyword argument`
        # at BOOT, before a screen is drawn, and the player sees a traceback
        # instead of a game. That is not hypothetical — it is in this machine's
        # own ~/Library/Logs/GauntletLegend/launch.log, from a bundle built
        # before `tier_clears` existed reading a save written after it.
        #
        # saves._skill_states already answers this properly: unknown keys are
        # dropped, a row that still will not build falls back to a fresh state
        # for that skill, and every missing skill is filled in. One loader, so
        # the two doors into a save cannot disagree about what a save is.
        book = skillmod.SkillBook(saves._skill_states(self.state))
        placement = (self.state.get("diagnostic") or {}).get("placement") or {}
        return book.with_floor(placement.get("chapter_index", 0))

    def _write_skills(self, skills: dict) -> None:
        self.state["skills"] = {k: v.to_dict() for k, v in skills.items()}

    @property
    def schedule(self) -> dict:
        return {key: srsmod.ScheduleEntry(**data)
                for key, data in self.state["schedule"].items()}

    def _write_schedule(self, schedule: dict) -> None:
        self.state["schedule"] = {k: v.to_dict() for k, v in schedule.items()}

    @property
    def encounter(self) -> Encounter | None:
        raw = self.state.get("encounter")
        if not raw:
            return None
        # Filtered rather than splatted whole. A save written by a build that
        # carried a field this one has dropped would otherwise raise on load,
        # mid-fight, with no way back into the game — and losing a run to a
        # field rename is the one thing a reload must never do. Missing fields
        # take their defaults, which is how the two counters added above arrive
        # in an encounter that was opened before they existed.
        return Encounter(**{k: v for k, v in raw.items() if k in _ENC_FIELDS})

    def _write_encounter(self, enc: Encounter | None) -> None:
        self.state["encounter"] = enc.to_dict() if enc else None

    # -- story -------------------------------------------------------------
    def story_context(self, *, readiness: dict | None = None,
                      events=()) -> dict:
        """build_context folds the whole engine state, so hand it the real thing
        rather than a reconstruction that could drift out of step."""
        merged = dict(self.state)
        merged["stats"] = {**self.state["stats"], **db.attempt_stats(self.conn)}
        return storymod.build_context(merged, self.skills, readiness=readiness,
                                      events=events)

    def collect_story(self, *, readiness: dict | None = None, events=()) -> list:
        """Fire every narrative beat whose trigger is now satisfied."""
        ctx = self.story_context(readiness=readiness, events=events)
        fired = []
        for entry in storymod.pending(ctx, self.state["story"]):
            # apply() MUTATES the story state and returns only the part of the
            # reward the engine has to pay. Titles, cards, codex entries, set
            # pieces, techniques and mentor favour are banked inside story itself.
            payable = storymod.apply(self.state["story"], entry)
            if not payable and entry["id"] not in self.state["story"].get("fired", []):
                continue                       # already shown on an earlier pass
            player = self.state["player"]
            if payable.get("xp"):
                player["xp"] += int(payable["xp"])
                player["level"] = world.level_for(player["xp"])
                player["title"] = world.title_for(player["level"])
            if payable.get("gold"):
                player["gold"] += int(payable["gold"])
            companion = payable.get("companion")
            if companion and companion not in self.state["companions"]:
                self.state["companions"].append(companion)
            consumable = payable.get("consumable")
            if consumable:
                self.state["consumables"][consumable] = \
                    self.state["consumables"].get(consumable, 0) + 1
            # keep the player-facing grimoire and codex in step with story's ledger
            for card in self.state["story"].get("cards", []):
                if card not in self.state["grimoire"]:
                    self.state["grimoire"].append(card)
            for note in self.state["story"].get("codex", []):
                if note not in self.state["codex"]:
                    self.state["codex"].append(note)
            entry["reward_summary"] = storymod.reward_summary(entry.get("reward") or {})
            fired.append(entry)
        return fired

    # -- build / loadout ---------------------------------------------------
    def effects(self, *, include_temp: bool = True) -> dict:
        enc = self.encounter
        temp = dict(enc.temp_effects) if (enc and include_temp) else {}
        base = items.total_effects(self.state["equipped"], self.state["attributes"], temp)
        # A forged blade folds in exactly like gear and for the same reason
        # artifacts do: forge.validate() keeps its fifty-four ids out of
        # items.BY_ID, so items.total_effects cannot see them.
        #
        # forge.effects_in() is the only isolation question this feature asks.
        # It is finalexam.sealed(enc, "BUILD") and nothing else, and it returns
        # EMPTY rather than reduced when the seal is up — a half-working
        # legendary is worse than an honest nothing. When the Editor Automaton
        # takes BUILD at rung eight of the boss ladder, the blade goes with it.
        # That is correct and is not special-cased here.
        blade_id = (self.state["equipped"] or {}).get("weapon", "")
        if blade_id in forge.RUNG_BY_ID:
            blade, rung = forge.RUNG_BY_ID[blade_id]
            for key, value in forge.effects_in(blade.id, rung.tier, enc).items():
                if key not in items.EFFECT_LABELS:
                    continue
                base[key] = (max(base.get(key, 0), value)
                             if key in items.SWITCH_KEYS
                             else base.get(key, 0) + value)
        # The temper, forge.WIRING §12. Tempered ARMOUR contributes resist_<el>
        # keys, which are already in items.EFFECT_LABELS and which
        # elements.armour_from_effects clamps at elements.RESIST_CAP — so they
        # are summed here and clamped exactly once, there. A tempered WEAPON
        # contributes nothing to this bag on purpose: its element is an argument
        # to elements.resolve_damage, read in _player_element, and a number with
        # two owners is a number that disagrees with itself.
        #
        # No seal test here. forge.effects_in() above already asked the one
        # isolation question for this feature, and a BUILD-sealed run is wearing
        # NO_ARMOUR anyway — elements.Defender.for_player drops the whole
        # profile rather than reducing it.
        if not finalexam.sealed(enc, "BUILD"):
            for key, value in forge.loadout_temper_effects(
                    self.state.get("forge") or {},
                    self.state["equipped"]).items():
                if key in items.EFFECT_LABELS:
                    base[key] = base.get(key, 0) + value

        # An equipped artifact folds in exactly like gear, with the same
        # max-not-sum rule for switches. items.total_effects cannot do it itself
        # because artifacts deliberately stay out of items.BY_ID (see _item).
        for item_id in (self.state["equipped"] or {}).values():
            artifact = legendaries.BY_ID.get(item_id)
            if artifact is None:
                continue
            for key, value in artifact.effects.items():
                if key not in items.EFFECT_LABELS:
                    continue
                base[key] = (max(base.get(key, 0), value)
                             if key in items.SWITCH_KEYS
                             else base.get(key, 0) + value)
        # mentor techniques are earned by demonstrated mastery, so they fold in
        # exactly like gear does — and obey the same rule about never answering
        earned = storymod.technique_effects(self.state["story"], self.story_context())
        for key, value in (earned or {}).items():
            if key in items.EFFECT_LABELS:
                base[key] = base.get(key, 0) + value

        mode = enc.mode if enc else config.MODE_ADVENTURE
        region_id = self.state["player"].get("region", "")
        # Companions contribute the BEST of each passive rather than the sum, and
        # they contribute through the same two gates every other kind of help
        # passes through, handed in rather than re-derived here:
        #
        #   THE SEAL. finalexam.sealed(enc, "PET") is the one authority on
        #   whether a companion exists in this encounter at all. Interview Mode
        #   was already covered, because pets.available_in refuses that mode on
        #   its own — but the boss that TAKES the companion is not Interview
        #   Mode, and without the seal the animal went on quietly paying out its
        #   probe charges and its rank grace for every rung after that one and
        #   for the final trial, to a player who had been told it was outside.
        #   A crutch the ladder has taken is taken, including the quiet half.
        #
        #   THE TIER. A passive that reads the room is help about this problem,
        #   so it sits under the same ladder the spoken line sits under. Economy
        #   passives are not gated: see pets.DEPTH_GATED_EFFECTS for which is
        #   which, and why a moving stamina cap would be the worse bug.
        if pets.available_in(mode, region_id,
                             sealed=finalexam.sealed(enc, "PET")):
            for key, value in pets.party_effects(
                    self.state["pets"].get("active", []),
                    self.state["pets"].get("bond", {}), mode=mode,
                    difficulty=self._companion_depth(enc)).items():
                if key in items.EFFECT_LABELS:
                    base[key] = max(base.get(key, 0), value)

        # A rebuilt town hall and a skill tree are both "build", which is what
        # the boss ladder takes away at rung 8 and the exam takes away entirely.
        if not finalexam.sealed(enc, "BUILD"):
            for key, value in quests.upgrade_effects(self.state).items():
                if key in items.EFFECT_LABELS:
                    base[key] = base.get(key, 0) + value
            for key, value in classes.tree_effects(self.state.get("class") or {}).items():
                if key not in items.EFFECT_LABELS:
                    continue
                base[key] = (max(base.get(key, 0), value)
                             if key in items.SWITCH_KEYS
                             else base.get(key, 0) + value)
        # Caps run LAST, on the merged total: an always-refunded probe is an
        # unlimited probe and a 100%-graced clock is not a clock.
        return classes.clamp(base)

    def _companion_depth(self, enc) -> str | None:
        """The depth a companion's passives are measured against, or None.

        None means "not inside an encounter", and outside an encounter nothing
        is gated: there is no room to read, and clipping a passive on the
        loadout screen would show the player a ceiling that is not the one they
        will fight with.

        The depth is the problem's OWN tier, with no boss lift — the same
        measure `_asked_depth` uses, and for the same reason written out there.
        A probe and a hint rung are both things the player goes and asks for, so
        they are measured the same way; what a boss takes away is decided once,
        in finalexam.BOSS_LADDER, and is already applied above.

        A mini-repo has no single problem tier to read, and no probes or hint
        tree to gate either, so it reads as ungated rather than as EASY.
        """
        if enc is None or getattr(enc, "repo_id", ""):
            return None
        problem = self.by_id.get(enc.problem_id)
        return pets.effective_difficulty(problem.difficulty) if problem else None

    def _sync_caps(self) -> None:
        """Equipment and attributes change the ceilings, never the current values
        downward past what the player already holds."""
        fx = self.effects(include_temp=False)
        player = self.state["player"]
        player["stamina_max"] = config.STAMINA_MAX + int(fx.get("stamina_max", 0))
        player["mana_max"] = config.MANA_MAX + int(fx.get("mana_max", 0))
        player["stamina"] = min(player["stamina"], player["stamina_max"])
        player["mana"] = min(player["mana"], player["mana_max"])

    def _pet_rows(self) -> list:
        """pets.catalogue() with THE WORN PIECE MERGED IN.

        petart.js has a complete regalia system — PET_REGALIA, petRegaliaFor(),
        wear(), REGALIA_SHAPES, thirty-one pieces — and until now nothing could
        reach it, because the worn piece never left the server. It lives in
        state["regalia"]["worn"] and travelled on exactly one route, /api/regalia,
        which the world screen does not fetch; the forty keys pets.catalogue()
        ships did not include it. So overworld.js had nothing to pass even once
        it learned to ask, and no companion in the field has ever worn anything.

        TWO ROSTERS, and they are worn differently. regalia.py's twenty-four are
        worn PER COMPANION — regalia.worn_by(state, pet_id) — and carry their own
        authored colour, which is the point of them: a jade collar is jade
        because regalia.py says so, not because the rarity ramp happened to land
        there. quests.py's seven are worn ONE AT A TIME by the party
        (REGALIA_ACTIVE_LIMIT is 1) and have no colour and no pet, so they are
        given to the ACTIVE companion only — putting the party's one collar on
        all twelve animals in the roster would be a different lie from the one
        being fixed. A quest piece sends no colour and petart falls back to the
        rarity accent, which is its documented behaviour for a piece that has
        none.
        """
        rows = pets.catalogue(self.state["pets"])
        worn_state = self.state.get(regalia.REGALIA_STATE_KEY)
        quest_piece = quests.worn_regalia(self.state["quests"]) or {}
        out = []
        for row in rows:
            piece_id = regalia.worn_by(worn_state, row["id"])
            colour = ""
            if piece_id:
                colour = getattr(regalia.BY_ID.get(piece_id), "colour", "") or ""
            elif row.get("active") and quest_piece.get("id"):
                piece_id = quest_piece["id"]
            out.append({**row, "regalia": piece_id, "regalia_colour": colour})
        return out

    def loadout(self) -> dict:
        """The kit screen. DEGRADE — docs/10-sealed-views.md §4.E.

        The swap test is no and the spend test is no: what you own does not
        move when the question does. The IN-FORCE test is yes, and that half is
        the whole finding. `_player_defender` hands `build_sealed=True` to
        elements during a measured run, so `effects`, `effect_text`, `armour`,
        `probe_charges` and `strike_element` are all numbers that are NOT in
        force while a run is open. Half this screen already knew — forge's
        contribution vanishes through `forge.effects_in` — and the other half
        did not, which made it internally inconsistent as well as wrong.
        A wrong number is worse than no number, because the player plans
        against it.

        So: keep everything that is WHAT YOU OWN, zero everything that is what
        it currently does for you, and say which. The same shape
        `regalia.view(sealed=True)` already returns.
        """
        suspended = bool(self._sealed_in_interview())
        fx = {} if suspended else self.effects(include_temp=False)
        equipped = {}
        for slot, item_id in self.state["equipped"].items():
            item = _item(item_id)
            if item:
                equipped[slot] = item.to_dict()
        owned = []
        for item_id in self.state["inventory"]:
            item = _item(item_id)
            if item:
                owned.append({**item.to_dict(),
                              "equipped": self.state["equipped"].get(item.slot) == item.id})
        consumables = [
            {"id": key, "count": count, **items.CONSUMABLES[key]}
            for key, count in self.state["consumables"].items()
            if count > 0 and key in items.CONSUMABLES
        ]
        return {
            "slots": items.SLOTS,
            "equipped": equipped,
            "inventory": owned,
            "consumables": consumables,
            "attributes": self.state["attributes"],
            "attribute_info": items.ATTRIBUTES,
            "unspent_points": self.state["unspent_points"],
            "build": self.state["build"],
            "builds": items.BUILDS,
            "sets": items.SETS,
            "active_sets": fx.get("_sets", []),
            "effects": {k: v for k, v in fx.items() if k != "_sets"},
            "effect_text": items.describe({k: v for k, v in fx.items() if k != "_sets"}),
            # Zero, not the base of one. Probes are a crutch with a rung on the
            # ladder and a measured run has none; quoting a charge the run
            # cannot spend is the in-force defect in miniature.
            "probe_charges": (0 if suspended else items.base_probe_charges(fx)),
            "secrets": [
                {**s, "found": s["id"] in self.state["secrets_found"]}
                for s in items.SECRETS
            ],
            "rarities": items.RARITIES,
            # THE RING, BESIDE THE SATCHEL. Not in `inventory` — see the note
            # above `items.keyring_rows`: a key is proved, not owned, so it has
            # no slot, no rarity and no drop rate, and it is drawn as its own
            # list rather than smuggled into the loot one.
            "keys": items.keyring_rows(self.state["cleared_bosses"]),
            "keys_held": len(world.keys_held(self.state["cleared_bosses"])),
            "keys_required": world.PORTAL_KEY_REQUIREMENT,
            # The belt, outside a fight. A player has to be able to see what is
            # in the pouch when deciding whether to walk into the marsh, not
            # only once the marsh has already poisoned them.
            "pouch": potions.pouch_view(self._pouch(),
                                        player=self.state["player"]),
            # The two jobs armour does, side by side and never blended into one
            # "defence" number — choosing between them IS the decision this
            # system exists to offer.
            "armour": items.armour_view(fx),
            # Through _player_element, not items.strike_element: the loadout
            # screen must name the same element the swing will actually use, and
            # a forged blade is invisible to the catalogue lookup. Under the
            # seal the swing has no element at all, and this says so.
            "strike_element": ("" if suspended else self._player_element()),
            "sealed": suspended,
            "suspended": (["effects", "effect_text", "armour", "probe_charges",
                           "strike_element"] if suspended else []),
            "seal_note": ("Your kit is yours and it is listed. None of it is in "
                          "force: a measured run is fought on the typing and "
                          "nothing else, so every number it would have added is "
                          "shown as zero rather than as a figure you would plan "
                          "against." if suspended else ""),
        }

    def choose_build(self, build_id: str) -> dict:
        spec = items.BUILDS.get(build_id)
        if not spec:
            return {"error": "unknown build"}
        if self.state["build"]:
            return {"error": "a path is already chosen; respec at the Armorer"}
        self.state["build"] = build_id
        for key, value in spec["starting"].items():
            self.state["attributes"][key] = self.state["attributes"].get(key, 0) + value
        # a starting kit so the loop has something to chew on immediately
        for item_id in ("rusty_blade", "training_vest", "worn_boots"):
            if item_id not in self.state["inventory"]:
                self.state["inventory"].append(item_id)
                self.state["equipped"][_item(item_id).slot] = item_id
        self.state["consumables"]["focus_elixir"] = \
            self.state["consumables"].get("focus_elixir", 0) + 2
        self.state["consumables"]["probe_scroll"] = \
            self.state["consumables"].get("probe_scroll", 0) + 1
        self.state["unspent_points"] += items.POINTS_PER_LEVEL
        self._sync_caps()
        self.save()
        return {"ok": True, "build": spec, "loadout": self.loadout()}

    def respec(self) -> dict:
        """The Armorer will unpick your attribute points for gold."""
        # THE WRITE CLAUSE, and it is asked at the door.
        #
        # A measured run moves nothing in the world in either direction. Every
        # sibling of this call already knew that — `buy_potion`, `forge_upgrade`,
        # `open_trial`, `spend_node`, `choose_class`, `class_respec` and
        # `set_active_pets` all refuse — and these were the ones nobody reached.
        # `_sealed_in_interview` is the question, because a run is open or it is
        # not and that does not depend on whether a question is on screen this
        # second. See `_sealed_for`.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        cost = 40 + 12 * sum(self.state["attributes"].values())
        if self.state["player"]["gold"] < cost:
            return {"error": f"the Armorer wants {cost} gold for that"}
        self.state["player"]["gold"] -= cost
        spent = sum(self.state["attributes"].values())
        self.state["attributes"] = {k: 0 for k in items.ATTRIBUTES}
        self.state["unspent_points"] += spent
        self._sync_caps()
        self.save()
        return {"ok": True, "points": self.state["unspent_points"], "cost": cost}

    def allocate(self, attribute: str, points: int = 1) -> dict:
        # Spends a point that `respec` charges gold to get back, so it is a
        # spend. Same door, same rule; see `respec`.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        if attribute not in items.ATTRIBUTES:
            return {"error": "unknown attribute"}
        points = max(1, min(points, self.state["unspent_points"]))
        if self.state["unspent_points"] < points:
            return {"error": "no unspent points"}
        self.state["attributes"][attribute] += points
        self.state["unspent_points"] -= points
        self._sync_caps()
        self.save()
        return {"ok": True, "attributes": self.state["attributes"],
                "unspent_points": self.state["unspent_points"],
                "effects": self.loadout()["effects"]}

    def equip(self, item_id: str) -> dict:
        # The build is suspended for the length of a measured run — `elements`
        # is handed `build_sealed=True` and `loadout()` marks the effects
        # suspended — so equipping mid-run cannot help with the question. It
        # can only leave the player convinced it did. `set_active_pets` is the
        # same shape and already refuses.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        item = _item(item_id)
        if not item or item_id not in self.state["inventory"]:
            return {"error": "you do not carry that"}
        class_id = (self.state.get("class") or {}).get("class", "")
        if class_id and not classes.equippable(item_id, class_id):
            return {"error": "not for your discipline",
                    "message": "%s is restricted to %s." % (
                        item.name, classes.restricted_to(item_id))}
        slot = item.slot
        # rings are interchangeable between the two ring slots
        if slot.startswith("ring"):
            if self.state["equipped"].get("ring1") in (None, item_id):
                slot = "ring1"
            elif self.state["equipped"].get("ring2") in (None, item_id):
                slot = "ring2"
            else:
                slot = "ring1"
        self.state["equipped"][slot] = item_id
        self._sync_caps()
        self.save()
        return {"ok": True, "slot": slot, "loadout": self.loadout()}

    def unequip(self, slot: str) -> dict:
        sealed = self._sealed_in_interview()          # see `equip`
        if sealed:
            return sealed
        self.state["equipped"].pop(slot, None)
        self._sync_caps()
        self.save()
        return {"ok": True, "loadout": self.loadout()}

    def use_consumable(self, key: str) -> dict:
        if self.state["consumables"].get(key, 0) <= 0:
            return {"error": "you have none of those"}
        spec = items.CONSUMABLES.get(key)
        if not spec:
            return {"error": "unknown item"}
        enc = self.encounter
        # The seal is checked BEFORE anything is applied. It used to sit below
        # the mana/stamina branch, so an Elixir of Focus worked mid-interview.
        if finalexam.sealed(enc, "ITEMS"):
            return finalexam.refuse("ITEMS")
        effect = dict(spec["effect"])
        player = self.state["player"]
        applied = []

        if "mana" in effect:
            player["mana"] = min(player["mana_max"], player["mana"] + effect.pop("mana"))
            applied.append("focus restored")
        if "stamina" in effect:
            player["stamina"] = min(player["stamina_max"],
                                    player["stamina"] + effect.pop("stamina"))
            applied.append("stamina restored")
        if effect:
            if enc is None:
                return {"error": "that one only works inside a battle"}
            for k, v in effect.items():
                enc.temp_effects[k] = enc.temp_effects.get(k, 0) + v
            applied.append("a charm settles over the battle")
            self._write_encounter(enc)

        self.state["consumables"][key] -= 1
        self.save()
        return {"ok": True, "name": spec["name"], "applied": applied,
                "mana": player["mana"], "stamina": player["stamina"],
                "probe_charges": self.probes_remaining()}

    # ======================================================================
    # The turn: elements, statuses, the pouch, and the enemy's half of it
    # ======================================================================
    #
    # THE RULE THAT OUTRANKS EVERYTHING IN THIS SECTION. The Python typing is
    # the attack. Every function below takes a number the typing already earned
    # and scales it; not one of them can generate a hit, end a fight, or be
    # substituted for a correct line. elements.resolve_damage takes `base` as an
    # argument and returns zero for zero, and a potion cannot be drunk INSTEAD
    # of casting — only alongside. What all of this decides is how LONG a fight
    # runs, which decides how many times the idiom gets typed, which is the only
    # pedagogical lever any of it has.

    def _region_element(self, problem: Problem | None = None) -> str:
        """The element of the ground this fight is standing on.

        The problem's realm wins, because a fight is fought where the problem
        lives rather than where the player's marker happens to be parked; the
        marker is the fallback. A dungeon is IN a region and `_metal_region`
        already reads its plan, so that is asked first of all.
        """
        run = self.state.get(dungeons.STATE_KEY)
        if run:
            plan = dungeons.DUNGEON_BY_ID.get(run.get("dungeon", ""))
            if plan is not None:
                return elements.affinity_for(plan.region)
        if problem is not None and problem.realm:
            return elements.affinity_for(problem.realm)
        return elements.affinity_for(self.state["player"].get("region", ""))

    def _player_element(self, enc: Encounter | None = None) -> str:
        """What the player's blow is made of.

        The weapon decides. A weapon out of a region with no weather leaves the
        question to whatever is walking beside you, which is the companion —
        elements.pet_element exists to answer exactly that and is the reason
        every one of the twelve animals has an element while five of the
        seventeen regions do not.

        A FORGED BLADE IS A WEAPON TOO, AND items.strike_element CANNOT SEE ONE.
        forge.validate() keeps the fifty-four rungs out of items.BY_ID on
        purpose, so the catalogue lookup inside strike_element returns None for
        every one of them and the blade struck NEUTRAL no matter what Vess made
        it out of. That quietly cost the whole forge loop its point — the
        element is stamped on the rung above precisely so that ember-metal
        carried home comes back as a blade that strikes with FIRE — and it took
        FIRE off the board entirely, because no catalogue weapon carries it and
        a forged one was the only way to hold it. Resolved here rather than by
        registering the rungs, which would break forge's own invariant.

        Order, and it matters: a temper OVERRIDES the metal the rung was made
        of, because tempering is the later and more deliberate act. That is
        forge.WIRING §12 — the weapon's element is read at the swing and never
        put in the effect bag, so there is one owner of the number.

        BUILD is the seal. When a measured run takes the loadout it takes the
        element with it, and the exam is fought on the typing and nothing else.
        """
        if finalexam.sealed(enc, "BUILD"):
            return elements.NEUTRAL
        companion = ""
        active = (self.state["pets"].get("active") or [])
        if active and not finalexam.sealed(enc, "PET"):
            pet = pets.BY_ID.get(active[0])
            companion = elements.pet_element(getattr(pet, "species", ""), active[0])
        equipped = self.state["equipped"] or {}
        weapon_id = equipped.get("weapon", "")
        tempered = forge.tempered_element(self._forge_state(), weapon_id)
        if tempered in elements.ELEMENTS:
            return tempered
        rung = FORGE_ITEMS.get(weapon_id)
        if rung is not None and rung.element in elements.ELEMENTS:
            return rung.element
        return items.strike_element(equipped, fallback=companion)

    # -- the pouch ---------------------------------------------------------
    def _pouch(self) -> potions.Pouch:
        return potions.Pouch.from_state(self.state)

    def _write_pouch(self, pouch: potions.Pouch) -> None:
        pouch.to_state(self.state)

    # -- statuses, as objects rather than as dicts -------------------------
    @staticmethod
    def _load_statuses(rows) -> list:
        """A saved status list, back as elements.StatusInstance.

        Tolerant by design: a save written by a build with a status this one has
        never heard of drops that entry rather than throwing. elements.tick_statuses
        does the same thing for the same reason.
        """
        out = []
        for row in rows or ():
            if not isinstance(row, dict) or row.get("id") not in elements.STATUSES:
                continue
            out.append(elements.StatusInstance.from_dict(row))
        return out

    @staticmethod
    def _dump_statuses(live) -> list:
        return [s.to_dict() for s in live or ()]

    def _player_defender(self, enc: Encounter | None,
                         statuses: list | None = None) -> elements.Defender:
        """The player, in the shape the damage function takes.

        `build_sealed` is handed in rather than re-derived inside elements.py:
        there is one isolation question in this game and it is finalexam.sealed.
        """
        sealed = finalexam.sealed(enc, "BUILD")
        return elements.Defender.for_player(
            self.state["player"], self.effects(),
            element=self._player_element(enc),
            statuses=statuses if statuses is not None else [],
            build_sealed=sealed)

    def _enemy_defender(self, enc: Encounter, statuses: list | None = None):
        vitals = enc.enemy_vitals or {}
        return elements.Defender(
            element=vitals.get("element", elements.NEUTRAL),
            armour=elements.NO_ARMOUR,
            statuses=statuses if statuses is not None else [],
            max_health=int(vitals.get("hp_max", 0) or 0))

    def _log(self, enc: Encounter, *lines) -> None:
        """One combat log, kept short. A battle that scrolls forever is a
        battle nobody reads the important line of."""
        for line in lines:
            if line:
                enc.combat_log.append(str(line))
        enc.combat_log[:] = enc.combat_log[-40:]

    # -- drinking ----------------------------------------------------------
    def use_potion(self, key: str) -> dict:
        """Drink one potion. THIS DOES NOT SPEND THE TURN.

        That sentence is the whole feature. A draught rides alongside the cast,
        so the player still has to type the line; if drinking were a turn, the
        optimal play would be drink-instead-of-think and the tactical layer
        would have eaten the lesson it exists to lengthen.

        The turn counter moves in `_advance_turn`, after a submission is graded,
        right or wrong. It does not move here, and nothing below writes it.
        """
        # The fight in progress owns the turn, the dose pool and the status
        # list, and there are two kinds of fight. Rather than two drink paths —
        # which is how two different rules about what a turn is end up in one
        # binary — the record is looked up here and the single call below reads
        # and writes whichever one it is.
        enc = self.encounter
        run = self.state.get(self.INCANT_STATE)
        if run:
            turn_state = potions.TurnState.from_dict(run.get("potion_turn"))
            poison = potions.Poison.from_dict(run.get("poison"))
            statuses = self._load_statuses(run.get("statuses"))
        else:
            turn_state = potions.TurnState.from_dict(enc.potion_turn if enc else None)
            poison = potions.Poison.from_dict(enc.poison if enc else None)
            statuses = self._load_statuses(enc.statuses if enc else [])
        pouch = self._pouch()
        result = potions.drink(
            pouch, key, player=self.state["player"], turn_state=turn_state,
            poison=poison, encounter=enc, statuses=statuses)
        if not result.get("ok"):
            return result
        self._write_pouch(pouch)
        if run:
            run["potion_turn"] = turn_state.to_dict()
            run["poison"] = poison.to_dict()
            run["statuses"] = self._dump_statuses(statuses)
            run["log"] = (list(run.get("log") or [])
                          + list(result.get("applied") or ()))[-40:]
        elif enc is not None:
            enc.potion_turn = turn_state.to_dict()
            enc.poison = poison.to_dict()
            enc.statuses = self._dump_statuses(statuses)
            self._log(enc, *(result.get("applied") or ()))
            self._write_encounter(enc)
        self.save()
        result["pouch"] = potions.pouch_view(
            pouch, player=self.state["player"], turn_state=turn_state,
            poison=poison, encounter=enc, statuses=statuses)
        result["statuses"] = self._dump_statuses(statuses)
        return result

    # -- the enemy's half --------------------------------------------------
    def _enemy_turn(self, enc: Encounter, *, base: int) -> dict:
        """The enemy acts once. Returns what the player should be shown.

        Order, and it matters:
          1. the enemy's own poison ticks, because a dose that would finish it
             finishes it before it gets to do anything about it;
          2. a monster carrying an antidote cures itself, AND THAT IS ITS TURN —
             poisoning something that can cure itself is therefore never wasted,
             it buys you a free turn, which is one more line of Python landed
             for nothing;
          3. otherwise it regenerates focus and may spend it on a special;
          4. the blow resolves through elements.resolve_damage, same function
             the player's blows go through, because two damage functions is how
             two different games end up in one binary.
        """
        vitals = enc.enemy_vitals or {}
        out: dict = {"acted": False, "damage": 0, "special": None,
                     "cured": None, "lines": [], "inflicted": ""}
        if not vitals:
            # A fight from a save written before the enemy had vitals, or from a
            # path that forgot to arm one. It still swings, for the plain amount
            # and with no element — because the alternative is that being wrong
            # silently becomes free, and a bug that makes the game easier is the
            # kind nobody reports.
            player = self.state["player"]
            hit = max(0, int(base))
            player["stamina"] = max(0, int(player["stamina"]) - hit)
            if hit:
                enc.hits_taken += 1
            out.update({"acted": True, "damage": hit})
            return out

        # 1 + 2: the enemy's own poison, then the vial.
        enemy_poison = potions.Poison.from_dict(enc.enemy_poison)
        enemy_statuses = self._load_statuses(enc.enemy_statuses)
        tick = elements.tick_statuses(enemy_statuses, int(vitals.get("hp_max", 1) or 1))
        dot = potions.poison_tick(enemy_poison)
        bleed = int(tick["damage"]) + int(dot["damage"])
        if bleed:
            vitals["hp"] = max(0, int(vitals.get("hp", 0)) - bleed)
        out["lines"] += list(tick["lines"])
        if dot["line"]:
            out["lines"].append(dot["line"])

        monster = {"hp": vitals.get("hp", 0), "hp_max": vitals.get("hp_max", 1),
                   "name": (enc.enemy or {}).get("name", "It"),
                   "antidotes": int(vitals.get("antidotes", 0) or 0)}
        cured = potions.monster_cure(monster, enemy_poison, rng=self._rng)
        vitals["antidotes"] = int(monster.get("antidotes", 0) or 0)
        enc.enemy_poison = enemy_poison.to_dict()
        enc.enemy_statuses = self._dump_statuses(enemy_statuses)
        if cured is not None:
            # It spent its turn drinking. It does not also get to swing.
            out.update({"acted": True, "cured": cured})
            out["lines"] += [cured["line"], cured["aside"]]
            return out

        # 3: focus, and what it buys.
        bestiary.regenerate(vitals)
        special = bestiary.take_turn(vitals, roll=self._rng.random())
        power = float(special["power"]) if special else 1.0
        # THE PHASE LADDER'S BLOW, and this is where "it gets stronger" stops
        # being a caption. `bestiary.buff_state` accumulates it a rung at a
        # time and `_arm_boss` puts it on the vitals; a boss with no ladder
        # under it has no `blow` key and multiplies by one, which is every
        # ordinary monster in the game, unchanged.
        power *= max(1.0, float(vitals.get("blow", 1.0) or 1.0))
        if special:
            out["special"] = special
            out["lines"].append(
                special["line"].format(who=(enc.enemy or {}).get("name", "It")))

        # 4: the blow. `base` is what the enemy's ordinary swing is worth and it
        # comes IN — this method does not decide how hard the game hits, it
        # decides what the wheel does to a number somebody else set.
        statuses = self._load_statuses(enc.statuses)
        defender = self._player_defender(enc, statuses)
        hit = elements.resolve_damage(
            max(0, int(round(base * power))),
            vitals.get("element", elements.NEUTRAL), defender,
            attacker_statuses=enemy_statuses,
            roll=self._rng.random(),
            build_sealed=finalexam.sealed(enc, "BUILD"))
        player = self.state["player"]
        player["stamina"] = max(0, int(player["stamina"]) - hit.damage)
        if hit.damage:
            # A blow that the wheel reduced to nothing is not a blow the kit
            # has to absorb, so it is not one the smith gets to bill for.
            enc.hits_taken += 1
        out["damage"] = hit.damage
        out["acted"] = True
        out["hit"] = hit.to_dict()
        out["lines"].append(hit.line)

        # The status the wheel says that hit carries, plus the one the special
        # names. `inflict` is the only thing that applies a status, and it is
        # called here rather than inside resolve_damage so a preview can ask
        # what a swing would do without it happening.
        #
        # POISON IS RECORDED IN EXACTLY ONE PLACE PER COMBATANT, and which place
        # depends on who has to read it. On the PLAYER it is the wheel —
        # elements.STATUSES["POISONED"] — because that is what ticks the status
        # bar and what potions.drink's `statuses` argument exists to clear. On a
        # MONSTER it is the dose pool, because potions.monster_cure is the
        # function that makes a monster drink and it takes a potions.Poison.
        # Writing both on the same combatant reads as one poisoning and bites
        # twice, which is what an earlier draft of this method did: three points
        # a turn off a twenty-point bar for a single hit, from two modules that
        # each believed they were the only one counting.
        # A CHARGED ATTACK STILL OBEYS THE WHEEL. elements.marks() is the one
        # owner of "hitting fire with fire does not set anything alight";
        # resolve_damage gets it out of INFLICT_CHANCE["SAME"] being zero, and
        # this path — which reads the status straight off the special — used to
        # be exempt. A fire monster in a fire region therefore burned a player
        # holding fire, for a tenth of the bar a tick, which is precisely the
        # consolation the shrug was supposed to be.
        # A BOSS ONLY LEAVES MARKS ONCE IT HAS CLIMBED TO LEAVING THEM.
        #
        # `bestiary.special_mark` is the one place the two halves of that meet:
        # SPECIALS says what each special inflicts, and the phase ladder says
        # whether this boss has reached the AFFLICTION rung yet. Reading
        # `special["inflicts"]` directly — which is what this loop did — handed
        # a phase-one boss a status it has not earned, which is the same defect
        # as the art never turning, one system over. An ordinary monster has no
        # fight and no ladder and is unchanged: `special_mark` is only asked
        # when there is a fight to ask it about.
        marks = (special or {}).get("inflicts", "")
        if special and enc.boss_id:
            boss_fight = self._boss_fight()
            if boss_fight and boss_fight.get("boss") == enc.boss_id:
                marks = bestiary.special_mark(boss_fight, special)
        for status_id in (hit.inflicted, marks):
            if not status_id or not elements.marks(hit.kind):
                continue
            landed = elements.inflict(statuses, status_id)
            if landed.get("applied"):
                out["inflicted"] = status_id
                out["lines"].append(landed["line"])
        enc.statuses = self._dump_statuses(statuses)
        return out

    def _open_player_turn(self, enc: Encounter) -> dict:
        """Start the player's turn: statuses tick, poison bites, focus returns.

        Called at the END of resolving the previous turn, which is the start of
        this one. That ordering is the whole reason a poisoned player finds out
        they are about to die while they still have a turn in which to drink
        something — and it is also why a dose cannot be rewound by a potion:
        the tick has already landed by the time the belt is drawn.
        """
        player = self.state["player"]
        statuses = self._load_statuses(enc.statuses)
        tick = elements.tick_statuses(statuses, int(player.get("stamina_max", 1) or 1))
        poison = potions.Poison.from_dict(enc.poison)
        dot = potions.poison_tick(poison)
        damage = int(tick["damage"]) + int(dot["damage"])
        if damage:
            player["stamina"] = max(0, int(player["stamina"]) - damage)
        # VOIDED stops focus COMING BACK. It never stops focus being SPENT,
        # because learning spells cost focus and a status that locked the hint
        # tree would be a status that could strand a learner.
        regained = 0
        if not tick["regen_blocked"]:
            before = int(player["mana"])
            player["mana"] = min(int(player["mana_max"]), before + FOCUS_PER_TURN)
            regained = int(player["mana"]) - before
        enc.statuses = self._dump_statuses(statuses)
        enc.poison = poison.to_dict()
        lines = list(tick["lines"]) + ([dot["line"]] if dot["line"] else [])
        self._log(enc, *lines)
        return {"damage": damage, "focus_regained": regained,
                "regen_blocked": bool(tick["regen_blocked"]),
                "statuses": enc.statuses, "poison": enc.poison, "lines": lines}

    def _advance_turn(self, enc: Encounter, *, correct: bool) -> dict:
        """A graded submission is a turn, right or wrong.

        A wrong cast costing the turn is already the rule everywhere else in
        this game — it is the Blitz rule bestiary.py names — and the pouch does
        not get to disagree with it. Without this call `drunk_this_turn` never
        clears and the second potion of a fight is refused forever.
        """
        turn_state = potions.TurnState.from_dict(enc.potion_turn)
        potions.cast_resolved(turn_state, correct=bool(correct))
        enc.potion_turn = turn_state.to_dict()
        enc.turn = int(turn_state.turn)
        return turn_state.to_dict()

    def probes_remaining(self) -> int:
        enc = self.encounter
        if not enc:
            return 0
        if finalexam.sealed(enc, "PROBES"):
            return 0
        fx = self.effects()
        if fx.get("probe_unbounded"):
            return 99            # an artifact, and the only thing that says this
        return max(0, items.base_probe_charges(fx) - enc.probes_used)

    def probe(self, args, expected, ops=None) -> dict:
        """Spend a charge to assert what the correct answer is on an input you choose."""
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if finalexam.sealed(enc, "PROBES"):
            return finalexam.refuse("PROBES")
        if enc.repo_id:
            # Not a seal: there is no single entry point to assert an answer
            # about. The suite is the probe, and it is free.
            return {"error": "a mini-repo cannot be probed",
                    "message": "There is no one function here to assert about. "
                               "Run the suite; it answers the same question and "
                               "costs nothing."}
        if self.probes_remaining() <= 0:
            return {"error": "no charges",
                    "message": "Out of probe charges. Raise LOGIC, wear Testsmith "
                               "pieces, or drink a Scroll of Probing."}
        problem = self.by_id[enc.problem_id]
        payload = {"ops": ops, "args": args} if ops else args
        result = tactics.run_probe(problem, payload, expected,
                                   effects=self.effects(),
                                   already_exposed=enc.exposed)
        enc.probes_used += 1
        self.state["stats"]["probes"] += 1
        if result.correct:
            self.state["stats"]["probes_correct"] += 1
            skills = self.skills
            # probing well IS testing skill; it is credited as such
            skillmod.apply_outcome(
                skills["TESTING"], solved=True, difficulty="TUTORIAL",
                hints_used=0, seconds=20, target_seconds=60, first_try=True,
                is_retest=False, mode=enc.mode)
            self._write_skills(skills)
        if result.weakness_hit and result.weakness not in enc.exposed:
            enc.exposed.append(result.weakness)
        enc.probe_log.append({"args": repr(args)[:120], "correct": result.correct,
                              "weakness": result.weakness})
        self._write_encounter(enc)
        self.save()
        enemy = self._enemy_for(problem, enc.exposed)
        return {
            **result.to_dict(),
            "charges_left": self.probes_remaining(),
            "enemy": enemy,
            "brief": tactics.tactical_brief(
                tactics.Enemy(**{k: v for k, v in enemy.items()
                                 if k in ("name", "sprite", "hp", "hp_max", "boss",
                                          "taunt", "colour", "difficulty",
                                          "weaknesses", "resistances", "exposed")}),
                enc.exposed),
        }

    # -- dashboard ---------------------------------------------------------
    # ======================================================================
    # The forge: metals, the blade, and Vess (forge.WIRING §4, §6, §7)
    # ======================================================================

    def _forge_state(self) -> dict:
        """The bag and the rungs. setdefault so a save written before the forge
        existed grows one rather than throwing on first read."""
        blob = self.state.get("forge")
        if not isinstance(blob, dict):
            blob = forge.new_state()
            self.state["forge"] = blob
        for key, default in forge.new_state().items():
            blob.setdefault(key, default)
        return blob

    def _blade_id(self) -> str:
        """The line this player's class owns, or empty for an unchosen class."""
        class_id = (self.state.get("class") or {}).get("class", "")
        blade = forge.blade_for_class(class_id)
        return blade.id if blade else ""

    def _hero_look(self) -> dict:
        """items.hero_look(), with the forged blade's own tint over the top.

        forge.WIRING §8: the catalogue derives a weapon's metal ramp from its
        rarity, which is right for found weapons and wrong for a blade whose
        whole point is that it changes colour nine times. sprites.js needs no
        edit either way — weaponRung() already honours `rung`.
        """
        look = items.hero_look(self.state["armor"], self.state["equipped"])
        equipped = self.state["equipped"] or {}
        weapon_id = equipped.get("weapon", "")
        if weapon_id in forge.RUNG_BY_ID:
            blade, rung = forge.RUNG_BY_ID[weapon_id]
            look["_weapon"] = forge.hero_weapon_look(blade.id, rung.tier)
            look["metal"] = look["_weapon"]["metal"]
            look["weapon"] = look["_weapon"]["key"]
            # The art pipeline wants the item, not the tint. lootart's
            # equippedHeroSprites(gear) draws the real rung in the hand; this is
            # the one slot that has anything to say.
            look["_gear"] = {"weapon": _forge_item_dict(weapon_id)}
        # THE CLASS THE PLAYER CHOSE, ON THE SPRITE THEY WALK AROUND IN.
        #
        # sprites.js has carried CLASS_RIG since §E landed and classKey() reads
        # `class_id || sprite`. This dict is the ONLY sprite-options payload the
        # client ever renders the hero from — dashboard() ships it as
        # `hero`, main.js hands it to Overworld.setEquipment and overworld.js
        # hands it to sprites.heroSprites — and it carried neither field, so
        # classKey() returned '' and all six classes drew one body. Proved on
        # the live app: after POST /api/class/choose the rendered frame was
        # byte-identical to the classless hero.
        #
        # No translation table: the six CharacterClass.sprite values in
        # classes.py are byte-identical to the six ids, and to HERO_CLASSES in
        # sprites.js. An unchosen class leaves the key off and falls back to the
        # generic hero, which is what it did before.
        #
        # THE BODY RIDES WITH IT. sprites.js BODY_RIG has carried two bodies
        # since §E and bodyKey() reads `body`, but nothing ever set it, so six
        # of the twelve authored sprites were unreachable from the game. It is
        # sent unconditionally, including for an unchosen class, because the
        # generic hero has a body too.
        look["body"] = classes.body_of(self.state)
        cls = (self.state.get("class") or {}).get("class", "")
        if cls:
            look["sprite"] = cls
        return look

    def forge_card(self) -> dict:
        """The at-a-glance panel: the blade, its rung, its technique, the bag,
        and what the next rung costs. This is the motivational point of the
        whole system, so it rides on /api/state rather than behind a click."""
        state = self._forge_state()
        blade_id = self._blade_id()
        bag = [{"metal": m.id, "name": m.name, "rung": m.rung,
                "colour": m.colour, "held": forge.held(state, m.id)}
               for m in forge.METALS]
        card = {
            "blade": blade_id,
            "tier": forge.owned_tier(state, blade_id) if blade_id else 0,
            "held_total": sum(row["held"] for row in bag),
            "bag": [row for row in bag if row["held"] > 0],
            "racked": state.get("racked", ""),
            "forged": int(state.get("forged", 0)),
            "smith": dict(forge.SMITH),
        }
        if not blade_id or not card["tier"]:
            return card
        blade = forge.BLADE_BY_ID[blade_id]
        rung = blade.rung(card["tier"])
        card["line"] = blade.line
        card["item"] = _forge_item_dict(rung.id)
        card["equipped"] = self.state["equipped"].get("weapon") == rung.id
        card["technique"] = {"name": blade.technique, "rank": rung.technique_rank,
                             "text": rung.technique_text,
                             "blurb": blade.technique_blurb}
        quote = forge.quote(state, blade_id, gold=int(self.state["player"]["gold"]))
        card["quote"] = quote
        card["ready"] = bool(quote.get("ready"))
        return card

    def smith(self, blade_id: str = "") -> dict:
        """Everything Vess's counter draws. She is not a mentor and is not in
        world.MENTORS: a mentor is a sealed capability and a blacksmith is not.
        """
        state = self._forge_state()
        class_id = (self.state.get("class") or {}).get("class", "")
        view = forge.smith_view(state, blade_id or self._blade_id(),
                                gold=int(self.state["player"]["gold"]),
                                class_id=class_id)
        chosen = view.get("blade", "")
        # Vess appends "The metal is fine" whenever gold is short, which is a
        # true sentence in the case she wrote it for and a flat contradiction
        # when the bag is short as well. The counter is composed here, so the
        # line is dropped rather than argued with; her own module is left alone.
        quote = view.get("quote") or {}
        if quote.get("short") and quote.get("gold_short"):
            view["lines"] = [line for line in view["lines"]
                             if line not in forge.SMITH_LINES["no_gold"]]
        view["gold"] = int(self.state["player"]["gold"])
        view["at_the_bench"] = (self.state["player"].get("region", "")
                                == forge.SMITH["region"])
        view["bench_region"] = forge.SMITH["region"]
        view["bench_region_name"] = world.REGION_BY_ID.get(
            forge.SMITH["region"], {}).get("name", "")
        view["route"] = forge.route_ahead(state, chosen) if chosen else []
        view["grind"] = forge.grind_estimate(chosen) if chosen else {}
        if chosen:
            tier = forge.owned_tier(state, chosen)
            view["tier"] = tier
            if tier:
                rung_id = forge.rung(chosen, tier).id
                view["item"] = _forge_item_dict(rung_id)
                view["equipped"] = self.state["equipped"].get("weapon") == rung_id
                nxt = forge.rung(chosen, tier + 1) if tier < forge.MAX_TIER else None
                view["next_item"] = _forge_item_dict(nxt.id) if nxt else None
            # Where the shortfall lives, per metal, so a refusal is a route
            # rather than a wall.
            view["counsel"] = [forge.counsel(mid) for mid in
                               (view.get("quote") or {}).get("short", {})]
        return view

    def forge_upgrade(self, blade_id: str = "") -> dict:
        """Take the metal, move the rung, pay the smith.

        forge.upgrade() does not touch the purse — it reports `gold_spent` and
        this is the one place that deducts it. Two owners of one number is how a
        purse goes negative.
        """
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        state = self._forge_state()
        blade_id = blade_id or self._blade_id()
        if not blade_id:
            return {"error": "no blade", **self.smith(blade_id)}
        # She works in one place. That is the loop the whole feature exists for:
        # walk out to where the metal is, carry it back to somebody who knows
        # what to do with it. Without this the town is decoration and the map is
        # a menu again. Reading the bench stays open from anywhere — knowing
        # what you are short of is the thing that gets a player walking.
        here = self.state["player"].get("region", "")
        if here != forge.SMITH["region"]:
            where = world.REGION_BY_ID.get(forge.SMITH["region"], {})
            return {"error": "away",
                    "message": f"{forge.SMITH['name'].title()} and her bench are "
                               f"in {where.get('name', 'the village')}. The metal "
                               f"does not work itself.",
                    "region": forge.SMITH["region"],
                    "region_name": where.get("name", ""),
                    "smith": self.smith(blade_id)}
        player = self.state["player"]
        result = forge.upgrade(state, blade_id, gold=int(player["gold"]))
        if result.get("error"):
            # Nothing was spent. forge.upgrade() checks the quote before it
            # touches the bag, so a refusal cannot have taken anything — but the
            # smith's screen is redrawn from the same state either way, so the
            # player can see that for themselves.
            return {**result, "smith": self.smith(blade_id)}
        # The quote already refused if the purse was short, so the subtraction
        # cannot go under. The floor is here anyway: "a purse never goes
        # negative" should be a property of the line that moves it, not of a
        # check somebody could later move or delete upstream.
        player["gold"] = max(0, int(player["gold"]) - int(result["gold_spent"]))

        # The object in the inventory becomes the object it was upgraded into.
        # The old rung is not kept: unlike items.UPGRADE_PATHS, which grants a
        # second object and leaves the first as a keepsake, a forged rung IS the
        # same blade — Vess worked the metal into it. There is nothing left to
        # keep.
        old_id = forge.rung(blade_id, result["tier"] - 1).id
        new_id = result["rung"]["id"]
        inventory = self.state["inventory"]
        if old_id in inventory:
            inventory[inventory.index(old_id)] = new_id
        elif new_id not in inventory:
            inventory.append(new_id)
        if self.state["equipped"].get("weapon") == old_id:
            self.state["equipped"]["weapon"] = new_id
        self._sync_caps()
        self.save()
        # `hero` is forge.upgrade()'s own key — the blade's _weapon dict — and
        # is left alone. The whole-sprite look goes under its own name.
        return {**result, "item": _forge_item_dict(new_id),
                "gold": int(player["gold"]),
                "hero_look": self._hero_look(),
                "technique_ladder": forge.technique_view(blade_id, result["tier"]),
                "smith": self.smith(blade_id)}

    def forge_rack(self, blade_id: str = "") -> dict:
        """Hang the blade on Vess's wall. The rung is kept — a forge does not
        un-forge anything — so trying a found weapon costs nothing but the rungs
        you did not forge while you were away."""
        # Asked at the door, like forge_upgrade and like every other overworld
        # action. Racking and unracking are BUILD changes — unrack equips the
        # blade and re-syncs the bars off it — so a measured run must not reach
        # either of them. server.py seals the route as well; that is a second
        # lock on the same door, not a second answer to the question, because
        # both of them are finalexam.sealed(enc, "BUILD") underneath.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        state = self._forge_state()
        blade_id = blade_id or self._blade_id()
        here = self.state["player"].get("region", "")
        if here != forge.SMITH["region"]:
            where = world.REGION_BY_ID.get(forge.SMITH["region"], {})
            return {"error": "away",
                    "message": f"The wall she would hang it on is in "
                               f"{where.get('name', 'the village')}.",
                    "smith": self.smith(blade_id)}
        result = forge.rack(state, blade_id)
        if result.get("error"):
            return result
        tier = forge.owned_tier(state, blade_id)
        if tier:
            rung_id = forge.rung(blade_id, tier).id
            if self.state["equipped"].get("weapon") == rung_id:
                self.state["equipped"].pop("weapon", None)
        self._sync_caps()
        self.save()
        return {**result, "smith": self.smith(blade_id)}

    def forge_unrack(self) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        state = self._forge_state()
        result = forge.unrack(state)
        blade_id = result.get("blade", "")
        tier = forge.owned_tier(state, blade_id) if blade_id else 0
        if tier:
            rung_id = forge.rung(blade_id, tier).id
            if rung_id not in self.state["inventory"]:
                self.state["inventory"].append(rung_id)
            self.state["equipped"]["weapon"] = rung_id
        self._sync_caps()
        self.save()
        return {**result, "smith": self.smith(blade_id)}

    def forge_technique(self, blade_id: str = "") -> dict:
        state = self._forge_state()
        blade_id = blade_id or self._blade_id()
        if not blade_id:
            return {"error": "no blade"}
        return forge.technique_view(blade_id, forge.owned_tier(state, blade_id))

    def forge_swap(self, blade_id: str = "") -> dict:
        state = self._forge_state()
        blade_id = blade_id or self._blade_id()
        tier = max(forge.MIN_TIER, forge.owned_tier(state, blade_id))
        return forge.swap_view(blade_id, tier) if blade_id else {}

    def _grant_blade(self) -> dict | None:
        """Rung one, handed over when the class is chosen. Idempotent, because a
        class quest finished twice by a save-file accident must not reset
        anybody's blade."""
        blade_id = self._blade_id()
        if not blade_id:
            return None
        state = self._forge_state()
        if forge.owned_tier(state, blade_id):
            return None
        forge.grant_blade(state, blade_id)
        rung_id = forge.rung(blade_id, forge.MIN_TIER).id
        if rung_id not in self.state["inventory"]:
            self.state["inventory"].append(rung_id)
        # The starting kit hands out a Rusty Blade before a class is chosen, so
        # the slot is normally full. A blade with the player's name on it takes
        # the slot from the starter and from nothing else — anything the player
        # went and found stays where they put it.
        held_weapon = self.state["equipped"].get("weapon", "")
        if not held_weapon or held_weapon == "rusty_blade":
            self.state["equipped"]["weapon"] = rung_id
        self._sync_caps()
        blade = forge.BLADE_BY_ID[blade_id]
        return {"blade": blade_id, "line": blade.line,
                "item": _forge_item_dict(rung_id),
                "technique": blade.technique,
                "lines": [forge.SMITH["greeting"],
                          f"That is a {blade.line}. Rung one of nine.",
                          blade.flavour]}

    def _metal_region(self) -> str:
        """Which region's metal this fight pays out.

        A dungeon is IN a region and the player's marker is normally standing in
        it, but the dungeon knows for certain and the marker is a cache. Read
        the plan when there is one.
        """
        run = self.state.get(dungeons.STATE_KEY)
        if run:
            plan = dungeons.DUNGEON_BY_ID.get(run.get("dungeon", ""))
            if plan is not None:
                return plan.region
        return self.state["player"].get("region", "")

    def _region_view(self, region_id: str) -> dict:
        """A region record with its sky on it.

        A COPY, always. `world.REGION_BY_ID` is module-level shared state and
        writing a `weather` key into it in place would hand every later caller
        in the process whatever the first caller's clock said.
        """
        base = world.REGION_BY_ID.get(region_id) or world.REGIONS[0]
        return {**base, "weather": weathermod.forecast(base["id"],
                                                       self.world.seed,
                                                       time.time())}

    def dashboard(self) -> dict:
        skills = self.skills
        now = time.time()
        for state in skills.values():
            skillmod.decay(state, now=now)
        self._write_skills(skills)

        player = self.state["player"]
        player["level"] = world.level_for(player["xp"])
        player["title"] = world.title_for(player["level"])
        into, need = world.xp_to_next(player["xp"])

        schedule = self.schedule
        stats = db.attempt_stats(self.conn)
        unaided_easy, unaided_medium = self._unaided_counts()
        ready = adaptive.readiness(skills=skills, schedule=schedule, stats=stats,
                                   unaided_easy=unaided_easy,
                                   unaided_medium=unaided_medium, now=now)
        cleared = set(self.state["cleared_bosses"])
        open_regions = world.unlocked_regions(skills, cleared, ready)
        castle = world.castle_requirements(skills, cleared, ready)
        due_now = srsmod.due(schedule, now=now, limit=25)

        self._refresh_daily(skills, schedule)
        self._sync_caps()
        self._sync_class_points()
        # Idempotent, and here rather than only at class choice so a save that
        # predates the forge — or one whose class was chosen by an older build —
        # still has a blade to bring to Vess. It returns immediately once the
        # line is owned.
        self._grant_blade()

        ctx = quests.context(self.story_context(readiness=ready), self.state)
        # Read once: `boss_fight` below is the ladder the player walked out of,
        # and asking for it twice is asking the save twice.
        open_fight = self._boss_fight()
        run = self.state.get(dungeons.STATE_KEY)
        dungeon_view = None
        if run:
            built = self._dungeon_for(run["dungeon"], run.get("seed"))
            dungeon_view = {**dungeons.progress(built, run),
                            "depth": self._dungeon_depth(built, run),
                            "options": dungeons.options(built, run),
                            "name": built.name}
        self.save()

        # One boss per region for the overworld marker. Six regions have none
        # and four have two; the FIRST row in world.BOSSES for a region is the
        # one whose key gates it, which is the one the marker stands for.
        region_boss: dict[str, dict] = {}
        for b in world.BOSSES:
            region_boss.setdefault(b["region"], b)

        return {
            "player": {**player, "xp_into_level": into, "xp_for_level": need},
            "skills": [
                {**s.to_dict(), "blurb": skillmod.STAGE_BLURB.get(s.stage, "")}
                for s in sorted(skills.values(), key=lambda s: -s.mastery)
            ],
            "armor": self.state["armor"],
            "weapons": self.state["weapons"],
            "companions": self.state["companions"],
            "achievements": self.state["achievements"],
            "cleared_bosses": self.state["cleared_bosses"],
            "readiness": ready,
            # THE SKY RIDES HERE. gauntlet/weather.py is the only thing in
            # the game that decides what the weather is, and this is the only
            # wire it travels down: both renderers already receive a region
            # record, so a `weather` key on it needs no new route, no new
            # fetch and no new client plumbing. It carries the condition now
            # AND the next two hours of it, so the client stays right as time
            # passes without asking again — see weather.strip().
            # THE BOSS MARKER'S SPRITE TRAVELS WITH THE REGION, for the same
            # reason `weather` does: the client already receives a region
            # record per region, and the overworld's boss marker had no way to
            # learn which creature it was standing for. It drew `m.boss ||
            # 'titan'` with nothing ever setting `m.boss`, so every region in
            # the game put a Hash Titan on its boss tile — including the Null
            # King's Castle, whose Interviewer has a 72x96 map form that no
            # player could ever have seen. Blank for the six regions that have
            # no boss; overworld.js keeps its own fallback for those.
            "regions": [
                {**r, "unlocked": r["id"] in open_regions,
                 "tier": world.town_tier(skills.get(r["skill"],
                                                    skillmod.SkillState(name="x")).mastery),
                 "boss_sprite": region_boss.get(r["id"], {}).get("sprite", ""),
                 "boss_colour": region_boss.get(r["id"], {}).get("colour", ""),
                 "weather": weathermod.forecast(r["id"], self.world.seed, now)}
                for r in world.REGIONS
            ],
            "bosses": [
                {**b, "cleared": b["id"] in self.state["cleared_bosses"],
                 "records": db.boss_history(self.conn, b["id"]),
                 # What this one is holding. Named on the dashboard so a boss
                 # has a reason to exist beyond XP before the player walks in.
                 "key": world.key_for_boss(b["id"])}
                for b in world.BOSSES
            ],
            # THE KEYRING, DERIVED. There is no state["keys"] on purpose:
            # `cleared_bosses` above IS the keyring, so every save that has ever
            # existed already holds exactly the keys its owner earned, a slot
            # round trip cannot lose one, and there is no second ledger to fall
            # out of step with the kill list.
            "keys": world.keyring(self.state["cleared_bosses"]),
            "keys_held": len(world.keys_held(self.state["cleared_bosses"])),
            "keys_required": world.PORTAL_KEY_REQUIREMENT,
            "portal": world.portal_status(self.state["cleared_bosses"]),
            # Said on the dashboard, next to the locked door, for the reason in
            # `practical_access`: the measurement is never behind the keys.
            "practical": self.practical_access(),
            # The open boss ladder, if the player walked out mid-fight. Four to
            # six graded solves is long enough that "where was I" is a question
            # the dashboard has to be able to answer.
            "boss_fight": bestiary.view(open_fight) if open_fight else None,
            "retests_due": [
                {"family": e.family, "days_overdue": round(srsmod.overdue_days(e, now=now), 1),
                 "stage": e.stage, "lapses": e.lapses}
                for e in due_now
            ],
            "daily": self.state["daily"],
            "weakness": skillmod.weakest(skills, limit=3),
            "stats": {**self.state["stats"], **stats},
            "settings": self.state["settings"],
            "corpus_size": len(self.corpus),
            "teachable_size": len(self.teachable),
            # The second number, beside the first and never folded into it.
            # readiness above is the RPG's measure of familiarity; this is the
            # measure of whether any of it transfers, and the UI is handed them
            # separately because they are separate claims.
            "transfer": self.transfer_report(),
            "grimoire": self.state["grimoire"],
            # Without the working tree. A Mini-Repo carries the player's files
            # on the encounter so a reload does not lose them, and echoing
            # several kilobytes of source on every state refresh is not what
            # this payload is for. `minirepo_view` is the door for the tree.
            "active_encounter": ({**self.state["encounter"], "repo_files": {}}
                                 if (self.state.get("encounter") or {}).get("repo_id")
                                 else self.state.get("encounter")),
            "interview": self.run_view(self.state.get("interview")),
            "loadout": self.loadout(),
            "unspent_points": self.state["unspent_points"],
            "build": self.state["build"],
            "secrets_found": self.state["secrets_found"],
            "castle": castle,
            "chapter": curriculum.next_objective(skills),
            "ladder": curriculum.ladder(skills),
            "quest_log": storymod.quest_log(
                self.story_context(readiness=ready), self.state["story"]),
            "honorific": storymod.honorific(self.state["story"]),
            "codex": self.state["codex"],
            "diagnostic_done": bool(self.state.get("diagnostic", {}).get("done")),

            # --- the eleven modules, reachable from the one screen the client
            # already refreshes. Everything below was written, self-checked and
            # unreferenced until now.
            "world": progression.world_map(self.state, skills, readiness=ready),
            "todo": progression.things_to_do(self.state, skills, readiness=ready,
                                             due_retests=len(due_now), limit=6),
            "quests": quests.board(ctx, self.state),
            "quest_next": quests.next_steps(ctx, self.state),
            "pets": self._pet_rows(),
            "pet_hints": pets.undiscovered_hints(self._pet_evidence(),
                                                 self.state["pets"]["found"]),
            "dungeon": dungeon_view,
            "dungeons": [self._dungeon_card(d) for d in
                         dungeons.dungeons_for_region(player.get("region", ""))],
            # Mini-Repo Battles: somebody else's codebase, on the same board as
            # everything else the player can choose to walk into.
            "mini_repos": self.minirepo_board(),
            "class": (classes.tree_view(self.state["class"],
                                        level=int(player["level"]))
                      if (self.state.get("class") or {}).get("class") else None),
            "class_selection": (classes.selection_screen()
                                if not (self.state.get("class") or {}).get("class")
                                else []),
            "legendaries": {"owned": list(self.state["legendaries"]),
                            "hand": legendaries.hand_summary(self.state["hand"])},
            "upgrades": items.upgrades_for(
                self.state["inventory"],
                {name: s.to_dict() for name, s in skills.items()},
                {**self.state["stats"], **stats}),
            "exam": {"ladder": finalexam.ladder_view(),
                     "format": finalexam.interview_format()},
            "seed": worldgen.seed_text(self.world.seed),
            "moveset": self.state["moveset"],
            # Cracked armour used to be a number nothing read. hero_look turns
            # integrity into what the player actually looks like on the map.
            "hero": self._hero_look(),
            # The blade, its rung, its technique, the metals held and what the
            # next rung costs. On /api/state rather than behind a click because
            # "it should be obvious at a glance what you are working toward" is
            # the entire motivational point of the system.
            "forge": self.forge_card(),
            "playtime": saves.format_playtime(
                float(player.get("playtime_seconds") or 0.0)),
        }

    def _dungeon_card(self, dungeon_id: str) -> dict:
        plan = dungeons.DUNGEON_BY_ID[dungeon_id]
        return {"id": plan.id, "name": plan.name, "region": plan.region,
                "chapter": plan.chapter, "tier": plan.tier,
                "archetype": plan.archetype, "rule": plan.rule,
                "floors": plan.floors, "blurb": plan.blurb, "lesson": plan.lesson,
                "cleared": dungeon_id in self.state["dungeons_cleared"]}

    # ======================================================================
    # The world layer's public surface. Each of these is a thin door onto a
    # module that already knows the rules; the engine's job here is to hold the
    # save, seal Interview Mode and pay out what the module says is owed.
    # ======================================================================

    def _readiness(self) -> dict:
        easy, medium = self._unaided_counts()
        return adaptive.readiness(skills=self.skills, schedule=self.schedule,
                                  stats=db.attempt_stats(self.conn),
                                  unaided_easy=easy, unaided_medium=medium)

    def _quest_ctx(self) -> dict:
        return quests.context(self.story_context(readiness=self._readiness()),
                              self.state)

    # -- the one question every one of the ten systems asks ----------------
    def _pays_into_the_world(self, enc: Encounter | None) -> bool:
        """May this encounter move gold, tack, trials, sanctuaries or sages.

        A measured run pays nothing into the world — that is the whole point of
        a measured run — and it is asked as a MODE question rather than as a
        capability question on purpose. `finalexam.sealed(enc, "BUILD")` is the
        right gate for the loadout (upkeep asks it, and so does elements), but
        it is also true of a hold-out problem served in Adventure Mode, and a
        hold-out clear is ordinary play that happens to be measured. Paying it
        nothing would make the transfer ladder a pay cut for taking it.
        """
        return getattr(enc, "mode", config.MODE_ADVENTURE) != config.MODE_INTERVIEW

    def _sealed_in_interview(self) -> dict | None:
        """One refusal for every overworld action. The modules refuse too, but
        the guarantee belongs at the door, not three rooms in."""
        if self._run_is_open():
            return finalexam.refuse("BUILD")
        return None

    def _run_is_open(self) -> bool:
        """Is a measured run open AT ALL, question on screen or not?"""
        return bool(self.state.get("interview")
                    or self.state.get("exam")
                    or (self.encounter
                        and self.encounter.mode == config.MODE_INTERVIEW))

    def _sealed_for(self, capability: str) -> bool:
        """`finalexam.sealed`, asked so that it cannot be answered by an
        encounter that is not there.

        THE HOLE THIS CLOSES, and it is the write clause rather than the view
        rule. `finalexam.sealed(encounter, capability)` is the one capability
        check and it is the right question — but it is asked OF AN ENCOUNTER,
        and BETWEEN TWO QUESTIONS OF A MEASURED RUN THERE IS NOT ONE. Every
        door that asked it with `self.encounter` therefore answered "not
        sealed" in the gap, and the town's doors are doors that pay:

            start_interview("FINAL_EXAM")      # no question open yet
            heal()                             # stamina 1 -> 20, free, mid-exam

        `Game._antagonist` already carries this exact paragraph and already
        fixes it, by asking `_sealed_in_interview` instead — the run is open or
        it is not, and that does not depend on whether a question happens to be
        on the screen this second. This is that fix, given a name, so the next
        door does not have to rediscover it.

        A run being open is sufficient. The capability ladder still decides
        everything else, so a hold-out problem served in Adventure Mode is
        untouched: `_pays_into_the_world` explains why that distinction has to
        survive, and it does.
        """
        return bool(self._run_is_open()
                    or finalexam.sealed(self.encounter, capability))

    # -- classes -----------------------------------------------------------
    def class_selection(self) -> dict:
        return {"selection": classes.selection_screen(),
                "chosen": (self.state.get("class") or {}).get("class", "")}

    def choose_class(self, class_id: str, body: str = "") -> dict:
        # The seal is asked FIRST. A refusal that names the player's build
        # state before it names the seal is a second answer to the same
        # question, and the answer in a measured run is always the seal.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        if (self.state.get("class") or {}).get("class"):
            return {"error": "a class is already chosen; respec at the Armorer"}
        if classes.get(class_id) is None:
            return {"error": "unknown class"}
        # The body is picked at the same door as the class, because the two
        # together are the sprite and there is no later screen that owns it.
        # An omitted or unknown value takes the default rather than refusing:
        # a client that has not been updated still gets a playable character.
        self.state["class"] = classes.new_state(
            class_id, body if body in classes.BODIES else classes.DEFAULT_BODY)
        # The movebook is stamped with the class it belongs to. It is a
        # DIFFERENT book from state["moveset"]: `moveset` rations LINES (four
        # slots at level one, eight at the ceiling) and the movebook rations
        # nothing, because a move you paid a skill point for is a move you own
        # and rationing the same thing twice would let a tree teach you
        # something you may not cast.
        self.state["movebook"] = movesets.new_book(class_id)
        self._sync_class_points()
        # The order issues you something with your name on it. Rung one of nine,
        # unequipped-slot-only, and Vess does the other eight.
        blade = self._grant_blade()
        self._sync_caps()
        self.save()
        return {"ok": True, "class": class_id, "blade": blade,
                "tree": classes.tree_view(self.state["class"],
                                          level=int(self.state["player"]["level"]))}

    def class_tree(self) -> dict:
        cls = self.state.get("class") or {}
        if not cls.get("class"):
            return {"error": "no class chosen", "selection": classes.selection_screen()}
        self._sync_class_points()
        return classes.tree_view(cls, level=int(self.state["player"]["level"]))

    def spend_node(self, node_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        cls = self.state.get("class") or {}
        if not cls.get("class"):
            return {"error": "no class chosen"}
        self._sync_class_points()
        result = classes.spend(cls, node_id, level=int(self.state["player"]["level"]))
        if "ok" in result:
            # THE ONLY WAY AN ORDINARY MOVE IS EVER ACQUIRED, and learning one
            # teaches the incantations it is spelled out of. One acquisition
            # path, not two, which is what quietly makes a class's tree decide
            # which idioms this playthrough is fluent in.
            #
            # `classes.moveset_for_node` — the integration note in movesets.py
            # calls it `moves_for_node`, which is not the name it shipped under.
            book = self.state.setdefault(
                "movebook", movesets.new_book(cls.get("class", "")))
            learned = []
            for move_id in classes.moveset_for_node(node_id):
                taught = movesets.learn(book, move_id, self.state["moveset"])
                if taught.get("learned"):
                    learned.append(taught)
            result["moves_learned"] = learned
            self._sync_caps()
            self.save()
            result["tree"] = classes.tree_view(
                cls, level=int(self.state["player"]["level"]))
        return result

    def class_respec(self, *, scope: str = "all", branch_id: str = "") -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        cls = self.state.get("class") or {}
        if not cls.get("class"):
            return {"error": "no class chosen"}
        quote = classes.respec_cost(cls, level=int(self.state["player"]["level"]),
                                    effects=self.effects(), scope=scope,
                                    branch_id=branch_id)
        result = classes.respec(cls, level=int(self.state["player"]["level"]),
                                gold_available=int(self.state["player"]["gold"]),
                                effects=self.effects(), scope=scope,
                                branch_id=branch_id)
        if result.get("ok"):
            self.state["player"]["gold"] -= int(result.get("gold", 0))
            self._sync_caps()
            self.save()
        return {**result, "quote": quote}

    def choose_dual(self, class_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        cls = self.state.get("class") or {}
        if not cls.get("class"):
            return {"error": "no class chosen"}
        result = classes.choose_dual(cls, class_id,
                                     level=int(self.state["player"]["level"]))
        if result.get("ok"):
            self.save()
        return result

    # -- quests ------------------------------------------------------------
    def quest_board(self, region_id: str = "") -> dict:
        ctx = self._quest_ctx()
        if region_id:
            return quests.region_board(region_id, ctx, self.state)
        return quests.board(ctx, self.state)

    def accept_quest(self, quest_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        result = quests.accept(self.state, quest_id, self._quest_ctx())
        self.save()
        return result

    def abandon_quest(self, quest_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        quests.abandon(self.state, quest_id)
        self.save()
        return {"ok": True}

    # -- ONE SETTLER FOR EVERY REWARD SHAPE IN THE GAME --------------------
    def _settle_pay(self, pay: dict, *, story: dict | None = None,
                    source: str = "quest", region_id: str = "",
                    tier: int = 0) -> dict:
        """Bank a reward bundle. Quests and rescues both come through here.

        captives.py's whole CONTRACT is that it emits nothing quests.py does not
        already emit, with identical shapes, precisely so that this method can be
        the only one that knows the vocabulary. Before this existed, the quest
        turn-in settled five of the nine keys and silently dropped the other
        four: `metal`, `potion`, `gear` and `vendor_credit` were authored, priced
        and summarised in the turn-in panel, and never actually given. That is
        the kind of bug a second settler guarantees and a single one cannot hide.

        Returns what was actually banked, so a caller has something to show.
        """
        player = self.state["player"]
        out: dict = {"xp": 0, "gold": 0, "items": [], "consumables": [],
                     "metal": None, "potion": None, "gear": "",
                     "vendor_credit": None, "rarity_floor":
                     pay.get("rarity_floor", "")}

        out["xp"] = int(pay.get("xp", 0))
        player["xp"] += out["xp"]

        # Gold goes through economy for the same reason the encounter does: the
        # rate has one owner. `quest_award` reads quests.REWARD_TIERS, so the
        # number is still the quest designer's; what economy adds is the ledger
        # entry, which is what the codex's lifetime earnings are read from.
        # THE PAY DICT IS THE AUTHORITY ON THE AMOUNT, not the tier. It is what
        # the turn-in panel already showed the player and what captives.py's
        # rescue lines were written against; economy is asked for the SOURCE and
        # the ledger entry, which is where the codex's lifetime figures come
        # from. A number the player has already been shown must not change on
        # its way into the purse.
        gold = int(pay.get("gold", 0))
        if gold:
            priced = (economy.quest_award(tier=tier, region_id=region_id)
                      if tier else economy.NOTHING)
            award = economy.Award(
                gold=gold, source=priced.source or "quest", base=priced.base,
                region_id=region_id, multipliers=dict(priced.multipliers),
                detail={**priced.detail, "settled_as": source})
            out["gold"] = economy.record(self.state, award)["gold"]
            player["gold"] += out["gold"]
            upkeep.record_income(self.state, out["gold"])
        player["level"] = world.level_for(player["xp"])
        player["title"] = world.title_for(player["level"])

        item_id = pay.get("set_item") or ""
        if item_id and _item(item_id) and item_id not in self.state["inventory"]:
            self.state["inventory"].append(item_id)
            self.state["stats"]["items_found"] += 1
            out["items"].append(item_id)

        consumable = pay.get("consumable")
        if consumable:
            key = consumable if isinstance(consumable, str) else consumable.get("id")
            count = 1 if isinstance(consumable, str) else int(
                consumable.get("count", 1))
            if key:
                self.state["consumables"][key] = \
                    self.state["consumables"].get(key, 0) + count
                out["consumables"].append({"id": key, "count": count})

        # -- the material layer, which nothing was paying ------------------
        metal = pay.get("metal")
        if metal and metal.get("id") in forge.METAL_BY_ID:
            forge.add_metal(self._forge_state(), metal["id"],
                            int(metal.get("count", 1)))
            out["metal"] = {"id": metal["id"], "count": int(metal.get("count", 1)),
                            "held": forge.held(self._forge_state(), metal["id"])}

        potion = pay.get("potion")
        if potion and potion.get("id") in potions.BY_ID:
            got = potions.grant(self.state, {"id": potion["id"],
                                             "count": int(potion.get("count", 1))})
            out["potion"] = {"id": potion["id"],
                             "count": int(potion.get("count", 1)), **got}

        gear = pay.get("gear") or ""
        if gear and _item(gear) and gear not in self.state["inventory"]:
            self.state["inventory"].append(gear)
            self.state["stats"]["items_found"] += 1
            out["gear"] = gear

        credit = pay.get("vendor_credit")
        if credit and credit.get("region"):
            # quests.py grants this and left the resolution open. It is
            # economy.grant_credit, and credit is spent before gold at that
            # region's vendor and nowhere else.
            banked = economy.grant_credit(self.state,
                                          credit["region"],
                                          int(credit.get("amount", 0)))
            out["vendor_credit"] = banked

        # -- the story bucket ----------------------------------------------
        reward_story = story or {}
        card = reward_story.get("card")
        if card and card not in self.state["grimoire"]:
            self.state["grimoire"].append(card)
        note = reward_story.get("codex")
        if note and note not in self.state["codex"]:
            self.state["codex"].append(note)
        if reward_story.get("title"):
            player["title"] = reward_story["title"]
        favor = reward_story.get("favor")
        if favor and favor.get("mentor"):
            # story.apply takes a whole BEAT, not a reward bucket, and a beat it
            # has already fired is a beat it refuses. The favour ledger is one
            # dict and this is the same arithmetic story.apply does to it —
            # written out rather than faked through a synthetic beat, because a
            # synthetic beat would end up in `fired` and suppress the real one.
            ledger = self.state["story"].setdefault("favor", {})
            ledger[favor["mentor"]] = int(
                ledger.get(favor["mentor"], 0)) + int(favor.get("amount", 0))
            out["favor"] = dict(favor)
        return out

    def turn_in_quest(self, quest_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        ctx = self._quest_ctx()
        if not quests.ready(quest_id, ctx, self.state):
            return {"error": "not finished",
                    "progress": quests.progress_of(quest_id, ctx, self.state)}
        done = quests.complete(self.state, quest_id)
        if not done:
            return {"error": "already turned in"}
        quest = quests.QUEST_BY_ID[quest_id]
        # The number is still quests.REWARD_TIERS'. economy.quest_award passes it
        # through untouched for a one-shot quest — which is every quest in this
        # game today — and the only thing routing it through buys is that when a
        # repeatable one is authored, the taper is already in the path rather
        # than needing to be remembered.
        settled = self._settle_pay(
            done.get("pay") or {}, story=done.get("story") or {},
            source="quest", region_id=quest.region,
            tier=int(done.get("tier", 0) or 0))
        player = self.state["player"]
        if done.get("chain_complete"):
            self.state["stats"]["chains_completed"] = int(
                self.state["stats"].get("chains_completed", 0)) + 1
        self._sync_caps()
        self.save()
        saves.autosave(self.conn, self.state, "quest_turned_in")
        return {"ok": True, **done, "settled": settled,
                "world": progression.advance(self.state, self.skills,
                                             readiness=self._readiness())}

    # ======================================================================
    # THE TOWN: the healer, the smith, and the honest shape of the loop
    # ======================================================================
    #
    # Health is free. Affliction removal is free. Reviving a fainted companion
    # is free. That is the most load-bearing decision in upkeep.py and it is not
    # a generosity: health gates ATTEMPTS, attempts are the entire mechanism by
    # which anybody gets better at this, and charging gold for healing builds a
    # difficulty curve that steepens exactly where it should flatten — on the
    # players who fail more, lose more stamina and earn less gold.
    #
    # The smith is where gold goes. Two poles, opposite sides of the square.

    def town(self) -> dict:
        """Everything the town square draws, in one call."""
        enc = self.encounter
        # `_sealed_for`, not `finalexam.sealed(enc, ...)`: between two questions
        # of a measured run there is no encounter to ask. See `_sealed_for`.
        sealed = self._sealed_for(upkeep.UPKEEP_CAPABILITY)
        gold = int(self.state["player"]["gold"])
        return {
            "visit": upkeep.town_visit(self.state, gold=gold, sealed=sealed),
            # The SAME seal the quote beside it gets. It was not being passed,
            # so this block quoted a mending bill two keys away from the door
            # that refuses to quote one. See upkeep.loop_report's docstring.
            "loop": upkeep.loop_report(self.state, sealed=sealed),
            "condition": upkeep.condition(self.state),
            "alarm": upkeep.alarm(self.state),
            "quote": upkeep.repair_quote(self.state, gold=gold, sealed=sealed),
            "healer": {"id": upkeep.DEFAULT_HEALER,
                       **{k: v for k, v in vars(upkeep.MENDER).items()
                          if k != "lines"}},
            "gold": gold,
            # WHERE THIS SQUARE IS. The town screen had no idea, which was fine
            # until something stood in exactly one of them.
            "region": self.state["player"].get("region", ""),
            # THE STANDING PORTAL, in the one square it stands in and null in
            # the other sixteen. Not sealed: it is what you have done and where
            # you may go, and the payload says in its own words that the
            # practical is not behind it. See `Game.portal`.
            "portal": (self.portal()
                       if self.state["player"].get("region", "")
                       == progression.PORTAL_REGION else None),
        }

    def heal(self) -> dict:
        """The Mender. Free, and she says so before you ask."""
        enc = self.encounter
        if self._sealed_for(upkeep.UPKEEP_CAPABILITY):
            return finalexam.refuse(upkeep.UPKEEP_CAPABILITY)
        statuses = list(enc.statuses) if enc else []
        out = upkeep.heal(self.state, statuses=statuses, sealed=False,
                          rng=self._rng)
        if enc is not None:
            enc.statuses = statuses
            self._write_encounter(enc)
        self.save()
        return out

    def repair_quote(self, piece: str = "") -> dict:
        enc = self.encounter
        return upkeep.repair_quote(
            self.state, piece, gold=int(self.state["player"]["gold"]),
            sealed=self._sealed_for(upkeep.UPKEEP_CAPABILITY))

    def repair(self, piece: str = "") -> dict:
        """Ferro. The purse is this file's, as always: upkeep REPORTS a spend."""
        enc = self.encounter
        if self._sealed_for(upkeep.UPKEEP_CAPABILITY):
            return finalexam.refuse(upkeep.UPKEEP_CAPABILITY)
        player = self.state["player"]
        out = upkeep.repair(self.state, piece, gold=int(player["gold"]),
                            sealed=False)
        spent = int(out.get("gold_spent", 0))
        if spent:
            # upkeep REPORTS the spend; the purse is this file's, same as
            # forge.upgrade(). economy.spend is the audit trail the codex's
            # lifetime figures are read from — it does not touch gold either.
            player["gold"] = max(0, int(player["gold"]) - spent)
            economy.spend(self.state, "repair", spent)
            self.state["stats"]["armor_repairs"] = int(
                self.state["stats"].get("armor_repairs", 0)) + 1
        self.save()
        return {**out, "gold": player["gold"]}

    # ======================================================================
    # THE SHOP AND THE BROKER
    # ======================================================================

    def shop(self, region_id: str = "") -> dict:
        """Seventeen vendors, one per region, each with its own shelf."""
        region_id = region_id or self.state["player"].get("region", "")
        return economy.vendor_view(self.state,
                                   region_id,
                                   gold=int(self.state["player"]["gold"]))

    def buy_potion(self, potion_id: str, *, region_id: str = "",
                   quantity: int = 1) -> dict:
        """The pouch is already filled when this returns. Subtract gold_spent
        only — `credit_spent` was banked by a quest and is already deducted."""
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        region_id = region_id or self.state["player"].get("region", "")
        player = self.state["player"]
        out = economy.buy_potion(self.state, region_id,
                                 potion_id, gold=int(player["gold"]),
                                 quantity=int(quantity))
        if out.get("error"):
            return out
        # `buy_potion` fills the pouch through potions.grant, which needs the
        # WHOLE save and not the economy block — see the call it makes.
        player["gold"] = max(0, int(player["gold"]) - int(out.get("gold_spent", 0)))
        self.save()
        return {**out, "gold": player["gold"]}

    def broker(self, region_id: str = "") -> dict:
        """The challenge broker's board. One trial open at a time, ever."""
        region_id = region_id or self.state["player"].get("region", "")
        econ = self.state
        return {**economy.broker_board(econ, region_id),
                "trial": economy.trial_state(econ),
                "gold": int(self.state["player"]["gold"])}

    def open_trial(self, form_id: str, *, region_id: str = "") -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        region_id = region_id or self.state["player"].get("region", "")
        out = economy.open_trial(self.state, region_id,
                                 form_id, now=time.time())
        self.save()
        return out

    def close_trial(self, *, abandon: bool = False) -> dict:
        """Settle the broker's contract exactly like any other award."""
        econ = self.state
        award = economy.close_trial(econ, abandon=bool(abandon))
        paid = economy.record(econ, award)["gold"]
        self.state["player"]["gold"] += paid
        if paid:
            upkeep.record_income(self.state, paid)
        self.save()
        return {"gold": paid, "award": award.to_dict(),
                "purse": int(self.state["player"]["gold"])}

    # ======================================================================
    # THE HIDDEN HEALERS
    # ======================================================================

    def sanctuary_view(self) -> dict:
        """The log page, plus whether one is urgent right now."""
        run = self.state.get(dungeons.STATE_KEY)
        built = self._dungeon_for(run["dungeon"], run.get("seed")) if run else None
        return {
            "journal": sanctuary.journal(self.state),
            "needed": sanctuary.needed_by(self.state),
            "marks": sanctuary.map_marks(self.state, built, run) if run else [],
        }

    def sanctuary_rest(self, sanctuary_id: str) -> dict:
        """Sit down. Free, for the same reason the Mender is free.

        Two deliberate side effects ride along and both are correct: the toll
        calls upkeep.wear_encounter, because a rest is another thing that
        happened away from town and the loop report should say so; and
        upkeep.heal revives a fainted companion, which is the whole point of a
        healer hidden where a fainted companion happens.
        """
        enc = self.encounter
        # `_sealed_for`: a sanctuary rest heals, and between two questions of a
        # measured run there is no encounter to ask the capability of.
        if self._sealed_for(upkeep.UPKEEP_CAPABILITY):
            return finalexam.refuse(upkeep.UPKEEP_CAPABILITY)
        statuses = list(enc.statuses) if enc else []
        out = sanctuary.rest(self.state, sanctuary_id,
                             run=self.state.get(dungeons.STATE_KEY),
                             statuses=statuses, sealed=False, rng=self._rng)
        if enc is not None:
            enc.statuses = statuses
            self._write_encounter(enc)
        self.save()
        return out

    # ======================================================================
    # THE TOWN'S FORTY-SEVEN VOICES
    # ======================================================================

    def town_talk(self, region_id: str = "") -> dict:
        """banter.view: everyone standing here, reading the room and your kit.

        A read plus a small write — the rotation advances so the same person
        does not open with the same sentence twice — so the save is written
        afterwards. The identity line stays quests.npc_line's; banter returns it
        under `identity` and it is rendered FIRST, then the composed lines.
        """
        payload = banter.view(self.state, region_id=region_id,
                              effects=self.effects(), encounter=self.encounter,
                              rng=self._rng)
        self.save()
        return payload

    def speak_to(self, npc_id: str) -> dict:
        """One speaker. Build the Ctx once per screen or the town disagrees with
        itself about the weather — which is why `town_talk` exists and this is
        for a second remark from somebody already on screen."""
        ctx = banter.context(self.state, effects=self.effects(),
                             encounter=self.encounter)
        said = banter.speak(npc_id, ctx,
                            state=self.state[banter.STATE_KEY], rng=self._rng)
        self.save()
        return {**said, "identity": banter.identity_line(npc_id, self.state)}

    # ======================================================================
    # REGALIA: twenty-four objects that buy MORE help, never DEEPER help
    # ======================================================================

    def regalia_view(self) -> dict:
        """The codex screen. Reads state; writes nothing about progression.

        The `also_` pair is the bridge described at `pet_intervention`: this
        screen shows the numbers that are ACTUALLY in force, which means it has
        to see quests.REGALIA's contribution too, through the same single floor
        and single ceiling.
        """
        pet_state = self.state["pets"]
        active = (pet_state.get("active") or [])
        pet_id = active[0] if active else ""
        gear = quests.regalia_effect(self.state["quests"])
        return regalia.view(
            self.state[regalia.REGALIA_STATE_KEY], pet_id=pet_id,
            bond=int((pet_state.get("bond") or {}).get(pet_id, 0)),
            region_id=self.state["player"].get("region", ""),
            pets_found=list(pet_state.get("found", [])),
            also_scale=gear["scale"], also_interventions=gear["interventions"])

    def wear_regalia(self, regalia_id: str) -> dict:
        """One object per companion. Passing "" takes it off, always allowed."""
        out = regalia.wear(self.state[regalia.REGALIA_STATE_KEY], regalia_id) \
            if regalia_id else regalia.take_off(
                self.state[regalia.REGALIA_STATE_KEY],
                (self.state["pets"].get("active") or [""])[0])
        self.save()
        return out

    # ======================================================================
    # THE SIXTEEN HIDDEN SAGES AND THE NINETY-SIX SECRET ARTS
    # ======================================================================
    #
    # THE OVERLAP, SETTLED. Both sages.py and arts.py authored ninety-six arts.
    # sages.py's own docstring settles it in arts.py's favour ON MEASUREMENT:
    # sixty-nine of its lines demand less Python than `sift`, an ordinary
    # chapter-two line the player already has, while arts.py's ninety-six clear
    # that same bar by 1.11x to 3.90x because they were authored against
    # `incantation.measure_complexity` — the function the damage actually calls.
    # arts.py's are also real Incantation and Move objects, so they are cast,
    # tiered, faded, grooved, drawn and recorded by machinery that already
    # exists rather than needing a second damage spine kept in step with the
    # first.
    #
    # So: sages.py owns WHO, WHERE and WHAT THE TRIAL IS. arts.py owns THE LINE.
    # `arts.taught_here(region, class_id)` is the bridge and `arts.sage_bridge()`
    # proves all ninety-six rooms map with nothing unmatched in either
    # direction. sages.moveset_requests() is NOT called from anywhere, which is
    # the one-line retirement its own docstring asks for.

    def _region_clears(self, region_id: str) -> int:
        return int((db.evidence_counters(self.conn).get("region_clears") or {})
                   .get(region_id, 0))

    def _class_id(self) -> str:
        return (self.state.get("class") or {}).get("class", "") or "analyst"

    def sage_board(self, region_id: str = "") -> dict:
        """Who is here, whether they will see you, and what is still owed.

        Shows a sage the player has not found as a SILHOUETTE with the deed
        spelled out, never as a grey wall: learning never dead-ends, and a
        condition you can read is a thing to go and do.
        """
        region_id = region_id or self.state["player"].get("region", "")
        enc = self.encounter
        sealed = finalexam.sealed(enc, sages.CAPABILITY)
        mode = getattr(enc, "mode", config.MODE_ADVENTURE)
        if not sages.available_in(mode, region_id, sealed=sealed):
            return {"sage": None, "region": region_id,
                    "available": False,
                    "reason": "sealed" if sealed else "nobody sits here"}
        sage = sages.for_region(region_id)
        state = self.state[SAGES_STATE_KEY]
        class_id = self._class_id()
        clears = self._region_clears(region_id)
        ok, why = sages.may_attempt(state, sage.id, clears)
        art = arts.taught_here(region_id, class_id)
        return {
            "region": region_id, "available": True,
            "sage": sage.id,
            "met": sages.has_met(state, sage.id),
            "progress": sages.discovery_progress(sage.id, self._pet_evidence()),
            "greeting": sages.greeting(sage.id, class_id, state),
            "may_attempt": ok, "why": why,
            "region_clears": clears,
            "gauntlet": sages.gauntlet(sage.id, class_id,
                                       attempt=int((state.get("attempts") or {})
                                                   .get(sage.id, 0))),
            # What is behind it, named but not given. `arts.taught_here` is the
            # bridge; the line itself is not rendered until it is taught.
            "art": ({"id": art.id, "name": art.name, "rung": art.rung,
                     "shape": art.shape, "known": arts.knows(
                         self.state[arts.STATE_KEY], art.id,
                         self.state["movebook"])}
                    if art is not None else None),
            "ladder": arts.ladder_view(self.state[arts.STATE_KEY], class_id,
                                       self.state["movebook"]),
        }

    def begin_gauntlet(self, region_id: str = "") -> dict:
        """Start or restart a trial, with its five problems BOUND to real ones.

        `sages.gauntlet()` returns SPECIFICATIONS — a pattern, a realm and a
        difficulty per rung — and `sages.resolve_gauntlet()` turns them into
        problem ids out of a corpus it is handed. The binding is banked here,
        because the rung is only cleared by clearing THAT problem and the engine
        is the only thing that can say whether that happened.

        A second attempt draws DIFFERENT problems from the same specifications,
        which is what stops a failed trial being farmed into a memorised
        sequence. `attempt` is what carries that, and it comes from the sage's
        own counter rather than from the caller.
        """
        region_id = region_id or self.state["player"].get("region", "")
        enc = self.encounter
        if finalexam.sealed(enc, sages.CAPABILITY):
            return finalexam.refuse(sages.CAPABILITY)
        sage = sages.for_region(region_id)
        if sage is None:
            return {"error": "nobody sits here"}
        state = self.state[SAGES_STATE_KEY]
        if not sages.has_met(state, sage.id):
            return {"error": "you have not found them yet"}
        class_id = self._class_id()
        plan = sages.begin(state, sage.id, class_id,
                           self._region_clears(region_id))
        if not plan.get("started"):
            self.save()
            return plan
        attempt = max(0, int((state.get("attempts") or {}).get(sage.id, 1)) - 1)
        resolved = sages.resolve_gauntlet(
            sage.id, class_id, problems=self.teachable, attempt=attempt,
            # Nothing the player has already cleared. A trial made of solved
            # problems is a trial that measures memory of this save file.
            exclude=set(self.state["solved_ids"]))
        bound = {row["key"]: row.get("problem", "")
                 for row in resolved.get("stages", []) if row.get("problem")}
        state["run"] = {"sage": sage.id, "class": class_id, "attempt": attempt,
                        "bound": bound, "at": time.time()}
        plan["stages"] = resolved.get("stages", plan.get("stages", []))
        plan["bound"] = bound
        # THE PRIZE, NAMED ONCE. `sages.begin` announces the art out of sages'
        # own RETIRED catalogue (`art_<region>_<class>`), and the art the
        # player is actually handed at the last rung is arts.py's
        # (`art_<class>_<region>`) — different id, different name. Unbridged,
        # the trial promised THE COUNTED WORD and paid out THE AVERAGE ALREADY
        # GUARDED. `gauntlet_stage` already corrects this on the way out; the
        # door has to say the same word as the till.
        taught = arts.taught_here(region_id, class_id)
        if taught is not None:
            plan["art"] = {
                "id": taught.id, "name": taught.name, "rung": taught.rung,
                "shape": taught.shape,
                "known": arts.knows(self.state[arts.STATE_KEY], taught.id,
                                    self.state["movebook"]),
            }
        self.save()
        return plan

    def gauntlet_encounter(self, stage_key: str) -> dict:
        """Open the rung's own problem, through the ordinary encounter door.

        It is an ordinary encounter in every respect — same sandbox, same
        grader, same mastery, same loot — because a trial that graded its own
        problems would be a second grading path, and there is one.
        """
        state = self.state[SAGES_STATE_KEY]
        run = state.get("run") or {}
        problem_id = (run.get("bound") or {}).get(stage_key, "")
        if not problem_id:
            return {"error": "no such rung in the open trial"}
        return self.start_encounter(problem_id, reason="SAGE")

    def gauntlet_stage(self, stage_key: str) -> dict:
        """One rung, resolved AGAINST THE RECORD rather than against a claim.

        This used to take `passed` as an argument, which meant a caller could
        hand itself a secret art by asserting it five times. Whether the rung
        was cleared is a fact the attempts table already holds: the rung's bound
        problem, solved, since this attempt began. Mastery moves only on graded
        evidence, and so does this.

        Failing costs THE TOLL and never a door. `sages.fail()` takes no
        mastery, no gold, no gear and no progress — three more encounters in
        this region before the sage will see you again, and the knowledge that
        they now know which rung you die on.
        """
        state = self.state[SAGES_STATE_KEY]
        run = state.get("run") or {}
        sage_id = run.get("sage", "")
        problem_id = (run.get("bound") or {}).get(stage_key, "")
        if not sage_id or not problem_id:
            return {"error": "no trial is open"}
        sage = sages.SAGE_BY_ID.get(sage_id)
        if sage is None:
            return {"error": "no trial is open"}
        since = float(run.get("at", 0.0))
        attempts = [row for row in db.attempts_for(self.conn, problem_id)
                    if float(row.get("created_at", 0.0)) >= since]
        if not attempts:
            return {"error": "that rung has not been attempted yet",
                    "problem": problem_id}
        passed = any(row["solved"] for row in attempts)
        class_id = run.get("class") or self._class_id()
        step = sages.record_stage(state, sage_id, stage_key, passed)
        if not step.get("ok"):
            return step
        if step.get("fail"):
            out = sages.fail(state, sage_id, stage_key,
                             self._region_clears(sage.region))
            state["run"] = None
            self.save()
            return {**step, **out}
        if step.get("cleared"):
            granted = sages.complete(state, sage_id, class_id, at=time.time())
            taught = self._teach_art(sage.region, class_id)
            state["run"] = None
            self.save()
            out = {**step, **granted, "art": taught}
            # sages.complete() reports an id out of its OWN retired catalogue
            # (`art_<region>_<class>`). The art the player actually walks away
            # with is arts.py's (`art_<class>_<region>`), because that is the
            # one that ships — see the note above `_region_clears`. Overwrite it
            # rather than send a client two ids for one thing.
            if taught.get("art"):
                out["art_id"] = taught["art"]
                out["art_name"] = taught.get("name", "")
            # `learn` is sages' handover kwargs for its own retired line. It
            # would construct, and constructing it would put a second, weaker
            # spelling of this art into the catalogue. Dropped here.
            out.pop("learn", None)
            return out
        self.save()
        return step

    def _teach_art(self, region_id: str, class_id: str) -> dict:
        """The one road into an art, and it runs through arts.grant.

        `grant` calls movesets.learn, which puts the ART MOVE in the movebook
        AND teaches the incantations its spine is spelled out of — the art's own
        line plus, for the wider shapes, the ordinary lines it is cast beside.
        One acquisition path, not two. Idempotent, because a re-attemptable
        gauntlet must be safe to re-clear.
        """
        art = arts.taught_here(region_id, class_id)
        if art is None:
            return {"taught": False, "reason": "no art is taught here"}
        return arts.grant(self.state[arts.STATE_KEY], self.state["movebook"],
                          art.id, moveset=self.state["moveset"], at=time.time())

    def art_book(self) -> dict:
        """What this playthrough knows, and how far the ladder still runs."""
        class_id = self._class_id()
        book = self.state["movebook"]
        return {
            "class": class_id,
            "ladder": arts.ladder_view(self.state[arts.STATE_KEY], class_id, book),
            "known": [a.id for a in arts.ARTS
                      if arts.knows(self.state[arts.STATE_KEY], a.id, book)],
            "sanctums": [s.to_dict() for s in
                         arts.cleared_sanctums(self.state[arts.STATE_KEY])],
            "moves": [m.id for m in movesets.known(book)],
        }

    # ======================================================================
    # THE PEOPLE THE BOSSES TOOK
    # ======================================================================

    def roll_call(self) -> dict:
        """A list that grows, with faces and trades on it, and watching it grow
        is most of the point. `still_held` is handed over with it deliberately:
        the ending is a eucatastrophe and not a restoration, and a roll call
        that quietly rounded up would be this game telling a lie about itself."""
        return {
            "freed": captives.roll_call(self.state),
            "by_region": captives.roll_call_by_region(self.state),
            # `still_held` hands back Captive DATACLASSES, where `roll_call`
            # hands back rows — so this payload used to be un-serialisable and
            # /api/rollcall answered 500. Rendered through captives' own
            # row-builder rather than a second spelling of it here: `_view` is
            # `asdict` plus `held_in` and `home_name`, it trims nothing, and
            # the two halves of the list now have the same shape, which is what
            # a client that draws both of them needs.
            "still_held": [captives._view(person)
                           for person in captives.still_held(self.state)],
            # THE THIRD LIST, which `still_held` already subtracts and which
            # used to have no route to a client at all. On the ordinary
            # fourteen-key playthrough everybody is carried out by hand and this
            # is empty, which is why it was invisible; on a save where the two
            # lists disagree — the index fell on people no boss of this run ever
            # held — the payload used to hand over `freed: 0, still_held: 0,
            # total: 25` and the screen printed a lie about its own roll call.
            # Same row shape as the other two, plus `released_line`, so the
            # renderer can stage it as what it was and not as a rescue.
            "released": captives.release_roll(self.state),
            "released_count": len(captives.released(self.state)),
            "index_collapsed": captives.index_collapsed(self.state),
            "boons": captives.boons(self.state),
            "routes": captives.open_routes(self.state),
            "changes": captives.village_changes(self.state),
            "total": len(captives.CAPTIVES),
        }

    # ======================================================================
    # THE STANDING PORTAL, AND THE ONE THING IT MUST NEVER STAND IN FRONT OF
    # ======================================================================
    #
    # THE PORTAL GATES THE STORY CLIMAX. Fourteen bosses, fourteen keys, one
    # door frame in the village square the player walked past on their first
    # morning. Behind it is the room under the castle, the mythic python wizard
    # standing in it, the captives, the cutscene and the ending.
    #
    # THE PORTAL NEVER GATES THE PRACTICAL. Interview Mode is a MEASUREMENT and
    # not a reward. A player must be able to sit it AT ANY TIME, from the menu,
    # at level one, holding nothing, to find out where they stand — that is the
    # entire point of this game. Gating the measurement behind fourteen boss
    # kills would make the one honest number in it something you have to earn
    # twice.
    #
    # Those two paragraphs are not a convention here. They are
    # `world.portal_gates()` and `progression.portal_blocks()`, which answer
    # False for every measured thing forever and are checked by tests rather
    # than trusted. `start_interview` below reads neither the keyring nor the
    # portal, and `practical_access()` exists so a screen can SAY so instead of
    # a player having to infer it from the absence of a lock.

    def portal(self) -> dict:
        """The portal panel: fourteen wards, which are lit, and who has the rest.

        Checked against docs/10-sealed-views.md: WORLD, and open during a
        measured run. The swap test is no — it does not move when the question
        on the screen does. The in-force test is no — a key is derived from
        `cleared_bosses`, which no seal suspends. The spend test is no — it
        names bosses and roads, never a problem.
        """
        prog = progression.snapshot(self.state, self.skills,
                                    readiness=self._readiness())
        view = progression.portal_view(prog)
        view["practical"] = self.practical_access()
        return view

    def practical_access(self) -> dict:
        """Whether the practical is reachable, and the honest answer is: always.

        This method returns a constant on purpose. It exists so the portal
        screen, the keyring and the menu can all print the same sentence from
        the same place, and so that anybody who later adds a condition has to
        delete a docstring that tells them not to.
        """
        return {
            # finalexam owns the sentence, because finalexam owns the exam. One
            # source, so the menu, the portal panel and the keyring cannot
            # drift into three different descriptions of the same open door.
            **finalexam.practical_gate(),
            "requires_keys": False,
            "keys_held": len(world.keys_held(self.state["cleared_bosses"])),
            "format": "FINAL_EXAM",
            "where": "From the menu. Interview Mode, at any time.",
            "gated_by_portal": world.portal_gates("practical"),   # False, forever
        }

    def enter_portal(self) -> dict:
        """Step through, or be told exactly which wards are dark.

        A refusal here is never a dead end. It names the bosses still holding
        keys, and it says in the same breath that the practical is reachable
        right now with none of them — because the one thing a locked door in
        this game must never do is make a player think the measurement is
        behind it.
        """
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        prog = progression.snapshot(self.state, self.skills,
                                    readiness=self._readiness())
        view = progression.portal_view(prog)
        view["practical"] = self.practical_access()
        if not progression.portal_open(prog):
            return {
                "ok": False, "open": False, "portal": view,
                "error": "the wards are not answered",
                "message": view.get("line", ""),
                "missing": view.get("missing", []),
                # Said on the refusal, not in a menu somewhere else.
                "practical": view["practical"],
            }
        # Open. `ev_portal_opens` is a WORLD EVENT and progression.advance is
        # the only thing that fires one — this method does not get a second
        # opinion about the ledger, it just runs the settle and reports whether
        # this was the pass that lit it.
        before = set((self.state.get("world") or {}).get("events_fired") or ())
        announcements = progression.advance(self.state, self.skills,
                                            readiness=self._readiness())
        after = set((self.state.get("world") or {}).get("events_fired") or ())
        fired = "ev_portal_opens" in (after - before)
        room = {
            "ok": True, "open": True, "portal": view,
            "trial": dict(world.FINAL_TRIAL),
            "examiner": finalexam.examiner_view(),
            "gates": list(world.PORTAL_GATES),
            "never_gates": list(world.PORTAL_NEVER_GATES),
            "practical": view["practical"],
            "first_time": bool(fired),
            "watching": self._antagonist(antagonist.PORTAL_OPENED) or None,
            "world": announcements,
            "message": world.THE_STANDING_PORTAL["open_line"],
            # The room is open; the fight in it has not started. `start_here`
            # is the route that starts it AS THE STORY — the only staged route
            # there is — and it is named in the payload so the client does not
            # have to know a second way in. `two_exams` travels with it so the
            # screen that offers the last fight is also the screen that says
            # what makes it different from the practice one.
            "trial_route": "/api/portal/trial",
            "ending": ending.status(
                self.state, cleared_bosses=self.state["cleared_bosses"]),
            "two_exams": ending.TWO_EXAMS,
        }
        self.save()
        return room

    # ======================================================================
    # THE LAST SCENE
    # ======================================================================

    def finale_scene(self, *, exam_report: dict | None = None) -> dict:
        """Staged AFTER the practical is scored, and never before.

        The direction of the gate, said once: the practical gates the finale and
        the finale does not gate the practical. A player who freed nobody sits
        the same sealed, timed, unassisted exam and can pass it.
        """
        enc = self.encounter
        ready = self._readiness()
        scene = finale.view(
            self.state,
            freed=captives.freed(self.state),
            exam_report=exam_report,
            readiness=ready,
            transfer_summary=self.transfer_report(),
            cleared_bosses=list(self.state["cleared_bosses"]),
            names=self._identifiers_named(),
            total_captives=len(captives.CAPTIVES),
            encounter=enc)
        self.save()
        return scene

    def _identifiers_named(self) -> list:
        """The player's own variable names, newest first, for the name rail.

        THREE RULES and the second is this method's job: identifiers only
        (finale.clean_names enforces it with a regex, so no code fragment can
        reach the screen by accident); NOTHING FROM A HOLD-OUT PROBLEM, because
        the rail is decoration and the hold-out is a measurement; and names the
        player did not choose are dropped by finale itself.
        """
        import re as _re
        sealed_ids = {row["problem_id"] for row in
                      self.conn.execute("SELECT problem_id FROM "
                                        "transfer_encounters").fetchall()}
        names: list = []
        for row in db.recent_attempts(self.conn, limit=60):
            if not row["solved"] or row["problem_id"] in sealed_ids:
                continue
            for token in _re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b",
                                     row["submitted_code"] or ""):
                if token not in names:
                    names.append(token)
        return names[:40]

    def mark_coda_seen(self) -> dict:
        """On `the_prompt_stays`, not on the freeze frame. The two halves of
        this ending are separate and a player who walked out at the title card
        has seen half of it."""
        # Through ending.py, which marks its own half and then calls
        # finale.mark_coda_seen for the other: "the_prompt_stays" on a pass and
        # "the_prompt_waits" on a failure are the same beat of the same ending,
        # and only one of them is a finale scene.
        out = ending.mark_coda_seen(self.state)
        self.save()
        return dict(out)

    # -- companions --------------------------------------------------------
    def pet_catalogue(self) -> dict:
        """The companion screen: the roster, the ladder it is ranked against,
        and whichever depth the player currently has no answer for."""
        pet_state = self.state["pets"]
        return {"pets": pets.catalogue(pet_state),
                "hints": pets.undiscovered_hints(self._pet_evidence(),
                                                 pet_state["found"]),
                "limit": pets.ACTIVE_LIMIT,
                "tiers": pets.tier_table(),
                "active": pets.active_id(pet_state),
                "fallen": list(pet_state.get("fallen") or []),
                "keepsake": pets.KEEPSAKE,
                # The scene, if the client has not played it yet. Handed back
                # here as well as on the clear that caused it, so a reload
                # between the two does not swallow the one moment that matters.
                "fall": self.state.get("pet_fall")}

    def set_active_pets(self, pet_ids: list) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return finalexam.refuse("PET")
        chosen = pets.set_active(self.state["pets"], pet_ids or [])
        self.save()
        return {"ok": True, "active": chosen}

    def pet_intervention(self, signals: dict | None = None) -> dict | None:
        """Called as the player works. On a hit the engine charges it exactly the
        way use_hint charges — one hint used, and the rank clamped.

        Two shapes come back and they are told apart by `refused`. A HINT is
        charged. A REFUSAL — the companion is below the depth of this encounter —
        costs nothing, clamps nothing, and carries the route out instead, which
        is the whole of the no-dead-end guarantee arriving at the moment the
        player learns their animal is the wrong animal.
        """
        enc = self.encounter
        if not enc:
            return None
        region_id = self.state["player"].get("region", "")
        # ONE isolation path. finalexam.sealed is the authority and pets takes
        # its verdict as an argument rather than forming a second opinion.
        sealed = finalexam.sealed(enc, "PET")
        if not pets.available_in(enc.mode, region_id, sealed=sealed):
            return None
        repo = self._repo_of(enc)
        problem = repo_problem(repo) if repo else self.by_id[enc.problem_id]
        spoken = dict(enc.pet_spoken or {})
        # -- THE REGALIA COLLISION, RESOLVED IN ONE PLACE -------------------
        #
        # There are two bodies of tack in this codebase and they are different
        # objects with the same name. `quests.REGALIA` is seven REGION-keyed
        # pieces, quest-awarded and priced by economy.py. `regalia.REGALIA` is
        # twenty-four COMPANION-keyed objects — the jade collar, the mystic
        # scarf — earned by a deed and deliberately unpriced. Both were authored
        # independently, both chose the SAME two levers (how soon the companion
        # speaks and how often), and by coincidence both chose the same floor
        # (0.40) and the same ceiling (4).
        #
        # DECISION: KEEP BOTH, BRIDGE THEM, CLAMP ONCE. They are not duplicates
        # — one is a reward for a region and one is a reward for an animal — and
        # deleting either would delete authored content to solve an arithmetic
        # problem. What cannot survive is applying them SIDE BY SIDE: two systems
        # that each clamp their own contribution do not add up to a clamped
        # total, and a Storied companion in a lantern harness and a jade collar
        # reaches 0.3075 and five interventions, past what BOTH files declare
        # legal. regalia.self_check()["bounds"]["stacked_with_quests_regalia"] is
        # that exact case, measured.
        #
        # So quests' contribution is folded in through `also_scale` /
        # `also_interventions`, regalia._clamp sees the TOTAL, and there is
        # exactly one floor and exactly one ceiling in the game. This is the only
        # call site either system reaches combat through, which is what makes
        # that claim checkable rather than hopeful.
        gear = quests.regalia_effect(self.state["quests"])
        event = regalia.party_intervention(
            self.state["pets"].get("active", []),
            bonds=self.state["pets"].get("bond", {}),
            mode=enc.mode, region_id=region_id, signals=signals or {},
            context=self._pet_context(problem, signals),
            spoken=spoken,
            difficulty=problem.difficulty, boss=bool(enc.boss_id),
            final=finalexam.encounter_seal(enc).final,
            sealed=sealed, state=self.state["pets"],
            refused=list(enc.pet_refused or []),
            regalia_state=self.state[regalia.REGALIA_STATE_KEY],
            also_scale=gear["scale"], also_interventions=gear["interventions"])
        if not event:
            return None
        if event.get("refused"):
            # Admitting it cannot read the room is not help and must never be
            # billed as help. In particular `pet_spoke` stays False: it feeds
            # `intervened=True` into bond_gain, and paying the assisted bonus to
            # an animal that said nothing useful would reward the apology.
            enc.pet_refused = sorted(set((enc.pet_refused or [])
                                         + [event["pet"]]))
            self._write_encounter(enc)
            self.save()
            return event
        # The caller contract, honoured here so no client can skip it.
        enc.hints_used += event["hint_weight"]
        enc.pet_spoke = True
        spoken[event["pet"]] = event["spoken"]
        enc.pet_spoken = spoken
        # A companion costs a hint AND caps the rank, exactly as a hint rung
        # does. Charging the hint without the cap would make a pet cheaper than
        # the spell that says the same thing.
        enc.rank_ceiling = _worse_rank(enc.rank_ceiling, event["rank_ceiling"])
        self.state["stats"]["hints_total"] += event["hint_weight"]
        self._write_encounter(enc)
        self.save()
        return event

    def _pet_context(self, problem, signals: dict | None = None) -> dict:
        """The REDACTED view a companion is allowed to read.

        Four fields, all of them vocabulary the game already shows the player
        somewhere else: the pattern, the edge-case class this problem guards,
        the category of their last graded failure, and one family they have
        already closed unaided that shares this pattern. There is no field here
        for a test or a worked solution, so a caller cannot hand one over by
        accident.

        "Already shows the player somewhere else" is a claim with a shelf life,
        because the boss ladder spends the whole game withdrawing those places.
        WEAKNESS_MAP goes two rungs before PET does, so for two fights the
        enemy's weaknesses are stripped out of the payload and the tactical
        brief is gone — and an EDGE_CLASS companion, or the hidden one wearing
        one, would have read the same class straight back out. That is the
        tactical read arriving through a side door with fur on it.

        So each field is redacted by the SAME seal that redacts the payload it
        came from. A companion whose key is gone falls through to its own
        generic line, which is the correct behaviour: it still speaks, it still
        costs a hint, and it no longer knows the thing the boss took.
        """
        signals = signals or {}
        enc = self.encounter
        weakness = str(signals.get("weakness") or "")
        if not weakness:
            keys = tactics.problem_weakness_keys(problem)
            weakness = keys[0]["key"] if keys else ""
        if finalexam.sealed(enc, "WEAKNESS_MAP"):
            weakness = ""
        category = ""
        recent = [c for c in (signals.get("last_categories") or []) if c]
        if recent:
            category = str(recent[-1])
        else:
            rows = db.attempts_for(self.conn, problem.id)
            if rows:
                category = str(rows[-1]["root_cause"] or "")
        context = {
            # PATTERN goes at a later rung than PET, so today this can only ever
            # be the pattern. It is written as a redaction anyway: the rule is
            # that a companion reads what the payload reads, and a rule that
            # happens to hold because of the order of two constants is not a
            # rule, it is a coincidence waiting for somebody to reorder them.
            "pattern": "" if finalexam.sealed(enc, "PATTERN") else problem.pattern,
            "family": problem.spaced_repetition_family,
            "weakness": weakness,
            "category": category,
        }
        # PRIOR_WORK is the only kind that reads this, and finding it is a scan
        # of the attempt log. It is computed for the animal that can use it and
        # for nobody else, because this runs on the client's timer.
        active = pets.BY_ID.get(pets.active_id(self.state["pets"]))
        if active is not None and active.hint_kind == "PRIOR_WORK":
            context["prior_family"] = self._prior_family(problem)
        return context

    def _prior_family(self, problem) -> str:
        """A family this player has already cleared unaided that shares this
        problem's pattern. BARROW's entire licence is to name one, and it can
        only ever name somewhere they have already been.
        """
        row = self.conn.execute(
            "SELECT family FROM attempts WHERE solved = 1 AND hints_used = 0"
            " AND pattern = ? AND family != ? AND problem_id != ?"
            " ORDER BY created_at DESC LIMIT 1",
            (problem.pattern, problem.spaced_repetition_family, problem.id),
        ).fetchone()
        return str(row["family"]) if row else ""

    def dismiss_pet(self) -> dict:
        """Send the companion in the field home. Reversible, always."""
        sealed = self._sealed_in_interview()
        if sealed:
            return finalexam.refuse("PET")
        out = pets.dismiss(self.state["pets"], at=time.time())
        self.save()
        return {"ok": True, **out}

    def recall_pet(self, pet_id: str) -> dict:
        """Bring a dismissed companion back. Whoever was out steps down."""
        sealed = self._sealed_in_interview()
        if sealed:
            return finalexam.refuse("PET")
        out = pets.recall(self.state["pets"], pet_id, at=time.time())
        self.save()
        return {"ok": bool(out.get("active")), **out}

    def hint_route(self) -> dict:
        """Every road out of the encounter the player is standing in, whatever
        is or is not walking with them.

        This exists so the refusal is never the last word. It is pure — it
        spends no focus, costs no rank and grants nothing — and it answers the
        same way for a player with the wrong companion, no companion, and a dead
        one, which is the proof that the tier ladder is not what stands between
        anybody and getting unstuck.
        """
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if finalexam.sealed(enc, "PET") and finalexam.sealed(enc, "HINTS"):
            # Nothing is open here and saying so is the honest answer. The exam
            # does not get a map out; that is what an exam is.
            return finalexam.refuse("HINTS")
        repo = self._repo_of(enc)
        problem = repo_problem(repo) if repo else self.by_id[enc.problem_id]
        depth = self._asked_depth(problem)
        route = pets.fallback_route(pets.active_id(self.state["pets"]),
                                    difficulty=depth, state=self.state["pets"])
        route["attempts"] = len(db.attempts_for(self.conn, problem.id))
        route["solution_free_now"] = route["attempts"] >= pets.FREE_SOLUTION_AFTER
        route["hint_count"] = 0 if finalexam.sealed(enc, "HINTS") \
            else len(problem.hint_tree)
        return route

    # -- dungeons ----------------------------------------------------------
    def dungeon_list(self, region_id: str = "") -> dict:
        region_id = region_id or self.state["player"].get("region", "")
        return {"region": region_id,
                "dungeons": [self._dungeon_card(d)
                             for d in dungeons.dungeons_for_region(region_id)]}

    def enter_dungeon(self, dungeon_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        if dungeon_id not in dungeons.DUNGEON_BY_ID:
            return {"error": "unknown dungeon"}
        built = self._dungeon_for(dungeon_id)
        try:
            run = dungeons.enter(built, run_seed=self._rng.randrange(1 << 30))
        except ValueError as exc:
            return {"error": str(exc)}
        # The room->problem map is stored so a returning player meets the same
        # problem in the same room; the building itself is never serialised.
        self.state["dungeon_map"][dungeon_id] = dungeons.populate(
            built, self.teachable, skills=self.skills,
            solved_ids=set(self.state["solved_ids"]), rng=self._rng)
        self.state[dungeons.STATE_KEY] = run
        self.save()
        return self.dungeon_state()

    def dungeon_state(self) -> dict:
        run = self.state.get(dungeons.STATE_KEY)
        if not run:
            return {"dungeon": None}
        built = self._dungeon_for(run["dungeon"], run.get("seed"))
        return {
            "dungeon": {"id": built.id, "name": built.name, "rule": built.rule,
                        "rule_note": built.rule_note, "archetype": built.archetype,
                        # "floors" is the floor COUNT, the way _dungeon_card
                        # and quests.note_depth mean it. Dungeon.floor is the
                        # difficulty floor ("GUIDED") and shipping that under
                        # the same key gave the client two types for one name.
                        "floors": dungeons.floors_for(built.id),
                        "difficulty_floor": built.floor,
                        "max_depth": built.max_depth},
            "run": run,
            "progress": {**dungeons.progress(built, run),
                         "depth": self._dungeon_depth(built, run)},
            "options": dungeons.options(built, run),
            "rooms": [r.to_dict() for r in built.rooms if r.id in run["visited"]],
            "exit_path": dungeons.exit_path(built, run["at"]),
        }

    def dungeon_move(self, room_id: int) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        run = self.state.get(dungeons.STATE_KEY)
        if not run:
            return {"error": "you are not in a dungeon"}
        built = self._dungeon_for(run["dungeon"], run.get("seed"))
        result = dungeons.move(built, run, int(room_id))
        if result.get("moved"):
            room = next((r for r in built.rooms if r.id == run["at"]), None)
            if room is not None and "hidden" in (room.tags or []):
                run["off_map"] = True
                self.state["stats"]["hidden_rooms_found"] = int(
                    self.state["stats"].get("hidden_rooms_found", 0)) + 1
            quests.note_depth(self.state, run["dungeon"],
                              self._dungeon_depth(built, run))
        self.state[dungeons.STATE_KEY] = run
        # THE DUNGEON HOOK, first of two. A hidden healer is found by being HURT
        # in the right room rather than by searching for one, so this is called
        # on every move and answers with a blank row almost every time. It never
        # writes to `run`, never raises, and writes to `state` only to record a
        # first find.
        found = sanctuary.dungeon_look(self.state, built, run,
                                       sealed=bool(sealed))
        self.save()
        return {**result, "state": self.dungeon_state(),
                "sanctuary": found if found.get("tell") or found.get("here")
                else None}

    def dungeon_engage(self) -> dict:
        """Fight what is standing in this room. The room holds an encounter
        REQUEST, not a problem id, so a chapter-one player who walks into the
        Graph Wastes still meets material the curriculum has opened.

        Sealed in a measured run. A descent left open when the exam starts is
        the one way a dungeon reaches Interview Mode, and engaging from inside
        it opened a full Adventure encounter over the top of the exam's own.
        """
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        run = self.state.get(dungeons.STATE_KEY)
        if not run:
            return {"error": "you are not in a dungeon"}
        built = self._dungeon_for(run["dungeon"], run.get("seed"))
        room = next((r for r in built.rooms if r.id == run["at"]), None)
        if room is None or not room.demands_solving:
            return {"error": "nothing here asks anything of you"}
        # A CLEARED ROOM IS SHUT. Without this the room stays openable forever:
        # `dungeon_map` binds the room to one problem so a relented retry asks
        # the same idea, which means re-engaging served the SAME problem again
        # and `clear_room` paid its purse again, every time, for as long as the
        # player pressed the key. That is unbounded gold and XP for no new
        # Python, and it is the one thing the economy may not offer. Failure
        # still reopens the room, because a failed room is not in `cleared`.
        if room.id in run.get("cleared", []):
            return {"error": "you have already cleared this room",
                    "message": "Whatever was in here, you beat it. The room "
                               "has nothing else to ask."}
        bound = (self.state["dungeon_map"].get(built.id) or {}).get(str(room.id))
        problem = self.by_id.get(bound)
        if problem is None:
            problem = dungeons.resolve_encounter(
                room.encounter, self.teachable, skills=self.skills,
                solved_ids=set(self.state["solved_ids"]),
                recent_ids=self.state["recent_ids"], rng=self._rng,
                attempts=int(run.get("attempts", {}).get(str(room.id), 0)))
        if problem is None:
            return {"error": "this room is empty"}
        payload = self.start_encounter(problem.id, reason="DUNGEON")
        if payload.get("error"):
            return payload            # a refusal is not an encounter to decorate
        enc = self.encounter
        enc.dungeon_room = room.id
        self._write_encounter(enc)
        payload["encounter"] = enc.to_dict()
        self.save()
        payload["room"] = room.to_dict()
        payload["dungeon"] = {"id": built.id, "name": built.name,
                              "depth": room.depth}
        return payload

    def dungeon_retreat(self) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        run = self.state.get(dungeons.STATE_KEY)
        if not run:
            return {"error": "you are not in a dungeon"}
        built = self._dungeon_for(run["dungeon"], run.get("seed"))
        path = dungeons.exit_path(built, run["at"])
        run["retreated"] = True
        for room_id in path[1:]:
            dungeons.move(built, run, room_id)
        self.state[dungeons.STATE_KEY] = run
        self.save()
        return {"ok": True, "path": path, "state": self.dungeon_state()}

    def leave_dungeon(self) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        run = self.state.get(dungeons.STATE_KEY)
        self.state[dungeons.STATE_KEY] = None
        self.save()
        return {"ok": True, "left": (run or {}).get("dungeon", "")}

    # -- the overworld -----------------------------------------------------
    def world_map(self) -> dict:
        # The wheel, on the map screen. elements.region_affinities() reads
        # world.REGIONS in world order and derives each region's element from
        # its BIOME, so a new region arrives with weather already attached and
        # nobody has to remember to author it twice.
        return {**progression.world_map(self.state, self.skills,
                                        readiness=self._readiness()),
                "affinities": elements.region_affinities()}

    def region_view(self, region_id: str) -> dict:
        prog = progression.snapshot(self.state, self.skills,
                                    readiness=self._readiness())
        view = progression.region_view(region_id, prog)
        hazard = elements.hazard_for(region_id)
        boots = items.boots_id(self.state["equipped"])
        # What one step across this region costs in the boots actually on the
        # player's feet. `roll` is pinned at 1.0 so this is the PREVIEW — it
        # reports the speed and the risk without ever inflicting anything, which
        # is the same discipline elements.resolve_damage uses for a swing.
        # DEGRADE — docs/10-sealed-views.md §4.D. The row is geography and
        # stays; `step` alone is computed from the boots actually equipped, and
        # boots are BUILD. `_player_defender` hands `build_sealed=True` into
        # elements during a measured run, so the quoted cost is not the cost.
        # Narrow, real, and the same in-force defect as the loadout screen.
        sealed = bool(self._sealed_in_interview())
        view["element"] = {
            "id": elements.affinity_for(region_id),
            "view": elements.element_view(elements.affinity_for(region_id)),
            "hazard": ({"id": hazard.id, "name": hazard.name,
                        "blurb": hazard.blurb, "element": hazard.element}
                       if hazard else {}),
            "step": (None if sealed
                     else elements.hazard_step(region_id, boots, roll=1.0)),
            "boots": ("" if sealed else boots),
            "sealed": sealed,
        }
        return view

    def things_to_do(self) -> list:
        due = srsmod.due(self.schedule, now=time.time(), limit=25)
        return progression.things_to_do(self.state, self.skills,
                                        readiness=self._readiness(),
                                        due_retests=len(due), limit=6)

    def travel(self, route_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        prog = progression.snapshot(self.state, self.skills,
                                    readiness=self._readiness())
        status = progression.can_travel(prog, route_id,
                                        frm=self.state["player"]["region"])
        if not status.get("ok"):
            return {"error": "the road is closed", "route": status}
        self.state["player"]["region"] = status["to"]
        # See `move`: geography is recorded wherever the player's region
        # changes, and there are exactly two such places.
        storymod.note_region(self.state["story"], status["to"])
        walked = self.state["world"].setdefault("routes_walked", [])
        if route_id not in walked:
            walked.append(route_id)
        self._count_world_stats()
        self.save()
        saves.autosave(self.conn, self.state, "region_entered")
        return {"ok": True, "route": status,
                "region": status["to"],
                "world": progression.advance(self.state, self.skills,
                                             readiness=self._readiness())}

    # -- saves -------------------------------------------------------------
    def save_slots(self) -> dict:
        return {"slots": saves.list_slots(self.conn),
                "undo_available": saves.undo_available(self.conn)}

    def save_to_slot(self, ordinal, name: str = "", note: str = "") -> dict:
        return saves.save_to_slot(self.conn, ordinal, self.state, name=name,
                                  note=note, readiness=self._readiness())

    def load_slot(self, slot_id) -> dict:
        # Saving mid-run is allowed — it banks the run, it does not help with
        # it. Loading is a retry, and the server has always said so; the engine
        # has to say it too or the guarantee lives in one layer only.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        try:
            result = saves.load_slot(self.conn, slot_id, current_state=self.state)
        except saves.SaveError as exc:
            return {"ok": False, "error": str(exc)}
        # The caller MUST adopt the returned state; dropping it leaves the
        # in-memory game and the row on disk out of step.
        self.state = result["state"]
        self._after_load()
        return result

    def undo_load(self) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        if not saves.undo_available(self.conn):
            return {"ok": False, "error": "there is nothing to undo"}
        try:
            result = saves.undo_load(self.conn, current_state=self.state)
        except saves.SaveError as exc:
            return {"ok": False, "error": str(exc)}
        self.state = result["state"]
        self._after_load()
        return result

    def _after_load(self) -> None:
        """A loaded save is somebody else's world. Rebuild everything derived."""
        merged = _deep_copy(DEFAULT_STATE)
        _merge(merged, self.state)
        self.state = self._repair_blocks(merged)
        self._reseed_world(self.state.get("world_seed") or 0)
        self._sync_class_points()
        self._grant_blade()
        self._sync_caps()
        self.save()

    # -- the final exam ----------------------------------------------------
    def exam_ladder(self) -> dict:
        return {"ladder": finalexam.ladder_view(),
                "format": finalexam.interview_format()}

    # -- the Obliging Hand -------------------------------------------------
    def hand_offer(self) -> dict:
        enc = self.encounter
        mode = enc.mode if enc else config.MODE_ADVENTURE
        return {**legendaries.hand_offer(),
                "owned": "obliging_hand" in self.state["legendaries"],
                "sealed": legendaries.hand_sealed(mode),
                "summary": legendaries.hand_summary(self.state["hand"])}

    def use_hand(self) -> dict:
        """The one thing in this codebase that lowers mastery for a reason other
        than a graded failure. It solves the encounter and pays loot and XP in
        full — the cost is a permanent ceiling on the skill, and nothing else."""
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if "obliging_hand" not in self.state["legendaries"]:
            return {"error": "you are not wearing it"}
        if finalexam.sealed(enc, "OBLIGING_HAND"):
            return finalexam.refuse("OBLIGING_HAND")
        if enc.repo_id:
            # The Hand solves an encounter by knowing the answer. There is no
            # single answer to a repository, and the one thing it could do —
            # write the reference patch into your editor — is the one thing
            # nothing in this game is allowed to do.
            return {"error": "the hand cannot read for you",
                    "message": "It has no idea which file this is in either. "
                               "Nothing is charged; nothing is lowered."}
        problem = self.by_id[enc.problem_id]
        skill_name = skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")
        skills = self.skills
        result = legendaries.use_hand(skills, self.state["hand"],
                                      skill=skill_name,
                                      difficulty=problem.difficulty,
                                      mode=enc.mode)
        if not result.get("solved"):
            return result
        self._write_skills(skills)
        fx = self.effects()
        drop = items.roll_drop(difficulty=problem.difficulty, rank=result["rank"],
                               luck=fx.get("loot_luck", 0.0),
                               is_boss=bool(enc.boss_id), skill=skill_name,
                               owned=set(self.state["inventory"]), rng=self._rng)
        if drop:
            self._take_drop(drop)
        player = self.state["player"]
        xp = grading.xp_for(difficulty=problem.difficulty, rank=result["rank"],
                            combo=grading.combo_multiplier(player["combo"]),
                            is_retest=enc.is_retest)
        player["xp"] += xp
        player["level"] = world.level_for(player["xp"])
        player["title"] = world.title_for(player["level"])
        if problem.id not in self.state["solved_ids"]:
            self.state["solved_ids"].append(problem.id)
        self._write_encounter(None)
        self.save()
        return {**result, "xp": xp, "loot": drop,
                "canonical_solution": problem.canonical_solution}

    # -- the relic codex ---------------------------------------------------
    def legendary_catalogue(self) -> dict:
        return {"catalogue": legendaries.catalogue(),
                "owned": list(self.state["legendaries"]),
                "hand": legendaries.hand_summary(self.state["hand"])}

    def legendary(self, artifact_id: str) -> dict:
        entry = legendaries.codex_entry(artifact_id)
        if not entry:
            return {"error": "unknown artifact"}
        stats = {**self.state["stats"], **db.attempt_stats(self.conn)}
        return {**entry, "owned": artifact_id in self.state["legendaries"],
                "progress": legendaries.eligible(
                    artifact_id,
                    skills={n: s.to_dict() for n, s in self.skills.items()},
                    stats=stats)}

    def _unaided_counts(self) -> tuple:
        rows = self.conn.execute(
            "SELECT difficulty, COUNT(DISTINCT problem_id) AS n FROM attempts"
            " WHERE solved = 1 AND hints_used = 0 GROUP BY difficulty").fetchall()
        counts = {r["difficulty"]: r["n"] for r in rows}
        return counts.get("EASY", 0) + counts.get("TUTORIAL", 0), counts.get("MEDIUM", 0)

    def _refresh_daily(self, skills, schedule) -> None:
        today = time.strftime("%Y-%m-%d")
        if self.state["daily"].get("date") == today:
            return
        self.state["daily"] = {
            "date": today, "completed": [],
            "quests": adaptive.daily_quests(
                skills=skills, schedule=schedule, corpus=self.teachable,
                profile=self.state["player"]["profile"]),
        }

    # ======================================================================
    # The hold-out, and the second number it exists to produce
    # ======================================================================
    #
    # Ordinary mastery measures familiarity and is untouched by everything
    # below. This is a SECOND number, from evidence the teaching side of the
    # game is not allowed to produce, and the two never mix: nothing here reads
    # mastery, nothing in skills.py reads this, neither gates the other, and
    # there is nothing the player can spend to move it.

    def _seen_problem_ids(self) -> set:
        """Every problem this player has ever met, as ids.

        Ids, not lineages — lineages are derived from them against whatever
        corpus is current, so a rebuild cannot leave a stale lineage string in a
        save. Three records, because each one knows something the others do not:
        the attempt log is the complete graded history, the hold-out ledger
        knows about sealed problems that were served and walked away from, and
        solved_ids/recent_ids cover the live session.
        """
        ids = set(self.state.get("solved_ids") or ())
        ids |= set(self.state.get("recent_ids") or ())
        ids |= db.attempted_problem_ids(self.conn)
        ids |= db.transfer_problem_ids(self.conn)
        return ids

    def transfer_pool(self) -> list:
        """Sealed problems from a lineage this player has never met. What is
        left that can still be asked of them exactly once."""
        return corpusmod.transfer_pool(self.corpus, self._seen_problem_ids())

    def _open_transfer(self, problem: Problem, mode: str) -> bool:
        """Spend one hold-out problem, and record whether it was met cold.

        Called at SERVE time and not at grading time, which is what makes the
        hold-out unfarmable: seeing a sealed problem consumes its lineage
        whether the player solves it, fails it, or closes the tab. That is the
        entire reason the hold-out is finite.
        """
        first = corpusmod.is_unfamiliar(self.corpus, problem,
                                        self._seen_problem_ids())
        return db.open_transfer(
            self.conn, problem_id=problem.id,
            lineage_id=corpusmod.lineage_of(problem),
            pattern=problem.pattern,
            skill=skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON"),
            difficulty=problem.difficulty, mode=mode,
            first_encounter=first)

    def _record_transfer(self, problem: Problem, enc: Encounter, *, solved: bool,
                         seconds: float, rank: str) -> dict | None:
        """Fold a graded hold-out outcome into the ledger.

        `unaided` is spelled out rather than assumed. Every one of these is
        already sealed off by HOLDOUT_SEAL before the encounter starts, so each
        clause should be unreachable — which is exactly why it is written down.
        The day one of them stops being unreachable, the number stops counting
        that encounter instead of quietly counting a hinted clear as transfer.
        """
        unaided = (enc.hints_used == 0 and not enc.used_phoenix
                   and enc.probes_used == 0 and not enc.pet_spoke
                   and not enc.temp_effects)
        # Was the measurement taken by THIS submission, or was it already taken?
        # db.resolve_transfer is write-once, so a second submission against the
        # same sealed problem returns the standing row untouched. Knowing which
        # happened is the difference between telling the player their clear
        # counted and telling them the truth, so it is read before the write
        # rather than guessed at afterwards.
        standing = db.transfer_row(self.conn, problem.id)
        already = bool(standing and standing["resolved"])
        row = db.resolve_transfer(
            self.conn, problem.id, solved=solved, unaided=unaided,
            hints_used=enc.hints_used, seconds=seconds, rank=rank)
        if row is not None:
            # Not a column; it describes this submission rather than the ledger.
            row["regrade"] = already
        return row

    def transfer_report(self) -> dict:
        """TRANSFER READINESS, its sample size and its confidence band.

        Deliberately not folded into adaptive.readiness(): that number is the
        RPG's own, built from taught material, and blending the two would give
        the player one number that means neither thing.
        """
        pool = self.transfer_pool()
        return transfermod.summarise(
            db.transfer_ledger(self.conn),
            remaining=len({p.lineage_id for p in pool}),
            holdout_total=len(self.holdout),
            lineages_total=len({p.lineage_id for p in self.holdout}))

    # -- what a measured run is allowed to say about itself ----------------

    @staticmethod
    def run_view(run: dict | None) -> dict | None:
        """A measured run, as the client may see it: how far in, how many left,
        how long. NOT which problems.

        The roster is the leak nobody looks for, because it is not a selector
        and it is not an encounter — it is a table of contents. Interview Mode
        reaches for the hold-out first, so `problem_ids` is a list of sealed ids
        the player has not been served yet, and it was being handed over twice:
        once in the payload that starts a run, and again on every poll of
        /api/state for as long as the run stayed open.

        Nothing was spent by reading it. A sealed problem is spent when it is
        SERVED — that is the rule that makes the hold-out finite — so the
        roster was a way to collect sealed ids and titles for free, abandon the
        run, go and read about them, and come back to be measured on problems
        chosen precisely because they had never been seen. The cheapest version
        of that costs one click and reveals the ids the selector likes best,
        which are the ones that would have been asked anyway.

        So a run discloses one question at a time, which is the pace at which it
        spends them. `total` replaces `problem_ids` because a progress counter
        is all the count was ever used for.
        """
        if not run:
            return None
        view = {k: v for k, v in run.items() if k != "problem_ids"}
        view["total"] = len(run.get("problem_ids") or ())
        return view

    # -- encounter selection ----------------------------------------------
    def next_encounter(self, *, region: str | None = None,
                       mode: str = config.MODE_ADVENTURE,
                       kind: str | None = None,
                       armor_piece: str = "") -> dict:
        skills = self.skills
        # The Armorer could not be asked to fix the piece you actually broke:
        # the repair went to whichever piece the served problem happened to be
        # tagged for. Naming the piece filters the candidates by that tag.
        tag = "armor:%s" % armor_piece if armor_piece else ""
        # self.teachable, not self.corpus. Adventure Mode teaches, so it does
        # not get handed the hold-out to filter back out again.
        pool = [p for p in self.teachable
                # parenthesised deliberately: the previous form parsed as
                # `(matches_kind and not_boss) or matches_kind`, which let an
                # explicit kind smuggle boss encounters into ordinary selection
                if (kind is None or p.encounter_kind == kind)
                and p.difficulty != "BOSS"
                and (not tag or tag in p.tags)]
        if tag and not pool:
            pool = [p for p in self.teachable
                    if (kind is None or p.encounter_kind == kind)
                    and p.difficulty != "BOSS"]
        selection = adaptive.select_next(
            pool,
            skills=skills, schedule=self.schedule,
            profile=self.state["player"]["profile"],
            solved_ids=set(self.state["solved_ids"]),
            recent_ids=self.state["recent_ids"],
            # Named from the full corpus rather than the filtered slice above, so
            # asking for one kind cannot blind the selector to what came before.
            recent_kinds=[self.by_id[i].encounter_kind
                          for i in self.state["recent_ids"] if i in self.by_id],
            # What has already been cleared TODAY, so a family learned this
            # morning can come back this afternoon instead of waiting a day for
            # the SRS minimum interval to expire.
            session=self.state["session"].get("log", []),
            region=region, allow_retest=(mode == config.MODE_ADVENTURE),
        )
        return self.start_encounter(selection.problem.id, mode=mode,
                                    is_retest=selection.is_retest,
                                    interval_days=selection.interval_days,
                                    reason=selection.reason)

    def start_encounter(self, problem_id: str, *, mode: str = config.MODE_ADVENTURE,
                        is_retest: bool = False, interval_days: float = 0.0,
                        reason: str = "MANUAL", boss_id: str = "",
                        interview_id: str = "") -> dict:
        problem = self.by_id.get(problem_id)
        if problem is None:
            raise KeyError(problem_id)
        holdout = corpusmod.is_sealed(problem)
        if holdout and mode != config.MODE_INTERVIEW:
            # The last door. Every selector above already draws from
            # self.teachable, so nothing should ever arrive here with hold-out
            # content — and a guarantee that depends on every caller getting it
            # right is not a guarantee. A quest, a dungeon room, a shrine, a
            # boss or a hand-typed problem id all end up in this method.
            return finalexam.refuse(finalexam.HOLDOUT)
        enc = Encounter(problem_id=problem_id, mode=mode, started_at=time.time(),
                        is_retest=is_retest, interval_days=interval_days,
                        boss_id=boss_id, interview_id=interview_id,
                        holdout=holdout,
                        region=self.state["player"].get("region", ""))
        # Turn one. The pouch's falloff, the dose pool and both status lists are
        # per-FIGHT, so they are born here and die with the encounter: a player
        # who walks away from a fight does not carry its poison to the next one,
        # and does not carry its sip discount either.
        enc.potion_turn = potions.new_fight().to_dict()
        enc.poison = {}
        enc.turn = 1
        self._arm_enemy(problem, enc)
        if holdout:
            # Spent on sight, before the payload is built. If this player never
            # submits, the lineage is still gone.
            self._open_transfer(problem, mode)
        self._write_encounter(enc)
        self.state["stats"]["encounters"] += 1
        self.save()
        return self._encounter_payload(problem, enc, reason=reason)

    def _encounter_payload(self, problem: Problem, enc: Encounter,
                           reason: str = "") -> dict:
        seal = finalexam.encounter_seal(enc)
        interview = enc.mode == config.MODE_INTERVIEW
        # An exam question goes through exam_view, which is the only payload an
        # exam may send: it additionally drops complexity_choices, because four
        # Big-O options with the right one among them tell you what shape of
        # answer is expected.
        view = (finalexam.exam_view(problem) if interview
                else problem.player_view(mode=enc.mode))
        if seal.blocks("VISUALS"):
            view["visualization"] = {}
        if seal.blocks("PATTERN"):
            view["pattern"] = "REDACTED"
            view["secondary_patterns"] = []
            view["optimal_complexity"] = {}
            view["common_failures"] = []
        if seal.blocks("HINTS"):
            view["hint_tree"] = []

        enemy_dict = self._enemy_for(problem, enc.exposed)
        enemy_obj = tactics.Enemy(**{k: v for k, v in enemy_dict.items()
                                     if k in ("name", "sprite", "hp", "hp_max", "boss",
                                              "taunt", "colour", "difficulty",
                                              "weaknesses", "resistances", "exposed")})
        if seal.blocks("WEAKNESS_MAP"):
            # derive_enemy builds `weaknesses` out of the problem's edge cases and
            # hangs a teaching line off each one, so shipping the enemy whole was
            # handing over the hidden tests with an explanation attached.
            enemy_dict = {**enemy_dict, "weaknesses": [], "resistances": [],
                          "exposed": []}
        skills = self.skills
        skill_name = skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")
        history = db.attempts_for(self.conn, problem.id)
        payload = {
            "problem": view,
            "encounter": enc.to_dict(),
            "reason": reason,
            "mode": enc.mode,
            "interview_locked": interview,
            "seal": seal.to_dict(),
            "enemy": enemy_dict,
            "tactics": ({} if seal.blocks("WEAKNESS_MAP")
                        else tactics.tactical_brief(enemy_obj, enc.exposed)),
            "probe_charges": self.probes_remaining(),
            "loadout": {} if seal.blocks("BUILD") else self.loadout(),
            "region": self._region_view(problem.realm),
            "mentor": (None if seal.blocks("MENTOR") else world.MENTORS.get(
                world.REGION_BY_ID.get(problem.realm, {}).get("mentor", "byte"))),
            "skill": "" if seal.blocks("SKILL_STATE") else skill_name,
            "skill_state": (None if seal.blocks("SKILL_STATE")
                            or skill_name not in skills
                            else skills[skill_name].to_dict()),
            "attempts_before": len(history),
            "best_time": db.best_time(self.conn, problem.id),
            "hint_count": 0 if seal.blocks("HINTS") else len(problem.hint_tree),
            "clock_seconds": finalexam.clock_for(problem, seal),
            # The seal is decided in one place and handed in, rather than
            # guessed at again here. From the rung that takes PET onward, the
            # field is empty in the payload as well as in the refusal, so the
            # client is never drawing an animal that cannot speak.
            "companions": ([] if not pets.available_in(
                enc.mode, self.state["player"].get("region", ""),
                sealed=finalexam.sealed(enc, "PET"))
                else list(self.state["pets"].get("active", []))),
            "mana": self.state["player"]["mana"],
            "stamina": self.state["player"]["stamina"],
            # THE LOW-HEALTH ALARM, AT THE DOOR OF THE FIGHT.
            #
            # `upkeep.alarm` is a pure function of two numbers that are already
            # on the two lines above this one, and the graded-submission result
            # has shipped it since upkeep landed. It was missing HERE, which
            # left a client exactly two ways to draw the red pulse on somebody
            # who walked INTO a fight already hurt: call `Game.town()`, which is
            # a VISIT and heals them, or keep its own copy of ALARM_BANDS. The
            # first is a cosmetic fetch with a game-changing side effect; the
            # second puts the threshold that decides when things got bad into
            # two files, which is how a sprite and a bar end up disagreeing.
            #
            # Not sealed, and it does not need to be: it is a reading of the
            # player's own health bar, which is on screen either way, and it
            # says nothing at all about the problem in front of them.
            "alarm": upkeep.alarm(self.state),
        }
        # -- the tactical layer, as the battle HUD draws it -------------------
        #
        # The belt carries its own `sealed` flag and a per-potion `reason`, so
        # no extra seal check belongs here: a greyed-out potion with no reason
        # is how a player concludes a mechanic is broken, and potions.pouch_view
        # is the one place that sentence is written.
        #
        # The enemy's element is behind the WEAKNESS_MAP seal, same as its
        # weaknesses, because "it is made of cold" is a reading of the room and
        # a measured run is not given readings. Its HEALTH AND FOCUS are not
        # sealed: those are what the fight looks like, not what the answer is.
        statuses = self._load_statuses(enc.statuses)
        turn_state = potions.TurnState.from_dict(enc.potion_turn)
        payload["pouch"] = potions.pouch_view(
            self._pouch(), player=self.state["player"], turn_state=turn_state,
            poison=potions.Poison.from_dict(enc.poison), encounter=enc,
            statuses=statuses)
        payload["turn"] = int(enc.turn)
        payload["statuses"] = list(enc.statuses)
        payload["enemy_statuses"] = list(enc.enemy_statuses)
        payload["poison"] = dict(enc.poison)
        payload["combat_log"] = list(enc.combat_log)
        vitals = dict(enc.enemy_vitals or {})
        revealed = not seal.blocks("WEAKNESS_MAP")
        player_element = self._player_element(enc)
        if not revealed:
            vitals = {**vitals, "element": "", "specials": []}
        payload["enemy_vitals"] = vitals
        payload["element"] = {
            "region": "" if not revealed else self._region_element(problem),
            "player": player_element,
            "enemy": vitals.get("element", ""),
            "view": elements.element_view(
                (enc.enemy_vitals or {}).get("element", elements.NEUTRAL),
                revealed=revealed),
            "armour": items.armour_view(
                {} if seal.blocks("BUILD") else self.effects()),
            "hazard": (lambda h: {"id": h.id, "name": h.name, "blurb": h.blurb}
                       if h else {})(elements.hazard_for(problem.realm)),
        }
        if enc.holdout:
            # The client cannot work this out for itself: `player_view` ships
            # neither `sealed` nor `lineage_id`, because a player who can read
            # the hold-out can study it. So the engine says it, in the only two
            # facts the interface needs — this is measured, and it counts once.
            row = db.transfer_row(self.conn, problem.id) or {}
            payload["transfer"] = {
                "holdout": True,
                "first_encounter": bool(row.get("first_encounter")),
                "note": ("A sealed problem, served cold. Nothing here will help "
                         "you and nothing here is a lesson."),
            }
        if interview:
            # Refuse to ship rather than hope. A bare `assert` would vanish under
            # python -O, and this is the one guarantee the whole mode rests on.
            leaks = finalexam.audit_payload(payload)
            if leaks:
                raise RuntimeError("exam payload leaks: %s" % "; ".join(leaks))
        return payload

    ENEMY_SPRITES = {
        "LANGUAGE": "runeling",
        "HASH_MAP": "vaultling", "SET": "wisp", "SLIDING_WINDOW": "marshling",
        "TWO_POINTER": "twinblade", "STACK": "cartgoblin", "QUEUE": "linewraith",
        "BFS": "lightwave", "DFS": "deepcrawler", "TREE": "branchling",
        "RECURSION": "mirrorspawn", "BINARY_SEARCH": "halfling",
        "MATRIX": "gridling", "HEAP": "pilekeeper", "PREFIX_SUM": "ledgerling",
        "SORTING": "orderling", "SIMULATION": "clockwork", "DP": "echoling",
        "STRING": "slime", "ARRAY": "indexling", "DESIGN": "construct",
        "DEBUGGING": "bugling", "COMPLEXITY": "wyrmling", "TESTING": "mimic",
        "RECOGNITION": "riddler", "GREEDY": "hoarder", "INTERVALS": "overlapper",
    }

    def _arm_enemy(self, problem: Problem, enc: Encounter) -> dict:
        """Give this fight's enemy its vitals: focus, an element, and specials.

        The element comes off the GROUND, which is the whole of the brief's
        "every area has an affinity from its surroundings" pushed one step down
        into the things that live there. The bestiary does not carry an element
        and does not need to — elements.enemy_element lets a future entry
        override it — and a boss gets more health, more focus and more to spend
        it on, which is all three of the things bosses were asked to get more of.

        Antidotes are rolled here too, once, so a monster that can cure itself
        is decided before the fight rather than every time it is asked.
        """
        enemy = self._enemy_for(problem, enc.exposed)
        enc.enemy = enemy
        element = elements.enemy_element(enemy, problem.realm) \
            if not finalexam.sealed(enc, "BUILD") else elements.NEUTRAL
        if element == elements.NEUTRAL and not finalexam.sealed(enc, "BUILD"):
            element = self._region_element(problem)
        is_boss = bool(enc.boss_id or enemy.get("boss"))
        # The focus pool is sized by DIFFICULTY rather than off this enemy's HP,
        # because a problem-encounter enemy's HP is tactics.derive_enemy's count
        # of hidden tests and not a health bar at all. Left to derive itself, a
        # three-test problem would field a monster carrying eight focus and a
        # cheapest special costing ten — a creature that stands there saving up
        # for something it can never buy.
        enc.enemy_vitals = bestiary.vitals(
            hp=int(enemy.get("hp_max") or enemy.get("hp") or 1),
            element=element if element in elements.ELEMENTS else "",
            is_boss=is_boss,
            focus=ENEMY_FOCUS_BY_DIFFICULTY.get(problem.difficulty, 12))
        enc.enemy_vitals["antidotes"] = potions.carries_antidote(
            difficulty=problem.difficulty,
            affinity=str(element or "").lower(),
            is_boss=is_boss,
            is_elite=problem.difficulty in ("HARD", "ELITE"),
            rng=self._rng)
        return enc.enemy_vitals

    def _enemy_for(self, problem: Problem, exposed: list | None = None) -> dict:
        """An enemy is a reading of the problem: its weaknesses are the edge cases
        it hides, its resistances are the ceilings it enforces."""
        boss = next((b for b in world.BOSSES if b["problem_id"] == problem.id), None)
        enemy = tactics.derive_enemy(
            problem,
            name=boss["name"] if boss else self._enemy_name(problem),
            sprite=boss["sprite"] if boss else self.ENEMY_SPRITES.get(
                problem.pattern, "slime"),
            boss=bool(boss),
            taunt=boss["taunt"] if boss else "",
            colour=boss["colour"] if boss else "")
        enemy.exposed = list(exposed or [])
        return enemy.to_dict()

    _ADJECTIVES = ["Lesser", "Elder", "Feral", "Gilded", "Hollow", "Shrouded",
                   "Ancient", "Restless"]

    def _enemy_name(self, problem: Problem) -> str:
        base = self.ENEMY_SPRITES.get(problem.pattern, "slime").title()
        seed = sum(ord(c) for c in problem.id)
        if problem.difficulty in ("TUTORIAL", "EASY"):
            return base
        return f"{self._ADJECTIVES[seed % len(self._ADJECTIVES)]} {base}"

    def _graced_target(self, problem: Problem) -> float:
        """HASTE and Chronomancer gear buy grace on the CLOCK, for rank only.
        Correctness is never graded on a curve."""
        enc = self.encounter
        if finalexam.sealed(enc, "BUILD"):
            return problem.target_seconds
        grace = self.effects().get("rank_grace", 0.0)
        return problem.target_seconds * (1.0 + grace)

    # -- running and grading ----------------------------------------------
    def run_code(self, code: str) -> dict:
        enc = self.encounter
        if enc and not enc.first_code_at and code.strip():
            enc.first_code_at = time.time()
            enc.runs += 1
            self._write_encounter(enc)
            self.save()
        elif enc:
            enc.runs += 1
            self._write_encounter(enc)
        report = sandbox.run_scratch(code)
        return report.to_dict()

    def run_visible(self, code: str) -> dict:
        """The Run button: visible trials only, no grading, no state change."""
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if enc.repo_id:
            return {"error": "this is a mini-repo",
                    "message": "A repository runs its own suite. Use RUN TESTS."}
        problem = self.by_id[enc.problem_id]
        enc.runs += 1
        if not enc.first_code_at and code.strip():
            enc.first_code_at = time.time()
        self._write_encounter(enc)
        self.save()
        report = sandbox.run_tests(code, problem.entry, problem.visible_tests)
        if report.phase == "syntax":
            enc.syntax_errors += 1
            self._write_encounter(enc)
            self.save()
        return {**report.to_dict(), "graded": False}

    def submit(self, code: str, *, declared_pattern: str = "",
               declared_cause: str = "", explanation: str = "") -> dict:
        """`declared_cause` is the player NAMING THE BUG before the grader says.

        It is a grading.ROOT_CAUSES key, it is optional, it changes no grade and
        it costs nothing to get wrong. What it does is put a number under the
        Debugging Dungeon's sage, whose whole condition is "six failures named
        before the diagnosis rendered" — a condition nothing in this engine
        could answer, because nothing was asking the question.
        """
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if enc.repo_id:
            return {"error": "this is a mini-repo",
                    "message": "A repository is handed back whole, not as one "
                               "function. Use HAND IT BACK."}
        problem = self.by_id[enc.problem_id]
        enc.submits += 1
        enc.declared_pattern = declared_pattern or enc.declared_pattern
        enc.declared_cause = declared_cause or enc.declared_cause
        enc.explanation = explanation or enc.explanation
        if not enc.first_code_at and code.strip():
            enc.first_code_at = time.time()

        if problem.entry.get("kind") == "test_forge":
            return self._grade_forge(code, problem, enc)
        if problem.encounter_kind in puzzles.PUZZLE_KINDS:
            return self._grade_puzzle(problem, enc, code)

        report = sandbox.run_tests(code, problem.entry, problem.all_tests,
                                   timeout_ms=3000, wall_seconds=20)
        if report.phase == "syntax":
            enc.syntax_errors += 1

        seconds = max(1.0, time.time() - enc.started_at)
        solved = report.all_passed
        analysis = grading.analyse(report, problem, hints_used=enc.hints_used,
                                   seconds=seconds,
                                   declared_pattern=declared_pattern or None)
        feedback = grading.battle_feedback(report, problem)
        first_try = solved and enc.submits == 1
        rank = grading.rank_for(solved=solved, hints_used=enc.hints_used,
                                seconds=seconds,
                                target_seconds=self._graced_target(problem),
                                used_phoenix=enc.used_phoenix, first_try=first_try)

        self._write_encounter(enc)
        result = self._apply_outcome(problem, enc, report, analysis, feedback,
                                     solved=solved, rank=rank, seconds=seconds,
                                     first_try=first_try, code=code)
        result["explanation_score"] = (
            coachmod.explanation_score(enc.explanation, problem)
            if enc.explanation and enc.mode != config.MODE_INTERVIEW else None)
        return result

    def _grade_forge(self, code: str, problem: Problem, enc: Encounter) -> dict:
        """TEST FORGE: the player's suite must accept the honest implementation
        and reject every Mimic."""
        harness = code + "\n\n" + problem.canonical_solution + "\n"
        probe = (harness + "\ndef __forge_check():\n"
                 "    cases = tests()\n"
                 "    for args, expected in cases:\n"
                 f"        if {problem.entry['name']}(*args) != expected:\n"
                 "            return ['REJECTS_CORRECT', len(cases)]\n"
                 "    return ['OK', len(cases)]\n")
        base = sandbox.run_tests(
            probe, {"kind": "function", "name": "__forge_check"},
            [{"name": "suite accepts the honest implementation", "args": [],
              "expected": ["OK", 0], "cmp": "any_of", "hidden": False}])

        lines, kills = [], 0
        accepts_correct = False
        suite_size = 0
        if base.phase == "syntax":
            lines.append({"name": "your suite", "status": "fail", "hidden": False,
                          "message": "Your test file does not compile."})
        elif base.tests and base.tests[0].got:
            got = base.tests[0].got
            accepts_correct = "OK" in str(got)
            try:
                suite_size = int(str(got).split(",")[-1].strip(" ]'\""))
            except ValueError:
                suite_size = 0
            lines.append({
                "name": "accepts the honest implementation",
                "status": "pass" if accepts_correct else "fail", "hidden": False,
                "message": "" if accepts_correct
                else "Your suite rejects a CORRECT implementation. One of your "
                     "expected values is wrong.",
            })

        if accepts_correct:
            for i, mutant in enumerate(problem.mutants):
                mp = (code + "\n\n" + mutant + "\n"
                      "\ndef __forge_kill():\n"
                      "    for args, expected in tests():\n"
                      f"        if {problem.entry['name']}(*args) != expected:\n"
                      "            return True\n"
                      "    return False\n")
                r = sandbox.run_tests(
                    mp, {"kind": "function", "name": "__forge_kill"},
                    [{"name": f"mimic {i + 1}", "args": [], "expected": True,
                      "cmp": "bool", "hidden": False}])
                killed = bool(r.tests and r.tests[0].passed)
                kills += killed
                lines.append({
                    "name": f"Mimic {i + 1}", "status": "pass" if killed else "fail",
                    "hidden": False,
                    "message": "" if killed
                    else "This Mimic survived your suite — it would ship.",
                })

        need = problem.mcq.get("min_kills", len(problem.mutants))
        solved = accepts_correct and kills >= need
        seconds = max(1.0, time.time() - enc.started_at)
        rank = grading.rank_for(solved=solved, hints_used=enc.hints_used,
                                seconds=seconds,
                                target_seconds=self._graced_target(problem),
                                used_phoenix=enc.used_phoenix,
                                first_try=solved and enc.submits == 1)
        feedback = {"damage": kills + int(accepts_correct),
                    "enemy_hp_total": len(problem.mutants) + 1,
                    "passed": kills + int(accepts_correct),
                    "total": len(problem.mutants) + 1,
                    "cleared": solved, "lines": lines, "slowest_ms": 0}

        class _Fake:
            phase = "tests"
            tests: list = []
            error = None
            ok = True
            all_passed = solved
            passed_count = kills
            slowest_ms = 0.0
        fake = _Fake()
        analysis = grading.Analysis(
            root_cause="" if solved else "TESTING",
            categories=[] if solved else ["TESTING"],
            narrative="" if solved else
            (f"{len(problem.mutants) - kills} Mimic(s) survived. A suite that every "
             "wrong implementation passes is not measuring anything."))
        self._write_encounter(enc)
        return self._apply_outcome(problem, enc, fake, analysis, feedback,
                                   solved=solved, rank=rank, seconds=seconds,
                                   first_try=solved and enc.submits == 1, code=code,
                                   extra={"suite_size": suite_size, "kills": kills,
                                          "mutants": len(problem.mutants)})

    def solve_puzzle(self, payload) -> dict:
        """Puzzle encounters take a structured answer rather than source code."""
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if enc.repo_id:
            return {"error": "this encounter is not a puzzle"}
        problem = self.by_id[enc.problem_id]
        if problem.encounter_kind not in puzzles.PUZZLE_KINDS:
            return {"error": "this encounter is not a puzzle"}
        enc.submits += 1
        self._write_encounter(enc)
        return self._grade_puzzle(problem, enc, payload)

    def _grade_puzzle(self, problem: Problem, enc: Encounter, payload) -> dict:
        outcome = puzzles.grade(problem, payload)
        solved = bool(outcome["solved"])
        seconds = max(1.0, time.time() - enc.started_at)
        first_try = solved and enc.submits <= 1
        rank = grading.rank_for(solved=solved, hints_used=enc.hints_used,
                                seconds=seconds,
                                target_seconds=self._graced_target(problem),
                                used_phoenix=enc.used_phoenix, first_try=first_try)
        feedback = {
            "damage": outcome["passed"], "enemy_hp_total": outcome["total"],
            "passed": outcome["passed"], "total": outcome["total"],
            "cleared": solved, "lines": outcome["lines"], "slowest_ms": 0,
        }

        class _Fake:
            phase = "tests"
            tests: list = []
            error = None
            ok = True
            all_passed = solved
            passed_count = outcome["passed"]
            slowest_ms = 0.0

        report = outcome.get("report") or _Fake()
        analysis = grading.Analysis(
            root_cause="" if solved else _PUZZLE_CAUSE.get(problem.encounter_kind,
                                                           "DEBUGGING"),
            narrative="" if solved else next(
                (line["message"] for line in outcome["lines"]
                 if line["status"] != "pass" and line["message"]), ""))
        result = self._apply_outcome(problem, enc, report, analysis, feedback,
                                     solved=solved, rank=rank, seconds=seconds,
                                     first_try=first_try, code="",
                                     extra={"puzzle": problem.encounter_kind})
        for key in ("explanation", "answer", "assembled_source"):
            if key in outcome:
                result[key] = outcome[key]
        return result

    # ======================================================================
    # MINI-REPO BATTLES
    #
    # Somebody else's codebase, a suite that mostly passes, and a clock. Every
    # rule lives in minirepo.py and none of them is re-implemented here; this is
    # the six calls of its contract, in the order an encounter uses them, plus
    # the one thing this file owns and that module does not — resolving the
    # outcome through _apply_outcome, so a Mini-Repo pays XP, loot, skills,
    # quests, artifacts and the rest exactly like any other encounter.
    # ======================================================================

    def _repo_of(self, enc: Encounter | None):
        """The Repo this encounter is fighting, or None if it is not one."""
        if enc is None or not enc.repo_id:
            return None
        return minirepo.get(enc.repo_id)

    def _repo_sealed(self, enc: Encounter) -> set:
        """What is switched off for this Mini-Repo.

        One line per capability, and every one of them asked of
        `finalexam.sealed`, which stays the only thing in this codebase that
        answers whether a capability is available. minirepo.player_view forces
        the same set again in Interview Mode; that is belt and braces, not a
        second opinion.
        """
        return {cap for cap in minirepo.SEALED_CAPABILITIES
                if finalexam.sealed(enc, cap)}

    def minirepo_board(self, *, difficulty: str = "", tag: str = "") -> dict:
        """The index cards, and which of them this player has already beaten."""
        cleared = {c[len(REPO_ID_PREFIX):] for c in self.state["solved_ids"]
                   if c.startswith(REPO_ID_PREFIX)}
        cards = minirepo.catalogue(difficulty=difficulty, tag=tag)
        return {
            "repos": [{**card, "cleared": card["id"] in cleared} for card in cards],
            "cleared": sorted(cleared),
            "blurb": ("Three to eight files somebody else wrote, a suite that "
                      "mostly passes, and a ticket. Navigate it, change it, and "
                      "hand it back with everything that was green still green."),
        }

    def start_minirepo(self, repo_id: str = "", *,
                       mode: str = config.MODE_ADVENTURE,
                       difficulty: str = "", reason: str = "MANUAL") -> dict:
        """Spawn one. CHOOSE, then OPEN — steps 1 and 2 of the contract."""
        open_repo = self._repo_of(self.encounter)
        if open_repo is not None:
            # There is a working tree on the encounter, and starting a second
            # repository would throw it away without being asked. Asking for
            # the one already open is a resume, not a refusal.
            if not repo_id or repo_id == open_repo.id:
                return self._repo_payload(open_repo, self.encounter,
                                          reason="RESUME")
            return {"error": "a mini-repo is already open",
                    "repo_id": open_repo.id,
                    "message": ("You are part-way through %s. Finish it or put "
                                "it down; your edits are still there."
                                % open_repo.title)}
        if self.state.get("interview"):
            # A measured run is open. Everything else in the overworld is
            # refused while one is, and a side fight would be the loudest
            # possible way to walk around it.
            return finalexam.refuse("BUILD")
        repo = minirepo.get(repo_id) if repo_id else None
        if repo_id and repo is None:
            return {"error": "unknown mini-repo", "repo_id": repo_id}
        if repo is None:
            cleared = {c[len(REPO_ID_PREFIX):] for c in self.state["solved_ids"]
                       if c.startswith(REPO_ID_PREFIX)}
            # `pick` widens the tier rather than returning None. It does NOT
            # widen the exclusion list, so a player who has beaten all sixteen
            # gets nothing back — and "you have finished everything, here is a
            # blank screen" is the one answer this game never gives. A repo
            # already beaten is still a fight, and a month later it is a good
            # one, so the second call is made here rather than left to chance.
            repo = (minirepo.pick(difficulty=difficulty, exclude=cleared)
                    or minirepo.pick(difficulty=difficulty))
        if repo is None:
            return {"error": "no mini-repo is available"}
        enc = Encounter(problem_id=REPO_ID_PREFIX + repo.id, mode=mode,
                        started_at=time.time(), repo_id=repo.id)
        # A Mini-Repo is a fight, and every fight gets a turn, a belt and
        # something to fight. Without these two lines a repo encounter reaches
        # _apply_outcome with no vitals and no turn state, the enemy half of the
        # turn finds nothing to act with, and a handed-back repo that fails its
        # suite costs nothing at all — which is not mercy, it is the one
        # encounter kind in the game where being wrong is free.
        enc.potion_turn = potions.new_fight().to_dict()
        self._arm_enemy(repo_problem(repo), enc)
        self._write_encounter(enc)
        self.state["stats"]["encounters"] += 1
        self.save()
        return self._repo_payload(repo, enc, reason=reason)

    def minirepo_view(self) -> dict:
        """The fight as it stands. A reload mid-repo comes back here."""
        enc = self.encounter
        repo = self._repo_of(enc)
        if repo is None:
            return {"error": "no mini-repo is open"}
        return self._repo_payload(repo, enc, reason="RESUME")

    def _repo_payload(self, repo, enc: Encounter, *, reason: str = "") -> dict:
        seal = finalexam.encounter_seal(enc)
        sealed_caps = self._repo_sealed(enc)
        problem = repo_problem(repo)
        view = minirepo.player_view(repo, mode=enc.mode, sealed=sealed_caps)
        # The player's own edits, laid back over the pristine bodies. The suite
        # is never overlaid: enc.repo_files only ever holds project paths.
        for row in view["files"]:
            saved = enc.repo_files.get(row["path"])
            if isinstance(saved, str):
                row["body"] = saved
                row["edited"] = True
        skills = self.skills
        skill_name = REPO_SKILL
        history = db.attempts_for(self.conn, problem.id)
        payload = {
            "repo": view,
            # Without the working tree: the files are in `repo.files` above,
            # already laid over with the player's edits, and sending them twice
            # only doubles the payload.
            "encounter": {**enc.to_dict(), "repo_files": {}},
            "reason": reason,
            "mode": enc.mode,
            "interview_locked": enc.mode == config.MODE_INTERVIEW,
            "seal": seal.to_dict(),
            "sealed": sorted(sealed_caps),
            # The repo's own number, through the same function every other
            # encounter's clock goes through. No BUILD grace: a Mini-Repo is
            # read time, and gear does not read faster.
            "clock_seconds": finalexam.clock_for(problem, seal),
            "target_seconds": repo.clock,
            "elapsed_seconds": max(0.0, time.time() - enc.started_at),
            "region": self._region_view(repo.realm),
            "mentor": (None if seal.blocks("MENTOR") else world.MENTORS.get(
                world.REGION_BY_ID.get(repo.realm, {}).get("mentor", "byte"))),
            "skill": "" if seal.blocks("SKILL_STATE") else skill_name,
            "skill_state": (None if seal.blocks("SKILL_STATE")
                            or skill_name not in skills
                            else skills[skill_name].to_dict()),
            "attempts_before": len(history),
            "best_time": db.best_time(self.conn, problem.id),
            # A Mini-Repo has no hint tree and cannot be probed, in any mode.
            # Said out loud so the client hides both rather than offering a
            # button that always refuses.
            "hint_count": 0,
            "probe_charges": 0,
            # The seal is decided in one place and handed in, rather than
            # guessed at again here. From the rung that takes PET onward, the
            # field is empty in the payload as well as in the refusal, so the
            # client is never drawing an animal that cannot speak.
            "companions": ([] if not pets.available_in(
                enc.mode, self.state["player"].get("region", ""),
                sealed=finalexam.sealed(enc, "PET"))
                else list(self.state["pets"].get("active", []))),
            "mana": self.state["player"]["mana"],
            "stamina": self.state["player"]["stamina"],
        }
        if enc.mode == config.MODE_INTERVIEW:
            # The same refusal-to-ship the exam payload gets. A bare assert
            # would vanish under python -O and this is the guarantee the mode
            # rests on.
            leaks = self._repo_leaks(repo, payload)
            if leaks:
                raise RuntimeError("mini-repo payload leaks: %s" % "; ".join(leaks))
        return payload

    @staticmethod
    def _repo_leaks(repo, payload: dict) -> list:
        """Anything in a sealed Mini-Repo payload that should not be there.

        The patch is the one that matters, and it is checked by searching the
        serialised payload for the literal text of every replacement — the same
        thing minirepo's own self-check does, for the same reason: a leak that
        only a structural check would catch is a leak that arrives the day
        somebody adds a field.
        """
        leaks = []
        view = payload.get("repo") or {}
        if view.get("start_file") or view.get("start_note"):
            leaks.append("the starting-file pointer survived the seal")
        if view.get("shapes"):
            leaks.append("the task shapes survived the seal")
        if view.get("targets"):
            leaks.append("the target tests survived the seal")
        if payload.get("hint_count") or payload.get("probe_charges"):
            leaks.append("a crutch is offered")
        if payload.get("mentor"):
            leaks.append("a mentor is attached to the encounter")
        if payload.get("skill") or payload.get("skill_state"):
            leaks.append("the player's own skill numbers are attached")
        blob = json.dumps(payload)
        for fix in repo.patch:
            if fix.new and fix.new in blob:
                leaks.append("the reference patch is in the payload")
                break
        return leaks

    # -- the working tree ---------------------------------------------------

    def _repo_tree(self, repo, files) -> tuple:
        """The player's working tree, or a refusal. Returns (tree, refusal).

        Three checks, and this is the only door the browser can reach them
        through: the shape (a dict of text), the paths (the files this repo
        handed out and no others), and the size. `sandbox.write_project` refuses
        a dangerous filename too and that guard is not routed around — but a
        path this repo never handed out is not a sandbox question, it is a "that
        is not what you were given" question, and answering it here is the
        difference between being told and watching the suite come back BROKEN.
        """
        if files is None:
            return {}, None
        if not isinstance(files, dict):
            return None, {"error": "the working tree must be an object of "
                                   "{path: source}"}
        known = set(repo.files) | set(repo.tests)
        tree, unknown, total = {}, [], 0
        for path, body in files.items():
            if not isinstance(path, str) or not isinstance(body, str):
                return None, {"error": "every file in the working tree must be "
                                       "text, keyed by its path"}
            if path not in known:
                unknown.append(path)
                continue
            total += len(body)
            tree[path] = body
        if unknown:
            return None, {
                "error": "not a file in this repository",
                "paths": sorted(unknown)[:8],
                "message": ("This fight is the files you were given. "
                            + ", ".join(sorted(unknown)[:3])
                            + " is not one of them."),
            }
        if total > sandbox.MAX_PROJECT_BYTES:
            return None, {
                "error": "working tree is too large",
                "message": ("A repository this size is %d bytes; you sent %d. "
                            "Nothing here needs that much text."
                            % (repo.byte_count, total)),
            }
        return tree, None

    @staticmethod
    def _repo_edits(repo, tree: dict) -> dict:
        """What the player actually changed.

        Only the files whose body differs from the one they were handed. Keeping
        the whole tree here would work and would be wrong twice: the save would
        carry several kilobytes of text the repo already owns, and every file
        would come back from a reload marked as edited — a dot beside a file
        nobody has touched is a lie about where the work is.
        """
        return {path: body for path, body in tree.items()
                if path in repo.files and body != repo.files[path]}

    def minirepo_run(self, files=None) -> dict:
        """RUN TESTS, mid-fight. Ungraded, and it changes nothing but the clock.

        Step 4 of the contract. `assemble` lays the suite down last, from the
        repo and never from the submission, so this cannot be used to find out
        what a weakened test would say.
        """
        enc = self.encounter
        repo = self._repo_of(enc)
        if repo is None:
            return {"error": "no mini-repo is open"}
        tree, refusal = self._repo_tree(repo, files)
        if refusal:
            return refusal
        enc.runs += 1
        edits = self._repo_edits(repo, tree)
        # Time to first code, the same measure every other encounter records:
        # running the suite to see what it says is reading, not writing.
        if edits and not enc.first_code_at:
            enc.first_code_at = time.time()
        enc.repo_files = edits
        self._write_encounter(enc)
        self.save()
        report = minirepo.run(repo, minirepo.assemble(repo, tree))
        sealed_caps = self._repo_sealed(enc)
        out = report.to_dict()
        # Which rows are the acceptance criteria, unless PATTERN is sealed — in
        # which case working out what the ticket is asking for is the exercise.
        show_targets = "PATTERN" not in sealed_caps
        for row in out["tests"]:
            row["target"] = show_targets and row["name"] in repo.targets
        out["targets"] = [] if not show_targets else list(repo.targets)
        out["graded"] = False
        return out

    def minirepo_submit(self, files=None, *, full_tree: bool = True) -> dict:
        """HAND IT BACK. Steps 5 and 6: the verdict, the rank, and the debrief.

        `files` is the player's WHOLE working tree, which is what the editor
        sends — every project file and every test file, as they stand. That is
        why `full_tree` defaults to True. A caller saving a single tab must pass
        `full_tree=False`, or every test file it did not send reads as a
        deletion and an honest player is accused of cheating. This is the one
        sharp edge in minirepo's API and it is documented at both ends.
        """
        enc = self.encounter
        repo = self._repo_of(enc)
        if repo is None:
            return {"error": "no mini-repo is open"}
        tree, refusal = self._repo_tree(repo, files)
        if refusal:
            return refusal
        enc.submits += 1
        if not enc.first_code_at:
            enc.first_code_at = time.time()
        enc.repo_files = self._repo_edits(repo, tree)
        seconds = max(1.0, time.time() - enc.started_at)

        verdict = minirepo.grade(repo, tree, seconds=seconds, full_tree=full_tree)
        solved = verdict.solved
        first_try = solved and enc.submits == 1
        rank = minirepo.rank_for(repo, verdict, seconds=seconds,
                                 hints_used=enc.hints_used, first_try=first_try)
        problem = repo_problem(repo)
        report = repo_report(verdict)
        feedback = self._repo_feedback(verdict)
        sealed_caps = self._repo_sealed(enc)
        analysis = grading.Analysis(
            root_cause="" if solved else self._REPO_CAUSE.get(verdict.outcome,
                                                              "DEBUGGING"),
            categories=[] if solved else [verdict.outcome],
            narrative="" if solved else verdict.message)
        self._write_encounter(enc)
        result = self._apply_outcome(
            problem, enc, report, analysis, feedback,
            solved=solved, rank=rank, seconds=seconds, first_try=first_try,
            code="", extra={
                "mini_repo": {
                    "id": repo.id,
                    "title": repo.title,
                    "verdict": verdict.to_dict(),
                    # Always. A tampered attempt is still owed the lesson and
                    # the file the cause lived in; the reference patch is the
                    # part that follows the SOLUTION seal.
                    "debrief": minirepo.debrief(repo, verdict,
                                                sealed=sealed_caps),
                    "clock_seconds": repo.clock,
                    "in_time": verdict.in_time,
                },
            })
        return result

    # Outcome -> the learning failure it represents, in the vocabulary the
    # coach, the training camps and the armour already speak. TAMPERED is not a
    # skill failure at all; it is filed under the suite, because the suite is
    # what was disrespected, and the debrief says the rest out loud.
    _REPO_CAUSE = {
        "TAMPERED": "TESTING",
        "BROKEN": "SYNTAX",
        "REGRESSED": "STATE_MANAGEMENT",
        "INCOMPLETE": "DEBUGGING",
    }

    @staticmethod
    def _repo_feedback(verdict) -> dict:
        """The verdict in the shape every other encounter reports damage in."""
        lines = [{"name": row["id"], "status": row["status"], "hidden": False,
                  "ms": row.get("ms", 0.0), "message": row.get("message", ""),
                  "target": bool(row.get("target"))}
                 for row in verdict.tests]
        if not lines:
            # BROKEN or TAMPERED: nothing ran, and a silent panel reads as a bug.
            lines = [{"name": verdict.outcome.title(), "status": "fail",
                      "hidden": False, "ms": 0.0, "message": verdict.message,
                      "target": False}]
        total = len(lines)
        passed = sum(1 for row in lines if row["status"] == "pass")
        return {"damage": passed, "enemy_hp_total": total, "passed": passed,
                "total": total, "cleared": verdict.solved, "lines": lines,
                "slowest_ms": max((row.get("ms") or 0.0) for row in lines)}

    def leave_minirepo(self) -> dict:
        """Walk out. Nothing is earned and nothing is lost; the repo is still
        there, with the same files, the next time it is opened."""
        enc = self.encounter
        repo = self._repo_of(enc)
        if repo is None:
            return {"error": "no mini-repo is open"}
        self._write_encounter(None)
        self.save()
        return {"ok": True, "repo_id": repo.id,
                "message": ("You put it down. Nothing was graded, so nothing "
                            "was earned — the repository is exactly as you "
                            "found it.")}

    # -- the opening diagnostic --------------------------------------------
    def diagnostic_trials(self) -> dict:
        state = self.state.setdefault("diagnostic", {})
        return {
            "done": bool(state.get("done")),
            "placement": state.get("placement"),
            "trials": [
                {"id": t.id, "probes": t.probes, "kind": t.kind, "prompt": t.prompt,
                 "code": t.code, "choices": list(t.choices), "narration": t.narration,
                 "fn_name": t.fn_name, "starter": t.starter,
                 "tests": [{"name": n, "args": list(a), "expected": x}
                           for n, a, x in t.tests]}
                for t in diagnostic.TRIALS
            ],
        }

    def diagnostic_check(self, trial_id: str, answer) -> dict:
        """Grade one trial. The coding trial is run in the real sandbox."""
        trial = diagnostic.TRIAL_BY_ID.get(trial_id)
        if trial is None:
            return {"error": "unknown trial"}
        if trial.kind == "mcq":
            correct = int(answer) == trial.answer
            return {"correct": correct, "expected": trial.answer,
                    "probes": trial.probes}
        tests = [{"name": n, "args": list(a), "expected": x, "cmp": "exact",
                  "hidden": False} for n, a, x in trial.tests]
        report = sandbox.run_tests(str(answer),
                                   {"kind": "function", "name": trial.fn_name},
                                   tests, timeout_ms=2500, wall_seconds=12)
        return {
            "correct": report.all_passed,
            "probes": trial.probes,
            "phase": report.phase,
            "error": report.error,
            "tests": [{"name": t.name, "status": t.status, "message": t.message}
                      for t in report.tests],
        }

    def diagnostic_finish(self, answers: dict, *, skipped: bool = False) -> dict:
        """The placement, taken once.

        TWO THINGS WERE WRONG HERE AND THE SECOND IS THE SERIOUS ONE.

        `diagnostic.seed_skills` is, by its own docstring, "the one place
        mastery moves without a graded attempt", and it is bounded so that it
        stays weak evidence: mastery caps at 35 and confidence at 18. What it
        is NOT bounded against is being called twice. `state.mastery + gain` and
        `state.unaided_clears += 1` are both cumulative, and nothing here ever
        read the `done` flag it had just written — so fifty POSTs to
        `/api/diagnostic/finish` manufactured fifty attempts, fifty clears and
        fifty UNAIDED clears, with no code run anywhere, and unaided clears are
        what `adaptive.readiness` and the castle gate are counted in. MASTERY
        MOVES ONLY ON GRADED EVIDENCE is one of the rules that cannot be
        weakened, and this was weakening it with a repeat request.

        It is a placement. You are placed once. A second call returns the
        placement already taken — not an error, because a client that retried a
        dropped response must get an answer rather than a dead end.

        And it is sealed in a measured run, like every other door that moves the
        world: `_sealed_in_interview` rather than `finalexam.sealed(enc, ...)`,
        because between two questions of a run there is no encounter to ask.
        """
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        taken = self.state.get("diagnostic") or {}
        if taken.get("done"):
            return {
                **(taken.get("placement") or {}),
                "already": True,
                "message": "You have already been placed. The ladder moves on "
                           "graded work from here.",
                "chapter": curriculum.next_objective(self.skills),
                "story": self.collect_story(),
            }
        placement = (diagnostic.skip_placement() if skipped
                     else diagnostic.evaluate(answers or {}))
        skills = self.skills
        diagnostic.seed_skills(skills, placement)
        self._write_skills(skills)
        self.state["diagnostic"] = {"done": True, "placement": placement.to_dict()}
        self.state["player"]["diagnostic_done"] = True
        self.save()
        return {
            **placement.to_dict(),
            "chapter": curriculum.next_objective(self.skills),
            "story": self.collect_story(events=("diagnostic_done",)),
        }

    def answer_mcq(self, choice: int) -> dict:
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if enc.repo_id:
            return {"error": "this encounter has no choices to pick from"}
        problem = self.by_id[enc.problem_id]
        enc.submits += 1
        correct = choice == problem.mcq.get("answer")
        seconds = max(1.0, time.time() - enc.started_at)
        rank = grading.rank_for(solved=correct, hints_used=enc.hints_used,
                                seconds=seconds,
                                target_seconds=self._graced_target(problem),
                                used_phoenix=False, first_try=enc.submits == 1)
        feedback = {"damage": int(correct), "enemy_hp_total": 1,
                    "passed": int(correct), "total": 1, "cleared": correct,
                    "lines": [{"name": "your answer",
                               "status": "pass" if correct else "fail",
                               "hidden": False,
                               "message": "" if correct else "Not the family this is."}],
                    "slowest_ms": 0}

        class _Fake:
            phase = "tests"
            tests: list = []
            error = None
            ok = True
            all_passed = correct
            passed_count = int(correct)
            slowest_ms = 0.0
        analysis = grading.Analysis(
            root_cause="" if correct else (
                "PATTERN_NOT_RECOGNIZED" if problem.encounter_kind == "PATTERN_ENCOUNTER"
                else "COMPLEXITY" if problem.encounter_kind == "COMPLEXITY_DUEL"
                else "TESTING"),
            narrative="" if correct else problem.mcq.get("explanation", ""))
        self._write_encounter(enc)
        result = self._apply_outcome(problem, enc, _Fake(), analysis, feedback,
                                     solved=correct, rank=rank, seconds=seconds,
                                     first_try=enc.submits == 1, code="")
        result["explanation"] = problem.mcq.get("explanation", "")
        result["correct_choice"] = problem.mcq.get("answer")
        return result

    # -- the one place progression changes ---------------------------------
    def _apply_outcome(self, problem: Problem, enc: Encounter, report, analysis,
                       feedback, *, solved: bool, rank: str, seconds: float,
                       first_try: bool, code: str, extra: dict | None = None) -> dict:
        player = self.state["player"]
        skills = self.skills
        skill_name = skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")
        # One clamp for all four grading paths. rank_for reads hints_used, which
        # a pet already raised; this is the separate ceiling a pet also imposes.
        if enc.rank_ceiling and rank:
            rank = _worse_rank(rank, enc.rank_ceiling)
        if solved and self.effects().get("rank_floor"):
            rank = _better_rank(rank, "B")      # an artifact, and it says so

        # -- skills
        skillmod.apply_outcome(
            skills[skill_name], solved=solved, difficulty=problem.difficulty,
            hints_used=enc.hints_used, seconds=seconds,
            target_seconds=problem.target_seconds, first_try=first_try,
            is_retest=enc.is_retest, interval_days=enc.interval_days, mode=enc.mode)
        # Fluency tiers credit PYTHON itself. A GUIDED fill-in-the-blank is filed
        # under whatever pattern it happens to use, but what it is actually
        # teaching is the language — and the curriculum's first chapters measure
        # exactly that.
        if problem.difficulty in ("GUIDED", "TUTORIAL") and skill_name != "PYTHON":
            skillmod.apply_outcome(
                skills["PYTHON"], solved=solved, difficulty=problem.difficulty,
                hints_used=enc.hints_used, seconds=seconds,
                target_seconds=problem.target_seconds, first_try=first_try,
                is_retest=enc.is_retest, mode=enc.mode)
        elif problem.spaced_repetition_family.startswith(("python_", "onboarding_")) \
                and skill_name != "PYTHON":
            skillmod.apply_outcome(
                skills["PYTHON"], solved=solved, difficulty="TUTORIAL",
                hints_used=enc.hints_used, seconds=seconds,
                target_seconds=problem.target_seconds, first_try=first_try,
                is_retest=False, mode=enc.mode)

        for secondary in problem.secondary_patterns:
            name = skillmod.PATTERN_TO_SKILL.get(secondary)
            if name and name in skills and name != skill_name:
                skillmod.apply_outcome(
                    skills[name], solved=solved, difficulty="TUTORIAL",
                    hints_used=enc.hints_used, seconds=seconds,
                    target_seconds=problem.target_seconds, first_try=first_try,
                    is_retest=False, mode=enc.mode)
        if solved and seconds <= problem.target_seconds:
            skillmod.apply_outcome(skills["SPEED"], solved=True, difficulty="EASY",
                                   hints_used=0, seconds=seconds,
                                   target_seconds=problem.target_seconds,
                                   first_try=first_try, is_retest=False, mode=enc.mode)
        if enc.is_retest and solved:
            skillmod.apply_outcome(skills["RECALL"], solved=True,
                                   difficulty=problem.difficulty, hints_used=0,
                                   seconds=seconds, target_seconds=problem.target_seconds,
                                   first_try=first_try, is_retest=True,
                                   interval_days=enc.interval_days, mode=enc.mode)
        # THE ORDER THAT MATTERS: grade first, then apply the Hand's ceiling.
        # Reversed, a clear briefly shows mastery above a ceiling the player paid
        # for, and they will see it and correctly read the cost as fake.
        for state in skills.values():
            legendaries.clamp_to_ceiling(state, self.state["hand"])
        self._write_skills(skills)
        # The tree's post-respec grip ticks down once per resolved encounter.
        classes.after_encounter(self.state.get("class") or {})

        # -- spaced repetition
        #
        # Not for hold-out content. The SRS is a teaching mechanism: it schedules
        # a family to come back in a disguise, which is the single most effective
        # way to make an unfamiliar problem familiar. It may not schedule a
        # sealed problem and it may not schedule FROM one — a sealed clear that
        # advanced its family's stage would be the hold-out quietly teaching
        # through the back door, on its own way out.
        schedule = self.schedule
        family = problem.spaced_repetition_family or problem.pattern.lower()
        entry = schedule.get(family) or srsmod.ScheduleEntry(family=family)
        if not enc.holdout:
            if problem.id not in entry.seen_problem_ids:
                entry.seen_problem_ids.append(problem.id)
                entry.seen_problem_ids = entry.seen_problem_ids[-30:]
            srsmod.schedule_after(entry, solved=solved, hints_used=enc.hints_used)
            schedule[family] = entry
            self._write_schedule(schedule)

        # -- transfer readiness
        #
        # The graded half of the measurement. The other half was taken when the
        # problem was served; this one only fills in what happened. Mastery above
        # is untouched by it and it is untouched by mastery: a sealed clear moves
        # both numbers, for completely separate reasons, out of the same evidence.
        transfer_row = (self._record_transfer(problem, enc, solved=solved,
                                              seconds=seconds, rank=rank)
                        if enc.holdout else None)

        # -- tactical resolution: weaknesses struck, resistances hit
        fx = self.effects()
        # The ground this fight was fought on. Read once: it decides the enemy's
        # element, which potions the region is generous with, and what the
        # player's own gear was or was not the right answer to.
        region_element = self._region_element(problem)
        enemy_dict = self._enemy_for(problem, enc.exposed)
        enemy_obj = tactics.Enemy(**{k: v for k, v in enemy_dict.items()
                                     if k in ("name", "sprite", "hp", "hp_max", "boss",
                                              "taunt", "colour", "difficulty",
                                              "weaknesses", "resistances", "exposed")})
        combat = tactics.resolve_combat(report, problem, enemy_obj,
                                        exposed=enc.exposed, effects=fx,
                                        hints_used=enc.hints_used)
        if combat["crits"]:
            self.state["stats"]["crits"] += len(combat["crits"])
            self.state["crit_streak"] += len(combat["crits"])
        elif not solved:
            self.state["crit_streak"] = 0

        # -- combo, xp, gold, stamina
        combo_saved = False
        if solved:
            player["combo"] += 1
            player["best_combo"] = max(player["best_combo"], player["combo"])
        elif fx.get("combo_shield", 0) and not enc.free_recast_used and player["combo"]:
            combo_saved = True
            enc.free_recast_used = True
        else:
            player["combo"] = 0
        combo = grading.combo_multiplier(player["combo"])
        base_xp = grading.xp_for(difficulty=problem.difficulty, rank=rank, combo=combo,
                                 is_retest=enc.is_retest) if solved else 4
        multiplier = 1.0 + fx.get("xp_bonus", 0.0)
        if enc.is_retest:
            multiplier += fx.get("retest_bonus", 0.0)
        if solved:
            multiplier *= combat["xp_multiplier"]
        xp = int(round(base_xp * multiplier))
        player["xp"] += xp

        # -- gold, which is now a receipt for correct Python ----------------
        #
        # `player["gold"] += xp // 3 + crits * 5` used to live here and it paid
        # for two things it should not have. It paid for TIME, because xp rises
        # with a combo a player can hold by grinding one family; and it paid for
        # COMBAT ROLLS, because five gold a crit made a purse swing on the
        # wheel rather than on correctness. economy.py owns the rate now, and
        # the crit term is gone deliberately: crits already feed xp through
        # tactics.resolve_combat's multiplier, and paying them twice is paying
        # for the dice.
        #
        # THE PURSE STAYS HERE. Every earner in economy.py REPORTS a number and
        # mutates nothing of the player's, exactly as forge.upgrade() does, so
        # this line is still the only place gold is added for an encounter.
        #
        # `blows_landed` is counted on the same branch, because the only blow a
        # graded submission lands is the one that solved it.
        if solved:
            enc.blows_landed += 1
        econ = self.state
        now = time.time()
        award = None
        purse = None
        if self._pays_into_the_world(enc):
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                award = economy.puzzle_award(
                    econ, region_id=enc.region, difficulty=problem.difficulty,
                    kind=problem.encounter_kind, problem_id=problem.id,
                    solved=solved, rank=rank, now=now)
            else:
                award = economy.encounter_award(
                    econ, region_id=enc.region, difficulty=problem.difficulty,
                    rank=rank, problem_id=problem.id, solved=solved,
                    is_retest=enc.is_retest, now=now)
            player["gold"] += economy.record(econ, award, now=now)["gold"]
            if solved:
                purse = economy.roll_purse(
                    region_id=enc.region, difficulty=problem.difficulty,
                    rank=rank, luck=fx.get("loot_luck", 0.0),
                    # The LAST phase, not every phase. See `_boss_finisher`.
                    is_boss=self._boss_finisher(enc, solved), solved=solved,
                    # READ BEFORE _resolve_boss increments it, which is why this
                    # sits above the boss block rather than below it.
                    times_defeated=self.state["boss_rematch"].get(enc.boss_id, 0),
                    rng=self._rng)
                player["gold"] += economy.record(econ, purse)["gold"]
                economy.restock(econ, enc.region, clears=1)
        previous_level = player["level"]
        player["level"] = world.level_for(player["xp"])
        player["title"] = world.title_for(player["level"])
        levels_gained = max(0, player["level"] - previous_level)
        if levels_gained:
            self.state["unspent_points"] += levels_gained * items.POINTS_PER_LEVEL
        if solved and fx.get("mana_regen"):
            player["mana"] = min(player["mana_max"],
                                 player["mana"] + int(fx["mana_regen"]))

        # -- the turn ------------------------------------------------------
        #
        # One graded submission is one turn, right or wrong. That is the rule a
        # potion is measured against — a draught rides alongside the cast and
        # never instead of it — so `_advance_turn` runs on BOTH branches below
        # or the pouch quietly stops refusing a second drink.
        #
        # A landed line ends the fight; a missed one gives the enemy its turn.
        # That asymmetry is the point: the reward for typing the right thing is
        # that nothing hits you, and the cost of typing the wrong thing is a
        # blow whose size the wheel decides. The enemy cannot end the fight
        # either way — stamina at zero routes to a training camp below, never to
        # a loss — so the only thing its turn buys is length.
        turn_state = self._advance_turn(enc, correct=solved)
        damage_taken = 0
        enemy_turn = None
        turn_open = None
        if not solved:
            base = (config.STAMINA_LOSS_SYNTAX
                    if analysis.root_cause == "SYNTAX"
                    else ENEMY_BASE_DAMAGE)
            enemy_turn = self._enemy_turn(enc, base=base)
            damage_taken = int(enemy_turn["damage"])
            self._log(enc, *(enemy_turn["lines"] or ()))
            # The player's next turn opens here, which is what lets a poisoned
            # player see the tick BEFORE they choose what to drink.
            turn_open = self._open_player_turn(enc)
            damage_taken += int(turn_open["damage"])
        else:
            player["stamina"] = min(player["stamina_max"], player["stamina"] + 1)
            player["mana"] = min(player["mana_max"], player["mana"] + 2)
        # `self.encounter` rebuilds an Encounter from the save on every read, so
        # everything the turn just moved — the pouch's lock, the dose pool, both
        # status lists, the enemy's focus — is in this object and nowhere else
        # until it is written. A fight that forgot its own poison between two
        # submissions is the bug this single line exists to prevent.
        self._write_encounter(enc)

        # -- armor: failures crack it, debugging repairs it
        armor_event = None
        if problem.encounter_kind == "DEBUG_BATTLE" and solved:
            piece = next((t.split(":")[1] for t in problem.tags
                          if t.startswith("armor:")), "chestplate")
            before = self.state["armor"].get(piece, 0)
            gain = {"TUTORIAL": 20, "EASY": 30, "MEDIUM": 45,
                    "HARD": 60}.get(problem.difficulty, 30)
            gain = int(gain * (1.0 + fx.get("armor_repair", 0.0)))
            self.state["armor"][piece] = min(100, before + gain)
            self.state["stats"]["armor_repairs"] += 1
            armor_event = {"piece": piece, "before": before,
                           "after": self.state["armor"][piece], "repaired": True}
        elif not solved:
            piece = {"SYNTAX": "helmet", "OFF_BY_ONE": "boots",
                     "STATE_MANAGEMENT": "gauntlets", "EDGE_CASE": "chestplate",
                     "INEFFICIENT_ALGORITHM": "shield"}.get(
                         analysis.root_cause, "chestplate")
            before = self.state["armor"].get(piece, 0)
            self.state["armor"][piece] = max(0, before - 12)
            armor_event = {"piece": piece, "before": before,
                           "after": self.state["armor"][piece], "repaired": False}

        # -- upkeep: what it cost to keep showing up ------------------------
        #
        # THE ONE CALL SITE THE CEILING DEPENDS ON. `upkeep.wear_encounter`
        # writes to state["armor"] — the same integers the hero sprite is drawn
        # from, so integrity IS durability and there is no second bar — and the
        # two keywords below are what turn its "repair stays under a third of
        # income" claim from a tuning hope into arithmetic:
        #
        #   pay_scale    the taper economy just applied. A grinder's wear falls
        #                in step with a grinder's income instead of outrunning it.
        #   gold_earned  what this fight actually paid. A struggling player's
        #                bill is clamped against a struggling player's purse.
        #
        # upkeep.self_check()["worst_player_wired"] sweeps every difficulty
        # against every rank against a player taking twelve hits and comes back
        # at exactly a third in the worst square. The same sweep with these two
        # keywords left off comes back at 83%. That gap is the cost of not
        # passing two arguments, which is why they are passed here and not
        # defaulted somewhere convenient.
        #
        # Sealed, none of it happens: a measured run does not read the loadout,
        # so there is nothing to wear out and nothing to mend. An exam that
        # quietly billed you afterwards would be an exam that punished you for
        # sitting it.
        upkeep_sealed = finalexam.sealed(enc, upkeep.UPKEEP_CAPABILITY)
        wear = upkeep.wear_encounter(
            self.state, difficulty=problem.difficulty,
            hits_taken=enc.hits_taken, blows_landed=enc.blows_landed,
            pay_scale=float((award.multipliers or {}).get("taper", 1.0))
            if award is not None else 1.0,
            gold_earned=(int(award.gold) + int(purse.gold if purse else 0))
            if award is not None else None,
            sealed=upkeep_sealed)
        if award is not None:
            # What the town's loop report divides the repair bill by. Income is
            # banked as it is earned so `loop_report` can answer "what share of
            # what you made since you were last here" without guessing a rate.
            upkeep.record_income(self.state,
                                 int(award.gold) + int(purse.gold if purse else 0))
        # The refill, the afflictions that expire with the fight, and the
        # low-focus floor that guarantees the map spells are always castable.
        # Only on a resolved fight, which is what this method is.
        battle_end = upkeep.after_battle(self.state, statuses=enc.statuses,
                                         sealed=upkeep_sealed)

        # -- inventory / progression
        if solved:
            if problem.id not in self.state["solved_ids"]:
                self.state["solved_ids"].append(problem.id)
            if problem.pattern not in self.state["grimoire"]:
                self.state["grimoire"].append(problem.pattern)
        self.state["recent_ids"].insert(0, problem.id)
        self.state["recent_ids"] = self.state["recent_ids"][:40]
        # `encounters` counted submissions, so 60 encounters with 19 retries read
        # as 79. It is incremented in start_encounter now; this counts what it
        # was actually counting, under its own name.
        self.state["stats"]["submissions"] = int(
            self.state["stats"].get("submissions", 0)) + 1
        if enc.mode != config.MODE_INTERVIEW:
            log = self.state["session"].setdefault("log", [])
            log.append({"id": problem.id, "family": family,
                        "pattern": problem.pattern, "kind": problem.encounter_kind,
                        "solved": bool(solved), "unaided": enc.hints_used == 0,
                        "at": time.time()})
            self.state["session"]["log"] = log[-80:]

        weapon_event = self._advance_weapons(skills)
        new_achievements = self._check_achievements(skills, problem, solved, rank,
                                                    first_try, seconds)
        companion_event = self._check_companions(skills)

        # -- boss
        boss_event = None
        if enc.boss_id:
            boss_event = self._resolve_boss(
                enc, solved, rank, seconds,
                passed=int(feedback.get("passed", 0) or 0),
                total=int(feedback.get("total", 0) or 0))

        # -- training camp / remediation on failure
        camp = None
        remediation = None
        if not solved:
            camp = adaptive.training_camp(analysis.root_cause, skills, skill_name)
            remediation = adaptive.remediation_plan(self.teachable, analysis.root_cause,
                                                    problem, skills)
        # HITTING THE FLOOR IS ASKED BEFORE DEATH IS, because the two answer
        # different questions and only one of them is new. `check` adjudicates
        # and, if the verdict is death, rewinds the game to the last waking
        # point and hands back the state to adopt — the same contract as
        # saves.load_slot. A measured run is death-proof and comes back as a
        # reprieve at one health, since killing a player mid-run would destroy
        # graded work in progress.
        stamina_zero = player["stamina"] <= 0
        death_out = death.check(self.conn, self.state, cause="enemy_turn",
                                encounter=enc)
        died = bool(death_out.get("died"))
        if died:
            self.state = death_out["state"]
            player = self.state["player"]
        if stamina_zero:
            # DEATH REPLACED THE HEAL, NOT THE TEACHING. The player who reached
            # the floor is the one who most needs the remediation, and that is
            # as true of a player who died as of one who was spared — they read
            # it when they wake. Only the heal is conditional, because death.py
            # has already decided what health they open their eyes on and a
            # second opinion here would overwrite it.
            camp = camp or adaptive.training_camp(analysis.root_cause or "PYTHON_RECALL",
                                                  skills, skill_name)
            if not died:
                player["stamina"] = max(4, player["stamina_max"] // 3)

        # -- loot
        drop = None
        if solved:
            drop = items.roll_drop(
                difficulty=problem.difficulty, rank=rank,
                luck=fx.get("loot_luck", 0.0),
                is_boss=self._boss_finisher(enc, solved),
                skill=skill_name,
                owned=set(self.state["inventory"]),
                rng=self._rng,
                upgrade=int(enc.temp_effects.get("loot_upgrade", 0)),
                critical=bool(combat["crits"]))
            if drop:
                self._take_drop(drop)

        # -- potions
        # The same loot path, the same knobs, one more roll. Gear and potions
        # are INDEPENDENT and a fight may pay both: gear is the reward loop and
        # a potion is ammunition, and ammunition that arrives only when a trophy
        # does would stop being a decision. The region's affinity biases WHICH
        # kind — the marsh hands out antidotes because the marsh is full of
        # poison — which is aesthetics and tactics agreeing for once.
        potion_drop = None
        if solved:
            potion_drop = potions.roll_monster_drop(
                difficulty=problem.difficulty, rank=rank,
                luck=fx.get("loot_luck", 0.0),
                is_boss=bool(enc.boss_id),
                affinity=str(region_element or "").lower(),
                rng=self._rng)
            if potion_drop:
                got = potions.grant(self.state, potion_drop)
                potion_drop["held"] = got.get("held", 0)
                # Overflow is surfaced rather than swallowed. A pouch that
                # silently eats loot is a pouch the player stops trusting.
                potion_drop["overflow"] = got.get("overflow", 0)

        # -- metal
        # One call site, weighted the way loot already is: the region decides
        # WHICH metal, the difficulty and the rank decide HOW MUCH, and a boss
        # always pays. forge.roll_metal returns None in town, on a miss and in a
        # sealed run — a metal is gear progress and gear does not accrue in a
        # measured run — so it is called unconditionally and the mode question
        # is asked once, inside forge.active(). This covers every graded fight
        # the game has: encounters, elites, dungeon rooms and bosses all resolve
        # through here.
        metal = None
        if solved:
            metal = forge.roll_metal(
                region_id=self._metal_region(),
                difficulty=problem.difficulty, rank=rank,
                luck=fx.get("loot_luck", 0.0),
                is_boss=bool(enc.boss_id), encounter=enc, rng=self._rng)
            if metal:
                forge.add_metal(self._forge_state(), metal["metal"],
                                metal["units"])
                metal["held"] = forge.held(self._forge_state(), metal["metal"])
                metal["blurb"] = forge.METAL_BY_ID[metal["metal"]].blurb
                metal["tell"] = forge.METAL_BY_ID[metal["metal"]].tell

        # -- secrets: hidden rewards with real discovery conditions
        secrets = self._check_secrets(problem, enc, solved, rank, combat, report,
                                      seconds=seconds, armor_event=armor_event)

        # -- the world layer: quests, companions, events, artifacts, upgrades.
        # All of it hangs off this one method because _apply_outcome is the one
        # place progression changes, and a second place would eventually disagree
        # with this one about what a clear is worth.
        world_result = self._advance_world(
            problem, enc, solved=solved, rank=rank, seconds=seconds,
            skill_name=skill_name, first_try=first_try, fx=fx,
            levels_gained=levels_gained, analysis=analysis)

        db.record_attempt(
            self.conn, problem_id=problem.id, pattern=problem.pattern,
            family=family, difficulty=problem.difficulty, mode=enc.mode,
            encounter_kind=problem.encounter_kind, solved=int(solved), rank=rank,
            hints_used=enc.hints_used, seconds=seconds,
            target_seconds=problem.target_seconds, runs=enc.runs,
            syntax_errors=enc.syntax_errors,
            tests_passed=feedback["passed"], tests_total=feedback["total"],
            first_try=int(first_try), is_retest=int(enc.is_retest),
            root_cause=analysis.root_cause, declared_pattern=enc.declared_pattern,
            # Two counting questions the hidden sages ask that nothing was
            # recording: WHERE a fight happened, and whether the player named
            # the bug before being told. Both default to '' in the schema, so
            # every row written before they existed reads as "not recorded".
            region=enc.region, declared_cause=enc.declared_cause,
            time_to_first_code=(enc.first_code_at - enc.started_at)
            if enc.first_code_at else 0.0,
            submitted_code=code[:20000])

        # --- narrative: which events did this outcome actually produce?
        events = ["encounter_cleared"] if solved else []
        if solved and enc.hints_used == 0:
            events.append("first_unaided_clear")
        if rank == "S":
            events.append("first_s_rank")
        if solved and problem.difficulty == "MEDIUM" and enc.hints_used == 0:
            events.append("first_medium_unaided")
        # CLEARED MEANS THE LAST PHASE FELL. A boss is four to six graded solves
        # now, and firing the story event on the first of them would hand the
        # player the beat for something they are still standing in front of.
        if enc.boss_id and solved and (boss_event or {}).get("defeated"):
            events.append("first_boss_cleared")
        if enc.is_retest and solved and enc.interval_days >= 7:
            events.append("retest_survived_7d")
        if armor_event and armor_event.get("repaired"):
            events.append("armor_repaired")
        if levels_gained:
            events.append("level_gained")
        if drop:
            events.append("loot_taken")
        if metal:
            events.append("metal_taken")
        if potion_drop:
            events.append("potion_taken")
        if enc.probes_used and any(l for l in enc.probe_log if l.get("correct")):
            events.append("probe_correct")
        if player["combo"] >= 5:
            events.append("combo_five")
        if solved and problem.id in self.state["perf_failed_ids"]:
            events.append("perf_recovered")
        if solved and any(not a["solved"] for a in db.attempts_for(self.conn, problem.id)):
            events.append("comeback_clear")
        if world_result["quests_completed"]:
            events.append("quest_completed")
        if world_result["world_events"]:
            events.append("world_event")
        if world_result.get("companion_fell"):
            events.append("companion_fell")
        if any(row.get("pet") == pets.RETURN_ID
               for row in world_result.get("found_pets") or ()):
            events.append("companion_returned")

        history = db.attempts_for(self.conn, problem.id)
        seal = finalexam.encounter_seal(enc)
        reply = coachmod.coach(mode=enc.mode, analysis=analysis, problem=problem,
                               report=report, hints_used=enc.hints_used,
                               seconds=seconds, history=history,
                               attempts_on_problem=len(history))

        interval = srsmod.interval_days(entry.stage, entry.ease)
        result = {
            "solved": solved, "rank": rank, "xp": xp, "combo": player["combo"],
            "combo_multiplier": combo, "seconds": round(seconds, 1),
            "target_seconds": problem.target_seconds,
            "feedback": feedback,
            "analysis": {"root_cause": analysis.root_cause,
                         "categories": analysis.categories,
                         "narrative": analysis.narrative},
            "coach": ({"available": False, "questions": [], "analysis": "",
                       "next_steps": [], "reveal_solution": False}
                      if seal.blocks("COACH") else
                      {"available": reply.available, "questions": reply.questions,
                       "analysis": reply.analysis, "next_steps": reply.next_steps,
                       "reveal_solution": reply.reveal_solution}),
            "armor_event": armor_event,
            "weapon_event": weapon_event,
            "companion_event": companion_event,
            "achievements": new_achievements,
            "boss": boss_event,
            "training_camp": camp,
            "remediation": remediation,
            "stamina": player["stamina"], "mana": player["mana"],
            "stamina_triggered_camp": stamina_zero,
            # The death sequence the client plays: the three slowing beats, the
            # black, the report of what was lost and what was kept, and where
            # the player wakes. None on every ordinary turn. A reprieve carries
            # the same shape and says nobody died — a measured run floors at one
            # health rather than ending, which is why it is reported separately
            # instead of being silently indistinguishable from surviving.
            "death": death_out if death_out.get("died") else None,
            "reprieve": (death_out if (not death_out.get("died")
                                       and death_out.get("reason") == "reprieve")
                         else None),
            "damage_taken": damage_taken,
            "next_retest_days": (0.0 if enc.holdout
                                 else round(interval, 1) if solved else 0.5),
            "skill": "" if seal.blocks("SKILL_STATE") else skill_name,
            "skill_state": (None if seal.blocks("SKILL_STATE")
                            else skills[skill_name].to_dict()),
            "level": player["level"], "title": player["title"],
            "canonical_solution": (problem.canonical_solution
                                   if (solved or reply.reveal_solution)
                                   and not seal.blocks("SOLUTION") else None),
            "provenance": {"source_type": problem.source_type,
                           "company": problem.reported_company,
                           "note": problem.provenance_note},
            "combat": {
                "damage": combat["damage"],
                "crits": combat["crits"],
                "resisted": combat["resisted"],
                "xp_multiplier": combat["xp_multiplier"],
                "probes_used": enc.probes_used,
                "exposed": enc.exposed,
            },
            "loot": drop,
            "potion": potion_drop,
            "metal": metal,
            # -- the turn, as the battle HUD needs to draw it ----------------
            "turn": int(enc.turn),
            "turn_state": turn_state,
            "enemy_turn": enemy_turn,
            "turn_open": turn_open,
            "statuses": list(enc.statuses),
            "enemy_statuses": list(enc.enemy_statuses),
            "poison": dict(enc.poison),
            "enemy_vitals": dict(enc.enemy_vitals),
            "element": {
                # Sealed the same way `_encounter_payload` seals it. The
                # region's weather is public map information, but WHICH weather
                # this fight was fought in is a reading of the room, and a
                # measured run is not given readings — not on the way in, and
                # not on the way out either.
                "region": "" if seal.blocks("WEAKNESS_MAP") else region_element,
                "player": self._player_element(enc),
                "enemy": (enc.enemy_vitals or {}).get("element", ""),
                "matchup": elements.matchup(
                    self._player_element(enc),
                    (enc.enemy_vitals or {}).get("element", elements.NEUTRAL))[1],
            },
            "pouch": potions.pouch_view(
                self._pouch(), player=player,
                turn_state=potions.TurnState.from_dict(enc.potion_turn),
                poison=potions.Poison.from_dict(enc.poison), encounter=enc,
                statuses=self._load_statuses(enc.statuses)),
            "combat_log": list(enc.combat_log),
            "secrets": secrets,
            "levels_gained": levels_gained,
            "unspent_points": self.state["unspent_points"],
            "combo_saved": combo_saved,
            "gold": player["gold"],
            # What the fight paid and what it cost to keep showing up. Both are
            # here rather than in a second round trip, because the two numbers
            # only mean anything beside each other: the whole of upkeep's claim
            # is that the second is a small share of the first.
            "award": award.to_dict() if award is not None else None,
            "purse_drop": purse.to_dict() if purse is not None else None,
            "wear": wear,
            "after_battle": battle_end,
            "upkeep": upkeep.condition(self.state),
            "alarm": upkeep.alarm(self.state),
            "enemy": enemy_dict,
        }
        result.update(world_result)
        if transfer_row is not None:
            # What this one encounter did to the second number, said by the
            # engine rather than inferred by the client. `counted` is the whole
            # story: sealed, unaided, and the first of its lineage.
            regrade = bool(transfer_row.get("regrade"))
            if regrade:
                # A second run at a sealed problem that was already graded. It
                # is allowed — nothing here dead-ends, and the practice is worth
                # having — but it is practice, and saying "it counts" under a
                # green tick when the ledger did not move is how a player ends
                # up trusting a number that was never measured.
                note = ("You have already been measured on this one, and that "
                        "measurement stands. Running it again is practice: it "
                        "moves mastery like any other attempt and it cannot "
                        "move transfer readiness in either direction.")
            elif transfer_row["counted"]:
                note = ("This was a sealed problem you had never met in any "
                        "form. It counts toward transfer readiness, and it "
                        "cannot be asked of you again.")
            else:
                note = ("This was a sealed problem, but not the first time you "
                        "have met this exercise. It moves mastery like any "
                        "other clear and it does not move transfer readiness.")
            result["transfer"] = {
                "holdout": True,
                "first_encounter": bool(transfer_row["first_encounter"]),
                # `counted` describes what THIS submission did to the number, so
                # a re-run of an already-graded problem reports False: the row it
                # would have counted for was written by somebody else's keystroke.
                "counted": bool(transfer_row["counted"]) and not regrade,
                "measurement_stands": regrade,
                "note": note,
                "readiness": self.transfer_report(),
            }
        if seal.blocks("PET"):
            result["pet"] = None
            result["companion_line"] = ""
        if extra:
            result.update(extra)

        if solved or enc.mode == config.MODE_INTERVIEW:
            self._write_encounter(None)

        # Story beats are collected AFTER the outcome is folded in, so a beat
        # whose trigger is "reach mastery 30" fires on the attempt that reaches it
        # rather than on the one after.
        result["story"] = self.collect_story(events=events)
        result["chapter"] = curriculum.next_objective(self.skills)
        # LAST, and unconditional. Two things move the skill-point total and
        # neither is a level-up on its own: a graduated chapter grants a point
        # with no level attached, and collect_story pays beat XP that can cross
        # a level boundary right here, after _advance_world has already run.
        # Syncing earlier left state["class"]["points"] one encounter behind
        # what tree_view showed — and the save carried the smaller number, so
        # the point was refused until the player happened to open the screen.
        # sync_points is a pure recompute from evidence, so calling it on every
        # resolved encounter cannot grant anything twice.
        self._sync_class_points()
        self.save()
        return result

    def _take_drop(self, drop: dict) -> None:
        if drop.get("kind") == "consumable":
            key = drop["id"]
            self.state["consumables"][key] = self.state["consumables"].get(key, 0) + 1
            return
        if drop.get("kind") == "potion":
            # potions.WIRING §7. Today nothing reaches here carrying a potion —
            # the two roll sites grant directly, because both of them want the
            # overflow report and this method has nowhere to put one — but this
            # is the drop handler, and a drop envelope that fell through it into
            # the inventory would appear as an unequippable item with no slot.
            # Cheaper as a named arm than as a bug report.
            report = potions.grant(self.state, drop)
            drop["held"] = report.get("held", 0)
            drop["overflow"] = report.get("overflow", 0)
            return
        item_id = drop["id"]
        if item_id not in self.state["inventory"]:
            self.state["inventory"].append(item_id)
            self.state["stats"]["items_found"] += 1
        # auto-equip into an empty slot so a new drop is felt immediately
        slot = drop["slot"]
        if slot.startswith("ring"):
            slot = ("ring1" if not self.state["equipped"].get("ring1")
                    else "ring2" if not self.state["equipped"].get("ring2") else None)
        if slot and not self.state["equipped"].get(slot):
            self.state["equipped"][slot] = item_id
            drop["auto_equipped"] = True
        self._sync_caps()

    # -- the world layer, folded in one pass -------------------------------
    def _pet_evidence(self) -> dict:
        """The flat snapshot pets.newly_found reads. Assembled once per clear."""
        skills = self.skills
        counters = self._sage_counters()
        rows = self.conn.execute(
            "SELECT family, COUNT(DISTINCT problem_id) AS n FROM attempts"
            " WHERE solved = 1 AND hints_used = 0 GROUP BY family").fetchall()
        families = {r["family"]: r["n"] for r in rows}
        retests = {}
        for row in self.conn.execute(
                "SELECT pattern, COUNT(*) AS n FROM attempts"
                " WHERE solved = 1 AND is_retest = 1 GROUP BY pattern").fetchall():
            name = skillmod.PATTERN_TO_SKILL.get(row["pattern"], "PYTHON")
            retests[name] = retests.get(name, 0) + row["n"]
        retests[""] = sum(retests.values())
        streak = 0
        for row in db.recent_attempts(self.conn, limit=60):
            if row["solved"] and not row["hints_used"]:
                streak += 1
            elif row["solved"]:
                break
        return {
            "families": families,
            "skills": {name: {"mastery": s.mastery,
                              "unaided_clears": s.unaided_clears,
                              "clears": s.clears}
                       for name, s in skills.items()},
            "bosses_unaided": [r["boss_id"] for r in db.boss_history(self.conn)
                               if r["defeated"] and not r["hints_used"]],
            "regions_cleared": list(world.unlocked_regions(
                skills, set(self.state["cleared_bosses"]))),
            "dungeons": dict(self.state["quests"].get("depths", {})),
            "retests": retests,
            "no_hint_streak": streak,
            "perf_cleared": len(self.state["perf_failed_ids"]),
            "probes_correct": self.state["stats"].get("probes_correct", 0),
            # The barrow's debt, which is what the legendary return is gated on.
            # A return that could happen before the loss would not be a return.
            "starter_fallen": pets.STARTER_ID in (
                self.state["pets"].get("fallen") or []),
            # Dungeon floors walked with no companion, no spell and no item.
            # MIMIC's condition, and it is not a place — it is a way of arriving.
            "solo_floors": int(self.state["stats"].get("solo_floors", 0)),
            "stats": {**self.state["stats"], **db.attempt_stats(self.conn)},

            # -- what regalia.py, sages.py and nothing else read ------------
            #
            # ONE SNAPSHOT, three readers. pets.py owns the evidence vocabulary
            # and its evaluator; regalia.py and sages.py reach for the same
            # `pets._discovery_row`, so a second opinion about what an unaided
            # clear is cannot exist. All this method does is answer more of the
            # questions that evaluator knows how to ask.
            #
            # `pets_found` is regalia's one addition and its whole gate.
            "pets_found": list(self.state["pets"].get("found", [])),
            # `arts` is what the last four sages gate on: the ladder is a
            # ladder, and the Coliseum will not see somebody who has not already
            # been taught three times.
            **sages.evidence_patch(self.state[SAGES_STATE_KEY]),
            # Casting, as opposed to submitting. Both are folded by
            # incantation.record_cast into the movebook they belong to.
            "clean_cast_streak": int(
                self.state["moveset"].get("best_clean_streak", 0)),
            "recalled_casts": int(
                self.state["moveset"].get("recalled_casts", 0)),
            # The counting questions, answered in SQL over `attempts` rather
            # than by a counter banked in the save. A banked counter can
            # disagree with the history it was counting; a query cannot.
            #
            # SPELLED OUT, NOT SPLATTED. `sages.self_check()["wiring"]` reads
            # THIS FUNCTION'S SOURCE for `"key":` literals to decide which
            # sages are findable, so a `**counters` here would leave it
            # reporting nine sages as unreachable while they were being reached.
            # A report that lies in the safe direction is still a report that
            # lies.
            "region_clears": counters["region_clears"],
            "regions_touched": counters["regions_touched"],
            "first_try": counters["first_try"],
            "lineage_pairs": counters["lineage_pairs"],
            "beat_own_time": counters["beat_own_time"],
            "root_cause_correct": counters["root_cause_correct"],
            # `lifo_clears` IS DELIBERATELY ABSENT. See `_sage_counters`.
        }

    def _sage_counters(self) -> dict:
        """db.evidence_counters, with patterns mapped through to skills.

        The mapping lives in `skills.PATTERN_TO_SKILL` and nowhere else, which
        is why db.py returns raw patterns and this method does the translation.
        """
        raw = db.evidence_counters(self.conn)
        first_try: dict = {}
        for pattern, count in (raw.get("first_try_by_pattern") or {}).items():
            name = skillmod.PATTERN_TO_SKILL.get(pattern, "PYTHON")
            first_try[name] = first_try.get(name, 0) + int(count)
        first_try[""] = sum(first_try.values())
        return {
            "region_clears": dict(raw.get("region_clears") or {}),
            "regions_touched": int(raw.get("regions_touched", 0)),
            "first_try": first_try,
            "lineage_pairs": int(raw.get("lineage_pairs", 0)),
            "beat_own_time": int(raw.get("beat_own_time", 0)),
            "root_cause_correct": int(raw.get("root_cause_correct", 0)),
        }

    # NOT MEASURED, AND SAID SO RATHER THAN FAKED.
    #
    # sages.DISCOVERY's `lifo_clears` clause wants "encounters cleared in the
    # reverse of the order offered", and nothing in this engine ever OFFERS a
    # list of encounters: `next_encounter` serves exactly one problem, chosen by
    # the selector. There is no order to reverse, so there is no honest number
    # to report — and `_pet_evidence` therefore does not emit the key at all,
    # rather than emitting a zero that would read as a measurement.
    #
    # The consequence is one sage. `mines` has a single discovery clause and it
    # is this one, so the Stack & Queue Mines sage is in the world and cannot be
    # found. That is named by `sages.self_check()["wiring"]`, which reads this
    # file's source to work it out, and it is shown at the board rather than
    # hidden: `sage_board()` renders the clause at zero next to a silhouette.
    # Whoever makes selection offer a CHOICE of encounters closes it by
    # recording which of the offered ids was taken; nothing else has to change.

    def _artifact_conditions(self, enc: Encounter, *, solved: bool,
                             seconds: float, problem: Problem) -> set:
        """Which of legendaries.CONDITIONS this encounter actually satisfied.

        Every one is derived from something already graded. None of them is a
        thing the player can assert about themselves.
        """
        found = set()
        if enc.hints_used == 0:
            found.add("no_spell_cast")
        if solved and enc.submits <= 1:
            found.add("no_failed_submission")
        if solved and seconds <= problem.target_seconds * 0.5:
            found.add("under_half_target")
        if solved and enc.submits > 1:
            found.add("after_a_loss")
        if enc.probe_log and all(p.get("correct") for p in enc.probe_log):
            found.add("every_probe_correct")
        if enc.probe_log and enc.probe_log[0].get("correct"):
            found.add("first_probe_correct")
        if int(self.state["hand"].get("uses", 0)) > 0:
            found.add("hand_worn_once")
        else:
            found.add("never_worn_hand")
        # The run this encounter was fought inside, AFTER the room was resolved.
        # Reading state[STATE_KEY] here instead would see the boss room still
        # uncleared on the one clear that completes the dungeon — and after the
        # descent closes, see nothing at all — so "every_room" and "full_depth"
        # could never both be true and the four dungeon artifacts were
        # unwinnable. _advance_dungeon parks the resolved pair here for exactly
        # this read; it is per-encounter scratch and never saved.
        resolved = getattr(self, "_resolved_dungeon", None)
        run = (resolved[1] if resolved else self.state.get(dungeons.STATE_KEY)) or {}
        if run:
            # Both of these are written by this engine's own dungeon handlers,
            # because the run state dungeons.enter() hands back does not record
            # either and inventing a key inside its dict would be a second owner.
            if not run.get("retreated"):
                found.add("no_retreat")
            if run.get("off_map"):
                found.add("off_map")
            dungeon = (resolved[0] if resolved
                       else self._dungeon_for(run["dungeon"], run.get("seed")))
            if len(set(run.get("cleared", []))) >= sum(
                    1 for r in dungeon.rooms if r.demands_solving):
                found.add("every_room")
            if self._dungeon_depth(dungeon, run) >= dungeon.max_depth:
                found.add("full_depth")
        return found

    def _advance_world(self, problem: Problem, enc: Encounter, *, solved: bool,
                       rank: str, seconds: float, skill_name: str,
                       first_try: bool, fx: dict, levels_gained: int,
                       analysis) -> dict:
        """Quests, companions, world events, artifacts, upgrades and the dungeon,
        all from the facts this encounter actually produced."""
        out = {"quests_ready": [], "quests_completed": [], "pet": None,
               "found_pets": [], "world_events": [], "artifacts": [],
               "upgrades": [], "daily_completed": [], "dungeon": None,
               "incantations_learned": [], "companion_line": "",
               # The barrow's scene, when this clear was the one that closed it.
               "companion_fell": None,
               # The ten systems' own returns, so a client reads one payload.
               "found_regalia": [], "found_sages": [], "trial": None,
               "sanctuary": None, "hunt": None}
        if enc.mode == config.MODE_INTERVIEW:
            # A measured run pays nothing into the world. That is the point.
            return out

        ready = adaptive.readiness(
            skills=self.skills, schedule=self.schedule,
            stats=db.attempt_stats(self.conn),
            unaided_easy=self._unaided_counts()[0],
            unaided_medium=self._unaided_counts()[1])

        # -- quests: graded facts only, never intent
        if solved:
            out["quests_ready"] = quests.note_clear(
                self.state, pattern=problem.pattern,
                family=problem.spaced_repetition_family,
                difficulty=problem.difficulty, skill=skill_name,
                unaided=(enc.hints_used == 0),
                under_target=(seconds <= problem.target_seconds))
            if problem.encounter_kind in puzzles.PUZZLE_KINDS:
                quests.note_puzzle(self.state, problem.encounter_kind)
            # THE SANCTUARY COOLDOWN CLOCK, and it is one line next to the quest
            # clock on purpose. It counts PROBLEMS SOLVED rather than minutes
            # elapsed, so a player who puts the game down for a week does not
            # come back to a hidden healer who has been resting without them.
            sanctuary.note_clear(self.state)

        # -- the broker's open contract, if there is one
        #
        # Every submission, right or wrong, graded or not: a trial that only saw
        # the clears would be a trial you could fail for free. `submit_to_trial`
        # returns {} when nothing is open, so there is no `if` to write.
        trial = economy.submit_to_trial(
            self.state,
            problem_id=problem.id, solved=solved, rank=rank,
            hints_used=enc.hints_used, seconds=seconds,
            target_seconds=problem.target_seconds, first_try=first_try,
            is_retest=enc.is_retest, difficulty=problem.difficulty,
            skill=problem.pattern,
            puzzle_kind=(problem.encounter_kind
                         if problem.encounter_kind in puzzles.PUZZLE_KINDS else ""),
            # The two regions that take the reading away. A trial that asked for
            # a declared pattern in a place where nothing tells you the pattern
            # would be asking for a guess.
            pattern_shown=enc.region not in ("null_kings_castle", "coding_coliseum"),
            companion_spoke=bool(enc.pet_spoke))
        out["trial"] = trial or None

        # -- companions: bond on evidence, discovery on the same pass
        pet_state = self.state["pets"]
        for pet_id in list(pet_state.get("active", [])):
            gained = pets.bond_gain(
                pet_id, skill=skill_name, cleared=solved, rank=rank,
                hints_used=enc.hints_used,
                intervened=bool(enc.pet_spoke),
                is_retest=enc.is_retest)
            if gained:
                out["pet"] = pets.award(pet_state, pet_id, gained)
        if solved:
            evidence = self._pet_evidence()
            for row in pets.newly_found(evidence, pet_state.get("found", [])):
                # discovery_progress keys the pet as "pet", not "id"
                if pets.grant(pet_state, row["pet"], at=time.time()):
                    out["found_pets"].append(row)

            # -- regalia: earned by a deed, never bought, never dropped ----
            #
            # The same evidence snapshot, one pass later, because the snapshot
            # already carries `pets_found` and an object for an animal you have
            # never met is a spoiler with a progress bar. `newly_found` is the
            # only reader; `grant` is the only writer.
            gear_state = self.state[regalia.REGALIA_STATE_KEY]
            for row in regalia.newly_found(evidence, gear_state.get("found", [])):
                got = regalia.grant(gear_state, row["regalia"])
                if got.get("found"):
                    out["found_regalia"].append({**row, **got})

            # -- the sages: found by having done the area's work ------------
            #
            # Discovery only. Meeting one costs nothing, opens nothing and
            # grants nothing: the gauntlet is still five problems and the art is
            # still behind them. This is the same division pets draws — evidence
            # is evaluated in one place and acted on in another.
            sage_state = self.state[SAGES_STATE_KEY]
            for row in sages.newly_found(evidence, sage_state.get("found", [])):
                if sages.meet(sage_state, row["sage"], at=time.time()):
                    out["found_sages"].append(row)
        if out["found_pets"] or pet_state.get("active"):
            speaker = (out["found_pets"][0]["pet"] if out["found_pets"]
                       else pet_state["active"][0])
            out["companion_line"] = pets.outcome_line(
                speaker, cleared=solved,
                helped=bool(enc.pet_spoke))

        # -- the world itself: events fire once, and only on what is now true
        advanced = progression.advance(self.state, self.skills, readiness=ready)
        out["world_events"] = advanced["events"]
        self._count_world_stats()

        # -- the daily board, which generated quests and could never finish one
        out["daily_completed"] = self._credit_daily(problem, enc, solved=solved,
                                                    rank=rank, seconds=seconds)

        # -- the dungeon this encounter was fought inside. This runs BEFORE the
        #    artifact roll: a relic earned by clearing every room must be able
        #    to see the room that was just cleared.
        out["dungeon"] = self._advance_dungeon(enc, solved=solved, rank=rank,
                                               fx=fx)
        # The Unclosed Bracket closes inside _advance_dungeon, because that is
        # the boss rather than a scene attached to it. It is lifted here so the
        # result payload carries it at the top level and the client does not
        # have to go looking inside a dungeon report for the most important
        # thing that has happened all chapter.
        out["companion_fell"] = (out["dungeon"] or {}).get("companion_fell")

        # -- earned upgrades: 18 items, every LEGENDARY weapon among them, were
        #    unreachable because nothing ever called items.upgrades_for.
        if solved:
            out["upgrades"] = self._grant_upgrades()
            out["artifacts"] = self._roll_artifacts(problem, enc, solved=solved,
                                                    seconds=seconds, fx=fx)
            learned = incantation.learn_from_clear(
                self.state["moveset"], skill=skill_name,
                chapter=curriculum.frontier(self.skills))
            out["incantations_learned"] = learned

        if levels_gained:
            incantation.grow_slots(self.state["moveset"],
                                   int(self.state["player"]["level"]))

        # -- THE OVERWORLD SANCTUARY HOOK ----------------------------------
        #
        # Two regions have no dungeon to hide a healer in — the Wastes and the
        # castle — and a tell nobody can follow to a room is a tease rather than
        # a puzzle, so out here a hurt traveller simply finds the tent. Every
        # other region returns the blank row, which is why this is called
        # unconditionally rather than behind a list of two ids.
        if enc.dungeon_room < 0:
            look = sanctuary.region_look(self.state, enc.region,
                                         last_difficulty=problem.difficulty,
                                         sealed=finalexam.sealed(enc, "BUILD"))
            if look.get("tell"):
                out["sanctuary"] = look

        # -- THE HUNT TICKS ON WHAT THE PLAYER DID, NOT ON A CLOCK ----------
        #
        # An encounter is the unit of time this engine actually has. hunters.py
        # is written in seconds because `web/js/overworld.js` mirrors it frame by
        # frame, so a headless session converts: one resolved encounter is one
        # ENCOUNTER_SECONDS of dwell, pressure and cooldown. The client's ticks
        # and these agree because they advance the same `Hunt` through the same
        # `hunt_step`; nothing here is a second chase.
        out["hunt"] = self._tick_hunt(enc, seconds=seconds, solved=solved)

        if solved:
            self._autosave("encounter_cleared", readiness=ready)
        return out

    # ======================================================================
    # THE APEX HUNTERS
    # ======================================================================
    #
    # hunters.py ships the creature, the readiness exam, the scaling and the
    # chase, and deliberately did NOT wire the chase into web/js/overworld.js —
    # "the contract between them is client_payload() and nothing else" — because
    # a creature whose position is decided in two places ends up in two places.
    # This engine holds the serialised `Hunt` rows and calls `hunt_step`; the
    # client mirrors the same rows through the same function. Neither invents a
    # second chase.
    #
    # ONE RESOLVED ENCOUNTER IS ONE TICK OF THIS MANY SECONDS.
    #
    # The alternative was wall-clock, and wall-clock means a player who leaves
    # the game open over lunch comes back to a creature that has been hunting an
    # empty room. hunters.MIN_REGION_DWELL_S is 150s, so at this rate an apex
    # needs roughly two encounters of dwell before it is even eligible, which is
    # the "meet the area first" rule arriving for free.
    ENCOUNTER_SECONDS = 90.0

    # AND IT IS SLICED, because `hunt_step` is written for a frame. Its
    # arithmetic is linear in dt and its thresholds are crossings — TRACKING
    # begins at scent 0.35, CLOSING wants 0.5, and scent only grows while the
    # player is MOVING and only in ROAMING. One ninety-second step jumps clean
    # over the window where both are true and the hunt gives up every time; the
    # first version of this did exactly that. hunters' own `_full_lifecycle`
    # proof runs at 1/30s. Two seconds is coarse enough to be cheap and fine
    # enough to take the same path through the machine.
    HUNT_SLICE_S = 2.0

    def _hunt_state(self) -> dict:
        block = self.state.setdefault(
            "hunters", {"regions": {}, "global_cooldown": 0.0, "kills": {},
                        "trophies": [], "fight": None, "last_tick": 0.0})
        block.setdefault("regions", {})
        block.setdefault("kills", {})
        block.setdefault("trophies", [])
        block.setdefault("global_cooldown", 0.0)
        block.setdefault("fight", None)
        return block

    def _hunt_for(self, region_id: str) -> hunters.Hunt:
        """The live Hunt row for one region, rebuilt from the save."""
        block = self._hunt_state()
        raw = (block["regions"].get(region_id) or {})
        row = hunters.new_hunt(region_id)
        for key, value in raw.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.region = region_id
        return row

    def _write_hunt(self, row: hunters.Hunt) -> None:
        self._hunt_state()["regions"][row.region] = row.to_dict()

    def _readiness_for(self, region_id: str, *, sealed: bool = False):
        """hunters.readiness_from_game, with the two things it cannot reach.

        The companion's TIER and the pouch are held in two other modules'
        states, so they are handed in rather than guessed at. Nothing here reads
        xp, level or mastery — that is the whole argument of hunters.py, and
        `hunters.self_check()["reads_no_progression"]` greps its own source to
        prove it stays true on that side of the wall.
        """
        active = (self.state["pets"].get("active") or [])
        tier = ""
        if active:
            pet = pets.BY_ID.get(active[0])
            tier = getattr(pet, "tier", "") if pet is not None else ""
        pouch = dict(self.state.get(potions.POUCH_STATE_KEY) or {})
        return hunters.readiness_from_game(
            self.state, self.effects(), region_id,
            companion_tier=tier, potions=pouch, build_sealed=sealed)

    def _moment(self, enc: Encounter | None, region_id: str, *,
                moving: bool = True) -> hunters.Moment:
        """What `hunt_step` is allowed to know about right now. Nothing else."""
        player = self.state["player"]
        maximum = max(1, int(player.get("stamina_max", 1) or 1))
        block = self._hunt_state()
        counters = db.evidence_counters(self.conn)
        return hunters.Moment(
            player_x=float(player.get("x", 0)), player_y=float(player.get("y", 0)),
            moving=bool(moving),
            health_fraction=max(0.0, min(1.0, player.get("stamina", 0) / maximum)),
            in_dungeon=bool(self.state.get(dungeons.STATE_KEY)),
            # A town is a sanctuary in the plain sense the module means: the
            # creature does not come into the square.
            in_sanctuary=(region_id == "python_village"),
            near_exit=False,
            clears=int((counters.get("region_clears") or {}).get(region_id, 0)),
            sealed=not self._pays_into_the_world(enc),
            in_battle=bool(block.get("fight")),
            global_cooldown=float(block.get("global_cooldown", 0.0)),
            # DETERMINISTIC, deliberately. `hash()` of a str is salted per
            # process, so a replay of the same save would jitter differently
            # every launch — and hunters.py's whole jitter design says a
            # deterministic replay is worth more than a surprise. The world seed
            # and the submission count are both in the save.
            seed=(int(self.state.get("world_seed", 0) or 0)
                  + int(self.state["stats"].get("submissions", 0))) & 0xFFFFFFFF,
        )

    def _tick_hunt(self, enc: Encounter | None, *, seconds: float = 0.0,
                   solved: bool = True) -> dict | None:
        """Advance this region's hunt by one encounter's worth of time."""
        region_id = getattr(enc, "region", "") or self.state["player"].get("region", "")
        if not hunters.apex_for(region_id):
            return None
        block = self._hunt_state()
        block["global_cooldown"] = max(
            0.0, float(block["global_cooldown"]) - self.ENCOUNTER_SECONDS)
        row = self._hunt_for(region_id)
        was = row.state
        events: list = []
        # WHETHER THE PLAYER IS MOVING IS DECIDED BY WHAT THE APEX IS DOING,
        # and this is the same reading hunters' own `_full_lifecycle` proof
        # takes: you walk the overworld until something is on your trail, and
        # then you are standing at a terminal typing Python, which is the only
        # posture in which anything in this game ever catches you.
        #
        # It is not a cheat for the creature. `moving` is what makes a player
        # gain (112 - 52) px/s, so a player who keeps walking keeps the gap, and
        # that is G1 — walking away is subtraction, not a skill check. What this
        # models is a player who stopped, because an encounter resolving IS a
        # player who stopped.
        remaining = self.ENCOUNTER_SECONDS
        while remaining > 0:
            slice_s = min(self.HUNT_SLICE_S, remaining)
            moving = row.state in ("DORMANT", "STIRRING", "ROAMING")
            row, half = hunters.hunt_step(
                row, self._moment(enc, region_id, moving=moving), slice_s)
            events.extend(half)
            remaining -= slice_s
        self._write_hunt(row)
        # THE LEDGER. `hunt_engage` allocates `fight["casts"]` and nothing ever
        # filled it, which left `hunt_resolve` taking the client's word for a
        # kill — a bounty in gold, metal, a draught and a trophy, for a POST.
        # A cast that lands on an apex is the same thing as a cast that lands
        # anywhere else in this game: a line of the player's own Python that
        # was graded and passed. So a solved encounter, fought while the fight
        # is open, is one cast. Nothing else moves this number.
        fight = block.get("fight")
        if (fight and solved
                # THE SAME THREE CONDITIONS web/js/huntui.js castLanded() uses,
                # because two counters that disagree are worse than one that is
                # wrong. In this region, because the pool belongs to the thing
                # standing in front of you; and only when the encounter pays
                # into the world at all, since a measured run advances nothing
                # and must not drain an apex either.
                and fight.get("region") == region_id
                and self._pays_into_the_world(enc)):
            fight["casts"] = int(fight.get("casts", 0)) + 1
        if row.state == "SPENT" or (was != "DORMANT" and row.state == "DORMANT"):
            block["global_cooldown"] = float(hunters.GLOBAL_COOLDOWN_S)
        if was == row.state and not events:
            return None
        return {**row.to_dict(), "events": list(events), "was": was,
                "telegraph": dict(hunters.TELEGRAPH.get(row.state, {}))}

    # -- the four doors the client actually presses ------------------------
    def hunt_view(self, region_id: str = "") -> dict:
        """Everything the overworld needs about this region's apex, in one call.

        `client_payload` is static and shipped once at load; the Hunt row and
        the readiness reading are per-region and per-moment. The READOUT is the
        point of the feature: it is a list of the things you have not done in
        this area yet, and it is legible before the fight rather than after it.
        """
        region_id = region_id or self.state["player"].get("region", "")
        apex = hunters.apex_for(region_id)
        if apex is None:
            return {"apex": None, "region": region_id,
                    "line": "Nothing hunts here."}
        # DEGRADE, NOT REFUSE — docs/10-sealed-views.md §4.F, and it is newly
        # cheap. `_readiness_for` counted class bonuses a measured run does not
        # have, which is why the whole screen was refused; `readiness_from_game`
        # takes `build_sealed=` and has all along. Everything ELSE on this
        # screen is now provably player-independent: `pace_for` returns the cast
        # band, the strike multiplier and the teaching stance from the chapter
        # and the region id alone. The chapter says how big the place is;
        # readiness says where in it you land, and only the second half is
        # sealed. A run sees where the creature is and how long its fight is,
        # with every BUILD term in the readiness readout at zero and a line
        # saying why. Not the whole score: the rung term is where the player
        # stands on the ladder, which no seal suspends, so a sealed readiness
        # is a smaller true number rather than a flat nought. The note below
        # says that, because it used to say "zero" and the screen said nine.
        sealed = bool(self._sealed_in_interview())
        ready = self._readiness_for(region_id, sealed=sealed)
        row = self._hunt_for(region_id)
        block = self._hunt_state()
        return {
            "region": region_id,
            "apex": apex.to_dict(),
            "hunt": row.to_dict(),
            "readiness": ready.to_dict(),
            "sealed": sealed,
            "seal_note": ("The chapter decides how long this fight is and that "
                          "is shown whole. Your preparation score is not: a "
                          "measured run is fought without the build, so every "
                          "term that counts gear, element or class reads zero "
                          "here. What is left standing is the part that is "
                          "still true — where you are on the ladder — which is "
                          "why this number is lower than the one outside and "
                          "not simply absent." if sealed else ""),
            # THE PACE, said out loud beside the readiness readout so a player
            # can see that the length they are being quoted is a property of
            # WHERE THEY ARE STANDING rather than of how well they have done.
            # Chapter I asks about a third of what chapter XI does; it was flat
            # across the whole game until the ramp landed.
            "pace": hunters.pace_for(region_id),
            "ramp": hunters.ramp_table(),
            "lesson": hunters.lesson_for(region_id),
            "scaling": (hunters.scale_for(region_id, ready=ready) or
                        hunters.Scaling(apex.id, region_id, 0, "", 0, 0, 1.0,
                                        1.0, "", (), "")).to_dict(),
            "telegraph": dict(hunters.TELEGRAPH.get(row.state, {})),
            "kills": int(block["kills"].get(apex.id, 0)),
            "guarantees": hunters.escape_guarantees(),
            "client": hunters.client_payload(),
            # The open fight and how much of it is done, so the bar the client
            # draws is the bar the engine will be paid against. Without this
            # the client is guessing at the number `hunt_resolve` checks.
            "fight": (dict(block["fight"], remaining=max(
                0, int((block["fight"].get("scaling") or {}).get(
                    "target_casts", 0)) - int(block["fight"].get("casts", 0))))
                if block.get("fight") else None),
        }

    def hunt_engage(self, region_id: str = "") -> dict:
        """Turn and face it. The scaling is frozen HERE and nowhere else.

        Freezing is not an optimisation. It is what stops a player stripping
        their gear mid-fight to shrink the pool, and what stops the pool growing
        under somebody who upgrades between rounds.
        """
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        region_id = region_id or self.state["player"].get("region", "")
        row = self._hunt_for(region_id)
        if row.state not in ("TRACKING", "CLOSING", "ENGAGED"):
            return {"error": "nothing is hunting you here", "state": row.state}
        ready = self._readiness_for(region_id)
        scaling = hunters.scale_for(region_id, ready=ready)
        if scaling is None:
            return {"error": "no apex here"}
        row.state = "ENGAGED"
        row.elapsed = 0.0
        self._write_hunt(row)
        block = self._hunt_state()
        block["fight"] = {"region": region_id, "apex": scaling.apex,
                          "peak": ready.score, "scaling": scaling.to_dict(),
                          "hp": scaling.hp, "casts": 0,
                          "started_at": time.time()}
        self.save()
        return {"engaged": True, "scaling": scaling.to_dict(),
                "readiness": ready.to_dict(),
                "flee": hunters.can_flee(row, turn=1),
                "lesson": hunters.lesson_for(region_id),
                # Said at the door, not after the loss. At readiness zero this
                # is fifty-two casts and is not a fight the design expects you
                # to win; it expects you to look at it and leave.
                "line": scaling.blurb}

    def hunt_flee(self) -> dict:
        """Always succeeds. No roll, turn one included. See G2."""
        block = self._hunt_state()
        fight = block.get("fight")
        if not fight:
            return {"error": "you are not fighting anything"}
        row = self._hunt_for(fight["region"])
        row = hunters.flee(row)
        self._write_hunt(row)
        block["fight"] = None
        block["global_cooldown"] = float(hunters.GLOBAL_COOLDOWN_S)
        self.save()
        return {"fled": True, "state": row.state,
                "line": "You walk. It does not get to decide whether that works."}

    def hunt_resolve(self, *, casts: int = 0, killed: bool = False) -> dict:
        """The fight is over. Pay it, or do not.

        THE TYPING IS STILL THE ATTACK: `casts` is how many lines actually
        landed, counted by whatever ran the fight, and this method neither
        grades nor grants mastery — the casting already happened, one line at a
        time, and was already paid for where casting is paid for.
        """
        block = self._hunt_state()
        fight = block.get("fight")
        if not fight:
            return {"error": "you are not fighting anything"}
        row = self._hunt_for(fight["region"])
        # WHAT THE CLIENT SAYS IS NOT WHAT HAPPENED. `casts` and `killed` both
        # arrive off the wire; the ledger below is what the engine watched the
        # player do. The frozen scaling says how many landed lines this apex is
        # long, and the fight block says how many landed. A claim beyond that is
        # refused and the fight is LEFT OPEN, because a player who is genuinely
        # mid-fight and whose client miscounted must not lose the fight to an
        # accounting error — they walk away with `hunt_flee`, which is free.
        landed = int(fight.get("casts", 0))
        needed = int((fight.get("scaling") or {}).get("target_casts", 0))
        if killed and landed < needed:
            self.save()
            return {"error": "it is still standing",
                    "killed": False, "casts": landed, "needed": needed,
                    "remaining": needed - landed,
                    "message": "That is not dead yet. It is %d landed lines "
                               "long and you have put %d into it. Keep typing, "
                               "or walk — walking always works."
                               % (needed, landed)}
        block["fight"] = None
        block["global_cooldown"] = float(hunters.GLOBAL_COOLDOWN_S)
        if not killed:
            row = hunters.flee(row)
            self._write_hunt(row)
            self.save()
            return {"killed": False, "state": row.state, "bounty": None}

        row.state = "SPENT"
        row.kills += 1
        row.cooldown = float(hunters.REGION_COOLDOWN_S)
        self._write_hunt(row)
        apex_id = fight["apex"]
        first = apex_id not in block["kills"]
        block["kills"][apex_id] = int(block["kills"].get(apex_id, 0)) + 1

        # The bounty is priced on READINESS AT THE MOMENT THE FIGHT STARTED —
        # frozen in `fight["peak"]` — so somebody who had no business winning is
        # paid for having had no business winning, and somebody who came
        # prepared is paid less and already knows why.
        prize = hunters.bounty(fight["region"], int(fight["peak"]),
                               first_kill=first)
        paid: dict = {"gold": 0, "metal": None, "potion": None, "trophy": ""}
        if prize is not None:
            econ = self.state
            award = economy.Award(gold=int(prize.gold), source="purse",
                                  region_id=fight["region"],
                                  detail={"apex": apex_id})
            paid["gold"] = economy.record(econ, award)["gold"]
            self.state["player"]["gold"] += paid["gold"]
            upkeep.record_income(self.state, paid["gold"])
            if prize.metal and prize.metal_units:
                forge.add_metal(self._forge_state(), prize.metal,
                                int(prize.metal_units))
                paid["metal"] = {"id": prize.metal, "count": prize.metal_units}
            got = potions.grant(self.state, {
                "id": self._apex_potion(prize), "count": int(prize.potion_doses)})
            paid["potion"] = {**got, "count": int(prize.potion_doses)}
            # `trophy_chance` is RETURNED rather than rolled, so the roll is
            # ours and uses our rng, exactly the way forge.roll_metal and
            # items.roll_drop already work.
            if prize.trophy_guaranteed or self._rng.random() < prize.trophy_chance:
                if prize.trophy in items.BY_ID and \
                        prize.trophy not in self.state["inventory"]:
                    self.state["inventory"].append(prize.trophy)
                    self.state["stats"]["items_found"] += 1
                    block["trophies"].append(prize.trophy)
                    paid["trophy"] = prize.trophy
        self.save()
        return {"killed": True, "first_kill": first, "casts": landed,
                "claimed_casts": int(casts), "needed": needed,
                "bounty": prize.to_dict() if hasattr(prize, "to_dict") else
                (asdict(prize) if prize is not None else None),
                "paid": paid, "state": row.state,
                "line": prize.line if prize is not None else ""}

    def _apex_potion(self, prize) -> str:
        """The apex's draught, in the band the bounty names. hunters.py names a
        BAND and leaves the id to whoever owns the pouch, which is potions.py."""
        band = str(getattr(prize, "potion_band", "") or "small")
        health = [p for p in potions.CATALOGUE if p.kind == "HEALTH"]
        exact = [p for p in health if p.strength == band]
        pick = exact or health
        return pick[0].id if pick else ""

    def _count_world_stats(self) -> None:
        """Two acquisition counters that were declared in DEFAULT_STATE and
        written by nothing, which made three artifacts unwinnable.

        Both are READ off state that other modules already own rather than
        tallied by hand, so they cannot drift: a region is retaken when
        progression says it is restored, and a green sphere is in hand when the
        player is standing in a region this seed put one in.
        """
        stats = self.state["stats"]
        states = (self.state["world"].get("region_states") or {})
        stats["regions_retaken"] = sum(
            1 for value in states.values() if value in ("restored", "transformed"))
        here = self.state["player"].get("region", "")
        held = self.state["world"].setdefault("green_index", [])
        if here and here not in held and any(
                sighting.region == here for sighting in self.world.sightings):
            held.append(here)
        stats["green_index_found"] = len(held)

    AUTOSAVE_THROTTLE_SECONDS = 180

    def _autosave(self, reason: str, **kwargs) -> None:
        """The ring is four slots deep and the whole state goes into each one, so
        writing on every cleared encounter would keep four minutes of history and
        a lot of disk churn. Notable events (a boss, a turn-in, a load) call
        saves.autosave directly and are never throttled."""
        now = time.time()
        last = float(self.state["stats"].get("autosave_at") or 0)
        if now - last < self.AUTOSAVE_THROTTLE_SECONDS:
            return
        self.state["stats"]["autosave_at"] = now
        saves.autosave(self.conn, self.state, reason, **kwargs)

    def _credit_daily(self, problem: Problem, enc: Encounter, *, solved: bool,
                      rank: str, seconds: float) -> list:
        """Daily quests were generated, rendered with their rewards, and had no
        completion path at all: `daily["completed"]` was written nowhere."""
        daily = self.state["daily"]
        done = daily.setdefault("completed", [])
        counts = daily.setdefault("counts", {})
        paid = []
        for quest in daily.get("quests", []):
            qid = quest["id"]
            if qid in done or not self._daily_matches(quest, problem, enc,
                                                      solved=solved):
                continue
            counts[qid] = int(counts.get(qid, 0)) + 1
            if counts[qid] < int(quest.get("count", 1)):
                continue
            done.append(qid)
            self.state["player"]["xp"] += int(quest.get("reward_xp", 0))
            paid.append({**quest, "completed": True,
                         "progress": counts[qid]})
        return paid

    def _daily_matches(self, quest: dict, problem: Problem, enc: Encounter, *,
                       solved: bool) -> bool:
        if not solved:
            return False
        kind = quest.get("kind")
        qid = quest.get("id", "")
        if kind == "RETEST":
            return enc.is_retest
        if kind == "MENTOR":
            want = qid.replace("daily-weak-", "").upper()
            return skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON") == want
        if qid == "daily-village":
            return problem.realm == "python_village"
        if qid == "daily-armor":
            return problem.encounter_kind == "DEBUG_BATTLE"
        if qid == "daily-bounty":
            return (time.time() - enc.started_at) <= problem.target_seconds
        return False

    def _grant_upgrades(self) -> list:
        """Swap an item for the form the evidence has earned. The upgraded item
        is added, the old one is kept — a Rusty Blade you can still see is what
        makes the new one mean something."""
        stats = {**self.state["stats"], **db.attempt_stats(self.conn)}
        skill_rows = {name: s.to_dict() for name, s in self.skills.items()}
        earned = items.upgrades_for(self.state["inventory"], skill_rows, stats)
        granted = []
        for upgrade in earned:
            new_id = upgrade["to"]
            if new_id in self.state["inventory"]:
                continue
            self.state["inventory"].append(new_id)
            self.state["stats"]["items_found"] += 1
            item = _item(new_id)
            if item and self.state["equipped"].get(item.slot) == upgrade["from"]:
                self.state["equipped"][item.slot] = new_id
                upgrade = {**upgrade, "auto_equipped": True}
            granted.append(upgrade)
        if granted:
            self._sync_caps()
        return granted

    def _roll_artifacts(self, problem: Problem, enc: Encounter, *, solved: bool,
                        seconds: float, fx: dict) -> list:
        """Twenty-two artifacts. Guaranteed ones are awarded when the evidence is
        in; the rest are rolled and may simply not drop, which is honest."""
        owned = set(self.state["legendaries"])
        conditions = self._artifact_conditions(enc, solved=solved,
                                               seconds=seconds, problem=problem)
        stats = {**self.state["stats"], **db.attempt_stats(self.conn)}
        skill_rows = {name: s.to_dict() for name, s in self.skills.items()}
        found = []
        for artifact in legendaries.ARTIFACTS:
            if artifact.id in owned:
                continue
            check = legendaries.eligible(artifact.id, skills=skill_rows,
                                         stats=stats, conditions=conditions)
            if not check:
                continue
            if check["met"] and artifact.acquisition["guaranteed"]:
                # "met" means award outright, do not roll. `kind` names WHERE it
                # comes from (boss/dungeon/proof/chain/...), not whether it is
                # certain — the manifest confused the two.
                found.append(self._take_artifact(artifact.id, check))
                continue
            if not check["conditions_met"] or not check["checks"]:
                continue
            if not all(row["met"] for row in check["checks"]):
                continue
            got = legendaries.roll(artifact.id, problem.difficulty,
                                   luck=fx.get("loot_luck", 0.0),
                                   conditions_met=True, owned=owned,
                                   rng=self._rng)
            if got:
                found.append(self._take_artifact(artifact.id, check))
        return found

    def _take_artifact(self, artifact_id: str, check: dict) -> dict:
        self.state["legendaries"].append(artifact_id)
        if artifact_id not in self.state["inventory"]:
            self.state["inventory"].append(artifact_id)
            self.state["stats"]["items_found"] += 1
        self._sync_caps()
        return {"id": artifact_id, "name": check.get("name", ""),
                "item": check.get("item"), "where": check.get("where", "")}

    def _advance_dungeon(self, enc: Encounter, *, solved: bool, rank: str,
                         fx: dict) -> dict | None:
        """A room cleared is a floor walked. A room failed relents one rung and is
        never terminal, which is why options() is asserted non-empty.

        Only a fight that was STARTED from a room counts. Carrying a dungeon run
        while doing overworld work is allowed, and crediting the room for it
        would be a floor the player never walked.
        """
        self._resolved_dungeon = None
        run = self.state.get(dungeons.STATE_KEY)
        if not run or enc.dungeon_room < 0:
            return None
        dungeon = self._dungeon_for(run["dungeon"], run.get("seed"))
        # CAPTURED BEFORE THE CLEAR. After it, the relent chain has moved and
        # the room no longer remembers what it demanded — and what the hidden
        # healer's reveal reads is the difficulty the room ACTUALLY ASKED FOR.
        asked = ("BOSS" if enc.dungeon_room == dungeon.boss_room
                 else self.by_id[enc.problem_id].difficulty
                 if enc.problem_id in self.by_id else "")
        result = dungeons.clear_room(dungeon, run, enc.dungeon_room, solved=solved)
        self._resolved_dungeon = (dungeon, run)
        if solved:
            reward = result.get("reward") or {}
            self.state["player"]["xp"] += int(reward.get("xp", 0))
            # The room's purse is economy.py's now. A ROOM PAYS ONLY IF IT ASKED
            # FOR SOMETHING: dungeon_room_award returns zero for ENTRANCE,
            # JUNCTION, STORY and TREASURE, so walking stops being paid for
            # while the chest still holds what roll_room_treasure puts in it.
            room_now = next((r for r in dungeon.rooms
                             if r.id == enc.dungeon_room), None)
            if self._pays_into_the_world(enc):
                award = economy.dungeon_room_award(
                    region_id=dungeon.region,
                    room_kind=getattr(room_now, "kind", "ENCOUNTER"),
                    depth=self._dungeon_depth(dungeon, run), solved=True)
                paid = economy.record(
                    self.state, award)["gold"]
                self.state["player"]["gold"] += paid
                upkeep.record_income(self.state, paid)
                result["gold"] = paid
            quests.note_depth(self.state, run["dungeon"],
                              self._dungeon_depth(dungeon, run))
            room = next((r for r in dungeon.rooms
                         if r.id == enc.dungeon_room), None)
            if room is not None:
                treasure = dungeons.roll_room_treasure(
                    dungeon, room, luck=fx.get("loot_luck", 0.0),
                    owned=set(self.state["inventory"]), rank=rank, rng=self._rng)
                if treasure:
                    self._take_drop(treasure)
                    result["treasure"] = treasure
                # A chest holds potions as well as gear, and holds them far more
                # reliably than a monster drops them: chests are the dependable
                # half of the economy and monsters are the lottery half, so a
                # player who explores is never out of thimbles and a player who
                # only fights occasionally is out of everything. Exploring is
                # the behaviour worth paying for, since the map is where the
                # problems are.
                if room.kind in ("TREASURE", "VAULT"):
                    found = potions.roll_chest(
                        # `dungeon.floor` rather than the private ladder
                        # roll_room_treasure runs on gear. The chest's SIZE is
                        # its own module's business; what a potion needs is how
                        # deep the player has walked, and the floor says that in
                        # one public word.
                        difficulty=dungeon.floor,
                        luck=fx.get("loot_luck", 0.0),
                        affinity=str(elements.affinity_for(dungeon.region)).lower(),
                        rng=self._rng)
                    if found:
                        result["chest_potions"] = [
                            {**row, **potions.grant(self.state, row)}
                            for row in found]
            self._count_solo_floor(enc)
            # THE DUNGEON HOOK, second of two, and it is the one that matters:
            # the room that just demanded something is the room a hidden healer
            # is revealed by. `asked` was captured above the clear.
            look = sanctuary.dungeon_look(self.state, dungeon, run,
                                          last_difficulty=asked,
                                          sealed=finalexam.sealed(enc, "BUILD"))
            if look.get("tell") or look.get("here"):
                result["sanctuary"] = look
            if enc.dungeon_room == dungeon.boss_room:
                result["dungeon_cleared"] = self._close_dungeon(dungeon, run,
                                                                rank=rank, fx=fx)
                fell = self._companion_falls(dungeon)
                if fell:
                    result["companion_fell"] = fell
                return result
        self.state[dungeons.STATE_KEY] = run
        return result

    def _count_solo_floor(self, enc: Encounter) -> None:
        """A floor walked with nothing helping. MIMIC's whole gate, and nothing
        else reads it.

        "Alone and unarmed" is checked against what the encounter actually
        records rather than what the player says about themselves: no companion
        in the field, no rung of the hint tree cast and nothing said unasked,
        and no consumable burned. A probe is a question you paid focus to ask,
        so it counts as help too.
        """
        if pets.active_id(self.state["pets"]):
            return
        if enc.hints_used or enc.pet_spoke or enc.temp_effects or enc.probes_used:
            return
        stats = self.state["stats"]
        stats["solo_floors"] = int(stats.get("solo_floors", 0)) + 1

    def _companion_falls(self, dungeon) -> dict | None:
        """The Unclosed Bracket closes, and the pig is on the inside of it.

        Fired from the dungeon's own boss rather than from a story trigger,
        because this is not a cutscene bolted onto a fight — it is what that
        boss IS. A thing that opens and never closes, met by an animal whose
        entire repertoire is supplying the mark that is missing.

        pets.fall is idempotent and the fact is persisted in the save, so this
        fires exactly once per run and survives a reload mid-scene. A player who
        cleared this dungeon before the fall existed settled the debt at load
        time; `is_fallen` is already true for them and this returns None.
        """
        if dungeon.id != pets.FALLS_AT_DUNGEON:
            return None
        pet_state = self.state["pets"]
        if pets.is_fallen(pet_state, pets.STARTER_ID):
            return None
        scene = pets.fall(pet_state, at=time.time())
        if not scene.get("fell"):
            return None
        self.state["pet_fall"] = scene
        self.save()
        saves.autosave(self.conn, self.state, "companion_fell")
        return scene

    def acknowledge_fall(self) -> dict:
        """The client has played the scene. Put the keepsake away.

        The fact stays in the save forever — `fallen` is what the legendary
        return is gated on — and only the undelivered scene is cleared.
        """
        scene = self.state.get("pet_fall")
        self.state["pet_fall"] = None
        self.save()
        return {"ok": True, "played": bool(scene)}

    def _close_dungeon(self, dungeon, run: dict, *, rank: str, fx: dict) -> dict:
        """The thing at the bottom falls and the descent is over.

        The manifest put this in _resolve_boss, and that guard is still there —
        but it only fires for a boss in world.BOSS_BY_ID, and a dungeon boss is
        assembled per run with an id like "halfwritten_barrow_boss_0007" that no
        world table has ever heard of. So every room in every dungeon could be
        beaten, boss room included, and "dungeons_cleared" stayed empty forever:
        the DELVE quests, progression.Needs.dungeon and the artifact conditions
        were all reading a list nothing ever wrote to.

        The boss's own reward is paid here too. clear_room pays room_reward,
        which is the room's share; assemble_boss().reward is the boss's, and it
        was going nowhere.
        """
        boss = run.get("boss") or {}
        reward = boss.get("reward") or {}
        player = self.state["player"]
        player["xp"] += int(reward.get("xp", 0))
        player["gold"] += int(reward.get("gold", 0))
        player["level"] = world.level_for(player["xp"])
        player["title"] = world.title_for(player["level"])
        spec = reward.get("drop") or {}
        drop = items.roll_drop(
            difficulty=spec.get("difficulty", "BOSS"), rank=rank,
            luck=fx.get("loot_luck", 0.0), is_boss=bool(spec.get("is_boss", True)),
            owned=set(self.state["inventory"]), rng=self._rng,
            upgrade=int(spec.get("upgrade", 0)))
        if drop:
            self._take_drop(drop)
        if dungeon.id not in self.state["dungeons_cleared"]:
            self.state["dungeons_cleared"].append(dungeon.id)
        quests.note_depth(self.state, dungeon.id, self._dungeon_depth(dungeon, run))
        self.state[dungeons.STATE_KEY] = None
        self.state["dungeon_map"].pop(dungeon.id, None)
        self.save()
        saves.autosave(self.conn, self.state, "boss_defeated")
        return {"id": dungeon.id, "name": dungeon.name,
                "boss": boss.get("name", ""), "boss_id": boss.get("id", ""),
                "xp": int(reward.get("xp", 0)), "gold": int(reward.get("gold", 0)),
                "loot": drop, "rank": rank}

    def _dungeon_depth(self, dungeon, run: dict) -> int:
        """Floor reached, counted as BFS depth from the threshold. progress()
        does not report it — the manifest said it did — so it is read off the
        deepest room actually visited, which is what "deepest floor reached"
        means and what quests.note_depth is asking for.
        """
        by_id = {room.id: room for room in dungeon.rooms}
        return max((by_id[r].depth for r in run.get("visited", []) if r in by_id),
                   default=0)

    def _dungeon_for(self, dungeon_id: str, seed=None):
        """Rebuild rather than store: generate(id, seed=) is deterministic, so a
        returning player walks into the identical building.

        The seeded world's build must win whenever it can. worldgen swaps the
        archetype and applies a size bonus, so `generate(id, seed=s)` is a
        DIFFERENT building from `build_dungeon(spec)` even at the same seed —
        a different archetype, a different room count, a different boss room.
        Entering through one and then walking through the other is how a player
        ends up standing in a room that does not exist. The spec's build carries
        the seed it was asked for, so matching on that seed is exact.
        """
        key = (dungeon_id, seed)
        if key in self._dungeons:
            return self._dungeons[key]
        built = None
        spec = next((d for d in self.world.dungeons if d.id == dungeon_id), None)
        if spec is not None:
            candidate = worldgen.build_dungeon(spec)
            if seed is None or candidate.seed == seed:
                built = candidate
        if built is None:
            built = dungeons.generate(dungeon_id, seed=seed)
        self._dungeons[key] = built
        return built

    def _award_secret(self, secret_id: str) -> dict | None:
        if secret_id in self.state["secrets_found"]:
            return None
        secret = items.SECRET_BY_ID.get(secret_id)
        if not secret:
            return None
        self.state["secrets_found"].append(secret_id)
        self.state["stats"]["secrets"] += 1
        item = _item(secret["item"])
        if item and item.id not in self.state["inventory"]:
            self.state["inventory"].append(item.id)
            self.state["stats"]["items_found"] += 1
        self._sync_caps()
        return {**secret, "item_detail": item.to_dict() if item else None}

    def _check_secrets(self, problem, enc, solved, rank, combat, report, *,
                       seconds: float = 0.0, armor_event: dict | None = None) -> list:
        """Hidden rewards, earned by doing something genuinely notable.

        All thirteen are evaluated here or at the one other hook their trigger
        names (`location`, `interview_finished`). Eight of them used to have no
        award path at all, so the Character panel showed conditions a player
        could satisfy and still get nothing.
        """
        found = []

        def take(secret_id):
            award = self._award_secret(secret_id)
            if award:
                found.append(award)

        # The Optimiser's Revelation: fail on performance alone, then clear it.
        perf_only = (not solved and getattr(report, "tests", None)
                     and all(t.kind == "performance"
                             for t in report.tests if not t.passed)
                     and any(not t.passed for t in report.tests))
        if perf_only and problem.id not in self.state["perf_failed_ids"]:
            self.state["perf_failed_ids"].append(problem.id)
        if solved and problem.id in self.state["perf_failed_ids"]:
            award = self._award_secret("secret_linear")
            if award:
                found.append(award)

        # Risen: clear something that beat you three times.
        if solved:
            history = db.attempts_for(self.conn, problem.id)
            if sum(1 for a in history if not a["solved"]) >= 3:
                award = self._award_secret("secret_phoenix")
                if award:
                    found.append(award)

        # Every Mimic Dies: a first-submission perfect Test Forge.
        if (solved and problem.encounter_kind == "TEST_FORGE" and enc.submits == 1):
            award = self._award_secret("secret_mimic")
            if award:
                found.append(award)

        # The Architect's Seal: three consecutive critical weakness strikes.
        if self.state["crit_streak"] >= 3:
            award = self._award_secret("secret_seal")
            if award:
                found.append(award)

        # --- the eight that had no award path at all ----------------------

        # The Thirtieth Day: a disguised retest of something a month old.
        if solved and enc.is_retest and enc.interval_days >= 30:
            take("secret_long_memory")

        # Half The Budget: a Medium, unaided, in under half its target.
        if (solved and problem.difficulty == "MEDIUM" and enc.hints_used == 0
                and seconds <= problem.target_seconds * 0.5):
            take("secret_half_clock")

        # Three Forges, No Survivors. The streak breaks on any imperfect forge.
        if problem.encounter_kind == "TEST_FORGE":
            perfect = solved and enc.submits == 1
            self.state["stats"]["forge_streak"] = (
                int(self.state["stats"].get("forge_streak", 0)) + 1 if perfect else 0)
            if self.state["stats"]["forge_streak"] >= 3:
                take("secret_forge_streak")

        # The Armorer's Last Plate: every piece back to full inside one session.
        pieces = [v for k, v in self.state["armor"].items() if k != "legendary"]
        if armor_event and armor_event.get("repaired") and pieces and min(pieces) >= 100:
            if not self.state["stats"].get("armor_full_this_session"):
                self.state["stats"]["armor_full_this_session"] = True
                take("secret_full_repair")

        # A boundary clear: a problem that actually declares edges, beaten on
        # the first graded submission with nothing cast. legendaries gates the
        # Off-By-One Band on twenty of these and the counter was declared and
        # never written, so the Band could not be earned at all. This is graded
        # evidence only — the player asserts nothing about themselves.
        if (solved and enc.submits <= 1 and enc.hints_used == 0
                and (problem.edge_cases or problem.hidden_tests)):
            self.state["stats"]["boundary_clears"] = int(
                self.state["stats"].get("boundary_clears", 0)) + 1

        # The Silent Chapter: graduated without casting a single learning spell.
        if solved:
            for chapter in self._newly_graduated_chapters():
                self.state["stats"]["chapters_graduated"] = int(
                    self.state["stats"].get("chapters_graduated", 0)) + 1
                if self._chapter_was_silent(chapter):
                    take("secret_silent_chapter")

        # The Second Meeting: a rematch win in under half the first win's time.
        if solved and enc.boss_id:
            wins = [r for r in db.boss_history(self.conn, enc.boss_id)
                    if r["defeated"]]
            if len(wins) >= 2 and wins[-1]["seconds"] <= wins[0]["seconds"] * 0.5:
                take("secret_rematch")

        return found

    def _newly_graduated_chapters(self) -> list:
        """Chapters that graduated on THIS clear. The ledger lives in the save,
        so a chapter cannot graduate twice and pay twice."""
        skills = self.skills
        banked = self.state["story"].setdefault("chapters_graduated", [])
        fresh = []
        for chapter in curriculum.CHAPTERS:
            if chapter.id in banked:
                continue
            if curriculum.chapter_progress(skills, chapter).get("graduated"):
                banked.append(chapter.id)
                fresh.append(chapter)
        return fresh

    def _chapter_was_silent(self, chapter) -> bool:
        """Did the player cast a single spell on anything this chapter teaches?

        Measured against recorded attempts, not against a running counter, so it
        stays true across sessions and cannot be reset by reloading.
        """
        families = set(chapter.families)
        if not families:
            return False
        marks = ", ".join("?" for _ in families)
        row = self.conn.execute(
            "SELECT COALESCE(SUM(hints_used), 0) AS n FROM attempts"
            " WHERE family IN (%s)" % marks, tuple(families)).fetchone()
        return int(row["n"] or 0) == 0

    # Every `location` secret and where it hides. The position is derived from
    # the region id, so the world is consistent and the codex hint leads
    # somewhere; the hardcoded `if region != "graph_wastes"` used to compute a
    # target for the Complexity Tower and then refuse to honour it, which made
    # secret_tower_alcove unobtainable.
    SECRET_LOCATIONS = {
        "graph_wastes": "secret_null_key",
        "complexity_tower": "secret_tower_alcove",
    }

    def find_secret_location(self, region_id: str, x: int, y: int) -> dict:
        secret_id = self.SECRET_LOCATIONS.get(region_id)
        if not secret_id:
            return {"found": False}
        target = self.secret_target(region_id)
        if abs(x - target["x"]) <= 1 and abs(y - target["y"]) <= 1:
            award = self._award_secret(secret_id)
            if award:
                self.state["stats"]["hidden_rooms_found"] = int(
                    self.state["stats"].get("hidden_rooms_found", 0)) + 1
            self.save()
            if award:
                return {"found": True, "secret": award}
            return {"found": True, "secret": None,
                    "message": "The alcove is already empty. You took what was here."}
        return {"found": False}

    def secret_target(self, region_id: str) -> dict:
        if region_id not in self.SECRET_LOCATIONS:
            return {}
        seed = sum(ord(c) for c in region_id)
        return {"x": 34 + seed % 6, "y": 6 + seed % 14}

    # -- hints -------------------------------------------------------------
    def use_hint(self, level: int) -> dict:
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        # The sacred rule, enforced server-side and in exactly one place:
        # finalexam.sealed is the ONE way to ask whether a capability exists here.
        if finalexam.sealed(enc, "HINTS"):
            return finalexam.refuse("HINTS")
        if self.effects().get("sealed_hints"):
            # An artifact the player chose to wear. Its own tooltip says so.
            return finalexam.refuse("HINTS")
        if enc.repo_id:
            # Not a refusal either: a Mini-Repo has no hint tree to climb, in
            # any mode. What it has instead is the suite, which can be run as
            # often as you like, and a debrief that always names the lesson and
            # the file the cause lived in — including after a failure.
            return {"error": "a mini-repo has no spells",
                    "message": "Nothing here is hidden from you. Read the "
                               "tests: they are the specification, and running "
                               "them costs nothing."}
        problem = self.by_id[enc.problem_id]
        rungs = problem.hint_tree
        if not 1 <= level <= len(rungs):
            return {"error": "no such spell"}
        rung = rungs[level - 1]

        # THE COMPANION IS THE HINT SYSTEM. Everything between the open rung and
        # the worked solution is read out by the animal walking with you, and an
        # animal below the depth of this encounter cannot read it. What it hands
        # over instead is the map: see _hint_gate, which is also where the
        # no-dead-end rule is enforced rather than promised.
        stuck = len(db.attempts_for(self.conn, problem.id)) >= pets.FREE_SOLUTION_AFTER
        blocked = self._hint_gate(enc, problem, level, rung, stuck=stuck)
        if blocked:
            return blocked

        player = self.state["player"]
        fx = self.effects()
        discount = fx.get("hint_discount", 0.0)
        cost = max(1, int(round(rung["mana"] * (1.0 - min(0.75, discount)))))
        if fx.get("hint_surcharge"):
            cost = int(round(cost * (1.0 + fx["hint_surcharge"])))
        # The full ladder costs 33 focus against a ceiling of 30, and PHOENIX —
        # the worked solution — costs 12, so a player who took rungs 1-4 had 9
        # and could not reach the floor the whole design rests on. Once the coach
        # would reveal the solution anyway (three attempts on this problem), the
        # rung that reveals it is free. It still costs the entire rank.
        if rung["spell"] == "PHOENIX" and stuck:
            cost = 0
        if player["mana"] < cost:
            return {"error": "not enough focus",
                    "message": f"{rung['title']} costs {cost} focus. "
                               "Memory Shrines restore it, and so does a clean solve."}
        if level not in enc.hint_levels:
            player["mana"] -= cost
            enc.hint_levels.append(level)
            enc.hints_used = len(enc.hint_levels)
            self.state["stats"]["hints_total"] += 1
        if rung["spell"] == "PHOENIX":
            enc.used_phoenix = True
        self._write_encounter(enc)
        self.save()
        return {
            "level": level, "spell": rung["spell"], "title": rung["title"],
            "body": rung["body"], "mana": player["mana"], "cost": cost,
            "hints_used": enc.hints_used,
            "rank_ceiling": rung["rank_cost"],
            "visualization": problem.visualization if level >= 2 else {},
            # Who read it out. The rung's words are the rung's words — a
            # companion is a voice around the hint tree, never a second one —
            # but the player should be able to see whose depth paid for it.
            "read_by": self._hint_voice(enc, problem, level, rung, stuck=stuck),
        }

    # -- who is allowed to say it ------------------------------------------
    #
    # The ladder in pets.py gates the middle of the hint tree and nothing else.
    # Three rungs out of the tree are permanently companion-free, and they are
    # the same three roads pets.PETLESS_ROADS names, so the module and the
    # engine cannot drift apart about what a stuck player is owed:
    #
    #   OPEN_RUNG   the first rung, always, in every mode where hints exist
    #   SOLUTION    PHOENIX, always — the worked solution was never a crutch you
    #               lean on during the fight, it is what you are owed afterwards
    #   COACH       not in this file at all; it has never asked who walks with you
    #
    # and a fourth, which is the sharpest edge of the whole design: after
    # FREE_SOLUTION_AFTER attempts the entire tree opens regardless of tier.
    # A player who has failed three times is stuck by measurement rather than by
    # assertion, and gating the CHEAP rungs of a tree whose most expensive rung
    # is already free would be a rule that only ever made things worse.

    def _asked_depth(self, problem) -> str:
        """The depth a DELIBERATELY ASKED rung is measured against.

        Note what is NOT in here: `boss=` and `final=`. pets.effective_difficulty
        raises a boss room to at least ELITE, and that is right for the help
        that arrives unasked — a boss is the encounter that exists to find out
        whether you needed it. Applying the same lift to the hint tree would
        mean nothing below LEGENDARY could read rungs 2 to 4 at any of the
        fourteen bosses, which is a large silent difficulty change and, worse,
        a second opinion about what a boss takes away. What a boss takes away is
        already decided in one place: finalexam.BOSS_LADDER removes the whole
        hint tree at rung 3 and never gives it back. So an asked rung is
        measured against the problem's own tier and nothing else.
        """
        return pets.effective_difficulty(problem.difficulty)

    def _hint_gate(self, enc: Encounter, problem, level: int, rung: dict, *,
                   stuck: bool) -> dict | None:
        """None if this rung may be cast, or the refusal that says why not.

        The refusal is deliberately NOT `{"error": "sealed"}`. A seal means the
        capability does not exist here; this means the animal in the field
        cannot read this depth, which is a different sentence with a different
        answer, and the client must not be able to confuse the two.
        """
        if level <= pets.OPEN_RUNG or rung["spell"] == "PHOENIX" or stuck:
            return None
        depth = self._asked_depth(problem)
        active = pets.active_id(self.state["pets"])
        if active and pets.covers(active, depth):
            return None
        route = pets.fallback_route(active, difficulty=depth,
                                    state=self.state["pets"])
        route["attempts"] = len(db.attempts_for(self.conn, problem.id))
        route["solution_free_after"] = pets.FREE_SOLUTION_AFTER
        pet = pets.BY_ID.get(active)
        return {
            "error": "above_tier",
            "capability": "HINTS",
            "level": level,
            "difficulty": depth,
            "companion": active,
            "companion_name": pet.name if pet else "",
            "companion_tier": pets.tier_of(active).key if active else "",
            "helps_through": pets.tier_of(active).depth if active else "",
            "opening": pet.above_tier if pet else "",
            # Said in the engine's own voice rather than an animal's, because
            # the player needs to hear the distinction out loud: the help still
            # exists, it is this companion that cannot reach it.
            "message": (
                f"{pet.name} cannot read this one. It is not that there is no "
                f"help here — the first rung is open, the coach speaks after a "
                f"failed submission, and the worked solution comes free after "
                f"{pets.FREE_SOLUTION_AFTER} attempts. It is that the animal "
                f"you brought covers {pets.tier_of(active).depth} and this room "
                f"is {depth}."
                if pet else
                "Nothing is walking with you, so the middle of the tree has "
                "nobody to read it out. The first rung is open, the coach speaks "
                "after a failed submission, and the worked solution comes free "
                f"after {pets.FREE_SOLUTION_AFTER} attempts."),
            "open_rung": pets.OPEN_RUNG,
            "route": route,
        }

    def _hint_voice(self, enc: Encounter, problem, level: int, rung: dict, *,
                    stuck: bool) -> dict:
        """Whose mouth this rung came out of, for the client to draw.

        A rung the ladder would have gated and which is open anyway — the first
        one, the worked solution, or anything at all once the player is three
        attempts deep — is marked `open: True` and carries no animal. That is
        the game telling the truth about its own floor rather than dressing the
        floor up as a favour.
        """
        active = pets.active_id(self.state["pets"])
        depth = self._asked_depth(problem)
        pet = pets.BY_ID.get(active)
        covered = bool(active) and pets.covers(active, depth)
        if not covered:
            return {"pet": "", "name": "", "open": True,
                    "why": ("the first rung is never gated" if level <= pets.OPEN_RUNG
                            else "the worked solution is never gated"
                            if rung["spell"] == "PHOENIX" else
                            f"{pets.FREE_SOLUTION_AFTER} attempts deep: the tree "
                            "is open")}
        bond = int(self.state["pets"].get("bond", {}).get(active, 0))
        return {"pet": pet.id, "name": pet.name, "species": pet.species,
                "sprite": pet.sprite, "colour": pet.colour, "open": False,
                "tier": pets.tier_of(active).key,
                "helps_through": pets.tier_of(active).depth,
                "bond_rank": pets.bond_rank(bond).key,
                "line": pet.on_intervene}

    # -- memory shrines ----------------------------------------------------
    def shrine(self) -> dict:
        question, answers, skill = self._rng.choice(world.SHRINE_QUESTIONS)
        self.state["_shrine"] = {"answers": answers, "skill": skill,
                                 "asked_at": time.time()}
        self.save()
        return {"question": question, "seconds": 20, "skill": skill}

    def shrine_answer(self, text: str) -> dict:
        """Trivia at a roadside stone. THE WRITE CLAUSE —
        docs/10-sealed-views.md §4.G.

        Reading the riddle is a view and stays open. Being PAID for it is not:
        this grants stamina, focus and XP and moves mastery on two skills
        through `skillmod.apply_outcome`, so without this check a measured run
        could heal and move mastery off trivia between questions. A view that
        changes the save is not a view, and mastery moves only on graded
        evidence — a shrine riddle is not graded evidence.

        The riddle is still ANSWERED, and still told whether it was right. What
        a run does not get is the payment.
        """
        pending = self.state.pop("_shrine", None)
        if not pending:
            return {"error": "no shrine active"}
        if not self._pays_into_the_world(self.encounter) or self.state.get(
                "interview"):
            given = (text or "").strip().lower()
            correct = any(a in given or given in a
                          for a in pending["answers"] if given)
            self.save()
            return {"correct": correct, "expected": pending["answers"][0],
                    "stamina": self.state["player"]["stamina"],
                    "mana": self.state["player"]["mana"], "xp": 0,
                    "paid": False,
                    "seal_note": "A measured run may read the stone and may "
                                 "not be paid for it."}
        given = (text or "").strip().lower()
        correct = any(a in given or given in a for a in pending["answers"] if given)
        player = self.state["player"]
        skills = self.skills
        if correct:
            bonus = 1.0 + self.effects().get("shrine_bonus", 0.0)
            player["stamina"] = min(player["stamina_max"],
                                    player["stamina"] + int(3 * bonus))
            player["mana"] = min(player["mana_max"],
                                 player["mana"] + int(6 * bonus))
            player["xp"] += int(12 * bonus)
            skillmod.apply_outcome(skills["RECALL"], solved=True, difficulty="TUTORIAL",
                                   hints_used=0, seconds=5, target_seconds=20,
                                   first_try=True, is_retest=False)
            target = skills.get(pending["skill"])
            if target:
                skillmod.apply_outcome(target, solved=True, difficulty="TUTORIAL",
                                       hints_used=0, seconds=5, target_seconds=20,
                                       first_try=True, is_retest=False)
        self._write_skills(skills)
        self.state["stats"]["shrines"] += 1
        self.save()
        return {"correct": correct, "expected": pending["answers"][0],
                "stamina": player["stamina"], "mana": player["mana"],
                "xp": 12 if correct else 0}

    # -- bosses ------------------------------------------------------------
    #
    # A BOSS IS A LADDER NOW, AND THIS IS WHERE THE RUNGS LIVE.
    #
    # What was here before: `start_boss` shipped a `phases` list and an `hp_max`
    # derived from it, `Encounter.boss_phase` was declared and never once
    # incremented, and a region boss died to ONE solved problem. Six keys per
    # boss promised a structure the fight did not have.
    #
    # What is here now, and the whole of it fits in four sentences:
    #
    #   1. `bestiary.open_fight` opens a fight with four to six phases, each
    #      with its own health pool and its own demanded idioms. It lives in
    #      state["boss_fight"] so a reload resumes the phase you were on.
    #   2. A GRADED SOLVE EMPTIES THE PHASE. `land(kind="submit", solved=True)`
    #      is the only thing that can, which is the Python typing being the
    #      attack, said in the one place it decides a fight's length.
    #   3. A FAILED SUBMISSION THAT PASSED TRIALS CHIPS IT.
    #      `land(kind="cast", ...)` takes damage that has already been through
    #      elements.resolve_damage against the boss's own buffed armour, and
    #      bestiary.CAST_FLOOR_HP stops it at one point — so chipping can never
    #      finish a phase and nothing but graded evidence ever advances the
    #      fight. It is also why a failed attempt at a boss now visibly moves
    #      the bar: LEARNING NEVER DEAD-ENDS is a thing the health bar can say.
    #   4. The phase turn buffs the boss (bestiary's ladder: a heavier blow, a
    #      second element, a status it did not leave before, plate, a narrower
    #      demand, more turns) and hands back a `beat` the client plays.
    #
    # The key drops when the LAST phase falls and not before. See `_key_card`.

    def _antagonist(self, occasion: str, *, detail: dict | None = None) -> dict:
        """The Null King, reading one line out of your file.

        He is weather. `blocking` is False in every payload this can return, so
        a caller attaches the result to a payload it was going to send anyway
        and a client that ignores it loses nothing. `finalexam.sealed` is the
        only capability question asked on the path, and in a measured run
        EXAM_SEAL seals every occasion he has — there is no branch by which he
        speaks into a measurement.

        Wrapped because a villain that raises inside a result payload is a
        villain somebody wraps in a try block and then deletes.
        """
        # ASKED AT THE DOOR AS WELL AS INSIDE, and this is not belt and braces.
        # `antagonist.speak` asks `finalexam.sealed(encounter, capability)`,
        # which is the right question — but it is asked OF AN ENCOUNTER, and
        # between two questions of a measured run there is not one. The module
        # would therefore have spoken into the gaps in a run, which is the exact
        # defect docs/10-sealed-views.md records against `/api/sage`. A run is
        # open or it is not, and that is `_sealed_in_interview`.
        if self._sealed_in_interview():
            return {}
        try:
            said = antagonist.speak(occasion, self.state, skills=self.skills,
                                    detail=detail or {},
                                    encounter=self.encounter, rng=self._rng)
        except Exception:                      # noqa: BLE001 - see docstring
            return {}
        return said if said.get("lines") else {}

    def unmaking_view(self) -> dict:
        """The spell, as data, for whoever is drawing it.

        THE SPELL EXPLAINS THE SEAL; IT DOES NOT CHANGE IT. `gauntlet/unmaking`
        holds no state, reads no save and cannot reach `finalexam.sealed`, which
        remains the one capability check in the codebase. This is narration over
        a rule that already existed, so it is safe to serve at any time and is
        not gated on the run — refusing it would be the animation making the
        exam harder than the audit.

        `first_time` is the only thing the server knows that the module does
        not: the full telling once, the wordless short form on every later cast.
        """
        seen = bool(self.state.get("story", {}).get("unmaking_seen"))
        reduced = bool(self.state.get("settings", {}).get("reduced_motion"))
        return unmaking.cinematic_view(first_time=not seen, reduced_motion=reduced)

    def mark_unmaking_seen(self) -> dict:
        """Latch the full telling so the second cast is the short form."""
        story = self.state.setdefault("story", {})
        first = not story.get("unmaking_seen")
        story["unmaking_seen"] = True
        self.save()
        return {"ok": True, "was_first": first}

    def antagonist_view(self) -> dict:
        """His standing, his pressure and whatever he has to say right now.

        A read plus a small write — the rotation advances so he does not open
        with the same sentence twice — which is the same bargain `town_talk`
        makes, and it is why this is saved afterwards.
        """
        # See `_antagonist`: the seal is asked of the RUN, not of an encounter
        # that may not exist between two questions of one. The curve is still
        # served — it is standing and pressure, both derived from graded
        # evidence and both world by docs/10-sealed-views.md — and he simply
        # has nothing to say while the measurement is running.
        if self._sealed_in_interview():
            # DEGRADE, and it has to SAY degrade. This used to splat
            # `finalexam.refuse("MENTOR")`, whose `error: "sealed"` key makes
            # `server._reply` answer 409 — so the standing and the pressure
            # this line is at pains to keep serving arrived at the client under
            # a status code meaning "no answer", and were thrown away.
            # `finalexam.suspended` is the same sentence without the key that
            # turns a served view into a refusal.
            return {**antagonist.herald(self.state, self.skills),
                    "lines": [], "moves": [], "blocking": False,
                    **finalexam.suspended("MENTOR")}
        out = antagonist.view(self.state, self.skills,
                              encounter=self.encounter, rng=self._rng)
        self.save()
        return out

    def _boss_finisher(self, enc: Encounter, solved: bool) -> bool:
        """Is THIS submission the one that ends the boss?

        A boss is four to six graded solves now, and two payers read
        `is_boss=` long before `_resolve_boss` runs: `economy.roll_purse` and
        `items.roll_drop`. Left as `bool(enc.boss_id)` they would pay the boss
        rate once per PHASE — four to six boss purses and four to six
        boss-rate drop rolls for one kill, which is not "more reward for more
        work", it is the same kill paid for several times.

        So the phases in the middle pay the ordinary encounter rate, which is
        what they are, and the last one pays what a boss pays.
        """
        if not enc.boss_id or not solved:
            return False
        fight = self._boss_fight()
        if not fight or fight.get("boss") != enc.boss_id:
            return True         # no ladder: the old one-solve boss, unchanged
        return int(fight.get("phase", 0) or 0) >= int(
            fight.get("phases", 1) or 1) - 1

    def _boss_fight(self) -> dict | None:
        """The open fight, or None. Refuses a fight written by another build:
        a stale shape is a fight that would resolve against the wrong ladder,
        and dropping it costs one boss re-entry rather than a wrong key."""
        fight = self.state.get("boss_fight")
        if not isinstance(fight, dict) or not fight.get("boss"):
            return None
        if int(fight.get("v", 0) or 0) != bestiary.FIGHT_VERSION:
            return None
        if fight["boss"] not in bestiary.BOSS_BY_ID:
            return None
        return fight

    def _write_boss_fight(self, fight: dict | None) -> None:
        self.state["boss_fight"] = fight or None

    def _boss_element(self, boss_id: str) -> str:
        """The ground this fight stands on, which is the region's affinity —
        the same value `vitals()` already gets. bestiary forms no second
        opinion about the wheel and neither does this."""
        boss = world.BOSS_BY_ID.get(boss_id, {})
        region = boss.get("region", "") or (
            bestiary.BOSS_BY_ID[boss_id].region
            if boss_id in bestiary.BOSS_BY_ID else "")
        element = elements.affinity_for(region)
        return element if element in elements.ELEMENTS else ""

    def _open_boss_fight(self, boss_id: str, rematch: int) -> dict:
        """Resume the open fight against this boss, or open a new one."""
        live = self._boss_fight()
        if live and live.get("boss") == boss_id and not live.get("cleared"):
            return live
        fight = bestiary.open_fight(boss_id,
                                    element=self._boss_element(boss_id),
                                    rematch=int(rematch or 0))
        if not fight:
            # A world boss with no bestiary entry. The fight degrades to the
            # single-solve shape it has always had rather than refusing to
            # start, because a boss nobody can walk into is a dead end.
            self._write_boss_fight(None)
            return {}
        fight["problems"] = []
        self._write_boss_fight(fight)
        return fight

    def _phase_problem(self, boss: dict, fight: dict, rematch: int) -> str:
        """The problem THIS phase asks for.

        bestiary.phase_kind names an `encounter_kind` per phase — recognise the
        family, state the approach, write it, survive the edges, name its cost,
        fight the disguised rematch — and this draws one from the boss's own
        spaced-repetition family that has not been served in this fight yet.

        It is a PREFERENCE and never a requirement. A family with nothing of
        that kind falls back to any unserved family problem, and then to the
        authored one. A phase that refused to start because the corpus had no
        COMPLEXITY_DUEL in it would be a dead end, and there are none of those.
        """
        authored = self._rematch_problem(boss, rematch)
        phase = int((fight or {}).get("phase", 0) or 0)
        if not fight or phase <= 0:
            return authored
        problem = self.by_id.get(boss.get("problem_id", ""))
        if problem is None:
            return authored
        want = bestiary.phase_kind(phase, int(fight.get("phases", 1) or 1))
        used = set(fight.get("problems") or ()) | {authored}
        family = [p for p in self.teachable
                  if p.spaced_repetition_family == problem.spaced_repetition_family
                  and p.id not in used]
        family.sort(key=lambda p: (adaptive.DIFF_ORDER.index(p.difficulty), p.id))
        pick = next((p for p in family if p.encounter_kind == want), None)
        return (pick or (family[0] if family else problem)).id

    def _arm_boss(self, enc: Encounter, fight: dict) -> None:
        """Put the ladder's buffs on the thing that actually swings.

        `bestiary.boss_vitals` is `vitals()` with the rungs folded in: the blow
        multiplier, the accreted second element, the focus regen, the specials
        that focus buys and the status it has climbed to being allowed to
        leave. `_enemy_turn` reads every one of them off `enc.enemy_vitals`, so
        this one assignment is what makes a phase turn change a number rather
        than print a caption.

        The hit points are NOT taken from the fight. A problem encounter's
        enemy HP is tactics.derive_enemy's count of hidden trials and has never
        been a health bar; the phase's pool lives on the fight, where `land()`
        keeps it.
        """
        if not fight:
            return
        buffed = bestiary.boss_vitals(fight)
        if not buffed:
            return
        row = dict(enc.enemy_vitals or {})
        keep_hp = int(row.get("hp", buffed.get("hp", 1)) or 1)
        keep_max = int(row.get("hp_max", buffed.get("hp_max", 1)) or 1)
        keep_focus = int(row.get("focus", buffed.get("focus", 0)) or 0)
        # The vial it was rolled for stays rolled. `_arm_enemy` decides once,
        # before the fight, whether this thing is carrying an antidote;
        # `boss_vitals` rebuilds the row from the ladder and would hand back the
        # bare default, which would quietly un-roll it on every phase turn.
        keep_vials = int(row.get("antidotes", 0) or 0)
        row.update(buffed)
        row["antidotes"] = keep_vials
        row["hp"], row["hp_max"] = keep_hp, keep_max
        # Focus is not restored by a phase turn. A boss that banked focus in the
        # phase it just lost would open the next one with a free special, and
        # the player has earned the opposite of that. Carried only within a
        # phase; `open_fight` and each turn rebuild the pool, not the balance.
        row["focus"] = min(int(row.get("focus_max", keep_focus) or keep_focus),
                           keep_focus)
        enc.enemy_vitals = row

    def _phase_preview(self, fight: dict) -> dict | None:
        """The next rung, one phase early, for whoever is wearing the artifact.

        `phase_preview` is in items.EFFECT_LABELS and has been dead payload
        since the artifacts landed, for the plain reason that there were no
        phases to preview. Gated on the effect, because an unconditional
        preview would delete the surprise the rung exists to be.
        """
        if not fight or not self.effects().get("phase_preview"):
            return None
        boss = bestiary.BOSS_BY_ID.get(fight.get("boss", ""))
        if boss is None:
            return None
        rungs = bestiary.ladder(boss)
        idx = int(fight.get("phase", 0) or 0)
        if idx >= len(rungs):
            return None
        return {**rungs[idx].to_dict(), "phase": idx + 1, "early": True}

    def _key_card(self, boss_id: str) -> dict | None:
        """What this boss is holding, whether or not it has been taken yet.

        A key is DERIVED — it is held if and only if its boss is in
        `cleared_bosses` — so there is no key ledger to fall out of step with
        the kill list, nothing to drop, nothing to sell, and no inventory bug
        that can take one back. See world.keys_held.
        """
        key = world.key_for_boss(boss_id)
        if not key:
            return None
        return {**key, "held": boss_id in set(self.state["cleared_bosses"])}

    def keyring(self) -> dict:
        """The fourteen keys, the roads they open and the portal that counts
        them. World, by the rule in docs/10-sealed-views.md: it is what you have
        done and where you may go, it does not move when the question on the
        screen does, and it reports nothing the seal has suspended."""
        cleared = list(self.state["cleared_bosses"])
        prog = progression.snapshot(self.state, self.skills,
                                    readiness=self._readiness())
        return {
            "keys": world.keyring(cleared),
            "held": world.keys_held(cleared),
            "required": world.PORTAL_KEY_REQUIREMENT,
            "portal": progression.portal_view(prog),
            # Said on the screen that counts the keys, because this is exactly
            # where a player would otherwise conclude the exam is behind them.
            "practical": self.practical_access(),
        }

    def start_boss(self, boss_id: str) -> dict:
        # ASKED AT THE DOOR, like every other overworld action, and it was not
        # being asked at all. `start_encounter` writes state["encounter"], so a
        # boss opened during a measured run replaced the question being
        # measured — a player could destroy their own exam by pressing the
        # wrong thing, and the practical is the one screen in this game that
        # must never be losable by accident. The write clause in
        # docs/10-sealed-views.md is what this is: a call that changes the save
        # is not a view, and a measured run does not make them.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        boss = world.BOSS_BY_ID.get(boss_id)
        if not boss:
            return {"error": "unknown boss"}

        if boss.get("final"):
            # Spec: final-boss completion requires actual interview-readiness gates.
            skills = self.skills
            ready = adaptive.readiness(
                skills=skills, schedule=self.schedule,
                stats=db.attempt_stats(self.conn),
                unaided_easy=self._unaided_counts()[0],
                unaided_medium=self._unaided_counts()[1])
            requirements = world.castle_requirements(
                skills, set(self.state["cleared_bosses"]), ready)
            if not requirements["open"]:
                return {
                    "error": "not ready",
                    "message": "The Interviewer will not see you yet. This is not a "
                               "difficulty wall — it is the readiness bar the whole "
                               "game exists to move you past.",
                    "requirements": requirements,
                    "readiness": ready,
                }
        # YOU HAVE TO GO THERE.
        #
        # This was the hole under the geography pass. story._places_proved says
        # that clearing a boss PROVES the player stood in that boss's region,
        # and story.build_context folds every cleared boss's region into
        # `regions_entered` on the strength of it — which is what rescues a save
        # written before the gate existed. Both were relying on a door that was
        # never locked: `start_boss` asked the seal, asked the readiness bar for
        # the final boss, and never once asked WHERE THE PLAYER WAS STANDING.
        #
        # So a level-six player in the village square could kill the Graph
        # Necromancer four regions away, take the Ring of Light, and have the
        # Cartographer — who lives in the Wastes and had never laid eyes on
        # them — open her chain. That is the exact bug the brief describes, one
        # hop further round than the place it was fixed.
        #
        # AFTER the readiness bar, not before it, and that order is the whole
        # design of this refusal. The Castle is the one region behind an event
        # wall rather than a road, so a player who is not ready yet must hear
        # the readiness bar — the thing they can act on — and not be sent to
        # walk to a place that is still sealed.
        #
        # NO DEAD END, and it is proved rather than asserted:
        # progression.verify_no_orphans deletes every wall and shows all sixteen
        # mortal regions still form one component, so the region a region boss
        # lives in is walkable with no key, no level and no gold. The Castle
        # opens on `ev_castle_unsealed`, whose terms are restoring captives and
        # RECALL mastery — both ordinary play, both always available — and the
        # refusal below names them when there is no road yet instead of leaving
        # the player looking at a wall with no sentence on it.
        here = self.state["player"]["region"]
        if boss["region"] != here:
            prog = progression.snapshot(self.state, self.skills,
                                        readiness=self._readiness())
            path = progression.path_between(prog, here, boss["region"])
            region = world.REGION_BY_ID.get(boss["region"], {})
            name = region.get("name", boss["region"])
            first = progression.ROUTE_BY_ID.get(path[0]) if path else None
            if path:
                message = (f"{boss['name']} is in {name}. You are not. Walk "
                           f"there and it will be waiting.")
            else:
                message = (f"{boss['name']} is in {name}, and no road there is "
                           f"open yet. Nothing here is spent waiting: the way "
                           f"in opens with the rest of the story.")
            return {
                "error": "not there",
                "message": message,
                "travel": {
                    "region": boss["region"],
                    "region_name": name,
                    "from": here,
                    "hops": len(path),
                    "route": path[0] if path else "",
                    "route_name": first.name if first else "",
                    "path": path,
                    "road_open": bool(path),
                },
                # A refusal in this game never leaves the player holding
                # nothing. Whether or not the road is open, the list of things
                # that are is attached to the same reply.
                "things_to_do": self.things_to_do(),
                # And the one door this refusal is never about.
                "practical": self.practical_access(),
            }

        rematch = self.state["boss_rematch"].get(boss_id, 0)

        # THE FIGHT, WHICH IS NOW LONGER THAN ONE PROBLEM.
        #
        # `open_fight` is called once per boss and then left alone: walking out
        # and coming back resumes the phase you were on rather than restarting
        # the ladder, because a four-solve fight that forgets itself on a reload
        # is a four-solve fight nobody finishes. `_open_boss_fight` returns the
        # live one when there is one.
        fight = self._open_boss_fight(boss_id, rematch)
        fight_view = bestiary.view(fight) if fight else {}

        # A rematch that replays the identical problem id is not a rematch. The
        # victory copy promised "the same boss, a different surface form", so the
        # rematch draws a different problem from the boss's own family, one rung
        # harder per tier, and only falls back to the authored one when the
        # family has nothing else. Each PHASE then draws its own problem on top
        # of that, by the kind bestiary.phase_kind names.
        problem_id = self._phase_problem(boss, fight, rematch)
        if fight is not None and problem_id not in (fight.get("problems") or ()):
            # So the next phase does not draw the same question again. A boss
            # that asked one problem six times would be a rematch of itself.
            fight.setdefault("problems", []).append(problem_id)
            self._write_boss_fight(fight)
        payload = self.start_encounter(problem_id,
                                       mode=config.MODE_ADVENTURE,
                                       boss_id=boss_id, reason="BOSS")
        enc = self.encounter
        if enc is not None and fight:
            # The encounter's own record of where in the ladder it sits. It was
            # declared with the dataclass and never once written to; this is the
            # line that was missing, and `_resolve_boss` reads it back.
            enc.boss_phase = int(fight.get("phase", 0) or 0)
            # THE BUFFS, FOLDED INTO THE THING THAT ACTUALLY SWINGS. A phase
            # turn that changes no number is a caption, so the boss standing in
            # front of the player is `boss_vitals` — the ladder's blow, focus
            # regen, second element and status — rather than a fresh roll.
            self._arm_boss(enc, fight)
            self._write_encounter(enc)
            self.save()
        spec = next((b for b in self.world.bosses if b.id == boss_id), None)
        # The six-phase structure is world.BOSS_PHASES and stays authoritative —
        # the manifest said worldgen.BossSpec.phases replaces it, but the seeded
        # list is a SUBSET of the same six keys (4-6 of them per boss), so it
        # names which phases this seed demands rather than redefining the shape.
        demanded = set(spec.phases) if spec is not None else set()
        phases = [{**phase, "demanded": (not demanded) or phase["key"] in demanded}
                  for phase in world.BOSS_PHASES]
        seal = finalexam.seal_for(mode=config.MODE_ADVENTURE, boss_id=boss_id)
        payload["boss"] = {
            **boss, "phases": phases, "rematch": rematch,
            # WHAT `hp_max` USED TO BE: a count of the seeded phase keys, which
            # no client ever read and which was not a health bar in any sense.
            # It is the current phase's real pool now, and `fight` beside it is
            # the whole ladder, so bosses.js can draw the art stage the server
            # is actually on instead of guessing from a fraction.
            "hp": int(fight_view.get("hp", 0)),
            "hp_max": int(fight_view.get("hp_max", 1) or 1),
            "fight": fight_view,
            "teaching_available": True,
            "affixes": list(spec.affixes) if spec is not None else [],
            "seal": seal.to_dict(),
            # Said before the first phase, not after the loss: the player is
            # told what this one takes away while they can still walk out.
            "herald": seal.herald,
            "ladder": self.boss_ladder(boss_id)["ladder"],
            # What this thing is holding, said at the door. The key is the
            # reason to finish the ladder rather than walk away after phase two,
            # so it is named before the first line of Python, not after the last.
            "key": self._key_card(boss_id),
            # `phase_preview` is a legendary effect that has been in
            # items.EFFECT_LABELS since the artifacts landed and has never once
            # been read: "a boss phase announces its modifier one phase early".
            # There were no phases to announce. There are now.
            "next_rung": self._phase_preview(fight),
        }
        # THE CAGE, BEFORE THE FIGHT, and this is the whole reason captives.py
        # has any weight. A cage the player WALKED PAST is a different fight
        # from a cage they hear about afterwards; the names and trades are on
        # the wall before the first line of Python is typed. It returns {} for a
        # boss holding nobody and carries freed=True on a rematch, so the cages
        # can be drawn empty the second time.
        room = captives.chamber(boss_id, self.state)
        if room:
            payload["chamber"] = room
        return payload

    def _rematch_problem(self, boss: dict, rematch: int) -> str:
        authored = boss["problem_id"]
        if not rematch:
            return authored
        problem = self.by_id.get(authored)
        if problem is None:
            return authored
        family = [p for p in self.teachable
                  if p.spaced_repetition_family == problem.spaced_repetition_family
                  and p.id != authored]
        if not family:
            return authored
        family.sort(key=lambda p: (adaptive.DIFF_ORDER.index(p.difficulty), p.id))
        return family[min(rematch - 1, len(family) - 1)].id

    # What a submission that did NOT solve the problem takes off the phase, as
    # a share of that phase's pool at full trial coverage.
    #
    # It is a third rather than a half because a phase has to stay worth a
    # graded solve: at a third, three near-misses still leave the pool above
    # bestiary.CAST_FLOOR_HP's floor of one, and the floor means that even
    # twenty of them cannot finish it. Nothing here supplies an answer and
    # nothing here clears a phase. What it buys is the health bar telling the
    # truth: you were close, and being close moved something.
    BOSS_CHIP_SHARE = 0.34

    def _resolve_boss(self, enc: Encounter, solved: bool, rank: str,
                      seconds: float, *, passed: int = 0,
                      total: int = 0) -> dict:
        boss = world.BOSS_BY_ID.get(enc.boss_id, {})
        fight = self._boss_fight()
        if fight is not None and fight.get("boss") != enc.boss_id:
            fight = None
        # `Encounter.boss_phase` is what it was declared for. It is stamped when
        # the phase's problem is served and read here, and the two disagreeing
        # means this submission belongs to a phase the fight has already left —
        # a second tab, a back button, a replayed request. Landing it would take
        # two phases off the boss for one solve, so nothing is landed at all.
        #
        # It returns rather than falling through to the one-solve path on
        # purpose: a stale submission must not be able to fell a boss, and the
        # player is not stranded by it because the fight is exactly where they
        # left it and `start_boss` walks straight back in.
        if fight is not None and int(enc.boss_phase or 0) != int(
                fight.get("phase", 0) or 0):
            return {
                "id": enc.boss_id, "name": boss.get("name", ""),
                "defeated": False, "stale": True,
                "phase": int(fight.get("phase", 0) or 0),
                "phases": int(fight.get("phases", 1) or 1),
                "fight": bestiary.view(fight),
                "message": "That answer was for a phase this fight has already "
                           "left. Nothing is lost — walk back in and the boss "
                           "is standing where you left it.",
                "history": db.boss_history(self.conn, enc.boss_id),
            }
        # THE LADDER, ADVANCED. One call, two kinds, and the kind is decided by
        # whether the Python ran — which is the only thing in this game that is
        # ever allowed to decide anything.
        event = self._land_on_boss(enc, fight, solved=solved,
                                   passed=passed, total=total)
        cleared = bool(event.get("cleared")) if fight else bool(solved)

        # `defeated=` IS THE CLEAR, NOT THE SOLVE. Recording a win per phase
        # would put four rows in the boss history for one kill and would tell
        # `db.boss_history` — which the exam ladder, the accolades and the
        # rematch tier all read — that a boss was beaten four times.
        db.record_boss(self.conn, enc.boss_id, seconds=seconds,
                       hints_used=enc.hints_used, rank=rank, defeated=cleared)

        # -- A PHASE FELL AND THE BOSS IS STILL STANDING --------------------
        #
        # No key, no purse, no cage opened, nothing appended to
        # cleared_bosses. What the player gets is the beat — the flash, the
        # herald, the tell — and the next phase's problem, which they fetch by
        # walking back in. Deliberately NOT started here: `start_boss` already
        # serves the current phase and starting a second encounter inside the
        # resolution of the first is how two live encounters end up in one save.
        if fight and solved and not cleared:
            self._write_boss_fight(fight)
            self.save()
            view = bestiary.view(fight)
            return {
                "id": enc.boss_id, "name": boss.get("name", ""),
                "defeated": False, "advanced": True, "rank": rank,
                "seconds": round(seconds, 1),
                "phase": int(fight.get("phase", 0) or 0),
                "phases": int(fight.get("phases", 1) or 1),
                "beat": event.get("beat"),
                "fight": view,
                "next_rung": self._phase_preview(fight),
                "key": self._key_card(enc.boss_id),
                "message": "The phase falls and the thing behind it does not. "
                           "Walk back in for the next one — the fight is where "
                           "you left it.",
                "history": db.boss_history(self.conn, enc.boss_id),
            }

        if cleared:
            if enc.boss_id not in self.state["cleared_bosses"]:
                self.state["cleared_bosses"].append(enc.boss_id)
            times_defeated = self.state["boss_rematch"].get(enc.boss_id, 0)
            self.state["boss_rematch"][enc.boss_id] = times_defeated + 1
            run = self.state.get(dungeons.STATE_KEY)
            in_dungeon = bool(run and run.get("boss", {}).get("id") == enc.boss_id)
            if in_dungeon:
                if run["dungeon"] not in self.state["dungeons_cleared"]:
                    self.state["dungeons_cleared"].append(run["dungeon"])
                self.state[dungeons.STATE_KEY] = None

            # -- THE CAGES, OPENED ------------------------------------------
            #
            # Directly after the cleared_bosses append, which is where the
            # contract puts it and where it belongs: the people this thing took
            # are freed by the same fact that records it as beaten. `free()`
            # returns {} on a rematch and {} for a boss holding nobody, so there
            # is no `if` to write and no way to pay twice.
            #
            # The reward is settled through the SAME handler a quest turn-in
            # uses, because captives.py deliberately emits nothing quests.py
            # does not already emit. One settler, one set of shapes; a second
            # would eventually disagree with the first about what a metal is.
            rescue = captives.free(self.state, enc.boss_id) \
                if self._pays_into_the_world(enc) else {}
            if rescue:
                rescue["settled"] = self._settle_pay(rescue.get("pay") or {},
                                                     story=rescue.get("story") or {},
                                                     source="rescue")

            # The boss's own purse, which is economy.py's number and not a flat
            # one. `times_defeated` is read BEFORE the increment above, which is
            # what turns a memorised rematch from 1.54x the plain rate into
            # 0.46x — less than walking next door and fighting something.
            boss_gold = 0
            if self._pays_into_the_world(enc):
                award = economy.boss_award(
                    region_id=(enc.region or boss.get("region", "")),
                    boss_id=enc.boss_id, solved=True, dungeon=in_dungeon,
                    times_defeated=times_defeated)
                boss_gold = economy.record(
                    self.state, award)["gold"]
                self.state["player"]["gold"] += boss_gold
                upkeep.record_income(self.state, boss_gold)

            # -- THE KEY --------------------------------------------------
            #
            # Taken by the same fact that records the boss as beaten, in the
            # same breath as the cages, and for the same reason: there is
            # nothing to award. `cleared_bosses` IS the keyring —
            # world.keys_held derives it — so this block grants nothing and
            # stores nothing. What it does is SAY so, because a key the player
            # is never told about is a key that does not exist to them.
            #
            # It therefore survives a save, a load and a slot round trip for
            # free: there is no second ledger that could fail to be written.
            key = self._key_card(enc.boss_id)
            opened = None
            if key:
                prog = progression.snapshot(self.state, self.skills,
                                            readiness=self._readiness())
                route = progression.ROUTE_BY_ID.get(key.get("opens", ""))
                if route is not None:
                    opened = progression.route_status(
                        route, prog, frm=route.frm)
                key["portal"] = progression.portal_view(prog)

            # HE WATCHES. One line, over the kill and over the key, and a
            # different one when the fourteenth ward lights. None of it blocks,
            # none of it is load-bearing, and deleting any of these three
            # statements costs a remark and nothing else.
            watched = [self._antagonist(antagonist.BOSS_FELLED,
                                        detail={"boss": enc.boss_id})]
            if key:
                watched.append(self._antagonist(antagonist.KEY_TAKEN,
                                                detail={"key": key["id"]}))
                if len(world.keys_held(self.state["cleared_bosses"])) >= \
                        world.PORTAL_KEY_REQUIREMENT:
                    watched.append(self._antagonist(
                        antagonist.PORTAL_OPENED))
            watching = [row for row in watched if row]

            # The fight is over and the ladder comes down with it. A cleared
            # fight left in the save would be resumed by the next `start_boss`
            # as a fight already at its last phase, which is how a rematch
            # would arrive pre-won.
            self._write_boss_fight(None)
            saves.autosave(self.conn, self.state, "boss_defeated")
            return {"id": enc.boss_id, "name": boss.get("name", ""),
                    "defeated": True, "rank": rank, "seconds": round(seconds, 1),
                    "rematch_tier": self.state["boss_rematch"][enc.boss_id],
                    "gold": boss_gold,
                    "rescue": rescue or None,
                    "phase": int((fight or {}).get("phase", 0) or 0),
                    "phases": int((fight or {}).get("phases", 1) or 1),
                    "key": key,
                    "opens": opened,
                    "watching": watching,
                    "history": db.boss_history(self.conn, enc.boss_id)}
        # A boss is never a dead end: it enters its teaching phase, and the
        # ladder comes WITH the refusal rather than behind a route nothing calls.
        # The fight is NOT thrown away — the phases already cleared stay
        # cleared, and the chip this submission landed stays landed, so walking
        # back in resumes rather than restarts.
        if fight:
            self._write_boss_fight(fight)
            self.save()
        seal = finalexam.seal_for(mode=config.MODE_ADVENTURE, boss_id=enc.boss_id)
        return {
            "id": enc.boss_id, "name": boss.get("name", ""), "defeated": False,
            "teaching_phase": True,
            "mentor": (None if seal.blocks("MENTOR") else world.MENTORS.get(
                world.REGION_BY_ID.get(boss.get("region", ""), {}).get(
                    "mentor", "byte"))),
            "ladder": self.boss_ladder(enc.boss_id).get("ladder", []),
            "phase": int((fight or {}).get("phase", 0) or 0),
            "phases": int((fight or {}).get("phases", 1) or 1),
            # What the near-miss took off it, and the bar it took it off. This
            # is the difference between "you failed" and "you were two trials
            # short and it felt them".
            "chip": int(event.get("damage", 0) or 0),
            "fight": bestiary.view(fight) if fight else None,
            "message": "The boss steps back. A mentor arrives. Nothing here is a wall.",
            "history": db.boss_history(self.conn, enc.boss_id),
        }

    def _land_on_boss(self, enc: Encounter, fight: dict | None, *,
                      solved: bool, passed: int, total: int) -> dict:
        """One piece of graded evidence, landed on the fight. The ONE call.

        Two kinds and nothing else, and which one it is was decided by whether
        the player's own Python ran:

          SOLVED   -> `land(kind="submit", solved=True)` empties the phase.
                      This is the only thing in the game that advances a boss.
          NOT      -> `land(kind="cast", damage=...)` chips it, with the damage
                      already through `elements.resolve_damage` against the
                      boss's own buffed armour, floored by
                      bestiary.CAST_FLOOR_HP so it can never finish a phase.

        `incantation=` is left empty on purpose. The DEMAND rung halves a cast
        that is not the phase's demanded IDIOM — an incantation id, from the
        typed-Python battle — and a graded submission is not one of those. A
        rung that silently halved every near-miss would be punishing the
        experiment the whole bestiary exists to encourage.
        """
        if not fight:
            return {"landed": False, "damage": 0, "turned": False,
                    "cleared": bool(solved), "beat": None, "line": ""}
        if solved:
            return bestiary.land(fight, kind="submit", solved=True)
        # The near miss. Nothing at all if nothing passed: a submission that
        # solved none of the trials landed no blow, and saying otherwise would
        # be the game manufacturing a hit.
        share = (max(0, int(passed)) / max(1, int(total))) if total else 0.0
        if share <= 0:
            bestiary.land(fight, kind="submit", solved=False)
            return {"landed": False, "damage": 0, "turned": False,
                    "cleared": False, "beat": None, "line": ""}
        pool = int(fight.get("hp_max", 1) or 1)
        base = max(1, int(round(pool * share * self.BOSS_CHIP_SHARE)))
        state = dict(fight.get("buff") or {})
        defender = elements.Defender(
            element=state.get("element", "") or fight.get("ground", ""),
            # THE ARMOUR RUNG, BITING. `buff_state` raises the boss's flat
            # points and the share of a hit they may remove as the ladder
            # climbs, and this is the one place a player can feel it: the same
            # near miss chips less in phase four than it did in phase one.
            armour=elements.ArmourProfile(
                points=int(state.get("armour_points", 0) or 0),
                points_cap=min(elements.ARMOUR_POINT_CAP,
                               float(state.get("armour_cap", 0.0) or 0.0)),
                kind="PLATE"),
            statuses=self._load_statuses(enc.enemy_statuses),
            max_health=pool,
            # THE ELEMENT RUNG, BITING. A boss that has accreted the counter to
            # its own ground is TWO elements, and `Defender.affinities()`
            # resolves against the chain rather than the primary. Passing only
            # the first would make the rung a caption: the loadout that was
            # working would go on working.
            elements=tuple(state.get("elements") or ()))
        hit = elements.resolve_damage(
            base, self._player_element(enc), defender,
            attacker_statuses=self._load_statuses(enc.statuses),
            roll=self._rng.random(),
            build_sealed=finalexam.sealed(enc, "BUILD"))
        event = bestiary.land(fight, kind="cast", damage=hit.damage)
        # The spent turn is recorded too, so the fight's own log says what
        # happened rather than showing a cast that arrived from nowhere.
        bestiary.land(fight, kind="submit", solved=False)
        event["line"] = f"{hit.line} {event.get('line', '')}".strip()
        return event

    def boss_ladder(self, boss_id: str) -> dict:
        """Repeated failure reduces complexity rather than repeating the wall."""
        boss = world.BOSS_BY_ID.get(boss_id)
        if not boss:
            return {"error": "unknown boss"}
        problem = self.by_id.get(boss["problem_id"])
        if not problem:
            return {"error": "unknown problem"}
        family = problem.spaced_repetition_family
        ladder = sorted(
            [p for p in self.teachable if p.spaced_repetition_family == family],
            key=lambda p: adaptive.DIFF_ORDER.index(p.difficulty))
        return {
            "boss": boss,
            "ladder": [{"id": p.id, "title": p.title, "difficulty": p.difficulty}
                       for p in ladder],
            "message": "Climb back up. Each rung is the same algorithm, one step simpler.",
        }

    # -- interview mode ----------------------------------------------------
    INTERVIEW_FORMATS = {
        "LIVE_SCREEN": {"label": "Live Screen", "minutes": 50, "count": 2,
                        "ladder": ["EASY", "MEDIUM"]},
        "GAUNTLET": {"label": "The Gauntlet", "minutes": 65, "count": 4,
                     "ladder": ["EASY", "EASY", "MEDIUM", "HARD"]},
        # The sealed practical. Its composer knows about weak skills and about
        # the codebase segment, which the engine's own ladder never did.
        "FINAL_EXAM": finalexam.interview_format(),
    }

    def start_interview(self, fmt: str = "GAUNTLET",
                        profile: str | None = None, *,
                        staged: bool = False) -> dict:
        """Start a measured run. `staged` is the story, never the measurement.

        `staged` is a PARAMETER and not a saved flag, and that is the whole of
        why the two exams cannot drift into each other. There is no bit left
        lying in the save that a later call could pick up by accident: the only
        way to reach `staged=True` is to be called by `start_final_trial()`,
        which is reached only from the last room's own door. Every other caller
        in the codebase — the menu, `/api/exam/start`, `/api/interview/start`,
        the CLI — gets the default and composes a measurement.

        THE DIRECTION OF THE GATE, said once more because this is the method it
        would be easiest to break: nothing here consults the portal, the keyring
        or `cleared_bosses`. A player at level one holding nothing sits exactly
        this run, under exactly this seal, on exactly this clock.
        """
        spec = self.INTERVIEW_FORMATS.get(fmt)
        if not spec:
            return {"error": "unknown format"}
        profile = config.normalise_profile(
            profile or self.state["player"]["profile"])
        if fmt == "FINAL_EXAM":
            return self._start_exam(profile, staged=staged)
        weights = adaptive.PROFILE_PATTERN_WEIGHT.get(
            profile, adaptive.PROFILE_PATTERN_WEIGHT["GENERAL_SWE"])
        recent = set(self.state["recent_ids"][:15])

        # Interview Mode measures, so it reaches for the hold-out FIRST. A
        # sealed problem from a lineage this player has never met is the only
        # content in the corpus that can answer the question they actually
        # asked. The hold-out is finite and spends as it is used, so when it has
        # nothing that fits the rung the set falls back to teachable material —
        # still a measured run, still unaided, just not evidence of transfer.
        # transfer_report() says which it was by counting only the first.
        holdout_first = self.transfer_pool()
        picked: set = set()
        lineages: set = set()

        def draw(want: str, pool: list):
            candidates = [p for p in pool
                          if p.difficulty == want
                          and p.entry.get("kind") in ("function", "class_ops")
                          and p.encounter_kind in ("CODE_BATTLE",)
                          and p.id not in recent
                          and p.id not in picked
                          # One per lineage per sitting: two siblings in one set
                          # is one exercise asked twice, and only the first of
                          # them could ever have counted for anything.
                          and p.lineage_id not in lineages]
            if not candidates:
                return None
            candidates.sort(key=lambda p: (weights.get(p.pattern, 1.0)
                                           * p.profile_weight.get(profile, 1.0)
                                           + self._rng.random()), reverse=True)
            return candidates[0]

        chosen = []
        for want in spec["ladder"]:
            problem = draw(want, holdout_first) or draw(want, self.teachable)
            if problem is None:
                continue
            picked.add(problem.id)
            lineages.add(problem.lineage_id)
            chosen.append(problem)

        run = {
            "id": f"iv-{int(time.time())}", "format": fmt, "profile": profile,
            "problem_ids": [p.id for p in chosen], "index": 0,
            "started_at": time.time(), "minutes": spec["minutes"],
            "results": [],
        }
        self.state["interview"] = run
        # A GAUNTLET run is not an exam, so it must not inherit the identity of
        # one. `state["exam"]` survived being abandoned before this line existed,
        # and `_exam_debrief` reads it off the save rather than off the run —
        # which meant an abandoned practical's payload could still be sitting
        # there and hand this run a debrief carrying THAT exam's `exam_id`.
        # Harmless while a format check guarded the finale; a way to end the
        # game from a drill now that `ending.resolve` decides off the id. So the
        # previous exam is dropped here and its staging with it: whoever walked
        # away from the last room is not in it any more.
        self.state["exam"] = None
        self._exam = None
        ending.clear_staging(self.state)
        self.save()
        return {
            "run": self.run_view(run), "label": spec["label"],
            "rules": [
                "No spells. No mentor. No pattern cards. No coach.",
                "The algorithm family is never named.",
                "Timer runs across the whole set, not per problem.",
                "State your approach before you write, in the box provided.",
                "Everything is recorded and analysed the moment it ends.",
            ],
            # The ladder, without the names on it. The client renders "five
            # problems, rising in difficulty"; it has never needed to know which
            # five, and the hold-out cannot afford for it to.
            "problems": [{"difficulty": p.difficulty} for p in chosen],
        }

    def start_final_trial(self, profile: str | None = None) -> dict:
        """THE LAST ROOM'S OWN DOOR, and the only staged route in the game.

        It composes the same practical `/api/exam/start` composes, out of the
        same corpus, under the same seal, on the same clock — and then says, of
        that one composed exam and by its id, "this sitting is the last room of
        the story". `ending.stage()` is the only thing that knows the
        difference and this is the only call site it has.

        IT DOES NOT CHECK THE PORTAL, deliberately. If the wards are dark
        `stage()` declines to stage and the exam runs anyway, as a measurement:
        the story is refused, never the practical. A refusal to stage is
        reported in `ending.staging` as information and it is NOT an error.
        """
        return self.start_interview("FINAL_EXAM", profile, staged=True)

    def _start_exam(self, profile: str, *, staged: bool = False) -> dict:
        # THE RECIPE IS SAVED WITH THE EXAM, and it has to be, because
        # `exam.seed` is NOT the seed the exam was drawn with: finalexam.compose
        # draws from its rng and only THEN pulls `seed=rng.randrange(1 << 30)`
        # off the far side of the draw. Feeding that value back into compose()
        # rebuilds a different exam, which is why `_recover_exam` silently failed
        # for every run that outlived the process that composed it — the player
        # got "the per-question debrief is unavailable" and no explanation they
        # could act on.
        #
        # It matters far more now than it did then. `ending.resolve` recognises
        # the story climax by `report["exam_id"]`, and an unavailable debrief
        # carries no exam id, so a player who closed the game in the middle of a
        # hundred-and-fifteen-minute practical and came back to finish it used to
        # lose the ENDING as well as the debrief. The four inputs that decide the
        # draw are the seed, the history, the recent ids and the profile; all
        # four are written down here and read back in `_recover_exam`.
        recipe = {
            # The same source compose() reaches for when handed no seed
            # (`random.getrandbits(48)`), so the exam is exactly as fresh as it
            # was before this line existed. It is captured rather than thrown
            # away, and that is the only difference.
            "seed": random.getrandbits(48),
            "history": finalexam.history_fingerprints(
                db.interview_history(self.conn, limit=50)),
            "recent_ids": list(self.state["recent_ids"]),
            "profile": profile,
        }
        exam = finalexam.compose(
            self.corpus, self.skills, profile=profile,
            seed=recipe["seed"],
            history=recipe["history"],
            recent_ids=recipe["recent_ids"])
        payload = exam.to_dict()
        # Kept in the save and never sent: `_start_exam` returns
        # `exam.player_view()`, and /api/state's `exam` key is the ladder.
        payload["recipe"] = recipe
        self._exam = exam
        self.state["exam"] = payload
        run = {
            "id": payload["id"], "format": "FINAL_EXAM", "profile": profile,
            "problem_ids": [q["problem_id"] for q in
                            (q for seg in payload["segments"]
                             for q in seg["questions"])],
            "index": 0, "started_at": time.time(),
            "minutes": payload["minutes"], "results": [],
        }
        self.state["interview"] = run
        # THE ONE PLACE THE TWO EXAMS ARE TOLD APART, and both arms of it write.
        #
        # Staging is bound to `payload["id"]`, the id of the exam that was just
        # composed and the id `finalexam.debrief` reports back as
        # `report["exam_id"]`. `ending.resolve` triggers on that match and on
        # nothing else.
        #
        # The menu arm CLEARS rather than merely declining to set, so that
        # `state["ending"]["staged_exam_id"]` is rewritten by every compose in
        # the game and can never be a stale id left over from a trial the player
        # walked out of. Combined with the same clearing in the GAUNTLET branch
        # above, the invariant is total: after any start_interview call, the
        # staged id is the id of the exam that is about to be sat if and only if
        # that exam was composed by `start_final_trial`, and is empty otherwise.
        if staged:
            staging = ending.stage(self.state, exam_id=payload["id"],
                                   cleared_bosses=self.state["cleared_bosses"])
            # A REFUSED STAGE STILL HAS TO WRITE, or the paragraph above is a
            # claim and not an invariant. `ending.stage` returns at its first
            # guard when the portal is shut, BEFORE it touches the block — so
            # without this line a trial composed behind dark wards leaves the
            # PREVIOUS staged id sitting in the save, naming an exam that is no
            # longer `state["exam"]`. The next menu compose clears it, so it is
            # not a way to collapse the two exams; what it is, is one `load_slot`
            # away from restoring that exam beside its stale id and re-firing an
            # ending that was already spent. Staging is total or it is nothing.
            if not staging.get("staged"):
                ending.clear_staging(self.state)
        else:
            ending.clear_staging(self.state)
            staging = {
                "staged": False, "reason": "from_the_menu",
                "why": "Interview Mode. This is the measurement, it is the "
                       "same exam the last room uses, and it does not end the "
                       "game however well it goes.",
                "blocks_the_practical": False,
            }
        self.save()
        fmt = finalexam.interview_format()
        return {
            "run": self.run_view(run), "label": fmt["label"],
            # Which of the two things the player is about to sit, said at the
            # door so they are never confused about it, and never as an error:
            # `staged: False` here is the normal case and the honest one.
            "staging": staging,
            "two_exams": ending.TWO_EXAMS,
            # `player_view`, not the `to_dict` that is kept in the save. Exam
            # already drew this line for itself — "how long, how many, and in
            # what order. Not what they are about" — and the engine was sending
            # the other one, which carries every question's problem_id and title.
            "exam": exam.player_view(),
            "rules": list(fmt["rules"]),
            "ladder": finalexam.ladder_view(),
            # The last thing in the game, given a face. Static module data: it
            # has never seen a question and there is no field on it that could
            # carry one, so it ships inside a sealed run without widening the
            # seal. The herald fires the beat; the beat pays nothing.
            "examiner": finalexam.examiner_view(),
            "problems": [{"difficulty": self.by_id[pid].difficulty}
                         for pid in run["problem_ids"] if pid in self.by_id],
        }

    def finish_exam(self, seconds_by_segment: dict | None = None) -> dict:
        """Kept as a named door for the client. The debrief itself is produced
        inside finish_interview, because the run can also end by answering the
        last question — and a debrief you only get by pressing the right button
        is a debrief half the players never see."""
        run = self.state.get("interview")
        if not run:
            return {"error": "no exam running"}
        return self.finish_interview(seconds_by_segment=seconds_by_segment)

    def _exam_debrief(self, results: list, seconds_by_segment,
                      *, measured: dict | None = None) -> dict | None:
        payload = self.state.get("exam")
        if not payload:
            return None
        exam = self._recover_exam(payload)
        if exam is None:
            # BELT AND BRACES FOR THE ENDING. `_start_exam` writes a recipe now
            # and this branch should be unreachable for any exam composed since;
            # it is still reachable for one that was already in flight when this
            # build landed, or if the corpus itself changed underneath a run.
            #
            # `exam_id` is carried anyway, because it is a FACT the engine holds
            # without rebuilding anything, and because `ending.resolve` reads it
            # to decide whether this was the last room of the story. Without it a
            # staged climax that could not be scored would return
            # `triggered: False` — the player would finish the last fight and the
            # game would say nothing at all, which is the one outcome this
            # feature exists to prevent. With it the climax resolves; there is no
            # verdict to read UNLESS the run was a clean sweep inside every
            # clock this branch can see — which it can, off the measured results
            # and the segment budgets in the payload, without rebuilding
            # anything. That case is carried, because the alternative is the one
            # this pass actually reproduced: a staged climax solved 6 of 6 in
            # time, the report printing "INTERVIEW REPORT — 100%", and "THE
            # SHELVES ARE STILL FULL" directly beneath it. Anything short of a
            # sweep still carries no verdict and still resolves as a failure —
            # which costs nothing, spends nothing and leaves the portal open, so
            # it is a rematch and not a loss.
            return {"exam_id": payload.get("id", ""),
                    "format": payload.get("format_id", ""),
                    "unavailable": True,
                    **self._unscored_verdict(payload, measured,
                                             seconds_by_segment),
                    "note":
                    "The exam was composed in an earlier process and could not "
                    "be rebuilt, so the per-question debrief is unavailable. "
                    "The score is still the measured one."}
        # debrief() documents `results` as exactly the shape interview_advance
        # already records, so it is passed through rather than rebuilt.
        return finalexam.debrief(
            exam, results, skills=self.skills,
            seconds_by_segment=seconds_by_segment or {},
            readiness=self._readiness(), corpus_index=self.by_id,
            # Which of these the player was actually shown. A sealed question
            # the run composed but never served is still unspent hold-out, and
            # a debrief that names it hands it over for free.
            served=db.transfer_problem_ids(self.conn))

    @staticmethod
    def _unscored_verdict(payload: dict, measured: dict | None,
                          seconds_by_segment) -> dict:
        """A verdict for a run whose exam could not be rebuilt, or nothing.

        THE ONLY CLAIM MADE HERE IS THE ONE THAT CANNOT BE WRONG. finalexam's
        pass rule is `set_solved >= 3 of 4`, `codebase_solved >= 2 of 2`, one
        MEDIUM among the solves and the clocks kept; every clause of it is
        satisfied outright by a run that solved everything in time, whatever the
        exam turned out to be, so that is the only shape this will speak for.
        A partial run is NOT guessed at — `finalexam._verdict` is the one place
        that decides those and this is not a second copy of it.

        The clock is checked per segment where the client sent segment timings,
        because that is the clock `finalexam.debrief` actually measures against,
        and against the whole 115 minutes otherwise.
        """
        m = measured or {}
        total = int(m.get("total") or 0)
        if not total or int(m.get("solved") or 0) != total:
            return {}
        if not m.get("within_clock"):
            return {}
        for segment in (payload.get("segments") or []):
            spent = (seconds_by_segment or {}).get(segment.get("id"))
            if spent is None:
                continue
            if float(spent) > float(segment.get("minutes") or 0) * 60:
                return {}
        # ending.PASS_VERDICT is the string `ending.resolve` compares against.
        # Spelling it from there rather than here keeps one spelling of it.
        return {"verdict": {
            "code": ending.PASS_VERDICT,
            "headline": "That is a pass.",
            "body": ("You solved {t} of {t} with nothing to lean on, inside the "
                     "clock. The per-question debrief could not be rebuilt — the "
                     "corpus moved under this sitting — but the result is the "
                     "measured one and it is not in doubt.").format(t=total),
        }}

    def _recover_exam(self, payload: dict):
        """The composed Exam, from memory or rebuilt from the recipe it was
        drawn with.

        Exam has no from_dict, so the rebuild re-runs the draw — and it can only
        be exact if it is handed the four things that decided it. See the note in
        `_start_exam`: `payload["seed"]` is a number the composer produced AFTER
        drawing and rebuilding from it is a different exam, so `payload["recipe"]`
        is what this reads. The fingerprint check stays and is the arbiter: it is
        what stops a near-miss rebuild being reported as this player's exam, and
        it is what catches an exam composed by a build that wrote no recipe.

        A rebuilt Exam is THE SAME EXAM and keeps its identity. The id is what
        `finalexam.debrief` stamps into `report["exam_id"]`, which is the one
        fact `ending.resolve` uses to recognise the story climax, and a fresh
        `fx-<now>` off the rebuild would quietly disown the run.
        """
        cached = getattr(self, "_exam", None)
        if cached is not None and cached.fingerprint == payload.get("fingerprint"):
            return cached
        recipe = payload.get("recipe") or {}
        try:
            rebuilt = finalexam.compose(
                self.corpus, self.skills,
                profile=recipe.get("profile") or payload.get("profile"),
                seed=recipe.get("seed", payload.get("seed")),
                history=recipe.get("history") or (),
                recent_ids=recipe.get("recent_ids") or (),
                format_id=payload.get("format_id", "THE_PRACTICAL"))
        except Exception:
            return None
        if rebuilt.fingerprint != payload.get("fingerprint"):
            return None
        rebuilt.id = payload.get("id") or rebuilt.id
        rebuilt.seed = payload.get("seed", rebuilt.seed)
        rebuilt.created_at = payload.get("created_at", rebuilt.created_at)
        self._exam = rebuilt
        return rebuilt

    def interview_current(self) -> dict:
        run = self.state.get("interview")
        if not run:
            return {"error": "no interview running"}
        if run["index"] >= len(run["problem_ids"]):
            return self.finish_interview()
        pid = run["problem_ids"][run["index"]]
        payload = self.start_encounter(pid, mode=config.MODE_INTERVIEW,
                                       interview_id=run["id"], reason="INTERVIEW")
        elapsed = time.time() - run["started_at"]
        payload["interview"] = {
            "index": run["index"], "total": len(run["problem_ids"]),
            "seconds_remaining": max(0, run["minutes"] * 60 - elapsed),
            "format": run["format"],
        }
        return payload

    def interview_advance(self, result: dict) -> dict:
        run = self.state.get("interview")
        if not run:
            return {"error": "no interview running"}
        run["results"].append({
            "problem_id": run["problem_ids"][run["index"]],
            "solved": result.get("solved", False),
            "rank": result.get("rank", ""),
            "seconds": result.get("seconds", 0),
            "root_cause": result.get("analysis", {}).get("root_cause", ""),
        })
        run["index"] += 1
        self.save()
        if run["index"] >= len(run["problem_ids"]):
            return self.finish_interview()
        return {"next": True, "index": run["index"], "total": len(run["problem_ids"])}

    def finish_interview(self, seconds_by_segment: dict | None = None) -> dict:
        run = self.state.get("interview")
        if not run:
            return {"error": "no interview running"}
        results = run["results"]
        solved = sum(1 for r in results if r["solved"])
        total = max(len(run["problem_ids"]), 1)
        seconds = time.time() - run["started_at"]
        within = seconds <= run["minutes"] * 60
        score = round(100 * solved / total * (1.0 if within else 0.85))
        # THE DEBRIEF IS TAKEN AFTER THE RUN IS MEASURED, and only because of
        # what happens when the exam cannot be rebuilt: that branch has no
        # per-question report to read a verdict out of, and the four numbers it
        # needs in order not to call a clean sweep a failure are these four,
        # which are measured here and nowhere else. Moving the call down is the
        # whole of it — nothing between this line and the top of the method
        # touches `results` or `state["exam"]`.
        debrief = self._exam_debrief(
            results, seconds_by_segment,
            measured={"solved": solved, "total": len(run["problem_ids"]),
                      "within_clock": within})

        causes = [r["root_cause"] for r in results if r.get("root_cause")]
        # finalexam.CAUSE_BUCKETS is the named version of what used to be three
        # inline sets here. Two copies of "what a root cause means" would drift.
        buckets = finalexam.CAUSE_BUCKETS
        knowledge = sum(1 for c in causes if c in buckets["knowledge"])
        implementation = sum(1 for c in causes if c in buckets["implementation"])
        timing = sum(1 for c in causes if c in buckets["timing"])

        db.record_interview(
            self.conn, profile=run["profile"], format=run["format"],
            problem_ids=",".join(run["problem_ids"]), score=score, solved=solved,
            total=total, seconds=seconds, detail=str(results))

        secrets = []
        if solved == total and total:
            self.state["stats"]["interviews_passed"] = int(
                self.state["stats"].get("interviews_passed", 0)) + 1
            # No Scratches: every problem solved with no failed submission.
            if all(r.get("rank") for r in results):
                award = self._award_secret("secret_flawless_run")
                if award:
                    secrets.append(award)

        was_exam = run["format"] == "FINAL_EXAM"
        self.state["interview"] = None
        self.state["exam"] = None
        self._exam = None
        self._write_encounter(None)
        self.save()
        saves.autosave(self.conn, self.state, "session_end")

        # The beat about the last trial fires HERE rather than at the door,
        # after `interview` has been cleared. collect_story pays beat rewards,
        # and a measured run pays nothing into the world — that invariant is
        # worth more than firing the line thirty seconds earlier. The herald at
        # the door is the examiner's own arrival, which is static prose and
        # costs nothing.
        story = (self.collect_story(events=("last_trial_entered",))
                 if was_exam else [])

        out = {
            "finished": True, "score": score, "solved": solved, "total": total,
            "debrief": debrief, "story": story,
            "seconds": round(seconds), "within_time": within,
            "results": results,
            "breakdown": {"knowledge_failures": knowledge,
                          "implementation_failures": implementation,
                          "time_failures": timing},
            "verdict": self._interview_verdict(score, knowledge, implementation, timing),
            "coach_now_available": True,
            "secrets": secrets,
            "history": db.interview_history(self.conn, limit=10),
        }
        # THE LAST SCENE, AFTER THE PRACTICAL IS SCORED AND NOT BEFORE.
        #
        # `self.state["interview"]` has already been cleared above, so the
        # encounter this is handed is None and the MENTOR seal is open: a
        # cutscene is a named voice speaking to you, which is exactly the mentor
        # crutch, and staging it one line earlier would be staging it inside a
        # measured run.
        #
        # THERE IS NO `if` HERE, AND ITS ABSENCE IS THE FEATURE. This used to
        # read `if was_exam:` and fire the finale — which meant a practice
        # practical, sittable from the menu on the first morning with no keys,
        # ended the game. `ending.resolve` is called after EVERY interview run
        # precisely so that the question "was this the story or a measurement"
        # has exactly one answer in exactly one place. For every ordinary run,
        # staged or not, it returns `triggered: False`, plays nothing, frees
        # nobody and moves nothing in the world.
        #
        # `weak_regions` is not passed: ending.WIRING marks it optional and
        # this class has no such method. Nor are `released` / `collapse_lines`
        # — ending.py makes `captives.liberate(state, passed=True)` itself on
        # the pass branch and builds both rosters from it, which is also what
        # frees the three the Interviewer took out of the home village.
        out["ending"] = ending.resolve(
            self.state,
            exam_report=debrief,
            readiness=self._readiness(),
            transfer_summary=self.transfer_report(),
            cleared_bosses=list(self.state["cleared_bosses"]),
            names=self._identifiers_named(),
            encounter=self.encounter)          # None by here, and correctly so
        self.save()
        return out

    @staticmethod
    def _interview_verdict(score, knowledge, implementation, timing) -> str:
        if score >= 90:
            return ("That is a passing performance on this format. Keep the retests "
                    "current so it stays true next week.")
        parts = []
        if knowledge >= max(implementation, timing) and knowledge:
            parts.append("The failures were mostly RECOGNITION — you did not identify "
                         "the family, so the implementation never had a chance. That is "
                         "the cheapest thing on this list to fix.")
        if implementation >= max(knowledge, timing) and implementation:
            parts.append("The failures were mostly IMPLEMENTATION — you knew the "
                         "approach and the Python got in the way. Village drills.")
        if timing >= max(knowledge, implementation) and timing:
            parts.append("The failures were mostly TIME — correct thinking, too slow to "
                         "finish. The Chronomancer's Arena is built for this.")
        if not parts:
            parts.append("Mixed causes. Work the specific root cause listed per problem.")
        return " ".join(parts)

    # -- typed-Python combat: the enemies ARE the variables ----------------
    # bestiary.py names the creatures and incantation.py owns the line the
    # player types. The engine holds the field between turns and nothing else:
    # the BattleContext is rebuilt from (encounter id, hp, turn) every request,
    # because it carries live Python objects and does not belong in a save file.
    def incantation_encounters(self, region_id: str = "") -> dict:
        region_id = region_id or self.state["player"].get("region", "")
        rows = bestiary.encounters_for_region(region_id)
        return {"region": region_id,
                "encounters": [{"id": e.id, "title": e.title, "blurb": e.blurb,
                                "chapter": e.chapter, "lesson": e.lesson,
                                "enemies": list(e.enemies)} for e in rows]}

    # ======================================================================
    # The incantation battle: the turn-based fight, in full
    # ======================================================================
    #
    # This is the fight the tactical layer was built for. The enemies have hit
    # points and stand there for eight to twenty casts (bestiary.MIN_CASTS /
    # MAX_CASTS), which means there is room for turns, for focus, for a status
    # to run its course and for a potion to matter. The problem encounter is
    # turn-aware too — one graded submission is one turn there as well — but it
    # ends the moment the line lands, so it is a one-exchange duel by nature.
    #
    # THE ORDER OF A TURN, and every part of it is somebody else's function:
    #
    #   1. the player types Python. incantation.cast decides whether it was
    #      correct. Wrong is a wasted turn and zero damage, and nothing below
    #      can change either of those.
    #   2. a correct cast's damage goes through elements.resolve_damage, which
    #      scales it and cannot generate it: feed it zero and zero comes out.
    #   3. the turn advances — potions.cast_resolved — right or wrong, which is
    #      what stops the pouch being emptied by typing nonsense.
    #   4. the enemy acts: its poison ticks, it may drink, it may spend focus on
    #      a special, and its blow resolves through the same damage function.
    #   5. the player's next turn opens: elements.tick_statuses on them, poison
    #      bites, focus returns unless something has VOIDED it.
    #
    # A potion is drunk between 5 and 1, through use_potion, and drinking is not
    # a turn. That is the entire argument of the feature.

    INCANT_STATE = "incantation"

    def _incantation_region(self, encounter_id: str) -> str:
        fight = bestiary.ENCOUNTER_BY_ID.get(encounter_id)
        if fight is not None:
            return fight.region
        boss = bestiary.BOSS_BY_ID.get(encounter_id)
        return boss.region if boss is not None else ""

    def start_incantation(self, encounter_id: str) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        # battle_context does not raise on an unknown id — it hands back an
        # empty battlefield, which is a fight with nothing in it that reports
        # itself already cleared. The try/except below therefore never fired.
        if encounter_id not in bestiary.ENCOUNTER_BY_ID:
            return {"error": "unknown incantation encounter"}
        try:
            ctx = bestiary.battle_context(encounter_id,
                                          mode=config.MODE_ADVENTURE)
        except (KeyError, TypeError):
            return {"error": "unknown incantation encounter"}
        region = self._incantation_region(encounter_id)
        element = elements.affinity_for(region)
        difficulty = self._incantation_difficulty(encounter_id)
        vitals = {}
        for enemy in ctx.enemies:
            row = bestiary.vitals(hp=enemy.hp_max, element=(
                element if element in elements.ELEMENTS else ""))
            row["antidotes"] = potions.carries_antidote(
                difficulty=difficulty, affinity=str(element or "").lower(),
                rng=self._rng)
            vitals[enemy.name] = row
        self.state[self.INCANT_STATE] = {
            "encounter": encounter_id,
            "region": region,
            "difficulty": difficulty,
            "hp": {e.name: e.hp for e in ctx.enemies},
            "vitals": vitals,
            "turn": 0, "casts": 0, "started_at": time.time(),
            # The fight's own tactical record. All plain JSON, so a twenty-turn
            # battle survives a page refresh — which it has to, because twenty
            # turns is twenty lines of Python and losing those to a reload is
            # the one thing that would stop a player using the feature.
            "potion_turn": potions.new_fight().to_dict(),
            "poison": {},
            "statuses": [],
            "enemy_poison": {},
            "attacker": 0,
            "log": [],
        }
        self.save()
        return self.incantation_view(ctx)

    def _incantation_difficulty(self, encounter_id: str) -> str:
        """What tier of potion this fight pays out and how likely a monster is
        to be carrying a vial. Read off the chapter the fight belongs to rather
        than invented, so a fight deeper in the curriculum is deeper here too."""
        fight = (bestiary.ENCOUNTER_BY_ID.get(encounter_id)
                 or bestiary.BOSS_BY_ID.get(encounter_id))
        if fight is None:
            return "EASY"
        rank = bestiary.chapter_rank(getattr(fight, "chapter", ""))
        if encounter_id in bestiary.BOSS_BY_ID:
            return "BOSS"
        return ("TUTORIAL", "EASY", "MEDIUM", "HARD", "ELITE")[
            min(4, max(0, rank))]

    def _incantation_context(self):
        run = self.state.get(self.INCANT_STATE)
        if not run:
            return None
        ctx = bestiary.battle_context(run["encounter"],
                                      mode=config.MODE_ADVENTURE,
                                      hp=dict(run.get("hp") or {}))
        ctx.turn = int(run.get("turn", 0))
        return ctx

    def _incant_pouch_view(self, run: dict) -> dict:
        return potions.pouch_view(
            self._pouch(), player=self.state["player"],
            turn_state=potions.TurnState.from_dict(run.get("potion_turn")),
            poison=potions.Poison.from_dict(run.get("poison")),
            encounter=None,
            statuses=self._load_statuses(run.get("statuses")))

    def incantation_view(self, ctx=None) -> dict:
        run = self.state.get(self.INCANT_STATE)
        if not run:
            return {"incantation": None}
        ctx = ctx or self._incantation_context()
        moveset = self.state["moveset"]
        skills = self.skills
        chapter = curriculum.frontier(skills)
        demand = incantation.next_demand(moveset, ctx, chapter=chapter,
                                         rng=self._rng)
        moves = []
        for move in incantation.equipped(moveset):
            tier = incantation.tier_for_move(moveset, move.id, skills)
            rendered = incantation.render_template(move, tier, context=ctx)
            moves.append({**rendered, "id": move.id, "tier": tier,
                          "teach": move.note, "skill": move.skill})
        vitals = run.get("vitals") or {}
        player = self.state["player"]
        player_element = self._player_element(None)
        return {
            "incantation": {
                "encounter": run["encounter"],
                "region": run.get("region", ""),
                "turn": ctx.turn,
                "timer_seconds": 0,       # adventure teaches; only exams are timed
                "enemies": [{**e.to_dict(), "vitals": vitals.get(e.name, {})}
                            for e in ctx.enemies],
                "bindings": ctx.bindings(),
                "demand": demand,
                "casts": run.get("casts", 0),
                "cleared": not ctx.living(),
                # -- the tactical layer -------------------------------------
                "statuses": list(run.get("statuses") or []),
                "poison": potions.Poison.from_dict(run.get("poison")).to_dict(),
                "log": list(run.get("log") or []),
                "element": {
                    "region": elements.affinity_for(run.get("region", "")),
                    "player": player_element,
                    "armour": items.armour_view(self.effects()),
                },
                # The two sentences that teach the whole turn. A mechanic the
                # player cannot see is a mechanic they conclude is broken.
                "rule": "Land the line and nothing reaches you but what it "
                        "saved up for. Miss, and it swings.",
                "potion_rule": "A draught rides with your cast. It is never "
                               "instead of one.",
                "health": {"value": player["stamina"],
                           "max": player["stamina_max"]},
                "focus": {"value": player["mana"], "max": player["mana_max"]},
            },
            "pouch": self._incant_pouch_view(run),
            "moveset": moves,
        }

    def incantation_cast(self, move_id: str, answers: dict) -> dict:
        # Asked at the door, like every other overworld action. start_incantation
        # already refuses, but a battle OPENED before an exam began would
        # otherwise keep running through it with the whole loadout attached —
        # the gear, the wheel and the pouch — which is a second isolation path
        # in a codebase that has spent a whole module having exactly one.
        sealed = self._sealed_in_interview()
        if sealed:
            return sealed
        run = self.state.get(self.INCANT_STATE)
        if not run:
            return {"error": "no incantation battle running"}
        ctx = self._incantation_context()
        skills = self.skills
        tier = incantation.tier_for_move(self.state["moveset"], move_id, skills)
        # apply=False, and this is the one substantive change to how a cast
        # lands. incantation.cast still decides ALONE whether the line was
        # correct and what it is worth; what it no longer does is subtract,
        # because between "what the typing earned" and "what the monster loses"
        # sits the wheel, and the wheel is elements.resolve_damage.
        result = incantation.cast(move_id, answers, ctx, tier=tier,
                                  seconds=time.time() - run["started_at"],
                                  streak=int(self.state["player"]["combo"]),
                                  timed=False, apply=False)
        incantation.record_cast(self.state["moveset"], result, tier=tier)
        # skill_deltas are graded evidence — the cast either ran the player's own
        # Python or it did not — so they fold in the way _apply_outcome does.
        for name, delta in (result.skill_deltas or {}).items():
            state = skills.get(name)
            if state is None:
                continue
            state.mastery = max(0.0, min(100.0, state.mastery + delta))
            legendaries.clamp_to_ceiling(state, self.state["hand"])
            state.stage = skillmod.derive_stage(state)
        self._write_skills(skills)

        lines: list = []
        strike = self._incant_strike(run, ctx, result, lines)

        # A LANDED LINE RETURNS A POINT OF HEALTH, AND THIS IS NOT A BONUS.
        #
        # `submit` has always refunded stamina on a solved answer, and it ends
        # the fight in the same breath. This loop refunded nothing and runs
        # fifteen to forty turns, which made it the only fight in the game a
        # player could be routed out of while typing PERFECTLY: twenty-four of
        # the thirty-seven authored encounters, with no armour and nothing to
        # drink. The arithmetic and the choice of number are in CAST_HEAL_SHARE.
        #
        # It cannot be farmed: it is capped at the bar, a cast that did not land
        # gets nothing, and a cast is a turn — which is the same pair of
        # conditions `submit` uses and the same rule the pouch is held to.
        if result.correct:
            player = self.state["player"]
            back = max(CAST_HEAL_FLOOR,
                       int(round(CAST_HEAL_SHARE * int(player["stamina_max"]))))
            player["stamina"] = min(int(player["stamina_max"]),
                                    int(player["stamina"]) + back)

        # The turn moves, right or wrong. A wasted turn is still a turn: that is
        # the Blitz rule this file inherits, and the pouch does not get a
        # separate opinion about it.
        turn_state = potions.TurnState.from_dict(run.get("potion_turn"))
        potions.cast_resolved(turn_state, correct=result.correct)
        run["potion_turn"] = turn_state.to_dict()

        cleared = not ctx.living()
        enemy_turn = None
        turn_open = None
        routed = False
        incant_death: dict = {}
        if not cleared:
            enemy_turn = self._incant_enemy_turn(run, ctx, lines,
                                                 correct=bool(result.correct))
            turn_open = self._incant_open_turn(run, lines)
            incant_death = death.check(self.conn, self.state,
                                       cause="incant_enemy_turn", encounter=None)
            if incant_death.get("died"):
                self.state = incant_death["state"]
            routed = int(self.state["player"]["stamina"]) <= 0
            # ASKED AGAIN, BECAUSE THE ENEMY'S TURN CAN END THE FIGHT. The
            # first thing `_incant_enemy_turn` does is tick the acting monster's
            # own poison, and a dose that finishes it finishes it there — which
            # is the whole reason poisoning something is worth a turn. Asking
            # only before that left a player standing in a field of corpses with
            # the battle still officially running, having to swing at nothing to
            # be told they had won; and the swing at nothing reads in the log as
            # a cast that landed on no one, which is worse than the wait.
            cleared = not ctx.living()
            if cleared:
                routed = False       # you do not get routed out of a win

        run["hp"] = {e.name: e.hp for e in ctx.enemies}
        run["turn"] = int(ctx.turn) + 1
        run["casts"] = int(run.get("casts", 0)) + 1
        # The same ledger _tick_hunt keeps. A line typed here was graded by
        # incantation.cast, so if an apex fight is open in THIS region it counts
        # against it, on the same terms an ordinary clear does.
        if result.correct:
            block = self._hunt_state()
            open_fight = block.get("fight")
            if open_fight and open_fight.get("region") == run.get("region"):
                open_fight["casts"] = int(open_fight.get("casts", 0)) + 1
        run["log"] = (list(run.get("log") or []) + lines)[-40:]

        payload = {**result.to_dict(), "ok": result.correct,
                   "strike": strike, "enemy_turn": enemy_turn,
                   "turn_open": turn_open, "lines": lines,
                   **self.incantation_view(ctx)}
        # Same shape as the graded-submission payload, so the client plays one
        # death sequence rather than two. `incant_death` is only bound when the
        # fight was still open; a win never asks.
        if not cleared and incant_death.get("died"):
            payload["death"] = incant_death
        if cleared:
            self.state["player"]["xp"] += 40 + 10 * len(ctx.enemies)
            potion = self._incant_reward(run)
            if potion:
                payload["potion"] = potion
            self.state[self.INCANT_STATE] = None
            payload["cleared"] = True
        elif routed:
            payload["routed"] = self._incant_rout()
        self.save()
        return payload

    def _incant_strike(self, run: dict, ctx, result, lines: list) -> dict | None:
        """The player's blow, through the wheel, applied to one monster.

        `result.damage` is what the typed line earned and is the `base`
        argument; a wrong cast brings zero here and zero is what comes out.
        Nothing in this method can manufacture a hit.
        """
        if not result.correct or not result.damage:
            return None
        enemy = ctx.enemy(result.target) or (ctx.living() or [None])[0]
        if enemy is None:
            return None
        vitals = (run.get("vitals") or {}).setdefault(
            enemy.name, bestiary.vitals(hp=enemy.hp_max))
        enemy_statuses = self._load_statuses(vitals.get("statuses"))
        player_statuses = self._load_statuses(run.get("statuses"))
        hit = elements.resolve_damage(
            int(result.damage), self._player_element(None),
            elements.Defender(element=vitals.get("element", elements.NEUTRAL),
                              armour=elements.NO_ARMOUR,
                              statuses=enemy_statuses,
                              max_health=int(vitals.get("hp_max", enemy.hp_max))),
            attacker_statuses=player_statuses,
            roll=self._rng.random())
        enemy.hp = max(0, enemy.hp - hit.damage)
        vitals["hp"] = enemy.hp
        lines.append(f"{enemy.display}: {hit.line}")
        if hit.inflicted == "POISONED":
            # A MONSTER's poison lives in the dose pool rather than on the
            # wheel, because potions.monster_cure is the function that makes a
            # monster drink and it takes a potions.Poison. The player's lives on
            # the wheel, for the mirror-image reason: potions.drink's `statuses`
            # argument is what clears it. One record per combatant, chosen by
            # who has to read it — write both and a single poisoning bites
            # twice, from two modules that each think they are the only one
            # counting.
            pool = potions.Poison.from_dict(
                (run.setdefault("enemy_poison", {})).get(enemy.name))
            landed = potions.poison_apply(pool, damage=2, turns=3,
                                          source="player")
            run["enemy_poison"][enemy.name] = pool.to_dict()
            lines.append(f"{enemy.display}: {landed.get('line') or 'venom takes.'}")
        elif hit.inflicted:
            landed = elements.inflict(enemy_statuses, hit.inflicted)
            if landed.get("applied"):
                lines.append(f"{enemy.display}: {landed['line']}")
        vitals["statuses"] = self._dump_statuses(enemy_statuses)
        return {**hit.to_dict(), "target": enemy.name,
                "defeated": not enemy.alive}

    def _incant_enemy_turn(self, run: dict, ctx, lines: list, *,
                           correct: bool = False) -> dict | None:
        """One enemy acts. ONE, not all of them, and not on every turn.

        TWO RULES, AND THE ARITHMETIC THAT FORCES BOTH.

        ONE ENEMY. A field of four monsters all swinging every turn would
        quadruple the incoming damage without quadrupling anything the player
        learns. They take it in turns, round-robin, which keeps the pressure
        flat across a two-monster fight and a four-monster one.

        AND IT SWINGS ON A WASTED TURN, OR WHEN IT HAS SAVED UP FOR SOMETHING.
        elements.MIN_DAMAGE is one, so an enemy that swings every turn of a
        twenty-cast fight takes twenty points off a twenty-point bar whatever
        the player is wearing — which would make every authored fight in
        bestiary.py unwinnable without a pouch full of potions, and a fight you
        can only win by shopping is not a fight about Python.

        So the rule is the one bestiary.py already wrote down as the Blitz rule:
        a wrong cast wastes the turn AND THE ENEMY GETS TO ACT. Land the line
        and the only thing that reaches you is whatever it has been saving its
        focus for — which is why focus exists, and why an enemy standing there
        charging is worth watching rather than worth ignoring.

        Its own clock runs either way: poison bites it, its statuses count down,
        it drinks if it needs to and it banks focus. A correct cast buys you the
        blow, not the turn.
        """
        living = ctx.living()
        if not living:
            return None
        index = int(run.get("attacker", 0)) % len(living)
        run["attacker"] = index + 1
        enemy = living[index]
        vitals = (run.get("vitals") or {}).setdefault(
            enemy.name, bestiary.vitals(hp=enemy.hp_max))
        out: dict = {"who": enemy.name, "display": enemy.display,
                     "damage": 0, "special": None, "cured": None}

        # 1. its own poison, and its own statuses, before it gets to act.
        enemy_statuses = self._load_statuses(vitals.get("statuses"))
        tick = elements.tick_statuses(enemy_statuses,
                                      int(vitals.get("hp_max", enemy.hp_max)))
        pool = potions.Poison.from_dict(
            (run.get("enemy_poison") or {}).get(enemy.name))
        dot = potions.poison_tick(pool)
        bleed = int(tick["damage"]) + int(dot["damage"])
        if bleed:
            enemy.hp = max(0, enemy.hp - bleed)
            vitals["hp"] = enemy.hp
            lines.append(f"{enemy.display}: {bleed} from what is in it.")
        lines += [f"{enemy.display}: {l}" for l in tick["lines"]]
        vitals["statuses"] = self._dump_statuses(enemy_statuses)
        if not enemy.alive:
            run.setdefault("enemy_poison", {})[enemy.name] = pool.to_dict()
            out["defeated"] = True
            return out

        # 2. the vial. Drinking IS its turn, which is why poisoning something
        #    that can cure itself is never wasted: the cure buys you a free
        #    turn, and a free turn is one more line of Python landed for
        #    nothing.
        monster = {"hp": enemy.hp, "hp_max": enemy.hp_max,
                   "display": enemy.display,
                   "antidotes": int(vitals.get("antidotes", 0) or 0)}
        cured = potions.monster_cure(monster, pool, rng=self._rng)
        vitals["antidotes"] = int(monster.get("antidotes", 0) or 0)
        run.setdefault("enemy_poison", {})[enemy.name] = pool.to_dict()
        if cured is not None:
            lines += [cured["line"], cured["aside"]]
            out["cured"] = cured
            return out

        # 3. focus, and what it buys.
        gained = bestiary.regenerate(vitals)
        special = bestiary.take_turn(vitals, roll=self._rng.random())
        out["focus"] = vitals.get("focus", 0)
        out["focus_gained"] = gained
        power = 1.0
        if special:
            power = float(special["power"])
            out["special"] = special
            lines.append(special["line"].format(who=enemy.display))

        # 4. the blow — if it has earned one. See the docstring: a landed line
        #    means nothing reaches you except what it saved up for.
        if not special and correct:
            out["held"] = True
            lines.append(f"{enemy.display} holds, and banks what it has.")
            return out
        player_statuses = self._load_statuses(run.get("statuses"))
        hit = elements.resolve_damage(
            max(0, int(round(ENEMY_BASE_DAMAGE * power))),
            vitals.get("element", elements.NEUTRAL),
            self._player_defender(None, player_statuses),
            attacker_statuses=enemy_statuses,
            roll=self._rng.random())
        player = self.state["player"]
        player["stamina"] = max(0, int(player["stamina"]) - hit.damage)
        out["damage"] = hit.damage
        out["hit"] = hit.to_dict()
        lines.append(f"You: {hit.line}")
        # The player's poison lives on the WHEEL and only there — see the note
        # in `_enemy_turn`. potions.drink clears it through its `statuses`
        # argument, so the antidote in the belt still works on it; what it must
        # not also do is land a dose, because then one poisoning ticks twice.
        # Same rule as `_enemy_turn`, same owner: a charged attack cannot leave a
        # mark a plain hit of that matchup was not allowed to leave.
        for status_id in (hit.inflicted, (special or {}).get("inflicts", "")):
            if not status_id or not elements.marks(hit.kind):
                continue
            landed = elements.inflict(player_statuses, status_id)
            if landed.get("applied"):
                lines.append(landed["line"])
                out["inflicted"] = status_id
        run["statuses"] = self._dump_statuses(player_statuses)
        return out

    def _incant_open_turn(self, run: dict, lines: list) -> dict:
        """The player's next turn begins: statuses tick, poison bites, focus
        returns unless something has VOIDED it.

        Here rather than at the top of the next cast, so the player reads the
        tick BEFORE they choose what to drink — and so a dose that has already
        landed cannot be rewound by a potion, which is the rule potions.py
        states and this is the call site that keeps it.
        """
        player = self.state["player"]
        statuses = self._load_statuses(run.get("statuses"))
        tick = elements.tick_statuses(statuses,
                                      int(player.get("stamina_max", 1) or 1))
        venom = potions.Poison.from_dict(run.get("poison"))
        dot = potions.poison_tick(venom)
        damage = int(tick["damage"]) + int(dot["damage"])
        if damage:
            player["stamina"] = max(0, int(player["stamina"]) - damage)
        regained = 0
        if not tick["regen_blocked"]:
            before = int(player["mana"])
            player["mana"] = min(int(player["mana_max"]), before + FOCUS_PER_TURN)
            regained = int(player["mana"]) - before
        run["statuses"] = self._dump_statuses(statuses)
        run["poison"] = venom.to_dict()
        lines += list(tick["lines"])
        if dot["line"]:
            lines.append(dot["line"])
        return {"damage": damage, "focus_regained": regained,
                "regen_blocked": bool(tick["regen_blocked"])}

    def _incant_reward(self, run: dict) -> dict | None:
        """A potion off the field, on the same table the rest of the game
        rolls. Gear does not drop here — a forged blade is never found and an
        incantation fight is not a loot run — but ammunition does, because the
        next fight in this chapter is the one it is for."""
        element = elements.affinity_for(run.get("region", ""))
        drop = potions.roll_monster_drop(
            difficulty=run.get("difficulty", "EASY"), rank="B",
            luck=self.effects().get("loot_luck", 0.0),
            affinity=str(element or "").lower(), rng=self._rng)
        if not drop:
            return None
        got = potions.grant(self.state, drop)
        return {**drop, "held": got.get("held", 0),
                "overflow": got.get("overflow", 0)}

    def _incant_rout(self) -> dict:
        """Health at zero is never a loss and never a wall.

        The fight ends, the player is put back on their feet at a third of the
        bar — the same restoration a failed encounter already gets — and the
        door they walked in through is still open. Nothing is taken: the casts
        that landed already moved mastery on their own evidence, one line at a
        time, and no part of that is refunded because none of it was a loan.
        """
        player = self.state["player"]
        player["stamina"] = max(4, player["stamina_max"] // 3)
        self.state[self.INCANT_STATE] = None
        return {
            "routed": True,
            "message": ("You are on one knee and the field is still standing. "
                        "Nothing you landed is lost — every line you got right "
                        "is already in your hands. Go back in when you are "
                        "ready, and take something to drink."),
            "stamina": player["stamina"],
        }

    def leave_incantation(self) -> dict:
        self.state[self.INCANT_STATE] = None
        self.save()
        return {"ok": True}

    # -- progression bookkeeping -------------------------------------------
    def _advance_weapons(self, skills: dict):
        events = []
        for weapon in world.WEAPONS:
            state = skills.get(weapon["skill"])
            if state is None:
                continue
            tier = 0
            if state.unaided_clears >= 3:
                tier = 1
            if state.unaided_clears >= 5 and state.mastery >= 55:
                tier = 2
            if state.retention >= 45:
                tier = 3
            if state.mastery >= 82 and state.speed >= 60 and state.hint_dependence <= 25:
                tier = 4
            previous = self.state["weapons"].get(weapon["id"], 0)
            if tier > previous:
                self.state["weapons"][weapon["id"]] = tier
                events.append({"id": weapon["id"], "name": weapon["name"],
                               "tier": tier, "icon": weapon["icon"],
                               "criterion": weapon["tiers"][min(tier - 1, 3)]})
        return events[0] if events else None

    def _check_companions(self, skills: dict):
        for companion in world.COMPANIONS:
            if companion["id"] in self.state["companions"]:
                continue
            state = skills.get(companion["skill"])
            if state and state.mastery >= 40 and state.unaided_clears >= 2:
                self.state["companions"].append(companion["id"])
                return companion
        return None

    def _check_achievements(self, skills, problem, solved, rank, first_try, seconds):
        earned = []

        def award(aid):
            if aid not in self.state["achievements"]:
                self.state["achievements"].append(aid)
                found = next((a for a in world.ACHIEVEMENTS if a["id"] == aid), None)
                if found:
                    earned.append(found)

        if solved and rank == "S":
            award("first_blood")
        if skills["HASH_MAP"].unaided_clears >= 5:
            award("hash_slinger")
        if skills["SLIDING_WINDOW"].speed >= 60:
            award("window_cleaner")
        if min(skills["DFS"].clears, skills["BFS"].clears, skills["TREE"].clears) >= 1:
            award("tree_climber")
        if solved and problem.difficulty == "MEDIUM" and self.encounter is None:
            pass
        if solved and first_try:
            award("first_try")
        if self.state["stats"]["armor_repairs"] >= 10:
            award("bug_hunter")
        if all(v >= 100 for k, v in self.state["armor"].items() if k != "legendary"):
            award("armorsmith")
        if solved and self.encounter and self.encounter.is_retest:
            award("memory_master")
        if skills["BIG_O"].mastery >= 70:
            award("explainer")
        if "the_interviewer" in self.state["cleared_bosses"]:
            award("legend")
        return earned

    # -- misc --------------------------------------------------------------
    def set_setting(self, key: str, value) -> dict:
        self.state["settings"][key] = value
        self.save()
        return self.state["settings"]

    def set_profile(self, profile: str) -> dict:
        if profile in config.INTERVIEW_PROFILES:
            self.state["player"]["profile"] = profile
            self.save()
        return {"profile": self.state["player"]["profile"]}

    def move(self, region: str, x: int, y: int) -> dict:
        self.state["player"]["region"] = region
        self.state["player"]["x"] = x
        self.state["player"]["y"] = y
        # THE GEOGRAPHY CLAUSE'S EVIDENCE, and the one write story.py asks the
        # engine to make outside `apply`.
        #
        # A story chain that fires on mastery alone gives a fast player a
        # Coliseum NPC commenting on their times while they are standing in
        # Python Village at level six. `story.needs_geography` refuses to let a
        # beat about a place fire before the player has been in it, and this
        # list is how it knows. It returns True the first time only, so arrival
        # is an event rather than a per-step write.
        arrived = storymod.note_region(self.state["story"], region)
        # He notices the first time and never again. `note_region` returning
        # True is the arrival; asking on every step would be a villain with a
        # motion sensor rather than a villain reading a file.
        watching = self._antagonist(antagonist.REGION_ENTERED,
                                    detail={"region": region}) if arrived else {}
        self.save()
        return {"ok": True, "arrived": bool(arrived),
                "watching": watching or None}

    def problem(self, problem_id: str, *, mode: str = config.MODE_ADVENTURE) -> dict:
        """Look one problem up by id. The browsable door, so it is also the
        obvious way to read the hold-out one id at a time; it refuses.

        THE MODE OF A LOOKUP IS NOT THE CLIENT'S TO DECLARE —
        docs/10-sealed-views.md §4.A, and it was the critical one.

        `player_view(mode=)` redacts the pattern, the hint tree, the
        visualisation, the common failures and the optimal complexity only when
        the string is exactly "interview". The problem id is in the encounter
        payload the run itself hands the client — it has to be, or the client
        could not submit — so `GET /api/problem?id=<the id on the screen>
        &mode=adventure` handed over PATTERN, HINTS, VISUALS and most of
        WEAKNESS_MAP for the question being measured, through one GET, with no
        capability consulted anywhere on the path.

        The parameter is still accepted, because a caller may legitimately ask
        for the stricter view. It can only ever make the answer stricter now.
        """
        p = self.by_id.get(problem_id)
        if p is None:
            return {"error": "unknown problem"}
        if corpusmod.is_sealed(p):
            return finalexam.refuse(finalexam.HOLDOUT)
        if self.state.get("interview") or (
                self.encounter and self.encounter.mode == config.MODE_INTERVIEW):
            mode = config.MODE_INTERVIEW
        return p.player_view(mode=mode)

    def performance_history(self, problem_id: str | None = None) -> dict:
        """What you have done. DEGRADE — docs/10-sealed-views.md §4.B.

        The aggregates are world: recent attempts, boss history, interview
        history, the stats block. `problem_id` is not. `db.attempts_for` is a
        SELECT *, and the attempts table stores `pattern`, `family`,
        `declared_pattern` and `root_cause` — so asking it for the id on the
        screen answered with the family name. That is the same leak as the
        problem lookup, one hop further round, and it survives fixing that one.

        A measured run gets the aggregates and an empty per-problem list, with
        the reason named, rather than a 409 on the whole screen.
        """
        sealed = bool(self._sealed_in_interview())
        return {
            "recent": db.recent_attempts(self.conn, limit=60),
            "problem": ([] if sealed or not problem_id
                        else db.attempts_for(self.conn, problem_id)),
            "bosses": db.boss_history(self.conn),
            "interviews": db.interview_history(self.conn),
            "stats": db.attempt_stats(self.conn),
            "sealed": sealed,
            "seal_note": ("Prior attempts on one problem name its pattern and "
                          "its family. The totals are yours to read; the row "
                          "for the question in front of you is not."
                          if sealed else ""),
        }

    # Keys the save carries that name problems the player has NOT been served
    # yet. See `export`.
    EXPORT_REDACTED = ("interview", "exam")

    def export(self) -> dict:
        """The save, with the unserved hold-out roster taken out of it.

        docs/10-sealed-views.md §4.H, the spend test, and the other critical.
        `run_view` was fixed once for exactly this and the save was never
        re-checked: a measured run reaches for the hold-out FIRST, so
        `state["interview"]["problem_ids"]` is a list of sealed problems the
        player has not been served yet, and a sealed problem is spent when it is
        SERVED. Reading the list therefore costs nothing and buys the player the
        ability to go and study the questions the selector likes best. The final
        practical is worse: `_start_exam` writes `state["exam"]`, which the
        engine's own comment says "carries every question's problem_id and
        title" — which is why the RESPONSE uses `exam.player_view()`. The save
        kept the other one and this door shipped the save.

        Redacted ALWAYS, not only mid-run, because neither key is needed to
        restore a save: a reload re-derives both, and an exported run is a run
        the player has chosen to bank rather than one they are sitting.
        """
        payload = db.export_save(self.conn)
        state = payload.get("state") if isinstance(payload, dict) else None
        if isinstance(state, dict):
            for key in self.EXPORT_REDACTED:
                if state.get(key):
                    state[key] = None
            payload["redacted"] = list(self.EXPORT_REDACTED)
        return payload

    def import_save(self, payload: dict) -> dict:
        """Load a save file, or report why it was refused and change nothing."""
        try:
            db.import_save(self.conn, payload)
        except db.InvalidSave as exc:
            # Refusing loudly matters more than loading something: a bad import
            # used to delete the player's entire graded history and say "ok".
            return {"ok": False, "error": str(exc)}
        self.state = self._load_or_create()
        return {"ok": True}


# Best to worst. grading.rank_for produces these and nothing else.
RANK_ORDER = ("S", "A", "B", "C", "LEARNING_CLEAR")


def _worse_rank(left: str, right: str) -> str:
    """The lower of two ranks. An empty string means "no opinion"."""
    if not left:
        return right
    if not right:
        return left
    return max(left, right, key=lambda r: RANK_ORDER.index(r)
               if r in RANK_ORDER else len(RANK_ORDER))


def _better_rank(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    return min(left, right, key=lambda r: RANK_ORDER.index(r)
               if r in RANK_ORDER else len(RANK_ORDER))


def _deep_copy(value):
    import copy
    return copy.deepcopy(value)


def _merge(base: dict, incoming: dict) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
