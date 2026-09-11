"""The narrative spine: acts, quest chains, a rival, mentors who remember you.

The engine already knows what the player can do. It does not know what any of it
*means*. This module is the meaning layer, and it is deliberately inert: it holds
no state, mutates nothing, and imports nothing that could import it back. The
engine builds a context out of state it already has, asks this module what fires,
and pays out.

Three rules constrain every line of content below.

1. Beats trigger on EVIDENCE, never on time played and never on exposure. A beat
   whose trigger is "you walked here" pays lore, not XP. A beat that pays XP is
   gated on a clear, a retest, a boss or a mastery number.
2. No reward supplies an answer. Mentor techniques spend the same economic
   vocabulary as items.EFFECT_LABELS — focus, probes, loot, XP — and every one of
   them is sealed in Interview Mode, along with the mentors themselves.
3. The rival motivates and never shames. Their lead is computed to shrink, they
   concede when the player passes them, and they are only ever ahead on one
   skill at a time.

Wiring is documented at the bottom of the file, in WIRING.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import curriculum
from . import world

# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------
# A trigger is a tiny declarative predicate. It has to be data rather than a
# lambda because the quest log renders it as a progress bar — "PYTHON mastery
# 18/25" — and the engagement problem this module exists to fix is that every
# unlock in the game was previously an invisible threshold that fired without
# warning.


@dataclass(frozen=True)
class Trigger:
    kind: str
    key: str = ""
    value: float = 0.0
    text: str = ""
    parts: tuple = ()


class When:
    """Constructors for triggers. Namespaced so the content tables read as prose."""

    @staticmethod
    def always() -> Trigger:
        return Trigger("always")

    @staticmethod
    def region(region_id: str) -> Trigger:
        return Trigger("region_entered", region_id)

    @staticmethod
    def boss(boss_id: str) -> Trigger:
        return Trigger("boss_cleared", boss_id)

    @staticmethod
    def bosses(count: int) -> Trigger:
        return Trigger("bosses_cleared", value=count)

    @staticmethod
    def mastery(skill: str, value: float) -> Trigger:
        return Trigger("skill_mastery", skill, value)

    @staticmethod
    def unaided(skill: str, count: int) -> Trigger:
        return Trigger("skill_unaided", skill, count)

    @staticmethod
    def clears(skill: str, count: int) -> Trigger:
        return Trigger("skill_clears", skill, count)

    @staticmethod
    def retention(skill: str, value: float) -> Trigger:
        return Trigger("skill_retention", skill, value)

    @staticmethod
    def speed(skill: str, value: float) -> Trigger:
        return Trigger("skill_speed", skill, value)

    @staticmethod
    def stage(skill: str, stage_name: str) -> Trigger:
        return Trigger("skill_stage", skill, text=stage_name)

    @staticmethod
    def solved(count: int) -> Trigger:
        return Trigger("solved", value=count)

    @staticmethod
    def stat(key: str, count: int) -> Trigger:
        return Trigger("stat", key, count)

    @staticmethod
    def level(value: int) -> Trigger:
        return Trigger("level", value=value)

    @staticmethod
    def chapter(chapter_id: str) -> Trigger:
        return Trigger("chapter", chapter_id)

    @staticmethod
    def gates(count: int) -> Trigger:
        return Trigger("gates", value=count)

    @staticmethod
    def gates_percent(percent: float) -> Trigger:
        return Trigger("gates_percent", value=percent)

    @staticmethod
    def event(name: str) -> Trigger:
        return Trigger("event", name)

    @staticmethod
    def flag(beat_id: str) -> Trigger:
        return Trigger("flag", beat_id)

    @staticmethod
    def all_of(*parts: Trigger) -> Trigger:
        return Trigger("all", parts=tuple(parts))

    @staticmethod
    def any_of(*parts: Trigger) -> Trigger:
        return Trigger("any", parts=tuple(parts))


# Transient things the engine reports about the attempt it just graded. A beat
# keyed on one of these fires exactly once, in the result payload of the
# submission that caused it — which is the only moment it reads as a consequence.
EVENTS = (
    "game_started", "region_entered", "mentor_met", "encounter_started",
    "encounter_cleared", "first_unaided_clear", "first_s_rank",
    "first_medium_unaided", "first_boss_cleared", "retest_survived_7d",
    "armor_repaired", "item_equipped", "loot_taken", "shrine_cleared",
    "level_gained", "diagnostic_started", "diagnostic_done", "gates_half",
    "chapter_graduated", "probe_correct", "combo_five", "comeback_clear",
    "perf_recovered", "session_ended",
)

_STAGE_ORDER = {name: i for i, name in enumerate(
    ["UNKNOWN", "EXPOSED", "UNDERSTOOD", "ASSISTED", "INDEPENDENT",
     "RETAINED", "FAST", "MASTERED"])}

_EMPTY_SKILL = {"mastery": 0.0, "clears": 0, "unaided_clears": 0, "attempts": 0,
                "retention": 0.0, "speed": 0.0, "stage": "UNKNOWN"}


def _skill(ctx: dict, name: str) -> dict:
    return ctx.get("skills", {}).get(name, _EMPTY_SKILL)


def trigger_progress(trigger: Trigger, ctx: dict) -> dict:
    """Current / required / met, phrased for the quest log.

    Composites report the least-complete part, because that is the thing the
    player should go and do next.
    """
    kind = trigger.kind
    if kind == "always":
        return {"label": "", "current": 1, "required": 1, "met": True}
    if kind == "region_entered":
        region = world.REGION_BY_ID.get(trigger.key, {})
        met = trigger.key in ctx.get("regions_entered", ())
        return {"label": f"Reach {region.get('name', trigger.key)}",
                "current": int(met), "required": 1, "met": met}
    if kind == "boss_cleared":
        boss = world.BOSS_BY_ID.get(trigger.key, {})
        met = trigger.key in ctx.get("cleared_bosses", ())
        return {"label": f"Defeat {boss.get('name', trigger.key)}",
                "current": int(met), "required": 1, "met": met}
    if kind == "bosses_cleared":
        have = len(ctx.get("cleared_bosses", ()))
        return {"label": "Bosses defeated", "current": have,
                "required": int(trigger.value), "met": have >= trigger.value}
    if kind in ("skill_mastery", "skill_retention", "skill_speed"):
        field_name = kind.split("_", 1)[1]
        have = round(_skill(ctx, trigger.key)[field_name])
        return {"label": f"{_pretty(trigger.key)} {field_name}",
                "current": have, "required": int(trigger.value),
                "met": have >= trigger.value}
    if kind == "skill_unaided":
        have = _skill(ctx, trigger.key)["unaided_clears"]
        return {"label": f"{_pretty(trigger.key)} unaided clears", "current": have,
                "required": int(trigger.value), "met": have >= trigger.value}
    if kind == "skill_clears":
        have = _skill(ctx, trigger.key)["clears"]
        return {"label": f"{_pretty(trigger.key)} clears", "current": have,
                "required": int(trigger.value), "met": have >= trigger.value}
    if kind == "skill_stage":
        have = _STAGE_ORDER.get(_skill(ctx, trigger.key)["stage"], 0)
        want = _STAGE_ORDER.get(trigger.text, 0)
        return {"label": f"{_pretty(trigger.key)} reaches {trigger.text}",
                "current": have, "required": want, "met": have >= want}
    if kind == "solved":
        have = ctx.get("solved_count", 0)
        return {"label": "Problems solved", "current": have,
                "required": int(trigger.value), "met": have >= trigger.value}
    if kind == "stat":
        have = ctx.get("stats", {}).get(trigger.key, 0)
        return {"label": _STAT_LABELS.get(trigger.key, trigger.key), "current": have,
                "required": int(trigger.value), "met": have >= trigger.value}
    if kind == "level":
        have = ctx.get("level", 1)
        return {"label": "Level", "current": have, "required": int(trigger.value),
                "met": have >= trigger.value}
    if kind == "chapter":
        want = _chapter_index(trigger.key)
        have = ctx.get("chapter_index", 0)
        title = curriculum.CHAPTER_BY_ID[trigger.key].title \
            if trigger.key in curriculum.CHAPTER_BY_ID else trigger.key
        return {"label": f"Reach {title}", "current": have + 1, "required": want + 1,
                "met": have >= want}
    if kind == "gates":
        have = ctx.get("gates_passed", 0)
        return {"label": "Readiness gates passed", "current": have,
                "required": int(trigger.value), "met": have >= trigger.value}
    if kind == "gates_percent":
        total = max(1, ctx.get("gates_total", 13))
        have = round(100 * ctx.get("gates_passed", 0) / total)
        return {"label": "Interview readiness", "current": have,
                "required": int(trigger.value), "met": have >= trigger.value}
    if kind == "event":
        met = trigger.key in ctx.get("events", ())
        return {"label": _EVENT_LABELS.get(trigger.key, trigger.key),
                "current": int(met), "required": 1, "met": met}
    if kind == "flag":
        met = trigger.key in ctx.get("flags", ())
        return {"label": "Earlier in the story", "current": int(met), "required": 1,
                "met": met}
    if kind == "all":
        parts = [trigger_progress(p, ctx) for p in trigger.parts]
        unmet = [p for p in parts if not p["met"]]
        if unmet:
            return {**unmet[0], "met": False}
        return {**parts[-1], "met": True} if parts else \
            {"label": "", "current": 1, "required": 1, "met": True}
    if kind == "any":
        parts = [trigger_progress(p, ctx) for p in trigger.parts]
        done = [p for p in parts if p["met"]]
        if done:
            return done[0]
        return parts[0] if parts else {"label": "", "current": 0, "required": 1,
                                       "met": False}
    return {"label": trigger.kind, "current": 0, "required": 1, "met": False}


def trigger_met(trigger: Trigger, ctx: dict) -> bool:
    if trigger.kind == "all":
        return all(trigger_met(p, ctx) for p in trigger.parts)
    if trigger.kind == "any":
        return any(trigger_met(p, ctx) for p in trigger.parts)
    return trigger_progress(trigger, ctx)["met"]


def describe_trigger(trigger: Trigger, ctx: dict) -> str:
    """One line the player can act on, with the numbers in it."""
    progress = trigger_progress(trigger, ctx)
    if not progress["label"]:
        return ""
    if progress["required"] <= 1:
        return progress["label"]
    return f"{progress['label']} {progress['current']}/{progress['required']}"


_STAT_LABELS = {
    "encounters": "Encounters fought", "armor_repairs": "Armour repairs",
    "shrines": "Shrines answered", "probes_correct": "Correct probes",
    "crits": "Weakness strikes", "items_found": "Items found",
    "secrets": "Secrets found", "sessions": "Sessions",
}

_EVENT_LABELS = {
    "first_unaided_clear": "Solve one unaided",
    "first_s_rank": "Earn an S rank",
    "first_medium_unaided": "Solve a Medium unaided",
    "first_boss_cleared": "Defeat a boss",
    "retest_survived_7d": "Clear a seven-day retest",
    "armor_repaired": "Repair a piece of armour",
    "shrine_cleared": "Answer a Memory Shrine",
    "probe_correct": "Land a probe",
    "chapter_graduated": "Graduate a chapter",
}


def _pretty(skill: str) -> str:
    return skill.replace("_", " ").title()


def _chapter_index(chapter_id: str) -> int:
    for index, chapter in enumerate(curriculum.CHAPTERS):
        if chapter.id == chapter_id:
            return index
    return 0


# ---------------------------------------------------------------------------
# Content shapes
# ---------------------------------------------------------------------------
# `reward` is a plain dict so the engine can pay it without importing anything
# from here. Recognised keys, and nothing else:
#
#   xp            int      paid exactly once, on the evidence the trigger names
#   gold          int
#   title         str      an honorific, stored beside world.title_for(level)
#   card          str      a GRIMOIRE_CARDS id — a revision card, not a hint
#   codex         str      a CODEX id — lore and reference
#   set_piece     str      a SET_PIECES id — an authored scene the client plays
#   technique     str      a TECHNIQUES id — a permanent, economic bonus
#   companion     str      a world.COMPANIONS id, when the chain IS the unlock
#   consumable    dict     {"id": key, "count": n} from items.CONSUMABLES
#   favor         dict     {"mentor": id, "amount": n}
#
# Nothing here changes what a problem says, what a test asserts, or what a hint
# reveals. That is the whole of rule 4.

REWARD_KEYS = ("xp", "gold", "title", "card", "codex", "set_piece", "technique",
               "companion", "consumable", "favor")


@dataclass(frozen=True)
class Beat:
    id: str
    act: str
    title: str
    region: str
    speaker: str
    trigger: Trigger
    lines: tuple
    reward: dict = field(default_factory=dict)
    objective: str = ""          # what the player is pointed at next


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    objective: str
    trigger: Trigger
    lines: tuple
    reward: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Chain:
    id: str
    title: str
    mentor: str
    skill: str
    region: str
    premise: str
    steps: tuple

    @property
    def reward(self) -> dict:
        return self.steps[-1].reward if self.steps else {}


@dataclass(frozen=True)
class Milestone:
    id: str
    name: str
    speaker: str
    trigger: Trigger
    line: str
    reward: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RivalMeeting:
    index: int
    place: str
    trigger: Trigger
    lines: tuple
    lead: float                  # mastery points they hold on your weakest skill
    reward: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Technique:
    id: str
    name: str
    mentor: str
    skill: str
    requires: Trigger
    effects: dict                # keys from items.EFFECT_LABELS, nothing else
    blurb: str
    line: str


@dataclass(frozen=True)
class MentorTrack:
    mentor: str
    skills: tuple
    chain: str
    technique: str
    tiers: tuple                 # (favor_threshold, rank_name, line) ascending


# ---------------------------------------------------------------------------
# The save shape and the context
# ---------------------------------------------------------------------------

STATE_KEY = "story"


def new_story_state() -> dict:
    """Everything this module needs the engine to persist. Add it to
    DEFAULT_STATE under STATE_KEY; _merge already forward-fills new keys."""
    return {
        "fired": [],             # beat / step / milestone / meeting ids, in order
        "chains": {},            # chain id -> index of the next step to satisfy
        "titles": [],            # honorifics earned, most recent last
        "cards": [],             # grimoire card ids
        "codex": [],             # codex entry ids
        "set_pieces": [],        # scenes already played
        "techniques": [],        # mentor signature techniques owned
        "favor": {},             # mentor id -> favour points
        "rival": {"meetings": 0, "conceded": False, "best_gap": 0.0},
        "session": {"step": 0, "complete": False},
    }


def build_context(state: dict, skills=None, *, readiness: dict | None = None,
                  events=(), regions_entered=None) -> dict:
    """Fold the engine's raw state into the flat shape triggers read.

    `skills` accepts either the typed SkillState mapping (Game.skills) or the raw
    dict in state["skills"]; the engine has both to hand and neither is worth
    converting at the call site.
    """
    raw_skills = skills if skills is not None else state.get("skills", {})
    folded = {}
    for name, value in raw_skills.items():
        source = value if isinstance(value, dict) else value.__dict__
        folded[name] = {
            "mastery": float(source.get("mastery", 0.0)),
            "clears": int(source.get("clears", 0)),
            "unaided_clears": int(source.get("unaided_clears", 0)),
            "attempts": int(source.get("attempts", 0)),
            "retention": float(source.get("retention", 0.0)),
            "speed": float(source.get("speed", 0.0)),
            "stage": source.get("stage", "UNKNOWN"),
        }

    story = state.get(STATE_KEY) or new_story_state()
    player = state.get("player", {})
    entered = regions_entered if regions_entered is not None \
        else story.get("regions_entered") or [player.get("region", "python_village")]

    class _Shim:
        """curriculum.frontier wants objects with a .mastery and .clears."""

        def __init__(self, data):
            self.mastery = data["mastery"]
            self.clears = data["clears"]
            self.unaided_clears = data["unaided_clears"]

    shimmed = {k: _Shim(v) for k, v in folded.items()}

    return {
        "skills": folded,
        "region": player.get("region", "python_village"),
        "regions_entered": set(entered),
        "cleared_bosses": set(state.get("cleared_bosses", [])),
        "solved_count": len(state.get("solved_ids", [])),
        "level": int(player.get("level", 1)),
        "stats": dict(state.get("stats", {})),
        "gates_passed": (readiness or {}).get("gates_passed", 0),
        "gates_total": (readiness or {}).get("gates_total", 13),
        "chapter_index": curriculum.frontier(shimmed),
        "flags": set(story.get("fired", [])),
        "events": set(events),
        "favor": dict(story.get("favor", {})),
        "techniques": list(story.get("techniques", [])),
        "chains": dict(story.get("chains", {})),
        "rival": dict(story.get("rival", {})),
        "weakest": _weakest(folded),
    }


def _weakest(folded: dict, limit: int = 3) -> list:
    """Weakest skills WITH evidence behind them. A skill nobody has attempted is
    not a weakness, it is an absence, and pointing a rival at it would be a lie."""
    seen = [(data["mastery"], name) for name, data in folded.items()
            if data["attempts"] > 0]
    if not seen:
        return ["PYTHON"]
    seen.sort()
    return [name for _, name in seen[:limit]]


# ---------------------------------------------------------------------------
# The main quest
# ---------------------------------------------------------------------------
# One named beat per region, bracketed by a prologue and an ending. Arrival beats
# pay lore, because arriving is not evidence of anything. Beats that pay XP are
# gated on clears, bosses or mastery.

ACT_I = "I. The Language"
ACT_II = "II. The Vaults"
ACT_III = "III. The Scan"
ACT_IV = "IV. The Depths"
ACT_V = "V. The Measure"
ACT_VI = "VI. The Castle"

MAIN_QUEST = [
    Beat(
        id="main_00_the_shattering", act=ACT_I, title="The Shattering",
        region="python_village", speaker="narrator",
        trigger=When.always(),
        lines=(
            "The Source was a language. Everything this realm could compute, it "
            "computed by being spoken to correctly.",
            "The Null King did not destroy it. He un-named it. The words scattered "
            "into sixteen regions and became patterns nobody can pronounce any more.",
            "You held the walls of this place for years without once learning to "
            "speak it. That worked until the day it stopped working.",
            "BYTE is in the square. Start there.",
        ),
        reward={"codex": "codex_source"},
        objective="Find BYTE in Python Village.",
    ),
    Beat(
        id="main_01_half_spoken", act=ACT_I, title="The Half-Spoken Village",
        region="python_village", speaker="byte",
        trigger=When.all_of(When.region("python_village"), When.clears("PYTHON", 3)),
        lines=(
            "Three drills. Your syntax is slow, not wrong. That is the better kind "
            "of broken and the slower kind to fix.",
            "Slow syntax costs you the first four minutes of every interview. Those "
            "are the only four minutes where looking uncertain is still free.",
            "We are not here to teach you what a dictionary is. You know. We are "
            "here to make typing one cost you nothing.",
        ),
        reward={"xp": 40, "card": "card_reflex", "codex": "codex_village"},
        objective="Bring PYTHON to mastery 20. Watch what the village does about it.",
    ),
    Beat(
        id="main_02_the_village_stands", act=ACT_I, title="The Village Stands",
        region="python_village", speaker="byte",
        trigger=When.all_of(When.region("python_village"), When.mastery("PYTHON", 45)),
        lines=(
            "Look at the east row. Roof, door, glass in the window.",
            "Nobody rebuilt that. The buildings hold their shape while somebody "
            "nearby can still say what they are. You are the somebody.",
            "It is not a metaphor and I resent the implication. It is load-bearing "
            "fluency.",
        ),
        reward={"xp": 90, "title": "Fluent", "set_piece": "scene_village_restored"},
        objective="Take the road east into the Fields of Syntax.",
    ),
    Beat(
        id="main_03_weeds", act=ACT_I, title="Weeds in the Fields",
        region="fields_of_syntax", speaker="byte",
        trigger=When.all_of(When.region("fields_of_syntax"),
                            When.unaided("PYTHON", 3)),
        lines=(
            "Half-formed statements grow out here. They compile in the way weeds "
            "are technically plants.",
            "Three unaided now. You did not ask me for anything on those, which is "
            "the number I was actually counting.",
            "South of here the Armorer keeps the broken programs. You will like her "
            "less than you expect and learn more than you want.",
        ),
        reward={"xp": 70, "card": "card_read_the_error"},
        objective="Go south to the Debugging Dungeon and repair something.",
    ),
    Beat(
        id="main_04_the_bargain", act=ACT_I, title="The Armorer's Bargain",
        region="debugging_dungeon", speaker="armorer",
        trigger=When.all_of(When.region("debugging_dungeon"),
                            When.stat("armor_repairs", 1)),
        lines=(
            "Every crack in every plate on these walls is a defect in some "
            "program. Mine included. I am not precious about it.",
            "Here is the bargain. Your armour only repairs by debugging. Nothing "
            "else mends it — not levels, not loot, not sleep.",
            "You are already good at reading other people's code under pressure. "
            "That is the rarest half of this. The other half is doing it to your own.",
        ),
        reward={"xp": 80, "codex": "codex_armour", "card": "card_trace_by_hand"},
        objective="Climb to Hashmap Highlands. The Archivist is expecting a sceptic.",
    ),
    Beat(
        id="main_05_one_key", act=ACT_II, title="One Key, One Vault",
        region="hashmap_highlands", speaker="archivist",
        trigger=When.all_of(When.region("hashmap_highlands"),
                            When.clears("HASH_MAP", 3)),
        lines=(
            "Every vault on this plateau opens to exactly one rune and no other. "
            "Nobody searches here. Searching is what you do when you have lost the key.",
            "The question 'have I seen this before' is the most common question in "
            "the entire craft. It should cost you one line and no thought.",
            "Learn it here and you will recognise it everywhere else, wearing a hat.",
        ),
        reward={"xp": 100, "card": "card_seen_before", "codex": "codex_vaults"},
        objective="The Hash Titan is at the plateau's edge. It fights by waiting.",
    ),
    Beat(
        id="main_06_the_titan_waits", act=ACT_II, title="The Titan Stops Waiting",
        region="hashmap_highlands", speaker="archivist",
        trigger=When.boss("hash_titan"),
        lines=(
            "It never attacked you. It never had to. It simply outlasted everybody "
            "who compared every scroll against every other scroll.",
            "You did not do that. You made one pass and kept a record.",
            "That is the trade the whole craft turns on: a little memory, bought "
            "once, to avoid doing the same work forever.",
        ),
        reward={"xp": 180, "set_piece": "scene_titan_falls", "card": "card_trade_memory",
                "favor": {"mentor": "archivist", "amount": 6}},
        objective="Three roads open from the plateau. Take any of them.",
    ),
    Beat(
        id="main_07_the_grove", act=ACT_II, title="The Grove That Rearranges",
        region="stringwood_labyrinth", speaker="scribe",
        trigger=When.all_of(When.region("stringwood_labyrinth"),
                            When.clears("STRING", 3)),
        lines=(
            "The trees reorder their letters when you are not looking. Several "
            "paths spell the same word and therefore arrive at the same clearing.",
            "Say what makes two of them the same before you write anything. Sorted "
            "letters. A count of letters. Either is a key.",
            "If you cannot say it, you do not have an approach yet. You have a mood.",
        ),
        reward={"xp": 110, "card": "card_canonical_form"},
        objective="The Array Caverns run beneath the plateau. Everything there is numbered.",
    ),
    Beat(
        id="main_08_from_zero", act=ACT_II, title="Counting From Zero",
        region="array_caverns", speaker="archivist",
        trigger=When.all_of(When.region("array_caverns"), When.clears("ARRAY", 3)),
        lines=(
            "Alcoves numbered from zero. The last one is always one short of the "
            "count. Miners have died of that sentence.",
            "Half of everything ahead of you is an index and a boundary. The other "
            "half is choosing which structure to index into.",
            "The Hydra lives down here. It grows a head for every duplicate you "
            "fail to skip, which is a fair description of an off-by-one error.",
        ),
        reward={"xp": 110, "codex": "codex_index", "card": "card_boundaries"},
        objective="Two routes now: the Marsh, or the Pass. Both teach one pass.",
    ),
    Beat(
        id="main_09_the_frame", act=ACT_III, title="The Frame That Never Restarts",
        region="sliding_window_marsh", speaker="window_mage",
        trigger=When.all_of(When.region("sliding_window_marsh"),
                            When.clears("SLIDING_WINDOW", 2)),
        lines=(
            "Watch the frame. It widens to the right until the ward breaks, then "
            "it gives ground on the left until the ward holds again.",
            "It never goes back to the start. Restarting the scan is how the Wraith "
            "eats — it does not need to beat you, it needs you to begin again.",
            "Two indices. One pass. Everything expensive in this marsh is a person "
            "who forgot they were allowed to keep what they already counted.",
        ),
        reward={"xp": 130, "card": "card_never_restart", "codex": "codex_window"},
        objective="Hold the ward. The Window Wraith feeds on restarts.",
    ),
    Beat(
        id="main_10_two_lanterns", act=ACT_III, title="Two Lanterns",
        region="twin_pointer_pass", speaker="ranger",
        trigger=When.all_of(When.region("twin_pointer_pass"),
                            When.clears("TWO_POINTER", 2)),
        lines=(
            "Two lanterns, one at each end of the bridge. They walk toward each "
            "other. Neither ever turns back.",
            "The whole method is knowing which one to move. Sum too small, move the "
            "left. Too large, move the right. The sorted order is what earns you that.",
            "Sort first if you must. It costs n log n and it buys you the entire "
            "rest of the problem, which is a bargain nobody regrets.",
        ),
        reward={"xp": 130, "card": "card_which_one_moves"},
        objective="The mines below run last-in-first-out. Bring patience.",
    ),
    Beat(
        id="main_11_last_in", act=ACT_III, title="Last In, First Out",
        region="stack_queue_mines", speaker="archivist",
        trigger=When.all_of(When.region("stack_queue_mines"), When.clears("STACK", 2)),
        lines=(
            "Ore carts unload from the top. The lift takes the oldest waiting miner. "
            "Two rules, two structures, and the mine has never once confused them.",
            "Anything nested is a stack. Anything fair is a queue. Undo is a stack. "
            "Shortest path is a queue.",
            "You will meet both again in the Wastes wearing different names.",
        ),
        reward={"xp": 130, "codex": "codex_order", "card": "card_nested_is_a_stack"},
        objective="The Citadel turns ninety degrees when the Golem stirs.",
    ),
    Beat(
        id="main_12_the_floor_turns", act=ACT_III, title="The Floor Turns",
        region="matrix_citadel", speaker="cartographer",
        trigger=When.all_of(When.region("matrix_citadel"), When.clears("MATRIX", 2)),
        lines=(
            "The whole floor plan rotates. Transpose, then reverse each row. The "
            "Golem's entire threat is that you will allocate a second citadel to "
            "avoid thinking about it.",
            "A grid is a list of lists until the moment you need a neighbour, and "
            "then it is a graph with very good manners.",
            "Remember that. It is the only bridge between here and the Wastes.",
        ),
        reward={"xp": 140, "card": "card_grid_is_a_graph"},
        objective="North of the Labyrinth, the forest contains itself.",
    ),
    Beat(
        id="main_13_forest_inside", act=ACT_IV, title="The Forest Inside the Forest",
        region="recursive_forest", speaker="druid",
        trigger=When.all_of(When.region("recursive_forest"),
                            When.clears("RECURSION", 2)),
        lines=(
            "Each clearing holds a smaller copy of this forest. You walk into it, "
            "and you come back carrying whatever the smaller one found.",
            "Say the base case out loud before you take a step. Then say what you "
            "do with the answer from below. There is no third part.",
            "People do not fear recursion. They fear not having written the base "
            "case, which is a completely reasonable thing to fear.",
        ),
        reward={"xp": 150, "card": "card_base_case_first", "codex": "codex_recursion"},
        objective="The Canopy above forks left and right and never rejoins.",
    ),
    Beat(
        id="main_14_every_branch", act=ACT_IV, title="Every Branch Splits Twice",
        region="binary_tree_canopy", speaker="druid",
        trigger=When.all_of(When.region("binary_tree_canopy"), When.clears("TREE", 2)),
        lines=(
            "A tree is recursion that someone drew. Nothing about it is new to you "
            "now except the attribute names.",
            "Left and right. A node with one child is not a leaf, whatever the "
            "Ent tells you while it is trying to eat you.",
            "The Dragon will invite you to compare it only to its children. Decline. "
            "Carry the bounds down.",
        ),
        reward={"xp": 150, "card": "card_carry_bounds"},
        objective="East, the Wastes. Every ruin connects to several others.",
    ),
    Beat(
        id="main_15_rings_of_light", act=ACT_IV, title="Rings of Light",
        region="graph_wastes", speaker="cartographer",
        trigger=When.all_of(When.region("graph_wastes"), When.clears("BFS", 2)),
        lines=(
            "Light spreads from a ruin in rings. The first ring to touch your "
            "destination is the shortest road, and you get that for free by the "
            "order you visit in.",
            "Mark a ruin the moment you put it in the queue. Not when you take it "
            "out. The Necromancer's whole army is nodes that were queued twice.",
            "Depth-first is for every road. Breadth-first is for the short one. "
            "They are not rivals, they answer different questions.",
        ),
        reward={"xp": 160, "codex": "codex_search", "card": "card_mark_on_enqueue"},
        objective="The Ruins keep their lights on for every tile you have paid for.",
    ),
    Beat(
        id="main_16_already_paid", act=ACT_IV, title="The Tiles You Already Paid For",
        region="dp_ruins", speaker="oracle",
        trigger=When.all_of(When.region("dp_ruins"), When.clears("DP", 2)),
        lines=(
            "Every tile you have solved stays lit. Walk it again and it costs you "
            "nothing, because you already paid.",
            "That is the whole of it. Write the recursion honestly, notice that it "
            "asks the same question repeatedly, and then refuse to answer twice.",
            "Exponential becomes linear and no cleverness was required. Only "
            "bookkeeping, which is the good news and also why nobody teaches it well.",
        ),
        reward={"xp": 170, "card": "card_refuse_to_answer_twice"},
        objective="The Tower charges more for every floor. Go and find out how much.",
    ),
    Beat(
        id="main_17_the_climb", act=ACT_V, title="The Cost of the Climb",
        region="complexity_tower", speaker="oracle",
        trigger=When.all_of(When.region("complexity_tower"), When.clears("BIG_O", 3)),
        lines=(
            "Each floor holds twice the enemies of the one below. You cannot brute "
            "force the top and the tower is not being subtle about it.",
            "Count the work you do per element. Multiply by the elements. Sequential "
            "work adds, nested work multiplies. That is the entire art and it fits "
            "on a coin.",
            "Say the cost before anyone asks. Candidates who volunteer it are "
            "assumed to have chosen it on purpose.",
        ),
        reward={"xp": 180, "codex": "codex_cost", "card": "card_count_per_element"},
        objective="The Coliseum has a sand floor, a clock, and no hints.",
    ),
    Beat(
        id="main_18_sand_and_clock", act=ACT_V, title="Sand, Clock, No Hints",
        region="coding_coliseum", speaker="chronomancer",
        trigger=When.all_of(When.region("coding_coliseum"), When.speed("SPEED", 40)),
        lines=(
            "Nothing new is taught here. Everything here you already know, and the "
            "only question is whether you know it faster than you can doubt yourself.",
            "Hesitation is not caution. Caution has a reason and can state it. "
            "Hesitation is just the gap between recognising a problem and starting it.",
            "We are going to make that gap small. That is the entire service.",
        ),
        reward={"xp": 190, "card": "card_start_before_certain",
                "favor": {"mentor": "chronomancer", "amount": 6}},
        objective="The castle opens on evidence, not on courage. Check what it wants.",
    ),
    Beat(
        id="main_19_nothing_labelled", act=ACT_VI, title="Nothing Is Labelled",
        region="null_kings_castle", speaker="interviewer",
        trigger=When.region("null_kings_castle"),
        lines=(
            "No signposts. No region names. Nothing in these rooms will tell you "
            "which pattern it wants.",
            "That is not a cruelty. It is the only honest test, because no one out "
            "there will label them either.",
            "Walk me through your approach before you write anything. I am not "
            "asking to be difficult. I am asking because it is the part of the job.",
        ),
        reward={"codex": "codex_castle", "card": "card_say_it_first"},
        objective="Recognise. Explain. Implement. Survive the trials. Name the cost.",
    ),
    Beat(
        id="main_20_what_it_was_for", act=ACT_VI, title="What the Source Was For",
        region="null_kings_castle", speaker="narrator",
        trigger=When.boss("the_interviewer"),
        lines=(
            "The Null King is not killed. He is named, correctly, out loud, by "
            "somebody who can also say why.",
            "The Source was never a weapon. It was a way of describing what should "
            "happen precisely enough that it then happened.",
            "You could always see what needed to happen. Now you can say it fast "
            "enough to matter. That was the entire gap and it is closed.",
        ),
        reward={"xp": 900, "title": "The Architect Who Spoke",
                "set_piece": "scene_source_restored", "codex": "codex_ending"},
        objective="Interview Mode is the same castle with the lights on. Go and be measured.",
    ),
]

MAIN_BY_ID = {b.id: b for b in MAIN_QUEST}


# ---------------------------------------------------------------------------
# Side chains
# ---------------------------------------------------------------------------
# One per mentor, three escalating steps, a real reward at the end. Every step
# is gated on graded evidence in that mentor's own skill, so a chain cannot be
# walked through — only worked through.

SIDE_CHAINS = [
    Chain(
        id="byte_metronome", title="The Metronome", mentor="byte", skill="PYTHON",
        region="python_village",
        premise="BYTE is an automaton that measures things. It has decided to "
                "measure how long you take to start typing.",
        steps=(
            Step(id="byte_metronome_1", title="Warm Hands",
                 objective="Clear five Python drills.",
                 trigger=When.clears("PYTHON", 5),
                 lines=("Five. I have your time-to-first-keystroke on all of them.",
                        "It is falling. Not because you know more — you knew all of "
                        "this — but because you are spending less of it deciding "
                        "whether you know it."),
                 reward={"xp": 35, "favor": {"mentor": "byte", "amount": 3}}),
            Step(id="byte_metronome_2", title="Without Asking",
                 objective="Clear six Python drills without casting a single spell.",
                 trigger=When.unaided("PYTHON", 6),
                 lines=("Six unaided. You asked me for nothing on any of them.",
                        "I want to be clear that I would have answered. The point "
                        "is not that help is shameful. The point is that you did "
                        "not need it and now we both know."),
                 reward={"xp": 75, "card": "card_reflex",
                         "favor": {"mentor": "byte", "amount": 5}}),
            Step(id="byte_metronome_3", title="The Metronome",
                 objective="Reach PYTHON mastery 55 and the INDEPENDENT stage.",
                 trigger=When.all_of(When.mastery("PYTHON", 55),
                                     When.stage("PYTHON", "INDEPENDENT")),
                 lines=("Take this. It keeps time, badly, and it is mine.",
                        "When you sit down in front of a blank editor it will tick "
                        "once. That is all it does. It will not tell you anything "
                        "and there is nothing in it to read.",
                        "You will start anyway, which was always the problem."),
                 reward={"xp": 160, "title": "Quick Hands",
                         "technique": "tech_metronome",
                         "favor": {"mentor": "byte", "amount": 10}}),
        ),
    ),
    Chain(
        id="archivist_index", title="The Index of Everything", mentor="archivist",
        skill="HASH_MAP", region="hashmap_highlands",
        premise="The Archivist is compiling an index of every question that turns "
                "out to be 'have I seen this before'. It is longer than expected.",
        steps=(
            Step(id="archivist_index_1", title="Four Vaults",
                 objective="Clear four hash-map encounters.",
                 trigger=When.clears("HASH_MAP", 4),
                 lines=("Four. Note what they had in common: none of them said the "
                        "word 'dictionary' anywhere in the statement.",
                        "That is the skill. Not using a dict. Noticing one is owed."),
                 reward={"xp": 45, "favor": {"mentor": "archivist", "amount": 3}}),
            Step(id="archivist_index_2", title="Unaided Keys",
                 objective="Clear five hash-map encounters unaided.",
                 trigger=When.unaided("HASH_MAP", 5),
                 lines=("Five, no spells. Your first instinct on a membership "
                        "question is now the right one.",
                        "Instinct is a word people use when they cannot remember "
                        "learning something. You learned it eleven days ago. I have "
                        "the record."),
                 reward={"xp": 95, "card": "card_seen_before",
                         "favor": {"mentor": "archivist", "amount": 5}}),
            Step(id="archivist_index_3", title="The Index Closes",
                 objective="Defeat the Hash Titan and reach HASH_MAP mastery 60.",
                 trigger=When.all_of(When.boss("hash_titan"),
                                     When.mastery("HASH_MAP", 60)),
                 lines=("The index is yours. It contains no answers. It contains "
                        "the shape of the question, which is worth more and sells "
                        "for less.",
                        "Anything asking about pairs, counts, duplicates, groups or "
                        "'first repeated' is one structure wearing four coats."),
                 reward={"xp": 200, "technique": "tech_index",
                         "card": "card_trade_memory",
                         "favor": {"mentor": "archivist", "amount": 10}}),
        ),
    ),
    Chain(
        id="window_ward", title="The Ward That Holds", mentor="window_mage",
        skill="SLIDING_WINDOW", region="sliding_window_marsh",
        premise="The Window Mage wants the ward held across the whole marsh in one "
                "unbroken pass. Nobody has managed it while she was watching.",
        steps=(
            Step(id="window_ward_1", title="Expand Right",
                 objective="Clear three sliding-window encounters.",
                 trigger=When.clears("SLIDING_WINDOW", 3),
                 lines=("Good. You widened right and you did not panic when the "
                        "ward broke.",
                        "Breaking is not failure here. Breaking is the signal that "
                        "tells the left edge to move."),
                 reward={"xp": 55, "favor": {"mentor": "window_mage", "amount": 3}}),
            Step(id="window_ward_2", title="Shrink Left",
                 objective="Clear four sliding-window encounters unaided.",
                 trigger=When.unaided("SLIDING_WINDOW", 4),
                 lines=("Four unaided. And you deleted the key when its count hit "
                        "zero, which is the line everyone forgets.",
                        "Leave it in and len() lies to you for the rest of the "
                        "problem. A quiet lie, from a function you trust."),
                 reward={"xp": 110, "card": "card_never_restart",
                         "favor": {"mentor": "window_mage", "amount": 5}}),
            Step(id="window_ward_3", title="One Unbroken Pass",
                 objective="Defeat the Window Wraith.",
                 trigger=When.boss("window_wraith"),
                 lines=("It starved. That is what happened. It eats restarts and "
                        "you did not give it one.",
                        "The staff is yours. It does nothing to the marsh. It makes "
                        "the ward visible, so you stop guessing where the edge is."),
                 reward={"xp": 220, "technique": "tech_ward",
                         "set_piece": "scene_marsh_clear",
                         "favor": {"mentor": "window_mage", "amount": 10}}),
        ),
    ),
    Chain(
        id="ranger_bridge", title="Both Ends of the Bridge", mentor="ranger",
        skill="TWO_POINTER", region="twin_pointer_pass",
        premise="The Ranger walks the pass twice a day, once from each end, and "
                "has views about people who start in the middle.",
        steps=(
            Step(id="ranger_bridge_1", title="Two Lanterns Lit",
                 objective="Clear three two-pointer encounters.",
                 trigger=When.clears("TWO_POINTER", 3),
                 lines=("Both ends. Neither turns back. You are doing it.",
                        "The sort you paid for at the start is the thing that makes "
                        "the rest legal. Never apologise for it."),
                 reward={"xp": 55, "favor": {"mentor": "ranger", "amount": 3}}),
            Step(id="ranger_bridge_2", title="Which One Moves",
                 objective="Clear four two-pointer encounters unaided.",
                 trigger=When.unaided("TWO_POINTER", 4),
                 lines=("You are asking the right question now. Not 'what do I do', "
                        "but 'which one moves and why'.",
                        "Sum too small, the left is the problem. Too large, the "
                        "right. Container of water, move the shorter wall. Always "
                        "the shorter wall."),
                 reward={"xp": 110, "card": "card_which_one_moves",
                         "favor": {"mentor": "ranger", "amount": 5}}),
            Step(id="ranger_bridge_3", title="The Behemoth Crosses",
                 objective="Defeat the Twin Pointer Behemoth.",
                 trigger=When.boss("twin_behemoth"),
                 lines=("It spent the whole fight inviting you to move the taller "
                        "wall and lose the width for nothing.",
                        "You declined every time. Take the sabers. They are a pair "
                        "and they are meant to be."),
                 reward={"xp": 220, "title": "Converger", "technique": "tech_converge",
                         "favor": {"mentor": "ranger", "amount": 10}}),
        ),
    ),
    Chain(
        id="druid_smaller_call", title="Trust the Smaller Call", mentor="druid",
        skill="RECURSION", region="recursive_forest",
        premise="The Druid will not explain recursion. The Druid will walk you into "
                "a clearing and wait for you to come back carrying something.",
        steps=(
            Step(id="druid_smaller_call_1", title="The Base Case",
                 objective="Clear three recursive encounters.",
                 trigger=When.clears("RECURSION", 3),
                 lines=("You wrote the base case first on the last two. I noticed "
                        "because the forest stopped moving.",
                        "That is the correct order and almost nobody arrives at it "
                        "by preference. They arrive at it by stack overflow."),
                 reward={"xp": 60, "favor": {"mentor": "druid", "amount": 3}}),
            Step(id="druid_smaller_call_2", title="Into the Canopy",
                 objective="Clear three tree encounters unaided.",
                 trigger=When.unaided("TREE", 3),
                 lines=("A tree is only recursion someone drew. You have stopped "
                        "treating them as separate subjects.",
                        "Left, right, base case, and what you do with what comes "
                        "back. Four things. It was always four things."),
                 reward={"xp": 120, "card": "card_base_case_first",
                         "favor": {"mentor": "druid", "amount": 5}}),
            Step(id="druid_smaller_call_3", title="What the Inner Copy Found",
                 objective="Defeat the Serialization Lich.",
                 trigger=When.boss("serialization_lich"),
                 lines=("Write the tree down. Read it back. Exactly. It is the "
                        "cruellest test of whether you actually understood the "
                        "shape, and you passed it.",
                        "ROOT has been following you since the second clearing. He "
                        "is not much of a talker. Neither are you."),
                 reward={"xp": 240, "companion": "root", "technique": "tech_smaller_call",
                         "favor": {"mentor": "druid", "amount": 10}}),
        ),
    ),
    Chain(
        id="cartographer_roads", title="Every Road, and the Short One",
        mentor="cartographer", skill="BFS", region="graph_wastes",
        premise="The Cartographer is redrawing the Wastes and needs two different "
                "surveys of the same ruins. They will not accept one survey twice.",
        steps=(
            Step(id="cartographer_roads_1", title="Rings",
                 objective="Clear three BFS encounters.",
                 trigger=When.clears("BFS", 3),
                 lines=("Rings of light. The first ring to touch the destination is "
                        "the shortest road and you never had to compare anything.",
                        "The order of visiting is the proof. That is rare and worth "
                        "sitting with."),
                 reward={"xp": 65, "favor": {"mentor": "cartographer", "amount": 3}}),
            Step(id="cartographer_roads_2", title="Every Road",
                 objective="Clear three DFS encounters.",
                 trigger=When.clears("DFS", 3),
                 lines=("And now the other survey. One committed path, all the way "
                        "down, then back up and take the next.",
                        "They are not rivals. They answer different questions and "
                        "the mistake is always using one to answer the other's."),
                 reward={"xp": 125, "card": "card_mark_on_enqueue",
                         "favor": {"mentor": "cartographer", "amount": 5}}),
            Step(id="cartographer_roads_3", title="The Survey Is Accepted",
                 objective="Defeat the Graph Necromancer.",
                 trigger=When.boss("graph_necromancer"),
                 lines=("Its army was nodes that got queued twice. You marked them "
                        "on the way in and the army never assembled.",
                        "The map is finished. I have put your name on it in small "
                        "letters, because the Wastes are still mostly rubble and I "
                        "do not want to oversell it."),
                 reward={"xp": 240, "technique": "tech_rings",
                         "card": "card_grid_is_a_graph",
                         "favor": {"mentor": "cartographer", "amount": 10}}),
        ),
    ),
    Chain(
        id="armorer_ten_cracks", title="Ten Cracks", mentor="armorer",
        skill="DEBUGGING", region="debugging_dungeon",
        premise="The Armorer has ten broken programs on the wall and no interest "
                "in fixing them herself. She has explained why. You were not "
                "listening, so she will explain again.",
        steps=(
            Step(id="armorer_ten_cracks_1", title="Three Plates",
                 objective="Repair three pieces of armour.",
                 trigger=When.stat("armor_repairs", 3),
                 lines=("Three. Did you notice none of them needed a rewrite.",
                        "A defect is a small wrong statement in a mostly right "
                        "program. Find it, and the program was always fine."),
                 reward={"xp": 60, "favor": {"mentor": "armorer", "amount": 3}}),
            Step(id="armorer_ten_cracks_2", title="Ten Cracks",
                 objective="Repair ten pieces of armour.",
                 trigger=When.stat("armor_repairs", 10),
                 lines=("Ten. You read the failing input every time before you "
                        "touched the code. That is the method. There is no other "
                        "method, there are only people skipping this one.",
                        "TRACE has decided you are worth following. She does that "
                        "at ten, never sooner. I have stopped arguing with her."),
                 reward={"xp": 140, "card": "card_trace_by_hand",
                         "favor": {"mentor": "armorer", "amount": 6}}),
            Step(id="armorer_ten_cracks_3", title="The Legendary Plate",
                 objective="Reach DEBUGGING mastery 60.",
                 trigger=When.mastery("DEBUGGING", 60),
                 lines=("The plate on the end wall has been waiting for somebody "
                        "who could fix multi-function programs. Not guess at them. "
                        "Fix them.",
                        "It is yours. It is heavy and it will not stop you making "
                        "mistakes. It will stop them mattering as much."),
                 reward={"xp": 230, "set_piece": "scene_plate_hung",
                         "technique": "tech_read_the_failure",
                         "favor": {"mentor": "armorer", "amount": 10}}),
        ),
    ),
    Chain(
        id="oracle_cost", title="Count the Work", mentor="oracle", skill="BIG_O",
        region="complexity_tower",
        premise="The Oracle does not predict anything. The Oracle multiplies. It "
                "has found this disappointing for people and has made peace with it.",
        steps=(
            Step(id="oracle_cost_1", title="Per Element",
                 objective="Clear three complexity encounters.",
                 trigger=When.clears("BIG_O", 3),
                 lines=("Work per element, times elements. You did not hedge on any "
                        "of the three, which is the part I was watching.",
                        "A wrong complexity said confidently is recoverable. A "
                        "right one said as a question is not."),
                 reward={"xp": 60, "favor": {"mentor": "oracle", "amount": 3}}),
            Step(id="oracle_cost_2", title="Adds Or Multiplies",
                 objective="Reach BIG_O mastery 45.",
                 trigger=When.mastery("BIG_O", 45),
                 lines=("Sequential work adds. Nested work multiplies. Two loops "
                        "side by side are not two loops inside each other, and "
                        "half the room gets that wrong under pressure.",
                        "You are no longer in that half."),
                 reward={"xp": 130, "card": "card_count_per_element",
                         "favor": {"mentor": "oracle", "amount": 6}}),
            Step(id="oracle_cost_3", title="Correct Is Not The Same As Fast",
                 objective="Defeat the Complexity Wyrm.",
                 trigger=When.boss("complexity_wyrm"),
                 lines=("It said correct is not the same as fast, and it was not "
                        "taunting you. It was stating its function.",
                        "You will now say the cost of your approach before anyone "
                        "asks for it. That single habit reads as seniority and it "
                        "costs one sentence."),
                 reward={"xp": 240, "technique": "tech_cost_first",
                         "favor": {"mentor": "oracle", "amount": 10}}),
        ),
    ),
    Chain(
        id="testsmith_suite", title="A Suite That Fails", mentor="testsmith",
        skill="TESTING", region="debugging_dungeon",
        premise="The Testsmith has a suite that every wrong answer passes. He keeps "
                "it on the bench as a warning and occasionally as a joke.",
        steps=(
            Step(id="testsmith_suite_1", title="First Blood On A Probe",
                 objective="Land three correct probes.",
                 trigger=When.stat("probes_correct", 3),
                 lines=("Three predictions, three correct. You said what the answer "
                        "would be before the machine did.",
                        "That is not a parlour trick. That is the thing the "
                        "interviewer is actually watching for."),
                 reward={"xp": 55, "favor": {"mentor": "testsmith", "amount": 3}}),
            Step(id="testsmith_suite_2", title="Empty, One, Duplicate, Negative",
                 objective="Land twelve correct probes.",
                 trigger=When.stat("probes_correct", 12),
                 lines=("Twelve. And you are probing the boring inputs first now — "
                        "empty, one element, all identical.",
                        "The exciting input is rarely the one that breaks it. The "
                        "exciting input is the one you designed for."),
                 reward={"xp": 125, "card": "card_boundaries",
                         "favor": {"mentor": "testsmith", "amount": 6}}),
            Step(id="testsmith_suite_3", title="The Suite That Fails",
                 objective="Reach TESTING mastery 50.",
                 trigger=When.mastery("TESTING", 50),
                 lines=("Take the bench suite. Every wrong answer passes it. That "
                        "is what it is for.",
                        "You now write the case that would embarrass you, before "
                        "somebody else finds it. Nothing else on this bench is "
                        "worth more than that."),
                 reward={"xp": 210, "title": "Case Finder",
                         "technique": "tech_edge_sense",
                         "favor": {"mentor": "testsmith", "amount": 10}}),
        ),
    ),
    Chain(
        id="scribe_aloud", title="Say It Before You Type It", mentor="scribe",
        skill="COMMUNICATION", region="stringwood_labyrinth",
        premise="The Scribe writes down what people say they are about to do, then "
                "writes down what they do. The two columns are the lesson.",
        steps=(
            Step(id="scribe_aloud_1", title="The First Sentence",
                 objective="Clear two explanation encounters.",
                 trigger=When.clears("COMMUNICATION", 2),
                 lines=("Two approaches stated before the first keystroke. Both "
                        "columns matched.",
                        "When they do not match it is almost never dishonesty. It "
                        "is that there was no approach and the sentence was hope."),
                 reward={"xp": 55, "favor": {"mentor": "scribe", "amount": 3}}),
            Step(id="scribe_aloud_2", title="Structure, Then Loop",
                 objective="Reach COMMUNICATION mastery 40.",
                 trigger=When.mastery("COMMUNICATION", 40),
                 lines=("You name the structure before the loop now. Dict for the "
                        "counts, set for the seen, list for the order.",
                        "Anyone listening can tell you have chosen rather than "
                        "reached. It is a completely different sound."),
                 reward={"xp": 120, "card": "card_say_it_first",
                         "favor": {"mentor": "scribe", "amount": 6}}),
            Step(id="scribe_aloud_3", title="The Two Columns Agree",
                 objective="Reach COMMUNICATION mastery 60.",
                 trigger=When.mastery("COMMUNICATION", 60),
                 lines=("Both columns, consistently, under time. I am closing the "
                        "ledger on you.",
                        "You were always able to reason about this out loud. What "
                        "was missing was doing it first, while it could still "
                        "change what you wrote."),
                 reward={"xp": 210, "technique": "tech_first_sentence",
                         "card": "card_canonical_form",
                         "favor": {"mentor": "scribe", "amount": 10}}),
        ),
    ),
    Chain(
        id="chronomancer_doubt", title="Faster Than Doubt", mentor="chronomancer",
        skill="SPEED", region="coding_coliseum",
        premise="The Chronomancer measures one thing: the gap between recognising "
                "a problem and beginning it. She calls it the only number that has "
                "ever mattered to her.",
        steps=(
            Step(id="chronomancer_doubt_1", title="The Gap",
                 objective="Reach SPEED 30.",
                 trigger=When.speed("SPEED", 30),
                 lines=("Your gap was forty seconds when you arrived. It is not "
                        "forty seconds now.",
                        "Nothing was added to you in that time. Something was "
                        "removed."),
                 reward={"xp": 60, "favor": {"mentor": "chronomancer", "amount": 3}}),
            Step(id="chronomancer_doubt_2", title="Under The Target",
                 objective="Reach SPEED 55.",
                 trigger=When.speed("SPEED", 55),
                 lines=("Under target on familiar patterns, repeatedly. That is not "
                        "luck any more, that is a distribution.",
                        "Speed is not typing faster. It is not rereading the "
                        "statement four times to postpone the decision."),
                 reward={"xp": 130, "card": "card_start_before_certain",
                         "favor": {"mentor": "chronomancer", "amount": 6}}),
            Step(id="chronomancer_doubt_3", title="Faster Than Doubt",
                 objective="Reach SPEED 70.",
                 trigger=When.speed("SPEED", 70),
                 lines=("You start before you are certain now, and you are right "
                        "about as often as when you waited. I have both numbers.",
                        "That was the whole complaint you walked in with. It is "
                        "no longer true about you."),
                 reward={"xp": 220, "title": "Unhesitating",
                         "technique": "tech_first_move",
                         "favor": {"mentor": "chronomancer", "amount": 10}}),
        ),
    ),
]

CHAIN_BY_ID = {c.id: c for c in SIDE_CHAINS}
STEP_BY_ID = {s.id: (c, s) for c in SIDE_CHAINS for s in c.steps}


# ---------------------------------------------------------------------------
# The rival
# ---------------------------------------------------------------------------
# KESTREL exists to be slightly ahead on one thing, and to be visibly behind on
# others. Their lead is authored to shrink at every meeting and reaches zero at
# the fifth, at which point they say so. Nothing they say is a comparison the
# player did not already have the numbers for, and nothing they say is a taunt.

RIVAL = {
    "id": "kestrel",
    "name": "KESTREL",
    "sprite": "ranger",
    "role": "another architect, further along on exactly one axis",
    "blurb": "Trains the pattern you avoid. Says so. Does not make a thing of it.",
}

RIVAL_MEETINGS = [
    RivalMeeting(
        index=1, place="python_village",
        trigger=When.solved(6), lead=12.0,
        lines=(
            "You are the one who held the eastern wall. I have read your incident "
            "reports. They are better than mine.",
            "I cannot do what you do. I can write the Python faster, which is a "
            "much smaller skill that happens to be the one they test first.",
            "I am working {skill} this week. You will be here a while, so am I.",
        ),
        reward={"codex": "codex_kestrel"},
    ),
    RivalMeeting(
        index=2, place="hashmap_highlands",
        trigger=When.all_of(When.solved(20), When.bosses(1)), lead=9.0,
        lines=(
            "You took the Titan. I took it on my fourth attempt and I am not going "
            "to pretend otherwise.",
            "I am still ahead of you on {skill}. Barely. It was twelve points when "
            "we met and it is nine now, and I can do arithmetic.",
            "Keep going at the thing you are avoiding. I only got ahead there "
            "because I ran out of things I was already good at.",
        ),
        reward={"xp": 60},
    ),
    RivalMeeting(
        index=3, place="recursive_forest",
        trigger=When.all_of(When.bosses(3), When.solved(45)), lead=6.0,
        lines=(
            "Six points on {skill}. That is the whole gap now.",
            "Here is the part nobody tells you. I am not better at this. I have "
            "simply started from a blank editor more times than you have.",
            "It is a count, not a talent. Counts can be caught.",
        ),
        reward={"xp": 90, "card": "card_start_before_certain"},
    ),
    RivalMeeting(
        index=4, place="complexity_tower",
        trigger=When.all_of(When.bosses(5), When.gates_percent(45)), lead=3.0,
        lines=(
            "Three points. I have stopped quoting the number because it has "
            "started to sound like an excuse.",
            "You explain your approach better than I do. I have watched you do it "
            "and then gone away and practised it, which I am telling you because "
            "it seemed unsporting not to.",
            "Whatever happens on {skill}, we both go into the castle. That was "
            "always the actual goal.",
        ),
        reward={"xp": 120},
    ),
    RivalMeeting(
        index=5, place="null_kings_castle",
        trigger=When.all_of(When.bosses(8), When.gates_percent(60)), lead=0.0,
        lines=(
            "Level. On {skill}, on everything else you were already ahead.",
            "I am going in after you. I want to see how it is done by somebody who "
            "can actually reason about systems, and then I want to argue with you "
            "about it afterwards.",
            "Good luck. I mean it in the flat, useful way, not the other way.",
        ),
        reward={"xp": 200, "title": "Peer", "set_piece": "scene_kestrel_concedes"},
    ),
]


def rival_status(ctx: dict) -> dict:
    """Where KESTREL stands, on one skill, right now.

    The lead comes from the last meeting held and never grows. Once the player's
    own mastery passes the rival's figure, the rival is behind and the UI says so
    — the point of the character is a gap that visibly closes.
    """
    held = int(ctx.get("rival", {}).get("meetings", 0))
    # The lead is whatever the last meeting authored. Before the first meeting it
    # is the opening gap; it only ever steps down from there.
    lead = RIVAL_MEETINGS[held - 1].lead if held else RIVAL_MEETINGS[0].lead
    weak = (ctx.get("weakest") or ["PYTHON"])[0]
    mine = _skill(ctx, weak)["mastery"]
    theirs = min(100.0, mine + lead)
    return {
        "name": RIVAL["name"],
        "meetings_held": held,
        "skill": weak,
        "skill_label": _pretty(weak),
        "player_mastery": round(mine, 1),
        "rival_mastery": round(theirs, 1),
        "gap": round(theirs - mine, 1),
        "ahead": theirs > mine,
        "conceded": theirs <= mine and held >= len(RIVAL_MEETINGS),
        "note": ("They are ahead on this one skill and behind on the rest."
                 if theirs > mine else
                 "You have caught them. They will mention it before you do."),
    }


def rival_lines(meeting: RivalMeeting, ctx: dict) -> list:
    """Meeting dialogue with the player's actual weak skill substituted in, so the
    rival is training the thing the player is avoiding rather than a fixed one."""
    weak = _pretty((ctx.get("weakest") or ["PYTHON"])[0])
    return [line.replace("{skill}", weak) for line in meeting.lines]


# ---------------------------------------------------------------------------
# Mentor relationships and signature techniques
# ---------------------------------------------------------------------------
# Familiarity is earned the same way everything else is: graded clears in that
# mentor's own skills. Unaided clears count triple, because they are the evidence
# that the mentor's lesson actually transferred.

FAVOR_TIERS = ((0, "Stranger"), (8, "Known"), (20, "Trusted"),
               (38, "Confided In"), (60, "Signature"))


def mentor_favor(mentor_id: str, ctx: dict) -> int:
    track = MENTOR_BY_ID.get(mentor_id)
    if track is None:
        return 0
    points = 0
    for name in track.skills:
        data = _skill(ctx, name)
        unaided = data["unaided_clears"]
        points += unaided * 3 + max(0, data["clears"] - unaided)
        points += int(data["mastery"] // 10)
    return points + int(ctx.get("favor", {}).get(mentor_id, 0))


def mentor_rank(favor: int) -> tuple:
    """(index, label) for a favour total."""
    best = (0, FAVOR_TIERS[0][1])
    for index, (threshold, label) in enumerate(FAVOR_TIERS):
        if favor >= threshold:
            best = (index, label)
    return best


TECHNIQUES = [
    Technique(
        id="tech_metronome", name="BYTE's Metronome", mentor="byte", skill="PYTHON",
        requires=When.all_of(When.mastery("PYTHON", 55),
                             When.stage("PYTHON", "INDEPENDENT")),
        effects={"rank_grace": 0.08},
        blurb="A tick at the start of every encounter. It tells you nothing and "
              "you begin anyway.",
        line="It does not know the answer. It is not that kind of instrument."),
    Technique(
        id="tech_index", name="The Archivist's Index", mentor="archivist",
        skill="HASH_MAP",
        requires=When.mastery("HASH_MAP", 60),
        effects={"xp_bonus": 0.08, "retest_bonus": 0.10},
        blurb="The shape of the question, indexed. Never the answer to one.",
        line="Four coats, one structure. Look for the coat."),
    Technique(
        id="tech_ward", name="The Held Ward", mentor="window_mage",
        skill="SLIDING_WINDOW",
        requires=When.mastery("SLIDING_WINDOW", 55),
        effects={"combo_shield": 1},
        blurb="The ward breaks once without the run ending. It does not fix the "
              "code and it will not tell you where the break was.",
        line="Breaking is a signal. Only starting over is a loss."),
    Technique(
        id="tech_converge", name="Converging Lanterns", mentor="ranger",
        skill="TWO_POINTER",
        requires=When.mastery("TWO_POINTER", 55),
        effects={"crit_bonus": 0.15},
        blurb="You strike edge cases harder, because you now know which end they "
              "live at.",
        line="Always the shorter wall."),
    Technique(
        id="tech_smaller_call", name="The Smaller Call", mentor="druid",
        skill="RECURSION",
        requires=When.mastery("RECURSION", 55),
        effects={"mana_max": 6},
        blurb="More focus to spend, because you stop burning it on whether the "
              "stack will unwind.",
        line="Base case. Then trust it."),
    Technique(
        id="tech_rings", name="Rings of Light", mentor="cartographer", skill="BFS",
        requires=When.mastery("BFS", 55),
        effects={"probe_charges": 1},
        blurb="One more probe per battle. You were already spreading outward in "
              "rings; now you can do it to the test cases.",
        line="Mark it when you queue it."),
    Technique(
        id="tech_read_the_failure", name="Read The Failure", mentor="armorer",
        skill="DEBUGGING",
        requires=When.mastery("DEBUGGING", 60),
        effects={"armor_repair": 0.20},
        blurb="Repairs restore more, because you stop guessing and start reading "
              "the input that broke it.",
        line="The program was always fine. One statement was not."),
    Technique(
        id="tech_cost_first", name="Cost First", mentor="oracle", skill="BIG_O",
        requires=When.mastery("BIG_O", 55),
        effects={"perf_insight": 1},
        blurb="Performance trials state their budget. Knowing the budget is not "
              "knowing the algorithm.",
        line="Say the cost before you are asked. It reads as intent."),
    Technique(
        id="tech_edge_sense", name="The Bench Suite", mentor="testsmith",
        skill="TESTING",
        requires=When.mastery("TESTING", 50),
        effects={"reveal_category": 1},
        blurb="A failed probe names the category it would have triggered. It never "
              "names the value or the fix.",
        line="Write the case that would embarrass you."),
    Technique(
        id="tech_first_sentence", name="The First Sentence", mentor="scribe",
        skill="COMMUNICATION",
        requires=When.mastery("COMMUNICATION", 60),
        effects={"hint_discount": 0.15},
        blurb="Learning spells cost less, because you have already said what you "
              "are trying to do and the question is sharper.",
        line="Structure, then loop. In that order, out loud."),
    Technique(
        id="tech_first_move", name="Faster Than Doubt", mentor="chronomancer",
        skill="SPEED",
        requires=When.speed("SPEED", 70),
        effects={"rank_grace": 0.12, "xp_bonus": 0.05},
        blurb="More clock grace, because the gap between recognising and beginning "
              "is no longer where your time goes.",
        line="Start before you are certain. You were right anyway."),
]

TECHNIQUE_BY_ID = {t.id: t for t in TECHNIQUES}


def technique_effects(story_state: dict, ctx: dict) -> dict:
    """Fold the owned techniques whose mastery requirement STILL holds.

    Deliberately re-checked rather than granted permanently: mastery decays, and a
    bonus that survives its own evidence is a bonus for exposure. Re-earn the
    number and the technique comes back, with no second ceremony.
    """
    folded: dict = {}
    for tech_id in story_state.get("techniques", []):
        tech = TECHNIQUE_BY_ID.get(tech_id)
        if tech is None or not trigger_met(tech.requires, ctx):
            continue
        for key, value in tech.effects.items():
            folded[key] = folded.get(key, 0) + value
    return folded


MENTOR_TRACKS = [
    MentorTrack(
        mentor="byte", skills=("PYTHON",), chain="byte_metronome",
        technique="tech_metronome",
        tiers=(
            (0, "Stranger",
             "You know what you want to say. Let us make the saying automatic."),
            (8, "Known",
             "Your hands have stopped hesitating over the colon. I log these things."),
            (20, "Trusted",
             "You have started typing before you finish reading. Usually that is a "
             "mistake. In your case it is the cure."),
            (38, "Confided In",
             "I was built to lint. Nobody has ever asked me what I would rather do. "
             "This, as it turns out."),
            (60, "Signature",
             "Take the metronome. It is the only thing I own."),
        )),
    MentorTrack(
        mentor="archivist", skills=("HASH_MAP", "SET", "ARRAY"),
        chain="archivist_index", technique="tech_index",
        tiers=(
            (0, "Stranger",
             "Choose the structure before you write the loop. The loop will then "
             "write itself."),
            (8, "Known",
             "You reached for a dict without being told. I have amended your file."),
            (20, "Trusted",
             "There are four structures worth arguing about and you now know which "
             "argument you are in."),
            (38, "Confided In",
             "I catalogued this realm before it broke. Most of the index survived. "
             "Most is a painful word."),
            (60, "Signature",
             "The index is yours. It holds questions, not answers, which is why it "
             "is still useful."),
        )),
    MentorTrack(
        mentor="ranger", skills=("TWO_POINTER",), chain="ranger_bridge",
        technique="tech_converge",
        tiers=(
            (0, "Stranger", "Two hands. One from each end. Neither ever turns back."),
            (8, "Known", "You sorted first and did not apologise for it. Good."),
            (20, "Trusted",
             "You have stopped asking what to do and started asking which one "
             "moves. Different question, same problem, solved."),
            (38, "Confided In",
             "I walked this pass from the middle once, when I was young. It took "
             "two days and I learned nothing except this."),
            (60, "Signature", "The sabers are a pair. They were always meant to be."),
        )),
    MentorTrack(
        mentor="window_mage", skills=("SLIDING_WINDOW",), chain="window_ward",
        technique="tech_ward",
        tiers=(
            (0, "Stranger",
             "Expand right. When the ward breaks, shrink left. Never start over."),
            (8, "Known",
             "You let it break without flinching. Most people restart out of "
             "embarrassment."),
            (20, "Trusted",
             "You delete the key at zero now. That line is the difference between "
             "a window and a very slow lie."),
            (38, "Confided In",
             "The marsh was a lake. The frame is what is left of the thing that "
             "measured it. I am not certain which of us is the relic."),
            (60, "Signature",
             "The ward will hold through one break for you. Only one, and only the "
             "break — never the mistake."),
        )),
    MentorTrack(
        mentor="druid", skills=("RECURSION", "TREE", "DFS"),
        chain="druid_smaller_call", technique="tech_smaller_call",
        tiers=(
            (0, "Stranger",
             "Trust the smaller call to be correct. Then say what you do with its "
             "answer."),
            (8, "Known",
             "You wrote the base case first. The forest went quiet. That was it "
             "approving."),
            (20, "Trusted",
             "A tree is recursion someone drew. You have stopped filing them "
             "separately."),
            (38, "Confided In",
             "Every clearing holds a smaller forest. I have never reached the "
             "smallest one. I have made peace with the base case being elsewhere."),
            (60, "Signature",
             "ROOT goes with you. He will say four things a month and three will "
             "be 'base case'."),
        )),
    MentorTrack(
        mentor="cartographer", skills=("BFS", "DFS", "GRAPH", "MATRIX"),
        chain="cartographer_roads", technique="tech_rings",
        tiers=(
            (0, "Stranger",
             "Rings of light for the shortest road. A single committed path for "
             "every road."),
            (8, "Known", "You marked on enqueue. The map thanks you and so do I."),
            (20, "Trusted",
             "A grid is a list of lists until you need a neighbour. Then it is a "
             "graph, and you saw that before I said it."),
            (38, "Confided In",
             "I am redrawing a realm that keeps moving. It is not a complaint. It "
             "is the only cartography worth doing."),
            (60, "Signature",
             "Your name is on the survey. Small letters. The Wastes are still "
             "mostly rubble."),
        )),
    MentorTrack(
        mentor="armorer", skills=("DEBUGGING",), chain="armorer_ten_cracks",
        technique="tech_read_the_failure",
        tiers=(
            (0, "Stranger",
             "Bring me your broken plate. We fix it the only way anything gets "
             "fixed — by reading it."),
            (8, "Known", "You read the failing input before you touched the code."),
            (20, "Trusted",
             "You have stopped rewriting and started repairing. Those are "
             "different crafts and only one of them scales."),
            (38, "Confided In",
             "Half these plates are mine. I keep them up so nobody mistakes me for "
             "someone who never cracked one."),
            (60, "Signature",
             "The end wall plate is yours. It will not stop you being wrong. It "
             "will stop it costing so much."),
        )),
    MentorTrack(
        mentor="oracle", skills=("BIG_O", "DP"), chain="oracle_cost",
        technique="tech_cost_first",
        tiers=(
            (0, "Stranger",
             "Count the work per element. Multiply by the elements. That is the "
             "whole art."),
            (8, "Known", "You stated a cost without hedging. Rarer than it should be."),
            (20, "Trusted",
             "Sequential adds, nested multiplies. You are out of the half of the "
             "room that confuses those under pressure."),
            (38, "Confided In",
             "I predict nothing. I multiply. People find this disappointing and "
             "then find it useful, in that order."),
            (60, "Signature",
             "You will name the cost before anyone asks. It reads as having chosen."),
        )),
    MentorTrack(
        mentor="testsmith", skills=("TESTING",), chain="testsmith_suite",
        technique="tech_edge_sense",
        tiers=(
            (0, "Stranger", "A suite every wrong answer passes is not a suite."),
            (8, "Known",
             "You predicted an output before the machine gave you one. That is the "
             "whole discipline in one gesture."),
            (20, "Trusted",
             "Empty, one element, all identical. You probe the boring inputs first "
             "now, which is where the bodies are."),
            (38, "Confided In",
             "I keep the failing suite on the bench as a warning. Occasionally as "
             "a joke. Mostly as a warning."),
            (60, "Signature",
             "A failed probe will name its category for you. Not its value. Never "
             "its value."),
        )),
    MentorTrack(
        mentor="scribe", skills=("COMMUNICATION", "STRING"), chain="scribe_aloud",
        technique="tech_first_sentence",
        tiers=(
            (0, "Stranger",
             "Say the approach aloud before the first keystroke. If you cannot, "
             "you do not have one yet."),
            (8, "Known", "Two columns. Yours matched. I write down when they do not."),
            (20, "Trusted",
             "You name the structure before the loop. Anyone listening can hear "
             "the difference between chosen and reached."),
            (38, "Confided In",
             "I have transcribed four hundred approaches. Thirty were plans. The "
             "rest were hope, spoken confidently."),
            (60, "Signature",
             "I am closing your ledger. Both columns, under time, consistently."),
        )),
    MentorTrack(
        mentor="chronomancer", skills=("SPEED",), chain="chronomancer_doubt",
        technique="tech_first_move",
        tiers=(
            (0, "Stranger",
             "You know this one. Now know it faster than you can doubt yourself."),
            (8, "Known", "Your gap is shorter. Nothing was added. Something was removed."),
            (20, "Trusted",
             "Under target on familiar patterns, repeatedly. That is a distribution, "
             "not a lucky afternoon."),
            (38, "Confided In",
             "I measure one number. People assume I must be shallow. I am simply "
             "finished."),
            (60, "Signature",
             "You start before you are certain and you are right as often as when "
             "you waited. That was the complaint you walked in with."),
        )),
    MentorTrack(
        mentor="interviewer", skills=("RECALL", "COMMUNICATION"), chain="",
        technique="",
        tiers=(
            (0, "Stranger",
             "There is no trick here. Just you, the problem, and the clock."),
            (8, "Known", "You stated the approach before writing. Noted."),
            (20, "Trusted",
             "You asked a clarifying question that changed your solution. That is "
             "the one that counts."),
            (38, "Confided In",
             "I am not the villain of this. I am the last honest room."),
            (60, "Signature",
             "Nothing is labelled in here. You have stopped needing it to be."),
        )),
]

MENTOR_BY_ID = {t.mentor: t for t in MENTOR_TRACKS}


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------
# One authored line at a moment that genuinely means something, fired in the
# result payload of the attempt that caused it. These exist because the engine
# already computes all of this and then says nothing about any of it.

MILESTONES = [
    Milestone(
        id="ms_first_unaided", name="Unaided", speaker="byte",
        trigger=When.event("first_unaided_clear"),
        line="No spells on that one. You had the whole thing in your head and you "
             "put it on the screen. That is the transaction.",
        reward={"xp": 50, "card": "card_reflex"}),
    Milestone(
        id="ms_first_s_rank", name="S Rank", speaker="chronomancer",
        trigger=When.event("first_s_rank"),
        line="First try, under target, nothing asked for. I have been waiting to "
             "log one of those.",
        reward={"xp": 70}),
    Milestone(
        id="ms_first_medium", name="A Real Medium", speaker="archivist",
        trigger=When.event("first_medium_unaided"),
        line="That was a Medium and you took it unaided. Mediums are what the "
             "interview is made of. The Easies were the alphabet.",
        reward={"xp": 120, "title": "Journeyman"}),
    Milestone(
        id="ms_first_boss", name="First Boss", speaker="narrator",
        trigger=When.event("first_boss_cleared"),
        line="Six phases: you named it, explained it, wrote it, survived the "
             "hidden trials, priced it, and recognised it again in disguise. That "
             "is not a fight. That is an interview with a sprite on it.",
        reward={"xp": 150, "set_piece": "scene_first_boss"}),
    Milestone(
        id="ms_retest_week", name="Seven Days Later", speaker="oracle",
        trigger=When.event("retest_survived_7d"),
        line="A week later, in disguise, and you still had it. Recall is the only "
             "evidence that the learning was learning rather than weather.",
        reward={"xp": 130, "card": "card_trade_memory"}),
    Milestone(
        id="ms_ten_repairs", name="Ten Cracks Mended", speaker="armorer",
        trigger=When.stat("armor_repairs", 10),
        line="Ten plates. You have repaired more programs than most people ever "
             "read. TRACE has noticed, and she is a snob about it.",
        reward={"xp": 140, "card": "card_trace_by_hand"}),
    Milestone(
        id="ms_gates_half", name="Halfway Honest", speaker="interviewer",
        trigger=When.gates_percent(50),
        line="Half the readiness gates. I want to be precise about what that "
             "means: on half the measures that predict the room, you already pass.",
        reward={"xp": 160, "codex": "codex_gates"}),
    Milestone(
        id="ms_first_probe", name="Called It", speaker="testsmith",
        trigger=When.event("probe_correct"),
        line="You predicted the output and you were right. Do that in the room and "
             "they stop watching your syntax.",
        reward={"xp": 40}),
    Milestone(
        id="ms_chapter", name="Chapter Closed", speaker="narrator",
        trigger=When.event("chapter_graduated"),
        line="That chapter is behind you on both counts — the mastery and the "
             "clears. It took both on purpose. Either alone can be faked.",
        reward={"xp": 100}),
    Milestone(
        id="ms_combo_five", name="Five In A Row", speaker="chronomancer",
        trigger=When.event("combo_five"),
        line="Five consecutive. Not one of them was your best work and that is "
             "exactly the point. Consistency is the thing under pressure.",
        reward={"xp": 60}),
    Milestone(
        id="ms_comeback", name="The One That Beat You", speaker="armorer",
        trigger=When.event("comeback_clear"),
        line="That problem beat you three times and you came back to it. Most "
             "people quietly never open it again.",
        reward={"xp": 110, "title": "Persistent"}),
    Milestone(
        id="ms_linear", name="Quadratic To Linear", speaker="oracle",
        trigger=When.event("perf_recovered"),
        line="You failed that one on performance alone, and then you did not "
             "change the answer, you changed the cost. Those are different edits "
             "and only one is engineering.",
        reward={"xp": 150, "card": "card_refuse_to_answer_twice"}),
]

MILESTONE_BY_ID = {m.id: m for m in MILESTONES}


# ---------------------------------------------------------------------------
# The first session
# ---------------------------------------------------------------------------
# The exact ordered opening for a brand new player. Each step names the cue that
# advances it, so the client never has to guess where it is. The whole script is
# roughly thirty minutes and every step after the third is gated on the player
# actually doing something.

FirstStep = dict

FIRST_SESSION = [
    {"id": "fs_01_intro", "minutes": 1, "screen": "modal", "speaker": "narrator",
     "cue": "game_started", "advance_on": "player_dismisses",
     "title": "The Shattering",
     "lines": ("The Source was a language. The Null King un-named it.",
               "You are the Security Architect. You can already see what needs to "
               "happen. You cannot yet say it in Python quickly enough for anyone "
               "to watch you do it.",
               "That is the entire gap. This is the whole game."),
     "shows": "No build choice, no attribute points, no menus. One screen."},

    {"id": "fs_02_village", "minutes": 2, "screen": "overworld",
     "speaker": "narrator", "cue": "region_entered:python_village",
     "advance_on": "player_walks_to_mentor",
     "title": "Python Village",
     "lines": ("Half the roofs are missing. The village holds its shape only while "
               "somebody nearby can still speak the language.",
               "The automaton in the square is waiting for you. It has been waiting "
               "for some time and will say so."),
     "shows": "Movement only. Travel, gear and the quest log stay locked."},

    {"id": "fs_03_first_mentor", "minutes": 3, "screen": "dialogue", "speaker": "byte",
     "cue": "mentor_met:byte", "advance_on": "player_accepts",
     "title": "BYTE",
     "lines": ("You read code well. I have seen your reports. None of that is in "
               "question and none of it is what we are fixing.",
               "We are fixing the blank screen. One rune at a time, and the first "
               "one has a hole in it that you fill in.",
               "Everything else on the line is already written. This is not a "
               "kindness, it is a measurement."),
     "shows": "Introduces the GUIDED tier in the mentor's own words."},

    {"id": "fs_04_tiny_encounter", "minutes": 5, "screen": "battle", "speaker": "byte",
     "cue": "encounter_started", "advance_on": "encounter_cleared",
     "title": "One Blank Rune",
     "lines": ("One blank. Read the three lines around it and write the one thing "
               "that is missing.",
               "There is no clock on this and there is no rank. Nothing here is "
               "being scored against you yet."),
     "shows": "A GUIDED / MISSING_RUNE encounter with a single __BLANK__. "
              "No probe UI, no spell bar, no timer."},

    {"id": "fs_05_first_win", "minutes": 7, "screen": "battle", "speaker": "byte",
     "cue": "encounter_cleared", "advance_on": "player_continues",
     "title": "That Counted",
     "lines": ("That counted. Not as encouragement — it moved a number, and the "
               "number is the only thing here that can move.",
               "Two more like it, then the blanks start multiplying."),
     "shows": "The XP bar tweens on the battle screen, in view. The results panel "
              "opens the player's line against the canonical one, at the top."},

    {"id": "fs_06_first_equipment", "minutes": 10, "screen": "loot",
     "speaker": "narrator", "cue": "loot_taken", "advance_on": "item_equipped",
     "title": "Something To Wear",
     "lines": ("A drop, and an empty slot to put it in.",
               "Gear changes what a fight costs and what it pays. It has never "
               "written a line of Python and it never will."),
     "shows": "Inventory opens for the first time, with the icon art actually "
              "drawn. Rule 4 stated once, plainly, and then never repeated."},

    {"id": "fs_07_the_armorer", "minutes": 14, "screen": "dialogue",
     "speaker": "armorer", "cue": "region_entered:debugging_dungeon",
     "advance_on": "armor_repaired",
     "title": "The Armorer",
     "lines": ("This program is four lines long and one of them is wrong. Find the "
               "wrong one. Do not rewrite the other three.",
               "Your armour repairs by debugging and by nothing else. Not levels, "
               "not loot, not rest.",
               "You are already good at reading somebody else's broken code. This "
               "is the half you have done professionally for a decade."),
     "shows": "A DEBUG_BATTLE at GUIDED tier, and the first armour bar filling."},

    {"id": "fs_08_world_map", "minutes": 18, "screen": "overworld",
     "speaker": "narrator", "cue": "armor_repaired", "advance_on": "map_opened",
     "title": "The Map Opens",
     "lines": ("Three regions are open. Thirteen are sealed and each one tells you "
               "exactly what it wants before you walk at it.",
               "Nothing here is locked behind a level. It is locked behind "
               "evidence, which you can read on the same screen."),
     "shows": "Travel unlocks. Every sealed region shows its criterion as a "
              "progress bar — 'PYTHON mastery 8/25' — never a bare 'Sealed'."},

    {"id": "fs_09_assessment", "minutes": 21, "screen": "dialogue",
     "speaker": "oracle", "cue": "map_opened", "advance_on": "diagnostic_started",
     "title": "The Assessment Begins",
     "lines": ("I am going to ask you a short series of questions and then stop "
               "asking. Six minutes.",
               "It is not a test you pass. It is the shape of what you already "
               "know, so that the realm stops handing you things you do not need "
               "and things you are not ready for.",
               "You may get several wrong. That is the entire point of asking."),
     "shows": "The diagnostic. Sets the opening chapter and the first difficulty "
              "targets; writes player['diagnostic_done']."},

    {"id": "fs_10_first_chain", "minutes": 25, "screen": "quest_log",
     "speaker": "byte", "cue": "diagnostic_done", "advance_on": "player_continues",
     "title": "The Metronome Begins",
     "lines": ("Five drills and I will show you your time-to-first-keystroke.",
               "It is a worse number than you think and it is the one that improves "
               "fastest."),
     "shows": "The quest log opens with one chain started, its first step at 1/5, "
              "and the chapter ladder visible above it."},

    {"id": "fs_11_the_rival", "minutes": 27, "screen": "overworld",
     "speaker": "kestrel", "cue": "solved:6", "advance_on": "player_continues",
     "title": "KESTREL",
     "lines": ("Another architect, on the same road, further along on exactly one "
               "thing and behind on the rest.",
               "They will tell you which one, and by how much, and they will not "
               "make a thing of it."),
     "shows": "The first rival meeting. One skill, one number, one bar."},

    {"id": "fs_12_the_reason", "minutes": 30, "screen": "session_report",
     "speaker": "narrator", "cue": "session_ended", "advance_on": "player_exits",
     "title": "What Moved",
     "lines": ("PYTHON went from nothing to a number. One chapter is open, one "
               "chain is running, one plate is mended.",
               "Two patterns come due in three days. They will be wearing different "
               "clothes and they pay more for it.",
               "The village is still missing most of its roofs. It gets them back "
               "the same way it lost them."),
     "shows": "The session report: mastery deltas, stages advanced, retests due "
              "with dates, quest turn-ins paid. A full stop, not a trailing comma."},
]


# ---------------------------------------------------------------------------
# Rewards that are made of words
# ---------------------------------------------------------------------------
# Grimoire cards are revision cards, not hints: they are only ever awarded AFTER
# the evidence, they name a rule rather than a solution, and they are unavailable
# during an encounter. A card the player could open mid-fight would be a hint
# with a nicer border.

GRIMOIRE_CARDS = {
    "card_reflex": {
        "name": "Start Before You Are Sure", "pattern": "PYTHON",
        "front": "The screen is blank and you have no plan. What goes on line one?",
        "back": "The signature, then a named variable for the thing you are "
                "accumulating. Naming the accumulator is usually where the plan "
                "arrives from."},
    "card_read_the_error": {
        "name": "The Error Is Addressed To You", "pattern": "DEBUGGING",
        "front": "A traceback appears. What do you read first?",
        "back": "The last line, for the type. Then the line number. Then the "
                "failing input. Guessing before reading costs more than reading."},
    "card_trace_by_hand": {
        "name": "Trace It By Hand", "pattern": "DEBUGGING",
        "front": "A test fails and the code looks right. Next move?",
        "back": "Take the failing input and walk the loop on paper, one iteration. "
                "The defect is almost always visible by iteration two."},
    "card_seen_before": {
        "name": "Have I Seen This Before", "pattern": "HASH_MAP",
        "front": "The problem asks about duplicates, pairs, counts or groups. "
                 "Which structure?",
        "back": "A dict when you need the value back, a set when you only need "
                "membership. Both are O(1) average. The loop writes itself after."},
    "card_trade_memory": {
        "name": "Buy Memory Once", "pattern": "HASH_MAP",
        "front": "Nested loops comparing every element to every other. What is the "
                 "standard trade?",
        "back": "One pass that records what it has seen. O(n) time for O(n) space. "
                "This single trade converts more quadratics than everything else "
                "combined."},
    "card_canonical_form": {
        "name": "Same Thing, Written Once", "pattern": "STRING",
        "front": "Two inputs should be treated as equal. What do you build?",
        "back": "A canonical form to use as a key — sorted letters, a character "
                "count tuple, a normalised case. Group by the form, not the input."},
    "card_boundaries": {
        "name": "Empty, One, All The Same", "pattern": "TESTING",
        "front": "Before you submit, which three inputs do you try?",
        "back": "Empty, a single element, and all-identical. Then negatives and "
                "the exact boundary. The interesting input is rarely the one that "
                "breaks it."},
    "card_never_restart": {
        "name": "Never Restart The Scan", "pattern": "SLIDING_WINDOW",
        "front": "The window breaks its constraint. What happens?",
        "back": "Shrink from the left until it holds again. Never move the right "
                "pointer backwards. And delete the key when its count reaches zero, "
                "or len() will keep counting it."},
    "card_which_one_moves": {
        "name": "Which One Moves", "pattern": "TWO_POINTER",
        "front": "Two pointers on a sorted array, and the sum is wrong. Which moves?",
        "back": "Sum too small, move the left pointer right. Too large, move the "
                "right pointer left. For container-of-water, always move the "
                "shorter wall."},
    "card_nested_is_a_stack": {
        "name": "Nested Is A Stack", "pattern": "STACK",
        "front": "How do you tell a stack problem from a queue problem?",
        "back": "Anything nested, matched or undoable is a stack. Anything fair, "
                "in order, or shortest-first is a queue."},
    "card_grid_is_a_graph": {
        "name": "A Grid Is A Graph", "pattern": "MATRIX",
        "front": "When does a matrix stop being a list of lists?",
        "back": "The moment you need a neighbour. Then it is a graph with four "
                "edges per node, and every traversal you already know applies."},
    "card_base_case_first": {
        "name": "Base Case First", "pattern": "RECURSION",
        "front": "What are the only two parts of a recursive function?",
        "back": "When to stop, and what to do with the answer from below. Write "
                "them in that order. There is no third part."},
    "card_carry_bounds": {
        "name": "Carry The Bounds Down", "pattern": "TREE",
        "front": "Validating a BST. Why is comparing to the children not enough?",
        "back": "A node deep on the left must still be less than an ancestor far "
                "above it. Pass a low and high bound down the recursion."},
    "card_mark_on_enqueue": {
        "name": "Mark It When You Queue It", "pattern": "BFS",
        "front": "When is a node marked visited in BFS?",
        "back": "When it enters the queue, not when it leaves. Marking on pop lets "
                "the same node be queued many times and quietly ruins the bound."},
    "card_refuse_to_answer_twice": {
        "name": "Refuse To Answer Twice", "pattern": "DP",
        "front": "The recursion is correct and exponentially slow. Next step?",
        "back": "Notice which arguments repeat, and cache on exactly those. "
                "Memoise first; convert to a table only if you need the order."},
    "card_count_per_element": {
        "name": "Count The Work Per Element", "pattern": "COMPLEXITY",
        "front": "How do you price an algorithm in one pass?",
        "back": "Work per element times elements. Sequential work adds, nested "
                "work multiplies. A sort inside a loop is n squared log n, and "
                "that is usually the bug."},
    "card_start_before_certain": {
        "name": "The Gap", "pattern": "SPEED",
        "front": "You recognise the pattern but have not started typing. Why not?",
        "back": "Because certainty feels like a prerequisite and is not one. Write "
                "the signature and the accumulator. The plan finishes arriving "
                "while your hands are moving."},
    "card_say_it_first": {
        "name": "Say It Before You Type It", "pattern": "RECOGNITION",
        "front": "What is the first sentence of any solution?",
        "back": "The structure and why. 'A dict from value to index, one pass.' If "
                "you cannot say it in one sentence you do not have an approach yet."},
}

CODEX = {
    "codex_source": {
        "title": "The Source",
        "text": "A language, not a weapon. Anything the realm could compute, it "
                "computed by being described to precisely enough. The Null King "
                "did not break it — he removed its names, and a language nobody "
                "can pronounce is indistinguishable from a ruin."},
    "codex_village": {
        "title": "Why The Village Is Half Built",
        "text": "Buildings here hold their shape while somebody nearby can still "
                "say what they are. Fluency is literally load-bearing. The village "
                "has four states and you have seen the worst of them."},
    "codex_armour": {
        "title": "Why Armour Only Mends By Debugging",
        "text": "A crack is a defect in some program. Levels do not close it, gold "
                "does not close it, and rest does not close it. Reading the failing "
                "input closes it. The Armorer considers this obvious and is "
                "correct, which is the irritating part."},
    "codex_vaults": {
        "title": "The Four Vaults",
        "text": "dict for lookup, set for membership, list for order, tuple for a "
                "fixed record. Most problems are decided by this choice before a "
                "single loop is written, and most bad solutions are a good loop "
                "over the wrong vault."},
    "codex_index": {
        "title": "Counting From Zero",
        "text": "The caverns number from zero and the last alcove is one short of "
                "the count. Roughly half of all defects in this realm are that "
                "sentence, misremembered under time pressure."},
    "codex_window": {
        "title": "The Frame",
        "text": "Built to measure a lake that is now a marsh. It widens right until "
                "the ward breaks and gives ground on the left until it holds. It "
                "has never once been carried back to the start, which is why it "
                "still works."},
    "codex_order": {
        "title": "Last In, First Out",
        "text": "The mines have run two rules for centuries without confusing them. "
                "Carts unload from the top. The lift takes whoever has waited "
                "longest. Nesting is a stack; fairness is a queue."},
    "codex_recursion": {
        "title": "The Forest Inside The Forest",
        "text": "Each clearing contains a smaller copy. You go in, and you come "
                "back carrying what the smaller one found. Nobody has reached the "
                "smallest clearing. The Druid says the base case is elsewhere and "
                "declines to elaborate."},
    "codex_search": {
        "title": "Two Surveys",
        "text": "Rings of light spread outward and the first ring to touch the "
                "destination is the shortest road, for free, by the order of "
                "visiting. A single committed path finds every road instead. They "
                "answer different questions and are not rivals."},
    "codex_cost": {
        "title": "The Tower's Rent",
        "text": "Each floor holds twice the enemies of the one below. The top floor "
                "is unreachable by brute force, deliberately, as architecture. "
                "Count the work per element, multiply by the elements, and you know "
                "before you climb whether you can."},
    "codex_gates": {
        "title": "The Thirteen Gates",
        "text": "Readiness is not a feeling. It is thirteen measures — fluency, "
                "recognition, algorithms, structures, debugging, testing, "
                "complexity, communication, retention, speed and the rest — each "
                "of which has a number and none of which move on exposure."},
    "codex_kestrel": {
        "title": "KESTREL",
        "text": "Another architect on the same road. Weaker on systems, stronger on "
                "production speed, and honest about both. Their lead has been "
                "measured at every meeting and it has never once grown."},
    "codex_castle": {
        "title": "The Castle",
        "text": "No signposts, no region names, nothing that says which pattern a "
                "room wants. It is not cruelty, it is the only honest arrangement, "
                "because nothing outside will be labelled either."},
    "codex_ending": {
        "title": "What It Was For",
        "text": "The Null King is not killed. He is named, correctly, out loud, by "
                "somebody who can also say why. That was always the requirement and "
                "it was never about courage."},
}

SET_PIECES = {
    "scene_village_restored": {
        "name": "The Village Stands",
        "scene": "The camera holds on the east row while roofs, doors and glass "
                 "resolve a tier at a time. BYTE says one line and does not "
                 "elaborate. The region card gains a RESTORED state."},
    "scene_titan_falls": {
        "name": "The Titan Stops Waiting",
        "scene": "It does not fall so much as stop. Its scrolls settle into one "
                 "indexed stack, and the plateau's vaults all open at once, "
                 "briefly, showing one rune each."},
    "scene_marsh_clear": {
        "name": "One Unbroken Pass",
        "scene": "The frame crosses the entire marsh without resetting. Behind it "
                 "the reeds stay lit. The Window Mage does not applaud; she writes "
                 "down the time."},
    "scene_plate_hung": {
        "name": "The Legendary Plate",
        "scene": "The Armorer takes the end-wall plate down for the first time in "
                 "the game's history and hangs your old cracked chestplate in its "
                 "place, uncommented."},
    "scene_first_boss": {
        "name": "Six Phases",
        "scene": "The boss HP bar reveals as six pips rather than a bar, and each "
                 "one darkens as its phase clears. The final pip is the disguised "
                 "rematch."},
    "scene_kestrel_concedes": {
        "name": "Level",
        "scene": "KESTREL turns their own skill panel around so you can read it, "
                 "which is the single least dramatic gesture in the game and the "
                 "one the player will remember."},
    "scene_source_restored": {
        "name": "Named Correctly",
        "scene": "Every region's palette resolves to its unbroken form for four "
                 "seconds, in unlock order, and the castle's rooms acquire labels "
                 "one by one. Then the labels fade, because you no longer need them."},
}


# ---------------------------------------------------------------------------
# The API the engine actually calls
# ---------------------------------------------------------------------------

_KIND_ORDER = {"main": 0, "chain": 1, "milestone": 2, "rival": 3}


def _entry(kind: str, ident: str, title: str, speaker: str, region: str,
           lines, reward: dict, objective: str = "", extra: dict | None = None) -> dict:
    payload = {"kind": kind, "id": ident, "title": title, "speaker": speaker,
               "speaker_name": _speaker_name(speaker), "region": region,
               "lines": list(lines), "reward": dict(reward), "objective": objective}
    if extra:
        payload.update(extra)
    return payload


def _speaker_name(speaker: str) -> str:
    if speaker == "narrator":
        return ""
    if speaker == RIVAL["id"]:
        return RIVAL["name"]
    mentor = world.MENTORS.get(speaker)
    return mentor["name"] if mentor else speaker.upper()


def pending(ctx: dict, story_state: dict) -> list:
    """Every beat that has just become true and has not been shown.

    Order is main beat, then chain step, then milestone, then rival — the arc
    first, the personal consequence second. The caller shows them in sequence and
    calls `apply` on each.
    """
    fired = set(story_state.get("fired", []))
    out = []

    for beat in MAIN_QUEST:
        if beat.id in fired or not trigger_met(beat.trigger, ctx):
            continue
        out.append(_entry("main", beat.id, beat.title, beat.speaker, beat.region,
                          beat.lines, beat.reward, beat.objective,
                          {"act": beat.act}))

    for chain in SIDE_CHAINS:
        index = int(story_state.get("chains", {}).get(chain.id, 0))
        if index >= len(chain.steps):
            continue
        step = chain.steps[index]
        if step.id in fired or not trigger_met(step.trigger, ctx):
            continue
        out.append(_entry("chain", step.id, step.title, chain.mentor, chain.region,
                          step.lines, step.reward, step.objective,
                          {"chain": chain.id, "chain_title": chain.title,
                           "step": index + 1, "steps": len(chain.steps),
                           "final": index + 1 == len(chain.steps)}))

    for milestone in MILESTONES:
        if milestone.id in fired or not trigger_met(milestone.trigger, ctx):
            continue
        out.append(_entry("milestone", milestone.id, milestone.name,
                          milestone.speaker, ctx.get("region", ""),
                          (milestone.line,), milestone.reward))

    held = int(story_state.get("rival", {}).get("meetings", 0))
    if held < len(RIVAL_MEETINGS):
        meeting = RIVAL_MEETINGS[held]
        meeting_id = f"rival_{meeting.index}"
        if meeting_id not in fired and trigger_met(meeting.trigger, ctx):
            out.append(_entry("rival", meeting_id,
                              f"{RIVAL['name']} — meeting {meeting.index}",
                              RIVAL["id"], meeting.place,
                              rival_lines(meeting, ctx), meeting.reward,
                              extra={"status": rival_status(ctx)}))

    out.sort(key=lambda e: _KIND_ORDER.get(e["kind"], 9))
    return out


def apply(story_state: dict, entry: dict) -> dict:
    """Record a shown beat and bank everything story owns.

    Returns the part of the reward only the engine can pay — XP, gold, a
    companion, a consumable — so the caller never has to know the reward
    vocabulary. Everything else (titles, cards, codex, scenes, techniques,
    favour) is written into story_state here.
    """
    reward = entry.get("reward") or {}
    fired = story_state.setdefault("fired", [])
    if entry["id"] in fired:
        return {}
    fired.append(entry["id"])

    if entry["kind"] == "chain":
        chains = story_state.setdefault("chains", {})
        chains[entry["chain"]] = chains.get(entry["chain"], 0) + 1
    elif entry["kind"] == "rival":
        rival = story_state.setdefault("rival", {"meetings": 0, "conceded": False})
        rival["meetings"] = rival.get("meetings", 0) + 1
        status = entry.get("status") or {}
        rival["conceded"] = bool(status.get("conceded"))
        rival["best_gap"] = status.get("gap", rival.get("best_gap", 0.0))

    for key, bucket in (("title", "titles"), ("card", "cards"),
                        ("codex", "codex"), ("set_piece", "set_pieces"),
                        ("technique", "techniques")):
        value = reward.get(key)
        if value:
            store = story_state.setdefault(bucket, [])
            if value not in store:
                store.append(value)

    favor = reward.get("favor")
    if favor:
        ledger = story_state.setdefault("favor", {})
        ledger[favor["mentor"]] = ledger.get(favor["mentor"], 0) + favor["amount"]

    return {k: reward[k] for k in ("xp", "gold", "companion", "consumable")
            if k in reward}


def reward_summary(reward: dict) -> list:
    """Human lines for the turn-in panel. Names what was given, never why."""
    out = []
    if reward.get("xp"):
        out.append(f"{reward['xp']} XP")
    if reward.get("gold"):
        out.append(f"{reward['gold']} gold")
    if reward.get("title"):
        out.append(f"Title: {reward['title']}")
    card = GRIMOIRE_CARDS.get(reward.get("card", ""))
    if card:
        out.append(f"Grimoire card: {card['name']}")
    entry = CODEX.get(reward.get("codex", ""))
    if entry:
        out.append(f"Codex: {entry['title']}")
    scene = SET_PIECES.get(reward.get("set_piece", ""))
    if scene:
        out.append(scene["name"])
    tech = TECHNIQUE_BY_ID.get(reward.get("technique", ""))
    if tech:
        out.append(f"Technique: {tech.name} — {'; '.join(_effect_lines(tech))}")
    if reward.get("companion"):
        companion = next((c for c in world.COMPANIONS
                          if c["id"] == reward["companion"]), None)
        out.append(f"{companion['name']} joins you" if companion
                   else f"Companion: {reward['companion']}")
    if reward.get("favor"):
        out.append(f"{_speaker_name(reward['favor']['mentor'])} remembers this")
    return out


def _effect_lines(tech: Technique) -> list:
    """Rendered without importing items, so story stays a leaf module."""
    labels = {"probe_charges": "+{v} probe charge", "mana_max": "+{v} focus",
              "stamina_max": "+{v} stamina", "hint_discount": "spells cost {p}% less",
              "rank_grace": "+{p}% clock grace", "crit_bonus": "+{p}% weakness XP",
              "loot_luck": "+{p}% loot quality", "xp_bonus": "+{p}% XP",
              "retest_bonus": "+{p}% retest XP",
              "combo_shield": "combo survives {v} failure",
              "reveal_category": "failed probes name their category",
              "perf_insight": "performance trials state their budget",
              "armor_repair": "+{p}% armour per repair"}
    out = []
    for key, value in tech.effects.items():
        template = labels.get(key, key)
        out.append(template.replace("{v}", str(value))
                   .replace("{p}", str(int(round(value * 100)))))
    return out


def main_progress(ctx: dict, story_state: dict) -> dict:
    """The arc, annotated, for the quest log. The next beat always shows its
    criterion with the numbers in it — no hidden thresholds."""
    fired = set(story_state.get("fired", []))
    done = [b for b in MAIN_QUEST if b.id in fired]
    upcoming = [b for b in MAIN_QUEST if b.id not in fired]
    current = upcoming[0] if upcoming else None
    return {
        "completed": len(done),
        "total": len(MAIN_QUEST),
        "act": current.act if current else ACT_VI,
        "current": {
            "id": current.id, "title": current.title, "act": current.act,
            "region": current.region,
            "region_name": world.REGION_BY_ID.get(current.region, {}).get(
                "name", current.region),
            "objective": (MAIN_BY_ID[done[-1].id].objective if done
                          else MAIN_QUEST[0].objective),
            "requirement": describe_trigger(current.trigger, ctx),
            "progress": trigger_progress(current.trigger, ctx),
        } if current else None,
        "beats": [
            {"id": b.id, "title": b.title, "act": b.act, "region": b.region,
             "done": b.id in fired,
             "requirement": describe_trigger(b.trigger, ctx) if b.id not in fired
             else ""}
            for b in MAIN_QUEST
        ],
    }


def chain_view(chain: Chain, ctx: dict, story_state: dict) -> dict:
    index = int(story_state.get("chains", {}).get(chain.id, 0))
    complete = index >= len(chain.steps)
    step = None if complete else chain.steps[index]
    mentor = world.MENTORS.get(chain.mentor, {})
    return {
        "id": chain.id, "title": chain.title, "premise": chain.premise,
        "mentor": chain.mentor, "mentor_name": mentor.get("name", chain.mentor),
        "skill": chain.skill, "region": chain.region,
        "step": min(index + 1, len(chain.steps)), "steps": len(chain.steps),
        "complete": complete,
        "objective": step.objective if step else "",
        "requirement": describe_trigger(step.trigger, ctx) if step else "",
        "progress": trigger_progress(step.trigger, ctx) if step else
        {"label": "", "current": 1, "required": 1, "met": True},
        "final_reward": reward_summary(chain.reward),
    }


def chains_view(ctx: dict, story_state: dict) -> list:
    return [chain_view(c, ctx, story_state) for c in SIDE_CHAINS]


def mentor_view(track: MentorTrack, ctx: dict, story_state: dict) -> dict:
    favor = mentor_favor(track.mentor, ctx)
    rank_index, rank_label = mentor_rank(favor)
    line = track.tiers[min(rank_index, len(track.tiers) - 1)][2]
    nxt = track.tiers[rank_index + 1] if rank_index + 1 < len(track.tiers) else None
    mentor = world.MENTORS.get(track.mentor, {})
    tech = TECHNIQUE_BY_ID.get(track.technique)
    return {
        "id": track.mentor, "name": mentor.get("name", track.mentor),
        "role": mentor.get("role", ""), "sprite": mentor.get("sprite", ""),
        "skills": list(track.skills),
        "favor": favor, "rank": rank_label, "rank_index": rank_index,
        "next_rank": nxt[1] if nxt else None,
        "next_at": nxt[0] if nxt else None,
        "line": line,
        "chain": track.chain,
        "technique": ({
            "id": tech.id, "name": tech.name, "blurb": tech.blurb, "line": tech.line,
            "effects": _effect_lines(tech),
            "owned": tech.id in story_state.get("techniques", []),
            "active": tech.id in story_state.get("techniques", [])
            and trigger_met(tech.requires, ctx),
            "requirement": describe_trigger(tech.requires, ctx),
            "progress": trigger_progress(tech.requires, ctx),
        } if tech else None),
    }


def mentors_view(ctx: dict, story_state: dict) -> list:
    return [mentor_view(t, ctx, story_state) for t in MENTOR_TRACKS]


def session_script(story_state: dict) -> dict:
    """Where the first-session script has got to, or None once it is finished."""
    session = story_state.get("session") or {"step": 0, "complete": False}
    index = int(session.get("step", 0))
    if session.get("complete") or index >= len(FIRST_SESSION):
        return {"active": False, "step": None, "index": len(FIRST_SESSION),
                "total": len(FIRST_SESSION)}
    return {"active": True, "step": dict(FIRST_SESSION[index]), "index": index,
            "total": len(FIRST_SESSION)}


def advance_session(story_state: dict) -> dict:
    session = story_state.setdefault("session", {"step": 0, "complete": False})
    session["step"] = int(session.get("step", 0)) + 1
    if session["step"] >= len(FIRST_SESSION):
        session["complete"] = True
    return session


def quest_log(ctx: dict, story_state: dict) -> dict:
    """One payload the client can render the whole narrative panel from."""
    return {
        "main": main_progress(ctx, story_state),
        "chains": chains_view(ctx, story_state),
        "mentors": mentors_view(ctx, story_state),
        "rival": rival_status(ctx),
        "titles": list(story_state.get("titles", [])),
        "cards": [{"id": cid, **GRIMOIRE_CARDS[cid]}
                  for cid in story_state.get("cards", []) if cid in GRIMOIRE_CARDS],
        "codex": [{"id": eid, **CODEX[eid]}
                  for eid in story_state.get("codex", []) if eid in CODEX],
        "set_pieces": [{"id": sid, **SET_PIECES[sid]}
                       for sid in story_state.get("set_pieces", [])
                       if sid in SET_PIECES],
        "session": session_script(story_state),
    }


def honorific(story_state: dict) -> str:
    """The most recent story title. Shown beside world.title_for(level), never
    instead of it — one is narrative, the other is a level readout."""
    titles = story_state.get("titles", [])
    return titles[-1] if titles else ""


def validate() -> list:
    """Every id this module points at must resolve. Cheap enough to assert in a
    test and it catches the whole class of typo that silently renders nothing."""
    problems = []

    def check_reward(where: str, reward: dict):
        for key in reward:
            if key not in REWARD_KEYS:
                problems.append(f"{where}: unknown reward key {key!r}")
        if reward.get("card") and reward["card"] not in GRIMOIRE_CARDS:
            problems.append(f"{where}: unknown card {reward['card']!r}")
        if reward.get("codex") and reward["codex"] not in CODEX:
            problems.append(f"{where}: unknown codex entry {reward['codex']!r}")
        if reward.get("set_piece") and reward["set_piece"] not in SET_PIECES:
            problems.append(f"{where}: unknown set piece {reward['set_piece']!r}")
        if reward.get("technique") and reward["technique"] not in TECHNIQUE_BY_ID:
            problems.append(f"{where}: unknown technique {reward['technique']!r}")
        if reward.get("companion") and reward["companion"] not in {
                c["id"] for c in world.COMPANIONS}:
            problems.append(f"{where}: unknown companion {reward['companion']!r}")
        if reward.get("favor") and reward["favor"]["mentor"] not in world.MENTORS:
            problems.append(f"{where}: unknown mentor in favor grant")

    def check_trigger(where: str, trigger: Trigger):
        if trigger.kind in ("all", "any"):
            for part in trigger.parts:
                check_trigger(where, part)
            return
        if trigger.kind == "region_entered" and trigger.key not in world.REGION_BY_ID:
            problems.append(f"{where}: unknown region {trigger.key!r}")
        if trigger.kind == "boss_cleared" and trigger.key not in world.BOSS_BY_ID:
            problems.append(f"{where}: unknown boss {trigger.key!r}")
        if trigger.kind == "event" and trigger.key not in EVENTS:
            problems.append(f"{where}: unknown event {trigger.key!r}")
        if trigger.kind == "chapter" and trigger.key not in curriculum.CHAPTER_BY_ID:
            problems.append(f"{where}: unknown chapter {trigger.key!r}")
        if trigger.kind == "skill_stage" and trigger.text not in _STAGE_ORDER:
            problems.append(f"{where}: unknown stage {trigger.text!r}")

    seen_ids = set()
    for beat in MAIN_QUEST:
        if beat.id in seen_ids:
            problems.append(f"duplicate id {beat.id!r}")
        seen_ids.add(beat.id)
        if beat.region not in world.REGION_BY_ID:
            problems.append(f"{beat.id}: unknown region {beat.region!r}")
        if beat.speaker != "narrator" and beat.speaker not in world.MENTORS:
            problems.append(f"{beat.id}: unknown speaker {beat.speaker!r}")
        check_trigger(beat.id, beat.trigger)
        check_reward(beat.id, beat.reward)

    for chain in SIDE_CHAINS:
        if chain.mentor not in world.MENTORS:
            problems.append(f"{chain.id}: unknown mentor {chain.mentor!r}")
        if chain.region not in world.REGION_BY_ID:
            problems.append(f"{chain.id}: unknown region {chain.region!r}")
        if len(chain.steps) < 2:
            problems.append(f"{chain.id}: a chain needs at least two steps")
        for step in chain.steps:
            if step.id in seen_ids:
                problems.append(f"duplicate id {step.id!r}")
            seen_ids.add(step.id)
            check_trigger(step.id, step.trigger)
            check_reward(step.id, step.reward)

    for milestone in MILESTONES:
        if milestone.id in seen_ids:
            problems.append(f"duplicate id {milestone.id!r}")
        seen_ids.add(milestone.id)
        if milestone.speaker != "narrator" and milestone.speaker not in world.MENTORS:
            problems.append(f"{milestone.id}: unknown speaker {milestone.speaker!r}")
        check_trigger(milestone.id, milestone.trigger)
        check_reward(milestone.id, milestone.reward)

    for meeting in RIVAL_MEETINGS:
        where = f"rival_{meeting.index}"
        if meeting.place not in world.REGION_BY_ID:
            problems.append(f"{where}: unknown region {meeting.place!r}")
        check_trigger(where, meeting.trigger)
        check_reward(where, meeting.reward)
    leads = [m.lead for m in RIVAL_MEETINGS]
    if leads != sorted(leads, reverse=True):
        problems.append("rival: the lead must never grow between meetings")

    for track in MENTOR_TRACKS:
        if track.mentor not in world.MENTORS:
            problems.append(f"mentor track: unknown mentor {track.mentor!r}")
        if track.chain and track.chain not in CHAIN_BY_ID:
            problems.append(f"{track.mentor}: unknown chain {track.chain!r}")
        if track.technique and track.technique not in TECHNIQUE_BY_ID:
            problems.append(f"{track.mentor}: unknown technique {track.technique!r}")

    for tech in TECHNIQUES:
        if tech.mentor not in world.MENTORS:
            problems.append(f"{tech.id}: unknown mentor {tech.mentor!r}")
        check_trigger(tech.id, tech.requires)
        if not tech.effects:
            problems.append(f"{tech.id}: a technique with no effect is a lie")

    cues = {step["id"] for step in FIRST_SESSION}
    if len(cues) != len(FIRST_SESSION):
        problems.append("first session: duplicate step id")

    for text in _all_prose():
        if "!" in text:
            problems.append(f"exclamation mark in prose: {text[:60]!r}")

    return problems


def _all_prose():
    for beat in MAIN_QUEST:
        yield from beat.lines
        yield beat.objective
    for chain in SIDE_CHAINS:
        yield chain.premise
        for step in chain.steps:
            yield from step.lines
            yield step.objective
    for milestone in MILESTONES:
        yield milestone.line
    for meeting in RIVAL_MEETINGS:
        yield from meeting.lines
    for track in MENTOR_TRACKS:
        for _, _, line in track.tiers:
            yield line
    for tech in TECHNIQUES:
        yield tech.blurb
        yield tech.line
    for card in GRIMOIRE_CARDS.values():
        yield card["front"]
        yield card["back"]
    for entry in CODEX.values():
        yield entry["text"]
    for scene in SET_PIECES.values():
        yield scene["scene"]
    for step in FIRST_SESSION:
        yield from step["lines"]
        yield step["shows"]


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

WIRING = """
This module edits nothing. Six small changes in engine.py turn it on, and one
route in server.py exposes it. Nothing in world.py changes.

