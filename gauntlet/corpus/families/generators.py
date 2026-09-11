"""Generators, iterators, closures, decorators and context managers.

Everything in this family is *language machinery the corpus could not teach at
all* before it existed. It is also the ground a Python interview walks onto the
moment the algorithm question is finished: "so what does `yield` actually do",
"why is `functools.wraps` there", "what does `with` buy you over try/finally".

The ramp is the point. The complaint that produced this file was that the game
was too hard, and the cause was topics that arrived already difficult. So every
topic here walks the same four rungs, in this order, and no topic is allowed to
skip one:

  GUIDED    complete, working code with one `__BLANK__` in it. The player types
            a single expression or a single statement into a program that
            already runs in their head. Encounter kind MISSING_RUNE.
  TUTORIAL  a skeleton whose comments name each step. The player writes bodies.
  EASY      the harness is given, the interesting function is theirs.
  MEDIUM/HARD  the whole thing, and a reason the naive version does not work.

One authoring convention runs through the module and is worth stating once.
Most of these concepts are only observable through a *consumer* — a generator is
not a value, a decorator is not a value, a context manager is not a value. So
each problem gives the player a small, complete, visible harness function (the
graded entry point) that exercises the thing they are writing and returns
something a test can compare. The harness lives in the starter code, not in a
hidden preamble: the player can read everything that grades them.

The memory argument gets made twice, and honestly. `gen-infinite-naturals` and
`gen-ledger-scan` are built on sources with no end, where the list version is not
slow or wasteful but *impossible*; `gen-mcq-list-cost` says the same thing in
prose. That is a stronger claim than "lists are big", and it is the true one.
"""
from __future__ import annotations

from ._base import code_problem, debug_problem, mcq_problem

# The player this corpus was built for. Language machinery is the stated
# bottleneck, so these weight high for every profile.
Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.2, "SECURITY_ENGINEERING": 2.0}

VIZ = {"type": "array_scan", "caption": "One value at a time, on demand."}

VISUAL = {
    "GUIDED": "The program already works. Read it top to bottom, then fill the "
              "hole. You are finishing someone else's sentence.",
    "TUTORIAL": "One comment, one line of code. Write a line, run it, write the "
                "next. Do not write all four and hope.",
    "EASY": "The harness below your function is already correct. Read it first — "
            "it tells you exactly what your function has to hand back.",
    "MEDIUM": "Say the mechanism out loud before you type it. Who pulls, who "
              "yields, and what is still alive between the two.",
    "HARD": "There is no version of this that builds the whole thing first. "
            "Decide what you are allowed to hold in memory, then hold only that.",
}


def _same_move(body: str) -> str:
    """Rung 4 of the hint tree for a scaffolded drill.

    Handing back the first lines of the canonical solution would make this rung
    identical to Phoenix, which for a six-line program is the whole answer. Show
    the same move on different data instead.
    """
    return "```python\n# the same move, somewhere else:\n" + body.strip() + "\n```"


def drill(pid, title, tier, statement, fn, params, ref, canonical, visible,
          hidden, *, starter="", starter_hint="", edges=(), perf=(),
          pattern="ARRAY", family="python_generators", nudge="", visual="",
          pseudocode="", fragment="", failures=(), time="O(n)", space="O(1)",
          after="", realm="fields_of_syntax", tags=(), secondary=()):
    """One problem. `after` is the id of the drill this one follows, which is
    what keeps the ramp legible to anything reading the corpus from outside."""
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=tier,
        family=family, profile_weight=Q, viz=VIZ, statement=statement,
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        visible=visible, hidden=hidden, edges=edges, perf=perf,
        time_complexity=time, space_complexity=space,
        failures=list(failures), nudge=nudge, visual=visual or VISUAL[tier],
        pseudocode=pseudocode, fragment=fragment,
        starter_code=starter, starter_hint=starter_hint,
        secondary=list(secondary),
        encounter="MISSING_RUNE" if tier == "GUIDED" else "CODE_BATTLE",
        prerequisites=[after] if after else [],
        tags=["python", "language-machinery", "tier:" + tier.lower()] + list(tags),
    )


# ---------------------------------------------------------------------------
# Reference implementations.
#
# Written straight, with none of the machinery the problem is about: the point
# of the reference is to compute the right answer a *different* way, so that a
# canonical solution which merely looks plausible is caught before a player ever
# meets it. Where the problem is about a decorator, the reference does the
# decorator's job inline; where it is about a generator, the reference builds
# the list it is allowed to build because n is small at build time.
# ---------------------------------------------------------------------------

# -- iterators ---------------------------------------------------------------

def _first_two(items):
    return [items[0], items[1]]


def _third_or_none(items):
    return items[2] if len(items) > 2 else None


def _manual_sum(items):
    total = 0
    for value in items:
        total += value
    return total


def _split_in_two(items):
    return [list(items[:2]), list(items[2:])]


def _countdown_values(start):
    return list(range(start, 0, -1))


def _twice_over(start, stop, step):
    out = []
    value = start
    while value < stop:
        out.append(value)
        value += step
    return [out, list(out)]


def _cycle_take(items, n):
    if not items:
        return []
    return [items[i % len(items)] for i in range(n)]


def _compress_runs(items):
    out = []
    for value in items:
        if out and out[-1][0] == value:
            out[-1][1] += 1
        else:
            out.append([value, 1])
    return out


# -- generators --------------------------------------------------------------

def _squares_list(n):
    return [i * i for i in range(n)]


def _evens_list(nums):
    return [value for value in nums if value % 2 == 0]


def _total_of_squares(nums):
    total = 0
    for value in nums:
        total += value ** 2
    return total


def _first_long_word(words, least):
    for word in words:
        if len(word) >= least:
            return word
    return ""


def _numbered_list(lines):
    out = []
    for index in range(len(lines)):
        text = lines[index].strip()
        if text != "":
            out.append([index + 1, text])
    return out


def _chain_list(first, second):
    return list(first) + list(second)


def _concat_all(groups):
    out = []
    for group in groups:
        for value in group:
            out.append(value)
    return out


def _first_n(start, n):
    return list(range(start, start + n))


def _take_until_limit(nums, limit):
    out = []
    for value in nums:
        if value >= limit:
            break
        out.append(value)
    return out


def _payload_bytes(lines):
    total = 0
    for line in lines:
        text = line.strip()
        if text == "" or text[0] == "#":
            continue
        total += len(text)
    return total


def _chunk_list(items, size):
    if size <= 0:
        return []
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def _window_list(items, k):
    if k <= 0:
        return []
    return [list(items[i:i + k]) for i in range(len(items) - k + 1)]


def _merge_lists(left, right):
    # Both inputs are sorted, so the merge of them is simply the sorted union.
    # Nothing here resembles the two-cursor walk the canonical solution uses,
    # which is exactly why it is worth running both.
    return sorted(list(left) + list(right))


def _deep_flatten_list(value):
    out = []
    for item in value:
        if isinstance(item, list):
            out.extend(_deep_flatten_list(item))
        else:
            out.append(item)
    return out


def _stream_list(first, second):
    return list(first) + list(second) + ["done"]


def _staged_run(steps, fail):
    log = ["start"] + list(steps) + ["end"]
    if fail:
        log.append("caught")
    return log


def _index_of_total(seed, target):
    value = seed
    total = 0
    index = 0
    while True:
        value = (value * 1103515245 + 12345) % 2147483648
        total += value % 100 + 1
        index += 1
        if total >= target:
            return [index, total]


# -- closures ----------------------------------------------------------------

def _add_each(amount, values):
    return [value + amount for value in values]


def _scale_all(factor, values):
    return [value * factor for value in values]


def _count_to(times):
    return list(range(1, times + 1))


def _running_totals(values):
    out = []
    total = 0
    for value in values:
        total += value
        out.append(total)
    return out


def _multipliers(factors, value):
    return [factor * value for factor in factors]


def _run_account(start, amounts):
    balance = start
    history = []
    for amount in amounts:
        if balance + amount < 0:
            history.append("refused")
        else:
            balance += amount
            history.append("ok")
    return [balance, history]


# -- decorators --------------------------------------------------------------

def _doubled_lengths(words):
    return [len(word) * 2 for word in words]


def _call_with_two(a, b):
    return ["called", a + b]


def _call_count(values):
    return [[value * 2 for value in values], len(values)]


def _identity_of(value):
    return ["scale", "Multiply by ten.", value * 10]


def _trace_report(words):
    spoken = [word.upper() for word in words]
    return ["shout", "Upper-case a word.", spoken, spoken[-1] if spoken else None]


def _fib_cost(n):
    memo = {}
    misses = 0

    def fib(k):
        nonlocal misses
        if k in memo:
            return memo[k]
        misses += 1
        memo[k] = k if k < 2 else fib(k - 1) + fib(k - 2)
        return memo[k]

    return [fib(n), misses]


def _repeated_greeting(name, times):
    return ["hail " + name] * times


def _describe(items, label):
    return [[label + ": " + str(item) for item in items], "render"]


def _clamped_scores(values, floor):
    return [max(floor, value - 10) for value in values]


def _stack_order(word):
    return [(word + ">")[::-1], word[::-1] + ">"]


def _flaky_run(fail_times, attempts):
    calls = 0
    for _ in range(attempts):
        calls += 1
        if calls <= fail_times:
            continue
        return ["ok", calls]
    return ["gave up", calls]


def _timing_report(ticks, values):
    done = [value * 2 for value in values]
    elapsed = [ticks[2 * i + 1] - ticks[2 * i] for i in range(len(values))]
    return [done, elapsed]


def _remembered(values):
    return [[value * value for value in values], list(values)]


# -- context managers --------------------------------------------------------

def _tally_run(values):
    return ["open"] + list(values) + ["close"]


def _door_log(steps, fail):
    log = ["open"] + list(steps) + ["close"]
    if fail:
        log.append("caught")
    return log


def _session_log(name, actions):
    return ["open:" + name] + list(actions) + ["close:" + name]


def _vault_log(steps, fail):
    log = ["unlock"] + list(steps)
    log.append("lock")
    if fail:
        log.append("caught")
    return log


def _scope_log(name, actions):
    return ["enter:" + name] + list(actions) + ["exit:" + name]


def _guarded_run(steps, fail):
    log = ["start"] + list(steps)
    if fail:
        log.extend(["saw-error", "end", "caught"])
    else:
        log.append("end")
    return log


def _suppress_run(kind):
    if kind == "value":
        return ["ValueError", None]
    if kind == "key":
        return ["KeyError", None]
    if kind == "type":
        return [None, "TypeError"]
    return [None, None]


