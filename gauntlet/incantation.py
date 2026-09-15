"""Typed-Python combat: the incantation system.

The player asked for a battle where the move IS the Python. Enemies are named
after the variables they embody — SEEN the Hollow Set is the variable ``seen``,
COUNTS the Tally Wraith is ``counts`` — and an attack is a real line of Python
typed against them. The template is shown in grey; the player fills the blanks
from the names standing in front of him.

The input rule is borrowed from one specific piece of design and nothing else:
the sequence is checked for CORRECTNESS, not speed. There is no timer in
Adventure Mode. A wrong cast does not hurt the player, it WASTES THE TURN — the
enemy acts and the player tries again. That is the whole punishment, and it is
enough, because the cost of being wrong is the thing that makes being right
memorable.

Why it is built the way it is:

  RETRIEVAL PRACTICE  Typing a line from memory is retrieval. Reading it again
      is not. So the player types, always; nothing here is multiple choice.
  GENERATION EFFECT   The answer is produced, never recognised.
  DESIRABLE DIFFICULTY  The wasted turn is the difficulty. It is never punitive
      beyond the turn — no stat loss, no gear damage, no dead end.
  INTERLEAVING        One battle fields several different enemies demanding
      several different incantations, so the player has to work out WHICH
      idiom applies before he can execute it. Discrimination is the skill;
      drilling one idiom ten times in a row does not build it.
  SPACING             Within a fight, repetition builds fluency. Across days,
      the SRS builds retention. Cast statistics here feed that scheduler.

Validation happens in three layers because the three failures teach different
lessons and must not be collapsed into one red buzzer:

  1. SYNTAX     Does the assembled line parse? ``ast.parse``, nothing else.
  2. BINDING    Do the names the player typed actually exist on this field?
                A beautifully-formed line naming a variable that is not there
                is the single most instructive failure in the game. It is
                exactly the timed practical mistake of using an undefined name.
  3. SEMANTICS  Does the line, RUN against the battle state, do what the
                incantation promises? It is executed in the sandbox. Nothing
                here pattern-matches the player's string against a stored
                answer, which is why ``counts.get(k, 0) + 1`` and
                ``counts.get(k,0)+1`` are the same cast and ``SEEN`` and
                ``seen`` are not.

Nothing in this module executes player text in-process. Every run goes through
``gauntlet.sandbox``.

Pure stdlib. Importing this module has no side effects beyond building the
catalogue, which is plain data.
"""
from __future__ import annotations

import ast
import io
import keyword
import re
import time
import tokenize
from dataclasses import dataclass, field, asdict

from . import sandbox

BLANK = "____"
SHAPE_BLANK = "___"

# ---------------------------------------------------------------------------
# Holes
# ---------------------------------------------------------------------------
# A template is source text with holes written as {name}. The KIND says what may
# legally fill the hole, and it is the kind that decides which teaching line the
# player gets when the fill is wrong.

ENEMY = "enemy"        # must name an enemy standing on the field
NAME = "name"          # must name any variable bound in this battle
MEMBER = "member"      # a method or attribute name, from a declared shortlist
LITERAL = "literal"    # a constant: a number, a string, True/False/None
EXPR = "expr"          # any expression whose free names are all bound
BINDER = "binder"      # a name the player INVENTS, bound by the line itself —
                       # a loop variable, a comprehension target. It is not
                       # looked up in the battle context, it is added to it for
                       # the length of the line.

HOLE_KINDS = (ENEMY, NAME, MEMBER, LITERAL, EXPR, BINDER)


@dataclass(frozen=True)
class Hole:
    """One blank in an incantation template."""
    name: str
    kind: str
    role: str                 # what this slot IS, in the game's words
    allowed: tuple = ()       # MEMBER holes only: the legal member names

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Incantation:
    """One idiom the player learns, equips and types."""
    id: str
    name: str                 # the display name: what the moveset lists
    template: str             # source text with {holes}
    holes: tuple              # tuple[Hole], in order of first appearance
    skill: str                # the skill this trains (gauntlet.skills.SKILLS)
    chapter: int              # index into curriculum.CHAPTERS; when it unlocks
    note: str                 # ONE line: when you reach for this
    family: str               # weakness/resistance key, and the SRS family
    effect: str               # effect id the client animates
    cost: int = 2             # focus spent to cast
    power: int = 8            # base damage before tier, weakness and streak
    par_seconds: float = 20.0 # the time a fluent cast takes; used by tier_for
    requires: tuple = ()      # enemy kinds that must be present to demand it
    target: str = ""          # which hole names the enemy being struck
    body: tuple = ()          # block bodies: what runs under a header template
    wrap: str = ""            # "" statement, "return" wrap line+body in a def
    inner: tuple = ()         # extra lines inside the wrapper, before the line
    imports: tuple = ()       # module imports the template needs
    demo: dict = field(default_factory=dict)     # practice bindings: name -> expr
    example: dict = field(default_factory=dict)  # a correct fill of every hole
    snapshot: dict = field(default_factory=dict) # pre-cast probes: key -> expr
    assertion: str = "True"   # post-cast truth test, templated like the line
    miss: str = ""            # what to say when it runs but does nothing

    # -- shape -------------------------------------------------------------
    @property
    def hole_names(self) -> tuple:
        return tuple(h.name for h in self.holes)

    def hole(self, name: str) -> Hole | None:
        for h in self.holes:
            if h.name == name:
                return h
        return None

    @property
    def target_hole(self) -> str:
        """Which hole names the enemy this incantation hits."""
        if self.target:
            return self.target
        for h in self.holes:
            if h.kind == ENEMY:
                return h.name
        return self.holes[0].name if self.holes else ""

    @property
    def is_block(self) -> bool:
        return self.template.rstrip().endswith(":")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "template": self.template,
            "holes": [h.to_dict() for h in self.holes], "skill": self.skill,
            "chapter": self.chapter, "note": self.note, "family": self.family,
            "effect": self.effect, "cost": self.cost, "power": self.power,
            "par_seconds": self.par_seconds, "requires": list(self.requires),
            "target": self.target_hole, "block": self.is_block,
            "client_template": client_template(self.template),
        }


_HOLE_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def holes_in(template: str) -> tuple:
    """Hole names in order of first appearance. Literal ``{}`` is not a hole."""
    seen, out = set(), []
    for match in _HOLE_RE.finditer(template):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            out.append(name)
    return tuple(out)


def fill(template: str, answers: dict) -> str:
    """Substitute answers into a template. Missing answers become ``____``."""
    def swap(match):
        return str(answers.get(match.group(1), BLANK))
    return _HOLE_RE.sub(swap, template)


def client_template(template: str) -> str:
    """``{store}.add({item})`` -> ``{{store}}.add({{item}})``.

    The form web/js/incantui.js parses. It keeps the hole NAMES, which matters
    for the templates that name the same variable twice: CHOOSE writes `{dp}`
    three times and `{i}` four, and a client that cannot see the names draws
    eight blanks for what is really three answers. The doubled brace is the
    client's existing named-hole syntax, so this is a translation and not a
    second format to keep in step.
    """
    return _HOLE_RE.sub(lambda m: "{{%s}}" % m.group(1), template)


def _inc(ident: str, name: str, template: str, *, holes: dict, skill: str,
         chapter: int, note: str, family: str, effect: str, cost: int = 2,
         power: int = 8, par: float = 20.0, requires: tuple = (),
         target: str = "", body: tuple = (), wrap: str = "", inner: tuple = (),
         imports: tuple = (), demo: dict | None = None,
         example: dict | None = None, snapshot: dict | None = None,
         assertion: str = "True", miss: str = "") -> Incantation:
    """Catalogue constructor. Keeps the entries below readable as a table."""
    ordered = []
    for hole_name in holes_in(template):
        spec = holes.get(hole_name)
        if spec is None:
            raise ValueError("%s: hole {%s} has no declaration" % (ident, hole_name))
        kind, role = spec[0], spec[1]
        allowed = tuple(spec[2]) if len(spec) > 2 else ()
        if kind not in HOLE_KINDS:
            raise ValueError("%s: hole {%s} has unknown kind %r"
                             % (ident, hole_name, kind))
        ordered.append(Hole(name=hole_name, kind=kind, role=role, allowed=allowed))
    return Incantation(
        id=ident, name=name, template=template, holes=tuple(ordered), skill=skill,
        chapter=chapter, note=note, family=family, effect=effect, cost=cost,
        power=power, par_seconds=par, requires=tuple(requires), target=target,
        body=tuple(body), wrap=wrap, inner=tuple(inner), imports=tuple(imports),
        demo=dict(demo or {}), example=dict(example or {}),
        snapshot=dict(snapshot or {}), assertion=assertion, miss=miss,
    )


# ---------------------------------------------------------------------------
# The field: enemies are variables
# ---------------------------------------------------------------------------

@dataclass
class Enemy:
    """An enemy IS a Python variable. Its name is a valid identifier.

    ``name`` is the identifier the player must type. ``title`` is what the
    game calls it. The player sees "SEEN, the Hollow Set" and has to produce
    ``seen`` — the shout and the spelling are deliberately different, because
    mistaking one for the other is a NameError and NameErrors are the lesson.
    """
    name: str                 # the identifier: seen, counts, left, window
    title: str                # the monster part: "the Hollow Set"
    kind: str                 # set | dict | list | int | str | deque | heap | grid | func
    binding: str              # source expression that creates it for this battle
    hp: int = 60
    hp_max: int = 60
    weakness: str = ""        # incantation family that strikes true
    resists: tuple = ()       # families that land at half force
    taunt: str = ""

    @property
    def display(self) -> str:
        return "%s, %s" % (self.name.upper(), self.title)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def to_dict(self) -> dict:
        data = asdict(self)
        data["display"] = self.display
        data["resists"] = list(self.resists)
        data["alive"] = self.alive
        return data


# The bestiary. Every entry is an original creature; the only thing borrowed
# from anywhere is the idea that a battle input can be a remembered sequence.
ARCHETYPES = {
    "seen": dict(name="seen", title="the Hollow Set", kind="set", binding="set()",
                 hp=70, weakness="membership", resists=("arith",),
                 taunt="It has no contents and perfect memory."),
    "counts": dict(name="counts", title="the Tally Wraith", kind="dict",
                   binding="{}", hp=80, weakness="counting", resists=("slice",),
                   taunt="It keeps a number beside every name it has heard."),
    "left": dict(name="left", title="the Near Warden", kind="int", binding="0",
                 hp=45, weakness="pointer", taunt="It holds the low ground."),
    "right": dict(name="right", title="the Far Warden", kind="int", binding="4",
                  hp=45, weakness="pointer", taunt="It holds the high ground."),
    "window": dict(name="window", title="the Creeping Frame", kind="deque",
                   binding="deque()", hp=75, weakness="window",
                   taunt="It grows from one end and starves from the other."),
    "total": dict(name="total", title="the Accumulator", kind="int", binding="0",
                  hp=60, weakness="arith", resists=("membership",),
                  taunt="Everything you add to it, it keeps."),
    "nums": dict(name="nums", title="the Ordered Host", kind="list",
                 binding="[3, 1, 4, 1, 5, 9, 2, 6]", hp=90, weakness="index",
                 taunt="Eight of them, and they answer only to position."),
    "stack": dict(name="stack", title="the Last-In Tower", kind="list",
                  binding="[1, 2, 3]", hp=65, weakness="stack",
                  taunt="Only its top will speak to you."),
    "frontier": dict(name="frontier", title="the Spreading Edge", kind="deque",
                     binding="deque(['a'])", hp=85, weakness="queue",
                     taunt="It advances one ring at a time, and never twice."),
    "memo": dict(name="memo", title="the Paid-Once Archive", kind="dict",
                 binding="{}", hp=95, weakness="memo",
                 taunt="Ask it twice and it charges you once."),
    "heap": dict(name="heap", title="the Smallest-First Cairn", kind="heap",
                 binding="[]", hp=80, weakness="heap",
                 taunt="Whatever you bury, the least of it surfaces."),
    "grid": dict(name="grid", title="the Walled Plane", kind="grid",
                 binding="[[1, 2, 3], [4, 5, 6], [7, 8, 9]]", hp=100,
                 weakness="matrix", taunt="Step outside it and you cease."),
    "dp": dict(name="dp", title="the Ledger of Paid Debts", kind="list",
               binding="[1, 1, 0, 0, 0]", hp=110, weakness="dp",
               taunt="Every answer it holds was bought exactly once."),
    "text": dict(name="text", title="the Long Utterance", kind="str",
                 binding="'the rain it raineth'", hp=70, weakness="string",
                 taunt="It is one thing pretending to be many."),
    "graph": dict(name="graph", title="the Tangled Moot", kind="dict",
                  binding="{'a': ['b', 'c'], 'b': ['a'], 'c': []}", hp=95,
                  weakness="graph", taunt="Every name it knows knows others."),
    "best": dict(name="best", title="the High-Water Mark", kind="int",
                 binding="0", hp=55, weakness="extreme",
                 taunt="It only ever moves one way."),
}


@dataclass
class BattleContext:
    """Everything the player's line is allowed to name, and the state it runs in.

    ``bindings`` is the full vocabulary: identifier -> the source expression that
    creates it at the top of the cast. Enemies contribute theirs; supporting
    names (an index, a character, a target sum) contribute the rest. Nothing
    outside this vocabulary may appear in a cast, which is what makes layer 2
    worth having.
    """
    enemies: list = field(default_factory=list)
    support: dict = field(default_factory=dict)   # name -> source expression
    imports: tuple = ()
    modules: tuple = ()          # module names the imports make available
    turn: int = 0
    mode: str = "adventure"      # `adventure` | `interview` (stored mode values)

    # -- vocabulary --------------------------------------------------------
    def enemy_names(self) -> list:
        return [e.name for e in self.enemies]

    def living(self) -> list:
        return [e for e in self.enemies if e.alive]

    def bindings(self) -> dict:
        out = {}
        for enemy in self.enemies:
            out[enemy.name] = enemy.binding
        out.update(self.support)
        return out

    def names(self) -> set:
        return set(self.bindings()) | set(self.modules)

    def kinds(self) -> set:
        """Kinds still standing. A dead dict cannot be demanded of."""
        return {e.kind for e in self.living()}

    def enemy(self, name: str) -> Enemy | None:
        for candidate in self.enemies:
            if candidate.name == name:
                return candidate
        return None

    def setup_lines(self) -> list:
        # Deterministic order so a failing cast is reproducible from the report.
        return ["%s = %s" % (name, expr)
                for name, expr in sorted(self.bindings().items())]

    def to_dict(self) -> dict:
        return {
            "enemies": [e.to_dict() for e in self.enemies],
            "support": dict(self.support),
            "imports": list(self.imports),
            "turn": self.turn,
            "mode": self.mode,
            "vocabulary": sorted(self.names()),
        }


def _imports_for(kinds: set) -> tuple:
    lines, mods = [], []
    if "deque" in kinds:
        lines.append("from collections import deque")
    if "heap" in kinds:
        lines.append("import heapq")
        mods.append("heapq")
    return tuple(lines), tuple(mods)


def spawn(archetype: str, **overrides) -> Enemy:
    """Build one enemy from the bestiary. Overrides let an encounter re-skin it."""
    spec = dict(ARCHETYPES[archetype])
    spec.update(overrides)
    hp = spec.pop("hp", 60)
    return Enemy(hp=hp, hp_max=hp, **spec)


def make_context(archetypes, support: dict | None = None, *,
                 mode: str = "adventure") -> BattleContext:
    """Assemble a field from bestiary keys plus any supporting variables.

    Battles are meant to be LONG and MIXED: several enemies of different kinds
    standing at once, so the player must decide which incantation applies before
    he can type it. That decision is the interleaving, and the interleaving is
    most of the learning.
    """
    enemies = [spawn(key) if isinstance(key, str) else key for key in archetypes]
    kinds = {e.kind for e in enemies}
    if any(e.binding.startswith("deque(") for e in enemies):
        kinds.add("deque")
    lines, mods = _imports_for(kinds)
    return BattleContext(enemies=enemies, support=dict(support or {}),
                         imports=lines, modules=mods, mode=mode)