1. STATE
   engine.DEFAULT_STATE gains one key:

       "story": story.new_story_state(),

   _merge already forward-fills it for existing saves, so old saves start the
   story from beat one with their evidence intact — which is correct, because
   every trigger reads mastery and clears, not a timestamp.

   Add one more field to DEFAULT_STATE["player"]: "regions_entered": [] — or
   store it in state["story"]["regions_entered"]. build_context() reads either;
   without it the only region that ever counts as entered is the current one,
   which makes arrival beats fire late rather than never.

2. FIRING BEATS
   At the end of Game._apply_outcome, after _check_achievements and before the
   result dict is assembled:

       ctx = story.build_context(self.state, skills, readiness=None,
                                 events=self._story_events(...))
       beats = story.pending(ctx, self.state["story"])
       story_payload = []
       for beat in beats:
           owed = story.apply(self.state["story"], beat)
           if owed.get("xp"):
               player["xp"] += owed["xp"]          # re-derive level/title after
           if owed.get("gold"):
               player["gold"] += owed["gold"]
           if owed.get("companion") and owed["companion"] not in self.state["companions"]:
               self.state["companions"].append(owed["companion"])
           if owed.get("consumable"):
               key = owed["consumable"]["id"]
               self.state["consumables"][key] = (
                   self.state["consumables"].get(key, 0) + owed["consumable"]["count"])
           story_payload.append({**beat, "reward_lines": story.reward_summary(beat["reward"])})
       result["story"] = story_payload

   Re-run world.level_for / world.title_for after the loop, since a beat can pay
   enough XP to level. Milestone XP is paid on the same submission that earned
   it, which is the only moment it reads as a consequence.

   _story_events() builds the transient set from things _apply_outcome already
   knows: "first_unaided_clear" when solved and hints_used == 0 and this is the
   first such row in db; "first_s_rank" when rank == "S" and no earlier S;
   "first_medium_unaided" likewise for MEDIUM; "retest_survived_7d" when
   enc.is_retest and enc.interval_days >= 7 and solved; "first_boss_cleared" from
   _resolve_boss; "probe_correct" from the probe path; "combo_five" when
   player["combo"] == 5; "perf_recovered" and "comeback_clear" from the two
   conditions _check_secrets already computes; "chapter_graduated" when
   curriculum.frontier() increases across the attempt. All of them are already
   derivable — none needs new bookkeeping.

