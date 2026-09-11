"""Sliding Window Marsh. The frame expands right; when the ward breaks it contracts left."""
from __future__ import annotations

from collections import Counter, defaultdict, deque

from ._base import code_problem

Q = {"PRACTICAL": 3.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 1.0}
QS = {"PRACTICAL": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}
VIZ = {"type": "sliding_window", "caption": "LEFT, RIGHT, COUNTS, CONSTRAINT, BEST."}

PSEUDO = """
left = 0
for right in range(len(data)):
    add(data[right])
    while window_is_invalid():
        remove(data[left])
        left += 1
    best = max(best, right - left + 1)
"""


def _longest_no_repeat(s):
    last, left, best = {}, 0, 0
    for right, ch in enumerate(s):
        if ch in last and last[ch] >= left:
            left = last[ch] + 1
        last[ch] = right
        best = max(best, right - left + 1)
    return best


def _longest_no_repeat_substr(s):
    last, left, best, start = {}, 0, 0, 0
    for right, ch in enumerate(s):
        if ch in last and last[ch] >= left:
            left = last[ch] + 1
        last[ch] = right
        if right - left + 1 > best:
            best, start = right - left + 1, left
    return s[start:start + best]


def _longest_k_distinct(s, k):
    counts, left, best = Counter(), 0, 0
    for right, ch in enumerate(s):
        counts[ch] += 1
        while len(counts) > k:
            counts[s[left]] -= 1
            if not counts[s[left]]:
                del counts[s[left]]
            left += 1
        best = max(best, right - left + 1)
    return best


def _longest_k_categories(items, k):
    counts, left, best = Counter(), 0, 0
    for right, item in enumerate(items):
        counts[item] += 1
        while len(counts) > k:
            counts[items[left]] -= 1
            if not counts[items[left]]:
                del counts[items[left]]
            left += 1
        best = max(best, right - left + 1)
    return best


def _min_window(s, t):
    if not t or not s:
        return ""
    need = Counter(t)
    missing = len(t)
    left = best_l = 0
    best = len(s) + 1
    for right, ch in enumerate(s):
        if need[ch] > 0:
            missing -= 1
        need[ch] -= 1
        while missing == 0:
            if right - left + 1 < best:
                best, best_l = right - left + 1, left
            need[s[left]] += 1
            if need[s[left]] > 0:
                missing += 1
            left += 1
    return "" if best > len(s) else s[best_l:best_l + best]


def _max_sliding_window(nums, k):
    if not nums or k <= 0:
        return []
    dq, out = deque(), []
    for i, v in enumerate(nums):
        while dq and nums[dq[-1]] <= v:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - k:
            dq.popleft()
        if i >= k - 1:
            out.append(nums[dq[0]])
    return out


def _min_subarray_len(nums, target):
    left, total, best = 0, 0, len(nums) + 1
    for right, v in enumerate(nums):
        total += v
        while left <= right and total >= target:
            best = min(best, right - left + 1)
            total -= nums[left]
            left += 1
    return 0 if best > len(nums) else best


def _max_avg(nums, k):
    if not nums or k <= 0:
        return 0.0
    window = sum(nums[:k])
    best = window
    for i in range(k, len(nums)):
        window += nums[i] - nums[i - k]
        best = max(best, window)
    return best / k


def _char_replacement(s, k):
    counts, left, best, most = Counter(), 0, 0, 0
    for right, ch in enumerate(s):
        counts[ch] += 1
        most = max(most, counts[ch])
        while (right - left + 1) - most > k:
            counts[s[left]] -= 1
            left += 1
        best = max(best, right - left + 1)
    return best


def _find_anagrams(s, p):
    if len(p) > len(s):
        return []
    need, window = Counter(p), Counter(s[:len(p)])
    out = [0] if window == need else []
    for i in range(len(p), len(s)):
        window[s[i]] += 1
        drop = s[i - len(p)]
        window[drop] -= 1
        if not window[drop]:
            del window[drop]
        if window == need:
            out.append(i - len(p) + 1)
    return out


def _fruit_baskets(trees):
    return _longest_k_categories(trees, 2)


def _binary_ones(nums, k):
    left, zeros, best = 0, 0, 0
    for right, v in enumerate(nums):
        zeros += v == 0
        while zeros > k:
            zeros -= nums[left] == 0
            left += 1
        best = max(best, right - left + 1)
    return best


