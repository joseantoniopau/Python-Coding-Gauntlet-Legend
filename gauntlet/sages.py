"""The hidden sages, their gauntlets, and the secret arts they do not give away.

Sixteen sages. One per region, none in the castle, because the castle is the
exam hall and there are no teachers in an exam hall.

THE IDEA THE BRIEF WAS REACHING FOR
-----------------------------------
The request was for "a hidden sage/monk in each area" whose teaching "changes
based on the selected class". Read literally that is seventeen areas times six
classes = a hundred and two characters, ninety-six of whom nobody will ever
meet on a given save. So it is not read literally.

There is ONE hermit in the ruin. Six people walk in and six different people
walk out, because what a sage is able to teach you is decided by what you
arrived able to learn. The Berserker meets a scarred woman who will not let him
finish a sentence. The Analyst meets a quiet man with the same scar who lets him
finish every sentence and then asks one question. They are the same person. Two
players comparing notes find this out, which is the entire reason it is built
this way and not the other way.

Sixteen sages, six faces each: ninety-six FACES, sixteen PEOPLE, and one place
to look in each region.

THE RULE THAT DECIDES WHETHER THIS IS GOOD OR BROKEN
----------------------------------------------------
A secret art out-damages an ordinary one BECAUSE IT DEMANDS MORE PYTHON. Never
because finding it granted a bonus. There is no discovery multiplier in this
file and there is a test that says so — see `self_check()["no_discovery_bonus"]`.

What there is instead is a scale. `complexity()` reads a cast — the template the
player actually types, the holes they actually fill, the constructs, the depth,
and whether two separate ideas were composed into one line — and returns a
number. Measured against the catalogue as it stood when this was written: the
sixty-six ordinary moves score 2.25 to 12.50, mean 6.39; the ninety-six arts
here score 13.55 to 37.50, mean 24.50. The cheapest secret art is harder than
the hardest ordinary move, with nothing overlapping, and `self_check()` recomputes
that every run rather than trusting this paragraph.

    AND THAT SCALE IS THE WRONG ONE, WHICH IS WHY THESE ARTS DO NOT SHIP.

    `complexity()` is private to this file and nothing in the damage path
    consults it. `incantation.measure_complexity` is what turns a cast into a
    number, and on it sixty-nine of the ninety-six arts below demand LESS
    Python than `sift` — an ordinary chapter-two comprehension the player is
    already carrying. `art_stringwood_berserker` measures 11.65 against sift's
    25.75. On the ruler that pays, it is not a secret art; it is a weaker move
    with a better name.

    This was found by measuring rather than by reading, because the file was
    internally consistent the whole time: every claim it makes on its own scale
    is true, and the scale is decoration. `self_check()["real_ruler_separation"]`
    now reports the real number every run, `self_check()["ships"]` is False
    because of it, and `overlap_report()["decision"]` records the settlement —
    `gauntlet/arts.py` owns the line, this file owns the person, the place and
    the trial. The catalogue below is kept and unwired until `Face.art` is
    repointed; see the decision text for the exact edit.

`suggested_power()` turns the score into damage: POWER = COMPLEXITY + 4, a line
anchored on the catalogue's own two extremes, so an art's damage sits on the
same line as every ordinary move's damage, further along it. Ordinary powers
run 6 to 16; the arts run 18 to 42. This is a SECOND damage spine, parallel to
`incantation._damage_for`, and keeping two of them in step is exactly the work
that was not done — which is the mechanical reason the scale above drifted away
from the one that matters without anybody noticing.

That is the honest reason. The player who learned THE QUARTER TURN can rotate a
matrix in one typed line, which they could not do the day before, and the damage
is a consequence of that rather than a reward for exploring.

    A flat bonus attached to a discovery would make exploring better than
    studying, which is backwards for this game.

WHAT A CRUTCH IS, AND WHY AN ART IS NOT ONE
-------------------------------------------
`finalexam` seals fourteen crutches. A sage is a MENTOR and is sealed with the
mentors: you cannot find one, face one, or be spoken to by one inside a measured
run. See `available_in()`.

A secret art is not sealed, and the distinction matters. An art is an
incantation you know how to type. It is fluency, not help — the same category as
TALLY or CONVERGE, which nothing seals either. Sealing it would be sealing the
player's own hands. What the seal removes is everything that would tell you
WHICH art to reach for, and that is already covered by PATTERN and WEAKNESS_MAP.

THE FOUR RULES, AND WHERE EACH ONE IS ENFORCED
----------------------------------------------
  Nothing supplies an answer.   A gauntlet is five problems and a frame. The
      frame has never seen a test, a solution, or a hint tree; `self_check()`
      greps every authored line in this file for answer-shaped words.
  Nothing works in a measured run.   `available_in()` takes `finalexam`'s
      verdict as an argument rather than forming a second opinion about it.
  Mastery moves on graded evidence.   This module is pure. It evaluates and
      describes; granting is the caller's business, exactly as in `pets`.
  Learning never dead-ends.   Failing costs time and pride. `fail()` takes
      nothing away: no mastery, no gold, no gear, no progress, and it never
      closes a door. What it costs is THE TOLL — three more encounters cleared
      in that region before the sage will see you again — and the knowledge
      that the sage now knows which stage you die on. Every gauntlet is
      re-attemptable for ever, and a second attempt draws DIFFERENT problems
      from the same specifications, so a failure cannot be farmed into a
      memorised sequence.

INTEGRATION CONTRACT
--------------------
    sages.SAGES / sages.get(sage_id) / sages.for_region(region_id)
    sages.face(sage_id, class_id)               -> the Face that class meets
    sages.art(sage_id, class_id)                -> the Art it teaches
    sages.art_by_id(art_id)
    sages.complexity(cast)                      -> the scale, for any cast
    sages.suggested_power(cast)                 -> damage, on the catalogue line
    sages.moveset_requests(class_id="")         -> Incantation-shaped dicts
    sages.available_in(mode, region_id, sealed=)
    sages.discovery_progress(sage_id, evidence) -> rows + `met`
    sages.newly_found(evidence, already=)
    sages.undiscovered_hints(evidence, already=, limit=)
    sages.gauntlet(sage_id, class_id, attempt=) -> the trial, as specs
    sages.resolve_gauntlet(sage_id, class_id, problems=, attempt=)
    sages.new_state() / meet / begin / record_stage / fail / complete
    sages.may_attempt(state, sage_id, region_clears)
    sages.greeting(sage_id, class_id, state)
    sages.has_met / cleared_as / arts_known / evidence_patch
    sages.ladder_view()                         -> how the ladder runs, as data
    sages.self_test(art) / sages.self_test_all()
    sages.self_check(problems=None)          -> `ok` (this file's internal
                                                consistency), `real_ruler_holds`
                                                (the arts measured on
                                                incantation's scale) and
                                                `ships` (both)
    sages.overlap_report()["decision"]       -> which catalogue ships, and why

AN OVERLAP, NOW SETTLED
-----------------------
A parallel pass shipped `gauntlet/arts.py` while this was being written. It
declares that "`gauntlet/sages.py` owns WHO and WHAT THE TRIAL IS" and that it
owns the line itself — and it then authors its own ninety-six arts, its own
complexity scale, and its own sixteen places (`SANCTUMS`). This file was
briefed to author the arts as well, so both exist. THEY DO NOT COLLIDE
MECHANICALLY — the ids are `art_<region>_<class>` here and `art_<class>_<region>`
there — but shipping both would give every class thirty-two secret arts, which
is not the design.

SETTLED, ON MEASUREMENT, IN arts.py's FAVOUR. See `overlap_report()`, whose
`decision` carries the exact edit and whose `measured` block carries the two
numbers that decided it:

  * these ninety-six arts are ranked by this file's `complexity()`, and against
    `incantation.measure_complexity` — the function the damage actually calls —
    SIXTY-NINE OF THEM demand less Python than `sift`, an ordinary chapter-two
    line the player already has. arts.py's ninety-six clear that same bar by
    1.11x to 3.90x, because they were authored against it;
  * arts.py's are real `Incantation` and `Move` objects, so they are cast,
    tiered, faded, grooved, drawn and recorded by systems that already exist,
    rather than needing a second damage spine kept in step with the first.

The geography disagreement is closed: `arts.py` has retired its Null King's
Castle room and put one in Python Village, so its sixteen sanctums are now
exactly this file's sixteen regions. `arts.sage_bridge()` maps all ninety-six
rooms with nothing unmatched in either direction, and `arts.taught_here(region,
class_id)` is the lookup `Face.art` should become.

The catalogue below is KEPT AND UNWIRED until that repoint happens. Deleting
authored work while the ruler it would be re-measured on is itself being
repaired — see `arts.saturation_report()` — is the one order of operations that
cannot be undone.

NOTHING IS NEEDED FROM SOMEBODY ELSE FOR THE ARTS THAT SHIP
-----------------------------------------------------------
    incantation.BUILTIN_NAMES needs the word `next` added to it — for THESE
    arts, which are the ones being retired.

Seventeen of the lines below are built on `next(generator, default)` and layer 2
rejects `next` as an unbound name. It is declared as `sages.REQUIRED_BUILTINS`,
derived from the templates by `sages.builtins_used()`, and reported every run by
`self_check()["handover"]`. None of arts.py's ninety-six need it, so once
`Face.art` is repointed this ask goes away with the catalogue it belongs to.

WHAT IS STILL OWED, BY SOMEBODY ELSE, AND MATTERS
-------------------------------------------------
    incantation.SCORE_FULL is too small for a secret tier to exist in.

It clamps the measurement at raw 40. The ordinary catalogue never reaches it;
every secret art passes it. `arts.saturation_report()` measures the damage, and
`arts.handover()["score_full"]` names the edit. Until it is made, the arts that
ship out-demand ordinary lines at PROMPTED and are indistinguishable from each
other at RECALLED.

Pure stdlib. Importing this module builds tables and nothing else.
"""
from __future__ import annotations

import ast
import random
import re
from dataclasses import dataclass, field

from . import curriculum, elements, world

# ---------------------------------------------------------------------------
# Stable ids this module keys on
# ---------------------------------------------------------------------------
# `classes`, `incantation` and `movesets` are being rewritten alongside this
# file, so nothing here imports them at module scope. The six class ids and the
# hole-kind vocabulary are the stable surface, they are restated here as
# constants, and `self_check()` proves the restatement still matches by
# importing the real modules late and comparing.

CLASS_IDS: tuple = ("analyst", "berserker", "archivist", "warden", "artificer",
                    "seer")

# incantation.Hole kinds, restated. Same strings, same meanings.
ENEMY = "enemy"        # must name an enemy standing on the field
NAME = "name"          # must name any variable bound in this battle
MEMBER = "member"      # a method or builtin name, from a declared shortlist
LITERAL = "literal"    # a constant
EXPR = "expr"          # any expression whose free names are all bound
BINDER = "binder"      # a name the player INVENTS, bound by the line itself
HOLE_KINDS = (ENEMY, NAME, MEMBER, LITERAL, EXPR, BINDER)

# The castle has no sage. Everywhere else does.
NO_SAGE_REGIONS: tuple = ("null_kings_castle",)

# What failing costs: encounters cleared in that region before the sage will
# look up again. Time and pride. Not progress.
RETURN_TOLL = 3

# The capability a sage is. `finalexam.CRUTCHES` already has an entry for the
# mentor; a sage is a mentor who is hard to find, not a fifteenth crutch.
CAPABILITY = "MENTOR"

# Two regions say in their own description that nothing helps you there. A sage
# is not an intervention — it is a place with a person in it — but the Coliseum
# is a sand floor with a clock and the castle is the exam, so neither will have
# somebody stepping out of the wall mid-fight. The Coliseum sage is found
# BETWEEN bouts, which `available_in` is told about by the caller passing the
# encounter's seal, not by this module guessing.
SILENCED_REGIONS: tuple = ("null_kings_castle",)


# ===========================================================================
# The scale
# ===========================================================================
# The one piece of this file the combat pass has to agree with. Everything
# else here is content; this is the contract.
#
# A cast is scored on what the PLAYER PRODUCES, which is the template line and
# the holes in it. Body lines are the consequence the header drives — the
# player does not type them — so they are counted, but at a third of the
# weight of the line that was typed.
#
# `complexity()` duck-types. Anything with `.template`, `.holes`, `.body`,
# `.inner`, `.wrap` and `.example` scores, which means an `incantation.Incantation`
# and an `Art` go through the identical function. That is the whole reason the
# ranking can be called honest: it is not two scales that happen to agree.

W_HOLE = 1.25          # per distinct hole the player has to fill
W_REPEAT = 0.6         # per extra appearance of a hole already counted
W_INVENT = 0.75        # per BINDER: a name the player has to make up
W_CONSTRUCT = 1.0      # per distinct construct in the typed line
W_DEPTH = 2.0          # per level of nesting in the assembled cast
W_BODY = 1.0           # per authored line the header drives
W_COMPOSE = 2.5        # per ordinary incantation this cast subsumes

# Constructs worth counting. Deliberately curated: `Name` and `Load` appear in
# every line ever written and counting them would mean "longer is harder",
# which is the thing this scale exists not to say.
CONSTRUCTS: dict = {
    ast.GeneratorExp: "generator expression",
    ast.ListComp: "comprehension",
    ast.SetComp: "set comprehension",
    ast.DictComp: "dict comprehension",
    ast.Lambda: "lambda",
    ast.IfExp: "conditional expression",
    ast.BoolOp: "boolean composition",
    ast.Compare: "comparison",
    ast.Subscript: "indexing",
    ast.Slice: "slicing",
    ast.Call: "call",
    ast.Attribute: "method",
    ast.For: "loop",
    ast.While: "while",
    ast.If: "branch",
    ast.AugAssign: "in-place update",
    ast.Assign: "assignment",
    ast.Return: "return",
    ast.Assert: "assertion",
    ast.Tuple: "tuple",
    ast.Dict: "dict literal",
    ast.Set: "set literal",
    ast.List: "list literal",
    ast.Starred: "unpacking",
    ast.FunctionDef: "definition",
    ast.keyword: "keyword argument",
}

_NESTS = (ast.For, ast.While, ast.If, ast.FunctionDef, ast.With, ast.Try,
          ast.Lambda, ast.comprehension)

# Damage, from the score. POWER = COMPLEXITY + 4, and both numbers are anchored
# rather than chosen: the line runs through the catalogue's own two extremes.
# ADVANCE, the cheapest thing in the game, scores 2.25 and was authored at power
# 6; PAIRING, the dearest, scores 12.5 and was authored at 10, with 16 the
# highest power anywhere in the catalogue. A slope of one and a floor of four
# reproduces that span to within a point at both ends, and it has the further
# virtue of being a sentence a balance argument can actually be had about.
#
# `self_check()["scale_fit"]` re-fits the live catalogue every run and reports
# the drift, so the day somebody rewrites the ordinary powers, this says so.
# The constants are written as numbers rather than computed at import, because a
# balance constant that silently moves when somebody edits a spell is not a
# balance constant.
POWER_INTERCEPT = 4.0
POWER_SLOPE = 1.00


# ---------------------------------------------------------------------------
# The one thing this file needs from somebody else
# ---------------------------------------------------------------------------
# `incantation.BUILTIN_NAMES` is the whitelist layer 2 checks a cast's free
# names against. Sixteen Seer arts and one Analyst art are built on
# `next(generator, default)` — the first thing that matches, with the
# not-found case priced in advance — and `next` is not on that list.
#
# It is a one-token edit in a file this module does not own, so it is written
# down as a requirement, derived from the arts rather than typed from memory
# (`builtins_used()` reads it back off the templates), and checked every run by
# `self_check()["handover"]`. Until it is made, those seventeen arts fail layer
# 2 with "`next` is not bound in this battle", which is a confusing thing to
# say about a builtin.
REQUIRED_BUILTINS: frozenset = frozenset({"next"})


_HOLE_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _holes_in(text: str) -> tuple:
    seen, out = set(), []
    for match in _HOLE_RE.finditer(text or ""):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            out.append(name)
    return tuple(out)


def _fill(template: str, answers: dict) -> str:
    return _HOLE_RE.sub(lambda m: str(answers.get(m.group(1), "____")), template or "")


def _assembled(cast) -> str:
    """The cast as source, with its own worked example poured into the holes.

    The same assembly `incantation.build_cast_source` performs, minus the
    battle scaffolding, because the scaffolding is the engine's and is
    identical for every spell in the game.
    """
    answers = dict(getattr(cast, "example", {}) or {})
    template = getattr(cast, "template", "") or ""
    line = _fill(template, answers)
    body = [_fill(b, answers) for b in (getattr(cast, "body", ()) or ())]
    lines = [line]
    if template.rstrip().endswith(":"):
        lines += ["    " + b for b in (body or ["pass"])]
    else:
        lines += body
    if getattr(cast, "wrap", "") == "return":
        head = ["def __inner__():"]
        head += ["    " + _fill(x, answers) for x in (getattr(cast, "inner", ()) or ())]
        lines = head + ["    " + one for one in lines]
    return "\n".join(lines)


def _depth_of(tree) -> int:
    best = 0

    def walk(node, level):
        nonlocal best
        best = max(best, level)
        for child in ast.iter_child_nodes(node):
            walk(child, level + (1 if isinstance(child, _NESTS) else 0))

    walk(tree, 0)
    return best


def complexity(cast) -> dict:
    """How much Python this cast asks the player for. The scale, in one place.

    Returns the breakdown as well as the number, because a balance number
    nobody can argue with is a balance number nobody can fix.
    """
    template = getattr(cast, "template", "") or ""
    body = tuple(getattr(cast, "body", ()) or ())
    inner = tuple(getattr(cast, "inner", ()) or ())

    typed = _holes_in(template)
    occurrences = sum(template.count("{%s}" % name) for name in typed)
    repeats = max(0, occurrences - len(typed))

    holes = getattr(cast, "holes", ()) or ()
    invented = sum(1 for hole in holes
                   if getattr(hole, "kind", "") == BINDER
                   or (isinstance(hole, (tuple, list)) and hole and hole[0] == BINDER))

    source = _assembled(cast)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"holes": len(typed), "repeats": repeats, "invented": invented,
                "constructs": [], "depth": 0, "body_lines": len(body) + len(inner),
                "composes": len(getattr(cast, "composes", ()) or ()),
                "score": 0.0, "parses": False, "source": source}

    try:
        line_tree = ast.parse(_fill(template, dict(getattr(cast, "example", {}) or {}))
                              + ("\n    pass" if template.rstrip().endswith(":") else ""))
    except SyntaxError:
        line_tree = tree

    constructs = sorted({CONSTRUCTS[type(node)] for node in ast.walk(line_tree)
                         if type(node) in CONSTRUCTS})
    depth = _depth_of(tree)
    composes = tuple(getattr(cast, "composes", ()) or ())

    score = (W_HOLE * len(typed)
             + W_REPEAT * repeats
             + W_INVENT * invented
             + W_CONSTRUCT * len(constructs)
             + W_DEPTH * depth
             + W_BODY * (len(body) + len(inner))
             + W_COMPOSE * len(composes))

    return {"holes": len(typed), "repeats": repeats, "invented": invented,
            "constructs": constructs, "depth": depth,
            "body_lines": len(body) + len(inner), "composes": len(composes),
            "score": round(score, 2), "parses": True, "source": source}


def score_of(cast) -> float:
    return complexity(cast)["score"]


def suggested_power(cast) -> int:
    """Damage before tier, weakness and streak. On the catalogue's own line.

    This is the BASE. `incantation.measure_complexity` then reads what the
    player actually typed at the tier they typed it at and scales this by its
    `weight`, which is the right division of labour: this file says how much
    Python the art DEMANDS of anybody, that one says how much the person in
    front of it SUPPLIED. Neither of them knows or cares that the art was
    found rather than earned, and that is the design rule holding.
    """
    value = cast if isinstance(cast, (int, float)) else score_of(cast)
    return max(1, int(round(POWER_INTERCEPT + POWER_SLOPE * float(value))))


def builtins_used(casts=None) -> set:
    """Every builtin an art's own worked example leans on, read off the source.

    Derived, so that adding an art that reaches for `divmod` turns into a line
    in the handover report rather than into a layer-2 failure six weeks later.
    """
    import builtins as _builtins
    out = set()
    for one in (casts if casts is not None else ARTS):
        try:
            tree = ast.parse(_assembled(one))
        except SyntaxError:
            continue
        bound = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                bound.add(node.id)
            elif isinstance(node, ast.arg):
                bound.add(node.arg)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                    and node.id not in bound and hasattr(_builtins, node.id):
                out.add(node.id)
    return out


# ===========================================================================
# What a secret art is
# ===========================================================================
# Authored in `incantation.Incantation`'s own shape, the way `classes.py`
# authors its gear requests in `items.Item`'s shape: so the moveset pass can
# lift them across without a rewrite, and so nothing here constructs an
# Incantation and makes the catalogue stop being the single source of truth.
#
# `power` is not a field. It is DERIVED, every time, from `complexity()`. There
# is no line in this file where a human typed a damage number for an art, which
# is the mechanical form of the design rule at the top.

@dataclass(frozen=True)
class Art:
    id: str
    name: str                  # what the moveset lists, shouted
    class_id: str
    region: str
    skill: str
    chapter: int
    family: str                # incantation.FAMILIES: weakness and SRS key
    effect: str                # effect id the client animates
    template: str              # the line the player types, with {holes}
    holes: dict                # hole name -> (kind, role)
    idiom: str                 # the harder thing it asks for, named
    composes: tuple            # ordinary incantation ids this subsumes
    note: str                  # ONE line: when you reach for this
    demo: dict                 # practice bindings: name -> source expression
    example: dict              # a correct fill of every hole
    assertion: str             # post-cast truth test, templated like the line
    miss: str                  # what to say when it runs and nothing moved
    body: tuple = ()
    inner: tuple = ()
    wrap: str = ""
    imports: tuple = ()
    snapshot: dict = field(default_factory=dict)
    cost: int = 4
    par_seconds: float = 45.0

    @property
    def power(self) -> int:
        return suggested_power(self)

    @property
    def score(self) -> float:
        return score_of(self)

    def to_dict(self) -> dict:
        detail = complexity(self)
        return {
            "id": self.id, "name": self.name, "class": self.class_id,
            "region": self.region, "skill": self.skill, "chapter": self.chapter,
            "family": self.family, "effect": self.effect,
            "template": self.template,
            "holes": [{"name": n, "kind": spec[0], "role": spec[1],
                       "allowed": list(spec[2]) if len(spec) > 2 else []}
                      for n, spec in self.hole_specs().items()],
            "idiom": self.idiom, "composes": list(self.composes),
            "note": self.note, "cost": self.cost, "par_seconds": self.par_seconds,
            "power": self.power, "complexity": detail["score"],
            "constructs": detail["constructs"], "depth": detail["depth"],
        }

    def hole_specs(self) -> dict:
        """Every hole in the template, with its kind, its role, and — for a
        MEMBER hole — the shortlist of names that may legally fill it.

        Ordered by first appearance, which is the order the player fills them
        in and the order `incantation._inc` wants them.
        """
        out = {}
        for name in _holes_in(self.template):
            spec = self.holes.get(name) or ROLES.get(name)
            if spec is None:
                raise KeyError("%s: hole {%s} has no declaration" % (self.id, name))
            out[name] = tuple(spec)
        return out

    def request(self) -> dict:
        """The kwargs `incantation._inc` takes, ready to splat.

        This is the handover. The moveset pass calls `sages.moveset_requests()`
        and gets ninety-six of these; nothing else about this module needs
        reading to wire the arts into the catalogue.
        """
        return {
            "ident": self.id, "name": self.name, "template": self.template,
            "holes": self.hole_specs(), "skill": self.skill,
            "chapter": self.chapter,
            "note": self.note, "family": self.family, "effect": self.effect,
            "cost": self.cost, "power": self.power, "par": self.par_seconds,
            "body": self.body, "wrap": self.wrap, "inner": self.inner,
            "imports": self.imports, "demo": self.demo, "example": self.example,
            "snapshot": self.snapshot, "assertion": self.assertion,
            "miss": self.miss,
        }


# The shared hole vocabulary. Ninety-six arts reusing one set of slot names is
# not laziness, it is the point: {seq} means the same thing in the Village and
# on the eighth floor of the Tower, so a player who has learned one art has
# learned half the grammar of the next one.
ROLES: dict = {
    "out":     (NAME, "the name the result lands on"),
    "seq":     (ENEMY, "the ordered host you are reading"),
    "var":     (BINDER, "a name for one of them"),
    "item":    (BINDER, "a name for the one in hand"),
    "expr":    (EXPR, "what each one is worth"),
    "cond":    (EXPR, "the test that decides who counts"),
    "alt":     (EXPR, "what the ones that fail the test become"),
    "book":    (ENEMY, "the tally that keeps a number beside every name"),
    "memo":    (ENEMY, "the archive that charges you once"),
    "key":     (EXPR, "the thing being looked up"),
    "store":   (ENEMY, "the set that remembers without counting"),
    "stack":   (ENEMY, "the tower that will only speak from the top"),
    "grid":    (ENEMY, "the walled plane"),
    "graph":   (ENEMY, "the moot, and everything each name knows"),
    "dp":      (ENEMY, "the ledger of debts already paid"),
    "text":    (ENEMY, "the long utterance"),
    "node":    (NAME, "the one you are standing on"),
    "left":    (ENEMY, "the near warden"),
    "right":   (ENEMY, "the far warden"),
    "best":    (ENEMY, "the high-water mark"),
    "total":   (ENEMY, "the accumulator"),
    "i":       (BINDER, "a name for the position"),
    "j":       (BINDER, "a name for the other position"),
    "n":       (EXPR, "how many there are"),
    "k":       (EXPR, "the width you were given"),
    "target":  (EXPR, "the number you were sent for"),
    "limit":   (EXPR, "the bound you may not cross"),
    "floor":   (EXPR, "the least it may be and still count"),
    "base":    (EXPR, "what it is worth when there is nothing left"),
    "default": (EXPR, "what comes back when nothing matched"),
    "fallback": (EXPR, "what comes back when nothing matched"),
    "glue":    (LITERAL, "what goes between them"),
    "sep":     (LITERAL, "what they come apart on"),
    "bad":     (EXPR, "the one you will not accept"),
    "cap":     (EXPR, "how many it may hold"),
    "value":   (EXPR, "what it becomes"),
    "fn":      (NAME, "the function you are calling on the smaller thing"),
    "tool":    (BINDER, "a name for the thing you are about to build"),
    "p":       (BINDER, "a name for what the tool is handed"),
    "a":       (BINDER, "a name for the left-hand one"),
    "b":       (BINDER, "a name for the right-hand one"),
    "c":       (BINDER, "a name for the column"),
    "r":       (BINDER, "a name for the row"),
    "nb":      (BINDER, "a name for the neighbour"),
    "child":   (BINDER, "a name for the smaller one"),
    "children": (EXPR, "everything smaller that hangs off this"),
    "first":   (ENEMY, "the first host"),
    "second":  (ENEMY, "the second host"),
    "parts":   (ENEMY, "the pieces it came apart into"),
    "word":    (BINDER, "a name for one of the pieces"),
    "cases":   (ENEMY, "the inputs you were handed"),
    "want":    (ENEMY, "what each of them is supposed to answer"),
    "case":    (BINDER, "a name for the input in hand"),
    "step":    (EXPR, "how far it moves"),
    "coins":   (ENEMY, "every move you are allowed to make"),
    "spans":   (ENEMY, "the frames you have measured"),
    "seen":    (ENEMY, "the hollow set that forgets nothing"),
    "frontier": (ENEMY, "the spreading edge of the search"),
    "depth":   (NAME, "the function that measures how far down it goes"),
    "cost":    (NAME, "the function that prices a pair"),
    "method":  (MEMBER, "the method that does it",
                ("upper", "lower", "strip", "title", "split", "casefold")),
    "agg":     (MEMBER, "the aggregate that finishes it",
                ("max", "min", "sum", "len", "any", "all", "sorted")),
}


@dataclass(frozen=True)
class Face:
    """One of the six people the same sage turns out to be."""
    class_id: str
    name: str                  # what this class hears the sage called
    title: str                 # the register: Wizard, Warrior, and four others
    greeting: str              # the first thing said, the first time
    creed: str                 # what this class believes, in this sage's mouth
    trial: str                 # the demand this face adds to the proof
    returning: str             # what is said to somebody who failed and came back
    art: Art


@dataclass(frozen=True)
class Stage:
    """One rung of a gauntlet, as a query against the corpus plus a frame.

    Problems are named by SPECIFICATION, not by id. Ids drift as the corpus is
    resealed and regenerated, and a gauntlet that silently resolves to nothing
    is worse than one that resolves to a different problem of the right shape.
    `prefer` is a shortlist of real ids to try first, and `self_check()` reports
    how many of them are still live.
    """
    key: str
    label: str
    kind: str                  # corpus ENCOUNTER_KINDS
    difficulty: str            # curriculum.TIERS
    pattern: str = ""          # corpus PATTERNS, or "" for any
    realm: str = ""            # region id, or "" for any
    demands: str = ""          # what it is testing, in the game's words
    prefer: tuple = ()         # real problem ids, tried in order


@dataclass(frozen=True)
class Discovery:
    region: str
    where: str                 # the place, in prose, for the codex
    how: str                   # the deed, in prose, for the player
    needs: tuple               # the same deed, as data, for the evaluator
    first_words: str = ""


