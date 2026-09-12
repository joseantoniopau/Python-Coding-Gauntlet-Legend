"""The bestiary: enemies that ARE Python variables.

Every other enemy in this game is a monster that happens to be carrying a problem.
These ones are different. Here the monster IS the construct and its NAME is the
variable you have to type:

    SEEN, the Hollow Set          ->  the variable `seen`, a set
    COUNTS, the Tally Wraith      ->  the variable `counts`, a dict
    LEFT and RIGHT, Twin Wardens  ->  `left` and `right`, two indices
    WINDOW, the Creeping Frame    ->  `window`, a deque
    TOTAL, the Accumulator        ->  `total`, an int

To hit a thing you cast an INCANTATION at it — a real Python idiom rendered as grey
ghost text with holes in it — and you fill the holes with the names standing in front
of you. `{store}.add({item})` becomes `seen.add(ch)` because SEEN is the enemy and
CH is what the loop is holding. That is the whole mechanic. It is retrieval
practice with a health bar.

WHY IT IS BUILT THIS WAY
------------------------
Four findings drive the numbers in this file, and they are the only reason any of
them are what they are:

  RETRIEVAL PRACTICE   Recalling with little support beats re-reading, because it
                       defeats the illusion of knowing. Typing the line is the point;
                       nothing in here ever offers a line to pick from a list.
  GENERATION EFFECT    Producing beats recognising. Hence holes, not options.
  DESIRABLE DIFFICULTY A wrong cast wastes the turn and nothing else. Effort is what
                       makes the memory stick; punishment is what makes people stop.
  INTERLEAVING         Every encounter in this file fields two to four DIFFERENT
                       enemies demanding DIFFERENT incantations, because the skill
                       being trained is discrimination — working out WHICH idiom
                       applies — and a fight against four copies of the same monster
                       trains nothing but typing speed.

Encounter HP is tuned so a fight takes between 8 and 20 casts. That is deliberate on
both ends. Below eight there is no repetition; above twenty it is a chore, and massed
practice past the point of fluency buys no retention anyway. Retention is the SRS's
job across days; this file's job is fluency within the fight.

RESISTANCE IS A LESSON, NOT A STAT
----------------------------------
An enemy resists an incantation when that incantation is genuinely the wrong tool for
that construct, and the resistance line says why:

  SEEN resists TALLY        a set forgets multiplicity; counting into it is nonsense
  COUNTS resists MARK       `.add` is not a dict method, and would throw the
                            numbers away if it were
  WINDOW resists REACH      `window[i]` on a deque walks the deque; O(1) at the ends
                            is the entire reason you chose a deque
  HEAP resists WEIGH        sorting a heap works, costs O(n log n), and gives up the
                            one property you were paying for

Casting a resisted incantation wastes the turn. That is the Blitz rule, and it is
survivable by design: nothing is lost but the turn, and the enemy gets to act.

CONTRACT WITH gauntlet/incantation.py
-------------------------------------
This module and `incantation.py` are written to be independently loadable. Nothing
here imports it at module scope and nothing here needs it to be present. Incantations
are referenced BY STRING ID only, and `EXPECTED_INCANTATIONS` below mirrors the
catalogue — id, chapter, skill, template, gloss — so this file loads, verifies and
reads on its own even if incantation.py is absent.

`incantation.CATALOGUE` is authoritative at runtime. `verify()` performs the
reconciliation lazily and reports any id this bestiary references that the catalogue
does not define. Run `python -m gauntlet.bestiary` to see that report.

Shapes repeat deliberately, and the repetition is the lesson rather than a
redundancy. ADVANCE is `{counter} += 1` whether you aim it at LEFT, at RIGHT or at
TOTAL; INSCRIBE and ENSHRINE write to a dict in the same shape and mean entirely
different things. At scaffold tier 3 the player is shown only the incantation NAME,
so the name is what carries the intent, and aiming one shape at three different
wardens to three different ends is precisely the discrimination being trained.

VOCABULARY NOTE. This file was drafted against a provisional naming — GUARD, MARK,
TALLY, ADVANCE, SHRINK, REACH and forty more — before incantation.py landed with its
own. Where the two disagreed, incantation.py won: it is the module that renders and
executes the line, so it owns the names. INCANTATION_ALIASES keeps the old spellings
resolvable so a stale reference elsewhere does not fail a cast, and verify() reports
any remaining drift in both directions.
"""
from __future__ import annotations

import copy
import heapq
import keyword
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# The incantation contract
# ---------------------------------------------------------------------------
# id -> (chapter_id, skill, template, gloss)
#
# Mirrored from incantation.CATALOGUE so this module loads, verifies and can be
# read on its own. incantation.py remains authoritative: verify() reconciles the
# two in both directions and reports any id that has drifted.
#
# chapter_id matches curriculum.CHAPTERS (incantation.py stores the same thing as
# an integer index). An incantation is AVAILABLE in its own chapter and every
# chapter after it — the moveset only ever grows.

EXPECTED_INCANTATIONS: dict = {
    # I. The Language Itself ----------------------------------------------
    'bind': ('fluency', 'PYTHON',
     '{target} = {value}',
     'Naming a result is the whole of programming. Reach for '
     'it first.'),
    'advance': ('fluency', 'PYTHON',
     '{counter} += 1',
     'Every loop that does not advance its own index runs '
     'forever.'),
    'gather': ('fluency', 'ARRAY',
     '{store}.append({item})',
     'Build the answer as you go; do not assemble it at the '
     'end.'),
    'measure': ('fluency', 'PYTHON',
     '{size} = len({seq})',
     'Length before loop. Half of all index bugs are length '
     'bugs.'),
    'reach': ('fluency', 'ARRAY',
     '{value} = {seq}[{index}]',
     'Reaching into a sequence by position. Mind the last '
     'valid index.'),
    'sever': ('fluency', 'ARRAY',
     '{part} = {seq}[{start}:{stop}]',
     'A slice copies. The stop index is never included — '
     'that is the trap.'),
    'swap': ('fluency', 'PYTHON',
     '{a}, {b} = {b}, {a}',
     'Python swaps in one line. No temporary, no third '
     'variable.'),
    'probe': ('fluency', 'SET',
     'if {item} in {store}:',
     'Ask before you act. In a set or dict this question is '
     'free.'),
    'guard': ('fluency', 'SET',
     'if {item} not in {store}:',
     'The first-sighting test. Everything de-duplicating '
     'starts here.'),
    'toll': ('fluency', 'ARRAY',
     '{total} += {seq}[{index}]',
     'The accumulator step. One element joins the total, '
     'then you move on.'),

    # II. The Four Vaults -------------------------------------------------
    'mark': ('structures', 'SET',
     '{store}.add({item})',
     'Record that you have been here. The visited-mark, in '
     'one line.'),
    'hollow': ('structures', 'SET',
     '{store} = set()',
     'An empty set needs set(). Empty braces build a dict, '
     'not a set.'),
    'ledger': ('structures', 'HASH_MAP',
     '{book} = {}',
     "The empty dict. Reach for it the moment you need 'seen "
     "it before'."),
    'inscribe': ('structures', 'HASH_MAP',
     '{book}[{key}] = {value}',
     'Writing a key that does not exist creates it. Reading '
     'one does not.'),
    'ask': ('structures', 'HASH_MAP',
     '{out} = {book}.get({key}, {default})',
     'get with a default never raises. Square brackets do.'),
    'tally': ('structures', 'HASH_MAP',
     '{book}[{key}] = {book}.get({key}, 0) + 1',
     'Count-by-key without a KeyError. The highest-yield '
     'line in interviews.'),
    'settle': ('structures', 'HASH_MAP',
     '{book}.setdefault({key}, []).append({item})',
     'Grouping: make the bucket if absent, then drop the '
     'item in it.'),
    'release': ('structures', 'SET',
     '{store}.discard({item})',
     'discard forgives a missing element. remove raises on '
     'it.'),
    'draw': ('structures', 'STACK',
     '{top} = {stack}.pop()',
     'pop takes from the end, and the end is the cheapest '
     'place to take from.'),
    'rollcall': ('structures', 'HASH_MAP',
     '{out} = sorted({book})',
     'Sorting a dict sorts its KEYS. Say .items() when you '
     'want both.'),

    # III. The Idioms -----------------------------------------------------
    'mirror': ('idiom', 'PYTHON',
     '{out} = [{expr} for {var} in {seq}]',
     'Transform every element. A comprehension, not a loop '
     'with append.'),
    'sift': ('idiom', 'PYTHON',
     '{out} = [{var} for {var} in {seq} if {cond}]',
     'Keep only what passes. The filter belongs at the end, '
     'after the for.'),
    'numbering': ('idiom', 'PYTHON',
     'for {i}, {item} in enumerate({seq}):',
     'When you need the index AND the value, enumerate gives '
     'you both.'),
    'pairing': ('idiom', 'PYTHON',
     'for {a}, {b} in zip({first}, {second}):',
     'Walk two sequences in step. zip stops at the shorter '
     'one.'),
    'march': ('idiom', 'ARRAY',
     'for {i} in range(len({seq})):',
     'Only when you genuinely need the index. Otherwise '
     'iterate directly.'),
    'weigh': ('idiom', 'SORTING',
     '{out} = sorted({seq}, key={keyfn})',
     'key takes a function, not a call. Pass len, not len().'),
    'greatest': ('idiom', 'ARRAY',
     '{best} = max({best}, {candidate})',
     'The high-water mark. It only ever moves one way.'),
    'least': ('idiom', 'ARRAY',
     '{best} = min({best}, {candidate})',
     'The mirror of GREATEST. Seed it with something big '
     'enough to lose.'),
    'distill': ('idiom', 'SET',
     '{out} = set({seq})',
     'Dedupe in one move. You lose the order; be sure you '
     'can afford to.'),
    'weave': ('idiom', 'STRING',
     '{out} = {glue}.join({parts})',
     'Build strings with join, never with += in a loop.'),
    'unravel': ('idiom', 'STRING',
     '{parts} = {text}.split({sep})',
     'split with no argument collapses all whitespace. With '
     'one, it does not.'),
    'temper': ('idiom', 'STRING',
     '{out} = {text}.{method}()',
     'Normalise before you compare, or case and whitespace '
     'will lie to you.'),

    # IV. Counting and Membership -----------------------------------------
    'complement': ('counting', 'HASH_MAP',
     '{need} = {target} - {seq}[{i}]',
     'Two-sum in one thought: ask what is missing, then look '
     'it up.'),
    'indexbook': ('counting', 'HASH_MAP',
     '{book}[{seq}[{i}]] = {i}',
     'Remember WHERE you saw it, not just that you did.'),
    'countdown': ('counting', 'HASH_MAP',
     '{book}[{key}] -= 1',
     'The other half of counting. Anagram checks live and '
     'die here.'),
    'purge': ('counting', 'HASH_MAP',
     'del {book}[{key}]',
     "Delete when a count hits zero, or your 'is it empty' "
     'test lies.'),

    # V. Scanning a Sequence ----------------------------------------------
    'converge': ('scanning', 'TWO_POINTER',
     'while {left} < {right}:',
     'Two pointers walking toward each other. They must be '
     'able to meet.'),
    'shrink': ('scanning', 'SLIDING_WINDOW',
     'while {total} > {limit}:',
     'The window contracts only while it is illegal. Not '
     'once — while.'),
    'inhale': ('scanning', 'SLIDING_WINDOW',
     '{total} += {seq}[{right}]',
     "The window's right edge steps forward and takes on one "
     'element.'),
    'exhale': ('scanning', 'SLIDING_WINDOW',
     '{total} -= {seq}[{left}]',
     'What leaves the window must be subtracted, or the '
     'total is a lie.'),
    'frame': ('scanning', 'SLIDING_WINDOW',
     '{window}.append({seq}[{right}])',
     'A deque takes from both ends in constant time. A list '
     'does not.'),
    'evict': ('scanning', 'SLIDING_WINDOW',
     '{gone} = {window}.popleft()',
     'popleft is why the window is a deque. From a list it '
     'costs O(n).'),
    'span': ('scanning', 'SLIDING_WINDOW',
     '{best} = max({best}, {right} - {left} + 1)',
     'Window length is right minus left plus one. The plus '
     'one is the bug.'),
    'prefix': ('scanning', 'PREFIX_SUM',
     '{sums}.append({sums}[-1] + {seq}[{i}])',
     'Each prefix is the one before it plus one element. '
     'Seed it with zero.'),

    # VI. Order and Structure ---------------------------------------------
    'peek': ('order', 'STACK',
     '{top} = {stack}[-1]',
     'Look without taking. Check it is not empty first.'),
    'dequeue': ('order', 'QUEUE',
     '{node} = {frontier}.popleft()',
     'Breadth-first takes from the FRONT. Take from the back '
     'and it is depth-first.'),
    'sink': ('order', 'HEAP',
     'heapq.heappush({heap}, {item})',
     'A heap is a list you only touch through heapq. Never '
     'sort it yourself.'),
    'surface': ('order', 'HEAP',
     '{item} = heapq.heappop({heap})',
     'heappop always returns the smallest. For the largest, '
     'push negatives.'),
    'halve': ('order', 'BINARY_SEARCH',
     '{mid} = ({left} + {right}) // 2',
     'Integer division, or the midpoint drifts off the grid '
     'as a float.'),
    'narrow': ('order', 'BINARY_SEARCH',
     '{left} = {mid} + 1',
     'Move past the midpoint, not to it, or the search never '
     'terminates.'),

    # VII. Things That Contain Themselves ---------------------------------
    'sentinel': ('recursion', 'PYTHON',
     'if not {seq}:',
     'The empty case, handled first. It is the test you will '
     'be given.'),
    'floor': ('recursion', 'RECURSION',
     'if {n} <= 1:',
     'The base case. Write it before the recursive call, '
     'always.'),
    'descend': ('recursion', 'RECURSION',
     '{total} += {fn}({node})',
     'Trust the recursive call to return the right answer '
     'for a smaller input.'),
    'unfold': ('recursion', 'RECURSION',
     'return {fn}({n} - 1) + {fn}({n} - 2)',
     'Two branches, both smaller. Without a base case this '
     'never returns.'),
    'pluck': ('recursion', 'RECURSION',
     '{value} = {node}.val',
     'A node is a value beside its references. Read the value '
     'first.'),
    'branch': ('recursion', 'RECURSION',
     '{node} = {node}.{side}',
     'Descend by rebinding the name. The child is a whole tree '
     'again.'),
    'consult': ('recursion', 'DP',
     'if {key} in {memo}:',
     'Check the archive before you pay for the answer again.'),
    'enshrine': ('recursion', 'DP',
     '{memo}[{key}] = {result}',
     'File the answer the moment you have it, or you will '
     'buy it again.'),

    # VIII. Maps and Mazes ------------------------------------------------
    'expand': ('traversal', 'GRAPH',
     'for {nb} in {graph}[{node}]:',
     'Adjacency: the neighbours of a node are a list hanging '
     'off a key.'),
    'enqueue': ('traversal', 'BFS',
     '{frontier}.append(({node}, {dist} + 1))',
     'Carry the distance with the node. Recomputing it later '
     'is how you lose it.'),
    'cell': ('traversal', 'MATRIX',
     '{value} = {grid}[{r}][{c}]',
     'Row first, then column. Getting that backwards is a '
     'silent bug.'),
    'bounds': ('traversal', 'MATRIX',
     'if 0 <= {r} < len({grid}) and 0 <= {c} < len({grid}[0]):',
     'Check the edges before you read the cell. Negative '
     'indices do not fail loudly.'),

    # IX. Paying Once -----------------------------------------------------
    'table': ('optimisation', 'DP',
     '{dp} = [0] * ({n} + 1)',
     'Size it n+1 so you can index by the number itself, not '
     'by an offset.'),
    'transition': ('optimisation', 'DP',
     '{dp}[{i}] = {dp}[{i} - 1] + {dp}[{i} - 2]',
     "Today's answer from yesterday's. That sentence IS "
     'dynamic programming.'),
    'choose': ('optimisation', 'DP',
     '{dp}[{i}] = max({dp}[{i} - 1], {dp}[{i} - 2] + {seq}[{i}])',
     'Take it or leave it, and keep the better. Most DP is '
     'this shape.'),

    # X. The Working Engineer ---------------------------------------------
    'witness': ('craft', 'TESTING',
     'assert {fn}({arg}) == {expected}',
     'One assertion per claim. The input you pick is the '
     "test's real content."),

}

INCANTATION_ALIASES: dict = {
    # Names this bestiary was drafted against, before incantation.py landed with
    # its own vocabulary. Kept so a stale reference in a save, a test or another
    # agent's branch resolves instead of failing.
    "append": "gather", "push": "gather", "add": "mark", "insert": "mark",
    "lengthen": "measure", "length": "measure", "sweep": "march",
    "test": "probe", "store": "inscribe", "fetch": "ask", "fallback": "ask",
    "unpack": "rollcall", "number": "numbering", "braid": "pairing",
    "comprehend": "mirror", "bucket": "settle", "signature": "weigh",
    "arrange": "weigh", "sort": "weigh", "crest": "span", "greatest_span": "span",
    "accrue": "toll", "evict_count": "countdown", "slide": "indexbook",
    "unpile": "draw", "pop": "draw", "unchoose": "draw",
    "heappush": "sink", "heappop": "surface", "drain": "surface",
    "fuse": "greatest", "merge": "greatest", "trough": "least",
    "basecase": "floor", "base_case": "floor", "combine": "unfold",
    "recurse": "unfold", "visit": "gather", "neighbours": "expand",
    "degree": "tally", "count": "tally", "memo_guard": "consult",
    "memo_check": "consult", "memo_store": "enshrine", "memoise": "enshrine",
    "memoize": "enshrine", "rolling": "swap", "empty_guard": "sentinel",
    "none_guard": "sentinel", "copy_guard": "sever", "slice": "sever",
    "assert_edge": "witness", "assert": "witness", "fix_bound": "narrow",
    "mid": "halve", "midpoint": "halve", "popleft": "dequeue",
    "increment": "advance", "inc": "advance", "index": "reach",
}

CHAPTER_ORDER: tuple = (
    "fluency", "structures", "idiom", "counting", "scanning", "order",
    "recursion", "traversal", "optimisation", "craft", "gauntlet",
)


def chapter_rank(chapter_id: str) -> int:
    try:
        return CHAPTER_ORDER.index(chapter_id)
    except ValueError:
        return len(CHAPTER_ORDER)


def incantations_available(chapter_id: str) -> set:
    """Every incantation the player could have learned by this chapter.

    The moveset is cumulative — chapter IX still fights with `advance`.
    """
    edge = chapter_rank(chapter_id)
    return {inc for inc, row in EXPECTED_INCANTATIONS.items()
            if chapter_rank(row[0]) <= edge}


_HOLE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")


def ghost_template(inc_id: str) -> str:
    """The template with every hole blanked: `{store}.add({item})` becomes
    `____.add(____)`.

    A fallback for anything that just wants a line to grey out. Scaffold tiers —
    how much of the line is shown at each level of mastery — belong to
    incantation.py, which knows what it blanks and in what order.
    """
    return _HOLE.sub("____", incantation_template(inc_id))