def practice_context(inc: Incantation) -> BattleContext:
    """The context an incantation is self-tested and drilled in.

    Built from its own ``demo`` bindings: whichever of them its example answers
    point an ENEMY hole at become enemies, the rest are supporting names.
    """
    enemy_names = []
    for hole in inc.holes:
        if hole.kind != ENEMY:
            continue
        answer = inc.example.get(hole.name, "")
        if answer in inc.demo and answer not in enemy_names:
            enemy_names.append(answer)
    enemies, support = [], {}
    for name, expr in inc.demo.items():
        if name in enemy_names:
            # An incantation that demands a kind gets a shade of that kind, so
            # the practice field passes the same castable() test a real one does.
            kind = inc.requires[0] if inc.requires else _kind_of(expr)
            enemies.append(Enemy(name=name, title="the Practice Shade",
                                 kind=kind, binding=expr,
                                 hp=40, hp_max=40, weakness=inc.family))
        else:
            support[name] = expr
    imports = tuple(inc.imports)
    modules = tuple(m for m in ("heapq",) if any("import " + m in i for i in imports))
    return BattleContext(enemies=enemies, support=support, imports=imports,
                         modules=modules)


def _kind_of(expr: str) -> str:
    """Infer an enemy's kind from the expression that creates it."""
    text = expr.strip()
    if text.startswith("deque("):
        return "deque"
    if text.startswith("set(") or (text.startswith("{") and ":" not in text
                                   and text != "{}"):
        return "set"
    if text.startswith("{"):
        return "dict"
    if text.startswith("[["):
        return "grid"
    if text.startswith("["):
        return "list"
    if text.startswith(("'", '"')):
        return "str"
    if text.startswith("lambda"):
        return "func"
    try:
        int(text)
        return "int"
    except ValueError:
        return "value"


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------
# Ordered by chapter, which is the order they can be learned in. Every entry
# carries its own worked example, and every example is executed by self_test()
# before this module is considered fit to ship. If an incantation cannot cast
# itself it has no business asking the player to cast it.

_FOUNDATION: tuple = (

    # -- I. The language itself -------------------------------------------
    _inc("bind", "STRIKE", "{target} = {value}",
         holes={"target": (NAME, "the variable that takes the value"),
                "value": (EXPR, "what it becomes")},
         skill="PYTHON", chapter=0, family="assign", effect="brand",
         note="Naming a result is the whole of programming. Reach for it first.",
         cost=1, power=6, par=12.0,
         demo={"total": "0", "nums": "[3, 1, 4]"},
         example={"target": "total", "value": "len(nums)"},
         snapshot={"old": "{target}"},
         assertion="{target} == ({value}) and {target} != __b__['old']",
         miss="It bound, but to the value it already had. Nothing moved."),

    _inc("advance", "ADVANCE", "{counter} += 1",
         holes={"counter": (ENEMY, "the counter that has to move")},
         skill="PYTHON", chapter=0, family="arith", effect="step",
         note="Every loop that does not advance its own index runs forever.",
         cost=1, power=6, par=10.0, requires=("int",),
         demo={"i": "0"},
         example={"counter": "i"},
         snapshot={"v": "{counter}"},
         assertion="{counter} == __b__['v'] + 1"),

    _inc("gather", "GATHER", "{store}.append({item})",
         holes={"store": (ENEMY, "the list collecting results"),
                "item": (EXPR, "what to put in it")},
         skill="ARRAY", chapter=0, family="list", effect="stack_up",
         note="Build the answer as you go; do not assemble it at the end.",
         power=7, par=14.0, requires=("list",),
         demo={"out": "[]", "word": "'ash'"},
         example={"store": "out", "item": "word"},
         snapshot={"n": "len({store})"},
         assertion="len({store}) == __b__['n'] + 1 and {store}[-1] == ({item})"),

    _inc("measure", "MEASURE", "{size} = len({seq})",
         holes={"size": (NAME, "where the count lands"),
                "seq": (ENEMY, "the thing being measured")},
         skill="PYTHON", chapter=0, family="len", effect="weigh",
         note="Length before loop. Half of all index bugs are length bugs.",
         cost=1, power=6, par=12.0,
         demo={"n": "0", "nums": "[3, 1, 4]"},
         example={"size": "n", "seq": "nums"},
         assertion="{size} == len({seq}) and isinstance({size}, int)"),

    _inc("reach", "REACH", "{value} = {seq}[{index}]",
         holes={"value": (NAME, "where the element lands"),
                "seq": (ENEMY, "the sequence"),
                "index": (EXPR, "the position")},
         skill="ARRAY", chapter=0, family="index", effect="pierce",
         note="Reaching into a sequence by position. Mind the last valid index.",
         power=7, par=14.0,
         demo={"cur": "None", "nums": "[3, 1, 4]", "i": "1"},
         example={"value": "cur", "seq": "nums", "index": "i"},
         snapshot={"old": "{value}"},
         assertion="{value} == {seq}[{index}] and {value} != __b__['old']"),

    _inc("sever", "SEVER", "{part} = {seq}[{start}:{stop}]",
         holes={"part": (NAME, "where the piece lands"),
                "seq": (ENEMY, "the sequence being cut"),
                "start": (EXPR, "first index kept"),
                "stop": (EXPR, "first index dropped")},
         skill="ARRAY", chapter=0, family="slice", effect="cleave",
         note="A slice copies. The stop index is never included — that is the trap.",
         power=8, par=18.0,
         demo={"chunk": "[]", "nums": "[3, 1, 4, 1, 5]", "i": "1", "j": "4"},
         example={"part": "chunk", "seq": "nums", "start": "i", "stop": "j"},
         assertion="{part} == {seq}[{start}:{stop}] "
                   "and len({part}) == max(0, ({stop}) - ({start}))"),

    _inc("swap", "SWAP", "{a}, {b} = {b}, {a}",
         holes={"a": (ENEMY, "one of the pair"), "b": (ENEMY, "the other")},
         skill="PYTHON", chapter=0, family="assign", effect="exchange",
         note="Python swaps in one line. No temporary, no third variable.",
         power=8, par=14.0,
         demo={"lo": "0", "hi": "4"},
         example={"a": "lo", "b": "hi"},
         snapshot={"a": "{a}", "b": "{b}"},
         assertion="{a} == __b__['b'] and {b} == __b__['a'] "
                   "and __b__['a'] != __b__['b']"),

    _inc("probe", "PROBE", "if {item} in {store}:",
         holes={"item": (EXPR, "the thing you are asking about"),
                "store": (ENEMY, "the collection that remembers")},
         skill="SET", chapter=0, family="membership", effect="scry",
         target="store",
         note="Ask before you act. In a set or dict this question is free.",
         power=7, par=16.0,
         body=("__fired__[0] += 1",),
         demo={"seen": "{2, 3}", "x": "3"},
         example={"item": "x", "store": "seen"},
         assertion="__fired__[0] == 1",
         miss="The question was well formed and the answer was no. "
              "Nothing under the branch ran."),

    _inc("guard", "GUARD", "if {item} not in {store}:",
         holes={"item": (EXPR, "the thing that might be new"),
                "store": (ENEMY, "the collection that remembers")},
         skill="SET", chapter=0, family="membership", effect="ward",
         target="store",
         note="The first-sighting test. Everything de-duplicating starts here.",
         power=7, par=16.0,
         body=("__fired__[0] += 1",),
         demo={"seen": "{2, 3}", "x": "5"},
         example={"item": "x", "store": "seen"},
         assertion="__fired__[0] == 1",
         miss="Well formed, but that item was already known, so the guard held."),

    _inc("toll", "TOLL", "{total} += {seq}[{index}]",
         holes={"total": (ENEMY, "the running sum"),
                "seq": (ENEMY, "the sequence being drained"),
                "index": (EXPR, "the position taken")},
         skill="ARRAY", chapter=0, family="arith", effect="drain",
         target="total",
         note="The accumulator step. One element joins the total, then you move on.",
         power=9, par=18.0,
         demo={"total": "0", "nums": "[3, 1, 4]", "i": "2"},
         example={"total": "total", "seq": "nums", "index": "i"},
         snapshot={"t": "{total}"},
         assertion="{total} == __b__['t'] + {seq}[{index}]"),

    # -- II. The four vaults ----------------------------------------------
    _inc("mark", "MARK", "{store}.add({item})",
         holes={"store": (ENEMY, "the set that remembers"),
                "item": (EXPR, "what to remember")},
         skill="SET", chapter=1, family="membership", effect="seal",
         note="Record that you have been here. The visited-mark, in one line.",
         power=8, par=12.0, requires=("set",),
         demo={"seen": "set()", "x": "7"},
         example={"store": "seen", "item": "x"},
         snapshot={"n": "len({store})", "had": "({item}) in {store}"},
         assertion="({item}) in {store} and len({store}) == "
                   "__b__['n'] + (0 if __b__['had'] else 1)"),

    _inc("hollow", "HOLLOW", "{store} = set()",
         holes={"store": (ENEMY, "the set being emptied into existence")},
         skill="SET", chapter=1, family="construct", effect="void",
         note="An empty set needs set(). Empty braces build a dict, not a set.",
         cost=1, power=6, par=10.0,
         demo={"seen": "{1, 2}"},
         example={"store": "seen"},
         assertion="{store} == set() and isinstance({store}, set)"),

    _inc("ledger", "LEDGER", "{book} = {}",
         holes={"book": (ENEMY, "the dict being opened")},
         skill="HASH_MAP", chapter=1, family="construct", effect="open_book",
         note="The empty dict. Reach for it the moment you need 'seen it before'.",
         cost=1, power=6, par=10.0,
         demo={"counts": "{'a': 1}"},
         example={"book": "counts"},
         assertion="{book} == {} and isinstance({book}, dict)"),

    _inc("inscribe", "INSCRIBE", "{book}[{key}] = {value}",
         holes={"book": (ENEMY, "the dict being written to"),
                "key": (EXPR, "what it is filed under"),
                "value": (EXPR, "what is filed")},
         skill="HASH_MAP", chapter=1, family="dict", effect="inscribe",
         note="Writing a key that does not exist creates it. Reading one does not.",
         power=8, par=16.0, requires=("dict",),
         demo={"counts": "{}", "ch": "'a'", "n": "4"},
         example={"book": "counts", "key": "ch", "value": "n"},
         assertion="{book}[{key}] == ({value})"),

    _inc("ask", "ASK", "{out} = {book}.get({key}, {default})",
         holes={"out": (NAME, "where the answer lands"),
                "book": (ENEMY, "the dict being questioned"),
                "key": (EXPR, "what you are asking for"),
                "default": (LITERAL, "what to say when it is absent")},
         skill="HASH_MAP", chapter=1, family="dict", effect="query",
         note="get with a default never raises. Square brackets do.",
         power=8, par=18.0, requires=("dict",),
         demo={"cur": "None", "counts": "{'a': 2}", "ch": "'z'"},
         example={"out": "cur", "book": "counts", "key": "ch", "default": "0"},
         assertion="{out} == {book}.get({key}, {default}) and {out} is not None"),

    _inc("tally", "TALLY", "{book}[{key}] = {book}.get({key}, 0) + 1",
         holes={"book": (ENEMY, "the dict keeping score"),
                "key": (EXPR, "the thing being counted")},
         skill="HASH_MAP", chapter=1, family="counting", effect="tally",
         note="Count-by-key without a KeyError. The highest-yield line in timed practicals.",
         cost=3, power=12, par=26.0, requires=("dict",),
         demo={"counts": "{}", "ch": "'a'"},
         example={"book": "counts", "key": "ch"},
         snapshot={"prev": "{book}.get({key}, 0)"},
         assertion="{book}[{key}] == __b__['prev'] + 1"),

    _inc("settle", "SETTLE", "{book}.setdefault({key}, []).append({item})",
         holes={"book": (ENEMY, "the dict of groups"),
                "key": (EXPR, "the group's signature"),
                "item": (EXPR, "the member joining it")},
         skill="HASH_MAP", chapter=1, family="grouping", effect="gather_flock",
         note="Grouping: make the bucket if absent, then drop the item in it.",
         cost=3, power=13, par=30.0, requires=("dict",),
         demo={"groups": "{}", "sig": "'abc'", "word": "'cab'"},
         example={"book": "groups", "key": "sig", "item": "word"},
         snapshot={"n": "len({book}.get({key}, []))"},
         assertion="{book}[{key}][-1] == ({item}) "
                   "and len({book}[{key}]) == __b__['n'] + 1"),

    _inc("release", "RELEASE", "{store}.discard({item})",
         holes={"store": (ENEMY, "the set letting go"),
                "item": (EXPR, "what leaves it")},
         skill="SET", chapter=1, family="membership", effect="unseal",
         note="discard forgives a missing element. remove raises on it.",
         power=8, par=14.0, requires=("set",),
         demo={"seen": "{1, 2, 3}", "x": "2"},
         example={"store": "seen", "item": "x"},
         snapshot={"had": "({item}) in {store}"},
         assertion="({item}) not in {store} and __b__['had']",
         miss="It ran, but that element was never in there to begin with."),

    _inc("draw", "DRAW", "{top} = {stack}.pop()",
         holes={"top": (NAME, "where the taken value lands"),
                "stack": (ENEMY, "the list being emptied from the end")},
         skill="STACK", chapter=1, family="stack", effect="unstack",
         note="pop takes from the end, and the end is the cheapest place to take from.",
         power=9, par=16.0, requires=("list",),
         demo={"cur": "None", "stack": "[1, 2, 3]"},
         example={"top": "cur", "stack": "stack"},
         snapshot={"n": "len({stack})", "last": "{stack}[-1] if {stack} else None"},
         assertion="{top} == __b__['last'] and len({stack}) == __b__['n'] - 1"),

    _inc("rollcall", "ROLLCALL", "{out} = sorted({book})",
         holes={"out": (NAME, "where the ordered names land"),
                "book": (ENEMY, "the dict being read")},
         skill="HASH_MAP", chapter=1, family="dict", effect="rollcall",
         note="Sorting a dict sorts its KEYS. Say .items() when you want both.",
         power=8, par=16.0, requires=("dict",),
         demo={"keys": "[]", "counts": "{'b': 1, 'a': 2}"},
         example={"out": "keys", "book": "counts"},
         assertion="{out} == sorted({book}) and {out} == sorted(list({book}))"),
)


