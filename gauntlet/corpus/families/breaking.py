"""Breaking and pricing: the two questions an interviewer actually listens for.

Every other family in this corpus asks "can you make it work". This one asks the
two follow-ups that decide the room:

  BREAK_IT          "what input breaks this?"
  COMPLEXITY_MATCH  "what does it cost?"

Neither needs a line of Python produced from a blank screen, which is the whole
point. This player reads code far better than he writes it, and these two skills
travel entirely on reading. They are also the two he already has at work — a
security engineer spends his day asking what input nobody tested — so this
family is where the game meets him at full strength instead of at his weakness.

BREAK_IT is graded by running BOTH implementations on whatever the player types.
That imposes a hard authoring rule, and every problem below obeys it: the honest
spell and the suspect spell agree on every ordinary input and diverge on exactly
one class. Typing `[]` at everything does not work here, because most of these
handle the empty list perfectly well. The class each one teaches is recorded in
`tags` as `break:<class>`, so failure analysis can see which class keeps winning.

COMPLEXITY_MATCH prices three or four snippets at once, and the "at once" is the
design. A lone snippet can be priced by counting visible `for` keywords; a set of
near-identical snippets cannot, because the differences are all in the lines that
do not look like loops. The classics that look linear and are not — `count()`
inside a loop, `in` against a list, `+=` on a string, a slice taken per
iteration — each appear beside their honest twin.

Two local constructors live here rather than in `_base`. `_base` predates the
puzzle encounters and has no builder for them; adding one there is a change to a
file three other families depend on, so the puzzle scaffolding stays local until
a second puzzle family wants it.

Placement note. `pattern` is TESTING or COMPLEXITY, because that is what decides
which oracle hint the player gets and what a miss is blamed on. But those two
patterns are not permitted until chapters V and VI, and a beginner needs to meet
"what breaks this?" long before then. So `spaced_repetition_family` is always a
family that an early chapter already claims, and `curriculum.is_permitted` lets a
claimed family through a pattern gate. That is what puts an empty-list hunt in
chapter I instead of chapter X.
"""
from __future__ import annotations

from ._base import code_problem, dedent
from ..schema import Problem, TARGET_SECONDS, build_hint_tree

# Weighted toward the profile this family flatters. Finding the input nobody
# tested is this player's day job; the game should notice that he is good at it.
Q = {"SECURITY_ENGINEERING": 2.0, "GENERAL_SWE": 1.4, "PRACTICAL": 1.4}

_BREAK_FAILURES = [
    "Probing only the middle of the input space",
    "Assuming the input is never empty and never has exactly one item",
    "Assuming values are positive, distinct and already in order",
    "Testing what the code appears to do instead of what the contract says",
]

_PRICE_FAILURES = [
    "Counting loops instead of counting work",
    "Assuming one line is one step",
    "Forgetting that a slice copies",
    "Forgetting that `in` against a list is a scan",
]

_CHECKLIST = """
empty          one item        duplicates      all identical
negatives      zero            the exact boundary
already sorted reversed        the value at the very end
"""

_BREAK_VISUAL = (
    "Run the honest contract in your head on the ugliest input you can justify. "
    "Then run the suspect spell on that same input and watch for the first place "
    "the two stories differ."
)

# Rung 4. Narrows to the class without naming the value, so the rung below
# Phoenix still leaves the player something to find.
_CLASS_HINT = {
    "empty": "Every `sum`, every `len`, every loop has a degenerate case. What is "
             "the smallest input that is still legal?",
    "single": "This one survives the empty list. Look at the next smallest input.",
    "duplicates": "Nothing in the contract says the values are distinct.",
    "negatives": "Nothing in the contract says the values are positive. What "
                 "happens at the wrong end of the sorted order?",
    "zero": "Zero is a value. It is also false. Which of those is the code "
            "reacting to?",
    "boundary": "Read the comparison operator, then read the contract's word for "
                "it again. `exceeds` and `at least` are not the same edge.",
    "identical": "What does the code do when two neighbours are equal, and what "
                 "does the contract say should happen?",
    "already_sorted": "The input has been rotated some number of times. Some "
                      "number includes none.",
    "reversed": "The contract says buy first, sell later. Find an input where the "
                "cheapest moment comes after the dearest.",
    "off_by_one": "Count the iterations that loop actually performs, then compare "
                  "it with the number of positions that need comparing.",
    "integer_division": "Python's `//` rounds down, toward minus infinity. "
                        "Downward and toward-zero are the same direction only on "
                        "one side of the number line.",
    "mutation": "The loop is walking a list by position while the body changes "
                "what is at each position. Where does the walker end up?",
    "delete_at_zero": "Subtracting one from a count is not the same as removing "
                      "the entry. When do those two stories differ?",
    "visited_on_pop": "A node can be put on the queue more than once before it is "
                      "ever taken off. Find a shape where that happens.",
    "negative_zero_slice": "Work out what `items[-n:]` means when `n` is 0. Write "
                           "the slice out with the number substituted in.",
    "partial_tail": "The loop's stopping point assumes the groups come out even.",
    "loop_bound": "The search keeps narrowing until `lo` and `hi` meet. What does "
                  "it do about the one position they meet at?",
    "half_way": "The contract names one exact value and says which way it goes. "
                "Try that value.",
    "overlap": "Two appearances of the piece can share characters. Build a text "
               "where they do.",
    "case": "The contract says letter case is ignored. Find the place the code "
            "forgot that.",
}


def _break_it(*, pid, title, realm, difficulty, family, klass, contract,
              fn, params, reference, honest, flawed, visible, hidden, edges,
              probes, explanation, nudge, worked, secondary=(),
              time="O(n)", space="O(1)", tags=()) -> Problem:
    """One BREAK_IT encounter.

    `visible` and `hidden` are inputs both spells agree on: they become the
    ordinary tests, and they are what tells the player what "correct" means
    before he goes hunting for what is not. `edges` are the inputs that expose
    the flaw; they are hidden and unrevealed, so reading the problem never hands
    over the answer. `probes` is the same thing as an executable answer key —
    argument lists that genuinely break the suspect spell.
    """
    statement = (dedent(contract).rstrip()
                 + "\n\nFind one input that proves the suspect spell does not do that.\n")
    p = code_problem(
        id=pid, title=title, realm=realm, pattern="TESTING", difficulty=difficulty,
        statement=statement, fn_name=fn, params=params, reference=reference,
        canonical=honest, visible=visible, hidden=hidden, edges=edges,
        time_complexity=time, space_complexity=space,
        secondary=list(secondary), family=family, encounter="BREAK_IT",
        profile_weight=Q, failures=_BREAK_FAILURES, nudge=nudge,
        visual=_BREAK_VISUAL, pseudocode=_CHECKLIST,
        fragment="```\n" + _CLASS_HINT[klass] + "\n```",
        # The suspect spell is what the player is staring at, so it is also what
        # the editor would hold if this ever renders outside the puzzle UI.
        starter_code=flawed,
        tags=["puzzle:break_it", "break:" + klass] + list(tags),
    )
    p.mcq = {"flawed_code": dedent(flawed),
             "explanation": dedent(explanation),
             "probes": [list(args) for args in probes]}
    # Phoenix has to end in a worked solution, but for this encounter the worked
    # solution is the breaking input and why it breaks — not the honest source,
    # which would give the answer away by diff two rungs earlier.
    p.hint_tree[-1]["body"] = dedent(worked)
    return p


_LADDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"]


def _options_for(costs: list[str]) -> list[str]:
    """Offer a window of the ladder rather than exactly the right answers.

    If the options were precisely the set of correct costs, a three-snippet
    puzzle would collapse into a permutation the player could brute-force.
    """
    indexes = sorted(_LADDER.index(cost) for cost in costs)
    lo, hi = indexes[0], indexes[-1]
    while hi - lo + 1 < 5 and (lo > 0 or hi < len(_LADDER) - 1):
        if lo > 0:
            lo -= 1
        if hi - lo + 1 < 5 and hi < len(_LADDER) - 1:
            hi += 1
    return _LADDER[lo:hi + 1]


def _price(*, pid, title, realm, difficulty, family, statement, snippets,
           explanation, nudge, secondary=(), tags=()) -> Problem:
    """One COMPLEXITY_MATCH encounter. `snippets` are (label, code, cost, why).

    Every puzzle is authored with exactly one strictly most expensive snippet, so
    that the plain multiple-choice shape underneath — "which of these costs the
    most?" — has a single true answer for anything that cannot render the full
    pairing interface.
    """
    costs = [cost for _, _, cost, _ in snippets]
    ranks = [_LADDER.index(cost) for cost in costs]
    worst = max(ranks)
    if ranks.count(worst) != 1:
        raise ValueError(f"{pid}: needs exactly one most expensive snippet")

    spec = [{"label": label, "code": dedent(code), "complexity": cost, "why": why}
            for label, code, cost, why in snippets]
    labels = [s["label"] for s in spec]
    table = "\n".join(f"{s['label']} — {s['complexity']}. {s['why']}" for s in spec)

    return Problem(
        id=pid, title=title, realm=realm, pattern="COMPLEXITY",
        difficulty=difficulty,
        problem_statement=dedent(statement),
        entry={"kind": "mcq", "name": pid, "signature": ""},
        canonical_solution=labels[ranks.index(worst)],
        encounter_kind="COMPLEXITY_MATCH",
        secondary_patterns=list(secondary),
        mcq={"snippets": spec, "options": _options_for(costs),
             "choices": labels, "answer": ranks.index(worst),
             "explanation": dedent(explanation)},
        common_failures=_PRICE_FAILURES,
        hint_tree=build_hint_tree(
            "COMPLEXITY", nudge=nudge,
            visual="Price the cheapest one first and use it as a ruler. Costs are "
                   "only ever read against each other.",
            pseudocode="```\nfor each line: how much work, and how many times?\n"
                       "a call is not one step — `count`, `in`, `remove`, a slice\n"
                       "and `+` on a string are all loops wearing a disguise\n```",
            fragment="```\nExactly one of these is the expensive one. Find it "
                     "first; the rest fall out.\n```",
            solution="```\n" + table + "\n```"),
        spaced_repetition_family=family,
        estimated_seconds=TARGET_SECONDS[difficulty],
        target_seconds=TARGET_SECONDS[difficulty],
        profile_weight=Q,
        tags=["puzzle:complexity_match"] + list(tags),
    )


