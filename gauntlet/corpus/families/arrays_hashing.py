"""Hashmap Highlands + Array Caverns: the load-bearing patterns of the Quora profile."""
from __future__ import annotations

from collections import Counter, defaultdict

from ._base import code_problem, dedent

Q = {"QUORA": 3.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 1.0}
QS = {"QUORA": 1.5, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}

VIZ_HASH = {"type": "hash_map", "caption": "Each key unlocks its own vault."}
VIZ_SCAN = {"type": "array_scan", "caption": "One pass, one dictionary."}


def _two_sum(nums, target):
    seen = {}
    for i, v in enumerate(nums):
        if target - v in seen:
            return [seen[target - v], i]
        seen[v] = i
    return []


def _two_sum_values(nums, target):
    seen = set()
    for v in nums:
        if target - v in seen:
            return sorted([target - v, v])
        seen.add(v)
    return []


def _count_pairs(nums, target):
    seen, total = Counter(), 0
    for v in nums:
        total += seen[target - v]
        seen[v] += 1
    return total


def _three_sum(nums):
    nums = sorted(nums)
    out, n = [], len(nums)
    for i in range(n - 2):
        if i and nums[i] == nums[i - 1]:
            continue
        lo, hi = i + 1, n - 1
        while lo < hi:
            s = nums[i] + nums[lo] + nums[hi]
            if s < 0:
                lo += 1
            elif s > 0:
                hi -= 1
            else:
                out.append([nums[i], nums[lo], nums[hi]])
                lo += 1
                while lo < hi and nums[lo] == nums[lo - 1]:
                    lo += 1
    return out


def _three_sum_target(nums, target):
    nums = sorted(nums)
    n = len(nums)
    for i in range(n - 2):
        lo, hi = i + 1, n - 1
        while lo < hi:
            s = nums[i] + nums[lo] + nums[hi]
            if s == target:
                return True
            lo += s < target
            hi -= s > target
    return False


def _group_anagrams(words):
    buckets = defaultdict(list)
    for w in words:
        buckets["".join(sorted(w))].append(w)
    return [sorted(g) for g in buckets.values()]


def _is_anagram(a, b):
    return Counter(a) == Counter(b)


def _first_unique(s):
    counts = Counter(s)
    for i, ch in enumerate(s):
        if counts[ch] == 1:
            return i
    return -1


def _top_k_frequent(nums, k):
    return [v for v, _ in Counter(nums).most_common(k)]


def _contains_duplicate(nums):
    return len(set(nums)) != len(nums)


def _close_duplicate(nums, k):
    last = {}
    for i, v in enumerate(nums):
        if v in last and i - last[v] <= k:
            return True
        last[v] = i
    return False


def _intersection(a, b):
    return sorted(set(a) & set(b))


def _subarray_sum_k(nums, k):
    counts, total, out = {0: 1}, 0, 0
    for v in nums:
        total += v
        out += counts.get(total - k, 0)
        counts[total] = counts.get(total, 0) + 1
    return out


def _pivot_index(nums):
    total, left = sum(nums), 0
    for i, v in enumerate(nums):
        if left == total - left - v:
            return i
        left += v
    return -1


def _range_sums(nums, queries):
    prefix = [0]
    for v in nums:
        prefix.append(prefix[-1] + v)
    return [prefix[hi + 1] - prefix[lo] for lo, hi in queries]


def _product_except_self(nums):
    n = len(nums)
    out = [1] * n
    run = 1
    for i in range(n):
        out[i] = run
        run *= nums[i]
    run = 1
    for i in range(n - 1, -1, -1):
        out[i] *= run
        run *= nums[i]
    return out


def _longest_consecutive(nums):
    pool, best = set(nums), 0
    for v in pool:
        if v - 1 in pool:
            continue
        length = 1
        while v + length in pool:
            length += 1
        best = max(best, length)
    return best


