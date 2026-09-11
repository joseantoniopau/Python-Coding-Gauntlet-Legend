"""The Entry Rungs: a first, gentle door into every topic the corpus teaches.

This module exists because of an audit, not because of a subject. Grouping the
corpus by `spaced_repetition_family` and asking each group one question — *what
is the easiest problem in here?* — found thirty-nine topics whose gentlest
encounter was EASY, MEDIUM or HARD. Nine of them opened at HARD. A player who
had never seen a two-dimensional DP table met it first as edit distance; the
only way to meet `tree_serialize` at all was to serialise a binary tree from a
blank screen.

That is not a difficulty curve, it is a cliff with a sign on it. So every topic
below gets the rung it was missing, and the file is arranged by that audit
rather than by subject:

  GUIDED    complete, working code with one or two `__BLANK__` runes struck out
            of it. The surrounding lines are the explanation; the hole is the
            question. Encounter kind MISSING_RUNE.
  TUTORIAL  the whole function, but small, single-idea, and stated plainly.
            Used where a named archetype needed two rungs rather than one.

Three authoring rules hold everywhere here.

1. THE REFERENCE IS A DIFFERENT ALGORITHM, not the canonical solution retyped.
   Where the canonical is a sliding window, the reference is the quadratic scan;
   where the canonical is a DP table, the reference is a memoised recursion;
   where the canonical walks a chain with a `seen` set, the reference is Floyd's
   tortoise and hare. The two must agree on every test, which is what makes a
   passing build evidence rather than a tautology.

2. THE RUNES ARE THE IDEA. A blank is never punctuation or bookkeeping. It is
   the shrink condition, the recurrence, the mark-before-you-walk, the
   `popleft` that is the entire reason BFS finds shortest paths. You cannot fill
   one by pattern-matching on the lines around it.

3. THE FAMILY NAMES ARE EXISTING ONES. Nothing here invents a topic. Every
   problem joins a `spaced_repetition_family` the curriculum and the spaced
   repetition scheduler already know about, so these become reachable the moment
   they ship without the chapter ladder needing to learn a new word.

The archetypes from the product spec that had no gentle entry are covered here
too, and the reason is the same one: 3sum opened at MEDIUM, matrix rotation
opened at MEDIUM, a hash-map-like structure opened at MEDIUM, undo/redo opened
at MEDIUM, and serialise/deserialise opened at HARD. Each now opens at GUIDED.
"""
from __future__ import annotations

from ._base import code_problem, design_problem, forge_problem
from ._tree import PREAMBLE as TREE_PREAMBLE, tree_ref
from .meta import PATTERN_CHOICES, complexity_q, pattern_q, reading_q, trap_q
from .scaffolds import rune

# Tree problems hand the player a real linked TreeNode; tests travel as
# level-order value lists and the sandbox adapters convert on the way in.
TREE = dict(preamble=TREE_PREAMBLE, arg_adapters=["tree"],
            realm="binary_tree_canopy")

COMPLEXITY_LADDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(2^n)"]


# ===========================================================================
# REFERENCES
#
# Every one of these is deliberately the *other* implementation. They compute
# the expected values at build time; the canonical solutions shown to the player
# have to reproduce them exactly or the problem never ships.
# ===========================================================================

def _ref_window_sums(nums, k):
    if k <= 0 or k > len(nums):
        return []
    return [sum(nums[i:i + k]) for i in range(len(nums) - k + 1)]


def _ref_longest_distinct(s):
    best = 0
    for i in range(len(s)):
        window = set()
        for j in range(i, len(s)):
            if s[j] in window:
                break
            window.add(s[j])
            best = max(best, j - i + 1)
    return best


def _ref_longest_distinct_text(s):
    best = ""
    for i in range(len(s)):
        for j in range(i, len(s)):
            piece = s[i:j + 1]
            if len(set(piece)) != len(piece):
                break
            if len(piece) > len(best):
                best = piece
    return best


def _ref_longest_k_distinct(s, k):
    if k <= 0:
        return 0
    best = 0
    for i in range(len(s)):
        for j in range(i, len(s)):
            if len(set(s[i:j + 1])) > k:
                break
            best = max(best, j - i + 1)
    return best


def _ref_longest_k_distinct_text(s, k):
    if k <= 0:
        return ""
    best = ""
    for i in range(len(s)):
        for j in range(i, len(s)):
            piece = s[i:j + 1]
            if len(set(piece)) > k:
                break
            if len(piece) > len(best):
                best = piece
    return best


def _ref_anagram_positions(text, pattern):
    from collections import Counter
    size = len(pattern)
    if size == 0 or size > len(text):
        return []
    want = Counter(pattern)
    return [i for i in range(len(text) - size + 1)
            if Counter(text[i:i + size]) == want]


def _ref_longest_run_repl(s, ch, k):
    best = 0
    for i in range(len(s)):
        spent = 0
        for j in range(i, len(s)):
            if s[j] != ch:
                spent += 1
            if spent > k:
                break
            best = max(best, j - i + 1)
    return best


def _ref_recent_count(times, now, span):
    return sum(1 for t in times if now - span < t <= now)


def _ref_shortest_cover(s, need):
    required = set(need)
    if not required:
        return ""
    best = ""
    for i in range(len(s)):
        for j in range(i, len(s)):
            if required.issubset(s[i:j + 1]):
                if not best or j - i + 1 < len(best):
                    best = s[i:j + 1]
                break
    return best


def _ref_window_maxima(nums, k):
    out = []
    if k <= 0 or k > len(nums):
        return out
    for i in range(len(nums) - k + 1):
        best = nums[i]
        for j in range(i + 1, i + k):
            if nums[j] > best:
                best = nums[j]
        out.append(best)
    return out


def _ref_has_three_sum(nums, target):
    from itertools import combinations
    return any(sum(triple) == target for triple in combinations(nums, 3))


def _ref_three_sum_sorted(nums, target):
    from itertools import combinations
    for triple in combinations(sorted(nums), 3):
        if sum(triple) == target:
            return list(triple)
    return []


def _ref_eval_rpn_simple(tokens):
    import operator
    ops = {"+": operator.add, "*": operator.mul}
    stack = []
    for token in tokens:
        if token in ops:
            right = stack.pop()
            left = stack.pop()
            stack.append(ops[token](left, right))
        else:
            stack.append(int(token))
    return stack[-1]


def _ref_max_depth(s):
    """A real stack, so an unmatched ')' cannot drive the depth below zero."""
    stack = []
    best = 0
    for ch in s:
        if ch == "(":
            stack.append(ch)
            best = max(best, len(stack))
        elif ch == ")" and stack:
            stack.pop()
    return best


def _ref_remove_adjacent_pairs(s):
    text = s
    while True:
        for i in range(len(text) - 1):
            if text[i] == text[i + 1]:
                text = text[:i] + text[i + 2:]
                break
        else:
            return text


def _ref_next_greater(nums):
    out = []
    for i, value in enumerate(nums):
        found = -1
        for later in nums[i + 1:]:
            if later > value:
                found = later
                break
        out.append(found)
    return out


def _ref_column_sums(grid):
    return [sum(column) for column in zip(*grid)]


def _ref_rotate_clockwise(grid):
    rows = len(grid)
    if rows == 0:
        return []
    cols = len(grid[0])
    return [[grid[rows - 1 - r][c] for r in range(rows)] for c in range(cols)]


def _ref_rotate_counter(grid):
    rows = len(grid)
    if rows == 0:
        return []
    cols = len(grid[0])
    return [[grid[r][cols - 1 - c] for r in range(rows)] for c in range(cols)]


def _ref_region_size(grid, r, c):
    if not grid or grid[r][c] == 0:
        return 0
    target = grid[r][c]
    seen = set()

    def walk(row, col):
        if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
            return 0
        if (row, col) in seen or grid[row][col] != target:
            return 0
        seen.add((row, col))
        return 1 + walk(row - 1, col) + walk(row + 1, col) \
            + walk(row, col - 1) + walk(row, col + 1)

    return walk(r, c)


def _ref_shortest_steps(grid, target_row, target_col):
    if not grid or grid[0][0] == 1:
        return -1
    level = [(0, 0)]
    seen = {(0, 0)}
    steps = 0
    while level:
        nxt = []
        for row, col in level:
            if (row, col) == (target_row, target_col):
                return steps
            for nr, nc in ((row - 1, col), (row + 1, col),
                           (row, col - 1), (row, col + 1)):
                if not (0 <= nr < len(grid) and 0 <= nc < len(grid[0])):
                    continue
                if (nr, nc) in seen or grid[nr][nc] == 1:
                    continue
                seen.add((nr, nc))
                nxt.append((nr, nc))
        level = nxt
        steps += 1
    return -1


def _ref_reachable(graph, start):
    found = set()

    def walk(node):
        if node in found:
            return
        found.add(node)
        for neighbour in graph.get(node, []):
            walk(neighbour)

    walk(start)
    return sorted(found)


def _ref_hops(graph, start, goal):
    level = [start]
    seen = {start}
    distance = 0
    while level:
        if goal in level:
            return distance
        nxt = []
        for node in level:
            for neighbour in graph.get(node, []):
                if neighbour not in seen:
                    seen.add(neighbour)
                    nxt.append(neighbour)
        level = nxt
        distance += 1
    return -1


def _ref_has_cycle(nxt, start):
    slow = fast = start
    while fast != -1 and nxt[fast] != -1:
        slow = nxt[slow]
        fast = nxt[nxt[fast]]
        if slow == fast:
            return True
    return False


def _ref_count_paths(graph, start, goal):
    memo = {}

    def walk(node):
        if node == goal:
            return 1
        if node not in memo:
            memo[node] = sum(walk(n) for n in graph.get(node, []))
        return memo[node]

    return walk(start)


def _ref_level_order(root):
    depths = {}

    def walk(node, depth):
        if node is None:
            return
        depths.setdefault(depth, []).append(node.val)
        walk(node.left, depth + 1)
        walk(node.right, depth + 1)

    walk(root, 0)
    out = []
    for depth in sorted(depths):
        out.extend(depths[depth])
    return out


def _ref_has_path_sum(root, target):
    if root is None:
        return False
    stack = [(root, target)]
    while stack:
        node, remaining = stack.pop()
        if node.left is None and node.right is None and node.val == remaining:
            return True
        for child in (node.left, node.right):
            if child is not None:
                stack.append((child, remaining - node.val))
    return False


def _ref_is_valid_bst(root):
    values = []

    def walk(node):
        if node is None:
            return
        walk(node.left)
        values.append(node.val)
        walk(node.right)

    walk(root)
    return all(values[i] < values[i + 1] for i in range(len(values) - 1))


def _ref_serialize(root):
    out = []
    stack = [root]
    order = []
    while stack:
        node = stack.pop()
        order.append(node)
        if node is not None:
            stack.append(node.right)
            stack.append(node.left)
    for node in order:
        out.append("#" if node is None else str(node.val))
    return out


def _ref_deserialize(tokens):
    """Rebuild the tree, then hand back the level-order value list the tests
    travel as — the same shape the sandbox's `tree` result adapter produces."""
    from ._tree import TreeNode, from_tree

    position = [0]

    def build():
        token = tokens[position[0]]
        position[0] += 1
        if token == "#":
            return None
        node = TreeNode(int(token))
        node.left = build()
        node.right = build()
        return node

    return from_tree(build()) if tokens else []


def _ref_unique_paths(rows, cols):
    import math
    if rows <= 0 or cols <= 0:
        return 0
    return math.comb(rows + cols - 2, rows - 1)


def _ref_lcs_length(a, b):
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def walk(i, j):
        if i == len(a) or j == len(b):
            return 0
        if a[i] == b[j]:
            return 1 + walk(i + 1, j + 1)
        return max(walk(i + 1, j), walk(i, j + 1))

    return walk(0, 0)


def _ref_can_break(text, words):
    vocabulary = set(words)
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def walk(start):
        if start == len(text):
            return True
        return any(text[start:end] in vocabulary and walk(end)
                   for end in range(start + 1, len(text) + 1))

    return walk(0)


def _ref_min_coins(coins, amount):
    if amount < 0:
        return -1
    if amount == 0:
        return 0
    frontier = {0}
    seen = {0}
    depth = 0
    while frontier:
        depth += 1
        nxt = set()
        for total in frontier:
            for coin in coins:
                step = total + coin
                if step == amount:
                    return depth
                if step < amount and step not in seen:
                    seen.add(step)
                    nxt.add(step)
        frontier = nxt
    return -1


def _ref_subset_sum(nums, target):
    def walk(index, remaining):
        if remaining == 0:
            return True
        if index == len(nums):
            return False
        return walk(index + 1, remaining - nums[index]) or walk(index + 1, remaining)

    return walk(0, target)


def _ref_longest_increasing(nums):
    import bisect
    tails = []
    for value in nums:
        slot = bisect.bisect_left(tails, value)
        if slot == len(tails):
            tails.append(value)
        else:
            tails[slot] = value
    return len(tails)


def _ref_sum_halves(nums):
    return sum(nums)


def _ref_smallest_root(n):
    import math
    if n <= 0:
        return 0
    root = math.isqrt(n)
    return root if root * root >= n else root + 1


def _ref_anagram_groups(words):
    from collections import defaultdict
    buckets = defaultdict(list)
    for word in words:
        buckets["".join(sorted(word))].append(word)
    return [sorted(bucket) for bucket in buckets.values()]


def _ref_round_trip(values):
    """Level-order out, level-order back — a different encoding entirely from the
    pre-order-with-markers one the player writes, which is the point: two formats
    that disagree about anything would disagree here."""
    from ._tree import from_tree, to_tree
    return from_tree(to_tree(values))


def _ref_initials(sentence):
    return "".join(word[0].upper() for word in sentence.split())


# ---------------------------------------------------------------------------
# Reference classes for the design rungs. Same rule: written independently of
# the canonical solution the player is shown.
# ---------------------------------------------------------------------------

class _RefTally:
    def __init__(self):
        self._items = []

    def add(self, item):
        self._items.append(item)
        return None

    def count(self, item):
        return self._items.count(item)

    def best(self):
        if not self._items:
            return None
        return max(sorted(set(self._items)), key=self._items.count)


class _RefHashMap:
    """A dict pretending to be a bucket array. The player writes the buckets;
    this only has to agree about what the answers are."""

    def __init__(self):
        self._store = {}

    def put(self, key, value):
        self._store[key] = value
        return None

    def get(self, key):
        return self._store.get(key, -1)

    def remove(self, key):
        self._store.pop(key, None)
        return None


class _RefEditor:
    def __init__(self):
        self._states = [""]
        self._at = 0

    def write(self, chunk):
        self._states = self._states[:self._at + 1]
        self._states.append(self._states[self._at] + chunk)
        self._at += 1
        return self._states[self._at]

    def undo(self):
        if self._at > 0:
            self._at -= 1
        return self._states[self._at]

    def redo(self):
        if self._at + 1 < len(self._states):
            self._at += 1
        return self._states[self._at]


# ===========================================================================
# SECTION 1 — THE WINDOW FAMILIES
#
# Six of the corpus's nine window families had no rung below EASY, and two of
# them (`rolling_max`, `window_cover`) had nothing below HARD. The window is the
# single most reported non-hash-map pattern there is, so it gets the most doors.
# ===========================================================================

MARSH = "sliding_window_marsh"