# -- III. The idioms, and IV. counting and membership ----------------------
_IDIOM: tuple = (

    _inc("mirror", "MIRROR", "{out} = [{expr} for {var} in {seq}]",
         holes={"out": (NAME, "where the new list lands"),
                "expr": (EXPR, "what each element becomes"),
                "var": (BINDER, "the name you give each element"),
                "seq": (ENEMY, "the sequence being read")},
         skill="PYTHON", chapter=2, family="comprehension", effect="mirror",
         note="Transform every element. A comprehension, not a loop with append.",
         cost=3, power=11, par=26.0,
         demo={"out": "[]", "nums": "[1, 2, 3]"},
         example={"out": "out", "expr": "n * 2", "var": "n", "seq": "nums"},
         assertion="{out} == [{expr} for {var} in {seq}] and len({out}) == len({seq})"),

    _inc("sift", "SIFT", "{out} = [{var} for {var} in {seq} if {cond}]",
         holes={"out": (NAME, "where the survivors land"),
                "var": (BINDER, "the name you give each element"),
                "seq": (ENEMY, "the sequence being filtered"),
                "cond": (EXPR, "what an element must satisfy")},
         skill="PYTHON", chapter=2, family="comprehension", effect="sift",
         note="Keep only what passes. The filter belongs at the end, after the for.",
         cost=3, power=11, par=28.0,
         demo={"keep": "[]", "nums": "[1, 2, 3, 4]"},
         example={"out": "keep", "var": "n", "seq": "nums", "cond": "n % 2 == 0"},
         assertion="{out} == [{var} for {var} in {seq} if {cond}] "
                   "and len({out}) <= len({seq})"),

    _inc("numbering", "NUMBERING", "for {i}, {item} in enumerate({seq}):",
         holes={"i": (BINDER, "the name for the position"),
                "item": (BINDER, "the name for the element"),
                "seq": (ENEMY, "the sequence being walked")},
         skill="PYTHON", chapter=2, family="iterate", effect="number",
         note="When you need the index AND the value, enumerate gives you both.",
         cost=2, power=10, par=22.0,
         body=("__fired__[0] += 1",),
         demo={"nums": "[3, 1, 4]"},
         example={"i": "i", "item": "n", "seq": "nums"},
         assertion="__fired__[0] == len({seq})"),

    _inc("pairing", "PAIRING", "for {a}, {b} in zip({first}, {second}):",
         holes={"a": (BINDER, "the name for the left element"),
                "b": (BINDER, "the name for the right element"),
                "first": (ENEMY, "the left sequence"),
                "second": (ENEMY, "the right sequence")},
         skill="PYTHON", chapter=2, family="iterate", effect="pair",
         note="Walk two sequences in step. zip stops at the shorter one.",
         cost=2, power=10, par=24.0,
         body=("__fired__[0] += 1",),
         demo={"names": "['a', 'b']", "scores": "[1, 2, 3]"},
         example={"a": "k", "b": "v", "first": "names", "second": "scores"},
         assertion="__fired__[0] == min(len({first}), len({second}))"),

    _inc("march", "MARCH", "for {i} in range(len({seq})):",
         holes={"i": (BINDER, "the name for the index"),
                "seq": (ENEMY, "the sequence being indexed")},
         skill="ARRAY", chapter=2, family="iterate", effect="march",
         note="Only when you genuinely need the index. Otherwise iterate directly.",
         power=9, par=20.0,
         body=("__fired__[0] += 1",),
         demo={"nums": "[3, 1, 4]"},
         example={"i": "i", "seq": "nums"},
         assertion="__fired__[0] == len({seq})"),

    _inc("weigh", "WEIGH", "{out} = sorted({seq}, key={keyfn})",
         holes={"out": (NAME, "where the ordered copy lands"),
                "seq": (ENEMY, "what is being ordered"),
                "keyfn": (EXPR, "the measure to sort by")},
         skill="SORTING", chapter=2, family="sorting", effect="weigh",
         note="key takes a function, not a call. Pass len, not len().",
         cost=3, power=11, par=28.0,
         demo={"order": "[]", "words": "['bbb', 'a', 'cc']"},
         example={"out": "order", "seq": "words", "keyfn": "len"},
         assertion="{out} == sorted({seq}, key={keyfn}) and len({out}) == len({seq})"),

    _inc("greatest", "GREATEST", "{best} = max({best}, {candidate})",
         holes={"best": (ENEMY, "the running maximum"),
                "candidate": (EXPR, "the challenger")},
         skill="ARRAY", chapter=2, family="extreme", effect="crest",
         note="The high-water mark. It only ever moves one way.",
         power=9, par=18.0,
         demo={"best": "0", "span": "7"},
         example={"best": "best", "candidate": "span"},
         snapshot={"b": "{best}"},
         assertion="{best} == max(__b__['b'], {candidate}) and {best} >= __b__['b']"),

    _inc("least", "LEAST", "{best} = min({best}, {candidate})",
         holes={"best": (ENEMY, "the running minimum"),
                "candidate": (EXPR, "the challenger")},
         skill="ARRAY", chapter=2, family="extreme", effect="trough",
         note="The mirror of GREATEST. Seed it with something big enough to lose.",
         power=9, par=18.0,
         demo={"best": "99", "cost": "4"},
         example={"best": "best", "candidate": "cost"},
         snapshot={"b": "{best}"},
         assertion="{best} == min(__b__['b'], {candidate}) and {best} <= __b__['b']"),

    _inc("distill", "DISTILL", "{out} = set({seq})",
         holes={"out": (NAME, "where the unique values land"),
                "seq": (ENEMY, "the sequence with repeats")},
         skill="SET", chapter=2, family="construct", effect="distil",
         note="Dedupe in one move. You lose the order; be sure you can afford to.",
         power=9, par=16.0,
         demo={"unique": "set()", "nums": "[1, 1, 2]"},
         example={"out": "unique", "seq": "nums"},
         assertion="{out} == set({seq}) and len({out}) <= len({seq})"),

    _inc("weave", "WEAVE", "{out} = {glue}.join({parts})",
         holes={"out": (NAME, "where the finished string lands"),
                "glue": (LITERAL, "what goes between the pieces"),
                "parts": (ENEMY, "the pieces")},
         skill="STRING", chapter=2, family="string", effect="weave",
         note="Build strings with join, never with += in a loop.",
         power=10, par=22.0,
         demo={"text": "''", "parts": "['a', 'b']"},
         example={"out": "text", "glue": "''", "parts": "parts"},
         assertion="{out} == {glue}.join({parts}) and isinstance({out}, str)"),

    _inc("unravel", "UNRAVEL", "{parts} = {text}.split({sep})",
         holes={"parts": (NAME, "where the pieces land"),
                "text": (ENEMY, "the string being cut"),
                "sep": (LITERAL, "what separates the pieces")},
         skill="STRING", chapter=2, family="string", effect="unravel",
         note="split with no argument collapses all whitespace. With one, it does not.",
         power=9, par=20.0,
         demo={"parts": "[]", "line": "'a b c'"},
         example={"parts": "parts", "text": "line", "sep": "' '"},
         assertion="{parts} == {text}.split({sep}) and isinstance({parts}, list)"),

    _inc("temper", "TEMPER", "{out} = {text}.{method}()",
         holes={"out": (NAME, "where the normalised string lands"),
                "text": (ENEMY, "the string being tidied"),
                "method": (MEMBER, "the tidying to apply",
                           ("lower", "upper", "strip", "title", "casefold"))},
         skill="STRING", chapter=2, family="string", effect="temper",
         note="Normalise before you compare, or case and whitespace will lie to you.",
         power=9, par=20.0,
         demo={"out": "''", "line": "'  Mixed Case  '"},
         example={"out": "out", "text": "line", "method": "strip"},
         snapshot={"old": "{text}"},
         assertion="{out} == {text}.{method}() and isinstance({out}, str) "
                   "and {out} != __b__['old']"),

    _inc("complement", "COMPLEMENT", "{need} = {target} - {seq}[{i}]",
         holes={"need": (NAME, "where the missing half lands"),
                "target": (ENEMY, "the sum you are chasing"),
                "seq": (ENEMY, "the numbers"),
                "i": (EXPR, "the position you are standing on")},
         skill="HASH_MAP", chapter=3, family="counting", effect="complement",
         target="seq",
         note="Two-sum in one thought: ask what is missing, then look it up.",
         cost=3, power=12, par=26.0,
         demo={"need": "0", "goal": "9", "nums": "[2, 7]", "i": "0"},
         example={"need": "need", "target": "goal", "seq": "nums", "i": "i"},
         assertion="{need} == {target} - {seq}[{i}]"),

    _inc("indexbook", "INDEXBOOK", "{book}[{seq}[{i}]] = {i}",
         holes={"book": (ENEMY, "the dict from value to position"),
                "seq": (ENEMY, "the sequence"),
                "i": (EXPR, "the position being filed")},
         skill="HASH_MAP", chapter=3, family="counting", effect="file",
         target="book",
         note="Remember WHERE you saw it, not just that you did.",
         cost=3, power=12, par=28.0, requires=("dict",),
         demo={"seen": "{}", "nums": "[2, 7]", "i": "1"},
         example={"book": "seen", "seq": "nums", "i": "i"},
         assertion="{book}[{seq}[{i}]] == ({i})"),

    _inc("countdown", "COUNTDOWN", "{book}[{key}] -= 1",
         holes={"book": (ENEMY, "the dict keeping score"),
                "key": (EXPR, "whose count falls")},
         skill="HASH_MAP", chapter=3, family="counting", effect="untally",
         note="The other half of counting. Anagram checks live and die here.",
         power=10, par=18.0, requires=("dict",),
         demo={"counts": "{'a': 2}", "ch": "'a'"},
         example={"book": "counts", "key": "ch"},
         snapshot={"prev": "{book}[{key}]"},
         assertion="{book}[{key}] == __b__['prev'] - 1"),

    _inc("purge", "PURGE", "del {book}[{key}]",
         holes={"book": (ENEMY, "the dict losing an entry"),
                "key": (EXPR, "the entry that goes")},
         skill="HASH_MAP", chapter=3, family="dict", effect="erase",
         note="Delete when a count hits zero, or your 'is it empty' test lies.",
         power=10, par=16.0, requires=("dict",),
         demo={"counts": "{'a': 1, 'b': 2}", "ch": "'a'"},
         example={"book": "counts", "key": "ch"},
         snapshot={"n": "len({book})"},
         assertion="({key}) not in {book} and len({book}) == __b__['n'] - 1"),
)


# -- V. Scanning a sequence, and VI. order and structure -------------------
_SCANNING: tuple = (

    _inc("converge", "CONVERGE", "while {left} < {right}:",
         holes={"left": (ENEMY, "the near pointer"),
                "right": (ENEMY, "the far pointer")},
         skill="TWO_POINTER", chapter=4, family="pointer", effect="converge",
         note="Two pointers walking toward each other. They must be able to meet.",
         cost=3, power=12, par=22.0, requires=("int",),
         body=("__fired__[0] += 1", "{left} += 1"),
         demo={"lo": "0", "hi": "3"},
         example={"left": "lo", "right": "hi"},
         assertion="{left} >= {right} and __fired__[0] > 0",
         miss="The condition was already false, so the wardens never closed."),

    _inc("shrink", "SHRINK", "while {total} > {limit}:",
         holes={"total": (ENEMY, "the quantity that is too large"),
                "limit": (EXPR, "what it must come back under")},
         skill="SLIDING_WINDOW", chapter=4, family="window", effect="shrink",
         note="The window contracts only while it is illegal. Not once — while.",
         cost=3, power=13, par=24.0,
         body=("__fired__[0] += 1", "{total} -= 1"),
         demo={"total": "5", "cap": "2"},
         example={"total": "total", "limit": "cap"},
         assertion="{total} <= {limit} and __fired__[0] > 0",
         miss="Nothing inside the loop made the quantity smaller, or it was "
              "already legal."),

    _inc("inhale", "INHALE", "{total} += {seq}[{right}]",
         holes={"total": (ENEMY, "the window's running value"),
                "seq": (ENEMY, "the sequence"),
                "right": (EXPR, "the arriving edge")},
         skill="SLIDING_WINDOW", chapter=4, family="window", effect="inhale",
         target="total",
         note="The window's right edge steps forward and takes on one element.",
         power=10, par=20.0,
         demo={"total": "0", "nums": "[3, 1, 4]", "hi": "1"},
         example={"total": "total", "seq": "nums", "right": "hi"},
         snapshot={"t": "{total}"},
         assertion="{total} == __b__['t'] + {seq}[{right}]"),

    _inc("exhale", "EXHALE", "{total} -= {seq}[{left}]",
         holes={"total": (ENEMY, "the window's running value"),
                "seq": (ENEMY, "the sequence"),
                "left": (EXPR, "the departing edge")},
         skill="SLIDING_WINDOW", chapter=4, family="window", effect="exhale",
         target="total",
         note="What leaves the window must be subtracted, or the total is a lie.",
         power=10, par=20.0,
         demo={"total": "10", "nums": "[3, 1, 4]", "lo": "0"},
         example={"total": "total", "seq": "nums", "left": "lo"},
         snapshot={"t": "{total}"},
         assertion="{total} == __b__['t'] - {seq}[{left}]"),

    _inc("frame", "FRAME", "{window}.append({seq}[{right}])",
         holes={"window": (ENEMY, "the frame itself"),
                "seq": (ENEMY, "the sequence being crossed"),
                "right": (EXPR, "the arriving position")},
         skill="SLIDING_WINDOW", chapter=4, family="window", effect="frame",
         target="window",
         note="A deque takes from both ends in constant time. A list does not.",
         power=10, par=22.0, requires=("deque",),
         imports=("from collections import deque",),
         demo={"window": "deque()", "nums": "[3, 1, 4]", "hi": "2"},
         example={"window": "window", "seq": "nums", "right": "hi"},
         snapshot={"n": "len({window})"},
         assertion="len({window}) == __b__['n'] + 1 "
                   "and {window}[-1] == {seq}[{right}]"),

    _inc("evict", "EVICT", "{gone} = {window}.popleft()",
         holes={"gone": (NAME, "where the dropped value lands"),
                "window": (ENEMY, "the frame losing its oldest member")},
         skill="SLIDING_WINDOW", chapter=4, family="window", effect="evict",
         target="window",
         note="popleft is why the window is a deque. From a list it costs O(n).",
         power=10, par=18.0, requires=("deque",),
         imports=("from collections import deque",),
         demo={"gone": "None", "window": "deque([1, 2, 3])"},
         example={"gone": "gone", "window": "window"},
         snapshot={"n": "len({window})", "head": "{window}[0] if {window} else None"},
         assertion="{gone} == __b__['head'] and len({window}) == __b__['n'] - 1"),

    _inc("span", "SPAN", "{best} = max({best}, {right} - {left} + 1)",
         holes={"best": (ENEMY, "the longest run so far"),
                "right": (ENEMY, "the far edge"),
                "left": (ENEMY, "the near edge")},
         skill="SLIDING_WINDOW", chapter=4, family="window", effect="span",
         target="best",
         note="Window length is right minus left plus one. The plus one is the bug.",
         cost=3, power=13, par=26.0,
         demo={"best": "0", "hi": "4", "lo": "1"},
         example={"best": "best", "right": "hi", "left": "lo"},
         snapshot={"b": "{best}"},
         assertion="{best} == max(__b__['b'], ({right}) - ({left}) + 1)"),

    _inc("prefix", "PREFIX", "{sums}.append({sums}[-1] + {seq}[{i}])",
         holes={"sums": (ENEMY, "the running totals"),
                "seq": (ENEMY, "the numbers"),
                "i": (EXPR, "the position being folded in")},
         skill="PREFIX_SUM", chapter=4, family="prefix", effect="prefix",
         target="sums",
         note="Each prefix is the one before it plus one element. Seed it with zero.",
         cost=3, power=13, par=28.0,
         demo={"sums": "[0]", "nums": "[3, 1, 4]", "i": "1"},
         example={"sums": "sums", "seq": "nums", "i": "i"},
         snapshot={"n": "len({sums})", "last": "{sums}[-1]"},
         assertion="len({sums}) == __b__['n'] + 1 "
                   "and {sums}[-1] == __b__['last'] + {seq}[{i}]"),

    _inc("peek", "PEEK", "{top} = {stack}[-1]",
         holes={"top": (NAME, "where the glimpse lands"),
                "stack": (ENEMY, "the tower being looked at")},
         skill="STACK", chapter=5, family="stack", effect="peek",
         note="Look without taking. Check it is not empty first.",
         power=9, par=14.0,
         demo={"cur": "None", "stack": "[1, 2, 3]"},
         example={"top": "cur", "stack": "stack"},
         snapshot={"n": "len({stack})"},
         assertion="{top} == {stack}[-1] and len({stack}) == __b__['n']"),

    _inc("dequeue", "DEQUEUE", "{node} = {frontier}.popleft()",
         holes={"node": (NAME, "where the next thing to visit lands"),
                "frontier": (ENEMY, "the advancing edge")},
         skill="QUEUE", chapter=5, family="queue", effect="dequeue",
         target="frontier",
         note="Breadth-first takes from the FRONT. Take from the back and it is depth-first.",
         power=10, par=18.0, requires=("deque",),
         imports=("from collections import deque",),
         demo={"cur": "None", "frontier": "deque(['a', 'b'])"},
         example={"node": "cur", "frontier": "frontier"},
         snapshot={"n": "len({frontier})",
                   "head": "{frontier}[0] if {frontier} else None"},
         assertion="{node} == __b__['head'] and len({frontier}) == __b__['n'] - 1"),

    _inc("sink", "SINK", "heapq.heappush({heap}, {item})",
         holes={"heap": (ENEMY, "the cairn"),
                "item": (EXPR, "what you bury in it")},
         skill="HEAP", chapter=5, family="heap", effect="sink",
         note="A heap is a list you only touch through heapq. Never sort it yourself.",
         cost=3, power=12, par=24.0, requires=("heap",),
         imports=("import heapq",),
         demo={"heap": "[]", "cost": "5"},
         example={"heap": "heap", "item": "cost"},
         snapshot={"n": "len({heap})"},
         assertion="len({heap}) == __b__['n'] + 1 and ({item}) in {heap}"),

    _inc("surface", "SURFACE", "{item} = heapq.heappop({heap})",
         holes={"item": (NAME, "where the smallest lands"),
                "heap": (ENEMY, "the cairn")},
         skill="HEAP", chapter=5, family="heap", effect="surface",
         target="heap",
         note="heappop always returns the smallest. For the largest, push negatives.",
         cost=3, power=12, par=22.0, requires=("heap",),
         imports=("import heapq",),
         demo={"cur": "None", "heap": "[1, 3, 5]"},
         example={"item": "cur", "heap": "heap"},
         snapshot={"n": "len({heap})", "top": "{heap}[0] if {heap} else None"},
         assertion="{item} == __b__['top'] and len({heap}) == __b__['n'] - 1"),

    _inc("halve", "HALVE", "{mid} = ({left} + {right}) // 2",
         holes={"mid": (NAME, "where the midpoint lands"),
                "left": (ENEMY, "the low bound"),
                "right": (ENEMY, "the high bound")},
         skill="BINARY_SEARCH", chapter=5, family="search", effect="halve",
         note="Integer division, or the midpoint drifts off the grid as a float.",
         cost=3, power=12, par=22.0,
         demo={"mid": "0", "lo": "0", "hi": "7"},
         example={"mid": "mid", "left": "lo", "right": "hi"},
         assertion="{mid} == ({left} + {right}) // 2 and isinstance({mid}, int)"),

    _inc("narrow", "NARROW", "{left} = {mid} + 1",
         holes={"left": (ENEMY, "the bound that moves"),
                "mid": (ENEMY, "the midpoint you just ruled out")},
         skill="BINARY_SEARCH", chapter=5, family="search", effect="narrow",
         note="Move past the midpoint, not to it, or the search never terminates.",
         power=10, par=16.0,
         demo={"lo": "0", "mid": "3"},
         example={"left": "lo", "mid": "mid"},
         assertion="{left} == {mid} + 1"),
)


