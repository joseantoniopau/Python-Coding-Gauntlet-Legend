"""Question generation system (spec section 48).

A template family is a *shape* plus a set of *skins*. A skin changes the surface
story, the element type, the output format and at least one constraint — never
just the variable names, because renaming does not exercise recognition.

Every generated problem carries a canonical solution and reference-derived tests,
and is run through the same validator as authored content. Anything that fails
validation is rejected rather than shipped.
"""
from __future__ import annotations

from collections import Counter

from .families._base import code_problem

# --- skin vocabulary ---------------------------------------------------------

SKINS = [
    {"key": "telemetry", "noun": "events", "unit": "event", "realm_hint": "security",
     "story": "a stream of authentication events", "security": True},
    {"key": "market", "noun": "prices", "unit": "price", "realm_hint": "general",
     "story": "a day's sequence of trade prices", "security": False},
    {"key": "sensors", "noun": "readings", "unit": "reading", "realm_hint": "general",
     "story": "a run of sensor readings", "security": False},
    {"key": "guild", "noun": "quests", "unit": "quest", "realm_hint": "general",
     "story": "the guild's quest log", "security": False},
    {"key": "caravan", "noun": "cargo", "unit": "crate", "realm_hint": "general",
     "story": "the crates loaded onto a caravan", "security": False},
]


def _rng(seed: int):
    """Deterministic small PRNG so the corpus is byte-identical across builds."""
    state = seed & 0xFFFFFFFF

    def nxt(lo, hi):
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return lo + state % (hi - lo + 1)
    return nxt


# =============================================================================
# Template family 1 — fixed-size window aggregate
# =============================================================================