def _windows() -> list:
    P: list = []

    P.append(rune(
        id="rp-window-sums", title="The Rune of the Rolling Total",
        realm=MARSH, difficulty="GUIDED", family="window_sum",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: the fixed frame",
        secondary=["ARRAY"],
        statement="""
            Return the sum of every window of exactly `k` consecutive values in
            `nums`, left to right. If `k` is not a usable width, return an empty list.

            Recomputing each window from scratch is O(n*k). The loop below does it in
            one pass: each step the window moves one place right, so exactly one value
            joins it and exactly one value leaves it.
        """,
        fn_name="window_sums", params="nums, k", reference=_ref_window_sums,
        canonical="""
            def window_sums(nums, k):
                if k <= 0 or k > len(nums):
                    return []
                total = sum(nums[:k])
                out = [total]
                for i in range(k, len(nums)):
                    total += nums[i] - nums[i - k]
                    out.append(total)
                return out
        """,
        blanks=[("sum(nums[:k])", "the total of the very first window"),
                ("nums[i] - nums[i - k]",
                 "the value joining the window, less the one leaving it")],
        visible=[("width three", [[1, 2, 3, 4, 5], 3]),
                 ("width one", [[4, 1, 7], 1])],
        hidden=[("whole list", [[2, 2, 2], 3]),
                ("negatives", [[-1, -2, 5, -3], 2])],
        edges=[("k wider than the list", [[1, 2], 5]),
               ("k of zero", [[1, 2], 0]),
               ("empty", [[], 2])],
        constraints=["k may be larger than the list, or zero"],
        failures=["Recomputing sum(nums[i:i+k]) each step, which is O(n*k)",
                  "Forgetting the first window and starting the loop at index 0"],
        nudge="One value arrives, one value departs. That is the whole trick.",
        visual="[1 2 3] 4 5  ->  1 [2 3 4] 5 : the 4 came in, the 1 went out.",
        pseudocode="""
            k unusable -> []
            total = sum of the first k
            out = [total]
            for i from k to the end:
                total += arriving - departing
                append total
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-window-distinct", title="The Rune of No Repeats",
        realm=MARSH, difficulty="GUIDED", family="window_distinct",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: the shrink condition",
        secondary=["HASH_MAP", "STRING"],
        statement="""
            Return the length of the longest stretch of `s` in which no character
            repeats.

            `seen` maps each character to the last index it appeared at. The window is
            everything from `left` to `right`. When the arriving character is already
            inside the window, the window cannot simply grow — its left edge has to
            jump past the earlier copy.
        """,
        fn_name="longest_distinct", params="s", reference=_ref_longest_distinct,
        canonical="""
            def longest_distinct(s):
                seen = {}
                left = 0
                best = 0
                for right, ch in enumerate(s):
                    if ch in seen and seen[ch] >= left:
                        left = seen[ch] + 1
                    seen[ch] = right
                    best = max(best, right - left + 1)
                return best
        """,
        blanks=[("seen[ch] + 1",
                 "the first index the window is still allowed to start at"),
                ("right - left + 1", "how wide the window is at this moment")],
        visible=[("classic", ["abcabcbb"]), ("all the same", ["bbbbb"])],
        hidden=[("late repeat", ["pwwkew"]), ("all distinct", ["abcdef"])],
        edges=[("empty", [""]), ("single", ["z"]), ("two same", ["aa"])],
        constraints=["`seen` remembers characters that have already left the window"],
        failures=["Jumping `left` backwards when the earlier copy is already outside "
                  "the window",
                  "Measuring the window as `right - left`, one short"],
        nudge="A character 'repeats' only if its last sighting is still inside the "
              "window. Check that before you move anything.",
        visual="a b c a b c b b : when the second 'a' arrives, left jumps to index 1.",
        pseudocode="""
            seen = {}, left = 0, best = 0
            for each index right and character:
                if this character was last seen at or after left:
                    left = that index + 1
                record this character at right
                best = max(best, current width)
        """,
        time_complexity="O(n)", space_complexity="O(k)",
    ))

    P.append(code_problem(
        id="rp-window-distinct-text", title="The Longest Clean Stretch",
        realm=MARSH, difficulty="TUTORIAL", family="window_distinct",
        pattern="SLIDING_WINDOW", secondary=["HASH_MAP", "STRING"],
        prerequisites=["rp-window-distinct"],
        statement="""
            Return the longest stretch of `s` containing no repeated character — the
            text itself this time, not its length. On a tie, return the one that starts
            earliest.

            You have already written the window that finds the length. The only new
            work is remembering *where* the best window was, not just how wide.
        """,
        fn_name="longest_distinct_text", params="s",
        reference=_ref_longest_distinct_text,
        canonical="""
            def longest_distinct_text(s):
                seen = {}
                left = 0
                best_start = 0
                best_length = 0
                for right, ch in enumerate(s):
                    if ch in seen and seen[ch] >= left:
                        left = seen[ch] + 1
                    seen[ch] = right
                    if right - left + 1 > best_length:
                        best_length = right - left + 1
                        best_start = left
                return s[best_start:best_start + best_length]
        """,
        starter_code="""
            def longest_distinct_text(s):
                # 1. seen: character -> the last index it appeared at
                # 2. left: the start of the current window
                # 3. best_start / best_length: where the best window was
                # 4. walk right across the string, moving left when a repeat arrives
                # 5. a STRICTLY wider window replaces the best one, so ties keep
                #    the earliest
                pass
        """,
        visible=[("classic", ["abcabcbb"]), ("late repeat", ["pwwkew"])],
        hidden=[("all distinct", ["abcdef"]), ("all the same", ["cccc"])],
        edges=[("empty", [""]), ("single", ["q"]),
               ("tie keeps the earlier", ["abab"])],
        failures=["Returning the length instead of the text",
                  "Using `>=` when comparing widths, which returns a later tie"],
        nudge="Record the start whenever you record a new best width. Never after.",
        visual="The answer is a slice. Slices need a start and a length, so track both.",
        pseudocode="""
            same window as before
            when the width beats the best:
                remember the width AND the left edge
            return the slice
        """,
        time_complexity="O(n)", space_complexity="O(k)",
    ))

    P.append(rune(
        id="rp-window-k-distinct", title="The Rune of the Budget of Kinds",
        realm=MARSH, difficulty="GUIDED", family="window_k_distinct",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: shrink until legal",
        secondary=["HASH_MAP", "STRING"],
        statement="""
            Return the length of the longest stretch of `s` containing at most `k`
            distinct characters.

            `counts` holds how many of each character sit inside the window. Growing
            the window is free; the interesting half is the `while`, which shrinks from
            the left until the window is legal again. A count that reaches zero must
            leave the dict entirely, or `len(counts)` keeps counting a character that
            is no longer there.
        """,
        fn_name="longest_k_distinct", params="s, k",
        reference=_ref_longest_k_distinct,
        canonical="""
            def longest_k_distinct(s, k):
                counts = {}
                left = 0
                best = 0
                for right, ch in enumerate(s):
                    counts[ch] = counts.get(ch, 0) + 1
                    while len(counts) > k:
                        counts[s[left]] -= 1
                        if counts[s[left]] == 0:
                            del counts[s[left]]
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        blanks=[("len(counts) > k",
                 "the window is holding more kinds of character than allowed"),
                ("del counts[s[left]]",
                 "this character has left the window entirely, so stop counting it")],
        visible=[("two kinds", ["eceba", 2]), ("three kinds", ["aabacbebebe", 3])],
        hidden=[("k covers everything", ["abcdef", 9]),
                ("one kind only", ["aabbcc", 1])],
        edges=[("k of zero", ["abc", 0]), ("empty", ["", 2]),
               ("single character", ["a", 1])],
        constraints=["k of zero admits no window at all"],
        failures=["Leaving zero-count characters in the dict, so `len(counts)` lies",
                  "Using `if` instead of `while`, which shrinks only once"],
        nudge="Grow on the right unconditionally. Shrink on the left until it is legal.",
        visual="e c e b a, k=2 : when 'b' arrives the window holds {e,c,b} — shrink.",
        pseudocode="""
            counts = {}, left = 0, best = 0
            for each index right and character:
                add it to counts
                while too many distinct:
                    remove s[left] from counts, deleting it at zero
                    left += 1
                best = max(best, width)
        """,
        time_complexity="O(n)", space_complexity="O(k)",
    ))

    P.append(code_problem(
        id="rp-window-k-distinct-text", title="The Widest Legal Stretch",
        realm=MARSH, difficulty="TUTORIAL", family="window_k_distinct",
        pattern="SLIDING_WINDOW", secondary=["HASH_MAP", "STRING"],
        prerequisites=["rp-window-k-distinct"],
        statement="""
            Return the longest stretch of `s` containing at most `k` distinct
            characters — the text, not the length. On a tie, return the earliest.

            Same window, same shrink rule. The only addition is remembering where the
            best window started.
        """,
        fn_name="longest_k_distinct_text", params="s, k",
        reference=_ref_longest_k_distinct_text,
        canonical="""
            def longest_k_distinct_text(s, k):
                counts = {}
                left = 0
                best_start = 0
                best_length = 0
                for right, ch in enumerate(s):
                    counts[ch] = counts.get(ch, 0) + 1
                    while len(counts) > k:
                        counts[s[left]] -= 1
                        if counts[s[left]] == 0:
                            del counts[s[left]]
                        left += 1
                    if right - left + 1 > best_length:
                        best_length = right - left + 1
                        best_start = left
                return s[best_start:best_start + best_length]
        """,
        starter_code="""
            def longest_k_distinct_text(s, k):
                # 1. counts: character -> how many are inside the window
                # 2. left, best_start, best_length
                # 3. grow right, then shrink left while len(counts) > k
                # 4. a strictly wider window replaces the best
                # 5. return the slice, not the number
                pass
        """,
        visible=[("two kinds", ["eceba", 2]), ("three kinds", ["aabacbebebe", 3])],
        hidden=[("one kind", ["aabbcc", 1]), ("k covers everything", ["abcd", 9])],
        edges=[("k of zero", ["abc", 0]), ("empty", ["", 2]),
               ("tie keeps the earlier", ["abcd", 2])],
        failures=["Returning the width instead of the slice",
                  "Forgetting that `k = 0` means the answer is the empty string"],
        nudge="`best_start` only ever changes on the same line that `best_length` does.",
        visual="The window is [left, right]. A slice needs the left edge kept.",
        pseudocode="""
            same shrink loop as the length version
            when the width strictly beats the best, record width and left
            return s[best_start : best_start + best_length]
        """,
        time_complexity="O(n)", space_complexity="O(k)",
    ))

    P.append(rune(
        id="rp-window-anagram", title="The Rune of the Matching Frame",
        realm="stringwood_labyrinth", difficulty="GUIDED", family="window_anagram",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: the fixed frame",
        secondary=["STRING", "HASH_MAP"],
        statement="""
            Return every index in `text` at which a rearrangement of `pattern` begins.

            The window here never changes size — it is always exactly as long as
            `pattern`. So the only question at each position is whether the letters
            inside the frame are the same multiset as the letters of `pattern`, and the
            cheapest way to ask that is to put both into the same canonical order.
        """,
        fn_name="anagram_positions", params="text, pattern",
        reference=_ref_anagram_positions,
        canonical="""
            def anagram_positions(text, pattern):
                size = len(pattern)
                if size == 0 or size > len(text):
                    return []
                want = sorted(pattern)
                out = []
                for i in range(len(text) - size + 1):
                    if sorted(text[i:i + size]) == want:
                        out.append(i)
                return out
        """,
        blanks=[("sorted(pattern)",
                 "the pattern's letters in an order two anagrams must share"),
                ("sorted(text[i:i + size]) == want",
                 "this frame's letters, in that same order, match the pattern's")],
        visible=[("two hits", ["cbaebabacd", "abc"]), ("overlapping", ["abab", "ab"])],
        hidden=[("no hit", ["abcdef", "xy"]), ("whole string", ["bca", "abc"])],
        edges=[("pattern longer than text", ["ab", "abc"]),
               ("empty pattern", ["abc", ""]),
               ("empty text", ["", "a"])],
        constraints=["an empty pattern matches nowhere, by decision"],
        failures=["Letting an empty pattern match at every index",
                  "Stopping the loop at `len(text)` and reading past the end"],
        nudge="Two strings are anagrams exactly when their sorted forms are equal.",
        visual="c[bae]babacd : the frame slides one place at a time and never resizes.",
        pseudocode="""
            pattern empty or longer than text -> []
            want = pattern's letters, sorted
            for every start where a full frame fits:
                if the frame's letters sorted == want: record the start
        """,
        time_complexity="O(n*m log m)", space_complexity="O(m)",
        complexity_choices=["O(n)", "O(n*m log m)", "O(n^2)", "O(n log n)"],
    ))

    P.append(rune(
        id="rp-window-replace", title="The Rune of the Spent Budget",
        realm=MARSH, difficulty="GUIDED", family="window_replace",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: a budget that shrinks",
        secondary=["STRING"],
        statement="""
            You may replace at most `k` characters of `s` with `ch`. Return the length
            of the longest run of `ch` you can produce.

            `others` counts how many characters inside the window are *not* `ch` —
            that is, how much of the budget the window is currently spending. The
            window is legal while that number is within budget.
        """,
        fn_name="longest_run_with_replacements", params="s, ch, k",
        reference=_ref_longest_run_repl,
        canonical="""
            def longest_run_with_replacements(s, ch, k):
                left = 0
                others = 0
                best = 0
                for right in range(len(s)):
                    if s[right] != ch:
                        others += 1
                    while others > k:
                        if s[left] != ch:
                            others -= 1
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        blanks=[("others > k",
                 "the window is spending more replacements than it is allowed"),
                ("others -= 1",
                 "the character leaving the window was one of the replaced ones")],
        visible=[("two spare", ["aabab", "a", 1]), ("none spare", ["abab", "b", 0])],
        hidden=[("budget covers all", ["xyz", "x", 3]),
                ("already a run", ["aaaa", "a", 2])],
        edges=[("empty", ["", "a", 2]), ("zero budget", ["ab", "a", 0]),
               ("character absent", ["bbb", "a", 1])],
        constraints=["k may exceed the length of the string"],
        failures=["Decrementing `others` for every departing character, "
                  "including the ones that were already `ch`"],
        nudge="Only non-`ch` characters cost anything, arriving or leaving.",
        visual="a a b a b, ch='a', k=1 : the window may hold exactly one 'b'.",
        pseudocode="""
            left = 0, others = 0, best = 0
            for each right:
                if s[right] is not ch: others += 1
                while over budget:
                    if s[left] is not ch: others -= 1
                    left += 1
                best = max(best, width)
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    P.append(rune(
        id="rp-window-time", title="The Rune of the Expiring Frame",
        realm=MARSH, difficulty="GUIDED", family="window_time",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: a window made of time",
        secondary=["QUEUE"],
        statement="""
            `times` is a list of event timestamps in ascending order. Return how many
            of them fall inside the last `span` seconds ending at `now` — that is,
            every event strictly later than `now - span` and no later than `now`.

            This is the window every rate limiter is built out of. Its width is not a
            count of elements, it is an interval, so what decides whether the oldest
            entry leaves is its timestamp, not the queue's length.
        """,
        fn_name="recent_count", params="times, now, span",
        reference=_ref_recent_count,
        canonical="""
            from collections import deque


            def recent_count(times, now, span):
                window = deque()
                for t in times:
                    if t > now:
                        continue
                    window.append(t)
                    while window and window[0] <= now - span:
                        window.popleft()
                return len(window)
        """,
        blanks=[("window[0] <= now - span",
                 "the oldest event has fallen out of the back of the interval"),
                ("window.popleft()",
                 "drop that expired event — from the FRONT, where the oldest is")],
        visible=[("half inside", [[1, 5, 9, 12], 12, 8]),
                 ("all inside", [[10, 11, 12], 12, 60])],
        hidden=[("none inside", [[1, 2, 3], 100, 5]),
                ("boundary is exclusive", [[4, 5, 6], 10, 6])],
        edges=[("empty", [[], 10, 5]), ("span of zero", [[10], 10, 0]),
               ("events after now", [[1, 50], 10, 20])],
        constraints=["timestamps are ascending", "an event exactly `span` old is out"],
        failures=["Using `<` instead of `<=` on the expiry test, keeping a stale event",
                  "Popping from the right, which throws away the newest event"],
        nudge="Expiry is a question about a timestamp, never about a length.",
        visual="now=12, span=8 : the interval is (4, 12]. The 1 is out; the 5 is in.",
        pseudocode="""
            window = empty deque
            for each timestamp not in the future:
                push it on the right
                while the leftmost is at or before now - span: pop it
            answer = how many are left
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-window-cover", title="The Rune of the Smallest Cover",
        realm=MARSH, difficulty="GUIDED", family="window_cover",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: covering a requirement",
        secondary=["SET", "STRING"],
        statement="""
            Return the shortest stretch of `s` that contains every character of `need`
            at least once, or the empty string if no stretch does. On a tie, return the
            one that starts earliest.

            This version is deliberately the honest quadratic one: from each starting
            point, extend until the requirement is covered, then stop — extending
            further can only make the answer longer. Recognising *why* you may stop is
            the idea; the linear version is a later problem.
        """,
        fn_name="shortest_cover", params="s, need", reference=_ref_shortest_cover,
        canonical="""
            def shortest_cover(s, need):
                required = set(need)
                if not required:
                    return ""
                best = ""
                for i in range(len(s)):
                    seen = set()
                    for j in range(i, len(s)):
                        seen.add(s[j])
                        if required <= seen:
                            if not best or j - i + 1 < len(best):
                                best = s[i:j + 1]
                            break
                return best
        """,
        blanks=[("required <= seen",
                 "everything the answer must contain is now inside this window"),
                ("j - i + 1 < len(best)",
                 "this window is STRICTLY shorter than the best one so far")],
        visible=[("classic", ["adobecodebanc", "abc"]),
                 ("whole string", ["xyz", "xyz"])],
        hidden=[("no cover", ["abc", "abcd"]), ("repeats", ["aaabc", "abc"])],
        edges=[("empty need", ["abc", ""]), ("empty text", ["", "a"]),
               ("single character", ["a", "a"])],
        constraints=["`need` counts kinds of character, not how many of each"],
        failures=["Using `<=` when comparing lengths, which returns a later tie",
                  "Continuing past the first cover from a given start, for no gain"],
        nudge="`set_a <= set_b` asks 'is a a subset of b'. That is the cover test.",
        visual="a d o b e c o d e b a n c : from index 9, 'banc' covers {a,b,c}.",
        pseudocode="""
            required = the distinct characters of need
            for each start i:
                grow j until required is covered
                if that window beats the best, keep it
                stop growing this start
        """,
        time_complexity="O(n^2)", space_complexity="O(k)",
    ))

    P.append(rune(
        id="rp-rolling-max", title="The Rune of the Loudest in the Frame",
        realm=MARSH, difficulty="GUIDED", family="rolling_max",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: the fixed frame",
        secondary=["ARRAY"],
        statement="""
            Return the largest value in each window of exactly `k` consecutive values
            of `nums`, left to right. If `k` is unusable, return an empty list.

            Start with the obvious version — ask each window for its own maximum. It is
            O(n*k) and it is correct, which is the right first answer to give out loud
            before anyone mentions a deque.
        """,
        fn_name="window_maxima", params="nums, k", reference=_ref_window_maxima,
        canonical="""
            def window_maxima(nums, k):
                if k <= 0 or k > len(nums):
                    return []
                out = []
                for i in range(len(nums) - k + 1):
                    out.append(max(nums[i:i + k]))
                return out
        """,
        blanks=[("range(len(nums) - k + 1)",
                 "every start position at which a full window of width k still fits"),
                ("max(nums[i:i + k])", "the largest value inside the window at i")],
        visible=[("classic", [[1, 3, -1, -3, 5, 3, 6, 7], 3]),
                 ("width one", [[4, 2, 9], 1])],
        hidden=[("whole list", [[5, 1, 5], 3]), ("descending", [[9, 8, 7, 6], 2])],
        edges=[("k wider than the list", [[1], 4]), ("k of zero", [[1, 2], 0]),
               ("empty", [[], 3])],
        constraints=["k may be zero or wider than the list"],
        failures=["Looping to `len(nums)` and producing short windows at the end"],
        nudge="How many windows of width k fit in a list of length n? That is your range.",
        visual="[1 3 -1] -3 5 : the frame is width 3 and never changes size.",
        pseudocode="""
            k unusable -> []
            for each start where a full window fits:
                append the maximum of that window
        """,
        time_complexity="O(n*k)", space_complexity="O(n)",
        complexity_choices=["O(n)", "O(n log n)", "O(n*k)", "O(n^2)"],
    ))

    P.append(code_problem(
        id="rp-rolling-max-deque", title="The Queue That Forgets the Beaten",
        realm=MARSH, difficulty="TUTORIAL", family="rolling_max",
        pattern="QUEUE", secondary=["SLIDING_WINDOW", "ARRAY"],
        prerequisites=["rp-rolling-max"],
        statement="""
            Same answer as before — the maximum of every window of width `k` — but in
            a single pass over `nums`.

            The insight is a deletion, not a data structure. If a value enters the
            window and it is larger than the value behind it, that older value can
            never be the maximum of any window from here on: it is smaller and it will
            expire sooner. So throw it away. What is left is a deque of indices whose
            values decrease from front to back, and the front is always the answer.
        """,
        fn_name="window_maxima_pass", params="nums, k",
        reference=_ref_window_maxima,
        canonical="""
            from collections import deque


            def window_maxima_pass(nums, k):
                if k <= 0 or k > len(nums):
                    return []
                out = []
                waiting = deque()
                for i, value in enumerate(nums):
                    while waiting and nums[waiting[-1]] <= value:
                        waiting.pop()
                    waiting.append(i)
                    if waiting[0] <= i - k:
                        waiting.popleft()
                    if i >= k - 1:
                        out.append(nums[waiting[0]])
                return out
        """,
        starter_code="""
            from collections import deque


            def window_maxima_pass(nums, k):
                # 1. k unusable -> []
                # 2. `waiting` holds INDICES, and the values at them decrease
                #    from front to back
                # 3. before pushing i: pop from the BACK every index whose value
                #    this one beats — they can never win again
                # 4. if the FRONT index has fallen out of the window, popleft it
                # 5. once the first full window exists, its answer is nums[front]
                pass
        """,
        visible=[("classic", [[1, 3, -1, -3, 5, 3, 6, 7], 3]),
                 ("width one", [[4, 2, 9], 1])],
        hidden=[("ascending", [[1, 2, 3, 4], 2]),
                ("descending", [[9, 8, 7, 6], 2]),
                ("all equal", [[5, 5, 5, 5], 2])],
        edges=[("k wider than the list", [[1], 4]), ("k of zero", [[1, 2], 0]),
               ("empty", [[], 3])],
        constraints=["one pass; each index is pushed once and popped at most once"],
        failures=["Storing values instead of indices, so expiry cannot be detected",
                  "Using `<` instead of `<=` when evicting, which keeps stale duplicates",
                  "Emitting an answer before the first full window exists"],
        nudge="Store indices. You need to know WHEN something expires, and a value "
              "does not know where it lives.",
        visual="Front = the current maximum. Back = the most recent arrival. "
               "Everything between is a value still waiting for its turn.",
        pseudocode="""
            for each index i and value:
                pop from the back while the back's value <= this value
                push i
                if the front has expired (front <= i - k): popleft
                if a full window exists: record nums[front]
        """,
        time_complexity="O(n)", space_complexity="O(k)",
    ))

    return P


# ===========================================================================
# SECTION 2 — POINTERS, STACKS AND STRINGS
#
# `three_sum` is on the reported-archetype list and opened at MEDIUM. The four
# stack families all opened at EASY, which is one rung too high for a structure
# whose whole content is "the most recent thing matters most".
# ===========================================================================

MINES = "stack_queue_mines"
WOOD = "stringwood_labyrinth"


def _pointers_and_stacks() -> list:
    P: list = []

    P.append(rune(
        id="rp-three-sum-exists", title="The Rune of the Third Index",
        realm="array_caverns", difficulty="GUIDED", family="three_sum",
        pattern="ARRAY", scaffold_for="BRUTE FORCE: every combination, once",
        secondary=["TWO_POINTER"],
        statement="""
            Return True when some three distinct positions in `nums` hold values summing
            to `target`.

            This is the version you should be able to write instantly, because it is
            what the fast version is measured against. The only real content is the
            index discipline: each loop starts one past the loop outside it, so no
            position is used twice and no triple is counted twice.
        """,
        fn_name="has_three_sum", params="nums, target",
        reference=_ref_has_three_sum,
        canonical="""
            def has_three_sum(nums, target):
                n = len(nums)
                for i in range(n):
                    for j in range(i + 1, n):
                        for k in range(j + 1, n):
                            if nums[i] + nums[j] + nums[k] == target:
                                return True
                return False
        """,
        blanks=[("range(j + 1, n)",
                 "the third index always starts one past the second"),
                ("nums[i] + nums[j] + nums[k] == target",
                 "these three chosen values hit the target exactly")],
        visible=[("hit", [[1, 2, 3, 4], 9]), ("miss", [[1, 2, 3], 20])],
        hidden=[("negatives", [[-1, 0, 1, 2], 0]), ("duplicates", [[2, 2, 2], 6])],
        edges=[("only two values", [[1, 2], 3]), ("empty", [[], 0]),
               ("exactly three", [[5, 5, 5], 15])],
        constraints=["three distinct positions; equal values at different positions "
                     "are still allowed"],
        failures=["Starting the inner loops at 0, which reuses one position",
                  "Returning a triple instead of a boolean"],
        nudge="i < j < k. Write those three ranges and the rest is arithmetic.",
        visual="The cost is 'choose 3 of n', which is n^3/6 — cubic, and honest.",
        pseudocode="""
            for i over every index:
                for j after i:
                    for k after j:
                        if the three sum to target -> True
            -> False
        """,
        time_complexity="O(n^3)", space_complexity="O(1)",
        complexity_choices=["O(n)", "O(n^2)", "O(n^3)", "O(2^n)"],
    ))

    P.append(code_problem(
        id="rp-three-sum-pair", title="Fix One, Converge the Rest",
        realm="array_caverns", difficulty="TUTORIAL", family="three_sum",
        pattern="TWO_POINTER", secondary=["SORTING", "ARRAY"],
        prerequisites=["rp-three-sum-exists"],
        statement="""
            Return the first triple of values from `nums` that sums to `target`, as a
            list in ascending order, or an empty list if there is none.

            Sort first. Then fix the smallest of the three and the problem collapses:
            from the remaining sorted stretch you need two values summing to a known
            remainder, and two converging pointers answer that in one pass. Cubic
            becomes quadratic, and the sort is what paid for it.
        """,
        fn_name="three_sum_sorted", params="nums, target",
        reference=_ref_three_sum_sorted,
        canonical="""
            def three_sum_sorted(nums, target):
                values = sorted(nums)
                n = len(values)
                for i in range(n - 2):
                    left = i + 1
                    right = n - 1
                    while left < right:
                        total = values[i] + values[left] + values[right]
                        if total == target:
                            return [values[i], values[left], values[right]]
                        if total < target:
                            left += 1
                        else:
                            right -= 1
                return []
        """,
        starter_code="""
            def three_sum_sorted(nums, target):
                # 1. sort a COPY — sorted() already gives you one
                # 2. for each i up to n - 3, fix values[i] as the smallest
                # 3. left = i + 1, right = n - 1
                # 4. too small -> move left up; too large -> move right down
                # 5. exactly right -> return the three values, ascending
                pass
        """,
        visible=[("hit", [[1, 2, 3, 4], 9]), ("unsorted input", [[4, 1, 3, 2], 6])],
        hidden=[("negatives", [[-2, -1, 0, 3], 0]), ("miss", [[1, 2, 3], 100])],
        edges=[("only two values", [[1, 2], 3]), ("empty", [[], 0]),
               ("exactly three", [[5, 1, 3], 9])],
        constraints=["the returned triple is ascending",
                     "the input list must not be mutated in place"],
        failures=["Calling `nums.sort()`, which mutates the caller's list",
                  "Moving the wrong pointer — too small means the LEFT one moves up",
                  "Looping i to n - 1, leaving no room for two more pointers"],
        nudge="Sorted order is what makes 'too small' and 'too large' actionable. "
              "Without it neither pointer knows which way to move.",
        visual="[-2 -1 0 3], i at -2 : left and right close in on a remainder of 2.",
        pseudocode="""
            values = sorted(nums)
            for i from 0 to n - 3:
                left, right = i + 1, n - 1
                while left < right:
                    total = the three values
                    equal -> return them
                    below -> left += 1
                    above -> right -= 1
            -> []
        """,
        time_complexity="O(n^2)", space_complexity="O(n)",
        complexity_choices=["O(n log n)", "O(n^2)", "O(n^3)", "O(n)"],
    ))

    P.append(rune(
        id="rp-stack-eval", title="The Rune of the Reckoning Stack",
        realm=MINES, difficulty="GUIDED", family="stack_eval",
        pattern="STACK", scaffold_for="STACK: operands wait, operators consume",
        statement="""
            Evaluate a list of tokens in reverse Polish notation, where every token is
            either an integer or one of `+` and `*`. Return the result.

            No parentheses, no precedence, no parsing. That is the point of the
            notation: the stack holds the operands that have not been used yet, and an
            operator always applies to the two most recent of them.
        """,
        fn_name="eval_rpn_simple", params="tokens",
        reference=_ref_eval_rpn_simple,
        canonical="""
            def eval_rpn_simple(tokens):
                stack = []
                for token in tokens:
                    if token == "+":
                        right = stack.pop()
                        left = stack.pop()
                        stack.append(left + right)
                    elif token == "*":
                        right = stack.pop()
                        left = stack.pop()
                        stack.append(left * right)
                    else:
                        stack.append(int(token))
                return stack[-1]
        """,
        blanks=[("stack.append(left + right)",
                 "push the result back where both operands used to be"),
                ("stack.append(int(token))",
                 "this token is a number, and numbers wait on the stack")],
        visible=[("add", [["2", "3", "+"]]), ("mixed", [["2", "3", "+", "4", "*"]])],
        hidden=[("nested", [["1", "2", "+", "3", "4", "+", "*"]]),
                ("negatives", [["-2", "3", "*"]])],
        edges=[("single number", [["7"]]), ("times one", [["9", "1", "*"]]),
               ("long chain", [["1", "1", "+", "1", "+", "1", "+"]])],
        constraints=["the token list is always well formed",
                     "tokens are strings, including the numbers"],
        failures=["Popping the operands in the wrong order — for `+` and `*` it does "
                  "not matter, for `-` and `/` it decides the answer",
                  "Forgetting `int()` and concatenating strings instead of adding"],
        nudge="An operator never looks further back than the top two entries.",
        visual="2 3 + 4 *  ->  [2] [2,3] [5] [5,4] [20]",
        pseudocode="""
            stack = []
            for each token:
                operator -> pop two, push the combination
                otherwise -> push int(token)
            answer is what is left on top
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-stack-nesting", title="The Rune of the Deepest Room",
        realm=MINES, difficulty="GUIDED", family="stack_nesting",
        pattern="STACK", scaffold_for="STACK: depth is a counter",
        statement="""
            Return the deepest level of nesting in `s`, counting only `(` and `)` and
            ignoring every other character.

            Depth is the one stack question that does not need a stack — you never look
            at what is inside it, only at how tall it is, and a single integer tracks
            that. Knowing when the structure collapses to a counter is worth as much as
            knowing when it does not.
        """,
        fn_name="max_depth", params="s", reference=_ref_max_depth,
        canonical="""
            def max_depth(s):
                depth = 0
                best = 0
                for ch in s:
                    if ch == "(":
                        depth += 1
                        best = max(best, depth)
                    elif ch == ")" and depth > 0:
                        depth -= 1
                return best
        """,
        blanks=[("best = max(best, depth)",
                 "record the deepest we have ever stood, not the depth right now"),
                ("depth -= 1", "one level of nesting closes")],
        visible=[("nested", ["((1)(2))"]), ("flat", ["(a)(b)(c)"])],
        hidden=[("no brackets", ["abc"]), ("deep", ["(((x)))"])],
        edges=[("empty", [""]), ("only closers", [")))"]),
               ("unbalanced open", ["((("])],
        constraints=["the input may be unbalanced; report the depth reached anyway"],
        failures=["Returning `depth` at the end, which is 0 for balanced input",
                  "Letting an unmatched ')' drive the depth below zero",
                  "Recording the maximum after decrementing rather than after "
                  "incrementing"],
        nudge="The answer is a high-water mark. Take it the moment you go deeper.",
        visual="( ( 1 ) ( 2 ) ) : depths 1, 2, 1, 2, 1, 0. The high-water mark is 2.",
        pseudocode="""
            depth = 0, best = 0
            for each character:
                '(' -> depth += 1; best = max(best, depth)
                ')' with something open -> depth -= 1
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        complexity_choices=["O(1)", "O(n)", "O(n log n)", "O(n^2)"],
    ))

    P.append(rune(
        id="rp-stack-simulation", title="The Rune of Mutual Destruction",
        realm=MINES, difficulty="GUIDED", family="stack_simulation",
        pattern="STACK", scaffold_for="STACK: the top is the only thing that matters",
        secondary=["STRING"],
        statement="""
            Repeatedly remove adjacent pairs of identical characters from `s` until no
            adjacent pair remains, and return what is left. Removing a pair can create
            a new one, and that one goes too.

            Rescanning the string after every removal is O(n^2) and fiddly. The stack
            version is one pass: the character you are holding only ever has to be
            compared against the one most recently kept.
        """,
        fn_name="remove_adjacent_pairs", params="s",
        reference=_ref_remove_adjacent_pairs,
        canonical="""
            def remove_adjacent_pairs(s):
                stack = []
                for ch in s:
                    if stack and stack[-1] == ch:
                        stack.pop()
                    else:
                        stack.append(ch)
                return "".join(stack)
        """,
        blanks=[("stack[-1] == ch",
                 "the character already on top matches the one arriving"),
                ("stack.pop()",
                 "they annihilate, so remove the one that was already there")],
        visible=[("cascading", ["abbaca"]), ("all cancel", ["aabb"])],
        hidden=[("nothing cancels", ["abc"]), ("full collapse", ["abccba"])],
        edges=[("empty", [""]), ("single", ["a"]), ("one pair", ["aa"])],
        constraints=["removals cascade: a removal may expose a new adjacent pair"],
        failures=["Checking `stack[-1]` on an empty stack",
                  "Rescanning from the start after each removal, which is quadratic"],
        nudge="After a removal, the thing to compare against is whatever is now on top.",
        visual="a b b a c a : bb goes, then aa goes, leaving 'ca'.",
        pseudocode="""
            stack = []
            for each character:
                top matches it -> pop
                otherwise      -> push
            join what is left
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-monotonic-next-greater", title="The Rune of the Waiting Indices",
        realm=MINES, difficulty="GUIDED", family="monotonic_stack",
        pattern="STACK", scaffold_for="STACK: indices waiting to be answered",
        secondary=["ARRAY"],
        statement="""
            For each position in `nums`, return the first later value that is strictly
            greater than it, or -1 if there is none.

            The stack holds the INDICES of values still waiting for an answer, and the
            values at those indices never increase from bottom to top. When a bigger
            value arrives it settles every one of them that it beats — each in O(1),
            each exactly once, which is why the whole thing is linear rather than
            quadratic.
        """,
        fn_name="next_greater", params="nums", reference=_ref_next_greater,
        canonical="""
            def next_greater(nums):
                answer = [-1] * len(nums)
                stack = []
                for i, value in enumerate(nums):
                    while stack and nums[stack[-1]] < value:
                        answer[stack.pop()] = value
                    stack.append(i)
                return answer
        """,
        blanks=[("nums[stack[-1]] < value",
                 "the index waiting on top has finally been beaten"),
                ("answer[stack.pop()] = value",
                 "that waiting index has found its answer; it leaves the stack")],
        visible=[("mixed", [[2, 1, 2, 4, 3]]), ("ascending", [[1, 2, 3]])],
        hidden=[("descending", [[5, 4, 3]]), ("equal values", [[2, 2, 2]])],
        edges=[("empty", [[]]), ("single", [[7]]), ("one peak", [[1, 9, 1]])],
        constraints=["'greater' is strict, so equal values do not answer each other"],
        failures=["Using `<=`, which lets an equal value answer a waiting index",
                  "Pushing the value instead of the index, so `answer` cannot be filled"],
        nudge="Each index is pushed once and popped at most once. That is the whole "
              "complexity argument.",
        visual="[2 1 2 4 3] : the 4 settles the 2, the 1 and the 2 all at once.",
        pseudocode="""
            answer = all -1
            stack = []
            for each index i and value:
                while the top's value is smaller: that index's answer is value; pop
                push i
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-anagram-groups", title="The Rune of the Shared Signature",
        realm=WOOD, difficulty="GUIDED", family="anagrams",
        pattern="HASH_MAP", scaffold_for="HASH MAP: grouping by a computed key",
        secondary=["STRING", "SORTING"],
        statement="""
            Group the words of `words` so that words which are rearrangements of each
            other end up together. Return the groups in the order their first member
            appeared, each group's own words sorted.

            This is the archetype usually stated as "group the anagrams together", and
            every grouping problem is the same problem underneath: find a key that all
            members of a group share and no non-member does, then use a dict. For
            anagrams that key is the word's letters in sorted order.
        """,
        fn_name="anagram_groups", params="words", reference=_ref_anagram_groups,
        canonical="""
            def anagram_groups(words):
                groups = {}
                for word in words:
                    signature = "".join(sorted(word))
                    if signature not in groups:
                        groups[signature] = []
                    groups[signature].append(word)
                return [sorted(group) for group in groups.values()]
        """,
        blanks=[('"".join(sorted(word))',
                 "a signature every anagram of this word shares, and nothing else does"),
                ("groups[signature].append(word)",
                 "file the word under its signature")],
        visible=[("classic", [["eat", "tea", "tan", "ate", "nat", "bat"]]),
                 ("no groups", [["abc", "def"]])],
        hidden=[("all one group", [["ab", "ba", "ab"]]),
                ("single letters", [["a", "b", "a"]])],
        edges=[("empty", [[]]), ("one word", [["solo"]]),
               ("empty strings", [["", ""]])],
        constraints=["dicts preserve insertion order, which is what fixes the "
                     "order of the groups"],
        failures=["Using the word itself as the key, which groups nothing",
                  "Using a `set` of letters as the key, which merges 'aab' with 'ab'"],
        nudge="Two words are anagrams exactly when their sorted letters are equal. "
              "Equal things make good dict keys.",
        visual="eat -> 'aet', tea -> 'aet', tan -> 'ant'. The key does the grouping.",
        pseudocode="""
            groups = {}
            for each word:
                key = its letters sorted and joined
                append the word to groups[key]
            return each group, sorted
        """,
        time_complexity="O(n*m log m)", space_complexity="O(n*m)",
        complexity_choices=["O(n)", "O(n log n)", "O(n*m log m)", "O(n^2)"],
    ))

    P.append(rune(
        id="rp-string-initials", title="The Rune of the First Letters",
        realm=WOOD, difficulty="GUIDED", family="string_basics",
        pattern="STRING", scaffold_for="STRING: split, transform, join",
        statement="""
            Return the initials of `sentence`: the first character of each
            whitespace-separated word, capitalised, run together into one string.

            Three string operations in a row, and almost every text problem is some
            arrangement of them. `split()` with no argument is the one worth knowing —
            it collapses runs of whitespace and drops leading and trailing blanks, which
            is why the empty string comes out as the empty string rather than crashing.
        """,
        fn_name="initials", params="sentence", reference=_ref_initials,
        canonical="""
            def initials(sentence):
                letters = []
                for word in sentence.split():
                    letters.append(word[0].upper())
                return "".join(letters)
        """,
        blanks=[("word[0].upper()", "this word's first character, as a capital"),
                ('"".join(letters)',
                 "one string with nothing at all between the letters")],
        visible=[("plain", ["hello brave world"]), ("already capital", ["Ada Byron"])],
        hidden=[("one word", ["python"]), ("digits", ["3 blind mice"])],
        edges=[("empty", [""]), ("only spaces", ["   "]),
               ("ragged spacing", ["  a   b  "])],
        constraints=["`split()` with no argument handles the ragged spacing for you"],
        failures=["Using `split(' ')`, which yields empty strings for double spaces "
                  "and then `word[0]` raises IndexError",
                  "Returning a list instead of a string"],
        nudge="Reach for `.split()` with no argument. The no-argument form is the "
              "forgiving one.",
        visual="'hello brave world' -> ['hello','brave','world'] -> 'HBW'",
        pseudocode="""
            for each word in sentence.split():
                take word[0], uppercased
            join them with nothing between
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    return P


# ===========================================================================
# SECTION 3 — GRIDS, MAZES AND GRAPHS
#
# Matrix rotation is on the reported-archetype list and opened at MEDIUM. Every
# grid and graph family opened at EASY except `graph_cycle` and `graph_paths`,
# which opened at HARD — a player's first ever cycle detection was a HARD.
# ===========================================================================

CITADEL = "matrix_citadel"
WASTES = "graph_wastes"


def _grids_and_graphs() -> list:
    P: list = []

    P.append(rune(
        id="rp-matrix-columns", title="The Rune of the Standing Columns",
        realm=CITADEL, difficulty="GUIDED", family="matrix_traverse",
        pattern="MATRIX", scaffold_for="MATRIX: row index versus column index",
        secondary=["ARRAY"],
        statement="""
            Return the sum of each column of `grid`, left to right. `grid` is a list of
            equal-length rows.

            Summing rows is easy because a row is already a list. Columns are the
            useful exercise, because the values you need are scattered one per row and
            the only thing holding them together is a shared second index.
        """,
        fn_name="column_sums", params="grid", reference=_ref_column_sums,
        canonical="""
            def column_sums(grid):
                if not grid:
                    return []
                width = len(grid[0])
                totals = [0] * width
                for row in grid:
                    for c in range(width):
                        totals[c] += row[c]
                return totals
        """,
        blanks=[("len(grid[0])", "how many columns the grid has"),
                ("totals[c] += row[c]",
                 "add this cell into the running total for its own column")],
        visible=[("square", [[[1, 2], [3, 4]]]),
                 ("wide", [[[1, 2, 3], [4, 5, 6]]])],
        hidden=[("single row", [[[7, 8, 9]]]),
                ("single column", [[[1], [2], [3]]])],
        edges=[("empty grid", [[]]), ("empty rows", [[[], []]]),
               ("negatives", [[[-1, 2], [1, -2]]])],
        constraints=["rows all have the same length", "the grid may be empty"],
        failures=["Indexing `grid[c][r]`, which transposes the answer",
                  "Reading `len(grid[0])` before checking the grid is non-empty"],
        nudge="`grid[r][c]` is row first, column second. Always.",
        visual="Column 0 is grid[0][0], grid[1][0], grid[2][0] — one cell per row.",
        pseudocode="""
            empty grid -> []
            totals = one zero per column
            for each row:
                for each column index c:
                    totals[c] += row[c]
        """,
        time_complexity="O(r*c)", space_complexity="O(c)",
        complexity_choices=["O(r)", "O(c)", "O(r*c)", "O(r^2)"],
    ))

    P.append(rune(
        id="rp-matrix-rotate", title="The Rune of the Quarter Turn",
        realm=CITADEL, difficulty="GUIDED", family="matrix_transform",
        pattern="MATRIX", scaffold_for="MATRIX: a rotation is two simpler moves",
        secondary=["ARRAY"],
        statement="""
            Return `grid` rotated 90 degrees clockwise, as a new grid.

            Index arithmetic for a rotation is easy to get subtly wrong and hard to
            check by eye. So do not do any. A clockwise quarter turn is exactly two
            moves you can already picture: reflect the grid along its main diagonal so
            rows become columns, then reverse each of the new rows.
        """,
        fn_name="rotate_clockwise", params="grid", reference=_ref_rotate_clockwise,
        canonical="""
            def rotate_clockwise(grid):
                if not grid:
                    return []
                turned = [list(row) for row in zip(*grid)]
                for row in turned:
                    row.reverse()
                return turned
        """,
        blanks=[("zip(*grid)", "rows become columns — this is the transpose"),
                ("row.reverse()",
                 "reverse each new row, so the old bottom-left ends up top-left")],
        visible=[("two by two", [[[1, 2], [3, 4]]]),
                 ("three by three", [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]])],
        hidden=[("wide becomes tall", [[[1, 2, 3], [4, 5, 6]]]),
                ("single row", [[[1, 2, 3]]])],
        edges=[("empty", [[]]), ("single cell", [[[5]]]),
               ("single column", [[[1], [2]]])],
        constraints=["a new grid is returned; the input is not modified"],
        failures=["Reversing before transposing, which turns the grid the other way",
                  "Forgetting `list(...)` and returning tuples from `zip`",
                  "Assuming the grid is square — a 2x3 rotates into a 3x2"],
        nudge="Transpose, then reverse each row. Swap those two steps and you have "
              "rotated counter-clockwise instead.",
        visual="1 2 / 3 4  -transpose->  1 3 / 2 4  -reverse rows->  3 1 / 4 2",
        pseudocode="""
            empty -> []
            turned = the transpose, as lists
            reverse each row of turned
            return turned
        """,
        time_complexity="O(r*c)", space_complexity="O(r*c)",
        complexity_choices=["O(r)", "O(r+c)", "O(r*c)", "O((r*c)^2)"],
    ))

    P.append(code_problem(
        id="rp-matrix-rotate-counter", title="The Other Quarter Turn",
        realm=CITADEL, difficulty="TUTORIAL", family="matrix_transform",
        pattern="MATRIX", secondary=["ARRAY"],
        prerequisites=["rp-matrix-rotate"],
        statement="""
            Return `grid` rotated 90 degrees counter-clockwise, as a new grid.

            You have the clockwise version. This one uses the same two moves, but the
            second one acts on a different thing: clockwise reverses each row,
            counter-clockwise reverses the order of the rows. Being able to say which
            is which — without drawing it — is the actual thing being tested.
        """,
        fn_name="rotate_counter", params="grid", reference=_ref_rotate_counter,
        canonical="""
            def rotate_counter(grid):
                if not grid:
                    return []
                turned = [list(row) for row in zip(*grid)]
                turned.reverse()
                return turned
        """,
        starter_code="""
            def rotate_counter(grid):
                # 1. empty grid -> []
                # 2. transpose, exactly as the clockwise version did
                # 3. now reverse the ORDER OF THE ROWS — not the contents of each
                #    row, which is what the clockwise version reversed
                # 4. hand back lists, not the tuples zip gives you
                pass
        """,
        visible=[("two by two", [[[1, 2], [3, 4]]]),
                 ("three by three", [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]])],
        hidden=[("wide becomes tall", [[[1, 2, 3], [4, 5, 6]]]),
                ("single row", [[[1, 2, 3]]])],
        edges=[("empty", [[]]), ("single cell", [[[5]]]),
               ("single column", [[[1], [2]]])],
        constraints=["a new grid is returned; the input is not modified"],
        failures=["Reversing the contents of each row, which is the clockwise turn",
                  "Applying the clockwise recipe unchanged and hoping"],
        nudge="Both turns start with the transpose. Clockwise then reverses each row; "
              "counter-clockwise reverses the order of the rows.",
        visual="1 2 / 3 4  -transpose->  1 3 / 2 4  -reverse the row order->  2 4 / 1 3",
        pseudocode="""
            empty -> []
            turned = the transpose, as lists
            reverse the order of turned's rows
            return turned
        """,
        time_complexity="O(r*c)", space_complexity="O(r*c)",
        complexity_choices=["O(r)", "O(r+c)", "O(r*c)", "O((r*c)^2)"],
    ))

    P.append(rune(
        id="rp-grid-region", title="The Rune of the Spreading Stain",
        realm=WASTES, difficulty="GUIDED", family="grid_traverse",
        pattern="DFS", scaffold_for="DFS: mark before you walk",
        secondary=["MATRIX", "SET"],
        statement="""
            Return how many cells belong to the connected region containing
            `grid[r][c]`, where two cells connect if they share an edge and hold the
            same value. A region of zeroes has size 0 by definition.

            Depth-first search on a grid is four lines of neighbour arithmetic and one
            rule that people get wrong: a cell is marked visited when it is *queued*,
            not when it is *processed*. Mark it late and the same cell enters the stack
            from two directions and is counted twice.
        """,
        fn_name="region_size", params="grid, r, c", reference=_ref_region_size,
        canonical="""
            def region_size(grid, r, c):
                if not grid or grid[r][c] == 0:
                    return 0
                target = grid[r][c]
                stack = [(r, c)]
                seen = {(r, c)}
                size = 0
                while stack:
                    row, col = stack.pop()
                    size += 1
                    neighbours = [(row - 1, col), (row + 1, col),
                                  (row, col - 1), (row, col + 1)]
                    for nr, nc in neighbours:
                        if not (0 <= nr < len(grid) and 0 <= nc < len(grid[0])):
                            continue
                        if (nr, nc) in seen or grid[nr][nc] != target:
                            continue
                        seen.add((nr, nc))
                        stack.append((nr, nc))
                return size
        """,
        blanks=[("(nr, nc) in seen or grid[nr][nc] != target",
                 "already visited, or simply not part of this region"),
                ("seen.add((nr, nc))",
                 "mark it NOW, before it is pushed — mark it later and it is "
                 "counted twice")],
        visible=[("plus shape", [[[1, 1, 0], [0, 1, 0], [0, 1, 1]], 0, 0]),
                 ("single cell", [[[1, 0], [0, 1]], 0, 0])],
        hidden=[("whole grid", [[[2, 2], [2, 2]], 1, 1]),
                ("value two region", [[[2, 0], [2, 3]], 0, 0])],
        edges=[("start on a zero", [[[0, 1], [1, 1]], 0, 0]),
               ("one by one", [[[9]], 0, 0]),
               ("bottom right corner", [[[1, 1], [1, 1]], 1, 1])],
        constraints=["four-way connectivity only; diagonals do not connect",
                     "a zero cell is not part of any region"],
        failures=["Marking a cell visited when it is popped rather than when it is "
                  "pushed, which double-counts",
                  "Checking the bounds after indexing rather than before"],
        nudge="Bounds, then visited, then value. In that order — the first one "
              "protects the other two.",
        visual="Push a cell and it is spoken for. Nothing may push it again.",
        pseudocode="""
            start cell is 0 -> 0
            stack = [start], seen = {start}, size = 0
            while the stack is not empty:
                pop a cell, count it
                for each of its four neighbours:
                    out of bounds -> skip
                    seen, or wrong value -> skip
                    mark seen, push
        """,
        time_complexity="O(r*c)", space_complexity="O(r*c)",
        complexity_choices=["O(r+c)", "O(r*c)", "O((r*c)^2)", "O(log(r*c))"],
    ))

    P.append(rune(
        id="rp-grid-bfs-steps", title="The Rune of the Expanding Ring",
        realm=WASTES, difficulty="GUIDED", family="grid_bfs",
        pattern="BFS", scaffold_for="BFS: the oldest entry first",
        secondary=["MATRIX", "QUEUE"],
        statement="""
            `grid` holds 0 for open ground and 1 for wall. Starting at the top-left
            corner and moving only up, down, left or right through open cells, return
            the fewest steps needed to stand on `(target_row, target_col)`, or -1 if it
            cannot be reached.

            Everything about this problem is in one method call. Take the OLDEST entry
            from the frontier and the search expands in rings of equal distance, so the
            first time you arrive anywhere is by a shortest route. Take the newest
            instead and you have written a depth-first search that returns some path,
            confidently, and it is the wrong one.
        """,
        fn_name="shortest_steps", params="grid, target_row, target_col",
        reference=_ref_shortest_steps,
        canonical="""
            from collections import deque


            def shortest_steps(grid, target_row, target_col):
                if not grid or grid[0][0] == 1:
                    return -1
                frontier = deque([(0, 0, 0)])
                seen = {(0, 0)}
                while frontier:
                    row, col, steps = frontier.popleft()
                    if (row, col) == (target_row, target_col):
                        return steps
                    moves = [(row - 1, col), (row + 1, col),
                             (row, col - 1), (row, col + 1)]
                    for nr, nc in moves:
                        if not (0 <= nr < len(grid) and 0 <= nc < len(grid[0])):
                            continue
                        if (nr, nc) in seen or grid[nr][nc] == 1:
                            continue
                        seen.add((nr, nc))
                        frontier.append((nr, nc, steps + 1))
                return -1
        """,
        blanks=[("frontier.popleft()",
                 "BFS takes the OLDEST entry — this one method call is why the first "
                 "arrival is the shortest"),
                ("frontier.append((nr, nc, steps + 1))",
                 "queue the neighbour at one step further out than where we stand")],
        visible=[("clear path", [[[0, 0], [0, 0]], 1, 1]),
                 ("around a wall", [[[0, 1], [0, 0]], 0, 1])],
        hidden=[("blocked", [[[0, 1], [1, 0]], 1, 1]),
                ("already there", [[[0, 0]], 0, 0])],
        edges=[("start is a wall", [[[1, 0], [0, 0]], 1, 1]),
               ("empty grid", [[], 0, 0]),
               ("single open cell", [[[0]], 0, 0])],
        constraints=["four-way movement", "the start is the top-left corner"],
        failures=["Using `pop()` instead of `popleft()`, which silently becomes DFS "
                  "and returns a path that is not shortest",
                  "Marking cells seen when they are dequeued, which queues duplicates"],
        nudge="A queue is oldest-out. A stack is newest-out. Only one of them "
              "measures distance.",
        visual="Ring 0 is the start. Ring 1 is everything one step away. Nothing in "
               "ring 2 is ever reached before ring 1 is exhausted.",
        pseudocode="""
            start blocked -> -1
            frontier = [(0, 0, 0 steps)], seen = {(0,0)}
            while the frontier is not empty:
                take the OLDEST entry
                is it the target -> its step count is the answer
                for each open, unseen neighbour: mark and queue at steps + 1
            -> -1
        """,
        time_complexity="O(r*c)", space_complexity="O(r*c)",
        complexity_choices=["O(r+c)", "O(r*c)", "O((r*c)^2)", "O(log(r*c))"],
    ))

    P.append(rune(
        id="rp-graph-reachable", title="The Rune of Everything Downstream",
        realm=WASTES, difficulty="GUIDED", family="graph_traverse",
        pattern="DFS", scaffold_for="DFS: a visited set is not optional",
        secondary=["SET"],
        statement="""
            `graph` maps each node to the list of nodes it points at. Return every node
            reachable from `start`, including `start` itself, sorted.

            A graph is not a tree: it has cycles, and a traversal without a visited set
            does not return a wrong answer, it runs forever. The set is the algorithm.
        """,
        fn_name="reachable", params="graph, start", reference=_ref_reachable,
        canonical="""
            def reachable(graph, start):
                seen = {start}
                stack = [start]
                while stack:
                    node = stack.pop()
                    for neighbour in graph.get(node, []):
                        if neighbour not in seen:
                            seen.add(neighbour)
                            stack.append(neighbour)
                return sorted(seen)
        """,
        blanks=[("stack.pop()",
                 "depth-first always continues from the most recent place it reached"),
                ("neighbour not in seen",
                 "we have not already committed to walking this one")],
        visible=[("chain", [{"a": ["b"], "b": ["c"], "c": []}, "a"]),
                 ("branching", [{"a": ["b", "c"], "b": [], "c": []}, "a"])],
        hidden=[("cycle", [{"a": ["b"], "b": ["a"]}, "a"]),
                ("disconnected", [{"a": [], "b": ["c"], "c": []}, "b"])],
        edges=[("unknown start", [{"a": ["b"]}, "z"]),
               ("empty graph", [{}, "a"]),
               ("self loop", [{"a": ["a"]}, "a"])],
        constraints=["a node with no outgoing edges may be missing from the dict"],
        failures=["Omitting the visited set, which never terminates on a cycle",
                  "Indexing `graph[node]` and raising KeyError on a leaf node"],
        nudge="`graph.get(node, [])` is what makes a missing key mean 'no edges'.",
        visual="a -> b -> a : without `seen`, this loop has no end.",
        pseudocode="""
            seen = {start}, stack = [start]
            while the stack is not empty:
                pop a node
                for each neighbour not already seen: mark it and push it
            return the seen set, sorted
        """,
        time_complexity="O(V+E)", space_complexity="O(V)",
        complexity_choices=["O(V)", "O(E)", "O(V+E)", "O(V*E)"],
    ))

    P.append(rune(
        id="rp-graph-hops", title="The Rune of the Fewest Hops",
        realm=WASTES, difficulty="GUIDED", family="graph_shortest",
        pattern="BFS", scaffold_for="BFS: distance comes for free",
        secondary=["QUEUE", "SET"],
        statement="""
            `graph` maps each node to the nodes it points at, and every edge costs the
            same. Return the fewest hops from `start` to `goal`, 0 if they are the same
            node, or -1 if `goal` cannot be reached.

            Unweighted means BFS, and BFS means the distance is not something you
            compute afterwards — you carry it alongside each node as you queue it.
        """,
        fn_name="hops", params="graph, start, goal", reference=_ref_hops,
        canonical="""
            from collections import deque


            def hops(graph, start, goal):
                if start == goal:
                    return 0
                frontier = deque([(start, 0)])
                seen = {start}
                while frontier:
                    node, distance = frontier.popleft()
                    for neighbour in graph.get(node, []):
                        if neighbour in seen:
                            continue
                        if neighbour == goal:
                            return distance + 1
                        seen.add(neighbour)
                        frontier.append((neighbour, distance + 1))
                return -1
        """,
        blanks=[("neighbour == goal",
                 "we have just stepped onto the destination, one hop from here"),
                ("frontier.append((neighbour, distance + 1))",
                 "queue it carrying its own distance, one further out")],
        visible=[("chain", [{"a": ["b"], "b": ["c"]}, "a", "c"]),
                 ("direct", [{"a": ["b"]}, "a", "b"])],
        hidden=[("shortcut wins", [{"a": ["b", "d"], "b": ["c"], "d": ["c"]}, "a", "c"]),
                ("unreachable", [{"a": ["b"], "c": []}, "a", "c"])],
        edges=[("same node", [{"a": ["b"]}, "a", "a"]),
               ("empty graph", [{}, "a", "b"]),
               ("cycle", [{"a": ["b"], "b": ["a"]}, "a", "b"])],
        constraints=["all edges cost the same, which is what makes BFS correct"],
        failures=["Returning the size of the frontier instead of the carried distance",
                  "Checking for the goal only when a node is dequeued, which still "
                  "works but does one more level of work than it needs to"],
        nudge="Every queued entry carries how far it is. Nothing has to be "
              "reconstructed later.",
        visual="(a,0) -> (b,1) -> (c,2). The number rides along with the node.",
        pseudocode="""
            start is the goal -> 0
            queue [(start, 0)], seen {start}
            while the queue is not empty:
                take the oldest (node, distance)
                for each unseen neighbour:
                    it is the goal -> distance + 1
                    otherwise mark it and queue (neighbour, distance + 1)
            -> -1
        """,
        time_complexity="O(V+E)", space_complexity="O(V)",
        complexity_choices=["O(V)", "O(E)", "O(V+E)", "O(V*E)"],
    ))

    P.append(rune(
        id="rp-graph-cycle-walk", title="The Rune of the Returning Road",
        realm=WASTES, difficulty="GUIDED", family="graph_cycle",
        pattern="SET", scaffold_for="SET: have I stood here before",
        secondary=["SIMULATION"],
        statement="""
            `nxt` is a list where `nxt[i]` is the single node reached from node `i`, or
            -1 for a dead end. Starting at `start`, return True if the walk ever
            revisits a node.

            One outgoing edge per node makes the walk a single road, so cycle detection
            needs no recursion and no stack — only a record of where you have been. If
            you arrive somewhere you have already stood, the road is a loop.
        """,
        fn_name="has_cycle", params="nxt, start", reference=_ref_has_cycle,
        canonical="""
            def has_cycle(nxt, start):
                seen = set()
                node = start
                while node != -1:
                    if node in seen:
                        return True
                    seen.add(node)
                    node = nxt[node]
                return False
        """,
        blanks=[("node in seen",
                 "we have arrived somewhere we have already stood"),
                ("node = nxt[node]", "take this node's single outgoing edge")],
        visible=[("loop", [[1, 2, 0], 0]), ("dead end", [[1, 2, -1], 0])],
        hidden=[("self loop", [[0], 0]),
                ("tail into a loop", [[1, 2, 3, 1], 0])],
        edges=[("starts at a dead end", [[-1], 0]),
               ("loop not on the path", [[-1, 2, 1], 0]),
               ("two node cycle", [[1, 0], 1])],
        constraints=["every node has at most one outgoing edge",
                     "-1 means the road stops"],
        failures=["Recording the node after following the edge, which misses a "
                  "self loop",
                  "Bounding the walk by a step count instead of by a visited set"],
        nudge="Mark where you are standing, then move. Not the other way round.",
        visual="0 -> 1 -> 2 -> 0 : the second sighting of 0 is the proof.",
        pseudocode="""
            seen = empty set, node = start
            while the node is not -1:
                already seen -> True
                mark it, follow its edge
            -> False
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-graph-count-paths", title="The Rune of Every Road There",
        realm=WASTES, difficulty="GUIDED", family="graph_paths",
        pattern="RECURSION", scaffold_for="RECURSION: a base case and a sum",
        secondary=["DFS"],
        statement="""
            `graph` maps each node to the nodes it points at, and contains no cycles.
            Return how many distinct paths lead from `start` to `goal`.

            Counting paths is the cleanest recursion there is, because the recursive
            statement is the whole solution: the number of paths from here is the sum
            of the number of paths from each place you can go next. All that is left is
            deciding what counts as arriving.
        """,
        fn_name="count_paths", params="graph, start, goal",
        reference=_ref_count_paths,
        canonical="""
            def count_paths(graph, start, goal):
                if start == goal:
                    return 1
                total = 0
                for neighbour in graph.get(start, []):
                    total += count_paths(graph, neighbour, goal)
                return total
        """,
        blanks=[("return 1", "arriving at the goal is exactly one completed path"),
                ("count_paths(graph, neighbour, goal)",
                 "every path onward from this neighbour is also a path from here")],
        visible=[("two roads", [{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []},
                                "a", "d"]),
                 ("single road", [{"a": ["b"], "b": ["c"], "c": []}, "a", "c"])],
        hidden=[("diamond twice over",
                 [{"a": ["b", "c"], "b": ["d", "e"], "c": ["e"], "d": ["f"],
                   "e": ["f"], "f": []}, "a", "f"]),
                ("no road", [{"a": ["b"], "b": [], "c": []}, "a", "c"])],
        edges=[("start is the goal", [{"a": ["b"]}, "a", "a"]),
               ("empty graph", [{}, "a", "b"]),
               ("dead ends only", [{"a": ["b", "c"], "b": [], "c": []}, "a", "d"])],
        constraints=["the graph is acyclic, so the recursion always terminates"],
        failures=["Returning the count of neighbours instead of summing their counts",
                  "Adding a visited set, which is correct for reachability and wrong "
                  "here — two different paths may legitimately share a node"],
        nudge="Write the sentence 'paths from X = sum of paths from each neighbour' "
              "and then type it.",
        visual="a->b->d and a->c->d are two paths, and they share d. Both count.",
        pseudocode="""
            here is the goal -> 1
            otherwise -> sum of count_paths(neighbour, goal) for each neighbour
        """,
        time_complexity="O(paths)", space_complexity="O(V)",
        complexity_choices=["O(V)", "O(V+E)", "O(paths)", "O(V^2)"],
    ))

    return P


# ===========================================================================
# SECTION 4 — TREES
#
# `tree_serialize` is on the reported-archetype list and its ONLY encounter was
# HARD. `bst` and `tree_paths` and `tree_bfs` all opened at EASY. A tree is the
# first structure where the base case is `None` rather than an empty list, and
# that deserves a rung of its own.
# ===========================================================================

CANOPY = "binary_tree_canopy"


def _trees() -> list:
    P: list = []

    P.append(rune(
        id="rp-tree-level-order", title="The Rune of the Rising Levels",
        difficulty="GUIDED", family="tree_bfs", pattern="BFS",
        scaffold_for="BFS: a tree is a graph that cannot loop",
        secondary=["TREE", "QUEUE"], **TREE,
        reference=tree_ref(_ref_level_order),
        statement="""
            Return every value in the tree in level order: the root, then everything one
            step below it, then everything two steps below, left to right within each
            level.

            A tree needs no visited set — there is exactly one route to each node — so
            what is left is the queue, and the queue is the whole of breadth-first
            search. Children join the back; work comes off the front.
        """,
        fn_name="level_order", params="root",
        canonical="""
            from collections import deque


            def level_order(root):
                if root is None:
                    return []
                out = []
                frontier = deque([root])
                while frontier:
                    node = frontier.popleft()
                    out.append(node.val)
                    if node.left is not None:
                        frontier.append(node.left)
                    if node.right is not None:
                        frontier.append(node.right)
                return out
        """,
        blanks=[("frontier.popleft()",
                 "take the OLDEST node — that is what keeps the levels in order"),
                ("frontier.append(node.right)",
                 "the right child joins the BACK of the queue, behind its sibling")],
        visible=[("full", [[1, 2, 3]]), ("deeper", [[1, 2, 3, 4, 5]])],
        hidden=[("right leaning", [[1, None, 2]]),
                ("left leaning", [[1, 2, None, 3]])],
        edges=[("empty", [[]]), ("single node", [[7]]),
               ("ragged", [[1, 2, 3, None, 4]])],
        constraints=["the level-order list may contain None for an absent child"],
        failures=["Using `pop()` and producing a depth-first order instead",
                  "Queueing `None` children and then reading `.val` off them"],
        nudge="Append the children, then move on. Never recurse here.",
        visual="Queue: [1] -> [2,3] -> [3,4,5] -> ... Each level is fully drained "
               "before the next begins.",
        pseudocode="""
            empty tree -> []
            queue = [root]
            while the queue is not empty:
                take the oldest node, record its value
                queue its left child if it exists
                queue its right child if it exists
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-tree-path-sum", title="The Rune of the Dwindling Debt",
        difficulty="GUIDED", family="tree_paths", pattern="TREE",
        scaffold_for="TREE: pass the remainder down", secondary=["RECURSION", "DFS"],
        **TREE, reference=tree_ref(_ref_has_path_sum),
        statement="""
            Return True when some root-to-leaf path through the tree has values summing
            to `target`.

            There are two ways to carry a running total through a recursion, and only
            one of them is pleasant. Do not accumulate upward — subtract downward. Each
            node spends its own value and asks its children for the rest, so by the time
            you reach a leaf the question has become a single comparison.
        """,
        fn_name="has_path_sum", params="root, target",
        canonical="""
            def has_path_sum(root, target):
                if root is None:
                    return False
                if root.left is None and root.right is None:
                    return root.val == target
                remaining = target - root.val
                return (has_path_sum(root.left, remaining)
                        or has_path_sum(root.right, remaining))
        """,
        blanks=[("root.val == target",
                 "at a leaf the whole path works out exactly when this holds"),
                ("target - root.val",
                 "what the rest of the path still has to supply")],
        visible=[("hit", [[5, 4, 8], 9]), ("miss", [[5, 4, 8], 100])],
        hidden=[("deeper path", [[1, 2, 3, 4], 7]),
                ("negative values", [[1, -2, 3], -1])],
        edges=[("empty tree", [[], 0]), ("single node hit", [[7], 7]),
               ("single node miss", [[7], 0])],
        constraints=["the path must end at a LEAF, not at any node",
                     "an empty tree has no paths at all, including for target 0"],
        failures=["Returning True at an internal node whose running total happens "
                  "to match",
                  "Treating a node with one child as a leaf"],
        nudge="A leaf is a node with NO left child and NO right child. Check both.",
        visual="target 9, root 5 : the children are asked for 4, not for 9.",
        pseudocode="""
            no node -> False
            at a leaf -> does this value equal what is left
            otherwise -> ask either child for (target - this value)
        """,
        time_complexity="O(n)", space_complexity="O(h)",
        complexity_choices=["O(log n)", "O(n)", "O(n log n)", "O(n^2)"],
    ))

    P.append(rune(
        id="rp-bst-bounds", title="The Rune of the Narrowing Window",
        difficulty="GUIDED", family="bst", pattern="TREE",
        scaffold_for="TREE: what a node inherits from its ancestors",
        secondary=["RECURSION", "BINARY_SEARCH"], **TREE,
        reference=tree_ref(_ref_is_valid_bst),
        statement="""
            Return True when the tree is a valid binary search tree: every value in a
            node's left subtree is strictly smaller than it, and every value in its
            right subtree strictly larger.

            The trap here is famous. Comparing each node only against its immediate
            children accepts trees that are obviously wrong, because a node four levels
            down can violate an ancestor it never meets. So the constraint has to travel
            downward: every node inherits a permitted range from above and narrows it
            for its own children.
        """,
        fn_name="is_valid_bst", params="root, low=None, high=None",
        canonical="""
            def is_valid_bst(root, low=None, high=None):
                if root is None:
                    return True
                if low is not None and root.val <= low:
                    return False
                if high is not None and root.val >= high:
                    return False
                return (is_valid_bst(root.left, low, root.val)
                        and is_valid_bst(root.right, root.val, high))
        """,
        blanks=[("root.val <= low",
                 "this node is not strictly above the floor its ancestors imposed"),
                ("is_valid_bst(root.left, low, root.val)",
                 "the left subtree keeps the same floor but takes THIS node as its "
                 "new ceiling")],
        visible=[("valid", [[2, 1, 3]]), ("invalid child", [[2, 3, 1]])],
        hidden=[("deep violation", [[5, 1, 7, None, None, 3, 8]]),
                ("valid and deep", [[8, 4, 12, 2, 6, 10, 14]])],
        edges=[("empty", [[]]), ("single node", [[1]]),
               ("duplicate value", [[2, 2]])],
        constraints=["strictly smaller and strictly larger; equal values are invalid"],
        failures=["Comparing a node only against its own two children, which accepts "
                  "a value that violates a distant ancestor",
                  "Using `<` and `>` where the bound is inclusive, accepting duplicates"],
        nudge="Ask what a node is ALLOWED to be, not what its children look like.",
        visual="5 with a right child 7 whose left child is 3 : 3 is inside 7's "
               "subtree but must still beat 5. Only an inherited bound catches it.",
        pseudocode="""
            no node -> True
            below the inherited floor, or above the inherited ceiling -> False
            left subtree: same floor, this value becomes the ceiling
            right subtree: this value becomes the floor, same ceiling
        """,
        time_complexity="O(n)", space_complexity="O(h)",
        complexity_choices=["O(log n)", "O(n)", "O(n log n)", "O(n^2)"],
    ))

    P.append(code_problem(
        id="rp-bst-inorder", title="The Walk That Sorts Itself",
        difficulty="TUTORIAL", family="bst", pattern="TREE",
        secondary=["RECURSION", "SORTING"], **TREE,
        reference=tree_ref(_ref_is_valid_bst),
        prerequisites=["rp-bst-bounds"],
        statement="""
            Same question, second proof: return True when the tree is a valid binary
            search tree — but decide it by walking the tree in order rather than by
            passing bounds down.

            An in-order walk of a binary search tree visits its values in ascending
            order. That is not a coincidence, it is the definition restated, and it is
            the fact worth remembering: the moment a problem says 'k-th smallest' or
            'sorted output' about a BST, this walk is the answer.
        """,
        fn_name="is_bst_inorder", params="root",
        canonical="""
            def is_bst_inorder(root):
                values = []

                def walk(node):
                    if node is None:
                        return
                    walk(node.left)
                    values.append(node.val)
                    walk(node.right)

                walk(root)
                for i in range(len(values) - 1):
                    if values[i] >= values[i + 1]:
                        return False
                return True
        """,
        starter_code="""
            def is_bst_inorder(root):
                # 1. collect the values with an IN-ORDER walk:
                #    left subtree, then this node, then right subtree
                # 2. the tree is a BST exactly when that list is STRICTLY ascending
                # 3. equal neighbours mean invalid, so compare with >=
                pass
        """,
        visible=[("valid", [[2, 1, 3]]), ("invalid child", [[2, 3, 1]])],
        hidden=[("deep violation", [[5, 1, 7, None, None, 3, 8]]),
                ("valid and deep", [[8, 4, 12, 2, 6, 10, 14]])],
        edges=[("empty", [[]]), ("single node", [[1]]),
               ("duplicate value", [[2, 2]])],
        constraints=["strictly ascending; equal neighbours are invalid"],
        failures=["Walking node-left-right (pre-order), which is not sorted",
                  "Using `>` and accepting duplicate values"],
        nudge="Left, self, right. Any other order loses the property entirely.",
        visual="8 4 12 2 6 10 14 in order is 2 4 6 8 10 12 14 — ascending, so valid.",
        pseudocode="""
            values = []
            walk(node): walk left; append node's value; walk right
            return whether values is strictly ascending
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="rp-tree-serialize", title="The Rune of the Written Tree",
        difficulty="GUIDED", family="tree_serialize", pattern="TREE",
        scaffold_for="TREE: shape has to be written down too",
        secondary=["RECURSION", "DFS"], **TREE,
        reference=tree_ref(_ref_serialize),
        statement="""
            Flatten the tree into a list of tokens: each node's value as a string, in
            pre-order, with the marker `"#"` standing in for every absent child.

            The markers are the entire point and the reason this is not just a
            traversal. A bare pre-order list of values does not determine a tree — two
            different trees produce the same one. Writing down the gaps as well makes
            the output unambiguous, which is what lets it be read back later.
        """,
        fn_name="serialize", params="root",
        canonical="""
            def serialize(root):
                out = []

                def walk(node):
                    if node is None:
                        out.append("#")
                        return
                    out.append(str(node.val))
                    walk(node.left)
                    walk(node.right)

                walk(root)
                return out
        """,
        blanks=[('out.append("#")',
                 "an absent child still has to occupy a slot in the output"),
                ("walk(node.right)",
                 "then everything on the right, after the left is fully written")],
        visible=[("full", [[1, 2, 3]]), ("right leaning", [[1, None, 2]])],
        hidden=[("left leaning", [[1, 2]]), ("deeper", [[1, 2, 3, 4, 5]])],
        edges=[("empty", [[]]), ("single node", [[7]]),
               ("negative value", [[-3, -4]])],
        constraints=["values are written as strings", "the marker is exactly \"#\""],
        failures=["Emitting nothing for an absent child, which makes the output "
                  "ambiguous and unreadable",
                  "Emitting the integer rather than `str(...)`"],
        nudge="Write the node, then the left side, then the right side — and write "
               "something for the sides that are not there.",
        visual="1 with only a right child 2 -> ['1', '#', '2', '#', '#']",
        pseudocode="""
            walk(node):
                no node -> write "#" and stop
                write str(node.val)
                walk left
                walk right
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(code_problem(
        id="rp-tree-deserialize", title="The Tree Read Back",
        realm=CANOPY, difficulty="TUTORIAL", family="tree_serialize",
        pattern="TREE", secondary=["RECURSION"],
        preamble=TREE_PREAMBLE, result_adapter="tree",
        reference=_ref_deserialize, prerequisites=["rp-tree-serialize"],
        statement="""
            Read back what the previous encounter wrote. Given a list of tokens in
            pre-order with `"#"` for absent children, rebuild the tree and return its
            root.

            The tokens arrive in exactly the order a pre-order walk consumes them, so
            the reader is the writer run backwards: take one token, and if it is a
            value, the next tokens are its left subtree followed by its right subtree.
            The only piece of state is a cursor saying how far through the list you
            are — and it has to be shared by every recursive call, not copied into it.
        """,
        fn_name="deserialize", params="tokens",
        canonical="""
            class Cursor:
                def __init__(self):
                    self.at = 0


            def deserialize(tokens):
                if not tokens:
                    return None
                cursor = Cursor()

                def build():
                    token = tokens[cursor.at]
                    cursor.at += 1
                    if token == "#":
                        return None
                    node = TreeNode(int(token))
                    node.left = build()
                    node.right = build()
                    return node

                return build()
        """,
        starter_code="""
            def deserialize(tokens):
                # `TreeNode` already exists. You need:
                # 1. a cursor into `tokens` that ALL the recursive calls share
                # 2. build(): read one token and advance the cursor
                # 3. "#" -> this child is absent, return None
                # 4. otherwise make a TreeNode, then build its left, then its right
                #    (that order is not optional: it is the order they were written)
                # 5. empty token list -> None
                pass
        """,
        visible=[("full", [["1", "2", "#", "#", "3", "#", "#"]]),
                 ("right leaning", [["1", "#", "2", "#", "#"]])],
        hidden=[("left leaning", [["1", "2", "#", "#", "#"]]),
                ("deeper", [["1", "2", "4", "#", "#", "5", "#", "#", "3", "#", "#"]])],
        edges=[("empty", [[]]), ("just a marker", [["#"]]),
               ("single node", [["7", "#", "#"]])],
        constraints=["the token list is always well formed",
                     "values are strings and need converting"],
        failures=["Passing the cursor as an integer argument, so each call advances "
                  "its own private copy and the tree comes out wrong",
                  "Building the right subtree before the left"],
        nudge="A local integer will not work — the recursion needs ONE cursor that "
              "every call can move. A tiny object, a list of one, or `nonlocal`.",
        visual="['1','2','#','#','3','#','#'] : the '2' consumes the two '#' after "
               "it, and only then does the '3' become the root's right child.",
        pseudocode="""
            empty -> None
            cursor at 0
            build():
                take the token at the cursor, advance it
                "#" -> None
                otherwise: node = TreeNode(value); node.left = build();
                           node.right = build(); return node
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(code_problem(
        id="rp-tree-round-trip", title="Written, Read, Unchanged",
        difficulty="EASY", family="tree_serialize", pattern="TREE",
        secondary=["RECURSION", "TESTING"], **TREE, result_adapter="tree",
        reference=_ref_round_trip,
        prerequisites=["rp-tree-serialize", "rp-tree-deserialize"],
        statement="""
            Put the two halves together: serialise the tree to tokens, rebuild it from
            those tokens, and return the rebuilt root. The result must be a genuinely
            new tree that is identical in shape and values to the one you were given.

            This is the encounter that proves the format. A serialiser nobody has run a
            round trip through is not known to work — it is known to produce output.
        """,
        fn_name="round_trip", params="root",
        canonical="""
            def round_trip(root):
                tokens = []

                def write(node):
                    if node is None:
                        tokens.append("#")
                        return
                    tokens.append(str(node.val))
                    write(node.left)
                    write(node.right)

                write(root)

                position = [0]

                def read():
                    token = tokens[position[0]]
                    position[0] += 1
                    if token == "#":
                        return None
                    node = TreeNode(int(token))
                    node.left = read()
                    node.right = read()
                    return node

                return read()
        """,
        starter_code="""
            def round_trip(root):
                # 1. write: pre-order, "#" for every absent child
                # 2. read: one shared cursor, value then left then right
                # 3. return the rebuilt root, not the token list
                # A correct pair is one where this function is the identity.
                pass
        """,
        visible=[("full", [[1, 2, 3]]), ("right leaning", [[1, None, 2]])],
        hidden=[("deeper", [[1, 2, 3, 4, 5]]), ("left leaning", [[1, 2]]),
                ("negatives", [[-1, -2, -3]])],
        edges=[("empty", [[]]), ("single node", [[7]]),
               ("ragged", [[1, 2, 3, None, 4]])],
        constraints=["the returned tree must be new, not the one passed in"],
        failures=["Returning the token list instead of the rebuilt root",
                  "Returning `root` unchanged, which passes nothing it should"],
        nudge="Two functions you have already written, one after the other, sharing "
              "one list of tokens.",
        visual="tree -> ['1','2','#','#','3','#','#'] -> tree. Identical, and new.",
        pseudocode="""
            tokens = serialise(root)
            return deserialise(tokens)
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    return P


# ===========================================================================
# SECTION 5 — PAYING ONCE
#
# Five of the six DP families had exactly one problem in them and it was MEDIUM
# or HARD. A player's first ever two-dimensional table was edit distance. Each
# family now opens with the smallest honest instance of its own recurrence.
# ===========================================================================

RUINS = "dp_ruins"


def _dynamic() -> list:
    P: list = []

    P.append(rune(
        id="rp-dp-grid-paths", title="The Rune of Arrivals",
        realm=RUINS, difficulty="GUIDED", family="dp_grid", pattern="DP",
        scaffold_for="DP: a cell is the sum of the ways into it",
        secondary=["MATRIX"],
        statement="""
            Moving only right or down, return how many distinct routes lead from the
            top-left corner of a `rows` x `cols` grid to the bottom-right one.

            Every dynamic programming problem is one sentence about a cell and its
            neighbours. Here it is: you can only have arrived at a cell from directly
            above it or directly to its left, so the number of ways to be standing on it
            is the sum of those two. The top row and the left column have exactly one
            route each, which is why the table starts full of ones.
        """,
        fn_name="unique_paths", params="rows, cols", reference=_ref_unique_paths,
        canonical="""
            def unique_paths(rows, cols):
                if rows <= 0 or cols <= 0:
                    return 0
                table = [[1] * cols for _ in range(rows)]
                for r in range(1, rows):
                    for c in range(1, cols):
                        table[r][c] = table[r - 1][c] + table[r][c - 1]
                return table[rows - 1][cols - 1]
        """,
        blanks=[("[[1] * cols for _ in range(rows)]",
                 "a table of the right shape, seeded so the top row and left column "
                 "each have one route"),
                ("table[r - 1][c] + table[r][c - 1]",
                 "every route arriving from above, plus every route arriving from "
                 "the left")],
        visible=[("three by three", [3, 3]), ("wide", [3, 7])],
        hidden=[("single row", [1, 5]), ("square", [4, 4])],
        edges=[("one by one", [1, 1]), ("zero rows", [0, 4]),
               ("negative", [-2, 3])],
        constraints=["movement is right and down only"],
        failures=["Starting the loops at 0 and reading `table[-1][c]`, which silently "
                  "wraps to the last row",
                  "Returning `table[rows][cols]`, one past the end"],
        nudge="Write the sentence about one cell first. The loops are bookkeeping.",
        visual="1 1 1 / 1 2 3 / 1 3 6 : each interior cell is the cell above plus "
               "the cell to its left.",
        pseudocode="""
            table of rows x cols, all ones
            for each row after the first:
                for each column after the first:
                    table[r][c] = table[r-1][c] + table[r][c-1]
            answer is the bottom-right cell
        """,
        time_complexity="O(r*c)", space_complexity="O(r*c)",
        complexity_choices=["O(r+c)", "O(r*c)", "O(2^(r+c))", "O((r*c)^2)"],
    ))

    P.append(rune(
        id="rp-dp-lcs", title="The Rune of the Shared Thread",
        realm=RUINS, difficulty="GUIDED", family="dp_2d", pattern="DP",
        scaffold_for="DP: two inputs means two dimensions", secondary=["STRING"],
        statement="""
            Return the length of the longest subsequence common to `a` and `b`. A
            subsequence keeps order but need not be contiguous.

            When a problem has two inputs that both shrink, the table has two
            dimensions, and `table[i][j]` means 'the answer for the first i characters
            of a and the first j of b'. Then there are only two cases, and they are the
            only two things that can be true of the last character of each prefix: it
            matches, or it does not.
        """,
        fn_name="lcs_length", params="a, b", reference=_ref_lcs_length,
        canonical="""
            def lcs_length(a, b):
                table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
                for i in range(1, len(a) + 1):
                    for j in range(1, len(b) + 1):
                        if a[i - 1] == b[j - 1]:
                            table[i][j] = table[i - 1][j - 1] + 1
                        else:
                            table[i][j] = max(table[i - 1][j], table[i][j - 1])
                return table[len(a)][len(b)]
        """,
        blanks=[("table[i - 1][j - 1] + 1",
                 "the characters match, so extend the answer for both prefixes one "
                 "shorter"),
                ("max(table[i - 1][j], table[i][j - 1])",
                 "they do not match, so take the better of dropping one character "
                 "from either side")],
        visible=[("classic", ["abcde", "ace"]), ("identical", ["abc", "abc"])],
        hidden=[("nothing shared", ["abc", "xyz"]),
                ("repeats", ["aab", "azb"])],
        edges=[("empty first", ["", "abc"]), ("both empty", ["", ""]),
               ("single character", ["a", "a"])],
        constraints=["the table has one extra row and column for the empty prefixes"],
        failures=["Indexing the strings with i and j rather than i-1 and j-1, which "
                  "runs off the end",
                  "Sizing the table len(a) x len(b), leaving nowhere for the base case"],
        nudge="Row 0 and column 0 mean 'one of the strings is empty'. The answer "
              "there is 0, and it is already there.",
        visual="a b c d e / a c e : the thread is a, then c, then e — length 3.",
        pseudocode="""
            table of (len(a)+1) x (len(b)+1), all zero
            for i from 1, for j from 1:
                last characters match -> diagonal + 1
                otherwise             -> max(above, left)
            answer is the bottom-right cell
        """,
        time_complexity="O(n*m)", space_complexity="O(n*m)",
        complexity_choices=["O(n+m)", "O(n*m)", "O(2^n)", "O(n^2*m)"],
    ))

    P.append(rune(
        id="rp-dp-word-break", title="The Rune of the Reachable End",
        realm=RUINS, difficulty="GUIDED", family="dp_string", pattern="DP",
        scaffold_for="DP: reachability along a string", secondary=["STRING", "SET"],
        statement="""
            Return True when `text` can be cut into a sequence of pieces, each of which
            appears in `words`. Words may be reused.

            Read the table as positions rather than as characters. `reachable[i]` means
            'the first i characters can be cut up legally'. Position 0 is reachable for
            free — the empty prefix needs no words — and every later position becomes
            reachable if some earlier reachable position has a real word between it and
            here.
        """,
        fn_name="can_break", params="text, words", reference=_ref_can_break,
        canonical="""
            def can_break(text, words):
                vocabulary = set(words)
                reachable = [False] * (len(text) + 1)
                reachable[0] = True
                for end in range(1, len(text) + 1):
                    for start in range(end):
                        if reachable[start] and text[start:end] in vocabulary:
                            reachable[end] = True
                            break
                return reachable[len(text)]
        """,
        blanks=[("reachable[0] = True",
                 "the empty prefix needs no words at all — this is the base case"),
                ("reachable[start] and text[start:end] in vocabulary",
                 "we could already reach `start`, and the piece from there to here "
                 "is a real word")],
        visible=[("two words", ["applepen", ["apple", "pen"]]),
                 ("no cut works", ["catsandog",
                                   ["cats", "dog", "sand", "and", "cat"]])],
        hidden=[("reuse", ["aaaa", ["a", "aa"]]),
                ("single word", ["sandstorm", ["sand", "storm"]])],
        edges=[("empty text", ["", ["a"]]), ("empty vocabulary", ["abc", []]),
               ("word longer than text", ["ab", ["abc"]])],
        constraints=["words may be used any number of times",
                     "the empty text is always breakable"],
        failures=["Seeding `reachable[0]` as False, which makes everything unreachable",
                  "Greedily taking the longest word at each step, which is wrong for "
                  "'catsandog'"],
        nudge="Indices here count characters consumed, not characters looked at. "
              "There are len(text) + 1 of them.",
        visual="a p p l e p e n : position 5 is reachable via 'apple', and 8 via "
               "'pen' from 5.",
        pseudocode="""
            reachable[0] = True, everything else False
            for each end position:
                for each earlier start:
                    start reachable and text[start:end] is a word -> end reachable
            answer is reachable[len(text)]
        """,
        time_complexity="O(n^2*m)", space_complexity="O(n)",
        complexity_choices=["O(n)", "O(n^2)", "O(n^2*m)", "O(2^n)"],
    ))

    P.append(rune(
        id="rp-dp-coin-change", title="The Rune of the Fewest Coins",
        realm=RUINS, difficulty="GUIDED", family="dp_unbounded", pattern="DP",
        scaffold_for="DP: build every amount below the one you want",
        statement="""
            Return the fewest coins from `coins` that sum to exactly `amount`, or -1 if
            no combination does. Each coin may be used any number of times.

            'Unbounded' is the easy half: because a coin can be reused, making `value`
            is simply one coin plus the best way of making `value - coin`, and that
            smaller amount has already been solved. The awkward half is the impossible
            case, and the trick below is standard — seed every unknown amount with a
            number no real answer could reach, then test against it at the end.
        """,
        fn_name="min_coins", params="coins, amount", reference=_ref_min_coins,
        canonical="""
            def min_coins(coins, amount):
                if amount < 0:
                    return -1
                best = [0] + [amount + 1] * amount
                for value in range(1, amount + 1):
                    for coin in coins:
                        if coin <= value:
                            best[value] = min(best[value], best[value - coin] + 1)
                return -1 if best[amount] > amount else best[amount]
        """,
        blanks=[("best[value - coin] + 1",
                 "the best way of making the remainder, plus this one coin"),
                ("best[amount] > amount",
                 "nothing ever improved on the impossible sentinel, so there is no "
                 "combination")],
        visible=[("classic", [[1, 2, 5], 11]), ("exact coin", [[2, 5], 5])],
        hidden=[("impossible", [[2], 3]), ("greedy would fail", [[1, 3, 4], 6])],
        edges=[("amount zero", [[1, 2], 0]), ("no coins", [[], 5]),
               ("negative amount", [[1], -1])],
        constraints=["coins are positive", "an amount of zero needs no coins"],
        failures=["Taking the largest coin that fits each time, which gives 3 coins "
                  "for 6 from {1,3,4} instead of 2",
                  "Seeding the table with 0 instead of an impossible value, so every "
                  "amount looks free"],
        nudge="No real answer can use more coins than the amount itself, so "
              "`amount + 1` is safely impossible.",
        visual="{1,3,4} making 6 : greedy takes 4+1+1. The table finds 3+3.",
        pseudocode="""
            best[0] = 0, every other amount = amount + 1
            for each value from 1 up:
                for each coin that fits:
                    best[value] = min(best[value], best[value - coin] + 1)
            still at the sentinel -> -1
        """,
        time_complexity="O(amount * len(coins))", space_complexity="O(amount)",
        complexity_choices=["O(amount)", "O(len(coins))",
                            "O(amount * len(coins))", "O(2^amount)"],
    ))

    P.append(rune(
        id="rp-dp-subset-sum", title="The Rune of What Can Be Made",
        realm=RUINS, difficulty="GUIDED", family="dp_knapsack", pattern="DP",
        scaffold_for="DP: carry the set of achievable states", secondary=["SET"],
        statement="""
            Return True when some subset of `nums` sums to exactly `target`.

            The knapsack shape stated in its smallest form. Instead of a table, carry
            the set of every total you could currently make. Each new value either joins
            a total or it does not, so the new set is the old one plus a copy of it
            shifted by that value. Nothing is recomputed, which is the whole reason this
            is not exponential.
        """,
        fn_name="subset_sum", params="nums, target", reference=_ref_subset_sum,
        canonical="""
            def subset_sum(nums, target):
                reachable = {0}
                for value in nums:
                    reachable |= {value + total for total in reachable}
                return target in reachable
        """,
        blanks=[("{value + total for total in reachable}",
                 "every total we could already make, with this value added to it"),
                ("target in reachable",
                 "was the target ever among the totals we could build")],
        visible=[("hit", [[3, 34, 4, 12, 5, 2], 9]), ("miss", [[3, 34, 4], 30])],
        hidden=[("uses everything", [[1, 2, 3], 6]),
                ("negatives", [[-1, 5, 3], 2])],
        edges=[("target zero", [[1, 2], 0]), ("empty list", [[], 5]),
               ("single value", [[7], 7])],
        constraints=["the empty subset sums to zero, so target 0 is always reachable"],
        failures=["Mutating `reachable` while iterating over it, which lets one value "
                  "be used twice",
                  "Starting from an empty set rather than {0}, losing the base case"],
        nudge="The set starts holding one thing: zero, made from nothing.",
        visual="{0} -> {0,3} -> {0,3,34,37} -> ... each step doubles what is known.",
        pseudocode="""
            reachable = {0}
            for each value:
                reachable = reachable, plus every element of it shifted by value
            answer is whether the target is in there
        """,
        time_complexity="O(n * sums)", space_complexity="O(sums)",
        complexity_choices=["O(n)", "O(n log n)", "O(n * sums)", "O(2^n)"],
    ))

    P.append(rune(
        id="rp-dp-lis", title="The Rune of the Longest Climb",
        realm=RUINS, difficulty="GUIDED", family="dp_subsequence", pattern="DP",
        scaffold_for="DP: the best answer ENDING here", secondary=["ARRAY"],
        statement="""
            Return the length of the longest strictly increasing subsequence of `nums`.
            The chosen values keep their order but need not be adjacent.

            The subtlety worth having is what the table means. `best[i]` is not 'the
            answer for the first i values' — it is 'the length of the longest climb that
            ENDS at position i'. Defined that way each entry depends only on earlier
            entries whose value is smaller, and the answer is the largest entry rather
            than the last one.
        """,
        fn_name="longest_increasing", params="nums",
        reference=_ref_longest_increasing,
        canonical="""
            def longest_increasing(nums):
                if not nums:
                    return 0
                best = [1] * len(nums)
                for i in range(len(nums)):
                    for j in range(i):
                        if nums[j] < nums[i]:
                            best[i] = max(best[i], best[j] + 1)
                return max(best)
        """,
        blanks=[("nums[j] < nums[i]",
                 "the earlier value is small enough to sit in front of this one"),
                ("best[j] + 1",
                 "the longest climb ending at j, with this value added to the end")],
        visible=[("classic", [[10, 9, 2, 5, 3, 7, 101, 18]]),
                 ("already sorted", [[1, 2, 3, 4]])],
        hidden=[("descending", [[5, 4, 3, 2]]), ("all equal", [[2, 2, 2]])],
        edges=[("empty", [[]]), ("single", [[9]]), ("two equal", [[3, 3]])],
        constraints=["strictly increasing, so equal values do not extend a climb"],
        failures=["Returning `best[-1]`, which is the climb ending at the LAST value, "
                  "not the longest one anywhere",
                  "Using `<=` and counting a flat run as a climb"],
        nudge="Every position starts at 1: a single value is a climb of length one.",
        visual="[10 9 2 5 3 7 101 18] : the climb 2,3,7,101 ends at index 6 — not "
               "at the end of the list.",
        pseudocode="""
            empty -> 0
            best = all ones
            for each i:
                for each earlier j with a smaller value:
                    best[i] = max(best[i], best[j] + 1)
            answer is the largest entry
        """,
        time_complexity="O(n^2)", space_complexity="O(n)",
        complexity_choices=["O(n)", "O(n log n)", "O(n^2)", "O(2^n)"],
    ))

    P.append(rune(
        id="rp-recursion-halves", title="The Rune of the Halved Problem",
        realm="recursive_forest", difficulty="GUIDED", family="recursion_divide",
        pattern="RECURSION", scaffold_for="RECURSION: divide, solve, combine",
        secondary=["ARRAY"],
        statement="""
            Return the sum of `nums` by splitting the list in half, summing each half
            recursively, and adding the two results.

            The answer is obviously `sum(nums)`, and that is deliberate — it means
            nothing here is hiding behind the arithmetic. Divide and conquer is three
            named steps, and this is the smallest problem that has all three: a base
            case small enough to answer outright, a split, and a combine.
        """,
        fn_name="sum_halves", params="nums", reference=_ref_sum_halves,
        canonical="""
            def sum_halves(nums):
                if not nums:
                    return 0
                if len(nums) == 1:
                    return nums[0]
                middle = len(nums) // 2
                return sum_halves(nums[:middle]) + sum_halves(nums[middle:])
        """,
        blanks=[("len(nums) // 2",
                 "the split point that makes the two halves as even as possible"),
                ("sum_halves(nums[:middle]) + sum_halves(nums[middle:])",
                 "solve both halves and combine them — the whole of divide and conquer")],
        visible=[("even length", [[1, 2, 3, 4]]), ("odd length", [[5, 5, 5]])],
        hidden=[("negatives", [[-1, 2, -3, 4]]), ("longer", [[1, 2, 3, 4, 5, 6, 7]])],
        edges=[("empty", [[]]), ("single", [[42]]), ("two values", [[1, -1]])],
        constraints=["both halves must be non-empty for lists of two or more, or the "
                     "recursion never ends"],
        failures=["Splitting as `nums[:0]` and `nums[0:]`, which recurses forever on "
                  "the same list",
                  "Forgetting the empty base case, so the one-element case is never "
                  "protected"],
        nudge="Every recursive call must receive a STRICTLY smaller list. Check that "
              "your split does.",
        visual="[1 2 3 4] -> [1 2] + [3 4] -> (1 + 2) + (3 + 4)",
        pseudocode="""
            empty -> 0
            one element -> that element
            otherwise -> solve the left half + solve the right half
        """,
        time_complexity="O(n)", space_complexity="O(n)",
        complexity_choices=["O(log n)", "O(n)", "O(n log n)", "O(n^2)"],
    ))

    P.append(rune(
        id="rp-search-on-answer", title="The Rune of the Guessed Answer",
        realm="complexity_tower", difficulty="GUIDED",
        family="binary_search_answer", pattern="BINARY_SEARCH",
        scaffold_for="BINARY SEARCH: over the answer, not over a list",
        statement="""
            Return the smallest non-negative integer `x` with `x * x >= n`. For n of 0
            or less, return 0.

            There is no list here, and that is the point. Binary search does not need
            one — it needs a range of candidate answers and a yes/no test that is False
            for a while and then True forever. Once you can see that shape, 'smallest
            capacity that fits in D days' and 'least speed that finishes in H hours' are
            the same problem wearing different clothes.
        """,
        fn_name="smallest_root", params="n", reference=_ref_smallest_root,
        canonical="""
            def smallest_root(n):
                if n <= 0:
                    return 0
                low = 0
                high = n
                while low < high:
                    mid = (low + high) // 2
                    if mid * mid >= n:
                        high = mid
                    else:
                        low = mid + 1
                return low
        """,
        blanks=[("mid * mid >= n",
                 "this candidate already satisfies the requirement, so nothing "
                 "larger needs testing"),
                ("low = mid + 1",
                 "this candidate is too small, so the answer is strictly above it")],
        visible=[("perfect square", [16]), ("between squares", [10])],
        hidden=[("one", [1]), ("large", [1000])],
        edges=[("zero", [0]), ("negative", [-5]), ("two", [2])],
        constraints=["the answer is always within [0, n] for n >= 1"],
        failures=["Writing `high = mid - 1`, which can step past the smallest "
                  "satisfying candidate and lose it",
                  "Looping while `low <= high`, which does not converge on a "
                  "smallest-such-that search"],
        nudge="When the candidate works, keep it — narrow to `mid`, not `mid - 1`.",
        visual="n = 10 : the test is False, False, False, True, True, ... and you "
               "want the first True.",
        pseudocode="""
            n <= 0 -> 0
            low, high = 0, n
            while low < high:
                mid = midpoint
                test passes -> high = mid      (keep this candidate)
                test fails   -> low = mid + 1  (discard it)
            answer is low
        """,
        time_complexity="O(log n)", space_complexity="O(1)",
    ))

    return P


# ===========================================================================
# SECTION 6 — DESIGN, AND THE ENCOUNTERS THAT ARE NOT IMPLEMENTATIONS
#
# `design` opened at EASY with two problems and then jumped to MEDIUM; the
# hash-map-like structure and the undo/redo editor — both on the reported
# archetype list — existed only at MEDIUM and HARD. The four meta families
# (`big_o`, `code_reading`, `edge_cases`, `pattern_recognition`) and the
# Testsmith Forge all opened at EASY or MEDIUM, which is one rung too high for
# encounters that take under two minutes.
# ===========================================================================

def _designs() -> list:
    P: list = []

    P.append(design_problem(
        id="rp-design-tally", title="The Keeper of Counts",
        realm="hashmap_highlands", difficulty="GUIDED", family="design",
        cls_name="Tally", reference_cls=_RefTally, secondary=["HASH_MAP"],
        statement="""
            Build a `Tally` that remembers how many times each item has been added.

            - `add(item)` records one sighting and returns nothing.
            - `count(item)` returns how many times it has been added, 0 if never.
            - `best()` returns the most-added item, or `None` if nothing has been
              added. On a tie, return the smallest item.

            This is the smallest design encounter there is, and it still contains the
            question every design encounter asks first: which structure, and why. One
            dict, chosen before any method is written, makes all three methods one line.
        """,
        canonical="""
            class Tally:
                def __init__(self):
                    self.counts = {}

                def add(self, item):
                    self.counts[item] = self.counts.get(item, 0) + 1

                def count(self, item):
                    return self.counts.get(item, 0)

                def best(self):
                    if not self.counts:
                        return None
                    return min(self.counts, key=lambda item: (-self.counts[item], item))
        """,
        visible=[("counting", ["add", "add", "count", "count"],
                  [["a"], ["b"], ["a"], ["z"]]),
                 ("most added", ["add", "add", "add", "best"],
                  [["x"], ["y"], ["x"], []])],
        hidden=[("tie goes to the smallest", ["add", "add", "best"],
                 [["b"], ["a"], []]),
                ("repeated counting", ["add", "add", "add", "count"],
                 [["q"], ["q"], ["q"], ["q"]])],
        edges=[("nothing added yet", ["best"], [[]]),
               ("counting something absent", ["count"], [["never"]]),
               ("one item only", ["add", "best"], [["solo"], []])],
        constraints=["items are hashable", "ties are broken by the smaller item"],
        failures=["`self.counts[item] += 1` raises KeyError on the first sighting",
                  "Returning 0 instead of None from `best()` on an empty tally",
                  "Breaking ties by insertion order, which is not the stated rule"],
        nudge="Pick the structure first. `dict.get(item, 0)` removes the first-sighting "
              "special case entirely.",
        visual="item -> count. Nothing else needs storing; `best` is a scan.",
        pseudocode="""
            __init__: one empty dict
            add:   counts[item] = counts.get(item, 0) + 1
            count: counts.get(item, 0)
            best:  empty -> None; otherwise the highest count, smallest item on a tie
        """,
        time_complexity="O(1) for add and count, O(n) for best",
        space_complexity="O(n)",
    ))

    P.append(design_problem(
        id="rp-design-hash-map", title="The Vault Built From Buckets",
        realm="hashmap_highlands", difficulty="TUTORIAL", family="design",
        cls_name="MyHashMap", reference_cls=_RefHashMap, secondary=["HASH_MAP"],
        statement="""
            Build a key-value store without using a dict for the storage. Keys are
            integers.

            - `put(key, value)` stores or overwrites, and returns nothing.
            - `get(key)` returns the stored value, or -1 if there is none.
            - `remove(key)` deletes the key if present, and returns nothing.

            Use a fixed list of 16 buckets, each a list of `(key, value)` pairs, and
            send a key to bucket `key % 16`. That one line is the whole of hashing:
            a cheap function from a key to a slot. Two keys can land in the same
            bucket — 1 and 17 do — and the bucket being a list is what makes that
            survivable rather than fatal.

            Note the deliberate flaw you are building: with a fixed 16 buckets and
            enough keys, every operation degrades to scanning a list. A real hash map
            grows its bucket array. Being able to say that out loud is the point of
            writing this by hand.
        """,
        canonical="""
            class MyHashMap:
                BUCKETS = 16

                def __init__(self):
                    self.slots = [[] for _ in range(self.BUCKETS)]

                def _bucket(self, key):
                    return self.slots[key % self.BUCKETS]

                def put(self, key, value):
                    bucket = self._bucket(key)
                    for i, pair in enumerate(bucket):
                        if pair[0] == key:
                            bucket[i] = (key, value)
                            return
                    bucket.append((key, value))

                def get(self, key):
                    for stored_key, value in self._bucket(key):
                        if stored_key == key:
                            return value
                    return -1

                def remove(self, key):
                    bucket = self._bucket(key)
                    for i, pair in enumerate(bucket):
                        if pair[0] == key:
                            bucket.pop(i)
                            return
        """,
        visible=[("store and read", ["put", "get", "get"],
                  [[1, "a"], [1], [2]]),
                 ("overwrite", ["put", "put", "get"],
                  [[3, "old"], [3, "new"], [3]])],
        hidden=[("remove", ["put", "remove", "get"], [[5, "x"], [5], [5]]),
                ("collision keeps both", ["put", "put", "get", "get"],
                 [[1, "a"], [17, "b"], [1], [17]])],
        edges=[("read a key never stored", ["get"], [[99]]),
               ("remove a key never stored", ["remove", "get"], [[9], [9]]),
               ("key zero", ["put", "get"], [[0, "zero"], [0]])],
        constraints=["keys are integers", "no dict may be used for the storage",
                     "a missing key reads as -1, which is why -1 is not a valid value"],
        failures=["Appending on every `put`, so an overwrite leaves two pairs and "
                  "`get` returns the stale one",
                  "Creating the buckets with `[[]] * 16`, which makes sixteen "
                  "references to ONE list",
                  "Returning None rather than -1 for a missing key"],
        nudge="`[[] for _ in range(16)]` and `[[]] * 16` look the same and are not. "
              "The second shares one list sixteen times.",
        visual="key 1 and key 17 both land in bucket 1. The bucket holds both pairs.",
        pseudocode="""
            __init__: 16 independent empty lists
            bucket(key): slots[key % 16]
            put:    scan the bucket for the key, replace it; otherwise append
            get:    scan the bucket for the key, return its value; otherwise -1
            remove: scan the bucket for the key, pop it
        """,
        time_complexity="O(1) average, O(n) when every key collides",
        space_complexity="O(n)",
    ))

    P.append(design_problem(
        id="rp-design-editor", title="The Scribe Who Can Take It Back",
        realm="stack_queue_mines", difficulty="TUTORIAL", family="design",
        cls_name="Editor", reference_cls=_RefEditor, secondary=["STACK"],
        statement="""
            Build a tiny text editor with undo and redo. Every method returns the
            document's text as it stands afterwards.

            - `write(chunk)` appends `chunk` to the document.
            - `undo()` reverts the last change, or does nothing if there is none.
            - `redo()` reapplies the last undone change, or does nothing if there is
              none.

            Two stacks, and one rule that people forget: writing something new
            **discards the redo history**. There is no longer a future to return to —
            you have just made a different one. Every editor you have ever used works
            this way, and the test for it is the one this encounter actually cares
            about.
        """,
        canonical="""
            class Editor:
                def __init__(self):
                    self.text = ""
                    self.past = []
                    self.future = []

                def write(self, chunk):
                    self.past.append(self.text)
                    self.future = []
                    self.text = self.text + chunk
                    return self.text

                def undo(self):
                    if not self.past:
                        return self.text
                    self.future.append(self.text)
                    self.text = self.past.pop()
                    return self.text

                def redo(self):
                    if not self.future:
                        return self.text
                    self.past.append(self.text)
                    self.text = self.future.pop()
                    return self.text
        """,
        visible=[("write and undo", ["write", "write", "undo"],
                  [["ab"], ["cd"], []]),
                 ("undo then redo", ["write", "undo", "redo"], [["hi"], [], []])],
        hidden=[("writing discards the redo history",
                 ["write", "undo", "write", "redo"], [["a"], [], ["b"], []]),
                ("two undos", ["write", "write", "undo", "undo"],
                 [["x"], ["y"], [], []])],
        edges=[("undo with nothing written", ["undo"], [[]]),
               ("redo with nothing undone", ["redo"], [[]]),
               ("writing nothing", ["write", "undo"], [[""], []])],
        constraints=["every method returns the resulting text",
                     "undo and redo on an empty history are no-ops, not errors"],
        failures=["Forgetting to clear the redo stack on a write, which lets `redo` "
                  "resurrect a document that no longer exists",
                  "Raising instead of returning the current text when there is "
                  "nothing to undo",
                  "Storing the edits rather than the states, which makes `undo` have "
                  "to invert an operation it may not be able to invert"],
        nudge="Store whole states, not edits. The document is small and the code is "
              "then obviously correct — say the trade-off out loud.",
        visual="past = [..., previous]   future = [undone, ...]. A write empties "
               "the second one.",
        pseudocode="""
            write: push the current text onto past; clear future; append
            undo:  past empty -> nothing; else push current onto future, pop past
            redo:  future empty -> nothing; else push current onto past, pop future
        """,
        time_complexity="O(len(text)) per operation", space_complexity="O(edits)",
    ))

    return P


def _meta() -> list:
    """The four non-implementation families, each opened at GUIDED."""
    P: list = []

    P.append(complexity_q(
        "rp-cx-one-loop", "The First Reckoning",
        "def total(nums):\n"
        "    running = 0\n"
        "    for value in nums:\n"
        "        running += value\n"
        "    return running\n",
        COMPLEXITY_LADDER, 2,
        "One loop over n items, doing a fixed amount of work per item, is O(n). "
        "Start every complexity answer here: count the work inside the loop, then "
        "multiply by how many times the loop runs.",
        difficulty="GUIDED", seconds=45))

    P.append(complexity_q(
        "rp-cx-nested-loop", "The Second Reckoning",
        "def any_pair_sums_to(nums, target):\n"
        "    for a in nums:\n"
        "        for b in nums:\n"
        "            if a + b == target:\n"
        "                return True\n"
        "    return False\n",
        COMPLEXITY_LADDER, 4,
        "The inner loop runs n times for each of the n runs of the outer loop, so the "
        "work is n * n. An early `return` does not change the answer: complexity "
        "describes the worst case, and the worst case is that no pair matches.",
        difficulty="GUIDED", seconds=45))

    P.append(reading_q(
        "rp-cr-alias", "Two Names, One List",
        "a = [1, 2, 3]\nb = a\nb.append(4)\nprint(a)\n",
        "What does this print?",
        ["[1, 2, 3, 4]", "[1, 2, 3]", "[4]", "It raises an exception"],
        0,
        "`b = a` does not copy anything. It gives the same list a second name, so "
        "appending through either name is visible through both. `b = a[:]` or "
        "`b = list(a)` is what makes a copy. Mutable default arguments, functions that "
        "'quietly' modify their input, and most surprising aliasing bugs are this one "
        "fact wearing a hat.",
        difficulty="GUIDED", seconds=60))

    P.append(trap_q(
        "rp-et-first-of-empty", "The Mimic of the First Element",
        "def first(items):\n    return items[0]\n",
        ["[]", "[0]", "[None]", "[1, 2, 3]"],
        0,
        "An empty list has no index 0, so this raises IndexError. Every function that "
        "reaches into a collection by position needs an answer for the collection "
        "being empty, decided before the code is written rather than after a "
        "traceback. `[0]` and `[None]` both work fine — a falsy element is not an "
        "absent one, and confusing the two is its own bug.",
        difficulty="GUIDED", seconds=45))

    P.append(pattern_q(
        "rp-pr-seen-before-guided", "Reading the Signals: First Light",
        "\"Given a list of values, report whether any value appears **twice**.\"\n\n"
        "Which structure does that in one pass?",
        PATTERN_CHOICES, 0,
        "'Have I seen this before' is a membership question, and membership over a "
        "growing collection is a hash-based structure — a set here, since you need to "
        "know whether a value is present, not how many times. Sorting first would also "
        "work and costs O(n log n) instead of O(n).",
        difficulty="GUIDED", seconds=40))

    P.append(forge_problem(
        id="rp-tf-count-positive", title="The Testsmith's Apprentice Piece",
        realm="debugging_dungeon", difficulty="GUIDED", family="testing",
        fn_name="count_positive",
        statement="""
            Three implementations of `count_positive(nums)`, which returns how many
            values in the list are strictly greater than zero. Two of them are
            **Mimics**.

            Write a test suite that accepts the honest one and rejects both Mimics.
            Return a list of `(args, expected)` pairs; `args` must be a tuple, and
            every pair must hold for a CORRECT implementation.

            Two inputs are enough here. Finding them is the exercise: ask what each
            Mimic gets away with, and then write the input it cannot.
        """,
        correct="def count_positive(nums):\n"
                "    return sum(1 for v in nums if v > 0)\n",
        mutants=[
            # counts zero as positive
            "def count_positive(nums):\n"
            "    return sum(1 for v in nums if v >= 0)\n",
            # returns the values rather than how many
            "def count_positive(nums):\n"
            "    return sum(v for v in nums if v > 0)\n",
        ],
        kills=[[[0]], [[2]]],
        nudge="One Mimic thinks zero is positive. The other adds the values up instead "
              "of counting them — which is invisible on a list of ones."))

    return P


def build() -> list:
    return (_windows() + _pointers_and_stacks() + _grids_and_graphs()
            + _trees() + _dynamic() + _designs() + _meta())
