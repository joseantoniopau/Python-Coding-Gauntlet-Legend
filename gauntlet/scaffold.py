"""The ramp, as presentation: one problem, four rungs.

    1  PICK          the line is shown with one token missing and four to choose from
    2  ONE BLANK     the line is shown with one token missing
    3  MANY BLANKS   the skeleton is shown with several tokens missing
    4  WRITE IT ALL  the signature, and nothing else

docs/14-the-ramp.md decided that these are four ways of DISPLAYING one problem,
not four problems. The corpus used to do the opposite — a separate record per
rung with the rung frozen into it — and that is why the ramp was a cliff:
TUTORIAL was 195 of 202 blank screens because nobody had authored the middle
rung, and nobody could author it without authoring a whole second problem.

So a problem declares `scaffold_spans`: the ordered list of spans of its own
canonical solution that carry the idea, best blank first, each with the one-line
gloss that becomes its numbered comment. Every rung is generated from that one
declaration. There is one id, one canonical solution and one lineage, so a rung
cannot drift from the problem it is a rung of, and a scaffolded serving cannot
become a second piece of evidence — it is not a second problem.

This module is the presentation layer and holds no state. Which rung a given
player is served is `curriculum.rung_for`, decided from measured competence;
which rungs a band may ever offer is `FLOOR`, decided structurally.
"""
from __future__ import annotations

import ast
import re

MARKER = "__BLANK__"

RUNGS = (1, 2, 3, 4)
RUNG_NAMES = {1: "PICK", 2: "ONE_BLANK", 3: "MANY_BLANKS", 4: "WRITE_IT_ALL"}

PICK = 1
ONE_BLANK = 2
MANY_BLANKS = 3
WRITE_IT_ALL = 4

# How many spans rung 3 strikes out. Three is the ceiling the shipped scaffolds
# already sit at (the 63 GUIDED many-blank starters average 2.3) and more than
# three blanks stops reading as a skeleton and starts reading as a cloze test.
MANY_SPAN_COUNT = 3

# ---------------------------------------------------------------------------
# THE FLOOR — the most help a band may ever offer.
# ---------------------------------------------------------------------------
#
# Monotone by construction: 1 <= 2 <= 3 <= 4 <= 4. This is a property of the
# serving code, so content drift cannot violate it. The corpus's live
# monotonicity bug — 21 EASY problems served with two blanks while TUTORIAL was
# a blank screen — is excluded here rather than argued about: EASY may be served
# at rung 3, and may never be served at rung 2.
FLOOR = {
    "GUIDED": PICK,
    "TUTORIAL": ONE_BLANK,
    "EASY": MANY_BLANKS,
    "MEDIUM": WRITE_IT_ALL,
    "HARD": WRITE_IT_ALL,
    "ELITE": WRITE_IT_ALL,
    "BOSS": WRITE_IT_ALL,
}

# The practical, Timed Practical Mode and the hold-out serve rung 4 and nothing else,
# in any band, forever. finalexam.py used to get this by accident — MISSING_RUNE
# was excluded by encounter kind and the one CODE_BATTLE carrying a blank was
# excluded by being GUIDED. Under render-time rungs both coincidences evaporate,
# because any CODE_BATTLE becomes servable at rung 2, so the guard is stated in
# the one vocabulary that stays true.
UNSCAFFOLDED_MODES = frozenset({"interview", "exam", "practical", "holdout"})


def floor_for(difficulty: str) -> int:
    return FLOOR.get(difficulty, WRITE_IT_ALL)


# ---------------------------------------------------------------------------
# Spans
# ---------------------------------------------------------------------------

def _lines(source: str) -> list:
    return source.split("\n")


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _boundary_clean(row: str, col: int, text: str) -> bool:
    """Does `text` stand on its own at this column, or inside a longer name?

    `ob-dict-store` declared the span `price` and `row.find` handed back column
    15 — the `price` inside `prices` — so rung 3 rendered
    `def dict_store(__BLANK__s, ...)`. `round_trip` returns True on that,
    because refilling the hole reproduces `prices` byte for byte, so the one
    check written to catch a declaration describing some other version of the
    answer is structurally unable to see this one. The boundary is the check.

    Only identifier-shaped spans are guarded. A span like `prices[item] = price`
    or `a - b` has punctuation at its edges and a neighbouring word character is
    meaningful there, not accidental.
    """
    if not _IDENT_RE.match(text):
        return True
    before = row[col - 1] if col > 0 else ""
    after = row[col + len(text):col + len(text) + 1]
    return not (before.isalnum() or before == "_"
                or after.isalnum() or after == "_")