# -- VII to X. Recursion, traversal, paying once, and the craft ------------
_DEPTH: tuple = (

    _inc("sentinel", "SENTINEL", "if not {seq}:",
         holes={"seq": (ENEMY, "the thing that might be empty")},
         skill="PYTHON", chapter=6, family="guard", effect="sentinel",
         note="The empty case, handled first. It is the test you will be given.",
         cost=1, power=8, par=12.0,
         body=("__fired__[0] += 1",),
         demo={"nums": "[]"},
         example={"seq": "nums"},
         assertion="__fired__[0] == 1",
         miss="It ran, and the thing was not empty, so nothing under it fired."),

    _inc("floor", "FLOOR", "if {n} <= 1:",
         holes={"n": (ENEMY, "the shrinking argument")},
         skill="RECURSION", chapter=6, family="base", effect="floor",
         note="The base case. Write it before the recursive call, always.",
         cost=2, power=11, par=16.0,
         wrap="return", body=("return {n}",),
         demo={"n": "1"},
         example={"n": "n"},
         assertion="__r__ == {n}",
         miss="The floor was never reached, so the function fell through it."),

    _inc("descend", "DESCEND", "{total} += {fn}({node})",
         holes={"total": (ENEMY, "what the descent contributes to"),
                "fn": (NAME, "the function calling itself"),
                "node": (EXPR, "the smaller problem")},
         skill="RECURSION", chapter=6, family="recurse", effect="descend",
         target="total",
         note="Trust the recursive call to return the right answer for a smaller input.",
         cost=3, power=13, par=26.0,
         demo={"total": "0", "depth": "lambda v: v * 2", "node": "4"},
         example={"total": "total", "fn": "depth", "node": "node"},
         snapshot={"t": "{total}"},
         assertion="{total} == __b__['t'] + {fn}({node})"),

    _inc("unfold", "UNFOLD", "return {fn}({n} - 1) + {fn}({n} - 2)",
         holes={"fn": (NAME, "the function calling itself"),
                "n": (ENEMY, "the argument that must shrink")},
         skill="RECURSION", chapter=6, family="recurse", effect="unfold",
         target="n",
         note="Two branches, both smaller. Without a base case this never returns.",
         cost=4, power=14, par=30.0,
         wrap="return",
         demo={"fib": "lambda v: 1", "n": "5"},
         example={"fn": "fib", "n": "n"},
         assertion="__r__ == {fn}({n} - 1) + {fn}({n} - 2) and __r__ is not None"),

    # A tree node is not a number, and the integer recursion above cannot touch
    # one: `if node <= 1` is a TypeError, not a base case. These two are the
    # vocabulary a node actually answers to — read what it carries, or walk into
    # one of its children. Without them the tree enemies have no idiom at all.
    _inc("pluck", "PLUCK", "{value} = {node}.val",
         holes={"value": (NAME, "where the payload lands"),
                "node": (ENEMY, "the node you are standing on")},
         skill="RECURSION", chapter=6, family="tree", effect="pluck",
         target="node", requires=("node",),
         note="A node is a value beside its references. Read the value first.",
         cost=2, power=11, par=16.0,
         imports=("from types import SimpleNamespace as Node",),
         demo={"node": "Node(val=5, left=None, right=None, next=None)",
               "cur": "0"},
         example={"value": "cur", "node": "node"},
         assertion="{value} == {node}.val",
         miss="The payload never moved. Reading a field has to land somewhere."),

    _inc("branch", "BRANCH", "{node} = {node}.{side}",
         holes={"node": (ENEMY, "the node you are standing on"),
                "side": (MEMBER, "which reference to follow",
                         ("left", "right", "next"))},
         skill="RECURSION", chapter=6, family="tree", effect="branch",
         target="node", requires=("node",),
         note="Descend by rebinding the name. The child is a whole tree again.",
         cost=3, power=13, par=22.0,
         imports=("from types import SimpleNamespace as Node",),
         demo={"node": "Node(val=5, left=Node(val=3, left=None, right=None, "
                       "next=None), right=None, next=None)"},
         example={"node": "node", "side": "left"},
         snapshot={"kid": "{node}.{side}"},
         assertion="({node} is None) == (__b__['kid'] is None) and "
                   "({node} is None or {node}.val == __b__['kid'].val)",
         miss="You are standing where you started. Rebind the name to the child."),

    _inc("consult", "CONSULT", "if {key} in {memo}:",
         holes={"key": (EXPR, "the sub-problem being asked about"),
                "memo": (ENEMY, "the archive of paid answers")},
         skill="DP", chapter=6, family="memo", effect="consult",
         target="memo",
         note="Check the archive before you pay for the answer again.",
         cost=2, power=11, par=20.0,
         body=("__fired__[0] += 1",),
         demo={"memo": "{3: 9}", "n": "3"},
         example={"key": "n", "memo": "memo"},
         assertion="__fired__[0] == 1",
         miss="Correct question, and the archive had never heard of it."),

    _inc("enshrine", "ENSHRINE", "{memo}[{key}] = {result}",
         holes={"memo": (ENEMY, "the archive"),
                "key": (EXPR, "the sub-problem"),
                "result": (EXPR, "what it cost you to learn")},
         skill="DP", chapter=6, family="memo", effect="enshrine",
         note="File the answer the moment you have it, or you will buy it again.",
         cost=3, power=12, par=24.0, requires=("dict",),
         demo={"memo": "{}", "n": "4", "answer": "12"},
         example={"memo": "memo", "key": "n", "result": "answer"},
         snapshot={"n": "len({memo})"},
         assertion="{memo}[{key}] == ({result}) and len({memo}) >= __b__['n']"),

    _inc("expand", "EXPAND", "for {nb} in {graph}[{node}]:",
         holes={"nb": (BINDER, "the name for each neighbour"),
                "graph": (ENEMY, "the map of who knows whom"),
                "node": (EXPR, "where you are standing")},
         skill="GRAPH", chapter=7, family="graph", effect="expand",
         target="graph",
         note="Adjacency: the neighbours of a node are a list hanging off a key.",
         cost=3, power=13, par=26.0,
         body=("__fired__[0] += 1",),
         demo={"graph": "{'a': ['b', 'c']}", "node": "'a'"},
         example={"nb": "nb", "graph": "graph", "node": "node"},
         assertion="__fired__[0] == len({graph}[{node}])"),

    _inc("enqueue", "ENQUEUE", "{frontier}.append(({node}, {dist} + 1))",
         holes={"frontier": (ENEMY, "the advancing edge"),
                "node": (EXPR, "the place being scheduled"),
                "dist": (ENEMY, "how far you have come")},
         skill="BFS", chapter=7, family="queue", effect="enqueue",
         target="frontier",
         note="Carry the distance with the node. Recomputing it later is how you lose it.",
         cost=3, power=13, par=28.0, requires=("deque",),
         imports=("from collections import deque",),
         demo={"frontier": "deque()", "node": "'a'", "dist": "0"},
         example={"frontier": "frontier", "node": "node", "dist": "dist"},
         snapshot={"n": "len({frontier})"},
         assertion="len({frontier}) == __b__['n'] + 1 "
                   "and {frontier}[-1] == (({node}), ({dist}) + 1)"),

    _inc("cell", "CELL", "{value} = {grid}[{r}][{c}]",
         holes={"value": (NAME, "where the cell's contents land"),
                "grid": (ENEMY, "the plane"),
                "r": (EXPR, "the row"), "c": (EXPR, "the column")},
         skill="MATRIX", chapter=7, family="matrix", effect="cell",
         target="grid",
         note="Row first, then column. Getting that backwards is a silent bug.",
         cost=3, power=12, par=22.0,
         demo={"cur": "None", "grid": "[[1, 2], [3, 4]]", "r": "1", "c": "0"},
         example={"value": "cur", "grid": "grid", "r": "r", "c": "c"},
         assertion="{value} == {grid}[{r}][{c}]"),

    _inc("bounds", "BOUNDS",
         "if 0 <= {r} < len({grid}) and 0 <= {c} < len({grid}[0]):",
         holes={"r": (ENEMY, "the row being tested"),
                "c": (ENEMY, "the column being tested"),
                "grid": (ENEMY, "the plane you must stay inside")},
         skill="MATRIX", chapter=7, family="matrix", effect="bounds",
         target="grid",
         note="Check the edges before you read the cell. Negative indices do not fail loudly.",
         cost=4, power=15, par=34.0,
         body=("__fired__[0] += 1",),
         demo={"grid": "[[1, 2], [3, 4]]", "r": "1", "c": "1"},
         example={"r": "r", "c": "c", "grid": "grid"},
         assertion="__fired__[0] == 1",
         miss="Correctly written, and that position really is off the plane."),

    _inc("table", "TABLE", "{dp} = [0] * ({n} + 1)",
         holes={"dp": (ENEMY, "the ledger being opened"),
                "n": (EXPR, "how far it must reach")},
         skill="DP", chapter=8, family="dp", effect="table",
         note="Size it n+1 so you can index by the number itself, not by an offset.",
         cost=2, power=11, par=20.0,
         demo={"dp": "[]", "n": "4"},
         example={"dp": "dp", "n": "n"},
         assertion="len({dp}) == ({n}) + 1 and set({dp}) == {0}"),

    _inc("transition", "TRANSITION",
         "{dp}[{i}] = {dp}[{i} - 1] + {dp}[{i} - 2]",
         holes={"dp": (ENEMY, "the ledger"),
                "i": (EXPR, "the entry being paid for")},
         skill="DP", chapter=8, family="dp", effect="transition",
         note="Today's answer from yesterday's. That sentence IS dynamic programming.",
         cost=4, power=15, par=32.0,
         demo={"dp": "[1, 1, 0, 0]", "i": "2"},
         example={"dp": "dp", "i": "i"},
         snapshot={"a": "{dp}[{i} - 1]", "b": "{dp}[{i} - 2]"},
         assertion="{dp}[{i}] == __b__['a'] + __b__['b']"),

    _inc("choose", "CHOOSE",
         "{dp}[{i}] = max({dp}[{i} - 1], {dp}[{i} - 2] + {seq}[{i}])",
         holes={"dp": (ENEMY, "the ledger"),
                "i": (EXPR, "the entry being decided"),
                "seq": (ENEMY, "what taking it is worth")},
         skill="DP", chapter=8, family="dp", effect="choose",
         target="dp",
         note="Take it or leave it, and keep the better. Most DP is this shape.",
         cost=4, power=16, par=38.0,
         demo={"dp": "[1, 2, 0]", "nums": "[1, 2, 3]", "i": "2"},
         example={"dp": "dp", "i": "i", "seq": "nums"},
         snapshot={"a": "{dp}[{i} - 1]", "b": "{dp}[{i} - 2] + {seq}[{i}]"},
         assertion="{dp}[{i}] == max(__b__['a'], __b__['b'])"),

    _inc("witness", "WITNESS", "assert {fn}({arg}) == {expected}",
         holes={"fn": (NAME, "the function under suspicion"),
                "arg": (EXPR, "the input you chose"),
                "expected": (EXPR, "what it owes you")},
         skill="TESTING", chapter=9, family="testing", effect="witness",
         note="One assertion per claim. The input you pick is the test's real content.",
         cost=2, power=11, par=24.0,
         demo={"solve": "lambda v: v + 1", "case": "2", "want": "3"},
         example={"fn": "solve", "arg": "case", "expected": "want"},
         assertion="{fn}({arg}) == ({expected})",
         miss="The assertion itself failed: the function does not owe what you claimed."),
)


CATALOGUE: tuple = _FOUNDATION + _IDIOM + _SCANNING + _DEPTH
BY_ID: dict = {i.id: i for i in CATALOGUE}
FAMILIES: tuple = tuple(sorted({i.family for i in CATALOGUE}))


def get(incantation_id: str) -> Incantation | None:
    return BY_ID.get(incantation_id)


def by_chapter(chapter: int) -> list:
    """Everything unlocked at or below a chapter. Chapter gating is the ladder."""
    return [i for i in CATALOGUE if i.chapter <= chapter]


def by_skill(skill: str) -> list:
    return [i for i in CATALOGUE if i.skill == skill]


def by_family(family: str) -> list:
    return [i for i in CATALOGUE if i.family == family]


# ---------------------------------------------------------------------------
# Scaffold fade
# ---------------------------------------------------------------------------
# The support the player is given is a dial, not a switch, and the dial is moved
# by measurement rather than by mood:
#
#   tier 0  the whole line, with every hole but one already filled
#   tier 1  the whole line, every hole blank
#   tier 2  the shape only — keywords and punctuation survive, names do not
#   tier 3  the incantation's NAME, and nothing else
#
# Tier 0 hands the player answers on purpose. That is the retrieval-support
# gradient, and it is the one place in this game where support is given freely,
# because it costs nothing to a player who no longer needs it: the tier rises
# the moment the evidence says it can.

TIER_NAMES = ("GUIDED", "PROMPTED", "SHAPED", "RECALLED")
MAX_TIER = 3


