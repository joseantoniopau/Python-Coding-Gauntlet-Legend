"""Combat tactics: enemy weaknesses, resistances, and the Probe.

This is where the game becomes strategic rather than merely gamified. An enemy's
weaknesses are *real properties of the problem*: the edge cases it hides and the
performance ceiling it enforces. To fight well you have to reason about how code
breaks — which is precisely the skill a timed practical is measuring.

The Probe is the headline mechanic. You spend a charge to assert "on THIS input,
the correct answer is THAT". The game runs the canonical solution and tells you
whether your model of the problem was right.

- Correct probe  -> you understood the spec. Damage, and the weakness is exposed:
                    passing its hidden trial now strikes critically.
- Wrong probe    -> you learn your mental model was wrong BEFORE you spend twenty
                    minutes implementing it. That is worth a charge.

No probe ever shows you an algorithm, a pattern name or a line of the solution.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import sandbox

# --------------------------------------------------------------------------
# Weakness taxonomy
# --------------------------------------------------------------------------

WEAKNESSES = {
    "EMPTY": {
        "name": "Empty Input", "icon": "∅", "colour": "#7ec8ff",
        "tell": "It flickers when nothing is offered to it.",
        "teach": "What does your function return when the input is empty?",
    },
    "SINGLE": {
        "name": "Lone Element", "icon": "1", "colour": "#8fd07a",
        "tell": "It stands very still when it is alone.",
        "teach": "A collection of one is the boundary most loops mishandle.",
    },
    "DUPLICATE": {
        "name": "Duplicates", "icon": "≡", "colour": "#e8c37d",
        "tell": "It splits into identical copies of itself.",
        "teach": "Sets collapse duplicates. Counters keep them. Which did you need?",
    },
    "NEGATIVE": {
        "name": "Negative Values", "icon": "−", "colour": "#ff6a7a",
        "tell": "Its shadow points the wrong way.",
        "teach": "Sliding windows and zero-seeded accumulators both break on negatives.",
    },
    "ZERO": {
        "name": "Zero", "icon": "0", "colour": "#c8a8ff",
        "tell": "There is a hole at its centre.",
        "teach": "Zero is falsy, divides badly, and makes `[:-0]` behave unexpectedly.",
    },
    "BOUNDARY": {
        "name": "Exact Boundary", "icon": "├", "colour": "#ff9d4a",
        "tell": "It presses itself flat against the edge of the arena.",
        "teach": "`>=` versus `>` at the limit is where most off-by-ones live.",
    },
    "SCALE": {
        "name": "Scale", "icon": "∞", "colour": "#ff6a7a",
        "tell": "It grows while you watch it.",
        "teach": "Correct is not the same as fast. Count the work per element.",
    },
    "UNIFORM": {
        "name": "All Identical", "icon": "=", "colour": "#9b96b8",
        "tell": "Every part of it is the same part.",
        "teach": "When everything is equal, does your comparison still make progress?",
    },
    "ORDER": {
        "name": "Adverse Order", "icon": "↯", "colour": "#a89aff",
        "tell": "It rearranges itself as you approach.",
        "teach": "Sorted, reversed, and shuffled inputs are three different tests.",
    },
}

RESISTANCES = {
    "BRUTE_FORCE": {
        "name": "Brute-Force Resistance", "icon": "⛊", "colour": "#ff6a7a",
        "tell": "Nested loops slide off its hide.",
        "teach": "This enemy carries a performance trial. A correct-but-quadratic "
                 "answer will not finish it.",
    },
    "AMBIGUITY": {
        "name": "Hidden Trials", "icon": "🔒", "colour": "#c8a8ff",
        "tell": "Most of it is not visible from here.",
        "teach": "More of this fight is hidden than shown. Visible trials are not the bar.",
    },
    "STATE": {
        "name": "Stateful", "icon": "⟳", "colour": "#7ec8ff",
        "tell": "It remembers what you did to it last turn.",
        "teach": "Operations are replayed in sequence. What survives between calls "
                 "matters as much as each call.",
    },
}

_NAME_SIGNALS = [
    ("empty", "EMPTY"), ("both empty", "EMPTY"), ("no ", "EMPTY"),
    ("single", "SINGLE"), ("lone", "SINGLE"), ("one item", "SINGLE"),
    ("duplicate", "DUPLICATE"), ("dupe", "DUPLICATE"), ("repeat", "DUPLICATE"),
    ("negative", "NEGATIVE"),
    ("zero", "ZERO"),
    ("boundary", "BOUNDARY"), ("exact", "BOUNDARY"), ("equals", "BOUNDARY"),
    ("exceed", "BOUNDARY"), ("off-by", "BOUNDARY"),
    ("all same", "UNIFORM"), ("identical", "UNIFORM"), ("uniform", "UNIFORM"),
    ("sorted", "ORDER"), ("reversed", "ORDER"), ("descending", "ORDER"),
    ("ascending", "ORDER"), ("rotat", "ORDER"), ("unsorted", "ORDER"),
]


def classify_test(test: dict) -> str | None:
    """Which weakness does this test probe? Read the name first, then the shape."""
    if test.get("kind") == "performance":
        return "SCALE"
    name = (test.get("name") or "").lower()
    for needle, key in _NAME_SIGNALS:
        if needle in name:
            return key
    return classify_args(test.get("args") or [])


def classify_args(args) -> str | None:
    """Shape-based classification, used for player-authored probes."""
    flat = []

    def walk(value, depth=0):
        if depth > 3:
            return
        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                flat.append(("empty_seq", None))
            elif len(value) == 1:
                flat.append(("single_seq", None))
            for v in value[:200]:
                walk(v, depth + 1)
            if len(value) >= 5000:
                flat.append(("huge", None))
            elif len(value) >= 2:
                vals = [v for v in value if isinstance(v, (int, float))]
                if len(vals) == len(value) and len(set(vals)) == 1:
                    flat.append(("uniform", None))
                elif len(vals) == len(value) and len(set(vals)) < len(vals):
                    flat.append(("dupes", None))
                if vals == sorted(vals) and len(vals) > 2:
                    flat.append(("sorted", None))
                if vals and vals == sorted(vals, reverse=True) and len(vals) > 2:
                    flat.append(("reversed", None))
        elif isinstance(value, str):
            if value == "":
                flat.append(("empty_seq", None))
            elif len(value) == 1:
                flat.append(("single_seq", None))
            elif len(set(value)) == 1:
                flat.append(("uniform", None))
            elif len(set(value)) < len(value):
                flat.append(("dupes", None))
        elif isinstance(value, bool):
            pass
        elif isinstance(value, (int, float)):
            if value == 0:
                flat.append(("zero", None))
            elif value < 0:
                flat.append(("negative", None))

    walk(args)
    kinds = {k for k, _ in flat}
    # priority order: the most instructive classification wins
    for key, weakness in (("huge", "SCALE"), ("empty_seq", "EMPTY"),
                          ("single_seq", "SINGLE"), ("uniform", "UNIFORM"),
                          ("dupes", "DUPLICATE"), ("negative", "NEGATIVE"),
                          ("zero", "ZERO"), ("reversed", "ORDER"),
                          ("sorted", "ORDER")):
        if key in kinds:
            return weakness
    return None


@dataclass
class Enemy:
    name: str
    sprite: str
    hp: int
    hp_max: int
    boss: bool = False
    taunt: str = ""
    colour: str = ""
    difficulty: str = "EASY"
    weaknesses: list = field(default_factory=list)     # [{key, name, icon, ...}]
    resistances: list = field(default_factory=list)
    exposed: list = field(default_factory=list)        # weaknesses revealed by probes

    def to_dict(self) -> dict:
        return {
            "name": self.name, "sprite": self.sprite, "hp": self.hp,
            "hp_max": self.hp_max, "boss": self.boss, "taunt": self.taunt,
            "colour": self.colour, "difficulty": self.difficulty,
            "weaknesses": self.weaknesses, "resistances": self.resistances,
            "exposed": self.exposed,
        }


def derive_enemy(problem, *, name: str, sprite: str, boss: bool = False,
                 taunt: str = "", colour: str = "") -> Enemy:
    """An enemy's weaknesses ARE the problem's edge cases. Nothing is invented."""
    seen = []
    for test in problem.edge_cases + problem.hidden_tests:
        key = classify_test(test)
        if key and key not in seen:
            seen.append(key)
    weaknesses = [{"key": k, **WEAKNESSES[k]} for k in seen[:3]]

    resistances = []
    if problem.perf_tests:
        resistances.append({"key": "BRUTE_FORCE", **RESISTANCES["BRUTE_FORCE"]})
    hidden_count = len(problem.hidden_tests) + len(problem.edge_cases)
    if hidden_count >= len(problem.visible_tests) * 2 and hidden_count >= 4:
        resistances.append({"key": "AMBIGUITY", **RESISTANCES["AMBIGUITY"]})
    if problem.entry.get("kind") == "class_ops":
        resistances.append({"key": "STATE", **RESISTANCES["STATE"]})

    hp = max(1, len(problem.all_tests))
    return Enemy(name=name, sprite=sprite, hp=hp, hp_max=hp, boss=boss,
                 taunt=taunt, colour=colour, difficulty=problem.difficulty,
                 weaknesses=weaknesses, resistances=resistances)


# --------------------------------------------------------------------------
# The Probe
# --------------------------------------------------------------------------

@dataclass
class ProbeResult:
    ok: bool
    correct: bool
    weakness: str | None
    weakness_hit: bool
    message: str
    true_value: str | None = None
    damage: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "correct": self.correct, "weakness": self.weakness,
            "weakness_hit": self.weakness_hit, "message": self.message,
            "true_value": self.true_value, "damage": self.damage, "error": self.error,
        }


def run_probe(problem, args, expected, *, effects: dict,
              already_exposed: list) -> ProbeResult:
    """Assert that on `args`, the correct answer is `expected`. Find out."""
    entry = problem.entry
    if entry.get("kind") not in ("function", "class_ops"):
        return ProbeResult(ok=False, correct=False, weakness=None, weakness_hit=False,
                           message="This encounter cannot be probed.",
                           error="unsupported")

    if entry.get("kind") == "class_ops":
        test = {"name": "probe", "ops": args.get("ops", []),
                "args": args.get("args", []), "expected": expected,
                "cmp": "exact", "hidden": False}
        shape_args = args.get("args", [])
    else:
        test = {"name": "probe", "args": args, "expected": expected,
                "cmp": problem.visible_tests[0].get("cmp", "exact")
                if problem.visible_tests else "exact",
                "hidden": False}
        shape_args = args

    report = sandbox.run_tests(problem.canonical_solution, entry, [test],
                               timeout_ms=2500, wall_seconds=10)

    if report.phase != "tests" or not report.tests:
        detail = (report.error or {}).get("message", "the probe could not be run")
        return ProbeResult(ok=False, correct=False, weakness=None, weakness_hit=False,
                           message=f"The probe fizzled: {detail}. Check the shape of "
                                   "your arguments against the signature.",
                           error=detail)

    outcome = report.tests[0]
    weakness = classify_args(shape_args)
    keys = [w["key"] for w in problem_weakness_keys(problem)]
    weakness_hit = bool(weakness and weakness in keys and weakness not in already_exposed)

    if outcome.status == "pass":
        damage = 2 if weakness_hit else 1
        if weakness_hit:
            info = WEAKNESSES[weakness]
            message = (f"Your model was right — and you struck {info['name']}. "
                       f"{info['tell']} The hidden trial in that category will now "
                       "land as a CRITICAL when your solution passes it.")
        elif weakness:
            article = "an" if WEAKNESSES[weakness]["name"][0] in "AEIOU" else "a"
            message = (f"Correct. That input is {article} {WEAKNESSES[weakness]['name']} case, "
                       "but this enemy does not guard that ground. Try another shape.")
        else:
            message = ("Correct — that is an ordinary case. Probes pay best when you "
                       "aim at a boundary the problem is hiding.")
        return ProbeResult(ok=True, correct=True, weakness=weakness,
                           weakness_hit=weakness_hit, message=message, damage=damage)

    # TWO EFFECTS, NOT ONE. These were ORed together, which meant anything that
    # had ever granted the weaker one handed over the stronger one's payload.
    #
    #   reveal_category    "probes name the failure category they would trigger"
    #   probe_reveal_value "a failed probe shows the true value"
    #
    # The Testsmith set grants both, so the set that this message points at
    # behaved correctly and the bug stayed invisible there. Everything holding
    # reveal_category ALONE was quietly an oracle: the Boundary Maul from rung
    # five and the Tracing Needle from rung four, whose own technique text says
    # "the category, never the input and never the expected value" — and then
    # the probe printed the expected value. That is the answer rule broken by a
    # boolean rather than by a decision, so the two are separated here and the
    # category is named as a category.
    reveal_value = bool(effects.get("probe_reveal_value"))
    name_category = bool(effects.get("reveal_category"))
    true_value = outcome.got if reveal_value else None
    hint = ""
    if weakness:
        hint = " " + WEAKNESSES[weakness]["teach"]
    message = ("Your model of the spec was wrong on that input. Better to learn it "
               "now than after twenty minutes of implementation." + hint)
    if name_category and weakness:
        # Same phrasing the passing branch above uses, because the category is
        # the same fact whether the probe landed or not.
        info = WEAKNESSES[weakness]
        article = "an" if info["name"][0] in "AEIOU" else "a"
        message += (f" That input is {article} {info['name']} case — which is "
                    "the category it falls in, and not what the answer on it is.")
    if not reveal_value:
        message += (" Equip something from the Testsmith line and a failed probe will "
                    "show you the true value.")
    return ProbeResult(ok=True, correct=False, weakness=weakness, weakness_hit=False,
                       message=message, true_value=true_value, damage=0)


def problem_weakness_keys(problem) -> list:
    seen = []
    for test in problem.edge_cases + problem.hidden_tests:
        key = classify_test(test)
        if key and key not in seen:
            seen.append(key)
    return [{"key": k} for k in seen[:3]]


# --------------------------------------------------------------------------
# Damage resolution
# --------------------------------------------------------------------------

def resolve_combat(report, problem, enemy: Enemy, *, exposed: list,
                   effects: dict, hints_used: int) -> dict:
    """Turn a test report into a combat outcome with real tactical consequences."""
    lines = []
    damage = 0
    crits = []
    resisted = []

    tests = report.tests if getattr(report, "tests", None) else []
    exposed_set = set(exposed or [])
    weakness_keys = {w["key"] for w in enemy.weaknesses}
    # the report preserves submission order, so index back into the real tests to
    # classify by SHAPE and not merely by the test's name
    source = problem.all_tests

    def classify_at(t):
        spec = source[t.index] if 0 <= t.index < len(source) else {
            "name": t.name, "kind": t.kind}
        return classify_test(spec)

    for t in tests:
        if not t.passed:
            continue
        base = 1
        key = classify_at(t)
        if key and key in weakness_keys:
            if key in exposed_set:
                base = 3
                crits.append({"key": key, "name": WEAKNESSES[key]["name"],
                              "trial": t.name})
            else:
                base = 2
        if t.kind == "performance":
            base = 3 if "BRUTE_FORCE" in {r["key"] for r in enemy.resistances} else 2
        damage += base

    for t in tests:
        if t.passed or t.kind != "performance":
            continue
        if "BRUTE_FORCE" in {r["key"] for r in enemy.resistances}:
            resisted.append({
                "key": "BRUTE_FORCE",
                "message": "Its hide turns your solution aside — correct, but too slow. "
                           "This enemy specifically resists brute force.",
            })

    crit_bonus = effects.get("crit_bonus", 0.0)
    xp_multiplier = 1.0 + (len(crits) * (0.25 + crit_bonus))
    if hints_used == 0 and crits:
        xp_multiplier += 0.15

    return {
        "damage": damage,
        "crits": crits,
        "resisted": resisted,
        "xp_multiplier": round(xp_multiplier, 2),
        "lines": lines,
    }


def tactical_brief(enemy: Enemy, exposed: list) -> dict:
    """What the TACTICS panel shows before a cast."""
    return {
        "weaknesses": [
            {**w, "exposed": w["key"] in (exposed or [])}
            for w in enemy.weaknesses
        ],
        "resistances": enemy.resistances,
        "advice": _advice(enemy, exposed),
    }


def _advice(enemy: Enemy, exposed: list) -> str:
    unexposed = [w for w in enemy.weaknesses if w["key"] not in (exposed or [])]
    if not enemy.weaknesses:
        return ("Nothing exotic here. Write it cleanly and cast — this one is about "
                "fluency, not tricks.")
    if unexposed:
        names = ", ".join(w["name"].lower() for w in unexposed)
        return (f"It guards {names}. Probe one of those before you cast: a correct "
                "probe exposes the weakness and turns that hidden trial into a "
                "critical strike.")
    if any(r["key"] == "BRUTE_FORCE" for r in enemy.resistances):
        return ("Every weakness is exposed. It still resists brute force — make sure "
                "your complexity is right before you cast.")
    return "Every weakness is exposed. Cast, and take the criticals."