def normalise(spans, canonical: str) -> list:
    """Resolve a declaration against the canonical solution it describes.

    A declaration names a line index, the exact text of the span on it, and the
    gloss. `nth` disambiguates a span text that occurs twice on one line. The
    return carries the resolved column, so every consumer slices the same bytes.
    """
    out = []
    rows = _lines(canonical)
    for order, span in enumerate(spans or []):
        line = int(span.get("line", -1))
        text = span.get("text", "")
        if not text or not 0 <= line < len(rows):
            raise ScaffoldError(f"span {order} names line {line}, which is not in the "
                                f"canonical solution ({len(rows)} lines)")
        row = rows[line]
        nth = max(1, int(span.get("nth", 1)))
        col, found = -1, 0
        start = 0
        while True:
            col = row.find(text, start)
            if col < 0:
                break
            if not _boundary_clean(row, col, text):
                # `price` inside `prices` is not an occurrence of `price`. A
                # declaration that struck it would blank four letters out of the
                # middle of a name — and `round_trip` cannot see it, because
                # refilling the hole reproduces the longer name exactly. This is
                # the check that catches it, at the only place that knows where
                # the strike is going to land.
                start = col + 1
                continue
            found += 1
            if found == nth:
                break
            start = col + 1
        if col < 0:
            raise ScaffoldError(
                f"span {order} declares {text!r} on line {line} of the canonical "
                f"solution, which reads {row!r} (no occurrence of it stands on its "
                f"own; a span may not strike inside a longer name)")
        out.append({"line": line, "col": col, "text": text,
                    "gloss": span.get("gloss", "").strip(),
                    "nth": nth,
                    "choices": list(span.get("choices") or [])})
    return out


def resolve_targets(canonical: str, pairs) -> list:
    """Turn the authoring form — (target text, gloss) — into resolved spans.

    The authoring form is the one `families/scaffolds.py` has used since the
    Rune Vault shipped: name the substring of the canonical solution that
    carries the idea and the sentence that explains what it has to do. Targets
    are matched in order and each consumes the first occurrence not already
    taken, so repeating a target strikes successive occurrences.

    A target that no longer appears in the canonical solution raises at build
    time rather than shipping a declaration that describes some other version of
    the answer. That is the check `starter_code` never had.
    """
    rows = canonical.split("\n")
    taken: list = []
    spans = []
    for order, pair in enumerate(pairs):
        target, gloss = pair[0], (pair[1] if len(pair) > 1 else "")
        # A third element pins the line, for the handful of spans whose text
        # also occurs earlier in the solution — `value` in `if value:` is also
        # the loop target two lines above it, and a declaration that silently
        # struck the wrong one would blank the `for` statement.
        only = pair[2] if len(pair) > 2 else None
        placed = False
        for index, row in enumerate(rows):
            if only is not None and index != only:
                continue
            start = 0
            while True:
                col = row.find(target, start)
                if col < 0:
                    break
                if not _boundary_clean(row, col, target):
                    start = col + 1
                    continue
                span = (index, col, col + len(target))
                if not any(index == t[0] and col < t[2] and span[2] > t[1]
                           for t in taken):
                    taken.append(span)
                    nth = 1 + sum(1 for t in taken[:-1]
                                  if t[0] == index and rows[index][t[1]:t[2]] == target
                                  and t[1] < col)
                    spans.append({"line": index, "text": target,
                                  "gloss": gloss, "nth": nth})
                    placed = True
                    break
                start = col + 1
            if placed:
                break
        if not placed:
            raise ScaffoldError(
                f"declared span {order} names {target!r}, which is not in the "
                f"canonical solution on its own (it may only occur inside a longer "
                f"name, or be already struck out by an earlier span)")
    return spans


class ScaffoldError(ValueError):
    """A declaration that does not describe its own canonical solution."""


def spans_of(problem) -> list:
    """The declared spans of a problem, resolved. Empty when it declares none."""
    declared = getattr(problem, "scaffold_spans", None) or []
    if not declared:
        return []
    return normalise(declared, problem.canonical_solution)


# The encounters that put a plain editor in front of the player, which is the
# only place a rung means anything.
#
#   A RUNE_ASSEMBLY is graded from an ORDERING of given runes — there is no
#   editor to blank, and the encounter is already a scaffold of a different
#   kind. A DEBUG_BATTLE, a REFACTOR_QUEST and a BREAK_IT all ship a starter
#   that IS the exercise: broken code to fix, ugly code to tidy, honest code to
#   break. Rendering a rung over any of those would replace the question with a
#   blanked copy of its own answer.
#
# So they are served whole, always, and `starter_code` is left exactly as
# authored. This is a property of the encounter, not a rule anyone has to
# remember at each call site.
SCAFFOLDABLE_KINDS = frozenset({"CODE_BATTLE", "MISSING_RUNE"})
EDITOR_ENTRIES = frozenset({"function", "class_ops"})


def scaffoldable(problem) -> bool:
    """Can a rung be rendered for this problem at all?"""
    return (problem.entry.get("kind") in EDITOR_ENTRIES
            and problem.encounter_kind in SCAFFOLDABLE_KINDS)


_PICK_CACHE: dict = {}


