"""The language itself: the mechanics that have to cost nothing to type.

Every other family in this corpus asks the player to *choose* something — a
structure, a pattern, an algorithm. This one does not. It drills the forms:
a comprehension with a condition, a sort by the second element, a dict built
from a zip. The content changes, the shape repeats, and the repetition is the
entire point. Under timed practical pressure the thing that fails first is not the
idea, it is the fingers.

Nineteen topics, each one walked up the same ramp:

  GUIDED    complete, working code with a single `__BLANK__`. The player types
            one expression into a program that already runs. MISSING_RUNE,
            because a one-token hole is not a blank-screen fight.
  TUTORIAL  a skeleton whose comments name each step. Bodies, never structure.
  EASY      signature plus one orienting comment.
  MEDIUM    only where the topic genuinely has a harder form worth meeting.

No topic is allowed to debut above GUIDED. That rule is the reason this family
exists in the shape it does: the previous corpus could teach `sorted(key=...)`
only by handing someone a MEDIUM problem that happened to need it.

Families are named to match the chapter ladder in `gauntlet/curriculum.py`
(the `onboarding_*` names chapters I-III already draw from), so these problems
are reachable the day they ship without the ladder needing to know this module
exists. Patterns are likewise held inside what those chapters permit.
"""
from __future__ import annotations

from ._base import code_problem

# The player this corpus was built for. Same weighting as python_village, since
# this is the same bottleneck seen from a different angle.
Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 1.5}

VIZ = {"type": "array_scan", "caption": "One form, practised until it is free."}

VISUAL = {
    "GUIDED": "The program runs already. Read it top to bottom, then fill the "
              "hole. You are finishing a sentence, not writing an essay.",
    "TUTORIAL": "One comment, one line. Write the first line, run it, then write "
                "the second.",
    "EASY": "Say the form out loud before you type it. The typing is the cheap part.",
    "MEDIUM": "Same form you have already drilled, one layer deeper.",
}


def _same_move(body: str) -> str:
    """Rung 4 of the hint tree, for the GUIDED rungs.

    A GUIDED solution is one line long, so the shared default — the first few
    lines of the canonical — would make Code Fragment identical to Phoenix at a
    third of the cost. These rungs show the same move on different data instead,
    which teaches the form without spending the problem.
    """
    return "```python\n# the same move, somewhere else:\n" + body.strip() + "\n```"


def drill(pid, title, tier, statement, fn, params, ref, canonical, visible,
          hidden, *, pattern, family, topic, realm="python_village", edges=(),
          starter="", starter_hint="", nudge="", pseudocode="", fragment="",
          failures=(), after="", time="O(n)", space="O(n)", constraints=()):
    """One rung of one topic. Everything the ramp needs, in one call."""
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=tier,
        family=family, profile_weight=Q, viz=VIZ, statement=statement,
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        visible=visible, hidden=hidden, edges=edges,
        time_complexity=time, space_complexity=space,
        constraints=list(constraints), failures=list(failures),
        nudge=nudge or "Reach for the built-in form before you write the loop.",
        visual=VISUAL[tier], pseudocode=pseudocode,
        fragment=fragment,
        starter_code=starter, starter_hint=starter_hint,
        encounter="MISSING_RUNE" if tier == "GUIDED" else "CODE_BATTLE",
        prerequisites=[after] if after else [],
        tags=["python", "language", "topic:" + topic, "scaffold:" + tier.lower()],
    )


# ---------------------------------------------------------------------------
# Reference implementations
# ---------------------------------------------------------------------------
#
# Written against the statement, not against the canonical solutions below. The
# whole safety property of this corpus is that these two were typed separately
# and still agree on every test.

# -- truthiness ---------------------------------------------------------------
def _or_default(value, fallback): return value or fallback
def _drop_falsy(items): return [v for v in items if v]
def _flag_split(config):
    on = sorted(k for k, v in config.items() if v)
    off = sorted(k for k, v in config.items() if not v)
    return [on, off]

# -- f-strings ----------------------------------------------------------------
def _price_tag(name, cost): return "%s: %.2f" % (name, cost)
def _progress_line(done, total):
    return "{}/{} ({:.0f}%)".format(done, total, 100.0 * done / total)
def _banner(title, width):
    pad = max(0, width - len(title))
    left = pad // 2
    return "-" * left + title + "-" * (pad - left)

# -- slicing ------------------------------------------------------------------
def _last_three(items): return items[max(0, len(items) - 3):]
def _middle(items): return items[1:len(items) - 1] if len(items) > 2 else []
def _every_other_from(items, start):
    return [items[i] for i in range(start, len(items), 2)]
def _windows(items, size):
    if size <= 0 or size > len(items):
        return []
    return [items[i:i + size] for i in range(len(items) - size + 1)]

# -- list comprehensions ------------------------------------------------------
def _squares_of_evens(nums):
    out = []
    for n in nums:
        if n % 2 == 0:
            out.append(n * n)
    return out
def _long_words(words, n): return [w for w in words if len(w) > n]
def _upper_initials(names): return [nm[0].upper() for nm in names if nm]
def _flatten_positive(rows):
    out = []
    for row in rows:
        for v in row:
            if v > 0:
                out.append(v)
    return out

# -- dict comprehensions ------------------------------------------------------
def _lengths(words): return {w: len(w) for w in words}
def _invert(mapping):
    out = {}
    for k, v in mapping.items():
        out[v] = k
    return out
def _filter_scores(scores, floor):
    return {k: v for k, v in scores.items() if v >= floor}

# -- sets ---------------------------------------------------------------------
def _unique_lengths(words): return {len(w) for w in words}
def _shared(a, b): return set(a) & set(b)
def _missing_keys(required, provided):
    have = set(provided)
    return sorted(k for k in set(required) if k not in have)

# -- enumerate ----------------------------------------------------------------
def _numbered_lines(lines):
    return ["%d. %s" % (i, ln) for i, ln in enumerate(lines, 1)]
def _indices_of(items, target):
    return [i for i, v in enumerate(items) if v == target]
def _first_duplicate_index(items):
    seen = set()
    for i, v in enumerate(items):
        if v in seen:
            return i
        seen.add(v)
    return -1

# -- zip ----------------------------------------------------------------------
def _pair_up(keys, values): return dict(zip(keys, values))
def _dot_pairs(a, b):
    total = 0
    for x, y in zip(a, b):
        total += x * y
    return total
def _columns(rows):
    if not rows:
        return []
    return [[row[c] for row in rows] for c in range(len(rows[0]))]
def _merge_records(names, scores, tiers):
    out = {}
    for n, s, t in zip(names, scores, tiers):
        if s >= 0:
            out[n] = [s, t]
    return out

# -- sorted with a key --------------------------------------------------------
def _by_second(pairs): return sorted((list(p) for p in pairs), key=lambda p: p[1])
def _by_length(words): return sorted(words, key=len)
def _by_score_desc(scores):
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [[k, v] for k, v in ordered]
def _rank_users(records):
    order = sorted(records, key=lambda r: (-r["score"], r["age"], r["name"]))
    return [r["name"] for r in order]

# -- min/max with a key -------------------------------------------------------
def _longest(words): return max(words, key=len)
def _cheapest(items): return min(items, key=lambda it: it[1])[0]
def _busiest_hour(counts): return min(counts, key=lambda h: (-counts[h], h))

# -- any / all ----------------------------------------------------------------
def _has_negative(nums): return any(n < 0 for n in nums)
def _all_strong(passwords, n): return all(len(p) >= n for p in passwords)
def _validate_rows(rows, width):
    return [all(len(r) == width for r in rows), any(len(r) == 0 for r in rows)]

# -- unpacking ----------------------------------------------------------------
def _swap(pair): return [pair[1], pair[0]]
def _head_and_rest(items): return [items[0], list(items[1:])]
def _trim_ends(items): return [items[0], items[-1], list(items[1:-1])]

# -- *args and ** unpacking ---------------------------------------------------
def _total(*nums): return sum(nums)
def _join_all(sep, *parts): return sep.join(str(p) for p in parts)
def _format_user(values):
    active = values["active"] if "active" in values else True
    return "%s:%d:%s" % (values["name"], values["score"], "on" if active else "off")

# -- is vs == -----------------------------------------------------------------
def _is_missing(value): return value is None
def _count_missing(rows, key):
    n = 0
    for row in rows:
        if row.get(key) is None:
            n += 1
    return n
def _fill_blanks(values, default):
    return [default if v is None else v for v in values]

# -- ternary ------------------------------------------------------------------
def _sign_word(n): return "positive" if n > 0 else "not positive"
def _clamp_label(n, lo, hi):
    if n < lo:
        return "low"
    if n > hi:
        return "high"
    return "ok"
def _statuses(codes): return ["ok" if c < 400 else "error" for c in codes]

# -- range and loops ----------------------------------------------------------
def _multiples(n, k):
    out, v = [], 0
    while v < n:
        out.append(v)
        v += k
    return out
def _sum_range(lo, hi):
    total = 0
    for v in range(lo, hi + 1):
        total += v
    return total
def _reversed_items(items):
    return [items[i] for i in range(len(items) - 1, -1, -1)]

# -- nested data --------------------------------------------------------------
def _user_city(record): return record["address"]["city"]
def _safe_city(record):
    if "address" not in record:
        return "unknown"
    inner = record["address"]
    return inner["city"] if "city" in inner else "unknown"
def _team_members(org):
    names = []
    for team in org["teams"]:
        for member in team["members"]:
            names.append(member)
    return sorted(names)
def _deep_get(data, path, default):
    node = data
    for step in path:
        if isinstance(node, dict):
            if step not in node:
                return default
            node = node[step]
            continue
        if isinstance(node, list) and isinstance(step, int) and 0 <= step < len(node):
            node = node[step]
            continue
        return default
    return node

# -- default arguments --------------------------------------------------------
def _greet(name, greeting="Hello"): return greeting + ", " + name
def _repeat_join(items, sep=", ", times=1):
    return sep.join([str(v) for v in items] * times)
def _add_tag(tag, tags=None):
    if tags is None:
        tags = []
    return list(tags) + [tag]

# -- tuples -------------------------------------------------------------------
def _as_pair(a, b): return [a, b]
def _unzip(pairs):
    return [[p[0] for p in pairs], [p[1] for p in pairs]]
def _pair_counts(pairs):
    counts = {}
    for pair in pairs:
        key = (pair[0], pair[1])
        counts[key] = counts.get(key, 0) + 1
    return sorted([[a, b, n] for (a, b), n in counts.items()])


