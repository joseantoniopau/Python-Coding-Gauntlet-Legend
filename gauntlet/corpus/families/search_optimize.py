"""Search, choice, and arithmetic.

Seven topics the corpus could not previously teach at all: backtracking, greedy,
bit manipulation, number theory, intervals, sorting by intention, and the two
graph techniques that are not a traversal (union-find and topological order).

Every topic enters the same way, and the order is the point:

  GUIDED    working code with one `__BLANK__`. The player supplies one
            expression into a program that already runs in their head.
  TUTORIAL  a small whole function, one idea, no branching cleverness.
  EASY      the classic statement of the technique.
  MEDIUM+   the version that has a trap in it.

A topic whose first appearance is MEDIUM is a bug in this file, not a
challenging problem. The corpus already had plenty of the latter.

The greedy section is the one with an argument in it. Greed is taught here as a
judgement — `so-greedy-vs-optimal` makes the player compute the gap between the
greedy answer and the true one, because the interview question is never "can you
write a greedy loop", it is "how do you know that works".
"""
from __future__ import annotations

from ._base import code_problem, mcq_problem

# Weighted for this player's declared profile.
Q = {"PRACTICAL": 1.5, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 1.5}

VIZ_CHOICE = {"type": "array_scan", "caption": "Choose, recurse, undo. Always undo."}
VIZ_SCAN = {"type": "array_scan", "caption": "One pass, one running decision."}

SCAFFOLD_VISUAL = {
    "GUIDED": "The program already works. Read it top to bottom, then fill the "
              "one hole. You are finishing a sentence, not writing an essay.",
    "TUTORIAL": "Small and whole. One idea, no cleverness, no branches you did "
                "not put there on purpose.",
}


def sp(pid, title, tier, statement, fn, params, ref, canonical, visible, hidden,
       *, pattern, family, realm, starter="", starter_hint="", nudge="",
       pseudocode="", fragment="", visual="", edges=(), perf=(), failures=(),
       cmp="exact", time="O(n)", space="O(n)", secondary=(), tags=(),
       constraints=(), after="", viz=None, boss=False):
    """One problem in this family. GUIDED tiers become MISSING_RUNE encounters,
    which is what stops a beginner meeting an empty editor."""
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=tier,
        family=family, profile_weight=Q, viz=viz or VIZ_SCAN,
        statement=statement, fn_name=fn, params=params, reference=ref,
        canonical=canonical, visible=visible, hidden=hidden, edges=edges,
        perf=perf, cmp=cmp, time_complexity=time, space_complexity=space,
        secondary=list(secondary), constraints=list(constraints),
        failures=list(failures), nudge=nudge,
        visual=visual or SCAFFOLD_VISUAL.get(tier, "Trace one small input by hand first."),
        pseudocode=pseudocode, fragment=fragment,
        starter_code=starter, starter_hint=starter_hint,
        encounter="MISSING_RUNE" if tier == "GUIDED" else "CODE_BATTLE",
        prerequisites=[after] if after else [],
        boss=boss,
        tags=list(tags) + ["scaffold:" + tier.lower()],
    )


def _same_move(body: str) -> str:
    """Rung 4 on a scaffolded problem. Handing over the answer line would make
    this rung identical to Phoenix, so it shows the same move on other data."""
    return "```python\n# the same move, somewhere else:\n" + body.strip() + "\n```"


# ===========================================================================
# Reference implementations
#
# Written against the statement, not against the canonical solutions below.
# Where a canonical solution is the textbook technique, the reference here is
# deliberately the dumb way: brute force, a library call, a different algorithm
# entirely. Two implementations that agree on every test is the whole contract.
# ===========================================================================

# --- backtracking ----------------------------------------------------------

def _subsets(nums):
    out = [[]]
    for value in nums:
        out = out + [row + [value] for row in out]
    return out


def _binary_strings(n):
    from itertools import product
    if n <= 0:
        return [""]
    return ["".join(bits) for bits in product("01", repeat=n)]


def _permutations(nums):
    from itertools import permutations
    return [list(p) for p in permutations(nums)]


