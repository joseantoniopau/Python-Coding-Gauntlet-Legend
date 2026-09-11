"""Twin Pointer Pass. Two adventurers, one from each end, or one chasing the other."""
from __future__ import annotations

from ._base import code_problem

Q = {"PRACTICAL": 3.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 1.0}
QS = {"PRACTICAL": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}
VIZ = {"type": "two_pointer", "caption": "Two runners, closing or chasing."}
PSEUDO = """
lo, hi = 0, len(data) - 1
while lo < hi:
    evaluate(data[lo], data[hi])
    move whichever pointer can improve the answer
"""


def _is_palindrome(s):
    cleaned = [c.lower() for c in s if c.isalnum()]
    lo, hi = 0, len(cleaned) - 1
    while lo < hi:
        if cleaned[lo] != cleaned[hi]:
            return False
        lo += 1
        hi -= 1
    return True


def _sorted_pair(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        s = nums[lo] + nums[hi]
        if s == target:
            return [lo, hi]
        if s < target:
            lo += 1
        else:
            hi -= 1
    return []


def _remove_duplicates(nums):
    if not nums:
        return []
    write = 1
    for read in range(1, len(nums)):
        if nums[read] != nums[write - 1]:
            nums[write] = nums[read]
            write += 1
    return nums[:write]


def _move_zeroes(nums):
    write = 0
    for v in nums:
        if v != 0:
            nums[write] = v
            write += 1
    for i in range(write, len(nums)):
        nums[i] = 0
    return nums


def _container_water(heights):
    lo, hi, best = 0, len(heights) - 1, 0
    while lo < hi:
        best = max(best, (hi - lo) * min(heights[lo], heights[hi]))
        if heights[lo] < heights[hi]:
            lo += 1
        else:
            hi -= 1
    return best


def _merge_sorted(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i]); i += 1
        else:
            out.append(b[j]); j += 1
    out.extend(a[i:]); out.extend(b[j:])
    return out


def _reverse_words(s):
    return " ".join(reversed(s.split()))


def _squares_sorted(nums):
    out = [0] * len(nums)
    lo, hi = 0, len(nums) - 1
    for pos in range(len(nums) - 1, -1, -1):
        if abs(nums[lo]) > abs(nums[hi]):
            out[pos] = nums[lo] ** 2
            lo += 1
        else:
            out[pos] = nums[hi] ** 2
            hi -= 1
    return out


def _is_subsequence(small, big):
    it = iter(big)
    return all(ch in it for ch in small)


def _trap_water(heights):
    if not heights:
        return 0
    lo, hi = 0, len(heights) - 1
    left_max, right_max, total = heights[lo], heights[hi], 0
    while lo < hi:
        if left_max <= right_max:
            lo += 1
            left_max = max(left_max, heights[lo])
            total += left_max - heights[lo]
        else:
            hi -= 1
            right_max = max(right_max, heights[hi])
            total += right_max - heights[hi]
    return total