def _shape(template: str) -> str:
    """Tier 2: keep the skeleton, blank every identifier including ours."""
    markers = {name: "__h%d__" % index
               for index, name in enumerate(holes_in(template))}
    source = fill(template, markers)
    inverse = {marker: BLANK for marker in markers.values()}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        # Never let a tokenizer hiccup cost the player their move.
        return fill(template, {name: BLANK for name in holes_in(template)})
    out, previous_end = [], 0
    for token in tokens:
        if token.type in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER,
                          tokenize.INDENT, tokenize.DEDENT):
            continue
        text = token.string
        if token.type == tokenize.NAME:
            if text in inverse:
                text = inverse[text]
            elif not keyword.iskeyword(text) and not keyword.issoftkeyword(text):
                text = SHAPE_BLANK
        if out and token.start[1] > previous_end:
            out.append(" ")
        out.append(text)
        previous_end = token.end[1]
    return "".join(out)


def _suggest(inc: Incantation, hole: Hole, context: BattleContext | None) -> str:
    """A tier-0 prefill for a hole the engine did not name explicitly."""
    example = inc.example.get(hole.name, "")
    if context is not None:
        if hole.kind == ENEMY:
            living = [e for e in context.living()]
            if example in [e.name for e in living]:
                return example
            if len(living) == 1:
                return living[0].name
        elif example and example in context.names():
            return example
    if hole.kind == BINDER and example:
        return example
    return "«%s»" % hole.role


def render_template(inc: Incantation | str, tier: int, *,
                    context: BattleContext | None = None,
                    answers: dict | None = None) -> dict:
    """What the player is shown before typing. Pure presentation, no grading."""
    inc = BY_ID[inc] if isinstance(inc, str) else inc
    tier = max(0, min(MAX_TIER, int(tier)))
    answers = dict(answers or {})
    editable = [h.name for h in inc.holes]
    prefilled: dict = {}

    if tier == 0:
        keep = inc.target_hole
        editable = [keep] if keep else editable
        for hole in inc.holes:
            if hole.name == keep:
                continue
            prefilled[hole.name] = answers.get(hole.name) or _suggest(inc, hole, context)
        ghost = fill(inc.template, {**prefilled, **{h: BLANK for h in editable}})
        prompt = "One blank. Name it."
    elif tier == 1:
        ghost = fill(inc.template, {})
        prompt = "The line is yours to fill."
    elif tier == 2:
        ghost = _shape(inc.template)
        prompt = "The shape is all you get. The names are yours."
    else:
        ghost = ""
        prompt = "%s. From memory." % inc.name

    return {
        "incantation": inc.id,
        "name": inc.name,
        "tier": tier,
        "tier_name": TIER_NAMES[tier],
        "ghost": ghost,
        # The client renders its own tiers from this one string; `ghost` is the
        # same line already rendered, for anything too thin to do that itself.
        "template": client_template(inc.template),
        "free_text": tier == MAX_TIER,
        "block": inc.is_block,
        "cost": inc.cost,
        "note": inc.note if tier <= 1 else "",
        "prompt": prompt,
        "holes": [
            {**hole.to_dict(),
             "editable": hole.name in editable,
             "prefilled": prefilled.get(hole.name, "")}
            for hole in inc.holes
        ],
    }


@dataclass
class CastStats:
    """Measured evidence for one incantation. This is what moves the scaffold."""
    incantation: str = ""
    casts: int = 0
    correct: int = 0
    streak: int = 0
    best_streak: int = 0
    miss_streak: int = 0
    fails: int = 0
    last_layer: str = ""
    last_cast_at: float = 0.0
    last_correct_at: float = 0.0
    seconds: list = field(default_factory=list)   # last 8 correct casts

    @property
    def median_seconds(self) -> float:
        if not self.seconds:
            return 0.0
        ordered = sorted(self.seconds)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[mid])
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def record(self, *, correct: bool, layer: str = "", seconds: float = 0.0,
               now: float | None = None) -> None:
        now = time.time() if now is None else now
        self.casts += 1
        self.last_cast_at = now
        self.last_layer = "" if correct else layer
        if correct:
            self.correct += 1
            self.streak += 1
            self.miss_streak = 0
            self.best_streak = max(self.best_streak, self.streak)
            self.last_correct_at = now
            if seconds > 0:
                self.seconds = (self.seconds + [round(seconds, 2)])[-8:]
        else:
            self.fails += 1
            self.streak = 0
            self.miss_streak += 1

    def to_dict(self) -> dict:
        data = asdict(self)
        data["median_seconds"] = self.median_seconds
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CastStats":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


def _mastery_of(skill_state) -> float:
    if skill_state is None:
        return 0.0
    if isinstance(skill_state, dict):
        return float(skill_state.get("mastery", 0.0))
    return float(getattr(skill_state, "mastery", 0.0))


def tier_for(skill_state, stats: CastStats | dict | None, *,
             now: float | None = None, par_seconds: float = 20.0) -> int:
    """Decide the scaffold tier from measured evidence, and only from that.

    It rises on accumulated correct casts that are also getting faster, and it
    is capped by the mastery of the underlying skill — fluency at typing one
    line is not the same as understanding what it is for.

    It falls immediately, and proportionately: one tier back for each miss in
    a row, so a slip costs a little help and a collapse costs all of it. No
    announcement, no penalty, no comment. Time away costs tiers too, which is
    the spacing effect showing up as a mechanic rather than as a lecture.
    """
    if stats is None:
        return 0
    if isinstance(stats, dict):
        stats = CastStats.from_dict(stats)
    if stats.casts == 0:
        return 0

    now = time.time() if now is None else now
    par = max(1.0, float(par_seconds))
    median = stats.median_seconds

    earned = 0
    if stats.correct >= 2 and stats.best_streak >= 2:
        earned = 1
    if (stats.correct >= 5 and stats.best_streak >= 4
            and (median == 0.0 or median <= par * 1.6)):
        earned = 2
    if (stats.correct >= 9 and stats.best_streak >= 6
            and median and median <= par):
        earned = 3

    # Falling back. A player who is missing gets the support back, one rung per
    # consecutive miss, before he has time to feel stranded.
    earned -= stats.miss_streak

    # Spacing: support returns as the memory ages, before the player notices.
    reference = stats.last_correct_at or stats.last_cast_at
    if reference:
        days = max(0.0, (now - reference) / 86400.0)
        if days >= 14:
            earned -= 2
        elif days >= 5:
            earned -= 1

    # Mastery ceiling: typing speed cannot outrun comprehension.
    mastery = _mastery_of(skill_state)
    ceiling = 1 if mastery < 25 else (2 if mastery < 55 else 3)
    return max(0, min(MAX_TIER, earned, ceiling))


# ---------------------------------------------------------------------------
# Layer 1: syntax
# ---------------------------------------------------------------------------

def assemble(inc: Incantation | str, answers: dict) -> str:
    """The line as the player has actually written it."""
    inc = BY_ID[inc] if isinstance(inc, str) else inc
    return fill(inc.template, answers)


def _pattern_for(inc: Incantation) -> re.Pattern:
    """A forgiving matcher that recovers hole answers from a freely typed line.

    Whitespace is irrelevant between tokens, which is the whole point: at tier 3
    the player is typing from memory and ``counts.get(k,0)+1`` must be accepted
    exactly as readily as ``counts.get(k, 0) + 1``.
    """
    parts, index = [], 0
    for match in _HOLE_RE.finditer(inc.template):
        static = inc.template[index:match.start()]
        parts.append(_loose(static))
        parts.append("(?P<%s>.+?)" % match.group(1)
                     if ("(?P<%s>" % match.group(1)) not in "".join(parts)
                     else "(?P=%s)" % match.group(1))
        index = match.end()
    parts.append(_loose(inc.template[index:]))
    return re.compile(r"^\s*" + "".join(parts) + r"\s*$")


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S")


def _loose(static: str) -> str:
    """Escape a static template fragment, allowing any whitespace between tokens.

    Split to real tokens rather than on spaces, so `.get( ch , 0 )` and
    `.get(ch,0)` are the same cast.
    """
    pieces = [re.escape(piece) for piece in _TOKEN_RE.findall(static)]
    glue = r"\s*"
    if not pieces:
        return glue if static else ""
    return glue + glue.join(pieces) + glue


def match_line(inc: Incantation | str, text: str) -> dict | None:
    """Recover per-hole answers from a whole line the player typed from memory."""
    inc = BY_ID[inc] if isinstance(inc, str) else inc
    match = _pattern_for(inc).match(text.rstrip())
    if not match:
        return None
    return {name: value.strip() for name, value in match.groupdict().items()}


def _syntax_error_line(exc: SyntaxError, line: str) -> str:
    """Say WHERE it broke, in the game's voice, without saying what goes there."""
    column = exc.offset or 0
    text = (exc.msg or "invalid syntax").rstrip(".")
    if column and 0 < column <= len(line) + 1:
        near = line[max(0, column - 1):column + 8].strip()
        if near:
            return "The line will not parse — %s, around `%s`." % (text, near)
    return "The line will not parse: %s." % text


# ---------------------------------------------------------------------------
# Layer 2: binding
# ---------------------------------------------------------------------------
# A line that parses and names something that is not there is the most useful
# wrong answer in the game. It is the timed practical mistake — confidently using an
# undefined name — and it is the one failure the player must learn to feel
# before he types, not after the traceback.

BUILTIN_NAMES = frozenset("""
abs all any bool chr dict divmod enumerate filter float format frozenset int
isinstance iter len list map max min next ord pow range repr reversed round
set setattr sorted str sum tuple type zip True False None print
""".split())
# `next` and `iter` were missing, and their absence was not a judgement — the
# set was authored before anything in the game used them. Seventeen of the
# secret arts in gauntlet/sages.py are built on `next(generator, default)`,
# which is the whole shape of "read the first thing that matches and do not
# walk the rest", and without this the checker refused a builtin by telling the
# player it was an unbound name. gauntlet/sages.REQUIRED_BUILTINS is derived
# from the templates, so if a later art needs another one it will say so.


def _bound_in(tree: ast.AST) -> set:
    """Names the line itself binds: loop targets, comprehension vars, arguments."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
    return bound


def _loads_in(tree: ast.AST) -> list:
    """Names the line READS, in source order. Duplicates kept out."""
    out, seen = [], set()

    def add(name):
        if name not in seen:
            seen.add(name)
            out.append(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            add(node.id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            # `total += 1` reads total before it writes it. Unbound is fatal.
            add(node.target.id)
    return out


def _is_identifier(text: str) -> bool:
    return bool(text) and text.isidentifier() and not keyword.iskeyword(text)


def _unbound_line(name: str, context: BattleContext) -> str:
    """The teaching line for a name that is not on the field."""
    vocabulary = context.names()
    lower = name.lower()
    for known in vocabulary:
        if known.lower() == lower and known != name:
            return ("`%s` is how it shouts its name. `%s` is how Python spells it. "
                    "Python is case-sensitive and so, from now on, are you."
                    % (name, known))
    near = [known for known in sorted(vocabulary)
            if known.startswith(name[:2]) and known != name]
    if near:
        return ("Nothing here is called `%s`. The field answers to %s."
                % (name, ", ".join("`%s`" % n for n in near[:3])))
    return ("`%s` is not bound in this battle. A name you have not defined is "
            "a NameError wearing a confident expression." % name)


def _check_hole(hole: Hole, answer: str, context: BattleContext,
                binders: set) -> str:
    """Return a teaching line, or "" when the fill is legal."""
    answer = (answer or "").strip()
    vocabulary = context.names() | binders

    if hole.kind == ENEMY:
        if not _is_identifier(answer):
            return ("%s wants a name, not an expression. Type the monster the way "
                    "Python would." % hole.role.capitalize())
        if answer not in vocabulary:
            return _unbound_line(answer, context)
        if context.enemy(answer) is None:
            return ("`%s` is bound here, but it is not what you are striking. "
                    "%s." % (answer, hole.role.capitalize()))
        enemy = context.enemy(answer)
        if not enemy.alive:
            return "%s is already down. Pick something still standing." % enemy.display
        return ""

    if hole.kind == NAME:
        if not _is_identifier(answer):
            return "%s wants a single bound name." % hole.role.capitalize()
        if answer not in vocabulary:
            return _unbound_line(answer, context)
        return ""

    if hole.kind == MEMBER:
        if not answer:
            return "%s is still blank." % hole.role.capitalize()
        if answer not in hole.allowed:
            return ("`%s` is not one of the methods that belongs in that slot."
                    % answer)
        return ""

    if hole.kind == BINDER:
        if not _is_identifier(answer):
            return ("%s is a name you invent. It has to be a legal identifier."
                    % hole.role.capitalize())
        if answer in context.names():
            return ("`%s` is already something else on this field. Shadowing it "
                    "here will cost you the variable you meant to keep." % answer)
        return ""

    if hole.kind == LITERAL:
        try:
            ast.literal_eval(answer)
        except (ValueError, SyntaxError):
            return ("%s has to be a constant — a number, a string, True, False "
                    "or None." % hole.role.capitalize())
        return ""

    # EXPR
    try:
        tree = ast.parse(answer, mode="eval")
    except SyntaxError:
        return "`%s` is not an expression Python can evaluate." % answer
    local = _bound_in(tree)
    for name in _loads_in(tree):
        if name in local or name in vocabulary or name in BUILTIN_NAMES:
            continue
        return _unbound_line(name, context)
    return ""


def check_binding(inc: Incantation, answers: dict, line: str,
                  context: BattleContext) -> tuple:
    """Layer 2. Returns (ok, teaching, offending_name)."""
    binders = {(answers.get(h.name) or "").strip()
               for h in inc.holes if h.kind == BINDER}
    binders.discard("")

    for hole in inc.holes:
        if hole.name not in answers:
            continue
        problem = _check_hole(hole, answers[hole.name], context, binders)
        if problem:
            return False, problem, (answers.get(hole.name) or "").strip()

    # Whatever the per-hole pass could not see — a line typed freehand at
    # tier 3, or a name smuggled inside an expression — is caught here.
    strict = all(h.name in answers for h in inc.holes)
    try:
        tree = ast.parse(_executable(inc, line, answers, strict))
    except SyntaxError:
        return True, "", ""      # layer 1 already had its say
    local = _bound_in(tree) | binders
    for name in _loads_in(tree):
        if name in local or name in context.names() or name in BUILTIN_NAMES:
            continue
        if name.startswith("__") and name.endswith("__"):
            continue
        return False, _unbound_line(name, context), name
    return True, "", ""


def _opens_block(inc: Incantation, line: str, strict: bool) -> bool:
    """Does this cast need something indented under it? In strict mode the
    template decides; with a freely typed line, the line itself does."""
    text = (inc.template if strict else (line or inc.template)).strip()
    return text.endswith(":")


def _body_lines(inc: Incantation, answers: dict, strict: bool,
                line: str = "") -> list:
    """What runs under a block header.

    With every hole recovered we run the body the incantation authored. With a
    freely typed line we cannot fill it, so we count one pass and leave — the
    ``break`` is what keeps a mistyped ``while`` from spinning until the
    sandbox kills it.
    """
    if strict:
        return [fill(b, answers) for b in inc.body]
    if not _opens_block(inc, line, strict):
        return []
    head = (line or inc.template).strip().split(" ", 1)[0]
    if head in ("while", "for"):
        return ["__fired__[0] += 1", "break"]
    return ["__fired__[0] += 1"]


def _executable(inc: Incantation, line: str, answers: dict,
                strict: bool = True) -> str:
    """The player's line plus whatever the template needs to be a legal statement."""
    out = [line]
    body = _body_lines(inc, answers, strict, line) or ["pass"]
    if _opens_block(inc, line, strict):
        out += ["    " + b for b in body]
    elif inc.body and strict:
        out += body
    text = "\n".join(out)
    if inc.wrap == "return":
        text = "def __inner__():\n" + "\n".join("    " + l for l in text.splitlines())
    return text + "\n"