def _combination_sum(candidates, target):
    from itertools import combinations_with_replacement
    pool = sorted({c for c in candidates if c > 0})
    if not pool or target <= 0:
        return []
    out = []
    for size in range(1, target // pool[0] + 1):
        for combo in combinations_with_replacement(pool, size):
            if sum(combo) == target:
                out.append(list(combo))
    return out


def _generate_parentheses(n):
    from itertools import product
    if n <= 0:
        return [""]
    out = []
    for combo in product("()", repeat=2 * n):
        depth, ok = 0, True
        for ch in combo:
            depth += 1 if ch == "(" else -1
            if depth < 0:
                ok = False
                break
        if ok and depth == 0:
            out.append("".join(combo))
    return out


def _palindrome_partitions(s):
    n = len(s)
    if n == 0:
        return [[]]
    out = []
    for mask in range(1 << (n - 1)):          # a cut, or no cut, between each pair
        parts, start = [], 0
        for i in range(n - 1):
            if mask >> i & 1:
                parts.append(s[start:i + 1])
                start = i + 1
        parts.append(s[start:])
        if all(part == part[::-1] for part in parts):
            out.append(parts)
    return out


def _word_search(board, word):
    rows = len(board)
    cols = len(board[0]) if rows else 0
    if not word:
        return True
    if not rows or not cols:
        return False

    def walk(r, c, k, used):
        if board[r][c] != word[k]:
            return False
        if k == len(word) - 1:
            return True
        used.add((r, c))
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in used:
                if walk(nr, nc, k + 1, used):
                    used.discard((r, c))
                    return True
        used.discard((r, c))
        return False

    return any(walk(r, c, 0, set()) for r in range(rows) for c in range(cols))


def _n_queens(n):
    from itertools import permutations
    if n < 0:
        return 0
    # n == 0 falls through: permutations of nothing is one empty placement, and
    # the empty placement is a legal one. The canonical solution agrees.
    total = 0
    for cols in permutations(range(n)):
        diag = {c - r for r, c in enumerate(cols)}
        anti = {c + r for r, c in enumerate(cols)}
        if len(diag) == n and len(anti) == n:
            total += 1
    return total


# --- greedy ----------------------------------------------------------------

def _assign_cookies(greed, size):
    kids = sorted(greed)
    i = 0
    for cookie in sorted(size):
        if i < len(kids) and kids[i] <= cookie:
            i += 1
    return i


def _us_coins(amount):
    count = 0
    for coin in (25, 10, 5, 1):
        count += amount // coin
        amount %= coin
    return count


def _max_profit(prices):
    return sum(max(0, b - a) for a, b in zip(prices, prices[1:]))


def _greedy_change(amount, coins):
    left, used = amount, 0
    for coin in sorted(coins, reverse=True):
        while coin <= left:
            left -= coin
            used += 1
    return used if left == 0 else -1


def _jump_game(nums):
    reach = 0
    for i, step in enumerate(nums):
        if i > reach:
            return False
        reach = max(reach, i + step)
    return True


def _max_meetings(meetings):
    count, end = 0, None
    for start, finish in sorted(meetings, key=lambda m: m[1]):
        if end is None or start >= end:
            count += 1
            end = finish
    return count


def _gas_station(gas, cost):
    n = len(gas)
    for start in range(n):                    # the dumb way: try every start
        tank, ok = 0, True
        for step in range(n):
            i = (start + step) % n
            tank += gas[i] - cost[i]
            if tank < 0:
                ok = False
                break
        if ok:
            return start
    return -1


def _greedy_vs_optimal(coins, amount):
    greedy = _greedy_change(amount, coins)
    best = [0] + [None] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if coin <= value and best[value - coin] is not None:
                if best[value] is None or best[value - coin] + 1 < best[value]:
                    best[value] = best[value - coin] + 1
    return [greedy, -1 if best[amount] is None else best[amount]]


def _min_jumps(nums):
    n = len(nums)
    best = [0] + [None] * (n - 1) if n else []
    for i in range(n):
        if best[i] is None:
            continue
        for step in range(1, nums[i] + 1):
            j = i + step
            if j < n and (best[j] is None or best[i] + 1 < best[j]):
                best[j] = best[i] + 1
    return 0 if not n else (-1 if best[n - 1] is None else best[n - 1])


# --- bit manipulation ------------------------------------------------------

def _bit_at(n, i):
    return int(bin(n)[2:].zfill(i + 1)[-(i + 1)]) if i >= 0 else 0


def _is_power_of_two(n):
    return n > 0 and bin(n).count("1") == 1


def _single_number(nums):
    from collections import Counter
    for value, count in Counter(nums).items():
        if count == 1:
            return value
    return 0


def _apply_flags(flags, mask, enable):
    out = 0
    for bit in range(max(flags.bit_length(), mask.bit_length()) + 1):
        on = flags >> bit & 1
        if mask >> bit & 1:
            on = 1 if enable else 0
        out |= on << bit
    return out


def _counting_bits(n):
    return [bin(i).count("1") for i in range(n + 1)]


def _missing_number(nums):
    present = set(nums)
    for value in range(len(nums) + 1):
        if value not in present:
            return value
    return -1


def _two_singles(nums):
    from collections import Counter
    return sorted(v for v, c in Counter(nums).items() if c == 1)


def _gray_code(n):
    if n <= 0:
        return [0]
    previous = _gray_code(n - 1)
    return previous + [(1 << (n - 1)) + value for value in reversed(previous)]


# --- math ------------------------------------------------------------------

def _fizzbuzz(n):
    out = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            out.append("FizzBuzz")
        elif i % 3 == 0:
            out.append("Fizz")
        elif i % 5 == 0:
            out.append("Buzz")
        else:
            out.append(str(i))
    return out


def _gcd(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def _lcm(a, b):
    if a == 0 or b == 0:
        return 0
    return abs(a * b) // _gcd(a, b)


def _safe_midpoint(lo, hi):
    return (lo + hi) // 2


def _is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    factor = 3
    while factor * factor <= n:
        if n % factor == 0:
            return False
        factor += 2
    return True


def _digit_sum(n):
    return sum(int(ch) for ch in str(abs(n)))


def _primes_below(n):
    return [value for value in range(2, max(n, 2)) if _is_prime(value)]


def _to_base(n, base):
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if not 2 <= base <= 36:
        return ""
    if n == 0:
        return "0"
    sign, n = ("-" if n < 0 else ""), abs(n)
    out = []
    while n:
        n, rest = divmod(n, base)
        out.append(digits[rest])
    return sign + "".join(reversed(out))


def _truncated_divide(a, b):
    if b == 0:
        return None
    size = abs(a) // abs(b)
    return size if (a < 0) == (b < 0) else -size


def _count_primes(limit):
    """Odd-only sieve. Deliberately not the sieve the player is asked to write."""
    if limit < 3:
        return 0
    size = limit // 2                       # index i stands for the odd number 2i+1
    sieve = bytearray([1]) * size
    sieve[0] = 0                            # 1 is not prime
    i = 1
    while (2 * i + 1) ** 2 < limit:
        if sieve[i]:
            step = 2 * i + 1
            start = (step * step) // 2
            sieve[start::step] = bytearray(len(range(start, size, step)))
        i += 1
    return 1 + sum(sieve)                   # the 1 is the prime 2


def _trailing_zeros(n):
    count, power = 0, 5
    while power <= n:
        count += n // power
        power *= 5
    return count


def _power_mod(base, exponent, mod):
    return pow(base, exponent, mod)


def _reverse_int(n):
    sign = -1 if n < 0 else 1
    value = sign * int(str(abs(n))[::-1])
    return 0 if not -(2 ** 31) <= value <= 2 ** 31 - 1 else value


# --- intervals -------------------------------------------------------------
# Half-open throughout: [start, end) holds start, excludes end. A meeting from
# 9 to 10 and one from 10 to 11 do not collide.

def _overlaps(a, b):
    return len(range(max(a[0], b[0]), min(a[1], b[1]))) > 0


def _can_attend_all(meetings):
    order = sorted(meetings)
    return all(order[i][1] <= order[i + 1][0] for i in range(len(order) - 1))


def _union_two(a, b):
    first, second = (a, b) if a[0] <= b[0] else (b, a)
    if second[0] <= first[1]:
        return [[first[0], max(first[1], second[1])]]
    return [list(first), list(second)]


def _merge_ranges(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def _insert_range(intervals, new):
    return _merge_ranges(list(intervals) + [list(new)])


def _min_removals(intervals):
    """Longest chain by O(n^2) DP, then subtract. Not the greedy the player writes."""
    order = sorted(intervals)
    n = len(order)
    best = [1] * n
    for i in range(n):
        for j in range(i):
            if order[j][1] <= order[i][0] and best[j] + 1 > best[i]:
                best[i] = best[j] + 1
    return n - (max(best) if best else 0)


def _min_rooms(meetings):
    """A sweep over start/end events. Ends sort before starts at equal time,
    which is exactly the half-open rule."""
    events = []
    for start, end in meetings:
        if end > start:
            events.append((start, 1))
            events.append((end, -1))
    events.sort()
    current = best = 0
    for _, delta in events:
        current += delta
        best = max(best, current)
    return best


def _free_slots(busy, day_start, day_end):
    """A boolean timeline. Correct, obvious, and the wrong shape at scale."""
    if day_end <= day_start:
        return []
    taken = [False] * (day_end - day_start)
    for start, end in busy:
        for t in range(max(start, day_start), min(end, day_end)):
            taken[t - day_start] = True
    out, run = [], None
    for index, used in enumerate(taken):
        if not used and run is None:
            run = index
        elif used and run is not None:
            out.append([run + day_start, index + day_start])
            run = None
    if run is not None:
        out.append([run + day_start, len(taken) + day_start])
    return out


# --- sorting ---------------------------------------------------------------

def _rank_players(records):
    """Two stable passes, least significant key first. The other way to do it."""
    by_name = sorted(records, key=lambda record: record[0])
    return [list(r) for r in sorted(by_name, key=lambda record: -record[1])]


def _tally_counts(values, top):
    return [sum(1 for v in values if v == value) for value in range(top + 1)]


def _counting_sort(nums, top):
    return sorted(nums)


def _group_stable(records):
    out = []
    for team in sorted({record[0] for record in records}):
        out.extend(list(r) for r in records if r[0] == team)
    return out


def _sort_versions(versions):
    decorated = [([int(part) for part in v.split(".")], i, v)
                 for i, v in enumerate(versions)]
    decorated.sort()
    return [v for _, _, v in decorated]


def _words_by_length(words):
    alphabetical = sorted(words)
    return sorted(alphabetical, key=len)


def _top_k_frequent(items, k):
    from collections import Counter
    counts = Counter(items)
    order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [key for key, _ in order[:k]]


# --- union-find ------------------------------------------------------------

def _find_root(parent, x):
    """Recursive, so the canonical loop below has something to disagree with."""
    return x if parent[x] == x else _find_root(parent, parent[x])


def _neighbours(n, edges):
    adj = {v: [] for v in range(n)}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    return adj


def _same_group(n, edges, a, b):
    if not 0 <= a < n or not 0 <= b < n:
        return False
    adj = _neighbours(n, edges)
    seen, stack = {a}, [a]
    while stack:
        node = stack.pop()
        if node == b:
            return True
        for nxt in adj[node]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return b in seen


def _count_components(n, edges):
    adj = _neighbours(n, edges)
    seen, groups = set(), 0
    for start in range(n):
        if start in seen:
            continue
        groups += 1
        stack = [start]
        seen.add(start)
        while stack:
            node = stack.pop()
            for nxt in adj[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
    return groups


def _redundant_edge(edges):
    nodes = {v for edge in edges for v in edge}
    index = {v: i for i, v in enumerate(sorted(nodes))}
    kept = []
    for a, b in edges:
        if _same_group(len(index), [[index[x], index[y]] for x, y in kept],
                       index[a], index[b]):
            return [a, b]
        kept.append([a, b])
    return []


# --- topological order -----------------------------------------------------

def _indegrees(n, edges):
    from collections import Counter
    counts = Counter(b for _, b in edges)
    return [counts.get(v, 0) for v in range(n)]


def _sources(n, edges):
    targets = {b for _, b in edges}
    return [v for v in range(n) if v not in targets]


def _topo_order(n, edges):
    """Repeatedly take the smallest node nothing still points at. O(n^2), clear."""
    left = set(range(n))
    pending = [tuple(e) for e in edges]
    out = []
    while left:
        blocked = {b for a, b in pending if a in left and b in left}
        ready = sorted(v for v in left if v not in blocked)
        if not ready:
            return []
        pick = ready[0]
        out.append(pick)
        left.discard(pick)
        pending = [e for e in pending if e[0] != pick]
    return out


def _can_finish(n, prereqs):
    colour = [0] * n                       # 0 unseen, 1 on the stack, 2 finished
    adj = {v: [] for v in range(n)}
    for course, needs in prereqs:
        adj[needs].append(course)

    def walk(node):
        if colour[node] == 1:
            return False
        if colour[node] == 2:
            return True
        colour[node] = 1
        for nxt in adj[node]:
            if not walk(nxt):
                return False
        colour[node] = 2
        return True

    return all(walk(v) for v in range(n))


def _combinations_k(n, k):
    from itertools import combinations
    if k < 0 or k > n:
        return []
    return [list(c) for c in combinations(range(1, n + 1), k)]


# ===========================================================================
# The family
# ===========================================================================

def build() -> list:
    P: list = []

    # -- backtracking --------------------------------------------------------
    # The template is one shape, four lines long: choose, recurse, undo. Every
    # problem below is that shape with a different question in the base case.

    P.append(sp(
        "so-bt-subsets", "Take It Or Leave It", "GUIDED",
        """
        Return every subset of `nums` (the power set). Values are distinct and
        the order of the subsets does not matter.

        The code below is the backtracking template. At each index it takes the
        value, explores everything that follows, then *undoes* the choice and
        explores again without it. One line — the undo — is missing.
        """,
        "subsets", "nums", _subsets,
        """
        def subsets(nums):
            out = []

            def choose(index, path):
                if index == len(nums):
                    out.append(list(path))      # a copy: `path` keeps changing
                    return
                path.append(nums[index])        # take it
                choose(index + 1, path)
                path.pop()                      # put it back
                choose(index + 1, path)         # leave it

            choose(0, [])
            return out
        """,
        [("three", [[1, 2, 3]]), ("one", [[7]])],
        [("two", [[1, 2]]), ("four", [[1, 2, 3, 4]]), ("negatives", [[-1, 0]])],
        edges=[("empty", [[]])], cmp="set",
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(n * 2^n)", space="O(n * 2^n)",
        starter="""
        def subsets(nums):
            out = []

            def choose(index, path):
                if index == len(nums):
                    out.append(list(path))
                    return
                path.append(nums[index])        # take it
                choose(index + 1, path)
                __BLANK__                       # undo it, so the next branch is clean
                choose(index + 1, path)         # leave it

            choose(0, [])
            return out
        """,
        nudge="`path` is one list shared by every branch. Before exploring the "
              "branch that does not use this value, the value has to come off.",
        pseudocode="append -> recurse -> remove -> recurse",
        fragment=_same_move("stack.append(move)\nplay(stack)\nstack.pop()"),
        failures=["Appending `path` itself instead of `list(path)` — every "
                  "answer then points at the same list, which ends up empty"],
        tags=["backtracking", "template"],
    ))

    P.append(sp(
        "so-bt-binary-strings", "Every Rune Of Length n", "GUIDED",
        """
        Return every string of length `n` made of the characters "0" and "1".
        Order does not matter. `n` is at most 6.

        Same template, different alphabet: at each position, try "0", then try
        "1". The second try is missing.
        """,
        "binary_strings", "n", _binary_strings,
        """
        def binary_strings(n):
            out = []

            def build(prefix):
                if len(prefix) == n:
                    out.append(prefix)
                    return
                build(prefix + "0")
                build(prefix + "1")

            build("")
            return out
        """,
        [("two", [2]), ("three", [3])],
        [("one", [1]), ("four", [4]), ("six", [6])],
        edges=[("zero", [0])], cmp="set",
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(n * 2^n)", space="O(n * 2^n)",
        after="so-bt-subsets",
        starter="""
        def binary_strings(n):
            out = []

            def build(prefix):
                if len(prefix) == n:
                    out.append(prefix)
                    return
                build(prefix + "0")
                build(__BLANK__)

            build("")
            return out
        """,
        nudge="Strings are immutable, so there is nothing to undo here. The "
              "'undo' is free: the old `prefix` was never modified.",
        pseudocode="if long enough: record it\notherwise: extend with each symbol",
        fragment=_same_move('build(prefix + "x")'),
        failures=["Returning after the first branch, which explores half the tree"],
        tags=["backtracking", "template"],
    ))

    P.append(sp(
        "so-bt-permutations", "Every Order Of March", "TUTORIAL",
        """
        Return every ordering of `nums`. Values are distinct, and the order of
        the orderings does not matter.

        Same template again, with one addition: a position can only be used
        once, so you need to record which values are already in the path.
        """,
        "permutations", "nums", _permutations,
        """
        def permutations(nums):
            out, used, path = [], [False] * len(nums), []

            def walk():
                if len(path) == len(nums):
                    out.append(list(path))
                    return
                for i in range(len(nums)):
                    if used[i]:
                        continue
                    used[i] = True              # choose
                    path.append(nums[i])
                    walk()                      # explore
                    path.pop()                  # undo, both halves of it
                    used[i] = False

            walk()
            return out
        """,
        [("three", [[1, 2, 3]]), ("two", [[1, 2]])],
        [("one", [[9]]), ("four", [[1, 2, 3, 4]]), ("negatives", [[-1, 1]])],
        edges=[("empty", [[]])], cmp="set",
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(n * n!)", space="O(n * n!)",
        after="so-bt-binary-strings",
        starter_hint="choose / explore / undo, with a `used` flag per index",
        nudge="Every `used[i] = True` needs an exactly matching `used[i] = False`.",
        pseudocode="for each unused index: mark it, recurse, unmark it",
        failures=["Undoing `path` but forgetting `used`, which loses most orderings",
                  "Returning [] instead of [[]] for the empty input"],
        tags=["backtracking", "core"],
    ))

    P.append(sp(
        "so-bt-combinations", "Choosing k From n", "TUTORIAL",
        """
        Return every combination of `k` distinct numbers chosen from 1..`n`.
        Each combination must be in increasing order; the order of the
        combinations themselves does not matter.
        """,
        "combinations", "n, k", _combinations_k,
        """
        def combinations(n, k):
            out, path = [], []

            def walk(start):
                if len(path) == k:
                    out.append(list(path))
                    return
                for value in range(start, n + 1):
                    path.append(value)
                    walk(value + 1)             # +1: never look back
                    path.pop()

            if 0 <= k <= n:
                walk(1)
            return out
        """,
        [("four choose two", [4, 2]), ("three choose one", [3, 1])],
        [("five choose three", [5, 3]), ("n choose n", [4, 4]),
         ("choose one from one", [1, 1])],
        edges=[("k is zero", [3, 0]), ("k bigger than n", [2, 5])], cmp="set",
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(k * C(n, k))", space="O(k * C(n, k))",
        after="so-bt-permutations",
        starter_hint="a `start` index is what stops [1,2] and [2,1] both appearing",
        nudge="The difference between a permutation and a combination is one "
              "parameter: where the loop begins.",
        pseudocode="walk(start): for value in start..n: take it, walk(value+1), drop it",
        failures=["Looping from 1 every time, which produces permutations",
                  "Recursing with `value` instead of `value + 1`, which reuses it"],
        tags=["backtracking", "core"],
    ))

    P.append(sp(
        "so-bt-combination-sum", "Runes That Add Up", "EASY",
        """
        Given positive `candidates` and a positive `target`, return every
        combination of candidates that sums to exactly `target`. A candidate may
        be used any number of times. Each combination must be in non-decreasing
        order, and no two combinations may be the same multiset.

        Return `[]` if the target cannot be made, or if it is not positive.
        """,
        "combination_sum", "candidates, target", _combination_sum,
        """
        def combination_sum(candidates, target):
            pool = sorted({value for value in candidates if value > 0})
            out, path = [], []

            def walk(start, remaining):
                if remaining == 0:
                    out.append(list(path))
                    return
                for i in range(start, len(pool)):
                    if pool[i] > remaining:
                        break                   # sorted, so everything after is worse
                    path.append(pool[i])
                    walk(i, remaining - pool[i])    # i, not i+1: reuse is allowed
                    path.pop()

            if target > 0:
                walk(0, target)
            return out
        """,
        [("classic", [[2, 3, 6, 7], 7]), ("two ways", [[2, 3], 6])],
        [("single candidate", [[3], 9]), ("impossible", [[5, 7], 3]),
         ("duplicated candidates", [[2, 2, 3], 6]),
         ("target equals a candidate", [[4, 9], 4])],
        edges=[("empty candidates", [[], 5]), ("zero target", [[1, 2], 0]),
               ("negative target", [[1], -2])], cmp="set",
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(n^(target/min))", space="O(target)",
        after="so-bt-combinations",
        starter_hint="sort first; pass `i` (not `i + 1`) to allow reuse",
        nudge="Two knobs decide the shape: where the loop starts, and whether the "
              "recursive call may pick the same index again.",
        pseudocode="walk(start, left): for i from start: if pool[i] <= left:\n"
                   "  take it, walk(i, left - pool[i]), drop it",
        failures=["Starting the loop at 0, which produces [2,3] and [3,2] both",
                  "Not de-duplicating candidates, which duplicates whole branches"],
        tags=["backtracking", "core"],
    ))

    P.append(sp(
        "so-bt-parentheses", "Well-Formed Wards", "EASY",
        """
        Return every well-formed string of `n` pairs of parentheses. Order does
        not matter. `n` is at most 6, and `n == 0` yields the empty string.

        A prefix is still usable while it has no more closers than openers, and
        no more openers than `n`. Those two conditions are the whole problem.
        """,
        "generate_parentheses", "n", _generate_parentheses,
        """
        def generate_parentheses(n):
            out = []

            def walk(text, opened, closed):
                if len(text) == 2 * n:
                    out.append(text)
                    return
                if opened < n:                  # room for another opener
                    walk(text + "(", opened + 1, closed)
                if closed < opened:             # an opener is waiting to be closed
                    walk(text + ")", opened, closed + 1)

            walk("", 0, 0)
            return out
        """,
        [("two pairs", [2]), ("three pairs", [3])],
        [("one pair", [1]), ("four pairs", [4]), ("five pairs", [5])],
        edges=[("zero pairs", [0])], cmp="set",
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(4^n / sqrt(n))", space="O(4^n / sqrt(n))",
        after="so-bt-combination-sum",
        starter_hint="carry `opened` and `closed` counts; prune instead of filtering",
        nudge="Generating all 2^(2n) strings and filtering works and is slow. "
              "Refusing to write an illegal character is the same answer, sooner.",
        pseudocode="if opened < n: try '('\nif closed < opened: try ')'",
        failures=["Testing `closed < n` instead of `closed < opened`, which "
                  "produces ')(' "],
        tags=["backtracking", "pruning"],
    ))

    P.append(sp(
        "so-bt-palindrome-partition", "Cutting The Mirror", "MEDIUM",
        """
        Return every way to cut `s` into pieces where every piece is a
        palindrome. Each answer is the list of pieces, left to right. The order
        of the answers does not matter. `s` is at most 8 characters.

        The empty string has exactly one partition: the empty list of pieces.
        """,
        "palindrome_partitions", "s", _palindrome_partitions,
        """
        def palindrome_partitions(s):
            out, path = [], []

            def walk(start):
                if start == len(s):
                    out.append(list(path))
                    return
                for end in range(start + 1, len(s) + 1):
                    piece = s[start:end]
                    if piece == piece[::-1]:    # only then is the branch worth taking
                        path.append(piece)
                        walk(end)
                        path.pop()

            walk(0)
            return out
        """,
        [("aab", ["aab"]), ("aba", ["aba"])],
        [("all same", ["aaa"]), ("no palindromic cut but singles", ["abc"]),
         ("even palindrome", ["abba"]), ("longer", ["aabaa"])],
        edges=[("empty", [""]), ("single", ["z"])], cmp="set",
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(n * 2^n)", space="O(n * 2^n)",
        after="so-bt-parentheses",
        starter_hint="the choice at each step is where the next cut goes",
        nudge="Single characters are always palindromes, so every string has at "
              "least one partition. The recursion can never dead-end.",
        pseudocode="walk(start): for end in start+1..n:\n"
                   "  if s[start:end] is a palindrome: take it, walk(end), drop it",
        failures=["Checking the palindrome after recursing rather than before",
                  "Returning [] for the empty string instead of [[]]"],
        tags=["backtracking", "strings"],
    ))

    P.append(sp(
        "so-bt-word-search", "The Word In The Grid", "MEDIUM",
        """
        `board` is a grid of single characters. Return True if `word` can be
        spelled by walking the grid from cell to cell, moving up, down, left or
        right, without using the same cell twice.

        The empty word is always found.
        """,
        "word_search", "board, word", _word_search,
        """
        def word_search(board, word):
            if not word:
                return True
            rows = len(board)
            cols = len(board[0]) if rows else 0

            def walk(r, c, k):
                if board[r][c] != word[k]:
                    return False
                if k == len(word) - 1:
                    return True
                keep = board[r][c]
                board[r][c] = None              # mark: this cell is on the path
                for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if 0 <= nr < rows and 0 <= nc < cols and walk(nr, nc, k + 1):
                        board[r][c] = keep
                        return True
                board[r][c] = keep              # unmark: the undo, again
                return False

            return any(walk(r, c, 0) for r in range(rows) for c in range(cols))
        """,
        [("found", [[["a", "b"], ["c", "d"]], "abdc"]),
         ("not found", [[["a", "b"], ["c", "d"]], "abc"])],
        [("needs a turn", [[["a", "b", "c"], ["f", "e", "d"]], "abcdef"]),
         ("no reuse allowed", [[["a", "b"], ["c", "d"]], "aba"]),
         ("single cell", [[["z"]], "z"]),
         ("longer than the grid", [[["a", "a"], ["a", "a"]], "aaaaa"])],
        edges=[("empty word", [[["a"]], ""]), ("empty board", [[], "a"])],
        pattern="DFS", family="backtracking", realm="matrix_citadel",
        viz=VIZ_CHOICE, secondary=["MATRIX", "RECURSION"],
        time="O(rows * cols * 4^len(word))", space="O(len(word))",
        after="so-bt-palindrome-partition",
        starter_hint="mark the cell before recursing, restore it after",
        nudge="The visited set can live in the board itself: overwrite the cell, "
              "recurse, put the character back.",
        pseudocode="for every cell: walk(cell, 0)\n"
                   "walk: char must match; mark; try 4 neighbours; unmark",
        failures=["Forgetting to restore the cell, which poisons every later start",
                  "Restoring the cell only on failure, so a successful path stays marked"],
        tags=["backtracking", "grid"],
    ))

    P.append(sp(
        "so-bt-n-queens", "The Eight Crowns", "HARD",
        """
        Return how many ways `n` queens can be placed on an `n` x `n` board so
        that no two share a row, a column, or a diagonal. `n` is at most 8.

        `n == 0` has one placement (the empty one), and `n == 2` and `n == 3`
        have none.
        """,
        "count_queens", "n", _n_queens,
        """
        def count_queens(n):
            columns, diagonal, anti = set(), set(), set()

            def place(row):
                if row == n:
                    return 1
                total = 0
                for col in range(n):
                    # one queen per row is built in; these three sets rule out
                    # the column and both diagonals in O(1)
                    if col in columns or row - col in diagonal or row + col in anti:
                        continue
                    columns.add(col)
                    diagonal.add(row - col)
                    anti.add(row + col)
                    total += place(row + 1)
                    columns.discard(col)
                    diagonal.discard(row - col)
                    anti.discard(row + col)
                return total

            return place(0)
        """,
        [("four", [4]), ("five", [5])],
        [("one", [1]), ("six", [6]), ("seven", [7]), ("eight", [8])],
        edges=[("zero", [0]), ("two has none", [2]), ("three has none", [3])],
        pattern="RECURSION", family="backtracking", realm="recursive_forest",
        viz=VIZ_CHOICE, time="O(n!)", space="O(n)",
        after="so-bt-word-search", boss=True,
        starter_hint="one queen per row; track columns and both diagonal families",
        nudge="Two cells are on the same diagonal exactly when `row - col` "
              "matches, and on the same anti-diagonal when `row + col` matches.",
        pseudocode="place(row): if row == n: count 1\n"
                   "for each free column: claim it and both diagonals, place(row+1), release",
        failures=["Scanning the whole board for conflicts, which is correct and slow",
                  "Releasing the column but not the diagonals"],
        tags=["backtracking", "pruning", "classic"],
    ))

    # -- greedy --------------------------------------------------------------
    # Greed is a claim, not a technique: "the locally best step is part of a
    # globally best answer". Sometimes true. The MEDIUM rungs are where the
    # player has to check rather than assume.

    P.append(sp(
        "so-greedy-cookies", "Feeding The Smallest Appetite First", "GUIDED",
        """
        `greed[i]` is how big a cookie child `i` insists on. `size[j]` is the
        size of cookie `j`. A child is satisfied by any cookie at least as big
        as their demand, and each cookie goes to at most one child. Return how
        many children can be satisfied.

        Both lists are already sorted by the code below. Walking them together,
        the smallest cookie that can satisfy the current child should go to that
        child. The comparison is missing.
        """,
        "assign_cookies", "greed, size", _assign_cookies,
        """
        def assign_cookies(greed, size):
            kids = sorted(greed)
            cookies = sorted(size)
            i = j = fed = 0
            while i < len(kids) and j < len(cookies):
                if cookies[j] >= kids[i]:       # this cookie is big enough
                    fed += 1
                    i += 1
                j += 1                          # either way, the cookie is spent
            return fed
        """,
        [("two fed", [[1, 2, 3], [1, 1, 3]]), ("one fed", [[1, 2], [1, 1]])],
        [("all fed", [[1, 2], [2, 3]]), ("none fed", [[5, 6], [1, 2]]),
         ("more cookies than kids", [[2], [1, 1, 9]])],
        edges=[("no kids", [[], [1, 2]]), ("no cookies", [[1], []])],
        pattern="SORTING", family="greedy", realm="stack_queue_mines",
        secondary=["GREEDY", "TWO_POINTER"], time="O(n log n)", space="O(n)",
        starter="""
        def assign_cookies(greed, size):
            kids = sorted(greed)
            cookies = sorted(size)
            i = j = fed = 0
            while i < len(kids) and j < len(cookies):
                if __BLANK__:                   # is this cookie big enough?
                    fed += 1
                    i += 1
                j += 1
            return fed
        """,
        nudge="A cookie satisfies a child when it is at least as big as the "
              "child's demand. Both indices point at the smallest one left.",
        pseudocode="sort both; walk together; if cookie fits the child, feed them",
        fragment=_same_move("if supply[j] >= demand[i]:\n    matched += 1"),
        failures=["Advancing `i` even when the child was not fed, which skips them"],
        tags=["greedy", "sorting"],
    ))

    P.append(sp(
        "so-greedy-us-coins", "Largest Coin First", "GUIDED",
        """
        Return the fewest coins needed to make `amount` out of 25s, 10s, 5s and
        1s. `amount` is at least 0.

        With these four denominations, taking as many of the largest coin as
        will fit is provably optimal — a fact about *these* coins, not about
        greed. The line that decides how many of the current coin to take is
        missing.
        """,
        "min_coins", "amount", _us_coins,
        """
        def min_coins(amount):
            count = 0
            for coin in (25, 10, 5, 1):
                count += amount // coin         # how many of this coin fit
                amount %= coin                  # what is still owed
            return count
        """,
        [("thirty", [30]), ("ninety nine", [99])],
        [("exact quarter", [25]), ("one", [1]), ("forty one", [41])],
        edges=[("zero", [0]), ("four", [4])],
        pattern="SIMULATION", family="greedy", realm="stack_queue_mines",
        secondary=["GREEDY"], time="O(1)", space="O(1)",
        after="so-greedy-cookies",
        starter="""
        def min_coins(amount):
            count = 0
            for coin in (25, 10, 5, 1):
                count += __BLANK__              # how many of this coin fit?
                amount %= coin
            return count
        """,
        nudge="Integer division answers 'how many whole times does this fit'. "
              "`%` answers 'what is left over'. You want both, in that order.",
        pseudocode="for each coin, largest first: take amount // coin of them",
        fragment=_same_move("boxes += items // per_box\nitems %= per_box"),
        failures=["Using `/` instead of `//`, which returns a float",
                  "Updating `amount` before counting, which loses the coin"],
        tags=["greedy", "math"],
    ))

    P.append(sp(
        "so-greedy-profit", "Every Rise Is Yours", "TUTORIAL",
        """
        `prices[i]` is a price on day `i`. You may buy and sell as often as you
        like, but you may hold at most one unit at a time. Return the maximum
        total profit.

        You are allowed to sell and rebuy on the same day, which quietly turns
        this into a much smaller problem than it looks.
        """,
        "max_profit", "prices", _max_profit,
        """
        def max_profit(prices):
            total = 0
            for i in range(1, len(prices)):
                if prices[i] > prices[i - 1]:
                    total += prices[i] - prices[i - 1]   # bank every rise
            return total
        """,
        [("classic", [[7, 1, 5, 3, 6, 4]]), ("rising", [[1, 2, 3, 4, 5]])],
        [("falling", [[5, 4, 3, 2, 1]]), ("flat", [[3, 3, 3]]),
         ("one dip", [[2, 1, 4]])],
        edges=[("empty", [[]]), ("single", [[9]])],
        pattern="ARRAY", family="greedy", realm="stack_queue_mines",
        secondary=["GREEDY"], time="O(n)", space="O(1)",
        after="so-greedy-us-coins",
        starter_hint="you never need to know where a 'trade' started",
        nudge="Any profitable run from a low to a high equals the sum of the "
              "day-to-day rises inside it. So collect the rises.",
        pseudocode="total = sum of (prices[i] - prices[i-1]) where that is positive",
        failures=["Tracking a buy price and a sell price, which is the harder "
                  "problem where only one transaction is allowed"],
        tags=["greedy"],
    ))

    P.append(sp(
        "so-greedy-change", "The Largest-Coin Reflex", "TUTORIAL",
        """
        Return how many coins the largest-first strategy uses to make `amount`
        from `coins`, or -1 if that strategy gets stuck with a remainder it
        cannot pay. `coins` are positive and `amount` is at least 0.

        This is deliberately not "the fewest coins". It is "what greed does".
        You will need the difference shortly.
        """,
        "greedy_change", "amount, coins", _greedy_change,
        """
        def greedy_change(amount, coins):
            left, used = amount, 0
            for coin in sorted(coins, reverse=True):
                take, left = divmod(left, coin)
                used += take
            return used if left == 0 else -1
        """,
        [("us coins", [30, [1, 5, 10, 25]]), ("greedy gets stuck", [6, [3, 4]])],
        [("exact single coin", [7, [7]]), ("unsorted input", [12, [10, 1, 5]]),
         ("no ones available", [8, [4, 3]]), ("needs many", [9, [1]])],
        edges=[("zero amount", [0, [1, 5]]), ("no coins", [5, []]),
               ("coin too large", [3, [5]])],
        pattern="SIMULATION", family="greedy", realm="stack_queue_mines",
        secondary=["GREEDY"], time="O(n log n)", space="O(1)",
        after="so-greedy-profit",
        starter_hint="sort descending, then divmod your way down",
        nudge="`divmod(left, coin)` hands back how many fit and what remains, in "
              "one call.",
        pseudocode="for coin in sorted descending: take, left = divmod(left, coin)",
        failures=["Returning `used` when a remainder is left, which reports a "
                  "count for change that was never actually made"],
        tags=["greedy", "math"],
    ))

    P.append(sp(
        "so-greedy-jump", "How Far The Road Reaches", "EASY",
        """
        `nums[i]` is the maximum number of steps you may jump forward from index
        `i`. Starting at index 0, return True if the last index is reachable.

        An empty list counts as already arrived.
        """,
        "can_jump", "nums", _jump_game,
        """
        def can_jump(nums):
            goal = len(nums) - 1
            # walk backwards: a cell is good if it can reach the nearest good one
            for i in range(len(nums) - 1, -1, -1):
                if i + nums[i] >= goal:
                    goal = i
            return goal <= 0
        """,
        [("reachable", [[2, 3, 1, 1, 4]]), ("blocked", [[3, 2, 1, 0, 4]])],
        [("single zero", [[0]]), ("long enough first jump", [[5, 0, 0, 0, 0, 0]]),
         ("zero in the middle is survivable", [[2, 0, 1]]),
         ("stops one short", [[1, 0, 1]])],
        edges=[("empty", [[]]), ("two zeros", [[0, 0]])],
        pattern="GREEDY", family="greedy", realm="stack_queue_mines",
        secondary=["ARRAY"], time="O(n)", space="O(1)",
        after="so-greedy-change",
        starter_hint="one number is enough: the furthest index reached so far",
        nudge="Forwards, carry the furthest reachable index and fail the moment "
              "the loop index passes it. Backwards, shrink the goal.",
        pseudocode="reach = 0\nfor i, step: if i > reach: fail\n"
                   "reach = max(reach, i + step)",
        failures=["Jumping exactly `nums[i]` every time — the value is a maximum, "
                  "not a requirement",
                  "Deciding a 0 is fatal; only a 0 you cannot jump over is"],
        tags=["greedy", "classic"],
    ))

    P.append(sp(
        "so-greedy-meetings", "As Many Meetings As Will Fit", "EASY",
        """
        Each meeting is `[start, end)` — it holds `start` and releases the room
        at `end`, so `[9, 10]` and `[10, 11]` do not collide. Return the largest
        number of meetings one room can host.

        The greedy choice here is provable: always take the meeting that *ends*
        soonest among those that still fit. Ending early leaves the most room
        for everything after it.
        """,
        "max_meetings", "meetings", _max_meetings,
        """
        def max_meetings(meetings):
            taken, free_at = 0, None
            for start, end in sorted(meetings, key=lambda m: m[1]):
                if free_at is None or start >= free_at:
                    taken += 1
                    free_at = end
            return taken
        """,
        [("three fit", [[[1, 3], [2, 4], [3, 5]]]),
         ("all overlap", [[[1, 9], [2, 9], [3, 9]]])],
        [("touching ends", [[[1, 2], [2, 3], [3, 4]]]),
         ("unsorted", [[[5, 6], [1, 2], [2, 5]]]),
         ("nested", [[[1, 10], [2, 3], [4, 5]]]),
         ("duplicates", [[[1, 2], [1, 2]]])],
        edges=[("empty", [[]]), ("single", [[[4, 7]]]),
               ("zero length", [[[3, 3], [3, 4]]])],
        pattern="GREEDY", family="greedy", realm="stack_queue_mines",
        secondary=["INTERVALS", "SORTING"], time="O(n log n)", space="O(1)",
        after="so-greedy-jump",
        starter_hint="sort by END, not by start",
        nudge="Sorting by start looks natural and is wrong: one long early "
              "meeting then eats the whole day.",
        pseudocode="sort by end\nfor each: if it starts after the room is free, take it",
        failures=["Sorting by start time",
                  "Sorting by duration, which fails on [[1,9],[2,3],[4,5]]"],
        tags=["greedy", "intervals", "classic"],
    ))

    P.append(mcq_problem(
        id="so-greedy-fails", title="Where Greed Goes Wrong",
        realm="stack_queue_mines", pattern="GREEDY", difficulty="EASY",
        family="greedy",
        statement="""
        You need to make 6 using coins worth 1, 3 and 4. The largest-first
        strategy takes a 4, then cannot use another 4, so it takes 1 and 1 —
        three coins.

        What does this tell you?
        """,
        choices=[
            "Greedy is wrong here: 3 + 3 makes 6 in two coins, so largest-first "
            "is not optimal for this coin set",
            "Greedy is fine; three coins is the best possible for 6",
            "Greedy failed because the coins were not sorted first",
            "Greedy failed because 6 is not divisible by 4",
        ],
        answer=0,
        explanation="""
        Two coins of 3 make 6. Largest-first returns three coins, so it is not
        optimal — for *these* denominations.

        This is the whole lesson of greedy algorithms. The strategy is not
        wrong in general; it is wrong for this coin system. With 1/5/10/25 it
        happens to be optimal, and that is a provable property of those
        denominations, not of the loop you wrote. When a greedy step cannot be
        justified, the honest fallback is dynamic programming over every amount,
        which is what `so-greedy-vs-optimal` makes you write.

        The reflex to build: before shipping a greedy solution, try to construct
        the input that breaks it. If you cannot, say out loud why not.
        """,
        seconds=90,
    ))

    P.append(sp(
        "so-greedy-vs-optimal", "The Gap Between Greed And Truth", "MEDIUM",
        """
        Return `[greedy_count, optimal_count]` for making `amount` from `coins`:

        - `greedy_count` is how many coins largest-first uses, or -1 if that
          strategy gets stuck.
        - `optimal_count` is the true minimum number of coins, or -1 if the
          amount cannot be made at all.

        `coins` are positive; `amount` is at least 0. When the two numbers
        differ, you have a concrete counterexample to greed on that coin set.
        """,
        "greedy_vs_optimal", "coins, amount", _greedy_vs_optimal,
        """
        def greedy_vs_optimal(coins, amount):
            left, greedy = amount, 0
            for coin in sorted(coins, reverse=True):
                take, left = divmod(left, coin)
                greedy += take
            if left:
                greedy = -1

            # the honest answer: best[value] is the fewest coins making `value`
            best = [0] + [None] * amount
            for value in range(1, amount + 1):
                options = [best[value - coin] for coin in coins
                           if coin <= value and best[value - coin] is not None]
                if options:
                    best[value] = min(options) + 1
            return [greedy, -1 if best[amount] is None else best[amount]]
        """,
        [("greedy loses", [[1, 3, 4], 6]), ("greedy wins", [[1, 5, 10, 25], 30])],
        [("greedy stuck, optimal exists", [[3, 4], 6]),
         ("neither can pay", [[5, 7], 3]),
         ("single denomination", [[2], 8]),
         ("greedy loses badly", [[1, 7, 10], 14])],
        edges=[("zero amount", [[1, 2], 0]), ("no coins", [[], 4]),
               ("coin equals amount", [[9], 9])],
        pattern="GREEDY", family="greedy", realm="stack_queue_mines",
        secondary=["DP"], time="O(amount * len(coins))", space="O(amount)",
        after="so-greedy-meetings",
        starter_hint="write both answers; the second one is a small DP",
        nudge="The DP is four lines: best[0] = 0, and best[v] is one more than "
              "the cheapest reachable best[v - coin].",
        pseudocode="greedy: divmod down the sorted coins\n"
                   "optimal: best[v] = 1 + min(best[v - c]) over usable coins",
        failures=["Treating unreachable amounts as 0 instead of unreachable, "
                  "which makes every later amount lie",
                  "Assuming greedy stuck implies optimal impossible — [3,4] "
                  "cannot greedily make 6, but 3+3 can"],
        tags=["greedy", "dp", "judgement"],
    ))

    P.append(sp(
        "so-greedy-gas", "One Lap Of The Ring Road", "MEDIUM",
        """
        `gas[i]` is the fuel available at station `i`; `cost[i]` is the fuel
        needed to drive from station `i` to station `i+1`, wrapping around at
        the end. Starting empty at some station, return the smallest starting
        index from which you can complete the whole loop, or -1 if none can.
        """,
        "gas_station", "gas, cost", _gas_station,
        """
        def gas_station(gas, cost):
            if sum(gas) < sum(cost):
                return -1                       # not enough fuel in the world
            start, tank = 0, 0
            for i in range(len(gas)):
                tank += gas[i] - cost[i]
                if tank < 0:
                    # nothing from `start` to `i` can be a start either: each of
                    # them left the tank non-negative until here
                    start, tank = i + 1, 0
            return start
        """,
        [("classic", [[1, 2, 3, 4, 5], [3, 4, 5, 1, 2]]),
         ("impossible", [[2, 3, 4], [3, 4, 3]])],
        [("start at zero", [[4, 1], [1, 4]]),
         ("exactly enough", [[1, 1], [1, 1]]),
         ("last station only", [[0, 0, 5], [1, 1, 1]]),
         ("surplus everywhere", [[5, 5, 5], [1, 1, 1]])],
        edges=[("single station, enough", [[3], [2]]),
               ("single station, not enough", [[1], [2]])],
        pattern="GREEDY", family="greedy", realm="stack_queue_mines",
        secondary=["ARRAY"], time="O(n)", space="O(1)",
        after="so-greedy-vs-optimal",
        starter_hint="one pass; when the tank goes negative, restart after that point",
        nudge="If the total fuel covers the total cost, exactly one start works. "
              "The only question is which, and a single pass finds it.",
        pseudocode="if sum(gas) < sum(cost): -1\n"
                   "tank += gas[i] - cost[i]; if tank < 0: start = i + 1, tank = 0",
        failures=["Trying every start and simulating, which is O(n^2) and will "
                  "be called out even when it passes",
                  "Forgetting the total check, which returns a start that fails"],
        tags=["greedy", "classic"],
    ))

    P.append(sp(
        "so-greedy-min-jumps", "Fewest Leaps", "MEDIUM",
        """
        `nums[i]` is the maximum jump length from index `i`. Starting at index
        0, return the fewest jumps needed to reach the last index, or -1 if it
        cannot be reached. An empty list, or a list of one, needs 0 jumps.
        """,
        "min_jumps", "nums", _min_jumps,
        """
        def min_jumps(nums):
            n = len(nums)
            if n <= 1:
                return 0
            jumps, end_of_level, furthest = 0, 0, 0
            for i in range(n - 1):
                if i > furthest:
                    return -1                   # this index was never reachable
                furthest = max(furthest, i + nums[i])
                if i == end_of_level:           # the current jump is used up
                    jumps += 1
                    end_of_level = furthest
            return jumps if furthest >= n - 1 else -1
        """,
        [("classic", [[2, 3, 1, 1, 4]]), ("blocked", [[3, 2, 1, 0, 4]])],
        [("one big jump", [[5, 1, 1, 1, 1, 1]]),
         ("all ones", [[1, 1, 1, 1]]),
         ("stalls immediately", [[0, 1]]),
         ("two zeros at the end", [[2, 0, 0]])],
        edges=[("empty", [[]]), ("single", [[0]]), ("pair", [[1, 0]])],
        pattern="GREEDY", family="greedy", realm="stack_queue_mines",
        secondary=["ARRAY"], time="O(n)", space="O(1)",
        after="so-greedy-gas",
        starter_hint="this is BFS by levels, written without a queue",
        nudge="Every jump defines a window of indices reachable with that many "
              "jumps. You only pay for a jump when you leave the current window.",
        pseudocode="furthest = max(furthest, i + nums[i])\n"
                   "when i reaches the end of this level: jumps += 1; level ends at furthest",
        failures=["Counting a jump per index rather than per level",
                  "Ignoring unreachable inputs and returning a plausible number"],
        tags=["greedy", "bfs-shaped"],
    ))

    # -- bit manipulation ----------------------------------------------------
    # Four operators carry almost all of it: >> to move a bit into view, & to
    # ask about it, | to set it, ^ to flip it. Everything below is those four.

    P.append(sp(
        "so-bit-read", "Reading One Bit", "GUIDED",
        """
        Return bit `i` of the non-negative integer `n`, counting from 0 at the
        least significant end. `bit_at(5, 0)` is 1 and `bit_at(5, 1)` is 0,
        because 5 is 101 in binary.

        The trick is always the same two moves: shift the bit you want down to
        position 0, then mask off everything else. One expression is missing.
        """,
        "bit_at", "n, i", _bit_at,
        """
        def bit_at(n, i):
            return (n >> i) & 1     # slide bit i down to the end, keep only it
        """,
        [("bit zero of five", [5, 0]), ("bit one of five", [5, 1])],
        [("bit two of five", [5, 2]), ("above the number", [5, 5]),
         ("zero", [0, 3]), ("a power of two", [8, 3])],
        edges=[("bit zero of zero", [0, 0]), ("large index", [1, 30])],
        pattern="SIMULATION", family="bits", realm="python_village",
        time="O(1)", space="O(1)",
        starter="""
        def bit_at(n, i):
            return __BLANK__ & 1    # first slide bit i down to position 0
        """,
        nudge="`n >> i` throws away the lowest `i` bits. `& 1` keeps only the "
              "lowest bit of whatever is left.",
        pseudocode="shift right by i, then mask with 1",
        fragment=_same_move("high_nibble = (byte >> 4) & 0b1111"),
        failures=["Using `and` instead of `&` — one is boolean logic, the other "
                  "works on bits"],
        tags=["bits"],
    ))

    P.append(sp(
        "so-bit-power-of-two", "One Bit Standing", "GUIDED",
        """
        Return True if `n` is a power of two. 1, 2, 4, 8 are; 0, 3, 6 and every
        negative number are not.

        A power of two has exactly one bit set. Subtracting one flips that bit
        off and turns everything below it on, so the two values share no bits at
        all. The mask is missing.
        """,
        "is_power_of_two", "n", _is_power_of_two,
        """
        def is_power_of_two(n):
            # 8 is 1000, 7 is 0111 -> 8 & 7 == 0. Only powers of two do that.
            return n > 0 and n & (n - 1) == 0
        """,
        [("eight", [8]), ("six", [6])],
        [("one", [1]), ("two", [2]), ("three", [3]), ("big power", [1024])],
        edges=[("zero", [0]), ("negative", [-4])],
        pattern="SIMULATION", family="bits", realm="python_village",
        time="O(1)", space="O(1)", after="so-bit-read",
        starter="""
        def is_power_of_two(n):
            return n > 0 and __BLANK__ == 0      # n and n-1 must share no bits
        """,
        nudge="`n - 1` clears the lowest set bit and sets everything under it. "
              "Now ask whether the two numbers have any bit in common.",
        pseudocode="n > 0 and (n & (n - 1)) == 0",
        fragment=_same_move("without_lowest_bit = value & (value - 1)"),
        failures=["Dropping the `n > 0` guard: 0 & -1 is 0, so zero would pass",
                  "Writing `n & n - 1` and trusting precedence — `-` binds tighter "
                  "than `&`, so it happens to work, but say what you mean"],
        tags=["bits"],
    ))

    P.append(sp(
        "so-bit-single-number", "The Unpaired Rune", "TUTORIAL",
        """
        Every value in `nums` appears exactly twice, except one that appears
        once. Return that one, using constant extra space.

        XOR is its own undo: `x ^ x` is 0, and `x ^ 0` is x. Order does not
        matter, so every pair cancels itself no matter where the two halves sit.
        """,
        "single_number", "nums", _single_number,
        """
        def single_number(nums):
            odd_one = 0
            for value in nums:
                odd_one ^= value        # pairs cancel; the loner survives
            return odd_one
        """,
        [("classic", [[4, 1, 2, 1, 2]]), ("single element", [[7]])],
        [("loner first", [[9, 3, 3]]), ("loner last", [[5, 5, 8]]),
         ("zeros present", [[0, 1, 1]]), ("longer", [[2, 3, 4, 3, 2, 5, 5]])],
        edges=[("loner is zero", [[0, 6, 6]]), ("two pairs and a loner", [[1, 1, 2, 2, 9]])],
        pattern="SIMULATION", family="bits", realm="python_village",
        secondary=["ARRAY"], time="O(n)", space="O(1)", after="so-bit-power-of-two",
        starter_hint="one accumulator, one operator",
        nudge="A Counter solves this in O(n) space. The interviewer is asking "
              "for O(1), and XOR is the only thing that gives it to you.",
        pseudocode="acc = 0; for v: acc ^= v; return acc",
        failures=["Sorting and comparing neighbours, which costs O(n log n) for "
                  "no gain"],
        tags=["bits", "classic"],
    ))

    P.append(sp(
        "so-bit-flags", "Setting And Clearing A Mask", "TUTORIAL",
        """
        `flags` is a non-negative integer used as a bag of boolean switches, and
        `mask` marks which switches this call is about. Return `flags` with
        every bit in `mask` turned on when `enable` is True, or turned off when
        it is False. Bits outside the mask never change.

        This is how permission bits, feature flags and packet headers are
        actually manipulated.
        """,
        "apply_flags", "flags, mask, enable", _apply_flags,
        """
        def apply_flags(flags, mask, enable):
            if enable:
                return flags | mask     # OR turns bits on
            return flags & ~mask        # AND with the inverse turns them off
        """,
        [("turn on", [0b1000, 0b0011, True]), ("turn off", [0b1011, 0b0010, False])],
        [("already on", [0b0011, 0b0001, True]),
         ("already off", [0b1000, 0b0100, False]),
         ("full mask", [0b0101, 0b1111, True]),
         ("empty mask", [0b0101, 0, False])],
        edges=[("zero flags", [0, 0b101, True]), ("clear everything", [0b1111, 0b1111, False])],
        pattern="SIMULATION", family="bits", realm="python_village",
        time="O(1)", space="O(1)", after="so-bit-single-number",
        starter_hint="| to set, & ~ to clear",
        nudge="`~mask` is the mask with every bit flipped, so ANDing with it "
              "keeps everything the mask did not name.",
        pseudocode="on:  flags | mask\noff: flags & ~mask",
        failures=["Using `^` to clear, which toggles and so turns an off bit on",
                  "Using `flags - mask`, which borrows across bits and is not "
                  "the same operation at all"],
        tags=["bits", "security"],
    ))

    P.append(sp(
        "so-bit-counting-bits", "Counting Every Crown", "EASY",
        """
        Return a list of length `n + 1` where entry `i` is the number of 1 bits
        in `i`. `n` is at least 0.

        Calling a popcount on every number is fine. There is a cheaper way: `i`
        has the same bits as `i >> 1`, plus its own lowest bit.
        """,
        "counting_bits", "n", _counting_bits,
        """
        def counting_bits(n):
            out = [0] * (n + 1)
            for i in range(1, n + 1):
                out[i] = out[i >> 1] + (i & 1)  # the answer for i//2, plus this bit
            return out
        """,
        [("to five", [5]), ("to two", [2])],
        [("to one", [1]), ("to eight", [8]), ("to sixteen", [16]),
         ("to thirty one", [31])],
        edges=[("zero", [0])],
        perf=[("to fifty thousand", [50000])],
        pattern="SIMULATION", family="bits", realm="python_village",
        secondary=["DP", "ARRAY"], time="O(n)", space="O(n)",
        after="so-bit-flags",
        starter_hint="each answer is built from an earlier one",
        nudge="Dropping the last bit of `i` gives a number you have already "
              "solved, because it is smaller than `i`.",
        pseudocode="out[i] = out[i >> 1] + (i & 1)",
        failures=["Recomputing the popcount of every number from scratch, which "
                  "is O(n log n) when O(n) is available"],
        tags=["bits", "dp"],
    ))

    P.append(sp(
        "so-bit-missing-number", "The Number That Never Came", "EASY",
        """
        `nums` holds `n` distinct values drawn from 0..`n` with exactly one
        missing. Return the missing value, without allocating a set.

        XOR every index together with every value: everything present cancels,
        and the absentee is what remains.
        """,
        "missing_number", "nums", _missing_number,
        """
        def missing_number(nums):
            missing = len(nums)         # the one index the loop cannot reach
            for i, value in enumerate(nums):
                missing ^= i ^ value
            return missing
        """,
        [("middle missing", [[3, 0, 1]]), ("last missing", [[0, 1]])],
        [("first missing", [[1, 2, 3]]), ("single zero present", [[0]]),
         ("single one present", [[1]]), ("shuffled", [[4, 2, 0, 1]])],
        edges=[("empty", [[]]), ("two values", [[2, 0]])],
        pattern="SIMULATION", family="bits", realm="python_village",
        secondary=["ARRAY"], time="O(n)", space="O(1)",
        after="so-bit-counting-bits",
        starter_hint="seed the accumulator with len(nums), then XOR index and value",
        nudge="The sum formula n(n+1)/2 minus the actual sum also works. XOR is "
              "the version that cannot overflow in a fixed-width language.",
        pseudocode="acc = len(nums)\nfor i, v: acc ^= i ^ v",
        failures=["Forgetting to seed with `len(nums)`, which loses the top index"],
        tags=["bits", "classic"],
    ))

    P.append(sp(
        "so-bit-two-singles", "Two Runes Unpaired", "MEDIUM",
        """
        Every value in `nums` appears exactly twice except two values that
        appear once. Return those two, sorted ascending. All values are
        non-negative.

        XORing everything leaves `a ^ b`. Any bit still set in that result is a
        bit where `a` and `b` disagree — which splits the whole list into two
        groups, each holding exactly one of the answers.
        """,
        "two_singles", "nums", _two_singles,
        """
        def two_singles(nums):
            mixed = 0
            for value in nums:
                mixed ^= value          # everything paired cancels: mixed == a ^ b

            lowest = mixed & -mixed     # one bit where a and b differ
            a = b = 0
            for value in nums:
                if value & lowest:
                    a ^= value          # the group with that bit set
                else:
                    b ^= value          # and the group without it
            return sorted([a, b])
        """,
        [("classic", [[1, 2, 1, 3, 2, 5]]), ("just the two", [[4, 9]])],
        [("zero is one of them", [[0, 7, 7, 4]]),
         ("adjacent values", [[6, 7, 1, 1]]),
         ("longer", [[10, 3, 10, 8, 2, 2]]),
         ("large values", [[1024, 5, 5, 2048]])],
        edges=[("two zeros cannot happen, so one is zero", [[0, 1]]),
               ("all pairs but two at the ends", [[9, 2, 2, 3, 3, 1]])],
        pattern="SIMULATION", family="bits", realm="fields_of_syntax",
        secondary=["ARRAY"], time="O(n)", space="O(1)",
        after="so-bit-missing-number",
        starter_hint="XOR everything, isolate one differing bit, then partition",
        nudge="`x & -x` isolates the lowest set bit. Two-s complement is why: "
              "`-x` is `~x + 1`, which flips everything above that bit.",
        pseudocode="mixed = XOR of all\nlowest = mixed & -mixed\n"
                   "XOR each group separately",
        failures=["Picking a bit that is 0 in `mixed`, which puts both answers "
                  "in the same group",
                  "Returning the pair in whatever order it fell out"],
        tags=["bits", "hard-trick"],
    ))

    P.append(sp(
        "so-bit-gray-code", "The Sequence That Changes One Bit", "MEDIUM",
        """
        Return the `n`-bit Gray code sequence: all 2^n integers, starting at 0,
        where consecutive entries differ in exactly one bit (and the last and
        first differ in one bit too). `n` is at most 10; `n <= 0` gives `[0]`.

        There is a closed form, and it is one line.
        """,
        "gray_code", "n", _gray_code,
        """
        def gray_code(n):
            if n <= 0:
                return [0]
            # i ^ (i >> 1) maps the counting order onto the reflected order
            return [i ^ (i >> 1) for i in range(1 << n)]
        """,
        [("two bits", [2]), ("three bits", [3])],
        [("one bit", [1]), ("four bits", [4]), ("five bits", [5]),
         ("ten bits", [10])],
        edges=[("zero bits", [0]), ("negative", [-1])],
        pattern="SIMULATION", family="bits", realm="fields_of_syntax",
        time="O(2^n)", space="O(2^n)", after="so-bit-two-singles",
        starter_hint="build it by reflection, or find the closed form",
        nudge="The reflected construction: take the sequence for n-1, then "
              "append it reversed with the new high bit set. Then notice what "
              "that does to each index.",
        pseudocode="for i in 0..2^n - 1: yield i ^ (i >> 1)",
        failures=["Returning the plain counting order, where 1 -> 2 flips two bits",
                  "Using `1 << n` with a negative `n`, which raises ValueError"],
        tags=["bits"],
    ))

    # -- math ----------------------------------------------------------------

    P.append(sp(
        "so-math-fizzbuzz", "Fizz, Buzz, And The Order Of Tests", "GUIDED",
        """
        Return the FizzBuzz list for 1..`n`: "Fizz" for multiples of 3, "Buzz"
        for multiples of 5, "FizzBuzz" for multiples of both, and the number as
        a string otherwise.

        The only thing this question really tests is whether you check the
        both-case first. The second half of that check is missing.
        """,
        "fizzbuzz", "n", _fizzbuzz,
        """
        def fizzbuzz(n):
            out = []
            for i in range(1, n + 1):
                if i % 3 == 0 and i % 5 == 0:   # both, and this must come first
                    out.append("FizzBuzz")
                elif i % 3 == 0:
                    out.append("Fizz")
                elif i % 5 == 0:
                    out.append("Buzz")
                else:
                    out.append(str(i))
            return out
        """,
        [("to fifteen", [15]), ("to five", [5])],
        [("to three", [3]), ("to one", [1]), ("to thirty", [30])],
        edges=[("zero", [0]), ("negative", [-3])],
        pattern="SIMULATION", family="math", realm="python_village",
        secondary=["STRING"], time="O(n)", space="O(n)",
        starter="""
        def fizzbuzz(n):
            out = []
            for i in range(1, n + 1):
                if i % 3 == 0 and __BLANK__:    # divisible by five as well
                    out.append("FizzBuzz")
                elif i % 3 == 0:
                    out.append("Fizz")
                elif i % 5 == 0:
                    out.append("Buzz")
                else:
                    out.append(str(i))
            return out
        """,
        nudge="`i % 5 == 0` is 'five divides i'. The branch above needs both "
              "divisibility tests to hold.",
        pseudocode="if divisible by 3 and 5: FizzBuzz\nelif by 3: Fizz\n"
                   "elif by 5: Buzz\nelse: the number",
        fragment=_same_move("if year % 4 == 0 and year % 100 != 0:"),
        failures=["Checking `% 3` first and `% 5` second without the combined "
                  "case, which prints Fizz for 15"],
        tags=["math", "classic"],
    ))

    P.append(sp(
        "so-math-gcd", "Euclid's Loop", "GUIDED",
        """
        Return the greatest common divisor of `a` and `b`, as a non-negative
        integer. `gcd(0, 0)` is 0.

        Euclid's insight: any divisor of `a` and `b` also divides `a % b`, so
        replacing the pair with `(b, a % b)` keeps the answer and shrinks the
        numbers. Repeat until one of them is 0. The replacement is missing.
        """,
        "gcd", "a, b", _gcd,
        """
        def gcd(a, b):
            a, b = abs(a), abs(b)
            while b:
                a, b = b, a % b     # the pair shrinks, the gcd does not change
            return a
        """,
        [("twelve and eighteen", [12, 18]), ("coprime", [7, 5])],
        [("one divides the other", [4, 12]), ("equal", [9, 9]),
         ("with zero", [0, 6]), ("negative", [-8, 12])],
        edges=[("both zero", [0, 0]), ("one", [1, 97])],
        pattern="SIMULATION", family="math", realm="python_village",
        time="O(log min(a, b))", space="O(1)",
        after="so-math-fizzbuzz",
        starter="""
        def gcd(a, b):
            a, b = abs(a), abs(b)
            while b:
                a, b = b, __BLANK__     # the remainder takes b's place
            return a
        """,
        nudge="The new pair is (the old b, the remainder of a divided by b). "
              "Python assigns the whole right-hand side before rebinding, so "
              "the swap is safe on one line.",
        pseudocode="while b: a, b = b, a mod b\nreturn a",
        fragment=_same_move("current, previous = previous, current + previous"),
        failures=["Writing two separate assignments, where the first overwrites "
                  "the `a` the second still needs"],
        tags=["math", "classic"],
    ))

    P.append(sp(
        "so-math-midpoint", "The Midpoint That Does Not Overflow", "GUIDED",
        """
        Return the midpoint of `lo` and `hi`, rounded down — the index a binary
        search would probe. Assume `lo <= hi`.

        `(lo + hi) // 2` is correct in Python, where integers do not overflow,
        and is a real bug in C, Java and Go, where `lo + hi` can wrap past the
        maximum integer. The form that never overflows adds only the *distance*
        to `lo`. That distance is missing.
        """,
        "safe_midpoint", "lo, hi", _safe_midpoint,
        """
        def safe_midpoint(lo, hi):
            # never forms lo + hi, so it cannot overflow a fixed-width integer
            return lo + (hi - lo) // 2
        """,
        [("small range", [0, 10]), ("adjacent", [3, 4])],
        [("equal", [5, 5]), ("negatives", [-10, -2]),
         ("crossing zero", [-3, 3]), ("huge", [2 ** 62, 2 ** 62 + 8])],
        edges=[("zero to one", [0, 1]), ("both zero", [0, 0])],
        pattern="SIMULATION", family="math", realm="python_village",
        secondary=["BINARY_SEARCH"], time="O(1)", space="O(1)",
        after="so-math-gcd",
        starter="""
        def safe_midpoint(lo, hi):
            return lo + __BLANK__       # half the distance between them
        """,
        nudge="Half the gap, floored, added to the lower end. `hi - lo` can "
              "never overflow when both are valid indices.",
        pseudocode="lo + (hi - lo) // 2",
        fragment=_same_move("probe = left + (right - left) // 2"),
        failures=["Writing `(lo + hi) // 2` and calling it done — correct in "
                  "Python, and the interviewer is asking about the other case"],
        tags=["math", "binary-search"],
    ))

    P.append(sp(
        "so-math-lcm", "The Smallest Shared Multiple", "TUTORIAL",
        """
        Return the least common multiple of `a` and `b`, as a non-negative
        integer. If either is 0, return 0.

        The identity to remember: `a * b == gcd(a, b) * lcm(a, b)`.
        """,
        "lcm", "a, b", _lcm,
        """
        def lcm(a, b):
            if a == 0 or b == 0:
                return 0
            a, b = abs(a), abs(b)
            first, second = a, b
            while second:
                first, second = second, first % second   # gcd, inline
            return a * b // first       # divide first in a fixed-width language
        """,
        [("four and six", [4, 6]), ("coprime", [3, 5])],
        [("one divides the other", [4, 12]), ("equal", [7, 7]),
         ("negative", [-4, 6]), ("with one", [1, 13])],
        edges=[("zero", [0, 5]), ("both zero", [0, 0])],
        pattern="SIMULATION", family="math", realm="python_village",
        time="O(log min(a, b))", space="O(1)", after="so-math-midpoint",
        starter_hint="reuse Euclid, then divide before multiplying where you can",
        nudge="Dividing by the gcd first keeps the intermediate value small, "
              "which matters everywhere except Python.",
        pseudocode="if either is 0: 0\nelse a * b // gcd(a, b)",
        failures=["Returning `a * b` for coprime inputs and assuming that is the "
                  "lcm in general — it is only true when the gcd is 1",
                  "Dividing by zero when an argument is 0"],
        tags=["math"],
    ))

    P.append(sp(
        "so-math-is-prime", "Testing For Primality", "TUTORIAL",
        """
        Return True if `n` is prime. 0, 1 and every negative number are not.

        You only need to test divisors up to the square root: if `n == p * q`
        and both exceeded the square root, their product would exceed `n`.
        """,
        "is_prime", "n", _is_prime,
        """
        def is_prime(n):
            if n < 2:
                return False
            factor = 2
            while factor * factor <= n:     # no float sqrt, no rounding question
                if n % factor == 0:
                    return False
                factor += 1
            return True
        """,
        [("seven", [7]), ("nine", [9])],
        [("two", [2]), ("large prime", [7919]), ("even", [100]),
         ("square of a prime", [49])],
        edges=[("zero", [0]), ("one", [1]), ("negative", [-7])],
        pattern="SIMULATION", family="math", realm="python_village",
        time="O(sqrt(n))", space="O(1)", after="so-math-lcm",
        starter_hint="loop while factor * factor <= n",
        nudge="`factor * factor <= n` avoids `int(n ** 0.5)` and the question of "
              "whether floating point rounded the boundary the wrong way.",
        pseudocode="if n < 2: False\nfor factor while factor^2 <= n: if it divides, False",
        failures=["Looping to `n`, which is correct and needlessly quadratic-ish",
                  "Calling 1 prime, or forgetting 2 is"],
        tags=["math"],
    ))

    P.append(sp(
        "so-math-digit-sum", "Adding Up The Digits", "TUTORIAL",
        """
        Return the sum of the decimal digits of `n`. The sign is ignored, so
        `digit_sum(-123)` is 6.

        Converting to a string works. Doing it with arithmetic is the version
        that teaches you `divmod`, which you will use in every base-conversion
        question there is.
        """,
        "digit_sum", "n", _digit_sum,
        """
        def digit_sum(n):
            n = abs(n)
            total = 0
            while n:
                n, digit = divmod(n, 10)    # peel the last digit off
                total += digit
            return total
        """,
        [("three digits", [123]), ("negative", [-45])],
        [("single digit", [7]), ("with zeros", [1002]),
         ("all nines", [999]), ("large", [987654321])],
        edges=[("zero", [0]), ("ten", [10])],
        pattern="SIMULATION", family="math", realm="python_village",
        time="O(log n)", space="O(1)", after="so-math-is-prime",
        starter_hint="divmod by 10 until nothing is left",
        nudge="`divmod(n, 10)` hands back everything except the last digit, and "
              "the last digit, in one call.",
        pseudocode="while n: n, digit = divmod(n, 10); total += digit",
        failures=["Looping `while n > 0` on a negative number, which returns 0",
                  "Forgetting that `-123 % 10` is 7 in Python, not -3"],
        tags=["math"],
    ))

    P.append(sp(
        "so-math-sieve", "The Sieve Of Eratosthenes", "EASY",
        """
        Return every prime strictly below `n`, ascending. `n <= 2` yields an
        empty list.

        Testing each number on its own costs O(n sqrt n). The sieve crosses out
        multiples instead and costs about O(n log log n) — and the inner loop
        can start at `p * p`, because everything smaller was already crossed out
        by a smaller prime.
        """,
        "primes_below", "n", _primes_below,
        """
        def primes_below(n):
            if n <= 2:
                return []
            prime = [True] * n
            prime[0] = prime[1] = False
            p = 2
            while p * p < n:
                if prime[p]:
                    for multiple in range(p * p, n, p):  # p*2 .. p*(p-1) are done
                        prime[multiple] = False
                p += 1
            return [value for value, ok in enumerate(prime) if ok]
        """,
        [("below twenty", [20]), ("below ten", [10])],
        [("below three", [3]), ("below fifty", [50]), ("below two", [2]),
         ("below one hundred", [100])],
        edges=[("zero", [0]), ("one", [1]), ("negative", [-5])],
        perf=[("below twenty thousand", [20000])],
        pattern="ARRAY", family="math", realm="fields_of_syntax",
        time="O(n log log n)", space="O(n)", after="so-math-digit-sum",
        starter_hint="a list of booleans, then cross out multiples",
        nudge="Start the inner loop at `p * p`. Every smaller multiple of `p` "
              "has a smaller prime factor and was crossed out already.",
        pseudocode="prime = [True] * n; prime[0] = prime[1] = False\n"
                   "for p while p*p < n: if prime[p]: cross out p*p, p*p+p, ...",
        failures=["Starting the inner loop at `2 * p`, which is correct and does "
                  "redundant work",
                  "Returning primes up to and including n when `below` was asked"],
        tags=["math", "classic"],
    ))

    P.append(sp(
        "so-math-to-base", "Writing A Number In Another Base", "EASY",
        """
        Return `n` written in `base`, using digits 0-9 then a-z, as a string.
        Negative numbers keep a leading "-", and 0 is "0". A base outside 2..36
        returns the empty string.
        """,
        "to_base", "n, base", _to_base,
        """
        def to_base(n, base):
            if base < 2 or base > 36:
                return ""
            if n == 0:
                return "0"
            digits = "0123456789abcdefghijklmnopqrstuvwxyz"
            sign = "-" if n < 0 else ""
            n = abs(n)
            out = []
            while n:
                n, rest = divmod(n, base)
                out.append(digits[rest])    # digits come out backwards
            return sign + "".join(reversed(out))
        """,
        [("binary", [10, 2]), ("hex", [255, 16])],
        [("base eight", [64, 8]), ("base thirty six", [35, 36]),
         ("negative", [-10, 2]), ("base ten is identity", [1234, 10])],
        edges=[("zero", [0, 2]), ("base too small", [5, 1]),
               ("base too large", [5, 37]), ("one", [1, 2])],
        pattern="SIMULATION", family="math", realm="fields_of_syntax",
        secondary=["STRING"], time="O(log n)", space="O(log n)",
        after="so-math-sieve",
        starter_hint="divmod down, then reverse what you collected",
        nudge="The digits fall out least significant first, so either reverse at "
              "the end or build the string by prepending.",
        pseudocode="while n: n, rest = divmod(n, base); collect digits[rest]\nreverse",
        failures=["Forgetting the `n == 0` case, which returns an empty string",
                  "Losing the sign, or taking divmod of a negative number"],
        tags=["math", "strings"],
    ))

    P.append(sp(
        "so-math-truncate", "The Division That Rounds The Other Way", "EASY",
        """
        Return `a` divided by `b`, truncated *toward zero* — the way C, Java and
        most CPUs do it. Return None when `b` is 0.

        Python's `//` floors instead: `-7 // 2` is -4, while a C programmer
        expects -3. This difference is a real source of off-by-one bugs when
        porting code or reasoning about an interview question written in another
        language.
        """,
        "truncated_divide", "a, b", _truncated_divide,
        """
        def truncated_divide(a, b):
            if b == 0:
                return None
            result = a // b
            # floor and truncate agree unless the result is negative and inexact
            if result < 0 and result * b != a:
                result += 1
            return result
        """,
        [("negative numerator", [-7, 2]), ("positive", [7, 2])],
        [("negative denominator", [7, -2]), ("both negative", [-7, -2]),
         ("exact negative", [-8, 2]), ("zero numerator", [0, 5])],
        edges=[("divide by zero", [5, 0]), ("one", [-1, 2]),
               ("large", [-10 ** 15 + 1, 3])],
        pattern="SIMULATION", family="math", realm="fields_of_syntax",
        time="O(1)", space="O(1)", after="so-math-to-base",
        starter_hint="floor, then correct the negative inexact case by one",
        nudge="`int(a / b)` truncates, and quietly loses precision above 2^53. "
              "Fix the integer result instead of going through a float.",
        pseudocode="q = a // b\nif q < 0 and q * b != a: q += 1",
        failures=["Using `int(a / b)`, which is wrong for large integers",
                  "Correcting every negative result, including the exact ones"],
        tags=["math", "traps"],
    ))

    P.append(sp(
        "so-math-count-primes", "How Many Primes Below n", "MEDIUM",
        """
        Return how many primes are strictly below `n`. `n` can be large enough
        that testing each number separately will time out.
        """,
        "count_primes", "n", _count_primes,
        """
        def count_primes(n):
            if n <= 2:
                return 0
            prime = bytearray([1]) * n
            prime[0] = prime[1] = 0
            p = 2
            while p * p < n:
                if prime[p]:
                    # slice assignment crosses out the whole arithmetic run at once
                    prime[p * p::p] = bytearray(len(range(p * p, n, p)))
                p += 1
            return sum(prime)
        """,
        [("below ten", [10]), ("below thirty", [30])],
        [("below two", [2]), ("below three", [3]), ("below one thousand", [1000]),
         ("below ten thousand", [10000])],
        edges=[("zero", [0]), ("one", [1]), ("negative", [-4])],
        perf=[("below two hundred thousand", [200000])],
        pattern="ARRAY", family="math", realm="fields_of_syntax",
        time="O(n log log n)", space="O(n)", after="so-math-truncate",
        starter_hint="sieve, then count what survived",
        nudge="A `bytearray` and a slice assignment cross out a whole run in one "
              "operation instead of one Python loop iteration per multiple.",
        pseudocode="sieve up to n, then sum the surviving flags",
        failures=["Calling an is_prime helper n times, which is the timeout",
                  "Counting primes up to n inclusive"],
        tags=["math", "performance"],
    ))

    P.append(sp(
        "so-math-trailing-zeros", "Zeros At The End Of A Factorial", "MEDIUM",
        """
        Return how many zeros `n!` ends with, without computing `n!`. `n` is at
        least 0.

        A trailing zero is a factor of 10, which is a 2 and a 5. Twos are far
        more common than fives, so the answer is simply how many factors of 5
        appear across 1..`n` — counting 25 twice, 125 three times, and so on.
        """,
        "trailing_zeros", "n", _trailing_zeros,
        """
        def trailing_zeros(n):
            count = 0
            while n:
                n //= 5             # n//5 multiples of 5, then n//25, then n//125
                count += n
            return count
        """,
        [("five", [5]), ("twenty five", [25])],
        [("four", [4]), ("ten", [10]), ("one hundred", [100]),
         ("one hundred and twenty five", [125])],
        edges=[("zero", [0]), ("one", [1]), ("large", [1000000])],
        pattern="SIMULATION", family="math", realm="fields_of_syntax",
        time="O(log n)", space="O(1)", after="so-math-count-primes",
        starter_hint="count factors of five, including the repeated ones",
        nudge="25 contributes two fives, not one. Dividing repeatedly counts "
              "each contribution exactly once.",
        pseudocode="while n: n //= 5; count += n",
        failures=["Returning `n // 5`, which is right until 25",
                  "Actually computing the factorial, which is enormous and slow"],
        tags=["math"],
    ))

    P.append(sp(
        "so-math-power-mod", "Exponentiation By Squaring", "MEDIUM",
        """
        Return `(base ** exponent) % mod` with a non-negative `exponent` and a
        `mod` of at least 1, without ever building the full power.

        Squaring halves the exponent each step, so the loop runs about log2
        times instead of `exponent` times. This is the core of RSA and of every
        modular-arithmetic question you will ever be asked.
        """,
        "power_mod", "base, exponent, mod", _power_mod,
        """
        def power_mod(base, exponent, mod):
            result = 1
            base %= mod
            while exponent:
                if exponent & 1:            # this bit of the exponent is set
                    result = result * base % mod
                base = base * base % mod    # square for the next bit up
                exponent >>= 1
            return result
        """,
        [("small", [2, 10, 1000]), ("wraps", [3, 5, 7])],
        [("exponent zero", [5, 0, 13]), ("base zero", [0, 5, 7]),
         ("large exponent", [7, 1000, 1000000007]),
         ("mod one", [9, 9, 1])],
        edges=[("base one", [1, 10 ** 6, 97]), ("base equals mod", [7, 3, 7]),
               ("huge", [123456789, 987654321, 1000000007])],
        pattern="SIMULATION", family="math", realm="fields_of_syntax",
        secondary=["RECURSION"], time="O(log exponent)", space="O(1)",
        after="so-math-trailing-zeros",
        starter_hint="walk the exponent's bits; square the base each step",
        nudge="Take the modulus after every multiply, not at the end. The whole "
              "point is that no intermediate value ever grows.",
        pseudocode="while exponent: if exponent is odd: result = result*base % mod\n"
                   "base = base*base % mod; exponent >>= 1",
        failures=["Computing `base ** exponent` first, which is astronomically large",
                  "Forgetting `base %= mod` before the loop"],
        tags=["math", "bits"],
    ))

    P.append(sp(
        "so-math-reverse-int", "Reversing A Number That Might Not Fit", "MEDIUM",
        """
        Return the digits of `n` reversed, keeping the sign: 123 becomes 321 and
        -120 becomes -21. If the reversed value falls outside the signed 32-bit
        range (-2^31 to 2^31 - 1), return 0 instead.

        Python integers never overflow, so the range check is something you have
        to write on purpose. That is the whole question.
        """,
        "reverse_int", "n", _reverse_int,
        """
        def reverse_int(n):
            sign = -1 if n < 0 else 1
            n = abs(n)
            out = 0
            while n:
                n, digit = divmod(n, 10)
                out = out * 10 + digit
            out *= sign
            if out < -(2 ** 31) or out > 2 ** 31 - 1:
                return 0                    # the check no other language gives you free
            return out
        """,
        [("plain", [123]), ("trailing zero", [-120])],
        [("single digit", [7]), ("palindrome", [1221]),
         ("overflows", [1534236469]), ("negative overflow", [-2147483648])],
        edges=[("zero", [0]), ("ten", [10]),
               ("largest that fits", [1463847412])],
        pattern="SIMULATION", family="math", realm="fields_of_syntax",
        time="O(log n)", space="O(1)", after="so-math-power-mod",
        starter_hint="peel digits with divmod, then range-check before returning",
        nudge="Trailing zeros disappear on their own: 120 reversed is 21, not "
              "'021'. The arithmetic handles that for free.",
        pseudocode="while n: n, digit = divmod(n, 10); out = out * 10 + digit\n"
                   "apply the sign, then bounds-check",
        failures=["Reversing the string form and forgetting the minus sign",
                  "Skipping the 32-bit check because Python did not complain"],
        tags=["math", "traps"],
    ))

    # -- intervals -----------------------------------------------------------
    # Half-open everywhere: [start, end) holds `start` and releases at `end`.
    # Saying which convention you are using, out loud, before writing the first
    # comparison, is most of what separates a clean interval answer from a
    # twenty-minute argument about whether [1,4] and [4,5] collide.

    P.append(sp(
        "so-int-overlaps", "Do These Two Collide", "GUIDED",
        """
        Each interval is `[start, end)` — it includes `start` and excludes
        `end`. Return True if `a` and `b` share any time at all. `[1, 4]` and
        `[4, 5]` do not: the first one is over the moment the second begins.

        Two intervals overlap exactly when the later of the two starts comes
        before the earlier of the two ends. Half of that is missing.
        """,
        "overlaps", "a, b", _overlaps,
        """
        def overlaps(a, b):
            # the intersection is [max of the starts, min of the ends)
            return max(a[0], b[0]) < min(a[1], b[1])
        """,
        [("overlapping", [[1, 5], [4, 8]]), ("touching", [[1, 4], [4, 5]])],
        [("disjoint", [[1, 2], [5, 6]]), ("contained", [[1, 10], [3, 4]]),
         ("identical", [[2, 6], [2, 6]]), ("reversed order", [[4, 8], [1, 5]])],
        edges=[("zero length", [[3, 3], [1, 5]]), ("both zero length", [[3, 3], [3, 3]])],
        pattern="INTERVALS", family="intervals", realm="stack_queue_mines",
        time="O(1)", space="O(1)",
        starter="""
        def overlaps(a, b):
            return max(a[0], b[0]) < __BLANK__   # the earlier of the two ends
        """,
        nudge="If the intersection has positive length, they overlap. The "
              "intersection starts at the later start and ends at the earlier end.",
        pseudocode="max(starts) < min(ends)",
        fragment=_same_move("shared = max(a_low, b_low) < min(a_high, b_high)"),
        failures=["Using `<=`, which reports a collision for meetings that merely "
                  "touch",
                  "Writing four separate cases, three of which are the same case"],
        tags=["intervals"],
    ))

    P.append(sp(
        "so-int-attend-all", "Can One Room Hold Them All", "TUTORIAL",
        """
        Each meeting is `[start, end)`. Return True if none of them collide, so
        a single room can host every one. Meetings that merely touch are fine.

        Unsorted, every pair has to be compared. Sorted by start, only
        neighbours can possibly collide, which turns O(n^2) into O(n log n).
        """,
        "can_attend_all", "meetings", _can_attend_all,
        """
        def can_attend_all(meetings):
            free_at = None
            for start, end in sorted(meetings):
                if free_at is not None and start < free_at:
                    return False        # this one begins before the last ended
                free_at = end
            return True
        """,
        [("clear", [[[1, 2], [3, 4]]]), ("collision", [[[1, 5], [4, 8]]])],
        [("touching is fine", [[[1, 4], [4, 5]]]),
         ("unsorted input", [[[5, 6], [1, 2]]]),
         ("nested", [[[1, 10], [2, 3]]]),
         ("identical", [[[1, 2], [1, 2]]])],
        edges=[("empty", [[]]), ("single", [[[1, 9]]])],
        pattern="INTERVALS", family="intervals", realm="stack_queue_mines",
        secondary=["SORTING"], time="O(n log n)", space="O(1)",
        after="so-int-overlaps",
        starter_hint="sort by start, then compare each with the one before it",
        nudge="After sorting, the only question per meeting is whether it starts "
              "before the previous one ended.",
        pseudocode="sort by start\nfor each: if start < previous end: False",
        failures=["Comparing every pair, which is correct and O(n^2)",
                  "Forgetting to sort, which reports a clash for [[3,4],[1,2]]"],
        tags=["intervals", "sorting"],
    ))

    P.append(sp(
        "so-int-union-two", "Joining Two Wards", "TUTORIAL",
        """
        Return the union of intervals `a` and `b` as a list, sorted by start:
        one interval if they overlap or touch, otherwise both, unchanged.

        Touching counts as joinable here even though it does not count as
        colliding — `[1, 4)` and `[4, 7)` together cover exactly `[1, 7)` with
        no gap. Knowing why those two rules differ is the point of this one.
        """,
        "union_two", "a, b", _union_two,
        """
        def union_two(a, b):
            if max(a[0], b[0]) <= min(a[1], b[1]):      # overlap or touch
                return [[min(a[0], b[0]), max(a[1], b[1])]]
            return sorted([list(a), list(b)])
        """,
        [("overlapping", [[1, 5], [4, 8]]), ("disjoint", [[1, 3], [5, 7]])],
        [("touching", [[1, 4], [4, 7]]), ("contained", [[1, 10], [3, 4]]),
         ("reversed order", [[5, 7], [1, 3]]), ("identical", [[2, 4], [2, 4]])],
        edges=[("zero length inside", [[1, 5], [3, 3]]),
               ("zero length outside", [[1, 5], [9, 9]])],
        pattern="INTERVALS", family="intervals", realm="stack_queue_mines",
        time="O(1)", space="O(1)", after="so-int-attend-all",
        starter_hint="one comparison decides which of the two shapes you return",
        nudge="The merged interval spans the earliest start to the latest end. "
              "Note that is `max` of the ends, not the end of whichever started "
              "later — containment would break that.",
        pseudocode="if they touch or overlap: [min start, max end]\nelse both, sorted",
        failures=["Using the second interval's end, which drops the tail of a "
                  "fully contained pair",
                  "Assuming `a` starts first"],
        tags=["intervals"],
    ))

    P.append(sp(
        "so-int-merge", "The Overlapping Wards", "EASY",
        """
        Merge every overlapping or touching interval in `intervals` and return
        the result sorted by start. Intervals arrive in any order.

        Sort by start, then keep one interval open: each new one either extends
        it or begins a new one. That is the whole algorithm, and it is the
        skeleton of most interval questions.
        """,
        "merge_ranges", "intervals", _merge_ranges,
        """
        def merge_ranges(intervals):
            out = []
            for start, end in sorted(intervals):
                if out and start <= out[-1][1]:
                    # extends the open interval; `max` matters for nested input
                    out[-1][1] = max(out[-1][1], end)
                else:
                    out.append([start, end])
            return out
        """,
        [("classic", [[[1, 3], [2, 6], [8, 10]]]), ("touching", [[[1, 4], [4, 5]]])],
        [("unsorted", [[[5, 6], [1, 3], [2, 4]]]),
         ("fully contained", [[[1, 10], [2, 3], [4, 5]]]),
         ("no overlap", [[[1, 2], [3, 4]]]),
         ("all one", [[[1, 2], [2, 3], [3, 4]]])],
        edges=[("empty", [[]]), ("single", [[[1, 2]]]),
               ("identical", [[[1, 2], [1, 2]]])],
        pattern="INTERVALS", family="intervals", realm="stack_queue_mines",
        secondary=["SORTING"], time="O(n log n)", space="O(n)",
        after="so-int-union-two",
        starter_hint="sort by start; extend the last interval or start a new one",
        nudge="`max(out[-1][1], end)` and not just `end`: a short interval "
              "entirely inside a long one must not shorten it.",
        pseudocode="for start, end in sorted(intervals):\n"
                   "  if it touches the open interval: extend it\n  else: open a new one",
        failures=["Assigning `out[-1][1] = end` without `max`, which loses the "
                  "tail on nested input",
                  "Sorting by end, which breaks the one-open-interval invariant"],
        tags=["intervals", "classic"],
    ))

    P.append(sp(
        "so-int-insert", "Slotting One In", "EASY",
        """
        `intervals` is already sorted by start and has no overlaps. Insert
        `new`, merging anything it touches, and return the result sorted by
        start.

        Concatenating and re-merging is legitimate and costs O(n log n). The
        three-phase scan below does it in one linear pass, which is the answer
        the question is looking for.
        """,
        "insert_range", "intervals, new", _insert_range,
        """
        def insert_range(intervals, new):
            out = []
            start, end = new[0], new[1]
            i = 0
            # phase 1: everything that finishes before the new one begins
            while i < len(intervals) and intervals[i][1] < start:
                out.append(list(intervals[i]))
                i += 1
            # phase 2: everything that touches it gets absorbed
            while i < len(intervals) and intervals[i][0] <= end:
                start = min(start, intervals[i][0])
                end = max(end, intervals[i][1])
                i += 1
            out.append([start, end])
            # phase 3: the untouched tail
            while i < len(intervals):
                out.append(list(intervals[i]))
                i += 1
            return out
        """,
        [("merges two", [[[1, 3], [6, 9]], [2, 5]]),
         ("no overlap", [[[1, 2], [6, 9]], [3, 4]])],
        [("before everything", [[[3, 5]], [1, 2]]),
         ("after everything", [[[1, 2]], [6, 8]]),
         ("swallows all", [[[2, 3], [5, 7]], [1, 9]]),
         ("touching at both ends", [[[1, 3], [5, 7]], [3, 5]])],
        edges=[("empty list", [[], [2, 4]]),
               ("zero length insert", [[[1, 5]], [3, 3]])],
        pattern="INTERVALS", family="intervals", realm="stack_queue_mines",
        time="O(n)", space="O(n)", after="so-int-merge",
        starter_hint="three loops: before, overlapping, after",
        nudge="Phase two grows the new interval rather than emitting anything. "
              "It emits once, after the loop.",
        pseudocode="copy while end < new start\nabsorb while start <= new end\n"
                   "emit the grown interval\ncopy the rest",
        failures=["Emitting inside the absorb loop, which produces duplicates",
                  "Using `<` instead of `<=` when absorbing, which leaves "
                  "touching intervals unjoined"],
        tags=["intervals"],
    ))

    P.append(sp(
        "so-int-min-removals", "The Fewest Cancellations", "MEDIUM",
        """
        Return the minimum number of intervals to remove so that none of the
        survivors overlap. Touching is allowed.

        Removing the fewest is the same as keeping the most, which is the
        meetings-in-one-room problem wearing a different hat. Recognising that
        is the whole question; the code is six lines.
        """,
        "min_removals", "intervals", _min_removals,
        """
        def min_removals(intervals):
            kept, free_at = 0, None
            for start, end in sorted(intervals, key=lambda iv: iv[1]):
                if free_at is None or start >= free_at:
                    kept += 1           # greedy: always keep the earliest finisher
                    free_at = end
            return len(intervals) - kept
        """,
        [("one to go", [[[1, 2], [2, 3], [3, 4], [1, 3]]]),
         ("all overlap", [[[1, 9], [2, 9], [3, 9]]])],
        [("none to go", [[[1, 2], [3, 4]]]),
         ("identical", [[[1, 2], [1, 2], [1, 2]]]),
         ("nested", [[[1, 10], [2, 3], [4, 5]]]),
         ("unsorted", [[[5, 9], [1, 3], [2, 6]]])],
        edges=[("empty", [[]]), ("single", [[[4, 7]]])],
        pattern="GREEDY", family="intervals", realm="stack_queue_mines",
        secondary=["INTERVALS", "SORTING"], time="O(n log n)", space="O(1)",
        after="so-int-insert",
        starter_hint="count how many you can keep; subtract from the total",
        nudge="Sort by end. The interval that finishes first is always safe to "
              "keep: anything it conflicts with finishes no earlier, so keeping "
              "it can never cost you a later choice.",
        pseudocode="sort by end; keep any interval starting at or after the last "
                   "kept end; answer = n - kept",
        failures=["Sorting by start, which throws away short early intervals",
                  "Removing the longest interval first, which feels right and is "
                  "wrong on [[1,2],[2,3],[1,5]]"],
        tags=["intervals", "greedy", "classic"],
    ))

    P.append(sp(
        "so-int-rooms", "How Many Rooms Are Needed", "MEDIUM",
        """
        Each meeting is `[start, end)`. Return the smallest number of rooms that
        can host all of them. A meeting with no duration needs no room.

        The answer is the largest number of meetings in progress at any one
        instant. A heap of end times models exactly that: its size is how many
        rooms are currently occupied.
        """,
        "min_rooms", "meetings", _min_rooms,
        """
        def min_rooms(meetings):
            import heapq
            rooms = []                  # end times of the rooms in use
            for start, end in sorted(meetings):
                if end <= start:
                    continue
                if rooms and rooms[0] <= start:
                    heapq.heapreplace(rooms, end)   # the earliest room is free
                else:
                    heapq.heappush(rooms, end)      # everyone is busy; open one
            return len(rooms)
        """,
        [("two rooms", [[[0, 30], [5, 10], [15, 20]]]),
         ("one room", [[[7, 10], [2, 4]]])],
        [("three deep", [[[1, 9], [2, 8], [3, 7]]]),
         ("touching needs one", [[[1, 2], [2, 3], [3, 4]]]),
         ("unsorted", [[[9, 12], [1, 4], [3, 5]]]),
         ("identical", [[[1, 5], [1, 5]]])],
        edges=[("empty", [[]]), ("single", [[[1, 2]]]),
               ("zero length", [[[3, 3], [3, 3]]])],
        pattern="HEAP", family="intervals", realm="stack_queue_mines",
        secondary=["INTERVALS", "GREEDY"], time="O(n log n)", space="O(n)",
        after="so-int-min-removals",
        starter_hint="a min-heap of end times; its size is the answer",
        nudge="You never need to know which room; only how many end times are "
              "still in the future. That is a heap of one number each.",
        pseudocode="sort by start\nif the earliest end <= this start: reuse that room\n"
                   "else push a new one\nanswer = heap size",
        failures=["Reusing a room when `rooms[0] < start` is false but equal — "
                  "under half-open rules, ending exactly at the start is fine",
                  "Sorting starts and ends separately and then losing track of "
                  "which pairs belong together"],
        tags=["intervals", "heap", "classic"],
    ))

    P.append(sp(
        "so-int-free-slots", "What The Day Has Left", "MEDIUM",
        """
        `busy` is a list of `[start, end)` intervals in any order, possibly
        overlapping. Return the free intervals inside `[day_start, day_end)`,
        sorted by start. Busy time outside the day is ignored, and an empty or
        backwards day yields `[]`.

        Merge first, then walk the gaps. Trying to compute gaps from unmerged
        input is where this question eats people.
        """,
        "free_slots", "busy, day_start, day_end", _free_slots,
        """
        def free_slots(busy, day_start, day_end):
            if day_end <= day_start:
                return []
            merged = []
            for start, end in sorted(busy):
                start, end = max(start, day_start), min(end, day_end)
                if start >= end:
                    continue            # entirely outside the day
                if merged and start <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], end)
                else:
                    merged.append([start, end])

            out, cursor = [], day_start
            for start, end in merged:
                if start > cursor:
                    out.append([cursor, start])
                cursor = max(cursor, end)
            if cursor < day_end:
                out.append([cursor, day_end])
            return out
        """,
        [("two gaps", [[[1, 3], [5, 7]], 0, 10]),
         ("nothing booked", [[], 9, 17])],
        [("overlapping bookings", [[[1, 5], [2, 3], [4, 6]], 0, 8]),
         ("booked solid", [[[0, 10]], 0, 10]),
         ("busy outside the day", [[[20, 22]], 0, 10]),
         ("clipped at both ends", [[[0, 4], [8, 20]], 2, 12])],
        edges=[("backwards day", [[[1, 2]], 5, 5]),
               ("zero length booking", [[[3, 3]], 0, 6])],
        pattern="INTERVALS", family="intervals", realm="stack_queue_mines",
        secondary=["SORTING"], time="O(n log n)", space="O(n)",
        after="so-int-rooms",
        starter_hint="clip to the day, merge, then emit the space between",
        nudge="Carry a cursor at `day_start`. Each merged interval emits the gap "
              "behind it, then pushes the cursor forward.",
        pseudocode="clip and merge the busy list\ncursor = day_start\n"
                   "for each merged: emit [cursor, start) if non-empty; cursor = end\n"
                   "emit the tail",
        failures=["Forgetting the final gap after the last booking",
                  "Emitting zero-length gaps between touching bookings"],
        tags=["intervals", "sweep"],
    ))

    # -- sorting -------------------------------------------------------------
    # Almost nobody is asked to implement a sort. Everybody is asked to sort by
    # something awkward, and to know what `sorted` guarantees while doing it.

    P.append(sp(
        "so-sort-rank", "Highest Score, Then Alphabetical", "GUIDED",
        """
        Each record is `[name, score]`. Return the records ordered by score,
        highest first, breaking ties by name in alphabetical order.

        One `key` function does both: return a tuple, and Python compares the
        first element, then the second only when the first ties. Negating a
        number reverses that element alone — which is how you get descending on
        one field and ascending on another in a single pass.
        """,
        "rank_players", "records", _rank_players,
        """
        def rank_players(records):
            # -score sorts descending; name then breaks ties ascending
            return sorted(records, key=lambda record: (-record[1], record[0]))
        """,
        [("tie on score", [[["ada", 5], ["bo", 7], ["cy", 5]]]),
         ("no ties", [[["zed", 1], ["ann", 9]]])],
        [("all tied", [[["c", 2], ["a", 2], ["b", 2]]]),
         ("already ordered", [[["a", 9], ["b", 3]]]),
         ("negative scores", [[["a", -1], ["b", -5]]]),
         ("single", [[["solo", 4]]])],
        edges=[("empty", [[]]), ("same name different score",
                                 [[["a", 1], ["a", 3]]])],
        pattern="SORTING", family="sorting", realm="fields_of_syntax",
        time="O(n log n)", space="O(n)",
        starter="""
        def rank_players(records):
            return sorted(records, key=lambda record: (__BLANK__, record[0]))
        """,
        nudge="Score descending means the key should get *smaller* as the score "
              "gets bigger.",
        pseudocode="sorted(records, key=lambda r: (-r[1], r[0]))",
        fragment=_same_move("sorted(files, key=lambda f: (-f.size, f.name))"),
        failures=["Passing `reverse=True`, which also reverses the name tie-break",
                  "Sorting twice in the wrong order, so the second sort undoes "
                  "the first"],
        tags=["sorting", "keys"],
    ))

    P.append(sp(
        "so-sort-tally", "Counting Into Buckets", "GUIDED",
        """
        Every value in `values` is an integer between 0 and `top` inclusive.
        Return a list of length `top + 1` where entry `i` is how many times `i`
        appears.

        This is the first half of a counting sort, and the same move as any
        frequency table: use the value itself as the index. One line is missing.
        """,
        "tally_counts", "values, top", _tally_counts,
        """
        def tally_counts(values, top):
            counts = [0] * (top + 1)
            for value in values:
                counts[value] += 1      # the value IS the slot
            return counts
        """,
        [("small", [[1, 3, 1, 0], 3]), ("all same", [[2, 2, 2], 2])],
        [("with zeros", [[0, 0, 1], 1]), ("sparse", [[5], 5]),
         ("top unused", [[0, 1], 4])],
        edges=[("empty", [[], 3]), ("top is zero", [[0, 0], 0])],
        pattern="SORTING", family="sorting", realm="fields_of_syntax",
        secondary=["ARRAY"], time="O(n + top)", space="O(top)",
        after="so-sort-rank",
        starter="""
        def tally_counts(values, top):
            counts = [0] * (top + 1)
            for value in values:
                __BLANK__               # one more sighting of this value
            return counts
        """,
        nudge="No dict needed: the values are already small non-negative "
              "integers, so they can index the list directly.",
        pseudocode="counts = [0] * (top + 1)\nfor value: counts[value] += 1",
        fragment=_same_move("histogram[len(word)] += 1"),
        failures=["Allocating `[0] * top`, which is one slot short",
                  "Reusing the same inner list via `[[0]] * n`, where every row "
                  "is the same object"],
        tags=["sorting", "counting"],
    ))

    P.append(sp(
        "so-sort-counting", "Sorting Without Comparing", "TUTORIAL",
        """
        Every value in `nums` is an integer between 0 and `top` inclusive.
        Return them sorted ascending, without calling `sorted` or `.sort()`.

        Counting sort beats the O(n log n) comparison bound by not comparing
        anything: it counts, then rebuilds. That only works because the range of
        values is known and small — which is the trade you should say out loud.
        """,
        "counting_sort", "nums, top", _counting_sort,
        """
        def counting_sort(nums, top):
            counts = [0] * (top + 1)
            for value in nums:
                counts[value] += 1
            out = []
            for value, seen in enumerate(counts):
                out.extend([value] * seen)      # rebuild in index order
            return out
        """,
        [("small", [[3, 1, 2, 1], 3]), ("already sorted", [[0, 1, 2], 2])],
        [("all same", [[4, 4, 4], 4]), ("reversed", [[5, 4, 3], 5]),
         ("with zeros", [[0, 2, 0], 2]), ("wide range, few values", [[9, 0], 9])],
        edges=[("empty", [[], 5]), ("single", [[2], 2]), ("top is zero", [[0], 0])],
        pattern="SORTING", family="sorting", realm="fields_of_syntax",
        secondary=["ARRAY"], time="O(n + top)", space="O(n + top)",
        after="so-sort-tally",
        starter_hint="count, then rebuild by walking the counts in order",
        nudge="Nothing is ever compared to anything. That is why the O(n log n) "
              "lower bound does not apply.",
        pseudocode="count every value\nfor value in 0..top: emit it `counts[value]` times",
        failures=["Returning the counts instead of the values",
                  "Claiming it is O(n): it is O(n + top), and `top` can dwarf n"],
        tags=["sorting", "counting"],
    ))

    P.append(sp(
        "so-sort-stable", "What Stability Buys You", "TUTORIAL",
        """
        Each record is `[team, name]`. Return the records grouped by team, teams
        in alphabetical order, and — this is the point — with the records inside
        each team left in their original input order.

        Python's `sorted` is stable: records comparing equal on the key keep
        their relative order. So one `sorted` call with a key of just the team
        already does all of this.
        """,
        "group_stable", "records", _group_stable,
        """
        def group_stable(records):
            # sorting on the team alone leaves each team's members in input order
            return [list(record) for record in
                    sorted(records, key=lambda record: record[0])]
        """,
        [("two teams", [[["red", "ann"], ["blue", "bo"], ["red", "cy"]]]),
         ("one team", [[["red", "z"], ["red", "a"]]])],
        [("already grouped", [[["a", "x"], ["a", "y"], ["b", "z"]]]),
         ("reverse alphabetical teams", [[["z", "1"], ["a", "2"]]]),
         ("three teams", [[["c", "p"], ["a", "q"], ["b", "r"], ["a", "s"]]]),
         ("duplicate records", [[["a", "x"], ["a", "x"]]])],
        edges=[("empty", [[]]), ("single", [[["solo", "one"]]])],
        pattern="SORTING", family="sorting", realm="fields_of_syntax",
        time="O(n log n)", space="O(n)", after="so-sort-counting",
        starter_hint="one sorted() call, keyed on the team only",
        nudge="If you key on `(team, name)` you also sort the names, which the "
              "question did not ask for and which destroys the input order.",
        pseudocode="sorted(records, key=team)",
        failures=["Sorting on the whole record, which alphabetises the names too",
                  "Bucketing into a dict and hoping the iteration order is "
                  "alphabetical — insertion order is not sorted order"],
        tags=["sorting", "stability"],
    ))

    P.append(mcq_problem(
        id="so-sort-stability-mcq", title="Two Sorts, One Order",
        realm="fields_of_syntax", pattern="SORTING", difficulty="EASY",
        family="sorting",
        statement="""
        You want records ordered by department ascending, and within each
        department by salary descending. You decide to do it with two separate
        `sorted` calls instead of one tuple key.

        In which order must the two calls happen?
        """,
        code="""
        by_salary = sorted(people, key=lambda p: -p["salary"])
        by_dept = sorted(by_salary, key=lambda p: p["dept"])
        """,
        choices=[
            "Salary first, then department — the last sort must be the primary "
            "key, and stability preserves the earlier one inside ties",
            "Department first, then salary — the primary key should be sorted first",
            "Either order works, because sorting is stable",
            "Neither works; multi-key ordering always needs a tuple key",
        ],
        answer=0,
        explanation="""
        Sort by the *least* significant key first and the most significant key
        last. The final sort decides the overall order; stability is what keeps
        the previous sort's order intact inside each group of ties.

        Sorting by department first and salary second would scatter the
        departments, because the salary sort compares across the whole list.

        The tuple key `(p["dept"], -p["salary"])` does it in one pass and is
        what you should reach for. The two-pass version matters when a key
        cannot be expressed as a tuple — a custom comparison, or a key you can
        only compute for part of the data — and when you are reading someone
        else's code that does it this way.
        """,
        seconds=90,
    ))

    P.append(sp(
        "so-sort-length", "Shortest First, Then Alphabetical", "EASY",
        """
        Return `words` sorted by length, shortest first, with words of equal
        length in alphabetical order.
        """,
        "words_by_length", "words", _words_by_length,
        """
        def words_by_length(words):
            return sorted(words, key=lambda word: (len(word), word))
        """,
        [("mixed", [["pear", "fig", "apple", "kiwi"]]),
         ("same length", [["cb", "ca", "aa"]])],
        [("already sorted", [["a", "bb", "ccc"]]),
         ("reversed", [["ccc", "bb", "a"]]),
         ("duplicates", [["ab", "ab", "a"]]),
         ("empty string present", [["", "a"]])],
        edges=[("empty", [[]]), ("single", [["only"]])],
        pattern="SORTING", family="sorting", realm="fields_of_syntax",
        secondary=["STRING"], time="O(n log n)", space="O(n)",
        after="so-sort-stable",
        starter_hint="a tuple key: length first, the word itself second",
        nudge="Uppercase sorts before lowercase in ASCII, so mixed case is a "
              "question worth asking before you write the key.",
        pseudocode="sorted(words, key=lambda w: (len(w), w))",
        failures=["Sorting by length only and assuming ties come out alphabetical "
                  "— stability preserves input order, which is not the same thing"],
        tags=["sorting", "keys"],
    ))

    P.append(sp(
        "so-sort-versions", "Version Numbers Are Not Strings", "EASY",
        """
        Each version is a string of dot-separated integers, such as "1.10.2".
        Return them sorted ascending by numeric component: "1.9" comes before
        "1.10", and "1.2" comes before "1.2.1".

        Sorting the strings directly puts "1.10" before "1.9", because "1" is
        less than "9" as a character. This is the single most common real-world
        sort-key bug there is.
        """,
        "sort_versions", "versions", _sort_versions,
        """
        def sort_versions(versions):
            # tuples of ints compare element by element, and a shorter prefix
            # sorts first, which is exactly the versioning rule
            return sorted(versions,
                          key=lambda v: tuple(int(part) for part in v.split(".")))
        """,
        [("ten beats nine", [["1.10", "1.9", "1.2"]]),
         ("prefix", [["1.2.1", "1.2"]])],
        [("three components", [["2.0.0", "1.9.9", "2.0.1"]]),
         ("already sorted", [["0.1", "0.2"]]),
         ("duplicates", [["1.0", "1.0"]]),
         ("leading zeros", [["1.01", "1.1", "1.2"]])],
        edges=[("empty", [[]]), ("single", [["3.4.5"]]),
               ("single component", [["10", "9", "2"]])],
        pattern="SORTING", family="sorting", realm="fields_of_syntax",
        secondary=["STRING"], time="O(n log n * parts)", space="O(n)",
        after="so-sort-length",
        starter_hint="split on '.', convert to ints, let the tuple do the rest",
        nudge="Do not pad the strings to equal width. Convert to numbers — "
              "padding is a second bug waiting for a three-digit release.",
        pseudocode="sorted(versions, key=lambda v: tuple(map(int, v.split('.'))))",
        failures=["Sorting the raw strings",
                  "Using `float(v)` , which cannot hold '1.2.3' at all"],
        tags=["sorting", "keys", "real-world"],
    ))

    P.append(sp(
        "so-sort-top-k", "The k Most Common", "MEDIUM",
        """
        Return the `k` most frequent values in `items`, most frequent first,
        breaking ties in ascending value order. If `k` exceeds the number of
        distinct values, return all of them. `k` is at least 0.
        """,
        "top_k_frequent", "items, k", _top_k_frequent,
        """
        def top_k_frequent(items, k):
            import heapq
            counts = {}
            for item in items:
                counts[item] = counts.get(item, 0) + 1
            # nsmallest on (-count, value) is "largest count, then earliest value"
            best = heapq.nsmallest(k, counts.items(),
                                   key=lambda pair: (-pair[1], pair[0]))
            return [value for value, _ in best]
        """,
        [("clear winner", [["a", "b", "a", "c", "a", "b"], 2]),
         ("tie broken by value", [["b", "a"], 1])],
        [("all distinct", [["x", "y", "z"], 2]),
         ("k larger than distinct", [["a", "a"], 5]),
         ("all identical", [["q", "q", "q"], 1]),
         ("three way tie", [["c", "b", "a"], 3])],
        edges=[("k is zero", [["a"], 0]), ("empty items", [[], 2])],
        pattern="SORTING", family="sorting", realm="fields_of_syntax",
        secondary=["HASH_MAP", "HEAP"], time="O(n log k)", space="O(n)",
        after="so-sort-versions",
        starter_hint="count, then order by (-count, value)",
        nudge="Sorting everything is O(n log n) and perfectly acceptable. A heap "
              "of size k is O(n log k), which is the answer to 'can you do "
              "better' when k is small.",
        pseudocode="count into a dict\ntake the k smallest by (-count, value)",
        failures=["Ignoring the tie-break, which makes the output depend on dict "
                  "insertion order",
                  "Using `most_common(k)`, whose tie-break is insertion order, "
                  "not value order"],
        tags=["sorting", "heap", "classic"],
    ))

    # -- union-find ----------------------------------------------------------
    # The structure that answers "are these two in the same group" faster than
    # a traversal can, and keeps answering it as edges arrive.

    P.append(sp(
        "so-uf-find", "Following The Parent Chain", "GUIDED",
        """
        `parent` is a list where `parent[i]` is the parent of node `i`, and a
        node that is its own parent is the root of its group. Return the root
        reached from `x`.

        This is the `find` half of union-find, and the whole of it is: keep
        stepping up until a node points at itself. The step is missing.
        """,
        "find_root", "parent, x", _find_root,
        """
        def find_root(parent, x):
            while parent[x] != x:
                x = parent[x]       # step up one level
            return x
        """,
        [("two levels", [[0, 0, 1], 2]), ("already a root", [[0, 0, 1], 0])],
        [("one level", [[0, 0, 1], 1]), ("separate groups", [[0, 1, 1], 2]),
         ("chain of four", [[0, 0, 1, 2], 3]),
         ("every node its own root", [[0, 1, 2], 1])],
        edges=[("single node", [[0], 0]), ("deep chain", [[0, 0, 1, 2, 3, 4], 5])],
        pattern="ARRAY", family="union_find", realm="graph_wastes",
        secondary=["SET"], time="O(depth)", space="O(1)",
        starter="""
        def find_root(parent, x):
            while parent[x] != x:
                x = __BLANK__       # step up one level
            return x
        """,
        nudge="The loop condition already says what a root is. The body just has "
              "to move `x` one link closer to it.",
        pseudocode="while x is not its own parent: x = its parent",
        fragment=_same_move("while node.owner is not node:\n    node = node.owner"),
        failures=["Writing `x = parent[parent[x]]`, which skips levels and can "
                  "overshoot a root",
                  "Looping forever on a malformed parent list containing a cycle"],
        tags=["union-find", "graphs"],
    ))

    P.append(sp(
        "so-uf-same-group", "Are These Two Connected", "TUTORIAL",
        """
        Nodes are numbered 0..`n`-1 and `edges` is a list of `[a, b]` pairs
        joining two nodes. Return True if `a` and `b` end up in the same group.

        Build the parent array, union each edge, then compare roots. Union-find
        answers this without ever walking the graph — which is what makes it the
        right structure when the edges arrive one at a time.
        """,
        "same_group", "n, edges, a, b", _same_group,
        """
        def same_group(n, edges, a, b):
            parent = list(range(n))         # everyone starts alone

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]   # halve the path on the way up
                    x = parent[x]
                return x

            for first, second in edges:
                root_a, root_b = find(first), find(second)
                if root_a != root_b:
                    parent[root_b] = root_a         # union
            if not 0 <= a < n or not 0 <= b < n:
                return False
            return find(a) == find(b)
        """,
        [("connected", [4, [[0, 1], [1, 2]], 0, 2]),
         ("not connected", [4, [[0, 1], [2, 3]], 0, 3])],
        [("same node", [3, [], 1, 1]), ("direct edge", [2, [[0, 1]], 1, 0]),
         ("long chain", [5, [[0, 1], [1, 2], [2, 3], [3, 4]], 0, 4]),
         ("duplicate edges", [3, [[0, 1], [0, 1]], 1, 0])],
        edges=[("no edges", [2, [], 0, 1]),
               ("self loop", [2, [[0, 0]], 0, 1])],
        pattern="ARRAY", family="union_find", realm="graph_wastes",
        secondary=["SET", "DFS"], time="O(E * alpha(n))", space="O(n)",
        after="so-uf-find",
        starter_hint="parent = list(range(n)); find, then union each edge",
        nudge="`parent[x] = parent[parent[x]]` inside the find loop is path "
              "halving. One line, and it is most of why this is near-constant.",
        pseudocode="parent = list(range(n))\nfor each edge: link the two roots\n"
                   "answer: find(a) == find(b)",
        failures=["Writing `parent[b] = a` instead of linking the two ROOTS, "
                  "which silently breaks earlier unions",
                  "Comparing `parent[a] == parent[b]` instead of the roots"],
        tags=["union-find", "graphs"],
    ))

    P.append(sp(
        "so-uf-components", "Counting The Islands Of A Graph", "EASY",
        """
        Nodes are numbered 0..`n`-1 and `edges` joins pairs of them. Return how
        many connected components the graph has. Isolated nodes count as their
        own component.

        Start at `n` components and subtract one every time a union actually
        merges two different groups. An edge inside a group changes nothing.
        """,
        "count_components", "n, edges", _count_components,
        """
        def count_components(n, edges):
            parent = list(range(n))
            groups = n

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for a, b in edges:
                root_a, root_b = find(a), find(b)
                if root_a != root_b:
                    parent[root_b] = root_a
                    groups -= 1     # only a real merge reduces the count
            return groups
        """,
        [("two islands", [5, [[0, 1], [1, 2], [3, 4]]]),
         ("all separate", [3, []])],
        [("one component", [3, [[0, 1], [1, 2]]]),
         ("redundant edge", [3, [[0, 1], [1, 2], [0, 2]]]),
         ("self loop", [3, [[1, 1]]]),
         ("duplicate edges", [4, [[0, 1], [0, 1], [2, 3]]])],
        edges=[("no nodes", [0, []]), ("single node", [1, []])],
        pattern="ARRAY", family="union_find", realm="graph_wastes",
        secondary=["DFS", "SET"], time="O(E * alpha(n))", space="O(n)",
        after="so-uf-same-group",
        starter_hint="count down from n; only decrement on a real merge",
        nudge="A DFS from every unvisited node also solves this. Union-find wins "
              "when the edges keep arriving after you have answered once.",
        pseudocode="groups = n\nfor each edge: if the roots differ, link them and "
                   "groups -= 1",
        failures=["Decrementing on every edge, which undercounts on duplicates",
                  "Forgetting that a node with no edges is still a component"],
        tags=["union-find", "graphs", "classic"],
    ))

    P.append(sp(
        "so-uf-redundant", "The Edge That Closed The Loop", "MEDIUM",
        """
        `edges` arrive in order and join labelled nodes. Return the first edge
        that joins two nodes already connected to each other — the edge that
        creates a cycle — as `[a, b]`, or `[]` if the edges never form one.

        Union-find is built for exactly this: before linking, ask whether they
        are already linked.
        """,
        "redundant_edge", "edges", _redundant_edge,
        """
        def redundant_edge(edges):
            parent = {}

            def find(x):
                parent.setdefault(x, x)
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for a, b in edges:
                root_a, root_b = find(a), find(b)
                if root_a == root_b:
                    return [a, b]       # already connected: this edge is the cycle
                parent[root_b] = root_a
            return []
        """,
        [("triangle", [[[1, 2], [1, 3], [2, 3]]]),
         ("a tree, no cycle", [[[1, 2], [1, 3]]])],
        [("cycle at the end", [[[1, 2], [2, 3], [3, 4], [1, 4]]]),
         ("immediate repeat", [[[1, 2], [1, 2]]]),
         ("two components, one cycle", [[[1, 2], [3, 4], [4, 5], [3, 5]]]),
         ("self loop", [[[1, 1]]])],
        edges=[("no edges", [[]]), ("single edge", [[[7, 8]]])],
        pattern="ARRAY", family="union_find", realm="graph_wastes",
        secondary=["SET", "DFS"], time="O(E * alpha(n))", space="O(n)",
        after="so-uf-components",
        starter_hint="a dict-backed parent map, since the labels are arbitrary",
        nudge="Nodes are labels, not indices, so back the parent map with a dict "
              "and create an entry the first time you see a node.",
        pseudocode="for each edge: if find(a) == find(b): this edge closes a cycle\n"
                   "otherwise union them",
        failures=["Returning the last edge instead of the first cycle-closing one",
                  "Assuming node labels are 0..n-1 and indexing a list with them"],
        tags=["union-find", "graphs", "cycles"],
    ))

    # -- topological order ---------------------------------------------------

    P.append(sp(
        "so-topo-indegree", "Counting What Points At You", "GUIDED",
        """
        Nodes are numbered 0..`n`-1 and each edge `[a, b]` means "a must come
        before b". Return a list where entry `i` is how many edges point *at*
        node `i`.

        Every topological sort starts here: a node with an indegree of 0 has
        nothing left blocking it. One line is missing.
        """,
        "indegrees", "n, edges", _indegrees,
        """
        def indegrees(n, edges):
            counts = [0] * n
            for source, target in edges:
                counts[target] += 1     # only the arrow's head is counted
            return counts
        """,
        [("chain", [3, [[0, 1], [1, 2]]]), ("fan in", [3, [[0, 2], [1, 2]]])],
        [("no edges", [3, []]), ("fan out", [3, [[0, 1], [0, 2]]]),
         ("duplicate edges", [2, [[0, 1], [0, 1]]]),
         ("cycle", [2, [[0, 1], [1, 0]]])],
        edges=[("no nodes", [0, []]), ("self loop", [2, [[1, 1]]])],
        pattern="HASH_MAP", family="graph_topo", realm="graph_wastes",
        secondary=["ARRAY"], time="O(n + E)", space="O(n)",
        starter="""
        def indegrees(n, edges):
            counts = [0] * n
            for source, target in edges:
                __BLANK__               # one more arrow lands on `target`
            return counts
        """,
        nudge="An edge `[a, b]` leaves `a` and arrives at `b`. Only the arrival "
              "counts here.",
        pseudocode="counts = [0] * n\nfor a, b in edges: counts[b] += 1",
        fragment=_same_move("references[imported_module] += 1"),
        failures=["Counting the source as well, which is the out-degree",
                  "Skipping duplicate edges — two edges are two blockers"],
        tags=["topological-sort", "graphs"],
    ))

    P.append(sp(
        "so-topo-sources", "Everything That Can Start Now", "TUTORIAL",
        """
        Each edge `[a, b]` means "a must come before b". Return, ascending,
        every node from 0..`n`-1 that nothing points at — the tasks that could
        be started immediately.
        """,
        "sources", "n, edges", _sources,
        """
        def sources(n, edges):
            blocked = [0] * n
            for _, target in edges:
                blocked[target] += 1
            return [node for node in range(n) if blocked[node] == 0]
        """,
        [("chain", [3, [[0, 1], [1, 2]]]), ("two roots", [4, [[0, 2], [1, 2]]])],
        [("no edges", [3, []]), ("everything blocked", [2, [[0, 1], [1, 0]]]),
         ("fan out", [3, [[0, 1], [0, 2]]]),
         ("duplicate edges", [3, [[0, 1], [0, 1]]])],
        edges=[("no nodes", [0, []]), ("self loop blocks itself", [2, [[1, 1]]])],
        pattern="HASH_MAP", family="graph_topo", realm="graph_wastes",
        secondary=["ARRAY", "BFS"], time="O(n + E)", space="O(n)",
        after="so-topo-indegree",
        starter_hint="indegree array, then collect the zeros in order",
        nudge="A cycle has no source. An empty answer on a non-empty graph is "
              "how Kahn's algorithm detects one.",
        pseudocode="count indegrees, return every node whose count is 0",
        failures=["Collecting sources from the edge list only, which misses "
                  "isolated nodes"],
        tags=["topological-sort", "graphs"],
    ))

    P.append(sp(
        "so-topo-order", "The Ordained Sequence", "EASY",
        """
        Each edge `[a, b]` means "a must come before b". Return a valid ordering
        of all `n` nodes, or `[]` if the constraints contain a cycle and no
        ordering exists.

        When several orderings are valid, return the lexicographically smallest
        one: whenever more than one node is ready, take the smallest-numbered.
        """,
        "topological_order", "n, edges", _topo_order,
        """
        def topological_order(n, edges):
            import heapq
            blocked = [0] * n
            after = {node: [] for node in range(n)}
            for source, target in edges:
                after[source].append(target)
                blocked[target] += 1

            ready = [node for node in range(n) if blocked[node] == 0]
            heapq.heapify(ready)        # a heap, so ties go to the smallest node
            out = []
            while ready:
                node = heapq.heappop(ready)
                out.append(node)
                for nxt in after[node]:
                    blocked[nxt] -= 1
                    if blocked[nxt] == 0:
                        heapq.heappush(ready, nxt)
            return out if len(out) == n else []      # short output means a cycle
        """,
        [("chain", [3, [[0, 1], [1, 2]]]), ("cycle", [2, [[0, 1], [1, 0]]])],
        [("no edges", [3, []]), ("diamond", [4, [[0, 1], [0, 2], [1, 3], [2, 3]]]),
         ("tie goes to the smaller", [3, [[2, 0]]]),
         ("two components", [4, [[1, 0], [3, 2]]])],
        edges=[("no nodes", [0, []]), ("self loop", [2, [[1, 1]]]),
               ("duplicate edges", [2, [[0, 1], [0, 1]]])],
        pattern="BFS", family="graph_topo", realm="graph_wastes",
        secondary=["QUEUE", "HEAP", "SORTING"], time="O((n + E) log n)",
        space="O(n + E)", after="so-topo-sources",
        starter_hint="Kahn: indegrees, a ready set, and a count of what you emitted",
        nudge="A plain deque gives a valid order. Swapping it for a heap is what "
              "makes the order the smallest valid one.",
        pseudocode="ready = nodes with indegree 0\nwhile ready: pop the smallest, "
                   "emit it, decrement its targets, push any that hit 0\n"
                   "if fewer than n emitted: cycle",
        failures=["Returning the partial order instead of [] when a cycle exists",
                  "Decrementing a node's indegree more than once per edge",
                  "Using a plain list and `min()`, which is O(n) per pop"],
        tags=["topological-sort", "graphs", "classic"],
    ))

    P.append(sp(
        "so-topo-can-finish", "Can The Course List Be Finished", "MEDIUM",
        """
        There are `n` courses numbered 0..`n`-1. Each pair `[course, needs]` in
        `prereqs` means `course` requires `needs` first. Return True if every
        course can be taken.

        The question is only whether the prerequisite graph has a cycle. Note
        the pair order — it is backwards from the edge direction, and reading
        past that is the most common way to fail this one.
        """,
        "can_finish", "n, prereqs", _can_finish,
        """
        def can_finish(n, prereqs):
            blocked = [0] * n
            after = {node: [] for node in range(n)}
            for course, needs in prereqs:
                after[needs].append(course)     # needs -> course, not the reverse
                blocked[course] += 1

            ready = [node for node in range(n) if blocked[node] == 0]
            taken = 0
            while ready:
                node = ready.pop()
                taken += 1
                for nxt in after[node]:
                    blocked[nxt] -= 1
                    if blocked[nxt] == 0:
                        ready.append(nxt)
            return taken == n       # anything left is inside a cycle
        """,
        [("possible", [2, [[1, 0]]]), ("impossible", [2, [[1, 0], [0, 1]]])],
        [("no prerequisites", [3, []]),
         ("long chain", [4, [[1, 0], [2, 1], [3, 2]]]),
         ("three way cycle", [3, [[1, 0], [2, 1], [0, 2]]]),
         ("diamond", [4, [[1, 0], [2, 0], [3, 1], [3, 2]]])],
        edges=[("no courses", [0, []]), ("self prerequisite", [1, [[0, 0]]]),
               ("duplicate prerequisite", [2, [[1, 0], [1, 0]]])],
        pattern="BFS", family="graph_topo", realm="graph_wastes",
        secondary=["DFS", "QUEUE"], time="O(n + E)", space="O(n + E)",
        after="so-topo-order",
        starter_hint="count what you manage to take; compare with n",
        nudge="You do not need the order, only whether one exists. Count the "
              "nodes you can retire and compare with `n`.",
        pseudocode="build the graph with edges needs -> course\n"
                   "peel off indegree-0 nodes, counting them\ntaken == n",
        failures=["Reversing the pair and building the graph backwards, which "
                  "still terminates and still returns True on a chain",
                  "Depth-first recursion without a third colour, which reports a "
                  "cycle for a node merely visited twice"],
        tags=["topological-sort", "graphs", "cycles"],
    ))

    return P