def _pick_choices(problem, span: dict) -> list:
    """`choices_for` memoised on the identity of the span it is asked about.

    `available_rungs` is on the serving path and is now asked this question on
    every encounter, and the answer is a pure function of the problem id and the
    span — the same fact `choices_for` relies on to keep the order stable across
    a page reload. The key carries the span text so a re-declaration in the same
    process cannot be answered from a stale entry.
    """
    key = (problem.id, span["line"], span["col"], span["text"])
    hit = _PICK_CACHE.get(key)
    if hit is None:
        hit = choices_for(problem, span)
        _PICK_CACHE[key] = hit
    return hit


def available_rungs(problem) -> tuple:
    """Which rungs this problem's declaration can actually generate.

    Rung 4 always. Rung 2 needs one span; rung 3 needs two, because a single
    blank presented as "fill in the blanks" is a lie about what is being asked.

    RUNG 1 NEEDS SOMETHING TO PICK BETWEEN, and that is not a property of the
    span count. `choices_for` returns nothing for 55 of the 498 problems with a
    declaration, because the neighbour generator has no move against their first
    span — and rung 1 was granted on the count alone, so `render` shipped
    `{"rung": 1, "name": "PICK", "choices": []}`: a multiple choice with no
    choices, byte-identical to the rung-2 render, with the clear filed at rung 1.
    Rung-1 evidence does not count toward leaving rung 2
    (`curriculum._unaided_at_or_below`), so the player did rung-2 work and was
    credited less than they earned. 34 of those 55 are GUIDED, whose floor IS
    rung 1, so for those the first rung of the ladder did not exist at all.

    So the ladder tells the truth about what it can render. Withholding it HERE
    rather than inside `render` is the whole point: `servable` reads this, so
    the serving falls UP to ONE_BLANK and `enc.rung` records the 2 that was
    actually shown. Handling it in `render` would leave the record saying 1.
    """
    if not scaffoldable(problem):
        return (WRITE_IT_ALL,)
    spans = spans_of(problem)
    count = len(spans)
    if count == 0:
        return (WRITE_IT_ALL,)
    rungs = []
    if len(_pick_choices(problem, spans[0])) >= 2:
        rungs.append(PICK)
    rungs.append(ONE_BLANK)
    if count >= 2:
        rungs.append(MANY_BLANKS)
    rungs.append(WRITE_IT_ALL)
    return tuple(rungs)


# ---------------------------------------------------------------------------
# Rendering: the canonical solution, with spans struck out
# ---------------------------------------------------------------------------

_COMMENT_RE = re.compile(r"\s+#\s.*$")


def strike(canonical: str, spans: list) -> str:
    """The canonical solution with these spans replaced by the marker.

    `__BLANK__` is a bare name on purpose: the starter still parses, so a player
    who runs it untouched gets a NameError that names the rune they still owe,
    not a SyntaxError pointing at column one. That rule was already written into
    `families/scaffolds.py` and is preserved here because it is the reason the
    marker is spelled the way it is.

    Spans are struck right-to-left within a line so that an earlier strike
    cannot move a later span's column out from under it.
    """
    rows = _lines(canonical)
    by_line: dict = {}
    for order, span in enumerate(spans):
        by_line.setdefault(span["line"], []).append((order, span))
    for line, items in by_line.items():
        row = rows[line]
        for _, span in sorted(items, key=lambda pair: pair[1]["col"], reverse=True):
            col, text = span["col"], span["text"]
            row = row[:col] + MARKER + row[col + len(text):]
        rows[line] = row
    return "\n".join(rows)


def annotate(source: str, spans: list, *, choices_for: dict | None = None) -> str:
    """Append each span's numbered gloss to the line it was struck from.

    The numbered comments are the teaching, not decoration around it. A blank
    with no gloss is a guessing game, so a span that declares none is written as
    a bare number rather than silently reading as ordinary code.
    """
    rows = _lines(source)
    columns = comment_columns(source)
    numbered: dict = {}
    for order, span in enumerate(spans, 1):
        numbered.setdefault(span["line"], []).append((order, span))
    # And the comment-only lines directly ABOVE a struck line go with it, for
    # the same reason and measured on the same corpus. `lang-sortkey-tutorial`
    # kept "# `key=len`, not `key=len(words)`. The key is the function itself."
    # standing over the blank that wants `sorted(words, key=len)`;
    # `oopl-eq-hash-easy` kept "# Same fields as __eq__, in the same order."
    # over the blank whose gloss says the same sentence. 64 problems rendered a
    # canonical comment within three lines of a blank. The gloss is the only
    # sentence a blank gets.
    dropped = set()
    for line in numbered:
        for above in _comments_above(rows, line, columns):
            dropped.add(above)
    for line, items in numbered.items():
        # The canonical solution's own trailing comment on this line goes. It
        # was written to explain the answer to somebody reading the worked
        # solution, so leaving it beside a blank cut out of that same line hands
        # the answer over — `total += __BLANK__   # bank every rise` — and then
        # the gloss lands after it as a second comment on one line.
        if line in columns:
            rows[line] = rows[line][:columns[line]].rstrip()
        notes = []
        for order, span in sorted(items):
            gloss = span["gloss"] or "the rune this line is missing"
            note = f"{order}. {gloss}"
            picks = (choices_for or {}).get(order)
            if picks:
                note += "   pick one:  " + "   |   ".join(picks)
            notes.append(note)
        rows[line] = rows[line].rstrip() + "  # " + "   ".join(notes)
    if dropped:
        rows = [row for index, row in enumerate(rows) if index not in dropped]
    return "\n".join(rows)