# ---------------------------------------------------------------------------
# Layer 3: semantics
# ---------------------------------------------------------------------------
# Nothing below compares the player's text to a stored answer. The line is run
# against the real battle state in the sandbox and the incantation's own
# promise is checked afterwards. That is why formatting never matters and why a
# clever-but-equivalent fill is accepted without anyone having to anticipate it.

CAST_ENTRY = {"kind": "function", "name": "__cast__"}

# Structural marks that make one line recognisably a given incantation. Names
# and constants are deliberately excluded: those are the player's to choose.
_SHAPE_NODES = (
    ast.If, ast.While, ast.For, ast.Assign, ast.AugAssign, ast.Delete,
    ast.Return, ast.Assert, ast.ListComp, ast.SetComp, ast.DictComp,
    ast.GeneratorExp, ast.Subscript, ast.Call, ast.Attribute, ast.Slice,
    ast.Tuple, ast.comprehension,
)


def _signature(tree: ast.AST) -> set:
    """The shape of a line: its structure, its operators, its method names."""
    marks = set()
    for node in ast.walk(tree):
        if isinstance(node, _SHAPE_NODES):
            marks.add(type(node).__name__)
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp)):
            marks.add(type(node.op).__name__)
        if isinstance(node, ast.AugAssign):
            marks.add("aug" + type(node.op).__name__)
        if isinstance(node, ast.Compare):
            for op in node.ops:
                marks.add(type(op).__name__)
        if isinstance(node, ast.Attribute):
            marks.add("attr:" + node.attr)
    if "Not" in marks and "In" in marks:
        marks.add("NotIn")        # `not x in y` is `x not in y` wearing a hat
    return marks


def _shape_matches(inc: Incantation, line: str) -> bool:
    """Does a freely typed line have the bones of this incantation?

    Only consulted when the line could not be matched back onto the template.
    Without it, any statement that mutates anything would pass for any
    incantation, and tier 3 would stop meaning anything.
    """
    placeholders = {name: "__hole_%s__" % name for name in holes_in(inc.template)}
    try:
        wanted = _signature(ast.parse(_executable(inc, fill(inc.template, placeholders),
                                                  placeholders, True)))
        got = _signature(ast.parse(_executable(inc, line, {}, False)))
    except SyntaxError:
        return True               # layer 1 owns that failure, not this one
    return wanted <= got

_EXCEPTION_LINES = {
    "NameError": "It parsed, and then it reached for something that does not exist.",
    "KeyError": "That key was not in there. Reading a missing key raises; "
                "asking with .get does not.",
    "IndexError": "That index is off the end. The last valid one is len minus one.",
    "TypeError": "The types do not agree. Check what each of those names actually is.",
    "AttributeError": "That object has no such method. You may be holding a "
                      "different structure than you think.",
    "ValueError": "The value was the wrong shape for that operation.",
    "ZeroDivisionError": "Something divided by a count that was still zero.",
    "AssertionError": "The assertion failed. The claim you made is not true of "
                      "that function.",
    "RecursionError": "It called itself forever. The base case never caught it.",
    "Timeout": "The line never finished. Something in that loop has to move "
               "toward the exit.",
}


def build_cast_source(inc: Incantation, answers: dict, context: BattleContext,
                      *, line: str = "", strict: bool = True) -> str:
    """The program handed to the sandbox: battle state, the cast, then the proof.

    ``strict`` is False when the player typed the whole line from memory and it
    could not be matched back onto the template. The incantation's own promise
    cannot be stated without knowing which name went in which hole, so the proof
    weakens to the one claim that still holds: a spell has to CHANGE something.
    """
    answers = dict(answers)
    line = line or fill(inc.template, answers)
    imports = list(context.imports)
    for statement in inc.imports:
        if statement not in imports:
            imports.append(statement)

    out = ["import copy"] + imports + ["", "def __cast__():"]
    for setup in context.setup_lines():
        out.append("    " + setup)
    out.append("    __fired__ = [0]")
    out.append("    __b__ = {}")
    watched = "{%s}" % ", ".join("%r: %s" % (name, name)
                                 for name in sorted(context.bindings()))
    if strict:
        for key in sorted(inc.snapshot):
            out.append("    __b__[%r] = copy.deepcopy(%s)"
                       % (key, fill(inc.snapshot[key], answers)))
    else:
        out.append("    __b__['__state__'] = {k: repr(v) for k, v in %s.items()}"
                   % watched)

    body = _body_lines(inc, answers, strict, line)
    indent = "    "
    if inc.wrap == "return":
        out.append("    def __inner__():")
        for extra in inc.inner:
            out.append("        " + fill(extra, answers))
        indent = "        "
    out.append(indent + line)
    if _opens_block(inc, line, strict):
        for statement in (body or ["pass"]):
            out.append(indent + "    " + statement)
    else:
        for statement in body:
            out.append(indent + statement)
    if inc.wrap == "return":
        out.append("        return None")
        out.append("    __r__ = __inner__()")
    if strict:
        proof = fill(inc.assertion, answers)
    else:
        proof = ("__fired__[0] > 0 or any(repr(v) != __b__['__state__'][k] "
                 "for k, v in %s.items())" % watched)
    out.append("    __ok__ = bool(%s)" % proof)
    out.append("    return 'OK' if __ok__ else 'NO_EFFECT'")
    return "\n".join(out) + "\n"


def check_semantics(inc: Incantation, answers: dict, line: str,
                    context: BattleContext, *, strict: bool = True) -> tuple:
    """Layer 3. Returns (ok, teaching, detail). Executes in the sandbox, always."""
    if not strict and not _shape_matches(inc, line):
        return (False,
                "That line does something, but it is not %s. Cast the shape the "
                "name asks for." % inc.name,
                "shape")
    source = build_cast_source(inc, answers, context, line=line, strict=strict)
    report = sandbox.run_tests(
        source, CAST_ENTRY,
        [{"name": inc.id, "args": [], "expected": "OK", "hidden": False}],
        # A cast is one line. If it has not finished in a second and a half it
        # is not slow, it is a loop with no way out.
        timeout_ms=1500, wall_seconds=6,
    )

    if report.phase == "syntax":
        detail = (report.error or {}).get("message", "invalid syntax")
        return False, "The line will not parse: %s." % detail, detail
    if not report.tests:
        error = report.error or {}
        kind = error.get("type", "ExecutionAborted")
        teaching = _EXCEPTION_LINES.get(kind, "It did not survive being run.")
        return False, teaching, error.get("message", "")

    result = report.tests[0]
    if result.passed:
        return True, "", ""
    if result.status == "timeout":
        return False, _EXCEPTION_LINES["Timeout"], result.message
    if result.status == "exception":
        kind = result.message.split(":", 1)[0].strip()
        teaching = _EXCEPTION_LINES.get(kind, "It ran, and then it broke.")
        return False, teaching, result.message
    miss = inc.miss or ("It parsed, it ran, and the battlefield is exactly as it "
                        "was. A line that changes nothing is not a spell.")
    return False, miss, result.message


# ---------------------------------------------------------------------------
# Complexity: the spine of the damage
# ---------------------------------------------------------------------------
# THE ONE RULE THIS SECTION EXISTS TO ENFORCE: damage follows the complexity of
# the Python the player actually wrote, and nothing else is allowed to be the
# spine. Not a number attached to the move, not the level of the character, not
# the rarity of the staff. Harder Python hits harder. That is the only incentive
# this game is permitted to offer, because it is the only one that points at the
# thing the player came here to learn.
#
# `Incantation.power` survives, demoted to a FLOOR (see POWER_FLOOR_SHARE). It
# guarantees a correct cast is never worthless; it no longer decides anything.
#
# The measure has five ingredients and every one of them is read off the text:
#
#   1. CONSTRUCTS   What Python is in the line, by kind. A subscript costs
#                   more than a name, a comprehension costs more than a loop,
#                   a lambda costs more than either. COMPLEXITY_POINTS is the
#                   table and it is the whole opinion of this module.
#   2. AUTHORSHIP   Who typed it. A hole the scaffold pre-filled is not the
#                   player's work; the skeleton at tier 0 is a printed line the
#                   player read. SKELETON_CREDIT is the dial, and it means the
#                   scaffold fade and the damage curve are THE SAME CURVE: as
#                   the game stops helping, the same cast starts hitting harder,
#                   without a single extra rule to explain.
#   3. NESTING      How deep the player's own expressions go. `counts[k]` is
#                   one level; `counts[nums[i]]` is two; the second is harder to
#                   hold in your head and it pays for that.
#   4. FORM         Comprehension or loop. A comprehension that does the work of
#                   a loop scores higher, on purpose and not as a matter of
#                   taste: it is the form that composes, the form an examiner
#                   reads faster, and the form a player will not reach for
#                   unless something pays them to.
#   5. COMPOSITION  Two different ideas in one expression — a lookup inside an
#                   arithmetic, a predicate inside a comprehension. Composing is
#                   the step between knowing idioms and writing Python, so it is
#                   the one flat bonus in the table.
#
# What is deliberately NOT measured: length, cleverness, obscurity, or line
# count. `counts.get(k, 0) + 1` and `counts.get(k,0)+1` score identically,
# because they are the same Python and the sandbox already proved it.

# Points per construct. Tuned against one anchor: bestiary.BASE_DAMAGE is 10,
# which is what every encounter budget in the game was written around. With
# DAMAGE_UNIT at 11.0 the MEASURED median of an ordinary cast at tier 1, taken
# over all sixty-six incantations casting their own worked examples, is exactly
# 10. That is not a coincidence, it is the calibration, and
# self_check_complexity() fails if it drifts outside 9.0 to 11.5.
#
# The range either side of that median is the whole point: 7 at the bottom for
# `i += 1` with the answer on screen, 29 at the top for a filtered comprehension
# typed from memory. Four times the damage for writing better Python, in the
# same game, on the same turn.
COMPLEXITY_POINTS = {
    # statements — the shape of the line
    "assign": 1, "augassign": 2, "branch": 4, "loop": 5, "delete": 2,
    "assert": 4, "return": 2, "function": 4,
    # expressions — the substance of it
    "call": 3, "keyword": 2, "attribute": 2, "subscript": 3, "slice": 4,
    "arith": 2, "unary": 1, "compare": 3, "chained_compare": 4, "logic": 4,
    "comprehension": 9, "comp_filter": 5, "nested_comprehension": 7,
    "generator": 8, "lambda": 6, "conditional": 5, "walrus": 6,
    "literal_structure": 2, "fstring": 3, "unpack": 4,
}

# Constructs grouped into IDEAS. Two ideas in one authored expression is what
# `composed` means; five calls in a row is one idea five times.
COMPLEXITY_FAMILY = {
    "call": "invocation", "keyword": "invocation", "attribute": "invocation",
    "subscript": "indexing", "slice": "indexing",
    "arith": "arithmetic", "unary": "arithmetic",
    "compare": "predicate", "chained_compare": "predicate", "logic": "predicate",
    "comprehension": "comprehension", "comp_filter": "comprehension",
    "nested_comprehension": "comprehension", "generator": "comprehension",
    "lambda": "abstraction", "conditional": "abstraction", "walrus": "abstraction",
    "literal_structure": "construction", "fstring": "construction",
    "unpack": "construction",
}

# What producing a hole is worth before anything inside it is counted. A BINDER
# is the dearest of the cheap ones because the player invented that name rather
# than reading it off a monster.
RETRIEVAL_POINTS = {ENEMY: 1, NAME: 1, MEMBER: 2, LITERAL: 1, EXPR: 2, BINDER: 2}

# How much of the printed skeleton counts as the player's work, by tier. At tier
# 0 the line is on the screen with one blank in it and the player is being shown
# Python, not writing it. At tier 3 there is nothing on the screen at all.
SKELETON_CREDIT = (0.30, 0.45, 0.75, 1.00)

DEPTH_POINTS = 2          # per level of authored nesting past the first
DEPTH_CAP = 4             # beyond four levels it is not depth, it is a mess
COMPOSITION_POINTS = 6    # two ideas in one expression, once

SCORE_FULL = 40.0         # raw points that read as a score of 100
WEIGHT_MIN = 0.55         # `i += 1` with the answer already on screen
WEIGHT_MAX = 3.00         # a composed, filtered comprehension typed from memory

DAMAGE_UNIT = 11.0        # damage per unit of weight — the calibration constant
POWER_FLOOR_SHARE = 0.45  # Incantation.power's remaining job: a floor, not a spine


@dataclass(frozen=True)
class Complexity:
    """How much Python one cast actually demanded. Pure measurement."""
    score: int = 0                # 0-100, for the player and the UI
    weight: float = WEIGHT_MIN    # the damage multiplier the score becomes
    raw: float = 0.0              # unnormalised points, for tuning
    authored: float = 0.0         # points the player typed
    skeleton: float = 0.0         # points the scaffold printed, after credit
    holes_filled: int = 0
    depth: int = 0
    form: str = "atom"            # atom | call | branch | loop | comprehension
    composed: bool = False
    constructs: tuple = ()        # (name, count) pairs, sorted
    families: tuple = ()          # the authored ideas, sorted
    notes: tuple = ()             # short player-facing lines, never the answer

    def to_dict(self) -> dict:
        data = asdict(self)
        data["constructs"] = [list(pair) for pair in self.constructs]
        data["families"] = list(self.families)
        data["notes"] = list(self.notes)
        return data


_NESTING_NODES = (
    ast.Call, ast.Subscript, ast.Attribute, ast.BinOp, ast.BoolOp, ast.Compare,
    ast.UnaryOp, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.Lambda, ast.IfExp, ast.Slice,
)


def _constructs_of(node) -> list:
    """The construct names one AST node contributes. Data, not judgement."""
    names = []
    if isinstance(node, ast.Assign):
        names.append("assign")
    elif isinstance(node, ast.AugAssign):
        names.append("augassign")
    elif isinstance(node, (ast.If, ast.IfExp)):
        names.append("branch" if isinstance(node, ast.If) else "conditional")
    elif isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
        names.append("loop")
    elif isinstance(node, ast.Delete):
        names.append("delete")
    elif isinstance(node, ast.Assert):
        names.append("assert")
    elif isinstance(node, ast.Return):
        names.append("return")
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.append("function")
    elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
        names.append("comprehension")
        names += ["nested_comprehension"] * max(0, len(node.generators) - 1)
        names += ["comp_filter"] * sum(len(g.ifs) for g in node.generators)
    elif isinstance(node, ast.GeneratorExp):
        names.append("generator")
        names += ["comp_filter"] * sum(len(g.ifs) for g in node.generators)
    elif isinstance(node, ast.Lambda):
        names.append("lambda")
    elif isinstance(node, ast.NamedExpr):
        names.append("walrus")
    elif isinstance(node, ast.Call):
        names.append("call")
        names += ["keyword"] * len(node.keywords)
    elif isinstance(node, ast.Attribute):
        names.append("attribute")
    elif isinstance(node, ast.Subscript):
        names.append("subscript")
    elif isinstance(node, ast.Slice):
        names.append("slice")
    elif isinstance(node, ast.BinOp):
        names.append("arith")
    elif isinstance(node, ast.UnaryOp):
        names.append("unary")
    elif isinstance(node, ast.BoolOp):
        names.append("logic")
    elif isinstance(node, ast.Compare):
        names.append("chained_compare" if len(node.ops) > 1 else "compare")
    elif isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict)):
        names.append("literal_structure")
    elif isinstance(node, ast.JoinedStr):
        names.append("fstring")
    elif isinstance(node, ast.Starred):
        names.append("unpack")
    return names