def incantation_template(inc_id: str) -> str:
    """The ghost text, from incantation.py if it is loaded, otherwise from this
    file's half of the contract. Never raises: a missing incantation renders as its
    own name, which is exactly what scaffold tier 3 shows anyway."""
    live = _live_catalogue()
    if live is not None:
        row = live.get(inc_id)
        template = _attr(row, "template") or _attr(row, "line") or _attr(row, "ghost")
        if template:
            return str(template)
    row = EXPECTED_INCANTATIONS.get(inc_id)
    return row[2] if row else inc_id.upper()


def resolve_incantation(inc_id: str) -> str:
    """Normalise an incantation id against the live catalogue.

    Tolerates case, surrounding whitespace and the alias table, so a disagreement
    between this file and incantation.py over `add` versus `mark` does not strand
    a cast mid-battle.
    """
    raw = str(inc_id or "").strip()
    if not raw:
        return ""
    for candidate in (raw, raw.lower(), INCANTATION_ALIASES.get(raw.lower(), "")):
        if candidate and candidate in EXPECTED_INCANTATIONS:
            return candidate
    live = _live_catalogue()
    if live is not None and raw.lower() in live:
        return raw.lower()
    return raw.lower()


def _attr(row, name):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _live_catalogue() -> dict | None:
    """gauntlet.incantation.CATALOGUE as a dict keyed by id, or None if that module
    is not present. Imported lazily and defensively — the two modules are authored
    in parallel and neither may block the other from loading."""
    try:
        from . import incantation  # noqa: WPS433 - deliberate late import
    except Exception:
        return None
    catalogue = getattr(incantation, "CATALOGUE", None)
    if catalogue is None:
        return None
    if isinstance(catalogue, dict):
        return dict(catalogue)
    out = {}
    for row in catalogue:
        key = _attr(row, "id")
        if key:
            out[str(key)] = row
    return out


# ---------------------------------------------------------------------------
# Values: what each enemy IS, materialised fresh for every battle
# ---------------------------------------------------------------------------
# Most enemy values are plain literals. The few that are not (a deque, a
# defaultdict, a binary tree) are written as a tiny spec dict keyed "@" so the
# roster stays readable and nothing mutable is shared between two battles.

class Node:
    """A binary tree node, and the linked-list node when only `next` is used.

    Deliberately anaemic. The player is learning that a node is a value plus two
    references and nothing else; giving it methods would teach the opposite.
    """

    __slots__ = ("val", "left", "right", "next")

    def __init__(self, val=0, left=None, right=None, next=None):
        self.val = val
        self.left = left
        self.right = right
        self.next = next

    def __repr__(self):
        return f"Node({self.val!r})"


def _tree(layout):
    """Level-order list with None for gaps -> root Node. [5, 3, 8, 1, 4] is the
    shape a player sees in every tree problem they will ever be given."""
    if not layout or layout[0] is None:
        return None
    nodes = [None if v is None else Node(v) for v in layout]
    kids = iter(nodes[1:])
    for node in nodes:
        if node is None:
            continue
        node.left = next(kids, None)
        node.right = next(kids, None)
    return nodes[0]


def _chain(values):
    head = None
    for val in reversed(values):
        head = Node(val, next=head)
    return head


def materialise(spec):
    """Turn a roster value into a live object. Deep-copies everything so two
    battles, or two casts, can never share a mutable."""
    if isinstance(spec, dict) and "@" in spec:
        kind = spec["@"]
        if kind == "deque":
            return deque(copy.deepcopy(spec.get("items", [])),
                         maxlen=spec.get("maxlen"))
        if kind == "defaultdict":
            kinds = {"list": list, "int": int, "set": set}
            factory = kinds[spec.get("factory", "list")]
            out = defaultdict(factory)
            for key, val in copy.deepcopy(spec.get("items", {})).items():
                out[key] = val
            return out
        if kind == "counter":
            return Counter(copy.deepcopy(spec.get("items", {})))
        if kind == "tree":
            return _tree(spec.get("layout", []))
        if kind == "chain":
            return _chain(spec.get("items", []))
        if kind == "heap":
            items = list(copy.deepcopy(spec.get("items", [])))
            heapq.heapify(items)
            return items
        if kind == "none":
            return None
        raise ValueError(f"unknown value spec: {kind}")
    return copy.deepcopy(spec)


def value_sketch(spec) -> str:
    """A short, honest rendering for the battle sidebar: `seen = set()`.

    Long collections are elided rather than wrapped, because the sidebar is one
    line per enemy and the player is reading it while typing.
    """
    value = materialise(spec)
    if isinstance(value, deque):
        text = f"deque({list(value)!r})"
    elif isinstance(value, defaultdict):
        text = f"defaultdict(list, {dict(value)!r})"
    elif isinstance(value, Counter):
        text = f"Counter({dict(value)!r})"
    elif isinstance(value, Node):
        text = f"Node({value.val!r})"
    else:
        text = repr(value)
    return text if len(text) <= 46 else text[:43] + "..."


# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Enemy:
    id: str                 # also the VARIABLE NAME. A valid Python identifier.
    title: str              # "SEEN, the Hollow Set"
    type: str               # set | dict | list | int | str | deque | heap |
                            # index | node | matrix | tuple | bool | none
    chapter: str            # curriculum chapter this construct belongs to
    skill: str              # skills.SKILLS entry it trains
    value: object           # literal, or a "@" spec -> materialise()
    hp: int                 # default HP; encounters may override
    weak_to: tuple          # incantation ids that damage it. [0] is its SIGNATURE.
    resists: tuple          # incantation ids that waste the turn, and why
    sprite: str             # web/js/sprites.js ENEMY_SHAPE_FOR key
    colour: str
    effect: str             # per-enemy effect id, for the FX agent
    effect_family: str      # the drawing technique this effect belongs to
    effect_note: str        # one line of direction for whoever draws it
    flavour: tuple          # 2-3 lines that teach something TRUE about the type

    @property
    def name(self) -> str:
        """The variable. Same thing as the id; named twice because in combat text
        it reads as a name and in code it reads as an identifier."""
        return self.id

    @property
    def signature(self) -> str:
        return self.weak_to[0] if self.weak_to else ""

    def fresh_value(self):
        return materialise(self.value)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.id, "title": self.title, "type": self.type,
            "chapter": self.chapter, "skill": self.skill, "hp": self.hp,
            "value": value_sketch(self.value),
            "weak_to": list(self.weak_to), "signature": self.signature,
            "resists": list(self.resists), "sprite": self.sprite,
            "colour": self.colour, "effect": self.effect,
            "effect_family": self.effect_family,
            "flavour": list(self.flavour),
            "templates": {inc: ghost_template(inc) for inc in self.weak_to},
        }


def _E(id, title, type, chapter, skill, value, hp, weak_to, resists,
       sprite, colour, effect, effect_family, effect_note, flavour):
    return Enemy(id=id, title=title, type=type, chapter=chapter, skill=skill,
                 value=value, hp=hp, weak_to=tuple(weak_to), resists=tuple(resists),
                 sprite=sprite, colour=colour, effect=effect,
                 effect_family=effect_family, effect_note=effect_note,
                 flavour=tuple(flavour))


