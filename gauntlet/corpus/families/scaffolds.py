"""The Rune Vault: MISSING_RUNE encounters, one rung below a real Code Battle.

The Village teaches Python. The Code Battles demand a whole function from a blank
screen. Nothing sat between them, which is why the blank screen was where people
stopped. These encounters are that missing rung.

Each one hands the player the complete, correct shape of a pattern with one to
three runes struck out of it. The struck lines are never bookkeeping — they are
the shrink condition, the visited-marking, the midpoint, the recurrence. The
surrounding code is the explanation; the hole is the question. You cannot fill it
by pattern-matching on syntax, only by knowing why the line exists.

Two authoring rules hold everywhere in this module:

1. The blanked starter is DERIVED from the canonical solution, never typed twice.
   `_blank` locates each target inside the canonical source and replaces it in
   place, raising at build time if a target has gone stale. A scaffold is
   therefore always exactly the worked solution with holes in it, and can never
   drift away from the answer it teaches.

2. `__BLANK__` is a bare name, so the starter always parses. A player who runs it
   untouched gets a NameError naming the rune they still owe, not a SyntaxError
   pointing at column one.
"""
from __future__ import annotations

from ._base import code_problem, dedent
from ._tree import PREAMBLE as TREE_PREAMBLE, tree_ref

Q = {"PRACTICAL": 2.0, "GENERAL_SWE": 2.0, "SECURITY_ENGINEERING": 1.5}

# Appended to every statement. The player must know that the rest of the function
# is not under suspicion, or they will read the whole thing looking for a second bug.
SCAFFOLD_NOTE = dedent("""
    Every `__BLANK__` is exactly one expression or one statement. Fill them in and
    change nothing else: the surrounding code is already correct, and is there to
    tell you what the missing rune has to do.
""")

VIZ_FOR = {
    "HASH_MAP": {"type": "hash_map", "caption": "KEY seen once, answered forever."},
    "SET": {"type": "hash_map", "caption": "Membership only. No counts."},
    "SLIDING_WINDOW": {"type": "sliding_window", "caption": "LEFT, RIGHT, CONSTRAINT, BEST."},
    "TWO_POINTER": {"type": "two_pointer", "caption": "Two indices, moving with intent."},
    "STACK": {"type": "stack", "caption": "The most recent thing, first."},
    "QUEUE": {"type": "queue", "caption": "Oldest in, oldest out."},
    "BFS": {"type": "bfs", "caption": "Expanding rings. First arrival wins."},
    "DFS": {"type": "dfs", "caption": "Commit to a path, then unwind."},
    "TREE": {"type": "tree", "caption": "What does this node need from its children?"},
    "RECURSION": {"type": "recursion", "caption": "Base case, then a smaller call."},
    "BINARY_SEARCH": {"type": "binary_search", "caption": "Halve the space, every step."},
    "PREFIX_SUM": {"type": "prefix_sum", "caption": "Totals precomputed once."},
    "SORTING": {"type": "array_scan", "caption": "Order first; the answer turns local."},
    "INTERVALS": {"type": "array_scan", "caption": "Sorted by start, merged in one pass."},
    "DP": {"type": "dp", "caption": "Each subproblem paid for exactly once."},
    "STRING": {"type": "array_scan", "caption": "Characters, counts and slices."},
}


# ---------------------------------------------------------------------------
# Scaffold construction
# ---------------------------------------------------------------------------

def _blank(canonical: str, blanks) -> str:
    """Strike the named targets out of the canonical source.

    `blanks` is an ordered sequence of (target, hint). Each target is a substring
    of the canonical solution; the first line still carrying it is rewritten with
    `__BLANK__` in its place and the hint appended as a numbered comment. Targets
    are matched in order, so repeating a target strikes successive occurrences.

    A target that no longer appears is a build-time error rather than a silently
    unblanked scaffold, because a MISSING_RUNE with nothing missing grades as a
    free clear and teaches nothing.
    """
    lines = canonical.rstrip("\n").splitlines()
    for number, (target, hint) in enumerate(blanks, 1):
        for i, line in enumerate(lines):
            if target in line and "__BLANK__" not in line:
                lines[i] = line.replace(target, "__BLANK__", 1) + f"  # {number}. {hint}"
                break
        else:
            raise ValueError(f"scaffold target {target!r} is not in the canonical solution")
    return "\n".join(lines) + "\n"


def rune(*, blanks, statement: str, scaffold_for: str, pattern: str,
         partial: str = "", canonical: str, **kw):
    """A MISSING_RUNE encounter, built from the canonical solution outward."""
    canonical = dedent(canonical)
    starter = _blank(canonical, blanks)
    tags = ["scaffold", "missing-rune"] + list(kw.pop("tags", ()))

    # Rung 4 of the hint tree would otherwise be the first four lines of the
    # answer, which for a twelve-line scaffold is most of the answer. Give back
    # the first rune instead and leave the rest struck out: a real intermediate
    # step rather than a truncation.
    if not partial:
        partial = _blank(canonical, list(blanks)[1:])
    fragment = "```python\n" + partial.rstrip() + "\n```"

    return code_problem(
        pattern=pattern,
        encounter="MISSING_RUNE",
        canonical=canonical,
        statement="SCAFFOLD — " + scaffold_for + "\n\n" + dedent(statement)
                  + "\n" + SCAFFOLD_NOTE,
        fragment=fragment,
        viz=VIZ_FOR.get(pattern, {}),
        profile_weight=Q,
        tags=tags,
        starter_code=starter,
        **kw,
    )


# ---------------------------------------------------------------------------
# References. Each is an independent retyping of the canonical solution; the
# validator only accepts the problem if the two agree on every test.
# ---------------------------------------------------------------------------

def _two_sum(nums, target):
    seen = {}
    for i, value in enumerate(nums):
        if target - value in seen:
            return [seen[target - value], i]
        seen[value] = i
    return []


def _count_frequency(items):
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _is_anagram(a, b):
    return len(a) == len(b) and sorted(a) == sorted(b)


def _first_unique_char(s):
    for i, ch in enumerate(s):
        if s.count(ch) == 1:
            return i
    return -1


def _group_anagrams(words):
    groups = {}
    for word in words:
        groups.setdefault("".join(sorted(word)), []).append(word)
    return [groups[key] for key in sorted(groups)]


def _contains_duplicate(nums):
    return len(set(nums)) != len(nums)


def _set_overlap(a, b):
    return [sorted(set(a) & set(b)), sorted(set(a) - set(b))]