@dataclass(frozen=True)
class Sage:
    id: str
    region: str
    tier: int                  # 0 at the Village, 15 at the Coliseum
    unnamed: str               # what they are called when nobody is listening
    scar: str                  # the detail six players compare notes about
    blurb: str
    discovery: Discovery
    stages: tuple              # tuple[Stage], 3 to 5
    fail_lines: tuple          # one per stage, in order
    on_clear: str
    faces: tuple               # tuple[Face], one per CLASS_IDS, in that order

    @property
    def name(self) -> str:
        return self.unnamed

    def face(self, class_id: str) -> Face | None:
        for one in self.faces:
            if one.class_id == class_id:
                return one
        return None

    def to_dict(self, *, found: bool = True, class_id: str = "") -> dict:
        data = {
            "id": self.id, "region": self.region, "tier": self.tier,
            "region_name": world.REGION_BY_ID.get(self.region, {}).get("name", ""),
            "element": elements.affinity_for(self.region),
            "found": bool(found),
            "where": self.discovery.where, "how": self.discovery.how,
            "stages": len(self.stages),
            "difficulties": [s.difficulty for s in self.stages],
        }
        if not found:
            return data
        data.update({"scar": self.scar, "blurb": self.blurb,
                     "unnamed": self.unnamed})
        one = self.face(class_id) if class_id else None
        if one is not None:
            data.update({
                "name": one.name, "title": one.title, "greeting": one.greeting,
                "creed": one.creed, "trial": one.trial,
                "art": one.art.to_dict(),
            })
        return data


# ===========================================================================
# The ladder
# ===========================================================================
# Sixteen regions in world order, and the rung each one stands on. `tier` is
# the only number that decides how hard a sage is: it picks the gauntlet's
# difficulties, its stage count, the focus an art costs, the seconds a fluent
# cast takes, and — through the templates below being written longer as the
# tier rises — the complexity of the art itself.
#
#   tier 0-3    three stages, TUTORIAL to MEDIUM.   Arts of four or five holes:
#               one composition, one line, nothing nested. A beginner can hold
#               it in their head walking away from the ruin.
#   tier 4-11   four stages, EASY to HARD. Five or six holes, a real idiom —
#               a lambda key, a chained comparison, a generator inside a
#               comprehension — and two ordinary moves fused into one line.
#   tier 12-15  five stages, MEDIUM to ELITE. Seven to nine holes, nesting,
#               and three ordinary moves fused. The Tower's arts are lines
#               that would be a paragraph anywhere else.
#
# `self_check()["ladder"]` prints the resulting complexity per tier, so the
# claim above is a measurement rather than a promise.

REGION_LADDER: tuple = (
    # key,         region id,                tier, skill,            chapter, pattern,       family
    ("village",    "python_village",          0,  "PYTHON",          1,  "LANGUAGE",       "comprehension"),
    ("fields",     "fields_of_syntax",        1,  "PYTHON",          2,  "LANGUAGE",       "iterate"),
    ("highlands",  "hashmap_highlands",       2,  "HASH_MAP",        3,  "HASH_MAP"        , "counting"),
    ("stringwood", "stringwood_labyrinth",    3,  "STRING",          2,  "STRING",         "string"),
    ("caverns",    "array_caverns",           4,  "ARRAY",           1,  "ARRAY",          "index"),
    ("marsh",      "sliding_window_marsh",    5,  "SLIDING_WINDOW",  4,  "SLIDING_WINDOW", "window"),
    ("pass",       "twin_pointer_pass",       6,  "TWO_POINTER",     4,  "TWO_POINTER",    "pointer"),
    ("mines",      "stack_queue_mines",       7,  "STACK",           5,  "STACK",          "stack"),
    ("citadel",    "matrix_citadel",          8,  "MATRIX",          5,  "MATRIX",         "matrix"),
    ("forest",     "recursive_forest",        9,  "RECURSION",       6,  "RECURSION",      "recurse"),
    ("canopy",     "binary_tree_canopy",     10,  "TREE",            7,  "TREE",           "tree"),
    ("wastes",     "graph_wastes",           11,  "GRAPH",           7,  "BFS",            "graph"),
    ("ruins",      "dp_ruins",               12,  "DP",              8,  "DP",             "dp"),
    ("dungeon",    "debugging_dungeon",      13,  "DEBUGGING",       9,  "DEBUGGING",      "testing"),
    ("tower",      "complexity_tower",       14,  "BIG_O",           8,  "COMPLEXITY",     "search"),
    ("coliseum",   "coding_coliseum",        15,  "SPEED",          10,  "",               "extreme"),
)

REGION_META: dict = {row[0]: {"key": row[0], "region": row[1], "tier": row[2],
                              "skill": row[3], "chapter": row[4],
                              "pattern": row[5], "family": row[6]}
                     for row in REGION_LADDER}
KEY_BY_REGION: dict = {row[1]: row[0] for row in REGION_LADDER}


def _cost_for(tier: int) -> int:
    """Focus per cast. Four at the bottom, seven at the top."""
    return 4 + tier // 6


def _par_for(tier: int) -> float:
    """The seconds a fluent cast of an art takes. Longer lines take longer."""
    return round(38.0 + 2.4 * tier, 1)


ARTS: list = []


def _art(region_key: str, class_id: str, name: str, template: str, *,
         demo: dict, example: dict, assertion: str, composes: tuple,
         idiom: str, note: str, miss: str, holes: dict | None = None,
         body: tuple = (), inner: tuple = (), wrap: str = "",
         imports: tuple = (), snapshot: dict | None = None,
         family: str = "") -> Art:
    """Authoring shorthand. Ids, skills, chapters, costs and POWER are derived.

    There is no `power` parameter, on purpose, and adding one would be the
    single edit that breaks the design rule this file was written to hold.
    """
    meta = REGION_META[region_key]
    art = Art(
        id="art_%s_%s" % (region_key, class_id),
        name=name, class_id=class_id, region=meta["region"], skill=meta["skill"],
        chapter=meta["chapter"], family=family or meta["family"],
        effect="art_%s_%s" % (class_id, region_key),
        template=template, holes=dict(holes or {}), idiom=idiom,
        composes=tuple(composes), note=note, demo=dict(demo),
        example=dict(example), assertion=assertion, miss=miss,
        body=tuple(body), inner=tuple(inner), wrap=wrap, imports=tuple(imports),
        snapshot=dict(snapshot or {}), cost=_cost_for(meta["tier"]),
        par_seconds=_par_for(meta["tier"]),
    )
    ARTS.append(art)
    return art


# ===========================================================================
# The secret arts
# ===========================================================================
# Ninety-six. Six structural signatures, one per class, instantiated sixteen
# times against what each region physically is.
#
# The signature is the class, made mechanical. It is not a colour on top of a
# shared template — a Berserker art and an Analyst art of the same region parse
# to different shapes, ask for different holes, and fail in different places.
#
#   ANALYST    THE DECLARED CAST     one statement, an aggregate over a
#                                    generator with a condition. Everything is
#                                    said at once and nothing is iterated by
#                                    hand, which is what the class believes.
#   BERSERKER  THE TWO-HANDED STRIKE tuple assignment: two names updated in one
#                                    statement, each from an expression that
#                                    reads the other's old value. It swings
#                                    twice and does not wait to see the first
#                                    land.
#   ARCHIVIST  THE PAID-ONCE LEDGER  a conditional expression over a cache:
#                                    look up, and on a miss compute and file in
#                                    the same breath. Nothing is ever asked for
#                                    twice.
#   WARDEN     THE WARD              a block header carrying a compound
#                                    boundary — a chained comparison and two
#                                    more clauses — with the operation
#                                    underneath. The guard is written before
#                                    the thing it guards.
#   ARTIFICER  THE FORGED KEY        a tool built and used inside one line: a
#                                    lambda handed straight to the thing that
#                                    needs it. Build it once, properly.
#   SEER       THE READ              a search for the first place two things
#                                    stopped agreeing: destructuring inside
#                                    enumerate inside zip, with a default.
#                                    Nothing is written; something is found.

# -- ANALYST: the declared cast --------------------------------------------

_art("village", "analyst", "THE COUNTED WORD",
     "{out} = sum({expr} for {var} in {seq} if {cond})",
     idiom="a generator expression consumed by an aggregate",
     composes=("bind", "sift"),
     note="When what you want is a number over a filtered host, say it once.",
     demo={"nums": "[3, 1, 4, 1, 5]", "total": "0"},
     example={"out": "total", "expr": "1", "var": "n", "seq": "nums",
              "cond": "n > 2"},
     snapshot={"before": "{out}"},
     assertion="{out} == sum({expr} for {var} in {seq} if {cond}) "
               "and {out} != __b__['before']",
     miss="It counted, and counted the same thing it already held."),

_art("fields", "analyst", "THE TWO-WAY MIRROR",
     "{out} = [{expr} if {cond} else {alt} for {var} in {seq}]",
     idiom="a conditional expression nested inside a comprehension",
     composes=("mirror", "sift"),
     note="Every one of them becomes something. The test picks which something.",
     demo={"nums": "[1, 2, 3, 4]", "labels": "[]"},
     example={"out": "labels", "expr": "'even'", "cond": "n % 2 == 0",
              "alt": "'odd'", "var": "n", "seq": "nums"},
     assertion="{out} == [{expr} if {cond} else {alt} for {var} in {seq}] "
               "and len({out}) == len({seq})",
     miss="Some of them fell out. A mirror keeps the count; a sieve does not."),

_art("highlands", "analyst", "THE DECLARED PLURALITY",
     "{out} = max(({expr}, {var}) for {var}, {expr} in {book}.items() if {expr} >= {floor})",
     holes={"var": (BINDER, "a name for the key"),
            "expr": (BINDER, "a name for the number beside it")},
     idiom="a tally unpacked into a tuple and ranked without a loop",
     composes=("tally", "greatest"),
     note="The commonest thing, and its name, out of a tally, in one line.",
     demo={"counts": "{'a': 3, 'b': 1, 'c': 3}", "best": "(0, '')"},
     example={"out": "best", "var": "w", "expr": "n", "book": "counts",
              "floor": "2"},
     assertion="{out} == max(({expr}, {var}) for {var}, {expr} in {book}.items() "
               "if {expr} >= {floor})",
     miss="It read the keys and never the counts. `.items()` hands you both."),

_art("stringwood", "analyst", "THE CHOSEN SPEECH",
     "{out} = {glue}.join({word} for {word} in {parts} if {cond})",
     idiom="a filtered generator handed straight to join",
     composes=("weave", "sift"),
     note="Say only the parts worth saying, and say them joined.",
     demo={"parts": "['the', 'rain', 'it', 'raineth']", "line": "''"},
     example={"out": "line", "glue": "'-'", "word": "w", "parts": "parts",
              "cond": "len(w) > 2"},
     snapshot={"before": "{out}"},
     assertion="{out} == {glue}.join({word} for {word} in {parts} if {cond}) "
               "and {out} != __b__['before']",
     miss="It joined nothing to nothing. Check what survived the test."),

_art("caverns", "analyst", "THE NAMED POSITION",
     "{out} = max(range(len({seq})), key=lambda {i}: {seq}[{i}])",
     idiom="a key function over positions rather than over values",
     composes=("march", "greatest", "reach"),
     note="When you need WHERE the largest is and not what it is.",
     demo={"nums": "[3, 1, 4, 1, 5, 9, 2]", "at": "0"},
     example={"out": "at", "seq": "nums", "i": "k"},
     assertion="{out} == max(range(len({seq})), key=lambda {i}: {seq}[{i}]) "
               "and {seq}[{out}] == max({seq})",
     miss="That is the value. The caverns number their alcoves; bring back "
          "a number."),

_art("marsh", "analyst", "THE WHOLE MARSH AT ONCE",
     "{out} = max(sum({seq}[{i}:{i} + {k}]) for {i} in range(len({seq}) - {k} + 1))",
     idiom="a slice built from an index inside an aggregate over a range",
     composes=("sever", "toll", "greatest"),
     note="Every frame of one width, measured, without the frame ever moving.",
     demo={"nums": "[2, 1, 5, 1, 3, 2]", "best": "0", "width": "3"},
     example={"out": "best", "seq": "nums", "i": "s", "k": "width"},
     snapshot={"before": "{out}"},
     assertion="{out} == max(sum({seq}[{i}:{i} + {k}]) "
               "for {i} in range(len({seq}) - {k} + 1)) "
               "and {out} > __b__['before']",
     miss="The last frame ran off the end, or never started. Count the starts."),

_art("pass", "analyst", "BOTH ENDS AT ONCE",
     "{out} = [({seq}[{i}], {seq}[{n} - 1 - {i}]) for {i} in range({n} // 2)]",
     idiom="two indices derived from one, walking toward each other",
     composes=("march", "reach", "swap"),
     note="Pair the near with the far without either lantern taking a step.",
     demo={"nums": "[1, 2, 3, 4, 5, 6]", "pairs": "[]", "count": "6"},
     example={"out": "pairs", "seq": "nums", "i": "k", "n": "count"},
     assertion="{out} == [({seq}[{i}], {seq}[{n} - 1 - {i}]) "
               "for {i} in range({n} // 2)] and len({out}) == {n} // 2",
     miss="The middle one got paired with itself, or got lost. Halve the range."),

_art("mines", "analyst", "NOTHING ABOVE IT",
     "{out} = [{i} for {i} in range(len({stack})) "
     "if all({stack}[{i}] >= {stack}[{j}] for {j} in range({i}))]",
     holes={"j": (BINDER, "a name for everything already below it")},
     idiom="a generator expression nested inside a comprehension",
     composes=("march", "peek", "sift"),
     note="Every cart nothing taller was ever stacked on top of.",
     demo={"stack": "[2, 1, 5, 4, 6]", "peaks": "[]"},
     example={"out": "peaks", "stack": "stack", "i": "a", "j": "b"},
     assertion="{out} == [{i} for {i} in range(len({stack})) "
               "if all({stack}[{i}] >= {stack}[{j}] for {j} in range({i}))] "
               "and len({out}) >= 1",
     miss="Nothing survived. The first one has nothing below it and always "
          "qualifies."),

_art("citadel", "analyst", "THE QUARTER TURN",
     "{out} = [[{grid}[{n} - 1 - {c}][{r}] for {c} in range({n})] "
     "for {r} in range({n})]",
     holes={"c": (BINDER, "a name for the column you are reading down"),
            "r": (BINDER, "a name for the row you are writing")},
     idiom="a comprehension inside a comprehension, with the indices crossed",
     composes=("cell", "mirror", "march"),
     note="The whole floor plan, turned ninety degrees, in one statement.",
     demo={"grid": "[[1, 2, 3], [4, 5, 6], [7, 8, 9]]", "turned": "[]",
           "side": "3"},
     example={"out": "turned", "grid": "grid", "n": "side", "c": "y", "r": "x"},
     assertion="{out} == [[{grid}[{n} - 1 - {c}][{r}] for {c} in range({n})] "
               "for {r} in range({n})] and len({out}) == {n}",
     miss="That is the transpose. A transpose is half a turn of the wrist and "
          "the Golem knows the difference."),

_art("forest", "analyst", "WHAT THE SMALLER CALL FOUND",
     "{out} = {base} if not {children} else {expr} + sum({fn}({child}) for {child} in {children})",
     idiom="a base case and a recursive combine, stated as one expression",
     composes=("floor", "descend", "unfold"),
     note="The whole shape of recursion: the floor, and what you do with what "
          "came back.",
     demo={"kids": "[1, 2]", "total": "0", "weight": "5", "size": "lambda t: 1"},
     example={"out": "total", "base": "0", "children": "kids", "expr": "weight",
              "fn": "size", "child": "c"},
     snapshot={"before": "{out}"},
     assertion="{out} == ({base} if not {children} else {expr} + "
               "sum({fn}({child}) for {child} in {children})) "
               "and {out} != __b__['before']",
     miss="It returned the floor with children still standing, or walked past "
          "an empty one."),

_art("canopy", "analyst", "THE HEIGHT OF IT",
     "{out} = 1 + max(({fn}({child}) for {child} in ({node}.left, {node}.right) "
     "if {child}), default={base})",
     imports=("from types import SimpleNamespace as Node",),
     idiom="a generator over both branches with a default for the empty case",
     composes=("pluck", "branch", "descend"),
     note="Both forks measured, the empty fork priced, and one added for here.",
     demo={"node": "Node(val=5, left=Node(val=3, left=None, right=None), "
                   "right=None)",
           "high": "0", "height": "lambda t: 0 if t is None else 1"},
     example={"out": "high", "fn": "height", "child": "kid", "node": "node",
              "base": "-1"},
     snapshot={"before": "{out}"},
     assertion="{out} == 1 + max(({fn}({child}) "
               "for {child} in ({node}.left, {node}.right) if {child}), "
               "default={base}) and {out} != __b__['before']",
     miss="A missing branch is not a branch of height zero, and max() of "
          "nothing is not zero either."),

_art("wastes", "analyst", "EVERY ROAD ALREADY WALKED",
     "{out} = [{node} for {node} in {graph} "
     "if all({nb} in {seen} for {nb} in {graph}[{node}])]",
     holes={"node": (BINDER, "a name for the ruin you are standing in")},
     idiom="a membership test over every neighbour, inside a comprehension",
     composes=("expand", "probe", "sift"),
     note="The ruins with nothing left to reach. Frontier arithmetic, said once.",
     demo={"graph": "{'a': ['b'], 'b': [], 'c': ['d']}", "seen": "{'b'}",
           "done": "[]"},
     example={"out": "done", "node": "v", "graph": "graph", "nb": "w",
              "seen": "seen"},
     assertion="{out} == [{node} for {node} in {graph} "
               "if all({nb} in {seen} for {nb} in {graph}[{node}])]",
     miss="A ruin with no roads at all has every road walked. That is not a "
          "bug, that is `all` of an empty thing."),

_art("ruins", "analyst", "THE WHOLE ROW IN ONE BREATH",
     "{out} = max(({dp}[{n} - {c}] + {value}) for {c} in {coins} if {c} <= {n})",
     holes={"n": (EXPR, "how far along the ledger you are"),
            "c": (BINDER, "a name for one of the moves")},
     idiom="a transition over every legal move, aggregated without a loop",
     composes=("table", "transition", "greatest"),
     note="One cell of the ledger, paid from every cell that could reach it.",
     demo={"dp": "[0, 1, 1, 2, 2]", "coins": "[1, 3]", "best": "0", "at": "4"},
     example={"out": "best", "dp": "dp", "n": "at", "c": "move", "value": "1",
              "coins": "coins"},
     assertion="{out} == max(({dp}[{n} - {c}] + {value}) "
               "for {c} in {coins} if {c} <= {n})",
     miss="A move longer than the distance walks off the front of the ledger. "
          "The condition is not decoration."),

_art("dungeon", "analyst", "EVERY FAILING CASE, NAMED",
     "{out} = [({i}, {case}) for {i}, {case} in enumerate({cases}) "
     "if {fn}({case}) != {want}[{i}]]",
     idiom="enumerate destructured, a call, and a lookup by the same index",
     composes=("numbering", "witness", "sift"),
     note="Not that it is broken. Which inputs break it, and where they sit.",
     demo={"cases": "[1, 2, 3]", "want": "[2, 4, 4]", "broken": "lambda v: v + 1",
           "failures": "[]"},
     example={"out": "failures", "i": "k", "case": "x", "cases": "cases",
              "fn": "broken", "want": "want"},
     assertion="{out} == [({i}, {case}) for {i}, {case} in enumerate({cases}) "
               "if {fn}({case}) != {want}[{i}]] and isinstance({out}, list)",
     miss="It found none. Either the program is right or the comparison is."),

_art("tower", "analyst", "THE FIRST CROSSING",
     "{out} = next(({i} for {i}, {var} in enumerate({seq}) if {var} * {i} > {limit}), "
     "{fallback})",
     idiom="next() over a generator, with the not-found case priced in advance",
     composes=("numbering", "greatest", "sentinel"),
     note="The first position where the cost stops being affordable. One pass, "
          "and it stops there.",
     demo={"nums": "[5, 4, 9, 2, 7]", "at": "-1", "cap": "10"},
     example={"out": "at", "i": "k", "var": "v", "seq": "nums", "limit": "cap",
              "fallback": "len(nums)"},
     snapshot={"before": "{out}"},
     assertion="{out} == next(({i} for {i}, {var} in enumerate({seq}) "
               "if {var} * {i} > {limit}), {fallback}) "
               "and {out} != __b__['before']",
     miss="It scanned the whole tower to find something on the second floor. "
          "next() is allowed to stop."),

_art("coliseum", "analyst", "ONE PASS, EVERYTHING",
     "{out} = min((({cost}({a}, {b}), {a}, {b}) for {a} in {first} "
     "for {b} in {second} if {a} != {b}), default={default})",
     idiom="a double generator, a call, a tuple key and a default, in one line",
     composes=("pairing", "least", "sift"),
     note="The cheapest pair, and which pair it was, before the clock finishes "
          "its first swing.",
     demo={"first": "[1, 2]", "second": "[2, 3]", "gap": "lambda x, y: abs(x - y)",
           "best": "None"},
     example={"out": "best", "cost": "gap", "a": "x", "b": "y", "first": "first",
              "second": "second", "default": "None"},
     assertion="{out} == min((({cost}({a}, {b}), {a}, {b}) for {a} in {first} "
               "for {b} in {second} if {a} != {b}), default={default})",
     miss="It brought back the cost and lost the pair. Put the price first and "
          "carry the rest."),

# -- BERSERKER: the two-handed strike ---------------------------------------
# Tuple assignment. Two or three names move in one statement, and every
# right-hand side reads the OLD value of the others, because Python evaluates
# the whole right side before it assigns any of the left. That fact is the art.
# A Berserker who does not know it writes two lines and gets a different answer.

_art("village", "berserker", "BOTH HANDS",
     "{total}, {best} = {total} + {value}, max({best}, {value})",
     idiom="tuple assignment: two accumulators updated from one reading",
     composes=("toll", "greatest"),
     note="Add it and rank it in the same swing. Two lines is one line too many.",
     demo={"total": "2", "best": "1", "x": "5"},
     example={"total": "total", "best": "best", "value": "x"},
     snapshot={"t": "{total}", "b": "{best}"},
     assertion="{total} == __b__['t'] + ({value}) "
               "and {best} == max(__b__['b'], {value})",
     miss="One hand moved. Both sides of the comma, or neither."),

_art("fields", "berserker", "STRIKE AND STEP",
     "{i}, {total} = {i} + 1, {total} + ({expr} if {cond} else 0)",
     holes={"i": (ENEMY, "the index that has to move")},
     idiom="an index and an accumulator, one of them conditional, in one statement",
     composes=("advance", "toll", "sift"),
     note="Advance and collect together, or you will collect from where you "
          "already are.",
     demo={"i": "0", "total": "0", "nums": "[3, 1, 4]"},
     example={"i": "i", "total": "total", "expr": "nums[i]",
              "cond": "nums[i] > 2"},
     snapshot={"i": "{i}", "t": "{total}", "add": "(({expr}) if ({cond}) else 0)"},
     assertion="{i} == __b__['i'] + 1 and {total} == __b__['t'] + __b__['add']",
     miss="It stepped first and then read. The right-hand side is settled "
          "before anything on the left moves; that is the whole point of this."),

_art("highlands", "berserker", "TALLY AND CREST",
     "{book}[{key}], {best} = {book}.get({key}, 0) + 1, "
     "max({best}, {book}.get({key}, 0) + 1)",
     idiom="a subscript as an assignment target, beside a plain name",
     composes=("tally", "greatest"),
     note="Count it and find out whether it is now the commonest, at once.",
     demo={"counts": "{'a': 2}", "best": "0", "ch": "'a'"},
     example={"book": "counts", "key": "ch", "best": "best"},
     snapshot={"n": "{book}.get({key}, 0)", "b": "{best}"},
     assertion="{book}[{key}] == __b__['n'] + 1 "
               "and {best} == max(__b__['b'], __b__['n'] + 1)",
     miss="The crest is one behind the tally. Both sides read the same old "
          "count, so both have to add the one."),

_art("stringwood", "berserker", "SAY IT AND KEEP IT",
     "{out}, {store} = {out} + {sep}.join({parts}), {store}.union({parts})",
     idiom="a string built and a set widened from the same pieces",
     composes=("weave", "distill", "gather"),
     note="The utterance and the memory of it, in one motion.",
     demo={"line": "'a'", "seen": "set()", "parts": "['x', 'y']"},
     example={"out": "line", "sep": "'-'", "parts": "parts", "store": "seen"},
     snapshot={"o": "{out}", "s": "set({store})"},
     assertion="{out} == __b__['o'] + {sep}.join({parts}) "
               "and {store} == __b__['s'].union({parts})",
     miss="The set took the whole string instead of the pieces. A str is "
          "iterable and that is exactly how this goes wrong."),

_art("caverns", "berserker", "TAKE AND ADVANCE",
     "{seq}[{left}], {left} = {value}, {left} + {step}",
     idiom="writing through an index in the same statement that moves it",
     composes=("bind", "advance", "reach"),
     note="Write where you are standing, then be somewhere else.",
     demo={"nums": "[0, 0, 0, 0]", "left": "1", "step": "2"},
     example={"seq": "nums", "left": "left", "value": "7", "step": "step"},
     snapshot={"l": "{left}", "v": "({value})"},
     assertion="{seq}[__b__['l']] == __b__['v'] and {left} == __b__['l'] + {step}",
     miss="It wrote at the new position. The target's index is read before the "
          "index is rebound, which is the only reason this is safe."),

_art("marsh", "berserker", "INHALE AND EXHALE",
     "{total}, {left} = {total} + {seq}[{right}] - {seq}[{left}], {left} + 1",
     idiom="a window's two edges settled in one statement",
     composes=("inhale", "exhale", "advance"),
     note="Take in the right, give up the left, move the wall. No restart.",
     demo={"total": "6", "left": "0", "right": "3", "nums": "[1, 2, 3, 4, 5]"},
     example={"total": "total", "left": "left", "right": "right", "seq": "nums"},
     snapshot={"t": "{total}", "l": "{left}",
               "d": "{seq}[{right}] - {seq}[{left}]"},
     assertion="{total} == __b__['t'] + __b__['d'] and {left} == __b__['l'] + 1",
     miss="The wall moved before the breath was taken, so it gave up the wrong "
          "reed."),

_art("pass", "berserker", "CLOSE FROM BOTH SIDES",
     "{left}, {right} = {left} + ({seq}[{left}] + {seq}[{right}] < {target}), "
     "{right} - ({seq}[{left}] + {seq}[{right}] > {target})",
     idiom="a comparison used as the number one or zero",
     composes=("converge", "narrow", "complement"),
     note="Both lanterns decide for themselves whether to move, and neither "
          "waits.",
     demo={"nums": "[1, 2, 3, 4, 5]", "left": "0", "right": "4", "target": "9"},
     example={"left": "left", "right": "right", "seq": "nums", "target": "target"},
     snapshot={"l": "{left}", "r": "{right}",
               "s": "{seq}[{left}] + {seq}[{right}]"},
     assertion="{left} == __b__['l'] + (__b__['s'] < {target}) "
               "and {right} == __b__['r'] - (__b__['s'] > {target})",
     miss="Both moved, or neither did, on a sum that only asked for one of "
          "them. A bool is worth one or nothing; it is never worth both."),

_art("mines", "berserker", "POP AND PUSH IN ONE MOTION",
     "{out}, {stack} = {stack}[-1], {stack}[:-1] + [{value}]",
     idiom="a slice that removes the top and a list that replaces it",
     composes=("peek", "draw", "gather"),
     note="Take the top cart and load the next, without the lift ever being "
          "empty.",
     demo={"stack": "[1, 2, 3]", "top": "0"},
     example={"out": "top", "stack": "stack", "value": "9"},
     snapshot={"s": "list({stack})"},
     assertion="{out} == __b__['s'][-1] "
               "and {stack} == __b__['s'][:-1] + [{value}]",
     miss="It kept the old top as well. `[:-1]` drops exactly one, and it "
          "drops the right one."),

_art("citadel", "berserker", "TWO CELLS, ONE BLOW",
     "{grid}[{r}][{c}], {grid}[{c}][{r}], {total} = "
     "{grid}[{c}][{r}], {grid}[{r}][{c}], {total} + 1",
     holes={"r": (NAME, "the row you are standing on"),
            "c": (NAME, "the column you are reaching across")},
     idiom="two subscripted targets swapped, and a counter, in one statement",
     composes=("cell", "swap", "advance"),
     note="Transposition is one swap, repeated. This is the swap, and the "
          "tally of how many you have done.",
     demo={"grid": "[[1, 2, 3], [4, 5, 6], [7, 8, 9]]", "r": "0", "c": "2",
           "swaps": "0"},
     example={"grid": "grid", "r": "r", "c": "c", "total": "swaps"},
     snapshot={"a": "{grid}[{r}][{c}]", "b": "{grid}[{c}][{r}]", "t": "{total}"},
     assertion="{grid}[{r}][{c}] == __b__['b'] and {grid}[{c}][{r}] == __b__['a'] "
               "and {total} == __b__['t'] + 1",
     miss="Both cells hold the same value now. You wrote the first one, then "
          "read it back and wrote it again."),

_art("forest", "berserker", "DOWN AND BACK IN ONE",
     "{total}, {n}, {best} = {total} + {fn}({n} - 1) + {fn}({n} - 2), {n} - 1, "
     "max({best}, {total})",
     holes={"n": (ENEMY, "the depth you are standing at")},
     idiom="two recursive calls, the descent they pay for, and a mark, at once",
     composes=("descend", "unfold", "advance", "greatest"),
     note="Ask both smaller copies and take the step, before you have time to "
          "doubt either of them.",
     demo={"total": "0", "n": "5", "best": "0", "f": "lambda k: k * k"},
     example={"total": "total", "fn": "f", "n": "n", "best": "best"},
     snapshot={"t": "{total}", "n": "{n}", "b": "{best}",
               "v1": "{fn}({n} - 1)", "v2": "{fn}({n} - 2)"},
     assertion="{total} == __b__['t'] + __b__['v1'] + __b__['v2'] "
               "and {n} == __b__['n'] - 1 "
               "and {best} == max(__b__['b'], __b__['t'])",
     miss="It descended first and then asked, so it asked the wrong depth. "
          "The right-hand side is settled before anything moves."),