ENEMIES: tuple = (
    # -- I. The Language Itself ---------------------------------------------
    _E("total", "TOTAL, the Accumulator", "int", "fluency", "PYTHON", 0, 48,
       ["advance", "toll", "descend", "bind"], ["mark", "gather", "tally"],
       "ledgerling", "#d6a84f", "fx_total_surge", "count_up",
       "Numerals climb its spine and stay lit; each hit adds one more rung.",
       ["It starts at zero and it returns to zero the moment you declare it inside "
        "the loop instead of above it.",
        "One idiom grows it: `+=`. Handing an accumulator a list does nothing but "
        "raise.",
        "An accumulator you reset every pass is a very slow way of writing the last "
        "element."]),
    _E("count", "COUNT, the Notch Keeper", "int", "fluency", "PYTHON", 0, 44,
       ["advance", "probe", "bind"], ["reach", "mark", "gather"],
       "indexling", "#6f8fbf", "fx_count_notch", "count_up",
       "A tally notch is cut into it on each hit; the notches never heal.",
       ["A counter is an int, not a container. `count[0]` is a TypeError and always "
        "will be.",
        "If you need counts per key, you do not want COUNT. You want a dict."]),
    _E("name", "NAME, the Bound Sigil", "str", "fluency", "PYTHON", "gauntlet", 40,
       ["bind", "reach", "measure"], ["inscribe", "gather", "mark"],
       "slime", "#5fbf8f", "fx_name_rebind", "seal",
       "The old glyph fades and a new one burns in over it. Nothing is edited.",
       ["Strings are immutable. `name[0] = 'G'` raises; you build a new string and "
        "rebind the name.",
        "Rebinding is cheap. Rebuilding a string inside a loop, one character at a "
        "time, is not."]),
    _E("items", "ITEMS, the Ordered Horde", "list", "fluency", "ARRAY",
       [3, 1, 4, 1, 5], 52,
       ["gather", "reach", "sever"], ["mark", "tally", "guard"],
       "sorter", "#6a9c8f", "fx_items_ripple", "chain_link",
       "The horde ripples from index zero outward, one body at a time.",
       ["A list keeps order and keeps duplicates. Both of those are features you pay "
        "for.",
        "`for x in items` walks the elements. `for i in range(len(items))` walks the "
        "positions. Pick the one you actually need."]),
    _E("flag", "FLAG, the Truth Warden", "bool", "fluency", "PYTHON", False, 36,
       ["bind", "probe"], ["advance", "gather", "mark"],
       "wisp", "#9b96b8", "fx_flag_flip", "seal",
       "It snaps between two states only. No in-between frames.",
       ["`bool` is a subclass of `int`, so `flag += 1` silently turns True into 2 and "
        "your truth value into arithmetic.",
        "Compare with `if flag:`, not `if flag == True:`. The second one is noise."]),
    _E("text", "TEXT, the Long Sentence", "str", "fluency", "STRING",
       "a man a plan", 50,
       ["reach", "bind", "sever"], ["inscribe", "gather", "mark"],
       "slime", "#5fbf8f", "fx_text_unspool", "chain_link",
       "Letters unspool off it in a ribbon and are swallowed back.",
       ["A string is a sequence of characters, so `for ch in text` works exactly like "
        "a list walk.",
        "Slicing copies. `text[::-1]` is a whole new string, and inside a loop that "
        "is how an O(n) problem becomes O(n squared)."]),
    _E("i", "I, the Wandering Index", "index", "fluency", "ARRAY", 0, 38,
       ["advance", "reach", "bind"], ["mark", "tally", "gather"],
       "indexling", "#6f8fbf", "fx_index_step", "count_up",
       "It hops one slot at a time along a lit ruler.",
       ["An index is a number that points. It is not the thing it points at.",
        "The last valid index is `len(seq) - 1`. Nearly every off-by-one in your "
        "career is that sentence, forgotten."]),
    _E("result", "RESULT, the Empty Vessel", "list", "fluency", "ARRAY", [], 46,
       ["gather", "bind", "mirror"], ["reach", "ask", "mark"],
       "vault", "#8fd07a", "fx_result_fill", "chain_link",
       "A glass vessel that fills from the bottom as it takes damage.",
       ["An empty list is falsy, indexes into nothing, and is the correct return "
        "value far more often than you expect.",
        "Build it with `append` in a loop, or with a comprehension. Not both."]),

    # -- II. The Four Vaults -------------------------------------------------
    _E("seen", "SEEN, the Hollow Set", "set", "structures", "SET", {"a", "b"}, 54,
       ["guard", "mark"], ["tally", "inscribe", "reach", "gather"],
       "wisp", "#7ec8ff", "fx_set_collapse", "collapse",
       "Duplicates fold into one another with a dry click and are gone.",
       ["A set forgets multiplicity. Add 'a' a thousand times and it holds one 'a', "
        "which is exactly why counting into it is nonsense.",
        "It also forgets order, and it cannot be indexed. `seen[0]` raises.",
        "What it gives you in exchange is O(1) membership, and that trade wins most "
        "interview problems."]),
    _E("lookup", "LOOKUP, the Keyed Vault", "dict", "structures", "HASH_MAP",
       {"a": 1, "b": 2}, 56,
       ["ask", "inscribe", "rollcall"], ["gather", "mark", "sink"],
       "vault", "#e8a33d", "fx_vault_open", "vault_open",
       "One door of many swings open; the others stay shut and dark.",
       ["A dict maps a key to exactly one value. Store twice under the same key and "
        "the first value is simply gone.",
        "Keys must be hashable, which is why a tuple can be a key and a list cannot."]),
    _E("stock", "STOCK, the Keyed Store", "dict", "structures", "HASH_MAP",
       {"rope": 2}, 46,
       ["inscribe", "ask", "guard"], ["gather", "mark", "weigh"],
       "vault", "#c89a3d", "fx_stock_shelve", "vault_open",
       "Shelves slide out, take the value, and slide back flush.",
       ["`stock[key] = value` creates the key if it is new and overwrites it if it "
        "is not. There is no third behaviour.",
        "Reading a key that is not there raises KeyError. That is a feature: it tells "
        "you your model was wrong."]),
    _E("bag", "BAG, the Mutable Hoard", "list", "structures", "ARRAY",
       [2, 7, 11], 48,
       ["gather", "reach", "sever"], ["guard", "mark", "ask"],
       "hoarder", "#bf8f5f", "fx_bag_stuff", "chain_link",
       "It swells as things go in and never quite closes again.",
       ["Asking a list whether it has seen something costs a walk of the whole list. "
        "A set answers the same question in one step.",
        "That difference is the entire gap between an O(n squared) solution and an "
        "O(n) one."]),
    _E("frozen", "FROZEN, the Sealed Tuple", "tuple", "structures", "PYTHON",
       (2, 7), 42,
       ["reach", "bind", "measure"], ["inscribe", "gather", "mark"],
       "sentinel", "#5a9cd6", "fx_frozen_seal", "seal",
       "Cracks race across it and then knit shut. Nothing gets in.",
       ["A tuple cannot be changed after it is made, which is precisely why it can be "
        "a dict key or a set member.",
        "`(r, c)` as a key is the standard way to remember a grid cell you have "
        "already visited."]),
    _E("unique", "UNIQUE, the Winnowing Ward", "set", "structures", "SET", set(), 44,
       ["mark", "guard"], ["reach", "inscribe", "tally"],
       "wisp", "#7ec8ff", "fx_unique_winnow", "collapse",
       "Chaff blows off it in sheets; one grain remains of each kind.",
       ["`set(items)` in one call does what a loop with a membership test does in "
        "four lines.",
        "You lose the order doing it. If order matters, `dict.fromkeys(items)` keeps "
        "it, because dicts have been ordered since 3.7."]),
    _E("missing", "MISSING, the Absent Key", "dict", "structures", "HASH_MAP", {}, 40,
       ["ask", "guard"], ["reach", "draw", "mark"],
       "riddler", "#8f9cd6", "fx_missing_void", "vault_open",
       "A door with nothing behind it. The hit lands on the frame.",
       ["`d[k]` on an absent key raises KeyError. `d.get(k, 0)` returns the default "
        "and keeps going.",
        "Which one you want depends on whether an absent key is a bug or a normal "
        "case. Decide that before you type either."]),
    _E("charset", "CHARSET, the Letter Ward", "set", "structures", "SET",
       {"a", "b", "c"}, 42,
       ["mark", "guard"], ["tally", "inscribe", "reach"],
       "wisp", "#7ec8ff", "fx_charset_glyphs", "collapse",
       "Letters orbit it and wink out as they are absorbed.",
       ["`set('hello')` is four characters, not five. The second 'l' had nowhere to "
        "go.",
        "If the question is 'how many of each letter', a set has already thrown away "
        "the answer."]),

    # -- III. The Idioms -----------------------------------------------------
    _E("counts", "COUNTS, the Tally Wraith", "dict", "idiom", "HASH_MAP", {}, 58,
       ["tally", "ask", "inscribe"], ["mark", "gather", "guard"],
       "vault", "#e8a33d", "fx_tally_burn", "tally_burn",
       "Numerals brand themselves onto its hide, each one ticking upward.",
       ["`counts[x] = counts.get(x, 0) + 1` is one line and it is the single highest "
        "yield line in interview Python.",
        "It resists anything that throws the numbers away. A set would answer "
        "'yes I saw it' and lose 'forty-one times'.",
        "`Counter(items)` does the same job when you are allowed the import."]),
    _E("freq", "FREQ, the Counter Shade", "dict", "idiom", "HASH_MAP",
       {"@": "counter", "items": {"a": 2, "b": 1}}, 50,
       ["tally", "ask", "rollcall"], ["mark", "gather", "reach"],
       "vault", "#d68f4f", "fx_freq_bars", "tally_burn",
       "Bar heights rise and fall across its chest as the counts change.",
       ["A Counter is a dict that returns 0 for keys it has never seen, so no guard "
        "is needed before you increment.",
        "`freq.most_common(1)` is the whole of a top-k question when k is one."]),
    _E("groups", "GROUPS, the Defaultdict Choir", "dict", "idiom", "HASH_MAP",
       {"@": "defaultdict", "factory": "list", "items": {}}, 54,
       ["settle", "ask", "rollcall"], ["inscribe", "mark", "gather"],
       "construct", "#c88fd6", "fx_groups_gather", "vault_open",
       "Voices pull toward each other and merge into one chord per key.",
       ["`groups[key].append(word)` only works because the defaultdict invents the "
        "empty list for you. On a plain dict it raises.",
        "Storing instead of appending is the classic error: `groups[key] = word` "
        "keeps the last word and silently discards the group."]),
    _E("pairs", "PAIRS, the Braided Twins", "list", "idiom", "PYTHON", [], 46,
       ["pairing", "gather", "rollcall"], ["tally", "mark", "reach"],
       "warden", "#c4553f", "fx_pairs_braid", "chain_link",
       "Two strands twist together and are cut at the shorter one's end.",
       ["`zip` stops at the shorter sequence without a word of warning. If that is a "
        "bug, check the lengths first.",
        "`zip(a, b)` gives you tuples; `list(zip(a, b))` gives you them as a list you "
        "can walk twice."]),
    _E("squares", "SQUARES, the Comprehension Wisp", "list", "idiom", "PYTHON", [], 44,
       ["mirror", "sift", "gather"], ["inscribe", "tally", "mark"],
       "wisp", "#8fd07a", "fx_squares_bloom", "chain_link",
       "The whole list blooms at once rather than one element at a time.",
       ["`[x * x for x in nums]` replaces three lines and one `append`, and it is "
        "faster because the loop runs in C.",
        "It stops being clearer than a loop the moment it needs two conditions and a "
        "nested for. Then write the loop."]),
    _E("window", "WINDOW, the Creeping Frame", "deque", "idiom", "QUEUE",
       {"@": "deque", "items": [1, 2, 3]}, 56,
       ["frame", "evict", "draw", "peek"], ["reach", "inscribe", "weigh"],
       "marshling", "#7f6ad6", "fx_window_slide", "frame_slide",
       "A bright rectangle slides along the ground, widening then snapping shorter.",
       ["A deque gives you O(1) at both ends, which is the only reason to reach for "
        "one instead of a list.",
        "`window[i]` in the middle costs a walk. If you are indexing into the middle "
        "of a deque, you wanted a list."]),
    _E("index_of", "INDEX_OF, the Position Oracle", "dict", "idiom", "HASH_MAP", {}, 48,
       ["numbering", "inscribe", "ask"], ["gather", "mark", "tally"],
       "riddler", "#8f9cd6", "fx_index_oracle", "vault_open",
       "It points, and a numeral flares over the position it names.",
       ["`for i, x in enumerate(seq)` gives you both at once. `range(len(seq))` then "
        "`seq[i]` is the same thing with extra steps.",
        "Storing the index rather than a count is what turns 'have I seen it' into "
        "'where did I see it', and that is a different class of problem."]),
    _E("line", "LINE, the Enumerated Row", "list", "idiom", "ARRAY",
       ["a", "b", "c"], 42,
       ["numbering", "reach", "march"], ["mark", "tally", "sink"],
       "sorter", "#6a9c8f", "fx_line_number", "chain_link",
       "Line numbers illuminate one after another down its length.",
       ["`enumerate(seq, 1)` starts the count at one, for when you are numbering "
        "things a human will read.",
        "The index and the element are two different values. Naming them `i, x` and "
        "then using the wrong one is the most common trace bug there is."]),

    # -- IV. Counting and Membership ----------------------------------------
    _E("target", "TARGET, the Sum That Waits", "int", "counting", "HASH_MAP", 9, 50,
       ["complement", "probe", "bind"], ["mark", "gather", "weigh"],
       "riddler", "#e8c37d", "fx_target_lock", "seal",
       "A reticle closes on it and holds until the complement is named.",
       ["Two-sum is not about finding two numbers. It is about, for each number, "
        "asking whether its complement has already gone past.",
        "`need = target - x` is the line. Everything else is bookkeeping."]),
    _E("need", "NEED, the Complement", "int", "counting", "HASH_MAP", 0, 46,
       ["complement", "bind", "guard"], ["gather", "mark", "sink"],
       "wisp", "#7ec8ff", "fx_need_mirror", "collapse",
       "Its silhouette is the negative space of the thing beside it.",
       ["The complement is computed before the lookup, not after. Compute, then ask "
        "the ledger.",
        "Check the ledger before you write yourself into it, or a number pairs with "
        "itself and you return the same index twice."]),
    _E("first_seen", "FIRST_SEEN, the Ledger of Firsts", "dict", "counting",
       "HASH_MAP", {}, 52,
       ["inscribe", "guard", "ask"], ["tally", "mark", "gather"],
       "vault", "#e8a33d", "fx_first_stamp", "vault_open",
       "A date-stamp thuds down and refuses to be overwritten.",
       ["Whether you overwrite an existing key decides whether you are recording the "
        "first sighting or the last. Both are correct; only one answers the question.",
        "Guard with `if x not in first_seen:` when first is what you mean."]),
    _E("dupes", "DUPES, the Echo Twins", "set", "counting", "SET", set(), 48,
       ["guard", "mark"], ["tally", "inscribe", "reach"],
       "mirrorspawn", "#8f6ad6", "fx_dupes_echo", "collapse",
       "It splits into identical copies that snap back into one.",
       ["'Have I seen this before' is a set, one line, O(1). It is the reflex the "
        "whole of chapter four exists to build.",
        "If the question is 'how many times', you have the wrong structure in front "
        "of you."]),
    _E("buckets", "BUCKETS, the Grouped Congregation", "dict", "counting", "HASH_MAP",
       {"@": "defaultdict", "factory": "list", "items": {}}, 56,
       ["settle", "weigh", "rollcall"], ["inscribe", "mark", "advance"],
       "construct", "#c88fd6", "fx_buckets_sort", "vault_open",
       "Figures stream into lit alcoves, one alcove per signature.",
       ["Anagram grouping is one idea: give every word a canonical form, then group "
        "on that form.",
        "`tuple(sorted(word))` is hashable and `sorted(word)` is not, which is the "
        "whole reason for the tuple."]),
    _E("letters", "LETTERS, the Sorted Signature", "tuple", "counting", "STRING",
       (), 44,
       ["weigh", "bind", "measure"], ["inscribe", "gather", "mark"],
       "slime", "#5fbf8f", "fx_letters_settle", "sort_cascade",
       "Its glyphs rearrange themselves into alphabetical order and lock.",
       ["Two anagrams have the same sorted letters. That is the only fact the problem "
        "turns on.",
        "Sorting each word costs O(k log k); counting each word's letters costs O(k). "
        "For long words, say so."]),
    _E("required", "REQUIRED, the Demand Ledger", "dict", "counting", "HASH_MAP",
       {"a": 1, "b": 1}, 54,
       ["tally", "ask", "countdown"], ["gather", "mark", "weigh"],
       "vault", "#d68f4f", "fx_required_debt", "tally_burn",
       "A debt column hangs over it and shortens as demands are met.",
       ["Minimum-window problems run two ledgers: what is required, and what the "
        "window currently holds.",
        "You are done when every required count is met, not when every required key "
        "is present. Those are different conditions."]),

    # -- V. Scanning a Sequence ---------------------------------------------
    _E("left", "LEFT, Warden of the Low End", "index", "scanning", "TWO_POINTER", 0, 50,
       ["advance", "converge", "indexbook"], ["mark", "tally", "gather"],
       "warden", "#c4553f", "fx_left_step", "converge",
       "It advances a single pace and plants itself. It never turns back.",
       ["The left edge only ever moves forward. That monotonicity is why the whole "
        "scan is O(n) and not O(n squared).",
        "Moving it inside a `while` is shrinking. Moving it inside the `for` is a "
        "different algorithm entirely."]),
    _E("right", "RIGHT, Warden of the High End", "index", "scanning", "TWO_POINTER",
       5, 50,
       ["converge", "reach", "advance"], ["mark", "tally", "gather"],
       "warden", "#a4453f", "fx_right_step", "converge",
       "It steps inward from the far edge, mirroring its twin.",
       ["On a sorted array, too large a sum means move RIGHT inward; too small means "
        "move LEFT inward. Nothing else is needed.",
        "Start it at `len(nums) - 1`, not `len(nums)`. The second one raises on the "
        "first read."]),
    _E("best", "BEST, the High-Water Mark", "int", "scanning", "SLIDING_WINDOW", 0, 48,
       ["span", "bind", "probe"], ["advance", "gather", "mark"],
       "ledgerling", "#d6a84f", "fx_best_crest", "count_up",
       "A tide line that only ever rises up its body, never falls.",
       ["A maximum is kept with `max`, not with `+= 1`. Incrementing a high-water "
        "mark is not maximising, it is counting.",
        "Window width is `right - left + 1`. The +1 is because both ends are "
        "inclusive, and forgetting it is the most common single error in this "
        "chapter."]),
    _E("running", "RUNNING, the Prefix Tide", "int", "scanning", "PREFIX_SUM", 0, 46,
       ["inhale", "toll", "advance"], ["mark", "gather", "weigh"],
       "ledgerling", "#9c8f4f", "fx_running_tide", "count_up",
       "A waterline creeps up it and holds at each new sum.",
       ["A running sum carries forward. Recomputing the prefix inside the loop turns "
        "one pass into n passes.",
        "A range sum is then `prefix[j] - prefix[i - 1]`, and the whole difficulty is "
        "in that `- 1`."]),
    _E("start", "START, the Anchor", "index", "scanning", "SLIDING_WINDOW", 0, 44,
       ["indexbook", "advance", "bind"], ["gather", "mark", "sink"],
       "warden", "#bf7f4f", "fx_start_anchor", "converge",
       "It drags forward in one jump rather than a series of shuffles.",
       ["When you know where the offender last appeared, jump the left edge past it "
        "in one move instead of crawling.",
        "`start = max(start, seen[ch] + 1)`. Without the `max`, an old sighting drags "
        "the window backwards and the scan stops being monotone."]),
    _E("seen_at", "SEEN_AT, the Last-Index Ledger", "dict", "scanning", "HASH_MAP",
       {}, 52,
       ["inscribe", "indexbook", "ask"], ["tally", "mark", "gather"],
       "vault", "#e8a33d", "fx_seen_at_pin", "vault_open",
       "Pins drop onto a ruler behind it, each one replacing the last.",
       ["Storing the index instead of a boolean is what lets the window jump rather "
        "than shrink one step at a time.",
        "Overwrite freely here: the LAST sighting is the one that matters."]),
    _E("inside", "INSIDE, the Window Ledger", "dict", "scanning", "SLIDING_WINDOW",
       {}, 54,
       ["tally", "countdown", "shrink"], ["mark", "gather", "weigh"],
       "marshling", "#7f9a5a", "fx_inside_ledger", "frame_slide",
       "Its ledger brightens on the right edge and dims on the left, in step.",
       ["Every element entering the window increments; every element leaving "
        "decrements. Those two lines are the window.",
        "Delete the key when its count hits zero, or `len(inside)` counts things "
        "that are no longer there."]),
    _E("prefix", "PREFIX, the Ledger of Sums", "list", "scanning", "PREFIX_SUM",
       [0], 50,
       ["prefix", "toll", "gather"], ["mark", "inscribe", "guard"],
       "ledgerling", "#9c8f4f", "fx_prefix_ledger", "chain_link",
       "Each rung of it lights carrying the weight of every rung below.",
       ["Seeding with a leading zero removes the special case for ranges that start "
        "at index 0. Do it every time.",
        "Prefix sums buy you O(1) range queries after one O(n) pass. You are trading "
        "memory for time, on purpose."]),

    # -- VI. Order and Structure --------------------------------------------
    _E("stack", "STACK, the Cart Tower", "list", "order", "STACK", [], 56,
       ["gather", "draw", "peek", "sentinel"], ["dequeue", "mark", "weigh"],
       "imp", "#b0763f", "fx_stack_topple", "chain_link",
       "Carts slam onto the top and are wrenched off the top. Only the top.",
       ["Last in, first out. `append` and `pop` with no argument are both O(1) and "
        "both work on the same end.",
        "`pop(0)` takes from the wrong end AND costs O(n) because everything shifts. "
        "If you want that end, you wanted a deque.",
        "Peeking an empty stack raises. Check `if stack:` first — that check is half "
        "of every matching-brackets solution."]),
    _E("queue", "QUEUE, the Lift Line", "deque", "order", "QUEUE",
       {"@": "deque", "items": ["a", "b"]}, 54,
       ["enqueue", "dequeue", "gather"], ["draw", "reach", "weigh"],
       "linewraith", "#3f7f9c", "fx_queue_advance", "chain_link",
       "The line shuffles forward one place; the front dissolves.",
       ["First in, first out. Push right with `append`, take left with `popleft`.",
        "Swap `popleft` for `pop` and your breadth-first search silently becomes "
        "depth-first. It still runs. It still returns an answer. The answer is "
        "wrong."]),
    _E("heap", "HEAP, the Pile Keeper", "heap", "order", "HEAP",
       {"@": "heap", "items": [5, 1, 8]}, 58,
       ["sink", "surface", "peek"], ["reach", "weigh", "guard"],
       "keeper", "#d68f4f", "fx_heap_sift", "sort_cascade",
       "The pile reshuffles itself from the inside; only the crown is ever clear.",
       ["A heap is not sorted. Only `heap[0]` is guaranteed, and that guarantee is "
        "the whole point.",
        "Push and pop cost O(log n), which is how top-k beats sorting when k is much "
        "smaller than n.",
        "Python's heapq is a min-heap. For a max-heap, push the negatives and negate "
        "on the way out."]),
    _E("lo", "LO, the Lower Bound", "index", "order", "BINARY_SEARCH", 0, 46,
       ["halve", "bind", "narrow"], ["advance", "mark", "gather"],
       "halfling", "#5a9cd6", "fx_lo_close", "halving",
       "It jumps half the remaining distance, never a single pace.",
       ["`lo = mid + 1`, not `lo += 1`. Creeping one at a time is a linear search "
        "wearing a binary search's clothes.",
        "The `+ 1` is what guarantees termination. Without it the range stops "
        "shrinking and you hang."]),
    _E("hi", "HI, the Upper Bound", "index", "order", "BINARY_SEARCH", 7, 46,
       ["halve", "bind", "probe"], ["advance", "mark", "gather"],
       "halfling", "#4a8cc6", "fx_hi_close", "halving",
       "It falls inward in halves and stops dead where its twin meets it.",
       ["Whether you initialise to `len(nums) - 1` or `len(nums)` decides whether the "
        "loop is `<=` or `<`. Choose one convention and keep it for life.",
        "Mixing the two conventions inside one function is where binary search goes "
        "to die."]),
    _E("mid", "MID, the Midpoint Shade", "index", "order", "BINARY_SEARCH", 0, 44,
       ["halve", "reach", "probe"], ["advance", "mark", "tally"],
       "halfling", "#7fa8d6", "fx_mid_split", "halving",
       "It appears exactly between the two wardens and vanishes when they meet.",
       ["`(lo + hi) // 2` — floor division, or you index with a float and it raises.",
        "Recomputing `mid` every pass is not optional. Computing it once above the "
        "loop is an infinite loop with extra steps."]),
    _E("intervals", "INTERVALS, the Overlapping Host", "list", "order", "INTERVALS",
       [[1, 3], [2, 6], [8, 10]], 58,
       ["weigh", "greatest", "march"], ["mark", "tally", "halve"],
       "overlapper", "#5f9fbf", "fx_intervals_merge", "sort_cascade",
       "Overlapping bars slide together and fuse into one longer bar.",
       ["Sort by start first. Almost every interval problem is trivial afterwards and "
        "impossible before.",
        "Two intervals overlap when the next start is at or before the current end. "
        "Whether 'at' counts is a question you ask out loud in an interview."]),
    _E("merged", "MERGED, the Fused Span", "list", "order", "INTERVALS", [], 50,
       ["gather", "greatest", "peek"], ["mark", "inscribe", "sink"],
       "overlapper", "#5f9fbf", "fx_merged_weld", "sort_cascade",
       "A weld-line runs along it where two spans became one.",
       ["You either extend the last span you kept or you append a new one. There is "
        "no third case.",
        "Extending means `max` of the two ends, because a short interval can sit "
        "entirely inside a long one."]),

    # -- VII. Things That Contain Themselves --------------------------------
    _E("node", "NODE, the Branching Warden", "node", "recursion", "TREE",
       {"@": "tree", "layout": [5, 3, 8, 1, 4, None, 9]}, 56,
       ["branch", "pluck", "bind"], ["reach", "mark", "weigh"],
       "drake", "#3f9c5a", "fx_node_fork", "unwind",
       "It forks into two smaller copies of itself and draws them back in.",
       ["A node is a value and two references. `node[0]` raises; it is not a "
        "sequence.",
        "`if node is None` is the base case, and it goes first. Writing the recursive "
        "call before the base case is how you meet RecursionError."]),
    _E("root", "ROOT, the Canopy Crown", "node", "recursion", "TREE",
       {"@": "tree", "layout": [1, 2, 3, 4, 5]}, 58,
       ["branch", "pluck", "bind"], ["reach", "mark", "weigh"],
       "drake", "#2f8c4a", "fx_root_crown", "unwind",
       "The whole canopy flexes when it is struck, down to the last leaf.",
       ["Trust the recursive call to be correct for the subtree, then say what you do "
        "with its answer. That sentence is the whole technique.",
        "A node with one child is not a leaf. Nearly every path-sum bug is that "
        "sentence, ignored."]),
    _E("depth", "DEPTH, the Stack Depth", "int", "recursion", "RECURSION", 0, 46,
       ["unfold", "floor", "advance", "bind"], ["mark", "gather", "weigh"],
       "mirrorspawn", "#8f6ad6", "fx_depth_stack", "unwind",
       "Copies of it recede into the distance and return one at a time.",
       ["Height is `1 + max(left, right)`. The 1 is this node; the max is the "
        "deeper child.",
        "Python's recursion limit is about a thousand frames. A linked list of ten "
        "thousand nodes will hit it, and that is a real answer to give out loud."]),
    _E("path", "PATH, the Breadcrumb Trail", "list", "recursion", "DFS", [], 52,
       ["gather", "draw", "march"], ["mark", "inscribe", "weigh"],
       "deepcrawler", "#4f8f5a", "fx_path_trail", "unwind",
       "A trail lights behind it and goes dark again as it withdraws.",
       ["Append on the way in, pop on the way out. Forget the pop and every branch "
        "inherits the last branch's trail.",
        "A set cannot hold a path, because the order IS the answer.",
        "Append `list(path)` to your results, not `path` — otherwise you store a "
        "reference to something you are about to mutate."]),
    _E("order", "ORDER, the Visit Record", "list", "recursion", "TREE", [], 48,
       ["gather", "march"], ["mark", "tally", "sink"],
       "sorter", "#6a9c8f", "fx_order_record", "chain_link",
       "Glyphs are struck into it in the exact order the nodes were touched.",
       ["Pre-order, in-order and post-order differ only in WHERE you put the visit "
        "line. Everything else is identical.",
        "In-order on a binary search tree comes out sorted. That single fact answers "
        "a surprising number of questions."]),
    _E("subtree", "SUBTREE, the Smaller Copy", "node", "recursion", "RECURSION",
       {"@": "tree", "layout": [3, 1, 4]}, 50,
       ["pluck", "branch", "bind"], ["reach", "gather", "halve"],
       "mirrorspawn", "#8f6ad6", "fx_subtree_nest", "unwind",
       "Inside it stands a smaller version of the same fight, already in progress.",
       ["Each call must make the problem strictly smaller, or you are not recursing, "
        "you are looping without a plan.",
        "The subtree does not need to know it is a subtree. That ignorance is what "
        "makes the code short."]),

    # -- VIII. Maps and Mazes ------------------------------------------------
    _E("grid", "GRID, the Wasted Lattice", "matrix", "traversal", "MATRIX",
       [[1, 0, 1], [0, 1, 0], [1, 1, 1]], 60,
       ["cell", "bounds", "expand"], ["reach", "mark", "sink"],
       "lattice", "#8a8f9c", "fx_grid_lattice", "flood",
       "Rows and columns ignite in sequence; the whole floor plan can turn at once.",
       ["`grid[r]` is a row. `grid[r][c]` is a cell. Confusing those two is most of "
        "chapter eight.",
        "`rows = len(grid)` and `cols = len(grid[0])`, and the second one raises on "
        "an empty grid. Guard it.",
        "Negative indices do not raise, they wrap around to the far side. That is "
        "why the lower bound check matters as much as the upper."]),
    _E("visited", "VISITED, the Ash Ward", "set", "traversal", "SET", set(), 54,
       ["mark", "guard"], ["tally", "inscribe", "reach"],
       "wisp", "#9b96b8", "fx_visited_ash", "collapse",
       "Ground it has touched turns to ash and will not take a print twice.",
       ["Mark a cell visited when you ENQUEUE it, not when you dequeue it. Otherwise "
        "the same cell enters the queue many times and your BFS degrades.",
        "A tuple `(r, c)` is hashable and can go in a set. A list cannot."]),
    _E("frontier", "FRONTIER, the Ring of Light", "deque", "traversal", "BFS",
       {"@": "deque", "items": [[0, 0]]}, 58,
       ["gather", "dequeue", "measure"], ["draw", "reach", "weigh"],
       "wave", "#4fb7d6", "fx_frontier_ring", "flood",
       "A ring of light expands outward one even step at a time.",
       ["BFS expands in rings, so the first time it reaches a cell it reached it by "
        "the shortest road. DFS makes no such promise.",
        "Processing the queue one full level at a time is how you know WHICH ring you "
        "are on, which is how you get the distance."]),
    _E("adj", "ADJ, the Road Ledger", "dict", "traversal", "GRAPH",
       {"@": "defaultdict", "factory": "list", "items": {}}, 56,
       ["settle", "ask", "rollcall"], ["mark", "gather", "halve"],
       "cartgoblin", "#6a4f8f", "fx_adj_roads", "flood",
       "Roads draw themselves between its joints as the ledger is written.",
       ["An adjacency list is a dict from node to a list of neighbours. Build it once, "
        "before you search.",
        "For an undirected edge you append in both directions. Forgetting the second "
        "one gives you a graph that works in one direction and is very hard to see."]),
    _E("row", "ROW, the Northing", "index", "traversal", "MATRIX", 0, 42,
       ["expand", "bounds", "advance"], ["mark", "tally", "sink"],
       "lattice", "#8a8f9c", "fx_row_scan", "flood",
       "A horizontal sweep line runs the width of the arena.",
       ["Row is the first index because a matrix is a list OF rows. `grid[row][col]`, "
        "in that order, always.",
        "`dr, dc` deltas keep the four directions in one place instead of four "
        "copy-pasted blocks."]),
    _E("col", "COL, the Easting", "index", "traversal", "MATRIX", 0, 42,
       ["expand", "bounds", "advance"], ["mark", "tally", "sink"],
       "lattice", "#7a7f8c", "fx_col_scan", "flood",
       "A vertical sweep line crosses the first at the cell under attack.",
       ["Columns are the inner index. To walk a column you need both loops; there is "
        "no `grid[:][c]` that does what you hope.",
        "`zip(*grid)` transposes, and is the shortest honest answer when someone asks "
        "for columns."]),
    _E("indeg", "INDEG, the Debt Counter", "dict", "traversal", "GRAPH",
       {"b": 1, "c": 2}, 52,
       ["tally", "countdown", "ask"], ["mark", "gather", "halve"],
       "ledger", "#9c8f4f", "fx_indeg_debt", "tally_burn",
       "Arrows pin it in place and fall away one by one as debts are cleared.",
       ["Topological order starts from every node with indegree zero. Find them "
        "first, then peel.",
        "If the queue empties before every node is out, there was a cycle. That check "
        "is the cycle detection — you do not need a separate pass."]),

    # -- IX. Paying Once -----------------------------------------------------
    _E("memo", "MEMO, the Paid-Once Relic", "dict", "optimisation", "DP", {}, 58,
       ["consult", "enshrine", "ask"], ["mark", "gather", "weigh"],
       "echoling", "#d6a84f", "fx_memo_recall", "table_light",
       "Struck once it flares; struck the same way again it simply returns the flare.",
       ["Check the memo before the work and write to it after. Two lines wrapped "
        "around a function you already had.",
        "That is the entire difference between the exponential fibonacci and the "
        "linear one. Say it that plainly in an interview."]),
    _E("dp", "DP, the Lit Table", "list", "optimisation", "DP",
       [1, 1, 0, 0, 0], 60,
       ["table", "transition", "reach"], ["mark", "gather", "guard"],
       "echoling", "#d6a84f", "fx_dp_table", "table_light",
       "Tiles light one after another and never go dark again.",
       ["Bottom-up fills the table in an order that guarantees the values it reads "
        "are already correct. Getting that order right IS the problem.",
        "Seed the base cases before the loop. `dp[0]` and `dp[1]` set by hand is not "
        "cheating, it is the definition."]),
    _E("prev", "PREV, the Rolling Twin", "int", "optimisation", "DP", 0, 46,
       ["swap", "bind", "advance"], ["gather", "mark", "inscribe"],
       "mirrorspawn", "#a8863f", "fx_prev_roll", "table_light",
       "It hands its value sideways and takes its twin's in the same motion.",
       ["When the recurrence only looks back two steps, the table is waste. Two "
        "variables do it in O(1) space.",
        "`prev, cur = cur, prev + cur` — the right-hand side is evaluated fully "
        "before anything is assigned, which is why this works at all."]),
    _E("cur", "CUR, the Rolling Twin", "int", "optimisation", "DP", 1, 46,
       ["swap", "bind", "advance"], ["gather", "mark", "inscribe"],
       "mirrorspawn", "#c8a64f", "fx_cur_roll", "table_light",
       "The mirror of its twin, one step further along and one step brighter.",
       ["Assigning these one at a time destroys the old value before the other line "
        "needs it. The tuple form is not style, it is correctness.",
        "Name them for what they hold, not `a` and `b`. You will read this again in "
        "twenty minutes."]),
    _E("cost", "COST, the Toll Ledger", "int", "optimisation", "DP", 0, 50,
       ["least", "choose", "toll"], ["advance", "mark", "gather"],
       "ledger", "#9c8f4f", "fx_cost_toll", "table_light",
       "A toll figure hangs over it and only ever revises downward.",
       ["Minimising keeps `min`, maximising keeps `max`, and mixing them up produces "
        "code that runs and answers the opposite question.",
        "Seed a minimum with infinity, not with zero. Zero is already smaller than "
        "every real cost you will find."]),

    # -- X. The Working Engineer --------------------------------------------
    _E("nums", "NUMS, the Unchecked Argument", "list", "craft", "DEBUGGING",
       [4, 2, 9], 54,
       ["sentinel", "measure", "sever"], ["reach", "mark", "sink"],
       "bugling", "#c43f4f", "fx_nums_empty", "shatter",
       "It thins to nothing and the blow that was aimed at it lands on the floor.",
       ["The empty list is the test you will be given and the one you will forget. "
        "Handle it in line one.",
        "`if not nums` covers None-ish emptiness and reads better than "
        "`len(nums) == 0`.",
        "If the caller still owns the list, do not sort it in place. Sort a copy or "
        "say clearly that you are mutating."]),
    _E("off_by_one", "OFF_BY_ONE, the Fencepost", "int", "craft", "DEBUGGING", 1, 52,
       ["narrow", "bounds", "probe"], ["advance", "mark", "gather"],
       "beetle", "#c43f4f", "fx_offbyone_slip", "shatter",
       "It stands exactly one pace from where you aimed, every time.",
       ["Ten fenceposts hold nine panels. Inclusive and exclusive ends differ by one "
        "and the difference is invisible until it is a bug.",
        "When you cannot see it, print the boundary values for n = 0, 1 and 2. The "
        "bug is always at one of them."]),
    _E("cache", "CACHE, the Shared Default", "dict", "craft", "DEBUGGING", {}, 50,
       ["sever", "sentinel", "consult"], ["bind", "mark", "advance"],
       "mimic", "#d6c04f", "fx_cache_haunt", "shatter",
       "It wears the shape of the last thing that touched it, and remembers.",
       ["A mutable default argument is created once, at definition, and shared by "
        "every call for the life of the program.",
        "`def f(seen=None):` then `if seen is None: seen = set()`. That is the fix, "
        "and it is the same four words every time."]),
    _E("expected", "EXPECTED, the Assertion Wraith", "int", "craft", "TESTING", 0, 48,
       ["witness", "probe", "bind"], ["guard", "mark", "gather"],
       "mimic", "#d6c04f", "fx_expected_verdict", "seal",
       "It holds up the answer you claimed and the answer you produced, side by side.",
       ["A test you can run beats a belief you hold. Write the assertion before you "
        "trust the function.",
        "Empty, one element, all identical, already sorted, reversed. Five cases, and "
        "naming them out loud is most of the testing signal an interviewer wants."]),

    # -- XI. Under Pressure --------------------------------------------------
    _E("answer", "ANSWER, the Unnamed Thing", "none", "gauntlet", "RECALL",
       {"@": "none"}, 56,
       ["bind", "sentinel", "gather"], ["mark", "tally", "sink"],
       "riddler", "#d8d8e0", "fx_answer_unmask", "seal",
       "Nothing about it says which structure it wants. That is the fight.",
       ["Nothing here is labelled. Deciding WHICH idiom applies is the skill being "
        "measured, and it is a different skill from executing it.",
        "`None` is not zero and not empty. `if answer is None` and `if not answer` "
        "are different questions."]),
    _E("k", "K, the Unspoken Limit", "int", "gauntlet", "RECALL", 3, 44,
       ["bind", "probe", "least"], ["mark", "gather", "weigh"],
       "riddler", "#c8c8d0", "fx_k_limit", "seal",
       "A bound hangs over the arena and is never stated aloud.",
       ["When k equals one, or equals n, or exceeds n, does your code still answer? "
        "Those three are free test cases and you are given them every time.",
        "Top-k with a heap is O(n log k). Sorting is O(n log n). When k is small, say "
        "which one you chose and why."]),
)