def _comments_above(rows: list, index: int, columns: dict) -> list:
    """The contiguous run of comment-only line indices directly above `index`.

    The same walk `_gloss_above` makes when it reads a hand-blanked starter back
    into a declaration — run here in the other direction, because a sentence
    that IS the gloss on the way in is the answer printed beside the hole on the
    way out.
    """
    picked = []
    cursor = index - 1
    while cursor >= 0:
        row = rows[cursor]
        if not row.strip():
            break
        if columns.get(cursor) != len(row) - len(row.lstrip()):
            break
        picked.append(cursor)
        cursor -= 1
    return picked


def skeleton(problem) -> str:
    """Rung 4: the signatures, and nothing to lean on.

    Derived from the canonical solution rather than from `starter_code`, because
    for the 214 problems that ship a blanked starter the starter IS a lower rung
    — serving that as rung 4 would be serving help while claiming not to. The
    shape is the one the corpus already uses for a blank screen: the header, and
    `pass` under it. Comments go, because a comment on a line the player has to
    write is the gloss of a scaffold with the scaffold taken away.
    """
    authored = problem.starter_code or ""
    if authored.strip() and MARKER not in authored:
        return authored                    # already a blank screen; leave it alone
    source = problem.canonical_solution
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _fallback_skeleton(problem)

    rows = _lines(source)
    columns = comment_columns(source)
    keep: dict = {}                        # line number (1-based) -> kept text
    fills: dict = {}                       # line number -> indent for its `pass`
    breaks: set = set()                    # line numbers that open a top-level block

    def take(first: int, last: int) -> None:
        for number in range(first, last + 1):
            row = rows[number - 1]
            column = columns.get(number - 1)
            text = (row[:column] if column is not None else row).rstrip()
            if text.strip():
                keep[number] = text

    def walk(node, top: bool) -> None:
        for child in getattr(node, "body", []):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                head = min([d.lineno for d in child.decorator_list] + [child.lineno])
                first = child.body[0]
                opens = min([d.lineno for d in getattr(first, "decorator_list", [])]
                            + [first.lineno])
                take(head, opens - 1)
                if top:
                    breaks.add(head)
                methods = [g for g in child.body
                           if isinstance(g, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if isinstance(child, ast.ClassDef) and methods:
                    walk(child, top=False)
                else:
                    fills[opens] = _indent_of(rows, opens)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                # An import the solution needs is scenery, not the exercise.
                take(child.lineno, child.end_lineno or child.lineno)
                if top:
                    breaks.add(child.lineno)

    walk(tree, top=True)
    if not keep:
        return _fallback_skeleton(problem)

    out: list = []
    for number in range(1, len(rows) + 1):
        if number in keep:
            if out and number in breaks and out[-1].strip():
                out.append("")
            out.append(keep[number])
        if number in fills:
            out.append(fills[number] + "pass")
    return "\n".join(out) + "\n"


def _indent_of(rows: list, lineno: int) -> str:
    row = rows[lineno - 1] if 0 < lineno <= len(rows) else "    "
    return row[:len(row) - len(row.lstrip())] or "    "


def _fallback_skeleton(problem) -> str:
    """When the canonical will not parse, the authored starter is the best we
    have — unless it is itself a lower rung, in which case say so rather than
    hand out the scaffold."""
    starter = problem.starter_code or ""
    if MARKER not in starter:
        return starter
    name = problem.entry.get("name") or "solve"
    signature = problem.entry.get("signature") or ""
    if "(" not in signature:
        signature = f"{name}(*args)"
    return f"def {signature}:\n    pass\n"


def servable(problem, difficulty: str, desired: int, *, floor: int | None = None) -> int:
    """The rung actually served: no lower than the band's floor, and never lower
    than this problem's declaration can support.

    Both corrections move UP the ladder — towards less help — because every way
    of getting this wrong that the corpus has already demonstrated moved down.

    `floor` overrides the band's own, and exists for exactly one caller: a
    LAPSED spaced-repetition review, which is allowed one rung below the band
    and is the only route to a scaffold at MEDIUM. Passing the band's floor here
    unconditionally is what silently pinned that recovery rung back to 4 —
    measured, and the reason this parameter is not optional-looking sugar.
    """
    low = floor_for(difficulty) if floor is None else int(floor)
    desired = max(low, min(WRITE_IT_ALL, int(desired)))
    available = [rung for rung in available_rungs(problem) if rung >= low]
    if not available:
        return WRITE_IT_ALL
    # The nearest rung AT OR ABOVE the one the player earned. Never below it,
    # even when a lower rung is legal in this band.
    #
    # Serving the nearest rung in either direction was tried and measured. It
    # reads better — a GUIDED problem with one declared span would offer one
    # blank rather than jumping to a blank screen — but it costs the invariant
    # that makes rung evidence mean anything: A SERVING IS NEVER EASIER THAN THE
    # RUNG IT IS RECORDED AS. Without that, a rung-3 record can contain rung-2
    # work, and `has_produced_code` is back to counting the wrong thing. It also
    # feeds back: a serving capped down files evidence down, so the climb stalls
    # and the measured mix came out 100% scaffolded at both GUIDED and TUTORIAL
    # — no taper at all between the first two bands.
    #
    # The cost is named rather than hidden: 120 of the 184 GUIDED declarations
    # carry a single span, so a player who has earned rung 3 is served those
    # whole. That is a content gap with an obvious remedy — a second span each —
    # not a mechanism failure.
    for rung in sorted(available):
        if rung >= desired:
            return rung
    return WRITE_IT_ALL


def render(problem, rung: int, *, spans: list | None = None) -> dict:
    """One problem, displayed at one rung. Pure presentation; no state read.

    The return is what a serving path needs and nothing more: the text to put in
    the editor, the rung it is, and — for rung 1 — the choices. The canonical
    text that fills each blank never appears in it, because this return travels
    to the client and `redact_mcq` is the precedent.
    """
    rung = int(rung)
    if rung not in RUNGS:
        raise ScaffoldError(f"{rung} is not a rung; the ladder is {RUNGS}")
    if not scaffoldable(problem):
        # No editor, or an editor whose contents are themselves the question.
        # The authored starter is the encounter; it is not ours to rewrite.
        return {"rung": WRITE_IT_ALL, "name": RUNG_NAMES[WRITE_IT_ALL],
                "starter_code": problem.starter_code, "blanks": 0, "choices": []}
    declared = spans if spans is not None else spans_of(problem)
    if rung == WRITE_IT_ALL or not declared:
        return {"rung": WRITE_IT_ALL, "name": RUNG_NAMES[WRITE_IT_ALL],
                "starter_code": skeleton(problem), "blanks": 0, "choices": []}

    if rung == PICK and len(_pick_choices(problem, declared[0])) < 2:
        # `available_rungs` has already withheld PICK for these, so `servable`
        # can no longer select it — but `render` is public and is called with a
        # literal rung by tests, by the audit and by `Game.problem` replaying a
        # stored `enc.rung`. It falls UP for the same reason MANY_BLANKS does:
        # a pick with nothing to pick between is a one-blank wearing rung 1's
        # name, and the rung a player is shown must be the rung recorded.
        return render(problem, ONE_BLANK, spans=declared)

    if rung == MANY_BLANKS:
        chosen = declared[:MANY_SPAN_COUNT]
        if len(chosen) < 2:
            # A one-line function has one idea, and "fill in the blanks" over a
            # single blank is a lie about what is being asked. Fall UP to the
            # whole function, never down to more help than the caller asked for
            # — falling down is how EASY came to be served two-blank scaffolds
            # while TUTORIAL was a blank screen.
            return render(problem, WRITE_IT_ALL, spans=declared)
    else:
        chosen = declared[:1]

    # Struck in declaration order, but numbered in the order they are read down
    # the page — a player fills them top to bottom and "3." above "1." is a
    # puzzle about the comments rather than about the code.
    ordered = sorted(chosen, key=lambda s: (s["line"], s["col"]))
    text = strike(problem.canonical_solution, ordered)
    picks = {}
    if rung == PICK:
        picks = {1: choices_for(problem, ordered[0])}
    return {"rung": rung, "name": RUNG_NAMES[rung],
            "starter_code": annotate(text, ordered, choices_for=picks) + "\n",
            "blanks": len(ordered),
            "choices": picks.get(1, [])}


# ---------------------------------------------------------------------------
# Plausible neighbours: rung 1's distractors, and the objective test
# ---------------------------------------------------------------------------
#
# One generator serves both, and that is the point. A span carries the idea if
# filling it with a plausible neighbour makes the tests fail; the same
# neighbours, shown beside the canonical token, are what rung 1 asks the player
# to choose between. So the distractors are provably wrong rather than merely
# different-looking, and the check that proves it is the check that a blank
# which any neighbour satisfies is decoration.

_TOKEN_SWAPS = (
    # (pattern, replacement) — applied one at a time, on token boundaries.
    (r"(?<![+\-*/<>=!%])\+(?![+=])", "-"),
    (r"(?<![+\-*/<>=!%])-(?![-=>])", "+"),
    (r"(?<![*])\*(?![*=])", "+"),
    (r"//", "/"),
    (r"(?<![/])/(?![/=])", "//"),
    (r"%", "//"),
    (r"<=", "<"),
    (r">=", ">"),
    (r"(?<![<>=!])<(?![=])", ">"),
    (r"(?<![<>=!])>(?![=])", "<"),
    (r"(?<![<>=!])<(?![=])", "<="),
    (r"(?<![<>=!])>(?![=])", ">="),
    (r"==", "!="),
    (r"!=", "=="),
    (r"\band\b", "or"),
    (r"\bor\b", "and"),
    (r"\bnot\s+in\b", "in"),
    (r"(?<!not )\bin\b", "not in"),
    (r"\bis\s+not\b", "is"),
    (r"(?<!is )\bis\b(?!\s+not)", "is not"),
    (r"\bnot\s+", ""),
    (r"\bmin\b", "max"),
    (r"\bmax\b", "min"),
    (r"\bappendleft\b", "append"),
    (r"\bappend\b(?!left)", "appendleft"),
    (r"\bpopleft\b", "pop"),
    (r"\bpop\b(?!left)", "popleft"),
    (r"\bsorted\b", "reversed"),
    (r"\bTrue\b", "False"),
    (r"\bFalse\b", "True"),
    (r"\bsum\b", "len"),
    (r"\blen\b", "sum"),
    (r"\badd\b", "discard"),
    (r"\bdiscard\b", "add"),
    (r"\bextend\b", "append"),
    (r"\bkeys\b", "values"),
    (r"\bvalues\b", "keys"),
    (r"\bupper\b", "lower"),
    (r"\blower\b", "upper"),
    (r"\bstrip\b", "lstrip"),
    (r"\bnext\b", "prev"),
    (r"\bprev\b", "next"),
    (r"\bleft\b", "right"),
    (r"\bright\b", "left"),
    (r"\bstartswith\b", "endswith"),
    (r"\bendswith\b", "startswith"),
    (r"\bupdate\b", "clear"),
    (r"\bremove\b", "pop"),
    (r"\bmove_to_end\b", "popitem"),
    (r"\bbisect_left\b", "bisect_right"),
    (r"\bbisect_right\b", "bisect_left"),
    (r"\bheappush\b", "heappushpop"),
    (r"\bmean\b", "median"),
    (r"\bmedian\b", "mean"),
    (r"\bgcd\b", "lcm"),
    (r"\byield from\b", "yield"),
)

_INT_RE = re.compile(r"(?<![\w.])(\d+)(?![\w.])")


def _integer_nudges(text: str) -> list:
    out = []
    for match in _INT_RE.finditer(text):
        value = int(match.group(1))
        for other in (value + 1, value - 1):
            if other < 0:
                continue
            out.append(text[:match.start()] + str(other) + text[match.end():])
    return out


def _swap_operands(text: str) -> list:
    """`a - b` read as `b - a`. The single most common wrong answer there is."""
    out = []
    for op in (" - ", " / ", " // ", " % ", " < ", " > ", " <= ", " >= "):
        if text.count(op) == 1:
            left, right = text.split(op)
            if left.strip() and right.strip():
                out.append(f"{right.strip()}{op}{left.strip()}")
    return out


def _index_nudges(text: str) -> list:
    out = []
    for match in re.finditer(r"\[([^\[\]]+)\]", text):
        inner = match.group(1).strip()
        if not inner or ":" in inner:
            continue
        for other in (f"{inner} + 1", f"{inner} - 1"):
            out.append(text[:match.start(1)] + other + text[match.end(1):])
    return out


def _structural(text: str) -> list:
    """Neighbours that only an AST can see.

    The most plausible wrong answer to "what goes here" is very often *part* of
    the right one — the expression with its wrapper forgotten, the call with its
    two arguments the wrong way round, the comprehension with its filter left
    off. Token swapping cannot reach any of those, and without them the mutant
    check goes quiet on exactly the spans that are hardest to judge by eye.
    """
    out = []
    for mode in ("eval", "exec"):
        try:
            tree = ast.parse(text, mode=mode)
        except SyntaxError:
            continue
        body = tree.body if mode == "eval" else (
            tree.body[0].value if tree.body and isinstance(tree.body[0], ast.Expr)
            else None)
        node = body if mode == "eval" else body
        if node is None:
            continue
        if isinstance(node, ast.Call):
            args = [a for a in node.args if not isinstance(a, ast.Starred)]
            # the wrapper forgotten
            for arg in args[:2]:
                piece = ast.get_source_segment(text, arg)
                if piece and piece != text:
                    out.append(piece)
            # the two arguments the wrong way round
            if len(args) == 2 and not node.keywords:
                first = ast.get_source_segment(text, args[0])
                second = ast.get_source_segment(text, args[1])
                func = ast.get_source_segment(text, node.func)
                if first and second and func:
                    out.append(f"{func}({second}, {first})")
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp,
                             ast.DictComp)):
            for generator in node.generators:
                for condition in generator.ifs:
                    piece = ast.get_source_segment(text, condition)
                    if piece:
                        # the filter left off entirely
                        stripped = text.replace(f" if {piece}", "", 1)
                        if stripped != text:
                            out.append(stripped)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left = ast.get_source_segment(text, node.left)
            right = ast.get_source_segment(text, node.comparators[0])
            if left and right:
                out.append(left)
                out.append(right)
        if isinstance(node, ast.BinOp):
            for side in (node.left, node.right):
                piece = ast.get_source_segment(text, side)
                if piece and piece != text:
                    out.append(piece)
        if isinstance(node, ast.Attribute):
            piece = ast.get_source_segment(text, node.value)
            if piece and piece != text:
                out.append(piece)
        break
    return out


