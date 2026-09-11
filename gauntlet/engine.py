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
from . import tactics
from . import skills as skillmod
from . import srs as srsmod
from . import world
from .corpus import ensure as ensure_corpus
from .corpus.schema import Problem


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

    def to_dict(self) -> dict:
        return asdict(self)


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
    "grimoire": [],
    "codex": [],
    "settings": {"music": True, "sfx": True, "reduced_motion": False,
                 "text_scale": 1.0, "high_contrast": False, "colorblind": False,
                 "crt": True},
    "skills": {},
    "schedule": {},
    "encounter": None,
    "interview": None,
    "daily": {"date": "", "quests": [], "completed": []},
    "stats": {"encounters": 0, "armor_repairs": 0, "shrines": 0,
              "hints_total": 0, "sessions": 0, "probes": 0, "probes_correct": 0,
              "crits": 0, "items_found": 0, "secrets": 0},
}


class Game:
    def __init__(self, *, db_path=None, corpus_path=None, rebuild: bool = False):
        self.conn = db.connect(db_path)
        self.corpus: list = ensure_corpus(corpus_path, rebuild=rebuild)
        self.by_id: dict = {p.id: p for p in self.corpus}
        self.state = self._load_or_create()
        self._rng = random.Random()

    # -- persistence -------------------------------------------------------
    def _load_or_create(self) -> dict:
        raw = db.load_state(self.conn)
        if raw is None:
            state = _deep_copy(DEFAULT_STATE)
            state["player"]["created_at"] = time.time()
            state["skills"] = {k: v.to_dict() for k, v in skillmod.new_skills().items()}
            db.save_state(self.conn, state)
            return state
        # forward-compatible: fill in anything a newer build added
        merged = _deep_copy(DEFAULT_STATE)
        _merge(merged, raw)
        for name in skillmod.SKILLS:
            merged["skills"].setdefault(name, skillmod.SkillState(name=name).to_dict())
        return merged

    def save(self) -> None:
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

    # -- build / loadout ---------------------------------------------------
    def effects(self, *, include_temp: bool = True) -> dict:
        enc = self.encounter
        temp = dict(enc.temp_effects) if (enc and include_temp) else {}
        return items.total_effects(self.state["equipped"], self.state["attributes"], temp)

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
            item = items.BY_ID.get(item_id)
            if item:
                equipped[slot] = item.to_dict()
        owned = []
        for item_id in self.state["inventory"]:
            item = items.BY_ID.get(item_id)
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
                self.state["equipped"][items.BY_ID[item_id].slot] = item_id
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
        item = items.BY_ID.get(item_id)
        if not item or item_id not in self.state["inventory"]:
            return {"error": "you do not carry that"}
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
            if enc.mode == config.MODE_INTERVIEW:
                return {"error": "sealed",
                        "message": "Items do not work in Interview Mode. That is the point."}
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
        if enc.mode == config.MODE_INTERVIEW:
            return 0
        return max(0, items.base_probe_charges(self.effects()) - enc.probes_used)

    def probe(self, args, expected, ops=None) -> dict:
        """Spend a charge to assert what the correct answer is on an input you choose."""
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if enc.mode == config.MODE_INTERVIEW:
            return {"error": "sealed",
                    "message": "Probes are a learning tool. Interview Mode measures "
                               "you without them."}
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
        }

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
                       kind: str | None = None) -> dict:
        skills = self.skills
        selection = adaptive.select_next(
            [p for p in self.corpus
             if (kind is None or p.encounter_kind == kind)
             and p.difficulty != "BOSS" or p.encounter_kind == kind],
            skills=skills, schedule=self.schedule,
            profile=self.state["player"]["profile"],
            solved_ids=set(self.state["solved_ids"]),
            recent_ids=self.state["recent_ids"],
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
        self.save()
        return self._encounter_payload(problem, enc, reason=reason)

    def _encounter_payload(self, problem: Problem, enc: Encounter,
                           reason: str = "") -> dict:
        view = problem.player_view(mode=enc.mode)
        enemy_dict = self._enemy_for(problem, enc.exposed)
        enemy_obj = tactics.Enemy(**{k: v for k, v in enemy_dict.items()
                                     if k in ("name", "sprite", "hp", "hp_max", "boss",
                                              "taunt", "colour", "difficulty",
                                              "weaknesses", "resistances", "exposed")})
        interview = enc.mode == config.MODE_INTERVIEW
        skills = self.skills
        skill_name = skillmod.PATTERN_TO_SKILL.get(problem.pattern, "PYTHON")
        history = db.attempts_for(self.conn, problem.id)
        return {
            "problem": view,
            "encounter": enc.to_dict(),
            "reason": reason,
            "mode": enc.mode,
            "interview_locked": enc.mode == config.MODE_INTERVIEW,
            "enemy": enemy_dict,
            "tactics": ({} if interview
                        else tactics.tactical_brief(enemy_obj, enc.exposed)),
            "probe_charges": self.probes_remaining(),
            "loadout": {} if interview else self.loadout(),
            "region": world.REGION_BY_ID.get(problem.realm, world.REGIONS[0]),
            "mentor": world.MENTORS.get(
                world.REGION_BY_ID.get(problem.realm, {}).get("mentor", "byte")),
            "skill": skill_name if enc.mode != config.MODE_INTERVIEW else "",
            "skill_state": (skills[skill_name].to_dict()
                            if enc.mode != config.MODE_INTERVIEW
                            and skill_name in skills else None),
            "attempts_before": len(history),
            "best_time": db.best_time(self.conn, problem.id),
            "hint_count": len(problem.hint_tree) if enc.mode != config.MODE_INTERVIEW else 0,
            "mana": self.state["player"]["mana"],
            "stamina": self.state["player"]["stamina"],
        }

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
        if enc and enc.mode == config.MODE_INTERVIEW:
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

        # -- skills
        skillmod.apply_outcome(
            skills[skill_name], solved=solved, difficulty=problem.difficulty,
            hints_used=enc.hints_used, seconds=seconds,
            target_seconds=problem.target_seconds, first_try=first_try,
            is_retest=enc.is_retest, interval_days=enc.interval_days, mode=enc.mode)
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
        self._write_skills(skills)

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
        self.state["stats"]["encounters"] += 1

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
        secrets = self._check_secrets(problem, enc, solved, rank, combat, report)

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

        history = db.attempts_for(self.conn, problem.id)
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
            "coach": {"available": reply.available, "questions": reply.questions,
                      "analysis": reply.analysis, "next_steps": reply.next_steps,
                      "reveal_solution": reply.reveal_solution},
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
            "skill": skill_name if enc.mode != config.MODE_INTERVIEW else "",
            "skill_state": (skills[skill_name].to_dict()
                            if enc.mode != config.MODE_INTERVIEW else None),
            "level": player["level"], "title": player["title"],
            "canonical_solution": (problem.canonical_solution
                                   if (solved or reply.reveal_solution)
                                   and enc.mode != config.MODE_INTERVIEW else None),
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
        if extra:
            result.update(extra)

        if solved or enc.mode == config.MODE_INTERVIEW:
            self._write_encounter(None)
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

    def _award_secret(self, secret_id: str) -> dict | None:
        if secret_id in self.state["secrets_found"]:
            return None
        secret = items.SECRET_BY_ID.get(secret_id)
        if not secret:
            return None
        self.state["secrets_found"].append(secret_id)
        self.state["stats"]["secrets"] += 1
        item = items.BY_ID.get(secret["item"])
        if item and item.id not in self.state["inventory"]:
            self.state["inventory"].append(item.id)
            self.state["stats"]["items_found"] += 1
        self._sync_caps()
        return {**secret, "item_detail": item.to_dict() if item else None}

    def _check_secrets(self, problem, enc, solved, rank, combat, report) -> list:
        """Hidden rewards, earned by doing something genuinely notable."""
        found = []

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

        return found

    def find_secret_location(self, region_id: str, x: int, y: int) -> dict:
        """The hidden alcove. Its position is derived from the region id, so the
        world is consistent — and the hint in the codex actually leads somewhere."""
        seed = sum(ord(c) for c in region_id)
        target = (34 + seed % 6, 6 + seed % 14)
        if region_id != "graph_wastes":
            return {"found": False}
        if abs(x - target[0]) <= 1 and abs(y - target[1]) <= 1:
            award = self._award_secret("secret_null_key")
            self.save()
            if award:
                return {"found": True, "secret": award}
            return {"found": True, "secret": None,
                    "message": "The alcove is already empty. You took what was here."}
        return {"found": False}

    def secret_target(self, region_id: str) -> dict:
        seed = sum(ord(c) for c in region_id)
        if region_id != "graph_wastes":
            return {}
        return {"x": 34 + seed % 6, "y": 6 + seed % 14}

    # -- hints -------------------------------------------------------------
    def use_hint(self, level: int) -> dict:
        enc = self.encounter
        if not enc:
            return {"error": "no active encounter"}
        if enc.mode == config.MODE_INTERVIEW:
            # The sacred rule. Enforced server-side, not merely hidden in the UI.
            return {"error": "sealed",
                    "message": "Spells do not work in Interview Mode. That is the point."}
        problem = self.by_id[enc.problem_id]
        rungs = problem.hint_tree
        if not 1 <= level <= len(rungs):
            return {"error": "no such spell"}
        rung = rungs[level - 1]

        player = self.state["player"]
        discount = self.effects().get("hint_discount", 0.0)
        cost = max(1, int(round(rung["mana"] * (1.0 - min(0.75, discount)))))
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
        payload = self.start_encounter(boss["problem_id"],
                                       mode=config.MODE_ADVENTURE,
                                       boss_id=boss_id, reason="BOSS")
        rematch = self.state["boss_rematch"].get(boss_id, 0)
        payload["boss"] = {
            **boss, "phases": world.BOSS_PHASES, "rematch": rematch,
            "hp_max": len(world.BOSS_PHASES),
            "teaching_available": True,
        }
        return payload

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
            return {"id": enc.boss_id, "name": boss.get("name", ""),
                    "defeated": True, "rank": rank, "seconds": round(seconds, 1),
                    "rematch_tier": self.state["boss_rematch"][enc.boss_id],
                    "history": db.boss_history(self.conn, enc.boss_id)}
        # A boss is never a dead end: it enters its teaching phase.
        return {
            "id": enc.boss_id, "name": boss.get("name", ""), "defeated": False,
            "teaching_phase": True,
            "mentor": world.MENTORS.get(
                world.REGION_BY_ID.get(boss.get("region", ""), {}).get("mentor", "byte")),
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
    }

    def start_interview(self, fmt: str = "GAUNTLET",
                        profile: str | None = None) -> dict:
        spec = self.INTERVIEW_FORMATS.get(fmt)
        if not spec:
            return {"error": "unknown format"}
        profile = profile or self.state["player"]["profile"]
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

    def finish_interview(self) -> dict:
        run = self.state.get("interview")
        if not run:
            return {"error": "no interview running"}
        results = run["results"]
        solved = sum(1 for r in results if r["solved"])
        total = max(len(run["problem_ids"]), 1)
        seconds = time.time() - run["started_at"]
        within = seconds <= run["minutes"] * 60
        score = round(100 * solved / total * (1.0 if within else 0.85))

        causes = [r["root_cause"] for r in results if r.get("root_cause")]
        knowledge = sum(1 for c in causes
                        if c in ("PATTERN_NOT_RECOGNIZED", "WRONG_ALGORITHM",
                                 "WRONG_DATA_STRUCTURE"))
        implementation = sum(1 for c in causes
                             if c in ("SYNTAX", "PYTHON_RECALL", "OFF_BY_ONE",
                                      "STATE_MANAGEMENT", "EDGE_CASE"))
        timing = sum(1 for c in causes
                     if c in ("TIME_PRESSURE", "INEFFICIENT_ALGORITHM"))

        db.record_interview(
            self.conn, profile=run["profile"], format=run["format"],
            problem_ids=",".join(run["problem_ids"]), score=score, solved=solved,
            total=total, seconds=seconds, detail=str(results))

        self.state["interview"] = None
        self._write_encounter(None)
        self.save()

        return {
            "finished": True, "score": score, "solved": solved, "total": total,
            "seconds": round(seconds), "within_time": within,
            "results": results,
            "breakdown": {"knowledge_failures": knowledge,
                          "implementation_failures": implementation,
                          "time_failures": timing},
            "verdict": self._interview_verdict(score, knowledge, implementation, timing),
            "coach_now_available": True,
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
        db.import_save(self.conn, payload)
        self.state = self._load_or_create()
        return {"ok": True}


def _deep_copy(value):
    import copy
    return copy.deepcopy(value)


def _merge(base: dict, incoming: dict) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