def build() -> list:
    return [
        # -- topic 1: truthiness ---------------------------------------------
        drill(
            "lang-truthy-guided", "The Falsy Five", "GUIDED",
            """
            Python calls a value *falsy* if it behaves like False in a condition:
            `0`, `""`, `[]`, `{}` and `None` all do. Everything else is truthy.
            `a or b` hands back `a` when `a` is truthy, otherwise `b`.
            Return `value` unless it is falsy, in which case return `fallback`.
            """,
            "or_default", "value, fallback", _or_default,
            """
            def or_default(value, fallback):
                # `or` does not return True or False here. It returns one of the
                # two operands, which is exactly what makes it a default.
                return value or fallback
            """,
            [("empty string", ["", "anon"]), ("real name", ["root", "anon"])],
            [("zero", [0, 5]), ("nonzero", [7, 5]), ("empty list", [[], [1]])],
            edges=[("none", [None, "fallback"])],
            pattern="STRING", family="onboarding_conditionals", topic="truthiness",
            starter="""
            def or_default(value, fallback):
                # One word goes in the hole, and it is not `if`.
                return value __BLANK__ fallback
            """,
            nudge="`or` short-circuits: it evaluates the left side, and only "
                  "reaches for the right side if the left one was falsy.",
            pseudocode="return value or fallback",
            fragment=_same_move('name = supplied or "anonymous"'),
            failures=["Writing `if value != None` — that is a different question, "
                      "and it says True for 0 and for the empty string"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-truthy-tutorial", "Sweeping the Blanks", "TUTORIAL",
            """
            Return a new list holding only the truthy values of `items`, in the
            order they appeared. `[0, 1, "", "a"]` gives `[1, "a"]`.
            """,
            "drop_falsy", "items", _drop_falsy,
            """
            def drop_falsy(items):
                kept = []
                for value in items:
                    # `if value:` asks about truthiness, not about equality.
                    if value:
                        kept.append(value)
                return kept
            """,
            [("mixed", [[0, 1, "", "a"]]), ("all truthy", [[1, 2, 3]])],
            [("all falsy", [[0, "", None]]), ("nested empties", [[[], [1], {}]]),
             ("negatives are truthy", [[-1, 0, -2]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_conditionals", topic="truthiness",
            after="lang-truthy-guided",
            starter="""
            def drop_falsy(items):
                # 1. start an empty list called `kept`
                # 2. loop over `items`
                # 3. if the value is truthy, append it to `kept`
                # 4. return `kept`
                pass
            """,
            nudge="-1 is truthy. Only zero is falsy among the numbers.",
            pseudocode="kept = []\nfor value in items:\n    if value: kept.append(value)\nreturn kept",
            failures=["Filtering with `if value > 0`, which drops strings and "
                      "raises TypeError on them"],
        ),

        drill(
            "lang-truthy-easy", "The Settings Audit", "EASY",
            """
            `config` maps a setting name to its value. Return a list of two lists:
            the names whose value is truthy, and the names whose value is falsy.
            Both lists sorted alphabetically.
            """,
            "flag_split", "config", _flag_split,
            """
            def flag_split(config):
                on = sorted(name for name, value in config.items() if value)
                off = sorted(name for name, value in config.items() if not value)
                return [on, off]
            """,
            [("mixed", [{"debug": False, "path": "/etc", "retries": 0, "tls": True}]),
             ("all on", [{"a": 1, "b": "yes"}])],
            [("all off", [{"a": 0, "b": "", "c": None}]),
             ("empty containers are falsy", [{"hosts": [], "tags": ["x"]}]),
             ("one key", [{"solo": 3}])],
            edges=[("empty config", [{}])],
            pattern="HASH_MAP", family="onboarding_conditionals", topic="truthiness",
            after="lang-truthy-tutorial",
            starter_hint="two sorted lists: truthy names, then falsy names",
            nudge="`not value` is the falsy test. There is no need to compare "
                  "against False.",
            pseudocode="on = sorted(k for k, v in config.items() if v)\n"
                       "off = sorted(k for k, v in config.items() if not v)\n"
                       "return [on, off]",
        ),

        # -- topic 2: f-strings ----------------------------------------------
        drill(
            "lang-fstring-guided", "Naming the Price", "GUIDED",
            """
            An f-string interpolates expressions: `f"{name}"` drops the value of
            `name` straight into the text. After a colon comes a *format spec*:
            `:.2f` means "a float, two decimal places".
            Return `name`, a colon, a space, then `cost` to two decimal places.
            price_tag("rune", 3.5) gives "rune: 3.50".
            """,
            "price_tag", "name, cost", _price_tag,
            """
            def price_tag(name, cost):
                # The format spec lives after the colon, inside the braces.
                return f"{name}: {cost:.2f}"
            """,
            [("half", ["rune", 3.5]), ("whole", ["ward", 12.0])],
            [("rounds up", ["charm", 1.005]), ("zero", ["dust", 0.0]),
             ("long name", ["obsidian key", 199.999])],
            edges=[("negative", ["debt", -2.5])],
            pattern="STRING", family="onboarding_strings", topic="fstrings",
            starter="""
            def price_tag(name, cost):
                # The name is already placed. Fill in the number, to two decimals.
                return f"{name}: {__BLANK__}"
            """,
            nudge="Inside the braces: the expression, then `:`, then the spec.",
            pseudocode='return f"{name}: {cost:.2f}"',
            fragment=_same_move('line = f"{user}: {ratio:.1%}"'),
            failures=["Using str(cost), which prints 3.5 rather than 3.50"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-fstring-tutorial", "The Progress Line", "TUTORIAL",
            """
            Return a progress line: `done`, a slash, `total`, then the percentage
            in parentheses with no decimals and a percent sign.
            progress_line(3, 4) gives "3/4 (75%)". `total` is always at least 1.
            """,
            "progress_line", "done, total", _progress_line,
            """
            def progress_line(done, total):
                percent = 100 * done / total
                # `:.0f` rounds to a whole number without turning it into an int.
                return f"{done}/{total} ({percent:.0f}%)"
            """,
            [("three quarters", [3, 4]), ("half", [1, 2])],
            [("none done", [0, 8]), ("all done", [9, 9]), ("thirds", [1, 3])],
            edges=[("single step", [1, 1])],
            pattern="STRING", family="onboarding_strings", topic="fstrings",
            after="lang-fstring-guided",
            constraints=["1 <= total", "0 <= done <= total"],
            starter="""
            def progress_line(done, total):
                # 1. compute the percentage into `percent`
                # 2. return an f-string: done, "/", total, then " (percent%)"
                #    with the percentage formatted as :.0f
                pass
            """,
            nudge="A literal percent sign is just a percent sign. Only the braces "
                  "are special in an f-string.",
            pseudocode='percent = 100 * done / total\nreturn f"{done}/{total} ({percent:.0f}%)"',
            failures=["Integer division: `100 * done // total` loses the rounding"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-fstring-easy", "The Centred Banner", "EASY",
            """
            Return `title` centred inside a field `width` characters wide, padded
            with `-`. If the padding cannot be split evenly the extra dash goes on
            the right. If `title` is already at least `width` long, return it
            unchanged. banner("map", 9) gives "---map---".
            """,
            "banner", "title, width", _banner,
            """
            def banner(title, width):
                # fill character, then alignment, then width. The width itself can
                # be an expression in braces, which is why this is one line.
                return f"{title:-^{width}}"
            """,
            [("odd padding", ["map", 9]), ("uneven", ["ab", 5])],
            [("exact fit", ["four", 4]), ("too long", ["overlong", 3]),
             ("wide", ["x", 8])],
            edges=[("empty title", ["", 4])],
            pattern="STRING", family="onboarding_strings", topic="fstrings",
            after="lang-fstring-tutorial",
            starter_hint="one f-string: fill char, alignment, width",
            nudge="`^` centres, `<` left-aligns, `>` right-aligns. The character "
                  "before the alignment symbol is the fill.",
            pseudocode='return f"{title:-^{width}}"',
            failures=["str.center() splits uneven padding the other way round"],
            time="O(1)", space="O(1)",
        ),

        # -- topic 3: slicing ------------------------------------------------
        drill(
            "lang-slice-guided", "The Last Three Runes", "GUIDED",
            """
            A slice `items[a:b]` takes from index `a` up to but not including `b`.
            Leave either side off and Python uses the end of the list. A negative
            index counts from the back, so `-3` is the third-from-last.
            Return the last three items of `items`, in order. Fewer than three
            items means you return all of them — a slice never raises IndexError.
            """,
            "last_three", "items", _last_three,
            """
            def last_three(items):
                # -3 is where to start; the missing end means "to the end".
                return items[-3:]
            """,
            [("five", [[1, 2, 3, 4, 5]]), ("exactly three", [["a", "b", "c"]])],
            [("two", [[9, 8]]), ("one", [[7]]), ("strings", [["x", "y", "z", "w"]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_lists", topic="slicing",
            starter="""
            def last_three(items):
                # The colon is already there. The start index is not.
                return items[__BLANK__:]
            """,
            nudge="Counting from the back: -1 is the last, -2 the one before it.",
            pseudocode="return items[-3:]",
            fragment=_same_move("tail = log[-10:]"),
            failures=["items[len(items) - 3:] raises nothing but returns the whole "
                      "list backwards-indexed when the list is short"],
            time="O(k)", space="O(k)",
        ),

        drill(
            "lang-slice-tutorial", "Trimming Both Ends", "TUTORIAL",
            """
            Return everything except the first and last item of `items`. A list of
            two or fewer items has no middle, so return an empty list.
            middle([1, 2, 3, 4]) gives [2, 3].
            """,
            "middle", "items", _middle,
            """
            def middle(items):
                # 1 skips the head, -1 stops before the tail, and a slice that
                # crosses over itself is empty rather than an error.
                return items[1:-1]
            """,
            [("four", [[1, 2, 3, 4]]), ("three", [["a", "b", "c"]])],
            [("two", [[1, 2]]), ("one", [[5]]), ("long", [[1, 2, 3, 4, 5, 6]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_lists", topic="slicing",
            after="lang-slice-guided",
            starter="""
            def middle(items):
                # 1. slice from index 1
                # 2. stop at index -1
                # 3. return it. No length check is needed.
                pass
            """,
            nudge="You do not need an `if`. Try the slice on a one-element list "
                  "and see what it gives you.",
            pseudocode="return items[1:-1]",
            time="O(n)", space="O(n)",
        ),

        drill(
            "lang-slice-easy", "Every Other, From Here", "EASY",
            """
            A slice takes a third number, the step: `items[a:b:c]`. Return every
            second item of `items` beginning at index `start`.
            every_other_from([0, 1, 2, 3, 4], 1) gives [1, 3].
            `start` is never negative; a `start` past the end gives an empty list.
            """,
            "every_other_from", "items, start", _every_other_from,
            """
            def every_other_from(items, start):
                # No end index: start, nothing, step.
                return items[start::2]
            """,
            [("from one", [[0, 1, 2, 3, 4], 1]), ("from zero", [[0, 1, 2, 3, 4], 0])],
            [("from last", [[0, 1, 2, 3, 4], 4]), ("past the end", [[1, 2], 5]),
             ("strings", [["a", "b", "c", "d"], 1])],
            edges=[("empty list", [[], 0])],
            pattern="ARRAY", family="onboarding_lists", topic="slicing",
            after="lang-slice-tutorial",
            constraints=["0 <= start"],
            starter_hint="one slice with a start and a step, no end",
            nudge="Two colons, and nothing between them.",
            pseudocode="return items[start::2]",
        ),

        drill(
            "lang-slice-medium", "Every Window in the Wall", "MEDIUM",
            """
            Return every contiguous run of exactly `size` items from `items`, left
            to right, as a list of lists. If `size` is not positive, or longer than
            `items`, return an empty list.
            windows([1, 2, 3, 4], 2) gives [[1, 2], [2, 3], [3, 4]].
            """,
            "windows", "items, size", _windows,
            """
            def windows(items, size):
                if size <= 0 or size > len(items):
                    return []
                out = []
                # The last legal start is len - size, and range excludes its end.
                for i in range(len(items) - size + 1):
                    out.append(items[i:i + size])
                return out
            """,
            [("pairs", [[1, 2, 3, 4], 2]), ("triples", [[1, 2, 3, 4, 5], 3])],
            [("size one", [[1, 2, 3], 1]), ("whole list", [[1, 2, 3], 3]),
             ("too big", [[1, 2], 5])],
            edges=[("zero size", [[1, 2, 3], 0]), ("empty list", [[], 2])],
            pattern="ARRAY", family="onboarding_lists", topic="slicing",
            after="lang-slice-easy",
            starter_hint="guard the bad sizes, then one slice per start index",
            nudge="How many windows are there? One per legal starting index, and "
                  "the last legal start is len(items) - size.",
            pseudocode="if size <= 0 or size > len(items): return []\n"
                       "for i in range(len(items) - size + 1):\n"
                       "    out.append(items[i:i + size])",
            failures=["Off by one in the range bound, which drops the final window",
                      "Forgetting that size > len(items) must not produce a short "
                      "window"],
            time="O(n * k)", space="O(n * k)",
        ),

        # -- topic 4: list comprehensions ------------------------------------
        drill(
            "lang-listcomp-guided", "The Comprehension, With a Condition", "GUIDED",
            """
            A list comprehension is a loop and an append, written as one
            expression: `[f(x) for x in xs if cond(x)]`. The `if` filters; the
            expression in front transforms.
            Return the squares of the even numbers in `nums`, in order.
            squares_of_evens([1, 2, 3, 4]) gives [4, 16].
            """,
            "squares_of_evens", "nums", _squares_of_evens,
            """
            def squares_of_evens(nums):
                # Read it right to left: take n from nums, keep it if even,
                # then square it.
                return [n * n for n in nums if n % 2 == 0]
            """,
            [("mixed", [[1, 2, 3, 4]]), ("all even", [[2, 4]])],
            [("all odd", [[1, 3, 5]]), ("zero is even", [[0, 1]]),
             ("negatives", [[-2, -3, 4]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_comprehensions", topic="listcomp",
            realm="fields_of_syntax",
            starter="""
            def squares_of_evens(nums):
                # The transform and the loop are done. Write the filter.
                return [n * n for n in nums if __BLANK__]
            """,
            nudge="`n % 2` is the remainder after dividing by two. Even numbers "
                  "leave nothing behind.",
            pseudocode="return [n * n for n in nums if n % 2 == 0]",
            fragment=_same_move("[w for w in words if w.startswith('a')]"),
            failures=["`n % 2 = 0` is an assignment and a SyntaxError; the "
                      "comparison is `==`"],
        ),

        drill(
            "lang-listcomp-tutorial", "Only the Long Ones", "TUTORIAL",
            """
            Return the words in `words` that are strictly longer than `n`
            characters, in the order they appeared. Write it as one comprehension.
            """,
            "long_words", "words, n", _long_words,
            """
            def long_words(words, n):
                return [word for word in words if len(word) > n]
            """,
            [("threshold three", [["a", "abcd", "abc", "abcde"], 3]),
             ("keep all", [["hello", "world"], 2])],
            [("keep none", [["a", "b"], 5]), ("exact length excluded", [["abc"], 3]),
             ("empty strings", [["", "ab"], 0])],
            edges=[("empty list", [[], 2])],
            pattern="ARRAY", family="onboarding_comprehensions", topic="listcomp",
            realm="fields_of_syntax", after="lang-listcomp-guided",
            starter="""
            def long_words(words, n):
                # One line. The shape is [ KEEP for NAME in SEQUENCE if TEST ].
                pass
            """,
            nudge="Strictly longer. A word of exactly n characters does not survive.",
            pseudocode="return [w for w in words if len(w) > n]",
        ),

        drill(
            "lang-listcomp-easy", "Initials of the Named", "EASY",
            """
            Return the uppercase first letter of each name in `names`, skipping any
            empty strings. upper_initials(["ada", "", "bo"]) gives ["A", "B"].
            The filter has to run before the transform, or the empty string will
            raise IndexError.
            """,
            "upper_initials", "names", _upper_initials,
            """
            def upper_initials(names):
                # The `if` is evaluated before the expression in front of `for`,
                # which is what keeps name[0] safe here.
                return [name[0].upper() for name in names if name]
            """,
            [("one blank", [["ada", "", "bo"]]), ("none blank", [["root", "vail"]])],
            [("already upper", [["Ada", "BO"]]), ("all blank", [["", ""]]),
             ("single letters", [["x", "", "y"]])],
            edges=[("empty list", [[]])],
            pattern="STRING", family="onboarding_comprehensions", topic="listcomp",
            realm="fields_of_syntax", after="lang-listcomp-tutorial",
            starter_hint="filter the blanks, then take [0].upper()",
            nudge="`if name` is the truthiness test again. An empty string is falsy.",
            pseudocode="return [name[0].upper() for name in names if name]",
            failures=["Transforming before filtering: IndexError on the empty string"],
        ),

        drill(
            "lang-listcomp-medium", "Flattening the Ledger", "MEDIUM",
            """
            `rows` is a list of lists of numbers. Return a single flat list of every
            value greater than zero, keeping row order and then order within a row.
            flatten_positive([[1, -2], [3]]) gives [1, 3].
            The nested form reads in the same order as the nested loop it replaces.
            """,
            "flatten_positive", "rows", _flatten_positive,
            """
            def flatten_positive(rows):
                # Outer loop first, inner loop second, filter last — exactly the
                # order you would write the two `for` statements.
                return [value for row in rows for value in row if value > 0]
            """,
            [("two rows", [[[1, -2], [3]]]), ("all positive", [[[1, 2], [3, 4]]])],
            [("all negative", [[[-1], [-2]]]), ("zero excluded", [[[0, 1]]]),
             ("ragged", [[[1], [], [2, 3]]])],
            edges=[("empty outer", [[]]), ("all rows empty", [[[], []]])],
            pattern="ARRAY", family="onboarding_comprehensions", topic="listcomp",
            realm="fields_of_syntax", after="lang-listcomp-easy",
            starter_hint="two for clauses, then one if",
            nudge="Write the nested loop first, then read the clauses off it top "
                  "to bottom.",
            pseudocode="for row in rows:\n    for value in row:\n        if value > 0: keep",
            failures=["Reversing the two `for` clauses, which raises NameError "
                      "because the inner name is not bound yet"],
        ),

        # -- topic 5: dict comprehensions ------------------------------------
        drill(
            "lang-dictcomp-guided", "Building a Map in One Line", "GUIDED",
            """
            A dict comprehension looks like a list one with a colon in it:
            `{key_expr: value_expr for x in xs}`. Both halves are expressions.
            Return a dict mapping each word in `words` to its length.
            lengths(["ab", "c"]) gives {"ab": 2, "c": 1}.
            """,
            "lengths", "words", _lengths,
            """
            def lengths(words):
                # The key is the word, the value is how long it is.
                return {word: len(word) for word in words}
            """,
            [("two words", [["ab", "c"]]), ("one word", [["rune"]])],
            [("duplicates collapse", [["a", "a", "bb"]]),
             ("empty string key", [["", "x"]]), ("longer", [["alpha", "be", "g"]])],
            edges=[("empty list", [[]])],
            pattern="HASH_MAP", family="onboarding_comprehensions", topic="dictcomp",
            realm="fields_of_syntax",
            starter="""
            def lengths(words):
                # The key half is written. Write the value half.
                return {word: __BLANK__ for word in words}
            """,
            nudge="Braces with a colon make a dict. Braces without one make a set.",
            pseudocode="return {word: len(word) for word in words}",
            fragment=_same_move("{user: user.upper() for user in users}"),
            failures=["Duplicate keys do not error — the last one silently wins"],
        ),

        drill(
            "lang-dictcomp-tutorial", "Turning the Map Around", "TUTORIAL",
            """
            Return a new dict with the keys and values of `mapping` swapped.
            If two keys share a value, the one that appears later wins, which is
            just what assignment does.
            invert({"a": 1, "b": 2}) gives {1: "a", 2: "b"}.
            """,
            "invert", "mapping", _invert,
            """
            def invert(mapping):
                # .items() yields (key, value) pairs, and the `for` target unpacks
                # them into two names.
                return {value: key for key, value in mapping.items()}
            """,
            [("two entries", [{"a": 1, "b": 2}]), ("one entry", [{"solo": 9}])],
            [("string values", [{"x": "p", "y": "q"}]),
             ("collision, last wins", [{"a": 1, "b": 1}]),
             ("numeric keys", [{"a": 0, "b": -1}])],
            edges=[("empty", [{}])],
            pattern="HASH_MAP", family="onboarding_comprehensions", topic="dictcomp",
            realm="fields_of_syntax", after="lang-dictcomp-guided",
            starter="""
            def invert(mapping):
                # 1. loop over mapping.items(), unpacking into key and value
                # 2. build {value: key}
                # 3. return it
                pass
            """,
            nudge="`for key, value in mapping.items()` — the unpacking happens in "
                  "the `for` target, exactly as it would in a plain loop.",
            pseudocode="return {v: k for k, v in mapping.items()}",
            failures=["Looping over `mapping` alone gives you keys, not pairs"],
        ),

        drill(
            "lang-dictcomp-easy", "The Passing Grades", "EASY",
            """
            `scores` maps a name to a number. Return a new dict holding only the
            entries whose value is greater than or equal to `floor`. The original
            must not be modified.
            """,
            "filter_scores", "scores, floor", _filter_scores,
            """
            def filter_scores(scores, floor):
                return {name: value for name, value in scores.items()
                        if value >= floor}
            """,
            [("some pass", [{"ada": 90, "bo": 40}, 50]),
             ("all pass", [{"ada": 90, "bo": 80}, 10])],
            [("none pass", [{"ada": 10}, 50]),
             ("boundary included", [{"ada": 50}, 50]),
             ("negative floor", [{"ada": -5, "bo": 1}, -5])],
            edges=[("empty", [{}, 0])],
            pattern="HASH_MAP", family="onboarding_comprehensions", topic="dictcomp",
            realm="fields_of_syntax", after="lang-dictcomp-tutorial",
            starter_hint="one dict comprehension with an if clause",
            nudge="Same three clauses as a list comprehension, with a colon in the "
                  "output half.",
            pseudocode="return {k: v for k, v in scores.items() if v >= floor}",
            failures=["Deleting from `scores` while iterating it — "
                      "RuntimeError: dictionary changed size during iteration"],
        ),

        # -- topic 6: sets ----------------------------------------------------
        drill(
            "lang-set-guided", "The Set Comprehension", "GUIDED",
            """
            A set holds each value once and has no order. Braces with no colon
            build one: `{expr for x in xs}`.
            Return the set of distinct word lengths in `words`.
            unique_lengths(["ab", "cd", "e"]) gives {2, 1}.
            """,
            "unique_lengths", "words", _unique_lengths,
            """
            def unique_lengths(words):
                # Two words of the same length contribute one element, not two.
                return {len(word) for word in words}
            """,
            [("one repeat", [["ab", "cd", "e"]]), ("all distinct", [["a", "bb", "ccc"]])],
            [("all same", [["xx", "yy"]]), ("with empty string", [["", "a"]]),
             ("single", [["rune"]])],
            edges=[("empty list", [[]])],
            pattern="SET", family="onboarding_set", topic="sets",
            starter="""
            def unique_lengths(words):
                # No colon inside these braces — that is what makes it a set.
                return {__BLANK__ for word in words}
            """,
            nudge="`{}` on its own is an empty dict, not an empty set. The empty "
                  "set is `set()`.",
            pseudocode="return {len(w) for w in words}",
            fragment=_same_move("{ip.split('.')[0] for ip in addresses}"),
        ),

        drill(
            "lang-set-tutorial", "What Both Lists Hold", "TUTORIAL",
            """
            Return the set of values that appear in both `a` and `b`.
            `set(a) & set(b)` is the intersection; `|` is union and `-` is
            difference. shared([1, 2, 3], [2, 3, 4]) gives {2, 3}.
            """,
            "shared", "a, b", _shared,
            """
            def shared(a, b):
                # Building both sets costs one pass each and buys O(1) membership.
                return set(a) & set(b)
            """,
            [("overlap", [[1, 2, 3], [2, 3, 4]]), ("no overlap", [[1], [2]])],
            [("duplicates ignored", [[1, 1, 2], [1]]),
             ("identical", [[5, 6], [6, 5]]), ("strings", [["a", "b"], ["b", "c"]])],
            edges=[("one empty", [[], [1, 2]])],
            pattern="SET", family="onboarding_set", topic="sets",
            after="lang-set-guided",
            starter="""
            def shared(a, b):
                # 1. turn each list into a set
                # 2. intersect them with &
                # 3. return the result
                pass
            """,
            nudge="`&` between two sets, not between a set and a list.",
            pseudocode="return set(a) & set(b)",
            failures=["`a & b` on two lists raises TypeError — the conversion is "
                      "not implicit"],
        ),

        drill(
            "lang-set-easy", "What the Config Is Missing", "EASY",
            """
            Return the sorted list of names in `required` that do not appear in
            `provided`. Each name appears at most once in the answer. Build a set
            from `provided` first so each membership test is O(1) rather than a
            scan.
            """,
            "missing_keys", "required, provided", _missing_keys,
            """
            def missing_keys(required, provided):
                have = set(provided)
                # sorted() over a set gives a list, and a deterministic one, which
                # is the only reason this is testable at all.
                return sorted(set(required) - have)
            """,
            [("two missing", [["host", "port", "tls"], ["host"]]),
             ("none missing", [["host"], ["host", "port"]])],
            [("all missing", [["a", "b"], []]),
             ("duplicates in required", [["a", "a", "b"], ["b"]]),
             ("order irrelevant", [["c", "a"], ["a"]])],
            edges=[("both empty", [[], []])],
            pattern="SET", family="onboarding_set", topic="sets",
            after="lang-set-tutorial",
            starter_hint="a set of what we have, then the sorted difference",
            nudge="Set difference is `-`. Sorting it at the end is what makes the "
                  "answer reproducible.",
            pseudocode="have = set(provided)\nreturn sorted(set(required) - have)",
            failures=["Returning the set itself: sets have no order, so the "
                      "output would not be stable"],
        ),

        # -- topic 7: enumerate ----------------------------------------------
        drill(
            "lang-enumerate-guided", "Index and Value Together", "GUIDED",
            """
            `enumerate(xs)` yields `(index, value)` pairs so you never need
            `range(len(xs))`. A second argument changes where the count starts.
            Return each line of `lines` prefixed with its 1-based number, a dot and
            a space. numbered_lines(["a", "b"]) gives ["1. a", "2. b"].
            """,
            "numbered_lines", "lines", _numbered_lines,
            """
            def numbered_lines(lines):
                # The second argument to enumerate is the starting count, not an
                # offset applied to the value.
                return [f"{i}. {line}" for i, line in enumerate(lines, 1)]
            """,
            [("two lines", [["a", "b"]]), ("one line", [["only"]])],
            [("ten lines", [["x"] * 10]), ("blank line", [["", "b"]]),
             ("spaces", [["a b", "c"]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_idioms", topic="enumerate",
            realm="fields_of_syntax",
            starter="""
            def numbered_lines(lines):
                # Numbering starts at one, not zero. Say so.
                return [f"{i}. {line}" for i, line in enumerate(lines, __BLANK__)]
            """,
            nudge="Counting from 1 is a parameter, not arithmetic on `i`.",
            pseudocode='return [f"{i}. {line}" for i, line in enumerate(lines, 1)]',
            fragment=_same_move("for rank, name in enumerate(winners, 1): ..."),
            failures=["Writing `i + 1` inside the f-string works, but the start "
                      "argument is what the reader expects to see"],
        ),

        drill(
            "lang-enumerate-tutorial", "Every Place It Appears", "TUTORIAL",
            """
            Return the list of 0-based indices at which `target` appears in
            `items`, ascending. indices_of(["a", "b", "a"], "a") gives [0, 2].
            """,
            "indices_of", "items, target", _indices_of,
            """
            def indices_of(items, target):
                found = []
                for i, value in enumerate(items):
                    if value == target:
                        found.append(i)
                return found
            """,
            [("twice", [["a", "b", "a"], "a"]), ("once", [[1, 2, 3], 2])],
            [("absent", [[1, 2], 9]), ("every position", [[7, 7, 7], 7]),
             ("first only", [["x", "y"], "x"])],
            edges=[("empty", [[], 1])],
            pattern="ARRAY", family="onboarding_idioms", topic="enumerate",
            realm="fields_of_syntax", after="lang-enumerate-guided",
            starter="""
            def indices_of(items, target):
                # 1. start an empty list `found`
                # 2. loop with enumerate, unpacking index and value
                # 3. append the index when the value matches
                # 4. return `found`
                pass
            """,
            nudge="You want the index, so the loop has to carry it. That is the "
                  "whole reason enumerate exists.",
            pseudocode="for i, value in enumerate(items):\n    if value == target: found.append(i)",
            failures=["`items.index(target)` finds only the first one"],
        ),

        drill(
            "lang-enumerate-easy", "Where It Repeats", "EASY",
            """
            Return the index of the first item in `items` that has already been
            seen earlier in the list, or -1 if every item is distinct.
            first_duplicate_index([1, 2, 1]) gives 2, because index 2 is where the
            repeat is noticed.
            """,
            "first_duplicate_index", "items", _first_duplicate_index,
            """
            def first_duplicate_index(items):
                seen = set()
                for index, value in enumerate(items):
                    if value in seen:
                        return index
                    seen.add(value)
                return -1
            """,
            [("repeat at two", [[1, 2, 1]]), ("no repeat", [[1, 2, 3]])],
            [("immediate repeat", [[4, 4]]), ("late repeat", [["a", "b", "c", "a"]]),
             ("single", [[9]])],
            edges=[("empty", [[]])],
            pattern="SET", family="onboarding_idioms", topic="enumerate",
            realm="fields_of_syntax", after="lang-enumerate-tutorial",
            starter_hint="a set of what you have seen, plus the index from enumerate",
            nudge="Check membership before adding, or every item looks like a "
                  "duplicate of itself.",
            pseudocode="seen = set()\nfor i, v in enumerate(items):\n"
                       "    if v in seen: return i\n    seen.add(v)\nreturn -1",
            failures=["Adding to the set before testing it, which returns 0 for "
                      "every non-empty list"],
        ),

        # -- topic 8: zip -----------------------------------------------------
        drill(
            "lang-zip-guided", "Two Lists, One Dict", "GUIDED",
            """
            `zip(a, b)` walks two sequences in step, yielding pairs, and stops at
            the shorter one. `dict(...)` over those pairs builds a mapping.
            Return a dict pairing each key in `keys` with the value at the same
            position in `values`. pair_up(["a", "b"], [1, 2]) gives {"a": 1, "b": 2}.
            """,
            "pair_up", "keys, values", _pair_up,
            """
            def pair_up(keys, values):
                # dict() accepts any iterable of two-item pairs, which is exactly
                # what zip hands it.
                return dict(zip(keys, values))
            """,
            [("two each", [["a", "b"], [1, 2]]), ("one each", [["solo"], [9]])],
            [("extra values ignored", [["a"], [1, 2, 3]]),
             ("extra keys ignored", [["a", "b", "c"], [1]]),
             ("string values", [["x", "y"], ["p", "q"]])],
            edges=[("both empty", [[], []])],
            pattern="HASH_MAP", family="onboarding_idioms", topic="zip",
            realm="fields_of_syntax",
            starter="""
            def pair_up(keys, values):
                # dict() is already there. Give it the pairs.
                return dict(__BLANK__)
            """,
            nudge="zip takes both sequences as arguments and returns the pairs.",
            pseudocode="return dict(zip(keys, values))",
            fragment=_same_move("row = dict(zip(headers, fields))"),
            failures=["zip stops at the shorter input and says nothing about it"],
        ),

        drill(
            "lang-zip-tutorial", "Multiplying in Step", "TUTORIAL",
            """
            Return the sum of `a[i] * b[i]` over every position both lists have.
            If one list is shorter, stop there. dot_pairs([1, 2], [3, 4]) gives 11.
            """,
            "dot_pairs", "a, b", _dot_pairs,
            """
            def dot_pairs(a, b):
                # The `for` target unpacks each pair into two names.
                return sum(x * y for x, y in zip(a, b))
            """,
            [("two each", [[1, 2], [3, 4]]), ("three each", [[1, 1, 1], [2, 3, 4]])],
            [("uneven", [[1, 2, 3], [10]]), ("zeros", [[0, 5], [7, 0]]),
             ("negatives", [[-1, 2], [3, -4]])],
            edges=[("both empty", [[], []])],
            pattern="ARRAY", family="onboarding_idioms", topic="zip",
            realm="fields_of_syntax", after="lang-zip-guided",
            starter="""
            def dot_pairs(a, b):
                # 1. zip the two lists
                # 2. multiply each pair
                # 3. sum the products and return the total
                pass
            """,
            nudge="`sum(...)` accepts a generator expression directly; the square "
                  "brackets are optional and cost memory.",
            pseudocode="return sum(x * y for x, y in zip(a, b))",
            time="O(n)", space="O(1)",
        ),

        drill(
            "lang-zip-easy", "Turning the Grid", "EASY",
            """
            `rows` is a rectangular list of lists. Return its transpose: the first
            output row is the first element of every input row, and so on.
            columns([[1, 2], [3, 4]]) gives [[1, 3], [2, 4]].
            `zip(*rows)` unpacks the rows into separate arguments, which is the
            whole trick.
            """,
            "columns", "rows", _columns,
            """
            def columns(rows):
                # zip(*rows) is zip(rows[0], rows[1], ...). Each tuple it yields is
                # one column, and list() turns it into the list the tests expect.
                return [list(column) for column in zip(*rows)]
            """,
            [("square", [[[1, 2], [3, 4]]]), ("wide", [[[1, 2, 3], [4, 5, 6]]])],
            [("single row", [[[1, 2, 3]]]), ("single column", [[[1], [2], [3]]]),
             ("strings", [[["a", "b"], ["c", "d"]]])],
            edges=[("no rows", [[]])],
            pattern="ARRAY", family="onboarding_idioms", topic="zip",
            realm="fields_of_syntax", after="lang-zip-tutorial",
            starter_hint="zip(*rows), then list() each column",
            nudge="Without the star you zip one argument — the list of rows — and "
                  "get the rows back.",
            pseudocode="return [list(col) for col in zip(*rows)]",
            failures=["Returning tuples instead of lists",
                      "Forgetting the star, which yields one-element tuples"],
        ),

        drill(
            "lang-zip-medium", "Three Lists, One Record", "MEDIUM",
            """
            `names`, `scores` and `tiers` are parallel lists. Return a dict mapping
            each name to the two-item list `[score, tier]`, skipping any entry whose
            score is negative. zip takes as many sequences as you give it.
            A name appearing twice keeps its later record.
            """,
            "merge_records", "names, scores, tiers", _merge_records,
            """
            def merge_records(names, scores, tiers):
                out = {}
                for name, score, tier in zip(names, scores, tiers):
                    if score >= 0:
                        out[name] = [score, tier]
                return out
            """,
            [("three rows", [["ada", "bo"], [10, 20], ["A", "B"]]),
             ("one row", [["solo"], [5], ["C"]])],
            [("negative skipped", [["ada", "bo"], [-1, 4], ["A", "B"]]),
             ("zero kept", [["ada"], [0], ["D"]]),
             ("duplicate name", [["ada", "ada"], [1, 2], ["A", "B"]])],
            edges=[("all empty", [[], [], []]),
                   ("all negative", [["a"], [-5], ["Z"]])],
            pattern="HASH_MAP", family="onboarding_idioms", topic="zip",
            realm="fields_of_syntax", after="lang-zip-easy",
            starter_hint="one zip over three lists, one filter, one dict",
            nudge="The `for` target takes three names because zip yields triples.",
            pseudocode="for name, score, tier in zip(names, scores, tiers):\n"
                       "    if score >= 0: out[name] = [score, tier]",
            failures=["Indexing all three lists by hand, which breaks the moment "
                      "they differ in length"],
        ),

        # -- topic 9: sorted with a key ---------------------------------------
        drill(
            "lang-sortkey-guided", "Sorting by the Second Element", "GUIDED",
            """
            `sorted(xs, key=f)` calls `f` on each item and orders by the result.
            The items themselves come back unchanged. A `lambda` is a small
            function written inline: `lambda w: len(w)` means "given w, hand back
            its length".
            Sort `pairs` (a list of two-item lists) by the second element,
            ascending. by_second([["a", 3], ["b", 1]]) gives [["b", 1], ["a", 3]].
            """,
            "by_second", "pairs", _by_second,
            """
            def by_second(pairs):
                # sorted() is stable, so pairs tying on the second element keep
                # their original relative order.
                return sorted(pairs, key=lambda pair: pair[1])
            """,
            [("two pairs", [[["a", 3], ["b", 1]]]),
             ("three pairs", [[["x", 2], ["y", 0], ["z", 1]]])],
            [("already sorted", [[["a", 1], ["b", 2]]]),
             ("ties keep order", [[["a", 1], ["b", 1]]]),
             ("negatives", [[["a", 0], ["b", -3]]])],
            edges=[("empty", [[]]), ("single", [[["only", 7]]])],
            pattern="SORTING", family="onboarding_idioms", topic="sortkey",
            realm="fields_of_syntax",
            starter="""
            def by_second(pairs):
                # The key function is the hole. It receives one pair.
                return sorted(pairs, key=lambda pair: __BLANK__)
            """,
            nudge="Index 1 is the second element. Index 0 is the first.",
            pseudocode="return sorted(pairs, key=lambda p: p[1])",
            fragment=_same_move("sorted(events, key=lambda e: e[0])"),
            failures=["Calling the key: `key=lambda p: p[1]()` — sorted calls it "
                      "for you, once per item"],
            time="O(n log n)",
        ),

        drill(
            "lang-sortkey-tutorial", "Shortest First", "TUTORIAL",
            """
            Return `words` sorted by length, shortest first. Words of equal length
            keep the order they came in. `len` is already a function, so it can be
            the key directly — no lambda needed.
            """,
            "by_length", "words", _by_length,
            """
            def by_length(words):
                # `key=len`, not `key=len(words)`. The key is the function itself.
                return sorted(words, key=len)
            """,
            [("mixed", [["ccc", "a", "bb"]]), ("already short first", [["a", "bb"]])],
            [("ties keep order", [["bb", "aa"]]), ("with empty string", [["a", ""]]),
             ("one word", [["alone"]])],
            edges=[("empty", [[]])],
            pattern="SORTING", family="onboarding_idioms", topic="sortkey",
            realm="fields_of_syntax", after="lang-sortkey-guided",
            starter="""
            def by_length(words):
                # One line: sorted(), with len as the key.
                pass
            """,
            nudge="Pass the name `len`, without parentheses.",
            pseudocode="return sorted(words, key=len)",
            failures=["`words.sort()` returns None; `sorted(words)` returns a list"],
            time="O(n log n)",
        ),

        drill(
            "lang-sortkey-easy", "The Leaderboard", "EASY",
            """
            `scores` maps a name to a number. Return a list of `[name, score]` pairs
            ordered by score descending, and by name ascending where scores tie.
            A tuple key sorts by its first element, then its second, so
            `key=lambda kv: (-kv[1], kv[0])` says exactly that.
            """,
            "by_score_desc", "scores", _by_score_desc,
            """
            def by_score_desc(scores):
                ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
                # .items() yields tuples; the tests compare against lists.
                return [[name, score] for name, score in ordered]
            """,
            [("clear order", [{"ada": 10, "bo": 30}]),
             ("tie broken by name", [{"bo": 5, "ada": 5}])],
            [("three", [{"a": 1, "b": 3, "c": 2}]),
             ("negatives", [{"a": -1, "b": -5}]), ("single", [{"solo": 0}])],
            edges=[("empty", [{}])],
            pattern="SORTING", family="onboarding_idioms", topic="sortkey",
            realm="fields_of_syntax", after="lang-sortkey-tutorial",
            starter_hint="sorted(scores.items(), key=...) then rebuild as lists",
            nudge="Negating the score reverses that field alone, which is what lets "
                  "the name stay ascending.",
            pseudocode="sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))",
            failures=["`reverse=True` reverses every field, including the name"],
            time="O(n log n)",
        ),

        drill(
            "lang-sortkey-medium", "Ranking the Fellowship", "MEDIUM",
            """
            `records` is a list of dicts, each with "name", "score" and "age".
            Return the names ordered by score descending, then age ascending, then
            name ascending. One `sorted` call with one tuple key.
            """,
            "rank_users", "records", _rank_users,
            """
            def rank_users(records):
                order = sorted(records,
                               key=lambda r: (-r["score"], r["age"], r["name"]))
                return [record["name"] for record in order]
            """,
            [("by score", [[{"name": "ada", "score": 5, "age": 30},
                            {"name": "bo", "score": 9, "age": 20}]]),
             ("tie on score", [[{"name": "ada", "score": 5, "age": 40},
                                {"name": "bo", "score": 5, "age": 20}]])],
            [("tie on score and age", [[{"name": "bo", "score": 1, "age": 1},
                                        {"name": "ada", "score": 1, "age": 1}]]),
             ("single", [[{"name": "solo", "score": 0, "age": 1}]]),
             ("three", [[{"name": "a", "score": 2, "age": 5},
                         {"name": "b", "score": 2, "age": 4},
                         {"name": "c", "score": 3, "age": 9}]])],
            edges=[("empty", [[]])],
            pattern="SORTING", family="onboarding_idioms", topic="sortkey",
            realm="fields_of_syntax", after="lang-sortkey-easy",
            starter_hint="one sorted() with a three-element tuple key",
            nudge="Only the numeric fields can be negated. Descending on a string "
                  "needs a different approach entirely.",
            pseudocode="sorted(records, key=lambda r: (-r['score'], r['age'], r['name']))",
            failures=["Sorting three times in a row and hoping stability saves you "
                      "— it does, but only if you sort in reverse priority order"],
            time="O(n log n)",
        ),

        # -- topic 10: min/max with a key -------------------------------------
        drill(
            "lang-maxkey-guided", "The Longest Word", "GUIDED",
            """
            `max(xs, key=f)` returns the *item* whose `f(item)` is largest, not the
            largest `f(item)`. Ties go to the earliest item. `min` works the same
            way in the other direction.
            Return the longest word in `words`, which always holds at least one.
            """,
            "longest", "words", _longest,
            """
            def longest(words):
                # Without the key this returns the alphabetically last word, which
                # is a different question with the same shape.
                return max(words, key=len)
            """,
            [("clear winner", [["a", "abc", "ab"]]), ("two words", [["xy", "z"]])],
            [("tie goes to first", [["ab", "cd"]]), ("one word", [["solo"]]),
             ("empty string present", [["", "a"]])],
            edges=[("all same length", [["aa", "bb", "cc"]])],
            pattern="ARRAY", family="onboarding_idioms", topic="minmaxkey",
            realm="fields_of_syntax",
            constraints=["words holds at least one string"],
            starter="""
            def longest(words):
                # Which measurement should max compare by?
                return max(words, key=__BLANK__)
            """,
            nudge="`len` is a function. Hand it over without calling it.",
            pseudocode="return max(words, key=len)",
            fragment=_same_move("newest = max(files, key=lambda f: f['mtime'])"),
            failures=["`max(len(w) for w in words)` returns the length, not the word"],
            time="O(n)", space="O(1)",
        ),

        drill(
            "lang-maxkey-tutorial", "The Cheapest Item", "TUTORIAL",
            """
            `items` is a list of `[name, price]` pairs, at least one of them.
            Return the name of the cheapest. On a tie, the earliest one wins,
            which is what `min` already does.
            """,
            "cheapest", "items", _cheapest,
            """
            def cheapest(items):
                # min gives back the whole pair; index 0 pulls the name out of it.
                best = min(items, key=lambda item: item[1])
                return best[0]
            """,
            [("three items", [[["rune", 5], ["ward", 2], ["charm", 9]]]),
             ("two items", [[["a", 1], ["b", 2]]])],
            [("tie goes to first", [[["a", 3], ["b", 3]]]),
             ("single", [[["solo", 8]]]), ("zero price", [[["free", 0], ["a", 1]]])],
            edges=[("negative price", [[["credit", -2], ["a", 1]]])],
            pattern="ARRAY", family="onboarding_idioms", topic="minmaxkey",
            realm="fields_of_syntax", after="lang-maxkey-guided",
            constraints=["items holds at least one pair"],
            starter="""
            def cheapest(items):
                # 1. min() over items, keyed on the price at index 1
                # 2. return the name at index 0 of whatever min gave you
                pass
            """,
            nudge="The key selects what to compare. The return value is still the "
                  "whole item.",
            pseudocode="best = min(items, key=lambda it: it[1])\nreturn best[0]",
            time="O(n)", space="O(1)",
        ),

        drill(
            "lang-maxkey-easy", "The Busiest Hour", "EASY",
            """
            `counts` maps an hour (an int) to how many events it saw. Return the
            hour with the most events; if several tie, return the smallest such
            hour. `counts` is never empty.
            Iterating a dict gives its keys, so `min(counts, key=...)` compares
            hours by whatever the key function says.
            """,
            "busiest_hour", "counts", _busiest_hour,
            """
            def busiest_hour(counts):
                # Negating the count makes "most events" a minimum, so the hour
                # itself can break the tie in the natural ascending direction.
                return min(counts, key=lambda hour: (-counts[hour], hour))
            """,
            [("clear peak", [{9: 3, 10: 7, 11: 1}]), ("two hours", [{0: 1, 1: 2}])],
            [("tie takes the earlier", [{5: 4, 2: 4}]), ("single hour", [{13: 0}]),
             ("all equal", [{1: 2, 2: 2, 3: 2}])],
            edges=[("zero counts", [{4: 0, 6: 0}])],
            pattern="HASH_MAP", family="onboarding_idioms", topic="minmaxkey",
            realm="fields_of_syntax", after="lang-maxkey-tutorial",
            constraints=["counts holds at least one hour"],
            starter_hint="min over the keys, with a tuple key of (-count, hour)",
            nudge="`max` would take the largest hour on a tie, which is the wrong "
                  "tiebreak. Flip the comparison instead of fighting it.",
            pseudocode="return min(counts, key=lambda h: (-counts[h], h))",
            failures=["`max(counts, key=counts.get)` is close, but breaks ties "
                      "toward whichever hour the dict happens to reach first"],
            time="O(n)", space="O(1)",
        ),

        # -- topic 11: any / all ----------------------------------------------
        drill(
            "lang-anyall-guided", "Is There a Single One", "GUIDED",
            """
            `any(...)` is True when at least one item is truthy; `all(...)` is True
            when every item is. Both take a generator expression and both stop early.
            Return True when `nums` contains a negative number.
            any() over an empty sequence is False, which is the answer you want here.
            """,
            "has_negative", "nums", _has_negative,
            """
            def has_negative(nums):
                # The generator yields booleans; any() stops at the first True.
                return any(n < 0 for n in nums)
            """,
            [("one negative", [[1, -2, 3]]), ("none negative", [[1, 2]])],
            [("all negative", [[-1, -2]]), ("zero is not negative", [[0]]),
             ("last one", [[1, 2, -1]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_conditionals", topic="anyall",
            starter="""
            def has_negative(nums):
                # The loop is written. Write the test it should ask of each number.
                return any(__BLANK__ for n in nums)
            """,
            nudge="One comparison, using `n`.",
            pseudocode="return any(n < 0 for n in nums)",
            fragment=_same_move("if any(user.is_admin for user in users): ..."),
            failures=["`any(nums)` asks whether any number is truthy, which is a "
                      "different question and says True for [1]"],
            time="O(n)", space="O(1)",
        ),

        drill(
            "lang-anyall-tutorial", "Every One Of Them", "TUTORIAL",
            """
            Return True when every password in `passwords` is at least `n`
            characters long. An empty list returns True, because there is nothing
            in it that fails — that is what `all` means, and it surprises people.
            """,
            "all_strong", "passwords, n", _all_strong,
            """
            def all_strong(passwords, n):
                return all(len(p) >= n for p in passwords)
            """,
            [("all long enough", [["abcdefgh", "12345678"], 8]),
             ("one short", [["abcdefgh", "abc"], 8])],
            [("exactly at the bound", [["abcd"], 4]), ("all short", [["a", "b"], 3]),
             ("zero requirement", [["", "a"], 0])],
            edges=[("empty list is True", [[], 8])],
            pattern="ARRAY", family="onboarding_conditionals", topic="anyall",
            after="lang-anyall-guided",
            starter="""
            def all_strong(passwords, n):
                # One line: all(), a generator expression, one comparison.
                pass
            """,
            nudge="At least `n` means `>=`, not `>`.",
            pseudocode="return all(len(p) >= n for p in passwords)",
            failures=["Returning False for the empty list by adding a length check "
                      "that the definition of `all` does not want"],
            time="O(n)", space="O(1)",
        ),

        drill(
            "lang-anyall-easy", "Auditing the Grid", "EASY",
            """
            `rows` is a list of lists. Return a two-item list: first, whether every
            row has exactly `width` items; second, whether any row is empty.
            Both answers must be real booleans, not counts.
            """,
            "validate_rows", "rows, width", _validate_rows,
            """
            def validate_rows(rows, width):
                rectangular = all(len(row) == width for row in rows)
                has_gap = any(len(row) == 0 for row in rows)
                return [rectangular, has_gap]
            """,
            [("clean grid", [[[1, 2], [3, 4]], 2]),
             ("ragged", [[[1, 2], [3]], 2])],
            [("empty row present", [[[1], []], 1]),
             ("width zero", [[[], []], 0]), ("single row", [[[7, 8, 9]], 3])],
            edges=[("no rows", [[], 3])],
            pattern="ARRAY", family="onboarding_conditionals", topic="anyall",
            after="lang-anyall-tutorial",
            starter_hint="one all(), one any(), returned as a two-item list",
            nudge="With no rows at all, `all` is True and `any` is False. Both are "
                  "correct and both are worth remembering.",
            pseudocode="return [all(len(r) == width for r in rows),\n"
                       "        any(len(r) == 0 for r in rows)]",
            time="O(n)", space="O(1)",
        ),

        # -- topic 12: unpacking and starred assignment -----------------------
        drill(
            "lang-unpack-guided", "Two Names, One Line", "GUIDED",
            """
            Assignment can take several names at once: `a, b = pair` binds the two
            elements in order, and raises ValueError if the count is wrong.
            `pair` is a two-item list. Return a new list holding the two values the
            other way round. swap([1, 2]) gives [2, 1].
            """,
            "swap", "pair", _swap,
            """
            def swap(pair):
                first, second = pair
                # No temporary variable is needed anywhere in this function.
                return [second, first]
            """,
            [("numbers", [[1, 2]]), ("strings", [["a", "b"]])],
            [("mixed types", [[1, "x"]]), ("identical", [[5, 5]]),
             ("nested", [[[1], [2]]])],
            edges=[("with none", [[None, 1]])],
            pattern="ARRAY", family="onboarding_basics", topic="unpacking",
            starter="""
            def swap(pair):
                # Two names on the left, one sequence on the right.
                __BLANK__ = pair
                return [second, first]
            """,
            nudge="The names have to be in the order the values arrive, and the "
                  "return line already tells you what they are called.",
            pseudocode="first, second = pair\nreturn [second, first]",
            fragment=_same_move("x, y = point"),
            failures=["Unpacking a three-item list into two names: "
                      "ValueError: too many values to unpack"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-unpack-tutorial", "The Head and the Rest", "TUTORIAL",
            """
            A starred name absorbs whatever is left over: `first, *rest = items`
            binds `first` to the first element and `rest` to a list of the others,
            possibly empty.
            Return the two-item list `[first, rest]`. `items` is never empty.
            head_and_rest([1, 2, 3]) gives [1, [2, 3]].
            """,
            "head_and_rest", "items", _head_and_rest,
            """
            def head_and_rest(items):
                first, *rest = items
                # `rest` is always a list, even when it is empty.
                return [first, rest]
            """,
            [("three", [[1, 2, 3]]), ("two", [["a", "b"]])],
            [("one leaves empty rest", [[9]]), ("strings", [["x", "y", "z"]]),
             ("nested values", [[[1], [2]]])],
            edges=[("with none inside", [[None, None]])],
            pattern="ARRAY", family="onboarding_basics", topic="unpacking",
            after="lang-unpack-guided",
            constraints=["items holds at least one element"],
            starter="""
            def head_and_rest(items):
                # 1. unpack with a starred name: first, then the rest
                # 2. return [first, rest]
                pass
            """,
            nudge="Only one name in the assignment may carry a star.",
            pseudocode="first, *rest = items\nreturn [first, rest]",
            failures=["`items[0], items[1:]` works, but fails louder and later "
                      "when the list is empty"],
        ),

        drill(
            "lang-unpack-easy", "Both Ends and the Middle", "EASY",
            """
            A starred name can sit in the middle: `first, *middle, last = items`.
            `items` holds at least two elements. Return the three-item list
            `[first, last, middle]`, where `middle` is everything between them.
            trim_ends([1, 2, 3, 4]) gives [1, 4, [2, 3]].
            """,
            "trim_ends", "items", _trim_ends,
            """
            def trim_ends(items):
                first, *middle, last = items
                return [first, last, middle]
            """,
            [("four", [[1, 2, 3, 4]]), ("three", [["a", "b", "c"]])],
            [("exactly two", [[1, 2]]), ("five", [[1, 2, 3, 4, 5]]),
             ("strings", [["x", "y", "z", "w"]])],
            edges=[("two identical", [[7, 7]])],
            pattern="ARRAY", family="onboarding_basics", topic="unpacking",
            after="lang-unpack-tutorial",
            constraints=["items holds at least two elements"],
            starter_hint="one starred assignment, then one list",
            nudge="With exactly two elements the starred name gets the empty list. "
                  "Nothing raises.",
            pseudocode="first, *middle, last = items\nreturn [first, last, middle]",
        ),

        # -- topic 13: *args and ** unpacking ---------------------------------
        drill(
            "lang-args-guided", "However Many You Like", "GUIDED",
            """
            A star in a parameter list collects every remaining positional argument
            into a tuple: `def total(*nums)` can be called with none, one, or forty.
            Return the sum of everything passed in. total(1, 2, 3) gives 6, and
            total() gives 0.
            """,
            "total", "*nums", _total,
            """
            def total(*nums):
                # Inside the function `nums` is an ordinary tuple. Nothing else
                # about it is special.
                return sum(nums)
            """,
            [("three", [1, 2, 3]), ("one", [7])],
            [("negatives", [-1, -2]), ("zeros", [0, 0, 0]), ("many", [1] * 10)],
            edges=[("none at all", [])],
            pattern="ARRAY", family="onboarding_functions", topic="varargs",
            starter="""
            def total(*nums):
                # What is the collected tuple called?
                return sum(__BLANK__)
            """,
            nudge="The star is part of the parameter declaration, not part of the "
                  "name you use inside.",
            pseudocode="return sum(nums)",
            fragment=_same_move("def log(*parts): return ' '.join(parts)"),
            failures=["Writing `sum(*nums)`, which unpacks the tuple back into "
                      "separate arguments and raises TypeError"],
            time="O(n)", space="O(1)",
        ),

        drill(
            "lang-args-tutorial", "One Fixed, Then the Rest", "TUTORIAL",
            """
            Fixed parameters come before the starred one. `def join_all(sep, *parts)`
            takes the separator first and collects everything after it.
            Return the parts joined by `sep`, converting each to text first.
            join_all("-", 1, 2) gives "1-2", and join_all("-") gives "".
            """,
            "join_all", "sep, *parts", _join_all,
            """
            def join_all(sep, *parts):
                # str.join refuses anything that is not already a string, so the
                # conversion has to be explicit.
                return sep.join(str(part) for part in parts)
            """,
            [("numbers", ["-", 1, 2]), ("strings", [", ", "a", "b"])],
            [("single part", ["-", 9]), ("mixed types", ["|", 1, "b", 2]),
             ("empty separator", ["", "a", "b"])],
            edges=[("no parts", ["-"])],
            pattern="STRING", family="onboarding_functions", topic="varargs",
            after="lang-args-guided",
            starter="""
            def join_all(sep, *parts):
                # 1. turn every part into a string
                # 2. join them with sep
                # 3. return the result
                pass
            """,
            nudge="`sep.join(...)` reads backwards the first few times. The "
                  "separator is the thing you call the method on.",
            pseudocode="return sep.join(str(p) for p in parts)",
            failures=["`sep.join(parts)` raises TypeError the moment a number "
                      "appears"],
        ),

        drill(
            "lang-args-easy", "Unpacking a Dict Into Arguments", "EASY",
            """
            Two stars unpack a dict into keyword arguments: `f(**values)` is
            `f(name=..., score=...)`. Keys that the function does not accept raise
            TypeError, and keys it does not receive fall back to their defaults.
            `values` always has "name" and "score", and sometimes "active".
            Return "name:score:on" when active, "name:score:off" otherwise, with
            active defaulting to True.
            format_user({"name": "ada", "score": 3}) gives "ada:3:on".
            """,
            "format_user", "values", _format_user,
            """
            def format_user(values):
                def row(name, score, active=True):
                    state = "on" if active else "off"
                    return f"{name}:{score}:{state}"

                # ** turns the dict's keys into parameter names at the call site.
                return row(**values)
            """,
            [("defaulted", [{"name": "ada", "score": 3}]),
             ("explicit true", [{"name": "bo", "score": 1, "active": True}])],
            [("inactive", [{"name": "cy", "score": 0, "active": False}]),
             ("zero score", [{"name": "dot", "score": 0}]),
             ("negative score", [{"name": "eve", "score": -2}])],
            edges=[("empty name", [{"name": "", "score": 5}])],
            pattern="STRING", family="onboarding_functions", topic="varargs",
            after="lang-args-tutorial",
            starter_hint="define a helper with a default, then call it with **values",
            nudge="The inner function names the keys. The dict supplies them.",
            pseudocode="def row(name, score, active=True): ...\nreturn row(**values)",
            failures=["Reading values['active'] directly, which raises KeyError "
                      "when it is absent"],
            time="O(1)", space="O(1)",
        ),

        # -- topic 14: is vs == ------------------------------------------------
        drill(
            "lang-identity-guided", "Missing Is Not Empty", "GUIDED",
            """
            `is` asks whether two names point at the same object. `==` asks whether
            two values are equal. For `None` there is exactly one object in the
            whole program, so `is None` is the check — and it is the only one that
            keeps 0 and "" out of the answer.
            Return True when `value` is None, and False for everything else,
            including 0, "" and [].
            """,
            "is_missing", "value", _is_missing,
            """
            def is_missing(value):
                # `not value` would say True for 0, "" and []. Those are present.
                return value is None
            """,
            [("none", [None]), ("zero is present", [0])],
            [("empty string is present", [""]), ("empty list is present", [[]]),
             ("a real value", ["ada"])],
            edges=[("false is present", [False])],
            pattern="STRING", family="onboarding_basics", topic="identity",
            starter="""
            def is_missing(value):
                # Two characters go in the hole.
                return value __BLANK__ None
            """,
            nudge="Not `==`, and not `not`. Identity.",
            pseudocode="return value is None",
            fragment=_same_move("if cached is None: cached = compute()"),
            failures=["`if not value:` treats 0, \"\" and [] as missing, which is "
                      "the single most common source of quiet data bugs"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-identity-tutorial", "Counting the Holes", "TUTORIAL",
            """
            `rows` is a list of dicts. Return how many of them are missing `key` —
            meaning the key is absent, or present with the value None. A row whose
            value is 0 or "" is not missing anything.
            `row.get(key)` returns None for an absent key, so one test covers both.
            """,
            "count_missing", "rows, key", _count_missing,
            """
            def count_missing(rows, key):
                missing = 0
                for row in rows:
                    if row.get(key) is None:
                        missing += 1
                return missing
            """,
            [("one absent", [[{"a": 1}, {}], "a"]),
             ("one explicit none", [[{"a": None}, {"a": 2}], "a"])],
            [("zero counts as present", [[{"a": 0}], "a"]),
             ("empty string counts as present", [[{"a": ""}], "a"]),
             ("none missing", [[{"a": 1}, {"a": 2}], "a"])],
            edges=[("no rows", [[], "a"])],
            pattern="HASH_MAP", family="onboarding_basics", topic="identity",
            after="lang-identity-guided",
            starter="""
            def count_missing(rows, key):
                # 1. start a counter at zero
                # 2. for each row, look the key up with .get()
                # 3. add one when the result is None
                # 4. return the counter
                pass
            """,
            nudge="`row[key]` raises on an absent key. `.get` does not.",
            pseudocode="for row in rows:\n    if row.get(key) is None: missing += 1",
            failures=["`if not row.get(key)` counts the rows holding 0 as missing"],
        ),

        drill(
            "lang-identity-easy", "Filling Only the Holes", "EASY",
            """
            Return a new list in which every None in `values` is replaced by
            `default`, and every other value — including 0, False and "" — is left
            exactly as it was.
            fill_blanks([1, None, 0], 9) gives [1, 9, 0].
            """,
            "fill_blanks", "values, default", _fill_blanks,
            """
            def fill_blanks(values, default):
                # The conditional expression picks per element; `is None` is what
                # keeps the falsy-but-present values intact.
                return [default if value is None else value for value in values]
            """,
            [("one hole", [[1, None, 0], 9]), ("no holes", [[1, 2], 9])],
            [("all holes", [[None, None], "x"]),
             ("false survives", [[False, None], True]),
             ("empty string survives", [["", None], "d"])],
            edges=[("empty list", [[], 0])],
            pattern="ARRAY", family="onboarding_basics", topic="identity",
            after="lang-identity-tutorial",
            starter_hint="one comprehension with a conditional expression",
            nudge="`value or default` looks shorter and is wrong: it replaces "
                  "every falsy value, not just the missing ones.",
            pseudocode="return [default if v is None else v for v in values]",
            failures=["Using `or`, which eats legitimate zeros and empty strings"],
        ),

        # -- topic 15: ternary expressions --------------------------------------
        drill(
            "lang-ternary-guided", "The Conditional Expression", "GUIDED",
            """
            Python's ternary reads in value order: `A if TEST else B`. It is an
            expression, so it produces a value and can sit anywhere a value can.
            Return "positive" when `n` is greater than zero, and "not positive"
            otherwise. Zero is not positive.
            """,
            "sign_word", "n", _sign_word,
            """
            def sign_word(n):
                # The condition sits in the middle. That ordering is the only part
                # people trip over.
                return "positive" if n > 0 else "not positive"
            """,
            [("positive", [5]), ("negative", [-5])],
            [("zero", [0]), ("one", [1]), ("large", [10 ** 6])],
            edges=[("minus one", [-1])],
            pattern="STRING", family="onboarding_conditionals", topic="ternary",
            starter="""
            def sign_word(n):
                # Both results are written. Write the test between them.
                return "positive" if __BLANK__ else "not positive"
            """,
            nudge="Strictly greater than zero.",
            pseudocode='return "positive" if n > 0 else "not positive"',
            fragment=_same_move('label = "even" if n % 2 == 0 else "odd"'),
            failures=["Writing it in C order, `n > 0 ? a : b`, which is a "
                      "SyntaxError in Python"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-ternary-tutorial", "Low, High, or Fine", "TUTORIAL",
            """
            Return "low" when `n` is below `lo`, "high" when it is above `hi`, and
            "ok" otherwise. The bounds themselves are "ok".
            Plain `if` statements are fine here — the point is that the three cases
            are exhaustive and ordered.
            """,
            "clamp_label", "n, lo, hi", _clamp_label,
            """
            def clamp_label(n, lo, hi):
                if n < lo:
                    return "low"
                if n > hi:
                    return "high"
                return "ok"
            """,
            [("below", [1, 5, 10]), ("above", [50, 5, 10])],
            [("inside", [7, 5, 10]), ("on the low bound", [5, 5, 10]),
             ("on the high bound", [10, 5, 10])],
            edges=[("bounds equal", [5, 5, 5])],
            pattern="STRING", family="onboarding_conditionals", topic="ternary",
            after="lang-ternary-guided",
            starter="""
            def clamp_label(n, lo, hi):
                # 1. below lo -> "low"
                # 2. above hi -> "high"
                # 3. otherwise -> "ok"
                pass
            """,
            nudge="An early `return` makes the later branches unreachable, so no "
                  "`elif` is needed.",
            pseudocode='if n < lo: return "low"\nif n > hi: return "high"\nreturn "ok"',
            failures=["Using `<=` on a bound, which mislabels the boundary values"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-ternary-easy", "Labelling the Responses", "EASY",
            """
            `codes` is a list of HTTP status codes. Return a list of labels: "ok"
            for a code below 400, "error" otherwise. One comprehension with a
            conditional expression in front of the `for`.
            Note where the condition goes: this is a choice per item, not a filter.
            """,
            "statuses", "codes", _statuses,
            """
            def statuses(codes):
                # A conditional expression before `for` transforms; an `if` after
                # the `for` would drop items instead.
                return ["ok" if code < 400 else "error" for code in codes]
            """,
            [("mixed", [[200, 404]]), ("all ok", [[200, 301]])],
            [("all errors", [[500, 403]]), ("boundary", [[399, 400]]),
             ("single", [[204]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_conditionals", topic="ternary",
            after="lang-ternary-tutorial",
            starter_hint="a conditional expression in the output half of a comprehension",
            nudge="400 is an error. 399 is not.",
            pseudocode='return ["ok" if c < 400 else "error" for c in codes]',
            failures=["Putting the `if` after the `for`, which filters the list "
                      "down instead of labelling every item"],
        ),

        # -- topic 16: range and loops ------------------------------------------
        drill(
            "lang-range-guided", "Start, Stop, Step", "GUIDED",
            """
            `range(start, stop, step)` counts from `start`, by `step`, stopping
            *before* `stop`. It never includes the stop value.
            Return every multiple of `k` from 0 up to but not including `n`, as a
            list. multiples(10, 3) gives [0, 3, 6, 9]. `k` is always positive, and
            an `n` of zero or less gives an empty list.
            """,
            "multiples", "n, k", _multiples,
            """
            def multiples(n, k):
                # range is lazy; list() is what makes it a list.
                return list(range(0, n, k))
            """,
            [("threes under ten", [10, 3]), ("twos under seven", [7, 2])],
            [("step one", [4, 1]), ("step past the end", [3, 10]),
             ("exact multiple", [9, 3])],
            edges=[("zero stop", [0, 3])],
            pattern="ARRAY", family="onboarding_loops", topic="range",
            constraints=["1 <= k"],
            starter="""
            def multiples(n, k):
                # Start and stop are written. The third argument is the step.
                return list(range(0, n, __BLANK__))
            """,
            nudge="The gap between consecutive multiples of k is k.",
            pseudocode="return list(range(0, n, k))",
            fragment=_same_move("for i in range(0, len(items), size): ..."),
            failures=["range(0, n) with a step of 1 and a filter works, but does "
                      "k times more work than it needs to"],
        ),

        drill(
            "lang-range-tutorial", "Inclusive on Both Ends", "TUTORIAL",
            """
            Return the sum of every integer from `lo` to `hi`, with both ends
            included. Since range excludes its stop, the stop you want is `hi + 1`.
            If `hi` is below `lo` the total is 0.
            """,
            "sum_range", "lo, hi", _sum_range,
            """
            def sum_range(lo, hi):
                # The + 1 is the entire lesson. An empty range sums to 0 on its own.
                return sum(range(lo, hi + 1))
            """,
            [("one to five", [1, 5]), ("three to three", [3, 3])],
            [("crossing zero", [-2, 2]), ("reversed bounds", [5, 1]),
             ("negatives", [-5, -3])],
            edges=[("off by one apart", [4, 3])],
            pattern="ARRAY", family="onboarding_loops", topic="range",
            after="lang-range-guided",
            starter="""
            def sum_range(lo, hi):
                # 1. build the range, remembering that stop is exclusive
                # 2. sum it
                # 3. return the total
                pass
            """,
            nudge="sum(range(5, 2)) is 0, not an error.",
            pseudocode="return sum(range(lo, hi + 1))",
            failures=["Forgetting the + 1 and silently losing the last term"],
            time="O(n)", space="O(1)",
        ),

        drill(
            "lang-range-easy", "Walking Backwards", "EASY",
            """
            Return the items of `items` in reverse order, built by indexing with a
            descending range rather than by slicing. The form
            `range(len(items) - 1, -1, -1)` is the one people fumble: the stop is
            -1 because index 0 must still be included.
            """,
            "reversed_items", "items", _reversed_items,
            """
            def reversed_items(items):
                # stop is -1, not 0, or the first element never gets visited.
                return [items[i] for i in range(len(items) - 1, -1, -1)]
            """,
            [("three", [[1, 2, 3]]), ("two", [["a", "b"]])],
            [("one", [[9]]), ("duplicates", [[1, 1, 2]]),
             ("longer", [[1, 2, 3, 4, 5]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_loops", topic="range",
            after="lang-range-tutorial",
            starter_hint="index with range(len - 1, -1, -1)",
            nudge="Write the three arguments out loud: start at the last index, "
                  "stop before -1, step by -1.",
            pseudocode="return [items[i] for i in range(len(items) - 1, -1, -1)]",
            failures=["A stop of 0, which drops the first element",
                      "Forgetting the negative step, which produces an empty list"],
        ),

        # -- topic 17: nested data access ----------------------------------------
        drill(
            "lang-nested-guided", "Two Keys Deep", "GUIDED",
            """
            Nested containers are read one step at a time, left to right:
            `record["address"]["city"]` looks up "address" in `record`, then "city"
            in whatever came back.
            `record` always has an "address" dict holding a "city". Return the city.
            """,
            "user_city", "record", _user_city,
            """
            def user_city(record):
                # Each pair of brackets is one lookup on the result of the last one.
                return record["address"]["city"]
            """,
            [("one user", [{"name": "ada", "address": {"city": "Rune", "zip": "1"}}]),
             ("another", [{"name": "bo", "address": {"city": "Ward"}}])],
            [("extra keys", [{"address": {"city": "Vale", "street": "x"}, "id": 3}]),
             ("empty city", [{"address": {"city": ""}}]),
             ("numeric-looking city", [{"address": {"city": "7"}}])],
            edges=[("city is the only key", [{"address": {"city": "Solo"}}])],
            pattern="HASH_MAP", family="onboarding_dict", topic="nested",
            starter="""
            def user_city(record):
                # The first lookup is written. Write the second.
                return record["address"][__BLANK__]
            """,
            nudge="The key is a string, so it needs its quotes.",
            pseudocode='return record["address"]["city"]',
            fragment=_same_move('port = config["server"]["port"]'),
            failures=["record[\"address\", \"city\"] looks up a tuple key and "
                      "raises KeyError"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-nested-tutorial", "When the Key Might Not Be There", "TUTORIAL",
            """
            `.get(key, default)` returns the default instead of raising when the key
            is absent. Chaining it with `{}` as the default keeps the next lookup
            legal: `record.get("address", {}).get("city", "unknown")`.
            Return the city, or "unknown" if either the address or the city is
            missing. The "address" key, when present, is always a dict.
            """,
            "safe_city", "record", _safe_city,
            """
            def safe_city(record):
                # The empty dict is there so the second .get has something to run
                # against when the first lookup finds nothing.
                return record.get("address", {}).get("city", "unknown")
            """,
            [("present", [{"address": {"city": "Rune"}}]),
             ("no address", [{"name": "ada"}])],
            [("address without city", [{"address": {"zip": "1"}}]),
             ("empty address", [{"address": {}}]),
             ("empty record", [{}])],
            edges=[("city present but empty", [{"address": {"city": ""}}])],
            pattern="HASH_MAP", family="onboarding_dict", topic="nested",
            after="lang-nested-guided",
            starter="""
            def safe_city(record):
                # 1. .get the address, defaulting to an empty dict
                # 2. .get the city off that, defaulting to "unknown"
                # 3. return it
                pass
            """,
            nudge="An empty string city is a real answer and must survive.",
            pseudocode='return record.get("address", {}).get("city", "unknown")',
            failures=["`.get(\"address\")` with no default returns None, and None "
                      "has no .get — AttributeError"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-nested-easy", "Everyone in the Org", "EASY",
            """
            `org` has a "teams" key holding a list of dicts, each with a "name" and
            a "members" list of strings. Return every member name across every team,
            sorted alphabetically. Duplicates are kept.
            """,
            "team_members", "org", _team_members,
            """
            def team_members(org):
                # Two levels: teams, then members inside each team.
                names = [m for team in org["teams"] for m in team["members"]]
                return sorted(names)
            """,
            [("two teams", [{"teams": [{"name": "red", "members": ["ada", "bo"]},
                                       {"name": "blue", "members": ["cy"]}]}]),
             ("one team", [{"teams": [{"name": "solo", "members": ["zed", "ada"]}]}])],
            [("empty team", [{"teams": [{"name": "ghost", "members": []},
                                        {"name": "red", "members": ["ada"]}]}]),
             ("duplicate member", [{"teams": [{"name": "a", "members": ["ada"]},
                                              {"name": "b", "members": ["ada"]}]}]),
             ("no teams", [{"teams": []}])],
            edges=[("all teams empty", [{"teams": [{"name": "a", "members": []}]}])],
            pattern="HASH_MAP", family="onboarding_dict", topic="nested",
            after="lang-nested-tutorial",
            starter_hint="a nested comprehension over teams, then members",
            nudge="Same nested comprehension shape as flattening a grid; only the "
                  "names of the levels changed.",
            pseudocode="names = [m for team in org['teams'] for m in team['members']]\n"
                       "return sorted(names)",
            time="O(n log n)",
        ),

        drill(
            "lang-nested-medium", "The Path Walker", "MEDIUM",
            """
            `path` is a list of steps: strings for dict keys, non-negative ints for
            list indices. Walk `data` one step at a time and return what you land
            on. Return `default` the moment a step does not fit — a missing key, an
            index out of range, or a step into something that is neither a dict nor
            a list. An empty path returns `data` itself.
            deep_get({"a": [{"b": 1}]}, ["a", 0, "b"], None) gives 1.
            """,
            "deep_get", "data, path, default", _deep_get,
            """
            def deep_get(data, path, default):
                node = data
                for step in path:
                    if isinstance(node, dict) and step in node:
                        node = node[step]
                    elif isinstance(node, list) and isinstance(step, int):
                        if not 0 <= step < len(node):
                            return default
                        node = node[step]
                    else:
                        # Neither container, or a key that is not there.
                        return default
                return node
            """,
            [("dict then list then dict", [{"a": [{"b": 1}]}, ["a", 0, "b"], None]),
             ("missing key", [{"a": 1}, ["b"], "gone"])],
            [("index out of range", [{"a": [1]}, ["a", 5], -1]),
             ("string step into a list", [{"a": [1]}, ["a", "x"], "bad"]),
             ("step into a scalar", [{"a": 1}, ["a", "b"], "bad"])],
            edges=[("empty path", [{"a": 1}, [], "unused"]),
                   ("empty data", [{}, ["a"], "default"])],
            pattern="HASH_MAP", family="onboarding_dict", topic="nested",
            after="lang-nested-easy",
            starter_hint="one cursor variable, one loop over path, one guard per step",
            nudge="Keep one variable pointing at the current node and reassign it. "
                  "There is no recursion needed here.",
            pseudocode="node = data\nfor step in path:\n"
                       "    if step does not fit node: return default\n"
                       "    node = node[step]\nreturn node",
            failures=["Catching every exception with a bare except, which also "
                      "swallows the bugs in your own walking code",
                      "Forgetting that a valid step can land on a falsy value that "
                      "must still be returned"],
            time="O(k)", space="O(1)",
        ),

        # -- topic 18: default arguments ----------------------------------------
        drill(
            "lang-default-guided", "A Parameter With a Fallback", "GUIDED",
            """
            A parameter can carry a default: `def greet(name, greeting="Hello")`.
            Callers may omit it, and the default is evaluated once, when the
            function is defined.
            Return the greeting, a comma, a space, then the name. greet("Vail")
            gives "Hello, Vail"; greet("Vail", "Well met") gives "Well met, Vail".
            """,
            "greet", 'name, greeting="Hello"', _greet,
            """
            def greet(name, greeting="Hello"):
                return f"{greeting}, {name}"
            """,
            [("default greeting", ["Vail"]), ("custom greeting", ["Vail", "Well met"])],
            [("empty name", [""]), ("custom and short", ["A", "Yo"]),
             ("default again", ["Root"])],
            edges=[("empty greeting", ["Vail", ""])],
            pattern="STRING", family="onboarding_functions", topic="defaults",
            starter="""
            def greet(name, greeting=__BLANK__):
                return f"{greeting}, {name}"
            """,
            nudge="The default is a value, written where it is declared. It needs "
                  "its quotes.",
            pseudocode='def greet(name, greeting="Hello"): return f"{greeting}, {name}"',
            fragment=_same_move('def connect(host, port=443): ...'),
            failures=["Putting a defaulted parameter before a required one, which "
                      "is a SyntaxError"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-default-tutorial", "Two Defaults at Once", "TUTORIAL",
            """
            Return the items of `items` as text, repeated `times` times in a row and
            joined by `sep`. `sep` defaults to ", " and `times` to 1.
            repeat_join([1, 2]) gives "1, 2"; repeat_join([1], "-", 3) gives "1-1-1".
            """,
            "repeat_join", 'items, sep=", ", times=1', _repeat_join,
            """
            def repeat_join(items, sep=", ", times=1):
                # Multiplying a list repeats its elements; it does not nest them.
                parts = [str(value) for value in items] * times
                return sep.join(parts)
            """,
            [("both defaults", [[1, 2]]), ("all three", [[1], "-", 3])],
            [("custom separator only", [["a", "b"], " | "]),
             ("times one", [[1, 2], "-", 1]), ("strings", [["x"], ", ", 2])],
            edges=[("empty items", [[]]), ("times zero", [[1, 2], "-", 0])],
            pattern="STRING", family="onboarding_functions", topic="defaults",
            after="lang-default-guided",
            starter="""
            def repeat_join(items, sep=", ", times=1):
                # 1. build a list of the items as strings
                # 2. repeat that list `times` times with *
                # 3. join it with sep and return
                pass
            """,
            nudge="Defaults are matched by position or by name; the caller may "
                  "supply one, two or three arguments.",
            pseudocode="parts = [str(v) for v in items] * times\nreturn sep.join(parts)",
        ),

        drill(
            "lang-default-easy", "The Mutable Default Trap", "EASY",
            """
            A default value is created once, when the function is defined — so a
            mutable default like `tags=[]` is shared by every call that omits it,
            and it accumulates. The fix is `tags=None` plus a check inside.
            Return a new list holding `tags` followed by `tag`. With no `tags` given,
            return just `[tag]`, every time, no matter how often it is called.
            """,
            "add_tag", "tag, tags=None", _add_tag,
            """
            def add_tag(tag, tags=None):
                if tags is None:
                    tags = []
                # Copying rather than appending in place keeps the caller's list
                # untouched, which is the second half of the same lesson.
                return list(tags) + [tag]
            """,
            [("no list given", ["red"]), ("with a list", ["red", ["blue"]])],
            [("empty list given", ["red", []]),
             ("two existing", ["c", ["a", "b"]]), ("no list again", ["solo"])],
            edges=[("empty tag", ["", ["a"]])],
            pattern="ARRAY", family="onboarding_functions", topic="defaults",
            after="lang-default-tutorial",
            starter_hint="tags=None, then build the list inside",
            nudge="This is the `is None` check again, and it is the reason that "
                  "check matters.",
            pseudocode="if tags is None: tags = []\nreturn list(tags) + [tag]",
            failures=["`def add_tag(tag, tags=[])` grows across calls and is the "
                      "canonical Python timed practical trap",
                      "`tags.append(tag)` mutates the caller's list and returns None"],
        ),

        # -- topic 19: tuples ----------------------------------------------------
        drill(
            "lang-tuple-guided", "The Comma Makes It", "GUIDED",
            """
            A tuple is an immutable sequence, and it is the comma that creates one —
            the parentheses are only for clarity. `(a, b)` is a two-item tuple.
            Build the tuple `(a, b)`, then return it as a list.
            as_pair(1, 2) gives [1, 2].
            """,
            "as_pair", "a, b", _as_pair,
            """
            def as_pair(a, b):
                pair = (a, b)
                # Tuples cannot be changed in place, which is exactly why they are
                # safe to use as dict keys.
                return list(pair)
            """,
            [("numbers", [1, 2]), ("strings", ["a", "b"])],
            [("mixed", [1, "x"]), ("identical", [5, 5]),
             ("nested list", [[1], 2])],
            edges=[("with none", [None, 0])],
            pattern="ARRAY", family="onboarding_lists", topic="tuples",
            starter="""
            def as_pair(a, b):
                # Build the pair. One comma is all it takes.
                pair = __BLANK__
                return list(pair)
            """,
            nudge="`(a)` is just `a` in parentheses. `(a,)` is a one-item tuple.",
            pseudocode="pair = (a, b)\nreturn list(pair)",
            fragment=_same_move("point = (row, col)"),
            failures=["Trying to assign into a tuple later: TypeError, "
                      "'tuple' object does not support item assignment"],
            time="O(1)", space="O(1)",
        ),

        drill(
            "lang-tuple-tutorial", "Taking the Pairs Apart", "TUTORIAL",
            """
            `zip(*pairs)` turns a list of pairs back into two sequences — the
            inverse of zipping them together. It yields tuples, and unpacking them
            into two names is the idiomatic way to catch them.
            Return `[firsts, seconds]` as two lists. An empty input returns
            `[[], []]`, because `zip(*[])` yields nothing to unpack.
            """,
            "unzip", "pairs", _unzip,
            """
            def unzip(pairs):
                if not pairs:
                    return [[], []]
                firsts, seconds = zip(*pairs)
                # zip hands back tuples; the tests want lists.
                return [list(firsts), list(seconds)]
            """,
            [("three pairs", [[["a", 1], ["b", 2], ["c", 3]]]),
             ("one pair", [[["solo", 9]]])],
            [("numbers both sides", [[[1, 2], [3, 4]]]),
             ("repeated firsts", [[["a", 1], ["a", 2]]]),
             ("two pairs", [[["x", 0], ["y", 0]]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="onboarding_lists", topic="tuples",
            after="lang-tuple-guided",
            starter="""
            def unzip(pairs):
                # 1. return [[], []] when there is nothing to unzip
                # 2. unpack zip(*pairs) into two names
                # 3. return both, as lists
                pass
            """,
            nudge="Without the guard, the unpacking raises ValueError on an empty "
                  "list: there are zero values, and you asked for two.",
            pseudocode="if not pairs: return [[], []]\nfirsts, seconds = zip(*pairs)\n"
                       "return [list(firsts), list(seconds)]",
            failures=["Returning the tuples themselves rather than lists"],
        ),

        drill(
            "lang-tuple-easy", "A Pair as a Key", "EASY",
            """
            A list cannot be a dict key — it is mutable, so it is unhashable. A
            tuple can. Count how many times each pair appears in `pairs` (a list of
            two-item lists) by using `tuple(pair)` as the key.
            Return a sorted list of `[first, second, count]` entries.
            """,
            "pair_counts", "pairs", _pair_counts,
            """
            def pair_counts(pairs):
                from collections import Counter

                # tuple() is the conversion that makes the key hashable.
                counts = Counter(tuple(pair) for pair in pairs)
                return sorted([first, second, n]
                              for (first, second), n in counts.items())
            """,
            [("one repeat", [[["a", "x"], ["b", "y"], ["a", "x"]]]),
             ("all distinct", [[["a", "x"], ["b", "y"]]])],
            [("all identical", [[["a", "x"], ["a", "x"], ["a", "x"]]]),
             ("single", [[["z", "z"]]]),
             ("same first different second", [[["a", "x"], ["a", "y"]]])],
            edges=[("empty", [[]])],
            pattern="HASH_MAP", family="onboarding_lists", topic="tuples",
            after="lang-tuple-tutorial",
            starter_hint="tuple(pair) as the key, then sort the entries",
            nudge="`counts[pair]` with a list raises TypeError: unhashable type: "
                  "'list'. Convert first.",
            pseudocode="counts = Counter(tuple(p) for p in pairs)\n"
                       "return sorted([a, b, n] for (a, b), n in counts.items())",
            failures=["Using the list directly as a key",
                      "Returning the dict, whose order is not what the tests compare"],
            time="O(n log n)",
        ),
    ]