def _parses(fragment: str) -> bool:
    for mode in ("eval", "exec"):
        try:
            ast.parse(fragment, mode=mode)
            return True
        except SyntaxError:
            continue
    return False


def neighbours(text: str, *, limit: int = 10) -> list:
    """Wrong fillings a player might plausibly write. Never the right one."""
    text = text.strip()
    seen, out = {text}, []
    candidates = []
    for pattern, replacement in _TOKEN_SWAPS:
        match = re.search(pattern, text)
        if match:
            candidates.append(text[:match.start()] + replacement + text[match.end():])
    candidates += _structural(text)
    candidates += _swap_operands(text)
    candidates += _integer_nudges(text)
    candidates += _index_nudges(text)
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate in seen or not candidate:
            continue
        if not _parses(candidate):
            continue
        seen.add(candidate)
        out.append(candidate)
        if len(out) >= limit:
            break
    return out


def choices_for(problem, span: dict, *, count: int = 4) -> list:
    """Rung 1's four options: the canonical token and three neighbours.

    Deterministic in the problem id and the span, so the order cannot be
    rerolled by reloading the page — a shuffled-on-every-request multiple choice
    is a free answer to anyone who reloads twice and watches which one moves.
    """
    right = span["text"].strip()
    wrong = [c for c in (span.get("choices") or []) if c.strip() != right]
    wrong += [c for c in neighbours(right) if c not in wrong]
    options = [right] + wrong[:max(0, count - 1)]
    if len(options) < 2:
        return []
    seed = _stable_seed(problem.id, span["line"], span["col"])
    return _stable_shuffle(options, seed)