# ---------------------------------------------------------------------------
# Reference implementations.
#
# Deliberately shaped differently from the canonical "honest" sources below. The
# canonical text is what the player is told is correct; these are what computed
# the expected values. Two implementations agreeing is what earns a problem its
# place, and here it also underwrites the grader: the honest spell has to be
# genuinely right on the breaking input, or the break is not a break.
# ---------------------------------------------------------------------------

def _average_score(scores):
    total = 0
    for score in scores:
        total += score
    return total / len(scores) if scores else 0.0


def _total_change(readings):
    return sum(abs(readings[i] - readings[i - 1]) for i in range(1, len(readings)))


def _second_highest(scores):
    distinct = sorted(set(scores))
    return distinct[-2] if len(distinct) > 1 else None


def _biggest_pair_product(nums):
    best = None
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            product = nums[i] * nums[j]
            if best is None or product > best:
                best = product
    return best


def _first_reading(readings):
    for value in readings:
        if value is not None:
            return value
    return None


def _within_budget(costs, limit):
    return sum(costs) <= limit


def _longest_rising_run(nums):
    best = 0
    run = 0
    previous = None
    for value in nums:
        run = run + 1 if previous is not None and value > previous else 1
        previous = value
        best = max(best, run)
    return best


def _rotation_point(nums):
    return nums.index(min(nums)) if nums else 0


def _best_swing(prices):
    best = 0
    for i in range(len(prices)):
        for j in range(i + 1, len(prices)):
            best = max(best, prices[j] - prices[i])
    return best


def _common_prefix_length(a, b):
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def _divide_toward_zero(n, k):
    quotient = abs(n) // abs(k)
    return quotient if (n < 0) == (k < 0) else -quotient


def _drop_negatives(values):
    return [value for value in values if value >= 0]


def _remove_one(bag, item):
    out = dict(bag)
    if item in out:
        out[item] -= 1
        if out[item] <= 0:
            del out[item]
    return out


def _visit_order(graph, start):
    reached = [start]
    frontier = [start]
    while frontier:
        following = []
        for node in frontier:
            for neighbour in graph.get(node, []):
                if neighbour not in reached:
                    reached.append(neighbour)
                    following.append(neighbour)
        frontier = following
    return reached


def _last_n(items, n):
    if n <= 0:
        return []
    return list(items[max(0, len(items) - n):])


def _chunk(items, size):
    out = []
    group = []
    for item in items:
        group.append(item)
        if len(group) == size:
            out.append(group)
            group = []
    if group:
        out.append(group)
    return out


def _find_index(sorted_nums, target):
    for i, value in enumerate(sorted_nums):
        if value == target:
            return i
    return -1


def _round_half_up(value):
    whole = int(value)
    return whole + 1 if value - whole >= 0.5 else whole


def _count_occurrences(text, piece):
    return sum(1 for i in range(len(text) - len(piece) + 1)
               if text[i:i + len(piece)] == piece)


def _is_palindrome(text):
    lowered = text.lower()
    return lowered == lowered[::-1]


# ---------------------------------------------------------------------------
# BREAK IT, part one: flaws exposed by the SHAPE of the input.
#
# Nothing clever here, and that is the point. Empty, one item, a repeat, a
# negative, a zero, the value sitting exactly on the comparison. This is the list
# a working engineer runs down out loud before writing a single test, and the
# whole of part one exists to make running it down a reflex.
# ---------------------------------------------------------------------------