_art("canopy", "berserker", "BOTH FORKS AT ONCE",
     "{node}, {total}, {best} = {node}.{method}, {total} + {node}.val, "
     "max({best}, {node}.val)",
     holes={"method": (MEMBER, "which fork you take", ("left", "right", "next"))},
     imports=("from types import SimpleNamespace as Node",),
     idiom="a rebinding descent that still reads the node it is leaving",
     composes=("pluck", "branch", "toll", "greatest"),
     note="Take the value, rank the value, and be one branch further down.",
     demo={"node": "Node(val=5, left=Node(val=3, left=None, right=None), "
                   "right=None)",
           "total": "0", "best": "0"},
     example={"node": "node", "total": "total", "best": "best", "method": "left"},
     snapshot={"t": "{total}", "b": "{best}", "v": "{node}.val",
               "k": "{node}.{method}"},
     assertion="{total} == __b__['t'] + __b__['v'] "
               "and {best} == max(__b__['b'], __b__['v']) "
               "and {node}.val == __b__['k'].val",
     miss="It descended and then read, so it read the child twice and the "
          "parent never."),

_art("wastes", "berserker", "ADVANCE THE WHOLE RING",
     "{frontier}, {seen} = [{nb} for {node} in {frontier} for {nb} in {graph}[{node}] "
     "if {nb} not in {seen}], {seen} | set({frontier})",
     holes={"node": (BINDER, "a name for a ruin on the current edge")},
     idiom="a double comprehension and a set union settled together",
     composes=("expand", "enqueue", "mark", "guard"),
     note="A whole ring of the search, advanced in one statement, with nothing "
          "visited twice.",
     demo={"graph": "{'a': ['b', 'c'], 'b': ['a'], 'c': []}",
           "frontier": "['a']", "seen": "set()"},
     example={"frontier": "frontier", "seen": "seen", "nb": "w", "node": "v",
              "graph": "graph"},
     snapshot={"f": "list({frontier})", "s": "set({seen})"},
     assertion="{seen} == __b__['s'] | set(__b__['f']) "
               "and all({nb} not in __b__['s'] for {nb} in {frontier})",
     miss="Something already seen is standing on the new edge. Mark them when "
          "you enqueue them, not when you reach them."),

_art("ruins", "berserker", "PAY THE WHOLE ROW",
     "{dp}[{n}], {best} = max({dp}[{n} - 1], {dp}[{n} - 2] + {value}), "
     "max({best}, {dp}[{n} - 1])",
     holes={"n": (EXPR, "how far along the ledger you are")},
     idiom="a table cell written from two older cells while ranking a third",
     composes=("table", "transition", "choose", "greatest"),
     note="Take it or leave it, and record the best of what you have been "
          "leaving.",
     demo={"dp": "[0, 1, 1, 2, 2]", "best": "0", "at": "4", "w": "5"},
     example={"dp": "dp", "n": "at", "best": "best", "value": "w"},
     snapshot={"d": "list({dp})", "b": "{best}"},
     assertion="{dp}[{n}] == max(__b__['d'][{n} - 1], __b__['d'][{n} - 2] "
               "+ {value}) and {best} == max(__b__['b'], __b__['d'][{n} - 1])",
     miss="The cell read itself. Every cell in a ledger is paid for by cells "
          "written before it, never by its own new value."),

_art("dungeon", "berserker", "FIX AND PROVE",
     "{seq}[{i}], {out}, {i} = {value}, {out} + [{fn}({value}) == {want}], {i} + 1",
     holes={"i": (NAME, "the position you are repairing"),
            "want": (EXPR, "what it is supposed to answer")},
     idiom="a repair, the assertion that it worked, and the step, together",
     composes=("bind", "witness", "gather", "advance"),
     note="A fix without a proof is a guess. Do both in the same breath and "
          "you can never ship one without the other.",
     demo={"nums": "[1, 2, 3]", "log": "[]", "i": "1",
           "f": "lambda v: v * 2", "want": "8"},
     example={"seq": "nums", "i": "i", "value": "4", "out": "log", "fn": "f",
              "want": "want"},
     snapshot={"o": "list({out})", "i": "{i}"},
     assertion="{seq}[__b__['i']] == ({value}) "
               "and {out} == __b__['o'] + [{fn}({value}) == {want}] "
               "and {i} == __b__['i'] + 1",
     miss="It repaired the position it moved to. Targets are assigned left to "
          "right, so the index is still the old one when the write happens."),

_art("tower", "berserker", "TWO COSTS AT ONCE",
     "{best}, {total}, {i} = max({best}, {total} + {seq}[{i}]), "
     "max({floor}, {total} + {seq}[{i}]), {i} + 1",
     holes={"i": (NAME, "the position you are reading")},
     idiom="a running best and a running total that may be abandoned, in one pass",
     composes=("greatest", "toll", "span", "transition", "advance"),
     note="The whole of the linear scan the Tower is built to punish you for "
          "not knowing. One statement, one pass, one reading of each floor.",
     demo={"nums": "[2, -3, 4]", "best": "0", "total": "0", "i": "2"},
     example={"best": "best", "total": "total", "seq": "nums", "i": "i",
              "floor": "0"},
     snapshot={"b": "{best}", "t": "{total}", "v": "{seq}[{i}]", "i": "{i}"},
     assertion="{best} == max(__b__['b'], __b__['t'] + __b__['v']) "
               "and {total} == max({floor}, __b__['t'] + __b__['v']) "
               "and {i} == __b__['i'] + 1",
     miss="The best was taken from the total after the total had already been "
          "abandoned. The old total is what both of them are owed."),

_art("coliseum", "berserker", "THREE THINGS, ONE LINE",
     "{left}, {right}, {best} = {left} + 1, {right} - 1, "
     "max({best}, min({seq}[{left}], {seq}[{right}]) * ({right} - {left}))",
     idiom="three names settled from one reading of two positions",
     composes=("converge", "narrow", "least", "greatest", "span"),
     note="Both walls move and the mark is set, in the time the Chronomancer "
          "gives you for one of the three.",
     demo={"nums": "[1, 8, 6, 2, 5, 4, 8, 3, 7]", "left": "0", "right": "8",
           "best": "0"},
     example={"left": "left", "right": "right", "best": "best", "seq": "nums"},
     snapshot={"l": "{left}", "r": "{right}", "b": "{best}"},
     assertion="{left} == __b__['l'] + 1 and {right} == __b__['r'] - 1 "
               "and {best} == max(__b__['b'], min({seq}[__b__['l']], "
               "{seq}[__b__['r']]) * (__b__['r'] - __b__['l']))",
     miss="The mark was set from the walls after they moved, so it measured a "
          "width you no longer have."),

# -- ARCHIVIST: the paid-once ledger ----------------------------------------
# A conditional expression wrapped round a cache. Look it up; on a miss,
# compute it and file it, in the same breath, so that the expensive branch can
# only ever run once. `setdefault` is doing two jobs at once here and the
# Archivist is the only class whose signature depends on knowing that.

_art("village", "archivist", "ASK ONCE",
     "{out} = {book}[{key}] if {key} in {book} else {book}.setdefault({key}, {default})",
     idiom="a conditional expression over a lookup, with the miss filed as it happens",
     composes=("ask", "probe"),
     note="The first answer costs. The second one is already written down.",
     demo={"notes": "{'a': 1}", "got": "-1", "k": "'b'"},
     example={"out": "got", "book": "notes", "key": "k", "default": "0"},
     assertion="{out} == {book}[{key}] and {key} in {book}",
     miss="It answered and forgot. A ledger that does not write is a guess "
          "with better manners."),

_art("fields", "archivist", "THE SECOND TIME IS FREE",
     "{out} = {book}[{key}] if {key} in {book} "
     "else {book}.setdefault({key}, {expr} if {cond} else {alt})",
     idiom="a conditional expression inside the miss branch of another one",
     composes=("ask", "probe", "sift"),
     note="Decide what it is worth, once, and never decide it again.",
     demo={"notes": "{}", "got": "-1", "k": "'n'", "n": "4"},
     example={"out": "got", "book": "notes", "key": "k", "expr": "n * 2",
              "cond": "n % 2 == 0", "alt": "n"},
     assertion="{out} == {book}[{key}] and {key} in {book}",
     miss="The inner choice ran on every visit. Only the miss is allowed to "
          "be expensive."),

_art("highlands", "archivist", "THE VAULT THAT ANSWERS TWICE",
     "{book}[{key}] = {book}[{key}] + [{item}] if {key} in {book} else [{item}]",
     holes={"item": (EXPR, "the thing being filed")},
     idiom="a subscript assigned from a conditional that reads the same subscript",
     composes=("settle", "probe", "inscribe"),
     note="Grouping without `setdefault` and without `defaultdict`, so you can "
          "see what both of them are doing for you.",
     demo={"groups": "{'a': [1]}", "k": "'a'", "x": "2"},
     example={"book": "groups", "key": "k", "item": "x"},
     snapshot={"had": "{book}.get({key})"},
     assertion="{book}[{key}] == (__b__['had'] or []) + [{item}]",
     miss="It replaced the vault's contents with one rune. The old list is "
          "part of the new one."),

_art("stringwood", "archivist", "THE NAME IT ALREADY HAD",
     "{out} = {book}[{key}] if {key} in {book} "
     "else {book}.setdefault({key}, {sep}.join(sorted({text})))",
     idiom="a canonical form computed on the miss and filed under the original",
     composes=("ask", "probe", "weave"),
     note="Two words that sort to the same letters are one word. Work it out "
          "once per word.",
     demo={"canon": "{}", "got": "''", "w": "'listen'"},
     example={"out": "got", "book": "canon", "key": "w", "sep": "''",
              "text": "w"},
     assertion="{out} == {book}[{key}] and {key} in {book}",
     miss="It sorted the key instead of the word, or the word instead of the "
          "key. They are the same string here and they will not be next time."),

_art("caverns", "archivist", "THE ALCOVE YOU ALREADY OPENED",
     "{out} = {memo}[{i}] if {i} in {memo} "
     "else {memo}.setdefault({i}, {seq}[{i}] + {value})",
     holes={"i": (EXPR, "the position being asked about")},
     idiom="a cache keyed by index over a host that is expensive to read",
     composes=("consult", "enshrine", "reach"),
     note="An alcove read twice should cost once. The number of the alcove is "
          "the key.",
     demo={"memo": "{}", "nums": "[3, 1, 4]", "got": "-1", "at": "2"},
     example={"out": "got", "memo": "memo", "i": "at", "seq": "nums",
              "value": "10"},
     assertion="{out} == {memo}[{i}] and {i} in {memo}",
     miss="It filed the value under the value. Alcoves are numbered; that is "
          "what makes them alcoves."),

_art("marsh", "archivist", "THE FRAME YOU HAVE ALREADY MEASURED",
     "{out} = {memo}[({left}, {right})] if ({left}, {right}) in {memo} "
     "else {memo}.setdefault(({left}, {right}), sum({seq}[{left}:{right}]))",
     idiom="a tuple used as a cache key over a slice",
     composes=("consult", "enshrine", "sever", "toll"),
     note="Two frames of the same span are one frame. A pair of walls is a key.",
     demo={"memo": "{}", "nums": "[1, 2, 3, 4]", "got": "-1", "left": "1",
           "right": "3"},
     example={"out": "got", "memo": "memo", "left": "left", "right": "right",
              "seq": "nums"},
     assertion="{out} == {memo}[({left}, {right})] and ({left}, {right}) in {memo}",
     miss="A list will not key a dict, and neither will the frame itself. "
          "Tuples hash; the things that move do not."),

_art("pass", "archivist", "THE PAIR YOU HAVE ALREADY PRICED",
     "{out} = {memo}[{key}] if {key} in {memo} "
     "else {memo}.setdefault({key}, {seq}[{left}] + {seq}[{right}])",
     idiom="a cache keyed by a pair of converging positions",
     composes=("consult", "enshrine", "complement"),
     note="The pass is walked from both ends and the middle gets asked twice.",
     demo={"memo": "{}", "nums": "[1, 2, 3, 4, 5]", "got": "-1", "left": "0",
           "right": "4"},
     example={"out": "got", "memo": "memo", "key": "(left, right)",
              "seq": "nums", "left": "left", "right": "right"},
     assertion="{out} == {memo}[{key}] and {key} in {memo}",
     miss="The lanterns swapped and the key changed with them. Decide which "
          "order the pair is written in, once."),

_art("mines", "archivist", "THE TOP YOU ALREADY READ",
     "{out} = {memo}[len({stack})] if len({stack}) in {memo} "
     "else {memo}.setdefault(len({stack}), {stack}[-1])",
     idiom="a cache keyed by the depth of the structure it is caching",
     composes=("consult", "enshrine", "peek", "measure"),
     note="A tower of this height has been read before, and it said this.",
     demo={"memo": "{}", "stack": "[1, 2, 3]", "got": "0"},
     example={"out": "got", "memo": "memo", "stack": "stack"},
     assertion="{out} == {memo}[len({stack})] and len({stack}) in {memo}",
     miss="It read the top and never filed the height it read it at, so the "
          "next cart pays full price."),

_art("citadel", "archivist", "THE CELL YOU ALREADY WALKED",
     "{out} = {memo}[({r}, {c})] if ({r}, {c}) in {memo} "
     "else {memo}.setdefault(({r}, {c}), {grid}[{r}][{c}])",
     holes={"r": (NAME, "the row"), "c": (NAME, "the column")},
     idiom="a coordinate pair as a key, which is how a visited set on a plane "
           "is built",
     composes=("consult", "enshrine", "cell", "bounds"),
     note="The floor turns. The cell you stood on does not stop having been "
          "stood on.",
     demo={"memo": "{}", "grid": "[[1, 2], [3, 4]]", "r": "1", "c": "0",
           "got": "-1"},
     example={"out": "got", "memo": "memo", "r": "r", "c": "c", "grid": "grid"},
     assertion="{out} == {memo}[({r}, {c})] and ({r}, {c}) in {memo}",
     miss="Row and column went into the key the other way round somewhere. "
          "A plane is unforgiving about that and so is the Golem."),

_art("forest", "archivist", "THE CALL YOU ALREADY MADE",
     "{out} = {memo}[{n}] if {n} in {memo} "
     "else {memo}.setdefault({n}, {fn}({n} - 1) + {fn}({n} - 2))",
     holes={"n": (EXPR, "the depth being asked about")},
     idiom="memoisation of a two-branch recurrence, written as one expression",
     composes=("consult", "enshrine", "unfold", "floor"),
     note="The difference between a forest you can walk and a forest that eats "
          "you is this line.",
     demo={"memo": "{}", "n": "5", "got": "-1", "f": "lambda k: k"},
     example={"out": "got", "memo": "memo", "n": "n", "fn": "f"},
     assertion="{out} == {memo}[{n}] and {n} in {memo}",
     miss="Both calls ran and neither was filed, which is the exponential "
          "forest wearing a cache as a hat."),

_art("canopy", "archivist", "THE BRANCH YOU ALREADY COUNTED",
     "{out} = {memo}[{node}.val] if {node}.val in {memo} "
     "else {memo}.setdefault({node}.val, {fn}({node}.left) + {fn}({node}.right) + 1)",
     imports=("from types import SimpleNamespace as Node",),
     idiom="a subtree's answer filed under the node that owns it",
     composes=("consult", "enshrine", "pluck", "branch"),
     note="A subtree is asked about once per parent. There is more than one "
          "parent.",
     demo={"memo": "{}", "got": "-1", "f": "lambda t: 0 if t is None else 1",
           "node": "Node(val=5, left=Node(val=3, left=None, right=None), "
                   "right=None)"},
     example={"out": "got", "memo": "memo", "node": "node", "fn": "f"},
     assertion="{out} == {memo}[{node}.val] and {node}.val in {memo}",
     miss="It keyed on the node object. Two nodes are equal when the tree says "
          "so, not when Python does."),

_art("wastes", "archivist", "THE ROAD YOU ALREADY WALKED",
     "{out} = {memo}[{node}] if {node} in {memo} "
     "else {memo}.setdefault({node}, min(({memo}[{nb}] for {nb} in {graph}[{node}] "
     "if {nb} in {memo}), default={default}) + 1)",
     holes={"node": (EXPR, "the ruin being asked about")},
     idiom="a cache read from inside the expression that fills it",
     composes=("consult", "enshrine", "expand", "least"),
     note="The distance to here is one more than the nearest place you already "
          "know the distance to.",
     demo={"memo": "{'b': 0}", "graph": "{'a': ['b', 'c'], 'b': [], 'c': []}",
           "node": "'a'", "got": "-1"},
     example={"out": "got", "memo": "memo", "node": "node", "nb": "w",
              "graph": "graph", "default": "99"},
     assertion="{out} == {memo}[{node}] and {node} in {memo}",
     miss="It took the minimum over neighbours it has never priced, which is "
          "a road to a place that does not exist yet."),

_art("ruins", "archivist", "PAID ONCE, FOR EVER",
     "{out} = {memo}[{key}] if {key} in {memo} "
     "else {memo}.setdefault({key}, max({fn}({key} - {c}) + {value} "
     "for {c} in {coins} if {c} <= {key}))",
     holes={"c": (BINDER, "a name for one of the moves")},
     idiom="a memoised transition: the whole of top-down dynamic programming",
     composes=("consult", "enshrine", "transition", "greatest", "choose"),
     note="This is the Ruins. Every lit tile in the floor is one entry of this "
          "dict, and the light is what `setdefault` did.",
     demo={"memo": "{}", "coins": "[1, 3]", "at": "4", "got": "-1",
           "solve": "lambda k: k", "w": "1"},
     example={"out": "got", "memo": "memo", "key": "at", "fn": "solve",
              "value": "w", "c": "move", "coins": "coins"},
     assertion="{out} == {memo}[{key}] and {key} in {memo}",
     miss="A move longer than the distance ran anyway and asked about a tile "
          "behind the entrance."),

_art("dungeon", "archivist", "THE BUG YOU ALREADY NAMED",
     "{out} = {memo}[{key}] if {key} in {memo} "
     "else {memo}.setdefault({key}, [{case} for {case} in {cases} "
     "if {fn}({case}) != {want}[{case}]])",
     idiom="a failure set computed once and filed under the version that failed",
     composes=("consult", "enshrine", "witness", "sift"),
     note="Re-running the whole suite to find out what you already knew is the "
          "second most common way to waste an afternoon.",
     demo={"memo": "{}", "cases": "[1, 2]", "want": "{1: 2, 2: 5}",
           "broken": "lambda v: v + 1", "got": "None", "sig": "'v+1'"},
     example={"out": "got", "memo": "memo", "key": "sig", "case": "x",
              "cases": "cases", "fn": "broken", "want": "want"},
     assertion="{out} == {memo}[{key}] and {key} in {memo}",
     miss="It filed the failures under the failures. The key is which version "
          "of the program produced them."),

_art("tower", "archivist", "THE COST YOU HAVE ALREADY PAID",
     "{out} = {memo}[{key}] if {key} in {memo} "
     "else {memo}.setdefault({key}, {agg}({fn}({var}) for {var} in {seq} if {cond}))",
     idiom="an expensive aggregate hidden behind a single dictionary lookup",
     composes=("consult", "enshrine", "sift", "toll"),
     note="The Tower charges per floor. It does not charge twice for the same "
          "floor unless you let it.",
     demo={"memo": "{}", "nums": "[1, 2, 3, 4]", "cost": "lambda v: v * v",
           "got": "-1", "sig": "'evens'"},
     example={"out": "got", "memo": "memo", "key": "sig", "agg": "sum",
              "fn": "cost", "var": "v", "seq": "nums", "cond": "v % 2 == 0"},
     assertion="{out} == {memo}[{key}] and {key} in {memo}",
     miss="The aggregate ran and the lookup ran. In a conditional expression "
          "exactly one branch is allowed to happen."),

_art("coliseum", "archivist", "NOTHING TWICE",
     "{out} = {memo}[{key}] if {key} in {memo} "
     "else {memo}.setdefault({key}, {agg}(sorted({seq}, key=lambda {p}: "
     "({expr}, {p}))[:{k}]))",
     idiom="a sort, a key function, a slice and a cache, in one expression",
     composes=("consult", "enshrine", "weigh", "sever", "toll"),
     note="The Coliseum gives you the same crowd twice on purpose, to find out "
          "whether you noticed.",
     demo={"memo": "{}", "nums": "[5, 1, 4, 2]", "got": "-1", "sig": "'top2'",
           "width": "2"},
     example={"out": "got", "memo": "memo", "key": "sig", "agg": "sum",
              "seq": "nums", "p": "v", "expr": "-v", "k": "width"},
     assertion="{out} == {memo}[{key}] and {key} in {memo}",
     miss="It sorted, sliced and summed, and then threw all of it away without "
          "writing it down."),

# -- WARDEN: the ward -------------------------------------------------------
# A block header carrying a compound boundary — a chained comparison and two or
# three more clauses — with the operation written underneath it. The guard is
# typed before the thing it guards, which is the habit the class is named for.
# Everything the body touches was named in the header: a ward cannot protect a
# name it never mentioned.

_art("village", "warden", "THE FIRST GUARD",
     "if {item} not in {store} and {item} != {bad} and len({store}) < {cap}:",
     holes={"item": (EXPR, "the thing asking to come in")},
     body=("{store}.add({item})",),
     idiom="three conditions fused with `and`, evaluated left to right",
     composes=("guard", "mark", "measure"),
     note="New, allowed, and there is room. Three questions, one gate.",
     demo={"seen": "set()", "x": "'a'", "cap": "3"},
     example={"item": "x", "store": "seen", "bad": "'z'", "cap": "cap"},
     snapshot={"n": "len({store})"},
     assertion="{item} in {store} and len({store}) == __b__['n'] + 1",
     miss="The gate held when it should have opened. Read the clauses in order "
          "and find the one that is false."),

_art("fields", "warden", "THE NARROW GATE",
     "if {seq} and 0 <= {i} < len({seq}) and {seq}[{i}] not in {store}:",
     holes={"i": (NAME, "the position you intend to read")},
     body=("{store}.add({seq}[{i}])",),
     idiom="an emptiness check and a chained comparison guarding one index",
     composes=("sentinel", "guard", "mark", "reach"),
     note="Empty, out of range, already seen. The three ways an index kills you.",
     demo={"nums": "[3, 1, 4]", "i": "1", "seen": "set()"},
     example={"seq": "nums", "i": "i", "store": "seen"},
     snapshot={"n": "len({store})"},
     assertion="len({store}) == __b__['n'] + 1 and {seq}[{i}] in {store}",
     miss="Nothing came through. The order of the clauses is the whole defence: "
          "the length check has to happen before the read."),

_art("highlands", "warden", "THE KEY THAT FITS",
     "if {key} in {book} and {book}[{key}] >= {floor} and {book}[{key}] < {limit}:",
     body=("{book}[{key}] = {book}[{key}] + 1",),
     idiom="a membership test that makes the two comparisons after it safe",
     composes=("probe", "countdown", "inscribe"),
     note="A vault that is not there has no count, and a count you did not "
          "check has no bounds.",
     demo={"counts": "{'a': 2}", "k": "'a'"},
     example={"key": "k", "book": "counts", "floor": "1", "limit": "9"},
     snapshot={"n": "{book}.get({key})"},
     assertion="{book}.get({key}) == __b__['n'] + 1",
     miss="The count did not move, which means one of the two bounds is the "
          "wrong way round."),

_art("stringwood", "warden", "THE WORD THAT PASSES",
     "if {text} and len({text}) >= {floor} and {text}.{method}() not in {store}:",
     body=("{store}.add({text}.{method}())",),
     idiom="a normalising call inside the guard AND inside the body, identically",
     composes=("sentinel", "temper", "guard", "mark"),
     note="Whatever form you tested, file that same form. Two forms is two "
          "bugs.",
     demo={"w": "'Listen'", "seen": "set()"},
     example={"text": "w", "floor": "3", "method": "lower", "store": "seen"},
     snapshot={"n": "len({store})"},
     assertion="len({store}) == __b__['n'] + 1 and {text}.{method}() in {store}",
     miss="It tested one spelling and filed another, so the next identical "
          "word gets in as well."),

_art("caverns", "warden", "NEITHER END",
     "if 0 <= {i} < len({seq}) and 0 <= {j} < len({seq}) and {i} != {j}:",
     holes={"i": (NAME, "the first position"), "j": (NAME, "the second position")},
     body=("{seq}[{i}], {seq}[{j}] = {seq}[{j}], {seq}[{i}]",),
     idiom="two chained comparisons and an inequality guarding one swap",
     composes=("bounds", "swap", "reach"),
     note="Two indices means twice the bounds. Swapping something with itself "
          "is not wrong, it is just a lie about having done something.",
     demo={"nums": "[1, 2, 3]", "i": "0", "j": "2"},
     example={"seq": "nums", "i": "i", "j": "j"},
     snapshot={"a": "{seq}[{i}]", "b": "{seq}[{j}]"},
     assertion="{seq}[{i}] == __b__['b'] and {seq}[{j}] == __b__['a']",
     miss="Both alcoves hold the same rune now, which is what happens when a "
          "swap is written as two statements."),

_art("marsh", "warden", "THE WARD THAT BREAKS",
     "if {right} < len({seq}) and {total} + {seq}[{right}] <= {limit} "
     "and {right} - {left} < {k}:",
     body=("{total} = {total} + {seq}[{right}]", "{right} = {right} + 1"),
     idiom="the window's three invariants, stated before the window moves",
     composes=("sentinel", "inhale", "advance", "shrink"),
     note="Room on the right, room under the ward, room inside the width. The "
          "frame does not move until all three say so.",
     demo={"nums": "[1, 2, 3, 4]", "right": "1", "left": "0", "total": "1",
           "cap": "10", "width": "3"},
     example={"right": "right", "seq": "nums", "total": "total", "limit": "cap",
              "left": "left", "k": "width"},
     snapshot={"t": "{total}", "r": "{right}", "v": "{seq}[{right}]"},
     assertion="{total} == __b__['t'] + __b__['v'] and {right} == __b__['r'] + 1",
     miss="The frame moved and then checked, which is how a window runs off "
          "the end of a marsh."),

_art("pass", "warden", "NEITHER LANTERN CROSSES",
     "if {left} < {right} and {seq}[{left}] + {seq}[{right}] != {target} "
     "and {seq}[{left}] <= {seq}[{right}]:",
     body=("{left} = {left} + 1",),
     idiom="a crossing check that makes both reads after it legal",
     composes=("converge", "complement", "narrow", "guard"),
     note="The lanterns have not passed each other, the sum is wrong, and the "
          "near one is the cheap one. Only then does anybody move.",
     demo={"nums": "[1, 2, 3, 4, 5]", "left": "0", "right": "4", "target": "9"},
     example={"left": "left", "right": "right", "seq": "nums",
              "target": "target"},
     snapshot={"l": "{left}"},
     assertion="{left} == __b__['l'] + 1",
     miss="Nobody moved. If the sum already matches, this ward is not the one "
          "you want; it exists to keep you walking."),

_art("mines", "warden", "NOTHING FALLS OFF THE TOP",
     "if {stack} and {stack}[-1] < {value} and len({stack}) < {cap}:",
     body=("{stack}.pop()", "{stack}.append({value})"),
     idiom="a truthiness check that makes `[-1]` safe, and a capacity check",
     composes=("sentinel", "peek", "draw", "gather"),
     note="An empty tower has no top, and `[-1]` on nothing is the mine "
          "collapsing.",
     demo={"stack": "[1, 2]", "v": "5", "cap": "9"},
     example={"stack": "stack", "value": "v", "cap": "cap"},
     snapshot={"s": "list({stack})"},
     assertion="{stack} == __b__['s'][:-1] + [{value}]",
     miss="The tower is the wrong height now. One comes off, one goes on, and "
          "the order is not negotiable."),

_art("citadel", "warden", "INSIDE THE WALLS",
     "if 0 <= {r} < len({grid}) and 0 <= {c} < len({grid}[0]) "
     "and {grid}[{r}][{c}] not in {store}:",
     holes={"r": (NAME, "the row"), "c": (NAME, "the column")},
     body=("{store}.add({grid}[{r}][{c}])",),
     idiom="two chained comparisons on two axes before a single plane read",
     composes=("bounds", "cell", "mark", "guard"),
     note="A plane has four edges and every one of them is a different way to "
          "cease.",
     demo={"grid": "[[1, 2], [3, 4]]", "r": "1", "c": "1", "seen": "set()"},
     example={"r": "r", "c": "c", "grid": "grid", "store": "seen"},
     snapshot={"n": "len({store})"},
     assertion="len({store}) == __b__['n'] + 1 and {grid}[{r}][{c}] in {store}",
     miss="Row and column are checked against each other's length somewhere. "
          "The Citadel is not always square and the Golem knows that too."),

_art("forest", "warden", "THE FLOOR YOU DO NOT GO BELOW",
     "if {n} > {base} and {n} not in {memo} and {fn}({n} - 1) is not None:",
     holes={"n": (NAME, "the depth you are standing at")},
     body=("{memo}[{n}] = {fn}({n} - 1) + 1",),
     idiom="a base case, a cache check and a returned-nothing check, in order",
     composes=("floor", "consult", "enshrine", "descend"),
     note="Three reasons not to recurse, tested before recursing. The third one "
          "is the one nobody writes.",
     demo={"n": "4", "memo": "{}", "f": "lambda k: k"},
     example={"n": "n", "base": "0", "memo": "memo", "fn": "f"},
     snapshot={"v": "{fn}({n} - 1)"},
     assertion="{memo}.get({n}) == __b__['v'] + 1",
     miss="Nothing was filed. A guard that never lets the work happen is a "
          "base case with the comparison inverted."),

_art("canopy", "warden", "NEITHER FORK IS EMPTY",
     "if {node} is not None and {node}.left is not None and {node}.val > {floor} "
     "and {node}.val not in {store}:",
     imports=("from types import SimpleNamespace as Node",),
     body=("{store}.add({node}.val)", "{node} = {node}.left"),
     idiom="`is not None` used four deep, because falsy is not the same as absent",
     composes=("sentinel", "pluck", "branch", "guard"),
     note="A node holding zero is a node. `if node:` is the bug this ward "
          "exists to make impossible.",
     demo={"node": "Node(val=5, left=Node(val=3, left=None, right=None), "
                   "right=None)",
           "seen": "set()"},
     example={"node": "node", "floor": "0", "store": "seen"},
     snapshot={"k": "{node}.left", "v": "{node}.val"},
     assertion="__b__['v'] in {store} and {node} is not None "
               "and {node}.val == __b__['k'].val",
     miss="You are standing where you started, or standing on nothing. The "
          "descent is the last line for a reason."),