def _sorted_intersection(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            if not out or out[-1] != a[i]:
                out.append(a[i])
            i += 1; j += 1
        elif a[i] < b[j]:
            i += 1
        else:
            j += 1
    return out


def _valid_after_one_removal(s):
    lo, hi = 0, len(s) - 1
    while lo < hi:
        if s[lo] != s[hi]:
            def ok(a, b):
                while a < b:
                    if s[a] != s[b]:
                        return False
                    a += 1; b -= 1
                return True
            return ok(lo + 1, hi) or ok(lo, hi - 1)
        lo += 1; hi -= 1
    return True


def _partition_sorted_events(events, cutoff):
    lo, hi = 0, len(events) - 1
    pairs = []
    while lo < hi:
        total = events[lo] + events[hi]
        if total > cutoff:
            hi -= 1
        else:
            pairs.append([events[lo], events[hi]])
            lo += 1; hi -= 1
    return pairs


def build() -> list:
    P: list = []

    P.append(code_problem(
        id="tp-valid-palindrome", title="The Mirror Gate", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="palindrome",
        secondary=["STRING"], profile_weight=Q, viz=VIZ, cmp="bool",
        statement="""
            Return `True` if `s` reads the same forwards and backwards, ignoring
            everything that is not a letter or digit, and ignoring case.
        """,
        fn_name="is_palindrome", params="s", reference=_is_palindrome,
        canonical="""
            def is_palindrome(s):
                cleaned = [ch.lower() for ch in s if ch.isalnum()]
                lo, hi = 0, len(cleaned) - 1
                while lo < hi:
                    if cleaned[lo] != cleaned[hi]:
                        return False
                    lo += 1
                    hi -= 1
                return True
        """,
        visible=[("classic", ["A man, a plan, a canal: Panama"]), ("not", ["race a car"])],
        hidden=[("digits", ["12321"]), ("punctuation only", [".,!"]),
                ("mixed case", ["Aa"]), ("odd length", ["aba"])],
        edges=[("empty", [""]), ("single", ["x"])],
        perf=[("200k chars", ["ab" * 100000])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Forgetting to strip non-alphanumerics", "Forgetting case folding",
                  "Assuming punctuation-only strings are not palindromes"],
        nudge="Clean first, compare from both ends second.",
        visual="Two runners start at the far walls and walk toward each other, comparing "
               "at each step. They meet in the middle or the gate stays shut.",
        pseudocode=PSEUDO, tags=["core"],
    ))

    P.append(code_problem(
        id="tp-sorted-pair", title="Converging Runners", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="sorted_pair",
        profile_weight=Q, viz=VIZ,
        statement="""
            `nums` is sorted ascending. Return the indices `[lo, hi]` of the two values
            summing to `target`, or `[]` if none exist. Use O(1) extra space.
        """,
        fn_name="two_sum_sorted", params="nums, target", reference=_sorted_pair,
        canonical="""
            def two_sum_sorted(nums, target):
                lo, hi = 0, len(nums) - 1
                while lo < hi:
                    total = nums[lo] + nums[hi]
                    if total == target:
                        return [lo, hi]
                    if total < target:
                        lo += 1        # need more; only the left can grow
                    else:
                        hi -= 1        # need less; only the right can shrink
                return []
        """,
        visible=[("classic", [[2, 7, 11, 15], 9]), ("far ends", [[1, 2, 3, 9], 10])],
        hidden=[("negatives", [[-5, -2, 0, 4], -7]), ("none", [[1, 2, 3], 100]),
                ("duplicates", [[3, 3, 3], 6])],
        edges=[("empty", [[], 5]), ("single", [[5], 5])],
        perf=[("200k sorted", [list(range(200000)), 399997])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Using a hash map — correct but O(n) space when O(1) was asked for",
                  "Using `<=` in the while condition lets an element pair with itself"],
        nudge="Sorted input is a gift: the sum only moves one way when each pointer moves.",
        visual="Sum too small? Only the left runner can help. Too large? Only the right.",
        pseudocode=PSEUDO, prerequisites=["ah-two-sum-indices"], tags=["core"],
    ))

    P.append(code_problem(
        id="tp-remove-duplicates", title="Compacting the Column", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="fast_slow",
        profile_weight=Q, viz=VIZ,
        statement="""
            `nums` is sorted ascending. Remove duplicates in place so each value appears
            once, and return the compacted list.
        """,
        fn_name="remove_duplicates", params="nums", reference=_remove_duplicates,
        canonical="""
            def remove_duplicates(nums):
                if not nums:
                    return []
                write = 1
                for read in range(1, len(nums)):
                    if nums[read] != nums[write - 1]:
                        nums[write] = nums[read]
                        write += 1
                return nums[:write]
        """,
        visible=[("classic", [[1, 1, 2]]), ("longer", [[0, 0, 1, 1, 1, 2, 2, 3, 3, 4]])],
        hidden=[("all same", [[5, 5, 5]]), ("none repeated", [[1, 2, 3]]),
                ("negatives", [[-2, -2, -1]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Removing from the list while iterating it",
                  "Comparing against nums[read-1] after you have already overwritten it"],
        nudge="One pointer reads, one pointer writes. The writer lags behind.",
        visual="A slow scribe copies only new values forward while a fast scout reads ahead.",
        pseudocode="write = 1; for read: if new: nums[write] = nums[read]; write += 1",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tp-move-zeroes", title="Sinking Stones", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="fast_slow",
        profile_weight=Q, viz=VIZ,
        statement="""
            Move every `0` in `nums` to the end while keeping the relative order of the
            non-zero values. Return the modified list.
        """,
        fn_name="move_zeroes", params="nums", reference=_move_zeroes,
        canonical="""
            def move_zeroes(nums):
                write = 0
                for value in nums:
                    if value != 0:
                        nums[write] = value
                        write += 1
                for i in range(write, len(nums)):
                    nums[i] = 0
                return nums
        """,
        visible=[("classic", [[0, 1, 0, 3, 12]]), ("already clean", [[1, 2, 3]])],
        hidden=[("all zeroes", [[0, 0]]), ("leading zeroes", [[0, 0, 1]]),
                ("negatives", [[0, -1, 0, -2]])],
        edges=[("empty", [[]]), ("single zero", [[0]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Building a new list is fine but not 'in place'",
                  "Swapping without care reorders the non-zero values"],
        nudge="Compact the survivors forward, then fill the tail.",
        visual="Non-zero stones float to the front; the pit behind them fills with zeroes.",
        pseudocode="compact non-zeroes to the front; zero-fill from write to end",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tp-container-water", title="The Twin Pointer Behemoth", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="MEDIUM", family="converging", boss=True,
        profile_weight=Q, viz=VIZ,
        statement="""
            `heights[i]` is the height of a wall at position `i`. Choose two walls so the
            water held between them is greatest. Return that volume.

            Volume is `(distance between walls) * (height of the shorter wall)`.
        """,
        fn_name="max_area", params="heights", reference=_container_water,
        canonical="""
            def max_area(heights):
                lo, hi = 0, len(heights) - 1
                best = 0
                while lo < hi:
                    best = max(best, (hi - lo) * min(heights[lo], heights[hi]))
                    if heights[lo] < heights[hi]:
                        lo += 1        # the short wall is the only limit worth changing
                    else:
                        hi -= 1
                return best
        """,
        visible=[("classic", [[1, 8, 6, 2, 5, 4, 8, 3, 7]]), ("two walls", [[1, 1]])],
        hidden=[("ascending", [[1, 2, 3, 4, 5]]), ("descending", [[5, 4, 3, 2, 1]]),
                ("plateau", [[3, 3, 3, 3]]), ("zero walls", [[0, 5, 0]])],
        edges=[("empty", [[]]), ("single", [[4]])],
        perf=[("100k walls", [[(i * 7919) % 1000 for i in range(100000)]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Checking every pair is O(n^2)",
                  "Moving the taller wall inward can never help — it only loses width",
                  "Using max instead of min for the limiting height"],
        nudge="Moving the taller wall inward loses width and cannot gain height. So move "
              "the shorter one. Always.",
        visual="Two walls, water between. Step the shorter wall inward — it is the only "
               "one that could possibly be holding you back.",
        pseudocode="""
            lo, hi = 0, n-1
            while lo < hi:
                best = max(best, (hi-lo) * min(h[lo], h[hi]))
                move the pointer at the SHORTER wall
        """,
        tags=["core", "boss"],
    ))

    P.append(code_problem(
        id="tp-trap-water", title="The Cistern Wyrm", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="HARD", family="converging",
        profile_weight=Q, viz=VIZ,
        statement="""
            `heights` describes an elevation map of unit-width bars. Return how much
            rainwater is trapped between them after it rains.
        """,
        fn_name="trap", params="heights", reference=_trap_water,
        canonical="""
            def trap(heights):
                if not heights:
                    return 0
                lo, hi = 0, len(heights) - 1
                left_max, right_max = heights[lo], heights[hi]
                total = 0
                while lo < hi:
                    if left_max <= right_max:
                        lo += 1
                        left_max = max(left_max, heights[lo])
                        total += left_max - heights[lo]
                    else:
                        hi -= 1
                        right_max = max(right_max, heights[hi])
                        total += right_max - heights[hi]
                return total
        """,
        visible=[("classic", [[0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]]),
                 ("simple basin", [[4, 2, 0, 3, 2, 5]])],
        hidden=[("monotonic", [[1, 2, 3]]), ("flat", [[2, 2, 2]]),
                ("v shape", [[5, 0, 5]]), ("descending", [[5, 4, 3]])],
        edges=[("empty", [[]]), ("single", [[3]]), ("two", [[3, 3]])],
        perf=[("100k bars", [[(i * 31) % 50 for i in range(100000)]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Water above a bar is min(tallest left, tallest right) - own height",
                  "Precomputing both max arrays works and costs O(n) space",
                  "Advancing the pointer before updating its running max"],
        nudge="Water above any bar is bounded by the shorter of the two tallest walls on "
              "either side. Whichever side is currently shorter is the binding constraint.",
        visual="Two walls close in. Whichever side has the lower running maximum is the "
               "one that determines the water level right now.",
        pseudocode="""
            while lo < hi:
                if left_max <= right_max: advance lo, update left_max, add left_max - h[lo]
                else:                     retreat hi, update right_max, add right_max - h[hi]
        """,
        prerequisites=["tp-container-water"], tags=["hard"],
    ))

    P.append(code_problem(
        id="tp-merge-sorted", title="Joining the Columns", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="merge", profile_weight=Q, viz=VIZ,
        statement="Merge two ascending lists into one ascending list. Duplicates are kept.",
        fn_name="merge_sorted", params="a, b", reference=_merge_sorted,
        canonical="""
            def merge_sorted(a, b):
                out, i, j = [], 0, 0
                while i < len(a) and j < len(b):
                    if a[i] <= b[j]:
                        out.append(a[i]); i += 1
                    else:
                        out.append(b[j]); j += 1
                out.extend(a[i:])
                out.extend(b[j:])
                return out
        """,
        visible=[("interleaved", [[1, 3, 5], [2, 4, 6]]), ("disjoint", [[1, 2], [8, 9]])],
        hidden=[("duplicates", [[1, 1], [1, 1]]), ("one empty", [[], [1, 2]]),
                ("negatives", [[-5, 0], [-3, 7]])],
        edges=[("both empty", [[], []])],
        perf=[("200k merge", [list(range(0, 200000, 2)), list(range(1, 200000, 2))])],
        time_complexity="O(n + m)", space_complexity="O(n + m)",
        failures=["Concatenating and re-sorting is O((n+m) log(n+m)) — correct, slower",
                  "Forgetting the leftover tail of whichever list is longer"],
        nudge="Two readers, one writer. Always take the smaller head.",
        visual="Two queues feed one line; the shorter head steps forward each time.",
        pseudocode="while both: take smaller head; then extend with both remainders",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tp-squares-sorted", title="Squares of the Ordered", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="converging",
        profile_weight=Q, viz=VIZ,
        statement="""
            `nums` is sorted ascending and may contain negatives. Return the squares of
            every value, sorted ascending, in O(n).
        """,
        fn_name="sorted_squares", params="nums", reference=_squares_sorted,
        canonical="""
            def sorted_squares(nums):
                out = [0] * len(nums)
                lo, hi = 0, len(nums) - 1
                for pos in range(len(nums) - 1, -1, -1):    # fill from the back
                    if abs(nums[lo]) > abs(nums[hi]):
                        out[pos] = nums[lo] ** 2
                        lo += 1
                    else:
                        out[pos] = nums[hi] ** 2
                        hi -= 1
                return out
        """,
        visible=[("mixed", [[-4, -1, 0, 3, 10]]), ("all negative", [[-7, -3, -1]])],
        hidden=[("all positive", [[1, 2, 3]]), ("zeros", [[0, 0]]),
                ("symmetric", [[-2, 2]])],
        edges=[("empty", [[]]), ("single", [[-5]])],
        perf=[("200k", [list(range(-100000, 100000))])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Squaring then sorting is O(n log n) — correct but not what was asked",
                  "Filling from the front instead of the back"],
        nudge="The largest square is always at one of the two ends. Fill the output "
              "backwards.",
        visual="The biggest magnitude lives at an end; take it, place it last, shrink.",
        pseudocode="fill out[] from the back, taking whichever end has larger |value|",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tp-is-subsequence", title="Threading the Needle", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="fast_slow",
        secondary=["STRING"], profile_weight=Q, viz=VIZ, cmp="bool",
        statement="""
            Return `True` if `small` is a subsequence of `big` — every character of
            `small` appears in `big` in the same relative order, not necessarily
            contiguously.
        """,
        fn_name="is_subsequence", params="small, big", reference=_is_subsequence,
        canonical="""
            def is_subsequence(small, big):
                i = 0
                for ch in big:
                    if i < len(small) and small[i] == ch:
                        i += 1
                return i == len(small)
        """,
        visible=[("yes", ["abc", "ahbgdc"]), ("no", ["axc", "ahbgdc"])],
        hidden=[("empty needle", ["", "abc"]), ("identical", ["abc", "abc"]),
                ("repeat chars", ["aab", "aXaXb"])],
        edges=[("empty haystack", ["a", ""]), ("both empty", ["", ""])],
        time_complexity="O(len(big))", space_complexity="O(1)",
        failures=["Requiring contiguity", "Not handling the empty needle as True"],
        nudge="One pointer only advances when it finds its next character.",
        visual="A slow needle advances only on a match; the thread runs straight through.",
        pseudocode="i = 0; for ch in big: if small[i] == ch: i += 1; return i == len(small)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tp-sorted-intersection", title="Where the Roads Meet", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="EASY", family="merge", profile_weight=Q, viz=VIZ,
        statement="""
            Both lists are sorted ascending and may contain duplicates. Return their
            sorted intersection with each value appearing once, using O(1) extra space
            beyond the output.
        """,
        fn_name="sorted_intersection", params="a, b", reference=_sorted_intersection,
        canonical="""
            def sorted_intersection(a, b):
                out, i, j = [], 0, 0
                while i < len(a) and j < len(b):
                    if a[i] == b[j]:
                        if not out or out[-1] != a[i]:
                            out.append(a[i])
                        i += 1
                        j += 1
                    elif a[i] < b[j]:
                        i += 1
                    else:
                        j += 1
                return out
        """,
        visible=[("overlap", [[1, 2, 2, 3], [2, 3, 4]]), ("disjoint", [[1, 2], [8, 9]])],
        hidden=[("all duplicates", [[2, 2, 2], [2, 2]]), ("one empty", [[], [1]]),
                ("negatives", [[-3, -1], [-3, 0]])],
        edges=[("both empty", [[], []])],
        perf=[("200k", [list(range(100000)), list(range(50000, 150000))])],
        time_complexity="O(n + m)", space_complexity="O(1) extra",
        failures=["Using sets is O(n+m) but costs O(n) space",
                  "Emitting duplicates when both lists repeat a value"],
        nudge="Sorted inputs let you walk both lists once, never backwards.",
        visual="Two roads walked in step; equal milestones are shared.",
        pseudocode="advance the smaller head; on equality record once and advance both",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tp-almost-palindrome", title="One Flaw Permitted", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="MEDIUM", family="palindrome",
        secondary=["STRING"], profile_weight=Q, viz=VIZ, cmp="bool",
        statement="""
            Return `True` if `s` can be made a palindrome by deleting **at most one**
            character.
        """,
        fn_name="valid_palindrome_after_removal", params="s",
        reference=_valid_after_one_removal,
        canonical="""
            def valid_palindrome_after_removal(s):
                def is_pal(lo, hi):
                    while lo < hi:
                        if s[lo] != s[hi]:
                            return False
                        lo += 1
                        hi -= 1
                    return True

                lo, hi = 0, len(s) - 1
                while lo < hi:
                    if s[lo] != s[hi]:
                        # spend the single deletion on one side or the other
                        return is_pal(lo + 1, hi) or is_pal(lo, hi - 1)
                    lo += 1
                    hi -= 1
                return True
        """,
        visible=[("delete one", ["abca"]), ("already palindrome", ["aba"])],
        hidden=[("cannot fix", ["abcd"]), ("delete at start", ["deeee"]),
                ("even length", ["abba"]), ("two flaws", ["abcdba"])],
        edges=[("empty", [""]), ("single", ["a"]), ("two different", ["ab"])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Only trying one of the two possible deletions",
                  "Recursing with a remaining-budget counter is a different, harder problem"],
        nudge="At the first mismatch you have exactly two choices. Try both, and only once.",
        visual="Runners meet a mismatch; one steps over the left obstacle, one over the "
               "right. Either path reaching the middle wins.",
        pseudocode="on mismatch: return is_pal(lo+1, hi) or is_pal(lo, hi-1)",
        prerequisites=["tp-valid-palindrome"], tags=["core"],
    ))

    P.append(code_problem(
        id="sec-risk-pairing", title="Pairing the Risk Budget", realm="twin_pointer_pass",
        pattern="TWO_POINTER", difficulty="MEDIUM", family="converging",
        security=True, profile_weight=QS, viz=VIZ,
        statement="""
            `events` holds risk scores sorted ascending. Pair the cheapest remaining event
            with the most expensive one whose combined score does not exceed `cutoff`; if
            the pair is too expensive, drop the most expensive event and try again.

            Return the pairs in the order they were formed, each as `[low, high]`.
        """,
        fn_name="pair_within_budget", params="events, cutoff",
        reference=_partition_sorted_events,
        canonical="""
            def pair_within_budget(events, cutoff):
                lo, hi = 0, len(events) - 1
                pairs = []
                while lo < hi:
                    if events[lo] + events[hi] > cutoff:
                        hi -= 1
                    else:
                        pairs.append([events[lo], events[hi]])
                        lo += 1
                        hi -= 1
                return pairs
        """,
        visible=[("two pairs", [[1, 2, 3, 4, 5, 6], 7]), ("none fit", [[9, 9], 5])],
        hidden=[("all fit", [[1, 1, 1, 1], 10]), ("odd count", [[1, 2, 3], 5]),
                ("exact cutoff", [[2, 3], 5])],
        edges=[("empty", [[], 5]), ("single", [[3], 5])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Advancing both pointers when the pair is rejected"],
        nudge="Sorted plus a budget is a converging-pointer shape.",
        visual="Cheapest and dearest approach each other.", pseudocode=PSEUDO,
        prerequisites=["tp-sorted-pair"], tags=["security", "transfer"],
    ))

    P.append(code_problem(
        id="st-reverse-words", title="Reversing the Chant", realm="stringwood_labyrinth",
        pattern="STRING", difficulty="EASY", family="string_basics", profile_weight=Q,
        statement="""
            Return `s` with its words in reverse order. Collapse all runs of whitespace to
            a single space and strip leading and trailing whitespace.
        """,
        fn_name="reverse_words", params="s", reference=_reverse_words,
        canonical="""
            def reverse_words(s):
                return " ".join(reversed(s.split()))
        """,
        visible=[("classic", ["the sky is blue"]), ("messy spaces", ["  hello   world  "])],
        hidden=[("single word", ["solo"]), ("tabs", ["a\tb"]), ("only spaces", ["    "])],
        edges=[("empty", [""])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Using split(' ') keeps empty strings from repeated spaces",
                  "Reversing the characters instead of the words"],
        nudge="Bare `.split()` already collapses whitespace for you.",
        visual="Tokens lifted out, reordered, re-joined.",
        pseudocode='return " ".join(reversed(s.split()))', tags=["core", "python"],
    ))

    return P
