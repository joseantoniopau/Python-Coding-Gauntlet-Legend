"""Complexity Tower approaches: halve the search space, every time."""
from __future__ import annotations

import bisect

from ._base import code_problem

Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 1.0}
VIZ = {"type": "binary_search", "caption": "Half the world disappears each step."}
PSEUDO = """
lo, hi = 0, len(data) - 1
while lo <= hi:
    mid = (lo + hi) // 2
    hit  -> return mid
    low  -> lo = mid + 1
    high -> hi = mid - 1
"""


def _search(nums, target):
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


def _search_insert(nums, target):
    return bisect.bisect_left(nums, target)


def _first_last(nums, target):
    lo = bisect.bisect_left(nums, target)
    hi = bisect.bisect_right(nums, target)
    return [-1, -1] if lo == hi else [lo, hi - 1]


def _search_rotated(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[lo] <= nums[mid]:              # left half is sorted
            if nums[lo] <= target < nums[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        else:                                   # right half is sorted
            if nums[mid] < target <= nums[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return -1


def _find_min_rotated(nums):
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] > nums[hi]:
            lo = mid + 1
        else:
            hi = mid
    return nums[lo] if nums else None


def _sqrt_floor(n):
    if n < 2:
        return n
    lo, hi = 1, n // 2
    best = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid * mid <= n:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _peak_index(nums):
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] < nums[mid + 1]:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _min_capacity(weights, days):
    if not weights:
        return 0
    lo, hi = max(weights), sum(weights)
    while lo < hi:
        mid = (lo + hi) // 2
        need, load = 1, 0
        for w in weights:
            if load + w > mid:
                need += 1
                load = 0
            load += w
        if need > days:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _count_le(nums, target):
    return bisect.bisect_right(nums, target)


def build() -> list:
    P: list = []
    common = dict(realm="complexity_tower", pattern="BINARY_SEARCH",
                  profile_weight=Q, viz=VIZ)

    P.append(code_problem(
        id="bs-search", title="The Halving Stair", difficulty="EASY",
        family="binary_search", **common,
        statement="""
            `nums` is sorted ascending with distinct values. Return the index of `target`,
            or `-1` if absent. Must be O(log n).
        """,
        fn_name="binary_search", params="nums, target", reference=_search,
        canonical="""
            def binary_search(nums, target):
                lo, hi = 0, len(nums) - 1
                while lo <= hi:                 # <=, or you miss a one-element range
                    mid = (lo + hi) // 2
                    if nums[mid] == target:
                        return mid
                    if nums[mid] < target:
                        lo = mid + 1
                    else:
                        hi = mid - 1
                return -1
        """,
        visible=[("found", [[-1, 0, 3, 5, 9, 12], 9]), ("absent", [[-1, 0, 3], 2])],
        hidden=[("first", [[1, 2, 3], 1]), ("last", [[1, 2, 3], 3]),
                ("single hit", [[5], 5]), ("single miss", [[5], 1])],
        edges=[("empty", [[], 1])],
        perf=[("1M elements", [list(range(1000000)), 999999])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["`while lo < hi` skips the final single-element check",
                  "Setting `lo = mid` instead of `mid + 1` loops forever",
                  "A linear scan passes correctness but not the million-element test"],
        nudge="Every comparison must eliminate half the remaining range, including the "
              "element you just looked at.",
        visual="A staircase where each step drops you into half the tower you were in.",
        pseudocode=PSEUDO, tags=["core"],
    ))

    P.append(code_problem(
        id="bs-search-insert", title="Where It Belongs", difficulty="EASY",
        family="binary_search", **common,
        statement="""
            `nums` is sorted ascending. Return the index of `target`, or the index where it
            would be inserted to keep the list sorted. On duplicates, return the leftmost
            valid position.
        """,
        fn_name="search_insert", params="nums, target", reference=_search_insert,
        canonical="""
            def search_insert(nums, target):
                lo, hi = 0, len(nums)         # hi is EXCLUSIVE here
                while lo < hi:
                    mid = (lo + hi) // 2
                    if nums[mid] < target:
                        lo = mid + 1
                    else:
                        hi = mid
                return lo
        """,
        visible=[("present", [[1, 3, 5, 6], 5]), ("insert middle", [[1, 3, 5, 6], 2])],
        hidden=[("insert front", [[1, 3], 0]), ("insert back", [[1, 3], 9]),
                ("duplicates", [[1, 2, 2, 3], 2])],
        edges=[("empty", [[], 5])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["Mixing an inclusive and exclusive bound in the same loop",
                  "Returning `mid` instead of `lo`"],
        nudge="This is the lower-bound shape: exclusive `hi`, `while lo < hi`, return `lo`.",
        visual="The boundary between 'definitely too small' and 'possibly the answer'.",
        pseudocode="lo, hi = 0, len(nums); while lo < hi: nums[mid] < target ? lo=mid+1 : hi=mid",
        tags=["core"],
    ))

    P.append(code_problem(
        id="bs-first-last", title="The Span of a Rune", difficulty="MEDIUM",
        family="binary_search", **common,
        statement="""
            `nums` is sorted ascending and may contain duplicates. Return
            `[first_index, last_index]` of `target`, or `[-1, -1]` if absent. Must be
            O(log n).
        """,
        fn_name="search_range", params="nums, target", reference=_first_last,
        canonical="""
            def search_range(nums, target):
                import bisect
                lo = bisect.bisect_left(nums, target)    # first index >= target
                hi = bisect.bisect_right(nums, target)   # first index > target
                return [-1, -1] if lo == hi else [lo, hi - 1]
        """,
        visible=[("range", [[5, 7, 7, 8, 8, 10], 8]), ("absent", [[5, 7, 7, 8], 6])],
        hidden=[("single occurrence", [[1, 2, 3], 2]), ("all same", [[2, 2, 2], 2]),
                ("at the ends", [[1, 1, 2], 1])],
        edges=[("empty", [[], 1])],
        perf=[("500k", [[i // 2 for i in range(500000)], 1000])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["Scanning outward from a found index is O(n) when everything matches",
                  "Confusing bisect_left with bisect_right"],
        nudge="Two boundaries, two searches. `bisect` gives you both for free.",
        visual="Two walls: the first element not less than the target, and the first "
               "element greater than it.",
        pseudocode="lo = bisect_left; hi = bisect_right; empty when they coincide",
        tags=["core"],
    ))

    P.append(code_problem(
        id="bs-rotated", title="The Turned Tower", difficulty="MEDIUM",
        family="binary_search", **common,
        statement="""
            `nums` was sorted ascending with distinct values, then rotated at an unknown
            pivot. Return the index of `target`, or `-1`. Must be O(log n).
        """,
        fn_name="search_rotated", params="nums, target", reference=_search_rotated,
        canonical="""
            def search_rotated(nums, target):
                lo, hi = 0, len(nums) - 1
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if nums[mid] == target:
                        return mid
                    if nums[lo] <= nums[mid]:                  # left half is sorted
                        if nums[lo] <= target < nums[mid]:
                            hi = mid - 1
                        else:
                            lo = mid + 1
                    else:                                      # right half is sorted
                        if nums[mid] < target <= nums[hi]:
                            lo = mid + 1
                        else:
                            hi = mid - 1
                return -1
        """,
        visible=[("in right half", [[4, 5, 6, 7, 0, 1, 2], 0]),
                 ("absent", [[4, 5, 6, 7, 0, 1, 2], 3])],
        hidden=[("no rotation", [[1, 2, 3], 3]), ("pivot at start", [[3, 1], 1]),
                ("single", [[1], 1]), ("target is pivot", [[5, 1, 3], 5])],
        edges=[("empty", [[], 1])],
        perf=[("500k rotated", [list(range(250000, 500000)) + list(range(250000)), 7])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["Forgetting that exactly one half is always sorted",
                  "Using `<` instead of `<=` when testing which half is sorted, which "
                  "breaks on two-element ranges"],
        nudge="At every step one half is definitely sorted. Decide whether the target "
              "falls inside that half; if not, it must be in the other.",
        visual="The tower was cut and re-stacked. One of the two halves is still in order "
               "— find it, then decide which side to keep.",
        pseudocode="""
            identify the sorted half via nums[lo] <= nums[mid]
            if target lies within that sorted half: search it
            else: search the other half
        """,
        prerequisites=["bs-search"], tags=["core"],
    ))

    P.append(code_problem(
        id="bs-find-min-rotated", title="The Lowest Stone", difficulty="MEDIUM",
        family="binary_search", **common,
        statement="""
            `nums` was sorted ascending with distinct values then rotated. Return the
            smallest value in O(log n).
        """,
        fn_name="find_min", params="nums", reference=_find_min_rotated,
        canonical="""
            def find_min(nums):
                lo, hi = 0, len(nums) - 1
                while lo < hi:
                    mid = (lo + hi) // 2
                    if nums[mid] > nums[hi]:
                        lo = mid + 1        # the dip is strictly right of mid
                    else:
                        hi = mid            # mid could BE the dip; keep it
                return nums[lo] if nums else None
        """,
        visible=[("rotated", [[3, 4, 5, 1, 2]]), ("not rotated", [[1, 2, 3]])],
        hidden=[("single", [[7]]), ("two rotated", [[2, 1]]),
                ("rotate by one", [[5, 1, 2, 3, 4]])],
        edges=[("empty", [[]])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["Comparing against `nums[lo]` instead of `nums[hi]` misreads the "
                  "unrotated case",
                  "Setting `hi = mid - 1` can step over the minimum itself"],
        nudge="Compare the middle to the right end, not the left. The right end tells you "
              "which side holds the dip.",
        visual="A hill that wraps around. The dip is wherever the descent lands.",
        pseudocode="nums[mid] > nums[hi] -> lo = mid + 1 else hi = mid",
        prerequisites=["bs-search"], tags=["core"],
    ))

    P.append(code_problem(
        id="bs-sqrt", title="The Root of the Tower", difficulty="EASY",
        family="binary_search", **common,
        statement="""
            Return the integer square root of `n` — the largest integer whose square does
            not exceed `n`. Do not use `**0.5`, `math.sqrt` or `math.isqrt`.
        """,
        fn_name="int_sqrt", params="n", reference=_sqrt_floor,
        canonical="""
            def int_sqrt(n):
                if n < 2:
                    return n
                lo, hi, best = 1, n // 2, 1
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if mid * mid <= n:
                        best = mid            # feasible; try for bigger
                        lo = mid + 1
                    else:
                        hi = mid - 1
                return best
        """,
        visible=[("perfect square", [16]), ("not perfect", [8])],
        hidden=[("zero", [0]), ("one", [1]), ("large", [2147395600]),
                ("just under", [15])],
        edges=[("two", [2])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["Searching up to `n` instead of `n // 2` still works but is wasteful",
                  "Returning `lo` rather than the last feasible `mid`"],
        nudge="Binary search on the *answer*, not on an array. Keep the last value that "
              "was still feasible.",
        visual="Guess a height; if its square fits under the ceiling, aim higher.",
        pseudocode="mid*mid <= n -> best = mid, lo = mid+1  else hi = mid-1",
        tags=["core"],
    ))

    P.append(code_problem(
        id="bs-peak", title="Finding the Summit", difficulty="MEDIUM",
        family="binary_search", **common,
        statement="""
            `nums` strictly increases then strictly decreases. Return the index of the
            peak in O(log n).
        """,
        fn_name="peak_index", params="nums", reference=_peak_index,
        canonical="""
            def peak_index(nums):
                lo, hi = 0, len(nums) - 1
                while lo < hi:
                    mid = (lo + hi) // 2
                    if nums[mid] < nums[mid + 1]:
                        lo = mid + 1        # still climbing
                    else:
                        hi = mid            # mid may be the peak
                return lo
        """,
        visible=[("classic", [[0, 2, 5, 3, 1]]), ("short", [[1, 3, 2]])],
        hidden=[("peak near start", [[1, 9, 8, 7]]), ("peak near end", [[1, 2, 3, 0]]),
                ("three", [[0, 5, 1]])],
        edges=[("minimum length", [[0, 1, 0]])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["Comparing to `mid - 1` needs a guard at index 0",
                  "`hi = mid - 1` can step over the peak"],
        nudge="Compare `mid` to its right neighbour. Rising means the peak is strictly "
              "ahead.",
        visual="You feel the slope under your feet and walk uphill by halves.",
        pseudocode="nums[mid] < nums[mid+1] -> lo = mid + 1 else hi = mid",
        tags=["core"],
    ))

    P.append(code_problem(
        id="bs-min-capacity", title="The Sufficient Vessel", difficulty="HARD",
        family="binary_search_answer", **common,
        statement="""
            Packages with the given `weights` must ship in their original order within
            `days` days. Each day loads consecutive packages up to the ship's capacity.

            Return the smallest capacity that makes it possible.
        """,
        fn_name="min_capacity", params="weights, days", reference=_min_capacity,
        canonical="""
            def min_capacity(weights, days):
                if not weights:
                    return 0
                lo, hi = max(weights), sum(weights)   # bounds of any workable capacity

                def days_needed(capacity):
                    need, load = 1, 0
                    for w in weights:
                        if load + w > capacity:
                            need += 1
                            load = 0
                        load += w
                    return need

                while lo < hi:
                    mid = (lo + hi) // 2
                    if days_needed(mid) > days:
                        lo = mid + 1        # too slow; need a bigger ship
                    else:
                        hi = mid            # feasible; try smaller
                return lo
        """,
        visible=[("classic", [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5]),
                 ("one day", [[1, 2, 3], 1])],
        hidden=[("each day one package", [[3, 2, 2, 4, 1, 4], 6]),
                ("two days", [[1, 2, 3, 1, 1], 4]),
                ("single package", [[7], 1]),
                ("more days than packages", [[1, 2], 9])],
        edges=[("empty", [[], 3])],
        perf=[("40k packages", [[(i % 97) + 1 for i in range(40000)], 200])],
        time_complexity="O(n log(sum))", space_complexity="O(1)",
        failures=["Searching below `max(weights)` — no ship can carry a single package "
                  "heavier than its capacity",
                  "Feasibility is monotonic; without that property binary search is invalid",
                  "Trying every capacity linearly is far too slow"],
        nudge="Binary search over the answer. The predicate 'can I finish in `days` days at "
              "capacity C' is false then true — monotonic, which is exactly what binary "
              "search needs.",
        visual="Guess a ship size, simulate the loading, and halve the range based on "
               "whether it was enough.",
        pseudocode="""
            lo = max(weights), hi = sum(weights)
            while lo < hi:
                feasible(mid) ? hi = mid : lo = mid + 1
        """,
        prerequisites=["bs-sqrt"], tags=["hard"],
    ))

    P.append(code_problem(
        id="bs-count-le", title="Counting Below the Line", difficulty="EASY",
        family="binary_search", **common,
        statement="""
            `nums` is sorted ascending. Return how many values are less than or equal to
            `target`, in O(log n).
        """,
        fn_name="count_at_most", params="nums, target", reference=_count_le,
        canonical="""
            def count_at_most(nums, target):
                import bisect
                return bisect.bisect_right(nums, target)
        """,
        visible=[("some", [[1, 2, 2, 3], 2]), ("none", [[5, 6], 1])],
        hidden=[("all", [[1, 2], 9]), ("exact boundary", [[1, 2, 3], 3]),
                ("duplicates", [[2, 2, 2], 2])],
        edges=[("empty", [[], 5])],
        time_complexity="O(log n)", space_complexity="O(1)",
        failures=["`bisect_left` would exclude values equal to the target"],
        nudge="The insertion point to the *right* of every equal value is the count.",
        visual="A wall placed just past the last matching element.",
        pseudocode="bisect.bisect_right(nums, target)",
        tags=["core"],
    ))

    return P
