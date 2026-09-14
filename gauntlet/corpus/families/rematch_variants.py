"""Changed-contract boss practice. These exercises are not sealed transfer tests."""
from __future__ import annotations

from collections import Counter
from itertools import combinations

from ._base import code_problem, design_problem
from ._tree import PREAMBLE as TREE_PREAMBLE, tree_ref


def _anagram_pairs(words):
    return sum(Counter(a) == Counter(b) for a, b in combinations(words, 2))


def _bst_report(root):
    values = []
    def inorder(node):
        if node:
            inorder(node.left)
            values.append(node.val)
            inorder(node.right)
    def heights(node):
        if not node:
            return 0, True
        left, a = heights(node.left)
        right, b = heights(node.right)
        return 1 + max(left, right), a and b and abs(left - right) <= 1
    inorder(root)
    height, balanced = heights(root)
    return {"is_bst": all(a < b for a, b in zip(values, values[1:])),
            "height": height, "balanced": balanced}


def _shortest_nodes(graph, start, end):
    paths, seen = [[start]], {start}
    while paths:
        following = []
        for path in paths:
            if path[-1] == end:
                return path
            for node in graph.get(path[-1], []):
                if node not in seen:
                    seen.add(node)
                    following.append(path + [node])
        paths = following
    return []


class _RollingReference:
    def __init__(self, k):
        self.k, self.window = k, []
    def push(self, value):
        self.window.append(value)
        self.window = self.window[-self.k:]
        return max(self.window) if len(self.window) == self.k else None
    def reset(self):
        self.window = []
        return None


def _wildcard_cover(s, target):
    if not target:
        return ""
    needed = Counter(c for c in target if c != '?')
    best = ""
    for start in range(len(s)):
        for end in range(start + len(target), len(s) + 1):
            window = s[start:end]
            counts = Counter(window)
            if all(counts[c] >= n for c, n in needed.items()):
                if not best or len(window) < len(best):
                    best = window
                break
    return best


def _tags(base):
    return ["practice:constraint-change", f"rematch-of:{base}"]