_art("wastes", "warden", "NO ROAD TWICE",
     "if {node} in {graph} and {node} not in {seen} "
     "and len({graph}[{node}]) <= {cap}:",
     holes={"node": (EXPR, "the ruin you are about to enter")},
     body=("{seen}.add({node})",),
     idiom="an existence check, a visited check and a degree bound, in one gate",
     composes=("probe", "guard", "mark", "expand"),
     note="Marked when you enter it, not when you leave it, which is the whole "
          "of why your search terminates.",
     demo={"graph": "{'a': ['b'], 'b': []}", "seen": "set()", "node": "'a'",
           "cap": "5"},
     example={"node": "node", "graph": "graph", "seen": "seen", "cap": "cap"},
     snapshot={"n": "len({seen})"},
     assertion="{node} in {seen} and len({seen}) == __b__['n'] + 1",
     miss="Nothing was marked. A ruin you walk into without marking is a ruin "
          "you will walk into again, for ever."),

_art("ruins", "warden", "THE TILE THAT IS ALREADY LIT",
     "if 0 <= {n} - {c} < len({dp}) and {c} <= {n} "
     "and {dp}[{n} - {c}] + {value} > {dp}[{n}]:",
     holes={"n": (NAME, "how far along the ledger you are"),
            "c": (NAME, "the move you are considering")},
     body=("{dp}[{n}] = {dp}[{n} - {c}] + {value}",),
     idiom="a bound on a derived index, then a comparison that uses it",
     composes=("bounds", "transition", "choose", "table"),
     note="Only write the tile if the new debt is smaller than the one already "
          "written there.",
     demo={"dp": "[0, 1, 1, 2, 2]", "at": "4", "move": "3", "w": "3"},
     example={"n": "at", "c": "move", "dp": "dp", "value": "w"},
     snapshot={"d": "list({dp})"},
     assertion="{dp}[{n}] == __b__['d'][{n} - {c}] + {value}",
     miss="The tile did not change, which means the ledger already held "
          "something better, or the index went negative and wrapped."),

_art("dungeon", "warden", "THE REPAIR THAT IS TESTED FIRST",
     "if {case} in {want} and {fn}({case}) != {want}[{case}] "
     "and {case} not in {store} and len({store}) < {cap}:",
     holes={"case": (EXPR, "the input you are accusing")},
     body=("{store}.add({case})",),
     idiom="four clauses where the second is only legal because of the first",
     composes=("probe", "witness", "guard", "mark"),
     note="Name the failing input before you touch the program. This is that "
          "habit with a `KeyError` guard in front of it.",
     demo={"want": "{1: 2, 2: 5}", "broken": "lambda v: v + 1",
           "failed": "set()", "x": "2", "cap": "9"},
     example={"case": "x", "want": "want", "fn": "broken", "store": "failed",
              "cap": "cap"},
     snapshot={"n": "len({store})"},
     assertion="{case} in {store} and len({store}) == __b__['n'] + 1",
     miss="It accused an input the suite has no answer for, or accused nothing "
          "at all."),

_art("tower", "warden", "THE BOUND YOU MAY NOT CROSS",
     "if {i} < len({seq}) and {total} + {seq}[{i}] <= {limit} "
     "and {seq}[{i}] not in {store}:",
     holes={"i": (NAME, "the position you are reading")},
     body=("{total} = {total} + {seq}[{i}]", "{store}.add({seq}[{i}])",
           "{i} = {i} + 1"),
     idiom="one guard, three consequences, and the index moved last",
     composes=("sentinel", "toll", "mark", "advance", "guard"),
     note="The Tower's floors double. A bound checked before the addition is "
          "the difference between climbing and falling.",
     demo={"nums": "[1, 2, 3]", "i": "0", "total": "0", "cap": "5",
           "seen": "set()"},
     example={"i": "i", "seq": "nums", "total": "total", "limit": "cap",
              "store": "seen"},
     snapshot={"t": "{total}", "i": "{i}", "v": "{seq}[{i}]"},
     assertion="{total} == __b__['t'] + __b__['v'] and {i} == __b__['i'] + 1 "
               "and __b__['v'] in {store}",
     miss="The index moved before the value was read, so the floor you paid "
          "for is not the floor you are on."),

_art("coliseum", "warden", "THE PERIMETER, UNDER A CLOCK",
     "if {left} < {right} and {seq}[{left}] not in {store} "
     "and {seq}[{right}] not in {store} "
     "and {seq}[{left}] + {seq}[{right}] <= {limit}:",
     body=("{store}.add({seq}[{left}])", "{store}.add({seq}[{right}])",
           "{left} = {left} + 1", "{right} = {right} - 1"),
     idiom="four clauses and four consequences, with nothing read after it moved",
     composes=("converge", "guard", "mark", "narrow", "advance"),
     note="Everything the Warden knows, in the one region that does not give "
          "you time to remember it.",
     demo={"nums": "[1, 2, 3, 4, 5]", "left": "0", "right": "4",
           "seen": "set()", "cap": "9"},
     example={"left": "left", "right": "right", "seq": "nums", "store": "seen",
              "limit": "cap"},
     snapshot={"l": "{left}", "r": "{right}", "a": "{seq}[{left}]",
               "b": "{seq}[{right}]"},
     assertion="{left} == __b__['l'] + 1 and {right} == __b__['r'] - 1 "
               "and __b__['a'] in {store} and __b__['b'] in {store}",
     miss="One wall moved before the other was read. Under a clock that is the "
          "only mistake anybody makes."),

# -- ARTIFICER: the forged key ----------------------------------------------
# A tool built and used inside a single line: a lambda handed straight to the
# thing that needs one. The Artificer's whole argument is that naming the
# comparison is cheaper than writing the comparison out four times, and a key
# function is the smallest possible demonstration of it.

_art("village", "artificer", "THE FIRST TOOL",
     "{out} = sorted({seq}, key=lambda {p}: ({expr}, {p}))",
     idiom="a lambda built where it is used, returning a tuple so ties break",
     composes=("weigh", "bind"),
     note="A key function is a tool. This is the first one you will build and "
          "you will build a hundred more.",
     demo={"nums": "[3, 1, 2]", "order": "[]"},
     example={"out": "order", "seq": "nums", "p": "v", "expr": "-v"},
     assertion="{out} == sorted({seq}, key=lambda {p}: ({expr}, {p}))",
     miss="It sorted by the thing itself. The key is what you are sorting BY, "
          "which is allowed to be different."),

_art("fields", "artificer", "TWO REASONS TO SORT",
     "{out} = sorted({seq}, key=lambda {p}: ({expr}, {alt}), reverse={cond})",
     idiom="a two-part key and a direction, decided in the same expression",
     composes=("weigh", "sift"),
     note="First by the thing that matters, then by the thing that settles "
          "ties. Never by whichever comes out.",
     demo={"words": "['bb', 'a', 'cc']", "order": "[]"},
     example={"out": "order", "seq": "words", "p": "w", "expr": "len(w)",
              "alt": "w", "cond": "True"},
     assertion="{out} == sorted({seq}, key=lambda {p}: ({expr}, {alt}), "
               "reverse={cond})",
     miss="Reversing a two-part key reverses both parts. If you wanted one of "
          "them the other way, negate it instead."),

_art("highlands", "artificer", "THE KEY THAT READS THE TALLY",
     "{out} = sorted({book}, key=lambda {p}: (-{book}[{p}], {p}))[:{k}]",
     idiom="a lambda that closes over the dict it is ranking",
     composes=("weigh", "tally", "sever"),
     note="Top-k out of a tally. The minus sign is doing the work a `reverse` "
          "could not do without breaking the tie-break.",
     demo={"counts": "{'a': 3, 'b': 1, 'c': 3}", "top": "[]", "width": "2"},
     example={"out": "top", "book": "counts", "p": "w", "k": "width"},
     assertion="{out} == sorted({book}, key=lambda {p}: (-{book}[{p}], {p}))[:{k}]",
     miss="Ties came out in whichever order the vault felt like. The second "
          "part of the key is not decoration."),

_art("stringwood", "artificer", "THE TOOL THAT NAMES WORDS",
     "{out} = sorted({parts}, key=lambda {p}: ({sep}.join(sorted({p})), len({p})))",
     idiom="a canonical form computed inside the key rather than stored beside it",
     composes=("weigh", "weave", "temper"),
     note="Anagrams sort together when the key is the sorted word. The grove "
          "has been doing this to you since you walked in.",
     demo={"parts": "['eat', 'tea', 'bat']", "order": "[]"},
     example={"out": "order", "parts": "parts", "p": "w", "sep": "''"},
     assertion="{out} == sorted({parts}, key=lambda {p}: "
               "({sep}.join(sorted({p})), len({p})))",
     miss="It sorted the words instead of sorting by the sorted words. Read "
          "the key again; there are two sorts in this line and only one of "
          "them is yours."),

_art("caverns", "artificer", "THE TOOL THAT READS POSITIONS",
     "{out} = sorted(range(len({seq})), key=lambda {i}: ({seq}[{i}], {i}))",
     idiom="a key over indices, so what comes back is where things are",
     composes=("weigh", "march", "reach"),
     note="Sort the alcove numbers, not the runes. Then you still know where "
          "everything came from.",
     demo={"nums": "[3, 1, 2]", "order": "[]"},
     example={"out": "order", "seq": "nums", "i": "k"},
     assertion="{out} == sorted(range(len({seq})), key=lambda {i}: "
               "({seq}[{i}], {i}))",
     miss="It brought back the runes in order and lost every alcove number, "
          "which was the only thing worth keeping."),

_art("marsh", "artificer", "THE TOOL THAT PRICES A FRAME",
     "{out} = max(range(len({seq}) - {k} + 1), key=lambda {i}: sum({seq}[{i}:{i} + {k}]))",
     idiom="a key function that slices, so the frame is priced without moving",
     composes=("weigh", "sever", "toll", "greatest"),
     note="Where the best frame starts, not what it is worth. The marsh will "
          "want the position.",
     demo={"nums": "[2, 1, 5, 1, 3]", "at": "0", "width": "3"},
     example={"out": "at", "seq": "nums", "i": "s", "k": "width"},
     assertion="{out} == max(range(len({seq}) - {k} + 1), key=lambda {i}: "
               "sum({seq}[{i}:{i} + {k}]))",
     miss="The last start ran off the end. The number of frames is one more "
          "than the difference, and it has been one more than the difference "
          "all along."),

_art("pass", "artificer", "THE TOOL THAT PRICES A PAIR",
     "{out} = min({spans}, key=lambda {p}: abs({seq}[{p}[0]] + {seq}[{p}[1]] - {target}))",
     idiom="a lambda that unpacks its argument by index inside the key",
     composes=("weigh", "complement", "least"),
     note="Every pair, priced by how far off it is. The closest one is the one "
          "you carry back.",
     demo={"nums": "[1, 2, 3, 4]", "spans": "[(0, 1), (0, 3), (2, 3)]",
           "best": "None", "target": "6"},
     example={"out": "best", "spans": "spans", "p": "pair", "seq": "nums",
              "target": "target"},
     assertion="{out} == min({spans}, key=lambda {p}: "
               "abs({seq}[{p}[0]] + {seq}[{p}[1]] - {target}))",
     miss="It minimised the sum instead of the distance from the target. "
          "`abs` is the difference between those two sentences."),

_art("mines", "artificer", "THE TOOL THAT KNOWS WHICH END",
     "{out} = sorted({stack}, key=lambda {p}: ({p} in {store}, -{p}))[:{k}]",
     idiom="a boolean as the first part of a key, which sorts False first",
     composes=("weigh", "probe", "sever"),
     note="Everything unseen, biggest first, and the seen ones swept to the "
          "back. Two ideas, one tuple.",
     demo={"stack": "[3, 1, 2]", "seen": "{1}", "top": "[]", "width": "2"},
     example={"out": "top", "stack": "stack", "p": "v", "store": "seen",
              "k": "width"},
     assertion="{out} == sorted({stack}, key=lambda {p}: "
               "({p} in {store}, -{p}))[:{k}]",
     miss="The seen carts came out first. `False` is less than `True` and that "
          "is the only reason this works."),

_art("citadel", "artificer", "THE TOOL THAT TURNS THE FLOOR",
     "{out} = sorted({spans}, key=lambda {p}: ({grid}[{p}[0]][{p}[1]], {p}))",
     idiom="a key that indexes a plane through a tuple it was handed",
     composes=("weigh", "cell", "bounds"),
     note="Coordinates ranked by what stands on them. The Citadel will rotate; "
          "the ranking will not care.",
     demo={"grid": "[[3, 1], [2, 4]]", "spans": "[(0, 0), (0, 1), (1, 0)]",
           "order": "[]"},
     example={"out": "order", "spans": "spans", "p": "cellref", "grid": "grid"},
     assertion="{out} == sorted({spans}, key=lambda {p}: "
               "({grid}[{p}[0]][{p}[1]], {p}))",
     miss="Row and column went in the other way round. On a square floor that "
          "is invisible, which is why the Citadel is not always square."),

_art("forest", "artificer", "THE TOOL THAT CALLS ITSELF",
     "{out} = sorted({children}, key=lambda {p}: (-{fn}({p}), {p}))[:{k}]",
     idiom="a key function whose body is a recursive call",
     composes=("weigh", "descend", "sever"),
     note="Rank the smaller copies by what the smaller copies came back with. "
          "You do not have to know how they did it.",
     demo={"kids": "[1, 2, 3]", "order": "[]", "size": "lambda t: t * t",
           "width": "2"},
     example={"out": "order", "children": "kids", "p": "c", "fn": "size",
              "k": "width"},
     assertion="{out} == sorted({children}, key=lambda {p}: "
               "(-{fn}({p}), {p}))[:{k}]",
     miss="It ranked the children by what they are rather than by what they "
          "found. Trust the smaller call, then use its answer."),

_art("canopy", "artificer", "THE TOOL THAT MEASURES BRANCHES",
     "{out} = max([{child} for {child} in ({node}.left, {node}.right) if {child}], "
     "key=lambda {p}: {fn}({p}), default={default})",
     imports=("from types import SimpleNamespace as Node",),
     idiom="a comprehension that removes the empty forks before the key sees them",
     composes=("weigh", "branch", "pluck", "greatest"),
     note="Build the list of forks that exist, then rank them. A key function "
          "handed `None` is a key function that raises.",
     demo={"node": "Node(val=5, left=Node(val=3, left=None, right=None), "
                   "right=Node(val=8, left=None, right=None))",
           "big": "None", "height": "lambda t: t.val"},
     example={"out": "big", "child": "kid", "node": "node", "p": "t",
              "fn": "height", "default": "None"},
     assertion="{out} is not None and "
               "{out}.val == max({fn}({node}.left), {fn}({node}.right))",
     miss="The key was handed an absent branch. Filter first, then measure; "
          "there is no order in which those two swap."),

_art("wastes", "artificer", "THE TOOL THAT RANKS ROADS",
     "{out} = sorted({graph}, key=lambda {p}: (-len({graph}[{p}]), {p}))[:{k}]",
     idiom="a key that measures a node's edges without walking any of them",
     composes=("weigh", "expand", "sever"),
     note="The busiest ruins first. You will want to start your search "
          "somewhere and this is an argument for where.",
     demo={"graph": "{'a': ['b', 'c'], 'b': [], 'c': ['a']}", "order": "[]",
           "width": "2"},
     example={"out": "order", "graph": "graph", "p": "v", "k": "width"},
     assertion="{out} == sorted({graph}, key=lambda {p}: "
               "(-len({graph}[{p}]), {p}))[:{k}]",
     miss="It ranked the roads instead of the ruins. Iterating a dict gives "
          "you its keys, and its keys are the places."),

_art("ruins", "artificer", "THE TOOL THAT PRICES A MOVE",
     "{out} = max({coins}, key=lambda {p}: "
     "({dp}[{n} - {p}] + {value} if {p} <= {n} else {base}, {p}))",
     holes={"n": (NAME, "how far along the ledger you are")},
     idiom="a conditional expression inside a key, pricing the illegal move out",
     composes=("weigh", "transition", "choose", "greatest"),
     note="Which move to make, not what it is worth. An illegal move is priced "
          "at something nothing can beat.",
     demo={"coins": "[1, 3]", "dp": "[0, 1, 1, 2, 2]", "at": "4", "w": "1",
           "best": "0"},
     example={"out": "best", "coins": "coins", "p": "m", "dp": "dp", "n": "at",
              "value": "w", "base": "-99"},
     assertion="{out} == max({coins}, key=lambda {p}: "
               "({dp}[{n} - {p}] + {value} if {p} <= {n} else {base}, {p}))",
     miss="An illegal move won, or an illegal move raised. Both mean the "
          "conditional is on the wrong side of the comma."),

_art("dungeon", "artificer", "THE TOOL THAT RANKS FAILURES",
     "{out} = sorted({cases}, key=lambda {p}: ({fn}({p}) == {want}[{p}], {p}))",
     idiom="a key whose value is the result of running the thing under test",
     composes=("weigh", "witness", "sift"),
     note="Failures to the front, in a stable order, so tomorrow's run is "
          "comparable with today's.",
     demo={"cases": "[1, 2, 3]", "want": "{1: 2, 2: 5, 3: 4}",
           "broken": "lambda v: v + 1", "order": "[]"},
     example={"out": "order", "cases": "cases", "p": "x", "fn": "broken",
              "want": "want"},
     assertion="{out} == sorted({cases}, key=lambda {p}: "
               "({fn}({p}) == {want}[{p}], {p}))",
     miss="The passing cases came first. You are ranking by a boolean and you "
          "wanted the false ones."),

_art("tower", "artificer", "THE TOOL THAT PRICES EVERYTHING ONCE",
     "{out} = min({seq}, key=lambda {p}: ({memo}[{p}] if {p} in {memo} "
     "else {memo}.setdefault({p}, {fn}({p})), {p}))",
     idiom="a key function with a cache inside it, so the sort is linear in calls",
     composes=("weigh", "consult", "enshrine", "least"),
     note="Sorting calls the key more than once per item. If the key is "
          "expensive, that is the Tower charging you for a floor twice.",
     demo={"nums": "[3, 1, 2]", "memo": "{}", "cost": "lambda v: -v",
           "best": "None"},
     example={"out": "best", "seq": "nums", "p": "v", "memo": "memo",
              "fn": "cost"},
     assertion="{out} == min({seq}, key=lambda {p}: ({memo}[{p}], {p})) "
               "and len({memo}) == len(set({seq}))",
     miss="The cache is empty and the cost function ran once per comparison. "
          "That is the shape of an O(n log n) sort with an O(n) key."),

_art("coliseum", "artificer", "THE TOOL THAT WINS THE ROUND",
     "{out} = sorted((({a}, {b}) for {a} in {first} for {b} in {second} "
     "if {a} != {b}), key=lambda {p}: ({cost}(*{p}), {p}))[:{k}]",
     idiom="a generator, a starred call inside a lambda, a key and a slice",
     composes=("weigh", "pairing", "sift", "sever"),
     note="Every pair built, priced and cut down to the ones worth having, in "
          "the time the sand gives you.",
     demo={"first": "[1, 2]", "second": "[2, 3]",
           "gap": "lambda x, y: abs(x - y)", "order": "[]", "width": "2"},
     example={"out": "order", "a": "x", "b": "y", "first": "first",
              "second": "second", "cost": "gap", "p": "pair", "k": "width"},
     assertion="{out} == sorted((({a}, {b}) for {a} in {first} "
               "for {b} in {second} if {a} != {b}), "
               "key=lambda {p}: ({cost}(*{p}), {p}))[:{k}]",
     miss="The star went missing and the tool was handed one tuple where it "
          "wanted two numbers."),

# -- SEER: the read ---------------------------------------------------------
# `next()` over a generator with a default: the first place two things stopped
# agreeing, and nothing written down. Every one of these is a question, not a
# change, which is why the Seer's arts are the only ones whose assertion can
# be the plain restatement — there is no mutation to prove.

_art("village", "seer", "THE FIRST DISAGREEMENT",
     "{out} = next(({i} for {i}, ({a}, {b}) in enumerate(zip({first}, {second})) "
     "if {a} != {b}), {default})",
     idiom="a nested unpack inside enumerate inside zip, with a default",
     composes=("pairing", "numbering"),
     note="Where two sequences part company. The first place, and only the "
          "first.",
     demo={"xs": "[1, 2, 3]", "ys": "[1, 9, 3]", "at": "-1"},
     example={"out": "at", "i": "k", "a": "p", "b": "q", "first": "xs",
              "second": "ys", "default": "-1"},
     snapshot={"before": "{out}"},
     assertion="{out} == next(({i} for {i}, ({a}, {b}) in "
               "enumerate(zip({first}, {second})) if {a} != {b}), {default}) "
               "and {out} != __b__['before']",
     miss="It found nothing, which either means they agree or means the "
          "unpacking is one bracket short."),

_art("fields", "seer", "WHAT IT STOPPED BEING",
     "{out} = next((({a}, {b}) for {a}, {b} in zip({first}, {second}) "
     "if {a} != {b}), {default})",
     idiom="a pair unpacked out of zip and carried whole through a default",
     composes=("pairing", "sift"),
     note="Not where. What each of them was at the time, which is the half you "
          "did not have.",
     demo={"xs": "[1, 2, 3]", "ys": "[1, 9, 3]", "at": "None"},
     example={"out": "at", "a": "p", "b": "q", "first": "xs", "second": "ys",
              "default": "None"},
     assertion="{out} == next((({a}, {b}) for {a}, {b} in "
               "zip({first}, {second}) if {a} != {b}), {default}) "
               "and {out} is not None",
     miss="It came back with one of them. A disagreement has two sides and the "
          "other one is the interesting side."),

_art("highlands", "seer", "THE COUNT THAT LIES",
     "{out} = next(({key} for {key} in {book} "
     "if {book}[{key}] != {second}.get({key}, {default})), {fallback})",
     holes={"key": (BINDER, "a name for the key under inspection"),
            "second": (ENEMY, "the tally you are checking against")},
     idiom="a `.get` with a default standing in for a key that may not exist",
     composes=("probe", "ask", "tally"),
     note="The first name two tallies disagree about, including the names only "
          "one of them has heard of.",
     demo={"counts": "{'a': 1, 'b': 2}", "other": "{'a': 1, 'b': 5}",
           "at": "''"},
     example={"out": "at", "key": "w", "book": "counts", "second": "other",
              "default": "0", "fallback": "None"},
     assertion="{out} == next(({key} for {key} in {book} "
               "if {book}[{key}] != {second}.get({key}, {default})), {fallback})"
               " and {out} is not None",
     miss="It raised on a key one vault has and the other does not, which is "
          "exactly the disagreement you were looking for."),

_art("stringwood", "seer", "WHERE THE WORDS PART",
     "{out} = next(({i} for {i}, ({a}, {b}) in enumerate(zip({text}, {second})) "
     "if {a}.{method}() != {b}.{method}()), {default})",
     holes={"second": (ENEMY, "the other utterance")},
     idiom="a normalising call applied to both halves of an unpacked pair",
     composes=("pairing", "temper"),
     note="Case is not a difference. Everything after the case is.",
     demo={"w1": "'Listen'", "w2": "'listex'", "at": "-1"},
     example={"out": "at", "i": "k", "a": "p", "b": "q", "text": "w1",
              "second": "w2", "method": "lower", "default": "-1"},
     assertion="{out} == next(({i} for {i}, ({a}, {b}) in "
               "enumerate(zip({text}, {second})) "
               "if {a}.{method}() != {b}.{method}()), {default}) and {out} >= 0",
     miss="It normalised one side and compared it against the other side raw, "
          "so every capital letter is now a difference."),

_art("caverns", "seer", "THE ALCOVE THAT MOVED",
     "{out} = next(({i} for {i} in range(len({seq})) "
     "if {seq}[{i}] != {second}[{i}]), {default})",
     holes={"second": (ENEMY, "the host you are checking against")},
     idiom="a positional scan over two hosts read through the same index",
     composes=("march", "reach", "probe"),
     note="zip stops at the shorter one. This does not, and sometimes that is "
          "the thing you need.",
     demo={"nums": "[1, 2, 3]", "other": "[1, 2, 9]", "at": "-1"},
     example={"out": "at", "i": "k", "seq": "nums", "second": "other",
              "default": "-1"},
     assertion="{out} == next(({i} for {i} in range(len({seq})) "
               "if {seq}[{i}] != {second}[{i}]), {default}) and {out} >= 0",
     miss="It read past the end of the shorter host. If they are not the same "
          "length, that is the first thing to say out loud."),

_art("marsh", "seer", "THE FRAME THAT BROKE",
     "{out} = next(({i} for {i} in range(len({seq}) - {k} + 1) "
     "if sum({seq}[{i}:{i} + {k}]) > {limit}), {default})",
     idiom="a slice summed inside the condition of a generator",
     composes=("sever", "toll", "sentinel"),
     note="The first place the ward broke, found without the frame ever having "
          "moved.",
     demo={"nums": "[1, 1, 5, 1]", "at": "-1", "width": "2", "cap": "5"},
     example={"out": "at", "i": "s", "seq": "nums", "k": "width",
              "limit": "cap", "default": "-1"},
     assertion="{out} == next(({i} for {i} in range(len({seq}) - {k} + 1) "
               "if sum({seq}[{i}:{i} + {k}]) > {limit}), {default}) "
               "and {out} >= 0",
     miss="It never broke, or it broke before it started. Count the frames: "
          "there is one more of them than you think."),

_art("pass", "seer", "WHERE THEY MEET",
     "{out} = next((({left}, {right}) for {left}, {right} in {spans} "
     "if {seq}[{left}] + {seq}[{right}] == {target}), {default})",
     holes={"left": (BINDER, "a name for the near end"),
            "right": (BINDER, "a name for the far end")},
     idiom="a pair unpacked in the loop header and read as two indices in the test",
     composes=("converge", "complement", "pairing"),
     note="The first pair that sums to what you were sent for, and which pair "
          "it was.",
     demo={"nums": "[1, 2, 3, 4]", "spans": "[(0, 1), (0, 3), (1, 2)]",
           "pair": "None", "target": "5"},
     example={"out": "pair", "left": "lo", "right": "hi", "spans": "spans",
              "seq": "nums", "target": "target", "default": "None"},
     assertion="{out} == next((({left}, {right}) for {left}, {right} in {spans} "
               "if {seq}[{left}] + {seq}[{right}] == {target}), {default}) "
               "and {out} is not None",
     miss="It brought back the sum. You knew the sum before you started; it is "
          "printed on the contract."),

_art("mines", "seer", "THE CART THAT WAS NEVER UNLOADED",
     "{out} = next(({i} for {i} in range(len({stack}) - 1, -1, -1) "
     "if {stack}[{i}] not in {store} and {stack}[{i}] > {floor}), {default})",
     idiom="a reversed range and a two-clause test, read from the top down",
     composes=("draw", "peek", "probe"),
     note="From the top down, because that is the only direction a tower "
          "answers in.",
     demo={"stack": "[1, 2, 3]", "seen": "{3}", "at": "-1"},
     example={"out": "at", "i": "k", "stack": "stack", "store": "seen",
              "floor": "1", "default": "-1"},
     assertion="{out} == next(({i} for {i} in range(len({stack}) - 1, -1, -1) "
               "if {stack}[{i}] not in {store} and {stack}[{i}] > {floor}), "
               "{default}) and {out} >= 0",
     miss="It read from the bottom, which on a stack is reading the oldest "
          "thing and calling it the newest."),

_art("citadel", "seer", "THE CELL THAT DID NOT TURN",
     "{out} = next((({r}, {c}) for {r} in range(len({grid})) "
     "for {c} in range(len({grid}[0])) if {grid}[{r}][{c}] != {second}[{c}][{r}]), "
     "{default})",
     holes={"second": (ENEMY, "the plane you are checking against")},
     idiom="two ranges and one crossed index, which is a transpose check",
     composes=("cell", "bounds", "pairing"),
     note="Where the rotation went wrong, given as a coordinate you can walk to.",
     demo={"grid": "[[1, 2], [3, 4]]", "other": "[[1, 3], [2, 9]]",
           "at": "None"},
     example={"out": "at", "r": "x", "c": "y", "grid": "grid",
              "second": "other", "default": "None"},
     assertion="{out} == next((({r}, {c}) for {r} in range(len({grid})) "
               "for {c} in range(len({grid}[0])) "
               "if {grid}[{r}][{c}] != {second}[{c}][{r}]), {default}) "
               "and {out} is not None",
     miss="Both indices went in the same order on both sides, which compares "
          "the plane against itself and always agrees."),

_art("forest", "seer", "WHERE THE COPIES DIVERGE",
     "{out} = next(({n} for {n} in range({limit}) "
     "if {n} >= {base} and {fn}({n}) != {second}({n})), {default})",
     holes={"n": (BINDER, "a name for the depth"),
            "second": (NAME, "the other implementation")},
     idiom="two functions compared over a bounded range, which is a property "
           "test in one line",
     composes=("unfold", "descend", "witness"),
     note="Two implementations of the same recurrence, and the first input "
          "they stop agreeing on.",
     demo={"f": "lambda k: k * 2", "g": "lambda k: k + k if k < 3 else 0",
           "at": "-1", "cap": "5"},
     example={"out": "at", "n": "d", "limit": "cap", "base": "1", "fn": "f",
              "second": "g", "default": "-1"},
     assertion="{out} == next(({n} for {n} in range({limit}) "
               "if {n} >= {base} and {fn}({n}) != {second}({n})), {default}) "
               "and {out} >= 0",
     miss="They agreed everywhere, which either means the rewrite is correct "
          "or means the range is too small to reach the interesting part."),

