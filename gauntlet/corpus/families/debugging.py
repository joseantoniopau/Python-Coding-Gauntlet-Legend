"""Debugging Dungeon / The Armorer's Forge.

Armor is not repaired by clicking a potion. It is repaired by fixing broken code.
Each entry pairs a defect class with the armor piece it restores.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque

from ._base import debug_problem

HELM, CHEST, GAUNTLETS, BOOTS, SHIELD, LEGENDARY = (
    "helmet", "chestplate", "gauntlets", "boots", "shield", "legendary")


def bug(pid, title, difficulty, statement, fn, params, ref, broken, canonical,
        visible, hidden, bug_type, armor, *, cmp="exact", nudge="", failures=(),
        security=False, time="O(n)", space="O(n)"):
    return debug_problem(
        id=pid, title=title, difficulty=difficulty, statement=statement,
        fn_name=fn, params=params, broken=broken, reference=ref,
        canonical=canonical, visible=visible, hidden=hidden, cmp=cmp,
        bug_type=bug_type, armor_piece=armor, nudge=nudge,
        failures=list(failures), security=security,
        time_complexity=time, space_complexity=space,
    )


# --- reference implementations (the CORRECT behaviour) ------------------------
def _sum_positive(nums): return sum(v for v in nums if v > 0)
def _count_words(text): return len(text.split())
def _average(nums): return sum(nums) / len(nums) if nums else 0.0
def _last_index(items, target):
    for i in range(len(items) - 1, -1, -1):
        if items[i] == target:
            return i
    return -1
def _remove_odds(nums): return [v for v in nums if v % 2 == 0]
def _tally(items):
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts
def _append_default(value, bucket=None):
    bucket = [] if bucket is None else list(bucket)
    bucket.append(value)
    return bucket
def _countdown(n):
    out = []
    while n > 0:
        out.append(n)
        n -= 1
    return out
def _fact(n): return 1 if n <= 1 else n * _fact(n - 1)
def _sum_digits(n):
    n = abs(n)
    total = 0
    while n:
        total += n % 10
        n //= 10
    return total
def _find_max(nums): return max(nums) if nums else None
def _reverse_in_place(items):
    items = list(items)
    lo, hi = 0, len(items) - 1
    while lo < hi:
        items[lo], items[hi] = items[hi], items[lo]
        lo += 1
        hi -= 1
    return items
def _first_n_evens(n):
    out, v = [], 0
    while len(out) < n:
        out.append(v)
        v += 2
    return out
def _binary_search(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
def _merge_counts(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v
    return out
def _dedupe(items):
    seen, out = set(), []
    for v in items:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out
def _matrix_row_sums(grid): return [sum(row) for row in grid]
def _transpose(grid): return [list(r) for r in zip(*grid)] if grid else []
def _bfs(graph, start):
    seen, out, q = {start}, [], deque([start])
    while q:
        node = q.popleft()
        out.append(node)
        for nxt in graph.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return out
def _window_max(nums, k):
    if k <= 0 or not nums:
        return []
    return [max(nums[i:i + k]) for i in range(len(nums) - k + 1)]
def _longest_run(s):
    if not s:
        return 0
    best = run = 1
    for i in range(1, len(s)):
        run = run + 1 if s[i] == s[i - 1] else 1
        best = max(best, run)
    return best
def _title_case(text): return " ".join(w.capitalize() for w in text.split())
def _safe_get(d, key, default): return d.get(key, default)
def _filter_len(words, n): return [w for w in words if len(w) >= n]
def _cumulative(nums):
    out, total = [], 0
    for v in nums:
        total += v
        out.append(total)
    return out
def _pair_sums(nums, target):
    seen, out = set(), []
    for v in nums:
        if target - v in seen:
            out.append([target - v, v])
        seen.add(v)
    return out
def _grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "F"
def _stack_balanced(s):
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack
def _failed_by_user(events):
    counts = defaultdict(int)
    for user, ok in events:
        if not ok:
            counts[user] += 1
    return dict(counts)
def _first_unique(s):
    counts = Counter(s)
    for i, ch in enumerate(s):
        if counts[ch] == 1:
            return i
    return -1
def _flatten_once(nested): return [v for row in nested for v in row]
def _clamp_all(nums, lo, hi): return [max(lo, min(hi, v)) for v in nums]
def _sum_column(grid, col): return sum(row[col] for row in grid if col < len(row))
def _rotate_right(items, k):
    if not items:
        return []
    k %= len(items)
    return items[-k:] + items[:-k] if k else list(items)
def _ioc_match(observed, feed): return sorted(set(observed) & set(feed))
def _severity_bucket(alerts):
    out = defaultdict(list)
    for name, sev in alerts:
        out[sev].append(name)
    return {k: sorted(v) for k, v in sorted(out.items())}


def build() -> list:
    return [
        bug("db-syntax-colon", "Cracked Helm", "TUTORIAL",
            "The Armorer hands you a helm with a hairline crack. The code does not even "
            "compile. Fix it so it returns the sum of the positive values.",
            "sum_positive", "nums", _sum_positive,
            "def sum_positive(nums)\n"
            "    return sum(v for v in nums if v > 0)\n",
            "def sum_positive(nums):\n    return sum(v for v in nums if v > 0)\n",
            [("mixed", [[-1, 2, 3]]), ("all negative", [[-1, -2]])],
            [("zeros", [[0, 1]]), ("empty", [[]])],
            "syntax", HELM,
            nudge="Read the very first line. Python is telling you exactly what it wants.",
            failures=["Missing colon after the def line"], space="O(1)"),

        bug("db-syntax-indent", "Misaligned Visor", "TUTORIAL",
            "The plates do not sit flush. Fix the indentation so the word count returns.",
            "count_words", "text", _count_words,
            "def count_words(text):\n"
            "words = text.split()\n"
            "    return len(words)\n",
            "def count_words(text):\n    words = text.split()\n    return len(words)\n",
            [("two", ["a b"]), ("one", ["solo"])],
            [("spaces", ["  a  b  "]), ("empty", [""])],
            "syntax", HELM,
            nudge="Every line in a function body sits at the same depth.",
            space="O(n)"),

        bug("db-divzero", "Shattered Chestplate", "EASY",
            "This averages a list, but the Armorer's test harness feeds it an empty one. "
            "Return `0.0` for an empty list.",
            "average", "nums", _average,
            "def average(nums):\n    return sum(nums) / len(nums)\n",
            "def average(nums):\n"
            "    if not nums:\n"
            "        return 0.0\n"
            "    return sum(nums) / len(nums)\n",
            [("basic", [[1, 2, 3]]), ("single", [[4]])],
            [("empty", [[]]), ("negatives", [[-2, 2]]), ("zeros", [[0, 0]])],
            "unhandled-edge-case", CHEST, cmp="float",
            nudge="What is `len(nums)` when the list is empty?",
            failures=["ZeroDivisionError on empty input"], space="O(1)"),

        bug("db-off-by-one-range", "Dented Boots", "EASY",
            "This should return the index of the LAST occurrence of `target`, or `-1`. "
            "It misses the element at index 0.",
            "last_index", "items, target", _last_index,
            "def last_index(items, target):\n"
            "    for i in range(len(items) - 1, 0, -1):\n"
            "        if items[i] == target:\n"
            "            return i\n"
            "    return -1\n",
            "def last_index(items, target):\n"
            "    for i in range(len(items) - 1, -1, -1):\n"
            "        if items[i] == target:\n"
            "            return i\n"
            "    return -1\n",
            [("last", [[1, 2, 1], 1]), ("absent", [[1, 2], 9])],
            [("only at zero", [[7, 1, 2], 7]), ("single", [[3], 3]),
             ("all same", [[5, 5, 5], 5])],
            "off-by-one", BOOTS,
            nudge="`range(a, b, -1)` stops BEFORE b. What index never gets checked?",
            failures=["Exclusive stop bound excludes index 0"], space="O(1)"),

        bug("db-mutate-while-iterating", "Fractured Gauntlets", "EASY",
            "This should return only the even values. It silently skips elements because "
            "the list is being modified while it is iterated.",
            "remove_odds", "nums", _remove_odds,
            "def remove_odds(nums):\n"
            "    nums = list(nums)\n"
            "    for value in nums:\n"
            "        if value % 2 != 0:\n"
            "            nums.remove(value)\n"
            "    return nums\n",
            "def remove_odds(nums):\n    return [v for v in nums if v % 2 == 0]\n",
            [("mixed", [[1, 2, 3, 4]]), ("all even", [[2, 4]])],
            [("consecutive odds", [[1, 3, 5, 2]]), ("all odd", [[1, 3]]),
             ("empty", [[]])],
            "mutation-during-iteration", GAUNTLETS,
            nudge="Removing an element shifts everything after it left, and the loop's "
                  "internal index has already moved on.",
            failures=["Consecutive removals skip elements"], space="O(n)"),

        bug("db-keyerror", "Pierced Gauntlets", "EASY",
            "Tallying occurrences. It raises KeyError the first time a value is seen.",
            "tally", "items", _tally,
            "def tally(items):\n"
            "    counts = {}\n"
            "    for item in items:\n"
            "        counts[item] += 1\n"
            "    return counts\n",
            "def tally(items):\n"
            "    counts = {}\n"
            "    for item in items:\n"
            "        counts[item] = counts.get(item, 0) + 1\n"
            "    return counts\n",
            [("basic", [["a", "b", "a"]]), ("single", [["x"]])],
            [("numbers", [[1, 1, 2]]), ("empty", [[]]), ("all same", [["z", "z"]])],
            "dictionary-state", GAUNTLETS,
            nudge="`counts[item] += 1` reads before it writes. There is nothing to read yet.",
            failures=["KeyError on first sighting"]),

        bug("db-mutable-default", "Cursed Gauntlets", "MEDIUM",
            "Each call should return a fresh list containing `value`. Instead results "
            "accumulate across calls — the classic Python trap.",
            "append_default", "value, bucket=None", _append_default,
            "def append_default(value, bucket=[]):\n"
            "    bucket.append(value)\n"
            "    return bucket\n",
            "def append_default(value, bucket=None):\n"
            "    bucket = [] if bucket is None else list(bucket)\n"
            "    bucket.append(value)\n"
            "    return bucket\n",
            [("first call", [1]), ("with bucket", [2, [9]])],
            [("second call", [3]), ("string", ["a"]), ("empty bucket", [1, []])],
            "mutable-default", GAUNTLETS,
            nudge="A default argument is evaluated ONCE, when the function is defined — "
                  "not on each call.",
            failures=["State leaks between calls"]),

        bug("db-infinite-loop", "Melted Shield", "EASY",
            "Should count down from `n` to 1. It never terminates because the loop "
            "variable is never changed.",
            "countdown", "n", _countdown,
            "def countdown(n):\n"
            "    out = []\n"
            "    while n > 0:\n"
            "        out.append(n)\n"
            "    return out\n",
            "def countdown(n):\n"
            "    out = []\n"
            "    while n > 0:\n"
            "        out.append(n)\n"
            "        n -= 1\n"
            "    return out\n",
            [("five", [5]), ("one", [1])],
            [("zero", [0]), ("negative", [-3]), ("ten", [10])],
            "infinite-loop", SHIELD,
            nudge="What makes the loop condition eventually false?",
            failures=["Loop variable never decremented"]),

        bug("db-recursion-base", "Bottomless Helm", "EASY",
            "Factorial by recursion. It recurses forever for `n = 0`.",
            "factorial", "n", _fact,
            "def factorial(n):\n"
            "    if n == 1:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n",
            "def factorial(n):\n"
            "    if n <= 1:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n",
            [("five", [5]), ("one", [1])],
            [("zero", [0]), ("two", [2]), ("ten", [10])],
            "recursion-base-case", HELM,
            nudge="The base case must be reachable from every legal input, not just the "
                  "ones you had in mind.",
            failures=["RecursionError at n = 0"], space="O(n)"),

        bug("db-modulo-negative", "Tarnished Chestplate", "MEDIUM",
            "Should return the sum of the decimal digits of `n`. It loops forever on "
            "negative input.",
            "sum_digits", "n", _sum_digits,
            "def sum_digits(n):\n"
            "    total = 0\n"
            "    while n:\n"
            "        total += n % 10\n"
            "        n //= 10\n"
            "    return total\n",
            "def sum_digits(n):\n"
            "    n = abs(n)\n"
            "    total = 0\n"
            "    while n:\n"
            "        total += n % 10\n"
            "        n //= 10\n"
            "    return total\n",
            [("positive", [123]), ("single", [7])],
            [("negative", [-45]), ("zero", [0]), ("large", [999999])],
            "sign-handling", CHEST,
            nudge="In Python `-45 // 10` is `-5`, and it keeps going: `-1`, then `-1` "
                  "forever. Floor division rounds toward negative infinity.",
            failures=["Infinite loop on negatives"], space="O(1)"),

        bug("db-empty-max", "Hollow Shield", "EASY",
            "Returns the largest value, or `None` for an empty list. It raises instead.",
            "find_max", "nums", _find_max,
            "def find_max(nums):\n    return max(nums)\n",
            "def find_max(nums):\n    return max(nums) if nums else None\n",
            [("basic", [[1, 9, 3]]), ("single", [[4]])],
            [("empty", [[]]), ("negatives", [[-5, -1]])],
            "unhandled-edge-case", SHIELD,
            nudge="`max([])` raises ValueError. Guard it.", space="O(1)"),

        bug("db-swap-loop", "Twisted Boots", "MEDIUM",
            "Reverses a list in place. It runs over the whole length and swaps everything "
            "back to where it started.",
            "reverse_items", "items", _reverse_in_place,
            "def reverse_items(items):\n"
            "    items = list(items)\n"
            "    for i in range(len(items)):\n"
            "        j = len(items) - 1 - i\n"
            "        items[i], items[j] = items[j], items[i]\n"
            "    return items\n",
            "def reverse_items(items):\n"
            "    items = list(items)\n"
            "    lo, hi = 0, len(items) - 1\n"
            "    while lo < hi:\n"
            "        items[lo], items[hi] = items[hi], items[lo]\n"
            "        lo += 1\n"
            "        hi -= 1\n"
            "    return items\n",
            [("even", [[1, 2, 3, 4]]), ("odd", [[1, 2, 3]])],
            [("single", [[1]]), ("empty", [[]]), ("two", [[1, 2]])],
            "loop-bounds", BOOTS,
            nudge="Trace `[1,2,3,4]` by hand. How many times does each pair get swapped?",
            failures=["Every pair swapped twice, restoring the original"]),

        bug("db-while-condition", "Overreaching Boots", "EASY",
            "Should return the first `n` non-negative even numbers. It returns one too "
            "many.",
            "first_n_evens", "n", _first_n_evens,
            "def first_n_evens(n):\n"
            "    out, v = [], 0\n"
            "    while len(out) <= n:\n"
            "        out.append(v)\n"
            "        v += 2\n"
            "    return out\n",
            "def first_n_evens(n):\n"
            "    out, v = [], 0\n"
            "    while len(out) < n:\n"
            "        out.append(v)\n"
            "        v += 2\n"
            "    return out\n",
            [("three", [3]), ("one", [1])],
            [("zero", [0]), ("five", [5])],
            "off-by-one", BOOTS,
            nudge="`<=` runs the body one extra time.", space="O(n)"),

        bug("db-binary-search", "Cracked Sword-Belt", "MEDIUM",
            "Binary search over a sorted list. It loops forever on some inputs.",
            "binary_search", "nums, target", _binary_search,
            "def binary_search(nums, target):\n"
            "    lo, hi = 0, len(nums) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] == target:\n"
            "            return mid\n"
            "        if nums[mid] < target:\n"
            "            lo = mid\n"
            "        else:\n"
            "            hi = mid\n"
            "    return -1\n",
            "def binary_search(nums, target):\n"
            "    lo, hi = 0, len(nums) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] == target:\n"
            "            return mid\n"
            "        if nums[mid] < target:\n"
            "            lo = mid + 1\n"
            "        else:\n"
            "            hi = mid - 1\n"
            "    return -1\n",
            [("found", [[1, 3, 5, 7], 5]), ("first", [[1, 3], 1])],
            [("absent", [[1, 3, 5], 4]), ("empty", [[], 1]), ("single", [[2], 2])],
            "loop-bounds", SHIELD,
            nudge="If the range never shrinks past `mid`, the range never shrinks at all.",
            failures=["Infinite loop when lo and hi are adjacent"], space="O(1)"),

        bug("db-merge-counts", "Overwritten Ledger", "EASY",
            "Merging two count dicts should ADD colliding counts. It overwrites them.",
            "merge_counts", "a, b", _merge_counts,
            "def merge_counts(a, b):\n"
            "    out = dict(a)\n"
            "    for k, v in b.items():\n"
            "        out[k] = v\n"
            "    return out\n",
            "def merge_counts(a, b):\n"
            "    out = dict(a)\n"
            "    for k, v in b.items():\n"
            "        out[k] = out.get(k, 0) + v\n"
            "    return out\n",
            [("collision", [{"a": 1}, {"a": 2}]), ("disjoint", [{"a": 1}, {"b": 2}])],
            [("empty b", [{"a": 1}, {}]), ("empty a", [{}, {"b": 1}]),
             ("multiple", [{"a": 1, "b": 1}, {"a": 1, "b": 1}])],
            "dictionary-state", GAUNTLETS,
            nudge="Read the requirement again: add, not replace."),

        bug("db-dedupe-order", "Scrambled Pauldron", "EASY",
            "Should remove duplicates while preserving first-appearance order. It sorts "
            "instead.",
            "dedupe", "items", _dedupe,
            "def dedupe(items):\n    return sorted(set(items))\n",
            "def dedupe(items):\n"
            "    seen, out = set(), []\n"
            "    for value in items:\n"
            "        if value not in seen:\n"
            "            seen.add(value)\n"
            "            out.append(value)\n"
            "    return out\n",
            [("unordered", [[3, 1, 3, 2]]), ("already unique", [[2, 1]])],
            [("strings", [["b", "a", "b"]]), ("empty", [[]]), ("all same", [[1, 1]])],
            "wrong-data-structure", CHEST,
            nudge="A set has no order. You need it for membership only.",
            failures=["Output is sorted rather than in original order"]),

        bug("db-row-sums", "Transposed Bracers", "EASY",
            "Should return the sum of each ROW. It sums each column.",
            "row_sums", "grid", _matrix_row_sums,
            "def row_sums(grid):\n"
            "    return [sum(col) for col in zip(*grid)]\n",
            "def row_sums(grid):\n    return [sum(row) for row in grid]\n",
            [("square", [[[1, 2], [3, 4]]]), ("wide", [[[1, 2, 3], [4, 5, 6]]])],
            [("single row", [[[1, 2]]]), ("single column", [[[1], [2]]]),
             ("empty", [[]])],
            "wrong-axis", GAUNTLETS,
            nudge="`zip(*grid)` iterates columns. You were asked for rows."),

        bug("db-transpose-tuple", "Rigid Tapestry", "EASY",
            "Transposes a matrix but returns tuples where lists are required.",
            "transpose", "grid", _transpose,
            "def transpose(grid):\n    return list(zip(*grid))\n",
            "def transpose(grid):\n"
            "    return [list(row) for row in zip(*grid)] if grid else []\n",
            [("square", [[[1, 2], [3, 4]]]), ("wide", [[[1, 2, 3], [4, 5, 6]]])],
            [("single", [[[1]]]), ("empty", [[]]), ("tall", [[[1], [2]]])],
            "wrong-type", CHEST,
            nudge="`zip` yields tuples. The tests compare against lists."),

        bug("db-bfs-visited", "Looping Compass", "MEDIUM",
            "Breadth-first traversal. Nodes are marked visited when popped instead of "
            "when queued, so they enter the queue repeatedly and appear twice.",
            "bfs_order", "graph, start", _bfs,
            "def bfs_order(graph, start):\n"
            "    from collections import deque\n"
            "    seen, out = set(), []\n"
            "    queue = deque([start])\n"
            "    while queue:\n"
            "        node = queue.popleft()\n"
            "        seen.add(node)\n"
            "        out.append(node)\n"
            "        for nxt in graph.get(node, []):\n"
            "            if nxt not in seen:\n"
            "                queue.append(nxt)\n"
            "    return out\n",
            "def bfs_order(graph, start):\n"
            "    from collections import deque\n"
            "    seen, out = {start}, []\n"
            "    queue = deque([start])\n"
            "    while queue:\n"
            "        node = queue.popleft()\n"
            "        out.append(node)\n"
            "        for nxt in graph.get(node, []):\n"
            "            if nxt not in seen:\n"
            "                seen.add(nxt)\n"
            "                queue.append(nxt)\n"
            "    return out\n",
            [("diamond", [{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}, "a"]),
             ("chain", [{"a": ["b"], "b": []}, "a"])],
            [("cycle", [{"a": ["b"], "b": ["a"]}, "a"]),
             ("single", [{"a": []}, "a"]),
             ("wide", [{"a": ["b", "c", "d"], "b": [], "c": [], "d": []}, "a"])],
            "state-management", LEGENDARY,
            nudge="Two paths reach `d` before `d` is ever popped. When should a node be "
                  "marked?",
            failures=["Duplicate nodes in the output"]),

        bug("db-window-slice", "Short Frame", "MEDIUM",
            "Maximum of each window of size `k`. The final window is missing.",
            "window_max", "nums, k", _window_max,
            "def window_max(nums, k):\n"
            "    if k <= 0 or not nums:\n"
            "        return []\n"
            "    return [max(nums[i:i + k]) for i in range(len(nums) - k)]\n",
            "def window_max(nums, k):\n"
            "    if k <= 0 or not nums:\n"
            "        return []\n"
            "    return [max(nums[i:i + k]) for i in range(len(nums) - k + 1)]\n",
            [("classic", [[1, 3, 2, 5], 2]), ("k one", [[4, 7], 1])],
            [("k equals n", [[1, 2], 2]), ("k zero", [[1], 0]), ("empty", [[], 2])],
            "off-by-one", BOOTS,
            nudge="How many windows of size k fit in n elements? Count it for n=4, k=2.",
            failures=["`len(nums) - k` produces one window too few"]),

        bug("db-longest-run", "Miscounted Tally", "MEDIUM",
            "Should return the length of the longest run of one repeated character. It "
            "resets the counter incorrectly and undercounts.",
            "longest_run", "s", _longest_run,
            "def longest_run(s):\n"
            "    if not s:\n"
            "        return 0\n"
            "    best = run = 1\n"
            "    for i in range(1, len(s)):\n"
            "        if s[i] == s[i - 1]:\n"
            "            run += 1\n"
            "        best = max(best, run)\n"
            "    return best\n",
            "def longest_run(s):\n"
            "    if not s:\n"
            "        return 0\n"
            "    best = run = 1\n"
            "    for i in range(1, len(s)):\n"
            "        run = run + 1 if s[i] == s[i - 1] else 1\n"
            "        best = max(best, run)\n"
            "    return best\n",
            [("two runs", ["aabbb"]), ("no repeats", ["abc"])],
            [("run at end", ["abccc"]), ("all same", ["aaaa"]), ("single", ["a"]),
             ("interrupted", ["aabaa"])],
            "state-management", CHEST,
            nudge="What should `run` become when the character CHANGES?",
            failures=["`run` never resets, so separate runs are joined"], space="O(1)"),

        bug("db-title-case", "Faded Standard", "EASY",
            "Should capitalise each word and lower the rest. It leaves the tail untouched.",
            "title_case", "text", _title_case,
            'def title_case(text):\n'
            '    return " ".join(w[0].upper() + w[1:] for w in text.split())\n',
            'def title_case(text):\n'
            '    return " ".join(w.capitalize() for w in text.split())\n',
            [("simple", ["hello world"]), ("shouting", ["hELLO wORLD"])],
            [("single", ["x"]), ("empty", [""]), ("extra spaces", ["  a  b "])],
            "incomplete-transform", CHEST,
            nudge="`.capitalize()` does both halves of the job."),

        bug("db-safe-get", "Brittle Key", "TUTORIAL",
            "Should return the default when the key is absent. It raises KeyError.",
            "safe_get", "d, key, default", _safe_get,
            "def safe_get(d, key, default):\n    return d[key]\n",
            "def safe_get(d, key, default):\n    return d.get(key, default)\n",
            [("present", [{"a": 1}, "a", 0]), ("absent", [{"a": 1}, "b", 0])],
            [("empty", [{}, "x", -1]), ("falsy value", [{"a": 0}, "a", 99])],
            "dictionary-state", HELM,
            nudge="`.get` never raises. Note the falsy-value test — `d[key] or default` "
                  "would be wrong.",
            space="O(1)"),

        bug("db-filter-len", "Loose Sieve", "EASY",
            "Should keep words of length at least `n`. It uses a strict comparison.",
            "filter_len", "words, n", _filter_len,
            "def filter_len(words, n):\n    return [w for w in words if len(w) > n]\n",
            "def filter_len(words, n):\n    return [w for w in words if len(w) >= n]\n",
            [("basic", [["a", "bb", "ccc"], 2]), ("none", [["a"], 5])],
            [("all pass", [["aa", "bb"], 1]), ("empty", [[], 2]), ("zero", [["a"], 0])],
            "wrong-comparison", BOOTS,
            nudge="'at least n' includes exactly n."),

        bug("db-cumulative-reset", "Leaking Accumulator", "EASY",
            "Running totals. The accumulator is reset inside the loop.",
            "cumulative", "nums", _cumulative,
            "def cumulative(nums):\n"
            "    out = []\n"
            "    for value in nums:\n"
            "        total = 0\n"
            "        total += value\n"
            "        out.append(total)\n"
            "    return out\n",
            "def cumulative(nums):\n"
            "    out, total = [], 0\n"
            "    for value in nums:\n"
            "        total += value\n"
            "        out.append(total)\n"
            "    return out\n",
            [("basic", [[1, 2, 3]]), ("negatives", [[5, -2]])],
            [("zeros", [[0, 0]]), ("single", [[7]]), ("empty", [[]])],
            "state-management", CHEST,
            nudge="Where does state that must survive the loop have to live?"),

        bug("db-pair-order", "Reversed Pairs", "MEDIUM",
            "Collects `[earlier, later]` pairs summing to `target`. It records itself "
            "before checking, so a value pairs with itself.",
            "pair_sums", "nums, target", _pair_sums,
            "def pair_sums(nums, target):\n"
            "    seen, out = set(), []\n"
            "    for value in nums:\n"
            "        seen.add(value)\n"
            "        if target - value in seen:\n"
            "            out.append([target - value, value])\n"
            "    return out\n",
            "def pair_sums(nums, target):\n"
            "    seen, out = set(), []\n"
            "    for value in nums:\n"
            "        if target - value in seen:\n"
            "            out.append([target - value, value])\n"
            "        seen.add(value)\n"
            "    return out\n",
            [("classic", [[1, 5, 3, 3], 6]), ("none", [[1, 2], 99])],
            [("self pair trap", [[3], 6]), ("zeros", [[0, 0], 0]),
             ("negatives", [[-1, 7], 6])],
            "ordering", GAUNTLETS,
            nudge="With `target = 6` and a single `3`, the buggy version finds a pair. "
                  "There is only one element.",
            failures=["An element pairs with itself"]),

        bug("db-grade-order", "Misordered Judgement", "EASY",
            "Grade boundaries are checked in the wrong order, so everything above 70 "
            "returns 'C'.",
            "grade", "score", _grade,
            'def grade(score):\n'
            '    if score >= 70:\n'
            '        return "C"\n'
            '    if score >= 80:\n'
            '        return "B"\n'
            '    if score >= 90:\n'
            '        return "A"\n'
            '    return "F"\n',
            'def grade(score):\n'
            '    if score >= 90:\n'
            '        return "A"\n'
            '    if score >= 80:\n'
            '        return "B"\n'
            '    if score >= 70:\n'
            '        return "C"\n'
            '    return "F"\n',
            [("A", [95]), ("C", [75])],
            [("B", [85]), ("F", [50]), ("boundary", [90]), ("boundary low", [70])],
            "wrong-condition", HELM,
            nudge="A chain of `if ... return` checks stops at the first true branch.",
            space="O(1)"),

        bug("db-parens-final", "Unsealed Vault", "MEDIUM",
            "Bracket matching. It accepts strings with unclosed openers.",
            "is_balanced", "s", _stack_balanced,
            "def is_balanced(s):\n"
            '    stack = []\n'
            '    pairs = {")": "(", "]": "[", "}": "{"}\n'
            "    for ch in s:\n"
            '        if ch in "([{":\n'
            "            stack.append(ch)\n"
            "        elif ch in pairs:\n"
            "            if not stack or stack.pop() != pairs[ch]:\n"
            "                return False\n"
            "    return True\n",
            "def is_balanced(s):\n"
            '    stack = []\n'
            '    pairs = {")": "(", "]": "[", "}": "{"}\n'
            "    for ch in s:\n"
            '        if ch in "([{":\n'
            "            stack.append(ch)\n"
            "        elif ch in pairs:\n"
            "            if not stack or stack.pop() != pairs[ch]:\n"
            "                return False\n"
            "    return not stack\n",
            [("balanced", ["([])"]), ("mismatch", ["(]"])],
            [("unclosed", ["((("]), ("empty", [""]), ("extra closer", ["())"])],
            "incomplete-check", SHIELD, cmp="bool",
            nudge="What does an empty stack at the end mean? What does a non-empty one mean?",
            failures=["Leftover openers are never detected"]),

        bug("db-first-unique-count", "Slow Glyph", "MEDIUM",
            "Correct, but O(n^2): it recounts the whole string for every character and "
            "times out on the large hidden test. Make it O(n).",
            "first_unique_char", "s", _first_unique,
            "def first_unique_char(s):\n"
            "    for i, ch in enumerate(s):\n"
            "        if s.count(ch) == 1:\n"
            "            return i\n"
            "    return -1\n",
            "def first_unique_char(s):\n"
            "    from collections import Counter\n"
            "    counts = Counter(s)\n"
            "    for i, ch in enumerate(s):\n"
            "        if counts[ch] == 1:\n"
            "            return i\n"
            "    return -1\n",
            [("classic", ["leetcode"]), ("none", ["aabb"])],
            [("long", ["ab" * 40000 + "z"]), ("single", ["x"]), ("empty", [""])],
            "performance", SHIELD,
            nudge="`s.count(ch)` walks the entire string. Doing that per character is the "
                  "whole problem.",
            failures=["Quadratic scan times out"]),

        bug("db-rotate-modulo", "Spinning Wheel", "MEDIUM",
            "Rotates a list right by `k`. It crashes or returns the wrong slice when `k` "
            "exceeds the list length or is zero.",
            "rotate_right", "items, k", _rotate_right,
            "def rotate_right(items, k):\n"
            "    return items[-k:] + items[:-k]\n",
            "def rotate_right(items, k):\n"
            "    if not items:\n"
            "        return []\n"
            "    k %= len(items)\n"
            "    return items[-k:] + items[:-k] if k else list(items)\n",
            [("simple", [[1, 2, 3, 4], 1]), ("wrap", [[1, 2, 3], 5])],
            [("k zero", [[1, 2, 3], 0]), ("k equals length", [[1, 2], 2]),
             ("empty", [[], 3])],
            "off-by-one", BOOTS,
            nudge="`items[-0:]` is the WHOLE list and `items[:-0]` is empty. Together they "
                  "duplicate everything.",
            failures=["k == 0 duplicates the list", "k > len misbehaves"]),

        bug("db-flatten-depth", "Half-Unfolded Scroll", "EASY",
            "Should flatten one level of nesting. The comprehension has its loops "
            "reversed and raises.",
            "flatten", "nested", _flatten_once,
            "def flatten(nested):\n"
            "    return [value for value in row for row in nested]\n",
            "def flatten(nested):\n"
            "    return [value for row in nested for value in row]\n",
            [("basic", [[[1, 2], [3]]]), ("uneven", [[[1], [], [2]]])],
            [("empty inner", [[[], []]]), ("empty", [[]]), ("strings", [[["a"], ["b"]]])],
            "syntax", HELM,
            nudge="In a nested comprehension the clauses run left to right, exactly as if "
                  "they were nested for-loops."),

        bug("db-clamp-order", "Inverted Bounds", "EASY",
            "Clamps values into `[lo, hi]`. The `min` and `max` are swapped, so values "
            "escape the range.",
            "clamp", "nums, lo, hi", _clamp_all,
            "def clamp(nums, lo, hi):\n"
            "    return [min(lo, max(hi, value)) for value in nums]\n",
            "def clamp(nums, lo, hi):\n"
            "    return [max(lo, min(hi, value)) for value in nums]\n",
            [("mixed", [[-5, 5, 15], 0, 10]), ("inside", [[3], 0, 10])],
            [("all below", [[-9], 0, 5]), ("all above", [[99], 0, 5]),
             ("empty", [[], 0, 1])],
            "wrong-condition", BOOTS,
            nudge="Trace the value 15 with lo=0 and hi=10 through both versions."),

        bug("db-column-bounds", "Ragged Bracers", "MEDIUM",
            "Sums one column of a possibly ragged matrix. It raises IndexError on short "
            "rows.",
            "sum_column", "grid, col", _sum_column,
            "def sum_column(grid, col):\n"
            "    return sum(row[col] for row in grid)\n",
            "def sum_column(grid, col):\n"
            "    return sum(row[col] for row in grid if col < len(row))\n",
            [("square", [[[1, 2], [3, 4]], 1]), ("first column", [[[1, 2]], 0])],
            [("ragged", [[[1, 2], [3]], 1]), ("empty", [[], 0]),
             ("all short", [[[1], [1]], 3])],
            "bounds-check", GAUNTLETS,
            nudge="Not every row is guaranteed to reach that column.",
            failures=["IndexError on a short row"]),

        bug("sec-db-ioc-case", "Blinded Sensor", "EASY",
            "Should return the sorted indicators present in both lists. It compares the "
            "lists element-wise instead of as sets, so it misses matches in different "
            "positions.",
            "indicator_hits", "observed, feed", _ioc_match,
            "def indicator_hits(observed, feed):\n"
            "    return sorted(a for a, b in zip(observed, feed) if a == b)\n",
            "def indicator_hits(observed, feed):\n"
            "    return sorted(set(observed) & set(feed))\n",
            [("positional luck", [["1.1.1.1", "8.8.8.8"], ["1.1.1.1", "9.9.9.9"]]),
             ("misaligned", [["8.8.8.8", "1.1.1.1"], ["1.1.1.1"]])],
            [("no hits", [["a"], ["b"]]), ("duplicates", [["a", "a"], ["a"]]),
             ("empty", [[], ["a"]])],
            "wrong-data-structure", LEGENDARY, security=True,
            nudge="Order in a telemetry stream is meaningless for membership questions.",
            failures=["Only matches indicators that happen to line up by index"]),

        bug("sec-db-failed-count", "Miscounted Failures", "EASY",
            "Counts failed authentications per identity. It counts every event, not just "
            "the failures.",
            "failed_by_user", "events", _failed_by_user,
            "def failed_by_user(events):\n"
            "    from collections import defaultdict\n"
            "    counts = defaultdict(int)\n"
            "    for user, ok in events:\n"
            "        counts[user] += 1\n"
            "    return dict(counts)\n",
            "def failed_by_user(events):\n"
            "    from collections import defaultdict\n"
            "    counts = defaultdict(int)\n"
            "    for user, ok in events:\n"
            "        if not ok:\n"
            "            counts[user] += 1\n"
            "    return dict(counts)\n",
            [("mixed", [[["a", False], ["a", True], ["b", False]]]),
             ("all failures", [[["a", False], ["a", False]]])],
            [("all successes", [[["a", True]]]), ("empty", [[]]),
             ("two users", [[["a", False], ["b", True]]])],
            "wrong-condition", CHEST, security=True,
            nudge="A successful login is not a failed login. Read the flag.",
            failures=["Successful authentications inflate the count"]),

        bug("sec-db-severity-group", "Unsorted Triage", "EASY",
            "Groups alert names by severity. It returns unsorted names, so the triage "
            "board is non-deterministic.",
            "group_by_severity", "alerts", _severity_bucket,
            "def group_by_severity(alerts):\n"
            "    from collections import defaultdict\n"
            "    out = defaultdict(list)\n"
            "    for name, sev in alerts:\n"
            "        out[sev].append(name)\n"
            "    return dict(out)\n",
            "def group_by_severity(alerts):\n"
            "    from collections import defaultdict\n"
            "    out = defaultdict(list)\n"
            "    for name, sev in alerts:\n"
            "        out[sev].append(name)\n"
            "    return {k: sorted(v) for k, v in sorted(out.items())}\n",
            [("two severities", [[["beacon", "high"], ["scan", "low"], ["c2", "high"]]]),
             ("one", [[["x", "low"]]])],
            [("already sorted", [[["a", "low"], ["b", "low"]]]), ("empty", [[]]),
             ("reverse order", [[["z", "high"], ["a", "high"]]])],
            "nondeterminism", CHEST, security=True,
            nudge="The tests compare exactly. Insertion order is not sorted order."),
    ]