def _measure_tree(node, depth: int = 0) -> tuple:
    """(points, counts, deepest). Recursive so nesting can actually be seen."""
    points = 0.0
    counts: dict = {}
    for name in _constructs_of(node):
        points += COMPLEXITY_POINTS.get(name, 0)
        counts[name] = counts.get(name, 0) + 1
    deepest = depth
    child_depth = depth + (1 if isinstance(node, _NESTING_NODES) else 0)
    for child in ast.iter_child_nodes(node):
        sub_points, sub_counts, sub_depth = _measure_tree(child, child_depth)
        points += sub_points
        for name, count in sub_counts.items():
            counts[name] = counts.get(name, 0) + count
        deepest = max(deepest, sub_depth)
    return points, counts, deepest


def _measure_source(source: str) -> tuple:
    """Measure a whole statement. A fragment that will not parse scores zero."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return 0.0, {}, 0
    return _measure_tree(tree)


def _measure_fragment(text: str) -> tuple:
    """Measure one hole's answer, which is an expression and not a statement."""
    text = (text or "").strip()
    if not text:
        return 0.0, {}, 0
    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return 0.0, {}, 0
    return _measure_tree(tree)


def authored_holes(inc: Incantation, tier: int) -> tuple:
    """Which holes the player typed at this tier. Mirrors render_template."""
    if int(tier) <= 0:
        keep = inc.target_hole
        return (keep,) if keep else inc.hole_names
    return inc.hole_names


def _form_of(counts: dict) -> str:
    if counts.get("comprehension") or counts.get("generator"):
        return "comprehension"
    if counts.get("loop"):
        return "loop"
    if counts.get("branch"):
        return "branch"
    if counts.get("call") or counts.get("subscript"):
        return "call"
    return "atom"