ENEMY_BY_ID: dict = {e.id: e for e in ENEMIES}
ENEMY_BY_NAME: dict = ENEMY_BY_ID          # the id IS the variable name


def enemies_for_chapter(chapter_id: str) -> list:
    return [e for e in ENEMIES if e.chapter == chapter_id]


def enemies_of_type(type_name: str) -> list:
    return [e for e in ENEMIES if e.type == type_name]


# ---------------------------------------------------------------------------
# Effects — what a successful cast LOOKS like against this particular enemy
# ---------------------------------------------------------------------------
# Requirement from the brief: a cast animates differently depending on what you
# hit. Every enemy therefore owns a unique effect id. To keep that from being
# seventy separate drawing jobs, each effect declares a FAMILY: the technique.
# Fourteen families to implement, seventy tints and beats on top of them.
#
# Three effects are global rather than per-enemy:
#   fx_resist   the wasted turn. Dull, brief, unmistakable. Never humiliating.
#   fx_glance   a correctly-typed incantation aimed at the wrong enemy.
#   *_crit      any enemy effect with "_crit" appended is its SIGNATURE variant:
#               same drawing, more of it.

EFFECT_FAMILIES: dict = {
    "count_up":     "Numerals climb and stay lit. For ints that only ever grow.",
    "collapse":     "Duplicates fold into one another and vanish. For sets.",
    "tally_burn":   "Numbers brand onto the body and tick upward. For counting dicts.",
    "vault_open":   "One keyed door of many swings open. For mapping dicts.",
    "chain_link":   "Elements light in sequence, end to end. For lists and strings.",
    "frame_slide":  "A bright rectangle slides and resizes. For windows.",
    "converge":     "Two lights step toward each other. For pointer pairs.",
    "halving":      "The remaining span is visibly cut in half. For binary search.",
    "unwind":       "A spiral descends, then returns carrying something. "
                    "For recursion.",
    "flood":        "Rings of light spread outward across a surface. "
                    "For grids and graphs.",
    "table_light":  "Tiles light in order and never go dark. For DP.",
    "sort_cascade": "Pieces fall into order and lock. For sorting, heaps, intervals.",
    "seal":         "Something closes, or refuses to open. "
                    "For immutables and booleans.",
    "shatter":      "A hairline crack opens where the defect is. For bugs.",
}

RESIST_EFFECT = "fx_resist"
GLANCE_EFFECT = "fx_glance"


def _build_effects() -> dict:
    out = {
        RESIST_EFFECT: {
            "family": "seal", "label": "Resisted",
            "note": "Short, dull, grey. The turn is gone and nothing else is. Do "
                    "not make this feel like a punishment; it is the mechanic.",
        },
        GLANCE_EFFECT: {
            "family": "seal", "label": "Glancing",
            "note": "Valid Python, wrong target. A scuff and a small number.",
        },
    }
    for enemy in ENEMIES:
        out[enemy.effect] = {
            "family": enemy.effect_family,
            "label": enemy.title.split(",")[0].title(),
            "enemy": enemy.id,
            "colour": enemy.colour,
            "note": enemy.effect_note,
        }
        out[enemy.effect + "_crit"] = {
            "family": enemy.effect_family,
            "label": enemy.title.split(",")[0].title() + " (signature)",
            "enemy": enemy.id,
            "colour": enemy.colour,
            "note": "The signature cast. Same drawing as " + enemy.effect
                    + ", held longer and brighter.",
        }
    return out


EFFECTS: dict = _build_effects()


# ---------------------------------------------------------------------------
# Encounters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Encounter:
    id: str
    title: str
    chapter: str
    region: str
    blurb: str
    enemies: tuple                # enemy ids, in the order they stand
    hp: dict                      # enemy id -> HP for THIS fight
    demands: tuple                # incantation ids this fight is here to rehearse
    lesson: str                   # what discriminating between these teaches

    def total_hp(self) -> int:
        return sum(self.hp.get(e, ENEMY_BY_ID[e].hp) for e in self.enemies)

    def enemy_list(self) -> list:
        return [ENEMY_BY_ID[e] for e in self.enemies]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "chapter": self.chapter,
            "region": self.region, "blurb": self.blurb, "lesson": self.lesson,
            "demands": list(self.demands),
            "casts": cast_budget(self),
            "enemies": [dict(e.to_dict(), hp=self.hp.get(e.id, e.hp))
                        for e in self.enemy_list()],
        }


def _C(id, title, chapter, region, blurb, hp, demands, lesson):
    return Encounter(id=id, title=title, chapter=chapter, region=region,
                     blurb=blurb, enemies=tuple(hp.keys()), hp=dict(hp),
                     demands=tuple(demands), lesson=lesson)