def _dedupe(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _max_window_sum(nums, k):
    if k <= 0 or k > len(nums):
        return 0
    return max(sum(nums[i:i + k]) for i in range(len(nums) - k + 1))


def _longest_unique_window(s):
    best = 0
    for i in range(len(s)):
        for j in range(i, len(s)):
            if len(set(s[i:j + 1])) == j - i + 1:
                best = max(best, j - i + 1)
    return best


def _min_window_length(nums, target):
    best = len(nums) + 1
    for i in range(len(nums)):
        total = 0
        for j in range(i, len(nums)):
            total += nums[j]
            if total >= target:
                best = min(best, j - i + 1)
                break
    return 0 if best > len(nums) else best


def _two_sum_sorted(nums, target):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
    return []


def _is_palindrome(s):
    return s == s[::-1]


def _reverse_list(items):
    return list(items)[::-1]


def _remove_duplicates(nums):
    out = []
    for value in nums:
        if not out or out[-1] != value:
            out.append(value)
    return out


def _is_balanced(s):
    stack = []
    opens = {"(": ")", "[": "]", "{": "}"}
    for ch in s:
        if ch in opens:
            stack.append(opens[ch])
        else:
            if not stack or stack.pop() != ch:
                return False
    return not stack


def _eval_rpn(tokens):
    stack = []
    for token in tokens:
        if token == "+":
            stack.append(stack.pop(-2) + stack.pop())
        elif token == "-":
            stack.append(stack.pop(-2) - stack.pop())
        elif token == "*":
            stack.append(stack.pop(-2) * stack.pop())
        else:
            stack.append(int(token))
    return stack[0]


def _days_until_warmer(temps):
    out = []
    for i, temp in enumerate(temps):
        wait = 0
        for j in range(i + 1, len(temps)):
            if temps[j] > temp:
                wait = j - i
                break
        out.append(wait)
    return out


def _recent_pings(times, window):
    out = []
    for i, t in enumerate(times):
        out.append(sum(1 for earlier in times[:i + 1] if earlier > t - window))
    return out


def _last_survivor(names, step):
    people, index = list(names), 0
    while len(people) > 1:
        index = (index + step - 1) % len(people)
        people.pop(index)
    return people[0]


def _shortest_path(grid):
    if not grid or grid[0][0] == 1 or grid[-1][-1] == 1:
        return -1
    rows, cols = len(grid), len(grid[0])
    best = {(0, 0): 1}
    layer = [(0, 0)]
    while layer:
        nxt = []
        for r, c in layer:
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0 \
                        and (nr, nc) not in best:
                    best[(nr, nc)] = best[(r, c)] + 1
                    nxt.append((nr, nc))
        layer = nxt
    return best.get((rows - 1, cols - 1), -1)


def _level_order(root):
    out, layer = [], [root] if root else []
    while layer:
        out.append([node.val for node in layer])
        nxt = []
        for node in layer:
            nxt.extend(child for child in (node.left, node.right) if child)
        layer = nxt
    return out


def _count_islands(grid):
    if not grid:
        return 0
    rows, cols = len(grid), len(grid[0])
    seen, total = set(), 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != 1 or (r, c) in seen:
                continue
            total += 1
            pending = [(r, c)]
            seen.add((r, c))
            while pending:
                pr, pc = pending.pop()
                for nr, nc in ((pr + 1, pc), (pr - 1, pc), (pr, pc + 1), (pr, pc - 1)):
                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1 \
                            and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        pending.append((nr, nc))
    return total


def _reachable(graph, start):
    seen, pending = set(), [start]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(graph.get(node, []))
    return sorted(seen)


def _max_depth(root):
    depth, layer = 0, [root] if root else []
    while layer:
        depth += 1
        layer = [child for node in layer for child in (node.left, node.right) if child]
    return depth


def _invert_tree(root):
    if root is None:
        return None
    root.left, root.right = _invert_tree(root.right), _invert_tree(root.left)
    return root


def _bst_contains(root, target):
    values = []
    pending = [root]
    while pending:
        node = pending.pop()
        if node is None:
            continue
        values.append(node.val)
        pending.append(node.left)
        pending.append(node.right)
    return target in values


def _factorial(n):
    total = 1
    for i in range(2, n + 1):
        total *= i
    return total


def _fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _binary_search(nums, target):
    for i, value in enumerate(nums):
        if value == target:
            return i
    return -1


def _first_at_least(nums, target):
    for i, value in enumerate(nums):
        if value >= target:
            return i
    return len(nums)


def _range_sums(nums, queries):
    return [sum(nums[lo:hi + 1]) for lo, hi in queries]


def _subarray_sum_count(nums, k):
    found = 0
    for i in range(len(nums)):
        total = 0
        for j in range(i, len(nums)):
            total += nums[j]
            if total == k:
                found += 1
    return found


def _climb_stairs(n):
    if n <= 0:
        return 1
    ways = [1, 1]
    for _ in range(2, n + 1):
        ways.append(ways[-1] + ways[-2])
    return ways[n]


def _max_loot(values):
    best = {}

    def go(i):
        if i >= len(values):
            return 0
        if i not in best:
            best[i] = max(go(i + 1), values[i] + go(i + 2))
        return best[i]

    return go(0)


def _unique_paths(rows, cols):
    if rows <= 0 or cols <= 0:
        return 0
    grid = [[1] * cols for _ in range(rows)]
    for r in range(1, rows):
        for c in range(1, cols):
            grid[r][c] = grid[r - 1][c] + grid[r][c - 1]
    return grid[rows - 1][cols - 1]


def _top_by_score(records, n):
    ordered = sorted(records, key=lambda r: r[0])
    ordered.sort(key=lambda r: r[1], reverse=True)
    return [list(r) for r in ordered[:n]]


def _merge_intervals(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def _reverse_words(text):
    words = text.split()
    words.reverse()
    return " ".join(words)


def _longest_common_prefix(words):
    if not words:
        return ""
    shortest = min(words, key=len)
    for i, ch in enumerate(shortest):
        if any(word[i] != ch for word in words):
            return shortest[:i]
    return shortest


# Level-order fixtures. The harness rebuilds these into real TreeNodes before the
# player's function ever sees them.
SAMPLE = [3, 9, 20, None, None, 15, 7]
SPINE = [1, 2, None, 3, None, 4]
BST = [8, 4, 12, 2, 6, 10, 14]
TREE_SHAPE = ("`root` is a `TreeNode` with `.val`, `.left` and `.right`. "
              "A missing child is `None`.")


def build() -> list:
    P: list = []
    tree = dict(preamble=TREE_PREAMBLE, arg_adapters=["tree"],
                realm="binary_tree_canopy")

    # -- HASH MAP -----------------------------------------------------------
    P.append(rune(
        id="sc-two-sum-rune", title="The Rune of the Missing Half",
        realm="hashmap_highlands", difficulty="GUIDED", family="two_sum",
        pattern="HASH_MAP", scaffold_for="HASH MAP", secondary=["ARRAY"],
        statement="""
            Return the indices of the two values in `nums` that add up to `target`.

            The scan is written for you. `seen` maps a value already walked past to
            the index it sat at. At every element the question is the same: what
            other number would finish the pair, and have I already walked past it?
        """,
        fn_name="two_sum", params="nums, target", reference=_two_sum,
        canonical="""
            def two_sum(nums, target):
                seen = {}
                for i, value in enumerate(nums):
                    need = target - value
                    if need in seen:
                        return [seen[need], i]
                    seen[value] = i
                return []
        """,
        blanks=[("target - value", "the number that would complete the pair"),
                ("seen[value] = i",
                 "file this value under its own index, for a later partner")],
        visible=[("ends", [[2, 7, 11, 15], 9]), ("middle", [[3, 2, 4], 6])],
        hidden=[("duplicates", [[3, 3], 6]), ("negatives", [[-3, 4, 3, 90], 0])],
        edges=[("no pair", [[1, 2, 3], 99]), ("empty", [[], 5])],
        constraints=["exactly one pair exists, or none at all"],
        failures=["Storing the value before checking it, so a number pairs with itself"],
        nudge="You are not looking for a pair. You are looking for one number at a time.",
        visual="At index i the dict already holds every index before i, and nothing after.",
        pseudocode="""
            seen = {}
            for each index i and value:
                need = target - value
                if need already in seen: answer is (seen[need], i)
                record value -> i
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-count-frequency", title="The Tally Rune", realm="hashmap_highlands",
        difficulty="GUIDED", family="counting", pattern="HASH_MAP",
        scaffold_for="HASH MAP: counting",
        statement="""
            Return a dict mapping each item in `items` to the number of times it
            appears.

            The loop is written. `counts` starts empty, which is the whole difficulty:
            the first time an item shows up there is no entry to add one to.
        """,
        fn_name="count_frequency", params="items", reference=_count_frequency,
        canonical="""
            def count_frequency(items):
                counts = {}
                for item in items:
                    counts[item] = counts.get(item, 0) + 1
                return counts
        """,
        blanks=[("counts.get(item, 0) + 1",
                 "this item's running count, treating 'never seen' as zero, plus one")],
        partial="""
            def count_frequency(items):
                counts = {}
                for item in items:
                    counts[item] = counts.get(item, __BLANK__) + 1
                return counts
        """,
        visible=[("letters", [["a", "b", "a"]]), ("numbers", [[1, 1, 1, 2]])],
        hidden=[("single", [["x"]]), ("all distinct", [["a", "b", "c"]])],
        edges=[("empty", [[]])],
        failures=["`counts[item] += 1` raises KeyError on the first sighting"],
        nudge="`dict.get` takes a second argument: what to return when the key is absent.",
        visual="Every item either extends a tally or starts one. Both cases, one line.",
        pseudocode="""
            counts = {}
            for each item:
                counts[item] = (existing count, default 0) + 1
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-is-anagram", title="The Budget of Letters", realm="stringwood_labyrinth",
        difficulty="TUTORIAL", family="anagrams", pattern="HASH_MAP",
        scaffold_for="HASH MAP: counting", secondary=["STRING"],
        statement="""
            Return True when `b` is a rearrangement of `a`.

            The first loop builds a budget: how many of each character `a` can
            afford. The second loop spends that budget, one character of `b` at a
            time. Two runes are missing from the spending loop.
        """,
        fn_name="is_anagram", params="a, b", reference=_is_anagram,
        canonical="""
            def is_anagram(a, b):
                if len(a) != len(b):
                    return False
                counts = {}
                for ch in a:
                    counts[ch] = counts.get(ch, 0) + 1
                for ch in b:
                    if counts.get(ch, 0) == 0:
                        return False
                    counts[ch] -= 1
                return True
        """,
        blanks=[("counts.get(ch, 0) == 0",
                 "b wants a character whose budget is already spent"),
                ("counts[ch] -= 1", "spend one of this character's remaining budget")],
        visible=[("classic", ["listen", "silent"]), ("not an anagram", ["rat", "car"])],
        hidden=[("repeats", ["aabb", "bbaa"]), ("different lengths", ["abc", "ab"])],
        edges=[("both empty", ["", ""]), ("same string", ["abc", "abc"])],
        failures=["Forgetting the length check, so 'a' matches 'aa'"],
        nudge="Count once, then spend. Never count both sides and compare by eye.",
        visual="The budget must land on exactly zero for every character.",
        pseudocode="""
            different lengths -> False
            count every character of a
            for each character of b:
                if none left in the budget -> False
                spend one
            -> True
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-first-unique-char", title="The Solitary Glyph",
        realm="stringwood_labyrinth", difficulty="EASY", family="frequency",
        pattern="HASH_MAP", scaffold_for="HASH MAP: two passes",
        secondary=["STRING"], prerequisites=["sc-count-frequency"],
        statement="""
            Return the index of the first character in `s` that appears exactly once,
            or -1 if every character repeats.

            This is two passes on purpose. The first counts every character; the
            second walks the string again in order and asks the counts a question.
            One pass cannot do it, because the answer depends on characters that
            have not been reached yet.
        """,
        fn_name="first_unique_char", params="s", reference=_first_unique_char,
        canonical="""
            def first_unique_char(s):
                counts = {}
                for ch in s:
                    counts[ch] = counts.get(ch, 0) + 1
                for i, ch in enumerate(s):
                    if counts[ch] == 1:
                        return i
                return -1
        """,
        blanks=[("counts.get(ch, 0) + 1", "build the tally for this character"),
                ("counts[ch] == 1", "this character's total over the whole string is one")],
        visible=[("classic", ["sandstorm"]), ("late answer", ["loveleetcode"])],
        hidden=[("none unique", ["aabb"]), ("first is unique", ["abab" + "c"])],
        edges=[("empty", [""]), ("single", ["z"])],
        failures=["Returning the character instead of its index",
                  "Stopping at the first character seen once *so far*"],
        nudge="The second loop reads counts. It never writes to them.",
        visual="Pass one fills the table; pass two consults it in string order.",
        pseudocode="""
            count every character
            walk the string again in order
                first character whose count is 1 -> its index
            none -> -1
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-group-anagrams", title="The Grove of Like Words",
        realm="stringwood_labyrinth", difficulty="EASY", family="anagrams",
        pattern="HASH_MAP", scaffold_for="HASH MAP: grouping by key",
        secondary=["SORTING", "STRING"], prerequisites=["sc-is-anagram"],
        statement="""
            Group the words into lists of mutual anagrams, and return the groups
            ordered by their shared signature.

            Grouping is always the same two moves: compute a key that every member
            of a group agrees on, then append into the bucket that key names. Both
            moves are struck out.
        """,
        fn_name="group_anagrams", params="words", reference=_group_anagrams,
        canonical="""
            def group_anagrams(words):
                groups = {}
                for word in words:
                    key = "".join(sorted(word))
                    groups.setdefault(key, []).append(word)
                return [groups[key] for key in sorted(groups)]
        """,
        blanks=[('"".join(sorted(word))',
                 "a signature every anagram of this word shares, and no other word does"),
                ("groups.setdefault(key, []).append(word)",
                 "file the word under its signature, creating the bucket if it is new")],
        visible=[("classic", [["eat", "tea", "tan", "ate", "nat", "bat"]]),
                 ("no groups", [["abc", "def"]])],
        hidden=[("single", [["a"]]), ("all one group", [["ab", "ba", "ab"]])],
        edges=[("empty", [[]]), ("empty words", [["", ""]])],
        failures=["Using a set as the key, which loses letter counts"],
        nudge="Anagrams disagree about order and agree about everything else.",
        visual="Sorting the letters throws away exactly the thing anagrams differ on.",
        pseudocode="""
            groups = {}
            for each word:
                key = sorted letters of the word
                append word to groups[key]
            return the buckets, key order
        """,
        time_complexity="O(n log n)", space_complexity="O(n)",
    ))

    # -- SET ----------------------------------------------------------------
    P.append(rune(
        id="sc-contains-duplicate", title="The Rune of Recognition",
        realm="fields_of_syntax", difficulty="GUIDED", family="dedupe",
        pattern="SET", scaffold_for="SET: membership",
        statement="""
            Return True if any value appears more than once in `nums`.

            `seen` is the memory of the scan. Two runes are missing: the question
            asked of that memory, and the act of adding to it.
        """,
        fn_name="contains_duplicate", params="nums", reference=_contains_duplicate,
        canonical="""
            def contains_duplicate(nums):
                seen = set()
                for value in nums:
                    if value in seen:
                        return True
                    seen.add(value)
                return False
        """,
        blanks=[("value in seen", "have we already walked past this exact value"),
                ("seen.add(value)", "record it, so a later copy is recognised")],
        visible=[("has one", [[1, 2, 3, 1]]), ("all distinct", [[1, 2, 3, 4]])],
        hidden=[("adjacent pair", [[5, 5]]), ("strings", [["a", "b", "a"]])],
        edges=[("empty", [[]]), ("single", [[7]])],
        failures=["Adding before checking, so every value collides with itself"],
        nudge="A set answers one question in constant time: have I got this already?",
        visual="Check, then add. That order is the whole problem.",
        pseudocode="""
            seen = empty set
            for each value:
                already in seen -> True
                add it
            -> False
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-set-overlap", title="The Twin Circles", realm="fields_of_syntax",
        difficulty="GUIDED", family="set_ops", pattern="SET",
        scaffold_for="SET: algebra",
        statement="""
            Return `[both, only_in_a]`: the values present in both `a` and `b`, and
            the values present in `a` but not in `b`. Both lists sorted.

            Python spells these two relationships with operators rather than loops.
            The sorting and the return shape are already written.
        """,
        fn_name="set_overlap", params="a, b", reference=_set_overlap,
        canonical="""
            def set_overlap(a, b):
                common = set(a) & set(b)
                only_a = set(a) - set(b)
                return [sorted(common), sorted(only_a)]
        """,
        blanks=[("set(a) & set(b)", "everything in a that is also in b"),
                ("set(a) - set(b)", "everything in a that b does not have")],
        visible=[("overlap", [[1, 2, 3], [2, 3, 4]]), ("disjoint", [[1], [2]])],
        hidden=[("identical", [[1, 2], [2, 1]]), ("duplicates in a", [[1, 1, 2], [2]])],
        edges=[("empty b", [[1, 2], []]), ("both empty", [[], []])],
        failures=["Using `|` (union) where `&` (intersection) was meant"],
        nudge="`&` is 'and'. `-` is 'take away'. `|` is 'either'.",
        visual="Two overlapping circles: the lens, and the left crescent.",
        pseudocode="""
            common = a AND b
            only_a = a MINUS b
            return both, sorted
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-dedupe-in-order", title="The First Sighting", realm="fields_of_syntax",
        difficulty="TUTORIAL", family="dedupe", pattern="SET",
        scaffold_for="SET: membership with order", secondary=["ARRAY"],
        prerequisites=["sc-contains-duplicate"],
        statement="""
            Return the items with later duplicates removed, keeping the order of
            first appearance.

            `set(items)` would deduplicate and destroy the order. So the set is used
            only to answer 'seen before?', while a separate list keeps the order.
            Both halves of that bargain are struck out.
        """,
        fn_name="dedupe", params="items", reference=_dedupe,
        canonical="""
            def dedupe(items):
                seen = set()
                out = []
                for item in items:
                    if item not in seen:
                        seen.add(item)
                        out.append(item)
                return out
        """,
        blanks=[("item not in seen", "this is the first time this item has appeared"),
                ("seen.add(item)", "remember it so the next copy is rejected")],
        visible=[("repeats", [[1, 2, 1, 3, 2]]), ("already unique", [[1, 2, 3]])],
        hidden=[("strings", [["a", "a", "b"]]), ("all identical", [[4, 4, 4]])],
        edges=[("empty", [[]]), ("single", [[9]])],
        failures=["Returning `list(set(items))`, which loses the order"],
        nudge="The set is the lookup. The list is the answer.",
        visual="Two structures, one loop, different jobs.",
        pseudocode="""
            seen = set(); out = []
            for each item:
                not seen -> mark seen, append to out
            return out
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    # -- SLIDING WINDOW -----------------------------------------------------
    P.append(rune(
        id="sc-window-fixed-sum", title="The Frame of Fixed Width",
        realm="sliding_window_marsh", difficulty="TUTORIAL", family="fixed_window",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: fixed width",
        secondary=["ARRAY"],
        statement="""
            Return the largest sum of any `k` consecutive values in `nums`, or 0 when
            `k` does not fit.

            The first window is summed up front. After that the window never gets
            re-added: it slides one step, and only two elements change. That single
            line is the difference between O(n) and O(n*k).
        """,
        fn_name="max_window_sum", params="nums, k", reference=_max_window_sum,
        canonical="""
            def max_window_sum(nums, k):
                if k <= 0 or k > len(nums):
                    return 0
                window = sum(nums[:k])
                best = window
                for right in range(k, len(nums)):
                    window += nums[right] - nums[right - k]
                    best = max(best, window)
                return best
        """,
        blanks=[("nums[right] - nums[right - k]",
                 "one element joins on the right; the one k steps back leaves on the left"),
                ("max(best, window)", "keep the better of the record and the current window")],
        visible=[("classic", [[2, 1, 5, 1, 3, 2], 3]), ("whole array", [[1, 2, 3], 3])],
        hidden=[("negatives", [[-1, -2, -3, -4], 2]), ("k of one", [[4, 9, 2], 1])],
        edges=[("k too large", [[1, 2], 5]), ("k zero", [[1, 2], 0]), ("empty", [[], 1])],
        failures=["Re-summing the slice each step, which is the O(n*k) version"],
        nudge="A window that slides does not need to be rebuilt.",
        visual="Right edge gains one element, left edge loses one. Net: two operations.",
        pseudocode="""
            window = sum of the first k
            for right from k to the end:
                window += entering element - leaving element
                best = max(best, window)
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    P.append(rune(
        id="sc-window-no-repeat", title="The Contracting Ward",
        realm="sliding_window_marsh", difficulty="EASY", family="window_distinct",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: shrink on violation",
        secondary=["SET", "STRING"], prerequisites=["sc-window-fixed-sum"],
        statement="""
            Return the length of the longest substring of `s` with no repeated
            character.

            The window is `s[left:right + 1]` and `seen` holds exactly its
            characters. `right` only ever moves forward. When the incoming character
            breaks the rule, the window contracts from the left until it is legal
            again. Three runes are missing: the violation test, the contraction, and
            the width.
        """,
        fn_name="longest_unique_window", params="s", reference=_longest_unique_window,
        canonical="""
            def longest_unique_window(s):
                seen = set()
                left = 0
                best = 0
                for right, ch in enumerate(s):
                    while ch in seen:
                        seen.remove(s[left])
                        left += 1
                    seen.add(ch)
                    best = max(best, right - left + 1)
                return best
        """,
        blanks=[("ch in seen",
                 "the window is illegal: the incoming character is already inside it"),
                ("seen.remove(s[left])",
                 "the leftmost character leaves the window as it contracts"),
                ("right - left + 1", "the width of the window right now")],
        visible=[("classic", ["abcabcbb"]), ("all same", ["bbbbb"])],
        hidden=[("mid restart", ["pwwkew"]), ("all distinct", ["abcdef"])],
        edges=[("empty", [""]), ("single", ["a"]), ("two same", ["aa"])],
        constraints=["0 <= len(s) <= 100000"],
        failures=["Resetting `left` to `right`, which throws away a legal prefix",
                  "Forgetting to remove from `seen` while moving `left`"],
        nudge="`left` never goes backwards. Neither does `right`. That is why it is linear.",
        visual="A rubber frame: it stretches right and is pulled in from the left.",
        pseudocode="""
            left = 0; seen = set()
            for right, ch in the string:
                while ch is already in the window:
                    drop s[left] from the window; left += 1
                add ch
                best = max(best, window width)
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-window-min-length", title="The Shortest Sufficient Span",
        realm="sliding_window_marsh", difficulty="EASY", family="window_sum",
        pattern="SLIDING_WINDOW", scaffold_for="SLIDING WINDOW: shrink while valid",
        secondary=["ARRAY"], prerequisites=["sc-window-no-repeat"],
        statement="""
            All values in `nums` are positive. Return the length of the shortest
            contiguous run whose sum is at least `target`, or 0 if none reaches it.

            This is the mirror of the usual window. Here the window shrinks while it
            is still *valid*, because the question asks for the shortest one that
            works, not the longest. The loop condition and the bookkeeping that goes
            with it are struck out.
        """,
        fn_name="min_window_length", params="nums, target", reference=_min_window_length,
        canonical="""
            def min_window_length(nums, target):
                left = 0
                total = 0
                best = len(nums) + 1
                for right, value in enumerate(nums):
                    total += value
                    while total >= target:
                        best = min(best, right - left + 1)
                        total -= nums[left]
                        left += 1
                return 0 if best > len(nums) else best
        """,
        blanks=[("total >= target",
                 "the window still satisfies the requirement, so it can afford to shrink"),
                ("total -= nums[left]",
                 "take the leaving element out of the running total before left moves")],
        visible=[("classic", [[2, 3, 1, 2, 4, 3], 7]), ("whole array", [[1, 1, 1, 1], 4])],
        hidden=[("one element does it", [[5, 1, 1], 5]), ("never reached", [[1, 1], 9])],
        edges=[("empty", [[], 3]), ("single hit", [[9], 9])],
        constraints=["every value in nums is positive"],
        failures=["Shrinking with `if` instead of `while`, which stops one step early",
                  "Recording the width after moving `left`"],
        nudge="Record the width before you shrink, not after.",
        visual="Grow until legal, then squeeze until it is not. Repeat.",
        pseudocode="""
            for right, value:
                total += value
                while total is still enough:
                    best = min(best, width)
                    total -= nums[left]; left += 1
            best never set -> 0
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    # -- TWO POINTER --------------------------------------------------------
    P.append(rune(
        id="sc-two-sum-sorted", title="The Converging Pass",
        realm="twin_pointer_pass", difficulty="GUIDED", family="sorted_pair",
        pattern="TWO_POINTER", scaffold_for="TWO POINTER: converging",
        secondary=["ARRAY"],
        statement="""
            `nums` is sorted ascending. Return the indices of the two values that add
            up to `target`.

            `left` starts at the smallest value and `right` at the largest. Because
            the list is sorted, the current sum tells you exactly which end is at
            fault: too small means the small end must rise; too large means the large
            end must fall. Two runes carry that decision.
        """,
        fn_name="two_sum_sorted", params="nums, target", reference=_two_sum_sorted,
        canonical="""
            def two_sum_sorted(nums, target):
                left = 0
                right = len(nums) - 1
                while left < right:
                    total = nums[left] + nums[right]
                    if total == target:
                        return [left, right]
                    if total < target:
                        left += 1
                    else:
                        right -= 1
                return []
        """,
        blanks=[("total < target", "the sum is too small to reach the target"),
                ("left += 1", "give up the smallest remaining value")],
        visible=[("classic", [[1, 3, 4, 6, 8], 10]), ("ends", [[2, 7, 11, 15], 17])],
        hidden=[("adjacent", [[1, 2], 3]), ("negatives", [[-5, -2, 0, 4], -2])],
        edges=[("no pair", [[1, 2, 3], 100]), ("empty", [[], 0])],
        constraints=["nums is sorted ascending", "at most one valid pair"],
        failures=["Moving both pointers at once, which skips valid pairs"],
        nudge="Sorted input means a wrong sum names its own culprit.",
        visual="The pair you want is somewhere between the two fingers. Never outside.",
        pseudocode="""
            left at the start, right at the end
            while they have not met:
                sum equals target -> answer
                sum too small -> left forward
                otherwise      -> right backward
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    P.append(rune(
        id="sc-palindrome-ends", title="The Mirror Gate", realm="twin_pointer_pass",
        difficulty="GUIDED", family="palindrome", pattern="TWO_POINTER",
        scaffold_for="TWO POINTER: mirrored ends", secondary=["STRING"],
        statement="""
            Return True when `s` reads the same forwards and backwards.

            Both pointers and both moves are already written. The only rune missing
            is the comparison that decides the answer.
        """,
        fn_name="is_palindrome", params="s", reference=_is_palindrome,
        canonical="""
            def is_palindrome(s):
                left = 0
                right = len(s) - 1
                while left < right:
                    if s[left] != s[right]:
                        return False
                    left += 1
                    right -= 1
                return True
        """,
        blanks=[("s[left] != s[right]", "the two mirrored characters disagree")],
        partial="""
            def is_palindrome(s):
                left = 0
                right = len(s) - 1
                while left < right:
                    if s[left] __BLANK__ s[right]:
                        return False
                    left += 1
                    right -= 1
                return True
        """,
        visible=[("palindrome", ["racecar"]), ("not", ["python"])],
        hidden=[("even length", ["abba"]), ("near miss", ["abca"])],
        edges=[("empty", [""]), ("single", ["x"])],
        failures=["Comparing `s[left] == s[right]` and returning False on a match"],
        nudge="You are proving a negative: find one mismatch and you are done.",
        visual="The loop stops when the fingers meet, which is why the middle is free.",
        pseudocode="""
            left at start, right at end
            while left < right:
                mismatch -> False
                step both inward
            -> True
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    P.append(rune(
        id="sc-reverse-two-pointer", title="The Turning of the Line",
        realm="twin_pointer_pass", difficulty="TUTORIAL", family="converging",
        pattern="TWO_POINTER", scaffold_for="TWO POINTER: in-place swap",
        secondary=["ARRAY"], prerequisites=["sc-palindrome-ends"],
        statement="""
            Return the items in reverse order, reversed by swapping ends rather than
            by slicing.

            `items[::-1]` is the Python answer and you already know it. This drill is
            about the mechanical version, because the same loop reverses a subrange,
            rotates an array, and shows up inside half the array questions asked in
            interviews.
        """,
        fn_name="reverse_list", params="items", reference=_reverse_list,
        canonical="""
            def reverse_list(items):
                out = list(items)
                left = 0
                right = len(out) - 1
                while left < right:
                    out[left], out[right] = out[right], out[left]
                    left += 1
                    right -= 1
                return out
        """,
        blanks=[("left < right", "keep going only while the two ends have not met"),
                ("out[left], out[right] = out[right], out[left]",
                 "exchange the two ends in one statement")],
        visible=[("odd length", [[1, 2, 3]]), ("even length", [[1, 2, 3, 4]])],
        hidden=[("strings", [["a", "b", "c"]]), ("two", [[1, 2]])],
        edges=[("empty", [[]]), ("single", [[5]])],
        failures=["Using `left <= right`, which swaps the middle element with itself",
                  "Swapping in two statements and clobbering the first value"],
        nudge="Python swaps in one line. Two lines needs a temporary.",
        visual="Every element moves exactly once. Half the loop, whole reversal.",
        pseudocode="""
            left at start, right at end
            while they have not met:
                swap them
                step both inward
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-remove-dups-sorted", title="The Slow Scribe", realm="twin_pointer_pass",
        difficulty="EASY", family="converging", pattern="TWO_POINTER",
        scaffold_for="TWO POINTER: fast read, slow write", secondary=["ARRAY"],
        prerequisites=["sc-reverse-two-pointer"],
        statement="""
            `nums` is sorted ascending. Remove the duplicates in place and return the
            list truncated to the kept values.

            Two indices moving at different speeds: `read` visits every element,
            `write` marks where the next kept value belongs. They are not a pair
            closing in — they are a reader running ahead of a scribe.
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
        blanks=[("nums[read] != nums[write - 1]",
                 "this value differs from the last value the scribe kept"),
                ("nums[write] = nums[read]", "copy it into the next free slot"),
                ("write += 1", "the scribe advances only when something was kept")],
        visible=[("classic", [[1, 1, 2, 2, 3]]), ("no duplicates", [[1, 2, 3]])],
        hidden=[("all identical", [[4, 4, 4, 4]]), ("pairs", [[1, 1, 2, 2]])],
        edges=[("empty", [[]]), ("single", [[7]])],
        constraints=["nums is sorted ascending"],
        failures=["Comparing against `nums[read - 1]` after it has been overwritten",
                  "Advancing `write` on every iteration"],
        nudge="Compare against what was last WRITTEN, not what was last read.",
        visual="The scribe lags behind the reader by exactly the number of duplicates seen.",
        pseudocode="""
            write = 1
            for read from 1 to the end:
                nums[read] differs from the last kept value:
                    nums[write] = nums[read]; write += 1
            return the first `write` values
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    # -- STACK --------------------------------------------------------------
    P.append(rune(
        id="sc-valid-parens", title="The Rune of Closure", realm="stack_queue_mines",
        difficulty="GUIDED", family="stack_matching", pattern="STACK",
        scaffold_for="STACK: matching pairs", secondary=["STRING"],
        statement="""
            Return True when every bracket in `s` closes correctly and in the right
            order.

            `pairs` maps each closer to the opener it demands. The rule is that a
            closer must answer the MOST RECENT unmatched opener, which is exactly
            what a stack remembers. Two runes are missing: what to do with an opener,
            and the test a closer must pass.
        """,
        fn_name="is_balanced", params="s", reference=_is_balanced,
        canonical="""
            def is_balanced(s):
                pairs = {")": "(", "]": "[", "}": "{"}
                stack = []
                for ch in s:
                    if ch not in pairs:
                        stack.append(ch)
                    elif not stack or stack.pop() != pairs[ch]:
                        return False
                return not stack
        """,
        blanks=[("stack.append(ch)",
                 "an opener: hold it until its partner arrives"),
                ("stack.pop() != pairs[ch]",
                 "the most recent unmatched opener is not the one this closer wants")],
        visible=[("nested", ["([{}])"]), ("crossed", ["([)]"])],
        hidden=[("sequential", ["()[]{}"]), ("unclosed", ["((("])],
        edges=[("empty", [""]), ("only a closer", [")"])],
        failures=["Counting brackets instead of matching them, so `([)]` passes",
                  "Forgetting the leftovers check on the final line"],
        nudge="Order matters, so a counter cannot do this. The most recent one wins.",
        visual="Every opener waits on the stack until its own closer arrives.",
        pseudocode="""
            for each character:
                opener -> push it
                closer -> the top must be its partner, else False
            stack empty at the end -> True
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-eval-rpn", title="The Postfix Oracle", realm="stack_queue_mines",
        difficulty="EASY", family="stack_eval", pattern="STACK",
        scaffold_for="STACK: evaluation", secondary=["SIMULATION"],
        prerequisites=["sc-valid-parens"],
        statement="""
            Evaluate a postfix expression given as tokens, where an operator acts on
            the two values before it. `["2", "3", "+"]` is 5.

            Operands are pushed; an operator pops two of them. The trap is that a
            stack gives them back in the opposite order to the one they were written
            in, which matters for every operator that is not commutative.
        """,
        fn_name="eval_rpn", params="tokens", reference=_eval_rpn,
        canonical="""
            def eval_rpn(tokens):
                stack = []
                for token in tokens:
                    if token in ("+", "-", "*"):
                        right = stack.pop()
                        left = stack.pop()
                        if token == "+":
                            stack.append(left + right)
                        elif token == "-":
                            stack.append(left - right)
                        else:
                            stack.append(left * right)
                    else:
                        stack.append(int(token))
                return stack[0]
        """,
        blanks=[("left - right",
                 "subtraction is not commutative — which operand came off the stack second?"),
                ("int(token)", "not an operator, so it is a number: push its value")],
        visible=[("add", [["2", "3", "+"]]), ("subtract", [["5", "2", "-"]])],
        hidden=[("nested", [["2", "3", "+", "4", "*"]]),
                ("negative result", [["3", "9", "-"]])],
        edges=[("single value", [["7"]]), ("negative literal", [["-4", "2", "*"]])],
        failures=["Popping the operands in written order, which reverses subtraction",
                  "Leaving the tokens as strings, so `+` concatenates"],
        nudge="The last thing pushed is the right-hand operand.",
        visual="Two pops, one push. The stack shrinks by one per operator.",
        pseudocode="""
            for each token:
                operator -> pop right, pop left, push the result
                otherwise -> push the number
            the single remaining value is the answer
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-days-until-warmer", title="The Waiting Stones",
        realm="stack_queue_mines", difficulty="EASY", family="monotonic_stack",
        pattern="STACK", scaffold_for="STACK: monotonic", secondary=["ARRAY"],
        prerequisites=["sc-eval-rpn"],
        statement="""
            For each day, return how many days you must wait for a warmer one, or 0
            if none comes.

            The stack holds the INDICES of days still waiting, and it is kept
            decreasing in temperature. When today beats the day on top, that day's
            wait is over and it can be resolved and discarded. Two runes carry that.
        """,
        fn_name="days_until_warmer", params="temps", reference=_days_until_warmer,
        canonical="""
            def days_until_warmer(temps):
                out = [0] * len(temps)
                stack = []
                for i, temp in enumerate(temps):
                    while stack and temps[stack[-1]] < temp:
                        j = stack.pop()
                        out[j] = i - j
                    stack.append(i)
                return out
        """,
        blanks=[("temps[stack[-1]] < temp",
                 "today is warmer than the day still waiting on top of the stack"),
                ("i - j", "how many days that waiting day had to wait")],
        visible=[("classic", [[73, 74, 75, 71, 69, 72, 76, 73]]),
                 ("rising", [[1, 2, 3]])],
        hidden=[("falling", [[3, 2, 1]]), ("flat", [[5, 5, 5]])],
        edges=[("empty", [[]]), ("single", [[40]])],
        failures=["Storing temperatures on the stack instead of indices, losing the distance",
                  "Using `<=`, which resolves a day against an equal temperature"],
        nudge="Store indices. The answer is a distance, and only indices carry distance.",
        visual="Each day is pushed once and popped at most once: linear, despite the while.",
        pseudocode="""
            for each day i:
                while the day on top is colder than today:
                    pop it; its answer is i - that index
                push i
            anything still on the stack keeps its 0
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    # -- QUEUE --------------------------------------------------------------
    P.append(rune(
        id="sc-recent-pings", title="The Expiring Ledger", realm="stack_queue_mines",
        difficulty="TUTORIAL", family="queue_window", pattern="QUEUE",
        scaffold_for="QUEUE: expiry from the front", secondary=["SLIDING_WINDOW"],
        statement="""
            `times` is a non-decreasing list of timestamps. For each one, return how
            many timestamps fall within the last `window` units, counting the current
            one.

            A deque is used because arrivals happen at one end and expiries at the
            other. The two struck runes are the expiry test and the expiry itself.
        """,
        fn_name="recent_pings", params="times, window", reference=_recent_pings,
        canonical="""
            def recent_pings(times, window):
                from collections import deque
                pending = deque()
                out = []
                for t in times:
                    pending.append(t)
                    while pending[0] <= t - window:
                        pending.popleft()
                    out.append(len(pending))
                return out
        """,
        blanks=[("pending[0] <= t - window",
                 "the oldest timestamp has fallen out of the window ending at t"),
                ("pending.popleft()", "discard from the OLD end, not the new one")],
        visible=[("spread out", [[1, 100, 3001, 3002], 3000]),
                 ("all inside", [[1, 2, 3], 10])],
        hidden=[("all expired", [[1, 50, 100], 10]), ("repeats", [[5, 5, 5], 3])],
        edges=[("empty", [[], 5]), ("single", [[1], 1])],
        constraints=["times is non-decreasing"],
        failures=["Using `.pop()` and expiring the newest entry instead of the oldest"],
        nudge="`.append` adds at the right. `.popleft` removes from the left.",
        visual="Arrivals at the back, expiries at the front. Nothing moves in the middle.",
        pseudocode="""
            for each timestamp t:
                append t
                while the oldest is too old: drop it
                record how many remain
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-last-survivor", title="The Circle of Passing",
        realm="stack_queue_mines", difficulty="EASY", family="stack_simulation",
        pattern="QUEUE", scaffold_for="QUEUE: rotation", secondary=["SIMULATION"],
        prerequisites=["sc-recent-pings"],
        statement="""
            Names stand in a circle. Counting from the front, every `step`-th name is
            removed, and counting resumes from the next one. Return the last name
            standing.

            The circle is modelled as a deque: sending the front to the back is what
            makes a straight line behave like a ring. Two runes are missing — how
            many are spared per round, and what happens to a spared name.
        """,
        fn_name="last_survivor", params="names, step", reference=_last_survivor,
        canonical="""
            def last_survivor(names, step):
                from collections import deque
                circle = deque(names)
                while len(circle) > 1:
                    for _ in range(step - 1):
                        front = circle.popleft()
                        circle.append(front)
                    circle.popleft()
                return circle[0]
        """,
        blanks=[("range(step - 1)",
                 "how many names are passed over before one is removed"),
                ("circle.append(front)", "a spared name rejoins the circle at the back")],
        visible=[("classic", [["a", "b", "c", "d", "e"], 3]),
                 ("every one counts", [["a", "b", "c"], 1])],
        hidden=[("two names", [["x", "y"], 2]), ("step beyond size", [["a", "b", "c"], 5])],
        edges=[("single name", [["solo"], 4])],
        constraints=["1 <= step", "names is non-empty"],
        failures=["Removing every step-th name counting from one, an off-by-one"],
        nudge="If every third is removed, exactly two are spared first.",
        visual="Front to back, front to back, then one falls. Repeat.",
        pseudocode="""
            while more than one remains:
                move (step - 1) names from front to back
                remove the front
            the survivor is what is left
        """,
        time_complexity="O(n * step)", space_complexity="O(n)",
    ))

    # -- BFS ----------------------------------------------------------------
    P.append(rune(
        id="sc-bfs-grid-shortest", title="The Expanding Ring", realm="graph_wastes",
        difficulty="EASY", family="grid_bfs", pattern="BFS",
        scaffold_for="BFS: shortest path on a grid", secondary=["QUEUE", "MATRIX"],
        statement="""
            `grid` holds 0 for open and 1 for blocked. Return the number of cells on
            the shortest path from the top-left to the bottom-right moving in four
            directions, or -1 if none exists.

            BFS is correct here because it explores in rings of equal distance, so
            the first time the exit is dequeued the distance is already minimal. Two
            runes are missing, and one of them is the reason BFS stays linear.
        """,
        fn_name="shortest_path", params="grid", reference=_shortest_path,
        canonical="""
            def shortest_path(grid):
                from collections import deque
                if not grid or grid[0][0] == 1 or grid[-1][-1] == 1:
                    return -1
                rows, cols = len(grid), len(grid[0])
                frontier = deque([(0, 0, 1)])
                visited = {(0, 0)}
                while frontier:
                    r, c, dist = frontier.popleft()
                    if r == rows - 1 and c == cols - 1:
                        return dist
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr, nc = r + dr, c + dc
                        if not (0 <= nr < rows and 0 <= nc < cols):
                            continue
                        if grid[nr][nc] == 1 or (nr, nc) in visited:
                            continue
                        visited.add((nr, nc))
                        frontier.append((nr, nc, dist + 1))
                return -1
        """,
        blanks=[("visited.add((nr, nc))",
                 "claim the cell when it is QUEUED, not when it is dequeued, "
                 "or it enters the frontier many times"),
                ("frontier.append((nr, nc, dist + 1))",
                 "queue it, one step further than the cell it came from")],
        visible=[("open grid", [[[0, 0], [0, 0]]]),
                 ("wall in the way", [[[0, 1], [1, 0]]])],
        hidden=[("unreachable exit beyond a cycle", [[[0, 0, 1], [0, 0, 1], [1, 1, 0]]]),
                ("detour", [[[0, 0, 0], [1, 1, 0], [0, 0, 0]]]),
                ("single cell", [[[0]]])],
        edges=[("blocked start", [[[1, 0], [0, 0]]]), ("empty grid", [[]])],
        failures=["Marking visited on dequeue, which lets duplicates pile up",
                  "Using a list with `.pop(0)` and turning the queue into O(n) per step"],
        nudge="Mark on enqueue. Every cell should enter the frontier exactly once.",
        visual="All of distance 1, then all of distance 2. Never out of order.",
        pseudocode="""
            frontier = deque of (start, distance 1); visited = {start}
            while frontier:
                pop the oldest
                is it the exit -> its distance
                for each open, unvisited neighbour:
                    mark visited, push with distance + 1
            -> -1
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-level-order", title="The Canopy by Layers", difficulty="EASY",
        family="tree_bfs", pattern="BFS", scaffold_for="BFS: level by level",
        secondary=["TREE", "QUEUE"], prerequisites=["sc-bfs-grid-shortest"], **tree,
        statement="""
            Return the node values level by level, as a list of lists.

            """ + TREE_SHAPE + """

            A plain BFS would give one flat list. What separates the levels is
            measuring the frontier BEFORE draining it: whatever is in the queue at
            the top of a round is exactly one level. Two runes carry that idea.
        """,
        fn_name="level_order", params="root", reference=tree_ref(_level_order),
        canonical="""
            def level_order(root):
                from collections import deque
                if root is None:
                    return []
                out = []
                frontier = deque([root])
                while frontier:
                    level = []
                    for _ in range(len(frontier)):
                        node = frontier.popleft()
                        level.append(node.val)
                        if node.left is not None:
                            frontier.append(node.left)
                        if node.right is not None:
                            frontier.append(node.right)
                    out.append(level)
                return out
        """,
        blanks=[("range(len(frontier))",
                 "snapshot the size first: exactly this many nodes form the current level"),
                ("frontier.append(node.left)",
                 "the left child belongs to the NEXT level, so it goes to the back")],
        examples=[{"input": "a root of 3 with children 9 and 20, and 20 has children 15 and 7",
                   "output": "[[3], [9, 20], [15, 7]]"},
                  {"input": "a single node holding 1", "output": "[[1]]"}],
        visible=[("classic", [SAMPLE]), ("single", [[1]])],
        hidden=[("left spine", [SPINE]), ("balanced", [BST])],
        edges=[("empty", [[]])],
        failures=["Appending children inside the same level list",
                  "Reading `len(frontier)` inside the loop, after it has already changed"],
        nudge="The queue length at the start of the round IS the width of the level.",
        visual="Drain exactly n nodes; whatever they pushed becomes the next round.",
        pseudocode="""
            frontier = deque([root])
            while frontier:
                n = current frontier size
                drain exactly n nodes into one level, pushing their children
                append the level
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    # -- DFS ----------------------------------------------------------------
    P.append(rune(
        id="sc-count-islands", title="The Sinking of the Isles", realm="graph_wastes",
        difficulty="EASY", family="grid_traverse", pattern="DFS",
        scaffold_for="DFS: flood fill", secondary=["MATRIX", "RECURSION"],
        statement="""
            `grid` holds 1 for land and 0 for water. Return the number of islands,
            where an island is land connected in four directions.

            `sink` floods one island, turning all of its land to water so it can
            never be counted twice. The outer loop finds islands that have not been
            sunk yet. Two runes are missing, and forgetting the first of them makes
            the recursion run forever.
        """,
        fn_name="count_islands", params="grid", reference=_count_islands,
        canonical="""
            def count_islands(grid):
                if not grid:
                    return 0
                rows, cols = len(grid), len(grid[0])

                def sink(r, c):
                    if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] != 1:
                        return
                    grid[r][c] = 0
                    sink(r + 1, c)
                    sink(r - 1, c)
                    sink(r, c + 1)
                    sink(r, c - 1)

                total = 0
                for r in range(rows):
                    for c in range(cols):
                        if grid[r][c] == 1:
                            total += 1
                            sink(r, c)
                return total
        """,
        blanks=[("grid[r][c] = 0",
                 "mark this cell visited BEFORE recursing, or the four calls bounce forever"),
                ("total += 1",
                 "reaching un-sunk land in the outer loop means exactly one new island")],
        visible=[("two islands", [[[1, 1, 0], [0, 0, 0], [0, 1, 1]]]),
                 ("all water", [[[0, 0], [0, 0]]])],
        hidden=[("one blob", [[[1, 1], [1, 1]]]),
                ("diagonal is not connected", [[[1, 0], [0, 1]]])],
        edges=[("empty grid", [[]]), ("single land", [[[1]]])],
        failures=["Sinking after the recursive calls, which never terminates",
                  "Treating diagonals as connected"],
        nudge="The base case is the boundary check plus 'this is not land'.",
        visual="Each call either returns immediately or claims one cell. Linear in cells.",
        pseudocode="""
            for every cell:
                land -> count one island, then flood it away
            flood(r, c):
                out of bounds or not land -> stop
                turn it to water
                flood all four neighbours
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-reachable-nodes", title="The Unwinding Path", realm="graph_wastes",
        difficulty="EASY", family="graph_traverse", pattern="DFS",
        scaffold_for="DFS: visited set", secondary=["SET", "RECURSION"],
        prerequisites=["sc-count-islands"],
        statement="""
            `graph` maps a node to its list of neighbours. Return every node
            reachable from `start`, sorted, including `start` itself.

            Unlike the grid, there is nothing to overwrite here, so the visited set
            IS the memory. Without it any cycle in the graph spins forever. Both
            runes concern that set.
        """,
        fn_name="reachable", params="graph, start", reference=_reachable,
        canonical="""
            def reachable(graph, start):
                visited = set()

                def walk(node):
                    if node in visited:
                        return
                    visited.add(node)
                    for neighbour in graph.get(node, []):
                        walk(neighbour)

                walk(start)
                return sorted(visited)
        """,
        blanks=[("node in visited",
                 "we have already been here, so this branch has nothing new to offer"),
                ("visited.add(node)",
                 "claim the node before descending, not after")],
        visible=[("chain", [{"a": ["b"], "b": ["c"], "c": []}, "a"]),
                 ("cycle", [{"a": ["b"], "b": ["a"]}, "a"])],
        hidden=[("branching", [{"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}, "a"]),
                ("isolated island", [{"a": [], "b": ["c"], "c": []}, "b"])],
        edges=[("unknown start", [{}, "z"]), ("self loop", [{"a": ["a"]}, "a"])],
        failures=["Marking visited after the calls, which never terminates on a cycle",
                  "Indexing `graph[node]` and raising KeyError on a node with no entry"],
        nudge="A cycle is not an error. It is the reason the visited set exists.",
        visual="Commit to one branch all the way down, then unwind and take the next.",
        pseudocode="""
            walk(node):
                already visited -> return
                mark visited
                walk each neighbour
            walk(start); answer is the visited set, sorted
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    # -- TREE RECURSION -----------------------------------------------------
    P.append(rune(
        id="sc-tree-max-depth", title="The Measure of the Grove", difficulty="GUIDED",
        family="tree_traverse", pattern="TREE", scaffold_for="TREE RECURSION",
        secondary=["RECURSION", "DFS"], **tree,
        statement="""
            Return the number of nodes on the longest root-to-leaf path.

            """ + TREE_SHAPE + """

            Every tree recursion has the same two parts and both are struck out
            here: what an empty tree answers, and how a node combines the answers
            its two children give back. You never trace the whole tree by hand — you
            trust the smaller call.
        """,
        fn_name="max_depth", params="root", reference=tree_ref(_max_depth),
        canonical="""
            def max_depth(root):
                if root is None:
                    return 0
                return 1 + max(max_depth(root.left), max_depth(root.right))
        """,
        blanks=[("return 0",
                 "the base case: what an absent subtree contributes"),
                ("1 + max(max_depth(root.left), max_depth(root.right))",
                 "this node, plus the deeper of the two answers below it")],
        examples=[{"input": "a root of 3 with children 9 and 20, and 20 has children 15 and 7",
                   "output": "3"},
                  {"input": "a single node holding 1", "output": "1"}],
        visible=[("classic", [SAMPLE]), ("single", [[1]])],
        hidden=[("left spine", [SPINE]), ("balanced", [BST])],
        edges=[("empty", [[]])],
        failures=["Returning None from the base case, which breaks the `max`",
                  "Adding the two depths instead of taking the larger"],
        nudge="Ask what a node needs from its children, not how the whole tree looks.",
        visual="Depth flows upward: each node adds one to the best report below it.",
        pseudocode="""
            empty -> 0
            otherwise -> 1 + max(depth of left, depth of right)
        """,
        time_complexity="O(n)", space_complexity="O(h)",
    ))

    P.append(rune(
        id="sc-tree-invert", title="The Mirrored Canopy", difficulty="TUTORIAL",
        family="tree_traverse", pattern="TREE",
        scaffold_for="TREE RECURSION: rebuilding", secondary=["RECURSION"],
        prerequisites=["sc-tree-max-depth"], result_adapter="tree", **tree,
        statement="""
            Mirror the tree left-to-right and return the new root.

            """ + TREE_SHAPE + """

            The base case and the return are written. The single missing rune is the
            line that does the work, and the trap inside it is that both children
            have to be replaced at once — assign one first and the other is already
            gone.
        """,
        fn_name="invert_tree", params="root",
        reference=tree_ref(_invert_tree, returns_tree=True),
        canonical="""
            def invert_tree(root):
                if root is None:
                    return None
                root.left, root.right = invert_tree(root.right), invert_tree(root.left)
                return root
        """,
        blanks=[("invert_tree(root.right), invert_tree(root.left)",
                 "each side becomes the mirrored form of the OTHER side")],
        partial="""
            def invert_tree(root):
                if root is None:
                    return None
                root.left, root.right = invert_tree(__BLANK__), invert_tree(__BLANK__)
                return root
        """,
        examples=[{"input": "a root of 4 with children 2 and 7",
                   "output": "the same tree with 7 on the left and 2 on the right"},
                  {"input": "an empty tree", "output": "an empty tree"}],
        visible=[("classic", [[4, 2, 7, 1, 3, 6, 9]]), ("single", [[1]])],
        hidden=[("left spine", [SPINE]), ("balanced", [BST])],
        edges=[("empty", [[]])],
        failures=["Assigning `root.left` first, which destroys it before the second read"],
        nudge="Python evaluates the whole right-hand side before assigning anything.",
        visual="Every node swaps its two children, all the way down.",
        pseudocode="""
            empty -> nothing
            swap the two inverted subtrees onto this node
            return this node
        """,
        time_complexity="O(n)", space_complexity="O(h)",
    ))

    P.append(rune(
        id="sc-bst-contains", title="The Ordered Grove", difficulty="EASY",
        family="bst", pattern="TREE", scaffold_for="TREE: binary search on a tree",
        secondary=["BINARY_SEARCH"], prerequisites=["sc-tree-max-depth"], **tree,
        statement="""
            `root` is a binary SEARCH tree: everything in a node's left subtree is
            smaller than it, everything on the right is larger. Return True when
            `target` is in the tree.

            """ + TREE_SHAPE + """

            No recursion here — a BST search is a walk down a single path, discarding
            half the remaining tree at each node. The two struck runes are that
            decision.
        """,
        fn_name="bst_contains", params="root, target", reference=tree_ref(_bst_contains),
        canonical="""
            def bst_contains(root, target):
                node = root
                while node is not None:
                    if node.val == target:
                        return True
                    if target < node.val:
                        node = node.left
                    else:
                        node = node.right
                return False
        """,
        blanks=[("target < node.val",
                 "the target is smaller than this node, so only one side can hold it"),
                ("node = node.right", "otherwise, descend the other way")],
        examples=[{"input": "the BST [8, 4, 12, 2, 6, 10, 14], target 6", "output": "True"},
                  {"input": "the BST [8, 4, 12, 2, 6, 10, 14], target 7", "output": "False"}],
        visible=[("present", [BST, 6]), ("absent", [BST, 7])],
        hidden=[("root", [BST, 8]), ("deepest right", [BST, 14])],
        edges=[("empty", [[], 1]), ("single miss", [[5], 9])],
        constraints=["the tree satisfies the binary-search-tree ordering"],
        failures=["Searching both subtrees, which throws away the ordering and costs O(n)"],
        nudge="The ordering is a promise. Believe it and never look at the other side.",
        visual="One path from root to leaf. Height, not size.",
        pseudocode="""
            node = root
            while node exists:
                equal -> True
                target smaller -> go left
                otherwise      -> go right
            -> False
        """,
        time_complexity="O(log n)", space_complexity="O(1)",
    ))

    # -- RECURSION ----------------------------------------------------------
    P.append(rune(
        id="sc-factorial-base", title="The Descending Rune", realm="recursive_forest",
        difficulty="GUIDED", family="recursion_basics", pattern="RECURSION",
        scaffold_for="RECURSION: base case and shrink",
        statement="""
            Return `n!`, the product of every integer from 1 to `n`. `0!` is 1.

            Two lines, two ideas, both struck out: the answer that needs no
            recursion, and the step that reduces the problem to a strictly smaller
            one. Get the second without the first and it never stops.
        """,
        fn_name="factorial", params="n", reference=_factorial,
        canonical="""
            def factorial(n):
                if n <= 1:
                    return 1
                return n * factorial(n - 1)
        """,
        blanks=[("return 1", "the smallest case, answered without recursing"),
                ("n * factorial(n - 1)",
                 "this number times the answer for a strictly smaller input")],
        visible=[("five", [5]), ("zero", [0])],
        hidden=[("one", [1]), ("ten", [10])],
        edges=[("two", [2]), ("twenty", [20])],
        constraints=["0 <= n <= 900"],
        failures=["Recursing on `n` instead of `n - 1`, so the input never shrinks",
                  "Returning 0 from the base case, which zeroes the whole product"],
        nudge="Every recursion needs a floor and a step toward it.",
        visual="factorial(5) waits on factorial(4) waits on factorial(3) ... down to 1.",
        pseudocode="""
            n <= 1 -> 1
            otherwise -> n * factorial(n - 1)
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-fib-memo", title="The Twice-Told Seed", realm="recursive_forest",
        difficulty="EASY", family="dp_linear", pattern="RECURSION",
        scaffold_for="RECURSION: memoisation", secondary=["DP"],
        prerequisites=["sc-factorial-base"],
        statement="""
            Return the nth Fibonacci number, with `fib(0) == 0` and `fib(1) == 1`.

            The naive recursion is correct and unusably slow, because it recomputes
            the same subproblem an exponential number of times. `memo` fixes that,
            and the two struck runes are the entire fix: check before computing,
            record after.
        """,
        fn_name="fib", params="n", reference=_fib,
        canonical="""
            def fib(n):
                memo = {}

                def go(k):
                    if k < 2:
                        return k
                    if k in memo:
                        return memo[k]
                    memo[k] = go(k - 1) + go(k - 2)
                    return memo[k]

                return go(n)
        """,
        blanks=[("k in memo", "this subproblem has already been solved once"),
                ("memo[k] = go(k - 1) + go(k - 2)",
                 "solve it from the two smaller answers, and record it before returning")],
        visible=[("tenth", [10]), ("base", [1])],
        hidden=[("zero", [0]), ("thirtieth", [30])],
        edges=[("two", [2]), ("deep", [120])],
        constraints=["0 <= n <= 400"],
        failures=["Checking the memo after computing, which saves nothing",
                  "Sharing one memo across calls with different meanings"],
        nudge="Same call, same answer, every time. So never make it twice.",
        visual="Without the memo the call tree doubles at every level. With it, it is a line.",
        pseudocode="""
            go(k):
                k < 2 -> k
                already in memo -> the stored answer
                compute from go(k-1) + go(k-2), store, return
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    # -- BINARY SEARCH ------------------------------------------------------
    P.append(rune(
        id="sc-binary-search-mid", title="The Halving Rune", realm="complexity_tower",
        difficulty="GUIDED", family="binary_search", pattern="BINARY_SEARCH",
        scaffold_for="BINARY SEARCH", secondary=["ARRAY"],
        statement="""
            `nums` is sorted ascending. Return the index of `target`, or -1.

            `lo` and `hi` bound the part of the list still worth looking at. Three
            runes are missing: where the middle is, and what each comparison does to
            the bounds. Every one of them must strictly shrink the range, or the loop
            never ends.
        """,
        fn_name="binary_search", params="nums, target", reference=_binary_search,
        canonical="""
            def binary_search(nums, target):
                lo = 0
                hi = len(nums) - 1
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if nums[mid] == target:
                        return mid
                    if nums[mid] < target:
                        lo = mid + 1
                    else:
                        hi = mid - 1
                return -1
        """,
        blanks=[("(lo + hi) // 2", "the middle of the range still under consideration"),
                ("lo = mid + 1",
                 "the middle was too small, so discard it and everything left of it"),
                ("hi = mid - 1", "the middle was too large: discard it and everything right")],
        visible=[("found", [[1, 3, 5, 7, 9], 7]), ("absent", [[1, 3, 5, 7, 9], 4])],
        hidden=[("first", [[1, 3, 5], 1]), ("last", [[1, 3, 5], 5])],
        edges=[("empty", [[], 1]), ("single hit", [[2], 2]), ("single miss", [[2], 3])],
        constraints=["nums is sorted ascending and has no duplicates"],
        failures=["Using `mid` instead of `mid + 1` / `mid - 1`, which loops forever",
                  "Writing `while lo < hi` with an inclusive `hi`, missing the last element"],
        nudge="Inclusive bounds need `<=` and need `mid` itself excluded when it fails.",
        visual="Half the candidates vanish per comparison. Twenty steps cover a million.",
        pseudocode="""
            lo = 0; hi = last index
            while lo <= hi:
                mid = midpoint
                hit -> mid
                too small -> lo = mid + 1
                too large -> hi = mid - 1
            -> -1
        """,
        time_complexity="O(log n)", space_complexity="O(1)",
    ))

    P.append(rune(
        id="sc-binary-search-leftmost", title="The Boundary Rune",
        realm="complexity_tower", difficulty="EASY", family="binary_search",
        pattern="BINARY_SEARCH", scaffold_for="BINARY SEARCH: first index that qualifies",
        secondary=["ARRAY"], prerequisites=["sc-binary-search-mid"],
        statement="""
            `nums` is sorted ascending. Return the index of the first value that is
            at least `target`, or `len(nums)` if every value is smaller.

            This variant does not look for an exact hit, so it never returns from
            inside the loop — it narrows until one candidate remains. That forces
            half-open bounds, and the two struck runes are where that shows.
        """,
        fn_name="first_at_least", params="nums, target", reference=_first_at_least,
        canonical="""
            def first_at_least(nums, target):
                lo = 0
                hi = len(nums)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if nums[mid] < target:
                        lo = mid + 1
                    else:
                        hi = mid
                return lo
        """,
        blanks=[("hi = len(nums)",
                 "the range is half-open: hi sits one PAST the last index, so "
                 "'no value qualifies' is representable"),
                ("hi = mid",
                 "mid might itself be the answer, so it is kept rather than discarded")],
        visible=[("middle", [[1, 3, 5, 7], 4]), ("exact", [[1, 3, 5, 7], 5])],
        hidden=[("before all", [[2, 4, 6], 1]), ("after all", [[2, 4, 6], 9])],
        edges=[("empty", [[], 3]), ("duplicates", [[2, 2, 2], 2])],
        constraints=["nums is sorted ascending"],
        failures=["Writing `hi = mid - 1` and stepping past the answer",
                  "Returning -1 when nothing qualifies, instead of len(nums)"],
        nudge="If mid could be the answer, it must stay inside the range.",
        visual="The range shrinks to width zero, and `lo` lands on the boundary.",
        pseudocode="""
            lo = 0; hi = len(nums)
            while lo < hi:
                mid = midpoint
                too small -> lo = mid + 1
                otherwise -> hi = mid
            -> lo
        """,
        time_complexity="O(log n)", space_complexity="O(1)",
    ))

    # -- PREFIX SUM ---------------------------------------------------------
    P.append(rune(
        id="sc-range-sums", title="The Ledger of Totals", realm="array_caverns",
        difficulty="EASY", family="prefix_sum", pattern="PREFIX_SUM",
        scaffold_for="PREFIX SUM", secondary=["ARRAY"],
        statement="""
            Answer every `[lo, hi]` query with the sum of `nums[lo..hi]` inclusive.

            Summing each slice is O(n) per query. Instead `prefix[i]` holds the total
            of the first `i` values, with a deliberate leading zero so that no query
            needs a special case. The build step and the query step are both struck
            out, and the second is where the off-by-one lives.
        """,
        fn_name="range_sums", params="nums, queries", reference=_range_sums,
        canonical="""
            def range_sums(nums, queries):
                prefix = [0]
                for value in nums:
                    prefix.append(prefix[-1] + value)
                return [prefix[hi + 1] - prefix[lo] for lo, hi in queries]
        """,
        blanks=[("prefix[-1] + value",
                 "each entry is the previous total plus this value"),
                ("prefix[hi + 1] - prefix[lo]",
                 "a range total is the difference of two prefix totals — mind which "
                 "index is inclusive")],
        visible=[("two queries", [[1, 2, 3, 4], [[0, 1], [1, 3]]]),
                 ("whole array", [[5, 5], [[0, 1]]])],
        hidden=[("single elements", [[3, 1, 4], [[0, 0], [2, 2]]]),
                ("negatives", [[-1, 2, -3], [[0, 2]]])],
        edges=[("no queries", [[1, 2, 3], []]), ("empty nums", [[], []])],
        constraints=["0 <= lo <= hi < len(nums)"],
        failures=["Using `prefix[hi] - prefix[lo]`, which drops the last element",
                  "Omitting the leading zero and special-casing `lo == 0`"],
        nudge="The leading zero exists so that `lo == 0` is not a special case.",
        visual="prefix[hi+1] counts everything up to hi; prefix[lo] removes the head.",
        pseudocode="""
            prefix = [0]
            for each value: prefix.append(last total + value)
            each query -> prefix[hi + 1] - prefix[lo]
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-subarray-sum-k", title="The Vanishing Difference", realm="array_caverns",
        difficulty="EASY", family="prefix_sum", pattern="PREFIX_SUM",
        scaffold_for="PREFIX SUM: with a hash map", secondary=["HASH_MAP"],
        prerequisites=["sc-range-sums"],
        statement="""
            Return how many contiguous subarrays of `nums` sum to exactly `k`.
            Values may be negative, so a sliding window will not work.

            A subarray sums to `k` exactly when two prefix totals differ by `k`, so
            the count becomes a lookup: how many earlier prefixes equal `total - k`.
            Three runes are missing, and the first of them is the one everyone
            forgets.
        """,
        fn_name="subarray_sum_count", params="nums, k", reference=_subarray_sum_count,
        canonical="""
            def subarray_sum_count(nums, k):
                counts = {0: 1}
                total = 0
                found = 0
                for value in nums:
                    total += value
                    found += counts.get(total - k, 0)
                    counts[total] = counts.get(total, 0) + 1
                return found
        """,
        blanks=[("{0: 1}",
                 "the empty prefix sums to zero and has been seen once — without it, "
                 "every subarray starting at index 0 is missed"),
                ("counts.get(total - k, 0)",
                 "how many earlier prefixes leave exactly k between there and here"),
                ("counts.get(total, 0) + 1", "record this prefix for later queries")],
        visible=[("classic", [[1, 1, 1], 2]), ("with zero", [[1, 2, 3], 3])],
        hidden=[("negatives", [[1, -1, 0], 0]), ("none", [[1, 2, 3], 100])],
        edges=[("empty", [[], 0]), ("single hit", [[5], 5])],
        perf=[("long run", [[1] * 1200, 3])],
        failures=["Starting with an empty dict, which misses prefixes from index 0",
                  "Recording the prefix before querying, which counts the empty subarray"],
        nudge="Query first, then record. Otherwise a k of 0 counts itself.",
        visual="total - previous_total == k is the same statement as 'that range sums to k'.",
        pseudocode="""
            counts = {0: 1}; total = 0; found = 0
            for each value:
                total += value
                found += counts.get(total - k, 0)
                counts[total] += 1
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    # -- DP -----------------------------------------------------------------
    P.append(rune(
        id="sc-climb-stairs", title="The Rune of Two Ways", realm="dp_ruins",
        difficulty="GUIDED", family="dp_linear", pattern="DP",
        scaffold_for="DYNAMIC PROGRAMMING: the recurrence",
        statement="""
            You climb one or two steps at a time. Return how many distinct ways there
            are to reach step `n`.

            The base cases and the loop are written. The single missing rune is the
            recurrence, and it is the whole problem: to be standing on a step you
            must have arrived from exactly one of two places.
        """,
        fn_name="climb_stairs", params="n", reference=_climb_stairs,
        canonical="""
            def climb_stairs(n):
                if n <= 2:
                    return max(n, 1)
                prev, cur = 1, 2
                for _ in range(3, n + 1):
                    prev, cur = cur, prev + cur
                return cur
        """,
        blanks=[("cur, prev + cur",
                 "shift the window forward: the new total is the sum of the two before it")],
        partial="""
            def climb_stairs(n):
                if n <= 2:
                    return max(n, 1)
                prev, cur = 1, 2
                for _ in range(3, n + 1):
                    prev, cur = cur, __BLANK__ + __BLANK__
                return cur
        """,
        visible=[("three steps", [3]), ("five steps", [5])],
        hidden=[("one", [1]), ("ten", [10])],
        edges=[("zero", [0]), ("two", [2]), ("forty", [40])],
        constraints=["0 <= n <= 40"],
        failures=["Assigning `prev` first, which loses the value `cur` still needs",
                  "Multiplying the two, which counts sequences that do not exist"],
        nudge="Ways to reach step n = ways to reach n-1 plus ways to reach n-2.",
        visual="Only two rows of the table are ever needed, so keep two variables.",
        pseudocode="""
            n <= 2 -> n (and 0 -> 1)
            prev, cur = 1, 2
            repeat n - 2 times: prev, cur = cur, prev + cur
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    P.append(rune(
        id="sc-max-loot", title="The Untouched Vault", realm="dp_ruins",
        difficulty="EASY", family="dp_linear", pattern="DP",
        scaffold_for="DYNAMIC PROGRAMMING: take or skip",
        prerequisites=["sc-climb-stairs"],
        statement="""
            You may take values from `values` but never two that are adjacent. Return
            the largest total you can take.

            At each position there are exactly two options, and the whole method is
            carrying forward the best answer for each of them. `best_so_far` is the
            best using everything up to here; `best_without_previous` is the best
            that leaves the previous position free. Two runes are missing.
        """,
        fn_name="max_loot", params="values", reference=_max_loot,
        canonical="""
            def max_loot(values):
                best_without_previous = 0
                best_so_far = 0
                for value in values:
                    candidate = best_without_previous + value
                    best_without_previous = best_so_far
                    best_so_far = max(best_so_far, candidate)
                return best_so_far
        """,
        blanks=[("best_without_previous + value",
                 "taking this value forbids the one before it, so build on the "
                 "total that left it free"),
                ("max(best_so_far, candidate)",
                 "take it or skip it, whichever pays more")],
        visible=[("classic", [[2, 7, 9, 3, 1]]), ("two", [[5, 1]])],
        hidden=[("all equal", [[3, 3, 3, 3]]), ("descending", [[9, 1, 1, 9]])],
        edges=[("empty", [[]]), ("single", [[4]]), ("zeros", [[0, 0, 0]])],
        constraints=["every value is non-negative"],
        failures=["Taking every other value, which is wrong for [2, 1, 1, 2]",
                  "Updating `best_so_far` before reading the value it is about to replace"],
        nudge="Two running answers, one step apart. Order of assignment matters.",
        visual="A table with two columns collapsed into two variables.",
        pseudocode="""
            for each value:
                candidate = best that skipped the previous + value
                shift the window
                best = max(best, candidate)
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    P.append(rune(
        id="sc-grid-paths", title="The Counted Descent", realm="dp_ruins",
        difficulty="EASY", family="dp_grid", pattern="DP",
        scaffold_for="DYNAMIC PROGRAMMING: a grid table", secondary=["MATRIX"],
        prerequisites=["sc-max-loot"],
        statement="""
            Moving only right or down, return how many distinct paths lead from the
            top-left of a `rows` x `cols` grid to the bottom-right.

            Only one row of the table is kept, because a cell depends on the cell
            above it and the cell to its left — and after the update, `row[c]` still
            holds the value from the row above. Two runes are missing: the first row,
            and the recurrence that reuses the slot.
        """,
        fn_name="unique_paths", params="rows, cols", reference=_unique_paths,
        canonical="""
            def unique_paths(rows, cols):
                if rows <= 0 or cols <= 0:
                    return 0
                row = [1] * cols
                for _ in range(1, rows):
                    for c in range(1, cols):
                        row[c] = row[c] + row[c - 1]
                return row[-1]
        """,
        blanks=[("[1] * cols",
                 "the top row: exactly one way to reach every cell in it"),
                ("row[c] + row[c - 1]",
                 "arrivals from above (still in this slot) plus arrivals from the left")],
        visible=[("three by seven", [3, 7]), ("square", [3, 3])],
        hidden=[("single row", [1, 5]), ("single column", [5, 1])],
        edges=[("one by one", [1, 1]), ("zero rows", [0, 4])],
        constraints=["0 <= rows, cols <= 30"],
        failures=["Starting the inner loop at 0 and reading `row[-1]`, which wraps around",
                  "Allocating the full 2-D table and then indexing it transposed"],
        nudge="Before `row[c]` is written, it still holds the row above it.",
        visual="One row, rewritten in place, sweeping downward.",
        pseudocode="""
            row = all ones, width cols
            repeat for each remaining row:
                for c from 1: row[c] = row[c] + row[c - 1]
            answer is the last cell
        """,
        time_complexity="O(n^2)", space_complexity="O(n)",
    ))

    # -- SORTING ------------------------------------------------------------
    P.append(rune(
        id="sc-sort-by-key", title="The Ordering Rune", realm="fields_of_syntax",
        difficulty="TUTORIAL", family="top_k", pattern="SORTING",
        scaffold_for="SORTING: a custom key",
        statement="""
            `records` is a list of `[name, score]`. Return the top `n` as lists,
            highest score first, ties broken by name ascending.

            `sorted` does all of the work; the only decision is what to sort BY. One
            rune: a key returning a tuple, where a leading minus flips one field's
            direction without flipping the other.
        """,
        fn_name="top_by_score", params="records, n", reference=_top_by_score,
        canonical="""
            def top_by_score(records, n):
                ordered = sorted(records, key=lambda r: (-r[1], r[0]))
                return [list(r) for r in ordered[:n]]
        """,
        blanks=[("(-r[1], r[0])",
                 "score descending first, then name ascending as the tie-break")],
        partial="""
            def top_by_score(records, n):
                ordered = sorted(records, key=lambda r: (__BLANK__, __BLANK__))
                return [list(r) for r in ordered[:n]]
        """,
        visible=[("clear order", [[["ann", 3], ["bob", 9], ["cy", 5]], 2]),
                 ("tie", [[["bob", 5], ["ann", 5]], 2])],
        hidden=[("n larger than list", [[["ann", 1]], 5]),
                ("all tied", [[["c", 2], ["a", 2], ["b", 2]], 3])],
        edges=[("empty", [[], 3]), ("n zero", [[["a", 1]], 0])],
        failures=["Sorting with `reverse=True`, which also reverses the name tie-break",
                  "Sorting twice and losing the first ordering"],
        nudge="A tuple key compares left to right. A minus flips one field only.",
        visual="Two fields, opposite directions. `reverse=True` cannot express that.",
        pseudocode="""
            sort by (negated score, name)
            take the first n
        """,
        time_complexity="O(n log n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-merge-intervals", title="The Joining of Spans", realm="array_caverns",
        difficulty="EASY", family="intervals", pattern="INTERVALS",
        scaffold_for="SORTING: intervals in one pass", secondary=["SORTING"],
        prerequisites=["sc-sort-by-key"],
        statement="""
            Merge every group of overlapping `[start, end]` intervals and return the
            result ordered by start.

            Sorting by start is what reduces this to a single pass: once the
            intervals are in order, an incoming one can only ever overlap the one
            currently being built. Three runes are missing, and the last hides a
            case people lose — an interval entirely contained by the previous one.
        """,
        fn_name="merge_intervals", params="intervals", reference=_merge_intervals,
        canonical="""
            def merge_intervals(intervals):
                if not intervals:
                    return []
                ordered = sorted(intervals, key=lambda pair: pair[0])
                merged = [list(ordered[0])]
                for start, end in ordered[1:]:
                    if start <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], end)
                    else:
                        merged.append([start, end])
                return merged
        """,
        blanks=[("key=lambda pair: pair[0]",
                 "sorting by this is what makes one pass sufficient"),
                ("start <= merged[-1][1]",
                 "this interval begins before the one being built has ended"),
                ("max(merged[-1][1], end)",
                 "the merged span ends at the later of the two ends — the incoming "
                 "one may end earlier")],
        visible=[("classic", [[[1, 3], [2, 6], [8, 10], [15, 18]]]),
                 ("touching", [[[1, 4], [4, 5]]])],
        hidden=[("contained", [[[1, 10], [2, 3]]]),
                ("unsorted input", [[[5, 6], [1, 2]]])],
        edges=[("empty", [[]]), ("single", [[[1, 2]]]), ("identical", [[[1, 2], [1, 2]]])],
        failures=["Assigning `end` directly and shortening a merged span",
                  "Assuming the input arrives sorted"],
        nudge="After sorting by start, only the most recent merged span can overlap.",
        visual="Spans on a line: each new one extends the last or starts a new one.",
        pseudocode="""
            sort by start
            merged = [first]
            for each remaining interval:
                overlaps the last merged -> extend its end to the later end
                otherwise -> start a new merged span
        """,
        time_complexity="O(n log n)", space_complexity="O(n)",
    ))

    # -- STRING -------------------------------------------------------------
    P.append(rune(
        id="sc-reverse-words", title="The Reordered Chant",
        realm="stringwood_labyrinth", difficulty="GUIDED", family="python_basics",
        pattern="STRING", scaffold_for="STRING: split and join",
        statement="""
            Return the words of `text` in reverse order, separated by single spaces.
            Runs of whitespace collapse.

            `str.split()` with no argument already handles the collapsing. The single
            missing rune is the rebuild: a separator, a join, and the words the other
            way round.
        """,
        fn_name="reverse_words", params="text", reference=_reverse_words,
        canonical="""
            def reverse_words(text):
                words = text.split()
                return " ".join(reversed(words))
        """,
        blanks=[('" ".join(reversed(words))',
                 "stitch the words back together, last to first, one space between")],
        partial="""
            def reverse_words(text):
                words = text.split()
                return __BLANK__.join(reversed(words))
        """,
        visible=[("simple", ["the sky is blue"]), ("padded", ["  hello   world  "])],
        hidden=[("single word", ["alone"]), ("two words", ["a b"])],
        edges=[("empty", [""]), ("only spaces", ["   "])],
        failures=["Calling `.split(' ')`, which produces empty strings from runs of spaces",
                  "Reversing the characters instead of the words"],
        nudge="`join` is a method on the separator, not on the list.",
        visual="split -> list of words -> reverse -> join.",
        pseudocode="""
            words = text.split()
            return the words joined by a single space, in reverse order
        """,
        time_complexity="O(n)", space_complexity="O(n)",
    ))

    P.append(rune(
        id="sc-common-prefix", title="The Shared Opening",
        realm="stringwood_labyrinth", difficulty="EASY", family="python_basics",
        pattern="STRING", scaffold_for="STRING: shrinking a candidate",
        prerequisites=["sc-reverse-words"],
        statement="""
            Return the longest string that starts every word in `words`, or `""` if
            there is none.

            The first word is taken as a candidate and every other word is allowed to
            veto it. A veto does not restart the search — it just trims the candidate
            by one character and asks again. Two runes carry that.
        """,
        fn_name="longest_common_prefix", params="words",
        reference=_longest_common_prefix,
        canonical="""
            def longest_common_prefix(words):
                if not words:
                    return ""
                prefix = words[0]
                for word in words[1:]:
                    while not word.startswith(prefix):
                        prefix = prefix[:-1]
                        if not prefix:
                            return ""
                return prefix
        """,
        blanks=[("not word.startswith(prefix)",
                 "this word does not begin with the candidate, so the candidate is too long"),
                ("prefix[:-1]", "drop one character from the right-hand end")],
        visible=[("shared", [["flower", "flow", "flight"]]),
                 ("none shared", [["dog", "racecar", "car"]])],
        hidden=[("identical", [["abc", "abc"]]), ("one word", [["single"]])],
        edges=[("empty list", [[]]), ("empty word", [["", "abc"]])],
        failures=["Comparing only the first two words",
                  "Trimming from the left, which is a common SUBSTRING, not a prefix"],
        nudge="The answer can never be longer than the first word.",
        visual="The candidate only ever shrinks, so the whole scan is linear.",
        pseudocode="""
            candidate = first word
            for every other word:
                while the word does not start with the candidate:
                    drop the candidate's last character
                    nothing left -> ""
            return the candidate
        """,
        time_complexity="O(n)", space_complexity="O(1)",
    ))

    return P
