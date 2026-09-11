"""Rune assembly: the solution already exists, scattered. Put it back in order.

This family exists for one player and one bottleneck: he can read Python fluently
and freezes when the screen is empty. A Parsons problem removes the typing and the
syntax recall and leaves only the structure — which is the part he is actually
missing. He is not being asked to remember that `dict.get` takes a default. He is
being asked whether the counter increment goes inside the loop or after it.

Three things make these puzzles honest rather than a matching game:

  * Every ordering is EXECUTED. `grade_rune_assembly` assembles the runes the
    player placed, at the depths they chose, and runs the result against the real
    tests. A memorised sequence that does not run is not a solve.
  * Every puzzle carries one to three DISTRACTORS. Each one is a line that is
    right somewhere else — the correct move for a neighbouring pattern, a sort
    that cannot help, a bound that is off by one. Placing one fails the encounter
    and shows its note, so a wrong rune teaches the distinction it came from.
  * The runes are DERIVED from the canonical solution, not typed twice. A rune
    list and a worked solution that drift apart would produce a puzzle whose
    correct answer does not pass its own tests, and the corpus validator would
    reject it — but only after it had already been shipped to the player as an
    unsolvable fight. Deriving makes the drift impossible.

The ladder runs the way the curriculum runs. Fluency first — accumulators, a loop
with a condition in it, counting into a dict, building a string — at GUIDED for
short bodies and TUTORIAL for longer ones. Then the interview patterns at EASY:
hash map, sliding window, two pointers, stack, queue, BFS, DFS, tree recursion,
binary search, prefix sum, DP. Families match the code battles exactly, so the
SRS schedules an assembly of `two_sum` in the same rotation as writing `two_sum`
from scratch. Reading the structure and producing the structure are the same
skill met from two directions.
"""
from __future__ import annotations

import bisect
import math
from collections import Counter, deque

from ._base import code_problem, dedent
from ._tree import PREAMBLE, tree_ref
from ...puzzles import shuffle_runes

# Weighted toward this player's declared profile. Assembly is the bridge he needs,
# so the selector should reach for it early and often.
Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 2.0}

VIZ = {"type": "array_scan",
       "caption": "Order is the whole puzzle. Depth is the other half of it."}

VISUAL = (
    "Read the runes once and find the two that obviously anchor it: the `def` and "
    "the `return`. Everything else lives between them. Then ask of each remaining "
    "rune — does this happen once, or once per item? Once means outside the loop."
)

REALM = {
    "ARRAY": "array_caverns", "STRING": "stringwood_labyrinth",
    "SIMULATION": "python_village", "HASH_MAP": "hashmap_highlands",
    "SET": "hashmap_highlands", "SLIDING_WINDOW": "sliding_window_marsh",
    "TWO_POINTER": "twin_pointer_pass", "PREFIX_SUM": "sliding_window_marsh",
    "STACK": "stack_queue_mines", "QUEUE": "stack_queue_mines",
    "BFS": "graph_wastes", "DFS": "graph_wastes", "MATRIX": "matrix_citadel",
    "TREE": "binary_tree_canopy", "RECURSION": "recursive_forest",
    "BINARY_SEARCH": "complexity_tower", "DP": "dp_ruins",
}


def _runes(canonical: str, distractors, notes: dict) -> list:
    """Turn the canonical solution into the rune list, then append the traps.

    Indentation is carried as depth units rather than spaces because that is what
    the player manipulates in the UI — the arrows move a line one level, not four
    characters. Anything not a clean multiple of four is an authoring mistake and
    is raised here rather than shipped as a puzzle with an unreachable answer.
    """
    out = []
    for line in dedent(canonical).splitlines():
        if not line.strip():
            continue                       # blank lines cannot be dragged
        spaces = len(line) - len(line.lstrip(" "))
        if spaces % 4:
            raise ValueError(f"rune indentation must be a multiple of four: {line!r}")
        text = line.strip()
        out.append({"text": text, "indent": spaces // 4,
                    "distractor": False, "note": notes.get(text, "")})
    seen = {r["text"] for r in out}
    for text, indent, note in distractors:
        if text in seen:
            # Two runes reading the same thing are not a distinction to learn, they
            # are a coin flip in the tray.
            raise ValueError(f"distractor duplicates a real rune: {text!r}")
        out.append({"text": text, "indent": indent, "distractor": True, "note": note})
    return out


def _seed(pid: str) -> int:
    """A stable per-problem shuffle. Runes that rearrange themselves between visits
    make the puzzle feel broken rather than hard."""
    return sum(ord(c) * (i + 1) for i, c in enumerate(pid)) % 100000


def _parsons(pid, title, tier, pattern, family, statement, fn, params, ref,
             canonical, visible, hidden, *, distractors, edges=(), notes=None,
             secondary=(), nudge="", pseudocode="", failures=(), realm="",
             time="O(n)", space="O(1)", after="", tags=(), preamble="",
             arg_adapters=(), cmp="exact", company="", source_type="GENERAL_INTERVIEW",
             provenance=""):
    """One rune-assembly encounter, validated the same way a code battle is.

    It is still a `code_problem` underneath: the canonical solution is run against
    the tests at build time, so a puzzle whose intended ordering does not work
    never reaches the corpus.
    """
    problem = code_problem(
        id=pid, title=title, realm=realm or REALM.get(pattern, "python_village"),
        pattern=pattern, difficulty=tier, family=family, profile_weight=Q, viz=VIZ,
        statement=statement, fn_name=fn, params=params, reference=ref,
        canonical=canonical, visible=visible, hidden=hidden, edges=edges,
        secondary=list(secondary), cmp=cmp,
        time_complexity=time, space_complexity=space,
        failures=list(failures), nudge=nudge, visual=VISUAL, pseudocode=pseudocode,
        encounter="RUNE_ASSEMBLY", prerequisites=[after] if after else [],
        preamble=preamble, arg_adapters=list(arg_adapters),
        source_type=source_type, company=company, provenance=provenance,
        tags=["parsons", "assembly"] + list(tags),
    )
    runes = _runes(canonical, distractors, notes or {})
    problem.mcq = {"runes": runes, "shuffle": shuffle_runes(runes, _seed(pid))}
    return problem


# --- reference implementations -----------------------------------------------
# Deliberately written a different way from the canonical solutions the runes are
# cut from. Two implementations agreeing is what earns a problem its place; two
# copies of the same implementation agreeing proves only that copying works.

def _r_sum_values(values): return sum(values)
def _r_count_evens(values): return len([v for v in values if v % 2 == 0])
def _r_largest(values): return max(values)
def _r_join_words(words): return " ".join(words)
def _r_letter_counts(text): return dict(Counter(text))
def _r_reverse_words(text): return " ".join(text.split()[::-1])
def _r_keep_long(words, least): return [w for w in words if len(w) >= least]
def _r_invert(mapping): return {v: k for k, v in mapping.items()}
def _r_digit_sum(n): return sum(int(c) for c in str(n))
def _r_count_vowels(text): return sum(1 for c in text.lower() if c in "aeiou")


def _r_first_repeat(values):
    for i, value in enumerate(values):
        if value in values[:i]:
            return value
    return None


def _r_average(values):
    return 0 if not values else sum(values) / float(len(values))


def _r_group_by_length(words):
    out = {}
    for size in sorted({len(w) for w in words}):
        out[size] = [w for w in words if len(w) == size]
    return out


def _r_running_totals(values):
    return [sum(values[:i + 1]) for i in range(len(values))]


def _r_most_common(words):
    pairs = Counter(words).most_common(1)
    return pairs[0][0] if pairs else None


def _r_dedupe(values): return list(dict.fromkeys(values))
def _r_transpose(grid): return [list(col) for col in zip(*grid)]


def _r_two_sum(nums, target):
    for j in range(len(nums)):
        for i in range(j):
            if nums[i] + nums[j] == target:
                return [i, j]
    return []


def _r_is_anagram(a, b): return sorted(a) == sorted(b)


def _r_max_window_sum(values, k):
    return max(sum(values[i:i + k]) for i in range(len(values) - k + 1))


def _r_longest_unique(text):
    best = 0
    for i in range(len(text)):
        for j in range(i, len(text)):
            piece = text[i:j + 1]
            if len(set(piece)) == len(piece):
                best = max(best, len(piece))
    return best


def _r_longest_k_distinct(text, k):
    best = 0
    for i in range(len(text)):
        for j in range(i, len(text)):
            piece = text[i:j + 1]
            if len(set(piece)) <= k:
                best = max(best, len(piece))
    return best


def _r_pair_sum_sorted(values, target):
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            if values[i] + values[j] == target:
                return [i, j]
    return []


def _r_is_palindrome(text): return text == text[::-1]


def _r_move_zeroes(values):
    kept = [v for v in values if v != 0]
    return kept + [0] * (len(values) - len(kept))


def _r_valid_parens(text):
    previous = None
    while previous != text:
        previous = text
        for pair in ("()", "[]", "{}"):
            text = text.replace(pair, "")
    return text == ""


def _r_next_warmer(temps):
    out = []
    for i, t in enumerate(temps):
        wait = 0
        for j in range(i + 1, len(temps)):
            if temps[j] > t:
                wait = j - i
                break
        out.append(wait)
    return out


def _r_eval_rpn(tokens):
    stack = []
    for token in tokens:
        if token == "+":
            stack.append(stack.pop(-2) + stack.pop())
        elif token == "-":
            stack.append(stack.pop(-2) - stack.pop())
        elif token == "*":
            stack.append(stack.pop(-2) * stack.pop())
        else:
            stack.append(int(token))
    return stack[0]


def _r_window_max(values, k):
    return [max(values[i:i + k]) for i in range(len(values) - k + 1)]


def _r_shortest_hops(graph, start, goal):
    frontier, seen, dist = [start], {start}, 0
    while frontier:
        if goal in frontier:
            return dist
        nxt = []
        for node in frontier:
            for other in graph[node]:
                if other not in seen:
                    seen.add(other)
                    nxt.append(other)
        frontier, dist = nxt, dist + 1
    return -1


def _r_reachable(graph, start):
    seen = set()

    def walk(node):
        if node in seen:
            return
        seen.add(node)
        for other in graph[node]:
            walk(other)

    walk(start)
    return sorted(seen)


def _r_max_depth(root):
    depth, level = 0, [root] if root else []
    while level:
        depth += 1
        level = [c for n in level for c in (n.left, n.right) if c]
    return depth


