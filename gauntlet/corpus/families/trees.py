"""Binary Tree Canopy and Recursive Forest. Every node asks its children a question."""
from __future__ import annotations

from collections import deque

from ._base import code_problem
from ._tree import PREAMBLE, TreeNode, to_tree, from_tree, tree_ref

Q = {"QUORA": 3.0, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 1.0}
QS = {"QUORA": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}
VIZ = {"type": "tree", "caption": "The dungeon physically branches."}
TREE_HINT = "root is a TreeNode with .val, .left and .right; children may be None"


def _max_depth(root):
    if root is None:
        return 0
    return 1 + max(_max_depth(root.left), _max_depth(root.right))


def _invert(root):
    if root is None:
        return None
    root.left, root.right = _invert(root.right), _invert(root.left)
    return root


def _is_valid_bst(root):
    def check(node, low, high):
        if node is None:
            return True
        if not (low < node.val < high):
            return False
        return check(node.left, low, node.val) and check(node.right, node.val, high)
    return check(root, float("-inf"), float("inf"))


def _has_path_sum(root, target):
    if root is None:
        return False
    if root.left is None and root.right is None:
        return root.val == target
    rest = target - root.val
    return _has_path_sum(root.left, rest) or _has_path_sum(root.right, rest)


def _all_path_sums(root, target):
    out = []

    def walk(node, remaining, path):
        if node is None:
            return
        path.append(node.val)
        remaining -= node.val
        if node.left is None and node.right is None and remaining == 0:
            out.append(list(path))
        else:
            walk(node.left, remaining, path)
            walk(node.right, remaining, path)
        path.pop()

    walk(root, target, [])
    return out


def _level_order(root):
    if root is None:
        return []
    out, queue = [], deque([root])
    while queue:
        level = []
        for _ in range(len(queue)):
            node = queue.popleft()
            level.append(node.val)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        out.append(level)
    return out


def _right_view(root):
    return [level[-1] for level in _level_order(root)]


def _inorder(root):
    out, stack, node = [], [], root
    while node or stack:
        while node:
            stack.append(node)
            node = node.left
        node = stack.pop()
        out.append(node.val)
        node = node.right
    return out


def _is_balanced(root):
    def depth(node):
        if node is None:
            return 0
        left = depth(node.left)
        if left < 0:
            return -1
        right = depth(node.right)
        if right < 0 or abs(left - right) > 1:
            return -1
        return 1 + max(left, right)
    return depth(root) >= 0


def _lowest_common(root, a, b):
    if root is None or root.val == a or root.val == b:
        return root.val if root else None
    left = _lowest_common(root.left, a, b)
    right = _lowest_common(root.right, a, b)
    if left is not None and right is not None:
        return root.val
    return left if left is not None else right


def _diameter(root):
    best = 0

    def depth(node):
        nonlocal best
        if node is None:
            return 0
        left, right = depth(node.left), depth(node.right)
        best = max(best, left + right)
        return 1 + max(left, right)

    depth(root)
    return best


def _serialize(root):
    out = []

    def walk(node):
        if node is None:
            out.append("#")
            return
        out.append(str(node.val))
        walk(node.left)
        walk(node.right)

    walk(root)
    return ",".join(out)


def _round_trip(values):
    """serialize -> deserialize -> level order; proves the pair is consistent."""
    root = to_tree(values)
    text = _serialize(root)
    tokens = iter(text.split(","))

    def build():
        tok = next(tokens)
        if tok == "#":
            return None
        node = TreeNode(int(tok))
        node.left = build()
        node.right = build()
        return node

    return from_tree(build())


def _count_nodes(root):
    if root is None:
        return 0
    return 1 + _count_nodes(root.left) + _count_nodes(root.right)


def _max_priv_depth(root):
    return _max_depth(root)


def _sum_tree(root):
    if root is None:
        return 0
    return root.val + _sum_tree(root.left) + _sum_tree(root.right)