def _distinct_windows(nums, k):
    counts, out = Counter(), []
    for i, v in enumerate(nums):
        counts[v] += 1
        if i >= k:
            drop = nums[i - k]
            counts[drop] -= 1
            if not counts[drop]:
                del counts[drop]
        if i >= k - 1:
            out.append(len(counts))
    return out


def _longest_k_identities(events, k):
    return _longest_k_categories([user for user, _ in events], k)


def _max_bytes_window(sizes, k):
    if k > len(sizes):
        return sum(sizes)
    window = sum(sizes[:k])
    best = window
    for i in range(k, len(sizes)):
        window += sizes[i] - sizes[i - k]
        best = max(best, window)
    return best


def _rate_limited(timestamps, window, limit):
    left, out = 0, []
    for right, t in enumerate(timestamps):
        while timestamps[left] <= t - window:
            left += 1
        out.append((right - left + 1) > limit)
    return out


def build() -> list:
    P: list = []

    P.append(code_problem(
        id="sw-longest-no-repeat", title="The Window Wraith", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_distinct",
        secondary=["HASH_MAP", "STRING"], boss=True, profile_weight=Q, viz=VIZ,
        source_type="REPORTED_INTERVIEW", year="reported pattern",
        provenance="One of the most widely reported string archetypes in SWE screens. "
                   "Historical pattern, not a guaranteed question.",
        statement="""
            Return the length of the longest substring of `s` containing no repeated
            character.

            The Wraith feeds on restarts. Every time your scan begins again from a new
            starting position, it heals.
        """,
        fn_name="length_of_longest_substring", params="s", reference=_longest_no_repeat,
        constraints=["0 <= len(s) <= 100000", "s may contain any characters"],
        canonical="""
            def length_of_longest_substring(s):
                last_seen = {}
                left = 0
                best = 0
                for right, ch in enumerate(s):
                    if ch in last_seen and last_seen[ch] >= left:
                        left = last_seen[ch] + 1     # jump past the earlier copy
                    last_seen[ch] = right
                    best = max(best, right - left + 1)
                return best
        """,
        visible=[("classic", ["abcabcbb"]), ("all same", ["bbbbb"])],
        hidden=[("interleaved", ["pwwkew"]), ("spaces", ["a b c a b"]),
                ("long distinct", ["abcdefghij"]), ("stale index", ["tmmzuxt"])],
        edges=[("empty", [""]), ("single", ["z"]), ("two same", ["aa"])],
        perf=[("100k chars", ["abcdefghij" * 10000])],
        time_complexity="O(n)", space_complexity="O(min(n, alphabet))",
        failures=["Checking every substring is O(n^2) or worse",
                  "Moving `left` to `last_seen[ch] + 1` without checking it is still "
                  "inside the window — a stale index drags `left` backwards",
                  "Using a set and removing one character at a time is correct but "
                  "easier to get wrong under time pressure"],
        nudge="You never need to restart the scan. When a repeat appears, the window's "
              "left edge only ever moves right.",
        visual="A glowing frame stretches right one character at a time. The instant a "
               "character already inside reappears, the left edge leaps to just past that "
               "earlier copy. It never moves backwards.",
        pseudocode=PSEUDO,
        alternates=[{"name": "set + shrink one at a time",
                     "note": "Same O(n), a little more code, harder to break.",
                     "complexity": "O(n)"}],
        variants=["sw-longest-no-repeat-substr", "sw-k-distinct", "sec-k-identities"],
        tags=["core", "practical", "boss"],
    ))

    P.append(code_problem(
        id="sw-longest-no-repeat-substr", title="Wraith's Echo", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_distinct",
        source_type="GENERATED_VARIANT", profile_weight=Q, viz=VIZ,
        statement="""
            Same ward, different demand: return the longest repeat-free substring
            **itself**, not its length. On ties return the leftmost one.
        """,
        fn_name="longest_unique_substring", params="s", reference=_longest_no_repeat_substr,
        canonical="""
            def longest_unique_substring(s):
                last_seen = {}
                left = best = start = 0
                for right, ch in enumerate(s):
                    if ch in last_seen and last_seen[ch] >= left:
                        left = last_seen[ch] + 1
                    last_seen[ch] = right
                    if right - left + 1 > best:
                        best, start = right - left + 1, left
                return s[start:start + best]
        """,
        visible=[("classic", ["abcabcbb"]), ("tie leftmost", ["abcbde"])],
        hidden=[("all same", ["cccc"]), ("end wins", ["aabcdef"]), ("stale", ["tmmzuxt"])],
        edges=[("empty", [""]), ("single", ["q"])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["Tracking length but forgetting to record where the best window started",
                  "Updating start on `>=` and losing the leftmost tie"],
        nudge="You need one more variable than last time. Which one?",
        visual="Same frame, but now you also remember where the widest frame began.",
        pseudocode=PSEUDO, prerequisites=["sw-longest-no-repeat"], tags=["variant"],
    ))

    P.append(code_problem(
        id="sw-k-distinct", title="The K-Distinct Ward", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_k_distinct",
        secondary=["HASH_MAP"], profile_weight=Q, viz=VIZ,
        source_type="REPORTED_INTERVIEW", year="reported pattern",
        provenance="At-most-K-distinct is a repeatedly reported screen archetype.",
        statement="""
            Return the length of the longest substring of `s` containing at most `k`
            distinct characters.

            When `k` is `0` the answer is `0`.
        """,
        fn_name="longest_k_distinct", params="s, k", reference=_longest_k_distinct,
        constraints=["0 <= len(s) <= 100000", "0 <= k <= 26"],
        canonical="""
            def longest_k_distinct(s, k):
                from collections import Counter
                counts = Counter()
                left = 0
                best = 0
                for right, ch in enumerate(s):
                    counts[ch] += 1
                    while len(counts) > k:
                        counts[s[left]] -= 1
                        if counts[s[left]] == 0:
                            del counts[s[left]]     # deleting is what keeps len() honest
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        visible=[("two distinct", ["eceba", 2]), ("three distinct", ["aa", 1])],
        hidden=[("k zero", ["abc", 0]), ("k exceeds alphabet", ["abc", 10]),
                ("long run", ["aabbcc", 2]), ("all same", ["aaaa", 1])],
        edges=[("empty", ["", 3]), ("k one", ["abaccc", 1])],
        perf=[("100k", ["abcde" * 20000, 3])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["Leaving zero-count keys in the dict so `len(counts)` never drops",
                  "Using `if` instead of `while` to shrink — one shrink is not always enough",
                  "Not handling k == 0"],
        nudge="`len(counts)` is your constraint check. That only works if you delete keys "
              "when they hit zero.",
        visual="Counters float above each character inside the frame. When a counter "
               "reaches zero its vault closes and the distinct count drops.",
        pseudocode=PSEUDO, prerequisites=["sw-longest-no-repeat"],
        variants=["sw-k-categories", "sec-k-identities"],
        tags=["core", "practical"],
    ))

    P.append(code_problem(
        id="sw-k-categories", title="Longest Caravan", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_k_distinct",
        source_type="GENERATED_VARIANT", profile_weight=Q, viz=VIZ,
        statement="""
            The same ward wearing a different face. `items` is a list of category labels.
            Return the length of the longest contiguous run containing at most `k`
            distinct categories.

            Nothing about the algorithm changed. Only the element type did.
        """,
        fn_name="longest_k_categories", params="items, k", reference=_longest_k_categories,
        canonical="""
            def longest_k_categories(items, k):
                from collections import Counter
                counts = Counter()
                left = best = 0
                for right, item in enumerate(items):
                    counts[item] += 1
                    while len(counts) > k:
                        counts[items[left]] -= 1
                        if counts[items[left]] == 0:
                            del counts[items[left]]
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        visible=[("two kinds", [["ore", "ore", "silk", "ore", "gem"], 2]),
                 ("one kind", [["a", "b", "a"], 1])],
        hidden=[("k zero", [["a"], 0]), ("all one", [["x", "x", "x"], 3]),
                ("wide", [["a", "b", "c", "d"], 3])],
        edges=[("empty", [[], 2])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["Assuming characters and indexing the list as a string"],
        nudge="If you solved the K-Distinct Ward, you have already solved this.",
        visual="Same frame, different cargo.", pseudocode=PSEUDO,
        prerequisites=["sw-k-distinct"], tags=["variant", "disguised"],
    ))

    P.append(code_problem(
        id="sw-min-window", title="The Contracting Seal", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="HARD", family="window_cover",
        secondary=["HASH_MAP", "STRING"], profile_weight=Q, viz=VIZ, boss=True,
        statement="""
            Return the shortest substring of `s` that contains every character of `t`
            **including duplicates**. Return `""` if no such substring exists.

            This is the window that shrinks as well as grows.
        """,
        fn_name="min_window", params="s, t", reference=_min_window,
        constraints=["0 <= len(s) <= 100000", "0 <= len(t) <= 1000"],
        canonical="""
            def min_window(s, t):
                from collections import Counter
                if not s or not t:
                    return ""
                need = Counter(t)
                missing = len(t)               # counts duplicates, not distinct chars
                left = best_left = 0
                best = len(s) + 1
                for right, ch in enumerate(s):
                    if need[ch] > 0:
                        missing -= 1
                    need[ch] -= 1              # may go negative: surplus
                    while missing == 0:
                        if right - left + 1 < best:
                            best, best_left = right - left + 1, left
                        need[s[left]] += 1
                        if need[s[left]] > 0:
                            missing += 1
                        left += 1
                return "" if best > len(s) else s[best_left:best_left + best]
        """,
        visible=[("classic", ["ADOBECODEBANC", "ABC"]), ("no cover", ["a", "aa"])],
        hidden=[("exact", ["ab", "ab"]), ("duplicates in t", ["aaab", "aab"]),
                ("whole string", ["abc", "cba"]), ("late window", ["xxxyz", "yz"])],
        edges=[("empty s", ["", "a"]), ("empty t", ["abc", ""]),
               ("t longer", ["a", "ab"])],
        perf=[("60k", ["abcde" * 12000, "ace"])],
        time_complexity="O(len(s) + len(t))", space_complexity="O(len(t))",
        failures=["Tracking distinct characters instead of total needed characters, "
                  "which breaks when `t` has duplicates",
                  "Shrinking with `if` instead of `while`",
                  "Recording the answer after moving `left` instead of before"],
        nudge="`missing` should count *characters still owed*, duplicates included — not "
              "how many distinct letters you have.",
        visual="The frame grows right until the seal is satisfied, then claws inward from "
               "the left as far as it can while staying satisfied, recording the width "
               "each time.",
        pseudocode="""
            need = Counter(t); missing = len(t)
            for right, ch:
                if need[ch] > 0: missing -= 1
                need[ch] -= 1
                while missing == 0:
                    record window
                    need[s[left]] += 1
                    if need[s[left]] > 0: missing += 1
                    left += 1
        """,
        prerequisites=["sw-k-distinct"], tags=["core", "hard", "boss"],
    ))

    P.append(code_problem(
        id="sw-max-sliding-window", title="The Rolling Titan", realm="sliding_window_marsh",
        pattern="QUEUE", difficulty="HARD", family="rolling_max",
        secondary=["SLIDING_WINDOW", "HEAP"], profile_weight=Q, boss=True,
        viz={"type": "monotonic_deque", "caption": "The deque keeps only useful candidates."},
        source_type="REPORTED_INTERVIEW", year="reported pattern",
        provenance="Rolling maximum over a time window is a repeatedly reported archetype.",
        statement="""
            Return the maximum of every window of size `k` as it slides across `nums`,
            left to right.

            Calling `max()` on each window is O(n·k). The Titan only falls to O(n).
        """,
        fn_name="max_sliding_window", params="nums, k", reference=_max_sliding_window,
        constraints=["0 <= len(nums) <= 100000", "1 <= k <= len(nums) when nums is non-empty"],
        canonical="""
            def max_sliding_window(nums, k):
                from collections import deque
                if not nums or k <= 0:
                    return []
                window = deque()          # holds INDICES, values decreasing
                out = []
                for i, value in enumerate(nums):
                    while window and nums[window[-1]] <= value:
                        window.pop()      # anything smaller can never be a max again
                    window.append(i)
                    if window[0] <= i - k:
                        window.popleft()  # the front has slid out of range
                    if i >= k - 1:
                        out.append(nums[window[0]])
                return out
        """,
        visible=[("classic", [[1, 3, -1, -3, 5, 3, 6, 7], 3]), ("k one", [[9, 2], 1])],
        hidden=[("descending", [[5, 4, 3, 2, 1], 2]), ("ascending", [[1, 2, 3, 4], 2]),
                ("all same", [[7, 7, 7], 2]), ("k equals n", [[4, 1, 9], 3])],
        edges=[("empty", [[], 3]), ("single", [[1], 1])],
        perf=[("100k", [[(i * 7919) % 1000 for i in range(100000)], 100])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["max() per window is O(n*k) and times out",
                  "Storing values instead of indices, so you cannot tell when the front "
                  "has expired",
                  "Evicting the front before appending the new index",
                  "Emitting an answer before the first window is full"],
        nudge="If a new value is bigger than something already waiting, that older value "
              "can never be the maximum of any future window. Discard it forever.",
        visual="A queue of candidates, tallest at the front, each shorter than the one "
               "before. New arrivals shove out everyone shorter behind them. The front "
               "leaves when it falls out of the frame.",
        pseudocode="""
            deque of indices, values strictly decreasing
            for i, value:
                pop back while nums[back] <= value
                push i
                popleft if front <= i - k
                if i >= k-1: emit nums[front]
        """,
        alternates=[{"name": "max-heap with lazy deletion",
                     "note": "O(n log n). Passes, but the deque is the expected answer.",
                     "complexity": "O(n log n)"}],
        tags=["core", "practical", "hard", "boss"],
    ))

    P.append(code_problem(
        id="sw-min-subarray-len", title="Shortest Sufficient March", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_sum",
        profile_weight=Q, viz=VIZ,
        statement="""
            All values are positive. Return the length of the shortest contiguous
            subarray whose sum is at least `target`, or `0` if none exists.
        """,
        fn_name="min_subarray_len", params="nums, target", reference=_min_subarray_len,
        canonical="""
            def min_subarray_len(nums, target):
                left = 0
                total = 0
                best = len(nums) + 1
                for right, value in enumerate(nums):
                    total += value
                    while left <= right and total >= target:
                        best = min(best, right - left + 1)
                        total -= nums[left]
                        left += 1
                return 0 if best > len(nums) else best
        """,
        visible=[("classic", [[2, 3, 1, 2, 4, 3], 7]), ("none", [[1, 1, 1], 100])],
        hidden=[("single suffices", [[1, 4, 4], 4]), ("whole array", [[1, 2, 3], 6]),
                ("exact", [[5], 5])],
        edges=[("empty", [[], 1]), ("target zero", [[1, 2], 0])],
        perf=[("100k", [[1] * 100000, 500])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Shrinking with `if` rather than `while`",
                  "Forgetting the impossible case returns 0",
                  "This approach silently breaks if negatives are allowed",
                  "A target of 0 walks `left` past `right` unless you guard the shrink"],
        nudge="Grow until satisfied, then shrink while still satisfied.",
        visual="The frame widens until the sum clears the bar, then tightens from the "
               "left as far as it can.",
        pseudocode=PSEUDO, tags=["core"],
    ))

    P.append(code_problem(
        id="sw-max-average", title="Steadiest Stretch", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="EASY", family="fixed_window",
        profile_weight=Q, viz=VIZ, cmp="float",
        statement="""
            Return the maximum average value of any contiguous subarray of exactly
            length `k`.
        """,
        fn_name="max_average", params="nums, k", reference=_max_avg,
        canonical="""
            def max_average(nums, k):
                if not nums or k <= 0:
                    return 0.0
                window = sum(nums[:k])
                best = window
                for i in range(k, len(nums)):
                    window += nums[i] - nums[i - k]
                    best = max(best, window)
                return best / k
        """,
        visible=[("classic", [[1, 12, -5, -6, 50, 3], 4]), ("k one", [[5, 9], 1])],
        hidden=[("negatives", [[-1, -2, -3], 2]), ("k equals n", [[1, 2, 3], 3])],
        edges=[("empty", [[], 2])],
        perf=[("100k", [[i % 13 for i in range(100000)], 1000])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Recomputing sum() per window", "Integer division instead of float",
                  "Seeding `best` with 0 breaks on all-negative input"],
        nudge="Slide the sum, divide once at the end.",
        visual="A fixed-width frame; one value in, one value out.",
        pseudocode="window += nums[i] - nums[i-k]", tags=["core"],
    ))

    P.append(code_problem(
        id="sw-char-replacement", title="The Malleable Ward", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="HARD", family="window_replace",
        secondary=["HASH_MAP"], profile_weight=Q, viz=VIZ,
        statement="""
            You may change at most `k` characters of `s` to any other character. Return
            the length of the longest run of a single repeated character you can produce.
        """,
        fn_name="character_replacement", params="s, k", reference=_char_replacement,
        canonical="""
            def character_replacement(s, k):
                from collections import Counter
                counts = Counter()
                left = best = most_common = 0
                for right, ch in enumerate(s):
                    counts[ch] += 1
                    most_common = max(most_common, counts[ch])
                    while (right - left + 1) - most_common > k:
                        counts[s[left]] -= 1
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        visible=[("one change", ["ABAB", 2]), ("classic", ["AABABBA", 1])],
        hidden=[("k zero", ["ABCD", 0]), ("all same", ["AAAA", 2]),
                ("k covers all", ["ABCD", 4])],
        edges=[("empty", ["", 2]), ("single", ["A", 0])],
        perf=[("60k", ["ABCDE" * 12000, 3])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Recomputing max(counts.values()) inside the loop — correct, O(26n)",
                  "Believing `most_common` must be exact; it never needs to shrink because "
                  "the answer only cares about the best window ever seen"],
        nudge="A window is valid when (width - most frequent character in it) <= k.",
        visual="The frame widens; the cost of making it uniform is everything that is not "
               "the majority character inside it.",
        pseudocode="while (width - most_common) > k: shrink", tags=["hard"],
    ))

    P.append(code_problem(
        id="sw-find-anagrams", title="Hidden Permutations", realm="stringwood_labyrinth",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_anagram",
        secondary=["HASH_MAP", "STRING"], profile_weight=Q, viz=VIZ,
        statement="""
            Return the starting indices of every substring of `s` that is an anagram of
            `p`, in ascending order.
        """,
        fn_name="find_anagrams", params="s, p", reference=_find_anagrams,
        canonical="""
            def find_anagrams(s, p):
                from collections import Counter
                if len(p) > len(s):
                    return []
                need = Counter(p)
                window = Counter(s[:len(p)])
                out = [0] if window == need else []
                for i in range(len(p), len(s)):
                    window[s[i]] += 1
                    leaving = s[i - len(p)]
                    window[leaving] -= 1
                    if window[leaving] == 0:
                        del window[leaving]      # otherwise the == comparison fails
                    if window == need:
                        out.append(i - len(p) + 1)
                return out
        """,
        visible=[("two hits", ["cbaebabacd", "abc"]), ("overlapping", ["abab", "ab"])],
        hidden=[("no hits", ["abcdef", "xyz"]), ("whole string", ["abc", "cab"]),
                ("repeats in p", ["aaab", "aab"])],
        edges=[("p longer", ["a", "ab"]), ("empty s", ["", "a"])],
        perf=[("60k", ["abcab" * 12000, "abc"])],
        time_complexity="O(len(s))", space_complexity="O(1)",
        failures=["Re-sorting each window is O(n·k log k)",
                  "Leaving zero-count keys so Counter equality never matches"],
        nudge="A fixed-width frame plus one equality check per step.",
        visual="A frame of width len(p) slides; its tally board must exactly match p's.",
        pseudocode="build need & first window; slide adding/removing one char; compare",
        prerequisites=["ah-valid-anagram"], tags=["core", "practical"],
    ))

    P.append(code_problem(
        id="sw-fruit-baskets", title="Two Baskets", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_k_distinct",
        source_type="GENERATED_VARIANT", profile_weight=Q, viz=VIZ,
        statement="""
            You walk a row of trees carrying exactly two baskets, each holding one kind
            of fruit. You must pick from every tree you pass, and you may not skip.
            Return the most fruit you can gather.

            The problem statement mentions no window, no `k`, and no distinct count.
            Recognise it anyway.
        """,
        fn_name="total_fruit", params="trees", reference=_fruit_baskets,
        canonical="""
            def total_fruit(trees):
                from collections import Counter
                counts = Counter()
                left = best = 0
                for right, kind in enumerate(trees):
                    counts[kind] += 1
                    while len(counts) > 2:            # two baskets == k of 2
                        counts[trees[left]] -= 1
                        if counts[trees[left]] == 0:
                            del counts[trees[left]]
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        visible=[("classic", [[1, 2, 1]]), ("three kinds", [[0, 1, 2, 2]])],
        hidden=[("long tail", [[1, 2, 3, 2, 2]]), ("all same", [[4, 4, 4, 4]]),
                ("alternating", [[1, 2, 1, 2, 1]])],
        edges=[("empty", [[]]), ("single", [[3]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Not recognising 'two baskets' as 'at most 2 distinct'"],
        nudge="'Two baskets' is `k = 2`. You have solved this problem before under a "
              "different name.",
        visual="Same frame as the K-Distinct Ward, with k pinned to two.",
        pseudocode=PSEUDO, prerequisites=["sw-k-distinct"],
        tags=["variant", "disguised", "recognition"],
    ))

    P.append(code_problem(
        id="sw-binary-ones", title="Flipped Banners", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_replace",
        profile_weight=Q, viz=VIZ,
        statement="""
            `nums` holds only `0` and `1`. You may flip at most `k` zeroes to one.
            Return the length of the longest run of ones you can produce.
        """,
        fn_name="longest_ones", params="nums, k", reference=_binary_ones,
        canonical="""
            def longest_ones(nums, k):
                left = zeros = best = 0
                for right, value in enumerate(nums):
                    if value == 0:
                        zeros += 1
                    while zeros > k:
                        if nums[left] == 0:
                            zeros -= 1
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        visible=[("classic", [[1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0], 2]),
                 ("no flips", [[1, 0, 1], 0])],
        hidden=[("all zeros", [[0, 0, 0], 2]), ("all ones", [[1, 1, 1], 1]),
                ("k covers all", [[0, 0], 5])],
        edges=[("empty", [[], 1])],
        perf=[("100k", [[i % 3 != 0 and 1 or 0 for i in range(100000)], 100])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Counting zeros with sum() over the slice each step"],
        nudge="The window is valid while it contains at most k zeroes.",
        visual="One counter: zeroes inside the frame.", pseudocode=PSEUDO,
        tags=["core"],
    ))

    P.append(code_problem(
        id="sw-distinct-windows", title="Census of Each March", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="fixed_window",
        secondary=["HASH_MAP"], profile_weight=Q, viz=VIZ,
        statement="""
            For every window of size `k`, report how many **distinct** values it contains.
            Return the counts left to right.
        """,
        fn_name="distinct_per_window", params="nums, k", reference=_distinct_windows,
        canonical="""
            def distinct_per_window(nums, k):
                from collections import Counter
                counts = Counter()
                out = []
                for i, value in enumerate(nums):
                    counts[value] += 1
                    if i >= k:
                        leaving = nums[i - k]
                        counts[leaving] -= 1
                        if counts[leaving] == 0:
                            del counts[leaving]
                    if i >= k - 1:
                        out.append(len(counts))
                return out
        """,
        visible=[("classic", [[1, 2, 1, 3, 4, 2, 3], 4]), ("k one", [[5, 5], 1])],
        hidden=[("all same", [[7, 7, 7], 2]), ("all distinct", [[1, 2, 3], 2]),
                ("k equals n", [[1, 1, 2], 3])],
        edges=[("empty", [[], 2]), ("k larger than n", [[1], 5])],
        perf=[("100k", [[i % 50 for i in range(100000)], 200])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["Building a set per window is O(n·k)",
                  "Not deleting zero-count keys, so len() is wrong"],
        nudge="Same delete-at-zero discipline as the K-Distinct Ward.",
        visual="A tally board that both gains and loses entries as the frame moves.",
        pseudocode="add entering; remove leaving; delete key at zero; emit len(counts)",
        prerequisites=["sw-k-distinct"], tags=["core"],
    ))

    # -- security transfers -----------------------------------------------------
    P.append(code_problem(
        id="sec-k-identities", title="Session Ward", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_k_distinct",
        security=True, profile_weight=QS, viz=VIZ,
        statement="""
            `events` is a chronological list of `[identity, action]` authentication
            records. Return the length of the longest contiguous stretch of events
            involving at most `k` distinct identities.
        """,
        fn_name="longest_k_identity_window", params="events, k",
        reference=_longest_k_identities,
        canonical="""
            def longest_k_identity_window(events, k):
                from collections import Counter
                identities = [user for user, _ in events]
                counts = Counter()
                left = best = 0
                for right, user in enumerate(identities):
                    counts[user] += 1
                    while len(counts) > k:
                        counts[identities[left]] -= 1
                        if counts[identities[left]] == 0:
                            del counts[identities[left]]
                        left += 1
                    best = max(best, right - left + 1)
                return best
        """,
        visible=[("two identities", [[["a", "login"], ["a", "login"], ["b", "login"],
                                      ["c", "login"]], 2]),
                 ("single", [[["a", "x"]], 1])],
        hidden=[("k zero", [[["a", "x"]], 0]),
                ("all one identity", [[["a", "x"], ["a", "y"], ["a", "z"]], 1]),
                ("wide", [[["a", "1"], ["b", "1"], ["c", "1"]], 3])],
        edges=[("empty", [[], 2])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["Forgetting to project out the identity field first"],
        nudge="Project the field you care about, then it is the ward you already know.",
        visual="Same frame; the tokens are identities.", pseudocode=PSEUDO,
        prerequisites=["sw-k-distinct"], tags=["security", "transfer", "disguised"],
    ))

    P.append(code_problem(
        id="sec-egress-burst", title="Egress Spike", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="EASY", family="fixed_window",
        security=True, profile_weight=QS, viz=VIZ,
        statement="""
            `sizes[i]` is bytes transferred in minute `i`. Return the largest total across
            any `k` consecutive minutes. If `k` exceeds the log length, return the total.
        """,
        fn_name="max_egress_window", params="sizes, k", reference=_max_bytes_window,
        canonical="""
            def max_egress_window(sizes, k):
                if k > len(sizes):
                    return sum(sizes)
                window = sum(sizes[:k])
                best = window
                for i in range(k, len(sizes)):
                    window += sizes[i] - sizes[i - k]
                    best = max(best, window)
                return best
        """,
        visible=[("spike", [[10, 10, 900, 10], 2]), ("flat", [[5, 5, 5], 2])],
        hidden=[("k equals n", [[1, 2, 3], 3]), ("k exceeds", [[1, 2], 9]),
                ("zeros", [[0, 0, 0], 2])],
        edges=[("empty", [[], 3])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Re-summing the slice per position"],
        nudge="One in, one out.", visual="Fixed frame across the minutes.",
        pseudocode="window += sizes[i] - sizes[i-k]",
        tags=["security", "transfer"],
    ))

    P.append(code_problem(
        id="sec-rate-limit", title="The Throttle Gate", realm="sliding_window_marsh",
        pattern="SLIDING_WINDOW", difficulty="MEDIUM", family="window_time",
        security=True, profile_weight=QS, viz=VIZ,
        statement="""
            `timestamps` is a non-decreasing list of request times in seconds. A request
            is **throttled** when more than `limit` requests (including itself) fall
            within the trailing `window` seconds — that is, in the half-open interval
            `(t - window, t]`.

            Return a list of booleans, one per request.
        """,
        fn_name="throttled", params="timestamps, window, limit", reference=_rate_limited,
        canonical="""
            def throttled(timestamps, window, limit):
                left = 0
                out = []
                for right, t in enumerate(timestamps):
                    while timestamps[left] <= t - window:
                        left += 1
                    out.append((right - left + 1) > limit)
                return out
        """,
        visible=[("burst", [[0, 1, 2, 3], 3, 2]), ("spread", [[0, 10, 20], 5, 1])],
        hidden=[("all same instant", [[5, 5, 5], 1, 2]),
                ("boundary exclusive", [[0, 10], 10, 1]),
                ("limit zero", [[1], 5, 0])],
        edges=[("empty", [[], 5, 1]), ("single", [[7], 1, 1])],
        perf=[("80k requests", [list(range(80000)), 60, 30])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Rescanning backwards per request is O(n^2)",
                  "Using `<` instead of `<=` on the expiry, shifting the boundary by one "
                  "second",
                  "Comparing with >= instead of > for the limit"],
        nudge="The left edge only moves forward, ever. That is what makes it linear.",
        visual="A trailing frame anchored at the newest request; expired requests drop "
               "off the back.",
        pseudocode="while timestamps[left] <= t - window: left += 1; count = right-left+1",
        tags=["security", "transfer"],
    ))

    return P