def _shape_breaks() -> list:
    out = []

    out.append(_break_it(
        pid="bk-empty-average", title="The Mean of Nothing",
        realm="python_village", difficulty="TUTORIAL", family="python_basics",
        klass="empty", secondary=["ARRAY"],
        contract="""
            The spell returns the mean of `scores`. A list with no scores in it
            has no mean, so the contract says: report 0.0.
        """,
        fn="average_score", params="scores", reference=_average_score,
        honest="""
            def average_score(scores):
                if not scores:
                    return 0.0
                return sum(scores) / len(scores)
        """,
        flawed="""
            def average_score(scores):
                return sum(scores) / len(scores)
        """,
        visible=[("two marks", [[2, 4]]), ("three marks", [[1, 2, 6]])],
        hidden=[("negative marks", [[-4, 2]]), ("a single mark", [[7]])],
        edges=[("no marks at all", [[]])],
        probes=[[[]]],
        nudge="Nothing in the contract promises there is anyone in the class.",
        explanation="""
            `sum([])` is 0 and `len([])` is 0, so the suspect spell evaluates
            `0 / 0` and raises ZeroDivisionError. The honest spell checks for the
            empty list first, which is why the contract bothers to say what an
            empty list means. Any function that divides by a count needs to say
            out loud what happens when the count is zero.
        """,
        worked="""
            `[[]]` — the empty list.

            Honest: 0.0, as the contract states.
            Suspect: `sum([]) / len([])` is `0 / 0`, a ZeroDivisionError.

            The division is the only dangerous line, and its denominator is the
            length of something the caller supplied. Whenever you see that, the
            first input to try is the one that makes the denominator zero.
        """,
        time="O(n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-single-total-change", title="The Lone Reading",
        realm="python_village", difficulty="TUTORIAL", family="python_basics",
        klass="single", secondary=["ARRAY"],
        contract="""
            The spell totals how much a sensor moved: the sum of the absolute
            differences between each pair of neighbouring readings. Fewer than two
            readings means nothing moved, so the total is 0.
        """,
        fn="total_change", params="readings", reference=_total_change,
        honest="""
            def total_change(readings):
                total = 0
                for i in range(1, len(readings)):
                    total += abs(readings[i] - readings[i - 1])
                return total
        """,
        flawed="""
            def total_change(readings):
                if not readings:
                    return 0
                total = 0
                i = 1
                while True:
                    total += abs(readings[i] - readings[i - 1])
                    i += 1
                    if i >= len(readings):
                        break
                return total
        """,
        visible=[("a rise and a fall", [[1, 4, 2]]), ("a flat line", [[5, 5, 5]])],
        hidden=[("a longer walk", [[0, 3, 3, -2]]), ("two readings", [[10, 4]])],
        edges=[("one reading", [[5]]), ("no readings", [[]])],
        probes=[[[5]]],
        nudge="Whoever wrote this remembered one degenerate case and stopped "
              "there. Which one did they miss?",
        explanation="""
            The suspect spell guards the empty list, so `[]` proves nothing. But
            the loop is a do-while: it computes before it checks. With exactly one
            reading, the body runs once anyway and reaches `readings[1]`, which
            does not exist. A loop that tests its bound at the bottom always
            executes once, and "once" is wrong whenever the right answer is zero
            times.
        """,
        worked="""
            `[[5]]` — one reading.

            Honest: 0. There are no neighbouring pairs, so there is nothing to add.
            Suspect: enters the loop regardless, reads `readings[1]`, IndexError.

            The empty list is guarded and the two-item list is fine. The gap is
            exactly the size in between, which is the case a bottom-tested loop
            always gets wrong.
        """,
        time="O(n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-dupes-second-highest", title="The Tied Champions",
        realm="hashmap_highlands", difficulty="EASY", family="dedupe",
        klass="duplicates", secondary=["SORTING", "SET"],
        contract="""
            The spell returns the second highest DISTINCT score. Two players tied
            at the top share one score between them, not two. When there is no
            second distinct score it returns `None`.
        """,
        fn="second_highest", params="scores", reference=_second_highest,
        honest="""
            def second_highest(scores):
                distinct = sorted(set(scores), reverse=True)
                if len(distinct) < 2:
                    return None
                return distinct[1]
        """,
        flawed="""
            def second_highest(scores):
                ordered = sorted(scores, reverse=True)
                if len(ordered) < 2:
                    return None
                return ordered[1]
        """,
        visible=[("three distinct", [[10, 30, 20]]), ("two distinct", [[4, 9]])],
        hidden=[("negative scores", [[-5, -1, -9]]), ("out of order", [[3, 8, 1, 7]])],
        edges=[("a tie at the top", [[90, 90, 70]]),
               ("every score the same", [[6, 6, 6]]),
               ("one score", [[5]]), ("no scores", [[]])],
        probes=[[[90, 90, 70]], [[6, 6, 6]]],
        nudge="The word the contract leans on is DISTINCT. Nothing in the input "
              "promises that.",
        explanation="""
            Sorting does not remove repeats, so position 1 in the sorted list is
            the second COPY, not the second VALUE. With a tie at the top the
            suspect spell hands back the champion's own score. The honest spell
            collapses the duplicates first — `set` before `sorted` — which is why
            it can say "second distinct" and mean it.
        """,
        worked="""
            `[[90, 90, 70]]` — a tie for first place.

            Honest: 70. The distinct scores are 90 and 70; the second is 70.
            Suspect: 90. Sorted descending that is [90, 90, 70], and index 1 is
            the other 90.

            `[[6, 6, 6]]` breaks it harder: the honest answer is `None`, because
            there is no second distinct score at all.
        """,
        time="O(n log n)", space="O(n)"))

    out.append(_break_it(
        pid="bk-negatives-pair-product", title="Two Debts Make a Fortune",
        realm="array_caverns", difficulty="EASY", family="sorted_pair",
        klass="negatives", secondary=["ARRAY", "SORTING"],
        contract="""
            The spell returns the largest product obtainable from any two
            different positions in `nums`. With fewer than two numbers there is no
            pair, so it returns `None`.
        """,
        fn="biggest_pair_product", params="nums", reference=_biggest_pair_product,
        honest="""
            def biggest_pair_product(nums):
                if len(nums) < 2:
                    return None
                ordered = sorted(nums)
                return max(ordered[-1] * ordered[-2], ordered[0] * ordered[1])
        """,
        flawed="""
            def biggest_pair_product(nums):
                if len(nums) < 2:
                    return None
                ordered = sorted(nums)
                return ordered[-1] * ordered[-2]
        """,
        visible=[("all positive", [[1, 4, 3]]), ("one negative, positives win",
                                                 [[-1, 5, 6]])],
        hidden=[("exactly two", [[2, 7]]), ("zeros in the mix", [[0, 0, 3]]),
                ("a single big number", [[9, 1, 2]])],
        edges=[("two large debts", [[-9, -8, 1, 2]]),
               ("everything negative", [[-4, -3, -2]]),
               ("one number", [[5]])],
        probes=[[[-9, -8, 1, 2]], [[-4, -3, -2]]],
        nudge="Sorting puts the biggest numbers at one end. It puts something "
              "else at the other.",
        explanation="""
            Two large negatives multiply to a large positive. The suspect spell
            only ever looks at the top of the sorted list, so it never considers
            the pair at the bottom. The honest spell takes the better of the two
            candidate pairs — the two largest, and the two smallest. This is the
            single most common miss in this problem family, and the only input
            that exposes it is one the author did not think was interesting.
        """,
        worked="""
            `[[-9, -8, 1, 2]]`

            Honest: 72, from -9 times -8.
            Suspect: 2, from the two biggest numbers, 2 and 1.

            Sorted order is [-9, -8, 1, 2]. Both ends are candidates, because a
            product of two negatives is positive. Only looking at one end is only
            correct when the input has no negatives in it — which nothing here
            promised.
        """,
        time="O(n log n)", space="O(n)"))

    out.append(_break_it(
        pid="bk-zero-first-reading", title="A Reading of Zero Is a Reading",
        realm="python_village", difficulty="TUTORIAL", family="python_basics",
        klass="zero", secondary=["ARRAY"],
        contract="""
            A sensor that failed records `None`. The spell returns the first
            reading that is not `None`, or `None` when every sensor failed. A
            reading of 0 is a perfectly good reading — the sensor worked, and it
            measured nothing.
        """,
        fn="first_reading", params="readings", reference=_first_reading,
        honest="""
            def first_reading(readings):
                present = [value for value in readings if value is not None]
                return present[0] if present else None
        """,
        flawed="""
            def first_reading(readings):
                for value in readings:
                    if value:
                        return value
                return None
        """,
        visible=[("the first sensor works", [[3, 5]]),
                 ("the first two failed", [[None, None, 8]])],
        hidden=[("a negative reading", [[None, -2, 4]]),
                ("every sensor failed", [[None, None]]),
                ("no sensors at all", [[]])],
        edges=[("a genuine zero", [[None, 0, 5]]), ("zero comes first", [[0, 9]])],
        probes=[[[None, 0, 5]], [[0, 9]]],
        nudge="The contract distinguishes 'missing' from 'nothing measured'. The "
              "code uses one test for both.",
        explanation="""
            `if value:` asks "is this truthy", and 0 is not. So the suspect spell
            walks straight past a real measurement of zero and reports the next
            one instead. `if value is not None:` asks the question the contract
            actually asks. Empty strings, empty lists and 0.0 fall into the same
            trap, which is why `is not None` is worth typing out in full every
            time you mean it.
        """,
        worked="""
            `[[None, 0, 5]]`

            Honest: 0. The second sensor worked and measured nothing.
            Suspect: 5. It skipped the 0 because `if 0:` is false.

            Whenever a contract separates "absent" from "zero", any truthiness
            test in the implementation is a bug waiting for the right input.
        """,
        time="O(n)", space="O(n)"))

    out.append(_break_it(
        pid="bk-boundary-within-budget", title="Exactly the Limit",
        realm="python_village", difficulty="TUTORIAL", family="python_basics",
        klass="boundary", secondary=["ARRAY"],
        contract="""
            The spell reports whether the total of `costs` stays within `limit`.
            Spending the limit exactly is within budget — the contract says the
            total must not EXCEED the limit.
        """,
        fn="within_budget", params="costs, limit", reference=_within_budget,
        honest="""
            def within_budget(costs, limit):
                total = 0
                for cost in costs:
                    total += cost
                return total <= limit
        """,
        flawed="""
            def within_budget(costs, limit):
                return sum(costs) < limit
        """,
        visible=[("comfortably under", [[1, 2], 10]), ("well over", [[6, 7], 10])],
        hidden=[("one item, under", [[4], 5]), ("one item, over", [[9], 5]),
                ("nothing bought", [[], 5])],
        edges=[("exactly the limit", [[2, 3], 5]),
               ("a free basket and a zero budget", [[], 0]),
               ("one item at exactly the limit", [[5], 5])],
        probes=[[[2, 3], 5], [[], 0]],
        nudge="There is exactly one total this spell could get wrong. Spend it.",
        explanation="""
            `<` excludes the boundary; `<=` includes it. The contract says
            "must not exceed", which is `<=`. Every comparison in a contract has
            an input sitting precisely on it, and that input is the only one that
            can tell the two operators apart. When an interviewer asks for a test
            case, this is the one to name first: it is cheap to say and it catches
            the most common class of bug there is.
        """,
        worked="""
            `[[2, 3], 5]` — a total of exactly 5 against a limit of 5.

            Honest: True. 5 does not exceed 5.
            Suspect: False. `5 < 5` is false.

            `[[], 0]` does the same job from the other side: an empty basket
            against a zero budget totals 0, which is within a limit of 0.
        """,
        time="O(n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-identical-rising-run", title="The Plateau",
        realm="array_caverns", difficulty="EASY", family="counting",
        klass="identical", secondary=["ARRAY"],
        contract="""
            The spell returns the length of the longest run of STRICTLY
            increasing neighbours. Equal neighbours do not continue a run, they
            end it. An empty list scores 0.
        """,
        fn="longest_rising_run", params="nums", reference=_longest_rising_run,
        honest="""
            def longest_rising_run(nums):
                if not nums:
                    return 0
                best = 1
                run = 1
                for i in range(1, len(nums)):
                    if nums[i] > nums[i - 1]:
                        run += 1
                    else:
                        run = 1
                    if run > best:
                        best = run
                return best
        """,
        flawed="""
            def longest_rising_run(nums):
                if not nums:
                    return 0
                best = 1
                run = 1
                for i in range(1, len(nums)):
                    if nums[i] >= nums[i - 1]:
                        run += 1
                    else:
                        run = 1
                    if run > best:
                        best = run
                return best
        """,
        visible=[("one long climb", [[1, 2, 3]]), ("a dip in the middle",
                                                   [[1, 3, 2, 4, 5]])],
        hidden=[("falling all the way", [[5, 4, 3]]), ("a single number", [[7]]),
                ("no numbers", [[]])],
        edges=[("every value identical", [[4, 4, 4]]),
               ("a plateau inside a climb", [[1, 2, 2, 3]])],
        probes=[[[4, 4, 4]], [[1, 2, 2, 3]]],
        nudge="The contract says STRICTLY. Build an input where strictly and "
              "loosely disagree.",
        explanation="""
            `>=` treats a flat step as a rise, so a plateau keeps a run alive that
            the contract says has ended. On strictly increasing or strictly
            decreasing data the two spells are indistinguishable, which is exactly
            why this survives a casual test suite: you have to feed it equal
            neighbours on purpose. Any time a contract uses the word "strictly",
            the test that matters is the one with a repeat in it.
        """,
        worked="""
            `[[4, 4, 4]]`

            Honest: 1. No neighbour is strictly greater than the one before it, so
            the longest rising run is a single element.
            Suspect: 3. It counted two flat steps as rises.

            `[[1, 2, 2, 3]]` is the subtler version: honest says 2, the suspect
            spell says 4, because it never noticed the run was broken in the
            middle.
        """,
        time="O(n)", space="O(1)"))

    return out


# ---------------------------------------------------------------------------
# BREAK IT, part two: flaws exposed by ORDER, BOUNDS and ARITHMETIC.
#
# These are the ones that survive a test suite. The input looks entirely
# ordinary; what is unusual about it is where the answer sits — at the end of the
# search, on the wrong side of zero, in the group that did not come out even.
# ---------------------------------------------------------------------------