ENCOUNTERS: tuple = (
    # -- I. The Language Itself ---------------------------------------------
    _C("enc_first_loop", "The First Loop", "fluency", "python_village",
       "A horde stands in a line and a ledger floats above it, waiting.",
       {"items": 70, "total": 70},
       ["toll", "advance", "reach"],
       "Walk the collection, add to the accumulator. Two different names, two "
       "different spells, and the ledger is not a list."),
    _C("enc_wandering_index", "The Wandering Index", "fluency", "python_village",
       "An index hops along a ruler while the horde it points at shifts.",
       {"i": 50, "items": 55, "result": 55},
       ["advance", "reach", "gather"],
       "The index is not the element. `i` moves, `items[i]` is read, and `result` "
       "is written — three names doing three jobs in one line of code."),
    _C("enc_sigils_sentence", "Two Sigils and a Sentence", "fluency",
       "fields_of_syntax",
       "Two bound sigils and a long sentence, guarded by a truth warden.",
       {"name": 40, "text": 50, "flag": 40, "count": 45},
       ["bind", "reach", "measure", "probe"],
       "Strings are rebound, never edited; a bool is not a counter. Four enemies, "
       "four different wrong instincts."),

    # -- II. The Four Vaults -------------------------------------------------
    _C("enc_hollow_set", "The Hollow Set", "structures", "python_village",
       "A hollow set drifts over the horde, swallowing repeats.",
       {"seen": 80, "items": 70},
       ["guard", "mark", "gather"],
       "Ask the set first, then tell it. Guard then mark, in that order, forever."),
    _C("enc_vault_and_hoard", "Vault and Hoard", "structures", "python_village",
       "A keyed vault and a swollen hoard, with a set watching both.",
       {"lookup": 60, "bag": 50, "seen": 55},
       ["ask", "inscribe", "guard", "gather"],
       "Three containers, three costs. Membership in the set is one step; in the "
       "hoard it is a walk. Same question, different price."),
    _C("enc_absent_key", "The Absent Key", "structures", "hashmap_highlands",
       "A door with nothing behind it, a store, and something sealed shut.",
       {"missing": 55, "stock": 60, "frozen": 50},
       ["ask", "inscribe", "reach", "guard"],
       "`d[k]` raises, `d.get(k, 0)` does not, and the tuple refuses both. Pick the "
       "read that matches whether absence is a bug."),

    # -- III. The Idioms -----------------------------------------------------
    _C("enc_tally_wraith", "The Tally Wraith", "idiom", "fields_of_syntax",
       "A wraith made of numerals, and beside it the set that cannot count.",
       {"counts": 85, "seen": 70},
       ["tally", "guard", "mark", "ask"],
       "The headline discrimination of the whole game: 'have I seen it' is a set, "
       "'how many times' is a dict. They stand side by side so you must choose."),
    _C("enc_choir_and_ledger", "Choir and Ledger", "idiom", "fields_of_syntax",
       "A choir that groups by key, an enumerated row, and an oracle of positions.",
       {"groups": 60, "line": 60, "index_of": 50},
       ["settle", "numbering", "inscribe", "reach"],
       "Append into a group, store a position, read an element. Three subscripts "
       "that are not the same subscript."),
    _C("enc_braids_blooms", "Braids and Blooms", "idiom", "fields_of_syntax",
       "Two strands braiding, a bloom of squares, an enumerated row and a wraith.",
       {"pairs": 45, "squares": 45, "line": 45, "counts": 50},
       ["pairing", "mirror", "numbering", "tally"],
       "Four idioms that each replace four lines of C-flavoured Python. Knowing "
       "which one the shape calls for is the entire lesson."),

    # -- IV. Counting and Membership ----------------------------------------
    _C("enc_two_that_sum", "Two That Sum", "counting", "hashmap_highlands",
       "A sum waits. Its complement circles. A set keeps the record.",
       {"target": 60, "need": 55, "seen": 55},
       ["complement", "guard", "mark"],
       "Compute the complement, then ask the ledger, then write yourself in. Reverse "
       "any two of those and you pair a number with itself."),
    _C("enc_anagram_grove", "The Anagram Grove", "counting", "stringwood_labyrinth",
       "Signatures settle into order and figures stream into alcoves.",
       {"buckets": 60, "letters": 55, "counts": 55},
       ["weigh", "settle", "tally"],
       "Two correct answers stand together: sort the letters, or count them. Both "
       "canonicalise; they cost different amounts and you should say which."),
    _C("enc_first_sighting", "First Sighting", "counting", "hashmap_highlands",
       "A stamped ledger, a pair of echoes, and an oracle that names positions.",
       {"first_seen": 60, "dupes": 55, "index_of": 50},
       ["inscribe", "guard", "numbering"],
       "Recording the FIRST sighting needs a guard; recording the LAST needs none. "
       "The bug is always in which one you meant."),
    _C("enc_demand_ledger", "The Demand Ledger", "counting", "hashmap_highlands",
       "A debt column hangs in the air over a sum and its echoes.",
       {"required": 60, "dupes": 55, "target": 55},
       ["tally", "ask", "guard", "complement"],
       "Counts you must meet versus keys you must have. Those are different "
       "conditions and minimum-window lives on the difference."),

    # -- V. Scanning a Sequence ---------------------------------------------
    _C("enc_twin_wardens", "Twin Wardens", "scanning", "twin_pointer_pass",
       "Two wardens hold either end of the bridge and step inward together.",
       {"left": 60, "right": 60, "items": 50},
       ["converge", "advance", "reach", "indexbook"],
       "The same `+= 1` that grows a total moves the low warden, and its mirror "
       "moves the high one. One spell, two intents."),
    _C("enc_creeping_frame", "The Creeping Frame", "scanning",
       "sliding_window_marsh",
       "A frame slides across the reeds, its ledger brightening and dimming.",
       {"window": 55, "inside": 60, "best": 55},
       ["frame", "tally", "countdown", "span"],
       "Enter and increment on the right, leave and decrement on the left. The "
       "high-water mark is kept with max, never with an increment."),
    _C("enc_jump_dont_crawl", "Jump, Do Not Crawl", "scanning",
       "sliding_window_marsh",
       "A ledger of pins, an anchor that lurches forward, and a tide line.",
       {"seen_at": 55, "start": 55, "best": 55},
       ["inscribe", "indexbook", "span"],
       "Storing the last index lets the left edge jump past the offender in one "
       "move. Storing a boolean forces it to crawl."),
    _C("enc_prefix_tide", "The Prefix Tide", "scanning", "array_caverns",
       "A ledger of sums, each rung carrying the weight of all below it.",
       {"prefix": 60, "running": 55, "i": 50},
       ["toll", "gather", "reach", "advance"],
       "Carry the sum forward or rebuild it every pass. One is O(n), the other is "
       "O(n squared), and they look nearly identical on the page."),

    # -- VI. Order and Structure --------------------------------------------
    _C("enc_cart_tower", "The Cart Tower", "order", "stack_queue_mines",
       "Carts stacked to the ceiling. Only the top one will move.",
       {"stack": 65, "items": 50, "i": 45},
       ["gather", "draw", "peek"],
       "Push and pop work the same end. Reaching for the other end is a different "
       "data structure and an order of magnitude."),
    _C("enc_lift_and_tower", "Lift and Tower", "order", "stack_queue_mines",
       "A lift line and a cart tower, working opposite ends of the same problem.",
       {"queue": 60, "stack": 60, "result": 50},
       ["dequeue", "draw", "gather"],
       "`popleft` or `pop` — one letter apart, and the difference between breadth "
       "first and depth first. This fight makes you pick under pressure."),
    _C("enc_halving_wardens", "The Halving Wardens", "order", "array_caverns",
       "Two bounds and the shade that stands exactly between them.",
       {"lo": 50, "hi": 50, "mid": 45, "items": 40},
       ["halve", "narrow", "probe"],
       "`lo = mid + 1` terminates; `lo += 1` is a linear search in disguise. The "
       "wardens resist the creep specifically so you feel it."),
    _C("enc_overlapping_host", "The Overlapping Host", "order", "array_caverns",
       "Bars of light overlap, slide together, and weld.",
       {"intervals": 65, "merged": 60, "best": 50},
       ["weigh", "greatest", "gather", "span"],
       "Sort by start, then extend or append. Two branches and no third case, once "
       "the sort has happened."),
    _C("enc_pile_keeper", "The Pile Keeper", "order", "stack_queue_mines",
       "A pile that reshuffles from the inside; only its crown is ever clear.",
       {"heap": 65, "counts": 55, "best": 50},
       ["sink", "surface", "tally"],
       "Count first, then heap the counts. Top-k is two structures cooperating, and "
       "the heap is useless without the tally that feeds it."),

    # -- VII. Things That Contain Themselves --------------------------------
    _C("enc_branching_warden", "The Branching Warden", "recursion",
       "recursive_forest",
       "It forks into two smaller copies of itself and draws them back in.",
       {"node": 85, "depth": 70},
       ["floor", "branch", "unfold"],
       "Base case, recursive call, combine. Always in that order, and the combine "
       "is the only part that is actually about your problem."),
    _C("enc_trail_and_canopy", "Trail and Canopy", "recursion",
       "binary_tree_canopy",
       "A crown of branches, a breadcrumb trail, and a record of every touch.",
       {"root": 65, "path": 55, "order": 55},
       ["branch", "gather", "draw"],
       "Append on the way in, pop on the way out, and record where the traversal "
       "order demands. Three appends, three different positions in the function."),
    _C("enc_smaller_copy", "The Smaller Copy", "recursion", "recursive_forest",
       "Inside the clearing stands a smaller copy of the same clearing.",
       {"subtree": 60, "node": 60, "depth": 50},
       ["unfold", "floor", "pluck"],
       "Every call must shrink the problem. The fight is winnable only if each cast "
       "makes the thing in front of you smaller than it was."),

    # -- VIII. Maps and Mazes ------------------------------------------------
    _C("enc_ash_ward", "The Ash Ward", "traversal", "graph_wastes",
       "A lattice of ground, a ring of light, and ash where the light has been.",
       {"grid": 65, "visited": 55, "frontier": 60},
       ["cell", "mark", "guard", "dequeue"],
       "Mark visited when you enqueue, not when you dequeue. The difference is "
       "invisible in the answer and enormous in the running time."),
    _C("enc_northing_easting", "Northing and Easting", "traversal",
       "matrix_citadel",
       "Two sweep lines cross at the cell under attack.",
       {"row": 50, "col": 50, "grid": 70},
       ["expand", "bounds", "cell"],
       "Row then column, and the bound check before the index. Negative indices do "
       "not raise; they quietly read the far side of the grid."),
    _C("enc_road_ledger", "The Road Ledger", "traversal", "graph_wastes",
       "Roads draw themselves between ruins as the ledger is written.",
       {"adj": 60, "visited": 55, "indeg": 60},
       ["settle", "tally", "countdown", "guard"],
       "Build the adjacency once, count the debts once, then peel. Three phases "
       "that people try to do in one loop and cannot."),

    # -- IX. Paying Once -----------------------------------------------------
    _C("enc_paid_once", "The Paid-Once Relic", "optimisation", "dp_ruins",
       "Struck the same way twice, it simply returns the first flare.",
       {"memo": 85, "depth": 70},
       ["consult", "enshrine", "unfold"],
       "Check before the work, write after it. Two lines around a function you "
       "already had, and exponential becomes linear."),
    _C("enc_lit_table", "The Lit Table", "optimisation", "dp_ruins",
       "Tiles light one after another and never go dark again.",
       {"dp": 65, "cost": 60, "i": 50},
       ["table", "least", "reach"],
       "Bottom-up needs an order in which every value it reads is already correct. "
       "Finding that order is the problem; the assignment is not."),
    _C("enc_rolling_twins", "Rolling Twins", "optimisation", "dp_ruins",
       "Two shades hand their values sideways in the same motion.",
       {"prev": 60, "cur": 60, "dp": 55},
       ["swap", "bind", "advance"],
       "When the recurrence only looks back twice, the table is waste. Two names "
       "and one tuple assignment do it in constant space."),

    # -- X. The Working Engineer --------------------------------------------
    _C("enc_unchecked_argument", "The Unchecked Argument", "craft",
       "debugging_dungeon",
       "It thins to nothing and the blow aimed at it lands on the floor.",
       {"nums": 70, "off_by_one": 60, "hi": 45},
       ["sentinel", "measure", "narrow"],
       "Empty input and the boundary. The two tests you will be handed and the two "
       "you will not have written."),
    _C("enc_shared_default", "The Shared Default", "craft", "debugging_dungeon",
       "Something wearing the shape of the last thing that touched it.",
       {"cache": 60, "expected": 55, "nums": 60},
       ["sever", "sentinel", "witness"],
       "A mutable default is created once and shared forever. State the "
       "expectation as an assertion rather than believing you are fine."),
    _C("enc_fencepost_cells", "Fencepost Cells", "craft", "debugging_dungeon",
       "A fencepost stands one pace from where you aimed. Twice.",
       {"off_by_one": 60, "lo": 55, "hi": 55},
       ["narrow", "bounds", "halve"],
       "Inclusive or exclusive, `<` or `<=`. Pick a convention, hold it across the "
       "whole function, and the class of bug disappears."),

    # -- XI. Under Pressure --------------------------------------------------
    _C("enc_nothing_labelled", "Nothing Is Labelled", "gauntlet",
       "coding_coliseum",
       "No signposts. Three shapes, and no hint which spell any of them wants.",
       {"answer": 65, "k": 50, "seen": 55},
       ["bind", "guard", "probe", "sentinel"],
       "Recognition under load. The incantations are all ones you know; nothing "
       "tells you which one applies, which is the only part being measured."),
    _C("enc_unsignposted_room", "The Unsignposted Room", "gauntlet",
       "null_kings_castle",
       "A wraith of numerals, two wardens, and a thing with no name at all.",
       {"answer": 50, "counts": 45, "left": 45, "right": 45},
       ["tally", "converge", "advance", "reach"],
       "Counting and scanning in the same fight, unlabelled. Interleaving at full "
       "strength: four enemies, four idioms, no signposts."),
    _C("enc_under_the_clock", "Under the Clock", "gauntlet", "coding_coliseum",
       "A sand floor, a clock, and four things that each want something different.",
       {"k": 45, "heap": 50, "best": 45, "memo": 45},
       ["sink", "surface", "span", "consult"],
       "Everything at once, on a timer, with nothing labelled. This is the shape of "
       "the interview, and the only new difficulty is the clock."),
)

ENCOUNTER_BY_ID: dict = {e.id: e for e in ENCOUNTERS}


def encounters_for_chapter(chapter_id: str) -> list:
    return [e for e in ENCOUNTERS if e.chapter == chapter_id]


def encounters_for_region(region_id: str) -> list:
    return [e for e in ENCOUNTERS if e.region == region_id]


# ---------------------------------------------------------------------------
# Bosses
# ---------------------------------------------------------------------------
# Each boss is one construct with several faces. A phase change swaps which
# enemies stand and therefore which incantation is demanded, so a single fight
# rehearses an entire idiom sequence in the order a real solution would use it.
# That sequencing is the pedagogy: the phases ARE the algorithm, walked through
# one line at a time.
#
# `id` matches world.BOSSES where a sensible mapping exists, so the existing boss
# rooms can host these fights without a second registry.

@dataclass(frozen=True)
class BossPhase:
    key: str
    label: str
    enemies: tuple
    demands: tuple
    hp: dict
    line: str                 # what the boss says as the phase opens
    teaches: str

    def total_hp(self) -> int:
        return sum(self.hp.get(e, ENEMY_BY_ID[e].hp) for e in self.enemies)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label, "line": self.line,
            "teaches": self.teaches, "demands": list(self.demands),
            "hp_total": self.total_hp(),
            "enemies": [dict(ENEMY_BY_ID[e].to_dict(),
                             hp=self.hp.get(e, ENEMY_BY_ID[e].hp))
                        for e in self.enemies],
        }


@dataclass(frozen=True)
class Boss:
    id: str                   # matches world.BOSSES id where one exists
    name: str
    form: str                 # the variable this boss IS
    chapter: str
    region: str
    skill: str
    colour: str
    sprite: str
    premise: str
    phases: tuple

    def total_hp(self) -> int:
        return sum(p.total_hp() for p in self.phases)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "form": self.form,
            "chapter": self.chapter, "region": self.region, "skill": self.skill,
            "colour": self.colour, "sprite": self.sprite, "premise": self.premise,
            "hp_total": self.total_hp(),
            "casts": cast_budget(self),
            "phases": [p.to_dict() for p in self.phases],
        }


def _P(key, label, hp, demands, line, teaches):
    return BossPhase(key=key, label=label, enemies=tuple(hp.keys()),
                     demands=tuple(demands), hp=dict(hp), line=line,
                     teaches=teaches)