def measure_complexity(inc: Incantation | str, answers: dict | None, *,
                       line: str = "", tier: int = 1,
                       strict: bool = True) -> Complexity:
    """How much Python this cast demanded, read off the cast and the template.

    ``answers`` is the hole -> text mapping; ``line`` is the assembled line.
    ``strict`` False means the player typed freely and nothing could be matched
    back onto the template — in which case the whole line is theirs, at full
    credit, which is the honest reading of what just happened.

    Pure and side-effect free: call it on a line you are only thinking about.
    """
    inc = BY_ID[inc] if isinstance(inc, str) else inc
    tier = max(0, min(MAX_TIER, int(tier)))
    answers = dict(answers or {})
    line = line or fill(inc.template, answers)
    notes: list = []

    if not strict or not answers:
        # Everything on screen was blank; everything in the line is the player's.
        points, counts, depth = _measure_source(_executable(inc, line, {}, False))
        authored, skeleton = points, 0.0
        families = {COMPLEXITY_FAMILY[name] for name in counts
                    if name in COMPLEXITY_FAMILY}
        filled = 0
        notes.append("typed from memory")
    else:
        placeholders = {name: "_h%d" % index
                        for index, name in enumerate(inc.hole_names)}
        skeleton_points, counts, _ = _measure_source(
            _executable(inc, fill(inc.template, placeholders), placeholders, True))
        skeleton = skeleton_points * SKELETON_CREDIT[tier]

        typed = authored_holes(inc, tier)
        authored = 0.0
        depth = 0
        families = set()
        filled = 0
        for hole in inc.holes:
            if hole.name not in typed:
                continue
            text = (answers.get(hole.name) or "").strip()
            if not text:
                continue
            filled += 1
            authored += RETRIEVAL_POINTS.get(hole.kind, 1)
            sub_points, sub_counts, sub_depth = _measure_fragment(text)
            authored += sub_points
            depth = max(depth, sub_depth)
            for name, count in sub_counts.items():
                counts[name] = counts.get(name, 0) + count
                if name in COMPLEXITY_FAMILY:
                    families.add(COMPLEXITY_FAMILY[name])

    form = _form_of(counts)
    composed = len(families) >= 2
    raw = authored + skeleton
    if depth > 1:
        bonus = DEPTH_POINTS * min(DEPTH_CAP, depth - 1)
        raw += bonus
        notes.append("nested %d deep" % depth)
    if composed:
        raw += COMPOSITION_POINTS
        notes.append("composed %s and %s" % tuple(sorted(families)[:2]))
    if form == "comprehension":
        notes.append("comprehension, not a loop")
    elif form == "loop":
        notes.append("a loop; a comprehension would score higher")

    score = int(round(max(0.0, min(100.0, raw * 100.0 / SCORE_FULL))))
    weight = WEIGHT_MIN + (WEIGHT_MAX - WEIGHT_MIN) * (score / 100.0)
    return Complexity(
        score=score, weight=round(weight, 3), raw=round(raw, 2),
        authored=round(authored, 2), skeleton=round(skeleton, 2),
        holes_filled=filled, depth=depth, form=form, composed=composed,
        constructs=tuple(sorted(counts.items())),
        families=tuple(sorted(families)), notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# The cast
# ---------------------------------------------------------------------------

@dataclass
class CastResult:
    """One turn's worth of consequence."""
    incantation: str
    correct: bool
    layer: str = ""              # "" | blank | syntax | binding | semantics
    line: str = ""
    teaching: str = ""
    detail: str = ""
    damage: int = 0
    target: str = ""
    weakness: bool = False
    resisted: bool = False
    effect: str = ""
    defeated: bool = False
    turn_wasted: bool = False
    tier: int = 1
    seconds: float = 0.0
    cost: int = 0
    skill_deltas: dict = field(default_factory=dict)
    teaching_withheld: bool = False   # True in timed practical: measured, not taught
    # What the typing was worth, and why. `complexity` is the whole measurement
    # so a client can show the player which part of their line paid.
    complexity: dict = field(default_factory=dict)
    complexity_score: int = 0
    weight: float = 0.0
    scale: float = 1.0                # what the caller multiplied it by

    def to_dict(self) -> dict:
        return asdict(self)


# What a failure costs. Never more than the turn: the numbers below are small on
# purpose, because the wasted turn is the punishment and a second punishment
# would just teach the player to stop casting.
_FAIL_DELTA = {"blank": 0.0, "syntax": -0.4, "binding": -0.9, "semantics": -1.2}

_LAYER_DEFAULT = {
    "blank": "There are blanks left. An unfinished line is not a cast.",
    "syntax": "The line will not parse.",
    "binding": "That name is not on this field.",
    "semantics": "It ran, and nothing moved.",
}


def _damage_for(inc: Incantation, enemy: Enemy | None, tier: int, streak: int,
                seconds: float, timed: bool, complexity: Complexity | None = None,
                scale: float = 1.0) -> tuple:
    """Damage, and whether it struck a weakness or was shrugged off.

    The spine is `complexity.weight` — what the player actually wrote. There is
    no longer a tier term here: the tier already moved the weight, through
    SKELETON_CREDIT, so applying it twice would pay for the same fact twice.

    `inc.power` is now a floor and only a floor. A correct cast of a simple line
    is never worthless, but authoring a big number on a move can no longer make
    that move hit hard. If you want to hit hard, write better Python.

    `scale` is the caller's business — moveset rank falloff, groove, class
    affinity — folded in multiplicatively and last, so nothing outside this
    module can invert the incentive: doubling `scale` doubles a bad cast and a
    good one alike, and the good one was already worth more.
    """
    weight = complexity.weight if complexity is not None else WEIGHT_MIN
    amount = max(DAMAGE_UNIT * weight, float(inc.power) * POWER_FLOOR_SHARE)
    amount *= 1.0 + min(0.5, 0.05 * max(0, streak))      # fluency compounds
    weakness = bool(enemy and enemy.weakness and enemy.weakness == inc.family)
    resisted = bool(enemy and inc.family in (enemy.resists or ()))
    if weakness:
        amount *= 2.0
    if resisted:
        amount *= 0.5
    if timed and seconds and seconds <= inc.par_seconds:
        amount *= 1.15
    amount *= max(0.0, float(scale))
    return max(1, int(round(amount))), weakness, resisted


def _deltas_for(inc: Incantation, correct: bool, layer: str, tier: int,
                complexity: Complexity | None = None) -> dict:
    """What one cast is worth to mastery.

    Mastery follows the same spine damage does, for the same reason: the player
    who wrote the harder line learned more, and pretending otherwise would mean
    the number on the health bar and the number on the skill disagree about what
    just happened. The floor is 2.0, so a plain correct cast always moves it.
    """
    if correct:
        score = complexity.score if complexity is not None else 0
        deltas = {inc.skill: round(2.0 + 1.8 * (score / 100.0), 2)}
        if inc.skill != "PYTHON":
            deltas["PYTHON"] = 0.6
        if tier >= 2:
            deltas["RECALL"] = round(0.5 * (tier - 1), 2)
        return deltas
    penalty = _FAIL_DELTA.get(layer, -0.5)
    if not penalty:
        return {}
    deltas = {inc.skill: penalty}
    if layer == "binding":
        # Naming something that is not there is a Python fluency problem before
        # it is a pattern problem, and it is graded as one.
        deltas["PYTHON"] = -0.4
    return deltas


def cast(incantation_id: str, answers, context: BattleContext, *,
         tier: int = 1, seconds: float = 0.0, streak: int = 0,
         timed: bool = False, apply: bool = True, scale: float = 1.0,
         target: str = "") -> CastResult:
    """Resolve one typed attack through all three layers, in order.

    ``answers`` is either a hole -> text mapping (tiers 0-2) or the whole line as
    a string (tier 3, typed from memory). A string is matched back onto the
    template so the per-hole teaching still works. A line too far from the
    template to be matched is still accepted if it has the incantation's bones
    and really does change the field — an equivalent phrasing is a cast, and a
    different spell wearing the right name is not.

    A wrong cast WASTES THE TURN. It returns damage 0, ``turn_wasted`` True and
    a line explaining what went wrong, which is never the answer.

    ``scale`` is a multiplier the caller owns — movesets.py sends rank falloff,
    groove and class affinity through it. ``target`` names the enemy to strike
    when the incantation has no ENEMY hole to read one off, which is how an AoE
    move points the same line at a second monster without inventing a template.
    """
    inc = BY_ID.get(incantation_id)
    if inc is None:
        return CastResult(incantation=incantation_id, correct=False, layer="syntax",
                          teaching="No such incantation is known.", turn_wasted=True)

    teaching_allowed = context.mode != "interview"

    if isinstance(answers, str):
        typed = answers.strip()
        recovered = match_line(inc, typed)
        answers = recovered if recovered is not None else {}
        line = typed
    else:
        answers = {k: (v or "").strip() for k, v in dict(answers).items()}
        missing = [h.name for h in inc.holes if not answers.get(h.name)]
        if missing:
            return _fail(inc, "blank", _LAYER_DEFAULT["blank"], "", tier, seconds,
                         teaching_allowed, detail=", ".join(missing))
        line = assemble(inc, answers)

    if not line.strip():
        return _fail(inc, "blank", _LAYER_DEFAULT["blank"], line, tier, seconds,
                     teaching_allowed)

    strict = bool(inc.holes) and all(h.name in answers for h in inc.holes)

    # 1. syntax
    try:
        ast.parse(_executable(inc, line, answers, strict))
    except SyntaxError as exc:
        return _fail(inc, "syntax", _syntax_error_line(exc, line), line, tier,
                     seconds, teaching_allowed, detail=str(exc.msg))

    # 2. binding
    ok, teaching, offender = check_binding(inc, answers, line, context)
    if not ok:
        return _fail(inc, "binding", teaching, line, tier, seconds,
                     teaching_allowed, detail=offender)

    # 3. semantics
    ok, teaching, detail = check_semantics(inc, answers, line, context,
                                           strict=strict)
    if not ok:
        return _fail(inc, "semantics", teaching, line, tier, seconds,
                     teaching_allowed, detail=detail)

    target_name = answers.get(inc.target_hole, "") or target
    enemy = context.enemy(target_name)
    if enemy is None:
        for hole in inc.holes:
            if hole.kind == ENEMY:
                enemy = context.enemy(answers.get(hole.name, "")) or enemy
    if enemy is None or not enemy.alive:
        # Incantations with no enemy hole — STRIKE, WITNESS — still have to land
        # somewhere, or a correct cast would be indistinguishable from a wasted turn.
        living = context.living()
        enemy = living[0] if living else None
    measured = measure_complexity(inc, answers, line=line, tier=tier,
                                  strict=strict)
    damage, weakness, resisted = _damage_for(inc, enemy, tier, streak, seconds,
                                             timed, complexity=measured,
                                             scale=scale)
    defeated = False
    if enemy is not None and apply:
        enemy.hp = max(0, enemy.hp - damage)
        defeated = not enemy.alive

    return CastResult(
        incantation=inc.id, correct=True, layer="", line=line,
        teaching="" if not teaching_allowed else inc.note,
        damage=damage, target=(enemy.name if enemy else ""),
        weakness=weakness, resisted=resisted,
        effect=(inc.effect + "_true") if weakness else inc.effect,
        defeated=defeated, turn_wasted=False, tier=tier, seconds=round(seconds, 2),
        cost=inc.cost,
        skill_deltas=_deltas_for(inc, True, "", tier, complexity=measured),
        teaching_withheld=not teaching_allowed,
        # In a measured run the SCORE still comes back — it is what the cast was
        # worth and the health bar is about to show it anyway — but the notes do
        # not. "a loop; a comprehension would score higher" is coaching, and
        # Timed Practical Mode does not coach.
        complexity=(measured.to_dict() if teaching_allowed
                    else {**measured.to_dict(), "notes": []}),
        complexity_score=measured.score,
        weight=measured.weight, scale=round(float(scale), 3),
    )


def _fail(inc: Incantation, layer: str, teaching: str, line: str, tier: int,
          seconds: float, teaching_allowed: bool, detail: str = "") -> CastResult:
    """Every failure path lands here, so every failure costs exactly one turn."""
    return CastResult(
        incantation=inc.id, correct=False, layer=layer, line=line,
        teaching=teaching if teaching_allowed
        else "Rejected at %s. No notes until the run is over." % layer,
        detail=detail if teaching_allowed else "",
        damage=0, effect="fizzle", turn_wasted=True, tier=tier,
        seconds=round(seconds, 2), cost=inc.cost,
        skill_deltas=_deltas_for(inc, False, layer, tier),
        teaching_withheld=not teaching_allowed,
    )


# ---------------------------------------------------------------------------
# The moveset
# ---------------------------------------------------------------------------
# Incantations are LEARNED by clearing content that uses them. Nothing here is
# bought, found in a chest or handed over by an item, because an idiom you did
# not earn is an idiom you cannot recall under pressure.
#
# The equipped list is deliberately small. Four slots at the start, eight at the
# end. A limited moveset forces the player to choose, and choosing is what makes
# him notice which idiom belongs to which shape of problem.

STARTING_MOVES = ("bind", "advance", "guard", "mark")
START_SLOTS = 4
MAX_SLOTS = 8
SLOT_EVERY_LEVELS = 5


def slots_for(level: int) -> int:
    """Four slots at level 1, one more every five levels, eight at the ceiling."""
    return min(MAX_SLOTS, START_SLOTS + max(0, (int(level) - 1) // SLOT_EVERY_LEVELS))


def new_moveset() -> dict:
    """The starting book: assignment, a counter, a guard and a mark."""
    return {
        "known": list(STARTING_MOVES),
        "equipped": list(STARTING_MOVES),
        "slots": START_SLOTS,
        "stats": {},
        # The two numbers that are about CASTING rather than about one line.
        #
        # `stats` is per-incantation and cannot answer "twelve casts in a row
        # that parsed and named real things", because a player who alternates
        # two lines has a best_streak of one on each and a clean run of twelve.
        # Nothing else in the save could answer it either, so `record_cast`
        # folds it in here, next to the evidence it is derived from, rather
        # than in a counter some call site has to remember to increment.
        #
        # `recalled` is casts made at the top scaffold tier — the whole line
        # typed from memory, no ghost. It is the only evidence in this file
        # that separates fluency from familiarity.
        "clean_streak": 0,
        "best_clean_streak": 0,
        "recalled_casts": 0,
    }


def known(moveset: dict) -> list:
    return [BY_ID[i] for i in moveset.get("known", []) if i in BY_ID]


def equipped(moveset: dict) -> list:
    return [BY_ID[i] for i in moveset.get("equipped", []) if i in BY_ID]


def is_known(moveset: dict, incantation_id: str) -> bool:
    return incantation_id in moveset.get("known", [])


def equip(moveset: dict, incantation_id: str) -> tuple:
    """Returns (ok, message). Messages are shown to the player verbatim."""
    if incantation_id not in BY_ID:
        return False, "No such incantation."
    if not is_known(moveset, incantation_id):
        return False, "You have not learned %s yet." % BY_ID[incantation_id].name
    slots = int(moveset.get("slots", START_SLOTS))
    current = moveset.setdefault("equipped", [])
    if incantation_id in current:
        return False, "%s is already equipped." % BY_ID[incantation_id].name
    if len(current) >= slots:
        return False, ("Your book holds %d. Something has to come out first."
                       % slots)
    current.append(incantation_id)
    return True, "%s equipped." % BY_ID[incantation_id].name


def unequip(moveset: dict, incantation_id: str) -> tuple:
    current = moveset.setdefault("equipped", [])
    if incantation_id not in current:
        return False, "That one is not equipped."
    if len(current) <= 1:
        return False, "Walking in with an empty book is not bravery."
    current.remove(incantation_id)
    return True, "%s set aside." % BY_ID[incantation_id].name


def grow_slots(moveset: dict, level: int) -> int:
    """Called on level-up. Returns how many slots were gained."""
    before = int(moveset.get("slots", START_SLOTS))
    after = max(before, slots_for(level))
    moveset["slots"] = after
    return after - before


def learn(moveset: dict, incantation_id: str) -> bool:
    """Add one incantation to the book, auto-equipping while there is room."""
    if incantation_id not in BY_ID or is_known(moveset, incantation_id):
        return False
    moveset.setdefault("known", []).append(incantation_id)
    if len(moveset.setdefault("equipped", [])) < int(moveset.get("slots", START_SLOTS)):
        moveset["equipped"].append(incantation_id)
    return True


def learnable(moveset: dict, *, skill: str = "", chapter: int = 0) -> list:
    """What this player could learn next: unlearned, in an open chapter."""
    out = [i for i in CATALOGUE
           if i.chapter <= chapter and not is_known(moveset, i.id)
           and (not skill or i.skill == skill)]
    return sorted(out, key=lambda i: (i.chapter, i.power, i.id))


def learn_from_clear(moveset: dict, *, skill: str = "", chapter: int = 0) -> list:
    """Clearing content teaches the idiom that content is made of.

    One at a time, cheapest first, and only from a chapter that is already open.
    A single clear never dumps five new lines on someone who has just proved he
    can write one.
    """
    candidates = learnable(moveset, skill=skill, chapter=chapter)
    if not candidates and skill:
        candidates = learnable(moveset, chapter=chapter)
    if not candidates:
        return []
    chosen = candidates[0]
    return [chosen.id] if learn(moveset, chosen.id) else []


# -- per-incantation evidence ----------------------------------------------

def stats_for(moveset: dict, incantation_id: str) -> CastStats:
    raw = moveset.setdefault("stats", {}).get(incantation_id)
    stats = CastStats.from_dict(raw or {})
    stats.incantation = incantation_id
    return stats


def record_cast(moveset: dict, result: CastResult, *,
                seconds: float = 0.0, now: float | None = None,
                tier: int | None = None) -> CastStats:
    """Fold one resolved cast into the evidence the scaffold is driven by.

    `tier` is the scaffold tier the line was cast AT. It is optional because
    the per-incantation statistics below do not need it; it is accepted because
    the book-wide `recalled_casts` counter does, and asking the caller for a
    number it already holds is cheaper than recomputing the tier here from the
    stats this call is in the middle of changing.
    """
    stats = stats_for(moveset, result.incantation)
    stats.record(correct=result.correct, layer=result.layer,
                 seconds=seconds or result.seconds, now=now)
    moveset.setdefault("stats", {})[result.incantation] = stats.to_dict()

    # The book-wide counters. A clean cast is one that PARSED AND NAMED REAL
    # THINGS — `result.correct` is exactly that verdict and nothing softer —
    # and a miss puts the run back to zero, which is what makes the number mean
    # anything.
    if result.correct:
        streak = int(moveset.get("clean_streak", 0)) + 1
        moveset["clean_streak"] = streak
        moveset["best_clean_streak"] = max(
            int(moveset.get("best_clean_streak", 0)), streak)
        if tier is not None and int(tier) >= len(TIER_NAMES) - 1:
            moveset["recalled_casts"] = int(moveset.get("recalled_casts", 0)) + 1
    else:
        moveset["clean_streak"] = 0
    return stats


def tier_for_move(moveset: dict, incantation_id: str, skills: dict | None = None,
                  *, now: float | None = None) -> int:
    """The scaffold tier this player has currently earned on this incantation."""
    inc = BY_ID.get(incantation_id)
    if inc is None:
        return 0
    skill_state = (skills or {}).get(inc.skill)
    return tier_for(skill_state, stats_for(moveset, incantation_id), now=now,
                    par_seconds=inc.par_seconds)


# -- what an encounter may demand ------------------------------------------

def castable(inc: Incantation, context: BattleContext) -> bool:
    """Can this incantation legally be demanded against this field?"""
    living = context.living()
    if not living:
        return False
    if inc.requires and not set(inc.requires) <= context.kinds():
        return False
    # A hole that wants a plain bound name needs somewhere to put its result
    # that is not one of the monsters.
    if any(h.kind == NAME for h in inc.holes) and not context.support:
        return False
    return True


def demandable(moveset: dict, context: BattleContext, *, chapter: int = 99) -> list:
    """The incantations this encounter is allowed to ask for.

    Equipped, learned, inside an open chapter, and actually castable against the
    monsters standing there. An encounter that demands something the player
    cannot cast is not difficulty, it is a bug.
    """
    return [i for i in equipped(moveset)
            if i.chapter <= chapter and castable(i, context)]


def plan_battle(moveset: dict, context: BattleContext, *, chapter: int = 99,
                turns: int = 12, rng=None) -> list:
    """Order the demands for one long fight.

    This is the PREVIEW of a fight — the shape of it, for the client to show.
    Turn by turn the engine should use next_demand(), which sees the corpses.

    Two rules, both from the learning evidence rather than from taste:
    INTERLEAVING — never demand the same incantation twice in a row while
    another is available, because discriminating between them is the skill.
    REPETITION — cycle back to each of them several times inside the fight,
    because fluency is built by casting the same line again after having had to
    think about something else. Retention is the SRS's job; this is fluency.
    """
    pool = demandable(moveset, context, chapter=chapter)
    if not pool:
        return []
    if rng is not None:
        pool = list(pool)
        rng.shuffle(pool)
    plan, previous = [], None
    index = 0
    while len(plan) < max(1, turns):
        choice = pool[index % len(pool)]
        if choice.id == previous and len(pool) > 1:
            index += 1
            choice = pool[index % len(pool)]
        hits_enemy = any(h.kind == ENEMY for h in choice.holes)
        targets = [e.name for e in context.living()] if hits_enemy else []
        plan.append({
            "incantation": choice.id,
            "name": choice.name,
            "suggested_target": targets[len(plan) % len(targets)] if targets else "",
        })
        previous = choice.id
        index += 1
    return plan


def next_demand(moveset: dict, context: BattleContext, *, chapter: int = 99,
                avoid: str = "", rng=None) -> dict | None:
    """What this turn asks for, decided against the field as it stands NOW.

    The engine should call this every turn rather than walking a plan made
    before anything died: an incantation whose enemy is already down is not a
    demand, it is a trick question.
    """
    pool = demandable(moveset, context, chapter=chapter)
    if not pool:
        return None
    choices = [i for i in pool if i.id != avoid] or pool
    choice = rng.choice(choices) if rng is not None else choices[0]
    living = context.living()
    hits_enemy = any(h.kind == ENEMY for h in choice.holes)
    return {
        "incantation": choice.id,
        "name": choice.name,
        "suggested_target": living[0].name if (hits_enemy and living) else "",
    }


def expected_damage(inc: Incantation | str, *, tier: int = 1) -> float:
    """What a competent, unremarkable cast of this incantation is worth.

    The template filled with its own worked example, at the given tier. It is
    the honest estimate because it is a real measurement of a real line: no
    encounter has to guess at a move's strength any more, it can ask.
    """
    inc = BY_ID[inc] if isinstance(inc, str) else inc
    measured = measure_complexity(inc, dict(inc.example), tier=tier)
    amount, _, _ = _damage_for(inc, None, tier, 0, 0.0, False,
                               complexity=measured)
    return float(amount)


def battle_length(context: BattleContext, moveset: dict, *, tier: int = 1) -> int:
    """Roughly how many correct casts this field will take. Battles run long on
    purpose: a two-cast fight teaches nobody anything.

    Measured rather than declared: every candidate move is scored at the tier
    the player is actually playing at, so a fight against a fluent player is
    correctly predicted to be shorter. That is not the fight getting easier, it
    is the player getting better, and the estimate should say so."""
    pool = demandable(moveset, context) or list(equipped(moveset))
    if not pool:
        return 0
    average = sum(expected_damage(i, tier=tier) for i in pool) / len(pool)
    total_hp = sum(e.hp for e in context.living())
    return max(1, int(round(total_hp / max(1.0, average))))


# ---------------------------------------------------------------------------
# Self test
# ---------------------------------------------------------------------------

def self_test(inc: Incantation | str, *, explain: bool = False):
    """Cast an incantation with its own worked example, through all three layers.

    If this fails, the incantation is not fit to be demanded of a player: its
    template, its example or its promise is wrong. Nothing here is mocked — the
    line really is parsed, bound and executed in the sandbox.
    """
    inc = BY_ID[inc] if isinstance(inc, str) else inc
    context = practice_context(inc)
    missing = [h.name for h in inc.holes if h.name not in inc.example]
    if missing:
        result = CastResult(incantation=inc.id, correct=False, layer="blank",
                            teaching="example is missing %s" % ", ".join(missing))
        return (False, result) if explain else False
    result = cast(inc.id, dict(inc.example), context, tier=1, apply=False)
    return (result.correct, result) if explain else result.correct


def self_check_complexity() -> dict:
    """The damage curve, measured over the whole catalogue. Real numbers.

    Calibration anchor: `bestiary.BASE_DAMAGE` is 10 and `SIGNATURE_DAMAGE` is
    16, and every encounter in the game was sized around those two numbers. An
    ordinary cast at tier 1 has to land near 10 and a weakness strike near 16,
    or the authored length of every fight in the game is quietly wrong.
    """
    problems: list = []
    rows = []
    for inc in CATALOGUE:
        damage = [expected_damage(inc, tier=t) for t in range(MAX_TIER + 1)]
        scores = [measure_complexity(inc, dict(inc.example), tier=t).score
                  for t in range(MAX_TIER + 1)]
        rows.append({"id": inc.id, "power": inc.power, "damage": damage,
                     "score": scores})
        if damage != sorted(damage):
            problems.append("%s: damage falls as the scaffold is removed" % inc.id)
        if min(damage) < 1:
            problems.append("%s: a correct cast landed for nothing" % inc.id)

    tier1 = sorted(r["damage"][1] for r in rows)
    median = tier1[len(tier1) // 2]
    if not 9.0 <= median <= 11.5:
        problems.append("the median ordinary cast is %.1f, not near "
                        "bestiary.BASE_DAMAGE of 10" % median)

    # The thing this whole section exists for: two casts of the SAME move, one
    # written plainly and one written well. If the second is not worth more,
    # complexity is not the spine and the file has failed.
    plain = measure_complexity("mirror", {"out": "out", "expr": "n", "var": "n",
                                          "seq": "nums"}, tier=3)
    rich = measure_complexity("mirror", {"out": "out", "seq": "nums", "var": "n",
                                         "expr": "n * 2 if n % 2 else n"}, tier=3)
    if rich.score <= plain.score:
        problems.append("writing better Python in the same move paid no more")

    return {
        "moves": len(rows),
        "unit": DAMAGE_UNIT,
        "weight_range": (WEIGHT_MIN, WEIGHT_MAX),
        "median_ordinary_cast": median,
        "tier1_range": (tier1[0], tier1[-1]),
        "tier3_range": (min(r["damage"][3] for r in rows),
                        max(r["damage"][3] for r in rows)),
        "same_move_plain": {"score": plain.score, "weight": plain.weight},
        "same_move_written_well": {"score": rich.score, "weight": rich.weight,
                                   "notes": list(rich.notes)},
        "gain_for_writing_it_better": round(rich.weight / plain.weight, 3),
        "rows": rows,
        "problems": problems,
    }


def self_test_all() -> dict:
    """Every incantation, every layer. Used by the acceptance tests."""
    failures = {}
    for inc in CATALOGUE:
        ok, result = self_test(inc, explain=True)
        if not ok:
            failures[inc.id] = "%s: %s %s" % (result.layer, result.teaching,
                                              result.detail)
    return {"total": len(CATALOGUE), "failed": len(failures), "detail": failures}


# ---------------------------------------------------------------------------
# Integration note
# ---------------------------------------------------------------------------
# This module is the combat engine, not the encounter. Wiring it up is four
# calls, and they belong in gauntlet/engine.py:
#
#   1. state["moveset"] = incantation.new_moveset() in DEFAULT_STATE, and
#      incantation.grow_slots(moveset, level) wherever the player levels.
#   2. On entering a battle: build the field with make_context(...), then
#      plan_battle(moveset, context, chapter=..., turns=battle_length(...)).
#      Render each demand with render_template(inc, tier_for_move(moveset, id,
#      state["skills"]), context=context) and send the ghost text to the client.
#   3. On a submitted cast: cast(id, answers, context, tier=..., seconds=...,
#      streak=state["player"]["combo"], timed=(mode == MODE_INTERVIEW),
#      scale=<whatever gauntlet/movesets.py's scale_for said, or 1.0>).
#      result.damage is already complexity-scaled; result.complexity is the
#      whole measurement, for a client that wants to show the player WHICH part
#      of the line they just wrote is what paid.
#      Apply result.damage to the named enemy, fold result.skill_deltas into
#      state["skills"][name]["mastery"] the way _apply_outcome already does for
#      a graded submission, and call record_cast(moveset, result) so the
#      scaffold has something to move on. A result with turn_wasted True means
#      the enemy acts and the SAME demand is re-rendered — one tier lower, by
#      arithmetic rather than by pity.
#   4. On clearing content: learn_from_clear(moveset, skill=problem.skill,
#      chapter=curriculum.frontier(state["skills"])) and show whatever
#      it returns. That is the only way an incantation is ever acquired.
#
# The SRS hook is stats: CastStats.last_correct_at and median_seconds are the
# per-idiom evidence srs.py needs to schedule a line for re-demand days later.
# Repetition inside a fight builds fluency; only the schedule builds retention.
#
# WHAT CHANGED WHEN COMPLEXITY BECAME THE SPINE
# ----------------------------------------------
# `_damage_for` no longer reads `Incantation.power` as a strength. It reads
# `measure_complexity`, which reads the line the player typed. `power` survives
# as a floor — POWER_FLOOR_SHARE of it — so a correct cast of a simple idiom is
# never worth nothing, and that is the only job it has left. Authoring a bigger
# number on a move can no longer make that move hit harder. The only way to hit
# harder is to write better Python, which is the whole design and now the whole
# arithmetic. `self_check_complexity()` measures the curve over all sixty-six
# incantations and fails if the median ordinary cast drifts away from
# bestiary.BASE_DAMAGE.
#
# The old `1 + 0.25 * tier` term is gone rather than retained, because the tier
# now enters through SKELETON_CREDIT: at tier 0 the line is printed on the
# screen and the player gets 30% of its credit, at tier 3 there is nothing on
# the screen and they get all of it. The scaffold fade and the damage curve are
# the same curve, and there is one rule to explain instead of two.
