"""Build-time tree helpers. Mirrors the adapters inside the sandbox harness."""
from __future__ import annotations


class TreeNode:
    __slots__ = ("val", "left", "right")

    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right


PREAMBLE = """
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
"""


def to_tree(values):
    if not values:
        return None
    root = TreeNode(values[0])
    queue, i, head = [root], 1, 0
    while head < len(queue) and i < len(values):
        node = queue[head]
        head += 1
        if i < len(values):
            v = values[i]; i += 1
            if v is not None:
                node.left = TreeNode(v)
                queue.append(node.left)
        if i < len(values):
            v = values[i]; i += 1
            if v is not None:
                node.right = TreeNode(v)
                queue.append(node.right)
    return root


def from_tree(node):
    if node is None:
        return []
    out, queue, head = [], [node], 0
    while head < len(queue):
        cur = queue[head]; head += 1
        if cur is None:
            out.append(None)
            continue
        out.append(cur.val)
        queue.append(cur.left)
        queue.append(cur.right)
    while out and out[-1] is None:
        out.pop()
    return out


def tree_ref(fn, *, returns_tree=False):
    """Wrap a TreeNode-taking reference so it accepts level-order lists."""
    def wrapper(values, *rest):
        result = fn(to_tree(values), *rest)
        return from_tree(result) if returns_tree else result
    return wrapper