BOSSES: tuple = (
    Boss("hash_titan", "The Hash Titan", "counts", "counting",
         "hashmap_highlands", "HASH_MAP", "#e8a33d", "titan",
         "It is a dict the size of a hill. Every phase is a different question "
         "asked of the same mapping, and only one of them is answered by a set.",
         (
             _P("membership", "Have you seen it", {"seen": 60},
                ["guard", "mark"],
                "Compare every scroll against every other. I will wait.",
                "Membership in O(1). Guard, then mark, and never the reverse."),
             _P("counting", "How many times", {"counts": 60},
                ["tally", "ask"],
                "A set answered the first question. It cannot answer this one.",
                "The moment multiplicity matters, the set is the wrong vault."),
             _P("grouping", "Which of them belong together", {"buckets": 60},
                ["settle", "weigh"],
                "Group them. Without sorting all of them.",
                "Canonical form as a key. Anagram grouping in two lines."),
             _P("complement", "What is still missing", {"target": 35, "need": 35},
                ["complement", "guard", "bind"],
                "One number is absent. Name it before you look for it.",
                "Compute the complement, then query the ledger, then write."),
         )),
    Boss("three_sum_hydra", "The Three-Sum Hydra", "left", "scanning",
         "array_caverns", "TWO_POINTER", "#4fb783", "hydra",
         "For every duplicate you fail to skip, it grows another head. The fight "
         "is a sort, a converge, a dedupe and a collection, in that order.",
         (
             _P("order", "Put them in order first", {"items": 35, "i": 35},
                ["reach", "advance"],
                "Unsorted, I have infinite heads. Sorted, I have three.",
                "Sorting is not the answer; it is what makes the answer possible."),
             _P("converge", "Close from both ends", {"left": 35, "right": 35},
                ["converge", "advance", "reach"],
                "Move the wrong warden. Please.",
                "Too large, move the high end in. Too small, move the low end up."),
             _P("dedupe", "Skip what you have already answered",
                {"dupes": 35, "seen": 35},
                ["guard", "mark"],
                "You found that triple twice. I counted.",
                "Skipping equal neighbours is what keeps the output a set of "
                "answers rather than a bag of repeats."),
             _P("collect", "Say what you found", {"result": 60},
                ["gather", "bind"],
                "Now hand it to me in the shape I asked for.",
                "Returning the right shape is part of being correct."),
         )),
    Boss("window_wraith", "The Window Wraith", "window", "scanning",
         "sliding_window_marsh", "SLIDING_WINDOW", "#7f6ad6", "wraith",
         "It feeds on restarts. Four phases: widen, record, shrink, measure — "
         "which is the sliding window written out as a fight.",
         (
             _P("widen", "Expand to the right", {"right": 35, "window": 35},
                ["advance", "frame"],
                "Restart your scan. I feed on restarts.",
                "The right edge only ever moves forward."),
             _P("ledger", "Record what is inside", {"inside": 60},
                ["tally", "countdown"],
                "You cannot shrink what you have not been counting.",
                "The window's contents are a dict, maintained incrementally."),
             _P("shrink", "Contract from the left", {"left": 35, "inside": 35},
                ["shrink", "advance", "countdown"],
                "The ward is broken. Fix it without starting again.",
                "While the window is illegal, drop from the left. A `while`, not "
                "an `if` — one drop may not be enough."),
             _P("crest", "Keep the best you saw", {"best": 60},
                ["span"],
                "You held the answer for one iteration and let it go.",
                "`right - left + 1`, kept with max. The +1 is inclusive width."),
         )),
    Boss("twin_behemoth", "The Twin Pointer Behemoth", "right", "scanning",
         "twin_pointer_pass", "TWO_POINTER", "#c4553f", "behemoth",
         "Two wardens and a width. Every phase asks which end to sacrifice.",
         (
             _P("span", "Measure the span", {"left": 35, "right": 35},
                ["converge", "advance"],
                "The widest span is the first one you see. It is rarely the best.",
                "Start at the extremes; width only ever decreases from here."),
             _P("measure", "Price what you are holding", {"best": 60},
                ["span", "probe"],
                "You measured. You did not remember.",
                "Keeping a maximum is a line of its own, every iteration."),
             _P("decide", "Sacrifice the right one", {"right": 40, "left": 30},
                ["converge", "reach"],
                "Move the taller wall. Go on. Lose the width for nothing.",
                "Moving the taller side can never help; the height is capped by "
                "the shorter one either way."),
             _P("prove", "Say why it terminates", {"best": 35, "items": 35},
                ["span", "reach"],
                "Convince me this halts.",
                "One pointer moves every iteration, so the loop is O(n). Say that "
                "sentence out loud in an interview."),
         )),
    Boss("matrix_golem", "The Matrix Golem", "grid", "traversal",
         "matrix_citadel", "MATRIX", "#8a8f9c", "golem",
         "A fortress of rows and columns that can be turned whole. The phases "
         "walk the in-place rotation, one motion at a time.",
         (
             _P("read", "Find a single cell", {"grid": 30, "row": 25, "col": 25},
                ["cell", "bounds"],
                "Allocate a second matrix. I will simply take it from you.",
                "Row first, column second, bound check before either."),
             _P("transpose", "Turn it on its diagonal", {"row": 35, "col": 35},
                ["expand", "advance"],
                "Swap across the diagonal. Only once each, or you undo yourself.",
                "Transposing swaps (r, c) with (c, r) for r < c only."),
             _P("reverse", "Reverse each row", {"grid": 35, "items": 35},
                ["cell", "reach"],
                "Half turned is not turned.",
                "Transpose then reverse each row is a ninety degree rotation. "
                "Knowing the decomposition IS the solution."),
             _P("in_place", "Use no second fortress", {"grid": 60},
                ["cell", "bounds"],
                "Now do it again in the space you were given.",
                "In place means O(1) extra space, and that constraint is usually "
                "what the question is actually about."),
         )),
    Boss("tree_dragon", "The Tree Dragon", "root", "recursion",
         "binary_tree_canopy", "TREE", "#3f9c5a", "dragon",
         "It dares you to compare it only to its children. The phases build the "
         "bounds argument that a local comparison cannot.",
         (
             _P("base", "Say where it stops", {"node": 35, "depth": 25},
                ["floor", "branch"],
                "Compare me only to my children. I dare you.",
                "The base case comes first, always, and `None` is valid."),
             _P("descend", "Trust the smaller call", {"node": 35, "subtree": 35},
                ["branch", "pluck"],
                "You recursed. You did not say what you would do with the answer.",
                "Assume the recursive call is correct for the subtree."),
             _P("bounds", "Carry the bounds down", {"lo": 35, "hi": 35},
                ["bind", "probe", "halve"],
                "Local order is not global order. Look further than one step.",
                "A BST is valid only against an inherited range, not against a "
                "parent. That is the entire trick."),
             _P("combine", "Fold the answers", {"root": 35, "depth": 35},
                ["unfold"],
                "Both halves are correct. Now make one answer out of them.",
                "The combine line is the only part specific to your problem."),
         )),
    Boss("path_sum_ent", "The Path-Sum Ent", "path", "recursion",
         "binary_tree_canopy", "TREE", "#6b8f3f", "ent",
         "It insists that a node with one child is not a leaf, and it is right.",
         (
             _P("trail", "Lay the trail", {"path": 60},
                ["gather", "draw"],
                "You walked in. You did not walk out.",
                "Append on the way in, pop on the way out. Backtracking is those "
                "two lines and nothing else."),
             _P("leaf", "Define a leaf", {"node": 35, "depth": 25},
                ["branch", "floor"],
                "A node with one child is not a leaf, little architect.",
                "A leaf has no left AND no right. One of the two is not enough."),
             _P("remain", "Track what is left to spend",
                {"total": 35, "target": 35},
                ["toll", "complement"],
                "Subtract as you descend, or add as you descend. Not both.",
                "Either accumulate toward the target or decrement the remainder. "
                "Mixing the two is the bug."),
             _P("record", "Copy before you store", {"result": 35, "path": 35},
                ["gather", "mirror"],
                "You stored the trail. Then you changed it.",
                "Append `list(path)`, not `path`, or every stored answer is the "
                "same mutating list."),
         )),
    Boss("graph_necromancer", "The Graph Necromancer", "frontier", "traversal",
         "graph_wastes", "BFS", "#6a4f8f", "necromancer",
         "It offers you the scenic route. The phases are BFS, assembled from "
         "parts, in the order the parts are needed.",
         (
             _P("build", "Draw the roads first", {"adj": 60},
                ["settle", "ask"],
                "Depth-first, was it? Enjoy the scenic route.",
                "Build the adjacency list before you search, not during."),
             _P("seed", "Light the first ring", {"frontier": 35, "visited": 35},
                ["gather", "mark"],
                "Mark it now. Not when you get around to it.",
                "Mark visited on enqueue. On dequeue, the same cell has already "
                "entered the queue five times."),
             _P("ring", "Expand evenly", {"frontier": 35, "visited": 35},
                ["dequeue", "guard"],
                "Take from the end and watch your shortest path evaporate.",
                "`popleft` is breadth. `pop` is depth. One letter, different "
                "algorithm, no error message."),
             _P("distance", "Count the rings", {"depth": 35, "best": 35},
                ["advance", "span"],
                "You arrived. You cannot tell me how far it was.",
                "Process a whole level at a time and the level number is the "
                "distance."),
         )),
    Boss("rolling_titan", "The Rolling Titan", "window", "order",
         "sliding_window_marsh", "QUEUE", "#3f7f9c", "titan",
         "It has all day and you have three seconds. The phases build the "
         "monotonic deque that replaces calling max in a loop.",
         (
             _P("enter", "Let the next one in", {"window": 60},
                ["frame"],
                "Call max() again. I have all day.",
                "Recomputing the maximum per window is O(n k). There is an O(n)."),
             _P("evict_front", "Drop what has left the window",
                {"window": 35, "left": 35},
                ["evict", "advance"],
                "That index is behind you. Why is it still in your hand?",
                "The front is evicted by INDEX, not by value."),
             _P("evict_back", "Drop what can never win",
                {"window": 40, "items": 30},
                ["draw", "reach"],
                "It is smaller than the one that just arrived. It will never win.",
                "Popping smaller values off the back is what keeps the deque "
                "monotonic, and monotone is what makes the front the answer."),
             _P("report", "Read the front", {"result": 35, "window": 35},
                ["gather", "peek"],
                "Now tell me the maximum without looking at the rest.",
                "The front of a monotonic deque is the window maximum, in O(1)."),
         )),
    Boss("editor_automaton", "The Editor Automaton", "stack", "craft",
         "matrix_citadel", "DESIGN", "#b0763f", "automaton",
         "It demands the undo you did not implement. The phases are a design "
         "interview conducted entirely in stack operations.",
         (
             _P("apply", "Apply an edit", {"stack": 35, "text": 35},
                ["gather", "bind"],
                "Undo that. No — the other undo. The one you did not implement.",
                "Every operation you might undo has to be recorded as you do it."),
             _P("undo", "Take back the last one", {"stack": 60},
                ["draw", "peek"],
                "The LAST one. Not the first.",
                "Undo is a stack because recency is the ordering that matters."),
             _P("redo", "Put it back", {"stack": 35, "result": 35},
                ["gather", "draw"],
                "Two stacks, or one and a great deal of regret.",
                "Redo is the undo stack's mirror. New edits clear it — say so "
                "before you are asked."),
             _P("guard", "Survive the empty case", {"stack": 60},
                ["sentinel", "peek"],
                "Undo on an empty document. Go.",
                "`if stack:` before every peek and pop. Half of every "
                "bracket-matching solution is that one check."),
         )),
    Boss("complexity_wyrm", "The Complexity Wyrm", "cost", "optimisation",
         "complexity_tower", "BIG_O", "#3f6f9c", "wyrm",
         "Correct is not the same as fast, and it is the difference. The phases "
         "walk one problem from brute force down to linear, out loud.",
         (
             _P("naive", "Do it the obvious way", {"items": 35, "total": 35},
                ["reach", "advance"],
                "Correct is not the same as fast. I am the difference.",
                "Write the brute force first. It is a correct baseline and an "
                "interviewer will take it over nothing."),
             _P("ledger", "Stop recomputing", {"counts": 35, "inside": 35},
                ["tally", "countdown"],
                "You counted that substring four times.",
                "A maintained ledger replaces a recount. This is where the "
                "exponent falls."),
             _P("window", "One pass, two edges",
                {"left": 30, "right": 25, "best": 25},
                ["advance", "converge", "span"],
                "Two nested loops became one. Say why.",
                "Each pointer moves at most n times, so the whole scan is O(n) "
                "even though it is written as a nested loop."),
             _P("price", "Name its cost", {"cost": 60},
                ["least", "toll"],
                "Now price it. Time and space, both, unprompted.",
                "Saying the complexity before being asked is half the score."),
         )),
    Boss("serialization_lich", "The Serialization Lich", "order", "recursion",
         "recursive_forest", "TREE", "#8f3f6f", "lich",
         "Write the tree down, then read it back, exactly. The phases separate "
         "the traversal from the format, which is the whole difficulty.",
         (
             _P("walk", "Write it down", {"node": 35, "order": 35},
                ["gather", "branch"],
                "Write the tree down. Now read it back. Exactly.",
                "Pre-order serialises cleanly because the root comes first and "
                "rebuilding can be greedy."),
             _P("nulls", "Record the absences", {"node": 35, "order": 25},
                ["branch", "gather"],
                "You wrote the nodes and not the gaps. Which tree was it?",
                "Without null markers the shape is ambiguous. The gaps carry as "
                "much information as the values."),
             _P("read_back", "Consume it in order",
                {"items": 40, "order": 30},
                ["reach", "march"],
                "You read the same token twice.",
                "Deserialisation needs a cursor that only moves forward. A shared "
                "index or an iterator, never a re-scan."),
             _P("rebuild", "Rebuild the shape", {"root": 35, "subtree": 35},
                ["branch", "pluck"],
                "Same tree. Not a tree with the same values.",
                "The recursion that writes and the recursion that reads are the "
                "same shape, run in opposite directions."),
         )),
    Boss("bug_demon", "The Bug Demon", "nums", "craft",
         "debugging_dungeon", "DEBUGGING", "#c43f4f", "demon",
         "It works on its machine. The phases are the four defects that survive "
         "every code review, in the order they are usually found.",
         (
             _P("empty", "The empty case", {"nums": 60},
                ["sentinel", "measure"],
                "It works on your machine.",
                "The empty input is the first test anyone runs and the last one "
                "anyone writes."),
             _P("fencepost", "The boundary",
                {"off_by_one": 30, "lo": 25, "hi": 25},
                ["narrow", "bounds"],
                "One pace short. Every time.",
                "`<` or `<=` at the limit. Check n = 0, 1 and 2 and the bug "
                "announces itself."),
             _P("aliasing", "The shared mutable", {"cache": 60},
                ["sever", "sentinel"],
                "You gave them a reference and called it a copy.",
                "A mutable default is created once at definition and shared by "
                "every call for the life of the process."),
             _P("prove", "Prove it is fixed", {"expected": 60},
                ["witness"],
                "You believe it is fixed. Show me.",
                "A test you can run beats a belief you hold."),
         )),
    Boss("the_interviewer", "The Interviewer", "answer", "gauntlet",
         "null_kings_castle", "RECALL", "#d8d8e0", "interviewer",
         "Nothing is labelled and nothing is offered. Six phases, mapped onto "
         "world.BOSS_PHASES, and every one of them is something you have already "
         "done in a room that told you what it was.",
         (
             _P("recognize", "Name the family", {"answer": 60},
                ["bind", "sentinel"],
                "Walk me through your approach before you write anything.",
                "Recognition is a separate skill from execution, and it is the "
                "one that fails first under pressure."),
             _P("explain", "State your approach", {"answer": 35, "k": 35},
                ["probe", "bind"],
                "Say it in two sentences. Then write it.",
                "If you cannot say the approach out loud, the code will not "
                "rescue you."),
             _P("implement", "Cast the spell",
                {"counts": 25, "seen": 20, "left": 20, "right": 20},
                ["tally", "guard", "advance", "converge"],
                "Four of them. Different spells. No labels.",
                "Interleaved retrieval with no cue. This is the measurement."),
             _P("edges", "Survive the hidden trials",
                {"nums": 30, "off_by_one": 25, "hi": 25},
                ["sentinel", "narrow"],
                "Empty. One element. All identical. Go.",
                "Naming the edge cases unprompted is a large part of the signal."),
             _P("complexity", "Name its cost", {"cost": 35, "k": 35},
                ["least", "probe"],
                "Time and space. Before I ask.",
                "Saying the cost unprompted is the difference between a pass and "
                "a strong pass."),
             _P("variant", "The disguised rematch",
                {"answer": 30, "memo": 25, "best": 25},
                ["consult", "enshrine", "span"],
                "Same problem. Different clothes. Again.",
                "Retention is proven on a disguised variant days later, which is "
                "exactly what the SRS is scheduling."),
         )),
)

BOSS_BY_ID: dict = {b.id: b for b in BOSSES}


def bosses_for_region(region_id: str) -> list:
    return [b for b in BOSSES if b.region == region_id]


# ---------------------------------------------------------------------------
# THE BATTLE CONTEXT
# ---------------------------------------------------------------------------
# This is the live Python namespace a battle runs against, and it is the seam
# between this module and gauntlet/incantation.py. The contract, precisely:
#
#   build_context(target) -> dict[str, object]
#
# A PLAIN DICT of name -> value. No dataclasses, no wrappers, no dunder keys.
# Every value is freshly materialised, so mutating it is safe and two battles
# never share a list. Keys arrive in four layers, later layers winning:
#
#   1. HELPERS   names the templates mention literally: deque, defaultdict,
#                Counter, heapq, Node. A template that says
#                `heapq.heappush({heap}, {item})` needs `heapq` to be a name.
#   2. AMBIENT   the INPUTS and the LOOP VARIABLES: nums, words, word, s, t, ch,
#                x, i, j, n, key, value, target, k, limit, grid, rows, cols,
#                node, root, out, seq, pos. Fresh copies every call.
#   3. ENEMIES   one key per enemy standing in this fight — its name bound to
#                its materialised value. Overrides ambient where they collide,
#                which is deliberate: when TARGET is on the field, `target` is
#                TARGET.
#   4. extras    whatever the caller passes, winning over everything.
#
# AMBIENT DELIBERATELY DOES NOT SUPPLY CONTAINERS. `nums` and `grid` are there
# because they are the inputs; `seen`, `counts`, `stack` and the rest are not,
# because a container you are asked to mutate has to be standing in front of you.
# Casting `seen.add(ch)` in a fight with no SEEN raises NameError, and that is
# the correct lesson: you cannot hit what is not there.
#
# HOW A CAST IS EXECUTED
#   ctx = bestiary.battle_context(encounter)      # -> incantation.BattleContext
#   result = incantation.cast(move_id, answers, ctx)
#
# Player text is NEVER executed in this process. incantation.check_semantics()
# assembles the whole battle — setup lines, the cast, the proof — into one
# program and hands it to gauntlet.sandbox, which runs it in a separate
# interpreter under a seatbelt profile, rlimits and a wall clock. That is the
# only place player text runs, and the only place it may ever run.
#
# In particular: do NOT exec() a cast against build_globals() in-process. A
# builtins whitelist is not a sandbox — `().__class__.__bases__[0].__subclasses__()`
# walks straight out of one to the filesystem, and no amount of pruning
# SAFE_BUILTINS closes that door. SAFE_BUILTINS below exists so the NAMES the
# templates use resolve when this module builds a preview value; it is a
# convenience, not a security boundary, and it is not a place to run a cast.
#
# Many incantations are FRAGMENTS — `if {item} not in {store}:` is not a complete
# statement. Completing them (appending a body, wrapping them) is incantation.py's
# job; this module only supplies the namespace.

SAFE_BUILTINS: dict = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "divmod": divmod, "enumerate": enumerate, "filter": filter, "float": float,
    "frozenset": frozenset, "int": int, "isinstance": isinstance, "len": len,
    "list": list, "map": map, "max": max, "min": min, "range": range,
    "repr": repr, "reversed": reversed, "round": round, "set": set,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "True": True, "False": False, "None": None,
}

HELPERS: dict = {
    "deque": deque,
    "defaultdict": defaultdict,
    "Counter": Counter,
    "heapq": heapq,
    "Node": Node,
}

# Inputs and loop variables only. See the note above about containers.
AMBIENT: dict = {
    "nums": [2, 7, 11, 15],
    "seq": [3, 1, 4, 1, 5],
    "words": ["eat", "tea", "tan", "ate"],
    "word": "listen",
    "s": "mississippi",
    "t": "abc",
    "ch": "s",
    "key": "a",
    "value": 1,
    "x": 7,
    "i": 0,
    "j": 1,
    "n": 4,
    "pos": 0,
    "target": 9,
    "k": 3,
    "limit": 3,
    "rows": 3,
    "cols": 3,
    "grid": [[1, 1, 0], [0, 1, 0], [0, 1, 1]],
    "node": {"@": "tree", "layout": [5, 3, 8, 1, 4, None, 9]},
    "root": {"@": "tree", "layout": [5, 3, 8, 1, 4, None, 9]},
    "out": [],
}

AMBIENT_NOTES: dict = {
    "nums": "the array you were handed",
    "seq": "a second sequence, when a problem needs two",
    "words": "a list of words, for grouping and signatures",
    "word": "one word",
    "s": "a string with repeats in it",
    "t": "the pattern or the second string",
    "ch": "the character the loop is currently holding",
    "key": "the key the loop is currently holding",
    "value": "the value the loop is currently holding",
    "x": "the element the loop is currently holding",
    "i": "an index",
    "j": "a second index",
    "n": "the length you measured",
    "pos": "a position you recorded",
    "target": "the number you are looking for",
    "k": "the limit the question gave you",
    "limit": "an alias for k, when the problem calls it that",
    "rows": "grid height",
    "cols": "grid width",
    "grid": "the matrix you were handed",
    "node": "the node the traversal is currently at",
    "root": "the top of the tree",
    "out": "somewhere to put an answer when no RESULT is on the field",
}


def _enemy_ids(target) -> list:
    """Accepts an Encounter, a BossPhase, a Boss, an Enemy, an id, or any
    iterable of those. Returns enemy ids in field order, without duplicates."""
    if target is None:
        return []
    if isinstance(target, Enemy):
        return [target.id]
    if isinstance(target, (Encounter, BossPhase)):
        return list(target.enemies)
    if isinstance(target, Boss):
        seen_ids, out = set(), []
        for phase in target.phases:
            for eid in phase.enemies:
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    out.append(eid)
        return out
    if isinstance(target, str):
        if target in ENCOUNTER_BY_ID:
            return list(ENCOUNTER_BY_ID[target].enemies)
        if target in BOSS_BY_ID:
            return _enemy_ids(BOSS_BY_ID[target])
        return [target]
    out, seen_ids = [], set()
    for item in target:
        for eid in _enemy_ids(item):
            if eid not in seen_ids:
                seen_ids.add(eid)
                out.append(eid)
    return out


def build_context(target, *, extras: dict | None = None,
                  include_ambient: bool = True) -> dict:
    """The live namespace for one battle. See the contract note above.

    `target` may be an Encounter, a Boss, a BossPhase, an Enemy, any of their
    ids, or an iterable mixing them. Unknown enemy ids are skipped rather than
    raising — a battle should not fail to start because a roster entry was
    renamed.
    """
    ctx: dict = dict(HELPERS)
    if include_ambient:
        for name, spec in AMBIENT.items():
            ctx[name] = materialise(spec)
    for eid in _enemy_ids(target):
        enemy = ENEMY_BY_ID.get(eid)
        if enemy is not None:
            ctx[enemy.name] = enemy.fresh_value()
    if extras:
        ctx.update(extras)
    return ctx


def build_globals(ctx: dict) -> dict:
    """The same dict with SAFE_BUILTINS installed, for evaluating THIS module's
    own authored values — never for running player text.

    A cast goes through incantation.cast(), which runs it in gauntlet.sandbox in
    a separate interpreter. SAFE_BUILTINS is a name table, not a jail: a
    whitelist of builtins does not contain attribute traversal, so anything that
    exec'd a player line against this mapping in-process would be handing out the
    interpreter. Build the namespace here; run it over there.
    """
    ctx["__builtins__"] = SAFE_BUILTINS
    return ctx


def context_summary(target, ctx: dict | None = None) -> list:
    """One row per name for the battle sidebar, enemies first.

    The player is reading this while typing, so it is `name`, `type`, and a
    short value — never a wrapped repr.
    """
    ids = _enemy_ids(target)
    ctx = ctx if ctx is not None else build_context(target)
    rows = []
    for eid in ids:
        enemy = ENEMY_BY_ID.get(eid)
        if enemy is None:
            continue
        rows.append({
            "name": enemy.name, "kind": "enemy", "type": enemy.type,
            "value": value_sketch(enemy.value), "title": enemy.title,
            "colour": enemy.colour,
        })
    for name, spec in AMBIENT.items():
        if name in ids:
            continue
        value = ctx.get(name, materialise(spec))
        rows.append({
            "name": name, "kind": "ambient",
            "type": type(value).__name__,
            "value": value_sketch(spec), "title": AMBIENT_NOTES.get(name, ""),
            "colour": "#6f7488",
        })
    return rows


# ---------------------------------------------------------------------------
# The engine bridge
# ---------------------------------------------------------------------------
# build_context() above is the LIVE namespace: name -> a real Python object, for
# anything that wants to look at a battle. The incantation engine needs the other
# half of the same truth — name -> the SOURCE that creates it — because it does
# not evaluate a cast here, it writes the whole battle out as a program and runs
# it in the sandbox. battle_context() is that translation, and it is the only
# seam between this module's content and that module's mechanics.
#
# Direction of dependency: content knows about the engine, never the reverse.
# incantation.py must stay bestiary-agnostic so it can be self-tested on its own
# practice fields, which is why the import below is local and defensive.

KIND_FOR_TYPE: dict = {
    "set": "set", "dict": "dict", "list": "list", "int": "int", "str": "str",
    "deque": "deque", "heap": "heap", "matrix": "grid",
    # An index IS an int; the roster names it separately only so the sidebar can
    # say what it is FOR. The engine gates incantations on the type, not the job.
    "index": "int",
    "node": "node", "tuple": "tuple", "bool": "bool", "none": "none",
}