_art("canopy", "seer", "THE BRANCH THAT LIED",
     "{out} = next(({child} for {child} in ({node}.left, {node}.right) "
     "if {child} is not None and {child}.val > {node}.val), {default})",
     imports=("from types import SimpleNamespace as Node",),
     idiom="an absence test that must run before the field read next to it",
     composes=("pluck", "branch", "sentinel"),
     note="A child that outranks its parent is the only evidence a search tree "
          "is broken, and it is local.",
     demo={"node": "Node(val=5, left=Node(val=3, left=None, right=None), "
                   "right=Node(val=8, left=None, right=None))",
           "at": "None"},
     example={"out": "at", "child": "kid", "node": "node", "default": "None"},
     assertion="{out} is not None and {out}.val > {node}.val",
     miss="It compared a node against nothing, or it compared the parent "
          "against itself. `and` stops at the first false clause; use that."),

_art("wastes", "seer", "THE ROAD THAT GOES NOWHERE",
     "{out} = next(({node} for {node} in {graph} "
     "if any({nb} not in {graph} for {nb} in {graph}[{node}])), {default})",
     holes={"node": (BINDER, "a name for the ruin under inspection")},
     idiom="a generator inside `any` inside the condition of another generator",
     composes=("expand", "probe", "sift"),
     note="The first ruin with a road to somewhere that is not on the map. "
          "This is how a graph is actually broken.",
     demo={"graph": "{'a': ['b'], 'b': ['z']}", "at": "None"},
     example={"out": "at", "node": "v", "graph": "graph", "nb": "w",
              "default": "None"},
     assertion="{out} == next(({node} for {node} in {graph} "
               "if any({nb} not in {graph} for {nb} in {graph}[{node}])), "
               "{default}) and {out} is not None",
     miss="It found nothing. A neighbour that is not a key is not the same as "
          "a neighbour with no neighbours, and the difference is a KeyError "
          "waiting for you."),

_art("ruins", "seer", "THE TILE THAT WAS NEVER PAID",
     "{out} = next(({n} for {n} in range(1, len({dp})) if {dp}[{n}] < "
     "max(({dp}[{n} - {c}] + {value} for {c} in {coins} if {c} <= {n}), "
     "default={base})), {default})",
     holes={"n": (BINDER, "a name for the tile"),
            "c": (BINDER, "a name for one of the moves")},
     idiom="a whole transition evaluated inside the condition of a search",
     composes=("table", "transition", "greatest", "sift"),
     note="The first tile whose ledger entry is smaller than what it could "
          "have been. That is where the recurrence is wrong.",
     demo={"dp": "[0, 1, 1, 2, 2]", "coins": "[1]", "w": "1", "at": "-1"},
     example={"out": "at", "n": "t", "dp": "dp", "c": "move", "value": "w",
              "coins": "coins", "base": "-99", "default": "-1"},
     assertion="{out} == next(({n} for {n} in range(1, len({dp})) "
               "if {dp}[{n}] < max(({dp}[{n} - {c}] + {value} "
               "for {c} in {coins} if {c} <= {n}), default={base})), {default}) "
               "and {out} >= 0",
     miss="It started at tile zero, which nothing reaches and nothing pays "
          "for, and declared the whole ledger wrong."),

_art("dungeon", "seer", "THE LINE THAT IS WRONG",
     "{out} = next((({i}, {case}) for {i}, {case} in enumerate({cases}) "
     "if {fn}({case}) != {want}[{i}]), {default})",
     idiom="enumerate destructured, the program run, and the answer sheet indexed",
     composes=("numbering", "witness", "sift"),
     note="The first failing case and where it sits. Then you read the code, "
          "and only then.",
     demo={"cases": "[1, 2, 3]", "want": "[2, 4, 4]",
           "broken": "lambda v: v + 1", "at": "None"},
     example={"out": "at", "i": "k", "case": "x", "cases": "cases",
              "fn": "broken", "want": "want", "default": "None"},
     assertion="{out} == next((({i}, {case}) for {i}, {case} in "
               "enumerate({cases}) if {fn}({case}) != {want}[{i}]), {default}) "
               "and {out} is not None",
     miss="It stopped at the first case rather than the first FAILING case. "
          "The condition is the whole of the difference."),

_art("tower", "seer", "WHERE IT STOPS BEING LINEAR",
     "{out} = next(({i} for {i} in range(1, len({seq})) "
     "if {seq}[{i}] > {seq}[{i} - 1] * {k} and {seq}[{i}] > {limit}), {default})",
     idiom="a scaled comparison against the previous position, plus a floor",
     composes=("march", "reach", "greatest"),
     note="The floor where the cost stopped growing the way you promised it "
          "would. The Oracle will ask you for this number.",
     demo={"nums": "[1, 2, 9, 10]", "at": "-1", "width": "2", "cap": "3"},
     example={"out": "at", "i": "k", "seq": "nums", "k": "width",
              "limit": "cap", "default": "-1"},
     assertion="{out} == next(({i} for {i} in range(1, len({seq})) "
               "if {seq}[{i}] > {seq}[{i} - 1] * {k} and {seq}[{i}] > {limit}), "
               "{default}) and {out} >= 1",
     miss="It started at zero and read the position before the first one, "
          "which on a list is the last one and is always a surprise."),

_art("coliseum", "seer", "THE ONE THING THAT DISAGREES, UNDER A CLOCK",
     "{out} = next((({i}, {a}, {b}) for {i}, ({a}, {b}) in "
     "enumerate(zip({first}, {second})) if {cost}({a}, {b}) > {limit}), {default})",
     idiom="a nested unpack, a call in the condition, and a default, in one pass",
     composes=("pairing", "numbering", "sift", "least"),
     note="Everything the Seer knows, in the region that gives you one reading "
          "and takes the page away.",
     demo={"xs": "[1, 2, 3]", "ys": "[1, 9, 3]",
           "gap": "lambda x, y: abs(x - y)", "cap": "3", "at": "None"},
     example={"out": "at", "i": "k", "a": "p", "b": "q", "first": "xs",
              "second": "ys", "cost": "gap", "limit": "cap", "default": "None"},
     assertion="{out} == next((({i}, {a}, {b}) for {i}, ({a}, {b}) in "
               "enumerate(zip({first}, {second})) if {cost}({a}, {b}) > {limit}), "
               "{default}) and {out} is not None",
     miss="It compared the pair against the bound instead of pricing it first. "
          "The tool goes between them."),


ART_BY_ID: dict = {a.id: a for a in ARTS}
ARTS_BY_CLASS: dict = {c: tuple(a for a in ARTS if a.class_id == c)
                       for c in CLASS_IDS}
ARTS_BY_REGION: dict = {row[1]: tuple(a for a in ARTS if a.region == row[1])
                        for row in REGION_LADDER}


# ===========================================================================
# How a sage is found
# ===========================================================================
# Not one of these is a tile you walk over, and not one of them is a purchase.
# Every clause is evidence the game already records, written as data so that
# any module can evaluate it and so the codex can draw a progress bar for a
# person nobody has met.
#
# The first eleven clause kinds are `pets.DISCOVERY_CHECKS` verbatim — same
# names, same fields, same evidence dict — because a second vocabulary for
# "what has this player done" is a second answer to the question. The rest are
# new, and every one of them reads something the combat and encounter loops
# already count. The value in each pair is (evidence key, how it reads).

SAGE_CHECKS: dict = {
    # -- shared with pets.py, clause-for-clause ----------------------------
    "family_unaided":    ("families", "unaided clears in {family}"),
    "skill_unaided":     ("skills", "{skill} unaided clears"),
    "skill_mastery":     ("skills", "{skill} mastery"),
    "boss_unaided":      ("bosses_unaided", "{boss} beaten with nothing cast"),
    "region_cleared":    ("regions_cleared", "{region} cleared"),
    "dungeon_depth":     ("dungeons", "{dungeon} depth reached"),
    "retest_survived":   ("retests", "{skill} memory ambushes survived"),
    "no_hint_streak":    ("no_hint_streak", "consecutive clears with no help"),
    "perf_cleared":      ("perf_cleared", "performance trials cleared"),
    "probes_correct":    ("probes_correct", "correct probes"),

    # -- new: what the typed-combat loop already counts ---------------------
    # A sage is found by CASTING, mostly, because a sage teaches a cast.
    "clean_casts":       ("clean_cast_streak",
                          "casts in a row that parsed and named real things"),
    "recalled_casts":    ("recalled_casts",
                          "casts made at RECALLED, from memory, with no ghost"),
    "region_clears":     ("region_clears", "encounters cleared in {region}"),
    "regions_touched":   ("regions_touched", "regions with at least one clear"),
    "lifo_clears":       ("lifo_clears",
                          "encounters cleared in the reverse of the order "
                          "they were offered"),
    "first_try":         ("first_try", "{skill} clears on the first submission"),
    "lineage_pair":      ("lineage_pairs",
                          "problems cleared in two different skins"),
    "beat_own_time":     ("beat_own_time", "personal bests broken on a rematch"),
    "root_cause_named":  ("root_cause_correct",
                          "failures named before the diagnosis rendered"),
    "arts_known":        ("arts", "secret arts already learned"),
}


# WHERE EACH EVIDENCE KEY IS SUPPOSED TO COME FROM, AND WHAT IT LOOKS LIKE.
#
# `engine.Game._pet_evidence()` already assembles most of this dict for
# `pets.newly_found`, and every clause above that reuses a pets key works
# today. The eight keys below are new, this module invented them, and until
# something fills them NINE OF THE SIXTEEN SAGES CANNOT BE FOUND — `mines` most
# starkly, because `lifo_clears` is its only condition.
#
# That is a wiring fact rather than a design fault and it is written down here,
# as data, so it is discovered by reading `self_check()["wiring"]` rather than
# by a player never meeting a sage. Each row is the key, the shape, and the one
# sentence that says how to count it.
# The evidence keys inherited from `pets.py` clause-for-clause. `engine.Game.
# _pet_evidence()` already returns every one of them, which is why the clauses
# built on them work today and the ones below do not. Stated as data rather than
# derived by introspecting the engine, because a check that silently degrades
# when `inspect.getsource` cannot read a file is a check that reports the wrong
# answer instead of no answer.
PETS_SHARED_KEYS: frozenset = frozenset({
    "families", "skills", "bosses_unaided", "regions_cleared", "dungeons",
    "retests", "no_hint_streak", "perf_cleared", "probes_correct",
})

EVIDENCE_SOURCES: dict = {
    "clean_cast_streak": (
        "int",
        "Casts in a row that parsed and named real things — layer 1 and layer "
        "2 both passed. Reset by a cast that did not. `incantation.cast` "
        "already distinguishes the two failures from a wrong answer."),
    "recalled_casts": (
        "int",
        "Casts made at tier MAX_TIER with no ghost on screen, cumulative."),
    "region_clears": (
        "{region_id: int}",
        "Encounters cleared per region, cumulative. The attempts table has "
        "the realm on every row."),
    "regions_touched": (
        "int or [region_id]",
        "How many regions have at least one clear in them."),
    "lifo_clears": (
        "int",
        "Encounters cleared in the reverse of the order they were offered in, "
        "cumulative. The offer order is already recorded when a camp is built."),
    "first_try": (
        "{skill: int}",
        "Clears where `submits <= 1`, per skill. `_artifact_conditions` "
        "already computes `no_failed_submission` from the same field."),
    "lineage_pairs": (
        "int",
        "Problems cleared in two different skins — two ids sharing a "
        "`lineage_id`, both solved. `corpus.assign_lineage` owns the pairing."),
    "beat_own_time": (
        "int",
        "Rematches that came in under the player's own previous best on that "
        "problem, cumulative."),
    "root_cause_correct": (
        "int",
        "Failures where the player named the cause before the diagnosis "
        "rendered, and was right."),
    "arts": (
        "[art_id]",
        "This module's own. Fold in `sages.evidence_patch(save.sages)`."),
}


# The six registers. A sage is one person; this is which of their six faces is
# turned toward you, and it is decided by what you walked in able to learn.
FACE_TITLES: dict = {
    "analyst": "the Wizard",
    "berserker": "the Warrior",
    "archivist": "the Lorekeeper",
    "warden": "the Templar",
    "artificer": "the Smith",
    "seer": "the Augur",
}

# What a returning failure is met with, per register. Authored once rather than
# ninety-six times, because "you came back" is a thing the class hears, not a
# thing the place says. The PLACE's half of that sentence is the sage's own
# `fail_lines`, which name the rung you actually died on.
CLASS_RETURN: dict = {
    "analyst": "You came back with a better model, or you came back with the "
               "same one. Only one of those is worth the walk.",
    "berserker": "Again, then. You were never going to leave it.",
    "archivist": "You have been away long enough for it to be a real test. "
                 "That was not a kindness.",
    "warden": "You know where it breaks now. Say so before you start this time.",
    "artificer": "You have had time to build something since. Show me what.",
    "seer": "You have read it twice now. The second reading is the one that "
            "counts.",
}


# ---------------------------------------------------------------------------
# The gauntlet frame
# ---------------------------------------------------------------------------
# Five rungs, in this order, always. A three-stage gauntlet is rungs 1, 2 and 5;
# a four-stage one inserts the region's own third rung; a five-stage one adds
# the ambush. The last rung is never anything else:
#
#   THE PROOF. Write, in full Python, the thing the secret art says in one line.
#   The art is handed over AFTER that, and only after, which is the whole reason
#   this is a gauntlet and not a chest. You are not given a shortcut to
#   something you cannot do; you are given a shortcut to something you have just
#   demonstrably done.

STAGE_FRAME: tuple = (
    ("name",   "Name the family",        "PATTERN_ENCOUNTER"),
    ("write",  "Write it",               "CODE_BATTLE"),
    ("edges",  "Survive the region",     ""),           # kind is per sage
    ("recall", "Something from further back", "MEMORY_AMBUSH"),
    ("proof",  "The proof",              "CODE_BATTLE"),
)

# Difficulty per rung, per region tier. Nothing above HARD is authored here:
# `self_check()` reports how many problems the live corpus actually holds at
# each of these, and `resolve_gauntlet` steps DOWN the ladder rather than
# resolving to nothing.
DIFFICULTY_LADDER: dict = {
    0:  ("TUTORIAL", "TUTORIAL", "EASY",   "EASY",   "EASY"),
    1:  ("TUTORIAL", "EASY",     "EASY",   "EASY",   "EASY"),
    2:  ("EASY",     "EASY",     "EASY",   "EASY",   "MEDIUM"),
    3:  ("EASY",     "MEDIUM",   "EASY",   "EASY",   "MEDIUM"),
    4:  ("EASY",     "MEDIUM",   "MEDIUM", "EASY",   "MEDIUM"),
    5:  ("EASY",     "MEDIUM",   "MEDIUM", "EASY",   "MEDIUM"),
    6:  ("MEDIUM",   "MEDIUM",   "MEDIUM", "EASY",   "MEDIUM"),
    7:  ("MEDIUM",   "MEDIUM",   "MEDIUM", "MEDIUM", "MEDIUM"),
    8:  ("MEDIUM",   "MEDIUM",   "MEDIUM", "MEDIUM", "MEDIUM"),
    9:  ("MEDIUM",   "MEDIUM",   "HARD",   "MEDIUM", "MEDIUM"),
    10: ("MEDIUM",   "MEDIUM",   "HARD",   "MEDIUM", "MEDIUM"),
    11: ("MEDIUM",   "MEDIUM",   "HARD",   "MEDIUM", "HARD"),
    12: ("MEDIUM",   "MEDIUM",   "HARD",   "MEDIUM", "HARD"),
    13: ("MEDIUM",   "MEDIUM",   "HARD",   "MEDIUM", "HARD"),
    14: ("MEDIUM",   "HARD",     "HARD",   "MEDIUM", "HARD"),
    15: ("MEDIUM",   "HARD",     "HARD",   "HARD",   "HARD"),
}


def stage_count(tier: int) -> int:
    """Three at the bottom of the map, four in the middle, five at the top."""
    if tier <= 3:
        return 3
    if tier <= 11:
        return 4
    return 5


def _rungs(tier: int) -> tuple:
    """Which of the five frame rungs this tier's gauntlet actually uses."""
    count = stage_count(tier)
    if count == 3:
        return (0, 1, 4)
    if count == 4:
        return (0, 1, 2, 4)
    return (0, 1, 2, 3, 4)


SAGES: list = []


def _face(class_id: str, name: str, greeting: str, creed: str,
          trial: str) -> dict:
    return {"class_id": class_id, "name": name, "greeting": greeting,
            "creed": creed, "trial": trial}


def _sage(region_key: str, unnamed: str, scar: str, blurb: str, *,
          where: str, how: str, needs: tuple, first_words: str,
          edges_kind: str, demands: dict, prefer: dict,
          fail_lines: tuple, on_clear: str, faces: tuple) -> Sage:
    meta = REGION_META[region_key]
    tier = meta["tier"]
    ladder = DIFFICULTY_LADDER[tier]
    stages = []
    for index in _rungs(tier):
        key, label, kind = STAGE_FRAME[index]
        stages.append(Stage(
            key=key, label=label,
            kind=(edges_kind if key == "edges" else kind),
            difficulty=ladder[index],
            pattern=("" if key in ("recall",) else meta["pattern"]),
            realm=("" if key == "recall" else meta["region"]),
            demands=demands[key],
            prefer=tuple(prefer.get(key, ())),
        ))
    built = Sage(
        id=region_key, region=meta["region"], tier=tier, unnamed=unnamed,
        scar=scar, blurb=blurb,
        discovery=Discovery(region=meta["region"], where=where, how=how,
                            needs=tuple(needs), first_words=first_words),
        stages=tuple(stages), fail_lines=tuple(fail_lines), on_clear=on_clear,
        faces=tuple(Face(class_id=row["class_id"], name=row["name"],
                         title=FACE_TITLES[row["class_id"]],
                         greeting=row["greeting"], creed=row["creed"],
                         trial=row["trial"],
                         returning=CLASS_RETURN[row["class_id"]],
                         art=ART_BY_ID["art_%s_%s" % (region_key,
                                                      row["class_id"])])
                    for row in faces),
    )
    SAGES.append(built)
    return built


# ===========================================================================
# The sixteen
# ===========================================================================

_sage(
    "village", "THE ONE WHO SWEEPS THE PORCH",
    scar="A long burn up the inside of the left forearm, the shape of a "
         "stack trace.",
    blurb="Somebody has been keeping the step of the half-rebuilt house clear "
          "since before you arrived, and has never once been inside it. They "
          "will not say what they were before. Six people have asked and six "
          "people got six different answers, all of them true.",
    where="The porch of the half-rebuilt house, at the hour when the village "
          "is still deciding whether to exist today.",
    how="Go back. Beat three things you have already beaten, days later, "
        "disguised, with no help — and the porch will have somebody on it.",
    needs=({"kind": "retest_survived", "skill": "", "count": 3},
           {"kind": "no_hint_streak", "count": 3}),
    first_words="Everybody walks forward. You are the first one this month to "
                "walk back, and back is where the thing you skipped is.",
    edges_kind="EDGE_CASE_TRAP",
    demands={
        "name": "Say what family this belongs to before you touch it.",
        "write": "Now write it. Small. Correctly.",
        "edges": "The empty one. The one-element one. The one where they are "
                 "all the same.",
        "recall": "Something from the first hour you played. Say it again.",
        "proof": "Write, in as many lines as you need, what your art says in "
                 "one. You do not get the one line until the many exist.",
    },
    prefer={"proof": ("ob-keep-long-words", "ob-double-each", "ob-initials")},
    fail_lines=(
        "You could not name it. That is not a failure of nerve, it is a gap, "
        "and gaps close.",
        "It did not run. Go and make things run for a while.",
        "The empty case took you. It always takes people here first.",
        "You had it once. Having it once is not having it.",
        "You wrote the long version and the long version was wrong. Come back "
        "when it is not.",
    ),
    on_clear="There. Now you have a thing you can say in one line that you "
             "could only say in six this morning. That is the only kind of "
             "progress there is.",
    faces=(
        _face("analyst", "TESSELL",
              "You have been standing there working out whether to speak. Keep "
              "doing that, it is the whole job.",
              "Say what you think is true before you find out. Otherwise you "
              "were never wrong, you were just late.",
              "Before your first run of the proof, name its cost."),
        _face("berserker", "GRIP",
              "Do not tell me what you are going to do.",
              "The first draft is a weapon. The second draft is the one you "
              "keep.",
              "Submit the proof once before you are comfortable with it."),
        _face("archivist", "OLDCOMB",
              "You came back. Almost nobody comes back. Sit down.",
              "Nothing is learned once. Everything here is learned three "
              "times, at increasing distance.",
              "The proof is something you have met before. Notice when."),
        _face("warden", "SILL",
              "Before you cross the step: what would break it.",
              "Name what breaks it, then write it. In that order, or you are "
              "just guessing twice.",
              "Call two classes of input before the proof runs."),
        _face("artificer", "PEG",
              "You are carrying a helper you wrote last week. Use it.",
              "Build it once, properly, and then never build it again.",
              "The proof must contain a function you can call twice."),
        _face("seer", "WICK",
              "It is already on the screen. It has been for a while.",
              "Read the code you have before writing code you do not.",
              "Before the proof, say which line you expect to be wrong."),
    ),
)

_sage(
    "fields", "THE ONE AT THE END OF THE SEVENTH FURROW",
    scar="Same burn, same forearm. They deny having been in the village.",
    blurb="The weeds in this field are malformed statements, and somebody has "
          "been pulling them and stacking them in rows that are, on "
          "inspection, sorted. They stack them by what kind of wrong they are.",
    where="The end of the seventh furrow, where the pulled weeds are stacked "
          "in rows that are clearly sorted by something.",
    how="Walk a furrow end to end. Twelve casts in a row in the Fields with "
        "nothing that failed to parse and nothing named that was not there — "
        "and someone will be standing at the end of it.",
    needs=({"kind": "clean_casts", "count": 12},
           {"kind": "region_clears", "region": "fields_of_syntax", "count": 5}),
    first_words="Twelve in a row and not one NameError. Do you know what most "
                "people's twelve look like. I have them in a pile.",
    edges_kind="DEBUG_BATTLE",
    demands={
        "name": "What is this. One word, and it is not the word on the sign.",
        "write": "Write it without a syntax error. That is the entire ask.",
        "edges": "Here is one that is wrong. Find where, not why.",
        "recall": "You knew this last week.",
        "proof": "Write your art out flat, one idea per line, and make it work "
                 "before it is allowed to become short.",
    },
    prefer={"proof": ("ob-index-of", "ob-add-lists", "ob-top-words")},
    fail_lines=(
        "Wrong family. The sign is a weed too.",
        "It would not parse. Go and type for an hour, then come back.",
        "You found why before you found where, and then you fixed the wrong "
        "line.",
        "You had that in the Village.",
        "The flat version is still wrong. Short and wrong is worse than long "
        "and wrong, so we will stay long.",
    ),
    on_clear="Take it. It is one line and it took you eleven to earn, which "
             "is the correct ratio.",
    faces=(
        _face("analyst", "QUILL",
              "You have read the whole field before stepping into it. Good. "
              "Now tell me which row is the wrong one.",
              "A guess said out loud at minute one is cheap. The same guess "
              "discovered at minute twenty is the timed practical.",
              "Declare the shape of the proof before you write a line of it."),
        _face("berserker", "HARROW",
              "Stop reading. The field is not going to get simpler.",
              "Type something, run it, read what broke, type again. Do not "
              "stall.",
              "Get something running inside half the time, however wrong."),
        _face("archivist", "SHEAF",
              "You have pulled this weed before. In the Village. Twice.",
              "Meet it again, disguised, on a delay, until it is yours.",
              "The proof is a shape you have seen. Say where."),
        _face("warden", "HEDGE",
              "A hedge is a statement about what is not allowed through.",
              "Before the first run, say which inputs you expect to break "
              "this.",
              "Name the malformed input before you touch the program."),
        _face("artificer", "SCYTHE",
              "You are pulling weeds one at a time. Make something that pulls "
              "rows.",
              "Write the helper, name the interface, come back and make it "
              "shorter.",
              "The proof must factor out the part you would otherwise write "
              "twice."),
        _face("seer", "GLEAN",
              "Everything you need is lying on the ground already.",
              "Trace it by hand. The interpreter is not a reading aid.",
              "Predict the value at the halfway line before running the "
              "proof."),
    ),
)

_sage(
    "highlands", "THE KEYWARD",
    scar="The burn again. On this one it has been tattooed over, badly, with "
         "a key.",
    blurb="Every vault on this plateau opens to exactly one rune, and there is "
          "one vault up on the scarp with no keyhole at all. Somebody lives "
          "behind it. They will open it for a person who has stopped guessing.",
    where="The keyless vault on the north scarp, which opens from the inside "
          "and only when the knocking stops.",
    how="Beat the Hash Titan with nothing cast, and be right about ten things "
        "before they happened. Then walk up the scarp and do not knock.",
    needs=({"kind": "boss_unaided", "boss": "hash_titan"},
           {"kind": "probes_correct", "count": 10}),
    first_words="Ten predictions and ten of them true. That is not luck twice, "
                "and it stopped being luck somewhere around the fourth.",
    edges_kind="EDGE_CASE_TRAP",
    demands={
        "name": "Dict, set, or neither. You have three seconds and one word.",
        "write": "Count them. Group them. Do not sort anything.",
        "edges": "The key that is not there. The count that reaches zero. The "
                 "key that is a list.",
        "recall": "A pattern from a region you left behind.",
        "proof": "Write the whole tally and the whole ranking out longhand, "
                 "with loops, and get it right.",
    },
    prefer={"proof": ("ah-two-sum-count", "ah-top-k-frequent",
                      "ah-longest-consecutive")},
    fail_lines=(
        "You reached for a list. The plateau is full of people who reached for "
        "a list.",
        "It counted, and then it sorted, and the sort was the whole cost.",
        "A missing key took you, which is how most people lose their first "
        "vault and their fourth.",
        "You have forgotten something you paid for.",
        "The longhand version is not right yet, and I am not shortening "
        "something that is not right.",
    ),
    on_clear="One line. It replaces the eleven you just wrote, and you will "
             "know exactly which eleven, which is the difference between "
             "knowing this and having read it.",
    faces=(
        _face("analyst", "CIPHER",
              "You want to know what is in the vault before you open it. So "
              "did I. It is a dict.",
              "Name the pattern family and the complexity before the first "
              "keystroke.",
              "State the proof's complexity in advance and be held to it."),
        _face("berserker", "BRAY",
              "There are nine hundred vaults. Start opening them.",
              "Being wrong quickly is the only thing standing between most "
              "people and a first line.",
              "Three wrong submissions before the clock's halfway mark, or "
              "you were reading."),
        _face("archivist", "KEYWARD",
              "You have seen the inside of a vault like this one. In the "
              "Fields. It had two keys then.",
              "Retrieval is the practice. Reading it again is not.",
              "The proof arrives disguised. Name what it really is."),
        _face("warden", "LATCH",
              "A latch is a question about what is allowed in. So is a key.",
              "A suite every wrong answer passes is not a suite.",
              "Name the missing-key case before the proof runs, or it will "
              "find it for you."),
        _face("artificer", "TUMBLER",
              "You have written `counts.get(k, 0) + 1` forty times. Give it a "
              "name.",
              "Decomposition, interfaces, and the judgement to reuse rather "
              "than retype.",
              "The proof's counting and the proof's ranking must be separate "
              "functions."),
        _face("seer", "SOUND",
              "You can hear which vault is empty by knocking on it. So can I.",
              "Name the failure category before the diagnosis renders.",
              "Say which of the two tallies is wrong before you compare them."),
    ),
)

_sage(
    "stringwood", "THE ANAGRAMMER",
    scar="The burn. Under it, in the same hand, the word LISTEN, then SILENT "
         "underneath.",
    blurb="The trees here reorder their letters when nobody is looking, and "
          "there is one grove where they do not, because somebody has been "
          "holding them still for a very long time by naming them correctly.",
    where="The still grove at the centre, where the letters have stopped "
          "moving because something has fixed their names.",
    how="Take the same exit twice. Clear three anagram encounters with no "
        "help, and get your STRING past thirty-five, and the grove will be "
        "where it was the first time.",
    needs=({"kind": "family_unaided", "family": "anagrams", "count": 3},
           {"kind": "skill_mastery", "skill": "STRING", "value": 35}),
    first_words="You came out of the same clearing twice and it was the same "
                "clearing. Nobody manages that in the first week.",
    edges_kind="EDGE_CASE_TRAP",
    demands={
        "name": "Two words, same letters. What is the key.",
        "write": "Group them. In one pass.",
        "edges": "Empty string. Different lengths. Casing. Spaces that count.",
        "recall": "Something you learned two regions ago, in a different "
                  "coat.",
        "proof": "Write the canonical form out by hand, and the grouping, and "
                 "the join. Three ideas, three blocks, all correct.",
    },
    prefer={"proof": ("ah-group-anagrams", "sw-find-anagrams",
                      "sc-first-unique-char")},
    fail_lines=(
        "You said STRING. Everything here is a string; that is not a family, "
        "that is the weather.",
        "It compared every scroll against every other. The wood has time. You "
        "do not.",
        "The empty word took you, or the capital letter did.",
        "It went. Come back when it has come back.",
        "One of the three blocks is wrong and I cannot tell which from here, "
        "which means neither can you yet.",
    ),
    on_clear="The letters will hold still for you now. Not because of the art. "
             "Because of what you had to know to be given it.",
    faces=(
        _face("analyst", "LEXIS",
              "You are about to say `sorted`. Say why first.",
              "Reason before writing, and the writing takes one attempt.",
              "Declare the key function before you write the grouping."),
        _face("berserker", "GNASH",
              "Words. Endless words. Break one and see what falls out.",
              "Iterate loudly. The wood cannot keep up with someone who is "
              "already wrong three times.",
              "The proof, submitted before you have re-read your own key."),
        _face("archivist", "CONCORD",
              "A concordance is a thing that remembers where every word was.",
              "Everything here is learned three times, at increasing distance.",
              "The proof is a retest as well. Both count."),
        _face("warden", "SPELT",
              "Which spelling did you test, and which spelling did you file.",
              "The edge is the case you normalised on one side and not the "
              "other.",
              "Name the casing case before the proof runs."),
        _face("artificer", "LIGATURE",
              "You keep writing the same normaliser. Bind it once.",
              "A tool used twice pays for itself; a tool used ten times is a "
              "career.",
              "The canonical form must be a named function in the proof."),
        _face("seer", "ACROSTIC",
              "Read down the first letters. Then read the code.",
              "The bug is on the screen and it has been for some minutes.",
              "Say where two words first stop agreeing, before you run it."),
    ),
)