def _stable_seed(*parts) -> int:
    import hashlib
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:8], 16)


def _stable_shuffle(items: list, seed: int) -> list:
    items = list(items)
    for i in range(len(items) - 1, 0, -1):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        j = seed % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items


def substitute(problem, span: dict, replacement: str) -> str:
    """The canonical solution with one span replaced. The mutant, for §4's test."""
    rows = _lines(problem.canonical_solution)
    row = rows[span["line"]]
    col, text = span["col"], span["text"]
    rows[span["line"]] = row[:col] + replacement + row[col + len(text):]
    return "\n".join(rows)


def round_trip(problem, spans: list | None = None) -> bool:
    """Filling every declared span with its own text reproduces the canonical.

    Trivially true when the declaration is honest, and the only thing that was
    ever checking the 214 hand-maintained blanked starters was nothing at all.
    """
    declared = spans if spans is not None else spans_of(problem)
    if not declared:
        return True
    struck = strike(problem.canonical_solution, declared)
    restored = struck
    for span in sorted(declared, key=lambda s: (s["line"], s["col"])):
        restored = restored.replace(MARKER, span["text"], 1)
    return restored == problem.canonical_solution


# ---------------------------------------------------------------------------
# The mechanical conversion of the 214 hand-blanked starters
# ---------------------------------------------------------------------------
#
# Every problem that already ships a `__BLANK__` starter is already a
# declaration, written in the wrong place — applied once at authoring time and
# then thrown away, leaving a hand-maintained copy of the canonical solution
# that nothing has ever checked. Measured across all 214, once comment-only
# lines are discounted, 213 are the canonical solution with spans struck out and
# every other byte identical; the one exception differs by a blank line.
#
# So the conversion is a read, not an authoring pass — and the read is itself
# the check `starter_code` never had. A starter that cannot be explained as
# "the canonical solution with these spans struck out" is mis-filed, and this
# raises instead of shipping it.