# A tree node rendered as source. Deliberately name-mangled: an incantation may
# bring its own `Node` along in its imports, and whichever lands last would
# otherwise silently replace the class these builders close over.
NODE_PREAMBLE: tuple = (
    "class __Node__:",
    "    __slots__ = ('val', 'left', 'right', 'next')",
    "    def __init__(self, val=0, left=None, right=None, next=None):",
    "        self.val, self.left, self.right, self.next = val, left, right, next",
    "def __tree__(layout):",
    "    if not layout or layout[0] is None: return None",
    "    nodes = [None if v is None else __Node__(v) for v in layout]",
    "    kids = iter(nodes[1:])",
    "    for nd in nodes:",
    "        if nd is None: continue",
    "        nd.left = next(kids, None); nd.right = next(kids, None)",
    "    return nodes[0]",
    "def __chain__(values):",
    "    head = None",
    "    for v in reversed(values): head = __Node__(v, next=head)",
    "    return head",
)

# The recursive call, stubbed. RECURSE and DESCEND both need a function name to
# hand the smaller problem to, and the point of those idioms is that you trust
# the call rather than trace it — so the battle binds one that answers without
# being written. Without this they are moves that cannot be cast at all.
BATTLE_FUNCTIONS: dict = {"solve": "lambda _smaller: 0"}


def value_source(spec) -> str:
    """The source EXPRESSION that rebuilds a roster value.

    value_sketch() renders a value for a human and elides anything long;
    this has to round-trip, so it never abbreviates.
    """
    if isinstance(spec, dict) and "@" in spec:
        kind = spec["@"]
        if kind == "deque":
            items = list(spec.get("items", []))
            maxlen = spec.get("maxlen")
            return ("deque(%r, maxlen=%r)" % (items, maxlen) if maxlen
                    else "deque(%r)" % (items,))
        if kind == "defaultdict":
            return "defaultdict(%s, %r)" % (spec.get("factory", "list"),
                                            dict(spec.get("items", {})))
        if kind == "counter":
            return "Counter(%r)" % (dict(spec.get("items", {})),)
        if kind == "heap":
            return repr(materialise(spec))      # heapified: a plain list again
        if kind == "tree":
            return "__tree__(%r)" % (list(spec.get("layout", [])),)
        if kind == "chain":
            return "__chain__(%r)" % (list(spec.get("items", [])),)
        if kind == "none":
            return "None"
        raise ValueError(f"unknown value spec: {kind}")
    return repr(spec)


def _preamble(sources) -> tuple:
    """Top-level lines a set of source expressions needs before they will run."""
    text = " ".join(sources)
    lines: list = []
    for needle, statement in (("deque(", "from collections import deque"),
                              ("defaultdict(", "from collections import defaultdict"),
                              ("Counter(", "from collections import Counter")):
        if needle in text:
            lines.append(statement)
    if "__tree__(" in text or "__chain__(" in text:
        lines.extend(NODE_PREAMBLE)
    return tuple(lines)


def _families(ids) -> list:
    """Incantation ids -> their weakness families, in order, without duplicates."""
    live = _live_catalogue() or {}
    out: list = []
    for inc in ids:
        family = _attr(live.get(resolve_incantation(inc)), "family")
        if family and family not in out:
            out.append(str(family))
    return out


def enemy_form(enemy, hp: int | None = None):
    """One roster Enemy as the engine's Enemy.

    The two records disagree by design: this file says an enemy is weak to
    particular INCANTATIONS, the engine matches on the incantation's FAMILY.
    The signature's family is the weakness, which keeps the crit landing on the
    idiom the creature was authored for.
    """
    from . import incantation

    points = enemy.hp if hp is None else hp
    families = _families(enemy.weak_to)
    return incantation.Enemy(
        name=enemy.id,
        title=enemy.title.split(", ", 1)[-1],
        kind=KIND_FOR_TYPE.get(enemy.type, "value"),
        binding=value_source(enemy.value),
        hp=points, hp_max=points,
        weakness=(families[0] if families else ""),
        resists=tuple(_families(enemy.resists)),
        taunt=(enemy.flavour[0] if enemy.flavour else ""),
    )


def battle_context(target, *, mode: str = "adventure",
                   hp: dict | None = None, extras: dict | None = None,
                   include_ambient: bool = True):
    """The field for one fight, in the shape incantation.cast() takes.

    `target` is anything _enemy_ids() accepts. Per-fight HP comes from the
    Encounter or BossPhase when `target` is one, so a creature that is a
    warm-up in one fight and a wall in another keeps its roster identity.
    """
    ids = _enemy_ids(target)
    fight = target
    if isinstance(target, str):
        fight = ENCOUNTER_BY_ID.get(target) or BOSS_BY_ID.get(target)
    points = dict(hp or {}) or dict(getattr(fight, "hp", {}) or {})
    enemies = [enemy_form(ENEMY_BY_ID[eid], points.get(eid))
               for eid in ids if eid in ENEMY_BY_ID]

    taken = {e.name for e in enemies}
    support: dict = {}
    if include_ambient:
        # Ambient names are the supporting cast: the index, the character, the
        # target sum. An enemy standing on the field always wins the name.
        support.update({name: value_source(spec)
                        for name, spec in AMBIENT.items() if name not in taken})
    support.update({n: v for n, v in BATTLE_FUNCTIONS.items() if n not in taken})
    if extras:
        support.update(extras)

    sources = [e.binding for e in enemies] + list(support.values())
    lines = _preamble(sources)
    modules: tuple = ()
    if any(e.kind == "heap" for e in enemies):
        lines = lines + ("import heapq",)
        modules = ("heapq",)

    from . import incantation
    return incantation.BattleContext(enemies=enemies, support=support,
                                     imports=lines, modules=modules, mode=mode)


# ---------------------------------------------------------------------------
# Casting: what a correctly-typed incantation does to a particular enemy
# ---------------------------------------------------------------------------
# This function grades a WELL-FORMED cast against a TARGET. A cast that does not
# parse, or whose blanks are filled with names that are not on the field, never
# reaches here — incantation.py refuses it and the turn is spent. That is the
# Blitz rule, and it is the only punishment in the system.

BASE_DAMAGE = 10
SIGNATURE_DAMAGE = 16          # the enemy's first weakness: the idiom it exists for
GLANCE_DAMAGE = 3              # real Python, wrong enemy
RESIST_DAMAGE = 0              # the turn is spent and the enemy acts

TYPE_RESIST_NOTE: dict = {
    "set": "A set holds membership and nothing else. No counts, no order, no index.",
    "dict": "A dict holds one value per key. Anything that discards the value "
            "discards the point of it.",
    "list": "A list holds order and duplicates, and answers membership only by "
            "walking itself.",
    "tuple": "A tuple cannot be changed after it is built. That is what it is for.",
    "str": "A string cannot be edited in place. You build a new one and rebind.",
    "int": "An int is a number, not a container.",
    "bool": "A bool has two states. Doing arithmetic to it makes it an int.",
    "index": "An index is a position, not the thing at that position.",
    "deque": "A deque is O(1) at the ends and O(n) in the middle. Reaching into "
             "the middle throws away the only reason to use one.",
    "heap": "Only heap[0] is ordered. The rest of the pile is not sorted and "
            "reading it as though it were is a bug.",
    "node": "A node is a value and two references. It is not a sequence.",
    "matrix": "A matrix is a list of rows. One index gives you a row, not a cell.",
    "none": "There is nothing here yet. Bind something before you read it.",
}


def cast_outcome(enemy, incantation_id: str) -> dict:
    """Grade one well-formed cast against one enemy.

    result is one of:
      "signature"  the idiom this construct exists for. Full damage, crit effect.
      "hit"        a correct idiom for this construct. Full damage.
      "glance"     valid Python aimed at the wrong construct. A scuff.
      "resist"     the wrong tool for this construct. The turn is spent.
    """
    target = enemy if isinstance(enemy, Enemy) else ENEMY_BY_ID.get(str(enemy))
    inc = resolve_incantation(incantation_id)
    if target is None:
        return {"result": "glance", "damage": 0, "effect": GLANCE_EFFECT,
                "incantation": inc, "enemy": None,
                "reason": "Nothing by that name is on the field."}
    row = EXPECTED_INCANTATIONS.get(inc)
    gloss = row[3] if row else ""
    if inc in target.resists:
        note = TYPE_RESIST_NOTE.get(target.type, "")
        return {
            "result": "resist", "damage": RESIST_DAMAGE, "effect": RESIST_EFFECT,
            "incantation": inc, "enemy": target.id,
            "reason": f"{target.id} is a {target.type}. {note} The turn is spent.",
        }
    if inc and inc == target.signature:
        return {
            "result": "signature", "damage": SIGNATURE_DAMAGE,
            "effect": target.effect + "_crit", "incantation": inc,
            "enemy": target.id,
            "reason": f"The idiom {target.id} exists for. {gloss}",
        }
    if inc in target.weak_to:
        return {
            "result": "hit", "damage": BASE_DAMAGE, "effect": target.effect,
            "incantation": inc, "enemy": target.id, "reason": gloss,
        }
    return {
        "result": "glance", "damage": GLANCE_DAMAGE, "effect": GLANCE_EFFECT,
        "incantation": inc, "enemy": target.id,
        "reason": "Valid Python. Not what this one is made of.",
    }


def effect_for(enemy, incantation_id: str) -> str:
    return cast_outcome(enemy, incantation_id)["effect"]


