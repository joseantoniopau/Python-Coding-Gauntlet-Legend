"""The game engine: state, encounters, combat, progression.

Everything the client can do goes through here, so the invariants live in one
place — chief among them that Interview Mode never leaks a hint, a pattern name,
or a coach.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, asdict

from . import adaptive, config, coach as coachmod, db, grading, items, sandbox
from . import curriculum, diagnostic, puzzles, story as storymod, tactics
from . import skills as skillmod
from . import srs as srsmod
from . import world
from . import bestiary, classes, dungeons, finalexam, incantation, legendaries
from . import pets, progression, quests, saves, worldgen
from .corpus import ensure as ensure_corpus
from .corpus.schema import Problem

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


def _item(item_id: str):
    """An item or an artifact, whichever owns this id. Artifacts never shadow."""
    found = items.BY_ID.get(item_id)
    if found is not None:
        return found
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
    # Companion interventions live here rather than in temp_effects, which is
    # folded straight into items.total_effects and can only hold numbers.
    pet_spoke: bool = False
    pet_spoken: dict = field(default_factory=dict)   # pet id -> times spoken
    rank_ceiling: str = ""          # the best rank still earnable here
    dungeon_room: int = -1          # the room this fight belongs to, or -1

    def to_dict(self) -> dict:
        return asdict(self)


# Which learning failure a puzzle miss actually represents.
_PUZZLE_CAUSE = {
    "RUNE_ASSEMBLY": "PYTHON_RECALL",
    "TRACE": "DEBUGGING",
    "SPOT_THE_FLAW": "DEBUGGING",
    "STATE_PREDICT": "PYTHON_RECALL",
    "BREAK_IT": "TESTING",
    "COMPLEXITY_MATCH": "COMPLEXITY",
}

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
    "solved_ids": [],
    "recent_ids": [],
    "attributes": {"LOGIC": 0, "FOCUS": 0, "VIGOR": 0, "INSIGHT": 0, "HASTE": 0},
    "unspent_points": 0,
    "build": "",
    "inventory": [],
    "equipped": {},
    "consumables": {},
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
              "forge_streak": 0},

    # --- the eleven modules' own sub-states -------------------------------
    # Each blob is whatever its owning module says it is, asked for rather than
    # copied, so a module that grows a key does not need this file edited. They
    # are all plain JSON and round-trip through db.save_state untouched.
    "pets": pets.new_state(),
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
    # What this sitting has already covered. The selector reads it to bring a
    # family back inside the session; the SRS schedule still owns tomorrow.
    "session": {"started_at": 0.0, "log": []},
}


class Game:
    def __init__(self, *, db_path=None, corpus_path=None, rebuild: bool = False):
        self.conn = db.connect(db_path)
        saves.ensure_schema(self.conn)          # named slots, autosave ring, undo
        self.corpus: list = ensure_corpus(corpus_path, rebuild=rebuild)
        self.by_id: dict = {p.id: p for p in self.corpus}
        self.state = self._load_or_create()
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
            db.save_state(self.conn, state)
            return state
        # forward-compatible: fill in anything a newer build added
        merged = _deep_copy(DEFAULT_STATE)
        _merge(merged, raw)
        for name in skillmod.SKILLS:
            merged["skills"].setdefault(name, skillmod.SkillState(name=name).to_dict())
        if not merged.get("story"):
            merged["story"] = storymod.new_story_state()
        return merged

    def save(self) -> None:
        self._tick_playtime()
        db.save_state(self.conn, self.state)

    # -- typed views over the raw state ------------------------------------
    @property
    def skills(self) -> dict:
        return {name: skillmod.SkillState(**data)
                for name, data in self.state["skills"].items()}

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
        return Encounter(**raw) if raw else None

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
        # contribute nothing at all in Interview Mode — party_effects self-guards,
        # but the region gate is ours.
        if pets.available_in(mode, region_id):
            for key, value in pets.party_effects(
                    self.state["pets"].get("active", []),
                    self.state["pets"].get("bond", {}), mode=mode).items():
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

    def _sync_caps(self) -> None:
        """Equipment and attributes change the ceilings, never the current values
        downward past what the player already holds."""
        fx = self.effects(include_temp=False)
        player = self.state["player"]
        player["stamina_max"] = config.STAMINA_MAX + int(fx.get("stamina_max", 0))
        player["mana_max"] = config.MANA_MAX + int(fx.get("mana_max", 0))
        player["stamina"] = min(player["stamina"], player["stamina_max"])
        player["mana"] = min(player["mana"], player["mana_max"])

    def loadout(self) -> dict:
        fx = self.effects(include_temp=False)
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
            "probe_charges": items.base_probe_charges(fx),
            "secrets": [
                {**s, "found": s["id"] in self.state["secrets_found"]}
                for s in items.SECRETS
            ],
            "rarities": items.RARITIES,
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

        ctx = quests.context(self.story_context(readiness=ready), self.state)
        run = self.state.get(dungeons.STATE_KEY)
        dungeon_view = None
        if run:
            built = self._dungeon_for(run["dungeon"], run.get("seed"))
            dungeon_view = {**dungeons.progress(built, run),
                            "depth": self._dungeon_depth(built, run),
                            "options": dungeons.options(built, run),
                            "name": built.name}
        self.save()

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
            "regions": [
                {**r, "unlocked": r["id"] in open_regions,
                 "tier": world.town_tier(skills.get(r["skill"],
                                                    skillmod.SkillState(name="x")).mastery)}
                for r in world.REGIONS
            ],
            "bosses": [
                {**b, "cleared": b["id"] in self.state["cleared_bosses"],
                 "records": db.boss_history(self.conn, b["id"])}
                for b in world.BOSSES
            ],
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
            "grimoire": self.state["grimoire"],
            "active_encounter": self.state.get("encounter"),
            "interview": self.state.get("interview"),
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
            "pets": pets.catalogue(self.state["pets"]),
            "pet_hints": pets.undiscovered_hints(self._pet_evidence(),
                                                 self.state["pets"]["found"]),
            "dungeon": dungeon_view,
            "dungeons": [self._dungeon_card(d) for d in
                         dungeons.dungeons_for_region(player.get("region", ""))],
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
            "hero": items.hero_look(self.state["armor"], self.state["equipped"]),
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

    def _sealed_in_interview(self) -> dict | None:
        """One refusal for every overworld action. The modules refuse too, but
        the guarantee belongs at the door, not three rooms in."""
        if self.state.get("interview") or (
                self.encounter and self.encounter.mode == config.MODE_INTERVIEW):
            return finalexam.refuse("BUILD")
        return None

    # -- classes -----------------------------------------------------------
    def class_selection(self) -> dict:
        return {"selection": classes.selection_screen(),
                "chosen": (self.state.get("class") or {}).get("class", "")}

    def choose_class(self, class_id: str) -> dict:
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
        self.state["class"] = classes.new_state(class_id)
        self._sync_class_points()
        self._sync_caps()
        self.save()
        return {"ok": True, "class": class_id,
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
        pay = done.get("pay") or {}
        player = self.state["player"]
        player["xp"] += int(pay.get("xp", 0))
        player["gold"] += int(pay.get("gold", 0))
        player["level"] = world.level_for(player["xp"])
        player["title"] = world.title_for(player["level"])
        if pay.get("set_item"):
            item_id = pay["set_item"]
            if _item(item_id) and item_id not in self.state["inventory"]:
                self.state["inventory"].append(item_id)
                self.state["stats"]["items_found"] += 1
        consumable = pay.get("consumable")
        if consumable:
            key = consumable if isinstance(consumable, str) else consumable.get("id")
            count = 1 if isinstance(consumable, str) else int(
                consumable.get("count", 1))
            if key:
                self.state["consumables"][key] = \
                    self.state["consumables"].get(key, 0) + count
        story_reward = done.get("story") or {}
        for card in ([story_reward["card"]] if story_reward.get("card") else []):
            if card not in self.state["grimoire"]:
                self.state["grimoire"].append(card)
        for note in ([story_reward["codex"]] if story_reward.get("codex") else []):
            if note not in self.state["codex"]:
                self.state["codex"].append(note)
        if story_reward.get("title"):
            player["title"] = story_reward["title"]
        if done.get("chain_complete"):
            self.state["stats"]["chains_completed"] = int(
                self.state["stats"].get("chains_completed", 0)) + 1
        self._sync_caps()
        self.save()
        saves.autosave(self.conn, self.state, "quest_turned_in")
        return {"ok": True, **done,
                "world": progression.advance(self.state, self.skills,
                                             readiness=self._readiness())}

    # -- companions --------------------------------------------------------
    def pet_catalogue(self) -> dict:
        return {"pets": pets.catalogue(self.state["pets"]),
                "hints": pets.undiscovered_hints(self._pet_evidence(),
                                                 self.state["pets"]["found"]),
                "limit": pets.ACTIVE_LIMIT}

    def set_active_pets(self, pet_ids: list) -> dict:
        sealed = self._sealed_in_interview()
        if sealed:
            return finalexam.refuse("PET")
        chosen = pets.set_active(self.state["pets"], pet_ids or [])
        self.save()
        return {"ok": True, "active": chosen}

    def pet_intervention(self, signals: dict | None = None) -> dict | None:
        """Called as the player works. On a hit the engine charges it exactly the
        way use_hint charges — one hint used, and the rank clamped."""
        enc = self.encounter
        if not enc:
            return None
        region_id = self.state["player"].get("region", "")
        if not pets.available_in(enc.mode, region_id):
            return None
        if finalexam.sealed(enc, "PET"):
            return None
        problem = self.by_id[enc.problem_id]
        spoken = dict(enc.pet_spoken or {})
        event = pets.party_intervention(
            self.state["pets"].get("active", []),
            bonds=self.state["pets"].get("bond", {}),
            mode=enc.mode, region_id=region_id, signals=signals or {},
            context={"pattern": problem.pattern,
                     "family": problem.spaced_repetition_family},
            spoken=spoken)
        if not event:
            return None
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
            built, self.corpus, skills=self.skills,
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
        self.save()
        return {**result, "state": self.dungeon_state()}

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
        bound = (self.state["dungeon_map"].get(built.id) or {}).get(str(room.id))
        problem = self.by_id.get(bound)
        if problem is None:
            problem = dungeons.resolve_encounter(
                room.encounter, self.corpus, skills=self.skills,
                solved_ids=set(self.state["solved_ids"]),
                recent_ids=self.state["recent_ids"], rng=self._rng,
                attempts=int(run.get("attempts", {}).get(str(room.id), 0)))
        if problem is None:
            return {"error": "this room is empty"}
        payload = self.start_encounter(problem.id, reason="DUNGEON")
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
        return progression.world_map(self.state, self.skills,
                                     readiness=self._readiness())

    def region_view(self, region_id: str) -> dict:
        prog = progression.snapshot(self.state, self.skills,
                                    readiness=self._readiness())
        return progression.region_view(region_id, prog)

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
        self.state = merged
        self._reseed_world(self.state.get("world_seed") or 0)
        self._sync_class_points()
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
                skills=skills, schedule=schedule, corpus=self.corpus,
                profile=self.state["player"]["profile"]),
        }

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
        pool = [p for p in self.corpus
                # parenthesised deliberately: the previous form parsed as
                # `(matches_kind and not_boss) or matches_kind`, which let an
                # explicit kind smuggle boss encounters into ordinary selection
                if (kind is None or p.encounter_kind == kind)
                and p.difficulty != "BOSS"
                and (not tag or tag in p.tags)]
        if tag and not pool:
            pool = [p for p in self.corpus
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
        enc = Encounter(problem_id=problem_id, mode=mode, started_at=time.time(),
                        is_retest=is_retest, interval_days=interval_days,
                        boss_id=boss_id, interview_id=interview_id)
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
            "region": world.REGION_BY_ID.get(problem.realm, world.REGIONS[0]),
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
            "companions": ([] if not pets.available_in(
                enc.mode, self.state["player"].get("region", ""))
                else list(self.state["pets"].get("active", []))),
            "mana": self.state["player"]["mana"],
            "stamina": self.state["player"]["stamina"],
        }
        if interview:
            # Refuse to ship rather than hope. A bare `assert` would vanish under
            # python -O, and this is the one guarantee the whole mode rests on.
            leaks = finalexam.audit_payload(payload)
            if leaks:
                raise RuntimeError("exam payload leaks: %s" % "; ".join(leaks))
        return payload

    ENEMY_SPRITES = {
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
               explanation: str = "") -> dict:
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        problem = self.by_id[enc.problem_id]
        enc.submits += 1
        enc.declared_pattern = declared_pattern or enc.declared_pattern
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
        schedule = self.schedule
        family = problem.spaced_repetition_family or problem.pattern.lower()
        entry = schedule.get(family) or srsmod.ScheduleEntry(family=family)
        if problem.id not in entry.seen_problem_ids:
            entry.seen_problem_ids.append(problem.id)
            entry.seen_problem_ids = entry.seen_problem_ids[-30:]
        srsmod.schedule_after(entry, solved=solved, hints_used=enc.hints_used)
        schedule[family] = entry
        self._write_schedule(schedule)

        # -- tactical resolution: weaknesses struck, resistances hit
        fx = self.effects()
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
        player["gold"] += (xp // 3 + len(combat["crits"]) * 5) if solved else 0
        previous_level = player["level"]
        player["level"] = world.level_for(player["xp"])
        player["title"] = world.title_for(player["level"])
        levels_gained = max(0, player["level"] - previous_level)
        if levels_gained:
            self.state["unspent_points"] += levels_gained * items.POINTS_PER_LEVEL
        if solved and fx.get("mana_regen"):
            player["mana"] = min(player["mana_max"],
                                 player["mana"] + int(fx["mana_regen"]))

        damage_taken = 0
        if not solved:
            damage_taken = (config.STAMINA_LOSS_SYNTAX
                            if analysis.root_cause == "SYNTAX"
                            else config.STAMINA_LOSS_FAILED_SUBMIT)
            player["stamina"] = max(0, player["stamina"] - damage_taken)
        else:
            player["stamina"] = min(player["stamina_max"], player["stamina"] + 1)
            player["mana"] = min(player["mana_max"], player["mana"] + 2)

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
            boss_event = self._resolve_boss(enc, solved, rank, seconds)

        # -- training camp / remediation on failure
        camp = None
        remediation = None
        if not solved:
            camp = adaptive.training_camp(analysis.root_cause, skills, skill_name)
            remediation = adaptive.remediation_plan(self.corpus, analysis.root_cause,
                                                    problem, skills)
        stamina_zero = player["stamina"] <= 0
        if stamina_zero:
            # Stamina at zero is never a punishment. It routes to teaching.
            player["stamina"] = max(4, player["stamina_max"] // 3)
            camp = camp or adaptive.training_camp(analysis.root_cause or "PYTHON_RECALL",
                                                  skills, skill_name)

        # -- loot
        drop = None
        if solved:
            drop = items.roll_drop(
                difficulty=problem.difficulty, rank=rank,
                luck=fx.get("loot_luck", 0.0),
                is_boss=bool(enc.boss_id),
                skill=skill_name,
                owned=set(self.state["inventory"]),
                rng=self._rng,
                upgrade=int(enc.temp_effects.get("loot_upgrade", 0)),
                critical=bool(combat["crits"]))
            if drop:
                self._take_drop(drop)

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
        if enc.boss_id and solved:
            events.append("first_boss_cleared")
        if enc.is_retest and solved and enc.interval_days >= 7:
            events.append("retest_survived_7d")
        if armor_event and armor_event.get("repaired"):
            events.append("armor_repaired")
        if levels_gained:
            events.append("level_gained")
        if drop:
            events.append("loot_taken")
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
            "damage_taken": damage_taken,
            "next_retest_days": round(interval, 1) if solved else 0.5,
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
            "secrets": secrets,
            "levels_gained": levels_gained,
            "unspent_points": self.state["unspent_points"],
            "combo_saved": combo_saved,
            "gold": player["gold"],
            "enemy": enemy_dict,
        }
        result.update(world_result)
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
            "stats": {**self.state["stats"], **db.attempt_stats(self.conn)},
        }

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
               "incantations_learned": [], "companion_line": ""}
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

        if solved:
            self._autosave("encounter_cleared", readiness=ready)
        return out

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
        result = dungeons.clear_room(dungeon, run, enc.dungeon_room, solved=solved)
        self._resolved_dungeon = (dungeon, run)
        if solved:
            reward = result.get("reward") or {}
            self.state["player"]["xp"] += int(reward.get("xp", 0))
            self.state["player"]["gold"] += int(reward.get("gold", 0))
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
            if enc.dungeon_room == dungeon.boss_room:
                result["dungeon_cleared"] = self._close_dungeon(dungeon, run,
                                                                rank=rank, fx=fx)
                return result
        self.state[dungeons.STATE_KEY] = run
        return result

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
        problem = self.by_id[enc.problem_id]
        rungs = problem.hint_tree
        if not 1 <= level <= len(rungs):
            return {"error": "no such spell"}
        rung = rungs[level - 1]

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
        stuck = len(db.attempts_for(self.conn, problem.id)) >= 3
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
        }

    # -- memory shrines ----------------------------------------------------
    def shrine(self) -> dict:
        question, answers, skill = self._rng.choice(world.SHRINE_QUESTIONS)
        self.state["_shrine"] = {"answers": answers, "skill": skill,
                                 "asked_at": time.time()}
        self.save()
        return {"question": question, "seconds": 20, "skill": skill}

    def shrine_answer(self, text: str) -> dict:
        pending = self.state.pop("_shrine", None)
        if not pending:
            return {"error": "no shrine active"}
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
    def start_boss(self, boss_id: str) -> dict:
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
        rematch = self.state["boss_rematch"].get(boss_id, 0)
        # A rematch that replays the identical problem id is not a rematch. The
        # victory copy promised "the same boss, a different surface form", so the
        # rematch draws a different problem from the boss's own family, one rung
        # harder per tier, and only falls back to the authored one when the
        # family has nothing else.
        problem_id = self._rematch_problem(boss, rematch)
        payload = self.start_encounter(problem_id,
                                       mode=config.MODE_ADVENTURE,
                                       boss_id=boss_id, reason="BOSS")
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
            "hp_max": sum(1 for p in phases if p["demanded"]),
            "teaching_available": True,
            "affixes": list(spec.affixes) if spec is not None else [],
            "seal": seal.to_dict(),
            # Said before the first phase, not after the loss: the player is
            # told what this one takes away while they can still walk out.
            "herald": seal.herald,
            "ladder": self.boss_ladder(boss_id)["ladder"],
        }
        return payload

    def _rematch_problem(self, boss: dict, rematch: int) -> str:
        authored = boss["problem_id"]
        if not rematch:
            return authored
        problem = self.by_id.get(authored)
        if problem is None:
            return authored
        family = [p for p in self.corpus
                  if p.spaced_repetition_family == problem.spaced_repetition_family
                  and p.id != authored]
        if not family:
            return authored
        family.sort(key=lambda p: (adaptive.DIFF_ORDER.index(p.difficulty), p.id))
        return family[min(rematch - 1, len(family) - 1)].id

    def _resolve_boss(self, enc: Encounter, solved: bool, rank: str,
                      seconds: float) -> dict:
        boss = world.BOSS_BY_ID.get(enc.boss_id, {})
        db.record_boss(self.conn, enc.boss_id, seconds=seconds,
                       hints_used=enc.hints_used, rank=rank, defeated=solved)
        if solved:
            if enc.boss_id not in self.state["cleared_bosses"]:
                self.state["cleared_bosses"].append(enc.boss_id)
            self.state["boss_rematch"][enc.boss_id] = \
                self.state["boss_rematch"].get(enc.boss_id, 0) + 1
            run = self.state.get(dungeons.STATE_KEY)
            if run and run.get("boss", {}).get("id") == enc.boss_id:
                if run["dungeon"] not in self.state["dungeons_cleared"]:
                    self.state["dungeons_cleared"].append(run["dungeon"])
                self.state[dungeons.STATE_KEY] = None
            saves.autosave(self.conn, self.state, "boss_defeated")
            return {"id": enc.boss_id, "name": boss.get("name", ""),
                    "defeated": True, "rank": rank, "seconds": round(seconds, 1),
                    "rematch_tier": self.state["boss_rematch"][enc.boss_id],
                    "history": db.boss_history(self.conn, enc.boss_id)}
        # A boss is never a dead end: it enters its teaching phase, and the
        # ladder comes WITH the refusal rather than behind a route nothing calls.
        seal = finalexam.seal_for(mode=config.MODE_ADVENTURE, boss_id=enc.boss_id)
        return {
            "id": enc.boss_id, "name": boss.get("name", ""), "defeated": False,
            "teaching_phase": True,
            "mentor": (None if seal.blocks("MENTOR") else world.MENTORS.get(
                world.REGION_BY_ID.get(boss.get("region", ""), {}).get(
                    "mentor", "byte"))),
            "ladder": self.boss_ladder(enc.boss_id).get("ladder", []),
            "message": "The boss steps back. A mentor arrives. Nothing here is a wall.",
            "history": db.boss_history(self.conn, enc.boss_id),
        }

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
            [p for p in self.corpus if p.spaced_repetition_family == family],
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
                        profile: str | None = None) -> dict:
        spec = self.INTERVIEW_FORMATS.get(fmt)
        if not spec:
            return {"error": "unknown format"}
        profile = config.normalise_profile(
            profile or self.state["player"]["profile"])
        if fmt == "FINAL_EXAM":
            return self._start_exam(profile)
        weights = adaptive.PROFILE_PATTERN_WEIGHT.get(
            profile, adaptive.PROFILE_PATTERN_WEIGHT["GENERAL_SWE"])
        recent = set(self.state["recent_ids"][:15])

        chosen = []
        for want in spec["ladder"]:
            pool = [p for p in self.corpus
                    if p.difficulty == want
                    and p.entry.get("kind") in ("function", "class_ops")
                    and p.encounter_kind in ("CODE_BATTLE",)
                    and p.id not in recent
                    and p.id not in {c.id for c in chosen}]
            if not pool:
                continue
            pool.sort(key=lambda p: (weights.get(p.pattern, 1.0)
                                     * p.profile_weight.get(profile, 1.0)
                                     + self._rng.random()), reverse=True)
            chosen.append(pool[0])

        run = {
            "id": f"iv-{int(time.time())}", "format": fmt, "profile": profile,
            "problem_ids": [p.id for p in chosen], "index": 0,
            "started_at": time.time(), "minutes": spec["minutes"],
            "results": [],
        }
        self.state["interview"] = run
        self.save()
        return {
            "run": run, "label": spec["label"],
            "rules": [
                "No spells. No mentor. No pattern cards. No coach.",
                "The algorithm family is never named.",
                "Timer runs across the whole set, not per problem.",
                "State your approach before you write, in the box provided.",
                "Everything is recorded and analysed the moment it ends.",
            ],
            "problems": [{"id": p.id, "title": p.title, "difficulty": p.difficulty}
                         for p in chosen],
        }

    def _start_exam(self, profile: str) -> dict:
        exam = finalexam.compose(
            self.corpus, self.skills, profile=profile,
            history=finalexam.history_fingerprints(
                db.interview_history(self.conn, limit=50)),
            recent_ids=self.state["recent_ids"])
        payload = exam.to_dict()
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
        self.save()
        fmt = finalexam.interview_format()
        return {
            "run": run, "label": fmt["label"], "exam": payload,
            "rules": list(fmt["rules"]),
            "ladder": finalexam.ladder_view(),
            "problems": [{"id": pid, "title": self.by_id[pid].title,
                          "difficulty": self.by_id[pid].difficulty}
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

    def _exam_debrief(self, results: list, seconds_by_segment) -> dict | None:
        payload = self.state.get("exam")
        if not payload:
            return None
        exam = self._recover_exam(payload)
        if exam is None:
            return {"unavailable": True, "note":
                    "The exam was composed in an earlier process and could not "
                    "be rebuilt, so the per-question debrief is unavailable. "
                    "The score is still the measured one."}
        # debrief() documents `results` as exactly the shape interview_advance
        # already records, so it is passed through rather than rebuilt.
        return finalexam.debrief(
            exam, results, skills=self.skills,
            seconds_by_segment=seconds_by_segment or {},
            readiness=self._readiness(), corpus_index=self.by_id)

    def _recover_exam(self, payload: dict):
        """The composed Exam, from memory or rebuilt from its own seed.

        Exam has no from_dict and compose() is seeded, so the rebuild is exact
        when it works — and the fingerprint says whether it did rather than
        leaving the player with a debrief about a different exam.
        """
        cached = getattr(self, "_exam", None)
        if cached is not None and cached.fingerprint == payload.get("fingerprint"):
            return cached
        try:
            rebuilt = finalexam.compose(
                self.corpus, self.skills, profile=payload.get("profile"),
                seed=payload.get("seed"),
                format_id=payload.get("format_id", "THE_PRACTICAL"))
        except Exception:
            return None
        return rebuilt if rebuilt.fingerprint == payload.get("fingerprint") else None

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
        debrief = self._exam_debrief(results, seconds_by_segment)
        solved = sum(1 for r in results if r["solved"])
        total = max(len(run["problem_ids"]), 1)
        seconds = time.time() - run["started_at"]
        within = seconds <= run["minutes"] * 60
        score = round(100 * solved / total * (1.0 if within else 0.85))

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

        self.state["interview"] = None
        self.state["exam"] = None
        self._exam = None
        self._write_encounter(None)
        self.save()
        saves.autosave(self.conn, self.state, "session_end")

        return {
            "finished": True, "score": score, "solved": solved, "total": total,
            "debrief": debrief,
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
        self.state["incantation"] = {
            "encounter": encounter_id,
            "hp": {e.name: e.hp for e in ctx.enemies},
            "turn": 0, "casts": 0, "started_at": time.time(),
        }
        self.save()
        return self.incantation_view(ctx)

    def _incantation_context(self):
        run = self.state.get("incantation")
        if not run:
            return None
        ctx = bestiary.battle_context(run["encounter"],
                                      mode=config.MODE_ADVENTURE,
                                      hp=dict(run.get("hp") or {}))
        ctx.turn = int(run.get("turn", 0))
        return ctx

    def incantation_view(self, ctx=None) -> dict:
        run = self.state.get("incantation")
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
        return {
            "incantation": {
                "encounter": run["encounter"],
                "turn": ctx.turn,
                "timer_seconds": 0,       # adventure teaches; only exams are timed
                "enemies": [e.to_dict() for e in ctx.enemies],
                "bindings": ctx.bindings(),
                "demand": demand,
                "casts": run.get("casts", 0),
                "cleared": not ctx.living(),
            },
            "moveset": moves,
        }

    def incantation_cast(self, move_id: str, answers: dict) -> dict:
        run = self.state.get("incantation")
        if not run:
            return {"error": "no incantation battle running"}
        ctx = self._incantation_context()
        skills = self.skills
        tier = incantation.tier_for_move(self.state["moveset"], move_id, skills)
        result = incantation.cast(move_id, answers, ctx, tier=tier,
                                  seconds=time.time() - run["started_at"],
                                  streak=int(self.state["player"]["combo"]),
                                  timed=False)
        incantation.record_cast(self.state["moveset"], result)
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
        run["hp"] = {e.name: e.hp for e in ctx.enemies}
        run["turn"] = int(ctx.turn) + 1
        run["casts"] = int(run.get("casts", 0)) + 1
        cleared = not ctx.living()
        payload = {**result.to_dict(), "ok": result.correct,
                   **self.incantation_view(ctx)}
        if cleared:
            self.state["player"]["xp"] += 40 + 10 * len(ctx.enemies)
            self.state["incantation"] = None
            payload["cleared"] = True
        self.save()
        return payload

    def leave_incantation(self) -> dict:
        self.state["incantation"] = None
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
        self.save()
        return {"ok": True}

    def problem(self, problem_id: str, *, mode: str = config.MODE_ADVENTURE) -> dict:
        p = self.by_id.get(problem_id)
        return p.player_view(mode=mode) if p else {"error": "unknown problem"}

    def performance_history(self, problem_id: str | None = None) -> dict:
        return {
            "recent": db.recent_attempts(self.conn, limit=60),
            "problem": db.attempts_for(self.conn, problem_id) if problem_id else [],
            "bosses": db.boss_history(self.conn),
            "interviews": db.interview_history(self.conn),
            "stats": db.attempt_stats(self.conn),
        }

    def export(self) -> dict:
        return db.export_save(self.conn)

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