3. ARRIVAL BEATS
   Game.move() is the only other firing site. After writing the new region:

       entered = self.state["story"].setdefault("regions_entered", [])
       if region not in entered:
           entered.append(region)
       ctx = story.build_context(self.state, self.skills,
                                 events=("region_entered",))
       return {"story": [...]}   # same loop as above

4. TECHNIQUE EFFECTS
   Game.effects() folds one more source, alongside items:

       fx = items.fold(...)                       # existing
       ctx = story.build_context(self.state, self.skills)
       for key, value in story.technique_effects(self.state["story"], ctx).items():
           fx[key] = fx.get(key, 0) + value

   Two invariants. First, technique_effects re-checks each technique's mastery
   requirement every call, so a decayed skill silently suspends its bonus until
   the number comes back — a permanent bonus that outlives its evidence would be
   a reward for exposure. Second, Interview Mode must not call this at all: pass
   include_story=False from the interview path, exactly as hints and coaching are
   already sealed. A technique is not an answer, but the mode boundary is
   absolute and is enforced by tests/test_interview_isolation.py.

5. DASHBOARD
   Game.dashboard() gains two keys, built from data it already has:

       ctx = story.build_context(self.state, skills, readiness=ready)
       "story": story.quest_log(ctx, self.state["story"]),
       "honorific": story.honorific(self.state["story"]),

   Render honorific beside world.title_for(level), never instead of it — one is
   narrative, the other is a level readout.

6. FIRST SESSION
   On a save whose player["intro_seen"] is False, the client drives itself from
   story.session_script(state["story"]) and calls a new /api/story/advance which
   does story.advance_session(state["story"]) and saves. Each step names the cue
   that produced it and the cue that advances it, so the client never has to
   infer where it is. Step 9 is the diagnostic; that is the intended place for
   gauntlet/diagnostic.py to be called for the first time.

7. TESTS
   tests/ should assert story.validate() == [] — it resolves every region, boss,
   mentor, event, chapter, card, codex entry, scene, technique and companion id
   this module references, rejects an unknown reward key, checks the rival's lead
   never grows, and fails on an exclamation mark in authored prose.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
   It never chooses a problem. Selection stays in adaptive.py and curriculum.py.
   It never grants mastery, never modifies a skill, and never touches the SRS
   schedule. It pays out only after the engine has already graded the evidence,
   and every single trigger in it reads a number that only a graded attempt can
   move. If any beat here can fire without a submission, that is a bug.
"""