def _tpl_fixed_window(skin, index):
    agg = ["sum", "max", "min"][index % 3]
    fn = f"window_{agg}_{skin['key']}"

    if agg == "sum":
        def ref(values, k):
            if k <= 0 or not values:
                return 0
            k = min(k, len(values))
            window = sum(values[:k])
            best = window
            for i in range(k, len(values)):
                window += values[i] - values[i - k]
                best = max(best, window)
            return best
        canonical = f"""
            def {fn}(values, k):
                if k <= 0 or not values:
                    return 0
                k = min(k, len(values))
                window = sum(values[:k])
                best = window
                for i in range(k, len(values)):
                    window += values[i] - values[i - k]
                    best = max(best, window)
                return best
        """
        ask = f"the largest **total** across any `k` consecutive {skin['noun']}"
    elif agg == "max":
        def ref(values, k):
            if k <= 0 or not values:
                return []
            k = min(k, len(values))
            return [max(values[i:i + k]) for i in range(len(values) - k + 1)]
        canonical = f"""
            def {fn}(values, k):
                from collections import deque
                if k <= 0 or not values:
                    return []
                k = min(k, len(values))
                window, out = deque(), []
                for i, value in enumerate(values):
                    while window and values[window[-1]] <= value:
                        window.pop()
                    window.append(i)
                    if window[0] <= i - k:
                        window.popleft()
                    if i >= k - 1:
                        out.append(values[window[0]])
                return out
        """
        ask = (f"the **maximum of every** window of `k` consecutive {skin['noun']}, "
               "left to right")
    else:
        def ref(values, k):
            if k <= 0 or not values:
                return []
            k = min(k, len(values))
            return [min(values[i:i + k]) for i in range(len(values) - k + 1)]
        canonical = f"""
            def {fn}(values, k):
                from collections import deque
                if k <= 0 or not values:
                    return []
                k = min(k, len(values))
                window, out = deque(), []
                for i, value in enumerate(values):
                    while window and values[window[-1]] >= value:
                        window.pop()
                    window.append(i)
                    if window[0] <= i - k:
                        window.popleft()
                    if i >= k - 1:
                        out.append(values[window[0]])
                return out
        """
        ask = f"the **minimum of every** window of `k` consecutive {skin['noun']}"

    rnd = _rng(1000 + index)
    sample = [rnd(0, 40) for _ in range(12)]
    return dict(
        fn_name=fn, params="values, k", reference=ref, canonical=canonical,
        pattern="SLIDING_WINDOW", realm="sliding_window_marsh",
        title=f"Framed {skin['unit'].title()}s",
        statement=f"""
            You are given {skin['story']} as a list of numbers, and a window size `k`.

            Return {ask}.

            If `k` exceeds the number of {skin['noun']}, treat the window as the whole
            list. If `k` is not positive, return an empty result.
        """,
        visible=[("sample", [sample, 3]), ("short window", [sample[:5], 2])],
        hidden=[("k of one", [sample, 1]), ("k equals length", [sample[:4], 4]),
                ("k exceeds", [sample[:3], 10]), ("flat", [[7] * 6, 3])],
        edges=[("empty", [[], 3]), ("k zero", [sample[:3], 0])],
        perf=[("50k", [[i % 97 for i in range(50000)], 250])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["Recomputing the aggregate per window is O(n·k)",
                  "Emitting a result before the first window is full",
                  "Forgetting the k-exceeds-length case"],
        nudge="A fixed-width frame: one element enters, one leaves. Never re-scan the "
              "middle.",
        visual="A glowing frame of width k slides right one position at a time.",
        pseudocode="add the entering element, remove the leaving element, record",
        family="fixed_window", security=skin["security"],
        viz={"type": "sliding_window", "caption": "One in, one out."},
    )


# =============================================================================
# Template family 2 — complement pair search
# =============================================================================

def _tpl_pair(skin, index):
    mode = ["indices", "exists", "count"][index % 3]
    fn = f"pair_{mode}_{skin['key']}"

    if mode == "indices":
        def ref(values, target):
            seen = {}
            for i, v in enumerate(values):
                if target - v in seen:
                    return [seen[target - v], i]
                seen[v] = i
            return []
        body = ("return the **indices** of the two that sum to `target`, smaller first, "
                "or `[]` if no such pair exists")
        canonical = f"""
            def {fn}(values, target):
                seen = {{}}
                for i, value in enumerate(values):
                    if target - value in seen:
                        return [seen[target - value], i]
                    seen[value] = i
                return []
        """
        cmp = "exact"
    elif mode == "exists":
        def ref(values, target):
            seen = set()
            for v in values:
                if target - v in seen:
                    return True
                seen.add(v)
            return False
        body = "return `True` if **any** two of them sum to `target`"
        canonical = f"""
            def {fn}(values, target):
                seen = set()
                for value in values:
                    if target - value in seen:
                        return True
                    seen.add(value)
                return False
        """
        cmp = "bool"
    else:
        def ref(values, target):
            seen, total = Counter(), 0
            for v in values:
                total += seen[target - v]
                seen[v] += 1
            return total
        body = ("return **how many index pairs** `(i, j)` with `i < j` sum to `target`; "
                "duplicates count separately")
        canonical = f"""
            def {fn}(values, target):
                from collections import Counter
                seen = Counter()
                total = 0
                for value in values:
                    total += seen[target - value]
                    seen[value] += 1
                return total
        """
        cmp = "exact"

    rnd = _rng(2000 + index)
    sample = [rnd(-20, 40) for _ in range(14)]
    target = sample[2] + sample[7]
    return dict(
        fn_name=fn, params="values, target", reference=ref, canonical=canonical,
        pattern="HASH_MAP", realm="hashmap_highlands",
        title=f"Matched {skin['unit'].title()}s",
        statement=f"""
            Given numeric values drawn from {skin['story']} and a `target`, {body}.

            A value may not pair with itself unless it genuinely appears twice.
        """,
        visible=[("sample", [sample, target]), ("no pair", [[1, 2, 3], 1000])],
        hidden=[("negatives", [[-5, 3, 8, -3], 0]), ("duplicates", [[4, 4, 4], 8]),
                ("zeroes", [[0, 0, 5], 0]), ("first and last", [[9, 1, 1, 1], 10])],
        edges=[("empty", [[], 5]), ("single", [[5], 10])],
        perf=[("60k", [list(range(60000)), 119997])],
        cmp=cmp, time_complexity="O(n)", space_complexity="O(n)",
        failures=["Nested loops time out at scale",
                  "Recording a value before checking its complement lets it pair with "
                  "itself"],
        nudge="Ask 'have I already seen what completes this pair?' — a membership "
              "question, therefore a dict or set.",
        visual="One left-to-right pass; each value looks for its complement among what "
               "came before.",
        pseudocode="for value: check complement in seen; then add value to seen",
        family="two_sum", security=skin["security"],
        viz={"type": "hash_map", "caption": "Each value unlocks its complement's vault."},
    )


# =============================================================================
# Template family 3 — at-most-K-distinct window
# =============================================================================

def _tpl_k_distinct(skin, index):
    want_span = index % 2 == 0
    fn = f"{'longest' if want_span else 'count'}_k_distinct_{skin['key']}"

    if want_span:
        def ref(items, k):
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
        ask = "the **length of the longest** contiguous run"
        canonical = f"""
            def {fn}(items, k):
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
        """
    else:
        def ref(items, k):
            counts, left, total = Counter(), 0, 0
            for right, item in enumerate(items):
                counts[item] += 1
                while len(counts) > k:
                    counts[items[left]] -= 1
                    if not counts[items[left]]:
                        del counts[items[left]]
                    left += 1
                total += right - left + 1
            return total
        ask = "the **number of** contiguous runs"
        canonical = f"""
            def {fn}(items, k):
                from collections import Counter
                counts = Counter()
                left = total = 0
                for right, item in enumerate(items):
                    counts[item] += 1
                    while len(counts) > k:
                        counts[items[left]] -= 1
                        if counts[items[left]] == 0:
                            del counts[items[left]]
                        left += 1
                    total += right - left + 1   # every window ending at `right`
                return total
        """

    labels = ["alpha", "beta", "gamma", "delta"]
    rnd = _rng(3000 + index)
    sample = [labels[rnd(0, 3)] for _ in range(14)]
    return dict(
        fn_name=fn, params="items, k", reference=ref, canonical=canonical,
        pattern="SLIDING_WINDOW", realm="sliding_window_marsh",
        title=f"Bounded {skin['unit'].title()} Variety",
        statement=f"""
            You are given {skin['story']} as a list of category labels, and a limit `k`.

            Return {ask} containing at most `k` distinct categories.

            When `k` is `0` the answer is `0`.
        """,
        visible=[("sample", [sample, 2]), ("k of one", [sample[:6], 1])],
        hidden=[("k zero", [sample[:4], 0]), ("k exceeds variety", [sample, 99]),
                ("all identical", [["alpha"] * 6, 1]),
                ("alternating", [["a", "b"] * 5, 2])],
        edges=[("empty", [[], 2]), ("single", [["alpha"], 1])],
        perf=[("60k", [[labels[i % 4] for i in range(60000)], 3])],
        time_complexity="O(n)", space_complexity="O(k)",
        failures=["Leaving zero-count keys in the dict, so `len(counts)` never drops",
                  "Shrinking with `if` instead of `while`",
                  "Not handling k == 0"],
        nudge="`len(counts)` is the constraint check, and it is only honest if you delete "
              "keys the moment they hit zero.",
        visual="Counters float above each item inside the frame; a counter reaching zero "
               "closes its vault.",
        pseudocode="expand right; while too many distinct: shrink left; record",
        family="window_k_distinct", security=skin["security"],
        viz={"type": "sliding_window", "caption": "LEFT, RIGHT, COUNTS, CONSTRAINT, BEST."},
    )


# =============================================================================
# Template family 4 — frequency ranking
# =============================================================================

def _tpl_frequency(skin, index):
    mode = ["top_k", "unique_first", "threshold"][index % 3]
    fn = f"{mode}_{skin['key']}"

    if mode == "top_k":
        def ref(items, k):
            return [v for v, _ in Counter(items).most_common(k)]
        ask = f"the `k` most frequent {skin['noun']}, most frequent first"
        canonical = f"""
            def {fn}(items, k):
                from collections import Counter
                return [value for value, _ in Counter(items).most_common(k)]
        """
        params, cmp = "items, k", "set"
        visible = [("sample", [["a", "b", "a", "c", "a", "b"], 2]),
                   ("single", [["z"], 1])]
        hidden = [("k exceeds", [["a", "b"], 9]), ("k zero", [["a"], 0]),
                  ("all distinct", [["a", "b", "c"], 2])]
        edges = [("empty", [[], 2])]
    elif mode == "unique_first":
        def ref(items):
            counts = Counter(items)
            for i, item in enumerate(items):
                if counts[item] == 1:
                    return i
            return -1
        ask = (f"the index of the first {skin['unit']} that appears exactly once, or `-1` "
               "if every one repeats")
        canonical = f"""
            def {fn}(items):
                from collections import Counter
                counts = Counter(items)
                for i, item in enumerate(items):
                    if counts[item] == 1:
                        return i
                return -1
        """
        params, cmp = "items", "exact"
        visible = [("middle", [["a", "b", "a", "c"]]), ("none", [["a", "a"]])]
        hidden = [("first is unique", [["z", "a", "a"]]), ("last", [["a", "a", "z"]]),
                  ("all unique", [["a", "b"]])]
        edges = [("empty", [[]]), ("single", [["solo"]])]
    else:
        def ref(items, threshold):
            return sorted(v for v, c in Counter(items).items() if c >= threshold)
        ask = (f"the sorted {skin['noun']} appearing at least `threshold` times")
        canonical = f"""
            def {fn}(items, threshold):
                from collections import Counter
                counts = Counter(items)
                return sorted(value for value, count in counts.items()
                              if count >= threshold)
        """
        params, cmp = "items, threshold", "exact"
        visible = [("two over", [["a", "a", "b", "b", "c"], 2]),
                   ("none", [["a", "b"], 5])]
        hidden = [("threshold one", [["a", "b"], 1]),
                  ("exact boundary", [["a", "a"], 2]),
                  ("all same", [["x"] * 5, 3])]
        edges = [("empty", [[], 1]), ("threshold zero", [["a"], 0])]

    return dict(
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        pattern="HASH_MAP", realm="hashmap_highlands",
        title=f"Weighing the {skin['unit'].title()}s",
        statement=f"""
            You are given {skin['story']} as a list of labels.

            Return {ask}.
        """,
        visible=visible, hidden=hidden, edges=edges, cmp=cmp,
        time_complexity="O(n log n)", space_complexity="O(n)",
        failures=["Calling `.count()` inside a loop makes it quadratic",
                  "Forgetting an empty input"],
        nudge="One `Counter`, then read from it. Never recount inside a loop.",
        visual="Each label's tally rises as you pass; the answer is read off the board.",
        pseudocode="counts = Counter(items); derive the answer from counts",
        family="counting", security=skin["security"],
        viz={"type": "hash_map", "caption": "One vault per label."},
    )


# =============================================================================
# Template family 5 — best contiguous run (Kadane skins)
# =============================================================================

def _tpl_best_run(skin, index):
    mode = ["max_sum", "max_len_positive", "min_sum"][index % 3]
    fn = f"{mode}_{skin['key']}"

    if mode == "max_sum":
        def ref(values):
            if not values:
                return 0
            best = cur = values[0]
            for v in values[1:]:
                cur = max(v, cur + v)
                best = max(best, cur)
            return best
        ask = "the **largest sum** of any non-empty contiguous run (`0` if the list is empty)"
        canonical = f"""
            def {fn}(values):
                if not values:
                    return 0
                best = current = values[0]
                for value in values[1:]:
                    current = max(value, current + value)
                    best = max(best, current)
                return best
        """
    elif mode == "max_len_positive":
        def ref(values):
            best = run = 0
            for v in values:
                run = run + 1 if v > 0 else 0
                best = max(best, run)
            return best
        ask = "the **length of the longest** contiguous run of strictly positive values"
        canonical = f"""
            def {fn}(values):
                best = run = 0
                for value in values:
                    run = run + 1 if value > 0 else 0
                    best = max(best, run)
                return best
        """
    else:
        def ref(values):
            if not values:
                return 0
            best = cur = values[0]
            for v in values[1:]:
                cur = min(v, cur + v)
                best = min(best, cur)
            return best
        ask = "the **smallest sum** of any non-empty contiguous run (`0` if empty)"
        canonical = f"""
            def {fn}(values):
                if not values:
                    return 0
                best = current = values[0]
                for value in values[1:]:
                    current = min(value, current + value)
                    best = min(best, current)
                return best
        """

    rnd = _rng(5000 + index)
    sample = [rnd(-15, 15) for _ in range(14)]
    return dict(
        fn_name=fn, params="values", reference=ref, canonical=canonical,
        pattern="DP", realm="dp_ruins",
        title=f"Best Stretch of {skin['unit'].title()}s",
        statement=f"""
            You are given {skin['story']} as a list of numbers, which may be negative.

            Return {ask}.
        """,
        visible=[("sample", [sample]), ("all positive", [[1, 2, 3]])],
        hidden=[("all negative", [[-3, -1, -2]]), ("single", [[5]]),
                ("zeros", [[0, 0, 0]]), ("one deep dip", [[5, -50, 6]])],
        edges=[("empty", [[]])],
        perf=[("150k", [[(i % 37) - 18 for i in range(150000)]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Seeding the accumulator at 0 breaks on all-negative input",
                  "Checking every subrange is O(n^2)"],
        nudge="At each element decide whether the running total is still helping you, or "
              "whether starting fresh here is better.",
        visual="A running accumulator that resets whenever carrying the past costs more "
               "than beginning again.",
        pseudocode="current = better_of(value, current + value); track the best current",
        family="dp_linear", security=skin["security"],
        viz={"type": "dp", "caption": "Solved positions light and are reused."},
    )


TEMPLATES = [
    ("fixed_window", _tpl_fixed_window),
    ("pair", _tpl_pair),
    ("k_distinct", _tpl_k_distinct),
    ("frequency", _tpl_frequency),
    ("best_run", _tpl_best_run),
]

DIFF_BY_TEMPLATE = {
    "fixed_window": "EASY", "pair": "EASY", "k_distinct": "MEDIUM",
    "frequency": "EASY", "best_run": "MEDIUM",
}


def generate(per_template: int = 8) -> list:
    """Emit generated variants. The caller validates before shipping any of them."""
    out = []
    index = 0
    for name, builder in TEMPLATES:
        for i in range(per_template):
            skin = SKINS[i % len(SKINS)]
            spec = builder(skin, index)
            index += 1
            profile = ({"QUORA": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 2.5}
                       if spec.pop("security", False)
                       else {"QUORA": 1.5, "GENERAL_SWE": 1.5, "SECURITY_ENGINEERING": 1.0})
            security = skin["security"]
            out.append(code_problem(
                id=f"gen-{name}-{skin['key']}-{i}",
                difficulty=DIFF_BY_TEMPLATE[name],
                source_type="GENERATED_VARIANT",
                provenance="Authored variant generated from a template family. Never "
                           "presented as a question any company has asked.",
                security=security,
                profile_weight=profile,
                tags=["generated", "variant", name],
                encounter="CODE_BATTLE",
                **spec,
            ))
    return out