def _merge_intervals(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def _max_overlap(intervals):
    events = []
    for s, e in intervals:
        events.append((s, 1))
        events.append((e, -1))
    events.sort()
    cur = best = 0
    for _, delta in events:
        cur += delta
        best = max(best, cur)
    return best


def _majority(nums):
    count = candidate = 0
    for v in nums:
        if count == 0:
            candidate = v
        count += 1 if v == candidate else -1
    return candidate


def _sort_by_frequency(nums):
    counts = Counter(nums)
    return sorted(nums, key=lambda v: (-counts[v], v))


def _failed_logins(events, threshold):
    counts = Counter(user for user, ok in events if not ok)
    return sorted(u for u, c in counts.items() if c >= threshold)


def _ioc_hits(observed, feed):
    return sorted(set(observed) & set(feed))


def _pair_risk(scores, target):
    seen = set()
    for s in scores:
        if target - s in seen:
            return True
        seen.add(s)
    return False


def _first_repeated_asset(assets):
    seen = set()
    for a in assets:
        if a in seen:
            return a
        seen.add(a)
    return ""


def _alert_burst(counts, k):
    prefix, best = 0, 0
    window = 0
    for i, v in enumerate(counts):
        window += v
        if i >= k:
            window -= counts[i - k]
        if i >= k - 1:
            best = max(best, window)
    return best


def build() -> list:
    P: list = []

    P.append(code_problem(
        id="ah-two-sum-indices", title="The Twin Runes", realm="hashmap_highlands",
        pattern="HASH_MAP", difficulty="EASY", family="two_sum",
        source_type="REPORTED_INTERVIEW", company="Quora", year="reported pattern",
        provenance="Historically reported pattern for software-engineering screens at "
                   "many companies including Quora. Not a guarantee of any question.",
        profile_weight=Q, viz=VIZ_HASH,
        statement="""
            Two runes in a row sum to the seal's value. Return the **indices** of the
            two runes that add up to `target`, smaller index first.

            Exactly one valid pair exists. You may not reuse the same rune twice.

            The obvious approach checks every pair. The seal breaks only for a
            single-pass solution.
        """,
        fn_name="two_sum", params="nums, target", reference=_two_sum,
        starter_hint="return the two indices, smaller first",
        constraints=["2 <= len(nums) <= 100000", "-10^9 <= nums[i] <= 10^9",
                     "exactly one valid answer exists"],
        canonical="""
            def two_sum(nums, target):
                seen = {}
                for i, value in enumerate(nums):
                    if target - value in seen:
                        return [seen[target - value], i]
                    seen[value] = i
                return []
        """,
        visible=[("classic", [[2, 7, 11, 15], 9]), ("later pair", [[3, 2, 4], 6])],
        hidden=[("negatives", [[-3, 4, 3, 90], 0]), ("duplicate values", [[3, 3], 6]),
                ("long tail", [list(range(1, 60)) + [900], 959])],
        edges=[("same value twice", [[0, 0], 0]), ("large negatives", [[-10**9, 10**9, 5], 0])],
        perf=[("60k runes", [list(range(60000)), 119997])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Nested loops time out at 60k elements",
                  "Storing the value before checking lets a rune pair with itself",
                  "Returning values instead of indices"],
        nudge="You are asked 'have I already seen the number that completes this pair?' "
              "That is a membership question, and membership questions want a dict.",
        visual="Walk left to right. Above each rune write the complement you still need. "
               "The moment a rune matches a complement already on the wall, you are done.",
        pseudocode="""
            seen = {}                       # value -> index
            for i, value in nums:
                need = target - value
                if need in seen:
                    return [seen[need], i]
                seen[value] = i
        """,
        alternates=[{"name": "sort + two pointers",
                     "note": "O(n log n) and loses the original indices unless you "
                             "carry them along. Worse here.",
                     "complexity": "O(n log n)"}],
        variants=["ah-two-sum-values", "ah-two-sum-count", "sec-pair-risk"],
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="ah-two-sum-values", title="Echo of the Twin Runes", realm="hashmap_highlands",
        pattern="HASH_MAP", difficulty="EASY", family="two_sum",
        source_type="GENERATED_VARIANT", profile_weight=Q, viz=VIZ_HASH,
        statement="""
            The same seal, a different demand. Return the two **values** that sum to
            `target`, sorted ascending. Return `[]` if no pair exists.

            Note what changed: no pair is guaranteed, and indices no longer matter.
        """,
        fn_name="pair_summing_to", params="nums, target", reference=_two_sum_values,
        constraints=["0 <= len(nums) <= 100000"],
        canonical="""
            def pair_summing_to(nums, target):
                seen = set()
                for value in nums:
                    if target - value in seen:
                        return sorted([target - value, value])
                    seen.add(value)
                return []
        """,
        visible=[("classic", [[2, 7, 11, 15], 9]), ("no pair", [[1, 2, 3], 100])],
        hidden=[("negatives", [[-4, 1, 5, 9], 5]), ("zeroes", [[0, 0, 3], 0]),
                ("first wins", [[5, 5, 1, 9], 10])],
        edges=[("empty", [[], 5]), ("single", [[5], 10])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Forgetting the empty-input case", "Returning unsorted values"],
        nudge="Indices are gone, so a set is enough. What does that save you?",
        visual="Same single pass. You are only asking 'have I seen the complement', "
               "never 'where was it'.",
        pseudocode="""
            seen = set()
            for value in nums:
                if target - value in seen: return sorted pair
                seen.add(value)
            return []
        """,
        tags=["variant"],
    ))

    P.append(code_problem(
        id="ah-two-sum-count", title="Counting the Twin Seals", realm="hashmap_highlands",
        pattern="HASH_MAP", difficulty="MEDIUM", family="two_sum",
        source_type="GENERATED_VARIANT", profile_weight=Q, viz=VIZ_HASH,
        statement="""
            Now count **how many index pairs** `(i, j)` with `i < j` satisfy
            `nums[i] + nums[j] == target`.

            Duplicates matter. `[1, 1, 1]` with target `2` has three pairs, not one.
        """,
        fn_name="count_pairs", params="nums, target", reference=_count_pairs,
        constraints=["0 <= len(nums) <= 100000"],
        canonical="""
            def count_pairs(nums, target):
                from collections import Counter
                seen = Counter()
                total = 0
                for value in nums:
                    total += seen[target - value]
                    seen[value] += 1
                return total
        """,
        visible=[("two pairs", [[1, 5, 7, -1, 5], 6]), ("all identical", [[1, 1, 1], 2])],
        hidden=[("none", [[1, 2, 3], 99]), ("zeroes", [[0, 0, 0, 0], 0]),
                ("mixed signs", [[-2, 2, -2, 2], 0])],
        edges=[("empty", [[], 0]), ("single", [[3], 6])],
        perf=[("40k", [[1] * 40000, 2])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Counting each pair twice", "Using a set, which collapses duplicates",
                  "Incrementing the counter before scoring the pair"],
        nudge="A set forgets multiplicity. You need counts, not membership.",
        visual="For each new value, every earlier copy of its complement is a fresh pair. "
               "Add the count, then record yourself.",
        pseudocode="""
            seen = Counter()
            for value in nums:
                total += seen[target - value]     # score BEFORE recording
                seen[value] += 1
        """,
        tags=["variant"],
    ))

    P.append(code_problem(
        id="sec-pair-risk", title="Paired Risk Signature", realm="hashmap_highlands",
        pattern="HASH_MAP", difficulty="EASY", family="two_sum", security=True,
        profile_weight=QS, viz=VIZ_HASH,
        statement="""
            A detection rule fires when two transactions in the same session have risk
            scores that sum exactly to a known fraud signature.

            Given `scores` and a `target`, return `True` if any two distinct
            transactions sum to the signature.
        """,
        fn_name="has_risk_pair", params="scores, target", reference=_pair_risk,
        canonical="""
            def has_risk_pair(scores, target):
                seen = set()
                for score in scores:
                    if target - score in seen:
                        return True
                    seen.add(score)
                return False
        """,
        visible=[("hit", [[10, 40, 25, 60], 50]), ("miss", [[1, 2, 3], 99])],
        hidden=[("negative adjustment", [[-20, 70, 30], 50]), ("dupes", [[25, 25], 50])],
        edges=[("empty", [[], 0]), ("single cannot pair", [[25], 50])],
        time_complexity="O(n)", space_complexity="O(n)", cmp="bool",
        failures=["Letting one transaction pair with itself"],
        nudge="Identical shape to the Twin Runes. Only the story changed.",
        visual="Same single pass over a set.",
        pseudocode="seen = set(); for s: if target - s in seen: return True; seen.add(s)",
        tags=["security", "transfer"],
    ))

    P.append(code_problem(
        id="ah-three-sum", title="The Three-Sum Hydra", realm="array_caverns",
        pattern="TWO_POINTER", difficulty="MEDIUM", family="three_sum",
        secondary=["SORTING", "ARRAY"], boss=True, profile_weight=Q,
        source_type="REPORTED_INTERVIEW", company="Quora", year="reported pattern",
        provenance="Widely reported archetype across SWE screens. Historical pattern only.",
        viz={"type": "two_pointer", "caption": "Fix one head; two more close in."},
        statement="""
            Return every unique triplet `[a, b, c]` from `nums` with `a + b + c == 0`.

            Each triplet must be sorted ascending, and no triplet may repeat. The order
            of the triplets in your answer does not matter.

            The Hydra grows a new head for every duplicate you fail to skip.
        """,
        fn_name="three_sum", params="nums", reference=_three_sum, cmp="nested_set",
        constraints=["0 <= len(nums) <= 3000", "-10^5 <= nums[i] <= 10^5"],
        canonical="""
            def three_sum(nums):
                nums.sort()
                out, n = [], len(nums)
                for i in range(n - 2):
                    if i and nums[i] == nums[i - 1]:
                        continue                       # skip duplicate first values
                    lo, hi = i + 1, n - 1
                    while lo < hi:
                        total = nums[i] + nums[lo] + nums[hi]
                        if total < 0:
                            lo += 1
                        elif total > 0:
                            hi -= 1
                        else:
                            out.append([nums[i], nums[lo], nums[hi]])
                            lo += 1
                            while lo < hi and nums[lo] == nums[lo - 1]:
                                lo += 1
                return out
        """,
        visible=[("classic", [[-1, 0, 1, 2, -1, -4]]), ("no triplet", [[0, 1, 1]])],
        hidden=[("all zeroes", [[0, 0, 0, 0]]),
                ("many duplicates", [[-2, 0, 1, 1, 2, -1, -4, 2, -2]]),
                ("wide range", [[-5, 2, 3, -3, 1, 4, -1, 0]])],
        edges=[("empty", [[]]), ("two only", [[1, -1]]), ("all same nonzero", [[3, 3, 3, 3]])],
        perf=[("1500 values", [[(i % 200) - 100 for i in range(1500)]])],
        time_complexity="O(n^2)", space_complexity="O(n)",
        failures=["Triple nested loop times out",
                  "Duplicate triplets because the outer index never skips repeats",
                  "Deduplicating with a set of tuples works but is the slow way out",
                  "Moving only one pointer after finding a hit"],
        nudge="Sorting turns 'find two numbers summing to X' into a two-pointer sweep. "
              "Fix the first number, then sweep the rest.",
        visual="Sort the array. Plant a flag at index i. Two runners start just right of "
               "the flag and at the far end, walking toward each other: sum too small, "
               "left runner advances; too large, right runner retreats.",
        pseudocode="""
            sort(nums)
            for i in 0 .. n-3:
                if nums[i] == nums[i-1]: continue
                lo, hi = i+1, n-1
                while lo < hi:
                    total = nums[i] + nums[lo] + nums[hi]
                    total < 0 -> lo += 1
                    total > 0 -> hi -= 1
                    else      -> record; lo += 1; skip duplicates
        """,
        prerequisites=["ah-two-sum-indices"],
        variants=["ah-three-sum-target"],
        tags=["core", "quora", "boss"],
    ))

    P.append(code_problem(
        id="ah-three-sum-target", title="Hydra Reborn", realm="array_caverns",
        pattern="TWO_POINTER", difficulty="MEDIUM", family="three_sum",
        source_type="GENERATED_VARIANT", profile_weight=Q, cmp="bool",
        statement="""
            The Hydra returns wearing a different face. Return `True` if **any** three
            values in `nums` sum to `target`. You do not need the triplets themselves.

            The target is no longer zero, and duplicates no longer need skipping. What
            does that let you delete?
        """,
        fn_name="has_triplet", params="nums, target", reference=_three_sum_target,
        canonical="""
            def has_triplet(nums, target):
                nums.sort()
                n = len(nums)
                for i in range(n - 2):
                    lo, hi = i + 1, n - 1
                    while lo < hi:
                        total = nums[i] + nums[lo] + nums[hi]
                        if total == target:
                            return True
                        if total < target:
                            lo += 1
                        else:
                            hi -= 1
                return False
        """,
        visible=[("hit", [[1, 4, 45, 6, 10, 8], 22]), ("miss", [[1, 2, 3], 100])],
        hidden=[("negatives", [[-5, -2, 0, 3, 9], -7]), ("exact three", [[1, 2, 3], 6])],
        edges=[("too short", [[1, 2], 3]), ("empty", [[], 0])],
        time_complexity="O(n^2)", space_complexity="O(1)",
        failures=["Still skipping duplicates you no longer need to skip"],
        nudge="Same skeleton as the Hydra, minus every line that existed for deduplication.",
        visual="Fix, then converge.", pseudocode="sort; fix i; converge lo/hi on target",
        prerequisites=["ah-three-sum"], tags=["variant"],
    ))

    P.append(code_problem(
        id="ah-group-anagrams", title="The Scattered Scrolls", realm="stringwood_labyrinth",
        pattern="HASH_MAP", difficulty="MEDIUM", family="anagrams", secondary=["STRING"],
        source_type="REPORTED_INTERVIEW", company="Quora", year="reported pattern",
        provenance="Character-frequency grouping is a widely reported screen archetype.",
        profile_weight=Q, cmp="nested_set", viz=VIZ_HASH,
        statement="""
            Group the scrolls so that every group holds words that are anagrams of one
            another. Return a list of groups; each group sorted ascending; group order
            does not matter.
        """,
        fn_name="group_anagrams", params="words", reference=_group_anagrams,
        canonical="""
            def group_anagrams(words):
                from collections import defaultdict
                buckets = defaultdict(list)
                for word in words:
                    key = "".join(sorted(word))
                    buckets[key].append(word)
                return [sorted(group) for group in buckets.values()]
        """,
        visible=[("classic", [["eat", "tea", "tan", "ate", "nat", "bat"]]),
                 ("singletons", [["abc", "def"]])],
        hidden=[("empty strings", [["", "", "a"]]),
                ("case sensitive", [["Ab", "bA", "ab"]]),
                ("repeats", [["aab", "aba", "baa", "aab"]])],
        edges=[("empty list", [[]]), ("single word", [["solo"]])],
        perf=[("4000 scrolls", [[("abc" if i % 2 else "cba") + str(i % 50)
                                for i in range(4000)]])],
        time_complexity="O(n k log k)", space_complexity="O(n k)",
        failures=["Comparing every word against every other word — O(n^2 k)",
                  "Using an unsorted string as the bucket key",
                  "Forgetting that '' is a valid word"],
        nudge="Two words are anagrams exactly when they share a canonical form. "
              "What canonical form can you compute in one line?",
        visual="Each scroll is stamped with its sorted letters. Scrolls with matching "
               "stamps fall into the same vault.",
        pseudocode="""
            buckets = defaultdict(list)
            for word: buckets["".join(sorted(word))].append(word)
            return list of buckets.values()
        """,
        alternates=[{"name": "26-slot count tuple as key",
                     "note": "O(nk) instead of O(nk log k). Faster, uglier.",
                     "complexity": "O(n k)"}],
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="ah-valid-anagram", title="Mirror Words", realm="stringwood_labyrinth",
        pattern="HASH_MAP", difficulty="EASY", family="anagrams", secondary=["STRING"],
        profile_weight=Q, cmp="bool",
        statement="Return `True` if `b` is an anagram of `a` — same characters, same counts.",
        fn_name="is_anagram", params="a, b", reference=_is_anagram,
        canonical="""
            def is_anagram(a, b):
                from collections import Counter
                return Counter(a) == Counter(b)
        """,
        visible=[("yes", ["anagram", "nagaram"]), ("no", ["rat", "car"])],
        hidden=[("length differs", ["a", "ab"]), ("unicode", ["héllo", "ollhé"]),
                ("repeats", ["aabb", "bbaa"])],
        edges=[("both empty", ["", ""]), ("one empty", ["", "a"])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Comparing sorted strings is O(n log n) — correct but slower",
                  "Assuming equal length"],
        nudge="Same characters, same counts. Python has a class for exactly that.",
        visual="Two frequency tables laid side by side must match cell for cell.",
        pseudocode="return Counter(a) == Counter(b)", tags=["core"],
    ))

    P.append(code_problem(
        id="ah-first-unique", title="The Lone Glyph", realm="stringwood_labyrinth",
        pattern="HASH_MAP", difficulty="EASY", family="frequency", secondary=["STRING"],
        profile_weight=Q,
        statement="""
            Return the index of the first character in `s` that appears exactly once.
            Return `-1` if every character repeats.
        """,
        fn_name="first_unique_char", params="s", reference=_first_unique,
        canonical="""
            def first_unique_char(s):
                from collections import Counter
                counts = Counter(s)
                for i, ch in enumerate(s):
                    if counts[ch] == 1:
                        return i
                return -1
        """,
        visible=[("middle", ["leetcode"]), ("later", ["loveleetcode"])],
        hidden=[("none unique", ["aabb"]), ("first is unique", ["zabb"]),
                ("spaces count", ["a b a"])],
        edges=[("empty", [""]), ("single", ["x"])],
        perf=[("100k chars", ["ab" * 50000])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Calling s.count(ch) inside the loop makes it O(n^2)",
                  "Returning the character instead of the index"],
        nudge="Two passes beat one clever pass here: count everything, then scan in order.",
        visual="First pass fills the tally board. Second pass reads left to right until a "
               "tally of exactly one.",
        pseudocode="counts = Counter(s); for i, ch: if counts[ch] == 1: return i; return -1",
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-top-k-frequent", title="Loudest Voices", realm="hashmap_highlands",
        pattern="HEAP", difficulty="MEDIUM", family="top_k", secondary=["HASH_MAP", "SORTING"],
        profile_weight=Q, cmp="set",
        statement="""
            Return the `k` most frequent values in `nums`. Ties may be broken any way you
            like — the order of your answer does not matter.
        """,
        fn_name="top_k_frequent", params="nums, k", reference=_top_k_frequent,
        canonical="""
            def top_k_frequent(nums, k):
                from collections import Counter
                import heapq
                counts = Counter(nums)
                return heapq.nlargest(k, counts, key=counts.get)
        """,
        visible=[("classic", [[1, 1, 1, 2, 2, 3], 2]), ("single", [[1], 1])],
        hidden=[("all distinct", [[5, 6, 7], 2]), ("k equals n", [[1, 2, 2, 3], 3]),
                ("negatives", [[-1, -1, 2], 1])],
        edges=[("k is zero", [[1, 2], 0])],
        perf=[("50k values", [[i % 500 for i in range(50000)], 5])],
        time_complexity="O(n log k)", space_complexity="O(n)",
        failures=["Fully sorting all counts is O(n log n) — acceptable but not optimal",
                  "Forgetting k == 0"],
        nudge="You need the top few, not a total order. That is a heap's job.",
        visual="Counts pour into a small heap that only ever keeps the k tallest.",
        pseudocode="counts = Counter(nums); return heapq.nlargest(k, counts, key=counts.get)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-contains-duplicate", title="Twice-Struck Rune", realm="fields_of_syntax",
        pattern="SET", difficulty="TUTORIAL", family="dedupe", cmp="bool",
        profile_weight=Q,
        statement="Return `True` if any value appears more than once in `nums`.",
        fn_name="contains_duplicate", params="nums", reference=_contains_duplicate,
        canonical="""
            def contains_duplicate(nums):
                return len(set(nums)) != len(nums)
        """,
        visible=[("dupe", [[1, 2, 3, 1]]), ("clean", [[1, 2, 3]])],
        hidden=[("all same", [[7, 7, 7]]), ("negatives", [[-1, 1, -1]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Nested loops"],
        nudge="A set collapses duplicates. Compare the sizes.",
        visual="Pour the list into a set and watch it shrink.",
        pseudocode="return len(set(nums)) != len(nums)", tags=["tutorial"],
    ))

    P.append(code_problem(
        id="ah-nearby-duplicate", title="Echo Within K Paces", realm="hashmap_highlands",
        pattern="HASH_MAP", difficulty="EASY", family="dedupe", cmp="bool",
        profile_weight=Q,
        statement="""
            Return `True` if `nums` contains two equal values whose indices differ by at
            most `k`.
        """,
        fn_name="has_nearby_duplicate", params="nums, k", reference=_close_duplicate,
        canonical="""
            def has_nearby_duplicate(nums, k):
                last_seen = {}
                for i, value in enumerate(nums):
                    if value in last_seen and i - last_seen[value] <= k:
                        return True
                    last_seen[value] = i
                return False
        """,
        visible=[("close", [[1, 2, 3, 1], 3]), ("too far", [[1, 2, 3, 1], 2])],
        hidden=[("adjacent", [[1, 1], 1]), ("k zero", [[1, 1], 0]),
                ("later pair closer", [[1, 2, 1, 1], 1])],
        edges=[("empty", [[], 3]), ("single", [[1], 5])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Keeping the first index instead of the most recent one",
                  "Off-by-one on the `<= k` comparison"],
        nudge="Only the most recent sighting of a value can ever be the closest.",
        visual="Each value remembers where you last saw it. Overwrite, never append.",
        pseudocode="last = {}; for i, v: if v in last and i-last[v] <= k: True; last[v] = i",
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-subarray-sum-k", title="The Prefix Ledger", realm="array_caverns",
        pattern="PREFIX_SUM", difficulty="MEDIUM", family="prefix_sum",
        secondary=["HASH_MAP"], profile_weight=Q,
        viz={"type": "prefix_sum", "caption": "Running totals remember every checkpoint."},
        statement="""
            Count the contiguous subarrays of `nums` whose values sum to exactly `k`.

            Values may be negative, so you cannot slide a window here.
        """,
        fn_name="subarray_sum", params="nums, k", reference=_subarray_sum_k,
        canonical="""
            def subarray_sum(nums, k):
                counts = {0: 1}          # one empty prefix, sum zero
                running = 0
                found = 0
                for value in nums:
                    running += value
                    found += counts.get(running - k, 0)
                    counts[running] = counts.get(running, 0) + 1
                return found
        """,
        visible=[("two", [[1, 1, 1], 2]), ("one", [[1, 2, 3], 3])],
        hidden=[("negatives", [[1, -1, 0], 0]), ("zeros", [[0, 0, 0], 0]),
                ("whole array", [[3, 4, 7], 14]), ("none", [[1, 2, 3], 99])],
        edges=[("empty", [[], 0]), ("single hit", [[5], 5])],
        perf=[("40k", [[1] * 40000, 3])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Sliding window fails once negatives appear",
                  "Forgetting to seed the map with {0: 1}",
                  "O(n^2) double loop times out"],
        nudge="sum(i..j) == prefix[j] - prefix[i-1]. Rearrange that for what you want.",
        visual="Walk the array keeping a running total. At each step ask how many earlier "
               "checkpoints were exactly k below where you stand now.",
        pseudocode="""
            counts = {0: 1}; running = 0; found = 0
            for value in nums:
                running += value
                found += counts.get(running - k, 0)
                counts[running] += 1
        """,
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="ah-pivot-index", title="The Balanced Stone", realm="array_caverns",
        pattern="PREFIX_SUM", difficulty="EASY", family="prefix_sum", profile_weight=Q,
        statement="""
            Return the leftmost index where the sum of everything to its left equals the
            sum of everything to its right. Return `-1` if no such index exists.
        """,
        fn_name="pivot_index", params="nums", reference=_pivot_index,
        canonical="""
            def pivot_index(nums):
                total = sum(nums)
                left = 0
                for i, value in enumerate(nums):
                    if left == total - left - value:
                        return i
                    left += value
                return -1
        """,
        visible=[("middle", [[1, 7, 3, 6, 5, 6]]), ("none", [[1, 2, 3]])],
        hidden=[("index zero", [[2, 1, -1]]), ("negatives", [[-1, -1, -1, 0, 1, 1]]),
                ("last index", [[1, -1, 0]])],
        edges=[("empty", [[]]), ("single", [[7]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Recomputing the right-hand sum inside the loop — O(n^2)",
                  "Including the pivot itself on one side"],
        nudge="One total, one running left sum. The right side is arithmetic.",
        visual="A stone on a beam: left weight, pivot, right weight.",
        pseudocode="total = sum(nums); left = 0; for i,v: if left == total-left-v: return i",
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-range-sums", title="Ledger Queries", realm="array_caverns",
        pattern="PREFIX_SUM", difficulty="EASY", family="prefix_sum", profile_weight=Q,
        statement="""
            Answer many range-sum queries over a fixed array. Each query is
            `[lo, hi]` inclusive. Return the answers in query order.

            There can be far more queries than array elements.
        """,
        fn_name="range_sums", params="nums, queries", reference=_range_sums,
        canonical="""
            def range_sums(nums, queries):
                prefix = [0]
                for value in nums:
                    prefix.append(prefix[-1] + value)
                return [prefix[hi + 1] - prefix[lo] for lo, hi in queries]
        """,
        visible=[("basic", [[1, 2, 3, 4], [[0, 1], [1, 3], [0, 3]]]),
                 ("single cells", [[5, 6], [[0, 0], [1, 1]]])],
        hidden=[("repeated query", [[1, 2, 3], [[0, 2]] * 5]),
                ("negatives", [[-1, 4, -2], [[0, 2], [1, 2]]])],
        edges=[("no queries", [[1, 2, 3], []])],
        perf=[("20k queries", [list(range(500)), [[0, 499]] * 20000])],
        time_complexity="O(n + q)", space_complexity="O(n)",
        failures=["Summing the slice per query is O(n*q)",
                  "Off-by-one on the inclusive upper bound"],
        nudge="Pay once up front so every query becomes a single subtraction.",
        visual="Cumulative milestones along a road; any leg is the difference of two.",
        pseudocode="prefix[i+1] = prefix[i] + nums[i]; answer = prefix[hi+1] - prefix[lo]",
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-product-except-self", title="The Excluded Rune", realm="array_caverns",
        pattern="ARRAY", difficulty="MEDIUM", family="prefix_sum", profile_weight=Q,
        statement="""
            Return an array where each position holds the product of every **other**
            value in `nums`.

            You may not use division — one zero in the input would destroy it.
        """,
        fn_name="product_except_self", params="nums", reference=_product_except_self,
        canonical="""
            def product_except_self(nums):
                n = len(nums)
                out = [1] * n
                running = 1
                for i in range(n):              # everything to the left
                    out[i] = running
                    running *= nums[i]
                running = 1
                for i in range(n - 1, -1, -1):  # everything to the right
                    out[i] *= running
                    running *= nums[i]
                return out
        """,
        visible=[("classic", [[1, 2, 3, 4]]), ("with zero", [[-1, 1, 0, -3, 3]])],
        hidden=[("two zeros", [[0, 0, 2]]), ("negatives", [[-1, -2, -3]]),
                ("ones", [[1, 1, 1]])],
        edges=[("single", [[5]]), ("empty", [[]])],
        # values kept near 1 so the answer stays a machine-sized integer
        perf=[("50k", [[1] * 49997 + [2, 3, 2]])],
        time_complexity="O(n)", space_complexity="O(1) extra",
        failures=["Dividing the total product breaks on zeros",
                  "Nested loops time out", "Mishandling two or more zeros"],
        nudge="Every answer is (product of the left side) times (product of the right side).",
        visual="Two sweeps: one left-to-right laying down left products, one right-to-left "
               "multiplying the right products in.",
        pseudocode="""
            pass 1 left -> right: out[i] = running_left; running_left *= nums[i]
            pass 2 right -> left: out[i] *= running_right; running_right *= nums[i]
        """,
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="ah-longest-consecutive", title="The Unbroken Chain", realm="hashmap_highlands",
        pattern="SET", difficulty="MEDIUM", family="set_ops", profile_weight=Q,
        statement="""
            Return the length of the longest run of consecutive integers present in
            `nums`. The values are unsorted and may repeat.

            Sorting works and is O(n log n). There is an O(n) way.
        """,
        fn_name="longest_consecutive", params="nums", reference=_longest_consecutive,
        canonical="""
            def longest_consecutive(nums):
                pool = set(nums)
                best = 0
                for value in pool:
                    if value - 1 in pool:
                        continue            # not the start of a run
                    length = 1
                    while value + length in pool:
                        length += 1
                    best = max(best, length)
                return best
        """,
        visible=[("classic", [[100, 4, 200, 1, 3, 2]]),
                 ("with duplicates", [[0, 3, 7, 2, 5, 8, 4, 6, 0, 1]])],
        hidden=[("negatives", [[-3, -2, -1, 5]]), ("all same", [[9, 9, 9]]),
                ("two runs", [[1, 2, 10, 11, 12]])],
        edges=[("empty", [[]]), ("single", [[42]])],
        perf=[("40k", [list(range(40000))])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Extending every value makes it O(n^2)",
                  "Forgetting to only start runs at a true run start"],
        nudge="Only start counting from a value whose predecessor is absent. That single "
              "guard is what makes the whole thing linear.",
        visual="Each value asks 'is there a link to my left?'. Only chain heads walk right.",
        pseudocode="""
            pool = set(nums)
            for v in pool:
                if v-1 in pool: continue
                length = 1; while v+length in pool: length += 1
                best = max(best, length)
        """,
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-merge-intervals", title="The Overlapping Wards", realm="array_caverns",
        pattern="INTERVALS", difficulty="MEDIUM", family="intervals",
        secondary=["SORTING"], profile_weight=Q, cmp="exact",
        statement="""
            Merge all overlapping intervals and return the result sorted by start.
            Intervals that merely touch (`[1,4]` and `[4,5]`) count as overlapping.
        """,
        fn_name="merge_intervals", params="intervals", reference=_merge_intervals,
        canonical="""
            def merge_intervals(intervals):
                out = []
                for start, end in sorted(intervals):
                    if out and start <= out[-1][1]:
                        out[-1][1] = max(out[-1][1], end)
                    else:
                        out.append([start, end])
                return out
        """,
        visible=[("classic", [[[1, 3], [2, 6], [8, 10], [15, 18]]]),
                 ("touching", [[[1, 4], [4, 5]]])],
        hidden=[("unsorted input", [[[5, 6], [1, 3], [2, 4]]]),
                ("fully contained", [[[1, 10], [2, 3], [4, 5]]]),
                ("no overlap", [[[1, 2], [3, 4]]])],
        edges=[("empty", [[]]), ("single", [[[1, 2]]]), ("identical", [[[1, 2], [1, 2]]])],
        perf=[("20k intervals", [[[i, i + 1] for i in range(0, 40000, 2)]])],
        time_complexity="O(n log n)", space_complexity="O(n)",
        failures=["Not sorting first", "Using `end` instead of max(end, previous end) — "
                  "a fully contained interval then truncates the merged one",
                  "Treating touching intervals as disjoint"],
        nudge="Sort by start. Then you only ever compare against the last merged interval.",
        visual="Wards laid on a timeline; each new ward either extends the current one or "
               "begins a new one.",
        pseudocode="""
            for start, end in sorted(intervals):
                if out and start <= out[-1][1]: out[-1][1] = max(out[-1][1], end)
                else: out.append([start, end])
        """,
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="ah-max-overlap", title="Peak Conjunction", realm="array_caverns",
        pattern="INTERVALS", difficulty="MEDIUM", family="intervals",
        secondary=["SORTING"], profile_weight=Q,
        statement="""
            Given intervals `[start, end)`, return the largest number of intervals active
            at the same instant. An interval ending exactly when another begins does not
            overlap it.
        """,
        fn_name="max_overlap", params="intervals", reference=_max_overlap,
        canonical="""
            def max_overlap(intervals):
                events = []
                for start, end in intervals:
                    events.append((start, 1))
                    events.append((end, -1))
                events.sort()          # -1 sorts before +1 at equal times
                current = best = 0
                for _, delta in events:
                    current += delta
                    best = max(best, current)
                return best
        """,
        visible=[("three deep", [[[0, 30], [5, 10], [15, 20]]]),
                 ("no overlap", [[[7, 10], [2, 4]]])],
        hidden=[("touching", [[[1, 5], [5, 9]]]), ("identical", [[[1, 5], [1, 5], [1, 5]]]),
                ("nested", [[[1, 100], [2, 3], [4, 5], [2, 90]]])],
        edges=[("empty", [[]]), ("single", [[[1, 2]]])],
        time_complexity="O(n log n)", space_complexity="O(n)",
        failures=["Sorting ends after starts at the same timestamp inflates the peak",
                  "Comparing every pair — O(n^2)"],
        nudge="Forget intervals. Think of +1 at every start and -1 at every end, then walk "
              "the timeline.",
        visual="A sweep line crosses the timeline; a counter rises and falls.",
        pseudocode="events = [(s,+1),(e,-1)]; sort; running max of the prefix sum",
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-majority", title="The Sovereign Value", realm="array_caverns",
        pattern="ARRAY", difficulty="EASY", family="counting", profile_weight=Q,
        statement="""
            One value appears more than `len(nums) // 2` times. Return it.

            A dictionary solves this in O(n) time and O(n) space. There is an O(1)-space
            answer worth knowing.
        """,
        fn_name="majority_element", params="nums", reference=_majority,
        canonical="""
            def majority_element(nums):
                count = 0
                candidate = None
                for value in nums:                 # Boyer-Moore vote
                    if count == 0:
                        candidate = value
                    count += 1 if value == candidate else -1
                return candidate
        """,
        visible=[("simple", [[3, 2, 3]]), ("longer", [[2, 2, 1, 1, 1, 2, 2]])],
        hidden=[("all same", [[7, 7, 7]]), ("negatives", [[-1, -1, 2]]),
                ("exact majority", [[1, 1, 1, 2, 2]])],
        edges=[("single", [[5]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Assuming the array is sorted", "Assuming a majority always exists "
                  "when the guarantee is removed"],
        nudge="Pair off every unlike element. Whatever survives is the majority.",
        visual="Soldiers of the same banner cancel soldiers of every other banner one for "
               "one. The last banner standing wins.",
        pseudocode="count == 0 -> adopt candidate; same -> count += 1; else -> count -= 1",
        tags=["core"],
    ))

    P.append(code_problem(
        id="ah-sort-by-frequency", title="Ordered by Clamour", realm="hashmap_highlands",
        pattern="SORTING", difficulty="EASY", family="counting",
        secondary=["HASH_MAP"], profile_weight=Q,
        statement="""
            Sort `nums` so the most frequent values come first. Values with equal
            frequency are ordered ascending. Every occurrence is kept.
        """,
        fn_name="sort_by_frequency", params="nums", reference=_sort_by_frequency,
        canonical="""
            def sort_by_frequency(nums):
                from collections import Counter
                counts = Counter(nums)
                return sorted(nums, key=lambda value: (-counts[value], value))
        """,
        visible=[("classic", [[1, 1, 2, 2, 2, 3]]), ("tie", [[2, 3, 1]])],
        hidden=[("negatives", [[-1, -1, 3, 3, 2]]), ("all same", [[4, 4, 4]])],
        edges=[("empty", [[]]), ("single", [[9]])],
        time_complexity="O(n log n)", space_complexity="O(n)",
        failures=["Sorting the unique values and forgetting to expand the counts",
                  "Wrong tie-break direction"],
        nudge="A tuple key sorts on the first element, then the second. Negate to reverse "
              "just one of them.",
        visual="Two-level sort: frequency descending, then value ascending.",
        pseudocode="sorted(nums, key=lambda v: (-counts[v], v))",
        tags=["core"],
    ))

    # -- security transfer skins ------------------------------------------------
    P.append(code_problem(
        id="sec-failed-logins", title="Brute-Force Ledger", realm="hashmap_highlands",
        pattern="HASH_MAP", difficulty="EASY", family="counting", security=True,
        profile_weight=QS, cmp="exact", viz=VIZ_HASH,
        statement="""
            `events` is a list of `[identity, succeeded]` authentication records.
            Return the sorted list of identities with at least `threshold` **failed**
            authentications.
        """,
        fn_name="brute_force_candidates", params="events, threshold",
        reference=_failed_logins,
        canonical="""
            def brute_force_candidates(events, threshold):
                from collections import Counter
                failures = Counter(user for user, ok in events if not ok)
                return sorted(user for user, count in failures.items()
                              if count >= threshold)
        """,
        visible=[("one candidate", [[["alice", False], ["alice", False],
                                     ["bob", True], ["alice", False]], 3]),
                 ("none", [[["alice", True], ["bob", True]], 1])],
        hidden=[("successes ignored", [[["a", False], ["a", True], ["a", False]], 2]),
                ("two candidates", [[["a", False], ["b", False]], 1]),
                ("exact threshold", [[["a", False], ["a", False]], 2])],
        edges=[("empty", [[], 1]), ("threshold zero counts nobody with no failures",
                                    [[["a", True]], 0])],
        time_complexity="O(n log n)", space_complexity="O(u)",
        failures=["Counting successes as failures", "Using > instead of >=",
                  "Returning an unsorted list"],
        nudge="Filter first, count second. Counter takes any iterable.",
        visual="One vault per identity; only failures increment it.",
        pseudocode="Counter(user for user, ok in events if not ok); filter >= threshold",
        tags=["security", "transfer"],
    ))

    P.append(code_problem(
        id="sec-ioc-hits", title="Indicator Crossfire", realm="hashmap_highlands",
        pattern="SET", difficulty="TUTORIAL", family="set_ops", security=True,
        profile_weight=QS, cmp="exact",
        statement="""
            Return the sorted indicators that appear in both the `observed` telemetry and
            the threat-intel `feed`. Duplicates collapse.
        """,
        fn_name="indicator_hits", params="observed, feed", reference=_ioc_hits,
        canonical="""
            def indicator_hits(observed, feed):
                return sorted(set(observed) & set(feed))
        """,
        visible=[("two hits", [["1.1.1.1", "8.8.8.8", "1.1.1.1"], ["1.1.1.1", "9.9.9.9"]]),
                 ("no hits", [["a"], ["b"]])],
        hidden=[("all hit", [["a", "b"], ["b", "a"]]), ("dupes in feed", [["a"], ["a", "a"]])],
        edges=[("empty observed", [[], ["a"]]), ("both empty", [[], []])],
        time_complexity="O(n + m)", space_complexity="O(n + m)",
        failures=["Nested loop over both lists is O(n*m) and will not hold at feed scale",
                  "Forgetting to deduplicate"],
        nudge="Membership at scale is a set question, always.",
        visual="Two circles overlap; keep the intersection.",
        pseudocode="return sorted(set(observed) & set(feed))",
        tags=["security", "transfer", "tutorial"],
    ))

    P.append(code_problem(
        id="sec-first-repeat-asset", title="The Returning Host", realm="hashmap_highlands",
        pattern="SET", difficulty="EASY", family="dedupe", security=True,
        profile_weight=QS,
        statement="""
            Return the first asset identifier that appears twice in the connection log,
            or `""` if every asset is unique.
        """,
        fn_name="first_repeated_asset", params="assets", reference=_first_repeated_asset,
        canonical="""
            def first_repeated_asset(assets):
                seen = set()
                for asset in assets:
                    if asset in seen:
                        return asset
                    seen.add(asset)
                return ""
        """,
        visible=[("repeat", [["h1", "h2", "h1", "h3"]]), ("none", [["h1", "h2"]])],
        hidden=[("immediate", [["h1", "h1"]]), ("last pair", [["a", "b", "c", "a"]])],
        edges=[("empty", [[]]), ("single", [["only"]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Returning the first duplicated value by count rather than by "
                  "second-appearance order"],
        nudge="'First' means first *second* sighting, so check before you record.",
        visual="A ledger you consult before you write.",
        pseudocode="seen = set(); for a: if a in seen: return a; seen.add(a)",
        tags=["security", "transfer"],
    ))

    P.append(code_problem(
        id="sec-alert-burst", title="Burst Detection", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="EASY", family="fixed_window",
        security=True, profile_weight=QS,
        viz={"type": "sliding_window", "caption": "A fixed frame slides across the minutes."},
        statement="""
            `counts[i]` is the number of alerts raised in minute `i`. Return the largest
            total across any `k` consecutive minutes.

            If `k` exceeds the log length, return the total of everything.
        """,
        fn_name="max_alert_burst", params="counts, k", reference=_alert_burst,
        canonical="""
            def max_alert_burst(counts, k):
                window = 0
                best = 0
                for i, value in enumerate(counts):
                    window += value
                    if i >= k:
                        window -= counts[i - k]
                    if i >= k - 1:
                        best = max(best, window)
                return best
        """,
        visible=[("burst at end", [[1, 2, 0, 9, 9], 2]), ("flat", [[1, 1, 1, 1], 2])],
        hidden=[("k equals length", [[3, 1, 2], 3]), ("k larger than log", [[3, 1], 5]),
                ("zeros", [[0, 0, 0], 2])],
        edges=[("empty", [[], 3]), ("k is one", [[4, 9, 2], 1])],
        perf=[("100k minutes", [[i % 7 for i in range(100000)], 60])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Recomputing sum(counts[i:i+k]) per position is O(n*k)",
                  "Off-by-one when the window first becomes full"],
        nudge="Add the entering minute, subtract the leaving minute. Never re-add the middle.",
        visual="A glowing frame of width k slides right; one value enters, one leaves.",
        pseudocode="window += counts[i]; if i >= k: window -= counts[i-k]; track best",
        tags=["security", "transfer"],
    ))

    return P
