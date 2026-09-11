"""The Pythonic family: the standard library an interviewer expects you to reach for.

Every other family here trains an algorithm. This one trains RECOGNITION — seeing
the shape of a problem and knowing which import already solved it. An interviewer
watching you hand-roll a frequency dict, a max-heap or a memo table is not
watching you fail; they are watching you spend four of your forty minutes on
something the library ships.

The contrast is structural rather than decorative. For most problems here the
*reference implementation* is the long way — the hand-rolled loop that computes
the expected answers at build time — and the *canonical solution* is the two-line
import. The two must agree on every test, so the file itself is the claim it
makes: these produce the same answer, and one of them is shorter than the other.

The ramp is the other half of the point. Every topic enters at GUIDED, where the
player types a single expression into an otherwise complete, working function,
and only then climbs. No topic in this file debuts above GUIDED, and no topic
skips a rung: if you are reading a MEDIUM here, the GUIDED, the TUTORIAL and the
EASY for that same import sit above it in `build()`, in that order.

Topics, in build order:
    collections   Counter, defaultdict, deque, namedtuple, OrderedDict
    heapq         heappush/heappop, nsmallest, the negation trick, merge, bounded
    itertools     product, combinations, permutations, groupby, accumulate, chain
    functools     lru_cache, reduce, partial, cmp_to_key
    dataclasses, bisect, math, statistics, enum, typing
"""
from __future__ import annotations

import textwrap

from ._base import code_problem, dedent, mcq_problem

# The player this corpus is for. Recognition is the highest-yield thing an
# interview rewards per minute spent, so it is weighted accordingly.
Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 2.0}

VIZ = {"type": "array_scan", "caption": "The library already wrote this loop."}

VISUAL = {
    "GUIDED": "The function already works. One expression is missing and the code "
              "around it tells you exactly what that expression has to produce.",
    "TUTORIAL": "You know which import this is. Write the three lines that use it, "
                "and run after each one.",
    "EASY": "Name the shape first — counting, ordering, grouping, extremes — then "
            "name the import. The code comes last and takes a minute.",
    "MEDIUM": "The library gets you most of the way. The judgement left over is "
              "the part being tested.",
    "HARD": "Two imports and a decision about which one is doing the real work.",
}

DEFAULT_NUDGE = ("Say the shape of this out loud — counting, grouping, ordering, "
                 "extremes, pairs — and the import usually names itself.")

LONG_WAY_HEAD = ("THE LONG WAY, which is correct, and which is what most people "
                 "write under pressure:")
LONG_WAY_TAIL = ("Same answer, and the library version is the one you want in your "
                 "fingers when the clock is running.")


def _statement(text: str, long_way: str) -> str:
    body = dedent(text).rstrip()
    if not long_way:
        return body
    block = textwrap.indent(dedent(long_way).rstrip(), "    ")
    return body + "\n\n" + LONG_WAY_HEAD + "\n\n" + block + "\n\n" + LONG_WAY_TAIL


def _drill(pid, title, tier, statement, fn, params, ref, canonical, visible, hidden,
           *, pattern, family, starter="", edges=(), long_way="", same_move="",
           nudge="", pseudocode="", time="O(n)", space="O(n)", failures=(),
           cmp="exact", constraints=(), realm="fields_of_syntax", after="",
           tags=()):
    """One recognition drill.

    GUIDED tiers are MISSING_RUNE encounters and must ship a starter with a hole
    in it — a guided rung with no hole is a free clear, which is exactly the
    failure this family exists to avoid.
    """
    if tier == "GUIDED":
        if "__BLANK__" not in starter:
            raise ValueError(f"{pid}: a GUIDED drill needs a __BLANK__ starter")
    fragment = ""
    if same_move:
        fragment = ("```python\n# the same move, on something else:\n"
                    + dedent(same_move).rstrip() + "\n```")
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=tier,
        family=family, profile_weight=Q, viz=VIZ,
        statement=_statement(statement, long_way),
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        visible=visible, hidden=hidden, edges=edges, cmp=cmp,
        time_complexity=time, space_complexity=space,
        constraints=list(constraints), failures=list(failures),
        nudge=nudge or DEFAULT_NUDGE, visual=VISUAL[tier],
        pseudocode=pseudocode, fragment=fragment,
        starter_code=starter, prerequisites=[after] if after else [],
        encounter="MISSING_RUNE" if tier == "GUIDED" else "CODE_BATTLE",
        tags=["stdlib", "recognition", "topic:" + family] + list(tags),
    )


# ---------------------------------------------------------------------------
# Reference implementations.
#
# These are deliberately the hand-rolled versions. They are what the canonical
# solutions replace, and the validator only ships a problem when the two agree.
# ---------------------------------------------------------------------------

# -- collections.Counter -----------------------------------------------------
def _char_tally(text):
    out = {}
    for ch in text:
        out[ch] = out.get(ch, 0) + 1
    return out


def _top_word(words):
    tally = {}
    for word in words:
        tally[word] = tally.get(word, 0) + 1
    best = None
    for word in sorted(tally):
        if best is None or tally[word] > tally[best]:
            best = word
    return best


def _can_build(note, letters):
    pool = {}
    for ch in letters:
        pool[ch] = pool.get(ch, 0) + 1
    for ch in note:
        if pool.get(ch, 0) == 0:
            return False
        pool[ch] -= 1
    return True


# -- collections.defaultdict -------------------------------------------------
def _group_by_initial(words):
    groups = {}
    for word in words:
        if word[0] not in groups:
            groups[word[0]] = []
        groups[word[0]].append(word)
    return groups


def _index_positions(items):
    out = {}
    for i in range(len(items)):
        if items[i] in out:
            out[items[i]].append(i)
        else:
            out[items[i]] = [i]
    return out


def _adjacency(edges):
    out = {}
    for pair in edges:
        a, b = pair[0], pair[1]
        out.setdefault(a, [])
        out.setdefault(b, [])
        if b not in out[a]:
            out[a].append(b)
        if a not in out[b]:
            out[b].append(a)
    return {node: sorted(out[node]) for node in sorted(out)}


# -- collections.deque -------------------------------------------------------
def _serve_queue(names, count):
    line = list(names)
    served = []
    while line and len(served) < count:
        served.append(line.pop(0))
    return [served, line]


def _rotate_right(items, k):
    if not items:
        return []
    k = k % len(items)
    cut = len(items) - k
    return list(items[cut:]) + list(items[:cut])


def _recent(lines, keep):
    if keep <= 0:
        return []
    return list(lines[-keep:])


# -- collections.namedtuple --------------------------------------------------
def _furthest_x(rows):
    best = rows[0][0]
    for row in rows:
        if row[0] > best:
            best = row[0]
    return best


def _rank_players(rows):
    ordered = sorted(rows, key=lambda row: (-row[1], row[0]))
    return [[row[0], row[1]] for row in ordered]


# -- collections.OrderedDict -------------------------------------------------
def _touch_order(keys, touches):
    order = []
    for key in keys:
        if key not in order:
            order.append(key)
    for key in touches:
        if key in order:
            order.remove(key)
            order.append(key)
    return order


def _fifo_evict(keys, capacity):
    out = []
    for key in keys:
        if key in out:
            continue
        out.append(key)
        if len(out) > capacity:
            out.pop(0)
    return out


# -- heapq -------------------------------------------------------------------
def _drain_sorted(nums):
    rest = list(nums)
    out = []
    while rest:
        smallest = rest[0]
        for value in rest:
            if value < smallest:
                smallest = value
        rest.remove(smallest)
        out.append(smallest)
    return out


def _k_smallest(nums, k):
    if k <= 0:
        return []
    return _drain_sorted(nums)[:k]


def _top_three_costs(prices):
    ordered = _drain_sorted(prices)
    ordered.reverse()
    return ordered[:3]


def _merge_sorted(lists):
    pooled = []
    for row in lists:
        pooled.extend(row)
    return _drain_sorted(pooled)


def _stream_top_k(values, k):
    if k <= 0:
        return []
    ordered = _drain_sorted(values)
    ordered.reverse()
    return ordered[:k]


# -- itertools ---------------------------------------------------------------
def _all_pairs(a, b):
    out = []
    for x in a:
        for y in b:
            out.append([x, y])
    return out


def _pin_codes(digits, length):
    codes = [""]
    for _ in range(length):
        grown = []
        for code in codes:
            for digit in digits:
                grown.append(code + digit)
        codes = grown
    return codes


def _winning_rolls(faces, dice, target):
    ways = {0: 1}
    for _ in range(dice):
        nxt = {}
        for total, count in ways.items():
            for face in range(1, faces + 1):
                nxt[total + face] = nxt.get(total + face, 0) + count
        ways = nxt
    return ways.get(target, 0)


def _pairs(items):
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            out.append([items[i], items[j]])
    return out


def _pair_sums(nums):
    out = []
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            out.append(nums[i] + nums[j])
    return sorted(out)


def _best_trio(scores):
    ordered = sorted(scores, reverse=True)
    return sum(ordered[:3])


def _arrangements(items):
    if not items:
        return [[]]
    out = []
    for i in range(len(items)):
        rest = list(items[:i]) + list(items[i + 1:])
        for tail in _arrangements(rest):
            out.append([items[i]] + tail)
    return sorted(out)


def _unique_arrangements(text):
    seen = set()
    for arrangement in _arrangements(list(text)):
        seen.add("".join(arrangement))
    return sorted(seen)


def _run_lengths(items):
    out = []
    for value in items:
        if out and out[-1][0] == value:
            out[-1][1] += 1
        else:
            out.append([value, 1])
    return out


def _encode_runs(text):
    parts = []
    for value, count in _run_lengths(list(text)):
        parts.append(value + str(count))
    return "".join(parts)


def _longest_run(items):
    if not items:
        return []
    best = [items[0], 0]
    for value, count in _run_lengths(items):
        if count > best[1]:
            best = [value, count]
    return best


def _running_totals(nums):
    out, total = [], 0
    for value in nums:
        total += value
        out.append(total)
    return out


def _running_max(nums):
    out, best = [], None
    for value in nums:
        if best is None or value > best:
            best = value
        out.append(best)
    return out


def _lowest_balance(deltas):
    balance, lowest = 0, None
    for delta in deltas:
        balance += delta
        if lowest is None or balance < lowest:
            lowest = balance
    return 0 if lowest is None else lowest


def _flatten(nested):
    out = []
    for row in nested:
        for value in row:
            out.append(value)
    return out


def _merge_feeds(a, b, c):
    seen, out = set(), []
    for row in (a, b, c):
        for value in row:
            if value not in seen:
                seen.add(value)
                out.append(value)
    return out


# -- functools ---------------------------------------------------------------
def _fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _climb(n):
    if n < 0:
        return 0
    ways = [0] * (n + 1)
    ways[0] = 1
    for step in range(1, n + 1):
        ways[step] = ways[step - 1] + (ways[step - 2] if step >= 2 else 0)
    return ways[n]


def _grid_paths(rows, cols):
    if rows <= 0 or cols <= 0:
        return 0
    table = [[1] * cols for _ in range(rows)]
    for r in range(1, rows):
        for c in range(1, cols):
            table[r][c] = table[r - 1][c] + table[r][c - 1]
    return table[rows - 1][cols - 1]


def _min_coins(coins, amount):
    unreachable = float("inf")
    best = [0] + [unreachable] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if 0 < coin <= value and best[value - coin] + 1 < best[value]:
                best[value] = best[value - coin] + 1
    return -1 if best[amount] == unreachable else best[amount]


def _product_of(nums):
    total = 1
    for value in nums:
        total *= value
    return total


def _merge_all(dicts):
    out = {}
    for mapping in dicts:
        for key, value in mapping.items():
            out[key] = value
    return out


def _intersect_all(lists):
    if not lists:
        return []
    common = set(lists[0])
    for row in lists[1:]:
        common &= set(row)
    return sorted(common)


def _scaled(values, factor):
    return [value * factor for value in values]


def _clamp_all(values, lo, hi):
    return [max(lo, min(hi, value)) for value in values]


def _by_length(words):
    return sorted(words, key=lambda word: (len(word), word))


def _by_magnitude(nums):
    return sorted(nums, key=lambda value: (abs(value), value))


def _by_version(versions):
    return sorted(versions, key=lambda v: [int(part) for part in v.split(".")])


def _largest_number(nums):
    parts = [str(n) for n in nums]
    for i in range(len(parts)):
        for j in range(len(parts) - 1 - i):
            if parts[j] + parts[j + 1] < parts[j + 1] + parts[j]:
                parts[j], parts[j + 1] = parts[j + 1], parts[j]
    joined = "".join(parts)
    return "0" if joined[:1] == "0" else joined


# -- dataclasses, bisect, math, statistics, enum -----------------------------
def _cart_total(rows):
    total = 0.0
    for row in rows:
        price = row[1]
        qty = row[2] if len(row) > 2 else 1
        total += price * qty
    return total