_sage(
    "caverns", "THE ZEROTH",
    scar="The burn, and above it a row of small scars, numbered, starting at "
         "zero.",
    blurb="The alcoves here are numbered from zero and the last one is always "
          "one short of the count. Somebody carved those numbers. They are "
          "still down there, and they have opinions about the people who "
          "start at one.",
    where="Alcove zero, which everybody walks past on the way to alcove one.",
    how="Name nothing that is not there. Twenty casts in a row with no "
        "unbound name, and three ARRAY encounters cleared with no help. Then "
        "look in the first alcove instead of the second.",
    needs=({"kind": "clean_casts", "count": 20},
           {"kind": "skill_unaided", "skill": "ARRAY", "count": 3}),
    first_words="Twenty casts and every name you typed was a name that "
                "existed. You would be amazed how rare that is down here.",
    edges_kind="EDGE_CASE_TRAP",
    demands={
        "name": "Index, slice, or scan. Pick.",
        "write": "Do it in one pass over the alcoves.",
        "edges": "Zero. One. The last one. The one past the last one.",
        "recall": "Something with a key in it, from the plateau.",
        "proof": "Write the index arithmetic out by hand and defend every "
                 "plus one.",
    },
    prefer={"proof": ("ah-three-sum", "bk-loopbound-find-index",
                      "cx-lookup-four-ways")},
    fail_lines=(
        "Wrong shape. There is a difference between reading positions and "
        "reading values, and it is the whole cavern.",
        "It went round twice. The alcoves do not move; you do not need to "
        "either.",
        "Off by one. Everybody. Every time. Come back.",
        "The plateau wants its pattern back.",
        "One of your plus ones is undefended and I think you know which.",
    ),
    on_clear="Alcove zero. You were the first person in a season to look in it "
             "before looking in alcove one.",
    faces=(
        _face("analyst", "ORDINAL",
              "You counted the alcoves before entering. That is the correct "
              "order of operations.",
              "Know the cost before you pay it, and you only pay it once.",
              "Name the loop's bound out loud before writing the loop."),
        _face("berserker", "HEW",
              "Stop counting and start cutting.",
              "Wrong fast beats right slow, at least until the third attempt.",
              "One submission inside half the target, whatever it costs you."),
        _face("archivist", "ZEROTH",
              "You have been in a room numbered like this before. Two regions "
              "back.",
              "Nothing is learned once, and indices are learned about six "
              "times.",
              "The proof will be handed to you again in a week. Write it for "
              "that person."),
        _face("warden", "LINTEL",
              "A lintel is what stops the roof arriving. Bounds are the same "
              "idea.",
              "Name what breaks it, then write it.",
              "Call the empty case and the single-element case in advance."),
        _face("artificer", "GANTRY",
              "You keep writing `range(len(x))`. There is a better thing and "
              "you know it.",
              "Build the access pattern once and stop re-deriving it.",
              "The proof must not repeat an index expression twice."),
        _face("seer", "PLUMB",
              "A plumb line tells you what is vertical without asking the "
              "wall.",
              "Trace it by hand. The wall lies; the line does not.",
              "State what the index holds at the last iteration, before you "
              "run it."),
    ),
)

_sage(
    "marsh", "THE ONE ON THE CAUSEWAY",
    scar="The burn, sodden and pale, on an arm that has been in this water a "
         "long time.",
    blurb="There is a glowing frame that slides across the reeds, widening "
          "right and shrinking left, and somebody rebuilt the causeway "
          "underneath it so that the frame would have something to slide "
          "along. They have never once stepped off it to start again.",
    where="The causeway stone that is not a stone, below the waterline, at the "
          "point where the frame is widest.",
    how="Never restart a scan. Clear five sliding-window encounters on the "
        "first submission, and six encounters in the Marsh at all, and the "
        "stone will be a door.",
    needs=({"kind": "first_try", "skill": "SLIDING_WINDOW", "count": 5},
           {"kind": "region_clears", "region": "sliding_window_marsh",
            "count": 6}),
    first_words="Five, and not one of them started over. The marsh eats people "
                "who start over. It is mostly what the marsh is.",
    edges_kind="COMPLEXITY_DUEL",
    demands={
        "name": "Fixed width or variable. Say which, and how you know.",
        "write": "Widen from the right. Give ground on the left when the ward "
                 "breaks. Do not start the scan again.",
        "edges": "Now tell me what it costs, and why it is not the square.",
        "recall": "A counting pattern from the plateau, disguised.",
        "proof": "Write both walls, the ward, and the shrink, longhand, and "
                 "make it linear.",
    },
    prefer={"proof": ("sw-longest-no-repeat", "sw-k-distinct",
                      "sw-k-categories")},
    fail_lines=(
        "You could not say which kind of window it was, which means you were "
        "going to write both and hope.",
        "It restarted. I heard it from here.",
        "You said it was linear and it was not, and the marsh knows the "
        "difference.",
        "The plateau's lesson did not survive the water.",
        "The shrink is wrong. It is always the shrink.",
    ),
    on_clear="The frame will hold its own width for you now. Do not mistake "
             "that for the marsh having got easier.",
    faces=(
        _face("analyst", "LEE",
              "The lee is the still side. You have been standing on it, "
              "thinking, and that is allowed.",
              "Name the invariant before you move either wall.",
              "State the window's invariant before the proof's first run."),
        _face("berserker", "SLOG",
              "Wade. The bottom is closer than it looks.",
              "Move the wall, see what breaks, move it back. Three times is "
              "faster than thinking once.",
              "Submit before the ward is finished. Twice."),
        _face("archivist", "TIDEBOOK",
              "A tidebook is a record of a thing that will happen again on "
              "schedule.",
              "You will meet this window in the Coliseum with a clock on it. "
              "Learn it now, cheaply.",
              "The proof's ambush is the same window, three regions later."),
        _face("warden", "CAUSEWAY",
              "A causeway is a promise about where the water is not.",
              "The ward is the test. Write the ward first.",
              "Name what makes the ward break, before it breaks."),
        _face("artificer", "SLUICE",
              "You keep writing the same shrink. Make it a thing with a name.",
              "A window is a tool, not a technique. Build it once.",
              "The proof must have `expand` and `shrink` as separate callables."),
        _face("seer", "WATERMARK",
              "The watermark shows you where it was, not where it is.",
              "Read the state at the moment the ward broke. That is the whole "
              "bug.",
              "Say which reed the ward breaks on, before running the proof."),
    ),
)

_sage(
    "pass", "THE ONE WHO CARRIES BOTH LANTERNS",
    scar="The burn, and both hands equally calloused, which is unusual.",
    blurb="Two lanterns start at either end of the bridge and converge, every "
          "night, and somebody has been lighting both of them. From the "
          "middle. Which means walking out and back twice, every night, for "
          "years, rather than admit that one end is closer.",
    where="The middle of the span, where both lanterns are always already lit "
          "and there are two sets of footprints going out and none coming "
          "back.",
    how="Solve the same problem from both ends. Clear two problems in two "
        "different skins, and four TWO_POINTER encounters with no help, and "
        "walk to the middle rather than across.",
    needs=({"kind": "lineage_pair", "count": 2},
           {"kind": "skill_unaided", "skill": "TWO_POINTER", "count": 4}),
    first_words="You recognised the same problem wearing a different coat. "
                "Twice. That is the only trick in this entire realm and you "
                "found it on a bridge.",
    edges_kind="EDGE_CASE_TRAP",
    demands={
        "name": "Two pointers, or a hash map. They are not the same problem "
                "and they look identical.",
        "write": "Both ends. Neither turns back.",
        "edges": "They cross. They meet. They start equal. There are two of "
                 "them and they are the same.",
        "recall": "Something from the caverns, and it is about indices.",
        "proof": "Write the convergence out longhand, including the reason "
                 "moving the taller wall is wrong.",
    },
    prefer={"proof": ("tp-container-water", "ll-cycle-entry",
                      "sec-risk-pairing")},
    fail_lines=(
        "You reached for a dict. Sometimes that is right. Today it was the "
        "expensive kind of right.",
        "One of them turned back. The whole pattern is that neither of them "
        "does.",
        "They crossed and you kept going. The pass ends where they meet.",
        "The caverns want a word with you about indices.",
        "You moved the taller wall and lost the width for nothing, and then "
        "wrote a paragraph defending it.",
    ),
    on_clear="Both lanterns, one hand each. It was always going to be one "
             "person doing it; it just took a while to be you.",
    faces=(
        _face("analyst", "MERIDIAN",
              "A meridian is a line you agree on so that two people can "
              "describe the same place.",
              "Declare which end is which before you move either.",
              "Name which pointer moves on a mismatch, in advance."),
        _face("berserker", "CRAG",
              "The span is not going to narrow itself.",
              "Move something. Find out. Move it back.",
              "First submission before you have checked the crossing case."),
        _face("archivist", "LANTERN",
              "You lit this bridge once already, in the Caverns, with one "
              "hand.",
              "The same idea, further apart, until it stops being an idea and "
              "becomes a reflex.",
              "The ambush will be this pattern under another name."),
        _face("warden", "CAIRN",
              "A cairn is somebody's note about where the edge was.",
              "The crossing condition is an edge case wearing a while loop.",
              "Call the crossing case before the proof runs."),
        _face("artificer", "BRIDLE",
              "Two pointers is a shape. Give the shape a signature.",
              "Build the walk once; the predicate is what changes.",
              "The proof must take the comparison as a parameter."),
        _face("seer", "HORIZON",
              "You can see the far lantern from here. That is the entire "
              "method.",
              "Predict where they meet before you let them walk.",
              "State the meeting index before running the proof."),
    ),
)

_sage(
    "mines", "THE ONE ON THE NINTH CART",
    scar="The burn, black with coal dust, which has not improved it.",
    blurb="Ore carts unload from the top and the lift takes the oldest first, "
          "and somebody has been riding the ninth cart down and back for long "
          "enough that the miners have stopped counting it as a cart.",
    where="The ninth cart, which goes down full and comes up full and which "
          "nobody has ever seen unloaded.",
    how="Take the top one first, for once. Clear the last five encounters the "
        "mines offered you in the reverse of the order they were offered, and "
        "the ninth cart will wait for you.",
    needs=({"kind": "lifo_clears", "count": 5},),
    first_words="Last in, first out. You did it with your own afternoon rather "
                "than with a list, which is the only way anybody ever "
                "actually learns it.",
    edges_kind="EDGE_CASE_TRAP",
    demands={
        "name": "Stack or queue. Which end does the work leave from.",
        "write": "One structure. The right one.",
        "edges": "Empty. One item. Every item the same. The pop that should "
                 "not have happened.",
        "recall": "Something from the marsh, and it is about a frame.",
        "proof": "Write the monotonic pass out longhand and say, in a comment, "
                 "why nothing is ever pushed twice.",
    },
    prefer={"proof": ("sq-next-greater", "sq-daily-temperatures",
                      "sq-simplify-path")},
    fail_lines=(
        "Wrong end. A cart taken from the bottom is a cave-in.",
        "You used both and needed one.",
        "It took from nothing. An empty tower has no top, and that was always "
        "going to be one of the cases.",
        "The marsh is calling in a debt.",
        "Something got pushed twice, which means the pass is not one pass.",
    ),
    on_clear="You can ride down now. Mind the ninth cart; it is somebody's "
             "house.",
    faces=(
        _face("analyst", "HEADFRAME",
              "The headframe is the part above ground that tells you what "
              "shape the mine is.",
              "Choose the structure before you write the loop; the loop then "
              "writes itself.",
              "Declare which end the work leaves from, before writing it."),
        _face("berserker", "SPOIL",
              "Spoil is the stuff you throw out. Most first drafts are spoil "
              "and that is fine.",
              "Push something. Pop it. Find out what fell.",
              "One submission before you have handled the empty tower."),
        _face("archivist", "SEAM",
              "A seam runs through several regions and comes up in all of "
              "them.",
              "You will be ambushed by a stack in the Wastes. Learn it here.",
              "The ambush will be a queue pretending to be a stack."),
        _face("warden", "PROP",
              "A prop holds up a roof that has not fallen yet.",
              "`if stack` before `stack[-1]`, every time, for ever.",
              "Call the empty case before the proof runs."),
        _face("artificer", "WINCH",
              "A winch is one machine that does two jobs depending which way "
              "you turn it.",
              "Deque, or two lists. Build it once and stop rebuilding.",
              "The proof must use one structure, not two."),
        _face("seer", "FIREDAMP",
              "Firedamp is invisible and it is what actually kills people.",
              "Read the state of the tower at the moment before the pop.",
              "Say what is on top at the halfway point, before running it."),
    ),
)

_sage(
    "citadel", "THE ONE WHO STANDS STILL WHEN THE FLOOR TURNS",
    scar="The burn, and a habit of keeping one hand flat against a wall.",
    blurb="The whole floor plan turns ninety degrees when the Golem stirs, and "
          "there is one person in the keep who does not turn with it. They "
          "have worked out which cell they are standing on in every possible "
          "orientation, and they did it without writing any of it down.",
    where="The cell that is the same cell after every quarter turn, which is "
          "not the middle and is not obvious.",
    how="Turn it without building a second one. Clear two performance trials "
        "in the Citadel and take MATRIX past forty, and the floor will leave "
        "you where you are.",
    needs=({"kind": "perf_cleared", "count": 2},
           {"kind": "skill_mastery", "skill": "MATRIX", "value": 40}),
    first_words="You rotated it in place. Everybody else allocates a second "
                "keep and the Golem takes it off them, every time, and they "
                "still do it.",
    edges_kind="COMPLEXITY_DUEL",
    demands={
        "name": "Transpose, rotate, or spiral. They are three things.",
        "write": "In place. The Golem takes anything you allocate.",
        "edges": "Now say what it costs in space, and mean it.",
        "recall": "Something from the mines, about which end.",
        "proof": "Write the whole rotation out longhand, both the transpose "
                 "and the reverse, and prove the indices.",
    },
    prefer={"proof": ("mx-rotate", "mx-spiral", "cx-grid-work")},
    fail_lines=(
        "Three different things and you named the wrong one, which is a whole "
        "different keep.",
        "You built a second matrix and the Golem has it now.",
        "You said constant space while holding a copy of the floor.",
        "The mines would like their lesson back.",
        "The indices do not survive a non-square keep, and this keep is not "
        "always square.",
    ),
    on_clear="Stand still. The floor does the turning. That is the art and it "
             "is also, as it happens, the advice.",
    faces=(
        _face("analyst", "CARDINAL",
              "North, east, south, west. Four states, and you can enumerate "
              "them before moving.",
              "Enumerate the states, then pick. Never pick and then discover "
              "the states.",
              "Name the four orientations before writing the rotation."),
        _face("berserker", "BASTION",
              "Hit it. It is a wall; walls are informative.",
              "Rotate it wrong once and the right indices become obvious.",
              "One submission with the indices unchecked."),
        _face("archivist", "BLAZON",
              "A blazon describes a shape so precisely that it can be redrawn "
              "from words.",
              "Say the transformation in words first; the indices follow.",
              "The ambush is a grid walk from the Caverns."),
        _face("warden", "MERLON",
              "A merlon is the bit of the battlement that is still there. The "
              "gaps are the point.",
              "Four edges, four ways out of the plane, four guards.",
              "Call the non-square case before the proof runs."),
        _face("artificer", "LATHE",
              "A lathe turns the work, not the tool.",
              "One rotation function, parameterised by how many quarter turns.",
              "The proof must handle one turn and three with the same code."),
        _face("seer", "SIGHTLINE",
              "A sightline crosses the keep whichever way it is facing.",
              "Read the coordinate, not the cell.",
              "Say which cell ends up at the origin, before running the "
              "proof."),
    ),
)

_sage(
    "forest", "THE ONE IN THE INNER GROVE",
    scar="The burn — and in the next clearing in, a smaller person with a "
         "smaller burn, and neither will discuss it.",
    blurb="Each clearing contains a smaller copy of the forest. Somebody is "
          "standing in the ninth one down. They have never gone further in, "
          "and they have never come out, and they insist those are the same "
          "decision.",
    where="The ninth clearing in, which is reached by trusting eight smaller "
          "copies to be correct.",
    how="Go down and come back with what the inner copy found. Reach the sixth "
        "floor of the Inner Grove and clear four RECURSION encounters with no "
        "help, and the ninth clearing will be a clearing.",
    needs=({"kind": "dungeon_depth", "dungeon": "inner_grove", "depth": 6},
           {"kind": "skill_unaided", "skill": "RECURSION", "count": 4}),
    first_words="Six down and back up carrying something. Most people get to "
                "three and start checking whether the forest is real.",
    edges_kind="COMPLEXITY_DUEL",
    demands={
        "name": "What is the smaller problem. Say it as a sentence.",
        "write": "Base case first. Then trust the smaller call.",
        "edges": "Now tell me how many calls, and whether the stack survives.",
        "recall": "Something from the Citadel, and it is about indices.",
        "proof": "Write the recurrence, the base case and the combine, "
                 "separately, and say which of the three is the one people "
                 "get wrong.",
    },
    prefer={"proof": ("rc-combination-sum", "so-bt-palindrome-partition",
                      "so-bt-n-queens")},
    fail_lines=(
        "You described the whole problem again, in smaller words. That is not "
        "a smaller problem.",
        "No base case. The forest is still going.",
        "It is exponential and you said it was not, and the ninth clearing "
        "heard you.",
        "The Citadel's lesson did not make it down here.",
        "The combine is wrong. It is almost always the combine.",
    ),
    on_clear="Go back up. Carry it. That is the whole of recursion and you can "
             "stop being frightened of it now.",
    faces=(
        _face("analyst", "DESCANT",
              "A descant is the line above the tune. State it, then sing it.",
              "Say what the smaller call returns before you write the call.",
              "State the recurrence in one sentence before writing it."),
        _face("berserker", "SPLIT",
              "Go in. You can always come back; that is literally the "
              "mechanism.",
              "Write the recursion without the base case, watch it die, add "
              "the base case.",
              "One submission that recurses before it terminates."),
        _face("archivist", "HEARTWOOD",
              "Heartwood is the part that stopped growing and started holding "
              "it up.",
              "The recursion you learn here becomes the memo you need in the "
              "Ruins.",
              "The ambush is a tree from the Canopy, one region early."),
        _face("warden", "BOLE",
              "The bole is where the trunk stops being roots. Every recursion "
              "has one.",
              "The base case is not an edge case. It is the case.",
              "Call the empty and single-node cases before the proof runs."),
        _face("artificer", "WITHY",
              "A withy bends without breaking because of how it was grown.",
              "The helper takes the accumulator. The public function does "
              "not.",
              "The proof must separate the wrapper from the recursion."),
        _face("seer", "UNDERSTORY",
              "Everything interesting is happening below eye level.",
              "Trace three frames by hand. Not thirty. Three.",
              "State what the third frame returns, before you run it."),
    ),
)

_sage(
    "canopy", "THE ONE WHO TOOK BOTH FORKS",
    scar="The burn, and a broken collarbone that healed at an angle, from a "
         "fall.",
    blurb="Every branch splits exactly twice and the path never rejoins, and "
          "somebody up there has walked every branch of this canopy, which "
          "means they have climbed down and back up an inhuman number of "
          "times rather than jump across.",
    where="The fork that is the same height on both sides, which is only "
          "findable by having measured both.",
    how="Take both forks. Two DFS encounters and two BFS encounters, cleared "
        "with no help, and it will become obvious that they were the same "
        "tree.",
    needs=({"kind": "skill_unaided", "skill": "DFS", "count": 2},
           {"kind": "skill_unaided", "skill": "BFS", "count": 2}),
    first_words="Depth and breadth, both, unaided. You now know the only thing "
                "this canopy has to teach, which is that they are the same "
                "walk with a different bag.",
    edges_kind="EDGE_CASE_TRAP",
    demands={
        "name": "Depth or breadth. And say what the bag is.",
        "write": "Walk it. Bring back one thing.",
        "edges": "Empty tree. One node. A node with one child, which is not a "
                 "leaf.",
        "recall": "Something recursive, from one clearing in.",
        "proof": "Write both walks, iteratively and recursively, and say what "
                 "changed.",
    },
    prefer={"proof": ("tr-validate-bst", "tr-all-path-sums", "tr-level-order")},
    fail_lines=(
        "You named the walk and not the bag, and the bag is the difference.",
        "It came back with nothing, or with everything.",
        "A node with one child took you. It is not a leaf. It has never been "
        "a leaf.",
        "The inner grove wants its recursion back.",
        "One of the two walks is wrong and it is the iterative one.",
    ),
    on_clear="Both forks. You will not have to choose again; you will just "
             "know which bag.",
    faces=(
        _face("analyst", "FORK",
              "Two branches. Two costs. Name both before climbing either.",
              "The stack and the queue are a decision, not a habit.",
              "Declare which traversal and why, before the first line."),
        _face("berserker", "LIMB",
              "Climb. If it holds, it held.",
              "Write the recursion, hit the recursion limit, write the loop.",
              "One submission that blows the stack."),
        _face("archivist", "ROOKERY",
              "A rookery is the same birds in the same trees, every year, "
              "which is how you learn to tell them apart.",
              "A tree walk is four lines you will retype two hundred times. "
              "Make them free.",
              "The ambush is a graph, which is a tree that stopped pretending."),
        _face("warden", "BOUGH",
              "A bough takes weight until it does not, and the warning is "
              "always the same sound.",
              "`is not None`, not `if node`. A node holding zero is a node.",
              "Call the falsy-value case before the proof runs."),
        _face("artificer", "TRELLIS",
              "A trellis is a shape you build so the growing has somewhere to "
              "go.",
              "One traversal, parameterised by what you do at each node.",
              "The proof must take the per-node action as a parameter."),
        _face("seer", "SKYLIGHT",
              "From up here you can see which branch is shorter. From down "
              "there you cannot.",
              "Read the shape before the code. The shape is the answer.",
              "Say which branch the walk reaches last, before running it."),
    ),
)

_sage(
    "wastes", "THE ONE WHO HAS WALKED EVERY ROAD",
    scar="The burn, and boots that have been resoled so many times that none "
         "of the original boot is left.",
    blurb="Every ruin here connects to several others, some routes shorter and "
          "some merely existing, and somebody has walked all of them. Not the "
          "useful ones. All of them. They can tell you which two ruins are "
          "not connected and there are only two.",
    where="The ruin that every road eventually reaches, which is not the one "
          "in the middle.",
    how="Visit every ruin. Clear at least one encounter in eleven different "
        "regions, and the roads will start converging on somewhere.",
    needs=({"kind": "regions_touched", "count": 11},
           {"kind": "skill_unaided", "skill": "BFS", "count": 3}),
    first_words="Eleven regions. You have been everywhere, which means you "
                "have seen the lattice from inside it, and almost nobody does.",
    edges_kind="COMPLEXITY_DUEL",
    demands={
        "name": "Shortest road, or any road. They are different searches.",
        "write": "Rings of light, or one committed path. Pick, and commit.",
        "edges": "Now the cost, and say it in nodes and edges, not in n.",
        "recall": "A structure from the mines, and which end it works from.",
        "proof": "Write the visited set, the frontier and the loop separately, "
                 "and say exactly when a node is marked.",
    },
    prefer={"proof": ("gr-topo-order", "gr-detect-cycle", "gr-count-islands")},
    fail_lines=(
        "Wrong search. Depth-first for a shortest path is the scenic route "
        "and the Necromancer sells tickets.",
        "It never terminated. Everything in this region that fails to terminate "
        "fails for one of two reasons, and you have met both of them.",
        "You said O(n) about a graph. There are two letters and you need both.",
        "The mines are owed a deque.",
        "One line of it is wrong and every other line is immaculate, which is the "
        "most expensive way there is for a search to be broken.",
    ),
    on_clear="Every road. Take it — and know that the reason it is worth "
             "having is that you walked them before you were given it.",
    faces=(
        _face("analyst", "LATTICE",
              "A lattice has a shape before it has a route.",
              "Name the search and its cost before the first enqueue.",
              "State V and E for the proof before writing it."),
        _face("berserker", "ROUT",
              "Pick a road. Any road. The map is made by walking.",
              "Run the search wrong, watch it loop, add the set.",
              "One submission with no visited set at all."),
        _face("archivist", "MILESTONE",
              "A milestone is somebody telling you how far you have come, "
              "which is a thing you forget.",
              "Every graph problem is this graph problem wearing a hat.",
              "The ambush is a grid, which is a graph with polite neighbours."),
        _face("warden", "TOLLGATE",
              "A tollgate is a place where you decide who has already paid.",
              "Mark it when you enqueue it, not when you pop it. That is the "
              "whole ward.",
              "Name the cycle case before the proof runs."),
        _face("artificer", "CAUSEWRIGHT",
              "A causewright builds the road once and lets everyone else walk "
              "it.",
              "One traversal, two frontiers, and the frontier is the "
              "parameter.",
              "The proof must switch between breadth and depth by one line."),
        _face("seer", "ROSE",
              "A compass rose does not know where you are. It knows which way "
              "is which.",
              "Read the frontier. It always tells you what the search thinks "
              "it is doing.",
              "Say which ruin is reached last, before running the proof."),
    ),
)

_sage(
    "ruins", "THE ONE WHO NEVER PAYS TWICE",
    scar="The burn, and the fingertips worn smooth from a lifetime of "
         "touching stone to see whether it is still warm.",
    blurb="Solved tiles glow and can be walked again for free. Somebody has "
          "been lighting tiles here for long enough that the ruins are "
          "brighter than they were, and they have never once relit one.",
    where="The tile that was lit first, which is the coldest one and the "
          "reason all the others are warm.",
    how="Never pay twice. Three DP encounters cleared on the first "
        "submission, and DP past fifty, and the first tile will have somebody "
        "sitting on it.",
    needs=({"kind": "first_try", "skill": "DP", "count": 3},
           {"kind": "skill_mastery", "skill": "DP", "value": 50},
           {"kind": "arts_known", "count": 1}),
    first_words="You already carry one art, so you know what one of these "
                "costs. Three first-try clears on tiles that eat people. Sit "
                "down.",
    edges_kind="COMPLEXITY_DUEL",
    demands={
        "name": "What is the state. Not the answer — the state.",
        "write": "One dimension if you can. Two if you must.",
        "edges": "Now the table's size, and whether you needed all of it.",
        "recall": "The recursion from the forest, which is this with no memo.",
        "proof": "Write the recurrence, the base row and the order of "
                 "filling, and defend the order.",
    },
    prefer={"proof": ("dp-lis", "dp-edit-distance", "dp-house-robber")},
    fail_lines=(
        "You described the answer. The state is what you need to know to "
        "decide, which is smaller and harder.",
        "The table is right and the base row is not, so everything is wrong "
        "in the same direction.",
        "You allocated the whole plane and used two rows of it.",
        "The forest is still charging you exponentially.",
        "The fill order reads a tile that has not been written, which is the "
        "only real bug in this entire region.",
    ),
    on_clear="Paid once. Take it. You will not relight a tile again as long as "
             "you live, which is worth more than the art.",
    faces=(
        _face("analyst", "TALLYWRIGHT",
              "Say the state out loud. If it takes more than a sentence it is "
              "the wrong state.",
              "The recurrence, stated, is the program. The rest is typing.",
              "State the recurrence before the table exists."),
        _face("berserker", "SPEND",
              "Write the recursion. Watch it die. Put a dict on it.",
              "Exponential first, memo second, table third. In that order, "
              "quickly.",
              "One submission with no memo at all."),
        _face("archivist", "ARREARS",
              "Arrears are what you owe because you did not pay attention "
              "earlier.",
              "A memo is an archive. You have been building one all game.",
              "The ambush is the recursion this replaces."),
        _face("warden", "THRESHOLD",
              "A threshold is the row you have to write before any of the "
              "others make sense.",
              "The base row is the test. Write it first and the rest is "
              "arithmetic.",
              "Call the zero-length and one-length cases before the proof "
              "runs."),
        _face("artificer", "SCAFFOLD",
              "Scaffolding comes down. The building stays.",
              "Top-down with a cache, then bottom-up, then two rows. Three "
              "builds, one idea.",
              "The proof must reduce the table to the rows it actually reads."),
        _face("seer", "PAVING",
              "You can see which tiles are lit. That is a debugger and it is "
              "free.",
              "Print the table. Read the table. The bug is visible in the "
              "table.",
              "Say which tile is wrong first, before running the proof."),
    ),
)

