"""Non-implementation encounters: recognition, complexity, code reading, edge-case
traps, and the Testsmith Forge.

These exist because an interview is not only 'write the function'. Recognising the
family, predicting behaviour, naming the complexity and inventing the input that
breaks a solution are separately trainable skills — and each is separately scored.
"""
from __future__ import annotations

from ._base import mcq_problem, forge_problem

PATTERN_CHOICES = ["HASH MAP", "SLIDING WINDOW", "TWO POINTERS", "BFS", "DFS",
                   "STACK", "BINARY SEARCH", "DYNAMIC PROGRAMMING", "HEAP",
                   "PREFIX SUM", "SORTING", "RECURSION"]


def pattern_q(pid, title, statement, choices, answer, explanation, *,
              difficulty="EASY", realm="fields_of_syntax", security=False, seconds=45):
    return mcq_problem(id=pid, title=title, realm=realm, pattern="RECOGNITION",
                       difficulty=difficulty, statement=statement, choices=choices,
                       answer=answer, explanation=explanation,
                       encounter="PATTERN_ENCOUNTER", family="pattern_recognition",
                       security=security, seconds=seconds)


def complexity_q(pid, title, code, choices, answer, explanation, *,
                 difficulty="EASY", seconds=60):
    return mcq_problem(id=pid, title=title, realm="complexity_tower",
                       pattern="COMPLEXITY", difficulty=difficulty,
                       statement="What is the **time complexity** of this function in "
                                 "terms of `n`, the size of the input?",
                       code=code, choices=choices, answer=answer,
                       explanation=explanation, encounter="COMPLEXITY_DUEL",
                       family="big_o", seconds=seconds)


def reading_q(pid, title, code, statement, choices, answer, explanation, *,
              difficulty="EASY", realm="fields_of_syntax", seconds=75):
    return mcq_problem(id=pid, title=title, realm=realm, pattern="STRING",
                       difficulty=difficulty, statement=statement, code=code,
                       choices=choices, answer=answer, explanation=explanation,
                       encounter="CODE_READING", family="code_reading", seconds=seconds)


def trap_q(pid, title, code, choices, answer, explanation, *, difficulty="MEDIUM",
           seconds=90):
    return mcq_problem(id=pid, title=title, realm="debugging_dungeon",
                       pattern="TESTING", difficulty=difficulty,
                       statement="This implementation looks right. **Which input exposes "
                                 "the bug?**",
                       code=code, choices=choices, answer=answer,
                       explanation=explanation, encounter="EDGE_CASE_TRAP",
                       family="edge_cases", seconds=seconds)