def _r_tree_sum(root):
    total, stack = 0, [root] if root else []
    while stack:
        node = stack.pop()
        total += node.val
        stack.extend(c for c in (node.left, node.right) if c)
    return total


def _r_level_values(root):
    out, level = [], [root] if root else []
    while level:
        out.extend(n.val for n in level)
        level = [c for n in level for c in (n.left, n.right) if c]
    return out


def _r_binary_search(values, target):
    return values.index(target) if target in values else -1


def _r_first_ge(values, target): return bisect.bisect_left(values, target)


def _r_count_subarrays(values, k):
    found = 0
    for i in range(len(values)):
        for j in range(i, len(values)):
            if sum(values[i:j + 1]) == k:
                found += 1
    return found


def _r_climb(n):
    memo = {}

    def ways(rungs):
        if rungs <= 2:
            return max(rungs, 0)
        if rungs not in memo:
            memo[rungs] = ways(rungs - 1) + ways(rungs - 2)
        return memo[rungs]

    return ways(n)


def _r_rob(values):
    memo = {}

    def best(i):
        if i >= len(values):
            return 0
        if i not in memo:
            memo[i] = max(values[i] + best(i + 2), best(i + 1))
        return memo[i]

    return best(0)


def _r_paths(rows, cols): return math.comb(rows + cols - 2, rows - 1)