_NUMBERED_RE = re.compile(r"(\d+)\.\s*(.*?)(?=\s{2,}\d+\.\s|$)")


def comment_columns(source: str) -> dict:
    """line index (0-based) -> column where its trailing comment starts.

    Tokenised rather than matched, because a `#` inside a string literal is not
    a comment and a scaffold that decided it was would strike the wrong span out
    of the line. Falls back to a regex only if the source will not tokenise.
    """
    import io
    import tokenize
    out: dict = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                out[token.start[0] - 1] = token.start[1]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        out = {}
        for index, row in enumerate(_lines(source)):
            hit = row.find("#")
            if hit >= 0 and row.count('"') % 2 == 0 and row.count("'") % 2 == 0:
                out[index] = hit
    return out


def _decomment(rows: list, columns: dict) -> list:
    return [(row[:columns[i]] if i in columns else row).rstrip()
            for i, row in enumerate(rows)]


def _split_gloss(row: str, column: int | None) -> tuple:
    """(code, [gloss, ...]) for one blanked starter line."""
    if column is None:
        return row.rstrip(), []
    code = row[:column].rstrip()
    comment = row[column:].lstrip("#").strip()
    numbered = _NUMBERED_RE.findall(comment)
    if numbered and comment[:1].isdigit():
        return code, [text.strip() for _, text in numbered]
    return code, ([comment] if comment else [])