def _order_breaks() -> list:
    out = []

    out.append(_break_it(
        pid="bk-sorted-rotation-point", title="Rotated by Nothing at All",
        realm="array_caverns", difficulty="MEDIUM", family="binary_search",
        klass="already_sorted", secondary=["ARRAY", "BINARY_SEARCH"],
        contract="""
            `nums` is a list of distinct numbers, sorted ascending, then rotated
            left some number of times. The spell returns the index of the smallest
            value. "Some number of times" includes none, and an empty list gives 0.
        """,
        fn="rotation_point", params="nums", reference=_rotation_point,
        honest="""
            def rotation_point(nums):
                if not nums:
                    return 0
                smallest = 0
                for i in range(1, len(nums)):
                    if nums[i] < nums[smallest]:
                        smallest = i
                return smallest
        """,
        flawed="""
            def rotation_point(nums):
                for i in range(1, len(nums)):
                    if nums[i] < nums[i - 1]:
                        return i
                return len(nums)
        """,
        visible=[("rotated by two", [[4, 5, 1, 2, 3]]),
                 ("rotated by three", [[3, 4, 5, 1, 2]])],
        hidden=[("rotated by one", [[9, 1, 3, 5]]),
                ("the smallest lands last", [[2, 3, 4, 1]]),
                ("an empty list", [[]])],
        edges=[("never rotated", [[1, 2, 3, 4, 5]]),
               ("a single value", [[7]])],
        probes=[[[1, 2, 3, 4, 5]], [[7]]],
        nudge="The spell hunts for the place the sequence drops. What if there "
              "isn't one?",
        explanation="""
            The suspect spell finds the rotation by looking for the one step that
            goes down. A list rotated zero times has no such step, and the fallback
            it reaches — `len(nums)` — is not even a valid index. The honest spell
            asks the question the contract asks, "where is the smallest value",
            which has an answer for every input including the un-rotated one. When
            a loop's `return` after the loop is a different KIND of answer from
            the `return` inside it, that fallback is where the bug lives.
        """,
        worked="""
            `[[1, 2, 3, 4, 5]]` — sorted, rotated zero times.

            Honest: 0. The smallest value is at the front.
            Suspect: 5. No neighbouring pair descends, so it falls out of the loop
            and returns the length — an index one past the end of the list.

            `[[7]]` does the same with a single value: the loop body never runs at
            all, and the suspect spell answers 1 for a list with one slot in it.
        """,
        time="O(n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-reversed-best-swing", title="The Market That Only Falls",
        realm="sliding_window_marsh", difficulty="EASY", family="window_sum",
        klass="reversed", secondary=["ARRAY", "GREEDY"],
        contract="""
            Buy once, sell once, and sell LATER than you bought. The spell returns
            the largest profit available. When no later price is higher than an
            earlier one, the right move is not to trade, and the profit is 0.
        """,
        fn="best_swing", params="prices", reference=_best_swing,
        honest="""
            def best_swing(prices):
                best = 0
                low = None
                for price in prices:
                    if low is None or price < low:
                        low = price
                    elif price - low > best:
                        best = price - low
                return best
        """,
        flawed="""
            def best_swing(prices):
                if not prices:
                    return 0
                return max(prices) - min(prices)
        """,
        visible=[("a dip then a rise", [[3, 1, 4, 6]]),
                 ("a steady climb", [[1, 2, 3]])],
        hidden=[("a flat market", [[4, 4, 4]]),
                ("low, high, low", [[5, 1, 9, 2]]),
                ("a single price", [[5]]), ("no prices", [[]])],
        edges=[("a market that only falls", [[9, 7, 4, 1]]),
               ("the peak comes first", [[8, 2, 3]])],
        probes=[[[9, 7, 4, 1]], [[8, 2, 3]]],
        nudge="`max` and `min` know their values. They do not know which came "
              "first.",
        explanation="""
            `max(prices) - min(prices)` is the right answer only when the cheapest
            price happens to arrive before the dearest one. Reverse that order and
            the suspect spell reports a profit from a trade nobody could have
            made — selling before buying. The honest spell carries the lowest price
            SEEN SO FAR, which is what enforces the ordering the contract
            describes. Any time a contract contains the word "later", check
            whether the implementation knows about time at all.
        """,
        worked="""
            `[[9, 7, 4, 1]]` — a market that only falls.

            Honest: 0. There is no later price higher than an earlier one, so the
            correct move is not to trade.
            Suspect: 8, being 9 minus 1 — a sale on day one of stock bought on
            day four.

            `[[8, 2, 3]]` is the quieter version: the honest profit is 1, buying at
            2 and selling at 3, but the suspect spell reports 6.
        """,
        time="O(n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-offbyone-common-prefix", title="One Letter Short",
        realm="stringwood_labyrinth", difficulty="EASY",
        family="onboarding_strings", klass="off_by_one", secondary=["STRING"],
        contract="""
            The spell returns how many characters `a` and `b` share from the
            start, counting up to the first place they differ. Two identical
            strings share all of themselves.
        """,
        fn="common_prefix_length", params="a, b", reference=_common_prefix_length,
        honest="""
            def common_prefix_length(a, b):
                i = 0
                while i < len(a) and i < len(b) and a[i] == b[i]:
                    i += 1
                return i
        """,
        flawed="""
            def common_prefix_length(a, b):
                count = 0
                for i in range(min(len(a), len(b)) - 1):
                    if a[i] != b[i]:
                        break
                    count += 1
                return count
        """,
        visible=[("share two letters", ["apple", "apricot"]),
                 ("share nothing", ["dog", "cat"])],
        hidden=[("share one letter", ["ant", "axe"]),
                ("one string is empty", ["", "abc"]),
                ("both empty", ["", ""])],
        edges=[("one is a prefix of the other", ["car", "carpet"]),
               ("identical strings", ["same", "same"])],
        probes=[["car", "carpet"], ["same", "same"]],
        nudge="Count the positions that loop visits, then count the positions "
              "that need comparing. They are not the same number.",
        explanation="""
            `range(min(len(a), len(b)) - 1)` stops one position early, so the last
            shared character is never counted. That only shows when the comparison
            actually reaches the end — that is, when one string is a prefix of the
            other. Every other input stops at a mismatch before the missing
            iteration matters, which is why the bug hides. The `- 1` was probably
            defensive: someone worried about running off the end and paid for it
            at the other boundary.
        """,
        worked="""
            `["car", "carpet"]`

            Honest: 3. All of "car" is shared.
            Suspect: 2. It compared positions 0 and 1 and stopped.

            `["same", "same"]` is the same break stated plainly: identical strings
            share 4 characters and the suspect spell reports 3. The rule to carry
            away: when a loop bound has an adjustment in it, test the input where
            the loop has to run all the way.
        """,
        time="O(n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-intdiv-toward-zero", title="Which Way Does It Round",
        realm="python_village", difficulty="EASY", family="python_basics",
        klass="integer_division", secondary=["SIMULATION"],
        contract="""
            Integer division that truncates TOWARD ZERO, the way C and most
            whiteboards mean it: -7 divided by 2 is -3, not -4. The divisor `k` is
            never 0.
        """,
        fn="divide_toward_zero", params="n, k", reference=_divide_toward_zero,
        honest="""
            def divide_toward_zero(n, k):
                quotient = abs(n) // abs(k)
                if (n < 0) != (k < 0):
                    return -quotient
                return quotient
        """,
        flawed="""
            def divide_toward_zero(n, k):
                return n // k
        """,
        visible=[("both positive", [7, 2]), ("it divides exactly", [9, 3])],
        hidden=[("both negative, exact", [-9, -3]),
                ("both negative, inexact", [-7, -2]),
                ("a zero numerator", [0, 5]), ("divisor of one", [13, 1])],
        edges=[("a negative numerator", [-7, 2]), ("a negative divisor", [7, -2])],
        probes=[[-7, 2], [7, -2]],
        nudge="Python's `//` always rounds DOWN. Downward and toward-zero point "
              "the same way on only one side of the number line.",
        explanation="""
            `//` floors: it rounds toward minus infinity. For positive results
            that is identical to truncating toward zero, so the suspect spell is
            right on every input where the signs match. Give it one negative and
            one positive and the two rules part company: -7 // 2 is -4, because
            -4 is below -3.5, but truncation toward zero gives -3. `%` has the
            matching surprise, which is why a hash bucket computed with `%` on a
            possibly-negative key is a bug this player will meet in real code.
        """,
        worked="""
            `[-7, 2]`

            Honest: -3. Truncating -3.5 toward zero drops the fraction.
            Suspect: -4. `-7 // 2` floors -3.5 downward.

            `[7, -2]` breaks it from the other direction for the same reason. The
            signs matching is what hides the bug, so the test that matters is the
            one where exactly one operand is negative.
        """,
        time="O(1)", space="O(1)"))

    out.append(_break_it(
        pid="bk-loopbound-find-index", title="Where lo Meets hi",
        realm="array_caverns", difficulty="MEDIUM", family="binary_search",
        klass="loop_bound", secondary=["BINARY_SEARCH", "ARRAY"],
        contract="""
            `sorted_nums` is sorted ascending with no duplicates. The spell returns
            the index of `target`, or -1 when `target` is not in the list.
        """,
        fn="find_index", params="sorted_nums, target", reference=_find_index,
        honest="""
            def find_index(sorted_nums, target):
                lo, hi = 0, len(sorted_nums) - 1
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if sorted_nums[mid] == target:
                        return mid
                    if sorted_nums[mid] < target:
                        lo = mid + 1
                    else:
                        hi = mid - 1
                return -1
        """,
        flawed="""
            def find_index(sorted_nums, target):
                lo, hi = 0, len(sorted_nums) - 1
                while lo < hi:
                    mid = (lo + hi) // 2
                    if sorted_nums[mid] == target:
                        return mid
                    if sorted_nums[mid] < target:
                        lo = mid + 1
                    else:
                        hi = mid - 1
                return -1
        """,
        visible=[("the middle value", [[1, 3, 5, 7, 9], 5]),
                 ("a value above the middle", [[1, 3, 5, 7, 9], 7])],
        hidden=[("the first value", [[1, 3, 5, 7, 9], 1]),
                ("a gap between values", [[1, 3, 5, 7, 9], 4]),
                ("larger than everything", [[1, 3, 5, 7, 9], 10]),
                ("smaller than everything", [[1, 3, 5, 7, 9], 0]),
                ("an empty list", [[], 3])],
        edges=[("the last value", [[1, 3, 5, 7, 9], 9]),
               ("a value the search corners", [[1, 3, 5, 7, 9], 3]),
               ("a list of one", [[5], 5])],
        probes=[[[1, 3, 5, 7, 9], 9], [[5], 5], [[1, 3, 5, 7, 9], 3]],
        nudge="The window narrows until `lo` and `hi` are the same index. Ask "
              "what the spell does with that index.",
        explanation="""
            `while lo < hi` stops as soon as the window narrows to a single
            position — and never looks at it. Everything found earlier, at some
            midpoint while the window was still wide, comes back correctly, which
            is why half a test suite passes. The values that lose are the ones the
            search corners: most memorably the last element, and any element a
            single-item list contains. The honest bound is `lo <= hi`, because a
            window of one is still a window with something in it.
        """,
        worked="""
            `[[1, 3, 5, 7, 9], 9]`

            Honest: 4. Suspect: -1.

            Trace it. lo=0 hi=4, mid=2, 5 < 9, so lo=3. lo=3 hi=4, mid=3, 7 < 9,
            so lo=4. Now lo=4 and hi=4 — the answer is sitting right there and
            `4 < 4` is false, so the loop exits and reports failure.

            `[[5], 5]` is the one-line version of the same bug: lo=0, hi=0, the
            loop never runs.
        """,
        time="O(log n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-tail-chunk", title="The Group That Did Not Come Out Even",
        realm="array_caverns", difficulty="EASY", family="python_basics",
        klass="partial_tail", secondary=["ARRAY"],
        contract="""
            The spell splits `items` into consecutive groups of `size`, in order.
            The last group may be shorter than the rest — nothing is thrown away.
            `size` is at least 1.
        """,
        fn="chunk", params="items, size", reference=_chunk,
        honest="""
            def chunk(items, size):
                return [items[i:i + size] for i in range(0, len(items), size)]
        """,
        flawed="""
            def chunk(items, size):
                groups = []
                for i in range(0, len(items) - size + 1, size):
                    groups.append(items[i:i + size])
                return groups
        """,
        visible=[("two even groups", [[1, 2, 3, 4], 2]),
                 ("groups of three", [[1, 2, 3, 4, 5, 6], 3])],
        hidden=[("groups of one", [[1, 2, 3], 1]),
                ("one group exactly", [[1, 2], 2]),
                ("an empty list", [[], 2])],
        edges=[("a short tail", [[1, 2, 3], 2]),
               ("the group is bigger than the list", [[1, 2], 5])],
        probes=[[[1, 2, 3], 2], [[1, 2], 5]],
        nudge="The stopping point of that loop is arithmetic about full groups. "
              "Give it a list that does not divide.",
        explanation="""
            `len(items) - size + 1` is the last index at which a FULL group
            starts. Stopping there silently drops any remainder, and when the list
            is shorter than one group it drops everything and returns an empty
            list. The contract said nothing is thrown away. The honest form steps
            by `size` all the way to the end and lets the slice run short, which
            is exactly what a Python slice does when asked for more than is there.
        """,
        worked="""
            `[[1, 2, 3], 2]`

            Honest: [[1, 2], [3]]. Suspect: [[1, 2]]. The 3 is gone.

            `[[1, 2], 5]` is worse and easier to reason about: the range is empty,
            so the suspect spell returns [] and loses the entire list. Any loop
            whose bound is computed from a division or a group size deserves an
            input whose length is not a multiple of it.
        """,
        time="O(n)", space="O(n)"))

    out.append(_break_it(
        pid="bk-halfway-rounding", title="The Exact Half",
        realm="python_village", difficulty="TUTORIAL", family="python_basics",
        klass="half_way", secondary=["SIMULATION"],
        contract="""
            The spell rounds a number that is zero or greater to the nearest whole
            number. A value sitting exactly halfway rounds UP: 2.5 becomes 3.
        """,
        fn="round_half_up", params="value", reference=_round_half_up,
        honest="""
            def round_half_up(value):
                return int(value + 0.5)
        """,
        flawed="""
            def round_half_up(value):
                return round(value)
        """,
        visible=[("below the half", [2.4]), ("above the half", [2.6])],
        hidden=[("already whole", [4.0]), ("just under a half", [7.49]),
                ("just over a half", [7.51]), ("zero", [0.0])],
        edges=[("exactly halfway", [2.5]), ("a half at the bottom", [0.5]),
               ("a half that agrees by luck", [3.5])],
        probes=[[2.5], [0.5]],
        nudge="The contract names one exact value and tells you which way it must "
              "go. Try that value, and then try the next one up.",
        explanation="""
            Python's built-in `round` does banker's rounding: an exact half goes to
            the nearest EVEN number. So `round(2.5)` is 2 and `round(0.5)` is 0,
            while the contract demands 3 and 1. The joke of it is that
            `round(3.5)` is 4 — correct, by luck, because 4 happens to be even —
            so a test suite that only probes 3.5 passes and proves nothing. Money
            and scoring code gets this wrong constantly.
        """,
        worked="""
            `[2.5]`

            Honest: 3, as the contract demands. Suspect: 2.

            `round` breaks ties toward the even neighbour, so halves alternate:
            0.5 to 0, 1.5 to 2, 2.5 to 2, 3.5 to 4. Half of them look right. If
            you test only 3.5 you will never see it, which makes this a good
            argument for testing two adjacent cases of the same shape.
        """,
        time="O(1)", space="O(1)"))

    out.append(_break_it(
        pid="bk-overlap-occurrences", title="Appearances That Share Letters",
        realm="stringwood_labyrinth", difficulty="EASY",
        family="onboarding_strings", klass="overlap", secondary=["STRING"],
        contract="""
            The spell counts how many times `piece` appears in `text`, counting
            OVERLAPPING appearances: "aaa" contains "aa" twice, once at position 0
            and once at position 1. `piece` is never empty.
        """,
        fn="count_occurrences", params="text, piece", reference=_count_occurrences,
        honest="""
            def count_occurrences(text, piece):
                found = 0
                start = text.find(piece)
                while start != -1:
                    found += 1
                    start = text.find(piece, start + 1)
                return found
        """,
        flawed="""
            def count_occurrences(text, piece):
                return text.count(piece)
        """,
        visible=[("twice, well apart", ["abab", "ab"]),
                 ("not there at all", ["abc", "zz"])],
        hidden=[("once", ["hello", "ll"]), ("a single character", ["banana", "a"]),
                ("the piece is longer than the text", ["ab", "abc"]),
                ("the whole text", ["abc", "abc"])],
        edges=[("overlapping pairs", ["aaa", "aa"]),
               ("overlapping triples", ["aaaa", "aaa"]),
               ("an overlap that is not obvious", ["abababa", "aba"])],
        probes=[["aaa", "aa"], ["abababa", "aba"]],
        nudge="`str.count` resumes searching AFTER the match it just found. When "
              "does that skip something?",
        explanation="""
            `str.count` counts non-overlapping appearances: having matched at
            position 0 it restarts at the end of that match, so a second
            appearance that begins inside the first is never seen. The contract
            asked for overlapping, which means resuming one character along rather
            than one match along. Every input where the piece cannot overlap itself
            — any piece whose characters are all different — gives identical
            answers, which is why the bug needs a repeated character to surface.
        """,
        worked="""
            `["aaa", "aa"]`

            Honest: 2, at positions 0 and 1. Suspect: 1.

            `["abababa", "aba"]` is the same trap without the tell: the honest
            count is 3, at positions 0, 2 and 4, and `str.count` reports 2. A piece
            can only overlap itself when it has internal repetition, so that is the
            shape of input to build on purpose.
        """,
        time="O(n)", space="O(1)"))

    out.append(_break_it(
        pid="bk-case-palindrome", title="The Capital at the Front",
        realm="stringwood_labyrinth", difficulty="EASY", family="palindrome",
        klass="case", secondary=["STRING", "TWO_POINTER"],
        contract="""
            The spell reports whether `text` reads the same forwards and
            backwards, IGNORING letter case. Spaces and punctuation are ordinary
            characters and count normally.
        """,
        fn="is_palindrome", params="text", reference=_is_palindrome,
        honest="""
            def is_palindrome(text):
                lowered = text.lower()
                left, right = 0, len(lowered) - 1
                while left < right:
                    if lowered[left] != lowered[right]:
                        return False
                    left += 1
                    right -= 1
                return True
        """,
        flawed="""
            def is_palindrome(text):
                return text == text[::-1]
        """,
        visible=[("a lowercase palindrome", ["racecar"]),
                 ("not a palindrome", ["python"])],
        hidden=[("even length", ["abba"]), ("empty", [""]), ("one letter", ["x"]),
                ("a space in the middle", ["ab ba"])],
        edges=[("a capital at the front", ["Racecar"]),
               ("alternating case", ["AbBa"]),
               ("capitals that do not save it", ["Python"])],
        probes=[["Racecar"], ["AbBa"]],
        nudge="Read the contract's third word again, then look for the line that "
              "honours it.",
        explanation="""
            The suspect spell compares raw characters, and "R" is not "r". So a
            word that is a palindrome to a reader is not one to the code. The
            honest spell normalises first and compares afterwards — the general
            shape of every "ignoring X" contract, where the normalising step is
            the part people forget. Note that "Python" still comes back False from
            both spells: a wrong implementation agreeing with a right one on the
            negative cases is exactly how this survives testing.
        """,
        worked="""
            `["Racecar"]`

            Honest: True. Lowered it is "racecar", a palindrome.
            Suspect: False. Reversed, "Racecar" is "racecaR", and "R" != "r".

            The contract says case is ignored; the implementation never lowers
            anything. Whenever a contract says "ignoring" something, look for the
            line that does the ignoring. If there isn't one, you already have your
            input.
        """,
        time="O(n)", space="O(n)"))

    return out