def cast_budget(thing) -> dict:
    """How many casts this fight takes: `fast` if every cast is a signature hit,
    `slow` if every cast is an ordinary one. The design target for an encounter
    is 8 to 20 — long enough for repetition, short enough not to be a chore."""
    if isinstance(thing, (Encounter, BossPhase)):
        hp = thing.total_hp()
    elif isinstance(thing, Boss):
        hp = thing.total_hp()
    else:
        hp = int(thing)
    return {
        "hp": hp,
        "fast": -(-hp // SIGNATURE_DAMAGE),
        "slow": -(-hp // BASE_DAMAGE),
    }


# ---------------------------------------------------------------------------
# Vitals: hit points, focus, an element, and the specials focus buys
# ---------------------------------------------------------------------------
#
# Everything above this line describes what an enemy IS. This section describes
# what it can DO on the turns between yours, and it is deliberately the smallest
# section in the file, because none of it is allowed to matter very much.
#
# THE RULE THAT SIZES EVERY NUMBER HERE
# --------------------------------------
# The Python typing is the attack. An enemy's turn cannot take a turn away from
# the player (elements.STATUSES has no such kind and self_check proves it), it
# cannot end the fight — stamina at zero routes to a training camp, never to a
# loss — and it cannot be answered by anything except continuing to type. All
# an enemy turn does is spend the player's health bar, which is what decides
# how many potions get drunk, which is what decides how LONG the fight is.
# Longer fight, more casts, more repetition. That is the entire pedagogical
# function of an enemy having a turn at all.
#
# FOCUS IS DERIVED, NOT AUTHORED
# -------------------------------
# Forty-five enemies authored a second time is forty-five enemies that
# eventually disagree with themselves. Focus comes off HP, because HP is already
# the measure of how long a thing is meant to stand there: a bigger enemy gets
# more turns, so it gets more specials. The ratio is the only free number, and
# it is set so an ordinary enemy fires roughly one special per four turns, which
# is often enough to be a pattern and rare enough to be an event.

FOCUS_PER_HP = 0.5          # a 60 HP enemy carries 30 focus
FOCUS_REGEN = 4             # gained at the start of each of its own turns
BOSS_FOCUS_MULTIPLIER = 1.6  # bosses get more of all three, as asked
BOSS_REGEN_BONUS = 2

# The cheapest special costs this much, so an enemy cannot open a fight with
# one: it has to stand there for a turn or two first, and the player gets to
# see it charging.
MIN_SPECIAL_COST = 8


def focus_for(hp: int, *, is_boss: bool = False) -> int:
    """The focus pool for something with this much health."""
    pool = max(MIN_SPECIAL_COST, int(round(int(hp) * FOCUS_PER_HP)))
    if is_boss:
        pool = int(round(pool * BOSS_FOCUS_MULTIPLIER))
    return pool


def focus_regen(*, is_boss: bool = False) -> int:
    return FOCUS_REGEN + (BOSS_REGEN_BONUS if is_boss else 0)


@dataclass(frozen=True)
class Special:
    """One thing an enemy can do with its focus.

    `power` is a MULTIPLIER on the enemy's ordinary blow, never a number of its
    own. That is the same discipline elements.resolve_damage is built on: this
    file does not generate damage, it scales damage somebody else decided on,
    and a caller who passes zero gets zero.
    """
    id: str
    name: str
    element: str            # the element this special belongs to
    cost: int               # focus spent
    power: float            # multiplier on the enemy's basic blow
    inflicts: str           # an elements.STATUSES id, or "" for none
    line: str               # what the combat log says, "{who}" for the name
    why: str                # for the codex, and for whoever tunes this


# One special per element plus one for neutral ground, which is the same shape
# as elements.HAZARD_BY_ELEMENT and for the same reason: derive the enemy's
# repertoire from the ground it is standing on and there is nothing extra to
# author per monster. A neutral region still gets one, because an enemy that
# could never do anything would make five of the seventeen regions feel broken
# rather than calm.
#
# Every `inflicts` is the status its own element already owns in
# elements.STATUSES. A special that inflicted somebody else's status would be a
# second, private opinion about what fire does.
SPECIALS: tuple = (
    Special("scorch", "Scorch", "FIRE", 10, 1.4, "BURNING",
            "{who} opens its mouth and the air goes dry.",
            "Fire is a burst. It hurts now and it is over."),
    Special("rime", "Rime", "COLD", 9, 1.1, "CHILLED",
            "{who} breathes, and the cold gets into your hands.",
            "Cold makes the fight longer rather than more dangerous, which is "
            "the trade this whole system is built to make."),
    Special("spore_burst", "Spore Burst", "POISON", 10, 1.0, "POISONED",
            "{who} splits something open and the air thickens.",
            "The one status with a dedicated cure, so the one that makes the "
            "antidote in the pouch worth carrying."),
    Special("sunder", "Sunder", "BRUTE", 12, 1.5, "STAGGERED",
            "{who} puts its whole weight behind one blow.",
            "The counter to armour points is not a better element; it is "
            "something heavy enough to make the plate irrelevant."),
    Special("arc", "Arc", "LIGHTNING", 11, 1.2, "SHOCKED",
            "{who} earths itself through you.",
            "Lightning does not do the damage. It makes whatever comes next "
            "do more."),
    Special("unmake", "Unmake", "VOID", 12, 1.3, "VOIDED",
            "{who} takes the light out of the room a piece at a time.",
            "It stops focus coming back. It never stops focus being spent, "
            "because a status that locked the hint tree could strand a learner."),
    Special("press", "Press", "", 8, 1.35, "",
            "{who} presses, and does not stop pressing.",
            "Neutral ground has no weather, so its special is simply a harder "
            "swing. Nothing to read and nothing to counter — which is what "
            "makes the elemental regions feel like somewhere."),
)

SPECIAL_BY_ID: dict = {s.id: s for s in SPECIALS}
SPECIAL_BY_ELEMENT: dict = {s.element: s.id for s in SPECIALS}
NEUTRAL_SPECIAL = "press"


def specials_for(element: str = "", *, is_boss: bool = False) -> list:
    """What an enemy standing on this ground can do.

    An ordinary enemy knows its region's special and nothing else. A boss knows
    that one AND the plain one, which is the "bosses get more of all three"
    clause: more health, more focus, and more than one thing to spend it on.
    """
    own = SPECIAL_BY_ELEMENT.get(str(element or ""), "")
    out = [own] if own else []
    if is_boss and NEUTRAL_SPECIAL not in out:
        out.append(NEUTRAL_SPECIAL)
    return out or [NEUTRAL_SPECIAL]


def vitals(*, hp: int, element: str = "", is_boss: bool = False,
           focus: int | None = None) -> dict:
    """Everything the turn loop needs about one combatant, as plain JSON.

    Plain JSON because it lives in the save file, and a save that cannot hold
    a fight in progress is a save that loses a twenty-turn fight to a page
    refresh. `element` is handed IN rather than derived here — the caller knows
    which region this is, and this module does not form a second opinion about
    the wheel any more than it forms one about the seal.
    """
    hp = max(1, int(hp))
    # `focus` is an override for callers whose `hp` is not a health pool. The
    # problem encounter's enemy carries one point of HP per hidden test, which
    # is a count of edge cases wearing a health bar — deriving focus off it
    # would give a three-test problem a monster that can never afford anything
    # it knows how to do, which is worse than a monster with no specials at all.
    pool = focus_for(hp, is_boss=is_boss) if focus is None else max(
        MIN_SPECIAL_COST, int(focus))
    return {
        "hp": hp, "hp_max": hp,
        "focus": 0, "focus_max": pool,
        "regen": focus_regen(is_boss=is_boss),
        "element": str(element or ""),
        "specials": specials_for(element, is_boss=is_boss),
        "statuses": [],
        "antidotes": 0,
        "boss": bool(is_boss),
    }


def affordable(vital: dict) -> list:
    """The specials this enemy could pay for right now, dearest first.

    Dearest first because an enemy that saved up should spend it on the thing it
    saved up FOR. An enemy that always fired the cheapest thing available would
    never show the player its expensive one.
    """
    focus = int((vital or {}).get("focus", 0) or 0)
    rows = [SPECIAL_BY_ID[sid] for sid in (vital or {}).get("specials", ())
            if sid in SPECIAL_BY_ID]
    return sorted([s for s in rows if s.cost <= focus],
                  key=lambda s: -s.cost)


# Two turns in three, once it can afford anything at all. High enough that
# saving up visibly pays off, low enough that the fight is not a drum machine.
SPECIAL_CHANCE = 0.65


def take_turn(vital: dict, *, roll: float = 1.0) -> dict | None:
    """Spend focus on a special, or don't. Mutates `vital`'s focus.

    Returns the Special as a dict, or None for an ordinary blow. `roll` comes in
    rather than being drawn here for the same reason it does in
    elements.resolve_damage: a pure function is one a test can pin down and a
    preview can call twice.

    An enemy that CAN fire does not always fire. Always-fire would make the
    special a metronome, and a metronome is something the player stops reading.
    """
    options = affordable(vital)
    if not options:
        return None
    if roll > SPECIAL_CHANCE:
        return None
    chosen = options[0]
    vital["focus"] = max(0, int(vital.get("focus", 0)) - chosen.cost)
    return {"id": chosen.id, "name": chosen.name, "element": chosen.element,
            "cost": chosen.cost, "power": chosen.power,
            "inflicts": chosen.inflicts, "line": chosen.line}



def regenerate(vital: dict) -> int:
    """Focus at the start of this enemy's turn. Returns what it gained."""
    before = int(vital.get("focus", 0) or 0)
    cap = int(vital.get("focus_max", 0) or 0)
    after = min(cap, before + int(vital.get("regen", FOCUS_REGEN) or 0))
    vital["focus"] = after
    return after - before

# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------
# Four invariants, and every one of them is something that would reach the
# player as a broken fight rather than an exception:
#
#   1. Every enemy name is a valid Python identifier, is not a keyword, and does
#      not shadow a helper or a builtin the templates rely on.
#   2. Every incantation id this file references exists. Checked against this
#      module's own contract always, and against incantation.CATALOGUE when that
#      module is present.
#   3. Every encounter is winnable with the moveset its chapter has actually
#      taught: every enemy on the field has at least one weakness the player
#      could be holding, and every demanded incantation damages something.
#   4. Every encounter takes 8 to 20 casts, and every boss phase 4 to 9.
#
# `python -m gauntlet.bestiary` prints the report. verify() returns it.

MIN_CASTS = 8
MAX_CASTS = 20
# A boss PHASE is a beat, not a fight: five to eight casts, then the demand
# changes. Four phases therefore land a boss at roughly a long encounter and a
# half, and the six-phase final boss at about twice one.
MIN_PHASE_CASTS = 4
MAX_PHASE_CASTS = 9
MIN_ENEMIES = 45
MIN_ENCOUNTERS = 25
MIN_BOSSES = 12


def referenced_incantations() -> set:
    """Every incantation id this file names, anywhere."""
    out: set = set()
    for enemy in ENEMIES:
        out |= set(enemy.weak_to) | set(enemy.resists)
    for enc in ENCOUNTERS:
        out |= set(enc.demands)
    for boss in BOSSES:
        for phase in boss.phases:
            out |= set(phase.demands)
    return out


def _check_names(problems: list) -> None:
    seen_ids: set = set()
    for enemy in ENEMIES:
        name = enemy.id
        if not name.isidentifier():
            problems.append(f"enemy {name!r} is not a valid Python identifier")
        if keyword.iskeyword(name) or keyword.issoftkeyword(name):
            problems.append(f"enemy {name!r} is a Python keyword")
        if name != name.lower():
            problems.append(f"enemy {name!r} is not lowercase")
        if name in HELPERS:
            problems.append(f"enemy {name!r} shadows a battle helper")
        if name in SAFE_BUILTINS:
            problems.append(f"enemy {name!r} shadows a builtin the templates use")
        if name in seen_ids:
            problems.append(f"enemy {name!r} is defined twice")
        seen_ids.add(name)
        if not enemy.weak_to:
            problems.append(f"enemy {name!r} has no weakness and cannot be killed")
        if len(enemy.flavour) < 2:
            problems.append(f"enemy {name!r} has fewer than two flavour lines")
        overlap = set(enemy.weak_to) & set(enemy.resists)
        if overlap:
            problems.append(
                f"enemy {name!r} is both weak to and resistant to {sorted(overlap)}")


def _check_incantations(problems: list) -> dict:
    referenced = referenced_incantations()
    unknown = sorted(referenced - set(EXPECTED_INCANTATIONS))
    for inc in unknown:
        problems.append(f"incantation {inc!r} is referenced but not in the contract")
    live = _live_catalogue()
    live_missing: list = []
    live_extra: list = []
    if live is not None:
        live_missing = sorted(referenced - set(live))
        live_extra = sorted(set(live) - set(EXPECTED_INCANTATIONS))
        for inc in live_missing:
            problems.append(
                f"incantation {inc!r} is referenced here but incantation.CATALOGUE "
                f"does not define it")
    return {
        "referenced": len(referenced),
        "contract": len(EXPECTED_INCANTATIONS),
        "catalogue_loaded": live is not None,
        "missing_from_catalogue": live_missing,
        "in_catalogue_only": live_extra,
    }


def _strike_problem(inc_id: str, target: str, field: list) -> str:
    """Why this incantation cannot be cast at `target` on `field`, or "".

    Symbolic and cheap, so verify() can run it over every fight. It knows two
    things the weakness table does not: an incantation whose template names two
    enemies needs two enemies STANDING, and one that declares `requires` needs
    that construct on the field. It cannot know whether the values will agree at
    runtime — tests/test_incantation.py casts for real and settles that.
    """
    live = _live_catalogue()
    if live is None:
        return ""
    inc = live.get(resolve_incantation(inc_id))
    if inc is None:
        return ""
    kinds = {KIND_FOR_TYPE.get(ENEMY_BY_ID[e].type, "value")
             for e in field if e in ENEMY_BY_ID}
    missing = set(_attr(inc, "requires") or ()) - kinds
    if missing:
        return f"needs {sorted(missing)} on the field"
    holes = _attr(inc, "holes") or ()
    enemy_holes = [h for h in holes if _attr(h, "kind") == "enemy"]
    if not enemy_holes:
        return ""
    target_hole = _attr(inc, "target_hole") or ""
    partner_holes = [h for h in enemy_holes if _attr(h, "name") != target_hole]
    standing = [e for e in field if e in ENEMY_BY_ID and e != target]
    if len(partner_holes) > len(standing):
        count = len(standing) + 1
        return (f"names {len(partner_holes) + 1} enemies but only {count} "
                f"{'stands' if count == 1 else 'stand'} in that fight")

    # Arity is not enough: NARROW names two enemies, but `left = mid + 1` wants
    # two NUMBERS. The catalogue already says what each hole is worth — its
    # practice binding — so read the expected kind off that rather than guess.
    wanted = _expected_kinds(inc)
    target_kind = KIND_FOR_TYPE.get(ENEMY_BY_ID[target].type, "value")
    need = wanted.get(target_hole)
    if need and not _kinds_agree(need, target_kind):
        return f"strikes a {need}, and {target} is a {target_kind}"
    spare = [KIND_FOR_TYPE.get(ENEMY_BY_ID[e].type, "value") for e in standing]
    for hole in partner_holes:
        need = wanted.get(_attr(hole, "name"))
        if not need:
            continue
        match = next((k for k in spare if _kinds_agree(need, k)), None)
        if match is None:
            return (f"needs a {need} standing beside {target} for "
                    f"{{{_attr(hole, 'name')}}}")
        spare.remove(match)
    return ""


# Two names for the same runtime thing. A heap IS a list — heapq is a discipline
# applied to one, not a type — a matrix is a list of lists, and a bool is an int.
# Treating these as different is how a check invents a bug that is not there.
_KIND_ALIKE: dict = {
    "heap": {"list", "grid"}, "list": {"heap", "grid", "tuple"},
    "grid": {"list", "heap"}, "tuple": {"list"},
    "int": {"bool"}, "bool": {"int"},
    "node": {"none"}, "none": {"node"},
}


def _kinds_agree(wanted: str, got: str) -> bool:
    if not wanted or not got or "value" in (wanted, got):
        return True                       # unknown is never evidence of a defect
    return wanted == got or got in _KIND_ALIKE.get(wanted, ())


def _expected_kinds(inc) -> dict:
    """Enemy hole -> the kind of construct it is written for.

    Read from the incantation's own practice field: `example` says which demo
    name fills the hole, `demo` says what that name is bound to, and the engine
    already knows how to name a kind from a binding. No new authoring, and it
    cannot drift from the catalogue because it IS the catalogue.
    """
    try:
        from . import incantation
    except Exception:
        return {}
    kind_of = getattr(incantation, "_kind_of", None)
    if kind_of is None:
        return {}
    example = _attr(inc, "example") or {}
    demo = _attr(inc, "demo") or {}
    out: dict = {}
    for hole in (_attr(inc, "holes") or ()):
        if _attr(hole, "kind") != "enemy":
            continue
        binding = demo.get(example.get(_attr(hole, "name"), ""), "")
        if binding:
            out[_attr(hole, "name")] = kind_of(binding)
    return out


def _check_strikes(problems: list, label: str, field: list,
                   available: set) -> None:
    """Every enemy needs a weakness that can actually be CAST where it stands."""
    for eid in field:
        enemy = ENEMY_BY_ID.get(eid)
        if enemy is None:
            continue
        usable = [i for i in enemy.weak_to if i in available]
        if not usable:
            continue                      # the caller already reported this
        reasons = {i: _strike_problem(i, eid, field) for i in usable}
        if all(reasons.values()):
            detail = "; ".join(f"{i}: {why}" for i, why in sorted(reasons.items()))
            problems.append(
                f"{label} is unwinnable: nothing that damages {eid!r} can be cast "
                f"on that field ({detail})")


def _check_encounters(problems: list) -> list:
    rows = []
    for enc in ENCOUNTERS:
        available = incantations_available(enc.chapter)
        budget = cast_budget(enc)
        if not (2 <= len(enc.enemies) <= 4):
            problems.append(
                f"encounter {enc.id!r} fields {len(enc.enemies)} enemies; "
                f"interleaving wants two to four")
        if len(set(enc.enemies)) != len(enc.enemies):
            problems.append(f"encounter {enc.id!r} fields the same enemy twice")
        if len({ENEMY_BY_ID[e].type for e in enc.enemies}) < 2:
            problems.append(
                f"encounter {enc.id!r} fields only one type of construct; there is "
                f"nothing to discriminate between")
        if not (MIN_CASTS <= budget["slow"] <= MAX_CASTS):
            problems.append(
                f"encounter {enc.id!r} takes {budget['fast']}-{budget['slow']} casts, "
                f"outside the {MIN_CASTS}-{MAX_CASTS} window")
        for eid in enc.enemies:
            enemy = ENEMY_BY_ID.get(eid)
            if enemy is None:
                problems.append(f"encounter {enc.id!r} names unknown enemy {eid!r}")
                continue
            if chapter_rank(enemy.chapter) > chapter_rank(enc.chapter):
                problems.append(
                    f"encounter {enc.id!r} (chapter {enc.chapter}) fields {eid!r} "
                    f"from the later chapter {enemy.chapter}")
            if not set(enemy.weak_to) & available:
                problems.append(
                    f"encounter {enc.id!r} is unwinnable: {eid!r} has no weakness "
                    f"the {enc.chapter} moveset has taught")
        _check_strikes(problems, f"encounter {enc.id!r}", list(enc.enemies),
                       available)
        for inc in enc.demands:
            if inc not in available:
                problems.append(
                    f"encounter {enc.id!r} demands {inc!r}, which chapter "
                    f"{enc.chapter} has not taught")
            if not any(inc in ENEMY_BY_ID[e].weak_to for e in enc.enemies
                       if e in ENEMY_BY_ID):
                problems.append(
                    f"encounter {enc.id!r} demands {inc!r}, which damages nothing "
                    f"on the field")
        rows.append({"id": enc.id, "chapter": enc.chapter,
                     "enemies": len(enc.enemies), **budget})
    covered = {e.chapter for e in ENCOUNTERS}
    for chapter in CHAPTER_ORDER:
        if chapter not in covered:
            problems.append(f"chapter {chapter!r} has no encounters")
    return rows


def _check_bosses(problems: list) -> list:
    rows = []
    world_ids: set = set()
    try:
        from . import world
        world_ids = {b["id"] for b in world.BOSSES}
    except Exception:
        pass
    for boss in BOSSES:
        available = incantations_available(boss.chapter)
        if len(boss.phases) < 3:
            problems.append(f"boss {boss.id!r} has fewer than three phases")
        demanded_per_phase = [set(p.demands) for p in boss.phases]
        if len(boss.phases) > 1 and all(
                d == demanded_per_phase[0] for d in demanded_per_phase):
            problems.append(
                f"boss {boss.id!r} demands the same incantations in every phase; "
                f"the phases are not rehearsing a sequence")
        for phase in boss.phases:
            beat = cast_budget(phase)
            if not (MIN_PHASE_CASTS <= beat["slow"] <= MAX_PHASE_CASTS):
                problems.append(
                    f"boss {boss.id!r} phase {phase.key!r} takes {beat['fast']}-"
                    f"{beat['slow']} casts, outside the {MIN_PHASE_CASTS}-"
                    f"{MAX_PHASE_CASTS} window for a phase")
            for eid in phase.enemies:
                enemy = ENEMY_BY_ID.get(eid)
                if enemy is None:
                    problems.append(
                        f"boss {boss.id!r} phase {phase.key!r} names unknown enemy "
                        f"{eid!r}")
                    continue
                if chapter_rank(enemy.chapter) > chapter_rank(boss.chapter):
                    problems.append(
                        f"boss {boss.id!r} phase {phase.key!r} fields {eid!r} from "
                        f"the later chapter {enemy.chapter}")
                if not set(enemy.weak_to) & available:
                    problems.append(
                        f"boss {boss.id!r} phase {phase.key!r} is unwinnable: "
                        f"{eid!r} has no weakness taught by {boss.chapter}")
            _check_strikes(problems, f"boss {boss.id!r} phase {phase.key!r}",
                           list(phase.enemies), available)
            for inc in phase.demands:
                if inc not in available:
                    problems.append(
                        f"boss {boss.id!r} phase {phase.key!r} demands {inc!r}, "
                        f"untaught in chapter {boss.chapter}")
                if not any(inc in ENEMY_BY_ID[e].weak_to for e in phase.enemies
                           if e in ENEMY_BY_ID):
                    problems.append(
                        f"boss {boss.id!r} phase {phase.key!r} demands {inc!r}, "
                        f"which damages nothing in that phase")
        if world_ids and boss.id not in world_ids:
            problems.append(
                f"boss {boss.id!r} does not map onto any world.BOSSES id")
        rows.append({"id": boss.id, "phases": len(boss.phases),
                     **cast_budget(boss)})
    if world_ids:
        for missing in sorted(world_ids - {b.id for b in BOSSES}):
            problems.append(f"world boss {missing!r} has no bestiary form")
    return rows


def _check_context(problems: list) -> None:
    """The context has to actually build, for every fight, without raising."""
    for enc in ENCOUNTERS:
        try:
            ctx = build_context(enc)
        except Exception as exc:           # pragma: no cover - authoring guard
            problems.append(f"encounter {enc.id!r} context failed: {exc}")
            continue
        for eid in enc.enemies:
            if eid not in ctx:
                problems.append(
                    f"encounter {enc.id!r} context is missing {eid!r}")
    for boss in BOSSES:
        for phase in boss.phases:
            try:
                build_context(phase)
            except Exception as exc:       # pragma: no cover - authoring guard
                problems.append(
                    f"boss {boss.id!r} phase {phase.key!r} context failed: {exc}")


def _check_vitals(problems: list) -> None:
    """The specials have to name real elements and real statuses.

    Reconciled LAZILY against elements.py, exactly the way the incantation ids
    are reconciled against incantation.py: this file keeps its own strings so it
    still loads and verifies on its own, and the reconciliation is what stops
    the two copies drifting apart in silence. A special that inflicted a status
    the wheel had renamed would be an enemy turn that silently did nothing.
    """
    try:
        from . import elements
    except Exception:                      # pragma: no cover - standalone read
        return
    for special in SPECIALS:
        if special.element and special.element not in elements.ELEMENTS:
            problems.append(
                f"special {special.id!r} claims element {special.element!r}, "
                f"which is not on the wheel")
        if special.inflicts and special.inflicts not in elements.STATUSES:
            problems.append(
                f"special {special.id!r} inflicts {special.inflicts!r}, which "
                f"elements.STATUSES does not define")
        if (special.inflicts and special.element
                and elements.STATUSES[special.inflicts].element != special.element):
            problems.append(
                f"special {special.id!r} is {special.element} but inflicts "
                f"{special.inflicts!r}, which belongs to another element")
    for eid in elements.ELEMENT_IDS:
        if eid not in SPECIAL_BY_ELEMENT:
            problems.append(f"element {eid!r} has no special, so an enemy "
                            f"standing there can never spend its focus")


def verify() -> dict:
    """Run every invariant. Returns counts and a list of problems; never raises."""
    problems: list = []
    _check_names(problems)
    incantations = _check_incantations(problems)
    encounters = _check_encounters(problems)
    bosses = _check_bosses(problems)
    _check_context(problems)
    _check_vitals(problems)

    if len(ENEMIES) < MIN_ENEMIES:
        problems.append(f"only {len(ENEMIES)} enemies; the design asks for "
                        f"{MIN_ENEMIES}")
    if len(ENCOUNTERS) < MIN_ENCOUNTERS:
        problems.append(f"only {len(ENCOUNTERS)} encounters; the design asks for "
                        f"{MIN_ENCOUNTERS}")
    if len(BOSSES) < MIN_BOSSES:
        problems.append(f"only {len(BOSSES)} bosses; the design asks for "
                        f"{MIN_BOSSES}")

    effect_ids = [e.effect for e in ENEMIES]
    if len(set(effect_ids)) != len(effect_ids):
        problems.append("two enemies share an effect id")
    for enemy in ENEMIES:
        if enemy.effect_family not in EFFECT_FAMILIES:
            problems.append(
                f"enemy {enemy.id!r} uses unknown effect family "
                f"{enemy.effect_family!r}")

    slow = [row["slow"] for row in encounters]
    return {
        "ok": not problems,
        "problems": problems,
        "enemies": len(ENEMIES),
        "enemies_by_chapter": {c: len(enemies_for_chapter(c))
                               for c in CHAPTER_ORDER},
        "encounters": len(ENCOUNTERS),
        "encounters_by_chapter": {c: len(encounters_for_chapter(c))
                                  for c in CHAPTER_ORDER},
        "bosses": len(BOSSES),
        "boss_phases": sum(len(b.phases) for b in BOSSES),
        "effects": len(EFFECTS),
        "effect_families": len(EFFECT_FAMILIES),
        "incantations": incantations,
        "cast_window": [min(slow), max(slow)] if slow else [0, 0],
        "encounter_budgets": encounters,
        "boss_budgets": bosses,
    }


def roster() -> list:
    """The whole bestiary, serialised, for the client."""
    return [e.to_dict() for e in ENEMIES]


def main() -> int:                         # pragma: no cover - authoring tool
    report = verify()
    print(f"enemies      {report['enemies']}")
    print(f"encounters   {report['encounters']}  "
          f"casts {report['cast_window'][0]}-{report['cast_window'][1]}")
    boss_slow = [row["slow"] for row in report["boss_budgets"]]
    print(f"bosses       {report['bosses']}  "
          f"phases {report['boss_phases']}  "
          f"casts {min(boss_slow)}-{max(boss_slow)}")
    print(f"effects      {report['effects']} across "
          f"{report['effect_families']} families")
    inc = report["incantations"]
    print(f"incantations {inc['referenced']} referenced / "
          f"{inc['contract']} in contract; catalogue "
          f"{'loaded' if inc['catalogue_loaded'] else 'not present'}")
    if inc["missing_from_catalogue"]:
        print("  missing from catalogue: "
              + ", ".join(inc["missing_from_catalogue"]))
    print("by chapter:")
    for chapter in CHAPTER_ORDER:
        print(f"  {chapter:<13} {report['enemies_by_chapter'][chapter]:>2} enemies"
              f"  {report['encounters_by_chapter'][chapter]:>2} encounters")
    if report["problems"]:
        print(f"\n{len(report['problems'])} problems:")
        for line in report["problems"]:
            print(f"  - {line}")
        return 1
    print("\nno problems")
    return 0


if __name__ == "__main__":                 # pragma: no cover
    raise SystemExit(main())