def build():
    problems = [
        code_problem(
            id="rm-anagram-index-pairs", title="The Titan Counts Every Pair",
            realm="hashmap_highlands", pattern="HASH_MAP", difficulty="MEDIUM",
            family="anagrams", boss=True, source_type="GENERATED_VARIANT",
            statement="""Return the number of index pairs i < j for which words[i]
            and words[j] are anagrams. Repeated words at different positions count
            separately. Return a count, not groups or a count of distinct spellings.
            Character multiplicity matters; 'ab' and 'aab' are not anagrams.""",
            fn_name="count_anagram_pairs", params="words", reference=_anagram_pairs,
            canonical='''
            def count_anagram_pairs(words):
                counts = {}
                total = 0
                for word in words:
                    key = tuple(sorted(word))
                    total += counts.get(key, 0)
                    counts[key] = counts.get(key, 0) + 1
                return total
            ''',
            visible=[("repeated positions", [["ab", "ba", "ab"]]),
                     ("two signatures", [["eat", "tea", "tan", "nat"]])],
            hidden=[("multiplicity", [["ab", "aab", "aba", "baa"]]),
                    ("all identical", [["a"] * 8]),
                    ("separate classes", [["ab", "ba", "c", "c", "c"]])],
            edges=[("empty list", [[]]), ("one word", [["abc"]]),
                   ("empty words count", [["", "", "a", ""]])],
            constraints=["0 <= len(words) <= 200", "words contain lowercase ASCII letters; empty words are allowed"],
            time_complexity="O(n k log k)", space_complexity="O(n k)",
            nudge="How many new index pairs does another member of an existing signature create?",
            tags=_tags("ah-group-anagrams")),
        code_problem(
            id="rm-bst-subtree-report", title="The Dragon's Three-Part Verdict",
            realm="binary_tree_canopy", pattern="TREE", difficulty="MEDIUM",
            family="bst", boss=True, source_type="GENERATED_VARIANT",
            statement="""Return a dictionary with is_bst, height and balanced for
            the whole binary tree. is_bst uses strict ordering throughout every
            subtree: duplicates are invalid. Height counts nodes on the longest
            root-to-leaf path (an empty tree has height 0). balanced is true only
            if EVERY node's two subtree heights differ by at most one. A tree may
            be a valid BST but unbalanced, or balanced but not a BST.""",
            fn_name="bst_report", params="root", reference=tree_ref(_bst_report),
            preamble=TREE_PREAMBLE, arg_adapters=["tree"],
            canonical='''
            def bst_report(root):
                def visit(node):
                    if node is None:
                        return True, 0, True, float('inf'), float('-inf')
                    lv, lh, lb, lo, lx = visit(node.left)
                    rv, rh, rb, ro, rx = visit(node.right)
                    valid = lv and rv and lx < node.val < ro
                    height = 1 + max(lh, rh)
                    balanced = lb and rb and abs(lh - rh) <= 1
                    return valid, height, balanced, min(lo, node.val, ro), max(lx, node.val, rx)
                valid, height, balanced, low, high = visit(root)
                return {'is_bst': valid, 'height': height, 'balanced': balanced}
            ''',
            visible=[("balanced search tree", [[2, 1, 3]]),
                     ("valid but unbalanced", [[3, 2, None, 1]])],
            hidden=[("ancestor violation", [[5, 1, 7, None, None, 4, 8]]),
                    ("equal heights hide inner imbalance", [[8, 4, 12, 2, None, None, 14, 1, None, None, 15]]),
                    ("duplicate key", [[2, 2, 3]])],
            edges=[("empty", [[]]), ("single", [[0]]), ("negative values", [[-2, -3, -1]])],
            constraints=["The input is a finite binary tree with integer values and at most 200 nodes."],
            time_complexity="O(n)", space_complexity="O(h)",
            nudge="Which summary lets a parent combine its children's answers without revisiting their nodes?",
            tags=_tags("tr-validate-bst")),
        code_problem(
            id="rm-shortest-node-path", title="The Necromancer Demands the Road",
            realm="graph_wastes", pattern="BFS", difficulty="MEDIUM",
            family="graph_shortest", boss=True, source_type="GENERATED_VARIANT",
            statement="""Return a shortest path as a list of node names from start
            to end, including both endpoints. Return [] when end is unreachable.
            This is a directed adjacency-list graph; a missing key has no outgoing
            edges. Resolve equal-length routes by first BFS discovery while
            visiting each node's neighbors in the listed order. Cycles and repeated
            edges are allowed. If start == end, return [start].""",
            fn_name="shortest_node_path", params="graph, start, end", reference=_shortest_nodes,
            canonical='''
            from collections import deque
            def shortest_node_path(graph, start, end):
                frontier = deque([start])
                parent = {start: None}
                while frontier:
                    node = frontier.popleft()
                    if node == end:
                        path = []
                        while node is not None:
                            path.append(node)
                            node = parent[node]
                        return path[::-1]
                    for neighbor in graph.get(node, []):
                        if neighbor not in parent:
                            parent[neighbor] = node
                            frontier.append(neighbor)
                return []
            ''',
            visible=[("route not distance", [{"a": ["b"], "b": ["c"]}, "a", "c"]),
                     ("listed order breaks ties", [{"a": ["c", "b"], "b": ["d"], "c": ["d"]}, "a", "d"])],
            hidden=[("cycle", [{"a": ["b"], "b": ["a", "c"], "c": ["a"]}, "a", "c"]),
                    ("duplicate discoveries", [{"a": ["b", "b", "c"], "b": ["d"], "c": ["d"]}, "a", "d"]),
                    ("longer route listed first", [{"a": ["b", "e"], "b": ["c"], "c": ["d"], "e": ["d"]}, "a", "d"])],
            edges=[("unreachable", [{"a": ["b"]}, "a", "z"]),
                   ("same node", [{}, "a", "a"]), ("missing source", [{}, "a", "b"])],
            constraints=["Node names are strings; neighbor lists preserve their given order."],
            time_complexity="O(V + E)", space_complexity="O(V)",
            nudge="What predecessor information is enough to reconstruct the first shortest route?",
            tags=_tags("gr-shortest-hops")),
        design_problem(
            id="rm-streaming-window-max", title="The Titan's Unfinished Stream",
            realm="sliding_window_marsh", difficulty="HARD", family="rolling_max",
            boss=True, source_type="GENERATED_VARIANT", secondary=["QUEUE"],
            statement="""Implement RollingMaximum(k) for a stream arriving one
            value at a time. push(value) returns None until k values have arrived,
            then returns the maximum of the last k values. reset() returns None
            and forgets the window, starting warm-up again. Each push must answer
            before the next input arrives. Keep O(k) window state; the reference
            uses O(1) amortized work per push. k is always a positive integer.""",
            cls_name="RollingMaximum", reference_cls=_RollingReference,
            canonical='''
            from collections import deque
            class RollingMaximum:
                def __init__(self, k):
                    self.k = k
                    self.reset()
                def reset(self):
                    self.index = -1
                    self.candidates = deque()
                def push(self, value):
                    self.index += 1
                    while self.candidates and self.candidates[0][0] <= self.index - self.k:
                        self.candidates.popleft()
                    while self.candidates and self.candidates[-1][1] <= value:
                        self.candidates.pop()
                    self.candidates.append((self.index, value))
                    return self.candidates[0][1] if self.index + 1 >= self.k else None
            ''',
            visible=[("warm-up and expiry", ["__init__"] + ["push"] * 5, [[3], [5], [1], [2], [0], [4]]),
                     ("reset forgets old peak", ["__init__", "push", "push", "reset", "push", "push"], [[2], [9], [8], [], [1], [2]])],
            hidden=[("equal maxima expire separately", ["__init__"] + ["push"] * 6, [[2], [4], [4], [1], [1], [3], [2]]),
                    ("negative stream", ["__init__"] + ["push"] * 5, [[3], [-2], [-8], [-4], [-5], [-9]]),
                    ("descending stream", ["__init__"] + ["push"] * 20, [[4]] + [[v] for v in range(20, 0, -1)])],
            edges=[("capacity one", ["__init__", "push", "push"], [[1], [9], [-3]]),
                   ("repeated reset", ["__init__", "reset", "reset", "push"], [[2], [], [], [7]])],
            constraints=["1 <= k <= 1000", "push accepts integers; the stream can continue after reset"],
            time_complexity="O(1) amortized per push", space_complexity="O(k)",
            nudge="Which candidates can never beat a newer value, and which are now outside the window?",
            tags=_tags("sw-max-sliding-window")),
        code_problem(
            id="rm-wildcard-window-cover", title="The Wyrm's Unnamed Runes",
            realm="complexity_tower", pattern="SLIDING_WINDOW", difficulty="HARD",
            family="window_cover", boss=True, source_type="GENERATED_VARIANT",
            statement="""Return the shortest substring of s that covers target.
            Literal target characters must appear with their full multiplicities.
            Each '?' in target is a wildcard consuming one additional character
            of any kind, so a valid window must also have length at least len(target).
            A character position cannot satisfy both a literal and a wildcard.
            Return the leftmost window on ties, or '' if no cover exists. An empty
            target returns ''. s contains lowercase ASCII letters and no '?'.""",
            fn_name="wildcard_window", params="s, target", reference=_wildcard_cover,
            canonical='''
            from collections import Counter
            def wildcard_window(s, target):
                if not target:
                    return ''
                need = Counter(c for c in target if c != '?')
                missing = sum(need.values())
                left = 0
                best = None
                for right, char in enumerate(s):
                    if char in need:
                        if need[char] > 0:
                            missing -= 1
                        need[char] -= 1
                    while missing == 0 and right - left + 1 >= len(target):
                        if best is None or right - left + 1 < best[1] - best[0]:
                            best = (left, right + 1)
                        old = s[left]
                        if old in need:
                            need[old] += 1
                            if need[old] > 0:
                                missing += 1
                        left += 1
                return '' if best is None else s[best[0]:best[1]]
            ''',
            visible=[("literal plus wildcard", ["cab", "a?"]),
                     ("repeated literal", ["baac", "aa?"])],
            hidden=[("wildcards need separate positions", ["a", "a?"]),
                    ("leftmost tied cover", ["zabac", "a?"]),
                    ("literal counts cannot be replaced", ["abbb", "aa?"]),
                    ("shrink past surplus", ["xxbaaayz", "aa?"])],
            edges=[("empty target", ["abc", ""]), ("empty source", ["", "?"]),
                   ("only wildcards", ["abcdef", "???"]), ("impossible length", ["ab", "???"])],
            constraints=["s uses lowercase ASCII letters; target also permits '?'", "ties return the leftmost substring"],
            time_complexity="O(n + m)", space_complexity="O(m)",
            nudge="Separate missing literal counts from the minimum length contributed by wildcard slots.",
            tags=_tags("sw-min-window")),
    ]

    stream = next(p for p in problems if p.id == "rm-streaming-window-max")
    stream.starter_code = ("class RollingMaximum:\n    def __init__(self, k):\n        pass\n\n"
                           "    def push(self, value):\n        pass\n\n"
                           "    def reset(self):\n        pass\n")
    return problems