# ---------------------------------------------------------------------------
# BREAK IT, part three: flaws in the MECHANISM rather than the input.
#
# Here the input is unremarkable and the code is doing something structurally
# unsound — walking a list it is editing, decrementing a count instead of
# deleting an entry, marking a node visited a moment too late. These are the
# bugs that reach production, because they need a particular SHAPE of data
# rather than a particular value, and shapes are what nobody enumerates.
# ---------------------------------------------------------------------------

def _mechanism_breaks() -> list:
    out = []

    out.append(_break_it(
        pid="bk-mutation-drop-negatives", title="Editing the Floor You Stand On",
        realm="array_caverns", difficulty="EASY", family="onboarding_lists",
        klass="mutation", secondary=["ARRAY"],
        contract="""
            The spell returns a new list holding only the values that are zero or
            greater, in their original order. The caller's own list is left alone.
        """,
        fn="drop_negatives", params="values", reference=_drop_negatives,
        honest="""
            def drop_negatives(values):
                kept = []
                for value in values:
                    if value >= 0:
                        kept.append(value)
                return kept
        """,
        flawed="""
            def drop_negatives(values):
                kept = list(values)
                for value in kept:
                    if value < 0:
                        kept.remove(value)
                return kept
        """,
        visible=[("one negative in the middle", [[1, -2, 3]]),
                 ("nothing to drop", [[1, 2, 3]])],
        hidden=[("the negative comes first", [[-1, 2, 3]]),
                ("zero survives", [[0, -1, 4]]),
                ("an empty list", [[]])],
        edges=[("two negatives side by side", [[1, -2, -3, 4]]),
               ("every value negative", [[-1, -2, -3]]),
               ("negatives at the end", [[5, -1, -2]])],
        probes=[[[1, -2, -3, 4]], [[-1, -2, -3]]],
        nudge="The loop walks the list by position. The body changes what is at "
              "each position. Where do those two disagree?",
        explanation="""
            Iterating a list walks an internal index. `remove` shifts everything
            after the removed item down one slot, so the next value slides into the
            position the loop has already passed and is never examined. A single
            isolated negative survives this — the loop just ends one item early,
            and there was nothing left to check anyway. Two negatives in a row is
            what exposes it: the second one is skipped entirely. The rule is
            absolute: never mutate a list while iterating it. Build a new one, or
            iterate a copy and edit the original.
        """,
        worked="""
            `[[1, -2, -3, 4]]`

            Honest: [1, 4]. Suspect: [1, -3, 4].

            Walk it. Index 0 holds 1, kept. Index 1 holds -2, removed — and now
            the list is [1, -3, 4], so -3 has slid into index 1, the position the
            loop is about to leave. Index 2 holds 4. Done, and -3 was never looked
            at. `[[-1, -2, -3]]` shows the same thing losing over half the list.
        """,
        time="O(n)", space="O(n)"))

    out.append(_break_it(
        pid="bk-delete-at-zero-remove-one", title="A Bag of Zero Apples",
        realm="hashmap_highlands", difficulty="EASY", family="counting",
        klass="delete_at_zero", secondary=["HASH_MAP"],
        contract="""
            `bag` maps an item's name to how many of it you are carrying. The spell
            removes ONE of `item` and returns the bag. When the last one goes the
            item is no longer in the bag at all — a bag does not contain zero
            apples, it simply has no apples in it. Removing something you are not
            carrying leaves the bag unchanged.
        """,
        fn="remove_one", params="bag, item", reference=_remove_one,
        honest="""
            def remove_one(bag, item):
                kept = {}
                for name, count in bag.items():
                    if name == item:
                        count -= 1
                        if count <= 0:
                            continue
                    kept[name] = count
                return kept
        """,
        flawed="""
            def remove_one(bag, item):
                kept = dict(bag)
                if item in kept:
                    kept[item] -= 1
                return kept
        """,
        visible=[("two apples, take one", [{"apple": 2, "pear": 1}, "apple"]),
                 ("three of a kind", [{"rope": 3}, "rope"])],
        hidden=[("not carrying it", [{"apple": 2}, "torch"]),
                ("taking from the middle", [{"a": 1, "b": 2, "c": 1}, "b"]),
                ("an empty bag", [{}, "apple"])],
        edges=[("the last apple", [{"apple": 1, "pear": 2}, "apple"]),
               ("the only item", [{"apple": 1}, "apple"])],
        probes=[[{"apple": 1}, "apple"], [{"apple": 1, "pear": 2}, "apple"]],
        nudge="Subtracting one from a count and removing an entry are different "
              "operations. Find the input where the difference shows.",
        explanation="""
            The suspect spell decrements and stops. At a count of one that leaves
            `{"apple": 0}` — an entry claiming you are carrying zero apples, which
            the contract says must not exist. It reads as a harmless difference
            until something downstream asks `"apple" in bag` and gets True, or
            counts `len(bag)` and gets one too many, or iterates the bag and hands
            the player a stack of nothing. This is the counting-map bug: a sliding
            window that tracks distinct characters this way reports the wrong
            distinct count the moment a character's count reaches zero.
        """,
        worked="""
            `[{"apple": 1}, "apple"]`

            Honest: {}. The last apple is gone, so there are no apples to record.
            Suspect: {"apple": 0}.

            The fix is one line — `del bag[item]` when the count hits zero — and
            the test that catches it is the one where the count STARTS at one.
            Any input with a count of two or more passes happily.
        """,
        time="O(n)", space="O(n)"))

    out.append(_break_it(
        pid="bk-visited-on-pop-order", title="Marked a Moment Too Late",
        realm="graph_wastes", difficulty="MEDIUM", family="graph_traverse",
        klass="visited_on_pop", secondary=["BFS", "QUEUE"],
        contract="""
            Breadth-first search from `start`. The spell returns the nodes in the
            order they are first reached, and every node appears EXACTLY ONCE.
            `graph` maps each node to its list of neighbours.
        """,
        fn="visit_order", params="graph, start", reference=_visit_order,
        honest="""
            def visit_order(graph, start):
                order = []
                seen = {start}
                queue = [start]
                while queue:
                    node = queue.pop(0)
                    order.append(node)
                    for neighbour in graph.get(node, []):
                        if neighbour not in seen:
                            seen.add(neighbour)
                            queue.append(neighbour)
                return order
        """,
        flawed="""
            def visit_order(graph, start):
                order = []
                seen = set()
                queue = [start]
                while queue:
                    node = queue.pop(0)
                    order.append(node)
                    seen.add(node)
                    for neighbour in graph.get(node, []):
                        if neighbour not in seen:
                            queue.append(neighbour)
                return order
        """,
        visible=[("a chain", [{"a": ["b"], "b": ["c"], "c": []}, "a"]),
                 ("a fan", [{"a": ["b", "c"], "b": [], "c": []}, "a"])],
        hidden=[("a lone node", [{"a": []}, "a"]),
                ("a tree", [{"a": ["b", "c"], "b": ["d"], "c": [], "d": []}, "a"]),
                ("a two-node cycle", [{"a": ["b"], "b": ["a"]}, "a"])],
        edges=[("a diamond", [{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []},
                              "a"]),
               ("two roads to the same place",
                [{"a": ["b", "c"], "b": ["e"], "c": ["e"], "e": ["f"], "f": []},
                 "a"])],
        probes=[[{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}, "a"]],
        nudge="A node is marked when it comes OFF the queue. How long can it sit "
              "on the queue before that happens, and who else looks at it "
              "meanwhile?",
        explanation="""
            Marking on pop leaves a window: between a node being queued and being
            popped, it is not in `seen`, so any other node that also points at it
            queues it a second time. It then gets popped twice and appears twice in
            the output. A chain or a tree never triggers this, because nothing has
            two routes into it — you need a node with two parents in the same
            frontier. The honest version marks on PUSH, which closes the window.
            In a large graph this is not only a wrong answer but a queue that grows
            with the number of edges rather than nodes.
        """,
        worked="""
            `[{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}, "a"]` — a diamond.

            Honest: ["a", "b", "c", "d"]. Suspect: ["a", "b", "c", "d", "d"].

            Trace the queue. Pop a, mark a, queue b and c. Pop b, mark b, d is not
            marked, queue d. Pop c, mark c — d is STILL not marked, because it has
            not been popped yet — so queue d again. The queue now holds d twice.
            Any node reachable by two paths of the same length does this.
        """,
        time="O(n)", space="O(n)"))

    out.append(_break_it(
        pid="bk-negzero-slice-last-n", title="The Last Zero Items",
        realm="array_caverns", difficulty="EASY", family="onboarding_lists",
        klass="negative_zero_slice", secondary=["ARRAY"],
        contract="""
            The spell returns the last `n` items, in order. Asking for zero items
            gives an empty list. Asking for more items than exist gives all of
            them.
        """,
        fn="last_n", params="items, n", reference=_last_n,
        honest="""
            def last_n(items, n):
                if n <= 0:
                    return []
                return items[-n:]
        """,
        flawed="""
            def last_n(items, n):
                return items[-n:]
        """,
        visible=[("the last two", [[1, 2, 3, 4], 2]),
                 ("the last one", [[1, 2, 3], 1])],
        hidden=[("more than there are", [[1, 2], 5]),
                ("all of them", [[1, 2, 3], 3]),
                ("an empty list", [[], 2])],
        edges=[("none at all", [[1, 2, 3], 0]),
               ("a negative count", [[1, 2, 3], -1]),
               ("zero from an empty list", [[], 0])],
        probes=[[[1, 2, 3], 0], [[1, 2, 3], -1]],
        nudge="Substitute the number into the slice by hand rather than reading "
              "it as a shape. What is `items[-0:]`?",
        explanation="""
            There is no negative zero. `-0` is `0`, so `items[-0:]` is `items[0:]`
            — the whole list, which is the exact opposite of the last zero items.
            Every positive `n` behaves, including an `n` larger than the list,
            which is what makes this so durable: the code looks like it has
            already thought about the boundaries. The honest spell handles the
            non-positive case before it ever builds the slice. This bug loves
            pagination code, where the page size arrives from a request.
        """,
        worked="""
            `[[1, 2, 3], 0]`

            Honest: []. The last zero items is nothing.
            Suspect: [1, 2, 3]. `items[-0:]` is `items[0:]`.

            `[[1, 2, 3], -1]` is the sibling: the suspect spell returns [2, 3],
            having read a negative count as an offset from the end. Any slice built
            from an arithmetic expression deserves the input that drives that
            expression to zero.
        """,
        time="O(n)", space="O(n)"))

    return out