_sage(
    "dungeon", "THE ONE WHO READS THE CRACK",
    scar="The burn, which on this one is clearly the original, and which they "
         "describe, once, as a defect they did not catch.",
    blurb="Cracked armour hangs on every wall and each crack is a defect in "
          "some program. Somebody has been cataloguing them. Not repairing "
          "them — cataloguing them — because the repair is the easy half and "
          "they have said so out loud in front of the Armorer.",
    where="The cell with no plate in it, where the catalogue is, which is the "
          "only room down here that is not about a bug.",
    how="Name the break before the diagnosis renders. Six times, correctly, "
        "and five DEBUGGING encounters cleared with no help.",
    needs=({"kind": "root_cause_named", "count": 6},
           {"kind": "skill_unaided", "skill": "DEBUGGING", "count": 5},
           {"kind": "arts_known", "count": 2}),
    first_words="Six times you knew what kind of wrong it was before you were "
                "told. That is not debugging. That is having read enough "
                "programs.",
    edges_kind="DEBUG_BATTLE",
    demands={
        "name": "What category of wrong is this. Before you read the fix.",
        "write": "Repair it. One line if one line is honest.",
        "edges": "Here is one where the test is wrong and the program is "
                 "right.",
        "recall": "Something from six regions back, broken on purpose.",
        "proof": "Write the failing case, the repair and the assertion that "
                 "proves it, as three separate things.",
    },
    prefer={"proof": ("pt-bug-denominator", "db-binary-search",
                      "db-modulo-negative")},
    fail_lines=(
        "You named the symptom. The category is the thing that makes the next "
        "one fast.",
        "It works now and you cannot say why, which means it does not work "
        "yet.",
        "You repaired a correct program to satisfy an incorrect test, and you "
        "will do it again in industry, and it will cost more.",
        "Six regions back, and it is exactly as broken as it was.",
        "There is no assertion. A repair without a proof is an opinion.",
    ),
    on_clear="Take it. And put your failing case in the catalogue on the way "
             "out; that is the rent.",
    faces=(
        _face("analyst", "SYMPTOM",
              "You want the category before the trace. You are correct and it "
              "is unusual.",
              "Nine categories. Name one, out loud, before reading a line.",
              "Name the failure category before the proof's first run."),
        _face("berserker", "CLANG",
              "Change something. The program will tell you.",
              "Bisect by breaking. It is crude and it is faster than reading.",
              "One repair attempt before you have read the whole function."),
        _face("archivist", "ERRATA",
              "Errata are the list of things that were wrong in the printing "
              "you own.",
              "You have made this exact mistake before. I have the record.",
              "The ambush is a bug you personally wrote."),
        _face("warden", "PROOFMARK",
              "A proofmark is somebody signing to say they checked.",
              "Write the failing test first. Then the fix cannot lie to you.",
              "The proof must have a failing assertion before it has a fix."),
        _face("artificer", "RIVET",
              "A rivet is a repair that is stronger than the thing it "
              "repaired.",
              "Fix the class of bug, not the instance, or you will be back.",
              "The proof's fix must be one function, not three edits."),
        _face("seer", "HAIRLINE",
              "A hairline crack is visible before it is a crack. That is the "
              "whole discipline.",
              "Step your own program. Yours. Not the reference.",
              "Say which frame diverges, before the trace renders."),
    ),
)

_sage(
    "tower", "THE ONE ON THE EIGHTH FLOOR",
    scar="The burn, and an expression of somebody who has done this climb "
         "many more times than necessary and knows it.",
    blurb="Each floor holds twice the enemies of the one below and the top "
          "floor is unreachable by brute force. Somebody lives on the eighth, "
          "which is exactly as high as a person can get by being stubborn, "
          "and they stopped there on purpose to think about why.",
    where="The eighth floor, which is the last one that can be reached the "
          "wrong way, and is therefore the only one worth living on.",
    how="Replace three quadratic answers with linear ones and take BIG_O past "
        "fifty-five, carrying two arts already. The stairs will be shorter "
        "than you remember.",
    needs=({"kind": "perf_cleared", "count": 3},
           {"kind": "skill_mastery", "skill": "BIG_O", "value": 55},
           {"kind": "arts_known", "count": 2}),
    first_words="Three times you made something faster rather than making it "
                "work again. The eighth floor is where those people end up.",
    edges_kind="COMPLEXITY_DUEL",
    demands={
        "name": "Name the cost of the obvious answer, before writing the "
                "obvious answer.",
        "write": "Now beat it. By a whole class, not by a constant.",
        "edges": "Say what you traded. There is always a trade and it is "
                 "usually memory.",
        "recall": "Something from the Highlands. It was O(n) then too.",
        "proof": "Write both versions, the slow one and the fast one, and the "
                 "measurement that separates them.",
    },
    prefer={"proof": ("cx-space-tradeoff", "bs-min-capacity", "bs-rotated")},
    fail_lines=(
        "You did not cost it, so you have no idea whether what you wrote next "
        "was an improvement.",
        "Same class, smaller constant. The tower doubles; constants do not "
        "help.",
        "You traded nothing, which means one of your two numbers is wrong.",
        "The Highlands are the reason this floor exists and you have "
        "forgotten them.",
        "There is no measurement. Two programs and a feeling is not a "
        "comparison.",
    ),
    on_clear="The ninth floor is up there. It was always up there. You could "
             "not have got to it the way you got to the eighth.",
    faces=(
        _face("analyst", "ASYMPTOTE",
              "You are already counting the work per element. Finish the "
              "sentence.",
              "Work per element, times elements. That is the whole art.",
              "State both complexities before writing either version."),
        _face("berserker", "HAUL",
              "Climb it wrong first. The wall is informative.",
              "Write the quadratic one in ninety seconds so you can see what "
              "the fast one has to beat.",
              "The slow version submitted before the fast one is written."),
        _face("archivist", "MARGIN",
              "The margin is where the person who read it before you left "
              "their working.",
              "Every fast answer in this game is one of six tricks and you "
              "have met all six.",
              "The ambush is a hash map, which is five of the six."),
        _face("warden", "BALUSTER",
              "A baluster stops the fall you were not planning on.",
              "Fast and wrong is a category of wrong, and it is the "
              "expensive one.",
              "The fast version must pass every case the slow one does."),
        _face("artificer", "COUNTERWEIGHT",
              "A counterweight makes the climb cheap by making something else "
              "heavy.",
              "Space for time. Say which you spent.",
              "The proof must state the extra memory the fast version holds."),
        _face("seer", "PARALLAX",
              "Parallax is how you measure something too far away to reach.",
              "Read the loop nesting. It is the complexity, written down.",
              "Say which loop is the expensive one, before measuring."),
    ),
)

_sage(
    "coliseum", "THE ONE WHO MARKS THE SAND",
    scar="The burn, healed properly for once, on somebody who has had access "
          "to a physician and did not use it for years.",
    blurb="A sand floor, a clock, and no hints. Somebody rakes the sand "
          "between bouts and marks where each fighter's feet were when the "
          "clock ran out. The marks go back a long way and they are, if you "
          "look, getting closer to the middle.",
    where="Under the sand, at the mark nearest the middle, which is the oldest "
          "one and is somebody's.",
    how="Beat your own best time on the same problem three times, and take "
        "SPEED past forty-five, carrying three arts. The rake stops when you "
        "get close.",
    needs=({"kind": "beat_own_time", "count": 3},
           {"kind": "skill_mastery", "skill": "SPEED", "value": 45},
           {"kind": "arts_known", "count": 3}),
    first_words="Three times faster than yourself. Not faster than anybody "
                "else — that is a different and much less interesting "
                "measurement.",
    edges_kind="SPEED_DUEL",
    demands={
        "name": "Name it in five seconds. The clock is already running.",
        "write": "Now write it, correctly, and do not look up.",
        "edges": "Again, under time, with the input that breaks it.",
        "recall": "Anything. From anywhere. You have no idea what is coming.",
        "proof": "Write it long, under the clock, and then do not be allowed "
                 "to shorten it until it is right.",
    },
    prefer={"proof": ("pt-feature-env-overrides", "pt-feature-date-range",
                      "pt-class-apply")},
    fail_lines=(
        "Too slow to name it, which means everything after would have been "
        "guessing at speed.",
        "The clock beat you. The clock is not the problem; the clock is the "
        "measurement.",
        "It broke under time on the case you would have caught untimed.",
        "You did not know what was coming, which is the entire test.",
        "Long and wrong, under a clock. Come back; the sand keeps.",
    ),
    on_clear="There is your mark. Nearest the middle. I will rake round it.",
    faces=(
        _face("analyst", "TEMPO",
              "You want a minute to think. You have nine seconds. Use them "
              "the same way.",
              "The declaration gets faster. It does not get skipped.",
              "Name the pattern inside ten seconds, or forfeit the "
              "declaration."),
        _face("berserker", "SAND",
              "Finally. Somewhere that agrees with you.",
              "Type. You have never needed anything else and here it is "
              "actually true.",
              "Submit inside half the clock, ready or not."),
        _face("archivist", "CHRONICLE",
              "A chronicle is what makes a fast answer possible: you are not "
              "solving it, you are recognising it.",
              "Speed is retrieval. There is nothing else in it.",
              "The ambush is unlabelled and could be any region."),
        _face("warden", "BARRIER",
              "The clock is not an excuse to stop testing. It is the reason "
              "the test has to be a reflex.",
              "Two edge calls, in four seconds, before the first line.",
              "Name two input classes before the clock reaches a quarter."),
        _face("artificer", "WHETSTONE",
              "A whetstone does not make the blade. It makes the blade you "
              "already have work.",
              "Under time, your bench is the only advantage that survives.",
              "The proof must reuse something you built in another region."),
        _face("seer", "WATCHER",
              "I have been watching fighters lose to their own first draft "
              "for eleven years.",
              "Read it once, properly, and you will not have to read it "
              "three times badly.",
              "Say the failure category before the clock's last quarter."),
    ),
)


SAGE_BY_ID: dict = {s.id: s for s in SAGES}
SAGE_BY_REGION: dict = {s.region: s for s in SAGES}
SAGE_IDS: tuple = tuple(s.id for s in SAGES)


# ===========================================================================
# Lookup
# ===========================================================================

def get(sage_id: str) -> Sage | None:
    return SAGE_BY_ID.get(sage_id)


def for_region(region_id: str) -> Sage | None:
    return SAGE_BY_REGION.get(region_id)


def face(sage_id: str, class_id: str) -> Face | None:
    sage = SAGE_BY_ID.get(sage_id)
    return sage.face(class_id) if sage else None


def art(sage_id: str, class_id: str) -> Art | None:
    one = face(sage_id, class_id)
    return one.art if one else None


def art_by_id(art_id: str) -> Art | None:
    return ART_BY_ID.get(art_id)


def arts_for(class_id: str) -> tuple:
    return ARTS_BY_CLASS.get(class_id, ())


def moveset_requests(class_id: str = "") -> list:
    """THE HANDOVER. Every art as the kwargs `incantation._inc` already takes.

        for request in sages.moveset_requests():
            catalogue.append(incantation._inc(**request))

    `power` in each request is derived from `complexity()` at call time, so an
    art that is edited to ask for less immediately hits for less, with nobody
    having to remember to change a second number.
    """
    chosen = ARTS_BY_CLASS.get(class_id, ()) if class_id else tuple(ARTS)
    return [one.request() for one in chosen]


def available_in(mode: str, region_id: str, *, sealed: bool = False) -> bool:
    """May a sage be found, faced or spoken to here.

    `sealed` is `finalexam.sealed(encounter, sages.CAPABILITY)`, passed in by
    the caller rather than decided here, so the exam's verdict is formed in one
    place. A sage is a mentor: the seal that takes the mentor takes the sage.

    THIS DOES NOT GATE THE ARTS. An art already learned is castable anywhere,
    including inside the exam, because it is the player's own fluency and not a
    crutch. What the exam removes is everything that would tell you which art
    to reach for, and `PATTERN` and `WEAKNESS_MAP` already remove that.
    """
    if sealed:
        return False
    if (mode or "").strip().upper() in ("INTERVIEW", "EXAM", "MEASURED",
                                        "PRACTICAL"):
        return False
    if region_id in SILENCED_REGIONS:
        return False
    return region_id in SAGE_BY_REGION


def ladder_view() -> list:
    """Sixteen rows: where each sage stands, how hard, and what it costs.

    The answer to "say how the ladder runs", as data rather than as a claim.
    """
    out = []
    for sage in SAGES:
        arts = ARTS_BY_REGION[sage.region]
        out.append({
            "sage": sage.id, "region": sage.region, "tier": sage.tier,
            "region_name": world.REGION_BY_ID[sage.region]["name"],
            "numeral": world.REGION_BY_ID[sage.region]["numeral"],
            "skill": REGION_META[sage.id]["skill"],
            "chapter": REGION_META[sage.id]["chapter"],
            "element": elements.affinity_for(sage.region),
            "stages": len(sage.stages),
            "difficulties": [s.difficulty for s in sage.stages],
            "art_complexity": [round(a.score, 2) for a in arts],
            "art_power": [a.power for a in arts],
            "cast_cost": arts[0].cost, "par_seconds": arts[0].par_seconds,
        })
    return out


# ===========================================================================
# Finding one
# ===========================================================================

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
        return _row("unaided clears in %s" % family.replace("_", " "),
                    (ev.get("families") or {}).get(family, 0),
                    clause.get("count", 1))
    if kind == "skill_unaided":
        skill = clause.get("skill", "")
        data = (ev.get("skills") or {}).get(skill) or {}
        return _row("%s unaided clears" % skill,
                    data.get("unaided_clears", 0), clause.get("count", 1))
    if kind == "skill_mastery":
        skill = clause.get("skill", "")
        data = (ev.get("skills") or {}).get(skill) or {}
        return _row("%s mastery" % skill, data.get("mastery", 0),
                    clause.get("value", 0))
    if kind == "boss_unaided":
        boss = clause.get("boss", "")
        return _row("%s beaten with nothing cast" % boss.replace("_", " "),
                    1 if boss in (ev.get("bosses_unaided") or []) else 0, 1)
    if kind == "region_cleared":
        region = clause.get("region", "")
        return _row("%s cleared" % region.replace("_", " "),
                    1 if region in (ev.get("regions_cleared") or []) else 0, 1)
    if kind == "dungeon_depth":
        dungeon = clause.get("dungeon", "")
        return _row("%s depth reached" % dungeon.replace("_", " "),
                    (ev.get("dungeons") or {}).get(dungeon, 0),
                    clause.get("depth", 1))
    if kind == "retest_survived":
        skill = clause.get("skill", "")
        retests = ev.get("retests") or {}
        # The evidence dict publishes the TOTAL under the empty key alongside
        # the per-skill counts (see the shape note above), so `sum(values)`
        # added the total to its own parts and every unnamed clause read
        # exactly twice the truth — a three-ambush gate opening after two.
        # Read the published total; fall back to summing the NAMED keys only,
        # for a caller that does not publish one.
        have = (retests.get(skill, 0) if skill else
                retests.get("", sum(v for k, v in retests.items() if k)))
        return _row("%s memory ambushes survived" % (skill or "any"),
                    have, clause.get("count", 1))
    if kind == "no_hint_streak":
        return _row("clears in a row with no help", ev.get("no_hint_streak", 0),
                    clause.get("count", 1))
    if kind == "perf_cleared":
        return _row("performance trials cleared", ev.get("perf_cleared", 0),
                    clause.get("count", 1))
    if kind == "probes_correct":
        return _row("correct probes", ev.get("probes_correct", 0),
                    clause.get("count", 1))
    if kind == "clean_casts":
        return _row("casts in a row that parsed and named real things",
                    ev.get("clean_cast_streak", 0), clause.get("count", 1))
    if kind == "recalled_casts":
        return _row("casts made from memory, with no ghost",
                    ev.get("recalled_casts", 0), clause.get("count", 1))
    if kind == "region_clears":
        region = clause.get("region", "")
        return _row("encounters cleared in %s" % region.replace("_", " "),
                    (ev.get("region_clears") or {}).get(region, 0),
                    clause.get("count", 1))
    if kind == "regions_touched":
        touched = ev.get("regions_touched", 0)
        have = len(touched) if isinstance(touched, (list, tuple, set)) else touched
        return _row("regions with at least one clear", have,
                    clause.get("count", 1))
    if kind == "lifo_clears":
        return _row("encounters cleared in the reverse of the order offered",
                    ev.get("lifo_clears", 0), clause.get("count", 1))
    if kind == "first_try":
        skill = clause.get("skill", "")
        data = ev.get("first_try") or {}
        have = data.get(skill, 0) if skill else sum(data.values())
        return _row("%s clears on the first submission" % (skill or "any"),
                    have, clause.get("count", 1))
    if kind == "lineage_pair":
        return _row("problems cleared in two different skins",
                    ev.get("lineage_pairs", 0), clause.get("count", 1))
    if kind == "beat_own_time":
        return _row("personal bests broken on a rematch",
                    ev.get("beat_own_time", 0), clause.get("count", 1))
    if kind == "root_cause_named":
        return _row("failures named before the diagnosis rendered",
                    ev.get("root_cause_correct", 0), clause.get("count", 1))
    if kind == "arts_known":
        arts = ev.get("arts", 0)
        have = len(arts) if isinstance(arts, (list, tuple, set)) else arts
        return _row("secret arts already learned", have, clause.get("count", 1))
    return _row(kind or "unknown condition", 0, 1)


def discovery_progress(sage_id: str, evidence: dict | None = None) -> dict:
    """How close this player is to finding this sage.

    Pure. It reads evidence and describes it; granting is the caller's, which
    keeps "mastery moves only on graded evidence" in one place instead of two.
    """
    sage = SAGE_BY_ID[sage_id]
    found = sage.discovery
    checks = [_discovery_row(clause, evidence or {}) for clause in found.needs]
    return {
        "sage": sage.id, "region": sage.region, "tier": sage.tier,
        "unnamed": sage.unnamed,
        "region_name": world.REGION_BY_ID[sage.region]["name"],
        "where": found.where, "how": found.how,
        "first_words": found.first_words,
        "checks": checks,
        "met": bool(checks) and all(row["met"] for row in checks),
    }


def newly_found(evidence: dict | None = None, already=None) -> list:
    """Every sage whose conditions are now satisfied and who has not been met."""
    have = set(already or [])
    out = []
    for sage in SAGES:
        if sage.id in have:
            continue
        progress = discovery_progress(sage.id, evidence)
        if progress["met"]:
            out.append(progress)
    return out


def undiscovered_hints(evidence: dict | None = None, already=None,
                       limit: int = 3) -> list:
    """The nearest unmet sages, for the codex page that says there is more.

    Sorted by how close they are, because a hidden thing with no visible
    progress is indistinguishable from a bug.
    """
    have = set(already or [])
    scored = []
    for sage in SAGES:
        if sage.id in have:
            continue
        progress = discovery_progress(sage.id, evidence)
        rows = progress["checks"] or []
        done = sum(1 for row in rows if row["met"])
        scored.append((done / len(rows) if rows else 0.0, -sage.tier, progress))
    scored.sort(key=lambda triple: (triple[0], triple[1]), reverse=True)
    return [progress for _, _, progress in scored[:limit]]


# ===========================================================================
# The gauntlet
# ===========================================================================

def gauntlet(sage_id: str, class_id: str, *, attempt: int = 0) -> dict:
    """The trial as SPECIFICATIONS, with no corpus involved.

    Safe to call from anywhere, including a test that does not want to build a
    thousand problems. `resolve_gauntlet` is the same thing with real problems
    poured into it.
    """
    sage = SAGE_BY_ID[sage_id]
    one = sage.face(class_id)
    if one is None:
        raise KeyError("%s has no face for class %r" % (sage_id, class_id))
    stages = []
    for index, stage in enumerate(sage.stages):
        stages.append({
            "index": index, "key": stage.key, "label": stage.label,
            "kind": stage.kind, "difficulty": stage.difficulty,
            "pattern": stage.pattern, "realm": stage.realm,
            "demands": stage.demands,
            "trial": one.trial if stage.key == "proof" else "",
            "prefer": list(stage.prefer),
            "on_fail": sage.fail_lines[index] if index < len(sage.fail_lines)
                       else sage.fail_lines[-1],
        })
    return {
        "sage": sage.id, "region": sage.region, "tier": sage.tier,
        "class": class_id, "name": one.name, "title": one.title,
        "creed": one.creed, "attempt": int(attempt),
        "stages": stages, "stage_count": len(stages),
        "art": one.art.to_dict(),
        "on_clear": sage.on_clear,
        "toll": RETURN_TOLL,
    }


def _seed(*parts) -> int:
    """A stable seed. `hash()` on strings is salted per process and a gauntlet
    that reshuffles when the server restarts is not a gauntlet."""
    import zlib
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


def _matches(problem, *, realm: str, pattern: str, difficulty: str) -> bool:
    if getattr(problem, "sealed", False):
        return False
    if difficulty and getattr(problem, "difficulty", "") != difficulty:
        return False
    if realm and getattr(problem, "realm", "") != realm:
        return False
    if pattern:
        if getattr(problem, "pattern", "") != pattern \
                and pattern not in (getattr(problem, "secondary_patterns", ())
                                    or ()):
            return False
    return True


def _relaxations(stage: Stage) -> list:
    """The order in which a stage gives ground when the corpus is thin.

    Difficulty first, one rung at a time, because a slightly easier problem of
    the right shape teaches the right thing and a harder problem of the wrong
    shape does not. Pattern next. Realm last, and only for the ambush rung,
    which was never about this region anyway.
    """
    tiers = list(curriculum.TIERS)
    try:
        start = tiers.index(stage.difficulty)
    except ValueError:
        start = tiers.index("MEDIUM")
    out = []
    for step in range(start, -1, -1):
        out.append((stage.realm, stage.pattern, tiers[step], "difficulty"))
    for step in range(start, -1, -1):
        out.append((stage.realm, "", tiers[step], "pattern"))
    for step in range(start, -1, -1):
        out.append(("", "", tiers[step], "realm"))
    return out


def resolve_gauntlet(sage_id: str, class_id: str, problems=None, *,
                     attempt: int = 0, exclude=()) -> dict:
    """The same trial with real problems in it.

    `problems` is any iterable of corpus problems — objects with `id`, `realm`,
    `pattern`, `difficulty`, `sealed`. Passing them in keeps this module free
    of a hard corpus dependency and keeps the tests fast; omitting them builds
    the corpus once, lazily.

    A SECOND ATTEMPT DRAWS DIFFERENT PROBLEMS. `attempt` feeds the seed, so
    failing a sage and coming back is not a chance to replay a sequence you
    have now memorised. The specifications are identical; the problems are not.
    """
    if problems is None:                       # pragma: no cover - IO-ish
        from . import corpus
        problems = corpus.ensure()
    pool = [p for p in problems if not getattr(p, "sealed", False)]
    banned = set(exclude or ())
    plan = gauntlet(sage_id, class_id, attempt=attempt)
    used = set()

    for row in plan["stages"]:
        stage = SAGE_BY_ID[sage_id].stages[row["index"]]
        chosen, how = None, ""
        # THE AUTHORED SHORTLIST IS A FIRST-ATTEMPT THING.
        #
        # `prefer` names real problems chosen by hand, and consulting it is
        # deterministic: it does not read `attempt`. A gauntlet whose every rung
        # was covered by its shortlist therefore drew the SAME five problems on
        # every retry, which is the one thing the docstring above promises it
        # does not do — four of the ninety-six were fully memorisable. A retry
        # skips the shortlist and takes the seeded draw instead, so coming back
        # is always a fresh reading of the same specification.
        shortlist = stage.prefer if not attempt else ()
        for pid in shortlist:
            if pid in banned or pid in used:
                continue
            hit = next((p for p in pool if p.id == pid), None)
            if hit is not None:
                chosen, how = hit, "authored"
                break
        if chosen is None:
            for realm, pattern, difficulty, gave in _relaxations(stage):
                candidates = [p for p in pool
                              if p.id not in banned and p.id not in used
                              and _matches(p, realm=realm, pattern=pattern,
                                           difficulty=difficulty)]
                if candidates:
                    candidates.sort(key=lambda p: p.id)
                    rng = random.Random(_seed(sage_id, class_id, attempt,
                                              stage.key))
                    chosen = candidates[rng.randrange(len(candidates))]
                    how = ("exact" if (realm, pattern, difficulty)
                           == (stage.realm, stage.pattern, stage.difficulty)
                           else "relaxed:" + gave)
                    break
        if chosen is None:
            row.update({"problem": "", "resolved": "none", "title": "",
                        "actual_difficulty": ""})
            continue
        used.add(chosen.id)
        row.update({"problem": chosen.id, "resolved": how,
                    "title": getattr(chosen, "title", ""),
                    "actual_difficulty": getattr(chosen, "difficulty", "")})
    plan["unresolved"] = [r["key"] for r in plan["stages"] if not r["problem"]]
    plan["resolved"] = not plan["unresolved"]
    return plan


# ===========================================================================
# State
# ===========================================================================
# Flat, JSON-safe, small enough to drop straight into the save blob.
#
# `found` and `arts` are append-only. Nothing in this module removes an art, a
# sage, or a cleared gauntlet, because the rule is that failing costs time and
# pride and never progress, and a module that cannot take anything away cannot
# be argued into taking something away later.

def new_state() -> dict:
    return {
        "found": [],          # sage ids met
        "cleared": {},        # sage id -> [class ids it has been cleared as]
        "arts": [],           # art ids learned
        "attempts": {},       # sage id -> how many times you have started
        "failed_at": {},      # sage id -> the stage key you died on last
        "toll_at": {},        # sage id -> region clears required before a retry
        "progress": {},       # sage id -> stage keys cleared in the RUN so far
        "met_at": {},         # sage id -> timestamp
        "cleared_at": {},     # art id -> timestamp
    }


def meet(state: dict, sage_id: str, *, at: float = 0.0) -> bool:
    """Record that the player has found this sage. Idempotent."""
    if sage_id not in SAGE_BY_ID:
        return False
    found = state.setdefault("found", [])
    if sage_id in found:
        return False
    found.append(sage_id)
    state.setdefault("met_at", {})[sage_id] = float(at)
    return True


def has_met(state: dict, sage_id: str) -> bool:
    return sage_id in (state or {}).get("found", [])


def cleared_as(state: dict, sage_id: str) -> list:
    return list((state or {}).get("cleared", {}).get(sage_id, []))


def arts_known(state: dict) -> list:
    return [ART_BY_ID[a] for a in (state or {}).get("arts", []) if a in ART_BY_ID]


def may_attempt(state: dict, sage_id: str, region_clears: int = 0) -> tuple:
    """(ok, why). The only thing failure costs, expressed as a function.

    The toll is encounters cleared in that region — not a wall-clock timer,
    because a timer punishes the player who put the game down and this is
    supposed to punish the player who wants to brute-force a trial.
    """
    if sage_id not in SAGE_BY_ID:
        return False, "There is nobody there."
    if not has_met(state, sage_id):
        return False, "You have not found them yet."
    owed = int((state.get("toll_at") or {}).get(sage_id, 0))
    have = int(region_clears or 0)
    if have < owed:
        return False, ("Not yet. %d more encounter%s in this region first."
                       % (owed - have, "" if owed - have == 1 else "s"))
    return True, ""


def begin(state: dict, sage_id: str, class_id: str,
          region_clears: int = 0) -> dict:
    """Start or restart a gauntlet. Returns the plan, or a refusal."""
    ok, why = may_attempt(state, sage_id, region_clears)
    if not ok:
        return {"started": False, "reason": why,
                "greeting": greeting(sage_id, class_id, state)}
    attempts = state.setdefault("attempts", {})
    attempts[sage_id] = int(attempts.get(sage_id, 0)) + 1
    state.setdefault("progress", {})[sage_id] = []
    plan = gauntlet(sage_id, class_id, attempt=attempts[sage_id] - 1)
    plan["started"] = True
    plan["greeting"] = greeting(sage_id, class_id, state)
    return plan


def record_stage(state: dict, sage_id: str, stage_key: str,
                 passed: bool) -> dict:
    """One rung, resolved. Returns what the caller should do next."""
    sage = SAGE_BY_ID[sage_id]
    keys = [s.key for s in sage.stages]
    if stage_key not in keys:
        return {"ok": False, "reason": "No such rung."}
    done = state.setdefault("progress", {}).setdefault(sage_id, [])
    if not passed:
        return {"ok": True, "passed": False, "cleared": False,
                "next": "", "fail": True}
    if stage_key not in done:
        done.append(stage_key)
    remaining = [k for k in keys if k not in done]
    return {"ok": True, "passed": True, "cleared": not remaining,
            "next": remaining[0] if remaining else "", "fail": False,
            "done": list(done), "remaining": remaining}


def fail(state: dict, sage_id: str, stage_key: str,
         region_clears: int = 0) -> dict:
    """Sent away. What this costs, exactly, and nothing more.

    No mastery, no gold, no gear, no progress, no closed door. The run's own
    progress is cleared — you face the whole trial again — and a toll is owed
    before the next attempt. The sage remembers, which is the other half.
    """
    sage = SAGE_BY_ID[sage_id]
    keys = [s.key for s in sage.stages]
    index = keys.index(stage_key) if stage_key in keys else 0
    state.setdefault("progress", {})[sage_id] = []
    state.setdefault("failed_at", {})[sage_id] = stage_key
    state.setdefault("toll_at", {})[sage_id] = int(region_clears or 0) + RETURN_TOLL
    frame_keys = [row[0] for row in STAGE_FRAME]
    frame_index = frame_keys.index(stage_key) if stage_key in frame_keys else index
    return {
        "sage": sage.id, "stage": stage_key,
        "line": sage.fail_lines[min(frame_index, len(sage.fail_lines) - 1)],
        "toll": RETURN_TOLL,
        "toll_at": state["toll_at"][sage_id],
        "attempts": int((state.get("attempts") or {}).get(sage_id, 0)),
        "lost": [],                    # deliberately, permanently, empty
        "kept": ["mastery", "gold", "gear", "arts", "region progress",
                 "everything else"],
        "reattemptable": True,
    }


def complete(state: dict, sage_id: str, class_id: str, *,
             at: float = 0.0) -> dict:
    """The trial is passed. Hands over exactly one art. Idempotent."""
    one = face(sage_id, class_id)
    if one is None:
        return {"granted": False, "reason": "No such sage, or no such class."}
    cleared = state.setdefault("cleared", {}).setdefault(sage_id, [])
    arts = state.setdefault("arts", [])
    already = one.art.id in arts
    if class_id not in cleared:
        cleared.append(class_id)
    if not already:
        arts.append(one.art.id)
        state.setdefault("cleared_at", {})[one.art.id] = float(at)
    state.setdefault("progress", {})[sage_id] = []
    state.setdefault("toll_at", {}).pop(sage_id, None)
    state.setdefault("failed_at", {}).pop(sage_id, None)
    return {"granted": not already, "art": one.art.to_dict(),
            "art_id": one.art.id, "sage": sage_id, "class": class_id,
            "line": SAGE_BY_ID[sage_id].on_clear,
            "learn": one.art.request()}