def build() -> list:
    return [
        # ===================================================================
        # ITERATORS — the protocol everything else in this file stands on
        # ===================================================================

        drill(
            "gen-iter-cursor", "The Cursor", "GUIDED",
            """
            `iter(x)` turns any iterable into a CURSOR. `next(cursor)` pulls one
            value out and moves the cursor forward. That is the entire protocol,
            and every `for` loop you have ever written is built on it.

            Return the first two values of `items` as a list, using the cursor.
            `items` always holds at least two values here.
            """,
            "first_two", "items", _first_two,
            """
            def first_two(items):
                cursor = iter(items)
                return [next(cursor), next(cursor)]
            """,
            [("two", [[1, 2]]), ("letters", [["a", "b", "c"]])],
            [("numbers", [[10, 20, 30]]), ("nested", [[[1], [2]]])],
            edges=[("exactly two", [[0, 0]])],
            family="python_iterators", time="O(1)",
            starter="""
            def first_two(items):
                # `next()` needs something to advance. Make one out of `items`.
                cursor = __BLANK__
                return [next(cursor), next(cursor)]
            """,
            nudge="A list is not a cursor. A list can be asked for a cursor.",
            pseudocode="cursor = a cursor over items\nreturn [pull one, pull one more]",
            fragment=_same_move("letters = iter('abc')\nnext(letters)   # 'a'"),
            failures=["Calling `next(items)` directly — a list is iterable, "
                      "but it is not itself an iterator"],
            tags=["iterators"],
        ),

        drill(
            "gen-iter-default", "Asking Past The End", "GUIDED",
            """
            When a cursor is empty, `next(cursor)` raises StopIteration. Give
            `next` a second argument and it hands that back instead of raising.

            Return the third value of `items`, or None when there is no third
            value. The first two are already being skipped for you.
            """,
            "third_or_none", "items", _third_or_none,
            """
            def third_or_none(items):
                cursor = iter(items)
                next(cursor, None)
                next(cursor, None)
                return next(cursor, None)
            """,
            [("three", [[1, 2, 3]]), ("two only", [[1, 2]])],
            [("four", [[1, 2, 3, 4]]), ("one", [[9]])],
            edges=[("empty", [[]])],
            family="python_iterators", time="O(1)", after="gen-iter-cursor",
            starter="""
            def third_or_none(items):
                cursor = iter(items)
                next(cursor, None)    # skip the first
                next(cursor, None)    # skip the second
                # the third value, or None if the cursor has already run out
                return __BLANK__
            """,
            nudge="The same call as the two skips above it. Nothing new.",
            pseudocode="pull one more, with None as the fallback",
            fragment=_same_move("next(iter([]), 'nothing here')   # 'nothing here'"),
            failures=["Letting StopIteration escape the function, which reads as "
                      "a crash to whoever called you"],
            tags=["iterators"],
        ),

        drill(
            "gen-iter-manual", "What `for` Actually Does", "TUTORIAL",
            """
            A `for` loop is sugar. Underneath, Python calls `iter()` once, then
            `next()` until StopIteration is raised, and swallows that exception
            as the signal to stop.

            Write that loop out by hand: sum `items` using only `iter`, `next`
            and a try/except. No `for`, no `sum`.
            """,
            "manual_sum", "items", _manual_sum,
            """
            def manual_sum(items):
                cursor = iter(items)
                total = 0
                while True:
                    try:
                        total += next(cursor)
                    except StopIteration:
                        return total
            """,
            [("three", [[1, 2, 3]]), ("one", [[5]])],
            [("negatives", [[-1, -2]]), ("zeros", [[0, 0, 0]])],
            edges=[("empty", [[]])],
            family="python_iterators", after="gen-iter-default",
            starter="""
            def manual_sum(items):
                # 1. make a cursor over `items`
                # 2. start a running total at 0
                # 3. loop forever, adding `next(cursor)` to the total
                # 4. when next() raises StopIteration, the sequence is over:
                #    return the total from inside the except block
                pass
            """,
            nudge="StopIteration is not an error here. It is the end-of-input "
                  "message, and catching it is the whole job.",
            pseudocode="cursor = iter(items)\ntotal = 0\nloop forever:\n"
                       "  try: total += next(cursor)\n  except StopIteration: return total",
            failures=["Catching bare `Exception`, which also swallows the real "
                      "errors your loop body raises"],
            tags=["iterators"],
        ),

        drill(
            "gen-iter-shared", "One Cursor, Two Readers", "TUTORIAL",
            """
            An iterator is consumed, not copied. Whatever one reader pulls out is
            gone for the next reader — which is the single most common surprise
            in code that passes iterators around.

            Take the first two values with `itertools.islice`, then the rest with
            `list`, both from the SAME cursor. Return them as two lists.
            """,
            "split_in_two", "items", _split_in_two,
            """
            def split_in_two(items):
                from itertools import islice

                cursor = iter(items)
                head = list(islice(cursor, 2))
                tail = list(cursor)
                return [head, tail]
            """,
            [("five", [[1, 2, 3, 4, 5]]), ("three letters", [["a", "b", "c"]])],
            [("exactly two", [[1, 2]]), ("one", [[7]])],
            edges=[("empty", [[]])],
            family="python_iterators", after="gen-iter-manual",
            starter="""
            def split_in_two(items):
                from itertools import islice

                # 1. one cursor over items — both reads must share it
                # 2. head: the first two values, via islice(cursor, 2)
                # 3. tail: everything the cursor has left, via list()
                # 4. return [head, tail]
                pass
            """,
            nudge="If you call `iter(items)` twice you get two independent "
                  "cursors, and `tail` comes back holding everything.",
            pseudocode="cursor = iter(items)\nhead = list(islice(cursor, 2))\n"
                       "tail = list(cursor)\nreturn [head, tail]",
            failures=["Building a second cursor, so the two halves overlap"],
            tags=["iterators"],
        ),

        drill(
            "gen-iter-class", "The Countdown Object", "EASY",
            """
            Any object is iterable if it answers `__iter__`. Any object is an
            ITERATOR if it also answers `__next__` and raises StopIteration when
            it is spent.

            Finish `Countdown` so that looping over `Countdown(5)` yields
            5, 4, 3, 2, 1 and then stops. `countdown_values` is written for you
            and only drains it into a list.
            """,
            "countdown_values", "start", _countdown_values,
            """
            class Countdown:
                def __init__(self, start):
                    self.current = start

                def __iter__(self):
                    # An iterator is its own iterable. `for` calls this first.
                    return self

                def __next__(self):
                    if self.current <= 0:
                        raise StopIteration
                    value = self.current
                    self.current -= 1
                    return value


            def countdown_values(start):
                return list(Countdown(start))
            """,
            [("five", [5]), ("one", [1])],
            [("three", [3]), ("ten", [10])],
            edges=[("zero", [0]), ("negative", [-4])],
            family="python_iterators", after="gen-iter-shared",
            pattern="SIMULATION",
            starter="""
            class Countdown:
                def __init__(self, start):
                    self.current = start

                def __iter__(self):
                    # hand back the object that answers __next__
                    pass

                def __next__(self):
                    # when there is nothing left, raise StopIteration;
                    # otherwise return the current value and step down by one
                    pass


            def countdown_values(start):
                return list(Countdown(start))
            """,
            nudge="`raise StopIteration` is a statement, not a return value. "
                  "Returning None instead gives you an infinite list of Nones.",
            pseudocode="__iter__: return self\n__next__:\n  if spent: raise StopIteration\n"
                       "  remember current, step down, return what you remembered",
            failures=["Stepping down before returning, which loses the first value",
                      "Returning None at the end instead of raising StopIteration"],
            tags=["iterators", "protocol"],
        ),

        drill(
            "gen-iter-reiterable", "An Object You Can Loop Twice", "EASY",
            """
            `Countdown` was an iterator: it is spent after one pass. Most things
            you loop over are not iterators — a list is not — they are ITERABLES
            that hand out a fresh iterator every time `__iter__` is called.

            Write `Steps` so it can be looped over any number of times. The
            easiest way: make `__iter__` a generator function, so each call
            produces a new run.

            `step` is always at least 1.
            """,
            "twice_over", "start, stop, step", _twice_over,
            """
            class Steps:
                def __init__(self, start, stop, step):
                    self.start = start
                    self.stop = stop
                    self.step = step

                def __iter__(self):
                    # `yield` here means every call builds a brand new generator,
                    # so two loops over the same Steps do not share a position.
                    value = self.start
                    while value < self.stop:
                        yield value
                        value += self.step


            def twice_over(start, stop, step):
                steps = Steps(start, stop, step)
                return [list(steps), list(steps)]
            """,
            [("by one", [0, 4, 1]), ("by two", [1, 7, 2])],
            [("empty range", [5, 5, 1]), ("step past the end", [0, 10, 7])],
            edges=[("stop below start", [3, 1, 1])],
            family="python_iterators", after="gen-iter-class",
            pattern="SIMULATION",
            starter="""
            class Steps:
                def __init__(self, start, stop, step):
                    self.start = start
                    self.stop = stop
                    self.step = step

                def __iter__(self):
                    # a fresh run every time this is called
                    pass


            def twice_over(start, stop, step):
                steps = Steps(start, stop, step)
                return [list(steps), list(steps)]
            """,
            nudge="If the second list comes back empty, you built an iterator "
                  "and handed out the same one twice.",
            pseudocode="__iter__:\n  value = start\n  while value < stop:\n"
                       "    yield value\n    value += step",
            failures=["Storing the cursor on `self`, which makes the object "
                      "single-use again"],
            tags=["iterators", "protocol"],
        ),

        drill(
            "gen-iter-cycle", "The Wheel", "MEDIUM",
            """
            Write `Cycle`, an iterator that walks `items` forever, wrapping back
            to the start when it reaches the end. Then `cycle_take(items, n)`
            returns the first `n` values it produces.

            An empty `items` has nothing to cycle: it must stop immediately
            rather than spin.
            """,
            "cycle_take", "items, n", _cycle_take,
            """
            class Cycle:
                def __init__(self, items):
                    self.items = list(items)
                    self.index = 0

                def __iter__(self):
                    return self

                def __next__(self):
                    if not self.items:
                        raise StopIteration
                    value = self.items[self.index]
                    self.index = (self.index + 1) % len(self.items)
                    return value


            def cycle_take(items, n):
                from itertools import islice

                return list(islice(Cycle(items), n))
            """,
            [("three of two", [[1, 2], 3]), ("exact", [["a", "b"], 2])],
            [("more than twice round", [[1, 2, 3], 7]), ("one item", [[9], 4])],
            edges=[("empty source", [[], 3]), ("take none", [[1, 2], 0])],
            family="python_iterators", after="gen-iter-reiterable",
            pattern="SIMULATION", time="O(n)",
            starter="""
            class Cycle:
                def __init__(self, items):
                    self.items = list(items)
                    self.index = 0

                def __iter__(self):
                    return self

                def __next__(self):
                    # wrap the index round; an empty source stops immediately
                    pass


            def cycle_take(items, n):
                from itertools import islice

                return list(islice(Cycle(items), n))
            """,
            nudge="Modulo is the wheel. The only special case is having no "
                  "spokes at all.",
            pseudocode="__next__:\n  if no items: raise StopIteration\n"
                       "  value = items[index]\n  index = (index + 1) % len(items)\n"
                       "  return value",
            failures=["Forgetting the empty case, which hangs the grader rather "
                      "than failing it"],
            tags=["iterators", "infinite"],
        ),

        drill(
            "gen-iter-peek", "The Peeking Cursor", "MEDIUM",
            """
            The iterator protocol has no `peek`. You cannot look at the next
            value without consuming it — so when you need one, you build a
            wrapper that keeps one value in hand.

            Write `Peekable`. It wraps any iterable and offers `has_next()`,
            `peek()` (the next value, not consumed) and `__next__`.

            `compress_runs` is written for you: it uses `peek` to run-length
            encode a sequence, returning [value, length] pairs. Make it work.
            """,
            "compress_runs", "items", _compress_runs,
            """
            class Peekable:
                # The sentinel has to be an object nothing else can equal, or a
                # stream containing None looks identical to a spent stream.
                _EMPTY = object()

                def __init__(self, source):
                    self.source = iter(source)
                    self.ahead = next(self.source, self._EMPTY)

                def has_next(self):
                    return self.ahead is not self._EMPTY

                def peek(self):
                    return self.ahead

                def __iter__(self):
                    return self

                def __next__(self):
                    if self.ahead is self._EMPTY:
                        raise StopIteration
                    value = self.ahead
                    self.ahead = next(self.source, self._EMPTY)
                    return value


            def compress_runs(items):
                cursor = Peekable(items)
                out = []
                while cursor.has_next():
                    value = next(cursor)
                    length = 1
                    while cursor.has_next() and cursor.peek() == value:
                        next(cursor)
                        length += 1
                    out.append([value, length])
                return out
            """,
            [("runs", [[1, 1, 2, 3, 3, 3]]), ("no runs", [["a", "b"]])],
            [("all the same", [[4, 4, 4, 4]]), ("single", [[7]])],
            edges=[("empty", [[]]), ("run at the end", [[1, 2, 2]])],
            family="python_iterators", after="gen-iter-cycle",
            pattern="SIMULATION",
            starter="""
            class Peekable:
                _EMPTY = object()       # a value no real element can equal

                def __init__(self, source):
                    # keep one value in hand, and remember where the rest is
                    pass

                def has_next(self):
                    pass

                def peek(self):
                    pass

                def __iter__(self):
                    return self

                def __next__(self):
                    # hand back the value in hand, and pull the next one into it
                    pass


            def compress_runs(items):
                cursor = Peekable(items)
                out = []
                while cursor.has_next():
                    value = next(cursor)
                    length = 1
                    while cursor.has_next() and cursor.peek() == value:
                        next(cursor)
                        length += 1
                    out.append([value, length])
                return out
            """,
            nudge="One value of lookahead is all you need, and it lives on the "
                  "object between calls.",
            pseudocode="__init__: ahead = next(source, EMPTY)\n"
                       "has_next: ahead is not EMPTY\npeek: ahead\n"
                       "__next__: value = ahead; ahead = next(source, EMPTY); return value",
            failures=["Using None as the sentinel, which breaks on a stream that "
                      "legitimately contains None"],
            tags=["iterators", "lookahead"],
        ),

        # ===================================================================
        # GENERATORS — the same protocol, written as a function
        # ===================================================================

        drill(
            "gen-yield-first", "The First Yield", "GUIDED",
            """
            A function with `yield` in it is not a normal function. Calling it
            runs none of the body: it hands back a GENERATOR, and the body only
            advances when something pulls a value out of it.

            `squares_list` is written for you and does the pulling. Make
            `squares` hand back i times i for each i below n.
            """,
            "squares_list", "n", _squares_list,
            """
            def squares(n):
                for i in range(n):
                    yield i * i


            def squares_list(n):
                return list(squares(n))
            """,
            [("five", [5]), ("one", [1])],
            [("three", [3]), ("ten", [10])],
            edges=[("zero", [0])],
            after="gen-iter-manual", time="O(n)", space="O(1)",
            starter="""
            def squares(n):
                for i in range(n):
                    __BLANK__       # hand back this number's square, then pause here


            def squares_list(n):
                return list(squares(n))
            """,
            nudge="`return` leaves for good. The other one leaves a bookmark.",
            pseudocode="for i below n:\n  yield i * i",
            fragment=_same_move("def evens(n):\n    for i in range(n):\n        yield i * 2"),
            failures=["Using `return i * i`, which ends the generator after one value"],
            tags=["generators", "yield"],
        ),

        drill(
            "gen-yield-filter", "Yield Only What Matters", "GUIDED",
            """
            A generator does not have to yield on every pass of its loop. Skip a
            value and the consumer simply never sees it — no list was built and
            then filtered, because no list was built at all.

            Yield only the even values of `nums`.
            """,
            "evens_list", "nums", _evens_list,
            """
            def evens(nums):
                for value in nums:
                    if value % 2 == 0:
                        yield value


            def evens_list(nums):
                return list(evens(nums))
            """,
            [("mixed", [[1, 2, 3, 4]]), ("none even", [[1, 3]])],
            [("negatives", [[-2, -3]]), ("zero", [[0, 1]])],
            edges=[("empty", [[]])],
            after="gen-yield-first", time="O(n)", space="O(1)",
            starter="""
            def evens(nums):
                for value in nums:
                    if __BLANK__:        # keep it only when it divides by two
                        yield value


            def evens_list(nums):
                return list(evens(nums))
            """,
            nudge="`-3 % 2` is 1 in Python, not -1, so the same test works for "
                  "negative numbers.",
            pseudocode="for value in nums:\n  if value is even:\n    yield value",
            fragment=_same_move("if len(word) > 3:\n    yield word"),
            tags=["generators", "yield"],
        ),

        drill(
            "gen-genexp-blank", "Parentheses, Not Brackets", "GUIDED",
            """
            `[x for x in y]` builds a list and hands it over. `(x for x in y)`
            builds nothing: it hands over a generator that will produce values
            when asked. Anything that consumes one value at a time — `sum`,
            `max`, `any`, `min` — is happy with either, and only one of them
            costs memory.

            Return the sum of the squares of `nums`, without building a list.
            """,
            "total_of_squares", "nums", _total_of_squares,
            """
            def total_of_squares(nums):
                return sum(value * value for value in nums)
            """,
            [("three", [[1, 2, 3]]), ("negatives", [[-2, 2]])],
            [("zero", [[0]]), ("bigger", [[10, 20]])],
            edges=[("empty", [[]])],
            after="gen-yield-filter", time="O(n)", space="O(1)",
            starter="""
            def total_of_squares(nums):
                # brackets here would build the whole list first. Use parentheses,
                # which inside a single call you may leave out entirely.
                return sum(__BLANK__)
            """,
            nudge="When the genexp is the only argument, `sum(x * x for x in nums)` "
                  "needs no extra brackets of any kind.",
            pseudocode="sum of (value * value) over nums",
            fragment=_same_move("longest = max(len(w) for w in words)"),
            failures=["`sum([...])` — correct, and it builds the whole list to "
                      "throw it away one line later"],
            tags=["generators", "genexp"],
        ),

        drill(
            "gen-lazy-first", "Stop At The First Match", "TUTORIAL",
            """
            Laziness is not only about memory. A generator that is never fully
            consumed never fully runs — so `next(genexp, default)` finds the
            first match and stops, however long the rest of the input is.

            Return the first word in `words` at least `least` characters long,
            or the empty string if there is none. One expression is enough.
            """,
            "first_long_word", "words, least", _first_long_word,
            """
            def first_long_word(words, least):
                return next((word for word in words if len(word) >= least), "")
            """,
            [("second matches", [["ab", "abcd", "abcde"], 4]),
             ("first matches", [["hello", "x"], 2])],
            [("none match", [["a", "b"], 3]), ("exact length", [["abc"], 3])],
            edges=[("empty", [[], 1])],
            after="gen-genexp-blank", time="O(n)", space="O(1)",
            starter="""
            def first_long_word(words, least):
                # 1. a generator expression over `words`, keeping only the long ones
                # 2. `next(..., "")` pulls the first one, or the fallback if there
                #    is no first one. Note the brackets: a genexp passed alongside
                #    another argument needs its own parentheses.
                pass
            """,
            nudge="A loop with an early `return` does the same thing. This is the "
                  "one-line version of that loop, and it is the idiom interviewers "
                  "recognise.",
            pseudocode='next((w for w in words if len(w) >= least), "")',
            failures=["Omitting the default, so a no-match input raises "
                      "StopIteration instead of answering"],
            tags=["generators", "genexp", "laziness"],
        ),

        drill(
            "gen-yield-pairs", "Yielding More Than Numbers", "TUTORIAL",
            """
            A generator can yield anything, including pairs — which is how you
            stream structured records without materialising them.

            Yield [line number, cleaned text] for each line of `lines` that is
            not blank. Line numbers start at 1 and count blank lines too. Clean
            a line with `.strip()`.
            """,
            "numbered_list", "lines", _numbered_list,
            """
            def numbered(lines):
                for index, line in enumerate(lines, 1):
                    text = line.strip()
                    if text:
                        yield [index, text]


            def numbered_list(lines):
                return list(numbered(lines))
            """,
            [("two lines", [["alpha", "beta"]]), ("blank in the middle", [["a", "", "b"]])],
            [("whitespace only", [["  ", "x"]]), ("padded", [[" y "]])],
            edges=[("all blank", [["", ""]]), ("empty", [[]])],
            after="gen-lazy-first", time="O(n)", space="O(1)",
            starter="""
            def numbered(lines):
                # 1. enumerate(lines, 1) gives you the number and the line together
                # 2. strip the line
                # 3. if anything is left, yield [number, stripped text]
                pass


            def numbered_list(lines):
                return list(numbered(lines))
            """,
            nudge="`enumerate(lines, 1)` starts counting at 1, so you never write "
                  "`index + 1` anywhere.",
            pseudocode="for index, line in enumerate(lines, 1):\n  text = line.strip()\n"
                       "  if text: yield [index, text]",
            failures=["Counting only the non-blank lines, so the numbers no longer "
                      "match the file"],
            tags=["generators", "yield"],
        ),

        drill(
            "gen-yieldfrom-blank", "Delegating The Whole Run", "GUIDED",
            """
            `yield from x` means: yield every value `x` produces, one at a time,
            and do not come back until it is spent. It is the loop

                for value in x:
                    yield value

            written once.

            `chain` yields everything in `first`, then everything in `second`.
            """,
            "chain_list", "first, second", _chain_list,
            """
            def chain(first, second):
                yield from first
                yield from second


            def chain_list(first, second):
                return list(chain(first, second))
            """,
            [("two lists", [[1, 2], [3, 4]]), ("letters", [["a"], ["b", "c"]])],
            [("first empty", [[], [1]]), ("second empty", [[1], []])],
            edges=[("both empty", [[], []])],
            after="gen-yield-pairs", time="O(n)", space="O(1)",
            starter="""
            def chain(first, second):
                yield from first
                __BLANK__        # now the same, for `second`


            def chain_list(first, second):
                return list(chain(first, second))
            """,
            nudge="The line above it is the answer with one word changed.",
            pseudocode="yield from first\nyield from second",
            fragment=_same_move("def both(a, b):\n    yield from a\n    yield from b"),
            failures=["`yield second`, which yields the list itself as a single value"],
            tags=["generators", "yield-from"],
        ),

        drill(
            "gen-yieldfrom-chain", "Two Sources, One Stream", "TUTORIAL",
            """
            Write `interleaved_then_rest`: yield the values of `first`, then the
            values of `second`, then the string "done". Use `yield from` for the
            two sequences and a plain `yield` for the marker — they mix freely
            in one generator.
            """,
            "stream_list", "first, second", _stream_list,
            """
            def stream(first, second):
                yield from first
                yield from second
                yield "done"


            def stream_list(first, second):
                return list(stream(first, second))
            """,
            [("two lists", [["a"], ["b"]]), ("numbers", [[1, 2], [3]])],
            [("first empty", [[], ["x"]]), ("second empty", [["x"], []])],
            edges=[("both empty", [[], []])],
            after="gen-yieldfrom-blank", time="O(n)", space="O(1)",
            starter="""
            def stream(first, second):
                # 1. yield from the first sequence
                # 2. yield from the second
                # 3. yield the single value "done"
                pass


            def stream_list(first, second):
                return list(stream(first, second))
            """,
            nudge="`yield from` takes an iterable. `yield` takes one value. The "
                  "marker is one value.",
            pseudocode='yield from first\nyield from second\nyield "done"',
            failures=['`yield from "done"`, which yields four separate characters'],
            tags=["generators", "yield-from"],
        ),

        drill(
            "gen-yieldfrom-flatten", "Unfolding With yield from", "EASY",
            """
            Flatten a list of lists into one stream, one level deep, preserving
            order. Write it as a generator: nothing larger than a single value
            is ever held.
            """,
            "concat_all", "groups", _concat_all,
            """
            def flatten(groups):
                for group in groups:
                    yield from group


            def concat_all(groups):
                return list(flatten(groups))
            """,
            [("simple", [[[1, 2], [3]]]), ("uneven", [[[1], [], [2, 3]]])],
            [("all empty", [[[], []]]), ("strings", [[["a"], ["b"]]])],
            edges=[("empty", [[]])],
            after="gen-yieldfrom-chain", time="O(n)", space="O(1)",
            starter="""
            def flatten(groups):
                # one `for` and one `yield from`
                pass


            def concat_all(groups):
                return list(flatten(groups))
            """,
            nudge="The list comprehension version is `[v for g in groups for v in g]`. "
                  "This is the same two loops, without the list.",
            pseudocode="for group in groups:\n  yield from group",
            tags=["generators", "yield-from"],
        ),

        drill(
            "gen-infinite-naturals", "A Source With No End", "EASY",
            """
            This is the argument for generators, and it is not about speed.

            `naturals(start)` yields start, start + 1, start + 2, and never
            stops. There is no list version of this function. Not a slow one,
            not a big one — there is no last natural number to put at the end of
            the list, so the list cannot exist. A generator can, because it only
            ever holds the value it is on.

            `first_n` is written for you: it uses `islice` to take n values and
            then walks away, leaving the rest unproduced.
            """,
            "first_n", "start, n", _first_n,
            """
            def naturals(start):
                value = start
                while True:
                    yield value
                    value += 1


            def first_n(start, n):
                from itertools import islice

                return list(islice(naturals(start), n))
            """,
            [("five from one", [1, 5]), ("three from zero", [0, 3])],
            [("from negative", [-2, 4]), ("just one", [7, 1])],
            edges=[("none", [3, 0])],
            perf=[("ten thousand", [0, 10000])],
            after="gen-yieldfrom-flatten", time="O(n)", space="O(1)",
            starter="""
            def naturals(start):
                # an endless counter: yield the value, then step it up, forever
                pass


            def first_n(start, n):
                from itertools import islice

                return list(islice(naturals(start), n))
            """,
            nudge="`while True` with a `yield` inside it is not an infinite loop. "
                  "It is a loop that runs exactly as often as someone asks it to.",
            pseudocode="value = start\nwhile True:\n  yield value\n  value += 1",
            failures=["Building a list inside `naturals`, which never returns",
                      "Putting the increment before the yield, which skips `start`"],
            tags=["generators", "infinite", "memory"],
        ),

        drill(
            "gen-return-stops", "return Ends A Generator", "EASY",
            """
            Inside a generator, `return` does not hand back a value. It raises
            StopIteration — it means "this stream is over", and the consumer's
            loop simply ends.

            Yield values from `nums` until you meet one that is `limit` or
            larger, then stop. Values after that one are never produced.
            """,
            "take_until_limit", "nums, limit", _take_until_limit,
            """
            def under_limit(nums, limit):
                for value in nums:
                    if value >= limit:
                        return
                    yield value


            def take_until_limit(nums, limit):
                return list(under_limit(nums, limit))
            """,
            [("stops in the middle", [[1, 2, 9, 3], 5]), ("never reaches it", [[1, 2], 5])],
            [("stops at once", [[9, 1], 5]), ("equal counts as over", [[5], 5])],
            edges=[("empty", [[], 3]), ("all under", [[-1, 0], 1])],
            after="gen-infinite-naturals", time="O(n)", space="O(1)",
            starter="""
            def under_limit(nums, limit):
                # walk nums; the moment a value reaches the limit, `return`
                # (with nothing after it) and the stream is over
                pass


            def take_until_limit(nums, limit):
                return list(under_limit(nums, limit))
            """,
            nudge="`break` would also work here. `return` is worth knowing because "
                  "it works from anywhere in the body, not just inside the loop.",
            pseudocode="for value in nums:\n  if value >= limit: return\n  yield value",
            failures=["`return value`, which silently discards the value — a "
                      "generator's return value is not yielded"],
            tags=["generators", "yield"],
        ),

        drill(
            "gen-genexp-pipeline", "A Pipeline, Not A Pile", "EASY",
            """
            Generator expressions compose. Feeding one into the next builds a
            PIPELINE where each value is carried end to end and then dropped —
            as opposed to three intermediate lists, each the size of the input.

            Given `lines`, return the total number of characters in the lines
            that survive two rules: strip each line, then drop the ones that are
            empty or start with "#". Build no lists.
            """,
            "payload_bytes", "lines", _payload_bytes,
            """
            def payload_bytes(lines):
                stripped = (line.strip() for line in lines)
                kept = (line for line in stripped
                        if line and not line.startswith("#"))
                return sum(len(line) for line in kept)
            """,
            [("comment and code", [["# note", "abc"]]), ("blank lines", [["", " x "]])],
            [("all comments", [["#a", "#b"]]), ("mixed", [[" hello ", "#skip", "hi"]])],
            edges=[("empty", [[]]), ("whitespace only", [["   "]])],
            after="gen-return-stops", time="O(n)", space="O(1)",
            starter="""
            def payload_bytes(lines):
                # 1. a genexp that strips every line
                # 2. a genexp over THAT one, keeping the lines that are neither
                #    empty nor comments
                # 3. sum(len(line) for line in ...) over the survivors
                pass
            """,
            nudge="Each stage reads from the stage before it. Nothing is stored "
                  "between them, which is the whole point.",
            pseudocode="stripped = (line.strip() for line in lines)\n"
                       "kept = (l for l in stripped if l and not l.startswith('#'))\n"
                       "return sum(len(l) for l in kept)",
            failures=["Stripping twice, or checking `startswith` before stripping — "
                      "an indented comment then counts as payload"],
            tags=["generators", "genexp", "pipeline"],
        ),

        drill(
            "gen-chunked", "Chunking A Stream", "MEDIUM",
            """
            Batch a stream into lists of at most `size`, without ever knowing how
            long the stream is. This is the shape of every "insert 1000 rows at a
            time" loop you will ever write.

            `chunked(source, size)` takes an ITERATOR and yields lists. It may
            not index, slice or call `len` on the source — none of those exist
            for a stream. `itertools.islice(cursor, size)` pulls up to `size`
            values off the front, and an empty result means the source is spent.

            A `size` of zero or less yields nothing.
            """,
            "chunk_list", "items, size", _chunk_list,
            """
            def chunked(source, size):
                from itertools import islice

                cursor = iter(source)
                while True:
                    block = list(islice(cursor, size))
                    if not block:
                        return
                    yield block


            def chunk_list(items, size):
                if size <= 0:
                    return []
                return list(chunked(iter(items), size))
            """,
            [("even split", [[1, 2, 3, 4], 2]), ("ragged", [[1, 2, 3], 2])],
            [("size one", [[1, 2], 1]), ("size past the end", [[1], 5])],
            edges=[("empty", [[], 3]), ("size zero", [[1, 2], 0])],
            after="gen-genexp-pipeline", time="O(n)", space="O(k)",
            pattern="SIMULATION",
            starter="""
            def chunked(source, size):
                from itertools import islice

                # 1. one cursor over the source
                # 2. loop: pull up to `size` values into a list
                # 3. an empty list means the source is spent — stop
                # 4. otherwise yield the block and go round again
                pass


            def chunk_list(items, size):
                if size <= 0:
                    return []
                return list(chunked(iter(items), size))
            """,
            nudge="The cursor is created ONCE, outside the loop. Inside the loop, "
                  "islice takes the next slice off the front of it.",
            pseudocode="cursor = iter(source)\nwhile True:\n"
                       "  block = list(islice(cursor, size))\n"
                       "  if not block: return\n  yield block",
            failures=["Calling `iter(source)` inside the loop, which restarts the "
                      "stream and yields the first chunk forever"],
            tags=["generators", "streaming"],
        ),

        drill(
            "gen-windows", "Windows Over A Stream", "MEDIUM",
            """
            Yield every window of exactly `k` consecutive values from a stream,
            in order. Again: no indexing and no `len` on the source, because a
            stream has neither.

            A `deque(maxlen=k)` is the tool. It drops from the left
            automatically as you append, so the window is always the last k
            values seen — yield a copy of it once it is full.

            Fewer than k values overall means no windows at all. A `k` of zero
            or less means the same.
            """,
            "window_list", "items, k", _window_list,
            """
            def windows(source, k):
                from collections import deque

                window = deque(maxlen=k)
                for value in source:
                    window.append(value)
                    if len(window) == k:
                        yield list(window)


            def window_list(items, k):
                if k <= 0:
                    return []
                return list(windows(iter(items), k))
            """,
            [("three of two", [[1, 2, 3], 2]), ("exact fit", [[1, 2], 2])],
            [("k of one", [[5, 6], 1]), ("k past the end", [[1], 3])],
            edges=[("empty", [[], 2]), ("k zero", [[1, 2], 0])],
            after="gen-chunked", time="O(n)", space="O(k)",
            pattern="SLIDING_WINDOW", secondary=["QUEUE"],
            starter="""
            def windows(source, k):
                from collections import deque

                # 1. a deque with maxlen=k — it evicts from the left for you
                # 2. for each value: append it
                # 3. once the deque holds k values, yield a LIST copy of it
                pass


            def window_list(items, k):
                if k <= 0:
                    return []
                return list(windows(iter(items), k))
            """,
            nudge="Yield `list(window)`, not `window`. Yielding the deque itself "
                  "hands out the same object every time, and it keeps changing.",
            pseudocode="window = deque(maxlen=k)\nfor value in source:\n"
                       "  window.append(value)\n  if len(window) == k: yield list(window)",
            failures=["Yielding the deque itself, so every window in the output "
                      "ends up identical to the last one"],
            tags=["generators", "streaming"],
        ),

        drill(
            "gen-merge-streams", "Merging Two Sorted Streams", "MEDIUM",
            """
            Merge two already-sorted streams into one sorted stream, lazily. Pull
            one value from each, yield the smaller, refill from the side it came
            from. When one side runs dry, drain the other.

            Sorting the concatenation would also produce the right answer — and
            it would need both inputs in memory at once, which is exactly what a
            stream merge exists to avoid.

            Use `next(cursor, sentinel)` rather than try/except; it keeps the
            loop readable. The sentinel must be an object no real value can
            equal.
            """,
            "merge_lists", "left, right", _merge_lists,
            """
            _SPENT = object()


            def merge_streams(left, right):
                a, b = iter(left), iter(right)
                x, y = next(a, _SPENT), next(b, _SPENT)
                while x is not _SPENT and y is not _SPENT:
                    if x <= y:
                        yield x
                        x = next(a, _SPENT)
                    else:
                        yield y
                        y = next(b, _SPENT)
                while x is not _SPENT:
                    yield x
                    x = next(a, _SPENT)
                while y is not _SPENT:
                    yield y
                    y = next(b, _SPENT)


            def merge_lists(left, right):
                return list(merge_streams(iter(left), iter(right)))
            """,
            [("interleaved", [[1, 3, 5], [2, 4]]), ("disjoint", [[1, 2], [8, 9]])],
            [("duplicates", [[1, 1], [1, 2]]), ("one side empty", [[], [3, 4]])],
            edges=[("both empty", [[], []]), ("other side empty", [[1], []])],
            after="gen-windows", time="O(n)", space="O(1)",
            pattern="TWO_POINTER",
            starter="""
            _SPENT = object()


            def merge_streams(left, right):
                # 1. a cursor over each side, and one value held from each
                # 2. while BOTH are live: yield the smaller, refill from that side
                # 3. then drain whichever side still has values
                pass


            def merge_lists(left, right):
                return list(merge_streams(iter(left), iter(right)))
            """,
            nudge="Two held values and two cursors. The held value is the one you "
                  "are comparing; refill it only from the side you just yielded.",
            pseudocode="x, y = next(a, SPENT), next(b, SPENT)\n"
                       "while both live:\n  yield the smaller; refill from that side\n"
                       "drain a\ndrain b",
            failures=["Refilling both sides after each yield, which drops values",
                      "Using `<` instead of `<=`, which is not wrong here but "
                      "makes the merge unstable when the two sides tie"],
            tags=["generators", "streaming", "merge"],
        ),

        drill(
            "gen-deep-flatten", "yield from, All The Way Down", "MEDIUM",
            """
            `yield from` delegates to any iterable — including another call to
            the generator you are writing. That makes recursive streaming almost
            free.

            Flatten arbitrarily nested lists into one stream of non-list values,
            in order. A value is nested if `isinstance(value, list)`.
            """,
            "deep_flatten_list", "value", _deep_flatten_list,
            """
            def deep_flatten(value):
                for item in value:
                    if isinstance(item, list):
                        yield from deep_flatten(item)
                    else:
                        yield item


            def deep_flatten_list(value):
                return list(deep_flatten(value))
            """,
            [("two deep", [[1, [2, 3], 4]]), ("already flat", [[1, 2]])],
            [("three deep", [[[[1]], 2]]), ("empty inner", [[[], [1]]])],
            edges=[("empty", [[]]), ("nothing but empties", [[[], [[]]]])],
            after="gen-merge-streams", time="O(n)", space="O(d)",
            pattern="RECURSION",
            starter="""
            def deep_flatten(value):
                # for each item: if it is a list, delegate to yourself;
                # otherwise yield it
                pass


            def deep_flatten_list(value):
                return list(deep_flatten(value))
            """,
            nudge="`yield deep_flatten(item)` yields a generator OBJECT. "
                  "`yield from` yields its values.",
            pseudocode="for item in value:\n  if it is a list: yield from deep_flatten(item)\n"
                       "  else: yield item",
            failures=["`yield` instead of `yield from` on the recursive call, "
                      "which produces a list of generator objects"],
            tags=["generators", "yield-from", "recursion"],
        ),

        drill(
            "gen-ledger-scan", "The Ledger That Does Not Fit", "HARD",
            """
            The ledger has no end. Entries are produced by a linear congruential
            generator: starting from `seed`, each step sets

                value = (value * 1103515245 + 12345) % 2147483648

            and the entry for that step is `value % 100 + 1` — so every entry is
            between 1 and 100. The first entry is the one produced by the FIRST
            step, not the seed itself.

            Return [index, total] for the first entry, counting from 1, at which
            the running total reaches `target` or more.

            There is no list here to build. Write the ledger as an endless
            generator, consume it until the condition holds, and stop. Your
            memory use must not grow with the index you end up returning.
            """,
            "index_of_total", "seed, target", _index_of_total,
            """
            def ledger(seed):
                value = seed
                while True:
                    value = (value * 1103515245 + 12345) % 2147483648
                    yield value % 100 + 1


            def index_of_total(seed, target):
                total = 0
                for index, amount in enumerate(ledger(seed), 1):
                    total += amount
                    if total >= target:
                        return [index, total]
            """,
            [("small target", [1, 100]), ("other seed", [7, 250])],
            [("target of one", [1, 1]), ("bigger target", [99, 5000])],
            edges=[("large seed", [2147483000, 10])],
            perf=[("two million entries", [3, 100000000])],
            after="gen-deep-flatten", time="O(k)", space="O(1)",
            pattern="SIMULATION", secondary=["COMPLEXITY"],
            starter="""
            def ledger(seed):
                # endless: step the value, yield the entry, repeat
                pass


            def index_of_total(seed, target):
                # walk the ledger with enumerate(..., 1), accumulate, and return
                # [index, total] the moment the total reaches `target`
                pass
            """,
            nudge="Step the value BEFORE yielding: the seed itself is not an entry.",
            visual="One integer of state in the generator, one running total in "
                   "the consumer. Nothing else is alive at any moment.",
            pseudocode="ledger: value = seed; loop forever: step value; yield value % 100 + 1\n"
                       "scan: total = 0; for index, amount in enumerate(ledger(seed), 1):\n"
                       "  total += amount; if total >= target: return [index, total]",
            failures=["Yielding before stepping, which is off by one entry",
                      "Collecting entries into a list first — on the performance "
                      "test that is hundreds of thousands of integers held for no "
                      "reason, and on the real ledger it never terminates"],
            tags=["generators", "infinite", "memory"],
        ),

        mcq_problem(
            id="gen-mcq-list-cost", title="What The List Costs",
            realm="fields_of_syntax", pattern="COMPLEXITY", difficulty="EASY",
            statement="""
            Both functions below return the same number. One of them holds n
            integers in memory while it does it. Which statement is true?
            """,
            code="""
            def total_a(n):
                return sum([i * i for i in range(n)])


            def total_b(n):
                return sum(i * i for i in range(n))
            """,
            choices=[
                "Same result. `total_a` builds a list of n integers first and holds "
                "all of them; `total_b` holds one integer at a time.",
                "Same result, same memory. The brackets are a style choice.",
                "`total_b` is broken: `sum` requires a sequence, not a generator.",
                "`total_a` uses less memory, because the list is computed once "
                "instead of repeatedly.",
            ],
            answer=0,
            explanation="""
            The brackets are not cosmetic. `[i * i for i in range(n)]` allocates a
            list of n integers, hands the whole thing to `sum`, and lets it be
            collected afterwards — peak memory grows with n. The parenthesised
            form builds a generator: `sum` pulls one square, adds it, drops it,
            and asks for the next. Peak memory is constant.

            At n = 10 the difference is nothing. At n = 100 million the first one
            is the reason the process died and the second one is a loop that
            finishes. This is the whole case for generators, and it is a memory
            argument, not a speed argument — the two run at roughly the same
            speed.
            """,
            family="python_generators", seconds=70,
        ),

        mcq_problem(
            id="gen-mcq-exhausted", title="Once Only",
            realm="fields_of_syntax", pattern="SIMULATION", difficulty="EASY",
            statement="""
            A generator is an iterator, and an iterator is consumed rather than
            copied. What does `second` hold at the end?
            """,
            code="""
            values = (n * n for n in range(4))
            first = list(values)
            second = list(values)
            """,
            choices=[
                "[0, 1, 4, 9]",
                "[]",
                "[0, 1, 4, 9] again — the generator restarts on each `list()` call",
                "A TypeError: a generator cannot be passed to `list` twice",
            ],
            answer=1,
            explanation="""
            `first` drains the generator completely. The generator is now spent:
            its frame has run to the end and every further `next()` raises
            StopIteration immediately, so `list()` collects nothing and `second`
            is the empty list.

            This is the bug behind a whole genre of confusing code — a function
            takes an iterable, loops over it twice, and the second loop silently
            does nothing. It never happens with a list, which is why it is so
            surprising the first time it happens with a generator. If you need two
            passes, either keep a list or build a fresh generator for each pass.
            """,
            family="python_generators", seconds=70,
        ),

        # ===================================================================
        # CLOSURES — functions that outlive the scope that made them
        # ===================================================================

        drill(
            "gen-closure-blank", "A Function That Remembers", "GUIDED",
            """
            A function defined inside another function can still see the outer
            function's variables after the outer call has returned. The inner
            function plus the variables it captured is a CLOSURE.

            `make_adder(3)` returns a function that adds 3 to whatever it is
            given. `add_each` is written for you.
            """,
            "add_each", "amount, values", _add_each,
            """
            def make_adder(amount):
                def add(value):
                    return value + amount
                return add


            def add_each(amount, values):
                add = make_adder(amount)
                return [add(value) for value in values]
            """,
            [("add three", [3, [1, 2]]), ("add zero", [0, [5]])],
            [("negative", [-2, [10, 0]]), ("single", [7, [1]])],
            edges=[("no values", [4, []])],
            family="python_closures", after="gen-yield-first", time="O(n)",
            pattern="SIMULATION",
            starter="""
            def make_adder(amount):
                def add(value):
                    # `amount` belongs to make_adder, and `add` can still see it
                    return value + __BLANK__
                return add


            def add_each(amount, values):
                add = make_adder(amount)
                return [add(value) for value in values]
            """,
            nudge="`add` never receives `amount` as an argument. It does not have "
                  "to: it was built inside the call that had one.",
            pseudocode="make_adder(amount) -> a function that adds amount",
            fragment=_same_move("def make_greeter(word):\n"
                                "    def greet(name):\n"
                                "        return word + ' ' + name\n"
                                "    return greet"),
            failures=["Returning `add()` instead of `add` — the parentheses call "
                      "it immediately instead of handing it over"],
            tags=["closures"],
        ),

        drill(
            "gen-closure-nonlocal-blank", "Rebinding What You Captured", "GUIDED",
            """
            Reading an outer variable from an inner function is free. ASSIGNING
            to one is not: a plain assignment creates a new local, and the outer
            variable never changes. `nonlocal` says "this name belongs to the
            enclosing function; rebind that one".

            `make_counter()` returns a function that hands back 1, then 2, then 3
            on each call.
            """,
            "count_to", "times", _count_to,
            """
            def make_counter():
                count = 0

                def bump():
                    nonlocal count
                    count += 1
                    return count

                return bump


            def count_to(times):
                bump = make_counter()
                return [bump() for _ in range(times)]
            """,
            [("three", [3]), ("one", [1])],
            [("five", [5]), ("two", [2])],
            edges=[("zero", [0])],
            family="python_closures", after="gen-closure-blank", time="O(n)",
            pattern="SIMULATION",
            starter="""
            def make_counter():
                count = 0

                def bump():
                    __BLANK__       # declare that `count` is the outer one, not a new local
                    count += 1
                    return count

                return bump


            def count_to(times):
                bump = make_counter()
                return [bump() for _ in range(times)]
            """,
            nudge="Without it, `count += 1` reads a local that has never been "
                  "assigned, and Python raises UnboundLocalError.",
            pseudocode="nonlocal count",
            fragment=_same_move("def tick():\n    nonlocal seconds\n    seconds += 1"),
            failures=["Using `global count`, which looks for a module-level name "
                      "that does not exist"],
            tags=["closures", "nonlocal"],
        ),

        drill(
            "gen-closure-factory", "The Factory", "TUTORIAL",
            """
            Write `make_multiplier(factor)`: it returns a function that multiplies
            its argument by `factor`. Each call to `make_multiplier` produces a
            fresh function with its own captured `factor`.

            `scale_all` is written for you and uses one of them.
            """,
            "scale_all", "factor, values", _scale_all,
            """
            def make_multiplier(factor):
                def multiply(value):
                    return value * factor
                return multiply


            def scale_all(factor, values):
                multiply = make_multiplier(factor)
                return [multiply(value) for value in values]
            """,
            [("times three", [3, [1, 2]]), ("times one", [1, [9]])],
            [("times zero", [0, [4, 5]]), ("negative", [-2, [3]])],
            edges=[("no values", [5, []])],
            family="python_closures", after="gen-closure-nonlocal-blank",
            pattern="SIMULATION", time="O(n)",
            starter="""
            def make_multiplier(factor):
                # 1. define an inner function taking one value
                # 2. it returns value * factor
                # 3. return the inner function itself, uncalled
                pass


            def scale_all(factor, values):
                multiply = make_multiplier(factor)
                return [multiply(value) for value in values]
            """,
            nudge="Three lines. The last one has no parentheses on it.",
            pseudocode="def make_multiplier(factor):\n  def multiply(value):\n"
                       "    return value * factor\n  return multiply",
            tags=["closures"],
        ),

        drill(
            "gen-closure-accumulator", "The Tally That Persists", "TUTORIAL",
            """
            A closure's captured variables live between calls. That makes a
            closure a tiny object with exactly one method — often all the state
            you need.

            Write `make_accumulator()`: it returns a function that adds its
            argument to a running total and returns the new total.
            """,
            "running_totals", "values", _running_totals,
            """
            def make_accumulator():
                total = 0

                def add(value):
                    nonlocal total
                    total += value
                    return total

                return add


            def running_totals(values):
                add = make_accumulator()
                return [add(value) for value in values]
            """,
            [("three", [[1, 2, 3]]), ("negatives", [[5, -2]])],
            [("zeros", [[0, 0]]), ("single", [[9]])],
            edges=[("empty", [[]])],
            family="python_closures", after="gen-closure-factory",
            pattern="SIMULATION", time="O(n)",
            starter="""
            def make_accumulator():
                # 1. a `total`, starting at 0
                # 2. an inner `add(value)` that declares `nonlocal total`,
                #    adds, and returns the new total
                # 3. return the inner function
                pass


            def running_totals(values):
                add = make_accumulator()
                return [add(value) for value in values]
            """,
            nudge="Same shape as the counter, except the amount arrives as an "
                  "argument instead of being always 1.",
            pseudocode="total = 0\ndef add(value):\n  nonlocal total\n"
                       "  total += value\n  return total\nreturn add",
            failures=["Forgetting `nonlocal`, which raises UnboundLocalError on "
                      "the first call"],
            tags=["closures", "nonlocal"],
        ),

        drill(
            "gen-closure-late-binding", "The Loop That Lied", "EASY",
            """
            The classic trap, and a genuine interview question.

            A closure captures the VARIABLE, not the value the variable held when
            the closure was made. Build three functions inside a loop over
            `factors` and all three end up looking at the same `factor` — whose
            value, by the time anyone calls them, is the last one the loop left
            behind.

            Return [fn(value) for each function you built], so that the function
            built for factor f returns f * value. Two cures: bind the value as a
            default argument (`lambda v, factor=factor: ...`), or build each
            function inside its own call to a factory.
            """,
            "multipliers", "factors, value", _multipliers,
            """
            def multipliers(factors, value):
                built = []
                for factor in factors:
                    # The default argument is evaluated NOW, at definition time,
                    # so each lambda gets its own copy of the current factor.
                    built.append(lambda v, factor=factor: v * factor)
                return [fn(value) for fn in built]
            """,
            [("three factors", [[1, 2, 3], 10]), ("one factor", [[5], 3])],
            [("negatives", [[-1, 2], 4]), ("with zero", [[0, 1], 7])],
            edges=[("no factors", [[], 5]), ("repeated factor", [[2, 2], 3])],
            family="python_closures", after="gen-closure-accumulator",
            pattern="SIMULATION", time="O(n)",
            starter="""
            def multipliers(factors, value):
                built = []
                for factor in factors:
                    # build a function that multiplies by THIS factor,
                    # not by whatever `factor` holds when the loop is over
                    pass
                return [fn(value) for fn in built]
            """,
            nudge="If every answer comes back the same, you captured the variable. "
                  "You want to capture the value.",
            pseudocode="for factor in factors:\n"
                       "  built.append(lambda v, factor=factor: v * factor)",
            failures=["`lambda v: v * factor` — every function returns the last "
                      "factor times the value"],
            tags=["closures", "late-binding", "trap"],
        ),

        debug_problem(
            id="gen-debug-late-binding", title="Three Knights, One Name",
            difficulty="EASY",
            statement="""
            Each handler is supposed to multiply by its own factor. Every one of
            them multiplies by the last factor in the list instead.

            The loop is right, the list is right, and the call at the end is
            right. What is wrong is WHEN the lambda looks at `factor`: it looks
            when it is called, not when it was written, and by then the loop has
            finished.

            Fix it. A factory function gives each closure its own scope; so does
            a default argument.
            """,
            fn_name="multipliers", params="factors, value",
            broken="""
            def multipliers(factors, value):
                built = []
                for factor in factors:
                    built.append(lambda v: v * factor)
                return [fn(value) for fn in built]
            """,
            reference=_multipliers,
            canonical="""
            def multipliers(factors, value):
                def make(factor):
                    # `factor` is a parameter of `make`, so every call to `make`
                    # creates a separate scope holding a separate value.
                    return lambda v: v * factor

                built = [make(factor) for factor in factors]
                return [fn(value) for fn in built]
            """,
            visible=[("three factors", [[1, 2, 3], 10]), ("two factors", [[4, 5], 2])],
            hidden=[("negatives", [[-1, 2], 4]), ("with zero", [[0, 1], 7]),
                    ("single", [[5], 3]), ("empty", [[], 5])],
            bug_type="late-binding-closure", armor_piece="gauntlets",
            nudge="Print the list of results for [1, 2, 3]. All three are the same "
                  "number, and that number tells you which factor won.",
            failures=["Assuming the loop variable is copied into each lambda"],
            family="python_closures", time_complexity="O(n)", space_complexity="O(n)",
        ),

        drill(
            "gen-closure-ledger", "The Running Ledger", "MEDIUM",
            """
            Two closures over the same captured state: this is an object, written
            without the word `class`.

            `make_account(balance)` returns a pair of functions. `apply(amount)`
            adds `amount` to the balance and records "ok" in the history — unless
            the result would go below zero, in which case it changes nothing and
            records "refused". `report()` returns [balance, history].

            `run_account` is written for you.
            """,
            "run_account", "start, amounts", _run_account,
            """
            def make_account(balance):
                history = []

                def apply(amount):
                    nonlocal balance
                    if balance + amount < 0:
                        history.append("refused")
                        return balance
                    balance += amount
                    history.append("ok")
                    return balance

                def report():
                    # history is MUTATED, never rebound, so it needs no nonlocal.
                    # balance is rebound, so it does.
                    return [balance, list(history)]

                return apply, report


            def run_account(start, amounts):
                apply, report = make_account(start)
                for amount in amounts:
                    apply(amount)
                return report()
            """,
            [("deposit and spend", [100, [50, -30]]), ("refused", [10, [-50]])],
            [("no movement", [5, []]), ("exactly to zero", [10, [-10]])],
            edges=[("zero then refuse", [0, [0, -1]]),
                   ("refuse then succeed", [5, [-10, 5]])],
            family="python_closures", after="gen-closure-late-binding",
            pattern="SIMULATION", time="O(n)", space="O(n)",
            starter="""
            def make_account(balance):
                history = []

                def apply(amount):
                    # rebinding `balance` needs one keyword. Appending to
                    # `history` needs none — think about why.
                    pass

                def report():
                    pass

                return apply, report


            def run_account(start, amounts):
                apply, report = make_account(start)
                for amount in amounts:
                    apply(amount)
                return report()
            """,
            nudge="Both inner functions close over the SAME two names. That is how "
                  "they stay in agreement without either one owning the state.",
            visual="One captured scope, two doors into it.",
            pseudocode="apply(amount):\n  nonlocal balance\n"
                       "  if balance + amount < 0: history.append('refused'); return balance\n"
                       "  balance += amount; history.append('ok'); return balance\n"
                       "report(): return [balance, list(history)]",
            failures=["Declaring `nonlocal history` — harmless but unnecessary, "
                      "and it suggests you think appending rebinds the name",
                      "Refusing on `balance + amount <= 0`, which rejects "
                      "spending down to exactly zero"],
            tags=["closures", "nonlocal", "state"],
        ),

        # ===================================================================
        # DECORATORS — a closure over a function, plus one line of syntax
        # ===================================================================

        drill(
            "gen-deco-blank", "Wrapping A Function", "GUIDED",
            """
            A decorator is a function that takes a function and returns a
            replacement for it. `@double_result` above a `def` means exactly

                length = double_result(length)

            and nothing more.

            `double_result` here returns a wrapper that calls the original and
            doubles whatever came back.
            """,
            "doubled_lengths", "words", _doubled_lengths,
            """
            def double_result(fn):
                def wrapper(value):
                    return fn(value) * 2
                return wrapper


            def doubled_lengths(words):
                @double_result
                def length(word):
                    return len(word)

                return [length(word) for word in words]
            """,
            [("two words", [["ab", "cde"]]), ("one word", [["x"]])],
            [("empty string", [[""]]), ("three words", [["a", "bb", "ccc"]])],
            edges=[("no words", [[]])],
            family="python_decorators", after="gen-closure-factory", time="O(n)",
            pattern="SIMULATION",
            starter="""
            def double_result(fn):
                def wrapper(value):
                    return fn(value) * 2
                __BLANK__      # a decorator must hand back the replacement function


            def doubled_lengths(words):
                @double_result
                def length(word):
                    return len(word)

                return [length(word) for word in words]
            """,
            nudge="Whatever the decorator returns is what the decorated name ends "
                  "up bound to. Return None and `length` becomes None.",
            pseudocode="def double_result(fn):\n  def wrapper(value): return fn(value) * 2\n"
                       "  return wrapper",
            fragment=_same_move("def shout(fn):\n"
                                "    def wrapper(text):\n"
                                "        return fn(text).upper()\n"
                                "    return wrapper"),
            failures=["Forgetting the return, which leaves the decorated name "
                      "bound to None and fails with 'NoneType is not callable'"],
            tags=["decorators"],
        ),

        drill(
            "gen-deco-passthrough", "Passing The Arguments Through", "GUIDED",
            """
            A wrapper that only accepts one argument can only decorate functions
            that take one argument. `*args, **kwargs` makes a wrapper work for any
            signature: collect whatever arrived, hand it straight on.

            Fill in the call to the wrapped function.
            """,
            "call_with_two", "a, b", _call_with_two,
            """
            def announce(fn):
                def wrapper(*args, **kwargs):
                    return ["called", fn(*args, **kwargs)]
                return wrapper


            def call_with_two(a, b):
                @announce
                def add(x, y):
                    return x + y

                return add(a, b)
            """,
            [("two numbers", [2, 3]), ("with zero", [0, 5])],
            [("negatives", [-1, -2]), ("large", [1000, 1])],
            edges=[("both zero", [0, 0])],
            family="python_decorators", after="gen-deco-blank", time="O(1)",
            pattern="SIMULATION",
            starter="""
            def announce(fn):
                def wrapper(*args, **kwargs):
                    # call the wrapped function with whatever arguments arrived
                    return ["called", __BLANK__]
                return wrapper


            def call_with_two(a, b):
                @announce
                def add(x, y):
                    return x + y

                return add(a, b)
            """,
            nudge="The star in the definition COLLECTS. The star at the call site "
                  "SPREADS. You want the spread.",
            pseudocode="return ['called', fn(*args, **kwargs)]",
            fragment=_same_move("def wrapper(*args, **kwargs):\n"
                                "    return fn(*args, **kwargs)"),
            failures=["`fn(args, kwargs)`, which passes a tuple and a dict as two "
                      "positional arguments"],
            tags=["decorators"],
        ),

        drill(
            "gen-deco-count", "Counting The Calls", "TUTORIAL",
            """
            Write `count_calls`: a decorator that leaves the wrapped function's
            behaviour alone but keeps a count of how many times it was called, as
            an attribute `calls` on the wrapper.

            Functions are objects; you can hang an attribute on one. The count has
            to live somewhere that survives between calls, and the wrapper itself
            is the honest place for it.
            """,
            "call_count", "values", _call_count,
            """
            def count_calls(fn):
                def wrapper(*args, **kwargs):
                    wrapper.calls += 1
                    return fn(*args, **kwargs)

                wrapper.calls = 0
                return wrapper


            def call_count(values):
                @count_calls
                def double(value):
                    return value * 2

                doubled = [double(value) for value in values]
                return [doubled, double.calls]
            """,
            [("three values", [[1, 2, 3]]), ("one value", [[5]])],
            [("negatives", [[-1, -2]]), ("zeros", [[0, 0, 0]])],
            edges=[("none", [[]])],
            family="python_decorators", after="gen-deco-passthrough", time="O(n)",
            pattern="SIMULATION",
            starter="""
            def count_calls(fn):
                def wrapper(*args, **kwargs):
                    # 1. add one to the count
                    # 2. return the wrapped function's result, unchanged
                    pass

                # 3. start the count at zero, on the wrapper, before returning it
                # 4. return the wrapper
                pass


            def call_count(values):
                @count_calls
                def double(value):
                    return value * 2

                doubled = [double(value) for value in values]
                return [doubled, double.calls]
            """,
            nudge="`double.calls` in the harness is `wrapper.calls`, because "
                  "`double` IS the wrapper after decoration.",
            pseudocode="def wrapper(*args, **kwargs):\n  wrapper.calls += 1\n"
                       "  return fn(*args, **kwargs)\nwrapper.calls = 0\nreturn wrapper",
            failures=["Not returning `fn(...)`, so every call answers None",
                      "Counting inside `count_calls` instead of inside `wrapper` — "
                      "that runs once, at decoration time"],
            tags=["decorators"],
        ),

        drill(
            "gen-deco-wraps-blank", "Keeping The Name", "GUIDED",
            """
            A wrapper is a different function from the one it replaced, and it
            says so: after decoration `scale.__name__` is "wrapper" and the
            docstring is gone. That breaks help(), debuggers, logs and anything
            that introspects.

            `functools.wraps` copies the original's name, docstring and metadata
            onto the wrapper. It is itself a decorator, applied to the wrapper.
            """,
            "identity_of", "value", _identity_of,
            """
            from functools import wraps


            def logged(fn):
                @wraps(fn)
                def wrapper(*args, **kwargs):
                    return fn(*args, **kwargs)
                return wrapper


            def identity_of(value):
                @logged
                def scale(amount):
                    'Multiply by ten.'
                    return amount * 10

                return [scale.__name__, scale.__doc__, scale(value)]
            """,
            [("three", [3]), ("zero", [0])],
            [("negative", [-2]), ("large", [99])],
            edges=[("one", [1])],
            family="python_decorators", after="gen-deco-count", time="O(1)",
            pattern="SIMULATION",
            starter="""
            from functools import wraps


            def logged(fn):
                __BLANK__        # copy fn's name and docstring onto the wrapper
                def wrapper(*args, **kwargs):
                    return fn(*args, **kwargs)
                return wrapper


            def identity_of(value):
                @logged
                def scale(amount):
                    'Multiply by ten.'
                    return amount * 10

                return [scale.__name__, scale.__doc__, scale(value)]
            """,
            nudge="It takes the function being wrapped as its argument, and it is "
                  "written with an at-sign on the line above `def wrapper`.",
            pseudocode="@wraps(fn)\ndef wrapper(*args, **kwargs): ...",
            fragment=_same_move("@wraps(fn)\ndef wrapper(*args, **kwargs):\n"
                                "    return fn(*args, **kwargs)"),
            failures=["`@wraps` with no arguments — it needs to be told which "
                      "function to copy from"],
            tags=["decorators", "wraps"],
        ),

        drill(
            "gen-deco-wraps", "The Name The Wrapper Ate", "TUTORIAL",
            """
            Write `trace`: it leaves behaviour unchanged, records the most recent
            result as `last` on the wrapper, and preserves the wrapped function's
            name and docstring with `functools.wraps`.

            The harness returns the decorated function's `__name__` and `__doc__`
            alongside the results, so a wrapper that ate them fails visibly.
            """,
            "trace_report", "words", _trace_report,
            """
            from functools import wraps


            def trace(fn):
                @wraps(fn)
                def wrapper(*args, **kwargs):
                    result = fn(*args, **kwargs)
                    wrapper.last = result
                    return result

                wrapper.last = None
                return wrapper


            def trace_report(words):
                @trace
                def shout(word):
                    'Upper-case a word.'
                    return word.upper()

                spoken = [shout(word) for word in words]
                return [shout.__name__, shout.__doc__, spoken, shout.last]
            """,
            [("two words", [["ab", "cd"]]), ("one word", [["hi"]])],
            [("already upper", [["AB"]]), ("three words", [["a", "b", "c"]])],
            edges=[("no words", [[]])],
            family="python_decorators", after="gen-deco-wraps-blank", time="O(n)",
            pattern="SIMULATION",
            starter="""
            from functools import wraps


            def trace(fn):
                # 1. @wraps(fn) on the wrapper
                # 2. the wrapper calls fn, stores the result on wrapper.last,
                #    and returns the result
                # 3. wrapper.last starts as None
                pass


            def trace_report(words):
                @trace
                def shout(word):
                    'Upper-case a word.'
                    return word.upper()

                spoken = [shout(word) for word in words]
                return [shout.__name__, shout.__doc__, spoken, shout.last]
            """,
            nudge="With no words at all nothing is ever called, so `last` must "
                  "still be the None it started as.",
            pseudocode="@wraps(fn)\ndef wrapper(*a, **kw):\n  result = fn(*a, **kw)\n"
                       "  wrapper.last = result\n  return result\n"
                       "wrapper.last = None\nreturn wrapper",
            failures=["Setting `wrapper.last = None` inside the wrapper, which "
                      "resets it on every call"],
            tags=["decorators", "wraps"],
        ),

        drill(
            "gen-deco-memoize", "Paying Once", "EASY",
            """
            Memoisation is a decorator in four lines, and it is the reason
            `functools.lru_cache` exists.

            Write `memoize`: keep a dict on the closure, return the cached value
            when the argument has been seen, otherwise call through and store the
            result. The wrapped function takes exactly one hashable argument.

            The harness counts how many times the UNDECORATED body actually runs
            while computing fib(n). Without the cache that count is exponential;
            with it, it is one per distinct argument.
            """,
            "fib_cost", "n", _fib_cost,
            """
            def memoize(fn):
                cache = {}

                def wrapper(value):
                    if value not in cache:
                        cache[value] = fn(value)
                    return cache[value]

                return wrapper


            def fib_cost(n):
                calls = []

                @memoize
                def fib(k):
                    calls.append(k)
                    if k < 2:
                        return k
                    return fib(k - 1) + fib(k - 2)

                return [fib(n), len(calls)]
            """,
            [("ten", [10]), ("zero", [0])],
            [("one", [1]), ("twenty", [20])],
            edges=[("two", [2]), ("thirty", [30])],
            family="python_decorators", after="gen-deco-wraps",
            pattern="HASH_MAP", secondary=["DP"], time="O(n)", space="O(n)",
            starter="""
            def memoize(fn):
                # a dict in the closure, one lookup, one store
                pass


            def fib_cost(n):
                calls = []

                @memoize
                def fib(k):
                    calls.append(k)
                    if k < 2:
                        return k
                    return fib(k - 1) + fib(k - 2)

                return [fib(n), len(calls)]
            """,
            nudge="The recursive calls inside `fib` go through the wrapper too — "
                  "`fib` is the decorated name. That is what makes this work.",
            visual="Each distinct argument crosses into the real function once. "
                   "Every later arrival is answered at the door.",
            pseudocode="cache = {}\ndef wrapper(value):\n"
                       "  if value not in cache: cache[value] = fn(value)\n"
                       "  return cache[value]\nreturn wrapper",
            failures=["Putting the cache inside `wrapper`, which gives every call "
                      "a fresh empty one",
                      "Using `if cache.get(value)`, which treats a cached 0 or "
                      "None as a miss"],
            tags=["decorators", "memoisation"],
        ),

        drill(
            "gen-deco-args-blank", "A Decorator That Takes An Argument", "GUIDED",
            """
            `@repeat(3)` is not a decorator. `repeat(3)` is CALLED first, and
            whatever it returns is used as the decorator. So a parameterised
            decorator is three layers:

                repeat(times)        -> decorate
                decorate(fn)         -> wrapper
                wrapper(*args)       -> the result

            Two of the three returns are already written.
            """,
            "repeated_greeting", "name, times", _repeated_greeting,
            """
            def repeat(times):
                def decorate(fn):
                    def wrapper(*args, **kwargs):
                        return [fn(*args, **kwargs) for _ in range(times)]
                    return wrapper
                return decorate


            def repeated_greeting(name, times):
                @repeat(times)
                def greet(who):
                    return "hail " + who

                return greet(name)
            """,
            [("twice", ["Vail", 2]), ("once", ["Root", 1])],
            [("three times", ["Ash", 3]), ("empty name", ["", 2])],
            edges=[("zero times", ["Vail", 0])],
            family="python_decorators", after="gen-deco-memoize", time="O(k)",
            pattern="SIMULATION",
            starter="""
            def repeat(times):
                def decorate(fn):
                    def wrapper(*args, **kwargs):
                        return [fn(*args, **kwargs) for _ in range(times)]
                    return wrapper
                __BLANK__      # what @repeat(times) evaluates to must be a decorator


            def repeated_greeting(name, times):
                @repeat(times)
                def greet(who):
                    return "hail " + who

                return greet(name)
            """,
            nudge="Count the returns. There must be one for each layer, and the "
                  "outermost layer is the one you are looking at.",
            pseudocode="repeat(times) returns decorate\n"
                       "decorate(fn) returns wrapper\nwrapper returns the answer",
            fragment=_same_move("def tag(label):\n    def decorate(fn):\n"
                                "        ...\n        return wrapper\n"
                                "    return decorate"),
            failures=["Returning `decorate(fn)` from `repeat`, which has no `fn` "
                      "to work with yet"],
            tags=["decorators", "decorator-args"],
        ),

        drill(
            "gen-deco-prefixed", "The Decorator Factory", "TUTORIAL",
            """
            Write `prefixed(label)`: a decorator factory whose wrapper puts
            `label + ": "` in front of whatever the wrapped function returned.
            Keep the wrapped function's name with `functools.wraps` — the harness
            checks it.

            Three layers, three returns. The middle layer is the decorator.
            """,
            "describe", "items, label", _describe,
            """
            from functools import wraps


            def prefixed(label):
                def decorate(fn):
                    @wraps(fn)
                    def wrapper(*args, **kwargs):
                        return label + ": " + fn(*args, **kwargs)
                    return wrapper
                return decorate


            def describe(items, label):
                @prefixed(label)
                def render(value):
                    return str(value)

                return [[render(item) for item in items], render.__name__]
            """,
            [("two items", [[1, 2], "rune"]), ("one item", [["a"], "name"])],
            [("empty label", [[3], ""]), ("three items", [[1, 2, 3], "x"])],
            edges=[("no items", [[], "rune"])],
            family="python_decorators", after="gen-deco-args-blank", time="O(n)",
            pattern="SIMULATION",
            starter="""
            from functools import wraps


            def prefixed(label):
                # 1. an inner `decorate(fn)`
                # 2. inside it, a @wraps(fn)-decorated `wrapper(*args, **kwargs)`
                #    returning label + ": " + fn(*args, **kwargs)
                # 3. decorate returns wrapper; prefixed returns decorate
                pass


            def describe(items, label):
                @prefixed(label)
                def render(value):
                    return str(value)

                return [[render(item) for item in items], render.__name__]
            """,
            nudge="`label` is visible from the innermost wrapper. That is the "
                  "whole reason this is nested rather than flat.",
            pseudocode="def prefixed(label):\n  def decorate(fn):\n"
                       "    @wraps(fn)\n    def wrapper(*a, **kw):\n"
                       "      return label + ': ' + fn(*a, **kw)\n"
                       "    return wrapper\n  return decorate",
            failures=["Only two layers, so `@prefixed(label)` tries to decorate "
                      "the label instead of the function"],
            tags=["decorators", "decorator-args", "wraps"],
        ),

        drill(
            "gen-deco-at-least", "A Floor Under The Answer", "EASY",
            """
            Write `at_least(floor)`: a decorator factory whose wrapper never lets
            the wrapped function's result fall below `floor`.

            This is the shape of most real parameterised decorators — a policy
            chosen once, applied to every call.
            """,
            "clamped_scores", "values, floor", _clamped_scores,
            """
            from functools import wraps


            def at_least(floor):
                def decorate(fn):
                    @wraps(fn)
                    def wrapper(*args, **kwargs):
                        return max(floor, fn(*args, **kwargs))
                    return wrapper
                return decorate


            def clamped_scores(values, floor):
                @at_least(floor)
                def score(value):
                    return value - 10

                return [score(value) for value in values]
            """,
            [("some below", [[5, 20], 0]), ("all above", [[30, 40], 0])],
            [("all below", [[1, 2], 0]), ("negative floor", [[5], -10])],
            edges=[("no values", [[], 0]), ("exactly on the floor", [[10], 0])],
            family="python_decorators", after="gen-deco-prefixed", time="O(n)",
            pattern="SIMULATION",
            starter="""
            from functools import wraps


            def at_least(floor):
                # three layers; the wrapper clamps with max()
                pass


            def clamped_scores(values, floor):
                @at_least(floor)
                def score(value):
                    return value - 10

                return [score(value) for value in values]
            """,
            nudge="`max(floor, result)` is the clamp. The work is getting the "
                  "three layers around it.",
            pseudocode="at_least(floor) -> decorate(fn) -> wrapper(*a, **kw):\n"
                       "  return max(floor, fn(*a, **kw))",
            tags=["decorators", "decorator-args"],
        ),

        drill(
            "gen-deco-stacking", "Stacking Them", "MEDIUM",
            """
            Decorators stack bottom-up. In

                @outer
                @inner
                def f(): ...

            `inner` is applied first, so `f` becomes `outer(inner(f))` — and at
            call time the OUTER wrapper runs first, around everything below it.

            Write two decorators. `reversed_text` reverses the wrapped function's
            result; `tagged` appends ">" to it. The harness stacks them both ways
            round, and the two orders must give different answers.
            """,
            "stack_order", "word", _stack_order,
            """
            def reversed_text(fn):
                def wrapper(value):
                    return fn(value)[::-1]
                return wrapper


            def tagged(fn):
                def wrapper(value):
                    return fn(value) + ">"
                return wrapper


            def stack_order(word):
                @reversed_text
                @tagged
                def a(value):
                    return value

                @tagged
                @reversed_text
                def b(value):
                    return value

                return [a(word), b(word)]
            """,
            [("three letters", ["abc"]), ("one letter", ["z"])],
            [("a word", ["null"]), ("digits", ["123"])],
            edges=[("empty", [""])],
            family="python_decorators", after="gen-deco-at-least", time="O(n)",
            pattern="SIMULATION",
            starter="""
            def reversed_text(fn):
                # wrapper returns the wrapped result, reversed
                pass


            def tagged(fn):
                # wrapper returns the wrapped result with ">" on the end
                pass


            def stack_order(word):
                @reversed_text
                @tagged
                def a(value):
                    return value

                @tagged
                @reversed_text
                def b(value):
                    return value

                return [a(word), b(word)]
            """,
            nudge="Work out `a('abc')` on paper before you run it. `tagged` is "
                  "applied first, so the reverse happens to the tagged string.",
            visual="Read the stack from the `def` upwards for the order of "
                   "APPLICATION, and downwards from the top for the order of "
                   "EXECUTION.",
            pseudocode="reversed_text: return fn(value)[::-1]\n"
                       "tagged: return fn(value) + '>'",
            failures=["Assuming the top decorator is applied first, which reverses "
                      "both answers"],
            tags=["decorators", "stacking"],
        ),

        drill(
            "gen-deco-retry", "Retry, Then Give Up", "MEDIUM",
            """
            Write `retry(attempts)`: a decorator factory whose wrapper calls the
            function, and on ValueError tries again, up to `attempts` calls in
            total. If the last attempt also raises, the exception escapes — a
            retry decorator that swallows the final failure is worse than no
            retry decorator at all.

            `attempts` is always at least 1. Catch ValueError only; every other
            exception is a bug, not a flake, and must propagate on the first
            occurrence.

            The harness builds a function that fails its first `fail_times` calls
            and then succeeds, and reports [result, how many calls happened].
            """,
            "flaky_run", "fail_times, attempts", _flaky_run,
            """
            from functools import wraps


            def retry(attempts):
                def decorate(fn):
                    @wraps(fn)
                    def wrapper(*args, **kwargs):
                        last = None
                        for _ in range(attempts):
                            try:
                                return fn(*args, **kwargs)
                            except ValueError as exc:
                                last = exc
                        raise last
                    return wrapper
                return decorate


            def flaky_run(fail_times, attempts):
                calls = []

                @retry(attempts)
                def unstable():
                    calls.append(len(calls))
                    if len(calls) <= fail_times:
                        raise ValueError("not yet")
                    return "ok"

                try:
                    result = unstable()
                except ValueError:
                    result = "gave up"
                return [result, len(calls)]
            """,
            [("one flake, three attempts", [1, 3]), ("never succeeds", [5, 2])],
            [("succeeds first time", [0, 3]), ("last attempt wins", [2, 3])],
            edges=[("single attempt, fails", [1, 1]),
                   ("single attempt, succeeds", [0, 1])],
            family="python_decorators", after="gen-deco-stacking", time="O(k)",
            pattern="SIMULATION",
            starter="""
            from functools import wraps


            def retry(attempts):
                # three layers. The wrapper loops `attempts` times, returning on
                # the first success, remembering the last ValueError, and
                # re-raising it once the attempts are used up.
                pass


            def flaky_run(fail_times, attempts):
                calls = []

                @retry(attempts)
                def unstable():
                    calls.append(len(calls))
                    if len(calls) <= fail_times:
                        raise ValueError("not yet")
                    return "ok"

                try:
                    result = unstable()
                except ValueError:
                    result = "gave up"
                return [result, len(calls)]
            """,
            nudge="`return fn(...)` inside the `try` is what ends the loop on "
                  "success. No flag variable is needed.",
            visual="attempts calls at most, one return on the first success, one "
                   "raise if none of them succeed.",
            pseudocode="for _ in range(attempts):\n  try: return fn(*a, **kw)\n"
                       "  except ValueError as exc: last = exc\nraise last",
            failures=["Returning None after the loop instead of re-raising, which "
                      "turns a hard failure into a silent wrong answer",
                      "Catching bare `Exception`, which retries genuine bugs "
                      "three times before reporting them"],
            tags=["decorators", "decorator-args", "retry"],
        ),

        drill(
            "gen-deco-timing", "The Timing Decorator", "MEDIUM",
            """
            The decorator everyone writes first. In real code the clock is
            `time.perf_counter`; here it is handed in as `clock` so the test can
            be exact, which is also how you would make a timing decorator
            testable in real code.

            Write `timed(clock)`: a decorator factory. Its wrapper reads the
            clock before and after the call, appends the difference to
            `wrapper.elapsed`, and returns the original result untouched. The
            list starts empty.

            The harness's clock yields the ticks you are given, one per read —
            two reads per call.
            """,
            "timing_report", "ticks, values", _timing_report,
            """
            from functools import wraps


            def timed(clock):
                def decorate(fn):
                    @wraps(fn)
                    def wrapper(*args, **kwargs):
                        start = clock()
                        result = fn(*args, **kwargs)
                        wrapper.elapsed.append(clock() - start)
                        return result

                    wrapper.elapsed = []
                    return wrapper

                return decorate


            def timing_report(ticks, values):
                readings = iter(ticks)

                def clock():
                    return next(readings)

                @timed(clock)
                def work(value):
                    return value * 2

                done = [work(value) for value in values]
                return [done, work.elapsed]
            """,
            [("two calls", [[0, 5, 5, 12], [1, 2]]), ("one call", [[10, 11], [3]])],
            [("zero-length call", [[4, 4], [0]]),
             ("three calls", [[0, 1, 1, 3, 3, 6], [1, 2, 3]])],
            edges=[("no calls", [[], []])],
            family="python_decorators", after="gen-deco-retry", time="O(n)",
            pattern="SIMULATION",
            starter="""
            from functools import wraps


            def timed(clock):
                # three layers again. The wrapper: read the clock, call, read the
                # clock, append the difference to wrapper.elapsed, return the
                # result. Set wrapper.elapsed = [] once, before returning wrapper.
                pass


            def timing_report(ticks, values):
                readings = iter(ticks)

                def clock():
                    return next(readings)

                @timed(clock)
                def work(value):
                    return value * 2

                done = [work(value) for value in values]
                return [done, work.elapsed]
            """,
            nudge="Read the clock BEFORE the call and store it. Reading it twice "
                  "afterwards measures nothing and eats the wrong ticks.",
            pseudocode="start = clock()\nresult = fn(*a, **kw)\n"
                       "wrapper.elapsed.append(clock() - start)\nreturn result",
            failures=["Returning the elapsed time instead of the result, which "
                      "silently replaces every value the function produced",
                      "Creating `elapsed` inside the wrapper, so only the last "
                      "timing survives"],
            tags=["decorators", "decorator-args", "timing"],
        ),

        debug_problem(
            id="gen-debug-wrapper-return", title="The Wrapper That Ate The Answer",
            difficulty="EASY",
            statement="""
            `remember` is supposed to record every argument it sees and otherwise
            leave `square` alone. The recording works. The squares come back as
            None.

            The bug is one missing word, and it is the most common decorator bug
            there is: a wrapper that calls the function and then forgets to hand
            the result back. The caller gets whatever the wrapper returned, which
            is None.
            """,
            fn_name="remembered", params="values",
            broken="""
            def remember(fn):
                def wrapper(value):
                    wrapper.seen.append(value)
                    fn(value)

                wrapper.seen = []
                return wrapper


            def remembered(values):
                @remember
                def square(value):
                    return value * value

                out = [square(value) for value in values]
                return [out, square.seen]
            """,
            reference=_remembered,
            canonical="""
            def remember(fn):
                def wrapper(value):
                    wrapper.seen.append(value)
                    return fn(value)

                wrapper.seen = []
                return wrapper


            def remembered(values):
                @remember
                def square(value):
                    return value * value

                out = [square(value) for value in values]
                return [out, square.seen]
            """,
            visible=[("three", [[1, 2, 3]]), ("one", [[4]])],
            hidden=[("negatives", [[-2, 3]]), ("zeros", [[0]]),
                    ("empty", [[]]), ("repeats", [[2, 2]])],
            bug_type="wrapper-drops-return", armor_piece="greaves",
            nudge="Look at the last line of the wrapper. It calls the function "
                  "and throws the answer away.",
            failures=["Writing a wrapper as a statement rather than an expression, "
                      "so the return value never leaves it"],
            family="python_decorators", time_complexity="O(n)",
            space_complexity="O(n)",
        ),

        # ===================================================================
        # CONTEXT MANAGERS — the `with` block, and what it is really for
        # ===================================================================

        drill(
            "gen-ctx-enter-blank", "What `with` Hands You", "GUIDED",
            """
            `with thing as name:` calls `thing.__enter__()` and binds whatever
            that RETURNS to `name`. It does not bind the object itself — they are
            only the same when `__enter__` returns `self`, which is the usual
            choice and the reason most people never notice the difference.

            Make `__enter__` hand back the Tally itself.
            """,
            "tally_run", "values", _tally_run,
            """
            class Tally:
                def __init__(self):
                    self.events = []

                def __enter__(self):
                    self.events.append("open")
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    self.events.append("close")
                    return False


            def tally_run(values):
                tally = Tally()
                with tally as handle:
                    for value in values:
                        handle.events.append(value)
                return tally.events
            """,
            [("two values", [["a", "b"]]), ("one value", [["x"]])],
            [("numbers", [[1, 2, 3]]), ("repeats", [["a", "a"]])],
            edges=[("nothing in the block", [[]])],
            family="python_context", after="gen-iter-class", time="O(n)",
            pattern="SIMULATION",
            starter="""
            class Tally:
                def __init__(self):
                    self.events = []

                def __enter__(self):
                    self.events.append("open")
                    __BLANK__       # this is what `as handle` will name

                def __exit__(self, exc_type, exc, traceback):
                    self.events.append("close")
                    return False


            def tally_run(values):
                tally = Tally()
                with tally as handle:
                    for value in values:
                        handle.events.append(value)
                return tally.events
            """,
            nudge="Return nothing and `handle` is None, so the first line of the "
                  "block fails with 'NoneType has no attribute events'.",
            pseudocode="__enter__: record the open, return self",
            fragment=_same_move("def __enter__(self):\n"
                                "    self.connection = connect()\n"
                                "    return self.connection"),
            failures=["Assuming `with x as y` always means `y is x`"],
            tags=["context-managers"],
        ),

        drill(
            "gen-ctx-exit-blank", "The Half That Always Runs", "GUIDED",
            """
            Here is the real reason the file example is everybody's first context
            manager, and it is not brevity. `__exit__` runs when the block ends —
            including when the block ends because something raised. The cleanup
            is not "at the end of the code you wrote", it is "on every way out".

            Record the close in `__exit__`. The harness runs the block twice: once
            cleanly, once with an exception thrown inside it. "close" must appear
            in both logs, and before "caught".
            """,
            "door_log", "steps, fail", _door_log,
            """
            class Door:
                def __init__(self):
                    self.log = []

                def __enter__(self):
                    self.log.append("open")
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    self.log.append("close")
                    return False


            def door_log(steps, fail):
                door = Door()
                try:
                    with door:
                        for step in steps:
                            door.log.append(step)
                        if fail:
                            raise ValueError("the block blew up")
                except ValueError:
                    door.log.append("caught")
                return door.log
            """,
            [("clean run", [["a", "b"], False]), ("failing run", [["a"], True])],
            [("no steps, clean", [[], False]), ("no steps, failing", [[], True])],
            edges=[("many steps, failing", [["x", "y", "z"], True])],
            family="python_context", after="gen-ctx-enter-blank", time="O(n)",
            pattern="SIMULATION",
            starter="""
            class Door:
                def __init__(self):
                    self.log = []

                def __enter__(self):
                    self.log.append("open")
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    __BLANK__       # the cleanup: record that the door closed
                    return False

            def door_log(steps, fail):
                door = Door()
                try:
                    with door:
                        for step in steps:
                            door.log.append(step)
                        if fail:
                            raise ValueError("the block blew up")
                except ValueError:
                    door.log.append("caught")
                return door.log
            """,
            nudge="One line, the mirror of the one in `__enter__`.",
            visual="The exception is still travelling while __exit__ runs. "
                   "`return False` means: I have cleaned up, carry on falling.",
            pseudocode="__exit__: record the close, return False",
            fragment=_same_move("def __exit__(self, exc_type, exc, tb):\n"
                                "    self.handle.close()\n"
                                "    return False"),
            failures=["`return True` from __exit__, which silently swallows every "
                      "exception the block raises"],
            tags=["context-managers", "cleanup"],
        ),

        drill(
            "gen-ctx-class", "Open, Use, Always Close", "TUTORIAL",
            """
            Write the whole protocol. `Session(name)` records "open:NAME" when the
            block is entered and "close:NAME" when it leaves, and `__enter__`
            hands back the log list itself so the block can append to it directly.

            `__exit__` takes three arguments beyond `self` — the exception type,
            the exception, and the traceback — all None when the block ended
            cleanly. Returning False (or None) means "I did not handle it".
            """,
            "session_log", "name, actions", _session_log,
            """
            class Session:
                def __init__(self, name):
                    self.name = name
                    self.log = []

                def __enter__(self):
                    self.log.append("open:" + self.name)
                    return self.log

                def __exit__(self, exc_type, exc, traceback):
                    self.log.append("close:" + self.name)
                    return False


            def session_log(name, actions):
                session = Session(name)
                with session as log:
                    for action in actions:
                        log.append(action)
                return session.log
            """,
            [("two actions", ["db", ["read", "write"]]),
             ("one action", ["file", ["read"]])],
            [("no actions", ["db", []]), ("empty name", ["", ["x"]])],
            edges=[("many actions", ["s", ["a", "b", "c", "d"]])],
            family="python_context", after="gen-ctx-exit-blank", time="O(n)",
            pattern="SIMULATION",
            starter="""
            class Session:
                def __init__(self, name):
                    self.name = name
                    self.log = []

                def __enter__(self):
                    # 1. record "open:" + the name
                    # 2. return the log list, so `as log` names it
                    pass

                def __exit__(self, exc_type, exc, traceback):
                    # 3. record "close:" + the name
                    # 4. return False — this manager handles nothing
                    pass


            def session_log(name, actions):
                session = Session(name)
                with session as log:
                    for action in actions:
                        log.append(action)
                return session.log
            """,
            nudge="__exit__ must accept exactly three extra parameters, even when "
                  "it ignores all three. Python always passes them.",
            pseudocode="__enter__: log 'open:name'; return self.log\n"
                       "__exit__(exc_type, exc, tb): log 'close:name'; return False",
            failures=["Defining `__exit__(self)` — Python calls it with three "
                      "arguments and you get a TypeError on the way out"],
            tags=["context-managers"],
        ),

        drill(
            "gen-ctx-vault", "Cleanup Happens Anyway", "EASY",
            """
            Write `Vault`: entering appends "unlock" to the log, leaving appends
            "lock". The block may raise; the lock must still happen, and the
            exception must still reach the caller.

            This is the whole argument for context managers over a pair of calls.
            Written by hand it is a try/finally every single time, at every call
            site, and the one place somebody forgets is the leak.
            """,
            "vault_log", "steps, fail", _vault_log,
            """
            class Vault:
                def __init__(self, log):
                    self.log = log

                def __enter__(self):
                    self.log.append("unlock")
                    return self.log

                def __exit__(self, exc_type, exc, traceback):
                    self.log.append("lock")
                    return False


            def vault_log(steps, fail):
                log = []
                try:
                    with Vault(log) as sink:
                        for step in steps:
                            sink.append(step)
                        if fail:
                            raise ValueError("interrupted")
                except ValueError:
                    log.append("caught")
                return log
            """,
            [("clean", [["a"], False]), ("interrupted", [["a", "b"], True])],
            [("nothing, clean", [[], False]), ("nothing, interrupted", [[], True])],
            edges=[("many steps", [["x", "y", "z"], True])],
            family="python_context", after="gen-ctx-class", time="O(n)",
            pattern="SIMULATION",
            starter="""
            class Vault:
                def __init__(self, log):
                    self.log = log

                def __enter__(self):
                    pass

                def __exit__(self, exc_type, exc, traceback):
                    pass


            def vault_log(steps, fail):
                log = []
                try:
                    with Vault(log) as sink:
                        for step in steps:
                            sink.append(step)
                        if fail:
                            raise ValueError("interrupted")
                except ValueError:
                    log.append("caught")
                return log
            """,
            nudge="If 'caught' shows up before 'lock', the cleanup is in the wrong "
                  "place — it is happening after the exception escaped, not on the "
                  "way out.",
            pseudocode="__enter__: log 'unlock'; return the log\n"
                       "__exit__: log 'lock'; return False",
            failures=["Returning True from __exit__, so the caller never learns "
                      "the block failed"],
            tags=["context-managers", "cleanup"],
        ),

        drill(
            "gen-ctx-contextmanager-blank", "yield Is The Body", "GUIDED",
            """
            `contextlib.contextmanager` turns a generator into a context manager.
            Everything before the `yield` is `__enter__`; the value yielded is
            what `as` binds; everything after is `__exit__`. The generator must
            yield exactly once.

            The `try/finally` is what makes the second half run even when the
            block raises — it is the same guarantee `__exit__` gives, spelled the
            ordinary way.
            """,
            "scope_log", "name, actions", _scope_log,
            """
            from contextlib import contextmanager


            @contextmanager
            def scope(log, name):
                log.append("enter:" + name)
                try:
                    yield log
                finally:
                    log.append("exit:" + name)


            def scope_log(name, actions):
                log = []
                with scope(log, name) as handle:
                    for action in actions:
                        handle.append(action)
                return log
            """,
            [("two actions", ["job", ["a", "b"]]), ("one action", ["job", ["a"]])],
            [("no actions", ["job", []]), ("empty name", ["", ["a"]])],
            edges=[("many actions", ["j", ["a", "b", "c"]])],
            family="python_context", after="gen-ctx-vault", time="O(n)",
            pattern="SIMULATION",
            starter="""
            from contextlib import contextmanager


            @contextmanager
            def scope(log, name):
                log.append("enter:" + name)
                try:
                    __BLANK__       # hand the log to the block, and pause here
                finally:
                    log.append("exit:" + name)


            def scope_log(name, actions):
                log = []
                with scope(log, name) as handle:
                    for action in actions:
                        handle.append(action)
                return log
            """,
            nudge="The same keyword as in every generator in this family. What it "
                  "yields is what `as handle` receives.",
            pseudocode="setup\ntry:\n  yield the resource\nfinally:\n  teardown",
            fragment=_same_move("@contextmanager\ndef opened(path):\n"
                                "    handle = open(path)\n    try:\n"
                                "        yield handle\n    finally:\n"
                                "        handle.close()"),
            failures=["Yielding twice, which raises RuntimeError: generator "
                      "didn't stop"],
            tags=["context-managers", "contextlib"],
        ),

        drill(
            "gen-ctx-contextmanager", "One Yield, Two Halves", "TUTORIAL",
            """
            Write `staged(log)` with `@contextmanager`: append "start" on the way
            in, yield the log, and append "end" on the way out — even when the
            block raised.

            The harness runs it both ways and appends "caught" outside when an
            exception escapes, so a `finally` that is missing shows up as "end"
            appearing after "caught", or not at all.
            """,
            "staged_run", "steps, fail", _staged_run,
            """
            from contextlib import contextmanager


            @contextmanager
            def staged(log):
                log.append("start")
                try:
                    yield log
                finally:
                    log.append("end")


            def staged_run(steps, fail):
                log = []
                try:
                    with staged(log) as sink:
                        for step in steps:
                            sink.append(step)
                        if fail:
                            raise ValueError("stopped")
                except ValueError:
                    log.append("caught")
                return log
            """,
            [("clean", [["a"], False]), ("failing", [["a"], True])],
            [("nothing, clean", [[], False]), ("nothing, failing", [[], True])],
            edges=[("many steps, failing", [["x", "y"], True])],
            family="python_context", after="gen-ctx-contextmanager-blank",
            time="O(n)", pattern="SIMULATION",
            starter="""
            from contextlib import contextmanager


            @contextmanager
            def staged(log):
                # 1. append "start"
                # 2. try: yield the log
                # 3. finally: append "end"
                pass


            def staged_run(steps, fail):
                log = []
                try:
                    with staged(log) as sink:
                        for step in steps:
                            sink.append(step)
                        if fail:
                            raise ValueError("stopped")
                except ValueError:
                    log.append("caught")
                return log
            """,
            nudge="Without the try/finally, the exception thrown into the "
                  "generator at the yield tears straight out and the teardown "
                  "never runs.",
            pseudocode='log.append("start")\ntry:\n  yield log\nfinally:\n'
                       '  log.append("end")',
            failures=["Putting the teardown after the yield with no try/finally, "
                      "so it only runs when the block succeeded"],
            tags=["context-managers", "contextlib"],
        ),

        drill(
            "gen-ctx-suppress", "Swallowing The Right Error", "MEDIUM",
            """
            `__exit__` gets the exception that is in flight, and its RETURN VALUE
            decides what happens next: truthy means "handled, stop propagating",
            anything falsy means "carry on". That is the only place in Python
            where a return value can cancel an exception, and it is worth
            treating carefully.

            Write `Suppress(*kinds)`: it swallows exceptions that are instances of
            the listed kinds, recording the class name in `self.caught`, and lets
            everything else through untouched.

            The harness asks for one of "value", "key", "type" or anything else.
            It returns [what the manager caught, what escaped to the caller].
            """,
            "suppress_run", "kind", _suppress_run,
            """
            class Suppress:
                def __init__(self, *kinds):
                    self.kinds = kinds
                    self.caught = None

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    # exc_type is None when the block ended cleanly. issubclass
                    # accepts a tuple, which is why `kinds` is kept as one.
                    if exc_type is not None and issubclass(exc_type, self.kinds):
                        self.caught = exc_type.__name__
                        return True
                    return False


            def suppress_run(kind):
                guard = Suppress(ValueError, KeyError)
                escaped = None
                try:
                    with guard:
                        if kind == "value":
                            raise ValueError("v")
                        if kind == "key":
                            raise KeyError("k")
                        if kind == "type":
                            raise TypeError("t")
                except TypeError:
                    escaped = "TypeError"
                return [guard.caught, escaped]
            """,
            [("suppressed", ["value"]), ("not suppressed", ["type"])],
            [("the other suppressed kind", ["key"]), ("clean block", ["clean"])],
            edges=[("unknown label", ["other"])],
            family="python_context", after="gen-ctx-contextmanager",
            time="O(1)", pattern="SIMULATION",
            starter="""
            class Suppress:
                def __init__(self, *kinds):
                    self.kinds = kinds
                    self.caught = None

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    # record and swallow the kinds you were given; let the rest go
                    pass


            def suppress_run(kind):
                guard = Suppress(ValueError, KeyError)
                escaped = None
                try:
                    with guard:
                        if kind == "value":
                            raise ValueError("v")
                        if kind == "key":
                            raise KeyError("k")
                        if kind == "type":
                            raise TypeError("t")
                except TypeError:
                    escaped = "TypeError"
                return [guard.caught, escaped]
            """,
            nudge="Check `exc_type is not None` first. On a clean exit all three "
                  "arguments are None, and `issubclass(None, ...)` is a TypeError.",
            visual="__exit__ returns True: the exception stops here. False: it "
                   "keeps falling. There is no third option.",
            pseudocode="if exc_type is not None and issubclass(exc_type, kinds):\n"
                       "  caught = exc_type.__name__\n  return True\nreturn False",
            failures=["Returning True unconditionally, which hides every error "
                      "the block ever raises",
                      "Comparing with `exc_type in self.kinds`, which misses "
                      "subclasses of the listed types"],
            tags=["context-managers", "exceptions"],
        ),
    ]