# ---------------------------------------------------------------------------
# COMPLEXITY MATCH
#
# The snippets inside one puzzle are always near-twins doing the SAME job. That
# is the only way to make the question about work rather than about shape: two
# functions with identical signatures and identical answers, where one of them
# hides a loop inside a method call.
# ---------------------------------------------------------------------------

def _prices() -> list:
    out = []

    out.append(_price(
        pid="cx-baseline-three-spells", title="Three Plain Spells",
        realm="python_village", difficulty="TUTORIAL", family="python_basics",
        secondary=["ARRAY"],
        statement="""
            Three spells, all reading the same list of n items. Price each one.
            Start with the cheapest and use it as your ruler.
        """,
        snippets=[
            ("First Sight", """
                def first_item(items):
                    return items[0]
            """, "O(1)",
             "Indexing a list jumps straight to the slot. It does not matter "
             "whether the list holds ten items or ten million."),
            ("One Sweep", """
                def total(items):
                    running = 0
                    for item in items:
                        running += item
                    return running
            """, "O(n)",
             "One pass, one cheap operation per item. Doubling the list doubles "
             "the work."),
            ("Every Pair", """
                def any_pair_sums(items, target):
                    for a in items:
                        for b in items:
                            if a + b == target:
                                return True
                    return False
            """, "O(n^2)",
             "The inner loop runs the full length of the list for every item in "
             "the outer loop. The early `return` helps some inputs and none of "
             "the ones you have to price for."),
        ],
        nudge="Count the work one item costs, then count how many items pay it.",
        explanation="""
            The whole of complexity analysis is in these three. Nothing that
            depends on the input is constant; one pass is linear; a pass inside a
            pass is quadratic. Note that `any_pair_sums` may return on its first
            comparison — complexity describes the worst case, because the worst
            case is what wakes you up at night.
        """))

    out.append(_price(
        pid="cx-count-inside-loop", title="The Loop That Does Not Look Like One",
        realm="hashmap_highlands", difficulty="EASY", family="counting",
        secondary=["HASH_MAP", "SORTING"],
        statement="""
            Three spells that all return the items appearing exactly once, in the
            original order, from a list of n items. Same answer, three prices.
        """,
        snippets=[
            ("Ask Each Time", """
                def loners(items):
                    out = []
                    for item in items:
                        if items.count(item) == 1:
                            out.append(item)
                    return out
            """, "O(n^2)",
             "`items.count(item)` walks the entire list. It is a loop wearing a "
             "method call as a disguise, and it runs once per item: n items times "
             "an n-long walk."),
            ("Count Once, Then Ask", """
                def loners(items):
                    seen = {}
                    for item in items:
                        seen[item] = seen.get(item, 0) + 1
                    return [item for item in items if seen[item] == 1]
            """, "O(n)",
             "Two separate passes, each doing O(1) work per item. Two passes is "
             "still linear — constants do not change the class."),
            ("Sort, Then Look Sideways", """
                def loners(items):
                    ordered = sorted(items)
                    out = []
                    for i, item in enumerate(ordered):
                        before = i > 0 and ordered[i - 1] == item
                        after = i + 1 < len(ordered) and ordered[i + 1] == item
                        if not before and not after:
                            out.append(item)
                    return out
            """, "O(n log n)",
             "The scan afterwards is linear, so the sort dominates. When a linear "
             "pass follows a sort, the sort is the price."),
        ],
        nudge="One of these calls a method that is secretly a loop. Method calls "
              "are not free and are not one step.",
        explanation="""
            `count`, `index`, `in` against a list, `remove`, `max` and `min` all
            walk the whole sequence. Put any of them inside a loop over the same
            sequence and you have written a quadratic algorithm that occupies four
            lines and contains one visible `for`. This is the single most common
            accidental O(n^2) in interview code, and the fix is always the same:
            do the counting once, up front, into a dict.
        """))

    out.append(_price(
        pid="cx-membership-list-vs-set", title="What `in` Actually Costs",
        realm="hashmap_highlands", difficulty="EASY", family="set_ops",
        secondary=["SET", "HASH_MAP"],
        statement="""
            `guests` and `invited` each hold n names. Every spell returns the
            guests who were not invited. Only the lookup differs.
        """,
        snippets=[
            ("Against a List", """
                def crashers(guests, invited):
                    out = []
                    for name in guests:
                        if name not in invited:
                            out.append(name)
                    return out
            """, "O(n^2)",
             "`invited` is a list, so `not in` scans it from the front every "
             "time — n names each paying an n-long scan."),
            ("Against a Set", """
                def crashers(guests, invited):
                    allowed = set(invited)
                    return [name for name in guests if name not in allowed]
            """, "O(n)",
             "Building the set costs one pass. After that each lookup is a hash "
             "and a bucket check: O(1), regardless of size."),
            ("Against a Sorted List", """
                import bisect

                def crashers(guests, invited):
                    ordered = sorted(invited)
                    out = []
                    for name in guests:
                        i = bisect.bisect_left(ordered, name)
                        if i == len(ordered) or ordered[i] != name:
                            out.append(name)
                    return out
            """, "O(n log n)",
             "Sorting costs n log n, then n binary searches cost log n each — "
             "n log n again. Correct, and strictly worse than the set."),
        ],
        nudge="`x in something` is not one operation. Its price depends entirely "
              "on what `something` is.",
        explanation="""
            The two spells differ by one call to `set()`, and that call is the
            difference between linear and quadratic. `in` against a list or a
            tuple is a scan; `in` against a set or a dict is a hash lookup. Saying
            this out loud — "I'll put the invited list in a set so membership is
            O(1)" — is most of what an interviewer wants to hear, and it is the
            same sentence every time.
        """))

    out.append(_price(
        pid="cx-string-building", title="Building a String Brick by Brick",
        realm="stringwood_labyrinth", difficulty="EASY",
        family="onboarding_strings", secondary=["STRING"],
        statement="""
            Four spells over strings. `words` holds n words and `text` holds n
            characters. Price each.
        """,
        snippets=[
            ("Brick by Brick", """
                def render(words):
                    out = ""
                    for word in words:
                        out = out + word
                    return out
            """, "O(n^2)",
             "Strings are immutable, so each `+` builds a whole new string and "
             "copies everything written so far. Step k copies k characters, and "
             "those copies add up to n^2 / 2. CPython sometimes patches this in "
             "place when nothing else holds the string, but that is an "
             "implementation detail that vanishes the moment another name "
             "refers to it — it is not the number to quote in an interview."),
            ("All at Once", """
                def render(words):
                    return "".join(words)
            """, "O(n)",
             "`join` measures the total length first, allocates once, and copies "
             "each character exactly once."),
            ("Backwards", """
                def flip(text):
                    return text[::-1]
            """, "O(n)",
             "A reversed slice builds one new string of the same length. One "
             "copy, one pass."),
            ("How Long Is It", """
                def size(text):
                    return len(text)
            """, "O(1)",
             "The length is stored on the object. `len` reads a field; it does "
             "not count anything."),
        ],
        nudge="Two of these build a new string, one reads a number that is "
              "already there, and one of the builders is doing far more work "
              "than the other.",
        explanation="""
            Accumulating a string with `+=` in a loop is the string version of
            calling `count` inside a loop: a quadratic algorithm that looks like a
            single pass. Collect the pieces in a list and `join` them once. The
            same argument applies to building a list with `result = result + [x]`,
            which copies the whole list every iteration, while `result.append(x)`
            does not.
        """))

    out.append(_price(
        pid="cx-slice-per-iteration", title="The Slice Inside the Loop",
        realm="sliding_window_marsh", difficulty="MEDIUM", family="prefix_sum",
        secondary=["PREFIX_SUM", "ARRAY"],
        statement="""
            `nums` holds n numbers. The first two spells compute the same thing:
            for each position, the total of everything from that position to the
            end. Price all four.
        """,
        snippets=[
            ("Sum the Tail Every Time", """
                def suffix_totals(nums):
                    return [sum(nums[i:]) for i in range(len(nums))]
            """, "O(n^2)",
             "`nums[i:]` copies the tail, which is O(n) work on its own, and then "
             "`sum` walks that copy. Both happen once per position."),
            ("Sum the Tail Once", """
                def suffix_totals(nums):
                    out = [0] * len(nums)
                    running = 0
                    for i in range(len(nums) - 1, -1, -1):
                        running += nums[i]
                        out[i] = running
                    return out
            """, "O(n)",
             "Walking from the right lets each total reuse the one after it. Every "
             "element is touched exactly once."),
            ("One Copy", """
                def snapshot(nums):
                    return nums[:]
            """, "O(n)",
             "A full slice copies every element once. Cheap per element, linear "
             "overall, and easy to forget is not free."),
            ("Halve Until Found", """
                def rank_of(sorted_nums, value):
                    lo, hi = 0, len(sorted_nums)
                    while lo < hi:
                        mid = (lo + hi) // 2
                        if sorted_nums[mid] < value:
                            lo = mid + 1
                        else:
                            hi = mid
                    return lo
            """, "O(log n)",
             "Each turn of the loop discards half of what is left. Doubling the "
             "list adds one iteration."),
        ],
        nudge="A slice is not a view. It is a copy, and copies cost what they "
              "copy.",
        explanation="""
            The first two spells return identical lists and differ by a factor of
            n. A slice taken inside a loop is the third disguise in the same
            family as `count` and `in`: it looks like indexing and it behaves like
            iteration. Whenever you see a slice in a loop body, ask whether the
            work it repeats could be carried forward in a running variable
            instead — which is precisely the prefix-sum idea.
        """))

    out.append(_price(
        pid="cx-anagram-four-ways", title="Four Ways to Compare Two Bags",
        realm="hashmap_highlands", difficulty="MEDIUM", family="anagrams",
        secondary=["HASH_MAP", "SORTING", "STRING"],
        statement="""
            `a` and `b` are strings of n characters. The first three spells decide
            whether they contain the same letters; the fourth only checks a
            necessary condition. Price all four.
        """,
        snippets=[
            ("Sort Both", """
                def same_letters(a, b):
                    return sorted(a) == sorted(b)
            """, "O(n log n)",
             "Two sorts and one comparison. The sorts dominate. Shortest to "
             "write, and not the fastest."),
            ("Count Both", """
                def same_letters(a, b):
                    counts = {}
                    for ch in a:
                        counts[ch] = counts.get(ch, 0) + 1
                    for ch in b:
                        if ch not in counts:
                            return False
                        counts[ch] -= 1
                        if counts[ch] == 0:
                            del counts[ch]
                    return not counts
            """, "O(n)",
             "Two linear passes over dict operations that are O(1) each. Note the "
             "`del` at zero — without it the final `not counts` would never be "
             "true."),
            ("Cross Them Off One at a Time", """
                def same_letters(a, b):
                    left = list(a)
                    for ch in b:
                        if ch not in left:
                            return False
                        left.remove(ch)
                    return not left
            """, "O(n^2)",
             "`ch not in left` scans the list and `left.remove(ch)` scans it "
             "again, both inside a loop over n characters. Two hidden loops in "
             "one body."),
            ("Length First", """
                def could_match(a, b):
                    return len(a) == len(b)
            """, "O(1)",
             "Two stored lengths compared. It does not answer the question, but "
             "it is the right first line of the one that does."),
        ],
        nudge="Three of these give the same answer. Only one of them is doing "
              "work proportional to the input once.",
        explanation="""
            This is the anagram question priced honestly. Sorting is the answer
            most people reach for and it is n log n; counting is linear and is
            what an interviewer is listening for. The third looks like counting
            and is quadratic, because `in` and `remove` are each a scan. The
            fourth is the guard clause every version should open with.
        """))

    out.append(_price(
        pid="cx-recursion-costs", title="The Cost of Calling Yourself",
        realm="recursive_forest", difficulty="MEDIUM", family="recursion_basics",
        secondary=["RECURSION", "DP"],
        statement="""
            Four recursive spells. `n` is the number given, or the length of the
            list. Price each by how many calls actually happen.
        """,
        snippets=[
            ("Plain Recursion", """
                def fib(n):
                    if n < 2:
                        return n
                    return fib(n - 1) + fib(n - 2)
            """, "O(2^n)",
             "Each call spawns two more and nothing is remembered, so the call "
             "tree roughly doubles per level. fib(40) makes over a billion calls "
             "to answer a question with 40 distinct sub-answers in it."),
            ("Recursion With a Memo", """
                def fib(n, memo=None):
                    if memo is None:
                        memo = {}
                    if n < 2:
                        return n
                    if n not in memo:
                        memo[n] = fib(n - 1, memo) + fib(n - 2, memo)
                    return memo[n]
            """, "O(n)",
             "There are only n distinct subproblems. The memo means each one is "
             "computed once and read thereafter."),
            ("Halving Recursion", """
                def find(sorted_nums, target, lo, hi):
                    if lo > hi:
                        return -1
                    mid = (lo + hi) // 2
                    if sorted_nums[mid] == target:
                        return mid
                    if sorted_nums[mid] < target:
                        return find(sorted_nums, target, mid + 1, hi)
                    return find(sorted_nums, target, lo, mid - 1)
            """, "O(log n)",
             "One call per level and each level halves the range. The depth is "
             "log n and nothing branches."),
            ("Split and Merge", """
                def merge_sort(items):
                    if len(items) < 2:
                        return items
                    mid = len(items) // 2
                    left = merge_sort(items[:mid])
                    right = merge_sort(items[mid:])
                    out = []
                    while left and right:
                        out.append(left.pop(0) if left[0] <= right[0]
                                   else right.pop(0))
                    return out + left + right
            """, "O(n log n)",
             "log n levels of splitting, and every level merges all n elements. "
             "Branching two ways while halving costs linear work per level."),
        ],
        nudge="Two of these branch and two do not. Of the two that branch, one "
              "remembers what it has already worked out.",
        explanation="""
            The shape of the call tree is the whole answer. One call per level and
            a halving input gives log n. Two calls per level with a halving input
            gives n log n. Two calls per level with an input shrinking by one gives
            2^n — unless the results are remembered, which collapses it to the
            number of distinct subproblems. That collapse is the entire idea of
            dynamic programming, stated in one line of dictionary lookup.
        """))

    out.append(_price(
        pid="cx-growing-a-list", title="Growing a List From Both Ends",
        realm="fields_of_syntax", difficulty="EASY",
        family="onboarding_collections", secondary=["ARRAY", "QUEUE"],
        statement="""
            Four spells that each build a collection of n items. Three of them
            cost the same. One does not.
        """,
        snippets=[
            ("Push to the Back", """
                def collect(items):
                    out = []
                    for item in items:
                        out.append(item)
                    return out
            """, "O(n)",
             "`append` writes into spare capacity at the end. It occasionally "
             "reallocates, but amortised over n appends it is O(1) each."),
            ("Push to the Front", """
                def collect(items):
                    out = []
                    for item in items:
                        out.insert(0, item)
                    return out
            """, "O(n^2)",
             "`insert(0, x)` shifts every existing element one slot to the right "
             "to make room. Doing that n times costs n^2 / 2 moves."),
            ("A Deque at the Front", """
                from collections import deque

                def collect(items):
                    out = deque()
                    for item in items:
                        out.appendleft(item)
                    return out
            """, "O(n)",
             "A deque is linked blocks, not one flat array, so there is nothing "
             "to shift. `appendleft` is O(1), which is the entire reason deque "
             "exists."),
            ("Stretch Once", """
                def collect(items):
                    out = []
                    out.extend(items)
                    return out
            """, "O(n)",
             "One bulk copy of n elements. The same total work as n appends, in "
             "one call."),
        ],
        nudge="Three of these add an item in constant time. One of them moves "
              "the whole collection to make room.",
        explanation="""
            A Python list is a flat array, so the front is the expensive end:
            `insert(0, x)` and `pop(0)` both shift everything. That is why a
            list-as-queue is quietly quadratic and why BFS should use
            `collections.deque`. Reaching for `deque` and being able to say "so
            popleft is O(1) instead of O(n)" is worth more in an interview than
            the traversal itself.
        """))

    out.append(_price(
        pid="cx-grid-work", title="Work on a Square Grid",
        realm="matrix_citadel", difficulty="MEDIUM", family="matrix_traverse",
        secondary=["MATRIX"],
        statement="""
            `grid` has n rows and n columns, so it holds n^2 cells. Price each
            spell in terms of n, not in terms of cells.
        """,
        snippets=[
            ("One Corner", """
                def corner(grid):
                    return grid[0][0]
            """, "O(1)",
             "Two index operations. The size of the grid never enters into it."),
            ("The Diagonal", """
                def trace(grid):
                    total = 0
                    for i in range(len(grid)):
                        total += grid[i][i]
                    return total
            """, "O(n)",
             "One cell per row. A square grid has n rows, so n cells — a tiny "
             "fraction of the n^2 that are there."),
            ("Every Cell", """
                def grid_total(grid):
                    total = 0
                    for row in grid:
                        for value in row:
                            total += value
                    return total
            """, "O(n^2)",
             "n rows times n columns. Linear in the number of CELLS, quadratic in "
             "n — which is why you have to say which variable you are pricing "
             "against."),
            ("Row Against Column", """
                def multiply(grid, other):
                    size = len(grid)
                    out = [[0] * size for _ in range(size)]
                    for r in range(size):
                        for c in range(size):
                            for k in range(size):
                                out[r][c] += grid[r][k] * other[k][c]
                    return out
            """, "O(n^3)",
             "n^2 output cells, each summing a row against a column of length n."),
        ],
        nudge="Say what n means before you price anything. Here it is the side of "
              "the grid, not the number of cells.",
        explanation="""
            Grid problems are where complexity answers most often get muddled,
            because there are two defensible variables: the side n and the cell
            count n^2. Both are correct; only one of them is what the interviewer
            asked. State your variable first — "n is the side length, so a full
            scan is O(n^2)" — and the ambiguity disappears.
        """))

    out.append(_price(
        pid="cx-lookup-four-ways", title="Four Ways to Look Something Up",
        realm="array_caverns", difficulty="MEDIUM", family="binary_search",
        secondary=["BINARY_SEARCH", "HASH_MAP"],
        statement="""
            n records, one lookup. Price the lookup as written, including any
            preparation the spell does for itself.
        """,
        snippets=[
            ("Walk Until Found", """
                def find(records, key):
                    for i, record in enumerate(records):
                        if record == key:
                            return i
                    return -1
            """, "O(n)",
             "A scan. Worst case is the last record or no record at all, and "
             "worst case is what gets priced."),
            ("Halve Until Found", """
                def find(sorted_records, key):
                    lo, hi = 0, len(sorted_records) - 1
                    while lo <= hi:
                        mid = (lo + hi) // 2
                        if sorted_records[mid] == key:
                            return mid
                        if sorted_records[mid] < key:
                            lo = mid + 1
                        else:
                            hi = mid - 1
                    return -1
            """, "O(log n)",
             "The records arrive already sorted, so the search pays nothing to "
             "prepare and halves its range each turn."),
            ("Sort First, Then Halve", """
                def find(records, key):
                    ordered = sorted(records)
                    lo, hi = 0, len(ordered) - 1
                    while lo <= hi:
                        mid = (lo + hi) // 2
                        if ordered[mid] == key:
                            return mid
                        if ordered[mid] < key:
                            lo = mid + 1
                        else:
                            hi = mid - 1
                    return -1
            """, "O(n log n)",
             "The sort costs n log n and swamps the log n search. Sorting to do "
             "ONE lookup is slower than simply walking the list."),
            ("Ask the Dictionary", """
                def find(index, key):
                    return index.get(key, -1)
            """, "O(1)",
             "A hash and a bucket read. Building `index` costs O(n) once, which "
             "is why this wins as soon as there is more than one lookup to do."),
        ],
        nudge="Preparation counts. A spell that sorts before it searches has paid "
              "for the sort.",
        explanation="""
            The trap is the third spell: it contains a binary search, so it looks
            logarithmic, and the sort above it makes it the most expensive of the
            four — worse than the naive scan it was meant to improve on. The
            question "how many times will this be looked up?" decides everything.
            Once: scan it. Many times: pay the O(n) to build a dict, then O(1)
            forever.
        """))

    return out


def build() -> list:
    """Every BREAK_IT and COMPLEXITY_MATCH problem in the corpus.

    The `probes` list inside each BREAK_IT mcq is the executable answer key: the
    inputs that genuinely break the suspect spell. It exists so the build can
    prove, by running them, that every one of these puzzles is actually solvable
    — a BREAK_IT with no working break is not a hard puzzle, it is a broken one.
    The front end has no use for it and never reads it.
    """
    return _shape_breaks() + _order_breaks() + _mechanism_breaks() + _prices()
