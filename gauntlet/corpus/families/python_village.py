"""Python Village and Fields of Syntax.

These are the drills that turn 'I know what to do' into 'my fingers already did it'.
Short, sharp, and heavily represented in the spaced-repetition schedule, because
raw Python fluency is the stated bottleneck.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque

from ._base import code_problem

Q = {"QUORA": 2.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 1.5}
VIZ = {"type": "array_scan", "caption": "One pass, one accumulator."}


def drill(pid, title, statement, fn, params, ref, canonical, visible, hidden,
          *, edges=(), cmp="exact", pattern="STRING", difficulty="TUTORIAL",
          nudge="", failures=(), family="python_basics", tags=("python", "drill"),
          time="O(n)", space="O(n)", realm="python_village", pseudocode=""):
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=difficulty,
        family=family, profile_weight=Q, viz=VIZ, statement=statement,
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        visible=visible, hidden=hidden, edges=edges, cmp=cmp,
        time_complexity=time, space_complexity=space,
        failures=list(failures), nudge=nudge or "Reach for the built-in before the loop.",
        visual="Watch the accumulator change on each element.",
        pseudocode=pseudocode or "walk the input once, updating one accumulator",
        tags=list(tags),
    )


# --- reference implementations -----------------------------------------------
def _count_chars(s): return dict(Counter(s))
def _word_count(text): return dict(Counter(text.split()))
def _unique_sorted(items): return sorted(set(items))
def _flatten(nested): return [v for row in nested for v in row]
def _sum_evens(nums): return sum(v for v in nums if v % 2 == 0)
def _squares(nums): return [v * v for v in nums]
def _invert_dict(d): return {v: k for k, v in d.items()}
def _group_by_length(words):
    out = defaultdict(list)
    for w in words:
        out[len(w)].append(w)
    return {k: sorted(v) for k, v in sorted(out.items())}
def _safe_increment(counts, key):
    counts = dict(counts)
    counts[key] = counts.get(key, 0) + 1
    return counts
def _merge_dicts(a, b): return {**a, **b}
def _zip_pairs(a, b): return [list(p) for p in zip(a, b)]
def _enumerate_offsets(items, start): return [[i, v] for i, v in enumerate(items, start)]
def _sort_by_second(pairs): return sorted((list(p) for p in pairs), key=lambda p: p[1])
def _top_n_by_value(d, n):
    return [list(p) for p in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]
def _slice_middle(items): 
    n = len(items)
    return items[n // 4: n - n // 4]
def _chunk(items, size):
    if size <= 0:
        return []
    return [items[i:i + size] for i in range(0, len(items), size)]
def _dedupe_preserve(items):
    seen, out = set(), []
    for v in items:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out
def _rotate_list(items, k):
    if not items:
        return []
    k %= len(items)
    return items[-k:] + items[:-k] if k else list(items)
def _title_words(text): return " ".join(w.capitalize() for w in text.split())
def _strip_punctuation(text): return "".join(c for c in text if c.isalnum() or c.isspace())
def _digits_only(text): return "".join(c for c in text if c.isdigit())
def _safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return None
def _parse_ints(items):
    out = []
    for item in items:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out
def _min_max(nums): return [] if not nums else [min(nums), max(nums)]
def _running_totals(nums):
    out, total = [], 0
    for v in nums:
        total += v
        out.append(total)
    return out
def _counter_most_common(items, n): return [list(p) for p in Counter(items).most_common(n)]
def _defaultdict_group(pairs):
    out = defaultdict(list)
    for k, v in pairs:
        out[k].append(v)
    return {k: out[k] for k in sorted(out)}
def _deque_rotate(items, k):
    d = deque(items)
    d.rotate(k)
    return list(d)
def _heap_smallest(nums, k):
    import heapq
    return heapq.nsmallest(k, nums)
def _set_ops(a, b):
    sa, sb = set(a), set(b)
    return [sorted(sa | sb), sorted(sa & sb), sorted(sa - sb)]
def _tuple_swap(pairs): return [[b, a] for a, b in pairs]
def _string_join(items, sep): return sep.join(str(v) for v in items)
def _reverse_slice(items): return items[::-1]
def _every_other(items): return items[::2]
def _clamp(nums, lo, hi): return [max(lo, min(hi, v)) for v in nums]
def _is_all_unique(items): return len(set(items)) == len(items)
def _sum_nested(nested): return sum(sum(row) for row in nested)
def _lambda_sort_desc(nums): return sorted(nums, key=lambda v: -v)
def _dict_comprehension_squares(n): return {i: i * i for i in range(n)}
def _filter_map(nums): return [v * 2 for v in nums if v > 0]
def _any_all(nums): return [any(v > 0 for v in nums), all(v > 0 for v in nums)]
def _string_format(name, score): return f"{name} scored {score:.2f}"


def build() -> list:
    return [
        drill("pv-count-chars", "The Tally Board",
              "Return a dict mapping each character of `s` to how many times it appears.",
              "count_chars", "s", _count_chars,
              "def count_chars(s):\n    from collections import Counter\n    return dict(Counter(s))",
              [("word", ["hello"]), ("repeats", ["aab"])],
              [("spaces count", ["a a"]), ("digits", ["112"]), ("mixed case", ["Aa"])],
              edges=[("empty", [""])], pattern="HASH_MAP",
              nudge="`collections.Counter` is a dict subclass built for exactly this.",
              failures=["Using a plain dict without `.get(ch, 0)` raises KeyError"],
              pseudocode="dict(Counter(s))"),

        drill("pv-word-count", "Counting the Chant",
              "Return a dict mapping each whitespace-separated word to its count.",
              "word_count", "text", _word_count,
              "def word_count(text):\n    from collections import Counter\n    return dict(Counter(text.split()))",
              [("simple", ["a b a"]), ("single", ["solo"])],
              [("extra spaces", ["  a   b  "]), ("punctuation attached", ["a, a"]),
               ("case sensitive", ["A a"])],
              edges=[("empty", [""])], pattern="HASH_MAP",
              nudge="Bare `.split()` collapses runs of whitespace.",
              pseudocode="dict(Counter(text.split()))"),

        drill("pv-unique-sorted", "The Ordered Set",
              "Return the unique values of `items`, sorted ascending.",
              "unique_sorted", "items", _unique_sorted,
              "def unique_sorted(items):\n    return sorted(set(items))",
              [("dupes", [[3, 1, 2, 1]]), ("clean", [[1, 2]])],
              [("negatives", [[-1, -1, 0]]), ("single", [[5]])],
              edges=[("empty", [[]])], pattern="SET",
              pseudocode="sorted(set(items))"),

        drill("pv-flatten", "Unfolding the Scroll",
              "Flatten a list of lists into a single list, preserving order.",
              "flatten", "nested", _flatten,
              "def flatten(nested):\n    return [value for row in nested for value in row]",
              [("simple", [[[1, 2], [3]]]), ("uneven", [[[1], [], [2, 3]]])],
              [("all empty", [[[], []]]), ("strings", [[["a"], ["b"]]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              nudge="In a nested comprehension the loops read left to right, outer first.",
              failures=["Reversing the two `for` clauses"],
              pseudocode="[v for row in nested for v in row]"),

        drill("pv-sum-evens", "Even Tribute",
              "Return the sum of the even values in `nums`.",
              "sum_evens", "nums", _sum_evens,
              "def sum_evens(nums):\n    return sum(value for value in nums if value % 2 == 0)",
              [("mixed", [[1, 2, 3, 4]]), ("none even", [[1, 3]])],
              [("negatives", [[-2, -3]]), ("zero", [[0, 1]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              failures=["`-3 % 2` is 1 in Python, not -1 — the check still works"],
              pseudocode="sum(v for v in nums if v % 2 == 0)"),

        drill("pv-squares", "Squared Runes",
              "Return a list of the squares of `nums`, in order.",
              "squares", "nums", _squares,
              "def squares(nums):\n    return [value * value for value in nums]",
              [("basic", [[1, 2, 3]]), ("negatives", [[-2, 3]])],
              [("zero", [[0]]), ("large", [[1000]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              pseudocode="[v * v for v in nums]"),

        drill("pv-invert-dict", "Reversing the Vault",
              "Return a dict with keys and values swapped. Values are unique.",
              "invert", "d", _invert_dict,
              "def invert(d):\n    return {value: key for key, value in d.items()}",
              [("simple", [{"a": 1, "b": 2}]), ("single", [{"x": 9}])],
              [("numeric keys", [{1: "a"}]), ("mixed", [{"k": True}])],
              edges=[("empty", [{}])], pattern="HASH_MAP",
              nudge="`.items()` yields (key, value) pairs.",
              pseudocode="{v: k for k, v in d.items()}"),

        drill("pv-group-by-length", "Sorting by Stature",
              "Group `words` by their length. Return a dict of length to sorted word list.",
              "group_by_length", "words", _group_by_length,
              "def group_by_length(words):\n"
              "    from collections import defaultdict\n"
              "    out = defaultdict(list)\n"
              "    for word in words:\n"
              "        out[len(word)].append(word)\n"
              "    return {k: sorted(v) for k, v in sorted(out.items())}",
              [("mixed", [["a", "bb", "cc", "ddd"]]), ("single", [["hi"]])],
              [("empty string", [["", "a"]]), ("duplicates", [["ab", "ab"]])],
              edges=[("empty", [[]])], pattern="HASH_MAP", difficulty="EASY",
              nudge="`defaultdict(list)` removes the 'does this key exist yet' branch.",
              pseudocode="defaultdict(list); out[len(w)].append(w)"),

        drill("pv-safe-increment", "The Careful Counter",
              "Return a copy of `counts` with `key`'s count incremented, creating it at 1 "
              "if absent. Do not modify the input.",
              "increment", "counts, key", _safe_increment,
              "def increment(counts, key):\n"
              "    counts = dict(counts)\n"
              "    counts[key] = counts.get(key, 0) + 1\n"
              "    return counts",
              [("existing", [{"a": 1}, "a"]), ("new", [{"a": 1}, "b"])],
              [("empty dict", [{}, "x"]), ("zero value", [{"a": 0}, "a"])],
              edges=[("numeric key", [{}, 1])], pattern="HASH_MAP",
              nudge="`.get(key, 0)` is the idiom that saves you a KeyError every time.",
              failures=["`counts[key] += 1` raises KeyError on a missing key",
                        "Mutating the caller's dict"],
              pseudocode="counts[key] = counts.get(key, 0) + 1"),

        drill("pv-merge-dicts", "Joining the Ledgers",
              "Merge two dicts. On a key collision, `b` wins.",
              "merge", "a, b", _merge_dicts,
              "def merge(a, b):\n    return {**a, **b}",
              [("disjoint", [{"a": 1}, {"b": 2}]), ("collision", [{"a": 1}, {"a": 9}])],
              [("empty b", [{"a": 1}, {}]), ("empty a", [{}, {"b": 2}])],
              edges=[("both empty", [{}, {}])], pattern="HASH_MAP",
              pseudocode="{**a, **b}"),

        drill("pv-zip-pairs", "Twinning the Columns",
              "Return `[a[i], b[i]]` pairs. Stop at the shorter list.",
              "pair_up", "a, b", _zip_pairs,
              "def pair_up(a, b):\n    return [list(pair) for pair in zip(a, b)]",
              [("equal length", [[1, 2], ["x", "y"]]), ("a longer", [[1, 2, 3], ["x"]])],
              [("b longer", [[1], ["x", "y"]]), ("one empty", [[], [1]])],
              edges=[("both empty", [[], []])], pattern="ARRAY",
              nudge="`zip` stops at the shortest input and yields tuples.",
              pseudocode="[list(p) for p in zip(a, b)]"),

        drill("pv-enumerate", "Numbering the March",
              "Return `[index, value]` pairs where the index starts at `start`.",
              "numbered", "items, start", _enumerate_offsets,
              "def numbered(items, start):\n"
              "    return [[i, value] for i, value in enumerate(items, start)]",
              [("from zero", [["a", "b"], 0]), ("from one", [["a", "b"], 1])],
              [("negative start", [["a"], -1]), ("single", [["z"], 5])],
              edges=[("empty", [[], 0])], pattern="ARRAY",
              nudge="`enumerate(items, start)` takes the starting index as its second "
                    "argument.",
              pseudocode="enumerate(items, start)"),

        drill("pv-sort-by-second", "Ranked by the Second Rune",
              "Sort a list of `[a, b]` pairs by the second element ascending, stable.",
              "sort_by_second", "pairs", _sort_by_second,
              "def sort_by_second(pairs):\n"
              "    return sorted((list(p) for p in pairs), key=lambda p: p[1])",
              [("basic", [[[1, 3], [2, 1]]]), ("ties", [[["a", 1], ["b", 1]]])],
              [("negatives", [[[1, -1], [2, -5]]]), ("single", [[[9, 9]]])],
              edges=[("empty", [[]])], pattern="SORTING",
              nudge="`key=` takes a function of one element and returns what to sort on.",
              pseudocode="sorted(pairs, key=lambda p: p[1])"),

        drill("pv-top-n", "The Loudest N",
              "Return the `n` highest-valued `[key, value]` pairs from a dict, sorted by "
              "value descending and key ascending on ties.",
              "top_n", "d, n", _top_n_by_value,
              "def top_n(d, n):\n"
              "    ranked = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))\n"
              "    return [list(pair) for pair in ranked[:n]]",
              [("three", [{"a": 3, "b": 1, "c": 2}, 2]), ("tie", [{"b": 1, "a": 1}, 2])],
              [("n exceeds size", [{"a": 1}, 5]), ("n zero", [{"a": 1}, 0])],
              edges=[("empty", [{}, 3])], pattern="SORTING", difficulty="EASY",
              nudge="A tuple key sorts on each element in turn; negate to reverse one.",
              pseudocode="sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:n]"),

        drill("pv-chunk", "Splitting the Caravan",
              "Split `items` into consecutive chunks of at most `size`. Return `[]` if "
              "`size` is not positive.",
              "chunk", "items, size", _chunk,
              "def chunk(items, size):\n"
              "    if size <= 0:\n"
              "        return []\n"
              "    return [items[i:i + size] for i in range(0, len(items), size)]",
              [("even split", [[1, 2, 3, 4], 2]), ("ragged", [[1, 2, 3], 2])],
              [("size one", [[1, 2], 1]), ("size exceeds", [[1], 5]),
               ("size zero", [[1, 2], 0])],
              edges=[("empty", [[], 3])], pattern="ARRAY", difficulty="EASY",
              nudge="`range(0, len, size)` gives you every chunk start.",
              failures=["Slicing past the end is safe in Python and yields a short chunk"],
              pseudocode="[items[i:i+size] for i in range(0, len(items), size)]"),

        drill("pv-dedupe-preserve", "Keeping the First Sighting",
              "Remove duplicates from `items` while preserving first-appearance order.",
              "dedupe", "items", _dedupe_preserve,
              "def dedupe(items):\n"
              "    seen, out = set(), []\n"
              "    for value in items:\n"
              "        if value not in seen:\n"
              "            seen.add(value)\n"
              "            out.append(value)\n"
              "    return out",
              [("dupes", [[1, 2, 1, 3]]), ("clean", [[1, 2]])],
              [("all same", [[7, 7, 7]]), ("strings", [["a", "b", "a"]])],
              edges=[("empty", [[]])], pattern="SET", difficulty="EASY",
              nudge="`sorted(set(...))` loses the order. You need a set plus a list.",
              pseudocode="seen set + output list"),

        drill("pv-rotate", "Turning the Wheel",
              "Rotate `items` right by `k` positions. `k` may exceed the length.",
              "rotate", "items, k", _rotate_list,
              "def rotate(items, k):\n"
              "    if not items:\n"
              "        return []\n"
              "    k %= len(items)\n"
              "    return items[-k:] + items[:-k] if k else list(items)",
              [("simple", [[1, 2, 3, 4], 1]), ("wraps", [[1, 2, 3], 5])],
              [("k zero", [[1, 2], 0]), ("k equals length", [[1, 2], 2]),
               ("single", [[9], 3])],
              edges=[("empty", [[], 2])], pattern="ARRAY", difficulty="EASY",
              nudge="`items[-0:]` is the whole list, not the empty one. Guard k == 0.",
              failures=["Forgetting the modulo lets k exceed the length",
                        "The `items[-k:]` slice silently misbehaves when k is 0"],
              pseudocode="k %= len(items); items[-k:] + items[:-k]"),

        drill("pv-title-words", "Capitalising the Decree",
              "Capitalise the first letter of each whitespace-separated word, lowering "
              "the rest, and collapse whitespace to single spaces.",
              "title_words", "text", _title_words,
              'def title_words(text):\n'
              '    return " ".join(word.capitalize() for word in text.split())',
              [("simple", ["hello world"]), ("mixed case", ["hELLo WORLD"])],
              [("extra spaces", ["  a  b  "]), ("single", ["x"])],
              edges=[("empty", [""])], pattern="STRING",
              nudge="`.capitalize()` also lowers the tail; `.title()` behaves differently "
                    "around apostrophes.",
              pseudocode='" ".join(w.capitalize() for w in text.split())'),

        drill("pv-strip-punctuation", "Cleansing the Text",
              "Remove every character that is not alphanumeric or whitespace.",
              "strip_punctuation", "text", _strip_punctuation,
              'def strip_punctuation(text):\n'
              '    return "".join(c for c in text if c.isalnum() or c.isspace())',
              [("classic", ["Hello, world!"]), ("digits kept", ["a1!"])],
              [("all punctuation", ["!!!"]), ("newline kept", ["a\nb"])],
              edges=[("empty", [""])], pattern="STRING",
              pseudocode='"".join(c for c in text if c.isalnum() or c.isspace())'),

        drill("pv-digits-only", "Extracting the Numerals",
              "Return only the digit characters of `text`, in order.",
              "digits_only", "text", _digits_only,
              'def digits_only(text):\n'
              '    return "".join(c for c in text if c.isdigit())',
              [("mixed", ["a1b2"]), ("none", ["abc"])],
              [("all digits", ["123"]), ("symbols", ["#4#"])],
              edges=[("empty", [""])], pattern="STRING",
              pseudocode='"".join(c for c in text if c.isdigit())'),

        drill("pv-safe-divide", "The Guarded Quotient",
              "Return `a / b`, or `None` when `b` is zero. Do not let the exception escape.",
              "safe_divide", "a, b", _safe_divide,
              "def safe_divide(a, b):\n"
              "    try:\n"
              "        return a / b\n"
              "    except ZeroDivisionError:\n"
              "        return None",
              [("normal", [10, 2]), ("zero divisor", [1, 0])],
              [("negative", [-9, 3]), ("float result", [7, 2])],
              edges=[("zero numerator", [0, 5])], pattern="SIMULATION",
              nudge="Catch the specific exception, never a bare `except`.",
              failures=["Catching Exception hides real bugs",
                        "Checking `if b == 0` also works and is arguably cleaner"],
              pseudocode="try: a / b  except ZeroDivisionError: None"),

        drill("pv-parse-ints", "Reading the Broken Ledger",
              "Convert each item to an int, silently skipping anything that will not "
              "convert.",
              "parse_ints", "items", _parse_ints,
              "def parse_ints(items):\n"
              "    out = []\n"
              "    for item in items:\n"
              "        try:\n"
              "            out.append(int(item))\n"
              "        except (TypeError, ValueError):\n"
              "            continue\n"
              "    return out",
              [("mixed", [["1", "x", "3"]]), ("all valid", [["4", "5"]])],
              [("none valid", [["a", "b"]]), ("none value", [[None, "2"]]),
               ("negatives", [["-3"]])],
              edges=[("empty", [[]])], pattern="SIMULATION", difficulty="EASY",
              nudge="`int(None)` raises TypeError, `int('x')` raises ValueError. Catch both.",
              pseudocode="try/except (TypeError, ValueError): continue"),

        drill("pv-min-max", "The Extremes",
              "Return `[minimum, maximum]` of `nums`, or `[]` when empty.",
              "min_max", "nums", _min_max,
              "def min_max(nums):\n"
              "    return [] if not nums else [min(nums), max(nums)]",
              [("mixed", [[3, 1, 4]]), ("single", [[7]])],
              [("negatives", [[-1, -9]]), ("all same", [[2, 2]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              failures=["`min([])` raises ValueError"],
              pseudocode="[] if not nums else [min(nums), max(nums)]"),

        drill("pv-running-totals", "The Accumulating Ledger",
              "Return the running (cumulative) totals of `nums`.",
              "running_totals", "nums", _running_totals,
              "def running_totals(nums):\n"
              "    out, total = [], 0\n"
              "    for value in nums:\n"
              "        total += value\n"
              "        out.append(total)\n"
              "    return out",
              [("basic", [[1, 2, 3]]), ("negatives", [[5, -2]])],
              [("zeros", [[0, 0]]), ("single", [[9]])],
              edges=[("empty", [[]])], pattern="PREFIX_SUM",
              nudge="`itertools.accumulate` does this too, and is worth knowing.",
              pseudocode="total += v; out.append(total)"),

        drill("pv-most-common", "The Frequent Few",
              "Return the `n` most common `[value, count]` pairs of `items`, most common "
              "first.",
              "most_common", "items, n", _counter_most_common,
              "def most_common(items, n):\n"
              "    from collections import Counter\n"
              "    return [list(pair) for pair in Counter(items).most_common(n)]",
              [("classic", [[1, 1, 2], 1]), ("two", [["a", "a", "b", "b"], 2])],
              [("n exceeds", [[1], 5]), ("n zero", [[1, 1], 0])],
              edges=[("empty", [[], 2])], pattern="HASH_MAP", difficulty="EASY",
              pseudocode="Counter(items).most_common(n)"),

        drill("pv-defaultdict-group", "The Automatic Vault",
              "Group `[key, value]` pairs into a dict of key to value-list, keys sorted.",
              "group_pairs", "pairs", _defaultdict_group,
              "def group_pairs(pairs):\n"
              "    from collections import defaultdict\n"
              "    out = defaultdict(list)\n"
              "    for key, value in pairs:\n"
              "        out[key].append(value)\n"
              "    return {k: out[k] for k in sorted(out)}",
              [("basic", [[["a", 1], ["a", 2], ["b", 3]]]), ("single", [[["x", 1]]])],
              [("numeric keys", [[[1, "a"], [1, "b"]]]),
               ("all distinct", [[["a", 1], ["b", 2]]])],
              edges=[("empty", [[]])], pattern="HASH_MAP", difficulty="EASY",
              nudge="`defaultdict(list)` creates the empty list for you on first touch.",
              pseudocode="defaultdict(list); out[k].append(v)"),

        drill("pv-deque-rotate", "The Circular Line",
              "Rotate the items using `collections.deque.rotate` and return a list. A "
              "positive `k` rotates right.",
              "deque_rotate", "items, k", _deque_rotate,
              "def deque_rotate(items, k):\n"
              "    from collections import deque\n"
              "    d = deque(items)\n"
              "    d.rotate(k)\n"
              "    return list(d)",
              [("right", [[1, 2, 3], 1]), ("left", [[1, 2, 3], -1])],
              [("wraps", [[1, 2], 5]), ("zero", [[1, 2], 0])],
              edges=[("empty", [[], 2])], pattern="QUEUE",
              nudge="`deque` also gives you O(1) `appendleft` and `popleft`.",
              pseudocode="deque(items).rotate(k)"),

        drill("pv-heap-smallest", "The Lightest Few",
              "Return the `k` smallest values of `nums`, ascending.",
              "k_smallest", "nums, k", _heap_smallest,
              "def k_smallest(nums, k):\n"
              "    import heapq\n"
              "    return heapq.nsmallest(k, nums)",
              [("basic", [[5, 1, 3], 2]), ("k one", [[9, 2], 1])],
              [("k exceeds", [[1, 2], 9]), ("k zero", [[1], 0]),
               ("negatives", [[-1, -5, 3], 2])],
              edges=[("empty", [[], 2])], pattern="HEAP", difficulty="EASY",
              nudge="`heapq.nsmallest` beats a full sort when k is much smaller than n.",
              pseudocode="heapq.nsmallest(k, nums)"),

        drill("pv-set-ops", "Three Circles",
              "Return `[union, intersection, a_only]`, each sorted.",
              "set_ops", "a, b", _set_ops,
              "def set_ops(a, b):\n"
              "    sa, sb = set(a), set(b)\n"
              "    return [sorted(sa | sb), sorted(sa & sb), sorted(sa - sb)]",
              [("overlap", [[1, 2], [2, 3]]), ("disjoint", [[1], [2]])],
              [("identical", [[1, 2], [2, 1]]), ("one empty", [[], [1]])],
              edges=[("both empty", [[], []])], pattern="SET",
              nudge="`|` union, `&` intersection, `-` difference, `^` symmetric difference.",
              pseudocode="sa | sb, sa & sb, sa - sb"),

        drill("pv-tuple-swap", "Turning the Pairs",
              "Swap the two elements of each `[a, b]` pair.",
              "swap_pairs", "pairs", _tuple_swap,
              "def swap_pairs(pairs):\n    return [[b, a] for a, b in pairs]",
              [("basic", [[[1, 2], [3, 4]]]), ("single", [[["x", "y"]]])],
              [("identical", [[[1, 1]]]), ("mixed types", [[[1, "a"]]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              nudge="Unpacking in the comprehension header is cleaner than indexing.",
              pseudocode="[[b, a] for a, b in pairs]"),

        drill("pv-join", "Binding the Runes",
              "Join `items` into a string with `sep` between them, converting each to str.",
              "join_items", "items, sep", _string_join,
              "def join_items(items, sep):\n"
              "    return sep.join(str(value) for value in items)",
              [("strings", [["a", "b"], "-"]), ("numbers", [[1, 2], ", "])],
              [("single", [["x"], "-"]), ("empty separator", [["a", "b"], ""])],
              edges=[("empty", [[], "-"])], pattern="STRING",
              nudge="`join` refuses non-strings; convert inside the generator.",
              failures=["`\", \".join([1, 2])` raises TypeError"],
              pseudocode="sep.join(str(v) for v in items)"),

        drill("pv-reverse-slice", "The Backwards Path",
              "Return `items` reversed, using slicing.",
              "reverse_items", "items", _reverse_slice,
              "def reverse_items(items):\n    return items[::-1]",
              [("list", [[1, 2, 3]]), ("two", [[1, 2]])],
              [("single", [[1]]), ("strings", [["a", "b"]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              pseudocode="items[::-1]"),

        drill("pv-every-other", "Every Second Step",
              "Return every second element starting from the first.",
              "every_other", "items", _every_other,
              "def every_other(items):\n    return items[::2]",
              [("even length", [[1, 2, 3, 4]]), ("odd length", [[1, 2, 3]])],
              [("single", [[1]]), ("strings", [["a", "b", "c"]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              nudge="The third slice component is the step.",
              pseudocode="items[::2]"),

        drill("pv-clamp", "Bounding the Values",
              "Clamp each value into the inclusive range `[lo, hi]`.",
              "clamp", "nums, lo, hi", _clamp,
              "def clamp(nums, lo, hi):\n"
              "    return [max(lo, min(hi, value)) for value in nums]",
              [("mixed", [[-5, 5, 15], 0, 10]), ("already inside", [[1, 2], 0, 10])],
              [("all below", [[-9, -8], 0, 5]), ("negatives range", [[0], -5, -1])],
              edges=[("empty", [[], 0, 1])], pattern="ARRAY",
              nudge="`max(lo, min(hi, v))` is the whole idiom.",
              pseudocode="max(lo, min(hi, v))"),

        drill("pv-all-unique", "No Twins Here",
              "Return `True` if every value in `items` is distinct.",
              "all_unique", "items", _is_all_unique,
              "def all_unique(items):\n    return len(set(items)) == len(items)",
              [("unique", [[1, 2, 3]]), ("dupes", [[1, 1]])],
              [("strings", [["a", "b"]]), ("single", [[1]])],
              edges=[("empty", [[]])], pattern="SET", cmp="bool",
              pseudocode="len(set(items)) == len(items)"),

        drill("pv-sum-nested", "Weighing the Nest",
              "Return the total of every value across a list of lists of numbers.",
              "sum_nested", "nested", _sum_nested,
              "def sum_nested(nested):\n    return sum(sum(row) for row in nested)",
              [("basic", [[[1, 2], [3]]]), ("with empties", [[[1], []]])],
              [("negatives", [[[-1], [1]]]), ("all empty", [[[], []]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              pseudocode="sum(sum(row) for row in nested)"),

        drill("pv-lambda-sort", "Descending by Decree",
              "Sort `nums` descending using a `key=` lambda rather than `reverse=True`.",
              "sort_desc", "nums", _lambda_sort_desc,
              "def sort_desc(nums):\n    return sorted(nums, key=lambda value: -value)",
              [("basic", [[3, 1, 2]]), ("negatives", [[-1, -3]])],
              [("all same", [[2, 2]]), ("single", [[5]])],
              edges=[("empty", [[]])], pattern="SORTING",
              nudge="Negating the key reverses the order without touching `reverse=`.",
              pseudocode="sorted(nums, key=lambda v: -v)"),

        drill("pv-dict-comprehension", "The Squared Vault",
              "Return `{i: i*i}` for `i` in `range(n)`.",
              "square_map", "n", _dict_comprehension_squares,
              "def square_map(n):\n    return {i: i * i for i in range(n)}",
              [("five", [5]), ("one", [1])],
              [("ten", [10]), ("two", [2])],
              edges=[("zero", [0])], pattern="HASH_MAP",
              pseudocode="{i: i*i for i in range(n)}"),

        drill("pv-filter-map", "Filter Then Transform",
              "Return each positive value doubled, in order.",
              "double_positives", "nums", _filter_map,
              "def double_positives(nums):\n"
              "    return [value * 2 for value in nums if value > 0]",
              [("mixed", [[-1, 2, 3]]), ("all positive", [[1, 2]])],
              [("none positive", [[-1, 0]]), ("zero excluded", [[0]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              nudge="In a comprehension the filter goes after the loop, the transform "
                    "before it.",
              pseudocode="[v * 2 for v in nums if v > 0]"),

        drill("pv-any-all", "The Two Oracles",
              "Return `[any positive, all positive]` for `nums`.",
              "any_all_positive", "nums", _any_all,
              "def any_all_positive(nums):\n"
              "    return [any(v > 0 for v in nums), all(v > 0 for v in nums)]",
              [("mixed", [[-1, 2]]), ("all positive", [[1, 2]])],
              [("none positive", [[-1, -2]]), ("zero", [[0]])],
              edges=[("empty", [[]])], pattern="ARRAY",
              nudge="`all([])` is True and `any([])` is False. Know this cold.",
              failures=["Assuming `all` of an empty sequence is False"],
              pseudocode="any(...), all(...)"),

        drill("pv-fstring", "Formatting the Proclamation",
              "Return the string `\"{name} scored {score}\"` with the score shown to "
              "exactly two decimal places.",
              "format_score", "name, score", _string_format,
              'def format_score(name, score):\n    return f"{name} scored {score:.2f}"',
              [("basic", ["Jose", 91.5]), ("rounding", ["Byte", 3.14159])],
              [("integer", ["Root", 7]), ("zero", ["Trace", 0])],
              edges=[("negative", ["Hash", -1.005])], pattern="STRING",
              nudge="`:.2f` inside the braces controls the formatting.",
              pseudocode='f"{name} scored {score:.2f}"'),
    ]