SAMPLE = [3, 9, 20, None, None, 15, 7]
BST = [5, 3, 8, 1, 4, 7, 9]
DEEP = [1, 2, None, 3, None, 4, None, 5]


def build() -> list:
    P: list = []
    common = dict(preamble=PREAMBLE, arg_adapters=["tree"], realm="binary_tree_canopy",
                  viz=VIZ, starter_hint=TREE_HINT, profile_weight=Q)

    P.append(code_problem(
        id="tr-max-depth", title="Canopy Height", pattern="TREE", difficulty="EASY",
        family="tree_traverse", secondary=["RECURSION", "DFS"], **common,
        statement="""
            Return the depth of the deepest node in the binary tree. An empty tree has
            depth `0`; a lone root has depth `1`.

            Trees are given to your tests in level order, but your function receives a
            real `TreeNode`.
        """,
        fn_name="max_depth", params="root", reference=tree_ref(_max_depth),
        canonical="""
            def max_depth(root):
                if root is None:
                    return 0
                return 1 + max(max_depth(root.left), max_depth(root.right))
        """,
        visible=[("classic", [SAMPLE]), ("single node", [[1]])],
        hidden=[("left chain", [DEEP]), ("balanced", [BST]),
                ("right only", [[1, None, 2, None, 3]])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Returning 0 for a single node — the root counts",
                  "Iterating without tracking levels"],
        nudge="A node's depth is one more than its deeper child's depth. That sentence is "
              "the whole function.",
        visual="Ask both branches how tall they are, take the taller, add yourself.",
        pseudocode="if node is None: 0 else 1 + max(depth(left), depth(right))",
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="tr-invert", title="The Mirrored Grove", pattern="TREE", difficulty="EASY",
        family="tree_traverse", secondary=["RECURSION"], **common,
        result_adapter="tree",
        statement="""
            Swap every node's left and right child, top to bottom, and return the root.
            Your answer is compared in level order.
        """,
        fn_name="invert_tree", params="root",
        reference=tree_ref(_invert, returns_tree=True),
        canonical="""
            def invert_tree(root):
                if root is None:
                    return None
                root.left, root.right = invert_tree(root.right), invert_tree(root.left)
                return root
        """,
        visible=[("classic", [[4, 2, 7, 1, 3, 6, 9]]), ("single", [[1]])],
        hidden=[("lopsided", [[1, 2]]), ("deep chain", [DEEP]), ("sample", [SAMPLE])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Assigning left before computing the new right loses a subtree",
                  "Forgetting to return the root"],
        nudge="Swap the children, then recurse — or recurse then swap. Just do not "
              "half-overwrite.",
        visual="Every fork in the path flips left for right, all the way down.",
        pseudocode="node.left, node.right = invert(node.right), invert(node.left)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tr-validate-bst", title="The Tree Dragon", pattern="TREE", difficulty="MEDIUM",
        family="bst", secondary=["RECURSION", "DFS"], boss=True, **common,
        source_type="REPORTED_INTERVIEW", company="Quora", year="reported pattern",
        provenance="Validating a BST is a repeatedly reported screen archetype.",
        statement="""
            Return `True` if the tree is a valid binary search tree: every value in a
            node's left subtree is strictly less than the node, every value in its right
            subtree is strictly greater, and both subtrees are themselves valid.

            The Dragon's favourite meal is a solution that only compares parents to their
            immediate children.
        """,
        fn_name="is_valid_bst", params="root", reference=tree_ref(_is_valid_bst),
        cmp="bool",
        canonical="""
            def is_valid_bst(root):
                def check(node, low, high):
                    if node is None:
                        return True
                    if not (low < node.val < high):
                        return False
                    return (check(node.left, low, node.val)
                            and check(node.right, node.val, high))

                return check(root, float("-inf"), float("inf"))
        """,
        visible=[("valid", [BST]), ("invalid", [[5, 1, 4, None, None, 3, 6]])],
        hidden=[("deep violation", [[10, 5, 15, None, None, 6, 20]]),
                ("equal values", [[2, 2, 2]]), ("left chain", [[3, 2, None, 1]]),
                ("negatives", [[0, -3, 9]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Only comparing a node to its direct children — a grandchild can still "
                  "violate the ordering",
                  "Allowing equal values",
                  "Using a fixed integer sentinel instead of infinity"],
        nudge="A node is not just constrained by its parent. It inherits a whole open "
              "interval from every ancestor above it.",
        visual="Every node carries a permitted range down to its children. Going left "
               "tightens the ceiling; going right raises the floor.",
        pseudocode="""
            check(node, low, high):
                node is None -> True
                not low < node.val < high -> False
                check(left, low, node.val) and check(right, node.val, high)
        """,
        alternates=[{"name": "in-order traversal must be strictly increasing",
                     "note": "Equally valid and often easier to explain aloud.",
                     "complexity": "O(n)"}],
        tags=["core", "quora", "boss"],
    ))

    P.append(code_problem(
        id="tr-path-sum", title="The Path-Sum Ent", pattern="TREE", difficulty="EASY",
        family="tree_paths", secondary=["RECURSION", "DFS"], **common,
        source_type="REPORTED_INTERVIEW", company="Quora", year="reported pattern",
        provenance="Path-sum variants are a repeatedly reported archetype.",
        statement="""
            Return `True` if any root-to-leaf path sums to `target`. A leaf is a node with
            no children.
        """,
        fn_name="has_path_sum", params="root, target",
        reference=tree_ref(_has_path_sum), cmp="bool",
        canonical="""
            def has_path_sum(root, target):
                if root is None:
                    return False
                if root.left is None and root.right is None:
                    return root.val == target       # only leaves may finish a path
                remaining = target - root.val
                return (has_path_sum(root.left, remaining)
                        or has_path_sum(root.right, remaining))
        """,
        visible=[("hit", [[5, 4, 8, 11, None, 13, 4, 7, 2], 22]),
                 ("miss", [[1, 2, 3], 5])],
        hidden=[("negatives", [[-2, None, -3], -5]), ("single", [[7], 7]),
                ("half path is not enough", [[1, 2], 1]),
                ("zero target", [[0], 0])],
        edges=[("empty", [[], 0]), ("empty nonzero", [[], 5])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Returning True at an internal node whose running sum happens to match",
                  "Treating a node with one child as a leaf",
                  "Returning True for an empty tree when target is 0"],
        nudge="Only a leaf may declare victory. A node with one child is not a leaf.",
        visual="Subtract as you descend. At a leaf, the remainder must be exactly zero.",
        pseudocode="leaf -> val == target; else -> either child with target - val",
        variants=["tr-all-path-sums"], tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="tr-all-path-sums", title="Every Road the Ent Knows", pattern="TREE",
        difficulty="MEDIUM", family="tree_paths", secondary=["RECURSION", "DFS"],
        source_type="GENERATED_VARIANT", cmp="nested_set", **common,
        statement="""
            Return **every** root-to-leaf path whose values sum to `target`, each as a
            list from root to leaf. Order does not matter.
        """,
        fn_name="path_sum_paths", params="root, target",
        reference=tree_ref(_all_path_sums),
        canonical="""
            def path_sum_paths(root, target):
                out = []

                def walk(node, remaining, path):
                    if node is None:
                        return
                    path.append(node.val)
                    remaining -= node.val
                    if node.left is None and node.right is None and remaining == 0:
                        out.append(list(path))       # copy! path is mutated after this
                    else:
                        walk(node.left, remaining, path)
                        walk(node.right, remaining, path)
                    path.pop()                        # undo before returning

                walk(root, target, [])
                return out
        """,
        visible=[("two paths", [[5, 4, 8, 11, None, 13, 4, 7, 2, None, None, 5, 1], 22]),
                 ("none", [[1, 2], 99])],
        hidden=[("single node", [[7], 7]), ("negatives", [[-2, None, -3], -5]),
                ("all match", [[0, 0, 0], 0])],
        edges=[("empty", [[], 0])],
        time_complexity="O(n·h)", space_complexity="O(h)",
        failures=["Appending `path` itself instead of a copy — every result mutates later",
                  "Forgetting to pop on the way back up",
                  "Recording at internal nodes"],
        nudge="Two classic backtracking mistakes live here: forgetting to copy, and "
              "forgetting to undo.",
        visual="Walk down carrying the trail; drop a copy at a matching leaf; erase your "
               "last step on the way back up.",
        pseudocode="append; recurse; pop  — and copy the path when you record it",
        prerequisites=["tr-path-sum"], tags=["core", "backtracking"],
    ))

    P.append(code_problem(
        id="tr-level-order", title="Rings of the Canopy", pattern="BFS", difficulty="MEDIUM",
        family="tree_bfs", secondary=["TREE", "QUEUE"],
        **{**common, "viz": {"type": "bfs",
                             "caption": "A wave of light expands level by level."}},
        statement="""
            Return the node values level by level, top to bottom, each level left to right.
        """,
        fn_name="level_order", params="root", reference=tree_ref(_level_order),
        canonical="""
            def level_order(root):
                from collections import deque
                if root is None:
                    return []
                out = []
                queue = deque([root])
                while queue:
                    level = []
                    for _ in range(len(queue)):     # snapshot THIS level's size
                        node = queue.popleft()
                        level.append(node.val)
                        if node.left:
                            queue.append(node.left)
                        if node.right:
                            queue.append(node.right)
                    out.append(level)
                return out
        """,
        visible=[("classic", [SAMPLE]), ("single", [[1]])],
        hidden=[("chain", [DEEP]), ("full", [BST]),
                ("right lean", [[1, None, 2, None, 3]])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(width)",
        failures=["Not snapshotting the level size, so children join the current level",
                  "Using list.pop(0) instead of deque.popleft",
                  "Appending None children"],
        nudge="Capture `len(queue)` before you start draining it. That is the level width.",
        visual="A ring of light expands outward one layer at a time. Everything currently "
               "in the queue is exactly one layer.",
        pseudocode="""
            while queue:
                for _ in range(len(queue)):   # snapshot first
                    pop, record, enqueue children
        """,
        variants=["tr-right-view"], tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="tr-right-view", title="Seen from the East", pattern="BFS", difficulty="MEDIUM",
        family="tree_bfs", secondary=["TREE"], source_type="GENERATED_VARIANT", **common,
        statement="""
            Standing to the right of the tree, return the values you can see, top to
            bottom — the rightmost node of each level.
        """,
        fn_name="right_side_view", params="root", reference=tree_ref(_right_view),
        canonical="""
            def right_side_view(root):
                from collections import deque
                if root is None:
                    return []
                out = []
                queue = deque([root])
                while queue:
                    size = len(queue)
                    for i in range(size):
                        node = queue.popleft()
                        if i == size - 1:
                            out.append(node.val)     # last of this level
                        if node.left:
                            queue.append(node.left)
                        if node.right:
                            queue.append(node.right)
                return out
        """,
        visible=[("classic", [[1, 2, 3, None, 5, None, 4]]), ("single", [[1]])],
        hidden=[("left chain still visible", [DEEP]), ("balanced", [BST])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(width)",
        failures=["Only following right children — a deep left subtree is still visible "
                  "when the right side runs out"],
        nudge="Not 'always go right'. The rightmost node *of each level*.",
        visual="Each ring of light; keep only its last node.",
        pseudocode="BFS by level; append the last node of each level",
        prerequisites=["tr-level-order"], tags=["variant"],
    ))

    P.append(code_problem(
        id="tr-inorder-iterative", title="The Unwound Path", pattern="TREE",
        difficulty="MEDIUM", family="tree_traverse", secondary=["STACK"], **common,
        statement="""
            Return the in-order traversal (left, node, right) **without recursion**. Use an
            explicit stack.
        """,
        fn_name="inorder", params="root", reference=tree_ref(_inorder),
        canonical="""
            def inorder(root):
                out, stack, node = [], [], root
                while node or stack:
                    while node:                 # dive left as far as possible
                        stack.append(node)
                        node = node.left
                    node = stack.pop()
                    out.append(node.val)
                    node = node.right           # then pivot right and repeat
                return out
        """,
        visible=[("bst is sorted", [BST]), ("single", [[1]])],
        hidden=[("chain", [DEEP]), ("sample", [SAMPLE]),
                ("right lean", [[1, None, 2]])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Terminating the loop while the stack still holds nodes",
                  "Pivoting right before recording the node"],
        nudge="The recursion's call stack becomes your list. Dive left, record, pivot right.",
        visual="You descend the left wall, then unwind one step at a time, turning right "
               "each time you pop.",
        pseudocode="while node or stack: dive left; pop; record; node = node.right",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tr-is-balanced", title="The Even Bough", pattern="TREE", difficulty="MEDIUM",
        family="tree_traverse", secondary=["RECURSION"], cmp="bool", **common,
        statement="""
            Return `True` if the tree is height-balanced: for every node, the depths of
            its two subtrees differ by at most one.
        """,
        fn_name="is_balanced", params="root", reference=tree_ref(_is_balanced),
        canonical="""
            def is_balanced(root):
                def depth(node):
                    if node is None:
                        return 0
                    left = depth(node.left)
                    if left < 0:
                        return -1              # propagate failure upward
                    right = depth(node.right)
                    if right < 0 or abs(left - right) > 1:
                        return -1
                    return 1 + max(left, right)

                return depth(root) >= 0
        """,
        visible=[("balanced", [SAMPLE]), ("unbalanced", [[1, 2, 2, 3, 3, None, None, 4, 4]])],
        hidden=[("chain", [DEEP]), ("single", [[1]]), ("two levels", [[1, 2]])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Recomputing depth at every node makes it O(n^2)",
                  "Only checking the root's two subtrees"],
        nudge="Compute depth and balance in the same pass. Use a sentinel to signal failure.",
        visual="Each node returns its height, or a red flag that travels straight to the top.",
        pseudocode="depth returns -1 on imbalance; any -1 short-circuits everything above",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tr-lowest-common", title="Where the Roads Diverged", pattern="TREE",
        difficulty="MEDIUM", family="tree_paths", secondary=["RECURSION"], **common,
        statement="""
            Return the value of the lowest node that has both `a` and `b` somewhere in its
            subtree. Both values are guaranteed present and distinct. A node may be its
            own ancestor.
        """,
        fn_name="lowest_common_ancestor", params="root, a, b",
        reference=tree_ref(_lowest_common),
        canonical="""
            def lowest_common_ancestor(root, a, b):
                if root is None or root.val == a or root.val == b:
                    return root.val if root else None
                left = lowest_common_ancestor(root.left, a, b)
                right = lowest_common_ancestor(root.right, a, b)
                if left is not None and right is not None:
                    return root.val       # they split here: this is the meeting point
                return left if left is not None else right
        """,
        visible=[("split at root", [BST, 1, 9]), ("one is ancestor", [BST, 3, 4])],
        hidden=[("deep pair", [[3, 5, 1, 6, 2, 0, 8, None, None, 7, 4], 7, 4]),
                ("root involved", [BST, 5, 1]), ("adjacent", [BST, 7, 9])],
        edges=[("two node tree", [[1, 2], 1, 2])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Returning the node only when both children are non-None but forgetting "
                  "the case where one target is the ancestor of the other",
                  "Assuming a BST and comparing values"],
        nudge="If one target turns up in each subtree, you are standing on the answer.",
        visual="Two search parties climb from below. Where their reports meet is the "
               "common ancestor.",
        pseudocode="found in both subtrees -> this node; otherwise pass up whichever found",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tr-diameter", title="The Longest Bough", pattern="TREE", difficulty="MEDIUM",
        family="tree_traverse", secondary=["RECURSION"], **common,
        statement="""
            Return the number of edges on the longest path between any two nodes. The path
            need not pass through the root.
        """,
        fn_name="diameter", params="root", reference=tree_ref(_diameter),
        canonical="""
            def diameter(root):
                best = 0

                def depth(node):
                    nonlocal best
                    if node is None:
                        return 0
                    left, right = depth(node.left), depth(node.right)
                    best = max(best, left + right)   # path bending at this node
                    return 1 + max(left, right)      # what we report upward

                depth(root)
                return best
        """,
        visible=[("classic", [[1, 2, 3, 4, 5]]), ("single", [[1]])],
        hidden=[("chain", [DEEP]), ("balanced", [BST]),
                ("bend below root", [[1, 2, None, 3, 4, 5, 6]])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Assuming the longest path passes through the root",
                  "Returning depth instead of the bent-path length",
                  "Counting nodes instead of edges"],
        nudge="Two different quantities: what a node *reports upward* and what a node "
              "*records as a best*. They are not the same number.",
        visual="At each node, a path may bend: down the left arm and back up the right.",
        pseudocode="best = max(best, left + right); return 1 + max(left, right)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="tr-serialize", title="The Bound Codex", pattern="TREE", difficulty="HARD",
        family="tree_serialize", secondary=["RECURSION", "STRING"], boss=True,
        **{k: v for k, v in common.items()
           if k not in ("preamble", "arg_adapters", "starter_hint")},
        source_type="REPORTED_INTERVIEW", company="Quora", year="reported pattern",
        provenance="Serialize/deserialize is a repeatedly reported hard-tier archetype.",
        statement="""
            Implement `round_trip(values)`: build a tree from the level-order `values`,
            serialize it to a string, deserialize that string back into a tree, and return
            the resulting tree in level order.

            You must write both halves. A `TreeNode` class and a `build_from_level_order`
            helper are already available. The output must equal the input tree exactly —
            structure included, not merely the same multiset of values.
        """,
        fn_name="round_trip", params="values", reference=_round_trip,
        preamble=PREAMBLE + """

def build_from_level_order(values):
    if not values:
        return None
    root = TreeNode(values[0])
    queue, i, head = [root], 1, 0
    while head < len(queue) and i < len(values):
        node = queue[head]; head += 1
        if i < len(values):
            v = values[i]; i += 1
            if v is not None:
                node.left = TreeNode(v); queue.append(node.left)
        if i < len(values):
            v = values[i]; i += 1
            if v is not None:
                node.right = TreeNode(v); queue.append(node.right)
    return root


def to_level_order(node):
    if node is None:
        return []
    out, queue, head = [], [node], 0
    while head < len(queue):
        cur = queue[head]; head += 1
        if cur is None:
            out.append(None); continue
        out.append(cur.val); queue.append(cur.left); queue.append(cur.right)
    while out and out[-1] is None:
        out.pop()
    return out
""",
        arg_adapters=[],
        starter_hint="use build_from_level_order(values) and to_level_order(node)",
        canonical="""
            def round_trip(values):
                root = build_from_level_order(values)

                def serialize(node, out):
                    if node is None:
                        out.append("#")          # the null marker is what saves you
                        return
                    out.append(str(node.val))
                    serialize(node.left, out)
                    serialize(node.right, out)

                parts = []
                serialize(root, parts)
                text = ",".join(parts)

                tokens = iter(text.split(","))

                def deserialize():
                    tok = next(tokens)
                    if tok == "#":
                        return None
                    node = TreeNode(int(tok))
                    node.left = deserialize()
                    node.right = deserialize()
                    return node

                return to_level_order(deserialize())
        """,
        visible=[("classic", [SAMPLE]), ("single", [[1]])],
        hidden=[("left chain", [DEEP]), ("right chain", [[1, None, 2, None, 3]]),
                ("balanced", [BST]), ("negatives", [[-1, -2, -3]]),
                ("lopsided", [[1, 2, 3, None, None, 4, 5]])],
        edges=[("empty", [[]]), ("zero value", [[0]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Omitting null markers — in-order alone cannot reconstruct structure",
                  "Splitting on a delimiter that also appears in negative numbers",
                  "Consuming tokens with an index that the recursion forgets to advance"],
        nudge="Pre-order plus an explicit marker for every missing child is enough to "
              "rebuild the tree uniquely. Without the markers it is not.",
        visual="Write the tree depth-first, marking each empty branch. Reading the same "
               "sequence back in the same order rebuilds it exactly.",
        pseudocode="""
            serialize:   None -> '#'; else val, serialize(left), serialize(right)
            deserialize: token '#' -> None; else node, left = build(), right = build()
        """,
        tags=["core", "quora", "hard", "boss"],
    ))

    P.append(code_problem(
        id="tr-count-nodes", title="Census of the Grove", pattern="TREE",
        difficulty="TUTORIAL", family="tree_traverse", secondary=["RECURSION"], **common,
        statement="Return the number of nodes in the tree.",
        fn_name="count_nodes", params="root", reference=tree_ref(_count_nodes),
        canonical="""
            def count_nodes(root):
                if root is None:
                    return 0
                return 1 + count_nodes(root.left) + count_nodes(root.right)
        """,
        visible=[("classic", [SAMPLE]), ("single", [[1]])],
        hidden=[("chain", [DEEP]), ("balanced", [BST])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Missing the None base case"],
        nudge="Yourself, plus both subtrees.",
        visual="Each node reports one plus what its children report.",
        pseudocode="0 if None else 1 + count(left) + count(right)",
        tags=["tutorial"],
    ))

    P.append(code_problem(
        id="tr-sum-tree", title="Weight of the Canopy", pattern="TREE",
        difficulty="TUTORIAL", family="tree_traverse", secondary=["RECURSION"], **common,
        statement="Return the sum of every node value in the tree.",
        fn_name="sum_tree", params="root", reference=tree_ref(_sum_tree),
        canonical="""
            def sum_tree(root):
                if root is None:
                    return 0
                return root.val + sum_tree(root.left) + sum_tree(root.right)
        """,
        visible=[("classic", [SAMPLE]), ("single", [[5]])],
        hidden=[("negatives", [[-1, -2, -3]]), ("chain", [DEEP])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Forgetting the base case returns 0, not None"],
        nudge="Same shape as the census, with a different accumulator.",
        visual="Values flow upward and add.",
        pseudocode="0 if None else val + sum(left) + sum(right)",
        tags=["tutorial"],
    ))

    P.append(code_problem(
        id="sec-privilege-depth", title="Depth of Privilege", pattern="TREE",
        difficulty="EASY", family="tree_traverse", secondary=["RECURSION"],
        security=True, preamble=PREAMBLE, arg_adapters=["tree"],
        realm="binary_tree_canopy", viz=VIZ, starter_hint=TREE_HINT, profile_weight=QS,
        statement="""
            A privilege hierarchy is stored as a binary tree; each node is a role. Return
            the length of the longest chain of delegation from the root role to any leaf
            role, counting roles.
        """,
        fn_name="privilege_depth", params="root", reference=tree_ref(_max_priv_depth),
        canonical="""
            def privilege_depth(root):
                if root is None:
                    return 0
                return 1 + max(privilege_depth(root.left), privilege_depth(root.right))
        """,
        visible=[("three deep", [SAMPLE]), ("single role", [[1]])],
        hidden=[("chain", [DEEP]), ("balanced", [BST])],
        edges=[("no roles", [[]])],
        time_complexity="O(n)", space_complexity="O(h)",
        failures=["Off-by-one on the root"],
        nudge="Identical to Canopy Height wearing an org chart.",
        visual="The deepest delegation chain.",
        pseudocode="1 + max(depth(left), depth(right))",
        prerequisites=["tr-max-depth"], tags=["security", "transfer", "disguised"],
    ))

    return P
