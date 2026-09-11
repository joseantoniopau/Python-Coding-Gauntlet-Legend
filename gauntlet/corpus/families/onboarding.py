"""Onboarding: the first hour, for someone who freezes at a blank screen.

Every other family in this corpus assumes the player can already produce Python.
This one does not. It is the bottom of the ramp, and it is built from a single
rule: the player should never meet an empty function body until they have
already made a dozen programs run.

Three rungs, in order:

  GUIDED    complete working code with one to three `__BLANK__` holes. The
            program already runs in the player's head; they supply one token.
            Encounter kind MISSING_RUNE, because it is not a blank-screen fight.
  TUTORIAL  a skeleton whose comments name each step, one comment per line of
            code. The player writes bodies, never structure.
  EASY      signature plus one orienting comment. The training wheels come off
            here, and only here.

The problems run in strict concept order, tagged `concept:NN`, and each one is
declared a prerequisite of the next so the ordering survives outside this file.
The twelve concepts:

   1 variables, print, types        7 set membership
   2 strings: index, slice, len     8 functions: def, return, args
   3 lists: index, append, iterate  9 the accumulator pattern
   4 for and range                 10 enumerate and zip
   5 conditionals                  11 comprehensions
   6 dict: create, get, set        12 Counter, defaultdict, deque

Each problem teaches exactly one new idea and names it in the first sentence.
No performance tests live here and no problem hides more than two tests: at this
tier the job is confidence, not filtering. That starts in python_village and
finishes in fields_of_syntax.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque

from ._base import code_problem

# The player this family exists for. Weighted toward his declared profile so the
# selector reaches for onboarding before it reaches for idiom drills.
Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 2.0}

VISUAL = {
    "GUIDED": "The program already works. Read it top to bottom, then fill the "
              "hole. You are finishing someone else's sentence, not writing an "
              "essay.",
    "TUTORIAL": "One comment, one line of code. Write the first line, run it, "
                "then write the second. Do not write all three and hope.",
    "EASY": "Say the steps out loud in English first. Then type them. The typing "
            "is the easy part once the sentence exists.",
}

VIZ = {"type": "array_scan", "caption": "One step at a time, one value at a time."}


def _drill(pid, title, concept, tier, statement, fn, params, ref, canonical,
           visible, hidden, *, pattern, family, starter="", starter_hint="",
           nudge="", pseudocode="", fragment="", visual="", edges=(),
           failures=(), after="", time="O(n)", space="O(1)", realm=""):
    """One onboarding problem. `after` is the id of the drill this one follows,
    which is what keeps concept order legible to anything reading the corpus."""
    if not realm:
        realm = "fields_of_syntax" if concept >= 10 else "python_village"
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=tier,
        family=family, profile_weight=Q, viz=VIZ, statement=statement,
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        visible=visible, hidden=hidden, edges=edges,
        time_complexity=time, space_complexity=space,
        failures=list(failures), nudge=nudge,
        visual=visual or VISUAL[tier], pseudocode=pseudocode, fragment=fragment,
        starter_code=starter, starter_hint=starter_hint,
        encounter="MISSING_RUNE" if tier == "GUIDED" else "CODE_BATTLE",
        prerequisites=[after] if after else [],
        tags=["python", "onboarding", "concept:%02d" % concept,
              "scaffold:" + tier.lower()],
    )


def _same_move(body: str) -> str:
    """Rung 4 for a scaffolded drill. Showing the answer line would make this rung
    identical to Phoenix, so it shows the same move on different data instead."""
    return "```python\n# the same move, on something else:\n" + body.strip() + "\n```"


# --- reference implementations -----------------------------------------------
# Independent of the canonical solutions on purpose: two implementations that
# agree is what earns a problem its place.

def _twice(n): return n * 2
def _greet(name): return "Hello, " + name
def _label(count): return "count: " + str(count)
def _type_name(value): return type(value).__name__

def _first_letter(text): return text[0]
def _text_length(text): return len(text)
def _last_letter(text): return text[-1]
def _first_three(text): return text[:3]
def _initials(first, last): return first[0] + last[0]

def _list_first(items): return items[0]
def _add_item(items, value): return list(items) + [value]
def _last_two(items): return items[-2:]
def _double_each(nums): return [n * 2 for n in nums]

def _count_to(n): return list(range(1, n + 1))
def _repeat(text, times): return text * times
def _every_third(items): return [items[i] for i in range(0, len(items), 3)]
def _countdown(n): return list(range(n, 0, -1))

def _is_even(n): return n % 2 == 0
def _bigger(a, b): return a if a > b else b
def _grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "F"
def _keep_long(words, least): return [w for w in words if len(w) >= least]

def _dict_lookup(prices, item): return prices[item]
def _dict_store(prices, item, price):
    out = dict(prices)
    out[item] = price
    return out
def _dict_default(prices, item): return prices.get(item, 0)
def _dict_lines(prices): return ["%s=%s" % (k, prices[k]) for k in sorted(prices)]

def _unique_count(items): return len(set(items))
def _has_value(items, value): return value in set(items)
def _set_build(items): return sorted(set(items))
def _first_repeat(items):
    seen = set()
    for value in items:
        if value in seen:
            return value
        seen.add(value)
    return None

def _area(width, height): return width * height
def _total_cost(price, quantity): return price * quantity
def _shout(text, mark="!"): return text.upper() + mark
def _double_lengths(words): return [len(w) * 2 for w in words]

def _total(nums):
    running = 0
    for value in nums:
        running += value
    return running
def _running_max(nums):
    if not nums:
        return None
    best = nums[0]
    for value in nums[1:]:
        if value > best:
            best = value
    return best
def _count_vowels(text):
    n = 0
    for ch in text:
        if ch in "aeiou":
            n += 1
    return n
def _tally(items):
    counts = {}
    for value in items:
        counts[value] = counts.get(value, 0) + 1
    return counts

def _numbered(items): return [[i, v] for i, v in enumerate(items)]
def _pair_up(a, b): return [[x, y] for x, y in zip(a, b)]
def _index_of(items, target):
    for i, value in enumerate(items):
        if value == target:
            return i
    return -1
def _add_lists(a, b): return [x + y for x, y in zip(a, b)]

def _doubled(nums): return [n * 2 for n in nums]
def _positives(nums): return [n for n in nums if n > 0]
def _shout_all(words): return [w.upper() for w in words]
def _length_map(words): return {w: len(w) for w in words}

def _counter_tally(items): return dict(Counter(items))
def _group_by_letter(words):
    out = defaultdict(list)
    for w in words:
        out[w[0]].append(w)
    return {k: out[k] for k in sorted(out)}
def _serve_queue(names, served):
    line = deque(names)
    out = []
    for _ in range(served):
        if line:
            out.append(line.popleft())
    return [out, list(line)]
def _top_words(words, n): return [list(p) for p in Counter(words).most_common(n)]


def build() -> list:
    return [
        # -- concept 1: variables, print, types -------------------------------
        _drill(
            "ob-store-value", "A Name for a Value", 1, "GUIDED",
            """
            A variable is a name you give a value so you can use it later.
            Store `n` multiplied by two under the name `doubled`, then return it.
            twice(5) gives 10, and twice(0) gives 0.
            """,
            "twice", "n", _twice,
            """
            def twice(n):
                doubled = n * 2
                return doubled
            """,
            [("five", [5]), ("zero", [0])],
            [("negative", [-3]), ("large", [50])],
            edges=[("one", [1])],
            pattern="STRING", family="onboarding_basics",
            starter="""
            def twice(n):
                # `doubled` is a name for a value. Give it the right value.
                doubled = __BLANK__
                return doubled
            """,
            nudge="The `=` sign does not mean equals. It means 'from now on, this "
                  "name refers to this value'.",
            pseudocode="doubled = n times 2\nreturn doubled",
            fragment=_same_move("tripled = n * 3"),
            time="O(1)",
        ),

        _drill(
            "ob-say-hello", "Print Is Not Return", 1, "GUIDED",
            """
            `print` shows a value on the screen. `return` hands it back to whoever
            called the function. They are not the same thing, and the game grades
            the returned value. greet("Root") returns "Hello, Root".
            """,
            "greet", "name", _greet,
            """
            def greet(name):
                message = "Hello, " + name
                print(message)
                return message
            """,
            [("root", ["Root"]), ("hash", ["Hash"])],
            [("one letter", ["X"]), ("spaces", ["Ada L"])],
            edges=[("empty name", [""])],
            pattern="STRING", family="onboarding_basics",
            after="ob-store-value",
            starter="""
            def greet(name):
                message = "Hello, " + __BLANK__
                print(message)    # shows it. Useful to you, invisible to the grader.
                return message    # hands it back. This is what gets graded.
            """,
            nudge="`+` between two strings joins them. The space after the comma "
                  "is already inside the quotes.",
            pseudocode='message = "Hello, " joined with the name\nprint it\nreturn it',
            fragment=_same_move('farewell = "Goodbye, " + name'),
            failures=["Printing the answer instead of returning it — the most "
                      "common first-week Python bug there is"],
            time="O(1)",
        ),

        _drill(
            "ob-number-to-text", "Casting the Number", 1, "TUTORIAL",
            """
            Python will not join a number onto a string with `+`. You have to
            convert it first, with `str()`. Return "count: " followed by `count`.
            """,
            "label", "count", _label,
            """
            def label(count):
                return "count: " + str(count)
            """,
            [("three", [3]), ("zero", [0])],
            [("negative", [-2]), ("big", [1024])],
            edges=[("minus one", [-1])],
            pattern="STRING", family="onboarding_basics",
            after="ob-say-hello",
            starter="""
            def label(count):
                # 1. turn the number `count` into text with str()
                # 2. join it onto "count: " with +
                # 3. return the joined string
                pass
            """,
            nudge='`"count: " + 3` raises TypeError. `"count: " + str(3)` does not.',
            pseudocode='return "count: " joined with str(count)',
            failures=["Forgetting str() and hitting "
                      "TypeError: can only concatenate str"],
            time="O(1)",
        ),

        _drill(
            "ob-type-name", "Naming the Thing", 1, "TUTORIAL",
            """
            Every value in Python has a type. `type(value)` gives you that type and
            `.__name__` gives you its name as a string. Return the type name of
            `value` — "int", "str", "list", and so on.
            """,
            "type_name", "value", _type_name,
            """
            def type_name(value):
                return type(value).__name__
            """,
            [("number", [5]), ("text", ["hi"])],
            [("list", [[1, 2]]), ("boolean", [True])],
            edges=[("float", [1.5])],
            pattern="STRING", family="onboarding_basics",
            after="ob-number-to-text",
            starter="""
            def type_name(value):
                # 1. ask for type(value)
                # 2. read its .__name__
                # 3. return that
                pass
            """,
            nudge="`type(3)` is the type itself. `type(3).__name__` is the string "
                  '"int", which is what you want to return.',
            pseudocode="return the __name__ of type(value)",
            failures=["Returning type(value) itself, which is not a string"],
            time="O(1)",
        ),

        # -- concept 2: strings, index, slice, len ----------------------------
        _drill(
            "ob-first-letter", "The Zeroth Rune", 2, "GUIDED",
            """
            Characters in a string are numbered from zero, not one. `text[0]` is
            the first character. Return the first character of `text`.
            first_letter("gauntlet") gives "g".
            """,
            "first_letter", "text", _first_letter,
            """
            def first_letter(text):
                return text[0]
            """,
            [("word", ["gauntlet"]), ("short", ["ab"])],
            [("single", ["z"]), ("space first", [" x"])],
            edges=[("digit first", ["9lives"])],
            pattern="STRING", family="onboarding_strings",
            after="ob-type-name",
            starter="""
            def first_letter(text):
                # Counting starts at zero. The first character is NOT text[1].
                return text[__BLANK__]
            """,
            nudge="If you reach for 1 you will get the second character. Python "
                  "counts from 0.",
            pseudocode="return the character at position 0",
            fragment=_same_move('"village"[0]   # "v"'),
            failures=["Using text[1] and getting the second character"],
            time="O(1)",
        ),

        _drill(
            "ob-text-length", "Measuring the Word", 2, "GUIDED",
            """
            `len(text)` counts the characters in a string. Return how many
            characters `text` has. text_length("rune") gives 4.
            """,
            "text_length", "text", _text_length,
            """
            def text_length(text):
                return len(text)
            """,
            [("rune", ["rune"]), ("empty", [""])],
            [("spaces count", ["a b"]), ("long", ["gauntlet legend"])],
            edges=[("one character", ["x"])],
            pattern="STRING", family="onboarding_strings",
            after="ob-first-letter",
            starter="""
            def text_length(text):
                # One built-in does this whole job.
                return __BLANK__(text)
            """,
            nudge="It is three letters long and you will type it a thousand times "
                  "before this is over.",
            pseudocode="return the length of text",
            fragment=_same_move("len([1, 2, 3])   # 3"),
            time="O(1)",
        ),

        _drill(
            "ob-last-letter", "Counting Backwards", 2, "TUTORIAL",
            """
            A negative index counts from the end: `text[-1]` is the last
            character, `text[-2]` the one before it. Return the last character of
            `text`.
            """,
            "last_letter", "text", _last_letter,
            """
            def last_letter(text):
                return text[-1]
            """,
            [("word", ["gauntlet"]), ("pair", ["ab"])],
            [("single", ["z"]), ("digit", ["x9"])],
            edges=[("trailing space", ["x "])],
            pattern="STRING", family="onboarding_strings",
            after="ob-text-length",
            starter="""
            def last_letter(text):
                # 1. index from the end with a negative number
                # 2. return that character
                pass
            """,
            nudge="`text[len(text) - 1]` also works. `text[-1]` is the same thing, "
                  "written the way Python people write it.",
            pseudocode="return the character at position -1",
            failures=["Using text[len(text)] and hitting IndexError"],
            time="O(1)",
        ),

        _drill(
            "ob-first-three", "The First Slice", 2, "TUTORIAL",
            """
            A slice takes a range of characters: `text[:3]` is everything up to but
            not including position 3. Return the first three characters of `text`,
            or all of it if it is shorter.
            """,
            "first_three", "text", _first_three,
            """
            def first_three(text):
                return text[:3]
            """,
            [("long", ["gauntlet"]), ("exactly three", ["run"])],
            [("shorter", ["ab"]), ("empty", [""])],
            edges=[("one character", ["a"])],
            pattern="STRING", family="onboarding_strings",
            after="ob-last-letter",
            starter="""
            def first_three(text):
                # 1. slice from the start up to position 3
                # 2. return the slice
                pass
            """,
            nudge="A slice never raises IndexError. Ask for three characters of a "
                  "two-character string and you get two, quietly.",
            pseudocode="return text sliced from the start to position 3",
            failures=["Guarding the short case by hand — the slice already handles it"],
            time="O(1)",
        ),

        _drill(
            "ob-initials", "Two Letters, Two Strings", 2, "EASY",
            """
            Return the initials of a name: the first character of `first` joined
            to the first character of `last`. Both are non-empty.
            """,
            "initials", "first, last", _initials,
            """
            def initials(first, last):
                return first[0] + last[0]
            """,
            [("full", ["Ada", "Lovelace"]), ("short", ["Jo", "Pa"])],
            [("single letters", ["X", "Y"]), ("lowercase", ["root", "node"])],
            edges=[("same initial", ["Ana", "Ash"])],
            pattern="STRING", family="onboarding_strings",
            after="ob-first-three",
            starter_hint="index each name at 0, then join with +",
            nudge="Two indexes and one `+`. Nothing else.",
            pseudocode="return first[0] joined to last[0]",
            fragment='```python\nreturn first[0] + last[0]\n```',
            time="O(1)",
        ),

        # -- concept 3: lists, index, append, iterate -------------------------
        _drill(
            "ob-list-first", "The Head of the List", 3, "GUIDED",
            """
            Lists are indexed exactly like strings: `items[0]` is the first
            element. Return the first element of `items`, which is never empty.
            list_first([9, 4, 7]) gives 9.
            """,
            "list_first", "items", _list_first,
            """
            def list_first(items):
                return items[0]
            """,
            [("numbers", [[9, 4, 7]]), ("one", [[5]])],
            [("strings", [["a", "b"]]), ("negatives", [[-1, 2]])],
            edges=[("list of lists", [[[1], [2]]])],
            pattern="ARRAY", family="onboarding_lists",
            after="ob-initials",
            starter="""
            def list_first(items):
                # Same rule as strings: the first slot is number 0.
                return items[__BLANK__]
            """,
            nudge="If you learned it for strings you already know it for lists. "
                  "Indexing is one idea, not two.",
            pseudocode="return the element at position 0",
            fragment=_same_move("[10, 20, 30][0]   # 10"),
            time="O(1)",
        ),

        _drill(
            "ob-list-append", "Adding to the Pack", 3, "GUIDED",
            """
            `.append(value)` adds one element to the end of a list, in place. Add
            `value` to the end of `items` and return the new list.
            add_item([1, 2], 3) gives [1, 2, 3].
            """,
            "add_item", "items, value", _add_item,
            """
            def add_item(items, value):
                items = list(items)
                items.append(value)
                return items
            """,
            [("numbers", [[1, 2], 3]), ("empty start", [[], 1])],
            [("strings", [["a"], "b"]), ("duplicate", [[1, 1], 1])],
            edges=[("value is a list", [[1], [2]])],
            pattern="ARRAY", family="onboarding_lists",
            after="ob-list-first",
            starter="""
            def add_item(items, value):
                items = list(items)     # a copy, so the caller's list is untouched
                items.__BLANK__(value)
                return items
            """,
            nudge="The method is six letters and it is the one you will use more "
                  "than any other list method.",
            pseudocode="copy the list\nadd value to the end\nreturn the list",
            fragment=_same_move("out = []\nout.append(1)   # out is now [1]"),
            failures=["Writing `items = items.append(value)` — append returns None, "
                      "so that throws the list away"],
            time="O(1)",
        ),

        _drill(
            "ob-last-two", "The Tail Slice", 3, "TUTORIAL",
            """
            Slices work on lists too, and a negative start counts from the end.
            Return the last two elements of `items`, or all of them if there are
            fewer than two.
            """,
            "last_two", "items", _last_two,
            """
            def last_two(items):
                return items[-2:]
            """,
            [("four", [[1, 2, 3, 4]]), ("exactly two", [[1, 2]])],
            [("one", [[7]]), ("empty", [[]])],
            edges=[("exactly three", [[1, 2, 3]])],
            pattern="ARRAY", family="onboarding_lists",
            after="ob-list-append",
            starter="""
            def last_two(items):
                # 1. slice starting two from the end and running to the end
                # 2. return the slice
                pass
            """,
            nudge="Leave the right-hand side of the colon empty and the slice runs "
                  "to the end.",
            pseudocode="return items sliced from -2 onward",
            failures=["Special-casing short lists — the slice already copes"],
            time="O(1)",
        ),

        _drill(
            "ob-double-each", "Walking the List", 3, "EASY",
            """
            A `for` loop visits each element of a list in turn. Build a new list
            holding every value in `nums` doubled, in the same order. Use a loop
            and `.append` — the one-line version comes later.
            """,
            "double_each", "nums", _double_each,
            """
            def double_each(nums):
                out = []
                for value in nums:
                    out.append(value * 2)
                return out
            """,
            [("three", [[1, 2, 3]]), ("negatives", [[-1, 4]])],
            [("zero", [[0]]), ("empty", [[]])],
            edges=[("single", [[5]])],
            pattern="ARRAY", family="onboarding_lists",
            after="ob-last-two",
            starter_hint="start with an empty list, loop, append, return it",
            nudge="Three lines before the loop body ever matters: make the empty "
                  "list, loop, return the list.",
            pseudocode="out = empty list\nfor value in nums:\n    append value * 2\nreturn out",
            failures=["Returning inside the loop, which stops after one element",
                      "Creating `out` inside the loop, which throws away every "
                      "previous element"],
        ),
        # -- concept 4: for and range -----------------------------------------
        _drill(
            "ob-count-to", "The Exclusive End", 4, "GUIDED",
            """
            `range(a, b)` counts from `a` up to but NOT including `b`. Return the
            list [1, 2, ..., n]. count_to(4) gives [1, 2, 3, 4], so the range has
            to stop one past n.
            """,
            "count_to", "n", _count_to,
            """
            def count_to(n):
                out = []
                for i in range(1, n + 1):
                    out.append(i)
                return out
            """,
            [("four", [4]), ("one", [1])],
            [("zero", [0]), ("ten", [10])],
            edges=[("negative n", [-2])],
            pattern="ARRAY", family="onboarding_loops",
            after="ob-double-each",
            starter="""
            def count_to(n):
                out = []
                for i in range(1, __BLANK__):
                    out.append(i)
                return out
            """,
            nudge="range stops one short. To include n you must ask for one more "
                  "than n.",
            pseudocode="for i from 1 up to n inclusive:\n    append i",
            fragment=_same_move("list(range(0, 3))   # [0, 1, 2] — 3 is not in it"),
            failures=["range(1, n), which quietly loses the last number"],
        ),

        _drill(
            "ob-repeat-text", "Doing It n Times", 4, "GUIDED",
            """
            When you only want to repeat something a fixed number of times and do
            not care about the counter, loop over `range(times)` and name the
            variable `_`. Return `text` repeated `times` times.
            repeat("ab", 3) gives "ababab".
            """,
            "repeat", "text, times", _repeat,
            """
            def repeat(text, times):
                out = ""
                for _ in range(times):
                    out = out + text
                return out
            """,
            [("three", ["ab", 3]), ("once", ["x", 1])],
            [("zero times", ["x", 0]), ("empty text", ["", 4])],
            edges=[("negative times", ["x", -1])],
            pattern="ARRAY", family="onboarding_loops",
            after="ob-count-to",
            starter="""
            def repeat(text, times):
                out = __BLANK__          # what should the answer start as?
                for _ in range(__BLANK__):
                    out = out + text
                return out
            """,
            nudge="`range(3)` with one argument means 0, 1, 2 — three passes. An "
                  "answer built by joining strings has to start as an empty one.",
            pseudocode="out = empty string\nrepeat `times` times:\n    out = out + text",
            fragment=_same_move("for _ in range(2):\n    print('again')"),
            time="O(n)",
        ),

        _drill(
            "ob-every-third", "Stepping the Range", 4, "TUTORIAL",
            """
            `range(start, stop, step)` takes a third argument: how far to jump each
            time. Return every third element of `items`, starting with the first.
            """,
            "every_third", "items", _every_third,
            """
            def every_third(items):
                out = []
                for i in range(0, len(items), 3):
                    out.append(items[i])
                return out
            """,
            [("seven", [[1, 2, 3, 4, 5, 6, 7]]), ("three", [[1, 2, 3]])],
            [("two", [[1, 2]]), ("empty", [[]])],
            edges=[("one", [[9]])],
            pattern="ARRAY", family="onboarding_loops",
            after="ob-repeat-text",
            starter="""
            def every_third(items):
                # 1. make an empty result list
                # 2. loop over range(0, len(items), 3)
                # 3. append items[i] each time
                # 4. return the result
                pass
            """,
            nudge="Loop over the positions here, not over the values — you need "
                  "the index to do the stepping.",
            pseudocode="for i in range(0, len(items), 3):\n    append items[i]",
            failures=["Looping over the values, which leaves you no index to step"],
        ),

        _drill(
            "ob-countdown", "Counting Down", 4, "EASY",
            """
            A negative step makes `range` run backwards. Return [n, n-1, ..., 1].
            countdown(3) gives [3, 2, 1], and countdown(0) gives [].
            """,
            "countdown", "n", _countdown,
            """
            def countdown(n):
                out = []
                for i in range(n, 0, -1):
                    out.append(i)
                return out
            """,
            [("three", [3]), ("one", [1])],
            [("zero", [0]), ("six", [6])],
            edges=[("negative n", [-1])],
            pattern="ARRAY", family="onboarding_loops",
            after="ob-every-third",
            starter_hint="range takes a start, a stop and a step; the step can be negative",
            nudge="The stop is still exclusive when you count down, so stopping at "
                  "0 is what includes 1.",
            pseudocode="for i from n down to 1:\n    append i",
            failures=["range(n, 1, -1), which loses the final 1",
                      "Forgetting the -1 step, which yields an empty range"],
        ),

        # -- concept 5: conditionals ------------------------------------------
        _drill(
            "ob-is-even", "The First Question", 5, "GUIDED",
            """
            `%` gives the remainder after division. A number is even when dividing
            it by two leaves a remainder of zero. Return True if `n` is even,
            False otherwise. is_even(4) gives True.
            """,
            "is_even", "n", _is_even,
            """
            def is_even(n):
                if n % 2 == 0:
                    return True
                return False
            """,
            [("even", [4]), ("odd", [7])],
            [("zero", [0]), ("negative even", [-6])],
            edges=[("negative odd", [-3])],
            pattern="SIMULATION", family="onboarding_conditionals",
            after="ob-countdown",
            starter="""
            def is_even(n):
                if n % 2 == __BLANK__:
                    return True
                return False
            """,
            nudge="`==` asks a question. `=` gives something a name. Only one of "
                  "them belongs inside an `if`.",
            pseudocode="if the remainder of n divided by 2 is zero:\n    True\nelse False",
            fragment=_same_move("9 % 2   # 1, so 9 is odd"),
            failures=["Writing `if n % 2 = 0`, which is a syntax error"],
            time="O(1)",
        ),

        _drill(
            "ob-bigger", "Choosing a Branch", 5, "GUIDED",
            """
            `if` runs one block, `else` runs the other, and never both. Return the
            larger of `a` and `b`. If they are equal either one is correct.
            bigger(3, 9) gives 9.
            """,
            "bigger", "a, b", _bigger,
            """
            def bigger(a, b):
                if a > b:
                    return a
                else:
                    return b
            """,
            [("second", [3, 9]), ("first", [9, 3])],
            [("equal", [4, 4]), ("negatives", [-5, -2])],
            edges=[("zero and negative", [0, -1])],
            pattern="SIMULATION", family="onboarding_conditionals",
            after="ob-is-even",
            starter="""
            def bigger(a, b):
                if a __BLANK__ b:
                    return a
                else:
                    return __BLANK__
            """,
            nudge="If `a > b` was false, there is exactly one other value it could be.",
            pseudocode="if a is greater than b: a\notherwise: b",
            fragment=_same_move("smaller = a if a < b else b"),
            time="O(1)",
        ),

        _drill(
            "ob-grade", "The Ladder of Ifs", 5, "TUTORIAL",
            """
            `elif` is checked only when every test above it failed, so order
            matters. Return "A" for 90 and above, "B" for 80 and above, "C" for 70
            and above, and "F" otherwise.
            """,
            "grade", "score", _grade,
            """
            def grade(score):
                if score >= 90:
                    return "A"
                elif score >= 80:
                    return "B"
                elif score >= 70:
                    return "C"
                else:
                    return "F"
            """,
            [("top", [95]), ("middle", [83])],
            [("boundary", [70]), ("fail", [12])],
            edges=[("exactly eighty", [80])],
            pattern="SIMULATION", family="onboarding_conditionals",
            after="ob-bigger",
            starter="""
            def grade(score):
                # 1. if score is 90 or more, return "A"
                # 2. elif 80 or more, return "B"
                # 3. elif 70 or more, return "C"
                # 4. else return "F"
                pass
            """,
            nudge="Test the highest band first. Start from 70 and a score of 95 "
                  "gets a C.",
            pseudocode='90+ -> "A"\n80+ -> "B"\n70+ -> "C"\nelse -> "F"',
            failures=["Checking the bands from lowest to highest",
                      "Using > where the specification says 'or more'"],
            time="O(1)",
        ),

        _drill(
            "ob-keep-long-words", "Filtering by Hand", 5, "EASY",
            """
            An `if` inside a `for` loop is how you keep some elements and drop the
            rest. Return the words in `words` whose length is at least `least`, in
            the original order.
            """,
            "keep_long", "words, least", _keep_long,
            """
            def keep_long(words, least):
                out = []
                for word in words:
                    if len(word) >= least:
                        out.append(word)
                return out
            """,
            [("mixed", [["a", "tree", "of"], 3]), ("all kept", [["long", "word"], 2])],
            [("none kept", [["a", "b"], 5]), ("empty", [[], 2])],
            edges=[("least is zero", [["a"], 0])],
            pattern="SIMULATION", family="onboarding_conditionals",
            after="ob-grade",
            starter_hint="empty list, loop, if the length is big enough then append",
            nudge="The `if` goes inside the loop, indented one level further than "
                  "the `for`.",
            pseudocode="for word in words:\n    if len(word) >= least:\n        append word",
            failures=["Indenting the `if` at the same level as the `for`",
                      "Using > instead of >= for 'at least'"],
        ),
        # -- concept 6: dict, create, get, set --------------------------------
        _drill(
            "ob-dict-lookup", "Opening the Vault", 6, "GUIDED",
            """
            A dict maps keys to values. `prices[item]` looks up one key. Return the
            price of `item`, which is always present.
            dict_lookup({"potion": 5}, "potion") gives 5.
            """,
            "dict_lookup", "prices, item", _dict_lookup,
            """
            def dict_lookup(prices, item):
                return prices[item]
            """,
            [("potion", [{"potion": 5, "rope": 2}, "potion"]),
             ("rope", [{"potion": 5, "rope": 2}, "rope"])],
            [("single entry", [{"map": 9}, "map"]),
             ("zero value", [{"lamp": 0}, "lamp"])],
            edges=[("numeric key", [{1: "a"}, 1])],
            pattern="HASH_MAP", family="onboarding_dict",
            after="ob-keep-long-words",
            starter="""
            def dict_lookup(prices, item):
                # Square brackets again — but a key goes in them, not a number.
                return prices[__BLANK__]
            """,
            nudge="The key you want is sitting in the parameter list.",
            pseudocode="return the value stored under `item`",
            fragment=_same_move('{"a": 1}["a"]   # 1'),
            failures=["Looking up a missing key, which raises KeyError"],
            time="O(1)",
        ),

        _drill(
            "ob-dict-store", "Writing to the Vault", 6, "GUIDED",
            """
            `d[key] = value` stores a value, creating the key if it did not exist.
            Store `price` under `item` and return the updated dict.
            dict_store({}, "rope", 2) gives {"rope": 2}.
            """,
            "dict_store", "prices, item, price", _dict_store,
            """
            def dict_store(prices, item, price):
                prices = dict(prices)
                prices[item] = price
                return prices
            """,
            [("new key", [{}, "rope", 2]),
             ("overwrite", [{"rope": 2}, "rope", 9])],
            [("second key", [{"rope": 2}, "map", 4]),
             ("zero", [{}, "lamp", 0])],
            edges=[("numeric key", [{}, 1, 2])],
            pattern="HASH_MAP", family="onboarding_dict",
            after="ob-dict-lookup",
            starter="""
            def dict_store(prices, item, price):
                prices = dict(prices)      # a copy, so the caller's dict is untouched
                prices[__BLANK__] = __BLANK__
                return prices
            """,
            nudge="A dict has no `.add`. Assignment is how you both create and "
                  "overwrite an entry.",
            pseudocode="copy the dict\nset prices[item] to price\nreturn it",
            fragment=_same_move('d = {}\nd["key"] = 1   # d is now {"key": 1}'),
            time="O(1)",
        ),

        _drill(
            "ob-dict-default", "Asking Without Breaking", 6, "TUTORIAL",
            """
            `prices[item]` raises KeyError when the key is missing. `prices.get(item,
            0)` returns 0 instead. Return the price of `item`, or 0 when it is not
            in the dict.
            """,
            "dict_default", "prices, item", _dict_default,
            """
            def dict_default(prices, item):
                return prices.get(item, 0)
            """,
            [("present", [{"rope": 2}, "rope"]), ("missing", [{"rope": 2}, "map"])],
            [("empty dict", [{}, "rope"]), ("zero stored", [{"lamp": 0}, "lamp"])],
            edges=[("numeric key", [{1: 5}, 1])],
            pattern="HASH_MAP", family="onboarding_dict",
            after="ob-dict-store",
            starter="""
            def dict_default(prices, item):
                # 1. call .get on the dict with two arguments: the key, and 0
                # 2. return what it gives you
                pass
            """,
            nudge="`.get` with one argument returns None for a missing key. The "
                  "second argument is what you want instead.",
            pseudocode="return prices.get(item, 0)",
            failures=["Writing an `if item in prices` branch, which works but is "
                      "four lines where one will do"],
            time="O(1)",
        ),

        _drill(
            "ob-dict-lines", "Reading Every Entry", 6, "EASY",
            """
            Looping over a dict gives you its keys. Return one "key=value" string
            per entry, sorted by key. For {"b": 2, "a": 1} return ["a=1", "b=2"].
            """,
            "dict_lines", "prices", _dict_lines,
            """
            def dict_lines(prices):
                out = []
                for key in sorted(prices):
                    out.append(str(key) + "=" + str(prices[key]))
                return out
            """,
            [("two", [{"b": 2, "a": 1}]), ("one", [{"rope": 9}])],
            [("empty", [{}]), ("three", [{"c": 3, "a": 1, "b": 2}])],
            edges=[("keys sort as text", [{"10": 1, "9": 2}])],
            pattern="HASH_MAP", family="onboarding_dict",
            after="ob-dict-default",
            starter_hint="sorted(prices) gives the keys in order; build one string per key",
            nudge="`sorted(prices)` sorts the keys. You still need the value, and "
                  "`prices[key]` is how you get it.",
            pseudocode="for key in sorted(prices):\n    append key + '=' + str(value)",
            failures=["Joining a number onto a string without str()",
                      "Relying on dict order instead of sorting"],
            time="O(n log n)",
        ),

        # -- concept 7: set membership ----------------------------------------
        _drill(
            "ob-unique-count", "Throwing Away Duplicates", 7, "GUIDED",
            """
            A set holds each value at most once. `set(items)` throws the duplicates
            away. Return how many distinct values are in `items`.
            unique_count([1, 1, 2]) gives 2.
            """,
            "unique_count", "items", _unique_count,
            """
            def unique_count(items):
                return len(set(items))
            """,
            [("duplicates", [[1, 1, 2]]), ("all distinct", [[1, 2, 3]])],
            [("empty", [[]]), ("strings", [["a", "a", "a"]])],
            edges=[("1 and \"1\" differ", [[1, "1"]])],
            pattern="SET", family="onboarding_set",
            after="ob-dict-lines",
            starter="""
            def unique_count(items):
                # Two built-ins, one inside the other.
                return len(__BLANK__(items))
            """,
            nudge="You already know how to count things. The only new part is "
                  "removing the duplicates first.",
            pseudocode="return the length of the set of items",
            fragment=_same_move("set([3, 3, 4])   # {3, 4}"),
            time="O(n)",
        ),

        _drill(
            "ob-has-value", "Have I Seen This", 7, "TUTORIAL",
            """
            `value in collection` is True when the value is present. On a set that
            check is instant no matter how large the set is; on a list it walks the
            whole thing. Return True when `value` appears in `items`.
            """,
            "has_value", "items, value", _has_value,
            """
            def has_value(items, value):
                known = set(items)
                return value in known
            """,
            [("present", [[1, 2, 3], 2]), ("absent", [[1, 2, 3], 9])],
            [("empty", [[], 1]), ("strings", [["a", "b"], "b"])],
            edges=[("duplicates", [[1, 1], 1])],
            pattern="SET", family="onboarding_set",
            after="ob-unique-count",
            starter="""
            def has_value(items, value):
                # 1. build a set from items
                # 2. return whether value is in that set
                pass
            """,
            nudge="`in` is a whole operator. There is no loop to write here.",
            pseudocode="known = set(items)\nreturn value in known",
            failures=["Writing a loop with a found flag, which is correct and "
                      "four times as long"],
            time="O(n)",
        ),

        _drill(
            "ob-set-build", "Filling the Set", 7, "TUTORIAL",
            """
            `.add(value)` puts one value into a set, and adding something already
            there changes nothing. Build a set from `items` with a loop and return
            its values sorted ascending.
            """,
            "set_build", "items", _set_build,
            """
            def set_build(items):
                seen = set()
                for value in items:
                    seen.add(value)
                return sorted(seen)
            """,
            [("duplicates", [[3, 1, 3]]), ("sorted already", [[1, 2]])],
            [("empty", [[]]), ("one", [[5]])],
            edges=[("all identical", [[2, 2, 2]])],
            pattern="SET", family="onboarding_set",
            after="ob-has-value",
            starter="""
            def set_build(items):
                # 1. start with an empty set: set()
                # 2. loop over items and .add each one
                # 3. return sorted(seen)
                pass
            """,
            nudge="`{}` is an empty dict, not an empty set. The empty set is "
                  "`set()`.",
            pseudocode="seen = set()\nfor value in items: seen.add(value)\nreturn sorted(seen)",
            failures=["Using `{}` for an empty set and getting a dict",
                      "Using .append, which sets do not have"],
            time="O(n log n)",
        ),

        _drill(
            "ob-first-repeat", "The First Face Twice", 7, "EASY",
            """
            Keep a set of what you have already seen, and check it before adding.
            Return the first value in `items` that appears a second time, or None
            when every value is distinct.
            """,
            "first_repeat", "items", _first_repeat,
            """
            def first_repeat(items):
                seen = set()
                for value in items:
                    if value in seen:
                        return value
                    seen.add(value)
                return None
            """,
            [("repeat", [[1, 2, 1, 3]]), ("none", [[1, 2, 3]])],
            [("immediate", [[4, 4]]), ("empty", [[]])],
            edges=[("repeat at the end", [[1, 2, 3, 3]])],
            pattern="SET", family="onboarding_set",
            after="ob-set-build",
            starter_hint="a `seen` set; check before you add, return as soon as you hit one",
            nudge="Check membership BEFORE adding. Add first and every value looks "
                  "like a repeat.",
            pseudocode="seen = set()\nfor value: if in seen -> return it; else add it\nreturn None",
            failures=["Adding before checking, which reports the first element",
                      "Returning None from inside the loop, which stops after one step"],
            time="O(n)",
        ),

        # -- concept 8: functions, def, return, args --------------------------
        _drill(
            "ob-two-arguments", "Two Parameters", 8, "GUIDED",
            """
            A function can take more than one argument; they arrive in the order
            they are written. Return the area of a rectangle, which is its width
            times its height. area(3, 4) gives 12.
            """,
            "area", "width, height", _area,
            """
            def area(width, height):
                return width * height
            """,
            [("small", [3, 4]), ("square", [5, 5])],
            [("one wide", [1, 7]), ("zero", [0, 9])],
            edges=[("both zero", [0, 0])],
            pattern="ARRAY", family="onboarding_functions",
            after="ob-first-repeat",
            starter="""
            def area(width, height):
                return width * __BLANK__
            """,
            nudge="Both parameters are already named for you. Use the second one.",
            pseudocode="return width times height",
            fragment=_same_move("perimeter = 2 * (width + height)"),
            time="O(1)",
        ),

        _drill(
            "ob-return-not-print", "Hand It Back", 8, "GUIDED",
            """
            A function that prints its answer and never returns it gives the caller
            None. Return the total cost, which is the price times the quantity.
            total_cost(3, 4) returns 12 and also prints it.
            """,
            "total_cost", "price, quantity", _total_cost,
            """
            def total_cost(price, quantity):
                total = price * quantity
                print(total)
                return total
            """,
            [("basic", [3, 4]), ("single", [7, 1])],
            [("zero quantity", [5, 0]), ("large", [12, 12])],
            edges=[("zero price", [0, 5])],
            pattern="ARRAY", family="onboarding_functions",
            after="ob-two-arguments",
            starter="""
            def total_cost(price, quantity):
                total = price * quantity
                print(total)      # you can see it
                __BLANK__ total   # the caller can use it
            """,
            nudge="Six letters. Without it the function evaluates to None no "
                  "matter what it printed.",
            pseudocode="total = price * quantity\nprint total\nreturn total",
            fragment=_same_move("def half(n):\n    return n / 2"),
            failures=["Printing instead of returning — the test sees None"],
            time="O(1)",
        ),

        _drill(
            "ob-default-argument", "A Parameter With a Default", 8, "TUTORIAL",
            """
            A parameter can carry a default value, used whenever the caller leaves
            it out. Return `text` in upper case with `mark` on the end, where
            `mark` defaults to "!". Keep the signature exactly as given.
            """,
            "shout", 'text, mark="!"', _shout,
            """
            def shout(text, mark="!"):
                return text.upper() + mark
            """,
            [("default mark", ["ready"]), ("given mark", ["ready", "?"])],
            [("already upper", ["OK"]), ("empty mark", ["go", ""])],
            edges=[("empty text", ["", "!"])],
            pattern="STRING", family="onboarding_functions",
            after="ob-return-not-print",
            starter="""
            def shout(text, mark="!"):
                # 1. upper-case the text with .upper()
                # 2. join `mark` onto the end with +
                # 3. return it
                pass
            """,
            nudge="`.upper()` returns a new string; it does not change the one you "
                  "called it on.",
            pseudocode="return text.upper() + mark",
            failures=["Calling text.upper without the parentheses, which returns "
                      "the method itself",
                      "Hard-coding \"!\" and ignoring `mark`"],
            time="O(n)",
        ),

        _drill(
            "ob-helper-call", "A Function Calling a Function", 8, "EASY",
            """
            Functions call other functions; that is how a large program stays
            small. Define a helper that doubles the length of one word, then use it
            on every word. Return the list of doubled lengths, in order.
            """,
            "double_lengths", "words", _double_lengths,
            """
            def double_lengths(words):
                def doubled_length(word):
                    return len(word) * 2

                out = []
                for word in words:
                    out.append(doubled_length(word))
                return out
            """,
            [("three", [["a", "be", "see"]]), ("one", [["rune"]])],
            [("empty word", [[""]]), ("empty list", [[]])],
            edges=[("long word", [["gauntlet"]])],
            pattern="ARRAY", family="onboarding_functions",
            after="ob-default-argument",
            starter_hint="define a small helper first, then loop and call it once per word",
            nudge="The helper is an ordinary `def`, written inside the outer one "
                  "and indented to match.",
            pseudocode="def helper(word): return len(word) * 2\nfor word in words: append helper(word)",
            failures=["Defining the helper after the loop that uses it",
                      "Calling the helper without parentheses"],
        ),
        # -- concept 9: the accumulator pattern --------------------------------
        _drill(
            "ob-running-total", "The Accumulator", 9, "GUIDED",
            """
            The accumulator pattern: one variable outside the loop, updated once
            per element. Return the sum of `nums` using a loop rather than `sum`.
            total([1, 2, 3]) gives 6.
            """,
            "total", "nums", _total,
            """
            def total(nums):
                running = 0
                for value in nums:
                    running = running + value
                return running
            """,
            [("three", [[1, 2, 3]]), ("negatives", [[-1, 4]])],
            [("empty", [[]]), ("one", [[7]])],
            edges=[("all negative", [[-1, -2]])],
            pattern="ARRAY", family="onboarding_loops",
            after="ob-helper-call",
            starter="""
            def total(nums):
                running = __BLANK__               # before the loop
                for value in nums:
                    running = running + __BLANK__  # once per element
                return running                    # after the loop
            """,
            nudge="Three positions matter and the starter names all three: set up "
                  "before, update inside, return after.",
            pseudocode="running = 0\nfor value in nums:\n    running = running + value\nreturn running",
            fragment=_same_move("count = 0\nfor _ in items:\n    count = count + 1"),
            failures=["Resetting `running` inside the loop, which returns only the "
                      "last element",
                      "Returning inside the loop, which returns after one element"],
        ),

        _drill(
            "ob-running-max", "Best So Far", 9, "TUTORIAL",
            """
            An accumulator does not have to be a number you add to — it can be the
            best value seen so far. Return the largest value in `nums` without
            using `max`, or None when `nums` is empty.
            """,
            "largest", "nums", _running_max,
            """
            def largest(nums):
                if not nums:
                    return None
                best = nums[0]
                for value in nums:
                    if value > best:
                        best = value
                return best
            """,
            [("rising", [[1, 5, 3]]), ("first is best", [[9, 2]])],
            [("empty", [[]]), ("negatives", [[-5, -2]])],
            edges=[("all equal", [[3, 3]])],
            pattern="ARRAY", family="onboarding_loops",
            after="ob-running-total",
            starter="""
            def largest(nums):
                # 1. if nums is empty, return None
                # 2. start `best` at the first element
                # 3. loop; whenever a value beats `best`, replace it
                # 4. return best
                pass
            """,
            nudge="Start `best` at the first element, not at 0. All-negative input "
                  "is what catches that.",
            pseudocode="best = nums[0]\nfor value: if value > best: best = value\nreturn best",
            failures=["Starting `best` at 0, which is wrong for all-negative input",
                      "Forgetting the empty case and hitting IndexError"],
        ),

        _drill(
            "ob-count-vowels", "Counting With a Condition", 9, "TUTORIAL",
            """
            An accumulator plus an `if` counts only the things you care about.
            Return how many characters of `text` are vowels. Count only lowercase
            a, e, i, o and u.
            """,
            "count_vowels", "text", _count_vowels,
            """
            def count_vowels(text):
                count = 0
                for ch in text:
                    if ch in "aeiou":
                        count = count + 1
                return count
            """,
            [("word", ["gauntlet"]), ("none", ["rhythm"])],
            [("empty", [""]), ("uppercase ignored", ["AEIou"])],
            edges=[("all vowels", ["aeiou"])],
            pattern="STRING", family="onboarding_loops",
            after="ob-running-max",
            starter="""
            def count_vowels(text):
                # 1. count = 0
                # 2. loop over the characters of text
                # 3. if the character is in "aeiou", add one
                # 4. return count
                pass
            """,
            nudge='Looping over a string gives you one character at a time, and '
                  '`ch in "aeiou"` is the whole membership test.',
            pseudocode='count = 0\nfor ch in text:\n    if ch in "aeiou": count += 1\nreturn count',
            failures=["Counting uppercase vowels the specification excludes"],
        ),

        _drill(
            "ob-tally", "Counting Into a Dict", 9, "EASY",
            """
            The accumulator can be a dict: one counter per distinct value. Return a
            dict mapping each value in `items` to how many times it appears. Build
            it with `.get`, not with Counter — Counter comes later.
            """,
            "tally", "items", _tally,
            """
            def tally(items):
                counts = {}
                for value in items:
                    counts[value] = counts.get(value, 0) + 1
                return counts
            """,
            [("letters", [["a", "b", "a"]]), ("numbers", [[1, 1, 1]])],
            [("empty", [[]]), ("all distinct", [["x", "y"]])],
            edges=[("1 and \"1\" differ", [[1, "1"]])],
            pattern="HASH_MAP", family="onboarding_loops",
            after="ob-count-vowels",
            starter_hint="an empty dict, then counts[value] = counts.get(value, 0) + 1",
            nudge="`.get(value, 0)` is what makes the first sighting work. Without "
                  "it the first `+ 1` raises KeyError.",
            pseudocode="counts = {}\nfor value in items:\n    counts[value] = counts.get(value, 0) + 1",
            failures=["Writing counts[value] = counts[value] + 1, which raises "
                      "KeyError on the first sighting"],
            time="O(n)",
        ),

        # -- concept 10: enumerate and zip -------------------------------------
        _drill(
            "ob-enumerate-pairs", "Index and Value At Once", 10, "GUIDED",
            """
            `enumerate(items)` hands you the position and the value together, so
            you never have to keep a counter by hand. Return [[index, value], ...]
            for every element. numbered(["a", "b"]) gives [[0, "a"], [1, "b"]].
            """,
            "numbered", "items", _numbered,
            """
            def numbered(items):
                out = []
                for index, value in enumerate(items):
                    out.append([index, value])
                return out
            """,
            [("letters", [["a", "b"]]), ("numbers", [[9]])],
            [("empty", [[]]), ("three", [["x", "y", "z"]])],
            edges=[("values are lists", [[[1], [2]]])],
            pattern="ARRAY", family="onboarding_idioms",
            after="ob-tally",
            starter="""
            def numbered(items):
                out = []
                for index, value in __BLANK__(items):
                    out.append(__BLANK__)
                return out
            """,
            nudge="It is nine letters and it replaces the `i = 0` / `i += 1` "
                  "bookkeeping you would otherwise write.",
            pseudocode="for index, value in enumerate(items):\n    append [index, value]",
            fragment=_same_move('for i, ch in enumerate("ab"):\n    print(i, ch)'),
            failures=["Looping over range(len(items)) and indexing by hand — "
                      "correct, but not what this drill is teaching"],
            time="O(n)",
        ),

        _drill(
            "ob-pair-up", "Two Lists, Side by Side", 10, "TUTORIAL",
            """
            `zip(a, b)` walks two sequences in step and stops at the shorter one.
            Return [[a0, b0], [a1, b1], ...] as a list of two-element lists.
            """,
            "pair_up", "a, b", _pair_up,
            """
            def pair_up(a, b):
                out = []
                for x, y in zip(a, b):
                    out.append([x, y])
                return out
            """,
            [("same length", [[1, 2], ["a", "b"]]),
             ("b shorter", [[1, 2, 3], ["a"]])],
            [("empty", [[], []]), ("a shorter", [[1], ["a", "b"]])],
            edges=[("one side empty", [[1, 2], []])],
            pattern="ARRAY", family="onboarding_idioms",
            after="ob-enumerate-pairs",
            starter="""
            def pair_up(a, b):
                # 1. make an empty result list
                # 2. loop over zip(a, b), unpacking into x and y
                # 3. append [x, y]
                # 4. return the result
                pass
            """,
            nudge="zip stops at the shorter input rather than raising. That is a "
                  "feature here, not a bug.",
            pseudocode="for x, y in zip(a, b):\n    append [x, y]",
            failures=["Returning the zip object itself, which is not a list",
                      "Appending a tuple where a list is required"],
            time="O(n)",
        ),

        _drill(
            "ob-index-of", "Finding the Position", 10, "EASY",
            """
            Return the index of the first element of `items` equal to `target`, or
            -1 when it is not there. Use `enumerate` so you have the index to
            return.
            """,
            "index_of", "items, target", _index_of,
            """
            def index_of(items, target):
                for index, value in enumerate(items):
                    if value == target:
                        return index
                return -1
            """,
            [("present", [[1, 2, 3], 2]), ("absent", [[1, 2], 9])],
            [("first", [[5, 5], 5]), ("empty", [[], 1])],
            edges=[("target is last", [[1, 2, 3], 3])],
            pattern="ARRAY", family="onboarding_idioms",
            after="ob-pair-up",
            starter_hint="enumerate, return the index on the first match, -1 after the loop",
            nudge="The `return -1` belongs after the loop, not in an `else` on the "
                  "`if`. An `else` there reports -1 on the first mismatch.",
            pseudocode="for index, value in enumerate(items):\n    if value == target: return index\nreturn -1",
            failures=["Putting `return -1` inside the loop, which gives up after "
                      "the first element"],
            time="O(n)",
        ),

        _drill(
            "ob-add-lists", "Adding Two Lists", 10, "EASY",
            """
            Return a list holding the element-wise sum of `a` and `b`, stopping at
            the shorter one. add_lists([1, 2], [10, 20]) gives [11, 22].
            """,
            "add_lists", "a, b", _add_lists,
            """
            def add_lists(a, b):
                out = []
                for x, y in zip(a, b):
                    out.append(x + y)
                return out
            """,
            [("same length", [[1, 2], [10, 20]]), ("uneven", [[1, 2, 3], [1]])],
            [("empty", [[], []]), ("negatives", [[-1], [1]])],
            edges=[("one side empty", [[1], []])],
            pattern="ARRAY", family="onboarding_idioms",
            after="ob-index-of",
            starter_hint="zip walks both lists in step; append each pair's sum",
            nudge="Same shape as pairing them up. The only change is what you "
                  "append.",
            pseudocode="for x, y in zip(a, b):\n    append x + y",
            time="O(n)",
        ),

        # -- concept 11: comprehensions ----------------------------------------
        _drill(
            "ob-comprehension-first", "The Loop on One Line", 11, "GUIDED",
            """
            A list comprehension is a `for` loop that builds a list, written on one
            line: `[word.upper() for word in words]`. Return every value in `nums`
            doubled. doubled([1, 2, 3]) gives [2, 4, 6].
            """,
            "doubled", "nums", _doubled,
            """
            def doubled(nums):
                return [value * 2 for value in nums]
            """,
            [("three", [[1, 2, 3]]), ("negatives", [[-1, 4]])],
            [("empty", [[]]), ("zero", [[0]])],
            edges=[("large", [[1000]])],
            pattern="ARRAY", family="onboarding_comprehensions",
            after="ob-add-lists",
            starter="""
            def doubled(nums):
                # The expression comes first, the `for` comes second.
                return [__BLANK__ for value in __BLANK__]
            """,
            nudge="Read it right to left: take each value in nums, double it, "
                  "collect the results.",
            pseudocode="[value * 2 for value in nums]",
            fragment=_same_move("[len(w) for w in words]"),
            time="O(n)",
        ),

        _drill(
            "ob-comprehension-filter", "Keeping Only Some", 11, "TUTORIAL",
            """
            A comprehension can end with an `if`, which decides what gets kept.
            Return the values of `nums` that are greater than zero, in order.
            """,
            "positives", "nums", _positives,
            """
            def positives(nums):
                return [value for value in nums if value > 0]
            """,
            [("mixed", [[-1, 2, 3]]), ("none", [[-1, -2]])],
            [("empty", [[]]), ("zero excluded", [[0, 1]])],
            edges=[("all kept", [[1, 2]])],
            pattern="ARRAY", family="onboarding_comprehensions",
            after="ob-comprehension-first",
            starter="""
            def positives(nums):
                # 1. write the comprehension: value, then for, then if
                # 2. return it
                pass
            """,
            nudge="The order is expression, then `for`, then `if`. The filter goes "
                  "last.",
            pseudocode="[value for value in nums if value > 0]",
            failures=["Putting the `if` before the `for`, which is a different "
                      "construct and needs an `else`"],
            time="O(n)",
        ),

        _drill(
            "ob-comprehension-upper", "Transforming Each One", 11, "TUTORIAL",
            """
            The expression at the front of a comprehension can be any expression,
            including a method call. Return every word in `words` upper-cased, in
            order.
            """,
            "shout_all", "words", _shout_all,
            """
            def shout_all(words):
                return [word.upper() for word in words]
            """,
            [("two", [["a", "be"]]), ("already upper", [["OK"]])],
            [("empty list", [[]]), ("empty word", [[""]])],
            edges=[("mixed case", [["aB"]])],
            pattern="STRING", family="onboarding_comprehensions",
            after="ob-comprehension-filter",
            starter="""
            def shout_all(words):
                # 1. comprehension over words, calling .upper() on each
                # 2. return it
                pass
            """,
            nudge="`.upper()` gives back a new string. Nothing is modified in place.",
            pseudocode="[word.upper() for word in words]",
            time="O(n)",
        ),

        _drill(
            "ob-length-map", "A Comprehension That Builds a Dict", 11, "EASY",
            """
            Swap the brackets for braces and add a colon and you build a dict
            instead of a list. Return a dict mapping each word in `words` to its
            length.
            """,
            "length_map", "words", _length_map,
            """
            def length_map(words):
                return {word: len(word) for word in words}
            """,
            [("two", [["a", "tree"]]), ("one", [["rune"]])],
            [("empty", [[]]), ("duplicate word", [["a", "a"]])],
            edges=[("empty word", [[""]])],
            pattern="HASH_MAP", family="onboarding_comprehensions",
            after="ob-comprehension-upper",
            starter_hint="braces, then key: value, then the for clause",
            nudge="`{word: len(word) for word in words}` — the colon is the whole "
                  "difference between a dict and a set comprehension.",
            pseudocode="{word: len(word) for word in words}",
            failures=["Forgetting the colon, which quietly builds a set instead"],
            time="O(n)",
        ),

        # -- concept 12: Counter, defaultdict, deque ---------------------------
        _drill(
            "ob-counter-intro", "The Counting Dict", 12, "GUIDED",
            """
            `collections.Counter` does the tally you wrote by hand in Counting Into
            a Dict. Return a plain dict mapping each value in `items` to its count.
            counter_tally(["a", "a", "b"]) gives {"a": 2, "b": 1}.
            """,
            "counter_tally", "items", _counter_tally,
            """
            def counter_tally(items):
                from collections import Counter
                return dict(Counter(items))
            """,
            [("letters", [["a", "a", "b"]]), ("numbers", [[1, 2, 2]])],
            [("empty", [[]]), ("single", [["x"]])],
            edges=[("all identical", [["a", "a"]])],
            pattern="HASH_MAP", family="onboarding_collections",
            after="ob-length-map",
            starter="""
            def counter_tally(items):
                from collections import Counter
                # Counter counts. dict() turns it back into an ordinary dict.
                return dict(__BLANK__(items))
            """,
            nudge="You wrote this by hand three drills ago. This is the same thing "
                  "with the loop already written for you.",
            pseudocode="dict(Counter(items))",
            fragment=_same_move('Counter("aab")   # Counter({"a": 2, "b": 1})'),
            time="O(n)",
        ),

        _drill(
            "ob-group-by-letter", "The Dict That Fills Itself", 12, "TUTORIAL",
            """
            `defaultdict(list)` creates an empty list the first time you touch a
            key, so you never write the 'if the key is missing' branch. Group
            `words` by their first letter and return a plain dict, keys sorted,
            each list in the original order. Every word is non-empty.
            """,
            "group_by_letter", "words", _group_by_letter,
            """
            def group_by_letter(words):
                from collections import defaultdict
                groups = defaultdict(list)
                for word in words:
                    groups[word[0]].append(word)
                return {key: groups[key] for key in sorted(groups)}
            """,
            [("two groups", [["ant", "bee", "ape"]]), ("one group", [["ant", "ape"]])],
            [("empty", [[]]), ("single letters", [["a", "b"]])],
            edges=[("single word", [["zebra"]])],
            pattern="HASH_MAP", family="onboarding_collections",
            after="ob-counter-intro",
            starter="""
            def group_by_letter(words):
                from collections import defaultdict
                # 1. groups = defaultdict(list)
                # 2. for each word, append it to groups[word[0]]
                # 3. return a plain dict with the keys sorted
                pass
            """,
            nudge="`defaultdict(list)` takes the FUNCTION `list`, not a call to it. "
                  "No parentheses after it.",
            pseudocode="groups = defaultdict(list)\nfor word: groups[word[0]].append(word)\nreturn sorted plain dict",
            failures=["Writing defaultdict(list()) instead of defaultdict(list)",
                      "Returning the defaultdict itself rather than a plain dict"],
            time="O(n log n)",
        ),

        _drill(
            "ob-serve-queue", "First In, First Out", 12, "TUTORIAL",
            """
            `collections.deque` removes from the front in constant time, which a
            list cannot do. Serve the first `served` names from the front of the
            line and return [served_names, who_is_left].
            """,
            "serve_queue", "names, served", _serve_queue,
            """
            def serve_queue(names, served):
                from collections import deque
                line = deque(names)
                out = []
                for _ in range(served):
                    if line:
                        out.append(line.popleft())
                return [out, list(line)]
            """,
            [("two of three", [["a", "b", "c"], 2]),
             ("none served", [["a", "b"], 0])],
            [("more than present", [["a"], 3]), ("empty line", [[], 2])],
            edges=[("serve every one", [["a", "b"], 2])],
            pattern="HASH_MAP", family="onboarding_collections",
            after="ob-group-by-letter",
            starter="""
            def serve_queue(names, served):
                from collections import deque
                # 1. line = deque(names)
                # 2. loop `served` times, popleft one name each time IF any remain
                # 3. return [served_names, list(line)]
                pass
            """,
            nudge="`.popleft()` on an empty deque raises IndexError, so check that "
                  "the line is not empty before each serve.",
            pseudocode="line = deque(names)\nrepeat served times: if line: out.append(line.popleft())\nreturn [out, list(line)]",
            failures=["Serving more people than are in the line",
                      "Returning the deque itself instead of a list"],
            time="O(n)",
        ),

        _drill(
            "ob-top-words", "The Most Common Ones", 12, "EASY",
            """
            `Counter.most_common(n)` returns the n highest-count entries, largest
            first. Return them as a list of [word, count] pairs for the `n` most
            common words in `words`. Ties may come back in any order.
            """,
            "top_words", "words, n", _top_words,
            """
            def top_words(words, n):
                from collections import Counter
                return [list(pair) for pair in Counter(words).most_common(n)]
            """,
            [("clear winner", [["a", "a", "a", "b", "b", "c"], 2]),
             ("single", [["a", "a", "b"], 1])],
            [("n larger than input", [["a"], 5]), ("empty", [[], 2])],
            edges=[("n is zero", [["a", "a"], 0])],
            pattern="HASH_MAP", family="onboarding_collections",
            after="ob-serve-queue",
            starter_hint="Counter(words).most_common(n) gives tuples; the tests want lists",
            nudge="`most_common` hands back tuples. The tests compare against "
                  "lists, so convert each pair.",
            pseudocode="[list(pair) for pair in Counter(words).most_common(n)]",
            failures=["Returning tuples where lists are expected",
                      "Sorting the whole Counter by hand when most_common exists"],
            time="O(n log n)",
        ),
    ]