def build() -> list:
    P: list = []

    # ---------------------------------------------------------------- fluency
    # Chapter I-III. Nothing here is an interview pattern. These exist so that
    # "loop, condition, accumulate" becomes a shape he can see rather than a
    # sentence he has to reconstruct.

    P.append(_parsons(
        "pa-sum-values", "Adding Them Up", "GUIDED", "ARRAY", "onboarding_loops",
        """
        Return the total of every number in `values`. The list may be empty, in
        which case the total is `0`. sum_values([2, 5, 1]) gives 8.

        This is the accumulator: one variable outside the loop, changed once per
        item inside it.
        """,
        "sum_values", "values", _r_sum_values,
        """
        def sum_values(values):
            total = 0
            for value in values:
                total += value
            return total
        """,
        [("three numbers", [[2, 5, 1]]), ("negatives", [[-4, 4, -1]])],
        [("single", [[7]]), ("zeros", [[0, 0, 0]])],
        edges=[("empty", [[]])],
        notes={"total = 0": "The accumulator is created once, before the loop. "
                            "Inside it, the running total would restart every step.",
               "return total": "Outside the loop. A return inside it would hand back "
                               "the first value and stop."},
        distractors=[
            ("total = values[0]", 1,
             "Seeding with the first value counts it twice, and raises IndexError "
             "the moment the list is empty."),
            ("values.sort()", 1,
             "A total does not care what order the numbers arrive in. This costs "
             "O(n log n) and buys nothing."),
        ],
        nudge="One variable holds the answer as it grows. Where does it have to be "
              "born so that the loop can keep adding to it?",
        pseudocode="total = 0\nfor each value: total = total + value\nreturn total",
        failures=["Resetting the accumulator inside the loop",
                  "Returning from inside the loop after the first item"],
        time="O(n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-count-evens", "Only the Even Ones", "GUIDED", "ARRAY",
        "onboarding_conditionals",
        """
        Return how many numbers in `values` are even. A number is even when
        dividing it by two leaves no remainder. count_evens([1, 2, 4, 7]) gives 2.

        The shape here is loop, then condition, then accumulate — three depths.
        """,
        "count_evens", "values", _r_count_evens,
        """
        def count_evens(values):
            count = 0
            for value in values:
                if value % 2 == 0:
                    count += 1
            return count
        """,
        [("mixed", [[1, 2, 4, 7]]), ("all odd", [[1, 3, 5]])],
        [("all even", [[2, 4, 6, 8]]), ("with zero", [[0, 1, 2]])],
        edges=[("empty", [[]])],
        notes={"count += 1": "Depth three: inside the loop AND inside the condition. "
                             "One level left and it counts everything."},
        distractors=[
            ("if value % 2 == 1:", 2,
             "That counts the odd ones. `% 2` is 0 for even numbers and 1 for odd."),
            ("count += value", 3,
             "That totals the even numbers instead of counting them. How many, not "
             "how much."),
        ],
        after="pa-sum-values",
        nudge="Two runes have to sit deeper than the loop body: the test, and the "
              "thing the test guards.",
        pseudocode="count = 0\nfor each value:\n  if value is even: count = count + 1\nreturn count",
        failures=["Putting the increment at loop depth so every item counts"],
        time="O(n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-largest", "The Largest Rune", "GUIDED", "ARRAY", "onboarding_loops",
        """
        Return the biggest number in `values`, which always holds at least one
        number. largest([3, 9, 2]) gives 9, and largest([-5, -2]) gives -2.

        Hold the best seen so far and replace it whenever something beats it.
        """,
        "largest", "values", _r_largest,
        """
        def largest(values):
            best = values[0]
            for value in values:
                if value > best:
                    best = value
            return best
        """,
        [("mixed", [[3, 9, 2]]), ("all negative", [[-5, -2, -9]])],
        [("last is biggest", [[1, 2, 3]]), ("first is biggest", [[9, 1, 1]])],
        edges=[("single", [[4]])],
        notes={"best = values[0]": "Seeding from the data itself is what makes this "
                                   "work on negatives."},
        distractors=[
            ("best = 0", 1,
             "Zero is not a safe starting point: on a list of negatives it is larger "
             "than every candidate and never gets replaced."),
            ("if value < best:", 2,
             "Read the comparison out loud. That one finds the smallest."),
        ],
        after="pa-count-evens",
        nudge="What is the safest possible first guess at the answer? It is already "
              "in the list.",
        pseudocode="best = first value\nfor each value: if bigger, best = value\nreturn best",
        failures=["Starting at 0 and breaking on all-negative input"],
        time="O(n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-join-words", "Building the Sentence", "GUIDED", "STRING",
        "onboarding_strings",
        """
        Join the words into one string with a single space between them, and no
        space on either end. join_words(["salt", "and", "iron"]) gives
        "salt and iron". An empty list gives "".

        Build it by accumulating, then trim what the accumulation left behind.
        """,
        "join_words", "words", _r_join_words,
        """
        def join_words(words):
            out = ""
            for word in words:
                out += word + " "
            return out.strip()
        """,
        [("three words", [["salt", "and", "iron"]]), ("one word", [["alone"]])],
        [("two words", [["cold", "open"]]), ("short words", [["a", "b", "c"]])],
        edges=[("empty", [[]])],
        notes={"return out.strip()": "The loop leaves one trailing space every time. "
                                     "Trimming at the end is cheaper than special-casing "
                                     "the last word inside the loop."},
        distractors=[
            ("out = []", 1,
             "A list would want `.append` and a `join` at the end. This spell "
             "accumulates the string directly, so it needs a string to start from."),
            ("out += word", 2,
             "Without the space the words run together into one long rope."),
        ],
        after="pa-largest",
        nudge="Adding the separator after every word is the easy way. Dealing with "
              "the one you added too many is the last line.",
        pseudocode='out = ""\nfor each word: out = out + word + " "\nreturn out with the ends trimmed',
        failures=["Leaving the trailing space on the result"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-letter-counts", "Tally of Letters", "GUIDED", "HASH_MAP", "counting",
        """
        Return a dict mapping each character in `text` to the number of times it
        appears. letter_counts("bomb") gives {"b": 2, "o": 1, "m": 1}.

        This is the counting idiom, and it is the single most reused four lines in
        the whole corpus.
        """,
        "letter_counts", "text", _r_letter_counts,
        """
        def letter_counts(text):
            counts = {}
            for ch in text:
                counts[ch] = counts.get(ch, 0) + 1
            return counts
        """,
        [("repeats", ["bomb"]), ("all distinct", ["abc"])],
        [("one letter", ["z"]), ("with spaces", ["a a"])],
        edges=[("empty", [""])],
        notes={"counts[ch] = counts.get(ch, 0) + 1":
               "`.get(ch, 0)` is what makes the first sighting of a character work. "
               "Read it as: whatever was there, or nothing, plus one."},
        distractors=[
            ("counts[ch] = counts[ch] + 1", 2,
             "A key that does not exist yet raises KeyError. `.get` supplies the "
             "missing zero; plain indexing does not."),
            ("counts = []", 1,
             "A list is indexed by position. You need to index by character."),
        ],
        after="pa-join-words",
        nudge="The first time you see a character there is nothing to add to. "
              "One rune solves that.",
        pseudocode="counts = empty dict\nfor each character: counts[ch] = old count or 0, plus 1\nreturn counts",
        failures=["KeyError on the first sighting of a character"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-reverse-words", "The Sentence Backwards", "GUIDED", "STRING",
        "onboarding_strings",
        """
        Return `text` with its words in the opposite order, single-spaced.
        reverse_words("iron and salt") gives "salt and iron". The words themselves
        keep their spelling.

        Three moves: split, reverse, rejoin.
        """,
        "reverse_words", "text", _r_reverse_words,
        """
        def reverse_words(text):
            words = text.split()
            words.reverse()
            return " ".join(words)
        """,
        [("three words", ["iron and salt"]), ("two words", ["cold open"])],
        [("one word", ["alone"]), ("extra spaces", ["  a   b  "])],
        edges=[("empty", [""])],
        notes={"words.reverse()": "`.reverse()` rearranges the list in place and "
                                  "returns None, which is why it is a statement and "
                                  "not part of the return line."},
        distractors=[
            ("return text[::-1]", 1,
             "That reverses the characters, so every word comes out spelled "
             "backwards too. Right tool, wrong level."),
            ("words.sort()", 1,
             "Alphabetical order is not reverse order. They coincide only by "
             "accident."),
        ],
        after="pa-letter-counts",
        nudge="`.split()` with no argument already collapses runs of whitespace. "
              "You do not have to handle that yourself.",
        pseudocode='words = text.split()\nreverse the list\nreturn the words joined by a space',
        failures=["Reversing the characters instead of the words"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-keep-long", "Only the Long Ones", "GUIDED", "ARRAY", "onboarding_loops",
        """
        Return the words that are at least `least` characters long, in the order
        they appeared. keep_long(["ok", "fine", "no"], 3) gives ["fine"].

        Collecting under a condition — the same three depths as counting, with a
        list instead of a number.
        """,
        "keep_long", "words, least", _r_keep_long,
        """
        def keep_long(words, least):
            out = []
            for word in words:
                if len(word) >= least:
                    out.append(word)
            return out
        """,
        [("one survivor", [["ok", "fine", "no"], 3]),
         ("all survive", [["alpha", "bravo"], 2])],
        [("none survive", [["a", "b"], 5]),
         ("exact length", [["abc", "ab"], 3])],
        edges=[("empty", [[], 2])],
        notes={"out = []": "The collector is born before the loop, like any other "
                           "accumulator."},
        distractors=[
            ("if len(word) > least:", 2,
             "`>` drops the words that are exactly `least` long. The spec says at "
             "least, which includes equal."),
            ("out.append(len(word))", 3,
             "That collects the lengths. The question asks for the words."),
        ],
        after="pa-reverse-words",
        nudge="At least means the boundary is included. One character of the "
              "comparison decides that.",
        pseudocode="out = []\nfor each word:\n  if it is long enough: keep it\nreturn out",
        failures=["Using > and losing the exactly-long-enough words"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-invert-dict", "Turning the Ledger Over", "GUIDED", "HASH_MAP",
        "frequency",
        """
        Return a new dict with the keys and values swapped. invert({"a": 1,
        "b": 2}) gives {1: "a", 2: "b"}. Values in the input are unique, so
        nothing collides.

        Iterating a dict hands you keys, not pairs — that is the rune to watch.
        """,
        "invert", "mapping", _r_invert,
        """
        def invert(mapping):
            out = {}
            for key in mapping:
                value = mapping[key]
                out[value] = key
            return out
        """,
        [("two entries", [{"a": 1, "b": 2}]), ("one entry", [{"x": 9}])],
        [("string values", [{"a": "b"}]), ("three entries", [{"a": 1, "b": 2, "c": 3}])],
        edges=[("empty", [{}])],
        notes={"for key in mapping:": "Looping a dict directly yields its keys. "
                                      "`.items()` would yield pairs, and then this "
                                      "spell would need one rune fewer."},
        distractors=[
            ("out[key] = value", 3,
             "That copies the ledger unchanged. The whole point is the swap."),
            ("for key, value in mapping:", 1,
             "Unpacking two names from a plain dict loop fails: each item is a "
             "single key. `.items()` is what yields pairs."),
        ],
        after="pa-keep-long",
        nudge="You need both halves of each entry, but the loop only gives you one "
              "of them directly.",
        pseudocode="out = {}\nfor each key: look up its value, store value -> key\nreturn out",
        failures=["Trying to unpack a pair from a bare dict loop"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-digit-sum", "Casting Down the Digits", "GUIDED", "SIMULATION",
        "python_basics",
        """
        Return the sum of the decimal digits of the non-negative integer `n`.
        digit_sum(472) gives 13. digit_sum(0) gives 0.

        Peel one digit at a time off the right-hand end. `% 10` reads it, `// 10`
        removes it.
        """,
        "digit_sum", "n", _r_digit_sum,
        """
        def digit_sum(n):
            total = 0
            while n > 0:
                total += n % 10
                n = n // 10
            return total
        """,
        [("three digits", [472]), ("two digits", [19])],
        [("single digit", [7]), ("trailing zeros", [100])],
        edges=[("zero", [0])],
        notes={"n = n // 10": "Integer division is what shortens the number. Without "
                              "this rune the loop never ends."},
        distractors=[
            ("n = n - 10", 3,
             "Subtracting ten does not remove a digit. 472 would take forty-seven "
             "trips to get anywhere near zero, and the digits would be wrong."),
            ("total += n % 2", 3,
             "`% 2` reads parity. `% 10` reads the last digit. The modulus is the "
             "base you are working in."),
        ],
        after="pa-invert-dict",
        nudge="A while loop needs something that changes, or it does not stop. Which "
              "rune is the one that shrinks `n`?",
        pseudocode="total = 0\nwhile n > 0:\n  add the last digit\n  drop the last digit\nreturn total",
        failures=["Forgetting the shrink and hanging forever"],
        time="O(log n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-first-repeat", "The First Familiar Face", "TUTORIAL", "SET", "dedupe",
        """
        Return the first value in `values` that has already been seen earlier in
        the list, or `None` if every value is distinct. first_repeat([4, 1, 4, 1])
        gives 4, because the second 4 arrives before the second 1.

        A set remembers what you have met. Membership in it costs nothing.
        """,
        "first_repeat", "values", _r_first_repeat,
        """
        def first_repeat(values):
            seen = set()
            for value in values:
                if value in seen:
                    return value
                seen.add(value)
            return None
        """,
        [("repeat", [[4, 1, 4, 1]]), ("no repeat", [[1, 2, 3]])],
        [("immediate", [[5, 5]]), ("late repeat", [[1, 2, 3, 1]])],
        edges=[("empty", [[]])],
        notes={"return None": "Reached only when the loop finishes, which means "
                              "nothing repeated. It has to sit at function depth."},
        distractors=[
            ("seen = []", 1,
             "A list would give the right answer and the wrong cost: `in` on a list "
             "walks it, turning a linear scan quadratic."),
            ("seen.append(value)", 2,
             "`.append` belongs to lists. A set grows with `.add`."),
            ("values.sort()", 1,
             "Sorting brings the duplicates together and destroys the arrival order "
             "that decides which one is first."),
        ],
        after="pa-digit-sum",
        nudge="Ask the question before you record the answer. The order of those two "
              "runes is the whole puzzle.",
        pseudocode="seen = set()\nfor each value:\n  if already seen: return it\n  record it\nreturn None",
        failures=["Recording the value before testing it, which reports the first "
                  "value as its own repeat"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-average", "The Mean of It", "TUTORIAL", "ARRAY", "onboarding_loops",
        """
        Return the arithmetic mean of `values` as a float, or `0` when the list is
        empty. average([2, 4, 9]) gives 5.0.

        Guard the empty case first, or the division at the end divides by zero.
        """,
        "average", "values", _r_average,
        """
        def average(values):
            if not values:
                return 0
            total = 0
            for value in values:
                total += value
            return total / len(values)
        """,
        [("three numbers", [[2, 4, 9]]), ("two numbers", [[1, 2]])],
        [("single", [[6]]), ("negatives", [[-2, 2]])],
        edges=[("empty", [[]])],
        cmp="float",
        notes={"if not values:": "The guard has to come before anything that assumes "
                                 "there is data."},
        distractors=[
            ("return total // len(values)", 1,
             "Floor division throws the fraction away. The mean of 1 and 2 is 1.5, "
             "not 1."),
            ("total = values[0]", 1,
             "Seeding with the first value counts it twice and skews every answer."),
        ],
        after="pa-first-repeat",
        nudge="Two runes are about protecting the last line. Put them where they can "
              "actually protect it.",
        pseudocode="if the list is empty: return 0\nsum it\nreturn sum divided by how many",
        failures=["ZeroDivisionError on the empty list",
                  "Integer division truncating the answer"],
        time="O(n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-count-vowels", "Counting the Vowels", "TUTORIAL", "STRING",
        "onboarding_strings",
        """
        Return how many vowels are in `text`, counting both cases. The vowels are
        a, e, i, o and u. count_vowels("Obsidian") gives 4.

        Fold the case once, at the top of the loop, rather than testing for ten
        characters instead of five.
        """,
        "count_vowels", "text", _r_count_vowels,
        """
        def count_vowels(text):
            vowels = "aeiou"
            count = 0
            for ch in text.lower():
                if ch in vowels:
                    count += 1
            return count
        """,
        [("mixed case", ["Obsidian"]), ("no vowels", ["rhythm"])],
        [("all vowels", ["aeiou"]), ("shouting", ["LOUD"])],
        edges=[("empty", [""])],
        notes={"for ch in text.lower():": "Lowering once here beats lowering every "
                                          "character inside the test."},
        distractors=[
            ("for ch in text:", 1,
             "Without the case fold, every capital vowel is missed."),
            ("if ch == vowels:", 2,
             "Equality asks whether one character is the whole five-letter string. "
             "`in` is the membership test you want."),
            ("count += ch", 3,
             "You cannot add a character to a number. This one raises TypeError."),
        ],
        after="pa-average",
        nudge="`in` works on a string the same way it works on a list. That is why "
              "the vowel rune can be one short string.",
        pseudocode='vowels = "aeiou"\ncount = 0\nfor each lowered character:\n  if it is a vowel: count it\nreturn count',
        failures=["Missing capital vowels entirely"],
        time="O(n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-running-totals", "The Trail of Totals", "TUTORIAL", "PREFIX_SUM",
        "prefix_sum",
        """
        Return a list where entry `i` is the sum of everything up to and including
        position `i`. running_totals([2, 3, 5]) gives [2, 5, 10].

        This is the prefix sum, built once in a single pass. Every window question
        later leans on it.
        """,
        "running_totals", "values", _r_running_totals,
        """
        def running_totals(values):
            out = []
            total = 0
            for value in values:
                total += value
                out.append(total)
            return out
        """,
        [("ascending", [[2, 3, 5]]), ("with negatives", [[5, -2, 1]])],
        [("single", [[4]]), ("zeros", [[0, 0, 1]])],
        edges=[("empty", [[]])],
        notes={"out.append(total)": "Record after adding, so entry i includes value i."},
        distractors=[
            ("out = [0]", 1,
             "Seeding with a zero makes the output one entry longer than the input. "
             "That variant is useful for subarray sums, and wrong here."),
            ("out.append(value)", 3,
             "That copies the input back out. The running total is the point."),
        ],
        after="pa-count-vowels",
        nudge="Two things happen per item, and their order decides whether entry i "
              "includes item i.",
        pseudocode="out = []\ntotal = 0\nfor each value:\n  add it to total\n  append total\nreturn out",
        failures=["Appending before accumulating, which shifts every entry"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-group-by-length", "Sorting the Stones by Size", "TUTORIAL", "HASH_MAP",
        "counting",
        """
        Group the words by their length. Return a dict mapping each length to the
        list of words of that length, in the order they appeared.
        group_by_length(["ox", "cat", "ant"]) gives {2: ["ox"], 3: ["cat", "ant"]}.

        The bucket has to exist before anything can be dropped into it.
        """,
        "group_by_length", "words", _r_group_by_length,
        """
        def group_by_length(words):
            groups = {}
            for word in words:
                size = len(word)
                if size not in groups:
                    groups[size] = []
                groups[size].append(word)
            return groups
        """,
        [("two sizes", [["ox", "cat", "ant"]]), ("one size", [["aa", "bb"]])],
        [("all different", [["a", "bb", "ccc"]]), ("single", [["solo"]])],
        edges=[("empty", [[]])],
        notes={"if size not in groups:": "Create the bucket, then fill it. "
                                         "`defaultdict(list)` exists to collapse "
                                         "these two runes into none."},
        distractors=[
            ("groups[size] = word", 3,
             "Assigning replaces the bucket with a single word. The bucket has to "
             "grow, which means `.append`."),
            ("groups = []", 1,
             "A list is indexed by position; word lengths are not positions, and "
             "there is no position 3 in an empty list."),
        ],
        after="pa-running-totals",
        nudge="Two runes handle the missing bucket. One tests, one creates. Both sit "
              "above the rune that fills it.",
        pseudocode="groups = {}\nfor each word:\n  size = its length\n  if no bucket yet: make one\n  append into the bucket\nreturn groups",
        failures=["KeyError when the first word of a new length arrives",
                  "Overwriting the bucket instead of appending to it"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-dedupe-order", "Keeping the First of Each", "TUTORIAL", "SET", "dedupe",
        """
        Return the values with duplicates removed, keeping the first appearance of
        each and the original order. dedupe([3, 1, 3, 2, 1]) gives [3, 1, 2].

        Two structures, doing two different jobs: the set decides, the list
        remembers.
        """,
        "dedupe", "values", _r_dedupe,
        """
        def dedupe(values):
            seen = set()
            out = []
            for value in values:
                if value not in seen:
                    seen.add(value)
                    out.append(value)
            return out
        """,
        [("repeats", [[3, 1, 3, 2, 1]]), ("no repeats", [[1, 2, 3]])],
        [("all same", [[7, 7, 7]]), ("strings", [["a", "b", "a"]])],
        edges=[("empty", [[]])],
        notes={"out = []": "The set cannot be the answer: sets have no order, and "
                           "order is half the spec."},
        distractors=[
            ("return sorted(set(values))", 1,
             "One line, right answer to a different question: `set` drops the "
             "duplicates and the order along with them."),
            ("if value in seen:", 3,
             "Inverted. That keeps only the repeats and drops every first sighting."),
        ],
        after="pa-group-by-length",
        nudge="Why is there both a set and a list? Because one of them answers "
              "'have I met you' and the other answers 'in what order'.",
        pseudocode="seen = set()\nout = []\nfor each value:\n  if new: record it and keep it\nreturn out",
        failures=["Returning the set and losing the order"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-most-common", "The Loudest Voice", "TUTORIAL", "HASH_MAP", "frequency",
        """
        Return the word that appears most often in `words`, or `None` for an empty
        list. most_common(["ash", "ash", "ember"]) gives "ash". No test has a tie.

        Two passes: count everything, then find the maximum of the counts.
        """,
        "most_common", "words", _r_most_common,
        """
        def most_common(words):
            counts = {}
            for word in words:
                counts[word] = counts.get(word, 0) + 1
            best = None
            for word in counts:
                if best is None or counts[word] > counts[best]:
                    best = word
            return best
        """,
        [("clear winner", [["ash", "ash", "ember"]]), ("single", [["solo"]])],
        [("late winner", [["a", "b", "b", "b"]]), ("two words", [["x", "x", "y"]])],
        edges=[("empty", [[]])],
        notes={"best = None": "Between the two loops. Above the first, it would be "
                              "pointless; inside the second, it would reset."},
        distractors=[
            ("counts[word] += 1", 2,
             "KeyError on the first sighting. `.get(word, 0)` is what makes the "
             "first one work."),
            ("if counts[word] > best:", 2,
             "`best` holds a word, not a count. That comparison compares a string "
             "with a number."),
        ],
        after="pa-dedupe-order",
        nudge="The second loop walks the counts, not the words. Only one of those "
              "has each word exactly once.",
        pseudocode="count every word\nbest = None\nfor each counted word:\n  if it beats best, it becomes best\nreturn best",
        failures=["Comparing a word against a count",
                  "Initialising `best` inside the scanning loop"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-transpose", "Turning the Map", "TUTORIAL", "MATRIX", "matrix_transform",
        """
        Return the transpose of `grid`: row `i` of the answer is column `i` of the
        input. transpose([[1, 2, 3], [4, 5, 6]]) gives [[1, 4], [2, 5], [3, 6]].
        Every row has the same length.

        The outer loop walks columns, which is the reversal that makes this work.
        """,
        "transpose", "grid", _r_transpose,
        """
        def transpose(grid):
            rows = len(grid)
            cols = len(grid[0])
            out = []
            for c in range(cols):
                row = []
                for r in range(rows):
                    row.append(grid[r][c])
                out.append(row)
            return out
        """,
        [("wide", [[[1, 2, 3], [4, 5, 6]]]), ("square", [[[1, 2], [3, 4]]])],
        [("tall", [[[1], [2], [3]]]), ("single row", [[[7, 8]]])],
        edges=[("one cell", [[[9]]])],
        notes={"out.append(row)": "Once per column, after the inner loop has "
                                  "finished filling it."},
        distractors=[
            ("row.append(grid[c][r])", 3,
             "The indices are swapped. On anything that is not square, this reads "
             "off the end of the grid."),
            ("for r in range(cols):", 2,
             "The inner loop walks rows, so it must be bounded by the row count. "
             "Bounds that follow the wrong dimension are the classic matrix bug."),
        ],
        after="pa-most-common",
        nudge="Which loop has to be on the outside for the answer's rows to come out "
              "as the input's columns?",
        pseudocode="for each column c:\n  row = []\n  for each row r: take grid[r][c]\n  append row\nreturn out",
        failures=["Swapping r and c inside the index",
                  "Appending the inner row at the wrong depth"],
        time="O(rows * cols)", space="O(rows * cols)",
    ))

    # ------------------------------------------------------- interview patterns
    # Chapter IV onward. Same interaction, real patterns. Assembling `two_sum`
    # before writing it means the shape is already familiar when the blank screen
    # arrives, and the SRS family is shared so both count as the same rehearsal.

    P.append(_parsons(
        "pa-two-sum", "The Pair That Sums", "EASY", "HASH_MAP", "two_sum",
        """
        Return the indices of the two numbers in `nums` that add to `target`, as
        [earlier, later]. two_sum([2, 7, 11], 9) gives [0, 1]. Exactly one pair
        works, and no number is used twice.

        One pass. For each number, ask whether the number it needs has already
        gone past.
        """,
        "two_sum", "nums, target", _r_two_sum,
        """
        def two_sum(nums, target):
            seen = {}
            for i in range(len(nums)):
                need = target - nums[i]
                if need in seen:
                    return [seen[need], i]
                seen[nums[i]] = i
            return []
        """,
        [("classic", [[2, 7, 11], 9]), ("at the end", [[1, 4, 6, 3], 9])],
        [("negatives", [[-3, 4, 1], 1]), ("two elements", [[5, 5], 10])],
        edges=[("no pair", [[1, 2], 50])],
        secondary=["ARRAY"], source_type="COMPANY_PATTERN",
        provenance="Hash-map complement lookup is the most widely reported "
                   "opening-round archetype there is.",
        notes={"need = target - nums[i]": "The complement. Everything else in this "
                                          "spell is bookkeeping around this one line.",
               "seen[nums[i]] = i": "Recorded after the check, so a number cannot "
                                    "pair with itself."},
        distractors=[
            ("need = nums[i] - target", 2,
             "Backwards. You want the complement — target minus this value — not "
             "this value minus the target."),
            ("nums.sort()", 1,
             "Sorting destroys the indices, and the indices are the answer."),
            ("if nums[i] in seen:", 2,
             "That asks whether this value has been seen before. The question is "
             "whether its partner has."),
        ],
        nudge="You are storing value -> index, and looking up by value. Which rune "
              "does which?",
        pseudocode="seen = {}\nfor each index i:\n  need = target - nums[i]\n  if need is on record: return both indices\n  record nums[i] -> i\nreturn []",
        failures=["Recording before checking, so a number pairs with itself",
                  "Returning the values instead of the indices"],
        time="O(n)", space="O(n)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-is-anagram", "Same Letters, Different Order", "EASY", "HASH_MAP",
        "anagrams",
        """
        Return True when `a` and `b` use exactly the same letters the same number
        of times. is_anagram("listen", "silent") is True; is_anagram("ab", "aa")
        is False.

        Count the first string up, then spend those counts down with the second.
        """,
        "is_anagram", "a, b", _r_is_anagram,
        """
        def is_anagram(a, b):
            if len(a) != len(b):
                return False
            counts = {}
            for ch in a:
                counts[ch] = counts.get(ch, 0) + 1
            for ch in b:
                if counts.get(ch, 0) == 0:
                    return False
                counts[ch] -= 1
            return True
        """,
        [("anagram", ["listen", "silent"]), ("not an anagram", ["ab", "aa"])],
        [("different lengths", ["abc", "ab"]), ("same string", ["mm", "mm"])],
        edges=[("both empty", ["", ""])],
        secondary=["STRING"],
        notes={"if len(a) != len(b):": "The cheap rejection, first. It also makes "
                                       "the count-down logic sufficient on its own.",
               "counts[ch] -= 1": "Spending the count is what catches a letter used "
                                  "more times in `b` than in `a`."},
        distractors=[
            ("counts[ch] += 1", 2,
             "KeyError on a letter's first appearance. `.get(ch, 0)` is the rune "
             "that survives it."),
            ("if len(a) == len(b):", 1,
             "Inverted guard: this returns False for every genuine anagram and True "
             "for nothing."),
            ("return sorted(a) == sorted(b)", 1,
             "Correct, and a different spell — O(n log n) instead of O(n), and it "
             "would make every other rune here unreachable."),
        ],
        nudge="After the second loop finishes without complaint, is there anything "
              "left to check? The length guard already answered that.",
        pseudocode="if lengths differ: False\ncount letters of a\nfor each letter of b:\n  if none left: False\n  spend one\nreturn True",
        failures=["Skipping the length guard and accepting a prefix",
                  "KeyError on a letter that only appears in b"],
        time="O(n)", space="O(n)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-max-window-sum", "The Richest Stretch", "EASY", "SLIDING_WINDOW",
        "fixed_window",
        """
        Return the largest sum of any `k` consecutive values. `k` is at least 1 and
        never longer than the list. max_window_sum([1, 9, 2, 4], 2) gives 11, from
        the 9 and the 2.

        Slide instead of recomputing: add the arriving value, subtract the leaving
        one.
        """,
        "max_window_sum", "values, k", _r_max_window_sum,
        """
        def max_window_sum(values, k):
            window = sum(values[:k])
            best = window
            for i in range(k, len(values)):
                window += values[i]
                window -= values[i - k]
                if window > best:
                    best = window
            return best
        """,
        [("pair", [[1, 9, 2, 4], 2]), ("triple", [[3, 1, 2, 8, 1], 3])],
        [("whole list", [[4, 5], 2]), ("negatives", [[-5, -1, -9], 2])],
        edges=[("single width", [[7, 2], 1])],
        secondary=["ARRAY"],
        notes={"window = sum(values[:k])": "The first window is built the expensive "
                                           "way, exactly once.",
               "window -= values[i - k]": "The value leaving sits k places behind "
                                          "the one arriving."},
        distractors=[
            ("window -= values[i - k + 1]", 2,
             "Off by one: that subtracts a value still inside the window and leaves "
             "the departed one in the total."),
            ("for i in range(len(values)):", 1,
             "Starting at zero re-adds the values the first window already holds."),
            ("best = 0", 1,
             "Zero is not a valid starting best when every value is negative."),
        ],
        nudge="The loop starts where the first window ends, not at the beginning.",
        pseudocode="window = sum of the first k\nbest = window\nfor i from k onward:\n  add values[i], drop values[i-k]\n  best = max(best, window)\nreturn best",
        failures=["Recomputing the whole window sum each step, which is O(n*k)",
                  "Off-by-one on the index leaving the window"],
        time="O(n)", space="O(1)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-longest-unique", "The Longest Clean Run", "EASY", "SLIDING_WINDOW",
        "window_distinct",
        """
        Return the length of the longest stretch of `text` with no repeated
        character. longest_unique("abcabcbb") gives 3, for "abc".

        The window's left edge only ever moves forward, and it jumps to just past
        the previous sighting of the offending character.
        """,
        "longest_unique", "text", _r_longest_unique,
        """
        def longest_unique(text):
            seen = {}
            left = 0
            best = 0
            for right in range(len(text)):
                ch = text[right]
                if ch in seen and seen[ch] >= left:
                    left = seen[ch] + 1
                seen[ch] = right
                if right - left + 1 > best:
                    best = right - left + 1
            return best
        """,
        [("classic", ["abcabcbb"]), ("all same", ["bbbb"])],
        [("all distinct", ["abcdef"]), ("repeat far back", ["abba"])],
        edges=[("empty", [""])],
        secondary=["HASH_MAP", "STRING"],
        notes={"if ch in seen and seen[ch] >= left:":
               "The second half matters: a duplicate that fell out of the window "
               "long ago must not drag the left edge backwards.",
               "seen[ch] = right": "Always recorded, duplicate or not."},
        distractors=[
            ("left = seen[ch]", 2,
             "Moving to the duplicate keeps the duplicate inside the window. Step "
             "one past it."),
            ("if right - left > best:", 2,
             "A window from left to right holds right - left + 1 characters. This "
             "undercounts every answer by one."),
            ("seen = set()", 1,
             "A set remembers that a character appeared but not where. The left "
             "edge has to jump to a position, so the record must be a dict."),
        ],
        nudge="Why is `seen[ch] >= left` there at all? Try 'abba' without it and "
              "watch the left edge walk backwards.",
        pseudocode="for each right:\n  if this char was seen inside the window: left = that + 1\n  record its position\n  best = max(best, window width)\nreturn best",
        failures=["Letting the left edge move backwards on an old duplicate",
                  "Off-by-one in the window width"],
        time="O(n)", space="O(n)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-k-distinct", "At Most K Kinds", "EASY", "SLIDING_WINDOW",
        "window_k_distinct",
        """
        Return the length of the longest stretch of `text` containing at most `k`
        distinct characters. longest_k_distinct("eceba", 2) gives 3, for "ece".
        A `k` of 0 gives 0.

        Grow on the right always; shrink from the left only while the window
        breaks the rule.
        """,
        "longest_k_distinct", "text, k", _r_longest_k_distinct,
        """
        def longest_k_distinct(text, k):
            counts = {}
            left = 0
            best = 0
            for right in range(len(text)):
                ch = text[right]
                counts[ch] = counts.get(ch, 0) + 1
                while len(counts) > k:
                    gone = text[left]
                    counts[gone] -= 1
                    if counts[gone] == 0:
                        del counts[gone]
                    left += 1
                if right - left + 1 > best:
                    best = right - left + 1
            return best
        """,
        [("two kinds", ["eceba", 2]), ("one kind", ["aabbcc", 1])],
        [("k covers everything", ["abc", 5]), ("all identical", ["aaaa", 1])],
        edges=[("k is zero", ["ab", 0])],
        secondary=["HASH_MAP", "STRING"],
        notes={"del counts[gone]": "Deleting at zero is what keeps `len(counts)` "
                                   "honest. A key sitting at zero still counts as a "
                                   "kind.",
               "left += 1": "The last rune of the shrink, after the character has "
                            "been accounted for."},
        distractors=[
            ("counts.pop(gone)", 4,
             "Popping unconditionally evicts a character that still has copies "
             "inside the window."),
            ("left = right", 3,
             "Jumping the left edge all the way throws away characters that were "
             "still perfectly valid."),
            ("while len(counts) >= k:", 2,
             "Off by one on the constraint: at most k means k is allowed. This "
             "shrinks a window that was already legal."),
        ],
        nudge="The dict has to shrink as well as grow, or the count of distinct "
              "kinds never comes back down.",
        pseudocode="for each right:\n  add the character\n  while too many kinds: drop one from the left\n  best = max(best, window width)\nreturn best",
        failures=["Leaving zero-count keys in the dict",
                  "Using >= on the constraint and shrinking a legal window"],
        time="O(n)", space="O(k)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-pair-sorted", "Two Ends Closing", "EASY", "TWO_POINTER", "sorted_pair",
        """
        `values` is sorted ascending. Return the indices of the one pair that adds
        to `target`, as [left, right], or [] when no pair does.
        pair_sum_sorted([1, 3, 4, 8], 7) gives [1, 2].

        Sorted input means the sum tells you which end to move.
        """,
        "pair_sum_sorted", "values, target", _r_pair_sum_sorted,
        """
        def pair_sum_sorted(values, target):
            left = 0
            right = len(values) - 1
            while left < right:
                total = values[left] + values[right]
                if total == target:
                    return [left, right]
                if total < target:
                    left += 1
                else:
                    right -= 1
            return []
        """,
        [("middle pair", [[1, 3, 4, 8], 7]), ("outer pair", [[1, 2, 3, 9], 10])],
        [("no pair", [[1, 2, 3], 100]), ("adjacent", [[2, 4], 6])],
        edges=[("single value", [[5], 5])],
        secondary=["ARRAY"],
        notes={"if total < target:": "Too small means the only way up is to raise "
                                     "the lower end. Too large means lower the "
                                     "upper end. That is the whole invariant."},
        distractors=[
            ("right = len(values)", 1,
             "One past the end. The last valid index is len - 1, and this raises "
             "IndexError on the first read."),
            ("while left <= right:", 1,
             "Letting the pointers land on the same index allows a value to pair "
             "with itself."),
            ("left = left + right", 3,
             "Pointer arithmetic borrowed from binary search. Here the pointers "
             "step by one, deliberately."),
        ],
        nudge="If the sum is too small, which pointer is the only one that can "
              "possibly help?",
        pseudocode="left = 0, right = last\nwhile left < right:\n  sum too small: left forward\n  too large: right back\n  equal: return both\nreturn []",
        failures=["Pairing an element with itself",
                  "Moving the wrong pointer and never converging"],
        time="O(n)", space="O(1)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-palindrome", "Reading It Both Ways", "EASY", "TWO_POINTER", "palindrome",
        """
        Return True when `text` reads the same forwards and backwards. The input is
        already lowercase with no punctuation. is_palindrome("racecar") is True;
        is_palindrome("raceca") is False.

        Walk in from both ends and stop the moment two characters disagree.
        """,
        "is_palindrome", "text", _r_is_palindrome,
        """
        def is_palindrome(text):
            left = 0
            right = len(text) - 1
            while left < right:
                if text[left] != text[right]:
                    return False
                left += 1
                right -= 1
            return True
        """,
        [("palindrome", ["racecar"]), ("not one", ["raceca"])],
        [("even length", ["abba"]), ("two different", ["ab"])],
        edges=[("single character", ["q"])],
        secondary=["STRING"],
        notes={"return True": "Reached only when the pointers cross without a "
                              "disagreement."},
        distractors=[
            ("if text[left] == text[right]:", 3,
             "Inverted: this returns False on the first pair that matches, which is "
             "the opposite of the test you want."),
            ("right = len(text)", 1,
             "One past the end. Indexing there raises IndexError immediately."),
            ("return text == text[::-1]", 1,
             "A correct one-liner, which is exactly why it cannot sit here — it "
             "would make the two-pointer walk you are building unreachable."),
        ],
        nudge="The loop condition decides what happens in the middle of an "
              "odd-length string. A single character never has to match anything.",
        pseudocode="left at the start, right at the end\nwhile they have not met:\n  differ: return False\n  step both inward\nreturn True",
        failures=["Comparing past the crossing point and doing twice the work",
                  "Starting `right` off the end of the string"],
        time="O(n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-move-zeroes", "Sweeping the Empty Runes", "EASY", "TWO_POINTER",
        "converging",
        """
        Return a list with every zero moved to the end and the non-zero values in
        their original order. move_zeroes([0, 1, 0, 3]) gives [1, 3, 0, 0].

        One index reads, a slower one writes. Then fill whatever the writer never
        reached.
        """,
        "move_zeroes", "values", _r_move_zeroes,
        """
        def move_zeroes(values):
            out = list(values)
            write = 0
            for read in range(len(out)):
                if out[read] != 0:
                    out[write] = out[read]
                    write += 1
            while write < len(out):
                out[write] = 0
                write += 1
            return out
        """,
        [("mixed", [[0, 1, 0, 3]]), ("no zeros", [[1, 2, 3]])],
        [("all zeros", [[0, 0]]), ("leading zeros", [[0, 0, 5]])],
        edges=[("empty", [[]])],
        secondary=["ARRAY"],
        notes={"write = 0": "The writer lags the reader. It only advances when "
                            "something was actually kept."},
        distractors=[
            ("out[read] = out[write]", 3,
             "The assignment runs the wrong way and overwrites the value you were "
             "trying to keep."),
            ("for read in range(len(out) - 1):", 1,
             "Stops one short and leaves the final value unexamined."),
            ("out.remove(0)", 2,
             "Mutating the list while iterating over its indices skips elements, "
             "and `.remove` is O(n) each time besides."),
        ],
        nudge="After the first loop, `write` is exactly the count of non-zero "
              "values. That is what the second loop uses.",
        pseudocode="write = 0\nfor each read index:\n  if non-zero: copy it to write, advance write\nfill the rest with zeros\nreturn out",
        failures=["Advancing the writer on every element",
                  "Forgetting the zero fill and leaving stale values behind"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-valid-parens", "The Matching Seals", "EASY", "STACK", "stack_matching",
        """
        Return True when every bracket in `text` closes in the right order. The
        text contains only the six bracket characters. valid_parens("([])") is
        True; valid_parens("(]") is False.

        The most recent unclosed bracket is the only one that can be closed next,
        which is exactly what a stack is for.
        """,
        "valid_parens", "text", _r_valid_parens,
        """
        def valid_parens(text):
            pairs = {")": "(", "]": "[", "}": "{"}
            stack = []
            for ch in text:
                if ch in pairs:
                    if not stack or stack.pop() != pairs[ch]:
                        return False
                else:
                    stack.append(ch)
            return not stack
        """,
        [("nested", ["([])"]), ("mismatched", ["(]"])],
        [("sequential", ["()[]{}"]), ("unclosed", ["((("])],
        edges=[("empty", [""])],
        secondary=["STRING"],
        notes={"return not stack": "An empty stack at the end means every opener "
                                   "found its closer. Anything left over is unbalanced.",
               "if not stack or stack.pop() != pairs[ch]:":
               "The `not stack` half runs first and short-circuits, which is what "
               "stops `.pop()` from raising on a string that starts with a closer."},
        distractors=[
            ("return True", 1,
             "Leftovers on the stack are unbalanced too. '(((' would pass."),
            ("if stack.pop() != pairs[ch]:", 2,
             "Popping an empty stack raises IndexError the moment the text opens "
             "with a closing bracket."),
            ("stack.pop(0)", 3,
             "Taking from the bottom makes this a queue, and brackets do not close "
             "oldest-first."),
        ],
        nudge="Two different failures end this as False: the wrong closer, and "
              "anything still open when the text runs out.",
        pseudocode="for each character:\n  a closer: the stack top must be its partner\n  otherwise: push it\nreturn the stack is empty",
        failures=["IndexError on a leading closing bracket",
                  "Returning True with openers still on the stack"],
        time="O(n)", space="O(n)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-next-warmer", "The Next Warmer Day", "EASY", "STACK", "monotonic_stack",
        """
        For each day, return how many days you wait for a strictly warmer one, or 0
        if none comes. next_warmer([3, 1, 4]) gives [1, 1, 0].

        Keep a stack of days still waiting. A warm day resolves every one of them
        it beats.
        """,
        "next_warmer", "temps", _r_next_warmer,
        """
        def next_warmer(temps):
            out = [0] * len(temps)
            stack = []
            for i in range(len(temps)):
                while stack and temps[stack[-1]] < temps[i]:
                    j = stack.pop()
                    out[j] = i - j
                stack.append(i)
            return out
        """,
        [("rising", [[3, 1, 4]]), ("falling", [[5, 4, 3]])],
        [("flat", [[2, 2, 2]]), ("late spike", [[1, 1, 1, 9]])],
        edges=[("single day", [[7]])],
        secondary=["ARRAY"],
        notes={"out = [0] * len(temps)": "Pre-filling with zero means the days still "
                                         "on the stack at the end need no cleanup.",
               "out[j] = i - j": "The answer is the distance waited, not the day "
                                 "arrived at."},
        distractors=[
            ("out[j] = i", 3,
             "That records the index of the warmer day. The question asks how many "
             "days of waiting, which is the difference."),
            ("if stack and temps[stack[-1]] < temps[i]:", 2,
             "One warm day can resolve several waiting days at once, so this has to "
             "keep popping, not pop once."),
            ("stack.append(temps[i])", 3,
             "Pushing the temperature loses the day number, and the day number is "
             "what the distance is computed from."),
        ],
        nudge="What is on the stack: temperatures, or the days those temperatures "
              "belong to? Only one of them lets you subtract.",
        pseudocode="out = zeros\nfor each day i:\n  while the stack top is colder: pop it and record i - j\n  push i\nreturn out",
        failures=["Pushing temperatures instead of indices",
                  "Resolving only one waiting day per warm day"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-eval-rpn", "The Reckoning Stack", "EASY", "STACK", "stack_eval",
        """
        Evaluate a list of tokens in reverse Polish notation and return the result.
        Operators are "+", "-" and "*"; everything else is an integer written as
        text. eval_rpn(["4", "1", "-"]) gives 3, because it means 4 - 1.

        The operands come off the stack in reverse: the first pop is the
        right-hand side.
        """,
        "eval_rpn", "tokens", _r_eval_rpn,
        """
        def eval_rpn(tokens):
            import operator
            ops = {"+": operator.add, "-": operator.sub, "*": operator.mul}
            stack = []
            for token in tokens:
                if token in ops:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(ops[token](a, b))
                else:
                    stack.append(int(token))
            return stack[0]
        """,
        [("subtraction", [["4", "1", "-"]]),
         ("nested", [["2", "3", "+", "4", "*"]])],
        [("single value", [["9"]]), ("negative result", [["1", "5", "-"]])],
        edges=[("multiplication only", [["3", "3", "*"]])],
        secondary=["SIMULATION"],
        notes={"b = stack.pop()": "Popped first, so it is the RIGHT operand. Getting "
                                  "these two runes the wrong way round breaks "
                                  "subtraction and nothing else, which makes it a "
                                  "vicious bug.",
               "stack.append(int(token))": "The tokens are text. Without the "
                                           "conversion, '+' would concatenate."},
        distractors=[
            ("stack.append(ops[token](b, a))", 3,
             "Operands reversed. 4 1 - would give -3. Addition would still look "
             "fine, which is how this one survives a careless test."),
            ("stack.append(token)", 3,
             "Pushing the raw string means the arithmetic happens on text, or "
             "explodes."),
            ("a = stack.pop(0)", 3,
             "Taking from the bottom of the stack reaches for the oldest operand "
             "rather than the one just computed."),
        ],
        nudge="Write out 4 1 - by hand. Which value leaves the stack first, and "
              "which side of the minus sign is it on?",
        pseudocode="for each token:\n  operator: pop right, pop left, push the result\n  number: push int(token)\nreturn what is left",
        failures=["Reversing the operands and breaking only subtraction",
                  "Forgetting int() and concatenating strings"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-window-max", "The Deque That Forgets", "EASY", "QUEUE", "queue_window",
        """
        Return the maximum of every window of `k` consecutive values.
        window_max([1, 3, 2], 2) gives [3, 3]. `k` is at least 1 and no longer
        than the list.

        The deque holds indices whose values descend. Anything smaller than the
        arriving value can never be a maximum again.
        """,
        "window_max", "values, k", _r_window_max,
        """
        def window_max(values, k):
            from collections import deque
            window = deque()
            out = []
            for i in range(len(values)):
                while window and values[window[-1]] <= values[i]:
                    window.pop()
                window.append(i)
                if window[0] <= i - k:
                    window.popleft()
                if i >= k - 1:
                    out.append(values[window[0]])
            return out
        """,
        [("pair", [[1, 3, 2], 2]), ("triple", [[9, 1, 1, 5], 3])],
        [("descending", [[5, 4, 3, 2], 2]), ("width one", [[4, 7], 1])],
        edges=[("whole list", [[2, 8], 2])],
        secondary=["SLIDING_WINDOW"],
        notes={"if window[0] <= i - k:": "The front has fallen out of the window. "
                                         "Exactly one index can expire per step.",
               "if i >= k - 1:": "No answer exists until the first full window has "
                                 "been assembled."},
        distractors=[
            ("if window[0] < i - k:", 3,
             "Off by one: the index exactly k back has already left the window, so "
             "`<` keeps a stale maximum for one step too long."),
            ("out.append(values[window[-1]])", 3,
             "The back of the deque holds the newest index, not the largest value. "
             "The maximum lives at the front."),
            ("if i >= k:", 2,
             "Off by one: the first full window closes at index k - 1, so this "
             "loses the first answer entirely."),
        ],
        nudge="Three things happen per step, in order: evict the useless tail, "
              "join, then expire the stale head.",
        pseudocode="for each i:\n  pop the tail while it is no larger than values[i]\n  push i\n  drop the head if it expired\n  once the window is full, record the head's value\nreturn out",
        failures=["Reading the maximum from the wrong end of the deque",
                  "Off-by-one when expiring the front index"],
        time="O(n)", space="O(k)",
    ))

    P.append(_parsons(
        "pa-shortest-hops", "The Shortest Road", "EASY", "BFS", "graph_shortest",
        """
        `graph` maps each node to a list of neighbours. Return the fewest hops from
        `start` to `goal`, or -1 when the goal cannot be reached. Reaching the
        start from itself is 0 hops.

        Breadth-first: the first time you arrive anywhere, you arrived by the
        shortest road.
        """,
        "shortest_hops", "graph, start, goal", _r_shortest_hops,
        """
        def shortest_hops(graph, start, goal):
            from collections import deque
            queue = deque([(start, 0)])
            seen = {start}
            while queue:
                node, dist = queue.popleft()
                if node == goal:
                    return dist
                for nxt in graph[node]:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append((nxt, dist + 1))
            return -1
        """,
        [("two hops", [{"a": ["b"], "b": ["c"], "c": []}, "a", "c"]),
         ("unreachable", [{"a": ["b"], "b": [], "c": []}, "a", "c"])],
        [("already there", [{"a": []}, "a", "a"]),
         ("branching", [{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []},
                        "a", "d"])],
        edges=[("cycle", [{"a": ["b"], "b": ["a"]}, "a", "b"])],
        secondary=["QUEUE"],
        notes={"seen.add(nxt)": "Marked when the node is QUEUED, not when it is "
                                "visited. Marking late lets the same node be "
                                "queued several times over.",
               "return -1": "Reached only when the queue drains without finding the "
                            "goal."},
        distractors=[
            ("queue.pop()", 2,
             "Popping the newest node turns this into depth-first search, and the "
             "first arrival stops being the shortest."),
            ("stack = [start]", 1,
             "A stack explores one road to its end before trying the next. BFS "
             "needs the oldest frontier node first."),
            ("seen.add(node)", 2,
             "Marking on the way out rather than on the way in lets a node be "
             "queued many times before it is ever dequeued."),
        ],
        nudge="Which end of the queue do you take from? That one choice is the "
              "entire difference between BFS and DFS.",
        pseudocode="queue = [(start, 0)]\nseen = {start}\nwhile queue:\n  take the oldest\n  if it is the goal: return its distance\n  queue every unseen neighbour at distance + 1\nreturn -1",
        failures=["Popping from the wrong end and losing the shortest-path guarantee",
                  "Marking nodes seen on dequeue, which re-queues them"],
        time="O(V + E)", space="O(V)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-reachable", "Every Road From Here", "EASY", "DFS", "graph_traverse",
        """
        `graph` maps each node to a list of neighbours. Return every node reachable
        from `start`, including `start` itself, as a sorted list. Cycles are
        possible, so nothing may be visited twice.

        Depth-first with an explicit stack: commit to a road, then unwind.
        """,
        "reachable", "graph, start", _r_reachable,
        """
        def reachable(graph, start):
            seen = set()
            stack = [start]
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                for nxt in graph[node]:
                    stack.append(nxt)
            return sorted(seen)
        """,
        [("chain", [{"a": ["b"], "b": ["c"], "c": []}, "a"]),
         ("island", [{"a": [], "b": ["a"]}, "a"])],
        [("cycle", [{"a": ["b"], "b": ["a"]}, "a"]),
         ("branching", [{"a": ["b", "c"], "b": [], "c": []}, "a"])],
        edges=[("self loop", [{"a": ["a"]}, "a"])],
        secondary=["SET"],
        notes={"if node in seen:": "The guard runs on the way out of the stack, "
                                   "because the same node can be pushed several "
                                   "times before it is ever popped.",
               "return sorted(seen)": "A set has no order. The tests compare a list."},
        distractors=[
            ("node = stack.pop(0)", 2,
             "Taking from the front is breadth-first. It gives the same set here, "
             "by a different road, and this spell is the depth-first one."),
            ("return seen", 1,
             "A set does not compare equal to the sorted list the tests expect."),
            ("if node not in seen:", 2,
             "Inverted: that skips every node the first time it is met and "
             "processes only the repeats."),
        ],
        nudge="A node can be pushed by two different neighbours before it is ever "
              "popped. Where does the duplicate get caught?",
        pseudocode="stack = [start]\nwhile stack:\n  pop a node\n  skip it if already seen\n  mark it, push its neighbours\nreturn sorted(seen)",
        failures=["Infinite loop on a cycle when nothing is marked seen",
                  "Returning the set rather than a sorted list"],
        time="O(V + E)", space="O(V)",
    ))

    P.append(_parsons(
        "pa-tree-sum", "The Weight of the Grove", "EASY", "TREE", "tree_traverse",
        """
        Return the sum of every value in the binary tree. An empty tree sums to 0.
        For a root of 1 with children 2 and 3, tree_sum gives 6.

        Trees arrive in your tests as level-order lists; your function receives a
        real TreeNode with `.val`, `.left` and `.right`.
        """,
        "tree_sum", "root", tree_ref(_r_tree_sum),
        """
        def tree_sum(root):
            if root is None:
                return 0
            return root.val + tree_sum(root.left) + tree_sum(root.right)
        """,
        [("three nodes", [[1, 2, 3]]), ("lone root", [[5]])],
        [("left chain", [[1, 2, None, 3]]), ("negatives", [[-1, -2, -3]])],
        edges=[("empty tree", [[]])],
        secondary=["RECURSION", "DFS"],
        preamble=PREAMBLE, arg_adapters=["tree"],
        notes={"if root is None:": "The base case is the missing node. Every "
                                   "recursive tree spell starts with this rune."},
        distractors=[
            ("return root.val", 1,
             "That answers for one node and never asks the children anything."),
            ("if root.left is None:", 1,
             "The base case is the absent node itself, not a node that happens to "
             "have no left child."),
        ],
        after="pa-reachable",
        nudge="What does a node need from its children? One number each. What does "
              "it add? Itself.",
        pseudocode="if the node is missing: 0\nreturn my value + left total + right total",
        failures=["No base case, so the recursion falls off the bottom of the tree"],
        time="O(n)", space="O(h)",
    ))

    P.append(_parsons(
        "pa-tree-depth", "How Tall the Canopy", "EASY", "TREE", "tree_traverse",
        """
        Return the depth of the deepest node. An empty tree has depth 0 and a lone
        root has depth 1. A root with one child has depth 2.

        Ask both children how tall they are, take the taller, and add yourself.
        """,
        "max_depth", "root", tree_ref(_r_max_depth),
        """
        def max_depth(root):
            if root is None:
                return 0
            left = max_depth(root.left)
            right = max_depth(root.right)
            return 1 + max(left, right)
        """,
        [("balanced", [[3, 9, 20, None, None, 15, 7]]), ("lone root", [[1]])],
        [("left chain", [[1, 2, None, 3]]), ("right chain", [[1, None, 2, None, 3]])],
        edges=[("empty tree", [[]])],
        secondary=["RECURSION", "DFS"],
        preamble=PREAMBLE, arg_adapters=["tree"],
        notes={"return 1 + max(left, right)": "The `1 +` is the node you are "
                                              "standing on. Forgetting it is the "
                                              "classic miss."},
        distractors=[
            ("return max(left, right)", 1,
             "Forgets to count the node you are standing on, so every tree comes "
             "back with depth 0."),
            ("return 1 + left + right", 1,
             "That counts nodes rather than levels. Depth is the longest road down, "
             "not the size of the tree."),
        ],
        after="pa-tree-sum",
        nudge="Two runes ask the children. One rune adds you. They cannot be in the "
              "other order.",
        pseudocode="if missing: 0\nleft = depth of left\nright = depth of right\nreturn 1 + the larger",
        failures=["Returning 0 for a single node",
                  "Summing the two depths instead of taking the larger"],
        time="O(n)", space="O(h)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-level-values", "Ring by Ring", "EASY", "BFS", "tree_bfs",
        """
        Return every value in the tree in level order: the root, then its children
        left to right, then their children. For a root of 1 with children 2 and 3,
        level_values gives [1, 2, 3]. An empty tree gives [].

        The recursion that works for depth does not work here. This one needs a
        queue.
        """,
        "level_values", "root", tree_ref(_r_level_values),
        """
        def level_values(root):
            from collections import deque
            if root is None:
                return []
            out = []
            queue = deque([root])
            while queue:
                node = queue.popleft()
                out.append(node.val)
                if node.left:
                    queue.append(node.left)
                if node.right:
                    queue.append(node.right)
            return out
        """,
        [("full", [[1, 2, 3]]), ("lopsided", [[1, 2, None, 3]])],
        [("lone root", [[9]]), ("deeper", [[1, 2, 3, 4, 5]])],
        edges=[("empty tree", [[]])],
        secondary=["TREE", "QUEUE"],
        preamble=PREAMBLE, arg_adapters=["tree"],
        notes={"queue = deque([root])": "Seeded with the root, which is the whole "
                                        "first ring.",
               "if node.left:": "Guarding here is what keeps `None` off the queue."},
        distractors=[
            ("queue.pop()", 2,
             "Popping the newest node walks the tree depth-first. The rings only "
             "come out in order when the oldest node leaves first."),
            ("for _ in range(len(queue)):", 2,
             "Batching by level belongs to the version that returns one list per "
             "level. This one returns a single flat list."),
            ("out.append(node)", 2,
             "That collects TreeNode objects. The answer is a list of values, which "
             "means `.val`."),
        ],
        after="pa-tree-depth",
        nudge="Which end of the deque does a queue take from? The tree does not "
              "care; the answer's order does.",
        pseudocode="queue = [root]\nwhile queue:\n  take the oldest node\n  record its value\n  queue each child that exists\nreturn out",
        failures=["Putting None on the queue and crashing on the next read",
                  "Using pop() and producing depth-first order"],
        time="O(n)", space="O(n)",
    ))

    P.append(_parsons(
        "pa-binary-search", "Halving the Search", "EASY", "BINARY_SEARCH",
        "binary_search",
        """
        `values` is sorted ascending and has no duplicates. Return the index of
        `target`, or -1 when it is absent. binary_search([1, 3, 7, 9], 7) gives 2.

        Two bounds and a midpoint. Every comparison throws away half of what is
        left.
        """,
        "binary_search", "values, target", _r_binary_search,
        """
        def binary_search(values, target):
            lo = 0
            hi = len(values) - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                if values[mid] == target:
                    return mid
                if values[mid] < target:
                    lo = mid + 1
                else:
                    hi = mid - 1
            return -1
        """,
        [("found", [[1, 3, 7, 9], 7]), ("absent", [[1, 3, 7, 9], 4])],
        [("first", [[2, 4, 6], 2]), ("last", [[2, 4, 6], 6])],
        edges=[("empty", [[], 1])],
        secondary=["ARRAY"],
        notes={"while lo <= hi:": "Closed on both ends, so a single remaining "
                                  "element still gets examined. `<` would skip it.",
               "lo = mid + 1": "The `+ 1` is what guarantees progress. Without it a "
                               "two-element range loops forever."},
        distractors=[
            ("hi = len(values)", 1,
             "One past the end in a closed-interval search, so the first midpoint "
             "can read off the array."),
            ("lo = mid", 3,
             "No progress: when lo and hi are adjacent, mid is lo, and the loop "
             "never moves again."),
            ("while lo < hi:", 1,
             "Stops one element too early and reports the last candidate as absent."),
        ],
        nudge="Two runes decide whether this terminates: the loop condition, and the "
              "`+ 1` or `- 1` on the bound you move.",
        pseudocode="lo = 0, hi = last\nwhile lo <= hi:\n  mid = midpoint\n  equal: return mid\n  too small: lo = mid + 1\n  too large: hi = mid - 1\nreturn -1",
        failures=["Infinite loop from moving a bound to mid instead of past it",
                  "Missing the final element with a strict loop condition"],
        time="O(log n)", space="O(1)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-first-ge", "The First One That Holds", "EASY", "BINARY_SEARCH",
        "binary_search",
        """
        `values` is sorted ascending. Return the index of the first value that is
        greater than or equal to `target`, or `len(values)` when every value is
        smaller. first_ge([1, 3, 5], 4) gives 2.

        This is the half-open form, and the small differences from the plain search
        are the entire lesson.
        """,
        "first_ge", "values, target", _r_first_ge,
        """
        def first_ge(values, target):
            lo = 0
            hi = len(values)
            while lo < hi:
                mid = (lo + hi) // 2
                if values[mid] < target:
                    lo = mid + 1
                else:
                    hi = mid
            return lo
        """,
        [("between values", [[1, 3, 5], 4]), ("exact hit", [[1, 3, 5], 3])],
        [("past the end", [[1, 2], 9]), ("before the start", [[4, 5], 1])],
        edges=[("empty", [[], 1])],
        secondary=["ARRAY"],
        notes={"hi = len(values)": "One past the end on purpose: it is the answer "
                                   "when nothing is large enough.",
               "hi = mid": "Not `mid - 1`. `mid` may itself be the first value that "
                           "holds, so it stays in the range."},
        distractors=[
            ("hi = len(values) - 1", 1,
             "The half-open form needs hi one past the end, or 'everything is too "
             "small' has no index to return."),
            ("hi = mid - 1", 3,
             "Discards `mid`, which may be the very first value that satisfies the "
             "test."),
            ("return -1", 1,
             "Absence is not the answer here. The answer for 'nothing is large "
             "enough' is the length itself."),
        ],
        after="pa-binary-search",
        nudge="Compare this against the plain search rune by rune. Three things "
              "changed, and each one has a reason.",
        pseudocode="lo = 0, hi = len(values)\nwhile lo < hi:\n  mid = midpoint\n  too small: lo = mid + 1\n  otherwise: hi = mid\nreturn lo",
        failures=["Excluding mid from the surviving range and overshooting",
                  "Starting hi at the last index and losing the past-the-end answer"],
        time="O(log n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-count-subarrays", "Stretches That Sum To K", "EASY", "PREFIX_SUM",
        "prefix_sum",
        """
        Return how many contiguous stretches of `values` sum to exactly `k`.
        count_subarrays([1, 1, 1], 2) gives 2, for the first two and the last two.
        Values may be negative.

        A stretch summing to k means two running totals differ by k, so count the
        running totals you have already seen.
        """,
        "count_subarrays", "values, k", _r_count_subarrays,
        """
        def count_subarrays(values, k):
            counts = {0: 1}
            total = 0
            found = 0
            for value in values:
                total += value
                found += counts.get(total - k, 0)
                counts[total] = counts.get(total, 0) + 1
            return found
        """,
        [("overlapping", [[1, 1, 1], 2]), ("whole list", [[3, 4], 7])],
        [("with negatives", [[1, -1, 0], 0]), ("none", [[1, 2], 9])],
        edges=[("empty", [[], 0])],
        secondary=["HASH_MAP", "ARRAY"],
        notes={"counts = {0: 1}": "The seeded zero stands for the empty prefix. "
                                  "Without it, a stretch that starts at index 0 is "
                                  "never counted.",
               "found += counts.get(total - k, 0)":
               "Counted BEFORE this prefix is recorded, which is what stops a "
               "zero-length stretch being counted when k is 0."},
        distractors=[
            ("counts = {}", 1,
             "Without the seeded zero, every stretch beginning at the first element "
             "goes uncounted."),
            ("found += counts.get(total + k, 0)", 2,
             "Sign flipped. The earlier prefix you are looking for is total minus "
             "k."),
            ("found += 1", 2,
             "A prefix value can have been seen many times, and each sighting is a "
             "separate stretch."),
        ],
        nudge="If the running total is now T and some earlier point had T - k, what "
              "does the piece between them sum to?",
        pseudocode="counts = {0: 1}\nfor each value:\n  total += value\n  found += how many times total - k has been seen\n  record total\nreturn found",
        failures=["Forgetting the {0: 1} seed",
                  "Recording the current prefix before counting against it"],
        time="O(n)", space="O(n)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-climb-stairs", "Counting the Ways Up", "EASY", "DP", "dp_linear",
        """
        You climb one or two rungs at a time. Return how many distinct ways there
        are to climb exactly `n` rungs. climb(3) gives 3: 1+1+1, 1+2, and 2+1.
        `n` is at least 1.

        Each rung is reachable from the two below it, so only two numbers ever
        need to be alive.
        """,
        "climb", "n", _r_climb,
        """
        def climb(n):
            if n <= 2:
                return n
            a = 1
            b = 2
            for _ in range(n - 2):
                a, b = b, a + b
            return b
        """,
        [("three rungs", [3]), ("five rungs", [5])],
        [("two rungs", [2]), ("ten rungs", [10])],
        edges=[("one rung", [1])],
        secondary=["RECURSION"],
        notes={"a, b = b, a + b": "A simultaneous assignment: the right-hand side is "
                                  "computed before anything is stored, so `a + b` "
                                  "still uses the old `a`.",
               "for _ in range(n - 2):": "Two rungs are already answered before the "
                                         "loop starts, so it runs that many times "
                                         "fewer."},
        distractors=[
            ("a, b = a + b, b", 2,
             "The pair rolls the wrong way. The new second value is the sum; the "
             "new first is the old second."),
            ("for _ in range(n):", 1,
             "Two answers are already in hand before the loop begins, so this "
             "overshoots by two steps."),
            ("return a", 1,
             "`a` is one rung behind. The answer is the newer of the pair."),
        ],
        nudge="Write out the first five answers by hand. The rule that produces the "
              "next one from the last two is the loop body.",
        pseudocode="if n <= 2: return n\na, b = 1, 2\nrepeat n - 2 times: roll the pair forward\nreturn b",
        failures=["Off-by-one in the number of iterations",
                  "Returning the trailing value of the pair"],
        time="O(n)", space="O(1)", tags=["core"],
    ))

    P.append(_parsons(
        "pa-house-robber", "Nothing From Two Adjacent Vaults", "EASY", "DP",
        "dp_linear",
        """
        Return the largest total you can take from `values` without ever taking two
        neighbours. rob([2, 7, 9, 3, 1]) gives 12, from the 2, the 9 and the 1. An
        empty list gives 0.

        Two running answers: the best that takes the current vault, and the best
        that leaves it.
        """,
        "rob", "values", _r_rob,
        """
        def rob(values):
            take = 0
            skip = 0
            for value in values:
                take, skip = skip + value, max(skip, take)
            return max(take, skip)
        """,
        [("classic", [[2, 7, 9, 3, 1]]), ("two vaults", [[5, 1]])],
        [("increasing", [[1, 2, 3]]), ("single", [[9]])],
        edges=[("empty", [[]])],
        secondary=["ARRAY", "GREEDY"],
        notes={"take, skip = skip + value, max(skip, take)":
               "Taking this vault has to build on the plan that skipped the last "
               "one. Skipping is free to keep whichever plan was better."},
        distractors=[
            ("take = take + value", 2,
             "That robs two neighbours in a row. The take must build on the skip."),
            ("return take", 1,
             "The best plan may well be to leave the last vault alone."),
            ("take, skip = max(skip, take), skip + value", 2,
             "The two halves are swapped: this makes `take` the plan that skipped "
             "and `skip` the plan that took."),
        ],
        after="pa-climb-stairs",
        nudge="Why does `take` add to `skip` rather than to itself? Say the rule "
              "out loud and the rune explains itself.",
        pseudocode="take = 0, skip = 0\nfor each value:\n  new take = old skip + value\n  new skip = the better of the two old plans\nreturn the better of the two",
        failures=["Adding to `take` and robbing adjacent vaults",
                  "Returning only one of the two running answers"],
        time="O(n)", space="O(1)",
    ))

    P.append(_parsons(
        "pa-grid-paths", "Roads Through the Citadel", "EASY", "DP", "dp_grid",
        """
        Count the paths from the top-left to the bottom-right of a `rows` by `cols`
        grid, moving only right or down. paths(2, 3) gives 3. Both dimensions are
        at least 1.

        One row of totals, rewritten in place once per row of the grid.
        """,
        "paths", "rows, cols", _r_paths,
        """
        def paths(rows, cols):
            row = [1] * cols
            for _ in range(rows - 1):
                for c in range(1, cols):
                    row[c] = row[c] + row[c - 1]
            return row[cols - 1]
        """,
        [("wide", [2, 3]), ("square", [3, 3])],
        [("single row", [1, 5]), ("single column", [4, 1])],
        edges=[("one cell", [1, 1])],
        secondary=["MATRIX"],
        notes={"row = [1] * cols": "Every cell in the first row is reached exactly "
                                   "one way: by going right the whole time.",
               "row[c] = row[c] + row[c - 1]":
               "`row[c]` is still the value from the row above, and `row[c - 1]` has "
               "already been rewritten for this row. The in-place update is doing "
               "two different jobs in one line."},
        distractors=[
            ("for c in range(cols):", 2,
             "Column zero is reachable exactly one way and must not be rewritten; "
             "starting there also reads `row[-1]`, the far end of the row."),
            ("row = [0] * cols", 1,
             "Zeros make every total zero forever. The first row is all ones."),
            ("for _ in range(rows):", 1,
             "The first row is already filled in, so the loop runs one time fewer "
             "than there are rows."),
        ],
        after="pa-house-robber",
        nudge="After the inner loop finishes, the list holds the answers for one "
              "more row down. How many times does that have to happen?",
        pseudocode="row = all ones\nrepeat rows - 1 times:\n  for each column from 1: row[c] += row[c-1]\nreturn the last entry",
        failures=["Rewriting column zero and reading off the end of the list",
                  "Running the outer loop once too often"],
        time="O(rows * cols)", space="O(cols)",
    ))

    return P