def _ranked(rows):
    ordered = sorted(rows, key=lambda row: (row[0], row[1]))
    return [[row[0], row[1]] for row in ordered]


def _insert_position(values, target):
    pos = 0
    while pos < len(values) and values[pos] < target:
        pos += 1
    return pos


def _place(values, target):
    out = list(values)
    pos = 0
    while pos < len(out) and out[pos] <= target:
        pos += 1
    out.insert(pos, target)
    return out


def _count_in_range(values, lo, hi):
    return sum(1 for value in values if lo <= value <= hi)


def _gcd_pair(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def _is_perfect_square(n):
    if n < 0:
        return False
    guess = 0
    while guess * guess < n:
        guess += 1
    return guess * guess == n


def _average(values):
    return sum(values) / len(values)


def _centre(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return [sum(values) / n, median]


_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


def _at_least(names, floor):
    cutoff = _LEVELS[floor]
    return [name for name in names if _LEVELS[name] >= cutoff]


def _louder_than(floor):
    cutoff = _LEVELS[floor]
    ordered = sorted(_LEVELS.items(), key=lambda kv: kv[1])
    return [name for name, value in ordered if value > cutoff]


def build() -> list:
    return [
        # ===================================================================
        # collections.Counter
        # ===================================================================
        _drill(
            "py-counter-guided", "The Tally That Ships With Python", "GUIDED",
            """
            A frequency table is the most common data structure in a correct
            interview answer, and `collections.Counter` is one. Hand it anything
            you can iterate and it counts the items for you.

            Return a plain dict mapping each character of `text` to its count.
            """,
            "char_tally", "text", _char_tally,
            """
            from collections import Counter


            def char_tally(text):
                counts = Counter(text)
                return dict(counts)
            """,
            [("hello", ["hello"]), ("repeats", ["aab"])],
            [("spaces count too", ["a a b"]), ("case matters", ["Aa"]),
             ("digits", ["112"])],
            edges=[("empty text", [""])],
            pattern="HASH_MAP", family="stdlib_counter",
            starter="""
            from collections import Counter


            def char_tally(text):
                # 1. Counter counts whatever you iterate. Hand it the text.
                counts = __BLANK__
                return dict(counts)
            """,
            long_way="""
            counts = {}
            for ch in text:
                if ch in counts:
                    counts[ch] += 1
                else:
                    counts[ch] = 1
            return counts
            """,
            same_move="Counter(['a', 'b', 'a'])   # Counter({'a': 2, 'b': 1})",
            nudge="`Counter(iterable)` is the whole answer. `dict(...)` around it "
                  "only strips the subclass so the test sees a plain dict.",
            pseudocode="dict(Counter(text))",
            failures=["Using `counts[ch] += 1` on a plain dict and meeting KeyError"],
            time="O(n)", space="O(k)",
        ),

        _drill(
            "py-counter-top-word", "The Loudest Word", "TUTORIAL",
            """
            Return the word that appears most often in `words`. If several words
            tie, return the alphabetically first of them. Return None for an
            empty list.

            Counter gives you the counts; the tie rule is yours to state.
            """,
            "top_word", "words", _top_word,
            """
            from collections import Counter


            def top_word(words):
                counts = Counter(words)
                if not counts:
                    return None
                # most_common breaks ties by insertion order, which is not the
                # rule we were given, so sort explicitly on the rule we were.
                return min(counts, key=lambda word: (-counts[word], word))
            """,
            [("clear winner", [["fire", "fire", "ice"]]),
             ("tie goes alphabetical", [["ice", "fire"]])],
            [("single word", [["one"]]),
             ("three way", [["c", "b", "a", "b"]]),
             ("all identical", [["x", "x", "x"]])],
            edges=[("empty", [[]])],
            pattern="HASH_MAP", family="stdlib_counter",
            after="py-counter-guided",
            nudge="`min(counts, key=...)` with a `(-count, word)` key gives you "
                  "'most frequent, ties alphabetical' in one expression.",
            pseudocode="counts = Counter(words)\nreturn min(counts, key=(-count, word))",
            failures=["Trusting most_common() to break ties the way the question asks"],
            time="O(n log n)", space="O(k)",
        ),

        _drill(
            "py-counter-ransom", "What The Note Still Needs", "EASY",
            """
            You have a pile of `letters` and a `note` you want to spell with them.
            Each letter in the pile may be used once. Return True if the note can
            be spelled, False otherwise.

            Counters subtract. `Counter(note) - Counter(letters)` drops every
            non-positive count, so what survives is exactly what is still missing.
            """,
            "can_build", "note, letters", _can_build,
            """
            from collections import Counter


            def can_build(note, letters):
                missing = Counter(note) - Counter(letters)
                return not missing
            """,
            [("enough letters", ["aab", "aabb"]), ("one short", ["aab", "ab"])],
            [("exact pile", ["abc", "cba"]), ("spare letters", ["a", "zzza"]),
             ("repeat heavy", ["aaa", "aa"])],
            edges=[("empty note", ["", ""]), ("empty pile", ["a", ""])],
            pattern="HASH_MAP", family="stdlib_counter",
            after="py-counter-top-word",
            long_way="""
            pool = {}
            for ch in letters:
                pool[ch] = pool.get(ch, 0) + 1
            for ch in note:
                if pool.get(ch, 0) == 0:
                    return False
                pool[ch] -= 1
            return True
            """,
            nudge="Counter supports -, +, & and |. Subtraction is the one that "
                  "answers 'what do I still need?'.",
            pseudocode="return not (Counter(note) - Counter(letters))",
            failures=["Using `&` (intersection) when you meant `-` (what is left owing)"],
            cmp="bool", time="O(n)", space="O(k)",
        ),

        # ===================================================================
        # collections.defaultdict
        # ===================================================================
        _drill(
            "py-defaultdict-guided", "The Dict That Expects You", "GUIDED",
            """
            `defaultdict(list)` is a dict that creates an empty list the first
            time you touch a missing key. That single behaviour deletes the
            'have I seen this key before?' branch from every grouping loop you
            will ever write.

            Group `words` by their first letter. Return a plain dict mapping each
            first letter to the words that start with it, in input order.
            """,
            "group_by_initial", "words", _group_by_initial,
            """
            from collections import defaultdict


            def group_by_initial(words):
                groups = defaultdict(list)
                for word in words:
                    groups[word[0]].append(word)
                return dict(groups)
            """,
            [("two groups", [["ash", "arc", "bolt"]]),
             ("one each", [["x", "y"]])],
            [("all same letter", [["ka", "kb", "kc"]]),
             ("order preserved", [["bee", "ant", "bat"]]),
             ("single word", [["solo"]])],
            edges=[("empty", [[]])],
            pattern="HASH_MAP", family="stdlib_defaultdict",
            starter="""
            from collections import defaultdict


            def group_by_initial(words):
                # 1. A dict whose missing values are born as empty lists.
                groups = __BLANK__
                for word in words:
                    groups[word[0]].append(word)
                return dict(groups)
            """,
            long_way="""
            groups = {}
            for word in words:
                if word[0] not in groups:
                    groups[word[0]] = []
                groups[word[0]].append(word)
            return groups
            """,
            same_move="tallies = defaultdict(int)   # missing keys start at 0",
            nudge="You pass the factory itself, not a call to it: "
                  "`defaultdict(list)`, never `defaultdict(list())`.",
            pseudocode="groups = defaultdict(list)\nfor word: groups[word[0]].append(word)",
            failures=["Writing `defaultdict(list())`, which passes an empty list "
                      "instead of the list type"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-defaultdict-index", "Every Place It Appeared", "TUTORIAL",
            """
            Return a dict mapping each value in `items` to the list of indexes
            where it appears, ascending. This is the shape behind most
            'find the duplicate / find the pair' answers, and `enumerate` plus
            `defaultdict(list)` writes it in three lines.
            """,
            "index_positions", "items", _index_positions,
            """
            from collections import defaultdict


            def index_positions(items):
                found = defaultdict(list)
                for index, value in enumerate(items):
                    found[value].append(index)
                return dict(found)
            """,
            [("one duplicate", [["a", "b", "a"]]), ("no duplicates", [["x", "y"]])],
            [("all identical", [["k", "k", "k"]]),
             ("numbers", [[3, 1, 3, 3]]),
             ("single", [[7]])],
            edges=[("empty", [[]])],
            pattern="HASH_MAP", family="stdlib_defaultdict",
            after="py-defaultdict-guided",
            nudge="`enumerate` hands you index and value together, which is the "
                  "other half of this idiom.",
            pseudocode="found = defaultdict(list)\nfor i, v in enumerate(items): found[v].append(i)",
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-defaultdict-adjacency", "Building The Map", "EASY",
            """
            `edges` is a list of [a, b] pairs in an undirected graph. Return a
            dict mapping each node to its sorted list of neighbours, with the
            keys themselves in sorted order.

            Every graph question starts here. If building the adjacency list
            costs you five minutes you have lost the question before it began.
            """,
            "adjacency", "edges", _adjacency,
            """
            from collections import defaultdict


            def adjacency(edges):
                graph = defaultdict(set)
                for a, b in edges:
                    # A set absorbs a repeated edge without a membership check.
                    graph[a].add(b)
                    graph[b].add(a)
                return {node: sorted(graph[node]) for node in sorted(graph)}
            """,
            [("triangle", [[["a", "b"], ["b", "c"], ["c", "a"]]]),
             ("single edge", [[["x", "y"]]])],
            [("repeated edge", [[["a", "b"], ["b", "a"]]]),
             ("star", [[["hub", "a"], ["hub", "b"], ["hub", "c"]]]),
             ("chain", [[["a", "b"], ["b", "c"]]])],
            edges=[("no edges", [[]]), ("self loop", [[["a", "a"]]])],
            pattern="HASH_MAP", family="stdlib_defaultdict",
            after="py-defaultdict-index",
            nudge="`defaultdict(set)` for the build, then one comprehension to "
                  "turn it into the sorted shape the answer wants.",
            pseudocode="graph = defaultdict(set)\nfor a, b in edges: add both directions\nsort at the end",
            failures=["Adding only one direction of an undirected edge",
                      "Forgetting that a repeated edge must not duplicate a neighbour"],
            time="O(e log e)", space="O(n + e)",
        ),

        # ===================================================================
        # collections.deque
        #
        # These three carry the spaced-repetition family `onboarding_collections`
        # rather than a stdlib_* name of their own. Chapter III claims that family
        # by name and its pattern list does not include QUEUE, so this is what
        # lets the deque ramp appear in the chapter whose blurb promises it
        # instead of waiting until Chapter VI.
        # ===================================================================
        _drill(
            "py-deque-guided", "Both Ends, O(1)", "GUIDED",
            """
            `list.pop(0)` is O(n): every remaining element shuffles down one slot.
            `collections.deque` pops from either end in constant time, which is
            why every BFS you will ever write starts with one.

            Serve the first `count` names from the queue. Return
            [served, still_waiting].
            """,
            "serve_queue", "names, count", _serve_queue,
            """
            from collections import deque


            def serve_queue(names, count):
                line = deque(names)
                served = []
                while line and len(served) < count:
                    served.append(line.popleft())
                return [served, list(line)]
            """,
            [("serve two", [["a", "b", "c"], 2]), ("serve none", [["a"], 0])],
            [("serve all", [["a", "b"], 2]),
             ("count exceeds line", [["a"], 5]),
             ("one waiting", [["a", "b"], 1])],
            edges=[("empty line", [[], 3])],
            pattern="QUEUE", family="onboarding_collections",
            starter="""
            from collections import deque


            def serve_queue(names, count):
                line = deque(names)
                served = []
                while line and len(served) < count:
                    # 1. Take the person at the FRONT of the line.
                    served.append(__BLANK__)
                return [served, list(line)]
            """,
            same_move="history.appendleft(event)   # push onto the front instead",
            nudge="`popleft()` takes from the front, `pop()` from the back. Both "
                  "are O(1) on a deque.",
            pseudocode="line = deque(names)\nwhile line and served < count: served.append(line.popleft())",
            failures=["Reaching for `list.pop(0)` and quietly making the loop O(n^2)"],
            time="O(k)", space="O(n)",
        ),

        _drill(
            "py-deque-rotate", "Turning The Wheel", "TUTORIAL",
            """
            Rotate `items` to the right by `k` positions and return the result as
            a list. `k` may be larger than the list, and may be negative (which
            rotates left). A deque does this in one method call.
            """,
            "rotate_right", "items, k", _rotate_right,
            """
            from collections import deque


            def rotate_right(items, k):
                wheel = deque(items)
                wheel.rotate(k)
                return list(wheel)
            """,
            [("by one", [["a", "b", "c"], 1]), ("by two", [[1, 2, 3, 4], 2])],
            [("k larger than list", [[1, 2, 3], 7]),
             ("negative k rotates left", [[1, 2, 3], -1]),
             ("k is zero", [[1, 2], 0])],
            edges=[("empty", [[], 3]), ("single element", [[9], 5])],
            pattern="QUEUE", family="onboarding_collections",
            after="py-deque-guided",
            long_way="""
            if not items:
                return []
            k = k % len(items)
            cut = len(items) - k
            return items[cut:] + items[:cut]
            """,
            nudge="`deque.rotate(k)` already handles k bigger than the deque and "
                  "negative k. You do not need the modulo.",
            pseudocode="wheel = deque(items); wheel.rotate(k); return list(wheel)",
            failures=["Taking `% len(items)` on an empty list and dividing by zero"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-deque-window", "The Last N Things", "EASY",
            """
            Return the last `keep` entries of `lines`, in order. If `keep` is zero
            or negative, return an empty list.

            `deque(lines, maxlen=keep)` keeps a bounded window for free: once it
            is full, every append silently drops the oldest item. That is a log
            tail, a recent-events buffer, and half of every rate limiter.
            """,
            "recent", "lines, keep", _recent,
            """
            from collections import deque


            def recent(lines, keep):
                if keep <= 0:
                    # deque refuses a negative maxlen, so rule it out up front.
                    return []
                window = deque(lines, maxlen=keep)
                return list(window)
            """,
            [("last two", [["a", "b", "c"], 2]), ("keep more than exist", [["a"], 5])],
            [("keep one", [["a", "b", "c"], 1]),
             ("keep exactly all", [["a", "b"], 2]),
             ("keep zero", [["a", "b"], 0])],
            edges=[("empty lines", [[], 2]), ("negative keep", [["a"], -1])],
            pattern="QUEUE", family="onboarding_collections",
            after="py-deque-rotate",
            nudge="A bounded deque never grows. That is the point: constant memory "
                  "over an unbounded stream.",
            pseudocode="if keep <= 0: return []\nreturn list(deque(lines, maxlen=keep))",
            failures=["Passing a negative maxlen, which raises ValueError"],
            time="O(n)", space="O(k)",
        ),

        # ===================================================================
        # collections.namedtuple
        # ===================================================================
        _drill(
            "py-namedtuple-guided", "A Tuple That Answers To Names", "GUIDED",
            """
            `row[0]` is a bug waiting to happen; `point.x` is not. A namedtuple is
            still a tuple — same size, same unpacking, same immutability — but the
            fields have names.

            `rows` is a list of [x, y] pairs. Return the largest x.
            """,
            "furthest_x", "rows", _furthest_x,
            """
            from collections import namedtuple

            Point = namedtuple("Point", "x y")


            def furthest_x(rows):
                points = [Point(*row) for row in rows]
                return max(point.x for point in points)
            """,
            [("two points", [[[1, 2], [5, 0]]]), ("descending", [[[9, 1], [2, 2]]])],
            [("negatives", [[[-4, 0], [-9, 1]]]),
             ("ties", [[[3, 1], [3, 9]]]),
             ("many", [[[1, 1], [2, 2], [3, 3]]])],
            edges=[("single point", [[[7, 7]]])],
            pattern="ARRAY", family="stdlib_namedtuple",
            starter="""
            from collections import namedtuple

            Point = namedtuple("Point", "x y")


            def furthest_x(rows):
                points = [Point(*row) for row in rows]
                # 1. Ask each point for its x by name, not by index.
                return max(__BLANK__ for point in points)
            """,
            same_move="Row = namedtuple('Row', 'name score'); row.score",
            nudge="`Point(*row)` unpacks the pair into the two fields. After that "
                  "`point.x` reads like the sentence you would say out loud.",
            pseudocode="Point = namedtuple('Point', 'x y')\nmax(point.x for point in points)",
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-namedtuple-rank", "The Leaderboard", "TUTORIAL",
            """
            `rows` is a list of [name, score]. Return the rows sorted by score
            descending, ties broken by name ascending, as a list of [name, score]
            lists.

            Build namedtuples first. `key=lambda p: (-p.score, p.name)` is a
            sentence; `key=lambda r: (-r[1], r[0])` is a puzzle.
            """,
            "rank_players", "rows", _rank_players,
            """
            from collections import namedtuple

            Player = namedtuple("Player", "name score")


            def rank_players(rows):
                players = [Player(*row) for row in rows]
                players.sort(key=lambda player: (-player.score, player.name))
                return [[player.name, player.score] for player in players]
            """,
            [("clear order", [[["ada", 10], ["bo", 30]]]),
             ("tie on score", [[["zed", 5], ["ada", 5]]])],
            [("already sorted", [[["a", 9], ["b", 1]]]),
             ("negative scores", [[["a", -1], ["b", -5]]]),
             ("three way", [[["c", 2], ["a", 2], ["b", 3]]])],
            edges=[("empty", [[]]), ("single", [[["solo", 1]]])],
            pattern="SORTING", family="stdlib_namedtuple",
            after="py-namedtuple-guided",
            nudge="Negating the score is how you sort one field descending and "
                  "another ascending in a single key.",
            pseudocode="players = [Player(*row) for row in rows]\nsort by (-score, name)",
            failures=["Sorting twice instead of using one tuple key"],
            time="O(n log n)", space="O(n)",
        ),

        # ===================================================================
        # collections.OrderedDict
        # ===================================================================
        _drill(
            "py-ordereddict-guided", "Move It To The End", "GUIDED",
            """
            A plain dict remembers insertion order, but it cannot cheaply CHANGE
            that order. `OrderedDict.move_to_end(key)` does, in O(1), which is the
            entire trick behind an LRU cache.

            `keys` seeds the cache in order. For each key in `touches` that is
            present, mark it as most recently used. Return the keys, least
            recently used first.
            """,
            "touch_order", "keys, touches", _touch_order,
            """
            from collections import OrderedDict


            def touch_order(keys, touches):
                cache = OrderedDict((key, True) for key in keys)
                for key in touches:
                    if key in cache:
                        cache.move_to_end(key)
                return list(cache)
            """,
            [("touch the first", [["a", "b", "c"], ["a"]]),
             ("touch nothing", [["a", "b"], []])],
            [("touch twice", [["a", "b", "c"], ["a", "a"]]),
             ("unknown key ignored", [["a", "b"], ["zz"]]),
             ("touch all in order", [["a", "b"], ["a", "b"]])],
            edges=[("empty cache", [[], ["a"]])],
            pattern="HASH_MAP", family="stdlib_ordereddict",
            starter="""
            from collections import OrderedDict


            def touch_order(keys, touches):
                cache = OrderedDict((key, True) for key in keys)
                for key in touches:
                    if key in cache:
                        # 1. Mark this key as the most recently used one.
                        __BLANK__
                return list(cache)
            """,
            long_way="""
            order = []
            for key in keys:
                if key not in order:
                    order.append(key)
            for key in touches:
                if key in order:
                    order.remove(key)     # O(n) scan, every single touch
                    order.append(key)
            return order
            """,
            same_move="cache.move_to_end(key, last=False)   # send it to the FRONT",
            nudge="`cache.move_to_end(key)` — no removal, no reinsertion, no scan.",
            pseudocode="cache = OrderedDict(...)\nfor key in touches: cache.move_to_end(key)",
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-ordereddict-evict", "The Oldest Goes First", "TUTORIAL",
            """
            Insert each key of `keys` into a cache that holds at most `capacity`
            entries, skipping keys already present. When the cache overflows,
            evict the OLDEST entry. Return the surviving keys, oldest first.

            `popitem(last=False)` pops from the front — FIFO. The default,
            `popitem()`, pops from the back — LIFO. Choosing wrong is silent.
            """,
            "fifo_evict", "keys, capacity", _fifo_evict,
            """
            from collections import OrderedDict


            def fifo_evict(keys, capacity):
                cache = OrderedDict()
                for key in keys:
                    if key in cache:
                        continue
                    cache[key] = True
                    if len(cache) > capacity:
                        cache.popitem(last=False)
                return list(cache)
            """,
            [("overflow by one", [["a", "b", "c"], 2]),
             ("fits exactly", [["a", "b"], 2])],
            [("repeat is ignored", [["a", "a", "b"], 2]),
             ("capacity one", [["a", "b", "c"], 1]),
             ("long run", [["a", "b", "c", "d"], 3])],
            edges=[("empty keys", [[], 2]), ("capacity zero", [["a"], 0])],
            pattern="HASH_MAP", family="stdlib_ordereddict",
            after="py-ordereddict-guided",
            nudge="`last=False` is the difference between a queue and a stack, and "
                  "it is one keyword.",
            pseudocode="for key: insert, then if len > capacity: popitem(last=False)",
            failures=["Calling `popitem()` with no argument and evicting the newest entry"],
            time="O(n)", space="O(capacity)",
        ),

        # ===================================================================
        # heapq — and the min-heap convention
        # ===================================================================
        _drill(
            "py-heapq-guided", "The Smallest Thing, Repeatedly", "GUIDED",
            """
            A heap is the structure for 'give me the extreme element, over and
            over' without paying for a full sort each time. `heapq` does not give
            you a heap CLASS — it gives you functions that treat a plain list as
            a heap. `heappush` puts a value in; `heappop` takes the smallest out.

            Push every value, then pop them all. The result is sorted ascending.
            """,
            "drain_sorted", "nums", _drain_sorted,
            """
            import heapq


            def drain_sorted(nums):
                heap = []
                for value in nums:
                    heapq.heappush(heap, value)
                out = []
                while heap:
                    out.append(heapq.heappop(heap))
                return out
            """,
            [("unsorted", [[3, 1, 2]]), ("already sorted", [[1, 2, 3]])],
            [("duplicates", [[2, 2, 1]]), ("negatives", [[-1, -5, 0]]),
             ("single", [[9]])],
            edges=[("empty", [[]])],
            pattern="HEAP", family="stdlib_heapq", realm="stack_queue_mines",
            starter="""
            import heapq


            def drain_sorted(nums):
                heap = []
                for value in nums:
                    # 1. Put this value into the heap, keeping the heap a heap.
                    __BLANK__
                out = []
                while heap:
                    out.append(heapq.heappop(heap))
                return out
            """,
            same_move="heapq.heapify(nums)   # turn a whole list into a heap in O(n)",
            nudge="`heapq.heappush(heap, value)` takes the list first and the value "
                  "second. It returns None — it mutates the list.",
            pseudocode="for value: heappush(heap, value)\nwhile heap: out.append(heappop(heap))",
            failures=["Expecting heappush to return the new heap; it returns None",
                      "Assuming the heap list is fully sorted — only heap[0] is guaranteed"],
            time="O(n log n)", space="O(n)",
        ),

        _drill(
            "py-heapq-nsmallest", "Three Of Them, Not All Of Them", "TUTORIAL",
            """
            Return the `k` smallest values of `nums`, ascending. If `k` is zero or
            negative, return an empty list.

            `heapq.nsmallest(k, nums)` is one line and, for small k, cheaper than
            sorting the whole list. Note the argument order: k comes FIRST.
            """,
            "k_smallest", "nums, k", _k_smallest,
            """
            import heapq


            def k_smallest(nums, k):
                if k <= 0:
                    return []
                return heapq.nsmallest(k, nums)
            """,
            [("three of five", [[5, 1, 4, 2, 3], 3]), ("one", [[9, 7], 1])],
            [("k exceeds length", [[2, 1], 9]), ("duplicates", [[1, 1, 2], 2]),
             ("negatives", [[-1, -9, 3], 2])],
            edges=[("k is zero", [[1, 2], 0]), ("empty list", [[], 3])],
            pattern="HEAP", family="stdlib_heapq", realm="stack_queue_mines",
            after="py-heapq-guided",
            nudge="`nsmallest(k, nums)` and `nlargest(k, nums)` both take k first. "
                  "Both accept `key=` like `sorted` does.",
            pseudocode="return heapq.nsmallest(k, nums)",
            failures=["Writing `nsmallest(nums, k)` with the arguments swapped"],
            time="O(n log k)", space="O(k)",
        ),

        _drill(
            "py-heapq-negate", "There Is No Max-Heap", "EASY",
            """
            Python ships a MIN-heap and nothing else. To get the largest elements
            out of a heap you negate on the way in and negate again on the way
            out. That trick appears in interview answers constantly and is worth
            having in your fingers.

            Return the three most expensive prices in `prices`, descending, using
            a heap. Fewer than three prices means return all of them.
            """,
            "top_three_costs", "prices", _top_three_costs,
            """
            import heapq


            def top_three_costs(prices):
                heap = []
                for price in prices:
                    # Negating inverts the ordering, so the smallest negative is
                    # the largest price.
                    heapq.heappush(heap, -price)
                out = []
                while heap and len(out) < 3:
                    out.append(-heapq.heappop(heap))
                return out
            """,
            [("five prices", [[10, 50, 20, 40, 30]]), ("exactly three", [[1, 3, 2]])],
            [("two prices", [[5, 8]]), ("ties", [[7, 7, 7, 1]]),
             ("negatives", [[-5, -1, -9, -2]])],
            edges=[("empty", [[]]), ("single", [[42]])],
            pattern="HEAP", family="stdlib_heapq", realm="stack_queue_mines",
            after="py-heapq-nsmallest",
            nudge="Negate on the way in, negate on the way out. Forget the second "
                  "negation and every answer comes back upside down.",
            pseudocode="push -price for each price\npop three, negate each one back",
            failures=["Negating on push and forgetting to negate on pop",
                      "Assuming heapq has a max-heap variant — it does not"],
            time="O(n log n)", space="O(n)",
        ),

        _drill(
            "py-heapq-merge", "K Sorted Streams", "MEDIUM",
            """
            `lists` is a list of already-sorted lists. Return one sorted list
            containing every value.

            Concatenating and re-sorting is O(total log total) and throws away the
            fact that the inputs were already sorted. `heapq.merge` walks them
            together with a heap of k heads, lazily, in O(total log k) — and it
            never holds more than one element per list in memory, which is what
            makes it the right answer for streams that do not fit in RAM.
            """,
            "merge_sorted", "lists", _merge_sorted,
            """
            import heapq


            def merge_sorted(lists):
                # merge returns a lazy iterator; the list() is what materialises it.
                return list(heapq.merge(*lists))
            """,
            [("three streams", [[[1, 4], [2, 5], [3, 6]]]),
             ("two streams", [[[1, 2], [3, 4]]])],
            [("uneven lengths", [[[1], [2, 3, 4]]]),
             ("duplicates across streams", [[[1, 2], [1, 2]]]),
             ("one stream", [[[5, 6, 7]]])],
            edges=[("no streams", [[]]), ("empty stream present", [[[], [1, 2]]])],
            pattern="HEAP", family="stdlib_heapq", realm="stack_queue_mines",
            after="py-heapq-negate",
            long_way="""
            pooled = []
            for row in lists:
                pooled.extend(row)
            pooled.sort()
            return pooled
            """,
            nudge="`heapq.merge(*lists)` — the star matters, it takes the streams "
                  "as separate arguments, not as one list of lists.",
            pseudocode="return list(heapq.merge(*lists))",
            failures=["Forgetting the `*` and merging a single list of lists",
                      "Returning the iterator instead of a list"],
            time="O(n log k)", space="O(k)",
        ),

        _drill(
            "py-heapq-stream-topk", "Top K Of A Stream You Cannot Store", "HARD",
            """
            Return the `k` largest values of `values`, descending, while holding
            no more than k values in memory at a time. `k` zero or negative
            returns an empty list.

            The move: keep a MIN-heap of size k. Its root is the weakest thing
            currently in the top k, so every new value is compared against exactly
            one element. `heappushpop` pushes and pops in a single sift instead of
            two, which is the detail an interviewer listens for.
            """,
            "stream_top_k", "values, k", _stream_top_k,
            """
            import heapq


            def stream_top_k(values, k):
                if k <= 0:
                    return []
                heap = []
                for value in values:
                    if len(heap) < k:
                        heapq.heappush(heap, value)
                    else:
                        # Push and pop in one sift. The smallest of the k+1
                        # candidates leaves, which is exactly the one that loses.
                        heapq.heappushpop(heap, value)
                return sorted(heap, reverse=True)
            """,
            [("top three", [[5, 1, 9, 3, 7], 3]), ("top one", [[4, 8, 2], 1])],
            [("k exceeds length", [[2, 1], 5]),
             ("duplicates", [[3, 3, 3, 1], 2]),
             ("descending input", [[9, 8, 7, 6], 2]),
             ("negatives", [[-3, -1, -7], 2])],
            edges=[("k is zero", [[1, 2], 0]), ("empty stream", [[], 3])],
            pattern="HEAP", family="stdlib_heapq", realm="stack_queue_mines",
            after="py-heapq-merge",
            nudge="Min-heap for the top k. It feels backwards until you say why: "
                  "the root is the first one you would throw away.",
            pseudocode="keep heap of size k\nif full: heappushpop(heap, value)\nreturn sorted(heap, reverse=True)",
            failures=["Using a max-heap of everything, which is O(n) memory",
                      "heappush then heappop as two calls — correct, but two sifts"],
            time="O(n log k)", space="O(k)",
        ),

        # ===================================================================
        # itertools.product
        # ===================================================================
        _drill(
            "py-product-guided", "Every Combination Of Two Bags", "GUIDED",
            """
            Two nested `for` loops that produce every pairing of two sequences is
            `itertools.product`. It yields tuples in the same order your nested
            loops would, with the LAST argument varying fastest.

            Return every [x, y] pair with x from `a` and y from `b`, in that order.
            """,
            "all_pairs", "a, b", _all_pairs,
            """
            from itertools import product


            def all_pairs(a, b):
                return [[x, y] for x, y in product(a, b)]
            """,
            [("two by two", [[1, 2], ["x", "y"]]), ("one by three", [[0], [1, 2, 3]])],
            [("three by one", [[1, 2, 3], ["a"]]),
             ("duplicates kept", [[1, 1], ["a"]]),
             ("strings both sides", [["a", "b"], ["c"]])],
            edges=[("empty first", [[], [1]]), ("empty second", [[1], []])],
            pattern="ARRAY", family="stdlib_product",
            starter="""
            from itertools import product


            def all_pairs(a, b):
                # 1. Every x from a paired with every y from b.
                return [[x, y] for x, y in __BLANK__]
            """,
            same_move="product(rows, cols)   # every cell coordinate of a grid",
            nudge="`product(a, b)` is the two nested loops, with the second one "
                  "innermost.",
            pseudocode="[[x, y] for x, y in product(a, b)]",
            failures=["Expecting lists back — product yields tuples"],
            time="O(n*m)", space="O(n*m)",
        ),

        _drill(
            "py-product-repeat", "Every Code Of Length N", "TUTORIAL",
            """
            Return every string of length `length` built from `digits`, in
            itertools order. `length` of zero yields exactly one code: the empty
            string.

            `product(digits, repeat=length)` is the loop-of-unknown-depth that you
            cannot write with nested `for` statements, because you do not know how
            many to nest.
            """,
            "pin_codes", "digits, length", _pin_codes,
            """
            from itertools import product


            def pin_codes(digits, length):
                return ["".join(code) for code in product(digits, repeat=length)]
            """,
            [("two digits, length two", [["0", "1"], 2]),
             ("three digits, length one", [["a", "b", "c"], 1])],
            [("length three", [["0", "1"], 3]),
             ("single digit", [["7"], 3]),
             ("length zero", [["0", "1"], 0])],
            edges=[("no digits", [[], 2])],
            pattern="ARRAY", family="stdlib_product",
            after="py-product-guided",
            long_way="""
            codes = [""]
            for _ in range(length):
                grown = []
                for code in codes:
                    for digit in digits:
                        grown.append(code + digit)
                codes = grown
            return codes
            """,
            nudge="`repeat=` is the keyword that turns product into a cartesian "
                  "power. There is no positional form of it.",
            pseudocode="product(digits, repeat=length), join each tuple",
            failures=["Passing repeat positionally — product reads it as another pool"],
            time="O(d^L)", space="O(d^L)",
        ),

        _drill(
            "py-product-dice", "Counting The Outcomes", "EASY",
            """
            Roll `dice` dice, each with faces numbered 1 to `faces`. Return how
            many of the possible outcomes sum to `target`.

            The brute-force enumeration is one line with `product`. Say the
            complexity out loud when you write it — faces to the power of dice —
            and say when you would replace it with counting DP instead.
            """,
            "winning_rolls", "faces, dice, target", _winning_rolls,
            """
            from itertools import product


            def winning_rolls(faces, dice, target):
                sides = range(1, faces + 1)
                return sum(1 for roll in product(sides, repeat=dice)
                           if sum(roll) == target)
            """,
            [("two d6 make seven", [6, 2, 7]), ("two d6 make two", [6, 2, 2])],
            [("three d4 make six", [4, 3, 6]),
             ("impossible total", [6, 2, 13]),
             ("one die", [6, 1, 3])],
            edges=[("zero dice, zero target", [6, 0, 0]),
                   ("zero dice, nonzero target", [6, 0, 5])],
            pattern="ARRAY", family="stdlib_product",
            after="py-product-repeat",
            nudge="Enumerate first, optimise second — but know out loud that this "
                  "is faces**dice work.",
            pseudocode="sum(1 for roll in product(range(1, faces+1), repeat=dice) if sum(roll) == target)",
            failures=["Using range(faces), which numbers the die 0..faces-1"],
            time="O(f^d)", space="O(d)",
        ),

        # ===================================================================
        # itertools.combinations
        # ===================================================================
        _drill(
            "py-combinations-guided", "Every Pair, Once", "GUIDED",
            """
            `combinations(items, 2)` yields every pair of distinct positions,
            each pair once, in input order — exactly what the `for i` / `for j in
            range(i+1, n)` double loop produces, without the off-by-one risk.

            Return every [first, second] pair from `items`.
            """,
            "pairs", "items", _pairs,
            """
            from itertools import combinations


            def pairs(items):
                return [list(pair) for pair in combinations(items, 2)]
            """,
            [("three items", [["a", "b", "c"]]), ("two items", [[1, 2]])],
            [("four items", [[1, 2, 3, 4]]),
             ("duplicates are positions, not values", [["a", "a"]]),
             ("numbers", [[5, 6, 7]])],
            edges=[("one item", [[1]]), ("empty", [[]])],
            pattern="ARRAY", family="stdlib_combinations",
            starter="""
            from itertools import combinations


            def pairs(items):
                # 1. Every pair of distinct positions, each pair exactly once.
                return [list(pair) for pair in __BLANK__]
            """,
            same_move="combinations(items, 3)   # triples instead of pairs",
            nudge="combinations picks by POSITION, so a repeated value still "
                  "produces a pair with itself from two different slots.",
            pseudocode="[list(pair) for pair in combinations(items, 2)]",
            failures=["Reaching for permutations and getting each pair twice"],
            time="O(n^2)", space="O(n^2)",
        ),

        _drill(
            "py-combinations-sums", "All The Pair Sums", "TUTORIAL",
            """
            Return the sums of every distinct pair of `nums`, sorted ascending.
            Each pair of positions counts once.
            """,
            "pair_sums", "nums", _pair_sums,
            """
            from itertools import combinations


            def pair_sums(nums):
                return sorted(a + b for a, b in combinations(nums, 2))
            """,
            [("three numbers", [[1, 2, 3]]), ("two numbers", [[5, 5]])],
            [("negatives", [[-1, 4, 2]]), ("zeros", [[0, 0, 1]]),
             ("four numbers", [[1, 2, 3, 4]])],
            edges=[("one number", [[9]]), ("empty", [[]])],
            pattern="ARRAY", family="stdlib_combinations",
            after="py-combinations-guided",
            nudge="Unpack the pair in the comprehension — `for a, b in "
                  "combinations(nums, 2)` — and the sum writes itself.",
            pseudocode="sorted(a + b for a, b in combinations(nums, 2))",
            time="O(n^2 log n)", space="O(n^2)",
        ),

        _drill(
            "py-combinations-trio", "The Best Three", "EASY",
            """
            Return the largest sum obtainable from any three values in `scores`.
            `scores` always has at least three values.

            Both answers are fine and you should be able to say the difference:
            `max(sum(c) for c in combinations(scores, 3))` is the obvious one and
            is O(n^3); sorting and taking the top three is O(n log n). Write the
            readable one, then name the cheaper one.
            """,
            "best_trio", "scores", _best_trio,
            """
            from itertools import combinations


            def best_trio(scores):
                return max(sum(trio) for trio in combinations(scores, 3))
            """,
            [("five scores", [[1, 9, 3, 7, 5]]), ("exactly three", [[2, 2, 2]])],
            [("negatives present", [[-5, 1, 2, 3]]),
             ("all negative", [[-1, -2, -3, -4]]),
             ("descending", [[9, 8, 7, 6]])],
            edges=[("three identical", [[4, 4, 4]])],
            pattern="ARRAY", family="stdlib_combinations",
            after="py-combinations-sums",
            constraints=["len(scores) >= 3"],
            nudge="`combinations(scores, 3)` enumerates the candidates; `max` of "
                  "their sums is the answer.",
            pseudocode="max(sum(trio) for trio in combinations(scores, 3))",
            failures=["Assuming the top three are the three largest when negatives "
                      "are involved — here they are, but say why"],
            time="O(n^3)", space="O(1)",
        ),

        # ===================================================================
        # itertools.permutations
        # ===================================================================
        _drill(
            "py-permutations-guided", "Every Order", "GUIDED",
            """
            `permutations(items)` yields every ordering of the items. There are
            n! of them, so this is a tool for small n and you should say that out
            loud when you reach for it.

            Return every arrangement of `items` as a list of lists, sorted so the
            result is deterministic.
            """,
            "arrangements", "items", _arrangements,
            """
            from itertools import permutations


            def arrangements(items):
                return sorted([list(order) for order in permutations(items)])
            """,
            [("three items", [[1, 2, 3]]), ("two items", [["a", "b"]])],
            [("one item", [[7]]), ("four items", [[1, 2, 3, 4]]),
             ("letters", [["x", "y", "z"]])],
            edges=[("empty", [[]])],
            pattern="RECURSION", family="stdlib_permutations",
            realm="recursive_forest",
            starter="""
            from itertools import permutations


            def arrangements(items):
                # 1. Every ordering of the items.
                return sorted([list(order) for order in __BLANK__])
            """,
            same_move="permutations(items, 2)   # every ordered pair instead",
            nudge="`permutations` cares about order, `combinations` does not. That "
                  "one sentence chooses between them every time.",
            pseudocode="sorted([list(order) for order in permutations(items)])",
            failures=["Reaching for permutations when the question does not care "
                      "about order, and doing k! times too much work"],
            time="O(n! * n)", space="O(n! * n)",
        ),

        _drill(
            "py-permutations-words", "Every Word Those Letters Make", "TUTORIAL",
            """
            Return every distinct string that can be made by rearranging all the
            characters of `text`, sorted.

            Repeated letters produce repeated permutations, so the set is doing
            real work here — it is not decoration.
            """,
            "unique_arrangements", "text", _unique_arrangements,
            """
            from itertools import permutations


            def unique_arrangements(text):
                return sorted({"".join(order) for order in permutations(text)})
            """,
            [("three distinct", ["abc"]), ("repeated letter", ["aab"])],
            [("all identical", ["aaa"]), ("two letters", ["ba"]),
             ("single letter", ["z"])],
            edges=[("empty", [""])],
            pattern="RECURSION", family="stdlib_permutations",
            realm="recursive_forest",
            after="py-permutations-guided",
            nudge="A set comprehension around the join collapses the duplicates "
                  "that repeated letters create.",
            pseudocode='sorted({"".join(p) for p in permutations(text)})',
            failures=["Returning duplicates when the input has a repeated letter"],
            time="O(n! * n)", space="O(n! * n)",
        ),

        # ===================================================================
        # itertools.groupby
        # ===================================================================
        _drill(
            "py-groupby-guided", "Runs Of The Same Thing", "GUIDED",
            """
            `groupby(items)` walks the sequence and yields (value, group) for each
            run of CONSECUTIVE equal items. It does not sort for you: unsorted
            input gives you one group per run, which is either exactly what you
            wanted or a bug, depending on which you meant.

            Return [value, run_length] for each run in `items`.
            """,
            "run_lengths", "items", _run_lengths,
            """
            from itertools import groupby


            def run_lengths(items):
                return [[value, len(list(run))] for value, run in groupby(items)]
            """,
            [("three runs", [["a", "a", "b", "c", "c", "c"]]),
             ("no repeats", [[1, 2, 3]])],
            [("one long run", [["x", "x", "x"]]),
             ("alternating", [[1, 2, 1, 2]]),
             ("single", [[5]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="stdlib_groupby",
            starter="""
            from itertools import groupby


            def run_lengths(items):
                # 1. Group the CONSECUTIVE equal items together.
                return [[value, len(list(run))] for value, run in __BLANK__]
            """,
            same_move="groupby(sorted(words, key=len), key=len)   # group by a key",
            nudge="The group is a lazy iterator that dies as soon as you advance "
                  "to the next group, which is why `len(list(run))` happens now.",
            pseudocode="[[value, len(list(run))] for value, run in groupby(items)]",
            failures=["Keeping the group object and reading it after the loop moved on",
                      "Forgetting groupby only groups ADJACENT equal items"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-groupby-encode", "Run Length Encoding", "TUTORIAL",
            """
            Compress `text` by replacing each run of a repeated character with the
            character followed by the run length: "aaabb" becomes "a3b2". A single
            character still gets its count: "abc" becomes "a1b1c1".
            """,
            "encode_runs", "text", _encode_runs,
            """
            from itertools import groupby


            def encode_runs(text):
                return "".join(ch + str(len(list(run)))
                               for ch, run in groupby(text))
            """,
            [("classic", ["aaabb"]), ("no repeats", ["abc"])],
            [("single char", ["z"]), ("long run", ["wwwwww"]),
             ("returns to an earlier char", ["aabaa"])],
            edges=[("empty", [""])],
            pattern="STRING", family="stdlib_groupby",
            after="py-groupby-guided",
            nudge="groupby accepts a string directly — a string is already an "
                  "iterable of characters.",
            pseudocode='"".join(ch + str(len(list(run))) for ch, run in groupby(text))',
            failures=["Emitting nothing for runs of length one"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-groupby-longest", "The Longest Stretch", "EASY",
            """
            Return [value, length] for the longest run of consecutive equal items
            in `items`. If several runs tie, return the first of them. Return an
            empty list for empty input.

            This is the shape behind 'longest streak', 'longest plateau' and
            'peak sustained load', and it is one `max` over one `groupby`.
            """,
            "longest_run", "items", _longest_run,
            """
            from itertools import groupby


            def longest_run(items):
                runs = [[value, len(list(run))] for value, run in groupby(items)]
                if not runs:
                    return []
                # max returns the FIRST maximum it meets, which is the tie rule
                # we were given. Say that out loud rather than hoping.
                return max(runs, key=lambda entry: entry[1])
            """,
            [("clear winner", [["a", "b", "b", "b", "c"]]),
             ("tie goes to the first", [[1, 1, 2, 2]])],
            [("all identical", [["x", "x", "x"]]),
             ("no repeats", [[1, 2, 3]]),
             ("winner at the end", [["a", "b", "b"]])],
            edges=[("empty", [[]]), ("single", [[9]])],
            pattern="ARRAY", family="stdlib_groupby",
            after="py-groupby-encode",
            nudge="Build the runs first, then take the max. Two simple passes beat "
                  "one clever one.",
            pseudocode="runs = groupby into [value, length]\nreturn max(runs, key=length)",
            failures=["Using max on the pairs directly and tie-breaking on the value"],
            time="O(n)", space="O(n)",
        ),

        # ===================================================================
        # itertools.accumulate
        # ===================================================================
        _drill(
            "py-accumulate-guided", "The Running Total", "GUIDED",
            """
            `accumulate(nums)` yields the running total: each element is the sum of
            everything up to and including that position. It is the prefix-sum
            array, already written.

            Return the running totals of `nums` as a list.
            """,
            "running_totals", "nums", _running_totals,
            """
            from itertools import accumulate


            def running_totals(nums):
                return list(accumulate(nums))
            """,
            [("counting up", [[1, 2, 3]]), ("with a zero", [[5, 0, 5]])],
            [("negatives", [[-1, -2, 3]]), ("single", [[7]]),
             ("alternating", [[1, -1, 1, -1]])],
            edges=[("empty", [[]])],
            pattern="PREFIX_SUM", family="stdlib_accumulate",
            starter="""
            from itertools import accumulate


            def running_totals(nums):
                # 1. The running total of nums, as a list.
                return __BLANK__
            """,
            same_move="list(accumulate(nums, initial=0))   # start with a leading 0",
            nudge="accumulate returns an iterator, so the `list(...)` is load "
                  "bearing, not decoration.",
            pseudocode="list(accumulate(nums))",
            failures=["Returning the iterator itself, which compares equal to nothing"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-accumulate-max", "The Running Best", "TUTORIAL",
            """
            Return the running maximum of `nums`: at each position, the largest
            value seen so far.

            `accumulate` takes a second argument — any two-argument function. Pass
            `max` and the running total becomes a running maximum. That generality
            is the reason to know the function at all.
            """,
            "running_max", "nums", _running_max,
            """
            from itertools import accumulate


            def running_max(nums):
                return list(accumulate(nums, max))
            """,
            [("rising", [[1, 3, 2, 5]]), ("falling", [[5, 4, 3]])],
            [("all equal", [[2, 2, 2]]), ("negatives", [[-5, -9, -1]]),
             ("single", [[8]])],
            edges=[("empty", [[]])],
            pattern="PREFIX_SUM", family="stdlib_accumulate",
            after="py-accumulate-guided",
            nudge="`accumulate(nums, max)` — pass the function, do not call it.",
            pseudocode="list(accumulate(nums, max))",
            failures=["Writing `accumulate(nums, max())`, which calls max with no arguments"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-accumulate-balance", "The Lowest The Balance Ever Got", "EASY",
            """
            `deltas` is a list of deposits and withdrawals applied in order,
            starting from a balance of zero. Return the lowest balance the account
            ever held after a transaction, or 0 if there were no transactions.

            One `min` over one `accumulate`. The `default=` keyword handles the
            empty case without a branch.
            """,
            "lowest_balance", "deltas", _lowest_balance,
            """
            from itertools import accumulate


            def lowest_balance(deltas):
                return min(accumulate(deltas), default=0)
            """,
            [("dips then recovers", [[10, -30, 40]]), ("only deposits", [[5, 5]])],
            [("ends lowest", [[1, -2, -3]]),
             ("starts lowest", [[-9, 20]]),
             ("single withdrawal", [[-4]])],
            edges=[("no transactions", [[]]), ("nets to zero", [[5, -5]])],
            pattern="PREFIX_SUM", family="stdlib_accumulate",
            after="py-accumulate-max",
            long_way="""
            balance, lowest = 0, None
            for delta in deltas:
                balance += delta
                if lowest is None or balance < lowest:
                    lowest = balance
            return 0 if lowest is None else lowest
            """,
            nudge="`min(..., default=0)` is the empty-sequence guard, built in.",
            pseudocode="min(accumulate(deltas), default=0)",
            failures=["Calling min on an empty iterator and raising ValueError",
                      "Including the starting balance of 0 as a candidate"],
            time="O(n)", space="O(n)",
        ),

        # ===================================================================
        # itertools.chain
        # ===================================================================
        _drill(
            "py-chain-guided", "One Sequence Out Of Many", "GUIDED",
            """
            `chain.from_iterable(nested)` walks a sequence of sequences as if they
            were one, without building the concatenation. It is the flatten you
            keep rewriting.

            Flatten `nested` — a list of lists — into one list, in order.
            """,
            "flatten", "nested", _flatten,
            """
            from itertools import chain


            def flatten(nested):
                return list(chain.from_iterable(nested))
            """,
            [("three rows", [[[1, 2], [3], [4, 5]]]),
             ("strings", [[["a"], ["b", "c"]]])],
            [("empty row in the middle", [[[1], [], [2]]]),
             ("one row", [[[1, 2, 3]]]),
             ("all empty", [[[], []]])],
            edges=[("no rows", [[]])],
            pattern="ARRAY", family="stdlib_chain",
            starter="""
            from itertools import chain


            def flatten(nested):
                # 1. Walk every row as if they were one sequence.
                return list(__BLANK__)
            """,
            same_move="chain(a, b, c)   # same idea, but the pieces named separately",
            nudge="`chain(*nested)` also works, but it unpacks every row as an "
                  "argument first. `from_iterable` stays lazy.",
            pseudocode="list(chain.from_iterable(nested))",
            failures=["Calling `chain(nested)`, which yields the rows, not their contents"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-chain-merge-feeds", "Three Feeds, First Sighting Wins", "TUTORIAL",
            """
            Return the values of `a`, `b` and `c` in that order, with later
            duplicates removed — each value appears once, at its first position.

            `chain(a, b, c)` walks the three without concatenating them, and
            `dict.fromkeys` is the shortest order-preserving dedupe in Python.
            """,
            "merge_feeds", "a, b, c", _merge_feeds,
            """
            from itertools import chain


            def merge_feeds(a, b, c):
                # dict keys are unique and, since 3.7, ordered by insertion.
                return list(dict.fromkeys(chain(a, b, c)))
            """,
            [("overlapping feeds", [[1, 2], [2, 3], [3, 4]]),
             ("disjoint feeds", [["a"], ["b"], ["c"]])],
            [("all identical", [[1], [1], [1]]),
             ("duplicates inside one feed", [[1, 1, 2], [], []]),
             ("two empty", [[], [5], []])],
            edges=[("all empty", [[], [], []])],
            pattern="SET", family="stdlib_chain",
            after="py-chain-guided",
            nudge="A set would dedupe but lose the order. `dict.fromkeys` keeps both.",
            pseudocode="list(dict.fromkeys(chain(a, b, c)))",
            failures=["Using a set and returning the values in arbitrary order"],
            time="O(n)", space="O(n)",
        ),

        # ===================================================================
        # functools.lru_cache
        # ===================================================================
        _drill(
            "py-lru-cache-guided", "Paying For A Result Once", "GUIDED",
            """
            `@lru_cache` remembers what a function returned for a given set of
            arguments. Put it on a recursive function whose subproblems overlap
            and an exponential algorithm becomes a linear one, with one line of
            code and no table to index by hand.

            Return the nth Fibonacci number, with fib(0) = 0 and fib(1) = 1.
            """,
            "fib", "n", _fib,
            """
            from functools import lru_cache


            def fib(n):
                @lru_cache(maxsize=None)
                def go(k):
                    if k < 2:
                        return k
                    return go(k - 1) + go(k - 2)

                return go(n)
            """,
            [("tenth", [10]), ("first", [1])],
            [("zeroth", [0]), ("thirtieth", [30]), ("fortieth", [40])],
            edges=[("second", [2])],
            pattern="RECURSION", family="stdlib_lru_cache", realm="dp_ruins",
            starter="""
            from functools import lru_cache


            def fib(n):
                # 1. Remember every result this function has already computed.
                __BLANK__
                def go(k):
                    if k < 2:
                        return k
                    return go(k - 1) + go(k - 2)

                return go(n)
            """,
            same_move="@lru_cache(maxsize=None)   # or @cache on Python 3.9+",
            nudge="The decorator goes on the RECURSIVE inner function. Caching the "
                  "outer one that is called once buys you nothing.",
            pseudocode="@lru_cache(maxsize=None)\ndef go(k): base case, else go(k-1) + go(k-2)",
            failures=["Decorating the outer function instead of the recursive one",
                      "Caching a function whose arguments are lists — they are unhashable"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-lru-cache-climb", "Counting The Ways Up", "TUTORIAL",
            """
            A staircase has `n` steps. You climb one or two at a time. Return how
            many distinct ways there are to reach the top. n = 0 has exactly one
            way: stand still.

            Write the honest recursion — ways(n) = ways(n-1) + ways(n-2) — and let
            the cache turn it from exponential into linear.
            """,
            "climb_ways", "n", _climb,
            """
            from functools import lru_cache


            def climb_ways(n):
                @lru_cache(maxsize=None)
                def ways(step):
                    if step < 0:
                        return 0
                    if step == 0:
                        return 1
                    return ways(step - 1) + ways(step - 2)

                return ways(n)
            """,
            [("four steps", [4]), ("one step", [1])],
            [("zero steps", [0]), ("ten steps", [10]), ("twenty steps", [20])],
            edges=[("two steps", [2])],
            pattern="RECURSION", family="stdlib_lru_cache", realm="dp_ruins",
            after="py-lru-cache-guided",
            nudge="Two base cases: below zero is an impossible path, exactly zero "
                  "is one completed path.",
            pseudocode="ways(step) = ways(step-1) + ways(step-2), cached",
            failures=["Returning 0 for n = 0 and being off by one everywhere"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-lru-cache-grid", "Paths Across The Grid", "EASY",
            """
            Return how many distinct paths cross a `rows` by `cols` grid from the
            top-left to the bottom-right, moving only right or down. A grid with
            no rows or no columns has zero paths.

            The recursion is two lines. Without the cache it revisits the same
            cell an exponential number of times; with it, each cell is computed
            once.
            """,
            "grid_paths", "rows, cols", _grid_paths,
            """
            from functools import lru_cache


            def grid_paths(rows, cols):
                if rows <= 0 or cols <= 0:
                    return 0

                @lru_cache(maxsize=None)
                def routes(r, c):
                    if r == 0 or c == 0:
                        return 1
                    return routes(r - 1, c) + routes(r, c - 1)

                return routes(rows - 1, cols - 1)
            """,
            [("three by three", [3, 3]), ("two by two", [2, 2])],
            [("one row", [1, 5]), ("one column", [6, 1]), ("four by five", [4, 5])],
            edges=[("zero rows", [0, 3]), ("one by one", [1, 1])],
            pattern="RECURSION", family="stdlib_lru_cache", realm="dp_ruins",
            after="py-lru-cache-climb",
            nudge="The cache key is the pair (r, c), so the memo table you would "
                  "have written by hand is created for you.",
            pseudocode="routes(r, c) = routes(r-1, c) + routes(r, c-1), edges are 1",
            failures=["Recursing on rows/cols instead of on indexes and counting one row too many"],
            time="O(r*c)", space="O(r*c)",
        ),

        _drill(
            "py-lru-cache-coins", "Fewest Coins", "MEDIUM",
            """
            Return the fewest coins from `coins` that sum exactly to `amount`, or
            -1 if no combination does. Coins may be reused. An amount of zero
            needs no coins.

            The recursion is obvious; the cache is what makes it tractable. Note
            the detail that trips people: `coins` is a list, and a list cannot be
            a cache key, so the recursive function must close over a tuple and
            take only the remaining amount.
            """,
            "min_coins", "coins, amount", _min_coins,
            """
            from functools import lru_cache


            def min_coins(coins, amount):
                usable = tuple(coin for coin in coins if coin > 0)

                @lru_cache(maxsize=None)
                def fewest(remaining):
                    if remaining == 0:
                        return 0
                    best = float("inf")
                    for coin in usable:
                        if coin <= remaining:
                            best = min(best, fewest(remaining - coin) + 1)
                    return best

                answer = fewest(amount)
                return -1 if answer == float("inf") else answer
            """,
            [("classic change", [[1, 5, 10], 12]), ("exact single coin", [[2, 5], 5])],
            [("impossible", [[5, 10], 3]),
             ("greedy would fail", [[1, 3, 4], 6]),
             ("one coin type", [[3], 9]),
             ("large amount", [[1, 7, 10], 63])],
            edges=[("amount zero", [[1, 2], 0]), ("no coins", [[], 5])],
            pattern="RECURSION", family="stdlib_lru_cache", realm="dp_ruins",
            after="py-lru-cache-grid",
            constraints=["0 <= amount <= 200", "coins are positive"],
            nudge="Close over `tuple(coins)` and cache on the remaining amount "
                  "alone. That keeps the cache key hashable and tiny.",
            pseudocode="fewest(rem) = min(fewest(rem - coin) + 1 for usable coin)\nbase: fewest(0) = 0",
            failures=["Passing the coin list into the cached function — TypeError: unhashable",
                      "Being greedy: [1,3,4] for 6 is 3+3, not 4+1+1"],
            time="O(amount * len(coins))", space="O(amount)",
        ),

        # ===================================================================
        # functools.reduce
        # ===================================================================
        _drill(
            "py-reduce-guided", "Folding A List Into One Value", "GUIDED",
            """
            `reduce(function, iterable, initial)` folds a sequence down to a single
            value by applying a two-argument function repeatedly. `sum` is reduce
            with addition; `math.prod` is reduce with multiplication; reduce is
            what you reach for when the operator has no built-in of its own.

            Return the product of `nums`. An empty list has product 1.
            """,
            "product_of", "nums", _product_of,
            """
            from functools import reduce
            from operator import mul


            def product_of(nums):
                return reduce(mul, nums, 1)
            """,
            [("three numbers", [[2, 3, 4]]), ("with a one", [[1, 5]])],
            [("contains zero", [[3, 0, 9]]), ("negatives", [[-2, 3]]),
             ("single", [[7]])],
            edges=[("empty", [[]])],
            pattern="ARRAY", family="stdlib_reduce",
            starter="""
            from functools import reduce
            from operator import mul


            def product_of(nums):
                # 1. Fold nums down with multiplication, starting from 1.
                return __BLANK__
            """,
            same_move="reduce(operator.or_, sets, set())   # union of many sets",
            nudge="The third argument is the starting value, and it is also the "
                  "answer for an empty sequence.",
            pseudocode="reduce(mul, nums, 1)",
            failures=["Omitting the initial value and raising TypeError on an empty list"],
            time="O(n)", space="O(1)",
        ),

        _drill(
            "py-reduce-merge", "Every Dict, Left To Right", "TUTORIAL",
            """
            `dicts` is a list of dicts. Return one dict containing every key, where
            a later dict wins any key it shares with an earlier one.
            """,
            "merge_all", "dicts", _merge_all,
            """
            from functools import reduce


            def merge_all(dicts):
                return reduce(lambda acc, item: {**acc, **item}, dicts, {})
            """,
            [("two dicts", [[{"a": 1}, {"b": 2}]]),
             ("later wins", [[{"a": 1}, {"a": 9}]])],
            [("three dicts", [[{"a": 1}, {"b": 2}, {"c": 3}]]),
             ("one dict", [[{"k": "v"}]]),
             ("overlapping keys", [[{"a": 1, "b": 1}, {"b": 2}]])],
            edges=[("no dicts", [[]]), ("empty dict present", [[{}, {"a": 1}]])],
            pattern="HASH_MAP", family="stdlib_reduce",
            after="py-reduce-guided",
            nudge="`{**a, **b}` merges two dicts with b winning. reduce turns that "
                  "two-argument move into an n-argument one.",
            pseudocode="reduce(lambda acc, item: {**acc, **item}, dicts, {})",
            failures=["Letting the EARLIER dict win by merging in the wrong order"],
            time="O(n*k)", space="O(k)",
        ),

        _drill(
            "py-reduce-intersect", "Present In Every List", "EASY",
            """
            Return the values present in every one of `lists`, sorted ascending.
            No lists at all means an empty result.

            Two sets intersect with `&`. n sets intersect with reduce and the same
            operator — which is the general shape of 'I know how to do this for
            two, and there are n'.
            """,
            "intersect_all", "lists", _intersect_all,
            """
            from functools import reduce


            def intersect_all(lists):
                if not lists:
                    # reduce with no initial value refuses an empty sequence.
                    return []
                return sorted(reduce(set.intersection, map(set, lists)))
            """,
            [("common value", [[[1, 2, 3], [2, 3, 4], [3, 2]]]),
             ("nothing in common", [[[1], [2]]])],
            [("one list", [[[3, 1, 2]]]),
             ("duplicates inside a list", [[[1, 1, 2], [2, 2]]]),
             ("all identical", [[[5], [5], [5]]])],
            edges=[("no lists", [[]]), ("empty list present", [[[1, 2], []]])],
            pattern="SET", family="stdlib_reduce",
            after="py-reduce-merge",
            nudge="`map(set, lists)` first, then reduce over `set.intersection`. "
                  "Passing the unbound method is the trick worth remembering.",
            pseudocode="sorted(reduce(set.intersection, map(set, lists)))",
            failures=["Calling reduce on an empty sequence with no initial value"],
            time="O(total)", space="O(n)",
        ),

        # ===================================================================
        # functools.partial
        # ===================================================================
        _drill(
            "py-partial-guided", "A Function With Its First Answer Filled In", "GUIDED",
            """
            `partial(func, x)` returns a new function that behaves like `func` with
            its first argument already supplied. It is how you hand a
            one-argument callback to something that only accepts one argument,
            without writing a lambda that closes over a loop variable and bites
            you later.

            Return every value of `values` multiplied by `factor`.
            """,
            "scaled", "values, factor", _scaled,
            """
            from functools import partial


            def scaled(values, factor):
                def multiply(a, b):
                    return a * b

                times = partial(multiply, factor)
                return [times(value) for value in values]
            """,
            [("double", [[1, 2, 3], 2]), ("by zero", [[4, 5], 0])],
            [("negative factor", [[1, 2], -3]), ("by one", [[9], 1]),
             ("negatives inside", [[-2, 4], 3])],
            edges=[("empty values", [[], 5])],
            pattern="ARRAY", family="stdlib_partial",
            starter="""
            from functools import partial


            def scaled(values, factor):
                def multiply(a, b):
                    return a * b

                # 1. multiply, with its FIRST argument already set to factor.
                times = __BLANK__
                return [times(value) for value in values]
            """,
            same_move="partial(int, base=2)   # a parser that always reads binary",
            nudge="`partial` fills arguments from the LEFT. Keyword arguments can "
                  "be filled in any position.",
            pseudocode="times = partial(multiply, factor)\n[times(v) for v in values]",
            failures=["Calling the function instead of partially applying it: "
                      "`partial(multiply(factor))`"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-partial-clamp", "Bounds, Applied Everywhere", "TUTORIAL",
            """
            Return every value of `values` clamped into the range [lo, hi] —
            anything below lo becomes lo, anything above hi becomes hi.

            Build the bounded function once with `partial`, then map it over the
            values. The point is that the bounds are stated in one place.
            """,
            "clamp_all", "values, lo, hi", _clamp_all,
            """
            from functools import partial


            def clamp_all(values, lo, hi):
                def clamp(low, high, value):
                    return max(low, min(high, value))

                bounded = partial(clamp, lo, hi)
                return [bounded(value) for value in values]
            """,
            [("mixed", [[-5, 5, 15], 0, 10]), ("all inside", [[1, 2], 0, 10])],
            [("all below", [[-9, -3], 0, 10]), ("all above", [[99, 50], 0, 10]),
             ("degenerate range", [[5, 1], 3, 3])],
            edges=[("empty", [[], 0, 10])],
            pattern="ARRAY", family="stdlib_partial",
            after="py-partial-guided",
            nudge="Order the parameters so the ones you want to pre-fill come "
                  "first. partial can only fill positionally from the left.",
            pseudocode="bounded = partial(clamp, lo, hi)\n[bounded(v) for v in values]",
            time="O(n)", space="O(n)",
        ),

        # ===================================================================
        # functools.cmp_to_key
        # ===================================================================
        _drill(
            "py-cmp-to-key-guided", "When The Rule Is About Two Things", "GUIDED",
            """
            `sorted(key=...)` scores each element alone. Some orderings cannot be
            expressed that way — the rule is genuinely about a PAIR. For those,
            write a comparator returning negative / zero / positive and wrap it in
            `functools.cmp_to_key`.

            Sort `words` by length, shortest first, ties broken alphabetically.
            (A key could do this one too; here it is the comparator you are
            learning, on a rule you can check by eye.)
            """,
            "by_length", "words", _by_length,
            """
            from functools import cmp_to_key


            def by_length(words):
                def compare(a, b):
                    if len(a) != len(b):
                        return len(a) - len(b)
                    # (a > b) - (a < b) is the classic three-way compare.
                    return (a > b) - (a < b)

                return sorted(words, key=cmp_to_key(compare))
            """,
            [("mixed lengths", [["bbb", "a", "cc"]]),
             ("same length", [["pear", "acid"]])],
            [("ties everywhere", [["bb", "aa", "cc"]]),
             ("already sorted", [["a", "bb", "ccc"]]),
             ("single", [["only"]])],
            edges=[("empty", [[]]), ("empty string present", [["", "a"]])],
            pattern="SORTING", family="stdlib_cmp_to_key",
            starter="""
            from functools import cmp_to_key


            def by_length(words):
                def compare(a, b):
                    if len(a) != len(b):
                        return len(a) - len(b)
                    return (a > b) - (a < b)

                # 1. Turn the two-argument comparator into a sort key.
                return sorted(words, key=__BLANK__)
            """,
            same_move="sorted(rows, key=cmp_to_key(my_rule), reverse=True)",
            nudge="Negative means 'a comes first'. Positive means 'b comes first'. "
                  "Zero means the order between them does not matter.",
            pseudocode="sorted(words, key=cmp_to_key(compare))",
            failures=["Returning True/False from the comparator — booleans are 1 and 0, "
                      "so 'b first' and 'equal' become indistinguishable"],
            time="O(n log n)", space="O(n)",
        ),

        _drill(
            "py-cmp-to-key-magnitude", "Closest To Zero First", "TUTORIAL",
            """
            Sort `nums` by absolute value, smallest first. When two values have the
            same magnitude the negative one comes first.

            Write it as a comparator: compare magnitudes, and fall back to the
            values themselves when the magnitudes match.
            """,
            "by_magnitude", "nums", _by_magnitude,
            """
            from functools import cmp_to_key


            def by_magnitude(nums):
                def compare(a, b):
                    if abs(a) != abs(b):
                        return abs(a) - abs(b)
                    return a - b

                return sorted(nums, key=cmp_to_key(compare))
            """,
            [("mixed signs", [[3, -1, 2]]), ("pair of opposites", [[2, -2]])],
            [("all negative", [[-3, -1, -2]]), ("with zero", [[0, -1, 1]]),
             ("already ordered", [[-1, 1, -2]])],
            edges=[("empty", [[]]), ("single", [[-5]])],
            pattern="SORTING", family="stdlib_cmp_to_key",
            after="py-cmp-to-key-guided",
            nudge="Subtraction is a legal comparator for numbers because its sign "
                  "is all the sort reads.",
            pseudocode="compare on abs(a) - abs(b), tie-break on a - b",
            time="O(n log n)", space="O(n)",
        ),

        _drill(
            "py-cmp-to-key-versions", "Version Numbers Do Not Sort As Strings", "EASY",
            """
            Sort `versions` — strings like "1.2.10" — in true version order.
            "1.2.10" is newer than "1.2.9", which string comparison gets wrong.
            A version with fewer components sorts before a longer one that shares
            its prefix: "1.2" comes before "1.2.0".
            """,
            "by_version", "versions", _by_version,
            """
            from functools import cmp_to_key


            def by_version(versions):
                def parts(version):
                    return [int(piece) for piece in version.split(".")]

                def compare(a, b):
                    left, right = parts(a), parts(b)
                    if left < right:
                        return -1
                    return 1 if left > right else 0

                return sorted(versions, key=cmp_to_key(compare))
            """,
            [("double digits", [["1.2.10", "1.2.9"]]),
             ("major versions", [["2.0", "1.9"]])],
            [("shared prefix", [["1.2", "1.2.0"]]),
             ("three deep", [["1.0.1", "1.0.0", "1.1.0"]]),
             ("leading zeros", [["1.01", "1.1"]])],
            edges=[("single", [["3.4"]]), ("empty", [[]])],
            pattern="SORTING", family="stdlib_cmp_to_key",
            after="py-cmp-to-key-magnitude",
            nudge="Python already compares lists of ints lexicographically, so the "
                  "comparator body is one list comparison.",
            pseudocode="parts = [int(p) for p in version.split('.')]\ncompare the two part lists",
            failures=["Sorting the raw strings and putting 1.2.10 before 1.2.9",
                      "Comparing only the first component"],
            time="O(n log n * k)", space="O(n)",
        ),

        _drill(
            "py-cmp-to-key-largest", "The Largest Number They Spell", "MEDIUM",
            """
            Arrange every number in `nums` into the single largest number their
            decimal strings can spell, and return it as a string. [3, 30, 34] gives
            "34330". All zeros give "0", not "000".

            There is no per-element key that orders these: whether 3 comes before
            30 depends on 30, and nothing about 3 alone. The rule is pairwise —
            a before b when a+b reads larger than b+a — which is precisely what
            cmp_to_key exists for.
            """,
            "largest_number", "nums", _largest_number,
            """
            from functools import cmp_to_key


            def largest_number(nums):
                parts = [str(n) for n in nums]

                def compare(a, b):
                    if a + b == b + a:
                        return 0
                    # -1 puts a first, and we want a first when a+b reads larger.
                    return -1 if a + b > b + a else 1

                parts.sort(key=cmp_to_key(compare))
                joined = "".join(parts)
                return "0" if joined.startswith("0") else joined
            """,
            [("classic", [[3, 30, 34, 5, 9]]), ("two numbers", [[10, 2]])],
            [("prefix trap", [[3, 30]]),
             ("all same digit", [[1, 1, 1]]),
             ("descending already", [[9, 8, 7]]),
             ("long and short", [[121, 12]])],
            edges=[("all zeros", [[0, 0]]), ("single number", [[7]]),
                   ("empty", [[]])],
            pattern="SORTING", family="stdlib_cmp_to_key",
            after="py-cmp-to-key-versions",
            nudge="Compare `a + b` against `b + a` as STRINGS. That single line is "
                  "the whole insight.",
            pseudocode="sort strings by: a+b > b+a means a first\njoin, then collapse all-zeros to '0'",
            failures=["Sorting numerically and getting 3 before 30",
                      "Returning '000' instead of '0'"],
            time="O(n log n * k)", space="O(n)",
        ),

        # ===================================================================
        # dataclasses
        # ===================================================================
        _drill(
            "py-dataclass-guided", "A Record Without The Boilerplate", "GUIDED",
            """
            `@dataclass` writes `__init__`, `__repr__` and `__eq__` from the field
            annotations. Three lines replace fifteen, and the fields have names
            and defaults instead of positions.

            `rows` is a list of [name, price] or [name, price, qty]. Return the
            total cost. A row with no quantity means one of that item.
            """,
            "cart_total", "rows", _cart_total,
            """
            from dataclasses import dataclass


            @dataclass
            class Item:
                name: str
                price: float
                qty: int = 1


            def cart_total(rows):
                items = [Item(*row) for row in rows]
                return sum(item.price * item.qty for item in items)
            """,
            [("two items", [[["axe", 10.0, 2], ["rope", 2.5]]]),
             ("defaults only", [[["torch", 1.0], ["flint", 2.0]]])],
            [("zero quantity", [[["dust", 5.0, 0]]]),
             ("single row", [[["blade", 7.5, 3]]]),
             ("integer prices", [[["stone", 2, 4]]])],
            edges=[("empty cart", [[]])],
            pattern="ARRAY", family="stdlib_dataclasses",
            starter="""
            from dataclasses import dataclass


            @dataclass
            class Item:
                name: str
                price: float
                qty: int = 1


            def cart_total(rows):
                items = [Item(*row) for row in rows]
                # 1. What one line of the receipt costs.
                return sum(__BLANK__ for item in items)
            """,
            same_move="@dataclass(frozen=True)   # the same record, immutable",
            nudge="The annotation `qty: int = 1` is what makes the third element "
                  "optional. The dataclass turns it into a real default argument.",
            pseudocode="sum(item.price * item.qty for item in items)",
            failures=["Using a mutable default like `tags: list = []` — dataclasses "
                      "reject it and demand field(default_factory=list)"],
            cmp="float", time="O(n)", space="O(n)",
        ),

        _drill(
            "py-dataclass-order", "Sortable For Free", "TUTORIAL",
            """
            `@dataclass(order=True)` generates the comparison methods, comparing
            fields in declaration order. Declare the fields in the order you want
            them compared and `sorted(records)` needs no key at all.

            `rows` is a list of [score, name]. Return them sorted by score
            ascending, ties by name ascending, as [score, name] lists.
            """,
            "ranked", "rows", _ranked,
            """
            from dataclasses import dataclass


            @dataclass(order=True)
            class Entry:
                score: int
                name: str


            def ranked(rows):
                entries = sorted(Entry(*row) for row in rows)
                return [[entry.score, entry.name] for entry in entries]
            """,
            [("two entries", [[[9, "ada"], [3, "bo"]]]),
             ("tie on score", [[[5, "zed"], [5, "ada"]]])],
            [("already sorted", [[[1, "a"], [2, "b"]]]),
             ("negative scores", [[[-1, "a"], [-5, "b"]]]),
             ("three entries", [[[2, "c"], [2, "a"], [1, "b"]]])],
            edges=[("empty", [[]]), ("single", [[[4, "solo"]]])],
            pattern="SORTING", family="stdlib_dataclasses",
            after="py-dataclass-guided",
            nudge="Field order IS comparison order. If you want to sort by score "
                  "first, score is declared first.",
            pseudocode="@dataclass(order=True) with score declared before name\nsorted(entries)",
            failures=["Forgetting `order=True` and meeting TypeError: '<' not supported"],
            time="O(n log n)", space="O(n)",
        ),

        # ===================================================================
        # bisect
        # ===================================================================
        _drill(
            "py-bisect-guided", "Where Would It Go?", "GUIDED",
            """
            `bisect_left(values, target)` returns the index where `target` belongs
            in an already-sorted list — the leftmost position that keeps the list
            sorted. It is a binary search you do not have to get the off-by-one
            right in.

            Return that insertion index for `target` in the sorted list `values`.
            """,
            "insert_position", "values, target", _insert_position,
            """
            import bisect


            def insert_position(values, target):
                return bisect.bisect_left(values, target)
            """,
            [("middle", [[1, 3, 5, 7], 4]), ("present already", [[1, 3, 5], 3])],
            [("before everything", [[2, 4], 1]),
             ("after everything", [[2, 4], 9]),
             ("duplicates present", [[1, 2, 2, 2, 3], 2])],
            edges=[("empty list", [[], 5]), ("single element", [[5], 5])],
            pattern="BINARY_SEARCH", family="stdlib_bisect", realm="stack_queue_mines",
            starter="""
            import bisect


            def insert_position(values, target):
                # 1. The leftmost index where target keeps the list sorted.
                return __BLANK__
            """,
            same_move="bisect.bisect_right(values, target)   # the rightmost such index",
            nudge="`bisect_left` lands BEFORE an equal run, `bisect_right` lands "
                  "after it. On a list with no duplicates they agree.",
            pseudocode="bisect.bisect_left(values, target)",
            failures=["Calling bisect on an unsorted list — it answers, and the "
                      "answer is meaningless"],
            time="O(log n)", space="O(1)",
        ),

        _drill(
            "py-bisect-insort", "Keeping It Sorted As You Go", "TUTORIAL",
            """
            Insert `target` into the sorted list `values` so the result stays
            sorted, and return the new list without modifying the caller's.

            `bisect.insort` finds the position and inserts in one call. The search
            is O(log n); the insert is still O(n), and knowing which half is which
            is the part an interviewer will ask about.
            """,
            "place", "values, target", _place,
            """
            import bisect


            def place(values, target):
                out = list(values)
                bisect.insort(out, target)
                return out
            """,
            [("into the middle", [[1, 3, 5], 4]), ("at the end", [[1, 2], 9])],
            [("at the front", [[5, 6], 1]),
             ("equal to an existing value", [[1, 2, 3], 2]),
             ("negatives", [[-5, -1], -3])],
            edges=[("empty list", [[], 1]), ("duplicate run", [[2, 2, 2], 2])],
            pattern="BINARY_SEARCH", family="stdlib_bisect", realm="stack_queue_mines",
            after="py-bisect-guided",
            nudge="`insort` is `insort_right`: it places a duplicate after the "
                  "existing equal values.",
            pseudocode="out = list(values)\nbisect.insort(out, target)",
            failures=["Mutating the caller's list because you forgot the copy"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-bisect-range", "How Many Fall In The Band", "EASY",
            """
            `values` is sorted ascending. Return how many of them fall in the
            inclusive range [lo, hi].

            Counting with a loop is O(n) and fine for one query. Two bisects
            answer it in O(log n), which is what you want when the query is asked
            a million times — and the subtraction is the whole implementation.
            """,
            "count_in_range", "values, lo, hi", _count_in_range,
            """
            import bisect


            def count_in_range(values, lo, hi):
                # bisect_left for the lower bound INCLUDES values equal to lo;
                # bisect_right for the upper bound INCLUDES values equal to hi.
                start = bisect.bisect_left(values, lo)
                stop = bisect.bisect_right(values, hi)
                # An inverted band (lo > hi) crosses the two indexes over, so the
                # subtraction goes negative. The count is zero, not minus two.
                return max(0, stop - start)
            """,
            [("middle band", [[1, 3, 5, 7, 9], 3, 7]),
             ("whole list", [[1, 2, 3], 0, 10])],
            [("bounds land on values", [[1, 2, 3, 4], 2, 3]),
             ("nothing in band", [[1, 2, 9], 4, 8]),
             ("duplicates in band", [[2, 2, 2, 5], 2, 2])],
            edges=[("empty list", [[], 1, 5]), ("inverted band", [[1, 2, 3], 5, 1])],
            pattern="BINARY_SEARCH", family="stdlib_bisect", realm="stack_queue_mines",
            after="py-bisect-insort",
            long_way="""
            count = 0
            for value in values:
                if lo <= value <= hi:
                    count += 1
            return count
            """,
            nudge="Left for the low end, right for the high end. Swap them and you "
                  "silently exclude the boundary values.",
            pseudocode="max(0, bisect_right(values, hi) - bisect_left(values, lo))",
            failures=["Using bisect_left for both bounds and dropping values equal to hi",
                      "Returning a negative count when lo > hi, because the two "
                      "indexes cross over"],
            time="O(log n)", space="O(1)",
        ),

        # ===================================================================
        # math
        # ===================================================================
        _drill(
            "py-math-gcd-guided", "Euclid Is Already Installed", "GUIDED",
            """
            `math.gcd(a, b)` is the greatest common divisor, in C, correct for
            negatives and zero. Writing the Euclid loop by hand is four lines you
            do not need and one `while` condition you can get wrong.

            Return the greatest common divisor of `a` and `b`.
            """,
            "gcd_pair", "a, b", _gcd_pair,
            """
            import math


            def gcd_pair(a, b):
                return math.gcd(a, b)
            """,
            [("twelve and eighteen", [12, 18]), ("coprime", [9, 28])],
            [("one divides the other", [5, 25]),
             ("negatives", [-12, 18]),
             ("equal", [7, 7])],
            edges=[("zero and n", [0, 5]), ("both zero", [0, 0])],
            pattern="ARRAY", family="stdlib_math",
            starter="""
            import math


            def gcd_pair(a, b):
                # 1. The greatest common divisor of a and b.
                return __BLANK__
            """,
            long_way="""
            a, b = abs(a), abs(b)
            while b:
                a, b = b, a % b
            return a
            """,
            same_move="math.lcm(a, b)   # lowest common multiple, same idea",
            nudge="`math.gcd(0, 0)` is 0 and `math.gcd(-12, 18)` is 6. The library "
                  "has already decided the edge cases; your loop has to.",
            pseudocode="math.gcd(a, b)",
            time="O(log n)", space="O(1)",
        ),

        _drill(
            "py-math-isqrt", "Integer Square Root, Exactly", "TUTORIAL",
            """
            Return True if `n` is a perfect square, False otherwise. Negative
            numbers are not.

            `math.isqrt(n)` is the exact integer square root — no floats, so no
            rounding surprise at large n. `int(n ** 0.5)` is the version that
            quietly answers wrong once n gets big enough.
            """,
            "is_perfect_square", "n", _is_perfect_square,
            """
            import math


            def is_perfect_square(n):
                if n < 0:
                    return False
                root = math.isqrt(n)
                return root * root == n
            """,
            [("sixteen", [16]), ("seventeen", [17])],
            [("one", [1]), ("large square", [10000]), ("large non-square", [9999])],
            edges=[("zero", [0]), ("negative", [-4])],
            pattern="ARRAY", family="stdlib_math",
            after="py-math-gcd-guided",
            nudge="isqrt floors the true root, so squaring it back is the test.",
            pseudocode="root = math.isqrt(n); return root * root == n",
            failures=["`int(n ** 0.5)` drifting by one on large inputs",
                      "math.isqrt raises ValueError on a negative — guard first"],
            cmp="bool", time="O(1)", space="O(1)",
        ),

        # ===================================================================
        # statistics
        # ===================================================================
        _drill(
            "py-statistics-guided", "The Mean, Without The Division", "GUIDED",
            """
            `statistics.mean` exists, handles integers and floats, and says what it
            means at the call site. `sum(values) / len(values)` is the same number
            and one more chance to divide by zero unnoticed.

            Return the arithmetic mean of `values`, which always has at least one
            entry.
            """,
            "average", "values", _average,
            """
            import statistics


            def average(values):
                return statistics.mean(values)
            """,
            [("three integers", [[1, 2, 3]]), ("floats", [[1.5, 2.5]])],
            [("negatives", [[-2, 2]]), ("all identical", [[4, 4, 4]]),
             ("mixed", [[1, 2, 3, 4]])],
            edges=[("single value", [[9]])],
            pattern="ARRAY", family="stdlib_statistics",
            constraints=["values has at least one entry"],
            starter="""
            import statistics


            def average(values):
                # 1. The arithmetic mean of the values.
                return __BLANK__
            """,
            same_move="statistics.pstdev(values)   # population standard deviation",
            nudge="`statistics.mean([])` raises StatisticsError rather than "
                  "ZeroDivisionError, which is a better error to read.",
            pseudocode="statistics.mean(values)",
            cmp="float", time="O(n)", space="O(1)",
        ),

        _drill(
            "py-statistics-centre", "Mean And Median Disagree", "TUTORIAL",
            """
            Return [mean, median] for `values`, which always has at least one
            entry.

            The point of the drill is the pair: one outlier drags the mean and
            leaves the median alone, and being able to say which one a metric
            should use is an engineering answer, not a maths answer.
            """,
            "centre", "values", _centre,
            """
            import statistics


            def centre(values):
                return [statistics.mean(values), statistics.median(values)]
            """,
            [("no outlier", [[1, 2, 3]]), ("one huge outlier", [[1, 2, 300]])],
            [("even count", [[1, 2, 3, 4]]),
             ("all identical", [[5, 5, 5]]),
             ("negatives", [[-3, -1, 1]])],
            edges=[("single value", [[7]]), ("two values", [[1, 4]])],
            pattern="ARRAY", family="stdlib_statistics",
            after="py-statistics-guided",
            constraints=["values has at least one entry"],
            nudge="`median` of an even-length sample averages the middle two, "
                  "which is why it can be a float when every input was an int.",
            pseudocode="[statistics.mean(values), statistics.median(values)]",
            cmp="float_list", time="O(n log n)", space="O(n)",
        ),

        # ===================================================================
        # enum
        # ===================================================================
        _drill(
            "py-enum-guided", "Names With Values Behind Them", "GUIDED",
            """
            An `Enum` turns a set of magic constants into named members with
            values. `Level["WARN"]` looks a member up by name and `.value` reads
            the number behind it — and a typo raises immediately instead of
            silently comparing False forever.

            Return the names in `names` whose level is at least `floor`.
            """,
            "at_least", "names, floor", _at_least,
            """
            from enum import Enum


            class Level(Enum):
                DEBUG = 10
                INFO = 20
                WARN = 30
                ERROR = 40


            def at_least(names, floor):
                cutoff = Level[floor].value
                return [name for name in names if Level[name].value >= cutoff]
            """,
            [("from info up", [["DEBUG", "INFO", "ERROR"], "INFO"]),
             ("everything", [["DEBUG", "WARN"], "DEBUG"])],
            [("nothing qualifies", [["DEBUG", "INFO"], "ERROR"]),
             ("order preserved", [["ERROR", "DEBUG", "WARN"], "WARN"]),
             ("single name", [["WARN"], "INFO"])],
            edges=[("empty names", [[], "INFO"])],
            pattern="HASH_MAP", family="stdlib_enum",
            starter="""
            from enum import Enum


            class Level(Enum):
                DEBUG = 10
                INFO = 20
                WARN = 30
                ERROR = 40


            def at_least(names, floor):
                # 1. The number behind the member named by `floor`.
                cutoff = __BLANK__
                return [name for name in names if Level[name].value >= cutoff]
            """,
            same_move="Level(30)   # look a member up by VALUE instead of by name",
            nudge="`Level[name]` is lookup by name and uses square brackets. "
                  "`Level(value)` is lookup by value and uses parentheses.",
            pseudocode="cutoff = Level[floor].value\nkeep names whose Level[name].value >= cutoff",
            failures=["Comparing members of a plain Enum with `>` — only IntEnum "
                      "supports ordering"],
            time="O(n)", space="O(n)",
        ),

        _drill(
            "py-enum-iterate", "Everything Louder Than This", "TUTORIAL",
            """
            Return the names of every level strictly louder than `floor`, quietest
            first.

            Iterating the Enum class itself yields its members in declaration
            order, which is the ordering you designed when you wrote the class.
            """,
            "louder_than", "floor", _louder_than,
            """
            from enum import Enum


            class Level(Enum):
                DEBUG = 10
                INFO = 20
                WARN = 30
                ERROR = 40


            def louder_than(floor):
                cutoff = Level[floor]
                return [level.name for level in Level if level.value > cutoff.value]
            """,
            [("above info", ["INFO"]), ("above debug", ["DEBUG"])],
            [("above warn", ["WARN"]), ("above error", ["ERROR"])],
            edges=[("the loudest", ["ERROR"])],
            pattern="HASH_MAP", family="stdlib_enum",
            after="py-enum-guided",
            nudge="`for level in Level` iterates the members; `.name` and `.value` "
                  "read the two halves of each one.",
            pseudocode="for level in Level: keep level.name where value > cutoff",
            time="O(k)", space="O(k)",
        ),

        # ===================================================================
        # typing basics — recognition, not runtime
        # ===================================================================
        mcq_problem(
            id="py-typing-read-annotation", title="Reading An Annotation",
            realm="fields_of_syntax", pattern="RECOGNITION", difficulty="GUIDED",
            statement="""
            An annotation is documentation the tooling can check. It is not
            enforced at runtime — nothing below raises because of it.

            What does this signature promise about `index`?
            """,
            code="""
            def index(rows: list[str]) -> dict[str, list[int]]:
                ...
            """,
            choices=[
                "It takes a list of strings and returns a dict whose keys are "
                "strings and whose values are lists of integers.",
                "It takes a list of strings and returns a list of integers keyed "
                "by a string.",
                "It raises TypeError if you pass anything other than a list of "
                "strings.",
                "It returns a dict with exactly one string key.",
            ],
            answer=0,
            explanation="""
            Read the outer container first, then what it holds:
            `dict[str, list[int]]` is a dict from str to list-of-int. This is the
            return shape of every 'group the positions by value' answer you will
            write.

            Nothing here is checked when the program runs. Passing a dict of ints
            does not raise; it just makes a liar of the signature, which is what a
            type checker is for.
            """,
            family="stdlib_typing", seconds=60,
            distractor_notes={
                "1": "Reads the nesting inside out.",
                "2": "Annotations are never enforced at runtime.",
                "3": "Nothing in the annotation constrains the number of keys.",
            },
        ),

        mcq_problem(
            id="py-typing-optional", title="The Value That Might Not Be There",
            realm="fields_of_syntax", pattern="RECOGNITION", difficulty="TUTORIAL",
            statement="""
            `Optional[int]` and `int | None` mean the same thing; the second is
            the modern spelling. What is this signature telling the caller?
            """,
            code="""
            def find(rows: list[str], needle: str) -> int | None:
                ...
            """,
            choices=[
                "It may return an int or None, so the caller has to handle the "
                "missing case.",
                "It returns an int, and returning None would be a runtime error.",
                "It returns an int or raises an exception when the needle is absent.",
                "`int | None` is invalid syntax; only `Optional[int]` works.",
            ],
            answer=0,
            explanation="""
            `-> int | None` is the API saying 'absent is a normal outcome, not an
            exception'. The caller writes `if result is None:` rather than a
            try/except.

            Saying this out loud in an interview — 'I will return None for not
            found rather than raise, and here is why' — is the communication half
            of the question, and it is usually worth more than the code.
            """,
            family="stdlib_typing", seconds=75,
            distractor_notes={
                "1": "None is exactly what the annotation permits.",
                "2": "That would be `-> int` with a documented exception.",
                "3": "`X | Y` has been valid in annotations since 3.10.",
            },
        ),
    ]