def build() -> list:
    P: list = []

    # ---------------- PATTERN RECOGNITION -----------------------------------
    recog = [
        ("pr-contiguous-longest", "Reading the Signals I",
         "\"Find the **longest contiguous** subarray containing at most K distinct "
         "values.\"\n\nWhich family is this?",
         1, "'Contiguous' plus 'longest' plus a constraint that can be violated and "
            "repaired is the sliding-window signature. The window grows right and "
            "shrinks left."),
        ("pr-sorted-pair", "Reading the Signals II",
         "\"The array is **sorted**. Find two values summing to a target, using **O(1) "
         "extra space**.\"\n\nWhich family is this?",
         2, "Sorted input plus an O(1)-space requirement rules out a hash map and points "
            "straight at converging two pointers."),
        ("pr-shortest-grid", "Reading the Signals III",
         "\"Find the **shortest** path through an unweighted grid.\"\n\nWhich family?",
         3, "'Shortest' in an unweighted graph is BFS. DFS finds a path but has no reason "
            "to find the shortest one."),
        ("pr-most-recent", "Reading the Signals IV",
         "\"Implement undo. The **most recent** action is reverted first.\"\n\n"
         "Which structure?",
         5, "'Most recent first' is LIFO, which is a stack — in Python, a plain list."),
        ("pr-seen-before", "Reading the Signals V",
         "\"Given a stream of values, report the first value you have **already seen**.\"",
         0, "A membership question over a growing collection is a hash-based structure — "
            "a set here, since counts are not needed."),
        ("pr-count-ways", "Reading the Signals VI",
         "\"Count the number of distinct ways to reach step N taking 1 or 2 steps.\"",
         7, "Counting ways with overlapping subproblems is dynamic programming. The "
            "recursive form recomputes the same steps exponentially."),
        ("pr-top-k", "Reading the Signals VII",
         "\"Return the **K largest** elements of a stream of a million values.\"",
         8, "You need the extreme elements repeatedly, not a total order. A heap of size K "
            "is O(n log k); a full sort is O(n log n) and stores everything."),
        ("pr-range-sums", "Reading the Signals VIII",
         "\"Answer a million queries for the **sum of a range** of a fixed array.\"",
         9, "Many queries against unchanging data means precompute once. Prefix sums make "
            "every query a single subtraction."),
        ("pr-min-search-space", "Reading the Signals IX",
         "\"Find the **smallest capacity** such that the shipment fits in D days.\"",
         6, "'Smallest value such that a monotonic predicate holds' is binary search over "
            "the answer, not over an array."),
        ("pr-explore-all", "Reading the Signals X",
         "\"List **every** path from A to B in a graph without repeating a node.\"",
         4, "Enumerating all paths is DFS with backtracking — you must un-mark nodes on "
            "the way back up, which BFS does not naturally do."),
        ("pr-anagram-group", "Reading the Signals XI",
         "\"Group words that are rearrangements of each other.\"",
         0, "Anything of the form 'group items sharing a computable key' is a hash map "
            "keyed by that canonical form."),
        ("pr-merge-intervals", "Reading the Signals XII",
         "\"Merge overlapping meetings into consolidated blocks.\"",
         10, "Interval problems almost always begin by sorting on the start time; the "
             "merge is then a single linear pass."),
    ]
    for pid, title, statement, answer, explanation in recog:
        P.append(pattern_q(pid, title, statement, PATTERN_CHOICES, answer, explanation))

    P.append(pattern_q(
        "pr-sec-window", "Reading the Signals: Telemetry",
        "\"Find the **longest stretch** of consecutive authentication events involving at "
        "most K distinct identities.\"\n\nWhich family?",
        PATTERN_CHOICES, 1,
        "Strip the security vocabulary and this is 'longest contiguous run with at most K "
        "distinct values' — a sliding window. Recognising the shape underneath the story "
        "is the whole skill.",
        security=True, difficulty="MEDIUM"))

    P.append(pattern_q(
        "pr-sec-lateral", "Reading the Signals: Lateral Movement",
        "\"Find the **fewest hops** an attacker needs to reach the domain controller.\"",
        PATTERN_CHOICES, 3,
        "'Fewest hops' on an unweighted host graph is BFS. Attack-path enumeration would "
        "be DFS; shortest-path is not.",
        security=True, difficulty="MEDIUM"))

    P.append(pattern_q(
        "pr-disguised-fruit", "The Disguised Ward",
        "\"You walk a row of trees carrying two baskets, each holding one kind of fruit. "
        "You must pick from every tree you pass and may not skip. Maximise the fruit "
        "collected.\"\n\nThis problem mentions no window, no K and no distinct count. "
        "Which family is it?",
        PATTERN_CHOICES, 1,
        "'Two baskets' is 'at most 2 distinct'. 'May not skip' is 'contiguous'. This is "
        "the K-distinct sliding window in costume — and problems arrive in costume.",
        difficulty="MEDIUM", seconds=60))

    # ---------------- COMPLEXITY DUELS --------------------------------------
    LADDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(2^n)"]
    duels = [
        ("cx-single-loop", "The First Floor",
         "def total(nums):\n    out = 0\n    for value in nums:\n        out += value\n"
         "    return out\n", 2,
         "One pass over n elements, constant work each. O(n)."),
        ("cx-nested-loop", "The Second Floor",
         "def pairs(nums):\n    out = []\n    for i in range(len(nums)):\n"
         "        for j in range(i + 1, len(nums)):\n            out.append((i, j))\n"
         "    return out\n", 4,
         "The inner loop runs n-1, then n-2, and so on: n(n-1)/2 iterations, which is "
         "O(n^2). Starting at i+1 halves the constant but not the class."),
        ("cx-halving", "The Spiral Stair",
         "def steps(n):\n    count = 0\n    while n > 1:\n        n //= 2\n"
         "        count += 1\n    return count\n", 1,
         "Each iteration halves n, so the loop runs about log2(n) times. O(log n)."),
        ("cx-sort-then-scan", "The Sorted Hall",
         "def has_duplicate(nums):\n    nums = sorted(nums)\n"
         "    for i in range(1, len(nums)):\n        if nums[i] == nums[i - 1]:\n"
         "            return True\n    return False\n", 3,
         "The sort dominates at O(n log n); the scan is O(n). The total is the larger term."),
        ("cx-hash-lookup", "The Instant Vault",
         "def contains(pool, target):\n    return target in pool   # pool is a set\n", 0,
         "Set membership is O(1) on average. Note that `target in some_list` would be "
         "O(n) — the same syntax, a completely different cost."),
        ("cx-list-membership", "The Deceptive Vault",
         "def contains(items, target):\n    return target in items   # items is a LIST\n",
         2, "`in` on a list scans linearly. Identical syntax to the set version, O(n) "
            "instead of O(1). This is a very common hidden quadratic."),
        ("cx-count-in-loop", "The Hidden Quadratic",
         "def first_unique(s):\n    for i, ch in enumerate(s):\n"
         "        if s.count(ch) == 1:\n            return i\n    return -1\n", 4,
         "`s.count(ch)` is itself O(n), called once per character: O(n^2). The loop looks "
         "linear, which is exactly why this one gets missed."),
        ("cx-naive-fib", "The Branching Curse",
         "def fib(n):\n    if n < 2:\n        return n\n"
         "    return fib(n - 1) + fib(n - 2)\n", 5,
         "Each call spawns two more, and nothing is cached. O(2^n) — it stalls around "
         "n = 40."),
        ("cx-string-concat", "The Copying Scribe",
         "def join_all(parts):\n    out = \"\"\n    for part in parts:\n"
         "        out += part\n    return out\n", 4,
         "Python strings are immutable, so each `+=` copies everything accumulated so far. "
         "With n parts of similar length that is O(n^2). `\"\".join(parts)` is O(n)."),
        ("cx-two-sequential", "The Twin Halls",
         "def process(nums):\n    a = sum(nums)\n    b = max(nums) if nums else 0\n"
         "    return a + b\n", 2,
         "Two sequential O(n) passes is O(2n), which is still O(n). Sequential work adds; "
         "only nested work multiplies."),
        ("cx-binary-in-loop", "The Halving Choir",
         "import bisect\n\ndef lookup_all(sorted_pool, queries):\n"
         "    return [bisect.bisect_left(sorted_pool, q) for q in queries]\n"
         "# n = len(queries), and len(sorted_pool) is also n\n", 3,
         "n queries, each a binary search costing O(log n). O(n log n)."),
        ("cx-slice-in-loop", "The Copying Frame",
         "def windows(nums, k):\n"
         "    return [max(nums[i:i + k]) for i in range(len(nums) - k + 1)]\n"
         "# treat k as proportional to n\n", 4,
         "Each slice copies k elements and each `max` scans them, repeated about n times: "
         "O(n·k), which is O(n^2) when k grows with n. The monotonic deque makes it O(n)."),
        ("cx-set-build", "The Filling Vault",
         "def unique_count(nums):\n    return len(set(nums))\n", 2,
         "Building the set inserts n elements at O(1) average each. O(n)."),
        ("cx-dict-in-loop", "The Counted Hall",
         "def tally(items):\n    counts = {}\n    for item in items:\n"
         "        counts[item] = counts.get(item, 0) + 1\n    return counts\n", 2,
         "One pass, O(1) average dict operations per element. O(n)."),
    ]
    for pid, title, code, answer, explanation in duels:
        P.append(complexity_q(pid, title, code, LADDER, answer, explanation,
                              difficulty="MEDIUM" if answer in (4, 5) else "EASY"))

    P.append(mcq_problem(
        id="cx-space-tradeoff", title="The Complexity Wyrm", realm="complexity_tower",
        pattern="COMPLEXITY", difficulty="HARD", encounter="COMPLEXITY_DUEL",
        family="big_o", seconds=90,
        statement="Two Sum can be solved two ways. Which statement is **true**?",
        code="# A: sort, then converge two pointers\n"
             "# B: one pass with a dict of value -> index\n",
        choices=[
            "A is O(n log n) time / O(1) extra space; B is O(n) time / O(n) space",
            "Both are O(n) time; A uses less space",
            "A is O(n) time; B is O(n log n) time",
            "Both are O(n log n); the difference is only constant factors",
        ], answer=0,
        explanation="""
            A pays O(n log n) for the sort but needs no extra structure — and it destroys
            the original indices unless you carry them along. B is a single O(n) pass but
            stores up to n entries.

            The right answer depends on what was asked for. If the interviewer says 'O(1)
            extra space', B is disqualified regardless of being asymptotically faster.
            Say that trade-off out loud; it is a large part of what is being scored.
        """))

    # ---------------- CODE READING ------------------------------------------
    P.append(reading_q(
        "cr-mutable-default", "The Sticky Default",
        "def add(value, bucket=[]):\n    bucket.append(value)\n    return bucket\n\n"
        "print(add(1))\nprint(add(2))\n",
        "What does this print?",
        ["[1] then [1, 2]", "[1] then [2]", "[1] then [1]", "It raises an exception"],
        0,
        "The default list is created once, when the function is DEFINED, and is shared by "
        "every call that does not pass a bucket. This is the single most common Python "
        "interview gotcha."))

    P.append(reading_q(
        "cr-shallow-copy", "The Shared Row",
        "grid = [[0] * 3] * 2\ngrid[0][0] = 9\nprint(grid)\n",
        "What does this print?",
        ["[[9, 0, 0], [9, 0, 0]]", "[[9, 0, 0], [0, 0, 0]]",
         "[[9, 9, 9], [0, 0, 0]]", "It raises an exception"],
        0,
        "`[x] * 2` copies the reference, not the object. Both rows ARE the same list. "
        "Build grids with `[[0] * cols for _ in range(rows)]`.",
        difficulty="MEDIUM"))

    P.append(reading_q(
        "cr-late-binding", "The Deferred Lambda",
        "fns = [lambda: i for i in range(3)]\nprint([f() for f in fns])\n",
        "What does this print?",
        ["[2, 2, 2]", "[0, 1, 2]", "[3, 3, 3]", "It raises an exception"],
        0,
        "The lambdas capture the variable `i`, not its value at creation time. By the time "
        "any of them run, the loop has finished and `i` is 2. Bind it with a default "
        "argument: `lambda i=i: i`.",
        difficulty="MEDIUM"))

    P.append(reading_q(
        "cr-dict-order", "The Remembered Order",
        "d = {}\nd['b'] = 1\nd['a'] = 2\nprint(list(d))\n",
        "What does this print?",
        ["['b', 'a']", "['a', 'b']", "The order is undefined", "It raises an exception"],
        0,
        "Since Python 3.7 dicts preserve insertion order as a language guarantee. They are "
        "still not sorted — that is a different property, and interviewers ask about both."))

    P.append(reading_q(
        "cr-slice-copy", "The Detached Slice",
        "a = [1, 2, 3]\nb = a[:]\nb.append(4)\nprint(a, b)\n",
        "What does this print?",
        ["[1, 2, 3] [1, 2, 3, 4]", "[1, 2, 3, 4] [1, 2, 3, 4]",
         "[1, 2, 3] [4]", "It raises an exception"],
        0,
        "`a[:]` makes a shallow copy, so appending to `b` leaves `a` alone. Had the "
        "elements themselves been mutable, the copy would still share them."))

    P.append(reading_q(
        "cr-integer-division", "The Floored Quotient",
        "print(-7 // 2, -7 % 2, int(-7 / 2))\n",
        "What does this print?",
        ["-4 1 -3", "-3 -1 -3", "-4 -1 -4", "-3 1 -4"],
        0,
        "`//` floors toward negative infinity, so -7 // 2 is -4. Python's `%` follows, "
        "returning 1. `int()` truncates toward zero, giving -3. Any problem that says "
        "'truncate toward zero' needs `int(a / b)`, not `//`.",
        difficulty="MEDIUM"))

    P.append(reading_q(
        "cr-truthiness", "The Empty Oracle",
        "print(all([]), any([]), bool([0]), bool(0))\n",
        "What does this print?",
        ["True False True False", "False False True False",
         "True True True False", "False True False False"],
        0,
        "`all([])` is vacuously True and `any([])` is False. `[0]` is a non-empty list so "
        "it is truthy, even though its only element is falsy.",
        difficulty="MEDIUM"))

    P.append(reading_q(
        "cr-string-immutable", "The Unchangeable Rune",
        "s = 'abc'\ntry:\n    s[0] = 'z'\nexcept Exception as exc:\n"
        "    print(type(exc).__name__)\n",
        "What does this print?",
        ["TypeError", "IndexError", "ValueError", "Nothing; it succeeds"],
        0,
        "Strings are immutable, so item assignment raises TypeError. Build a list of "
        "characters when you need to mutate, then join."))

    P.append(reading_q(
        "cr-sort-stability", "The Stable Order",
        "pairs = [('b', 1), ('a', 1), ('c', 0)]\n"
        "print(sorted(pairs, key=lambda p: p[1]))\n",
        "What does this print?",
        ["[('c', 0), ('b', 1), ('a', 1)]", "[('c', 0), ('a', 1), ('b', 1)]",
         "[('a', 1), ('b', 1), ('c', 0)]", "The order among ties is undefined"],
        0,
        "Python's sort is stable: elements comparing equal keep their original relative "
        "order, so ('b', 1) stays ahead of ('a', 1). Stability is what makes multi-pass "
        "sorting work.",
        difficulty="MEDIUM"))

    P.append(reading_q(
        "cr-set-order", "The Unordered Vault",
        "s = {3, 1, 2}\nprint(sorted(s))\n",
        "What does this print?",
        ["[1, 2, 3]", "[3, 1, 2]", "{1, 2, 3}", "The order is undefined"],
        0,
        "A set has no order, which is exactly why `sorted()` is here. Returning a raw set "
        "from a function whose tests compare lists is a routine failure."))

    # ---------------- EDGE-CASE TRAPS ---------------------------------------
    P.append(trap_q(
        "et-average-empty", "The Mimic of Averages",
        "def average(nums):\n    return sum(nums) / len(nums)\n",
        ["[]", "[0]", "[-1, 1]", "[1000000]"],
        0,
        "An empty list gives `len(nums) == 0` and raises ZeroDivisionError. Every "
        "aggregate over a collection needs an empty-input answer decided up front."))

    P.append(trap_q(
        "et-max-empty", "The Hollow Maximum",
        "def largest(nums):\n    best = 0\n    for value in nums:\n"
        "        best = max(best, value)\n    return best\n",
        ["[-5, -2, -9]", "[]", "[0]", "[1, 2, 3]"],
        0,
        "Seeding `best` at 0 silently returns 0 for an all-negative list. The empty list "
        "also returns 0, which may or may not be correct — but the negatives case is "
        "unambiguously wrong."))

    P.append(trap_q(
        "et-rotate-zero", "The Motionless Wheel",
        "def rotate(items, k):\n    return items[-k:] + items[:-k]\n",
        ["items=[1,2,3], k=0", "items=[1,2,3], k=1", "items=[1,2,3], k=3",
         "items=[], k=2"],
        0,
        "With k = 0, `items[-0:]` is the WHOLE list and `items[:-0]` is empty, so the "
        "result duplicates everything: [1,2,3,1,2,3]... actually [1,2,3] + [] — the "
        "rotation silently does nothing while a k of 3 wraps wrongly too. Negative-zero "
        "slicing is a reliable trap."))

    P.append(trap_q(
        "et-window-off-by-one", "The Missing Frame",
        "def windows(nums, k):\n"
        "    return [nums[i:i + k] for i in range(len(nums) - k)]\n",
        ["nums=[1,2,3], k=2 (the last window is missing)", "nums=[], k=1",
         "nums=[1], k=1", "nums=[1,2], k=3"],
        0,
        "There are `n - k + 1` windows, not `n - k`. The last one is always dropped. This "
        "is the single most common off-by-one in windowing code."))

    P.append(trap_q(
        "et-duplicate-pair", "The Self-Pairing Rune",
        "def has_pair(nums, target):\n"
        "    for value in nums:\n"
        "        if target - value in nums:\n"
        "            return True\n"
        "    return False\n",
        ["nums=[3], target=6", "nums=[1,2], target=3", "nums=[], target=0",
         "nums=[1,1], target=2"],
        0,
        "`3` finds its own complement `3` in the list and reports a pair, though there is "
        "only one element. Any 'two elements' problem must exclude the element itself."))

    P.append(trap_q(
        "et-dict-mutation", "The Shifting Vault",
        "def drop_zeros(counts):\n"
        "    for key in counts:\n"
        "        if counts[key] == 0:\n"
        "            del counts[key]\n"
        "    return counts\n",
        ["{'a': 0}", "{'a': 1}", "{}", "{'a': 1, 'b': 2}"],
        0,
        "Deleting from a dict while iterating it raises RuntimeError: dictionary changed "
        "size during iteration. Iterate over `list(counts)` or build a new dict."))

    P.append(trap_q(
        "et-recursion-depth", "The Bottomless Descent",
        "def depth(node):\n"
        "    if node is None:\n        return 0\n"
        "    return 1 + max(depth(node.left), depth(node.right))\n",
        ["A tree that is one long left-leaning chain of 50,000 nodes",
         "An empty tree", "A single node", "A perfectly balanced tree of 50,000 nodes"],
        0,
        "The recursion is correct but its depth equals the tree height. A degenerate chain "
        "hits Python's recursion limit; a balanced tree of the same size is only about 17 "
        "deep and is fine."))

    P.append(trap_q(
        "et-float-equality", "The Imprecise Scale",
        "def is_third(value):\n    return value == 0.1 + 0.2\n",
        ["value=0.3", "value=0.30000000000000004", "value=0", "value=0.1"],
        0,
        "`0.1 + 0.2` is 0.30000000000000004 in binary floating point, so comparing against "
        "0.3 is False. Use `math.isclose` for float comparisons."))

    P.append(trap_q(
        "et-sort-key-none", "The Unsortable Column",
        "def sort_by_score(rows):\n"
        "    return sorted(rows, key=lambda r: r['score'])\n",
        ["A row where 'score' is None", "An empty list", "A single row",
         "Rows with equal scores"],
        0,
        "Comparing None to an int raises TypeError. Real data has holes; decide whether "
        "they sort first, last, or are filtered out before you sort."))

    P.append(trap_q(
        "et-in-place-mutation", "The Vandalised Input",
        "def top_three(nums):\n    nums.sort(reverse=True)\n    return nums[:3]\n",
        ["Any call where the caller still needs the original order of `nums`",
         "An empty list", "A list of length 2", "A list of identical values"],
        0,
        "`list.sort()` mutates the caller's list. The return value is right but the "
        "argument has been reordered behind the caller's back. Use `sorted(nums, ...)` "
        "unless in-place mutation was explicitly requested."))

    # ---------------- TEST FORGE --------------------------------------------
    P.append(forge_problem(
        id="tf-sum-list", title="The Testsmith's First Lesson", realm="debugging_dungeon",
        difficulty="EASY", fn_name="total",
        statement="""
            The Testsmith hands you four implementations of `total(nums)`, which should
            return the sum of a list. Three of them are **Mimics** — subtly wrong.

            Write a test suite that **accepts** the correct implementation and **rejects**
            every Mimic. Return a list of `(args, expected)` pairs; `args` must be a tuple.

            A Mimic that survives your suite is a bug that ships.
        """,
        correct="def total(nums):\n    return sum(nums)\n",
        mutants=[
            "def total(nums):\n    return sum(nums[1:])\n",          # drops the first
            "def total(nums):\n    return sum(v for v in nums if v > 0)\n",  # drops negatives
            "def total(nums):\n    return sum(nums) if nums else 1\n",       # empty is wrong
        ],
        nudge="One Mimic drops the first element, one ignores negatives, one lies about "
              "the empty list. What three inputs catch them?"))

    P.append(forge_problem(
        id="tf-max-list", title="Forging Against the Maximum", realm="debugging_dungeon",
        difficulty="MEDIUM", fn_name="largest",
        statement="""
            Four implementations of `largest(nums)`, which returns the largest value or
            `None` for an empty list. Three are Mimics.

            Write a suite that keeps the honest one and kills the rest.
        """,
        correct="def largest(nums):\n    return max(nums) if nums else None\n",
        mutants=[
            "def largest(nums):\n"
            "    best = 0\n"
            "    for v in nums:\n        best = max(best, v)\n    return best\n",
            "def largest(nums):\n    return max(nums) if nums else 0\n",
            "def largest(nums):\n    return sorted(nums)[-1] if nums else None\n"
            "    # correct-looking, but O(n log n) and crashes on generators\n",
        ],
        nudge="All-negative input exposes the zero-seeded Mimic. The empty list exposes "
              "the one returning 0."))

    P.append(forge_problem(
        id="tf-dedupe", title="Forging Against the Deduplicator", realm="debugging_dungeon",
        difficulty="MEDIUM", fn_name="dedupe",
        statement="""
            `dedupe(items)` removes duplicates while **preserving first-appearance order**.
            Three of the four implementations are Mimics.

            Kill them all.
        """,
        correct="def dedupe(items):\n"
                "    seen, out = set(), []\n"
                "    for v in items:\n"
                "        if v not in seen:\n            seen.add(v)\n            out.append(v)\n"
                "    return out\n",
        mutants=[
            "def dedupe(items):\n    return sorted(set(items))\n",
            "def dedupe(items):\n    return list(set(items))\n",
            "def dedupe(items):\n"
            "    out = []\n"
            "    for v in items:\n"
            "        if not out or out[-1] != v:\n            out.append(v)\n"
            "    return out\n",
        ],
        nudge="An input that is already sorted will not distinguish the sorting Mimics. "
              "The last Mimic only removes ADJACENT duplicates."))

    P.append(forge_problem(
        id="tf-is-palindrome", title="Forging Against the Mirror", realm="debugging_dungeon",
        difficulty="MEDIUM", fn_name="is_palindrome",
        statement="""
            `is_palindrome(s)` returns whether `s` reads the same both ways, **ignoring
            case and every non-alphanumeric character**. Three Mimics hide among four
            implementations.
        """,
        correct="def is_palindrome(s):\n"
                "    cleaned = [c.lower() for c in s if c.isalnum()]\n"
                "    return cleaned == cleaned[::-1]\n",
        mutants=[
            "def is_palindrome(s):\n    return s == s[::-1]\n",
            "def is_palindrome(s):\n"
            "    cleaned = [c for c in s if c.isalnum()]\n"
            "    return cleaned == cleaned[::-1]\n",
            "def is_palindrome(s):\n"
            "    cleaned = [c.lower() for c in s if c.isalpha()]\n"
            "    return cleaned == cleaned[::-1]\n",
        ],
        nudge="Three separate requirements — punctuation, case, digits — and each Mimic "
              "ignores exactly one."))

    P.append(forge_problem(
        id="tf-sec-threshold", title="Forging Against the Detection", realm="debugging_dungeon",
        difficulty="MEDIUM", fn_name="over_threshold",
        statement="""
            `over_threshold(counts, threshold)` returns the sorted keys whose count is
            **at least** the threshold. Three of four are Mimics — and in a detection
            rule, an off-by-one is a missed alert.
        """,
        correct="def over_threshold(counts, threshold):\n"
                "    return sorted(k for k, v in counts.items() if v >= threshold)\n",
        mutants=[
            "def over_threshold(counts, threshold):\n"
            "    return sorted(k for k, v in counts.items() if v > threshold)\n",
            "def over_threshold(counts, threshold):\n"
            "    return [k for k, v in counts.items() if v >= threshold]\n",
            "def over_threshold(counts, threshold):\n"
            "    return sorted(k for k, v in counts.items() if v >= threshold)[:1]\n",
        ],
        nudge="One is off by one at the boundary, one forgets to sort, one truncates. "
              "The unsorted Mimic only shows itself with input inserted out of order."))

    return P