def greeting(sage_id: str, class_id: str, state: dict | None = None) -> dict:
    """What is said, and it depends on what has happened between you.

    Four things can be true, and they read differently:
      never met        the silhouette, and the deed that finds them
      first meeting    the face's own greeting
      came back failed the class's return line, and THE RUNG YOU DIED ON
      already cleared  the sage on the other side of it
    """
    sage = SAGE_BY_ID.get(sage_id)
    one = face(sage_id, class_id)
    if sage is None or one is None:
        return {"state": "absent", "line": ""}
    state = state or {}
    if not has_met(state, sage_id):
        return {"state": "unmet", "line": "", "where": sage.discovery.where,
                "how": sage.discovery.how}
    if class_id in cleared_as(state, sage_id):
        return {"state": "cleared", "name": one.name, "title": one.title,
                "line": sage.on_clear, "art": one.art.id}
    failed = (state.get("failed_at") or {}).get(sage_id, "")
    attempts = int((state.get("attempts") or {}).get(sage_id, 0))
    if failed and attempts:
        keys = [row[0] for row in STAGE_FRAME]
        index = keys.index(failed) if failed in keys else 0
        return {"state": "returning", "name": one.name, "title": one.title,
                "line": one.returning,
                "remembers": sage.fail_lines[min(index,
                                                 len(sage.fail_lines) - 1)],
                "failed_at": failed, "attempts": attempts}
    return {"state": "first", "name": one.name, "title": one.title,
            "line": one.greeting, "creed": one.creed,
            "first_words": sage.discovery.first_words}


def evidence_patch(state: dict) -> dict:
    """The slice of the evidence dict this module OWNS.

    `arts_known` clauses read `evidence["arts"]`, and the later sages gate on
    it, so the caller folds this into whatever it assembles:

        evidence.update(sages.evidence_patch(save.sages))
    """
    return {"arts": list((state or {}).get("arts", []))}


# ===========================================================================
# Proofs
# ===========================================================================
# Two of these matter more than the rest.
#
# `self_test_all()` CASTS EVERY ART. Each one is assembled the way
# `incantation.build_cast_source` assembles it — demo bindings, the snapshot,
# the line with its own worked example poured in, the body, then the art's own
# assertion — and the result is executed. An art that cannot cast itself has no
# business asking a player to cast it. The text executed is authored in this
# file and has never been near player input; nothing here is a path for running
# anything a player typed, which still goes through `gauntlet.sandbox` and
# always will.
#
# `self_check()["separation"]` PROVES THE DESIGN RULE. It scores every ordinary
# incantation and every secret art on the same function and reports the gap.
# If an art ever scores below an ordinary move, the claim at the top of this
# file has become false and this is where it says so.

_ANSWER_TELLS = (
    "the answer is", "the solution is", "here is the solution",
    "here's the solution", "copy this", "paste this", "the correct code is",
    "just write ", "simply write", "the fix is to write",
)


def _prose(sage: Sage):
    """Every authored SENTENCE in a sage. Not templates, not examples — the
    grep below is looking for prose that gives a problem away, and a template
    is Python by design."""
    yield "unnamed", sage.unnamed
    yield "scar", sage.scar
    yield "blurb", sage.blurb
    yield "where", sage.discovery.where
    yield "how", sage.discovery.how
    yield "first_words", sage.discovery.first_words
    yield "on_clear", sage.on_clear
    for line in sage.fail_lines:
        yield "fail", line
    for stage in sage.stages:
        yield "demands", stage.demands
    for one in sage.faces:
        yield "greeting", one.greeting
        yield "creed", one.creed
        yield "trial", one.trial
        yield "note", one.art.note
        yield "miss", one.art.miss
        yield "idiom", one.art.idiom


def self_test(one: Art, *, explain: bool = False):
    """Cast one art against its own worked example. True, or a reason."""
    answers = dict(one.example)
    lines = ["import copy"] + list(one.imports) + ["", "def __cast__():"]
    for name in sorted(one.demo):
        lines.append("    %s = %s" % (name, one.demo[name]))
    lines.append("    __b__ = {}")
    for key in sorted(one.snapshot):
        lines.append("    __b__[%r] = copy.deepcopy(%s)"
                     % (key, _fill(one.snapshot[key], answers)))
    line = _fill(one.template, answers)
    body = [_fill(b, answers) for b in one.body]
    if one.template.rstrip().endswith(":"):
        lines.append("    " + line)
        for statement in (body or ["pass"]):
            lines.append("        " + statement)
    else:
        lines.append("    " + line)
        for statement in body:
            lines.append("    " + statement)
    lines.append("    return bool(%s)" % _fill(one.assertion, answers))
    source = "\n".join(lines) + "\n"
    namespace: dict = {}
    try:
        exec(compile(source, "<%s>" % one.id, "exec"), namespace)
        ok = bool(namespace["__cast__"]())
    except Exception as exc:                   # noqa: BLE001 - reported, not raised
        return (False, "%s: %s" % (type(exc).__name__, exc), source) \
            if explain else False
    if explain:
        return (ok, "" if ok else "the assertion was false", source)
    return ok


def self_test_all() -> dict:
    failures = []
    for one in ARTS:
        ok, why, _ = self_test(one, explain=True)
        if not ok:
            failures.append({"art": one.id, "why": why})
    return {"arts": len(ARTS), "passed": len(ARTS) - len(failures),
            "failed": failures}


def _fit(points: list) -> dict:
    """Least squares of (complexity, authored power) over the live catalogue."""
    if len(points) < 2:
        return {"slope": POWER_SLOPE, "intercept": POWER_INTERCEPT, "n": 0}
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    if not var:
        return {"slope": POWER_SLOPE, "intercept": POWER_INTERCEPT,
                "n": len(points)}
    slope = sum((x - mx) * (y - my) for x, y in points) / var
    return {"slope": round(slope, 3), "intercept": round(my - slope * mx, 3),
            "n": len(points)}


def overlap_report() -> dict:
    """What `gauntlet/arts.py` and this file both claim, as facts.

    Written because two passes were briefed to author the secret arts and both
    did. Nothing here decides anything; it lays out the differences so that
    whoever wires the game up settles it once, on evidence, instead of
    discovering it when a class has thirty-two signature moves.
    """
    try:
        from . import arts as other
    except Exception:                          # pragma: no cover
        return {"present": False}
    theirs = {a.id for a in other.ARTS}
    their_regions = sorted({a.region for a in other.ARTS})
    ours = sorted(SAGE_BY_REGION)
    return {
        "present": True,
        "their_arts": len(theirs), "our_arts": len(ARTS),
        "id_collisions": sorted(theirs & set(ART_BY_ID)),
        "their_id_shape": "art_<class>_<region>",
        "our_id_shape": "art_<region>_<class>",
        "regions_only_theirs": [r for r in their_regions if r not in ours],
        "regions_only_ours": [r for r in ours if r not in their_regions],
        "their_power_range": [min(a.power for a in other.ARTS),
                              max(a.power for a in other.ARTS)],
        "our_power_range": [min(a.power for a in ARTS),
                            max(a.power for a in ARTS)],
        "they_also_author_places": hasattr(other, "SANCTUM_BY_REGION"),
        "decision": _OVERLAP_DECISION,
        "measured": {
            "ours_below_the_engine_bar": "69 of 96, at tier 1, against the "
                                         "hardest ordinary line castable in "
                                         "each art's own area",
            "theirs_below_the_engine_bar": "0 of 96",
            "ours_pinned_at_the_ruler_ceiling_at_recalled": "39 of 96",
            "theirs_pinned_at_the_ruler_ceiling_at_recalled": "94 of 96",
            "why_both_numbers_matter": "Ours were ranked on this file's private "
                                       "`complexity()`, which the damage never "
                                       "consults. Theirs were ranked on "
                                       "`incantation.measure_complexity`, which "
                                       "it does — and then ran off the top of "
                                       "it. See arts.saturation_report().",
        },
    }


# The settlement, written down once so that neither file can drift away from it
# quietly. It was decided on measurement, not on taste: see `overlap_report()`
# ["measured"] and `self_check()["real_ruler_separation"]`.
_OVERLAP_DECISION = (
    "SETTLED: gauntlet/arts.py owns THE LINE, this file owns WHO, WHERE and "
    "WHAT THE TRIAL IS. The deciding fact is that these ninety-six arts are "
    "ranked by this file's own `complexity()`, which nothing in the damage path "
    "reads, and on `incantation.measure_complexity` — which is what actually "
    "pays — sixty-nine of them demand LESS Python than `sift`, an ordinary "
    "chapter-two line the player already has. arts.py's ninety-six clear that "
    "bar by 1.11x to 2.28x because they were authored against it. "
    "THE EDIT THAT FINISHES THIS: drop ARTS, ART_BY_ID, _art and "
    "moveset_requests from this file and point Face.art at "
    "arts.taught_here(region_id, class_id), which now covers all sixteen sage "
    "regions with nothing unmatched in either direction. Everything else here "
    "is untouched by the choice. The arts below are kept, unwired, until that "
    "edit is made, because deleting authored work on a ruler that is itself "
    "being repaired (arts.saturation_report()) is the one order of operations "
    "that cannot be undone."
)


def _band(tier: int) -> int:
    return 0 if tier <= 3 else (1 if tier <= 11 else 2)


def self_check(problems=None) -> dict:
    """Counts and proofs. Safe from a test or from the command line.

    `problems` is optional: pass a corpus and every gauntlet is resolved
    against it and the real numbers come back. Omit it and the corpus-facing
    checks are skipped rather than guessed at.
    """
    report: dict = {}

    # -- counts ------------------------------------------------------------
    face_names = [one.name for sage in SAGES for one in sage.faces]
    report.update({
        "sages": len(SAGES),
        "faces": len(face_names),
        "distinct_face_names": len(set(face_names)),
        "arts": len(ARTS),
        "arts_per_class": {c: len(ARTS_BY_CLASS[c]) for c in CLASS_IDS},
        "regions_with_a_sage": len(SAGE_BY_REGION),
        "regions_total": len(world.REGIONS),
        "regions_without": [r["id"] for r in world.REGIONS
                            if r["id"] not in SAGE_BY_REGION],
        "one_sage_per_region": len(SAGE_BY_REGION) == len(SAGES),
        "six_faces_each": all(len(s.faces) == len(CLASS_IDS) for s in SAGES),
        "one_art_per_face": all(
            s.face(c) is not None and s.face(c).art.class_id == c
            for s in SAGES for c in CLASS_IDS),
        "authored_lines": sum(1 for s in SAGES for _ in _prose(s)),
    })

    # -- every art casts itself --------------------------------------------
    report["self_test"] = self_test_all()
    report["every_art_casts"] = not report["self_test"]["failed"]

    # -- the scale ---------------------------------------------------------
    art_scores = {one.id: one.score for one in ARTS}
    report["art_complexity"] = {"min": round(min(art_scores.values()), 2),
                                "max": round(max(art_scores.values()), 2),
                                "mean": round(sum(art_scores.values())
                                              / len(art_scores), 2)}
    report["art_power"] = {"min": min(a.power for a in ARTS),
                           "max": max(a.power for a in ARTS)}

    try:
        from . import incantation
        ordinary = [(complexity(i)["score"], i.power) for i in incantation.CATALOGUE]
        ord_scores = [s for s, _ in ordinary]
        report["ordinary_complexity"] = {
            "count": len(ord_scores), "min": round(min(ord_scores), 2),
            "max": round(max(ord_scores), 2),
            "mean": round(sum(ord_scores) / len(ord_scores), 2)}
        report["separation"] = {
            "hardest_ordinary": round(max(ord_scores), 2),
            "easiest_art": report["art_complexity"]["min"],
            "gap": round(report["art_complexity"]["min"] - max(ord_scores), 2),
            "every_art_above_every_ordinary_move":
                min(art_scores.values()) > max(ord_scores),
            "arts_below_the_bar": [aid for aid, sc in art_scores.items()
                                   if sc <= max(ord_scores)],
        }
        # Advisory, not a gate: the ordinary powers belong to `incantation`
        # and are being rewritten alongside this file. If this ever reads
        # False, the arts have stopped out-damaging the moves they are three
        # times the work of, and the fix is the SLOPE, never a bonus.
        ordinary_power = max(i.power for i in incantation.CATALOGUE)
        report["power_separation"] = {
            "hardest_ordinary_power": ordinary_power,
            "easiest_art_power": report["art_power"]["min"],
            "every_art_hits_harder": report["art_power"]["min"] > ordinary_power,
            "advisory": "incantation owns the ordinary numbers; if this goes "
                        "false, move POWER_SLOPE, never add a finder's bonus.",
        }
        report["scale_fit"] = _fit(ordinary)
        report["scale_fit"]["shipped_slope"] = POWER_SLOPE
        report["scale_fit"]["shipped_intercept"] = POWER_INTERCEPT

        # The same arts, measured by the combat system's OWN runtime scale
        # rather than by this file's authoring scale. This is the check that
        # actually matters, because `incantation._damage_for` multiplies by
        # `Complexity.weight` and nothing in this module can influence that.
        try:
            built = [incantation._inc(**one.request()) for one in ARTS]
            art_m = [incantation.measure_complexity(b, dict(b.example))
                     for b in built]
            ord_m = [incantation.measure_complexity(i, dict(i.example))
                     for i in incantation.CATALOGUE]
            art_s = sorted(m.score for m in art_m)
            ord_s = sorted(m.score for m in ord_m)
            median = ord_s[len(ord_s) // 2]
            report["runtime_scale"] = {
                "source": "incantation.measure_complexity, at tier 1",
                "ordinary_score_mean": round(sum(ord_s) / len(ord_s), 1),
                "ordinary_score_median": median,
                "art_score_mean": round(sum(art_s) / len(art_s), 1),
                "art_score_median": art_s[len(art_s) // 2],
                "arts_above_the_ordinary_median":
                    "%d/%d" % (sum(1 for x in art_s if x > median), len(art_s)),
                "ordinary_weight_mean":
                    round(sum(m.weight for m in ord_m) / len(ord_m), 2),
                "art_weight_mean":
                    round(sum(m.weight for m in art_m) / len(art_m), 2),
                "every_art_constructs": len(built) == len(ARTS),
            }
            # THE SAME QUESTION, ASKED OF THE RULER THAT PAYS THE DAMAGE.
            #
            # `separation` above is computed with THIS file's `complexity()`,
            # and on that scale the catalogue separates cleanly. That scale
            # decides nothing. `incantation.measure_complexity` decides the
            # damage, and against the hardest ordinary line castable in each
            # art's own area — which is `sift` from chapter two everywhere from
            # the Fields onward — most of these arts are the SHALLOWER line.
            #
            # This is reported rather than quietly passed because it is the one
            # fact that decides whether this catalogue can ship: an art that
            # measures below an ordinary move on the engine's ruler hits for
            # less than an ordinary move, whatever the private scale says.
            from . import arts as _arts
            bar, rows = {}, []
            for meta in REGION_META.values():
                best, raw = _arts.ordinary_line_ceiling(meta["chapter"])
                bar[meta["region"]] = (best.id if best else "", raw)
            for one, inc in zip(ARTS, built):
                measured = incantation.measure_complexity(
                    inc, dict(inc.example), tier=1)
                line, raw = bar.get(one.region, ("", 0.0))
                rows.append({"art": one.id, "region": one.region,
                             "raw": measured.raw, "ordinary": line,
                             "ordinary_raw": raw,
                             "ratio": round(measured.raw / raw, 2) if raw else 0.0,
                             "clears": bool(raw) and measured.raw >= raw * 1.10})
            under = [r for r in rows if not r["clears"]]
            report["real_ruler_separation"] = {
                "source": "incantation.measure_complexity vs the hardest "
                          "ordinary line castable in each art's own area, "
                          "tier 1, margin 1.10",
                "arts": len(rows),
                "below_the_bar": len(under),
                "worst": sorted(under, key=lambda r: r["ratio"])[:8],
                "holds": not under,
                "note": ("`separation` above is this file's own scale and it "
                         "separates. This is the engine's scale and it does "
                         "not: %d of %d arts demand less Python than an "
                         "ordinary line the player already has. On the ruler "
                         "that pays the damage these arts do not out-damage "
                         "the moves they are supposed to beat. See "
                         "`overlap_report()['decision']`."
                         % (len(under), len(rows))) if under else
                        "Holds on both scales.",
            }
        except Exception as exc:               # pragma: no cover
            report["runtime_scale"] = "unavailable: %s" % exc

        missing = sorted(REQUIRED_BUILTINS - set(incantation.BUILTIN_NAMES))
        report["handover"] = {
            "required_builtins": sorted(REQUIRED_BUILTINS),
            "builtins_the_arts_use": sorted(builtins_used()),
            "missing_from_incantation": missing,
            "satisfied": not missing,
            "edit": "add %s to incantation.BUILTIN_NAMES" % (missing or "nothing"),
            "arts_blocked": sorted(one.id for one in ARTS
                                   if missing and any(
                                       name in _assembled(one)
                                       for name in missing)),
        }
        # Vocabulary: an art's family and the moves it composes must be real.
        bad_family = sorted({a.family for a in ARTS
                             if a.family not in incantation.FAMILIES})
        bad_compose = sorted({cid for a in ARTS for cid in a.composes
                              if cid not in incantation.BY_ID})
        report["unknown_families"] = bad_family
        report["unknown_composed_moves"] = bad_compose
        report["id_collisions"] = sorted(set(ART_BY_ID) & set(incantation.BY_ID))
        report["hole_kinds_agree"] = tuple(sorted(HOLE_KINDS)) == tuple(
            sorted(incantation.HOLE_KINDS))
    except Exception as exc:                   # pragma: no cover - diagnostics
        report["combat_cross_check"] = "unavailable: %s" % exc

    # -- no discovery bonus, mechanically ----------------------------------
    # `Art` has no power field and `_art` has no power parameter, so there is
    # nowhere for a finder's bonus to be typed. This asserts that rather than
    # claiming it.
    import inspect as _inspect
    report["no_discovery_bonus"] = {
        "art_has_no_power_field": "power" not in Art.__dataclass_fields__,
        "constructor_takes_no_power":
            "power" not in _inspect.signature(_art).parameters,
        "power_is_derived": all(
            a.power == suggested_power(a.score) for a in ARTS),
        "multiplier_keys": [],       # deliberately, permanently, empty
    }

    # -- the ladder --------------------------------------------------------
    ladder = {}
    for class_id in CLASS_IDS:
        bands = {0: [], 1: [], 2: []}
        for one in ARTS_BY_CLASS[class_id]:
            bands[_band(REGION_META[KEY_BY_REGION[one.region]]["tier"])].append(
                one.score)
        means = [round(sum(bands[b]) / len(bands[b]), 2) for b in (0, 1, 2)]
        ladder[class_id] = {"band_means": means,
                            "rises": means[0] < means[1] < means[2]}
    report["ladder"] = ladder
    report["ladder_rises_for_every_class"] = all(v["rises"]
                                                 for v in ladder.values())
    report["stage_counts"] = {s.id: len(s.stages) for s in SAGES}
    report["stage_count_rises"] = [len(s.stages) for s in SAGES] == sorted(
        len(s.stages) for s in SAGES)

    # -- hole declarations -------------------------------------------------
    hole_problems = []
    for one in ARTS:
        try:
            specs = one.hole_specs()
        except KeyError as exc:
            hole_problems.append(str(exc))
            continue
        for name, spec in specs.items():
            if spec[0] not in HOLE_KINDS:
                hole_problems.append("%s: {%s} kind %r" % (one.id, name, spec[0]))
            if spec[0] == MEMBER and len(spec) < 3:
                hole_problems.append("%s: {%s} is a MEMBER hole with no "
                                     "shortlist" % (one.id, name))
        missing = [name for name in specs if name not in one.example]
        if missing:
            hole_problems.append("%s: example misses %s" % (one.id, missing))
    report["hole_problems"] = hole_problems

    # -- vocabularies owned by other modules -------------------------------
    unknown = []
    try:
        from . import classes
        real = tuple(c.id for c in classes.CLASSES)
        if tuple(sorted(real)) != tuple(sorted(CLASS_IDS)):
            unknown.append("class ids drifted: %s vs %s" % (real, CLASS_IDS))
    except Exception as exc:                   # pragma: no cover
        unknown.append("classes unavailable: %s" % exc)
    try:
        from . import skills as skills_mod
        for one in ARTS:
            if one.skill not in skills_mod.SKILLS:
                unknown.append("%s: skill %s" % (one.id, one.skill))
    except Exception as exc:                   # pragma: no cover
        unknown.append("skills unavailable: %s" % exc)
    for sage in SAGES:
        if sage.region not in world.REGION_BY_ID:
            unknown.append("%s: region %s" % (sage.id, sage.region))
        for clause in sage.discovery.needs:
            if clause.get("kind") not in SAGE_CHECKS:
                unknown.append("%s: clause %s" % (sage.id, clause.get("kind")))
        for stage in sage.stages:
            if stage.difficulty not in curriculum.TIERS:
                unknown.append("%s/%s: difficulty %s"
                               % (sage.id, stage.key, stage.difficulty))
    try:
        from .corpus.schema import ENCOUNTER_KINDS, PATTERNS
        for sage in SAGES:
            for stage in sage.stages:
                if stage.kind not in ENCOUNTER_KINDS:
                    unknown.append("%s/%s: kind %s"
                                   % (sage.id, stage.key, stage.kind))
                if stage.pattern and stage.pattern not in PATTERNS:
                    unknown.append("%s/%s: pattern %s"
                                   % (sage.id, stage.key, stage.pattern))
    except Exception as exc:                   # pragma: no cover
        unknown.append("corpus schema unavailable: %s" % exc)
    report["unknown_vocabulary"] = unknown
    report["overlap"] = overlap_report()

    # -- nothing here supplies an answer -----------------------------------
    answerish = []
    for sage in SAGES:
        for label, text in _prose(sage):
            lowered = (text or "").lower()
            answerish += ["%s.%s" % (sage.id, label)
                          for tell in _ANSWER_TELLS if tell in lowered]
    report["answerish_lines"] = answerish

    # -- no dead ends, exercised rather than described ---------------------
    probe = new_state()
    meet(probe, "highlands")
    begin(probe, "highlands", "seer")
    before = (list(probe["arts"]), dict(probe["cleared"]))
    verdict = fail(probe, "highlands", "write", region_clears=4)
    after = (list(probe["arts"]), dict(probe["cleared"]))
    blocked, _ = may_attempt(probe, "highlands", 4)
    allowed, _ = may_attempt(probe, "highlands", 4 + RETURN_TOLL)
    granted = complete(probe, "highlands", "seer")
    report["no_dead_ends"] = {
        "failure_takes_nothing": before == after and verdict["lost"] == [],
        "toll_blocks_immediately": not blocked,
        "toll_clears_after_%d_clears" % RETURN_TOLL: allowed,
        "reattemptable": verdict["reattemptable"],
        "remembers_the_rung": verdict["stage"] == "write",
        "greeting_changes_after_failure":
            greeting("highlands", "seer", probe)["state"] in ("returning",
                                                             "cleared"),
        "clearing_grants_exactly_one_art": granted["granted"]
        and len(probe["arts"]) == 1,
        "second_clear_grants_nothing":
            not complete(probe, "highlands", "seer")["granted"],
    }

    # -- the exam ----------------------------------------------------------
    report["sealed_in_the_exam"] = {
        "sealed_verdict_wins": not available_in("ADVENTURE", "hashmap_highlands",
                                                sealed=True),
        "interview_mode_refused": not available_in("INTERVIEW",
                                                   "hashmap_highlands"),
        "castle_has_none": not available_in("ADVENTURE", "null_kings_castle"),
        "ordinary_region_allows": available_in("ADVENTURE",
                                               "hashmap_highlands"),
        "capability": CAPABILITY,
    }

    # -- discovery ---------------------------------------------------------
    empty = {row["sage"]: discovery_progress(row["sage"], {})["met"]
             for row in ladder_view()}
    report["discovery"] = {
        "every_sage_has_conditions": all(s.discovery.needs for s in SAGES),
        "nothing_is_free_at_zero_evidence": not any(empty.values()),
        "clause_kinds_used": sorted({c.get("kind")
                                     for s in SAGES
                                     for c in s.discovery.needs}),
        "clause_kinds_available": sorted(SAGE_CHECKS),
        "late_sages_gate_on_earlier_arts":
            sorted(s.id for s in SAGES
                   if any(c.get("kind") == "arts_known"
                          for c in s.discovery.needs)),
    }

    # -- the corpus, if we were given one ----------------------------------
    if problems is not None:
        pool = [p for p in problems if not getattr(p, "sealed", False)]
        live = {p.id for p in pool}
        prefer_ids = [pid for s in SAGES for st in s.stages for pid in st.prefer]
        rows, unresolved, relaxed = [], [], 0
        for sage in SAGES:
            for class_id in CLASS_IDS:
                plan = resolve_gauntlet(sage.id, class_id, pool)
                unresolved += plan["unresolved"]
                relaxed += sum(1 for r in plan["stages"]
                               if str(r.get("resolved", "")).startswith("relaxed"))
                rows.append(plan)
        report["corpus"] = {
            "problems_considered": len(pool),
            "gauntlets_resolved": len(rows),
            "stages_resolved": sum(len(r["stages"]) for r in rows),
            "authored_prefer_ids": len(prefer_ids),
            "prefer_ids_still_live": sum(1 for pid in prefer_ids if pid in live),
            "dead_prefer_ids": sorted({pid for pid in prefer_ids
                                       if pid not in live}),
            "stages_that_had_to_relax": relaxed,
            "stages_with_nothing_at_all": sorted(set(unresolved)),
            "every_gauntlet_resolves": not unresolved,
        }
        # A second attempt must not be the same five problems.
        first = resolve_gauntlet("ruins", "warden", pool, attempt=0)
        second = resolve_gauntlet("ruins", "warden", pool, attempt=1)
        report["corpus"]["reshuffles_on_retry"] = (
            [r["problem"] for r in first["stages"]]
            != [r["problem"] for r in second["stages"]])

    report["ok"] = bool(
        report["every_art_casts"]
        and not report["hole_problems"]
        and not report["unknown_vocabulary"]
        and not report["answerish_lines"]
        and report["six_faces_each"] and report["one_art_per_face"]
        and report["ladder_rises_for_every_class"]
        and all(report["no_dead_ends"].values())
        and all(report["sealed_in_the_exam"][k] for k in
                ("sealed_verdict_wins", "interview_mode_refused",
                 "castle_has_none", "ordinary_region_allows"))
        and report["discovery"]["every_sage_has_conditions"]
        and report["discovery"]["nothing_is_free_at_zero_evidence"]
        and report.get("separation", {}).get(
            "every_art_above_every_ordinary_move", True)
    )
    # `ok` is this file's internal consistency and it is still worth having.
    # `ships` is the harder question and it is the one the wiring pass has to
    # read: on the engine's own ruler these arts do not out-demand the ordinary
    # lines they stand beside, and a catalogue that fails that is a catalogue of
    # weaker moves with better names.
    # -- what the wiring pass still owes, per sage -------------------------
    # A discovery clause is only as real as the evidence key behind it. Nine
    # sages currently gate on keys nothing emits, so they are unfindable for a
    # reason no player could ever diagnose. Named here rather than discovered
    # in play.
    try:
        import inspect as _isp
        import re as _re
        from .engine import Game as _Game
        emitted = set(_re.findall(r'"([a-z_]+)":',
                                  _isp.getsource(_Game._pet_evidence)))
    except Exception:                          # pragma: no cover - diagnostics
        emitted = set()
    wanted, blocked = {}, {}
    for sage in SAGES:
        for clause in sage.discovery.needs:
            key = SAGE_CHECKS.get(clause.get("kind", ""), ("", ""))[0]
            wanted.setdefault(key, []).append(sage.id)
            reachable = emitted if emitted else PETS_SHARED_KEYS
            if key and key not in reachable and key != "arts":
                blocked.setdefault(sage.id, []).append(key)
    known = set(EVIDENCE_SOURCES) | PETS_SHARED_KEYS
    report["wiring"] = {
        "evidence_keys_used": sorted(wanted),
        "documented_here": sorted(EVIDENCE_SOURCES),
        "shared_with_pets": sorted(PETS_SHARED_KEYS),
        # A key with no description here and no pets clause behind it is a
        # clause nobody can implement. Judged against the two declared sets,
        # never against whatever `inspect` managed to read.
        "undocumented": sorted(k for k in wanted if k and k not in known),
        "engine_source_readable": bool(emitted),
        "emitted_by_engine": sorted(emitted),
        "keys_still_owed": sorted({k for keys in blocked.values() for k in keys}),
        "sages_unfindable_until_then": sorted(blocked),
        "count": "%d of %d" % (len(blocked), len(SAGES)),
        "single_clause_sages_at_risk": sorted(
            s.id for s in SAGES
            if len(s.discovery.needs) == 1 and s.id in blocked),
        "note": "Every key is described in `sages.EVIDENCE_SOURCES`. Until "
                "`engine.Game._pet_evidence()` returns them, these sages are "
                "in the world and cannot be found, which a player cannot tell "
                "apart from them not existing.",
    }

    report["real_ruler_holds"] = bool(
        report.get("real_ruler_separation", {}).get("holds", False))
    report["ships"] = bool(report["ok"] and report["real_ruler_holds"])
    # `ok` is this file's own integrity. `ready` is whether the arts can
    # actually be cast today, which additionally needs the one-token edit in
    # `incantation` that `report["handover"]` names. They are reported
    # separately so that a red light points at the right module.
    report["ready"] = bool(report["ok"]
                           and report.get("handover", {}).get("satisfied", True))
    report["blocked_on"] = ([] if report["ready"]
                            else [report.get("handover", {}).get("edit", "")])
    return report


if __name__ == "__main__":                     # pragma: no cover
    import json as _json
    print(_json.dumps(self_check(), indent=2, default=str))