def _significant(rows: list, stripped: list) -> list:
    """(index, code, row) for the lines that are code.

    A comment-only line is teaching wrapped around the hole, and both sides of
    the comparison carry their own: the canonical solution explains itself to a
    player reading the worked answer, and the scaffold explains the hole. Blank
    lines are formatting. Neither is the exercise, so neither is compared.
    """
    return [(index, code, rows[index])
            for index, code in enumerate(stripped) if code.strip()]


def _gloss_above(rows: list, index: int, columns: dict) -> list:
    """The contiguous comment-only lines directly above a blanked line."""
    picked = []
    cursor = index - 1
    while cursor >= 0:
        row = rows[cursor]
        if not row.strip():
            break
        if columns.get(cursor) != len(row) - len(row.lstrip()):
            break
        text = row.strip().lstrip("#").strip()
        # The author's own numbering comes off, exactly as `_split_gloss` takes
        # it off a trailing comment. Without this the 21 `py-*-guided` stdlib
        # declarations stored a gloss that already began "1. " and `annotate`
        # prepended a second one: "# 1. 1. Counter counts whatever you iterate."
        numbered = _NUMBERED_RE.findall(text)
        if numbered and text[:1].isdigit():
            text = " ".join(part.strip() for _, part in numbered)
        picked.append(text)
        cursor -= 1
    text = " ".join(reversed([line for line in picked if line]))
    return [text] if text else []


def derive_spans(problem) -> list:
    """Read a hand-blanked `starter_code` back into a declaration.

    Raises `ScaffoldError` naming the problem when the starter is not the
    canonical solution with spans struck out — which is the case `pt-class-latest`
    proves exists and nothing was catching.
    """
    starter = problem.starter_code or ""
    if MARKER not in starter:
        return []
    canonical = problem.canonical_solution
    srows = _lines(starter.rstrip("\n"))
    crows = _lines(canonical.rstrip("\n"))
    scols = comment_columns(starter)
    ccols = comment_columns(canonical)
    left = _significant(srows, _decomment(srows, scols))
    right = _significant(crows, _decomment(crows, ccols))
    if len(left) != len(right):
        raise ScaffoldError(
            f"{problem.id}: the blanked starter has {len(left)} code lines and the "
            f"canonical solution has {len(right)}; a scaffold must be the canonical "
            f"solution with spans struck out, not a second copy of it")

    spans = []
    for (sindex, scode, srow), (cindex, ccode, _) in zip(left, right):
        if MARKER not in scode:
            if scode != ccode:
                raise ScaffoldError(
                    f"{problem.id}: unblanked starter line {scode!r} does not match "
                    f"the canonical line {ccode!r}")
            continue
        code, glosses = _split_gloss(srow, scols.get(sindex))
        if MARKER not in code:                     # the `#` was inside a string
            code, glosses = srow.rstrip(), []
        if not glosses:
            # 110 of the 306 blanked lines put their teaching on the comment
            # line ABOVE the hole rather than after it. That is the gloss; a
            # deriver that dropped it would replace a sentence somebody wrote
            # for a beginner with a generated placeholder.
            glosses = _gloss_above(srows, sindex, scols)
        parts = code.split(MARKER)
        canon = ccode
        if not canon.startswith(parts[0]):
            raise ScaffoldError(
                f"{problem.id}: blanked line {code!r} does not open the canonical "
                f"line {canon!r}")
        pos = len(parts[0])
        found = []
        for number, part in enumerate(parts[1:], 1):
            if number == len(parts) - 1:
                end = len(canon) - len(part)
                if not canon.endswith(part) or end < pos:
                    raise ScaffoldError(
                        f"{problem.id}: blanked line {code!r} does not close the "
                        f"canonical line {canon!r}")
            else:
                end = canon.find(part, pos)
                if end < 0:
                    raise ScaffoldError(
                        f"{problem.id}: cannot locate {part!r} after column {pos} of "
                        f"the canonical line {canon!r}")
            text = canon[pos:end]
            if not text.strip():
                raise ScaffoldError(
                    f"{problem.id}: the span struck out of {canon!r} is whitespace")
            found.append(text)
            pos = end + len(part)
        for offset, text in enumerate(found):
            gloss = glosses[offset] if offset < len(glosses) else (
                glosses[0] if len(glosses) == 1 and len(found) == 1 else "")
            nth = 1 + sum(1 for earlier in found[:offset] if earlier == text)
            spans.append({"line": cindex, "text": text, "gloss": gloss, "nth": nth})
    if not spans:
        raise ScaffoldError(f"{problem.id}: starter carries {MARKER} but no span "
                            f"could be read out of it")
    return spans
