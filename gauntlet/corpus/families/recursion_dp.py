"""Recursive Forest, Dynamic Programming Ruins, Complexity Tower approaches."""
from __future__ import annotations

from functools import lru_cache

from ._base import code_problem

Q = {"QUORA": 2.5, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 1.0}
QS = {"QUORA": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}
VIZ_R = {"type": "recursion", "caption": "Nested rooms; you return carrying results."}
VIZ_DP = {"type": "dp", "caption": "Solved tiles light up and are reused."}


def _factorial(n):
    return 1 if n <= 1 else n * _factorial(n - 1)


def _fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _digit_reduce(n):
    steps = 0
    while n >= 10:
        n = sum(int(d) for d in str(n))
        steps += 1
    return steps


def _power(base, exp):
    if exp == 0:
        return 1
    half = _power(base, exp // 2)
    return half * half * (base if exp % 2 else 1)


def _reverse_string(s):
    return s if len(s) <= 1 else _reverse_string(s[1:]) + s[0]


def _subsets(nums):
    out = [[]]
    for v in nums:
        out += [row + [v] for row in out]
    return sorted(out, key=lambda r: (len(r), r))


def _permutations(nums):
    if not nums:
        return [[]]
    out = []
    for i, v in enumerate(nums):
        for rest in _permutations(nums[:i] + nums[i + 1:]):
            out.append([v] + rest)
    return sorted(out)


def _combination_sum(candidates, target):
    out = []

    def walk(start, remaining, path):
        if remaining == 0:
            out.append(list(path))
            return
        if remaining < 0:
            return
        for i in range(start, len(candidates)):
            path.append(candidates[i])
            walk(i, remaining - candidates[i], path)
            path.pop()

    walk(0, target, [])
    return sorted(out)


def _generate_parens(n):
    out = []

    def walk(current, opened, closed):
        if len(current) == 2 * n:
            out.append(current)
            return
        if opened < n:
            walk(current + "(", opened + 1, closed)
        if closed < opened:
            walk(current + ")", opened, closed + 1)

    walk("", 0, 0)
    return sorted(out)


def _climb_stairs(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _house_robber(nums):
    take, skip = 0, 0
    for v in nums:
        take, skip = skip + v, max(skip, take)
    return max(take, skip)


def _coin_change(coins, amount):
    INF = amount + 1
    dp = [0] + [INF] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if coin <= value:
                dp[value] = min(dp[value], dp[value - coin] + 1)
    return -1 if dp[amount] >= INF else dp[amount]


def _unique_paths(rows, cols):
    if rows <= 0 or cols <= 0:
        return 0
    row = [1] * cols
    for _ in range(1, rows):
        for c in range(1, cols):
            row[c] += row[c - 1]
    return row[-1]


def _lis(nums):
    import bisect
    tails = []
    for v in nums:
        i = bisect.bisect_left(tails, v)
        if i == len(tails):
            tails.append(v)
        else:
            tails[i] = v
    return len(tails)


def _edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] if a[i - 1] == b[j - 1] else 1 + min(
                prev[j - 1], prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def _max_subarray(nums):
    if not nums:
        return 0
    best = cur = nums[0]
    for v in nums[1:]:
        cur = max(v, cur + v)
        best = max(best, cur)
    return best


def _min_path_sum(grid):
    if not grid or not grid[0]:
        return 0
    rows, cols = len(grid), len(grid[0])
    dp = [row[:] for row in grid]
    for c in range(1, cols):
        dp[0][c] += dp[0][c - 1]
    for r in range(1, rows):
        dp[r][0] += dp[r - 1][0]
        for c in range(1, cols):
            dp[r][c] += min(dp[r - 1][c], dp[r][c - 1])
    return dp[-1][-1]


def _word_break(s, words):
    pool = set(words)
    dp = [True] + [False] * len(s)
    for end in range(1, len(s) + 1):
        for start in range(end):
            if dp[start] and s[start:end] in pool:
                dp[end] = True
                break
    return dp[-1]


def _decode_ways(digits):
    if not digits or digits[0] == "0":
        return 0
    prev, cur = 1, 1
    for i in range(1, len(digits)):
        nxt = 0
        if digits[i] != "0":
            nxt += cur
        if 10 <= int(digits[i - 1:i + 1]) <= 26:
            nxt += prev
        prev, cur = cur, nxt
    return cur


def _budget_alerts(costs, values, budget):
    dp = [0] * (budget + 1)
    for cost, value in zip(costs, values):
        for b in range(budget, cost - 1, -1):
            dp[b] = max(dp[b], dp[b - cost] + value)
    return dp[budget]


def build() -> list:
    P: list = []

    P.append(code_problem(
        id="rc-factorial", title="The Descending Spiral", realm="recursive_forest",
        pattern="RECURSION", difficulty="TUTORIAL", family="recursion_basics",
        profile_weight=Q, viz=VIZ_R,
        statement="""
            Return `n!` using recursion. `0!` and `1!` are both `1`.

            This is where the Recursive Forest teaches its one rule: shrink toward a base
            case you actually reach.
        """,
        fn_name="factorial", params="n", reference=_factorial,
        canonical="""
            def factorial(n):
                if n <= 1:
                    return 1            # base case: without this you fall forever
                return n * factorial(n - 1)
        """,
        visible=[("five", [5]), ("zero", [0])],
        hidden=[("one", [1]), ("ten", [10]), ("twenty", [20])],
        edges=[("negative treated as base", [-3])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Missing base case gives RecursionError",
                  "Using `n == 1` alone breaks for n = 0"],
        nudge="Every recursion needs a floor and a step that reaches it.",
        visual="You walk into a smaller copy of the same room until the room is too small "
               "to enter, then carry the answer back out.",
        pseudocode="if n <= 1: return 1; return n * factorial(n-1)",
        tags=["tutorial"],
    ))

    P.append(code_problem(
        id="rc-fib", title="The Twin Seeds", realm="recursive_forest",
        pattern="DP", difficulty="EASY", family="dp_linear", secondary=["RECURSION"],
        profile_weight=Q, viz=VIZ_DP,
        statement="""
            Return the `n`-th Fibonacci number, where `fib(0) == 0` and `fib(1) == 1`.

            Naive recursion recomputes the same seed thousands of times. The hidden tests
            include `n = 90`.
        """,
        fn_name="fib", params="n", reference=_fib,
        canonical="""
            def fib(n):
                a, b = 0, 1
                for _ in range(n):
                    a, b = b, a + b      # only the last two values ever matter
                return a
        """,
        visible=[("small", [7]), ("zero", [0])],
        hidden=[("one", [1]), ("thirty", [30]), ("ninety", [90]), ("fifty", [50])],
        edges=[("two", [2])],
        perf=[("n=90", [90])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Plain recursion is O(2^n) and times out around n = 40",
                  "Memoised recursion is fine but uses O(n) stack",
                  "Off-by-one on the seed values"],
        nudge="You only ever need the previous two values. Everything else is waste.",
        visual="Two glowing tiles slide forward; each new tile is the sum behind it.",
        pseudocode="a, b = 0, 1; repeat n times: a, b = b, a + b; return a",
        alternates=[{"name": "@lru_cache recursion", "note": "O(n), clear, more memory.",
                     "complexity": "O(n)"}],
        tags=["core", "optimization"],
    ))

    P.append(code_problem(
        id="rc-digit-reduce", title="The Reducing Rite", realm="recursive_forest",
        pattern="RECURSION", difficulty="EASY", family="recursion_basics",
        profile_weight=Q, viz=VIZ_R,
        source_type="REPORTED_INTERVIEW", company="Quora", year="reported pattern",
        provenance="Recursive number reduction is a repeatedly reported warm-up archetype.",
        statement="""
            Repeatedly replace `n` with the sum of its digits until a single digit remains.
            Return how many replacements that took. A number already below ten takes `0`.
        """,
        fn_name="digit_reduction_steps", params="n", reference=_digit_reduce,
        canonical="""
            def digit_reduction_steps(n):
                steps = 0
                while n >= 10:
                    n = sum(int(d) for d in str(n))
                    steps += 1
                return steps
        """,
        visible=[("two steps", [38]), ("already single", [5])],
        hidden=[("zero", [0]), ("large", [999999]), ("exactly ten", [10]),
                ("three steps", [199999])],
        edges=[("nine", [9])],
        time_complexity="O(log n) per step", space_complexity="O(1)",
        failures=["Returning the final digit rather than the number of steps",
                  "Looping while n > 10 instead of >= 10"],
        nudge="Count the transformations, not the result.",
        visual="A number folds into itself until it cannot fold again.",
        pseudocode="while n >= 10: n = sum of digits; steps += 1",
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="rc-fast-power", title="Halving the Incantation", realm="recursive_forest",
        pattern="RECURSION", difficulty="MEDIUM", family="recursion_divide",
        profile_weight=Q, viz=VIZ_R,
        statement="""
            Return `base ** exp` for a non-negative integer exponent, in O(log exp)
            multiplications. Do not use `**` or `pow`.
        """,
        fn_name="fast_power", params="base, exp", reference=_power,
        canonical="""
            def fast_power(base, exp):
                if exp == 0:
                    return 1
                half = fast_power(base, exp // 2)      # compute ONCE, reuse
                return half * half * (base if exp % 2 else 1)
        """,
        visible=[("even", [2, 10]), ("odd", [3, 5])],
        hidden=[("zero exponent", [7, 0]), ("one", [5, 1]), ("large", [2, 30]),
                ("negative base", [-2, 3])],
        edges=[("base zero", [0, 5]), ("base one", [1, 100])],
        time_complexity="O(log exp)", space_complexity="O(log exp)",
        failures=["Calling fast_power twice per level makes it O(exp) again",
                  "Forgetting the odd-exponent extra multiplication"],
        nudge="Compute the half once and square it. Calling it twice throws away the "
              "entire saving.",
        visual="Each step halves the work; the tower of squarings is only log tall.",
        pseudocode="half = f(base, exp//2); return half*half*(base if odd else 1)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="rc-subsets", title="Every Possible Loadout", realm="recursive_forest",
        pattern="RECURSION", difficulty="MEDIUM", family="backtracking",
        profile_weight=Q, viz=VIZ_R, cmp="nested_set",
        statement="""
            Return every subset of `nums` (the power set). The values are distinct. Order
            does not matter.
        """,
        fn_name="subsets", params="nums", reference=_subsets,
        canonical="""
            def subsets(nums):
                out = [[]]
                for value in nums:
                    out += [row + [value] for row in out]   # double the set each time
                return out
        """,
        visible=[("three", [[1, 2, 3]]), ("one", [[7]])],
        hidden=[("two", [[1, 2]]), ("four", [[1, 2, 3, 4]]),
                ("negatives", [[-1, 0]])],
        edges=[("empty", [[]])],
        time_complexity="O(n·2^n)", space_complexity="O(n·2^n)",
        failures=["Forgetting the empty subset",
                  "Appending to the row in place instead of building a new list"],
        nudge="Each new element either joins every existing subset or does not. That is a "
              "doubling.",
        visual="Every element splits the world in two: with it, and without it.",
        pseudocode="out = [[]]; for v: out += [row + [v] for row in out]",
        tags=["core"],
    ))

    P.append(code_problem(
        id="rc-permutations", title="Every Order of March", realm="recursive_forest",
        pattern="RECURSION", difficulty="MEDIUM", family="backtracking",
        profile_weight=Q, viz=VIZ_R, cmp="nested_set",
        statement="Return every permutation of the distinct values in `nums`.",
        fn_name="permutations", params="nums", reference=_permutations,
        canonical="""
            def permutations(nums):
                if not nums:
                    return [[]]
                out = []
                for i, value in enumerate(nums):
                    for rest in permutations(nums[:i] + nums[i + 1:]):
                        out.append([value] + rest)
                return out
        """,
        visible=[("three", [[1, 2, 3]]), ("two", [[1, 2]])],
        hidden=[("one", [[9]]), ("four", [[1, 2, 3, 4]]), ("negatives", [[-1, 1]])],
        edges=[("empty", [[]])],
        time_complexity="O(n·n!)", space_complexity="O(n·n!)",
        failures=["Returning [] rather than [[]] for the empty input, which kills every "
                  "branch above it",
                  "Mutating the input list while recursing"],
        nudge="Pick each element as the head; permute what is left.",
        visual="Each choice removes one option and recurses on the remainder.",
        pseudocode="for each value: prepend it to every permutation of the rest",
        tags=["core"],
    ))

    P.append(code_problem(
        id="rc-combination-sum", title="Runes That Add Up", realm="recursive_forest",
        pattern="RECURSION", difficulty="MEDIUM", family="backtracking",
        profile_weight=Q, viz=VIZ_R, cmp="nested_set",
        statement="""
            Return every combination of `candidates` summing to `target`. Each candidate
            may be reused any number of times. Combinations that differ only in order are
            the same combination.
        """,
        fn_name="combination_sum", params="candidates, target",
        reference=_combination_sum,
        canonical="""
            def combination_sum(candidates, target):
                out = []

                def walk(start, remaining, path):
                    if remaining == 0:
                        out.append(list(path))
                        return
                    if remaining < 0:
                        return
                    for i in range(start, len(candidates)):
                        path.append(candidates[i])
                        walk(i, remaining - candidates[i], path)   # i, not i+1: reusable
                        path.pop()

                walk(0, target, [])
                return out
        """,
        visible=[("classic", [[2, 3, 6, 7], 7]), ("none", [[5], 3])],
        hidden=[("multiple", [[2, 3, 5], 8]), ("single reuse", [[2], 6]),
                ("exact", [[7], 7])],
        edges=[("target zero", [[2], 0]), ("no candidates", [[], 5])],
        time_complexity="exponential in target/min(candidates)", space_complexity="O(target)",
        failures=["Recursing with `i + 1` forbids reuse and gives the wrong answer",
                  "Starting each branch at 0 produces permutations, not combinations",
                  "Forgetting to copy the path"],
        nudge="Passing `i` allows reuse; passing `start` at all is what stops permutations.",
        visual="A branching search that never looks backwards past its starting index.",
        pseudocode="walk(start, remaining): for i in start..n: take candidates[i], recurse at i",
        tags=["core", "backtracking"],
    ))

    P.append(code_problem(
        id="rc-generate-parens", title="Well-Formed Wards", realm="recursive_forest",
        pattern="RECURSION", difficulty="MEDIUM", family="backtracking",
        secondary=["STRING"], profile_weight=Q, viz=VIZ_R, cmp="set",
        statement="Return every well-formed string of `n` pairs of parentheses.",
        fn_name="generate_parens", params="n", reference=_generate_parens,
        canonical="""
            def generate_parens(n):
                out = []

                def walk(current, opened, closed):
                    if len(current) == 2 * n:
                        out.append(current)
                        return
                    if opened < n:
                        walk(current + "(", opened + 1, closed)
                    if closed < opened:            # never close what was not opened
                        walk(current + ")", opened, closed + 1)

                walk("", 0, 0)
                return out
        """,
        visible=[("three pairs", [3]), ("one pair", [1])],
        hidden=[("two", [2]), ("four", [4])],
        edges=[("zero", [0])],
        time_complexity="O(4^n / sqrt(n))", space_complexity="O(n)",
        failures=["Generating all 2^(2n) strings and filtering is far slower",
                  "Allowing a closing bracket when none is open"],
        nudge="Two counters constrain the whole search: you may open while under n, and "
              "close only while closed < opened.",
        visual="A tree of choices that prunes itself the moment a ward would be invalid.",
        pseudocode="open if opened < n; close if closed < opened; record at length 2n",
        tags=["core", "backtracking"],
    ))

    P.append(code_problem(
        id="dp-climb-stairs", title="The Ascending Ruins", realm="dp_ruins",
        pattern="DP", difficulty="EASY", family="dp_linear", profile_weight=Q, viz=VIZ_DP,
        statement="""
            You climb `n` steps taking one or two at a time. Return how many distinct ways
            there are. `n = 0` has exactly one way: stand still.
        """,
        fn_name="climb_stairs", params="n", reference=_climb_stairs,
        canonical="""
            def climb_stairs(n):
                a, b = 1, 1              # ways to reach the previous two steps
                for _ in range(n):
                    a, b = b, a + b
                return a
        """,
        visible=[("three", [3]), ("two", [2])],
        hidden=[("one", [1]), ("ten", [10]), ("forty", [40])],
        edges=[("zero", [0])],
        perf=[("n=40", [40])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Plain recursion is O(2^n)", "Off-by-one on the seeds"],
        nudge="Ways to reach a step = ways to reach the two steps below it.",
        visual="Each tile lights up from the two tiles behind it.",
        pseudocode="a, b = 1, 1; n times: a, b = b, a + b",
        tags=["core"],
    ))

    P.append(code_problem(
        id="dp-house-robber", title="The Selective Plunder", realm="dp_ruins",
        pattern="DP", difficulty="MEDIUM", family="dp_linear", profile_weight=Q, viz=VIZ_DP,
        statement="""
            Each value is the loot in a vault. You cannot rob two adjacent vaults. Return
            the maximum loot.
        """,
        fn_name="rob", params="nums", reference=_house_robber,
        canonical="""
            def rob(nums):
                take, skip = 0, 0
                for value in nums:
                    take, skip = skip + value, max(skip, take)
                return max(take, skip)
        """,
        visible=[("classic", [[1, 2, 3, 1]]), ("bigger later", [[2, 7, 9, 3, 1]])],
        hidden=[("all same", [[5, 5, 5, 5]]), ("two", [[2, 1]]),
                ("descending", [[9, 1, 1, 9]])],
        edges=[("empty", [[]]), ("single", [[4]])],
        perf=[("100k vaults", [[i % 97 for i in range(100000)]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Taking every other vault greedily fails on [2, 1, 1, 2]",
                  "Two O(n) variables are enough; a full dp array is unnecessary"],
        nudge="At each vault you either take it (adding to the best that skipped the "
              "previous one) or you skip it.",
        visual="Two running totals race forward; taking one forbids the other's last step.",
        pseudocode="take, skip = skip + value, max(skip, take)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="dp-coin-change", title="The Minted Sum", realm="dp_ruins", pattern="DP",
        difficulty="MEDIUM", family="dp_unbounded", profile_weight=Q, viz=VIZ_DP,
        statement="""
            Return the fewest coins summing exactly to `amount`, or `-1` if impossible.
            Coins may be reused without limit.
        """,
        fn_name="coin_change", params="coins, amount", reference=_coin_change,
        canonical="""
            def coin_change(coins, amount):
                INF = amount + 1
                dp = [0] + [INF] * amount        # dp[v] = fewest coins to make v
                for value in range(1, amount + 1):
                    for coin in coins:
                        if coin <= value:
                            dp[value] = min(dp[value], dp[value - coin] + 1)
                return -1 if dp[amount] >= INF else dp[amount]
        """,
        visible=[("classic", [[1, 2, 5], 11]), ("impossible", [[2], 3])],
        hidden=[("zero amount", [[1], 0]), ("greedy trap", [[1, 3, 4], 6]),
                ("single coin", [[7], 7]), ("no coins", [[], 5])],
        edges=[("amount zero no coins", [[], 0])],
        perf=[("amount 4000", [[1, 5, 10, 25], 4000])],
        time_complexity="O(amount · len(coins))", space_complexity="O(amount)",
        failures=["Greedy largest-coin-first fails: [1,3,4] for 6 gives 3 coins, not 2",
                  "Returning INF instead of -1",
                  "Not seeding dp[0] = 0"],
        nudge="Greedy is wrong here. Build every amount from zero upward.",
        visual="Each tile from 1 to amount lights up using the cheapest already-lit tile "
               "one coin behind it.",
        pseudocode="dp[0]=0; for v in 1..amount: dp[v] = min(dp[v-coin] + 1)",
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="dp-unique-paths", title="Roads Through the Ruins", realm="dp_ruins",
        pattern="DP", difficulty="MEDIUM", family="dp_grid", secondary=["MATRIX"],
        profile_weight=Q, viz=VIZ_DP,
        statement="""
            Count the distinct paths from the top-left to the bottom-right of a
            `rows x cols` grid moving only right or down.
        """,
        fn_name="unique_paths", params="rows, cols", reference=_unique_paths,
        canonical="""
            def unique_paths(rows, cols):
                if rows <= 0 or cols <= 0:
                    return 0
                row = [1] * cols                  # one row of the table is enough
                for _ in range(1, rows):
                    for c in range(1, cols):
                        row[c] += row[c - 1]
                return row[-1]
        """,
        visible=[("3x7", [3, 7]), ("3x2", [3, 2])],
        hidden=[("1x1", [1, 1]), ("single row", [1, 9]), ("square", [5, 5]),
                ("large", [15, 15])],
        edges=[("zero rows", [0, 5])],
        time_complexity="O(rows·cols)", space_complexity="O(cols)",
        failures=["Recursing without memoisation is exponential",
                  "Off-by-one on the first row and column, which are all 1"],
        nudge="Paths to a tile = paths from above + paths from the left.",
        visual="The grid lights up left to right, top to bottom; each tile sums its two "
               "already-lit neighbours.",
        pseudocode="row = [1]*cols; for each further row: row[c] += row[c-1]",
        tags=["core"],
    ))

    P.append(code_problem(
        id="dp-max-subarray", title="The Richest Stretch", realm="dp_ruins", pattern="DP",
        difficulty="MEDIUM", family="dp_linear", secondary=["ARRAY"], profile_weight=Q,
        viz=VIZ_DP,
        statement="""
            Return the largest sum of any non-empty contiguous subarray. Values may be
            negative. Return `0` for an empty list.
        """,
        fn_name="max_subarray", params="nums", reference=_max_subarray,
        canonical="""
            def max_subarray(nums):
                if not nums:
                    return 0
                best = current = nums[0]
                for value in nums[1:]:
                    current = max(value, current + value)   # extend, or start fresh here
                    best = max(best, current)
                return best
        """,
        visible=[("classic", [[-2, 1, -3, 4, -1, 2, 1, -5, 4]]), ("all positive", [[1, 2, 3]])],
        hidden=[("all negative", [[-3, -1, -2]]), ("single", [[5]]),
                ("zeros", [[0, 0, 0]]), ("one big dip", [[5, -100, 6]])],
        edges=[("empty", [[]])],
        perf=[("200k", [[(i % 41) - 20 for i in range(200000)]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Seeding `best` at 0 returns 0 for an all-negative array",
                  "Checking every subarray is O(n^2)"],
        nudge="At each element: does the running total help you, or is the element better "
              "alone?",
        visual="A running total that resets whenever carrying the past costs more than "
               "starting over.",
        pseudocode="current = max(value, current + value); best = max(best, current)",
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="dp-min-path-sum", title="The Cheapest Descent", realm="dp_ruins", pattern="DP",
        difficulty="MEDIUM", family="dp_grid", secondary=["MATRIX"], profile_weight=Q,
        viz=VIZ_DP,
        statement="""
            Each cell holds a toll. Moving only right or down from the top-left to the
            bottom-right, return the minimum total toll.
        """,
        fn_name="min_path_sum", params="grid", reference=_min_path_sum,
        canonical="""
            def min_path_sum(grid):
                if not grid or not grid[0]:
                    return 0
                rows, cols = len(grid), len(grid[0])
                dp = [row[:] for row in grid]
                for c in range(1, cols):
                    dp[0][c] += dp[0][c - 1]       # top row: only from the left
                for r in range(1, rows):
                    dp[r][0] += dp[r - 1][0]       # left column: only from above
                    for c in range(1, cols):
                        dp[r][c] += min(dp[r - 1][c], dp[r][c - 1])
                return dp[-1][-1]
        """,
        visible=[("classic", [[[1, 3, 1], [1, 5, 1], [4, 2, 1]]]),
                 ("single row", [[[1, 2, 3]]])],
        hidden=[("single column", [[[1], [2], [3]]]), ("single cell", [[[5]]]),
                ("zeros", [[[0, 0], [0, 0]]])],
        edges=[("empty", [[]])],
        time_complexity="O(rows·cols)", space_complexity="O(rows·cols)",
        failures=["Forgetting that the first row and column have only one predecessor",
                  "Mutating the caller's grid — acceptable here, surprising elsewhere"],
        nudge="Fill the borders first; then every interior cell has two choices.",
        visual="Tolls accumulate; each tile takes the cheaper of the two lit neighbours.",
        pseudocode="dp[r][c] += min(dp[r-1][c], dp[r][c-1])",
        tags=["core"],
    ))

    P.append(code_problem(
        id="dp-lis", title="The Lengthening Sequence", realm="dp_ruins", pattern="DP",
        difficulty="HARD", family="dp_subsequence", secondary=["BINARY_SEARCH"],
        profile_weight=Q, viz=VIZ_DP,
        statement="""
            Return the length of the longest strictly increasing subsequence (values need
            not be adjacent).

            An O(n^2) solution is accepted logically but the performance test needs
            O(n log n).
        """,
        fn_name="length_of_lis", params="nums", reference=_lis,
        canonical="""
            def length_of_lis(nums):
                import bisect
                tails = []          # tails[i] = smallest tail of an increasing run of i+1
                for value in nums:
                    i = bisect.bisect_left(tails, value)
                    if i == len(tails):
                        tails.append(value)
                    else:
                        tails[i] = value
                return len(tails)
        """,
        visible=[("classic", [[10, 9, 2, 5, 3, 7, 101, 18]]), ("all same", [[7, 7, 7]])],
        hidden=[("ascending", [[1, 2, 3, 4]]), ("descending", [[4, 3, 2, 1]]),
                ("negatives", [[-2, -1, -3, 0]]), ("single", [[1]])],
        edges=[("empty", [[]])],
        perf=[("40k", [[(i * 7919) % 10000 for i in range(40000)]])],
        time_complexity="O(n log n)", space_complexity="O(n)",
        failures=["`tails` is not the answer sequence — only its length is meaningful",
                  "Using bisect_right allows equal values, giving non-strict runs",
                  "The O(n^2) version times out at 40k"],
        nudge="Keep the smallest possible tail for each achievable length. Binary search "
              "tells you which length each value improves.",
        visual="A row of tiles, each holding the smallest ending value for a run of that "
               "length. Each new value overwrites exactly one tile or extends the row.",
        pseudocode="for v: i = bisect_left(tails, v); append or overwrite tails[i]",
        tags=["hard"],
    ))

    P.append(code_problem(
        id="dp-edit-distance", title="The Transmuting Script", realm="dp_ruins",
        pattern="DP", difficulty="HARD", family="dp_2d", secondary=["STRING"],
        profile_weight=Q, viz=VIZ_DP,
        statement="""
            Return the minimum number of single-character insertions, deletions or
            substitutions that turn `a` into `b`.
        """,
        fn_name="edit_distance", params="a, b", reference=_edit_distance,
        canonical="""
            def edit_distance(a, b):
                prev = list(range(len(b) + 1))       # deleting everything from a prefix
                for i in range(1, len(a) + 1):
                    cur = [i] + [0] * len(b)
                    for j in range(1, len(b) + 1):
                        if a[i - 1] == b[j - 1]:
                            cur[j] = prev[j - 1]     # free: characters already match
                        else:
                            cur[j] = 1 + min(prev[j - 1],  # substitute
                                             prev[j],      # delete from a
                                             cur[j - 1])   # insert into a
                    prev = cur
                return prev[-1]
        """,
        visible=[("classic", ["horse", "ros"]), ("longer", ["intention", "execution"])],
        hidden=[("identical", ["abc", "abc"]), ("one empty", ["", "abc"]),
                ("substitution only", ["abc", "abd"]), ("insert only", ["ab", "abc"])],
        edges=[("both empty", ["", ""])],
        time_complexity="O(len(a)·len(b))", space_complexity="O(len(b))",
        failures=["Wrong base row: an empty source needs j insertions, not 0",
                  "Mixing up which neighbour means insert versus delete"],
        nudge="Three neighbours, three operations. The diagonal is free when the "
              "characters already match.",
        visual="A grid where each cell asks its three already-lit neighbours which route "
               "was cheapest.",
        pseudocode="""
            match -> prev[j-1]
            else  -> 1 + min(prev[j-1], prev[j], cur[j-1])
        """,
        tags=["hard"],
    ))

    P.append(code_problem(
        id="dp-word-break", title="The Fractured Sentence", realm="dp_ruins", pattern="DP",
        difficulty="MEDIUM", family="dp_string", secondary=["STRING", "SET"],
        profile_weight=Q, viz=VIZ_DP, cmp="bool",
        statement="""
            Return `True` if `s` can be split into a sequence of words from `words`. Words
            may be reused.
        """,
        fn_name="word_break", params="s, words", reference=_word_break,
        canonical="""
            def word_break(s, words):
                pool = set(words)                    # membership must be O(1)
                dp = [True] + [False] * len(s)       # dp[i]: s[:i] is breakable
                for end in range(1, len(s) + 1):
                    for start in range(end):
                        if dp[start] and s[start:end] in pool:
                            dp[end] = True
                            break
                return dp[-1]
        """,
        visible=[("breakable", ["leetcode", ["leet", "code"]]),
                 ("not breakable", ["catsandog", ["cats", "dog", "sand", "and", "cat"]])],
        hidden=[("reuse", ["aaaa", ["a"]]), ("whole word", ["apple", ["apple"]]),
                ("empty string", ["", ["a"]]), ("no words", ["abc", []])],
        edges=[("single char", ["a", ["a"]])],
        perf=[("300 chars", ["a" * 300, ["a", "aa", "aaa"]])],
        time_complexity="O(n^2) substrings", space_complexity="O(n)",
        failures=["Greedy longest-match-first fails on 'catsandog'",
                  "Scanning the word list linearly instead of using a set",
                  "Plain recursion re-explores the same suffix exponentially"],
        nudge="Mark every prefix that is breakable. A prefix is breakable if some earlier "
              "breakable prefix is followed by a real word.",
        visual="Positions light up left to right; each lit position can ignite later ones.",
        pseudocode="dp[end] = any(dp[start] and s[start:end] in pool)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="dp-decode-ways", title="The Ciphered Ledger", realm="dp_ruins", pattern="DP",
        difficulty="MEDIUM", family="dp_linear", secondary=["STRING"], profile_weight=Q,
        viz=VIZ_DP,
        statement="""
            `'A'` to `'Z'` map to `"1"` to `"26"`. Return how many ways the digit string
            decodes. A `'0'` cannot stand alone, and a leading `'0'` makes the whole string
            undecodable.
        """,
        fn_name="decode_ways", params="digits", reference=_decode_ways,
        canonical="""
            def decode_ways(digits):
                if not digits or digits[0] == "0":
                    return 0
                prev, cur = 1, 1
                for i in range(1, len(digits)):
                    nxt = 0
                    if digits[i] != "0":
                        nxt += cur                      # take one digit
                    if 10 <= int(digits[i - 1:i + 1]) <= 26:
                        nxt += prev                     # take two digits
                    prev, cur = cur, nxt
                return cur
        """,
        visible=[("two ways", ["226"]), ("one way", ["12"])],
        hidden=[("leading zero", ["06"]), ("internal zero", ["100"]),
                ("valid zero pair", ["10"]), ("long", ["11106"]),
                ("all ones", ["1111"])],
        edges=[("empty", [""]), ("single zero", ["0"])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Treating '0' as decodable on its own",
                  "Accepting '06' as a two-digit code — leading zeroes are invalid",
                  "Not returning 0 for an unreachable string"],
        nudge="Two choices per position, each with its own validity rule. Zeroes are where "
              "this problem hides its teeth.",
        visual="Positions light from one or two behind, but only when the code is legal.",
        pseudocode="nxt = (cur if digit != '0') + (prev if 10 <= two_digit <= 26)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="sec-detection-budget", title="Detection Budget", realm="dp_ruins", pattern="DP",
        difficulty="HARD", family="dp_knapsack", security=True, profile_weight=QS,
        viz=VIZ_DP,
        statement="""
            You may deploy detections. `costs[i]` is the compute budget detection `i`
            consumes and `values[i]` is its coverage score. Each detection may be deployed
            at most once.

            Return the greatest total coverage within `budget`.
        """,
        fn_name="max_coverage", params="costs, values, budget", reference=_budget_alerts,
        canonical="""
            def max_coverage(costs, values, budget):
                dp = [0] * (budget + 1)
                for cost, value in zip(costs, values):
                    for b in range(budget, cost - 1, -1):   # DESCENDING: each item once
                        dp[b] = max(dp[b], dp[b - cost] + value)
                return dp[budget]
        """,
        visible=[("classic", [[1, 3, 4, 5], [1, 4, 5, 7], 7]),
                 ("nothing fits", [[10], [99], 5])],
        hidden=[("exact fit", [[2, 3], [3, 4], 5]), ("zero budget", [[1], [5], 0]),
                ("one item", [[3], [10], 3]), ("no items", [[], [], 5])],
        edges=[("budget zero no items", [[], [], 0])],
        time_complexity="O(n · budget)", space_complexity="O(budget)",
        failures=["Iterating the budget ascending lets one detection be deployed many "
                  "times — that is the unbounded knapsack, a different problem",
                  "Greedy by value-per-cost is not optimal"],
        nudge="The loop direction is the entire difference between 'use once' and 'use "
              "many times'. Descending means each item is considered once.",
        visual="Budget tiles light up right to left so this round's gains cannot feed "
               "themselves.",
        pseudocode="for each item: for b from budget down to cost: dp[b] = max(dp[b], dp[b-cost]+value)",
        tags=["security", "transfer", "hard"],
    ))

    return P
